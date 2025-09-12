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
  Stepper,
  Step,
  StepLabel,
  StepContent,
  LinearProgress,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  BugReport as BugReportIcon,
  NetworkCheck as NetworkCheckIcon,
  CloudOff as CloudOffIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Autorenew as AutorenewIcon,
  OfflineBolt as OfflineIcon,
  Help as HelpIcon,
  Close as CloseIcon,
} from '@mui/icons-material';

import SmartErrorRecoveryEngine, { 
  SmartErrorType, 
  RecoveryPlan, 
  RecoveryAction,
  ErrorContext,
  RecoveryPriority 
} from '../../utils/smartErrorRecovery';

interface SmartErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorId: string;
  context: ErrorContext;
  recoveryPlan: RecoveryPlan | null;
  isRecovering: boolean;
  showDetails: boolean;
  showGuidance: boolean;
  activeStep: number;
  recoveryProgress: number;
  userInteractionRequired: boolean;
  preventionTipsShown: boolean;
}

interface SmartErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, context: ErrorContext) => void;
  onRecovery?: (successful: boolean, plan: RecoveryPlan) => void;
  component: string;
  operation?: string;
  level?: 'app' | 'page' | 'component' | 'widget';
  enableAutoRecovery?: boolean;
  maxRecoveryAttempts?: number;
  showRecoveryGuidance?: boolean;
  enableOfflineMode?: boolean;
}

class SmartErrorBoundary extends Component<SmartErrorBoundaryProps, SmartErrorBoundaryState> {
  private recoveryEngine: SmartErrorRecoveryEngine;
  private recoveryTimeoutId: NodeJS.Timeout | null = null;
  private progressIntervalId: NodeJS.Timeout | null = null;

  constructor(props: SmartErrorBoundaryProps) {
    super(props);
    
    this.recoveryEngine = new SmartErrorRecoveryEngine();
    
    this.state = {
      hasError: false,
      error: null,
      errorId: '',
      context: this.createErrorContext(),
      recoveryPlan: null,
      isRecovering: false,
      showDetails: false,
      showGuidance: false,
      activeStep: 0,
      recoveryProgress: 0,
      userInteractionRequired: false,
      preventionTipsShown: false,
    };
  }

  private createErrorContext(): ErrorContext {
    return {
      component: this.props.component,
      operation: this.props.operation || 'unknown',
      timestamp: Date.now(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      retryCount: 0,
      networkStatus: navigator.onLine ? 'online' : 'offline',
    };
  }

  static getDerivedStateFromError(error: Error): Partial<SmartErrorBoundaryState> {
    const errorId = `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    return {
      hasError: true,
      error,
      errorId,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const context: ErrorContext = {
      ...this.createErrorContext(),
      retryCount: this.state.context.retryCount,
    };

    // Generate recovery plan
    const recoveryPlan = this.recoveryEngine.generateRecoveryPlan(error, context);
    
    this.setState({
      context,
      recoveryPlan,
      userInteractionRequired: !recoveryPlan.actions.some(a => a.automatic),
    });

    // Log error for monitoring
    this.logError(error, context, recoveryPlan);

    // Call custom error handler
    if (this.props.onError) {
      this.props.onError(error, context);
    }

    // Start automatic recovery if enabled
    if (this.props.enableAutoRecovery !== false) {
      this.startAutomaticRecovery(recoveryPlan);
    }
  }

  private logError(error: Error, context: ErrorContext, plan: RecoveryPlan) {
    const logData = {
      errorId: this.state.errorId,
      errorType: plan.errorType,
      recoveryStrategy: plan.strategy,
      priority: plan.priority,
      estimatedRecoveryRate: plan.estimatedRecoveryRate,
      message: error.message,
      stack: error.stack,
      context,
      timestamp: new Date().toISOString(),
    };

    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 Smart Error Boundary (${plan.errorType.toUpperCase()})`);
      console.error('Error:', error);
      console.info('Recovery Plan:', plan);
      console.info('Context:', context);
      console.info('Log Data:', logData);
      console.groupEnd();
    }
  }

  private async startAutomaticRecovery(plan: RecoveryPlan) {
    const automaticActions = plan.actions.filter(action => action.automatic);
    
    if (automaticActions.length === 0) return;

    this.setState({ isRecovering: true, recoveryProgress: 0 });

    for (const action of automaticActions) {
      try {
        this.setState({ activeStep: plan.actions.indexOf(action) });
        
        if (action.estimatedTime && action.estimatedTime > 1) {
          this.startProgressIndicator(action.estimatedTime);
        }

        const result = await action.action();
        
        if (result === true) {
          // Recovery successful
          this.handleRecoverySuccess(plan);
          return;
        }
      } catch (recoveryError) {
        console.error('Recovery action failed:', recoveryError);
        continue;
      }
    }

    // If we reach here, automatic recovery failed
    this.setState({ 
      isRecovering: false, 
      userInteractionRequired: true,
      recoveryProgress: 0 
    });
  }

  private startProgressIndicator(estimatedTime: number) {
    let elapsed = 0;
    const interval = 100; // Update every 100ms

    this.progressIntervalId = setInterval(() => {
      elapsed += interval;
      const progress = Math.min((elapsed / (estimatedTime * 1000)) * 100, 95);
      this.setState({ recoveryProgress: progress });

      if (elapsed >= estimatedTime * 1000) {
        if (this.progressIntervalId) {
          clearInterval(this.progressIntervalId);
          this.progressIntervalId = null;
        }
      }
    }, interval);
  }

  private handleRecoverySuccess(plan: RecoveryPlan) {
    this.setState({ 
      isRecovering: false, 
      recoveryProgress: 100,
      hasError: false,
    });

    if (this.props.onRecovery) {
      this.props.onRecovery(true, plan);
    }

    // Reset after a brief success indication
    setTimeout(() => {
      this.resetErrorBoundary();
    }, 1000);
  }

  private async executeRecoveryAction(action: RecoveryAction, plan: RecoveryPlan) {
    this.setState({ isRecovering: true });

    try {
      if (action.estimatedTime && action.estimatedTime > 1) {
        this.startProgressIndicator(action.estimatedTime);
      }

      const result = await action.action();

      if (result === true) {
        this.handleRecoverySuccess(plan);
      } else {
        this.setState({ isRecovering: false, recoveryProgress: 0 });
      }
    } catch (recoveryError) {
      console.error('Manual recovery action failed:', recoveryError);
      this.setState({ isRecovering: false, recoveryProgress: 0 });
    }
  }

  private resetErrorBoundary = () => {
    if (this.recoveryTimeoutId) {
      clearTimeout(this.recoveryTimeoutId);
      this.recoveryTimeoutId = null;
    }
    
    if (this.progressIntervalId) {
      clearInterval(this.progressIntervalId);
      this.progressIntervalId = null;
    }

    this.setState({
      hasError: false,
      error: null,
      errorId: '',
      context: this.createErrorContext(),
      recoveryPlan: null,
      isRecovering: false,
      showDetails: false,
      showGuidance: false,
      activeStep: 0,
      recoveryProgress: 0,
      userInteractionRequired: false,
      preventionTipsShown: false,
    });
  };

  private toggleDetails = () => {
    this.setState({ showDetails: !this.state.showDetails });
  };

  private toggleGuidance = () => {
    this.setState({ showGuidance: !this.state.showGuidance });
  };

  private getErrorIcon(errorType: SmartErrorType) {
    switch (errorType) {
      case SmartErrorType.NETWORK_CONNECTION:
      case SmartErrorType.NETWORK_TIMEOUT:
        return <NetworkCheckIcon />;
      case SmartErrorType.API_SERVER_ERROR:
      case SmartErrorType.API_NOT_FOUND:
        return <CloudOffIcon />;
      case SmartErrorType.WEBSOCKET_CONNECTION:
      case SmartErrorType.WEBSOCKET_PROTOCOL:
        return <CloudOffIcon />;
      default:
        return <ErrorIcon />;
    }
  }

  private getSeverity(priority: RecoveryPriority): 'error' | 'warning' | 'info' {
    switch (priority) {
      case RecoveryPriority.CRITICAL:
        return 'error';
      case RecoveryPriority.HIGH:
        return 'warning';
      case RecoveryPriority.MEDIUM:
      case RecoveryPriority.LOW:
      default:
        return 'info';
    }
  }

  componentWillUnmount() {
    if (this.recoveryTimeoutId) {
      clearTimeout(this.recoveryTimeoutId);
    }
    if (this.progressIntervalId) {
      clearInterval(this.progressIntervalId);
    }
  }

  render() {
    const { 
      hasError, 
      recoveryPlan, 
      isRecovering, 
      showDetails, 
      showGuidance,
      recoveryProgress,
      userInteractionRequired,
      preventionTipsShown 
    } = this.state;
    const { children, fallback, showRecoveryGuidance = true } = this.props;

    if (hasError && recoveryPlan) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback;
      }

      const severity = this.getSeverity(recoveryPlan.priority);
      const errorIcon = this.getErrorIcon(recoveryPlan.errorType);

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
          {/* Main Error Alert */}
          <Alert 
            severity={severity} 
            icon={errorIcon}
            sx={{ mb: 2 }}
          >
            <AlertTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {recoveryPlan.priority === RecoveryPriority.CRITICAL ? 'Critical Issue' :
               recoveryPlan.priority === RecoveryPriority.HIGH ? 'Service Issue' : 
               'Temporary Issue'}
              
              <Chip 
                label={`${recoveryPlan.estimatedRecoveryRate}% recoverable`}
                size="small"
                color={recoveryPlan.estimatedRecoveryRate >= 90 ? 'success' : 
                       recoveryPlan.estimatedRecoveryRate >= 70 ? 'warning' : 'error'}
              />
            </AlertTitle>
            {recoveryPlan.userMessage}
          </Alert>

          {/* Recovery Progress */}
          {isRecovering && (
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <AutorenewIcon sx={{ mr: 1, fontSize: 20 }} className="rotating" />
                <Typography variant="body2" color="text.secondary">
                  Recovery in progress...
                </Typography>
              </Box>
              {recoveryProgress > 0 && (
                <LinearProgress 
                  variant="determinate" 
                  value={recoveryProgress} 
                  sx={{ height: 6, borderRadius: 3 }}
                />
              )}
            </Box>
          )}

          {/* Recovery Actions */}
          <Stack direction="row" spacing={2} sx={{ mb: 2, flexWrap: 'wrap' }}>
            {recoveryPlan.actions
              .filter(action => userInteractionRequired || !action.automatic)
              .map((action, index) => (
              <Button
                key={action.id}
                variant={action.primary ? 'contained' : 'outlined'}
                onClick={() => this.executeRecoveryAction(action, recoveryPlan)}
                disabled={isRecovering}
                size="small"
                startIcon={action.primary && !isRecovering ? <RefreshIcon /> : undefined}
                sx={{ mb: 1 }}
              >
                {action.label}
              </Button>
            ))}

            <Button
              variant="outlined"
              onClick={this.resetErrorBoundary}
              disabled={isRecovering}
              size="small"
              sx={{ mb: 1 }}
            >
              Reset
            </Button>

            {/* Help button */}
            {showRecoveryGuidance && (
              <Tooltip title="Show recovery guidance">
                <IconButton 
                  onClick={this.toggleGuidance}
                  size="small"
                  color="primary"
                >
                  <HelpIcon />
                </IconButton>
              </Tooltip>
            )}

            {/* Debug details for development */}
            {process.env.NODE_ENV === 'development' && (
              <Button
                variant="text"
                startIcon={showDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                onClick={this.toggleDetails}
                size="small"
              >
                {showDetails ? 'Hide' : 'Show'} Debug Info
              </Button>
            )}
          </Stack>

          {/* Recovery Guidance Dialog */}
          <Dialog
            open={showGuidance}
            onClose={this.toggleGuidance}
            maxWidth="md"
            fullWidth
          >
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              Recovery Guidance
              <IconButton onClick={this.toggleGuidance}>
                <CloseIcon />
              </IconButton>
            </DialogTitle>
            <DialogContent>
              <Stepper activeStep={-1} orientation="vertical">
                {recoveryPlan.guidanceSteps.map((step, index) => (
                  <Step key={index}>
                    <StepLabel>
                      <Typography variant="body1">{step}</Typography>
                    </StepLabel>
                  </Step>
                ))}
              </Stepper>

              {recoveryPlan.preventionTips && recoveryPlan.preventionTips.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Prevention Tips
                  </Typography>
                  {recoveryPlan.preventionTips.map((tip, index) => (
                    <Typography key={index} variant="body2" sx={{ mb: 1 }}>
                      • {tip}
                    </Typography>
                  ))}
                </Box>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={this.toggleGuidance}>Close</Button>
            </DialogActions>
          </Dialog>

          {/* Debug Information */}
          {process.env.NODE_ENV === 'development' && (
            <Collapse in={showDetails}>
              <Box
                sx={{
                  p: 2,
                  backgroundColor: theme => theme.palette.grey[100],
                  borderRadius: 1,
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  mt: 2,
                }}
              >
                <Typography variant="subtitle2" gutterBottom>
                  <BugReportIcon sx={{ mr: 1, verticalAlign: 'middle', fontSize: 16 }} />
                  Debug Information
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Error ID:</strong> {this.state.errorId}
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Error Type:</strong> {recoveryPlan.errorType}
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Recovery Strategy:</strong> {recoveryPlan.strategy}
                </Typography>

                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Priority:</strong> {recoveryPlan.priority}
                </Typography>

                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Component:</strong> {this.props.component}
                </Typography>
                
                <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                  <strong>Operation:</strong> {this.props.operation || 'N/A'}
                </Typography>
                
                {this.state.error?.message && (
                  <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                    <strong>Message:</strong> {this.state.error.message}
                  </Typography>
                )}
                
                {this.state.error?.stack && (
                  <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                    <strong>Stack:</strong>
                    <pre style={{ whiteSpace: 'pre-wrap', margin: '8px 0', fontSize: '0.75rem' }}>
                      {this.state.error.stack}
                    </pre>
                  </Typography>
                )}

                {recoveryPlan.technicalMessage && (
                  <Typography component="div" variant="body2" sx={{ mb: 1 }}>
                    <strong>Technical Details:</strong> {recoveryPlan.technicalMessage}
                  </Typography>
                )}
              </Box>
            </Collapse>
          )}

          {/* Support Contact */}
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
            If this problem persists, please contact support with error ID: <strong>{this.state.errorId}</strong>
            {recoveryPlan.escalationPath && (
              <> | <Button size="small" href={recoveryPlan.escalationPath}>Get Help</Button></>
            )}
          </Typography>

          <style>{`
            .rotating {
              animation: rotate 2s linear infinite;
            }
            
            @keyframes rotate {
              from {
                transform: rotate(0deg);
              }
              to {
                transform: rotate(360deg);
              }
            }
          `}</style>
        </Paper>
      );
    }

    return children;
  }
}

// Higher-order component for easier wrapping
export const withSmartErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  errorBoundaryProps: Omit<SmartErrorBoundaryProps, 'children'>
) => {
  const WithSmartErrorBoundaryComponent = (props: P) => (
    <SmartErrorBoundary {...errorBoundaryProps}>
      <WrappedComponent {...props} />
    </SmartErrorBoundary>
  );

  WithSmartErrorBoundaryComponent.displayName = 
    `withSmartErrorBoundary(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return WithSmartErrorBoundaryComponent;
};

export default SmartErrorBoundary;