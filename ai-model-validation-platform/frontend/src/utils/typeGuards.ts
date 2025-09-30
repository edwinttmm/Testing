/**
 * TypeScript Type Guards for React Hook Optimization
 * Provides runtime type checking to ensure type safety in React components
 */

import { VideoFile, GroundTruthAnnotation, VRUType, Annotation, BoundingBox, Detection, VideoStatus } from '../services/types';
import { AxiosError } from 'axios';
import logger from './safeErrorLogger';

/**
 * Type guard for VideoFile
 */
export function isVideoFile(obj: unknown): obj is VideoFile {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    'url' in obj &&
    typeof (obj as VideoFile).id === 'string' &&
    typeof (obj as VideoFile).url === 'string'
  );
}

/**
 * Type guard for array of VideoFiles
 */
export function isVideoFileArray(obj: unknown): obj is VideoFile[] {
  return Array.isArray(obj) && obj.every(isVideoFile);
}

/**
 * Type guard for GroundTruthAnnotation
 */
export function isGroundTruthAnnotation(obj: unknown): obj is GroundTruthAnnotation {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'id' in obj &&
    'videoId' in obj &&
    'boundingBox' in obj &&
    typeof (obj as GroundTruthAnnotation).id === 'string' &&
    typeof (obj as GroundTruthAnnotation).videoId === 'string'
  );
}

/**
 * Type guard for VRU Type
 */
export function isVRUType(value: unknown): value is VRUType {
  const validTypes: VRUType[] = [VRUType.PEDESTRIAN, VRUType.CYCLIST, VRUType.MOTORCYCLIST, VRUType.WHEELCHAIR, VRUType.SCOOTER];
  return typeof value === 'string' && validTypes.includes(value as VRUType);
}

/**
 * Type guard for React ref objects
 */
export function isReactRef<T>(obj: unknown): obj is React.RefObject<T> {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'current' in obj
  );
}

/**
 * Type guard for HTML video element
 */
export function isHTMLVideoElement(element: unknown): element is HTMLVideoElement {
  return element instanceof HTMLVideoElement;
}

/**
 * Type guard for connection state status
 */
export function isConnectionStatus(value: unknown): value is 'connected' | 'disconnected' | 'connecting' | 'reconnecting' | 'error' {
  const validStatuses = ['connected', 'disconnected', 'connecting', 'reconnecting', 'error'];
  return typeof value === 'string' && validStatuses.includes(value);
}

/**
 * Type guard for error objects
 */
export function isError(obj: unknown): obj is Error {
  return obj instanceof Error;
}

/**
 * Type guard for function
 */
export function isFunction(obj: unknown): obj is Function {
  return typeof obj === 'function';
}

/**
 * Type guard for non-null object
 */
export function isNonNullObject(obj: unknown): obj is Record<string, unknown> {
  return typeof obj === 'object' && obj !== null;
}

/**
 * Safe property access with type guard
 */
export function hasProperty<T extends string>(
  obj: unknown,
  prop: T
): obj is Record<T, unknown> {
  return isNonNullObject(obj) && prop in obj;
}

/**
 * Type assertion helper for hook dependencies
 */
export function assertNotNull<T>(value: T | null | undefined, message?: string): T {
  if (value == null) {
    throw new Error(message || 'Value is null or undefined');
  }
  return value;
}

/**
 * Safe callback wrapper for optional function props
 */
export function safeCallback<T extends unknown[], R>(
  callback: ((...args: T) => R) | undefined,
  fallback?: (...args: T) => R
): (...args: T) => R {
  return callback || fallback || ((() => undefined) as (...args: T) => R);
}

/**
 * Type-safe array filter for removing null/undefined values
 */
export function filterNonNull<T>(array: (T | null | undefined)[]): T[] {
  return array.filter((item): item is T => item != null);
}

/**
 * Validate object structure for React Hook dependencies
 */
export function validateDependencies(deps: readonly unknown[]): boolean {
  return deps.every(dep => {
    // Allow primitives
    if (dep === null || dep === undefined || typeof dep !== 'object') {
      return true;
    }
    
    // Check for stable references (functions, objects)
    if (typeof dep === 'function') {
      return dep.name !== ''; // Named functions are generally more stable
    }
    
    return true; // Allow all object dependencies for now
  });
}

/**
 * Create stable callback reference
 */
export function createStableCallback<T extends unknown[], R>(
  callback: (...args: T) => R,
  deps: readonly unknown[]
): (...args: T) => R {
  if (!validateDependencies(deps)) {
    logger.warn('Unstable dependencies detected in callback', deps, { context: 'type-guards' });
  }
  return callback;
}

/**
 * Type guard for Axios errors
 */
export function isAxiosError(obj: unknown): obj is AxiosError {
  return obj instanceof Error && 'isAxiosError' in obj && (obj as { isAxiosError: boolean }).isAxiosError === true;
}

/**
 * Type guard for objects
 */
export function isObject(obj: unknown): obj is Record<string, unknown> {
  return typeof obj === 'object' && obj !== null && !Array.isArray(obj);
}

/**
 * Type guard for arrays
 */
export function isArray(obj: unknown): obj is unknown[] {
  return Array.isArray(obj);
}

/**
 * Type guard for strings
 */
export function isString(obj: unknown): obj is string {
  return typeof obj === 'string';
}

/**
 * Type guard for numbers
 */
export function isNumber(obj: unknown): obj is number {
  return typeof obj === 'number' && !isNaN(obj);
}

/**
 * Safe getter with default fallback
 */
export function safeGet<T>(obj: unknown, path: string, defaultValue?: T): T | undefined {
  if (!isObject(obj)) return defaultValue;
  
  const keys = path.split('.');
  let result: unknown = obj;
  
  for (const key of keys) {
    if (!isObject(result) || !(key in result)) {
      return defaultValue;
    }
    result = result[key];
  }
  
  return result as T;
}

/**
 * Type guard for detection properties - validates individual detection object
 * Matches actual YOLO/backend response format with snake_case and array bbox
 */
export function hasDetectionProperties(obj: unknown): boolean {
  if (!isObject(obj)) {
    logger.debug('hasDetectionProperties: not an object', obj, { context: 'type-guards', function: 'hasDetectionProperties' });
    return false;
  }
  
  // Debug: show object keys and sample values
  const keys = Object.keys(obj);
  const sampleValues = Object.fromEntries(
    keys.slice(0, 5).map(key => [key, obj[key]])
  );
  logger.debug('hasDetectionProperties checking object', {
    keys,
    sampleValues,
    fullObject: obj
  }, { context: 'type-guards', function: 'hasDetectionProperties' });
  
  // Check for backend response format properties
  // Backend sends: class_name, bbox (array), confidence, frame_number, timestamp
  const hasConfidence = 'confidence' in obj && isNumber(obj.confidence);
  
  // Backend bbox can be array [x, y, width, height] or object {x, y, width, height}
  const hasBoundingBox = (
    ('bbox' in obj && (
      (isArray(obj.bbox) && (obj.bbox as unknown[]).length >= 4) ||
      (isObject(obj.bbox) && 'x' in obj.bbox && 'y' in obj.bbox && 'width' in obj.bbox && 'height' in obj.bbox)
    )) ||
    ('bounding_box' in obj && (
      (isArray(obj.bounding_box) && ((obj.bounding_box as unknown[]).length >= 4)) ||
      (isObject(obj.bounding_box) && 'x' in obj.bounding_box && 'y' in obj.bounding_box && 'width' in obj.bounding_box && 'height' in obj.bounding_box)
    )) ||
    ('boundingBox' in obj && (isArray(obj.boundingBox) || isObject(obj.boundingBox))) ||
    ('x' in obj && 'y' in obj && 'width' in obj && 'height' in obj) ||
    ('x1' in obj && 'y1' in obj && 'x2' in obj && 'y2' in obj)
  );
  
  // Backend sends class_name (snake_case), not className
  // Ground truth objects use 'vru_type' field
  const hasClass = (
    // Common variants
    ('class_name' in obj && isString(obj.class_name)) ||
    ('class_label' in obj && isString(obj.class_label)) ||
    ('classLabel' in obj && isString((obj as any).classLabel)) ||
    ('className' in obj && isString(obj.className)) ||
    ('label' in obj && isString(obj.label)) ||
    ('class' in obj && isString(obj.class)) ||
    ('name' in obj && isString(obj.name)) ||
    // VRU type variants
    ('vru_type' in obj && isString((obj as any).vru_type)) ||  // Ground truth format (old)
    ('vruType' in obj && isString((obj as any).vruType))       // Ground truth format (camelCase)
  );
  
  // Optional but commonly present in backend response
  const hasFrameInfo = (
    ('frame_number' in obj) || 
    ('frameNumber' in obj) || 
    ('timestamp' in obj)
  );
  
  logger.debug('hasDetectionProperties detailed checks', {
    hasConfidence,
    confidenceValue: obj.confidence,
    hasBoundingBox,
    bboxValue: obj.bbox || obj.bounding_box || obj.boundingBox,
    bboxType: typeof (obj.bbox || obj.bounding_box || obj.boundingBox),
    bboxIsArray: isArray(obj.bbox || obj.bounding_box || obj.boundingBox),
    bboxIsObject: isObject(obj.bbox || obj.bounding_box || obj.boundingBox),
    hasClass,
    classValue: obj.class_name || obj.class_label || (obj as any).classLabel || obj.className || obj.label || (obj as any).vru_type || (obj as any).vruType,
    hasFrameInfo,
    frameValue: obj.frame_number || obj.frameNumber,
    timestampValue: obj.timestamp,
    objectKeys: keys
  }, { context: 'type-guards', function: 'hasDetectionProperties' });
  
  // Detection must have confidence, bbox, and class - frame info is optional
  const hasValidDetectionStructure = hasConfidence && hasBoundingBox && hasClass;
  
  if (!hasValidDetectionStructure) {
    logger.warn('Detection validation failed', {
      missingConfidence: !hasConfidence,
      missingBoundingBox: !hasBoundingBox, 
      missingClass: !hasClass,
      object: obj
    }, { context: 'type-guards', function: 'hasDetectionProperties' });
  }
  
  logger.debug('hasDetectionProperties final result', { 
    result: hasValidDetectionStructure, 
    object: obj 
  }, { context: 'type-guards', function: 'hasDetectionProperties' });
  
  return hasValidDetectionStructure;
}

/**
 * Type guard for detection response containers (legacy - kept for backward compatibility)
 */
export function hasDetectionContainer(obj: unknown): boolean {
  return isObject(obj) && 
    ('detections' in obj || 'detection_results' in obj || 'annotations' in obj);
}

/**
 * Map YOLO class names to VRU types
 * Handles common class name variations from different models
 */
export function mapYoloClassToVRUType(className: string): string {
  const classMap: Record<string, string> = {
    // COCO/YOLO standard classes
    'person': 'pedestrian',
    'people': 'pedestrian', 
    'human': 'pedestrian',
    'pedestrian': 'pedestrian',
    'child': 'pedestrian',
    'children': 'pedestrian',
    
    // Bicycle/Cyclist classes
    'bicycle': 'cyclist',
    'bike': 'cyclist',
    'cyclist': 'cyclist',
    'bicyclist': 'cyclist',
    
    // Motorcycle classes  
    'motorcycle': 'motorcyclist',
    'motorbike': 'motorcyclist',
    'motorcyclist': 'motorcyclist',
    
    // Scooter classes
    'scooter': 'scooter_rider',
    'scooter_rider': 'scooter_rider',
    'e_scooter': 'scooter_rider',
    
    // Wheelchair classes
    'wheelchair': 'wheelchair_user',
    'wheelchair_user': 'wheelchair_user'
  };
  
  const lowerClassName = className.toLowerCase();
  const result = classMap[lowerClassName] || 'pedestrian'; // Default to pedestrian
  
  // Debug logging for class mapping
  logger.debug('Class mapping', { input: className, output: result }, { context: 'type-guards', function: 'mapYoloClassToVRUType' });
  
  return result;
}

/**
 * Type guard for valid WebSocket data
 */
export function isValidWebSocketData(data: unknown): data is Record<string, unknown> {
  return isObject(data) && ('type' in data || 'event' in data);
}

/**
 * Parse error response safely with type checking
 */
export function parseErrorResponse(error: unknown): { message: string; code?: string | number; details?: unknown; status?: number } {
  if (isAxiosError(error)) {
    const response = error.response;
    if (response && isObject(response.data)) {
      return {
        message: isString(response.data.message) ? response.data.message : error.message,
        code: response.status,
        status: response.status,
        details: response.data
      };
    }
    const result: { message: string; code?: string | number; details?: unknown; status?: number } = {
      message: error.message,
      details: error
    };
    if (error.code !== undefined) {
      result.code = error.code;
    }
    return result;
  }
  
  if (isError(error)) {
    return {
      message: error.message,
      details: error
    };
  }
  
  if (isObject(error) && hasProperty(error, 'message') && isString(error.message)) {
    const result: { message: string; code?: string | number; details?: unknown; status?: number } = {
      message: error.message,
      details: error
    };
    if (hasProperty(error, 'code') && (isString(error.code) || isNumber(error.code))) {
      result.code = error.code;
    }
    return result;
  }
  
  return {
    message: 'Unknown error occurred',
    details: error
  };
}

/**
 * Safe object spreading with type validation - overloaded function
 */
export function safeSpread<T extends Record<string, unknown>>(source: unknown): T;
export function safeSpread<T extends Record<string, unknown>>(target: T, source: unknown): T;
export function safeSpread<T extends Record<string, unknown>>(
  targetOrSource: T | unknown,
  source?: unknown
): T {
  // Single parameter usage: safeSpread<T>(obj)
  if (arguments.length === 1) {
    const sourceObj = targetOrSource;
    if (!isObject(sourceObj)) {
      return {} as T;
    }
    try {
      return { ...sourceObj } as T;
    } catch (error) {
      logger.warn('Safe spread failed (single parameter)', error, { context: 'type-guards', function: 'safeSpread' });
      return {} as T;
    }
  }
  
  // Two parameter usage: safeSpread(target, source)
  const target = targetOrSource as T;
  if (!isObject(source)) {
    return target;
  }
  
  try {
    return { ...target, ...source } as T;
  } catch (error) {
    logger.warn('Safe spread failed (dual parameter)', error, { context: 'type-guards', function: 'safeSpread' });
    return target;
  }
}

/**
 * Type guard for checking if response has data property
 */
export function hasResponseData<T = unknown>(response: unknown): response is { data: T } {
  return isObject(response) && 'data' in response;
}

/**
 * Convert unknown data to VideoFile with validation
 */
export function convertToVideoFile(data: unknown): VideoFile | null {
  if (!isObject(data)) {
    return null;
  }
  
  // Check required VideoFile properties from types.ts
  if (!hasProperty(data, 'id') || !isString(data.id)) {
    return null;
  }
  
  // ProjectId - handle null values for shared video architecture
  const projectId = (hasProperty(data, 'projectId') && (isString(data.projectId) || data.projectId === null)) ? data.projectId : 
                   (hasProperty(data, 'project_id') && (isString(data.project_id) || data.project_id === null)) ? data.project_id : null;
  
  try {
    const videoFile: VideoFile = {
      id: data.id,
      projectId: projectId,
      filename: (hasProperty(data, 'filename') && isString(data.filename)) ? data.filename : `video_${data.id}.mp4`,
      fileSize: (hasProperty(data, 'fileSize') && isNumber(data.fileSize)) ? data.fileSize :
               (hasProperty(data, 'file_size') && isNumber(data.file_size)) ? data.file_size :
               (hasProperty(data, 'size') && isNumber(data.size)) ? data.size : 0,
      processingStatus: (hasProperty(data, 'processingStatus') && isString(data.processingStatus)) ? 
                       data.processingStatus : 
                       (hasProperty(data, 'processing_status') && isString(data.processing_status)) ? 
                       data.processing_status : 'pending',
      groundTruthGenerated: (hasProperty(data, 'groundTruthGenerated') && typeof data.groundTruthGenerated === 'boolean') ? 
                           data.groundTruthGenerated : 
                           (hasProperty(data, 'ground_truth_generated') && typeof data.ground_truth_generated === 'boolean') ? 
                           data.ground_truth_generated : false,
      detectionCount: (hasProperty(data, 'detectionCount') && isNumber(data.detectionCount)) ? 
                     data.detectionCount : 
                     (hasProperty(data, 'detection_count') && isNumber(data.detection_count)) ? 
                     data.detection_count : 0,
      annotationCount: (hasProperty(data, 'annotationCount') && isNumber(data.annotationCount)) ? 
                      data.annotationCount : 0,
      createdAt: (hasProperty(data, 'createdAt') && isString(data.createdAt)) ? data.createdAt : 
                 (hasProperty(data, 'created_at') && isString(data.created_at)) ? data.created_at : new Date().toISOString(),
      status: (hasProperty(data, 'status') && isString(data.status) && 
             Object.values(VideoStatus).includes(data.status as VideoStatus)) 
             ? data.status as VideoStatus
             : VideoStatus.PROCESSING,
      
      // Optional properties with compatibility fields
      originalName: (hasProperty(data, 'originalName') && isString(data.originalName)) ? data.originalName : 
                   (hasProperty(data, 'original_name') && isString(data.original_name)) ? data.original_name : undefined,
      name: (hasProperty(data, 'name') && isString(data.name)) ? data.name : 
            (hasProperty(data, 'filename') && isString(data.filename)) ? data.filename : undefined,
      size: (hasProperty(data, 'size') && isNumber(data.size)) ? data.size : 
           (hasProperty(data, 'fileSize') && isNumber(data.fileSize)) ? data.fileSize :
           (hasProperty(data, 'file_size') && isNumber(data.file_size)) ? data.file_size : undefined,
      url: (hasProperty(data, 'url') && isString(data.url)) ? data.url : undefined,
      uploadedAt: (hasProperty(data, 'uploadedAt') && isString(data.uploadedAt)) ? data.uploadedAt : 
                 (hasProperty(data, 'uploaded_at') && isString(data.uploaded_at)) ? data.uploaded_at : undefined,
      filePath: (hasProperty(data, 'filePath') && isString(data.filePath)) ? data.filePath : 
               (hasProperty(data, 'file_path') && isString(data.file_path)) ? data.file_path : undefined,
      duration: (hasProperty(data, 'duration') && isNumber(data.duration)) ? data.duration : undefined,
      frameRate: (hasProperty(data, 'frameRate') && isNumber(data.frameRate)) ? data.frameRate : 
                (hasProperty(data, 'frame_rate') && isNumber(data.frame_rate)) ? data.frame_rate : undefined,
      width: (hasProperty(data, 'width') && isNumber(data.width)) ? data.width : undefined,
      height: (hasProperty(data, 'height') && isNumber(data.height)) ? data.height : undefined
    };

    // Add optional properties only if they exist and are valid - comprehensive mapping
    if (hasProperty(data, 'fileSize') && isNumber(data.fileSize)) {
      videoFile.fileSize = data.fileSize;
    }
    if (hasProperty(data, 'file_size') && isNumber(data.file_size)) {
      videoFile.file_size = data.file_size;
    }
    if (hasProperty(data, 'duration') && isNumber(data.duration)) {
      videoFile.duration = data.duration;
    }
    if (hasProperty(data, 'frameRate') && isNumber(data.frameRate)) {
      videoFile.frameRate = data.frameRate;
    }
    if (hasProperty(data, 'frame_rate') && isNumber(data.frame_rate)) {
      videoFile.frame_rate = data.frame_rate;
    }
    if (hasProperty(data, 'createdAt') && isString(data.createdAt)) {
      videoFile.createdAt = data.createdAt;
    }
    if (hasProperty(data, 'created_at') && isString(data.created_at)) {
      videoFile.created_at = data.created_at;
    }
    if (hasProperty(data, 'updatedAt') && isString(data.updatedAt)) {
      videoFile.updatedAt = data.updatedAt;
    }
    if (hasProperty(data, 'updatedAt') && isString(data.updatedAt)) {
      videoFile.updatedAt = data.updatedAt;
    }
    if (hasProperty(data, 'processing_status') && isString(data.processing_status) && 
        ['pending', 'processing', 'completed', 'failed'].includes(data.processing_status)) {
      videoFile.processing_status = data.processing_status as 'pending' | 'processing' | 'completed' | 'failed';
    }
    if (hasProperty(data, 'groundTruthStatus') && isString(data.groundTruthStatus) && 
        ['pending', 'processing', 'completed', 'failed'].includes(data.groundTruthStatus)) {
      videoFile.groundTruthStatus = data.groundTruthStatus as 'pending' | 'processing' | 'completed' | 'failed';
    }
    if (hasProperty(data, 'ground_truth_status') && isString(data.ground_truth_status) && 
        ['pending', 'processing', 'completed', 'failed'].includes(data.ground_truth_status)) {
      videoFile.ground_truth_status = data.ground_truth_status as 'pending' | 'processing' | 'completed' | 'failed';
    }
    if (hasProperty(data, 'groundTruthGenerated') && data.groundTruthGenerated !== undefined) {
      videoFile.groundTruthGenerated = Boolean(data.groundTruthGenerated);
    }
    if (hasProperty(data, 'ground_truth_generated') && data.ground_truth_generated !== undefined) {
      videoFile.ground_truth_generated = Boolean(data.ground_truth_generated);
    }
    if (hasProperty(data, 'detectionCount') && isNumber(data.detectionCount)) {
      videoFile.detectionCount = data.detectionCount;
    }
    if (hasProperty(data, 'detection_count') && isNumber(data.detection_count)) {
      videoFile.detection_count = data.detection_count;
    }
    // Backend path and metadata fields
    if (hasProperty(data, 'project_id')) {
      if (isString(data.project_id)) {
        videoFile.project_id = parseInt(data.project_id, 10);
      } else if (isNumber(data.project_id)) {
        videoFile.project_id = data.project_id;
      }
    }
    if (hasProperty(data, 'original_name') && isString(data.original_name)) {
      videoFile.original_name = data.original_name;
    }
    if (hasProperty(data, 'file_path') && isString(data.file_path)) {
      videoFile.file_path = data.file_path;
    }
    if (hasProperty(data, 'uploaded_at') && isString(data.uploaded_at)) {
      videoFile.uploaded_at = data.uploaded_at;
    }
    if (hasProperty(data, 'width') && isNumber(data.width)) {
      videoFile.width = data.width;
    }
    if (hasProperty(data, 'height') && isNumber(data.height)) {
      videoFile.height = data.height;
    }
    if (hasProperty(data, 'fps') && isNumber(data.fps)) {
      videoFile.fps = data.fps;
    }
    if (hasProperty(data, 'bitrate') && isNumber(data.bitrate)) {
      videoFile.bitrate = data.bitrate;
    }
    if (hasProperty(data, 'format') && isString(data.format)) {
      videoFile.format = data.format;
    }
    if (hasProperty(data, 'codec') && isString(data.codec)) {
      videoFile.codec = data.codec;
    }
    if (hasProperty(data, 'thumbnailUrl') && isString(data.thumbnailUrl)) {
      videoFile.thumbnailUrl = data.thumbnailUrl;
    }
    if (hasProperty(data, 'metadata') && isObject(data.metadata)) {
      videoFile.metadata = data.metadata;
    }
    if (hasProperty(data, 'annotations') && isArray(data.annotations)) {
      // Convert array items to Annotation[] format for VideoFile compatibility
      videoFile.annotations = data.annotations.map((annotation: unknown) => {
        // Enhanced conversion handling both camelCase and snake_case fields
        if (isObject(annotation)) {
          const id = safeGet(annotation, 'id', '') as string;
          const videoId = safeGet(annotation, 'videoId', safeGet(annotation, 'video_id', '')) as string;
          const timestamp = safeGet(annotation, 'timestamp', 0) as number;
          const endTimestamp = safeGet(annotation, 'endTimestamp', safeGet(annotation, 'end_timestamp', undefined)) as number | undefined;
          
          // Handle bounding box from various field formats
          let boundingBoxes: BoundingBox[] = [];
          const bbox = safeGet(annotation, 'boundingBox', safeGet(annotation, 'bounding_box', safeGet(annotation, 'bbox', null)));
          if (isObject(bbox)) {
            boundingBoxes = [{
              x: safeGet(bbox, 'x', 0) as number,
              y: safeGet(bbox, 'y', 0) as number,
              width: safeGet(bbox, 'width', 100) as number,
              height: safeGet(bbox, 'height', 100) as number,
              label: safeGet(bbox, 'label', safeGet(bbox, 'class_label', 'unknown')) as string,
              confidence: safeGet(bbox, 'confidence', safeGet(bbox, 'score', 1.0)) as number
            }];
          }
          
          const detectionType = safeGet(annotation, 'vruType', 
            safeGet(annotation, 'vru_type',
              safeGet(annotation, 'detectionType', 
                safeGet(annotation, 'class_label', 'pedestrian')))) as string;
                
          const confidence = safeGet(annotation, 'confidence', 1.0) as number;
          
          // Try to get detections array or create from annotation data
          let detections: Detection[] = [];
          const detectionsArray = safeGet(annotation, 'detections', []);
          if (isArray(detectionsArray)) {
            detections = detectionsArray.map((det: unknown) => det as Detection);
          } else {
            // Create a detection from the annotation itself if no separate detections
            detections = [{
              id: id,
              videoId: safeGet(annotation, 'videoId', safeGet(annotation, 'video_id', 'unknown')) as string,
              detectionId: safeGet(annotation, 'detectionId', safeGet(annotation, 'detection_id', id)) as string,
              frameNumber: safeGet(annotation, 'frameNumber', safeGet(annotation, 'frame_number', 0)) as number,
              classId: safeGet(annotation, 'classId', safeGet(annotation, 'class_id', 1)) as number,
              className: safeGet(annotation, 'className', safeGet(annotation, 'class_name', detectionType)) as string,
              validationStatus: safeGet(annotation, 'validationStatus', safeGet(annotation, 'validation_status', 'pending')) as 'pending' | 'validated' | 'rejected' | 'needs_review',
              timestamp: timestamp,
              boundingBox: (() => {
                const bbox = boundingBoxes[0];
                if (!bbox) {
                  console.warn('🚨 USING FALLBACK BOUNDING BOX - Real detection data not found!', {
                    annotation,
                    boundingBoxes,
                    expectedData: 'bbox array should contain real detection coordinates'
                  });
                  return { x: 0, y: 0, width: 100, height: 100, label: 'unknown', confidence: 1.0 };
                }
                return bbox;
              })(),
              vruType: detectionType as VRUType,
              confidence: confidence,
              isGroundTruth: true,
              validated: safeGet(annotation, 'validated', false) as boolean,
              createdAt: safeGet(annotation, 'createdAt', safeGet(annotation, 'created_at', new Date().toISOString())) as string
            }];
          }
          
          return {
            id: id,
            videoId: videoId,
            timestamp: timestamp,
            endTimestamp: endTimestamp,
            boundingBoxes: boundingBoxes,
            detectionType: detectionType,
            confidence: confidence,
            detections: detections
          } as Annotation;
        }
        return annotation as Annotation;
      });
    }
    
    return videoFile;
  } catch (error) {
    logger.warn('Failed to convert to VideoFile', error, { context: 'type-guards', function: 'convertToVideoFile' });
    return null;
  }
}

/**
 * Safely convert array with type checking and filtering
 */
export function safeConvertArray<T>(
  data: unknown,
  converter: (item: unknown) => T | null
): T[] {
  if (!isArray(data)) {
    return [];
  }
  
  try {
    return data
      .map(converter)
      .filter((item): item is T => item !== null);
  } catch (error) {
    logger.warn('Safe convert array failed', error, { context: 'type-guards', function: 'safeConvertArray' });
    return [];
  }
}

/**
 * Type guard for API error response structure
 */
export function isApiErrorResponse(obj: unknown): obj is {
  error: string;
  message?: string;
  code?: string | number;
  details?: unknown;
} {
  return isObject(obj) && 
    'error' in obj && 
    isString(obj.error) &&
    (obj.error.length > 0);
}

/**
 * Safely convert unknown to Record<string, unknown> for API parameters
 */
export function safeParams(params: unknown): Record<string, unknown> | undefined {
  if (params == null) {
    return undefined;
  }
  if (isObject(params)) {
    return params;
  }
  // If it's not an object, return undefined instead of trying to convert
  return undefined;
}

/**
 * Safely extract error data from AxiosResponse for ErrorFactory
 */
export function safeExtractErrorData(response: unknown): Record<string, unknown> | null {
  if (!response) {
    return null;
  }
  
  // Check if it's an AxiosResponse
  if (isObject(response) && hasProperty(response, 'data') && hasProperty(response, 'status')) {
    return {
      status: response.status,
      data: response.data,
      statusText: hasProperty(response, 'statusText') ? response.statusText : 'Unknown'
    };
  }
  
  // If it's already a Record<string, unknown>, return it
  if (isObject(response)) {
    return response;
  }
  
  return null;
}
