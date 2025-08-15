/**
 * Universal Error Handling Utilities
 * Prevents [object Object] display by safely extracting error messages
 */

/**
 * Safely extracts a string error message from any error type
 * @param error - Any error object, string, or unknown type
 * @param fallback - Fallback message if no valid message found
 * @returns Safe string message for display
 */
export const getErrorMessage = (error: unknown, fallback: string = 'An unexpected error occurred'): string => {
  // If it's already a string, return it
  if (typeof error === 'string') {
    return error;
  }
  
  // If it's an Error instance, return the message
  if (error instanceof Error) {
    return error.message;
  }
  
  // If it's an object with a message property
  if (error && typeof error === 'object' && 'message' in error) {
    const message = (error as any).message;
    if (typeof message === 'string') {
      return message;
    }
  }
  
  // If it's an object with an error property
  if (error && typeof error === 'object' && 'error' in error) {
    const errorProp = (error as any).error;
    if (typeof errorProp === 'string') {
      return errorProp;
    }
  }
  
  // If it's an object with a detail property (common in API responses)
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as any).detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  
  // Return fallback for any other case
  return fallback;
};

/**
 * Creates a safe Error object from any error type
 * @param error - Any error object, string, or unknown type
 * @param fallback - Fallback message if no valid message found
 * @returns Error object with safe message
 */
export const createSafeError = (error: unknown, fallback: string = 'An unexpected error occurred'): Error => {
  if (error instanceof Error) {
    return error;
  }
  
  const message = getErrorMessage(error, fallback);
  return new Error(message);
};

/**
 * Safely handles WebSocket error data
 * @param data - WebSocket error data
 * @returns Safe error message for display
 */
export const getWebSocketErrorMessage = (data: unknown): string => {
  return getErrorMessage(data, 'WebSocket connection error occurred');
};

/**
 * Safely handles API error responses
 * @param error - API error response
 * @returns Safe error message for display
 */
export const getApiErrorMessage = (error: unknown): string => {
  // Check for common API error structures
  if (error && typeof error === 'object') {
    const apiError = error as any;
    
    // Check response.data structure (Axios style)
    if (apiError.response?.data) {
      return getErrorMessage(apiError.response.data, 'API request failed');
    }
    
    // Check for direct API error properties
    if (apiError.detail || apiError.message || apiError.error) {
      return getErrorMessage(apiError, 'API request failed');
    }
  }
  
  return getErrorMessage(error, 'API request failed');
};

/**
 * Prevents [object Object] by ensuring only valid strings are returned
 * @param value - Any value that might be displayed as text
 * @param fallback - Fallback if value is not a valid string
 * @returns Safe string for display
 */
export const ensureString = (value: unknown, fallback: string = 'Invalid data'): string => {
  if (typeof value === 'string') {
    return value;
  }
  
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  
  return fallback;
};