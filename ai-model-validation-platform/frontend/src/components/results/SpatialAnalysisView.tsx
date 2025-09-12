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
  Chip,
  Paper,
  LinearProgress
} from '@mui/material';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
  PieChart,
  Pie,
  BarChart,
  Bar
} from 'recharts';
import {
  SpatialAnalysis,
  FrameComparisonResult
} from '../../types/enhanced-results';

interface SpatialAnalysisViewProps {
  spatialAnalysis: SpatialAnalysis;
  comparisonResults: FrameComparisonResult[];
  videoUrl?: string;
}

export const SpatialAnalysisView: React.FC<SpatialAnalysisViewProps> = ({
  spatialAnalysis,
  comparisonResults,
  videoUrl
}) => {
  const [viewType, setViewType] = useState<'heatmap' | 'distribution' | 'quality' | 'occlusion'>('heatmap');

  // Prepare spatial distribution data
  const quadrantData = Object.entries(spatialAnalysis?.spatialDistribution?.quadrants || {}).map(([quadrant, count]) => ({
    name: `Quadrant ${quadrant}`,
    value: count || 0,
    fill: getQuadrantColor(quadrant)
  }));

  // Prepare hotspot data for scatter plot
  const hotspotData = (spatialAnalysis?.spatialDistribution?.hotspots || []).map((hotspot, index) => ({
    id: index,
    x: hotspot?.x || 0,
    y: hotspot?.y || 0,
    density: hotspot?.density || 0,
    radius: hotspot?.radius || 0,
    size: (hotspot?.radius || 0) * 5 // Scale for visualization
  }));

  // Prepare bounding box quality data
  const boundingBoxQuality = spatialAnalysis?.boundingBoxQuality || { averageIou: 0, tightnessFactor: 0, consistencyScore: 0 };
  const boundingBoxData = [
    { metric: 'Average IoU', value: (boundingBoxQuality.averageIou || 0) * 100, target: 70 },
    { metric: 'Tightness Factor', value: (boundingBoxQuality.tightnessFactor || 0) * 100, target: 85 },
    { metric: 'Consistency Score', value: (boundingBoxQuality.consistencyScore || 0) * 100, target: 80 }
  ];

  // Prepare occlusion analysis data
  const occlusionAnalysis = spatialAnalysis?.occlusionAnalysis || { totalOccluded: 0, partialOcclusion: 0, fullOcclusion: 0, occlusionImpact: 0 };
  const occlusionData = [
    { name: 'No Occlusion', value: (occlusionAnalysis.totalOccluded || 0) === 0 ? 100 : 0, fill: '#4caf50' },
    { name: 'Partial Occlusion', value: occlusionAnalysis.partialOcclusion || 0, fill: '#ff9800' },
    { name: 'Full Occlusion', value: occlusionAnalysis.fullOcclusion || 0, fill: '#f44336' }
  ];

  function getQuadrantColor(quadrant: string): string {
    const colors: Record<string, string> = {
      '1': '#2196f3', // Top-right - Blue
      '2': '#4caf50', // Top-left - Green
      '3': '#ff9800', // Bottom-left - Orange
      '4': '#f44336'  // Bottom-right - Red
    };
    return colors[quadrant] || '#9e9e9e';
  }

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
            {label || 'Spatial Point'}
          </Typography>
          {Object.entries(data).map(([key, value]: [string, any]) => (
            <Typography key={key} variant="body2">
              {key}: {typeof value === 'number' ? value.toFixed(2) : value}
            </Typography>
          ))}
        </Box>
      );
    }
    return null;
  };

  const renderSpatialHeatmap = () => (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Detection Hotspots
      </Typography>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart data={hotspotData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            type="number"
            dataKey="x" 
            tick={{ fontSize: 12 }}
            label={{ value: 'X Position (pixels)', position: 'insideBottom', offset: -10 }}
            domain={[0, 1920]} // Assuming 1080p video
          />
          <YAxis 
            type="number"
            dataKey="y" 
            tick={{ fontSize: 12 }}
            label={{ value: 'Y Position (pixels)', angle: -90, position: 'insideLeft' }}
            domain={[0, 1080]}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Scatter 
            name="Detection Hotspots" 
            dataKey="density"
            fill="#ff6b6b"
            fillOpacity={0.6}
          >
            {hotspotData.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={`rgba(255, 107, 107, ${Math.min(entry.density, 1)})`}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Typography variant="subtitle2" gutterBottom>
          Hotspot Analysis
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Total Hotspots</Typography>
            <Typography variant="h6">{hotspotData.length}</Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Max Density</Typography>
            <Typography variant="h6">
              {hotspotData.length > 0 ? Math.max(...hotspotData.map(h => h.density)).toFixed(2) : 0}
            </Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Avg Radius</Typography>
            <Typography variant="h6">
              {hotspotData.length > 0 ? (hotspotData.reduce((sum, h) => sum + h.radius, 0) / hotspotData.length).toFixed(1) : 0}px
            </Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="body2" color="text.secondary">Coverage</Typography>
            <Typography variant="h6">
              {((hotspotData.length * 100) / (1920 * 1080 / 10000)).toFixed(1)}%
            </Typography>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );

  const renderQuadrantDistribution = () => (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Quadrant Distribution
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={quadrantData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {quadrantData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Grid>
        <Grid item xs={12} md={6}>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={quadrantData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#8884d8">
                {quadrantData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Grid>
      </Grid>

      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Spatial Balance Analysis
        </Typography>
        <Grid container spacing={2}>
          {quadrantData.map((quadrant, index) => (
            <Grid item xs={6} md={3} key={index}>
              <Card variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h6" style={{ color: quadrant.fill }}>
                  {quadrant.value}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {quadrant.name}
                </Typography>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    </Box>
  );

  const renderBoundingBoxQuality = () => (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Bounding Box Quality Assessment
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={boundingBoxData} layout="horizontal">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} />
              <YAxis dataKey="metric" type="category" width={120} />
              <Tooltip 
                formatter={(value: number, name: string, props: any) => [
                  `${value.toFixed(1)}%`,
                  name,
                  `Target: ${props.payload.target}%`
                ]}
              />
              <Bar dataKey="value" fill="#2196f3" />
              <Bar 
                dataKey="target" 
                fill="transparent" 
                stroke="#4caf50" 
                strokeWidth={2}
                strokeDasharray="5 5"
              />
            </BarChart>
          </ResponsiveContainer>
        </Grid>
      </Grid>

      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Quality Metrics Detail
        </Typography>
        <Grid container spacing={2}>
          {boundingBoxData.map((metric, index) => (
            <Grid item xs={12} md={4} key={index}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {metric.metric}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="h6">
                    {metric.value.toFixed(1)}%
                  </Typography>
                  <Chip
                    size="small"
                    label={metric.value >= metric.target ? 'Good' : metric.value >= metric.target - 10 ? 'Fair' : 'Poor'}
                    color={metric.value >= metric.target ? 'success' : metric.value >= metric.target - 10 ? 'warning' : 'error'}
                  />
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(metric.value, 100)}
                  color={metric.value >= metric.target ? 'success' : metric.value >= metric.target - 10 ? 'warning' : 'error'}
                  sx={{ mt: 1 }}
                />
                <Typography variant="caption" color="text.secondary">
                  Target: {metric.target}%
                </Typography>
              </Paper>
            </Grid>
          ))}
        </Grid>
      </Box>

      <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Typography variant="subtitle2" gutterBottom>
          Quality Assessment Summary
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">Overall Quality Score</Typography>
            <Typography variant="h6" color={
              boundingBoxData.every(m => m.value >= m.target) ? 'success.main' :
              boundingBoxData.some(m => m.value >= m.target - 10) ? 'warning.main' : 'error.main'
            }>
              {(boundingBoxData.reduce((sum, m) => sum + m.value, 0) / boundingBoxData.length).toFixed(1)}%
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">Metrics Meeting Target</Typography>
            <Typography variant="h6">
              {boundingBoxData.filter(m => m.value >= m.target).length} / {boundingBoxData.length}
            </Typography>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );

  const renderOcclusionAnalysis = () => (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Occlusion Analysis
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={occlusionData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {occlusionData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Grid>
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 2 }}>
            <Typography variant="subtitle2">Occlusion Impact Analysis</Typography>
            
            <Box>
              <Typography variant="body2" color="text.secondary">
                Total Occluded Objects
              </Typography>
              <Typography variant="h6">
                {occlusionAnalysis.totalOccluded || 0}
              </Typography>
            </Box>

            <Box>
              <Typography variant="body2" color="text.secondary">
                Partial Occlusion Rate
              </Typography>
              <Typography variant="h6" color="warning.main">
                {occlusionAnalysis.partialOcclusion || 0}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={occlusionAnalysis.partialOcclusion || 0}
                color="warning"
                sx={{ mt: 1 }}
              />
            </Box>

            <Box>
              <Typography variant="body2" color="text.secondary">
                Full Occlusion Rate
              </Typography>
              <Typography variant="h6" color="error.main">
                {occlusionAnalysis.fullOcclusion || 0}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={occlusionAnalysis.fullOcclusion || 0}
                color="error"
                sx={{ mt: 1 }}
              />
            </Box>

            <Box>
              <Typography variant="body2" color="text.secondary">
                Occlusion Impact on Performance
              </Typography>
              <Typography variant="h6" color={
                (occlusionAnalysis.occlusionImpact || 0) < 0.2 ? 'success.main' :
                (occlusionAnalysis.occlusionImpact || 0) < 0.4 ? 'warning.main' : 'error.main'
              }>
                {((occlusionAnalysis.occlusionImpact || 0) * 100).toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Performance degradation due to occlusion
              </Typography>
            </Box>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Spatial Analysis
          </Typography>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Analysis Type</InputLabel>
            <Select
              value={viewType}
              label="Analysis Type"
              onChange={(e) => setViewType(e.target.value as any)}
            >
              <MenuItem value="heatmap">Detection Heatmap</MenuItem>
              <MenuItem value="distribution">Spatial Distribution</MenuItem>
              <MenuItem value="quality">Bounding Box Quality</MenuItem>
              <MenuItem value="occlusion">Occlusion Analysis</MenuItem>
            </Select>
          </FormControl>
        </Box>

        {viewType === 'heatmap' && renderSpatialHeatmap()}
        {viewType === 'distribution' && renderQuadrantDistribution()}
        {viewType === 'quality' && renderBoundingBoxQuality()}
        {viewType === 'occlusion' && renderOcclusionAnalysis()}
      </CardContent>
    </Card>
  );
};