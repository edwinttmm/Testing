/**
 * Enhanced Video Uploader Component
 * 
 * Features:
 * - Chunked uploads for large files (up to 1GB)
 * - Progress tracking with detailed metrics
 * - Retry mechanisms with exponential backoff
 * - Resume functionality for interrupted uploads
 * - Drag-and-drop support
 * - File validation and size limits
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  LinearProgress,
  Alert,
  Paper,
  Grid,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Cancel as CancelIcon,
  Pause as PauseIcon,
  PlayArrow as PlayArrowIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  VideoFile as VideoFileIcon,
  Info as InfoIcon
} from '@mui/icons-material';
import { EnhancedVideoUploadClient, UploadError, UploadProgress, UploadConfig } from '../services/enhanced_video_upload_client';

interface UploadItem {
  id: string;
  file: File;
  progress: UploadProgress | null;
  status: 'pending' | 'uploading' | 'paused' | 'completed' | 'failed' | 'cancelled';
  error?: string;
  result?: any;
  uploadSessionId?: string;
  canResume?: boolean;
  startTime: Date;
  endTime?: Date;
}

interface EnhancedVideoUploaderProps {
  onUploadComplete?: (result: any) => void;
  onUploadError?: (error: UploadError) => void;
  maxFiles?: number;
  config?: Partial<UploadConfig>;
  projectId?: string;
  className?: string;
}

const EnhancedVideoUploader: React.FC<EnhancedVideoUploaderProps> = ({
  onUploadComplete,
  onUploadError,
  maxFiles = 10,
  config = {},
  projectId,
  className
}) => {
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [selectedUpload, setSelectedUpload] = useState<UploadItem | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadClientRef = useRef<EnhancedVideoUploadClient | null>(null);
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());

  // Initialize upload client
  useEffect(() => {
    uploadClientRef.current = new EnhancedVideoUploadClient();
  }, []);

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Format duration
  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  };

  // Validate files
  const validateFiles = (files: File[]): { valid: File[]; invalid: Array<{ file: File; reason: string }> } => {
    const valid: File[] = [];
    const invalid: Array<{ file: File; reason: string }> = [];
    
    const allowedExtensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm'];
    const maxSize = config.maxFileSize || 1024 * 1024 * 1024; // 1GB default

    files.forEach(file => {
      // Check file type
      const extension = '.' + file.name.toLowerCase().split('.').pop();
      if (!allowedExtensions.includes(extension)) {
        invalid.push({ file, reason: `Unsupported format. Allowed: ${allowedExtensions.join(', ')}` });
        return;
      }

      // Check file size
      if (file.size > maxSize) {
        invalid.push({ file, reason: `File too large. Maximum: ${formatFileSize(maxSize)}` });
        return;
      }

      // Check for empty files
      if (file.size === 0) {
        invalid.push({ file, reason: 'Empty file not allowed' });
        return;
      }

      // Check for duplicates
      if (uploads.some(upload => upload.file.name === file.name && upload.file.size === file.size)) {
        invalid.push({ file, reason: 'File already queued for upload' });
        return;
      }

      valid.push(file);
    });

    return { valid, invalid };
  };

  // Add files to upload queue
  const addFiles = useCallback((files: File[]) => {
    if (uploads.length + files.length > maxFiles) {
      alert(`Maximum ${maxFiles} files allowed`);
      return;
    }

    const { valid, invalid } = validateFiles(files);
    
    // Show validation errors
    if (invalid.length > 0) {
      const errorMessage = invalid.map(item => `${item.file.name}: ${item.reason}`).join('\n');
      alert(`Some files were rejected:\n\n${errorMessage}`);
    }

    // Add valid files to queue
    const newUploads: UploadItem[] = valid.map(file => ({
      id: `upload_${Date.now()}_${Math.random().toString(36).substring(2)}`,
      file,
      progress: null,
      status: 'pending',
      startTime: new Date()
    }));

    setUploads(prev => [...prev, ...newUploads]);

    // Auto-start uploads
    newUploads.forEach(upload => {
      startUpload(upload);
    });
  }, [uploads, maxFiles, config]);

  // Start upload
  const startUpload = async (uploadItem: UploadItem) => {
    if (!uploadClientRef.current) return;

    // Create abort controller
    const abortController = new AbortController();
    abortControllersRef.current.set(uploadItem.id, abortController);

    // Update status
    setUploads(prev => prev.map(u => 
      u.id === uploadItem.id ? { ...u, status: 'uploading' } : u
    ));

    try {
      const result = await uploadClientRef.current.uploadVideo(uploadItem.file, {
        projectId,
        config,
        abortSignal: abortController.signal,
        onProgress: (progress: UploadProgress) => {
          setUploads(prev => prev.map(u => 
            u.id === uploadItem.id ? { ...u, progress } : u
          ));
        },
        onError: (error: UploadError) => {
          console.error(`Upload error for ${uploadItem.file.name}:`, error);
          
          setUploads(prev => prev.map(u => 
            u.id === uploadItem.id ? {
              ...u,
              status: 'failed',
              error: error.message,
              canResume: error.retryable,
              endTime: new Date()
            } : u
          ));

          if (onUploadError) {
            onUploadError(error);
          }
        }
      });

      // Upload completed successfully
      setUploads(prev => prev.map(u => 
        u.id === uploadItem.id ? {
          ...u,
          status: 'completed',
          result,
          endTime: new Date()
        } : u
      ));

      if (onUploadComplete) {
        onUploadComplete(result);
      }

    } catch (error) {
      const uploadError = error instanceof UploadError ? error : 
        new UploadError(error instanceof Error ? error.message : 'Unknown error', 'UPLOAD_FAILED');
      
      setUploads(prev => prev.map(u => 
        u.id === uploadItem.id ? {
          ...u,
          status: 'failed',
          error: uploadError.message,
          canResume: uploadError.retryable,
          endTime: new Date()
        } : u
      ));

      if (onUploadError) {
        onUploadError(uploadError);
      }
    } finally {
      abortControllersRef.current.delete(uploadItem.id);
    }
  };

  // Cancel upload
  const cancelUpload = (uploadId: string) => {
    const abortController = abortControllersRef.current.get(uploadId);
    if (abortController) {
      abortController.abort();
    }

    setUploads(prev => prev.map(u => 
      u.id === uploadId ? { ...u, status: 'cancelled', endTime: new Date() } : u
    ));
  };

  // Retry upload
  const retryUpload = (uploadItem: UploadItem) => {
    const newUpload = {
      ...uploadItem,
      status: 'pending' as const,
      error: undefined,
      progress: null,
      startTime: new Date(),
      endTime: undefined
    };

    setUploads(prev => prev.map(u => 
      u.id === uploadItem.id ? newUpload : u
    ));

    startUpload(newUpload);
  };

  // Remove upload from list
  const removeUpload = (uploadId: string) => {
    setUploads(prev => prev.filter(u => u.id !== uploadId));
  };

  // Clear completed uploads
  const clearCompleted = () => {
    setUploads(prev => prev.filter(u => u.status !== 'completed'));
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

    const files = Array.from(e.dataTransfer.files);
    addFiles(files);
  }, [addFiles]);

  // File input handler
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    addFiles(files);
    
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [addFiles]);

  // Get status summary
  const getStatusSummary = () => {
    const counts = uploads.reduce((acc, upload) => {
      acc[upload.status] = (acc[upload.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return counts;
  };

  const statusSummary = getStatusSummary();
  const hasActiveUploads = uploads.some(u => u.status === 'uploading');
  const hasFailedUploads = uploads.some(u => u.status === 'failed');

  return (
    <Box className={className}>
      {/* Upload Area */}
      <Paper
        elevation={2}
        sx={{
          p: 3,
          border: isDragging ? '2px dashed #1976d2' : '2px dashed #ccc',
          backgroundColor: isDragging ? '#f3f7ff' : 'background.paper',
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          '&:hover': {
            borderColor: '#1976d2',
            backgroundColor: '#f8f9fa'
          }
        }}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <CloudUploadIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
        <Typography variant="h6" gutterBottom>
          {isDragging ? 'Drop video files here' : 'Upload Video Files'}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Drag and drop files here or click to browse
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Supported formats: MP4, AVI, MOV, MKV, WebM • Max size: {formatFileSize(config.maxFileSize || 1024 * 1024 * 1024)}
        </Typography>
        
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".mp4,.avi,.mov,.mkv,.webm"
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />
      </Paper>

      {/* Upload Status Summary */}
      {uploads.length > 0 && (
        <Box sx={{ mt: 2, mb: 2 }}>
          <Grid container spacing={1} alignItems="center">
            <Grid item>
              <Typography variant="body2" color="text.secondary">
                {uploads.length} file{uploads.length !== 1 ? 's' : ''}:
              </Typography>
            </Grid>
            {Object.entries(statusSummary).map(([status, count]) => (
              <Grid item key={status}>
                <Chip
                  size="small"
                  label={`${count} ${status}`}
                  color={
                    status === 'completed' ? 'success' :
                    status === 'failed' ? 'error' :
                    status === 'uploading' ? 'primary' : 'default'
                  }
                  variant="outlined"
                />
              </Grid>
            ))}
            <Grid item sx={{ ml: 'auto' }}>
              <Button
                size="small"
                onClick={() => setShowDetails(true)}
                startIcon={<InfoIcon />}
              >
                Details
              </Button>
              {statusSummary.completed > 0 && (
                <Button
                  size="small"
                  onClick={clearCompleted}
                  sx={{ ml: 1 }}
                >
                  Clear Completed
                </Button>
              )}
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Upload List (condensed view) */}
      {uploads.length > 0 && !showDetails && (
        <Box>
          {uploads.slice(0, 3).map((upload) => (
            <Box key={upload.id} sx={{ mb: 1 }}>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box flex={1}>
                  <Typography variant="body2" noWrap>
                    {upload.file.name} ({formatFileSize(upload.file.size)})
                  </Typography>
                  {upload.progress && (
                    <LinearProgress
                      variant="determinate"
                      value={upload.progress.percentage}
                      sx={{ mt: 0.5 }}
                    />
                  )}
                </Box>
                <Box sx={{ ml: 2, minWidth: 100, textAlign: 'right' }}>
                  {upload.status === 'uploading' && upload.progress && (
                    <Typography variant="caption" color="text.secondary">
                      {upload.progress.percentage.toFixed(1)}% • {formatFileSize(upload.progress.uploadSpeedMbps * 1024 * 1024)}/s
                    </Typography>
                  )}
                  {upload.status === 'completed' && (
                    <CheckCircleIcon color="success" fontSize="small" />
                  )}
                  {upload.status === 'failed' && (
                    <ErrorIcon color="error" fontSize="small" />
                  )}
                </Box>
              </Box>
            </Box>
          ))}
          {uploads.length > 3 && (
            <Typography variant="caption" color="text.secondary">
              +{uploads.length - 3} more files...
            </Typography>
          )}
        </Box>
      )}

      {/* Detailed Upload Dialog */}
      <Dialog
        open={showDetails}
        onClose={() => setShowDetails(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Upload Details
          <IconButton
            onClick={() => setShowDetails(false)}
            sx={{ position: 'absolute', right: 8, top: 8 }}
          >
            <CancelIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          <List>
            {uploads.map((upload, index) => (
              <React.Fragment key={upload.id}>
                <ListItem>
                  <ListItemIcon>
                    <VideoFileIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" justifyContent="space-between">
                        <Typography variant="subtitle2">
                          {upload.file.name}
                        </Typography>
                        <Box display="flex" gap={1}>
                          {upload.status === 'uploading' && (
                            <IconButton size="small" onClick={() => cancelUpload(upload.id)}>
                              <CancelIcon fontSize="small" />
                            </IconButton>
                          )}
                          {upload.status === 'failed' && upload.canResume && (
                            <IconButton size="small" onClick={() => retryUpload(upload)}>
                              <RefreshIcon fontSize="small" />
                            </IconButton>
                          )}
                          {['completed', 'failed', 'cancelled'].includes(upload.status) && (
                            <IconButton size="small" onClick={() => removeUpload(upload.id)}>
                              <CancelIcon fontSize="small" />
                            </IconButton>
                          )}
                        </Box>
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Size: {formatFileSize(upload.file.size)} • Status: {upload.status}
                        </Typography>
                        
                        {upload.progress && (
                          <Box sx={{ mt: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={upload.progress.percentage}
                            />
                            <Box display="flex" justifyContent="space-between" mt={0.5}>
                              <Typography variant="caption">
                                {upload.progress.percentage.toFixed(1)}% ({upload.progress.chunksCompleted}/{upload.progress.totalChunks} chunks)
                              </Typography>
                              <Typography variant="caption">
                                {formatFileSize(upload.progress.uploadSpeedMbps * 1024 * 1024)}/s • ETA: {formatDuration(upload.progress.etaSeconds)}
                              </Typography>
                            </Box>
                          </Box>
                        )}
                        
                        {upload.error && (
                          <Alert severity="error" sx={{ mt: 1 }}>
                            {upload.error}
                          </Alert>
                        )}
                        
                        {upload.endTime && (
                          <Typography variant="caption" color="text.secondary">
                            Duration: {formatDuration((upload.endTime.getTime() - upload.startTime.getTime()) / 1000)}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                </ListItem>
                {index < uploads.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDetails(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Global Status Messages */}
      {hasActiveUploads && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Upload in progress... Large files are uploaded in chunks for better reliability.
        </Alert>
      )}
      
      {hasFailedUploads && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          Some uploads failed. Click the retry button to try again, or check the details for more information.
        </Alert>
      )}
    </Box>
  );
};

export default EnhancedVideoUploader;