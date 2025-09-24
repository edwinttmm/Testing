import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Chip,
  Button,
  Alert,
  Stack,
  CircularProgress,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

import { apiService } from '../services/api';
// Using inline interface instead of importing

interface SimpleLabJackStatusState {
  connected: boolean;
  status: 'connected' | 'disconnected' | 'checking' | 'error';
  deviceInfo?: {
    deviceType: string;
    serialNumber?: string;
  };
  error?: string;
}

interface SimpleLabJackStatusProps {
  onStatusChange?: (status: SimpleLabJackStatusState) => void;
  showRefreshButton?: boolean;
}

const SimpleLabJackStatus: React.FC<SimpleLabJackStatusProps> = ({
  onStatusChange,
  showRefreshButton = true
}) => {
  const [status, setStatus] = useState<SimpleLabJackStatusState>({
    connected: false,
    status: 'checking'
  });
  const [loading, setLoading] = useState(false);

  const checkLabJackStatus = async () => {
    try {
      setLoading(true);
      console.log('🔍 [SimpleLabJackStatus] Checking LabJack status...');
      const response = await apiService.checkLabJackStatus();
      console.log('📡 [SimpleLabJackStatus] API Response:', response);
      
      const newStatus: SimpleLabJackStatusState = {
        connected: response?.is_connected || false,
        status: response?.is_connected ? 'connected' : 'disconnected',
        deviceInfo: response?.device_info ? {
          deviceType: (response.device_info as any)?.device_type || 'LabJack DAQ',
          serialNumber: (response.device_info as any)?.serial_number?.toString()
        } : undefined,
        error: (response as any)?.error_message || response?.error
      };
      
      console.log('✅ [SimpleLabJackStatus] Processed Status:', newStatus);
      setStatus(newStatus);
      onStatusChange?.(newStatus);
      
    } catch (err: any) {
      const errorStatus: SimpleLabJackStatusState = {
        connected: false,
        status: 'error',
        error: err.message || 'Connection check failed'
      };
      
      setStatus(errorStatus);
      onStatusChange?.(errorStatus);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkLabJackStatus();
    
    // Poll every 5 seconds
    const interval = setInterval(checkLabJackStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = () => {
    switch (status.status) {
      case 'connected': return 'success';
      case 'disconnected': return 'error';
      case 'checking': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusText = () => {
    switch (status.status) {
      case 'connected': return 'Connected';
      case 'disconnected': return 'Not Detected';
      case 'checking': return 'Checking...';
      case 'error': return 'Error';
      default: return 'Unknown';
    }
  };

  const getStatusIcon = () => {
    if (loading || status.status === 'checking') {
      return <CircularProgress size={20} />;
    }
    return status.connected ? <CheckCircleIcon /> : <ErrorIcon />;
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 1 }}>
        <Chip
          icon={getStatusIcon()}
          label={`LabJack DAQ: ${getStatusText()}`}
          color={getStatusColor()}
          variant="filled"
        />
        
        {status.deviceInfo && (
          <Typography variant="body2" color="text.secondary">
            {status.deviceInfo.deviceType}
            {status.deviceInfo.serialNumber && ` (S/N: ${status.deviceInfo.serialNumber})`}
          </Typography>
        )}
        
        {showRefreshButton && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={checkLabJackStatus}
            disabled={loading}
          >
            Refresh
          </Button>
        )}
      </Stack>

      {/* Connection Status Alert */}
      {!status.connected && status.status !== 'checking' && (
        <Alert severity="error" sx={{ mt: 1 }}>
          <Typography variant="body2">
            <strong>Hardware Required:</strong> LabJack device must be connected before starting test.
            {status.error && ` (${status.error})`}
          </Typography>
        </Alert>
      )}

      {status.connected && (
        <Alert severity="success" sx={{ mt: 1 }}>
          <Typography variant="body2">
            LabJack device ready for HIL testing.
          </Typography>
        </Alert>
      )}
    </Box>
  );
};

export default SimpleLabJackStatus;