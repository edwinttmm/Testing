import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  Stack,
  IconButton,
  Paper,
  Alert,
  Fade
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  VolumeOff as VolumeOffIcon,
  Fullscreen as FullscreenIcon,
  CheckCircle as CheckCircleIcon
} from '@mui/icons-material';

interface AutomatedVideoPlayerProps {
  videoUrl?: string;
  videoName?: string;
  videoIndex: number;
  totalVideos: number;
  isAutomated: boolean;
  onVideoStart?: () => void;
  onVideoEnd?: () => void;
  onError?: (error: string) => void;
  expectedDetectionTime?: number;
  className?: string;
}

interface DetectionOverlay {
  timestamp: number;
  message: string;
  type: 'success' | 'warning' | 'error';
  voltage?: number;
}

export const AutomatedVideoPlayer: React.FC<AutomatedVideoPlayerProps> = ({
  videoUrl,
  videoName,
  videoIndex,
  totalVideos,
  isAutomated,
  onVideoStart,
  onVideoEnd,
  onError,
  expectedDetectionTime = 2.0,
  className
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [detectionOverlays, setDetectionOverlays] = useState<DetectionOverlay[]>([]);
  const [videoError, setVideoError] = useState<string | null>(null);

  // Auto-play when video URL changes and automation is enabled
  useEffect(() => {
    if (videoUrl && isAutomated && videoRef.current) {
      const video = videoRef.current;
      
      // Reset video state
      setCurrentTime(0);
      setVideoError(null);
      setDetectionOverlays([]);
      
      // Auto-play with error handling
      const playVideo = async () => {
        try {
          video.load();
          await video.play();
          setIsPlaying(true);
          
          if (onVideoStart) {
            onVideoStart();
          }
        } catch (error) {
          console.error('Auto-play failed:', error);
          const errorMessage = error instanceof Error ? error.message : 'Auto-play failed';
          setVideoError(errorMessage);
          
          if (onError) {
            onError(errorMessage);
          }
        }
      };
      
      // Small delay to ensure video is ready
      const timeoutId = setTimeout(playVideo, 100);
      
      return () => clearTimeout(timeoutId);
    }
    // Return cleanup function for all paths
    return () => {};
  }, [videoUrl, isAutomated, onVideoStart, onError]);

  // Video event handlers
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  }, []);

  const handleVideoEnd = useCallback(() => {
    setIsPlaying(false);
    setCurrentTime(duration);
    
    if (onVideoEnd) {
      onVideoEnd();
    }
  }, [duration, onVideoEnd]);

  const handleVideoError = useCallback(() => {
    if (videoRef.current?.error) {
      const errorMessage = `Video error: ${videoRef.current.error.message}`;
      setVideoError(errorMessage);
      setIsPlaying(false);
      
      if (onError) {
        onError(errorMessage);
      }
    }
  }, [onError]);

  // Manual playback controls (for non-automated mode)
  const togglePlayPause = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        videoRef.current.play()
          .then(() => setIsPlaying(true))
          .catch(error => {
            console.error('Play failed:', error);
            setVideoError('Failed to play video');
          });
      }
    }
  }, [isPlaying]);

  const stopVideo = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
      setIsPlaying(false);
      setCurrentTime(0);
    }
  }, []);

  // Add detection overlay (called externally) - exposed for external use
  const _addDetectionOverlay = useCallback((message: string, type: 'success' | 'warning' | 'error', voltage?: number) => {
    const overlay: DetectionOverlay = {
      timestamp: Date.now(),
      message,
      type,
      voltage
    };
    
    setDetectionOverlays(prev => [...prev.slice(-5), overlay]); // Keep last 5 overlays
  }, []);

  // Note: _addDetectionOverlay is available for external use but not directly exposed via ref
  // If needed, this function can be called through parent component state management

  // Progress calculation
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
  const detectionTimeProgress = duration > 0 ? (expectedDetectionTime / duration) * 100 : 0;

  // Format time display
  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <Card className={className} sx={{ position: 'relative', overflow: 'visible' }}>
      <CardContent sx={{ pb: 2 }}>
        {/* Header */}
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Box>
            <Typography variant="h6" noWrap>
              Video {videoIndex + 1} of {totalVideos}
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {videoName || 'Unknown Video'}
            </Typography>
          </Box>
          
          <Stack direction="row" spacing={1} alignItems="center">
            {isAutomated && (
              <Chip 
                label="AUTOMATED" 
                color="primary" 
                size="small"
                icon={<CheckCircleIcon />}
              />
            )}
            
            <Chip 
              label={isPlaying ? 'PLAYING' : 'PAUSED'}
              color={isPlaying ? 'success' : 'default'}
              size="small"
              icon={isPlaying ? <PlayIcon /> : <PauseIcon />}
            />
          </Stack>
        </Stack>

        {/* Video Player */}
        <Box sx={{ position: 'relative', mb: 2 }}>
          {videoUrl ? (
            <video
              ref={videoRef}
              src={videoUrl}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={handleVideoEnd}
              onError={handleVideoError}
              style={{
                width: '100%',
                height: 'auto',
                maxHeight: '400px',
                backgroundColor: '#000',
                borderRadius: '4px'
              }}
              muted // Required for auto-play in many browsers
              playsInline
            />
          ) : (
            <Box
              sx={{
                width: '100%',
                height: '300px',
                backgroundColor: 'grey.900',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 1
              }}
            >
              <Typography color="text.secondary">
                No video loaded
              </Typography>
            </Box>
          )}

          {/* Detection Overlays */}
          {detectionOverlays.map((overlay, index) => (
            <Fade key={overlay.timestamp} in={true} timeout={500}>
              <Box
                sx={{
                  position: 'absolute',
                  top: 16 + (index * 40),
                  right: 16,
                  zIndex: 10
                }}
              >
                <Alert 
                  severity={overlay.type} 
                  onClose={() => {
                    setDetectionOverlays(prev => 
                      prev.filter(o => o.timestamp !== overlay.timestamp)
                    );
                  }}
                >
                  {overlay.message}
                  {overlay.voltage && ` (${overlay.voltage.toFixed(2)}V)`}
                </Alert>
              </Box>
            </Fade>
          ))}

          {/* Error Overlay */}
          {videoError && (
            <Box
              sx={{
                position: 'absolute',
                top: 16,
                left: 16,
                right: 16,
                zIndex: 10
              }}
            >
              <Alert severity="error">
                {videoError}
              </Alert>
            </Box>
          )}
        </Box>

        {/* Progress Bar with Detection Marker */}
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2">
              {formatTime(currentTime)} / {formatTime(duration)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Expected detection: {expectedDetectionTime}s
            </Typography>
          </Box>
          
          <Box sx={{ position: 'relative' }}>
            <LinearProgress 
              variant="determinate" 
              value={progress} 
              sx={{ height: 8, borderRadius: 4 }}
            />
            
            {/* Detection Time Marker */}
            {detectionTimeProgress > 0 && (
              <Box
                sx={{
                  position: 'absolute',
                  left: `${detectionTimeProgress}%`,
                  top: 0,
                  bottom: 0,
                  width: 2,
                  backgroundColor: 'warning.main',
                  transform: 'translateX(-1px)',
                  zIndex: 1
                }}
              />
            )}
          </Box>
        </Box>

        {/* Manual Controls (only shown when not automated) */}
        {!isAutomated && (
          <Stack direction="row" spacing={1} justifyContent="center">
            <IconButton onClick={togglePlayPause} disabled={!videoUrl}>
              {isPlaying ? <PauseIcon /> : <PlayIcon />}
            </IconButton>
            
            <IconButton onClick={stopVideo} disabled={!videoUrl}>
              <StopIcon />
            </IconButton>
            
            <IconButton disabled>
              <VolumeOffIcon />
            </IconButton>
            
            <IconButton disabled>
              <FullscreenIcon />
            </IconButton>
          </Stack>
        )}

        {/* Status Information */}
        {isAutomated && (
          <Paper sx={{ p: 1, mt: 2, bgcolor: 'background.default' }}>
            <Typography variant="caption" color="text.secondary">
              🤖 Automated playback active - Video will advance automatically after completion
            </Typography>
          </Paper>
        )}
      </CardContent>
    </Card>
  );
};

export default AutomatedVideoPlayer;