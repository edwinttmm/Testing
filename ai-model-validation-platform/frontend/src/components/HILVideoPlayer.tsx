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
import { clockSyncService } from '../services/clockSyncService';
import websocketService from '../services/websocketService';

// HIL Video Player Component for full-screen test execution
// Implements PRD Module 3 requirements for sequential video playback

interface HILVideoPlayerProps {
  // Video playlist and current video
  videoPlaylist: VideoFile[];
  currentVideoIndex: number;

  // Test execution state
  testInProgress: boolean;
  isFullScreen: boolean;

  // Clean video mode - shows ONLY video, no overlays at all
  cleanVideoMode?: boolean;
  onToggleCleanMode?: () => void;

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
  cleanVideoMode = false,
  onToggleCleanMode,
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
  const [clockSyncInitialized, setClockSyncInitialized] = useState(false);

  const currentVideo = videoPlaylist[currentVideoIndex];

  // Keyboard shortcut 'C' to toggle clean video mode (no overlays)
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input field
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if ((e.key === 'c' || e.key === 'C') && onToggleCleanMode) {
        e.preventDefault();
        onToggleCleanMode();
      }
      // Also support 'Escape' to exit clean mode
      if (e.key === 'Escape' && cleanVideoMode && onToggleCleanMode) {
        e.preventDefault();
        onToggleCleanMode();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [cleanVideoMode, onToggleCleanMode]);

  // Initialize clock synchronization on test start
  useEffect(() => {
    if (testInProgress && !clockSyncInitialized) {
      clockSyncService.synchronize()
        .then((offset) => {
          console.log(`[HILVideoPlayer] Clock synchronized. Offset: ${offset.toFixed(2)}ms`);
          setClockSyncInitialized(true);

          // Warn if drift is high
          if (!clockSyncService.isDriftAcceptable()) {
            console.warn(`[HILVideoPlayer] Clock drift detected: ${offset.toFixed(2)}ms`);
          }
        })
        .catch((error) => {
          console.error('[HILVideoPlayer] Clock sync failed:', error);
          onVideoError('Clock sync failed - timestamps may be inaccurate');
        });

      // Re-sync every 30 seconds during test
      const syncInterval = setInterval(() => {
        if (testInProgress) {
          clockSyncService.autoSyncIfNeeded();
        }
      }, 30000);

      return () => clearInterval(syncInterval);
    }
  }, [testInProgress, clockSyncInitialized, onVideoError]);
  
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

    // Capture exact video start time with clock synchronization
    if (videoRef.current && currentVideo) {
      const syncedTimestamp = clockSyncService.getSynchronizedTime();

      console.log('[HILVideoPlayer] VIDEO_STARTED event', {
        videoId: currentVideo.id,
        timestamp: syncedTimestamp,
        testSessionId: testStartTime?.toISOString()
      });

      // Emit VIDEO_STARTED via WebSocket
      if (websocketService.isConnected) {
        websocketService.emit('video-lifecycle', {
          event: 'VIDEO_STARTED',
          sessionId: testStartTime?.toISOString() || 'unknown',
          videoId: currentVideo.id,
          timestamp: syncedTimestamp,
          clockOffset: clockSyncService.getOffset(),
          videoIndex: currentVideoIndex,
          videoUrl: currentVideo.filePath,
          clientTimestamp: new Date().toISOString()
        });
      } else {
        console.warn('[HILVideoPlayer] WebSocket not connected - VIDEO_STARTED event not sent');
      }
    }

    // Notify parent component that video has started for timing measurement
    if (onVideoStart && videoRef.current) {
      onVideoStart(videoRef.current);
    }
  }, [onVideoStart, currentVideo, currentVideoIndex, testStartTime]);
  
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

    // Capture exact video end time with clock synchronization
    if (videoRef.current && currentVideo) {
      const syncedTimestamp = clockSyncService.getSynchronizedTime();
      const duration = videoRef.current.currentTime;

      console.log('[HILVideoPlayer] VIDEO_ENDED event', {
        videoId: currentVideo.id,
        timestamp: syncedTimestamp,
        duration,
        testSessionId: testStartTime?.toISOString()
      });

      // Emit VIDEO_ENDED via WebSocket
      if (websocketService.isConnected) {
        websocketService.emit('video-lifecycle', {
          event: 'VIDEO_ENDED',
          sessionId: testStartTime?.toISOString() || 'unknown',
          videoId: currentVideo.id,
          timestamp: syncedTimestamp,
          duration,
          clockOffset: clockSyncService.getOffset(),
          videoIndex: currentVideoIndex,
          clientTimestamp: new Date().toISOString()
        });
      } else {
        console.warn('[HILVideoPlayer] WebSocket not connected - VIDEO_ENDED event not sent');
      }
    }

    onVideoEnd();
  }, [onVideoEnd, currentVideo, currentVideoIndex, testStartTime]);
  
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

    // Emit VIDEO_ERROR via WebSocket
    if (currentVideo) {
      const syncedTimestamp = clockSyncService.getSynchronizedTime();

      console.error('[HILVideoPlayer] VIDEO_ERROR event', {
        videoId: currentVideo.id,
        timestamp: syncedTimestamp,
        error: errorMessage,
        errorCode: error?.code
      });

      if (websocketService.isConnected) {
        websocketService.emit('video-lifecycle', {
          event: 'VIDEO_ERROR',
          sessionId: testStartTime?.toISOString() || 'unknown',
          videoId: currentVideo.id,
          timestamp: syncedTimestamp,
          error: errorMessage,
          errorCode: error?.code,
          videoIndex: currentVideoIndex,
          clientTimestamp: new Date().toISOString()
        });
      }
    }

    onVideoError(`Video error: ${errorMessage}`);
  }, [onVideoError, currentVideo, currentVideoIndex, testStartTime]);
  
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
      }}
    >
      {/* Main Video Element - CLEAN: No overlays, just pure video */}
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
    </Box>
  );
};

export default HILVideoPlayer;