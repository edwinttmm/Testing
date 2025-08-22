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
  Chip,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  LinkOff,
  VideoLibrary,
  Assessment,
  Info,
} from '@mui/icons-material';
import { VideoFile } from '../services/types';

interface UnlinkVideoConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  video: VideoFile | null;
  projectName?: string;
  onConfirm: (videoId: string) => Promise<void>;
  loading?: boolean;
}

const UnlinkVideoConfirmationDialog: React.FC<UnlinkVideoConfirmationDialogProps> = ({
  open,
  onClose,
  video,
  projectName = 'this project',
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
      console.error('Error unlinking video:', error);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  if (!video) return null;

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose} 
      maxWidth="md" 
      fullWidth
      aria-labelledby="unlink-video-dialog-title"
      aria-describedby="unlink-video-dialog-description"
    >
      <DialogTitle id="unlink-video-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <LinkOff color="warning" />
          Unlink Video from Project
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>Note:</strong> This will only remove the video from this project. 
            The video file and its annotations will remain in your library.
          </Typography>
        </Alert>

        <Typography variant="h6" gutterBottom>
          Video Details
        </Typography>
        
        {/* Video Information Card */}
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <VideoLibrary color="primary" sx={{ fontSize: 32 }} />
            <Box>
              <Typography variant="h6" component="div">
                {video.filename || video.name || 'Unknown Video'}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                <Chip 
                  label={video.status} 
                  size="small" 
                  color={video.status === 'completed' ? 'success' : video.status === 'processing' ? 'warning' : 'default'}
                />
                {video.duration && (
                  <Chip 
                    label={formatDuration(video.duration)} 
                    size="small" 
                    variant="outlined" 
                  />
                )}
              </Box>
            </Box>
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Box>
              <Typography variant="body2" color="text.secondary">
                <strong>File Size:</strong> {formatFileSize(video.size || video.fileSize || video.file_size || 0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                <strong>Uploaded:</strong> {new Date(video.createdAt || video.created_at || video.uploadedAt || '').toLocaleDateString()}
              </Typography>
            </Box>
            {video.detectionCount !== undefined && (
              <Box>
                <Typography variant="body2" color="text.secondary">
                  <strong>Detections:</strong> {video.detectionCount}
                </Typography>
              </Box>
            )}
            {video.ground_truth_generated && (
              <Box>
                <Typography variant="body2" color="text.secondary">
                  <strong>Ground Truth:</strong> Generated
                </Typography>
              </Box>
            )}
          </Box>
        </Paper>

        <Typography variant="body1" id="unlink-video-dialog-description" sx={{ mb: 2 }}>
          Are you sure you want to unlink <strong>"{video.filename || video.name || 'this video'}"</strong> from <strong>{projectName}</strong>?
        </Typography>

        {/* What will happen */}
        <Paper sx={{ bgcolor: 'action.hover', p: 2 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Info color="primary" fontSize="small" />
            What this action will do:
          </Typography>
          <List dense sx={{ pl: 1 }}>
            <ListItem sx={{ px: 0 }}>
              <ListItemIcon sx={{ minWidth: 32 }}>
                <LinkOff fontSize="small" color="action" />
              </ListItemIcon>
              <ListItemText 
                primary="Remove video from project's ground truth dataset"
                primaryTypographyProps={{ variant: 'body2' }}
              />
            </ListItem>
            <ListItem sx={{ px: 0 }}>
              <ListItemIcon sx={{ minWidth: 32 }}>
                <Assessment fontSize="small" color="action" />
              </ListItemIcon>
              <ListItemText 
                primary="Remove video from test sessions (won't affect completed tests)"
                primaryTypographyProps={{ variant: 'body2' }}
              />
            </ListItem>
          </List>

          <Alert severity="success" sx={{ mt: 2, py: 1 }}>
            <Typography variant="body2">
              <strong>Preserved:</strong> The video file, annotations, and detection results will remain in your library and can be re-linked later.
            </Typography>
          </Alert>
        </Paper>

        {/* Warning for active test sessions */}
        {video.status === 'processing' && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>Warning:</strong> This video appears to be processing. 
              Unlinking it may interrupt ongoing operations.
            </Typography>
          </Alert>
        )}
      </DialogContent>
      
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button 
          onClick={handleConfirm}
          variant="contained"
          color="warning"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={20} /> : <LinkOff />}
        >
          {loading ? 'Unlinking...' : 'Unlink from Project'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default UnlinkVideoConfirmationDialog;