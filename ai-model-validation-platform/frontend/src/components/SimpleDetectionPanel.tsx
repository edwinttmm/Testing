import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Alert,
  Grid,
  Divider,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Timeline as TimelineIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { simpleDetectionService, SimpleDetectionStatus, DetectionResult } from '../services/simpleDetectionService';
import { labjackLogger } from '../utils/labjackLogger';

interface SimpleDetectionPanelProps {
  projectId?: string;
  toleranceMs?: number;
  onDetectionComplete?: (result: DetectionResult) => void;
}

export const SimpleDetectionPanel: React.FC<SimpleDetectionPanelProps> = ({
  projectId = 'default',
  toleranceMs = 100,
  onDetectionComplete,
}) => {
  const [status, setStatus] = useState<SimpleDetectionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load status with enhanced error handling
  const loadStatus = async () => {
    try {
      const result = await simpleDetectionService.getStatus();
      setStatus(result);
      
      // Log any connection issues
      if (result.connection_status === 'error') {
        labjackLogger.warn('SimpleDetection', 'Connection issues detected', {
          status: result.connection_status,
          error: result.error_message,
        });
      }
      
      // Log Windows driver issues
      if (result.windows_compatibility && !result.windows_compatibility.driver_detected) {
        labjackLogger.logWindowsDriverIssue(
          'Driver not detected in simple detection service',
          result.windows_compatibility.recommendations
        );
      }
    } catch (err: unknown) {
      const error = err as Error;
      labjackLogger.error('SimpleDetection', 'Failed to load status', error);
      // Still silently handle for UI, but log for debugging
    }
  };

  // Start detection
  const handleStart = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const sessionId = `${projectId}_${Date.now()}`;
      await simpleDetectionService.startDetection(sessionId, toleranceMs);
      
      // Detection started successfully
      await loadStatus();
    } catch (err: unknown) {
      const error = err as { message?: string };
      setError(error.message || 'Failed to start detection');
    } finally {
      setLoading(false);
    }
  };

  // Stop detection
  const handleStop = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await simpleDetectionService.stopDetection();
      // Detection stopped successfully
      
      // Notify parent component
      if (onDetectionComplete && result.data) {
        onDetectionComplete(result);
      }
      
      await loadStatus();
    } catch (err: unknown) {
      const error = err as { message?: string };
      setError(error.message || 'Failed to stop detection');
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh status when running
  useEffect(() => {
    const interval = setInterval(() => {
      if (status?.running) {
        loadStatus();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [status?.running]);

  // Load initial status
  useEffect(() => {
    loadStatus();
  }, []);

  const getStatusColor = () => {
    if (status?.running) return 'success';
    return 'default';
  };

  const getStatusText = () => {
    if (status?.running) return 'Detecting';
    return 'Stopped';
  };

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Typography variant="h6" component="div" display="flex" alignItems="center">
            <TimelineIcon sx={{ mr: 1 }} />
            Simple LabJack Detection
          </Typography>
          <Chip
            label={getStatusText()}
            color={getStatusColor()}
            variant={status?.running ? 'filled' : 'outlined'}
          />
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Session ID
            </Typography>
            <Typography variant="body1">
              {status?.session_id || 'None'}
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Tolerance
            </Typography>
            <Typography variant="body1">
              {status?.tolerance_ms || toleranceMs}ms
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Detections
            </Typography>
            <Typography variant="body1" display="flex" alignItems="center">
              <SpeedIcon sx={{ mr: 0.5, fontSize: 16 }} />
              {status?.detections_count || 0}
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">
              Duration
            </Typography>
            <Typography variant="body1">
              {status?.duration_seconds ? `${status.duration_seconds.toFixed(1)}s` : '0s'}
            </Typography>
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />

        <Box display="flex" gap={1}>
          <Button
            variant="contained"
            startIcon={<StartIcon />}
            onClick={handleStart}
            disabled={loading || status?.running}
            color="primary"
          >
            Start Detection
          </Button>
          <Button
            variant="outlined"
            startIcon={<StopIcon />}
            onClick={handleStop}
            disabled={loading || !status?.running}
            color="secondary"
          >
            Stop & Get Results
          </Button>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
          ✅ Enhanced reliability - Windows compatible with automatic retry and recovery
        </Typography>
        
        {/* Enhanced status indicators */}
        {status && (
          <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {status.connection_status && (
              <Chip
                size="small"
                label={`Connection: ${status.connection_status.toUpperCase()}`}
                color={status.connection_status === 'connected' ? 'success' : 'error'}
                variant="outlined"
              />
            )}
            {status.hardware_status && (
              <Chip
                size="small"
                label={`Hardware: ${status.hardware_status.toUpperCase()}`}
                color={
                  status.hardware_status === 'ok' ? 'success' :
                  status.hardware_status === 'warning' ? 'warning' : 'error'
                }
                variant="outlined"
              />
            )}
            {status.windows_compatibility && !status.windows_compatibility.driver_detected && (
              <Chip
                size="small"
                label="Driver Issues"
                color="warning"
                variant="outlined"
              />
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default SimpleDetectionPanel;