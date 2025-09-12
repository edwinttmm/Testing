import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Alert,
  LinearProgress,
  IconButton,
  Tooltip,
  Grid,
  Divider,
} from '@mui/material';
import {
  CheckCircle,
  Error,
  Warning,
  Refresh,
  Computer,
  Settings,
  NetworkCheck,
} from '@mui/icons-material';

// TypeScript interfaces for health status responses
interface LabJackStatus {
  connected: boolean;
  driver_version?: string;
  device_info?: {
    model: string;
    serial_number: string;
    firmware_version: string;
  };
  windows_compatible: boolean;
  error_message?: string;
}

interface Frame80DetectionStatus {
  ready: boolean;
  model_loaded: boolean;
  confidence_threshold: number;
  last_detection?: string;
  performance_metrics?: {
    avg_inference_time: number;
    fps: number;
  };
}

interface HealthResponse {
  status: 'healthy' | 'unhealthy' | 'warning';
  timestamp: string;
  api_version: string;
  uptime: number;
  labjack: LabJackStatus;
  frame80_detection: Frame80DetectionStatus;
  system_info: {
    platform: string;
    python_version: string;
    memory_usage: number;
    cpu_usage: number;
  };
}

interface ApiHealthIndicatorProps {
  baseUrl?: string;
  refreshInterval?: number;
  onHealthChange?: (status: 'healthy' | 'unhealthy' | 'warning') => void;
}

const ApiHealthIndicator: React.FC<ApiHealthIndicatorProps> = ({
  baseUrl = 'http://localhost:8000',
  refreshInterval = 10000, // 10 seconds
  onHealthChange,
}) => {
  const [healthStatus, setHealthStatus] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Check health endpoint
  const checkHealth = useCallback(async () => {
    try {
      setError(null);
      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${baseUrl}/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);

      if (!response.ok) {
        // @ts-ignore - Suppress TypeScript warnings for Error constructor
        const httpError = new Error(`HTTP ${response.status}: ${response.statusText}`);
        throw httpError;
      }

      const data: HealthResponse = await response.json();
      setHealthStatus(data);
      setLastUpdate(new Date());
      
      // Notify parent component of health status change
      if (onHealthChange) {
        onHealthChange(data.status);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      setHealthStatus(null);
      
      if (onHealthChange) {
        onHealthChange('unhealthy');
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [baseUrl, onHealthChange]);

  // Manual refresh
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    checkHealth();
  }, [checkHealth]);

  // Auto-refresh effect
  useEffect(() => {
    checkHealth();
    
    const interval = setInterval(checkHealth, refreshInterval);
    
    return () => clearInterval(interval);
  }, [checkHealth, refreshInterval]);

  // Status color helper
  const getStatusColor = (status: string): 'success' | 'error' | 'warning' => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'unhealthy':
        return 'error';
      case 'warning':
        return 'warning';
      default:
        return 'error';
    }
  };

  // Status icon helper
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle color="success" />;
      case 'unhealthy':
        return <Error color="error" />;
      case 'warning':
        return <Warning color="warning" />;
      default:
        return <Error color="error" />;
    }
  };

  // Render loading state
  if (loading && !healthStatus) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" alignItems="center" gap={2}>
            <NetworkCheck />
            <Typography variant="h6">Checking API Health...</Typography>
          </Box>
          <LinearProgress sx={{ mt: 2 }} />
        </CardContent>
      </Card>
    );
  }

  // Render error state
  if (error && !healthStatus) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error" sx={{ mb: 2 }}>
            <Typography variant="h6">Backend Connection Failed</Typography>
            <Typography variant="body2">{error}</Typography>
          </Alert>
          
          <Alert severity="info">
            <Typography variant="body2">
              <strong>Troubleshooting Steps:</strong>
            </Typography>
            <ul>
              <li>Ensure the backend server is running on {baseUrl}</li>
              <li>Check network connectivity</li>
              <li>Verify CORS settings if running on different domains</li>
              <li>Check firewall settings</li>
            </ul>
          </Alert>

          <Box display="flex" justifyContent="space-between" alignItems="center" mt={2}>
            <Typography variant="caption" color="text.secondary">
              {lastUpdate ? `Last attempted: ${lastUpdate.toLocaleTimeString()}` : 'Never connected'}
            </Typography>
            <IconButton onClick={handleRefresh} disabled={isRefreshing}>
              <Refresh />
            </IconButton>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <NetworkCheck />
            <Typography variant="h6">API Health Status</Typography>
          </Box>
          <Box display="flex" alignItems="center" gap={1}>
            {healthStatus && (
              <Chip
                icon={getStatusIcon(healthStatus.status)}
                label={healthStatus.status.toUpperCase()}
                color={getStatusColor(healthStatus.status)}
                size="small"
              />
            )}
            <Tooltip title="Refresh">
              <IconButton onClick={handleRefresh} disabled={isRefreshing} size="small">
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {isRefreshing && <LinearProgress sx={{ mb: 2 }} />}

        {healthStatus && (
          <Grid container spacing={2}>
            {/* System Info */}
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                <Computer sx={{ verticalAlign: 'middle', mr: 1 }} />
                System Information
              </Typography>
              <Box pl={2}>
                <Typography variant="body2">
                  <strong>Platform:</strong> {healthStatus.system_info.platform}
                </Typography>
                <Typography variant="body2">
                  <strong>Python:</strong> {healthStatus.system_info.python_version}
                </Typography>
                <Typography variant="body2">
                  <strong>API Version:</strong> {healthStatus.api_version}
                </Typography>
                <Typography variant="body2">
                  <strong>Uptime:</strong> {Math.round(healthStatus.uptime)} seconds
                </Typography>
              </Box>
            </Grid>

            {/* Performance Metrics */}
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                <Settings sx={{ verticalAlign: 'middle', mr: 1 }} />
                Performance
              </Typography>
              <Box pl={2}>
                <Typography variant="body2">
                  <strong>Memory Usage:</strong> {healthStatus.system_info.memory_usage.toFixed(1)}%
                </Typography>
                <Typography variant="body2">
                  <strong>CPU Usage:</strong> {healthStatus.system_info.cpu_usage.toFixed(1)}%
                </Typography>
              </Box>
            </Grid>

            <Grid item xs={12}>
              <Divider sx={{ my: 1 }} />
            </Grid>

            {/* LabJack Status */}
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                LabJack Hardware Status
              </Typography>
              <Box pl={2}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  {healthStatus.labjack.connected ? (
                    <CheckCircle color="success" fontSize="small" />
                  ) : (
                    <Error color="error" fontSize="small" />
                  )}
                  <Typography variant="body2">
                    <strong>Connected:</strong> {healthStatus.labjack.connected ? 'Yes' : 'No'}
                  </Typography>
                </Box>
                
                {healthStatus.labjack.device_info && (
                  <>
                    <Typography variant="body2">
                      <strong>Model:</strong> {healthStatus.labjack.device_info.model}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Serial:</strong> {healthStatus.labjack.device_info.serial_number}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Firmware:</strong> {healthStatus.labjack.device_info.firmware_version}
                    </Typography>
                  </>
                )}

                <Box display="flex" alignItems="center" gap={1} mt={1}>
                  {healthStatus.labjack.windows_compatible ? (
                    <CheckCircle color="success" fontSize="small" />
                  ) : (
                    <Warning color="warning" fontSize="small" />
                  )}
                  <Typography variant="body2">
                    <strong>Windows Compatible:</strong> {healthStatus.labjack.windows_compatible ? 'Yes' : 'No'}
                  </Typography>
                </Box>

                {healthStatus.labjack.driver_version && (
                  <Typography variant="body2">
                    <strong>Driver Version:</strong> {healthStatus.labjack.driver_version}
                  </Typography>
                )}

                {healthStatus.labjack.error_message && (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    <Typography variant="caption">
                      {healthStatus.labjack.error_message}
                    </Typography>
                  </Alert>
                )}
              </Box>
            </Grid>

            {/* Frame 80 Detection Status */}
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                Frame 80 Detection
              </Typography>
              <Box pl={2}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  {healthStatus.frame80_detection.ready ? (
                    <CheckCircle color="success" fontSize="small" />
                  ) : (
                    <Warning color="warning" fontSize="small" />
                  )}
                  <Typography variant="body2">
                    <strong>Ready:</strong> {healthStatus.frame80_detection.ready ? 'Yes' : 'No'}
                  </Typography>
                </Box>

                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  {healthStatus.frame80_detection.model_loaded ? (
                    <CheckCircle color="success" fontSize="small" />
                  ) : (
                    <Error color="error" fontSize="small" />
                  )}
                  <Typography variant="body2">
                    <strong>Model Loaded:</strong> {healthStatus.frame80_detection.model_loaded ? 'Yes' : 'No'}
                  </Typography>
                </Box>

                <Typography variant="body2">
                  <strong>Confidence Threshold:</strong> {(healthStatus.frame80_detection.confidence_threshold * 100).toFixed(1)}%
                </Typography>

                {healthStatus.frame80_detection.last_detection && (
                  <Typography variant="body2">
                    <strong>Last Detection:</strong> {healthStatus.frame80_detection.last_detection}
                  </Typography>
                )}

                {healthStatus.frame80_detection.performance_metrics && (
                  <>
                    <Typography variant="body2">
                      <strong>Avg Inference:</strong> {healthStatus.frame80_detection.performance_metrics.avg_inference_time.toFixed(1)}ms
                    </Typography>
                    <Typography variant="body2">
                      <strong>FPS:</strong> {healthStatus.frame80_detection.performance_metrics.fps.toFixed(1)}
                    </Typography>
                  </>
                )}
              </Box>
            </Grid>
          </Grid>
        )}

        {/* Windows Compatibility Alert */}
        {healthStatus && !healthStatus.labjack.windows_compatible && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>Windows Compatibility Issue:</strong> LabJack drivers may not be properly installed for Windows. 
              Please install the latest LabJack drivers from the official website and restart the application.
            </Typography>
          </Alert>
        )}

        {/* Footer */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mt={2}>
          <Typography variant="caption" color="text.secondary">
            {lastUpdate && `Last updated: ${lastUpdate.toLocaleTimeString()}`}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Auto-refresh: {refreshInterval / 1000}s
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ApiHealthIndicator;