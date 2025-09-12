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
  Tabs,
  Tab,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Paper,
  Tooltip,
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
  Timeline as TimelineIcon,
  Speed as SpeedIcon,
  DataUsage as DataUsageIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';

import { 
  Project, 
  TestSession, 
  VideoFile,
  ExtendedProject,
  ChipColor,
  ModelConfiguration,
  LabJackStatus,
} from '../services/types';
import { apiService } from '../services/api';
import VideoSelectionDialog from '../components/VideoSelectionDialog';
import LabJackStatusPanel from '../components/LabJackStatusPanel';
import { TestConfiguration, TestResult } from '../types/common';

interface StreamingData {
  data: number[];
  timestamp: number;
  sample_rate: number;
  channels: string[];
}


interface TestResults {
  id: string;
  sessionId: string;
  videoId: string;
  modelConfig: ModelConfiguration;
  results: {
    accuracy: number;
    precision: number;
    recall: number;
    f1Score: number;
    detections: Record<string, unknown>[];
    processingTime: number;
    errorCount: number;
  };
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  startedAt: string;
  completedAt?: string;
  error?: string;
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
      id={`test-execution-tabpanel-${index}`}
      aria-labelledby={`test-execution-tab-${index}`}
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

const TestExecutionEnhanced: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedVideos, setSelectedVideos] = useState<VideoFile[]>([]);
  const [testResults, setTestResults] = useState<TestResults[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentSession, setCurrentSession] = useState<TestSession | null>(null);
  
  // LabJack integration state
  const [labJackStatus, setLabJackStatus] = useState<LabJackStatus | null>(null);
  const [streamingData, setStreamingData] = useState<number[]>([]);
  const [signalValidationEnabled, setSignalValidationEnabled] = useState(false);
  const [detectedSignals, setDetectedSignals] = useState<Array<{
    timestamp: number;
    channel: string;
    voltage: number;
    type: 'detection' | 'validation' | 'sync';
  }>>([]);
  
  // Dialog states
  const [videoSelectionOpen, setVideoSelectionOpen] = useState(false);
  const [sessionDialogOpen, setSessionDialogOpen] = useState(false);
  
  // Form states
  const [sessionName, setSessionName] = useState('');
  const [sessionDescription, setSessionDescription] = useState('');
  const [testConfig, setTestConfig] = useState({
    batchSize: 1,
    concurrent: false,
    saveIntermediateResults: true,
    generateReport: true,
    enableLabJackValidation: false,
    voltageThreshold: 2.5,
  });
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error' | 'warning' | 'info'>('info');

  const wsRef = useRef<WebSocket | null>(null);

  // Helper functions
  const showSnackbar = useCallback((message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  }, []);

  const updateTestProgress = useCallback((progress: Record<string, unknown>) => {
    console.log('Test progress:', progress);
  }, []);

  const addTestResult = useCallback((result: TestResults) => {
    setTestResults(prev => [...prev, result]);
  }, []);

  const handleTestCompletion = useCallback((data: Record<string, unknown>) => {
    setIsRunning(false);
    showSnackbar('Test execution completed', 'success');
    
    setSessions(prevSessions =>
      prevSessions.map(s => 
        s.id === currentSession?.id ? { ...s, status: 'completed' as const } : s
      )
    );
  }, [currentSession?.id, showSnackbar]);

  const handleTestError = useCallback((error: Error | unknown) => {
    setIsRunning(false);
    const message = error instanceof Error ? error.message : 'Unknown error';
    showSnackbar(`Test execution failed: ${message}`, 'error');
    
    setSessions(prevSessions =>
      prevSessions.map(s => 
        s.id === currentSession?.id ? { ...s, status: 'failed' as const } : s
      )
    );
  }, [currentSession?.id, showSnackbar]);

  // LabJack event handlers
  const handleLabJackDataReceived = useCallback((data: StreamingData) => {
    setStreamingData(prev => [...prev.slice(-200), ...data.data]);
    
    // Signal validation logic
    if (signalValidationEnabled && testConfig.enableLabJackValidation) {
      data.data.forEach((voltage, index) => {
        if (Math.abs(voltage) > testConfig.voltageThreshold) {
          const signal = {
            timestamp: data.timestamp + (index / data.sample_rate) * 1000,
            channel: data.channels[index % data.channels.length],
            voltage,
            type: 'detection' as const,
          };
          
          setDetectedSignals(prev => [...prev.slice(-50), signal]);
          
          // Emit signal validation event via WebSocket if connected
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              type: 'signal_validation',
              data: signal,
            }));
          }
        }
      });
    }
  }, [signalValidationEnabled, testConfig.enableLabJackValidation, testConfig.voltageThreshold]);

  const handleLabJackStatusChanged = useCallback((status: LabJackStatus) => {
    setLabJackStatus(status);
    
    // Update test configuration based on LabJack availability
    if (status.connected && !testConfig.enableLabJackValidation) {
      setTestConfig(prev => ({ ...prev, enableLabJackValidation: true }));
    }
  }, [testConfig.enableLabJackValidation]);

  const handleWebSocketMessage = useCallback((data: Record<string, unknown>) => {
    switch (data.type) {
      case 'test_progress':
        updateTestProgress(data.payload as Record<string, unknown>);
        break;
      case 'test_result':
        addTestResult(data.payload as TestResults);
        break;
      case 'test_completed':
        handleTestCompletion(data.payload as Record<string, unknown>);
        break;
      case 'test_error':
        handleTestError(data.payload);
        break;
      case 'signal_validated':
        // Handle signal validation response from backend
        const signal = data.payload as any;
        setDetectedSignals(prev => [...prev.slice(-50), {
          ...signal,
          type: 'validation' as const,
        }]);
        break;
      default:
        console.log('Unknown WebSocket message:', data);
    }
  }, [updateTestProgress, addTestResult, handleTestCompletion, handleTestError]);

  const connectWebSocket = useCallback(() => {
    if (!currentSession) return;
    
    const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8001';
    wsRef.current = new WebSocket(`${wsUrl}/ws/test-execution/${currentSession.id}`);
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleWebSocketMessage(data);
    };
    
    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      showSnackbar('WebSocket connection error', 'error');
    };
    
    wsRef.current.onclose = () => {
      if (isRunning) {
        setTimeout(connectWebSocket, 3000);
      }
    };
  }, [currentSession, handleWebSocketMessage, isRunning, showSnackbar]);

  // Load data functions
  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      const projects = await apiService.getProjects();
      setProjects(projects);
      if (projects.length > 0) {
        setSelectedProject(projects[0]);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load projects';
      setError(message);
      showSnackbar('Failed to load projects', 'error');
    } finally {
      setLoading(false);
    }
  }, [showSnackbar]);

  const loadTestSessions = useCallback(async () => {
    if (!selectedProject) return;
    
    try {
      setLoading(true);
      const response = await apiService.get<TestSession[]>(`/api/projects/${selectedProject.id}/test-sessions`);
      setSessions(response);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load test sessions';
      setError(message);
      showSnackbar('Failed to load test sessions', 'error');
    } finally {
      setLoading(false);
    }
  }, [selectedProject, showSnackbar]);

  // Effects
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selectedProject) {
      loadTestSessions();
    }
  }, [selectedProject, loadTestSessions]);

  useEffect(() => {
    if (isRunning && currentSession) {
      connectWebSocket();
    }
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [isRunning, currentSession, connectWebSocket]);

  // Event handlers
  const handleVideoSelection = (videos: VideoFile[]) => {
    setSelectedVideos(videos);
    showSnackbar(`${videos.length} videos selected`, 'success');
  };

  const createTestSession = async () => {
    if (!sessionName.trim()) {
      showSnackbar('Session name is required', 'warning');
      return;
    }

    if (!selectedProject) {
      showSnackbar('Please select a project', 'warning');
      return;
    }

    if (selectedVideos.length === 0) {
      showSnackbar('Please select at least one video', 'warning');
      return;
    }

    const modelConfigs = (selectedProject as ExtendedProject).modelConfigurations || (selectedProject as ExtendedProject).models || [];
    if (modelConfigs.length === 0) {
      showSnackbar('Please configure at least one model', 'warning');
      return;
    }

    try {
      setLoading(true);
      const sessionData = {
        name: sessionName,
        description: sessionDescription,
        projectId: selectedProject.id,
        videoIds: selectedVideos.map(v => v.id),
        modelConfigIds: modelConfigs.map((mc: ModelConfiguration) => mc.id),
        configuration: {
          ...testConfig,
          labJackConfig: labJackStatus?.connected ? {
            mode: labJackStatus.mode,
            channels: ['AIN0', 'AIN1'],
            sampleRate: 1000,
            voltageThreshold: testConfig.voltageThreshold,
          } : null,
        },
      };

      const newSession = await apiService.post<TestSession>('/api/test-sessions', sessionData);
      setSessions(prev => [newSession, ...prev]);
      setCurrentSession(newSession);
      
      setSessionName('');
      setSessionDescription('');
      setSessionDialogOpen(false);
      
      showSnackbar('Test session created successfully', 'success');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create test session';
      setError(message);
      showSnackbar('Failed to create test session', 'error');
    } finally {
      setLoading(false);
    }
  };

  const startTestExecution = async (session: TestSession) => {
    try {
      setIsRunning(true);
      setCurrentSession(session);
      setTestResults([]);
      setDetectedSignals([]);
      
      await apiService.post(`/api/test-sessions/${session.id}/start`);
      showSnackbar('Test execution started', 'success');
      
      setSessions(prevSessions => 
        prevSessions.map(s => 
          s.id === session.id ? { ...s, status: 'running' as const } : s
        )
      );
      
      // Enable signal validation if LabJack is connected
      if (labJackStatus?.connected) {
        setSignalValidationEnabled(true);
      }
      
    } catch (err: unknown) {
      setIsRunning(false);
      const message = err instanceof Error ? err.message : 'Failed to start test execution';
      setError(message);
      showSnackbar('Failed to start test execution', 'error');
    }
  };

  const stopTestExecution = async () => {
    if (!currentSession) return;
    
    try {
      await apiService.post(`/api/test-sessions/${currentSession.id}/stop`);
      setIsRunning(false);
      setSignalValidationEnabled(false);
      showSnackbar('Test execution stopped', 'warning');
      
      setSessions(prevSessions =>
        prevSessions.map(s => 
          s.id === currentSession.id ? { ...s, status: 'cancelled' as const } : s
        )
      );
      
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to stop test execution';
      setError(message);
      showSnackbar('Failed to stop test execution', 'error');
    }
  };

  const getStatusIcon = useCallback((status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon color="success" />;
      case 'running':
        return <CircularProgress size={24} />;
      case 'failed':
        return <ErrorIcon color="error" />;
      case 'cancelled':
        return <WarningIcon color="warning" />;
      default:
        return <InfoIcon color="info" />;
    }
  }, []);

  const getStatusColor = useCallback((status: string): ChipColor => {
    switch (status) {
      case 'completed': return 'success';
      case 'running': return 'primary';
      case 'failed': return 'error';
      case 'cancelled': return 'warning';
      default: return 'default';
    }
  }, []);

  const getModelConfigsCount = useCallback((project: Project | ExtendedProject) => {
    const extendedProject = project as ExtendedProject;
    const modelConfigs = extendedProject.modelConfigurations || extendedProject.models || [];
    return modelConfigs.length;
  }, []);

  if (loading && projects.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

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
        
        <Box sx={{ 
          display: 'flex', 
          flexDirection: { xs: 'column', sm: 'row' },
          gap: { xs: 1, sm: 1 },
          width: { xs: '100%', sm: 'auto' }
        }}>
          <FormControl sx={{ 
            minWidth: { xs: '100%', sm: 200 },
            mb: { xs: 1, sm: 0 }
          }}>
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
          
          <Button
            variant="outlined"
            startIcon={<VideoIcon />}
            onClick={() => setVideoSelectionOpen(true)}
            disabled={!selectedProject}
            size={window.innerWidth < 600 ? "medium" : "small"}
          >
            Select Videos ({selectedVideos.length})
          </Button>
          
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setSessionDialogOpen(true)}
            disabled={!selectedProject || selectedVideos.length === 0 || getModelConfigsCount(selectedProject || {} as Project) === 0}
            size={window.innerWidth < 600 ? "medium" : "small"}
          >
            New Session
          </Button>
        </Box>
      </Box>

      {/* Status Alert */}
      {error && (
        <Alert 
          severity="error" 
          sx={{ mb: 2 }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(e, newValue) => setTabValue(newValue)}>
          <Tab label="Test Sessions" />
          <Tab label="LabJack Hardware" />
          <Tab label="Real-time Monitoring" />
        </Tabs>
      </Box>

      {/* Test Sessions Tab */}
      <TabPanel value={tabValue} index={0}>
        {/* Current Execution Status */}
        {isRunning && currentSession && (
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Box sx={{ 
                display: 'flex', 
                flexDirection: { xs: 'column', sm: 'row' },
                alignItems: { xs: 'stretch', sm: 'center' }, 
                justifyContent: 'space-between', 
                mb: 2,
                gap: { xs: 2, sm: 0 }
              }}>
                <Typography variant="h6">
                  Running: {currentSession.name}
                </Typography>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={stopTestExecution}
                >
                  Stop Execution
                </Button>
              </Box>
              
              <LinearProgress sx={{ mb: 2 }} />
              
              <Typography variant="body2" color="text.secondary">
                Progress: {testResults.length} / {selectedVideos.length * getModelConfigsCount(selectedProject || {} as Project)} tests completed
              </Typography>
              
              {signalValidationEnabled && labJackStatus?.connected && (
                <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    LabJack Validation Active
                  </Typography>
                  <Box display="flex" gap={2} alignItems="center">
                    <Chip 
                      label={`${labJackStatus.mode.toUpperCase()} Mode`} 
                      size="small" 
                      color="success" 
                    />
                    <Chip 
                      label={`${detectedSignals.length} Signals`} 
                      size="small" 
                      icon={<TimelineIcon />} 
                    />
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        )}

        {/* Test Sessions List */}
        <Typography variant="h5" sx={{ mb: 2 }}>
          Test Sessions
          {selectedProject && (
            <Typography variant="body2" color="text.secondary" component="span" sx={{ ml: 2 }}>
              for {selectedProject.name}
            </Typography>
          )}
        </Typography>
        
        {sessions.length === 0 ? (
          <Card>
            <CardContent sx={{ textAlign: 'center', py: 4 }}>
              <ReportIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No test sessions yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Create your first test session to start evaluating models
              </Typography>
            </CardContent>
          </Card>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {sessions.map((session) => (
              <Card key={session.id}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                    <Typography variant="h6">
                      {session.name}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getStatusIcon(session.status)}
                      <Chip 
                        label={session.status}
                        color={getStatusColor(session.status)}
                        size="small"
                      />
                    </Box>
                  </Box>
                  
                  {session.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {session.description}
                    </Typography>
                  )}
                  
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Videos: {session.videoIds?.length || 1}
                  </Typography>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    Models: {session.modelConfigIds?.length || 1}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Created: {new Date(session.createdAt || Date.now()).toLocaleDateString()}
                  </Typography>
                </CardContent>
                
                <CardActions>
                  {session.status === 'pending' && (
                    <Button
                      size="small"
                      startIcon={<PlayIcon />}
                      onClick={() => startTestExecution(session)}
                      disabled={isRunning}
                    >
                      Start
                    </Button>
                  )}
                  
                  {session.status === 'completed' && (
                    <Button
                      size="small"
                      startIcon={<ReportIcon />}
                      onClick={() => {/* Navigate to results */}}
                    >
                      View Results
                    </Button>
                  )}
                  
                  <Button
                    size="small"
                    startIcon={<EditIcon />}
                    onClick={() => {/* Edit session */}}
                  >
                    Edit
                  </Button>
                  
                  <Button
                    size="small"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={() => {/* Delete session */}}
                  >
                    Delete
                  </Button>
                </CardActions>
              </Card>
            ))}
          </Box>
        )}
      </TabPanel>

      {/* LabJack Hardware Tab */}
      <TabPanel value={tabValue} index={1}>
        <LabJackStatusPanel
          onDataReceived={handleLabJackDataReceived}
          onStatusChanged={handleLabJackStatusChanged}
        />
      </TabPanel>

      {/* Real-time Monitoring Tab */}
      <TabPanel value={tabValue} index={2}>
        <Grid container spacing={3}>
          {/* Signal Data Chart */}
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Live Signal Data
                </Typography>
                
                {streamingData.length > 0 ? (
                  <Box sx={{ height: 300, bgcolor: 'grey.50', borderRadius: 1, p: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Latest {Math.min(streamingData.length, 200)} samples
                    </Typography>
                    
                    {/* Simple visualization - could be replaced with a proper chart */}
                    <Box sx={{ height: 200, border: '1px solid #ccc', borderRadius: 1, overflow: 'hidden' }}>
                      <Box sx={{ 
                        height: '100%', 
                        background: `linear-gradient(to right, ${streamingData.slice(-50).map((v, i) => 
                          `transparent ${(i/49)*100}%, rgba(33, 150, 243, ${Math.abs(v)/5}) ${((i+1)/49)*100}%`
                        ).join(', ')})` 
                      }} />
                    </Box>
                    
                    <Typography variant="caption" color="text.secondary">
                      Range: {Math.min(...streamingData).toFixed(2)}V to {Math.max(...streamingData).toFixed(2)}V
                    </Typography>
                  </Box>
                ) : (
                  <Alert severity="info">
                    No streaming data available. Start LabJack streaming to see real-time data.
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Detection Events */}
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Signal Events
                </Typography>
                
                <List dense sx={{ maxHeight: 300, overflow: 'auto' }}>
                  {detectedSignals.slice(-10).reverse().map((signal, index) => (
                    <ListItem key={`${signal.timestamp}-${index}`}>
                      <ListItemIcon>
                        {signal.type === 'detection' && <TrendingUpIcon color="primary" />}
                        {signal.type === 'validation' && <CheckCircleIcon color="success" />}
                        {signal.type === 'sync' && <TimelineIcon color="info" />}
                      </ListItemIcon>
                      <ListItemText
                        primary={`${signal.channel}: ${signal.voltage.toFixed(3)}V`}
                        secondary={new Date(signal.timestamp).toLocaleTimeString()}
                      />
                    </ListItem>
                  ))}
                  
                  {detectedSignals.length === 0 && (
                    <ListItem>
                      <ListItemText
                        primary="No signals detected"
                        secondary="Signals will appear when voltage exceeds threshold"
                      />
                    </ListItem>
                  )}
                </List>
              </CardContent>
            </Card>
          </Grid>

          {/* Statistics */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Session Statistics
              </Typography>
              
              <Grid container spacing={3}>
                <Grid item xs={12} sm={3}>
                  <Box textAlign="center">
                    <DataUsageIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
                    <Typography variant="h6">{streamingData.length}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Samples
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={12} sm={3}>
                  <Box textAlign="center">
                    <TrendingUpIcon sx={{ fontSize: 40, color: 'success.main', mb: 1 }} />
                    <Typography variant="h6">{detectedSignals.length}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Signal Events
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={12} sm={3}>
                  <Box textAlign="center">
                    <SpeedIcon sx={{ fontSize: 40, color: 'warning.main', mb: 1 }} />
                    <Typography variant="h6">
                      {labJackStatus?.connected ? `${labJackStatus.statistics?.samples_received || 0}/s` : 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Sample Rate
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={12} sm={3}>
                  <Box textAlign="center">
                    <TimelineIcon sx={{ fontSize: 40, color: 'info.main', mb: 1 }} />
                    <Typography variant="h6">{testResults.length}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Test Results
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Video Selection Dialog */}
      {selectedProject && (
        <VideoSelectionDialog
          open={videoSelectionOpen}
          onClose={() => setVideoSelectionOpen(false)}
          projectId={selectedProject.id}
          onSelectionComplete={handleVideoSelection}
          selectedVideoIds={selectedVideos.map(v => v.id)}
        />
      )}

      {/* New Session Dialog */}
      <Dialog
        open={sessionDialogOpen}
        onClose={() => setSessionDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Create Enhanced Test Session</DialogTitle>
        <DialogContent>
          <TextField
            label="Session Name"
            value={sessionName}
            onChange={(e) => setSessionName(e.target.value)}
            fullWidth
            margin="normal"
            required
          />
          
          <TextField
            label="Description"
            value={sessionDescription}
            onChange={(e) => setSessionDescription(e.target.value)}
            fullWidth
            margin="normal"
            multiline
            rows={3}
          />
          
          <Typography variant="subtitle1" sx={{ mt: 2, mb: 1 }}>
            Test Configuration
          </Typography>
          
          <FormControlLabel
            control={
              <Switch
                checked={testConfig.concurrent}
                onChange={(e) => setTestConfig(prev => ({ ...prev, concurrent: e.target.checked }))}
              />
            }
            label="Run tests concurrently"
          />
          
          <FormControlLabel
            control={
              <Switch
                checked={testConfig.saveIntermediateResults}
                onChange={(e) => setTestConfig(prev => ({ ...prev, saveIntermediateResults: e.target.checked }))}
              />
            }
            label="Save intermediate results"
          />
          
          <FormControlLabel
            control={
              <Switch
                checked={testConfig.generateReport}
                onChange={(e) => setTestConfig(prev => ({ ...prev, generateReport: e.target.checked }))}
              />
            }
            label="Generate detailed report"
          />
          
          {labJackStatus?.connected && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle1" gutterBottom>
                LabJack Hardware Validation
              </Typography>
              
              <FormControlLabel
                control={
                  <Switch
                    checked={testConfig.enableLabJackValidation}
                    onChange={(e) => setTestConfig(prev => ({ ...prev, enableLabJackValidation: e.target.checked }))}
                  />
                }
                label="Enable hardware signal validation"
              />
              
              {testConfig.enableLabJackValidation && (
                <TextField
                  label="Voltage Threshold (V)"
                  type="number"
                  value={testConfig.voltageThreshold}
                  onChange={(e) => setTestConfig(prev => ({ ...prev, voltageThreshold: parseFloat(e.target.value) }))}
                  fullWidth
                  margin="normal"
                  inputProps={{ step: 0.1, min: 0, max: 10 }}
                />
              )}
            </>
          )}
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setSessionDialogOpen(false)}>
            Cancel
          </Button>
          <Button onClick={createTestSession} variant="contained">
            Create Session
          </Button>
        </DialogActions>
      </Dialog>

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

export default TestExecutionEnhanced;