/**
 * Video Debugging Helper Utility
 * Comprehensive video troubleshooting and diagnostic tools
 */

import { VideoFile } from '../services/types';
import { diagnoseVideoCompatibility } from '../types/VideoFormat';
import { fixVideoUrl } from './videoUrlFixer';

export interface VideoDebugResult {
  url: string;
  originalUrl: string;
  exists: boolean;
  canPlay: boolean;
  format: string;
  size?: number;
  duration?: number;
  error?: string;
  networkError?: boolean;
  codecSupported?: boolean;
  browserCompatible?: boolean;
}

/**
 * Comprehensive video debugging function
 */
export async function debugVideoFile(video: VideoFile): Promise<VideoDebugResult> {
  console.log('🔍 Debugging video:', video);
  
  const result: VideoDebugResult = {
    url: '',
    originalUrl: video.url || '',
    exists: false,
    canPlay: false,
    format: video.format || 'unknown',
  };

  try {
    // Fix and validate URL
    result.url = fixVideoUrl(video.url, video.filename, video.id, { debug: true });
    
    if (!result.url) {
      result.error = 'No valid URL could be generated';
      return result;
    }

    console.log('🔧 Fixed URL:', result.originalUrl, '->', result.url);

    // Check if file exists via HEAD request
    try {
      const response = await fetch(result.url, { method: 'HEAD' });
      result.exists = response.ok;
      result.size = parseInt(response.headers.get('content-length') || '0');
      
      if (!result.exists) {
        result.error = `File not found: ${response.status} ${response.statusText}`;
        return result;
      }
    } catch (error) {
      result.networkError = true;
      result.error = `Network error: ${error instanceof Error ? error.message : 'Unknown'}`;
      return result;
    }

    // Test video compatibility and playback
    const compatibility = await diagnoseVideoCompatibility(result.url);
    result.canPlay = compatibility.canPlay;
    result.codecSupported = compatibility.formatSupported;
    result.browserCompatible = !compatibility.error?.includes('format not supported');
    
    if (compatibility.error) {
      result.error = compatibility.error;
    }

    // Get video duration if possible
    try {
      const video = document.createElement('video');
      video.src = result.url;
      
      await new Promise((resolve, reject) => {
        video.addEventListener('loadedmetadata', () => {
          result.duration = video.duration;
          resolve(void 0);
        });
        video.addEventListener('error', reject);
        
        setTimeout(reject, 5000); // 5 second timeout
      });
    } catch (error) {
      // Duration detection failed, not critical
    }

    return result;

  } catch (error) {
    result.error = error instanceof Error ? error.message : 'Unknown error';
    return result;
  }
}

/**
 * Debug multiple videos in batch
 */
export async function debugVideoList(videos: VideoFile[]): Promise<VideoDebugResult[]> {
  console.log('🔍 Debugging video list:', videos.length, 'videos');
  
  const results: VideoDebugResult[] = [];
  
  // Process in small batches to avoid overwhelming the browser
  const batchSize = 3;
  for (let i = 0; i < videos.length; i += batchSize) {
    const batch = videos.slice(i, i + batchSize);
    const batchPromises = batch.map(video => debugVideoFile(video));
    const batchResults = await Promise.all(batchPromises);
    results.push(...batchResults);
    
    // Small delay between batches
    if (i + batchSize < videos.length) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  
  return results;
}

/**
 * Generate debugging report
 */
export function generateVideoDebugReport(results: VideoDebugResult[]): {
  summary: string;
  workingVideos: number;
  brokenVideos: number;
  networkErrors: number;
  formatErrors: number;
  details: VideoDebugResult[];
  recommendations: string[];
} {
  const workingVideos = results.filter(r => r.canPlay).length;
  const brokenVideos = results.length - workingVideos;
  const networkErrors = results.filter(r => r.networkError).length;
  const formatErrors = results.filter(r => r.error?.includes('format')).length;
  
  const recommendations: string[] = [];
  
  if (networkErrors > 0) {
    recommendations.push(`${networkErrors} videos have network/404 errors - check file paths and server availability`);
  }
  
  if (formatErrors > 0) {
    recommendations.push(`${formatErrors} videos have format/codec issues - re-encode to H.264/MP4 for maximum compatibility`);
  }
  
  if (results.some(r => !r.exists)) {
    recommendations.push('Some video files are missing - verify upload and storage');
  }
  
  if (results.some(r => r.url !== r.originalUrl)) {
    recommendations.push('Video URLs were auto-fixed - update database to use correct URLs');
  }

  const summary = `${workingVideos}/${results.length} videos working (${Math.round(workingVideos / results.length * 100)}%)`;
  
  return {
    summary,
    workingVideos,
    brokenVideos,
    networkErrors,
    formatErrors,
    details: results,
    recommendations
  };
}

/**
 * Browser compatibility check
 */
export function checkBrowserVideoSupport(): {
  h264: boolean;
  webm: boolean;
  ogg: boolean;
  fullscreen: boolean;
} {
  const video = document.createElement('video');
  
  return {
    h264: video.canPlayType('video/mp4; codecs="avc1.42E01E"') !== '',
    webm: video.canPlayType('video/webm; codecs="vp9"') !== '',
    ogg: video.canPlayType('video/ogg; codecs="theora"') !== '',
    fullscreen: !!(document.fullscreenEnabled || 
                   (document as any).webkitFullscreenEnabled || 
                   (document as any).mozFullScreenEnabled || 
                   (document as any).msFullscreenEnabled)
  };
}

/**
 * Console-friendly debugging output
 */
export function logVideoDebugInfo(results: VideoDebugResult[]): void {
  const report = generateVideoDebugReport(results);
  
  console.group('🎬 Video Debug Report');
  console.log('📊 Summary:', report.summary);
  console.log('✅ Working videos:', report.workingVideos);
  console.log('❌ Broken videos:', report.brokenVideos);
  console.log('🌐 Network errors:', report.networkErrors);
  console.log('🎞️ Format errors:', report.formatErrors);
  
  if (report.recommendations.length > 0) {
    console.group('💡 Recommendations');
    report.recommendations.forEach(rec => console.log('-', rec));
    console.groupEnd();
  }
  
  console.group('📋 Detailed Results');
  results.forEach(result => {
    const status = result.canPlay ? '✅' : '❌';
    const issues = result.error ? ` (${result.error})` : '';
    console.log(`${status} ${result.url}${issues}`);
  });
  console.groupEnd();
  
  const browserSupport = checkBrowserVideoSupport();
  console.group('🌐 Browser Support');
  console.log('H.264/MP4:', browserSupport.h264 ? '✅' : '❌');
  console.log('VP9/WebM:', browserSupport.webm ? '✅' : '❌');
  console.log('Theora/OGG:', browserSupport.ogg ? '✅' : '❌');
  console.log('Fullscreen API:', browserSupport.fullscreen ? '✅' : '❌');
  console.groupEnd();
  
  console.groupEnd();
}