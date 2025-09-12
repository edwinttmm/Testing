import React from 'react';
import ErrorBoundary, { ErrorType } from './ErrorBoundary';
import { useErrorNotification } from './ErrorNotification';

interface IntegratedErrorHandlerProps {
  children: React.ReactNode;
  level?: 'app' | 'page' | 'component';
  context?: string;
  showErrorDetails?: boolean;
  maxRetries?: number;
}

const ErrorHandler: React.FC<IntegratedErrorHandlerProps> = ({
  children,
  level = 'component',
  context,
  showErrorDetails = process.env.NODE_ENV === 'development',
  maxRetries = 3,
}) => {
  const { showError } = useErrorNotification();

  const handleError = (error: Error, errorInfo: React.ErrorInfo, _errorType: ErrorType) => {
    // Show user-friendly notification
    if (showErrorDetails) {
      showError(error.message, {
        title: context ? `Error in ${context}` : 'Application Error',
        details: `${error.stack}\n\nComponent Stack:${errorInfo.componentStack}`,
        persistent: level === 'app', // App-level errors persist
      });
    } else {
      showError(error.message, {
        title: context ? `Error in ${context}` : 'Application Error',
        persistent: level === 'app', // App-level errors persist
      });
    }

    // Log for debugging
    console.error(`[${level.toUpperCase()}] Error in ${context || 'component'}:`, {
      error,
      errorInfo,
    });

    // In production, send to error tracking service
    if (process.env.NODE_ENV === 'production') {
      // TODO: Send to error tracking service like Sentry
      console.error('Production error:', { error, errorInfo, level, context });
    }
  };

  const errorBoundaryProps: Record<string, unknown> = {
    onError: handleError,
    maxRetries,
    level,
    context,
  };

  if (context) {
    errorBoundaryProps.resetKeys = [context];
  }

  return (
    <ErrorBoundary {...errorBoundaryProps}>
      {children}
    </ErrorBoundary>
  );
};

export const IntegratedErrorHandler: React.FC<IntegratedErrorHandlerProps> = (props) => {
  return <ErrorHandler {...props} />;
};

export default IntegratedErrorHandler;