import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  LinearProgress,
  Box,
  Chip
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Speed,
  Assessment as AccuracyIcon,
  Timer,
  CheckCircle,
  Error as ErrorIcon
} from '@mui/icons-material';
import { ComparisonMetrics } from '../../types/enhanced-results';

interface ComparisonMetricsCardProps {
  metrics: ComparisonMetrics & { detectionCounts?: any };
  title?: string;
  compact?: boolean;
  validationType?: 'ai' | 'labjack';
}

export const ComparisonMetricsCard: React.FC<ComparisonMetricsCardProps> = ({
  metrics,
  title = "Performance Metrics",
  compact = false,
  validationType = 'ai'
}) => {
  const getPerformanceColor = (value: number, type: 'accuracy' | 'precision' | 'recall' | 'f1Score' | 'passRate' | 'latency' = 'accuracy') => {
    if (type === 'passRate') {
      if (value >= 95) return 'success';
      if (value >= 85) return 'info';
      if (value >= 70) return 'warning';
      return 'error';
    }
    if (type === 'latency') {
      if (value <= 50) return 'success';
      if (value <= 100) return 'info';
      if (value <= 200) return 'warning';
      return 'error';
    }
    if (value >= 0.9) return 'success';
    if (value >= 0.8) return 'info';
    if (value >= 0.7) return 'warning';
    return 'error';
  };

  const formatMetric = (value: number, type: 'percentage' | 'decimal' | 'latency' | 'count' = 'percentage') => {
    switch (type) {
      case 'percentage':
        return `${value.toFixed(1)}%`;
      case 'decimal':
        return `${(value * 100).toFixed(1)}%`;
      case 'latency':
        return `${value.toFixed(1)}ms`;
      case 'count':
        return value.toString();
      default:
        return value.toFixed(3);
    }
  };

  if (compact) {
    if (validationType === 'labjack') {
      return (
        <Card variant="outlined" sx={{ height: '100%' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {title}
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color={`${getPerformanceColor(metrics.passRate || 0, 'passRate')}.main`}>
                    {formatMetric(metrics.passRate || 0, 'percentage')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Pass Rate
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color={`${getPerformanceColor(metrics.averageLatencyMs || 0, 'latency')}.main`}>
                    {formatMetric(metrics.averageLatencyMs || 0, 'latency')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Avg Latency
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" color="success.main">
                    {formatMetric(metrics.passedDetections || 0, 'count')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Passed
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h5" color="error.main">
                    {formatMetric(metrics.failedDetections || 0, 'count')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Failed
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      );
    }
    // Original AI validation compact view
    return (
      <Card variant="outlined" sx={{ height: '100%' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.accuracy)}.main`}>
                  {formatMetric(metrics.accuracy, 'decimal')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Accuracy
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.f1Score, 'f1Score')}.main`}>
                  {formatMetric(metrics.f1Score, 'decimal')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  F1 Score
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h5" color={`${getPerformanceColor(metrics.precision, 'precision')}.main`}>
                  {formatMetric(metrics.precision, 'decimal')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Precision
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={6}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="h5" color={`${getPerformanceColor(metrics.recall, 'recall')}.main`}>
                  {formatMetric(metrics.recall, 'decimal')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Recall
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        
        {/* Primary Metrics */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          {validationType === 'labjack' ? (
            // LabJack timing validation metrics
            <>
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <CheckCircle sx={{ mr: 1, color: 'success.main' }} />
                  <Typography variant="h6">Pass Rate</Typography>
                </Box>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.passRate || 0, 'passRate')}.main`}>
                  {formatMetric(metrics.passRate || 0, 'percentage')}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metrics.passRate || 0}
                  color={getPerformanceColor(metrics.passRate || 0, 'passRate') as any}
                  sx={{ mt: 1 }}
                />
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Timer sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6">Avg Latency</Typography>
                </Box>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.averageLatencyMs || 0, 'latency')}.main`}>
                  {formatMetric(metrics.averageLatencyMs || 0, 'latency')}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(100, (metrics.averageLatencyMs || 0) / 2)}
                  color={getPerformanceColor(metrics.averageLatencyMs || 0, 'latency') as any}
                  sx={{ mt: 1 }}
                />
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Speed sx={{ mr: 1, color: 'warning.main' }} />
                  <Typography variant="h6">Max Latency</Typography>
                </Box>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.maxLatencyMs || 0, 'latency')}.main`}>
                  {formatMetric(metrics.maxLatencyMs || 0, 'latency')}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(100, (metrics.maxLatencyMs || 0) / 5)}
                  color={getPerformanceColor(metrics.maxLatencyMs || 0, 'latency') as any}
                  sx={{ mt: 1 }}
                />
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <ErrorIcon sx={{ mr: 1, color: 'error.main' }} />
                  <Typography variant="h6">Failed Detections</Typography>
                </Box>
                <Typography variant="h4" color="error.main">
                  {formatMetric(metrics.failedDetections || 0, 'count')}
                </Typography>
                <Box sx={{ mt: 1, height: 4, bgcolor: 'grey.200', borderRadius: 1 }}>
                  <Box
                    sx={{
                      height: '100%',
                      width: `${Math.min(100, ((metrics.failedDetections || 0) / (metrics.totalDetections || 1)) * 100)}%`,
                      bgcolor: 'error.main',
                      borderRadius: 1
                    }}
                  />
                </Box>
              </Grid>
            </>
          ) : (
            // Original AI validation metrics
            <>
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <AccuracyIcon sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6">Accuracy</Typography>
                </Box>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.accuracy)}.main`}>
                  {formatMetric(metrics.accuracy, 'decimal')}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metrics.accuracy * 100}
                  color={getPerformanceColor(metrics.accuracy) as any}
                  sx={{ mt: 1 }}
                />
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <TrendingUp sx={{ mr: 1, color: 'success.main' }} />
                  <Typography variant="h6">Precision</Typography>
                </Box>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.precision, 'precision')}.main`}>
                  {formatMetric(metrics.precision, 'decimal')}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metrics.precision * 100}
                  color={getPerformanceColor(metrics.precision, 'precision') as any}
                  sx={{ mt: 1 }}
                />
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <TrendingDown sx={{ mr: 1, color: 'info.main' }} />
                  <Typography variant="h6">Recall</Typography>
                </Box>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.recall, 'recall')}.main`}>
                  {formatMetric(metrics.recall, 'decimal')}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metrics.recall * 100}
                  color={getPerformanceColor(metrics.recall, 'recall') as any}
                  sx={{ mt: 1 }}
                />
              </Grid>
              
              <Grid item xs={6} md={3}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Speed sx={{ mr: 1, color: 'secondary.main' }} />
                  <Typography variant="h6">F1 Score</Typography>
                </Box>
                <Typography variant="h4" color={`${getPerformanceColor(metrics.f1Score, 'f1Score')}.main`}>
                  {formatMetric(metrics.f1Score, 'decimal')}
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metrics.f1Score * 100}
                  color={getPerformanceColor(metrics.f1Score, 'f1Score') as any}
                  sx={{ mt: 1 }}
                />
              </Grid>
            </>
          )}
        </Grid>

        {/* Secondary Metrics */}
        <Grid container spacing={2}>
          {validationType === 'labjack' ? (
            // LabJack timing validation secondary metrics
            <>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Total Detections
                </Typography>
                <Typography variant="h6">
                  {metrics.totalDetections || 0}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Passed Detections
                </Typography>
                <Typography variant="h6" color="success.main">
                  {metrics.passedDetections || 0}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Failed Detections
                </Typography>
                <Typography variant="h6" color="error.main">
                  {metrics.failedDetections || 0}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Min Latency
                </Typography>
                <Typography variant="h6">
                  {formatMetric(metrics.minLatencyMs || 0, 'latency')}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Threshold
                </Typography>
                <Typography variant="h6">
                  {formatMetric(metrics.latencyThresholdMs || 100, 'latency')}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Processing Latency
                </Typography>
                <Typography variant="h6">
                  {formatMetric(metrics.averageLatency || 0, 'latency')}
                </Typography>
              </Grid>
            </>
          ) : (
            // Original AI validation secondary metrics
            <>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  True Positives
                </Typography>
                <Typography variant="h6" color="success.main">
                  {metrics.truePositives}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  False Positives
                </Typography>
                <Typography variant="h6" color="error.main">
                  {metrics.falsePositives}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  False Negatives
                </Typography>
                <Typography variant="h6" color="warning.main">
                  {metrics.falseNegatives}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Avg IoU
                </Typography>
                <Typography variant="h6">
                  {formatMetric(metrics.averageIou, 'decimal')}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Avg Confidence
                </Typography>
                <Typography variant="h6">
                  {formatMetric(metrics.averageConfidence, 'decimal')}
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body2" color="text.secondary">
                  Avg Latency
                </Typography>
                <Typography variant="h6">
                  {metrics.averageLatency.toFixed(1)}ms
                </Typography>
              </Grid>
            </>
          )}
        </Grid>

        {/* Performance Indicators */}
        <Box sx={{ display: 'flex', gap: 1, mt: 2, flexWrap: 'wrap' }}>
          {validationType === 'labjack' ? (
            // LabJack timing performance chips
            <>
              <Chip
                label={`Pass Rate: ${formatMetric(metrics.passRate || 0, 'percentage')}`}
                color={getPerformanceColor(metrics.passRate || 0, 'passRate')}
                size="small"
              />
              <Chip
                label={`Avg: ${formatMetric(metrics.averageLatencyMs || 0, 'latency')}`}
                color={getPerformanceColor(metrics.averageLatencyMs || 0, 'latency')}
                size="small"
              />
              <Chip
                label={`Max: ${formatMetric(metrics.maxLatencyMs || 0, 'latency')}`}
                color={getPerformanceColor(metrics.maxLatencyMs || 0, 'latency')}
                size="small"
              />
              <Chip
                label={`${metrics.failedDetections || 0} failures`}
                color={metrics.failedDetections && metrics.failedDetections > 0 ? 'error' : 'success'}
                size="small"
              />
            </>
          ) : (
            // Original AI validation chips
            <>
              <Chip
                label={`Accuracy: ${formatMetric(metrics.accuracy, 'decimal')}`}
                color={getPerformanceColor(metrics.accuracy)}
                size="small"
              />
              <Chip
                label={`IoU: ${formatMetric(metrics.averageIou, 'decimal')}`}
                color={getPerformanceColor(metrics.averageIou)}
                size="small"
              />
              <Chip
                label={`${metrics.averageLatency.toFixed(1)}ms latency`}
                color={metrics.averageLatency < 100 ? 'success' : metrics.averageLatency < 200 ? 'warning' : 'error'}
                size="small"
              />
            </>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};