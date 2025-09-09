/**
 * Video URL Utilities
 * 
 * Provides comprehensive video URL handling across different environments:
 * - Environment-aware URL generation
 * - Fallback mechanisms for broken URLs
 * - Video format validation
 * - Accessibility checks
 */

import { getServiceConfig, isDebugEnabled } from './envConfig';
import logger from './safeErrorLogger';

/**
 * Format time in MM:SS or HH:MM:SS format
 */
export const formatTime = (seconds: number): string => {
  if (isNaN(seconds) || !isFinite(seconds)) {
    return '00:00';
  }

  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

export interface VideoMetadata {
  id: string;
  filename: string;
  originalName?: string;
  url?: string;
  size?: number;
  duration?: number;
  format?: string;
  status?: 'completed' | 'processing' | 'error';
}

export interface VideoUrlOptions {
  thumbnail?: boolean;
  quality?: 'low' | 'medium' | 'high';
  forceRefresh?: boolean;
}

// Enhanced video player utilities
export interface VideoPlayResult {
  success: boolean;
  error?: Error;
}

// Global user interaction tracking for autoplay policy compliance
let hasUserInteracted = false;
let userGestureTimestamp = 0;
const USER_GESTURE_TIMEOUT = 5000; // 5 seconds

// Track user interactions that enable autoplay
const initializeUserInteractionTracking = (() => {
  let initialized = false;
  return () => {
    if (initialized) return;
    initialized = true;
    
    const events = ['click', 'tap', 'touchstart', 'touchend', 'mousedown', 'keydown'];
    const handleUserGesture = () => {
      hasUserInteracted = true;
      userGestureTimestamp = Date.now();
    };
    
    events.forEach(eventType => {
      document.addEventListener(eventType, handleUserGesture, { passive: true, capture: true });
    });
  };
})();

// Initialize tracking immediately
initializeUserInteractionTracking();

/**
 * Check if we have a recent user gesture for autoplay
 */
export const hasRecentUserGesture = (): boolean => {
  return hasUserInteracted && (Date.now() - userGestureTimestamp) < USER_GESTURE_TIMEOUT;
};

/**
 * Mark that user interaction occurred (for manual triggering)
 */
export const markUserInteraction = (): void => {
  hasUserInteracted = true;
  userGestureTimestamp = Date.now();
};

/**
 * Detect autoplay policy and attempt playback with fallbacks
 */
export const detectAutoplayPolicy = async (videoElement: HTMLVideoElement): Promise<{
  allowed: boolean;
  muted: boolean;
  requiresUserGesture: boolean;
}> => {
  try {
    // Test muted autoplay first
    const originalMuted = videoElement.muted;
    const originalVolume = videoElement.volume;
    
    videoElement.muted = true;
    videoElement.volume = 0;
    
    await videoElement.play();
    videoElement.pause();
    videoElement.currentTime = 0;
    
    // Restore original settings
    videoElement.muted = originalMuted;
    videoElement.volume = originalVolume;
    
    return {
      allowed: true,
      muted: true,
      requiresUserGesture: false
    };
  } catch (error) {
    return {
      allowed: false,
      muted: false,
      requiresUserGesture: true
    };
  }
};

/**
 * Safely attempt to play a video element with autoplay policy handling
 */
export const safeVideoPlay = async (videoElement: HTMLVideoElement | null, options: {
  forceMuted?: boolean;
  userInitiated?: boolean;
  retryWithMuted?: boolean;
} = {}): Promise<VideoPlayResult> => {
  console.log('🔍 DEBUG: safeVideoPlay() called with options:', options);
  
  if (!videoElement) {
    console.log('🔍 DEBUG: Video element is null');
    return { success: false, error: new Error('Video element is null') };
  }

  console.log('🔍 DEBUG: Video element state:', {
    readyState: videoElement.readyState,
    paused: videoElement.paused,
    currentTime: videoElement.currentTime,
    duration: videoElement.duration,
    src: videoElement.src,
    muted: videoElement.muted
  });

  try {
    // Check if video is ready to play
    if (videoElement.readyState < HTMLMediaElement.HAVE_METADATA) {
      console.log('🔍 DEBUG: Video metadata not loaded, readyState:', videoElement.readyState);
      return { success: false, error: new Error('Video metadata not loaded') };
    }
    console.log('🔍 DEBUG: Video metadata is loaded, proceeding with playback');

    const { forceMuted = false, userInitiated = false, retryWithMuted = true } = options;
    
    // Mark user interaction if this is user-initiated
    if (userInitiated) {
      markUserInteraction();
    }
    
    // First attempt - try normal playback if we have user gesture
    if (!forceMuted && (userInitiated || hasRecentUserGesture())) {
      console.log('🔍 DEBUG: Attempting normal (unmuted) playback');
      try {
        const playPromise = videoElement.play();
        console.log('🔍 DEBUG: videoElement.play() called, promise:', playPromise);
        if (playPromise !== undefined) {
          await playPromise;
        }
        console.log('🔍 DEBUG: Normal playback succeeded');
        return { success: true };
      } catch (playError) {
        console.log('🔍 DEBUG: Normal playback failed:', playError);
        logger.warn('Normal video play failed, trying muted fallback', playError);
        
        // Don't retry with muted if explicitly disabled
        if (!retryWithMuted) {
          console.log('🔍 DEBUG: Retry with muted is disabled, returning error');
          return { success: false, error: playError as Error };
        }
      }
    } else {
      console.log('🔍 DEBUG: Skipping normal playback attempt. forceMuted:', forceMuted, 'userInitiated:', userInitiated, 'hasRecentUserGesture:', hasRecentUserGesture());
    }
    
    // Fallback attempt - try muted autoplay
    if (retryWithMuted || forceMuted) {
      console.log('🔍 DEBUG: Attempting muted playback fallback');
      const originalMuted = videoElement.muted;
      const originalVolume = videoElement.volume;
      
      try {
        videoElement.muted = true;
        videoElement.volume = 0;
        console.log('🔍 DEBUG: Set video to muted, calling play()');
        
        const playPromise = videoElement.play();
        console.log('🔍 DEBUG: Muted videoElement.play() called, promise:', playPromise);
        if (playPromise !== undefined) {
          await playPromise;
        }
        
        console.log('🔍 DEBUG: Muted playback succeeded');
        
        // If successful with muted, provide feedback
        if (!forceMuted) {
          logger.info('Video started in muted mode due to autoplay policy');
        }
        
        return { success: true };
      } catch (mutedError) {
        console.log('🔍 DEBUG: Muted playback also failed:', mutedError);
        // Restore original settings if muted playback failed
        videoElement.muted = originalMuted;
        videoElement.volume = originalVolume;
        
        return { success: false, error: mutedError as Error };
      }
    } else {
      console.log('🔍 DEBUG: Skipping muted playback. retryWithMuted:', retryWithMuted, 'forceMuted:', forceMuted);
    }
    
    return { success: false, error: new Error('Autoplay blocked and no fallback available') };
    
  } catch (error) {
    return { success: false, error: error as Error };
  }
};

/**
 * Safely pause a video element
 */
export const safeVideoPause = (videoElement: HTMLVideoElement | null): boolean => {
  if (!videoElement) return false;

  try {
    videoElement.pause();
    return true;
  } catch (error) {
    logger.warn('Video pause failed', error, { context: 'video-utils', function: 'safeVideoPause' });
    return false;
  }
};

/**
 * Enable unmuted playback after user interaction
 */
export const enableUnmutedPlayback = async (videoElement: HTMLVideoElement): Promise<boolean> => {
  if (!videoElement || !hasRecentUserGesture()) {
    return false;
  }
  
  try {
    videoElement.muted = false;
    // Test if unmuted playback works
    if (!videoElement.paused) {
      // Video is playing, just unmute
      return true;
    }
    
    // Try to play unmuted
    const result = await safeVideoPlay(videoElement, { userInitiated: true, retryWithMuted: false });
    return result.success;
  } catch (error) {
    logger.warn('Failed to enable unmuted playback', error);
    return false;
  }
};

/**
 * Safely stop a video element
 */
export const safeVideoStop = (videoElement: HTMLVideoElement | null): boolean => {
  if (!videoElement) return false;

  try {
    videoElement.pause();
    videoElement.currentTime = 0;
    return true;
  } catch (error) {
    logger.warn('Video stop failed', error, { context: 'video-utils', function: 'safeVideoStop' });
    return false;
  }
};

/**
 * Set video source with proper error handling
 */
export const setVideoSource = async (videoElement: HTMLVideoElement, src: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const handleLoad = () => {
      cleanup();
      resolve();
    };

    const handleError = (_event: Event) => {
      cleanup();
      const error = videoElement.error;
      if (error) {
        reject(new Error(`Video load error: ${getVideoErrorMessage(videoElement)}`));
      } else {
        reject(new Error(`Video load failed for unknown reason`));
      }
    };

    const cleanup = () => {
      videoElement.removeEventListener('loadedmetadata', handleLoad);
      videoElement.removeEventListener('error', handleError);
    };

    videoElement.addEventListener('loadedmetadata', handleLoad);
    videoElement.addEventListener('error', handleError);
    
    videoElement.src = src;
    videoElement.load();
  });
};

/**
 * Clean up video element resources
 */
export const cleanupVideoElement = (videoElement: HTMLVideoElement | null): void => {
  if (!videoElement) return;

  try {
    videoElement.pause();
    videoElement.currentTime = 0;
    videoElement.src = '';
    videoElement.load();
  } catch (error) {
    logger.warn('Video cleanup failed', error, { context: 'video-utils', function: 'cleanupVideoElement' });
  }
};

/**
 * Add multiple event listeners to video element with cleanup
 */
export const addVideoEventListeners = (
  videoElement: HTMLVideoElement,
  listeners: Array<{ event: string; handler: EventListener }>
): (() => void) => {
  listeners.forEach(({ event, handler }) => {
    videoElement.addEventListener(event, handler);
  });

  // Return cleanup function
  return () => {
    listeners.forEach(({ event, handler }) => {
      videoElement.removeEventListener(event, handler);
    });
  };
};

/**
 * Enhanced video codec and format detection
 */
export interface VideoCodecSupport {
  h264: boolean;
  hevc: boolean;
  vp9: boolean;
  vp8: boolean;
  av1: boolean;
}

export interface VideoFormatSupport {
  mp4: boolean;
  webm: boolean;
  ogg: boolean;
  avi: boolean;
  mov: boolean;
  mkv: boolean;
}

/**
 * Check browser video codec support
 */
export const checkVideoCodecSupport = (): VideoCodecSupport => {
  const video = document.createElement('video');
  
  return {
    h264: video.canPlayType('video/mp4; codecs="avc1.42E01E"') !== '',
    hevc: video.canPlayType('video/mp4; codecs="hvc1.1.6.L93.B0"') !== '',
    vp9: video.canPlayType('video/webm; codecs="vp9"') !== '',
    vp8: video.canPlayType('video/webm; codecs="vp8"') !== '',
    av1: video.canPlayType('video/mp4; codecs="av01.0.05M.08"') !== '' || 
          video.canPlayType('video/webm; codecs="av01.0.05M.08"') !== ''
  };
};

/**
 * Check browser video format support
 */
export const checkVideoFormatSupport = (): VideoFormatSupport => {
  const video = document.createElement('video');
  
  return {
    mp4: video.canPlayType('video/mp4') !== '',
    webm: video.canPlayType('video/webm') !== '',
    ogg: video.canPlayType('video/ogg') !== '',
    avi: false, // Not natively supported in browsers
    mov: video.canPlayType('video/quicktime') !== '',
    mkv: false // Not natively supported in browsers
  };
};

/**
 * Get fallback video sources with multiple formats and codecs
 */
export const generateFallbackSources = (baseUrl: string, filename: string): string[] => {
  const codecSupport = checkVideoCodecSupport();
  const formatSupport = checkVideoFormatSupport();
  const sources: string[] = [];
  
  // Extract base filename without extension
  const baseName = filename.replace(/\.[^/.]+$/, '');
  
  // Primary choices based on codec support
  if (codecSupport.h264 && formatSupport.mp4) {
    sources.push(`${baseUrl}/${baseName}.mp4`);
    sources.push(`${baseUrl}/${baseName}_h264.mp4`);
  }
  
  if (codecSupport.vp9 && formatSupport.webm) {
    sources.push(`${baseUrl}/${baseName}.webm`);
    sources.push(`${baseUrl}/${baseName}_vp9.webm`);
  }
  
  if (codecSupport.vp8 && formatSupport.webm) {
    sources.push(`${baseUrl}/${baseName}_vp8.webm`);
  }
  
  // Add original filename as fallback
  sources.push(`${baseUrl}/${filename}`);
  
  // Add common fallback extensions
  const fallbackExtensions = ['mp4', 'webm', 'mov'];
  fallbackExtensions.forEach(ext => {
    if (!sources.some(src => src.endsWith(`.${ext}`))) {
      sources.push(`${baseUrl}/${baseName}.${ext}`);
    }
  });
  
  return sources;
};

/**
 * Set video source with multiple fallback formats
 */
export const setVideoSourceWithFallback = async (
  videoElement: HTMLVideoElement, 
  sources: string[]
): Promise<void> => {
  return new Promise((resolve, reject) => {
    let currentSourceIndex = 0;
    
    const tryNextSource = () => {
      if (currentSourceIndex >= sources.length) {
        reject(new Error('No compatible video source found'));
        return;
      }
      
      const src = sources[currentSourceIndex];
      currentSourceIndex++;
      
      const handleLoad = () => {
        cleanup();
        resolve();
      };
      
      const handleError = () => {
        cleanup();
        console.warn(`Failed to load video source: ${src}`);
        setTimeout(tryNextSource, 100); // Small delay before trying next source
      };
      
      const cleanup = () => {
        videoElement.removeEventListener('loadedmetadata', handleLoad);
        videoElement.removeEventListener('error', handleError);
      };
      
      videoElement.addEventListener('loadedmetadata', handleLoad);
      videoElement.addEventListener('error', handleError);
      
      videoElement.src = src;
      videoElement.load();
    };
    
    tryNextSource();
  });
};

/**
 * Get human-readable video error message with format suggestions
 */
export const getVideoErrorMessage = (videoElement: HTMLVideoElement): string => {
  const error = videoElement.error;
  if (!error) return 'Unknown error';

  const codecSupport = checkVideoCodecSupport();
  const formatSupport = checkVideoFormatSupport();

  switch (error.code) {
    case MediaError.MEDIA_ERR_ABORTED:
      return 'Video loading was aborted. Try refreshing the page.';
    case MediaError.MEDIA_ERR_NETWORK:
      return 'Network error occurred while loading video. Check your connection and try again.';
    case MediaError.MEDIA_ERR_DECODE:
      return 'Video decoding error. The video file may be corrupted or use an unsupported codec.';
    case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
      let suggestion = 'Video format not supported by this browser.';
      
      if (codecSupport.h264 && formatSupport.mp4) {
        suggestion += ' Try converting to MP4 with H.264 codec.';
      } else if (codecSupport.vp9 && formatSupport.webm) {
        suggestion += ' Try converting to WebM with VP9 codec.';
      } else if (formatSupport.mp4) {
        suggestion += ' Try converting to MP4 format.';
      }
      
      return suggestion;
    default:
      return 'Unknown video error occurred.';
  }
};

/**
 * Check if video is ready for playback
 */
export const isVideoReady = (videoElement: HTMLVideoElement): boolean => {
  return videoElement.readyState >= HTMLMediaElement.HAVE_METADATA;
};

class VideoUtilsManager {
  private urlCache = new Map<string, string>();
  private accessibilityCache = new Map<string, boolean>();
  
  /**
   * Generate a proper video URL based on environment and video metadata
   */
  generateVideoUrl(video: VideoMetadata, options: VideoUrlOptions = {}): string {
    const { thumbnail = false, quality = 'medium', forceRefresh = false } = options;
    
    // Use cached URL if available and not forcing refresh
    const cacheKey = `${video.id}_${thumbnail ? 'thumb' : 'video'}_${quality}`;
    if (!forceRefresh && this.urlCache.has(cacheKey)) {
      return this.urlCache.get(cacheKey)!;
    }
    
    let videoUrl: string;
    
    // Debug: Log the video object to see what we're working with
    if (isDebugEnabled()) {
      logger.debug('VideoUtils generateVideoUrl - video object', video, { context: 'video-utils', function: 'generateVideoUrl' });
    }
    
    // If video already has a URL, check if it needs fixing
    if (video.url) {
      const videoConfig = getServiceConfig('video');
      
      // Fix localhost URLs that should use the correct backend URL
      if (video.url.includes('localhost:8000')) {
        videoUrl = video.url.replace('http://localhost:8000', videoConfig.baseUrl || 'http://155.138.239.131:8000');
        if (isDebugEnabled()) {
          logger.debug('VideoUtils fixed localhost URL', { original: video.url, fixed: videoUrl }, { context: 'video-utils', function: 'generateVideoUrl' });
        }
      } else if (this.isValidUrl(video.url)) {
        videoUrl = video.url;
        if (isDebugEnabled()) {
          logger.debug('VideoUtils using complete URL', videoUrl, { context: 'video-utils', function: 'generateVideoUrl' });
        }
      } else if (video.url.startsWith('/')) {
        // Handle relative URLs from backend
        videoUrl = `${videoConfig.baseUrl || ''}${video.url}`;
        if (isDebugEnabled()) {
          logger.debug('VideoUtils using backend URL', { original: video.url, full: videoUrl }, { context: 'video-utils', function: 'generateVideoUrl' });
        }
      } else {
        videoUrl = video.url;
        if (isDebugEnabled()) {
          logger.debug('VideoUtils using video.url as-is', videoUrl, { context: 'video-utils', function: 'generateVideoUrl' });
        }
      }
    } else {
      // Generate URL based on video metadata
      const videoConfig = getServiceConfig('video');
      if (isDebugEnabled()) {
        logger.debug('VideoUtils generateVideoUrl config baseUrl', videoConfig.baseUrl, { context: 'video-utils', function: 'generateVideoUrl' });
      }
      const filename = video.filename || video.id;
      
      if (thumbnail) {
        // Generate thumbnail URL
        videoUrl = `${videoConfig.baseUrl || ''}/thumbnails/${filename}.jpg`;
      } else {
        // Generate video URL with quality suffix if needed
        const qualitySuffix = quality !== 'medium' ? `_${quality}` : '';
        videoUrl = `${videoConfig.baseUrl || ''}/uploads/${filename}${qualitySuffix}`;
      }
    }
    
    // Add cache busting parameter if needed
    if (forceRefresh) {
      const separator = videoUrl.includes('?') ? '&' : '?';
      videoUrl = `${videoUrl}${separator}t=${Date.now()}`;
    }
    
    // Cache the generated URL
    this.urlCache.set(cacheKey, videoUrl);
    
    if (isDebugEnabled()) {
      logger.debug('Generated video URL', { videoId: video.id, url: videoUrl }, { context: 'video-utils', function: 'generateVideoUrl' });
    }
    
    return videoUrl;
  }
  
  /**
   * Generate multiple video URLs for different qualities
   */
  generateVideoUrls(video: VideoMetadata, options: VideoUrlOptions = {}) {
    return {
      low: this.generateVideoUrl(video, { ...options, quality: 'low' }),
      medium: this.generateVideoUrl(video, { ...options, quality: 'medium' }),
      high: this.generateVideoUrl(video, { ...options, quality: 'high' }),
      thumbnail: this.generateVideoUrl(video, { ...options, thumbnail: true })
    };
  }
  
  /**
   * Check if a video URL is accessible
   */
  async checkVideoAccessibility(url: string, timeoutMs: number = 10000): Promise<boolean> {
    // Use cached result if available
    if (this.accessibilityCache.has(url)) {
      return this.accessibilityCache.get(url)!;
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      
      const response = await fetch(url, {
        method: 'HEAD', // Only check headers, don't download content
        signal: controller.signal,
        cache: 'no-cache'
      });
      
      clearTimeout(timeoutId);
      
      const accessible = Boolean(response.ok && response.headers.get('content-type')?.includes('video'));
      
      // Cache the result for 5 minutes
      this.accessibilityCache.set(url, accessible);
      setTimeout(() => this.accessibilityCache.delete(url), 5 * 60 * 1000);
      
      if (isDebugEnabled()) {
        logger.debug('Video accessibility check', { url, accessible }, { context: 'video-utils', function: 'checkVideoAccessibility' });
      }
      
      return accessible;
      
    } catch (error: Error | unknown) {
      if (isDebugEnabled()) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        logger.warn('Video accessibility check failed', errorMessage, { context: 'video-utils', function: 'checkVideoAccessibility', url });
      }
      
      // Cache negative result for 1 minute
      this.accessibilityCache.set(url, false);
      setTimeout(() => this.accessibilityCache.delete(url), 60 * 1000);
      
      return false;
    }
  }
  
  /**
   * Clear cache for videos that no longer exist
   */
  clearStaleVideoCache(validVideoIds: string[]): void {
    const cacheKeys = Array.from(this.urlCache.keys());
    const staleCacheKeys = cacheKeys.filter(key => {
      // Extract video ID from cache key (format: "videoId_quality" or just "videoId")
      const videoId = key.split('_')[0];
      return !validVideoIds.includes(videoId);
    });
    
    staleCacheKeys.forEach(key => {
      this.urlCache.delete(key);
      if (isDebugEnabled()) {
        logger.debug('Cleared stale video cache', key, { context: 'video-utils', function: 'clearStaleVideoCache' });
      }
    });
  }

  /**
   * Get fallback video URL with multiple attempts
   */
  async getFallbackVideoUrl(video: VideoMetadata, options: VideoUrlOptions = {}): Promise<string | null> {
    const attempts = [
      // Primary URL
      () => this.generateVideoUrl(video, options),
      // Fallback to medium quality
      () => this.generateVideoUrl(video, { ...options, quality: 'medium' }),
      // Fallback to low quality
      () => this.generateVideoUrl(video, { ...options, quality: 'low' }),
      // Direct filename access
      () => {
        const videoConfig = getServiceConfig('video');
        if (isDebugEnabled()) {
          logger.debug('VideoUtils config baseUrl', videoConfig.baseUrl, { context: 'video-utils', function: 'getFallbackVideoUrl' });
        }
        return `${videoConfig.baseUrl || ''}/uploads/${video.filename}`;
      },
      // Direct ID access
      () => {
        const videoConfig = getServiceConfig('video');
        return `${videoConfig.baseUrl || ''}/uploads/${video.id}`;
      }
    ];
    
    for (const attemptFn of attempts) { // eslint-disable-line no-await-in-loop
      try {
        const url = attemptFn();
        const accessible = await this.checkVideoAccessibility(url);
        
        if (accessible) {
          if (isDebugEnabled()) {
            logger.debug('Found accessible video URL', { videoId: video.id, url }, { context: 'video-utils', function: 'getFallbackVideoUrl' });
          }
          return url;
        }
      } catch (error: Error | unknown) {
        if (isDebugEnabled()) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          logger.warn('Fallback attempt failed', errorMessage, { context: 'video-utils', function: 'getFallbackVideoUrl', videoId: video.id });
        }
      }
    }
    
    logger.error('No accessible video URL found', undefined, { context: 'video-utils', function: 'getFallbackVideoUrl', videoId: video.id });
    return null;
  }
  
  /**
   * Validate video format support
   */
  isVideoFormatSupported(filename: string): boolean {
    const videoConfig = getServiceConfig('video');
    const extension = filename.split('.').pop()?.toLowerCase();
    
    if (!extension) return false;
    
    return videoConfig.supportedFormats?.includes(extension) || false;
  }
  
  /**
   * Validate video file size
   */
  isVideoSizeValid(sizeInBytes: number): boolean {
    const videoConfig = getServiceConfig('video');
    const maxSizeBytes = (videoConfig.maxSizeMB || 100) * 1024 * 1024;
    
    return sizeInBytes <= maxSizeBytes;
  }
  
  /**
   * Get video format information
   */
  getVideoFormatInfo(filename: string) {
    const extension = filename.split('.').pop()?.toLowerCase();
    const videoConfig = getServiceConfig('video');
    
    const formatInfo: Record<string, { name: string; mimeType: string; description: string }> = {
      mp4: {
        name: 'MP4',
        mimeType: 'video/mp4',
        description: 'MPEG-4 Video (recommended)'
      },
      avi: {
        name: 'AVI',
        mimeType: 'video/x-msvideo',
        description: 'Audio Video Interleave'
      },
      mov: {
        name: 'MOV',
        mimeType: 'video/quicktime',
        description: 'QuickTime Video'
      },
      mkv: {
        name: 'MKV',
        mimeType: 'video/x-matroska',
        description: 'Matroska Video'
      }
    };
    
    return {
      extension,
      supported: extension ? (videoConfig.supportedFormats?.includes(extension) || false) : false,
      ...formatInfo[extension || ''] || {
        name: extension?.toUpperCase() || 'Unknown',
        mimeType: 'video/*',
        description: 'Unknown video format'
      }
    };
  }
  
  /**
   * Generate video preview/poster image URL
   */
  generatePosterUrl(video: VideoMetadata): string {
    const videoConfig = getServiceConfig('video');
    const filename = video.filename || video.id;
    
    return `${videoConfig.baseUrl || ''}/posters/${filename}.jpg`;
  }
  
  /**
   * Clear URL caches
   */
  clearCache(): void {
    this.urlCache.clear();
    this.accessibilityCache.clear();
    
    if (isDebugEnabled()) {
      logger.debug('Video URL caches cleared', undefined, { context: 'video-utils', function: 'clearCache' });
    }
  }
  
  /**
   * Get cache statistics
   */
  getCacheStats() {
    return {
      urlCacheSize: this.urlCache.size,
      accessibilityCacheSize: this.accessibilityCache.size
    };
  }
  
  /**
   * Validate if a URL is properly formed
   */
  private isValidUrl(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }
}

// Export singleton instance
export const videoUtils = new VideoUtilsManager();

// Export convenience functions
export const generateVideoUrl = (video: VideoMetadata, options?: VideoUrlOptions) => 
  videoUtils.generateVideoUrl(video, options);

export const generateVideoUrls = (video: VideoMetadata, options?: VideoUrlOptions) => 
  videoUtils.generateVideoUrls(video, options);

export const checkVideoAccessibility = (url: string, timeout?: number) => 
  videoUtils.checkVideoAccessibility(url, timeout);

export const getFallbackVideoUrl = (video: VideoMetadata, options?: VideoUrlOptions) => 
  videoUtils.getFallbackVideoUrl(video, options);

export const isVideoFormatSupported = (filename: string) => 
  videoUtils.isVideoFormatSupported(filename);

export const isVideoSizeValid = (sizeInBytes: number) => 
  videoUtils.isVideoSizeValid(sizeInBytes);

export const getVideoFormatInfo = (filename: string) => 
  videoUtils.getVideoFormatInfo(filename);

export const generatePosterUrl = (video: VideoMetadata) => 
  videoUtils.generatePosterUrl(video);

export default videoUtils;