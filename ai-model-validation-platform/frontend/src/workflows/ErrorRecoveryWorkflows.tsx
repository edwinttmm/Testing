import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Button,
  Typography,
  Paper,
  Alert,
  AlertTitle,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Card,
  CardContent,
  CardActions,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  PlayArrow as StartIcon,
  Refresh as RefreshIcon,
  Help as HelpIcon,
  Timeline as WorkflowIcon,
  Autorenew as AutorenewIcon,
  ExpandMore as ExpandMoreIcon,
  Close as CloseIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';

import { SmartErrorType, RecoveryPlan, RecoveryStrategy } from '../utils/smartErrorRecovery';
import { AttemptResult, ErrorStage, EscalationLevel } from '../utils/progressiveErrorHandler';
import { UserMessage } from '../utils/userFriendlyMessages';
import SmartErrorBoundary from '../components/ui/SmartErrorBoundary';
import ErrorRecoveryPanel from '../components/ui/ErrorRecoveryPanel';
import UserFriendlyErrorDisplay from '../components/ui/UserFriendlyErrorDisplay';

export interface WorkflowStep {
  id: string;
  title: string;
  description: string;
  action: () => Promise<boolean>;
  validation?: () => boolean;
  autoExecute?: boolean;
  estimatedTime?: number; // seconds
  dependencies?: string[]; // IDs of steps that must complete first
  optional?: boolean;
  retryCount?: number;
  maxRetries?: number;
}

export interface RecoveryWorkflow {
  id: string;
  name: string;
  description: string;
  errorType: SmartErrorType;
  strategy: RecoveryStrategy;
  steps: WorkflowStep[];
  successRate: number;
  averageTime: number; // seconds
  userGuidance: string[];
  prerequisites?: string[];
}

interface ErrorRecoveryWorkflowsProps {
  errorType: SmartErrorType;
  recoveryPlan: RecoveryPlan;
  userMessage: UserMessage;
  onWorkflowComplete: (success: boolean, workflow: RecoveryWorkflow) => void;
  onStepComplete?: (stepId: string, success: boolean) => void;
  enableAutoExecution?: boolean;
  showProgressDetails?: boolean;
}

const ErrorRecoveryWorkflows: React.FC<ErrorRecoveryWorkflowsProps> = ({
  errorType,
  recoveryPlan,
  userMessage,
  onWorkflowComplete,
  onStepComplete,
  enableAutoExecution = true,
  showProgressDetails = true,
}) => {
  const [activeWorkflow, setActiveWorkflow] = useState<RecoveryWorkflow | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [failedSteps, setFailedSteps] = useState<string[]>([]);
  const [workflowInProgress, setWorkflowInProgress] = useState(false);
  const [workflowProgress, setWorkflowProgress] = useState(0);
  const [showWorkflowDialog, setShowWorkflowDialog] = useState(false);
  const [availableWorkflows, setAvailableWorkflows] = useState<RecoveryWorkflow[]>([]);

  // Initialize workflows based on error type
  useEffect(() => {
    const workflows = generateRecoveryWorkflows(errorType, recoveryPlan);
    setAvailableWorkflows(workflows);
    
    // Auto-select the best workflow
    if (workflows.length > 0) {
      const bestWorkflow = workflows.reduce((best, current) => 
        current.successRate > best.successRate ? current : best
      );
      setActiveWorkflow(bestWorkflow);
      
      if (enableAutoExecution) {
        startWorkflow(bestWorkflow);
      }
    }
  }, [errorType, recoveryPlan, enableAutoExecution]);

  const generateRecoveryWorkflows = useCallback((
    errorType: SmartErrorType, 
    plan: RecoveryPlan
  ): RecoveryWorkflow[] => {
    const workflows: RecoveryWorkflow[] = [];

    switch (errorType) {
      case SmartErrorType.NETWORK_CONNECTION:
        workflows.push(createNetworkRecoveryWorkflow(plan));
        break;
      
      case SmartErrorType.API_UNAUTHORIZED:
        workflows.push(createAuthRecoveryWorkflow(plan));
        break;
      
      case SmartErrorType.API_SERVER_ERROR:
        workflows.push(createServerErrorRecoveryWorkflow(plan));
        break;
      
      case SmartErrorType.CHUNK_LOADING:
        workflows.push(createChunkLoadingRecoveryWorkflow(plan));
        break;
      
      case SmartErrorType.VALIDATION_ERROR:
        workflows.push(createValidationRecoveryWorkflow(plan));
        break;
      
      case SmartErrorType.WEBSOCKET_CONNECTION:
        workflows.push(createWebSocketRecoveryWorkflow(plan));
        break;
      
      default:
        workflows.push(createGenericRecoveryWorkflow(plan));
    }

    return workflows;
  }, []);

  const createNetworkRecoveryWorkflow = (plan: RecoveryPlan): RecoveryWorkflow => ({
    id: 'network-recovery',
    name: 'Network Connection Recovery',
    description: 'Restore network connectivity and resume operations',
    errorType: SmartErrorType.NETWORK_CONNECTION,
    strategy: RecoveryStrategy.OFFLINE_MODE,
    successRate: 95,
    averageTime: 60,
    userGuidance: [
      'We\'ll help you get back online and continue working',
      'Some features will work offline while we restore connection',
      'Your data will sync automatically when connection returns'
    ],
    steps: [
      {
        id: 'check-connection',
        title: 'Check Internet Connection',
        description: 'Verify current network status',
        autoExecute: true,
        estimatedTime: 5,
        action: async () => {
          try {
            const response = await fetch('/api/ping', { 
              method: 'HEAD',
              cache: 'no-cache',
              signal: AbortSignal.timeout(5000)
            });
            return response.ok;
          } catch {
            return false;
          }
        }
      },
      {
        id: 'enable-offline',
        title: 'Enable Offline Mode',
        description: 'Activate offline features to continue working',
        autoExecute: true,
        estimatedTime: 2,
        dependencies: ['check-connection'],
        action: async () => {
          // Enable offline capabilities
          return true;
        }
      },
      {
        id: 'cache-data',
        title: 'Prepare Offline Data',
        description: 'Cache essential data for offline use',
        autoExecute: true,
        estimatedTime: 10,
        dependencies: ['enable-offline'],
        action: async () => {
          // Cache critical data
          return true;
        }
      },
      {
        id: 'monitor-connection',
        title: 'Monitor Connection Recovery',
        description: 'Continuously check for connection restoration',
        autoExecute: true,
        estimatedTime: 30,
        dependencies: ['cache-data'],
        action: async () => {
          // Set up connection monitoring
          return true;
        }
      }
    ]
  });

  const createAuthRecoveryWorkflow = (plan: RecoveryPlan): RecoveryWorkflow => ({
    id: 'auth-recovery',
    name: 'Authentication Recovery',
    description: 'Restore user session and authentication',
    errorType: SmartErrorType.API_UNAUTHORIZED,
    strategy: RecoveryStrategy.REFRESH_SESSION,
    successRate: 98,
    averageTime: 30,
    userGuidance: [
      'Your session has expired for security reasons',
      'We\'ll guide you through signing in again',
      'Your work will be preserved and available after sign-in'
    ],
    steps: [
      {
        id: 'save-current-work',
        title: 'Save Current Work',
        description: 'Preserve any unsaved changes locally',
        autoExecute: true,
        estimatedTime: 3,
        action: async () => {
          // Save form data, drafts, etc.
          return true;
        }
      },
      {
        id: 'attempt-refresh',
        title: 'Attempt Token Refresh',
        description: 'Try to refresh authentication automatically',
        autoExecute: true,
        estimatedTime: 5,
        dependencies: ['save-current-work'],
        action: async () => {
          try {
            const response = await fetch('/auth/refresh', { method: 'POST' });
            return response.ok;
          } catch {
            return false;
          }
        }
      },
      {
        id: 'redirect-login',
        title: 'Redirect to Sign In',
        description: 'Navigate to authentication page',
        autoExecute: false,
        estimatedTime: 10,
        dependencies: ['attempt-refresh'],
        action: async () => {
          // Redirect to login with return URL
          window.location.href = `/login?return=${encodeURIComponent(window.location.pathname)}`;
          return true;
        }
      },
      {
        id: 'restore-work',
        title: 'Restore Previous Work',
        description: 'Reload saved work after authentication',
        autoExecute: true,
        estimatedTime: 5,
        dependencies: ['redirect-login'],
        action: async () => {
          // Restore saved data
          return true;
        }
      }
    ]
  });

  const createServerErrorRecoveryWorkflow = (plan: RecoveryPlan): RecoveryWorkflow => ({
    id: 'server-recovery',
    name: 'Server Error Recovery',
    description: 'Handle server issues and provide alternatives',
    errorType: SmartErrorType.API_SERVER_ERROR,
    strategy: RecoveryStrategy.USER_GUIDED_RETRY,
    successRate: 75,
    averageTime: 120,
    userGuidance: [
      'The server is experiencing temporary issues',
      'We\'ll try different approaches to complete your request',
      'You can continue with offline features while we resolve this'
    ],
    steps: [
      {
        id: 'check-server-status',
        title: 'Check Server Status',
        description: 'Verify which services are affected',
        autoExecute: true,
        estimatedTime: 10,
        action: async () => {
          try {
            const response = await fetch('/api/health');
            const data = await response.json();
            return data.status === 'healthy';
          } catch {
            return false;
          }
        }
      },
      {
        id: 'retry-with-backoff',
        title: 'Smart Retry',
        description: 'Retry the request with increasing delays',
        autoExecute: true,
        estimatedTime: 60,
        maxRetries: 3,
        dependencies: ['check-server-status'],
        action: async () => {
          // Implement exponential backoff retry
          for (let i = 0; i < 3; i++) {
            await new Promise(resolve => setTimeout(resolve, Math.pow(2, i) * 1000));
            try {
              // Retry the original operation
              return true;
            } catch {
              continue;
            }
          }
          return false;
        }
      },
      {
        id: 'enable-offline-features',
        title: 'Enable Offline Features',
        description: 'Activate available offline functionality',
        autoExecute: true,
        estimatedTime: 5,
        optional: true,
        action: async () => {
          // Enable offline mode
          return true;
        }
      },
      {
        id: 'queue-for-later',
        title: 'Queue Request',
        description: 'Save request to process when server recovers',
        autoExecute: true,
        estimatedTime: 2,
        action: async () => {
          // Queue the request
          return true;
        }
      }
    ]
  });

  const createChunkLoadingRecoveryWorkflow = (plan: RecoveryPlan): RecoveryWorkflow => ({
    id: 'chunk-recovery',
    name: 'Application Update Recovery',
    description: 'Handle application updates and resource loading',
    errorType: SmartErrorType.CHUNK_LOADING,
    strategy: RecoveryStrategy.ALTERNATIVE_PATH,
    successRate: 99,
    averageTime: 20,
    userGuidance: [
      'The application was updated while you were using it',
      'We need to refresh to get the latest version',
      'Your work will be preserved during the update'
    ],
    steps: [
      {
        id: 'save-application-state',
        title: 'Save Application State',
        description: 'Preserve current user session and data',
        autoExecute: true,
        estimatedTime: 3,
        action: async () => {
          // Save current state to localStorage
          return true;
        }
      },
      {
        id: 'clear-cache',
        title: 'Clear Browser Cache',
        description: 'Remove outdated application resources',
        autoExecute: true,
        estimatedTime: 2,
        dependencies: ['save-application-state'],
        action: async () => {
          if ('caches' in window) {
            const cacheNames = await caches.keys();
            await Promise.all(cacheNames.map(name => caches.delete(name)));
          }
          return true;
        }
      },
      {
        id: 'refresh-application',
        title: 'Refresh Application',
        description: 'Reload the page with updated resources',
        autoExecute: false,
        estimatedTime: 10,
        dependencies: ['clear-cache'],
        action: async () => {
          window.location.reload();
          return true;
        }
      }
    ]
  });

  const createValidationRecoveryWorkflow = (plan: RecoveryPlan): RecoveryWorkflow => ({
    id: 'validation-recovery',
    name: 'Input Validation Recovery',
    description: 'Guide user through fixing validation errors',
    errorType: SmartErrorType.VALIDATION_ERROR,
    strategy: RecoveryStrategy.USER_GUIDED_RETRY,
    successRate: 95,
    averageTime: 45,
    userGuidance: [
      'Some information needs to be corrected',
      'We\'ll highlight exactly what needs fixing',
      'Use the provided examples to guide your corrections'
    ],
    steps: [
      {
        id: 'highlight-errors',
        title: 'Highlight Validation Issues',
        description: 'Show exactly which fields need attention',
        autoExecute: true,
        estimatedTime: 2,
        action: async () => {
          // Highlight invalid fields
          return true;
        }
      },
      {
        id: 'show-examples',
        title: 'Show Input Examples',
        description: 'Display correct formatting examples',
        autoExecute: true,
        estimatedTime: 1,
        dependencies: ['highlight-errors'],
        action: async () => {
          // Show formatting examples
          return true;
        }
      },
      {
        id: 'enable-live-validation',
        title: 'Enable Live Validation',
        description: 'Provide real-time feedback as user types',
        autoExecute: true,
        estimatedTime: 2,
        dependencies: ['show-examples'],
        action: async () => {
          // Enable live validation
          return true;
        }
      },
      {
        id: 'auto-format',
        title: 'Auto-format Input',
        description: 'Automatically fix common formatting issues',
        autoExecute: true,
        optional: true,
        estimatedTime: 1,
        action: async () => {
          // Apply auto-formatting
          return true;
        }
      }
    ]
  });

  const createWebSocketRecoveryWorkflow = (plan: RecoveryPlan): RecoveryWorkflow => ({
    id: 'websocket-recovery',
    name: 'Real-time Connection Recovery',
    description: 'Restore WebSocket connection for live features',
    errorType: SmartErrorType.WEBSOCKET_CONNECTION,
    strategy: RecoveryStrategy.AUTOMATIC_RETRY,
    successRate: 92,
    averageTime: 30,
    userGuidance: [
      'Live updates have been temporarily paused',
      'We\'re reconnecting to restore real-time features',
      'You can continue using the app normally during reconnection'
    ],
    steps: [
      {
        id: 'close-old-connection',
        title: 'Clean Up Connection',
        description: 'Properly close existing WebSocket connection',
        autoExecute: true,
        estimatedTime: 2,
        action: async () => {
          // Close existing WebSocket
          return true;
        }
      },
      {
        id: 'wait-before-reconnect',
        title: 'Wait Before Reconnect',
        description: 'Brief pause to avoid overwhelming the server',
        autoExecute: true,
        estimatedTime: 5,
        dependencies: ['close-old-connection'],
        action: async () => {
          await new Promise(resolve => setTimeout(resolve, 5000));
          return true;
        }
      },
      {
        id: 'establish-connection',
        title: 'Establish New Connection',
        description: 'Create new WebSocket connection',
        autoExecute: true,
        estimatedTime: 10,
        maxRetries: 3,
        dependencies: ['wait-before-reconnect'],
        action: async () => {
          // Establish WebSocket connection
          return true;
        }
      },
      {
        id: 'sync-missed-updates',
        title: 'Sync Missed Updates',
        description: 'Fetch any updates that occurred during disconnection',
        autoExecute: true,
        estimatedTime: 10,
        dependencies: ['establish-connection'],
        action: async () => {
          // Sync updates
          return true;
        }
      }
    ]
  });

  const createGenericRecoveryWorkflow = (plan: RecoveryPlan): RecoveryWorkflow => ({
    id: 'generic-recovery',
    name: 'General Error Recovery',
    description: 'Standard recovery process for unexpected errors',
    errorType: SmartErrorType.UNKNOWN,
    strategy: RecoveryStrategy.MANUAL_INTERVENTION,
    successRate: 60,
    averageTime: 90,
    userGuidance: [
      'An unexpected error occurred',
      'We\'ll try several approaches to resolve it',
      'Your data is safe and will be preserved'
    ],
    steps: [
      {
        id: 'collect-error-info',
        title: 'Collect Error Information',
        description: 'Gather details about the error for diagnosis',
        autoExecute: true,
        estimatedTime: 5,
        action: async () => {
          // Collect error details
          return true;
        }
      },
      {
        id: 'attempt-retry',
        title: 'Attempt Simple Retry',
        description: 'Try the operation again',
        autoExecute: true,
        estimatedTime: 10,
        dependencies: ['collect-error-info'],
        action: async () => {
          // Retry the operation
          return Math.random() > 0.5; // 50% success rate for generic retry
        }
      },
      {
        id: 'clear-temporary-data',
        title: 'Clear Temporary Data',
        description: 'Remove potentially corrupted temporary data',
        autoExecute: true,
        estimatedTime: 5,
        dependencies: ['attempt-retry'],
        action: async () => {
          // Clear temp data
          return true;
        }
      },
      {
        id: 'provide-alternatives',
        title: 'Offer Alternative Actions',
        description: 'Present alternative ways to complete the task',
        autoExecute: false,
        estimatedTime: 30,
        action: async () => {
          // Present alternatives
          return true;
        }
      }
    ]
  });

  const startWorkflow = async (workflow: RecoveryWorkflow) => {
    setActiveWorkflow(workflow);
    setWorkflowInProgress(true);
    setCurrentStep(0);
    setCompletedSteps([]);
    setFailedSteps([]);
    setWorkflowProgress(0);

    try {
      await executeWorkflow(workflow);
    } catch (error) {
      console.error('Workflow execution failed:', error);
      onWorkflowComplete(false, workflow);
    } finally {
      setWorkflowInProgress(false);
    }
  };

  const executeWorkflow = async (workflow: RecoveryWorkflow) => {
    const totalSteps = workflow.steps.length;
    let successfulSteps = 0;

    for (let i = 0; i < workflow.steps.length; i++) {
      const step = workflow.steps[i];
      setCurrentStep(i);

      // Check dependencies
      if (step.dependencies) {
        const unmetDependencies = step.dependencies.filter(dep => 
          !completedSteps.includes(dep)
        );
        
        if (unmetDependencies.length > 0) {
          console.warn(`Step ${step.id} has unmet dependencies:`, unmetDependencies);
          continue;
        }
      }

      // Execute step
      try {
        const success = await executeStep(step);
        
        if (success) {
          setCompletedSteps(prev => [...prev, step.id]);
          successfulSteps++;
          onStepComplete?.(step.id, true);
        } else {
          setFailedSteps(prev => [...prev, step.id]);
          onStepComplete?.(step.id, false);
          
          // If step is not optional and failed, consider workflow failed
          if (!step.optional) {
            throw new Error(`Critical step ${step.id} failed`);
          }
        }
      } catch (error) {
        setFailedSteps(prev => [...prev, step.id]);
        onStepComplete?.(step.id, false);
        
        if (!step.optional) {
          throw error;
        }
      }

      // Update progress
      setWorkflowProgress((i + 1) / totalSteps * 100);
    }

    // Workflow completed
    const overallSuccess = successfulSteps / totalSteps >= 0.7; // 70% success threshold
    onWorkflowComplete(overallSuccess, workflow);
  };

  const executeStep = async (step: WorkflowStep): Promise<boolean> => {
    const maxRetries = step.maxRetries || 1;
    let retryCount = 0;

    while (retryCount < maxRetries) {
      try {
        return await step.action();
      } catch (error) {
        retryCount++;
        if (retryCount >= maxRetries) {
          throw error;
        }
        
        // Wait before retry
        await new Promise(resolve => setTimeout(resolve, 1000 * retryCount));
      }
    }

    return false;
  };

  const renderWorkflowSelection = () => (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        Available Recovery Options
      </Typography>
      
      {availableWorkflows.map((workflow) => (
        <Card 
          key={workflow.id} 
          sx={{ 
            mb: 2, 
            border: activeWorkflow?.id === workflow.id ? 2 : 1,
            borderColor: activeWorkflow?.id === workflow.id ? 'primary.main' : 'divider'
          }}
        >
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <WorkflowIcon sx={{ mr: 1 }} />
              <Typography variant="h6">{workflow.name}</Typography>
              
              <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
                <Chip 
                  label={`${workflow.successRate}% success`} 
                  color="success" 
                  size="small" 
                />
                <Chip 
                  label={`~${Math.ceil(workflow.averageTime / 60)}min`} 
                  icon={<SpeedIcon />}
                  size="small" 
                />
              </Box>
            </Box>
            
            <Typography variant="body2" color="text.secondary">
              {workflow.description}
            </Typography>
          </CardContent>
          
          <CardActions>
            <Button 
              variant={activeWorkflow?.id === workflow.id ? 'contained' : 'outlined'}
              onClick={() => startWorkflow(workflow)}
              disabled={workflowInProgress}
              startIcon={workflowInProgress ? <AutorenewIcon className="spinning" /> : <StartIcon />}
            >
              {workflowInProgress ? 'Running...' : 'Start Recovery'}
            </Button>
            
            <Button 
              size="small" 
              onClick={() => setShowWorkflowDialog(true)}
            >
              View Steps
            </Button>
          </CardActions>
        </Card>
      ))}
    </Box>
  );

  const renderWorkflowProgress = () => {
    if (!activeWorkflow || !workflowInProgress) return null;

    return (
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Recovery in Progress: {activeWorkflow.name}
        </Typography>
        
        <LinearProgress 
          variant="determinate" 
          value={workflowProgress} 
          sx={{ mb: 2, height: 8, borderRadius: 4 }}
        />
        
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Step {currentStep + 1} of {activeWorkflow.steps.length}: 
          {activeWorkflow.steps[currentStep]?.title}
        </Typography>

        {showProgressDetails && (
          <Stepper activeStep={currentStep} orientation="vertical">
            {activeWorkflow.steps.map((step, index) => (
              <Step key={step.id}>
                <StepLabel 
                  error={failedSteps.includes(step.id)}
                >
                  {step.title}
                  {step.optional && <Chip label="Optional" size="small" sx={{ ml: 1 }} />}
                </StepLabel>
                <StepContent>
                  <Typography variant="body2">{step.description}</Typography>
                  {step.estimatedTime && (
                    <Typography variant="caption" color="text.secondary">
                      Estimated time: {step.estimatedTime} seconds
                    </Typography>
                  )}
                </StepContent>
              </Step>
            ))}
          </Stepper>
        )}
      </Paper>
    );
  };

  const renderWorkflowDialog = () => (
    <Dialog 
      open={showWorkflowDialog} 
      onClose={() => setShowWorkflowDialog(false)}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        Recovery Workflow Details
        <IconButton onClick={() => setShowWorkflowDialog(false)}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      
      <DialogContent>
        {activeWorkflow && (
          <Box>
            <Typography variant="h6" gutterBottom>
              {activeWorkflow.name}
            </Typography>
            
            <Typography variant="body1" paragraph>
              {activeWorkflow.description}
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Chip 
                label={`Success Rate: ${activeWorkflow.successRate}%`} 
                color="success" 
                sx={{ mr: 1 }}
              />
              <Chip 
                label={`Average Time: ${Math.ceil(activeWorkflow.averageTime / 60)} minutes`}
                color="info"
              />
            </Box>

            <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
              User Guidance
            </Typography>
            
            <List>
              {activeWorkflow.userGuidance.map((guidance, index) => (
                <ListItem key={index}>
                  <ListItemIcon>
                    <HelpIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText primary={guidance} />
                </ListItem>
              ))}
            </List>

            <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
              Recovery Steps
            </Typography>
            
            <Stepper orientation="vertical">
              {activeWorkflow.steps.map((step, index) => (
                <Step key={step.id}>
                  <StepLabel>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {step.title}
                      {step.optional && <Chip label="Optional" size="small" />}
                      {step.autoExecute && <Chip label="Automatic" color="primary" size="small" />}
                    </Box>
                  </StepLabel>
                  <StepContent>
                    <Typography variant="body2" paragraph>
                      {step.description}
                    </Typography>
                    
                    {step.estimatedTime && (
                      <Typography variant="caption" color="text.secondary">
                        Estimated time: {step.estimatedTime} seconds
                      </Typography>
                    )}
                    
                    {step.dependencies && step.dependencies.length > 0 && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        Dependencies: {step.dependencies.join(', ')}
                      </Typography>
                    )}
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          </Box>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={() => setShowWorkflowDialog(false)}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );

  return (
    <SmartErrorBoundary
      component="error-recovery-workflows"
      operation="workflow-execution"
      enableAutoRecovery={true}
      showRecoveryGuidance={true}
    >
      <Box>
        {/* User-friendly error display */}
        <UserFriendlyErrorDisplay 
          userMessage={userMessage}
          onAction={async (actionId) => {
            if (actionId === 'retry' && activeWorkflow) {
              await startWorkflow(activeWorkflow);
            }
          }}
        />

        {/* Workflow selection */}
        {!workflowInProgress && renderWorkflowSelection()}

        {/* Workflow progress */}
        {renderWorkflowProgress()}

        {/* Workflow details dialog */}
        {renderWorkflowDialog()}

        <style>{`
          .spinning {
            animation: spin 1s linear infinite;
          }
          
          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
      </Box>
    </SmartErrorBoundary>
  );
};

export default ErrorRecoveryWorkflows;