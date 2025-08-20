/**
 * Custom React Hook for Video Player
 * Provides safe video operations with automatic cleanup
 * and proper error handling
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import {
  safeVideoPlay,
  safeVideoPause,
  safeVideoStop,
  setVideoSource,
  cleanupVideoElement,
  isVideoReady,
  addVideoEventListeners,
  VideoPlayResult,
} from '../utils/videoUtils';

export interface VideoPlayerState {
  isPlaying: boolean;
  isPaused: boolean;
  isLoading: boolean;
  duration: number;
  currentTime: number;
  volume: number;
  muted: boolean;
  error: string | null;
  videoSize: {
    width: number;
    height: number;
  };
}

export interface VideoPlayerControls {
  play: () => Promise<VideoPlayResult>;
  pause: () => void;
  stop: () => void;
  seek: (time: number) => void;
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  loadVideo: (src: string) => Promise<void>;
}

export interface UseVideoPlayerOptions {
  onTimeUpdate?: (currentTime: number) => void;
  onPlay?: () => void;
  onPause?: () => void;
  onEnded?: () => void;
  onError?: (error: string) => void;
  autoCleanup?: boolean;
}

export function useVideoPlayer(options: UseVideoPlayerOptions = {}) {
  const {
    onTimeUpdate,
    onPlay,
    onPause,
    onEnded,
    onError,
    autoCleanup = true,
  } = options;

  const videoRef = useRef<HTMLVideoElement>(null);
  
  const [state, setState] = useState<VideoPlayerState>({
    isPlaying: false,
    isPaused: true,
    isLoading: false,
    duration: 0,
    currentTime: 0,
    volume: 1,
    muted: false,
    error: null,
    videoSize: { width: 0, height: 0 },
  });

  // Initialize video event listeners
  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    const handleLoadedMetadata = () => {
      if (isVideoReady(videoElement)) {
        setState(prev => ({
          ...prev,
          duration: videoElement.duration,
          videoSize: {
            width: videoElement.videoWidth,
            height: videoElement.videoHeight,
          },
          isLoading: false,
          error: null,
        }));
      }
    };

    const handleTimeUpdate = () => {
      const currentTime = videoElement.currentTime;
      setState(prev => ({ ...prev, currentTime }));
      onTimeUpdate?.(currentTime);
    };

    const handlePlay = () => {
      setState(prev => ({ ...prev, isPlaying: true, isPaused: false }));
      onPlay?.();
    };

    const handlePause = () => {
      setState(prev => ({ ...prev, isPlaying: false, isPaused: true }));
      onPause?.();
    };

    const handleEnded = () => {
      setState(prev => ({ ...prev, isPlaying: false, isPaused: true }));
      onEnded?.();
    };

    const handleError = (event: Event) => {
      const errorMessage = videoElement.error?.message || 'Video playback error';
      setState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
      onError?.(errorMessage);
    };

    const handleLoadStart = () => {
      setState(prev => ({ ...prev, isLoading: true, error: null }));
    };

    const handleVolumeChange = () => {
      setState(prev => ({
        ...prev,
        volume: videoElement.volume,
        muted: videoElement.muted,
      }));
    };

    const cleanupListeners = addVideoEventListeners(videoElement, [
      { event: 'loadedmetadata', handler: handleLoadedMetadata },
      { event: 'timeupdate', handler: handleTimeUpdate },
      { event: 'play', handler: handlePlay },
      { event: 'pause', handler: handlePause },
      { event: 'ended', handler: handleEnded },
      { event: 'error', handler: handleError },
      { event: 'loadstart', handler: handleLoadStart },
      { event: 'volumechange', handler: handleVolumeChange },
    ]);

    return () => {
      cleanupListeners();
      if (autoCleanup) {
        cleanupVideoElement(videoElement);
      }
    };
  }, [onTimeUpdate, onPlay, onPause, onEnded, onError, autoCleanup]);

  // Control functions
  const controls: VideoPlayerControls = {
    play: useCallback(async () => {
      const result = await safeVideoPlay(videoRef.current);
      if (!result.success && result.error) {
        setState(prev => ({ ...prev, error: result.error!.message }));
        onError?.(result.error.message);
      }
      return result;
    }, [onError]),

    pause: useCallback(() => {
      safeVideoPause(videoRef.current);
    }, []),

    stop: useCallback(() => {
      safeVideoStop(videoRef.current);
    }, []),

    seek: useCallback((time: number) => {
      const videoElement = videoRef.current;
      if (!videoElement) return;

      try {
        videoElement.currentTime = Math.max(0, Math.min(time, state.duration));
      } catch (error) {
        console.warn('Seek failed:', error);
        setState(prev => ({ ...prev, error: 'Seek operation failed' }));
      }
    }, [state.duration]),

    setVolume: useCallback((volume: number) => {
      const videoElement = videoRef.current;
      if (!videoElement) return;

      try {
        videoElement.volume = Math.max(0, Math.min(1, volume));
      } catch (error) {
        console.warn('Volume change failed:', error);
      }
    }, []),

    toggleMute: useCallback(() => {
      const videoElement = videoRef.current;
      if (!videoElement) return;

      try {
        videoElement.muted = !videoElement.muted;
      } catch (error) {
        console.warn('Mute toggle failed:', error);
      }
    }, []),

    loadVideo: useCallback(async (src: string) => {
      const videoElement = videoRef.current;
      if (!videoElement) {
        throw new Error('Video element not available');
      }

      setState(prev => ({ ...prev, isLoading: true, error: null }));
      
      try {
        await setVideoSource(videoElement, src);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to load video';
        setState(prev => ({ ...prev, error: errorMessage, isLoading: false }));
        onError?.(errorMessage);
        throw error;
      }
    }, [onError]),
  };

  return {
    videoRef,
    state,
    controls,
  };
}

export default useVideoPlayer;