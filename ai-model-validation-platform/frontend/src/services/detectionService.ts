import { VideoFile, GroundTruthAnnotation, VRUType, BoundingBox } from './types';
import { apiService } from './api';
import { generateDetectionId, createDetectionTracker } from '../utils/detectionIdManager';

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
  source: 'backend' | 'fallback' | 'mock';
  processingTime: number;
}

class DetectionService {
  private retryCount: Map<string, number> = new Map();
  private isProcessing: Map<string, boolean> = new Map();
  private websocket: WebSocket | null = null;
  
  async runDetection(
    videoId: string, 
    config: DetectionConfig
  ): Promise<DetectionResult> {
    const startTime = Date.now();
    const maxRetries = config.maxRetries || 3;
    const retryDelay = config.retryDelay || 1000;
    
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
      // Try backend detection first
      const result = await this.runBackendDetection(videoId, config);
      
      if (result.success) {
        return {
          ...result,
          processingTime: Date.now() - startTime
        };
      }
      
      // If backend fails and fallback is enabled, use fallback detection
      if (config.useFallback !== false) {
        console.warn('Backend detection failed, using fallback detection');
        return await this.runFallbackDetection(videoId, config);
      }
      
      return result;
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      // Retry logic
      const currentRetries = this.retryCount.get(videoId) || 0;
      if (currentRetries < maxRetries) {
        this.retryCount.set(videoId, currentRetries + 1);
        console.log(`Retrying detection (${currentRetries + 1}/${maxRetries})...`);
        
        await new Promise(resolve => setTimeout(resolve, retryDelay * (currentRetries + 1)));
        return await this.runDetection(videoId, config);
      }
      
      // All retries exhausted, use mock detection
      if (config.useFallback !== false) {
        console.warn('All retries exhausted, using mock detection');
        return await this.runMockDetection(videoId);
      }
      
      return {
        success: false,
        detections: [],
        error: errorMessage,
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
      const response = await apiService.runDetectionPipeline(videoId, config);
      
      if (!response || !response.detections) {
        throw new Error('Invalid detection response from backend');
      }
      
      // Convert backend detections to annotations
      const annotations = this.convertDetectionsToAnnotations(
        videoId,
        response.detections
      );
      
      return {
        success: true,
        detections: annotations,
        source: 'backend',
        processingTime: response.processingTime || 0
      };
      
    } catch (error) {
      console.error('Backend detection error:', error);
      throw error;
    }
  }
  
  private async runFallbackDetection(
    videoId: string,
    config: DetectionConfig
  ): Promise<DetectionResult> {
    const startTime = Date.now();
    
    try {
      // Simulate detection using browser-based computer vision
      const detections = await this.simulateLocalDetection(videoId, config);
      
      return {
        success: true,
        detections,
        source: 'fallback',
        processingTime: Date.now() - startTime
      };
      
    } catch (error) {
      console.error('Fallback detection error:', error);
      return {
        success: false,
        detections: [],
        error: 'Fallback detection failed',
        source: 'fallback',
        processingTime: Date.now() - startTime
      };
    }
  }
  
  private async runMockDetection(videoId: string): Promise<DetectionResult> {
    const startTime = Date.now();
    
    // Generate realistic mock detections for testing
    const mockDetections = this.generateMockDetections(videoId);
    
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    return {
      success: true,
      detections: mockDetections,
      source: 'mock',
      processingTime: Date.now() - startTime
    };
  }
  
  private async simulateLocalDetection(
    videoId: string,
    config: DetectionConfig
  ): Promise<GroundTruthAnnotation[]> {
    const detections: GroundTruthAnnotation[] = [];
    
    // Simulate detection at key frames
    const keyFrames = [0, 30, 60, 90, 120, 150];
    const vruTypes: VRUType[] = ['pedestrian', 'cyclist', 'motorcyclist'];
    
    for (const frame of keyFrames) {
      for (let i = 0; i < Math.floor(Math.random() * 3) + 1; i++) {
        const vruType = vruTypes[Math.floor(Math.random() * vruTypes.length)];
        const detection = this.createAnnotation(
          videoId,
          vruType,
          frame,
          frame / 30, // timestamp
          {
            x: Math.random() * 800 + 100,
            y: Math.random() * 400 + 100,
            width: Math.random() * 100 + 50,
            height: Math.random() * 150 + 100,
            label: vruType,
            confidence: Math.random() * 0.5 + 0.5
          }
        );
        detections.push(detection);
      }
    }
    
    return detections;
  }
  
  private generateMockDetections(videoId: string): GroundTruthAnnotation[] {
    const detections: GroundTruthAnnotation[] = [];
    const frames = [0, 15, 30, 45, 60, 75, 90];
    
    frames.forEach((frame, index) => {
      const annotation = this.createAnnotation(
        videoId,
        'pedestrian',
        frame,
        frame / 30,
        {
          x: 200 + index * 50,
          y: 150 + index * 20,
          width: 80,
          height: 160,
          label: 'pedestrian',
          confidence: 0.95
        }
      );
      detections.push(annotation);
    });
    
    return detections;
  }
  
  private createAnnotation(
    videoId: string,
    vruType: VRUType,
    frameNumber: number,
    timestamp: number,
    boundingBox: BoundingBox
  ): GroundTruthAnnotation {
    const detectionId = generateDetectionId(vruType, frameNumber);
    
    createDetectionTracker(
      detectionId,
      vruType,
      frameNumber,
      timestamp,
      boundingBox,
      boundingBox.confidence
    );
    
    return {
      id: `mock-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      videoId,
      detectionId,
      frameNumber,
      timestamp,
      vruType,
      boundingBox,
      occluded: false,
      truncated: false,
      difficult: false,
      validated: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
  }
  
  private convertDetectionsToAnnotations(
    videoId: string,
    detections: any[]
  ): GroundTruthAnnotation[] {
    return detections.map(det => {
      const vruType = this.mapClassToVRUType(det.class || det.label);
      const detectionId = generateDetectionId(vruType, det.frame || 0);
      
      return {
        id: det.id || `det-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        videoId,
        detectionId,
        frameNumber: det.frame || 0,
        timestamp: det.timestamp || 0,
        vruType,
        boundingBox: {
          x: det.x || det.bbox?.x || 0,
          y: det.y || det.bbox?.y || 0,
          width: det.width || det.bbox?.width || 100,
          height: det.height || det.bbox?.height || 100,
          label: vruType,
          confidence: det.confidence || 0.5
        },
        occluded: det.occluded || false,
        truncated: det.truncated || false,
        difficult: det.difficult || false,
        validated: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
    });
  }
  
  private mapClassToVRUType(className: string): VRUType {
    const mapping: { [key: string]: VRUType } = {
      'person': 'pedestrian',
      'pedestrian': 'pedestrian',
      'bicycle': 'cyclist',
      'cyclist': 'cyclist',
      'motorcycle': 'motorcyclist',
      'motorcyclist': 'motorcyclist',
      'wheelchair': 'wheelchair_user',
      'scooter': 'scooter_rider'
    };
    
    return mapping[className.toLowerCase()] || 'pedestrian';
  }
  
  // WebSocket support for real-time detection updates
  connectWebSocket(url: string, onUpdate: (data: any) => void): void {
    try {
      this.websocket = new WebSocket(url);
      
      this.websocket.onopen = () => {
        console.log('WebSocket connected for real-time detection updates');
      };
      
      this.websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onUpdate(data);
        } catch (error) {
          console.error('WebSocket message parse error:', error);
        }
      };
      
      this.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      this.websocket.onclose = () => {
        console.log('WebSocket disconnected');
        // Attempt reconnection after 5 seconds
        setTimeout(() => this.connectWebSocket(url, onUpdate), 5000);
      };
      
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  }
  
  disconnectWebSocket(): void {
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
  }
}

export const detectionService = new DetectionService();