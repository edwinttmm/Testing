import React, { useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Grid,
  Chip,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import {
  Timeline,
  ShowChart,
  BarChart as BarChartIcon,
  PieChart as PieChartIcon,
  TrendingUp,
  Refresh
} from '@mui/icons-material';
import { EnhancedDashboardStats } from '../../services/types';

interface RealtimeMetricsChartProps {
  stats: EnhancedDashboardStats;
  timeSeriesData?: Array<{
    timestamp: string;
    accuracy: number;
    detections: number;
    latency: number;
    signalSuccess: number;
  }>;
  chartType?: 'line' | 'area' | 'bar' | 'pie';
  showAnimation?: boolean;
  autoRefresh?: boolean;
  onRefresh?: () => void;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

export const RealtimeMetricsChart: React.FC<RealtimeMetricsChartProps> = ({
  stats,
  timeSeriesData = [],
  chartType = 'line',
  showAnimation = true,
  autoRefresh = true,
  onRefresh
}) => {
  const [selectedChart, setSelectedChart] = React.useState(chartType);
  const [showTrend, setShowTrend] = React.useState(true);
  const [metric, setMetric] = React.useState<'accuracy' | 'detections' | 'latency' | 'signalSuccess'>('accuracy');

  // Generate mock time series data if none provided
  const chartData = useMemo(() => {
    if (timeSeriesData.length > 0) {
      return timeSeriesData;
    }

    // Generate last 24 hours of mock data
    const now = new Date();
    const data = [];
    for (let i = 23; i >= 0; i--) {
      const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000);
      data.push({
        timestamp: timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        accuracy: Math.max(0, Math.min(100, (stats.average_accuracy || 0) + (Math.random() - 0.5) * 20)),
        detections: Math.floor((stats.detection_event_count || 0) * 0.1 + Math.random() * 10),
        latency: Math.max(0, 50 + (Math.random() - 0.5) * 40),
        signalSuccess: Math.max(0, Math.min(100, (stats.signal_processing_metrics?.successRate || 0) + (Math.random() - 0.5) * 15))
      });
    }
    return data;
  }, [stats, timeSeriesData]);

  // Pie chart data
  const pieData = useMemo(() => [
    { name: 'Projects', value: stats.project_count || 0, color: COLORS[0] },
    { name: 'Videos', value: stats.video_count || 0, color: COLORS[1] },
    { name: 'Tests', value: stats.test_session_count || 0, color: COLORS[2] },
    { name: 'Detections', value: stats.detection_event_count || 0, color: COLORS[3] }
  ], [stats]);

  const getMetricColor = (value: number, type: string) => {
    if (type === 'latency') {
      return value < 50 ? '#4caf50' : value < 100 ? '#ff9800' : '#f44336';
    }
    return value > 80 ? '#4caf50' : value > 60 ? '#ff9800' : '#f44336';
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <Box
          sx={{
            bgcolor: 'background.paper',
            p: 1.5,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            boxShadow: 2
          }}
        >
          <Typography variant="caption" gutterBottom>
            {label}
          </Typography>
          {payload.map((entry: any, index: number) => (
            <Typography key={index} variant="body2" sx={{ color: entry.color }}>
              {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
              {entry.dataKey === 'accuracy' || entry.dataKey === 'signalSuccess' ? '%' : 
               entry.dataKey === 'latency' ? 'ms' : ''}
            </Typography>
          ))}
        </Box>
      );
    }
    return null;
  };

  const renderLineChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <RechartsTooltip content={<CustomTooltip />} />
        <Legend />
        {metric === 'accuracy' && (
          <Line 
            type="monotone" 
            dataKey="accuracy" 
            stroke="#2196f3" 
            strokeWidth={2}
            dot={{ fill: '#2196f3', strokeWidth: 2, r: 4 }}
            name="Accuracy (%)"
            animationDuration={showAnimation ? 1000 : 0}
          />
        )}
        {metric === 'detections' && (
          <Line 
            type="monotone" 
            dataKey="detections" 
            stroke="#4caf50" 
            strokeWidth={2}
            dot={{ fill: '#4caf50', strokeWidth: 2, r: 4 }}
            name="Detections"
            animationDuration={showAnimation ? 1000 : 0}
          />
        )}
        {metric === 'latency' && (
          <Line 
            type="monotone" 
            dataKey="latency" 
            stroke="#ff9800" 
            strokeWidth={2}
            dot={{ fill: '#ff9800', strokeWidth: 2, r: 4 }}
            name="Latency (ms)"
            animationDuration={showAnimation ? 1000 : 0}
          />
        )}
        {metric === 'signalSuccess' && (
          <Line 
            type="monotone" 
            dataKey="signalSuccess" 
            stroke="#9c27b0" 
            strokeWidth={2}
            dot={{ fill: '#9c27b0', strokeWidth: 2, r: 4 }}
            name="Signal Success (%)"
            animationDuration={showAnimation ? 1000 : 0}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );

  const renderAreaChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <RechartsTooltip content={<CustomTooltip />} />
        <Legend />
        <Area 
          type="monotone" 
          dataKey={metric} 
          stroke="#2196f3" 
          fill="#2196f3" 
          fillOpacity={0.6}
          name={metric.charAt(0).toUpperCase() + metric.slice(1)}
        />
      </AreaChart>
    </ResponsiveContainer>
  );

  const renderBarChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <RechartsTooltip content={<CustomTooltip />} />
        <Legend />
        <Bar 
          dataKey={metric} 
          fill="#2196f3"
          name={metric.charAt(0).toUpperCase() + metric.slice(1)}
        />
      </BarChart>
    </ResponsiveContainer>
  );

  const renderPieChart = () => (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={pieData}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={({ name, value, percent }) => `${name}: ${value} (${(percent * 100).toFixed(1)}%)`}
          outerRadius={80}
          fill="#8884d8"
          dataKey="value"
        >
          {pieData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <RechartsTooltip />
      </PieChart>
    </ResponsiveContainer>
  );

  const renderChart = () => {
    switch (selectedChart) {
      case 'line':
        return renderLineChart();
      case 'area':
        return renderAreaChart();
      case 'bar':
        return renderBarChart();
      case 'pie':
        return renderPieChart();
      default:
        return renderLineChart();
    }
  };

  return (
    <Card>
      <CardContent>
        {/* Header with Controls */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Timeline color="primary" />
            Real-time Metrics
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {autoRefresh && (
              <Chip
                icon={<TrendingUp />}
                label="Live"
                color="success"
                size="small"
                variant="filled"
              />
            )}
            
            {onRefresh && (
              <Tooltip title="Refresh Data">
                <IconButton onClick={onRefresh} size="small">
                  <Refresh />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* Chart Controls */}
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl size="small" fullWidth>
              <InputLabel>Chart Type</InputLabel>
              <Select
                value={selectedChart}
                label="Chart Type"
                onChange={(e) => setSelectedChart(e.target.value as any)}
              >
                <MenuItem value="line">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <ShowChart fontSize="small" />
                    Line Chart
                  </Box>
                </MenuItem>
                <MenuItem value="area">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Timeline fontSize="small" />
                    Area Chart
                  </Box>
                </MenuItem>
                <MenuItem value="bar">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <BarChartIcon fontSize="small" />
                    Bar Chart
                  </Box>
                </MenuItem>
                <MenuItem value="pie">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <PieChartIcon fontSize="small" />
                    Pie Chart
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {selectedChart !== 'pie' && (
            <Grid item xs={12} sm={6} md={3}>
              <FormControl size="small" fullWidth>
                <InputLabel>Metric</InputLabel>
                <Select
                  value={metric}
                  label="Metric"
                  onChange={(e) => setMetric(e.target.value as any)}
                >
                  <MenuItem value="accuracy">Accuracy (%)</MenuItem>
                  <MenuItem value="detections">Detections</MenuItem>
                  <MenuItem value="latency">Latency (ms)</MenuItem>
                  <MenuItem value="signalSuccess">Signal Success (%)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          )}

          <Grid item xs={12} sm={6} md={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={showAnimation}
                  onChange={(e) => setShowAnimation && setShowAnimation(e.target.checked)}
                  size="small"
                />
              }
              label="Animations"
            />
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={showTrend}
                  onChange={(e) => setShowTrend(e.target.checked)}
                  size="small"
                />
              }
              label="Show Trend"
            />
          </Grid>
        </Grid>

        {/* Chart */}
        <Box sx={{ height: 300 }}>
          {renderChart()}
        </Box>

        {/* Current Values */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Current Values
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <Typography variant="body2">
                <strong>Accuracy:</strong> {(stats.average_accuracy || 0).toFixed(1)}%
              </Typography>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Typography variant="body2">
                <strong>Detections:</strong> {stats.detection_event_count || 0}
              </Typography>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Typography variant="body2">
                <strong>Signal Success:</strong> {(stats.signal_processing_metrics?.successRate || 0).toFixed(1)}%
              </Typography>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Typography variant="body2">
                <strong>Processing Time:</strong> {(stats.signal_processing_metrics?.avgProcessingTime || 0).toFixed(1)}ms
              </Typography>
            </Grid>
          </Grid>
        </Box>
      </CardContent>
    </Card>
  );
};

export default RealtimeMetricsChart;