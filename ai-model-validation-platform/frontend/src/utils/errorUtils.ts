/**
 * Enhanced error utilities with better error message extraction
 */

import { AxiosError } from 'axios';

export interface AppError {
  message: string;
  code?: string | undefined;
  status?: number | undefined;
  details?: unknown;
  timestamp?: Date | undefined;
  context?: string | undefined;
}

/**
 * Extracts user-friendly error message from various error types
 */
export function getErrorMessage(error: unknown, fallback = 'An unexpected error occurred'): string {
  if (typeof error === 'string') {
    return error;
  }

  if (error instanceof Error) {
    return error.message;
  }

  // Handle Axios errors
  if (isAxiosError(error)) {
    // Try to extract message from response data
    const responseData = error.response?.data;
    
    if (typeof responseData === 'string') {
      return responseData;
    }
    
    if (responseData && typeof responseData === 'object') {
      const errorObj = responseData as Record<string, unknown>;
      const message = errorObj.message || errorObj.detail || errorObj.error;
      if (typeof message === 'string') {
        return message;
      }
    }

    // Handle different status codes
    if (error.response?.status) {
      switch (error.response.status) {
        case 400:
          return 'Invalid request. Please check your input and try again.';
        case 401:
          return 'Authentication required. Please sign in and try again.';
        case 403:
          return 'You don\'t have permission to perform this action.';
        case 404:
          return 'The requested resource was not found.';
        case 405:
          return 'This operation is not currently supported.';
        case 408:
          return 'The request timed out. Please try again.';
        case 409:
          return 'There was a conflict. Please refresh and try again.';
        case 429:
          return 'Too many requests. Please wait and try again.';
        case 500:
          return 'Internal server error. Please try again later.';
        case 502:
          return 'Bad gateway. The server is temporarily unavailable.';
        case 503:
          return 'Service temporarily unavailable. Please try again in a few moments.';
        case 504:
          return 'Gateway timeout. Please try again later.';
        default:
          return `Server error (${error.response.status}). Please try again.`;
      }
    }

    // Network errors
    if (error.code === 'ERR_NETWORK' || error.code === 'NETWORK_ERROR') {
      return 'Network error. Please check your internet connection.';
    }

    if (error.code === 'ERR_CANCELED') {
      return 'The operation was cancelled.';
    }

    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      return 'Request timed out. Please try again.';
    }

    return error.message || fallback;
  }

  // If it's an object with a message property
  if (error && typeof error === 'object' && 'message' in error) {
    const message = (error as Record<string, unknown>).message;
    if (typeof message === 'string') {
      return message;
    }
  }
  
  // If it's an object with an error property
  if (error && typeof error === 'object' && 'error' in error) {
    const errorProp = (error as Record<string, unknown>).error;
    if (typeof errorProp === 'string') {
      return errorProp;
    }
  }
  
  // If it's an object with a detail property (common in API responses)
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as Record<string, unknown>).detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }

  return fallback;
}

/**
 * Type guard for Axios errors
 */
function isAxiosError(error: unknown): error is AxiosError {
  return error !== null &&
    typeof error === 'object' &&
    'isAxiosError' in error &&
    (error as AxiosError).isAxiosError === true;
}

/**
 * Creates a standardized AppError from any error type
 */
export function normalizeError(error: unknown, context?: string): AppError {
  const timestamp = new Date();
  
  if (error instanceof Error) {
    const errorObj: AppError = {
      message: getErrorMessage(error),
      timestamp,
    };
    
    const errorRecord = error as unknown as Record<string, unknown>;
    if (errorRecord.code && typeof errorRecord.code === 'string') errorObj.code = errorRecord.code;
    if (errorRecord.status && typeof errorRecord.status === 'number') errorObj.status = errorRecord.status;
    if (error.stack) errorObj.details = error.stack;
    if (context) errorObj.context = context;
    
    return errorObj;
  }

  if (isAxiosError(error)) {
    const errorObj: AppError = {
      message: getErrorMessage(error),
      timestamp,
    };
    
    if (error.code) errorObj.code = error.code;
    if (error.response?.status) errorObj.status = error.response.status;
    if (context) errorObj.context = context;
    
    errorObj.details = {
      method: error.config?.method,
      url: error.config?.url,
      data: error.response?.data,
    };
    
    return errorObj;
  }

  const errorObj: AppError = {
    message: getErrorMessage(error),
    timestamp,
  };
  
  if (context) errorObj.context = context;
  
  return errorObj;
}

/**
 * Creates a safe Error object from any error type
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
    const apiError = error as Record<string, unknown>;
    
    // Check response.data structure (Axios style)
    if ('response' in apiError && apiError.response && typeof apiError.response === 'object' && 'data' in apiError.response) {
      return getErrorMessage((apiError.response as Record<string, unknown>).data, 'API request failed');
    }
    
    // Check for direct API error properties
    if (apiError.detail || apiError.message || apiError.error) {
      return getErrorMessage(apiError, 'API request failed');
    }
  }
  
  return getErrorMessage(error, 'API request failed');
};

/**
 * Determines if an error is retryable
 */
export function isRetryableError(error: unknown): boolean {
  if (isAxiosError(error)) {
    // Network errors are retryable
    if (error.code === 'ERR_NETWORK' || error.code === 'ECONNABORTED') {
      return true;
    }

    // Server errors (5xx) are retryable
    if (error.response?.status && error.response.status >= 500) {
      return true;
    }

    // Some client errors are retryable
    if (error.response?.status === 408 || error.response?.status === 429) {
      return true;
    }

    return false;
  }

  // Timeout errors are retryable
  if (error instanceof Error && error.message.includes('timeout')) {
    return true;
  }

  // Default to non-retryable for safety
  return false;
}

/**
 * Gets user-friendly suggestions based on error type
 */
export function getErrorSuggestions(error: unknown): string[] {
  const suggestions: string[] = [];

  if (isAxiosError(error)) {
    if (error.code === 'ERR_NETWORK') {
      suggestions.push('Check your internet connection');
      suggestions.push('Try refreshing the page');
    } else if (error.response?.status === 503) {
      suggestions.push('The service may be undergoing maintenance');
      suggestions.push('Try again in a few minutes');
    } else if (error.response?.status === 429) {
      suggestions.push('You\'re making requests too quickly');
      suggestions.push('Wait a moment before trying again');
    } else if (error.response?.status === 401) {
      suggestions.push('Your session may have expired');
      suggestions.push('Try refreshing the page');
    }
  }

  if (suggestions.length === 0) {
    suggestions.push('Try refreshing the page');
    suggestions.push('Contact support if the problem persists');
  }

  return suggestions;
}

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

export default {
  getErrorMessage,
  normalizeError,
  isRetryableError,
  getErrorSuggestions,
  createSafeError,
  ensureString,
  getWebSocketErrorMessage,
  getApiErrorMessage,
};