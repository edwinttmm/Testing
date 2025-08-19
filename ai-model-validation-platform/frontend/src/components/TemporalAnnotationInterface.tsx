import React, { useState, useCallback, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Slider,
  IconButton,
  Button,
  Stack,
  Chip,
  Tooltip,
  TextField,
  Card,
  CardContent,
  Divider,
  Alert,
  Badge,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  FirstPage,
  LastPage,
  Timeline,
  Add,
  Delete,
  Visibility,
  VisibilityOff,
  KeyboardArrowLeft,
  KeyboardArrowRight,
} from '@mui/icons-material';
import { VRUType, GroundTruthAnnotation } from '../services/types';
import { generateDetectionId } from '../utils/detectionIdManager';

interface TemporalAnnotationInterfaceProps {
  annotations: GroundTruthAnnotation[];
  currentFrame: number;
  totalFrames: number;
  frameRate: number;
  duration: number;
  onFrameChange: (frame: number) => void;
  onAnnotationCreate: (annotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'>) => void;
  onAnnotationUpdate: (id: string, updates: Partial<GroundTruthAnnotation>) => void;
  onAnnotationDelete: (id: string) => void;
  onPlay?: () => void;
  onPause?: () => void;
  isPlaying?: boolean;
  selectedVRUType: VRUType;
}

// TODO: Implement keyframe annotations
// interface AnnotationKeyframe {
//   frame: number;
//   timestamp: number;
//   annotations: GroundTruthAnnotation[];
// }

interface TemporalRange {
  start: number;
  end: number;
  vruType: VRUType;
  detectionId: string;
}

const TemporalAnnotationInterface: React.FC<TemporalAnnotationInterfaceProps> = ({
  annotations,
  currentFrame,
  totalFrames,
  frameRate,
  duration,
  onFrameChange,
  onAnnotationCreate,
  onAnnotationUpdate,
  onAnnotationDelete,
  onPlay,
  onPause,
  isPlaying = false,
  selectedVRUType,
}) => {
  const [selectedRange, setSelectedRange] = useState<TemporalRange | null>(null);
  const [showAllAnnotations, setShowAllAnnotations] = useState(true);
  // TODO: Implement playback speed control
  // const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [annotationMode, setAnnotationMode] = useState<'single' | 'temporal' | 'track'>('single');
  const [trackingDetectionId, setTrackingDetectionId] = useState<string | null>(null);

  // Calculate keyframes - frames that have annotations
  const keyframes = useMemo(() => {
    const frameMap = new Map<number, GroundTruthAnnotation[]>();
    
    annotations.forEach(annotation => {
      const frame = annotation.frameNumber;
      if (!frameMap.has(frame)) {
        frameMap.set(frame, []);
      }
      frameMap.get(frame)!.push(annotation);
    });

    return Array.from(frameMap.entries())
      .map(([frame, annotations]) => ({
        frame,
        timestamp: frame / frameRate,
        annotations,
      }))
      .sort((a, b) => a.frame - b.frame);
  }, [annotations, frameRate]);

  // Calculate temporal ranges - continuous annotations for same detection ID
  const temporalRanges = useMemo(() => {
    const rangeMap = new Map<string, { frames: number[]; vruType: VRUType }>();
    
    annotations.forEach(annotation => {
      const detectionId = annotation.detectionId;
      if (!rangeMap.has(detectionId)) {
        rangeMap.set(detectionId, { frames: [], vruType: annotation.vruType });
      }
      rangeMap.get(detectionId)!.frames.push(annotation.frameNumber);
    });

    return Array.from(rangeMap.entries()).map(([detectionId, data]) => {
      const sortedFrames = data.frames.sort((a, b) => a - b);
      return {
        detectionId,
        vruType: data.vruType,
        start: sortedFrames[0],
        end: sortedFrames[sortedFrames.length - 1],
      } as TemporalRange;
    });
  }, [annotations]);

  // Get annotations for current frame
  const currentAnnotations = annotations.filter(
    annotation => annotation.frameNumber === currentFrame
  );

  // Convert frame to timestamp
  const frameToTimestamp = useCallback((frame: number) => frame / frameRate, [frameRate]);
  
  // Convert timestamp to frame
  // TODO: Implement timestamp to frame conversion utility
  // const timestampToFrame = useCallback((timestamp: number) => Math.round(timestamp * frameRate), [frameRate]);

  // Format time display
  const formatTime = useCallback((seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const centiseconds = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${centiseconds.toString().padStart(2, '0')}`;
  }, []);

  // Navigation functions
  const goToFrame = useCallback((frame: number) => {
    const clampedFrame = Math.max(0, Math.min(frame, totalFrames - 1));
    onFrameChange(clampedFrame);
  }, [totalFrames, onFrameChange]);

  const goToNextKeyframe = useCallback(() => {
    const nextKeyframe = keyframes.find(kf => kf.frame > currentFrame);
    if (nextKeyframe) {
      goToFrame(nextKeyframe.frame);
    }
  }, [keyframes, currentFrame, goToFrame]);

  const goToPreviousKeyframe = useCallback(() => {
    const prevKeyframe = keyframes
      .slice()
      .reverse()
      .find(kf => kf.frame < currentFrame);
    if (prevKeyframe) {
      goToFrame(prevKeyframe.frame);
    }
  }, [keyframes, currentFrame, goToFrame]);

  const stepFrame = useCallback((direction: 'forward' | 'backward') => {
    const step = direction === 'forward' ? 1 : -1;
    goToFrame(currentFrame + step);
  }, [currentFrame, goToFrame]);

  // Annotation functions
  const startTracking = useCallback((vruType: VRUType) => {
    const detectionId = generateDetectionId(vruType, currentFrame);
    setTrackingDetectionId(detectionId);
    setAnnotationMode('track');
  }, [currentFrame]);

  const stopTracking = useCallback(() => {
    setTrackingDetectionId(null);
    setAnnotationMode('single');
  }, []);

  const createTemporalAnnotation = useCallback((startFrame: number, endFrame: number) => {
    const detectionId = generateDetectionId(selectedVRUType, startFrame);
    
    // Create annotations for each frame in range
    for (let frame = startFrame; frame <= endFrame; frame++) {
      onAnnotationCreate({
        videoId: '', // Will be set by parent
        detectionId,
        frameNumber: frame,
        timestamp: frameToTimestamp(frame),
        vruType: selectedVRUType,
        boundingBox: { x: 100, y: 100, width: 50, height: 100, label: selectedVRUType, confidence: 1.0 },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
      });
    }
  }, [selectedVRUType, frameToTimestamp, onAnnotationCreate]);

  // Slider marks for keyframes
  const sliderMarks = keyframes.map(kf => ({
    value: kf.frame,
    label: kf.annotations.length.toString(),
  }));

  // Get color for VRU type
  const getVRUColor = (vruType: VRUType): string => {
    const colors = {
      pedestrian: '#2196f3',
      cyclist: '#4caf50',
      motorcyclist: '#ff9800',
      wheelchair_user: '#9c27b0',
      scooter_rider: '#ff5722',
    };
    return colors[vruType] || '#607d8b';
  };

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        Temporal Annotation Timeline
      </Typography>

      {/* Main Timeline Slider */}
      <Box sx={{ mb: 3 }}>
        <Slider
          value={currentFrame}
          min={0}
          max={totalFrames - 1}
          onChange={(_, value) => goToFrame(value as number)}
          marks={sliderMarks.length < 50 ? sliderMarks : []}
          sx={{ mb: 1 }}
        />
        
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="caption">
            Frame: {currentFrame} / {totalFrames - 1}
          </Typography>
          <Typography variant="caption">
            Time: {formatTime(frameToTimestamp(currentFrame))} / {formatTime(duration)}
          </Typography>
        </Stack>
      </Box>

      {/* Control Buttons */}
      <Stack direction="row" spacing={1} justifyContent="center" alignItems="center" sx={{ mb: 2 }}>
        <Tooltip title="First Frame">
          <IconButton onClick={() => goToFrame(0)} size="small">
            <FirstPage />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Previous Keyframe">
          <IconButton onClick={goToPreviousKeyframe} size="small">
            <SkipPrevious />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Previous Frame">
          <IconButton onClick={() => stepFrame('backward')} size="small">
            <KeyboardArrowLeft />
          </IconButton>
        </Tooltip>
        
        <Tooltip title={isPlaying ? 'Pause' : 'Play'}>
          <IconButton
            onClick={isPlaying ? onPause : onPlay}
            color="primary"
          >
            {isPlaying ? <Pause /> : <PlayArrow />}
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Next Frame">
          <IconButton onClick={() => stepFrame('forward')} size="small">
            <KeyboardArrowRight />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Next Keyframe">
          <IconButton onClick={goToNextKeyframe} size="small">
            <SkipNext />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Last Frame">
          <IconButton onClick={() => goToFrame(totalFrames - 1)} size="small">
            <LastPage />
          </IconButton>
        </Tooltip>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* Annotation Mode Selection */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Annotation Mode
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button
            variant={annotationMode === 'single' ? 'contained' : 'outlined'}
            size="small"
            onClick={() => setAnnotationMode('single')}
          >
            Single Frame
          </Button>
          <Button
            variant={annotationMode === 'temporal' ? 'contained' : 'outlined'}
            size="small"
            onClick={() => setAnnotationMode('temporal')}
          >
            Temporal Range
          </Button>
          <Button
            variant={annotationMode === 'track' ? 'contained' : 'outlined'}
            size="small"
            onClick={() => setAnnotationMode('track')}
            startIcon={<Timeline />}
          >
            Track Object
          </Button>
        </Stack>
      </Box>

      {/* Tracking Controls */}
      {annotationMode === 'track' && (
        <Box sx={{ mb: 2, p: 2, bgcolor: 'primary.light', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Object Tracking
          </Typography>
          {trackingDetectionId ? (
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="body2">
                Tracking: {trackingDetectionId}
              </Typography>
              <Button
                variant="contained"
                color="secondary"
                size="small"
                onClick={stopTracking}
              >
                Stop Tracking
              </Button>
            </Stack>
          ) : (
            <Button
              variant="contained"
              size="small"
              onClick={() => startTracking(selectedVRUType)}
              startIcon={<Add />}
            >
              Start Tracking {selectedVRUType}
            </Button>
          )}
        </Box>
      )}

      {/* Temporal Range Controls */}
      {annotationMode === 'temporal' && (
        <Box sx={{ mb: 2, p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Temporal Range Annotation
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <TextField
              label="Start Frame"
              type="number"
              size="small"
              sx={{ width: 100 }}
            />
            <TextField
              label="End Frame"
              type="number"
              size="small"
              sx={{ width: 100 }}
            />
            <Button
              variant="contained"
              size="small"
              onClick={() => createTemporalAnnotation(currentFrame, currentFrame + 30)}
              startIcon={<Add />}
            >
              Create Range
            </Button>
          </Stack>
        </Box>
      )}

      {/* Current Frame Annotations */}
      <Box sx={{ mb: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="subtitle2">
            Current Frame Annotations ({currentAnnotations.length})
          </Typography>
          <IconButton
            size="small"
            onClick={() => setShowAllAnnotations(!showAllAnnotations)}
          >
            {showAllAnnotations ? <Visibility /> : <VisibilityOff />}
          </IconButton>
        </Stack>
        
        {currentAnnotations.length > 0 ? (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {currentAnnotations.map(annotation => (
              <Chip
                key={annotation.id}
                label={`${annotation.vruType} (${annotation.detectionId})`}
                size="small"
                sx={{
                  bgcolor: getVRUColor(annotation.vruType),
                  color: 'white',
                  '& .MuiChip-deleteIcon': { color: 'white' },
                }}
                onDelete={() => onAnnotationDelete(annotation.id)}
                deleteIcon={<Delete />}
              />
            ))}
          </Stack>
        ) : (
          <Alert severity="info" sx={{ py: 1 }}>
            No annotations on current frame
          </Alert>
        )}
      </Box>

      {/* Temporal Ranges Overview */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Detection Tracks ({temporalRanges.length})
        </Typography>
        
        {temporalRanges.length > 0 ? (
          <Stack spacing={1}>
            {temporalRanges.map(range => (
              <Card
                key={range.detectionId}
                variant="outlined"
                sx={{
                  cursor: 'pointer',
                  border: selectedRange?.detectionId === range.detectionId ? 2 : 1,
                  borderColor: selectedRange?.detectionId === range.detectionId
                    ? 'primary.main'
                    : getVRUColor(range.vruType),
                }}
                onClick={() => setSelectedRange(range)}
              >
                <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          bgcolor: getVRUColor(range.vruType),
                          borderRadius: '50%',
                        }}
                      />
                      <Typography variant="body2">
                        {range.detectionId}
                      </Typography>
                      <Chip
                        label={range.vruType}
                        size="small"
                        variant="outlined"
                      />
                    </Stack>
                    <Stack direction="row" alignItems="center" spacing={2}>
                      <Typography variant="caption">
                        Frames: {range.start} - {range.end} ({range.end - range.start + 1})
                      </Typography>
                      <Badge
                        badgeContent={
                          annotations.filter(a => a.detectionId === range.detectionId).length
                        }
                        color="primary"
                      >
                        <Timeline />
                      </Badge>
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Stack>
        ) : (
          <Alert severity="info" sx={{ py: 1 }}>
            No detection tracks created
          </Alert>
        )}
      </Box>

      {/* Keyframes Overview */}
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Keyframes ({keyframes.length})
        </Typography>
        
        {keyframes.length > 0 ? (
          <Box sx={{ maxHeight: 200, overflowY: 'auto' }}>
            <Stack spacing={1}>
              {keyframes.map(keyframe => (
                <Box
                  key={keyframe.frame}
                  onClick={() => goToFrame(keyframe.frame)}
                  sx={{
                    p: 1,
                    bgcolor: keyframe.frame === currentFrame ? 'primary.light' : 'grey.100',
                    borderRadius: 1,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'grey.200' },
                  }}
                >
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="body2">
                      Frame {keyframe.frame} ({formatTime(keyframe.timestamp)})
                    </Typography>
                    <Stack direction="row" spacing={0.5}>
                      {keyframe.annotations.map(annotation => (
                        <Box
                          key={annotation.id}
                          sx={{
                            width: 8,
                            height: 8,
                            bgcolor: getVRUColor(annotation.vruType),
                            borderRadius: '50%',
                          }}
                        />
                      ))}
                    </Stack>
                  </Stack>
                </Box>
              ))}
            </Stack>
          </Box>
        ) : (
          <Alert severity="info" sx={{ py: 1 }}>
            No keyframes created
          </Alert>
        )}
      </Box>
    </Paper>
  );
};

export default TemporalAnnotationInterface;