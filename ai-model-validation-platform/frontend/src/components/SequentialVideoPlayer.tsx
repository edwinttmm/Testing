/**
 * Sequential Video Player Component - SIMPLE & RELIABLE VERSION
 * 
 * React component that provides a straightforward sequential video playback interface
 * with minimal complexity and maximum reliability
 */

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  LinearProgress,
  Chip,
  Stack,
  Alert,
  Tooltip,
  Paper,
  Fade,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Fullscreen as FullscreenIcon,
  FullscreenExit as ExitFullscreenIcon,
  VolumeOff as VolumeOffIcon,
  VolumeUp as VolumeUpIcon,
} from '@mui/icons-material';

import {
  SequentialVideoPlaybackSystem,
  VideoState,
  VideoCallbacks,
} from '../utils/sequentialVideoPlaybackSystem';
import { markUserInteraction } from '../utils/videoUtils';
import { VideoFile } from '../services/types';

interface SequentialVideoPlayerProps {
  videos: VideoFile[];
  config?: {
    autoAdvance?: boolean;
    loopPlayback?: boolean;
  };
  onVideoStart?: (video: VideoFile, index: number) => void;
  onVideoEnd?: (video: VideoFile, index: number) => void;
  onPlaybackComplete?: () => void;
  onError?: (error: string, video: VideoFile) => void;
  onProgressUpdate?: (progress: number, videoIndex: number) => void;
  autoStart?: boolean;
  showControls?: boolean;
  showProgress?: boolean;
  syncWithLabJack?: boolean;
  className?: string;
}

interface UIState {
  isLoading: boolean;
  loadingMessage: string;
  showAutoplayWarning: boolean;
  isMutedForAutoplay: boolean;
}

const SequentialVideoPlayer: React.FC<SequentialVideoPlayerProps> = React.memo(({
  videos,
  config = {},
  onVideoStart,
  onVideoEnd,
  onPlaybackComplete,
  onError,
  onProgressUpdate,
  autoStart = false,
  showControls = true,
  showProgress = true,
  syncWithLabJack = false,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const playbackSystemRef = useRef<SequentialVideoPlaybackSystem | null>(null);
  
  const [playbackState, setPlaybackState] = useState<VideoState | null>(null);
  const [uiState, setUIState] = useState<UIState>({
    isLoading: false,
    loadingMessage: '',
    showAutoplayWarning: false,
    isMutedForAutoplay: false,
  });
  const [errors, setErrors] = useState<string[]>([]);

  // Initialize playback system - ONLY runs once on mount
  useEffect(() => {
    if (!containerRef.current) {
      console.log('🔍 DEBUG: containerRef.current is null, cannot initialize playback system');
      return;
    }

    console.log('🎬 Initializing SequentialVideoPlayer with SIMPLE configuration');
    console.log('🔍 DEBUG: containerRef.current exists:', containerRef.current);

    // Create callbacks directly in useEffect to avoid dependency issues
    const callbacks: VideoCallbacks = {
      onVideoStart: (video: VideoFile, index: number) => {
        console.log(`🎬 Video started: ${video.filename}`);
        setUIState(prev => ({ ...prev, isMutedForAutoplay: false, showAutoplayWarning: false }));
        onVideoStart?.(video, index);
      },
      onVideoEnd: (video: VideoFile, index: number) => {
        console.log(`✅ Video ended: ${video.filename}`);
        onVideoEnd?.(video, index);
      },
      onPlaybackComplete: () => {
        console.log('🎉 All videos completed!');
        setUIState(prev => ({ ...prev, isLoading: false }));
        onPlaybackComplete?.();
      },
      onVideoError: (error: string | import('../utils/sequentialVideoPlaybackSystem').PlaybackError, video: VideoFile) => {
        const errorMessage = typeof error === 'string' ? error : error.message;
        console.error(`❌ Video error: ${errorMessage}`);
        setErrors(prev => [...prev, errorMessage]);
        onError?.(errorMessage, video);
      },
      onProgressUpdate: (progress: number, videoIndex: number) => {
        onProgressUpdate?.(progress, videoIndex);
      },
      onStateChange: (state: VideoState | import('../utils/sequentialVideoPlaybackSystem').PlaybackState) => {
        // Convert PlaybackState to VideoState if needed for compatibility
        const compatibleState: VideoState = 'videos' in state && Array.isArray(state.videos) && state.videos.length > 0 && typeof state.videos[0] === 'object' && state.videos[0] !== null && 'queueIndex' in state.videos[0]
          ? {
              currentIndex: state.currentIndex,
              isPlaying: state.isPlaying,
              isTransitioning: state.isTransitioning,
              videos: state.videos.map(v => {
                const { queueIndex, preloaded, ...videoFile } = v as any;
                return videoFile;
              }),
              totalProgress: state.totalProgress,
              errors: 'errors' in state && Array.isArray(state.errors) 
                ? state.errors.map((err: any) => typeof err === 'string' ? err : err.message)
                : []
            }
          : state as VideoState;
        setPlaybackState(compatibleState);
      },
    };

    playbackSystemRef.current = new SequentialVideoPlaybackSystem(
      containerRef.current,
      callbacks
    );

    return () => {
      console.log('🧹 Destroying SequentialVideoPlaybackSystem');
      if (playbackSystemRef.current) {
        playbackSystemRef.current.destroy();
        playbackSystemRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // EMPTY dependency array - only run once on mount/unmount

  // Load videos when they change - use JSON.stringify for stable comparison
  const videosKey = useMemo(() => JSON.stringify(videos), [videos]);
  
  useEffect(() => {
    if (!playbackSystemRef.current) {
      console.log('🔍 DEBUG: playbackSystemRef.current is null, cannot load videos');
      return;
    }
    
    if (videos.length === 0) {
      console.log('🔍 DEBUG: videos.length is 0, no videos to load');
      return;
    }

    console.log(`🔄 Loading videos: ${videos.length} videos`);
    console.log('🔍 DEBUG: Videos to load:', videos);

    const loadVideos = async () => {
      setUIState(prev => ({ 
        ...prev, 
        isLoading: true, 
        loadingMessage: 'Loading video queue...' 
      }));

      try {
        await playbackSystemRef.current!.loadVideoQueue(videos);
        setUIState(prev => ({ ...prev, isLoading: false }));

        if (autoStart) {
          console.log('🚀 Auto-starting playback...');
          console.log('🔍 DEBUG: autoStart is true, will call handleStartPlayback in 100ms');
          setTimeout(() => {
            console.log('🔍 DEBUG: Timeout reached, calling handleStartPlayback()');
            handleStartPlayback();
          }, 100);
        } else {
          console.log('🔍 DEBUG: autoStart is false, user must manually start playback');
        }
      } catch (error) {
        console.error('Failed to load video queue:', error);
        setUIState(prev => ({ 
          ...prev, 
          isLoading: false,
          loadingMessage: '' 
        }));
      }
    };

    loadVideos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videosKey, autoStart]); // Remove handleStartPlayback dependency to fix hoisting issue

  // Playback control handlers - MOVED AFTER useEffect to fix hoisting
  const handleStartPlayback = useCallback(async () => {
    console.log('🔍 DEBUG: handleStartPlayback called');
    if (!playbackSystemRef.current) {
      console.log('🔍 DEBUG: playbackSystemRef.current is null, cannot start playback');
      return;
    }

    console.log('🔍 DEBUG: playbackSystemRef.current exists, setting loading state');
    setUIState(prev => ({ 
      ...prev, 
      isLoading: true, 
      loadingMessage: 'Starting sequential playback...' 
    }));

    try {
      console.log('🔍 DEBUG: Calling startPlayback() on the playback system');
      await playbackSystemRef.current.startPlayback();
      console.log('🔍 DEBUG: startPlayback() completed successfully');
      setUIState(prev => ({ ...prev, isLoading: false }));
    } catch (error) {
      console.error('🔍 DEBUG: startPlayback() failed with error:', error);
      console.error('Failed to start playback:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      if (errorMessage.toLowerCase().includes('autoplay') || errorMessage.toLowerCase().includes('interact')) {
        setUIState(prev => ({ 
          ...prev, 
          isLoading: false,
          loadingMessage: '',
          showAutoplayWarning: true
        }));
      } else {
        setUIState(prev => ({ 
          ...prev, 
          isLoading: false,
          loadingMessage: '' 
        }));
      }
    }
  }, []);

  const handlePausePlayback = useCallback(() => {
    if (!playbackSystemRef.current) return;
    playbackSystemRef.current.pause();
  }, []);

  const handleResumePlayback = useCallback(async () => {
    if (!playbackSystemRef.current) return;
    await playbackSystemRef.current.resume();
  }, []);

  const handleStopPlayback = useCallback(() => {
    if (!playbackSystemRef.current) return;
    
    setUIState(prev => ({ 
      ...prev, 
      isLoading: true, 
      loadingMessage: 'Stopping playback...' 
    }));

    playbackSystemRef.current.stop();
    setUIState(prev => ({ ...prev, isLoading: false }));
  }, []);

  const handleToggleFullscreen = useCallback(async () => {
    if (!playbackSystemRef.current) return;

    try {
      if (document.fullscreenElement) {
        await playbackSystemRef.current.exitFullscreen();
      } else {
        await playbackSystemRef.current.enterFullscreen();
      }
    } catch (error) {
      console.error('Failed to toggle fullscreen:', error);
    }
  }, []);

  const handleEnableSound = useCallback(() => {
    // Mark user interaction
    markUserInteraction();
    
    setUIState(prev => ({ 
      ...prev, 
      isMutedForAutoplay: false,
      showAutoplayWarning: false 
    }));
  }, []);

  const handleDismissAutoplayWarning = useCallback(() => {
    setUIState(prev => ({ ...prev, showAutoplayWarning: false }));
  }, []);

  // UI utilities
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getCurrentVideo = (): VideoFile | null => {
    return playbackState?.videos[playbackState.currentIndex] || null;
  };

  const getStatistics = () => {
    if (!playbackState) return null;
    return {
      totalVideos: playbackState.videos.length,
      currentIndex: playbackState.currentIndex,
      totalProgress: playbackState.totalProgress,
      errors: playbackState.errors.length,
    };
  };

  const stats = getStatistics();
  const currentVideo = getCurrentVideo();

  return (
    <Box className={className}>
      {/* Main Video Container */}
      <Card sx={{ position: 'relative', mb: 2 }}>
        <Box
          ref={containerRef}
          sx={{
            position: 'relative',
            width: '100%',
            minHeight: 400,
            backgroundColor: '#000',
            borderRadius: 1,
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {/* Loading overlay */}
          {uiState.isLoading && (
            <Fade in={true}>
              <Box
                sx={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  backgroundColor: 'rgba(0, 0, 0, 0.8)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 1000,
                }}
              >
                <Stack alignItems="center" spacing={2}>
                  <CircularProgress size={60} />
                  <Typography variant="h6" color="white">
                    {uiState.loadingMessage}
                  </Typography>
                </Stack>
              </Box>
            </Fade>
          )}

          {/* Status overlay */}
          {playbackState && !uiState.isLoading && (
            <Box
              sx={{
                position: 'absolute',
                top: 16,
                left: 16,
                zIndex: 100,
              }}
            >
              <Stack direction="row" spacing={1}>
                <Chip
                  icon={playbackState.isPlaying ? <PlayIcon /> : <PauseIcon />}
                  label={playbackState.isPlaying ? 'PLAYING' : 'PAUSED'}
                  color={playbackState.isPlaying ? 'success' : 'default'}
                  size="small"
                />
                
                {playbackState.isTransitioning && (
                  <Chip
                    label="TRANSITIONING"
                    color="warning"
                    size="small"
                  />
                )}

                {syncWithLabJack && (
                  <Chip
                    label="SYNC"
                    color="info"
                    size="small"
                  />
                )}
                
                {uiState.isMutedForAutoplay && (
                  <Chip
                    icon={<VolumeOffIcon />}
                    label="MUTED"
                    color="warning"
                    size="small"
                    onClick={handleEnableSound}
                    clickable
                  />
                )}
              </Stack>
            </Box>
          )}

          {/* Video info overlay */}
          {currentVideo && playbackState && !uiState.isLoading && (
            <Box
              sx={{
                position: 'absolute',
                top: 16,
                right: 16,
                zIndex: 100,
              }}
            >
              <Paper sx={{ p: 1, backgroundColor: 'rgba(0, 0, 0, 0.8)' }}>
                <Typography variant="caption" color="white">
                  Video {playbackState.currentIndex + 1} of {playbackState.videos.length}
                </Typography>
                <Typography variant="body2" color="white" sx={{ fontWeight: 'medium' }}>
                  {currentVideo.filename || currentVideo.name}
                </Typography>
              </Paper>
            </Box>
          )}

          {/* Autoplay Warning */}
          {uiState.showAutoplayWarning && (
            <Box
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                zIndex: 200,
                minWidth: 300,
              }}
            >
              <Fade in={true}>
                <Alert
                  severity="warning"
                  action={
                    <Stack direction="row" spacing={1}>
                      <Button
                        color="inherit"
                        size="small"
                        startIcon={<VolumeUpIcon />}
                        onClick={handleEnableSound}
                      >
                        Enable Sound
                      </Button>
                      <Button
                        color="inherit"
                        size="small"
                        onClick={handleDismissAutoplayWarning}
                      >
                        Dismiss
                      </Button>
                    </Stack>
                  }
                >
                  <Typography variant="subtitle2" gutterBottom>
                    Autoplay Policy Notice
                  </Typography>
                  <Typography variant="body2">
                    Click the play button to start video playback. Browser policies require user interaction.
                  </Typography>
                </Alert>
              </Fade>
            </Box>
          )}
          
          {/* Error notifications */}
          {errors.length > 0 && (
            <Box
              sx={{
                position: 'absolute',
                bottom: 16,
                left: 16,
                right: 16,
                zIndex: 100,
              }}
            >
              {errors.slice(-3).map((error, index) => (
                <Fade key={index} in={true}>
                  <Alert
                    severity="error"
                    sx={{ mb: 1 }}
                    onClose={() => {
                      setErrors(prev => prev.filter((_, i) => i !== index));
                    }}
                  >
                    {error}
                  </Alert>
                </Fade>
              ))}
            </Box>
          )}
        </Box>
      </Card>

      {/* Progress Section */}
      {showProgress && playbackState && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Sequential Playback Progress
            </Typography>
            
            <LinearProgress
              variant="determinate"
              value={playbackState.totalProgress}
              sx={{ height: 8, borderRadius: 4, mb: 1 }}
            />
            
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 2 }}>
              <Typography variant="body2">
                {Math.round(playbackState.totalProgress)}% Complete
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {playbackState.currentIndex + (playbackState.isPlaying ? 1 : 0)} / {playbackState.videos.length} videos
              </Typography>
            </Stack>

            {stats && (
              <Stack direction="row" spacing={2}>
                <Chip
                  label={`Current: ${stats.currentIndex + 1}`}
                  size="small"
                  color="primary"
                />
                <Chip
                  label={`Errors: ${stats.errors}`}
                  size="small"
                  color={stats.errors > 0 ? 'error' : 'default'}
                />
              </Stack>
            )}
          </CardContent>
        </Card>
      )}

      {/* Control Panel */}
      {showControls && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
              {!playbackState?.isPlaying ? (
                <Tooltip title="Start/Resume Playback">
                  <IconButton
                    onClick={playbackState ? handleResumePlayback : handleStartPlayback}
                    disabled={uiState.isLoading || (!playbackState && videos.length === 0)}
                    color="primary"
                    size="large"
                  >
                    <PlayIcon />
                  </IconButton>
                </Tooltip>
              ) : (
                <Tooltip title="Pause Playback">
                  <IconButton
                    onClick={handlePausePlayback}
                    color="primary"
                    size="large"
                  >
                    <PauseIcon />
                  </IconButton>
                </Tooltip>
              )}

              <Tooltip title="Stop Playback">
                <IconButton
                  onClick={handleStopPlayback}
                  disabled={!playbackState?.isPlaying}
                  color="error"
                >
                  <StopIcon />
                </IconButton>
              </Tooltip>

              <Tooltip title={document.fullscreenElement ? 'Exit Fullscreen' : 'Enter Fullscreen'}>
                <IconButton onClick={handleToggleFullscreen}>
                  {document.fullscreenElement ? <ExitFullscreenIcon /> : <FullscreenIcon />}
                </IconButton>
              </Tooltip>
              
              {uiState.isMutedForAutoplay && (
                <Tooltip title="Enable Sound">
                  <IconButton 
                    onClick={handleEnableSound}
                    color="warning"
                    sx={{
                      animation: 'pulse 2s infinite',
                      '@keyframes pulse': {
                        '0%': { opacity: 1 },
                        '50%': { opacity: 0.5 },
                        '100%': { opacity: 1 },
                      },
                    }}
                  >
                    <VolumeOffIcon />
                  </IconButton>
                </Tooltip>
              )}
            </Stack>

            {/* Simple status display */}
            {playbackState && (
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  {playbackState.isTransitioning 
                    ? 'Transitioning between videos...'
                    : playbackState.isPlaying
                    ? `Playing video ${playbackState.currentIndex + 1} of ${playbackState.videos.length}`
                    : `Ready to play ${playbackState.videos.length} videos`
                  }
                </Typography>
                
                {currentVideo && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    Current: {currentVideo.filename} ({formatTime(currentVideo.duration || 0)})
                  </Typography>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
});

export default SequentialVideoPlayer;