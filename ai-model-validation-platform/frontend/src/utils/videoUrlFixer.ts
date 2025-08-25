/**
 * Video URL Fixer Utility
 * 
 * Provides centralized video URL fixing functionality to ensure all video URLs
 * use the correct backend server URL instead of localhost references.
 */

import { getServiceConfig } from './envConfig';

export interface VideoUrlFixOptions {
  forceAbsolute?: boolean | undefined;
  debug?: boolean | undefined;
}

/**
 * Fix video URL to use the correct backend base URL
 * 
 * This function handles:
 * - Localhost URL replacements
 * - Relative URL conversions
 * - Invalid URL corrections
 * - Filename-based URL construction
 */
export function fixVideoUrl(
  url: string | undefined, 
  filename?: string, 
  id?: string,
  options: VideoUrlFixOptions = {}
): string {
  const { forceAbsolute = false, debug = false } = options;
  const videoConfig = getServiceConfig('video');
  
  if (debug) {
    console.log('🔧 fixVideoUrl called with:', { url, filename, id, baseUrl: videoConfig.baseUrl });
  }
  
  // If no URL provided, try to construct from filename or id
  if (!url || url.trim() === '') {
    if (filename && filename.trim()) {
      const fixedUrl = `${videoConfig.baseUrl || ''}/uploads/${filename}`;
      if (debug) {
        console.log('🔧 fixVideoUrl constructed from filename:', fixedUrl);
      }
      return fixedUrl;
    } else if (id && id.trim()) {
      const fixedUrl = `${videoConfig.baseUrl || ''}/uploads/${id}`;
      if (debug) {
        console.log('🔧 fixVideoUrl constructed from id:', fixedUrl);
      }
      return fixedUrl;
    } else {
      if (debug) {
        console.warn('🔧 fixVideoUrl no URL, filename, or id provided');
      }
      return '';
    }
  }
  
  // Fix localhost URLs
  if (url.includes('localhost:8000')) {
    const fixedUrl = url.replace('http://localhost:8000', videoConfig.baseUrl || '');
    if (debug) {
      console.log('🔧 fixVideoUrl fixed localhost:', url, '->', fixedUrl);
    }
    return fixedUrl;
  }
  
  // Convert relative URLs to absolute
  if (url.startsWith('/')) {
    const fixedUrl = `${videoConfig.baseUrl || ''}${url}`;
    if (debug) {
      console.log('🔧 fixVideoUrl converted relative URL:', url, '->', fixedUrl);
    }
    return fixedUrl;
  }
  
  // If forcing absolute and URL doesn't have protocol, make it absolute
  if (forceAbsolute && !url.match(/^https?:\/\//)) {
    const fixedUrl = `${videoConfig.baseUrl || ''}/${url}`;
    if (debug) {
      console.log('🔧 fixVideoUrl forced absolute:', url, '->', fixedUrl);
    }
    return fixedUrl;
  }
  
  // URL is already correct, return as-is
  if (debug) {
    console.log('🔧 fixVideoUrl URL already correct:', url);
  }
  return url;
}

/**
 * Fix video object's URL property in-place
 */
export function fixVideoObjectUrl(
  video: { url?: string; filename?: string; id?: string },
  options: VideoUrlFixOptions = {}
): void {
  if (!video) return;
  
  const originalUrl = video.url;
  video.url = fixVideoUrl(video.url, video.filename, video.id, options);
  
  if (options.debug && originalUrl !== video.url) {
    console.log('🔧 fixVideoObjectUrl updated:', originalUrl, '->', video.url);
  }
}

/**
 * Batch fix multiple video URLs
 */
export function fixMultipleVideoUrls(
  videos: Array<{ url?: string; filename?: string; id?: string }>,
  options: VideoUrlFixOptions = {}
): void {
  if (!videos || videos.length === 0) return;
  
  videos.forEach((video, index) => {
    if (video) {
      const debug = options.debug === true && index < 5; // Only debug first 5 to avoid spam
      fixVideoObjectUrl(video, { ...options, debug: debug });
    }
  });
  
  if (options.debug) {
    console.log(`🔧 fixMultipleVideoUrls processed ${videos.length} videos`);
  }
}

/**
 * Validate if a video URL is accessible (basic check)
 */
export function isVideoUrlValid(url: string): boolean {
  if (!url || url.trim() === '') return false;
  
  try {
    const urlObj = new URL(url);
    return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Get the proper video base URL for the current environment
 */
export function getVideoBaseUrl(): string {
  const videoConfig = getServiceConfig('video');
  return videoConfig.baseUrl || '';
}

export default {
  fixVideoUrl,
  fixVideoObjectUrl,
  fixMultipleVideoUrls,
  isVideoUrlValid,
  getVideoBaseUrl
};