import { GroundTruthAnnotation } from './types';
import { apiService } from './api';
import { isDebugEnabled } from '../utils/envConfig';

export interface DetectionConfig {
  confidenceThreshold: number;
  nmsThreshold: number;
  modelName: string;
  targetClasses: string[];
  maxRetries?: number;
  retryDelay?: number;
  useFallback?: boolean;
}

export interface DetectionResult {
  success: boolean;
  detections: GroundTruthAnnotation[];
  error?: string;
  source: 'backend' | 'fallback';
  processingTime: number;
}

class DetectionService {
  private retryCount: Map<string, number> = new Map();
  private isProcessing: Map<string, boolean> = new Map();
  // WebSocket functionality completely removed - HTTP-only service
  
  async runDetection(
    videoId: string, 
    config: DetectionConfig
  ): Promise<DetectionResult> {
    const startTime = Date.now();
    
    if (isDebugEnabled()) {
      console.log('🎯 Detection Service: Starting detection for video:', videoId, 'with config:', config);
    }
    
    // Check if already processing
    if (this.isProcessing.get(videoId)) {
      return {
        success: false,
        detections: [],
        error: 'Detection already in progress for this video',
        source: 'backend',
        processingTime: 0
      };
    }
    
    this.isProcessing.set(videoId, true);
    
    try {
      // Try backend detection with extended timeout for heavy processing
      const backendPromise = this.runBackendDetection(videoId, config);
      const timeoutPromise = new Promise<DetectionResult>((_, reject) => 
        setTimeout(() => reject(new Error('Detection timeout - video processing taking too long')), 30000)
      );
      
      try {
        const result = await Promise.race([backendPromise, timeoutPromise]);
        if (result.success) {
          if (isDebugEnabled()) {
            console.log('✅ Detection completed successfully:', result.detections.length, 'detections found');
          }
          return {
            ...result,
            processingTime: Date.now() - startTime
          };
        }
        throw new Error(result.error || 'Detection failed');
      } catch (backendError: any) {
        console.warn('Backend detection failed:', backendError.message);
        
        // Try fallback detection if enabled and retries remain
        if (config.useFallback && this.retryCount.get(videoId) === undefined) {
          this.retryCount.set(videoId, 1);
          if (isDebugEnabled()) {
            console.log('🔄 Attempting fallback detection...');
          }
          return await this.runFallbackDetection(videoId, config);
        }
        
        throw backendError;
      }
      
    } catch (error: any) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      if (isDebugEnabled()) {
        console.error('❌ Detection failed:', errorMessage);
      }
      
      // Return user-friendly error message
      let userFriendlyError = 'Detection service is currently unavailable.';
      if (errorMessage.includes('timeout')) {
        userFriendlyError = 'Detection is taking longer than expected. Please try with a shorter video.';
      } else if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
        userFriendlyError = 'Network connection issue. Please check your internet connection.';
      } else if (errorMessage.includes('400')) {
        userFriendlyError = 'Invalid video format or corrupted file. Please try another video.';
      } else if (errorMessage.includes('500')) {
        userFriendlyError = 'Server error occurred during detection. Please try again later.';
      }
      
      return {
        success: false,
        detections: [],
        error: userFriendlyError,
        source: 'backend',
        processingTime: Date.now() - startTime
      };
      
    } finally {
      this.isProcessing.delete(videoId);
      this.retryCount.delete(videoId);
    }
  }
  
  private async runBackendDetection(
    videoId: string,
    config: DetectionConfig
  ): Promise<DetectionResult> {
    try {
      if (isDebugEnabled()) {
        console.log('🔍 Running backend detection pipeline...', { videoId, config });
      }
      
      const response = await apiService.runDetectionPipeline(videoId, {
        confidenceThreshold: config.confidenceThreshold,
        nmsThreshold: config.nmsThreshold,
        modelName: config.modelName,
        targetClasses: config.targetClasses
      });
      
      if (isDebugEnabled()) {
        console.log('📡 Backend detection response:', response);
      }
      
      if (!response) {
        throw new Error('No response received from detection pipeline');
      }
      
      // Handle different response formats
      const detections = response.detections || [];
      
      if (!Array.isArray(detections)) {
        console.warn('⚠️ Detection response is not an array:', detections);
        throw new Error('Invalid detection response format');
      }
      
      // Convert backend detections to annotations
      const annotations = this.convertDetectionsToAnnotations(videoId, detections);
      
      if (isDebugEnabled()) {
        console.log('🎯 Converted detections to annotations:', annotations.length, 'annotations');
      }
      
      return {
        success: true,
        detections: annotations,
        source: 'backend',
        processingTime: response.processingTime || 0
      };
      
    } catch (error: any) {
      console.error('Backend detection error:', error);
      
      // Provide more specific error messages
      if (error.status === 404) {
        throw new Error('Video not found on server. Please re-upload the video.');
      } else if (error.status === 422) {
        throw new Error('Invalid video format or detection parameters.');
      } else if (error.status >= 500) {
        throw new Error('Server error during detection. Please try again.');
      } else if (error.message?.includes('Network Error')) {
        throw new Error('Network connection failed. Please check your connection.');
      }
      
      throw error;
    }
  }
  
  private async runFallbackDetection(
    videoId: string,
    config: DetectionConfig
  ): Promise<DetectionResult> {
    const startTime = Date.now();
    
    if (isDebugEnabled()) {
      console.log('🚧 Running fallback detection (mock data)...');
    }
    
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Generate mock detections for demonstration
    const mockDetections: GroundTruthAnnotation[] = [
      {
        id: `mock-${Date.now()}-1`,
        videoId,
        detectionId: `DET_PED_0001`,
        frameNumber: 30,
        timestamp: 1.0,
        vruType: 'pedestrian',
        boundingBox: {
          x: 320,
          y: 240,
          width: 80,
          height: 160,
          label: 'pedestrian',
          confidence: 0.85
        },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      },
      {
        id: `mock-${Date.now()}-2`,
        videoId,
        detectionId: `DET_CYC_0001`,
        frameNumber: 45,
        timestamp: 1.5,
        vruType: 'cyclist',
        boundingBox: {
          x: 200,
          y: 180,
          width: 120,
          height: 180,
          label: 'cyclist',
          confidence: 0.92
        },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    ];
    
    if (isDebugEnabled()) {
      console.log('✅ Fallback detection completed with mock data:', mockDetections.length, 'detections');
    }
    
    return {
      success: true,
      detections: mockDetections,
      source: 'fallback',
      processingTime: Date.now() - startTime
    };
  }
  
  
  
  
  
  private convertDetectionsToAnnotations(
    videoId: string,
    detections: any[]
  ): GroundTruthAnnotation[] {
    // Convert backend detections to annotations format
    return detections.map(det => ({
      id: det.id || `det-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      videoId,
      detectionId: det.detectionId || '',
      frameNumber: det.frame || 0,
      timestamp: det.timestamp || 0,
      vruType: det.vruType || 'pedestrian',
      boundingBox: {
        x: det.x || det.bbox?.x || 0,
        y: det.y || det.bbox?.y || 0,
        width: det.width || det.bbox?.width || 100,
        height: det.height || det.bbox?.height || 100,
        label: det.label || 'pedestrian',
        confidence: det.confidence || 0.5
      },
      occluded: det.occluded || false,
      truncated: det.truncated || false,
      difficult: det.difficult || false,
      validated: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }));
  }
  
  // WebSocket functionality completely removed - HTTP-only detection service
  connectWebSocket(videoId: string, onUpdate: (data: any) => void): void {
    console.log('ℹ️ WebSocket functionality disabled - using HTTP-only detection workflow');
    // No WebSocket connections will be established
  }
  
  disconnectWebSocket(): void {
    console.log('ℹ️ HTTP-only mode - no WebSocket connections to disconnect');
    // No WebSocket cleanup needed
  }
}

export const detectionService = new DetectionService();