/**
 * Upload-specific promise handling utilities
 * Prevents unhandled promise rejections in upload workflows
 */

export interface UploadPromiseOptions {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
  onProgress?: (progress: number) => void;
  onError?: (error: Error) => void;
}

export class UploadTimeoutError extends Error {
  constructor(timeout: number) {
    super(`Upload operation timed out after ${timeout}ms`);
    this.name = 'UploadTimeoutError';
  }
}

export class UploadCancelledError extends Error {
  constructor() {
    super('Upload operation was cancelled');
    this.name = 'UploadCancelledError';
  }
}

/**
 * Wraps upload promises with timeout, retry logic, and proper error handling
 */
export const withUploadPromiseHandling = async <T>(
  promiseFactory: () => Promise<T>,
  options: UploadPromiseOptions = {}
): Promise<T> => {
  const {
    timeout = 30000,
    retries = 3,
    retryDelay = 1000,
    onProgress,
    onError,
  } = options;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const timeoutPromise = new Promise<never>((_, reject) => {
        const timeoutId = setTimeout(() => {
          reject(new UploadTimeoutError(timeout));
        }, timeout);

        // Clear timeout if the main promise resolves first
        return timeoutId;
      });

      const mainPromise = promiseFactory();

      // Race between the main promise and timeout
      const result = await Promise.race([mainPromise, timeoutPromise]);

      return result;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      console.warn(`Upload attempt ${attempt + 1} failed:`, lastError);

      // Don't retry for certain error types
      if (
        lastError instanceof UploadCancelledError ||
        lastError.name === 'AbortError' ||
        lastError.message.includes('cancelled')
      ) {
        throw lastError;
      }

      onError?.(lastError);

      // If this is the last attempt, throw the error
      if (attempt === retries) {
        break;
      }

      // Wait before retrying with exponential backoff
      const delay = retryDelay * Math.pow(2, attempt);
      await new Promise(resolve => setTimeout(resolve, delay));

      onProgress?.(0); // Reset progress on retry
    }
  }

  throw lastError || new Error('Upload failed after all retry attempts');
};

/**
 * Creates a cancellable upload promise
 */
export const createCancellableUpload = <T>(
  promiseFactory: (signal: AbortSignal) => Promise<T>
): { promise: Promise<T>; cancel: () => void } => {
  const abortController = new AbortController();

  const promise = promiseFactory(abortController.signal).catch(error => {
    if (error.name === 'AbortError') {
      throw new UploadCancelledError();
    }
    throw error;
  });

  const cancel = () => {
    abortController.abort();
  };

  return { promise, cancel };
};

/**
 * Batches multiple upload promises with proper error handling
 */
export const batchUploadPromises = async <T>(
  promiseFactories: Array<() => Promise<T>>,
  options: UploadPromiseOptions & { concurrency?: number } = {}
): Promise<PromiseSettledResult<T>[]> => {
  const { concurrency = 3 } = options;

  // Process uploads in batches to avoid overwhelming the system
  const results: PromiseSettledResult<T>[] = [];

  for (let i = 0; i < promiseFactories.length; i += concurrency) {
    const batch = promiseFactories.slice(i, i + concurrency);

    const batchPromises = batch.map(factory =>
      withUploadPromiseHandling(factory, options)
    );

    const batchResults = await Promise.allSettled(batchPromises);
    results.push(...batchResults);
  }

  return results;
};

/**
 * Upload progress tracker with promise handling
 */
export class UploadProgressTracker {
  private progressMap = new Map<string, number>();
  private completedUploads = new Set<string>();
  private failedUploads = new Set<string>();

  updateProgress(uploadId: string, progress: number): void {
    this.progressMap.set(uploadId, progress);

    if (progress >= 100) {
      this.completedUploads.add(uploadId);
    }
  }

  markFailed(uploadId: string): void {
    this.failedUploads.add(uploadId);
  }

  getOverallProgress(): number {
    if (this.progressMap.size === 0) return 0;

    const totalProgress = Array.from(this.progressMap.values()).reduce(
      (sum, progress) => sum + progress,
      0
    );

    return Math.round(totalProgress / this.progressMap.size);
  }

  getCompletedCount(): number {
    return this.completedUploads.size;
  }

  getFailedCount(): number {
    return this.failedUploads.size;
  }

  getTotalCount(): number {
    return this.progressMap.size;
  }

  clear(): void {
    this.progressMap.clear();
    this.completedUploads.clear();
    this.failedUploads.clear();
  }
}

/**
 * Global upload error handler for unhandled promise rejections
 */
let isGlobalHandlerSetup = false;

export const setupGlobalUploadErrorHandler = (): void => {
  if (isGlobalHandlerSetup) return;

  // Handle unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    if (
      event.reason &&
      (event.reason.message?.includes('upload') ||
        event.reason.name === 'UploadTimeoutError' ||
        event.reason.name === 'UploadCancelledError')
    ) {
      console.error('Unhandled upload promise rejection:', event.reason);
      
      // Prevent the error from appearing in console as unhandled
      event.preventDefault();
      
      // You could also send this to your error reporting service
      // Example: errorReportingService.captureException(event.reason);
    }
  });

  isGlobalHandlerSetup = true;
};

export default {
  withUploadPromiseHandling,
  createCancellableUpload,
  batchUploadPromises,
  UploadProgressTracker,
  setupGlobalUploadErrorHandler,
  UploadTimeoutError,
  UploadCancelledError,
};