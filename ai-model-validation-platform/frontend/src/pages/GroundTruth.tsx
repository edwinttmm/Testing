import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams } from 'react-router-dom';
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
  Tab,
  Tabs,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Paper,
  Tooltip,
} from '@mui/material';
import {
  CloudUpload,
  CheckCircle,
  HourglassEmpty,
  Error as ErrorIcon,
  Visibility,
  Delete,
  Cancel,
  Edit,
  Save,
  GetApp,
  Publish,
  CropFree,
} from '@mui/icons-material';
import { 
  VideoFile, 
 
  VRUType, 
  GroundTruthAnnotation, 
  AnnotationSession,
  BoundingBox,
 
} from '../services/types';
import { apiService, getVideoDetections } from '../services/api';
import { getErrorMessage } from '../utils/errorUtils';
import { detectionService, DetectionConfig } from '../services/detectionService';
// Removed useDetectionWebSocket - using manual detection only
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';
import AnnotationTools, { AnnotationTool } from '../components/AnnotationTools';
import TemporalAnnotationInterface from '../components/TemporalAnnotationInterface';
import DetectionResultsPanel from '../components/DetectionResultsPanel';
import DetectionControls from '../components/DetectionControls';
import { 
  detectionIdManager, 
  generateDetectionId, 
  createDetectionTracker,
  getDetectionStatistics 
} from '../utils/detectionIdManager';

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
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
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
  // State management
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [uploadingVideos, setUploadingVideos] = useState<UploadingVideo[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoFile | null>(null);
  const [annotations, setAnnotations] = useState<GroundTruthAnnotation[]>([]);
  const [selectedAnnotation, setSelectedAnnotation] = useState<GroundTruthAnnotation | null>(null);
  const [annotationSession, setAnnotationSession] = useState<AnnotationSession | null>(null);
  
  // UI state
  const [activeTab, setActiveTab] = useState(0);
  const [uploadDialog, setUploadDialog] = useState(false);
  const [viewDialog, setViewDialog] = useState(false);
  const [annotationMode, setAnnotationMode] = useState(false);
  const [showAnnotations, setShowAnnotations] = useState(true);
  const [selectedTool, setSelectedTool] = useState<AnnotationTool>({
    id: 'default',
    name: 'Rectangle',
    type: 'rectangle',
    icon: <CropFree />,
    cursor: 'crosshair'
  });
  const [selectedVRUType, setSelectedVRUType] = useState<VRUType>('pedestrian');
  
  // Video player state
  const [currentFrame, setCurrentFrame] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [totalFrames, setTotalFrames] = useState(0);
  const [frameRate] = useState(30); // Default frame rate
  
  // Error and success handling
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [uploadErrors, setUploadErrors] = useState<UploadError[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  
  // Detection pipeline state (manual control only)
  const [detectionResults, setDetectionResults] = useState<GroundTruthAnnotation[]>([]);
  const [detectionError, setDetectionError] = useState<string | null>(null);
  const [isDetectionRunning, setIsDetectionRunning] = useState(false);
  
  // File input ref for upload
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Manual detection only - no WebSocket or automatic detection

  // Get project ID from URL params
  const { id: urlProjectId } = useParams<{ id: string }>();
  
  // Dynamic project ID state that can be derived from video context
  const [projectId, setProjectId] = useState<string | null>(urlProjectId || null);
  const [projectContext, setProjectContext] = useState<'url' | 'video' | 'central' | null>(urlProjectId ? 'url' : null);

  // Utility function to get the best available project context for operations
  const getProjectContextForOperation = useCallback((operationVideo?: VideoFile) => {
    const videoProjectId = operationVideo?.projectId || selectedVideo?.projectId;
    
    // Priority: URL project ID > Video's project ID > Current derived project ID
    const contextualProjectId = urlProjectId || videoProjectId || projectId;
    const source = urlProjectId ? 'url' : videoProjectId ? 'video' : projectId ? 'derived' : 'none';
    
    return { projectId: contextualProjectId, source };
  }, [urlProjectId, selectedVideo, projectId]);

  // Helper function to determine project context from videos
  const deriveProjectContext = useCallback((videos: VideoFile[]) => {
    if (videos.length === 0) return null;
    
    // Get unique project IDs from videos
    const projectIds = [...new Set(videos.map(v => v.projectId).filter(Boolean))];
    
    // If all videos belong to the same project, use that project ID
    if (projectIds.length === 1 && projectIds[0]) {
      return projectIds[0];
    }
    
    // If videos belong to multiple projects or no project, use central store approach
    return null;
  }, []);

  // Smart video loading that works with or without project context
  const loadVideos = useCallback(async () => {
    
    try {
      setError(null);
      let videoList: VideoFile[];
      
      if (projectId && projectContext === 'url') {
        // Load videos for specific project from URL
        videoList = await apiService.getVideos(projectId);
      } else {
        // Load all videos from central store and derive project context
        const { videos: allVideos } = await apiService.getAllVideos(false, 0, 1000);
        videoList = allVideos;
        
        // Try to derive project context from videos
        const derivedProjectId = deriveProjectContext(allVideos);
        if (derivedProjectId && !projectId) {
          setProjectId(derivedProjectId);
          setProjectContext('video');
        } else if (!derivedProjectId && !projectId) {
          // Use central store approach for mixed/unassigned videos
          setProjectContext('central');
        }
      }
      
      setVideos(videoList);
    } catch (err) {
      const errorMsg = getErrorMessage(err, 'Backend connection failed');
      setError(`Failed to load videos: ${errorMsg}`);
      
      console.error('Error loading videos:', errorMsg);
    }
  }, [projectId, projectContext, deriveProjectContext]);

  const loadAnnotations = useCallback(async (videoId: string, videoProjectId?: string) => {
    try {
      // Use video's project context if available, otherwise use current project context
      
      const annotationList = await apiService.getAnnotations(videoId);
      setAnnotations(annotationList);
      
      // Import annotations into detection ID manager
      detectionIdManager.clear();
      annotationList.forEach(annotation => {
        createDetectionTracker(
          annotation.detectionId,
          annotation.vruType,
          annotation.frameNumber,
          annotation.timestamp,
          annotation.boundingBox,
          1.0
        );
      });
    } catch (err) {
      console.error('Error loading annotations for video:', videoId, err);
      setAnnotations([]);
    }
  }, []);

  const uploadFiles = useCallback(async (files: File[]) => {
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
    
    // Upload files with project context awareness
    const uploadPromises = newUploadingVideos.map(async (uploadingVideo) => {
      
      try {
        // Upload to project if we have project context, otherwise use central store
        const uploadedVideo = projectId && projectContext === 'url'
          ? await apiService.uploadVideo(
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
            )
          : await apiService.uploadVideoCentral(
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
        const errorMsg = getErrorMessage(err, 'Backend connection failed - upload failed');
        
        setUploadingVideos(prev => 
          prev.map(v => 
            v.id === uploadingVideo.id 
              ? { ...v, status: 'failed', error: `${errorMsg} (${uploadingVideo.file.type})` }
              : v
          )
        );
        
        // Provide more specific error guidance
        let userFriendlyError = errorMsg;
        if (errorMsg.includes('Failed to upload video to central store')) {
          userFriendlyError = `Server storage issue - please try again later or contact administrator. The central video store is currently experiencing problems.`;
        }
        
        setUploadErrors(prev => [...prev, {
          message: `${userFriendlyError} - File: ${uploadingVideo.name} (${uploadingVideo.file.type}, ${formatFileSize(uploadingVideo.file.size)})`,
          fileName: uploadingVideo.name
        }]);
        
        console.error('Upload failed:', errorMsg);
      }
    });
    
    await Promise.allSettled(uploadPromises);
  }, [projectId, projectContext]); // Depends on project context

  // Load videos on component mount (optimized dependencies)
  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  // Manual detection mode - no automatic connections or cleanup needed

  // Load annotations when video is selected - use video's project context
  useEffect(() => {
    if (selectedVideo) {
      // Pass the video's project ID for proper context
      loadAnnotations(selectedVideo.id, selectedVideo.projectId);
      setTotalFrames(Math.floor((selectedVideo.duration || 0) * frameRate));
      
      // Update project context if we didn't have one before
      if (!projectId && selectedVideo.projectId) {
        setProjectId(selectedVideo.projectId);
        setProjectContext('video');
      }
    }
  }, [selectedVideo, frameRate, loadAnnotations, projectId]);

  const createAnnotationSession = useCallback(async (videoId: string) => {
    try {
      // Get the appropriate project context for this operation
      const video = videos.find(v => v.id === videoId) || selectedVideo;
      const { projectId: contextualProjectId, source } = getProjectContextForOperation(video || undefined);
      
      if (!contextualProjectId) {
        throw new Error('No project context available for annotation session. Please ensure the video is properly associated with a project.');
      }
      
      const session = await apiService.createAnnotationSession(videoId, contextualProjectId);
      setAnnotationSession(session);
      setSuccessMessage(`Annotation session started (using ${source} project context)`);
    } catch (err) {
      setError(`Failed to create annotation session: ${getErrorMessage(err)}`);
    }
  }, [videos, selectedVideo, getProjectContextForOperation]);

  // Annotation handlers
  const handleAnnotationCreate = useCallback(async (
    vruType: VRUType, 
    boundingBox?: Partial<BoundingBox>
  ) => {
    if (!selectedVideo) return;

    const detectionId = generateDetectionId(vruType, currentFrame);
    const annotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'> = {
      videoId: selectedVideo.id,
      detectionId,
      frameNumber: currentFrame,
      timestamp: currentTime,
      vruType,
      boundingBox: boundingBox ? { 
        x: boundingBox.x || 100,
        y: boundingBox.y || 100,
        width: boundingBox.width || 50,
        height: boundingBox.height || 100,
        label: vruType, 
        confidence: 1.0 
      } : { 
        x: 100, 
        y: 100, 
        width: 50, 
        height: 100, 
        label: vruType, 
        confidence: 1.0 
      },
      occluded: false,
      truncated: false,
      difficult: false,
      validated: false,
    };

    try {
      const newAnnotation = await apiService.createAnnotation(selectedVideo.id, annotation);
      setAnnotations(prev => [...prev, newAnnotation]);
      setSelectedAnnotation(newAnnotation);
      
      // Add to detection tracker
      createDetectionTracker(
        newAnnotation.detectionId,
        newAnnotation.vruType,
        newAnnotation.frameNumber,
        newAnnotation.timestamp,
        newAnnotation.boundingBox,
        1.0
      );
      
      setSuccessMessage(`Created ${vruType} annotation`);
    } catch (err) {
      setError(`Failed to create annotation: ${getErrorMessage(err)}`);
    }
  }, [selectedVideo, currentFrame, currentTime]);

  const handleAnnotationUpdate = useCallback(async (updates: Partial<GroundTruthAnnotation>) => {
    if (!selectedAnnotation) return;

    try {
      const updatedAnnotation = await apiService.updateAnnotation(selectedAnnotation.id, updates);
      setAnnotations(prev => 
        prev.map(ann => ann.id === selectedAnnotation.id ? updatedAnnotation : ann)
      );
      setSelectedAnnotation(updatedAnnotation);
      setSuccessMessage('Annotation updated');
    } catch (err) {
      setError(`Failed to update annotation: ${getErrorMessage(err)}`);
    }
  }, [selectedAnnotation]);

  // Wrapper functions for TemporalAnnotationInterface
  const handleTemporalAnnotationCreate = useCallback(async (annotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'>) => {
    await handleAnnotationCreate(annotation.vruType, annotation.boundingBox);
  }, [handleAnnotationCreate]);

  const handleTemporalAnnotationUpdate = useCallback(async (id: string, updates: Partial<GroundTruthAnnotation>) => {
    // Find the annotation and set it as selected, then update
    const annotation = annotations.find(ann => ann.id === id);
    if (annotation) {
      setSelectedAnnotation(annotation);
      await handleAnnotationUpdate(updates);
    }
  }, [annotations, handleAnnotationUpdate]);

  const handleAnnotationDelete = useCallback(async (annotationId: string) => {
    try {
      await apiService.deleteAnnotation(annotationId);
      setAnnotations(prev => prev.filter(ann => ann.id !== annotationId));
      if (selectedAnnotation?.id === annotationId) {
        setSelectedAnnotation(null);
      }
      setSuccessMessage('Annotation deleted');
    } catch (err) {
      setError(`Failed to delete annotation: ${getErrorMessage(err)}`);
    }
  }, [selectedAnnotation]);

  const handleAnnotationValidate = useCallback(async (annotationId: string, validated: boolean) => {
    try {
      const updatedAnnotation = await apiService.validateAnnotation(annotationId, validated);
      setAnnotations(prev => 
        prev.map(ann => ann.id === annotationId ? updatedAnnotation : ann)
      );
      if (selectedAnnotation?.id === annotationId) {
        setSelectedAnnotation(updatedAnnotation);
      }
      setSuccessMessage(`Annotation ${validated ? 'validated' : 'marked as pending'}`);
    } catch (err) {
      setError(`Failed to validate annotation: ${getErrorMessage(err)}`);
    }
  }, [selectedAnnotation]);

  // Video player handlers
  const handleTimeUpdate = useCallback((time: number, frame: number) => {
    setCurrentTime(time);
    setCurrentFrame(frame);
  }, []);

  const handleCanvasClick = useCallback((x: number, y: number, frame: number, timestamp: number) => {
    if (!annotationMode) return;
    
    handleAnnotationCreate(selectedVRUType, { x, y, width: 50, height: 100 });
  }, [annotationMode, selectedVRUType, handleAnnotationCreate]);

  const handleFrameChange = useCallback((frame: number) => {
    setCurrentFrame(frame);
    setCurrentTime(frame / frameRate);
  }, [frameRate]);

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
  }, [uploadFiles]);

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
      setError(getErrorMessage(err, 'Failed to delete video'));
    }
  };

  const cancelUpload = (uploadId: string) => {
    setUploadingVideos(prev => prev.filter(v => v.id !== uploadId));
  };

  const handleViewVideo = async (video: VideoFile) => {
    setSelectedVideo(video);
    setViewDialog(true);
    setActiveTab(0); // Default to video player tab
    
    // Clear previous detection state
    setDetectionError(null);
    setDetectionResults([]);
    setAnnotations([]);
    setIsDetectionRunning(false);
    
    // Load existing annotations (no automatic detection)
    try {
      const existingAnnotations = await apiService.getAnnotations(video.id);
      if (existingAnnotations && existingAnnotations.length > 0) {
        setAnnotations(existingAnnotations);
        setDetectionResults(existingAnnotations);
        console.log(`Loaded ${existingAnnotations.length} existing annotations`);
      } else {
        console.log('No existing annotations found. Use detection controls to analyze this video.');
      }
    } catch (err) {
      console.warn('Could not load existing annotations:', err);
    }
  };

  // Start annotation session with improved project context handling
  const handleStartAnnotation = useCallback(async (video: VideoFile) => {
    try {
      // Check for project context before starting annotation
      const { projectId: contextualProjectId, source } = getProjectContextForOperation(video);
      
      if (!contextualProjectId) {
        setError('Cannot start annotation session: Video is not associated with a project. Please assign the video to a project first.');
        return;
      }
      
      setSelectedVideo(video);
      await createAnnotationSession(video.id);
      setAnnotationMode(true);
      setViewDialog(true);
      setActiveTab(1); // Switch to annotation tab
      
      if (source === 'video' && !projectId) {
        // Update global project context if we derived it from video
        setProjectId(contextualProjectId);
        setProjectContext('video');
      }
    } catch (err) {
      setError(`Failed to start annotation session: ${getErrorMessage(err)}`);
    }
  }, [createAnnotationSession, getProjectContextForOperation, projectId]);

  // Export annotations
  // Detection control handlers
  const handleDetectionStart = useCallback(() => {
    setIsDetectionRunning(true);
    setDetectionError(null);
    setDetectionResults([]);
  }, []);

  const handleDetectionComplete = useCallback((newAnnotations: GroundTruthAnnotation[]) => {
    setIsDetectionRunning(false);
    setAnnotations(newAnnotations);
    setDetectionResults(newAnnotations);
    setSuccessMessage(`Detection completed! Found ${newAnnotations.length} objects.`);
  }, []);

  const handleDetectionError = useCallback((error: string) => {
    setIsDetectionRunning(false);
    setDetectionError(error);
    setError(`Detection failed: ${error}`);
  }, []);

  const handleExportAnnotations = useCallback(async (format: 'coco' | 'yolo' | 'pascal' | 'json') => {
    if (!selectedVideo) return;

    try {
      const blob = await apiService.exportAnnotations(selectedVideo.id, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `${selectedVideo.filename}_annotations.${format === 'json' ? 'json' : format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      setSuccessMessage(`Annotations exported as ${format.toUpperCase()}`);
    } catch (err) {
      setError(`Failed to export annotations: ${getErrorMessage(err)}`);
    }
  }, [selectedVideo]);

  const getStatusIcon = (status: VideoFile['status'] | UploadingVideo['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'processing':
      case 'uploading':
        return <HourglassEmpty color="warning" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      default:
        return <HourglassEmpty color="info" />;
    }
  };

  // Memoize detection statistics to prevent recalculation on every render
  const detectionStats = useMemo(() => getDetectionStatistics(), []);

  // Memoize combined video list
  const allVideos = useMemo(() => [...uploadingVideos, ...videos], [uploadingVideos, videos]);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4">Ground Truth Management</Typography>
          {projectContext && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {projectContext === 'url' && `Project: ${projectId} (from URL)`}
              {projectContext === 'video' && `Project: ${projectId} (derived from videos)`}
              {projectContext === 'central' && 'Central video store (mixed/unassigned videos)'}
            </Typography>
          )}
        </Box>
        <Button
          variant="contained"
          startIcon={<CloudUpload />}
          onClick={() => setUploadDialog(true)}
        >
          Upload Video
        </Button>
      </Box>

      {/* Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 3 }}>
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
        
        <Grid size={{ xs: 12, md: 3 }}>
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
        
        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Total Annotations
              </Typography>
              <Typography variant="h3" color="success.main">
                {detectionStats.totalDetections}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Ground truth detections
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Validated
              </Typography>
              <Typography variant="h3" color="info.main">
                {detectionStats.validatedDetections}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Validated annotations
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* VRU Type Distribution */}
      {detectionStats.totalDetections > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Detection Distribution
            </Typography>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              {Object.entries(detectionStats.detectionsByType).map(([vruType, count]) => (
                <Chip
                  key={vruType}
                  label={`${vruType}: ${count}`}
                  color={count > 0 ? 'primary' : 'default'}
                  variant={count > 0 ? 'filled' : 'outlined'}
                />
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      {/* Video Library */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Video Library
          </Typography>
          
          <List>
            {/* Show uploading videos first */}
            {uploadingVideos.map((video) => (
              <Box key={video.id}>
                <ListItem divider>
                  <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
                    {getStatusIcon(video.status)}
                  </Box>
                  
                  <ListItemText
                    primary={video.name}
                    secondary={`Size: ${video.size} • Status: ${video.status}`}
                  />
                  
                  <ListItemSecondaryAction>
                    {video.status === 'uploading' && (
                      <IconButton size="small" onClick={() => cancelUpload(video.id)}>
                        <Cancel />
                      </IconButton>
                    )}
                  </ListItemSecondaryAction>
                </ListItem>
                
                {/* Progress indicators outside ListItem to avoid HTML nesting issues */}
                {video.status === 'uploading' && (
                  <Box sx={{ pl: 7, pb: 2 }}>
                    <Typography variant="caption">Uploading... {video.progress}%</Typography>
                    <LinearProgress variant="determinate" value={video.progress} sx={{ mt: 0.5 }} />
                  </Box>
                )}
                {video.status === 'processing' && (
                  <Box sx={{ pl: 7, pb: 2 }}>
                    <Typography variant="caption">Processing ground truth...</Typography>
                    <LinearProgress sx={{ mt: 0.5 }} />
                  </Box>
                )}
                {video.status === 'failed' && (
                  <Box sx={{ pl: 7, pb: 2 }}>
                    <Alert severity="error">
                      {video.error}
                    </Alert>
                  </Box>
                )}
              </Box>
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
                    <>
                      Size: {formatFileSize(video.file_size || video.fileSize || video.size || 0)} • Duration: {formatDuration(video.duration)} • Uploaded: {new Date(video.created_at || video.createdAt || video.uploadedAt).toLocaleDateString()}
                      {video.projectId && (
                        <>
                          <br />
                          <Typography variant="caption" color="primary">
                            Project: {video.projectId.slice(0, 8)}...
                          </Typography>
                        </>
                      )}
                      {!video.projectId && projectContext === 'central' && (
                        <>
                          <br />
                          <Typography variant="caption" color="text.secondary">
                            Unassigned to project
                          </Typography>
                        </>
                      )}
                      {video.status === 'processing' && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="caption">Processing ground truth...</Typography>
                          <LinearProgress sx={{ mt: 0.5 }} />
                        </Box>
                      )}
                      {(video.status === 'completed' || video.groundTruthGenerated) && (
                        <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                          <Chip
                            label="Ready for annotation"
                            size="small"
                            color="success"
                          />
                          {!video.projectId && (
                            <Chip
                              label="No project context"
                              size="small"
                              color="warning"
                              variant="outlined"
                            />
                          )}
                        </Box>
                      )}
                    </>
                  }
                />
                
                <ListItemSecondaryAction>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    {video.status === 'completed' && (
                      <Tooltip title={
                        video.projectId || projectId 
                          ? "Start Annotation" 
                          : "Cannot annotate: Video not associated with a project"
                      }>
                        <span> {/* Span wrapper needed for disabled button tooltips */}
                          <IconButton 
                            size="small"
                            disabled={!video.projectId && !projectId}
                            onClick={() => handleStartAnnotation(video)}
                          >
                            <Edit />
                          </IconButton>
                        </span>
                      </Tooltip>
                    )}
                    <Tooltip title="View Details">
                      <IconButton 
                        size="small" 
                        onClick={() => handleViewVideo(video)}
                      >
                        <Visibility />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete Video">
                      <IconButton 
                        size="small" 
                        onClick={() => handleDeleteVideo(video.id)}
                      >
                        <Delete />
                      </IconButton>
                    </Tooltip>
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

      {/* Upload Dialog */}
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
            After upload, you can create ground truth annotations using our annotation tools.
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

      {/* Video Annotation Dialog */}
      <Dialog 
        open={viewDialog} 
        onClose={() => {
          setViewDialog(false);
          setAnnotationMode(false);
          setSelectedVideo(null);
          setSelectedAnnotation(null);
        }} 
        maxWidth="xl" 
        fullWidth
        PaperProps={{
          sx: { height: '90vh' }
        }}
      >
        <DialogTitle>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              {selectedVideo?.filename || selectedVideo?.name} - Ground Truth Annotation
            </Typography>
            <Stack direction="row" spacing={1}>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>VRU Type</InputLabel>
                <Select
                  value={selectedVRUType}
                  label="VRU Type"
                  onChange={(e) => setSelectedVRUType(e.target.value as VRUType)}
                >
                  <MenuItem value="pedestrian">Pedestrian</MenuItem>
                  <MenuItem value="cyclist">Cyclist</MenuItem>
                  <MenuItem value="motorcyclist">Motorcyclist</MenuItem>
                  <MenuItem value="wheelchair_user">Wheelchair User</MenuItem>
                  <MenuItem value="scooter_rider">Scooter Rider</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          </Stack>
        </DialogTitle>
        
        <DialogContent sx={{ p: 0 }}>
          <Box sx={{ width: '100%' }}>
            <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
              <Tab label="Video Player" />
              <Tab label="Annotation Tools" />
              <Tab label="Timeline" />
              <Tab label="Export" />
            </Tabs>

            <TabPanel value={activeTab} index={0}>
              {selectedVideo && (
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, lg: 8 }}>
                    {/* Detection Controls */}
                    <DetectionControls
                      video={selectedVideo}
                      onDetectionStart={handleDetectionStart}
                      onDetectionComplete={handleDetectionComplete}
                      onDetectionError={handleDetectionError}
                      disabled={false}
                    />
                    
                    <VideoAnnotationPlayer
                      video={selectedVideo}
                      annotations={annotations}
                      onAnnotationSelect={setSelectedAnnotation}
                      onTimeUpdate={handleTimeUpdate}
                      onCanvasClick={handleCanvasClick}
                      annotationMode={annotationMode}
                      selectedAnnotation={selectedAnnotation}
                      frameRate={frameRate}
                    />
                  </Grid>
                  <Grid size={{ xs: 12, lg: 4 }}>
                    <Typography variant="h6" gutterBottom>
                      Video Information
                    </Typography>
                    <Paper sx={{ p: 2, mb: 2 }}>
                      <Typography variant="body2">
                        <strong>Duration:</strong> {selectedVideo.duration?.toFixed(2)}s<br/>
                        <strong>Current Time:</strong> {currentTime.toFixed(2)}s<br/>
                        <strong>Current Frame:</strong> {currentFrame} / {totalFrames}<br/>
                        <strong>Frame Rate:</strong> {frameRate} fps
                      </Typography>
                    </Paper>
                    
                    <Typography variant="h6" gutterBottom>
                      Detection Results
                    </Typography>
                    <DetectionResultsPanel
                      detections={detectionResults.map(annotation => ({
                        id: annotation.id,
                        timestamp: annotation.timestamp,
                        frameNumber: annotation.frameNumber,
                        confidence: annotation.boundingBox.confidence || 1.0,
                        classLabel: annotation.vruType,
                        vruType: annotation.vruType,
                        boundingBox: annotation.boundingBox,
                      }))}
                      onDetectionSelect={(detection) => {
                        const annotation = annotations.find(a => a.id === detection.id);
                        if (annotation) {
                          setSelectedAnnotation(annotation);
                          setCurrentFrame(annotation.frameNumber);
                          setCurrentTime(annotation.timestamp);
                        }
                      }}
                      loading={false}
                      error={detectionError}
                      isRunning={isDetectionRunning}
                    />
                    
                    <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                      Session Stats
                    </Typography>
                    <Paper sx={{ p: 2 }}>
                      <Typography variant="body2">
                        <strong>Total Annotations:</strong> {annotations.length}<br/>
                        <strong>Validated:</strong> {annotations.filter(a => a.validated).length}<br/>
                        <strong>Current Frame:</strong> {annotations.filter(a => a.frameNumber === currentFrame).length}<br/>
                        <strong>Mode:</strong> <span style={{ color: '#4caf50' }}>
                          🎮 Manual Detection Only
                        </span>
                        {annotations.length === 0 && !isDetectionRunning && (
                          <>
                            <br/><em style={{ color: '#666' }}>💡 Use detection controls above to analyze this video.</em>
                          </>
                        )}
                      </Typography>
                    </Paper>
                  </Grid>
                </Grid>
              )}
            </TabPanel>

            <TabPanel value={activeTab} index={1}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, lg: 8 }}>
                  {selectedVideo && (
                    <VideoAnnotationPlayer
                      video={selectedVideo}
                      annotations={annotations}
                      onAnnotationSelect={setSelectedAnnotation}
                      onTimeUpdate={handleTimeUpdate}
                      onCanvasClick={handleCanvasClick}
                      annotationMode={annotationMode}
                      selectedAnnotation={selectedAnnotation}
                      frameRate={frameRate}
                    />
                  )}
                </Grid>
                <Grid size={{ xs: 12, lg: 4 }}>
                  <AnnotationTools
                    selectedAnnotation={selectedAnnotation}
                    onAnnotationUpdate={handleAnnotationUpdate}
                    onAnnotationDelete={handleAnnotationDelete}
                    onAnnotationValidate={handleAnnotationValidate}
                    onToolSelect={setSelectedTool}
                    selectedTool={selectedTool}
                    onCreateAnnotation={handleAnnotationCreate}
                    annotationMode={annotationMode}
                    onAnnotationModeToggle={setAnnotationMode}
                    showAnnotations={showAnnotations}
                    onShowAnnotationsToggle={setShowAnnotations}
                    frameNumber={currentFrame}
                    timestamp={currentTime}
                  />
                </Grid>
              </Grid>
            </TabPanel>

            <TabPanel value={activeTab} index={2}>
              <TemporalAnnotationInterface
                annotations={annotations}
                currentFrame={currentFrame}
                totalFrames={totalFrames}
                frameRate={frameRate}
                duration={selectedVideo?.duration || 0}
                onFrameChange={handleFrameChange}
                onAnnotationCreate={handleTemporalAnnotationCreate}
                onAnnotationUpdate={handleTemporalAnnotationUpdate}
                onAnnotationDelete={handleAnnotationDelete}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                isPlaying={isPlaying}
                selectedVRUType={selectedVRUType}
              />
            </TabPanel>

            <TabPanel value={activeTab} index={3}>
              <Box sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Export Annotations
                </Typography>
                <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
                  <Button 
                    variant="outlined" 
                    startIcon={<GetApp />}
                    onClick={() => handleExportAnnotations('json')}
                  >
                    Export JSON
                  </Button>
                  <Button 
                    variant="outlined" 
                    startIcon={<GetApp />}
                    onClick={() => handleExportAnnotations('coco')}
                  >
                    Export COCO
                  </Button>
                  <Button 
                    variant="outlined" 
                    startIcon={<GetApp />}
                    onClick={() => handleExportAnnotations('yolo')}
                  >
                    Export YOLO
                  </Button>
                  <Button 
                    variant="outlined" 
                    startIcon={<GetApp />}
                    onClick={() => handleExportAnnotations('pascal')}
                  >
                    Export Pascal VOC
                  </Button>
                </Stack>

                <Typography variant="h6" gutterBottom>
                  Import Annotations
                </Typography>
                <Button
                  variant="outlined"
                  startIcon={<Publish />}
                  onClick={() => fileInputRef.current?.click()}
                >
                  Import Annotations
                </Button>
              </Box>
            </TabPanel>
          </Box>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setViewDialog(false)}>Close</Button>
          {annotationSession && (
            <Button 
              variant="contained" 
              startIcon={<Save />}
              onClick={() => {
                setSuccessMessage('Annotation session saved');
              }}
            >
              Save Session
            </Button>
          )}
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