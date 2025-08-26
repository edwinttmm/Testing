/**
 * Video URL Error Handler
 * 
 * Provides comprehensive error handling for video URL enhancement operations
 * with fallback strategies and recovery mechanisms.
 */

import { VideoFile } from '../services/types';
import { isDebugEnabled } from './envConfig';

export interface VideoUrlError {
  videoId?: string;
  originalUrl?: string;
  errorType: 'NETWORK_ERROR' | 'PARSE_ERROR' | 'INVALID_URL' | 'TIMEOUT_ERROR' | 'UNKNOWN_ERROR';
  message: string;
  timestamp: number;
  recoverable: boolean;
  fallbackUsed?: boolean;
}

export interface ErrorRecoveryOptions {
  maxRetries?: number;
  retryDelay?: number;
  fallbackToFilename?: boolean;
  fallbackToId?: boolean;
  skipOnError?: boolean;
}

class VideoUrlErrorHandler {
  private errors: VideoUrlError[] = [];
  private maxErrorHistory = 100;
  private errorCounts = new Map<string, number>();
  
  /**
   * Record a video URL error
   */
  recordError(error: Omit<VideoUrlError, 'timestamp'>, videoId?: string): void {
    const fullError: VideoUrlError = {
      ...error,
      videoId: videoId ?? undefined,
      timestamp: Date.now()
    };
    
    this.errors.push(fullError);
    
    // Maintain error history size
    if (this.errors.length > this.maxErrorHistory) {
      this.errors = this.errors.slice(-this.maxErrorHistory);
    }
    
    // Track error frequency
    const errorKey = `${error.errorType}:${videoId || 'unknown'}`;
    this.errorCounts.set(errorKey, (this.errorCounts.get(errorKey) || 0) + 1);
    
    if (isDebugEnabled()) {
      console.error('📹❌ Video URL Error:', fullError);
    }
  }
  
  /**
   * Attempt to recover from a video URL error
   */
  attemptRecovery(
    video: Partial<VideoFile>,
    error: VideoUrlError,
    options: ErrorRecoveryOptions = {}
  ): VideoFile | null {
    const {
      fallbackToFilename = true,
      fallbackToId = true,
      skipOnError = false
    } = options;
    
    if (skipOnError) {
      return null;
    }
    
    try {
      // Attempt fallback to filename
      if (fallbackToFilename && video.filename) {
        const fallbackUrl = this.constructFallbackUrl(video.filename);
        if (fallbackUrl) {
          const recoveredVideo: VideoFile = {
            id: video.id || 'unknown',
            filename: video.filename,
            url: fallbackUrl,
            originalName: video.originalName || video.filename,
            fileSize: video.fileSize || 0,
            createdAt: video.createdAt || new Date().toISOString(),
            // Add other required VideoFile properties with defaults
            uploadedAt: video.uploadedAt || new Date().toISOString(),
            processing_status: video.processing_status || 'unknown',
            groundTruthGenerated: video.groundTruthGenerated || false,
            detectionCount: video.detectionCount || 0
          };
          
          this.recordError({
            ...error,
            recoverable: true,
            fallbackUsed: true,
            message: `Recovery successful using filename: ${video.filename}`
          }, video.id);
          
          if (isDebugEnabled()) {
            console.log('📹✅ Video URL recovered using filename:', recoveredVideo.url);
          }
          
          return recoveredVideo;
        }
      }
      
      // Attempt fallback to ID
      if (fallbackToId && video.id) {
        const fallbackUrl = this.constructFallbackUrl(video.id);
        if (fallbackUrl) {
          const recoveredVideo: VideoFile = {
            id: video.id,
            filename: video.filename || video.id,
            url: fallbackUrl,
            originalName: video.originalName || video.filename || video.id,
            fileSize: video.fileSize || 0,
            createdAt: video.createdAt || new Date().toISOString(),
            uploadedAt: video.uploadedAt || new Date().toISOString(),
            processing_status: video.processing_status || 'unknown',
            groundTruthGenerated: video.groundTruthGenerated || false,
            detectionCount: video.detectionCount || 0
          };
          
          this.recordError({
            ...error,
            recoverable: true,
            fallbackUsed: true,
            message: `Recovery successful using ID: ${video.id}`
          }, video.id);
          
          if (isDebugEnabled()) {
            console.log('📹✅ Video URL recovered using ID:', recoveredVideo.url);
          }
          
          return recoveredVideo;
        }
      }
      
      return null;
      
    } catch (recoveryError) {
      this.recordError({
        errorType: 'UNKNOWN_ERROR',
        message: `Recovery attempt failed: ${recoveryError}`,
        recoverable: false
      }, video.id);
      
      return null;
    }
  }
  
  /**
   * Construct a fallback URL using filename or ID
   */
  private constructFallbackUrl(identifier: string): string | null {
    try {
      // Use a safe default base URL
      const baseUrl = 'http://155.138.239.131:8000';
      return `${baseUrl}/uploads/${identifier}`;
    } catch (error) {
      return null;
    }
  }
  
  /**
   * Check if a video has had repeated errors
   */
  isProblematicVideo(videoId: string): boolean {
    const errorCount = this.errorCounts.get(`UNKNOWN_ERROR:${videoId}`) || 0;
    return errorCount >= 3;
  }
  
  /**
   * Get error statistics
   */
  getErrorStats() {
    const now = Date.now();
    const recentErrors = this.errors.filter(error => now - error.timestamp < 300000); // 5 minutes
    
    const errorTypeCount = new Map<string, number>();
    const recoverableCount = { recoverable: 0, nonRecoverable: 0 };
    
    recentErrors.forEach(error => {
      errorTypeCount.set(error.errorType, (errorTypeCount.get(error.errorType) || 0) + 1);
      if (error.recoverable) {
        recoverableCount.recoverable++;
      } else {
        recoverableCount.nonRecoverable++;
      }
    });
    
    return {
      totalRecentErrors: recentErrors.length,
      totalHistoryErrors: this.errors.length,
      errorsByType: Object.fromEntries(errorTypeCount),
      recoveryStats: recoverableCount,
      mostProblematicVideos: this.getMostProblematicVideos()
    };
  }
  
  /**
   * Get videos with the most errors
   */
  private getMostProblematicVideos(): Array<{ videoId: string; errorCount: number }> {
    const videoErrors = new Map<string, number>();
    
    for (const [key, count] of this.errorCounts) {
      if (key.includes(':')) {
        const videoId = key.split(':')[1];
        if (videoId && videoId !== 'unknown') {
          videoErrors.set(videoId, (videoErrors.get(videoId) || 0) + count);
        }
      }
    }
    
    return Array.from(videoErrors.entries())
      .map(([videoId, errorCount]) => ({ videoId, errorCount }))
      .sort((a, b) => b.errorCount - a.errorCount)
      .slice(0, 10);
  }
  
  /**
   * Clear error history
   */
  clearErrors(): void {
    this.errors = [];
    this.errorCounts.clear();
  }
  
  /**
   * Get recent errors
   */
  getRecentErrors(maxAge = 300000): VideoUrlError[] {
    const now = Date.now();
    return this.errors.filter(error => now - error.timestamp < maxAge);
  }
}

// Export singleton instance
export const videoUrlErrorHandler = new VideoUrlErrorHandler();

/**
 * Utility function to safely enhance video with error handling
 */
export function safeEnhanceVideo(
  video: unknown,
  enhancerFn: (video: unknown) => VideoFile,
  options: ErrorRecoveryOptions = {}
): VideoFile | null {
  try {
    return enhancerFn(video);
  } catch (error) {
    const videoId = (video as any)?.id;
    const originalUrl = (video as any)?.url;
    
    let errorType: VideoUrlError['errorType'] = 'UNKNOWN_ERROR';
    let message = 'Unknown error occurred';
    
    if (error instanceof TypeError) {
      errorType = 'PARSE_ERROR';
      message = 'Failed to parse video data';
    } else if (error instanceof Error) {
      if (error.message.includes('network')) {
        errorType = 'NETWORK_ERROR';
      } else if (error.message.includes('timeout')) {
        errorType = 'TIMEOUT_ERROR';
      } else if (error.message.includes('invalid') || error.message.includes('url')) {
        errorType = 'INVALID_URL';
      }
      message = error.message;
    }
    
    const videoError: Omit<VideoUrlError, 'timestamp'> = {
      originalUrl: originalUrl ?? undefined,
      errorType,
      message,
      recoverable: errorType !== 'PARSE_ERROR'
    };
    
    videoUrlErrorHandler.recordError(videoError, videoId);
    
    // Attempt recovery
    if (video && typeof video === 'object') {
      return videoUrlErrorHandler.attemptRecovery(video as Partial<VideoFile>, {
        ...videoError,
        timestamp: Date.now()
      }, options);
    }
    
    return null;
  }
}

export default videoUrlErrorHandler;