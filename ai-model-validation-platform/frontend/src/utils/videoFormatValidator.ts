/**
 * Video Format Validation Utility
 * 
 * Provides comprehensive video format validation and support detection:
 * - MIME type validation
 * - HTML5 video element canPlayType() checking
 * - Format compatibility detection
 * - Fallback format suggestions
 * - User-friendly error messages
 */

export interface VideoFormatInfo {
  extension: string;
  mimeType: string;
  codec?: string;
  containerFormat: string;
  displayName: string;
  browserSupport: 'universal' | 'modern' | 'limited' | 'unsupported';
  description: string;
}

export interface VideoFormatValidationResult {
  isSupported: boolean;
  confidence: 'certainly' | 'probably' | 'maybe' | 'no';
  originalFormat: VideoFormatInfo;
  supportedAlternatives: VideoFormatInfo[];
  errorMessage?: string;
  recommendation?: string;
}

export interface VideoCompatibilityReport {
  url: string;
  filename: string;
  detectedFormat: VideoFormatInfo;
  validationResult: VideoFormatValidationResult;
  fallbackUrls: string[];
  browserCapabilities: BrowserVideoCapabilities;
}

export interface BrowserVideoCapabilities {
  supportsMP4: boolean;
  supportsWebM: boolean;
  supportsOgg: boolean;
  supportsHLS: boolean;
  supportedCodecs: {
    h264: boolean;
    h265: boolean;
    vp8: boolean;
    vp9: boolean;
    av1: boolean;
  };
}

class VideoFormatValidator {
  private formatDefinitions: Map<string, VideoFormatInfo>;
  private browserCapabilities: BrowserVideoCapabilities;

  constructor() {
    this.formatDefinitions = this.initializeFormatDefinitions();
    this.browserCapabilities = this.detectBrowserCapabilities();
  }

  private initializeFormatDefinitions(): Map<string, VideoFormatInfo> {
    const formats = new Map<string, VideoFormatInfo>();

    // MP4 formats
    formats.set('mp4', {
      extension: 'mp4',
      mimeType: 'video/mp4',
      codec: 'avc1.42E01E, mp4a.40.2',
      containerFormat: 'MPEG-4',
      displayName: 'MP4',
      browserSupport: 'universal',
      description: 'Most compatible video format, supported by all modern browsers'
    });

    formats.set('m4v', {
      extension: 'm4v',
      mimeType: 'video/mp4',
      codec: 'avc1.42E01E, mp4a.40.2',
      containerFormat: 'MPEG-4',
      displayName: 'M4V',
      browserSupport: 'universal',
      description: 'Apple iTunes video format, compatible with MP4'
    });

    // WebM formats
    formats.set('webm', {
      extension: 'webm',
      mimeType: 'video/webm',
      codec: 'vp8, vorbis',
      containerFormat: 'WebM',
      displayName: 'WebM',
      browserSupport: 'modern',
      description: 'Open-source format, excellent compression and quality'
    });

    // OGG formats
    formats.set('ogv', {
      extension: 'ogv',
      mimeType: 'video/ogg',
      codec: 'theora, vorbis',
      containerFormat: 'Ogg',
      displayName: 'OGV',
      browserSupport: 'limited',
      description: 'Open-source format, limited browser support'
    });

    formats.set('ogg', {
      extension: 'ogg',
      mimeType: 'video/ogg',
      codec: 'theora, vorbis',
      containerFormat: 'Ogg',
      displayName: 'OGG',
      browserSupport: 'limited',
      description: 'Open-source format, limited browser support'
    });

    // MOV formats
    formats.set('mov', {
      extension: 'mov',
      mimeType: 'video/quicktime',
      codec: 'avc1.42E01E, mp4a.40.2',
      containerFormat: 'QuickTime',
      displayName: 'MOV',
      browserSupport: 'limited',
      description: 'Apple QuickTime format, limited web browser support'
    });

    formats.set('qt', {
      extension: 'qt',
      mimeType: 'video/quicktime',
      codec: 'avc1.42E01E, mp4a.40.2',
      containerFormat: 'QuickTime',
      displayName: 'QuickTime',
      browserSupport: 'limited',
      description: 'Apple QuickTime format, limited web browser support'
    });

    // AVI formats
    formats.set('avi', {
      extension: 'avi',
      mimeType: 'video/x-msvideo',
      containerFormat: 'AVI',
      displayName: 'AVI',
      browserSupport: 'unsupported',
      description: 'Legacy format, not supported in web browsers without conversion'
    });

    // MKV formats
    formats.set('mkv', {
      extension: 'mkv',
      mimeType: 'video/x-matroska',
      containerFormat: 'Matroska',
      displayName: 'MKV',
      browserSupport: 'unsupported',
      description: 'High-quality format, not natively supported in web browsers'
    });

    // HLS formats
    formats.set('m3u8', {
      extension: 'm3u8',
      mimeType: 'application/x-mpegURL',
      containerFormat: 'HLS',
      displayName: 'HLS Stream',
      browserSupport: 'modern',
      description: 'HTTP Live Streaming format, requires HLS.js library'
    });

    // DASH formats
    formats.set('mpd', {
      extension: 'mpd',
      mimeType: 'application/dash+xml',
      containerFormat: 'DASH',
      displayName: 'DASH Stream',
      browserSupport: 'modern',
      description: 'Dynamic Adaptive Streaming, requires DASH.js library'
    });

    return formats;
  }

  private detectBrowserCapabilities(): BrowserVideoCapabilities {
    const video = document.createElement('video');

    return {
      supportsMP4: this.canPlayFormat(video, 'video/mp4'),
      supportsWebM: this.canPlayFormat(video, 'video/webm'),
      supportsOgg: this.canPlayFormat(video, 'video/ogg'),
      supportsHLS: this.canPlayFormat(video, 'application/x-mpegURL'),
      supportedCodecs: {
        h264: this.canPlayFormat(video, 'video/mp4; codecs="avc1.42E01E"'),
        h265: this.canPlayFormat(video, 'video/mp4; codecs="hev1.1.6.L93.B0"'),
        vp8: this.canPlayFormat(video, 'video/webm; codecs="vp8"'),
        vp9: this.canPlayFormat(video, 'video/webm; codecs="vp9"'),
        av1: this.canPlayFormat(video, 'video/mp4; codecs="av01.0.01M.08"')
      }
    };
  }

  private canPlayFormat(video: HTMLVideoElement, mimeType: string): boolean {
    const result = video.canPlayType(mimeType);
    return result === 'probably' || result === 'maybe';
  }

  /**
   * Extract format information from filename or URL
   */
  getFormatFromFilename(filename: string): VideoFormatInfo {
    const extension = this.extractExtension(filename);
    const formatInfo = this.formatDefinitions.get(extension);

    if (formatInfo) {
      return formatInfo;
    }

    // Unknown format
    return {
      extension,
      mimeType: 'video/*',
      containerFormat: 'Unknown',
      displayName: extension.toUpperCase(),
      browserSupport: 'unsupported',
      description: `Unknown video format: ${extension}`
    };
  }

  /**
   * Validate if a video format is supported by the current browser
   */
  validateVideoFormat(filename: string): VideoFormatValidationResult {
    const formatInfo = this.getFormatFromFilename(filename);
    const video = document.createElement('video');

    // Test basic MIME type support
    let confidence: VideoFormatValidationResult['confidence'] = 'no';
    let isSupported = false;

    if (formatInfo.mimeType !== 'video/*') {
      const canPlayResult = video.canPlayType(formatInfo.mimeType);
      
      switch (canPlayResult) {
        case 'probably':
          confidence = 'probably';
          isSupported = true;
          break;
        case 'maybe':
          confidence = 'maybe';
          isSupported = true;
          break;
        case '':
        default:
          confidence = 'no';
          isSupported = false;
          break;
      }

      // Test with codec if available
      if (formatInfo.codec && canPlayResult !== 'probably') {
        const codecResult = video.canPlayType(`${formatInfo.mimeType}; codecs="${formatInfo.codec}"`);
        if (codecResult === 'probably') {
          confidence = 'probably';
          isSupported = true;
        } else if (codecResult === 'maybe' && !isSupported) {
          confidence = 'maybe';
          isSupported = true;
        }
      }
    }

    // Get supported alternatives
    const supportedAlternatives = this.getSupportedAlternatives(formatInfo);

    let errorMessage: string | undefined;
    let recommendation: string | undefined;

    if (!isSupported) {
      errorMessage = this.generateErrorMessage(formatInfo);
      recommendation = this.generateRecommendation(formatInfo, supportedAlternatives);
    }

    return {
      isSupported,
      confidence,
      originalFormat: formatInfo,
      supportedAlternatives,
      errorMessage,
      recommendation
    };
  }

  /**
   * Get list of supported alternative formats
   */
  private getSupportedAlternatives(currentFormat: VideoFormatInfo): VideoFormatInfo[] {
    const alternatives: VideoFormatInfo[] = [];

    // Always recommend MP4 if not already MP4
    if (currentFormat.extension !== 'mp4' && this.browserCapabilities.supportsMP4) {
      const mp4Format = this.formatDefinitions.get('mp4');
      if (mp4Format) alternatives.push(mp4Format);
    }

    // Recommend WebM for modern browsers
    if (currentFormat.extension !== 'webm' && this.browserCapabilities.supportsWebM) {
      const webmFormat = this.formatDefinitions.get('webm');
      if (webmFormat) alternatives.push(webmFormat);
    }

    // Recommend OGG as fallback
    if (currentFormat.extension !== 'ogv' && this.browserCapabilities.supportsOgg) {
      const oggFormat = this.formatDefinitions.get('ogv');
      if (oggFormat) alternatives.push(oggFormat);
    }

    return alternatives;
  }

  /**
   * Generate user-friendly error message
   */
  private generateErrorMessage(formatInfo: VideoFormatInfo): string {
    switch (formatInfo.browserSupport) {
      case 'unsupported':
        return `The ${formatInfo.displayName} format is not supported by web browsers. Please convert your video to a web-compatible format.`;
      
      case 'limited':
        return `The ${formatInfo.displayName} format has limited browser support. Some users may not be able to play this video.`;
      
      case 'modern':
        return `The ${formatInfo.displayName} format requires a modern browser. Please update your browser or use a different format.`;
      
      default:
        return `The video format ${formatInfo.displayName} is not supported by your current browser.`;
    }
  }

  /**
   * Generate format recommendation
   */
  private generateRecommendation(formatInfo: VideoFormatInfo, alternatives: VideoFormatInfo[]): string {
    if (alternatives.length === 0) {
      return 'Please convert your video to MP4 format for maximum compatibility.';
    }

    const recommendedFormat = alternatives[0];
    return `We recommend converting your video to ${recommendedFormat.displayName} format for better compatibility.`;
  }

  /**
   * Generate fallback URLs for a video
   */
  generateFallbackUrls(originalUrl: string): string[] {
    const fallbackUrls: string[] = [];
    const basePath = originalUrl.substring(0, originalUrl.lastIndexOf('.'));

    // Generate URLs for supported formats
    if (this.browserCapabilities.supportsMP4) {
      fallbackUrls.push(`${basePath}.mp4`);
    }
    
    if (this.browserCapabilities.supportsWebM) {
      fallbackUrls.push(`${basePath}.webm`);
    }
    
    if (this.browserCapabilities.supportsOgg) {
      fallbackUrls.push(`${basePath}.ogv`);
    }

    return fallbackUrls.filter(url => url !== originalUrl);
  }

  /**
   * Perform comprehensive video compatibility analysis
   */
  async analyzeVideoCompatibility(url: string, filename: string): Promise<VideoCompatibilityReport> {
    const detectedFormat = this.getFormatFromFilename(filename);
    const validationResult = this.validateVideoFormat(filename);
    const fallbackUrls = this.generateFallbackUrls(url);

    return {
      url,
      filename,
      detectedFormat,
      validationResult,
      fallbackUrls,
      browserCapabilities: this.browserCapabilities
    };
  }

  /**
   * Test if a specific URL/format combination can be played
   */
  async testVideoPlayability(url: string): Promise<{
    canPlay: boolean;
    error?: string;
    loadTime?: number;
  }> {
    return new Promise((resolve) => {
      const video = document.createElement('video');
      const startTime = Date.now();
      let timeoutId: NodeJS.Timeout;

      const cleanup = () => {
        clearTimeout(timeoutId);
        video.removeEventListener('canplay', handleCanPlay);
        video.removeEventListener('error', handleError);
        video.src = '';
      };

      const handleCanPlay = () => {
        cleanup();
        resolve({
          canPlay: true,
          loadTime: Date.now() - startTime
        });
      };

      const handleError = () => {
        cleanup();
        const error = video.error;
        let errorMessage = 'Unknown video error';
        
        if (error) {
          switch (error.code) {
            case MediaError.MEDIA_ERR_ABORTED:
              errorMessage = 'Video loading was aborted';
              break;
            case MediaError.MEDIA_ERR_NETWORK:
              errorMessage = 'Network error occurred while loading video';
              break;
            case MediaError.MEDIA_ERR_DECODE:
              errorMessage = 'Video decoding error - format may be corrupted';
              break;
            case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
              errorMessage = 'Video format not supported by this browser';
              break;
          }
        }

        resolve({
          canPlay: false,
          error: errorMessage
        });
      };

      // Set up timeout (10 seconds)
      timeoutId = setTimeout(() => {
        cleanup();
        resolve({
          canPlay: false,
          error: 'Video loading timeout - file may be too large or network is slow'
        });
      }, 10000);

      video.addEventListener('canplay', handleCanPlay);
      video.addEventListener('error', handleError);
      video.preload = 'metadata';
      video.src = url;
    });
  }

  /**
   * Get browser capabilities report
   */
  getBrowserCapabilities(): BrowserVideoCapabilities {
    return { ...this.browserCapabilities };
  }

  /**
   * Get all supported formats for current browser
   */
  getSupportedFormats(): VideoFormatInfo[] {
    const supported: VideoFormatInfo[] = [];

    for (const formatInfo of this.formatDefinitions.values()) {
      if (formatInfo.browserSupport === 'universal' || 
          formatInfo.browserSupport === 'modern') {
        const video = document.createElement('video');
        const canPlay = this.canPlayFormat(video, formatInfo.mimeType);
        
        if (canPlay) {
          supported.push(formatInfo);
        }
      }
    }

    return supported;
  }

  /**
   * Extract file extension from filename or URL
   */
  private extractExtension(filename: string): string {
    const lastDotIndex = filename.lastIndexOf('.');
    if (lastDotIndex === -1) return '';
    
    return filename.substring(lastDotIndex + 1).toLowerCase();
  }

  /**
   * Get format recommendations for upload
   */
  getUploadRecommendations(): {
    recommended: VideoFormatInfo[];
    acceptable: VideoFormatInfo[];
    avoid: VideoFormatInfo[];
  } {
    const allFormats = Array.from(this.formatDefinitions.values());

    return {
      recommended: allFormats.filter(f => f.browserSupport === 'universal'),
      acceptable: allFormats.filter(f => f.browserSupport === 'modern'),
      avoid: allFormats.filter(f => f.browserSupport === 'limited' || f.browserSupport === 'unsupported')
    };
  }
}

// Export singleton instance
export const videoFormatValidator = new VideoFormatValidator();

// Export convenience functions
export const validateVideoFormat = (filename: string) => 
  videoFormatValidator.validateVideoFormat(filename);

export const getFormatFromFilename = (filename: string) => 
  videoFormatValidator.getFormatFromFilename(filename);

export const analyzeVideoCompatibility = (url: string, filename: string) => 
  videoFormatValidator.analyzeVideoCompatibility(url, filename);

export const testVideoPlayability = (url: string) => 
  videoFormatValidator.testVideoPlayability(url);

export const getBrowserCapabilities = () => 
  videoFormatValidator.getBrowserCapabilities();

export const getSupportedFormats = () => 
  videoFormatValidator.getSupportedFormats();

export const getUploadRecommendations = () => 
  videoFormatValidator.getUploadRecommendations();

export default videoFormatValidator;