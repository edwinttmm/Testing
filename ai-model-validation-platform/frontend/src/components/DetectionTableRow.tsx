import React from 'react';
import { TableRow, TableCell, Chip, Typography, Tooltip, Box } from '@mui/material';
import { CheckCircle as CheckCircleIcon, Error as ErrorIcon, WarningAmberRounded as WarningIcon } from '@mui/icons-material';

interface DetectionTableRowProps {
  index: number;
  detection: {
    id: string;
    timestamp?: number;
    detection_time_ms?: number;
    real_latency_ms?: number;
    actualLatencyMs?: number;
    actual_latency_ms?: number | string;  // NEW: Backend unified latency field
    voltage?: number;
    voltage_level?: number;
    passed?: boolean;
    result?: 'pass' | 'fail';
    ground_truth_match_id?: string;
    validation_result?: string;
    latency_threshold_ms?: number;
    latencyThresholdMs?: number;
    tolerance_ms?: number;
    toleranceMs?: number;
    usable_for_validation?: boolean;
    usableForValidation?: boolean;
    timing_degraded?: boolean;
    timingDegraded?: boolean;
    // NEW: Multi-video sequence fields
    sequence_id?: string;
    video_id?: string;
    videoId?: string;
    video_relative_timestamp?: number;
    videoRelativeTimestamp?: number;
    // NEW: Detection source fields
    source?: 'ai' | 'labjack' | 'manual';
    detection_type?: 'hardware' | 'software';
  };
  videoName?: string;
  videoSequenceNumber?: number;
  totalVideos?: number;
  onClick?: () => void;
}

export const DetectionTableRow: React.FC<DetectionTableRowProps> = ({
  index,
  detection,
  videoName,
  videoSequenceNumber,
  totalVideos,
  onClick
}) => {
  const usableForValidation =
    detection.usable_for_validation ?? detection.usableForValidation ?? true;
  const timingDegraded =
    detection.timing_degraded ?? detection.timingDegraded ?? false;
  const isTimingSuppressed = !usableForValidation || timingDegraded;
  const normalizedResult = typeof detection.validation_result === 'string'
    ? detection.validation_result.toUpperCase()
    : undefined;
  const isFailureState = !isTimingSuppressed
    ? normalizedResult
      ? ['FAIL', 'FP', 'FN'].includes(normalizedResult)
      : detection.result === 'fail'
    : false;
  const isPassed = !isTimingSuppressed && (detection.passed ?? (!isFailureState));

  // CRITICAL FIX: Backend returns videoRelativeTimestamp (seconds) in perVideoResults.detectionEvents
  // Convert from seconds to milliseconds for display
  const latency =
    (detection.videoRelativeTimestamp ? detection.videoRelativeTimestamp * 1000 : null)
    ?? (detection.video_relative_timestamp ? detection.video_relative_timestamp * 1000 : null)
    ?? (typeof detection.actual_latency_ms === 'string' ? parseFloat(detection.actual_latency_ms) : detection.actual_latency_ms)
    ?? detection.actualLatencyMs
    ?? detection.real_latency_ms
    ?? detection.detection_time_ms
    ?? 0;

  const latencyValue = typeof latency === 'number' ? latency : Number(latency) || 0;
  const latencyMagnitude = Math.abs(latencyValue);
  const voltage = detection.voltage || detection.voltage_level || 0;
  const latencyThreshold =
    detection.latency_threshold_ms ??
    detection.latencyThresholdMs ??
    detection.tolerance_ms ??
    detection.toleranceMs ??
    100;
  const withinTolerance = latencyMagnitude <= latencyThreshold;
  const latencyColor = withinTolerance
    ? 'success.main'
    : latencyMagnitude <= latencyThreshold * 1.5
      ? 'warning.main'
      : 'error.main';
  const latencyTooltip = `Latency: ${latencyValue.toFixed(1)}ms (threshold ±${latencyThreshold}ms)`;

  // BUG FIX: Use validation_result field instead of ground_truth_match_id (which is not populated)
  // Timeline component correctly uses validation_result, table should too
  const hasGroundTruthMatch = !isTimingSuppressed
    ? normalizedResult
      ? ['TP', 'PASS'].includes(normalizedResult)
      : !!detection.ground_truth_match_id
    : false;
  const validationResult = normalizedResult || (hasGroundTruthMatch ? 'TP' : 'FP');

  // NEW: Extract video and sequence info
  const videoIdValue = detection.video_id || detection.videoId;
  const sequenceIdValue = detection.sequence_id;
  const videoRelativeTime = detection.video_relative_timestamp ?? detection.videoRelativeTimestamp;

  // NEW: Extract detection source
  const detectionSource = detection.source;
  const detectionType = detection.detection_type;

  const rowBgColor = isTimingSuppressed
    ? 'warning.50'
    : isPassed
      ? 'success.50'
      : 'error.50';
  const rowHoverColor = isTimingSuppressed
    ? 'warning.100'
    : isPassed
      ? 'success.100'
      : 'error.100';

  return (
    <TableRow
      sx={{
        bgcolor: rowBgColor,
        '&:hover': { bgcolor: rowHoverColor },
        cursor: onClick ? 'pointer' : 'default'
      }}
      onClick={onClick}
    >
      <TableCell>
        <Typography variant="body2" fontWeight="bold">
          {index + 1}
        </Typography>
      </TableCell>

      <TableCell>
        {videoSequenceNumber && totalVideos ? (
          <Chip
            label={`Video ${videoSequenceNumber}/${totalVideos}`}
            size="small"
            color="primary"
            variant="outlined"
            title={videoIdValue ? `Video ID: ${videoIdValue.substring(0, 8)}...` : undefined}
          />
        ) : (
          <Typography variant="caption" color="textSecondary" title={videoIdValue || undefined}>
            {videoName || 'N/A'}
          </Typography>
        )}
      </TableCell>

      <TableCell>
        {detectionSource && (
          <Chip
            label={detectionSource.toUpperCase()}
            size="small"
            color={
              detectionSource === 'labjack' ? 'success' :
              detectionSource === 'ai' ? 'primary' : 'default'
            }
            variant="outlined"
            title={`Detection Source: ${detectionSource}`}
          />
        )}
        {!detectionSource && <Typography variant="caption" color="textSecondary">N/A</Typography>}
      </TableCell>

      <TableCell>
        <Typography
          variant="body2"
          title={
            videoRelativeTime !== undefined
              ? `Video relative: ${videoRelativeTime.toFixed(3)}s`
              : detection.timestamp !== undefined
                ? `Timestamp: ${detection.timestamp.toFixed(3)}s`
                : undefined
          }
        >
          {videoRelativeTime !== undefined
            ? videoRelativeTime.toFixed(3)
            : detection.timestamp !== undefined
              ? detection.timestamp.toFixed(3)
              : '—'}
        </Typography>
      </TableCell>

      <TableCell>
        <Typography variant="body2" fontWeight="medium">
          {voltage.toFixed(2)}V
        </Typography>
      </TableCell>

      <TableCell>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography
            variant="body2"
            fontWeight="bold"
            color={latencyColor}
            title={latencyTooltip}
          >
            {latencyValue.toFixed(1)} ms
          </Typography>
          <Chip
            label={`±${latencyThreshold}ms`}
            size="small"
            color={withinTolerance ? 'success' : 'error'}
            variant="outlined"
            title={`Session tolerance: ±${latencyThreshold}ms`}
          />
          {latencyMagnitude > 5000 && (
            <Tooltip title="Detection occurred outside video timing window - assigned artificial 10s latency for tracking">
              <span style={{ color: '#ff9800', fontSize: '0.9rem', cursor: 'help' }}>⚠</span>
            </Tooltip>
          )}
        </Box>
      </TableCell>

      <TableCell>
        {isTimingSuppressed ? (
          <Tooltip title="Timing data was degraded; this detection was excluded from GT matching.">
            <Chip
              label="Timing degraded"
              size="small"
              color="warning"
              variant="outlined"
            />
          </Tooltip>
        ) : hasGroundTruthMatch ? (
          <Tooltip title={`Validation: ${validationResult}`}>
            <Chip
              label="Yes"
              size="small"
              color="success"
              variant="outlined"
            />
          </Tooltip>
        ) : (
          <Chip
            label="No"
            size="small"
            color="warning"
            variant="outlined"
          />
        )}
      </TableCell>

      <TableCell>
        {isTimingSuppressed ? (
          <Chip
            icon={<WarningIcon />}
            label="TIMING DEGRADED"
            color="warning"
            size="small"
          />
        ) : (
          <Chip
            icon={isPassed ? <CheckCircleIcon /> : <ErrorIcon />}
            label={isPassed ? "PASS" : "FAIL"}
            color={isPassed ? "success" : "error"}
            size="small"
          />
        )}
      </TableCell>
    </TableRow>
  );
};
