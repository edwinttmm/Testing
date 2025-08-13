import React, { useState, useEffect } from 'react';
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
  CircularProgress,
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
  Upload,
  Delete,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { Project, VideoFile, TestSession, TestMetrics } from '../services/types';

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
  const [videoError, setVideoError] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [projectStats, setProjectStats] = useState<{
    totalTests: number;
    averageAccuracy: number;
    lastTestAccuracy: number | null;
    lastTestTime: string | null;
  }>({ totalTests: 0, averageAccuracy: 0, lastTestAccuracy: null, lastTestTime: null });

  useEffect(() => {
    if (!id) {
      setError('Project ID is required');
      setLoading(false);
      return;
    }
    
    loadProjectData();
  }, [id]);

  const loadProjectData = async () => {
    if (!id) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // Load project data
      const projectData = await apiService.getProject(id);
      setProject(projectData);
      
      // Load videos and test sessions in parallel
      const [videosData, testSessionsData] = await Promise.allSettled([
        apiService.getVideos(id),
        apiService.getTestSessions(id)
      ]);
      
      if (videosData.status === 'fulfilled') {
        setVideos(videosData.value);
        setVideoError(null);
      } else {
        console.error('Failed to load videos:', videosData.reason);
        setVideoError('Failed to load project videos');
        setVideos([]);
      }
      
      if (testSessionsData.status === 'fulfilled') {
        setTestSessions(testSessionsData.value);
        setTestError(null);
        
        // Calculate project statistics
        calculateProjectStats(testSessionsData.value);
      } else {
        console.error('Failed to load test sessions:', testSessionsData.reason);
        setTestError('Failed to load test sessions');
        setTestSessions([]);
      }
      
    } catch (err: any) {
      console.error('Failed to load project:', err);
      setError(err.message || 'Failed to load project details');
    } finally {
      setLoading(false);
    }
  };
  
  const calculateProjectStats = (sessions: TestSession[]) => {
    const completedSessions = sessions.filter(s => s.status === 'completed' && s.metrics);
    
    if (completedSessions.length === 0) {
      setProjectStats({ totalTests: 0, averageAccuracy: 0, lastTestAccuracy: null, lastTestTime: null });
      return;
    }
    
    const totalTests = completedSessions.length;
    const averageAccuracy = completedSessions.reduce((sum, session) => {
      return sum + (session.metrics?.accuracy || 0);
    }, 0) / totalTests;
    
    // Find most recent test
    const sortedSessions = [...completedSessions].sort((a, b) => {
      const timeA = new Date(a.completedAt || a.createdAt || '').getTime();
      const timeB = new Date(b.completedAt || b.createdAt || '').getTime();
      return timeB - timeA;
    });
    
    const lastTest = sortedSessions[0];
    const lastTestAccuracy = lastTest?.metrics?.accuracy || null;
    const lastTestTime = lastTest?.completedAt || lastTest?.createdAt || null;
    
    setProjectStats({
      totalTests,
      averageAccuracy: Math.round(averageAccuracy * 10) / 10,
      lastTestAccuracy: lastTestAccuracy ? Math.round(lastTestAccuracy * 10) / 10 : null,
      lastTestTime
    });
  };
  
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
            <Grid item xs={12} md={3} key={index}>
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
        <Grid item xs={12} md={3}>
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

        <Grid item xs={12} md={3}>
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

        <Grid item xs={12} md={3}>
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

        <Grid item xs={12} md={3}>
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
            <Button variant="outlined" size="small" startIcon={<Upload />}>
              Upload Video
            </Button>
          </Box>
          
          {videoError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {videoError}
            </Alert>
          )}
          
          {videos.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <VideoLibrary sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="body1" color="text.secondary" gutterBottom>
                No videos uploaded yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Upload ground truth videos to start testing your AI model
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
                    <TableCell>Uploaded</TableCell>
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
                        {formatTimeAgo(video.created_at || video.createdAt || video.uploadedAt)}
                      </TableCell>
                      <TableCell>
                        <Button 
                          size="small" 
                          color="error" 
                          startIcon={<Delete />}
                          onClick={() => {
                            // Add delete functionality
                            console.log('Delete video:', video.id);
                          }}
                        >
                          Delete
                        </Button>
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
          
          {testError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {testError}
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
                        {formatTimeAgo(session.completedAt || session.createdAt)}
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
            <Grid item xs={12} md={6}>
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
            
            <Grid item xs={12} md={6}>
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
    </Box>
  );
};

export default ProjectDetail;