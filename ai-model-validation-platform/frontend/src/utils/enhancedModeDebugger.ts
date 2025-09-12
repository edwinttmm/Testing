/**
 * Enhanced Mode Debugging Utilities
 * 
 * Provides comprehensive debugging for Enhanced Mode issues:
 * - Video URL generation and loading
 * - Detection data flow from API to frontend shapes
 * - Canvas rendering and video overlay positioning
 * - Bounding box coordinate mapping
 */

export interface EnhancedModeDebugInfo {
  timestamp: string;
  component: string;
  action: string;
  data: any;
  success: boolean;
  error?: string;
}

class EnhancedModeDebugger {
  private logs: EnhancedModeDebugInfo[] = [];
  private enabled = true; // Always enabled for now to catch issues

  log(component: string, action: string, data: any, success: boolean = true, error?: string): void {
    if (!this.enabled) return;

    const logEntry: EnhancedModeDebugInfo = {
      timestamp: new Date().toISOString(),
      component,
      action,
      data,
      success,
      error
    };

    this.logs.push(logEntry);
    
    // Console output with clear formatting
    const emoji = success ? '✅' : '❌';
    const prefix = `${emoji} [${component}] ${action}:`;
    
    if (success) {
      console.log(prefix, data);
    } else {
      console.error(prefix, data, error ? `Error: ${error}` : '');
    }

    // Keep only last 100 logs to prevent memory issues
    if (this.logs.length > 100) {
      this.logs = this.logs.slice(-100);
    }
  }

  // Specific debugging methods for Enhanced Mode components
  logVideoLoading(videoId: string, videoUrl: string, success: boolean, error?: string): void {
    this.log('VideoLoader', 'LoadVideo', {
      videoId,
      videoUrl,
      urlType: videoUrl.includes('getDynamicVideoUrl') ? 'dynamic' : 'static',
      urlValid: this.isValidUrl(videoUrl)
    }, success, error);
  }

  logDetectionData(source: string, detections: any[], processedShapes: any[]): void {
    this.log('DetectionProcessor', 'ProcessDetections', {
      source,
      rawDetections: detections.length,
      processedShapes: processedShapes.length,
      sampleDetection: detections[0],
      sampleShape: processedShapes[0],
      coordinateMapping: processedShapes.map(shape => ({
        id: shape.id,
        boundingBox: shape.boundingBox,
        hasRealCoords: shape.boundingBox && !(shape.boundingBox.x === 0 && shape.boundingBox.y === 0 && shape.boundingBox.width === 100 && shape.boundingBox.height === 100)
      }))
    }, processedShapes.length > 0);
  }

  logCanvasRendering(canvasInfo: any, videoInfo: any): void {
    this.log('CanvasRenderer', 'RenderFrame', {
      canvas: {
        width: canvasInfo.width,
        height: canvasInfo.height,
        context: canvasInfo.context ? 'available' : 'missing'
      },
      video: {
        width: videoInfo.videoWidth,
        height: videoInfo.videoHeight,
        currentTime: videoInfo.currentTime,
        duration: videoInfo.duration,
        readyState: videoInfo.readyState
      },
      overlay: {
        positioned: canvasInfo.positioned,
        zIndex: canvasInfo.zIndex
      }
    }, canvasInfo.context && videoInfo.videoWidth > 0);
  }

  logBoundingBoxConversion(originalBbox: any, convertedBbox: any, conversionType: string): void {
    this.log('BoundingBoxConverter', 'ConvertCoordinates', {
      original: originalBbox,
      converted: convertedBbox,
      conversionType,
      isDefault: convertedBbox.x === 0 && convertedBbox.y === 0 && convertedBbox.width === 100 && convertedBbox.height === 100,
      hasValidCoords: convertedBbox.width > 0 && convertedBbox.height > 0
    }, convertedBbox.width > 0 && convertedBbox.height > 0);
  }

  logSequentialVideoPlayer(state: any, action: string): void {
    this.log('SequentialVideoPlayer', action, {
      currentIndex: state.currentIndex,
      isPlaying: state.isPlaying,
      isTransitioning: state.isTransitioning,
      totalVideos: state.videos?.length || 0,
      currentVideo: state.videos?.[state.currentIndex],
      videoElement: {
        exists: !!state.videoElement,
        src: state.videoElement?.src,
        readyState: state.videoElement?.readyState,
        paused: state.videoElement?.paused,
        currentTime: state.videoElement?.currentTime
      }
    }, true);
  }

  logNetworkRequest(url: string, method: string, success: boolean, responseData?: any, error?: string): void {
    this.log('NetworkRequest', `${method.toUpperCase()}_${url.split('/').pop()}`, {
      url,
      method,
      success,
      responseKeys: responseData ? Object.keys(responseData) : [],
      dataSize: responseData ? JSON.stringify(responseData).length : 0
    }, success, error);
  }

  // Utility methods
  private isValidUrl(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }

  // Get debugging summary
  getSummary(): { 
    totalLogs: number; 
    errors: number; 
    recentErrors: EnhancedModeDebugInfo[];
    componentBreakdown: Record<string, number>;
  } {
    const errors = this.logs.filter(log => !log.success);
    const componentBreakdown = this.logs.reduce((acc, log) => {
      acc[log.component] = (acc[log.component] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return {
      totalLogs: this.logs.length,
      errors: errors.length,
      recentErrors: errors.slice(-10),
      componentBreakdown
    };
  }

  // Clear logs
  clear(): void {
    this.logs = [];
    console.log('🧹 Enhanced Mode debugger logs cleared');
  }

  // Export logs for analysis
  export(): EnhancedModeDebugInfo[] {
    return [...this.logs];
  }
}

// Global singleton instance
export const enhancedModeDebugger = new EnhancedModeDebugger();

// Convenience functions
export const debugVideoLoading = (videoId: string, videoUrl: string, success: boolean, error?: string) => 
  enhancedModeDebugger.logVideoLoading(videoId, videoUrl, success, error);

export const debugDetectionData = (source: string, detections: any[], processedShapes: any[]) => 
  enhancedModeDebugger.logDetectionData(source, detections, processedShapes);

export const debugCanvasRendering = (canvasInfo: any, videoInfo: any) => 
  enhancedModeDebugger.logCanvasRendering(canvasInfo, videoInfo);

export const debugBoundingBoxConversion = (originalBbox: any, convertedBbox: any, conversionType: string) => 
  enhancedModeDebugger.logBoundingBoxConversion(originalBbox, convertedBbox, conversionType);

export const debugSequentialVideoPlayer = (state: any, action: string) => 
  enhancedModeDebugger.logSequentialVideoPlayer(state, action);

export const debugNetworkRequest = (url: string, method: string, success: boolean, responseData?: any, error?: string) => 
  enhancedModeDebugger.logNetworkRequest(url, method, success, responseData, error);

// Make debugger available globally for manual inspection in browser console
if (typeof window !== 'undefined') {
  (window as any).enhancedModeDebugger = enhancedModeDebugger;
}

export default enhancedModeDebugger;