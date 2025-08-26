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
  Paper,
  IconButton,
  Tooltip,
  Stack,
  Divider,
  Badge,
} from '@mui/material';
import { FixedGrid } from '../components/ui/FixedUIComponents';
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

import { Project, TestSession, TestResult, VideoFile } from '../services/types';
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

const EnhancedTestExecution = () => {
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedVideos, setSelectedVideos] = useState<VideoFile[]>([]);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
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
      const wsUrl = process.env.REACT_APP_WS_URL || 'ws://155.138.239.131:8001';
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
    setPlaybackState(prev => {
      if (!prev.isSequentialMode) return prev;

      const nextIndex = prev.currentVideoIndex + 1;
      
      if (nextIndex < selectedVideos.length) {
        const nextVideo = selectedVideos[nextIndex];
        showSnackbar(`Advanced to video ${nextIndex + 1} of ${selectedVideos.length}`, 'info');
        return {
          ...prev,
          currentVideoIndex: nextIndex,
          playingVideo: nextVideo,
          totalProgress: (nextIndex / selectedVideos.length) * 100,
        };
      } else if (testConfig.loopPlayback) {
        // Loop back to first video
        showSnackbar('Looping back to first video', 'info');
        return {
          ...prev,
          currentVideoIndex: 0,
          playingVideo: selectedVideos[0],
          totalProgress: 0,
        };
      } else {
        // End of sequence
        showSnackbar('Sequential playback completed', 'success');
        return {
          ...prev,
          isSequentialMode: false,
          totalProgress: 100,
        };
      }
    });
  }, [selectedVideos, testConfig.loopPlayback, showSnackbar]);

  const goToPreviousVideo = useCallback(() => {
    setPlaybackState(prev => {
      if (!prev.isSequentialMode) return prev;

      const prevIndex = Math.max(0, prev.currentVideoIndex - 1);
      const prevVideo = selectedVideos[prevIndex];
      
      showSnackbar(`Moved to video ${prevIndex + 1} of ${selectedVideos.length}`, 'info');
      return {
        ...prev,
        currentVideoIndex: prevIndex,
        playingVideo: prevVideo,
        totalProgress: (prevIndex / selectedVideos.length) * 100,
      };
    });
  }, [selectedVideos, showSnackbar]);

  const handleVideoEnd = useCallback(() => {
    if (testConfig.autoAdvance) {
      setPlaybackState(prev => {
        if (prev.isSequentialMode) {
          setTimeout(() => {
            advanceToNextVideo();
          }, testConfig.latencyMs);
        }
        return prev;
      });
    }
  }, [testConfig.autoAdvance, testConfig.latencyMs, advanceToNextVideo]);

  // Session Management Functions
  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiService.get<TestSession[]>('/api/sessions');
      setSessions(response);
    } catch (err: any) {
      setError(err.message || 'Failed to load sessions');
      showSnackbar('Failed to load sessions', 'error');
    } finally {
      setLoading(false);
    }
  }, [showSnackbar]);

  const createSession = useCallback(async () => {
    if (!sessionName.trim()) {
      showSnackbar('Session name is required', 'warning');
      return;
    }

    try {
      setLoading(true);
      const newSession = {
        name: sessionName,
        description: sessionDescription,
        projectId: selectedProject?.id,
        videoIds: selectedVideos.map(v => v.id),
        config: testConfig,
        status: 'created' as const,
        createdAt: new Date(),
      };

      const response = await apiService.post<TestSession>('/api/sessions', newSession);
      setSessions(prev => [...prev, response]);
      setCurrentSession(response);
      setSessionName('');
      setSessionDescription('');
      setSessionDialogOpen(false);
      showSnackbar('Session created successfully', 'success');
    } catch (err: any) {
      setError(err.message || 'Failed to create session');
      showSnackbar('Failed to create session', 'error');
    } finally {
      setLoading(false);
    }
  }, [sessionName, sessionDescription, selectedProject, selectedVideos, testConfig, showSnackbar]);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await apiService.delete(`/api/sessions/${sessionId}`);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (currentSession?.id === sessionId) {
        setCurrentSession(null);
      }
      showSnackbar('Session deleted successfully', 'success');
    } catch (err: any) {
      showSnackbar('Failed to delete session', 'error');
    }
  }, [currentSession, showSnackbar]);

  const startTestExecution = useCallback(async () => {
    if (!currentSession) {
      showSnackbar('Please select a session to start', 'warning');
      return;
    }

    try {
      setIsRunning(true);
      setTestResults([]);
      
      // Initialize WebSocket connection for real-time updates
      const wsUrl = process.env.REACT_APP_WS_URL || 'ws://155.138.239.131:8001';
      wsRef.current = new WebSocket(`${wsUrl}/ws/test/${currentSession.id}`);
      
      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'test_result') {
          setTestResults(prev => [...prev, data.payload]);
        } else if (data.type === 'session_complete') {
          setIsRunning(false);
          showSnackbar('Test execution completed', 'success');
        }
      };
      
      wsRef.current.onerror = () => {
        setIsRunning(false);
        showSnackbar('WebSocket connection failed', 'error');
      };

      // Start the test execution
      await apiService.post(`/api/sessions/${currentSession.id}/start`);
      showSnackbar('Test execution started', 'info');
      
    } catch (err: any) {
      setIsRunning(false);
      showSnackbar('Failed to start test execution', 'error');
    }
  }, [currentSession, showSnackbar]);

  const stopTestExecution = useCallback(async () => {
    try {
      if (currentSession) {
        await apiService.post(`/api/sessions/${currentSession.id}/stop`);
      }
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      
      setIsRunning(false);
      showSnackbar('Test execution stopped', 'info');
    } catch (err: any) {
      showSnackbar('Failed to stop test execution', 'error');
    }
  }, [currentSession, showSnackbar]);

  const exportTestResults = useCallback(() => {
    if (testResults.length === 0) {
      showSnackbar('No test results to export', 'warning');
      return;
    }

    const csvContent = [
      'Video,Status,Timestamp,Processing Time,Confidence,Details',
      ...testResults.map(result => 
        `"${result.videoName || 'Unknown'}","${result.status}","${result.timestamp}","${result.processingTime}ms","${result.confidence || 'N/A'}","${result.details || ''}"`
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `test-results-${currentSession?.name || 'session'}-${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    window.URL.revokeObjectURL(url);
    
    showSnackbar('Test results exported', 'success');
  }, [testResults, currentSession, showSnackbar]);

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
    loadSessions();
    performConnectionCheck();

    // Set up periodic connection checks
    connectionCheckInterval.current = setInterval(performConnectionCheck, 30000);

    return () => {
      if (connectionCheckInterval.current) {
        clearInterval(connectionCheckInterval.current);
      }
    };
  }, [performConnectionCheck, loadSessions, showSnackbar]);

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
          <FixedGrid container spacing={2} alignItems="center">
            <FixedGrid xs={12} sm={6} md={3}>
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
            </FixedGrid>

            <FixedGrid xs={12} sm={6} md={2}>
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
            </FixedGrid>

            <FixedGrid xs={12} sm={6} md={2}>
              <Button
                variant="outlined"
                startIcon={<VideoIcon />}
                onClick={() => setVideoSelectionOpen(true)}
                disabled={!selectedProject}
                fullWidth
              >
                Videos ({selectedVideos.length})
              </Button>
            </FixedGrid>

            <FixedGrid xs={12} sm={6} md={2}>
              <Button
                variant="outlined"
                startIcon={<SpeedIcon />}
                onClick={() => setTestConfigDialogOpen(true)}
                fullWidth
              >
                Test Config
              </Button>
            </FixedGrid>

            <FixedGrid xs={12} sm={6} md={2}>
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={() => setSessionDialogOpen(true)}
                disabled={!selectedProject || selectedVideos.length === 0}
                fullWidth
              >
                New Session
              </Button>
            </FixedGrid>

            <FixedGrid xs={12} sm={6} md={2}>
              <Stack direction="row" spacing={1}>
                {isRunning ? (
                  <Button
                    variant="contained"
                    color="error"
                    startIcon={<StopIcon />}
                    onClick={stopTestExecution}
                    fullWidth
                  >
                    Stop Test
                  </Button>
                ) : (
                  <Button
                    variant="contained"
                    startIcon={<PlayIcon />}
                    onClick={startTestExecution}
                    disabled={!currentSession}
                    fullWidth
                  >
                    Start Test
                  </Button>
                )}
              </Stack>
            </FixedGrid>
          </FixedGrid>
        </CardContent>
      </Card>

      {/* Session Management */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Sessions
          </Typography>
          
          {sessions.length === 0 ? (
            <Alert severity="info">
              No test sessions created yet. Create a new session to start testing.
            </Alert>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Paper sx={{ minWidth: 800 }}>
                {sessions.map((session) => (
                  <Box
                    key={session.id}
                    sx={{
                      p: 2,
                      borderBottom: '1px solid',
                      borderColor: 'divider',
                      bgcolor: currentSession?.id === session.id ? 'action.selected' : 'transparent',
                      cursor: 'pointer',
                      '&:hover': {
                        bgcolor: 'action.hover',
                      },
                    }}
                    onClick={() => setCurrentSession(session)}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Box sx={{ flex: 1 }}>
                        <Typography variant="subtitle1" fontWeight="medium">
                          {session.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {session.description || 'No description'}
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                          <Chip
                            label={session.status || 'created'}
                            size="small"
                            color={session.status === 'running' ? 'warning' : session.status === 'completed' ? 'success' : 'default'}
                          />
                          <Typography variant="caption" color="text.secondary">
                            Videos: {session.videoIds?.length || 0}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Created: {session.createdAt ? new Date(session.createdAt).toLocaleDateString() : 'Unknown'}
                          </Typography>
                        </Stack>
                      </Box>
                      <Stack direction="row" spacing={1}>
                        <Tooltip title="Edit Session">
                          <IconButton size="small" onClick={(e) => {
                            e.stopPropagation();
                            setSessionName(session.name);
                            setSessionDescription(session.description || '');
                            setSessionDialogOpen(true);
                          }}>
                            <EditIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete Session">
                          <IconButton 
                            size="small" 
                            color="error"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (window.confirm(`Delete session "${session.name}"?`)) {
                                deleteSession(session.id);
                              }
                            }}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </Stack>
                  </Box>
                ))}
              </Paper>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Test Results Display */}
      {testResults.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Typography variant="h6">
                Test Results ({testResults.length})
              </Typography>
              <Button
                variant="outlined"
                startIcon={<ReportIcon />}
                onClick={exportTestResults}
                size="small"
              >
                Export CSV
              </Button>
            </Stack>
            
            <Box sx={{ overflowX: 'auto' }}>
              <Paper sx={{ minWidth: 1000 }}>
                <Box sx={{ display: 'table', width: '100%' }}>
                  {/* Table Header */}
                  <Box sx={{ 
                    display: 'table-row', 
                    bgcolor: 'grey.100',
                    fontWeight: 'medium'
                  }}>
                    <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>Video</Box>
                    <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>Status</Box>
                    <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>Timestamp</Box>
                    <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>Processing Time</Box>
                    <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>Confidence</Box>
                    <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>Details</Box>
                  </Box>
                  
                  {/* Table Body */}
                  {testResults.map((result, index) => (
                    <Box key={index} sx={{ display: 'table-row' }}>
                      <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="body2">{result.videoName || 'Unknown'}</Typography>
                      </Box>
                      <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Chip
                          size="small"
                          icon={result.status === 'success' ? <CheckCircleIcon /> : result.status === 'failed' ? <ErrorIcon /> : <InfoIcon />}
                          label={result.status}
                          color={result.status === 'success' ? 'success' : result.status === 'failed' ? 'error' : 'default'}
                        />
                      </Box>
                      <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="body2">
                          {result.timestamp ? new Date(result.timestamp).toLocaleString() : 'N/A'}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="body2">{result.processingTime ? `${result.processingTime}ms` : 'N/A'}</Typography>
                      </Box>
                      <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="body2">{result.confidence ? `${(result.confidence * 100).toFixed(1)}%` : 'N/A'}</Typography>
                      </Box>
                      <Box sx={{ display: 'table-cell', p: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="body2" sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {result.details || 'No details'}
                        </Typography>
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Paper>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Test Execution Status */}
      {isRunning && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <CircularProgress size={24} />
              <Typography variant="h6">
                Test Execution in Progress
              </Typography>
            </Box>
            <LinearProgress sx={{ mb: 2 }} />
            <Typography variant="body2" color="text.secondary">
              Session: {currentSession?.name} | Videos processed: {testResults.length}
            </Typography>
          </CardContent>
        </Card>
      )}

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
          <FixedGrid container spacing={3} sx={{ mt: 1 }}>
            <FixedGrid xs={12} sm={6}>
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
            </FixedGrid>

            <FixedGrid xs={12} sm={6}>
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
            </FixedGrid>

            <FixedGrid xs={12} sm={6}>
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
            </FixedGrid>

            <FixedGrid xs={12} sm={6}>
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
            </FixedGrid>

            <FixedGrid xs={12} sm={6}>
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
            </FixedGrid>

            <FixedGrid xs={12} sm={6}>
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
            </FixedGrid>
          </FixedGrid>
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

      {/* Session Dialog */}
      <Dialog
        open={sessionDialogOpen}
        onClose={() => {
          setSessionDialogOpen(false);
          setSessionName('');
          setSessionDescription('');
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {sessionName ? 'Edit Session' : 'Create New Test Session'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            <TextField
              autoFocus
              label="Session Name"
              value={sessionName}
              onChange={(e) => setSessionName(e.target.value)}
              fullWidth
              required
              sx={{ mb: 2 }}
            />
            
            <TextField
              label="Description"
              value={sessionDescription}
              onChange={(e) => setSessionDescription(e.target.value)}
              fullWidth
              multiline
              rows={3}
              sx={{ mb: 2 }}
            />
            
            <Alert severity="info" sx={{ mb: 2 }}>
              This session will include {selectedVideos.length} videos from project "{selectedProject?.name}".
            </Alert>
            
            <Box sx={{ bgcolor: 'grey.50', p: 2, borderRadius: 1 }}>
              <Typography variant="subtitle2" gutterBottom>
                Test Configuration Summary:
              </Typography>
              <Stack direction="row" flexWrap="wrap" gap={1}>
                <Chip size="small" label={`Batch Size: ${testConfig.batchSize}`} />
                <Chip size="small" label={testConfig.concurrent ? 'Concurrent' : 'Sequential'} />
                <Chip size="small" label={testConfig.autoAdvance ? 'Auto Advance' : 'Manual'} />
                <Chip size="small" label={`Latency: ${testConfig.latencyMs}ms`} />
                {testConfig.loopPlayback && <Chip size="small" label="Loop" color="primary" />}
                {testConfig.randomOrder && <Chip size="small" label="Random" color="secondary" />}
              </Stack>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setSessionDialogOpen(false);
            setSessionName('');
            setSessionDescription('');
          }}>
            Cancel
          </Button>
          <Button 
            onClick={createSession} 
            variant="contained"
            disabled={!sessionName.trim() || loading}
            startIcon={loading ? <CircularProgress size={16} /> : undefined}
          >
            {sessionName ? 'Update Session' : 'Create Session'}
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