import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Checkbox,
  Alert,
  CircularProgress,
  Chip,
  TextField,
  InputAdornment,
  Divider,
  Card,
  CardContent,
} from '@mui/material';
import {
  Search,
  CheckCircle,
  HourglassEmpty,
  Error,
  VideoFile as VideoIcon,
} from '@mui/icons-material';
import { VideoFile } from '../services/types';
import { getAllVideos } from '../services/api';
import { getErrorMessage } from '../utils/errorUtils';

interface VideoSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  projectId: string;
  onSelectionComplete: (selectedVideos: VideoFile[]) => void;
  selectedVideoIds?: string[];
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatDuration = (seconds?: number): string => {
  if (!seconds) return 'Unknown';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const getStatusIcon = (status: VideoFile['status']) => {
  switch (status) {
    case 'completed':
      return <CheckCircle color="success" fontSize="small" />;
    case 'processing':
      return <HourglassEmpty color="warning" fontSize="small" />;
    case 'failed':
      return <Error color="error" fontSize="small" />;
    default:
      return <HourglassEmpty color="info" fontSize="small" />;
  }
};

const getStatusColor = (status: VideoFile['status']) => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'processing':
      return 'warning';
    case 'failed':
      return 'error';
    default:
      return 'info';
  }
};

const VideoSelectionDialog: React.FC<VideoSelectionDialogProps> = ({
  open,
  onClose,
  projectId,
  onSelectionComplete,
  selectedVideoIds = [],
}) => {
  const [availableVideos, setAvailableVideos] = useState<VideoFile[]>([]);
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(
    new Set(selectedVideoIds)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus] = useState<VideoFile['status'] | 'all'>('all');

  // Load available videos from central store
  const loadAvailableVideos = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Get unassigned videos from central store
      const response = await getAllVideos(true); // Only unassigned videos
      setAvailableVideos(response.videos || []);
      
    } catch (err) {
      console.error('Failed to load available videos:', err);
      setError(getErrorMessage(err, 'Failed to load available videos'));
    } finally {
      setLoading(false);
    }
  }, []);

  // Load videos on dialog open
  useEffect(() => {
    if (open) {
      loadAvailableVideos();
    }
  }, [open, loadAvailableVideos]);


  useEffect(() => {
    if (open) {
      loadAvailableVideos();
    }
  }, [open, loadAvailableVideos]);

  const handleVideoToggle = (videoId: string) => {
    const newSelection = new Set(selectedVideos);
    if (newSelection.has(videoId)) {
      newSelection.delete(videoId);
    } else {
      newSelection.add(videoId);
    }
    setSelectedVideos(newSelection);
  };

  const getFilteredVideos = useCallback(() => {
    return availableVideos.filter(video => {
      const matchesSearch = video.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           video.originalName?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = filterStatus === 'all' || video.status === filterStatus;
      
      return matchesSearch && matchesStatus;
    });
  }, [availableVideos, searchTerm, filterStatus]);

  const handleSelectAll = () => {
    const filteredVideos = getFilteredVideos();
    const allFilteredIds = new Set(filteredVideos.map(v => v.id));
    
    // Check if all filtered videos are already selected
    const allSelected = filteredVideos.every(video => selectedVideos.has(video.id));
    
    if (allSelected) {
      // Deselect all filtered videos
      const newSelection = new Set(selectedVideos);
      filteredVideos.forEach(video => newSelection.delete(video.id));
      setSelectedVideos(newSelection);
    } else {
      // Select all filtered videos
      const newSelection = new Set([...selectedVideos, ...allFilteredIds]);
      setSelectedVideos(newSelection);
    }
  };

  const handleConfirm = () => {
    const selectedVideoObjects = availableVideos.filter(video => 
      selectedVideos.has(video.id)
    );
    onSelectionComplete(selectedVideoObjects);
    onClose();
  };

  const handleCancel = () => {
    setSelectedVideos(new Set(selectedVideoIds)); // Reset to initial selection
    onClose();
  };

  const filteredVideos = getFilteredVideos();
  const selectedCount = selectedVideos.size;

  return (
    <Dialog
      open={open}
      onClose={handleCancel}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { height: '80vh' }
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <VideoIcon color="primary" />
          <Typography variant="h6">Select Videos from Ground Truth Library</Typography>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ p: 0 }}>
        {error && (
          <Alert severity="error" sx={{ m: 2 }}>
            {error}
          </Alert>
        )}

        {/* Search and Filter Controls */}
        <Box sx={{ p: 2, pb: 0 }}>
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <TextField
              placeholder="Search videos..."
              size="small"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ flexGrow: 1 }}
            />
            <Button
              variant="outlined"
              size="small"
              onClick={handleSelectAll}
              disabled={filteredVideos.length === 0}
            >
              {filteredVideos.length > 0 && filteredVideos.every(v => selectedVideos.has(v.id))
                ? 'Deselect All'
                : 'Select All'
              }
            </Button>
          </Box>

          {/* Selection Summary */}
          <Card variant="outlined">
            <CardContent sx={{ py: 1.5 }}>
              <Typography variant="body2" color="text.secondary">
                {selectedCount} video{selectedCount !== 1 ? 's' : ''} selected
                {filteredVideos.length > 0 && ` • ${filteredVideos.length} available`}
              </Typography>
            </CardContent>
          </Card>
        </Box>

        <Divider />

        {/* Video List */}
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : filteredVideos.length === 0 ? (
            <Box sx={{ textAlign: 'center', p: 4 }}>
              <VideoIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                {availableVideos.length === 0 
                  ? 'No videos available'
                  : 'No videos match your search'
                }
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {availableVideos.length === 0
                  ? 'Upload videos to the Ground Truth library first'
                  : 'Try adjusting your search terms'
                }
              </Typography>
            </Box>
          ) : (
            <List sx={{ py: 0 }}>
              {filteredVideos.map((video, index) => (
                <React.Fragment key={video.id}>
                  <ListItem
                    sx={{
                      cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                    onClick={() => handleVideoToggle(video.id)}
                  >
                    <Checkbox
                      checked={selectedVideos.has(video.id)}
                      onChange={() => handleVideoToggle(video.id)}
                      sx={{ mr: 1 }}
                    />
                    
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {getStatusIcon(video.status)}
                          <Typography variant="body1">
                            {video.filename || video.originalName}
                          </Typography>
                        </Box>
                      }
                      secondary={
                        <Box>
                          <Typography variant="caption" component="div">
                            Size: {formatFileSize(video.file_size || video.fileSize || video.size || 0)} • 
                            Duration: {formatDuration(video.duration)} • 
                            Uploaded: {new Date(video.created_at || video.createdAt || video.uploadedAt).toLocaleDateString()}
                          </Typography>
                          
                          <Box sx={{ mt: 0.5, display: 'flex', gap: 1 }}>
                            <Chip
                              label={video.status}
                              color={getStatusColor(video.status)}
                              size="small"
                            />
                            {video.detectionCount && (
                              <Chip
                                label={`${video.detectionCount} detections`}
                                variant="outlined"
                                size="small"
                              />
                            )}
                            <Chip
                              label="Ground Truth Ready"
                              color="success"
                              variant="outlined"
                              size="small"
                            />
                          </Box>
                        </Box>
                      }
                    />
                  </ListItem>
                  
                  {index < filteredVideos.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleCancel}>
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={selectedCount === 0}
        >
          Link {selectedCount} Video{selectedCount !== 1 ? 's' : ''}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default VideoSelectionDialog;