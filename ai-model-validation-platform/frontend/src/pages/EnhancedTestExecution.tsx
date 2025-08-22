import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  LinearProgress,
  Alert,
  Snackbar,
  Switch,
  FormControlLabel,
  CircularProgress,
  Grid,
  Paper,
  IconButton,
  Tooltip,
  Stack,
  Divider,
  Badge,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Assessment as ReportIcon,
  VideoLibrary as VideoIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  NetworkCheck as NetworkCheckIcon,
  Sync as SyncIcon,
  SkipNext as SkipNextIcon,
  SkipPrevious as SkipPreviousIcon,
  Shuffle as ShuffleIcon,
  Loop as LoopIcon,
  Speed as SpeedIcon,
  Timeline as TimelineIcon,
  Wifi as WifiIcon,
  WifiOff as WifiOffIcon,
} from '@mui/icons-material';

import { Project, TestSession, VideoFile } from '../services/types';
import { apiService } from '../services/api';
import VideoSelectionDialog from '../components/VideoSelectionDialog';
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';

interface TestConfiguration {
  batchSize: number;
  concurrent: boolean;
  saveIntermediateResults: boolean;
  generateReport: boolean;
  sequentialPlayback: boolean;
  autoAdvance: boolean;
  latencyMs: number;
  syncExternalSignals: boolean;
  loopPlayback: boolean;
  randomOrder: boolean;
}

interface ConnectionStatus {
  api: 'connected' | 'disconnected' | 'checking';
  websocket: 'connected' | 'disconnected' | 'checking';
  latency: number;
  lastCheck: Date;
}

interface PlaybackState {
  currentVideoIndex: number;
  playingVideo: VideoFile | null;
  isSequentialMode: boolean;
  totalProgress: number;
  videoProgress: Record<string, number>;
}

const EnhancedTestExecution: React.FC = () => {
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedVideos, setSelectedVideos] = useState<VideoFile[]>([]);
  const [testResults, setTestResults] = useState<any[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentSession, setCurrentSession] = useState<TestSession | null>(null);
  
  // Enhanced test configuration
  const [testConfig, setTestConfig] = useState<TestConfiguration>({
    batchSize: 1,
    concurrent: false,
    saveIntermediateResults: true,
    generateReport: true,
    sequentialPlayback: true,
    autoAdvance: true,
    latencyMs: 100,
    syncExternalSignals: false,
    loopPlayback: false,
    randomOrder: false,
  });

  // Connection status
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    api: 'disconnected',
    websocket: 'disconnected',
    latency: 0,
    lastCheck: new Date(),
  });

  // Playback state for sequential mode
  const [playbackState, setPlaybackState] = useState<PlaybackState>({
    currentVideoIndex: 0,
    playingVideo: null,
    isSequentialMode: false,
    totalProgress: 0,
    videoProgress: {},
  });

  // Dialog states
  const [videoSelectionOpen, setVideoSelectionOpen] = useState(false);
  const [sessionDialogOpen, setSessionDialogOpen] = useState(false);
  const [testConfigDialogOpen, setTestConfigDialogOpen] = useState(false);

  // Form states
  const [sessionName, setSessionName] = useState('');
  const [sessionDescription, setSessionDescription] = useState('');

  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error' | 'warning' | 'info'>('info');

  const wsRef = useRef<WebSocket | null>(null);
  const connectionCheckInterval = useRef<NodeJS.Timeout | null>(null);

  // Helper functions
  const showSnackbar = useCallback((message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  }, []);

  // Connection checking
  const checkAPIConnection = useCallback(async () => {
    setConnectionStatus(prev => ({ ...prev, api: 'checking' }));
    const startTime = Date.now();
    
    try {
      await apiService.get('/api/health');
      const latency = Date.now() - startTime;
      setConnectionStatus(prev => ({
        ...prev,
        api: 'connected',
        latency,
        lastCheck: new Date(),
      }));
      return true;
    } catch (error) {
      setConnectionStatus(prev => ({
        ...prev,
        api: 'disconnected',
        lastCheck: new Date(),
      }));
      return false;
    }
  }, []);

  const checkWebSocketConnection = useCallback(() => {
    setConnectionStatus(prev => ({ ...prev, websocket: 'checking' }));
    
    try {
      const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8001';
      const testWs = new WebSocket(`${wsUrl}/ws/test`);
      
      testWs.onopen = () => {
        setConnectionStatus(prev => ({ ...prev, websocket: 'connected' }));
        testWs.close();
      };
      
      testWs.onerror = () => {
        setConnectionStatus(prev => ({ ...prev, websocket: 'disconnected' }));
      };
      
      setTimeout(() => {
        if (testWs.readyState === WebSocket.CONNECTING) {
          testWs.close();
          setConnectionStatus(prev => ({ ...prev, websocket: 'disconnected' }));
        }
      }, 5000);
    } catch (error) {
      setConnectionStatus(prev => ({ ...prev, websocket: 'disconnected' }));
    }
  }, []);

  const performConnectionCheck = useCallback(async () => {
    await Promise.all([checkAPIConnection(), checkWebSocketConnection()]);
  }, [checkAPIConnection, checkWebSocketConnection]);

  // Sequential playback logic
  const initializeSequentialPlayback = useCallback(() => {
    if (selectedVideos.length === 0) return;

    const orderedVideos = testConfig.randomOrder 
      ? [...selectedVideos].sort(() => Math.random() - 0.5)
      : selectedVideos;

    setPlaybackState({
      currentVideoIndex: 0,
      playingVideo: orderedVideos[0],
      isSequentialMode: true,
      totalProgress: 0,
      videoProgress: {},
    });
  }, [selectedVideos, testConfig.randomOrder]);

  const advanceToNextVideo = useCallback(() => {
    if (!playbackState.isSequentialMode) return;

    const nextIndex = playbackState.currentVideoIndex + 1;
    
    if (nextIndex < selectedVideos.length) {
      const nextVideo = selectedVideos[nextIndex];
      setPlaybackState(prev => ({
        ...prev,
        currentVideoIndex: nextIndex,
        playingVideo: nextVideo,
        totalProgress: (nextIndex / selectedVideos.length) * 100,
      }));
      showSnackbar(`Advanced to video ${nextIndex + 1} of ${selectedVideos.length}`, 'info');
    } else if (testConfig.loopPlayback) {
      // Loop back to first video
      setPlaybackState(prev => ({
        ...prev,
        currentVideoIndex: 0,
        playingVideo: selectedVideos[0],
        totalProgress: 0,
      }));
      showSnackbar('Looping back to first video', 'info');
    } else {
      // End of sequence
      setPlaybackState(prev => ({
        ...prev,
        isSequentialMode: false,
        totalProgress: 100,
      }));
      showSnackbar('Sequential playback completed', 'success');
    }
  }, [playbackState, selectedVideos, testConfig.loopPlayback, showSnackbar]);

  const goToPreviousVideo = useCallback(() => {
    if (!playbackState.isSequentialMode) return;

    const prevIndex = Math.max(0, playbackState.currentVideoIndex - 1);
    const prevVideo = selectedVideos[prevIndex];
    
    setPlaybackState(prev => ({
      ...prev,
      currentVideoIndex: prevIndex,
      playingVideo: prevVideo,
      totalProgress: (prevIndex / selectedVideos.length) * 100,
    }));
    showSnackbar(`Moved to video ${prevIndex + 1} of ${selectedVideos.length}`, 'info');
  }, [playbackState, selectedVideos, showSnackbar]);

  const handleVideoEnd = useCallback(() => {
    if (testConfig.autoAdvance && playbackState.isSequentialMode) {
      setTimeout(() => {
        advanceToNextVideo();
      }, testConfig.latencyMs);
    }
  }, [testConfig.autoAdvance, testConfig.latencyMs, playbackState.isSequentialMode, advanceToNextVideo]);

  // Load projects and start connection monitoring
  useEffect(() => {
    const loadProjects = async () => {
      try {
        setLoading(true);
        const response = await apiService.get<Project[]>('/api/projects');
        setProjects(response);
        if (response.length > 0) {
          setSelectedProject(response[0]);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load projects');
        showSnackbar('Failed to load projects', 'error');
      } finally {
        setLoading(false);
      }
    };

    loadProjects();
    performConnectionCheck();

    // Set up periodic connection checks
    connectionCheckInterval.current = setInterval(performConnectionCheck, 30000);

    return () => {
      if (connectionCheckInterval.current) {
        clearInterval(connectionCheckInterval.current);
      }
    };
  }, [performConnectionCheck, showSnackbar]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const getConnectionIcon = (status: string) => {
    switch (status) {
      case 'connected': return <WifiIcon color="success" />;
      case 'disconnected': return <WifiOffIcon color="error" />;
      case 'checking': return <CircularProgress size={20} />;
      default: return <WifiOffIcon color="disabled" />;
    }
  };

  const formatLatency = (latency: number) => {
    if (latency < 100) return `${latency}ms`;
    if (latency < 1000) return `${latency}ms`;
    return `${(latency / 1000).toFixed(1)}s`;
  };

  return (
    <Box sx={{ p: { xs: 1, sm: 2, md: 3 } }}>
      {/* Header */}
      <Box sx={{ 
        display: 'flex', 
        flexDirection: { xs: 'column', sm: 'row' },
        justifyContent: 'space-between', 
        alignItems: { xs: 'stretch', sm: 'center' }, 
        mb: 3,
        gap: { xs: 2, sm: 0 }
      }}>
        <Typography 
          variant="h4" 
          component="h1"
          sx={{ 
            fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem' },
            textAlign: { xs: 'center', sm: 'left' }
          }}
        >
          Enhanced Test Execution
        </Typography>
        
        {/* Connection Status */}
        <Card sx={{ 
          minWidth: { xs: '100%', sm: 300 },
          bgcolor: 'background.paper'
        }}>
          <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
            <Stack direction="row" spacing={2} alignItems="center">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {getConnectionIcon(connectionStatus.api)}
                <Typography variant="caption">API</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {getConnectionIcon(connectionStatus.websocket)}
                <Typography variant="caption">WebSocket</Typography>
              </Box>
              <Divider orientation="vertical" flexItem />
              <Typography variant="caption">
                {formatLatency(connectionStatus.latency)}
              </Typography>
              <Tooltip title="Check Connection">
                <IconButton size="small" onClick={performConnectionCheck}>
                  <NetworkCheckIcon />
                </IconButton>
              </Tooltip>
            </Stack>
          </CardContent>
        </Card>
      </Box>

      {/* Project Selection and Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth>
                <InputLabel>Project</InputLabel>
                <Select
                  value={selectedProject?.id || ''}
                  onChange={(e) => {
                    const project = projects.find(p => p.id === e.target.value);
                    setSelectedProject(project || null);
                  }}
                >
                  {projects.map((project) => (
                    <MenuItem key={project.id} value={project.id}>
                      {project.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <TextField
                label="Latency (ms)"
                type="number"
                value={testConfig.latencyMs}
                onChange={(e) => setTestConfig(prev => ({ 
                  ...prev, 
                  latencyMs: parseInt(e.target.value) || 100 
                }))}
                InputProps={{ inputProps: { min: 0, max: 5000 } }}
                fullWidth
                size="small"
              />
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <Button
                variant="outlined"
                startIcon={<VideoIcon />}
                onClick={() => setVideoSelectionOpen(true)}
                disabled={!selectedProject}
                fullWidth
              >
                Videos ({selectedVideos.length})
              </Button>
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <Button
                variant="outlined"
                startIcon={<SpeedIcon />}
                onClick={() => setTestConfigDialogOpen(true)}
                fullWidth
              >
                Test Config
              </Button>
            </Grid>

            <Grid item xs={12} sm={12} md={3}>
              <Stack direction="row" spacing={1}>
                <Button
                  variant="contained"
                  startIcon={<PlayIcon />}
                  onClick={initializeSequentialPlayback}
                  disabled={!selectedProject || selectedVideos.length === 0}
                  fullWidth
                >
                  Start Sequential
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Sequential Playback Controls */}
      {playbackState.isSequentialMode && playbackState.playingVideo && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Sequential Playback - Video {playbackState.currentVideoIndex + 1} of {selectedVideos.length}
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={playbackState.totalProgress} 
                sx={{ mb: 2 }}
              />
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
                <Tooltip title="Previous Video">
                  <IconButton 
                    onClick={goToPreviousVideo}
                    disabled={playbackState.currentVideoIndex === 0}
                  >
                    <SkipPreviousIcon />
                  </IconButton>
                </Tooltip>
                
                <Chip 
                  label={playbackState.playingVideo.filename || 'Current Video'}
                  variant="outlined"
                />
                
                <Tooltip title="Next Video">
                  <IconButton 
                    onClick={advanceToNextVideo}
                    disabled={playbackState.currentVideoIndex === selectedVideos.length - 1 && !testConfig.loopPlayback}
                  >
                    <SkipNextIcon />
                  </IconButton>
                </Tooltip>

                {testConfig.syncExternalSignals && (
                  <Tooltip title="Sync External Signals">
                    <IconButton color="primary">
                      <SyncIcon />
                    </IconButton>
                  </Tooltip>
                )}
              </Stack>
            </Box>

            {/* Video Player */}
            <VideoAnnotationPlayer
              video={playbackState.playingVideo}
              annotations={[]}
              annotationMode={false}
              frameRate={30}
              onVideoEnd={handleVideoEnd}
              enableFullscreen={true}
              syncIndicator={testConfig.syncExternalSignals}
              externalTimeSync={testConfig.syncExternalSignals ? Date.now() : undefined}
            />
          </CardContent>
        </Card>
      )}

      {/* Test Configuration Dialog */}
      <Dialog
        open={testConfigDialogOpen}
        onClose={() => setTestConfigDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Test Configuration</DialogTitle>
        <DialogContent>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={testConfig.sequentialPlayback}
                    onChange={(e) => setTestConfig(prev => ({ 
                      ...prev, 
                      sequentialPlayback: e.target.checked 
                    }))}
                  />
                }
                label="Sequential Playback"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={testConfig.autoAdvance}
                    onChange={(e) => setTestConfig(prev => ({ 
                      ...prev, 
                      autoAdvance: e.target.checked 
                    }))}
                  />
                }
                label="Auto Advance Videos"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={testConfig.loopPlayback}
                    onChange={(e) => setTestConfig(prev => ({ 
                      ...prev, 
                      loopPlayback: e.target.checked 
                    }))}
                  />
                }
                label="Loop Playback"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={testConfig.randomOrder}
                    onChange={(e) => setTestConfig(prev => ({ 
                      ...prev, 
                      randomOrder: e.target.checked 
                    }))}
                  />
                }
                label="Random Order"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={testConfig.syncExternalSignals}
                    onChange={(e) => setTestConfig(prev => ({ 
                      ...prev, 
                      syncExternalSignals: e.target.checked 
                    }))}
                  />
                }
                label="Sync External Signals"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                label="Advance Delay (ms)"
                type="number"
                value={testConfig.latencyMs}
                onChange={(e) => setTestConfig(prev => ({ 
                  ...prev, 
                  latencyMs: parseInt(e.target.value) || 100 
                }))}
                InputProps={{ inputProps: { min: 0, max: 10000 } }}
                fullWidth
                helperText="Delay between video transitions"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTestConfigDialogOpen(false)}>
            Cancel
          </Button>
          <Button onClick={() => setTestConfigDialogOpen(false)} variant="contained">
            Save Configuration
          </Button>
        </DialogActions>
      </Dialog>

      {/* Video Selection Dialog */}
      {selectedProject && (
        <VideoSelectionDialog
          open={videoSelectionOpen}
          onClose={() => setVideoSelectionOpen(false)}
          projectId={selectedProject.id}
          onSelectionComplete={(videos: VideoFile[]) => {
            setSelectedVideos(videos);
            showSnackbar(`${videos.length} videos selected`, 'success');
          }}
          selectedVideoIds={selectedVideos.map(v => v.id)}
        />
      )}

      {/* Snackbar */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
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
  );
};

export default EnhancedTestExecution;