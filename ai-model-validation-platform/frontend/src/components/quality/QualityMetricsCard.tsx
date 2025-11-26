/**
 * Quality Metrics Card Component
 *
 * Dashboard widget displaying quality statistics with:
 * - Validation rate with progress bar
 * - Quality level indicator (EXCELLENT, GOOD, FAIR, POOR)
 * - Color-coded visual design
 * - Click to expand details
 */

import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Box,
  LinearProgress,
  Chip,
  Stack,
  IconButton,
  Collapse,
  Button,
  Divider,
  Skeleton,
  Alert
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon
} from '@mui/icons-material';
import { QualityLevel, QualityInfo } from '../../types/quality';
import { qualityApi } from '../../services/qualityApi';

interface QualityMetricsCardProps {
  sessionId?: string;  // For session-specific metrics; undefined for global
  onViewDetails?: () => void;
  autoRefresh?: boolean;
  refreshInterval?: number; // in milliseconds
}

const qualityLevelConfig = (level: QualityLevel) => {
  switch (level) {
    case QualityLevel.EXCELLENT:
      return { color: '#2e7d32', bgColor: '#e8f5e9', icon: <CheckCircleIcon />, label: 'Excellent' };
    case QualityLevel.GOOD:
      return { color: '#558b2f', bgColor: '#f1f8e9', icon: <CheckCircleIcon />, label: 'Good' };
    case QualityLevel.FAIR:
      return { color: '#f57c00', bgColor: '#fff3e0', icon: <WarningIcon />, label: 'Fair' };
    case QualityLevel.POOR:
      return { color: '#c62828', bgColor: '#ffebee', icon: <ErrorIcon />, label: 'Poor' };
    default:
      return { color: '#757575', bgColor: '#f5f5f5', icon: null, label: 'Unknown' };
  }
};

const getValidationRateColor = (rate: number): string => {
  if (rate >= 95) return '#2e7d32';  // Green
  if (rate >= 85) return '#558b2f';  // Light green
  if (rate >= 70) return '#f57c00';  // Orange
  return '#c62828';  // Red
};

export const QualityMetricsCard: React.FC<QualityMetricsCardProps> = ({
  sessionId,
  onViewDetails,
  autoRefresh = false,
  refreshInterval = 30000
}) => {
  const [qualityInfo, setQualityInfo] = useState<QualityInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const fetchQualityData = async () => {
    if (!sessionId) {
      setLoading(false);
      return;
    }

    try {
      setError(null);
      const data = await qualityApi.getSessionQuality(sessionId);
      setQualityInfo(data);
    } catch (err) {
      console.error('Failed to fetch quality metrics:', err);
      setError('Failed to load quality metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQualityData();

    if (autoRefresh && refreshInterval > 0) {
      const interval = setInterval(fetchQualityData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [sessionId, autoRefresh, refreshInterval]);

  const handleRefresh = () => {
    setLoading(true);
    fetchQualityData();
  };

  if (loading) {
    return (
      <Card sx={{ minHeight: 200 }}>
        <CardContent>
          <Skeleton variant="text" width="60%" height={32} />
          <Skeleton variant="rectangular" height={60} sx={{ my: 2 }} />
          <Skeleton variant="text" width="40%" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error" action={
            <IconButton size="small" onClick={handleRefresh}>
              <RefreshIcon />
            </IconButton>
          }>
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!qualityInfo) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">No quality data available</Alert>
        </CardContent>
      </Card>
    );
  }

  const levelConfig = qualityLevelConfig(qualityInfo.quality_level);
  const validationRate = qualityInfo.validation_rate;
  const rateColor = getValidationRateColor(validationRate);

  return (
    <Card
      sx={{
        boxShadow: 3,
        transition: 'box-shadow 0.3s',
        '&:hover': {
          boxShadow: 6
        }
      }}
    >
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" component="div" fontWeight={600}>
            Data Quality
          </Typography>
          <IconButton
            size="small"
            onClick={handleRefresh}
            disabled={loading}
            aria-label="Refresh quality metrics"
          >
            <RefreshIcon />
          </IconButton>
        </Box>

        {/* Validation Rate */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 1 }}>
            <Typography variant="h3" component="div" sx={{ color: rateColor, fontWeight: 700 }}>
              {validationRate.toFixed(1)}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Validation Rate
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={validationRate}
            sx={{
              height: 8,
              borderRadius: 4,
              backgroundColor: '#e0e0e0',
              '& .MuiLinearProgress-bar': {
                backgroundColor: rateColor,
                borderRadius: 4
              }
            }}
          />
        </Box>

        {/* Quality Level Badge */}
        <Box sx={{ mb: 2 }}>
          <Chip
            icon={levelConfig.icon}
            label={`Quality: ${levelConfig.label}`}
            sx={{
              backgroundColor: levelConfig.bgColor,
              color: levelConfig.color,
              fontWeight: 600,
              fontSize: '0.875rem',
              px: 1,
              '& .MuiChip-icon': {
                color: levelConfig.color
              }
            }}
          />
        </Box>

        {/* Summary Stats */}
        <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Usable
            </Typography>
            <Typography variant="h6" fontWeight={600} color="success.main">
              {qualityInfo.summary.usable_detections}
            </Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Degraded
            </Typography>
            <Typography variant="h6" fontWeight={600} color="warning.main">
              {qualityInfo.summary.degraded_detections}
            </Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Total
            </Typography>
            <Typography variant="h6" fontWeight={600}>
              {qualityInfo.summary.total_detections}
            </Typography>
          </Box>
        </Stack>

        {/* Warnings indicator */}
        {qualityInfo.summary.has_warnings && (
          <Alert severity="warning" sx={{ mt: 2 }} icon={<WarningIcon />}>
            <Typography variant="body2">
              {qualityInfo.summary.critical_issues} critical issue{qualityInfo.summary.critical_issues !== 1 ? 's' : ''} detected
            </Typography>
          </Alert>
        )}

        {/* Expandable Details */}
        <Collapse in={expanded} timeout="auto" unmountOnExit>
          <Divider sx={{ my: 2 }} />
          <Stack spacing={1}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2" color="text.secondary">Timing Degraded:</Typography>
              <Typography variant="body2" fontWeight={500}>
                {qualityInfo.timing_health.timing_degraded ? 'Yes' : 'No'}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2" color="text.secondary">Timing Verified:</Typography>
              <Typography variant="body2" fontWeight={500}>
                {qualityInfo.timing_health.timing_verified ? 'Yes' : 'No'}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2" color="text.secondary">Degradation Rate:</Typography>
              <Typography variant="body2" fontWeight={500} color="warning.main">
                {qualityInfo.timing_health.degradation_percentage.toFixed(1)}%
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2" color="text.secondary">Verified Count:</Typography>
              <Typography variant="body2" fontWeight={500}>
                {qualityInfo.timing_health.verified_count}
              </Typography>
            </Box>
          </Stack>
        </Collapse>
      </CardContent>

      <CardActions sx={{ px: 2, pb: 2 }}>
        <Button
          size="small"
          onClick={() => setExpanded(!expanded)}
          endIcon={<ExpandMoreIcon sx={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: '0.3s' }} />}
        >
          {expanded ? 'Hide' : 'Show'} Details
        </Button>
        {onViewDetails && (
          <Button size="small" onClick={onViewDetails} variant="outlined">
            Full Report
          </Button>
        )}
      </CardActions>
    </Card>
  );
};

/**
 * Compact version for inline display
 */
export const CompactQualityMetrics: React.FC<{ qualityInfo: QualityInfo }> = ({ qualityInfo }) => {
  const levelConfig = qualityLevelConfig(qualityInfo.quality_level);

  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
      <Chip
        icon={levelConfig.icon}
        label={levelConfig.label}
        size="small"
        sx={{
          backgroundColor: levelConfig.bgColor,
          color: levelConfig.color,
          fontWeight: 600
        }}
      />
      <Typography variant="body2" color="text.secondary">
        {qualityInfo.validation_rate.toFixed(1)}% validated
      </Typography>
      {qualityInfo.summary.has_warnings && (
        <Chip
          icon={<WarningIcon />}
          label={`${qualityInfo.warnings.length} warning${qualityInfo.warnings.length !== 1 ? 's' : ''}`}
          size="small"
          color="warning"
        />
      )}
    </Box>
  );
};
