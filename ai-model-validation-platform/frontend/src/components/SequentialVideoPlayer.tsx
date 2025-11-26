/**
 * Sequential Video Player Component
 *
 * Automatically plays videos one after another with real-time timing tracking.
 * Key features:
 * - Auto-advancing playback without user interaction between videos
 * - Dynamic timing tracking with sequence-relative timestamps
 * - Status display and progress bars
 * - Backend synchronization for video transitions
 * - Error handling with retry logic
 * - Real-time heartbeat monitoring
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { apiService } from '../services/api';
import { VideoFile } from '../services/types';
import { safeVideoPlay, safeVideoPause, safeVideoStop, formatTime } from '../utils/videoUtils';
import logger from '../utils/safeErrorLogger';
import { clockSyncService } from '../services/clockSyncService';
import websocketService from '../services/websocketService';
import {
  VideoTimingMetadata,
  createVideoTimingMetadata,
  recordVideoPlaybackStart,
  recordVideoPlaybackEnd,
  getSequenceElapsedTimeMs,
  getVideoElapsedTimeMs,
  getUnixTimestampMs,
  calculateTransitionMetrics,
  mapDetectionToVideo,
  calculateSequenceTimingStats,
  exportTimingData
} from '../utils/videoTimingUtils';

interface SequentialVideoPlayerProps {
  videoPlaylist: VideoFile[];
  sequenceId: string;
  maxLatencyMs: number;
  onSequenceComplete: () => void;
  onError: (error: string) => void;
  onVideoStarted?: (videoId: string, videoIndex: number, startTime: number) => void;
  onVideoEnded?: (videoId: string, videoIndex: number, endTime: number) => void;
  // NOTE: fullScreenMode removed - parent container handles fullscreen CSS/layout
}

interface VideoTransitionState {
  videoId: string;
  startTime: number;
  endTime?: number;
  actualDuration?: number;
}

interface HeartbeatStatus {
  currentVideoId: string;
  currentVideoIndex: number;
  videoTime: number;
  sequenceElapsedTime: number;
  isPlaying: boolean;
}

const HEARTBEAT_INTERVAL_MS = 1000;
const MAX_RETRY_ATTEMPTS = 3;
const RETRY_DELAY_BASE_MS = 1000;

export const SequentialVideoPlayer = React.memo<SequentialVideoPlayerProps>(({
  videoPlaylist,
  sequenceId,
  maxLatencyMs,
  onSequenceComplete,
  onError,
  onVideoStarted,
  onVideoEnded
}) => {
  // State management
  const [currentVideoIndex, setCurrentVideoIndex] = useState(0);
  const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(videoPlaylist[0] || null);
  const [sequenceStartTimeMs, setSequenceStartTime] = useState<number | null>(null);
  const [sequenceStartUnixSeconds, setSequenceStartUnix] = useState<number | null>(null);
  const [videoStartTimeMs, setVideoStartTime] = useState<number | null>(null);
  const [videoStartUnixSeconds, setVideoStartUnix] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completedVideos, setCompletedVideos] = useState<string[]>([]);
  const [videoProgress, setVideoProgress] = useState(0);
  const [sequenceProgress, setSequenceProgress] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<number | null>(null);

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const transitionHistoryRef = useRef<VideoTransitionState[]>([]);
  const preloadVideoRef = useRef<HTMLVideoElement | null>(null);

  // Enhanced timing tracking refs
  const videoTimingsRef = useRef<VideoTimingMetadata[]>([]);
  const currentVideoTimingRef = useRef<VideoTimingMetadata | null>(null);
  const activeWaitPromiseRef = useRef<Promise<number> | null>(null);
  const lastVideoStartTimestampRef = useRef<number | null>(null);

  // FIX #1: Prevent re-initialization guard
  const hasInitializedRef = useRef(false);

  // FIX #3: Ref fallback for sequence start time
  const sequenceStartTimeRef = useRef<number | null>(null);

  // FIX #4: Prevent API calls after unmount
  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Reset monotonic tracking whenever a new sequence begins
    lastVideoStartTimestampRef.current = null;
  }, [sequenceId]);

  /**
   * Wait for the browser to fire the first playing event so we know frames are visible.
   * BUG FIX #1: Use AbortController to prevent memory leaks
   * BUG FIX #2: Prevent race conditions with promise ref
   */
  const waitForPlaybackStart = useCallback(
    (videoEl: HTMLVideoElement, timeoutMs = 5000): Promise<number> => {
      // FIX #2: Return existing promise if already waiting (Race Condition Protection)
      if (activeWaitPromiseRef.current) {
        console.log('[waitForPlaybackStart] Reusing existing promise');
        return activeWaitPromiseRef.current;
      }

      const promise = new Promise<number>((resolve, reject) => {
        if (!videoEl) {
          activeWaitPromiseRef.current = null;
          reject(new Error('Video element is not available'));
          return;
        }

        // If playback is already in progress (e.g., cached autoplay), resolve immediately
        if (!videoEl.paused && videoEl.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          activeWaitPromiseRef.current = null;
          resolve(getUnixTimestampMs());
          return;
        }

        // FIX #1: Use AbortController for automatic cleanup (Memory Leak Prevention)
        const abortController = new AbortController();
        const signal = abortController.signal;

        const cleanup = () => {
          activeWaitPromiseRef.current = null; // Clear promise ref on completion
          abortController.abort(); // Removes ALL listeners at once
          window.clearTimeout(timeoutId);
        };

        const handlePlaying = () => {
          cleanup();
          resolve(getUnixTimestampMs());
        };

        const handlePlaybackError = (event?: Event) => {
          cleanup();
          reject(
            new Error(
              `Playback interrupted before start${event?.type ? ` (${event.type})` : ''}`
            )
          );
        };

        const timeoutId = window.setTimeout(() => {
          cleanup();
          reject(new Error('Timed out waiting for video to begin playback'));
        }, timeoutMs);

        // FIX #1: All listeners use the same signal for automatic cleanup
        videoEl.addEventListener('playing', handlePlaying, { signal });
        videoEl.addEventListener('stalled', handlePlaybackError, { signal });
        videoEl.addEventListener('suspend', handlePlaybackError, { signal });
        videoEl.addEventListener('error', handlePlaybackError, { signal });
      });

      activeWaitPromiseRef.current = promise;
      return promise;
    },
    []
  );

  /**
   * Calculate exponential backoff delay for retries
   */
  const getRetryDelay = (attempt: number): number => {
    return Math.min(RETRY_DELAY_BASE_MS * Math.pow(2, attempt), 10000);
  };

  /**
   * Send video started event to backend
   * CRITICAL BUG FIX: Now properly sets video start timestamps BEFORE state updates
   * Enhanced with better error notifications
   */
  const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
    // CRITICAL FIX: Check if component is still mounted before making API call
    if (!isMountedRef.current) {
      console.log('⏭️ Skipping video-started event - component unmounted');
      return;
    }

    // CRITICAL VALIDATION: sequenceId is REQUIRED for timing tracking
    if (!sequenceId || sequenceId.trim() === '') {
      const criticalError = '❌ CRITICAL: Cannot send video-started event - no sequence ID. Timing data will be lost!';
      console.error(criticalError, { videoId, timestamp });
      logger.error('Missing sequence ID in sendVideoStartedEvent', new Error(criticalError), {
        context: 'SequentialVideoPlayer',
        videoId
      });
      // Set visible error for user
      const userMessage = 'Test synchronization error. Please stop and restart the test.';
      setError(userMessage);
      onError(userMessage);
      // Show alert for critical failure
      alert('Error: Test synchronization failed. Please stop and restart the test.');
      throw new Error(criticalError); // BLOCKING: Throw error to prevent silent failure
    }

    // FIX #2: Keep millisecond precision - DO NOT truncate with Math.floor()
    // Backend stores Float timestamps and Hungarian matcher requires ±100ms accuracy
    let normalizedTimestamp = timestamp;
    const lastStartTimestamp = lastVideoStartTimestampRef.current;
    if (lastStartTimestamp !== null && normalizedTimestamp <= lastStartTimestamp) {
      normalizedTimestamp = lastStartTimestamp + 5; // Bump by 5ms to preserve ordering
      console.warn(
        '⚠️ Adjusted video-start timestamp to maintain monotonic order',
        { videoId, originalTimestamp: timestamp, adjustedTimestamp: normalizedTimestamp }
      );
    }
    lastVideoStartTimestampRef.current = normalizedTimestamp;

    const startedAtSeconds = normalizedTimestamp / 1000;  // Full precision (e.g., 1763119711.531)
    const clientTimestamp = new Date(normalizedTimestamp).toISOString();
    const sequenceStartSeconds = sequenceStartUnixSeconds ?? startedAtSeconds;
    const sequenceElapsedSeconds = startedAtSeconds - sequenceStartSeconds;

    // Set timestamps immediately for accurate tracking
    setVideoStartUnix(startedAtSeconds);

    if (sequenceStartUnixSeconds === null) {
      setSequenceStartUnix(sequenceStartSeconds);
    }

    console.log('🎬 Sending video-started event to backend (with millisecond precision):', {
      sequenceId,
      videoId,
      startedAt: startedAtSeconds,  // Full precision logged
      url: `/api/video-sequences/${sequenceId}/video-started`
    });

    try {
      // CRITICAL FIX: Create AbortController for this request
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // CRITICAL FIX: Check mounted status again before fetch (race condition protection)
      if (!isMountedRef.current) {
        console.log('⏭️ Skipping video-started event - component unmounted before fetch');
        return;
      }

      // FIX #20: Backend Pydantic model expects camelCase fields
      // VideoStartedRequest expects: videoId (str), startedAt (float), clientTimestamp (str)
      // FIX #2: Send full precision timestamp (not truncated)
      const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
        videoId,
        startedAt: startedAtSeconds,  // Full millisecond precision
        sequenceElapsedTime: sequenceElapsedSeconds,
        clientTimestamp
      }, { signal: abortController.signal });

      console.log('✅ Video started event sent successfully');
      logger.info('Video started event sent', undefined, {
        context: 'SequentialVideoPlayer',
        videoId,
        timestamp,
        startedAt: startedAtSeconds
      });
    } catch (err) {
      // CRITICAL: Log detailed error for debugging
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      console.error('❌ FAILED to send video-started event:', {
        error: errorMessage,
        videoId,
        sequenceId,
        startedAt: startedAtSeconds
      });
      logger.error('Failed to send video started event to backend', err as Error, {
        context: 'SequentialVideoPlayer',
        videoId,
        sequenceId,
        startedAt: startedAtSeconds
      });

      // Show warning to user with actionable message
      const userWarning = `Failed to sync video ${currentVideoIndex + 1} start. Test results may be inaccurate.`;
      setError(userWarning);
      // Don't throw - allow playback to continue but log the failure
    }
  }, [sequenceId, sequenceStartUnixSeconds, currentVideoIndex, onError]);

  /**
   * Send video ended event to backend
   * CRITICAL BUG FIX: Now properly calculates and sends timing data
   * Enhanced with better error notifications
   */
  const sendVideoEndedEvent = useCallback(async (videoId: string, timestamp: number, actualPlaybackSeconds: number | null): Promise<string | null> => {
    // CRITICAL FIX: Check if component is still mounted before making API call
    if (!isMountedRef.current) {
      console.log('⏭️ Skipping video-ended event - component unmounted');
      return null;
    }

    // CRITICAL VALIDATION: sequenceId is REQUIRED for timing tracking
    if (!sequenceId || sequenceId.trim() === '') {
      const criticalError = '❌ CRITICAL: Cannot send video-ended event - no sequence ID. Timing data will be lost!';
      console.error(criticalError, { videoId, timestamp });
      logger.error('Missing sequence ID in sendVideoEndedEvent', new Error(criticalError), {
        context: 'SequentialVideoPlayer',
        videoId
      });
      // Show user warning
      const userWarning = 'Test synchronization error. Timing data may be incomplete.';
      setError(userWarning);
      // Return null to allow sequence to continue (user already saw videos)
      return null;
    }

    // FIX #2: Keep millisecond precision for video end times too
    const endedAtSeconds = timestamp / 1000;  // Full precision (no Math.floor)
    const clientTimestamp = new Date(timestamp).toISOString();
    const derivedDuration =
      videoStartUnixSeconds !== null ? Math.max(endedAtSeconds - videoStartUnixSeconds, 0) : null;
    const actualDuration = actualPlaybackSeconds ?? derivedDuration;
    const sequenceStartSeconds = sequenceStartUnixSeconds ?? endedAtSeconds;
    const sequenceElapsedSeconds = endedAtSeconds - sequenceStartSeconds;

    console.log('🎬 Sending video-ended event to backend (with millisecond precision):', {
      sequenceId,
      videoId,
      endedAt: endedAtSeconds,  // Full precision logged
      actualDuration,
      url: `/api/video-sequences/${sequenceId}/video-ended`
    });

    try {
      // CRITICAL FIX: Create AbortController for this request
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // CRITICAL FIX: Check mounted status again before fetch (race condition protection)
      if (!isMountedRef.current) {
        console.log('⏭️ Skipping video-ended event - component unmounted before fetch');
        return null;
      }

      const response = await apiService.post<{ nextVideoId?: string | null; next_video_id?: string | null }>(`/api/video-sequences/${sequenceId}/video-ended`, {
        videoId,
        endedAt: endedAtSeconds,
        actualDuration: actualDuration ?? undefined,
        sequenceElapsedTime: sequenceElapsedSeconds,
        clientTimestamp
      }, { signal: abortController.signal });

      console.log('✅ Video ended event sent successfully');

      // Backend may return nextVideoId or next_video_id
      const nextVideoId = response.nextVideoId || response.next_video_id || null;

      logger.info('Video ended event sent', undefined, {
        context: 'SequentialVideoPlayer',
        videoId,
        timestamp,
        endedAt: endedAtSeconds,
        nextVideoId
      });

      return nextVideoId;
    } catch (err) {
      // CRITICAL: Log detailed error for debugging
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      console.error('❌ FAILED to send video-ended event:', {
        error: errorMessage,
        videoId,
        sequenceId,
        endedAt: endedAtSeconds,
        actualDuration
      });
      logger.error('Failed to send video ended event to backend', err as Error, {
        context: 'SequentialVideoPlayer',
        videoId,
        sequenceId,
        endedAt: endedAtSeconds
      });

      // Show warning to user with actionable message
      const userWarning = `Failed to sync video ${currentVideoIndex + 1} end. Test results may be incomplete.`;
      setError(userWarning);
      // Continue sequence even if backend fails
      return null;
    }
  }, [sequenceId, videoStartUnixSeconds, sequenceStartUnixSeconds, currentVideoIndex]);

  /**
   * Send heartbeat with current status
   */
  const sendHeartbeat = useCallback(async () => {
    // CRITICAL FIX: Don't send heartbeat if component unmounted
    if (!isMountedRef.current) return;

    if (!currentVideo || !videoRef.current || !sequenceStartTimeMs) return;

    // BUG FIX #4: Use consistent high-precision timestamp
    const status: HeartbeatStatus = {
      currentVideoId: currentVideo.id,
      currentVideoIndex,
      videoTime: videoRef.current.currentTime,
      sequenceElapsedTime: getUnixTimestampMs() - sequenceStartTimeMs,
      isPlaying
    };

    try {
      await apiService.post(`/api/video-sequences/${sequenceId}/heartbeat`, status);
    } catch (err) {
      // Heartbeat failures are non-critical, just log
      logger.warn('Heartbeat failed', undefined, {
        context: 'SequentialVideoPlayer',
        error: err
      });
    }
  }, [currentVideo, currentVideoIndex, isPlaying, sequenceId, sequenceStartTimeMs]);

  /**
   * Start heartbeat monitoring
   */
  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }

    heartbeatIntervalRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);

    logger.debug('Heartbeat monitoring started', undefined, {
      context: 'SequentialVideoPlayer',
      interval: HEARTBEAT_INTERVAL_MS
    });
  }, [sendHeartbeat]);

  /**
   * Stop heartbeat monitoring
   */
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;

      logger.debug('Heartbeat monitoring stopped', undefined, {
        context: 'SequentialVideoPlayer'
      });
    }
  }, []);

  /**
   * Preload next video for smooth transitions
   */
  const preloadNextVideo = useCallback((index: number) => {
    if (index + 1 >= videoPlaylist.length) return;

    const nextVideo = videoPlaylist[index + 1];

    if (!preloadVideoRef.current) {
      preloadVideoRef.current = document.createElement('video');
      preloadVideoRef.current.preload = 'auto';
    }

    preloadVideoRef.current.src = nextVideo.url || '';

    logger.debug('Preloading next video', undefined, {
      context: 'SequentialVideoPlayer',
      videoId: nextVideo.id,
      index: index + 1
    });
  }, [videoPlaylist]);

  /**
   * Load and play a video with enhanced timing tracking
   */
  const loadAndPlayVideo = useCallback(async (video: VideoFile, index: number) => {
    console.log('🎬 loadAndPlayVideo called', {
      video,
      index,
      videoUrl: video.url,
      videoId: video.id,
      filename: video.filename
    });

    logger.info('Loading video', undefined, {
      context: 'SequentialVideoPlayer',
      videoId: video.id,
      index,
      url: video.url
    });

    if (!videoRef.current) {
      const error = 'Video element not available';
      console.error('❌ [SequentialVideoPlayer]', error);
      logger.error('Video element not available', new Error(error), { context: 'SequentialVideoPlayer' });
      onError(error);
      return;
    }

    // CRITICAL: Validate and fix video URL before attempting playback
    if (!video.url || video.url.trim() === '') {
      // Try to construct URL from filename if available
      if (video.filename) {
        const baseUrl = typeof window !== 'undefined' && window.location.hostname === 'localhost'
          ? 'http://localhost:8000'
          : 'http://155.138.239.131:8000';
        video.url = `${baseUrl}/uploads/${video.filename}`;
        console.log('🎬 Constructed video URL from filename:', video.url);
      } else {
        const error = `Video URL is missing or empty for: ${video.filename || video.id}`;
        console.error('❌ [SequentialVideoPlayer]', error, { video });
        logger.error('Missing video URL', new Error(error), {
          context: 'SequentialVideoPlayer',
          videoId: video.id,
          filename: video.filename
        });
        onError(error);
        return;
      }
    }

    // Fix video URL to use correct backend URL
    const originalUrl = video.url;
    if (video.url.includes('localhost') && typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
      // Fix localhost URLs when accessed from non-localhost
      const targetUrl = 'http://155.138.239.131:8000';
      video.url = video.url.replace(/http:\/\/(localhost|127\.0\.0\.1)(:\d+)?/, targetUrl);
      console.log('🎬 Fixed localhost URL:', originalUrl, '->', video.url);
    }

    console.log('🎬 Video URL validated:', video.url);

    // Test URL accessibility before loading
    try {
      console.log('🎬 Testing video URL accessibility:', video.url);
      const response = await fetch(video.url, { method: 'HEAD' });
      if (!response.ok) {
        throw new Error(`Video not accessible: HTTP ${response.status} ${response.statusText}`);
      }
      console.log('✅ Video URL is accessible:', response.status);
    } catch (fetchError) {
      const error = `Video file not accessible: ${video.filename || video.id}. ${fetchError instanceof Error ? fetchError.message : 'Unknown error'}`;
      console.error('❌ [SequentialVideoPlayer] Video URL not accessible:', video.url, fetchError);
      logger.error('Video URL not accessible', fetchError as Error, {
        context: 'SequentialVideoPlayer',
        videoId: video.id,
        url: video.url
      });
      onError(error);
      return;
    }

    setCurrentVideo(video);
    setCurrentVideoIndex(index);
    setVideoProgress(0);
    // FIX: Don't reset retry count here - it prevents retry exhaustion detection
    // setRetryCount(0); // ❌ REMOVED: Causes infinite loop by resetting counter before retry logic checks

    try {
      console.log('🎬 Starting video load process...');

      // FIX: Use local variable for immediate access (solves React setState async issue)
      let effectiveSequenceStartTime = sequenceStartTimeMs;

      // FIX #2: Initialize sequence start time if not set (handles first video + async state edge cases)
      if (!effectiveSequenceStartTime) {
        const startTime = getUnixTimestampMs();
        effectiveSequenceStartTime = startTime;  // ✅ Use immediately
        setSequenceStartTime(startTime);  // Update state for React
        sequenceStartTimeRef.current = startTime; // FIX #3: Store in ref for sync access
        logger.info('Sequence started with high-precision timing', undefined, {
          context: 'SequentialVideoPlayer',
          sequenceId,
          startTime: startTime.toFixed(2)
        });
      }

      // FIX #3: Fallback to ref if state hasn't updated yet (React async state)
      if (!effectiveSequenceStartTime && sequenceStartTimeRef.current) {
        effectiveSequenceStartTime = sequenceStartTimeRef.current;
        console.log('Using ref fallback for sequence start time:', effectiveSequenceStartTime);
      }

      // Calculate expected start time for this video
      // FIX: Use effectiveSequenceStartTime which is guaranteed to have a value
      if (!effectiveSequenceStartTime || typeof effectiveSequenceStartTime !== 'number') {
        throw new Error('Sequence start time not initialized - cannot calculate expected start time');
      }

      const previousVideoDurations = videoTimingsRef.current
        .filter(t => t.duration !== null)
        .map(t => t.duration!);
      const expectedStartTime = effectiveSequenceStartTime +
        previousVideoDurations.reduce((sum, duration) => sum + duration, 0);

      // Create timing metadata for this video
      const videoTiming = createVideoTimingMetadata(video.id, index, expectedStartTime);
      currentVideoTimingRef.current = videoTiming;

      logger.debug('Video loading started', undefined, {
        context: 'SequentialVideoPlayer',
        videoId: video.id,
        index,
        loadStartTime: videoTiming.loadStartTime.toFixed(2),
        expectedStartTime: expectedStartTime.toFixed(2)
      });

      // Load video source
      videoRef.current.src = video.url || '';
      videoRef.current.load();

      // Wait for metadata to load
      await new Promise<void>((resolve, reject) => {
        const timeoutId = setTimeout(() => {
          reject(new Error('Video metadata load timeout'));
        }, 10000);

        const handleLoad = () => {
          clearTimeout(timeoutId);
          videoRef.current?.removeEventListener('loadedmetadata', handleLoad);
          videoRef.current?.removeEventListener('error', handleError);
          resolve();
        };

        const handleError = () => {
          clearTimeout(timeoutId);
          videoRef.current?.removeEventListener('loadedmetadata', handleLoad);
          videoRef.current?.removeEventListener('error', handleError);
          reject(new Error(`Video load error: ${videoRef.current?.error?.message || 'Unknown error'}`));
        };

        videoRef.current?.addEventListener('loadedmetadata', handleLoad);
        videoRef.current?.addEventListener('error', handleError);
      });

      // Wait for video to be ready before playing (proper event-based approach)
      await new Promise<void>((resolve, reject) => {
        if (!videoRef.current) {
          reject(new Error('Video element not available'));
          return;
        }

        // Check if video is already ready
        if (videoRef.current.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
          resolve();
          return;
        }

        const timeoutId = setTimeout(() => {
          cleanup();
          reject(new Error('Video failed to load enough data'));
        }, 15000);

        const cleanup = () => {
          clearTimeout(timeoutId);
          videoRef.current?.removeEventListener('canplaythrough', onCanPlay);
          videoRef.current?.removeEventListener('error', onError);
        };

        const onCanPlay = () => {
          cleanup();
          resolve();
        };

        const onError = () => {
          cleanup();
          reject(new Error('Video failed to load'));
        };

        videoRef.current.addEventListener('canplaythrough', onCanPlay);
        videoRef.current.addEventListener('error', onError);
      });

      // Play video and wait for the first playing event (ensures frames are on screen)
      const playResult = await safeVideoPlay(videoRef.current, {
        userInitiated: true,
        forceMuted: false
      });

      // FIX #3: Detect autoplay blocking (Autoplay Blocking Detection)
      if (!playResult.success) {
        const errorMsg = playResult.error?.message || 'Unknown error';

        // Check for autoplay blocking - provide user-friendly error
        if (errorMsg.includes('NotAllowedError') ||
            errorMsg.includes('play() request was interrupted') ||
            errorMsg.includes('user didn\'t interact')) {
          throw new Error(
            'Browser blocked video autoplay. Please click the video to start playback.'
          );
        }

        throw new Error(`Failed to play video: ${errorMsg}`);
      }

      const playInitiatedAt = getUnixTimestampMs();
      const playbackStartedAt = await waitForPlaybackStart(videoRef.current);
      const declaredStartTimestamp = Math.min(playInitiatedAt, playbackStartedAt);

      // FIX #4: Send video-started event AFTER playback actually starts
      // This ensures accurate timing and SequenceVideoResult creation happens before detections
      await sendVideoStartedEvent(video.id, declaredStartTimestamp);

      // Record playback start with high precision (using actual playing timestamp)
      const updatedTiming = recordVideoPlaybackStart(
        currentVideoTimingRef.current,
        playbackStartedAt
      );
      currentVideoTimingRef.current = updatedTiming;

      // Set video start time for UI state
      setVideoStartTime(updatedTiming.playbackStartTime!);

      // Notify parent component of video start
      if (onVideoStarted) {
        onVideoStarted(video.id, index, updatedTiming.playbackStartTime!);
      }

      // Record transition state (legacy)
      transitionHistoryRef.current.push({
        videoId: video.id,
        startTime: updatedTiming.playbackStartTime!
      });

      // Log timing metrics
      logger.info('Video playback started with timing tracking', undefined, {
        context: 'SequentialVideoPlayer',
        videoId: video.id,
        index,
        playbackStartTime: updatedTiming.playbackStartTime!.toFixed(2),
        actualStartDelay: updatedTiming.actualStartDelay.toFixed(2),
        transitionDelay: updatedTiming.transitionDelay.toFixed(2)
      });

      // Calculate and log transition metrics if not first video
      if (index > 0 && videoTimingsRef.current.length > 0) {
        const previousTiming = videoTimingsRef.current[videoTimingsRef.current.length - 1];
        const transitionMetrics = calculateTransitionMetrics(previousTiming, updatedTiming);

        logger.debug('Video transition metrics', undefined, {
          context: 'SequentialVideoPlayer',
          fromVideoId: transitionMetrics.fromVideoId,
          toVideoId: transitionMetrics.toVideoId,
          gapDuration: transitionMetrics.gapDuration.toFixed(2),
          bufferingTime: transitionMetrics.bufferingTime.toFixed(2),
          loadTime: transitionMetrics.loadTime.toFixed(2)
        });
      }

      setIsPlaying(true);
      setError(null);

      // Preload next video
      preloadNextVideo(index);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error loading video';
      logger.error('Failed to load and play video', err as Error, {
        context: 'SequentialVideoPlayer',
        videoId: video.id,
        index
      });

      // Retry logic
      if (retryCount < MAX_RETRY_ATTEMPTS) {
        const delay = getRetryDelay(retryCount);
        logger.info(`Retrying video load in ${delay}ms`, undefined, {
          context: 'SequentialVideoPlayer',
          attempt: retryCount + 1,
          maxAttempts: MAX_RETRY_ATTEMPTS
        });

        setTimeout(() => {
          setRetryCount(prev => prev + 1);
          loadAndPlayVideo(video, index);
        }, delay);
      } else {
        setError(errorMessage);
        onError(errorMessage);
      }
    }
  }, [
    sequenceStartTimeMs,
    sequenceId,
    sendVideoStartedEvent,
    preloadNextVideo,
    retryCount,
    onError,
    onVideoStarted,
    waitForPlaybackStart
  ]);

  const formatTimingValue = useCallback((value?: number | null, suffix = ''): string => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return `${value.toFixed(2)}${suffix}`;
    }
    return `n/a${suffix}`;
  }, []);

  /**
   * Handle video end and advance to next video with enhanced timing tracking
   * FIX #1: Race Condition - Wait for cleanup before loading next video
   */
  const handleVideoEnd = useCallback(async () => {
    if (!currentVideo || !videoRef.current) return;

    setIsPlaying(false);

    const videoEnd = getUnixTimestampMs();

    // Record playback end with high precision
    if (currentVideoTimingRef.current) {
      const updatedTiming = recordVideoPlaybackEnd(currentVideoTimingRef.current);
      currentVideoTimingRef.current = updatedTiming;

      // FIX #2: Memory Leak - Limit timing history to last 100 entries
      videoTimingsRef.current.push(updatedTiming);
      if (videoTimingsRef.current.length > 100) {
        videoTimingsRef.current = videoTimingsRef.current.slice(-100);
      }

      logger.info('Video playback ended with timing tracking', undefined, {
        context: 'SequentialVideoPlayer',
        videoId: currentVideo.id,
        playbackEndTime: formatTimingValue(updatedTiming.playbackEndTime),
        duration: formatTimingValue(updatedTiming.duration),
        actualStartDelay: formatTimingValue(updatedTiming.actualStartDelay)
      });
    }

    // Update transition history (legacy)
    const currentTransition = transitionHistoryRef.current[transitionHistoryRef.current.length - 1];
    if (currentTransition) {
      currentTransition.endTime = videoEnd;
      currentTransition.actualDuration = videoStartTimeMs ? videoEnd - videoStartTimeMs : 0;
    }

    // Send video ended event and get next video ID
    const actualPlaybackSeconds = videoRef.current?.currentTime ?? null;
    const nextVideoId = await sendVideoEndedEvent(currentVideo.id, videoEnd, actualPlaybackSeconds);

    // Notify parent component of video end
    if (onVideoEnded) {
      onVideoEnded(currentVideo.id, currentVideoIndex, videoEnd);
    }

    // Mark video as completed
    setCompletedVideos(prev => [...prev, currentVideo.id]);

    logger.info('Video ended', undefined, {
      context: 'SequentialVideoPlayer',
      videoId: currentVideo.id,
      duration: videoRef.current.duration,
      nextVideoId
    });

    // Check if sequence is complete based on playlist position
    // FIXED: Don't rely solely on backend nextVideoId - check playlist directly
    const hasMoreVideos = currentVideoIndex < videoPlaylist.length - 1;

    if (!hasMoreVideos) {
      // Calculate and log final timing statistics
      const timingStats = calculateSequenceTimingStats(videoTimingsRef.current);

      logger.info('Sequence complete with timing statistics', undefined, {
        context: 'SequentialVideoPlayer',
        sequenceId,
        totalVideos: videoPlaylist.length,
        nextVideoId,
        currentVideoIndex,
          timingStats: timingStats && {
            totalExpectedDuration: formatTimingValue(timingStats.totalExpectedDuration),
            totalActualDuration: formatTimingValue(timingStats.totalActualDuration),
            totalLoadingDelay: formatTimingValue(timingStats.totalLoadingDelay),
            totalTransitionDelay: formatTimingValue(timingStats.totalTransitionDelay),
            averageLoadingDelay: formatTimingValue(timingStats.averageLoadingDelay),
            timingEfficiency: formatTimingValue(timingStats.timingEfficiency, '%')
          }
        });

      // Export timing data for debugging
      const timingData = exportTimingData(videoTimingsRef.current);
      logger.debug('Sequence timing export', undefined, {
        context: 'SequentialVideoPlayer',
        timingData
      });

      setVideoStartUnix(null);
      stopHeartbeat();
      onSequenceComplete();
      return;
    }

    // Advance to next video
    const nextIndex = currentVideoIndex + 1;
    const nextVideo = videoPlaylist[nextIndex];

    if (nextVideo) {
      console.log('🎬 Advancing to next video:', {
        nextVideoId,
        nextIndex,
        totalVideos: videoPlaylist.length,
        nextVideoUrl: nextVideo.url,
        nextVideoFilename: nextVideo.filename
      });

      // QUEEN'S PROTOCOL #38: STEP 1 - Persist state BEFORE advancing to next video
      try {
        const stateToSave = {
          currentVideoIndex: nextIndex,
          completedVideos: [...completedVideos, currentVideo.id],
          videoTimings: videoTimingsRef.current,  // SAVE FULL TIMING DATA
          sequenceStartUnixMs: sequenceStartUnixSeconds ? sequenceStartUnixSeconds * 1000 : null,
          sequenceId: sequenceId,
          timestamp: Date.now()
        };
        sessionStorage.setItem(`videoPlayer_${sequenceId}`, JSON.stringify(stateToSave));
        console.log('✅ State persisted before video transition');
      } catch (err) {
        console.warn('Failed to save state to sessionStorage:', err);
      }

      // FIX #1: Race Condition - Wait for cleanup before loading next video
      setVideoStartUnix(null);
      setRetryCount(0); // Reset retry counter on successful video completion
      await new Promise(resolve => setTimeout(resolve, 100)); // Small delay for cleanup
      loadAndPlayVideo(nextVideo, nextIndex);
    } else {
      console.error('❌ Next video not found in playlist at index:', nextIndex);
      logger.error('Next video missing from playlist', new Error('Next video not found'), {
        context: 'SequentialVideoPlayer',
        nextIndex,
        playlistLength: videoPlaylist.length
      });
      onSequenceComplete();
    }
  }, [
    currentVideo,
    currentVideoIndex,
    videoPlaylist,
    videoStartTimeMs,
    videoStartUnixSeconds,
    sendVideoEndedEvent,
    onSequenceComplete,
    loadAndPlayVideo,
    stopHeartbeat,
    sequenceId,
    onVideoEnded,
    formatTimingValue
  ]);

  /**
   * Update progress tracking
   */
  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current || !currentVideo) return;

    const currentTime = videoRef.current.currentTime;
    const duration = videoRef.current.duration;

    if (duration > 0) {
      setVideoProgress((currentTime / duration) * 100);
    }

    // Update sequence progress
    const sequenceVideoDuration = videoPlaylist.reduce((sum, v) => sum + (v.duration || 0), 0);
    const completedDuration = completedVideos.reduce((sum, id) => {
      const video = videoPlaylist.find(v => v.id === id);
      return sum + (video?.duration || 0);
    }, 0);
    const currentProgress = completedDuration + currentTime;

    if (sequenceVideoDuration > 0) {
      setSequenceProgress((currentProgress / sequenceVideoDuration) * 100);

      // Estimate time remaining
      const remainingDuration = sequenceVideoDuration - currentProgress;
      setEstimatedTimeRemaining(remainingDuration);
    }
  }, [currentVideo, videoPlaylist, completedVideos]);

  /**
   * CRITICAL FIX #1: Validate sequenceId BEFORE any playback can start
   * This effect runs FIRST and blocks playback if sequenceId is missing
   */
  useEffect(() => {
    // BLOCKING VALIDATION: sequenceId is REQUIRED for timing tracking
    if (!sequenceId || sequenceId.trim() === '') {
      const criticalError = '❌ CRITICAL: No sequence ID provided. Cannot track video timing. Please refresh and try again.';
      console.error(criticalError, {
        sequenceId,
        videoPlaylistLength: videoPlaylist.length
      });
      logger.error('Missing sequence ID - blocking playback', new Error(criticalError), {
        context: 'SequentialVideoPlayer',
        sequenceId,
        videoCount: videoPlaylist.length
      });
      setError(criticalError);
      onError(criticalError);
      // Show user-visible alert for critical error
      alert('Error: Test session not initialized. Please refresh and try again.');
      return;
    }
  }, [sequenceId, videoPlaylist.length, onError]);

  /**
   * Initialize clock synchronization on mount
   * CRITICAL: Must sync before any video playback to ensure accurate timestamps
   */
  useEffect(() => {
    async function syncClock() {
      try {
        const offset = await clockSyncService.synchronize();
        console.log(`✅ Clock synchronized. Offset: ${offset.toFixed(2)}ms`);

        const metrics = clockSyncService.getMetrics();
        if (metrics) {
          logger.info('Clock synchronization complete', undefined, {
            context: 'SequentialVideoPlayer',
            offset_ms: metrics.offset_ms,
            rtt_ms: metrics.rtt_ms,
            server_time: metrics.server_time_ms
          });
        }

        // Warn if drift is high
        if (!clockSyncService.isDriftAcceptable()) {
          const warning = `Clock drift detected (${offset.toFixed(2)}ms). Timestamps may be inaccurate.`;
          console.warn(warning);
          setError(warning);
        }
      } catch (error) {
        console.error('❌ Clock sync failed:', error);
        logger.error('Clock synchronization failed', error as Error, {
          context: 'SequentialVideoPlayer'
        });
        // Don't block playback - just warn user
        setError('Warning: Clock sync failed. Timestamps may be inaccurate.');
      }
    }

    syncClock();
  }, []); // Run once on mount

  /**
   * Initialize first video on mount
   * FIX #3: State Persistence - Save and restore state from sessionStorage
   */
  useEffect(() => {
    console.log('🎬 SequentialVideoPlayer MOUNTED', {
      videoPlaylistLength: videoPlaylist.length,
      sequenceId,
      firstVideoUrl: videoPlaylist[0]?.url,
      firstVideoId: videoPlaylist[0]?.id,
      firstVideoFilename: videoPlaylist[0]?.filename
    });

    logger.info('SequentialVideoPlayer component mounted', undefined, {
      context: 'SequentialVideoPlayer',
      videoCount: videoPlaylist.length,
      sequenceId
    });

    // PROTOCOL #39: Subscribe to lifecycle events with sequence ordering
    const unsubscribeLifecycle = websocketService.subscribeToLifecycleEvents((event: any) => {
      console.log(`🔔 Lifecycle event received: ${event.event} (seq: ${event.sequence_number})`, event);

      if (event.event === 'video_started') {
        logger.info('Video started lifecycle event', undefined, {
          context: 'SequentialVideoPlayer',
          videoId: event.videoId,
          sequenceNumber: event.sequence_number
        });
      } else if (event.event === 'video_ended') {
        logger.info('Video ended lifecycle event', undefined, {
          context: 'SequentialVideoPlayer',
          videoId: event.videoId,
          sequenceNumber: event.sequence_number
        });
      }
    });

    // FIX #3: State Persistence - Restore state from sessionStorage with validation
    // PROTOCOL #45: Enhanced validation for state recovery
    try {
      const savedState = sessionStorage.getItem(`videoPlayer_${sequenceId}`);
      if (savedState) {
        const state = JSON.parse(savedState);

        // VALIDATION 1: Check timestamp (don't restore if > 1 hour old)
        const age_ms = Date.now() - (state.timestamp || 0);
        const MAX_AGE_MS = 3600000; // 1 hour

        if (age_ms > MAX_AGE_MS) {
          console.warn(`Saved state too old (${Math.floor(age_ms / 60000)} minutes), discarding`);
          sessionStorage.removeItem(`videoPlayer_${sequenceId}`);
          return;
        }

        // VALIDATION 2: Check sequence_id matches
        // Note: In this component, sequenceId serves as the session identifier
        if (state.sequenceId && state.sequenceId !== sequenceId) {
          console.warn('Sequence ID mismatch, discarding saved state:', {
            saved: state.sequenceId,
            current: sequenceId
          });
          sessionStorage.removeItem(`videoPlayer_${sequenceId}`);
          return;
        }

        // VALIDATION 3: Check data integrity
        if (typeof state.currentVideoIndex !== 'number' ||
            !Array.isArray(state.completedVideos) ||
            !Array.isArray(state.videoTimings)) {
          console.warn('Saved state has invalid structure, discarding');
          sessionStorage.removeItem(`videoPlayer_${sequenceId}`);
          return;
        }

        // RESTORE: State is valid
        console.log('Restoring valid state:', {
          age_ms,
          currentVideoIndex: state.currentVideoIndex,
          completedVideos: state.completedVideos.length,
          videoTimings: state.videoTimings.length
        });

        setCurrentVideoIndex(state.currentVideoIndex || 0);
        setCompletedVideos(state.completedVideos || []);
        videoTimingsRef.current = state.videoTimings || [];

        if (state.sequenceStartUnixMs && typeof state.sequenceStartUnixMs === 'number') {
          setSequenceStartUnix(Math.floor(state.sequenceStartUnixMs / 1000));
        }

        console.log('✅ State restored successfully');
      }
    } catch (error) {
      console.error('Failed to restore state:', error);
      sessionStorage.removeItem(`videoPlayer_${sequenceId}`);
    }

    // Early exit if sequenceId validation failed (handled by previous useEffect)
    if (!sequenceId || sequenceId.trim() === '') {
      return;
    }

    // FIX #1: Prevent re-initialization if already started
    if (hasInitializedRef.current) {
      console.log('⏭️ Player already initialized, skipping re-initialization');
      return;
    }

    if (videoPlaylist.length === 0) {
      const error = 'No videos in playlist';
      console.error('❌ [SequentialVideoPlayer]', error);
      logger.error('No videos in playlist', new Error(error), { context: 'SequentialVideoPlayer' });
      setError(error);
      onError(error);
      return;
    }

    console.log('✅ Validation passed - sequenceId is valid:', sequenceId);

    // CRITICAL FIX: Always start first video on mount, don't check currentVideo state
    // because it's already initialized to videoPlaylist[0] in useState
    console.log('🎬 Starting first video...', videoPlaylist[0]);

    // Mark as initialized BEFORE starting playback
    hasInitializedRef.current = true;

    // Wrap in try-catch to catch any synchronous errors
    try {
      loadAndPlayVideo(videoPlaylist[0], 0);
      startHeartbeat();
    } catch (err) {
      const error = `Failed to start video playback: ${err instanceof Error ? err.message : 'Unknown error'}`;
      console.error('❌ [SequentialVideoPlayer]', error, err);
      logger.error('Failed to initialize playback', err as Error, { context: 'SequentialVideoPlayer' });
      // FIX: Don't reset initialization flag on error - causes re-initialization loop
      // hasInitializedRef.current = false; // ❌ REMOVED: Causes video 1↔2 loop
      setError(error);
      onError(error);
    }

    return () => {
      console.log('🎬 SequentialVideoPlayer UNMOUNTING');

      // CRITICAL FIX: Mark component as unmounted FIRST to prevent new API calls
      isMountedRef.current = false;

      // CRITICAL FIX: Abort any in-flight API requests
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
        console.log('✅ Aborted in-flight API requests');
      }

      // PROTOCOL #39: Unsubscribe from lifecycle events
      if (unsubscribeLifecycle) {
        unsubscribeLifecycle();
      }

      // QUEEN'S PROTOCOL #38: STEP 1 - Persist FIRST (while data still exists)
      try {
        const stateToSave = {
          currentVideoIndex,
          completedVideos,
          videoTimings: videoTimingsRef.current,  // HAS DATA!
          sequenceStartUnixMs: sequenceStartUnixSeconds ? sequenceStartUnixSeconds * 1000 : null,
          sequenceId: sequenceId,  // Use sequenceId as session identifier
          timestamp: Date.now()  // Add timestamp for validation
        };
        sessionStorage.setItem(`videoPlayer_${sequenceId}`, JSON.stringify(stateToSave));
        console.log('✅ State persisted before cleanup');
      } catch (err) {
        console.warn('Failed to save state to sessionStorage:', err);
      }

      // QUEEN'S PROTOCOL #38: STEP 2 - Clear SECOND (after persistence complete)
      videoTimingsRef.current = [];
      transitionHistoryRef.current = [];
      hasInitializedRef.current = false; // Reset initialization flag

      stopHeartbeat();
      if (videoRef.current) {
        safeVideoStop(videoRef.current);
      }
    };
  }, [sequenceId, sequenceStartUnixSeconds]); // FIX: Removed videoPlaylist to prevent re-initialization on reference change

  /**
   * Attach video event listeners
   */
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    video.addEventListener('ended', handleVideoEnd);
    video.addEventListener('timeupdate', handleTimeUpdate);

    return () => {
      video.removeEventListener('ended', handleVideoEnd);
      video.removeEventListener('timeupdate', handleTimeUpdate);
    };
  }, [handleVideoEnd, handleTimeUpdate]);

  // Calculate display values
  // FIX #4: Null Safety - Validate sequenceStartTimeMs before calculations
  const currentVideoTime = videoRef.current?.currentTime || 0;
  const currentVideoDuration = videoRef.current?.duration || 0;
  const sequenceElapsedTime = (sequenceStartTimeMs && typeof sequenceStartTimeMs === 'number')
    ? (getUnixTimestampMs() - sequenceStartTimeMs) / 1000
    : 0;

  // CLEAN VIDEO ONLY - no overlays, no status, no controls
  return (
    <div className="sequential-video-player-clean">
      <video
        ref={videoRef}
        className="video-player-clean"
        playsInline
        controls={false}
      />
      <style>{`
        .sequential-video-player-clean {
          width: 100%;
          height: 100%;
          background: black;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .video-player-clean {
          width: 100%;
          height: 100%;
          object-fit: contain;
          display: block;
          background: black;
        }
      `}</style>
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function to prevent unnecessary re-renders
  // Only re-render if these critical props change
  // NOTE: fullScreenMode removed from comparison - parent container handles fullscreen CSS
  return (
    prevProps.sequenceId === nextProps.sequenceId &&
    prevProps.videoPlaylist === nextProps.videoPlaylist &&
    prevProps.maxLatencyMs === nextProps.maxLatencyMs
  );
});

export default SequentialVideoPlayer;
