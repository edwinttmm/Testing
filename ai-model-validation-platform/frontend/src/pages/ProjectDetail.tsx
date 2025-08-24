import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  Tab,
  Tabs,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Skeleton,
} from '@mui/material';
import {
  PlayArrow,
  VideoLibrary,
  Assessment,
  Edit,
  Delete,
  Link,
} from '@mui/icons-material';
import { apiService, getLinkedVideos, linkVideosToProject, unlinkVideoFromProject, deleteVideo } from '../services/api';
import { Project, VideoFile, TestSession } from '../services/types';
import VideoSelectionDialog from '../components/VideoSelectionDialog';
import VideoDeleteConfirmationDialog from '../components/VideoDeleteConfirmationDialog';
import UnlinkVideoConfirmationDialog from '../components/UnlinkVideoConfirmationDialog';
import { getErrorMessage } from '../utils/errorUtils';

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
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const ProjectDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tabValue, setTabValue] = useState(0);
  const [project, setProject] = useState<Project | null>(null);
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [testSessions, setTestSessions] = useState<TestSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Removed unused error state variables
  const [projectStats, setProjectStats] = useState<{
    totalTests: number;
    averageAccuracy: number;
    lastTestAccuracy: number | null;
    lastTestTime: string | null;
  }>({ totalTests: 0, averageAccuracy: 0, lastTestAccuracy: null, lastTestTime: null });
  
  // Video linking state
  const [videoSelectionOpen, setVideoSelectionOpen] = useState(false);
  const [linkingVideos, setLinkingVideos] = useState(false);
  
  // Video deletion state
  const [deleteDialog, setDeleteDialog] = useState(false);
  const [selectedVideoForDelete, setSelectedVideoForDelete] = useState<VideoFile | null>(null);
  const [deletingVideo, setDeletingVideo] = useState(false);
  
  // Video unlinking state
  const [unlinkDialog, setUnlinkDialog] = useState(false);
  const [selectedVideoForUnlink, setSelectedVideoForUnlink] = useState<VideoFile | null>(null);
  const [unlinkingVideo, setUnlinkingVideo] = useState(false);

  // Unlink video functionality
  const handleUnlinkVideo = (video: VideoFile) => {
    setSelectedVideoForUnlink(video);
    setUnlinkDialog(true);
  };

  const confirmUnlinkVideo = async (videoId: string) => {
    const video = videos.find(v => v.id === videoId);
    if (!video || !id) return;

    try {
      setUnlinkingVideo(true);
      await unlinkVideoFromProject(id, videoId);
      // Refresh project data to update video list
      await loadProjectData();
    } catch (err: any) {
      console.error('Video unlink error:', err);
      setError(getErrorMessage(err, 'Failed to unlink video'));
    } finally {
      setUnlinkingVideo(false);
    }
  };

  // Delete video functionality
  const handleDeleteVideo = (video: VideoFile) => {
    setSelectedVideoForDelete(video);
    setDeleteDialog(true);
  };

  const confirmDeleteVideo = async (videoId: string) => {
    try {
      setDeletingVideo(true);
      await deleteVideo(videoId);
      // Refresh project data to update video list
      await loadProjectData();
    } catch (err: any) {
      console.error('Video delete error:', err);
      setError(getErrorMessage(err, 'Failed to delete video'));
    } finally {
      setDeletingVideo(false);
    }
  };

  const loadProjectData = useCallback(async () => {
    if (!id) {
      setError('Project ID is required');
      setLoading(false);
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      // Load project data
      const projectData = await apiService.getProject(id);
      setProject(projectData);
      
      // Load linked videos and test sessions in parallel  
      const [videosData, testSessionsData] = await Promise.all([
        getLinkedVideos(id),
        apiService.getTestSessions(id)
      ]);
      
      setVideos(videosData);
      setTestSessions(testSessionsData);
      
      // Calculate project statistics locally
      const completedSessions = testSessionsData.filter(s => s.status === 'completed' && s.metrics);
      
      if (completedSessions.length === 0) {
        setProjectStats({ totalTests: 0, averageAccuracy: 0, lastTestAccuracy: null, lastTestTime: null });
      } else {
        const totalTests = completedSessions.length;
        const averageAccuracy = completedSessions.reduce((sum, session) => {
          return sum + (session.metrics?.accuracy || 0);
        }, 0) / totalTests;
        
        // Find most recent test
        const sortedSessions = [...completedSessions].sort((a, b) => {
          const timeA = a.completedAt || a.createdAt;
          const timeB = b.completedAt || b.createdAt;
          const timeAStr = typeof timeA === 'string' ? timeA : timeA?.toISOString?.() || '';
          const timeBStr = typeof timeB === 'string' ? timeB : timeB?.toISOString?.() || '';
          return new Date(timeBStr).getTime() - new Date(timeAStr).getTime();
        });
        
        const lastTest = sortedSessions[0];
        const lastTestAccuracy = lastTest?.metrics?.accuracy || null;
        const lastTestTimeRaw = lastTest?.completedAt || lastTest?.createdAt || null;
        const lastTestTime = typeof lastTestTimeRaw === 'string'
          ? lastTestTimeRaw
          : lastTestTimeRaw?.toISOString?.() || null;
        
        setProjectStats({
          totalTests,
          averageAccuracy: Math.round(averageAccuracy * 10) / 10,
          lastTestAccuracy: lastTestAccuracy ? Math.round(lastTestAccuracy * 10) / 10 : null,
          lastTestTime
        });
      }
    } catch (err: any) {
      console.error('Failed to load project data:', err);
      setError(getErrorMessage(err, 'Failed to load project data'));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadProjectData();
  }, [loadProjectData]);

  // Project statistics are now calculated inline in loadProjectData
  
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };
  
  const handleEditProject = () => {
    // Navigate to edit page or open edit modal
    navigate(`/projects/${id}/edit`);
  };
  
  const handleRunNewTest = () => {
    // Navigate to test execution page
    navigate(`/test-execution?projectId=${id}`);
  };

  // Video linking handlers
  const handleLinkVideosClick = () => {
    setVideoSelectionOpen(true);
  };

  const handleVideoSelectionComplete = async (selectedVideos: VideoFile[]) => {
    if (!id) return;
    
    try {
      setLinkingVideos(true);
      setError(null);
      
      const videoIds = selectedVideos.map(video => video.id);
      await linkVideosToProject(id, videoIds);
      
      // Refresh project data to update video list
      await loadProjectData();
      
    } catch (err: any) {
      console.error('Failed to link videos:', err);
      setError(getErrorMessage(err, 'Failed to link videos to project'));
    } finally {
      setLinkingVideos(false);
    }
  };
  
  const formatTimeAgo = (dateString: string | null) => {
    if (!dateString) return 'Never';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes} minute${diffInMinutes > 1 ? 's' : ''} ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)} hour${Math.floor(diffInMinutes / 60) > 1 ? 's' : ''} ago`;
    return `${Math.floor(diffInMinutes / 1440)} day${Math.floor(diffInMinutes / 1440) > 1 ? 's' : ''} ago`;
  };
  
  const formatFileSize = (bytes: number | undefined) => {
    if (!bytes) return 'Unknown';
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };
  
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
      case 'completed':
        return 'success';
      case 'draft':
      case 'pending':
        return 'warning';
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };
  
  if (loading) {
    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box>
            <Skeleton variant="text" width={300} height={40} />
            <Skeleton variant="text" width={500} height={24} />
          </Box>
          <Skeleton variant="rectangular" width={120} height={36} />
        </Box>
        
        <Grid container spacing={3} sx={{ mb: 3 }}>
          {[...Array(4)].map((_, index) => (
            <Grid size={{ xs: 12, md: 3 }} key={index}>
              <Card>
                <CardContent>
                  <Skeleton variant="text" width={150} height={24} />
                  <Skeleton variant="text" width={120} height={32} />
                  <Skeleton variant="text" width={180} height={20} />
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
        
        <Card>
          <Skeleton variant="rectangular" height={400} />
        </Card>
      </Box>
    );
  }
  
  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="contained" onClick={() => navigate('/projects')}>Back to Projects</Button>
      </Box>
    );
  }
  
  if (!project) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Project not found</Alert>
        <Button variant="contained" onClick={() => navigate('/projects')}>Back to Projects</Button>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4">{project.name}</Typography>
          <Typography variant="body1" color="text.secondary">
            {project.description || 'No description provided'}
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Edit />} onClick={handleEditProject}>
          Edit Project
        </Button>
      </Box>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Camera Details
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Model:</strong> {project.cameraModel || 'Not specified'}
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>View:</strong> {project.cameraView || 'Not specified'}
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Signal:</strong> {project.signalType || 'Not specified'}
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Videos:</strong> {videos.length}
              </Typography>
              <Typography variant="body2">
                <strong>Status:</strong> 
                <Chip 
                  label={project.status} 
                  color={getStatusColor(project.status) as any} 
                  size="small" 
                  sx={{ ml: 1 }}
                />
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Statistics
              </Typography>
              <Typography variant="h4" color="primary" gutterBottom>
                {projectStats.totalTests}
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                Total Tests Completed
              </Typography>
              <Chip 
                label={project.status} 
                color={getStatusColor(project.status) as any} 
                size="small" 
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Average Accuracy
              </Typography>
              <Typography variant="h4" color="success.main" gutterBottom>
                {projectStats.averageAccuracy > 0 ? `${projectStats.averageAccuracy}%` : 'N/A'}
              </Typography>
              <Typography variant="body2">
                {projectStats.totalTests > 0 
                  ? `Based on ${projectStats.totalTests} test${projectStats.totalTests > 1 ? 's' : ''}` 
                  : 'No completed tests'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Last Test
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                {formatTimeAgo(projectStats.lastTestTime)}
              </Typography>
              <Typography variant="body2" color={projectStats.lastTestAccuracy ? "success.main" : "text.secondary"}>
                {projectStats.lastTestAccuracy 
                  ? `${projectStats.lastTestAccuracy}% accuracy` 
                  : 'No completed tests'}
              </Typography>
              <Button
                size="small"
                startIcon={<PlayArrow />}
                sx={{ mt: 1 }}
                onClick={handleRunNewTest}
                variant="outlined"
              >
                Run New Test
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="Ground Truth Videos" />
            <Tab label="Test Results" />
            <Tab label="Settings" />
          </Tabs>
        </Box>
        
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <VideoLibrary />
            <Typography variant="h6">Ground Truth Videos ({videos.length})</Typography>
            <Button 
              variant="outlined" 
              size="small" 
              startIcon={<Link />}
              onClick={handleLinkVideosClick}
              disabled={linkingVideos}
            >
              Link Videos
            </Button>
          </Box>
          
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          {videos.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <VideoLibrary sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="body1" color="text.secondary" gutterBottom>
                No videos linked yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Link ground truth videos from the library to start testing your AI model
              </Typography>
            </Box>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Filename</TableCell>
                    <TableCell>File Size</TableCell>
                    <TableCell>Duration</TableCell>
                    <TableCell>Ground Truth</TableCell>
                    <TableCell>Detections</TableCell>
                    <TableCell>Linked</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {videos.map((video) => (
                    <TableRow key={video.id}>
                      <TableCell>
                        <Box>
                          <Typography variant="body2" fontWeight="medium">
                            {video.filename || video.originalName || video.name || 'Unknown'}
                          </Typography>
                          <Chip 
                            label={video.status} 
                            size="small" 
                            color={getStatusColor(video.status) as any}
                          />
                        </Box>
                      </TableCell>
                      <TableCell>
                        {formatFileSize(video.file_size || video.fileSize || video.size)}
                      </TableCell>
                      <TableCell>
                        {video.duration ? `${Math.round(video.duration)}s` : 'Unknown'}
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={video.ground_truth_generated || video.groundTruthGenerated ? 'Generated' : 'Pending'}
                          size="small"
                          color={video.ground_truth_generated || video.groundTruthGenerated ? 'success' : 'warning'}
                        />
                      </TableCell>
                      <TableCell>
                        {video.detectionCount || 0}
                      </TableCell>
                      <TableCell>
                        {formatTimeAgo(
                          (() => {
                            const dateValue = video.created_at || video.createdAt || video.uploadedAt;
                            if (typeof dateValue === 'string') {
                              return dateValue;
                            } else if (dateValue && typeof dateValue === 'object' && 'toISOString' in dateValue) {
                              return (dateValue as Date).toISOString();
                            }
                            return null;
                          })()
                        )}
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <Button 
                            size="small" 
                            color="warning" 
                            startIcon={<Delete />}
                            onClick={() => handleUnlinkVideo(video)}
                            disabled={unlinkingVideo || deletingVideo}
                          >
                            Unlink
                          </Button>
                          <Button 
                            size="small" 
                            color="error" 
                            variant="outlined"
                            startIcon={<Delete />}
                            onClick={() => handleDeleteVideo(video)}
                            disabled={unlinkingVideo || deletingVideo}
                          >
                            Delete
                          </Button>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>
        
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <Assessment />
            <Typography variant="h6">Test Results ({testSessions.length})</Typography>
            <Button variant="outlined" size="small" onClick={handleRunNewTest}>
              Run New Test
            </Button>
          </Box>
          
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          {testSessions.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Assessment sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="body1" color="text.secondary" gutterBottom>
                No test results yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Run your first test to see performance metrics and results
              </Typography>
            </Box>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Test Name</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Accuracy</TableCell>
                    <TableCell>Precision</TableCell>
                    <TableCell>Recall</TableCell>
                    <TableCell>F1 Score</TableCell>
                    <TableCell>Detections</TableCell>
                    <TableCell>Completed</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {testSessions.map((session) => (
                    <TableRow key={session.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {session.name}
                        </Typography>
                        {session.description && (
                          <Typography variant="caption" color="text.secondary">
                            {session.description}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={session.status} 
                          size="small" 
                          color={getStatusColor(session.status) as any}
                        />
                      </TableCell>
                      <TableCell>
                        {session.metrics?.accuracy 
                          ? `${Math.round(session.metrics.accuracy * 10) / 10}%` 
                          : 'N/A'}
                      </TableCell>
                      <TableCell>
                        {session.metrics?.precision 
                          ? `${Math.round(session.metrics.precision * 10) / 10}%` 
                          : 'N/A'}
                      </TableCell>
                      <TableCell>
                        {session.metrics?.recall 
                          ? `${Math.round(session.metrics.recall * 10) / 10}%` 
                          : 'N/A'}
                      </TableCell>
                      <TableCell>
                        {session.metrics?.f1Score 
                          ? `${Math.round(session.metrics.f1Score * 10) / 10}%` 
                          : 'N/A'}
                      </TableCell>
                      <TableCell>
                        {session.metrics?.totalDetections || 0}
                      </TableCell>
                      <TableCell>
                        {formatTimeAgo(
                          (() => {
                            const dateValue = session.completedAt || session.createdAt;
                            return typeof dateValue === 'string'
                              ? dateValue
                              : dateValue?.toISOString?.() || null;
                          })()
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </TabPanel>
        
        <TabPanel value={tabValue} index={2}>
          <Typography variant="h6" gutterBottom>
            Project Settings
          </Typography>
          
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Project Information
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Project ID:</strong> {project.id}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Created:</strong> {new Date(project.createdAt).toLocaleDateString()}
                    </Typography>
                  </Box>
                  {project.updatedAt && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        <strong>Last Updated:</strong> {new Date(project.updatedAt).toLocaleDateString()}
                      </Typography>
                    </Box>
                  )}
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Status:</strong> 
                      <Chip 
                        label={project.status} 
                        color={getStatusColor(project.status) as any} 
                        size="small" 
                        sx={{ ml: 1 }}
                      />
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid size={{ xs: 12, md: 6 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Camera Configuration
                  </Typography>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Model:</strong> {project.cameraModel || 'Not specified'}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>View Type:</strong> {project.cameraView || 'Not specified'}
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>Signal Type:</strong> {project.signalType || 'Not specified'}
                    </Typography>
                  </Box>
                  <Button variant="outlined" onClick={handleEditProject} sx={{ mt: 2 }}>
                    Edit Configuration
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>
      </Card>

      {/* Video Selection Dialog */}
      <VideoSelectionDialog
        open={videoSelectionOpen}
        onClose={() => setVideoSelectionOpen(false)}
        projectId={id || ''}
        onSelectionComplete={handleVideoSelectionComplete}
        selectedVideoIds={videos.map(v => v.id)}
      />

      {/* Video Unlink Confirmation Dialog */}
      <UnlinkVideoConfirmationDialog
        open={unlinkDialog}
        onClose={() => setUnlinkDialog(false)}
        video={selectedVideoForUnlink}
        projectName={project?.name}
        onConfirm={confirmUnlinkVideo}
        loading={unlinkingVideo}
      />

      {/* Video Delete Confirmation Dialog */}
      <VideoDeleteConfirmationDialog
        open={deleteDialog}
        onClose={() => setDeleteDialog(false)}
        video={selectedVideoForDelete}
        onConfirm={confirmDeleteVideo}
        loading={deletingVideo}
        projectsUsingVideo={selectedVideoForDelete ? [project?.name || 'Current Project'] : []}
        annotationCount={selectedVideoForDelete?.detectionCount || 0}
        testSessionCount={testSessions.filter(s => s.videoId === selectedVideoForDelete?.id).length}
      />
    </Box>
  );
};

export default ProjectDetail;