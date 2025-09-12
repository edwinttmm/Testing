import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Grid,
  LinearProgress,
  Chip,
  Alert,
  AlertTitle,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Divider,
  Stack,
  IconButton,
  Tooltip,
  CircularProgress,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Pause,
  Fullscreen,
  FullscreenExit,
  CheckCircle,
  Error,
  Warning,
  Settings,
  Refresh,
  Visibility,
  Timeline,
  Hardware,
  Speed,
  Analytics,
  VideoLibrary,
  Assignment,
  Schedule,
  SignalCellular4Bar,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import {
  Project,
  VideoFile,
  TestSession,
  TestSessionCreate,
  DetectionOutcome,
  SignalType,
  VRUType,
  VideoStatus,
} from '../services/types';
import LabJackStatusPanel from '../components/LabJackStatusPanel';

// PRD-aligned interfaces using exact variable names from GLOBAL_VARIABLES_REFERENCE.md
interface TestSessionInterface {
  id: number;
  projectId: number;
  testStartTime: string; // PRD: Test_Start_Time
  maxLatencyMs: number; // PRD: User-defined threshold
  labjackConnected: boolean;
  totalEvents: number;
  passedEvents: number;
  failedEvents: number;
  missedDetections: number;
  averageLatencyMs: number;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed';
  completedAt?: string;
}

interface DetectionEventInterface {
  id: string;
  testSessionId: string;
  videoId: string;
  groundTruthObjectId: number;
  expectedEventTime: string; // PRD: Expected_Event_Time
  signalReceivedTime?: string; // PRD: Signal_Received_Time
  latencyMs?: number;
  outcome: DetectionOutcome;
  signalType: SignalType;
  signalValue?: number;
  snapshotPath?: string;
  createdAt: string;
}

interface GroundTruthObjectInterface {
  id: number;
  videoId: number;
  vruId: string; // PRD: Persistent VRU ID
  vruType: VRUType;
  frameNumber: number;
  timestampMs: number;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  confidence: number;
  validated: boolean;
}

interface LabJackConnectionStatus {
  connected: boolean;
  status: 'connected' | 'disconnected' | 'connecting' | 'error';
  mode: 'auto' | 'bridge' | 'direct' | 'mock';
  deviceInfo?: {
    deviceType: string;
    serialNumber?: string;
  };
  signalType: SignalType;
  voltageThreshold: number;
}

const HILTestExecution: React.FC = () => {
  // Core state using PRD-aligned variable names
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [videoPlaylist, setVideoPlaylist] = useState<VideoFile[]>([]);
  const [currentTestSession, setCurrentTestSession] = useState<TestSessionInterface | null>(null);
  const [detectionEvents, setDetectionEvents] = useState<DetectionEventInterface[]>([]);
  const [maxLatencyMs, setMaxLatencyMs] = useState<number>(100); // PRD: Default 100ms
  
  // LabJack hardware integration
  const [labjackStatus, setLabjackStatus] = useState<LabJackConnectionStatus | null>(null);
  
  // Test execution state
  const [testInProgress, setTestInProgress] = useState(false);
  const [currentVideoIndex, setCurrentVideoIndex] = useState(0);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [testStartTime, setTestStartTime] = useState<Date | null>(null); // PRD: Test_Start_Time reference
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [startTestDialog, setStartTestDialog] = useState(false);
  
  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const fullScreenContainerRef = useRef<HTMLDivElement>(null);
  
  // WebSocket for real-time updates
  const { isConnected: wsConnected, emit: wsEmit, on: wsSubscribe } = useWebSocket();
  
  // Load projects on component mount
  useEffect(() => {
    loadProjects();
  }, []);
  
  // Load projects function
  const loadProjects = async () => {
    try {
      setLoading(true);
      const response = await apiService.getProjects();
      // Only show projects with validated videos (PRD requirement)
      const validProjects = response.filter(project => 
        project.status === 'active' || project.status === 'testing'
      );
      setProjects(validProjects);
    } catch (err: any) {
      setError(`Failed to load projects: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Load video playlist for selected project
  const loadVideoPlaylist = async (projectId: string) => {
    try {
      setLoading(true);
      const response = await apiService.get<VideoFile[]>(`/api/v1/projects/${projectId}/videos`);
      // Only include validated videos (PRD requirement)
      const validatedVideos = response.filter(video => 
        video.status === 'validated' || 
        video.status === VideoStatus.VALIDATED || 
        (video as any).validation_status === 'validated'
      );
      setVideoPlaylist(validatedVideos);
      
      if (validatedVideos.length === 0) {
        setError('No validated videos found in this project. Please ensure videos are properly validated before testing.');
      }
    } catch (err: any) {
      setError(`Failed to load video playlist: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Check LabJack connection status
  const checkLabJackStatus = useCallback(async () => {
    try {
      const response = await apiService.get<any>('/api/labjack/status');
      const status: LabJackConnectionStatus = {
        connected: response.connected || false,
        status: response.status || 'disconnected',
        mode: response.mode || 'auto',
        deviceInfo: response.device_info ? {
          deviceType: response.device_info.device_type || 'Unknown',
          serialNumber: response.device_info.serial_number
        } : undefined,
        signalType: response.signal_type || SignalType.TTL,
        voltageThreshold: response.voltage_threshold || 2.5
      };
      setLabjackStatus(status);
      return status;
    } catch (err: any) {
      console.error('Failed to check LabJack status:', err);
      const errorStatus: LabJackConnectionStatus = {
        connected: false,
        status: 'error',
        mode: 'auto',
        signalType: SignalType.TTL,
        voltageThreshold: 2.5
      };
      setLabjackStatus(errorStatus);
      return errorStatus;
    }
  }, []);
  
  // Load LabJack status on component mount and set up polling
  useEffect(() => {
    checkLabJackStatus();
    
    // Poll LabJack status every 5 seconds
    const statusInterval = setInterval(checkLabJackStatus, 5000);
    
    return () => {
      clearInterval(statusInterval);
    };
  }, [checkLabJackStatus]);
  
  // Handle project selection
  const handleProjectSelect = (project: Project) => {
    setSelectedProject(project);
    loadVideoPlaylist(project.id);
    setCurrentVideoIndex(0);
    setDetectionEvents([]);
    setError(null);
  };
  
  // Validate test start conditions (PRD requirement)
  const validateTestStart = (): { canStart: boolean; errors: string[] } => {
    const errors: string[] = [];
    
    if (!selectedProject) {
      errors.push('Please select a project');
    }
    
    if (videoPlaylist.length === 0) {
      errors.push('No validated videos in playlist');
    }
    
    if (!labjackStatus?.connected) {
      errors.push('LabJack device not connected (PRD requirement)');
    }
    
    if (maxLatencyMs <= 0 || maxLatencyMs > 10000) {
      errors.push('Maximum latency must be between 1-10000ms');
    }
    
    return {
      canStart: errors.length === 0,
      errors
    };
  };
  
  // Start HIL test execution
  const startTest = async () => {
    const validation = validateTestStart();
    if (!validation.canStart) {
      setError(`Cannot start test:\n${validation.errors.join('\n')}`);
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      
      // Create test session
      const testSessionData: TestSessionCreate = {
        projectId: selectedProject!.id,
        name: `HIL Test Session - ${new Date().toISOString()}`,
        maxLatencyMs,
        labjackConnected: labjackStatus!.connected,
        status: 'running'
      };
      
      const session = await apiService.post<TestSessionInterface>('/api/v1/test-sessions', testSessionData);
      setCurrentTestSession(session);
      
      // Capture high-precision Test_Start_Time (PRD requirement)
      const startTime = new Date();
      setTestStartTime(startTime);
      setTestInProgress(true);
      
      // Switch to full-screen mode (PRD requirement)
      await enterFullScreen();
      
      // Start video playback
      setCurrentVideoIndex(0);
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
        await videoRef.current.play();
      }
      
      // Subscribe to hardware signals via WebSocket
      if (wsConnected) {
        wsEmit('subscribe_hardware_signals', {
          sessionId: session.id,
          signalType: labjackStatus!.signalType
        });
      }
      
      setSuccessMessage('HIL test started successfully');
      setStartTestDialog(false);
      
    } catch (err: any) {
      setError(`Failed to start test: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Stop test execution
  const stopTest = async () => {
    try {
      setLoading(true);
      
      if (currentTestSession) {
        await apiService.post(`/api/v1/test-sessions/${currentTestSession.id}/stop`);
      }
      
      // Exit full-screen mode
      await exitFullScreen();
      
      // Stop video playback
      if (videoRef.current) {
        videoRef.current.pause();
      }
      
      // Unsubscribe from hardware signals
      if (wsConnected) {
        wsEmit('unsubscribe_hardware_signals');
      }
      
      setTestInProgress(false);
      setCurrentTestSession(null);
      setTestStartTime(null);
      setSuccessMessage('Test stopped successfully');
      
    } catch (err: any) {
      setError(`Failed to stop test: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Full-screen management (PRD requirement)
  const enterFullScreen = async () => {
    if (fullScreenContainerRef.current) {
      try {
        if (fullScreenContainerRef.current.requestFullscreen) {
          await fullScreenContainerRef.current.requestFullscreen();
        } else if ((fullScreenContainerRef.current as any).webkitRequestFullscreen) {
          await (fullScreenContainerRef.current as any).webkitRequestFullscreen();
        } else if ((fullScreenContainerRef.current as any).msRequestFullscreen) {
          await (fullScreenContainerRef.current as any).msRequestFullscreen();
        }
        setIsFullScreen(true);
      } catch (err) {
        console.error('Failed to enter full-screen mode:', err);
      }
    }
  };
  
  const exitFullScreen = async () => {
    try {
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if ((document as any).webkitExitFullscreen) {
        await (document as any).webkitExitFullscreen();
      } else if ((document as any).msExitFullscreen) {
        await (document as any).msExitFullscreen();
      }
      setIsFullScreen(false);
    } catch (err) {
      console.error('Failed to exit full-screen mode:', err);
    }
  };
  
  // Handle video end - advance to next video in playlist
  const handleVideoEnded = () => {
    if (currentVideoIndex < videoPlaylist.length - 1) {
      setCurrentVideoIndex(prev => prev + 1);
    } else {
      // Test completed
      completeTest();
    }
  };
  
  // Complete test when all videos are played
  const completeTest = async () => {
    try {
      if (currentTestSession) {
        await apiService.post(`/api/v1/test-sessions/${currentTestSession.id}/complete`);
      }
      
      await exitFullScreen();
      setTestInProgress(false);
      setSuccessMessage('HIL test completed successfully');
      
    } catch (err: any) {
      setError(`Failed to complete test: ${err.message}`);
    }
  };
  
  // WebSocket event handlers for hardware signals
  useEffect(() => {
    if (!wsConnected) return;
    
    const handleHardwareSignal = (data: any) => {
      if (!testInProgress || !testStartTime || !currentTestSession) return;
      
      // Calculate Expected_Event_Time and Signal_Received_Time (PRD requirement)
      const signalReceivedTime = new Date();
      const expectedEventTime = new Date(testStartTime.getTime() + data.expectedTimestamp);
      const latencyMs = signalReceivedTime.getTime() - expectedEventTime.getTime();
      
      // Determine outcome based on latency threshold
      let outcome: DetectionOutcome;
      if (latencyMs <= maxLatencyMs) {
        outcome = DetectionOutcome.PASS;
      } else {
        outcome = DetectionOutcome.FAIL_HIGH_LATENCY;
      }
      
      const event: DetectionEventInterface = {
        id: String(data.id),
        testSessionId: String(currentTestSession.id),
        videoId: videoPlaylist[currentVideoIndex]?.id || '0',
        groundTruthObjectId: data.groundTruthObjectId,
        expectedEventTime: expectedEventTime.toISOString(),
        signalReceivedTime: signalReceivedTime.toISOString(),
        latencyMs,
        outcome,
        signalType: data.signalType || SignalType.TTL,
        signalValue: data.signalValue,
        createdAt: new Date().toISOString()
      };
      
      setDetectionEvents(prev => [...prev, event]);
    };
    
    wsSubscribe('hardware_signal_detected', handleHardwareSignal);
    
    return () => {
      // Cleanup WebSocket subscription
    };
  }, [wsConnected, testInProgress, testStartTime, currentTestSession, maxLatencyMs, videoPlaylist, currentVideoIndex, wsSubscribe]);
  
  // Get connection status color
  const getConnectionStatusColor = () => {
    if (!labjackStatus) return 'default';
    if (labjackStatus.connected) return 'success';
    if (labjackStatus.status === 'connecting') return 'warning';
    return 'error';
  };
  
  // Get connection status text
  const getConnectionStatusText = () => {
    if (!labjackStatus) return 'Unknown';
    if (labjackStatus.connected) return 'Connected';
    if (labjackStatus.status === 'connecting') return 'Connecting...';
    if (labjackStatus.status === 'error') return 'Connection Error';
    return 'Not Detected';
  };
  
  return (
    <div ref={fullScreenContainerRef}>
      <Box sx={{ p: isFullScreen ? 0 : 3 }}>
        {/* Header - Hide in full-screen mode */}
        {!isFullScreen && (
          <>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h4">HIL Test Execution</Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="contained"
                  startIcon={<PlayArrow />}
                  onClick={() => setStartTestDialog(true)}
                  disabled={!selectedProject || !labjackStatus?.connected || testInProgress}
                  color="primary"
                >
                  Start HIL Test
                </Button>
                {testInProgress && (
                  <Button
                    variant="contained"
                    startIcon={<Stop />}
                    onClick={stopTest}
                    color="error"
                    disabled={loading}
                  >
                    Stop Test
                  </Button>
                )}
                <Button
                  variant="outlined"
                  startIcon={<Refresh />}
                  onClick={() => {
                    loadProjects();
                    checkLabJackStatus();
                  }}
                  disabled={loading}
                >
                  Refresh
                </Button>
              </Box>
            </Box>

            {/* Error and Success Messages */}
            {error && (
              <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
                <AlertTitle>Error</AlertTitle>
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{error}</pre>
              </Alert>
            )}
            
            {successMessage && (
              <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccessMessage(null)}>
                {successMessage}
              </Alert>
            )}

            {/* Project Selection Section */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  1. Project Selection
                </Typography>
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Select Project</InputLabel>
                  <Select
                    value={selectedProject?.id || ''}
                    onChange={(e) => {
                      const project = projects.find(p => p.id === e.target.value);
                      if (project) handleProjectSelect(project);
                    }}
                    disabled={testInProgress}
                  >
                    {projects.map((project) => (
                      <MenuItem key={project.id} value={project.id}>
                        {project.name} ({project.videoCount || 0} videos)
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                
                {selectedProject && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Camera: {selectedProject.cameraModel} • View: {selectedProject.cameraView} • 
                      Signal Type: {selectedProject.signalType}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Video Playlist: {videoPlaylist.length} validated videos
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>

            {/* LabJack Connection Status Section */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  2. Hardware Connection Status
                </Typography>
                
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  <Chip
                    icon={labjackStatus?.connected ? <CheckCircle /> : <Error />}
                    label={getConnectionStatusText()}
                    color={getConnectionStatusColor()}
                    size="medium"
                  />
                  
                  {labjackStatus?.deviceInfo && (
                    <Typography variant="body2" color="text.secondary">
                      Device: {labjackStatus.deviceInfo.deviceType}
                      {labjackStatus.deviceInfo.serialNumber && ` (S/N: ${labjackStatus.deviceInfo.serialNumber})`}
                    </Typography>
                  )}
                </Box>
                
                {!labjackStatus?.connected && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    <AlertTitle>Hardware Required</AlertTitle>
                    LabJack device must be connected before starting test (PRD requirement).
                    Check device connection and drivers.
                  </Alert>
                )}
                
                {/* Embed LabJack Status Panel for detailed controls */}
                <LabJackStatusPanel 
                  onStatusChanged={(status) => {
                    setLabjackStatus({
                      connected: status.connected,
                      status: status.status as any,
                      mode: status.mode,
                      deviceInfo: status.device_info ? {
                        deviceType: status.device_info.device_type || 'Unknown',
                        serialNumber: status.device_info.serial_number
                      } : undefined,
                      signalType: SignalType.TTL,
                      voltageThreshold: status.voltage_threshold || 2.5
                    });
                  }}
                />
              </CardContent>
            </Card>

            {/* Test Configuration Section */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  3. Test Configuration
                </Typography>
                
                <TextField
                  fullWidth
                  label="Maximum Acceptable Latency (ms)"
                  type="number"
                  value={maxLatencyMs}
                  onChange={(e) => setMaxLatencyMs(Number(e.target.value))}
                  disabled={testInProgress}
                  sx={{ mb: 2 }}
                  helperText="Enter the maximum acceptable latency in milliseconds (PRD requirement)"
                  inputProps={{ min: 1, max: 10000 }}
                />
                
                {selectedProject && videoPlaylist.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Test Playlist ({videoPlaylist.length} videos)
                    </Typography>
                    <List dense>
                      {videoPlaylist.slice(0, 5).map((video, index) => (
                        <ListItem key={video.id}>
                          <ListItemIcon>
                            <VideoLibrary color={index === currentVideoIndex ? 'primary' : 'disabled'} />
                          </ListItemIcon>
                          <ListItemText
                            primary={video.filename}
                            secondary={`Duration: ${Math.round(video.duration / 1000)}s • ${video.annotationCount || 0} annotations`}
                          />
                        </ListItem>
                      ))}
                      {videoPlaylist.length > 5 && (
                        <ListItem>
                          <ListItemText primary={`... and ${videoPlaylist.length - 5} more videos`} />
                        </ListItem>
                      )}
                    </List>
                  </Box>
                )}
              </CardContent>
            </Card>
          </>
        )}

        {/* Full-Screen Video Display */}
        {testInProgress && (
          <Box
            sx={{
              width: '100%',
              height: isFullScreen ? '100vh' : '600px',
              backgroundColor: 'black',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            {videoPlaylist[currentVideoIndex] && (
              <video
                ref={videoRef}
                src={videoPlaylist[currentVideoIndex].filePath}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain'
                }}
                onEnded={handleVideoEnded}
                controls={!isFullScreen}
                autoPlay
              />
            )}
            
            {/* Full-screen controls overlay */}
            {isFullScreen && (
              <Box
                sx={{
                  position: 'absolute',
                  top: 16,
                  right: 16,
                  display: 'flex',
                  gap: 1,
                  backgroundColor: 'rgba(0,0,0,0.7)',
                  borderRadius: 2,
                  p: 1
                }}
              >
                <Tooltip title="Exit Full Screen">
                  <span>
                    <IconButton onClick={exitFullScreen} sx={{ color: 'white' }}>
                      <FullscreenExit />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title="Stop Test">
                  <span>
                    <IconButton onClick={stopTest} sx={{ color: 'white' }}>
                      <Stop />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
            )}
            
            {/* Test progress indicator */}
            {isFullScreen && (
              <Box
                sx={{
                  position: 'absolute',
                  bottom: 16,
                  left: 16,
                  right: 16,
                  backgroundColor: 'rgba(0,0,0,0.7)',
                  borderRadius: 2,
                  p: 2,
                  color: 'white'
                }}
              >
                <Typography variant="h6">
                  Video {currentVideoIndex + 1} of {videoPlaylist.length}
                </Typography>
                <Typography variant="body2">
                  {videoPlaylist[currentVideoIndex]?.filename}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={(currentVideoIndex / videoPlaylist.length) * 100}
                  sx={{ mt: 1, backgroundColor: 'rgba(255,255,255,0.3)' }}
                />
                
                {/* Real-time detection events */}
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2">
                    Events Detected: {detectionEvents.length} • 
                    Passed: {detectionEvents.filter(e => e.outcome === DetectionOutcome.PASS).length} • 
                    Failed: {detectionEvents.filter(e => e.outcome !== DetectionOutcome.PASS).length}
                  </Typography>
                </Box>
              </Box>
            )}
          </Box>
        )}

        {/* Real-time Test Results - Show when not in full-screen */}
        {testInProgress && !isFullScreen && detectionEvents.length > 0 && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Real-time Test Results
              </Typography>
              
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="primary">
                      {detectionEvents.length}
                    </Typography>
                    <Typography variant="body2">Total Events</Typography>
                  </Box>
                </Grid>
                <Grid item xs={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">
                      {detectionEvents.filter(e => e.outcome === DetectionOutcome.PASS).length}
                    </Typography>
                    <Typography variant="body2">Passed</Typography>
                  </Box>
                </Grid>
                <Grid item xs={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="error.main">
                      {detectionEvents.filter(e => e.outcome !== DetectionOutcome.PASS).length}
                    </Typography>
                    <Typography variant="body2">Failed</Typography>
                  </Box>
                </Grid>
                <Grid item xs={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="warning.main">
                      {detectionEvents.length > 0 ? Math.round(detectionEvents.reduce((sum, e) => sum + (e.latencyMs || 0), 0) / detectionEvents.length) : 0}ms
                    </Typography>
                    <Typography variant="body2">Avg Latency</Typography>
                  </Box>
                </Grid>
              </Grid>
              
              <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Time</TableCell>
                      <TableCell>Video</TableCell>
                      <TableCell>Expected</TableCell>
                      <TableCell>Received</TableCell>
                      <TableCell>Latency (ms)</TableCell>
                      <TableCell>Outcome</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {detectionEvents.slice(-10).reverse().map((event) => (
                      <TableRow key={event.id}>
                        <TableCell>
                          {new Date(event.createdAt).toLocaleTimeString()}
                        </TableCell>
                        <TableCell>
                          {videoPlaylist.find(v => v.id === String(event.videoId))?.filename || `Video ${event.videoId}`}
                        </TableCell>
                        <TableCell>
                          {new Date(event.expectedEventTime).toLocaleTimeString()}
                        </TableCell>
                        <TableCell>
                          {event.signalReceivedTime ? new Date(event.signalReceivedTime).toLocaleTimeString() : '-'}
                        </TableCell>
                        <TableCell>
                          <Typography
                            color={
                              event.latencyMs && event.latencyMs <= maxLatencyMs
                                ? 'success.main'
                                : 'error.main'
                            }
                          >
                            {event.latencyMs?.toFixed(1) || '-'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={event.outcome}
                            size="small"
                            color={event.outcome === DetectionOutcome.PASS ? 'success' : 'error'}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        )}

        {/* Start Test Confirmation Dialog */}
        <Dialog open={startTestDialog} onClose={() => setStartTestDialog(false)} maxWidth="md" fullWidth>
          <DialogTitle>Start HIL Test Execution</DialogTitle>
          <DialogContent>
            <Alert severity="info" sx={{ mb: 3 }}>
              <AlertTitle>Test Configuration Summary</AlertTitle>
              <Typography variant="body2">
                • Project: {selectedProject?.name}<br />
                • Videos: {videoPlaylist.length} validated videos<br />
                • Max Latency: {maxLatencyMs}ms<br />
                • LabJack: {getConnectionStatusText()}<br />
                • Signal Type: {labjackStatus?.signalType || 'TTL'}
              </Typography>
            </Alert>
            
            <Typography variant="body1" paragraph>
              Starting this test will:
            </Typography>
            <List>
              <ListItem>
                <ListItemIcon><PlayArrow /></ListItemIcon>
                <ListItemText primary="Switch to full-screen display mode (PRD requirement)" />
              </ListItem>
              <ListItem>
                <ListItemIcon><VideoLibrary /></ListItemIcon>
                <ListItemText primary="Play all videos sequentially" />
              </ListItem>
              <ListItem>
                <ListItemIcon><Hardware /></ListItemIcon>
                <ListItemText primary="Monitor hardware signals continuously" />
              </ListItem>
              <ListItem>
                <ListItemIcon><Timeline /></ListItemIcon>
                <ListItemText primary="Record precision timing for all events" />
              </ListItem>
              <ListItem>
                <ListItemIcon><Analytics /></ListItemIcon>
                <ListItemText primary="Generate real-time performance analysis" />
              </ListItem>
            </List>
            
            {!labjackStatus?.connected && (
              <Alert severity="error" sx={{ mt: 2 }}>
                Cannot start test: LabJack device not connected (PRD requirement)
              </Alert>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setStartTestDialog(false)}>Cancel</Button>
            <Button
              onClick={startTest}
              variant="contained"
              disabled={!labjackStatus?.connected || loading}
              startIcon={loading ? <CircularProgress size={16} /> : <PlayArrow />}
            >
              {loading ? 'Starting...' : 'Start HIL Test'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Snackbar for notifications */}
        <Snackbar
          open={!!successMessage}
          autoHideDuration={6000}
          onClose={() => setSuccessMessage(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert onClose={() => setSuccessMessage(null)} severity="success">
            {successMessage}
          </Alert>
        </Snackbar>
      </Box>
    </div>
  );
};

export default HILTestExecution;