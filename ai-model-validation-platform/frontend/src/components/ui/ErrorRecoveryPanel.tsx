import React, { useState } from 'react';
// useEffect removed - not used in component
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  AlertTitle,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  LinearProgress,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Tooltip,
  Stack,
  Divider,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  CheckCircle as _CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Help as HelpIcon,
  BugReport as BugReportIcon,
  Send as SendIcon,
  ContentCopy as CopyIcon,
  Timeline as TimelineIcon,
  Autorenew as AutorenewIcon,
  Close as CloseIcon,
} from '@mui/icons-material';

import { 
  AttemptResult, 
  ErrorStage, 
  EscalationLevel, 
  ProgressiveErrorState 
} from '../../utils/progressiveErrorHandler';
import { RecoveryPlan, SmartErrorType as _SmartErrorType } from '../../utils/smartErrorRecovery';

interface ErrorRecoveryPanelProps {
  attemptResult: AttemptResult<unknown>;
  errorState: ProgressiveErrorState;
  recoveryPlan?: RecoveryPlan;
  onRetry?: () => Promise<void>;
  onAlternativeAction?: (actionId: string) => Promise<void>;
  onEscalateToSupport?: (details: string) => Promise<void>;
  onDismiss?: () => void;
  showTechnicalDetails?: boolean;
  enableSupportEscalation?: boolean;
}

const ErrorRecoveryPanel: React.FC<ErrorRecoveryPanelProps> = ({
  attemptResult,
  errorState,
  // _recoveryPlan removed - unused prop
  onRetry,
  onAlternativeAction,
  onEscalateToSupport,
  onDismiss,
  showTechnicalDetails = false,
  enableSupportEscalation = true,
}) => {
  const [activeStep, setActiveStep] = useState(0);
  const [showSupportDialog, setShowSupportDialog] = useState(false);
  const [supportDetails, setSupportDetails] = useState('');
  const [isRetrying, setIsRetrying] = useState(false);
  const [expandedAccordion, setExpandedAccordion] = useState<string | false>(false);

  const getSeverityIcon = () => {
    switch (attemptResult.escalationLevel) {
      case EscalationLevel.SUPPORT_CONTACT:
        return <ErrorIcon color="error" />;
      case EscalationLevel.USER_INTERVENTION:
        return <WarningIcon color="warning" />;
      case EscalationLevel.ALTERNATIVE_APPROACH:
        return <InfoIcon color="info" />;
      default:
        return <WarningIcon color="warning" />;
    }
  };

  const getSeverity = (): 'error' | 'warning' | 'info' => {
    switch (attemptResult.escalationLevel) {
      case EscalationLevel.SUPPORT_CONTACT:
        return 'error';
      case EscalationLevel.USER_INTERVENTION:
        return 'warning';
      default:
        return 'info';
    }
  };

  const getStageColor = (stage: ErrorStage): 'primary' | 'warning' | 'error' => {
    switch (stage) {
      case ErrorStage.TRY:
        return 'primary';
      case ErrorStage.RETRY:
        return 'warning';
      case ErrorStage.ESCALATE:
        return 'error';
      default:
        return 'primary';
    }
  };

  const handleRetry = async () => {
    if (!onRetry) return;
    
    setIsRetrying(true);
    try {
      await onRetry();
    } finally {
      setIsRetrying(false);
    }
  };

  const handleAlternativeAction = async (actionId: string) => {
    if (!onAlternativeAction) return;
    
    try {
      await onAlternativeAction(actionId);
    } catch (error) {
      // Alternative action failed, handled silently
    }
  };

  const handleSupportEscalation = async () => {
    if (!onEscalateToSupport) return;
    
    try {
      await onEscalateToSupport(supportDetails);
      setShowSupportDialog(false);
      setSupportDetails('');
    } catch (error) {
      // Support escalation failed, handled silently
    }
  };

  const copyErrorDetails = () => {
    const errorDetails = {
      stage: attemptResult.stage,
      escalationLevel: attemptResult.escalationLevel,
      attempts: errorState.totalAttempts,
      errors: errorState.errors.map(e => e.message),
      timestamp: new Date().toISOString(),
      url: window.location.href,
    };
    
    navigator.clipboard.writeText(JSON.stringify(errorDetails, null, 2));
  };

  const renderProgressIndicator = () => (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <TimelineIcon />
        Error Recovery Progress
      </Typography>
      
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Chip 
          label={`Stage: ${attemptResult.stage.toUpperCase()}`}
          color={getStageColor(attemptResult.stage)}
          size="small"
        />
        <Chip 
          label={`Attempt ${errorState.attemptCount}/${errorState.totalAttempts}`}
          variant="outlined"
          size="small"
        />
        {attemptResult.escalationLevel && (
          <Chip 
            label={attemptResult.escalationLevel.replace('_', ' ').toUpperCase()}
            color={getSeverity()}
            size="small"
          />
        )}
      </Box>

      <LinearProgress 
        variant="determinate" 
        value={(errorState.attemptCount / Math.max(errorState.totalAttempts, 1)) * 100}
        sx={{ height: 8, borderRadius: 4 }}
        color={getStageColor(attemptResult.stage)}
      />
    </Box>
  );

  const renderGuidanceSteps = () => {
    if (!attemptResult.guidance || attemptResult.guidance.length === 0) return null;

    return (
      <Accordion 
        expanded={expandedAccordion === 'guidance'} 
        onChange={(_, isExpanded) => setExpandedAccordion(isExpanded ? 'guidance' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Recovery Guidance</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stepper activeStep={activeStep} orientation="vertical">
            {attemptResult.guidance.map((step, index) => (
              <Step key={index}>
                <StepLabel 
                  onClick={() => setActiveStep(index)}
                  sx={{ cursor: 'pointer' }}
                >
                  {step}
                </StepLabel>
                <StepContent>
                  <Box sx={{ mb: 2 }}>
                    <Button
                      variant="contained"
                      onClick={() => setActiveStep(index + 1)}
                      sx={{ mt: 1, mr: 1 }}
                      size="small"
                    >
                      {index === attemptResult.guidance!.length - 1 ? 'Complete' : 'Next Step'}
                    </Button>
                  </Box>
                </StepContent>
              </Step>
            ))}
          </Stepper>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderAlternativeActions = () => {
    if (!attemptResult.alternatives || attemptResult.alternatives.length === 0) return null;

    return (
      <Accordion 
        expanded={expandedAccordion === 'alternatives'} 
        onChange={(_, isExpanded) => setExpandedAccordion(isExpanded ? 'alternatives' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Alternative Solutions</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Try these alternative approaches to achieve your goal:
          </Typography>
          
          <List>
            {attemptResult.alternatives.map((alternative, index) => (
              <ListItem 
                key={index}
                sx={{ 
                  border: 1, 
                  borderColor: 'divider', 
                  borderRadius: 1, 
                  mb: 1,
                  flexDirection: 'column',
                  alignItems: 'stretch'
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                  <ListItemIcon>
                    <InfoIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={alternative.label}
                    secondary={alternative.description}
                  />
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => handleAlternativeAction(alternative.label)}
                  >
                    Try This
                  </Button>
                </Box>
              </ListItem>
            ))}
          </List>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderTechnicalDetails = () => {
    if (!showTechnicalDetails || !attemptResult.error) return null;

    return (
      <Accordion 
        expanded={expandedAccordion === 'technical'} 
        onChange={(_, isExpanded) => setExpandedAccordion(isExpanded ? 'technical' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <BugReportIcon />
            Technical Details
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
            <Typography component="div" variant="body2" sx={{ mb: 1 }}>
              <strong>Error Message:</strong> {attemptResult.error.message}
            </Typography>
            
            <Typography component="div" variant="body2" sx={{ mb: 1 }}>
              <strong>Stage:</strong> {attemptResult.stage}
            </Typography>
            
            <Typography component="div" variant="body2" sx={{ mb: 1 }}>
              <strong>Escalation Level:</strong> {attemptResult.escalationLevel}
            </Typography>
            
            <Typography component="div" variant="body2" sx={{ mb: 1 }}>
              <strong>Attempts:</strong> {errorState.attemptCount}/{errorState.totalAttempts}
            </Typography>
            
            {attemptResult.error.stack && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <strong>Stack Trace:</strong>
                  <Tooltip title="Copy error details">
                    <IconButton size="small" onClick={copyErrorDetails}>
                      <CopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Typography>
                <pre style={{ 
                  whiteSpace: 'pre-wrap', 
                  backgroundColor: '#f5f5f5', 
                  padding: '8px', 
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  overflow: 'auto',
                  maxHeight: '200px'
                }}>
                  {attemptResult.error.stack}
                </pre>
              </Box>
            )}
          </Box>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderRecoveryActions = () => (
    <Box sx={{ mt: 3 }}>
      <Stack direction="row" spacing={2} flexWrap="wrap">
        {onRetry && (
          <Button
            variant="contained"
            startIcon={isRetrying ? <AutorenewIcon className="spinning" /> : <RefreshIcon />}
            onClick={handleRetry}
            disabled={isRetrying}
          >
            {isRetrying ? 'Retrying...' : 'Try Again'}
          </Button>
        )}

        {enableSupportEscalation && attemptResult.escalationLevel === EscalationLevel.SUPPORT_CONTACT && (
          <Button
            variant="outlined"
            startIcon={<HelpIcon />}
            onClick={() => setShowSupportDialog(true)}
            color="error"
          >
            Contact Support
          </Button>
        )}

        {onDismiss && (
          <Button
            variant="text"
            onClick={onDismiss}
          >
            Dismiss
          </Button>
        )}
      </Stack>
    </Box>
  );

  const renderSupportDialog = () => (
    <Dialog open={showSupportDialog} onClose={() => setShowSupportDialog(false)} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        Contact Technical Support
        <IconButton onClick={() => setShowSupportDialog(false)}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Please provide additional details about what you were trying to do when this error occurred.
          Technical details have been automatically included.
        </Typography>
        
        <TextField
          autoFocus
          multiline
          rows={4}
          fullWidth
          label="Additional Details (Optional)"
          value={supportDetails}
          onChange={(e) => setSupportDetails(e.target.value)}
          placeholder="Describe what you were trying to do, any specific steps that led to this error, or any other relevant information..."
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setShowSupportDialog(false)}>Cancel</Button>
        <Button 
          onClick={handleSupportEscalation} 
          variant="contained" 
          startIcon={<SendIcon />}
        >
          Send to Support
        </Button>
      </DialogActions>
    </Dialog>
  );

  return (
    <Paper elevation={3} sx={{ p: 3, m: 2, maxWidth: 800 }}>
      {/* Main Alert */}
      <Alert severity={getSeverity()} icon={getSeverityIcon()} sx={{ mb: 3 }}>
        <AlertTitle>
          {attemptResult.escalationLevel === EscalationLevel.SUPPORT_CONTACT && 'Technical Support Required'}
          {attemptResult.escalationLevel === EscalationLevel.USER_INTERVENTION && 'Your Action Required'}
          {attemptResult.escalationLevel === EscalationLevel.ALTERNATIVE_APPROACH && 'Alternative Solutions Available'}
          {attemptResult.escalationLevel === EscalationLevel.GUIDED_RETRY && 'Let\'s Fix This Together'}
          {!attemptResult.escalationLevel && 'Error Recovery Options'}
        </AlertTitle>
        
        {attemptResult.error?.message || 'An error occurred during the operation.'}
      </Alert>

      {/* Progress Indicator */}
      {renderProgressIndicator()}

      <Divider sx={{ my: 2 }} />

      {/* Recovery Content */}
      <Box sx={{ mt: 2 }}>
        {renderGuidanceSteps()}
        {renderAlternativeActions()}
        {renderTechnicalDetails()}
      </Box>

      {/* Recovery Actions */}
      {renderRecoveryActions()}

      {/* Support Dialog */}
      {renderSupportDialog()}

      {/* Styling for animations */}
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
    </Paper>
  );
};

export default ErrorRecoveryPanel;