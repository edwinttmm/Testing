import { useState, useCallback } from 'react';
import { ErrorFactory, logError } from '../utils/errorTypes';

interface ErrorBoundaryHook {
  error: Error | null;
  hasError: boolean;
  captureError: (error: Error, context?: string) => void;
  clearError: () => void;
  throwError: (error: Error) => never;
}

/**
 * Custom hook for manual error boundary functionality
 * Useful for catching errors in event handlers, async operations, etc.
 */
export const useErrorBoundary = (): ErrorBoundaryHook => {
  const [error, setError] = useState<Error | null>(null);

  const captureError = useCallback((error: Error, context?: string) => {
    // Log the error
    logError(error, `useErrorBoundary ${context || ''}`);
    
    // Set the error state
    setError(error);
    
    // In development, also log to console
    if (process.env.NODE_ENV === 'development') {
      console.error('Error captured by useErrorBoundary:', { error, context });
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const throwError = useCallback((error: Error): never => {
    // This will be caught by the nearest error boundary
    throw error;
  }, []);

  return {
    error,
    hasError: error !== null,
    captureError,
    clearError,
    throwError,
  };
};

/**
 * Hook for handling async errors
 */
export const useAsyncError = () => {
  const { throwError } = useErrorBoundary();

  const catchAsyncError = useCallback((error: Error) => {
    // Transform the async error into a sync error that can be caught by error boundaries
    setTimeout(() => {
      throwError(error);
    }, 0);
  }, [throwError]);

  return { catchAsyncError };
};

/**
 * Hook for API error handling
 */
export const useApiError = () => {
  const { captureError } = useErrorBoundary();

  const handleApiError = useCallback((error: unknown, context?: string) => {
    let formattedError: Error;
    
    const errorObj = error as Record<string, unknown>;

    if (errorObj && typeof errorObj === 'object' && 'response' in errorObj) {
      // API responded with an error status
      formattedError = ErrorFactory.createApiError(
        errorObj.response as Record<string, unknown>, 
        (errorObj.response as Record<string, unknown>)?.data as Record<string, unknown>, 
        { context, originalError: error }
      );
    } else if (errorObj && typeof errorObj === 'object' && 'request' in errorObj) {
      // Network error - no response received
      formattedError = ErrorFactory.createNetworkError(
        undefined, 
        { context, originalError: error }
      );
    } else {
      // Something else went wrong
      const message = errorObj && typeof errorObj === 'object' && 'message' in errorObj 
        ? String(errorObj.message) 
        : 'Unknown API error';
      formattedError = new Error(message);
    }

    captureError(formattedError, context);
    return formattedError;
  }, [captureError]);

  return { handleApiError };
};

/**
 * Hook for WebSocket error handling
 */
export const useWebSocketError = () => {
  const { captureError } = useErrorBoundary();

  const handleWebSocketError = useCallback((event: Event, context?: string) => {
    const error = ErrorFactory.createWebSocketError('WebSocket error', { context, event });
    captureError(error, context);
    return error;
  }, [captureError]);

  return { handleWebSocketError };
};

/**
 * Hook for form validation error handling
 */
export const useValidationError = () => {
  const { captureError } = useErrorBoundary();

  const handleValidationError = useCallback((field: string, value: unknown, rule: string) => {
    const error = ErrorFactory.createValidationError(`Validation error: ${field}`, { value, rule });
    captureError(error, `validation-${field}`);
    return error;
  }, [captureError]);

  return { handleValidationError };
};

export default useErrorBoundary;