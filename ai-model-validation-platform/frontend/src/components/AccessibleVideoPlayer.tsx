/**
 * Accessible Video Player Component
 * Provides full ARIA support, keyboard navigation, and screen reader compatibility
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  IconButton,
  Slider,
  Typography,
  Card,
  CardContent,
  Tooltip,
  Stack,
  Button,
  Alert,
  CircularProgress,
  LinearProgress,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  VolumeUp,
  VolumeOff,
  Fullscreen,
  SkipNext,
  SkipPrevious,
  Refresh,
  ErrorOutline,
  Speed,
  Settings,
  ClosedCaption,
} from '@mui/icons-material';
import { VideoFile, GroundTruthAnnotation } from '../services/types';
import VideoPlaybackManager, { VideoPlaybackState } from '../utils/videoPlaybackManager';

interface AccessibleVideoPlayerProps {
  video: VideoFile;
  annotations: GroundTruthAnnotation[];
  onAnnotationSelect?: (annotation: GroundTruthAnnotation) => void;
  onTimeUpdate?: (currentTime: number, frameNumber: number) => void;
  onCanvasClick?: (x: number, y: number, frameNumber: number, timestamp: number) => void;
  annotationMode: boolean;
  selectedAnnotation?: GroundTruthAnnotation | null;
  frameRate?: number;
  autoRetry?: boolean;
  maxRetries?: number;
}

const AccessibleVideoPlayer: React.FC<AccessibleVideoPlayerProps> = ({
  video,
  annotations,
  onAnnotationSelect,
  onTimeUpdate,
  onCanvasClick,
  annotationMode,
  selectedAnnotation,
  frameRate = 30,
  autoRetry = true,
  maxRetries = 3,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const playbackManager = useRef<VideoPlaybackManager>(null);
  
  // State management
  const [playbackState, setPlaybackState] = useState<VideoPlaybackState>({
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    buffering: false,
    loading: true,
    error: null,
    readyState: 0,
  });
  
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [videoSize, setVideoSize] = useState({ width: 0, height: 0 });
  const [settingsAnchor, setSettingsAnchor] = useState<null | HTMLElement>(null);

  // Accessibility state
  const [focusedControl, setFocusedControl] = useState<string | null>(null);
  const [announcements, setAnnouncements] = useState<string>('');

  // Calculate current frame number
  const currentFrame = Math.floor(playbackState.currentTime * frameRate);

  // Get annotations for current frame
  const currentAnnotations = annotations.filter(
    annotation => Math.abs(annotation.frameNumber - currentFrame) <= 1
  );

  // Initialize playback manager
  useEffect(() => {
    if (!videoRef.current) return;

    playbackManager.current = new VideoPlaybackManager({
      retryAttempts: maxRetries,
      enableAutoRetry: autoRetry,
    });

    playbackManager.current.attachVideoElement(videoRef.current);
    
    const unsubscribe = playbackManager.current.onStateChange((state) => {
      setPlaybackState(state);
      
      // Call parent callback
      if (onTimeUpdate) {
        const frame = Math.floor(state.currentTime * frameRate);
        onTimeUpdate(state.currentTime, frame);
      }
    });

    return () => {
      unsubscribe();
      playbackManager.current?.destroy();
    };
  }, [maxRetries, autoRetry, frameRate, onTimeUpdate]);

  // Load video when URL changes
  useEffect(() => {
    if (!video.url || !playbackManager.current) return;

    const loadVideo = async () => {
      try {
        await playbackManager.current!.loadVideo(video.url!);
        announce(`Video loaded: ${video.filename || video.name}`);
        
        // Update video dimensions
        if (videoRef.current) {
          setVideoSize({
            width: videoRef.current.videoWidth,
            height: videoRef.current.videoHeight,
          });
        }
      } catch (error) {
        console.error('Failed to load video:', error);
        announce(`Failed to load video: ${video.filename || video.name}`);
      }
    };

    loadVideo();
  }, [video.url, video.filename, video.name]);

  // Accessibility announcements
  const announce = (message: string) => {
    setAnnouncements(message);
    setTimeout(() => setAnnouncements(''), 100);
  };

  // Keyboard event handler
  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (!playbackManager.current) return;

    const { key, ctrlKey, altKey, shiftKey } = event;
    
    // Prevent default for handled keys
    const handledKeys = ['Space', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 
                         'Home', 'End', 'KeyM', 'KeyF', 'KeyJ', 'KeyK', 'KeyL'];
    
    if (handledKeys.includes(key) || handledKeys.includes(event.code)) {
      event.preventDefault();
    }

    switch (key) {
      case ' ':
      case 'k':
        togglePlayPause();
        break;
        
      case 'ArrowLeft':
      case 'j':
        if (shiftKey) {
          stepFrame('backward');
        } else {
          seekRelative(-10);
        }
        break;
        
      case 'ArrowRight':
      case 'l':
        if (shiftKey) {
          stepFrame('forward');
        } else {
          seekRelative(10);
        }
        break;
        
      case 'ArrowUp':
        changeVolume(0.1);
        break;
        
      case 'ArrowDown':
        changeVolume(-0.1);
        break;
        
      case 'Home':
        seekTo(0);
        break;
        
      case 'End':
        seekTo(playbackState.duration);
        break;
        
      case 'm':
        toggleMute();
        break;
        
      case 'f':
        toggleFullscreen();
        break;
        
      case ',':
        if (playbackState.isPlaying) {
          playbackManager.current.pause();
        }
        stepFrame('backward');
        break;
        
      case '.':
        if (playbackState.isPlaying) {
          playbackManager.current.pause();
        }
        stepFrame('forward');
        break;
    }
  }, [playbackState.isPlaying, playbackState.duration]);

  // Control functions
  const togglePlayPause = async () => {
    if (!playbackManager.current) return;

    if (playbackState.isPlaying) {
      playbackManager.current.pause();
      announce('Video paused');
    } else {
      const success = await playbackManager.current.play();
      announce(success ? 'Video playing' : 'Failed to play video');
    }
  };

  const seekTo = (time: number) => {
    if (!playbackManager.current) return;
    playbackManager.current.seek(time);
    announce(`Seeked to ${formatTime(time)}`);
  };

  const seekRelative = (seconds: number) => {
    const newTime = Math.max(0, Math.min(playbackState.duration, playbackState.currentTime + seconds));
    seekTo(newTime);
  };

  const stepFrame = (direction: 'forward' | 'backward') => {
    const frameTime = 1 / frameRate;
    const offset = direction === 'forward' ? frameTime : -frameTime;
    seekRelative(offset);
    announce(`${direction === 'forward' ? 'Next' : 'Previous'} frame: ${currentFrame}`);
  };

  const changeVolume = (delta: number) => {
    const newVolume = Math.max(0, Math.min(1, volume + delta));
    setVolume(newVolume);
    playbackManager.current?.setVolume(newVolume);
    announce(`Volume ${Math.round(newVolume * 100)}%`);
  };

  const toggleMute = () => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);
    playbackManager.current?.setVolume(newMuted ? 0 : volume);
    announce(newMuted ? 'Muted' : 'Unmuted');
  };

  const toggleFullscreen = () => {
    const container = containerRef.current;
    if (!container) return;

    try {
      if (!document.fullscreenElement) {
        container.requestFullscreen();
        announce('Entered fullscreen');
      } else {
        document.exitFullscreen();
        announce('Exited fullscreen');
      }
    } catch (error) {
      console.warn('Fullscreen toggle failed:', error);
      announce('Fullscreen not supported');
    }
  };

  const handlePlaybackRateChange = (rate: number) => {
    if (!videoRef.current) return;
    
    try {
      videoRef.current.playbackRate = rate;
      setPlaybackRate(rate);
      announce(`Playback speed ${rate}x`);
    } catch (error) {
      console.warn('Playback rate change failed:', error);
    }
  };

  const formatTime = (time: number): string => {
    const hours = Math.floor(time / 3600);
    const minutes = Math.floor((time % 3600) / 60);
    const seconds = Math.floor(time % 60);
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Error state rendering
  if (playbackState.error) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Alert 
            severity="error" 
            icon={<ErrorOutline />}
            action={
              playbackState.error.recoverable ? (
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={() => playbackManager.current?.loadVideo(video.url!)}
                  startIcon={<Refresh />}
                  aria-label="Retry loading video"
                >
                  Retry
                </Button>
              ) : null
            }
          >
            <Typography variant="body2">
              <strong>Video Error:</strong> {playbackState.error.message}
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1 }}>
              {playbackState.error.recoverable 
                ? 'You can try to reload the video.'
                : 'This error requires a page refresh to fix.'
              }
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        {/* Screen reader announcements */}
        <div aria-live="polite" aria-atomic="true" className="sr-only">
          {announcements}
        </div>
        
        <Box 
          ref={containerRef} 
          sx={{ position: 'relative', bgcolor: 'black', borderRadius: 1 }}
          role="region"
          aria-label="Video player"
          tabIndex={0}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocusedControl('player')}
        >
          {/* Loading overlay */}
          {playbackState.loading && (
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: 'rgba(0, 0, 0, 0.7)',
                color: 'white',
                zIndex: 10,
              }}
              role="status"
              aria-label="Loading video"
            >
              <CircularProgress color="inherit" sx={{ mb: 2 }} />
              <Typography variant="body1">Loading video...</Typography>
              <Typography variant="caption" sx={{ mt: 1 }}>
                {video.filename || video.name}
              </Typography>
            </Box>
          )}

          {/* Video Element */}
          <video
            ref={videoRef}
            style={{
              width: '100%',
              height: 'auto',
              display: 'block',
              maxHeight: '500px',
            }}
            preload="metadata"
            playsInline
            aria-label={`Video: ${video.filename || video.name}`}
            aria-describedby="video-description"
          />

          {/* Annotation Canvas Overlay */}
          <canvas
            ref={canvasRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: annotationMode ? 'auto' : 'none',
              cursor: annotationMode ? 'crosshair' : 'default',
            }}
            onClick={(e) => {
              if (onCanvasClick && annotationMode && videoRef.current) {
                const rect = e.currentTarget.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const currentTime = videoRef.current.currentTime;
                const frameNumber = Math.floor(currentTime * frameRate);
                onCanvasClick(x, y, frameNumber, currentTime);
              }
            }}
            role={annotationMode ? 'button' : 'presentation'}
            aria-label={annotationMode ? 'Click to create annotation' : 'Video annotations overlay'}
            tabIndex={annotationMode ? 0 : -1}
          />

          {/* Annotation Mode Indicator */}
          {annotationMode && (
            <Box
              sx={{
                position: 'absolute',
                top: 8,
                left: 8,
                bgcolor: 'rgba(255, 152, 0, 0.9)',
                color: 'white',
                px: 2,
                py: 1,
                borderRadius: 1,
                fontSize: '14px',
                fontWeight: 'bold',
              }}
              role="status"
              aria-label="Annotation mode active"
            >
              ANNOTATION MODE
            </Box>
          )}

          {/* Buffering indicator */}
          {playbackState.buffering && !playbackState.loading && (
            <Box
              sx={{
                position: 'absolute',
                top: 16,
                right: 16,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                bgcolor: 'rgba(0, 0, 0, 0.7)',
                color: 'white',
                px: 2,
                py: 1,
                borderRadius: 1,
                zIndex: 5,
              }}
              role="status"
              aria-label="Buffering video"
            >
              <CircularProgress size={16} color="inherit" />
              <Typography variant="caption">Buffering...</Typography>
            </Box>
          )}
        </Box>

        {/* Video Controls */}
        <Box sx={{ mt: 2 }} role="group" aria-label="Video controls">
          {/* Progress Slider */}
          <Box sx={{ mb: 2 }}>
            <Slider
              value={playbackState.currentTime}
              min={0}
              max={playbackState.duration || 1}
              onChange={(_, value) => seekTo(value as number)}
              sx={{ width: '100%' }}
              size="small"
              disabled={playbackState.loading || !!playbackState.error}
              aria-label="Video progress"
              aria-valuetext={`${formatTime(playbackState.currentTime)} of ${formatTime(playbackState.duration)}`}
            />
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1 }}>
              <Typography variant="caption" id="video-description">
                Frame: {currentFrame} | {formatTime(playbackState.currentTime)} / {formatTime(playbackState.duration)}
              </Typography>
              <Typography variant="caption">
                Annotations: {currentAnnotations.length}
              </Typography>
            </Stack>
          </Box>

          {/* Control Buttons */}
          <Stack direction="row" spacing={1} alignItems="center" justifyContent="center" role="toolbar" aria-label="Video playback controls">
            <Tooltip title="Previous Frame (Shift + Left Arrow)">
              <IconButton 
                onClick={() => stepFrame('backward')} 
                size="small"
                disabled={playbackState.loading || !!playbackState.error}
                aria-label="Go to previous frame"
              >
                <SkipPrevious />
              </IconButton>
            </Tooltip>
            
            <Tooltip title={playbackState.isPlaying ? 'Pause (Space)' : 'Play (Space)'}>
              <IconButton 
                onClick={togglePlayPause}
                disabled={playbackState.loading || !!playbackState.error}
                aria-label={playbackState.isPlaying ? 'Pause video' : 'Play video'}
              >
                {playbackState.buffering ? (
                  <CircularProgress size={24} />
                ) : playbackState.isPlaying ? (
                  <Pause />
                ) : (
                  <PlayArrow />
                )}
              </IconButton>
            </Tooltip>
            
            <Tooltip title="Next Frame (Shift + Right Arrow)">
              <IconButton 
                onClick={() => stepFrame('forward')} 
                size="small"
                disabled={playbackState.loading || !!playbackState.error}
                aria-label="Go to next frame"
              >
                <SkipNext />
              </IconButton>
            </Tooltip>

            {/* Volume controls */}
            <Box sx={{ mx: 2, display: 'flex', alignItems: 'center', minWidth: 120 }}>
              <Tooltip title={isMuted ? 'Unmute (M)' : 'Mute (M)'}>
                <IconButton 
                  onClick={toggleMute} 
                  size="small"
                  aria-label={isMuted ? 'Unmute' : 'Mute'}
                >
                  {isMuted ? <VolumeOff /> : <VolumeUp />}
                </IconButton>
              </Tooltip>
              <Slider
                value={isMuted ? 0 : volume}
                min={0}
                max={1}
                step={0.1}
                onChange={(_, value) => {
                  const newVolume = value as number;
                  setVolume(newVolume);
                  playbackManager.current?.setVolume(newVolume);
                }}
                size="small"
                sx={{ ml: 1, width: 80 }}
                disabled={playbackState.loading || !!playbackState.error}
                aria-label="Volume"
                aria-valuetext={`Volume ${Math.round((isMuted ? 0 : volume) * 100)}%`}
              />
            </Box>

            {/* Settings menu */}
            <Tooltip title="Settings">
              <IconButton
                size="small"
                onClick={(e) => setSettingsAnchor(e.currentTarget)}
                aria-label="Video settings"
                aria-haspopup="true"
              >
                <Settings />
              </IconButton>
            </Tooltip>

            <Tooltip title="Fullscreen (F)">
              <IconButton 
                size="small" 
                onClick={toggleFullscreen}
                disabled={playbackState.loading || !!playbackState.error}
                aria-label="Toggle fullscreen"
              >
                <Fullscreen />
              </IconButton>
            </Tooltip>
          </Stack>

          {/* Settings Menu */}
          <Menu
            anchorEl={settingsAnchor}
            open={Boolean(settingsAnchor)}
            onClose={() => setSettingsAnchor(null)}
            aria-label="Video settings menu"
          >
            <MenuItem disabled>
              <Typography variant="subtitle2">Playback Speed</Typography>
            </MenuItem>
            {[0.25, 0.5, 0.75, 1, 1.25, 1.5, 2].map(rate => (
              <MenuItem
                key={rate}
                selected={playbackRate === rate}
                onClick={() => {
                  handlePlaybackRateChange(rate);
                  setSettingsAnchor(null);
                }}
              >
                {rate}x {rate === 1 && '(Normal)'}
              </MenuItem>
            ))}
          </Menu>
        </Box>

        {/* Keyboard shortcuts help */}
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Keyboard shortcuts: Space (play/pause), ← → (seek), ↑ ↓ (volume), M (mute), F (fullscreen)
          </Typography>
        </Box>

        {/* Current Annotations Info */}
        {currentAnnotations.length > 0 && (
          <Paper sx={{ mt: 2, p: 2, bgcolor: 'grey.50' }} role="region" aria-label="Current frame annotations">
            <Typography variant="subtitle2" gutterBottom>
              Current Frame Annotations ({currentAnnotations.length})
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {currentAnnotations.map((annotation, index) => (
                <Box
                  key={annotation.id}
                  onClick={() => onAnnotationSelect?.(annotation)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    px: 2,
                    py: 1,
                    bgcolor: selectedAnnotation?.id === annotation.id ? 'primary.main' : 'white',
                    color: selectedAnnotation?.id === annotation.id ? 'white' : 'text.primary',
                    border: '1px solid',
                    borderColor: 'primary.main',
                    borderRadius: 1,
                    cursor: 'pointer',
                    '&:hover': {
                      bgcolor: selectedAnnotation?.id === annotation.id ? 'primary.dark' : 'grey.100',
                    },
                  }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Annotation ${index + 1}: ${annotation.vruType} detection ${annotation.detectionId}${annotation.validated ? ' (validated)' : ''}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onAnnotationSelect?.(annotation);
                    }
                  }}
                >
                  <Typography variant="caption">
                    {annotation.vruType} ({annotation.detectionId})
                  </Typography>
                  {annotation.validated && (
                    <Typography variant="caption" sx={{ color: 'success.main' }} aria-label="Validated">
                      ✓
                    </Typography>
                  )}
                </Box>
              ))}
            </Stack>
          </Paper>
        )}
      </CardContent>
    </Card>
  );
};

export default AccessibleVideoPlayer;