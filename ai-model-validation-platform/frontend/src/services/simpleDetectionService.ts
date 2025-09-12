/**
 * Simple Detection Service
 * 
 * Service for testing the new simple-detection endpoints
 * Provides clean REST API calls for background LabJack detection
 */

import { apiService } from './api';

// Types for Simple Detection API
export interface StartDetectionRequest {
  session_id: string;
  tolerance_ms?: number;
  project_id?: string;
  video_id?: string;
}

export interface StartDetectionResponse {
  success: boolean;
  session_id: string;
  tolerance_ms: number;
  start_time: number;
  message: string;
  database_session_id?: string;
}

export interface StopDetectionResponse {
  success: boolean;
  session_id?: string;
  start_time?: number;
  end_time?: number;
  duration_seconds?: number;
  total_detections: number;
  detection_events: DetectionEvent[];
  message: string;
  database_session_id?: string;
}

export interface DetectionStatusResponse {
  running: boolean;
  session_id?: string;
  start_time?: number;
  current_time?: number;
  duration_seconds?: number;
  events_collected?: number;
  tolerance_ms?: number;
  message: string;
}

export interface DetectionEvent {
  detection_id: string;
  timestamp: number;
  pin_state: number;
  metadata?: any;
}

export interface VideoEvent {
  timestamp: number;
  event_type: string;
  class_label?: string;
  confidence?: number;
  bbox_x?: number;
  bbox_y?: number;
  bbox_width?: number;
  bbox_height?: number;
  metadata?: any;
}

export interface AnalyzeDetectionRequest {
  video_events: VideoEvent[];
  save_to_database?: boolean;
}

export interface AnalyzeDetectionResponse {
  success: boolean;
  matched_detections: number;
  total_detections: number;
  accuracy_percentage: number;
  video_correlations: any[];
  message: string;
}

export interface SimpleDetectionStatus {
  running: boolean;
  session_id?: string;
  start_time?: number;
  current_time?: number;
  duration_seconds?: number;
  detections_count?: number;
  tolerance_ms?: number;
  message: string;
  connection_status?: string;
  hardware_status?: string;
  error_message?: string;
  windows_compatibility?: {
    driver_detected: boolean;
    recommendations: string[];
  };
}

export interface DetectionResult {
  success: boolean;
  session_id?: string;
  start_time?: number;
  end_time?: number;
  duration_seconds?: number;
  total_detections: number;
  detection_events: DetectionEvent[];
  message: string;
  database_session_id?: string;
  data?: any;
}

export interface DetectionSession {
  id: string;
  session_id: string;
  project_id?: string;
  video_id?: string;
  start_time?: number;
  end_time?: number;
  duration_seconds?: number;
  tolerance_ms: number;
  status: string;
  total_detections?: number;
  matched_detections?: number;
  accuracy_percentage?: number;
  created_at?: string;
}

export interface DetectionSessionsResponse {
  total: number;
  limit: number;
  offset: number;
  sessions: DetectionSession[];
}

/**
 * Simple Detection Service Class
 */
export class SimpleDetectionService {
  private baseUrl = '/api/simple-detection';

  /**
   * Start a background detection session
   */
  async startDetection(sessionIdOrRequest: string | StartDetectionRequest, toleranceMs?: number): Promise<StartDetectionResponse> {
    try {
      let request: StartDetectionRequest;
      
      if (typeof sessionIdOrRequest === 'string') {
        // Legacy signature: (sessionId, toleranceMs)
        request = {
          session_id: sessionIdOrRequest,
          tolerance_ms: toleranceMs || 100
        };
      } else {
        // New signature: (request)
        request = sessionIdOrRequest;
      }
      
      const response = await apiService.post(`${this.baseUrl}/start`, request);
      console.log('Detection started:', response);
      return response as StartDetectionResponse;
    } catch (error) {
      console.error('Error starting detection:', error);
      throw this.handleError(error, 'Failed to start detection session');
    }
  }

  /**
   * Stop the current detection session
   */
  async stopDetection(): Promise<DetectionResult> {
    try {
      const response = await apiService.post(`${this.baseUrl}/stop`);
      console.log('Detection stopped:', response);
      const apiResponse = response as any;
      return {
        success: true,
        session_id: apiResponse.session_id,
        start_time: apiResponse.start_time,
        end_time: apiResponse.end_time,
        duration_seconds: apiResponse.duration_seconds,
        total_detections: apiResponse.total_detections || 0,
        detection_events: apiResponse.detection_events || [],
        message: apiResponse.message || 'Detection stopped successfully',
        database_session_id: apiResponse.database_session_id,
        data: response
      };
    } catch (error) {
      console.error('Error stopping detection:', error);
      throw this.handleError(error, 'Failed to stop detection session');
    }
  }

  /**
   * Get current detection status
   */
  async getDetectionStatus(): Promise<DetectionStatusResponse> {
    try {
      const response = await apiService.get(`${this.baseUrl}/status`);
      return response as DetectionStatusResponse;
    } catch (error) {
      console.error('Error getting detection status:', error);
      throw this.handleError(error, 'Failed to get detection status');
    }
  }

  /**
   * Get current detection status (alias for compatibility)
   */
  async getStatus(): Promise<SimpleDetectionStatus> {
    try {
      const response = await this.getDetectionStatus();
      return {
        running: response.running,
        session_id: response.session_id,
        start_time: response.start_time,
        current_time: response.current_time,
        duration_seconds: response.duration_seconds,
        detections_count: response.events_collected,
        tolerance_ms: response.tolerance_ms,
        message: response.message,
        connection_status: 'connected',
        hardware_status: 'ok',
        windows_compatibility: {
          driver_detected: true,
          recommendations: []
        }
      };
    } catch (error) {
      return {
        running: false,
        message: 'Service unavailable',
        connection_status: 'error',
        hardware_status: 'error',
        error_message: error instanceof Error ? error.message : 'Unknown error',
        windows_compatibility: {
          driver_detected: false,
          recommendations: ['Check LabJack drivers', 'Verify hardware connection']
        }
      };
    }
  }

  /**
   * Analyze completed detection session
   */
  async analyzeDetection(
    sessionId: string, 
    request: AnalyzeDetectionRequest
  ): Promise<AnalyzeDetectionResponse> {
    try {
      const response = await apiService.post(`${this.baseUrl}/analyze/${sessionId}`, request);
      console.log('Detection analysis completed:', response);
      return response as AnalyzeDetectionResponse;
    } catch (error) {
      console.error('Error analyzing detection:', error);
      throw this.handleError(error, 'Failed to analyze detection session');
    }
  }

  /**
   * List detection sessions
   */
  async listDetectionSessions(options?: {
    project_id?: string;
    video_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<DetectionSessionsResponse> {
    try {
      const params = new URLSearchParams();
      if (options?.project_id) params.append('project_id', options.project_id);
      if (options?.video_id) params.append('video_id', options.video_id);
      if (options?.status) params.append('status', options.status);
      if (options?.limit) params.append('limit', options.limit.toString());
      if (options?.offset) params.append('offset', options.offset.toString());

      const url = `${this.baseUrl}/sessions${params.toString() ? '?' + params.toString() : ''}`;
      const response = await apiService.get(url);
      return response as DetectionSessionsResponse;
    } catch (error) {
      console.error('Error listing detection sessions:', error);
      throw this.handleError(error, 'Failed to list detection sessions');
    }
  }

  /**
   * Get detailed information about a specific detection session
   */
  async getDetectionSessionDetails(sessionId: string): Promise<any> {
    try {
      const response = await apiService.get(`${this.baseUrl}/sessions/${sessionId}`);
      return response;
    } catch (error) {
      console.error('Error getting session details:', error);
      throw this.handleError(error, 'Failed to get session details');
    }
  }

  /**
   * Generate a unique session ID
   */
  generateSessionId(prefix: string = 'session'): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    return `${prefix}_${timestamp}_${random}`;
  }

  /**
   * Check if the simple detection service is available
   */
  async checkServiceAvailability(): Promise<{ available: boolean; message: string }> {
    try {
      await this.getDetectionStatus();
      return { available: true, message: 'Simple detection service is available' };
    } catch (error) {
      return { 
        available: false, 
        message: 'Simple detection service is not available. Please check if the backend is running.' 
      };
    }
  }

  /**
   * Create sample video events for testing
   */
  createSampleVideoEvents(): VideoEvent[] {
    return [
      {
        timestamp: 1.5,
        event_type: 'pedestrian_detection',
        class_label: 'pedestrian',
        confidence: 0.95,
        bbox_x: 100,
        bbox_y: 50,
        bbox_width: 80,
        bbox_height: 120,
        metadata: { source: 'test_data' }
      },
      {
        timestamp: 3.2,
        event_type: 'cyclist_detection',
        class_label: 'cyclist',
        confidence: 0.87,
        bbox_x: 200,
        bbox_y: 80,
        bbox_width: 60,
        bbox_height: 90,
        metadata: { source: 'test_data' }
      },
      {
        timestamp: 5.8,
        event_type: 'vehicle_detection',
        class_label: 'car',
        confidence: 0.92,
        bbox_x: 300,
        bbox_y: 120,
        bbox_width: 150,
        bbox_height: 100,
        metadata: { source: 'test_data' }
      }
    ];
  }

  /**
   * Error handler for service methods
   */
  private handleError(error: any, defaultMessage: string): Error {
    if (error?.response?.data?.detail) {
      return new Error(error.response.data.detail);
    }
    if (error?.message) {
      return new Error(error.message);
    }
    return new Error(defaultMessage);
  }
}

// Create singleton instance
export const simpleDetectionService = new SimpleDetectionService();

// Export default
export default simpleDetectionService;