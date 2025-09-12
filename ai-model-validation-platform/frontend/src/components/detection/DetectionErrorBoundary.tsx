import React, { Component, ReactNode } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Typography,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  IconButton,
  Tooltip,
  Stack,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
} from '@mui/material';
import {
  Refresh,
  BugReport,
  ExpandMore,
  ContentCopy,
  Warning,
  Error as ErrorIcon,
  NetworkCheck,
  VideoCameraBack,
  Computer,
  Settings,
  Info,
  Close,
  ReportProblem
} from '@mui/icons-material';

// Error type definitions
export enum ErrorCategory {
  NETWORK = 'network',
  RENDERING = 'rendering',
  PROCESSING = 'processing',
  HARDWARE = 'hardware',
  AUTHENTICATION = 'authentication',
  PERMISSION = 'permission',
  VALIDATION = 'validation',
  UNKNOWN = 'unknown'
}

export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface DetectionError {
  id: string;
  message: string;
  category: ErrorCategory;
  severity: ErrorSeverity;
  stack?: string;
  timestamp: Date;
  componentStack?: string;
  userAgent?: string;
  url?: string;
  userId?: string;
  sessionId?: string;
  additionalInfo?: Record<string, any>;
  frame80Specific?: boolean;
  canvasError?: boolean;
  videoError?: boolean;
  apiError?: boolean;
  hardwareError?: boolean;
}

export interface ErrorReportingService {
  reportError: (error: DetectionError) => Promise<void>;
  reportPerformanceIssue?: (metrics: Record<string, any>) => Promise<void>;
}

interface DetectionErrorBoundaryState {
  hasError: boolean;
  error: DetectionError | null;
  errorInfo: React.ErrorInfo | null;
  retryCount: number;
  isReporting: boolean;
  showDetailDialog: boolean;
  lastErrorTimestamp: number;
}

interface DetectionErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: DetectionError, errorInfo: React.ErrorInfo | null) => void;
  errorReportingService?: ErrorReportingService;
  maxRetries?: number;
  autoRetryDelay?: number;
  enableAutoRecovery?: boolean;
  sessionId?: string;
  userId?: string;
  environment?: 'development' | 'staging' | 'production';
}

export class DetectionErrorBoundary extends Component<
  DetectionErrorBoundaryProps,
  DetectionErrorBoundaryState
> {
  private retryTimeoutId: NodeJS.Timeout | null = null;
  private errorThrottleTimeoutId: NodeJS.Timeout | null = null;
  private readonly maxRetries: number;
  private readonly autoRetryDelay: number;

  constructor(props: DetectionErrorBoundaryProps) {
    super(props);
    
    this.maxRetries = props.maxRetries ?? 3;
    this.autoRetryDelay = props.autoRetryDelay ?? 5000;
    
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0,
      isReporting: false,
      showDetailDialog: false,
      lastErrorTimestamp: 0
    };
  }

  static getDerivedStateFromError(error: Error): Partial<DetectionErrorBoundaryState> {
    const detectionError = DetectionErrorBoundary.categorizeError(error);
    
    return {
      hasError: true,
      error: detectionError,
      lastErrorTimestamp: Date.now()
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const detectionError = DetectionErrorBoundary.categorizeError(error);
    const timestamp = Date.now();
    
    // Prevent error spam - throttle similar errors
    if (timestamp - this.state.lastErrorTimestamp < 1000 && 
        this.state.error?.message === error.message) {
      return;
    }

    // Enhanced error information
    const enhancedError: DetectionError = {
      ...detectionError,
      componentStack: errorInfo.componentStack,
      userAgent: navigator.userAgent,
      url: window.location.href,
      userId: this.props.userId,
      sessionId: this.props.sessionId,
      timestamp: new Date(),
      additionalInfo: {
        retryCount: this.state.retryCount,
        environment: this.props.environment || 'development',
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        },
        memory: (performance as any).memory ? {
          usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
          totalJSHeapSize: (performance as any).memory.totalJSHeapSize,
          jsHeapSizeLimit: (performance as any).memory.jsHeapSizeLimit
        } : undefined
      }
    };

    console.error('DetectionErrorBoundary caught an error:', error);
    console.error('Error info:', errorInfo);
    console.error('Enhanced error details:', enhancedError);

    this.setState({
      error: enhancedError,
      errorInfo,
      lastErrorTimestamp: timestamp
    });

    // Report error to external service
    this.reportError(enhancedError, errorInfo);

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(enhancedError, errorInfo);
    }

    // Auto-retry for certain error types
    if (this.props.enableAutoRecovery && this.shouldAutoRetry(enhancedError)) {
      this.scheduleAutoRetry();
    }
  }

  componentWillUnmount() {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }
    if (this.errorThrottleTimeoutId) {
      clearTimeout(this.errorThrottleTimeoutId);
    }
  }

  private static categorizeError(error: Error): DetectionError {
    const message = error.message.toLowerCase();
    const stack = error.stack || '';
    
    let category = ErrorCategory.UNKNOWN;
    let severity = ErrorSeverity.MEDIUM;
    let frame80Specific = false;
    let canvasError = false;
    let videoError = false;
    let apiError = false;
    let hardwareError = false;

    // Network errors
    if (message.includes('network') || message.includes('fetch') || 
        message.includes('xhr') || message.includes('timeout') ||
        message.includes('connection') || stack.includes('NetworkError')) {
      category = ErrorCategory.NETWORK;
      severity = ErrorSeverity.HIGH;
      apiError = true;
    }
    
    // Canvas/rendering errors
    else if (message.includes('canvas') || message.includes('webgl') || 
             message.includes('rendering') || message.includes('context') ||
             stack.includes('CanvasRenderingContext') || stack.includes('WebGL')) {
      category = ErrorCategory.RENDERING;
      severity = ErrorSeverity.HIGH;
      canvasError = true;
    }
    
    // Video processing errors
    else if (message.includes('video') || message.includes('media') || 
             message.includes('codec') || message.includes('decode') ||
             stack.includes('HTMLVideoElement') || stack.includes('MediaSource')) {
      category = ErrorCategory.PROCESSING;
      severity = ErrorSeverity.HIGH;
      videoError = true;
    }
    
    // Hardware/device errors
    else if (message.includes('device') || message.includes('hardware') || 
             message.includes('gpu') || message.includes('webgl') ||
             message.includes('labjack') || message.includes('usb')) {
      category = ErrorCategory.HARDWARE;
      severity = ErrorSeverity.CRITICAL;
      hardwareError = true;
    }
    
    // Frame 80 specific errors
    else if (message.includes('frame 80') || message.includes('frame80') ||
             stack.includes('frame80') || message.includes('detection failure at frame 80')) {
      category = ErrorCategory.PROCESSING;
      severity = ErrorSeverity.HIGH;
      frame80Specific = true;
    }
    
    // Authentication/permission errors
    else if (message.includes('unauthorized') || message.includes('permission') || 
             message.includes('forbidden') || message.includes('access denied')) {
      category = ErrorCategory.AUTHENTICATION;
      severity = ErrorSeverity.MEDIUM;
    }
    
    // Validation errors
    else if (message.includes('validation') || message.includes('invalid') || 
             message.includes('schema') || message.includes('format')) {
      category = ErrorCategory.VALIDATION;
      severity = ErrorSeverity.LOW;
    }

    return {
      id: `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      message: error.message,
      category,
      severity,
      stack: error.stack,
      timestamp: new Date(),
      frame80Specific,
      canvasError,
      videoError,
      apiError,
      hardwareError
    };
  }

  private shouldAutoRetry(error: DetectionError): boolean {
    if (this.state.retryCount >= this.maxRetries) {
      return false;
    }

    // Auto-retry for certain recoverable errors
    return error.category === ErrorCategory.NETWORK ||
           error.category === ErrorCategory.PROCESSING ||
           (error.frame80Specific && error.severity !== ErrorSeverity.CRITICAL);
  }

  private scheduleAutoRetry = (): void => {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }

    this.retryTimeoutId = setTimeout(() => {
      this.handleRetry();
    }, this.autoRetryDelay);
  };

  private async reportError(error: DetectionError, errorInfo: React.ErrorInfo | null): Promise<void> {
    if (!this.props.errorReportingService) {
      return;
    }

    try {
      this.setState({ isReporting: true });
      await this.props.errorReportingService.reportError(error);
    } catch (reportingError) {
      console.error('Failed to report error:', reportingError);
    } finally {
      this.setState({ isReporting: false });
    }
  }

  private handleRetry = (): void => {
    this.setState(prevState => ({
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: prevState.retryCount + 1,
      showDetailDialog: false
    }));

    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
      this.retryTimeoutId = null;
    }
  };

  private handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0,
      showDetailDialog: false
    });

    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
      this.retryTimeoutId = null;
    }
  };

  private handleCopyError = async (): Promise<void> => {
    if (!this.state.error) return;

    const errorDetails = JSON.stringify({
      id: this.state.error.id,
      message: this.state.error.message,
      category: this.state.error.category,
      severity: this.state.error.severity,
      timestamp: this.state.error.timestamp,
      stack: this.state.error.stack,
      componentStack: this.state.errorInfo?.componentStack,
      additionalInfo: this.state.error.additionalInfo,
      retryCount: this.state.retryCount
    }, null, 2);

    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(errorDetails);
      } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = errorDetails;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
    } catch (err) {
      console.error('Failed to copy error details:', err);
    }
  };

  private getErrorIcon(category: ErrorCategory): ReactNode {
    switch (category) {
      case ErrorCategory.NETWORK:
        return <NetworkCheck color="error" />;
      case ErrorCategory.RENDERING:
        return <Computer color="error" />;
      case ErrorCategory.PROCESSING:
        return <VideoCameraBack color="error" />;
      case ErrorCategory.HARDWARE:
        return <Settings color="error" />;
      case ErrorCategory.AUTHENTICATION:
        return <Warning color="error" />;
      default:
        return <ErrorIcon color="error" />;
    }
  }

  private getErrorSeverityColor(severity: ErrorSeverity): 'error' | 'warning' | 'info' {
    switch (severity) {
      case ErrorSeverity.CRITICAL:
      case ErrorSeverity.HIGH:
        return 'error';
      case ErrorSeverity.MEDIUM:
        return 'warning';
      default:
        return 'info';
    }
  }

  private getRecoveryInstructions(error: DetectionError): string[] {
    const instructions: string[] = [];

    if (error.category === ErrorCategory.NETWORK) {
      instructions.push('Check your internet connection');
      instructions.push('Verify API endpoints are accessible');
      instructions.push('Try disabling browser extensions');
      instructions.push('Clear browser cache and cookies');
    } else if (error.category === ErrorCategory.RENDERING) {
      instructions.push('Update your graphics drivers');
      instructions.push('Try using a different browser');
      instructions.push('Disable hardware acceleration');
      instructions.push('Close other graphics-intensive applications');
    } else if (error.category === ErrorCategory.PROCESSING) {
      instructions.push('Ensure video format is supported');
      instructions.push('Check available system memory');
      instructions.push('Try processing smaller video segments');
      if (error.frame80Specific) {
        instructions.push('Frame 80 may contain corrupted data - try skipping this frame');
        instructions.push('Check video encoding quality around frame 80');
      }
    } else if (error.category === ErrorCategory.HARDWARE) {
      instructions.push('Check hardware connections');
      instructions.push('Verify device drivers are up to date');
      instructions.push('Restart the hardware device');
      instructions.push('Check USB connections and power supply');
    } else if (error.category === ErrorCategory.AUTHENTICATION) {
      instructions.push('Re-authenticate with the system');
      instructions.push('Check your permissions');
      instructions.push('Contact system administrator');
    } else {
      instructions.push('Try refreshing the page');
      instructions.push('Clear browser cache');
      instructions.push('Report this issue if it persists');
    }

    return instructions;
  }

  render(): ReactNode {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const { error } = this.state;
      const recoveryInstructions = this.getRecoveryInstructions(error);
      const isAutoRetrying = this.retryTimeoutId !== null;

      return (
        <Box sx={{ p: 3, maxWidth: 800, mx: 'auto', my: 4 }}>
          <Paper elevation={3} sx={{ p: 3 }}>
            <Alert 
              severity={this.getErrorSeverityColor(error.severity)}
              icon={this.getErrorIcon(error.category)}
              sx={{ mb: 3 }}
            >
              <AlertTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                Detection System Error
                <Chip 
                  label={error.category.toUpperCase()} 
                  size="small" 
                  color={this.getErrorSeverityColor(error.severity)}
                  variant="outlined"
                />
                <Chip 
                  label={error.severity.toUpperCase()} 
                  size="small" 
                  color={this.getErrorSeverityColor(error.severity)}
                />
              </AlertTitle>
              
              <Typography variant="body2" sx={{ mb: 2 }}>
                {error.message}
              </Typography>

              {error.frame80Specific && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  <AlertTitle>Frame 80 Detection Failure</AlertTitle>
                  This error is specific to frame 80 processing. This may indicate data corruption or 
                  processing limitations at this particular frame position.
                </Alert>
              )}

              {isAutoRetrying && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                    Auto-recovery in progress... (Attempt {this.state.retryCount + 1} of {this.maxRetries})
                  </Typography>
                  <LinearProgress />
                </Box>
              )}

              <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ gap: 1 }}>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<Refresh />}
                  onClick={this.handleRetry}
                  disabled={isAutoRetrying || this.state.isReporting}
                >
                  Retry Now
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<BugReport />}
                  onClick={() => this.setState({ showDetailDialog: true })}
                >
                  View Details
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<ContentCopy />}
                  onClick={this.handleCopyError}
                >
                  Copy Error
                </Button>
                <Button
                  variant="text"
                  size="small"
                  onClick={this.handleReset}
                  color="inherit"
                >
                  Reset Component
                </Button>
              </Stack>
            </Alert>

            {/* Recovery Instructions */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Info color="primary" />
                  Recovery Instructions
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  Try these steps to resolve the issue:
                </Typography>
                <Box component="ol" sx={{ pl: 2 }}>
                  {recoveryInstructions.map((instruction, index) => (
                    <Typography key={index} component="li" variant="body2" sx={{ mb: 1 }}>
                      {instruction}
                    </Typography>
                  ))}
                </Box>
              </AccordionDetails>
            </Accordion>

            {/* Retry Information */}
            {this.state.retryCount > 0 && (
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  Retry attempts: {this.state.retryCount} / {this.maxRetries}
                  {this.state.retryCount >= this.maxRetries && 
                    ' - Maximum retries reached. Manual intervention required.'}
                </Typography>
              </Alert>
            )}

            {/* Development Mode Details */}
            {process.env.NODE_ENV === 'development' && (
              <Accordion sx={{ mt: 2 }}>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6" color="warning.main">
                    Development Error Details
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" component="pre" sx={{ 
                    fontSize: '0.75rem',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    maxHeight: 300,
                    overflow: 'auto',
                    bgcolor: 'rgba(0, 0, 0, 0.05)',
                    p: 2,
                    borderRadius: 1,
                    border: '1px solid rgba(0, 0, 0, 0.1)'
                  }}>
                    <strong>Error ID:</strong> {error.id}
                    {'\n\n'}
                    <strong>Message:</strong> {error.message}
                    {'\n\n'}
                    <strong>Category:</strong> {error.category}
                    {'\n\n'}
                    <strong>Severity:</strong> {error.severity}
                    {'\n\n'}
                    <strong>Timestamp:</strong> {error.timestamp.toISOString()}
                    {'\n\n'}
                    <strong>Stack:</strong> {error.stack || 'No stack trace'}
                    {'\n\n'}
                    <strong>Component Stack:</strong> {this.state.errorInfo?.componentStack || 'No component stack'}
                    {error.additionalInfo && (
                      <>
                        {'\n\n'}
                        <strong>Additional Info:</strong> {JSON.stringify(error.additionalInfo, null, 2)}
                      </>
                    )}
                  </Typography>
                </AccordionDetails>
              </Accordion>
            )}
          </Paper>

          {/* Error Detail Dialog */}
          <Dialog
            open={this.state.showDetailDialog}
            onClose={() => this.setState({ showDetailDialog: false })}
            maxWidth="md"
            fullWidth
          >
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              Error Details
              <IconButton onClick={() => this.setState({ showDetailDialog: false })}>
                <Close />
              </IconButton>
            </DialogTitle>
            <DialogContent>
              <Typography variant="body2" component="pre" sx={{ 
                fontSize: '0.75rem',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                bgcolor: 'rgba(0, 0, 0, 0.05)',
                p: 2,
                borderRadius: 1,
                border: '1px solid rgba(0, 0, 0, 0.1)',
                maxHeight: 400,
                overflow: 'auto'
              }}>
                {JSON.stringify({
                  id: error.id,
                  message: error.message,
                  category: error.category,
                  severity: error.severity,
                  timestamp: error.timestamp,
                  stack: error.stack,
                  componentStack: this.state.errorInfo?.componentStack,
                  frame80Specific: error.frame80Specific,
                  canvasError: error.canvasError,
                  videoError: error.videoError,
                  apiError: error.apiError,
                  hardwareError: error.hardwareError,
                  additionalInfo: error.additionalInfo,
                  retryCount: this.state.retryCount
                }, null, 2)}
              </Typography>
            </DialogContent>
            <DialogActions>
              <Button onClick={this.handleCopyError} startIcon={<ContentCopy />}>
                Copy to Clipboard
              </Button>
              <Button onClick={() => this.setState({ showDetailDialog: false })}>
                Close
              </Button>
            </DialogActions>
          </Dialog>
        </Box>
      );
    }

    return this.props.children;
  }
}

// HOC wrapper for functional components with detection-specific features
export const withDetectionErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  options?: {
    fallback?: ReactNode;
    onError?: (error: DetectionError, errorInfo: React.ErrorInfo | null) => void;
    errorReportingService?: ErrorReportingService;
    maxRetries?: number;
    autoRetryDelay?: number;
    enableAutoRecovery?: boolean;
  }
) => {
  return (props: P) => (
    <DetectionErrorBoundary {...options}>
      <WrappedComponent {...props} />
    </DetectionErrorBoundary>
  );
};

// Utility function to create error reporting service
export const createErrorReportingService = (
  endpoint: string,
  apiKey?: string
): ErrorReportingService => {
  return {
    reportError: async (error: DetectionError) => {
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(apiKey && { 'Authorization': `Bearer ${apiKey}` })
          },
          body: JSON.stringify(error)
        });

        if (!response.ok) {
          throw new Error(`Failed to report error: ${response.statusText}`);
        }
      } catch (reportingError) {
        console.error('Error reporting failed:', reportingError);
        throw reportingError;
      }
    }
  };
};

export default DetectionErrorBoundary;