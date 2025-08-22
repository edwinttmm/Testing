import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardMedia,
  Grid,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Menu,
  Alert,
  Skeleton,
  Stack,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Tab,
  Tabs,
  LinearProgress,
  Snackbar,
  InputAdornment,
  ButtonGroup,
} from '@mui/material';
import {
  Visibility,
  MoreVert,
  FilterList,
  Search,
  Download,
  Refresh,
  ViewList,
  ViewModule,
  Analytics,
  VideoLibrary,
  Label,
  Assignment,
  GetApp,
  Clear,
  TrendingUp,
  Delete,
} from '@mui/icons-material';
import {
  VideoFile,
  GroundTruthAnnotation,
  VRUType,
  ApiError,
  DetectionTypeBreakdown,
  DetectionTypeMetrics,
} from '../services/types';
import { 
  getAvailableGroundTruthVideos,
  getAnnotations,
  exportAnnotations,
  deleteVideo,
  getAllVideos,
  getProjects,
  getVideoDetections,
} from '../services/api';
import EnhancedVideoPlayer from '../components/EnhancedVideoPlayer';
import VideoDeleteConfirmationDialog from '../components/VideoDeleteConfirmationDialog';
import DetectionResultsPanel from '../components/DetectionResultsPanel';
import DetectionControls from '../components/DetectionControls';

// Enhanced interfaces for dataset management
interface DatasetFilter {
  search?: string;
  projects?: string[];
  vruTypes?: VRUType[];
  hasAnnotations?: boolean;
  dateRange?: {
    start: string;
    end: string;
  };
  minDuration?: number;
  maxDuration?: number;
  status?: ('completed' | 'processing' | 'failed')[];
}

interface DatasetStats {
  totalVideos: number;
  totalAnnotations: number;
  totalDuration: number;
  avgAnnotationsPerVideo: number;
  detectionTypeBreakdown: DetectionTypeBreakdown;
  projectDistribution: { [key: string]: number };
  qualityMetrics: {
    highQuality: number;
    mediumQuality: number;
    lowQuality: number;
  };
  recentActivity: {
    date: string;
    videosAdded: number;
    annotationsAdded: number;
  }[];
}

interface VideoWithAnnotations extends VideoFile {
  groundTruthAnnotations: GroundTruthAnnotation[];
  annotationCount: number;
  detectionTypes: VRUType[];
  quality?: 'high' | 'medium' | 'low';
  projectName?: string;
  thumbnail?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`dataset-tabpanel-${index}`}
      aria-labelledby={`dataset-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

const DatasetVideos: React.FC = () => {

  // Core state
  const [videos, setVideos] = useState<VideoWithAnnotations[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filter and search state
  const [filter, setFilter] = useState<DatasetFilter>({});
  const [searchQuery, setSearchQuery] = useState('');

  // View state
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [activeTab, setActiveTab] = useState(0);
  const [sortBy, setSortBy] = useState<'name' | 'date' | 'annotations' | 'duration'>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Dialog state
  const [selectedVideo, setSelectedVideo] = useState<VideoWithAnnotations | null>(null);
  const [viewDialog, setViewDialog] = useState(false);
  const [exportDialog, setExportDialog] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState(false);
  const [deletingVideo, setDeletingVideo] = useState(false);
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

  // Statistics
  const [stats, setStats] = useState<DatasetStats>({
    totalVideos: 0,
    totalAnnotations: 0,
    totalDuration: 0,
    avgAnnotationsPerVideo: 0,
    detectionTypeBreakdown: {} as DetectionTypeBreakdown,
    projectDistribution: {},
    qualityMetrics: { highQuality: 0, mediumQuality: 0, lowQuality: 0 },
    recentActivity: [],
  });

  // Detection state - MANUAL ONLY (no automatic triggers)
  const [detectionState, setDetectionState] = useState<{
    detections: any[];
    error: string | null;
  }>({
    detections: [],
    error: null
  });

  const calculateStats = useCallback((videosData: VideoWithAnnotations[]) => {
    const totalVideos = videosData.length;
    const totalAnnotations = videosData.reduce((sum, v) => sum + v.annotationCount, 0);
    const totalDuration = videosData.reduce((sum, v) => sum + (v.duration || 0), 0);
    
    // Detection type breakdown
    const detectionTypeBreakdown: DetectionTypeBreakdown = {
      pedestrian: calculateDetectionMetrics(videosData, 'pedestrian'),
      cyclist: calculateDetectionMetrics(videosData, 'cyclist'),
      motorcyclist: calculateDetectionMetrics(videosData, 'motorcyclist'),
      wheelchair_user: calculateDetectionMetrics(videosData, 'wheelchair_user'),
      scooter_rider: calculateDetectionMetrics(videosData, 'scooter_rider'),
      overall: calculateDetectionMetrics(videosData, null), // Overall metrics
    };

    // Project distribution
    const projectDistribution = videosData.reduce((acc, video) => {
      const projectName = video.projectName || 'Unknown';
      acc[projectName] = (acc[projectName] || 0) + 1;
      return acc;
    }, {} as { [key: string]: number });

    // Quality metrics
    const qualityMetrics = videosData.reduce(
      (acc, video) => {
        if (video.quality === 'high') acc.highQuality++;
        else if (video.quality === 'medium') acc.mediumQuality++;
        else acc.lowQuality++;
        return acc;
      },
      { highQuality: 0, mediumQuality: 0, lowQuality: 0 }
    );

    // Recent activity (mock data - would come from API in real implementation)
    const recentActivity = Array.from({ length: 7 }, (_, i) => ({
      date: new Date(Date.now() - i * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      videosAdded: Math.floor(Math.random() * 5),
      annotationsAdded: Math.floor(Math.random() * 20),
    })).reverse();

    setStats({
      totalVideos,
      totalAnnotations,
      totalDuration,
      avgAnnotationsPerVideo: totalVideos > 0 ? totalAnnotations / totalVideos : 0,
      detectionTypeBreakdown,
      projectDistribution,
      qualityMetrics,
      recentActivity,
    });
  }, []);

  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      console.log('📈 Loading initial dataset data...');

      // First try to get videos from ground truth endpoint, then fallback to all videos
      let videosData: VideoFile[] = [];
      try {
        videosData = await getAvailableGroundTruthVideos();
        console.log('📈 Loaded ground truth videos:', videosData.length);
      } catch (groundTruthError) {
        console.warn('⚠️ Ground truth videos not available, trying all videos:', groundTruthError);
        try {
          const allVideosResponse = await getAllVideos();
          videosData = allVideosResponse.videos || [];
          console.log('📈 Loaded all videos:', videosData.length);
        } catch (allVideosError) {
          console.error('❌ Failed to load any videos:', allVideosError);
          videosData = [];
        }
      }
      
      // Also try to get projects for better project name resolution
      let projects: any[] = [];
      try {
        projects = await getProjects();
        console.log('📈 Loaded projects:', projects.length);
      } catch (projectsError) {
        console.warn('⚠️ Failed to load projects:', projectsError);
      }
      
      // Enhance videos with annotation data and project info
      const enhancedVideos = await Promise.all(
        videosData.map(async (video) => {
          try {
            const annotations = await getAnnotations(video.id);
            
            // Try to resolve project name
            let projectName = 'Unknown Project';
            if (video.projectId) {
              const project = projects.find(p => p.id === video.projectId);
              if (project) {
                projectName = project.name;
              }
            }
            
            return {
              ...video,
              groundTruthAnnotations: annotations,
              annotationCount: annotations.length,
              detectionTypes: [...new Set(annotations.map(a => a.vruType))],
              quality: assessVideoQuality(video),
              projectName,
              thumbnail: generateThumbnail(video),
            } as VideoWithAnnotations;
          } catch (err) {
            console.warn(`Failed to load annotations for video ${video.id}:`, err);
            
            // Try to resolve project name even if annotations fail
            let projectName = 'Unknown Project';
            if (video.projectId) {
              const project = projects.find(p => p.id === video.projectId);
              if (project) {
                projectName = project.name;
              }
            }
            
            return {
              ...video,
              groundTruthAnnotations: [],
              annotationCount: 0,
              detectionTypes: [],
              quality: 'medium' as const,
              projectName,
              thumbnail: generateThumbnail(video),
            } as VideoWithAnnotations;
          }
        })
      );

      console.log('📈 Enhanced videos:', enhancedVideos.length, 'with annotations');
      setVideos(enhancedVideos);
      calculateStats(enhancedVideos);

      if (enhancedVideos.length === 0) {
        setError('No videos found. Please upload some videos to see dataset information.');
      }

    } catch (err) {
      const apiError = err as ApiError;
      const errorMessage = apiError.message || 'Failed to load dataset information';
      setError(errorMessage);
      console.error('Failed to load dataset data:', err);
      
      // Set empty state but don't crash
      setVideos([]);
      calculateStats([]);
    } finally {
      setLoading(false);
    }
  }, [calculateStats]);

  // Load data on component mount
  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  const calculateDetectionMetrics = (videos: VideoWithAnnotations[], vruType: VRUType | null): DetectionTypeMetrics => {
    const relevantAnnotations = videos.flatMap(v => 
      vruType ? v.groundTruthAnnotations.filter(a => a.vruType === vruType) : v.groundTruthAnnotations
    );

    return {
      totalGroundTruth: relevantAnnotations.length,
      totalDetected: relevantAnnotations.filter(a => a.validated).length,
      truePositives: relevantAnnotations.filter(a => a.validated && !a.difficult).length,
      falsePositives: 0, // Would be calculated from test data
      falseNegatives: 0, // Would be calculated from test data
      precision: 0, // Would be calculated from test results
      recall: 0, // Would be calculated from test results
      f1Score: 0, // Would be calculated from test results
      averageConfidence: relevantAnnotations.reduce((sum, a) => sum + (a.boundingBox.confidence || 1.0), 0) / relevantAnnotations.length || 0,
    };
  };

  const assessVideoQuality = (video: VideoFile): 'high' | 'medium' | 'low' => {
    // Simple quality assessment based on available data
    const hasGoodDuration = (video.duration || 0) > 10 && (video.duration || 0) < 300;
    const hasReasonableSize = (video.size || video.fileSize || video.file_size || 0) > 1024 * 1024; // > 1MB
    
    if (hasGoodDuration && hasReasonableSize) return 'high';
    if (hasGoodDuration || hasReasonableSize) return 'medium';
    return 'low';
  };

  const generateThumbnail = (video: VideoFile): string => {
    // In a real implementation, this would generate or fetch video thumbnails
    // For now, return a placeholder
    return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'%3E%3Crect fill='%23f0f0f0' width='400' height='300'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='0.35em' fill='%23666' font-size='16'%3E${video.filename || video.name}%3C/text%3E%3C/svg%3E`;
  };

  // Filtered and sorted videos
  const filteredVideos = useMemo(() => {
    let filtered = videos.filter(video => {
      // Search filter
      if (searchQuery && !video.filename?.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !video.projectName?.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }

      // Project filter
      if (filter.projects?.length && !filter.projects.some(p => 
        video.projectName?.includes(p) || video.projectId === p)) {
        return false;
      }

      // VRU type filter
      if (filter.vruTypes?.length && !filter.vruTypes.some(type => 
        video.detectionTypes.includes(type))) {
        return false;
      }

      // Annotations filter
      if (filter.hasAnnotations !== undefined) {
        if (filter.hasAnnotations && video.annotationCount === 0) return false;
        if (!filter.hasAnnotations && video.annotationCount > 0) return false;
      }

      // Duration filter
      if (filter.minDuration && (video.duration || 0) < filter.minDuration) return false;
      if (filter.maxDuration && (video.duration || 0) > filter.maxDuration) return false;

      // Status filter
      if (filter.status?.length && !filter.status.includes(video.status as any)) {
        return false;
      }

      return true;
    });

    // Sort
    filtered.sort((a, b) => {
      let aValue: any, bValue: any;
      
      switch (sortBy) {
        case 'name':
          aValue = a.filename || a.name || '';
          bValue = b.filename || b.name || '';
          break;
        case 'date':
          aValue = new Date(a.createdAt || a.created_at || a.uploadedAt || 0).getTime();
          bValue = new Date(b.createdAt || b.created_at || b.uploadedAt || 0).getTime();
          break;
        case 'annotations':
          aValue = a.annotationCount;
          bValue = b.annotationCount;
          break;
        case 'duration':
          aValue = a.duration || 0;
          bValue = b.duration || 0;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [videos, searchQuery, filter, sortBy, sortOrder]);

  // Event handlers
  const handleVideoSelect = useCallback(async (video: VideoWithAnnotations) => {
    setSelectedVideo(video);
    setViewDialog(true);
  }, []);

  // Manual detection handlers (only triggered by user action)
  const handleDetectionStart = useCallback(() => {
    if (!selectedVideo) return;
    console.log('🔍 Manual detection started for video:', selectedVideo.id);
    // Reset detection state
    setDetectionState(prev => ({ ...prev, error: null }));
  }, [selectedVideo]);

  const handleDetectionComplete = useCallback(async (annotations: GroundTruthAnnotation[]) => {
    if (!selectedVideo) return;
    
    console.log('✅ Manual detection completed with', annotations.length, 'annotations');
    
    try {
      // Fetch latest detections from API
      const detections = await getVideoDetections(selectedVideo.id);
      setDetectionState(prev => ({ 
        ...prev, 
        detections,
        error: null 
      }));

      // Update the video's annotation data
      setSelectedVideo(prevVideo => {
        if (!prevVideo) return null;
        return {
          ...prevVideo,
          groundTruthAnnotations: [...prevVideo.groundTruthAnnotations, ...annotations],
          annotationCount: prevVideo.annotationCount + annotations.length,
          detectionTypes: [...new Set([...prevVideo.detectionTypes, ...annotations.map(a => a.vruType)])]
        };
      });

      // Also update the videos list
      setVideos(prevVideos => 
        prevVideos.map(v => 
          v.id === selectedVideo.id 
            ? {
                ...v,
                groundTruthAnnotations: [...v.groundTruthAnnotations, ...annotations],
                annotationCount: v.annotationCount + annotations.length,
                detectionTypes: [...new Set([...v.detectionTypes, ...annotations.map(a => a.vruType)])]
              }
            : v
        )
      );

      setSuccessMessage(`Detection completed! Found ${annotations.length} objects.`);
      
    } catch (error: any) {
      console.error('Failed to fetch latest detections:', error);
      setDetectionState(prev => ({ 
        ...prev, 
        error: `Failed to fetch detection results: ${error.message}` 
      }));
    }
  }, [selectedVideo]);

  const handleDetectionError = useCallback((error: string) => {
    console.error('🚨 Manual detection error:', error);
    setDetectionState(prev => ({ ...prev, error }));
  }, []);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, videoId: string) => {
    setMenuAnchorEl(event.currentTarget);
    setSelectedVideoId(videoId);
  };

  const handleMenuClose = () => {
    setMenuAnchorEl(null);
    setSelectedVideoId(null);
  };

  const handleDeleteVideo = useCallback(async (videoId: string) => {
    const video = videos.find(v => v.id === videoId);
    if (!video) return;

    setSelectedVideo(video);
    setDeleteDialog(true);
    handleMenuClose();
  }, [videos]);

  const confirmDeleteVideo = useCallback(async (videoId: string) => {
    const video = videos.find(v => v.id === videoId);
    if (!video) return;

    try {
      setDeletingVideo(true);
      await deleteVideo(videoId);
      
      // Remove video from local state
      setVideos(prev => prev.filter(v => v.id !== videoId));
      
      // Recalculate stats
      const updatedVideos = videos.filter(v => v.id !== videoId);
      calculateStats(updatedVideos);
      
      setSuccessMessage(`Successfully deleted ${video.filename || video.name}`);
    } catch (err) {
      const apiError = err as ApiError;
      setError(`Failed to delete video: ${apiError.message}`);
    } finally {
      setDeletingVideo(false);
    }
  }, [videos, calculateStats]);

  const handleExportDataset = useCallback(async (format: 'json' | 'coco' | 'yolo', videoIds?: string[]) => {
    try {
      const videosToExport = videoIds || filteredVideos.map(v => v.id);
      
      // Export annotations for each video and combine
      const exports = await Promise.all(
        videosToExport.map(async (videoId) => {
          try {
            return await exportAnnotations(videoId, format);
          } catch (err) {
            console.warn(`Failed to export annotations for video ${videoId}:`, err);
            return null;
          }
        })
      );

      // Create combined export file
      const validExports = exports.filter(e => e !== null);
      if (validExports.length > 0) {
        // For now, just download the first export
        // In a real implementation, you'd combine all exports
        const blob = validExports[0]!;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `dataset_export_${format}_${new Date().toISOString().split('T')[0]}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        
        setSuccessMessage(`Dataset exported as ${format.toUpperCase()}`);
      }
    } catch (err) {
      const apiError = err as ApiError;
      setError(`Failed to export dataset: ${apiError.message}`);
    }
  }, [filteredVideos]);

  const formatDuration = (seconds: number): string => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hrs > 0) return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getQualityColor = (quality?: 'high' | 'medium' | 'low') => {
    switch (quality) {
      case 'high': return 'success';
      case 'medium': return 'warning';
      case 'low': return 'error';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Skeleton variant="text" width={200} height={40} />
          <Skeleton variant="rectangular" width={120} height={36} />
        </Box>
        
        {/* Stats skeleton */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          {[1, 2, 3, 4].map((i) => (
            <Grid size={{ xs: 12, sm: 6, md: 3 }} key={i}>
              <Card>
                <CardContent>
                  <Skeleton variant="text" width="60%" height={24} />
                  <Skeleton variant="text" width="40%" height={48} />
                  <Skeleton variant="text" width="80%" height={16} />
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Video grid skeleton */}
        <Grid container spacing={2}>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={i}>
              <Card>
                <Skeleton variant="rectangular" height={180} />
                <CardContent>
                  <Skeleton variant="text" width="100%" />
                  <Skeleton variant="text" width="60%" />
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Dataset Videos
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Browse, analyze, and manage video datasets with manual detection controls
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={loadInitialData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<GetApp />}
            onClick={() => setExportDialog(true)}
            disabled={filteredVideos.length === 0}
          >
            Export Dataset
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert 
          severity="error" 
          sx={{ mb: 3 }}
          action={
            <Button color="inherit" size="small" onClick={loadInitialData}>
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
          <Tab label="Overview" icon={<Analytics />} />
          <Tab label="Video Library" icon={<VideoLibrary />} />
          <Tab label="Annotations" icon={<Label />} />
        </Tabs>
      </Box>

      {/* Overview Tab */}
      <TabPanel value={activeTab} index={0}>
        {/* Statistics Cards */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <VideoLibrary color="primary" sx={{ fontSize: 40 }} />
                  <Box>
                    <Typography variant="h4" component="div">
                      {stats.totalVideos}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Videos
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Label color="success" sx={{ fontSize: 40 }} />
                  <Box>
                    <Typography variant="h4" component="div">
                      {stats.totalAnnotations}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Annotations
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <TrendingUp color="info" sx={{ fontSize: 40 }} />
                  <Box>
                    <Typography variant="h4" component="div">
                      {formatDuration(stats.totalDuration)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Duration
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Assignment color="warning" sx={{ fontSize: 40 }} />
                  <Box>
                    <Typography variant="h4" component="div">
                      {stats.avgAnnotationsPerVideo.toFixed(1)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Avg Annotations/Video
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Detection Type Distribution */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Detection Type Distribution
                </Typography>
                <Stack spacing={2}>
                  {Object.entries(stats.detectionTypeBreakdown).filter(([key]) => key !== 'overall').map(([vruType, metrics]) => (
                    <Box key={vruType}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                          {vruType.replace('_', ' ')}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {metrics.totalGroundTruth}
                        </Typography>
                      </Box>
                      <LinearProgress 
                        variant="determinate" 
                        value={(metrics.totalGroundTruth / stats.totalAnnotations) * 100} 
                        sx={{ height: 8, borderRadius: 1 }}
                      />
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Project Distribution
                </Typography>
                <Stack spacing={2}>
                  {Object.entries(stats.projectDistribution).map(([project, count]) => (
                    <Box key={project}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2">{project}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {count} videos
                        </Typography>
                      </Box>
                      <LinearProgress 
                        variant="determinate" 
                        value={(count / stats.totalVideos) * 100} 
                        sx={{ height: 8, borderRadius: 1 }}
                      />
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Quality Metrics */}
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Video Quality Assessment
            </Typography>
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Box textAlign="center">
                  <Typography variant="h3" color="success.main">
                    {stats.qualityMetrics.highQuality}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    High Quality
                  </Typography>
                </Box>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Box textAlign="center">
                  <Typography variant="h3" color="warning.main">
                    {stats.qualityMetrics.mediumQuality}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Medium Quality
                  </Typography>
                </Box>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <Box textAlign="center">
                  <Typography variant="h3" color="error.main">
                    {stats.qualityMetrics.lowQuality}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Low Quality
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </TabPanel>

      {/* Video Library Tab */}
      <TabPanel value={activeTab} index={1}>
        {/* Search and Filter Controls */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                placeholder="Search videos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search />
                    </InputAdornment>
                  ),
                  endAdornment: searchQuery && (
                    <InputAdornment position="end">
                      <IconButton size="small" onClick={() => setSearchQuery('')}>
                        <Clear />
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Stack direction="row" spacing={2} justifyContent="flex-end">
                <Button
                  variant="outlined"
                  startIcon={<FilterList />}
                  onClick={() => {/* setShowFilterDialog(true) */}}
                >
                  Filter
                </Button>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Sort by</InputLabel>
                  <Select
                    value={sortBy}
                    label="Sort by"
                    onChange={(e) => setSortBy(e.target.value as any)}
                  >
                    <MenuItem value="date">Date</MenuItem>
                    <MenuItem value="name">Name</MenuItem>
                    <MenuItem value="annotations">Annotations</MenuItem>
                    <MenuItem value="duration">Duration</MenuItem>
                  </Select>
                </FormControl>
                <ButtonGroup>
                  <IconButton 
                    onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                    title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
                  >
                    {sortOrder === 'asc' ? '↑' : '↓'}
                  </IconButton>
                  <IconButton 
                    onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
                    title={viewMode === 'grid' ? 'List View' : 'Grid View'}
                  >
                    {viewMode === 'grid' ? <ViewList /> : <ViewModule />}
                  </IconButton>
                </ButtonGroup>
              </Stack>
            </Grid>
          </Grid>
          
          <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Showing {filteredVideos.length} of {videos.length} videos
            </Typography>
            {Object.keys(filter).length > 0 && (
              <Button
                size="small"
                startIcon={<Clear />}
                onClick={() => setFilter({})}
              >
                Clear Filters
              </Button>
            )}
          </Box>
        </Paper>

        {/* Video Grid/List */}
        {filteredVideos.length === 0 ? (
          <Box textAlign="center" py={6}>
            <VideoLibrary sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h5" color="text.secondary" gutterBottom>
              No videos found
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
              {videos.length === 0 
                ? 'No videos have been uploaded to the system yet.'
                : 'No videos match your current search and filter criteria.'
              }
            </Typography>
          </Box>
        ) : viewMode === 'grid' ? (
          <Grid container spacing={2}>
            {filteredVideos.map((video) => (
              <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={video.id}>
                <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <CardMedia
                    component="img"
                    height={180}
                    image={video.thumbnail || ''}
                    alt={video.filename || video.name || ''}
                    sx={{ 
                      bgcolor: 'grey.100',
                      cursor: 'pointer',
                      '&:hover': { opacity: 0.8 }
                    }}
                    onClick={() => handleVideoSelect(video)}
                  />
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                      <Typography variant="h6" component="div" noWrap sx={{ flexGrow: 1, mr: 1 }}>
                        {video.filename || video.name}
                      </Typography>
                      <IconButton
                        size="small"
                        onClick={(e) => handleMenuClick(e, video.id)}
                      >
                        <MoreVert />
                      </IconButton>
                    </Box>

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {video.projectName || 'No Project Assigned'}
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                      <Chip
                        label={`${video.annotationCount} annotations`}
                        size="small"
                        color={video.annotationCount > 0 ? 'primary' : 'default'}
                      />
                      <Chip
                        label={video.quality || 'unknown'}
                        size="small"
                        color={getQualityColor(video.quality) as any}
                      />
                      <Chip
                        label={formatDuration(video.duration || 0)}
                        size="small"
                        variant="outlined"
                      />
                    </Box>

                    {video.detectionTypes.length > 0 && (
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {video.detectionTypes.map((type) => (
                          <Chip
                            key={type}
                            label={type.replace('_', ' ')}
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: '0.7rem', height: 20 }}
                          />
                        ))}
                      </Box>
                    )}
                  </CardContent>
                  
                  <Box sx={{ p: 1 }}>
                    <Button
                      fullWidth
                      size="small"
                      startIcon={<Visibility />}
                      onClick={() => handleVideoSelect(video)}
                    >
                      View Details
                    </Button>
                  </Box>
                </Card>
              </Grid>
            ))}
          </Grid>
        ) : (
          <List>
            {filteredVideos.map((video, index) => (
              <React.Fragment key={video.id}>
                <ListItem>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Typography variant="subtitle1">{video.filename || video.name}</Typography>
                        <Chip
                          label={`${video.annotationCount} annotations`}
                          size="small"
                          color={video.annotationCount > 0 ? 'primary' : 'default'}
                        />
                        <Chip
                          label={video.quality || 'unknown'}
                          size="small"
                          color={getQualityColor(video.quality) as any}
                        />
                      </Box>
                    }
                    secondary={
                      <>
                        {video.projectName || 'No Project'} • {formatDuration(video.duration || 0)} • {formatFileSize(video.size || video.fileSize || video.file_size || 0)}
                        {video.detectionTypes.length > 0 && (
                          <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            {video.detectionTypes.map((type) => (
                              <Chip
                                key={type}
                                label={type.replace('_', ' ')}
                                size="small"
                                variant="outlined"
                                sx={{ fontSize: '0.7rem', height: 20 }}
                              />
                            ))}
                          </Box>
                        )}
                      </>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <IconButton onClick={() => handleVideoSelect(video)}>
                        <Visibility />
                      </IconButton>
                      <IconButton onClick={(e) => handleMenuClick(e, video.id)}>
                        <MoreVert />
                      </IconButton>
                    </Box>
                  </ListItemSecondaryAction>
                </ListItem>
                {index < filteredVideos.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        )}
      </TabPanel>

      {/* Annotations Tab */}
      <TabPanel value={activeTab} index={2}>
        <Typography variant="h6" gutterBottom>
          Annotation Summary
        </Typography>
        
        {stats.totalAnnotations > 0 ? (
          <Grid container spacing={3}>
            {Object.entries(stats.detectionTypeBreakdown).filter(([key]) => key !== 'overall').map(([vruType, metrics]) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={vruType}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" sx={{ textTransform: 'capitalize', mb: 2 }}>
                      {vruType.replace('_', ' ')}
                    </Typography>
                    <Stack spacing={1}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2">Total:</Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {metrics.totalGroundTruth}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2">Validated:</Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {metrics.totalDetected}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2">Avg Confidence:</Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {(metrics.averageConfidence * 100).toFixed(1)}%
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        ) : (
          <Box textAlign="center" py={6}>
            <Label sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h5" color="text.secondary" gutterBottom>
              No annotations yet
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Upload videos and create ground truth annotations to see annotation statistics here.
            </Typography>
          </Box>
        )}
      </TabPanel>

      {/* Context Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={Boolean(menuAnchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => {
          const video = filteredVideos.find(v => v.id === selectedVideoId);
          if (video) handleVideoSelect(video);
          handleMenuClose();
        }}>
          <Visibility sx={{ mr: 1 }} fontSize="small" />
          View Details
        </MenuItem>
        <MenuItem onClick={() => {
          if (selectedVideoId) {
            handleExportDataset('json', [selectedVideoId]);
          }
          handleMenuClose();
        }}>
          <Download sx={{ mr: 1 }} fontSize="small" />
          Export Annotations
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedVideoId) {
              handleDeleteVideo(selectedVideoId);
            }
          }}
          sx={{ color: 'error.main' }}
        >
          <Delete sx={{ mr: 1 }} fontSize="small" />
          Delete Video
        </MenuItem>
      </Menu>

      {/* Video Detail Dialog */}
      <Dialog 
        open={viewDialog} 
        onClose={() => setViewDialog(false)} 
        maxWidth="xl" 
        fullWidth
        PaperProps={{ sx: { height: '90vh' } }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">
              {selectedVideo?.filename || selectedVideo?.name}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip 
                label={`${selectedVideo?.annotationCount || 0} annotations`}
                color="primary"
                size="small"
              />
              <Chip 
                label={selectedVideo?.quality || 'unknown'}
                color={getQualityColor(selectedVideo?.quality) as any}
                size="small"
              />
            </Box>
          </Box>
        </DialogTitle>
        
        <DialogContent>
          {selectedVideo && (
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, lg: 8 }}>
                <EnhancedVideoPlayer
                  video={selectedVideo}
                  annotations={selectedVideo.groundTruthAnnotations}
                  onAnnotationSelect={() => {}}
                  onTimeUpdate={() => {}}
                  onCanvasClick={() => {}}
                  annotationMode={false}
                  selectedAnnotation={null}
                  frameRate={30}
                  autoRetry={true}
                  maxRetries={3}
                  showDetectionControls={false}
                />
              </Grid>
              <Grid size={{ xs: 12, lg: 4 }}>
                {/* Manual Detection Controls */}
                <DetectionControls
                  video={selectedVideo}
                  onDetectionStart={handleDetectionStart}
                  onDetectionComplete={handleDetectionComplete}
                  onDetectionError={handleDetectionError}
                  disabled={false}
                />

                <Typography variant="h6" gutterBottom>
                  Video Information
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }}>
                  <Stack spacing={1}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">Project:</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {selectedVideo.projectName || 'No Project Assigned'}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">Duration:</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {formatDuration(selectedVideo.duration || 0)}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">Size:</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {formatFileSize(selectedVideo.size || selectedVideo.fileSize || selectedVideo.file_size || 0)}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2">Quality:</Typography>
                      <Chip 
                        label={selectedVideo.quality || 'unknown'}
                        color={getQualityColor(selectedVideo.quality) as any}
                        size="small"
                      />
                    </Box>
                  </Stack>
                </Paper>

                <Typography variant="h6" gutterBottom>
                  Detection Types
                </Typography>
                <Paper sx={{ p: 2, mb: 2 }}>
                  {selectedVideo.detectionTypes.length > 0 ? (
                    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                      {selectedVideo.detectionTypes.map((type) => (
                        <Chip
                          key={type}
                          label={type.replace('_', ' ')}
                          variant="outlined"
                        />
                      ))}
                    </Stack>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No annotations available
                    </Typography>
                  )}
                </Paper>
                
                {/* Detection Results */}
                <DetectionResultsPanel 
                  detections={detectionState.detections}
                  loading={false}
                  error={detectionState.error}
                  isRunning={false}
                  onDetectionSelect={(detection) => {
                    console.log('Selected detection:', detection);
                    // TODO: Seek video to detection timestamp
                  }}
                />
              </Grid>
            </Grid>
          )}
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setViewDialog(false)}>Close</Button>
          <Button
            variant="contained"
            startIcon={<Download />}
            onClick={() => {
              if (selectedVideo) {
                handleExportDataset('json', [selectedVideo.id]);
              }
            }}
          >
            Export Annotations
          </Button>
        </DialogActions>
      </Dialog>

      {/* Export Dataset Dialog */}
      <Dialog open={exportDialog} onClose={() => setExportDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Export Dataset</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ mb: 3 }}>
            Export annotations from {filteredVideos.length} videos in your preferred format.
          </Typography>
          
          <Stack spacing={2}>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={() => {
                handleExportDataset('json');
                setExportDialog(false);
              }}
              fullWidth
            >
              Export as JSON
            </Button>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={() => {
                handleExportDataset('coco');
                setExportDialog(false);
              }}
              fullWidth
            >
              Export as COCO
            </Button>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={() => {
                handleExportDataset('yolo');
                setExportDialog(false);
              }}
              fullWidth
            >
              Export as YOLO
            </Button>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExportDialog(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>

      {/* Video Delete Confirmation Dialog */}
      <VideoDeleteConfirmationDialog
        open={deleteDialog}
        onClose={() => setDeleteDialog(false)}
        video={selectedVideo}
        onConfirm={confirmDeleteVideo}
        loading={deletingVideo}
        projectsUsingVideo={selectedVideo?.projectName ? [selectedVideo.projectName] : []}
        annotationCount={selectedVideo?.annotationCount || 0}
        testSessionCount={0} // Would need to be fetched from API
      />

      {/* Success/Error Snackbars */}
      <Snackbar
        open={!!successMessage}
        autoHideDuration={6000}
        onClose={() => setSuccessMessage(null)}
      >
        <Alert severity="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default DatasetVideos;