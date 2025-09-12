import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Chip
} from '@mui/material';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ScatterChart,
  Scatter,
  ReferenceLine,
  Area,
  ComposedChart,
  Bar
} from 'recharts';
import {
  TemporalAnalysis,
  FrameComparisonResult
} from '../../types/enhanced-results';

interface TemporalAnalysisChartProps {
  temporalAnalysis: TemporalAnalysis;
  comparisonResults: FrameComparisonResult[];
  currentFrame?: number;
  onFrameSelect?: (frameNumber: number) => void;
}

export const TemporalAnalysisChart: React.FC<TemporalAnalysisChartProps> = ({
  temporalAnalysis,
  comparisonResults,
  currentFrame,
  onFrameSelect
}) => {
  const [chartType, setChartType] = useState<'performance' | 'gaps' | 'patterns'>('performance');
  const [showTrends, setShowTrends] = useState(true);
  const [showAnnotations, setShowAnnotations] = useState(true);

  // Prepare performance over time data
  const performanceData = (comparisonResults || []).map(result => {
    const frameMetrics = result?.frameMetrics || { accuracy: 0, precision: 0, recall: 0, f1Score: 0, truePositives: 0, falsePositives: 0, falseNegatives: 0, averageIou: 0 };
    const gtLength = result?.groundTruthDetections?.length || 0;
    const testLength = result?.testDetections?.length || 0;
    
    return {
      frameNumber: result?.frameNumber || 0,
      timestamp: result?.timestamp || 0,
      accuracy: (frameMetrics.accuracy || 0) * 100,
      precision: (frameMetrics.precision || 0) * 100,
      recall: (frameMetrics.recall || 0) * 100,
      f1Score: (frameMetrics.f1Score || 0) * 100,
      detectionCount: gtLength + testLength,
      truePositives: frameMetrics.truePositives || 0,
      falsePositives: frameMetrics.falsePositives || 0,
      falseNegatives: frameMetrics.falseNegatives || 0,
      averageIou: (frameMetrics.averageIou || 0) * 100
    };
  });

  // Prepare detection gaps data
  const gapsData = (temporalAnalysis?.detectionGaps || []).map(gap => ({
    startFrame: gap?.startFrame || 0,
    endFrame: gap?.endFrame || 0,
    duration: gap?.duration || 0,
    affectedObjects: gap?.affectedObjects?.length || 0,
    severity: (gap?.duration || 0) > 30 ? 'high' : (gap?.duration || 0) > 10 ? 'medium' : 'low'
  }));

  // Prepare patterns data
  const patternsData = (temporalAnalysis?.temporalPatterns || []).map((pattern, index) => ({
    id: index,
    pattern: pattern?.pattern || 'Unknown',
    frequency: pattern?.frequency || 0,
    confidence: (pattern?.confidence || 0) * 100
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
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
            Frame {label}
          </Typography>
          {payload.map((entry: any, index: number) => (
            <Typography key={index} variant="body2" style={{ color: entry.color }}>
              {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
              {entry.name.includes('accuracy') || entry.name.includes('precision') || entry.name.includes('recall') || entry.name.includes('f1Score') || entry.name.includes('Iou') ? '%' : ''}
            </Typography>
          ))}
        </Box>
      );
    }
    return null;
  };

  const renderPerformanceChart = () => (
    <ResponsiveContainer width="100%" height={400}>
      <ComposedChart data={performanceData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis 
          dataKey="frameNumber" 
          tick={{ fontSize: 12 }}
          label={{ value: 'Frame Number', position: 'insideBottom', offset: -10 }}
        />
        <YAxis 
          yAxisId="performance"
          tick={{ fontSize: 12 }}
          label={{ value: 'Performance (%)', angle: -90, position: 'insideLeft' }}
          domain={[0, 100]}
        />
        <YAxis 
          yAxisId="count"
          orientation="right"
          tick={{ fontSize: 12 }}
          label={{ value: 'Detection Count', angle: 90, position: 'insideRight' }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />

        {/* Reference lines */}
        <ReferenceLine yAxisId="performance" y={80} stroke="#4caf50" strokeDasharray="5 5" />
        <ReferenceLine yAxisId="performance" y={60} stroke="#ff9800" strokeDasharray="5 5" />

        {/* Current frame indicator */}
        {currentFrame !== undefined && (
          <ReferenceLine x={currentFrame} stroke="#2196f3" strokeWidth={3} />
        )}

        {/* Performance metrics */}
        <Line 
          yAxisId="performance"
          type="monotone" 
          dataKey="accuracy" 
          stroke="#2196f3" 
          strokeWidth={2}
          dot={{ r: 3 }}
          name="Accuracy"
        />
        <Line 
          yAxisId="performance"
          type="monotone" 
          dataKey="precision" 
          stroke="#4caf50" 
          strokeWidth={2}
          dot={{ r: 3 }}
          name="Precision"
        />
        <Line 
          yAxisId="performance"
          type="monotone" 
          dataKey="recall" 
          stroke="#ff9800" 
          strokeWidth={2}
          dot={{ r: 3 }}
          name="Recall"
        />
        <Line 
          yAxisId="performance"
          type="monotone" 
          dataKey="f1Score" 
          stroke="#9c27b0" 
          strokeWidth={2}
          dot={{ r: 3 }}
          name="F1 Score"
        />

        {/* Detection count as bars */}
        <Bar 
          yAxisId="count"
          dataKey="detectionCount" 
          fill="rgba(255, 193, 7, 0.3)" 
          name="Detection Count"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );

  const renderGapsChart = () => (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Detection Gaps Timeline
      </Typography>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart data={gapsData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            type="number"
            dataKey="startFrame" 
            tick={{ fontSize: 12 }}
            label={{ value: 'Start Frame', position: 'insideBottom', offset: -10 }}
          />
          <YAxis 
            type="number"
            dataKey="duration" 
            tick={{ fontSize: 12 }}
            label={{ value: 'Gap Duration (frames)', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip 
            content={({ active, payload }: any) => {
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
                      Detection Gap
                    </Typography>
                    <Typography variant="body2">
                      Frames: {data.startFrame} - {data.endFrame}
                    </Typography>
                    <Typography variant="body2">
                      Duration: {data.duration} frames
                    </Typography>
                    <Typography variant="body2">
                      Affected Objects: {data.affectedObjects}
                    </Typography>
                    <Chip 
                      size="small" 
                      label={data.severity} 
                      color={data.severity === 'high' ? 'error' : data.severity === 'medium' ? 'warning' : 'info'}
                    />
                  </Box>
                );
              }
              return null;
            }}
          />
          <Scatter 
            name="Detection Gaps" 
            fill="#ff9800"
          />
        </ScatterChart>
      </ResponsiveContainer>

      {/* Gap statistics */}
      <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Typography variant="subtitle2" gutterBottom>
          Gap Analysis Summary
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Total Gaps</Typography>
            <Typography variant="h6">{gapsData.length}</Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Avg Duration</Typography>
            <Typography variant="h6">
              {gapsData.length > 0 ? (gapsData.reduce((sum, gap) => sum + gap.duration, 0) / gapsData.length).toFixed(1) : 0}
            </Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Max Duration</Typography>
            <Typography variant="h6">
              {gapsData.length > 0 ? Math.max(...gapsData.map(gap => gap.duration)) : 0}
            </Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Tracking Consistency</Typography>
            <Typography variant="h6" color={(temporalAnalysis.trackingConsistency || 0) > 0.8 ? 'success.main' : (temporalAnalysis.trackingConsistency || 0) > 0.6 ? 'warning.main' : 'error.main'}>
              {((temporalAnalysis.trackingConsistency || 0) * 100).toFixed(1)}%
            </Typography>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );

  const renderPatternsChart = () => (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Temporal Patterns Analysis
      </Typography>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart data={patternsData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            type="number"
            dataKey="frequency" 
            tick={{ fontSize: 12 }}
            label={{ value: 'Frequency', position: 'insideBottom', offset: -10 }}
          />
          <YAxis 
            type="number"
            dataKey="confidence" 
            tick={{ fontSize: 12 }}
            label={{ value: 'Confidence (%)', angle: -90, position: 'insideLeft' }}
            domain={[0, 100]}
          />
          <Tooltip 
            content={({ active, payload }: any) => {
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
                      Temporal Pattern
                    </Typography>
                    <Typography variant="body2">
                      Pattern: {data.pattern}
                    </Typography>
                    <Typography variant="body2">
                      Frequency: {data.frequency}
                    </Typography>
                    <Typography variant="body2">
                      Confidence: {data.confidence.toFixed(1)}%
                    </Typography>
                  </Box>
                );
              }
              return null;
            }}
          />
          <Scatter 
            name="Temporal Patterns" 
            fill="#9c27b0"
          />
        </ScatterChart>
      </ResponsiveContainer>

      {/* Pattern details */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Detected Patterns
        </Typography>
        <Grid container spacing={1}>
          {patternsData.map((pattern, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
              <Card variant="outlined" sx={{ p: 1 }}>
                <Typography variant="body2" fontWeight="bold">
                  {pattern.pattern}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Frequency: {pattern.frequency} | Confidence: {pattern.confidence.toFixed(1)}%
                </Typography>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* Temporal stability */}
      <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Typography variant="subtitle2" gutterBottom>
          Temporal Stability Metrics
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">Temporal Stability</Typography>
            <Typography variant="h6" color={(temporalAnalysis.temporalStability || 0) > 0.8 ? 'success.main' : (temporalAnalysis.temporalStability || 0) > 0.6 ? 'warning.main' : 'error.main'}>
              {((temporalAnalysis.temporalStability || 0) * 100).toFixed(1)}%
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">Unique Patterns</Typography>
            <Typography variant="h6">
              {patternsData.length}
            </Typography>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Temporal Analysis
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Chart Type</InputLabel>
              <Select
                value={chartType}
                label="Chart Type"
                onChange={(e) => setChartType(e.target.value as any)}
              >
                <MenuItem value="performance">Performance Timeline</MenuItem>
                <MenuItem value="gaps">Detection Gaps</MenuItem>
                <MenuItem value="patterns">Temporal Patterns</MenuItem>
              </Select>
            </FormControl>
            <FormControlLabel
              control={
                <Switch
                  checked={showTrends}
                  onChange={(e) => setShowTrends(e.target.checked)}
                  size="small"
                />
              }
              label="Trends"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={showAnnotations}
                  onChange={(e) => setShowAnnotations(e.target.checked)}
                  size="small"
                />
              }
              label="Annotations"
            />
          </Box>
        </Box>

        {chartType === 'performance' && renderPerformanceChart()}
        {chartType === 'gaps' && renderGapsChart()}
        {chartType === 'patterns' && renderPatternsChart()}

        {/* Click handler for frame selection */}
        {chartType === 'performance' && onFrameSelect && (
          <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>
            Click on any point in the performance chart to jump to that frame
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};