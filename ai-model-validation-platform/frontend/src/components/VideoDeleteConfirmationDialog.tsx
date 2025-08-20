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
import { VideoFile } from '../services/types';

interface VideoDeleteConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  video: VideoFile | null;
  onConfirm: (videoId: string) => Promise<void>;
  loading?: boolean;
}

const VideoDeleteConfirmationDialog: React.FC<VideoDeleteConfirmationDialogProps> = ({
  open,
  onClose,
  video,
  onConfirm,
  loading = false,
}) => {
  const handleConfirm = async () => {
    if (!video) return;
    
    try {
      await onConfirm(video.id);
      onClose();
    } catch (error) {
      // Error handling is done in the parent component
      console.error('Error deleting video:', error);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  if (!video) return null;

  return (
    <Dialog 
      open={open} 
      onClose={handleClose} 
      maxWidth="sm" 
      fullWidth
      aria-labelledby="delete-video-dialog-title"
      aria-describedby="delete-video-dialog-description"
    >
      <DialogTitle id="delete-video-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Warning color="warning" />
          Confirm Delete Video
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Alert severity="error" sx={{ mb: 2 }}>
          <Typography variant="body2">
            <strong>Warning:</strong> This action cannot be undone and will permanently delete the video file.
          </Typography>
        </Alert>
        
        <Typography variant="body1" id="delete-video-dialog-description" sx={{ mb: 2 }}>
          Are you sure you want to permanently delete <strong>"{video.filename || video.name || 'this video'}"</strong>?
        </Typography>
        
        <Typography variant="body2" color="text.secondary">
          This will permanently delete:
        </Typography>
        <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
          <li>The video file and all its metadata</li>
          <li>All ground truth annotations</li>
          <li>All detection results and analysis</li>
          <li>Project associations and test session data</li>
        </ul>
        
        {video.size && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            File size: {Math.round((video.size || video.fileSize || video.file_size || 0) / 1024 / 1024 * 100) / 100} MB
          </Typography>
        )}
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
          {loading ? 'Deleting...' : 'Delete Video'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default VideoDeleteConfirmationDialog;