/**
 * Promise handling utilities for better error management
 */

export interface PromiseOptions {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
  onRetry?: (attempt: number, error: any) => void;
  onTimeout?: () => void;
  abortSignal?: AbortSignal;
}

/**
 * Wraps a promise with timeout functionality
 */
export function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  timeoutMessage = 'Operation timed out'
): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs)
    ),
  ]);
}

/**
 * Wraps a promise with retry functionality
 */
export async function withRetries<T>(
  promiseFactory: () => Promise<T>,
  options: PromiseOptions = {}
): Promise<T> {
  const { retries = 3, retryDelay = 1000, onRetry } = options;
  
  let lastError: any;
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await promiseFactory();
    } catch (error) {
      lastError = error;
      
      if (attempt === retries) {
        break;
      }
      
      if (onRetry) {
        onRetry(attempt + 1, error);
      }
      
      await new Promise(resolve => setTimeout(resolve, retryDelay));
    }
  }
  
  throw lastError;
}

/**
 * Combines timeout and retry functionality
 */
export async function withTimeoutAndRetries<T>(
  promiseFactory: () => Promise<T>,
  options: PromiseOptions = {}
): Promise<T> {
  const { timeout = 30000, ...retryOptions } = options;
  
  return withRetries(
    () => withTimeout(promiseFactory(), timeout),
    retryOptions
  );
}

/**
 * Creates a promise that can be cancelled
 */
export function makeCancellable<T>(promise: Promise<T>): {
  promise: Promise<T>;
  cancel: () => void;
} {
  let cancelled = false;
  
  const cancellablePromise = new Promise<T>((resolve, reject) => {
    promise.then(
      (value) => {
        if (!cancelled) {
          resolve(value);
        }
      },
      (error) => {
        if (!cancelled) {
          reject(error);
        }
      }
    );
  });
  
  return {
    promise: cancellablePromise,
    cancel: () => {
      cancelled = true;
    },
  };
}

/**
 * Executes promises in batches with concurrency limit
 */
export async function batchExecute<T, R>(
  items: T[],
  executor: (item: T) => Promise<R>,
  options: {
    batchSize?: number;
    onBatchComplete?: (results: R[], batch: T[]) => void;
    onError?: (error: any, item: T) => R | void;
  } = {}
): Promise<R[]> {
  const { batchSize = 5, onBatchComplete, onError } = options;
  const results: R[] = [];
  
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    
    const batchPromises = batch.map(async (item) => {
      try {
        return await executor(item);
      } catch (error) {
        if (onError) {
          const fallback = onError(error, item);
          if (fallback !== undefined) {
            return fallback;
          }
        }
        throw error;
      }
    });
    
    const batchResults = await Promise.allSettled(batchPromises);
    const successfulResults = batchResults
      .filter(result => result.status === 'fulfilled')
      .map(result => (result as PromiseFulfilledResult<R>).value);
    
    results.push(...successfulResults);
    
    if (onBatchComplete) {
      onBatchComplete(successfulResults, batch);
    }
  }
  
  return results;
}

/**
 * Safe promise wrapper that never throws
 */
export async function safePromise<T, E = Error>(
  promise: Promise<T>
): Promise<{ success: true; data: T } | { success: false; error: E }> {
  try {
    const data = await promise;
    return { success: true, data };
  } catch (error) {
    return { success: false, error: error as E };
  }
}

/**
 * Promise-based delay function
 */
export function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    
    const timeoutId = setTimeout(() => resolve(), ms);
    
    signal?.addEventListener('abort', () => {
      clearTimeout(timeoutId);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

/**
 * Executes an async function with exponential backoff retry
 */
export async function withExponentialBackoff<T>(
  fn: () => Promise<T>,
  options: {
    maxRetries?: number;
    initialDelay?: number;
    maxDelay?: number;
    factor?: number;
    onRetry?: (attempt: number, delay: number, error: any) => void;
  } = {}
): Promise<T> {
  const {
    maxRetries = 3,
    initialDelay = 1000,
    maxDelay = 10000,
    factor = 2,
    onRetry
  } = options;
  
  let lastError: any;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      if (attempt === maxRetries) {
        break;
      }
      
      const delayTime = Math.min(
        initialDelay * Math.pow(factor, attempt),
        maxDelay
      );
      
      if (onRetry) {
        onRetry(attempt + 1, delayTime, error);
      }
      
      await delay(delayTime);
    }
  }
  
  throw lastError;
}

/**
 * Global unhandled promise rejection handler
 */
export function setupGlobalErrorHandling(onUnhandledRejection?: (error: any) => void) {
  // Handle unhandled promise rejections
  if (typeof window !== 'undefined') {
    window.addEventListener('unhandledrejection', (event) => {
      console.error('Unhandled promise rejection:', event.reason);
      
      if (onUnhandledRejection) {
        onUnhandledRejection(event.reason);
      }
      
      // Prevent the default browser behavior
      event.preventDefault();
    });
    
    // Handle errors in event handlers
    window.addEventListener('error', (event) => {
      console.error('Global error:', event.error);
      
      if (onUnhandledRejection) {
        onUnhandledRejection(event.error);
      }
    });
  }
}

export default {
  withTimeout,
  withRetries,
  withTimeoutAndRetries,
  makeCancellable,
  batchExecute,
  safePromise,
  delay,
  withExponentialBackoff,
  setupGlobalErrorHandling,
};