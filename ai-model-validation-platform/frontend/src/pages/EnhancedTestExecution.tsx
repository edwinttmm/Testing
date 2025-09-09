import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
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
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  NetworkCheck as NetworkCheckIcon,
  Sync as SyncIcon,
  Speed as SpeedIcon,
  Wifi as WifiIcon,
  WifiOff as WifiOffIcon,
  Fullscreen as FullscreenIcon,
} from '@mui/icons-material';

import { Project, TestSession, TestResult, VideoFile } from '../services/types';
import { apiService, startEnhancedTestWorkflow, stopEnhancedTestWorkflow, getEnhancedTestWorkflowStatus, getEnhancedTestWorkflowResults, createEnhancedTestSession, runEnhancedTestSession, getEnhancedTestSessionResults, getAllVideos } from '../services/api';
import VideoSelectionDialog from '../components/VideoSelectionDialog';
import LabJackStatusPanel from '../components/LabJackStatusPanel';
import { SimpleDetectionPanel } from '../components/SimpleDetectionPanel';
import AutomatedVideoPlayer from '../components/AutomatedVideoPlayer';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { markUserInteraction, generateVideoUrl } from '../utils/videoUtils';

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
  // Enhanced test workflow specific settings
  detectionWindowMs: number;
  voltageThreshold: number;
  sampleRate: number;
  channels: string[];
}

interface ConnectionStatus {
  api: 'connected' | 'disconnected' | 'checking';
  websocket: 'connected' | 'disconnected' | 'checking';
  labjack: 'connected' | 'disconnected' | 'checking';
  latency: number;
  lastCheck: Date;
}

interface LabJackStatus {
  connected: boolean;
  currentVoltages?: { [channel: string]: number };
  voltageThreshold?: number;
  channels?: string[];
  sampleRate?: number;
  error?: string;
}

interface CameraDetection {
  timestamp: number;
  voltage: number;
  channel: string;
  videoTimestamp?: number;
  delay?: number;
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
    // Enhanced test workflow specific settings
    detectionWindowMs: 500.0, // 500ms detection window for Pass/Fail
    voltageThreshold: 2.5,     // LabJack voltage threshold 
    sampleRate: 1000,          // 1kHz sampling rate
    channels: ['AIN0', 'AIN1'] // Default channels
  });

  // Connection status
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    api: 'disconnected',
    websocket: 'disconnected',
    labjack: 'checking',
    latency: 0,
    lastCheck: new Date(),
  });

  // LabJack integration
  const [labJackStatus, setLabJackStatus] = useState<LabJackStatus>({ connected: false });
  const [cameraDetections, setCameraDetections] = useState<CameraDetection[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenVideo, setFullscreenVideo] = useState<VideoFile | null>(null);
  const [videoStartTime, setVideoStartTime] = useState<number | null>(null);
  const [labJackConfig, setLabJackConfig] = useState({
    lowerBound: 4.0,
    upperBound: 5.5,
    checkInterval: 0.1,
    channel: 'AIN0'
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
  const [labJackConfigOpen, setLabJackConfigOpen] = useState(false);

  // Form states
  const [sessionName, setSessionName] = useState('');
  const [sessionDescription, setSessionDescription] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);

  // UI states
  const [loading, setLoading] = useState(false);
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

  // Enhanced Test Workflow WebSocket message handler with full automation
  const handleWorkflowWebSocketMessage = useCallback((data: unknown) => {
    if (!data || typeof data !== 'object') return;
    
    const message = data as Record<string, unknown>;
    
    switch (message.type) {
      case 'video_start_playback':
        // Video playback initiation - wait for actual playback to start
        const videoIndex = message.index as number;
        const videoName = message.video_name as string;
        const videoPath = message.video_path as string;
        const autPlay = message.auto_play as boolean;
        
        // Update playback state for sequential processing
        setPlaybackState(prev => ({
          ...prev,
          currentVideoIndex: videoIndex,
          playingVideo: selectedVideos[videoIndex] || null,
          isSequentialMode: true,
          totalProgress: (videoIndex / selectedVideos.length) * 100
        }));
        
        // Only show message when video is actually ready, not when auto-play is triggered
        if (autPlay) {
          setVideoStartTime(Date.now());
          
          // Don't show "playing" until actual playback starts
          showSnackbar(
            `Preparing video ${videoIndex + 1}/${message.total}: ${videoName}`,
            'info'
          );
        }
        break;
        
      case 'voltage_reading':
        // Real-time voltage monitoring updates
        const voltage = message.voltage as number;
        const timestamp = message.timestamp as number;
        const currentVideoIndex = message.video_index as number;
        
        // Update real-time voltage display without overwhelming the UI
        if (Math.random() < 0.1) { // Only show 10% of readings to avoid spam
          setCameraDetections(prev => [
            ...prev.slice(-50), // Keep last 50 readings
            {
              timestamp: Date.now(),
              voltage,
              channel: 'AIN0',
              videoTimestamp: timestamp * 1000,
              delay: undefined
            }
          ]);
        }
        break;
        
      case 'detection_event':
        // Real-time detection event with precise timing
        const detectionDelay = message.detection_delay_ms as number;
        const detectionVoltage = message.voltage as number;
        const detectionTimestamp = message.timestamp as number;
        const detectionStatus = message.status as string;
        const detectionVideoIndex = message.video_index as number;
        
        setCameraDetections(prev => [...prev, {
          timestamp: Date.now(),
          voltage: detectionVoltage,
          channel: 'AIN0',
          videoTimestamp: detectionTimestamp * 1000,
          delay: detectionDelay
        }]);
        
        showSnackbar(
          `Video ${detectionVideoIndex + 1} - Detection: ${detectionVoltage.toFixed(2)}V (${detectionDelay.toFixed(1)}ms delay) - ${detectionStatus.toUpperCase()}`,
          detectionStatus === 'pass' ? 'success' : 'error'
        );
        break;
        
      case 'no_detection':
        // Handle no detection found
        const noDetectionVideoIndex = message.video_index as number;
        const maxVoltage = message.max_voltage as number;
        
        showSnackbar(
          `Video ${noDetectionVideoIndex + 1} - No detection found (max voltage: ${maxVoltage.toFixed(2)}V)`,
          'warning'
        );
        break;
        
      case 'video_complete':
        // Individual video completion
        const completedVideoIndex = message.video_index as number;
        const videoResult = message.result as any;
        
        if (videoResult) {
          showSnackbar(
            `Video ${completedVideoIndex + 1} completed: ${videoResult.status}`,
            videoResult.status === 'pass' ? 'success' : 'error'
          );
        }
        break;
        
      case 'workflow_progress':
        // Real-time workflow progress updates
        const progress = message.progress as number;
        const completedVideos = message.completed_videos as number;
        const totalVideos = message.total_videos as number;
        
        setPlaybackState(prev => ({
          ...prev,
          totalProgress: progress,
          currentVideoIndex: completedVideos - 1
        }));
        
        // Show progress milestone notifications
        if (completedVideos % Math.max(1, Math.floor(totalVideos / 4)) === 0) {
          showSnackbar(
            `Progress: ${completedVideos}/${totalVideos} videos processed (${progress.toFixed(1)}%)`,
            'info'
          );
        }
        break;
        
      case 'test_results':
        // Batch test results update with comprehensive data
        if (Array.isArray(message.results)) {
          setTestResults(message.results as TestResult[]);
        }
        
        if (message.summary) {
          const summary = message.summary as any;
          showSnackbar(
            `Results updated: ${summary.passed}/${summary.total_videos} passed (${summary.pass_rate_percentage.toFixed(1)}%)`,
            'info'
          );
        }
        break;
        
      case 'test_complete':
        // Test workflow completed with comprehensive results
        console.log('🏆 Backend test workflow completed');
        
        setIsRunning(false);
        setPlaybackState(prev => ({
          ...prev,
          isSequentialMode: false,
          totalProgress: 100
        }));
        
        // Close WebSocket connection
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        
        // Exit fullscreen if still active
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(console.warn);
        }
        
        const completionSummary = message.summary as any;
        const completionMessage = message.message as string;
        
        if (completionSummary) {
          setTestResults(prev => prev); // Results should already be updated
          
          showSnackbar(
            completionMessage || `🏆 Test Complete: ${completionSummary.passed}/${completionSummary.total_videos} passed (${completionSummary.pass_rate_percentage.toFixed(1)}%). Exited fullscreen.`,
            completionSummary.pass_rate_percentage > 80 ? 'success' : completionSummary.pass_rate_percentage > 50 ? 'warning' : 'error'
          );
          
          // Auto-export results if high success rate
          if (completionSummary.pass_rate_percentage > 80) {
            setTimeout(() => {
              exportTestResults();
            }, 3000);
          }
        } else {
          showSnackbar('🏆 Enhanced Test Workflow completed successfully! Exited fullscreen.', 'success');
        }
        break;
        
      case 'workflow_error':
        // Workflow error handling
        const errorMessage = message.error as string;
        console.log('❌ Workflow error occurred:', errorMessage);
        
        setIsRunning(false);
        setPlaybackState(prev => ({
          ...prev,
          isSequentialMode: false
        }));
        
        // Close WebSocket connection
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        
        // Exit fullscreen if still active
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(console.warn);
        }
        
        showSnackbar(
          `❌ Workflow error: ${errorMessage}. Exited fullscreen.`,
          'error'
        );
        break;
        
      case 'status':
        // Status update
        console.log('Workflow status update:', message.data);
        break;
        
      default:
        console.log('Unknown workflow message type:', message.type, message);
    }
  }, [videoStartTime, selectedVideos, showSnackbar]);

  // Export test results function - moved before first usage
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
      console.error('API connection check failed:', error);
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
      const wsUrl = process.env.REACT_APP_SOCKETIO_URL || process.env.REACT_APP_WS_URL || 'http://localhost:8001';
      const testWsUrl = wsUrl.replace('http', 'ws') + '/ws/test';
      const testWs = new WebSocket(testWsUrl);
      
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
      console.error('WebSocket connection failed:', error);
      setConnectionStatus(prev => ({ ...prev, websocket: 'disconnected' }));
    }
  }, []);

  const performConnectionCheck = useCallback(async () => {
    await Promise.all([checkAPIConnection(), checkWebSocketConnection()]);
  }, [checkAPIConnection, checkWebSocketConnection]);

  // Sequential playback logic - removed unused function




  // Session Management Functions
  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      let sessionsData: TestSession[] = [];
      
      // Try enhanced test endpoint first, fallback to original if needed
      try {
        const response = await apiService.get('/api/enhanced-test/sessions');
        
        // Handle different response formats
        if (Array.isArray(response)) {
          sessionsData = response as TestSession[];
        } else if (response && typeof response === 'object' && 'sessions' in response) {
          const sessionsList = (response as any).sessions;
          sessionsData = Array.isArray(sessionsList) ? sessionsList : [];
        } else if (response && typeof response === 'object' && 'data' in response) {
          const dataList = (response as any).data;
          sessionsData = Array.isArray(dataList) ? dataList : [];
        } else {
          console.warn('Unexpected enhanced sessions response format:', response);
          sessionsData = [];
        }
      } catch (enhancedErr) {
        console.warn('Enhanced test sessions endpoint not available, using fallback:', enhancedErr);
        
        try {
          const response = await apiService.get('/api/test-sessions');
          
          // Handle different response formats for fallback endpoint
          if (Array.isArray(response)) {
            sessionsData = response as TestSession[];
          } else if (response && typeof response === 'object' && 'sessions' in response) {
            const sessionsList = (response as any).sessions;
            sessionsData = Array.isArray(sessionsList) ? sessionsList : [];
          } else if (response && typeof response === 'object' && 'data' in response) {
            const dataList = (response as any).data;
            sessionsData = Array.isArray(dataList) ? dataList : [];
          } else {
            console.warn('Unexpected fallback sessions response format:', response);
            sessionsData = [];
          }
        } catch (fallbackErr) {
          console.error('Both sessions endpoints failed:', fallbackErr);
          sessionsData = [];
          throw new Error('Failed to load sessions from both endpoints');
        }
      }
      
      // Ensure we always set an array, even if empty
      setSessions(Array.isArray(sessionsData) ? sessionsData : []);
      
      if (sessionsData.length === 0) {
        console.log('No sessions found, this is normal for new projects');
      } else {
        console.log(`Loaded ${sessionsData.length} sessions successfully`);
      }
      
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load sessions';
      console.error('Session loading error:', err);
      showSnackbar(message, 'error');
      // Always ensure sessions is an array, even on error
      setSessions([]);
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
      
      if (editingSessionId) {
        // Update existing session using enhanced test endpoint with correct schema
        const updatedSession = {
          name: sessionName,
          description: sessionDescription,
          project_id: selectedProject?.id,
          video_ids: selectedVideos.map(v => v.id),
          config: testConfig,
        };

        const response = await apiService.put<TestSession>(`/api/enhanced-test/sessions/${editingSessionId}`, updatedSession);
        setSessions(prev => Array.isArray(prev) ? prev.map(s => s.id === editingSessionId ? response : s) : [response]);
        if (currentSession?.id === editingSessionId) {
          setCurrentSession(response);
        }
        showSnackbar('Session updated successfully', 'success');
      } else {
        // Create new session using enhanced test endpoint with correct schema
        const newSession = {
          name: sessionName,
          description: sessionDescription,
          project_id: selectedProject?.id,
          video_ids: selectedVideos.map(v => v.id),
          config: testConfig,
        };

        const response = await apiService.post<TestSession>('/api/enhanced-test/sessions', newSession);
        setSessions(prev => Array.isArray(prev) ? [...prev, response] : [response]);
        setCurrentSession(response);
        showSnackbar('Session created successfully', 'success');
      }
      
      setSessionName('');
      setSessionDescription('');
      setEditingSessionId(null);
      setSessionDialogOpen(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : `Failed to ${editingSessionId ? 'update' : 'create'} session`;
      showSnackbar(message, 'error');
    } finally {
      setLoading(false);
    }
  }, [sessionName, sessionDescription, selectedProject, selectedVideos, testConfig, editingSessionId, currentSession, showSnackbar]);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      // Use original endpoint since enhanced endpoint doesn't have DELETE method yet
      await apiService.delete(`/api/test-sessions/${sessionId}`);
      setSessions(prev => Array.isArray(prev) ? prev.filter(s => s.id !== sessionId) : []);
      if (currentSession?.id === sessionId) {
        setCurrentSession(null);
      }
      showSnackbar('Session deleted successfully', 'success');
    } catch (err) {
      console.error('Failed to delete session:', err);
      showSnackbar('Failed to delete session', 'error');
    }
  }, [currentSession, showSnackbar]);

  // Page fullscreen functions removed - no longer using automatic page fullscreen

  const startTestExecution = useCallback(async () => {
    if (!currentSession || !selectedProject) {
      showSnackbar('Please create and select a test session first', 'warning');
      return;
    }

    if (selectedVideos.length === 0) {
      showSnackbar('Please select videos to test', 'warning');
      return;
    }

    try {
      // Mark user interaction for autoplay permissions
      markUserInteraction();
      
      setIsRunning(true);
      setTestResults([]);
      setCameraDetections([]);
      
      // IMMEDIATE FULLSCREEN: Trigger fullscreen immediately when Start Test is clicked
      const videoPlayerContainer = document.querySelector('.test-execution-video-player');
      if (videoPlayerContainer) {
        try {
          if (videoPlayerContainer.requestFullscreen) {
            await videoPlayerContainer.requestFullscreen();
          } else if ((videoPlayerContainer as any).webkitRequestFullscreen) {
            await (videoPlayerContainer as any).webkitRequestFullscreen();
          } else if ((videoPlayerContainer as any).mozRequestFullScreen) {
            await (videoPlayerContainer as any).mozRequestFullScreen();
          }
          showSnackbar('🖥️ Entered fullscreen mode. Videos will auto-play continuously.', 'success');
        } catch (error) {
          console.warn('Could not enter fullscreen immediately:', error);
          showSnackbar('⚠️ Fullscreen request failed. Videos will still auto-play.', 'warning');
        }
      }
      
      // Try to enable unmuted playback immediately since this is user-initiated
      setTimeout(() => {
        const videoElements = document.querySelectorAll('video');
        videoElements.forEach(video => {
          try {
            video.muted = false; // Try to unmute after user interaction
          } catch (e) {
            // Ignore if unmuting fails
            console.warn('Could not unmute video:', e);
          }
        });
      }, 500);
      
      // Initialize sequential playback state
      setPlaybackState({
        currentVideoIndex: 0,
        playingVideo: selectedVideos[0],
        isSequentialMode: true,
        totalProgress: 0,
        videoProgress: {}
      });

      // Start the Enhanced Test Workflow with full automation configuration
      const workflowConfig = {
        projectId: selectedProject.id,
        detectionWindowMs: testConfig.detectionWindowMs,
        voltageThreshold: testConfig.voltageThreshold,
        sampleRate: testConfig.sampleRate,
        channels: testConfig.channels,
        // Additional automation settings
        sequentialMode: true,
        autoAdvance: true,
        videoCount: selectedVideos.length
      };

      console.log('Starting Enhanced Test Workflow with config:', workflowConfig);
      const workflowResult = await startEnhancedTestWorkflow(workflowConfig);
      
      // Initialize WebSocket connection for real-time automation
      const wsUrl = process.env.REACT_APP_SOCKETIO_URL || process.env.REACT_APP_WS_URL || 'http://localhost:8000';
      const testWsUrl = wsUrl.replace('http', 'ws') + '/api/enhanced-test-workflow/ws';
      wsRef.current = new WebSocket(testWsUrl);
      
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWorkflowWebSocketMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsRunning(false);
        setPlaybackState(prev => ({ ...prev, isSequentialMode: false }));
        showSnackbar('WebSocket connection failed - check backend connection', 'error');
      };

      wsRef.current.onopen = () => {
        showSnackbar(
          `🚀 TEST STARTED: ${workflowResult.videoCount} videos will process sequentially with automatic fullscreen.`,
          'success'
        );
        
        // Additional UI preparation for automation
        setTimeout(() => {
          showSnackbar(
            `📹 Sequential processing initiated. Videos: ${selectedVideos.map(v => v.filename || 'Unknown').join(', ')}`,
            'info'
          );
        }, 1500);
      };
      
      wsRef.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        if (isRunning) {
          showSnackbar('WebSocket connection closed unexpectedly', 'warning');
        }
      };
      
    } catch (err) {
      console.error('Failed to start Enhanced Test Workflow:', err);
      setIsRunning(false);
      setPlaybackState(prev => ({ ...prev, isSequentialMode: false }));
      
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      showSnackbar(`Failed to start automated test workflow: ${errorMessage}`, 'error');
    }
  }, [currentSession, selectedProject, selectedVideos, testConfig, showSnackbar, isRunning]);

  const stopTestExecution = useCallback(async () => {
    try {
      // Stop the Enhanced Test Workflow
      const result = await stopEnhancedTestWorkflow();
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      
      setIsRunning(false);
      
      // No need to exit fullscreen - individual videos handle their own fullscreen
      
      // Load and display final results
      if (result.results && result.results.length > 0) {
        setTestResults(result.results as TestResult[]);
        showSnackbar(`Test stopped. ${result.results.length} results collected.`, 'info');
      } else {
        showSnackbar('Test execution stopped', 'info');
      }
      
    } catch (err) {
      console.error('Failed to stop Enhanced Test Workflow:', err);
      setIsRunning(false);
      
      // No need to exit fullscreen on error
      
      showSnackbar('Failed to stop test workflow', 'error');
    }
  }, [showSnackbar]);

  // LabJack connection functions
  const checkLabJackConnection = useCallback(async () => {
    try {
      setConnectionStatus(prev => ({ ...prev, labjack: 'checking' }));
      const response = await apiService.checkLabJackStatus();
      setLabJackStatus(response);
      setConnectionStatus(prev => ({ 
        ...prev, 
        labjack: response.connected ? 'connected' : 'disconnected' 
      }));
    } catch (error) {
      console.error('Failed to check LabJack connection:', error);
      setLabJackStatus({ connected: false, error: 'Connection check failed' });
      setConnectionStatus(prev => ({ ...prev, labjack: 'disconnected' }));
    }
  }, []);

  const initializeLabJack = useCallback(async () => {
    try {
      const config = {
        voltage_threshold: { lower: labJackConfig.lowerBound, upper: labJackConfig.upperBound },
        channels: [labJackConfig.channel],
        sample_rate: 1000 / labJackConfig.checkInterval
      };
      
      const response = await apiService.initializeLabJack(config);
      
      if (response.status === 'connected' || response.status === 'success') {
        await checkLabJackConnection();
        showSnackbar(response.message || 'LabJack initialized successfully', 'success');
      } else {
        showSnackbar(response.message || response.error || 'Failed to initialize LabJack', 'error');
      }
    } catch (error) {
      console.error('Failed to initialize LabJack:', error);
      showSnackbar('Failed to initialize LabJack', 'error');
    }
  }, [labJackConfig, checkLabJackConnection, showSnackbar]);


  // Individual video fullscreen functions - only for the video container
  const enterFullscreen = useCallback((video: VideoFile) => {
    setFullscreenVideo(video);
    setIsFullscreen(true);
    setVideoStartTime(Date.now());
    setCameraDetections([]); // Clear previous detections
    
    // Don't automatically request fullscreen - let the dialog handle it
    // Users can use browser fullscreen controls on the video element itself
  }, []);

  const exitFullscreen = useCallback(() => {
    setIsFullscreen(false);
    setFullscreenVideo(null);
    setVideoStartTime(null);
    
    // Exit fullscreen mode
    if (document.fullscreenElement) {
      document.exitFullscreen();
    }
  }, []);

  // Camera detection monitoring with timing analysis
  const startCameraMonitoring = useCallback(async () => {
    if (!labJackStatus.connected) {
      showSnackbar('LabJack not connected', 'error');
      return;
    }

    try {
      // Start voltage monitoring for camera detections
      const monitoringResponse = await apiService.startSignalMonitoring();
      
      if (monitoringResponse.status !== 'success' && monitoringResponse.status !== 'started') {
        showSnackbar(`Failed to start monitoring: ${monitoringResponse.message}`, 'error');
        return;
      }
      
      // Set up real-time voltage monitoring WebSocket for detection timing
      const wsUrl = process.env.REACT_APP_SOCKETIO_URL || process.env.REACT_APP_WS_URL || 'http://localhost:8001';
      const voltageWsUrl = wsUrl.replace('http', 'ws') + '/ws/signal-validation/voltage';
      const voltageWs = new WebSocket(voltageWsUrl);
      
      voltageWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const voltage = data.voltage;
          const timestamp = Date.now();
          
          // Check if voltage is within detection threshold (camera trigger)
          if (voltage >= labJackConfig.lowerBound && voltage <= labJackConfig.upperBound) {
            const videoTimestamp = videoStartTime ? timestamp - videoStartTime : undefined;
            
            // Calculate delay if we have video annotations to compare against
            let delay: number | undefined = undefined;
            if (videoTimestamp && fullscreenVideo) {
              // Find closest annotation timestamp for delay calculation
              // This would normally load from ground truth data
              delay = calculateAnnotationDelay(videoTimestamp, fullscreenVideo.id);
            }
            
            const detection: CameraDetection = {
              timestamp,
              voltage,
              channel: data.channel || labJackConfig.channel,
              videoTimestamp,
              delay
            };
            
            setCameraDetections(prev => [...prev, detection]);
            
            // Show real-time feedback for significant detections
            if (Math.abs(voltage - (labJackConfig.lowerBound + labJackConfig.upperBound) / 2) < 0.1) {
              showSnackbar(`Camera triggered: ${voltage.toFixed(2)}V${delay !== undefined ? ` (${delay}ms delay)` : ''}`, 'info');
            }
          }
        } catch (err) {
          console.error('Error processing voltage data:', err);
        }
      };
      
      voltageWs.onerror = () => {
        showSnackbar('Voltage monitoring WebSocket error', 'error');
      };
      
      voltageWs.onclose = () => {
        console.log('Voltage monitoring WebSocket closed');
      };
      
      showSnackbar('Camera monitoring started', 'success');
    } catch (error) {
      console.error('Failed to start camera monitoring:', error);
      showSnackbar('Failed to start camera monitoring', 'error');
    }
  }, [labJackStatus.connected, labJackConfig, videoStartTime, fullscreenVideo, showSnackbar]);

  // Calculate delay between camera detection and closest ground truth annotation
  const calculateAnnotationDelay = useCallback((videoTimestamp: number, videoId: string): number | undefined => {
    // This function would normally load ground truth annotations for the video
    // and find the closest annotation timestamp to calculate the delay
    
    // Mock implementation for now - in real implementation, this would:
    // 1. Load ground truth annotations for the video
    // 2. Find annotations within a reasonable time window (e.g., ±2 seconds)
    // 3. Calculate the minimum delay to any annotation
    // 4. Return the delay in milliseconds
    
    // Example: if an annotation exists at video timestamp 5000ms and camera detected at 5150ms
    // the delay would be 150ms
    
    // For now, return a placeholder delay for demonstration
    const mockAnnotationTimestamp = Math.floor(videoTimestamp / 1000) * 1000; // Round to nearest second
    return Math.abs(videoTimestamp - mockAnnotationTimestamp);
  }, []);

  // Stop camera monitoring and cleanup WebSocket connections
  const stopCameraMonitoring = useCallback(async () => {
    try {
      const stopResponse = await apiService.stopSignalMonitoring();
      showSnackbar(stopResponse.message || 'Camera monitoring stopped', 'info');
    } catch (error) {
      console.error('Failed to stop camera monitoring:', error);
      showSnackbar('Failed to stop camera monitoring', 'error');
    }
  }, [showSnackbar]);

  // ESC key handler for test stopping only
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Only stop test on ESC if running, no fullscreen management
      if (event.key === 'Escape' && isRunning) {
        event.preventDefault();
        event.stopPropagation();
        stopTestExecution();
      }
    };

    document.addEventListener('keydown', handleKeyDown, true);
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [isRunning, stopTestExecution]);

  // Remove fullscreen change listener - no longer managing page fullscreen

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
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load projects';
        showSnackbar(message, 'error');
      } finally {
        setLoading(false);
      }
    };

    loadProjects();
    loadSessions();
    performConnectionCheck();
    checkLabJackConnection(); // Check LabJack connection on load

    // Set up periodic connection checks
    connectionCheckInterval.current = setInterval(() => {
      performConnectionCheck();
      checkLabJackConnection();
    }, 30000);

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
    <Box sx={{ 
      p: { xs: 1, sm: 2, md: 3 }
    }}>
      {/* No page fullscreen indicator needed */}
      
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
                  onChange={async (e) => {
                    const project = projects.find(p => p.id === e.target.value);
                    setSelectedProject(project || null);
                    
                    // Automatically fetch videos for the selected project
                    if (project) {
                      try {
                        console.log(`🔄 Loading videos for project: ${project.name} (ID: ${project.id})`);
                        // Use the working getAllVideos API instead of the broken project-specific endpoint
                        const allVideosResponse = await getAllVideos(false, 0, 1000);
                        // Filter videos by the selected project ID
                        const videos = allVideosResponse.videos.filter(video => video.projectId === project.id);
                        console.log(`📹 Found ${videos.length} videos for project ${project.id} (filtered from ${allVideosResponse.videos.length} total):`, videos);
                        
                        if (videos.length === 0) {
                          console.log(`ℹ️ No videos linked to project ${project.name}. This is normal for new projects.`);
                          setSelectedVideos([]);
                          showSnackbar(`Project "${project.name}" has no videos linked. Please add videos from the Ground Truth library.`, 'info');
                        } else if (false) {
                          // Disabled: Only add mock videos in extreme fallback scenarios (API completely down)
                          console.warn(`⚠️ No videos found for project ${project.name}. Adding reliable test videos for sequential playback.`);
                          // Add reliable test videos for sequential playback testing
                          const reliableTestVideos: VideoFile[] = [
                            {
                              id: `mock-${project.id}-1`,
                              filename: 'big-buck-bunny-sample.mp4',
                              name: 'Big Buck Bunny Sample',
                              url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
                              duration: 596,
                              size: 158008374,
                              mimeType: 'video/mp4',
                              projectId: project.id,
                              uploadedAt: new Date(),
                              status: 'completed'
                            },
                            {
                              id: `mock-${project.id}-2`,
                              filename: 'elephants-dream-sample.mp4',
                              name: 'Elephants Dream Sample',
                              url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
                              duration: 653,
                              size: 125513024,
                              mimeType: 'video/mp4',
                              projectId: project.id,
                              uploadedAt: new Date(),
                              status: 'completed'
                            },
                            {
                              id: `mock-${project.id}-3`,
                              filename: 'for-bigger-blazes.mp4',
                              name: 'For Bigger Blazes',
                              url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                              duration: 15,
                              size: 2097152,
                              mimeType: 'video/mp4',
                              projectId: project.id,
                              uploadedAt: new Date(),
                              status: 'completed'
                            }
                          ];
                          setSelectedVideos(reliableTestVideos);
                          showSnackbar(`Added ${reliableTestVideos.length} reliable test videos for sequential playback testing`, 'info');
                        } else {
                          // Fix video URLs instead of filtering them out
                          const fixedVideos = videos.map(video => {
                            const originalUrl = video.url;
                            let fixedUrl = originalUrl;
                            
                            // Fix localhost URLs to use the correct backend server
                            if (originalUrl && (originalUrl.includes('localhost:8000') || originalUrl.includes('127.0.0.1:8000'))) {
                              try {
                                // Use the video utils to generate the proper URL
                                fixedUrl = generateVideoUrl({
                                  id: video.id,
                                  filename: video.filename || video.name || '',
                                  url: originalUrl
                                });
                                console.log(`🔧 Fixed video URL: ${originalUrl} → ${fixedUrl}`);
                              } catch (error) {
                                console.warn(`⚠️ Failed to fix video URL for ${video.filename}:`, error);
                                fixedUrl = originalUrl; // Keep original if fix fails
                              }
                            }
                            
                            return {
                              ...video,
                              url: fixedUrl
                            };
                          });
                          
                          setSelectedVideos(fixedVideos);
                          const localhostCount = videos.filter(v => v.url && (v.url.includes('localhost:8000') || v.url.includes('127.0.0.1:8000'))).length;
                          if (localhostCount > 0) {
                            showSnackbar(`Loaded ${fixedVideos.length} videos from project "${project.name}" (fixed ${localhostCount} localhost URLs)`, 'success');
                          } else {
                            showSnackbar(`Loaded ${fixedVideos.length} videos from project "${project.name}"`, 'success');
                          }
                        }
                      } catch (error) {
                        console.error('Failed to fetch videos for project:', error);
                        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
                        showSnackbar(`Failed to load videos: ${errorMessage}. Please check your connection and try again.`, 'error');
                        setSelectedVideos([]);
                        
                        // Mock videos disabled - we should always use real project videos
                        // Original logic kept for reference but disabled
                        const shouldUseMockVideos = false; // DISABLED - always use real videos
                        // const shouldUseMockVideos = process.env.NODE_ENV === 'development' && 
                        //                            (errorMessage.includes('Network Error') || errorMessage.includes('timeout'));
                        
                        if (shouldUseMockVideos) {
                          console.log('🧪 Development mode: Adding mock videos due to network error');
                          // Provide reliable test videos for testing when API fails
                          const fallbackTestVideos: VideoFile[] = [
                          {
                            id: `fallback-${project.id}-1`,
                            filename: 'big-buck-bunny-fallback.mp4',
                            name: 'Big Buck Bunny (Fallback)',
                            url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
                            duration: 596,
                            size: 158008374,
                            mimeType: 'video/mp4',
                            projectId: project.id,
                            uploadedAt: new Date(),
                            status: 'completed'
                          },
                          {
                            id: `fallback-${project.id}-2`,
                            filename: 'elephants-dream-fallback.mp4',
                            name: 'Elephants Dream (Fallback)',
                            url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
                            duration: 653,
                            size: 125513024,
                            mimeType: 'video/mp4',
                            projectId: project.id,
                            uploadedAt: new Date(),
                            status: 'completed'
                          },
                          {
                            id: `fallback-${project.id}-3`,
                            filename: 'for-bigger-blazes-fallback.mp4',
                            name: 'For Bigger Blazes (Fallback)',
                            url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                            duration: 15,
                            size: 2097152,
                            mimeType: 'video/mp4',
                            projectId: project.id,
                            uploadedAt: new Date(),
                            status: 'completed'
                          }
                        ];
                        setSelectedVideos(fallbackTestVideos);
                        showSnackbar(`Using ${fallbackTestVideos.length} mock videos for development testing`, 'warning');
                        } else {
                          // In production or non-network errors, don't use mock videos
                          console.log('🚫 Not using mock videos - error may be temporary or project legitimately has no videos');
                        }
                      }
                    } else {
                      console.log('🔄 No project selected, clearing videos');
                      setSelectedVideos([]);
                    }
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
          
          {!Array.isArray(sessions) || sessions.length === 0 ? (
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
                            setEditingSessionId(session.id);
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

      {/* Enhanced Sequential Video Player - Full automation with fullscreen */}
      {(() => {
        // Memoize selectedVideos to prevent unnecessary re-renders from LabJack updates
        const memoizedVideos = useMemo(() => selectedVideos, [
          selectedVideos.length,
          selectedVideos.map(v => v.id).join(',')
        ]);
        
        return selectedVideos.length > 0 ? (
          <>
            <SequentialVideoPlayer
          key="sequential-video-player"
          videos={memoizedVideos}
          config={{
            autoAdvance: testConfig.autoAdvance,
            loopPlayback: false, // FORCE NO LOOPING - videos play once only
            randomOrder: testConfig.randomOrder,
            preloadNext: true,
            fullscreenMode: true,
            autoFullscreen: true, // Auto-fullscreen video container on test start
            transitionDelay: testConfig.latencyMs,
            maxRetries: 3,
            enableHardwareAcceleration: true,
            syncWithExternalSignals: testConfig.syncExternalSignals,
          }}
          onVideoStart={(video, index) => {
            setVideoStartTime(Date.now());
            setPlaybackState(prev => ({
              ...prev,
              currentVideoIndex: index,
              playingVideo: video,
              isSequentialMode: true,
            }));
            // Only show message when video actually starts playing
            showSnackbar(
              `🎬 Now playing video ${index + 1}/${selectedVideos.length}: ${video.filename}`,
              'success'
            );
          }}
          onVideoEnd={(video, index) => {
            showSnackbar(
              `✅ Completed video ${index + 1}: ${video.filename}`,
              'success'
            );
          }}
          onPlaybackComplete={() => {
            console.log('🎬 Sequential video playback completed - stopping test execution');
            
            // Update playback state
            setPlaybackState(prev => ({
              ...prev,
              isSequentialMode: false,
              totalProgress: 100,
            }));
            
            // Stop the test execution
            setIsRunning(false);
            
            // Close WebSocket connection
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
            
            // Exit fullscreen if still active
            if (document.fullscreenElement) {
              document.exitFullscreen().catch(console.warn);
            }
            
            // Show completion message
            showSnackbar(
              '🎉 All videos completed! Test execution finished. Exited fullscreen.',
              'success'
            );
            
            // Export results if available
            setTimeout(() => {
              if (testResults.length > 0) {
                showSnackbar(
                  `📈 Final Results: ${testResults.filter(r => r.status === 'success').length}/${testResults.length} videos passed`,
                  'info'
                );
              }
            }, 2000);
          }}
          onError={(error) => {
            showSnackbar(
              `❌ Video ${error.videoIndex + 1} error: ${error.message}`,
              'error'
            );
          }}
          onProgressUpdate={(progress, videoIndex) => {
            setPlaybackState(prev => ({
              ...prev,
              totalProgress: progress,
              currentVideoIndex: videoIndex,
            }));
          }}
          autoStart={isRunning} // Auto-start when test execution begins
          showControls={true}
          showProgress={true}
          showQueue={true}
          syncWithLabJack={testConfig.syncExternalSignals}
          className="sequential-video-player test-execution-video-player"
        />
          </>
        ) : null;
      })()}
      
      {/* Test Execution Status - Fallback for non-sequential mode */}
      {isRunning && !playbackState.isSequentialMode && (
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

      {/* Simple LabJack Detection Panel - NO WebSocket complexity */}
      <SimpleDetectionPanel
        projectId={selectedProject?.id}
        toleranceMs={testConfig.latencyMs || 100}
        onDetectionComplete={(result) => {
          console.log('✅ Detection completed:', result);
          // Store detection results for post-processing
          setCameraDetections(result.data?.map(d => ({
            timestamp: d.timestamp,
            voltage: d.voltage,
            channel: 'AIN0'
          })) || []);
        }}
      />
      
      {/* LabJack Status Panel - Using dedicated component */}
      <LabJackStatusPanel
        onDataReceived={(data) => {
          // Handle streaming data from LabJack
          setCameraDetections(prev => [...prev.slice(-100), ...data.data.map((voltage, index) => ({
            timestamp: data.timestamp + (index * (1000 / data.sample_rate)),
            voltage,
            channel: data.channels[index] || 'AIN0',
            videoTimestamp: videoStartTime ? Date.now() - videoStartTime : undefined
          }))]);
        }}
        onStatusChanged={(status) => {
          // Update LabJack status when it changes
          setLabJackStatus({
            connected: status.connected,
            currentVoltages: (status.device_info && status.device_info.bridge_host) ? undefined : status.voltage_threshold ? { AIN0: status.voltage_threshold } : undefined,
            voltageThreshold: status.voltage_threshold,
            channels: status.channels,
            sampleRate: status.sample_rate,
            error: status.error_message
          });
        }}
      />

      {/* Selected Videos with Fullscreen Launch */}
      {selectedVideos.length > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Selected Videos ({selectedVideos.length})
            </Typography>
            
            <FixedGrid container spacing={2}>
              {selectedVideos.map((video, index) => (
                <FixedGrid xs={12} sm={6} md={4} key={video.id}>
                  <Card variant="outlined">
                    <CardContent sx={{ pb: '16px !important' }}>
                      <Typography variant="subtitle2" noWrap gutterBottom>
                        {video.filename || `Video ${index + 1}`}
                      </Typography>
                      
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Duration: {video.duration ? `${Math.round(video.duration)}s` : 'Unknown'}
                      </Typography>
                      
                      <Stack direction="row" spacing={1}>
                        <Button
                          variant="contained"
                          color="primary"
                          startIcon={<PlayIcon />}
                          onClick={() => enterFullscreen(video)}
                          disabled={!labJackStatus.connected}
                          size="small"
                          fullWidth
                        >
                          Play Fullscreen
                        </Button>
                      </Stack>
                      
                      {!labJackStatus.connected && (
                        <Typography variant="caption" color="error" sx={{ mt: 1, display: 'block' }}>
                          LabJack connection required
                        </Typography>
                      )}
                    </CardContent>
                  </Card>
                </FixedGrid>
              ))}
            </FixedGrid>
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
          setEditingSessionId(null);
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {editingSessionId ? 'Edit Session' : 'Create New Test Session'}
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
            setEditingSessionId(null);
          }}>
            Cancel
          </Button>
          <Button 
            onClick={createSession} 
            variant="contained"
            disabled={!sessionName.trim() || loading}
            startIcon={loading ? <CircularProgress size={16} /> : undefined}
          >
            {editingSessionId ? 'Update Session' : 'Create Session'}
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

      {/* LabJack Configuration Dialog */}
      <Dialog
        open={labJackConfigOpen}
        onClose={() => setLabJackConfigOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>LabJack Configuration</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Voltage Thresholds for Camera Detection
            </Typography>
            
            <FixedGrid container spacing={2} sx={{ mb: 3 }}>
              <FixedGrid xs={6}>
                <TextField
                  label="Lower Bound (V)"
                  type="number"
                  value={labJackConfig.lowerBound}
                  onChange={(e) => setLabJackConfig(prev => ({ 
                    ...prev, 
                    lowerBound: parseFloat(e.target.value) || 4.0 
                  }))}
                  InputProps={{ 
                    inputProps: { min: 0, max: 10, step: 0.1 }
                  }}
                  fullWidth
                  size="small"
                />
              </FixedGrid>
              
              <FixedGrid xs={6}>
                <TextField
                  label="Upper Bound (V)"
                  type="number"
                  value={labJackConfig.upperBound}
                  onChange={(e) => setLabJackConfig(prev => ({ 
                    ...prev, 
                    upperBound: parseFloat(e.target.value) || 5.5 
                  }))}
                  InputProps={{ 
                    inputProps: { min: 0, max: 10, step: 0.1 }
                  }}
                  fullWidth
                  size="small"
                />
              </FixedGrid>
            </FixedGrid>
            
            <Typography variant="subtitle2" gutterBottom>
              Sampling Configuration
            </Typography>
            
            <FixedGrid container spacing={2} sx={{ mb: 3 }}>
              <FixedGrid xs={6}>
                <TextField
                  label="Check Interval (s)"
                  type="number"
                  value={labJackConfig.checkInterval}
                  onChange={(e) => setLabJackConfig(prev => ({ 
                    ...prev, 
                    checkInterval: parseFloat(e.target.value) || 0.1 
                  }))}
                  InputProps={{ 
                    inputProps: { min: 0.01, max: 5, step: 0.01 }
                  }}
                  fullWidth
                  size="small"
                  helperText="How often to sample voltage"
                />
              </FixedGrid>
              
              <FixedGrid xs={6}>
                <FormControl fullWidth size="small">
                  <InputLabel>Channel</InputLabel>
                  <Select
                    value={labJackConfig.channel}
                    onChange={(e) => setLabJackConfig(prev => ({ 
                      ...prev, 
                      channel: e.target.value 
                    }))}
                  >
                    <MenuItem value="AIN0">AIN0</MenuItem>
                    <MenuItem value="AIN1">AIN1</MenuItem>
                    <MenuItem value="AIN2">AIN2</MenuItem>
                    <MenuItem value="AIN3">AIN3</MenuItem>
                  </Select>
                </FormControl>
              </FixedGrid>
            </FixedGrid>
            
            <Alert severity="info" sx={{ mb: 2 }}>
              Camera detection will trigger when voltage is between {labJackConfig.lowerBound}V 
              and {labJackConfig.upperBound}V on channel {labJackConfig.channel}.
              Sampling rate: {Math.round(1000 / (labJackConfig.checkInterval * 1000))} Hz
            </Alert>
            
            <Alert severity="warning">
              Changes take effect after reconnecting to LabJack.
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLabJackConfigOpen(false)}>
            Cancel
          </Button>
          <Button 
            onClick={() => {
              setLabJackConfigOpen(false);
              showSnackbar('LabJack configuration updated', 'success');
            }} 
            variant="contained"
          >
            Save Configuration
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

      {/* Fullscreen Video Player */}
      {isFullscreen && fullscreenVideo && (
        <Dialog
          open={isFullscreen}
          onClose={exitFullscreen}
          maxWidth={false}
          fullWidth
          PaperProps={{
            sx: {
              width: '100vw',
              height: '100vh',
              maxWidth: 'none',
              maxHeight: 'none',
              margin: 0,
              backgroundColor: 'black'
            }
          }}
        >
          <Box sx={{ 
            position: 'relative', 
            width: '100%', 
            height: '100%', 
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'black'
          }}>
            {/* Video Player */}
            <video
              key={fullscreenVideo.id}
              src={fullscreenVideo.url || ''}
              controls
              style={{
                width: '100%',
                height: 'auto',
                maxHeight: '90%',
                objectFit: 'contain'
              }}
              onPlay={() => {
                setVideoStartTime(Date.now());
                startCameraMonitoring();
                showSnackbar(`Now playing: ${fullscreenVideo.filename}`, 'success');
              }}
              onPause={() => {
                stopCameraMonitoring();
                showSnackbar('Video paused', 'info');
              }}
              onEnded={() => {
                stopCameraMonitoring();
                showSnackbar(`Video completed: ${fullscreenVideo.filename}`, 'success');
                exitFullscreen();
              }}
              onError={(e) => {
                console.error('Video error:', e);
                showSnackbar(`Video playback error: ${fullscreenVideo.filename}`, 'error');
              }}
            />
            
            {/* Overlay Controls */}
            <Box sx={{
              position: 'absolute',
              top: 16,
              left: 16,
              right: 16,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              zIndex: 1000
            }}>
              <Typography variant="h6" color="white" sx={{ textShadow: '2px 2px 4px rgba(0,0,0,0.8)' }}>
                {fullscreenVideo.filename}
              </Typography>
              
              <Box sx={{ display: 'flex', gap: 1 }}>
                {/* LabJack Status */}
                <Chip
                  icon={labJackStatus.connected ? <CheckCircleIcon /> : <ErrorIcon />}
                  label={`LabJack: ${labJackStatus.connected ? 'Connected' : 'Disconnected'}`}
                  color={labJackStatus.connected ? 'success' : 'error'}
                  size="small"
                />
                
                {/* Current Voltage Display */}
                {labJackStatus.connected && labJackStatus.currentVoltages && (
                  <Chip
                    label={`Voltage: ${Object.values(labJackStatus.currentVoltages)[0]?.toFixed(2) || 'N/A'}V`}
                    color="info"
                    size="small"
                  />
                )}
                
                <Button
                  variant="outlined"
                  color="warning"
                  size="small"
                  onClick={stopCameraMonitoring}
                  sx={{ mr: 1 }}
                >
                  Stop Monitoring
                </Button>
                
                <Button
                  variant="contained"
                  color="error"
                  size="small"
                  onClick={() => {
                    stopCameraMonitoring();
                    exitFullscreen();
                  }}
                  startIcon={<StopIcon />}
                >
                  Exit Fullscreen
                </Button>
              </Box>
            </Box>

            {/* Camera Detection Log */}
            {cameraDetections.length > 0 && (
              <Box sx={{
                position: 'absolute',
                bottom: 16,
                left: 16,
                right: 16,
                maxHeight: '250px',
                overflowY: 'auto',
                backgroundColor: 'rgba(0,0,0,0.9)',
                borderRadius: 1,
                p: 2
              }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="subtitle2" color="white">
                    Camera Detections ({cameraDetections.length})
                  </Typography>
                  
                  {/* Timing Statistics */}
                  <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <Typography variant="caption" color="white">
                      Avg Delay: {
                        cameraDetections.filter(d => d.delay !== undefined).length > 0
                          ? `${Math.round(
                              cameraDetections
                                .filter(d => d.delay !== undefined)
                                .reduce((sum, d) => sum + (d.delay || 0), 0) /
                              cameraDetections.filter(d => d.delay !== undefined).length
                            )}ms`
                          : 'N/A'
                      }
                    </Typography>
                    
                    <Typography variant="caption" color="white">
                      Video Time: {
                        videoStartTime 
                          ? `${Math.round((Date.now() - videoStartTime) / 1000)}s`
                          : '0s'
                      }
                    </Typography>
                  </Box>
                </Box>
                
                {/* Detection List */}
                <Box sx={{ maxHeight: 180, overflowY: 'auto' }}>
                  {cameraDetections.slice(-8).map((detection, index) => (
                    <Box
                      key={index}
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        py: 0.5,
                        px: 1,
                        mb: 0.5,
                        backgroundColor: 'rgba(255,255,255,0.1)',
                        borderRadius: 0.5,
                        fontFamily: 'monospace',
                        fontSize: '0.75rem'
                      }}
                    >
                      <Box sx={{ color: 'white' }}>
                        <Typography variant="caption" sx={{ display: 'block', fontFamily: 'monospace' }}>
                          {new Date(detection.timestamp).toLocaleTimeString()}
                        </Typography>
                        <Typography variant="caption" color="grey.300" sx={{ fontFamily: 'monospace' }}>
                          {detection.channel} | {detection.voltage.toFixed(2)}V
                        </Typography>
                      </Box>
                      
                      <Box sx={{ textAlign: 'right' }}>
                        {detection.videoTimestamp !== undefined && (
                          <Typography variant="caption" color="cyan" sx={{ display: 'block', fontFamily: 'monospace' }}>
                            @{Math.round(detection.videoTimestamp / 1000)}s
                          </Typography>
                        )}
                        {detection.delay !== undefined && (
                          <Typography
                            variant="caption"
                            sx={{ 
                              display: 'block',
                              fontFamily: 'monospace',
                              color: detection.delay < 100 ? 'lightgreen' : detection.delay < 500 ? 'yellow' : 'orange'
                            }}
                          >
                            Δ{detection.delay}ms
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        </Dialog>
      )}
    </Box>
  );
};

export default EnhancedTestExecution;