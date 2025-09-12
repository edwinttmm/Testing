import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  LinearProgress,
  Alert,
  Divider
} from '@mui/material';
import {
  CheckCircle as PassIcon,
  Cancel as FailIcon,
  Speed as LatencyIcon,
  Timeline as TrendIcon,
  Assessment as MetricsIcon
} from '@mui/icons-material';

interface VideoDetectionResult {
  videoName: string;
  videoId: string;
  detectionFound: boolean;
  latencyMs?: number;
  result: 'PASS' | 'FAIL_TIMEOUT' | 'FAIL_NO_DETECTION';
  details: string;
}

interface EnhancedTestMetrics {
  sessionName: string;
  projectName: string;
  totalVideos: number;
  passedVideos: number;
  failedVideos: number;
  passRate: number;
  averageLatencyMs: number;
  latencyThresholdMs: number;
  videoResults: VideoDetectionResult[];
}

interface EnhancedTestMetricsPanelProps {
  sessionId: string;
}

const EnhancedTestMetricsPanel: React.FC<EnhancedTestMetricsPanelProps> = ({ sessionId }) => {
  const [metrics, setMetrics] = useState<EnhancedTestMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load real enhanced test data from API
  useEffect(() => {
    const loadEnhancedMetrics = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Try to fetch real enhanced test results from API
        const response = await fetch(`/api/results/sessions/${sessionId}/detailed`);
        
        if (!response.ok) {
          throw new Error(`API request failed: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Check if we have actual enhanced test data
        if (data.video_results && data.video_results.length > 0) {
          const videoResults: VideoDetectionResult[] = data.video_results.map((video: any, index: number) => ({
            videoName: video.video_name || `Video ${index + 1}`,
            videoId: video.video_id || `video_${index}`,
            detectionFound: video.total_detections > 0,
            latencyMs: video.average_confidence || undefined, // Repurposed field for latency
            result: video.total_detections > 0 
              ? (video.success_rate > 50 ? 'PASS' : 'FAIL_TIMEOUT')
              : 'FAIL_NO_DETECTION',
            details: video.total_detections > 0 
              ? `Detected in ${video.average_confidence || 0}ms`
              : 'No detection found'
          }));

          const totalVideos = videoResults.length;
          const passedVideos = videoResults.filter(v => v.result === 'PASS').length;
          const failedVideos = totalVideos - passedVideos;
          const passRate = totalVideos > 0 ? (passedVideos / totalVideos) * 100 : 0;
          
          const latencies = videoResults
            .filter(v => v.latencyMs !== undefined && v.latencyMs > 0)
            .map(v => v.latencyMs!);
          const averageLatency = latencies.length > 0 
            ? latencies.reduce((a, b) => a + b, 0) / latencies.length 
            : 0;

          const enhancedMetrics: EnhancedTestMetrics = {
            sessionName: data.session_name || "Enhanced Detection Test",
            projectName: data.project_name || "Detection Project",
            totalVideos,
            passedVideos,
            failedVideos,
            passRate,
            averageLatencyMs: averageLatency,
            latencyThresholdMs: 100, // Default threshold - should come from test config
            videoResults
          };
          
          setMetrics(enhancedMetrics);
        } else {
          // No enhanced test results available
          setMetrics(null);
        }
        
      } catch (err) {
        console.error('Failed to load enhanced test metrics:', err);
        // If API fails, assume no tests have been run
        setMetrics(null);
        setError(null); // Don't show error, just show "no tests" state
      } finally {
        setLoading(false);
      }
    };
    
    loadEnhancedMetrics();
  }, [sessionId]);

  const getResultColor = (result: string) => {
    switch (result) {
      case 'PASS': return 'success';
      case 'FAIL_TIMEOUT': return 'error';
      case 'FAIL_NO_DETECTION': return 'warning';
      default: return 'default';
    }
  };

  const getResultIcon = (result: string) => {
    switch (result) {
      case 'PASS': return <PassIcon color="success" fontSize="small" />;
      case 'FAIL_TIMEOUT': return <FailIcon color="error" fontSize="small" />;
      case 'FAIL_NO_DETECTION': return <FailIcon color="warning" fontSize="small" />;
      default: return null;
    }
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Loading Enhanced Test Metrics...
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        Failed to load enhanced test metrics: {error}
      </Alert>
    );
  }

  if (!metrics) {
    return (
      <Alert severity="info" sx={{ m: 2 }}>
        No enhanced test metrics available for this session.
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <MetricsIcon color="primary" />
        Enhanced Detection Test Results
      </Typography>
      
      <Typography variant="body2" color="text.secondary" gutterBottom>
        {metrics.sessionName} • {metrics.projectName}
      </Typography>

      {/* Detection Overview Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Total Videos
              </Typography>
              <Typography variant="h4" component="div">
                {metrics.totalVideos}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Pass Rate
              </Typography>
              <Typography variant="h4" component="div" color="success.main">
                {metrics.passRate.toFixed(1)}%
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={metrics.passRate} 
                color="success"
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <LatencyIcon fontSize="small" />
                Avg Latency
              </Typography>
              <Typography variant="h4" component="div">
                {metrics.averageLatencyMs > 0 ? metrics.averageLatencyMs.toFixed(1) : '--'}
                <Typography variant="h6" component="span" color="text.secondary">
                  ms
                </Typography>
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Threshold: {metrics.latencyThresholdMs}ms
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Detections Found
              </Typography>
              <Typography variant="h4" component="div" color="primary.main">
                {metrics.videoResults.filter(v => v.detectionFound).length}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                of {metrics.totalVideos} videos
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Video Detection Results */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendIcon color="primary" />
                Video Detection Results
              </Typography>
              
              <TableContainer sx={{ maxHeight: 500 }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Video</TableCell>
                      <TableCell align="center">Detection</TableCell>
                      <TableCell align="right">Latency (ms)</TableCell>
                      <TableCell align="center">Result</TableCell>
                      <TableCell>Details</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {metrics.videoResults.map((video) => (
                      <TableRow key={video.videoId}>
                        <TableCell>
                          <Typography variant="body2" fontWeight="medium">
                            {video.videoName}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={video.detectionFound ? 'YES' : 'NO'}
                            size="small"
                            color={video.detectionFound ? 'success' : 'default'}
                            variant={video.detectionFound ? 'filled' : 'outlined'}
                          />
                        </TableCell>
                        <TableCell align="right">
                          {video.latencyMs !== undefined && video.latencyMs > 0 ? (
                            <Typography 
                              variant="body2" 
                              color={video.latencyMs > metrics.latencyThresholdMs ? 'error' : 'text.primary'}
                              fontWeight={video.latencyMs > metrics.latencyThresholdMs ? 'bold' : 'normal'}
                            >
                              {video.latencyMs.toFixed(1)}
                            </Typography>
                          ) : (
                            <Typography variant="body2" color="text.secondary">
                              --
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            icon={getResultIcon(video.result)}
                            label={video.result}
                            size="small"
                            color={getResultColor(video.result) as any}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">
                            {video.details}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Divider sx={{ my: 3 }} />
      
      {/* Performance Summary */}
      <Alert 
        severity={metrics.passRate >= 80 ? "success" : metrics.passRate >= 60 ? "warning" : "error"}
        sx={{ mt: 3 }}
      >
        <Typography variant="body2">
          <strong>Detection Test Summary:</strong> {' '}
          {metrics.passRate >= 80 
            ? `Excellent detection performance! ${metrics.passedVideos} of ${metrics.totalVideos} videos passed with detections within ${metrics.latencyThresholdMs}ms threshold.`
            : metrics.passRate >= 60
            ? `Good detection performance. ${metrics.passedVideos} of ${metrics.totalVideos} videos passed. Some detections exceeded the ${metrics.latencyThresholdMs}ms latency threshold.`
            : `Detection performance needs improvement. Only ${metrics.passedVideos} of ${metrics.totalVideos} videos passed. Check for detection failures or latency issues.`
          }
        </Typography>
      </Alert>
    </Box>
  );
};

export default EnhancedTestMetricsPanel;