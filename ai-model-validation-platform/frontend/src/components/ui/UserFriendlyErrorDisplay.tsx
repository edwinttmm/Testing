import React, { useState, useEffect } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Typography,
  Button,
  Collapse,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
  Paper,
  IconButton,
  Tooltip,
  Stack,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  CheckCircle as SuccessIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Lightbulb as SuggestionIcon,
  PlayArrow as NextStepIcon,
  Schedule as TimeIcon,
  Help as HelpIcon,
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Autorenew as AutorenewIcon,
} from '@mui/icons-material';

import { UserMessage, MessageCategory, generateHelpText } from '../../utils/userFriendlyMessages';

interface UserFriendlyErrorDisplayProps {
  userMessage: UserMessage;
  onAction?: (actionId: string) => Promise<void>;
  onDismiss?: () => void;
  showTechnicalDetails?: boolean;
  enableAutoActions?: boolean;
  audience?: 'beginner' | 'intermediate' | 'advanced';
  compact?: boolean;
}

const UserFriendlyErrorDisplay: React.FC<UserFriendlyErrorDisplayProps> = ({
  userMessage,
  onAction,
  onDismiss,
  showTechnicalDetails = false,
  enableAutoActions = true,
  audience = 'intermediate',
  compact = false,
}) => {
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [showNextSteps, setShowNextSteps] = useState(true);
  const [showHelp, setShowHelp] = useState(false);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  const getSeverityIcon = () => {
    switch (userMessage.severity) {
      case 'error':
        return <ErrorIcon color="error" />;
      case 'warning':
        return <WarningIcon color="warning" />;
      case 'info':
        return <InfoIcon color="info" />;
      case 'success':
        return <SuccessIcon color="success" />;
      default:
        return <InfoIcon />;
    }
  };

  const getCategoryColor = (category: MessageCategory): 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success' => {
    switch (category) {
      case MessageCategory.CONNECTION:
        return 'warning';
      case MessageCategory.AUTHENTICATION:
        return 'info';
      case MessageCategory.PERMISSIONS:
        return 'error';
      case MessageCategory.DATA:
        return 'primary';
      case MessageCategory.SYSTEM:
        return 'error';
      case MessageCategory.USER_INPUT:
        return 'warning';
      case MessageCategory.RESOURCES:
        return 'secondary';
      case MessageCategory.TEMPORARY:
        return 'info';
      default:
        return 'primary';
    }
  };

  const getCategoryLabel = (category: MessageCategory): string => {
    switch (category) {
      case MessageCategory.CONNECTION:
        return 'Connection';
      case MessageCategory.AUTHENTICATION:
        return 'Sign In';
      case MessageCategory.PERMISSIONS:
        return 'Access';
      case MessageCategory.DATA:
        return 'Data';
      case MessageCategory.SYSTEM:
        return 'System';
      case MessageCategory.USER_INPUT:
        return 'Input';
      case MessageCategory.RESOURCES:
        return 'Resources';
      case MessageCategory.TEMPORARY:
        return 'Temporary';
      default:
        return 'General';
    }
  };

  const handleAction = async (actionId: string) => {
    if (!onAction) return;

    setIsProcessing(true);
    try {
      await onAction(actionId);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleStepComplete = (stepIndex: number) => {
    setCompletedSteps(prev => [...prev, stepIndex]);
  };

  const renderMainAlert = () => (
    <Alert 
      severity={userMessage.severity} 
      icon={getSeverityIcon()}
      action={
        onDismiss && (
          <IconButton
            aria-label="dismiss"
            color="inherit"
            size="small"
            onClick={onDismiss}
          >
            <CloseIcon fontSize="inherit" />
          </IconButton>
        )
      }
      sx={{ mb: 2 }}
    >
      <AlertTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {userMessage.title}
        
        <Chip 
          label={getCategoryLabel(userMessage.category)}
          color={getCategoryColor(userMessage.category)}
          size="small"
        />
        
        {userMessage.estimatedFixTime && (
          <Chip 
            label={userMessage.estimatedFixTime}
            icon={<TimeIcon />}
            variant="outlined"
            size="small"
          />
        )}
      </AlertTitle>
      
      <Typography variant="body1">
        {userMessage.message}
      </Typography>
      
      {userMessage.context && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          Context: {userMessage.context}
        </Typography>
      )}
    </Alert>
  );

  const renderSuggestions = () => {
    if (!userMessage.suggestions || userMessage.suggestions.length === 0 || compact) return null;

    return (
      <Accordion 
        expanded={showSuggestions} 
        onChange={(_, expanded) => setShowSuggestions(expanded)}
        elevation={0}
        sx={{ border: 1, borderColor: 'divider', mb: 1 }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SuggestionIcon color="primary" />
            Why This Happened
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <List dense>
            {userMessage.suggestions.map((suggestion, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  <InfoIcon color="primary" fontSize="small" />
                </ListItemIcon>
                <ListItemText primary={suggestion} />
              </ListItem>
            ))}
          </List>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderNextSteps = () => {
    if (!userMessage.nextSteps || userMessage.nextSteps.length === 0 || compact) return null;

    return (
      <Accordion 
        expanded={showNextSteps} 
        onChange={(_, expanded) => setShowNextSteps(expanded)}
        elevation={0}
        sx={{ border: 1, borderColor: 'divider', mb: 1 }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <NextStepIcon color="success" />
            What Happens Next
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stepper orientation="vertical" nonLinear>
            {userMessage.nextSteps.map((step, index) => (
              <Step key={index} completed={completedSteps.includes(index)}>
                <StepLabel 
                  onClick={() => handleStepComplete(index)}
                  sx={{ cursor: 'pointer' }}
                >
                  {step}
                </StepLabel>
                <StepContent>
                  <Button
                    size="small"
                    onClick={() => handleStepComplete(index)}
                    sx={{ mt: 1 }}
                  >
                    Mark as Done
                  </Button>
                </StepContent>
              </Step>
            ))}
          </Stepper>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderActionButtons = () => {
    if (!userMessage.actionable && !onAction) return null;

    const buttons = [];

    // Primary action button
    if (userMessage.actionable && onAction) {
      buttons.push(
        <Button
          key="primary"
          variant="contained"
          startIcon={isProcessing ? <AutorenewIcon className="spinning" /> : <RefreshIcon />}
          onClick={() => handleAction('retry')}
          disabled={isProcessing}
          color={userMessage.severity === 'error' ? 'error' : 'primary'}
        >
          {isProcessing ? 'Working...' : 'Try Again'}
        </Button>
      );
    }

    // Category-specific actions
    switch (userMessage.category) {
      case MessageCategory.AUTHENTICATION:
        buttons.push(
          <Button
            key="signin"
            variant="outlined"
            onClick={() => handleAction('signin')}
            disabled={isProcessing}
          >
            Sign In
          </Button>
        );
        break;

      case MessageCategory.CONNECTION:
        buttons.push(
          <Button
            key="offline"
            variant="outlined"
            onClick={() => handleAction('offline-mode')}
            disabled={isProcessing}
          >
            Work Offline
          </Button>
        );
        break;

      case MessageCategory.SYSTEM:
        if (userMessage.learnMoreUrl) {
          buttons.push(
            <Button
              key="status"
              variant="text"
              href={userMessage.learnMoreUrl}
              target="_blank"
            >
              Check Status
            </Button>
          );
        }
        break;
    }

    // Help button
    if (userMessage.suggestions || userMessage.nextSteps) {
      buttons.push(
        <Tooltip key="help" title="Get more help">
          <IconButton onClick={() => setShowHelp(true)}>
            <HelpIcon />
          </IconButton>
        </Tooltip>
      );
    }

    return (
      <Box sx={{ mt: 2 }}>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {buttons}
        </Stack>
      </Box>
    );
  };

  const renderHelpDialog = () => {
    const helpTexts = generateHelpText(userMessage);

    return (
      <Collapse in={showHelp}>
        <Paper sx={{ p: 2, mt: 2, backgroundColor: 'background.default' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <HelpIcon color="primary" />
              Additional Help
            </Typography>
            <IconButton size="small" onClick={() => setShowHelp(false)}>
              <CloseIcon />
            </IconButton>
          </Box>
          
          <List>
            {helpTexts.map((text, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  <InfoIcon color="primary" fontSize="small" />
                </ListItemIcon>
                <ListItemText primary={text} />
              </ListItem>
            ))}
          </List>

          {userMessage.learnMoreUrl && (
            <Box sx={{ mt: 2 }}>
              <Button
                variant="outlined"
                size="small"
                href={userMessage.learnMoreUrl}
                target="_blank"
              >
                Learn More
              </Button>
            </Box>
          )}
        </Paper>
      </Collapse>
    );
  };

  if (compact) {
    return (
      <Alert severity={userMessage.severity} icon={getSeverityIcon()}>
        <AlertTitle>{userMessage.title}</AlertTitle>
        {userMessage.message}
        {renderActionButtons()}
      </Alert>
    );
  }

  return (
    <Paper elevation={1} sx={{ p: 2, m: 1 }}>
      {renderMainAlert()}
      {renderSuggestions()}
      {renderNextSteps()}
      {renderActionButtons()}
      {renderHelpDialog()}

      {/* Animation styles */}
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

export default UserFriendlyErrorDisplay;