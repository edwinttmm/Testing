/**
 * Video Debug Tools
 * 
 * Comprehensive debugging utilities for video compatibility and format issues:
 * - Real-time compatibility testing
 * - Format detection and analysis
 * - Performance monitoring
 * - Error diagnosis and reporting
 */

import { videoCompatibilityChecker, VideoTestResult, BrowserInfo } from './videoCompatibilityChecker';
import { videoFormatValidator, VideoCompatibilityReport } from './videoFormatValidator';
import logger from './safeErrorLogger';

export interface VideoDebugSession {
  id: string;
  startTime: number;
  browser: BrowserInfo;
  tests: VideoTestResult[];
  errors: VideoDebugError[];
  performance: VideoPerformanceMetrics;
}

export interface VideoDebugError {
  timestamp: number;
  type: 'format' | 'network' | 'decode' | 'permission' | 'unknown';
  message: string;
  url?: string;
  details?: any;
}

export interface VideoPerformanceMetrics {
  totalTests: number;
  successfulTests: number;
  failedTests: number;
  averageLoadTime: number;
  slowestLoadTime: number;
  fastestLoadTime: number;
  formatPerformance: Record<string, {
    testCount: number;
    successRate: number;
    averageLoadTime: number;
  }>;
}

export interface VideoFormatAnalysis {
  detected: {
    extension: string;
    mimeType: string;
    estimatedCodec?: string;
  };
  validation: {
    isValid: boolean;
    confidence: string;
    browserSupport: string;
  };
  recommendations: string[];
  alternatives: string[];
}

class VideoDebugTools {
  private sessions = new Map<string, VideoDebugSession>();
  private currentSessionId: string | null = null;

  /**
   * Start a new debug session
   */
  startSession(sessionId?: string): string {
    const id = sessionId || `debug_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const session: VideoDebugSession = {
      id,
      startTime: Date.now(),
      browser: this.getBrowserInfo(),
      tests: [],
      errors: [],
      performance: {
        totalTests: 0,
        successfulTests: 0,
        failedTests: 0,
        averageLoadTime: 0,
        slowestLoadTime: 0,
        fastestLoadTime: Infinity,
        formatPerformance: {}
      }
    };

    this.sessions.set(id, session);
    this.currentSessionId = id;

    logger.debug('Debug session started', { sessionId: id }, { context: 'video-debug-tools' });
    return id;
  }

  /**
   * Get current browser information
   */
  private getBrowserInfo(): BrowserInfo {
    const capabilities = videoCompatibilityChecker.getBrowserCapabilities();
    return capabilities.browser;
  }

  /**
   * Test video URL and record results
   */
  async testVideo(url: string, format?: string, sessionId?: string): Promise<VideoTestResult> {
    const id = sessionId || this.currentSessionId || this.startSession();
    const session = this.sessions.get(id);
    
    if (!session) {
      throw new Error(`Debug session ${id} not found`);
    }

    logger.debug('Testing video', { url, format, sessionId: id }, { context: 'video-debug-tools' });

    try {
      const result = await videoCompatibilityChecker.testVideoPlayback(url, format);
      
      // Record result
      session.tests.push(result);
      this.updatePerformanceMetrics(session, result);

      if (!result.canLoad || !result.canPlay) {
        this.recordError(session, {
          timestamp: Date.now(),
          type: this.categorizeError(result.error),
          message: result.error || 'Unknown error',
          url,
          details: result
        });
      }

      logger.debug('Video test completed', { result }, { context: 'video-debug-tools' });
      return result;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      this.recordError(session, {
        timestamp: Date.now(),
        type: 'unknown',
        message: errorMessage,
        url,
        details: { error }
      });

      throw error;
    }
  }

  /**
   * Test multiple video formats
   */
  async testMultipleFormats(
    baseUrl: string, 
    formats: string[], 
    sessionId?: string
  ): Promise<VideoTestResult[]> {
    const id = sessionId || this.currentSessionId || this.startSession();
    
    logger.debug('Testing multiple formats', { 
      baseUrl, 
      formats, 
      sessionId: id 
    }, { context: 'video-debug-tools' });

    const results: VideoTestResult[] = [];
    
    for (const format of formats) {
      const url = this.generateUrlForFormat(baseUrl, format);
      try {
        const result = await this.testVideo(url, format, id);
        results.push(result);
      } catch (error) {
        logger.warn('Format test failed', error, { 
          context: 'video-debug-tools',
          format,
          url
        });
        
        // Create failed result
        results.push({
          format,
          url,
          canLoad: false,
          canPlay: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        });
      }
    }

    return results;
  }

  /**
   * Analyze video format
   */
  async analyzeVideoFormat(url: string, filename: string): Promise<VideoFormatAnalysis> {
    logger.debug('Analyzing video format', { url, filename }, { context: 'video-debug-tools' });

    const formatInfo = videoFormatValidator.getFormatFromFilename(filename);
    const validationResult = videoFormatValidator.validateVideoFormat(filename);
    const compatibilityReport = await videoFormatValidator.analyzeVideoCompatibility(url, filename);

    const analysis: VideoFormatAnalysis = {
      detected: {
        extension: formatInfo.extension,
        mimeType: formatInfo.mimeType,
        estimatedCodec: formatInfo.codec
      },
      validation: {
        isValid: validationResult.isSupported,
        confidence: validationResult.confidence,
        browserSupport: formatInfo.browserSupport
      },
      recommendations: [],
      alternatives: validationResult.supportedAlternatives.map(alt => alt.extension)
    };

    // Generate recommendations
    if (!validationResult.isSupported) {
      analysis.recommendations.push('Video format is not supported in current browser');
      
      if (validationResult.recommendation) {
        analysis.recommendations.push(validationResult.recommendation);
      }
    }

    if (formatInfo.browserSupport === 'limited') {
      analysis.recommendations.push('Format has limited browser support - consider alternatives');
    }

    if (validationResult.supportedAlternatives.length > 0) {
      const primary = validationResult.supportedAlternatives[0];
      analysis.recommendations.push(`Consider converting to ${primary.displayName} format`);
    }

    return analysis;
  }

  /**
   * Generate comprehensive compatibility matrix
   */
  generateCompatibilityMatrix(): string {
    const matrix = videoCompatibilityChecker.getCompatibilityMatrix();
    const browsers = ['chrome', 'firefox', 'safari', 'edge'];
    
    let output = '# Video Format Compatibility Matrix\n\n';
    output += '| Format | Chrome | Firefox | Safari | Edge | Codecs | Recommendation |\n';
    output += '|--------|--------|---------|--------|------|--------|----------------|\n';

    matrix.forEach(entry => {
      const browserSupport = browsers.map(browser => {
        const support = entry.browsers[browser as keyof typeof entry.browsers];
        const icon = support === 'supported' ? '✅' : 
                    support === 'partial' ? '⚠️' : '❌';
        return `${icon} ${support}`;
      });

      const codecs = entry.codecs.join(', ');
      const recommendation = entry.recommendation === 'primary' ? '🟢 Primary' :
                           entry.recommendation === 'fallback' ? '🟡 Fallback' : '🔴 Avoid';

      output += `| ${entry.format.toUpperCase()} | ${browserSupport.join(' | ')} | ${codecs} | ${recommendation} |\n`;
    });

    output += '\n## Legend\n';
    output += '- ✅ Fully Supported\n';
    output += '- ⚠️ Partial Support\n';
    output += '- ❌ Not Supported\n';
    output += '- 🟢 Primary Choice\n';
    output += '- 🟡 Fallback Option\n';
    output += '- 🔴 Avoid Using\n';

    if (this.currentSessionId) {
      const session = this.sessions.get(this.currentSessionId);
      if (session && session.tests.length > 0) {
        output += '\n## Current Session Results\n';
        output += this.generateSessionReport(this.currentSessionId);
      }
    }

    return output;
  }

  /**
   * Generate session report
   */
  generateSessionReport(sessionId: string): string {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return 'Session not found';
    }

    let report = `## Debug Session Report: ${sessionId}\n\n`;
    report += `**Started:** ${new Date(session.startTime).toISOString()}\n`;
    report += `**Browser:** ${session.browser.name} ${session.browser.version} on ${session.browser.platform}\n`;
    report += `**Duration:** ${Math.round((Date.now() - session.startTime) / 1000)}s\n\n`;

    // Performance summary
    report += `### Performance Summary\n`;
    report += `- **Total Tests:** ${session.performance.totalTests}\n`;
    report += `- **Success Rate:** ${session.performance.totalTests > 0 ? 
      Math.round((session.performance.successfulTests / session.performance.totalTests) * 100) : 0}%\n`;
    report += `- **Average Load Time:** ${Math.round(session.performance.averageLoadTime)}ms\n`;
    
    if (session.performance.slowestLoadTime > 0) {
      report += `- **Slowest Load:** ${Math.round(session.performance.slowestLoadTime)}ms\n`;
    }
    
    if (session.performance.fastestLoadTime < Infinity) {
      report += `- **Fastest Load:** ${Math.round(session.performance.fastestLoadTime)}ms\n`;
    }

    // Format performance
    if (Object.keys(session.performance.formatPerformance).length > 0) {
      report += `\n### Format Performance\n`;
      Object.entries(session.performance.formatPerformance).forEach(([format, metrics]) => {
        report += `- **${format.toUpperCase()}:** ${Math.round(metrics.successRate * 100)}% success (${metrics.testCount} tests, ${Math.round(metrics.averageLoadTime)}ms avg)\n`;
      });
    }

    // Errors
    if (session.errors.length > 0) {
      report += `\n### Errors (${session.errors.length})\n`;
      session.errors.forEach((error, index) => {
        const time = new Date(error.timestamp).toLocaleTimeString();
        report += `${index + 1}. **${time}** [${error.type}] ${error.message}\n`;
        if (error.url) {
          report += `   - URL: ${error.url}\n`;
        }
      });
    }

    // Test results
    if (session.tests.length > 0) {
      report += `\n### Test Results\n`;
      session.tests.forEach((test, index) => {
        const status = test.canLoad && test.canPlay ? '✅ Pass' : '❌ Fail';
        const loadTime = test.loadTime ? ` (${Math.round(test.loadTime)}ms)` : '';
        report += `${index + 1}. ${status} ${test.format.toUpperCase()}${loadTime}\n`;
        if (test.error) {
          report += `   - Error: ${test.error}\n`;
        }
        if (test.metadata?.dimensions) {
          report += `   - Resolution: ${test.metadata.dimensions.width}x${test.metadata.dimensions.height}\n`;
        }
      });
    }

    return report;
  }

  /**
   * Real-time video monitoring
   */
  startRealtimeMonitoring(videoElement: HTMLVideoElement, sessionId?: string): () => void {
    const id = sessionId || this.currentSessionId || this.startSession();
    const session = this.sessions.get(id);
    
    if (!session) {
      throw new Error(`Debug session ${id} not found`);
    }

    const events = [
      'loadstart', 'loadedmetadata', 'loadeddata', 'canplay', 'canplaythrough',
      'playing', 'waiting', 'seeking', 'seeked', 'ended', 'error', 'stalled'
    ];

    const eventHandlers = new Map<string, EventListener>();

    events.forEach(eventName => {
      const handler = (event: Event) => {
        const timestamp = Date.now();
        const eventData = {
          timestamp,
          event: eventName,
          currentTime: videoElement.currentTime,
          duration: videoElement.duration,
          readyState: videoElement.readyState,
          networkState: videoElement.networkState,
          buffered: this.getBufferedRanges(videoElement),
          error: videoElement.error ? {
            code: videoElement.error.code,
            message: videoElement.error.message
          } : null
        };

        logger.debug('Video event', eventData, { 
          context: 'video-debug-tools',
          sessionId: id,
          event: eventName
        });

        // Record errors
        if (eventName === 'error' && videoElement.error) {
          this.recordError(session, {
            timestamp,
            type: this.categorizeVideoError(videoElement.error),
            message: videoElement.error.message || 'Video error occurred',
            details: eventData
          });
        }
      };

      eventHandlers.set(eventName, handler);
      videoElement.addEventListener(eventName, handler);
    });

    // Return cleanup function
    return () => {
      eventHandlers.forEach((handler, eventName) => {
        videoElement.removeEventListener(eventName, handler);
      });
      eventHandlers.clear();
    };
  }

  /**
   * Get buffered ranges
   */
  private getBufferedRanges(video: HTMLVideoElement): Array<{start: number; end: number}> {
    const ranges: Array<{start: number; end: number}> = [];
    
    for (let i = 0; i < video.buffered.length; i++) {
      ranges.push({
        start: video.buffered.start(i),
        end: video.buffered.end(i)
      });
    }

    return ranges;
  }

  /**
   * Export session data
   */
  exportSessionData(sessionId: string): string {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error(`Session ${sessionId} not found`);
    }

    return JSON.stringify({
      session,
      exportTime: new Date().toISOString(),
      browserInfo: videoCompatibilityChecker.getBrowserCapabilities()
    }, null, 2);
  }

  /**
   * Clear session data
   */
  clearSession(sessionId: string): void {
    this.sessions.delete(sessionId);
    if (this.currentSessionId === sessionId) {
      this.currentSessionId = null;
    }
  }

  /**
   * Get all sessions
   */
  getSessions(): VideoDebugSession[] {
    return Array.from(this.sessions.values());
  }

  /**
   * Update performance metrics
   */
  private updatePerformanceMetrics(session: VideoDebugSession, result: VideoTestResult): void {
    const perf = session.performance;
    
    perf.totalTests++;
    
    if (result.canLoad && result.canPlay) {
      perf.successfulTests++;
    } else {
      perf.failedTests++;
    }

    if (result.loadTime) {
      const totalLoadTime = perf.averageLoadTime * (perf.totalTests - 1) + result.loadTime;
      perf.averageLoadTime = totalLoadTime / perf.totalTests;
      
      perf.slowestLoadTime = Math.max(perf.slowestLoadTime, result.loadTime);
      perf.fastestLoadTime = Math.min(perf.fastestLoadTime, result.loadTime);
    }

    // Format-specific performance
    const format = result.format;
    if (!perf.formatPerformance[format]) {
      perf.formatPerformance[format] = {
        testCount: 0,
        successRate: 0,
        averageLoadTime: 0
      };
    }

    const formatPerf = perf.formatPerformance[format];
    formatPerf.testCount++;
    
    const previousSuccesses = Math.round(formatPerf.successRate * (formatPerf.testCount - 1));
    const newSuccesses = previousSuccesses + (result.canLoad && result.canPlay ? 1 : 0);
    formatPerf.successRate = newSuccesses / formatPerf.testCount;

    if (result.loadTime) {
      const totalFormatLoadTime = formatPerf.averageLoadTime * (formatPerf.testCount - 1) + result.loadTime;
      formatPerf.averageLoadTime = totalFormatLoadTime / formatPerf.testCount;
    }
  }

  /**
   * Record error in session
   */
  private recordError(session: VideoDebugSession, error: VideoDebugError): void {
    session.errors.push(error);
    
    // Keep only last 100 errors
    if (session.errors.length > 100) {
      session.errors.shift();
    }
  }

  /**
   * Categorize error type
   */
  private categorizeError(errorMessage?: string): VideoDebugError['type'] {
    if (!errorMessage) return 'unknown';
    
    const message = errorMessage.toLowerCase();
    
    if (message.includes('format') || message.includes('codec') || message.includes('supported')) {
      return 'format';
    }
    if (message.includes('network') || message.includes('load') || message.includes('fetch')) {
      return 'network';
    }
    if (message.includes('decode') || message.includes('corrupt')) {
      return 'decode';
    }
    if (message.includes('permission') || message.includes('blocked') || message.includes('cors')) {
      return 'permission';
    }

    return 'unknown';
  }

  /**
   * Categorize video error
   */
  private categorizeVideoError(error: MediaError): VideoDebugError['type'] {
    switch (error.code) {
      case MediaError.MEDIA_ERR_NETWORK:
        return 'network';
      case MediaError.MEDIA_ERR_DECODE:
        return 'decode';
      case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
        return 'format';
      default:
        return 'unknown';
    }
  }

  /**
   * Generate URL for format
   */
  private generateUrlForFormat(baseUrl: string, format: string): string {
    const basePath = baseUrl.substring(0, baseUrl.lastIndexOf('.'));
    return `${basePath}.${format}`;
  }
}

// Export singleton instance
export const videoDebugTools = new VideoDebugTools();

// Export convenience functions
export const startDebugSession = (sessionId?: string) =>
  videoDebugTools.startSession(sessionId);

export const testVideo = (url: string, format?: string, sessionId?: string) =>
  videoDebugTools.testVideo(url, format, sessionId);

export const analyzeVideoFormat = (url: string, filename: string) =>
  videoDebugTools.analyzeVideoFormat(url, filename);

export const generateCompatibilityMatrix = () =>
  videoDebugTools.generateCompatibilityMatrix();

export const generateSessionReport = (sessionId: string) =>
  videoDebugTools.generateSessionReport(sessionId);

export default videoDebugTools;