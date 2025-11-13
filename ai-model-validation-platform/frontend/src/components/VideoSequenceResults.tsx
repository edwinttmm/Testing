import React, { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Collapse,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Alert,
  LinearProgress,
  Tooltip
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  CheckCircle,
  Error,
  ExpandMore,
  ExpandLess,
  VideoFile,
  Timeline,
  Speed,
  Assessment,
  Close
} from '@mui/icons-material';
import { VideoSequenceResults, PerVideoResult, EnhancedDetectionEvent, GroundTruthEvent } from '../types/enhanced-results';
import FrameCorrelationTimeline from './FrameCorrelationTimeline';

interface VideoSequenceResultsProps {
  sequenceResults: VideoSequenceResults;
  groundTruthEvents?: GroundTruthEvent[];
  onExportVideo?: (videoId: string) => void;
  onExportAll?: () => void;
}

const VideoSequenceResultsComponent: React.FC<VideoSequenceResultsProps> = ({
  sequenceResults,
  groundTruthEvents = [],
  onExportVideo,
  onExportAll
}) => {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [selectedVideo, setSelectedVideo] = useState<PerVideoResult | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  const handleRowToggle = (videoId: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(videoId)) {
      newExpanded.delete(videoId);
    } else {
      newExpanded.add(videoId);
    }
    setExpandedRows(newExpanded);
  };

  const handleVideoDetail = (video: PerVideoResult) => {
    setSelectedVideo(video);
    setDetailDialogOpen(true);
  };

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const videos = useMemo<PerVideoResult[]>(() => {
    const rawVideos = sequenceResults?.per_video_results ?? sequenceResults?.perVideoResults ?? [];
    return Array.isArray(rawVideos) ? rawVideos : [];
  }, [sequenceResults]);

  const summary = useMemo(() => {
    if (sequenceResults?.sequence_summary) {
      return sequenceResults.sequence_summary;
    }

    if (sequenceResults?.sequenceSummary) {
      const s = sequenceResults.sequenceSummary;
      const durationSeconds =
        s.sequenceDurationSeconds ??
        videos.reduce((sum, video) => sum + (video.duration_seconds ?? video.duration ?? 0), 0);
      const totalDetectionsFromSummary =
        s.totalDetections ??
        videos.reduce(
          (sum, video) =>
            sum + (video.total_detections ?? video.totalDetections ?? video.detection_count ?? 0),
          0
        );
      const totalPassedFromSummary =
        s.totalPassedDetections ??
        videos.reduce(
          (sum, video) => sum + (video.passed_detections ?? video.passedDetections ?? 0),
          0
        );
      const totalFailedFromSummary =
        s.totalFailedDetections ??
        videos.reduce(
          (sum, video) => sum + (video.failed_detections ?? video.failedDetections ?? 0),
          0
        );

      return {
        overall_status: (s.overallStatus ?? 'partial') as 'pass' | 'fail' | 'partial',
        total_videos: s.totalVideos ?? videos.length,
        videos_passed: s.videosPassed ?? 0,
        videos_failed: s.videosFailed ?? 0,
        sequence_duration_seconds: durationSeconds,
        sequence_duration_formatted: s.sequenceDurationFormatted ?? formatDuration(durationSeconds),
        average_latency_ms: s.averageLatencyMs ?? 0,
        worst_latency_ms: s.worstLatencyMs ?? 0,
        best_latency_ms: s.bestLatencyMs ?? 0,
        total_detections: totalDetectionsFromSummary,
        total_passed_detections: totalPassedFromSummary,
        total_failed_detections: totalFailedFromSummary,
        overall_pass_rate: s.overallPassRate ?? (totalDetectionsFromSummary > 0
          ? (totalPassedFromSummary / totalDetectionsFromSummary) * 100
          : 0)
      };
    }

    const totalVideos = videos.length;
    const videosPassed = videos.filter(video =>
      (video.status ?? video.pass_fail ?? video.passFail ?? '').toString().toLowerCase() === 'pass'
    ).length;
    const videosFailed = videos.filter(video =>
      (video.status ?? video.pass_fail ?? video.passFail ?? '').toString().toLowerCase() === 'fail'
    ).length;
    const totalDetections = videos.reduce(
      (sum, video) => sum + (video.total_detections ?? video.totalDetections ?? video.detection_count ?? 0),
      0
    );
    const totalPassed = videos.reduce(
      (sum, video) => sum + (video.passed_detections ?? video.passedDetections ?? 0),
      0
    );
    const totalFailed = videos.reduce(
      (sum, video) => sum + (video.failed_detections ?? video.failedDetections ?? 0),
      0
    );
    const durationSeconds = videos.reduce(
      (sum, video) => sum + (video.duration_seconds ?? video.duration ?? 0),
      0
    );
    const worstLatency =
      videos.length > 0
        ? Math.max(...videos.map(video => video.max_latency_ms ?? video.maxLatencyMs ?? 0))
        : 0;
    const bestLatencyCandidates = videos
      .map(video => video.min_latency_ms ?? video.minLatencyMs)
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    const bestLatency = bestLatencyCandidates.length > 0 ? Math.min(...bestLatencyCandidates) : 0;

    const averageLatency =
      videos.length > 0
        ? videos.reduce((sum, video) => {
            const avgLatency = video.average_latency_ms ?? video.averageLatencyMs;
            const detectionCount = video.total_detections ?? video.totalDetections ?? video.detection_count ?? 0;
            if (avgLatency === undefined || detectionCount === 0) {
              return sum;
            }
            return sum + avgLatency * detectionCount;
          }, 0) / (totalDetections || 1)
        : 0;

    return {
      overall_status:
        videosFailed === 0 && videosPassed === totalVideos && totalVideos > 0
          ? 'pass'
          : videosPassed === 0 && videosFailed > 0
            ? 'fail'
            : 'partial',
      total_videos: totalVideos,
      videos_passed: videosPassed,
      videos_failed: videosFailed,
      sequence_duration_seconds: durationSeconds,
      sequence_duration_formatted: formatDuration(durationSeconds),
      average_latency_ms: averageLatency,
      worst_latency_ms: worstLatency,
      best_latency_ms: bestLatency,
      total_detections: totalDetections,
      total_passed_detections: totalPassed,
      total_failed_detections: totalFailed,
      overall_pass_rate: totalDetections > 0 ? (totalPassed / totalDetections) * 100 : 0
    };
  }, [sequenceResults, videos]);

  const overallStatus = (summary?.overall_status ?? 'partial') as 'pass' | 'fail' | 'partial';
  const totalVideos = summary?.total_videos ?? videos.length ?? 0;
  const videosPassed = summary?.videos_passed ?? 0;
  const videosFailed = summary?.videos_failed ?? Math.max(totalVideos - videosPassed, 0);
  const sequenceDurationSeconds =
    summary?.sequence_duration_seconds ??
    videos.reduce((sum, video) => sum + (video.duration_seconds ?? video.duration ?? 0), 0);
  const sequenceDurationFormatted =
    summary?.sequence_duration_formatted ?? formatDuration(sequenceDurationSeconds);
  const averageLatencyMs = summary?.average_latency_ms ?? 0;
  const worstLatencyMs = summary?.worst_latency_ms ?? 0;
  const bestLatencyMs = summary?.best_latency_ms ?? 0;
  const totalDetectionsSummary = summary?.total_detections ?? 0;
  const totalPassedDetectionsSummary = summary?.total_passed_detections ?? 0;
  const totalFailedDetectionsSummary =
    summary?.total_failed_detections ?? Math.max(totalDetectionsSummary - totalPassedDetectionsSummary, 0);
  const overallPassRate = summary?.overall_pass_rate ?? (
    totalDetectionsSummary > 0 ? (totalPassedDetectionsSummary / totalDetectionsSummary) * 100 : 0
  );

  const selectedVideoDetails = useMemo(() => {
    if (!selectedVideo) {
      return null;
    }

    const number = selectedVideo.video_number ?? selectedVideo.videoNumber ?? 0;
    const durationSeconds = selectedVideo.duration_seconds ?? selectedVideo.duration ?? 0;
    const passRateBase =
      selectedVideo.pass_rate ??
      selectedVideo.passRate ??
      selectedVideo.pass_rate_percent ??
      selectedVideo.passRatePercent ??
      undefined;
    const totalDetections =
      selectedVideo.total_detections ?? selectedVideo.totalDetections ?? selectedVideo.detection_count ?? 0;
    const passedDetections =
      selectedVideo.passed_detections ??
      selectedVideo.passedDetections ??
      (totalDetections > 0 && passRateBase !== undefined
        ? Math.round((Number(passRateBase) / 100) * totalDetections)
        : 0);
    const passRate = passRateBase ?? (totalDetections > 0 ? (passedDetections / totalDetections) * 100 : 0);

    return {
      number,
      name: selectedVideo.video_name ?? selectedVideo.videoName ?? `Video ${number || '?'}`,
      status: (selectedVideo.status ?? selectedVideo.pass_fail ?? selectedVideo.passFail ?? 'pending')
        .toString()
        .toLowerCase(),
      durationLabel: selectedVideo.duration_formatted ?? selectedVideo.durationFormatted ?? formatDuration(durationSeconds),
      durationSeconds,
      totalDetections,
      passRate,
      avgLatency: selectedVideo.average_latency_ms ?? selectedVideo.averageLatencyMs ?? 0,
      videoUrl:
        selectedVideo.video_url ??
        selectedVideo.videoUrl ??
        (selectedVideo.metrics as Record<string, any> | undefined)?.video_url ??
        null,
      fps: selectedVideo.fps ?? (selectedVideo.metrics as Record<string, any> | undefined)?.fps ?? undefined,
      startTime:
        selectedVideo.video_start_time ??
        selectedVideo.videoStartTime ??
        selectedVideo.start_time ??
        selectedVideo.startTime ??
        undefined,
      endTime:
        selectedVideo.video_end_time ??
        selectedVideo.videoEndTime ??
        selectedVideo.end_time ??
        selectedVideo.endTime ??
        undefined
    };
  }, [selectedVideo]);

  const getStatusColor = (status: 'pass' | 'fail') => {
    return status === 'pass' ? 'success' : 'error';
  };

  const getOverallStatusColor = (status: 'pass' | 'fail' | 'partial') => {
    switch (status) {
      case 'pass':
        return 'success';
      case 'fail':
        return 'error';
      case 'partial':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Box>
      {/* Sequence Summary Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <Assessment color="primary" sx={{ fontSize: 32 }} />
            <Typography variant="h5">
              Multi-Video Sequence Test Results
            </Typography>
            <Chip
              label={overallStatus.toUpperCase()}
              color={getOverallStatusColor(overallStatus) as any}
              sx={{ ml: 'auto' }}
            />
          </Box>

          <Grid container spacing={3}>
            {/* Overall Status */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'primary.50', borderLeft: 4, borderColor: 'primary.main' }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Overall Status
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  {overallStatus === 'pass' ? (
                    <CheckCircle color="success" />
                  ) : (
                    <Error color="error" />
                  )}
                  <Typography variant="h4">
                    {videosPassed}/{totalVideos}
                  </Typography>
                </Box>
                <Typography variant="body2">
                  Videos Passed
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={totalVideos > 0 ? (videosPassed / totalVideos) * 100 : 0}
                  color={videosPassed === totalVideos && totalVideos > 0 ? 'success' : 'warning'}
                  sx={{ mt: 1 }}
                />
              </Paper>
            </Grid>

            {/* Sequence Duration */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'info.50', borderLeft: 4, borderColor: 'info.main' }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Sequence Duration
                </Typography>
                <Typography variant="h4">
                  {sequenceDurationFormatted}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {sequenceDurationSeconds.toFixed(1)}s total
                </Typography>
              </Paper>
            </Grid>

            {/* Latency Summary */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: (theme) => alpha(theme.palette.success.main, 0.1), borderLeft: 4, borderColor: 'success.main' }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Latency Metrics
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Avg</Typography>
                    <Typography variant="h6">{averageLatencyMs.toFixed(1)}ms</Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Worst</Typography>
                    <Typography variant="h6">{worstLatencyMs.toFixed(1)}ms</Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">Best</Typography>
                    <Typography variant="h6">{bestLatencyMs.toFixed(1)}ms</Typography>
                  </Box>
                </Box>
              </Paper>
            </Grid>

            {/* Detection Summary */}
            <Grid item xs={12}>
              <Alert severity="info" sx={{ display: 'flex', alignItems: 'center' }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Detection Summary
                  </Typography>
                  <Typography variant="body2">
                    <strong>{totalDetectionsSummary}</strong> total detections •{' '}
                    <strong>{totalPassedDetectionsSummary}</strong> passed •{' '}
                    <strong>{totalFailedDetectionsSummary}</strong> failed •{' '}
                    <strong>{overallPassRate.toFixed(1)}%</strong> pass rate
                  </Typography>
                </Box>
                {onExportAll && (
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={onExportAll}
                    sx={{ ml: 2 }}
                  >
                    Export All Results
                  </Button>
                )}
              </Alert>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Video Progression Timeline */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Timeline color="primary" />
            <Typography variant="h6">
              Video Sequence Timeline
            </Typography>
          </Box>
          <Box sx={{ position: 'relative', height: 120, bgcolor: 'grey.50', borderRadius: 1, overflow: 'hidden' }}>
            {/* Timeline background */}
            <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex' }}>
              {videos.map((video, index) => {
                const rawDuration =
                  video.duration_seconds ??
                  video.duration ??
                  (typeof (video.video_end_time ?? video.videoEndTime) === 'number' &&
                  typeof (video.video_start_time ?? video.videoStartTime) === 'number'
                    ? (video.video_end_time ?? video.videoEndTime ?? 0) -
                      (video.video_start_time ?? video.videoStartTime ?? 0)
                    : 0);
                const resolvedDuration = rawDuration && rawDuration > 0 ? rawDuration : 0;
                const explicitStart =
                  video.video_start_time ??
                  video.videoStartTime ??
                  video.start_time ??
                  video.startTime;
                const fallbackStart =
                  index === 0
                    ? 0
                    : videos
                        .slice(0, index)
                        .reduce(
                          (sum, current) =>
                            sum + (current.duration_seconds ?? current.duration ?? 0),
                          0
                        );
                const resolvedStart =
                  typeof explicitStart === 'number' && Number.isFinite(explicitStart)
                    ? explicitStart
                    : fallbackStart;
                const fallbackSegments = videos.length > 0 ? videos.length : 1;
                const startPercent =
                  sequenceDurationSeconds > 0
                    ? (resolvedStart / sequenceDurationSeconds) * 100
                    : (index / fallbackSegments) * 100;
                const widthPercent =
                  sequenceDurationSeconds > 0
                    ? (resolvedDuration / sequenceDurationSeconds) * 100
                    : (1 / fallbackSegments) * 100;
                const status = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending')
                  .toString()
                  .toLowerCase();
                const videoName = video.video_name ?? video.videoName ?? `Video ${index + 1}`;
                const passRate =
                  video.pass_rate ??
                  video.passRate ??
                  video.pass_rate_percent ??
                  video.passRatePercent ??
                  0;
                const durationLabel = video.duration_formatted ?? video.durationFormatted ?? formatDuration(resolvedDuration);
                const videoNumber = video.video_number ?? video.videoNumber ?? index + 1;

                return (
                  <Tooltip
                    key={video.video_id ?? video.videoId ?? index}
                    title={
                      <Box>
                        <Typography variant="body2" fontWeight="bold">{videoName}</Typography>
                        <Typography variant="caption">Duration: {durationLabel}</Typography>
                        <Typography variant="caption" display="block">
                          Status: {status.toUpperCase()} ({Number(passRate).toFixed(1)}% pass rate)
                        </Typography>
                      </Box>
                    }
                  >
                    <Box
                      sx={{
                        position: 'absolute',
                        left: `${startPercent}%`,
                        width: `${widthPercent}%`,
                        height: '100%',
                        bgcolor: status === 'pass'
                          ? (theme) => alpha(theme.palette.success.main, 0.7)
                          : (theme) => alpha(theme.palette.error.main, 0.7),
                        borderRight: index < videos.length - 1 ? '2px solid white' : 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        '&:hover': {
                          opacity: 0.8,
                          transform: 'scaleY(1.05)',
                        }
                      }}
                      onClick={() => handleVideoDetail(video)}
                    >
                      <Typography variant="caption" fontWeight="bold" color="white">
                        #{videoNumber}
                      </Typography>
                      <Typography variant="caption" fontSize={10} color="white">
                        {durationLabel}
                      </Typography>
                    </Box>
                  </Tooltip>
                );
              })}
            </Box>

            {/* Time markers */}
            <Box sx={{ position: 'absolute', bottom: -20, left: 0, right: 0, display: 'flex', justifyContent: 'space-between', px: 1 }}>
              <Typography variant="caption" color="text.secondary">0:00</Typography>
              <Typography variant="caption" color="text.secondary">
                {sequenceDurationFormatted}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Per-Video Results Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Per-Video Results
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell />
                  <TableCell>Video #</TableCell>
                  <TableCell>Video Name</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Duration</TableCell>
                  <TableCell>Detections</TableCell>
                  <TableCell>Pass/Fail</TableCell>
                  <TableCell>Avg Latency</TableCell>
                  <TableCell>Max Latency</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {videos.map((video, index) => {
                  const videoId = (video.video_id ?? video.videoId ?? `video-${index}`).toString();
                  const status = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending')
                    .toString()
                    .toLowerCase();
                  const videoNumber = video.video_number ?? video.videoNumber ?? index + 1;
                  const videoName = video.video_name ?? video.videoName ?? `Video ${videoNumber}`;
                  const durationSeconds =
                    video.duration_seconds ?? video.duration ?? 0;
                  const durationLabel =
                    video.duration_formatted ?? video.durationFormatted ?? formatDuration(durationSeconds);
                  const totalDetections =
                    video.total_detections ?? video.totalDetections ?? video.detection_count ?? 0;
                  const passRateValueBase =
                    video.pass_rate ??
                    video.passRate ??
                    video.pass_rate_percent ??
                    video.passRatePercent ??
                    undefined;
                  const passedDetections =
                    video.passed_detections ??
                    video.passedDetections ??
                    (totalDetections > 0 && passRateValueBase !== undefined
                      ? Math.round((Number(passRateValueBase) / 100) * totalDetections)
                      : 0);
                  const passRateValue =
                    passRateValueBase ??
                    (totalDetections > 0 ? (passedDetections / totalDetections) * 100 : 0);
                  const failedDetections =
                    video.failed_detections ??
                    video.failedDetections ??
                    Math.max(totalDetections - passedDetections, 0);
                  const avgLatency = video.average_latency_ms ?? video.averageLatencyMs ?? 0;
                  const maxLatency = video.max_latency_ms ?? video.maxLatencyMs ?? 0;
                  const latencyThreshold = video.latency_threshold_ms ?? video.latencyThresholdMs ?? undefined;
                  const detectionEvents = video.detection_events ?? video.detectionEvents ?? [];

                  return (
                  <React.Fragment key={videoId}>
                    {/* Main Row */}
                    <TableRow
                      sx={{
                        bgcolor: (theme) => {
                          if (status === 'pass') {
                            return alpha(theme.palette.success.main, 0.1);
                          }
                          if (status === 'fail') {
                            return alpha(theme.palette.error.main, 0.1);
                          }
                          return alpha(theme.palette.warning.main, 0.1);
                        },
                        '&:hover': {
                          bgcolor: (theme) => {
                            if (status === 'pass') {
                              return alpha(theme.palette.success.main, 0.2);
                            }
                            if (status === 'fail') {
                              return alpha(theme.palette.error.main, 0.2);
                            }
                            return alpha(theme.palette.warning.main, 0.2);
                          }
                        }
                      }}
                    >
                      <TableCell>
                        <IconButton
                          size="small"
                          onClick={() => handleRowToggle(videoId)}
                        >
                          {expandedRows.has(videoId) ? <ExpandLess /> : <ExpandMore />}
                        </IconButton>
                      </TableCell>
                      <TableCell>
                        <Chip label={`#${videoNumber}`} size="small" color="primary" />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <VideoFile fontSize="small" />
                          <Tooltip title={videoName}>
                            <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                              {videoName}
                            </Typography>
                          </Tooltip>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          icon={status === 'pass' ? <CheckCircle /> : <Error />}
                          label={status.toUpperCase()}
                          color={
                            status === 'pass'
                              ? getStatusColor('pass') as any
                              : status === 'fail'
                                ? getStatusColor('fail') as any
                                : 'warning'
                          }
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {durationLabel}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          ({durationSeconds.toFixed(1)}s)
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="bold">
                          {totalDetections}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box>
                          <Chip
                            label={`${passedDetections} pass`}
                            size="small"
                            color="success"
                            variant="outlined"
                            sx={{ mr: 0.5, mb: 0.5 }}
                          />
                          <Chip
                            label={`${failedDetections} fail`}
                            size="small"
                            color="error"
                            variant="outlined"
                          />
                          <Typography variant="caption" display="block" color="text.secondary">
                            {Number(passRateValue).toFixed(1)}% pass rate
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {avgLatency.toFixed(1)}ms
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          color={
                            latencyThreshold !== undefined && maxLatency > latencyThreshold
                              ? 'error'
                              : 'text.primary'
                          }
                        >
                          {maxLatency.toFixed(1)}ms
                        </Typography>
                        {latencyThreshold !== undefined && maxLatency > latencyThreshold && (
                          <Chip label="Exceeded" color="error" size="small" sx={{ mt: 0.5 }} />
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => handleVideoDetail(video)}
                        >
                          Details
                        </Button>
                      </TableCell>
                    </TableRow>

                    {/* Expandable Row - Detection Events */}
                    <TableRow>
                      <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={10}>
                        <Collapse in={expandedRows.has(videoId)} timeout="auto" unmountOnExit>
                          <Box sx={{ margin: 2 }}>
                            <Typography variant="subtitle2" gutterBottom>
                              Detection Events ({detectionEvents.length})
                            </Typography>
                            <Table size="small">
                              <TableHead>
                                <TableRow>
                                  <TableCell>Relative Time (s)</TableCell>
                                  <TableCell>Absolute Time (s)</TableCell>
                                  <TableCell>Latency (ms)</TableCell>
                                  <TableCell>Signal</TableCell>
                                  <TableCell>Status</TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {detectionEvents.slice(0, 10).map((event) => {
                                  const relativeTime =
                                    event.video_relative_timestamp ??
                                    event.videoRelativeTimestamp ??
                                    null;
                                  const absoluteTime =
                                    event.timestamp ??
                                    event.time ??
                                    null;
                                  const latencyValue =
                                    event.actualLatencyMs ??
                                    event.actual_latency_ms ??
                                    event.real_latency_ms ??
                                    event.latency_ms ??
                                    null;
                                  const voltageValue =
                                    event.voltage ??
                                    event.voltage_level ??
                                    event.signal_value ??
                                    event.signalValue ??
                                    null;
                                  const signalType = event.signal_type ?? event.signalType ?? null;
                                  const channelInfo = event.channel ?? event.channel_name ?? event.channelName ?? null;
                                  const baseSignalLabel = [signalType, channelInfo].filter(Boolean).join(' / ');
                                  const valueLabel =
                                    voltageValue !== null
                                      ? `${Number(voltageValue).toFixed(2)} V`
                                      : event.signal_value ?? event.signalValue ?? '—';
                                  const signalLabel =
                                    baseSignalLabel
                                      ? valueLabel !== '—'
                                        ? `${baseSignalLabel} (${valueLabel})`
                                        : baseSignalLabel
                                      : valueLabel !== '—'
                                        ? valueLabel
                                        : '—';
                                  const passed =
                                    typeof event.passed === 'boolean'
                                      ? event.passed
                                      : (event.result ?? event.validation_result ?? '').toString().toLowerCase() === 'pass'
                                        ? true
                                        : (event.result ?? event.validation_result ?? '').toString().toLowerCase() === 'fail'
                                          ? false
                                          : undefined;

                                  return (
                                    <TableRow key={event.id ?? `${absoluteTime}-${relativeTime}`}>
                                      <TableCell>
                                        {relativeTime !== null ? Number(relativeTime).toFixed(3) : '—'}
                                      </TableCell>
                                      <TableCell>
                                        {absoluteTime !== null ? Number(absoluteTime).toFixed(3) : '—'}
                                      </TableCell>
                                      <TableCell>
                                        {latencyValue !== null ? Number(latencyValue).toFixed(1) : '—'}
                                      </TableCell>
                                      <TableCell>{signalLabel}</TableCell>
                                      <TableCell>
                                        {passed === undefined ? (
                                          <Chip label="—" size="small" color="default" />
                                        ) : (
                                          <Chip
                                            label={passed ? 'PASS' : 'FAIL'}
                                            size="small"
                                            color={passed ? 'success' : 'error'}
                                          />
                                        )}
                                      </TableCell>
                                    </TableRow>
                                  );
                                })}
                                {detectionEvents.length > 10 && (
                                  <TableRow>
                                    <TableCell colSpan={5} align="center">
                                      <Typography variant="caption" color="text.secondary">
                                        Showing 10 of {detectionEvents.length} events. Click "Details" for full view.
                                      </Typography>
                                    </TableCell>
                                  </TableRow>
                                )}
                              </TableBody>
                            </Table>
                          </Box>
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Video Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        {selectedVideo && selectedVideoDetails && (
          <>
            <DialogTitle>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <VideoFile />
                <Typography variant="h6">
                  Video #{selectedVideoDetails.number || '—'}: {selectedVideoDetails.name}
                </Typography>
                <Chip
                  label={selectedVideoDetails.status.toUpperCase()}
                  color={
                    selectedVideoDetails.status === 'pass'
                      ? getStatusColor('pass') as any
                      : selectedVideoDetails.status === 'fail'
                        ? getStatusColor('fail') as any
                        : 'warning'
                  }
                  sx={{ ml: 'auto' }}
                />
              </Box>
            </DialogTitle>
            <DialogContent dividers>
              {/* Video Metrics */}
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">Duration</Typography>
                    <Typography variant="h6">{selectedVideoDetails.durationLabel}</Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">Detections</Typography>
                    <Typography variant="h6">{selectedVideoDetails.totalDetections}</Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">Pass Rate</Typography>
                    <Typography variant="h6">{Number(selectedVideoDetails.passRate).toFixed(1)}%</Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper sx={{ p: 2, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">Avg Latency</Typography>
                    <Typography variant="h6">{selectedVideoDetails.avgLatency.toFixed(1)}ms</Typography>
                  </Paper>
                </Grid>
              </Grid>

              {/* Frame Correlation Timeline for this video */}
              <FrameCorrelationTimeline
                detectionEvents={selectedVideo.detection_events ?? selectedVideo.detectionEvents ?? []}
                groundTruthEvents={groundTruthEvents.filter(gt => {
                  // Filter ground truth events by this video's time window
                  const gtTime = gt.timestamp;
                  const startTime = selectedVideoDetails.startTime ?? 0;
                  const endTime = selectedVideoDetails.endTime ?? startTime;
                  return gtTime >= startTime && gtTime <= endTime;
                })}
                videoMetadata={{
                  fps: selectedVideoDetails.fps,
                  duration: selectedVideoDetails.durationSeconds,
                  filename: selectedVideoDetails.name
                }}
                showFrameNumbers={true}
                showLatencyInfo={true}
                highlightMisalignments={true}
              />
            </DialogContent>
            <DialogActions>
              {selectedVideoDetails.videoUrl && (
                <Button
                  variant="outlined"
                  onClick={() => window.open(selectedVideoDetails.videoUrl as string, '_blank', 'noopener')}
                >
                  Open Video
                </Button>
              )}
              {onExportVideo && (selectedVideo.video_id ?? selectedVideo.videoId) && (
                <Button onClick={() => onExportVideo((selectedVideo.video_id ?? selectedVideo.videoId) as string)}>
                  Export Results
                </Button>
              )}
              <Button onClick={() => setDetailDialogOpen(false)}>
                Close
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
};

export default VideoSequenceResultsComponent;
