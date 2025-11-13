import React from 'react';
import { Alert, Box, Typography, Chip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';

interface TestStatusBannerProps {
  passed: boolean;
  detectionCount: number;
  expectedCount: number;
  matchRate: number;
  passRate?: number;
  failedCount?: number;
  latencyThresholdMs?: number;
  criteriaText?: string;
  videoCount?: number;
  videosPassedCount?: number;
}

export const TestStatusBanner: React.FC<TestStatusBannerProps> = ({
  passed,
  detectionCount,
  expectedCount,
  matchRate,
  passRate,
  failedCount,
  latencyThresholdMs,
  criteriaText,
  videoCount,
  videosPassedCount
}) => {
  return (
    <Alert
      severity={passed ? "success" : "error"}
      icon={passed ? <CheckCircleIcon sx={{ fontSize: 40 }} /> : <ErrorIcon sx={{ fontSize: 40 }} />}
      sx={{
        mb: 3,
        p: 3,
        '& .MuiAlert-icon': {
          fontSize: 40,
          alignItems: 'center'
        }
      }}
    >
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <Box>
          <Typography variant="h4" fontWeight="bold">
            {passed ? "✓ TEST PASSED" : "✗ TEST FAILED"}
          </Typography>
          <Typography variant="h6" sx={{ mt: 1 }}>
            {detectionCount} out of {expectedCount} detections captured
          </Typography>
          {videoCount && videoCount > 1 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
              <VideoLibraryIcon sx={{ fontSize: 20 }} />
              <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                {videosPassedCount}/{videoCount} Videos Passed
              </Typography>
            </Box>
          )}
          <Typography variant="body2">
            Match Rate: {matchRate.toFixed(1)}%
          </Typography>
          {typeof passRate === 'number' && (
            <Typography variant="body2">
              Pass Rate: {passRate.toFixed(1)}%
            </Typography>
          )}
          {typeof latencyThresholdMs === 'number' && (
            <Typography variant="body2">
              Latency Threshold: {latencyThresholdMs}ms
            </Typography>
          )}
          {typeof failedCount === 'number' && failedCount > 0 && (
            <Typography variant="body2" color="error">
              Failures above threshold: {failedCount}
            </Typography>
          )}
          {criteriaText && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              {criteriaText}
            </Typography>
          )}
        </Box>
        <Box textAlign="right">
          <Chip
            label={passed ? "PASSED" : "FAILED"}
            color={passed ? "success" : "error"}
            sx={{
              fontSize: 20,
              height: 50,
              px: 3,
              fontWeight: 'bold'
            }}
          />
        </Box>
      </Box>
    </Alert>
  );
};
