import React, { useState, useCallback } from 'react';
import {
  Box,
  Paper,
  IconButton,
  ButtonGroup,
  Divider,
  Tooltip,
  Slider,
  Typography,
  Menu,
  MenuItem,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  Chip,
} from '@mui/material';
import {
  CropFree as RectangleIcon,
  Timeline as PolygonIcon,
  Brush as BrushIcon,
  Place as PointIcon,
  NearMe as SelectIcon,
  Undo,
  Redo,
  ContentCopy,
  ContentPaste,
  Delete,
  ZoomIn,
  ZoomOut,
  ZoomOutMap,
  Grid3x3,
  Palette,
  Settings as SettingsIcon,
  ExpandMore,
  Visibility,
  VisibilityOff,
  Lock,
  LockOpen,
} from '@mui/icons-material';
import { useAnnotation } from './AnnotationManager';
import { DrawingTool, AnnotationStyle, BrushSettings } from './types';

const DRAWING_TOOLS: DrawingTool[] = [
  { id: 'select', name: 'Select', type: 'select', icon: <SelectIcon />, cursor: 'default', hotkey: 'V' },
  { id: 'rectangle', name: 'Rectangle', type: 'rectangle', icon: <RectangleIcon />, cursor: 'crosshair', hotkey: 'R' },
  { id: 'polygon', name: 'Polygon', type: 'polygon', icon: <PolygonIcon />, cursor: 'crosshair', hotkey: 'P' },
  { id: 'brush', name: 'Brush', type: 'brush', icon: <BrushIcon />, cursor: 'crosshair', hotkey: 'B' },
  { id: 'point', name: 'Point', type: 'point', icon: <PointIcon />, cursor: 'pointer', hotkey: 'T' },
];

const PRESET_COLORS = [
  '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#95a5a6',
];

interface AnnotationToolbarProps {
  onToolChange?: (toolId: string) => void;
  onZoomChange?: (scale: number) => void;
  disabled?: boolean;
  compact?: boolean;
}

const AnnotationToolbar: React.FC<AnnotationToolbarProps> = ({
  onToolChange,
  onZoomChange,
  disabled = false,
  compact = false,
}) => {
  const { state, actions } = useAnnotation();
  const [colorMenuAnchor, setColorMenuAnchor] = useState<HTMLElement | null>(null);
  const [settingsExpanded, setSettingsExpanded] = useState(false);

  const selectedShapes = actions.getSelectedShapes();
  const hasSelection = selectedShapes.length > 0;
  const hasClipboard = state.clipboard.length > 0;

  // Tool selection handler
  const handleToolSelect = useCallback((toolId: string) => {
    actions.setActiveTool(toolId);
    onToolChange?.(toolId);
  }, [actions, onToolChange]);

  // Undo/Redo handlers
  const handleUndo = useCallback(() => {
    actions.undo();
  }, [actions]);

  const handleRedo = useCallback(() => {
    actions.redo();
  }, [actions]);

  // Copy/Paste handlers
  const handleCopy = useCallback(() => {
    if (hasSelection) {
      actions.copyShapes(selectedShapes);
    }
  }, [actions, hasSelection, selectedShapes]);

  const handlePaste = useCallback(() => {
    if (hasClipboard) {
      actions.pasteShapes();
    }
  }, [actions, hasClipboard]);

  // Delete handler
  const handleDelete = useCallback(() => {
    if (hasSelection) {
      actions.deleteShapes(selectedShapes.map(s => s.id));
    }
  }, [actions, hasSelection, selectedShapes]);

  // Zoom handlers
  const handleZoomIn = useCallback(() => {
    const newScale = Math.min(state.canvasTransform.scale * 1.2, 5);
    actions.setTransform({ scale: newScale });
    onZoomChange?.(newScale);
  }, [actions, state.canvasTransform.scale, onZoomChange]);

  const handleZoomOut = useCallback(() => {
    const newScale = Math.max(state.canvasTransform.scale / 1.2, 0.1);
    actions.setTransform({ scale: newScale });
    onZoomChange?.(newScale);
  }, [actions, state.canvasTransform.scale, onZoomChange]);

  const handleZoomFit = useCallback(() => {
    actions.setTransform({ scale: 1, translateX: 0, translateY: 0 });
    onZoomChange?.(1);
  }, [actions, onZoomChange]);

  // Style update handler
  const handleStyleUpdate = useCallback((updates: Partial<AnnotationStyle>) => {
    if (hasSelection) {
      selectedShapes.forEach(shape => {
        actions.updateShape(shape.id, {
          style: { ...shape.style, ...updates }
        });
      });
    }
    
    // Update default style for new shapes
    actions.updateSettings({
      defaultStyle: { ...state.settings.defaultStyle, ...updates }
    });
  }, [actions, hasSelection, selectedShapes, state.settings.defaultStyle]);

  // Settings handlers
  const handleGridToggle = useCallback(() => {
    actions.updateSettings({ showGrid: !state.settings.showGrid });
  }, [actions, state.settings.showGrid]);

  const handleSnapToggle = useCallback(() => {
    actions.updateSettings({ snapToGrid: !state.settings.snapToGrid });
  }, [actions, state.settings.snapToGrid]);

  const handleGridSizeChange = useCallback((size: number) => {
    actions.updateSettings({ gridSize: size });
  }, [actions]);

  // Brush settings handler
  const handleBrushSettingsUpdate = useCallback((updates: Partial<BrushSettings>) => {
    actions.updateSettings({
      brushSettings: { ...state.settings.brushSettings, ...updates }
    });
  }, [actions, state.settings.brushSettings]);

  // Visibility toggle
  const handleVisibilityToggle = useCallback((shapeId: string) => {
    const shape = actions.getShapeById(shapeId);
    if (shape) {
      actions.updateShape(shapeId, { visible: !shape.visible });
    }
  }, [actions]);

  // Lock toggle
  const handleLockToggle = useCallback((shapeId: string) => {
    const shape = actions.getShapeById(shapeId);
    if (shape) {
      actions.updateShape(shapeId, { locked: !shape.locked });
    }
  }, [actions]);

  if (compact) {
    return (
      <Paper elevation={2} sx={{ p: 1, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        {/* Essential tools only */}
        <ButtonGroup size="small" disabled={disabled}>
          {DRAWING_TOOLS.slice(0, 3).map((tool) => (
            <Tooltip key={tool.id} title={`${tool.name} (${tool.hotkey})`}>
              <IconButton
                onClick={() => handleToolSelect(tool.id)}
                color={state.activeToolId === tool.id ? 'primary' : 'default'}
              >
                {tool.icon}
              </IconButton>
            </Tooltip>
          ))}
        </ButtonGroup>
        
        <Divider orientation="vertical" flexItem />
        
        <ButtonGroup size="small" disabled={disabled}>
          <Tooltip title="Undo (Ctrl+Z)">
            <IconButton onClick={handleUndo}><Undo /></IconButton>
          </Tooltip>
          <Tooltip title="Redo (Ctrl+Y)">
            <IconButton onClick={handleRedo}><Redo /></IconButton>
          </Tooltip>
        </ButtonGroup>
        
        <Typography variant="body2" sx={{ ml: 'auto' }}>
          Scale: {Math.round(state.canvasTransform.scale * 100)}%
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper elevation={2} sx={{ p: 2, minWidth: 300 }}>
      <Typography variant="h6" gutterBottom>
        Annotation Tools
      </Typography>

      {/* Drawing Tools */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Drawing Tools
        </Typography>
        <ButtonGroup orientation="vertical" fullWidth disabled={disabled}>
          {DRAWING_TOOLS.map((tool) => (
            <Tooltip key={tool.id} title={`${tool.name} (${tool.hotkey})`} placement="right">
              <IconButton
                onClick={() => handleToolSelect(tool.id)}
                color={state.activeToolId === tool.id ? 'primary' : 'default'}
                sx={{
                  justifyContent: 'flex-start',
                  px: 2,
                  py: 1,
                  bgcolor: state.activeToolId === tool.id ? 'primary.light' : 'transparent',
                }}
              >
                {tool.icon}
                <Typography variant="body2" sx={{ ml: 1 }}>
                  {tool.name}
                </Typography>
                <Chip
                  label={tool.hotkey}
                  size="small"
                  variant="outlined"
                  sx={{ ml: 'auto', minWidth: 24, height: 20 }}
                />
              </IconButton>
            </Tooltip>
          ))}
        </ButtonGroup>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Edit Tools */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Edit
        </Typography>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Tooltip title="Undo (Ctrl+Z)">
            <IconButton onClick={handleUndo} disabled={disabled}>
              <Undo />
            </IconButton>
          </Tooltip>
          <Tooltip title="Redo (Ctrl+Y)">
            <IconButton onClick={handleRedo} disabled={disabled}>
              <Redo />
            </IconButton>
          </Tooltip>
          <Tooltip title="Copy (Ctrl+C)">
            <IconButton onClick={handleCopy} disabled={disabled || !hasSelection}>
              <ContentCopy />
            </IconButton>
          </Tooltip>
          <Tooltip title="Paste (Ctrl+V)">
            <IconButton onClick={handlePaste} disabled={disabled || !hasClipboard}>
              <ContentPaste />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete (Del)">
            <IconButton onClick={handleDelete} disabled={disabled || !hasSelection}>
              <Delete />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Zoom Controls */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Zoom & Navigation
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
          <Tooltip title="Zoom Out">
            <IconButton onClick={handleZoomOut} disabled={disabled}>
              <ZoomOut />
            </IconButton>
          </Tooltip>
          <Typography variant="body2" sx={{ minWidth: 60, textAlign: 'center' }}>
            {Math.round(state.canvasTransform.scale * 100)}%
          </Typography>
          <Tooltip title="Zoom In">
            <IconButton onClick={handleZoomIn} disabled={disabled}>
              <ZoomIn />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom to Fit">
            <IconButton onClick={handleZoomFit} disabled={disabled}>
              <ZoomOutMap />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Style Controls */}
      {hasSelection && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Style ({selectedShapes.length} selected)
          </Typography>
          
          {/* Color Palette */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" display="block" gutterBottom>
              Stroke Color
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
              {PRESET_COLORS.map((color) => (
                <Box
                  key={color}
                  sx={{
                    width: 24,
                    height: 24,
                    bgcolor: color,
                    border: selectedShapes[0]?.style.strokeColor === color ? '2px solid #000' : '1px solid #ccc',
                    borderRadius: 0.5,
                    cursor: 'pointer',
                    '&:hover': { transform: 'scale(1.1)' }
                  }}
                  onClick={() => handleStyleUpdate({ strokeColor: color })}
                />
              ))}
            </Box>
          </Box>

          {/* Stroke Width */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" gutterBottom>
              Stroke Width: {selectedShapes[0]?.style.strokeWidth || state.settings.defaultStyle.strokeWidth}px
            </Typography>
            <Slider
              value={selectedShapes[0]?.style.strokeWidth || state.settings.defaultStyle.strokeWidth}
              min={1}
              max={10}
              step={1}
              onChange={(_, value) => handleStyleUpdate({ strokeWidth: value as number })}
              disabled={disabled}
              size="small"
            />
          </Box>

          {/* Fill Opacity */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" gutterBottom>
              Fill Opacity: {Math.round((selectedShapes[0]?.style.fillOpacity || state.settings.defaultStyle.fillOpacity) * 100)}%
            </Typography>
            <Slider
              value={selectedShapes[0]?.style.fillOpacity || state.settings.defaultStyle.fillOpacity}
              min={0}
              max={1}
              step={0.1}
              onChange={(_, value) => handleStyleUpdate({ fillOpacity: value as number })}
              disabled={disabled}
              size="small"
            />
          </Box>
        </Box>
      )}

      {/* Shape List */}
      {state.shapes.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Shapes ({state.shapes.length})
          </Typography>
          <Box sx={{ maxHeight: 200, overflowY: 'auto' }}>
            {state.shapes.map((shape) => (
              <Box
                key={shape.id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  p: 1,
                  bgcolor: state.selectedShapeIds.includes(shape.id) ? 'primary.light' : 'transparent',
                  borderRadius: 1,
                  cursor: 'pointer',
                  '&:hover': { bgcolor: 'action.hover' }
                }}
                onClick={() => actions.selectShapes([shape.id])}
              >
                <Box sx={{ 
                  width: 16, 
                  height: 16, 
                  bgcolor: shape.style.strokeColor, 
                  borderRadius: shape.type === 'point' ? '50%' : 1,
                  mr: 1 
                }} />
                
                <Typography variant="body2" sx={{ flex: 1 }}>
                  {shape.type} {shape.label && `- ${shape.label}`}
                </Typography>
                
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleVisibilityToggle(shape.id);
                  }}
                >
                  {shape.visible !== false ? <Visibility /> : <VisibilityOff />}
                </IconButton>
                
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleLockToggle(shape.id);
                  }}
                >
                  {shape.locked ? <Lock /> : <LockOpen />}
                </IconButton>
              </Box>
            ))}
          </Box>
        </Box>
      )}

      <Divider sx={{ mb: 2 }} />

      {/* Settings */}
      <Accordion expanded={settingsExpanded} onChange={() => setSettingsExpanded(!settingsExpanded)}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <SettingsIcon sx={{ mr: 1 }} />
          <Typography variant="subtitle2">Settings</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={2}>
            {/* Grid Settings */}
            <FormControlLabel
              control={
                <Switch
                  checked={state.settings.showGrid}
                  onChange={handleGridToggle}
                  disabled={disabled}
                />
              }
              label="Show Grid"
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={state.settings.snapToGrid}
                  onChange={handleSnapToggle}
                  disabled={disabled}
                />
              }
              label="Snap to Grid"
            />

            <Box>
              <Typography variant="caption" gutterBottom>
                Grid Size: {state.settings.gridSize}px
              </Typography>
              <Slider
                value={state.settings.gridSize}
                min={5}
                max={50}
                step={5}
                onChange={(_, value) => handleGridSizeChange(value as number)}
                disabled={disabled}
                size="small"
              />
            </Box>

            {/* Brush Settings */}
            {state.activeToolId === 'brush' && (
              <>
                <Divider />
                <Typography variant="subtitle2">Brush Settings</Typography>
                
                <Box>
                  <Typography variant="caption" gutterBottom>
                    Size: {state.settings.brushSettings.size}px
                  </Typography>
                  <Slider
                    value={state.settings.brushSettings.size}
                    min={1}
                    max={50}
                    step={1}
                    onChange={(_, value) => handleBrushSettingsUpdate({ size: value as number })}
                    disabled={disabled}
                    size="small"
                  />
                </Box>
                
                <Box>
                  <Typography variant="caption" gutterBottom>
                    Opacity: {Math.round(state.settings.brushSettings.opacity * 100)}%
                  </Typography>
                  <Slider
                    value={state.settings.brushSettings.opacity}
                    min={0.1}
                    max={1}
                    step={0.1}
                    onChange={(_, value) => handleBrushSettingsUpdate({ opacity: value as number })}
                    disabled={disabled}
                    size="small"
                  />
                </Box>
                
                <FormControlLabel
                  control={
                    <Switch
                      checked={state.settings.brushSettings.isEraser}
                      onChange={(_, checked) => handleBrushSettingsUpdate({ isEraser: checked })}
                      disabled={disabled}
                    />
                  }
                  label="Eraser Mode"
                />
              </>
            )}
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Paper>
  );
};

export default AnnotationToolbar;