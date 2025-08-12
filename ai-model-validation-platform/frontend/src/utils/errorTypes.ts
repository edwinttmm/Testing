// Error type definitions and utilities for the AI Model Validation Platform

export interface AppError extends Error {
  code?: string;
  statusCode?: number;
  context?: Record<string, any>;
  timestamp?: string;
  retry?: boolean;
}

export class NetworkError extends Error implements AppError {
  code = 'NETWORK_ERROR';
  retry = true;
  timestamp: string;
  
  constructor(message: string = 'Network request failed', public statusCode?: number, public context?: Record<string, any>) {
    super(message);
    this.name = 'NetworkError';
    this.timestamp = new Date().toISOString();
  }
}

export class WebSocketError extends Error implements AppError {
  code = 'WEBSOCKET_ERROR';
  retry = true;
  timestamp: string;
  
  constructor(message: string = 'WebSocket connection failed', public context?: Record<string, any>) {
    super(message);
    this.name = 'WebSocketError';
    this.timestamp = new Date().toISOString();
  }
}

export class ApiError extends Error implements AppError {
  code = 'API_ERROR';
  retry = false;
  timestamp: string;
  
  constructor(message: string = 'API request failed', public statusCode?: number, public context?: Record<string, any>) {
    super(message);
    this.name = 'ApiError';
    this.timestamp = new Date().toISOString();
    
    // Determine if retry is possible based on status code
    if (statusCode && (statusCode >= 500 || statusCode === 429)) {
      this.retry = true;
    }
  }
}

export class ValidationError extends Error implements AppError {
  code = 'VALIDATION_ERROR';
  retry = false;
  timestamp: string;
  
  constructor(message: string = 'Validation failed', public context?: Record<string, any>) {
    super(message);
    this.name = 'ValidationError';
    this.timestamp = new Date().toISOString();
  }
}

export class ChunkLoadError extends Error implements AppError {
  code = 'CHUNK_LOAD_ERROR';
  retry = true;
  timestamp: string;
  
  constructor(message: string = 'Failed to load application chunk', public context?: Record<string, any>) {
    super(message);
    this.name = 'ChunkLoadError';
    this.timestamp = new Date().toISOString();
  }
}

export class ComponentError extends Error implements AppError {
  code = 'COMPONENT_ERROR';
  retry = false;
  timestamp: string;
  
  constructor(message: string = 'Component rendering failed', public context?: Record<string, any>) {
    super(message);
    this.name = 'ComponentError';
    this.timestamp = new Date().toISOString();
  }
}

// Error factory for creating specific error types
export class ErrorFactory {
  static createNetworkError(response?: Response | { status?: number; url?: string }, context?: Record<string, any>): NetworkError {
    const statusCode = response?.status;
    const message = response 
      ? `Network request failed with status ${statusCode}`
      : 'Network request failed';
    
    return new NetworkError(message, statusCode, {
      url: 'url' in (response || {}) ? response?.url : undefined,
      ...context,
    });
  }

  static createApiError(response?: Response | { status?: number; statusText?: string; config?: { url?: string } }, data?: any, context?: Record<string, any>): ApiError {
    const statusCode = response?.status;
    const statusText = 'statusText' in (response || {}) ? (response as any)?.statusText : undefined;
    const url = 'url' in (response || {}) ? (response as any)?.url : ('config' in (response || {}) ? (response as any)?.config?.url : undefined);
    const message = data?.message || statusText || 'API request failed';
    
    return new ApiError(message, statusCode, {
      url,
      data,
      ...context,
    });
  }

  static createWebSocketError(event?: Event, context?: Record<string, any>): WebSocketError {
    const message = 'WebSocket connection failed';
    
    return new WebSocketError(message, {
      event: event?.type,
      ...context,
    });
  }

  static createValidationError(field: string, value: any, rule: string): ValidationError {
    const message = `Validation failed for field '${field}': ${rule}`;
    
    return new ValidationError(message, {
      field,
      value,
      rule,
    });
  }

  static createChunkLoadError(chunkName?: string): ChunkLoadError {
    const message = chunkName 
      ? `Failed to load chunk: ${chunkName}`
      : 'Failed to load application chunk';
    
    return new ChunkLoadError(message, { chunkName });
  }
}

// Error utilities
export const isRetryableError = (error: Error): boolean => {
  if ('retry' in error) {
    return Boolean(error.retry);
  }
  
  // Check error message for retryable patterns
  const message = error.message.toLowerCase();
  return message.includes('network') || 
         message.includes('timeout') || 
         message.includes('websocket') ||
         message.includes('chunk');
};

export const getErrorSeverity = (error: Error): 'low' | 'medium' | 'high' | 'critical' => {
  if (error instanceof ValidationError) return 'low';
  if (error instanceof NetworkError || error instanceof WebSocketError) return 'medium';
  if (error instanceof ApiError) {
    const statusCode = error.statusCode;
    if (statusCode && statusCode >= 500) return 'high';
    return 'medium';
  }
  if (error instanceof ChunkLoadError || error instanceof ComponentError) return 'high';
  
  return 'critical';
};

export const formatErrorForUser = (error: Error): string => {
  if (error instanceof NetworkError) {
    return 'Unable to connect to the server. Please check your internet connection and try again.';
  }
  
  if (error instanceof WebSocketError) {
    return 'Real-time connection lost. Attempting to reconnect...';
  }
  
  if (error instanceof ApiError) {
    if (error.statusCode === 401) {
      return 'Your session has expired. Please log in again.';
    }
    if (error.statusCode === 403) {
      return 'You do not have permission to perform this action.';
    }
    if (error.statusCode === 404) {
      return 'The requested resource was not found.';
    }
    if (error.statusCode && error.statusCode >= 500) {
      return 'The server is temporarily unavailable. Please try again in a few moments.';
    }
    return 'There was a problem with your request. Please try again.';
  }
  
  if (error instanceof ValidationError) {
    return error.message;
  }
  
  if (error instanceof ChunkLoadError) {
    return 'Failed to load application resources. Please refresh the page.';
  }
  
  if (error instanceof ComponentError) {
    return 'A component has encountered an error. Some features may be unavailable.';
  }
  
  return 'An unexpected error occurred. If the problem persists, please contact support.';
};

// Error logging utility
export const logError = (error: Error, context?: Record<string, any>) => {
  const errorData = {
    name: error.name,
    message: error.message,
    stack: error.stack,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href,
    ...context,
  };

  if (process.env.NODE_ENV === 'development') {
    console.error('Error logged:', errorData);
  } else {
    // In production, send to error tracking service
    // analytics.track('error_logged', errorData);
  }
};

// Export utility object for backwards compatibility
const ErrorUtilities = {
  NetworkError,
  WebSocketError,
  ApiError,
  ValidationError,
  ChunkLoadError,
  ComponentError,
  ErrorFactory,
  isRetryableError,
  getErrorSeverity,
  formatErrorForUser,
  logError,
};

export default ErrorUtilities;