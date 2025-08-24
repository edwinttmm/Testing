/**
 * Global Error Handler for Unhandled Promise Rejections
 * Centralizes error handling to prevent [object Object] console spam
 */

// Global error serialization utility
export const serializeError = (error: unknown): string => {
  try {
    if (error === null) return 'null';
    if (error === undefined) return 'undefined';
    if (typeof error === 'string') return error;
    if (typeof error === 'number' || typeof error === 'boolean') return String(error);
    
    // Handle Error objects
    if (error instanceof Error) {
      return `${error.name}: ${error.message}`;
    }
    
    // Handle objects with message property
    if (error && typeof error === 'object' && 'message' in error && error.message) {
      return String(error.message);
    }
    
    // Handle network errors
    if (error && typeof error === 'object') {
      if (('code' in error && error.code === 'NETWORK_ERROR') || ('name' in error && error.name === 'NetworkError')) {
        return 'Network connection failed - backend may be offline';
      }
      if ('status' in error && error.status) {
        const statusText = 'statusText' in error ? (error.statusText || 'Unknown error') : 'Unknown error';
        return `HTTP ${error.status}: ${statusText}`;
      }
    }
    
    // Handle objects with toString method
    if (error && typeof error.toString === 'function') {
      const str = error.toString();
      if (str !== '[object Object]') {
        return str;
      }
    }
    
    // Fallback to JSON serialization
    return JSON.stringify(error, Object.getOwnPropertyNames(error), 2);
  } catch (serializationError) {
    return `[Unserializable Error: ${typeof error}]`;
  }
};

// Global promise rejection handler
export const setupGlobalErrorHandling = () => {
  // Prevent duplicate handlers
  if ((window as any).__globalErrorHandlerSetup) {
    return;
  }

  // Handle unhandled promise rejections
  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    const errorMsg = serializeError(event.reason);
    console.warn('🚨 Unhandled Promise Rejection:', errorMsg);
    
    // Log full error details in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Full error details:', event.reason);
    }
    
    // Prevent default browser behavior
    event.preventDefault();
    
    // Send to error reporting service if available
    if ((window as any).errorReporter) {
      (window as any).errorReporter.reportError({
        type: 'unhandled_promise_rejection',
        message: errorMsg,
        reason: event.reason,
        timestamp: new Date().toISOString()
      });
    }
  });

  // Handle global JavaScript errors
  window.addEventListener('error', (event: ErrorEvent) => {
    const errorMsg = serializeError(event.error);
    console.warn('🚨 Global JavaScript Error:', errorMsg);
    
    if (process.env.NODE_ENV === 'development') {
      console.error('Full error details:', event.error);
    }
  });

  // Mark as setup to prevent duplicates
  (window as any).__globalErrorHandlerSetup = true;
  
  console.info('✅ Global error handling initialized');
};

// Export for use in components
const globalErrorHandler = { serializeError, setupGlobalErrorHandling };
export default globalErrorHandler;