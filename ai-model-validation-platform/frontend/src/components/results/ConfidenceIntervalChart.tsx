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
  FormControlLabel
} from '@mui/material';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ErrorBar,
  LineChart,
  Line,
  ReferenceLine
} from 'recharts';
import { ConfidenceIntervals } from '../../types/enhanced-results';

interface ConfidenceIntervalChartProps {
  intervals: ConfidenceIntervals;
  chartType?: 'bar' | 'line';
  showErrorBars?: boolean;
  showReferenceLine?: boolean;
  referenceValue?: number;
}

export const ConfidenceIntervalChart: React.FC<ConfidenceIntervalChartProps> = ({
  intervals,
  chartType = 'bar',
  showErrorBars = true,
  showReferenceLine = true,
  referenceValue = 0.8 // 80% reference line for performance metrics
}) => {
  const [selectedChart, setSelectedChart] = React.useState(chartType);
  const [showBars, setShowBars] = React.useState(showErrorBars);
  const [showRef, setShowRef] = React.useState(showReferenceLine);

  const chartData = useMemo(() => {
    const data = [];
    const metrics = ['accuracy', 'precision', 'recall', 'f1Score', 'iou'] as const;
    
    metrics.forEach(metric => {
      const interval = intervals[metric];
      if (interval) {
        data.push({
          metric: metric.charAt(0).toUpperCase() + metric.slice(1),
          estimate: interval.estimate * 100, // Convert to percentage
          lowerBound: interval.lowerBound * 100,
          upperBound: interval.upperBound * 100,
          marginOfError: interval.marginOfError * 100,
          confidenceLevel: interval.confidenceLevel * 100,
          method: interval.method
        });
      }
    });

    // Add latency separately (different unit)
    if (intervals.latency) {
      data.push({
        metric: 'Latency',
        estimate: intervals.latency.estimate,
        lowerBound: intervals.latency.lowerBound,
        upperBound: intervals.latency.upperBound,
        marginOfError: intervals.latency.marginOfError,
        confidenceLevel: intervals.latency.confidenceLevel * 100,
        method: intervals.latency.method,
        isLatency: true
      });
    }

    return data;
  }, [intervals]);

  const performanceData = chartData.filter(d => !d.isLatency);
  const latencyData = chartData.filter(d => d.isLatency);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Box
          sx={{
            bgcolor: 'background.paper',
            p: 2,
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            boxShadow: 1
          }}
        >
          <Typography variant="subtitle2" gutterBottom>
            {label}
          </Typography>
          <Typography variant="body2">
            Estimate: {data.isLatency ? `${data.estimate.toFixed(2)}ms` : `${data.estimate.toFixed(2)}%`}
          </Typography>
          <Typography variant="body2">
            CI: [{data.isLatency ? `${data.lowerBound.toFixed(2)}ms` : `${data.lowerBound.toFixed(2)}%`}, {data.isLatency ? `${data.upperBound.toFixed(2)}ms` : `${data.upperBound.toFixed(2)}%`}]
          </Typography>
          <Typography variant="body2">
            Margin of Error: ±{data.isLatency ? `${data.marginOfError.toFixed(2)}ms` : `${data.marginOfError.toFixed(2)}%`}
          </Typography>
          <Typography variant="caption">
            Method: {data.method} | {data.confidenceLevel.toFixed(0)}% CI
          </Typography>
        </Box>
      );
    }
    return null;
  };

  const getBarColor = (value: number, isLatency = false) => {
    if (isLatency) {
      if (value <= 50) return '#4caf50'; // Green - excellent
      if (value <= 100) return '#2196f3'; // Blue - good
      if (value <= 200) return '#ff9800'; // Orange - acceptable
      return '#f44336'; // Red - poor
    } else {
      if (value >= 90) return '#4caf50'; // Green - excellent
      if (value >= 80) return '#2196f3'; // Blue - good
      if (value >= 70) return '#ff9800'; // Orange - acceptable
      return '#f44336'; // Red - poor
    }
  };

  const renderBarChart = (data: any[], isLatency = false) => (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis 
          dataKey="metric" 
          tick={{ fontSize: 12 }}
          angle={-45}
          textAnchor="end"
          height={80}
        />
        <YAxis 
          tick={{ fontSize: 12 }}
          label={{ 
            value: isLatency ? 'Latency (ms)' : 'Performance (%)', 
            angle: -90, 
            position: 'insideLeft' 
          }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        
        {showRef && !isLatency && (
          <ReferenceLine 
            y={referenceValue * 100} 
            stroke="#ff4444" 
            strokeDasharray="5 5"
            label={{ value: `Target: ${referenceValue * 100}%`, position: 'insideTopRight' }}
          />
        )}
        
        <Bar 
          dataKey="estimate" 
          name="Estimate"
          fill="#2196f3"
        >
          {showBars && (
            <ErrorBar 
              dataKey="marginOfError" 
              width={4} 
              stroke="#333"
              strokeWidth={2}
            />
          )}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );

  const renderLineChart = (data: any[], isLatency = false) => (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis 
          dataKey="metric" 
          tick={{ fontSize: 12 }}
          angle={-45}
          textAnchor="end"
          height={80}
        />
        <YAxis 
          tick={{ fontSize: 12 }}
          label={{ 
            value: isLatency ? 'Latency (ms)' : 'Performance (%)', 
            angle: -90, 
            position: 'insideLeft' 
          }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        
        {showRef && !isLatency && (
          <ReferenceLine 
            y={referenceValue * 100} 
            stroke="#ff4444" 
            strokeDasharray="5 5"
            label={{ value: `Target: ${referenceValue * 100}%`, position: 'insideTopRight' }}
          />
        )}
        
        <Line 
          type="monotone" 
          dataKey="estimate" 
          stroke="#2196f3"
          strokeWidth={3}
          dot={{ fill: '#2196f3', strokeWidth: 2, r: 6 }}
          name="Estimate"
        />
        <Line 
          type="monotone" 
          dataKey="upperBound" 
          stroke="#4caf50"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={false}
          name="Upper Bound"
        />
        <Line 
          type="monotone" 
          dataKey="lowerBound" 
          stroke="#ff9800"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={false}
          name="Lower Bound"
        />
      </LineChart>
    </ResponsiveContainer>
  );

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Confidence Interval Visualization
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>Chart Type</InputLabel>
              <Select
                value={selectedChart}
                label="Chart Type"
                onChange={(e) => setSelectedChart(e.target.value as 'bar' | 'line')}
              >
                <MenuItem value="bar">Bar Chart</MenuItem>
                <MenuItem value="line">Line Chart</MenuItem>
              </Select>
            </FormControl>
            <FormControlLabel
              control={
                <Switch
                  checked={showBars}
                  onChange={(e) => setShowBars(e.target.checked)}
                  size="small"
                />
              }
              label="Error Bars"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={showRef}
                  onChange={(e) => setShowRef(e.target.checked)}
                  size="small"
                />
              }
              label="Reference Line"
            />
          </Box>
        </Box>

        {/* Performance Metrics Chart */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Performance Metrics
          </Typography>
          {selectedChart === 'bar' 
            ? renderBarChart(performanceData, false)
            : renderLineChart(performanceData, false)
          }
        </Box>

        {/* Latency Chart */}
        {latencyData.length > 0 && (
          <Box>
            <Typography variant="subtitle1" gutterBottom>
              Latency Metrics
            </Typography>
            {selectedChart === 'bar' 
              ? renderBarChart(latencyData, true)
              : renderLineChart(latencyData, true)
            }
          </Box>
        )}

        {/* Summary Statistics */}
        <Box sx={{ mt: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Summary Statistics
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Typography variant="body2">
              <strong>Avg Confidence Level:</strong> {' '}
              {performanceData.length > 0 
                ? (performanceData.reduce((sum, d) => sum + d.confidenceLevel, 0) / performanceData.length).toFixed(0)
                : 0
              }%
            </Typography>
            <Typography variant="body2">
              <strong>Narrowest Interval:</strong> {' '}
              {performanceData.length > 0
                ? performanceData.reduce((min, d) => Math.min(min, d.marginOfError), Infinity).toFixed(2)
                : 0
              }%
            </Typography>
            <Typography variant="body2">
              <strong>Widest Interval:</strong> {' '}
              {performanceData.length > 0
                ? performanceData.reduce((max, d) => Math.max(max, d.marginOfError), 0).toFixed(2)
                : 0
              }%
            </Typography>
            <Typography variant="body2">
              <strong>Methods Used:</strong> {' '}
              {[...new Set(chartData.map(d => d.method))].join(', ')}
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};