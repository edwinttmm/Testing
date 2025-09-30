import React, { useState, useMemo } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  Typography,
  Box,
  Grid,
  Paper,
  useTheme,
  Chip,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Divider,
  CircularProgress,
  LinearProgress,
} from '@mui/material';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  RadialBarChart,
  RadialBar,
  DonutChart,
} from 'recharts';
import {
  DonutLarge,
  BarChart as BarChartIcon,
  Visibility,
  Assessment,
  TrendingUp,
  PieChart as PieChartIcon,
} from '@mui/icons-material';
import { EnhancedDashboardStats } from '../../services/types';

interface DetectionData {
  name: string;
  value: number;
  color: string;
  confidence: number;
  count: number;
}

interface ConfidenceDistribution {
  range: string;
  count: number;
  percentage: number;
  color: string;
}

interface DetectionAnalyticsChartProps {
  stats: EnhancedDashboardStats | null;
  loading?: boolean;
  className?: string;
}

const DetectionAnalyticsChart: React.FC<DetectionAnalyticsChartProps> = ({
  stats,
  loading = false,
  className
}) => {
  const theme = useTheme();
  const [chartType, setChartType] = useState<'pie' | 'donut' | 'bar' | 'radial'>('donut');
  const [viewMode, setViewMode] = useState<'types' | 'confidence' | 'accuracy'>('types');

  // Detection type data
  const detectionTypeData: DetectionData[] = useMemo(() => {
    const baseCount = stats?.total_detections || 100;
    return [
      {
        name: 'Pedestrian',
        value: Math.floor(baseCount * 0.45),
        color: '#8884d8',
        confidence: 92.5,
        count: Math.floor(baseCount * 0.45),
      },
      {
        name: 'Cyclist',
        value: Math.floor(baseCount * 0.28),
        color: '#82ca9d',
        confidence: 88.2,
        count: Math.floor(baseCount * 0.28),
      },
      {
        name: 'Motorcyclist',
        value: Math.floor(baseCount * 0.15),
        color: '#ffc658',
        confidence: 85.7,
        count: Math.floor(baseCount * 0.15),
      },
      {
        name: 'Wheelchair User',
        value: Math.floor(baseCount * 0.08),
        color: '#ff7300',
        confidence: 89.1,
        count: Math.floor(baseCount * 0.08),
      },
      {
        name: 'Scooter Rider',
        value: Math.floor(baseCount * 0.04),
        color: '#ff0000',
        confidence: 86.3,
        count: Math.floor(baseCount * 0.04),
      },
    ];
  }, [stats]);

  // Confidence distribution data
  const confidenceData: ConfidenceDistribution[] = useMemo(() => [
    { range: '90-100%', count: 156, percentage: 62, color: theme.palette.success.main },
    { range: '80-89%', count: 78, percentage: 31, color: theme.palette.info.main },
    { range: '70-79%', count: 12, percentage: 5, color: theme.palette.warning.main },
    { range: '60-69%', count: 5, percentage: 2, color: theme.palette.error.main },
  ], [theme]);

  // Accuracy metrics data
  const accuracyData = useMemo(() => [
    {
      metric: 'True Positives',
      value: stats?.average_accuracy ? Math.floor(stats.average_accuracy * 0.8) : 72,
      color: theme.palette.success.main,
    },
    {
      metric: 'False Positives',
      value: 15,
      color: theme.palette.warning.main,
    },
    {
      metric: 'False Negatives',
      value: 8,
      color: theme.palette.error.main,
    },
    {
      metric: 'True Negatives',
      value: 95,
      color: theme.palette.info.main,
    },
  ], [stats, theme]);

  const getCurrentData = () => {
    switch (viewMode) {
      case 'confidence':
        return confidenceData;
      case 'accuracy':
        return accuracyData;
      default:
        return detectionTypeData;
    }
  };

  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }: any) => {
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

  const renderChart = () => {
    const data = getCurrentData();

    switch (chartType) {
      case 'pie':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={renderCustomizedLabel}
                outerRadius={120}
                fill="#8884d8"
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <RechartsTooltip
                formatter={(value: number, name: string) => [value, name]}
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );

      case 'donut':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={renderCustomizedLabel}
                outerRadius={120}
                innerRadius={60}
                fill="#8884d8"
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <RechartsTooltip
                formatter={(value: number, name: string) => [value, name]}
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );

      case 'bar':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis 
                dataKey="name" 
                tick={{ fontSize: 12 }}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <RechartsTooltip
                formatter={(value: number, name: string) => [value, name]}
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              />
              <Bar dataKey="value" fill={theme.palette.primary.main}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        );

      case 'radial':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <RadialBarChart cx="50%" cy="50%" innerRadius="20%" outerRadius="90%" data={data}>
              <RadialBar
                minAngle={15}
                label={{ position: 'insideStart', fill: '#fff' }}
                background
                clockWise
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </RadialBar>
              <Legend iconSize={12} layout="vertical" verticalAlign="middle" align="right" />
              <RechartsTooltip
                formatter={(value: number, name: string) => [value, name]}
                contentStyle={{
                  backgroundColor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              />
            </RadialBarChart>
          </ResponsiveContainer>
        );

      default:
        return null;
    }
  };

  if (loading) {
    return (
      <Card className={className} sx={{ height: 500 }}>
        <CardHeader title="Detection Analytics" />
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
            <CircularProgress />
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
          ? 'linear-gradient(135deg, rgba(255, 152, 0, 0.1) 0%, rgba(255, 193, 7, 0.1) 100%)'
          : 'linear-gradient(135deg, rgba(255, 152, 0, 0.05) 0%, rgba(255, 193, 7, 0.05) 100%)'
      }}
    >
      <CardHeader
        title={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <DonutLarge color="primary" />
            <Typography variant="h6">Detection Analytics</Typography>
            <Chip
              icon={<Assessment />}
              label={`${stats?.total_detections || 0} Total`}
              color="warning"
              size="small"
              variant="outlined"
            />
          </Box>
        }
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(_, newMode) => newMode && setViewMode(newMode)}
              size="small"
            >
              <ToggleButton value="types">
                <Tooltip title="Detection Types">
                  <Visibility />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="confidence">
                <Tooltip title="Confidence Distribution">
                  <TrendingUp />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="accuracy">
                <Tooltip title="Accuracy Metrics">
                  <Assessment />
                </Tooltip>
              </ToggleButton>
            </ToggleButtonGroup>
            
            <ToggleButtonGroup
              value={chartType}
              exclusive
              onChange={(_, newType) => newType && setChartType(newType)}
              size="small"
            >
              <ToggleButton value="donut">
                <Tooltip title="Donut Chart">
                  <DonutLarge />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="pie">
                <Tooltip title="Pie Chart">
                  <PieChartIcon />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="bar">
                <Tooltip title="Bar Chart">
                  <BarChartIcon />
                </Tooltip>
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>
        }
      />
      
      <CardContent sx={{ pt: 0, height: 480 }}>
        <Grid container spacing={2} sx={{ height: '100%' }}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 2, height: '100%' }}>
              <Typography variant="subtitle2" gutterBottom>
                {viewMode === 'types' ? 'Detection Types Distribution' :
                 viewMode === 'confidence' ? 'Confidence Level Distribution' :
                 'Accuracy Metrics Breakdown'}
              </Typography>
              {renderChart()}
            </Paper>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 2, height: '100%', overflow: 'auto' }}>
              <Typography variant="subtitle2" gutterBottom>
                Detailed Statistics
              </Typography>
              
              <Box sx={{ mt: 2 }}>
                {getCurrentData().map((item, index) => (
                  <Box key={index} sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                      <Typography variant="body2" fontWeight="medium">
                        {item.name}
                      </Typography>
                      <Chip
                        label={item.value}
                        size="small"
                        sx={{ bgcolor: item.color, color: 'white' }}
                      />
                    </Box>
                    
                    <LinearProgress
                      variant="determinate"
                      value={viewMode === 'confidence' ? (item as any).percentage : 
                             (item.value / Math.max(...getCurrentData().map(d => d.value))) * 100}
                      sx={{
                        height: 8,
                        borderRadius: 4,
                        backgroundColor: theme.palette.action.hover,
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: item.color,
                          borderRadius: 4,
                        },
                      }}
                    />
                    
                    {viewMode === 'types' && 'confidence' in item && (
                      <Typography variant="caption" color="text.secondary">
                        Avg. Confidence: {(item as any).confidence}%
                      </Typography>
                    )}
                    
                    {viewMode === 'confidence' && 'percentage' in item && (
                      <Typography variant="caption" color="text.secondary">
                        {(item as any).percentage}% of total detections
                      </Typography>
                    )}
                  </Box>
                ))}
              </Box>

              <Divider sx={{ my: 2 }} />

              {/* Summary Statistics */}
              <Typography variant="subtitle2" gutterBottom>
                Summary
              </Typography>
              
              <Box sx={{ mt: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="caption">Total Detections:</Typography>
                  <Typography variant="caption" fontWeight="bold">
                    {stats?.total_detections || 0}
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="caption">Average Accuracy:</Typography>
                  <Typography variant="caption" fontWeight="bold">
                    {stats?.average_accuracy?.toFixed(1) || 0}%
                  </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="caption">Processing Rate:</Typography>
                  <Typography variant="caption" fontWeight="bold">
                    {stats?.signal_processing_metrics?.successRate?.toFixed(1) || 0}%
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="caption">Trend:</Typography>
                  <Chip
                    label={stats?.trend_analysis?.accuracy === 'improving' ? 'Improving' :
                           stats?.trend_analysis?.accuracy === 'declining' ? 'Declining' : 'Stable'}
                    color={stats?.trend_analysis?.accuracy === 'improving' ? 'success' :
                           stats?.trend_analysis?.accuracy === 'declining' ? 'error' : 'default'}
                    size="small"
                    variant="outlined"
                  />
                </Box>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default DetectionAnalyticsChart;