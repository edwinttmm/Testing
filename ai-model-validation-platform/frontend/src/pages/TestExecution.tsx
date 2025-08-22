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
} from '@mui/icons-material';

import { Project, TestSession, VideoFile } from '../services/types';
import { apiService } from '../services/api';
import VideoSelectionDialog from '../components/VideoSelectionDialog';

interface ModelConfiguration {
  id: string;
  name: string;
  type: string;
  config: any;
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
    detections: any[];
    processingTime: number;
    errorCount: number;
  };
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  startedAt: string;
  completedAt?: string;
  error?: string;
}

const TestExecution: React.FC = () => {
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedVideos, setSelectedVideos] = useState<VideoFile[]>([]);
  const [testResults, setTestResults] = useState<TestResults[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentSession, setCurrentSession] = useState<TestSession | null>(null);
  
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

  const updateTestProgress = useCallback((progress: any) => {
    // Update progress indicators
    console.log('Test progress:', progress);
  }, []);

  const addTestResult = useCallback((result: TestResults) => {
    setTestResults(prev => [...prev, result]);
  }, []);

  const handleTestCompletion = useCallback((data: any) => {
    setIsRunning(false);
    showSnackbar('Test execution completed', 'success');
    
    // Update session status
    setSessions(prevSessions =>
      prevSessions.map(s => 
        s.id === currentSession?.id ? { ...s, status: 'completed' as const } : s
      )
    );
  }, [currentSession?.id, showSnackbar]);

  const handleTestError = useCallback((error: any) => {
    setIsRunning(false);
    showSnackbar(`Test execution failed: ${error.message}`, 'error');
    
    // Update session status
    setSessions(prevSessions =>
      prevSessions.map(s => 
        s.id === currentSession?.id ? { ...s, status: 'failed' as const } : s
      )
    );
  }, [currentSession?.id, showSnackbar]);

  const handleWebSocketMessage = useCallback((data: any) => {
    switch (data.type) {
      case 'test_progress':
        updateTestProgress(data.payload);
        break;
      case 'test_result':
        addTestResult(data.payload);
        break;
      case 'test_completed':
        handleTestCompletion(data.payload);
        break;
      case 'test_error':
        handleTestError(data.payload);
        break;
      default:
        console.log('Unknown WebSocket message:', data);
    }
  }, [updateTestProgress, addTestResult, handleTestCompletion, handleTestError]);

  const connectWebSocket = useCallback(() => {
    const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8001';
    wsRef.current = new WebSocket(`${wsUrl}/ws/test-execution/${currentSession?.id}`);
    
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
        // Attempt to reconnect
        setTimeout(connectWebSocket, 3000);
      }
    };
  }, [currentSession, handleWebSocketMessage, isRunning, showSnackbar]);

  const loadProjects = useCallback(async () => {
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
  }, [showSnackbar]);

  const loadTestSessions = useCallback(async () => {
    if (!selectedProject) return;
    
    try {
      setLoading(true);
      const response = await apiService.get<TestSession[]>(`/api/projects/${selectedProject.id}/test-sessions`);
      setSessions(response);
    } catch (err: any) {
      setError(err.message || 'Failed to load test sessions');
      showSnackbar('Failed to load test sessions', 'error');
    } finally {
      setLoading(false);
    }
  }, [selectedProject, showSnackbar]);

  // Load projects and sessions
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selectedProject) {
      loadTestSessions();
    }
  }, [selectedProject, loadTestSessions]);

  // WebSocket connection for real-time updates
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

    const modelConfigs = (selectedProject as any).modelConfigurations || (selectedProject as any).models || [];
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
        modelConfigIds: modelConfigs.map((mc: any) => mc.id),
        configuration: testConfig,
      };

      const newSession = await apiService.post<TestSession>('/api/test-sessions', sessionData);
      setSessions(prev => [newSession, ...prev]);
      setCurrentSession(newSession);
      
      // Reset form
      setSessionName('');
      setSessionDescription('');
      setSessionDialogOpen(false);
      
      showSnackbar('Test session created successfully', 'success');
    } catch (err: any) {
      setError(err.message || 'Failed to create test session');
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
      
      await apiService.post(`/api/test-sessions/${session.id}/start`);
      showSnackbar('Test execution started', 'success');
      
      // Update session status
      setSessions(prevSessions => 
        prevSessions.map(s => 
          s.id === session.id ? { ...s, status: 'running' as const } : s
        )
      );
      
    } catch (err: any) {
      setIsRunning(false);
      setError(err.message || 'Failed to start test execution');
      showSnackbar('Failed to start test execution', 'error');
    }
  };

  const stopTestExecution = async () => {
    if (!currentSession) return;
    
    try {
      await apiService.post(`/api/test-sessions/${currentSession.id}/stop`);
      setIsRunning(false);
      showSnackbar('Test execution stopped', 'warning');
      
      // Update session status
      setSessions(prevSessions =>
        prevSessions.map(s => 
          s.id === currentSession.id ? { ...s, status: 'cancelled' as const } : s
        )
      );
      
    } catch (err: any) {
      setError(err.message || 'Failed to stop test execution');
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

  const getStatusColor = useCallback((status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'running': return 'primary';
      case 'failed': return 'error';
      case 'cancelled': return 'warning';
      default: return 'default';
    }
  }, []);

  const getModelConfigsCount = useCallback((project: Project) => {
    const modelConfigs = (project as any).modelConfigurations || (project as any).models || [];
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
          Test Execution
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
            sx={{
              minHeight: { xs: '48px', sm: 'auto' },
              fontSize: { xs: '0.9rem', sm: '0.875rem' },
              touchAction: 'manipulation',
              '&:active': {
                transform: 'scale(0.95)'
              }
            }}
          >
            Select Videos ({selectedVideos.length})
          </Button>
          
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setSessionDialogOpen(true)}
            disabled={!selectedProject || selectedVideos.length === 0 || getModelConfigsCount(selectedProject || {} as Project) === 0}
            size={window.innerWidth < 600 ? "medium" : "small"}
            sx={{
              minHeight: { xs: '48px', sm: 'auto' },
              fontSize: { xs: '0.9rem', sm: '0.875rem' },
              touchAction: 'manipulation',
              '&:active': {
                transform: 'scale(0.95)'
              }
            }}
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

      {/* Current Execution Status */}
      {isRunning && currentSession && (
        <Card sx={{ mb: 3, mx: { xs: 0, sm: 'auto' } }}>
          <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
            <Box sx={{ 
              display: 'flex', 
              flexDirection: { xs: 'column', sm: 'row' },
              alignItems: { xs: 'stretch', sm: 'center' }, 
              justifyContent: 'space-between', 
              mb: 2,
              gap: { xs: 2, sm: 0 }
            }}>
              <Typography 
                variant="h6"
                sx={{ 
                  fontSize: { xs: '1.1rem', sm: '1.25rem' },
                  textAlign: { xs: 'center', sm: 'left' }
                }}
              >
                Running: {currentSession.name}
              </Typography>
              <Button
                variant="contained"
                color="error"
                startIcon={<StopIcon />}
                onClick={stopTestExecution}
                size={window.innerWidth < 600 ? "medium" : "small"}
                sx={{
                  minHeight: { xs: '48px', sm: 'auto' },
                  fontSize: { xs: '0.9rem', sm: '0.875rem' },
                  touchAction: 'manipulation',
                  width: { xs: '100%', sm: 'auto' },
                  '&:active': {
                    transform: 'scale(0.95)'
                  }
                }}
              >
                Stop Execution
              </Button>
            </Box>
            
            <LinearProgress sx={{ mb: 2 }} />
            
            <Typography 
              variant="body2" 
              color="text.secondary"
              sx={{ 
                fontSize: { xs: '0.8rem', sm: '0.875rem' },
                textAlign: { xs: 'center', sm: 'left' }
              }}
            >
              Progress: {testResults.length} / {selectedVideos.length * getModelConfigsCount(selectedProject || {} as Project)} tests completed
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Test Sessions */}
      <Typography 
        variant="h5" 
        sx={{ 
          mb: 2,
          fontSize: { xs: '1.25rem', sm: '1.5rem' },
          textAlign: { xs: 'center', sm: 'left' }
        }}
      >
        Test Sessions
        {selectedProject && (
          <Typography 
            variant="body2" 
            color="text.secondary" 
            component="span" 
            sx={{ 
              ml: { xs: 0, sm: 2 },
              display: { xs: 'block', sm: 'inline' },
              fontSize: { xs: '0.8rem', sm: '0.875rem' }
            }}
          >
            for {selectedProject.name}
          </Typography>
        )}
      </Typography>
      
      {sessions.length === 0 ? (
        <Card sx={{ mx: { xs: 0, sm: 'auto' } }}>
          <CardContent sx={{ 
            textAlign: 'center', 
            py: { xs: 3, sm: 4 },
            px: { xs: 2, sm: 3 }
          }}>
            <ReportIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography 
              variant="h6" 
              color="text.secondary" 
              gutterBottom
              sx={{ fontSize: { xs: '1.1rem', sm: '1.25rem' } }}
            >
              No test sessions yet
            </Typography>
            <Typography 
              variant="body2" 
              color="text.secondary"
              sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}
            >
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
                      color={getStatusColor(session.status) as any}
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
                  Videos: {(session as any).videoIds?.length || 1}
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  Models: {(session as any).modelConfigIds?.length || 1}
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
        <DialogTitle>Create Test Session</DialogTitle>
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

export default TestExecution;