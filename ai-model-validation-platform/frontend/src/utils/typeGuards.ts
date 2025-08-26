/**
 * TypeScript Type Guards for React Hook Optimization
 * Provides runtime type checking to ensure type safety in React components
 */

import { VideoFile, GroundTruthAnnotation, VRUType } from '../services/types';
import { AxiosError } from 'axios';

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
  const validTypes: VRUType[] = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair_user', 'scooter_rider'];
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
    console.warn('Unstable dependencies detected in callback');
  }
  return callback;
}

/**
 * Type guard for Axios errors
 */
export function isAxiosError(obj: unknown): obj is AxiosError {
  return obj instanceof Error && 'isAxiosError' in obj && (obj as any).isAxiosError === true;
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
  let result: any = obj;
  
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
 * Checks for actual YOLO detection properties instead of nested containers
 */
export function hasDetectionProperties(obj: unknown): boolean {
  if (!isObject(obj)) {
    console.log('🔍 hasDetectionProperties: not an object', obj);
    return false;
  }
  
  // Debug: show object keys
  const keys = Object.keys(obj);
  console.log('🔍 hasDetectionProperties checking object with keys:', keys);
  
  // Check for YOLO detection object properties - be more permissive
  const hasConfidence = 'confidence' in obj || 'conf' in obj || 'score' in obj;
  const hasBoundingBox = 'bbox' in obj || 'boundingBox' in obj || 'box' in obj || 
     ('x' in obj && 'y' in obj && 'width' in obj && 'height' in obj) ||
     ('x1' in obj && 'y1' in obj && 'x2' in obj && 'y2' in obj);
  const hasClass = 'class' in obj || 'label' in obj || 'category' in obj || 'name' in obj || 'class_id' in obj;
  
  console.log('🔍 hasDetectionProperties checks:', {
    hasConfidence,
    hasBoundingBox,
    hasClass,
    objectKeys: keys
  });
  
  // Be more permissive - accept if it has at least confidence OR bounding box OR class
  const hasValidDetectionStructure = hasConfidence || hasBoundingBox || hasClass;
  
  console.log('🔍 hasDetectionProperties result:', hasValidDetectionStructure, 'for object:', obj);
  
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
  return classMap[lowerClassName] || 'pedestrian'; // Default to pedestrian
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
      console.warn('Safe spread failed:', error);
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
    console.warn('Safe spread failed:', error);
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
  
  // ProjectId is required in the interface
  const projectId = (hasProperty(data, 'projectId') && isString(data.projectId)) ? data.projectId : '';
  
  try {
    const videoFile: VideoFile = {
      id: data.id,
      projectId: projectId,
      filename: (hasProperty(data, 'filename') && isString(data.filename)) ? data.filename : `video_${data.id}.mp4`,
      originalName: (hasProperty(data, 'originalName') && isString(data.originalName)) ? data.originalName : 
                   (hasProperty(data, 'original_name') && isString(data.original_name)) ? data.original_name : data.id,
      size: (hasProperty(data, 'size') && isNumber(data.size)) ? data.size : 
           (hasProperty(data, 'fileSize') && isNumber(data.fileSize)) ? data.fileSize :
           (hasProperty(data, 'file_size') && isNumber(data.file_size)) ? data.file_size : 0,
      url: (hasProperty(data, 'url') && isString(data.url)) ? data.url : '',
      status: (hasProperty(data, 'status') && isString(data.status) && 
             ['uploading', 'processing', 'completed', 'failed'].includes(data.status)) 
             ? data.status as 'uploading' | 'processing' | 'completed' | 'failed'
             : 'uploading',
      uploadedAt: (hasProperty(data, 'uploadedAt') && isString(data.uploadedAt)) ? data.uploadedAt : 
                 (hasProperty(data, 'uploaded_at') && isString(data.uploaded_at)) ? data.uploaded_at : new Date().toISOString(),
      
      // Optional properties - only set if they have valid values
      name: (hasProperty(data, 'name') && isString(data.name)) ? data.name : 
            (hasProperty(data, 'filename') && isString(data.filename)) ? data.filename : data.id
    };

    // Add optional properties only if they exist and are valid
    if (hasProperty(data, 'fileSize') && isNumber(data.fileSize)) {
      videoFile.fileSize = data.fileSize;
    }
    if (hasProperty(data, 'file_size') && isNumber(data.file_size)) {
      videoFile.file_size = data.file_size;
    }
    if (hasProperty(data, 'duration') && isNumber(data.duration)) {
      videoFile.duration = data.duration;
    }
    if (hasProperty(data, 'createdAt') && isString(data.createdAt)) {
      videoFile.createdAt = data.createdAt;
    }
    if (hasProperty(data, 'created_at') && isString(data.created_at)) {
      videoFile.created_at = data.created_at;
    }
    if (hasProperty(data, 'processing_status') && isString(data.processing_status) && 
        ['pending', 'processing', 'completed', 'failed'].includes(data.processing_status)) {
      videoFile.processing_status = data.processing_status as 'pending' | 'processing' | 'completed' | 'failed';
    }
    if (hasProperty(data, 'groundTruthStatus') && isString(data.groundTruthStatus) && 
        ['pending', 'processing', 'completed', 'failed'].includes(data.groundTruthStatus)) {
      videoFile.groundTruthStatus = data.groundTruthStatus as 'pending' | 'processing' | 'completed' | 'failed';
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
      videoFile.annotations = data.annotations as any;
    }
    
    return videoFile;
  } catch (error) {
    console.warn('Failed to convert to VideoFile:', error);
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
    console.warn('Safe convert array failed:', error);
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