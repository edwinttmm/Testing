import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Grid,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Snackbar,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Pause,
  CheckCircle,
  Error,
  Warning,
  RadioButtonChecked,
  Settings,
  Refresh,
  WifiOff,
  Wifi,
} from '@mui/icons-material';
import { io, Socket } from 'socket.io-client';
import { getWebSocketErrorMessage } from '../utils/errorUtils';
import { apiService } from '../services/api';
import { TestSession as TestSessionType, VideoFile, Project, ApiError } from '../services/types';

interface DetectionEvent {
  id: string;
  timestamp: number;
  validationResult: 'TP' | 'FP' | 'FN';
  confidence: number;
  classLabel: string;
}

const TestExecution: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [currentSession, setCurrentSession] = useState<TestSessionType | null>(null);
  const [detectionEvents, setDetectionEvents] = useState<DetectionEvent[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [videos, setVideos] = useState<VideoFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [sessionDialog, setSessionDialog] = useState(false);
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedVideo, setSelectedVideo] = useState('');
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const MAX_RECONNECT_ATTEMPTS = 5;

  // Load projects and videos
  useEffect(() => {
    loadProjects();
  }, []);

  const loadVideos = useCallback(async (projectId: string) => {
    try {
      const videoList = await apiService.getVideos(projectId);
      setVideos(videoList.filter(v => v.status === 'completed')); // Only show ready videos
    } catch (err) {
      const apiError = err as ApiError;
      setError(`Failed to load videos: ${apiError.message}`);
    }
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadVideos(selectedProject);
    }
  }, [selectedProject, loadVideos]);

  const loadProjects = async () => {
    try {
      const projectList = await apiService.getProjects();
      setProjects(projectList);
    } catch (err) {
      const apiError = err as ApiError;
      setError(`Failed to load projects: ${apiError.message}`);
    }
  };

  const handleReconnect = useCallback(() => {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      const delay = Math.pow(2, reconnectAttempts) * 1000; // Exponential backoff
      
      reconnectTimeoutRef.current = setTimeout(() => {
        // Attempting to reconnect
        setReconnectAttempts(prev => prev + 1);
        // Will trigger useEffect to reinitialize
      }, delay);
    } else {
      setConnectionError('Unable to connect to real-time server. Please refresh the page.');
    }
  }, [reconnectAttempts]);

  const initializeWebSocket = useCallback(() => {
    const wsUrl = process.env.REACT_APP_WS_URL || 'http://localhost:8001';
    const token = localStorage.getItem('authToken') || 'dev-token';
    
    const newSocket = io(wsUrl, {
      auth: {
        token: token
      },
      transports: ['websocket', 'polling'],
      timeout: 10000,
      forceNew: true,
      path: '/socket.io/'
    });
    
    newSocket.on('connect', () => {
      setIsConnected(true);
      setConnectionError(null);
      setReconnectAttempts(0);
      // Connected to WebSocket server
      setSuccessMessage('Connected to real-time detection server');
      
      // Join test namespace
      newSocket.emit('join_room', { room: 'test_sessions' });
    });

    newSocket.on('disconnect', (reason) => {
      setIsConnected(false);
      // Disconnected from WebSocket server
      
      // Try to reconnect if not manually disconnected
      if (reason !== 'io client disconnect') {
        handleReconnect();
      }
    });

    newSocket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      setIsConnected(false);
      const errorMessage = error?.message || (error as any)?.description || 'Unknown error';
      setConnectionError(`Failed to connect to real-time server: ${errorMessage}`);
      handleReconnect();
    });

    newSocket.on('detection_event', (event: DetectionEvent) => {
      // Received detection event
      setDetectionEvents(prev => [...prev, event]);
    });

    newSocket.on('test_session_update', (session: TestSessionType) => {
      // Test session update
      setCurrentSession(session);
    });

    newSocket.on('connection_status', (data) => {
      // Connection status update
      if (data.status === 'connected') {
        setSuccessMessage(data.message || 'Connected successfully');
      }
    });

    newSocket.on('error', (data) => {
      console.error('Socket.IO error:', data);
      const errorMessage = getWebSocketErrorMessage(data);
      setError(`Server error: ${errorMessage}`);
    });

    setSocket(newSocket);
  }, [handleReconnect]);

  // WebSocket connection with reconnection
  useEffect(() => {
    initializeWebSocket();

    return () => {
      if (socket) {
        socket.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initializeWebSocket]);

  const handleStartTest = async () => {
    if (!selectedProject || !selectedVideo) {
      setError('Please select a project and video');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Create real test session via API
      const sessionData = {
        name: `Test Session ${new Date().toLocaleString()}`,
        projectId: selectedProject,
        videoId: selectedVideo,
        toleranceMs: 100, // Default tolerance
      };
      
      const newSession = await apiService.createTestSession(sessionData);
      setCurrentSession(newSession);
      setDetectionEvents([]);
      setSessionDialog(false);

      // Notify server via WebSocket
      if (socket && isConnected) {
        socket.emit('start_test_session', {
          sessionId: newSession.id,
          projectId: selectedProject,
          videoId: selectedVideo,
        });
      }

      // Load selected video URL
      const selectedVideoData = videos.find(v => v.id === selectedVideo);
      if (videoRef.current && selectedVideoData) {
        videoRef.current.src = selectedVideoData.url || `/api/videos/${selectedVideo}/stream`;
        videoRef.current.load();
        await new Promise(resolve => {
          if (videoRef.current) {
            videoRef.current.onloadeddata = resolve;
          }
        });
        videoRef.current.play();
      }

      setSuccessMessage(`Test session started: ${newSession.name}`);
    } catch (err) {
      const apiError = err as ApiError;
      setError(`Failed to start test session: ${apiError.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStopTest = async () => {
    if (!currentSession) return;

    try {
      setLoading(true);
      
      // Notify server to stop session
      if (socket && isConnected) {
        socket.emit('stop_test_session', {
          sessionId: currentSession.id,
        });
      }

      // Update session status
      setCurrentSession({
        ...currentSession,
        status: 'completed',
      });

      // Stop video
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.currentTime = 0;
      }

      setSuccessMessage('Test session stopped');
    } catch (err) {
      console.error('Error stopping test session:', err);
      setError('Failed to stop test session');
    } finally {
      setLoading(false);
    }
  };

  const handlePauseTest = async () => {
    if (!currentSession) return;

    try {
      // Notify server to pause session
      if (socket && isConnected) {
        socket.emit('pause_test_session', {
          sessionId: currentSession.id,
        });
      }

      // Update session status
      setCurrentSession({
        ...currentSession,
        status: 'cancelled',
      });

      // Pause video
      if (videoRef.current) {
        videoRef.current.pause();
      }
    } catch (err) {
      console.error('Error pausing test session:', err);
      setError('Failed to pause test session');
    }
  };

  const handleResumeTest = async () => {
    if (!currentSession) return;

    try {
      // Notify server to resume session
      if (socket && isConnected) {
        socket.emit('resume_test_session', {
          sessionId: currentSession.id,
        });
      }

      // Update session status
      setCurrentSession({
        ...currentSession,
        status: 'running',
      });

      // Resume video
      if (videoRef.current) {
        videoRef.current.play();
      }
    } catch (err) {
      console.error('Error resuming test session:', err);
      setError('Failed to resume test session');
    }
  };

  const handleRetryConnection = () => {
    setReconnectAttempts(0);
    setConnectionError(null);
    initializeWebSocket();
  };

  const getValidationIcon = (result: string) => {
    switch (result) {
      case 'TP':
        return <CheckCircle color="success" />;
      case 'FP':
        return <Error color="error" />;
      case 'FN':
        return <Warning color="warning" />;
      default:
        return <RadioButtonChecked />;
    }
  };

  const getValidationColor = (result: string) => {
    switch (result) {
      case 'TP':
        return 'success';
      case 'FP':
        return 'error';
      case 'FN':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getMetrics = () => {
    const tp = detectionEvents.filter(e => e.validationResult === 'TP').length;
    const fp = detectionEvents.filter(e => e.validationResult === 'FP').length;
    const fn = detectionEvents.filter(e => e.validationResult === 'FN').length;
    
    const precision = tp + fp > 0 ? (tp / (tp + fp) * 100) : 0;
    const recall = tp + fn > 0 ? (tp / (tp + fn) * 100) : 0;

    return { tp, fp, fn, precision, recall };
  };

  const metrics = getMetrics();
  const selectedVideoData = videos.find(v => v.id === selectedVideo);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Test Execution & Monitoring</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {connectionError && (
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={handleRetryConnection}
              size="small"
            >
              Retry Connection
            </Button>
          )}
          <Button
            variant="contained"
            startIcon={<Settings />}
            onClick={() => setSessionDialog(true)}
            disabled={currentSession?.status === 'running' || loading}
          >
            New Test Session
          </Button>
        </Box>
      </Box>

      {/* Connection Status */}
      <Alert 
        severity={isConnected ? 'success' : (connectionError ? 'error' : 'warning')} 
        sx={{ mb: 3 }}
        icon={isConnected ? <Wifi /> : <WifiOff />}
        action={
          !isConnected && connectionError && (
            <Button color="inherit" size="small" onClick={handleRetryConnection}>
              Retry
            </Button>
          )
        }
      >
        Real-time Server: {
          isConnected 
            ? 'Connected and ready'
            : connectionError || 'Connecting...'
        }
        {reconnectAttempts > 0 && (
          <Typography variant="caption" display="block">
            Reconnect attempt {reconnectAttempts}/{MAX_RECONNECT_ATTEMPTS}
          </Typography>
        )}
      </Alert>

      {/* Current Session Info */}
      {currentSession && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="subtitle2">
            Active Session: {currentSession.name}
          </Typography>
          <Typography variant="caption">
            Status: {currentSession.status?.toUpperCase()} • 
            Started: {new Date(currentSession.createdAt || '').toLocaleString()}
          </Typography>
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Video Player */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Video
                {selectedVideoData && (
                  <Typography variant="caption" component="span" sx={{ ml: 2 }}>
                    {selectedVideoData.filename}
                  </Typography>
                )}
              </Typography>
              
              <Box sx={{ position: 'relative', mb: 2 }}>
                <video
                  ref={videoRef}
                  width="100%"
                  height="400"
                  controls
                  style={{ backgroundColor: '#000' }}
                >
                  Your browser does not support the video tag.
                </video>
                
                {currentSession?.status === 'running' && (
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 10,
                      right: 10,
                      bgcolor: 'error.main',
                      color: 'white',
                      px: 1,
                      py: 0.5,
                      borderRadius: 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                    }}
                  >
                    <RadioButtonChecked sx={{ fontSize: 16 }} />
                    TESTING
                  </Box>
                )}
                
                {loading && (
                  <Box
                    sx={{
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: 'translate(-50%, -50%)',
                    }}
                  >
                    <CircularProgress />
                  </Box>
                )}
              </Box>

              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<PlayArrow />}
                  onClick={handleStartTest}
                  disabled={currentSession?.status === 'running' || loading}
                  color="success"
                >
                  Start Test
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Pause />}
                  onClick={currentSession?.status === 'running' ? handlePauseTest : handleResumeTest}
                  disabled={!currentSession || currentSession.status === 'completed' || loading}
                >
                  {currentSession?.status === 'running' ? 'Pause' : 'Resume'}
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Stop />}
                  onClick={handleStopTest}
                  disabled={!currentSession || currentSession.status === 'completed' || loading}
                  color="error"
                >
                  Stop Test
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Real-time Results */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Grid container spacing={2}>
            {/* Metrics */}
            <Grid size={{ xs: 12 }}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Live Metrics
                  </Typography>
                  
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2">Precision</Typography>
                    <LinearProgress 
                      variant="determinate" 
                      value={metrics.precision} 
                      color="primary"
                    />
                    <Typography variant="caption">{metrics.precision.toFixed(1)}%</Typography>
                  </Box>
                  
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2">Recall</Typography>
                    <LinearProgress 
                      variant="determinate" 
                      value={metrics.recall} 
                      color="secondary"
                    />
                    <Typography variant="caption">{metrics.recall.toFixed(1)}%</Typography>
                  </Box>

                  <Grid container spacing={1}>
                    <Grid size={{ xs: 4 }}>
                      <Chip 
                        label={`TP: ${metrics.tp}`} 
                        color="success" 
                        size="small" 
                      />
                    </Grid>
                    <Grid size={{ xs: 4 }}>
                      <Chip 
                        label={`FP: ${metrics.fp}`} 
                        color="error" 
                        size="small" 
                      />
                    </Grid>
                    <Grid size={{ xs: 4 }}>
                      <Chip 
                        label={`FN: ${metrics.fn}`} 
                        color="warning" 
                        size="small" 
                      />
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            {/* Detection Log */}
            <Grid size={{ xs: 12 }}>
              <Card sx={{ height: 400 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Detection Events ({detectionEvents.length})
                  </Typography>
                  
                  <List sx={{ height: 300, overflow: 'auto' }}>
                    {detectionEvents.slice(-10).reverse().map((event, index) => (
                      <ListItem key={`${event.id}-${index}`} dense>
                        <ListItemIcon>
                          {getValidationIcon(event.validationResult)}
                        </ListItemIcon>
                        <ListItemText
                          primary={`${event.classLabel} (${(event.confidence * 100).toFixed(1)}%)`}
                          secondary={`${event.timestamp.toFixed(2)}s - ${event.validationResult}`}
                        />
                        <Chip
                          label={event.validationResult}
                          color={getValidationColor(event.validationResult) as any}
                          size="small"
                        />
                      </ListItem>
                    ))}
                    {detectionEvents.length === 0 && (
                      <ListItem>
                        <ListItemText
                          primary="No detection events yet"
                          secondary="Start a test session to see real-time results"
                        />
                      </ListItem>
                    )}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Grid>
      </Grid>

      {/* New Test Session Dialog */}
      <Dialog open={sessionDialog} onClose={() => setSessionDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Configure Test Session</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mb: 2, mt: 1 }}>
            <InputLabel>Select Project</InputLabel>
            <Select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              label="Select Project"
            >
              {projects.map((project) => (
                <MenuItem key={project.id} value={project.id}>
                  {project.name}
                </MenuItem>
              ))}
              {projects.length === 0 && (
                <MenuItem disabled>No projects available</MenuItem>
              )}
            </Select>
          </FormControl>
          
          <FormControl fullWidth>
            <InputLabel>Select Video</InputLabel>
            <Select
              value={selectedVideo}
              onChange={(e) => setSelectedVideo(e.target.value)}
              label="Select Video"
              disabled={!selectedProject}
            >
              {videos.map((video) => (
                <MenuItem key={video.id} value={video.id}>
                  {video.filename} ({video.status})
                </MenuItem>
              ))}
              {selectedProject && videos.length === 0 && (
                <MenuItem disabled>No completed videos available</MenuItem>
              )}
            </Select>
          </FormControl>
          
          {selectedProject && videos.length === 0 && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Upload and process videos in the Ground Truth section first.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSessionDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleStartTest} 
            variant="contained"
            disabled={!selectedProject || !selectedVideo || loading}
          >
            {loading ? <CircularProgress size={20} /> : 'Start Test'}
          </Button>
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

export default TestExecution;