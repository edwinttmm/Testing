/**
 * Video Timing Utilities for Multi-Video Sequences
 *
 * Provides high-precision timing tracking for video sequences with dynamic
 * adjustment for loading delays, buffering, and transitions between videos.
 *
 * Key Features:
 * - High-precision timing using performance.now()
 * - Dynamic delay tracking and compensation
 * - Video transition metadata
 * - Detection-to-video mapping
 * - Sequence timeline calculations
 */

export interface VideoTimingMetadata {
  videoId: string;
  videoIndex: number;
  loadStartTime: number;
  playbackStartTime: number | null;
  playbackEndTime: number | null;
  expectedStartTime: number;
  actualStartDelay: number;
  transitionDelay: number;
  duration: number | null;
}

export interface SequenceTimingState {
  sequenceStartTime: number | null;
  currentVideoIndex: number;
  videoTimings: VideoTimingMetadata[];
  totalExpectedDuration: number;
  totalActualDuration: number;
  cumulativeDelay: number;
}

export interface DetectionTimingResult {
  detectionTimestamp: number;
  sequenceElapsedTime: number;
  videoId: string;
  videoIndex: number;
  videoElapsedTime: number;
  isWithinVideoPlayback: boolean;
  estimatedLoadingDelay: number;
}

export interface TransitionMetrics {
  fromVideoId: string;
  toVideoId: string;
  gapDuration: number;
  bufferingTime: number;
  loadTime: number;
}

/**
 * Get current Unix timestamp in milliseconds synchronized with server clock.
 *
 * Returns Unix epoch time (ms since Jan 1, 1970) for synchronization with backend.
 * Now uses clock sync service to adjust for client-server time offset.
 *
 * RENAMED from getHighPrecisionTimestamp to getUnixTimestampMs for clarity.
 * This function does NOT return performance.now() - it returns Date.now() + offset.
 *
 * Backend expects Unix epoch for proper ground truth calculation.
 *
 * CRITICAL: Import clockSyncService to use synchronized time.
 */
export function getUnixTimestampMs(): number {
  // Import here to avoid circular dependencies
  try {
    // Try to use synchronized time if available
    const { clockSyncService } = require('../services/clockSyncService');
    return clockSyncService.getSynchronizedTime();
  } catch (error) {
    // Fallback to unsynchronized time if service not available
    console.warn('Clock sync service not available, using unsynchronized time');
    return Date.now();
  }
}

// Backward compatibility exports (deprecated)
/** @deprecated Use getUnixTimestampMs instead */
export const getHighPrecisionTimestamp = getUnixTimestampMs;

/**
 * Calculate sequence elapsed time since start (in milliseconds)
 */
export function getSequenceElapsedTimeMs(sequenceStartTimeMs: number | null): number {
  if (!sequenceStartTimeMs) return 0;
  return getUnixTimestampMs() - sequenceStartTimeMs;
}

/** @deprecated Use getSequenceElapsedTimeMs instead */
export const getSequenceElapsedTime = getSequenceElapsedTimeMs;

/**
 * Calculate video elapsed time since video started playing (in milliseconds)
 */
export function getVideoElapsedTimeMs(videoStartTimeMs: number | null): number {
  if (!videoStartTimeMs) return 0;
  return getUnixTimestampMs() - videoStartTimeMs;
}

/** @deprecated Use getVideoElapsedTimeMs instead */
export const getVideoElapsedTime = getVideoElapsedTimeMs;

/**
 * Initialize a new video timing metadata object
 */
export function createVideoTimingMetadata(
  videoId: string,
  videoIndex: number,
  expectedStartTime: number
): VideoTimingMetadata {
  const loadStartTime = getUnixTimestampMs();

  return {
    videoId,
    videoIndex,
    loadStartTime,
    playbackStartTime: null,
    playbackEndTime: null,
    expectedStartTime,
    actualStartDelay: 0,
    transitionDelay: 0,
    duration: null
  };
}

/**
 * Record video playback start and calculate delays
 */
export function recordVideoPlaybackStart(
  timing: VideoTimingMetadata,
  playbackStartOverride?: number
): VideoTimingMetadata {
  const playbackStartTime = playbackStartOverride ?? getUnixTimestampMs();
  const actualStartDelay = playbackStartTime - timing.expectedStartTime;
  const transitionDelay = playbackStartTime - timing.loadStartTime;

  return {
    ...timing,
    playbackStartTime,
    actualStartDelay,
    transitionDelay
  };
}

/**
 * Record video playback end and calculate actual duration
 */
export function recordVideoPlaybackEnd(
  timing: VideoTimingMetadata
): VideoTimingMetadata {
  const playbackEndTime = getUnixTimestampMs();
  const duration = timing.playbackStartTime
    ? playbackEndTime - timing.playbackStartTime
    : null;

  return {
    ...timing,
    playbackEndTime,
    duration
  };
}

/**
 * Calculate video transition delay between two videos
 */
export function calculateVideoTransitionDelay(
  previousVideo: VideoTimingMetadata,
  currentVideo: VideoTimingMetadata
): number {
  if (!previousVideo.playbackEndTime || !currentVideo.playbackStartTime) {
    return 0;
  }

  return currentVideo.playbackStartTime - previousVideo.playbackEndTime;
}

/**
 * Calculate transition metrics for a video switch
 */
export function calculateTransitionMetrics(
  previousVideo: VideoTimingMetadata,
  currentVideo: VideoTimingMetadata
): TransitionMetrics {
  const gapDuration = calculateVideoTransitionDelay(previousVideo, currentVideo);
  const loadTime = currentVideo.playbackStartTime
    ? currentVideo.playbackStartTime - currentVideo.loadStartTime
    : 0;

  // Estimate buffering time (time between expected start and actual start)
  const bufferingTime = Math.max(0, currentVideo.actualStartDelay - loadTime);

  return {
    fromVideoId: previousVideo.videoId,
    toVideoId: currentVideo.videoId,
    gapDuration,
    bufferingTime,
    loadTime
  };
}

/**
 * Map a detection timestamp to the correct video in the sequence
 *
 * @param detectionTimestamp - Absolute timestamp when detection occurred
 * @param sequenceStartTime - When the sequence started
 * @param videoTimings - Array of video timing metadata
 * @returns Detection timing result with video mapping
 */
export function mapDetectionToVideo(
  detectionTimestamp: number,
  sequenceStartTime: number,
  videoTimings: VideoTimingMetadata[]
): DetectionTimingResult | null {
  if (videoTimings.length === 0) {
    return null;
  }

  const sequenceElapsedTime = detectionTimestamp - sequenceStartTime;

  // Find which video was playing at this timestamp
  for (let i = 0; i < videoTimings.length; i++) {
    const timing = videoTimings[i];

    // Skip videos that haven't started yet
    if (!timing.playbackStartTime) {
      continue;
    }

    // Check if detection falls within this video's playback window
    const videoStartTime = timing.playbackStartTime;
    const videoEndTime = timing.playbackEndTime || getUnixTimestampMs();

    if (detectionTimestamp >= videoStartTime && detectionTimestamp <= videoEndTime) {
      const videoElapsedTime = detectionTimestamp - videoStartTime;

      return {
        detectionTimestamp,
        sequenceElapsedTime,
        videoId: timing.videoId,
        videoIndex: timing.videoIndex,
        videoElapsedTime,
        isWithinVideoPlayback: true,
        estimatedLoadingDelay: timing.actualStartDelay
      };
    }

    // Check if detection falls in gap between videos
    if (i < videoTimings.length - 1) {
      const nextTiming = videoTimings[i + 1];
      if (nextTiming.playbackStartTime) {
        if (detectionTimestamp > videoEndTime &&
            detectionTimestamp < nextTiming.playbackStartTime) {
          // Detection occurred during transition - attribute to previous video
          const videoElapsedTime = detectionTimestamp - videoStartTime;

          return {
            detectionTimestamp,
            sequenceElapsedTime,
            videoId: timing.videoId,
            videoIndex: timing.videoIndex,
            videoElapsedTime,
            isWithinVideoPlayback: false,
            estimatedLoadingDelay: timing.actualStartDelay
          };
        }
      }
    }
  }

  // If no match found, attribute to last video if detection is after last video start
  const lastTiming = videoTimings[videoTimings.length - 1];
  if (lastTiming.playbackStartTime && detectionTimestamp >= lastTiming.playbackStartTime) {
    const videoElapsedTime = detectionTimestamp - lastTiming.playbackStartTime;

    return {
      detectionTimestamp,
      sequenceElapsedTime,
      videoId: lastTiming.videoId,
      videoIndex: lastTiming.videoIndex,
      videoElapsedTime,
      isWithinVideoPlayback: lastTiming.playbackEndTime
        ? detectionTimestamp <= lastTiming.playbackEndTime
        : true,
      estimatedLoadingDelay: lastTiming.actualStartDelay
    };
  }

  return null;
}

/**
 * Calculate cumulative delay up to a specific video index
 */
export function calculateCumulativeDelay(
  videoTimings: VideoTimingMetadata[],
  upToIndex: number
): number {
  let cumulativeDelay = 0;

  for (let i = 0; i <= upToIndex && i < videoTimings.length; i++) {
    const timing = videoTimings[i];

    // Add actual start delay
    cumulativeDelay += timing.actualStartDelay;

    // Add transition delay (gap between videos)
    if (i > 0 && timing.playbackStartTime && videoTimings[i - 1].playbackEndTime) {
      const transitionGap = timing.playbackStartTime - videoTimings[i - 1].playbackEndTime!;
      cumulativeDelay += transitionGap;
    }
  }

  return cumulativeDelay;
}

/**
 * Get expected timestamp for a video at a given index
 *
 * Calculates when a video should start based on previous video durations,
 * without accounting for actual delays.
 */
export function getExpectedVideoStartTime(
  sequenceStartTime: number,
  previousVideoDurations: number[]
): number {
  const totalPreviousDuration = previousVideoDurations.reduce((sum, duration) => sum + duration, 0);
  return sequenceStartTime + totalPreviousDuration;
}

/**
 * Adjust detection timestamp for loading delays
 *
 * Compensates for video loading delays to get the "true" video timeline position
 */
export function adjustDetectionForDelays(
  detectionTimestamp: number,
  sequenceStartTime: number,
  videoTimings: VideoTimingMetadata[]
): number {
  const detectionResult = mapDetectionToVideo(detectionTimestamp, sequenceStartTime, videoTimings);

  if (!detectionResult) {
    return detectionTimestamp - sequenceStartTime;
  }

  // Calculate adjusted timestamp by removing loading delays
  const cumulativeDelay = calculateCumulativeDelay(videoTimings, detectionResult.videoIndex);
  return (detectionTimestamp - sequenceStartTime) - cumulativeDelay;
}

/**
 * Get timing statistics for the entire sequence
 */
export interface SequenceTimingStats {
  totalVideos: number;
  totalExpectedDuration: number;
  totalActualDuration: number;
  totalLoadingDelay: number;
  totalTransitionDelay: number;
  averageLoadingDelay: number;
  averageTransitionDelay: number;
  maxLoadingDelay: number;
  minLoadingDelay: number;
  timingEfficiency: number; // Percentage of time spent in actual video playback
}

export function calculateSequenceTimingStats(
  videoTimings: VideoTimingMetadata[]
): SequenceTimingStats {
  const completedVideos = videoTimings.filter(v => v.duration !== null);

  const totalExpectedDuration = completedVideos.reduce((sum, v) => sum + (v.duration || 0), 0);
  const totalLoadingDelay = videoTimings.reduce((sum, v) => sum + v.actualStartDelay, 0);

  let totalTransitionDelay = 0;
  for (let i = 1; i < videoTimings.length; i++) {
    if (videoTimings[i].playbackStartTime && videoTimings[i - 1].playbackEndTime) {
      totalTransitionDelay += videoTimings[i].playbackStartTime! - videoTimings[i - 1].playbackEndTime!;
    }
  }

  const totalActualDuration = totalExpectedDuration + totalLoadingDelay + totalTransitionDelay;

  const loadingDelays = videoTimings.map(v => v.actualStartDelay);
  const averageLoadingDelay = loadingDelays.length > 0
    ? loadingDelays.reduce((sum, delay) => sum + delay, 0) / loadingDelays.length
    : 0;

  const transitionDelays: number[] = [];
  for (let i = 1; i < videoTimings.length; i++) {
    if (videoTimings[i].playbackStartTime && videoTimings[i - 1].playbackEndTime) {
      transitionDelays.push(videoTimings[i].playbackStartTime! - videoTimings[i - 1].playbackEndTime!);
    }
  }
  const averageTransitionDelay = transitionDelays.length > 0
    ? transitionDelays.reduce((sum, delay) => sum + delay, 0) / transitionDelays.length
    : 0;

  const maxLoadingDelay = loadingDelays.length > 0 ? Math.max(...loadingDelays) : 0;
  const minLoadingDelay = loadingDelays.length > 0 ? Math.min(...loadingDelays) : 0;

  const timingEfficiency = totalActualDuration > 0
    ? (totalExpectedDuration / totalActualDuration) * 100
    : 0;

  return {
    totalVideos: videoTimings.length,
    totalExpectedDuration,
    totalActualDuration,
    totalLoadingDelay,
    totalTransitionDelay,
    averageLoadingDelay,
    averageTransitionDelay,
    maxLoadingDelay,
    minLoadingDelay,
    timingEfficiency
  };
}

/**
 * Format timing data for logging and debugging
 */
export function formatTimingForLogging(timing: VideoTimingMetadata): Record<string, any> {
  return {
    videoId: timing.videoId,
    videoIndex: timing.videoIndex,
    loadStartTime: timing.loadStartTime.toFixed(2),
    playbackStartTime: timing.playbackStartTime?.toFixed(2) || 'not started',
    playbackEndTime: timing.playbackEndTime?.toFixed(2) || 'not ended',
    actualStartDelay: `${timing.actualStartDelay.toFixed(2)}ms`,
    transitionDelay: `${timing.transitionDelay.toFixed(2)}ms`,
    duration: timing.duration ? `${timing.duration.toFixed(2)}ms` : 'unknown'
  };
}

/**
 * Export timing data for analysis
 */
export function exportTimingData(videoTimings: VideoTimingMetadata[]): string {
  const stats = calculateSequenceTimingStats(videoTimings);

  const report = {
    summary: stats,
    videoTimings: videoTimings.map(formatTimingForLogging),
    timestamp: new Date().toISOString()
  };

  return JSON.stringify(report, null, 2);
}
