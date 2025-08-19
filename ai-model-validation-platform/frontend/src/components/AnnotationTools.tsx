import React, { useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  ButtonGroup,
  Chip,
  Stack,
  Tooltip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Switch,
  FormControlLabel,
  Divider,
  Alert,
} from '@mui/material';
import {
  CropFree,
  RadioButtonUnchecked,
  Timeline,
  Edit,
  Save,
  Delete,
  Visibility,
  VisibilityOff,
  Check,
  Clear,
  Add,
  Remove,
} from '@mui/icons-material';
import { VRUType, GroundTruthAnnotation, BoundingBox } from '../services/types';

interface AnnotationToolsProps {
  selectedAnnotation?: GroundTruthAnnotation | null;
  onAnnotationUpdate?: (annotation: Partial<GroundTruthAnnotation>) => void;
  onAnnotationDelete?: (annotationId: string) => void;
  onAnnotationValidate?: (annotationId: string, validated: boolean) => void;
  onToolSelect?: (tool: AnnotationTool) => void;
  selectedTool?: AnnotationTool;
  onCreateAnnotation?: (vruType: VRUType, boundingBox?: Partial<BoundingBox>) => void;
  annotationMode: boolean;
  onAnnotationModeToggle?: (enabled: boolean) => void;
  showAnnotations: boolean;
  onShowAnnotationsToggle?: (show: boolean) => void;
  frameNumber: number;
  timestamp: number;
}

export interface AnnotationTool {
  id: string;
  name: string;
  type: 'rectangle' | 'polygon' | 'circle' | 'point';
  icon: React.ReactNode;
  cursor: string;
}

const ANNOTATION_TOOLS: AnnotationTool[] = [
  {
    id: 'rectangle',
    name: 'Rectangle',
    type: 'rectangle',
    icon: <CropFree />,
    cursor: 'crosshair',
  },
  {
    id: 'circle',
    name: 'Circle',
    type: 'circle',
    icon: <RadioButtonUnchecked />,
    cursor: 'crosshair',
  },
  {
    id: 'point',
    name: 'Point',
    type: 'point',
    icon: <Timeline />,
    cursor: 'pointer',
  },
];

const VRU_TYPES: Array<{ value: VRUType; label: string; color: string }> = [
  { value: 'pedestrian', label: 'Pedestrian', color: '#2196f3' },
  { value: 'cyclist', label: 'Cyclist', color: '#4caf50' },
  { value: 'motorcyclist', label: 'Motorcyclist', color: '#ff9800' },
  { value: 'wheelchair_user', label: 'Wheelchair User', color: '#9c27b0' },
  { value: 'scooter_rider', label: 'Scooter Rider', color: '#ff5722' },
];

const AnnotationTools: React.FC<AnnotationToolsProps> = ({
  selectedAnnotation,
  onAnnotationUpdate,
  onAnnotationDelete,
  onAnnotationValidate,
  onToolSelect,
  selectedTool,
  onCreateAnnotation,
  annotationMode,
  onAnnotationModeToggle,
  showAnnotations,
  onShowAnnotationsToggle,
  frameNumber,
  timestamp,
}) => {
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState(selectedAnnotation?.notes || '');
  const [selectedVRUType, setSelectedVRUType] = useState<VRUType>('pedestrian');

  // Update notes when selected annotation changes
  React.useEffect(() => {
    if (selectedAnnotation) {
      setNotes(selectedAnnotation.notes || '');
    }
  }, [selectedAnnotation]);

  const handleToolSelect = useCallback((tool: AnnotationTool) => {
    onToolSelect?.(tool);
  }, [onToolSelect]);

  const handleSaveNotes = () => {
    if (selectedAnnotation && onAnnotationUpdate) {
      onAnnotationUpdate({ id: selectedAnnotation.id, notes });
    }
    setEditingNotes(false);
  };

  const handleCancelNotes = () => {
    setNotes(selectedAnnotation?.notes || '');
    setEditingNotes(false);
  };

  const handleVRUTypeChange = (vruType: VRUType) => {
    if (selectedAnnotation && onAnnotationUpdate) {
      onAnnotationUpdate({ id: selectedAnnotation.id, vruType });
    }
  };

  const handleValidationToggle = () => {
    if (selectedAnnotation && onAnnotationValidate) {
      onAnnotationValidate(selectedAnnotation.id, !selectedAnnotation.validated);
    }
  };

  const handleCreateQuickAnnotation = () => {
    if (onCreateAnnotation) {
      onCreateAnnotation(selectedVRUType);
    }
  };

  return (
    <Paper sx={{ p: 2, minHeight: 400 }}>
      <Typography variant="h6" gutterBottom>
        Annotation Tools
      </Typography>

      {/* Annotation Mode Toggle */}
      <Box sx={{ mb: 2 }}>
        <FormControlLabel
          control={
            <Switch
              checked={annotationMode}
              onChange={(e) => onAnnotationModeToggle?.(e.target.checked)}
            />
          }
          label="Annotation Mode"
        />
        <FormControlLabel
          control={
            <Switch
              checked={showAnnotations}
              onChange={(e) => onShowAnnotationsToggle?.(e.target.checked)}
            />
          }
          label="Show Annotations"
          sx={{ ml: 2 }}
        />
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Current Frame Info */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Current Frame: {frameNumber}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Timestamp: {timestamp.toFixed(2)}s
        </Typography>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Drawing Tools */}
      {annotationMode && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Drawing Tools
          </Typography>
          <ButtonGroup variant="outlined" size="small" sx={{ mb: 2 }}>
            {ANNOTATION_TOOLS.map((tool) => (
              <Tooltip key={tool.id} title={tool.name}>
                <IconButton
                  onClick={() => handleToolSelect(tool)}
                  color={selectedTool?.id === tool.id ? 'primary' : 'default'}
                  sx={{
                    bgcolor: selectedTool?.id === tool.id ? 'primary.light' : 'transparent',
                  }}
                >
                  {tool.icon}
                </IconButton>
              </Tooltip>
            ))}
          </ButtonGroup>

          {/* VRU Type Selection for New Annotations */}
          <FormControl size="small" sx={{ minWidth: 150, mb: 2, display: 'block' }}>
            <InputLabel>VRU Type</InputLabel>
            <Select
              value={selectedVRUType}
              label="VRU Type"
              onChange={(e) => setSelectedVRUType(e.target.value as VRUType)}
            >
              {VRU_TYPES.map((type) => (
                <MenuItem key={type.value} value={type.value}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        bgcolor: type.color,
                        borderRadius: '50%',
                      }}
                    />
                    <span>{type.label}</span>
                  </Stack>
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Button
            variant="outlined"
            size="small"
            startIcon={<Add />}
            onClick={handleCreateQuickAnnotation}
            sx={{ display: 'block', mb: 2 }}
          >
            Quick Annotate
          </Button>

          <Divider sx={{ mb: 2 }} />
        </Box>
      )}

      {/* Selected Annotation Editor */}
      {selectedAnnotation ? (
        <Box>
          <Typography variant="subtitle1" gutterBottom>
            Selected Annotation
          </Typography>
          
          <Stack spacing={2}>
            {/* Detection ID */}
            <TextField
              label="Detection ID"
              value={selectedAnnotation.detectionId}
              size="small"
              InputProps={{ readOnly: true }}
            />

            {/* VRU Type */}
            <FormControl size="small">
              <InputLabel>VRU Type</InputLabel>
              <Select
                value={selectedAnnotation.vruType}
                label="VRU Type"
                onChange={(e) => handleVRUTypeChange(e.target.value as VRUType)}
              >
                {VRU_TYPES.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          bgcolor: type.color,
                          borderRadius: '50%',
                        }}
                      />
                      <span>{type.label}</span>
                    </Stack>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Bounding Box Info */}
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Bounding Box
              </Typography>
              <Stack direction="row" spacing={1}>
                <TextField
                  label="X"
                  value={Math.round(selectedAnnotation.boundingBox.x)}
                  size="small"
                  InputProps={{ readOnly: true }}
                  sx={{ width: 80 }}
                />
                <TextField
                  label="Y"
                  value={Math.round(selectedAnnotation.boundingBox.y)}
                  size="small"
                  InputProps={{ readOnly: true }}
                  sx={{ width: 80 }}
                />
                <TextField
                  label="W"
                  value={Math.round(selectedAnnotation.boundingBox.width)}
                  size="small"
                  InputProps={{ readOnly: true }}
                  sx={{ width: 80 }}
                />
                <TextField
                  label="H"
                  value={Math.round(selectedAnnotation.boundingBox.height)}
                  size="small"
                  InputProps={{ readOnly: true }}
                  sx={{ width: 80 }}
                />
              </Stack>
            </Box>

            {/* Annotation Properties */}
            <Stack direction="row" spacing={2}>
              <FormControlLabel
                control={
                  <Switch
                    checked={selectedAnnotation.occluded}
                    onChange={(e) =>
                      onAnnotationUpdate?.({
                        id: selectedAnnotation.id,
                        occluded: e.target.checked,
                      })
                    }
                  />
                }
                label="Occluded"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={selectedAnnotation.truncated}
                    onChange={(e) =>
                      onAnnotationUpdate?.({
                        id: selectedAnnotation.id,
                        truncated: e.target.checked,
                      })
                    }
                  />
                }
                label="Truncated"
              />
            </Stack>

            <FormControlLabel
              control={
                <Switch
                  checked={selectedAnnotation.difficult}
                  onChange={(e) =>
                    onAnnotationUpdate?.({
                      id: selectedAnnotation.id,
                      difficult: e.target.checked,
                    })
                  }
                />
              }
              label="Difficult"
            />

            {/* Notes */}
            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="subtitle2">Notes</Typography>
                <IconButton
                  size="small"
                  onClick={() => setEditingNotes(!editingNotes)}
                >
                  <Edit />
                </IconButton>
              </Stack>
              {editingNotes ? (
                <Stack spacing={1}>
                  <TextField
                    multiline
                    rows={3}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    size="small"
                    placeholder="Add notes about this detection..."
                  />
                  <Stack direction="row" spacing={1}>
                    <Button size="small" startIcon={<Save />} onClick={handleSaveNotes}>
                      Save
                    </Button>
                    <Button size="small" startIcon={<Clear />} onClick={handleCancelNotes}>
                      Cancel
                    </Button>
                  </Stack>
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ minHeight: 40 }}>
                  {selectedAnnotation.notes || 'No notes added'}
                </Typography>
              )}
            </Box>

            {/* Validation */}
            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle2">Validation</Typography>
                <Chip
                  label={selectedAnnotation.validated ? 'Validated' : 'Pending'}
                  color={selectedAnnotation.validated ? 'success' : 'warning'}
                  size="small"
                  icon={selectedAnnotation.validated ? <Check /> : <Clear />}
                />
              </Stack>
              <Button
                variant={selectedAnnotation.validated ? 'outlined' : 'contained'}
                color={selectedAnnotation.validated ? 'warning' : 'success'}
                size="small"
                startIcon={selectedAnnotation.validated ? <Clear /> : <Check />}
                onClick={handleValidationToggle}
                sx={{ mt: 1 }}
              >
                {selectedAnnotation.validated ? 'Mark as Pending' : 'Validate'}
              </Button>
            </Box>

            {/* Actions */}
            <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
              <Button
                variant="outlined"
                color="error"
                size="small"
                startIcon={<Delete />}
                onClick={() => onAnnotationDelete?.(selectedAnnotation.id)}
              >
                Delete
              </Button>
            </Stack>
          </Stack>
        </Box>
      ) : (
        <Alert severity="info">
          {annotationMode
            ? 'Click on the video to create a new annotation or select an existing one.'
            : 'Enable annotation mode to start creating annotations.'}
        </Alert>
      )}

      {/* Instructions */}
      <Box sx={{ mt: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
        <Typography variant="subtitle2" gutterBottom>
          Instructions
        </Typography>
        <Typography variant="caption" component="div" sx={{ mb: 1 }}>
          • Enable annotation mode to create and edit annotations
        </Typography>
        <Typography variant="caption" component="div" sx={{ mb: 1 }}>
          • Select a drawing tool and VRU type, then click on the video
        </Typography>
        <Typography variant="caption" component="div" sx={{ mb: 1 }}>
          • Click on existing annotations to select and edit them
        </Typography>
        <Typography variant="caption" component="div">
          • Use frame navigation to annotate across different time points
        </Typography>
      </Box>
    </Paper>
  );
};

export default AnnotationTools;