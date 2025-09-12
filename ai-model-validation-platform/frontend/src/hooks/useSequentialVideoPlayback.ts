/**
 * Sequential Video Playback Hook
 * 
 * Custom React hook for managing sequential video playback with:
 * - Automatic fullscreen functionality
 * - Video queue management
 * - Progress tracking
 * - Error handling and recovery
 * - LabJack synchronization
 */

import { useRef, useCallback, useEffect, useState } from 'react';
import {
  SequentialVideoPlaybackSystem,
  PlaybackConfiguration,
  PlaybackState,
  PlaybackError,
  VideoQueueItem,
} from '../utils/sequentialVideoPlaybackSystem';
import { VideoFile } from '../services/types';

export interface UseSequentialVideoPlaybackOptions {
  config?: Partial<PlaybackConfiguration>;
  onVideoStart?: (video: VideoQueueItem, index: number) => void;
  onVideoEnd?: (video: VideoQueueItem, index: number) => void;
  onPlaybackComplete?: () => void;
  onError?: (error: PlaybackError) => void;
  onProgressUpdate?: (progress: number, videoIndex: number) => void;
  onStateChange?: (state: PlaybackState) => void;
  autoCleanup?: boolean;
}

export interface SequentialVideoPlaybackControls {
  loadVideoQueue: (videos: VideoFile[]) => Promise<void>;
  startPlayback: () => Promise<void>;
  pausePlayback: () => void;
  resumePlayback: () => Promise<void>;
  stopPlayback: () => Promise<void>;
  advanceToNext: () => Promise<void>;
  goToPrevious: () => Promise<void>;
  jumpToVideo: (index: number) => Promise<void>;
  enterFullscreen: () => Promise<void>;
  exitFullscreen: () => Promise<void>;
  toggleFullscreen: () => Promise<void>;
  getCurrentVideo: () => VideoQueueItem | null;
  getStatistics: () => any;
  updateConfig: (config: Partial<PlaybackConfiguration>) => void;
  destroy: () => void;
}

export interface SequentialVideoPlaybackState {
  playbackState: PlaybackState | null;
  isReady: boolean;
  isLoading: boolean;
  errors: PlaybackError[];
  loadingMessage: string;
}

export function useSequentialVideoPlayback(
  containerRef: React.RefObject<HTMLElement>,
  options: UseSequentialVideoPlaybackOptions = {}
): [SequentialVideoPlaybackState, SequentialVideoPlaybackControls] {
  const {
    config = {},
    onVideoStart,
    onVideoEnd,
    onPlaybackComplete,
    onError,
    onProgressUpdate,
    onStateChange,
    autoCleanup = true,
  } = options;

  const playbackSystemRef = useRef<SequentialVideoPlaybackSystem | null>(null);
  
  const [state, setState] = useState<SequentialVideoPlaybackState>({
    playbackState: null,
    isReady: false,
    isLoading: false,
    errors: [],
    loadingMessage: '',
  });

  // Initialize playback system when container is available
  useEffect(() => {
    if (!containerRef.current || playbackSystemRef.current) return;

    const defaultConfig: Partial<PlaybackConfiguration> = {
      autoAdvance: true,
      loopPlayback: false,
      randomOrder: false,
      preloadNext: true,
      fullscreenMode: true,
      autoFullscreen: false,
      transitionDelay: 500,
      maxRetries: 3,
      enableHardwareAcceleration: true,
      syncWithExternalSignals: false,
      ...config,
    };

    const callbacks = {
      onVideoStart: (video: VideoQueueItem, index: number) => {
        onVideoStart?.(video, index);
      },
      onVideoEnd: (video: VideoQueueItem, index: number) => {
        onVideoEnd?.(video, index);
      },
      onPlaybackComplete: () => {
        setState(prev => ({
          ...prev,
          isLoading: false,
          loadingMessage: '',
        }));
        onPlaybackComplete?.();
      },
      onVideoError: (error: PlaybackError, video: VideoQueueItem) => {
        setState(prev => ({
          ...prev,
          errors: [...prev.errors, error],
        }));
        onError?.(error);
      },
      onProgressUpdate: (progress: number, videoIndex: number) => {
        onProgressUpdate?.(progress, videoIndex);
      },
      onStateChange: (playbackState: PlaybackState) => {
        setState(prev => ({
          ...prev,
          playbackState,
        }));
        onStateChange?.(playbackState);
      },
      onFullscreenChange: (isFullscreen: boolean) => {
        console.log('Fullscreen state changed:', isFullscreen);
      },
    };

    try {
      playbackSystemRef.current = new SequentialVideoPlaybackSystem(
        containerRef.current,
        defaultConfig,
        callbacks
      );

      setState(prev => ({
        ...prev,
        isReady: true,
        isLoading: false,
      }));
    } catch (error) {
      console.error('Failed to initialize playback system:', error);
      setState(prev => ({
        ...prev,
        isReady: false,
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: -1,
          errorType: 'load',
          message: error instanceof Error ? error.message : 'Initialization failed',
          timestamp: Date.now(),
          recoverable: false,
        }],
      }));
    }
  }, [containerRef.current]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (autoCleanup && playbackSystemRef.current) {
        playbackSystemRef.current.destroy();
        playbackSystemRef.current = null;
      }
    };
  }, [autoCleanup]);

  // Control functions
  const loadVideoQueue = useCallback(async (videos: VideoFile[]): Promise<void> => {
    if (!playbackSystemRef.current) {
      throw new Error('Playback system not initialized');
    }

    setState(prev => ({
      ...prev,
      isLoading: true,
      loadingMessage: 'Loading video queue...',
      errors: [],
    }));

    try {
      await playbackSystemRef.current.loadVideoQueue(videos);
      setState(prev => ({
        ...prev,
        isLoading: false,
        loadingMessage: '',
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load video queue';
      setState(prev => ({
        ...prev,
        isLoading: false,
        loadingMessage: '',
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: -1,
          errorType: 'load',
          message: errorMessage,
          timestamp: Date.now(),
          recoverable: true,
        }],
      }));
      throw error;
    }
  }, []);

  const startPlayback = useCallback(async (): Promise<void> => {
    if (!playbackSystemRef.current) {
      throw new Error('Playback system not initialized');
    }

    setState(prev => ({
      ...prev,
      isLoading: true,
      loadingMessage: 'Starting sequential playback...',
    }));

    try {
      await playbackSystemRef.current.startPlayback();
      setState(prev => ({
        ...prev,
        isLoading: false,
        loadingMessage: '',
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to start playback';
      setState(prev => ({
        ...prev,
        isLoading: false,
        loadingMessage: '',
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: -1,
          errorType: 'play',
          message: errorMessage,
          timestamp: Date.now(),
          recoverable: true,
        }],
      }));
      throw error;
    }
  }, []);

  const pausePlayback = useCallback((): void => {
    if (!playbackSystemRef.current) return;
    playbackSystemRef.current.pause();
  }, []);

  const resumePlayback = useCallback(async (): Promise<void> => {
    if (!playbackSystemRef.current) {
      throw new Error('Playback system not initialized');
    }

    try {
      await playbackSystemRef.current.resume();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to resume playback';
      setState(prev => ({
        ...prev,
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: -1,
          errorType: 'play',
          message: errorMessage,
          timestamp: Date.now(),
          recoverable: true,
        }],
      }));
      throw error;
    }
  }, []);

  const stopPlayback = useCallback(async (): Promise<void> => {
    if (!playbackSystemRef.current) return;

    setState(prev => ({
      ...prev,
      isLoading: true,
      loadingMessage: 'Stopping playback...',
    }));

    try {
      playbackSystemRef.current.stop();
      setState(prev => ({
        ...prev,
        isLoading: false,
        loadingMessage: '',
      }));
    } catch (error) {
      console.warn('Error stopping playback:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
        loadingMessage: '',
      }));
    }
  }, []);

  const advanceToNext = useCallback(async (): Promise<void> => {
    if (!playbackSystemRef.current) return;
    
    try {
      playbackSystemRef.current.next();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to advance to next video';
      setState(prev => ({
        ...prev,
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: -1,
          errorType: 'transition',
          message: errorMessage,
          timestamp: Date.now(),
          recoverable: true,
        }],
      }));
    }
  }, []);

  const goToPrevious = useCallback(async (): Promise<void> => {
    if (!playbackSystemRef.current) return;
    
    try {
      playbackSystemRef.current.previous();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to go to previous video';
      setState(prev => ({
        ...prev,
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: -1,
          errorType: 'transition',
          message: errorMessage,
          timestamp: Date.now(),
          recoverable: true,
        }],
      }));
    }
  }, []);

  const jumpToVideo = useCallback(async (index: number): Promise<void> => {
    if (!playbackSystemRef.current) return;
    
    try {
      playbackSystemRef.current.jumpTo(index);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to jump to video';
      setState(prev => ({
        ...prev,
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: index,
          errorType: 'transition',
          message: errorMessage,
          timestamp: Date.now(),
          recoverable: true,
        }],
      }));
    }
  }, []);

  const enterFullscreen = useCallback(async (): Promise<void> => {
    if (!playbackSystemRef.current) return;
    
    try {
      await playbackSystemRef.current.enterFullscreen();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to enter fullscreen';
      setState(prev => ({
        ...prev,
        errors: [...prev.errors, {
          videoId: '',
          videoIndex: -1,
          errorType: 'fullscreen',
          message: errorMessage,
          timestamp: Date.now(),
          recoverable: false,
        }],
      }));
    }
  }, []);

  const exitFullscreen = useCallback(async (): Promise<void> => {
    if (!playbackSystemRef.current) return;
    
    try {
      await playbackSystemRef.current.exitFullscreen();
    } catch (error) {
      console.warn('Failed to exit fullscreen:', error);
    }
  }, []);

  const toggleFullscreen = useCallback(async (): Promise<void> => {
    if (state.playbackState?.isFullscreen) {
      await exitFullscreen();
    } else {
      await enterFullscreen();
    }
  }, [state.playbackState?.isFullscreen, enterFullscreen, exitFullscreen]);

  const getCurrentVideo = useCallback((): VideoQueueItem | null => {
    if (!playbackSystemRef.current) return null;
    return playbackSystemRef.current.getCurrentVideo();
  }, []);

  const getStatistics = useCallback(() => {
    if (!playbackSystemRef.current) return null;
    return {
      totalVideos: state.playbackState?.videos?.length || 0,
      currentIndex: state.playbackState?.currentIndex || 0,
      totalProgress: state.playbackState?.totalProgress || 0,
      errors: state.errors?.length || 0,
      isPlaying: state.playbackState?.isPlaying || false,
      isTransitioning: state.playbackState?.isTransitioning || false
    };
  }, [state]);

  const updateConfig = useCallback((newConfig: Partial<PlaybackConfiguration>): void => {
    if (!playbackSystemRef.current) return;
    // Simple system doesn't support runtime config updates
    console.log('Config update not supported in simple system:', newConfig);
  }, []);

  const destroy = useCallback((): void => {
    if (playbackSystemRef.current) {
      playbackSystemRef.current.destroy();
      playbackSystemRef.current = null;
      setState(prev => ({
        ...prev,
        playbackState: null,
        isReady: false,
      }));
    }
  }, []);

  // Clear old errors periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setState(prev => ({
        ...prev,
        errors: prev.errors.filter(error => 
          Date.now() - error.timestamp < 30000 // Keep errors for 30 seconds
        ),
      }));
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const controls: SequentialVideoPlaybackControls = {
    loadVideoQueue,
    startPlayback,
    pausePlayback,
    resumePlayback,
    stopPlayback,
    advanceToNext,
    goToPrevious,
    jumpToVideo,
    enterFullscreen,
    exitFullscreen,
    toggleFullscreen,
    getCurrentVideo,
    getStatistics,
    updateConfig,
    destroy,
  };

  return [state, controls];
}

export default useSequentialVideoPlayback;