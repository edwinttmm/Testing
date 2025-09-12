import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  LinearProgress,
  Alert,
  Pagination
} from '@mui/material';
import {
  Search,
  FilterList,
  PlayCircle,
  Visibility,
  CheckCircle,
  Error,
  Schedule,
  CloudUpload,
  Analytics
} from '@mui/icons-material';
import { VideoFile, VideoStatus } from '../services/types';
import { apiService } from '../services/api';

interface VideoLibraryStats {
  total_videos: number;
  pending_annotation: number;
  pending_validation: number;
  validated: number;
  processing: number;
  error: number;
}

interface VideoAnnotationOverlay {
  video: VideoFile;
  annotations: Array<{
    id: number;
    vru_type: string;
    frame_number: number;
    timestamp_ms: number;
    bbox: {
      x: number;
      y: number;
      width: number;
      height: number;
    };
    confidence: number;
    validated: boolean;
  }>;
}

const VideoLibraryComplete: React.FC = () => {
  // State management
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [stats, setStats] = useState<VideoLibraryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedVideo, setSelectedVideo] = useState<VideoFile | null>(null);
  const [annotationOverlay, setAnnotationOverlay] = useState<VideoAnnotationOverlay | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const videosPerPage = 20;

  // Load video library data
  const loadVideoLibrary = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Load videos with search/filter using available API methods
      const videoResponse = await apiService.getAllVideos();
      
      // Extract videos array from response
      const allVideos = videoResponse.videos || [];
      
      // Filter videos based on search and status
      let filteredVideos = allVideos;
      if (searchQuery) {
        filteredVideos = filteredVideos.filter(video => 
          video.filename.toLowerCase().includes(searchQuery.toLowerCase())
        );
      }
      if (statusFilter) {
        filteredVideos = filteredVideos.filter(video => video.status === statusFilter);
      }
      
      // Pagination
      const startIndex = (page - 1) * videosPerPage;
      const paginatedVideos = filteredVideos.slice(startIndex, startIndex + videosPerPage);
      
      setVideos(paginatedVideos);
      setTotalPages(Math.ceil(filteredVideos.length / videosPerPage));
      
      // Calculate statistics from all videos (not just filtered)
      const stats: VideoLibraryStats = {
        total_videos: allVideos.length,
        validated: allVideos.filter(v => v.status === 'validated').length,
        pending_validation: allVideos.filter(v => v.status === 'pending_validation').length,
        pending_annotation: allVideos.filter(v => v.status === 'pending_annotation').length,
        processing: allVideos.filter(v => v.status === 'processing').length,
        error: allVideos.filter(v => v.status === 'error').length
      };
      setStats(stats);
      
    } catch (err) {
      setError('Failed to load video library');
      console.error('Video library loading error:', err);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, statusFilter, page]);

  useEffect(() => {
    loadVideoLibrary();
  }, [loadVideoLibrary]);

  // Handle search
  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setPage(1); // Reset to first page on new search
  };

  // Handle filter change
  const handleFilterChange = (status: string) => {
    setStatusFilter(status);
    setPage(1); // Reset to first page on new filter
  };

  // Handle status update
  const handleStatusUpdate = async (videoId: number, newStatus: VideoStatus) => {
    try {
      // Use generic API method to update video status
      await apiService.put(`/api/v1/videos/${videoId}/status`, { 
        status: newStatus, 
        user_id: 1 
      });
      await loadVideoLibrary(); // Reload to get updated data
    } catch (err) {
      console.error('Status update error:', err);
      setError('Failed to update video status');
    }
  };

  // Handle video selection for detailed view
  const handleVideoSelect = async (video: VideoFile) => {
    try {
      setSelectedVideo(video);
      
      // Load annotations overlay using API service
      const annotations = await apiService.getAnnotations(video.id);
      const overlayData: VideoAnnotationOverlay = {
        video,
        annotations: annotations.map((ann: any) => ({
          id: ann.id,
          vru_type: ann.vruType || ann.vru_type,
          frame_number: ann.frameNumber || ann.frame_number,
          timestamp_ms: ann.timestampMs || ann.timestamp_ms,
          bbox: ann.bbox,
          confidence: ann.confidence || 1.0,
          validated: ann.validated || false
        }))
      };
      setAnnotationOverlay(overlayData);
      
    } catch (err) {
      console.error('Failed to load video annotations:', err);
    }
  };

  // Get status color
  const getStatusColor = (status: VideoStatus): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status) {
      case 'validated': return 'success';
      case 'pending_validation': return 'warning';
      case 'pending_annotation': return 'info';
      case 'processing': return 'primary';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  // Get status icon
  const getStatusIcon = (status: VideoStatus) => {
    switch (status) {
      case 'validated': return <CheckCircle />;
      case 'pending_validation': return <Schedule />;
      case 'pending_annotation': return <CloudUpload />;
      case 'processing': return <Analytics />;
      case 'error': return <Error />;
      default: return null;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header with Statistics */}
      <Typography variant="h4" gutterBottom>
        Video Library Management
      </Typography>
      
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={2}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6">{stats.total_videos}</Typography>
                <Typography variant="body2">Total Videos</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="success.main">{stats.validated}</Typography>
                <Typography variant="body2">Validated</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="warning.main">{stats.pending_validation}</Typography>
                <Typography variant="body2">Pending Validation</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="info.main">{stats.pending_annotation}</Typography>
                <Typography variant="body2">Pending Annotation</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="primary.main">{stats.processing}</Typography>
                <Typography variant="body2">Processing</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h6" color="error.main">{stats.error}</Typography>
                <Typography variant="body2">Errors</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Search and Filter Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Search by filename"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                InputProps={{
                  startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />
                }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel>Filter by Status</InputLabel>
                <Select
                  value={statusFilter}
                  label="Filter by Status"
                  onChange={(e) => handleFilterChange(e.target.value)}
                  startAdornment={<FilterList sx={{ mr: 1 }} />}
                >
                  <MenuItem value="">All Statuses</MenuItem>
                  <MenuItem value="pending_annotation">Pending Annotation</MenuItem>
                  <MenuItem value="pending_validation">Pending Validation</MenuItem>
                  <MenuItem value="validated">Validated</MenuItem>
                  <MenuItem value="processing">Processing</MenuItem>
                  <MenuItem value="error">Error</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant="outlined"
                onClick={loadVideoLibrary}
                disabled={loading}
              >
                Refresh
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Loading indicator */}
      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {/* Video Library Table */}
      <Card>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Filename</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="center">Duration</TableCell>
                <TableCell align="center">Detections</TableCell>
                <TableCell align="center">Annotations</TableCell>
                <TableCell align="center">Uploaded</TableCell>
                <TableCell align="center">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {videos.map((video) => (
                <TableRow key={video.id} hover>
                  <TableCell>
                    <Box>
                      <Typography variant="body2" fontWeight="medium">
                        {video.filename}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {video.width}×{video.height} • {video.frameRate}fps
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip
                      icon={getStatusIcon(video.status as VideoStatus)}
                      label={video.status.replace('_', ' ').toUpperCase()}
                      color={getStatusColor(video.status as VideoStatus)}
                      variant="outlined"
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="center">
                    {Math.round(video.duration / 1000)}s
                  </TableCell>
                  <TableCell align="center">
                    {video.detectionCount || 0}
                  </TableCell>
                  <TableCell align="center">
                    {video.annotationCount || 0}
                  </TableCell>
                  <TableCell align="center">
                    {new Date(video.uploadedAt).toLocaleDateString()}
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="View with annotations">
                      <IconButton
                        size="small"
                        onClick={() => handleVideoSelect(video)}
                        color="primary"
                      >
                        <Visibility />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Play video">
                      <IconButton size="small" color="secondary">
                        <PlayCircle />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        
        {/* Pagination */}
        {totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
            <Pagination
              count={totalPages}
              page={page}
              onChange={(_, newPage) => setPage(newPage)}
              color="primary"
            />
          </Box>
        )}
      </Card>

      {/* Video Details Dialog */}
      <Dialog
        open={!!selectedVideo}
        onClose={() => {
          setSelectedVideo(null);
          setAnnotationOverlay(null);
        }}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          Video Details: {selectedVideo?.filename}
        </DialogTitle>
        <DialogContent>
          {annotationOverlay && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Annotation Overlay
              </Typography>
              <Typography variant="body2" gutterBottom>
                {annotationOverlay.annotations.length} annotations detected
              </Typography>
              
              {/* Video playback with annotations would go here */}
              <Box sx={{ bgcolor: 'grey.100', p: 2, borderRadius: 1, mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Video player with annotation overlay will be displayed here
                </Typography>
              </Box>
              
              {/* Annotation list */}
              <Typography variant="subtitle1" gutterBottom>
                Detected Objects:
              </Typography>
              {annotationOverlay.annotations.slice(0, 10).map((annotation) => (
                <Chip
                  key={annotation.id}
                  label={`${annotation.vru_type} (${annotation.confidence.toFixed(2)})`}
                  variant={annotation.validated ? "filled" : "outlined"}
                  color={annotation.validated ? "success" : "default"}
                  size="small"
                  sx={{ mr: 1, mb: 1 }}
                />
              ))}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setSelectedVideo(null);
              setAnnotationOverlay(null);
            }}
          >
            Close
          </Button>
          <Button variant="contained" color="primary">
            Edit Annotations
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default VideoLibraryComplete;