import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  IconButton,
  Tooltip,
  Chip,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Paper,
  LinearProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  ButtonGroup,
  TextField,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  FastForward,
  FastRewind,
  CropFree,
  Edit,
  Delete,
  Check,
  Close,
  CallSplit,
  CallMerge,
  Visibility,
  VisibilityOff,
  Save,
  Fullscreen,
  FullscreenExit,
  ZoomIn,
  ZoomOut,
  RestartAlt,
} from '@mui/icons-material';
import { VideoFile, GroundTruthAnnotation, VRUType, BoundingBox } from '../services/types';
import ValidationWorkflowPanel from './ValidationWorkflowPanel';
import { getErrorMessage } from '../utils/errorUtils';
import { apiService } from '../services/api';

// PRD-aligned interfaces using exact variable names from GLOBAL_VARIABLES_REFERENCE.md
interface VideoValidationSession {
  id: string;
  videoId: string;
  projectId: string;
  groundTruthObjects: GroundTruthObject[];
  validated: boolean;
  validatedAt?: string;
  validatedBy?: string;
}

interface GroundTruthObject {
  id: string;
  videoId: string;
  vruId: string;          // PRD: Persistent VRU ID
  vruType: VRUType;
  frameNumber: number;
  timestampMs: number;    // PRD: timestamp in milliseconds
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  confidence: number;
  validated: boolean;
  selected?: boolean;
  mergeCandidate?: boolean;
  splitCandidate?: boolean;
}

interface TimelineMarker {
  frameNumber: number;
  timestampMs: number;
  vruId: string;
  vruType: VRUType;
  validated: boolean;
}

interface AnnotationValidationInterfaceProps {
  video: VideoFile;
  onValidationComplete: (validated: boolean) => void;
  onClose: () => void;
  initialAnnotations?: GroundTruthAnnotation[];
}

const AnnotationValidationInterface: React.FC<AnnotationValidationInterfaceProps> = ({
  video,
  onValidationComplete,
  onClose,
  initialAnnotations = []
}) => {
  // Core state using PRD-aligned naming
  const [groundTruthObjects, setGroundTruthObjects] = useState<GroundTruthObject[]>([]);
  const [selectedVruId, setSelectedVruId] = useState<string | null>(null);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [currentTimestampMs, setCurrentTimestampMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [totalFrames, setTotalFrames] = useState(0);
  const [frameRate, setFrameRate] = useState(30);
  
  // Video viewport state
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [videoDimensions, setVideoDimensions] = useState({ width: 0, height: 0 });
  
  // Annotation manipulation state
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [resizeHandle, setResizeHandle] = useState<'nw' | 'ne' | 'sw' | 'se' | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  
  // VRU management state
  const [mergeMode, setMergeMode] = useState(false);
  const [splitMode, setSplitMode] = useState(false);
  const [mergeSelection, setMergeSelection] = useState<Set<string>>(new Set());
  const [showValidatedOnly, setShowValidatedOnly] = useState(false);
  
  // Validation workflow state
  const [validationSession, setValidationSession] = useState<VideoValidationSession | null>(null);
  const [isValidated, setIsValidated] = useState(false);
  const [validationDialog, setValidationDialog] = useState(false);
  
  // UI state
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [timelineVisible, setTimelineVisible] = useState(true);
  
  // Refs for video and canvas
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize validated state from incoming video status on mount or when video changes
  useEffect(() => {
    try {
      const status = (video as any)?.status || (video as any)?.validationStatus || (video as any)?.validation_status;
      if (typeof status === 'string') {
        const normalized = status.toLowerCase();
        if (normalized.includes('validated')) {
          setIsValidated(true);
          return;
        }
      }
    } catch {}
    // Fallback: leave as-is; panel will show "Ready for Validation" when 100%
  }, [video]);
  
  // Convert initial annotations to ground truth objects
  useEffect(() => {
    const convertedObjects: GroundTruthObject[] = initialAnnotations.map(annotation => ({
      id: annotation.id,
      videoId: annotation.videoId,
      vruId: annotation.detectionId || `VRU_${annotation.id}`,
      vruType: annotation.vruType,
      frameNumber: annotation.frameNumber,
      timestampMs: annotation.timestamp * 1000, // Convert to milliseconds
      bbox: {
        x: annotation.boundingBox.x,
        y: annotation.boundingBox.y,
        width: annotation.boundingBox.width,
        height: annotation.boundingBox.height,
      },
      confidence: annotation.boundingBox.confidence || 1.0,
      validated: annotation.validated || false,
    }));
    
    setGroundTruthObjects(convertedObjects);
    
    // Calculate total frames from video duration
    if (video.duration && video.frameRate) {
      setTotalFrames(Math.floor(video.duration * video.frameRate));
      setFrameRate(video.frameRate);
    }
  }, [initialAnnotations, video]);
  
  // Generate timeline markers from ground truth objects
  const timelineMarkers = useMemo<TimelineMarker[]>(() => {
    return groundTruthObjects.map(obj => ({
      frameNumber: obj.frameNumber,
      timestampMs: obj.timestampMs,
      vruId: obj.vruId,
      vruType: obj.vruType,
      validated: obj.validated,
    }));
  }, [groundTruthObjects]);
  
  // Filter objects based on current frame and validation status
  const currentFrameObjects = useMemo(() => {
    return groundTruthObjects.filter(obj => {
      const frameMatch = obj.frameNumber === currentFrame;
      const validationMatch = showValidatedOnly ? obj.validated : true;
      return frameMatch && validationMatch;
    });
  }, [groundTruthObjects, currentFrame, showValidatedOnly]);
  
  // Large central video viewport with bounding box overlay
  const renderVideoViewport = () => (
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
        src={`http://localhost:8000/api/videos/${video.id}/file`}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          transform: `scale(${zoomLevel})`,
          transformOrigin: 'center center',
        }}
        onLoadedMetadata={handleVideoLoaded}
        onTimeUpdate={handleTimeUpdate}
        onCanPlay={handleCanPlay}
        controls={false}
        preload="metadata"
      />
      
      {/* Bounding Box Overlay Canvas */}
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
        onDoubleClick={handleCanvasDoubleClick}
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
        <IconButton size="small" onClick={handlePlayPause} sx={{ color: 'white' }}>
          {isPlaying ? <Pause /> : <PlayArrow />}
        </IconButton>
        
        <IconButton size="small" onClick={handlePreviousFrame} sx={{ color: 'white' }}>
          <SkipPrevious />
        </IconButton>
        
        <IconButton size="small" onClick={handleNextFrame} sx={{ color: 'white' }}>
          <SkipNext />
        </IconButton>
        
        <Typography variant="body2" sx={{ mx: 1, minWidth: '80px' }}>
          {currentFrame} / {totalFrames}
        </Typography>
        
        <Typography variant="body2" sx={{ mx: 1, minWidth: '100px' }}>
          {(currentTimestampMs / 1000).toFixed(2)}s
        </Typography>
        
        <Box sx={{ flexGrow: 1 }} />
        
        <IconButton size="small" onClick={handleZoomOut} sx={{ color: 'white' }}>
          <ZoomOut />
        </IconButton>
        
        <Typography variant="body2" sx={{ mx: 1 }}>
          {Math.round(zoomLevel * 100)}%
        </Typography>
        
        <IconButton size="small" onClick={handleZoomIn} sx={{ color: 'white' }}>
          <ZoomIn />
        </IconButton>
        
        <IconButton size="small" onClick={handleToggleFullscreen} sx={{ color: 'white' }}>
          {isFullscreen ? <FullscreenExit /> : <Fullscreen />}
        </IconButton>
      </Box>
      
      {/* Frame-by-frame navigation hint */}
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
        Use ← → keys for frame navigation
      </Box>
    </Box>
  );
  
  // Interactive timeline with annotation markers
  const renderTimeline = () => (
    <Card sx={{ mt: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Interactive Timeline</Typography>
          <Button
            size="small"
            onClick={() => setTimelineVisible(!timelineVisible)}
            startIcon={timelineVisible ? <VisibilityOff /> : <Visibility />}
          >
            {timelineVisible ? 'Hide' : 'Show'} Timeline
          </Button>
        </Box>
        
        {timelineVisible && (
          <Box>
            {/* Timeline progress bar */}
            <Box sx={{ position: 'relative', mb: 2 }}>
              <LinearProgress
                variant="determinate"
                value={(currentFrame / totalFrames) * 100}
                sx={{ height: 8, borderRadius: 4 }}
              />
              
              {/* Annotation markers */}
              {timelineMarkers.map((marker, index) => (
                <Box
                  key={`${marker.vruId}-${marker.frameNumber}`}
                  sx={{
                    position: 'absolute',
                    left: `${(marker.frameNumber / totalFrames) * 100}%`,
                    top: 0,
                    width: 3,
                    height: 8,
                    backgroundColor: getVRUColor(marker.vruType),
                    borderRadius: '0 0 2px 2px',
                    cursor: 'pointer',
                    opacity: marker.validated ? 1 : 0.6,
                    border: selectedVruId === marker.vruId ? '2px solid white' : 'none',
                  }}
                  onClick={() => handleTimelineMarkerClick(marker)}
                  title={`${marker.vruType} at frame ${marker.frameNumber} (${marker.validated ? 'Validated' : 'Pending'})`}
                />
              ))}
              
              {/* Current position indicator */}
              <Box
                sx={{
                  position: 'absolute',
                  left: `${(currentFrame / totalFrames) * 100}%`,
                  top: -2,
                  width: 2,
                  height: 12,
                  backgroundColor: 'red',
                  borderRadius: 1,
                }}
              />
            </Box>
            
            {/* Timeline controls */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                type="number"
                label="Frame"
                value={currentFrame}
                onChange={handleFrameInput}
                size="small"
                sx={{ width: 100 }}
                inputProps={{ min: 0, max: totalFrames }}
              />
              
              <TextField
                type="number"
                label="Time (s)"
                value={(currentTimestampMs / 1000).toFixed(2)}
                onChange={handleTimeInput}
                size="small"
                sx={{ width: 100 }}
                inputProps={{ step: 0.1, min: 0, max: video.duration }}
              />
              
              <ButtonGroup size="small">
                <Button onClick={() => jumpToFrame(0)}>Start</Button>
                <Button onClick={() => jumpToFrame(totalFrames)}>End</Button>
              </ButtonGroup>
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
  
  // Object management panel
  const renderObjectManagement = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          VRU Object Management
        </Typography>
        
        {/* Controls */}
        <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button
            variant={mergeMode ? 'contained' : 'outlined'}
            size="small"
            onClick={() => {
              setMergeMode(!mergeMode);
              setSplitMode(false);
              setMergeSelection(new Set());
            }}
            startIcon={<CallMerge />}
          >
            Merge VRUs
          </Button>
          
          <Button
            variant={splitMode ? 'contained' : 'outlined'}
            size="small"
            onClick={() => {
              setSplitMode(!splitMode);
              setMergeMode(false);
              setMergeSelection(new Set());
            }}
            startIcon={<CallSplit />}
          >
            Split VRU
          </Button>
          
          <Button
            size="small"
            onClick={() => setShowValidatedOnly(!showValidatedOnly)}
            variant={showValidatedOnly ? 'contained' : 'outlined'}
          >
            {showValidatedOnly ? 'Show All' : 'Validated Only'}
          </Button>
        </Box>
        
        {/* Object list for current frame */}
        <Typography variant="subtitle2" gutterBottom>
          Current Frame Objects ({currentFrameObjects.length})
        </Typography>
        
        <List dense>
          {currentFrameObjects.map((obj) => (
            <ListItem
              key={obj.id}
              sx={{
                border: obj.selected ? '2px solid #2196f3' : '1px solid #ddd',
                borderRadius: 1,
                mb: 1,
                backgroundColor: mergeSelection.has(obj.vruId) ? 'rgba(33, 150, 243, 0.1)' : 'transparent',
              }}
              onClick={() => handleObjectSelect(obj)}
            >
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip
                      label={obj.vruType}
                      size="small"
                      sx={{ backgroundColor: getVRUColor(obj.vruType), color: 'white' }}
                    />
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {obj.vruId}
                    </Typography>
                    {obj.validated && <Check color="success" fontSize="small" />}
                    {mergeMode && (
                      <input
                        type="checkbox"
                        checked={mergeSelection.has(obj.vruId)}
                        onChange={(e) => handleMergeSelection(obj.vruId, e.target.checked)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}
                  </Box>
                }
                secondary={
                  <Box>
                    <Typography variant="caption">
                      Confidence: {(obj.confidence * 100).toFixed(1)}%
                    </Typography>
                    <br />
                    <Typography variant="caption">
                      BBox: ({obj.bbox.x.toFixed(0)}, {obj.bbox.y.toFixed(0)}, {obj.bbox.width.toFixed(0)}x{obj.bbox.height.toFixed(0)})
                    </Typography>
                  </Box>
                }
              />
              
              <ListItemSecondaryAction>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  <FormControl size="small" sx={{ minWidth: 100 }}>
                    <Select
                      value={obj.vruType}
                      onChange={(e) => handleVRUTypeChange(obj.id, e.target.value as VRUType)}
                      size="small"
                    >
                      <MenuItem value="pedestrian">Pedestrian</MenuItem>
                      <MenuItem value="cyclist">Cyclist</MenuItem>
                      <MenuItem value="motorcyclist">Motorcyclist</MenuItem>
                      <MenuItem value="wheelchair">Wheelchair</MenuItem>
                      <MenuItem value="scooter">Scooter</MenuItem>
                    </Select>
                  </FormControl>
                  
                  <Tooltip title={obj.validated ? 'Mark as Pending' : 'Validate'}>
                    <IconButton
                      size="small"
                      onClick={() => handleObjectValidate(obj.id, !obj.validated)}
                      color={obj.validated ? 'success' : 'default'}
                    >
                      <Check />
                    </IconButton>
                  </Tooltip>
                  
                  <Tooltip title="Delete Object">
                    <IconButton
                      size="small"
                      onClick={() => handleObjectDelete(obj.id)}
                      color="error"
                    >
                      <Delete />
                    </IconButton>
                  </Tooltip>
                </Box>
              </ListItemSecondaryAction>
            </ListItem>
          ))}
          
          {currentFrameObjects.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
              No objects in current frame
            </Typography>
          )}
        </List>
        
        {/* Merge/Split actions */}
        {mergeMode && mergeSelection.size > 1 && (
          <Box sx={{ mt: 2, p: 2, border: '1px solid #2196f3', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Merge {mergeSelection.size} VRUs
            </Typography>
            <Button
              variant="contained"
              size="small"
              onClick={handleMergeVRUs}
              startIcon={<CallMerge />}
            >
              Merge Selected
            </Button>
          </Box>
        )}
        
        {splitMode && selectedVruId && (
          <Box sx={{ mt: 2, p: 2, border: '1px solid #ff9800', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Split VRU: {selectedVruId}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Click on the bounding box to create split points
            </Typography>
            <Button
              variant="contained"
              size="small"
              onClick={handleSplitVRU}
              startIcon={<CallSplit />}
            >
              Confirm Split
            </Button>
          </Box>
        )}
      </CardContent>
    </Card>
  );
  
  
  // Event handlers
  const handleVideoLoaded = useCallback(() => {
    if (videoRef.current) {
      const video = videoRef.current;
      setVideoDimensions({ width: video.videoWidth, height: video.videoHeight });
      setTotalFrames(Math.floor(video.duration * frameRate));
      
      // Initialize canvas
      if (canvasRef.current) {
        const canvas = canvasRef.current;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }
    }
  }, [frameRate]);
  
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      const currentTime = videoRef.current.currentTime;
      const frame = Math.floor(currentTime * frameRate);
      setCurrentFrame(frame);
      setCurrentTimestampMs(currentTime * 1000);
      
      // Redraw bounding boxes
      drawBoundingBoxes();
    }
  }, [frameRate]);
  
  const handleCanPlay = useCallback(() => {
    // Video is ready to play
    drawBoundingBoxes();
  }, []);
  
  const handlePlayPause = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  }, [isPlaying]);
  
  const handleNextFrame = useCallback(() => {
    if (videoRef.current && currentFrame < totalFrames - 1) {
      const newFrame = currentFrame + 1;
      const newTime = newFrame / frameRate;
      videoRef.current.currentTime = newTime;
      setCurrentFrame(newFrame);
      setCurrentTimestampMs(newTime * 1000);
    }
  }, [currentFrame, totalFrames, frameRate]);
  
  const handlePreviousFrame = useCallback(() => {
    if (videoRef.current && currentFrame > 0) {
      const newFrame = currentFrame - 1;
      const newTime = newFrame / frameRate;
      videoRef.current.currentTime = newTime;
      setCurrentFrame(newFrame);
      setCurrentTimestampMs(newTime * 1000);
    }
  }, [currentFrame, frameRate]);
  
  const jumpToFrame = useCallback((frame: number) => {
    if (videoRef.current) {
      const clampedFrame = Math.max(0, Math.min(frame, totalFrames - 1));
      const newTime = clampedFrame / frameRate;
      videoRef.current.currentTime = newTime;
      setCurrentFrame(clampedFrame);
      setCurrentTimestampMs(newTime * 1000);
    }
  }, [totalFrames, frameRate]);
  
  const handleFrameInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const frame = parseInt(e.target.value);
    if (!isNaN(frame)) {
      jumpToFrame(frame);
    }
  }, [jumpToFrame]);
  
  const handleTimeInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (!isNaN(time)) {
      const frame = Math.floor(time * frameRate);
      jumpToFrame(frame);
    }
  }, [frameRate, jumpToFrame]);
  
  const handleTimelineMarkerClick = useCallback((marker: TimelineMarker) => {
    jumpToFrame(marker.frameNumber);
    setSelectedVruId(marker.vruId);
  }, [jumpToFrame]);
  
  const handleZoomIn = useCallback(() => {
    setZoomLevel(prev => Math.min(prev * 1.25, 4));
  }, []);
  
  const handleZoomOut = useCallback(() => {
    setZoomLevel(prev => Math.max(prev / 1.25, 0.25));
  }, []);
  
  const handleToggleFullscreen = useCallback(() => {
    if (!isFullscreen) {
      if (containerRef.current?.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);
  
  // Canvas interaction handlers for direct bounding box manipulation
  const handleCanvasMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX / zoomLevel;
    const y = (e.clientY - rect.top) * scaleY / zoomLevel;
    
    // Check if clicking on existing bounding box or resize handle
    const clickedObject = findObjectAtPoint(x, y);
    
    if (clickedObject) {
      setSelectedVruId(clickedObject.vruId);
      
      // Check if clicking on resize handle
      const handle = getResizeHandle(x, y, clickedObject.bbox);
      if (handle) {
        setIsResizing(true);
        setResizeHandle(handle);
        setDragStart({ x, y });
      } else {
        setIsDragging(true);
        setDragStart({ x: x - clickedObject.bbox.x, y: y - clickedObject.bbox.y });
      }
    }
  }, [zoomLevel]);
  
  const handleCanvasMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !dragStart) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX / zoomLevel;
    const y = (e.clientY - rect.top) * scaleY / zoomLevel;
    
    if (isDragging && selectedVruId) {
      // Move bounding box
      const newX = x - dragStart.x;
      const newY = y - dragStart.y;
      
      updateObjectBoundingBox(selectedVruId, { x: newX, y: newY });
    } else if (isResizing && selectedVruId && resizeHandle) {
      // Resize bounding box
      const deltaX = x - dragStart.x;
      const deltaY = y - dragStart.y;
      
      resizeBoundingBox(selectedVruId, resizeHandle, deltaX, deltaY);
      setDragStart({ x, y });
    }
    
    drawBoundingBoxes();
  }, [isDragging, isResizing, selectedVruId, resizeHandle, dragStart, zoomLevel]);
  
  const handleCanvasMouseUp = useCallback(() => {
    setIsDragging(false);
    setIsResizing(false);
    setResizeHandle(null);
    setDragStart(null);
  }, []);
  
  const handleCanvasDoubleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    // Create new bounding box on double-click
    if (!canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX / zoomLevel;
    const y = (e.clientY - rect.top) * scaleY / zoomLevel;
    
    handleCreateNewObject(x, y);
  }, [zoomLevel]);
  
  // Object manipulation functions
  const findObjectAtPoint = useCallback((x: number, y: number): GroundTruthObject | null => {
    for (const obj of currentFrameObjects) {
      const bbox = obj.bbox;
      if (x >= bbox.x && x <= bbox.x + bbox.width &&
          y >= bbox.y && y <= bbox.y + bbox.height) {
        return obj;
      }
    }
    return null;
  }, [currentFrameObjects]);
  
  const getResizeHandle = useCallback((x: number, y: number, bbox: BoundingBox): 'nw' | 'ne' | 'sw' | 'se' | null => {
    const handleSize = 8;
    const { x: bx, y: by, width, height } = bbox;
    
    // Check each corner
    if (Math.abs(x - bx) < handleSize && Math.abs(y - by) < handleSize) return 'nw';
    if (Math.abs(x - (bx + width)) < handleSize && Math.abs(y - by) < handleSize) return 'ne';
    if (Math.abs(x - bx) < handleSize && Math.abs(y - (by + height)) < handleSize) return 'sw';
    if (Math.abs(x - (bx + width)) < handleSize && Math.abs(y - (by + height)) < handleSize) return 'se';
    
    return null;
  }, []);
  
  const updateObjectBoundingBox = useCallback((vruId: string, updates: Partial<BoundingBox>) => {
    setGroundTruthObjects(prev => prev.map(obj => 
      obj.vruId === vruId 
        ? { ...obj, bbox: { ...obj.bbox, ...updates } }
        : obj
    ));
  }, []);
  
  const resizeBoundingBox = useCallback((vruId: string, handle: string, deltaX: number, deltaY: number) => {
    setGroundTruthObjects(prev => prev.map(obj => {
      if (obj.vruId !== vruId) return obj;
      
      const bbox = { ...obj.bbox };
      
      switch (handle) {
        case 'nw':
          bbox.x += deltaX;
          bbox.y += deltaY;
          bbox.width -= deltaX;
          bbox.height -= deltaY;
          break;
        case 'ne':
          bbox.y += deltaY;
          bbox.width += deltaX;
          bbox.height -= deltaY;
          break;
        case 'sw':
          bbox.x += deltaX;
          bbox.width -= deltaX;
          bbox.height += deltaY;
          break;
        case 'se':
          bbox.width += deltaX;
          bbox.height += deltaY;
          break;
      }
      
      // Ensure minimum size
      bbox.width = Math.max(bbox.width, 10);
      bbox.height = Math.max(bbox.height, 10);
      
      return { ...obj, bbox };
    }));
  }, []);
  
  const handleCreateNewObject = useCallback(async (x: number, y: number) => {
    try {
      const newVruId = `VRU_${Date.now()}`;
      const newObject: GroundTruthObject = {
        id: `new_${Date.now()}`,
        videoId: video.id,
        vruId: newVruId,
        vruType: VRUType.PEDESTRIAN,
        frameNumber: currentFrame,
        timestampMs: currentTimestampMs,
        bbox: {
          x: x - 25,
          y: y - 50,
          width: 50,
          height: 100,
        },
        confidence: 1.0,
        validated: false,
      };
      
      // Create on backend
      const annotation = await apiService.createAnnotation(video.id, {
        videoId: video.id,
        detectionId: newVruId,
        frameNumber: currentFrame,
        timestamp: currentTimestampMs / 1000,
        vruType: VRUType.PEDESTRIAN,
        boundingBox: {
          x: newObject.bbox.x,
          y: newObject.bbox.y,
          width: newObject.bbox.width,
          height: newObject.bbox.height,
          label: 'pedestrian',
          confidence: 1.0,
        },
        occluded: false,
        truncated: false,
        difficult: false,
        validationStatus: 'pending',
        validated: false,
      });
      
      newObject.id = annotation.id;
      setGroundTruthObjects(prev => [...prev, newObject]);
      setSelectedVruId(newVruId);
      setSuccessMessage('New object created');
      
    } catch (error) {
      setError(`Failed to create object: ${getErrorMessage(error)}`);
    }
  }, [video.id, currentFrame, currentTimestampMs]);
  
  const handleObjectSelect = useCallback((obj: GroundTruthObject) => {
    setSelectedVruId(selectedVruId === obj.vruId ? null : obj.vruId);
    
    // Update selection state
    setGroundTruthObjects(prev => prev.map(o => ({
      ...o,
      selected: o.vruId === obj.vruId ? !o.selected : false
    })));
    
    drawBoundingBoxes();
  }, [selectedVruId]);
  
  const handleVRUTypeChange = useCallback(async (objectId: string, newType: VRUType) => {
    try {
      await apiService.updateAnnotation(objectId, { vruType: newType });
      
      setGroundTruthObjects(prev => prev.map(obj => 
        obj.id === objectId ? { ...obj, vruType: newType } : obj
      ));
      
      setSuccessMessage(`VRU type changed to ${newType}`);
    } catch (error) {
      setError(`Failed to update VRU type: ${getErrorMessage(error)}`);
    }
  }, []);
  
  const handleObjectValidate = useCallback(async (objectId: string, validated: boolean) => {
    try {
      await apiService.validateAnnotation(objectId, validated);
      
      setGroundTruthObjects(prev => prev.map(obj => 
        obj.id === objectId ? { ...obj, validated } : obj
      ));
      
      setSuccessMessage(`Object ${validated ? 'validated' : 'marked as pending'}`);
    } catch (error) {
      setError(`Failed to validate object: ${getErrorMessage(error)}`);
    }
  }, []);
  
  const handleObjectDelete = useCallback(async (objectId: string) => {
    try {
      await apiService.deleteAnnotation(objectId);
      
      setGroundTruthObjects(prev => prev.filter(obj => obj.id !== objectId));
      
      if (groundTruthObjects.find(obj => obj.id === objectId)?.vruId === selectedVruId) {
        setSelectedVruId(null);
      }
      
      setSuccessMessage('Object deleted');
    } catch (error) {
      setError(`Failed to delete object: ${getErrorMessage(error)}`);
    }
  }, [selectedVruId, groundTruthObjects]);
  
  const handleMergeSelection = useCallback((vruId: string, selected: boolean) => {
    setMergeSelection(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(vruId);
      } else {
        newSet.delete(vruId);
      }
      return newSet;
    });
  }, []);
  
  const handleMergeVRUs = useCallback(async () => {
    if (mergeSelection.size < 2) return;
    
    try {
      const selectedObjects = groundTruthObjects.filter(obj => mergeSelection.has(obj.vruId));
      const primaryObject = selectedObjects[0];
      const secondaryObjects = selectedObjects.slice(1);
      
      // Merge logic: keep primary object, delete others, update VRU ID references
      for (const obj of secondaryObjects) {
        await apiService.deleteAnnotation(obj.id);
      }
      
      setGroundTruthObjects(prev => prev.filter(obj => !mergeSelection.has(obj.vruId) || obj.vruId === primaryObject.vruId));
      setMergeSelection(new Set());
      setMergeMode(false);
      setSuccessMessage(`Merged ${mergeSelection.size} VRUs into ${primaryObject.vruId}`);
      
    } catch (error) {
      setError(`Failed to merge VRUs: ${getErrorMessage(error)}`);
    }
  }, [mergeSelection, groundTruthObjects]);
  
  const handleSplitVRU = useCallback(async () => {
    if (!selectedVruId) return;
    
    try {
      const objectToSplit = groundTruthObjects.find(obj => obj.vruId === selectedVruId);
      if (!objectToSplit) return;
      
      // Create new VRU with same properties but new ID
      const newVruId = `${selectedVruId}_split_${Date.now()}`;
      const newObject: GroundTruthObject = {
        ...objectToSplit,
        id: `split_${Date.now()}`,
        vruId: newVruId,
        bbox: {
          ...objectToSplit.bbox,
          x: objectToSplit.bbox.x + objectToSplit.bbox.width / 2,
          width: objectToSplit.bbox.width / 2,
        },
        validated: false,
      };
      
      // Create on backend
      const annotation = await apiService.createAnnotation(video.id, {
        videoId: video.id,
        detectionId: newVruId,
        frameNumber: newObject.frameNumber,
        timestamp: newObject.timestampMs / 1000,
        vruType: newObject.vruType,
        boundingBox: {
          x: newObject.bbox.x,
          y: newObject.bbox.y,
          width: newObject.bbox.width,
          height: newObject.bbox.height,
          label: newObject.vruType,
          confidence: newObject.confidence,
        },
        occluded: false,
        truncated: false,
        difficult: false,
        validationStatus: 'pending',
        validated: false,
      });
      
      newObject.id = annotation.id;
      
      // Update original object bbox
      updateObjectBoundingBox(selectedVruId, { width: objectToSplit.bbox.width / 2 });
      
      setGroundTruthObjects(prev => [...prev, newObject]);
      setSplitMode(false);
      setSuccessMessage(`Split VRU ${selectedVruId} into two objects`);
      
    } catch (error) {
      setError(`Failed to split VRU: ${getErrorMessage(error)}`);
    }
  }, [selectedVruId, groundTruthObjects, video.id, updateObjectBoundingBox]);
  
  const handleValidateAllVisible = useCallback(async () => {
    try {
      for (const obj of currentFrameObjects) {
        if (!obj.validated) {
          await apiService.validateAnnotation(obj.id, true);
        }
      }
      
      setGroundTruthObjects(prev => prev.map(obj => 
        currentFrameObjects.some(frameObj => frameObj.id === obj.id)
          ? { ...obj, validated: true }
          : obj
      ));
      
      setSuccessMessage(`Validated ${currentFrameObjects.filter(obj => !obj.validated).length} objects`);
    } catch (error) {
      setError(`Failed to validate objects: ${getErrorMessage(error)}`);
    }
  }, [currentFrameObjects]);
  
  const handleSaveProgress = useCallback(async () => {
    try {
      // Save all current changes to backend
      for (const obj of groundTruthObjects) {
        await apiService.updateAnnotation(obj.id, {
          vruType: obj.vruType,
          boundingBox: {
            x: obj.bbox.x,
            y: obj.bbox.y,
            width: obj.bbox.width,
            height: obj.bbox.height,
            label: obj.vruType,
            confidence: obj.confidence,
          },
          validated: obj.validated,
        });
      }
      
      setSuccessMessage('Progress saved successfully');
    } catch (error) {
      setError(`Failed to save progress: ${getErrorMessage(error)}`);
    }
  }, [groundTruthObjects]);
  
  const handleValidateAllObjects = useCallback(async () => {
    try {
      for (const obj of groundTruthObjects) {
        if (!obj.validated) {
          await apiService.validateAnnotation(obj.id, true);
        }
      }
      
      setGroundTruthObjects(prev => prev.map(obj => ({ ...obj, validated: true })));
      setSuccessMessage(`Validated all ${groundTruthObjects.filter(obj => !obj.validated).length} objects`);
    } catch (error) {
      setError(`Failed to validate all objects: ${getErrorMessage(error)}`);
    }
  }, [groundTruthObjects]);
  
  const handleExportValidated = useCallback(async () => {
    try {
      const validatedObjects = groundTruthObjects.filter(obj => obj.validated);
      if (validatedObjects.length === 0) {
        setError('No validated objects to export');
        return;
      }
      
      // Create export data in Label Studio format
      const exportData = {
        data: { video: video.filename },
        annotations: [{
          id: Date.now(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          result: validatedObjects.map((obj, index) => ({
            id: obj.id,
            type: 'rectanglelabels',
            value: {
              x: (obj.bbox.x / videoDimensions.width) * 100,
              y: (obj.bbox.y / videoDimensions.height) * 100,
              width: (obj.bbox.width / videoDimensions.width) * 100,
              height: (obj.bbox.height / videoDimensions.height) * 100,
              rectanglelabels: [obj.vruType]
            },
            from_name: 'label',
            to_name: 'video',
          })),
        }],
      };
      
      // Download as JSON
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `${video.filename}_validated_annotations.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      
      setSuccessMessage(`Exported ${validatedObjects.length} validated annotations`);
    } catch (error) {
      setError(`Failed to export annotations: ${getErrorMessage(error)}`);
    }
  }, [groundTruthObjects, video.filename, videoDimensions]);
  
  const handleFinalValidation = useCallback(async () => {
    try {
      // Mark video as validated
      await apiService.validateVideo(video.id, true);
      
      setIsValidated(true);
      setValidationDialog(false);
      onValidationComplete(true);
      setSuccessMessage('Video validation complete!');
      
    } catch (error) {
      setError(`Failed to complete validation: ${getErrorMessage(error)}`);
    }
  }, [video.id, onValidationComplete]);
  
  // Drawing functions
  const drawBoundingBoxes = useCallback(() => {
    if (!canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw bounding boxes for current frame objects
    currentFrameObjects.forEach(obj => {
      const { bbox, vruType, validated, selected } = obj;
      const color = getVRUColor(vruType);
      
      // Set stroke style
      ctx.strokeStyle = selected ? '#2196f3' : color;
      ctx.lineWidth = selected ? 3 : validated ? 2 : 1;
      ctx.setLineDash(validated ? [] : [5, 5]);
      
      // Draw bounding box
      ctx.strokeRect(bbox.x, bbox.y, bbox.width, bbox.height);
      
      // Draw fill for selected objects
      if (selected) {
        ctx.fillStyle = 'rgba(33, 150, 243, 0.1)';
        ctx.fillRect(bbox.x, bbox.y, bbox.width, bbox.height);
      }
      
      // Draw resize handles for selected object
      if (selected) {
        const handleSize = 6;
        ctx.fillStyle = '#2196f3';
        
        // Corner handles
        ctx.fillRect(bbox.x - handleSize/2, bbox.y - handleSize/2, handleSize, handleSize);
        ctx.fillRect(bbox.x + bbox.width - handleSize/2, bbox.y - handleSize/2, handleSize, handleSize);
        ctx.fillRect(bbox.x - handleSize/2, bbox.y + bbox.height - handleSize/2, handleSize, handleSize);
        ctx.fillRect(bbox.x + bbox.width - handleSize/2, bbox.y + bbox.height - handleSize/2, handleSize, handleSize);
      }
      
      // Draw label
      ctx.fillStyle = color;
      ctx.font = '12px Arial';
      const labelText = `${obj.vruId} (${vruType})`;
      const labelWidth = ctx.measureText(labelText).width;
      
      // Label background
      ctx.fillRect(bbox.x, bbox.y - 20, labelWidth + 4, 16);
      
      // Label text
      ctx.fillStyle = 'white';
      ctx.fillText(labelText, bbox.x + 2, bbox.y - 6);
      
      // Validation status indicator
      if (validated) {
        ctx.fillStyle = '#4caf50';
        ctx.fillRect(bbox.x + bbox.width - 15, bbox.y - 15, 12, 12);
        ctx.fillStyle = 'white';
        ctx.font = '10px Arial';
        ctx.fillText('✓', bbox.x + bbox.width - 12, bbox.y - 6);
      }
    });
  }, [currentFrameObjects]);
  
  // Redraw when objects change
  useEffect(() => {
    drawBoundingBoxes();
  }, [drawBoundingBoxes]);
  
  // VRU color mapping
  const getVRUColor = useCallback((vruType: VRUType): string => {
    const colors = {
      pedestrian: '#ff5722',
      cyclist: '#2196f3',
      motorcyclist: '#ff9800',
      wheelchair: '#9c27b0',
      scooter: '#4caf50',
    };
    return colors[vruType] || '#607d8b';
  }, []);
  
  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          handlePreviousFrame();
          break;
        case 'ArrowRight':
          e.preventDefault();
          handleNextFrame();
          break;
        case ' ':
          e.preventDefault();
          handlePlayPause();
          break;
        case 'f':
          e.preventDefault();
          handleToggleFullscreen();
          break;
        case 'Escape':
          if (isFullscreen) {
            handleToggleFullscreen();
          }
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNextFrame, handlePreviousFrame, handlePlayPause, handleToggleFullscreen, isFullscreen]);
  
  // Keep local and parent validation state in sync when workflow panel completes
  const handleWorkflowValidationComplete = useCallback((validated: boolean) => {
    setIsValidated(validated);
    onValidationComplete(validated);
  }, [onValidationComplete]);

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid #ddd' }}>
        <Typography variant="h5" gutterBottom>
          Annotation Validation Interface
        </Typography>
        <Typography variant="subtitle2" color="text.secondary">
          {video.filename} • PRD Module 1.3 Implementation
        </Typography>
      </Box>
      
      {/* Main content */}
      <Box sx={{ flexGrow: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Large central video viewport */}
        <Box sx={{ flexGrow: 1, p: 2 }}>
          {renderVideoViewport()}
          {renderTimeline()}
        </Box>
        
        {/* Right panel */}
        <Box sx={{ width: 350, borderLeft: '1px solid #ddd', overflow: 'auto' }}>
          <Box sx={{ p: 2, space: 2 }}>
            {renderObjectManagement()}
            <Box sx={{ mt: 2 }}>
              <ValidationWorkflowPanel
                video={video}
                groundTruthObjects={groundTruthObjects}
                isValidated={isValidated}
                onValidationComplete={handleWorkflowValidationComplete}
                onSaveProgress={handleSaveProgress}
                onValidateAllFrame={handleValidateAllVisible}
                onValidateAll={handleValidateAllObjects}
                onExportValidated={handleExportValidated}
              />
            </Box>
          </Box>
        </Box>
      </Box>
      
      {/* Validation completion dialog */}
      <Dialog open={validationDialog} onClose={() => setValidationDialog(false)}>
        <DialogTitle>Complete Video Validation</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Are you ready to mark this video as "Validated"?
          </Typography>
          <Typography variant="body2" color="text.secondary">
            This will lock the annotations and mark the video as ready for testing projects.
          </Typography>
          
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2">Validation Summary:</Typography>
            <Typography variant="body2">
              • Total Objects: {groundTruthObjects.length}
            </Typography>
            <Typography variant="body2">
              • Validated Objects: {groundTruthObjects.filter(obj => obj.validated).length}
            </Typography>
            <Typography variant="body2">
              • Completion: {Math.round((groundTruthObjects.filter(obj => obj.validated).length / Math.max(groundTruthObjects.length, 1)) * 100)}%
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setValidationDialog(false)}>Cancel</Button>
          <Button 
            variant="contained" 
            onClick={handleFinalValidation}
            startIcon={<Check />}
          >
            Mark as Validated
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Error/Success messages */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ m: 2 }}>
          {error}
        </Alert>
      )}
      
      {successMessage && (
        <Alert severity="success" onClose={() => setSuccessMessage(null)} sx={{ m: 2 }}>
          {successMessage}
        </Alert>
      )}
    </Box>
  );
};

export default AnnotationValidationInterface;
