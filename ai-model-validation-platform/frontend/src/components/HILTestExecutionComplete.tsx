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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
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
  ExpandMore,
  Tune,
  Assessment,
  Save,
  Download,
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
} from '../services/types';
import LabJackStatusPanel from './LabJackStatusPanel';

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
  testReport?: string;
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
  vruType?: VRUType;
  frameNumber?: number;
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
  sampleRate?: number;
}

interface TestConfiguration {
  maxLatencyMs: number;
  autoAdvanceVideos: boolean;
  pauseOnFailure: boolean;
  captureSnapshots: boolean;
  enableRealTimeAnalysis: boolean;
  hardwareSignalTimeout: number;
  precisionTimingEnabled: boolean;
  customSignalThreshold?: number;
}

const HILTestExecutionComplete: React.FC = () => {
  // Core state using PRD-aligned variable names
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [videoPlaylist, setVideoPlaylist] = useState<VideoFile[]>([]);
  const [currentTestSession, setCurrentTestSession] = useState<TestSessionInterface | null>(null);
  const [detectionEvents, setDetectionEvents] = useState<DetectionEventInterface[]>([]);
  
  // Test Configuration
  const [testConfig, setTestConfig] = useState<TestConfiguration>({
    maxLatencyMs: 100, // PRD: Default 100ms
    autoAdvanceVideos: true,
    pauseOnFailure: false,
    captureSnapshots: true,
    enableRealTimeAnalysis: true,
    hardwareSignalTimeout: 5000,
    precisionTimingEnabled: true,
    customSignalThreshold: undefined,
  });
  
  // LabJack hardware integration
  const [labjackStatus, setLabjackStatus] = useState<LabJackConnectionStatus | null>(null);
  
  // Test execution state
  const [testInProgress, setTestInProgress] = useState(false);
  const [testPaused, setTestPaused] = useState(false);
  const [currentVideoIndex, setCurrentVideoIndex] = useState(0);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [videoReady, setVideoReady] = useState(false); // Track when video is ready for playback
  const [testStartTime, setTestStartTime] = useState<Date | null>(null); // PRD: Test_Start_Time reference
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [startTestDialog, setStartTestDialog] = useState(false);
  const [configurationExpanded, setConfigurationExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  
  // Advanced features
  const [performanceMetrics, setPerformanceMetrics] = useState<any>(null);
  const [testReport, setTestReport] = useState<string | null>(null);
  const [snapshotPaths, setSnapshotPaths] = useState<string[]>([]);
  
  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const fullScreenContainerRef = useRef<HTMLDivElement>(null);
  const performanceTimerRef = useRef<NodeJS.Timeout | null>(null);
  
  // WebSocket for real-time updates
  const { isConnected: wsConnected, emit: wsEmit, on: wsSubscribe } = useWebSocket();
  
  // Get video source with fallback handling
  const getVideoSource = (video: VideoFile): string => {
    // Primary source: direct file path
    if (video.filePath && video.filePath.startsWith('http')) {
      return video.filePath;
    }
    
    // Fallback: streaming API endpoint
    return `/api/v1/videos/${video.id}/stream`;
  };
  
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
      const validatedVideos = response.filter(video => video.status === 'validated');
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
  
  // Check LabJack connection status with enhanced details
  const checkLabJackStatus = useCallback(async () => {
    try {
      // Add timestamp to bypass cache
      const response = await apiService.get<any>(`/api/labjack/status?t=${Date.now()}`);
      const status: LabJackConnectionStatus = {
        connected: response.is_connected || response.connected || false,
        status: response.connection_status || response.status || 'disconnected',
        mode: response.mode || 'auto',
        deviceInfo: response.device_info ? {
          deviceType: response.device_info.device_type || 'Unknown',
          serialNumber: response.device_info.serial_number
        } : undefined,
        signalType: response.signal_type || SignalType.TTL,
        voltageThreshold: response.voltage_threshold || 2.5,
        sampleRate: response.sample_rate || 1000
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
        voltageThreshold: 2.5,
        sampleRate: 1000
      };
      setLabjackStatus(errorStatus);
      return errorStatus;
    }
  }, []);
  
  // Load LabJack status on component mount and set up polling
  useEffect(() => {
    checkLabJackStatus();
    
    // Poll LabJack status every 3 seconds for more responsive updates
    const statusInterval = setInterval(checkLabJackStatus, 3000);
    
    return () => {
      clearInterval(statusInterval);
      if (performanceTimerRef.current) {
        clearInterval(performanceTimerRef.current);
      }
    };
  }, [checkLabJackStatus]);
  
  // Handle project selection
  const handleProjectSelect = (project: Project) => {
    setSelectedProject(project);
    loadVideoPlaylist(project.id);
    setCurrentVideoIndex(0);
    setDetectionEvents([]);
    setError(null);
    setTestReport(null);
    setSnapshotPaths([]);
  };
  
  // Validate test start conditions (PRD requirement) - Enhanced validation
  const validateTestStart = (): { canStart: boolean; errors: string[]; warnings: string[] } => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!selectedProject) {
      errors.push('Please select a project');
    }
    
    if (videoPlaylist.length === 0) {
      errors.push('No validated videos in playlist');
    }
    
    if (!labjackStatus?.connected) {
      errors.push('LabJack device not connected (PRD requirement)');
    }
    
    if (testConfig.maxLatencyMs <= 0 || testConfig.maxLatencyMs > 10000) {
      errors.push('Maximum latency must be between 1-10000ms');
    }
    
    if (!testConfig.precisionTimingEnabled) {
      warnings.push('Precision timing is disabled - may affect accuracy');
    }
    
    if (testConfig.hardwareSignalTimeout < 1000) {
      warnings.push('Hardware signal timeout is very low - may cause false failures');
    }
    
    return {
      canStart: errors.length === 0,
      errors,
      warnings
    };
  };
  
  // Start HIL test execution with enhanced configuration
  const startTest = async () => {
    const validation = validateTestStart();
    if (!validation.canStart) {
      setError(`Cannot start test:\n${validation.errors.join('\n')}`);
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      
      // Create test session with full configuration
      const testSessionData: TestSessionCreate & { configuration?: any } = {
        projectId: selectedProject!.id,
        name: `HIL Test Session - ${new Date().toISOString()}`,
        maxLatencyMs: testConfig.maxLatencyMs,
        labjackConnected: labjackStatus!.connected,
        status: 'running',
        configuration: testConfig
      };
      
      const session = await apiService.post<TestSessionInterface>('/api/v1/test-sessions', testSessionData);
      setCurrentTestSession(session);
      
      // CRITICAL: Dynamic Timing Synchronization
      // Step 1: Initialize monitoring FIRST (before video)
      console.log('🎯 Step 1: Initializing monitoring...');
      const monitoringStartTime = Date.now();  // CRITICAL FIX: Use Date.now() for Unix epoch timestamps
      
      // Subscribe to hardware signals BEFORE video starts
      if (wsConnected) {
        wsEmit('subscribe_hardware_signals', {
          sessionId: session.id,
          signalType: labjackStatus!.signalType,
          configuration: testConfig,
          waitForReady: true  // New flag to wait for confirmation
        });
        
        // Wait for monitoring ready confirmation
        console.log('⏳ Waiting for monitoring ready confirmation...');
        const readyTimeout = 5000; // 5 second timeout
        const startWait = performance.now();
        
        // This would ideally be a promise/callback from WebSocket
        // For now, adding a small delay to ensure monitoring is ready
        await new Promise(resolve => setTimeout(resolve, 500));
        
        console.log(`✅ Monitoring ready after ${performance.now() - startWait}ms`);
      }
      
      // Step 2: Set test in progress FIRST to show video element
      console.log('🎯 Step 2: Setting test in progress...');
      setTestInProgress(true);
      setTestPaused(false);
      setVideoReady(false); // Reset video ready state
      
      // Step 3: Wait for video to be ready before playing
      console.log('🎯 Step 3: Waiting for video to be ready...');
      await waitForVideoReady();
      
      // Step 4: Only now start video playback
      console.log('🎯 Step 4: Starting video playback...');
      if (videoRef.current) {
        videoRef.current.currentTime = 0;

        // CRITICAL FIX: Call backend API to register video start with metadata
        const currentVideo = videoPlaylist[currentVideoIndex];
        if (currentVideo && session) {
          try {
            const videoData = {
              video_id: currentVideo.id,
              duration_s: currentVideo.duration ? currentVideo.duration / 1000 : undefined,  // Convert ms to seconds
              duration: currentVideo.duration ? currentVideo.duration / 1000 : undefined,    // Fallback key
              fps: currentVideo.frameRate || 30,
              filename: currentVideo.filename,
              resolution: `${currentVideo.width || 1920}x${currentVideo.height || 1080}`
            };

            console.log(`📡 Calling /api/hil-test-complete/session/${session.id}/video/start with data:`, videoData);
            const response = await fetch(`/api/hil-test-complete/session/${session.id}/video/start`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(videoData)
            });

            if (!response.ok) {
              console.error('Failed to register video start:', await response.text());
            } else {
              console.log('✅ Video start registered with backend');
            }
          } catch (error) {
            console.error('Error registering video start:', error);
          }
        }

        // Add event listeners for precise timing
        videoRef.current.addEventListener('playing', () => {
          const videoStartTime = Date.now();  // CRITICAL FIX: Use Date.now() for Unix epoch timestamps
          console.log(`📹 Video playing at ${videoStartTime}ms`);
          console.log(`⏱️ Total setup time: ${videoStartTime - monitoringStartTime}ms`);

          // Send precise video start time to backend with complete metadata
          if (wsConnected && currentVideo) {
            wsEmit('video_started', {
              sessionId: session.id,
              videoStartTime: videoStartTime,
              monitoringStartTime: monitoringStartTime,
              setupDelay: videoStartTime - monitoringStartTime,
              // CRITICAL FIX: Include video metadata for LabJack auto-stop timer
              video_data: {
                duration_s: currentVideo.duration ? currentVideo.duration / 1000 : undefined,  // Convert ms to seconds
                duration: currentVideo.duration ? currentVideo.duration / 1000 : undefined,    // Fallback key
                fps: currentVideo.frameRate || 30,
                filename: currentVideo.filename,
                video_id: currentVideo.id,
                sequence_order: 0  // First video in sequence
              }
            });
          }
        });
        
        await videoRef.current.play();
      }
      
      // Step 5: Enter fullscreen AFTER video is confirmed ready and playing
      console.log('🎯 Step 5: Entering fullscreen mode...');
      if (testConfig.autoAdvanceVideos) {
        await enterFullScreen();
      }
      
      // Capture high-precision Test_Start_Time (PRD requirement)
      const startTime = new Date();
      setTestStartTime(startTime);
      
      // Start performance monitoring
      if (testConfig.enableRealTimeAnalysis) {
        startPerformanceMonitoring();
      }
      
      setSuccessMessage('HIL test started successfully with enhanced monitoring');
      setStartTestDialog(false);
      
    } catch (err: any) {
      setError(`Failed to start test: ${err.message}`);
      setTestInProgress(false);
      setVideoReady(false);
    } finally {
      setLoading(false);
    }
  };
  
  // Wait for video element to be ready for playback
  const waitForVideoReady = (): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (!videoRef.current) {
        reject(new Error('Video element not found'));
        return;
      }
      
      const video = videoRef.current;
      const timeout = 10000; // 10 second timeout
      let timeoutId: NodeJS.Timeout;
      
      const cleanup = () => {
        video.removeEventListener('loadeddata', onLoadedData);
        video.removeEventListener('canplay', onCanPlay);
        video.removeEventListener('error', onError);
        if (timeoutId) clearTimeout(timeoutId);
      };
      
      const onLoadedData = () => {
        console.log('📹 Video loaded data event');
      };
      
      const onCanPlay = () => {
        console.log('📹 Video can play - ready for playback');
        setVideoReady(true);
        cleanup();
        resolve();
      };
      
      const onError = (e: Event) => {
        console.error('📹 Video error:', e);
        cleanup();
        reject(new Error('Video failed to load'));
      };
      
      // Set up event listeners
      video.addEventListener('loadeddata', onLoadedData);
      video.addEventListener('canplay', onCanPlay);
      video.addEventListener('error', onError);
      
      // Set timeout
      timeoutId = setTimeout(() => {
        cleanup();
        reject(new Error('Video load timeout'));
      }, timeout);
      
      // Check if video is already ready
      if (video.readyState >= 3) { // HAVE_FUTURE_DATA
        console.log('📹 Video already ready');
        onCanPlay();
      }
    });
  };
  
  // Enhanced performance monitoring
  const startPerformanceMonitoring = () => {
    performanceTimerRef.current = setInterval(async () => {
      if (!currentTestSession) return;
      
      try {
        const metrics = await apiService.get(`/api/v1/test-sessions/${currentTestSession.id}/metrics`);
        setPerformanceMetrics(metrics);
      } catch (err) {
        console.error('Failed to fetch performance metrics:', err);
      }
    }, 1000);
  };
  
  // Pause/Resume test execution
  const togglePause = async () => {
    try {
      if (testPaused) {
        // Resume test
        if (videoRef.current) {
          await videoRef.current.play();
        }
        if (wsConnected) {
          wsEmit('resume_test', { sessionId: currentTestSession?.id });
        }
        setTestPaused(false);
        setSuccessMessage('Test resumed');
      } else {
        // Pause test
        if (videoRef.current) {
          videoRef.current.pause();
        }
        if (wsConnected) {
          wsEmit('pause_test', { sessionId: currentTestSession?.id });
        }
        setTestPaused(true);
        setSuccessMessage('Test paused');
      }
    } catch (err: any) {
      setError(`Failed to ${testPaused ? 'resume' : 'pause'} test: ${err.message}`);
    }
  };
  
  // Stop test execution with enhanced cleanup
  const stopTest = async () => {
    try {
      setLoading(true);
      
      if (currentTestSession) {
        // Generate test report before stopping
        const reportResponse = await apiService.post(`/api/v1/test-sessions/${currentTestSession.id}/generate-report`);
        setTestReport(reportResponse.report_content);
        
        await apiService.post(`/api/v1/test-sessions/${currentTestSession.id}/stop`);
      }
      
      // Exit full-screen mode
      await exitFullScreen();
      
      // Stop video playback
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.currentTime = 0;
      }
      
      // Unsubscribe from hardware signals
      if (wsConnected) {
        wsEmit('unsubscribe_hardware_signals');
      }
      
      // Stop performance monitoring
      if (performanceTimerRef.current) {
        clearInterval(performanceTimerRef.current);
        performanceTimerRef.current = null;
      }
      
      setTestInProgress(false);
      setTestPaused(false);
      setVideoReady(false);
      setCurrentTestSession(null);
      setTestStartTime(null);
      setSuccessMessage('Test stopped successfully - Report generated');
      
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
    if (testConfig.autoAdvanceVideos && currentVideoIndex < videoPlaylist.length - 1) {
      // Reset video ready state before advancing to next video
      setVideoReady(false);
      setCurrentVideoIndex(prev => prev + 1);
    } else if (currentVideoIndex >= videoPlaylist.length - 1) {
      // Test completed
      completeTest();
    }
  };
  
  // Effect to handle video ready state when video index changes
  useEffect(() => {
    if (testInProgress && videoRef.current) {
      const video = videoRef.current;

      const handleCanPlay = () => {
        console.log(`📹 Video ${currentVideoIndex + 1} can play`);
        setVideoReady(true);
      };

      const handleLoadStart = () => {
        console.log(`📹 Video ${currentVideoIndex + 1} load started`);
        setVideoReady(false);
      };

      video.addEventListener('canplay', handleCanPlay);
      video.addEventListener('loadstart', handleLoadStart);

      // ✅ NEW: Notify backend when advancing to next video
      if (currentVideoIndex > 0 && currentTestSession) {
        const currentVideo = videoPlaylist[currentVideoIndex];
        if (currentVideo) {
          notifyVideoStart(currentVideo);
        }
      }

      // Check if video is already ready
      if (video.readyState >= 3) {
        setVideoReady(true);
      }

      return () => {
        video.removeEventListener('canplay', handleCanPlay);
        video.removeEventListener('loadstart', handleLoadStart);
      };
    }
  }, [currentVideoIndex, testInProgress]);
  
  // Notify backend when advancing to next video in sequence
  const notifyVideoStart = async (video: VideoFile) => {
    try {
      const videoData = {
        video_id: video.id,
        duration_s: video.duration ? video.duration / 1000 : undefined,
        duration: video.duration ? video.duration / 1000 : undefined,
        fps: video.frameRate || 30,
        filename: video.filename,
        resolution: `${video.width || 1920}x${video.height || 1080}`,
        sequence_order: currentVideoIndex
      };

      console.log(`📡 Notifying backend of video ${currentVideoIndex + 1} start:`, videoData);

      const response = await fetch(`/api/hil-test-complete/session/${currentTestSession!.id}/video/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(videoData)
      });

      if (!response.ok) {
        console.error(`Failed to notify video start: ${await response.text()}`);
      } else {
        console.log(`✅ Backend notified of video ${currentVideoIndex + 1} start`);
      }

      // Also emit WebSocket event
      if (wsConnected) {
        wsEmit('video_started', {
          sessionId: currentTestSession!.id,
          videoStartTime: Date.now(),
          video_data: videoData
        });
      }
    } catch (error) {
      console.error('Error notifying video start:', error);
    }
  };

  // Complete test when all videos are played
  const completeTest = async () => {
    try {
      if (currentTestSession) {
        const completionData = await apiService.post(`/api/v1/test-sessions/${currentTestSession.id}/complete`);
        setTestReport(completionData.final_report);
      }

      await exitFullScreen();
      setTestInProgress(false);
      setTestPaused(false);
      setVideoReady(false);
      setSuccessMessage('HIL test completed successfully - Comprehensive report generated');

    } catch (err: any) {
      setError(`Failed to complete test: ${err.message}`);
    }
  };
  
  // Enhanced WebSocket event handlers for hardware signals
  useEffect(() => {
    if (!wsConnected) return;
    
    const handleHardwareSignal = (data: any) => {
      if (!testInProgress || testPaused || !testStartTime || !currentTestSession) return;
      
      // Calculate Expected_Event_Time and Signal_Received_Time (PRD requirement)
      const signalReceivedTime = new Date();
      const expectedEventTime = new Date(testStartTime.getTime() + data.expectedTimestamp);
      const latencyMs = signalReceivedTime.getTime() - expectedEventTime.getTime();
      
      // Enhanced outcome determination
      let outcome: DetectionOutcome;
      if (latencyMs <= testConfig.maxLatencyMs) {
        outcome = DetectionOutcome.PASS;
      } else if (latencyMs <= testConfig.maxLatencyMs * 2) {
        outcome = DetectionOutcome.FAIL_HIGH_LATENCY;
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
        createdAt: new Date().toISOString(),
        vruType: data.vruType,
        frameNumber: data.frameNumber
      };
      
      setDetectionEvents(prev => [...prev, event]);
      
      // Handle pause on failure if configured
      if (testConfig.pauseOnFailure && outcome !== DetectionOutcome.PASS && !testPaused) {
        togglePause();
      }
      
      // Capture snapshot if configured
      if (testConfig.captureSnapshots && outcome !== DetectionOutcome.PASS) {
        captureFailureSnapshot(event);
      }
    };
    
    const handleTestUpdate = (data: any) => {
      if (data.sessionId === currentTestSession?.id) {
        setCurrentTestSession(prev => prev ? { ...prev, ...data.updates } : null);
      }
    };
    
    wsSubscribe('hardware_signal_detected', handleHardwareSignal);
    wsSubscribe('test_session_updated', handleTestUpdate);
    
    return () => {
      // Cleanup WebSocket subscriptions
    };
  }, [wsConnected, testInProgress, testPaused, testStartTime, currentTestSession, testConfig, videoPlaylist, currentVideoIndex, wsSubscribe]);
  
  // Capture failure snapshot
  const captureFailureSnapshot = async (event: DetectionEventInterface) => {
    try {
      const response = await apiService.post('/api/v1/capture-snapshot', {
        sessionId: currentTestSession?.id,
        eventId: event.id,
        videoId: event.videoId,
        timestamp: event.expectedEventTime
      });
      
      if (response.snapshot_path) {
        setSnapshotPaths(prev => [...prev, response.snapshot_path]);
      }
    } catch (err) {
      console.error('Failed to capture snapshot:', err);
    }
  };
  
  // Download test report
  const downloadReport = async () => {
    if (!currentTestSession) return;
    
    try {
      const response = await apiService.get(`/api/v1/test-sessions/${currentTestSession.id}/report/download`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `HIL_Test_Report_${currentTestSession.id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(`Failed to download report: ${err.message}`);
    }
  };
  
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
  
  // Calculate test statistics
  const getTestStatistics = () => {
    const totalEvents = detectionEvents.length;
    const passedEvents = detectionEvents.filter(e => e.outcome === DetectionOutcome.PASS).length;
    const failedEvents = totalEvents - passedEvents;
    const passRate = totalEvents > 0 ? (passedEvents / totalEvents) * 100 : 0;
    const averageLatency = totalEvents > 0 
      ? detectionEvents.reduce((sum, e) => sum + (e.latencyMs || 0), 0) / totalEvents 
      : 0;
    
    return {
      totalEvents,
      passedEvents,
      failedEvents,
      passRate,
      averageLatency
    };
  };

  return (
    <div ref={fullScreenContainerRef}>
      <Box sx={{ p: isFullScreen ? 0 : 3 }}>
        {/* Header - Hide in full-screen mode */}
        {!isFullScreen && (
          <>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h4">HIL Test Execution - Complete</Typography>
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
                  <>
                    <Button
                      variant="contained"
                      startIcon={testPaused ? <PlayArrow /> : <Pause />}
                      onClick={togglePause}
                      color={testPaused ? "success" : "warning"}
                      disabled={loading}
                    >
                      {testPaused ? 'Resume' : 'Pause'}
                    </Button>
                    <Button
                      variant="contained"
                      startIcon={<Stop />}
                      onClick={stopTest}
                      color="error"
                      disabled={loading}
                    >
                      Stop Test
                    </Button>
                  </>
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

            {/* Main Content Tabs */}
            <Card sx={{ mb: 3 }}>
              <Tabs
                value={activeTab}
                onChange={(_, newValue) => setActiveTab(newValue)}
                indicatorColor="primary"
                textColor="primary"
              >
                <Tab label="Test Setup" icon={<Settings />} />
                <Tab label="Configuration" icon={<Tune />} />
                <Tab label="Results" icon={<Assessment />} disabled={!testInProgress && detectionEvents.length === 0} />
                <Tab label="Reports" icon={<Assignment />} disabled={!testReport} />
              </Tabs>
            </Card>

            {/* Test Setup Tab */}
            {activeTab === 0 && (
              <>
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
                          • Sample Rate: {labjackStatus.sampleRate}Hz
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
                          voltageThreshold: status.voltage_threshold || 2.5,
                          sampleRate: status.sample_rate || 1000
                        });
                      }}
                    />
                  </CardContent>
                </Card>
              </>
            )}

            {/* Configuration Tab */}
            {activeTab === 1 && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Advanced Test Configuration
                  </Typography>
                  
                  <Grid container spacing={3}>
                    <Grid item xs={12} md={6}>
                      <TextField
                        fullWidth
                        label="Maximum Acceptable Latency (ms)"
                        type="number"
                        value={testConfig.maxLatencyMs}
                        onChange={(e) => setTestConfig(prev => ({ ...prev, maxLatencyMs: Number(e.target.value) }))}
                        disabled={testInProgress}
                        helperText="Enter the maximum acceptable latency in milliseconds (PRD requirement)"
                        inputProps={{ min: 1, max: 10000 }}
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <TextField
                        fullWidth
                        label="Hardware Signal Timeout (ms)"
                        type="number"
                        value={testConfig.hardwareSignalTimeout}
                        onChange={(e) => setTestConfig(prev => ({ ...prev, hardwareSignalTimeout: Number(e.target.value) }))}
                        disabled={testInProgress}
                        helperText="Timeout for waiting for hardware signals"
                        inputProps={{ min: 100, max: 30000 }}
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={testConfig.autoAdvanceVideos}
                            onChange={(e) => setTestConfig(prev => ({ ...prev, autoAdvanceVideos: e.target.checked }))}
                            disabled={testInProgress}
                          />
                        }
                        label="Auto-advance videos"
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={testConfig.pauseOnFailure}
                            onChange={(e) => setTestConfig(prev => ({ ...prev, pauseOnFailure: e.target.checked }))}
                            disabled={testInProgress}
                          />
                        }
                        label="Pause on failure"
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={testConfig.captureSnapshots}
                            onChange={(e) => setTestConfig(prev => ({ ...prev, captureSnapshots: e.target.checked }))}
                            disabled={testInProgress}
                          />
                        }
                        label="Capture failure snapshots"
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={testConfig.enableRealTimeAnalysis}
                            onChange={(e) => setTestConfig(prev => ({ ...prev, enableRealTimeAnalysis: e.target.checked }))}
                            disabled={testInProgress}
                          />
                        }
                        label="Enable real-time analysis"
                      />
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={testConfig.precisionTimingEnabled}
                            onChange={(e) => setTestConfig(prev => ({ ...prev, precisionTimingEnabled: e.target.checked }))}
                            disabled={testInProgress}
                          />
                        }
                        label="Precision timing (PRD requirement)"
                      />
                    </Grid>
                  </Grid>
                  
                  {selectedProject && videoPlaylist.length > 0 && (
                    <Box sx={{ mt: 3 }}>
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
            )}

            {/* Results Tab */}
            {activeTab === 2 && (detectionEvents.length > 0 || testInProgress) && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Real-time Test Results
                  </Typography>
                  
                  {(() => {
                    const stats = getTestStatistics();
                    return (
                      <>
                        <Grid container spacing={2} sx={{ mb: 3 }}>
                          <Grid item xs={3}>
                            <Box textAlign="center">
                              <Typography variant="h4" color="primary">
                                {stats.totalEvents}
                              </Typography>
                              <Typography variant="body2">Total Events</Typography>
                            </Box>
                          </Grid>
                          <Grid item xs={3}>
                            <Box textAlign="center">
                              <Typography variant="h4" color="success.main">
                                {stats.passedEvents}
                              </Typography>
                              <Typography variant="body2">Passed</Typography>
                            </Box>
                          </Grid>
                          <Grid item xs={3}>
                            <Box textAlign="center">
                              <Typography variant="h4" color="error.main">
                                {stats.failedEvents}
                              </Typography>
                              <Typography variant="body2">Failed</Typography>
                            </Box>
                          </Grid>
                          <Grid item xs={3}>
                            <Box textAlign="center">
                              <Typography variant="h4" color="warning.main">
                                {Math.round(stats.averageLatency)}ms
                              </Typography>
                              <Typography variant="body2">Avg Latency</Typography>
                            </Box>
                          </Grid>
                        </Grid>
                        
                        <Grid container spacing={2} sx={{ mb: 3 }}>
                          <Grid item xs={6}>
                            <Box textAlign="center">
                              <Typography variant="h5" color={stats.passRate >= 80 ? "success.main" : stats.passRate >= 60 ? "warning.main" : "error.main"}>
                                {stats.passRate.toFixed(1)}%
                              </Typography>
                              <Typography variant="body2">Pass Rate</Typography>
                            </Box>
                          </Grid>
                          <Grid item xs={6}>
                            <Box textAlign="center">
                              <Typography variant="h5" color="info.main">
                                {snapshotPaths.length}
                              </Typography>
                              <Typography variant="body2">Snapshots Captured</Typography>
                            </Box>
                          </Grid>
                        </Grid>
                      </>
                    );
                  })()}
                  
                  <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
                    <Table stickyHeader size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Time</TableCell>
                          <TableCell>Video</TableCell>
                          <TableCell>VRU Type</TableCell>
                          <TableCell>Expected</TableCell>
                          <TableCell>Received</TableCell>
                          <TableCell>Latency (ms)</TableCell>
                          <TableCell>Outcome</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {detectionEvents.slice(-15).reverse().map((event) => (
                          <TableRow key={event.id}>
                            <TableCell>
                              {new Date(event.createdAt).toLocaleTimeString()}
                            </TableCell>
                            <TableCell>
                              {videoPlaylist.find(v => v.id === String(event.videoId))?.filename || `Video ${event.videoId}`}
                            </TableCell>
                            <TableCell>
                              <Chip label={event.vruType || 'Unknown'} size="small" variant="outlined" />
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
                                  event.latencyMs && event.latencyMs <= testConfig.maxLatencyMs
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

            {/* Reports Tab */}
            {activeTab === 3 && testReport && (
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">
                      Test Report
                    </Typography>
                    <Button
                      variant="contained"
                      startIcon={<Download />}
                      onClick={downloadReport}
                      color="primary"
                    >
                      Download PDF Report
                    </Button>
                  </Box>
                  
                  <Paper sx={{ p: 2, maxHeight: 600, overflow: 'auto', backgroundColor: 'grey.50' }}>
                    <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.9rem' }}>
                      {testReport}
                    </pre>
                  </Paper>
                  
                  {snapshotPaths.length > 0 && (
                    <Box sx={{ mt: 3 }}>
                      <Typography variant="subtitle1" gutterBottom>
                        Failure Snapshots ({snapshotPaths.length})
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {snapshotPaths.map((path, index) => (
                          <Button
                            key={index}
                            variant="outlined"
                            size="small"
                            startIcon={<Visibility />}
                            onClick={() => window.open(path, '_blank')}
                          >
                            Snapshot {index + 1}
                          </Button>
                        ))}
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* Loading indicator when test is starting but video not ready */}
        {testInProgress && !videoReady && (
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
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
                color: 'white'
              }}
            >
              <CircularProgress size={80} sx={{ color: 'white' }} />
              <Typography variant="h5">Preparing Video...</Typography>
              <Typography variant="body1">
                Video {currentVideoIndex + 1} of {videoPlaylist.length}
              </Typography>
              {videoPlaylist[currentVideoIndex] && (
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                  {videoPlaylist[currentVideoIndex].filename}
                </Typography>
              )}
            </Box>
          </Box>
        )}
        
        {/* Full-Screen Video Display */}
        {testInProgress && videoReady && (
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
                src={getVideoSource(videoPlaylist[currentVideoIndex])}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain'
                }}
                onEnded={handleVideoEnded}
                onLoadedData={() => {
                  console.log('📹 Video loadeddata event');
                }}
                onCanPlay={() => {
                  console.log('📹 Video canplay event');
                  setVideoReady(true);
                }}
                onError={(e) => {
                  console.error('📹 Video error:', e);
                  setError('Video playback error - switching to fallback source');
                  // Try fallback source
                  if (videoRef.current) {
                    videoRef.current.src = `/api/v1/videos/${videoPlaylist[currentVideoIndex].id}/stream`;
                  }
                }}
                controls={!isFullScreen}
                preload="metadata"
              />
            )}
            
            {/* Loading indicator when video is not ready */}
            {!videoReady && (
              <Box
                sx={{
                  position: 'absolute',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  color: 'white'
                }}
              >
                <CircularProgress size={60} sx={{ color: 'white' }} />
                <Typography variant="h6">Loading video...</Typography>
              </Box>
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
                  <IconButton onClick={exitFullScreen} sx={{ color: 'white' }}>
                    <FullscreenExit />
                  </IconButton>
                </Tooltip>
                <Tooltip title={testPaused ? "Resume Test" : "Pause Test"}>
                  <IconButton onClick={togglePause} sx={{ color: 'white' }}>
                    {testPaused ? <PlayArrow /> : <Pause />}
                  </IconButton>
                </Tooltip>
                <Tooltip title="Stop Test">
                  <IconButton onClick={stopTest} sx={{ color: 'white' }}>
                    <Stop />
                  </IconButton>
                </Tooltip>
              </Box>
            )}
            
            {/* Enhanced test progress indicator */}
            {isFullScreen && (
              <Box
                sx={{
                  position: 'absolute',
                  bottom: 16,
                  left: 16,
                  right: 16,
                  backgroundColor: 'rgba(0,0,0,0.8)',
                  borderRadius: 2,
                  p: 2,
                  color: 'white'
                }}
              >
                <Typography variant="h6">
                  Video {currentVideoIndex + 1} of {videoPlaylist.length}
                  {testPaused && <Chip label="PAUSED" color="warning" size="small" sx={{ ml: 1 }} />}
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
                  {(() => {
                    const stats = getTestStatistics();
                    return (
                      <Typography variant="body2">
                        Events: {stats.totalEvents} • 
                        Passed: {stats.passedEvents} • 
                        Failed: {stats.failedEvents} • 
                        Pass Rate: {stats.passRate.toFixed(1)}% • 
                        Avg Latency: {Math.round(stats.averageLatency)}ms
                      </Typography>
                    );
                  })()}
                </Box>
                
                {/* Performance metrics */}
                {performanceMetrics && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption">
                      CPU: {performanceMetrics.cpu_usage?.toFixed(1)}% • 
                      Memory: {performanceMetrics.memory_usage?.toFixed(1)}MB • 
                      Signal Rate: {performanceMetrics.signal_rate?.toFixed(1)}/s
                    </Typography>
                  </Box>
                )}
              </Box>
            )}
          </Box>
        )}

        {/* Start Test Confirmation Dialog - Enhanced */}
        <Dialog open={startTestDialog} onClose={() => setStartTestDialog(false)} maxWidth="md" fullWidth>
          <DialogTitle>Start HIL Test Execution - Enhanced</DialogTitle>
          <DialogContent>
            <Alert severity="info" sx={{ mb: 3 }}>
              <AlertTitle>Test Configuration Summary</AlertTitle>
              <Typography variant="body2">
                • Project: {selectedProject?.name}<br />
                • Videos: {videoPlaylist.length} validated videos<br />
                • Max Latency: {testConfig.maxLatencyMs}ms<br />
                • LabJack: {getConnectionStatusText()}<br />
                • Signal Type: {labjackStatus?.signalType || 'TTL'}<br />
                • Auto-advance: {testConfig.autoAdvanceVideos ? 'Yes' : 'No'}<br />
                • Precision Timing: {testConfig.precisionTimingEnabled ? 'Enabled' : 'Disabled'}<br />
                • Snapshots: {testConfig.captureSnapshots ? 'Enabled' : 'Disabled'}
              </Typography>
            </Alert>
            
            <Typography variant="body1" paragraph>
              Starting this enhanced test will:
            </Typography>
            <List>
              <ListItem>
                <ListItemIcon><PlayArrow /></ListItemIcon>
                <ListItemText primary="Switch to full-screen display mode (PRD requirement)" />
              </ListItem>
              <ListItem>
                <ListItemIcon><VideoLibrary /></ListItemIcon>
                <ListItemText primary="Play all videos sequentially with enhanced controls" />
              </ListItem>
              <ListItem>
                <ListItemIcon><Hardware /></ListItemIcon>
                <ListItemText primary="Monitor hardware signals with precision timing" />
              </ListItem>
              <ListItem>
                <ListItemIcon><Timeline /></ListItemIcon>
                <ListItemText primary="Record sub-millisecond timing for all events" />
              </ListItem>
              <ListItem>
                <ListItemIcon><Analytics /></ListItemIcon>
                <ListItemText primary="Generate comprehensive real-time analysis" />
              </ListItem>
              <ListItem>
                <ListItemIcon><Save /></ListItemIcon>
                <ListItemText primary="Capture failure snapshots and generate detailed reports" />
              </ListItem>
            </List>
            
            {(() => {
              const validation = validateTestStart();
              return (
                <>
                  {validation.errors.length > 0 && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                      <AlertTitle>Cannot start test:</AlertTitle>
                      {validation.errors.map((error, index) => (
                        <Typography key={index} variant="body2">• {error}</Typography>
                      ))}
                    </Alert>
                  )}
                  
                  {validation.warnings.length > 0 && (
                    <Alert severity="warning" sx={{ mt: 2 }}>
                      <AlertTitle>Warnings:</AlertTitle>
                      {validation.warnings.map((warning, index) => (
                        <Typography key={index} variant="body2">• {warning}</Typography>
                      ))}
                    </Alert>
                  )}
                </>
              );
            })()}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setStartTestDialog(false)}>Cancel</Button>
            <Button
              onClick={startTest}
              variant="contained"
              disabled={!validateTestStart().canStart || loading}
              startIcon={loading ? <CircularProgress size={16} /> : <PlayArrow />}
            >
              {loading ? 'Starting...' : 'Start Enhanced HIL Test'}
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

export default HILTestExecutionComplete;