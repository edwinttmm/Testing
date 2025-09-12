/**
 * Unified Annotation Manager Component
 * ===================================
 * 
 * Single source of truth for all annotation functionality.
 * Consolidates duplicate annotation components into one clean implementation.
 */

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  Alert,
  Snackbar,
  IconButton,
  Tooltip,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  CircularProgress
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  CheckCircle as ValidatedIcon,
  RadioButtonUnchecked as UnvalidatedIcon,
  Visibility as ViewIcon,
  Download as ExportIcon,
  Upload as ImportIcon,
  Search as SearchIcon
} from '@mui/icons-material';

// Types
interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence?: number;
  label?: string;
}

interface Annotation {
  id: string;
  videoId: string;
  detectionId?: string;
  frameNumber: number;
  timestamp: number;
  endTimestamp?: number;
  vruType: VRUType;
  boundingBox: BoundingBox;
  occluded: boolean;
  truncated: boolean;
  difficult: boolean;
  notes?: string;
  annotator?: string;
  validated: boolean;
  createdAt?: string;
  updatedAt?: string;
}

enum VRUType {
  PEDESTRIAN = 'pedestrian',
  CYCLIST = 'cyclist',
  MOTORCYCLIST = 'motorcyclist',
  WHEELCHAIR = 'wheelchair',
  SCOOTER = 'scooter',
  ANIMAL = 'animal',
  OTHER = 'other'
}

interface AnnotationManagerProps {
  videoId: string;
  currentFrame: number;
  currentTimestamp: number;
  videoDimensions: { width: number; height: number };
  onAnnotationSelect?: (annotation: Annotation) => void;
  onAnnotationCreate?: (annotation: Annotation) => void;
  onAnnotationUpdate?: (annotation: Annotation) => void;
  onAnnotationDelete?: (annotationId: string) => void;
  readonly?: boolean;
}

interface AnnotationFormData {
  vruType: VRUType;
  boundingBox: BoundingBox;
  occluded: boolean;
  truncated: boolean;
  difficult: boolean;
  notes: string;
  annotator: string;
}

const DEFAULT_FORM_DATA: AnnotationFormData = {
  vruType: VRUType.PEDESTRIAN,
  boundingBox: { x: 0, y: 0, width: 100, height: 100 },
  occluded: false,
  truncated: false,
  difficult: false,
  notes: '',
  annotator: ''
};

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const UnifiedAnnotationManager: React.FC<AnnotationManagerProps> = ({
  videoId,
  currentFrame,
  currentTimestamp,
  videoDimensions,
  onAnnotationSelect,
  onAnnotationCreate,
  onAnnotationUpdate,
  onAnnotationDelete,
  readonly = false
}) => {
  // State
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [selectedAnnotation, setSelectedAnnotation] = useState<Annotation | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState<AnnotationFormData>(DEFAULT_FORM_DATA);
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [validatedOnly, setValidatedOnly] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // API Functions
  const fetchAnnotations = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${API_BASE}/api/annotations/videos/${videoId}/annotations?validated_only=${validatedOnly}`
      );
      
      if (!response.ok) {
        throw new Error('Failed to fetch annotations');
      }
      
      const data = await response.json();
      if (data.success) {
        setAnnotations(data.annotations);
      } else {
        throw new Error('Failed to fetch annotations');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch annotations');
    } finally {
      setLoading(false);
    }
  }, [videoId, validatedOnly]);

  const createAnnotation = async (annotationData: AnnotationFormData) => {
    try {
      setLoading(true);
      
      const payload = {
        frameNumber: currentFrame,
        timestamp: currentTimestamp,
        vruType: annotationData.vruType,
        boundingBox: annotationData.boundingBox,
        occluded: annotationData.occluded,
        truncated: annotationData.truncated,
        difficult: annotationData.difficult,
        notes: annotationData.notes,
        annotator: annotationData.annotator,
        validated: false
      };

      const response = await fetch(
        `${API_BASE}/api/annotations/videos/${videoId}/annotations`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload)
        }
      );

      if (!response.ok) {
        throw new Error('Failed to create annotation');
      }

      const data = await response.json();
      if (data.success) {
        setAnnotations(prev => [...prev, data.annotation]);
        setSuccess('Annotation created successfully');
        onAnnotationCreate?.(data.annotation);
        return data.annotation;
      } else {
        throw new Error('Failed to create annotation');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create annotation');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const updateAnnotation = async (annotationId: string, updateData: Partial<AnnotationFormData>) => {
    try {
      setLoading(true);
      
      const response = await fetch(
        `${API_BASE}/api/annotations/annotations/${annotationId}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(updateData)
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update annotation');
      }

      const data = await response.json();
      if (data.success) {
        setAnnotations(prev =>
          prev.map(ann => ann.id === annotationId ? data.annotation : ann)
        );
        setSuccess('Annotation updated successfully');
        onAnnotationUpdate?.(data.annotation);
        return data.annotation;
      } else {
        throw new Error('Failed to update annotation');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update annotation');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const deleteAnnotation = async (annotationId: string) => {
    try {
      setLoading(true);
      
      const response = await fetch(
        `${API_BASE}/api/annotations/annotations/${annotationId}`,
        {
          method: 'DELETE'
        }
      );

      if (!response.ok) {
        throw new Error('Failed to delete annotation');
      }

      setAnnotations(prev => prev.filter(ann => ann.id !== annotationId));
      setSuccess('Annotation deleted successfully');
      onAnnotationDelete?.(annotationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete annotation');
    } finally {
      setLoading(false);
    }
  };

  const validateAnnotation = async (annotationId: string, validated: boolean) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/annotations/annotations/${annotationId}/validate`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ validated })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to validate annotation');
      }

      const data = await response.json();
      if (data.success) {
        setAnnotations(prev =>
          prev.map(ann => ann.id === annotationId ? data.annotation : ann)
        );
        setSuccess(`Annotation ${validated ? 'validated' : 'unvalidated'} successfully`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate annotation');
    }
  };

  // Event Handlers
  const handleCreateAnnotation = () => {
    setFormData(DEFAULT_FORM_DATA);
    setSelectedAnnotation(null);
    setIsEditing(false);
    setIsDialogOpen(true);
  };

  const handleEditAnnotation = (annotation: Annotation) => {
    setFormData({
      vruType: annotation.vruType,
      boundingBox: annotation.boundingBox,
      occluded: annotation.occluded,
      truncated: annotation.truncated,
      difficult: annotation.difficult,
      notes: annotation.notes || '',
      annotator: annotation.annotator || ''
    });
    setSelectedAnnotation(annotation);
    setIsEditing(true);
    setIsDialogOpen(true);
  };

  const handleSaveAnnotation = async () => {
    try {
      if (isEditing && selectedAnnotation) {
        await updateAnnotation(selectedAnnotation.id, formData);
      } else {
        await createAnnotation(formData);
      }
      setIsDialogOpen(false);
      setSelectedAnnotation(null);
    } catch (err) {
      // Error already handled in API functions
    }
  };

  const handleDeleteAnnotation = async (annotationId: string) => {
    if (window.confirm('Are you sure you want to delete this annotation?')) {
      await deleteAnnotation(annotationId);
    }
  };

  const handleAnnotationSelect = (annotation: Annotation) => {
    setSelectedAnnotation(annotation);
    onAnnotationSelect?.(annotation);
  };

  // Load annotations on mount and when dependencies change
  useEffect(() => {
    if (videoId) {
      fetchAnnotations();
    }
  }, [fetchAnnotations]);

  // Filter annotations based on search term
  const filteredAnnotations = useMemo(() => {
    if (!searchTerm) return annotations;
    
    return annotations.filter(annotation =>
      annotation.vruType.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (annotation.notes && annotation.notes.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (annotation.annotator && annotation.annotator.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  }, [annotations, searchTerm]);

  // Get current frame annotations
  const currentFrameAnnotations = useMemo(() => {
    return filteredAnnotations.filter(ann => ann.frameNumber === currentFrame);
  }, [filteredAnnotations, currentFrame]);

  return (
    <Box sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          Annotation Manager
        </Typography>
        
        {/* Controls */}
        <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          {!readonly && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleCreateAnnotation}
              size="small"
            >
              Add Annotation
            </Button>
          )}
          
          <FormControlLabel
            control={
              <Switch
                checked={validatedOnly}
                onChange={(e) => setValidatedOnly(e.target.checked)}
                size="small"
              />
            }
            label="Validated Only"
          />
          
          <TextField
            placeholder="Search annotations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            size="small"
            InputProps={{
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'action.active' }} />
            }}
            sx={{ minWidth: 200 }}
          />
        </Box>
      </Box>

      {/* Current Frame Info */}
      <Paper sx={{ p: 1, mb: 2, bgcolor: 'primary.light', color: 'primary.contrastText' }}>
        <Typography variant="body2">
          Frame: {currentFrame} | Time: {currentTimestamp.toFixed(2)}s | 
          Annotations: {currentFrameAnnotations.length}
        </Typography>
      </Paper>

      {/* Annotations List */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
            <CircularProgress />
          </Box>
        )}
        
        {!loading && filteredAnnotations.length === 0 && (
          <Alert severity="info">
            No annotations found for this video.
          </Alert>
        )}
        
        {!loading && filteredAnnotations.length > 0 && (
          <List dense>
            {filteredAnnotations.map((annotation, index) => (
              <React.Fragment key={annotation.id}>
                <ListItem
                  button
                  selected={selectedAnnotation?.id === annotation.id}
                  onClick={() => handleAnnotationSelect(annotation)}
                  sx={{
                    bgcolor: annotation.frameNumber === currentFrame ? 'action.selected' : 'inherit'
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                          label={annotation.vruType}
                          size="small"
                          color="primary"
                          variant={annotation.validated ? "filled" : "outlined"}
                        />
                        <Typography variant="body2">
                          Frame {annotation.frameNumber}
                        </Typography>
                        {annotation.validated && <ValidatedIcon color="success" fontSize="small" />}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="caption" display="block">
                          Time: {annotation.timestamp.toFixed(2)}s
                        </Typography>
                        {annotation.notes && (
                          <Typography variant="caption" color="text.secondary">
                            {annotation.notes.substring(0, 50)}
                            {annotation.notes.length > 50 ? '...' : ''}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                  
                  <ListItemSecondaryAction>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      {!readonly && (
                        <>
                          <Tooltip title={annotation.validated ? "Mark as unvalidated" : "Mark as validated"}>
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                validateAnnotation(annotation.id, !annotation.validated);
                              }}
                              color={annotation.validated ? "success" : "default"}
                            >
                              {annotation.validated ? <ValidatedIcon /> : <UnvalidatedIcon />}
                            </IconButton>
                          </Tooltip>
                          
                          <Tooltip title="Edit annotation">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditAnnotation(annotation);
                              }}
                            >
                              <EditIcon />
                            </IconButton>
                          </Tooltip>
                          
                          <Tooltip title="Delete annotation">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteAnnotation(annotation.id);
                              }}
                              color="error"
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </>
                      )}
                    </Box>
                  </ListItemSecondaryAction>
                </ListItem>
                
                {index < filteredAnnotations.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        )}
      </Box>

      {/* Annotation Form Dialog */}
      <Dialog
        open={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {isEditing ? 'Edit Annotation' : 'Create New Annotation'}
        </DialogTitle>
        
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            {/* VRU Type */}
            <FormControl fullWidth>
              <InputLabel>VRU Type</InputLabel>
              <Select
                value={formData.vruType}
                onChange={(e) => setFormData(prev => ({ ...prev, vruType: e.target.value as VRUType }))}
                label="VRU Type"
              >
                {Object.values(VRUType).map(type => (
                  <MenuItem key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Bounding Box */}
            <Typography variant="subtitle2">Bounding Box</Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              <TextField
                label="X"
                type="number"
                value={formData.boundingBox.x}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  boundingBox: { ...prev.boundingBox, x: Number(e.target.value) }
                }))}
              />
              <TextField
                label="Y"
                type="number"
                value={formData.boundingBox.y}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  boundingBox: { ...prev.boundingBox, y: Number(e.target.value) }
                }))}
              />
              <TextField
                label="Width"
                type="number"
                value={formData.boundingBox.width}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  boundingBox: { ...prev.boundingBox, width: Number(e.target.value) }
                }))}
              />
              <TextField
                label="Height"
                type="number"
                value={formData.boundingBox.height}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  boundingBox: { ...prev.boundingBox, height: Number(e.target.value) }
                }))}
              />
            </Box>

            {/* Flags */}
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.occluded}
                    onChange={(e) => setFormData(prev => ({ ...prev, occluded: e.target.checked }))}
                  />
                }
                label="Occluded"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.truncated}
                    onChange={(e) => setFormData(prev => ({ ...prev, truncated: e.target.checked }))}
                  />
                }
                label="Truncated"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.difficult}
                    onChange={(e) => setFormData(prev => ({ ...prev, difficult: e.target.checked }))}
                  />
                }
                label="Difficult"
              />
            </Box>

            {/* Notes */}
            <TextField
              label="Notes"
              multiline
              rows={3}
              value={formData.notes}
              onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
              placeholder="Add any notes about this annotation..."
            />

            {/* Annotator */}
            <TextField
              label="Annotator"
              value={formData.annotator}
              onChange={(e) => setFormData(prev => ({ ...prev, annotator: e.target.value }))}
              placeholder="Your name or ID"
            />
          </Box>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setIsDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveAnnotation}
            variant="contained"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} /> : <SaveIcon />}
          >
            {isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success/Error Snackbars */}
      <Snackbar
        open={!!success}
        autoHideDuration={4000}
        onClose={() => setSuccess(null)}
      >
        <Alert severity="success" onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      </Snackbar>

      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
      >
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default UnifiedAnnotationManager;