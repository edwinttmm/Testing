/**
 * Safe Video Player Example Component
 * Demonstrates proper usage of video utilities and hooks
 * to prevent "play() request interrupted" errors
 */

import React from 'react';
import {
  Box,
  Button,
  Typography,
  Alert,
  LinearProgress,
  Stack,
  Card,
  CardContent,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Stop,
  VolumeUp,
  VolumeOff,
} from '@mui/icons-material';
import { useVideoPlayer } from '../../hooks/useVideoPlayer';

interface SafeVideoPlayerExampleProps {
  videoSrc: string;
  title?: string;
}

const SafeVideoPlayerExample: React.FC<SafeVideoPlayerExampleProps> = ({
  videoSrc,
  title = 'Safe Video Player Example',
}) => {
  const { videoRef, state, controls } = useVideoPlayer({
    onPlay: () => console.log('Video started playing safely'),
    onPause: () => console.log('Video paused'),
    onEnded: () => console.log('Video playback ended'),
    onError: (error) => console.error('Video error handled:', error),
    autoCleanup: true, // Automatically cleanup on unmount
  });

  const handlePlay = async () => {
    const result = await controls.play();
    if (!result.success) {
      console.warn('Play failed but handled gracefully:', result.error?.message);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progressPercentage = state.duration > 0 
    ? (state.currentTime / state.duration) * 100 
    : 0;

  return (
    <Card sx={{ maxWidth: 600, mx: 'auto', mt: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>

        {/* Video Element */}
        <Box sx={{ position: 'relative', mb: 2 }}>
          <video
            ref={videoRef}
            style={{
              width: '100%',
              height: 'auto',
              backgroundColor: '#000',
              borderRadius: '4px',
            }}
            src={videoSrc}
            preload="metadata"
            playsInline
          />
          
          {state.isLoading && (
            <Box
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                color: 'white',
              }}
            >
              <Typography variant="body2">Loading video...</Typography>
            </Box>
          )}
        </Box>

        {/* Error Display */}
        {state.error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Video Error: {state.error}
          </Alert>
        )}

        {/* Progress Bar */}
        <Box sx={{ mb: 2 }}>
          <LinearProgress
            variant="determinate"
            value={progressPercentage}
            sx={{ height: 8, borderRadius: 1 }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
            <Typography variant="caption">
              {formatTime(state.currentTime)}
            </Typography>
            <Typography variant="caption">
              {formatTime(state.duration)}
            </Typography>
          </Box>
        </Box>

        {/* Controls */}
        <Stack direction="row" spacing={1} justifyContent="center" alignItems="center">
          <Button
            variant="contained"
            size="small"
            startIcon={state.isPlaying ? <Pause /> : <PlayArrow />}
            onClick={state.isPlaying ? controls.pause : handlePlay}
            disabled={state.isLoading}
          >
            {state.isPlaying ? 'Pause' : 'Play'}
          </Button>

          <Button
            variant="outlined"
            size="small"
            startIcon={<Stop />}
            onClick={controls.stop}
            disabled={state.isLoading || (!state.isPlaying && state.currentTime === 0)}
          >
            Stop
          </Button>

          <Button
            variant="text"
            size="small"
            startIcon={state.muted ? <VolumeOff /> : <VolumeUp />}
            onClick={controls.toggleMute}
            disabled={state.isLoading}
          >
            {state.muted ? 'Unmute' : 'Mute'}
          </Button>
        </Stack>

        {/* Video Info */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Video State Information
          </Typography>
          <Stack spacing={1}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2">Status:</Typography>
              <Typography variant="body2">
                {state.isLoading ? 'Loading...' : state.isPlaying ? 'Playing' : 'Paused'}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2">Duration:</Typography>
              <Typography variant="body2">{formatTime(state.duration)}</Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2">Resolution:</Typography>
              <Typography variant="body2">
                {state.videoSize.width} x {state.videoSize.height}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2">Volume:</Typography>
              <Typography variant="body2">
                {Math.round(state.volume * 100)}% {state.muted ? '(Muted)' : ''}
              </Typography>
            </Box>
          </Stack>
        </Box>

        {/* Usage Notes */}
        <Alert severity="info" sx={{ mt: 2 }}>
          <Typography variant="body2" component="div">
            <strong>Safety Features Demonstrated:</strong>
            <ul style={{ marginTop: 8, marginBottom: 0 }}>
              <li>Promise-based play() calls with error handling</li>
              <li>Automatic cleanup on component unmount</li>
              <li>Graceful error recovery</li>
              <li>Loading state management</li>
              <li>Memory leak prevention</li>
            </ul>
          </Typography>
        </Alert>
      </CardContent>
    </Card>
  );
};

export default SafeVideoPlayerExample;