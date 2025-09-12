// ReactNode import removed - not used in this file
// import { ReactNode } from 'react';

/**
 * Comprehensive TypeScript interfaces for error handling
 * Replaces all 'any' types with proper type safety
 */

// React Error Boundary Types
export interface ErrorInfo {
  componentStack: string;
  errorBoundary?: string;
  errorBoundaryStack?: string;
}

export interface ErrorBoundaryError extends Error {
  digest?: string;
}

export interface ErrorBoundaryContext {
  level: 'app' | 'page' | 'component';
  context: string;
  metadata?: Record<string, unknown>;
}

// API Error Types
export interface ApiErrorResponse {
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, unknown>;
  timestamp?: string;
}

export interface NetworkError extends Error {
  code?: string;
  response?: {
    status: number;
    statusText: string;
    data?: unknown;
  };
  request?: unknown;
  config?: Record<string, unknown>;
}

// API Response Types
export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services?: {
    database?: 'connected' | 'disconnected';
    ml?: 'available' | 'unavailable';
  };
  version?: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  description?: string;
  cameraModel: string;
  cameraView: string;
  signalType: string;
  createdAt: string;
  updatedAt: string;
  videoCount?: number;
  testsCount?: number;
  accuracy?: number;
  status?: 'active' | 'archived' | 'draft';
}

export interface CreateProjectRequest {
  name: string;
  description: string;
  cameraModel: string;
  cameraView: string;
  signalType: string;
}

export interface CreateProjectResponse extends ProjectResponse {}

// Error Handler Types
export interface ErrorHandlerOptions {
  level?: 'error' | 'warn' | 'info';
  context?: string;
  metadata?: Record<string, unknown>;
  shouldReport?: boolean;
  shouldNotify?: boolean;
}

export interface GlobalErrorContext {
  source: 'unhandledRejection' | 'error' | 'beforeunload' | 'component';
  timestamp: string;
  userAgent?: string;
  url?: string;
}

// Logging Types
export interface LogContext {
  action: string;
  metadata?: Record<string, unknown>;
  timestamp?: string;
  level?: 'debug' | 'info' | 'warn' | 'error';
}

// Component Error Types
export interface ComponentErrorState {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  retryCount?: number;
  lastError?: string;
}

// Utility type for safe error casting (fixed for exactOptionalPropertyTypes)
export type SafeError = {
  message: string;
  name?: string | undefined;
  stack?: string | undefined;
  code?: string | number | undefined;
  response?: {
    status?: number | undefined;
    statusText?: string | undefined;
    data?: unknown;
  } | undefined;
};

// Type guards for error handling
export const isNetworkError = (error: unknown): error is NetworkError => {
  return error instanceof Error && (
    error.name === 'NetworkError' ||
    (error.name === 'TypeError' && error.message.includes('fetch')) ||
    'response' in error ||
    'request' in error
  );
};

export const isApiErrorResponse = (error: unknown): error is ApiErrorResponse => {
  return typeof error === 'object' && 
         error !== null && 
         'message' in error &&
         typeof (error as ApiErrorResponse).message === 'string';
};

export const isSafeError = (error: unknown): error is SafeError => {
  return typeof error === 'object' && 
         error !== null && 
         'message' in error &&
         typeof (error as SafeError).message === 'string';
};

// Error factory for consistent error creation
export class TypedErrorFactory {
  static createApiError(
    message: string, 
    status?: number, 
    details?: Record<string, unknown>
  ): NetworkError {
    const error = new Error(message) as NetworkError;
    error.name = 'ApiError';
    if (status !== undefined) {
      error.response = { status, statusText: '', data: details };
    }
    return error;
  }

  static createNetworkError(message: string = 'Network request failed'): NetworkError {
    const error = new Error(message) as NetworkError;
    error.name = 'NetworkError';
    error.code = 'NETWORK_ERROR';
    return error;
  }

  static createValidationError(
    message: string, 
    field?: string, 
    value?: unknown
  ): Error & { field?: string; value?: unknown } {
    const error = new Error(message) as Error & { field?: string; value?: unknown };
    error.name = 'ValidationError';
    if (field) error.field = field;
    if (value !== undefined) error.value = value;
    return error;
  }

  static fromUnknown(error: unknown, fallbackMessage = 'An unknown error occurred'): SafeError {
    if (error instanceof Error) {
      return {
        message: error.message,
        name: error.name,
        stack: error.stack,
        code: 'code' in error ? (error as Record<string, unknown>).code as string | number | undefined : undefined,
        response: 'response' in error ? (error as Record<string, unknown>).response as SafeError['response'] : undefined
      };
    }
    
    if (typeof error === 'string') {
      return { message: error };
    }
    
    if (typeof error === 'object' && error !== null && 'message' in error) {
      const safeError = error as Record<string, unknown>;
      return {
        message: typeof safeError.message === 'string' ? safeError.message : fallbackMessage,
        name: typeof safeError.name === 'string' ? safeError.name : 'UnknownError'
      };
    }
    
    return { message: fallbackMessage, name: 'UnknownError' };
  }
}