import React, { useEffect } from 'react';
import { Snackbar, Alert, AlertTitle } from '@mui/material';

interface GlobalErrorHandlerProps {
  onError?: (error: Error, source: string) => void;
}

// Global error handler component to catch unhandled promise rejections
const GlobalErrorHandler: React.FC<GlobalErrorHandlerProps> = ({ onError }) => {
  const [errorQueue, setErrorQueue] = React.useState<Array<{
    id: string;
    message: string;
    source: string;
    timestamp: number;
  }>>([]);

  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('🚨 Unhandled Promise Rejection:', event.reason);
      
      // Prevent default browser behavior
      event.preventDefault();
      
      // Create error entry
      const errorEntry = {
        id: `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        message: serializeError(event.reason),
        source: 'promise-rejection',
        timestamp: Date.now()
      };

      // Add to error queue
      setErrorQueue(prev => [...prev.slice(-4), errorEntry]); // Keep only last 5 errors

      // Call custom error handler
      if (onError) {
        const syntheticError = new Error(`Unhandled Promise Rejection: ${errorEntry.message}`);
        (syntheticError as Error & { originalReason?: unknown }).originalReason = event.reason;
        onError(syntheticError, 'promise-rejection');
      }
    };

    const handleGlobalError = (event: ErrorEvent) => {
      console.error('🚨 Global JavaScript Error:', event.error);
      
      const errorEntry = {
        id: `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        message: event.error?.message || event.message || 'Unknown error',
        source: 'global-error',
        timestamp: Date.now()
      };

      setErrorQueue(prev => [...prev.slice(-4), errorEntry]);

      if (onError && event.error) {
        onError(event.error, 'global-error');
      }
    };

    // Add global error listeners
    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleGlobalError);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleGlobalError);
    };
  }, [onError]);

  const serializeError = (error: unknown): string => {
    try {
      if (error === null) return 'null';
      if (error === undefined) return 'undefined';
      if (typeof error === 'string') return error;
      if (typeof error === 'number' || typeof error === 'boolean') return String(error);
      
      if (error instanceof Error) {
        return `${error.name}: ${error.message}`;
      }
      
      if (error && typeof error === 'object' && 'message' in error) {
        return String((error as { message: unknown }).message);
      }
      
      if (error && typeof error.toString === 'function') {
        const str = error.toString();
        if (str !== '[object Object]') {
          return str;
        }
      }
      
      return JSON.stringify(error, null, 2);
    } catch (serializationError) {
      return `[Unserializable Error: ${typeof error}]`;
    }
  };

  const dismissError = (errorId: string) => {
    setErrorQueue(prev => prev.filter(error => error.id !== errorId));
  };

  return (
    <>
      {errorQueue.map((error) => (
        <Snackbar
          key={error.id}
          open={true}
          autoHideDuration={10000}
          onClose={() => dismissError(error.id)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert 
            severity="error"
            onClose={() => dismissError(error.id)}
            sx={{ maxWidth: 400 }}
          >
            <AlertTitle>Unhandled Error</AlertTitle>
            {error.message}
            <br />
            <small>Source: {error.source} | {new Date(error.timestamp).toLocaleTimeString()}</small>
          </Alert>
        </Snackbar>
      ))}
    </>
  );
};

export default GlobalErrorHandler;