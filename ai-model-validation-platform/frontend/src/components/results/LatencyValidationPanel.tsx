import React, { useState, useEffect, useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Box,
  Alert,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  Timer,
  CheckCircle,
  Error as ErrorIcon,
  Warning,
  Timeline,
  Assessment,
  Speed
} from '@mui/icons-material';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';

import { LatencyValidationResult, DetectionLatencyEvent, LatencyStatistics } from '../../types/enhanced-results';

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend);

interface LatencyValidationPanelProps {
  sessionId: string;
  data: LatencyValidationResult | null;
  loading?: boolean;
  error?: string;
}

export const LatencyValidationPanel: React.FC<LatencyValidationPanelProps> = ({
  sessionId,
  data,
  loading = false,
  error
}) => {
  const [selectedTimeRange, setSelectedTimeRange] = useState<'all' | '1m' | '5m' | '15m'>('all');
  const [showOutliers, setShowOutliers] = useState(true);
  const [chartType, setChartType] = useState<'histogram' | 'timeline'>('histogram');

  // Filter events based on time range
  const filteredEvents = useMemo(() => {
    if (!data?.detection_events) return [];
    
    const now = Date.now();
    let cutoffTime = 0;
    
    switch (selectedTimeRange) {
      case '1m':
        cutoffTime = now - 60 * 1000;
        break;
      case '5m':
        cutoffTime = now - 5 * 60 * 1000;
        break;
      case '15m':
        cutoffTime = now - 15 * 60 * 1000;
        break;
      default:
        return data.detection_events;
    }
    
    return data.detection_events.filter(event => event.timestamp >= cutoffTime);
  }, [data?.detection_events, selectedTimeRange]);

  // Calculate histogram data for latency distribution
  const histogramData = useMemo(() => {
    if (!filteredEvents.length) return null;
    
    const latencies = filteredEvents.map(event => event.detection_time_ms);
    const binCount = 20;
    const min = Math.min(...latencies);
    const max = Math.max(...latencies);
    const binSize = (max - min) / binCount;
    
    const bins = Array.from({ length: binCount }, (_, i) => ({
      min: min + i * binSize,
      max: min + (i + 1) * binSize,
      count: 0,
      passed: 0,
      failed: 0
    }));
    
    filteredEvents.forEach(event => {
      const binIndex = Math.min(Math.floor((event.detection_time_ms - min) / binSize), binCount - 1);
      bins[binIndex].count++;
      if (event.passed) {
        bins[binIndex].passed++;
      } else {
        bins[binIndex].failed++;
      }
    });
    
    return {
      labels: bins.map(bin => `${bin.min.toFixed(0)}-${bin.max.toFixed(0)}ms`),
      datasets: [
        {
          label: 'Passed Detections',
          data: bins.map(bin => bin.passed),
          backgroundColor: 'rgba(76, 175, 80, 0.8)',
          borderColor: 'rgba(76, 175, 80, 1)',
          borderWidth: 1
        },
        {
          label: 'Failed Detections',
          data: bins.map(bin => bin.failed),
          backgroundColor: 'rgba(244, 67, 54, 0.8)',
          borderColor: 'rgba(244, 67, 54, 1)',
          borderWidth: 1
        }
      ]
    };
  }, [filteredEvents]);

  // Calculate timeline data
  const timelineData = useMemo(() => {
    if (!filteredEvents.length) return null;
    
    // Group events by time intervals (every 10 seconds for timeline view)
    const timeInterval = 10000; // 10 seconds
    const groups = new Map<number, { passed: number; failed: number; latencies: number[] }>();
    
    filteredEvents.forEach(event => {
      const timeGroup = Math.floor(event.timestamp / timeInterval) * timeInterval;
      const existing = groups.get(timeGroup) || { passed: 0, failed: 0, latencies: [] };
      
      if (event.passed) {
        existing.passed++;
      } else {
        existing.failed++;
      }
      existing.latencies.push(event.detection_time_ms);
      
      groups.set(timeGroup, existing);
    });
    
    const sortedGroups = Array.from(groups.entries()).sort((a, b) => a[0] - b[0]);
    
    return {
      labels: sortedGroups.map(([timestamp]) => new Date(timestamp).toLocaleTimeString()),
      datasets: [
        {
          label: 'Average Latency (ms)',
          data: sortedGroups.map(([, group]) => 
            group.latencies.reduce((sum, lat) => sum + lat, 0) / group.latencies.length
          ),
          borderColor: 'rgba(33, 150, 243, 1)',
          backgroundColor: 'rgba(33, 150, 243, 0.1)',
          yAxisID: 'y',
          type: 'line' as const
        },
        {
          label: 'Pass Rate (%)',
          data: sortedGroups.map(([, group]) => 
            (group.passed / (group.passed + group.failed)) * 100
          ),
          borderColor: 'rgba(76, 175, 80, 1)',
          backgroundColor: 'rgba(76, 175, 80, 0.1)',
          yAxisID: 'y1',
          type: 'line' as const
        }
      ]
    };
  }, [filteredEvents]);

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: chartType === 'histogram' ? 'Latency Distribution' : 'Latency Over Time'
      },
    },
    scales: chartType === 'timeline' ? {
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        title: {
          display: true,
          text: 'Latency (ms)'
        }
      },
      y1: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        title: {
          display: true,
          text: 'Pass Rate (%)'
        },
        max: 100,
        min: 0,
        grid: {
          drawOnChartArea: false,
        },
      },
    } : undefined,
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            LabJack Timing Validation
          </Typography>
          <LinearProgress />
          <Typography variant="body2" sx={{ mt: 1 }}>
            Loading latency validation results...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error">
            <Typography variant="h6">Error Loading Latency Validation</Typography>
            <Typography>{error}</Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">
            <Typography variant="h6">No Latency Data Available</Typography>
            <Typography>
              Latency validation data is not available for this session. 
              Ensure that LabJack timing validation is properly configured.
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box sx={{ space: 2 }}>
      {/* Summary Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <CheckCircle sx={{ mr: 1, color: 'success.main' }} />
                <Typography variant="h6">Pass Rate</Typography>
              </Box>
              <Typography variant="h3" color={data.pass_rate >= 95 ? 'success.main' : data.pass_rate >= 85 ? 'warning.main' : 'error.main'}>
                {data.pass_rate.toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {data.passed_detections} of {data.total_detections} detections
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Timer sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Avg Latency</Typography>
              </Box>
              <Typography variant="h3" color={data.average_latency_ms <= 50 ? 'success.main' : data.average_latency_ms <= 100 ? 'warning.main' : 'error.main'}>
                {data.average_latency_ms.toFixed(1)}ms
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Threshold: {data.latency_threshold_ms}ms
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Speed sx={{ mr: 1, color: 'warning.main' }} />
                <Typography variant="h6">Max Latency</Typography>
              </Box>
              <Typography variant="h3" color={data.max_latency_ms <= 100 ? 'success.main' : data.max_latency_ms <= 200 ? 'warning.main' : 'error.main'}>
                {data.max_latency_ms.toFixed(1)}ms
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Min: {data.min_latency_ms.toFixed(1)}ms
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ErrorIcon sx={{ mr: 1, color: 'error.main' }} />
                <Typography variant="h6">Failed Detections</Typography>
              </Box>
              <Typography variant="h3" color="error.main">
                {data.failed_detections}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {((data.failed_detections / data.total_detections) * 100).toFixed(1)}% failure rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Chart Controls */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={selectedTimeRange}
              onChange={(e) => setSelectedTimeRange(e.target.value as any)}
              label="Time Range"
            >
              <MenuItem value="all">All Data</MenuItem>
              <MenuItem value="15m">Last 15 min</MenuItem>
              <MenuItem value="5m">Last 5 min</MenuItem>
              <MenuItem value="1m">Last 1 min</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Chart Type</InputLabel>
            <Select
              value={chartType}
              onChange={(e) => setChartType(e.target.value as any)}
              label="Chart Type"
            >
              <MenuItem value="histogram">Histogram</MenuItem>
              <MenuItem value="timeline">Timeline</MenuItem>
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Switch
                checked={showOutliers}
                onChange={(e) => setShowOutliers(e.target.checked)}
                size="small"
              />
            }
            label="Show Outliers"
          />

          <Box sx={{ ml: 'auto' }}>
            <Chip
              label={`${filteredEvents.length} events`}
              size="small"
              variant="outlined"
            />
          </Box>
        </Box>
      </Paper>

      {/* Chart */}
      <Grid container spacing={2}>
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              {chartType === 'histogram' && histogramData ? (
                <Bar data={histogramData} options={chartOptions} />
              ) : timelineData ? (
                <Line data={timelineData} options={chartOptions} />
              ) : (
                <Alert severity="info">No data available for the selected time range</Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={4}>
          {/* Statistics */}
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Latency Statistics
              </Typography>
              {data.summary_statistics && (
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Mean:</Typography>
                    <Typography variant="body2" fontWeight="medium">
                      {data.summary_statistics.mean.toFixed(1)}ms
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Median:</Typography>
                    <Typography variant="body2" fontWeight="medium">
                      {data.summary_statistics.median.toFixed(1)}ms
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Std Dev:</Typography>
                    <Typography variant="body2" fontWeight="medium">
                      ±{data.summary_statistics.std_deviation.toFixed(1)}ms
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">95th Percentile:</Typography>
                    <Typography variant="body2" fontWeight="medium">
                      {data.summary_statistics.p95.toFixed(1)}ms
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">99th Percentile:</Typography>
                    <Typography variant="body2" fontWeight="medium">
                      {data.summary_statistics.p99.toFixed(1)}ms
                    </Typography>
                  </Box>
                  {data.summary_statistics.outlier_count > 0 && (
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2" color="warning.main">Outliers:</Typography>
                      <Typography variant="body2" fontWeight="medium" color="warning.main">
                        {data.summary_statistics.outlier_count}
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Failed Detections List */}
          {data.failed_detections > 0 && (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Recent Failed Detections
                </Typography>
                <List dense>
                  {filteredEvents
                    .filter(event => !event.passed)
                    .slice(0, 5)
                    .map((event, index) => (
                      <React.Fragment key={event.id}>
                        <ListItem>
                          <ListItemIcon>
                            <ErrorIcon color="error" />
                          </ListItemIcon>
                          <ListItemText
                            primary={`Frame ${event.frame_number}`}
                            secondary={`${event.detection_time_ms.toFixed(1)}ms - ${event.error_message || 'Exceeded threshold'}`}
                          />
                        </ListItem>
                        {index < 4 && <Divider />}
                      </React.Fragment>
                    ))}
                </List>
                {data.failed_detections > 5 && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
                    And {data.failed_detections - 5} more failed detections...
                  </Typography>
                )}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};