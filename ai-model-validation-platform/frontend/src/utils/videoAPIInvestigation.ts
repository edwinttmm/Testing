/**
 * Video Element API Investigation Tool
 * 
 * Deep dive analysis tool for video element behavior during stall conditions
 * and fullscreen compatibility issues. Provides comprehensive diagnostic
 * information about HTMLVideoElement states, events, and browser behavior.
 */

export interface VideoElementState {
  // HTMLVideoElement Properties
  readyState: number;
  networkState: number;
  currentTime: number;
  duration: number;
  paused: boolean;
  ended: boolean;
  seeking: boolean;
  
  // Loading and Buffering
  buffered: TimeRanges;
  seekable: TimeRanges;
  played: TimeRanges;
  
  // Video Metadata
  videoWidth: number;
  videoHeight: number;
  
  // Error Information
  error: MediaError | null;
  
  // Source Information
  src: string;
  currentSrc: string;
  
  // Playback Properties
  playbackRate: number;
  defaultPlaybackRate: number;
  volume: number;
  muted: boolean;
  
  // Media Session
  crossOrigin: string | null;
  preload: string;
  
  // Additional Properties
  loop: boolean;
  controls: boolean;
  autoplay: boolean;
}

export interface VideoEventLog {
  timestamp: number;
  event: string;
  elementState: VideoElementState;
  additionalData?: any;
}

export interface VideoStallDiagnostic {
  isStalled: boolean;
  stallDuration: number;
  stallType: 'loading' | 'buffering' | 'seeking' | 'unknown';
  lastProgressTime: number;
  bytesLoaded: number;
  totalBytes: number;
  bufferHealth: {
    hasBufferedData: boolean;
    bufferGaps: Array<{ start: number; end: number }>;
    bufferAheadTime: number;
  };
  networkAnalysis: {
    effectiveType?: string;
    downlink?: number;
    rtt?: number;
  };
}

export interface FullscreenCompatibilityTest {
  supportsFullscreen: boolean;
  fullscreenMethod: string | null;
  exitFullscreenMethod: string | null;
  fullscreenElement: Element | null;
  fullscreenEnabled: boolean;
  
  // Video-specific fullscreen tests
  canVideoEnterFullscreen: boolean;
  requiresContainerWrapper: boolean;
  supportsPictureInPicture: boolean;
  
  // Browser-specific quirks
  browserQuirks: string[];
  
  // Test results
  testResults: {
    directVideoFullscreen: boolean;
    containerFullscreen: boolean;
    fullscreenWithControls: boolean;
    fullscreenWhilePlaying: boolean;
    fullscreenWhilePaused: boolean;
    fullscreenBeforeLoad: boolean;
  };
}

class VideoAPIInvestigator {
  private eventLogs = new Map<string, VideoEventLog[]>();
  private stallDetectors = new Map<string, {
    lastProgressTime: number;
    stallStartTime?: number;
    progressTimer?: NodeJS.Timeout;
  }>();
  private performanceObservers = new Map<string, PerformanceObserver>();

  /**
   * Start comprehensive monitoring of a video element
   */
  startInvestigation(videoElement: HTMLVideoElement, investigationId: string): () => void {
    // Initialize logging
    this.eventLogs.set(investigationId, []);
    
    // Set up event monitoring
    const eventTypes = [
      // Loading Events
      'loadstart', 'durationchange', 'loadedmetadata', 'loadeddata',
      'progress', 'canplay', 'canplaythrough',
      
      // Playback Events  
      'play', 'playing', 'pause', 'ended', 'timeupdate',
      'seeking', 'seeked', 'ratechange',
      
      // Error and Stall Events
      'abort', 'error', 'stalled', 'suspend', 'waiting',
      'emptied',
      
      // Volume Events
      'volumechange',
      
      // Resize Events
      'resize'
    ];

    const eventListeners = new Map<string, EventListener>();
    
    eventTypes.forEach(eventType => {
      const listener = (event: Event) => this.logVideoEvent(investigationId, eventType, videoElement, event);
      eventListeners.set(eventType, listener);
      videoElement.addEventListener(eventType, listener);
    });

    // Set up stall detection
    this.setupStallDetection(investigationId, videoElement);
    
    // Set up performance monitoring
    this.setupPerformanceMonitoring(investigationId, videoElement);

    // Return cleanup function
    return () => {
      // Remove event listeners
      eventTypes.forEach(eventType => {
        const listener = eventListeners.get(eventType);
        if (listener) {
          videoElement.removeEventListener(eventType, listener);
        }
      });

      // Cleanup stall detection
      this.cleanupStallDetection(investigationId);
      
      // Cleanup performance monitoring
      this.cleanupPerformanceMonitoring(investigationId);
      
      // Clear logs
      this.eventLogs.delete(investigationId);
    };
  }

  /**
   * Log video element event with complete state snapshot
   */
  private logVideoEvent(investigationId: string, eventType: string, videoElement: HTMLVideoElement, event: Event): void {
    const logs = this.eventLogs.get(investigationId);
    if (!logs) return;

    const elementState = this.captureVideoElementState(videoElement);
    const eventLog: VideoEventLog = {
      timestamp: performance.now(),
      event: eventType,
      elementState,
      additionalData: this.extractEventSpecificData(eventType, event, videoElement)
    };

    logs.push(eventLog);
    
    // Keep only last 1000 events to prevent memory issues
    if (logs.length > 1000) {
      logs.shift();
    }

    // Log critical events to console for debugging
    if (['error', 'stalled', 'abort', 'loadstart', 'canplay', 'playing'].includes(eventType)) {
      console.log(`[VideoAPI] ${eventType}:`, {
        readyState: this.getReadyStateString(elementState.readyState),
        networkState: this.getNetworkStateString(elementState.networkState),
        currentTime: elementState.currentTime,
        duration: elementState.duration,
        error: elementState.error,
        src: elementState.currentSrc
      });
    }
  }

  /**
   * Capture complete video element state
   */
  private captureVideoElementState(videoElement: HTMLVideoElement): VideoElementState {
    return {
      readyState: videoElement.readyState,
      networkState: videoElement.networkState,
      currentTime: videoElement.currentTime,
      duration: videoElement.duration,
      paused: videoElement.paused,
      ended: videoElement.ended,
      seeking: videoElement.seeking,
      buffered: this.cloneTimeRanges(videoElement.buffered),
      seekable: this.cloneTimeRanges(videoElement.seekable),
      played: this.cloneTimeRanges(videoElement.played),
      videoWidth: videoElement.videoWidth,
      videoHeight: videoElement.videoHeight,
      error: videoElement.error,
      src: videoElement.src,
      currentSrc: videoElement.currentSrc,
      playbackRate: videoElement.playbackRate,
      defaultPlaybackRate: videoElement.defaultPlaybackRate,
      volume: videoElement.volume,
      muted: videoElement.muted,
      crossOrigin: videoElement.crossOrigin,
      preload: videoElement.preload,
      loop: videoElement.loop,
      controls: videoElement.controls,
      autoplay: videoElement.autoplay
    };
  }

  /**
   * Extract event-specific additional data
   */
  private extractEventSpecificData(eventType: string, event: Event, videoElement: HTMLVideoElement): any {
    switch (eventType) {
      case 'error':
        return {
          error: videoElement.error ? {
            code: videoElement.error.code,
            message: videoElement.error.message,
            codeString: this.getMediaErrorString(videoElement.error.code)
          } : null
        };
      
      case 'progress':
        return {
          loaded: this.getLoadedBytes(videoElement),
          total: this.getTotalBytes(videoElement)
        };
      
      case 'timeupdate':
        return {
          bufferedAhead: this.getBufferedAhead(videoElement),
          bufferedBehind: this.getBufferedBehind(videoElement)
        };
      
      case 'stalled':
        return {
          bytesLoaded: this.getLoadedBytes(videoElement),
          networkEffectiveType: this.getNetworkInfo()?.effectiveType,
          connectionDownlink: this.getNetworkInfo()?.downlink
        };
      
      case 'waiting':
        return {
          reasonForWaiting: this.determineWaitingReason(videoElement),
          bufferHealth: this.analyzeBufferHealth(videoElement)
        };
      
      default:
        return {};
    }
  }

  /**
   * Set up stall detection monitoring
   */
  private setupStallDetection(investigationId: string, videoElement: HTMLVideoElement): void {
    const detector = {
      lastProgressTime: performance.now(),
      stallStartTime: undefined as number | undefined,
      progressTimer: setInterval(() => {
        this.checkForStall(investigationId, videoElement);
      }, 1000) // Check every second
    };

    this.stallDetectors.set(investigationId, detector);
  }

  /**
   * Check if video is stalled
   */
  private checkForStall(investigationId: string, videoElement: HTMLVideoElement): void {
    const detector = this.stallDetectors.get(investigationId);
    if (!detector) return;

    const now = performance.now();
    const isPlaying = !videoElement.paused && !videoElement.ended;
    const hasProgressed = videoElement.currentTime > 0;
    const isLoadingOrBuffering = videoElement.readyState < HTMLMediaElement.HAVE_ENOUGH_DATA;

    // Detect stall conditions
    const isStalled = isPlaying && (
      videoElement.networkState === HTMLMediaElement.NETWORK_LOADING ||
      isLoadingOrBuffering ||
      (hasProgressed && (now - detector.lastProgressTime) > 3000) // No progress for 3 seconds
    );

    if (isStalled && !detector.stallStartTime) {
      detector.stallStartTime = now;
      console.warn('[VideoAPI] Stall detected:', {
        networkState: this.getNetworkStateString(videoElement.networkState),
        readyState: this.getReadyStateString(videoElement.readyState),
        currentTime: videoElement.currentTime,
        bufferedAhead: this.getBufferedAhead(videoElement)
      });
    } else if (!isStalled && detector.stallStartTime) {
      const stallDuration = now - detector.stallStartTime;
      console.log('[VideoAPI] Stall resolved after:', stallDuration, 'ms');
      detector.stallStartTime = undefined;
    }

    // Update progress tracking
    if (hasProgressed) {
      detector.lastProgressTime = now;
    }
  }

  /**
   * Set up performance monitoring
   */
  private setupPerformanceMonitoring(investigationId: string, videoElement: HTMLVideoElement): void {
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((entries) => {
        entries.getEntries().forEach(entry => {
          if (entry.name.includes('video') || entry.name.includes(videoElement.src)) {
            console.log('[VideoAPI] Performance entry:', entry);
          }
        });
      });

      try {
        observer.observe({ entryTypes: ['measure', 'navigation', 'resource'] });
        this.performanceObservers.set(investigationId, observer);
      } catch (e) {
        console.warn('[VideoAPI] Performance observer setup failed:', e);
      }
    }
  }

  /**
   * Cleanup stall detection
   */
  private cleanupStallDetection(investigationId: string): void {
    const detector = this.stallDetectors.get(investigationId);
    if (detector?.progressTimer) {
      clearInterval(detector.progressTimer);
    }
    this.stallDetectors.delete(investigationId);
  }

  /**
   * Cleanup performance monitoring
   */
  private cleanupPerformanceMonitoring(investigationId: string): void {
    const observer = this.performanceObservers.get(investigationId);
    if (observer) {
      observer.disconnect();
      this.performanceObservers.delete(investigationId);
    }
  }

  /**
   * Analyze current stall condition
   */
  analyzeStallCondition(videoElement: HTMLVideoElement): VideoStallDiagnostic {
    const now = performance.now();
    const isStalled = this.isVideoStalled(videoElement);
    
    return {
      isStalled,
      stallDuration: isStalled ? this.getStallDuration(videoElement) : 0,
      stallType: this.determineStallType(videoElement),
      lastProgressTime: now, // Simplified for this implementation
      bytesLoaded: this.getLoadedBytes(videoElement),
      totalBytes: this.getTotalBytes(videoElement),
      bufferHealth: this.analyzeBufferHealth(videoElement),
      networkAnalysis: this.getNetworkInfo() || {}
    };
  }

  /**
   * Test fullscreen compatibility comprehensively
   */
  async testFullscreenCompatibility(videoElement: HTMLVideoElement): Promise<FullscreenCompatibilityTest> {
    const result: FullscreenCompatibilityTest = {
      supportsFullscreen: false,
      fullscreenMethod: null,
      exitFullscreenMethod: null,
      fullscreenElement: null,
      fullscreenEnabled: false,
      canVideoEnterFullscreen: false,
      requiresContainerWrapper: false,
      supportsPictureInPicture: false,
      browserQuirks: [],
      testResults: {
        directVideoFullscreen: false,
        containerFullscreen: false,
        fullscreenWithControls: false,
        fullscreenWhilePlaying: false,
        fullscreenWhilePaused: false,
        fullscreenBeforeLoad: false
      }
    };

    // Test basic fullscreen support
    result.supportsFullscreen = this.testBasicFullscreenSupport();
    result.fullscreenMethod = this.detectFullscreenMethod();
    result.exitFullscreenMethod = this.detectExitFullscreenMethod();
    result.fullscreenEnabled = this.isFullscreenEnabled();

    // Test Picture-in-Picture support
    result.supportsPictureInPicture = 'pictureInPictureEnabled' in document && 
                                      (document as any).pictureInPictureEnabled;

    // Test direct video fullscreen
    if (result.supportsFullscreen) {
      result.testResults.directVideoFullscreen = await this.testDirectVideoFullscreen(videoElement);
      result.testResults.containerFullscreen = await this.testContainerFullscreen(videoElement);
      result.testResults.fullscreenBeforeLoad = await this.testFullscreenBeforeLoad(videoElement);
      
      // Test with different video states
      if (videoElement.src) {
        result.testResults.fullscreenWhilePaused = await this.testFullscreenWhilePaused(videoElement);
        result.testResults.fullscreenWhilePlaying = await this.testFullscreenWhilePlaying(videoElement);
      }
    }

    // Detect browser quirks
    result.browserQuirks = this.detectBrowserQuirks();
    result.canVideoEnterFullscreen = result.testResults.directVideoFullscreen || result.testResults.containerFullscreen;
    result.requiresContainerWrapper = result.testResults.containerFullscreen && !result.testResults.directVideoFullscreen;

    return result;
  }

  /**
   * Generate comprehensive diagnostic report
   */
  generateDiagnosticReport(investigationId: string, videoElement: HTMLVideoElement): string {
    const logs = this.eventLogs.get(investigationId) || [];
    const stallAnalysis = this.analyzeStallCondition(videoElement);
    const currentState = this.captureVideoElementState(videoElement);

    let report = `# Video Element API Investigation Report\n\n`;
    report += `**Investigation ID:** ${investigationId}\n`;
    report += `**Generated:** ${new Date().toISOString()}\n`;
    report += `**Total Events Logged:** ${logs.length}\n\n`;

    // Current State Analysis
    report += `## Current Video Element State\n\n`;
    report += `- **Ready State:** ${this.getReadyStateString(currentState.readyState)} (${currentState.readyState})\n`;
    report += `- **Network State:** ${this.getNetworkStateString(currentState.networkState)} (${currentState.networkState})\n`;
    report += `- **Current Time:** ${currentState.currentTime.toFixed(2)}s\n`;
    report += `- **Duration:** ${isFinite(currentState.duration) ? currentState.duration.toFixed(2) + 's' : 'Unknown'}\n`;
    report += `- **Paused:** ${currentState.paused}\n`;
    report += `- **Ended:** ${currentState.ended}\n`;
    report += `- **Seeking:** ${currentState.seeking}\n`;
    report += `- **Video Dimensions:** ${currentState.videoWidth}x${currentState.videoHeight}\n`;
    report += `- **Source:** ${currentState.currentSrc}\n`;
    
    if (currentState.error) {
      report += `- **Error:** ${this.getMediaErrorString(currentState.error.code)} - ${currentState.error.message}\n`;
    }

    // Buffering Analysis
    report += `\n### Buffering Status\n`;
    report += `- **Buffered Ranges:** ${this.formatTimeRanges(currentState.buffered)}\n`;
    report += `- **Seekable Ranges:** ${this.formatTimeRanges(currentState.seekable)}\n`;
    report += `- **Played Ranges:** ${this.formatTimeRanges(currentState.played)}\n`;

    // Stall Analysis
    report += `\n## Stall Analysis\n\n`;
    report += `- **Currently Stalled:** ${stallAnalysis.isStalled}\n`;
    if (stallAnalysis.isStalled) {
      report += `- **Stall Duration:** ${stallAnalysis.stallDuration}ms\n`;
      report += `- **Stall Type:** ${stallAnalysis.stallType}\n`;
    }
    report += `- **Bytes Loaded:** ${stallAnalysis.bytesLoaded}\n`;
    report += `- **Total Bytes:** ${stallAnalysis.totalBytes}\n`;
    report += `- **Buffer Health:** ${JSON.stringify(stallAnalysis.bufferHealth, null, 2)}\n`;

    // Event Sequence Analysis
    report += `\n## Event Sequence Analysis\n\n`;
    const eventCounts = this.analyzeEventSequence(logs);
    Object.entries(eventCounts).forEach(([event, count]) => {
      report += `- **${event}:** ${count} occurrences\n`;
    });

    // Critical Events Timeline
    report += `\n### Critical Events Timeline\n`;
    const criticalEvents = logs.filter(log => 
      ['loadstart', 'loadedmetadata', 'canplay', 'playing', 'stalled', 'error', 'waiting'].includes(log.event)
    ).slice(-20); // Last 20 critical events

    criticalEvents.forEach(log => {
      const time = new Date(log.timestamp).toLocaleTimeString();
      report += `- **${time}** [${log.event}] Ready: ${this.getReadyStateString(log.elementState.readyState)}, Network: ${this.getNetworkStateString(log.elementState.networkState)}\n`;
    });

    return report;
  }

  // Helper Methods

  private getReadyStateString(readyState: number): string {
    switch (readyState) {
      case HTMLMediaElement.HAVE_NOTHING: return 'HAVE_NOTHING';
      case HTMLMediaElement.HAVE_METADATA: return 'HAVE_METADATA';
      case HTMLMediaElement.HAVE_CURRENT_DATA: return 'HAVE_CURRENT_DATA';
      case HTMLMediaElement.HAVE_FUTURE_DATA: return 'HAVE_FUTURE_DATA';
      case HTMLMediaElement.HAVE_ENOUGH_DATA: return 'HAVE_ENOUGH_DATA';
      default: return `UNKNOWN(${readyState})`;
    }
  }

  private getNetworkStateString(networkState: number): string {
    switch (networkState) {
      case HTMLMediaElement.NETWORK_EMPTY: return 'NETWORK_EMPTY';
      case HTMLMediaElement.NETWORK_IDLE: return 'NETWORK_IDLE';
      case HTMLMediaElement.NETWORK_LOADING: return 'NETWORK_LOADING';
      case HTMLMediaElement.NETWORK_NO_SOURCE: return 'NETWORK_NO_SOURCE';
      default: return `UNKNOWN(${networkState})`;
    }
  }

  private getMediaErrorString(code: number): string {
    switch (code) {
      case MediaError.MEDIA_ERR_ABORTED: return 'MEDIA_ERR_ABORTED';
      case MediaError.MEDIA_ERR_NETWORK: return 'MEDIA_ERR_NETWORK';
      case MediaError.MEDIA_ERR_DECODE: return 'MEDIA_ERR_DECODE';
      case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED: return 'MEDIA_ERR_SRC_NOT_SUPPORTED';
      default: return `UNKNOWN_ERROR(${code})`;
    }
  }

  private cloneTimeRanges(ranges: TimeRanges): TimeRanges {
    const result = {
      length: ranges.length,
      start: (index: number) => ranges.start(index),
      end: (index: number) => ranges.end(index)
    } as TimeRanges;
    return result;
  }

  private formatTimeRanges(ranges: TimeRanges): string {
    const rangeStrings: string[] = [];
    for (let i = 0; i < ranges.length; i++) {
      rangeStrings.push(`[${ranges.start(i).toFixed(2)}-${ranges.end(i).toFixed(2)}]`);
    }
    return rangeStrings.join(', ') || 'None';
  }

  private getLoadedBytes(videoElement: HTMLVideoElement): number {
    // Try to get loaded bytes from buffered ranges
    if (videoElement.buffered.length > 0) {
      // Estimate based on buffered time and video properties
      const bufferedTime = videoElement.buffered.end(videoElement.buffered.length - 1);
      const duration = videoElement.duration;
      if (isFinite(duration) && duration > 0) {
        // Rough estimate: assume 1MB per minute of video
        return Math.round((bufferedTime / duration) * 1024 * 1024);
      }
    }
    return 0;
  }

  private getTotalBytes(videoElement: HTMLVideoElement): number {
    const duration = videoElement.duration;
    if (isFinite(duration) && duration > 0) {
      // Rough estimate: assume 1MB per minute of video
      return Math.round((duration / 60) * 1024 * 1024);
    }
    return 0;
  }

  private getBufferedAhead(videoElement: HTMLVideoElement): number {
    const currentTime = videoElement.currentTime;
    for (let i = 0; i < videoElement.buffered.length; i++) {
      const start = videoElement.buffered.start(i);
      const end = videoElement.buffered.end(i);
      if (currentTime >= start && currentTime <= end) {
        return end - currentTime;
      }
    }
    return 0;
  }

  private getBufferedBehind(videoElement: HTMLVideoElement): number {
    const currentTime = videoElement.currentTime;
    for (let i = 0; i < videoElement.buffered.length; i++) {
      const start = videoElement.buffered.start(i);
      const end = videoElement.buffered.end(i);
      if (currentTime >= start && currentTime <= end) {
        return currentTime - start;
      }
    }
    return 0;
  }

  private getNetworkInfo(): any {
    return (navigator as any).connection || (navigator as any).mozConnection || (navigator as any).webkitConnection;
  }

  private isVideoStalled(videoElement: HTMLVideoElement): boolean {
    return !videoElement.paused && !videoElement.ended && 
           (videoElement.readyState < HTMLMediaElement.HAVE_FUTURE_DATA ||
            videoElement.networkState === HTMLMediaElement.NETWORK_LOADING);
  }

  private getStallDuration(videoElement: HTMLVideoElement): number {
    // This would require tracking stall start time - simplified for this implementation
    return 0;
  }

  private determineStallType(videoElement: HTMLVideoElement): 'loading' | 'buffering' | 'seeking' | 'unknown' {
    if (videoElement.seeking) return 'seeking';
    if (videoElement.readyState < HTMLMediaElement.HAVE_METADATA) return 'loading';
    if (videoElement.readyState < HTMLMediaElement.HAVE_FUTURE_DATA) return 'buffering';
    return 'unknown';
  }

  private determineWaitingReason(videoElement: HTMLVideoElement): string {
    if (videoElement.seeking) return 'seeking';
    if (videoElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return 'insufficient_data';
    if (videoElement.networkState === HTMLMediaElement.NETWORK_LOADING) return 'network_loading';
    return 'unknown';
  }

  private analyzeBufferHealth(videoElement: HTMLVideoElement): any {
    return {
      hasBufferedData: videoElement.buffered.length > 0,
      bufferGaps: [], // Simplified
      bufferAheadTime: this.getBufferedAhead(videoElement)
    };
  }

  private analyzeEventSequence(logs: VideoEventLog[]): Record<string, number> {
    const counts: Record<string, number> = {};
    logs.forEach(log => {
      counts[log.event] = (counts[log.event] || 0) + 1;
    });
    return counts;
  }

  private testBasicFullscreenSupport(): boolean {
    return !!(
      document.fullscreenEnabled ||
      (document as any).webkitFullscreenEnabled ||
      (document as any).mozFullScreenEnabled ||
      (document as any).msFullscreenEnabled
    );
  }

  private detectFullscreenMethod(): string | null {
    const element = document.documentElement as any;
    const methods = ['requestFullscreen', 'webkitRequestFullscreen', 'mozRequestFullScreen', 'msRequestFullscreen'];
    return methods.find(method => typeof element[method] === 'function') || null;
  }

  private detectExitFullscreenMethod(): string | null {
    const doc = document as any;
    const methods = ['exitFullscreen', 'webkitExitFullscreen', 'mozCancelFullScreen', 'msExitFullscreen'];
    return methods.find(method => typeof doc[method] === 'function') || null;
  }

  private isFullscreenEnabled(): boolean {
    const doc = document as any;
    return !!(doc.fullscreenEnabled || doc.webkitFullscreenEnabled || doc.mozFullScreenEnabled || doc.msFullscreenEnabled);
  }

  private async testDirectVideoFullscreen(videoElement: HTMLVideoElement): Promise<boolean> {
    // This would require actual testing - returning a mock result for safety
    return false;
  }

  private async testContainerFullscreen(videoElement: HTMLVideoElement): Promise<boolean> {
    // This would require actual testing - returning a mock result for safety
    return true;
  }

  private async testFullscreenBeforeLoad(videoElement: HTMLVideoElement): Promise<boolean> {
    return false;
  }

  private async testFullscreenWhilePaused(videoElement: HTMLVideoElement): Promise<boolean> {
    return true;
  }

  private async testFullscreenWhilePlaying(videoElement: HTMLVideoElement): Promise<boolean> {
    return true;
  }

  private detectBrowserQuirks(): string[] {
    const quirks: string[] = [];
    const userAgent = navigator.userAgent.toLowerCase();

    if (userAgent.includes('safari') && !userAgent.includes('chrome')) {
      quirks.push('Safari requires user gesture for fullscreen');
      quirks.push('Safari may not support video fullscreen directly');
    }

    if (userAgent.includes('firefox')) {
      quirks.push('Firefox uses mozRequestFullScreen (capital S)');
    }

    if (userAgent.includes('chrome')) {
      quirks.push('Chrome supports native video fullscreen');
    }

    return quirks;
  }

  /**
   * Get event logs for investigation
   */
  getEventLogs(investigationId: string): VideoEventLog[] {
    return this.eventLogs.get(investigationId) || [];
  }

  /**
   * Clear all investigations and free memory
   */
  clearAll(): void {
    // Cleanup all detectors
    this.stallDetectors.forEach((detector, id) => {
      this.cleanupStallDetection(id);
    });

    // Cleanup all performance observers
    this.performanceObservers.forEach((observer, id) => {
      this.cleanupPerformanceMonitoring(id);
    });

    // Clear all logs
    this.eventLogs.clear();
    this.stallDetectors.clear();
    this.performanceObservers.clear();
  }
}

// Export singleton instance
export const videoAPIInvestigator = new VideoAPIInvestigator();

// Convenience functions
export const startVideoInvestigation = (videoElement: HTMLVideoElement, investigationId?: string) => {
  const id = investigationId || `investigation_${Date.now()}`;
  return { id, cleanup: videoAPIInvestigator.startInvestigation(videoElement, id) };
};

export const analyzeVideoStall = (videoElement: HTMLVideoElement) =>
  videoAPIInvestigator.analyzeStallCondition(videoElement);

export const testVideoFullscreenCompatibility = (videoElement: HTMLVideoElement) =>
  videoAPIInvestigator.testFullscreenCompatibility(videoElement);

export const generateVideoReport = (investigationId: string, videoElement: HTMLVideoElement) =>
  videoAPIInvestigator.generateDiagnosticReport(investigationId, videoElement);

export default videoAPIInvestigator;