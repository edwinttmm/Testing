import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  LinearProgress,
  Alert,
  Divider,
  IconButton,
  Tooltip,
  Stack,
  Badge
} from '@mui/material';
import {
  CheckCircle,
  Error,
  Warning,
  Computer,
  Memory,
  Speed,
  Storage,
  NetworkCheck,
  Refresh,
  Security,
  MonitorHeart,
  CloudSync
} from '@mui/icons-material';
import { EnhancedDashboardStats } from '../../services/types';

interface SystemHealthProps {
  stats: EnhancedDashboardStats;
  isConnected: boolean;
  autoRefresh?: boolean;
  onRefresh?: () => void;
}

interface HealthMetric {
  name: string;
  value: number;
  status: 'healthy' | 'warning' | 'error';
  unit: string;
  threshold: { warning: number; error: number };
  icon: React.ReactNode;
  description: string;
}

export const SystemHealthIndicator: React.FC<SystemHealthProps> = ({
  stats,
  isConnected,
  autoRefresh = false,
  onRefresh
}) => {
  const [systemMetrics, setSystemMetrics] = useState<HealthMetric[]>([]);
  const [overallHealth, setOverallHealth] = useState<'healthy' | 'warning' | 'error'>('healthy');
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Calculate system health metrics
  useEffect(() => {
    const calculateMetrics = (): HealthMetric[] => {
      const metrics: HealthMetric[] = [
        {
          name: 'System Uptime',
          value: isConnected ? 100 : 0,
          status: isConnected ? 'healthy' : 'error',
          unit: '%',
          threshold: { warning: 90, error: 80 },
          icon: <Computer />,
          description: 'System availability and responsiveness'
        },
        {
          name: 'Detection Accuracy',
          value: stats.average_accuracy || 0,
          status: (stats.average_accuracy || 0) >= 90 ? 'healthy' : (stats.average_accuracy || 0) >= 70 ? 'warning' : 'error',
          unit: '%',
          threshold: { warning: 70, error: 50 },
          icon: <Speed />,
          description: 'Average detection accuracy across all tests'
        },
        {
          name: 'Signal Processing',
          value: stats.signal_processing_metrics?.successRate || 0,
          status: (stats.signal_processing_metrics?.successRate || 0) >= 95 ? 'healthy' : 
                 (stats.signal_processing_metrics?.successRate || 0) >= 80 ? 'warning' : 'error',
          unit: '%',
          threshold: { warning: 80, error: 60 },
          icon: <NetworkCheck />,
          description: 'Signal processing success rate'
        },
        {
          name: 'Processing Speed',
          value: Math.max(0, 100 - (stats.signal_processing_metrics?.avgProcessingTime || 0) / 10),
          status: (stats.signal_processing_metrics?.avgProcessingTime || 0) <= 50 ? 'healthy' : 
                 (stats.signal_processing_metrics?.avgProcessingTime || 0) <= 100 ? 'warning' : 'error',
          unit: '%',
          threshold: { warning: 70, error: 50 },
          icon: <MonitorHeart />,
          description: 'Processing speed efficiency'
        },
        {
          name: 'Test Coverage',
          value: Math.min(100, ((stats.test_session_count || 0) / Math.max(1, stats.project_count || 1)) * 20),
          status: ((stats.test_session_count || 0) / Math.max(1, stats.project_count || 1)) >= 3 ? 'healthy' :
                 ((stats.test_session_count || 0) / Math.max(1, stats.project_count || 1)) >= 1 ? 'warning' : 'error',
          unit: '%',
          threshold: { warning: 60, error: 40 },
          icon: <Security />,
          description: 'Test coverage across projects'
        },
        {
          name: 'Data Throughput',
          value: Math.min(100, ((stats.video_count || 0) + (stats.detection_event_count || 0)) / 10),
          status: ((stats.video_count || 0) + (stats.detection_event_count || 0)) >= 50 ? 'healthy' :
                 ((stats.video_count || 0) + (stats.detection_event_count || 0)) >= 20 ? 'warning' : 'error',
          unit: '%',
          threshold: { warning: 70, error: 50 },
          icon: <Storage />,
          description: 'Data processing throughput'
        }
      ];

      return metrics;
    };

    const metrics = calculateMetrics();
    setSystemMetrics(metrics);

    // Calculate overall health
    const healthyCount = metrics.filter(m => m.status === 'healthy').length;
    const warningCount = metrics.filter(m => m.status === 'warning').length;
    const errorCount = metrics.filter(m => m.status === 'error').length;

    if (errorCount > 0) {
      setOverallHealth('error');
    } else if (warningCount > 0) {
      setOverallHealth('warning');
    } else {
      setOverallHealth('healthy');
    }

    setLastUpdate(new Date());
  }, [stats, isConnected]);

  const getStatusColor = (status: 'healthy' | 'warning' | 'error') => {
    switch (status) {
      case 'healthy': return 'success';
      case 'warning': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: 'healthy' | 'warning' | 'error') => {
    switch (status) {
      case 'healthy': return <CheckCircle color="success" />;
      case 'warning': return <Warning color="warning" />;
      case 'error': return <Error color="error" />;
      default: return <CheckCircle />;
    }
  };

  const getOverallStatusMessage = () => {
    switch (overallHealth) {
      case 'healthy':
        return 'All systems operational. Performance is within expected parameters.';
      case 'warning':
        return 'Some systems need attention. Performance may be degraded.';
      case 'error':
        return 'Critical issues detected. Immediate attention required.';
      default:
        return 'System status unknown.';
    }
  };

  return (
    <Card>
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Badge
              badgeContent={systemMetrics.filter(m => m.status === 'error').length}
              color="error"
              invisible={systemMetrics.filter(m => m.status === 'error').length === 0}
            >
              <MonitorHeart color="primary" />
            </Badge>
            System Health
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              icon={getStatusIcon(overallHealth)}
              label={overallHealth.toUpperCase()}
              color={getStatusColor(overallHealth)}
              variant="filled"
              size="small"
            />
            
            {autoRefresh && (
              <Chip
                icon={<CloudSync />}
                label="Auto"
                color="info"
                variant="outlined"
                size="small"
              />
            )}
            
            {onRefresh && (
              <Tooltip title="Refresh Health Status">
                <IconButton onClick={onRefresh} size="small">
                  <Refresh />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* Overall Status Alert */}
        <Alert severity={getStatusColor(overallHealth)} sx={{ mb: 2 }}>
          <Typography variant="body2">
            <strong>System Status:</strong> {getOverallStatusMessage()}
          </Typography>
        </Alert>

        {/* Health Metrics Grid */}
        <Grid container spacing={2}>
          {systemMetrics.map((metric, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent sx={{ p: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Box sx={{ color: `${getStatusColor(metric.status)}.main`, mr: 1 }}>
                      {metric.icon}
                    </Box>
                    <Typography variant="subtitle2" noWrap>
                      {metric.name}
                    </Typography>
                  </Box>
                  
                  <Box sx={{ display: 'flex', alignItems: 'baseline', mb: 1 }}>
                    <Typography 
                      variant="h6" 
                      sx={{ 
                        color: `${getStatusColor(metric.status)}.main`,
                        fontFamily: 'monospace',
                        mr: 0.5
                      }}
                    >
                      {metric.value.toFixed(1)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {metric.unit}
                    </Typography>
                    <Box sx={{ ml: 'auto' }}>
                      {getStatusIcon(metric.status)}
                    </Box>
                  </Box>
                  
                  <LinearProgress
                    variant="determinate"
                    value={metric.value}
                    color={getStatusColor(metric.status)}
                    sx={{ mb: 1, height: 6, borderRadius: 3 }}
                  />
                  
                  <Typography variant="caption" color="text.secondary" title={metric.description}>
                    {metric.description.length > 40 
                      ? `${metric.description.substring(0, 40)}...` 
                      : metric.description
                    }
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        <Divider sx={{ my: 2 }} />

        {/* System Summary */}
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" gutterBottom>
              Performance Summary
            </Typography>
            <Stack spacing={1}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Healthy Systems:</Typography>
                <Chip 
                  label={systemMetrics.filter(m => m.status === 'healthy').length}
                  color="success"
                  size="small"
                />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Systems with Warnings:</Typography>
                <Chip 
                  label={systemMetrics.filter(m => m.status === 'warning').length}
                  color="warning"
                  size="small"
                />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Critical Systems:</Typography>
                <Chip 
                  label={systemMetrics.filter(m => m.status === 'error').length}
                  color="error"
                  size="small"
                />
              </Box>
            </Stack>
          </Grid>

          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" gutterBottom>
              Connection Status
            </Typography>
            <Stack spacing={1}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Backend API:</Typography>
                <Chip 
                  label={isConnected ? 'Connected' : 'Disconnected'}
                  color={isConnected ? 'success' : 'error'}
                  size="small"
                  icon={isConnected ? <CheckCircle /> : <Error />}
                />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">WebSocket:</Typography>
                <Chip 
                  label={isConnected ? 'Active' : 'Inactive'}
                  color={isConnected ? 'success' : 'default'}
                  size="small"
                  variant={isConnected ? 'filled' : 'outlined'}
                />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">Last Update:</Typography>
                <Typography variant="caption" color="text.secondary">
                  {lastUpdate.toLocaleTimeString()}
                </Typography>
              </Box>
            </Stack>
          </Grid>
        </Grid>

        {/* Recommendations */}
        {overallHealth !== 'healthy' && (
          <>
            <Divider sx={{ my: 2 }} />
            <Alert severity="info">
              <Typography variant="subtitle2" gutterBottom>
                Recommended Actions:
              </Typography>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                {systemMetrics
                  .filter(m => m.status !== 'healthy')
                  .map((metric, index) => (
                    <li key={index}>
                      <Typography variant="body2">
                        {metric.status === 'error' ? 'Fix' : 'Monitor'} {metric.name.toLowerCase()} - currently at {metric.value.toFixed(1)}%
                      </Typography>
                    </li>
                  ))
                }
              </ul>
            </Alert>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default SystemHealthIndicator;