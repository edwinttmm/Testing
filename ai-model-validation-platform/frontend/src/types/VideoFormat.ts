/**
 * Video Format and Codec Support Definitions
 * Helps with video compatibility debugging
 */

export interface VideoFormatInfo {
  container: string;
  codecs: string[];
  mimeType: string;
  browserSupport: {
    chrome: boolean;
    firefox: boolean;
    safari: boolean;
    edge: boolean;
  };
}

export const SUPPORTED_VIDEO_FORMATS: Record<string, VideoFormatInfo> = {
  mp4_h264: {
    container: 'mp4',
    codecs: ['avc1.42E01E', 'avc1.42001E', 'avc1.58A01E'],
    mimeType: 'video/mp4; codecs="avc1.42E01E"',
    browserSupport: {
      chrome: true,
      firefox: true,
      safari: true,
      edge: true
    }
  },
  webm_vp9: {
    container: 'webm',
    codecs: ['vp09.00.10.08'],
    mimeType: 'video/webm; codecs="vp09.00.10.08"',
    browserSupport: {
      chrome: true,
      firefox: true,
      safari: false,
      edge: true
    }
  },
  webm_vp8: {
    container: 'webm',
    codecs: ['vp8'],
    mimeType: 'video/webm; codecs="vp8"',
    browserSupport: {
      chrome: true,
      firefox: true,
      safari: false,
      edge: true
    }
  }
};

/**
 * Check if browser supports a specific video format
 */
export function checkVideoFormatSupport(format: VideoFormatInfo): boolean {
  const video = document.createElement('video');
  return video.canPlayType(format.mimeType) !== '';
}

/**
 * Get supported video formats for current browser
 */
export function getSupportedFormats(): VideoFormatInfo[] {
  return Object.values(SUPPORTED_VIDEO_FORMATS).filter(checkVideoFormatSupport);
}

/**
 * Diagnose video compatibility issues
 */
export function diagnoseVideoCompatibility(videoUrl: string): Promise<{
  canPlay: boolean;
  error?: string;
  formatSupported: boolean;
  networkError?: boolean;
}> {
  return new Promise((resolve) => {
    const video = document.createElement('video');
    const result = {
      canPlay: false,
      formatSupported: false,
      networkError: false
    };

    video.addEventListener('canplaythrough', () => {
      result.canPlay = true;
      result.formatSupported = true;
      resolve(result);
    });

    video.addEventListener('error', (e) => {
      const error = video.error;
      if (error) {
        switch (error.code) {
          case MediaError.MEDIA_ERR_ABORTED:
            resolve({ ...result, error: 'Video loading aborted' });
            break;
          case MediaError.MEDIA_ERR_NETWORK:
            resolve({ ...result, error: 'Network error loading video', networkError: true });
            break;
          case MediaError.MEDIA_ERR_DECODE:
            resolve({ ...result, error: 'Video format not supported by browser', formatSupported: false });
            break;
          case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
            resolve({ ...result, error: 'Video source format not supported', formatSupported: false });
            break;
          default:
            resolve({ ...result, error: 'Unknown video error' });
        }
      } else {
        resolve({ ...result, error: 'Video load error' });
      }
    });

    video.addEventListener('loadstart', () => {
      // Video started loading, good sign
    });

    video.src = videoUrl;
    video.load();

    // Timeout after 10 seconds
    setTimeout(() => {
      if (!result.canPlay) {
        resolve({ ...result, error: 'Video load timeout' });
      }
    }, 10000);
  });
}