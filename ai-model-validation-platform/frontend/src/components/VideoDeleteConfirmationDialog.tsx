import React, { useState, useEffect } from 'react';
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
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  Checkbox,
  FormControlLabel,
  Collapse,
  LinearProgress,
} from '@mui/material';
import {
  Warning,
  Delete,
  VideoLibrary,
  Label,
  Assessment,
  Link,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import { VideoFile } from '../services/types';

interface VideoDeleteConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  video: VideoFile | null;
  onConfirm: (videoId: string) => Promise<void>;
  loading?: boolean;
  projectsUsingVideo?: string[];
  annotationCount?: number;
  testSessionCount?: number;
}

const VideoDeleteConfirmationDialog: React.FC<VideoDeleteConfirmationDialogProps> = ({
  open,
  onClose,
  video,
  onConfirm,
  loading = false,
  projectsUsingVideo = [],
  annotationCount = 0,
  testSessionCount = 0,
}) => {
  const [confirmDeletion, setConfirmDeletion] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [deletionStep, setDeletionStep] = useState<'confirm' | 'deleting' | 'cleanup' | 'complete'>('confirm');

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (open) {
      setConfirmDeletion(false);
      setShowDetails(false);
      setDeletionStep('confirm');
    }
  }, [open]);

  const handleConfirm = async () => {
    if (!video || !confirmDeletion) return;
    
    try {
      setDeletionStep('deleting');
      await onConfirm(video.id);
      setDeletionStep('complete');
      
      // Close after a brief delay to show success
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (error) {
      setDeletionStep('confirm');
      // Error handling is done in the parent component
      console.error('Error deleting video:', error);
    }
  };

  const handleClose = () => {
    if (!loading && deletionStep !== 'deleting' && deletionStep !== 'cleanup') {
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

  const isHighImpactDeletion = projectsUsingVideo.length > 0 || annotationCount > 10 || testSessionCount > 0;

  if (deletionStep === 'deleting' || deletionStep === 'cleanup') {
    return (
      <Dialog open={open} maxWidth="sm" fullWidth disableEscapeKeyDown>
        <DialogContent sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress size={60} sx={{ mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            {deletionStep === 'deleting' ? 'Deleting Video...' : 'Cleaning up resources...'}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Please wait while we remove the video and all associated data.
          </Typography>
          <LinearProgress sx={{ width: '100%' }} />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            This may take a moment for videos with many annotations
          </Typography>
        </DialogContent>
      </Dialog>
    );
  }

  if (deletionStep === 'complete') {
    return (
      <Dialog open={open} maxWidth="sm" fullWidth>
        <DialogContent sx={{ textAlign: 'center', py: 4 }}>
          <Box sx={{ color: 'success.main', mb: 2 }}>
            <Delete sx={{ fontSize: 60 }} />
          </Box>
          <Typography variant="h6" gutterBottom>
            Video Deleted Successfully
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {video.filename || video.name} has been permanently removed from the system.
          </Typography>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog 
      open={open} 
      onClose={handleClose} 
      maxWidth="md" 
      fullWidth
      aria-labelledby="delete-video-dialog-title"
      aria-describedby="delete-video-dialog-description"
    >
      <DialogTitle id="delete-video-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Warning color="error" />
          Confirm Permanent Deletion
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>Warning:</strong> This action cannot be undone. The video file and all associated data will be permanently deleted.
          </Typography>
        </Alert>

        {/* Video Information */}
        <Typography variant="h6" gutterBottom>
          Video to Delete
        </Typography>
        
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
                <Chip 
                  label={formatFileSize(video.size || video.fileSize || video.file_size || 0)} 
                  size="small" 
                  variant="outlined" 
                />
              </Box>
            </Box>
          </Box>
        </Paper>

        {/* High Impact Warning */}
        {isHighImpactDeletion && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <strong>High Impact Deletion:</strong> This video is actively used in your projects and has significant data associated with it.
            </Typography>
          </Alert>
        )}

        {/* Impact Summary */}
        <Paper sx={{ bgcolor: 'action.hover', p: 2, mb: 2 }}>
          <Button
            onClick={() => setShowDetails(!showDetails)}
            endIcon={showDetails ? <ExpandLess /> : <ExpandMore />}
            sx={{ p: 0, mb: showDetails ? 2 : 0, justifyContent: 'flex-start', textTransform: 'none' }}
          >
            <Typography variant="subtitle2">
              What will be permanently deleted
            </Typography>
          </Button>

          <Collapse in={showDetails}>
            <List dense>
              <ListItem sx={{ px: 0 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <VideoLibrary fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText 
                  primary="Video file and metadata"
                  secondary={`${formatFileSize(video.size || video.fileSize || video.file_size || 0)} of storage space`}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
              
              <ListItem sx={{ px: 0 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <Label fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText 
                  primary={`${annotationCount || video.detectionCount || 0} ground truth annotations`}
                  secondary="All bounding boxes, labels, and validation data"
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>

              <ListItem sx={{ px: 0 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <Assessment fontSize="small" color="error" />
                </ListItemIcon>
                <ListItemText 
                  primary={`${testSessionCount} test session references`}
                  secondary="Detection results, performance metrics, and analysis data"
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>

              {projectsUsingVideo.length > 0 && (
                <ListItem sx={{ px: 0 }}>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <Link fontSize="small" color="error" />
                  </ListItemIcon>
                  <ListItemText 
                    primary={`Links from ${projectsUsingVideo.length} project${projectsUsingVideo.length > 1 ? 's' : ''}`}
                    secondary={projectsUsingVideo.join(', ')}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                </ListItem>
              )}
            </List>
          </Collapse>
        </Paper>

        {/* Confirmation checkbox */}
        <FormControlLabel
          control={
            <Checkbox
              checked={confirmDeletion}
              onChange={(e) => setConfirmDeletion(e.target.checked)}
              color="error"
            />
          }
          label={
            <Typography variant="body2">
              I understand this action is permanent and cannot be undone
            </Typography>
          }
          sx={{ mb: 1 }}
        />

        <Typography variant="body1" id="delete-video-dialog-description">
          Type the video name to confirm: <strong>{video.filename || video.name}</strong>
        </Typography>
      </DialogContent>
      
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button 
          onClick={handleConfirm}
          variant="contained"
          color="error"
          disabled={loading || !confirmDeletion}
          startIcon={loading ? <CircularProgress size={20} /> : <Delete />}
        >
          {loading ? 'Deleting...' : 'Permanently Delete Video'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default VideoDeleteConfirmationDialog;