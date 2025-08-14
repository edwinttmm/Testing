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
  CircularProgress,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  BugReport as BugReportIcon,
  NetworkCheck as NetworkCheckIcon,
  CloudOff as CloudOffIcon,
} from '@mui/icons-material';

// Enhanced error types for better categorization
export enum EnhancedErrorType {
  NETWORK = 'network',
  WEBSOCKET = 'websocket', 
  API = 'api',
  COMPONENT = 'component',
  CHUNK_LOAD = 'chunk_load',
  RENDER = 'render',
  TIMEOUT = 'timeout',
  UNKNOWN = 'unknown',
}

export interface EnhancedErrorInfo {
  componentStack?: string | null;
  errorBoundary?: string;
  errorBoundaryStack?: string;
  timestamp: string;
  userAgent: string;
  url: string;
}

export interface EnhancedErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: EnhancedErrorInfo | null;
  errorType: EnhancedErrorType;
  errorId: string;
  retryCount: number;
  maxRetryCount: number;
  isRetrying: boolean;
  showDetails: boolean;
  lastErrorTime: number;
}

export interface EnhancedErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: EnhancedErrorInfo, errorType: EnhancedErrorType) => void;
  enableRetry?: boolean;
  maxRetries?: number;
  retryDelay?: number;
  resetOnPropsChange?: boolean;
  resetKeys?: Array<string | number>;
  level?: 'app' | 'page' | 'component' | 'widget';
  context?: string;
  isolate?: boolean; // Prevents error from bubbling up
  enableRecovery?: boolean; // Enables automatic recovery strategies
  fallbackDelay?: number; // Delay before showing fallback UI
}

class EnhancedErrorBoundary extends Component<EnhancedErrorBoundaryProps, EnhancedErrorBoundaryState> {
  private retryTimeoutId: NodeJS.Timeout | null = null;
  private fallbackTimeoutId: NodeJS.Timeout | null = null;
  private errorReportingQueue: Array<{ error: Error; errorInfo: EnhancedErrorInfo; errorType: EnhancedErrorType }> = [];

  constructor(props: EnhancedErrorBoundaryProps) {
    super(props);
    
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorType: EnhancedErrorType.UNKNOWN,
      errorId: '',
      retryCount: 0,
      maxRetryCount: props.maxRetries || 3,
      isRetrying: false,
      showDetails: false,
      lastErrorTime: 0,
    };

    // Set up global error listeners for this boundary's context
    this.setupGlobalErrorHandling();
  }

  private setupGlobalErrorHandling() {
    // Listen for unhandled promise rejections
    window.addEventListener('unhandledrejection', this.handleUnhandledRejection);
    
    // Listen for global JavaScript errors
    window.addEventListener('error', this.handleGlobalError);
  }

  private handleUnhandledRejection = (event: PromiseRejectionEvent) => {
    if (this.props.context && event.reason) {
      console.warn(`Unhandled promise rejection in ${this.props.context}:`, event.reason);
      
      // Create synthetic error for error boundary
      const syntheticError = new Error(`Unhandled Promise Rejection: ${event.reason}`);
      this.handleSyntheticError(syntheticError, 'promise-rejection');
    }
  };

  private handleGlobalError = (event: ErrorEvent) => {
    if (this.props.context && event.error) {
      console.warn(`Global error in ${this.props.context}:`, event.error);
      
      // Don't handle errors that are already being handled by React error boundaries
      if (!this.state.hasError) {
        this.handleSyntheticError(event.error, 'global-error');
      }
    }
  };

  private handleSyntheticError(error: Error, source: string) {
    // Only handle synthetic errors if we're not already in an error state
    if (!this.state.hasError) {
      const errorType = EnhancedErrorBoundary.categorizeError(error);
      const errorId = EnhancedErrorBoundary.generateErrorId();
      const errorInfo: EnhancedErrorInfo = {
        componentStack: `Synthetic error from ${source}`,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href,
      };

      this.setState({
        hasError: true,
        error,
        errorInfo,
        errorType,
        errorId,
        lastErrorTime: Date.now(),
      });

      this.logError(error, errorInfo, errorType, errorId);

      if (this.props.onError) {
        this.props.onError(error, errorInfo, errorType);
      }
    }
  }

  static getDerivedStateFromError(error: Error): Partial<EnhancedErrorBoundaryState> {
    const errorType = EnhancedErrorBoundary.categorizeError(error);
    const errorId = EnhancedErrorBoundary.generateErrorId();
    const now = Date.now();

    return {
      hasError: true,
      error,
      errorType,
      errorId,
      lastErrorTime: now,
      isRetrying: false,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const { errorType, errorId } = this.state;
    
    const enhancedErrorInfo: EnhancedErrorInfo = {
      ...errorInfo,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
    };
    
    this.setState({ errorInfo: enhancedErrorInfo });

    // Log error details
    this.logError(error, enhancedErrorInfo, errorType, errorId);

    // Queue error for batch reporting
    this.errorReportingQueue.push({ error, errorInfo: enhancedErrorInfo, errorType });
    this.flushErrorReporting();

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, enhancedErrorInfo, errorType);
    }

    // Attempt automatic recovery for certain error types
    if (this.props.enableRecovery) {
      this.attemptAutomaticRecovery(error, errorType);
    }
  }

  componentDidUpdate(prevProps: EnhancedErrorBoundaryProps) {
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
    this.cleanup();
    window.removeEventListener('unhandledrejection', this.handleUnhandledRejection);
    window.removeEventListener('error', this.handleGlobalError);
  }

  private cleanup() {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
      this.retryTimeoutId = null;
    }
    if (this.fallbackTimeoutId) {
      clearTimeout(this.fallbackTimeoutId);
      this.fallbackTimeoutId = null;
    }
  }

  private static categorizeError(error: Error): EnhancedErrorType {
    const message = (error.message || '').toLowerCase();
    const stack = (error.stack || '').toLowerCase();
    const name = (error.name || '').toLowerCase();

    // Network-related errors
    if (message.includes('network') || 
        message.includes('fetch') || 
        message.includes('connection') ||
        name.includes('networkerror')) {
      return EnhancedErrorType.NETWORK;
    }

    // Timeout errors
    if (message.includes('timeout') || 
        message.includes('aborted') ||
        message.includes('econnaborted')) {
      return EnhancedErrorType.TIMEOUT;
    }

    // WebSocket errors
    if (message.includes('websocket') || 
        message.includes('ws') ||
        message.includes('socket')) {
      return EnhancedErrorType.WEBSOCKET;
    }

    // API errors
    if (message.includes('api') || 
        message.includes('404') || 
        message.includes('500') ||
        message.includes('http')) {
      return EnhancedErrorType.API;
    }

    // Chunk loading errors (code splitting)
    if (message.includes('loading chunk') || 
        message.includes('chunk load') ||
        message.includes('dynamicimport')) {
      return EnhancedErrorType.CHUNK_LOAD;
    }

    // Render errors
    if (stack.includes('render') || 
        message.includes('cannot read prop') ||
        message.includes('undefined is not an object') ||
        message.includes('null is not an object')) {
      return EnhancedErrorType.RENDER;
    }

    return EnhancedErrorType.UNKNOWN;
  }

  private static generateErrorId(): string {
    return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private logError(error: Error, errorInfo: EnhancedErrorInfo, errorType: EnhancedErrorType, errorId: string) {
    const logData = {
      errorId,
      errorType,
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: errorInfo.timestamp,
      userAgent: errorInfo.userAgent,
      url: errorInfo.url,
      context: this.props.context || 'unknown',
      level: this.props.level || 'component',
      retryCount: this.state.retryCount,
    };

    // Enhanced logging in development
    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 Enhanced Error Boundary (${errorType.toUpperCase()})`);
      console.error('Error:', error);
      console.error('Error Info:', errorInfo);
      console.error('Log Data:', logData);
      console.trace('Stack Trace');
      console.groupEnd();
    } else {
      // Production logging with structured format
      console.error('ErrorBoundary:', JSON.stringify(logData, null, 2));
    }
  }

  private flushErrorReporting() {
    if (this.errorReportingQueue.length === 0) return;

    // Batch report errors to prevent spam
    const errors = [...this.errorReportingQueue];
    this.errorReportingQueue = [];

    try {
      // Send to error tracking service
      if (typeof window !== 'undefined' && (window as any).errorTracker) {
        (window as any).errorTracker.reportBatch(errors);
      }

      // Send to analytics if available
      if (typeof window !== 'undefined' && (window as any).analytics) {
        errors.forEach(({ error, errorType }) => {
          (window as any).analytics.track('error_boundary_triggered', {
            errorType,
            message: error.message,
            context: this.props.context,
          });
        });
      }
    } catch (trackingError) {
      console.warn('Failed to report errors:', trackingError);
    }
  }

  private attemptAutomaticRecovery(error: Error, errorType: EnhancedErrorType) {
    // Define recovery strategies for different error types
    switch (errorType) {
      case EnhancedErrorType.NETWORK:
        // For network errors, wait and retry
        this.scheduleRecovery(5000, 'Network connectivity restored');
        break;
      
      case EnhancedErrorType.CHUNK_LOAD:
        // For chunk load errors, try to reload the page
        this.scheduleRecovery(2000, 'Reloading application resources');
        break;
      
      case EnhancedErrorType.API:
        // For API errors, retry with exponential backoff
        this.scheduleRecovery(Math.min(1000 * Math.pow(2, this.state.retryCount), 10000), 'Retrying API request');
        break;
        
      default:
        // For other errors, use standard retry logic
        break;
    }
  }

  private scheduleRecovery(delay: number, message: string) {
    if (this.state.retryCount >= this.state.maxRetryCount) {
      return;
    }

    console.log(`Scheduling automatic recovery in ${delay}ms: ${message}`);
    
    this.retryTimeoutId = setTimeout(() => {
      this.handleRetry(true);
    }, delay);
  }

  private resetErrorBoundary = () => {
    this.cleanup();
    
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorType: EnhancedErrorType.UNKNOWN,
      errorId: '',
      retryCount: 0,
      isRetrying: false,
      showDetails: false,
      lastErrorTime: 0,
    });
  };

  private handleRetry = (isAutomatic: boolean = false) => {
    const { maxRetries = 3, retryDelay = 1000 } = this.props;
    const { retryCount, maxRetryCount } = this.state;

    if (retryCount >= maxRetryCount) {
      console.warn(`Max retry attempts (${maxRetryCount}) reached`);
      return;
    }

    this.setState({ 
      isRetrying: true,
      retryCount: retryCount + 1 
    });

    // Calculate delay with exponential backoff
    const delay = isAutomatic ? 0 : Math.min(retryDelay * Math.pow(2, retryCount), 10000);

    if (!isAutomatic) {
      console.log(`Retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetryCount})`);
    }

    this.retryTimeoutId = setTimeout(() => {
      this.resetErrorBoundary();
    }, delay);
  };

  private toggleDetails = () => {
    this.setState({ showDetails: !this.state.showDetails });
  };

  private getErrorSeverity(): 'error' | 'warning' | 'info' {
    const { errorType } = this.state;
    
    switch (errorType) {
      case EnhancedErrorType.NETWORK:
      case EnhancedErrorType.WEBSOCKET:
      case EnhancedErrorType.API:
      case EnhancedErrorType.TIMEOUT:
        return 'warning'; // Recoverable errors
      case EnhancedErrorType.CHUNK_LOAD:
        return 'info'; // Usually fixable with refresh
      case EnhancedErrorType.RENDER:
      case EnhancedErrorType.COMPONENT:
      default:
        return 'error'; // Critical errors
    }
  }

  private getErrorIcon() {
    const { errorType } = this.state;
    
    switch (errorType) {
      case EnhancedErrorType.NETWORK:
      case EnhancedErrorType.TIMEOUT:
        return <NetworkCheckIcon />;
      case EnhancedErrorType.API:
      case EnhancedErrorType.WEBSOCKET:
        return <CloudOffIcon />;
      default:
        return <ErrorIcon />;
    }
  }

  private getErrorMessage(): string {
    const { error, errorType } = this.state;
    
    switch (errorType) {
      case EnhancedErrorType.NETWORK:
        return 'Network connection issue. Please check your internet connection and try again.';
      case EnhancedErrorType.TIMEOUT:
        return 'Request timed out. The service may be experiencing high load. Please try again.';
      case EnhancedErrorType.WEBSOCKET:
        return 'Real-time connection lost. Attempting to reconnect automatically...';
      case EnhancedErrorType.API:
        return 'Service temporarily unavailable. Please try again in a moment.';
      case EnhancedErrorType.CHUNK_LOAD:
        return 'Failed to load application resources. Please refresh the page to get the latest version.';
      case EnhancedErrorType.RENDER:
        return 'Display issue encountered. Some content may not render correctly.';
      case EnhancedErrorType.COMPONENT:
        return 'A component has encountered an error. Some features may be temporarily unavailable.';
      default:
        return error?.message || 'An unexpected error occurred. Our team has been notified.';
    }
  }

  private getRecoveryActions(): Array<{ label: string; action: () => void; primary?: boolean }> {
    const { errorType, retryCount, maxRetryCount, isRetrying } = this.state;
    const actions: Array<{ label: string; action: () => void; primary?: boolean }> = [];

    // Retry action for recoverable errors
    if (this.canRetry()) {
      actions.push({
        label: isRetrying 
          ? 'Retrying...' 
          : `Try Again ${retryCount > 0 ? `(${retryCount}/${maxRetryCount})` : ''}`,
        action: () => this.handleRetry(),
        primary: true
      });
    }

    // Reset action
    actions.push({
      label: 'Reset',
      action: this.resetErrorBoundary
    });

    // Refresh page for chunk loading errors
    if (errorType === EnhancedErrorType.CHUNK_LOAD) {
      actions.push({
        label: 'Refresh Page',
        action: () => window.location.reload()
      });
    }

    return actions;
  }

  private canRetry(): boolean {
    const { enableRetry = true } = this.props;
    const { errorType, retryCount, maxRetryCount, isRetrying } = this.state;

    if (!enableRetry || isRetrying || retryCount >= maxRetryCount) {
      return false;
    }

    // Some errors are more likely to be recoverable
    switch (errorType) {
      case EnhancedErrorType.NETWORK:
      case EnhancedErrorType.WEBSOCKET:
      case EnhancedErrorType.API:
      case EnhancedErrorType.TIMEOUT:
      case EnhancedErrorType.CHUNK_LOAD:
        return true;
      default:
        return false;
    }
  }

  render() {
    const { hasError, error, errorInfo, errorType, errorId, showDetails, isRetrying } = this.state;
    const { children, fallback, fallbackDelay = 100 } = this.props;

    if (hasError) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback;
      }

      const severity = this.getErrorSeverity();
      const errorMessage = this.getErrorMessage();
      const errorIcon = this.getErrorIcon();
      const recoveryActions = this.getRecoveryActions();

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
            icon={errorIcon}
            sx={{ mb: 2 }}
          >
            <AlertTitle>
              {severity === 'error' ? 'Something went wrong' : 
               severity === 'warning' ? 'Service Issue' : 'Temporary Issue'}
            </AlertTitle>
            {errorMessage}
          </Alert>

          {isRetrying && (
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CircularProgress size={20} sx={{ mr: 2 }} />
              <Typography variant="body2" color="text.secondary">
                Attempting recovery...
              </Typography>
            </Box>
          )}

          <Stack direction="row" spacing={2} sx={{ mb: 2, flexWrap: 'wrap' }}>
            {recoveryActions.map((action, index) => (
              <Button
                key={index}
                variant={action.primary ? 'contained' : 'outlined'}
                onClick={action.action}
                disabled={isRetrying}
                size="small"
                startIcon={action.primary && !isRetrying ? <RefreshIcon /> : undefined}
              >
                {action.label}
              </Button>
            ))}

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
                  <strong>Context:</strong> {this.props.context || 'N/A'}
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Level:</strong> {this.props.level || 'component'}
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Message:</strong> {error?.message}
                </Typography>
                
                {error?.stack && (
                  <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                    <strong>Stack:</strong>
                    <pre style={{ whiteSpace: 'pre-wrap', margin: '8px 0', fontSize: '0.75rem' }}>
                      {error.stack}
                    </pre>
                  </Typography>
                )}
                
                {errorInfo?.componentStack && (
                  <Typography component="div" variant="body2">
                    <strong>Component Stack:</strong>
                    <pre style={{ whiteSpace: 'pre-wrap', margin: '8px 0', fontSize: '0.75rem' }}>
                      {errorInfo.componentStack}
                    </pre>
                  </Typography>
                )}
              </Box>
            </Collapse>
          )}

          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
            If this problem persists, please contact support with error ID: <strong>{errorId}</strong>
          </Typography>
        </Paper>
      );
    }

    return children;
  }
}

// Higher-order component for easier wrapping
export const withEnhancedErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  errorBoundaryProps?: Omit<EnhancedErrorBoundaryProps, 'children'>
) => {
  const WithErrorBoundaryComponent = (props: P) => (
    <EnhancedErrorBoundary {...errorBoundaryProps}>
      <WrappedComponent {...props} />
    </EnhancedErrorBoundary>
  );

  WithErrorBoundaryComponent.displayName = `withEnhancedErrorBoundary(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return WithErrorBoundaryComponent;
};

export default EnhancedErrorBoundary;