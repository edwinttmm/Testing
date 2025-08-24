import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Alert,
  Snackbar,
  Stack,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControlLabel,
  Switch,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Divider,
  ListItemText,
  List,
  ListItem,
} from '@mui/material';
import {
  Help,
  Settings,
  History as HistoryIcon,
  Fullscreen,
} from '@mui/icons-material';
import { VideoFile, GroundTruthAnnotation, VRUType } from '../../services/types';
import { AnnotationShape, Point } from './types';
import { AnnotationProvider, useAnnotation } from './AnnotationManager';
import EnhancedAnnotationCanvas from './EnhancedAnnotationCanvas';
import AnnotationToolbar from './AnnotationToolbar';
import KeyboardShortcuts from './KeyboardShortcuts';
import AnnotationHistory from './AnnotationHistory';
import ContextMenu from './ContextMenu';
import ZoomPanControls from './ZoomPanControls';

// Import existing components
// Note: VideoAnnotationPlayer import - create if needed
const VideoAnnotationPlayer = React.lazy(() => 
  import('../VideoAnnotationPlayer').catch(() => 
    Promise.resolve({ default: () => <div>Classic mode not available</div> })
  )
);

interface EnhancedVideoAnnotationPlayerProps {
  video: VideoFile;
  annotations: GroundTruthAnnotation[];
  /** 
   * @future Feature: Multi-user annotation collaboration
   * @roadmap Planned for v2.0 - Real-time annotation selection sharing
   * @see Issue #156: Collaborative annotation editing
   */
  onAnnotationSelect?: (annotation: GroundTruthAnnotation) => void;
  onTimeUpdate?: (currentTime: number, frameNumber: number) => void;
  onCanvasClick?: (x: number, y: number, frameNumber: number, timestamp: number) => void;
  /** 
   * @future Feature: Extended annotation modes (collaborative, review, validation)
   * @roadmap Planned for v1.5 - Multiple annotation workflows
   * @see Issue #158: Advanced annotation modes
   */
  annotationMode: boolean;
  /** 
   * @future Feature: Multi-selection and annotation groups
   * @roadmap Planned for v2.0 - Support multiple selected annotations
   * @see Issue #159: Multi-annotation selection
   */
  selectedAnnotation?: GroundTruthAnnotation | null;
  frameRate?: number;
  showDetectionControls?: boolean;
  detectionControlsComponent?: React.ReactNode;
  onAnnotationCreate?: (annotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'>) => void;
  /** 
   * @future Feature: Real-time multi-user annotation updates
   * @roadmap Planned for v2.0 - Live collaborative editing
   * @see Issue #157: Multi-user annotation synchronization
   */
  onAnnotationUpdate?: (id: string, updates: Partial<GroundTruthAnnotation>) => void;
  onAnnotationDelete?: (id: string) => void;
}

// Enhanced annotation interface component
interface EnhancedAnnotationInterfaceProps {
  video: VideoFile;
  videoElement: HTMLVideoElement | null;
  canvasSize: { width: number; height: number };
  onShapeCreate: (shape: AnnotationShape) => void;
  onShapeUpdate: (shape: AnnotationShape) => void;
  onShapeDelete: (shapeId: string) => void;
}

const EnhancedAnnotationInterface: React.FC<EnhancedAnnotationInterfaceProps> = ({
  video,
  videoElement,
  canvasSize,
  onShapeCreate,
  onShapeUpdate,
  onShapeDelete
}) => {
  const { state, actions } = useAnnotation();
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const [contextMenu, setContextMenu] = useState<{
    position: { top: number; left: number };
    targetShape?: AnnotationShape;
    clickPoint?: Point;
  } | null>(null);
  
  /** 
   * @future Feature: Context-aware help and interactive tutorials
   * @roadmap Planned for v1.6 - Adaptive help system
   */
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  /** 
   * @future Feature: Multi-monitor support and advanced fullscreen modes
   * @roadmap Planned for v1.8 - Extended fullscreen capabilities
   * @see Issue #160: Multi-monitor annotation support
   */
  const [isFullscreen, setIsFullscreen] = useState(false);
  /** 
   * @future Feature: User profiles and persistent settings
   * @roadmap Planned for v1.7 - User preference synchronization
   * @see Issue #161: User settings persistence
   */
 const [videoSettings, setVideoSettings] = useState({
    quality: '720p',
    playbackRate: 1.0,
    showAnnotations: true,
    showConfidence: true,
    autoPlay: false,
    enableTooltips: true
  });
  // Handle shape creation from canvas
  const handleCanvasClick = useCallback((point: Point, event: MouseEvent) => {
    // Only create shapes when using drawing tools
    if (['rectangle', 'polygon', 'brush', 'point'].includes(state.activeToolId)) {
      // Canvas will handle this through its drawing tools
      return;
    }
    
    // For selection tool, handle context menu
    if (event.button === 2) { // Right click
      setContextMenu({
        position: { top: event.clientY, left: event.clientX },
        clickPoint: point,
      });
    }
  }, [state.activeToolId, setContextMenu]);

  // Handle shape click
  const handleShapeClick = useCallback((shape: AnnotationShape, event: MouseEvent) => {
    if (event.button === 2) { // Right click
      setContextMenu({
        position: { top: event.clientY, left: event.clientX },
        targetShape: shape,
      });
    } else {
      // Regular click - select shape
      actions.selectShapes([shape.id], event.shiftKey);
    }
  }, [actions, setContextMenu]);

  // Handle shape changes
  const handleShapeChange = useCallback((shapes: AnnotationShape[]) => {
    // Sync with parent component
    shapes.forEach(shape => {
      onShapeUpdate(shape);
    });
  }, [onShapeUpdate]);

  // Close context menu
  const handleContextMenuClose = useCallback(() => {
    setContextMenu(null);
  }, []);

  // Handle frame navigation
  const handleFrameNavigate = useCallback((direction: 'prev' | 'next') => {
    if (!videoElement) return;
    
    const frameTime = 1 / 30; // Assuming 30 FPS
    const currentTime = videoElement.currentTime;
    const newTime = direction === 'next' 
      ? Math.min(currentTime + frameTime, videoElement.duration)
      : Math.max(currentTime - frameTime, 0);
    
    videoElement.currentTime = newTime;
  }, [videoElement]);

  // Handle play/pause
  const handlePlayPause = useCallback(() => {
    if (!videoElement) return;
    
    if (videoElement.paused) {
      videoElement.play().catch(error => {
        console.error('Error playing video:', error);
        // Handle autoplay restrictions or other errors
      });
    } else {
      videoElement.pause();
    }
  }, [videoElement]);

  // Handle fullscreen toggle
  const handleFullscreenToggle = useCallback(async () => {
    if (!canvasContainerRef.current) return;

    try {
      if (!document.fullscreenElement) {
        await canvasContainerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (error) {
      console.error('Fullscreen toggle error:', error);
    }
  }, [setIsFullscreen]);

  // Handle settings change
  const handleSettingsChange = useCallback((key: string, value: any) => {
    setVideoSettings(prev => ({ ...prev, [key]: value }));
    
    // Apply settings immediately if video is available
    if (videoElement && key === 'playbackRate') {
      videoElement.playbackRate = value;
    }
  }, [videoElement, setVideoSettings]);

  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Main annotation area */}
      <Box sx={{ flex: 1, display: 'flex', gap: 2 }}>
        {/* Canvas area */}
        <Box sx={{ flex: 1, position: 'relative' }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ height: '100%', p: 1 }}>
              <Box
                ref={canvasContainerRef}
                sx={{ 
                  width: '100%', 
                  height: '100%', 
                  position: 'relative',
                  overflow: 'hidden',
                  borderRadius: 1,
                  bgcolor: 'black',
                }}
              >
                {videoElement && (
                  <EnhancedAnnotationCanvas
                    width={canvasSize.width}
                    height={canvasSize.height}
                    videoElement={videoElement}
                    onShapeClick={handleShapeClick}
                    onCanvasClick={handleCanvasClick}
                    onShapeChange={handleShapeChange}
                  />
                )}
                
                {/* Overlay controls */}
                <Box
                  sx={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    display: 'flex',
                    gap: 1,
                    zIndex: 10,
                  }}
                >
                  <Tooltip title="Keyboard Shortcuts (F1)">
                    <IconButton
                      size="small"
                      onClick={() => setShowKeyboardHelp(true)}
                      sx={{ 
                        bgcolor: 'rgba(0,0,0,0.7)', 
                        color: 'white',
                        '&:hover': { bgcolor: 'rgba(0,0,0,0.9)' }
                      }}
                    >
                      <Help />
                    </IconButton>
                  </Tooltip>
                  
                  <Tooltip title="History">
                    <IconButton
                      size="small"
                      onClick={() => setShowHistory(!showHistory)}
                      color={showHistory ? 'primary' : 'default'}
                      sx={{ 
                        bgcolor: showHistory ? 'primary.main' : 'rgba(0,0,0,0.7)', 
                        color: showHistory ? 'white' : 'white',
                        '&:hover': { bgcolor: showHistory ? 'primary.dark' : 'rgba(0,0,0,0.9)' }
                      }}
                    >
                      <HistoryIcon />
                    </IconButton>
                  </Tooltip>
                  
                  <Tooltip title="Settings">
                    <IconButton
                      size="small"
                      onClick={() => setShowSettings(true)}
                      sx={{ 
                        bgcolor: 'rgba(0,0,0,0.7)', 
                        color: 'white',
                        '&:hover': { bgcolor: 'rgba(0,0,0,0.9)' }
                      }}
                    >
                      <Settings />
                    </IconButton>
                  </Tooltip>
                  
                  <Tooltip title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}>
                    <IconButton
                      size="small"
                      onClick={() => handleFullscreenToggle()}
                      sx={{ 
                        bgcolor: 'rgba(0,0,0,0.7)', 
                        color: 'white',
                        '&:hover': { bgcolor: 'rgba(0,0,0,0.9)' }
                      }}
                    >
                      <Fullscreen />
                    </IconButton>
                  </Tooltip>
                </Box>

                {/* Status overlay */}
                <Box
                  sx={{
                    position: 'absolute',
                    bottom: 8,
                    left: 8,
                    right: 8,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    zIndex: 10,
                  }}
                >
                  <Stack direction="row" spacing={1}>
                    <Chip
                      label={`Tool: ${state.activeToolId}`}
                      size="small"
                      variant="filled"
                      sx={{ bgcolor: 'rgba(0,0,0,0.7)', color: 'white' }}
                    />
                    {state.shapes.length > 0 && (
                      <Chip
                        label={`Shapes: ${state.shapes.length}`}
                        size="small"
                        variant="outlined"
                        sx={{ borderColor: 'white', color: 'white' }}
                      />
                    )}
                    {state.selectedShapeIds.length > 0 && (
                      <Chip
                        label={`Selected: ${state.selectedShapeIds.length}`}
                        size="small"
                        color="primary"
                      />
                    )}
                  </Stack>
                  
                  <ZoomPanControls
                    containerRef={canvasContainerRef as React.RefObject<HTMLElement>}
                    contentSize={canvasSize}
                    compact
                  />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Right sidebar */}
        <Box sx={{ width: 320, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Annotation toolbar */}
          <AnnotationToolbar />
          
          {/* History panel (if shown) */}
          {showHistory && (
            <Box sx={{ height: 400 }}>
              <AnnotationHistory showHistoryPanel={true} />
            </Box>
          )}
          
          {/* Zoom/Pan controls */}
          <ZoomPanControls
            containerRef={canvasContainerRef as React.RefObject<HTMLElement>}
            contentSize={canvasSize}
          />
        </Box>
      </Box>

      {/* Context menu */}
      <ContextMenu
        anchorPosition={contextMenu?.position || null}
        onClose={handleContextMenuClose}
        targetShape={contextMenu?.targetShape ?? null}
        clickPoint={contextMenu?.clickPoint || null}
      />

      {/* Settings Dialog */}
      <Dialog
        open={showSettings}
        onClose={() => setShowSettings(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Video Player Settings</DialogTitle>
 <DialogContent>
          <Grid container spacing={3}>
            {/* Video Quality */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth>
                <InputLabel>Video Quality</InputLabel>
                <Select
                  value={videoSettings.quality}
                  onChange={(e) => handleSettingsChange('quality', e.target.value)}
                  label="Video Quality"
                >
                  <MenuItem value="480p">480p</MenuItem>
                  <MenuItem value="720p">720p</MenuItem>
                  <MenuItem value="1080p">1080p</MenuItem>
                  <MenuItem value="auto">Auto</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            {/* Playback Speed */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControl fullWidth>
                <InputLabel>Playback Speed</InputLabel>
                <Select
                  value={videoSettings.playbackRate}
                  onChange={(e) => handleSettingsChange('playbackRate', e.target.value)}
                  label="Playback Speed"
                >
                  <MenuItem value={0.25}>0.25x</MenuItem>
                  <MenuItem value={0.5}>0.5x</MenuItem>
                  <MenuItem value={0.75}>0.75x</MenuItem>
                  <MenuItem value={1.0}>1x</MenuItem>
                  <MenuItem value={1.25}>1.25x</MenuItem>
                  <MenuItem value={1.5}>1.5x</MenuItem>
                  <MenuItem value={2.0}>2x</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid size={{ xs: 12 }}>
              <Divider />
            </Grid>
            
            {/* Annotation Settings */}
            <Grid size={{ xs: 12 }}>
              <Typography variant="h6" gutterBottom>
                Annotation Display
              </Typography>
            </Grid>
            
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={videoSettings.showAnnotations}
                    onChange={(e) => handleSettingsChange('showAnnotations', e.target.checked)}
                  />
                }
                label="Show Annotations"
              />
            </Grid>
            
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={videoSettings.showConfidence}
                    onChange={(e) => handleSettingsChange('showConfidence', e.target.checked)}
                  />
                }
                label="Show Confidence Scores"
              />
            </Grid>
            
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={videoSettings.enableTooltips}
                    onChange={(e) => handleSettingsChange('enableTooltips', e.target.checked)}
                  />
                }
                label="Enable Tooltips"
              />
            </Grid>
            
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={videoSettings.autoPlay}
                    onChange={(e) => handleSettingsChange('autoPlay', e.target.checked)}
                  />
                }
                label="Auto-play Videos"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowSettings(false)}>Cancel</Button>
          <Button onClick={() => setShowSettings(false)} variant="contained">
            Apply Settings
          </Button>
        </DialogActions>
      </Dialog>

      {/* Keyboard shortcuts */}
      <KeyboardShortcuts
        onFrameNavigate={handleFrameNavigate}
        onPlayPause={handlePlayPause}
        showHelpDialog={showKeyboardHelp}
        onHelpDialogClose={() => setShowKeyboardHelp(false)}
      />
    </Box>
  );
};

// Main component with backward compatibility
const EnhancedVideoAnnotationPlayer = (props: EnhancedVideoAnnotationPlayerProps) => {
  const {
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
    onAnnotationCreate,
    onAnnotationUpdate,
    onAnnotationDelete,
  } = props;

  const videoRef = useRef<HTMLVideoElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });
  const [enhancedMode, setEnhancedMode] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Missing state variables
  const [videoSettings, setVideoSettings] = useState({
    quality: '720p',
    playbackRate: 1.0,
    showAnnotations: true,
    showConfidence: true,
    autoPlay: false,
    enableTooltips: true,
  });

  // VRU color mapping - moved before usage to fix dependency order
  const getVRUColor = useCallback((vruType: VRUType): string => {
    const colors = {
      pedestrian: '#2196f3',
      cyclist: '#4caf50',
      motorcyclist: '#ff9800',
      wheelchair_user: '#9c27b0',
      scooter_rider: '#ff5722',
    };
    return colors[vruType as keyof typeof colors] || '#607d8b';
  }, []);

  // Missing state variables for video errors
  const [videoError, setVideoError] = useState<{ type: string; message: string } | null>(null);
  const [videoLoadError, setVideoLoadError] = useState<boolean>(false);

  // Video event handlers
  const handleVideoRetry = useCallback(() => {
    if (videoRef.current) {
      setVideoError(null);
      setVideoLoadError(false);
      videoRef.current.load();
    }
  }, []);

  const handleVideoPlay = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.play().catch(error => {
        console.error('Play failed:', error);
        setVideoError({ type: 'playback', message: 'Failed to start video playback' });
      });
    }
  }, []);

  const handleVideoPause = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
    }
  }, []);

  const handleVideoError = useCallback((e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    const error = video.error;
    
    if (error) {
      let errorMessage = 'Unknown video error';
      switch (error.code) {
        case MediaError.MEDIA_ERR_ABORTED:
          errorMessage = 'Video playback was aborted';
          break;
        case MediaError.MEDIA_ERR_NETWORK:
          errorMessage = 'Network error occurred while loading video';
          break;
        case MediaError.MEDIA_ERR_DECODE:
          errorMessage = 'Video decoding error';
          break;
        case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
          errorMessage = 'Video format not supported';
          break;
        default:
          errorMessage = error.message || 'Unknown video error';
      }
      
      setVideoError({ type: 'load', message: errorMessage });
      setVideoLoadError(true);
    }
  }, []);

  const handleVideoLoadStart = useCallback(() => {
    setVideoError(null);
    setVideoLoadError(false);
  }, []);

  const handleVideoCanPlay = useCallback(() => {
    setVideoError(null);
    setVideoLoadError(false);
  }, []);

  // Convert existing annotations to shapes
  const convertAnnotationsToShapes = useCallback((annotations: GroundTruthAnnotation[]): AnnotationShape[] => {
    return annotations.map(annotation => ({
      id: annotation.id,
      type: 'rectangle' as const,
      points: [
        { x: annotation.boundingBox.x, y: annotation.boundingBox.y },
        { x: annotation.boundingBox.x + annotation.boundingBox.width, y: annotation.boundingBox.y },
        { x: annotation.boundingBox.x + annotation.boundingBox.width, y: annotation.boundingBox.y + annotation.boundingBox.height },
        { x: annotation.boundingBox.x, y: annotation.boundingBox.y + annotation.boundingBox.height },
      ],
      boundingBox: annotation.boundingBox,
      style: {
        strokeColor: getVRUColor(annotation.vruType),
        fillColor: `${getVRUColor(annotation.vruType)}20`,
        strokeWidth: selectedAnnotation?.id === annotation.id ? 3 : 2,
        fillOpacity: 0.2,
      },
      label: annotation.vruType,
      confidence: annotation.boundingBox.confidence,
      visible: true,
      selected: selectedAnnotation?.id === annotation.id,
    }));
  }, [selectedAnnotation, getVRUColor]);

  // Handle shape creation
  const handleShapeCreate = useCallback((shape: AnnotationShape) => {
    if (!onAnnotationCreate) return;

    // Convert shape to ground truth annotation
    const annotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'> = {
      videoId: video.id,
      detectionId: `det_${Date.now()}`,
      frameNumber: Math.floor((videoRef.current?.currentTime || 0) * frameRate),
      timestamp: videoRef.current?.currentTime || 0,
      vruType: (shape.label || 'pedestrian') as VRUType,
      boundingBox: {
        ...shape.boundingBox,
        label: shape.label || 'pedestrian',
        confidence: shape.confidence || 1.0,
      },
      occluded: false,
      truncated: false,
      difficult: false,
      validated: false,
    };

    onAnnotationCreate(annotation);
  }, [onAnnotationCreate, video.id, frameRate]);

  // Handle shape updates
  const handleShapeUpdate = useCallback((shape: AnnotationShape) => {
    if (!onAnnotationUpdate) return;

    const updates: Partial<GroundTruthAnnotation> = {
      boundingBox: {
        ...shape.boundingBox,
        label: shape.label || 'pedestrian',
        confidence: shape.confidence || 1.0,
      },
      vruType: (shape.label || 'pedestrian') as VRUType,
    };

    onAnnotationUpdate(shape.id, updates);
  }, [onAnnotationUpdate]);

  // Handle shape deletion
  const handleShapeDelete = useCallback((shapeId: string) => {
    if (!onAnnotationDelete) return;
    onAnnotationDelete(shapeId);
  }, [onAnnotationDelete]);

  // Update canvas size when video loads and apply settings
  useEffect(() => {
    const updateCanvasSize = () => {
      if (videoRef.current) {
        const video = videoRef.current;
        setCanvasSize({
          width: video.videoWidth || 800,
          height: video.videoHeight || 600,
        });
        
        // Apply video settings
        video.playbackRate = videoSettings.playbackRate;
        if (videoSettings.autoPlay) {
          video.autoplay = true;
        }
      }
    };

    const video = videoRef.current;
    if (video) {
      video.addEventListener('loadedmetadata', updateCanvasSize);
      return () => video.removeEventListener('loadedmetadata', updateCanvasSize);
    }
    return undefined;
  }, [videoSettings]);

  // Apply settings when they change
  useEffect(() => {
    if (videoRef.current) {
      const video = videoRef.current;
      video.playbackRate = videoSettings.playbackRate;
    }
  }, [videoSettings.playbackRate]);

  // Convert annotations to shapes
  const initialShapes = useMemo(() => {
    return convertAnnotationsToShapes(annotations);
  }, [annotations, convertAnnotationsToShapes]);

  // Enhanced mode toggle
  const toggleEnhancedMode = useCallback(() => {
    setEnhancedMode(!enhancedMode);
  }, [enhancedMode]);

  // Error handling
  const handleError = useCallback((error: string) => {
    setError(error);
    setTimeout(() => setError(null), 5000);
  }, []);

  return (
    <Box sx={{ height: '100%' }}>
      {/* Mode toggle */}
      <Box sx={{ mb: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          Video Annotation {enhancedMode ? '(Enhanced)' : '(Classic)'}
        </Typography>
        <Button
          variant="outlined"
          size="small"
          onClick={toggleEnhancedMode}
        >
          {enhancedMode ? 'Classic Mode' : 'Enhanced Mode'}
        </Button>
      </Box>

      {enhancedMode ? (
        // Enhanced annotation interface
        <AnnotationProvider
          initialShapes={initialShapes}
          onChange={(shapes: AnnotationShape[]) => shapes.forEach(handleShapeUpdate)}
        >
          <EnhancedAnnotationInterface
            video={video}
            videoElement={videoRef.current}
            canvasSize={canvasSize}
            onShapeCreate={handleShapeCreate}
            onShapeUpdate={handleShapeUpdate}
            onShapeDelete={handleShapeDelete}
          />
          
          {/* Hidden video element for playback control */}
          <video
            ref={videoRef}
            src={video.url}
            style={{ display: 'none' }}
            onTimeUpdate={(e) => {
              const video = e.currentTarget;
              onTimeUpdate?.(video.currentTime, Math.floor(video.currentTime * frameRate));
            }}
            onError={handleVideoError}
            onLoadStart={handleVideoLoadStart}
            onCanPlay={handleVideoCanPlay}
            onPlay={handleVideoPlay}
            onPause={handleVideoPause}
          />
        </AnnotationProvider>
      ) : (
        // Classic interface (backward compatibility)
        <React.Suspense fallback={<div>Loading...</div>}>
          <VideoAnnotationPlayer
          video={video}
          annotations={annotations}
          onAnnotationSelect={onAnnotationSelect ?? (() => {})}
          onTimeUpdate={onTimeUpdate ?? (() => {})}
          onCanvasClick={onCanvasClick ?? (() => {})}
          annotationMode={annotationMode}
          selectedAnnotation={selectedAnnotation || null}
          frameRate={frameRate}
          showDetectionControls={showDetectionControls}
          detectionControlsComponent={detectionControlsComponent}
          />
        </React.Suspense>
      )}

      {/* Enhanced Error Display */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          severity="error" 
          onClose={() => setError(null)}
          action={
            <Button color="inherit" size="small" onClick={() => setError(null)}>
              DISMISS
            </Button>
          }
        >
          {error}
        </Alert>
      </Snackbar>
      
      {/* Video-specific error display */}
      <Snackbar
        open={!!videoError && !videoLoadError}
        autoHideDuration={8000}
        onClose={() => setVideoError(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert 
          severity="warning" 
          onClose={() => setVideoError(null)}
          action={
            <Stack direction="row" spacing={1}>
              <Button color="inherit" size="small" onClick={handleVideoRetry}>
                RETRY
              </Button>
              <Button color="inherit" size="small" onClick={() => setVideoError(null)}>
                DISMISS
              </Button>
            </Stack>
          }
        >
          <strong>{videoError?.type.toUpperCase()}:</strong> {videoError?.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default EnhancedVideoAnnotationPlayer;