import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
} from '@mui/material';
import { CameraType, SignalType, ProjectStatus } from '../services/types';
import { ProjectUpdate, Project } from '../services/types';
import { getErrorMessage } from '../utils/errorUtils';

interface EditProjectDialogProps {
  open: boolean;
  onClose: () => void;
  project: Project | null;
  onSave: (projectId: string, updates: ProjectUpdate) => Promise<void>;
  loading?: boolean;
}

const EditProjectDialog: React.FC<EditProjectDialogProps> = ({
  open,
  onClose,
  project,
  onSave,
  loading = false,
}) => {
  const [formData, setFormData] = useState<ProjectUpdate>({
    name: '',
    description: '',
    cameraModel: '',
    cameraView: CameraType.FRONT_FACING_VRU,
    signalType: SignalType.GPIO,
    status: ProjectStatus.DRAFT,
  });
  const [formErrors, setFormErrors] = useState<{[key: string]: string}>({});
  const [error, setError] = useState<string | null>(null);

  // Initialize form data when project changes
  useEffect(() => {
    if (project) {
      setFormData({
        name: project.name,
        description: project.description ?? '',
        cameraModel: project.cameraModel,
        cameraView: project.cameraView,
        signalType: project.signalType,
        status: project.status,
      });
      setFormErrors({});
      setError(null);
    }
  }, [project]);

  const validateForm = (): boolean => {
    const errors: {[key: string]: string} = {};
    
    if (!formData.name?.trim()) {
      errors.name = 'Project name is required';
    }
    if (!formData.description?.trim()) {
      errors.description = 'Description is required';
    }
    if (!formData.cameraModel?.trim()) {
      errors.cameraModel = 'Camera model is required';
    }
    
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleFormChange = (field: keyof ProjectUpdate, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (formErrors[field]) {
      setFormErrors(prev => ({ ...prev, [field]: '' }));
    }
    setError(null);
  };

  const handleSave = async () => {
    if (!project || !validateForm()) {
      return;
    }

    try {
      setError(null);
      await onSave(project.id, formData);
      onClose();
    } catch (error: any) {
      console.error('Error updating project:', error);
      setError(getErrorMessage(error, 'Failed to update project. Please try again.'));
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Edit Project</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        <TextField
          autoFocus
          margin="dense"
          label="Project Name"
          fullWidth
          variant="outlined"
          value={formData.name || ''}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFormChange('name', e.target.value)}
          error={!!formErrors.name}
          helperText={formErrors.name}
          disabled={loading}
          sx={{ mb: 2 }}
        />
        
        <TextField
          margin="dense"
          label="Description"
          fullWidth
          multiline
          rows={3}
          variant="outlined"
          value={formData.description || ''}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFormChange('description', e.target.value)}
          error={!!formErrors.description}
          helperText={formErrors.description}
          disabled={loading}
          sx={{ mb: 2 }}
        />
        
        <TextField
          margin="dense"
          label="Camera Model"
          fullWidth
          variant="outlined"
          value={formData.cameraModel || ''}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFormChange('cameraModel', e.target.value)}
          error={!!formErrors.cameraModel}
          helperText={formErrors.cameraModel}
          disabled={loading}
          placeholder="e.g., Sony IMX390, OmniVision OV2312"
          sx={{ mb: 2 }}
        />
        
        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel>Camera View</InputLabel>
          <Select 
            label="Camera View"
            value={formData.cameraView || 'Front-facing VRU'}
            onChange={(e: any) => handleFormChange('cameraView', e.target.value as any)}
            disabled={loading}
          >
            <MenuItem value="Front-facing VRU">Front-facing VRU</MenuItem>
            <MenuItem value="Rear-facing VRU">Rear-facing VRU</MenuItem>
            <MenuItem value="In-Cab Driver Behavior">In-Cab Driver Behavior</MenuItem>
          </Select>
        </FormControl>
        
        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel>Signal Type</InputLabel>
          <Select 
            label="Signal Type"
            value={formData.signalType || 'GPIO'}
            onChange={(e: any) => handleFormChange('signalType', e.target.value)}
            disabled={loading}
          >
            <MenuItem value="GPIO">GPIO</MenuItem>
            <MenuItem value="Network Packet">Network Packet</MenuItem>
            <MenuItem value="Serial">Serial</MenuItem>
          </Select>
        </FormControl>
        
        <FormControl fullWidth>
          <InputLabel>Status</InputLabel>
          <Select 
            label="Status"
            value={formData.status || 'Draft'}
            onChange={(e: any) => handleFormChange('status', e.target.value as any)}
            disabled={loading}
          >
            <MenuItem value="Draft">Draft</MenuItem>
            <MenuItem value="Active">Active</MenuItem>
            <MenuItem value="Completed">Completed</MenuItem>
          </Select>
        </FormControl>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button 
          onClick={handleSave} 
          variant="contained"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={20} /> : null}
        >
          {loading ? 'Saving...' : 'Save Changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditProjectDialog;