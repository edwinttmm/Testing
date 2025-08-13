import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Box,
} from '@mui/material';
import { Warning } from '@mui/icons-material';
import { Project } from '../services/types';

interface DeleteConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  project: Project | null;
  onConfirm: (projectId: string) => Promise<void>;
  loading?: boolean;
}

const DeleteConfirmationDialog: React.FC<DeleteConfirmationDialogProps> = ({
  open,
  onClose,
  project,
  onConfirm,
  loading = false,
}) => {
  const handleConfirm = async () => {
    if (!project) return;
    
    try {
      await onConfirm(project.id);
      onClose();
    } catch (error) {
      // Error handling is done in the parent component
      console.error('Error deleting project:', error);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  if (!project) return null;

  return (
    <Dialog 
      open={open} 
      onClose={handleClose} 
      maxWidth="sm" 
      fullWidth
      aria-labelledby="delete-dialog-title"
      aria-describedby="delete-dialog-description"
    >
      <DialogTitle id="delete-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Warning color="warning" />
          Confirm Delete Project
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Alert severity="warning" sx={{ mb: 2 }}>
          <Typography variant="body2">
            <strong>Warning:</strong> This action cannot be undone.
          </Typography>
        </Alert>
        
        <Typography variant="body1" id="delete-dialog-description" sx={{ mb: 2 }}>
          Are you sure you want to delete the project <strong>"{project.name}"</strong>?
        </Typography>
        
        <Typography variant="body2" color="text.secondary">
          This will permanently delete:
        </Typography>
        <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
          <li>The project and all its settings</li>
          <li>All uploaded videos and their data</li>
          <li>All test sessions and results</li>
          <li>All detection events and ground truth data</li>
        </ul>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button 
          onClick={handleConfirm}
          variant="contained"
          color="error"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={20} /> : null}
        >
          {loading ? 'Deleting...' : 'Delete Project'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default DeleteConfirmationDialog;