import React, { useRef, useEffect, useCallback, useState } from 'react';
import {
  Box,
  IconButton,
  Typography,
  LinearProgress,
  Tooltip,
  Fade,
  Alert,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  VolumeOff,
  VolumeUp,
  Fullscreen,
  FullscreenExit,
  Timeline,
} from '@mui/icons-material';
import { VideoFile, DetectionOutcome } from '../services/types';

// HIL Video Player Component for full-screen test execution
// Implements PRD Module 3 requirements for sequential video playback

interface HILVideoPlayerProps {
  // Video playlist and current video
  videoPlaylist: VideoFile[];
  currentVideoIndex: number;
  
  // Test execution state
  testInProgress: boolean;
  isFullScreen: boolean;
  
  // Hardware signal detection events
  detectionEvents: Array<{
    id: number;
    videoId: number;
    expectedEventTime: string;
    signalReceivedTime?: string;
    latencyMs?: number;
    outcome: DetectionOutcome;
    createdAt: string;
  }>;
  
  // Maximum latency threshold for pass/fail determination
  maxLatencyMs: number;
  
  // Event handlers
  onVideoEnd: () => void;
  onVideoError: (error: string) => void;
  onNextVideo: () => void;
  onPreviousVideo: () => void;
  onToggleFullScreen: () => void;
  onVideoStart?: (videoElement: HTMLVideoElement) => void;
  
  // Optional test session info
  testStartTime?: Date;
}

const HILVideoPlayer: React.FC<HILVideoPlayerProps> = ({
  videoPlaylist,
  currentVideoIndex,
  testInProgress,
  isFullScreen,
  detectionEvents,
  maxLatencyMs,
  onVideoEnd,
  onVideoError,
  onNextVideo,
  onPreviousVideo,
  onToggleFullScreen,
  onVideoStart,
  testStartTime,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [videoProgress, setVideoProgress] = useState(0);
  const [videoCurrentTime, setVideoCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const [controlsTimeout, setControlsTimeout] = useState<NodeJS.Timeout | null>(null);
  
  const currentVideo = videoPlaylist[currentVideoIndex];
  
  // Auto-hide controls in full-screen mode
  useEffect(() => {
    if (isFullScreen && testInProgress) {
      const hideControls = () => {
        setShowControls(false);
      };
      
      const showControlsTemporary = () => {
        setShowControls(true);
        if (controlsTimeout) clearTimeout(controlsTimeout);
        setControlsTimeout(setTimeout(hideControls, 3000));
      };
      
      const handleMouseMove = () => showControlsTemporary();
      const handleMouseLeave = () => {
        if (controlsTimeout) clearTimeout(controlsTimeout);
        setControlsTimeout(setTimeout(hideControls, 1000));
      };
      
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseleave', handleMouseLeave);
      
      // Initially show controls for 3 seconds
      showControlsTemporary();
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseleave', handleMouseLeave);
        if (controlsTimeout) clearTimeout(controlsTimeout);
      };
    } else {
      setShowControls(true);
    }
  }, [isFullScreen, testInProgress, controlsTimeout]);
  
  // Video event handlers
  const handleVideoLoad = useCallback(() => {
    if (videoRef.current) {
      setVideoDuration(videoRef.current.duration);
      setVideoCurrentTime(0);
      setVideoProgress(0);
    }
  }, []);
  
  const handleVideoPlay = useCallback(() => {
    setIsPlaying(true);
    // Notify parent component that video has started for timing measurement
    if (onVideoStart && videoRef.current) {
      onVideoStart(videoRef.current);
    }
  }, [onVideoStart]);
  
  const handleVideoPause = useCallback(() => {
    setIsPlaying(false);
  }, []);
  
  const handleVideoTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      const current = videoRef.current.currentTime;
      const duration = videoRef.current.duration;
      setVideoCurrentTime(current);
      setVideoProgress(duration > 0 ? (current / duration) * 100 : 0);
    }
  }, []);
  
  const handleVideoEnded = useCallback(() => {
    setIsPlaying(false);
    onVideoEnd();
  }, [onVideoEnd]);
  
  const handleVideoError = useCallback(() => {
    const error = videoRef.current?.error;
    let errorMessage = 'Unknown video error';
    
    if (error) {
      switch (error.code) {
        case MediaError.MEDIA_ERR_ABORTED:
          errorMessage = 'Video playback was aborted';
          break;
        case MediaError.MEDIA_ERR_NETWORK:
          errorMessage = 'Network error occurred while loading video';
          break;
        case MediaError.MEDIA_ERR_DECODE:
          errorMessage = 'Error decoding video file';
          break;
        case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
          errorMessage = 'Video format not supported';
          break;
        default:
          errorMessage = error.message || 'Video error occurred';
      }
    }
    
    onVideoError(`Video error: ${errorMessage}`);
  }, [onVideoError]);
  
  // Auto-play when test starts and video changes
  useEffect(() => {
    if (testInProgress && videoRef.current && currentVideo) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().catch(err => {
        console.error('Failed to auto-play video:', err);
        onVideoError('Failed to start video playback');
      });
    }
  }, [testInProgress, currentVideo, onVideoError]);
  
  // Play/pause toggle
  const togglePlayPause = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play().catch(err => {
          console.error('Failed to play video:', err);
          onVideoError('Failed to play video');
        });
      }
    }
  }, [isPlaying, onVideoError]);
  
  // Mute/unmute toggle
  const toggleMute = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.muted = !videoRef.current.muted;
      setIsMuted(videoRef.current.muted);
    }
  }, []);
  
  // Format time display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // Calculate test statistics for current video
  const videoEvents = detectionEvents.filter(event => String(event.videoId) === currentVideo?.id);
  const passedEvents = videoEvents.filter(event => event.outcome === DetectionOutcome.PASS);
  const failedEvents = videoEvents.filter(event => event.outcome !== DetectionOutcome.PASS);
  const averageLatency = videoEvents.length > 0 
    ? videoEvents.reduce((sum, event) => sum + (event.latencyMs || 0), 0) / videoEvents.length
    : 0;
  
  if (!currentVideo) {
    return (
      <Box
        sx={{
          width: '100%',
          height: isFullScreen ? '100vh' : '600px',
          backgroundColor: 'black',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white'
        }}
      >
        <Typography variant="h6">No video selected</Typography>
      </Box>
    );
  }
  
  return (
    <Box
      sx={{
        width: '100%',
        height: isFullScreen ? '100vh' : '600px',
        backgroundColor: 'black',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: isFullScreen && !showControls ? 'none' : 'default'
      }}
    >
      {/* Main Video Element */}
      <video
        ref={videoRef}
        src={currentVideo.filePath}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain'
        }}
        onLoadedMetadata={handleVideoLoad}
        onPlay={handleVideoPlay}
        onPause={handleVideoPause}
        onTimeUpdate={handleVideoTimeUpdate}
        onEnded={handleVideoEnded}
        onError={handleVideoError}
        playsInline
        preload="metadata"
      />
      
      {/* Video Loading Overlay */}
      {!videoDuration && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0,0,0,0.7)',
            color: 'white'
          }}
        >
          <Typography variant="h6">Loading video...</Typography>
        </Box>
      )}
      
      {/* Full-Screen Controls Overlay */}
      <Fade in={showControls || !isFullScreen}>
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            pointerEvents: showControls || !isFullScreen ? 'auto' : 'none',
            background: isFullScreen 
              ? 'linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 20%, transparent 80%, rgba(0,0,0,0.5) 100%)'
              : 'none'
          }}
        >
          {/* Top Bar - Video Info and Test Progress */}
          <Box
            sx={{
              position: 'absolute',
              top: isFullScreen ? 16 : 8,
              left: isFullScreen ? 16 : 8,
              right: isFullScreen ? 16 : 8,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              color: 'white',
              zIndex: 2
            }}
          >
            <Box>
              <Typography variant={isFullScreen ? 'h5' : 'h6'} sx={{ fontWeight: 'bold' }}>
                Video {currentVideoIndex + 1} of {videoPlaylist.length}
              </Typography>
              <Typography variant={isFullScreen ? 'body1' : 'body2'}>
                {currentVideo.filename}
              </Typography>
              {testStartTime && (
                <Typography variant={isFullScreen ? 'body2' : 'caption'} sx={{ opacity: 0.8 }}>
                  Test running for {Math.floor((Date.now() - testStartTime.getTime()) / 1000)}s
                </Typography>
              )}
            </Box>
            
            {/* Full-Screen Toggle */}
            <Tooltip title={isFullScreen ? "Exit Full Screen" : "Enter Full Screen"}>
              <IconButton
                onClick={onToggleFullScreen}
                sx={{ color: 'white' }}
                size={isFullScreen ? 'large' : 'medium'}
              >
                {isFullScreen ? <FullscreenExit /> : <Fullscreen />}
              </IconButton>
            </Tooltip>
          </Box>
          
          {/* Center Play/Pause Button */}
          {!testInProgress && (
            <Box
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                zIndex: 2
              }}
            >
              <IconButton
                onClick={togglePlayPause}
                sx={{
                  color: 'white',
                  backgroundColor: 'rgba(0,0,0,0.5)',
                  '&:hover': { backgroundColor: 'rgba(0,0,0,0.7)' }
                }}
                size={isFullScreen ? 'large' : 'medium'}
              >
                {isPlaying ? <Pause sx={{ fontSize: 48 }} /> : <PlayArrow sx={{ fontSize: 48 }} />}
              </IconButton>
            </Box>
          )}
          
          {/* Bottom Controls Bar */}
          <Box
            sx={{
              position: 'absolute',
              bottom: isFullScreen ? 16 : 8,
              left: isFullScreen ? 16 : 8,
              right: isFullScreen ? 16 : 8,
              backgroundColor: 'rgba(0,0,0,0.7)',
              borderRadius: 2,
              p: isFullScreen ? 2 : 1,
              color: 'white'
            }}
          >
            {/* Progress Bar */}
            <LinearProgress
              variant="determinate"
              value={videoProgress}
              sx={{
                mb: 1,
                backgroundColor: 'rgba(255,255,255,0.3)',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: 'white'
                }
              }}
            />
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {/* Playback Controls */}
              <IconButton
                onClick={onPreviousVideo}
                disabled={currentVideoIndex === 0}
                sx={{ color: 'white' }}
                size="small"
              >
                <SkipPrevious />
              </IconButton>
              
              {!testInProgress && (
                <IconButton onClick={togglePlayPause} sx={{ color: 'white' }} size="small">
                  {isPlaying ? <Pause /> : <PlayArrow />}
                </IconButton>
              )}
              
              <IconButton
                onClick={onNextVideo}
                disabled={currentVideoIndex >= videoPlaylist.length - 1}
                sx={{ color: 'white' }}
                size="small"
              >
                <SkipNext />
              </IconButton>
              
              <IconButton onClick={toggleMute} sx={{ color: 'white' }} size="small">
                {isMuted ? <VolumeOff /> : <VolumeUp />}
              </IconButton>
              
              {/* Time Display */}
              <Typography variant="body2" sx={{ minWidth: 80 }}>
                {formatTime(videoCurrentTime)} / {formatTime(videoDuration)}
              </Typography>
              
              {/* Spacer */}
              <Box sx={{ flexGrow: 1 }} />
              
              {/* Test Statistics for Current Video */}
              {testInProgress && videoEvents.length > 0 && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Typography variant="body2">
                    <Timeline sx={{ fontSize: 16, mr: 0.5 }} />
                    {videoEvents.length} events
                  </Typography>
                  <Typography variant="body2" color="success.light">
                    ✓ {passedEvents.length}
                  </Typography>
                  <Typography variant="body2" color="error.light">
                    ✗ {failedEvents.length}
                  </Typography>
                  <Typography variant="body2">
                    Avg: {averageLatency.toFixed(1)}ms
                  </Typography>
                </Box>
              )}
              
              {/* Overall Test Progress */}
              {testInProgress && (
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {Math.round((currentVideoIndex / videoPlaylist.length) * 100)}% Complete
                </Typography>
              )}
            </Box>
          </Box>
        </Box>
      </Fade>
      
      {/* Test Status Alerts */}
      {testInProgress && videoEvents.length > 0 && (
        <Box
          sx={{
            position: 'absolute',
            top: isFullScreen ? 100 : 60,
            right: isFullScreen ? 16 : 8,
            maxWidth: 300,
            zIndex: 3
          }}
        >
          {/* Recent high latency alert */}
          {failedEvents.slice(-1).map(event => (
            <Alert 
              key={event.id}
              severity="warning" 
              sx={{ 
                mb: 1,
                backgroundColor: 'rgba(255, 152, 0, 0.9)',
                color: 'white',
                '& .MuiAlert-icon': { color: 'white' }
              }}
            >
              High latency detected: {event.latencyMs?.toFixed(1)}ms (max: {maxLatencyMs}ms)
            </Alert>
          ))}
        </Box>
      )}
    </Box>
  );
};

export default HILVideoPlayer;