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
  onAnnotationSelect?: (annotation: GroundTruthAnnotation) => void;
  onTimeUpdate?: (currentTime: number, frameNumber: number) => void;
  onCanvasClick?: (x: number, y: number, frameNumber: number, timestamp: number) => void;
  annotationMode: boolean;
  selectedAnnotation?: GroundTruthAnnotation | null;
  frameRate?: number;
  showDetectionControls?: boolean;
  detectionControlsComponent?: React.ReactNode;
  onAnnotationCreate?: (annotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'>) => void;
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
  
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

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
  }, [state.activeToolId]);

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
  }, [actions]);

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
      videoElement.play();
    } else {
      videoElement.pause();
    }
  }, [videoElement]);

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

  // VRU color mapping
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

  // Update canvas size when video loads
  useEffect(() => {
    const updateCanvasSize = () => {
      if (videoRef.current) {
        const video = videoRef.current;
        setCanvasSize({
          width: video.videoWidth || 800,
          height: video.videoHeight || 600,
        });
      }
    };

    const video = videoRef.current;
    if (video) {
      video.addEventListener('loadedmetadata', updateCanvasSize);
      return () => video.removeEventListener('loadedmetadata', updateCanvasSize);
    }
    return undefined;
  }, []);

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

      {/* Error snackbar */}
      <Snackbar
        open={!!error}
        autoHideDuration={5000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default EnhancedVideoAnnotationPlayer;