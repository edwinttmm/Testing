import { GroundTruthAnnotation, DetectionUpdate, VRUType } from './types';
import { apiService } from './api';
import { isDebugEnabled } from '../utils/envConfig';
import { isObject, isArray, isString, isNumber, safeGet, hasDetectionProperties, mapYoloClassToVRUType } from '../utils/typeGuards';
import { debugDetectionData, debugBoundingBoxConversion, debugNetworkRequest } from '../utils/enhancedModeDebugger';

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
      // Try backend detection with extended timeout for heavy processing (YOLOv8 can take 70+ seconds)
      const backendPromise = this.runBackendDetection(videoId, config);
      const timeoutPromise = new Promise<DetectionResult>((_, reject) => 
        setTimeout(() => reject(new Error('Detection timeout - video processing taking too long')), 130000) // 130 seconds to handle real YOLOv8 processing
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
      } catch (backendError: unknown) {
        const errorMessage = backendError instanceof Error ? backendError.message : String(backendError);
        console.warn('Backend detection failed:', errorMessage);
        
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
      
    } catch (error: unknown) {
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
        console.log('🔍 Running backend detection pipeline (real YOLOv8 AI - may take up to 70+ seconds)...', { videoId, config });
      }
      
      // CRITICAL DEBUG: Always log this regardless of debug mode
      console.log('🚨 DETECTION SERVICE CALLED:', { videoId, config, timestamp: new Date().toISOString() });
      
      const response = await apiService.runDetectionPipeline(videoId, {
        confidenceThreshold: config.confidenceThreshold,
        nmsThreshold: config.nmsThreshold,
        modelName: config.modelName,
        targetClasses: config.targetClasses
      });
      
      // CRITICAL DEBUG: Always log API response
      console.log('🚨 API RESPONSE RECEIVED:', { 
        response, 
        responseType: typeof response,
        responseKeys: response ? Object.keys(response) : 'null',
        detectionsRaw: response?.detections,
        detectionsType: typeof response?.detections,
        detectionsLength: response?.detections?.length,
        timestamp: new Date().toISOString() 
      });
      
      if (isDebugEnabled()) {
        console.log('📡 Backend detection response:', response);
      }
      
      if (!response) {
        throw new Error('No response received from detection pipeline');
      }
      
      // Handle different response formats  
      let detections: unknown[] = response.detections || [];
      
      if (isDebugEnabled()) {
        console.log('🔍 Raw backend detection response:', {
          responseType: typeof response,
          responseKeys: Object.keys(response),
          detectionsType: typeof detections,
          detectionsIsArray: Array.isArray(detections),
          detectionsLength: Array.isArray(detections) ? detections.length : 'N/A',
          rawResponse: response,
          firstDetection: Array.isArray(detections) && detections.length > 0 ? detections[0] : null
        });
      }
      
      // Handle nested response formats with proper type casting
      if (!Array.isArray(detections)) {
        if (isObject(detections) && 'results' in detections) {
          detections = (detections as { results: unknown[] }).results;
        } else if (isObject(detections) && 'data' in detections) {
          detections = (detections as { data: unknown[] }).data;
        } else {
          console.warn('⚠️ Detection response is not an array:', detections);
          console.warn('⚠️ Full response structure:', response);
          throw new Error(`Invalid detection response format: expected array, got ${typeof detections}`);
        }
      }
      
      if (!Array.isArray(detections)) {
        throw new Error(`Detection data is still not an array after normalization: ${typeof detections}`);
      }
      
      if (isDebugEnabled()) {
        console.log('🔍 Pre-filtering detection data:', {
          totalDetections: detections.length,
          sampleDetections: detections.slice(0, 2).map((det, index) => ({
            index,
            type: typeof det,
            keys: isObject(det) ? Object.keys(det) : 'N/A',
            hasClassValue: isObject(det) ? (det.class_name || det.className || det.label || det.class || 'MISSING') : 'N/A',
            hasConfidenceValue: isObject(det) ? det.confidence : 'N/A',
            hasBboxValue: isObject(det) ? (det.bbox || det.boundingBox || 'MISSING') : 'N/A',
            raw: det
          }))
        });
      }
      
      // Type-safe detection conversion with improved filtering
      const validDetections = detections.filter((det, index) => {
        const isValid = hasDetectionProperties(det);
        if (!isValid && isDebugEnabled()) {
          console.log(`❌ Detection ${index} failed validation:`, det);
        }
        return isValid;
      });
      
      if (isDebugEnabled()) {
        console.log('🔍 Detection filtering results:', {
          totalDetections: detections.length,
          validDetections: validDetections.length,
          filteredOut: detections.length - validDetections.length,
          filteringPercentage: detections.length > 0 ? ((validDetections.length / detections.length) * 100).toFixed(1) + '%' : '0%',
          sampleValidDetection: validDetections[0] || null,
          sampleInvalidDetection: detections.find(det => !hasDetectionProperties(det)) || null
        });
      }
      
      if (validDetections.length === 0 && detections.length > 0) {
        console.error('🚨 All detections were filtered out! Sample detection analysis:', {
          sampleDetection: detections[0],
          detectionKeys: isObject(detections[0]) ? Object.keys(detections[0]) : 'Not an object',
          hasConfidence: isObject(detections[0]) ? 'confidence' in detections[0] : false,
          hasBbox: isObject(detections[0]) ? ('bbox' in detections[0] || 'boundingBox' in detections[0]) : false,
          hasClass: isObject(detections[0]) ? ('class_name' in detections[0] || 'className' in detections[0] || 'label' in detections[0]) : false
        });
      }
      
      // Convert backend detections to annotations
      const annotations = this.convertDetectionsToAnnotations(videoId, validDetections);
      
      // Debug detection data processing
      debugDetectionData('backend', validDetections, annotations);
      
      // CRITICAL DEBUG: Always log conversion results
      console.log('🚨 DETECTION CONVERSION RESULTS:', {
        validDetections: validDetections.length,
        convertedAnnotations: annotations.length,
        sampleValidDetection: validDetections[0],
        sampleAnnotation: annotations[0],
        timestamp: new Date().toISOString()
      });
      
      if (isDebugEnabled()) {
        console.log('🎯 Converted detections to annotations:', annotations.length, 'annotations');
      }
      
      const result = {
        success: true,
        detections: annotations,
        source: 'backend' as const,
        processingTime: response.processingTime || 0
      };
      
      // CRITICAL DEBUG: Always log final result
      console.log('🚨 FINAL DETECTION RESULT:', {
        success: result.success,
        detectionsCount: result.detections.length,
        source: result.source,
        processingTime: result.processingTime,
        sampleDetection: result.detections[0],
        timestamp: new Date().toISOString()
      });
      
      return result;
      
    } catch (error: unknown) {
      console.error('Backend detection error:', error);
      
      // Provide more specific error messages using type guards
      if (isObject(error)) {
        const status = safeGet(error, 'status', undefined);
        const message = safeGet(error, 'message', '');
        
        if (isNumber(status)) {
          if (status === 404) {
            throw new Error('Video not found on server. Please re-upload the video.');
          } else if (status === 422) {
            throw new Error('Invalid video format or detection parameters.');
          } else if (status >= 500) {
            throw new Error('Server error during detection. Please try again.');
          }
        } else if (isString(message) && message.includes('Network Error')) {
          throw new Error('Network connection failed. Please check your connection.');
        }
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
      console.log('🚧 Running fallback detection (mock data) - this is NOT real AI detection...');
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
        vruType: VRUType.PEDESTRIAN,
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
        validationStatus: 'pending',
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
        vruType: VRUType.CYCLIST,
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
        validationStatus: 'pending',
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
    detections: unknown[]
  ): GroundTruthAnnotation[] {
    // Convert backend detections to annotations format with type safety
    return detections.map((det, index) => {
      if (!isObject(det)) {
        console.warn(`Invalid detection at index ${index}:`, det);
        det = {}; // Use empty object as fallback
      }
      
      // Handle backend response format with class_name and bbox array
      const className = safeGet(det, 'class_name', safeGet(det, 'class', safeGet(det, 'label', safeGet(det, 'name', 'person')))) as string;
      // Prefer standard keys: bbox (array) or bounding_box/boundingBox (object)
      const bboxSource = (safeGet(det, 'bbox', undefined) as unknown) ??
                         (safeGet(det, 'bounding_box', undefined) as unknown) ??
                         (safeGet(det, 'boundingBox', undefined) as unknown) ?? [];
      
      // Parse bbox array [x, y, width, height] or [x1, y1, x2, y2] format
      let bbox = { x: 0, y: 0, width: 100, height: 100 }; // Default fallback
      
      // CRITICAL DEBUG: Always log bbox data
      console.log('🚨 BBOX PARSING DEBUG:', {
        detectionIndex: index,
        bboxSource,
        bboxSourceType: typeof bboxSource,
        bboxSourceIsArray: Array.isArray(bboxSource),
        bboxSourceIsObject: isObject(bboxSource),
        bboxArrayLength: Array.isArray(bboxSource) ? (bboxSource as unknown[]).length : 'N/A',
        detectionObject: det,
        timestamp: new Date().toISOString()
      });
      
      if (Array.isArray(bboxSource) && bboxSource.length >= 4) {
        // Check if bbox is in [x1, y1, x2, y2] format (coordinates) or [x, y, width, height] format
        // If x2 > x1 + width assumption, likely coordinates format
        const [val1, val2, val3, val4] = bboxSource as number[];
        
        console.log('🚨 BBOX ARRAY VALUES:', { val1, val2, val3, val4 });
        
        if (val3 > val1 && val4 > val2 && (val3 - val1) > 10 && (val4 - val2) > 10) {
          // Likely [x1, y1, x2, y2] coordinate format - convert to width/height
          bbox = {
            x: Math.round(val1),
            y: Math.round(val2),
            width: Math.round(val3 - val1),
            height: Math.round(val4 - val2)
          };
          console.log('🚨 CONVERTED FROM COORDS:', bbox);
        } else {
          // Likely [x, y, width, height] format - use directly
          bbox = {
            x: Math.round(val1),
            y: Math.round(val2),
            width: Math.round(val3),
            height: Math.round(val4)
          };
          console.log('🚨 USED DIRECT VALUES:', bbox);
        }
      } else if (isObject(bboxSource)) {
        // Handle object format bbox
        bbox = {
          x: Math.round(safeGet(bboxSource, 'x', 0) as number),
          y: Math.round(safeGet(bboxSource, 'y', 0) as number),
          width: Math.round(safeGet(bboxSource, 'width', safeGet(bboxSource, 'w', 100)) as number),
          height: Math.round(safeGet(bboxSource, 'height', safeGet(bboxSource, 'h', 100)) as number)
        };
        console.log('🚨 PARSED FROM OBJECT:', bbox);
      } else {
        // Fallback to object properties directly on detection
        bbox = {
          x: Math.round(safeGet(det, 'x', 0) as number),
          y: Math.round(safeGet(det, 'y', 0) as number),
          width: Math.round(safeGet(det, 'width', safeGet(det, 'w', 100)) as number),
          height: Math.round(safeGet(det, 'height', safeGet(det, 'h', 100)) as number)
        };
        console.log('🚨 USED DETECTION FALLBACK:', bbox);
      }
      
      // Debug bounding box conversion
      debugBoundingBoxConversion(bboxSource as unknown, bbox, 'detection_to_annotation');
      
      // Ensure bbox values are valid numbers
      bbox.x = isNaN(bbox.x) ? 0 : Math.max(0, bbox.x);
      bbox.y = isNaN(bbox.y) ? 0 : Math.max(0, bbox.y);  
      bbox.width = isNaN(bbox.width) ? 100 : Math.max(1, bbox.width);
      bbox.height = isNaN(bbox.height) ? 100 : Math.max(1, bbox.height);
      
      return {
        id: safeGet(det, 'id', `det-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`) as string,
        videoId,
        detectionId: safeGet(det, 'detectionId', safeGet(det, 'id', '')) as string,
        frameNumber: safeGet(det, 'frame_number', safeGet(det, 'frame', safeGet(det, 'frameNumber', 0))) as number,
        timestamp: safeGet(det, 'timestamp', 0) as number,
        vruType: mapYoloClassToVRUType(className) as VRUType,
        boundingBox: {
          x: bbox.x,
          y: bbox.y,
          width: bbox.width,
          height: bbox.height,
          label: mapYoloClassToVRUType(className),
          confidence: safeGet(det, 'confidence', 0.5) as number
        },
        occluded: safeGet(det, 'occluded', false) as boolean,
        truncated: safeGet(det, 'truncated', false) as boolean,
        difficult: safeGet(det, 'difficult', false) as boolean,
        validationStatus: 'pending' as const,
        validated: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
    });
  }
  
  // WebSocket functionality completely removed - HTTP-only detection service
  connectWebSocket(videoId: string, onUpdate: (data: DetectionUpdate) => void): void {
    console.log('ℹ️ WebSocket functionality disabled - using HTTP-only detection workflow');
    // No WebSocket connections will be established
  }
  
  disconnectWebSocket(): void {
    console.log('ℹ️ HTTP-only mode - no WebSocket connections to disconnect');
    // No WebSocket cleanup needed
  }
}

export const detectionService = new DetectionService();
