import React, { useState, useEffect, useCallback } from 'react';
import {
  Alert,
  Snackbar,
  IconButton,
  Typography,
  Box,
  Button,
} from '@mui/material';
import {
  Close,
  Wifi,
  WifiOff,
  Refresh,
} from '@mui/icons-material';
import { apiService } from '../services/api';

interface ApiConnectionStatusProps {
  onRetry?: () => void;
}

const ApiConnectionStatus: React.FC<ApiConnectionStatusProps> = ({ onRetry }) => {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const [showAlert, setShowAlert] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  // Check API connectivity
  const checkApiConnection = useCallback(async () => {
    try {
      await apiService.healthCheck();
      setApiConnected(true);
      setLastError(null);
      if (showAlert) {
        setShowAlert(false);
      }
    } catch (error: any) {
      setApiConnected(false);
      setLastError(error.message || 'API connection failed');
      setShowAlert(true);
    }
  }, [showAlert]);

  // Monitor online/offline status
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Recheck API when coming back online
      checkApiConnection();
    };

    const handleOffline = () => {
      setIsOnline(false);
      setShowAlert(true);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial API check
    checkApiConnection();

    // Periodic API health checks
    const healthCheckInterval = setInterval(checkApiConnection, 60000); // Every minute

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(healthCheckInterval);
    };
  }, [checkApiConnection]);

  const handleRetry = async () => {
    setShowAlert(false);
    await checkApiConnection();
    onRetry?.();
  };

  const handleClose = () => {
    setShowAlert(false);
  };

  if (!showAlert) {
    return null;
  }

  const getAlertMessage = () => {
    if (!isOnline) {
      return 'No internet connection. Please check your network.';
    }
    if (apiConnected === false) {
      return `Backend API is unreachable. ${lastError || 'Please check the server status.'}`;
    }
    return 'Connection issue detected.';
  };

  const getAlertSeverity = () => {
    if (!isOnline || apiConnected === false) {
      return 'error';
    }
    return 'warning';
  };

  return (
    <Snackbar
      open={showAlert}
      anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      sx={{ mt: 8 }} // Account for header height
    >
      <Alert
        severity={getAlertSeverity()}
        variant="filled"
        icon={isOnline ? (apiConnected ? <Wifi /> : <WifiOff />) : <WifiOff />}
        action={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button
              color="inherit"
              size="small"
              onClick={handleRetry}
              startIcon={<Refresh />}
            >
              Retry
            </Button>
            <IconButton
              size="small"
              aria-label="close"
              color="inherit"
              onClick={handleClose}
            >
              <Close fontSize="small" />
            </IconButton>
          </Box>
        }
        sx={{ width: '100%', minWidth: 400 }}
      >
        <Typography variant="subtitle2" gutterBottom>
          Connection Problem
        </Typography>
        <Typography variant="body2">
          {getAlertMessage()}
        </Typography>
      </Alert>
    </Snackbar>
  );
};

export default ApiConnectionStatus;