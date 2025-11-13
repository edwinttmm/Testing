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
}

export interface DetectionResult {
  success: boolean;
  detections: GroundTruthAnnotation[];
  error?: string;
  source: 'backend';
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
      // Run backend detection and let it take as long as needed; no hard client timeout
      const result = await this.runBackendDetection(videoId, config);
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
      
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      if (isDebugEnabled()) {
        console.error('❌ Detection failed:', errorMessage);
      }
      
      // Return user-friendly error message
      let userFriendlyError = 'Detection service is currently unavailable.';
      if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
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
    const startTime = Date.now();
    let pollCount = 0;
    try {
      if (isDebugEnabled()) {
        console.log('🔍 Running ground truth generation (real YOLO AI - may take up to 70+ seconds)...', { videoId, config });
      }
      
      // CRITICAL DEBUG: Always log this regardless of debug mode
      console.log('🚨 DETECTION SERVICE CALLED:', { videoId, config, timestamp: new Date().toISOString() });
      
      // Step 1: Check if ground truth data already exists (treat 404 as no data)
      console.log('📡 Checking for existing ground truth data for video:', videoId);
      let response: any = await apiService.getGroundTruth(videoId);
      const hasObjects = Array.isArray(response?.objects) && response.objects.length > 0;

      // Step 2: If no existing data, trigger ground truth processing (YOLO detection)
      if (!hasObjects) {
        console.log('📡 No existing data found, triggering ground truth processing for video:', videoId);
        try {
          const processResponse = await apiService.cachedRequest('POST', `/api/videos/${videoId}/process-ground-truth`);
          console.log('📡 Ground truth processing started:', processResponse);

          // Poll for results up to 120s with steady backoff
          const maxWaitMs = 120_000; // 120 seconds
          const startPoll = Date.now();
          let intervalMs = 1500;
          while (Date.now() - startPoll < maxWaitMs) {
            await new Promise(resolve => setTimeout(resolve, intervalMs));
            try {
              response = await apiService.getGroundTruth(videoId);
            } catch (_) {
              // Treat transient errors as retry conditions
              response = { status: 'retry', objects: [] } as any;
            }
            const rawStatus = String((response as any)?.status || '').toLowerCase();
            const status = rawStatus.startsWith('processing') ? 'processing' : rawStatus;
            const ready = Array.isArray((response as any)?.objects) && (response as any).objects.length > 0;
            pollCount += 1;
            if (isDebugEnabled()) {
              console.log('🧪 GT Poll', {
                attempt: pollCount,
                elapsedMs: Date.now() - startPoll,
                status,
                objects: Array.isArray((response as any)?.objects) ? (response as any).objects.length : 'NA',
              });
            }
            if (ready) {
              break;
            }
            if (status === 'failed' || status === 'timeout' || status === 'error') {
              // Terminal error state
              break;
            }
            // Exponential-ish backoff capped at 5s
            intervalMs = Math.min(intervalMs + 1000, 5000);
          }
        } catch (processError) {
          console.warn('⚠️ Ground truth processing failed (YOLO may not be available):', processError);
          throw new Error('Ground truth processing is not available. YOLO dependencies may not be installed.');
        }
      }
      
      // CRITICAL DEBUG: Always log API response
      const groundTruthData = response;
      console.log('🚨 GROUND TRUTH API RESPONSE RECEIVED:', { 
        response, 
        responseType: typeof response,
        responseKeys: response ? Object.keys(response) : 'null',
        groundTruthData,
        groundTruthType: typeof groundTruthData,
        objectsRaw: groundTruthData?.objects,
        objectsType: typeof groundTruthData?.objects,
        objectsLength: groundTruthData?.objects?.length,
        timestamp: new Date().toISOString() 
      });
      
      if (isDebugEnabled()) {
        console.log('📡 Ground truth response:', groundTruthData);
      }
      
      if (!groundTruthData) {
        throw new Error('No ground truth data received from API');
      }
      
      // If still not ready and no objects, surface a clear message instead of returning success with 0
      let status = ((groundTruthData?.status as string) || 'unknown').toLowerCase();
      // Normalize legacy/variant statuses
      if (status.startsWith('processing')) status = 'processing';
      const objects = Array.isArray(groundTruthData?.objects) ? groundTruthData.objects : [];
      if (!objects.length) {
        if (status === 'pending' || status === 'processing' || status === 'retry') {
          throw new Error('Ground truth is still processing. Please try again in a moment.');
        }
        if (status === 'failed' || status === 'timeout' || status === 'error') {
          throw new Error('Ground truth processing failed. YOLO may not be available or an error occurred.');
        }
      }

      // Handle ground truth response format (backend returns objects)
      let detections: unknown[] = objects;
      if (isDebugEnabled()) {
        console.log('🧪 GT Final Check', {
          polledAttempts: pollCount,
          objectsCount: Array.isArray(objects) ? objects.length : 'NA',
          totalElapsedMs: Date.now() - startTime,
        });
      }
      
      if (isDebugEnabled()) {
        console.log('🔍 Raw ground truth response:', {
          responseType: typeof response,
          responseKeys: Object.keys(response),
          groundTruthDataKeys: groundTruthData ? Object.keys(groundTruthData) : 'null',
          detectionsType: typeof detections,
          detectionsIsArray: Array.isArray(detections),
          detectionsLength: Array.isArray(detections) ? detections.length : 'N/A',
          rawResponse: groundTruthData,
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
            hasClassValue: isObject(det) ? (det.class_label || (det as any).classLabel || det.class_name || det.className || (det as any).vruType || (det as any).vru_type || det.label || det.class || 'MISSING') : 'N/A',
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
          hasClass: isObject(detections[0]) ? (
            'class_label' in (detections[0] as any) ||
            'classLabel' in (detections[0] as any) ||
            'class_name' in (detections[0] as any) ||
            'className' in (detections[0] as any) ||
            'vruType' in (detections[0] as any) ||
            'vru_type' in (detections[0] as any) ||
            'label' in (detections[0] as any)
          ) : false
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
        processingTime: Date.now() - startTime  // Calculate processing time from start
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
      // Ground truth objects use 'class_label' field (new) or 'vru_type' field (old)
      const className = safeGet(det, 'class_label',
                        safeGet(det, 'classLabel',
                        safeGet(det, 'vru_type', 
                        safeGet(det, 'vruType',
                        safeGet(det, 'class_name', 
                        safeGet(det, 'class', 
                        safeGet(det, 'label', 
                        safeGet(det, 'name', 'person')))))))) as string;
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
        frameNumber: safeGet(det, 'frame_number', safeGet(det, 'frame', safeGet(det, 'frameNumber', Math.floor((safeGet(det, 'timestamp', 0) as number) * 30)))) as number,
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
  
  // WebSocket real-time detection subscription for live updates
  connectWebSocket(sessionId: string, onUpdate: (data: DetectionUpdate) => void): () => void {
    console.log('🔌 Subscribing to real-time detection events for session:', sessionId);

    // Import websocketService dynamically to avoid circular dependencies
    import('./websocketService').then(({ default: websocketService }) => {
      // Subscribe to session-specific detection events
      websocketService.emit('join_session', { session_id: sessionId });
      console.log('📡 Joined session room:', sessionId);
    }).catch(err => {
      console.error('❌ Failed to import websocketService:', err);
    });

    // Return unsubscribe function
    return () => {
      import('./websocketService').then(({ default: websocketService }) => {
        websocketService.emit('leave_session', { session_id: sessionId });
        console.log('🔕 Left session room:', sessionId);
      }).catch(err => {
        console.error('❌ Failed to leave session:', err);
      });
    };
  }

  disconnectWebSocket(): void {
    console.log('ℹ️ Detection WebSocket disconnected');
    // Cleanup handled by unsubscribe function returned from connectWebSocket
  }
}

export const detectionService = new DetectionService();
