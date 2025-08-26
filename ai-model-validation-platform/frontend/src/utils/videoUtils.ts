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

/**
 * Safely attempt to play a video element
 */
export const safeVideoPlay = async (videoElement: HTMLVideoElement | null): Promise<VideoPlayResult> => {
  if (!videoElement) {
    return { success: false, error: new Error('Video element is null') };
  }

  try {
    // Check if video is ready to play
    if (videoElement.readyState < HTMLMediaElement.HAVE_METADATA) {
      return { success: false, error: new Error('Video metadata not loaded') };
    }

    const playPromise = videoElement.play();
    if (playPromise !== undefined) {
      await playPromise;
    }
    
    return { success: true };
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
    console.warn('Video pause failed:', error);
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
    console.warn('Video stop failed:', error);
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

    const handleError = (event: Event) => {
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
    console.warn('Video cleanup failed:', error);
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
 * Get human-readable video error message
 */
export const getVideoErrorMessage = (videoElement: HTMLVideoElement): string => {
  const error = videoElement.error;
  if (!error) return 'Unknown error';

  switch (error.code) {
    case MediaError.MEDIA_ERR_ABORTED:
      return 'Video loading was aborted';
    case MediaError.MEDIA_ERR_NETWORK:
      return 'Network error occurred while loading video';
    case MediaError.MEDIA_ERR_DECODE:
      return 'Video decoding error';
    case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
      return 'Video format not supported';
    default:
      return 'Unknown video error';
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
      console.log('🔧 VideoUtils generateVideoUrl - video object:', video);
    }
    
    // If video already has a URL, check if it needs fixing
    if (video.url) {
      const videoConfig = getServiceConfig('video');
      
      // Fix localhost URLs that should use the correct backend URL
      if (video.url.includes('localhost:8000')) {
        videoUrl = video.url.replace('http://localhost:8000', videoConfig.baseUrl || 'http://155.138.239.131:8000');
        if (isDebugEnabled()) {
          console.log('🔧 VideoUtils fixed localhost URL:', video.url, '-> Fixed URL:', videoUrl);
        }
      } else if (this.isValidUrl(video.url)) {
        videoUrl = video.url;
        if (isDebugEnabled()) {
          console.log('🔧 VideoUtils using complete URL:', videoUrl);
        }
      } else if (video.url.startsWith('/')) {
        // Handle relative URLs from backend
        videoUrl = `${videoConfig.baseUrl || ''}${video.url}`;
        if (isDebugEnabled()) {
          console.log('🔧 VideoUtils using backend URL:', video.url, '-> Full URL:', videoUrl);
        }
      } else {
        videoUrl = video.url;
        if (isDebugEnabled()) {
          console.log('🔧 VideoUtils using video.url as-is:', videoUrl);
        }
      }
    } else {
      // Generate URL based on video metadata
      const videoConfig = getServiceConfig('video');
      if (isDebugEnabled()) {
        console.log('🔧 VideoUtils generateVideoUrl config baseUrl:', videoConfig.baseUrl);
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
      console.log(`🎥 Generated video URL for ${video.id}:`, videoUrl);
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
        console.log(`🎥 Video accessibility check for ${url}:`, accessible ? '✅' : '❌');
      }
      
      return accessible;
      
    } catch (error: any) {
      if (isDebugEnabled()) {
        console.warn(`🎥 Video accessibility check failed for ${url}:`, error.message);
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
        console.log(`🧹 Cleared stale video cache for: ${key}`);
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
          console.log('🔧 VideoUtils config baseUrl:', videoConfig.baseUrl);
        }
        return `${videoConfig.baseUrl || ''}/uploads/${video.filename}`;
      },
      // Direct ID access
      () => {
        const videoConfig = getServiceConfig('video');
        return `${videoConfig.baseUrl || ''}/uploads/${video.id}`;
      }
    ];
    
    for (const attemptFn of attempts) {
      try {
        const url = attemptFn();
        const accessible = await this.checkVideoAccessibility(url);
        
        if (accessible) {
          if (isDebugEnabled()) {
            console.log(`✅ Found accessible video URL for ${video.id}:`, url);
          }
          return url;
        }
      } catch (error: any) {
        if (isDebugEnabled()) {
          console.warn(`⚠️ Fallback attempt failed for ${video.id}:`, error.message);
        }
      }
    }
    
    console.error(`❌ No accessible video URL found for ${video.id}`);
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
      console.log('🎥 Video URL caches cleared');
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