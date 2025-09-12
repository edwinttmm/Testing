import React, { useRef, useEffect, useCallback, useState } from 'react';
import { Box, IconButton, Typography, Tooltip } from '@mui/material';
import {
  PlayArrow,
  Pause,
  Fullscreen,
  FullscreenExit,
  ZoomIn,
  ZoomOut,
  FitScreen,
} from '@mui/icons-material';
import { VideoFile, GroundTruthObject } from '../services/types';

interface VideoViewportProps {
  video: VideoFile;
  groundTruthObjects: GroundTruthObject[];
  currentFrame: number;
  currentTime: number;
  isPlaying: boolean;
  zoomLevel: number;
  isFullscreen: boolean;
  selectedVruId: string | null;
  onTimeUpdate: (time: number, frame: number) => void;
  onPlayPause: () => void;
  onZoomChange: (zoom: number) => void;
  onFullscreenToggle: () => void;
  onObjectSelect: (vruId: string) => void;
  onObjectManipulate: (vruId: string, action: 'drag' | 'resize', data: any) => void;
  onFrameNavigation: (direction: 'next' | 'previous') => void;
  frameRate?: number;
}

const VideoViewport: React.FC<VideoViewportProps> = ({
  video,
  groundTruthObjects,
  currentFrame,
  currentTime,
  isPlaying,
  zoomLevel,
  isFullscreen,
  selectedVruId,
  onTimeUpdate,
  onPlayPause,
  onZoomChange,
  onFullscreenToggle,
  onObjectSelect,
  onObjectManipulate,
  onFrameNavigation,
  frameRate = 30,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [videoDimensions, setVideoDimensions] = useState({ width: 0, height: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [resizeHandle, setResizeHandle] = useState<string | null>(null);
  
  // Initialize video and canvas
  useEffect(() => {
    if (videoRef.current) {
      const videoElement = videoRef.current;
      
      const handleLoadedMetadata = () => {
        setVideoDimensions({
          width: videoElement.videoWidth,
          height: videoElement.videoHeight,
        });
        
        if (canvasRef.current) {
          canvasRef.current.width = videoElement.videoWidth;
          canvasRef.current.height = videoElement.videoHeight;
        }
      };
      
      const handleTimeUpdate = () => {
        const time = videoElement.currentTime;
        const frame = Math.floor(time * frameRate);
        onTimeUpdate(time, frame);
      };
      
      videoElement.addEventListener('loadedmetadata', handleLoadedMetadata);
      videoElement.addEventListener('timeupdate', handleTimeUpdate);
      
      return () => {
        videoElement.removeEventListener('loadedmetadata', handleLoadedMetadata);
        videoElement.removeEventListener('timeupdate', handleTimeUpdate);
      };
    }
  }, [frameRate, onTimeUpdate]);
  
  // Sync video time with currentTime prop
  useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 0.1) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);
  
  // Sync video play state
  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play().catch(console.error);
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);
  
  // Draw bounding boxes and annotations
  const drawBoundingBoxes = useCallback(() => {
    if (!canvasRef.current || !videoDimensions.width) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Filter objects for current frame
    const currentFrameObjects = groundTruthObjects.filter(
      obj => obj.frameNumber === currentFrame
    );
    
    currentFrameObjects.forEach(obj => {
      const { bbox, vruType, validated, vruId } = obj;
      const isSelected = vruId === selectedVruId;
      
      // Get VRU type color
      const color = getVRUColor(vruType);
      
      // Draw bounding box
      ctx.strokeStyle = isSelected ? '#2196f3' : color;
      ctx.lineWidth = isSelected ? 3 : validated ? 2 : 1;
      ctx.setLineDash(validated ? [] : [5, 5]);
      ctx.strokeRect(bbox.x, bbox.y, bbox.width, bbox.height);
      
      // Fill for selected objects
      if (isSelected) {
        ctx.fillStyle = 'rgba(33, 150, 243, 0.1)';
        ctx.fillRect(bbox.x, bbox.y, bbox.width, bbox.height);
      }
      
      // Draw resize handles for selected object
      if (isSelected) {
        drawResizeHandles(ctx, bbox);
      }
      
      // Draw label
      drawObjectLabel(ctx, obj, color);
      
      // Draw validation status
      if (validated) {
        drawValidationIndicator(ctx, bbox);
      }
    });
  }, [groundTruthObjects, currentFrame, selectedVruId, videoDimensions]);
  
  // Redraw when dependencies change
  useEffect(() => {
    drawBoundingBoxes();
  }, [drawBoundingBoxes]);
  
  // Canvas interaction handlers
  const handleCanvasMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX / zoomLevel;
    const y = (e.clientY - rect.top) * scaleY / zoomLevel;
    
    // Find clicked object
    const clickedObject = findObjectAtPoint(x, y);
    
    if (clickedObject) {
      onObjectSelect(clickedObject.vruId);
      
      // Check for resize handle
      const handle = getResizeHandle(x, y, clickedObject.bbox);
      if (handle) {
        setIsResizing(true);
        setResizeHandle(handle);
        setDragStart({ x, y });
      } else {
        setIsDragging(true);
        setDragStart({ 
          x: x - clickedObject.bbox.x, 
          y: y - clickedObject.bbox.y 
        });
      }
    }
  }, [zoomLevel, onObjectSelect]);
  
  const handleCanvasMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !dragStart || !selectedVruId) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX / zoomLevel;
    const y = (e.clientY - rect.top) * scaleY / zoomLevel;
    
    if (isDragging) {
      // Dragging object
      const newX = x - dragStart.x;
      const newY = y - dragStart.y;
      
      onObjectManipulate(selectedVruId, 'drag', { x: newX, y: newY });
    } else if (isResizing && resizeHandle) {
      // Resizing object
      const deltaX = x - dragStart.x;
      const deltaY = y - dragStart.y;
      
      onObjectManipulate(selectedVruId, 'resize', {
        handle: resizeHandle,
        deltaX,
        deltaY,
      });
      
      setDragStart({ x, y });
    }
  }, [
    isDragging,
    isResizing,
    dragStart,
    selectedVruId,
    zoomLevel,
    resizeHandle,
    onObjectManipulate,
  ]);
  
  const handleCanvasMouseUp = useCallback(() => {
    setIsDragging(false);
    setIsResizing(false);
    setDragStart(null);
    setResizeHandle(null);
  }, []);
  
  // Helper functions
  const findObjectAtPoint = useCallback((x: number, y: number) => {
    const currentFrameObjects = groundTruthObjects.filter(
      obj => obj.frameNumber === currentFrame
    );
    
    return currentFrameObjects.find(obj => {
      const { bbox } = obj;
      return x >= bbox.x && x <= bbox.x + bbox.width &&
             y >= bbox.y && y <= bbox.y + bbox.height;
    }) || null;
  }, [groundTruthObjects, currentFrame]);
  
  const getResizeHandle = useCallback((x: number, y: number, bbox: any): string | null => {
    const handleSize = 8;
    const { x: bx, y: by, width, height } = bbox;
    
    if (Math.abs(x - bx) < handleSize && Math.abs(y - by) < handleSize) return 'nw';
    if (Math.abs(x - (bx + width)) < handleSize && Math.abs(y - by) < handleSize) return 'ne';
    if (Math.abs(x - bx) < handleSize && Math.abs(y - (by + height)) < handleSize) return 'sw';
    if (Math.abs(x - (bx + width)) < handleSize && Math.abs(y - (by + height)) < handleSize) return 'se';
    
    return null;
  }, []);
  
  const getVRUColor = (vruType: string): string => {
    const colors = {
      pedestrian: '#ff5722',
      cyclist: '#2196f3',
      motorcyclist: '#ff9800',
      wheelchair: '#9c27b0',
      scooter: '#4caf50',
    };
    return colors[vruType as keyof typeof colors] || '#607d8b';
  };
  
  const drawResizeHandles = (ctx: CanvasRenderingContext2D, bbox: any) => {
    const handleSize = 6;
    ctx.fillStyle = '#2196f3';
    
    // Corner handles
    ctx.fillRect(bbox.x - handleSize/2, bbox.y - handleSize/2, handleSize, handleSize);
    ctx.fillRect(bbox.x + bbox.width - handleSize/2, bbox.y - handleSize/2, handleSize, handleSize);
    ctx.fillRect(bbox.x - handleSize/2, bbox.y + bbox.height - handleSize/2, handleSize, handleSize);
    ctx.fillRect(bbox.x + bbox.width - handleSize/2, bbox.y + bbox.height - handleSize/2, handleSize, handleSize);
  };
  
  const drawObjectLabel = (ctx: CanvasRenderingContext2D, obj: GroundTruthObject, color: string) => {
    const { bbox, vruId, vruType } = obj;
    
    ctx.fillStyle = color;
    ctx.font = '12px Arial';
    const labelText = `${vruId} (${vruType})`;
    const labelWidth = ctx.measureText(labelText).width;
    
    // Label background
    ctx.fillRect(bbox.x, bbox.y - 20, labelWidth + 4, 16);
    
    // Label text
    ctx.fillStyle = 'white';
    ctx.fillText(labelText, bbox.x + 2, bbox.y - 6);
  };
  
  const drawValidationIndicator = (ctx: CanvasRenderingContext2D, bbox: any) => {
    ctx.fillStyle = '#4caf50';
    ctx.fillRect(bbox.x + bbox.width - 15, bbox.y - 15, 12, 12);
    ctx.fillStyle = 'white';
    ctx.font = '10px Arial';
    ctx.fillText('✓', bbox.x + bbox.width - 12, bbox.y - 6);
  };
  
  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return; // Ignore if typing in input
      
      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          onFrameNavigation('previous');
          break;
        case 'ArrowRight':
          e.preventDefault();
          onFrameNavigation('next');
          break;
        case ' ':
          e.preventDefault();
          onPlayPause();
          break;
        case 'f':
          e.preventDefault();
          onFullscreenToggle();
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onFrameNavigation, onPlayPause, onFullscreenToggle]);
  
  return (
    <Box
      ref={containerRef}
      sx={{
        position: 'relative',
        width: '100%',
        height: isFullscreen ? '100vh' : '60vh',
        backgroundColor: '#000',
        overflow: 'hidden',
        borderRadius: isFullscreen ? 0 : 1,
        border: isFullscreen ? 'none' : '1px solid #ddd',
      }}
    >
      {/* Video Element */}
      <video
        ref={videoRef}
        src={video.filePath || `/api/videos/${video.id}/stream`}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          transform: `scale(${zoomLevel})`,
          transformOrigin: 'center center',
        }}
        controls={false}
        preload="metadata"
      />
      
      {/* Bounding Box Overlay */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'auto',
          cursor: isDragging ? 'grabbing' : isResizing ? 'nw-resize' : 'default',
        }}
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleCanvasMouseMove}
        onMouseUp={handleCanvasMouseUp}
      />
      
      {/* Video Controls Overlay */}
      <Box
        sx={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'rgba(0,0,0,0.7)',
          color: 'white',
          p: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <Tooltip title="Play/Pause (Space)">
          <IconButton size="small" onClick={onPlayPause} sx={{ color: 'white' }}>
            {isPlaying ? <Pause /> : <PlayArrow />}
          </IconButton>
        </Tooltip>
        
        <Typography variant="body2" sx={{ mx: 1, minWidth: '80px' }}>
          Frame: {currentFrame}
        </Typography>
        
        <Typography variant="body2" sx={{ mx: 1, minWidth: '100px' }}>
          Time: {currentTime.toFixed(2)}s
        </Typography>
        
        <Box sx={{ flexGrow: 1 }} />
        
        <Tooltip title="Zoom Out">
          <IconButton 
            size="small" 
            onClick={() => onZoomChange(Math.max(zoomLevel / 1.25, 0.25))} 
            sx={{ color: 'white' }}
          >
            <ZoomOut />
          </IconButton>
        </Tooltip>
        
        <Typography variant="body2" sx={{ mx: 1 }}>
          {Math.round(zoomLevel * 100)}%
        </Typography>
        
        <Tooltip title="Zoom In">
          <IconButton 
            size="small" 
            onClick={() => onZoomChange(Math.min(zoomLevel * 1.25, 4))} 
            sx={{ color: 'white' }}
          >
            <ZoomIn />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Fit Screen">
          <IconButton 
            size="small" 
            onClick={() => onZoomChange(1)} 
            sx={{ color: 'white' }}
          >
            <FitScreen />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Fullscreen (F)">
          <IconButton size="small" onClick={onFullscreenToggle} sx={{ color: 'white' }}>
            {isFullscreen ? <FullscreenExit /> : <Fullscreen />}
          </IconButton>
        </Tooltip>
      </Box>
      
      {/* Navigation hint */}
      <Box
        sx={{
          position: 'absolute',
          top: 10,
          right: 10,
          background: 'rgba(0,0,0,0.7)',
          color: 'white',
          px: 1,
          py: 0.5,
          borderRadius: 1,
          fontSize: '0.75rem',
        }}
      >
        ← → Frame navigation • Space: Play/Pause • F: Fullscreen
      </Box>
    </Box>
  );
};

export default VideoViewport;