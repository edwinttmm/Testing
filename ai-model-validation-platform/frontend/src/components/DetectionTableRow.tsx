import React from 'react';
import { TableRow, TableCell, Chip, Typography, Tooltip, Box } from '@mui/material';
import { CheckCircle as CheckCircleIcon, Error as ErrorIcon } from '@mui/icons-material';

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
    // NEW: Multi-video sequence fields
    sequence_id?: string;
    video_id?: string;
    videoId?: string;
    video_relative_timestamp?: number;
    videoRelativeTimestamp?: number;
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
  const isPassed = detection.passed || detection.result === 'pass';

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

  const voltage = detection.voltage || detection.voltage_level || 0;
  // BUG FIX: Use validation_result field instead of ground_truth_match_id (which is not populated)
  // Timeline component correctly uses validation_result, table should too
  const hasGroundTruthMatch = detection.validation_result === 'TP' || detection.validation_result === 'PASS';
  const validationResult = detection.validation_result || (hasGroundTruthMatch ? 'TP' : 'FP');

  // NEW: Extract video and sequence info
  const videoIdValue = detection.video_id || detection.videoId;
  const sequenceIdValue = detection.sequence_id;
  const videoRelativeTime = detection.video_relative_timestamp || detection.videoRelativeTimestamp;

  return (
    <TableRow
      sx={{
        bgcolor: isPassed ? 'success.50' : 'error.50',
        '&:hover': { bgcolor: isPassed ? 'success.100' : 'error.100' },
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
        <Typography
          variant="body2"
          title={videoRelativeTime ? `Video relative: ${videoRelativeTime.toFixed(3)}s` : undefined}
        >
          {detection.timestamp?.toFixed(3) || '—'}
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
            color={latency < 50 ? 'success.main' : latency < 100 ? 'warning.main' : 'error.main'}
            title={`Latency: ${latency.toFixed(1)}ms`}
          >
            {latency.toFixed(1)} ms
          </Typography>
          {latency > 5000 && (
            <Tooltip title="Detection occurred outside video timing window - assigned artificial 10s latency for tracking">
              <span style={{ color: '#ff9800', fontSize: '0.9rem', cursor: 'help' }}>⚠</span>
            </Tooltip>
          )}
        </Box>
      </TableCell>

      <TableCell>
        {hasGroundTruthMatch ? (
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
        <Chip
          icon={isPassed ? <CheckCircleIcon /> : <ErrorIcon />}
          label={isPassed ? "PASS" : "FAIL"}
          color={isPassed ? "success" : "error"}
          size="small"
        />
      </TableCell>
    </TableRow>
  );
};
