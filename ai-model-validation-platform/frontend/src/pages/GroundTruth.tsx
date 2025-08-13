import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  LinearProgress,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Alert,
  Snackbar,
} from '@mui/material';
import {
  CloudUpload,
  CheckCircle,
  HourglassEmpty,
  Error,
  Visibility,
  Delete,
  Cancel,
} from '@mui/icons-material';
import { VideoFile, ApiError } from '../services/types';
import { apiService } from '../services/api';

interface UploadingVideo {
  id: string;
  file: File;
  name: string;
  size: string;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
}

interface UploadError {
  message: string;
  fileName: string;
}

// Video format validation
const SUPPORTED_FORMATS = ['mp4', 'avi', 'mov'];
const MAX_FILE_SIZE = 1024 * 1024 * 1024; // 1GB in bytes

// Utility functions
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

const validateVideoFile = (file: File): string | null => {
  const extension = file.name.split('.').pop()?.toLowerCase();
  
  if (!extension || !SUPPORTED_FORMATS.includes(extension)) {
    return `Unsupported format. Please use: ${SUPPORTED_FORMATS.join(', ').toUpperCase()}`;
  }
  
  if (file.size > MAX_FILE_SIZE) {
    return `File too large. Maximum size: ${formatFileSize(MAX_FILE_SIZE)}`;
  }
  
  return null;
};

const GroundTruth: React.FC = () => {
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [uploadingVideos, setUploadingVideos] = useState<UploadingVideo[]>([]);
  const [uploadDialog, setUploadDialog] = useState(false);
  const [viewDialog, setViewDialog] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState<VideoFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [uploadErrors, setUploadErrors] = useState<UploadError[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Mock project ID - in real app this would come from route params or context
  const projectId = 'f4ad5fe6-9cdf-450e-8897-bf0d719b25c2'; // Using first available project ID

  // Load videos on component mount
  useEffect(() => {
    loadVideos();
  }, [projectId]);

  const loadVideos = async () => {
    try {
      setError(null);
      const videoList = await apiService.getVideos(projectId);
      setVideos(videoList);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to load videos');
    }
  };

  const getStatusIcon = (status: VideoFile['status'] | UploadingVideo['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'processing':
      case 'uploading':
        return <HourglassEmpty color="warning" />;
      case 'failed':
        return <Error color="error" />;
      default:
        return <HourglassEmpty color="info" />;
    }
  };


  // File upload handlers
  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return;
    
    const newUploadErrors: UploadError[] = [];
    const validFiles: File[] = [];
    
    Array.from(files).forEach(file => {
      const validationError = validateVideoFile(file);
      if (validationError) {
        newUploadErrors.push({
          message: validationError,
          fileName: file.name
        });
      } else {
        validFiles.push(file);
      }
    });
    
    setUploadErrors(newUploadErrors);
    
    if (validFiles.length > 0) {
      uploadFiles(validFiles);
    }
  }, []);

  const uploadFiles = async (files: File[]) => {
    const newUploadingVideos: UploadingVideo[] = files.map(file => ({
      id: Math.random().toString(36).substr(2, 9),
      file,
      name: file.name,
      size: formatFileSize(file.size),
      progress: 0,
      status: 'uploading'
    }));
    
    setUploadingVideos(prev => [...prev, ...newUploadingVideos]);
    setUploadDialog(false);
    
    // Upload files concurrently
    const uploadPromises = newUploadingVideos.map(async (uploadingVideo) => {
      try {
        const uploadedVideo = await apiService.uploadVideo(
          projectId,
          uploadingVideo.file,
          (progress) => {
            setUploadingVideos(prev => 
              prev.map(v => 
                v.id === uploadingVideo.id 
                  ? { ...v, progress }
                  : v
              )
            );
          }
        );
        
        // Update status to processing
        setUploadingVideos(prev => 
          prev.map(v => 
            v.id === uploadingVideo.id 
              ? { ...v, status: 'processing', progress: 100 }
              : v
          )
        );
        
        // Add to main videos list and remove from uploading
        setTimeout(() => {
          setVideos(prev => [uploadedVideo, ...prev]);
          setUploadingVideos(prev => prev.filter(v => v.id !== uploadingVideo.id));
          setSuccessMessage(`Successfully uploaded ${uploadingVideo.name}`);
        }, 1000);
        
      } catch (err) {
        const apiError = err as ApiError;
        setUploadingVideos(prev => 
          prev.map(v => 
            v.id === uploadingVideo.id 
              ? { ...v, status: 'failed', error: apiError.message }
              : v
          )
        );
        
        setUploadErrors(prev => [...prev, {
          message: apiError.message || 'Upload failed',
          fileName: uploadingVideo.name
        }]);
      }
    });
    
    await Promise.allSettled(uploadPromises);
  };

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    handleFileSelect(files);
  }, [handleFileSelect]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    handleFileSelect(e.target.files);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [handleFileSelect]);

  const handleDeleteVideo = async (videoId: string) => {
    try {
      await apiService.deleteVideo(videoId);
      setVideos(prev => prev.filter(v => v.id !== videoId));
      setSuccessMessage('Video deleted successfully');
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || 'Failed to delete video');
    }
  };

  const cancelUpload = (uploadId: string) => {
    setUploadingVideos(prev => prev.filter(v => v.id !== uploadId));
  };

  const handleViewVideo = async (video: VideoFile) => {
    setSelectedVideo(video);
    setViewDialog(true);
    
    // Load ground truth data if available
    if (video.ground_truth_generated || video.groundTruthGenerated) {
      try {
        const groundTruth = await apiService.getGroundTruth(video.id);
        // Could store ground truth data in state if needed for detailed view
        console.log('Ground truth data:', groundTruth);
      } catch (err) {
        console.warn('Could not load ground truth data:', err);
      }
    }
  };

  const allVideos = [...uploadingVideos, ...videos];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Ground Truth Management</Typography>
        <Button
          variant="contained"
          startIcon={<CloudUpload />}
          onClick={() => setUploadDialog(true)}
        >
          Upload Video
        </Button>
      </Box>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Total Videos
              </Typography>
              <Typography variant="h3" color="primary">
                {videos.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Uploaded and processed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Processing Queue
              </Typography>
              <Typography variant="h3" color="warning.main">
                {videos.filter(v => v.status === 'processing').length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Videos being processed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Total Detections
              </Typography>
              <Typography variant="h3" color="success.main">
                {videos.reduce((sum, v) => sum + (v.detectionCount || 0), 0)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Ground truth objects
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Video Library
          </Typography>
          
          <List>
            {/* Show uploading videos first */}
            {uploadingVideos.map((video) => (
              <ListItem key={video.id} divider>
                <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
                  {getStatusIcon(video.status)}
                </Box>
                
                <ListItemText
                  primary={video.name}
                  secondary={
                    <Box>
                      <Typography variant="caption" component="div">
                        Size: {video.size} • Status: {video.status}
                      </Typography>
                      {video.status === 'uploading' && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="caption">Uploading... {video.progress}%</Typography>
                          <LinearProgress variant="determinate" value={video.progress} sx={{ mt: 0.5 }} />
                        </Box>
                      )}
                      {video.status === 'processing' && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="caption">Processing ground truth...</Typography>
                          <LinearProgress sx={{ mt: 0.5 }} />
                        </Box>
                      )}
                      {video.status === 'failed' && (
                        <Alert severity="error" sx={{ mt: 1 }}>
                          {video.error}
                        </Alert>
                      )}
                    </Box>
                  }
                />
                
                <ListItemSecondaryAction>
                  {video.status === 'uploading' && (
                    <IconButton size="small" onClick={() => cancelUpload(video.id)}>
                      <Cancel />
                    </IconButton>
                  )}
                </ListItemSecondaryAction>
              </ListItem>
            ))}
            
            {/* Show completed videos */}
            {videos.map((video) => (
              <ListItem key={video.id} divider>
                <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
                  {getStatusIcon(video.status)}
                </Box>
                
                <ListItemText
                  primary={video.filename || video.name}
                  secondary={
                    <Box>
                      <Typography variant="caption" component="div">
                        Size: {formatFileSize(video.file_size || video.fileSize || video.size || 0)} • Duration: {formatDuration(video.duration)} • Uploaded: {new Date(video.created_at || video.createdAt || video.uploadedAt).toLocaleDateString()}
                      </Typography>
                      {video.status === 'processing' && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="caption">Processing ground truth...</Typography>
                          <LinearProgress sx={{ mt: 0.5 }} />
                        </Box>
                      )}
                      {(video.status === 'completed' || video.groundTruthGenerated) && (
                        <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                          <Chip
                            label={`Ready for testing`}
                            size="small"
                            color="success"
                          />
                        </Box>
                      )}
                    </Box>
                  }
                />
                
                <ListItemSecondaryAction>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <IconButton 
                      size="small" 
                      title="View details"
                      onClick={() => handleViewVideo(video)}
                    >
                      <Visibility />
                    </IconButton>
                    <IconButton 
                      size="small" 
                      title="Delete video"
                      onClick={() => handleDeleteVideo(video.id)}
                    >
                      <Delete />
                    </IconButton>
                  </Box>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
            
            {/* Show empty state */}
            {allVideos.length === 0 && (
              <ListItem>
                <ListItemText
                  primary="No videos uploaded yet"
                  secondary="Click 'Upload Video' to get started"
                  sx={{ textAlign: 'center' }}
                />
              </ListItem>
            )}
          </List>
        </CardContent>
      </Card>

      <Dialog open={uploadDialog} onClose={() => setUploadDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Upload Test Video</DialogTitle>
        <DialogContent>
          <Box
            sx={{
              border: isDragging ? '2px dashed #1976d2' : '2px dashed #ccc',
              borderRadius: 2,
              p: 4,
              textAlign: 'center',
              cursor: 'pointer',
              bgcolor: isDragging ? 'action.hover' : 'transparent',
              transition: 'all 0.2s ease-in-out',
              '&:hover': {
                borderColor: 'primary.main',
                bgcolor: 'action.hover',
              },
            }}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <CloudUpload sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Drop video files here or click to browse
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Supported formats: MP4, AVI, MOV • Max size: 1GB
            </Typography>
          </Box>
          
          <Typography variant="body2" sx={{ mt: 2 }}>
            After upload, the system will automatically process the video using YOLOv8 to generate initial ground truth data.
          </Typography>
          
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".mp4,.avi,.mov"
            style={{ display: 'none' }}
            onChange={handleFileInputChange}
          />
          
          {uploadErrors.length > 0 && (
            <Box sx={{ mt: 2 }}>
              {uploadErrors.map((error, index) => (
                <Alert key={index} severity="error" sx={{ mb: 1 }}>
                  <strong>{error.fileName}:</strong> {error.message}
                </Alert>
              ))}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUploadDialog(false)}>Cancel</Button>
          <Button 
            variant="contained" 
            onClick={() => fileInputRef.current?.click()}
          >
            Browse Files
          </Button>
        </DialogActions>
      </Dialog>

      {/* Video View Dialog */}
      <Dialog open={viewDialog} onClose={() => setViewDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          Video Details: {selectedVideo?.filename || selectedVideo?.name}
        </DialogTitle>
        <DialogContent>
          {selectedVideo && (
            <Box sx={{ mt: 2 }}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="h6" gutterBottom>
                    Video Information
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Filename:</strong> {selectedVideo.filename || selectedVideo.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Size:</strong> {formatFileSize(selectedVideo.file_size || selectedVideo.fileSize || selectedVideo.size || 0)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Duration:</strong> {formatDuration(selectedVideo.duration)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Status:</strong> {selectedVideo.status}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Uploaded:</strong> {new Date(selectedVideo.created_at || selectedVideo.createdAt || selectedVideo.uploadedAt).toLocaleString()}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Ground Truth:</strong> {selectedVideo.ground_truth_generated || selectedVideo.groundTruthGenerated ? 'Generated' : 'Pending'}
                    </Typography>
                  </Box>
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="h6" gutterBottom>
                    Detection Summary
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Total Detections:</strong> {selectedVideo.detectionCount || 0}
                    </Typography>
                    {selectedVideo.status === 'processing' && (
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="body2" color="warning.main">
                          Processing ground truth data...
                        </Typography>
                        <LinearProgress sx={{ mt: 1 }} />
                      </Box>
                    )}
                    {selectedVideo.status === 'completed' && (
                      <Chip
                        label="Ready for Testing"
                        color="success"
                        size="small"
                        sx={{ mt: 1 }}
                      />
                    )}
                    {selectedVideo.status === 'failed' && (
                      <Alert severity="error" sx={{ mt: 1 }}>
                        Processing failed. Please try re-uploading the video.
                      </Alert>
                    )}
                  </Box>
                </Grid>
              </Grid>
              
              {/* Actions */}
              <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<Delete />}
                  onClick={() => {
                    setViewDialog(false);
                    handleDeleteVideo(selectedVideo.id);
                  }}
                >
                  Delete Video
                </Button>
                {selectedVideo.status === 'completed' && (
                  <Button
                    variant="contained"
                    startIcon={<CheckCircle />}
                    disabled
                  >
                    Ready for Testing
                  </Button>
                )}
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Success/Error Snackbars */}
      <Snackbar
        open={!!successMessage}
        autoHideDuration={6000}
        onClose={() => setSuccessMessage(null)}
        message={successMessage}
      />
      
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

export default GroundTruth;