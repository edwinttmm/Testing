import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Typography, Paper, IconButton, Chip, Button, Stack } from '@mui/material';
import { 
  PlayArrow, 
  Pause, 
  CameraAlt, 
  Visibility,
  VisibilityOff 
} from '@mui/icons-material';
import { VideoFile, GroundTruthAnnotation, VRUType } from '../services/types';
import { getDynamicVideoUrl } from '../utils/videoUtils';

interface EnhancedClassicVideoPlayerProps {
  video: VideoFile;
  annotations: GroundTruthAnnotation[];
  onAnnotationSelect?: (annotation: GroundTruthAnnotation) => void;
  onTimeUpdate?: (currentTime: number, frameNumber: number) => void;
  onCanvasClick?: (x: number, y: number, frameNumber: number, timestamp: number) => void;
  annotationMode: boolean;
  selectedAnnotation?: GroundTruthAnnotation | null;
  frameRate?: number;
  showDetectionControls?: boolean;
  detectionControlsComponent?: React.ReactNode;
  onVideoEnd?: () => void;
}

const VRU_TYPE_COLORS: Record<string, string> = {
  pedestrian: '#4caf50',
  cyclist: '#2196f3',
  motorcyclist: '#ff9800',
  wheelchair: '#9c27b0',
  scooter: '#00bcd4'
};

const EnhancedClassicVideoPlayer: React.FC<EnhancedClassicVideoPlayerProps> = ({
  video,
  annotations,
  onAnnotationSelect,
  onTimeUpdate,
  onCanvasClick,
  annotationMode,
  selectedAnnotation,
  frameRate = 30,
  showDetectionControls = false,
  detectionControlsComponent,
  onVideoEnd,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [showAnnotations, setShowAnnotations] = useState(true);
  const [videoDimensions, setVideoDimensions] = useState({ width: 0, height: 0 });

  // Draw annotations on canvas overlay
  const drawAnnotations = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    const container = containerRef.current;
    const ctx = canvas?.getContext('2d');
    
    if (!canvas || !video || !ctx || !container) return;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    if (!showAnnotations || annotations.length === 0) return;
    
    // Get current frame number
    const currentFrame = Math.floor(currentTime * frameRate);
    
    // Draw each annotation
    annotations.forEach((annotation, index) => {
      // Check if annotation is visible at current time (show all for now to debug)
      const annotationFrame = annotation.frameNumber || 0;
      const frameThreshold = 30; // Show within 30 frames to make it more visible
      const isVisible = annotationFrame === 0 || Math.abs(annotationFrame - currentFrame) < frameThreshold;
      
      // For debugging, show all annotations initially
      const shouldShow = true; // Change to isVisible when working
      
      if (!shouldShow) return;
      
      // Get bounding box - handle both camelCase and snake_case
      const bbox = annotation.boundingBox || (annotation as any).bounding_box;
      if (!bbox) {
        console.warn('Annotation missing bounding box:', annotation);
        return;
      }
      
      // Get the displayed video dimensions
      const containerRect = container.getBoundingClientRect();
      const videoRect = video.getBoundingClientRect();
      
      // Calculate the actual display dimensions of the video
      const videoAspectRatio = video.videoWidth / video.videoHeight;
      const containerAspectRatio = containerRect.width / containerRect.height;
      
      let displayWidth, displayHeight, offsetX = 0, offsetY = 0;
      
      if (videoAspectRatio > containerAspectRatio) {
        // Video is wider than container
        displayWidth = containerRect.width;
        displayHeight = containerRect.width / videoAspectRatio;
        offsetY = (containerRect.height - displayHeight) / 2;
      } else {
        // Video is taller than container
        displayHeight = containerRect.height;
        displayWidth = containerRect.height * videoAspectRatio;
        offsetX = (containerRect.width - displayWidth) / 2;
      }
      
      // Calculate scale factors from video native dimensions to display dimensions
      const scaleX = displayWidth / video.videoWidth;
      const scaleY = displayHeight / video.videoHeight;
      
      // Scale bounding box coordinates
      let scaledX = (bbox.x * scaleX) + offsetX;
      let scaledY = (bbox.y * scaleY) + offsetY;
      let scaledWidth = bbox.width * scaleX;
      let scaledHeight = bbox.height * scaleY;

      // Clip bounding boxes to canvas bounds (objects can leave frame edges)
      // Only skip drawing if the box is completely outside canvas
      const isCompletelyOutside =
        scaledX + scaledWidth < 0 ||
        scaledY + scaledHeight < 0 ||
        scaledX > canvas.width ||
        scaledY > canvas.height;

      if (isCompletelyOutside) {
        return; // Skip this annotation entirely
      }

      // Clip coordinates to canvas bounds for partial visibility
      const clippedX = Math.max(0, scaledX);
      const clippedY = Math.max(0, scaledY);
      const clippedWidth = Math.min(scaledWidth, canvas.width - clippedX);
      const clippedHeight = Math.min(scaledHeight, canvas.height - clippedY);

      // Set style based on selection
      const isSelected = selectedAnnotation?.id === annotation.id;
      const color = VRU_TYPE_COLORS[annotation.vruType] || '#ff0000';

      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 4 : 3;
      ctx.setLineDash(isSelected ? [] : []);

      // Draw rectangle (use original coordinates for proper partial rendering)
      ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

      // Draw label background (ensure label stays within canvas)
      ctx.fillStyle = color;
      const labelHeight = 25;
      const labelX = Math.max(0, Math.min(scaledX, canvas.width - 100));
      const labelY = Math.max(labelHeight, scaledY);
      ctx.fillRect(labelX, labelY - labelHeight, Math.max(Math.min(scaledWidth, 100), 100), labelHeight);

      // Draw label text
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 12px Arial';
      const confidence = (bbox.confidence || annotation.confidence || 0) * 100;
      const labelText = `${annotation.vruType} (${Math.round(confidence)}%) #${index + 1}`;
      ctx.fillText(
        labelText,
        labelX + 3,
        labelY - 8
      );
      
      // Debug info in corner
      if (index === 0) {
        ctx.fillStyle = 'rgba(0,0,0,0.7)';
        ctx.fillRect(5, 5, 300, 100);
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px Arial';
        ctx.fillText(`Annotations: ${annotations.length}`, 10, 20);
        ctx.fillText(`Frame: ${currentFrame} / Target: ${annotationFrame}`, 10, 35);
        ctx.fillText(`Video: ${video.videoWidth}x${video.videoHeight}`, 10, 50);
        ctx.fillText(`Display: ${Math.round(displayWidth)}x${Math.round(displayHeight)}`, 10, 65);
        ctx.fillText(`Scale: ${scaleX.toFixed(2)}, ${scaleY.toFixed(2)}`, 10, 80);
        ctx.fillText(`Canvas: ${canvas.width}x${canvas.height}`, 10, 95);
      }
      
      ctx.setLineDash([]);
    });
  }, [annotations, currentTime, frameRate, selectedAnnotation, showAnnotations]);

  // Update canvas size when video loads
  const handleVideoLoadedMetadata = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    
    if (!video || !canvas || !container) return;
    
    // Set canvas size to match video display size
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    
    setVideoDimensions({
      width: video.videoWidth,
      height: video.videoHeight
    });
  }, []);

  // Handle time update
  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    
    const time = video.currentTime;
    setCurrentTime(time);
    
    const frameNumber = Math.floor(time * frameRate);
    onTimeUpdate?.(time, frameNumber);
    
    // Redraw annotations
    drawAnnotations();
  }, [frameRate, onTimeUpdate, drawAnnotations]);

  // Handle canvas click
  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Scale coordinates to video dimensions
    const scaleX = video.videoWidth / canvas.width;
    const scaleY = video.videoHeight / canvas.height;
    
    const videoX = x * scaleX;
    const videoY = y * scaleY;
    
    const frameNumber = Math.floor(currentTime * frameRate);
    
    // Check if click is on an annotation
    annotations.forEach(annotation => {
      const bbox = annotation.boundingBox || (annotation as any).bounding_box;
      if (!bbox) return;
      
      if (
        videoX >= bbox.x &&
        videoX <= bbox.x + bbox.width &&
        videoY >= bbox.y &&
        videoY <= bbox.y + bbox.height
      ) {
        onAnnotationSelect?.(annotation);
      }
    });
    
    onCanvasClick?.(videoX, videoY, frameNumber, currentTime);
  }, [annotations, currentTime, frameRate, onAnnotationSelect, onCanvasClick]);

  // Take snapshot and save to backend/dataset
  const takeSnapshot = useCallback(async () => {
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    
    if (!video) {
      console.error('Video element not available for snapshot');
      return;
    }
    
    // Ensure video has proper dimensions
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      console.error('Video dimensions not available:', { width: video.videoWidth, height: video.videoHeight });
      return;
    }
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.error('Canvas context not available');
      return;
    }
    
    try {
      // Draw video frame
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Draw annotations on snapshot with proper scaling
      const canvasElement = canvasRef.current;
      const videoElement = videoRef.current;
      
      if (canvasElement && videoElement) {
        // Calculate scale factors for proper annotation placement
        const scaleX = canvas.width / canvasElement.width;
        const scaleY = canvas.height / canvasElement.height;
        
        annotations.forEach(annotation => {
          const bbox = annotation.boundingBox || (annotation as any).bounding_box;
          if (!bbox) {
            console.warn('Annotation missing bounding box:', annotation);
            return;
          }
          
          // Scale bounding box to original video dimensions
          const scaledX = bbox.x * scaleX;
          const scaledY = bbox.y * scaleY;
          const scaledWidth = bbox.width * scaleX;
          const scaledHeight = bbox.height * scaleY;
          
          const color = VRU_TYPE_COLORS[annotation.vruType] || '#ff0000';
          ctx.strokeStyle = color;
          ctx.lineWidth = 3;
          ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
          
          // Draw label background
          ctx.fillStyle = color;
          const labelHeight = 30;
          ctx.fillRect(scaledX, scaledY - labelHeight, scaledWidth, labelHeight);
          
          // Draw label text
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 16px Arial';
          ctx.fillText(
            `${annotation.vruType} (${Math.round((bbox.confidence || 0) * 100)}%)`,
            scaledX + 5,
            scaledY - 8
          );
        });
      }
      
      // Convert to blob and save to backend
      canvas.toBlob(async (blob) => {
        if (!blob) {
          console.error('Failed to create snapshot blob');
          return;
        }
        
        try {
          // Create FormData to send to backend
          const formData = new FormData();
          const frameNumber = Math.floor(currentTime * frameRate);
          const filename = `snapshot_${video.id || 'unknown'}_frame_${frameNumber}_${Date.now()}.png`;
          
          formData.append('file', blob, filename);
          formData.append('video_id', video.id || '');
          formData.append('frame_number', frameNumber.toString());
          formData.append('timestamp', currentTime.toString());
          formData.append('annotation_count', annotations.length.toString());
          
          // Save to backend
          const response = await fetch('/api/snapshots/save', {
            method: 'POST',
            body: formData,
          });
          
          if (response.ok) {
            const result = await response.json();
            console.log('Snapshot saved to dataset:', result);
            
            // Also download locally for immediate use
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
          } else {
            console.error('Failed to save snapshot to backend:', response.statusText);
            // Fallback to local download
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
          }
        } catch (error) {
          console.error('Error saving snapshot:', error);
          // Fallback to local download
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `snapshot_frame_${Math.floor(currentTime * frameRate)}_${Date.now()}.png`;
          a.click();
          URL.revokeObjectURL(url);
        }
      }, 'image/png');
    } catch (error) {
      console.error('Error creating snapshot:', error);
    }
  }, [annotations, currentTime, frameRate, video]);

  // Play/pause toggle
  const togglePlayPause = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    
    if (isPlaying) {
      video.pause();
    } else {
      video.play();
    }
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  // Setup resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    
    const resizeObserver = new ResizeObserver(() => {
      handleVideoLoadedMetadata();
    });
    
    resizeObserver.observe(container);
    
    return () => {
      resizeObserver.disconnect();
    };
  }, [handleVideoLoadedMetadata]);

  // Redraw when annotations change
  useEffect(() => {
    drawAnnotations();
  }, [annotations, drawAnnotations]);

  return (
    <Paper elevation={2} sx={{ p: 2 }}>
      <Stack spacing={2}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            {video.filename || video.originalName || 'Video Player'}
          </Typography>
          <Stack direction="row" spacing={1}>
            <Chip 
              label={`${annotations.length} annotations`}
              color="primary"
              size="small"
            />
            {annotationMode && (
              <Chip 
                label="Annotation Mode"
                color="secondary"
                size="small"
              />
            )}
          </Stack>
        </Box>
        
        <Box 
          ref={containerRef}
          sx={{ 
            position: 'relative',
            width: '100%',
            backgroundColor: '#000',
            borderRadius: 1,
            overflow: 'hidden'
          }}
        >
          <video
            ref={videoRef}
            src={getDynamicVideoUrl(video.id)}
            style={{ 
              width: '100%',
              height: 'auto',
              display: 'block'
            }}
            onLoadedMetadata={handleVideoLoadedMetadata}
            onTimeUpdate={handleTimeUpdate}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={() => {
              setIsPlaying(false);
              onVideoEnd?.();
            }}
            controls={false}
            crossOrigin="anonymous"
          />
          
          <canvas
            ref={canvasRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: annotationMode ? 'auto' : 'none',
              cursor: annotationMode ? 'crosshair' : 'default'
            }}
            onClick={handleCanvasClick}
          />
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <IconButton onClick={togglePlayPause} color="primary">
            {isPlaying ? <Pause /> : <PlayArrow />}
          </IconButton>
          
          <Typography variant="body2" sx={{ minWidth: 100 }}>
            Frame: {Math.floor(currentTime * frameRate)}
          </Typography>
          
          <Box sx={{ flex: 1 }} />
          
          <Button
            startIcon={<CameraAlt />}
            onClick={takeSnapshot}
            variant="outlined"
            size="small"
          >
            Snapshot
          </Button>
          
          <IconButton 
            onClick={() => setShowAnnotations(!showAnnotations)}
            color={showAnnotations ? 'primary' : 'default'}
          >
            {showAnnotations ? <Visibility /> : <VisibilityOff />}
          </IconButton>
        </Box>
        
        {videoDimensions.width > 0 && (
          <Typography variant="caption" color="text.secondary">
            Video: {videoDimensions.width}x{videoDimensions.height} | 
            Display: {canvasRef.current?.width}x{canvasRef.current?.height}
          </Typography>
        )}
        
        {showDetectionControls && detectionControlsComponent && (
          <Box sx={{ mt: 2 }}>
            {detectionControlsComponent}
          </Box>
        )}
      </Stack>
    </Paper>
  );
};

export default EnhancedClassicVideoPlayer;