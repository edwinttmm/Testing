import { useCallback, useMemo, useRef, useEffect } from 'react';
import { useErrorNotification } from '../components/ui/ErrorNotification';
import { ErrorTransformer, ErrorCallback, RetryCallback } from '../types/common';

export interface ErrorHandlerOptions {
  /**
   * Whether to show notifications for errors
   */
  showNotifications?: boolean;
  
  /**
   * Custom error message prefix
   */
  messagePrefix?: string;
  
  /**
   * Whether to log errors to console
   */
  logErrors?: boolean;
  
  /**
   * Maximum number of retry attempts
   */
  maxRetries?: number;
  
  /**
   * Retry delay in milliseconds
   */
  retryDelay?: number;
  
  /**
   * Whether to use exponential backoff for retries
   */
  exponentialBackoff?: boolean;
  
  /**
   * Custom error transformer
   */
  transformError?: ErrorTransformer;
}

export interface RetryableFunction<T> {
  (): Promise<T>;
}

export interface UseErrorHandlerReturn {
  /**
   * Handle an error with notifications and logging
   */
  handleError: (error: Error | unknown, context?: string) => void;
  
  /**
   * Execute a function with automatic error handling
   */
  withErrorHandling: <T>(
    fn: () => Promise<T>,
    options?: {
      context?: string;
      showNotification?: boolean;
      onError?: (error: Error | unknown) => void;
    }
  ) => Promise<T | null>;
  
  /**
   * Execute a function with retry logic and error handling
   */
  withRetry: <T>(
    fn: RetryableFunction<T>,
    options?: {
      context?: string;
      maxRetries?: number;
      retryDelay?: number;
      exponentialBackoff?: boolean;
      onRetry?: RetryCallback;
      onError?: ErrorCallback;
    }
  ) => Promise<T | null>;
  
  /**
   * Create an error handler for a specific context
   */
  createHandler: (context: string) => (error: Error | unknown) => void;
  
  /**
   * Get user-friendly error message
   */
  getErrorMessage: (error: Error | unknown) => string;
}

const defaultOptions: ErrorHandlerOptions = {
  showNotifications: true,
  logErrors: true,
  maxRetries: 3,
  retryDelay: 1000,
  exponentialBackoff: true,
};

export const useErrorHandler = (options: ErrorHandlerOptions = {}): UseErrorHandlerReturn => {
  const opts = useMemo(() => ({ ...defaultOptions, ...options }), [options]);
  const { showError } = useErrorNotification();
  const abortControllerRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    const currentController = abortControllerRef.current;
    return () => {
      if (currentController) {
        currentController.abort();
      }
    };
  }, []);

  const getErrorMessage = useCallback((error: Error | unknown): string => {
    if (opts.transformError) {
      return opts.transformError(error as Error);
    }

    // Type guard for error objects
    const isErrorLike = (err: unknown): err is { 
      message?: string; 
      response?: { 
        data?: { message?: string; detail?: string }; 
        status?: number; 
      };
      code?: string;
    } => {
      return typeof err === 'object' && err !== null;
    };

    // Handle different error types
    if (typeof error === 'string') {
      return error;
    }

    const errorObj = isErrorLike(error) ? error : {};

    if (errorObj.message) {
      return errorObj.message;
    }

    if (errorObj.response?.data?.message) {
      return errorObj.response.data.message;
    }

    if (errorObj.response?.data?.detail) {
      return errorObj.response.data.detail;
    }

    if (errorObj.response?.status) {
      switch (errorObj.response.status) {
        case 400:
          return 'Invalid request. Please check your input and try again.';
        case 401:
          return 'Authentication required. Please sign in and try again.';
        case 403:
          return 'You don\'t have permission to perform this action.';
        case 404:
          return 'The requested resource was not found.';
        case 405:
          return 'This operation is not supported.';
        case 408:
          return 'The request timed out. Please try again.';
        case 409:
          return 'There was a conflict with the current state. Please refresh and try again.';
        case 429:
          return 'Too many requests. Please wait a moment and try again.';
        case 500:
          return 'An internal server error occurred. Please try again later.';
        case 502:
          return 'Bad gateway. The server is temporarily unavailable.';
        case 503:
          return 'Service temporarily unavailable. Please try again in a few moments.';
        case 504:
          return 'Gateway timeout. Please try again later.';
        default:
          return `Server error (${errorObj.response.status}). Please try again or contact support.`;
      }
    }

    // Network errors
    if (errorObj.code === 'ERR_NETWORK' || errorObj.code === 'NETWORK_ERROR') {
      return 'Network error. Please check your internet connection and try again.';
    }

    if (errorObj.code === 'ERR_CANCELED') {
      return 'The operation was cancelled.';
    }

    if (errorObj.code === 'ECONNABORTED' || errorObj.code === 'TIMEOUT_ERROR') {
      return 'The request timed out. Please try again.';
    }

    return 'An unexpected error occurred. Please try again or contact support.';
  }, [opts]);

  const handleError = useCallback((error: Error | unknown, context?: string) => {
    const message = getErrorMessage(error);
    const fullMessage = opts.messagePrefix 
      ? `${opts.messagePrefix}: ${message}`
      : message;

    if (opts.logErrors) {
      // This is intentionally using console.error for error tracking - will be replaced with proper logger
      // console.error(`Error ${context ? `in ${context}` : ''}:`, error);
    }

    if (opts.showNotifications) {
      showError(fullMessage, {
        title: context ? `Error in ${context}` : 'Error',
        details: (error instanceof Error && error.stack) ? error.stack : String(error),
      });
    }
  }, [opts, showError, getErrorMessage]);

  const withErrorHandling = useCallback(async <T>(
    fn: () => Promise<T>,
    options: {
      context?: string;
      showNotification?: boolean;
      onError?: ErrorCallback;
    } = {}
  ): Promise<T | null> => {
    try {
      return await fn();
    } catch (error) {
      if (options.onError) {
        options.onError(error as Error);
      } else if (options.showNotification !== false) {
        handleError(error, options.context);
      }
      return null;
    }
  }, [handleError]);

  const withRetry = useCallback(async <T>(
    fn: RetryableFunction<T>,
    options: {
      context?: string;
      maxRetries?: number;
      retryDelay?: number;
      exponentialBackoff?: boolean;
      onRetry?: RetryCallback;
      onError?: ErrorCallback;
    } = {}
  ): Promise<T | null> => {
    const maxRetries = options.maxRetries ?? opts.maxRetries!;
    const baseDelay = options.retryDelay ?? opts.retryDelay!;
    const exponentialBackoff = options.exponentialBackoff ?? opts.exponentialBackoff!;

    let lastError: Error | unknown;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;

        // Don't retry on the last attempt
        if (attempt === maxRetries) {
          break;
        }

        // Check if error is retryable
        if (!isRetryableError(error)) {
          break;
        }

        // Call retry callback if provided
        if (options.onRetry) {
          options.onRetry(attempt + 1, error as Error);
        }

        // Calculate delay with optional exponential backoff
        const delay = exponentialBackoff 
          ? baseDelay * Math.pow(2, attempt)
          : baseDelay;

        // Wait before retrying
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }

    // All retries failed, handle the error
    if (options.onError) {
      options.onError(lastError as Error);
    } else {
      handleError(lastError, options.context);
    }

    return null;
  }, [opts.maxRetries, opts.retryDelay, opts.exponentialBackoff, handleError]);

  const createHandler = useCallback((context: string) => {
    return (error: Error | unknown) => handleError(error, context);
  }, [handleError]);

  return {
    handleError,
    withErrorHandling,
    withRetry,
    createHandler,
    getErrorMessage,
  };
};

/**
 * Determines if an error is retryable
 */
function isRetryableError(error: Error | unknown): boolean {
  // Type guard for error objects
  const isErrorLike = (err: unknown): err is { code?: string; response?: { status?: number } } => {
    return typeof err === 'object' && err !== null;
  };
  // Network errors are retryable
  if ((isErrorLike(error) && error.code === 'ERR_NETWORK') || (isErrorLike(error) && error.code === 'NETWORK_ERROR')) {
    return true;
  }

  // Timeout errors are retryable
  if ((isErrorLike(error) && error.code === 'ECONNABORTED') || (isErrorLike(error) && error.code === 'TIMEOUT_ERROR')) {
    return true;
  }

  // HTTP status codes that are retryable
  if (isErrorLike(error) && error.response?.status) {
    const status = error.response.status;
    
    // Server errors (5xx) are retryable
    if (status >= 500) {
      return true;
    }
    
    // Some client errors are retryable
    if (status === 408 || status === 429) { // Request Timeout, Too Many Requests
      return true;
    }
    
    return false;
  }

  // Cancelled requests are not retryable
  if (isErrorLike(error) && error.code === 'ERR_CANCELED') {
    return false;
  }

  // Default to retryable for unknown errors
  return true;
}

export default useErrorHandler;