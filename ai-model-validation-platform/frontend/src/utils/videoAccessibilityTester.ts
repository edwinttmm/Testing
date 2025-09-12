/**
 * Video Accessibility Tester
 * 
 * Comprehensive video file accessibility and permission testing:
 * - File existence verification
 * - CORS and security policy checking
 * - Network connectivity testing
 * - Permission validation
 * - Performance monitoring
 */

import logger from './safeErrorLogger';

export interface VideoAccessibilityResult {
  isAccessible: boolean;
  status: 'accessible' | 'not_found' | 'forbidden' | 'cors_blocked' | 'network_error' | 'timeout';
  httpStatus?: number;
  responseTime?: number;
  contentType?: string;
  contentLength?: number;
  headers?: Record<string, string>;
  error?: string;
  recommendations?: string[];
}

export interface VideoAccessibilityTestSuite {
  url: string;
  results: {
    head: VideoAccessibilityResult;
    options: VideoAccessibilityResult;
    partial: VideoAccessibilityResult;
  };
  summary: {
    overallAccessible: boolean;
    bestMethod: 'head' | 'options' | 'partial' | 'none';
    issues: string[];
    recommendations: string[];
  };
}

export interface VideoPermissionTest {
  url: string;
  hasReadPermission: boolean;
  hasRangeRequestSupport: boolean;
  supportsHeadRequests: boolean;
  corsEnabled: boolean;
  cachePolicy?: string;
  securityHeaders?: Record<string, string>;
}

class VideoAccessibilityTester {
  private cache = new Map<string, VideoAccessibilityResult>();
  private readonly DEFAULT_TIMEOUT = 10000;
  private readonly CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

  /**
   * Test video accessibility using HEAD request
   */
  async testHeadRequest(url: string, timeout = this.DEFAULT_TIMEOUT): Promise<VideoAccessibilityResult> {
    const startTime = Date.now();
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      const response = await fetch(url, {
        method: 'HEAD',
        signal: controller.signal,
        cache: 'no-cache',
        mode: 'cors'
      });
      
      clearTimeout(timeoutId);
      const responseTime = Date.now() - startTime;
      
      const result: VideoAccessibilityResult = {
        isAccessible: response.ok,
        status: this.getStatusFromResponse(response),
        httpStatus: response.status,
        responseTime,
        contentType: response.headers.get('content-type') || undefined,
        contentLength: this.getContentLength(response),
        headers: this.extractHeaders(response)
      };

      if (!response.ok) {
        result.error = `HTTP ${response.status}: ${response.statusText}`;
        result.recommendations = this.generateRecommendations(response.status, 'head');
      }

      return result;
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      return this.handleRequestError(error, responseTime, 'head');
    }
  }

  /**
   * Test video accessibility using OPTIONS request
   */
  async testOptionsRequest(url: string, timeout = this.DEFAULT_TIMEOUT): Promise<VideoAccessibilityResult> {
    const startTime = Date.now();
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      const response = await fetch(url, {
        method: 'OPTIONS',
        signal: controller.signal,
        cache: 'no-cache',
        mode: 'cors'
      });
      
      clearTimeout(timeoutId);
      const responseTime = Date.now() - startTime;
      
      const result: VideoAccessibilityResult = {
        isAccessible: response.ok,
        status: this.getStatusFromResponse(response),
        httpStatus: response.status,
        responseTime,
        headers: this.extractHeaders(response)
      };

      if (!response.ok) {
        result.error = `HTTP ${response.status}: ${response.statusText}`;
        result.recommendations = this.generateRecommendations(response.status, 'options');
      }

      return result;
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      return this.handleRequestError(error, responseTime, 'options');
    }
  }

  /**
   * Test video accessibility using partial content request
   */
  async testPartialRequest(url: string, timeout = this.DEFAULT_TIMEOUT): Promise<VideoAccessibilityResult> {
    const startTime = Date.now();
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      const response = await fetch(url, {
        method: 'GET',
        signal: controller.signal,
        cache: 'no-cache',
        mode: 'cors',
        headers: {
          'Range': 'bytes=0-1023' // Request first 1KB
        }
      });
      
      clearTimeout(timeoutId);
      const responseTime = Date.now() - startTime;
      
      const result: VideoAccessibilityResult = {
        isAccessible: response.ok || response.status === 206,
        status: this.getStatusFromResponse(response),
        httpStatus: response.status,
        responseTime,
        contentType: response.headers.get('content-type') || undefined,
        contentLength: this.getContentLength(response),
        headers: this.extractHeaders(response)
      };

      if (!response.ok && response.status !== 206) {
        result.error = `HTTP ${response.status}: ${response.statusText}`;
        result.recommendations = this.generateRecommendations(response.status, 'partial');
      }

      // Consume response body to avoid memory leaks
      if (response.body) {
        const reader = response.body.getReader();
        try {
          await reader.read();
        } finally {
          reader.releaseLock();
        }
      }

      return result;
      
    } catch (error) {
      const responseTime = Date.now() - startTime;
      return this.handleRequestError(error, responseTime, 'partial');
    }
  }

  /**
   * Comprehensive accessibility test suite
   */
  async testVideoAccessibility(url: string): Promise<VideoAccessibilityTestSuite> {
    logger.debug('Starting video accessibility test', { url }, { context: 'video-accessibility-tester' });

    // Check cache first
    const cacheKey = `suite_${url}`;
    if (this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey)!;
      if (Date.now() - (cached as any).timestamp < this.CACHE_DURATION) {
        return (cached as any).data;
      }
    }

    const [headResult, optionsResult, partialResult] = await Promise.all([
      this.testHeadRequest(url),
      this.testOptionsRequest(url),
      this.testPartialRequest(url)
    ]);

    const suite: VideoAccessibilityTestSuite = {
      url,
      results: {
        head: headResult,
        options: optionsResult,
        partial: partialResult
      },
      summary: this.generateSummary(headResult, optionsResult, partialResult)
    };

    // Cache the result
    this.cache.set(cacheKey, {
      ...suite,
      timestamp: Date.now()
    } as any);

    logger.debug('Video accessibility test completed', { 
      url, 
      accessible: suite.summary.overallAccessible 
    }, { context: 'video-accessibility-tester' });

    return suite;
  }

  /**
   * Test video permissions comprehensively
   */
  async testVideoPermissions(url: string): Promise<VideoPermissionTest> {
    const suite = await this.testVideoAccessibility(url);
    
    const result: VideoPermissionTest = {
      url,
      hasReadPermission: suite.summary.overallAccessible,
      hasRangeRequestSupport: this.checkRangeRequestSupport(suite.results),
      supportsHeadRequests: suite.results.head.isAccessible,
      corsEnabled: this.checkCORSSupport(suite.results),
      cachePolicy: this.extractCachePolicy(suite.results),
      securityHeaders: this.extractSecurityHeaders(suite.results)
    };

    return result;
  }

  /**
   * Batch test multiple video URLs
   */
  async testMultipleVideos(urls: string[]): Promise<VideoAccessibilityTestSuite[]> {
    const tests = urls.map(url => this.testVideoAccessibility(url));
    return Promise.all(tests);
  }

  /**
   * Test video with different quality levels
   */
  async testVideoQualities(baseUrl: string, qualities: string[] = ['low', 'medium', 'high']): Promise<Record<string, VideoAccessibilityTestSuite>> {
    const results: Record<string, VideoAccessibilityTestSuite> = {};
    
    for (const quality of qualities) {
      const url = this.generateQualityUrl(baseUrl, quality);
      results[quality] = await this.testVideoAccessibility(url);
    }

    return results;
  }

  /**
   * Generate URL for specific quality
   */
  private generateQualityUrl(baseUrl: string, quality: string): string {
    const lastDotIndex = baseUrl.lastIndexOf('.');
    if (lastDotIndex === -1) {
      return `${baseUrl}_${quality}`;
    }
    
    const basePath = baseUrl.substring(0, lastDotIndex);
    const extension = baseUrl.substring(lastDotIndex);
    return `${basePath}_${quality}${extension}`;
  }

  /**
   * Get status from HTTP response
   */
  private getStatusFromResponse(response: Response): VideoAccessibilityResult['status'] {
    if (response.ok || response.status === 206) {
      return 'accessible';
    }
    
    switch (response.status) {
      case 404:
        return 'not_found';
      case 403:
      case 401:
        return 'forbidden';
      default:
        return 'network_error';
    }
  }

  /**
   * Handle request errors
   */
  private handleRequestError(
    error: unknown, 
    responseTime: number, 
    method: string
  ): VideoAccessibilityResult {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    
    let status: VideoAccessibilityResult['status'] = 'network_error';
    let recommendations: string[] = [];

    if (errorMessage.includes('abort') || errorMessage.includes('timeout')) {
      status = 'timeout';
      recommendations.push('Video server may be slow or overloaded');
      recommendations.push('Try reducing timeout or using a different server');
    } else if (errorMessage.includes('CORS') || errorMessage.includes('cors')) {
      status = 'cors_blocked';
      recommendations.push('Server needs to allow CORS for video access');
      recommendations.push('Add Access-Control-Allow-Origin header on server');
    } else if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
      status = 'network_error';
      recommendations.push('Check network connectivity');
      recommendations.push('Verify video URL is correct');
    }

    return {
      isAccessible: false,
      status,
      responseTime,
      error: errorMessage,
      recommendations
    };
  }

  /**
   * Extract relevant headers
   */
  private extractHeaders(response: Response): Record<string, string> {
    const headers: Record<string, string> = {};
    
    const relevantHeaders = [
      'content-type',
      'content-length', 
      'accept-ranges',
      'access-control-allow-origin',
      'access-control-allow-methods',
      'cache-control',
      'expires',
      'etag',
      'last-modified',
      'content-encoding',
      'content-security-policy',
      'x-frame-options',
      'x-content-type-options'
    ];

    relevantHeaders.forEach(headerName => {
      const value = response.headers.get(headerName);
      if (value) {
        headers[headerName] = value;
      }
    });

    return headers;
  }

  /**
   * Get content length from response
   */
  private getContentLength(response: Response): number | undefined {
    const contentLength = response.headers.get('content-length');
    return contentLength ? parseInt(contentLength, 10) : undefined;
  }

  /**
   * Generate recommendations based on HTTP status
   */
  private generateRecommendations(status: number, method: string): string[] {
    const recommendations: string[] = [];

    switch (status) {
      case 404:
        recommendations.push('Video file not found - check URL and file path');
        recommendations.push('Verify file exists on server');
        break;
      
      case 403:
        recommendations.push('Access forbidden - check file permissions');
        recommendations.push('Verify server allows video file access');
        break;
      
      case 401:
        recommendations.push('Authentication required');
        recommendations.push('Provide proper authentication credentials');
        break;
      
      case 405:
        recommendations.push(`${method.toUpperCase()} method not allowed`);
        recommendations.push('Server may not support this request method');
        break;
      
      case 500:
        recommendations.push('Server internal error');
        recommendations.push('Contact server administrator');
        break;
      
      case 503:
        recommendations.push('Service unavailable - server may be overloaded');
        recommendations.push('Try again later or use different server');
        break;
    }

    return recommendations;
  }

  /**
   * Generate test suite summary
   */
  private generateSummary(
    headResult: VideoAccessibilityResult,
    optionsResult: VideoAccessibilityResult,
    partialResult: VideoAccessibilityResult
  ): VideoAccessibilityTestSuite['summary'] {
    const results = [headResult, optionsResult, partialResult];
    const methods = ['head', 'options', 'partial'] as const;
    
    const accessibleResults = results.filter(r => r.isAccessible);
    const overallAccessible = accessibleResults.length > 0;
    
    let bestMethod: 'head' | 'options' | 'partial' | 'none' = 'none';
    if (overallAccessible) {
      // Prefer HEAD request, then partial, then OPTIONS
      if (headResult.isAccessible) bestMethod = 'head';
      else if (partialResult.isAccessible) bestMethod = 'partial';
      else if (optionsResult.isAccessible) bestMethod = 'options';
    }

    const issues: string[] = [];
    const recommendations: string[] = [];

    results.forEach((result, index) => {
      if (!result.isAccessible && result.error) {
        issues.push(`${methods[index].toUpperCase()}: ${result.error}`);
      }
      if (result.recommendations) {
        recommendations.push(...result.recommendations);
      }
    });

    // Remove duplicate recommendations
    const uniqueRecommendations = [...new Set(recommendations)];

    return {
      overallAccessible,
      bestMethod,
      issues,
      recommendations: uniqueRecommendations
    };
  }

  /**
   * Check range request support
   */
  private checkRangeRequestSupport(results: VideoAccessibilityTestSuite['results']): boolean {
    const partialResult = results.partial;
    return partialResult.httpStatus === 206 || 
           (partialResult.headers?.['accept-ranges'] === 'bytes');
  }

  /**
   * Check CORS support
   */
  private checkCORSSupport(results: VideoAccessibilityTestSuite['results']): boolean {
    return Object.values(results).some(result => 
      result.headers?.['access-control-allow-origin'] !== undefined
    );
  }

  /**
   * Extract cache policy
   */
  private extractCachePolicy(results: VideoAccessibilityTestSuite['results']): string | undefined {
    for (const result of Object.values(results)) {
      const cacheControl = result.headers?.['cache-control'];
      if (cacheControl) return cacheControl;
      
      const expires = result.headers?.['expires'];
      if (expires) return `Expires: ${expires}`;
    }
    return undefined;
  }

  /**
   * Extract security headers
   */
  private extractSecurityHeaders(results: VideoAccessibilityTestSuite['results']): Record<string, string> {
    const securityHeaders: Record<string, string> = {};
    
    const securityHeaderNames = [
      'content-security-policy',
      'x-frame-options',
      'x-content-type-options',
      'strict-transport-security',
      'referrer-policy'
    ];

    Object.values(results).forEach(result => {
      securityHeaderNames.forEach(headerName => {
        const value = result.headers?.[headerName];
        if (value && !securityHeaders[headerName]) {
          securityHeaders[headerName] = value;
        }
      });
    });

    return securityHeaders;
  }

  /**
   * Clear accessibility test cache
   */
  clearCache(): void {
    this.cache.clear();
    logger.debug('Video accessibility test cache cleared', undefined, { context: 'video-accessibility-tester' });
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys())
    };
  }

  /**
   * Generate accessibility report
   */
  generateAccessibilityReport(suite: VideoAccessibilityTestSuite): string {
    let report = `# Video Accessibility Report\n\n`;
    report += `**URL:** ${suite.url}\n`;
    report += `**Overall Accessible:** ${suite.summary.overallAccessible ? '✅ Yes' : '❌ No'}\n`;
    report += `**Best Method:** ${suite.summary.bestMethod.toUpperCase()}\n\n`;

    // Test Results
    report += `## Test Results\n\n`;
    
    Object.entries(suite.results).forEach(([method, result]) => {
      const status = result.isAccessible ? '✅ Accessible' : '❌ Failed';
      report += `### ${method.toUpperCase()} Request\n`;
      report += `- **Status:** ${status}\n`;
      report += `- **HTTP Status:** ${result.httpStatus || 'N/A'}\n`;
      report += `- **Response Time:** ${result.responseTime ? `${result.responseTime}ms` : 'N/A'}\n`;
      
      if (result.contentType) {
        report += `- **Content Type:** ${result.contentType}\n`;
      }
      
      if (result.contentLength) {
        report += `- **Content Length:** ${this.formatBytes(result.contentLength)}\n`;
      }
      
      if (result.error) {
        report += `- **Error:** ${result.error}\n`;
      }
      
      report += `\n`;
    });

    // Issues
    if (suite.summary.issues.length > 0) {
      report += `## Issues Found\n\n`;
      suite.summary.issues.forEach(issue => {
        report += `- ${issue}\n`;
      });
      report += `\n`;
    }

    // Recommendations
    if (suite.summary.recommendations.length > 0) {
      report += `## Recommendations\n\n`;
      suite.summary.recommendations.forEach(rec => {
        report += `- ${rec}\n`;
      });
      report += `\n`;
    }

    return report;
  }

  /**
   * Format bytes for display
   */
  private formatBytes(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

// Export singleton instance
export const videoAccessibilityTester = new VideoAccessibilityTester();

// Export convenience functions
export const testVideoAccessibility = (url: string) =>
  videoAccessibilityTester.testVideoAccessibility(url);

export const testVideoPermissions = (url: string) =>
  videoAccessibilityTester.testVideoPermissions(url);

export const testMultipleVideos = (urls: string[]) =>
  videoAccessibilityTester.testMultipleVideos(urls);

export const generateAccessibilityReport = (suite: VideoAccessibilityTestSuite) =>
  videoAccessibilityTester.generateAccessibilityReport(suite);

export default videoAccessibilityTester;