import React, { useState, useEffect, useMemo } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Tabs,
  Tab,
  Grid,
  Paper,
  useTheme,
  Chip,
  IconButton,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';
import {
  Analytics,
  Speed,
  Assessment,
  TrendingUp,
  Refresh,
  Download,
  FilterAlt,
} from '@mui/icons-material';
import { EnhancedDashboardStats } from '../../services/types';

interface PerformanceData {
  metric: string;
  value: number;
  benchmark: number;
  improvement: number;
  color: string;
}

interface LatencyData {
  timeRange: string;
  avgLatency: number;
  p95Latency: number;
  p99Latency: number;
}

interface PerformanceMetricsPanelProps {
  stats: EnhancedDashboardStats | null;
  loading?: boolean;
  className?: string;
}

const PerformanceMetricsPanel: React.FC<PerformanceMetricsPanelProps> = ({
  stats,
  loading = false,
  className
}) => {
  const theme = useTheme();
  const [tabValue, setTabValue] = useState(0);
  const [timeframe, setTimeframe] = useState<'1h' | '6h' | '24h' | '7d'>('24h');
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 1000);
  };

  // Performance metrics data
  const performanceData: PerformanceData[] = useMemo(() => [
    {
      metric: 'Accuracy',
      value: stats?.average_accuracy || 0,
      benchmark: 85,
      improvement: stats?.trend_analysis?.accuracy === 'improving' ? 5.2 : 
                   stats?.trend_analysis?.accuracy === 'declining' ? -2.1 : 0,
      color: theme.palette.primary.main,
    },
    {
      metric: 'Precision',
      value: stats?.confidence_intervals?.precision?.[1] || 0,
      benchmark: 80,
      improvement: 3.1,
      color: theme.palette.success.main,
    },
    {
      metric: 'Recall',
      value: stats?.confidence_intervals?.recall?.[1] || 0,
      benchmark: 82,
      improvement: 1.8,
      color: theme.palette.info.main,
    },
    {
      metric: 'F1-Score',
      value: stats?.confidence_intervals?.f1_score?.[1] || 0,
      benchmark: 78,
      improvement: 2.4,
      color: theme.palette.warning.main,
    },
    {
      metric: 'Signal Processing',
      value: stats?.signal_processing_metrics?.successRate || 0,
      benchmark: 95,
      improvement: stats?.trend_analysis?.performance === 'improving' ? 4.3 : 0,
      color: theme.palette.secondary.main,
    },
  ], [stats, theme]);

  // Latency analysis data
  const latencyData: LatencyData[] = useMemo(() => [
    {
      timeRange: '00:00',
      avgLatency: 45,
      p95Latency: 78,
      p99Latency: 125,
    },
    {
      timeRange: '04:00',
      avgLatency: 42,
      p95Latency: 71,
      p99Latency: 118,
    },
    {
      timeRange: '08:00',
      avgLatency: 38,
      p95Latency: 65,
      p99Latency: 102,
    },
    {
      timeRange: '12:00',
      avgLatency: stats?.signal_processing_metrics?.avgProcessingTime || 48,
      p95Latency: 82,
      p99Latency: 134,
    },
    {
      timeRange: '16:00',
      avgLatency: 44,
      p95Latency: 76,
      p99Latency: 121,
    },
    {
      timeRange: '20:00',
      avgLatency: 41,
      p95Latency: 69,
      p99Latency: 115,
    },
  ], [stats]);

  // Detection type breakdown for pie chart
  const detectionBreakdown = useMemo(() => [
    { name: 'Pedestrian', value: 45, color: '#8884d8' },
    { name: 'Cyclist', value: 28, color: '#82ca9d' },
    { name: 'Motorcyclist', value: 15, color: '#ffc658' },
    { name: 'Wheelchair', value: 8, color: '#ff7300' },
    { name: 'Scooter', value: 4, color: '#ff0000' },
  ], []);

  // Radar chart data for performance comparison
  const radarData = useMemo(() => [
    {
      metric: 'Accuracy',
      current: stats?.average_accuracy || 0,
      target: 95,
      industry: 88,
    },
    {
      metric: 'Speed',
      current: Math.max(100 - (stats?.signal_processing_metrics?.avgProcessingTime || 50), 0),
      target: 95,
      industry: 85,
    },
    {
      metric: 'Reliability',
      current: stats?.signal_processing_metrics?.successRate || 0,
      target: 99,
      industry: 92,
    },
    {
      metric: 'Throughput',
      current: Math.min((stats?.total_detections || 0) / 10, 100),
      target: 90,
      industry: 75,
    },
    {
      metric: 'Quality',
      current: (stats?.confidence_intervals?.precision?.[1] || 0),
      target: 92,
      industry: 80,
    },
  ], [stats]);

  const TabPanel = ({ children, value, index, ...other }: any) => (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: 2 }}>{children}</Box>}
    </div>
  );

  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text 
        x={x} 
        y={y} 
        fill="white" 
        textAnchor={x > cx ? 'start' : 'end'} 
        dominantBaseline="central"
        fontSize={12}
        fontWeight="bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  if (loading) {
    return (
      <Card className={className} sx={{ height: 500 }}>
        <CardHeader title="Performance Analytics" />
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
            <Analytics sx={{ fontSize: 40, color: 'text.secondary' }} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card 
      className={className} 
      sx={{ 
        height: 550,
        background: theme.palette.mode === 'dark' 
          ? 'linear-gradient(135deg, rgba(33, 150, 243, 0.1) 0%, rgba(103, 58, 183, 0.1) 100%)'
          : 'linear-gradient(135deg, rgba(33, 150, 243, 0.05) 0%, rgba(103, 58, 183, 0.05) 100%)'
      }}
    >
      <CardHeader
        title={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Analytics color="primary" />
            <Typography variant="h6">Performance Analytics</Typography>
            <Chip
              icon={<TrendingUp />}
              label="Real-time"
              color="info"
              size="small"
              variant="outlined"
            />
          </Box>
        }
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 80 }}>
              <InputLabel>Period</InputLabel>
              <Select
                value={timeframe}
                label="Period"
                onChange={(e) => setTimeframe(e.target.value as any)}
              >
                <MenuItem value="1h">1h</MenuItem>
                <MenuItem value="6h">6h</MenuItem>
                <MenuItem value="24h">24h</MenuItem>
                <MenuItem value="7d">7d</MenuItem>
              </Select>
            </FormControl>
            <Tooltip title="Refresh data">
              <IconButton
                onClick={handleRefresh}
                disabled={refreshing}
                color="primary"
              >
                <Refresh className={refreshing ? 'rotating' : ''} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Export data">
              <IconButton color="primary">
                <Download />
              </IconButton>
            </Tooltip>
          </Box>
        }
      />
      
      <CardContent sx={{ pt: 0, height: 480 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs 
            value={tabValue} 
            onChange={(_, newValue) => setTabValue(newValue)}
            variant="fullWidth"
          >
            <Tab icon={<Assessment />} label="Metrics" />
            <Tab icon={<Speed />} label="Latency" />
            <Tab icon={<FilterAlt />} label="Breakdown" />
          </Tabs>
        </Box>

        <TabPanel value={tabValue} index={0}>
          <Grid container spacing={2} sx={{ height: 380 }}>
            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 1, height: '100%' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Performance vs Benchmark
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={performanceData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis dataKey="metric" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                    <RechartsTooltip
                      formatter={(value: number, name: string) => [
                        `${value.toFixed(1)}%`,
                        name === 'value' ? 'Current' : 'Benchmark'
                      ]}
                      contentStyle={{
                        backgroundColor: theme.palette.background.paper,
                        border: `1px solid ${theme.palette.divider}`,
                        borderRadius: theme.shape.borderRadius,
                      }}
                    />
                    <Legend />
                    <Bar dataKey="value" fill={theme.palette.primary.main} name="Current" />
                    <Bar dataKey="benchmark" fill={theme.palette.grey[400]} name="Benchmark" />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Performance Radar
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10 }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 8 }} />
                    <Radar
                      name="Current"
                      dataKey="current"
                      stroke={theme.palette.primary.main}
                      fill={theme.palette.primary.main}
                      fillOpacity={0.3}
                      strokeWidth={2}
                    />
                    <Radar
                      name="Target"
                      dataKey="target"
                      stroke={theme.palette.success.main}
                      fill="transparent"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                    />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
          </Grid>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <Paper sx={{ p: 2, height: 380 }}>
            <Typography variant="subtitle2" gutterBottom>
              Latency Analysis (ms)
            </Typography>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={latencyData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="timeRange" />
                <YAxis />
                <RechartsTooltip
                  formatter={(value: number, name: string) => [`${value}ms`, name]}
                  contentStyle={{
                    backgroundColor: theme.palette.background.paper,
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: theme.shape.borderRadius,
                  }}
                />
                <Legend />
                <Bar dataKey="avgLatency" fill={theme.palette.info.main} name="Average" />
                <Bar dataKey="p95Latency" fill={theme.palette.warning.main} name="95th Percentile" />
                <Bar dataKey="p99Latency" fill={theme.palette.error.main} name="99th Percentile" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <Grid container spacing={2} sx={{ height: 380 }}>
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Detection Type Distribution
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={detectionBreakdown}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={renderCustomizedLabel}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {detectionBreakdown.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, height: '100%' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Performance Improvements
                </Typography>
                <Box sx={{ mt: 2 }}>
                  {performanceData.map((metric) => (
                    <Box key={metric.metric} sx={{ mb: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2">{metric.metric}</Typography>
                        <Chip
                          label={`${metric.improvement > 0 ? '+' : ''}${metric.improvement.toFixed(1)}%`}
                          color={metric.improvement > 0 ? 'success' : metric.improvement < 0 ? 'error' : 'default'}
                          size="small"
                        />
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ 
                          width: '100%', 
                          height: 8, 
                          borderRadius: 4, 
                          bgcolor: 'action.hover',
                          position: 'relative'
                        }}>
                          <Box sx={{
                            width: `${metric.value}%`,
                            height: '100%',
                            borderRadius: 4,
                            bgcolor: metric.color,
                          }} />
                        </Box>
                        <Typography variant="caption" color="text.secondary">
                          {metric.value.toFixed(1)}%
                        </Typography>
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Paper>
            </Grid>
          </Grid>
        </TabPanel>
      </CardContent>
    </Card>
  );
};

export default PerformanceMetricsPanel;