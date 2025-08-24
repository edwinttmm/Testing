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
 * Type guard for detection properties
 */
export function hasDetectionProperties(obj: unknown): boolean {
  return isObject(obj) && 
    ('detections' in obj || 'detection_results' in obj || 'annotations' in obj);
}

/**
 * Type guard for valid WebSocket data
 */
export function isValidWebSocketData(data: unknown): data is Record<string, unknown> {
  return isObject(data) && ('type' in data || 'event' in data);
}