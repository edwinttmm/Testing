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
  Replay,
} from '@mui/icons-material';
import { VideoFile, GroundTruthAnnotation } from '../services/types';
import {
  safeVideoPlay,
  safeVideoPause,
  cleanupVideoElement,
  setVideoSource,
  addVideoEventListeners,
  getVideoErrorMessage,
  isVideoReady,
} from '../utils/videoUtils';

interface EnhancedVideoPlayerProps {
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

interface PlaybackError {
  message: string;
  type: 'load' | 'play' | 'network' | 'format' | 'unknown';
  recoverable: boolean;
}

const EnhancedVideoPlayer: React.FC<EnhancedVideoPlayerProps> = ({
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
  
  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [videoSize, setVideoSize] = useState({ width: 0, height: 0 });
  const [playbackRate, setPlaybackRate] = useState(1);
  // Fullscreen state removed - isFullscreen variable was unused
  
  // Loading and error state
  const [loading, setLoading] = useState(true);
  const [buffering, setBuffering] = useState(false);
  const [loadProgress, setLoadProgress] = useState(0);
  const [error, setError] = useState<PlaybackError | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  // Calculate current frame number
  const currentFrame = Math.floor(currentTime * frameRate);

  // Get annotations for current frame
  const currentAnnotations = annotations.filter(
    annotation => Math.abs(annotation.frameNumber - currentFrame) <= 1
  );

  // Define initializeVideo first without dependencies
  const initializeVideo = useCallback(async () => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    try {
      setLoading(true);
      setError(null);
      setBuffering(true);

      // Use only the video.url prop - no fallback to filename
      if (!video.url) {
        throw new Error('Video URL is not available');
      }
      await setVideoSource(videoElement, video.url);
      
      setLoading(false);
      setBuffering(false);
    } catch (err) {
      console.error('Video initialization error:', err);
      // Handle error directly here to avoid circular dependency
      const error: PlaybackError = {
        message: err instanceof Error ? err.message : 'Unknown video error',
        type: 'load',
        recoverable: true
      };
      setError(error);
      setLoading(false);
      setBuffering(false);
      setIsPlaying(false);
    }
  }, [video.url]);

  // Define handleVideoError after initializeVideo to avoid circular dependency
  const handleVideoError = useCallback((err: Error, type: PlaybackError['type'] = 'unknown') => {
    let errorInfo: PlaybackError;
    
    const videoElement = videoRef.current;
    if (videoElement && videoElement.error) {
      const message = getVideoErrorMessage(videoElement);
      errorInfo = {
        message,
        type: 'format',
        recoverable: videoElement.error.code !== MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED
      };
    } else {
      errorInfo = {
        message: err.message || 'Unknown video error',
        type,
        recoverable: type !== 'format'
      };
    }

    setError(errorInfo);
    setLoading(false);
    setBuffering(false);
    setIsPlaying(false);

    // Auto-retry for recoverable errors
    if (autoRetry && errorInfo.recoverable && retryCount < maxRetries) {
      const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 10000); // Exponential backoff
      setTimeout(() => {
        setRetryCount(prev => prev + 1);
        initializeVideo();
      }, retryDelay);
    }
  }, [autoRetry, maxRetries, retryCount, initializeVideo]);

  const handleRetry = useCallback(() => {
    setRetryCount(0);
    setError(null);
    initializeVideo();
  }, [initializeVideo]);

  // Draw annotations on canvas
  const drawAnnotations = useCallback(() => {
    const canvas = canvasRef.current;
    const videoElement = videoRef.current;
    
    if (!canvas || !videoElement || !isVideoReady(videoElement)) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Set canvas size to match video display size
    const rect = videoElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Calculate scaling factors
    const scaleX = rect.width / videoSize.width;
    const scaleY = rect.height / videoSize.height;

    if (videoSize.width === 0 || videoSize.height === 0) return;

    // Draw current annotations
    currentAnnotations.forEach(annotation => {
      const bbox = annotation.boundingBox;
      
      // Scale bounding box to canvas size
      const x = bbox.x * scaleX;
      const y = bbox.y * scaleY;
      const width = bbox.width * scaleX;
      const height = bbox.height * scaleY;

      // Set style based on annotation type and selection
      const isSelected = selectedAnnotation?.id === annotation.id;
      const color = getVRUColor(annotation.vruType);
      
      ctx.strokeStyle = isSelected ? '#ff0000' : color;
      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.fillStyle = isSelected ? 'rgba(255, 0, 0, 0.1)' : `${color}20`;

      // Draw bounding box
      ctx.strokeRect(x, y, width, height);
      ctx.fillRect(x, y, width, height);

      // Draw label
      ctx.fillStyle = isSelected ? '#ff0000' : color;
      ctx.font = '14px Arial';
      const labelText = `${annotation.vruType} (${annotation.detectionId})`;
      const labelWidth = ctx.measureText(labelText).width;
      
      // Label background
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(x, y - 20, labelWidth + 8, 18);
      
      // Label text
      ctx.fillStyle = '#ffffff';
      ctx.fillText(labelText, x + 4, y - 6);

      // Draw validation indicator
      if (annotation.validated) {
        ctx.fillStyle = '#4caf50';
        ctx.fillRect(x + width - 20, y, 20, 20);
        ctx.fillStyle = '#ffffff';
        ctx.font = '12px Arial';
        ctx.fillText('✓', x + width - 15, y + 14);
      }
    });
  }, [currentAnnotations, selectedAnnotation, videoSize]);

  // Handle canvas click
  const handleCanvasClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!annotationMode) return;

    const canvas = canvasRef.current;
    const videoElement = videoRef.current;
    
    if (!canvas || !videoElement || !isVideoReady(videoElement)) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Convert to video coordinates
    const scaleX = videoSize.width / rect.width;
    const scaleY = videoSize.height / rect.height;
    const videoX = x * scaleX;
    const videoY = y * scaleY;

    // Check if click is on existing annotation
    const clickedAnnotation = currentAnnotations.find(annotation => {
      const bbox = annotation.boundingBox;
      return (
        videoX >= bbox.x &&
        videoX <= bbox.x + bbox.width &&
        videoY >= bbox.y &&
        videoY <= bbox.y + bbox.height
      );
    });

    if (clickedAnnotation) {
      onAnnotationSelect?.(clickedAnnotation);
    } else {
      // Create new annotation at click position
      onCanvasClick?.(videoX, videoY, currentFrame, currentTime);
    }
  }, [annotationMode, currentAnnotations, videoSize, currentFrame, currentTime, onAnnotationSelect, onCanvasClick]);

  // Get color for VRU type
  const getVRUColor = (vruType: string): string => {
    const colors = {
      pedestrian: '#2196f3',
      cyclist: '#4caf50',
      motorcyclist: '#ff9800',
      wheelchair_user: '#9c27b0',
      scooter_rider: '#ff5722',
    };
    return colors[vruType as keyof typeof colors] || '#607d8b';
  };

  // Control functions with enhanced error handling
  const togglePlayPause = useCallback(async () => {
    const videoElement = videoRef.current;
    if (!videoElement || !isVideoReady(videoElement)) return;

    try {
      if (isPlaying) {
        safeVideoPause(videoElement);
      } else {
        setBuffering(true);
        const result = await safeVideoPlay(videoElement);
        if (!result.success) {
          console.warn('Video play failed:', result.error?.message);
          handleVideoError(result.error || new Error('Play failed'), 'play');
        }
        setBuffering(false);
      }
    } catch (error) {
      handleVideoError(error as Error, 'play');
    }
  }, [isPlaying, handleVideoError]);

  const handleSeek = useCallback((value: number) => {
    const videoElement = videoRef.current;
    if (!videoElement || !isVideoReady(videoElement)) return;

    try {
      setBuffering(true);
      videoElement.currentTime = value;
      setCurrentTime(value);
    } catch (error) {
      console.warn('Video seek failed:', error);
      handleVideoError(error as Error, 'play');
    } finally {
      setTimeout(() => setBuffering(false), 500);
    }
  }, [handleVideoError]);

  const handleVolumeChange = useCallback((value: number) => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    try {
      videoElement.volume = value;
      setVolume(value);
      setIsMuted(value === 0);
    } catch (error) {
      console.warn('Volume change failed:', error);
    }
  }, []);

  const toggleMute = useCallback(() => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    try {
      if (isMuted) {
        videoElement.volume = volume;
        setIsMuted(false);
      } else {
        videoElement.volume = 0;
        setIsMuted(true);
      }
    } catch (error) {
      console.warn('Mute toggle failed:', error);
    }
  }, [isMuted, volume]);

  const stepFrame = useCallback((direction: 'forward' | 'backward') => {
    const videoElement = videoRef.current;
    if (!videoElement || !isVideoReady(videoElement)) return;

    try {
      const frameTime = 1 / frameRate;
      const newTime = direction === 'forward' 
        ? Math.min(currentTime + frameTime, duration)
        : Math.max(currentTime - frameTime, 0);
      
      handleSeek(newTime);
    } catch (error) {
      console.warn('Frame step failed:', error);
    }
  }, [currentTime, duration, frameRate, handleSeek]);

  const handlePlaybackRateChange = useCallback((rate: number) => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    try {
      videoElement.playbackRate = rate;
      setPlaybackRate(rate);
    } catch (error) {
      console.warn('Playback rate change failed:', error);
    }
  }, []);

  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    try {
      if (!document.fullscreenElement) {
        container.requestFullscreen();
      } else {
        document.exitFullscreen();
      }
    } catch (error) {
      console.warn('Fullscreen toggle failed:', error);
    }
  }, []);

  const formatTime = useCallback((time: number): string => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, []);

  // Setup video event listeners
  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    const handleLoadStart = () => {
      setLoading(true);
      setBuffering(true);
    };

    const handleLoadedMetadata = () => {
      setDuration(videoElement.duration);
      setVideoSize({ 
        width: videoElement.videoWidth, 
        height: videoElement.videoHeight 
      });
      setLoading(false);
    };

    const handleCanPlay = () => {
      setBuffering(false);
    };

    const handleWaiting = () => {
      setBuffering(true);
    };

    const handleCanPlayThrough = () => {
      setBuffering(false);
    };

    const handleTimeUpdate = () => {
      if (videoElement.currentTime !== undefined) {
        const time = videoElement.currentTime;
        setCurrentTime(time);
        const frame = Math.floor(time * frameRate);
        onTimeUpdate?.(time, frame);
      }
    };

    const handleProgress = () => {
      if (videoElement.buffered.length > 0) {
        const buffered = videoElement.buffered.end(videoElement.buffered.length - 1);
        const progress = (buffered / videoElement.duration) * 100;
        setLoadProgress(progress);
      }
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    
    const handleError = (event: Event) => {
      console.error('Video error event:', event);
      handleVideoError(new Error('Video playback error'), 'play');
    };

    const handleStalled = () => {
      setBuffering(true);
      console.warn('Video playback stalled');
    };

    const handleSuspend = () => {
      console.warn('Video loading suspended');
    };

    // Use utility function for batch event listener management
    const cleanupListeners = addVideoEventListeners(videoElement, [
      { event: 'loadstart', handler: handleLoadStart },
      { event: 'loadedmetadata', handler: handleLoadedMetadata },
      { event: 'canplay', handler: handleCanPlay },
      { event: 'canplaythrough', handler: handleCanPlayThrough },
      { event: 'waiting', handler: handleWaiting },
      { event: 'timeupdate', handler: handleTimeUpdate },
      { event: 'progress', handler: handleProgress },
      { event: 'play', handler: handlePlay },
      { event: 'pause', handler: handlePause },
      { event: 'ended', handler: handleEnded },
      { event: 'error', handler: handleError },
      { event: 'stalled', handler: handleStalled },
      { event: 'suspend', handler: handleSuspend },
    ]);

    return cleanupListeners;
  }, [frameRate, onTimeUpdate, handleVideoError]);

  // Initialize video when component mounts or video changes
  useEffect(() => {
    // Capture ref at effect creation time to avoid stale closure
    const videoElement = videoRef.current;
    initializeVideo();
    return () => {
      if (videoElement) {
        cleanupVideoElement(videoElement);
      }
    };
  }, [initializeVideo]);

  // Redraw annotations when annotations change
  useEffect(() => {
    if (!loading && !error) {
      drawAnnotations();
    }
  }, [drawAnnotations, loading, error]);

  // Error state rendering
  if (error) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Alert 
            severity="error" 
            icon={<ErrorOutline />}
            action={
              error.recoverable ? (
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={handleRetry}
                  startIcon={<Refresh />}
                >
                  Retry ({retryCount}/{maxRetries})
                </Button>
              ) : (
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={() => window.location.reload()}
                  startIcon={<Replay />}
                >
                  Reload Page
                </Button>
              )
            }
          >
            <Typography variant="body2">
              <strong>Video Error:</strong> {error.message}
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1 }}>
              {error.recoverable 
                ? `Attempting to recover... (${retryCount}/${maxRetries} attempts)`
                : 'This error requires a page reload to fix.'
              }
            </Typography>
          </Alert>
          
          {/* Show video info even in error state */}
          <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Video Information
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>File:</strong> {video.filename || video.name || 'Unknown'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Source:</strong> {video.url}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Status:</strong> {video.status || 'Unknown'}
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box ref={containerRef} sx={{ position: 'relative', bgcolor: 'black', borderRadius: 1 }}>
          {/* Loading overlay */}
          {loading && (
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
            >
              <CircularProgress color="inherit" sx={{ mb: 2 }} />
              <Typography variant="body1">Loading video...</Typography>
              <Typography variant="caption" sx={{ mt: 1 }}>
                {video.filename || video.name}
              </Typography>
              {loadProgress > 0 && (
                <Box sx={{ width: '200px', mt: 2 }}>
                  <LinearProgress 
                    variant="determinate" 
                    value={loadProgress} 
                    color="inherit"
                  />
                  <Typography variant="caption" align="center" display="block">
                    {loadProgress.toFixed(0)}% loaded
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {/* Buffering overlay */}
          {buffering && !loading && (
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
            >
              <CircularProgress size={16} color="inherit" />
              <Typography variant="caption">Buffering...</Typography>
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
            onResize={() => {
              const videoElement = videoRef.current;
              if (videoElement && videoElement.videoWidth && videoElement.videoHeight) {
                setVideoSize({
                  width: videoElement.videoWidth,
                  height: videoElement.videoHeight,
                });
              }
            }}
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
            onClick={handleCanvasClick}
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
            >
              ANNOTATION MODE
            </Box>
          )}
        </Box>

        {/* Video Controls */}
        <Box sx={{ mt: 2 }}>
          {/* Progress Slider */}
          <Box sx={{ mb: 2 }}>
            <Slider
              value={currentTime}
              min={0}
              max={duration}
              onChange={(_, value) => handleSeek(value as number)}
              sx={{ width: '100%' }}
              size="small"
              disabled={loading || !!error}
            />
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1 }}>
              <Typography variant="caption">
                Frame: {currentFrame} | {formatTime(currentTime)} / {formatTime(duration)}
              </Typography>
              <Typography variant="caption">
                Annotations: {currentAnnotations.length}
                {loadProgress > 0 && loadProgress < 100 && ` | ${loadProgress.toFixed(0)}% loaded`}
              </Typography>
            </Stack>
          </Box>

          {/* Control Buttons */}
          <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
            <Tooltip title="Previous Frame">
              <IconButton 
                onClick={() => stepFrame('backward')} 
                size="small"
                disabled={loading || !!error}
              >
                <SkipPrevious />
              </IconButton>
            </Tooltip>
            
            <Tooltip title={isPlaying ? 'Pause' : 'Play'}>
              <IconButton 
                onClick={togglePlayPause}
                disabled={loading || !!error}
              >
                {buffering ? (
                  <CircularProgress size={24} />
                ) : isPlaying ? (
                  <Pause />
                ) : (
                  <PlayArrow />
                )}
              </IconButton>
            </Tooltip>
            
            <Tooltip title="Next Frame">
              <IconButton 
                onClick={() => stepFrame('forward')} 
                size="small"
                disabled={loading || !!error}
              >
                <SkipNext />
              </IconButton>
            </Tooltip>

            <Box sx={{ mx: 2, display: 'flex', alignItems: 'center', minWidth: 120 }}>
              <Tooltip title={isMuted ? 'Unmute' : 'Mute'}>
                <IconButton onClick={toggleMute} size="small">
                  {isMuted ? <VolumeOff /> : <VolumeUp />}
                </IconButton>
              </Tooltip>
              <Slider
                value={isMuted ? 0 : volume}
                min={0}
                max={1}
                step={0.1}
                onChange={(_, value) => handleVolumeChange(value as number)}
                size="small"
                sx={{ ml: 1, width: 80 }}
                disabled={loading || !!error}
              />
            </Box>

            {/* Playback Rate */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="caption">Speed:</Typography>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                {[0.5, 0.75, 1, 1.25, 1.5, 2].map(rate => (
                  <Button
                    key={rate}
                    size="small"
                    variant={playbackRate === rate ? 'contained' : 'outlined'}
                    onClick={() => handlePlaybackRateChange(rate)}
                    sx={{ minWidth: 'auto', px: 1, py: 0.5 }}
                    disabled={loading || !!error}
                  >
                    {rate}x
                  </Button>
                ))}
              </Box>
            </Box>

            <Tooltip title="Fullscreen">
              <IconButton 
                size="small" 
                onClick={toggleFullscreen}
                disabled={loading || !!error}
              >
                <Fullscreen />
              </IconButton>
            </Tooltip>
          </Stack>
        </Box>

        {/* Current Annotations Info */}
        {currentAnnotations.length > 0 && (
          <Paper sx={{ mt: 2, p: 2, bgcolor: 'grey.50' }}>
            <Typography variant="subtitle2" gutterBottom>
              Current Frame Annotations ({currentAnnotations.length})
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {currentAnnotations.map(annotation => (
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
                    borderColor: getVRUColor(annotation.vruType),
                    borderRadius: 1,
                    cursor: 'pointer',
                    '&:hover': {
                      bgcolor: selectedAnnotation?.id === annotation.id ? 'primary.dark' : 'grey.100',
                    },
                  }}
                >
                  <Box
                    sx={{
                      width: 12,
                      height: 12,
                      bgcolor: getVRUColor(annotation.vruType),
                      borderRadius: '50%',
                    }}
                  />
                  <Typography variant="caption">
                    {annotation.vruType} ({annotation.detectionId})
                  </Typography>
                  {annotation.validated && (
                    <Typography variant="caption" sx={{ color: 'success.main' }}>
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

export default EnhancedVideoPlayer;