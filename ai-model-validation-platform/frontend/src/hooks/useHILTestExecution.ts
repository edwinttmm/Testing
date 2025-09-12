import { useState, useEffect, useCallback, useRef } from 'react';
import { apiService } from '../services/api';
import { useWebSocket } from './useWebSocket';
import {
  Project,
  VideoFile,
  DetectionOutcome,
  SignalType,
} from '../services/types';

// HIL Test Execution Hook for managing test state and hardware integration
// Implements PRD Module 3 requirements with precision timing and signal detection

interface TestSessionState {
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

interface DetectionEvent {
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

interface LabJackStatus {
  connected: boolean;
  status: 'connected' | 'disconnected' | 'connecting' | 'error';
  mode: 'auto' | 'bridge' | 'direct' | 'mock';
  deviceInfo?: {
    deviceType: string;
    serialNumber?: string;
  };
  signalType: SignalType;
  voltageThreshold: number;
  bridgeLatency?: number;
}

interface HILTestExecutionState {
  // Core test state
  projects: Project[];
  selectedProject: Project | null;
  videoPlaylist: VideoFile[];
  currentTestSession: TestSessionState | null;
  detectionEvents: DetectionEvent[];
  
  // Hardware state
  labjackStatus: LabJackStatus | null;
  
  // Test execution state
  testInProgress: boolean;
  currentVideoIndex: number;
  testStartTime: Date | null; // PRD: Test_Start_Time reference
  maxLatencyMs: number;
  
  // UI state
  loading: boolean;
  error: string | null;
  isFullScreen: boolean;
}

interface HILTestExecutionActions {
  // Project management
  loadProjects: () => Promise<void>;
  selectProject: (project: Project) => Promise<void>;
  
  // Hardware management
  checkLabJackStatus: () => Promise<LabJackStatus>;
  connectLabJack: () => Promise<boolean>;
  
  // Test execution
  startTest: (maxLatency: number) => Promise<boolean>;
  stopTest: () => Promise<void>;
  pauseTest: () => Promise<void>;
  resumeTest: () => Promise<void>;
  
  // Video playback
  nextVideo: () => void;
  previousVideo: () => void;
  
  // Full-screen management
  enterFullScreen: () => Promise<boolean>;
  exitFullScreen: () => Promise<boolean>;
  
  // Event handling
  recordDetectionEvent: (event: Partial<DetectionEvent>) => void;
  
  // Utilities
  clearError: () => void;
  validateTestStart: () => { canStart: boolean; errors: string[] };
}

export const useHILTestExecution = (): HILTestExecutionState & HILTestExecutionActions => {
  // State management
  const [state, setState] = useState<HILTestExecutionState>({
    projects: [],
    selectedProject: null,
    videoPlaylist: [],
    currentTestSession: null,
    detectionEvents: [],
    labjackStatus: null,
    testInProgress: false,
    currentVideoIndex: 0,
    testStartTime: null,
    maxLatencyMs: 100, // PRD: Default 100ms
    loading: false,
    error: null,
    isFullScreen: false,
  });
  
  // Refs for cleanup and precision timing
  const testStartTimeRef = useRef<Date | null>(null);
  const statusPollingRef = useRef<NodeJS.Timeout | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const fullScreenRef = useRef<HTMLDivElement | null>(null);
  
  // WebSocket for real-time hardware signals
  const { isConnected: wsConnected, emit: wsEmit, on: wsSubscribe } = useWebSocket();
  
  // Load projects function
  const loadProjects = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      const response = await apiService.getProjects();
      // Only show projects with validated videos (PRD requirement)
      const validProjects = response.filter(project => 
        project.status === 'active' || project.status === 'testing'
      );
      
      setState(prev => ({ ...prev, projects: validProjects }));
    } catch (err: any) {
      setState(prev => ({ ...prev, error: `Failed to load projects: ${err.message}` }));
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, []);
  
  // Select project and load video playlist
  const selectProject = useCallback(async (project: Project) => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null, selectedProject: project }));
      
      const response = await apiService.get<VideoFile[]>(`/api/v1/projects/${project.id}/videos`);
      // Only include validated videos (PRD requirement)
      const validatedVideos = response.filter(video => video.status === 'validated');
      
      if (validatedVideos.length === 0) {
        throw new Error('No validated videos found in this project. Please ensure videos are properly validated before testing.');
      }
      
      setState(prev => ({
        ...prev,
        videoPlaylist: validatedVideos,
        currentVideoIndex: 0,
        detectionEvents: []
      }));
    } catch (err: any) {
      setState(prev => ({ ...prev, error: `Failed to load video playlist: ${err.message}` }));
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, []);
  
  // Check LabJack connection status with real API calls (PRD requirement)
  const checkLabJackStatus = useCallback(async (): Promise<LabJackStatus> => {
    try {
      const response = await apiService.get<any>('/api/labjack/status');
      const status: LabJackStatus = {
        connected: response.connected || false,
        status: response.status || 'disconnected',
        mode: response.mode || 'auto',
        deviceInfo: response.device_info ? {
          deviceType: response.device_info.device_type || 'Unknown',
          serialNumber: response.device_info.serial_number
        } : undefined,
        signalType: response.signal_type || SignalType.TTL,
        voltageThreshold: response.voltage_threshold || 2.5,
        bridgeLatency: response.bridge_latency
      };
      
      setState(prev => ({ ...prev, labjackStatus: status }));
      return status;
    } catch (err: any) {
      console.error('Failed to check LabJack status:', err);
      const errorStatus: LabJackStatus = {
        connected: false,
        status: 'error',
        mode: 'auto',
        signalType: SignalType.TTL,
        voltageThreshold: 2.5
      };
      setState(prev => ({ ...prev, labjackStatus: errorStatus }));
      return errorStatus;
    }
  }, []);
  
  // Connect to LabJack device
  const connectLabJack = useCallback(async (): Promise<boolean> => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));
      
      await apiService.post('/api/labjack/connect', {
        force_mode: 'auto',
        timeout: 15000
      });
      
      // Refresh status after connection attempt
      const status = await checkLabJackStatus();
      return status.connected;
    } catch (err: any) {
      setState(prev => ({ ...prev, error: `Failed to connect LabJack: ${err.message}` }));
      return false;
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [checkLabJackStatus]);
  
  // Validate test start conditions (PRD requirement)
  const validateTestStart = useCallback((): { canStart: boolean; errors: string[] } => {
    const errors: string[] = [];
    
    if (!state.selectedProject) {
      errors.push('Please select a project');
    }
    
    if (state.videoPlaylist.length === 0) {
      errors.push('No validated videos in playlist');
    }
    
    if (!state.labjackStatus?.connected) {
      errors.push('LabJack device not connected (PRD requirement)');
    }
    
    if (state.maxLatencyMs <= 0 || state.maxLatencyMs > 10000) {
      errors.push('Maximum latency must be between 1-10000ms');
    }
    
    return {
      canStart: errors.length === 0,
      errors
    };
  }, [state.selectedProject, state.videoPlaylist.length, state.labjackStatus?.connected, state.maxLatencyMs]);
  
  // Start HIL test execution
  const startTest = useCallback(async (maxLatency: number): Promise<boolean> => {
    const validation = validateTestStart();
    if (!validation.canStart) {
      setState(prev => ({ 
        ...prev, 
        error: `Cannot start test:\n${validation.errors.join('\n')}` 
      }));
      return false;
    }
    
    try {
      setState(prev => ({ ...prev, loading: true, error: null, maxLatencyMs: maxLatency }));
      
      // Create test session with PRD-aligned data
      const testSessionData = {
        projectId: state.selectedProject!.id,
        maxLatencyMs: maxLatency,
        labjackConnected: state.labjackStatus!.connected,
        status: 'running'
      };
      
      const session = await apiService.post<TestSessionState>('/api/v1/test-sessions', testSessionData);
      
      // Capture high-precision Test_Start_Time (PRD requirement)
      const startTime = new Date();
      testStartTimeRef.current = startTime;
      
      setState(prev => ({
        ...prev,
        currentTestSession: session,
        testStartTime: startTime,
        testInProgress: true,
        currentVideoIndex: 0,
        detectionEvents: []
      }));
      
      // Subscribe to hardware signals via WebSocket
      if (wsConnected) {
        wsEmit('subscribe_hardware_signals', {
          sessionId: session.id,
          signalType: state.labjackStatus!.signalType
        });
      }
      
      return true;
    } catch (err: any) {
      setState(prev => ({ ...prev, error: `Failed to start test: ${err.message}` }));
      return false;
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [state.selectedProject, state.labjackStatus, validateTestStart, wsConnected, wsEmit]);
  
  // Stop test execution
  const stopTest = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true }));
      
      if (state.currentTestSession) {
        await apiService.post(`/api/v1/test-sessions/${state.currentTestSession.id}/stop`);
      }
      
      // Unsubscribe from hardware signals
      if (wsConnected) {
        wsEmit('unsubscribe_hardware_signals');
      }
      
      setState(prev => ({
        ...prev,
        testInProgress: false,
        currentTestSession: null,
        testStartTime: null
      }));
      
      testStartTimeRef.current = null;
    } catch (err: any) {
      setState(prev => ({ ...prev, error: `Failed to stop test: ${err.message}` }));
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [state.currentTestSession, wsConnected, wsEmit]);
  
  // Pause test execution
  const pauseTest = useCallback(async () => {
    if (!state.currentTestSession) return;
    
    try {
      await apiService.post(`/api/v1/test-sessions/${state.currentTestSession.id}/pause`);
      setState(prev => ({
        ...prev,
        currentTestSession: prev.currentTestSession ? {
          ...prev.currentTestSession,
          status: 'paused'
        } : null
      }));
    } catch (err: any) {
      setState(prev => ({ ...prev, error: `Failed to pause test: ${err.message}` }));
    }
  }, [state.currentTestSession]);
  
  // Resume test execution
  const resumeTest = useCallback(async () => {
    if (!state.currentTestSession) return;
    
    try {
      await apiService.post(`/api/v1/test-sessions/${state.currentTestSession.id}/resume`);
      setState(prev => ({
        ...prev,
        currentTestSession: prev.currentTestSession ? {
          ...prev.currentTestSession,
          status: 'running'
        } : null
      }));
    } catch (err: any) {
      setState(prev => ({ ...prev, error: `Failed to resume test: ${err.message}` }));
    }
  }, [state.currentTestSession]);
  
  // Navigate to next video
  const nextVideo = useCallback(() => {
    setState(prev => ({
      ...prev,
      currentVideoIndex: Math.min(prev.currentVideoIndex + 1, prev.videoPlaylist.length - 1)
    }));
  }, []);
  
  // Navigate to previous video
  const previousVideo = useCallback(() => {
    setState(prev => ({
      ...prev,
      currentVideoIndex: Math.max(prev.currentVideoIndex - 1, 0)
    }));
  }, []);
  
  // Enter full-screen mode (PRD requirement)
  const enterFullScreen = useCallback(async (): Promise<boolean> => {
    if (!fullScreenRef.current) return false;
    
    try {
      if (fullScreenRef.current.requestFullscreen) {
        await fullScreenRef.current.requestFullscreen();
      } else if ((fullScreenRef.current as any).webkitRequestFullscreen) {
        await (fullScreenRef.current as any).webkitRequestFullscreen();
      } else if ((fullScreenRef.current as any).msRequestFullscreen) {
        await (fullScreenRef.current as any).msRequestFullscreen();
      }
      
      setState(prev => ({ ...prev, isFullScreen: true }));
      return true;
    } catch (err) {
      console.error('Failed to enter full-screen mode:', err);
      return false;
    }
  }, []);
  
  // Exit full-screen mode
  const exitFullScreen = useCallback(async (): Promise<boolean> => {
    try {
      if (document.exitFullscreen) {
        await document.exitFullscreen();
      } else if ((document as any).webkitExitFullscreen) {
        await (document as any).webkitExitFullscreen();
      } else if ((document as any).msExitFullscreen) {
        await (document as any).msExitFullscreen();
      }
      
      setState(prev => ({ ...prev, isFullScreen: false }));
      return true;
    } catch (err) {
      console.error('Failed to exit full-screen mode:', err);
      return false;
    }
  }, []);
  
  // Record detection event with precision timing
  const recordDetectionEvent = useCallback((eventData: Partial<DetectionEvent>) => {
    if (!state.testInProgress || !testStartTimeRef.current || !state.currentTestSession) return;
    
    // Calculate Expected_Event_Time and Signal_Received_Time (PRD requirement)
    const signalReceivedTime = new Date();
    const expectedEventTime = new Date(testStartTimeRef.current.getTime() + (eventData.expectedEventTime ? new Date(eventData.expectedEventTime).getTime() : 0));
    const latencyMs = signalReceivedTime.getTime() - expectedEventTime.getTime();
    
    // Determine outcome based on latency threshold
    let outcome: DetectionOutcome;
    if (latencyMs <= state.maxLatencyMs) {
      outcome = DetectionOutcome.PASS;
    } else {
      outcome = DetectionOutcome.FAIL_HIGH_LATENCY;
    }
    
    const event: DetectionEvent = {
      id: String(eventData.id || Date.now()),
      testSessionId: String(state.currentTestSession.id),
      videoId: state.videoPlaylist[state.currentVideoIndex]?.id || '0',
      groundTruthObjectId: eventData.groundTruthObjectId || 0,
      expectedEventTime: expectedEventTime.toISOString(),
      signalReceivedTime: signalReceivedTime.toISOString(),
      latencyMs,
      outcome,
      signalType: eventData.signalType || state.labjackStatus?.signalType || SignalType.TTL,
      signalValue: eventData.signalValue,
      snapshotPath: eventData.snapshotPath,
      createdAt: new Date().toISOString()
    };
    
    setState(prev => ({
      ...prev,
      detectionEvents: [...prev.detectionEvents, event]
    }));
  }, [state.testInProgress, state.currentTestSession, state.videoPlaylist, state.currentVideoIndex, state.maxLatencyMs, state.labjackStatus?.signalType]);
  
  // Clear error state
  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);
  
  // Set up LabJack status polling
  useEffect(() => {
    checkLabJackStatus();
    
    // Poll LabJack status every 5 seconds
    statusPollingRef.current = setInterval(checkLabJackStatus, 5000);
    
    return () => {
      if (statusPollingRef.current) {
        clearInterval(statusPollingRef.current);
      }
    };
  }, [checkLabJackStatus]);
  
  // WebSocket event handlers for hardware signals (PRD requirement)
  useEffect(() => {
    if (!wsConnected || !state.testInProgress) return;
    
    const handleHardwareSignal = (data: any) => {
      recordDetectionEvent({
        id: data.id,
        groundTruthObjectId: data.groundTruthObjectId,
        expectedEventTime: data.expectedTimestamp,
        signalType: data.signalType,
        signalValue: data.signalValue
      });
    };
    
    wsSubscribe('hardware_signal_detected', handleHardwareSignal);
    
    // Cleanup handled by useWebSocket hook
  }, [wsConnected, state.testInProgress, recordDetectionEvent, wsSubscribe]);
  
  // Full-screen event listeners
  useEffect(() => {
    const handleFullScreenChange = () => {
      const isFullScreen = !!(
        document.fullscreenElement ||
        (document as any).webkitFullscreenElement ||
        (document as any).msFullscreenElement
      );
      setState(prev => ({ ...prev, isFullScreen }));
    };
    
    document.addEventListener('fullscreenchange', handleFullScreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullScreenChange);
    document.addEventListener('msfullscreenchange', handleFullScreenChange);
    
    return () => {
      document.removeEventListener('fullscreenchange', handleFullScreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullScreenChange);
      document.removeEventListener('msfullscreenchange', handleFullScreenChange);
    };
  }, []);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (statusPollingRef.current) {
        clearInterval(statusPollingRef.current);
      }
      if (state.testInProgress && wsConnected) {
        wsEmit('unsubscribe_hardware_signals');
      }
    };
  }, [state.testInProgress, wsConnected, wsEmit]);
  
  return {
    // State
    ...state,
    
    // Actions
    loadProjects,
    selectProject,
    checkLabJackStatus,
    connectLabJack,
    startTest,
    stopTest,
    pauseTest,
    resumeTest,
    nextVideo,
    previousVideo,
    enterFullScreen,
    exitFullScreen,
    recordDetectionEvent,
    clearError,
    validateTestStart,
  };
};

export default useHILTestExecution;