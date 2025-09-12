import React, { useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Paper,
  Chip,
  LinearProgress,
  Stack,
  Divider
} from '@mui/material';
import {
  Speed as SpeedIcon,
  Timer as TimerIcon,
  TrendingUp as TrendingUpIcon,
  Assessment as AssessmentIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon
} from '@mui/icons-material';

interface TimingMetrics {
  latency: number;
  responseTime: number;
  accuracy: number;
  jitter?: number;
  throughput?: number;
}

interface DetectionEvent {
  id: string | number;
  videoId: number;
  expectedEventTime?: string;
  signalReceivedTime?: string;
  latencyMs?: number;
  outcome: string;
  createdAt: string;
}

interface TimingMetricsPanelProps {
  metrics: TimingMetrics;
  isRunning: boolean;
  detectionEvents: DetectionEvent[];
  maxLatencyMs?: number;
}

const TimingMetricsPanel: React.FC<TimingMetricsPanelProps> = ({
  metrics,
  isRunning,
  detectionEvents,
  maxLatencyMs = 500
}) => {
  // Calculate real-time metrics from detection events
  const calculatedMetrics = useMemo(() => {
    if (detectionEvents.length === 0) {
      return {
        averageLatency: 0,
        minLatency: 0,
        maxLatency: 0,
        passRate: 0,
        totalEvents: 0,
        passedEvents: 0,
        failedEvents: 0,
        jitter: 0
      };
    }

    const validEvents = detectionEvents.filter(event => event.latencyMs !== undefined);
    const latencies = validEvents.map(event => event.latencyMs!);
    
    const averageLatency = latencies.length > 0 ? latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length : 0;
    const minLatency = latencies.length > 0 ? Math.min(...latencies) : 0;
    const maxLatency = latencies.length > 0 ? Math.max(...latencies) : 0;
    
    const passedEvents = detectionEvents.filter(event => 
      event.outcome === 'PASS' || (event.latencyMs !== undefined && event.latencyMs <= maxLatencyMs)
    ).length;
    const failedEvents = detectionEvents.length - passedEvents;
    const passRate = detectionEvents.length > 0 ? (passedEvents / detectionEvents.length) * 100 : 0;
    
    // Calculate jitter (standard deviation of latencies)
    const jitter = latencies.length > 1 
      ? Math.sqrt(latencies.reduce((sum, lat) => sum + Math.pow(lat - averageLatency, 2), 0) / latencies.length)
      : 0;

    return {
      averageLatency,
      minLatency,
      maxLatency,
      passRate,
      totalEvents: detectionEvents.length,
      passedEvents,
      failedEvents,
      jitter
    };
  }, [detectionEvents, maxLatencyMs]);

  const getLatencyColor = (latency: number) => {
    if (latency <= maxLatencyMs * 0.5) return 'success';
    if (latency <= maxLatencyMs * 0.8) return 'warning';
    return 'error';
  };

  const getPassRateColor = (passRate: number) => {
    if (passRate >= 90) return 'success';
    if (passRate >= 70) return 'warning';
    return 'error';
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TimerIcon />
          Timing Metrics & Performance
        </Typography>

        {/* Real-time Status Indicator */}
        <Box sx={{ mb: 2 }}>
          <Chip
            icon={isRunning ? <TrendingUpIcon /> : <AssessmentIcon />}
            label={isRunning ? 'Live Monitoring' : 'Analysis Ready'}
            color={isRunning ? 'primary' : 'default'}
            variant={isRunning ? 'filled' : 'outlined'}
          />
        </Box>

        {/* Primary Metrics */}
        <Grid container spacing={2} sx={{ mb: 2 }}>
          {/* Average Latency */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
              <SpeedIcon color="primary" sx={{ fontSize: 32, mb: 1 }} />
              <Typography variant="h4" color="primary.main" sx={{ fontFamily: 'monospace' }}>
                {calculatedMetrics.averageLatency.toFixed(1)}ms
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Average Latency
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={(calculatedMetrics.averageLatency / maxLatencyMs) * 100}
                color={getLatencyColor(calculatedMetrics.averageLatency)}
                sx={{ mt: 1 }}
              />
            </Paper>
          </Grid>

          {/* Pass Rate */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
              <CheckCircleIcon color="success" sx={{ fontSize: 32, mb: 1 }} />
              <Typography variant="h4" color="success.main" sx={{ fontFamily: 'monospace' }}>
                {calculatedMetrics.passRate.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Pass Rate
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={calculatedMetrics.passRate}
                color={getPassRateColor(calculatedMetrics.passRate)}
                sx={{ mt: 1 }}
              />
            </Paper>
          </Grid>

          {/* Response Time Range */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
              <TimerIcon color="info" sx={{ fontSize: 32, mb: 1 }} />
              <Typography variant="h6" color="info.main" sx={{ fontFamily: 'monospace' }}>
                {calculatedMetrics.minLatency.toFixed(1)} - {calculatedMetrics.maxLatency.toFixed(1)}ms
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Min - Max Response
              </Typography>
              <Typography variant="caption" display="block" color="text.secondary">
                Jitter: {calculatedMetrics.jitter.toFixed(1)}ms
              </Typography>
            </Paper>
          </Grid>

          {/* Total Events */}
          <Grid item xs={12} sm={6} md={3}>
            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
              <AssessmentIcon color="secondary" sx={{ fontSize: 32, mb: 1 }} />
              <Typography variant="h4" color="secondary.main" sx={{ fontFamily: 'monospace' }}>
                {calculatedMetrics.totalEvents}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Total Events
              </Typography>
              <Stack direction="row" spacing={1} justifyContent="center" sx={{ mt: 1 }}>
                <Chip 
                  label={`✓ ${calculatedMetrics.passedEvents}`}
                  color="success" 
                  size="small" 
                />
                <Chip 
                  label={`✗ ${calculatedMetrics.failedEvents}`}
                  color="error" 
                  size="small" 
                />
              </Stack>
            </Paper>
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />

        {/* Detailed Metrics */}
        <Typography variant="subtitle1" gutterBottom>
          Performance Analysis
        </Typography>

        <Grid container spacing={2}>
          {/* Latency Breakdown */}
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Latency Distribution
              </Typography>
              
              <Stack spacing={1}>
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption">Excellent (&lt;{maxLatencyMs * 0.5}ms)</Typography>
                    <Typography variant="caption">
                      {detectionEvents.filter(e => e.latencyMs && e.latencyMs < maxLatencyMs * 0.5).length}
                    </Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={calculatedMetrics.totalEvents > 0 
                      ? (detectionEvents.filter(e => e.latencyMs && e.latencyMs < maxLatencyMs * 0.5).length / calculatedMetrics.totalEvents) * 100
                      : 0
                    }
                    color="success"
                  />
                </Box>

                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption">Good ({maxLatencyMs * 0.5}-{maxLatencyMs * 0.8}ms)</Typography>
                    <Typography variant="caption">
                      {detectionEvents.filter(e => e.latencyMs && e.latencyMs >= maxLatencyMs * 0.5 && e.latencyMs <= maxLatencyMs * 0.8).length}
                    </Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={calculatedMetrics.totalEvents > 0 
                      ? (detectionEvents.filter(e => e.latencyMs && e.latencyMs >= maxLatencyMs * 0.5 && e.latencyMs <= maxLatencyMs * 0.8).length / calculatedMetrics.totalEvents) * 100
                      : 0
                    }
                    color="warning"
                  />
                </Box>

                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption">Poor (&gt;{maxLatencyMs * 0.8}ms)</Typography>
                    <Typography variant="caption">
                      {detectionEvents.filter(e => e.latencyMs && e.latencyMs > maxLatencyMs * 0.8).length}
                    </Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={calculatedMetrics.totalEvents > 0 
                      ? (detectionEvents.filter(e => e.latencyMs && e.latencyMs > maxLatencyMs * 0.8).length / calculatedMetrics.totalEvents) * 100
                      : 0
                    }
                    color="error"
                  />
                </Box>
              </Stack>
            </Paper>
          </Grid>

          {/* Performance Summary */}
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Performance Summary
              </Typography>
              
              <Stack spacing={2}>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    System Responsiveness
                  </Typography>
                  <Chip 
                    label={
                      calculatedMetrics.averageLatency <= maxLatencyMs * 0.5 ? 'Excellent' :
                      calculatedMetrics.averageLatency <= maxLatencyMs * 0.8 ? 'Good' : 'Needs Improvement'
                    }
                    color={getLatencyColor(calculatedMetrics.averageLatency)}
                  />
                </Box>

                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Detection Accuracy
                  </Typography>
                  <Chip 
                    label={
                      calculatedMetrics.passRate >= 95 ? 'Excellent' :
                      calculatedMetrics.passRate >= 80 ? 'Good' : 'Needs Improvement'
                    }
                    color={getPassRateColor(calculatedMetrics.passRate)}
                  />
                </Box>

                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Signal Stability (Jitter)
                  </Typography>
                  <Chip 
                    label={
                      calculatedMetrics.jitter <= 50 ? 'Stable' :
                      calculatedMetrics.jitter <= 100 ? 'Moderate' : 'Unstable'
                    }
                    color={
                      calculatedMetrics.jitter <= 50 ? 'success' :
                      calculatedMetrics.jitter <= 100 ? 'warning' : 'error'
                    }
                  />
                </Box>

                {isRunning && (
                  <Box sx={{ textAlign: 'center', mt: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      Live monitoring active - metrics update in real-time
                    </Typography>
                  </Box>
                )}
              </Stack>
            </Paper>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default TimingMetricsPanel;