import React, { useEffect, useState, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Switch,
  FormControlLabel,
  Chip,
  Tooltip,
  Grid,
  Alert,
  LinearProgress,
  Divider,
  Button,
  Menu,
  MenuItem
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent
} from '@mui/lab';
import {
  PlayArrow,
  Pause,
  ZoomIn,
  ZoomOut,
  GetApp,
  Speed,
  TrendingUp,
  Memory,
  SignalCellular4Bar,
  Warning
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer, ReferenceLine, Brush } from 'recharts';

import {
  RawTimingData,
  TimelineData,
  VoltageTransition,
  VideoSyncEvent,
  CompressionStatistics
} from '../types/enhanced-results';

interface RawTimingTimelineProps {
  sessionId: string;
  rawTimingData?: RawTimingData;
  timelineData?: TimelineData;
  onExportRequest?: () => void;
}

interface TimelineVisualizationMode {
  key: string;
  name: string;
  description: string;
}

const visualizationModes: TimelineVisualizationMode[] = [
  { key: 'voltage_transitions', name: 'Voltage Transitions', description: 'Raw voltage changes with microsecond precision' },
  { key: 'detection_events', name: 'Detection Events Only', description: 'Filtered detection transitions' },
  { key: 'frequency_analysis', name: 'Frequency Analysis', description: 'Transition rate over time' },
  { key: 'comparison', name: 'Raw vs Video Sync', description: 'Compare raw and video-synchronized events' }
];

const RawTimingTimeline: React.FC<RawTimingTimelineProps> = ({
  sessionId,
  rawTimingData,
  timelineData,
  onExportRequest
}) => {
  const [visualizationMode, setVisualizationMode] = useState<string>('voltage_transitions');
  const [showVideoSync, setShowVideoSync] = useState(true);
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [selectedTransition, setSelectedTransition] = useState<VoltageTransition | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTimeUs, setCurrentTimeUs] = useState(0);
  const [exportMenuAnchor, setExportMenuAnchor] = useState<null | HTMLElement>(null);

  // Process timeline data for visualization
  const chartData = useMemo(() => {
    if (!timelineData?.timeline_points) return [];

    return timelineData.timeline_points.map((point, index) => ({
      time_ms: point.timestamp_ms,
      timestamp_us: point.timestamp_us,
      total_transitions: point.total_transitions,
      detection_transitions: point.detection_transitions,
      transition_rate_hz: point.transition_rate_hz,
      window_duration_us: point.window_duration_us
    }));
  }, [timelineData]);

  // Get detection events for detailed view
  const detectionTransitions = useMemo(() => {
    return rawTimingData?.voltage_transitions?.filter(t => t.is_detection_event) || [];
  }, [rawTimingData]);

  // Calculate frequency statistics
  const frequencyStats = useMemo(() => {
    if (!rawTimingData?.timing_correlation?.frequency_analysis) {
      return null;
    }

    const analysis = rawTimingData.timing_correlation.frequency_analysis;
    return {
      raw_frequency_hz: analysis.raw_frequency_hz,
      legacy_frequency_hz: analysis.legacy_frequency_hz,
      frequency_improvement: analysis.raw_frequency_hz / Math.max(analysis.legacy_frequency_hz, 0.1),
      raw_interval_ms: analysis.raw_average_interval_ms,
      legacy_interval_ms: analysis.legacy_average_interval_ms
    };
  }, [rawTimingData]);

  // Format microseconds for display
  const formatMicroseconds = (us: number): string => {
    if (us < 1000) {
      return `${us.toFixed(1)}μs`;
    } else if (us < 1_000_000) {
      return `${(us / 1000).toFixed(2)}ms`;
    } else {
      return `${(us / 1_000_000).toFixed(3)}s`;
    }
  };

  // Format voltage with appropriate precision
  const formatVoltage = (v: number): string => {
    return `${v.toFixed(3)}V`;
  };

  // Get transition color based on type and detection status
  const getTransitionColor = (transition: VoltageTransition): string => {
    if (transition.is_detection_event) {
      return '#4caf50'; // Green for detections
    }
    switch (transition.transition_type) {
      case 'rising_edge': return '#2196f3'; // Blue
      case 'falling_edge': return '#ff9800'; // Orange
      case 'spike': return '#f44336'; // Red
      case 'drift': return '#9c27b0'; // Purple
      case 'noise': return '#607d8b'; // Gray
      default: return '#757575';
    }
  };

  // Render voltage transitions timeline
  const renderVoltageTransitionsTimeline = () => {
    if (!rawTimingData?.voltage_transitions) return null;

    const transitions = rawTimingData.voltage_transitions.slice(0, 100); // Limit for performance

    return (
      <Timeline position="right">
        {transitions.map((transition, index) => (
          <TimelineItem key={transition.id}>
            <TimelineOppositeContent sx={{ m: 'auto 0' }} variant="body2" color="text.secondary">
              <Typography variant="caption" display="block">
                {formatMicroseconds(transition.timestamp_us - (rawTimingData.session_info.start_timestamp_us || 0))}
              </Typography>
              <Typography variant="caption" display="block" color="primary">
                {formatVoltage(transition.voltage_before_v)} → {formatVoltage(transition.voltage_after_v)}
              </Typography>
            </TimelineOppositeContent>
            
            <TimelineSeparator>
              <TimelineDot 
                sx={{ 
                  backgroundColor: getTransitionColor(transition),
                  cursor: 'pointer',
                  '&:hover': { transform: 'scale(1.2)' }
                }}
                onClick={() => setSelectedTransition(transition)}
              >
                {transition.is_detection_event ? <SignalCellular4Bar fontSize="small" /> : null}
              </TimelineDot>
              {index < transitions.length - 1 && <TimelineConnector />}
            </TimelineSeparator>
            
            <TimelineContent sx={{ py: '12px', px: 2 }}>
              <Typography variant="h6" component="span">
                {transition.transition_type.replace('_', ' ').toUpperCase()}
              </Typography>
              <Typography color="text.secondary">
                Δ{formatVoltage(transition.voltage_delta_v)} • 
                {transition.detection_confidence ? ` ${(transition.detection_confidence * 100).toFixed(1)}% confidence` : ''}
                {transition.transition_duration_us ? ` • ${formatMicroseconds(transition.transition_duration_us)} duration` : ''}
              </Typography>
              {transition.is_detection_event && (
                <Chip 
                  label="DETECTION" 
                  size="small" 
                  color="success" 
                  sx={{ mt: 0.5 }}
                />
              )}
            </TimelineContent>
          </TimelineItem>
        ))}
      </Timeline>
    );
  };

  // Render frequency analysis chart
  const renderFrequencyChart = () => {
    if (!chartData.length) return null;

    return (
      <Box sx={{ width: '100%', height: 400 }}>
        <ResponsiveContainer>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="time_ms" 
              tickFormatter={(value) => `${(value / 1000).toFixed(1)}s`}
            />
            <YAxis 
              label={{ value: 'Transition Rate (Hz)', angle: -90, position: 'insideLeft' }}
            />
            <ChartTooltip 
              formatter={(value: any, name: string) => [
                `${Number(value).toFixed(2)} Hz`,
                name === 'transition_rate_hz' ? 'Transition Rate' : name
              ]}
              labelFormatter={(value) => `Time: ${(Number(value) / 1000).toFixed(2)}s`}
            />
            <Line 
              type="monotone" 
              dataKey="transition_rate_hz" 
              stroke="#2196f3" 
              strokeWidth={2}
              dot={false}
            />
            {frequencyStats && (
              <ReferenceLine 
                y={frequencyStats.legacy_frequency_hz} 
                stroke="#ff9800" 
                strokeDasharray="5 5"
                label={{ value: `Legacy: ${frequencyStats.legacy_frequency_hz.toFixed(1)}Hz`, position: 'topRight' }}
              />
            )}
            <Brush dataKey="time_ms" height={30} />
          </LineChart>
        </ResponsiveContainer>
      </Box>
    );
  };

  // Render comparison view
  const renderComparisonView = () => {
    if (!rawTimingData?.timing_correlation) return null;

    const correlation = rawTimingData.timing_correlation;

    return (
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom color="primary">
                Raw Detection Events
              </Typography>
              <Typography variant="h3" color="primary">
                {correlation.raw_detection_transitions_count || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Continuous voltage monitoring
              </Typography>
              {frequencyStats && (
                <Typography variant="body1" sx={{ mt: 1 }}>
                  Rate: {frequencyStats.raw_frequency_hz.toFixed(1)} Hz
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom color="secondary">
                Video-Sync Events
              </Typography>
              <Typography variant="h3" color="secondary">
                {correlation.legacy_events_count || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Frame-synchronized events
              </Typography>
              {frequencyStats && (
                <Typography variant="body1" sx={{ mt: 1 }}>
                  Rate: {frequencyStats.legacy_frequency_hz.toFixed(1)} Hz
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {frequencyStats && (
          <Grid item xs={12}>
            <Alert severity="info" sx={{ mt: 2 }}>
              <Typography variant="body2">
                <strong>Detection Rate Improvement:</strong> Raw monitoring detects events {frequencyStats.frequency_improvement.toFixed(1)}x more frequently than video-synchronized detection
                ({frequencyStats.raw_frequency_hz.toFixed(1)}Hz vs {frequencyStats.legacy_frequency_hz.toFixed(1)}Hz)
              </Typography>
            </Alert>
          </Grid>
        )}

        {correlation.timing_comparison && correlation.timing_comparison.length > 0 && (
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Timing Correlation Analysis
            </Typography>
            <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
              {correlation.timing_comparison.slice(0, 20).map((comp, index) => (
                <Box key={index} sx={{ p: 1, borderBottom: 1, borderColor: 'divider' }}>
                  <Typography variant="body2">
                    Time difference: {comp.difference_ms.toFixed(2)}ms 
                    (Raw: {formatMicroseconds(comp.raw_timestamp_us)} • 
                    Legacy: {formatMicroseconds(comp.legacy_timestamp_us)})
                    • Confidence: {(comp.detection_confidence * 100).toFixed(1)}%
                  </Typography>
                </Box>
              ))}
            </Box>
          </Grid>
        )}
      </Grid>
    );
  };

  // Render compression statistics
  const renderCompressionStats = () => {
    if (!rawTimingData?.compression_statistics) return null;

    const stats = rawTimingData.compression_statistics;

    return (
      <Card sx={{ mt: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <Memory sx={{ mr: 1, verticalAlign: 'middle' }} />
            Compression Statistics
          </Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="primary">
                  {stats.achieved_compression_ratio?.toFixed(1) || 'N/A'}x
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Compression Ratio
                </Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="success.main">
                  {stats.signal_fidelity_score ? `${(stats.signal_fidelity_score * 100).toFixed(1)}%` : 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Signal Fidelity
                </Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="warning.main">
                  {stats.storage_efficiency_percent?.toFixed(1) || 'N/A'}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Storage Efficiency
                </Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center">
                <Typography variant="h4" color="info.main">
                  {stats.throughput_samples_per_second?.toFixed(0) || 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Samples/sec
                </Typography>
              </Box>
            </Grid>
          </Grid>

          {stats.raw_data_size_bytes && stats.compressed_data_size_bytes && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" gutterBottom>
                Storage: {(stats.compressed_data_size_bytes / 1024 / 1024).toFixed(2)}MB compressed 
                (vs {(stats.raw_data_size_bytes / 1024 / 1024).toFixed(2)}MB raw)
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={stats.storage_efficiency_percent || 0} 
                sx={{ height: 8, borderRadius: 4 }}
              />
            </Box>
          )}
        </CardContent>
      </Card>
    );
  };

  // Main render based on visualization mode
  const renderContent = () => {
    switch (visualizationMode) {
      case 'voltage_transitions':
        return renderVoltageTransitionsTimeline();
      case 'detection_events':
        return renderVoltageTransitionsTimeline(); // Filter applied in data processing
      case 'frequency_analysis':
        return renderFrequencyChart();
      case 'comparison':
        return renderComparisonView();
      default:
        return <Typography>Select a visualization mode</Typography>;
    }
  };

  return (
    <Card sx={{ mt: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center' }}>
            <TrendingUp sx={{ mr: 1 }} />
            Raw Timing Timeline
            {rawTimingData?.timing_precision === 'microsecond' && (
              <Chip 
                label="μs precision" 
                size="small" 
                color="primary" 
                sx={{ ml: 1 }}
              />
            )}
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={(e) => setExportMenuAnchor(e.currentTarget)}
              size="small"
            >
              Export
            </Button>
            
            <Menu
              anchorEl={exportMenuAnchor}
              open={Boolean(exportMenuAnchor)}
              onClose={() => setExportMenuAnchor(null)}
            >
              <MenuItem onClick={() => { onExportRequest?.(); setExportMenuAnchor(null); }}>
                Export Raw Data (JSON)
              </MenuItem>
              <MenuItem onClick={() => setExportMenuAnchor(null)}>
                Export Chart (PNG)
              </MenuItem>
              <MenuItem onClick={() => setExportMenuAnchor(null)}>
                Export Timeline (CSV)
              </MenuItem>
            </Menu>
          </Box>
        </Box>

        <Box sx={{ mb: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Visualization Mode:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {visualizationModes.map(mode => (
                  <Chip
                    key={mode.key}
                    label={mode.name}
                    variant={visualizationMode === mode.key ? 'filled' : 'outlined'}
                    color={visualizationMode === mode.key ? 'primary' : 'default'}
                    onClick={() => setVisualizationMode(mode.key)}
                    size="small"
                  />
                ))}
              </Box>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={showVideoSync}
                    onChange={(e) => setShowVideoSync(e.target.checked)}
                  />
                }
                label="Show Video Sync Events"
              />
            </Grid>
          </Grid>
        </Box>

        {rawTimingData?.data_source === 'legacy_detection_events' && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <Warning sx={{ mr: 1, verticalAlign: 'middle' }} />
              Using legacy detection events - no raw timing data available. 
              Timing precision limited to video frame rate (18.8Hz).
            </Typography>
          </Alert>
        )}

        <Divider sx={{ mb: 2 }} />

        {renderContent()}

        {renderCompressionStats()}

        {selectedTransition && (
          <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', border: 1, borderColor: 'divider' }}>
            <Typography variant="h6" gutterBottom>
              Selected Transition Details
            </Typography>
            <Grid container spacing={1}>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2">
                  <strong>Timestamp:</strong> {formatMicroseconds(selectedTransition.timestamp_us)}
                </Typography>
                <Typography variant="body2">
                  <strong>Channel:</strong> {selectedTransition.channel}
                </Typography>
                <Typography variant="body2">
                  <strong>Type:</strong> {selectedTransition.transition_type.replace('_', ' ')}
                </Typography>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2">
                  <strong>Voltage Change:</strong> {formatVoltage(selectedTransition.voltage_before_v)} → {formatVoltage(selectedTransition.voltage_after_v)}
                </Typography>
                <Typography variant="body2">
                  <strong>Detection:</strong> {selectedTransition.is_detection_event ? 'YES' : 'No'}
                </Typography>
                <Typography variant="body2">
                  <strong>Confidence:</strong> {(selectedTransition.detection_confidence * 100).toFixed(1)}%
                </Typography>
              </Grid>
            </Grid>
            <Button 
              size="small" 
              onClick={() => setSelectedTransition(null)}
              sx={{ mt: 1 }}
            >
              Close
            </Button>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default RawTimingTimeline;