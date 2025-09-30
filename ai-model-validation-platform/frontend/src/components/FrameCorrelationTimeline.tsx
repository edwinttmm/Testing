import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Alert,
  Tooltip,
  LinearProgress
} from '@mui/material';
import {
  CheckCircle,
  Error,
  Warning,
  Timeline,
  VideoFile,
  Speed,
  AccessTime,
  Stop,
  PlayDisabled
} from '@mui/icons-material';

interface FrameCorrelationEvent {
  id: string;
  type: 'detection' | 'ground_truth';
  timestamp: number;
  frame_number: number;
  video_frame_number?: number;
  confidence?: number;
  // Latency relative to nearest ground truth (signed ms; positive means after GT)
  latency_ms?: number;
  // Hardware/processing latency reported by backend (kept for reference)
  real_latency_ms?: number;
  voltage?: number;
  channel?: string;
  label?: string;
  passed?: boolean;
  correlation_status?: 'aligned' | 'misaligned' | 'missing' | 'video_ended';
  frame_offset_ms?: number;
}

interface FrameCorrelationTimelineProps {
  detectionEvents: any[];
  groundTruthEvents: any[];
  videoMetadata: {
    fps?: number;
    duration?: number;
    filename?: string;
  };
  onEventSelect?: (event: FrameCorrelationEvent) => void;
  showFrameNumbers?: boolean;
  showLatencyInfo?: boolean;
  highlightMisalignments?: boolean;
}

const FrameCorrelationTimeline: React.FC<FrameCorrelationTimelineProps> = ({
  detectionEvents = [],
  groundTruthEvents = [],
  videoMetadata,
  onEventSelect,
  showFrameNumbers = true,
  showLatencyInfo = true,
  highlightMisalignments = true
}) => {
  const fps = videoMetadata?.fps || 24;
  const duration = videoMetadata?.duration ?? undefined;
  const totalFrames = typeof duration === 'number' && Number.isFinite(duration) ? Math.max(0, Math.round(duration * fps)) : undefined;

  // Helper to clamp a frame number into valid video range if duration is known.
  const clampFrame = (frame: number): number => {
    if (!Number.isFinite(frame)) return 0;
    if (totalFrames == null) return Math.max(0, Math.floor(frame));
    return Math.min(Math.max(0, Math.floor(frame)), Math.max(0, totalFrames - 1));
  };
  
  // Process and correlate events
  const correlatedEvents = useMemo(() => {
    const events: FrameCorrelationEvent[] = [];
    
    // Calculate last detection timestamp for boundary detection
    const lastDetectionTime = detectionEvents.length > 0 ? 
      Math.max(...detectionEvents.map(d => {
        const frameNumRaw = d.video_frame_number ?? d.frame_number ?? 0;
        const frameNum = clampFrame(Number(frameNumRaw));
        // Prefer video-derived time; ignore absolute epoch timestamps
        const rel = frameNum > 0 ? (frameNum / fps) : 0;
        return rel;
      })) : 0;
    const videoEndMargin = 0.5; // 500ms grace period after last detection
    
    // Add ground truth events with boundary detection
    groundTruthEvents.forEach((gt: any) => {
      const gtFrameRaw = gt.video_frame ?? gt.frame_number ?? 0;
      const gtFrameNumber = clampFrame(Number(gtFrameRaw));
      // Prefer frame-derived time to avoid epoch seconds leaking in
      const gtTimeSeconds = gtFrameNumber > 0 ? (gtFrameNumber / fps) : (Number(gt.timestamp) || 0);
      
      // Determine if this ground truth is beyond monitoring boundary
      let gtCorrelationStatus: 'aligned' | 'video_ended' = 'aligned';
      
      // If ground truth is beyond last detection time + margin, mark as video_ended
      if (gtTimeSeconds > (lastDetectionTime + videoEndMargin)) {
        gtCorrelationStatus = 'video_ended';
      }
      
      events.push({
        id: `gt-${gt.id || Math.random()}`,
        type: 'ground_truth',
        timestamp: gtTimeSeconds,
        frame_number: gtFrameNumber,
        confidence: gt.confidence || 1.0,
        label: gt.class_label || 'pedestrian',
        correlation_status: gtCorrelationStatus
      });
    });
    
    // Add detection events with correlation analysis
    detectionEvents.forEach((det: any) => {
      const detectionFrameNumber = clampFrame(Number(det.video_frame_number ?? det.frame_number ?? 0));
      const videoTimeSeconds = detectionFrameNumber > 0 ? (detectionFrameNumber / fps) : 0;
      
      // Find closest ground truth event for correlation
      let closestGT = null;
      let minTimeDiff = Infinity;
      
      groundTruthEvents.forEach((gt: any) => {
        const gtFrame = gt.video_frame || gt.frame_number || 0;
        const frameDiff = Math.abs(detectionFrameNumber - gtFrame);
        const timeDiff = Math.abs(videoTimeSeconds - (gt.timestamp || 0));
        
        if (timeDiff < minTimeDiff) {
          minTimeDiff = timeDiff;
          closestGT = gt;
        }
      });
      
      // Determine correlation status
      let correlationStatus: 'aligned' | 'misaligned' | 'missing' | 'video_ended' = 'missing';
      let frameOffsetMs = 0;
      let gtLatencyMs: number | undefined = undefined; // signed Δ vs nearest GT
      
      if (closestGT) {
        const closestGTFrame = clampFrame(Number(closestGT.video_frame ?? closestGT.frame_number ?? 0));
        const closestGTTimeSec = closestGTFrame > 0 ? (closestGTFrame / fps) : (Number(closestGT.timestamp) || 0);
        const frameOffsetFrames = Math.abs(detectionFrameNumber - closestGTFrame);
        frameOffsetMs = (frameOffsetFrames / fps) * 1000;
        // Signed latency from GT to detection in ms
        gtLatencyMs = (videoTimeSeconds - closestGTTimeSec) * 1000;
        
        if (frameOffsetMs <= (1000 / fps) * 2) { // Within 2 frames
          correlationStatus = 'aligned';
        } else if (frameOffsetMs <= (1000 / fps) * 5) { // Within 5 frames
          correlationStatus = 'misaligned';
        } else {
          correlationStatus = 'missing';
        }
      }
      
      events.push({
        id: `det-${det.id || det.event_id || Math.random()}`,
        type: 'detection',
        // Always use video-relative seconds to keep a consistent timebase
        timestamp: videoTimeSeconds,
        frame_number: detectionFrameNumber,
        video_frame_number: detectionFrameNumber,
        confidence: det.confidence || 0.8,
        // Show latency relative to nearest GT in this visualization
        latency_ms: gtLatencyMs,
        // Preserve backend-reported real latency for reference/tooltips
        real_latency_ms: det.real_latency_ms || det.detection_time_ms || det.corrected_latency?.real_latency_ms,
        voltage: det.voltage || det.voltage_level,
        channel: det.channel || 'AIN0',
        passed: det.passed || det.validation_result === 'PASS',
        correlation_status: correlationStatus,
        frame_offset_ms: frameOffsetMs
      });
    });
    
    // Sort by timestamp
    return events.sort((a, b) => a.timestamp - b.timestamp);
  }, [detectionEvents, groundTruthEvents, fps]);
  
  // Calculate last detection time for UI display
  const lastDetectionTime = useMemo(() => {
    return detectionEvents.length > 0 ? 
      Math.max(...detectionEvents.map(d => {
        const frameNum = d.video_frame_number || d.frame_number || 0;
        return d.timestamp || (frameNum / fps);
      })) : 0;
  }, [detectionEvents, fps]);
  
  // Calculate correlation statistics
  const correlationStats = useMemo(() => {
    const detections = correlatedEvents.filter(e => e.type === 'detection');
    const groundTruths = correlatedEvents.filter(e => e.type === 'ground_truth');
    const aligned = detections.filter(e => e.correlation_status === 'aligned').length;
    const misaligned = detections.filter(e => e.correlation_status === 'misaligned').length;
    const missing = detections.filter(e => e.correlation_status === 'missing').length;
    const videoEnded = groundTruths.filter(e => e.correlation_status === 'video_ended').length;
    
    // Calculate alignment rate based on monitored period only (exclude video_ended)
    const monitoredGroundTruths = groundTruths.filter(e => e.correlation_status !== 'video_ended').length;
    
    return {
      total: detections.length,
      totalGroundTruth: groundTruths.length,
      monitoredGroundTruth: monitoredGroundTruths,
      aligned,
      misaligned,
      missing,
      videoEnded,
      alignmentRate: detections.length > 0 ? (aligned / detections.length) * 100 : 0,
      monitoredCoverage: monitoredGroundTruths > 0 ? (aligned / monitoredGroundTruths) * 100 : 0
    };
  }, [correlatedEvents]);
  
  const getCorrelationColor = (status: string) => {
    switch (status) {
      case 'aligned': return 'success';
      case 'misaligned': return 'warning';
      case 'missing': return 'error';
      case 'video_ended': return 'info';
      default: return 'default';
    }
  };
  
  const getCorrelationIcon = (status: string) => {
    switch (status) {
      case 'aligned': return <CheckCircle />;
      case 'misaligned': return <Warning />;
      case 'missing': return <Error />;
      case 'video_ended': return <PlayDisabled />;
      default: return <Timeline />;
    }
  };
  
  const formatFrameTime = (frameNumber: number) => {
    const timeSeconds = frameNumber / fps;
    return `${timeSeconds.toFixed(3)}s`;
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Timeline color="primary" />
          <Typography variant="h6">
            Frame Correlation Timeline
          </Typography>
          <Chip 
            label={`${correlatedEvents.length} events`} 
            size="small" 
            color="primary" 
          />
        </Box>
        
        {/* Correlation Statistics */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={6}>
            <Box sx={{ p: 2, bgcolor: 'info.50', borderRadius: 1 }}>
              <Typography variant="subtitle2" gutterBottom>
                Frame Alignment Statistics
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                <Chip 
                  label={`${correlationStats.aligned} Aligned`} 
                  color="success" 
                  size="small" 
                />
                <Chip 
                  label={`${correlationStats.misaligned} Misaligned`} 
                  color="warning" 
                  size="small" 
                />
                <Chip 
                  label={`${correlationStats.missing} Missing`} 
                  color="error" 
                  size="small" 
                />
                <Chip 
                  label={`${correlationStats.videoEnded} Video Ended`} 
                  color="info" 
                  size="small" 
                />
              </Box>
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Alignment Rate: {correlationStats.alignmentRate.toFixed(1)}% • 
                  Monitored Coverage: {correlationStats.monitoredCoverage.toFixed(1)}%
                </Typography>
                <LinearProgress 
                  variant="determinate" 
                  value={correlationStats.alignmentRate} 
                  color={correlationStats.alignmentRate >= 80 ? 'success' : correlationStats.alignmentRate >= 60 ? 'warning' : 'error'}
                  sx={{ mt: 0.5 }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                  {correlationStats.monitoredGroundTruth} monitored events • {correlationStats.videoEnded} beyond monitoring boundary
                </Typography>
              </Box>
            </Box>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Box sx={{ p: 2, bgcolor: 'success.50', borderRadius: 1 }}>
              <Typography variant="subtitle2" gutterBottom>
                Video Metadata
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <VideoFile fontSize="small" />
                <Typography variant="body2">
                  {videoMetadata.filename || 'Unknown file'}
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary">
                FPS: {fps} • Duration: {videoMetadata.duration?.toFixed(2)}s
              </Typography>
            </Box>
          </Grid>
        </Grid>
        
        {/* Alert for alignment issues */}
        {correlationStats.alignmentRate < 80 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Frame Alignment Issues Detected</Typography>
            <Typography variant="body2">
              {correlationStats.misaligned + correlationStats.missing} out of {correlationStats.total} detections 
              are not properly aligned with ground truth events. This may indicate timing synchronization issues.
            </Typography>
          </Alert>
        )}
        
        {/* Alert for video boundary detection */}
        {correlationStats.videoEnded > 0 && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Video Boundary Detection</Typography>
            <Typography variant="body2">
              {correlationStats.videoEnded} ground truth events were detected beyond the monitoring boundary 
              (after the last detection at {lastDetectionTime > 0 ? `${lastDetectionTime.toFixed(3)}s` : 'unknown time'}). 
              These represent video content that wasn't monitored by the detection system.
            </Typography>
          </Alert>
        )}
        
        {/* Event Timeline Table */}
        <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 600 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell>Frame Info</TableCell>
                <TableCell>Video Time</TableCell>
                <TableCell>Correlation</TableCell>
                {showLatencyInfo && <TableCell>Latency</TableCell>}
                <TableCell>Details</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {correlatedEvents.map((event, index) => (
                <TableRow 
                  key={event.id}
                  onClick={() => onEventSelect?.(event)}
                  sx={{ 
                    cursor: onEventSelect ? 'pointer' : 'default',
                    '&:hover': onEventSelect ? { bgcolor: 'action.hover' } : {},
                    bgcolor: event.correlation_status === 'video_ended' ? 'info.50' :
                            event.type === 'ground_truth' ? 'warning.50' : 
                            event.correlation_status === 'misaligned' && highlightMisalignments ? 'error.50' : 
                            undefined
                  }}
                >
                  <TableCell>
                    <Chip 
                      label={event.type === 'ground_truth' ? 
                        (event.correlation_status === 'video_ended' ? 'GT (Video Ended)' : 'GT') : 
                        'Detection'
                      } 
                      color={event.correlation_status === 'video_ended' ? 'info' : 
                            event.type === 'ground_truth' ? 'warning' : 'primary'}
                      size="small"
                    />
                  </TableCell>
                  
                  <TableCell>
                    <Box>
                      <Typography variant="body2" fontWeight="bold">
                        Frame {event.frame_number}
                      </Typography>
                      {event.video_frame_number && event.video_frame_number !== event.frame_number && (
                        <Typography variant="caption" color="text.secondary">
                          Video: F{event.video_frame_number}
                        </Typography>
                      )}
                    </Box>
                  </TableCell>
                  
                  <TableCell>
                    <Typography variant="body2">
                      {formatFrameTime(event.frame_number)}
                    </Typography>
                  </TableCell>
                  
                  <TableCell>
                    {(event.type === 'detection' || event.correlation_status === 'video_ended') && (
                      <Tooltip title={
                        event.correlation_status === 'video_ended' ? 
                          'Ground truth beyond monitoring boundary' :
                          `Frame offset: ${event.frame_offset_ms?.toFixed(1)}ms`
                      }>
                        <Chip 
                          icon={getCorrelationIcon(event.correlation_status || 'missing')}
                          label={event.correlation_status === 'video_ended' ? 'Video Ended' : event.correlation_status}
                          color={getCorrelationColor(event.correlation_status || 'missing') as any}
                          size="small"
                          variant={event.correlation_status === 'video_ended' ? 'filled' : 'outlined'}
                        />
                      </Tooltip>
                    )}
                  </TableCell>
                  
                  {showLatencyInfo && (
                    <TableCell>
                  {(event.latency_ms !== undefined || event.real_latency_ms !== undefined) && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AccessTime fontSize="small" />
                      <Typography variant="body2">
                            {event.latency_ms !== undefined ? `${event.latency_ms.toFixed(1)}ms` : '—'}
                      </Typography>
                      {event.real_latency_ms !== undefined && (
                        <Tooltip title={`Hardware/processing latency: ${event.real_latency_ms.toFixed(1)}ms`}>
                          <Chip label={`real ${event.real_latency_ms.toFixed(0)}ms`} size="small" variant="outlined" />
                        </Tooltip>
                      )}
                      {event.passed === false && (
                        <Chip label="FAIL" color="error" size="small" />
                      )}
                    </Box>
                  )}
                    </TableCell>
                  )}
                  
                  <TableCell>
                    <Box>
                      {event.type === 'ground_truth' ? (
                        <Typography variant="body2">
                          {event.label} • {(event.confidence! * 100).toFixed(1)}%
                        </Typography>
                      ) : (
                        <Typography variant="body2">
                          {event.voltage?.toFixed(2)}V ({event.channel})
                        </Typography>
                      )}
                    </Box>
                  </TableCell>
                  
                  <TableCell>
                    {event.type === 'detection' && (
                      <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                        {(() => {
                          const toleranceMs = (2 / fps) * 1000; // ±2 frames
                          const gtPass = typeof event.latency_ms === 'number' && Math.abs(event.latency_ms) <= toleranceMs;
                          return (
                            <Chip
                              label={gtPass ? 'GT PASS' : 'GT FAIL'}
                              color={gtPass ? 'success' : 'error'}
                              size="small"
                            />
                          );
                        })()}
                        {typeof event.passed === 'boolean' && (
                          <Tooltip title="Threshold status from backend (e.g., 100ms limit, voltage)">
                            <Chip
                              label={event.passed ? 'thr PASS' : 'thr FAIL'}
                              color={event.passed ? 'success' : 'error'}
                              size="small"
                              variant="outlined"
                            />
                          </Tooltip>
                        )}
                      </Box>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              
              {correlatedEvents.length === 0 && (
                <TableRow>
                  <TableCell colSpan={showLatencyInfo ? 7 : 6} align="center">
                    <Typography color="text.secondary">
                      No correlation data available
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        
        {/* Summary Information */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Frame correlation analysis: Detections are matched to ground truth events within a ±2 frame tolerance ({((2 / fps) * 1000).toFixed(1)}ms at {fps}fps).
            Misaligned events may indicate timing synchronization issues. "Video Ended" events represent ground truth 
            beyond the monitoring boundary (>{lastDetectionTime.toFixed(3)}s + 0.5s margin) and are excluded from alignment statistics.
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default FrameCorrelationTimeline;
