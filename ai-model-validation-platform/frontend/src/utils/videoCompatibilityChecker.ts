/**
 * Comprehensive Video Compatibility Checker
 * 
 * Provides complete video format validation and compatibility checking:
 * - Browser-specific codec detection
 * - Format conversion recommendations
 * - Cross-browser compatibility testing
 * - Video file accessibility verification
 * - Debug tools and compatibility matrix
 * - Proper video element lifecycle management
 * - Memory leak prevention and cleanup
 */

import { videoFormatValidator, VideoFormatInfo, VideoCompatibilityReport } from './videoFormatValidator';
import logger from './safeErrorLogger';

export interface BrowserInfo {
  name: string;
  version: string;
  engine: string;
  platform: string;
  mobile: boolean;
}

export interface VideoCompatibilityMatrix {
  format: string;
  browsers: {
    chrome: 'supported' | 'partial' | 'unsupported';
    firefox: 'supported' | 'partial' | 'unsupported';
    safari: 'supported' | 'partial' | 'unsupported';
    edge: 'supported' | 'partial' | 'unsupported';
  };
  codecs: string[];
  recommendation: 'primary' | 'fallback' | 'avoid';
  notes?: string;
}

export interface VideoCompatibilityResult {
  isCompatible: boolean;
  primaryFormat?: string;
  fallbackFormats: string[];
  unsupportedReasons: string[];
  recommendations: string[];
  browserSupport: BrowserInfo[];
  compatibilityMatrix: VideoCompatibilityMatrix[];
}

export interface VideoTestResult {
  format: string;
  url: string;
  canLoad: boolean;
  canPlay: boolean;
  loadTime?: number;
  error?: string;
  metadata?: {
    duration?: number;
    dimensions?: { width: number; height: number };
    bitrate?: number;
    codec?: string;
  };
}

/**
 * Video Element Manager - Handles proper lifecycle of video elements
 */
class VideoElementManager {
  private static instance: VideoElementManager;
  private videoElements = new Map<string, HTMLVideoElement>();
  private eventListeners = new Map<string, { element: HTMLVideoElement; listeners: Array<{ event: string; handler: EventListener }> }>();
  private cleanupTimers = new Map<string, NodeJS.Timeout>();

  static getInstance(): VideoElementManager {
    if (!VideoElementManager.instance) {
      VideoElementManager.instance = new VideoElementManager();
    }
    return VideoElementManager.instance;
  }

  /**
   * Create a managed video element
   */
  createVideoElement(id: string): HTMLVideoElement {
    // Cleanup any existing element with this ID
    this.destroyVideoElement(id);

    const video = document.createElement('video');
    video.style.display = 'none';
    video.style.position = 'absolute';
    video.style.top = '-9999px';
    video.style.left = '-9999px';
    video.preload = 'none';
    video.muted = true; // Prevent autoplay issues
    
    // Add to DOM temporarily for testing
    document.body.appendChild(video);
    
    this.videoElements.set(id, video);
    this.eventListeners.set(id, { element: video, listeners: [] });

    // Auto-cleanup after 30 seconds
    const timer = setTimeout(() => {
      this.destroyVideoElement(id);
    }, 30000);
    this.cleanupTimers.set(id, timer);

    return video;
  }

  /**
   * Add event listener with automatic cleanup tracking
   */
  addEventListener(id: string, event: string, handler: EventListener): void {
    const entry = this.eventListeners.get(id);
    if (entry) {
      entry.element.addEventListener(event, handler);
      entry.listeners.push({ event, handler });
    }
  }

  /**
   * Get managed video element
   */
  getVideoElement(id: string): HTMLVideoElement | undefined {
    return this.videoElements.get(id);
  }

  /**
   * Destroy video element and cleanup all resources
   */
  destroyVideoElement(id: string): void {
    const video = this.videoElements.get(id);
    const listeners = this.eventListeners.get(id);
    const timer = this.cleanupTimers.get(id);

    if (video) {
      try {
        // Stop and cleanup video
        video.pause();
        video.removeAttribute('src');
        video.load(); // Reset the video element
        
        // Remove from DOM if present
        if (video.parentNode) {
          video.parentNode.removeChild(video);
        }
      } catch (error) {
        console.warn('Error during video cleanup:', error);
      }
    }

    // Remove event listeners
    if (listeners) {
      listeners.listeners.forEach(({ event, handler }) => {
        try {
          listeners.element.removeEventListener(event, handler);
        } catch (error) {
          console.warn('Error removing event listener:', error);
        }
      });
    }

    // Clear timer
    if (timer) {
      clearTimeout(timer);
      this.cleanupTimers.delete(id);
    }

    // Remove from maps
    this.videoElements.delete(id);
    this.eventListeners.delete(id);
  }

  /**
   * Cleanup all video elements
   */
  destroyAll(): void {
    const ids = Array.from(this.videoElements.keys());
    ids.forEach(id => this.destroyVideoElement(id));
  }

  /**
   * Get stats for debugging
   */
  getStats(): { activeElements: number; pendingCleanups: number } {
    return {
      activeElements: this.videoElements.size,
      pendingCleanups: this.cleanupTimers.size
    };
  }
}

class VideoCompatibilityChecker {
  private browserInfo: BrowserInfo;
  private compatibilityMatrix: VideoCompatibilityMatrix[];
  private testCache = new Map<string, VideoTestResult>();
  private videoManager = VideoElementManager.getInstance();

  constructor() {
    this.browserInfo = this.detectBrowser();
    this.compatibilityMatrix = this.initializeCompatibilityMatrix();
  }

  /**
   * Detect current browser and capabilities
   */
  private detectBrowser(): BrowserInfo {
    const userAgent = navigator.userAgent.toLowerCase();
    let name = 'unknown';
    let version = 'unknown';
    let engine = 'unknown';

    // Browser detection
    if (userAgent.includes('chrome') && !userAgent.includes('edg')) {
      name = 'chrome';
      const match = userAgent.match(/chrome\/(\d+)/);
      version = match ? match[1] : 'unknown';
      engine = 'blink';
    } else if (userAgent.includes('firefox')) {
      name = 'firefox';
      const match = userAgent.match(/firefox\/(\d+)/);
      version = match ? match[1] : 'unknown';
      engine = 'gecko';
    } else if (userAgent.includes('safari') && !userAgent.includes('chrome')) {
      name = 'safari';
      const match = userAgent.match(/version\/(\d+)/);
      version = match ? match[1] : 'unknown';
      engine = 'webkit';
    } else if (userAgent.includes('edg')) {
      name = 'edge';
      const match = userAgent.match(/edg\/(\d+)/);
      version = match ? match[1] : 'unknown';
      engine = 'blink';
    }

    return {
      name,
      version,
      engine,
      platform: this.detectPlatform(),
      mobile: this.isMobile()
    };
  }

  /**
   * Detect platform
   */
  private detectPlatform(): string {
    const platform = navigator.platform.toLowerCase();
    if (platform.includes('win')) return 'windows';
    if (platform.includes('mac')) return 'macos';
    if (platform.includes('linux')) return 'linux';
    if (platform.includes('iphone') || platform.includes('ipad')) return 'ios';
    if (platform.includes('android')) return 'android';
    return 'unknown';
  }

  /**
   * Check if mobile device
   */
  private isMobile(): boolean {
    return /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(navigator.userAgent);
  }

  /**
   * Initialize compatibility matrix
   */
  private initializeCompatibilityMatrix(): VideoCompatibilityMatrix[] {
    return [
      {
        format: 'mp4',
        browsers: {
          chrome: 'supported',
          firefox: 'supported',
          safari: 'supported',
          edge: 'supported'
        },
        codecs: ['h264', 'aac'],
        recommendation: 'primary',
        notes: 'Universal support, best choice for web delivery'
      },
      {
        format: 'webm',
        browsers: {
          chrome: 'supported',
          firefox: 'supported',
          safari: 'partial',
          edge: 'supported'
        },
        codecs: ['vp8', 'vp9', 'av1', 'vorbis', 'opus'],
        recommendation: 'primary',
        notes: 'Excellent compression, limited Safari support'
      },
      {
        format: 'ogg',
        browsers: {
          chrome: 'supported',
          firefox: 'supported',
          safari: 'unsupported',
          edge: 'partial'
        },
        codecs: ['theora', 'vorbis'],
        recommendation: 'avoid',
        notes: 'Legacy format, poor browser support'
      },
      {
        format: 'mov',
        browsers: {
          chrome: 'partial',
          firefox: 'unsupported',
          safari: 'partial',
          edge: 'partial'
        },
        codecs: ['h264', 'prores', 'aac'],
        recommendation: 'avoid',
        notes: 'Apple format, limited web browser support'
      },
      {
        format: 'avi',
        browsers: {
          chrome: 'unsupported',
          firefox: 'unsupported',
          safari: 'unsupported',
          edge: 'unsupported'
        },
        codecs: ['various'],
        recommendation: 'avoid',
        notes: 'Legacy format, no native browser support'
      },
      {
        format: 'mkv',
        browsers: {
          chrome: 'unsupported',
          firefox: 'unsupported',
          safari: 'unsupported',
          edge: 'unsupported'
        },
        codecs: ['h264', 'h265', 'vp9', 'av1'],
        recommendation: 'avoid',
        notes: 'Container format, no native browser support'
      },
      {
        format: 'm3u8',
        browsers: {
          chrome: 'partial',
          firefox: 'partial',
          safari: 'supported',
          edge: 'partial'
        },
        codecs: ['h264', 'aac'],
        recommendation: 'fallback',
        notes: 'HLS streaming, requires JavaScript library for most browsers'
      }
    ];
  }

  /**
   * Perform comprehensive compatibility check
   */
  async performCompatibilityCheck(
    videoUrl: string, 
    filename: string
  ): Promise<VideoCompatibilityResult> {
    const formatInfo = videoFormatValidator.getFormatFromFilename(filename);
    const validationResult = videoFormatValidator.validateVideoFormat(filename);
    
    const isCompatible = validationResult.isSupported;
    const recommendations: string[] = [];
    const unsupportedReasons: string[] = [];

    // Get browser-specific support info
    const matrixEntry = this.compatibilityMatrix.find(m => m.format === formatInfo.extension);
    
    if (!matrixEntry) {
      unsupportedReasons.push(`Unknown format: ${formatInfo.extension}`);
      recommendations.push('Convert to MP4 (H.264/AAC) for maximum compatibility');
    } else {
      const browserSupport = matrixEntry.browsers[this.browserInfo.name as keyof typeof matrixEntry.browsers];
      
      if (browserSupport === 'unsupported') {
        unsupportedReasons.push(`${formatInfo.displayName} is not supported in ${this.browserInfo.name}`);
      } else if (browserSupport === 'partial') {
        recommendations.push(`${formatInfo.displayName} has limited support in ${this.browserInfo.name}`);
      }
    }

    // Generate fallback formats
    const fallbackFormats = this.generateFallbackFormats(formatInfo.extension);
    
    // Add general recommendations
    if (!isCompatible) {
      if (validationResult.recommendation) {
        recommendations.push(validationResult.recommendation);
      }
      recommendations.push('Test video playback in your target browsers');
    }

    return {
      isCompatible,
      primaryFormat: isCompatible ? formatInfo.extension : undefined,
      fallbackFormats,
      unsupportedReasons,
      recommendations,
      browserSupport: [this.browserInfo],
      compatibilityMatrix: this.compatibilityMatrix
    };
  }

  /**
   * Generate recommended fallback formats
   */
  private generateFallbackFormats(currentFormat: string): string[] {
    const fallbacks: string[] = [];

    // Always recommend MP4 first if not current format
    if (currentFormat !== 'mp4') {
      fallbacks.push('mp4');
    }

    // Add WebM for modern browsers
    if (currentFormat !== 'webm' && this.browserInfo.name !== 'safari') {
      fallbacks.push('webm');
    }

    // Add HLS for streaming if appropriate
    if (!fallbacks.includes('m3u8') && this.supportsHLS()) {
      fallbacks.push('m3u8');
    }

    return fallbacks;
  }

  /**
   * Check HLS support
   */
  private supportsHLS(): boolean {
    // Native HLS support in Safari, requires hls.js for others
    return this.browserInfo.name === 'safari' || 
           (typeof (window as any).Hls !== 'undefined');
  }

  /**
   * Test video loading and playback with proper element management
   */
  async testVideoPlayback(videoUrl: string, format?: string): Promise<VideoTestResult> {
    const cacheKey = `${videoUrl}:${format || 'unknown'}`;
    
    if (this.testCache.has(cacheKey)) {
      return this.testCache.get(cacheKey)!;
    }

    const testId = `test_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const video = this.videoManager.createVideoElement(testId);
    const startTime = Date.now();
    
    const result: VideoTestResult = {
      format: format || this.extractFormatFromUrl(videoUrl),
      url: videoUrl,
      canLoad: false,
      canPlay: false
    };

    try {
      // Test if video can be loaded
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Load timeout - video failed to load within 10 seconds'));
        }, 10000);

        const cleanup = () => {
          clearTimeout(timeout);
        };

        const onLoadedMetadata = () => {
          cleanup();
          result.canLoad = true;
          result.loadTime = Date.now() - startTime;
          
          // Safely get metadata
          try {
            result.metadata = {
              duration: isFinite(video.duration) ? video.duration : undefined,
              dimensions: {
                width: video.videoWidth || 0,
                height: video.videoHeight || 0
              }
            };
          } catch (metaError) {
            console.warn('Error reading video metadata:', metaError);
          }
          
          resolve();
        };

        const onError = () => {
          cleanup();
          const error = video.error;
          result.error = error ? this.getVideoErrorMessage(error) : 'Unknown video loading error';
          reject(new Error(result.error));
        };

        const onAbort = () => {
          cleanup();
          result.error = 'Video loading was aborted';
          reject(new Error(result.error));
        };

        const onStalled = () => {
          console.warn('Video loading stalled for:', videoUrl);
        };

        // Add event listeners using managed system
        this.videoManager.addEventListener(testId, 'loadedmetadata', onLoadedMetadata);
        this.videoManager.addEventListener(testId, 'error', onError);
        this.videoManager.addEventListener(testId, 'abort', onAbort);
        this.videoManager.addEventListener(testId, 'stalled', onStalled);
        
        // Configure video for testing
        video.preload = 'metadata';
        video.muted = true; // Ensure no audio issues
        video.crossOrigin = 'anonymous'; // Try to handle CORS
        video.src = videoUrl;
        video.load();
      });

      // Test if video can play (only if it loaded successfully)
      if (result.canLoad) {
        try {
          // Create a new promise for play test to avoid interference
          await new Promise<void>((resolve, reject) => {
            const playTimeout = setTimeout(() => {
              video.pause();
              reject(new Error('Play timeout - video failed to start playing'));
            }, 5000);

            const onPlay = () => {
              clearTimeout(playTimeout);
              result.canPlay = true;
              video.pause();
              resolve();
            };

            const onPlayError = (event: Event) => {
              clearTimeout(playTimeout);
              const errorMsg = video.error ? this.getVideoErrorMessage(video.error) : 'Playback failed';
              result.error = result.error ? `${result.error}; ${errorMsg}` : errorMsg;
              reject(new Error(errorMsg));
            };

            this.videoManager.addEventListener(testId, 'play', onPlay);
            this.videoManager.addEventListener(testId, 'error', onPlayError);

            // Attempt to play
            const playPromise = video.play();
            if (playPromise) {
              playPromise.catch((playError) => {
                clearTimeout(playTimeout);
                result.canPlay = false;
                const errorMsg = playError.message || 'Play method failed';
                result.error = result.error ? `${result.error}; ${errorMsg}` : errorMsg;
                reject(new Error(errorMsg));
              });
            }
          });
        } catch (playError) {
          result.canPlay = false;
          const errorMsg = (playError as Error).message;
          result.error = result.error ? `${result.error}; ${errorMsg}` : errorMsg;
        }
      }

    } catch (loadError) {
      result.canLoad = false;
      result.canPlay = false;
      result.error = (loadError as Error).message;
    } finally {
      // Always cleanup the video element
      setTimeout(() => {
        this.videoManager.destroyVideoElement(testId);
      }, 100); // Small delay to ensure any pending operations complete
    }

    // Cache result for 5 minutes
    this.testCache.set(cacheKey, result);
    setTimeout(() => this.testCache.delete(cacheKey), 5 * 60 * 1000);

    return result;
  }

  /**
   * Test multiple video formats with proper sequential handling
   */
  async testMultipleFormats(baseUrl: string, formats: string[]): Promise<VideoTestResult[]> {
    const results: VideoTestResult[] = [];
    
    // Test formats sequentially to avoid overwhelming the browser
    for (const format of formats) {
      try {
        const url = this.generateUrlForFormat(baseUrl, format);
        console.log(`Testing format ${format} at ${url}`);
        
        const result = await this.testVideoPlayback(url, format);
        results.push(result);
        
        // Small delay between tests to prevent resource conflicts
        await new Promise(resolve => setTimeout(resolve, 200));
      } catch (error) {
        console.warn(`Failed to test format ${format}:`, error);
        results.push({
          format,
          url: this.generateUrlForFormat(baseUrl, format),
          canLoad: false,
          canPlay: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        });
      }
    }
    
    return results;
  }

  /**
   * Generate URL for specific format
   */
  private generateUrlForFormat(baseUrl: string, format: string): string {
    const basePath = baseUrl.substring(0, baseUrl.lastIndexOf('.'));
    return `${basePath}.${format}`;
  }

  /**
   * Extract format from URL
   */
  private extractFormatFromUrl(url: string): string {
    const match = url.match(/\.([^.?]+)(?:\?|$)/);
    return match ? match[1].toLowerCase() : 'unknown';
  }

  /**
   * Get human-readable error message
   */
  private getVideoErrorMessage(error: MediaError): string {
    switch (error.code) {
      case MediaError.MEDIA_ERR_ABORTED:
        return 'Video loading was aborted by user';
      case MediaError.MEDIA_ERR_NETWORK:
        return 'Network error occurred while loading video';
      case MediaError.MEDIA_ERR_DECODE:
        return 'Video decoding error - file may be corrupted or unsupported codec';
      case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
        return 'Video format not supported by this browser';
      default:
        return `Unknown video error (code: ${error.code})`;
    }
  }

  /**
   * Get browser capabilities report
   */
  getBrowserCapabilities() {
    const video = document.createElement('video');
    
    const capabilities = {
      browser: this.browserInfo,
      formats: {
        mp4: this.testFormatSupport(video, 'video/mp4'),
        webm: this.testFormatSupport(video, 'video/webm'),
        ogg: this.testFormatSupport(video, 'video/ogg'),
        hls: this.supportsHLS()
      },
      codecs: {
        h264: this.testCodecSupport(video, 'video/mp4; codecs="avc1.42E01E"'),
        h265: this.testCodecSupport(video, 'video/mp4; codecs="hev1.1.6.L93.B0"'),
        vp8: this.testCodecSupport(video, 'video/webm; codecs="vp8"'),
        vp9: this.testCodecSupport(video, 'video/webm; codecs="vp9"'),
        av1: this.testCodecSupport(video, 'video/webm; codecs="av01.0.05M.08"')
      },
      features: {
        fullscreen: this.supportsFullscreen(),
        pictureInPicture: this.supportsPictureInPicture(),
        mediaSession: this.supportsMediaSession(),
        autoplay: this.getAutoplaySupport()
      }
    };

    return capabilities;
  }

  /**
   * Test format support
   */
  private testFormatSupport(video: HTMLVideoElement, mimeType: string): string {
    const result = video.canPlayType(mimeType);
    if (result === 'probably') return 'full';
    if (result === 'maybe') return 'partial';
    return 'none';
  }

  /**
   * Test codec support
   */
  private testCodecSupport(video: HTMLVideoElement, codecString: string): boolean {
    const result = video.canPlayType(codecString);
    return result === 'probably' || result === 'maybe';
  }

  /**
   * Check fullscreen support
   */
  private supportsFullscreen(): boolean {
    return !!(
      document.fullscreenEnabled ||
      (document as any).webkitFullscreenEnabled ||
      (document as any).mozFullScreenEnabled ||
      (document as any).msFullscreenEnabled
    );
  }

  /**
   * Check picture-in-picture support
   */
  private supportsPictureInPicture(): boolean {
    return 'pictureInPictureEnabled' in document;
  }

  /**
   * Check Media Session API support
   */
  private supportsMediaSession(): boolean {
    return 'mediaSession' in navigator;
  }

  /**
   * Get autoplay support level
   */
  private getAutoplaySupport(): string {
    // This is a simplified detection
    // Real autoplay detection requires actual testing
    if (this.browserInfo.mobile) {
      return 'user-gesture-required';
    }
    
    switch (this.browserInfo.name) {
      case 'chrome':
        return 'document-user-activation-required';
      case 'safari':
        return 'user-gesture-required';
      case 'firefox':
        return 'allowed';
      default:
        return 'unknown';
    }
  }

  /**
   * Generate compatibility report
   */
  generateCompatibilityReport(): string {
    const capabilities = this.getBrowserCapabilities();
    
    let report = `# Video Compatibility Report\n\n`;
    report += `**Browser:** ${capabilities.browser.name} ${capabilities.browser.version} (${capabilities.browser.engine})\n`;
    report += `**Platform:** ${capabilities.browser.platform} ${capabilities.browser.mobile ? '(mobile)' : '(desktop)'}\n\n`;
    
    report += `## Format Support\n`;
    Object.entries(capabilities.formats).forEach(([format, support]) => {
      const status = typeof support === 'string' ? support : (support ? 'supported' : 'unsupported');
      report += `- **${format.toUpperCase()}:** ${status}\n`;
    });
    
    report += `\n## Codec Support\n`;
    Object.entries(capabilities.codecs).forEach(([codec, supported]) => {
      report += `- **${codec.toUpperCase()}:** ${supported ? 'supported' : 'unsupported'}\n`;
    });
    
    report += `\n## Features\n`;
    Object.entries(capabilities.features).forEach(([feature, support]) => {
      const status = typeof support === 'string' ? support : (support ? 'supported' : 'unsupported');
      report += `- **${feature}:** ${status}\n`;
    });
    
    report += `\n## Recommendations\n`;
    report += this.generateRecommendations(capabilities);
    
    return report;
  }

  /**
   * Generate recommendations based on capabilities
   */
  private generateRecommendations(capabilities: any): string {
    const recommendations: string[] = [];

    // Format recommendations
    if (capabilities.formats.mp4 === 'full') {
      recommendations.push('Use MP4 (H.264/AAC) as primary format for maximum compatibility');
    }

    if (capabilities.formats.webm === 'full' && capabilities.browser.name !== 'safari') {
      recommendations.push('Consider WebM as alternative for better compression');
    }

    // Codec recommendations
    if (!capabilities.codecs.h264) {
      recommendations.push('⚠️ H.264 codec not supported - this may cause playback issues');
    }

    if (capabilities.codecs.av1) {
      recommendations.push('AV1 codec supported - consider for next-generation video encoding');
    }

    // Feature recommendations
    if (!capabilities.features.fullscreen) {
      recommendations.push('⚠️ Fullscreen not supported - provide alternative viewing options');
    }

    if (capabilities.features.autoplay === 'user-gesture-required') {
      recommendations.push('Autoplay requires user interaction - show play button prominently');
    }

    if (capabilities.browser.mobile) {
      recommendations.push('Mobile device detected - optimize for touch controls and bandwidth');
    }

    return recommendations.map(rec => `- ${rec}`).join('\n');
  }

  /**
   * Clear test cache and cleanup video elements
   */
  clearCache(): void {
    this.testCache.clear();
    this.videoManager.destroyAll();
  }

  /**
   * Get video manager stats for debugging
   */
  getVideoManagerStats() {
    return this.videoManager.getStats();
  }

  /**
   * Force cleanup of all video resources
   */
  cleanup(): void {
    this.clearCache();
    this.videoManager.destroyAll();
  }

  /**
   * Get compatibility matrix
   */
  getCompatibilityMatrix(): VideoCompatibilityMatrix[] {
    return [...this.compatibilityMatrix];
  }
}

// Export singleton instance
export const videoCompatibilityChecker = new VideoCompatibilityChecker();

// Export convenience functions
export const performCompatibilityCheck = (videoUrl: string, filename: string) =>
  videoCompatibilityChecker.performCompatibilityCheck(videoUrl, filename);

export const testVideoPlayback = (videoUrl: string, format?: string) =>
  videoCompatibilityChecker.testVideoPlayback(videoUrl, format);

export const getBrowserCapabilities = () =>
  videoCompatibilityChecker.getBrowserCapabilities();

export const generateCompatibilityReport = () =>
  videoCompatibilityChecker.generateCompatibilityReport();

export default videoCompatibilityChecker;