import { useCallback, useRef, useEffect } from 'react';

interface UploadErrorHandlerOptions {
  maxRetries?: number;
  retryDelay?: number;
  onError?: (error: Error) => void;
  onRetryExhausted?: (error: Error) => void;
}

interface UploadErrorHandler {
  handleError: (error: Error, context?: string) => void;
  handlePromiseRejection: <T>(promise: Promise<T>, context?: string) => Promise<T>;
  clearRetryState: () => void;
  getRetryCount: (context: string) => number;
}

export const useUploadErrorHandler = (
  options: UploadErrorHandlerOptions = {}
): UploadErrorHandler => {
  const {
    maxRetries = 3,
    retryDelay = 1000,
    onError,
    onRetryExhausted,
  } = options;

  const retryCountRef = useRef<Map<string, number>>(new Map());
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const handleError = useCallback((error: Error, context = 'general') => {
    if (!isMountedRef.current) return;

    console.error(`Upload error in ${context}:`, error);

    const currentRetries = retryCountRef.current.get(context) || 0;

    if (currentRetries >= maxRetries) {
      console.error(`Max retries (${maxRetries}) reached for ${context}`);
      onRetryExhausted?.(error);
      return;
    }

    retryCountRef.current.set(context, currentRetries + 1);
    onError?.(error);
  }, [maxRetries, onError, onRetryExhausted]);

  const handlePromiseRejection = useCallback(async <T>(
    promise: Promise<T>,
    context = 'promise'
  ): Promise<T> => {
    if (!isMountedRef.current) {
      return Promise.reject(new Error('Component unmounted'));
    }

    try {
      const result = await promise;
      
      // Clear retry count on success
      retryCountRef.current.delete(context);
      
      return result;
    } catch (error) {
      const errorObj = error instanceof Error ? error : new Error(String(error));
      handleError(errorObj, context);
      
      const currentRetries = retryCountRef.current.get(context) || 0;
      
      if (currentRetries < maxRetries && isMountedRef.current) {
        // Retry with exponential backoff
        const delay = retryDelay * Math.pow(2, currentRetries - 1);
        
        await new Promise(resolve => setTimeout(resolve, delay));
        
        if (!isMountedRef.current) {
          throw new Error('Component unmounted during retry');
        }
        
        return handlePromiseRejection(promise, context);
      }
      
      throw errorObj;
    }
  }, [handleError, maxRetries, retryDelay]);

  const clearRetryState = useCallback(() => {
    retryCountRef.current.clear();
  }, []);

  const getRetryCount = useCallback((context: string): number => {
    return retryCountRef.current.get(context) || 0;
  }, []);

  return {
    handleError,
    handlePromiseRejection,
    clearRetryState,
    getRetryCount,
  };
};

export default useUploadErrorHandler;