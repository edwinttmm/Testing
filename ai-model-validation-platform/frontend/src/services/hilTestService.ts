import { apiService } from './api';
import {
  Project,
  VideoFile,
  DetectionOutcome,
  SignalType,
} from './types';

// HIL Test Service for managing Hardware-in-the-Loop test execution
// Implements PRD Module 3 requirements with precision timing and real hardware integration

export interface HILTestSession {
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
  createdAt: string;
  updatedAt: string;
}

export interface HILDetectionEvent {
  id: number;
  testSessionId: number;
  videoId: number;
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

export interface HILTestSessionCreate {
  projectId: number;
  maxLatencyMs: number;
  labjackConnected: boolean;
  signalType?: SignalType;
  voltageThreshold?: number;
}

export interface HILTestSessionStats {
  totalSessions: number;
  completedSessions: number;
  averageLatency: number;
  passRate: number;
  totalEvents: number;
  recentSessions: HILTestSession[];
}

export interface LabJackConnectionInfo {
  connected: boolean;
  status: 'connected' | 'disconnected' | 'connecting' | 'error';
  mode: 'auto' | 'bridge' | 'direct' | 'mock';
  deviceInfo?: {
    deviceType: string;
    serialNumber?: string;
    firmwareVersion?: string;
  };
  signalType: SignalType;
  voltageThreshold: number;
  bridgeLatency?: number;
  lastConnectionAttempt?: string;
  errorMessage?: string;
}

class HILTestService {
  private baseUrl = '/api/v1';

  // Test Session Management

  /**
   * Create a new HIL test session
   */
  async createTestSession(data: HILTestSessionCreate): Promise<HILTestSession> {
    try {
      return await apiService.post<HILTestSession>(`${this.baseUrl}/test-sessions`, data);
    } catch (error) {
      throw new Error(`Failed to create test session: ${error}`);
    }
  }

  /**
   * Get test session by ID
   */
  async getTestSession(sessionId: number): Promise<HILTestSession> {
    try {
      return await apiService.get<HILTestSession>(`${this.baseUrl}/test-sessions/${sessionId}`);
    } catch (error) {
      throw new Error(`Failed to get test session: ${error}`);
    }
  }

  /**
   * Get all test sessions for a project
   */
  async getProjectTestSessions(projectId: number): Promise<HILTestSession[]> {
    try {
      return await apiService.get<HILTestSession[]>(`${this.baseUrl}/projects/${projectId}/test-sessions`);
    } catch (error) {
      throw new Error(`Failed to get project test sessions: ${error}`);
    }
  }

  /**
   * Start test execution
   */
  async startTestSession(sessionId: number): Promise<HILTestSession> {
    try {
      return await apiService.post<HILTestSession>(`${this.baseUrl}/test-sessions/${sessionId}/start`);
    } catch (error) {
      throw new Error(`Failed to start test session: ${error}`);
    }
  }

  /**
   * Stop test execution
   */
  async stopTestSession(sessionId: number): Promise<HILTestSession> {
    try {
      return await apiService.post<HILTestSession>(`${this.baseUrl}/test-sessions/${sessionId}/stop`);
    } catch (error) {
      throw new Error(`Failed to stop test session: ${error}`);
    }
  }

  /**
   * Pause test execution
   */
  async pauseTestSession(sessionId: number): Promise<HILTestSession> {
    try {
      return await apiService.post<HILTestSession>(`${this.baseUrl}/test-sessions/${sessionId}/pause`);
    } catch (error) {
      throw new Error(`Failed to pause test session: ${error}`);
    }
  }

  /**
   * Resume test execution
   */
  async resumeTestSession(sessionId: number): Promise<HILTestSession> {
    try {
      return await apiService.post<HILTestSession>(`${this.baseUrl}/test-sessions/${sessionId}/resume`);
    } catch (error) {
      throw new Error(`Failed to resume test session: ${error}`);
    }
  }

  /**
   * Complete test session
   */
  async completeTestSession(sessionId: number): Promise<HILTestSession> {
    try {
      return await apiService.post<HILTestSession>(`${this.baseUrl}/test-sessions/${sessionId}/complete`);
    } catch (error) {
      throw new Error(`Failed to complete test session: ${error}`);
    }
  }

  // Detection Event Management

  /**
   * Get detection events for a test session
   */
  async getSessionDetectionEvents(sessionId: number): Promise<HILDetectionEvent[]> {
    try {
      return await apiService.get<HILDetectionEvent[]>(`${this.baseUrl}/test-sessions/${sessionId}/detection-events`);
    } catch (error) {
      throw new Error(`Failed to get detection events: ${error}`);
    }
  }

  /**
   * Record a new detection event (called by hardware signal detection)
   */
  async recordDetectionEvent(event: Omit<HILDetectionEvent, 'id' | 'createdAt'>): Promise<HILDetectionEvent> {
    try {
      return await apiService.post<HILDetectionEvent>(`${this.baseUrl}/detection-events`, event);
    } catch (error) {
      throw new Error(`Failed to record detection event: ${error}`);
    }
  }

  /**
   * Get detection event with snapshot
   */
  async getDetectionEventSnapshot(eventId: number): Promise<Blob> {
    try {
      return await apiService.get<Blob>(`${this.baseUrl}/detection-events/${eventId}/snapshot`);
    } catch (error) {
      throw new Error(`Failed to get detection event snapshot: ${error}`);
    }
  }

  // LabJack Hardware Integration (PRD requirement)

  /**
   * Get LabJack connection status with real API calls
   */
  async getLabJackStatus(): Promise<LabJackConnectionInfo> {
    try {
      const response = await apiService.get<any>('/api/labjack/status');
      return {
        connected: response.connected || false,
        status: response.status || 'disconnected',
        mode: response.mode || 'auto',
        deviceInfo: response.device_info ? {
          deviceType: response.device_info.device_type || 'Unknown',
          serialNumber: response.device_info.serial_number,
          firmwareVersion: response.device_info.firmware_version
        } : undefined,
        signalType: response.signal_type || SignalType.TTL,
        voltageThreshold: response.voltage_threshold || 2.5,
        bridgeLatency: response.bridge_latency,
        lastConnectionAttempt: response.last_connection_attempt,
        errorMessage: response.error_message
      };
    } catch (error) {
      // Return error status if API call fails
      return {
        connected: false,
        status: 'error',
        mode: 'auto',
        signalType: SignalType.TTL,
        voltageThreshold: 2.5,
        errorMessage: `API connection failed: ${error}`
      };
    }
  }

  /**
   * Connect to LabJack device
   */
  async connectLabJack(options: {
    mode?: 'auto' | 'bridge' | 'direct' | 'mock';
    timeout?: number;
    forceReconnect?: boolean;
  } = {}): Promise<LabJackConnectionInfo> {
    try {
      const response = await apiService.post<any>('/api/labjack/connect', {
        force_mode: options.mode || 'auto',
        timeout: options.timeout || 15000,
        force_reconnect: options.forceReconnect || false
      });
      
      return await this.getLabJackStatus(); // Get updated status
    } catch (error) {
      throw new Error(`Failed to connect LabJack: ${error}`);
    }
  }

  /**
   * Disconnect from LabJack device
   */
  async disconnectLabJack(): Promise<void> {
    try {
      await apiService.post('/api/labjack/disconnect');
    } catch (error) {
      throw new Error(`Failed to disconnect LabJack: ${error}`);
    }
  }

  /**
   * Discover available LabJack devices
   */
  async discoverLabJackDevices(): Promise<{
    devicesFound: number;
    devices: Array<{
      name: string;
      connection: string;
      serialNumber?: string;
    }>;
  }> {
    try {
      const response = await apiService.post<any>('/api/labjack/discover', {
        timeout: 10000,
        scan_network: true,
        scan_usb: true
      });
      
      return {
        devicesFound: response.devices_found || 0,
        devices: response.devices || []
      };
    } catch (error) {
      throw new Error(`Failed to discover LabJack devices: ${error}`);
    }
  }

  // Project and Video Management for HIL Testing

  /**
   * Get projects suitable for HIL testing (with validated videos)
   */
  async getHILTestableProjects(): Promise<Project[]> {
    try {
      const projects = await apiService.getProjects();
      // Filter projects that have validated videos and are ready for testing
      return projects.filter(project => 
        (project.status === 'active' || project.status === 'testing') &&
        (project.videoCount || 0) > 0
      );
    } catch (error) {
      throw new Error(`Failed to get HIL testable projects: ${error}`);
    }
  }

  /**
   * Get validated videos for a project (HIL test playlist)
   */
  async getProjectValidatedVideos(projectId: number): Promise<VideoFile[]> {
    try {
      const videos = await apiService.get<VideoFile[]>(`${this.baseUrl}/projects/${projectId}/videos`);
      // Only return validated videos (PRD requirement)
      return videos.filter(video => video.status === 'validated');
    } catch (error) {
      throw new Error(`Failed to get project validated videos: ${error}`);
    }
  }

  // Test Statistics and Reporting

  /**
   * Get HIL test statistics
   */
  async getHILTestStats(projectId?: number): Promise<HILTestSessionStats> {
    try {
      const endpoint = projectId 
        ? `${this.baseUrl}/projects/${projectId}/hil-stats`
        : `${this.baseUrl}/hil-stats`;
      
      return await apiService.get<HILTestSessionStats>(endpoint);
    } catch (error) {
      throw new Error(`Failed to get HIL test stats: ${error}`);
    }
  }

  /**
   * Generate HIL test report
   */
  async generateTestReport(sessionId: number, format: 'json' | 'pdf' | 'csv' = 'json'): Promise<any> {
    try {
      return await apiService.get<any>(`${this.baseUrl}/test-sessions/${sessionId}/report?format=${format}`);
    } catch (error) {
      throw new Error(`Failed to generate test report: ${error}`);
    }
  }

  /**
   * Export test data
   */
  async exportTestData(sessionId: number, includeSnapshots: boolean = false): Promise<Blob> {
    try {
      return await apiService.get<Blob>(
        `${this.baseUrl}/test-sessions/${sessionId}/export?include_snapshots=${includeSnapshots}`
      );
    } catch (error) {
      throw new Error(`Failed to export test data: ${error}`);
    }
  }

  // Real-time WebSocket Support

  /**
   * Subscribe to hardware signal events for a test session
   * Note: This returns the subscription configuration, actual WebSocket handling is done by useWebSocket hook
   */
  getHardwareSignalSubscription(sessionId: number) {
    return {
      event: 'subscribe_hardware_signals',
      data: {
        sessionId,
        signalTypes: [SignalType.TTL, SignalType.GPIO, SignalType.ANALOG],
        precision: 'microseconds' // PRD requirement: sub-millisecond precision
      }
    };
  }

  /**
   * Unsubscribe from hardware signal events
   */
  getHardwareSignalUnsubscription() {
    return {
      event: 'unsubscribe_hardware_signals'
    };
  }

  // Utility Methods

  /**
   * Calculate test metrics from detection events
   */
  calculateTestMetrics(events: HILDetectionEvent[], maxLatencyMs: number) {
    const passedEvents = events.filter(event => event.outcome === DetectionOutcome.PASS);
    const failedEvents = events.filter(event => event.outcome !== DetectionOutcome.PASS);
    const highLatencyEvents = events.filter(event => 
      event.outcome === DetectionOutcome.FAIL_HIGH_LATENCY
    );
    const missedDetections = events.filter(event => 
      event.outcome === DetectionOutcome.FAIL_MISSED_DETECTION
    );
    
    const latencies = events
      .filter(event => event.latencyMs !== undefined)
      .map(event => event.latencyMs!);
    
    const averageLatency = latencies.length > 0 
      ? latencies.reduce((sum, latency) => sum + latency, 0) / latencies.length
      : 0;
    
    const maxLatency = latencies.length > 0 ? Math.max(...latencies) : 0;
    const minLatency = latencies.length > 0 ? Math.min(...latencies) : 0;
    
    return {
      totalEvents: events.length,
      passedEvents: passedEvents.length,
      failedEvents: failedEvents.length,
      highLatencyEvents: highLatencyEvents.length,
      missedDetections: missedDetections.length,
      passRate: events.length > 0 ? (passedEvents.length / events.length) * 100 : 0,
      averageLatency,
      maxLatency,
      minLatency,
      latencyThreshold: maxLatencyMs,
      withinThreshold: events.filter(event => 
        event.latencyMs !== undefined && event.latencyMs <= maxLatencyMs
      ).length
    };
  }

  /**
   * Validate HIL test preconditions
   */
  async validateTestPreconditions(projectId: number): Promise<{
    canStartTest: boolean;
    errors: string[];
    warnings: string[];
  }> {
    const errors: string[] = [];
    const warnings: string[] = [];

    try {
      // Check project exists and has validated videos
      const videos = await this.getProjectValidatedVideos(projectId);
      if (videos.length === 0) {
        errors.push('No validated videos found in project');
      }

      // Check LabJack connection
      const labjackStatus = await this.getLabJackStatus();
      if (!labjackStatus.connected) {
        errors.push('LabJack device not connected (PRD requirement)');
      } else if (labjackStatus.status === 'error') {
        warnings.push(`LabJack connection issue: ${labjackStatus.errorMessage}`);
      }

      // Check if LabJack is in mock mode
      if (labjackStatus.mode === 'mock') {
        warnings.push('LabJack running in mock mode - not using real hardware');
      }

      return {
        canStartTest: errors.length === 0,
        errors,
        warnings
      };
    } catch (error) {
      return {
        canStartTest: false,
        errors: [`Validation failed: ${error}`],
        warnings
      };
    }
  }
}

// Export singleton instance
export const hilTestService = new HILTestService();
export default hilTestService;