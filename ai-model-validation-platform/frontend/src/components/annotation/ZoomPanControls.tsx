import React, { useCallback, useRef, useEffect, useState } from 'react';
import {
  Box,
  Paper,
  IconButton,
  Tooltip,
  Slider,
  Typography,
  ButtonGroup,
  Stack,
  Chip,
} from '@mui/material';
import {
  ZoomIn,
  ZoomOut,
  ZoomOutMap,
  CenterFocusStrong,
  Fullscreen,
  FullscreenExit,
  PanTool,
} from '@mui/icons-material';
import { useAnnotation } from './AnnotationManager';
import { Point, Size } from './types';

interface ZoomPanControlsProps {
  containerRef?: React.RefObject<HTMLElement>;
  contentSize?: Size;
  onZoomChange?: (scale: number) => void;
  onPanChange?: (translate: Point) => void;
  onFullscreenToggle?: (isFullscreen: boolean) => void;
  disabled?: boolean;
  showMinimap?: boolean;
  compact?: boolean;
}

const ZoomPanControls: React.FC<ZoomPanControlsProps> = ({
  containerRef,
  contentSize = { width: 800, height: 600 },
  onZoomChange,
  onPanChange,
  onFullscreenToggle,
  disabled = false,
  showMinimap = false,
  compact = false,
}) => {
  const { state, actions } = useAnnotation();
  const [isPanning, setIsPanning] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [containerSize, setContainerSize] = useState<Size>({ width: 800, height: 600 });
  
  const panStartRef = useRef<Point | null>(null);
  const lastPanPointRef = useRef<Point | null>(null);

  // Zoom constraints
  const MIN_ZOOM = 0.1;
  const MAX_ZOOM = 10;
  const ZOOM_STEP = 1.2;

  // Get current transform
  const { scale, translateX, translateY } = state.canvasTransform;

  // Update container size when container changes
  useEffect(() => {
    if (!containerRef?.current) return;

    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setContainerSize({ width: rect.width, height: rect.height });
      }
    };

    updateSize();

    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [containerRef]);

  // Zoom functions
  const zoomIn = useCallback(() => {
    const newScale = Math.min(scale * ZOOM_STEP, MAX_ZOOM);
    actions.setTransform({ scale: newScale });
    onZoomChange?.(newScale);
  }, [scale, actions, onZoomChange]);

  const zoomOut = useCallback(() => {
    const newScale = Math.max(scale / ZOOM_STEP, MIN_ZOOM);
    actions.setTransform({ scale: newScale });
    onZoomChange?.(newScale);
  }, [scale, actions, onZoomChange]);

  const zoomToFit = useCallback(() => {
    const scaleX = containerSize.width / contentSize.width;
    const scaleY = containerSize.height / contentSize.height;
    const fitScale = Math.min(scaleX, scaleY, 1); // Don't zoom in beyond 100%
    
    const newTranslateX = (containerSize.width - contentSize.width * fitScale) / 2;
    const newTranslateY = (containerSize.height - contentSize.height * fitScale) / 2;

    actions.setTransform({
      scale: fitScale,
      translateX: newTranslateX,
      translateY: newTranslateY,
    });
    
    onZoomChange?.(fitScale);
    onPanChange?.({ x: newTranslateX, y: newTranslateY });
  }, [containerSize, contentSize, actions, onZoomChange, onPanChange]);

  const zoomToActualSize = useCallback(() => {
    actions.setTransform({ scale: 1 });
    onZoomChange?.(1);
  }, [actions, onZoomChange]);

  const centerContent = useCallback(() => {
    const newTranslateX = (containerSize.width - contentSize.width * scale) / 2;
    const newTranslateY = (containerSize.height - contentSize.height * scale) / 2;

    actions.setTransform({
      translateX: newTranslateX,
      translateY: newTranslateY,
    });
    
    onPanChange?.({ x: newTranslateX, y: newTranslateY });
  }, [containerSize, contentSize, scale, actions, onPanChange]);

  // Handle zoom slider change
  const handleZoomSliderChange = useCallback((_event: Event, value: number | number[]) => {
    const newScale = Array.isArray(value) ? value[0] : value;
    actions.setTransform({ scale: newScale });
    onZoomChange?.(newScale);
  }, [actions, onZoomChange]);

  // Handle wheel zoom
  const handleWheel = useCallback((event: WheelEvent) => {
    if (!containerRef?.current?.contains(event.target as Node)) return;
    if (!event.ctrlKey && !event.metaKey) return; // Only zoom with Ctrl/Cmd held

    event.preventDefault();

    const rect = containerRef.current.getBoundingClientRect();
    const clientX = event.clientX - rect.left;
    const clientY = event.clientY - rect.top;

    // Calculate zoom
    const zoomFactor = event.deltaY > 0 ? 1 / ZOOM_STEP : ZOOM_STEP;
    const newScale = Math.min(Math.max(scale * zoomFactor, MIN_ZOOM), MAX_ZOOM);

    // Calculate new translation to zoom towards cursor
    const scaleDiff = newScale - scale;
    const newTranslateX = translateX - (clientX - translateX) * (scaleDiff / scale);
    const newTranslateY = translateY - (clientY - translateY) * (scaleDiff / scale);

    actions.setTransform({
      scale: newScale,
      translateX: newTranslateX,
      translateY: newTranslateY,
    });

    onZoomChange?.(newScale);
    onPanChange?.({ x: newTranslateX, y: newTranslateY });
  }, [containerRef, scale, translateX, translateY, actions, onZoomChange, onPanChange]);

  // Handle mouse pan
  const handleMouseDown = useCallback((event: MouseEvent) => {
    if (!isPanning) return;
    if (event.button !== 1 && !event.altKey) return; // Middle mouse or Alt+drag

    event.preventDefault();
    panStartRef.current = { x: event.clientX, y: event.clientY };
    lastPanPointRef.current = { x: translateX, y: translateY };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!panStartRef.current || !lastPanPointRef.current) return;

      const deltaX = moveEvent.clientX - panStartRef.current.x;
      const deltaY = moveEvent.clientY - panStartRef.current.y;

      const newTranslateX = lastPanPointRef.current.x + deltaX;
      const newTranslateY = lastPanPointRef.current.y + deltaY;

      actions.setTransform({
        translateX: newTranslateX,
        translateY: newTranslateY,
      });

      onPanChange?.({ x: newTranslateX, y: newTranslateY });
    };

    const handleMouseUp = () => {
      panStartRef.current = null;
      lastPanPointRef.current = null;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [isPanning, translateX, translateY, actions, onPanChange]);

  // Set up event listeners
  useEffect(() => {
    const container = containerRef?.current;
    if (!container) return;

    container.addEventListener('wheel', handleWheel, { passive: false });
    container.addEventListener('mousedown', handleMouseDown);

    return () => {
      container.removeEventListener('wheel', handleWheel);
      container.removeEventListener('mousedown', handleMouseDown);
    };
  }, [containerRef, handleWheel, handleMouseDown]);

  // Fullscreen handling
  const toggleFullscreen = useCallback(() => {
    if (!containerRef?.current) return;

    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
    
    onFullscreenToggle?.(!isFullscreen);
  }, [containerRef, isFullscreen, onFullscreenToggle]);

  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isNowFullscreen = !!document.fullscreenElement;
      setIsFullscreen(isNowFullscreen);
      onFullscreenToggle?.(isNowFullscreen);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [onFullscreenToggle]);

  // Calculate zoom percentage
  const zoomPercentage = Math.round(scale * 100);

  // Compact view
  if (compact) {
    return (
      <Paper elevation={1} sx={{ p: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        <ButtonGroup size="small" disabled={disabled}>
          <Tooltip title="Zoom Out">
            <IconButton onClick={zoomOut} disabled={scale <= MIN_ZOOM}>
              <ZoomOut />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom In">
            <IconButton onClick={zoomIn} disabled={scale >= MAX_ZOOM}>
              <ZoomIn />
            </IconButton>
          </Tooltip>
        </ButtonGroup>
        
        <Chip 
          label={`${zoomPercentage}%`} 
          size="small" 
          variant="outlined"
          onClick={zoomToActualSize}
          sx={{ cursor: 'pointer', minWidth: 60 }}
        />
        
        <Tooltip title="Fit to Screen">
          <IconButton onClick={zoomToFit} size="small" disabled={disabled}>
            <ZoomOutMap />
          </IconButton>
        </Tooltip>
      </Paper>
    );
  }

  // Full controls
  return (
    <Paper elevation={2} sx={{ p: 2, minWidth: 250 }}>
      <Typography variant="h6" gutterBottom>
        Zoom & Pan
      </Typography>

      {/* Zoom Controls */}
      <Box sx={{ mb: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
          <Tooltip title="Zoom Out">
            <IconButton 
              onClick={zoomOut} 
              disabled={disabled || scale <= MIN_ZOOM}
              size="small"
            >
              <ZoomOut />
            </IconButton>
          </Tooltip>
          
          <Box sx={{ flex: 1, mx: 2 }}>
            <Slider
              value={scale}
              min={MIN_ZOOM}
              max={MAX_ZOOM}
              step={0.1}
              onChange={handleZoomSliderChange}
              disabled={disabled}
              size="small"
              sx={{ mx: 1 }}
            />
          </Box>
          
          <Tooltip title="Zoom In">
            <IconButton 
              onClick={zoomIn} 
              disabled={disabled || scale >= MAX_ZOOM}
              size="small"
            >
              <ZoomIn />
            </IconButton>
          </Tooltip>
        </Stack>

        <Stack direction="row" justifyContent="center" sx={{ mb: 2 }}>
          <Chip
            label={`${zoomPercentage}%`}
            onClick={zoomToActualSize}
            color={zoomPercentage === 100 ? 'primary' : 'default'}
            sx={{ cursor: 'pointer', minWidth: 80 }}
          />
        </Stack>

        <Stack direction="row" spacing={1} justifyContent="center">
          <Tooltip title="Zoom to Fit">
            <IconButton onClick={zoomToFit} disabled={disabled} size="small">
              <ZoomOutMap />
            </IconButton>
          </Tooltip>
          <Tooltip title="Center Content">
            <IconButton onClick={centerContent} disabled={disabled} size="small">
              <CenterFocusStrong />
            </IconButton>
          </Tooltip>
          <Tooltip title="100% Size">
            <IconButton onClick={zoomToActualSize} disabled={disabled} size="small">
              1:1
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Pan Controls */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Pan Tool
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Tooltip title={isPanning ? "Disable Pan Tool" : "Enable Pan Tool (Alt+Drag or Middle Mouse)"}>
            <IconButton
              onClick={() => setIsPanning(!isPanning)}
              color={isPanning ? 'primary' : 'default'}
              size="small"
              disabled={disabled}
            >
              <PanTool />
            </IconButton>
          </Tooltip>
          <Typography variant="body2" color={isPanning ? 'primary' : 'text.secondary'}>
            {isPanning ? 'Enabled' : 'Disabled'}
          </Typography>
        </Stack>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          Hold Alt+Drag or use middle mouse to pan
        </Typography>
      </Box>

      {/* Position Info */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Position
        </Typography>
        <Stack spacing={1}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="body2">X:</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              {Math.round(translateX)}px
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="body2">Y:</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              {Math.round(translateY)}px
            </Typography>
          </Box>
        </Stack>
      </Box>

      {/* Fullscreen */}
      <Box>
        <Tooltip title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}>
          <IconButton
            onClick={toggleFullscreen}
            disabled={disabled}
            sx={{ width: '100%' }}
          >
            {isFullscreen ? <FullscreenExit /> : <Fullscreen />}
            <Typography variant="body2" sx={{ ml: 1 }}>
              {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            </Typography>
          </IconButton>
        </Tooltip>
      </Box>

      {/* Minimap */}
      {showMinimap && (
        <Box sx={{ mt: 3, p: 1, border: 1, borderColor: 'divider', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Overview
          </Typography>
          <Box
            sx={{
              width: '100%',
              height: 120,
              bgcolor: 'grey.100',
              border: 1,
              borderColor: 'divider',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Content representation */}
            <Box
              sx={{
                position: 'absolute',
                bgcolor: 'primary.light',
                opacity: 0.3,
                width: `${Math.min(100, (containerSize.width / contentSize.width) * 100)}%`,
                height: `${Math.min(100, (containerSize.height / contentSize.height) * 100)}%`,
                left: `${Math.max(0, -translateX / contentSize.width * 100)}%`,
                top: `${Math.max(0, -translateY / contentSize.height * 100)}%`,
              }}
            />
            
            {/* Viewport indicator */}
            <Box
              sx={{
                position: 'absolute',
                border: 2,
                borderColor: 'primary.main',
                width: `${Math.min(100, (containerSize.width / (contentSize.width * scale)) * 100)}%`,
                height: `${Math.min(100, (containerSize.height / (contentSize.height * scale)) * 100)}%`,
                left: `${Math.max(0, -translateX / (contentSize.width * scale) * 100)}%`,
                top: `${Math.max(0, -translateY / (contentSize.height * scale) * 100)}%`,
              }}
            />
          </Box>
        </Box>
      )}

      {/* Help Text */}
      <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
        <Typography variant="caption" component="div">
          • Ctrl/Cmd + Wheel: Zoom
        </Typography>
        <Typography variant="caption" component="div">
          • Alt + Drag: Pan
        </Typography>
        <Typography variant="caption" component="div">
          • Middle Mouse: Pan
        </Typography>
      </Box>
    </Paper>
  );
};

export default ZoomPanControls;