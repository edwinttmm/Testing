import React, { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Fade,
  Alert
} from '@mui/material';
import {
  Stop as StopIcon,
  Warning as WarningIcon
} from '@mui/icons-material';

interface EmergencyStopButtonProps {
  onEmergencyStop: () => void;
  isVisible: boolean;
  position?: {
    top?: number | string;
    bottom?: number | string;
    left?: number | string;
    right?: number | string;
  };
  confirmationRequired?: boolean;
}

const EmergencyStopButton: React.FC<EmergencyStopButtonProps> = ({
  onEmergencyStop,
  isVisible,
  position = { top: 16, right: 16 },
  confirmationRequired = true
}) => {
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [isPressed, setIsPressed] = useState(false);

  const handleEmergencyStop = () => {
    if (confirmationRequired) {
      setShowConfirmation(true);
    } else {
      executeEmergencyStop();
    }
  };

  const executeEmergencyStop = () => {
    setIsPressed(true);
    onEmergencyStop();
    setShowConfirmation(false);
    
    // Reset pressed state after animation
    setTimeout(() => setIsPressed(false), 2000);
  };

  const handleCancel = () => {
    setShowConfirmation(false);
  };

  if (!isVisible) {
    return null;
  }

  return (
    <>
      {/* Emergency Stop Button */}
      <Fade in={isVisible}>
        <Box
          sx={{
            position: 'fixed',
            ...position,
            zIndex: 9999,
            animation: isPressed ? 'none' : 'pulse 2s infinite'
          }}
        >
          <Button
            variant="contained"
            color="error"
            size="large"
            startIcon={<StopIcon />}
            onClick={handleEmergencyStop}
            sx={{
              minWidth: 180,
              minHeight: 56,
              fontSize: '1.1rem',
              fontWeight: 'bold',
              boxShadow: isPressed ? 'inset 0 0 20px rgba(255,255,255,0.5)' : '0 4px 20px rgba(244,67,54,0.5)',
              background: isPressed 
                ? 'linear-gradient(45deg, #f44336, #d32f2f)'
                : 'linear-gradient(45deg, #f44336, #e53935)',
              border: '3px solid #ffffff',
              transform: isPressed ? 'scale(0.95)' : 'scale(1)',
              transition: 'all 0.2s ease',
              '&:hover': {
                background: 'linear-gradient(45deg, #d32f2f, #b71c1c)',
                boxShadow: '0 6px 25px rgba(244,67,54,0.7)',
                transform: 'scale(1.05)'
              },
              '&:active': {
                transform: 'scale(0.98)',
                boxShadow: 'inset 0 0 15px rgba(0,0,0,0.3)'
              }
            }}
          >
            EMERGENCY STOP
          </Button>
        </Box>
      </Fade>

      {/* Confirmation Dialog */}
      <Dialog
        open={showConfirmation}
        onClose={handleCancel}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            border: '3px solid #f44336',
            backgroundColor: '#fff3e0'
          }
        }}
      >
        <DialogTitle sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 2,
          color: 'error.main',
          backgroundColor: '#ffebee'
        }}>
          <WarningIcon color="error" />
          Emergency Stop Confirmation
        </DialogTitle>
        
        <DialogContent sx={{ pt: 2 }}>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              <strong>WARNING: This will immediately terminate the test!</strong>
            </Typography>
            <Typography variant="body2">
              The emergency stop will:
            </Typography>
            <ul style={{ marginTop: 8, marginBottom: 8 }}>
              <li>Stop video playback immediately</li>
              <li>Disconnect hardware monitoring</li>
              <li>Exit full-screen mode</li>
              <li>Save partial test results</li>
              <li>End the current test session</li>
            </ul>
          </Alert>
          
          <Typography variant="body1" color="text.primary">
            Are you sure you want to perform an emergency stop?
          </Typography>
        </DialogContent>
        
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button 
            onClick={handleCancel} 
            variant="outlined"
            color="primary"
            size="large"
          >
            Cancel
          </Button>
          <Button 
            onClick={executeEmergencyStop} 
            variant="contained"
            color="error"
            size="large"
            startIcon={<StopIcon />}
            sx={{
              fontWeight: 'bold',
              minWidth: 160
            }}
          >
            EMERGENCY STOP
          </Button>
        </DialogActions>
      </Dialog>

      {/* CSS Animation */}
      <style>
        {`
          @keyframes pulse {
            0% {
              box-shadow: 0 4px 20px rgba(244,67,54,0.5);
            }
            50% {
              box-shadow: 0 4px 30px rgba(244,67,54,0.8);
            }
            100% {
              box-shadow: 0 4px 20px rgba(244,67,54,0.5);
            }
          }
        `}
      </style>
    </>
  );
};

export default EmergencyStopButton;