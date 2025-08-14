// Simplified Error type definitions for build compatibility

export interface AppError extends Error {
  code?: string;
  statusCode?: number;
  context?: Record<string, any>;
  timestamp?: string;
  retry?: boolean;
}

export class NetworkError extends Error {
  code = 'NETWORK_ERROR';
  retry = true;
  timestamp: string;
  statusCode: number;
  context: Record<string, any>;
  
  constructor(message = 'Network request failed', statusCode = 0, context = {}) {
    super(message);
    this.name = 'NetworkError';
    this.timestamp = new Date().toISOString();
    this.statusCode = statusCode;
    this.context = context;
  }
}

export class WebSocketError extends Error {
  code = 'WEBSOCKET_ERROR';
  retry = true;
  timestamp: string;
  statusCode: number;
  context: Record<string, any>;
  
  constructor(message = 'WebSocket connection failed', statusCode = 0, context = {}) {
    super(message);
    this.name = 'WebSocketError';
    this.timestamp = new Date().toISOString();
    this.statusCode = statusCode;
    this.context = context;
  }
}

export class ValidationError extends Error {
  code = 'VALIDATION_ERROR';
  retry = false;
  timestamp: string;
  statusCode: number;
  context: Record<string, any>;
  
  constructor(message = 'Validation failed', statusCode = 0, context = {}) {
    super(message);
    this.name = 'ValidationError';
    this.timestamp = new Date().toISOString();
    this.statusCode = statusCode;
    this.context = context;
  }
}

// Simplified error factory
export function createAppError(type: string, message: string, statusCode = 0, context = {}): AppError {
  switch (type) {
    case 'NETWORK_ERROR':
      return new NetworkError(message, statusCode, context);
    case 'WEBSOCKET_ERROR':
      return new WebSocketError(message, statusCode, context);
    case 'VALIDATION_ERROR':
      return new ValidationError(message, statusCode, context);
    default:
      const error = new Error(message) as AppError;
      error.code = type;
      error.statusCode = statusCode;
      error.context = context;
      error.timestamp = new Date().toISOString();
      return error;
  }
}

// Legacy export for compatibility
export const ErrorFactory = { 
  createAppError,
  createNetworkError: (message?: string, context = {}) => new NetworkError(message, 0, context),
  createApiError: (response: any, data: any, context = {}) => new NetworkError('API Error', response?.status || 0, { ...context, response, data }),
  createValidationError: (message?: string, context = {}) => new ValidationError(message, 0, context),
  createWebSocketError: (message?: string, context = {}) => new WebSocketError(message, 0, context)
};

// Simple logging utility
export const logError = (error: Error, context = '') => {
  console.error(`[Error ${context}]:`, error.message, error.stack);
};

export default { NetworkError, WebSocketError, ValidationError, createAppError, ErrorFactory, logError };