import React, { Component, ReactNode } from 'react';
import {
  Box,
  Typography,
  Button,
  Alert,
  AlertTitle,
  Paper,
  Stack,
  Collapse,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  BugReport as BugReportIcon,
} from '@mui/icons-material';

// Error types for better categorization
export enum ErrorType {
  NETWORK = 'network',
  WEBSOCKET = 'websocket',
  API = 'api',
  COMPONENT = 'component',
  CHUNK_LOAD = 'chunk_load',
  RENDER = 'render',
  UNKNOWN = 'unknown',
}

export interface ErrorInfo {
  componentStack: string;
  errorBoundary?: string;
  errorBoundaryStack?: string;
}

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorType: ErrorType;
  errorId: string;
  retryCount: number;
  showDetails: boolean;
}

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo, errorType: ErrorType) => void;
  enableRetry?: boolean;
  maxRetries?: number;
  resetOnPropsChange?: boolean;
  resetKeys?: Array<string | number>;
  level?: 'app' | 'page' | 'component';
  context?: string;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private retryTimeoutId: NodeJS.Timeout | null = null;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorType: ErrorType.UNKNOWN,
      errorId: '',
      retryCount: 0,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    const errorType = ErrorBoundary.categorizeError(error);
    const errorId = ErrorBoundary.generateErrorId();

    return {
      hasError: true,
      error,
      errorType,
      errorId,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { errorType, errorId } = this.state;
    
    this.setState({ errorInfo });

    // Log error details
    this.logError(error, errorInfo, errorType, errorId);

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo, errorType);
    }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    const { resetOnPropsChange, resetKeys } = this.props;
    const { hasError } = this.state;

    if (hasError && resetOnPropsChange && resetKeys) {
      const hasResetKeyChanged = resetKeys.some(
        (key, index) => key !== prevProps.resetKeys?.[index]
      );

      if (hasResetKeyChanged) {
        this.resetErrorBoundary();
      }
    }
  }

  componentWillUnmount() {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }
  }

  private static categorizeError(error: Error): ErrorType {
    const message = error.message.toLowerCase();
    const stack = error.stack?.toLowerCase() || '';

    if (message.includes('network') || message.includes('fetch')) {
      return ErrorType.NETWORK;
    }

    if (message.includes('websocket') || message.includes('ws')) {
      return ErrorType.WEBSOCKET;
    }

    if (message.includes('api') || message.includes('404') || message.includes('500')) {
      return ErrorType.API;
    }

    if (message.includes('loading chunk') || message.includes('chunk load')) {
      return ErrorType.CHUNK_LOAD;
    }

    if (stack.includes('render') || message.includes('cannot read prop')) {
      return ErrorType.RENDER;
    }

    return ErrorType.UNKNOWN;
  }

  private static generateErrorId(): string {
    return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private logError(error: Error, errorInfo: ErrorInfo, errorType: ErrorType, errorId: string) {
    const logData = {
      errorId,
      errorType,
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      context: this.props.context || 'unknown',
      level: this.props.level || 'component',
    };

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 Error Boundary (${errorType.toUpperCase()})`);
      console.error('Error:', error);
      console.error('Error Info:', errorInfo);
      console.error('Log Data:', logData);
      console.groupEnd();
    }

    // In production, send to error tracking service
    if (process.env.NODE_ENV === 'production') {
      try {
        // Example: Send to error tracking service
        // analytics.track('error_boundary_triggered', logData);
        console.error('ErrorBoundary:', logData);
      } catch (trackingError) {
        console.error('Failed to track error:', trackingError);
      }
    }
  }

  private resetErrorBoundary = () => {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
      this.retryTimeoutId = null;
    }

    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorType: ErrorType.UNKNOWN,
      errorId: '',
      retryCount: 0,
      showDetails: false,
    });
  };

  private handleRetry = () => {
    const { maxRetries = 3 } = this.props;
    const { retryCount } = this.state;

    if (retryCount >= maxRetries) {
      return;
    }

    this.setState({ retryCount: retryCount + 1 });

    // Add delay for retry to prevent rapid successive failures
    this.retryTimeoutId = setTimeout(() => {
      this.resetErrorBoundary();
    }, Math.min(1000 * Math.pow(2, retryCount), 5000)); // Exponential backoff, max 5s
  };

  private toggleDetails = () => {
    this.setState({ showDetails: !this.state.showDetails });
  };

  private getErrorSeverity(): 'error' | 'warning' {
    const { errorType } = this.state;
    
    switch (errorType) {
      case ErrorType.NETWORK:
      case ErrorType.WEBSOCKET:
      case ErrorType.API:
        return 'warning'; // Recoverable errors
      case ErrorType.CHUNK_LOAD:
      case ErrorType.RENDER:
      case ErrorType.COMPONENT:
      default:
        return 'error'; // Critical errors
    }
  }

  private getErrorMessage(): string {
    const { error, errorType } = this.state;
    
    switch (errorType) {
      case ErrorType.NETWORK:
        return 'Network connection issue. Please check your internet connection.';
      case ErrorType.WEBSOCKET:
        return 'Real-time connection lost. Attempting to reconnect...';
      case ErrorType.API:
        return 'Service temporarily unavailable. Please try again in a moment.';
      case ErrorType.CHUNK_LOAD:
        return 'Failed to load application resources. Please refresh the page.';
      case ErrorType.RENDER:
        return 'Display issue encountered. The page content may not render correctly.';
      case ErrorType.COMPONENT:
        return 'A component has encountered an error. Some features may be unavailable.';
      default:
        return error?.message || 'An unexpected error occurred.';
    }
  }

  private canRetry(): boolean {
    const { enableRetry = true, maxRetries = 3 } = this.props;
    const { errorType, retryCount } = this.state;

    if (!enableRetry || retryCount >= maxRetries) {
      return false;
    }

    // Some errors are more likely to be recoverable
    switch (errorType) {
      case ErrorType.NETWORK:
      case ErrorType.WEBSOCKET:
      case ErrorType.API:
      case ErrorType.CHUNK_LOAD:
        return true;
      default:
        return false;
    }
  }

  render() {
    const { hasError, error, errorInfo, errorType, errorId, retryCount, showDetails } = this.state;
    const { children, fallback } = this.props;

    if (hasError) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback;
      }

      const severity = this.getErrorSeverity();
      const errorMessage = this.getErrorMessage();
      const canRetry = this.canRetry();

      return (
        <Paper 
          elevation={0} 
          sx={{ 
            p: 3, 
            m: 2, 
            border: theme => `1px solid ${theme.palette.divider}`,
            backgroundColor: theme => theme.palette.background.default,
          }}
        >
          <Alert 
            severity={severity} 
            icon={<ErrorIcon />}
            sx={{ mb: 2 }}
          >
            <AlertTitle>
              {severity === 'error' ? 'Something went wrong' : 'Service Issue'}
            </AlertTitle>
            {errorMessage}
          </Alert>

          <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
            {canRetry && (
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={this.handleRetry}
                size="small"
              >
                Try Again {retryCount > 0 && `(${retryCount}/3)`}
              </Button>
            )}
            
            <Button
              variant="outlined"
              onClick={this.resetErrorBoundary}
              size="small"
            >
              Reset
            </Button>

            {process.env.NODE_ENV === 'development' && (
              <Button
                variant="text"
                startIcon={showDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                onClick={this.toggleDetails}
                size="small"
              >
                {showDetails ? 'Hide' : 'Show'} Details
              </Button>
            )}
          </Stack>

          {process.env.NODE_ENV === 'development' && (
            <Collapse in={showDetails}>
              <Box
                sx={{
                  p: 2,
                  backgroundColor: theme => theme.palette.grey[100],
                  borderRadius: 1,
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                }}
              >
                <Typography variant="subtitle2" gutterBottom>
                  <BugReportIcon sx={{ mr: 1, verticalAlign: 'middle', fontSize: 16 }} />
                  Debug Information
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Error ID:</strong> {errorId}
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Error Type:</strong> {errorType}
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Message:</strong> {error?.message}
                </Typography>
                
                {error?.stack && (
                  <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                    <strong>Stack:</strong>
                    <pre style={{ whiteSpace: 'pre-wrap', margin: '8px 0' }}>
                      {error.stack}
                    </pre>
                  </Typography>
                )}
                
                {errorInfo?.componentStack && (
                  <Typography component="div" variant="body2">
                    <strong>Component Stack:</strong>
                    <pre style={{ whiteSpace: 'pre-wrap', margin: '8px 0' }}>
                      {errorInfo.componentStack}
                    </pre>
                  </Typography>
                )}
              </Box>
            </Collapse>
          )}

          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
            If this problem persists, please contact support with error ID: {errorId}
          </Typography>
        </Paper>
      );
    }

    return children;
  }
}

// Higher-order component for easier wrapping
export const withErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) => {
  const WithErrorBoundaryComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <WrappedComponent {...props} />
    </ErrorBoundary>
  );

  WithErrorBoundaryComponent.displayName = `withErrorBoundary(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return WithErrorBoundaryComponent;
};

// Hook for programmatic error reporting
export const useErrorHandler = () => {
  const reportError = (error: Error, context?: string) => {
    // This would typically integrate with your error tracking service
    console.error('Programmatic error reported:', { error, context });
    
    if (process.env.NODE_ENV === 'production') {
      // analytics.track('manual_error_report', { error: error.message, context });
    }
  };

  return { reportError };
};

export default ErrorBoundary;