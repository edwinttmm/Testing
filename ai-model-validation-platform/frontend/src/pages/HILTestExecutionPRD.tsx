import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Alert,
  Chip,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Stack,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Fullscreen as FullscreenIcon,
} from '@mui/icons-material';

import { Project, VideoFile } from '../services/types';
import { apiService } from '../services/api';
import { markUserInteraction } from '../utils/videoUtils';
import SimpleLabJackStatus from '../components/SimpleLabJackStatus';

// PRD-compliant interfaces with exact variable names
interface HILTestSession {
  id: string;
  projectId: string;
  testStartTime: Date | null; // PRD: Test_Start_Time at exact video playback start
  maxLatencyMs: number; // PRD: User-defined maximum acceptable latency
  labjackConnected: boolean;
  status: 'pending' | 'running' | 'completed' | 'failed';
  videoPlaylist: VideoFile[];
}

interface LabJackConnectionStatus {
  connected: boolean;
  status: 'connected' | 'disconnected' | 'checking' | 'error';
  deviceInfo?: {
    deviceType: string;
    serialNumber?: string;
  };
  error?: string;
}

interface DetectionEvent {
  expectedEventTime: Date; // PRD: Expected_Event_Time relative to Test_Start_Time
  signalReceivedTime?: Date; // PRD: Signal_Received_Time from LabJack
  latencyMs?: number; // PRD: Calculated latency
  outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection';
  videoId: string;
  frameNumber?: number;
}

const HILTestExecutionPRD: React.FC = () => {
  // Core state (PRD-aligned)
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [videoPlaylist, setVideoPlaylist] = useState<VideoFile[]>([]);
  const [maxLatencyMs, setMaxLatencyMs] = useState<number>(100); // PRD: Default 100ms
  const [labjackStatus, setLabjackStatus] = useState<LabJackConnectionStatus>({
    connected: false,
    status: 'checking'
  });
  
  // Test execution state
  const [currentSession, setCurrentSession] = useState<HILTestSession | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [detectionEvents, setDetectionEvents] = useState<DetectionEvent[]>([]);
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startTestDialog, setStartTestDialog] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error' | 'warning' | 'info'>('info');
  
  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const fullscreenContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Helper function
  const showSnackbar = useCallback((message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  }, []);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Poll for video status updates
  useEffect(() => {
    const isProcessing = videoPlaylist.some(video => video.processing_status === 'processing' || video.processing_status === 'pending');

    if (selectedProject && isProcessing) {
      const interval = setInterval(() => {
        loadVideoPlaylist(selectedProject);
      }, 5000); // Poll every 5 seconds

      return () => clearInterval(interval);
    }
  }, [selectedProject, videoPlaylist]);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const projects = await apiService.getProjects();
      setProjects(projects);
    } catch (err: any) {
      setError(`Failed to load projects: ${err.message}`);
      showSnackbar('Failed to load projects', 'error');
    } finally {
      setLoading(false);
    }
  };


  // Load video playlist for selected project (PRD requirement)
  const loadVideoPlaylist = async (project: Project) => {
    try {
      setLoading(true);
            const response = await apiService.get<VideoFile[]>(`/api/projects/${project.id}/videos`);
      setVideoPlaylist(response);
    } catch (err: any) {
      setError(`Failed to load video playlist: ${err.message}`);
      showSnackbar('Failed to load videos', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleProjectSelect = (project: Project) => {
    setSelectedProject(project);
    loadVideoPlaylist(project);
    setError(null);
  };

  const validatedVideos = videoPlaylist.filter(video => video.processing_status === 'completed');

  // PRD: Validate test start conditions
  const canStartTest = (): { canStart: boolean; reasons: string[] } => {
    const reasons: string[] = [];
    
    if (!selectedProject) {
      reasons.push('Please select a Project');
    }
    
    if (validatedVideos.length === 0) {
      reasons.push('Project has no validated videos');
    }
    
    if (!labjackStatus.connected) {
      reasons.push('LabJack DAQ device not connected'); // PRD requirement
    }
    
    if (!maxLatencyMs || maxLatencyMs <= 0) {
      reasons.push('Please enter maximum acceptable latency');
    }
    
    return {
      canStart: reasons.length === 0,
      reasons
    };
  };

  // PRD: Start HIL test execution
  const startTest = async () => {
    const validation = canStartTest();
    if (!validation.canStart) {
      setError(validation.reasons.join('. '));
      return;
    }

    try {
      // Mark user interaction for autoplay permissions
      markUserInteraction();
      
      setTestRunning(true);
      setStartTestDialog(false);
      setDetectionEvents([]);
      
      // Create test session
      const session: HILTestSession = {
        id: `session_${Date.now()}`,
        projectId: selectedProject!.id,
        testStartTime: null, // Will be set when video starts
        maxLatencyMs,
        labjackConnected: labjackStatus.connected,
        status: 'running',
        videoPlaylist
      };
      setCurrentSession(session);
      
      // PRD: Switch to full-screen immediately
      await enterFullScreen();
      
      // Start video playback - this will trigger precision timing capture
      if (videoRef.current && videoPlaylist[0]) {
        videoRef.current.src = videoPlaylist[0].filePath || videoPlaylist[0].url || '';
        videoRef.current.currentTime = 0;
        await videoRef.current.play();
      }
      
      // Initialize WebSocket for LabJack signal monitoring
      initializeSignalMonitoring(session);
      
      showSnackbar('HIL Test Started - Full Screen Mode Active', 'success');
      
    } catch (err: any) {
      setTestRunning(false);
      setError(`Failed to start test: ${err.message}`);
      showSnackbar('Failed to start test', 'error');
    }
  };

  // PRD: Full-screen mode (required)
  const enterFullScreen = async () => {
    if (fullscreenContainerRef.current) {
      try {
        if (fullscreenContainerRef.current.requestFullscreen) {
          await fullscreenContainerRef.current.requestFullscreen();
        } else if ((fullscreenContainerRef.current as any).webkitRequestFullscreen) {
          await (fullscreenContainerRef.current as any).webkitRequestFullscreen();
        } else if ((fullscreenContainerRef.current as any).msRequestFullscreen) {
          await (fullscreenContainerRef.current as any).msRequestFullscreen();
        }
        setIsFullScreen(true);
      } catch (err) {
        console.warn('Fullscreen failed:', err);
        showSnackbar('Fullscreen not available, continuing in window mode', 'warning');
      }
    }
  };

  const exitFullScreen = async () => {
    try {
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if ((document as any).webkitExitFullscreen) {
        await (document as any).webkitExitFullscreen();
      }
      setIsFullScreen(false);
    } catch (err) {
      console.warn('Exit fullscreen failed:', err);
    }
  };

  // PRD: Capture Test_Start_Time at exact video playback start
  const handleVideoStart = () => {
    if (currentSession) {
      const testStartTime = new Date(); // PRD: High-precision Test_Start_Time
      setCurrentSession(prev => prev ? { ...prev, testStartTime } : null);
      console.log('HIL Test - Precision Test_Start_Time captured:', testStartTime.toISOString());
      showSnackbar('Precision timing started', 'success');
    }
  };

  // Initialize LabJack signal monitoring via WebSocket
  const initializeSignalMonitoring = (session: HILTestSession) => {
    const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8001';
    wsRef.current = new WebSocket(`${wsUrl}/ws/labjack-signals/${session.id}`);
    
    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleLabJackSignal(data);
      } catch (err) {
        console.error('WebSocket message error:', err);
      }
    };
    
    wsRef.current.onerror = (error) => {
      console.error('LabJack WebSocket error:', error);
      showSnackbar('Signal monitoring error', 'error');
    };
    
    wsRef.current.onclose = () => {
      if (testRunning) {
        showSnackbar('Signal monitoring disconnected', 'warning');
      }
    };
  };

  // PRD: Handle LabJack signal detection
  const handleLabJackSignal = (signalData: any) => {
    if (!currentSession || !currentSession.testStartTime) return;
    
    const signalReceivedTime = new Date(signalData.timestamp);
    const expectedEventTime = new Date(currentSession.testStartTime.getTime() + signalData.expectedOffset);
    const latencyMs = signalReceivedTime.getTime() - expectedEventTime.getTime();
    
    // PRD: Determine outcome based on latency threshold
    let outcome: 'pass' | 'fail_high_latency' | 'fail_missed_detection' = 'pass';
    if (latencyMs > maxLatencyMs) {
      outcome = 'fail_high_latency';
    }
    
    const event: DetectionEvent = {
      expectedEventTime,
      signalReceivedTime,
      latencyMs,
      outcome,
      videoId: signalData.videoId,
      frameNumber: signalData.frameNumber
    };
    
    setDetectionEvents(prev => [...prev, event]);
    
    // Show real-time feedback
    const status = outcome === 'pass' ? 'success' : 'error';
    showSnackbar(
      `Detection: ${latencyMs.toFixed(1)}ms latency - ${outcome.toUpperCase()}`,
      status
    );
  };

  const stopTest = async () => {
    try {
      setTestRunning(false);
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      
      if (videoRef.current) {
        videoRef.current.pause();
      }
      
      await exitFullScreen();
      
      if (currentSession) {
        setCurrentSession(prev => prev ? { ...prev, status: 'completed' } : null);
      }
      
      showSnackbar('Test stopped successfully', 'info');
      
    } catch (err: any) {
      showSnackbar('Failed to stop test', 'error');
    }
  };

  // ESC key handler for stopping test
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && testRunning) {
        event.preventDefault();
        stopTest();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [testRunning]);

  // Fullscreen change listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullScreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
    };
  }, []);


  return (
    <div ref={fullscreenContainerRef}>
      <Box sx={{ p: isFullScreen ? 0 : 3 }}>
        {/* Hide UI in full-screen mode */}
        {!isFullScreen && (
          <>
            {/* Header */}
            <Typography variant="h4" gutterBottom>
              HIL Test Execution
            </Typography>

            {/* Error Alert */}
            {error && (
              <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            {/* Main Test Setup Card */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Test Setup
                </Typography>

                {/* 1. Project Selection (PRD requirement) */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    1. Project Selection
                  </Typography>
                  <FormControl fullWidth sx={{ mb: 1 }}>
                    <InputLabel>Select Project</InputLabel>
                    <Select
                      value={selectedProject?.id || ''}
                      onChange={(e) => {
                        const project = projects.find(p => p.id === e.target.value);
                        if (project) handleProjectSelect(project);
                      }}
                      disabled={testRunning}
                    >
                      {Array.isArray(projects) && projects.map((project) => (
                        <MenuItem key={project.id} value={project.id}>
                          {project.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  
                  {selectedProject && (
                    <Typography variant="body2" color="text.secondary">
                      Video Playlist: {validatedVideos.length} validated videos
                    </Typography>
                  )}
                </Box>

                {/* 2. LabJack Connection Status (PRD requirement) */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    2. Hardware Connection Status
                  </Typography>
                  <SimpleLabJackStatus
                    onStatusChange={(status) => setLabjackStatus(status)}
                    showRefreshButton={true}
                  />
                </Box>

                {/* 3. Latency Input (PRD requirement) */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    3. Maximum Acceptable Latency
                  </Typography>
                  <TextField
                    label="Maximum Latency (ms)"
                    type="number"
                    value={maxLatencyMs}
                    onChange={(e) => setMaxLatencyMs(Number(e.target.value) || 100)}
                    disabled={testRunning}
                    inputProps={{ min: 1, max: 10000 }}
                    helperText="Enter maximum acceptable latency in milliseconds (PRD requirement)"
                    sx={{ maxWidth: 300 }}
                  />
                </Box>

                {/* Start Test Button */}
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                  <Button
                    variant="contained"
                    size="large"
                    startIcon={<PlayIcon />}
                    onClick={() => setStartTestDialog(true)}
                    disabled={!canStartTest().canStart || testRunning || loading}
                  >
                    Start HIL Test
                  </Button>
                  
                  {testRunning && (
                    <Button
                      variant="contained"
                      color="error"
                      startIcon={<StopIcon />}
                      onClick={stopTest}
                    >
                      Stop Test
                    </Button>
                  )}
                </Box>

                {/* Validation Messages */}
                {!canStartTest().canStart && (
                  <Box sx={{ mt: 2 }}>
                    {canStartTest().reasons.map((reason, index) => (
                      <Alert key={index} severity="warning" sx={{ mt: 1 }}>
                        {reason}
                      </Alert>
                    ))}
                  </Box>
                )}
              </CardContent>
            </Card>

            {/* Test Results (Real-time) */}
            {detectionEvents.length > 0 && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Test Results ({detectionEvents.length} events)
                  </Typography>
                  
                  {/* Summary Statistics */}
                  <Box sx={{ mb: 2 }}>
                    {(() => {
                      const passed = detectionEvents.filter(e => e.outcome === 'pass').length;
                      const failed = detectionEvents.length - passed;
                      const passRate = detectionEvents.length > 0 ? (passed / detectionEvents.length) * 100 : 0;
                      const avgLatency = detectionEvents.length > 0 
                        ? detectionEvents.reduce((sum, e) => sum + (e.latencyMs || 0), 0) / detectionEvents.length 
                        : 0;
                      
                      return (
                        <Stack direction="row" spacing={4}>
                          <Typography variant="body1">
                            <strong>Passed:</strong> {passed}
                          </Typography>
                          <Typography variant="body1">
                            <strong>Failed:</strong> {failed}
                          </Typography>
                          <Typography variant="body1">
                            <strong>Pass Rate:</strong> {passRate.toFixed(1)}%
                          </Typography>
                          <Typography variant="body1">
                            <strong>Avg Latency:</strong> {avgLatency.toFixed(1)}ms
                          </Typography>
                        </Stack>
                      );
                    })()}
                  </Box>
                  
                  <LinearProgress
                    variant="determinate"
                    value={detectionEvents.length > 0 ? (detectionEvents.filter(e => e.outcome === 'pass').length / detectionEvents.length) * 100 : 0}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* Full-Screen Video Player (PRD requirement) */}
        {testRunning && (
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
            {videoPlaylist[0] && (
              <video
                ref={videoRef}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain'
                }}
                onPlay={handleVideoStart} // PRD: Capture Test_Start_Time
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
                  borderRadius: 1,
                  p: 1
                }}
              >
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={stopTest}
                  sx={{ color: 'white' }}
                >
                  Stop Test
                </Button>
              </Box>
            )}
            
            {/* Test progress indicator */}
            {isFullScreen && currentSession && (
              <Box
                sx={{
                  position: 'absolute',
                  bottom: 16,
                  left: 16,
                  right: 16,
                  backgroundColor: 'rgba(0,0,0,0.8)',
                  borderRadius: 1,
                  p: 2,
                  color: 'white'
                }}
              >
                <Typography variant="h6">
                  HIL Test Running
                </Typography>
                <Typography variant="body2">
                  Project: {selectedProject?.name} | Max Latency: {maxLatencyMs}ms
                </Typography>
                <Typography variant="body2">
                  Events: {detectionEvents.length} | 
                  Passed: {detectionEvents.filter(e => e.outcome === 'pass').length}
                </Typography>
                <LinearProgress sx={{ mt: 1, backgroundColor: 'rgba(255,255,255,0.3)' }} />
              </Box>
            )}
          </Box>
        )}

        {/* Start Test Confirmation Dialog */}
        <Dialog open={startTestDialog} onClose={() => setStartTestDialog(false)} maxWidth="md">
          <DialogTitle>Start HIL Test Execution</DialogTitle>
          <DialogContent>
            <Typography variant="body1" paragraph>
              Ready to start HIL test with the following configuration:
            </Typography>
            
            <Box sx={{ bgcolor: 'grey.50', p: 2, borderRadius: 1, mb: 2 }}>
              <Typography variant="body2">
                • <strong>Project:</strong> {selectedProject?.name}<br />
                • <strong>Videos:</strong> {videoPlaylist.length} validated videos<br />
                • <strong>Max Latency:</strong> {maxLatencyMs}ms<br />
                • <strong>LabJack Status:</strong> {labjackStatus.connected ? 'Connected' : 'Not Detected'}<br />
              </Typography>
            </Box>
            
            <Typography variant="body1">
              The test will immediately switch to full-screen mode and begin video playback 
              with precision timing capture (PRD requirement).
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setStartTestDialog(false)}>Cancel</Button>
            <Button
              onClick={startTest}
              variant="contained"
              disabled={!canStartTest().canStart}
              startIcon={<FullscreenIcon />}
            >
              Start Full-Screen Test
            </Button>
          </DialogActions>
        </Dialog>

        {/* Snackbar */}
        <Snackbar
          open={snackbarOpen}
          autoHideDuration={4000}
          onClose={() => setSnackbarOpen(false)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert
            onClose={() => setSnackbarOpen(false)}
            severity={snackbarSeverity}
            sx={{ width: '100%' }}
          >
            {snackbarMessage}
          </Alert>
        </Snackbar>
      </Box>
    </div>
  );
};

export default HILTestExecutionPRD;