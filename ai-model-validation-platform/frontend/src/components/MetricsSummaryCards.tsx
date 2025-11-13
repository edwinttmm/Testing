import React from 'react';
import { Grid, Card, CardContent, Typography, LinearProgress, Chip, Box } from '@mui/material';
import {
  Assessment as AssessmentIcon,
  Timer as TimerIcon,
  CheckCircle as CheckCircleIcon,
  Router as RouterIcon
} from '@mui/icons-material';

interface MetricsSummaryCardsProps {
  detections: number;
  expected: number;
  avgLatency: number;
  matchRate: number;
  hardwareStatus: {
    labJackConnected: boolean;
    labJackModel: string;
  };
  videoStartupDelay?: number; // Video startup delay in ms (system timing)
  detectionLatency?: number;   // True detection latency in ms (what we care about)
}

export const MetricsSummaryCards: React.FC<MetricsSummaryCardsProps> = ({
  detections,
  expected,
  avgLatency,
  matchRate,
  hardwareStatus,
  videoStartupDelay,
  detectionLatency
}) => {
  const getLatencyQuality = (latency: number) => {
    if (latency < 50) return { label: 'Excellent', color: 'success.main' };
    if (latency < 100) return { label: 'Good', color: 'warning.main' };
    return { label: 'Needs Improvement', color: 'error.main' };
  };

  // Use detectionLatency if provided, otherwise fall back to avgLatency
  const displayLatency = detectionLatency !== undefined ? detectionLatency : avgLatency;
  const latencyQuality = getLatencyQuality(displayLatency);

  return (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      {/* Detections Card */}
      <Grid item xs={12} md={videoStartupDelay !== undefined ? 2.4 : 3}>
        <Card elevation={2}>
          <CardContent>
            <Box display="flex" alignItems="center" mb={1}>
              <AssessmentIcon color="primary" sx={{ mr: 1 }} />
              <Typography color="textSecondary" variant="overline">
                Detections
              </Typography>
            </Box>
            <Typography variant="h3" color="primary" fontWeight="bold">
              {detections}
            </Typography>
            <Typography variant="body2" color="textSecondary">
              out of {expected} expected
            </Typography>
            <LinearProgress
              variant="determinate"
              value={(detections / expected) * 100}
              sx={{ mt: 2, height: 8, borderRadius: 1 }}
              color={detections === expected ? 'success' : detections >= expected * 0.8 ? 'warning' : 'error'}
            />
          </CardContent>
        </Card>
      </Grid>

      {/* Detection Latency Card - PROMINENT */}
      <Grid item xs={12} md={videoStartupDelay !== undefined ? 2.4 : 3}>
        <Card elevation={3} sx={{ border: 2, borderColor: 'primary.main' }}>
          <CardContent>
            <Box display="flex" alignItems="center" mb={1}>
              <TimerIcon color="primary" sx={{ mr: 1 }} />
              <Typography color="primary" variant="overline" fontWeight="bold">
                Detection Latency
              </Typography>
            </Box>
            <Typography variant="h3" color={latencyQuality.color} fontWeight="bold">
              {displayLatency.toFixed(0)}
              <Typography component="span" variant="h6" color="textSecondary">ms</Typography>
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {latencyQuality.label}
            </Typography>
            <LinearProgress
              variant="determinate"
              value={Math.min(100, (displayLatency / 200) * 100)}
              sx={{ mt: 2, height: 8, borderRadius: 1 }}
              color={displayLatency < 50 ? 'success' : displayLatency < 100 ? 'warning' : 'error'}
            />
          </CardContent>
        </Card>
      </Grid>

      {/* Video Startup Delay Card - Only show if provided */}
      {videoStartupDelay !== undefined && (
        <Grid item xs={12} md={2.4}>
          <Card elevation={2}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <TimerIcon sx={{ mr: 1, color: 'text.secondary' }} />
                <Typography color="textSecondary" variant="overline">
                  Video Startup
                </Typography>
              </Box>
              <Typography variant="h3" color="text.secondary" fontWeight="bold">
                {videoStartupDelay.toFixed(0)}
                <Typography component="span" variant="h6" color="textSecondary">ms</Typography>
              </Typography>
              <Typography variant="body2" color="textSecondary">
                System delay
              </Typography>
              <Box sx={{ mt: 2, height: 8 }} /> {/* Spacer for alignment */}
            </CardContent>
          </Card>
        </Grid>
      )}

      {/* Match Rate Card */}
      <Grid item xs={12} md={videoStartupDelay !== undefined ? 2.4 : 3}>
        <Card elevation={2}>
          <CardContent>
            <Box display="flex" alignItems="center" mb={1}>
              <CheckCircleIcon color="primary" sx={{ mr: 1 }} />
              <Typography color="textSecondary" variant="overline">
                Match Rate
              </Typography>
            </Box>
            <Typography variant="h3" color={matchRate >= 80 ? 'success.main' : 'warning.main'} fontWeight="bold">
              {matchRate.toFixed(1)}
              <Typography component="span" variant="h6" color="textSecondary">%</Typography>
            </Typography>
            <Typography variant="body2" color="textSecondary">
              {matchRate >= 90 ? 'Excellent' : matchRate >= 80 ? 'Good' : 'Fair'}
            </Typography>
            <LinearProgress
              variant="determinate"
              value={matchRate}
              sx={{ mt: 2, height: 8, borderRadius: 1 }}
              color={matchRate >= 90 ? 'success' : matchRate >= 80 ? 'warning' : 'error'}
            />
          </CardContent>
        </Card>
      </Grid>

      {/* Hardware Status Card */}
      <Grid item xs={12} md={videoStartupDelay !== undefined ? 2.4 : 3}>
        <Card elevation={2}>
          <CardContent>
            <Box display="flex" alignItems="center" mb={1}>
              <RouterIcon color="primary" sx={{ mr: 1 }} />
              <Typography color="textSecondary" variant="overline">
                Hardware
              </Typography>
            </Box>
            <Typography variant="h5" fontWeight="bold">
              {hardwareStatus.labJackModel}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Status:
            </Typography>
            <Chip
              label={hardwareStatus.labJackConnected ? "Connected" : "Disconnected"}
              color={hardwareStatus.labJackConnected ? "success" : "error"}
              size="small"
              sx={{ mt: 1 }}
            />
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};
