import React, { useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  LinearProgress,
  ButtonGroup,
  Button,
  TextField,
  Tooltip,
  Chip,
  Stack,
  IconButton,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  FastForward,
  FastRewind,
  Visibility,
  VisibilityOff,
} from '@mui/icons-material';
import { GroundTruthObject, VRUType } from '../services/types';

interface TimelineMarker {
  frameNumber: number;
  timestampMs: number;
  vruId: string;
  vruType: VRUType;
  validated: boolean;
  confidence: number;
}

interface InteractiveTimelineProps {
  groundTruthObjects: GroundTruthObject[];
  currentFrame: number;
  totalFrames: number;
  currentTime: number;
  duration: number;
  frameRate: number;
  isPlaying: boolean;
  selectedVruId: string | null;
  visible: boolean;
  onFrameChange: (frame: number) => void;
  onTimeChange: (time: number) => void;
  onPlayPause: () => void;
  onVisibilityToggle: () => void;
  onMarkerClick: (marker: TimelineMarker) => void;
  onJumpToStart: () => void;
  onJumpToEnd: () => void;
  onStepForward: () => void;
  onStepBackward: () => void;
  onFastForward: () => void;
  onFastRewind: () => void;
}

const InteractiveTimeline: React.FC<InteractiveTimelineProps> = ({
  groundTruthObjects,
  currentFrame,
  totalFrames,
  currentTime,
  duration,
  frameRate,
  isPlaying,
  selectedVruId,
  visible,
  onFrameChange,
  onTimeChange,
  onPlayPause,
  onVisibilityToggle,
  onMarkerClick,
  onJumpToStart,
  onJumpToEnd,
  onStepForward,
  onStepBackward,
  onFastForward,
  onFastRewind,
}) => {
  // Generate timeline markers from ground truth objects
  const timelineMarkers = useMemo<TimelineMarker[]>(() => {
    return groundTruthObjects.map(obj => ({
      frameNumber: obj.frameNumber,
      timestampMs: obj.timestampMs,
      vruId: obj.vruId,
      vruType: obj.vruType,
      validated: obj.validated,
      confidence: obj.confidence,
    }));
  }, [groundTruthObjects]);
  
  // Group markers by frame to handle overlapping annotations
  const markersByFrame = useMemo(() => {
    const grouped = new Map<number, TimelineMarker[]>();
    
    timelineMarkers.forEach(marker => {
      const existing = grouped.get(marker.frameNumber) || [];
      existing.push(marker);
      grouped.set(marker.frameNumber, existing);
    });
    
    return grouped;
  }, [timelineMarkers]);
  
  // Calculate timeline statistics
  const timelineStats = useMemo(() => {
    const total = timelineMarkers.length;
    const validated = timelineMarkers.filter(m => m.validated).length;
    const uniqueFrames = new Set(timelineMarkers.map(m => m.frameNumber)).size;
    const vruTypeCounts = timelineMarkers.reduce((acc, marker) => {
      acc[marker.vruType] = (acc[marker.vruType] || 0) + 1;
      return acc;
    }, {} as Record<VRUType, number>);
    
    return { total, validated, uniqueFrames, vruTypeCounts };
  }, [timelineMarkers]);
  
  // Handle frame input
  const handleFrameInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const frame = parseInt(e.target.value);
    if (!isNaN(frame)) {
      const clampedFrame = Math.max(0, Math.min(frame, totalFrames - 1));
      onFrameChange(clampedFrame);
    }
  }, [onFrameChange, totalFrames]);
  
  // Handle time input
  const handleTimeInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (!isNaN(time)) {
      const clampedTime = Math.max(0, Math.min(time, duration));
      onTimeChange(clampedTime);
    }
  }, [onTimeChange, duration]);
  
  // Handle timeline click
  const handleTimelineClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = clickX / rect.width;
    const frame = Math.floor(percentage * totalFrames);
    const clampedFrame = Math.max(0, Math.min(frame, totalFrames - 1));
    onFrameChange(clampedFrame);
  }, [onFrameChange, totalFrames]);
  
  // Get VRU color
  const getVRUColor = (vruType: VRUType): string => {
    const colors = {
      pedestrian: '#ff5722',
      cyclist: '#2196f3',
      motorcyclist: '#ff9800',
      wheelchair: '#9c27b0',
      scooter: '#4caf50',
    };
    return colors[vruType] || '#607d8b';
  };
  
  // Get marker height based on confidence
  const getMarkerHeight = (confidence: number): number => {
    return Math.max(4, confidence * 12);
  };
  
  // Format time display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}:${secs.padStart(4, '0')}`;
  };
  
  if (!visible) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
        <Button
          size="small"
          onClick={onVisibilityToggle}
          startIcon={<Visibility />}
          variant="outlined"
        >
          Show Timeline
        </Button>
      </Box>
    );
  }
  
  return (
    <Card sx={{ mt: 2 }}>
      <CardContent>
        {/* Timeline Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Interactive Timeline</Typography>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Timeline Statistics */}
            <Stack direction="row" spacing={1}>
              <Chip 
                label={`${timelineStats.total} objects`} 
                size="small" 
                variant="outlined" 
              />
              <Chip 
                label={`${timelineStats.validated} validated`} 
                size="small" 
                color="success"
                variant={timelineStats.validated > 0 ? 'filled' : 'outlined'}
              />
              <Chip 
                label={`${timelineStats.uniqueFrames} frames`} 
                size="small" 
                color="primary"
                variant="outlined"
              />
            </Stack>
            
            <IconButton size="small" onClick={onVisibilityToggle}>
              <VisibilityOff />
            </IconButton>
          </Box>
        </Box>
        
        {/* VRU Type Distribution */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            VRU Distribution
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {Object.entries(timelineStats.vruTypeCounts).map(([vruType, count]) => (
              <Chip
                key={vruType}
                label={`${vruType}: ${count}`}
                size="small"
                sx={{
                  backgroundColor: getVRUColor(vruType as VRUType),
                  color: 'white',
                  '&:hover': {
                    backgroundColor: getVRUColor(vruType as VRUType),
                    opacity: 0.8,
                  },
                }}
              />
            ))}
          </Stack>
        </Box>
        
        {/* Main Timeline */}
        <Box sx={{ position: 'relative', mb: 2 }}>
          {/* Timeline Background */}
          <Box
            sx={{
              height: 20,
              backgroundColor: '#f0f0f0',
              borderRadius: 1,
              cursor: 'pointer',
              position: 'relative',
              overflow: 'hidden',
            }}
            onClick={handleTimelineClick}
          >
            {/* Progress Bar */}
            <LinearProgress
              variant="determinate"
              value={(currentFrame / Math.max(totalFrames - 1, 1)) * 100}
              sx={{
                height: '100%',
                backgroundColor: 'transparent',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: 'rgba(33, 150, 243, 0.3)',
                },
              }}
            />
            
            {/* Annotation Markers */}
            {Array.from(markersByFrame.entries()).map(([frameNumber, markers]) => {
              const position = (frameNumber / Math.max(totalFrames - 1, 1)) * 100;
              
              return (
                <Box key={frameNumber}>
                  {markers.map((marker, index) => (
                    <Tooltip
                      key={`${marker.vruId}-${index}`}
                      title={
                        <Box>
                          <Typography variant="caption">
                            {marker.vruType} - {marker.vruId}
                          </Typography>
                          <br />
                          <Typography variant="caption">
                            Frame: {marker.frameNumber} | Time: {formatTime(marker.timestampMs / 1000)}
                          </Typography>
                          <br />
                          <Typography variant="caption">
                            Confidence: {(marker.confidence * 100).toFixed(1)}%
                          </Typography>
                          <br />
                          <Typography variant="caption">
                            Status: {marker.validated ? 'Validated' : 'Pending'}
                          </Typography>
                        </Box>
                      }
                    >
                      <Box
                        sx={{
                          position: 'absolute',
                          left: `${position}%`,
                          top: index * 2,
                          width: 3,
                          height: getMarkerHeight(marker.confidence),
                          backgroundColor: getVRUColor(marker.vruType),
                          borderRadius: '0 0 2px 2px',
                          cursor: 'pointer',
                          opacity: marker.validated ? 1 : 0.6,
                          border: selectedVruId === marker.vruId ? '2px solid white' : 'none',
                          transform: selectedVruId === marker.vruId ? 'scale(1.5)' : 'scale(1)',
                          transition: 'transform 0.2s ease',
                          zIndex: selectedVruId === marker.vruId ? 10 : 1,
                          '&:hover': {
                            transform: 'scale(1.2)',
                            zIndex: 5,
                          },
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onMarkerClick(marker);
                        }}
                      />
                    </Tooltip>
                  ))}
                </Box>
              );
            })}
            
            {/* Current Position Indicator */}
            <Box
              sx={{
                position: 'absolute',
                left: `${(currentFrame / Math.max(totalFrames - 1, 1)) * 100}%`,
                top: -2,
                width: 2,
                height: 24,
                backgroundColor: '#d32f2f',
                borderRadius: '2px 2px 0 0',
                zIndex: 20,
                boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
              }}
            />
          </Box>
          
          {/* Timeline Scale */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              0:00
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatTime(duration / 2)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatTime(duration)}
            </Typography>
          </Box>
        </Box>
        
        {/* Playback Controls */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <ButtonGroup size="small">
            <Tooltip title="Jump to Start">
              <Button onClick={onJumpToStart}>
                <SkipPrevious />
              </Button>
            </Tooltip>
            
            <Tooltip title="Fast Rewind (10 frames)">
              <Button onClick={onFastRewind}>
                <FastRewind />
              </Button>
            </Tooltip>
            
            <Tooltip title="Previous Frame (←)">
              <Button onClick={onStepBackward}>
                <SkipPrevious sx={{ fontSize: 16 }} />
              </Button>
            </Tooltip>
            
            <Tooltip title="Play/Pause (Space)">
              <Button onClick={onPlayPause} variant="contained">
                {isPlaying ? <Pause /> : <PlayArrow />}
              </Button>
            </Tooltip>
            
            <Tooltip title="Next Frame (→)">
              <Button onClick={onStepForward}>
                <SkipNext sx={{ fontSize: 16 }} />
              </Button>
            </Tooltip>
            
            <Tooltip title="Fast Forward (10 frames)">
              <Button onClick={onFastForward}>
                <FastForward />
              </Button>
            </Tooltip>
            
            <Tooltip title="Jump to End">
              <Button onClick={onJumpToEnd}>
                <SkipNext />
              </Button>
            </Tooltip>
          </ButtonGroup>
          
          <Box sx={{ flexGrow: 1 }} />
          
          {/* Direct Input Controls */}
          <TextField
            type="number"
            label="Frame"
            value={currentFrame}
            onChange={handleFrameInput}
            size="small"
            sx={{ width: 100 }}
            inputProps={{ 
              min: 0, 
              max: totalFrames - 1,
              step: 1 
            }}
          />
          
          <TextField
            type="number"
            label="Time (s)"
            value={currentTime.toFixed(2)}
            onChange={handleTimeInput}
            size="small"
            sx={{ width: 100 }}
            inputProps={{ 
              min: 0, 
              max: duration,
              step: 0.1 
            }}
          />
        </Box>
        
        {/* Current Frame Info */}
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          p: 1,
          backgroundColor: '#f8f9fa',
          borderRadius: 1,
        }}>
          <Typography variant="body2">
            <strong>Current:</strong> Frame {currentFrame} of {totalFrames}
          </Typography>
          
          <Typography variant="body2">
            <strong>Time:</strong> {formatTime(currentTime)} / {formatTime(duration)}
          </Typography>
          
          <Typography variant="body2">
            <strong>Objects:</strong> {markersByFrame.get(currentFrame)?.length || 0} in frame
          </Typography>
          
          <Typography variant="body2">
            <strong>Frame Rate:</strong> {frameRate} fps
          </Typography>
        </Box>
        
        {/* Keyboard Shortcuts Help */}
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            <strong>Shortcuts:</strong> ← → Frame navigation • Space: Play/Pause • Click timeline to jump
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default InteractiveTimeline;