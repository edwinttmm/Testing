/**
 * Unified Error Boundary Component
 * Consolidates all error boundary implementations into a single, configurable component
 */

import React, { Component, ReactNode, memo } from 'react';
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
  Wifi as WifiIcon,
  WifiOff as WifiOffIcon,
} from '@mui/icons-material';

// Unified error types for all boundary scenarios
export enum UnifiedErrorType {
  NETWORK = 'network',
  WEBSOCKET = 'websocket',
  API = 'api',
  COMPONENT = 'component',
  CHUNK_LOAD = 'chunk_load',
  RENDER = 'render',
  TIMEOUT = 'timeout',
  ASYNC = 'async',
  UNKNOWN = 'unknown',
}

export interface UnifiedErrorInfo {
  componentStack?: string | null;
  errorBoundary?: string;
  errorBoundaryStack?: string;
  timestamp: string;
  userAgent: string;
  url: string;
}

export interface UnifiedErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: UnifiedErrorInfo | null;
  errorType: UnifiedErrorType;
  errorId: string;
  retryCount: number;
  maxRetryCount: number;
  isRetrying: boolean;
  showDetails: boolean;
  lastErrorTime: number;
  asyncLoading: boolean;
}

// Configuration for different boundary types
export type BoundaryType = 'standard' | 'websocket' | 'async';

export interface UnifiedErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: UnifiedErrorInfo, errorType: UnifiedErrorType) => void;
  enableRetry?: boolean;
  maxRetries?: number;
  retryDelay?: number;
  resetOnPropsChange?: boolean;
  resetKeys?: Array<string | number>;
  level?: 'app' | 'page' | 'component' | 'widget';
  context?: string;
  isolate?: boolean;
  enableRecovery?: boolean;
  fallbackDelay?: number;
  
  // Boundary type-specific props
  boundaryType?: BoundaryType;
  
  // WebSocket specific
  reconnectAction?: () => void;
  connectionStatus?: 'connected' | 'disconnected' | 'connecting';
  
  // Async specific
  asyncOperation?: () => Promise<any>;
  loadingComponent?: ReactNode;
  errorComponent?: (error: Error, retry: () => void) => ReactNode;
  dependencies?: any[];
}

class UnifiedErrorBoundary extends Component<UnifiedErrorBoundaryProps, UnifiedErrorBoundaryState> {
  private retryTimeoutId: NodeJS.Timeout | null = null;
  private fallbackTimeoutId: NodeJS.Timeout | null = null;
  private errorReportingQueue: Array<{ error: Error; errorInfo: UnifiedErrorInfo; errorType: UnifiedErrorType }> = [];

  constructor(props: UnifiedErrorBoundaryProps) {
    super(props);
    
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorType: UnifiedErrorType.UNKNOWN,
      errorId: '',
      retryCount: 0,
      maxRetryCount: props.maxRetries || 3,
      isRetrying: false,
      showDetails: false,
      lastErrorTime: 0,
      asyncLoading: false,
    };

    this.setupGlobalErrorHandling();
  }

  private setupGlobalErrorHandling() {
    if (this.props.boundaryType !== 'standard') {
      window.addEventListener('unhandledrejection', this.handleUnhandledRejection);
      window.addEventListener('error', this.handleGlobalError);
    }
  }

  private handleUnhandledRejection = (event: PromiseRejectionEvent) => {
    if (this.props.context && event.reason) {
      const reasonStr = this.serializeError(event.reason);
      console.warn(`Unhandled promise rejection in ${this.props.context}:`, reasonStr, event.reason);
      
      event.preventDefault();
      
      const syntheticError = new Error(`Unhandled Promise Rejection: ${reasonStr}`);
      (syntheticError as any).originalReason = event.reason;
      this.handleSyntheticError(syntheticError, 'promise-rejection');
    }
  };

  private handleGlobalError = (event: ErrorEvent) => {
    if (this.props.context && event.error && !this.state.hasError) {
      console.warn(`Global error in ${this.props.context}:`, event.error);
      this.handleSyntheticError(event.error, 'global-error');
    }
  };

  private handleSyntheticError(error: Error, source: string) {
    if (!this.state.hasError) {
      const errorType = UnifiedErrorBoundary.categorizeError(error);
      const errorId = UnifiedErrorBoundary.generateErrorId();
      const errorInfo: UnifiedErrorInfo = {
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

  static getDerivedStateFromError(error: Error): Partial<UnifiedErrorBoundaryState> {
    const errorType = UnifiedErrorBoundary.categorizeError(error);
    const errorId = UnifiedErrorBoundary.generateErrorId();
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
    
    const enhancedErrorInfo: UnifiedErrorInfo = {
      ...errorInfo,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
    };
    
    this.setState({ errorInfo: enhancedErrorInfo });

    this.logError(error, enhancedErrorInfo, errorType, errorId);
    this.errorReportingQueue.push({ error, errorInfo: enhancedErrorInfo, errorType });
    this.flushErrorReporting();

    if (this.props.onError) {
      this.props.onError(error, enhancedErrorInfo, errorType);
    }

    if (this.props.enableRecovery) {
      this.attemptAutomaticRecovery(error, errorType);
    }
  }

  componentDidUpdate(prevProps: UnifiedErrorBoundaryProps) {
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

  private static categorizeError(error: Error): UnifiedErrorType {
    const message = (error.message || '').toLowerCase();
    const stack = (error.stack || '').toLowerCase();
    const name = (error.name || '').toLowerCase();

    if (message.includes('network') || 
        message.includes('fetch') || 
        message.includes('connection') ||
        name.includes('networkerror')) {
      return UnifiedErrorType.NETWORK;
    }

    if (message.includes('timeout') || 
        message.includes('aborted') ||
        message.includes('econnaborted')) {
      return UnifiedErrorType.TIMEOUT;
    }

    if (message.includes('websocket') || 
        message.includes('ws') ||
        message.includes('socket')) {
      return UnifiedErrorType.WEBSOCKET;
    }

    if (message.includes('api') || 
        message.includes('404') || 
        message.includes('500') ||
        message.includes('http')) {
      return UnifiedErrorType.API;
    }

    if (message.includes('loading chunk') || 
        message.includes('chunk load') ||
        message.includes('dynamicimport')) {
      return UnifiedErrorType.CHUNK_LOAD;
    }

    if (message.includes('async') || 
        message.includes('promise')) {
      return UnifiedErrorType.ASYNC;
    }

    if (stack.includes('render') || 
        message.includes('cannot read prop') ||
        message.includes('undefined is not an object') ||
        message.includes('null is not an object')) {
      return UnifiedErrorType.RENDER;
    }

    return UnifiedErrorType.UNKNOWN;
  }

  private static generateErrorId(): string {
    return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private serializeError(error: any): string {
    try {
      if (error === null) return 'null';
      if (error === undefined) return 'undefined';
      if (typeof error === 'string') return error;
      if (typeof error === 'number' || typeof error === 'boolean') return String(error);
      
      if (error instanceof Error) {
        return `${error.name}: ${error.message}`;
      }
      
      if (error && typeof error === 'object' && error.message) {
        return String(error.message);
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
  }

  private logError(error: Error, errorInfo: UnifiedErrorInfo, errorType: UnifiedErrorType, errorId: string) {
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
      boundaryType: this.props.boundaryType || 'standard',
    };

    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 Unified Error Boundary (${errorType.toUpperCase()})`);
      console.error('Error:', error);
      console.error('Error Info:', errorInfo);
      console.error('Log Data:', logData);
      console.trace('Stack Trace');
      console.groupEnd();
    } else {
      console.error('UnifiedErrorBoundary:', JSON.stringify(logData, null, 2));
    }
  }

  private flushErrorReporting() {
    if (this.errorReportingQueue.length === 0) return;

    const errors = [...this.errorReportingQueue];
    this.errorReportingQueue = [];

    try {
      if (typeof window !== 'undefined' && (window as any).errorTracker) {
        (window as any).errorTracker.reportBatch(errors);
      }

      if (typeof window !== 'undefined' && (window as any).analytics) {
        errors.forEach(({ error, errorType }) => {
          (window as any).analytics.track('unified_error_boundary_triggered', {
            errorType,
            message: error.message,
            context: this.props.context,
            boundaryType: this.props.boundaryType,
          });
        });
      }
    } catch (trackingError) {
      console.warn('Failed to report errors:', trackingError);
    }
  }

  private attemptAutomaticRecovery(error: Error, errorType: UnifiedErrorType) {
    switch (errorType) {
      case UnifiedErrorType.NETWORK:
        this.scheduleRecovery(5000, 'Network connectivity restored');
        break;
      
      case UnifiedErrorType.CHUNK_LOAD:
        this.scheduleRecovery(2000, 'Reloading application resources');
        break;
      
      case UnifiedErrorType.API:
        this.scheduleRecovery(Math.min(1000 * Math.pow(2, this.state.retryCount), 10000), 'Retrying API request');
        break;
        
      case UnifiedErrorType.WEBSOCKET:
        if (this.props.reconnectAction) {
          this.scheduleRecovery(3000, 'Reconnecting WebSocket');
        }
        break;
        
      default:
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
      errorType: UnifiedErrorType.UNKNOWN,
      errorId: '',
      retryCount: 0,
      isRetrying: false,
      showDetails: false,
      lastErrorTime: 0,
      asyncLoading: false,
    });
  };

  private handleRetry = (isAutomatic: boolean = false) => {
    const { retryDelay = 1000 } = this.props;
    const { retryCount, maxRetryCount } = this.state;

    if (retryCount >= maxRetryCount) {
      console.warn(`Max retry attempts (${maxRetryCount}) reached`);
      return;
    }

    this.setState({ 
      isRetrying: true,
      retryCount: retryCount + 1 
    });

    const delay = isAutomatic ? 0 : Math.min(retryDelay * Math.pow(2, retryCount), 10000);

    if (!isAutomatic) {
      console.log(`Retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetryCount})`);
    }

    this.retryTimeoutId = setTimeout(() => {
      if (this.props.boundaryType === 'websocket' && this.props.reconnectAction) {
        this.props.reconnectAction();
      }
      this.resetErrorBoundary();
    }, delay);
  };

  private toggleDetails = () => {
    this.setState({ showDetails: !this.state.showDetails });
  };

  private getErrorSeverity(): 'error' | 'warning' | 'info' {
    const { errorType } = this.state;
    
    switch (errorType) {
      case UnifiedErrorType.NETWORK:
      case UnifiedErrorType.WEBSOCKET:
      case UnifiedErrorType.API:
      case UnifiedErrorType.TIMEOUT:
        return 'warning';
      case UnifiedErrorType.CHUNK_LOAD:
      case UnifiedErrorType.ASYNC:
        return 'info';
      case UnifiedErrorType.RENDER:
      case UnifiedErrorType.COMPONENT:
      default:
        return 'error';
    }
  }

  private getErrorIcon() {
    const { errorType } = this.state;
    const { boundaryType } = this.props;
    
    if (boundaryType === 'websocket') {
      return <WifiOffIcon />;
    }
    
    switch (errorType) {
      case UnifiedErrorType.NETWORK:
      case UnifiedErrorType.TIMEOUT:
        return <NetworkCheckIcon />;
      case UnifiedErrorType.API:
      case UnifiedErrorType.WEBSOCKET:
        return <CloudOffIcon />;
      default:
        return <ErrorIcon />;
    }
  }

  private getErrorMessage(): string {
    const { error, errorType } = this.state;
    const { boundaryType } = this.props;
    
    if (boundaryType === 'websocket') {
      return 'Real-time connection lost. Some features may not work properly until reconnected.';
    }
    
    switch (errorType) {
      case UnifiedErrorType.NETWORK:
        return 'Network connection issue. Please check your internet connection and try again.';
      case UnifiedErrorType.TIMEOUT:
        return 'Request timed out. The service may be experiencing high load. Please try again.';
      case UnifiedErrorType.WEBSOCKET:
        return 'Real-time connection lost. Attempting to reconnect automatically...';
      case UnifiedErrorType.API:
        return 'Service temporarily unavailable. Please try again in a moment.';
      case UnifiedErrorType.CHUNK_LOAD:
        return 'Failed to load application resources. Please refresh the page to get the latest version.';
      case UnifiedErrorType.RENDER:
        return 'Display issue encountered. Some content may not render correctly.';
      case UnifiedErrorType.COMPONENT:
        return 'A component has encountered an error. Some features may be temporarily unavailable.';
      case UnifiedErrorType.ASYNC:
        return 'An error occurred while loading data. Please try again.';
      default:
        return error?.message || 'An unexpected error occurred. Our team has been notified.';
    }
  }

  private getRecoveryActions(): Array<{ label: string; action: () => void; primary?: boolean }> {
    const { errorType, retryCount, maxRetryCount, isRetrying } = this.state;
    const { boundaryType, reconnectAction, connectionStatus } = this.props;
    const actions: Array<{ label: string; action: () => void; primary?: boolean }> = [];

    // WebSocket specific actions
    if (boundaryType === 'websocket' && reconnectAction && connectionStatus !== 'connecting') {
      actions.push({
        label: 'Reconnect',
        action: reconnectAction,
        primary: true
      });
    }

    // Retry action for recoverable errors
    if (this.canRetry()) {
      actions.push({
        label: isRetrying 
          ? 'Retrying...' 
          : `Try Again ${retryCount > 0 ? `(${retryCount}/${maxRetryCount})` : ''}`,
        action: () => this.handleRetry(),
        primary: !reconnectAction
      });
    }

    // Reset action
    actions.push({
      label: 'Reset',
      action: this.resetErrorBoundary
    });

    // Refresh page for chunk loading errors
    if (errorType === UnifiedErrorType.CHUNK_LOAD) {
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

    switch (errorType) {
      case UnifiedErrorType.NETWORK:
      case UnifiedErrorType.WEBSOCKET:
      case UnifiedErrorType.API:
      case UnifiedErrorType.TIMEOUT:
      case UnifiedErrorType.CHUNK_LOAD:
      case UnifiedErrorType.ASYNC:
        return true;
      default:
        return false;
    }
  }

  render() {
    const { hasError, error, errorInfo, errorType, errorId, showDetails, isRetrying } = this.state;
    const { children, fallback, boundaryType, connectionStatus } = this.props;

    if (hasError) {
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
              {boundaryType === 'websocket' ? 'Real-time Connection Lost' :
               severity === 'error' ? 'Something went wrong' : 
               severity === 'warning' ? 'Service Issue' : 'Temporary Issue'}
            </AlertTitle>
            {errorMessage}
          </Alert>

          {boundaryType === 'websocket' && connectionStatus && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Status: {connectionStatus === 'connecting' ? 'Reconnecting...' : 'Disconnected'}
              </Typography>
            </Box>
          )}

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
                disabled={isRetrying && !action.label.includes('Reconnect')}
                size="small"
                startIcon={action.primary && !isRetrying ? <RefreshIcon /> : 
                          action.label.includes('Reconnect') ? <WifiIcon /> : undefined}
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
                  <strong>Boundary Type:</strong> {boundaryType || 'standard'}
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

    return <>{children}</>;
  }
}

// Higher-order component for easier wrapping
export const withUnifiedErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  errorBoundaryProps?: Omit<UnifiedErrorBoundaryProps, 'children'>
) => {
  const WithErrorBoundaryComponent = (props: P) => (
    <UnifiedErrorBoundary {...errorBoundaryProps}>
      <WrappedComponent {...props} />
    </UnifiedErrorBoundary>
  );

  WithErrorBoundaryComponent.displayName = `withUnifiedErrorBoundary(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return WithErrorBoundaryComponent;
};

// Specific boundary type components for backward compatibility
export const StandardErrorBoundary = memo((props: Omit<UnifiedErrorBoundaryProps, 'boundaryType'>) => (
  <UnifiedErrorBoundary {...props} boundaryType="standard" />
));

export const WebSocketErrorBoundary = memo((props: Omit<UnifiedErrorBoundaryProps, 'boundaryType'>) => (
  <UnifiedErrorBoundary 
    {...props} 
    boundaryType="websocket"
    maxRetries={5}
    context="websocket-connection"
  />
));

export const AsyncErrorBoundary = memo((props: Omit<UnifiedErrorBoundaryProps, 'boundaryType'>) => (
  <UnifiedErrorBoundary {...props} boundaryType="async" />
));

StandardErrorBoundary.displayName = 'StandardErrorBoundary';
WebSocketErrorBoundary.displayName = 'WebSocketErrorBoundary';
AsyncErrorBoundary.displayName = 'AsyncErrorBoundary';

export default UnifiedErrorBoundary;