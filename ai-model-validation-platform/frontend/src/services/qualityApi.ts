/**
 * Quality API Service Layer
 *
 * Fully typed API service with:
 * - Request caching
 * - Error handling with retry logic
 * - Loading states
 * - AbortController support
 */

import axios, { AxiosInstance, CancelTokenSource } from 'axios';
import {
  QualityInfo,
  QualityWarning,
  TimingHealthStatus,
  VideoQualityMetrics,
  GlobalQualityMetrics,
  QualityApiParams,
  QualityApiResponse,
  QualityLevel,
  QualityWarningSeverity,
  QualityWarningCategory
} from '../types/quality';
import { getConfigValueSync } from '../utils/configurationManager';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
}

export class QualityApiService {
  private api: AxiosInstance;
  private cache: Map<string, CacheEntry<any>> = new Map();
  private pendingRequests: Map<string, Promise<any>> = new Map();
  private readonly CACHE_TTL_MS = 30000; // 30 seconds
  private readonly MAX_RETRIES = 3;
  private readonly RETRY_DELAY_MS = 1000;

  constructor() {
    const backendUrl = getConfigValueSync('backendUrl') || 'http://localhost:5000';

    this.api = axios.create({
      baseURL: backendUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    // Response interceptor for error handling
    this.api.interceptors.response.use(
      response => response,
      error => {
        console.error('Quality API Error:', error.message);
        return Promise.reject(error);
      }
    );
  }

  /**
   * Get quality warnings for a session
   */
  async getQualityWarnings(sessionId: string): Promise<QualityWarning[]> {
    const cacheKey = `warnings_${sessionId}`;
    const cached = this.getCached<QualityWarning[]>(cacheKey);

    if (cached) {
      return cached;
    }

    try {
      const response = await this.retryRequest(() =>
        this.api.get('/api/monitoring/quality-warnings', {
          params: { session_id: sessionId }
        })
      );

      const warnings = response.data.warnings || [];
      this.setCache(cacheKey, warnings);

      return warnings;
    } catch (error) {
      console.error('Failed to fetch quality warnings:', error);
      return []; // Return empty array instead of throwing
    }
  }

  /**
   * Get timing health status for a session
   */
  async getTimingHealth(sessionId: string): Promise<TimingHealthStatus | null> {
    const cacheKey = `timing_health_${sessionId}`;
    const cached = this.getCached<TimingHealthStatus>(cacheKey);

    if (cached) {
      return cached;
    }

    try {
      const response = await this.retryRequest(() =>
        this.api.get('/api/monitoring/timing-health', {
          params: { session_id: sessionId }
        })
      );

      const health: TimingHealthStatus = {
        session_id: sessionId,
        timing_degraded: response.data.timing_degraded || false,
        timing_verified: response.data.timing_verified || false,
        total_detections: response.data.total_detections || 0,
        degraded_count: response.data.degraded_count || 0,
        verified_count: response.data.verified_count || 0,
        quality_level: response.data.quality_level || QualityLevel.UNKNOWN,
        degradation_percentage: response.data.degradation_percentage || 0,
        validation_rate: response.data.validation_rate || 0,
        usable_detections_count: response.data.usable_detections_count || 0,
        timestamp: response.data.timestamp || new Date().toISOString()
      };

      this.setCache(cacheKey, health);
      return health;
    } catch (error) {
      console.error('Failed to fetch timing health:', error);
      return null;
    }
  }

  /**
   * Get video quality metrics
   */
  async getVideoQualityMetrics(videoId: string): Promise<VideoQualityMetrics | null> {
    const cacheKey = `video_quality_${videoId}`;
    const cached = this.getCached<VideoQualityMetrics>(cacheKey);

    if (cached) {
      return cached;
    }

    try {
      const response = await this.retryRequest(() =>
        this.api.get(`/api/video-sequences/${videoId}/quality-summary`)
      );

      const metrics: VideoQualityMetrics = {
        video_id: videoId,
        video_name: response.data.video_name,
        total_detections: response.data.total_detections || 0,
        usable_count: response.data.usable_count || 0,
        degraded_count: response.data.degraded_count || 0,
        validation_rate: response.data.validation_rate || 0,
        quality_level: response.data.quality_level || QualityLevel.UNKNOWN,
        timing_stats: response.data.timing_stats || {
          mean_latency_ms: 0,
          median_latency_ms: 0,
          max_latency_ms: 0,
          min_latency_ms: 0,
          std_deviation_ms: 0
        },
        accuracy_stats: response.data.accuracy_stats
      };

      this.setCache(cacheKey, metrics);
      return metrics;
    } catch (error) {
      console.error('Failed to fetch video quality metrics:', error);
      return null;
    }
  }

  /**
   * Get complete quality information for a session
   */
  async getSessionQuality(sessionId: string): Promise<QualityInfo | null> {
    const cacheKey = `session_quality_${sessionId}`;
    const cached = this.getCached<QualityInfo>(cacheKey);

    if (cached) {
      return cached;
    }

    try {
      // Fetch all quality data in parallel
      const [warnings, timingHealth] = await Promise.all([
        this.getQualityWarnings(sessionId),
        this.getTimingHealth(sessionId)
      ]);

      if (!timingHealth) {
        return null;
      }

      const qualityInfo: QualityInfo = {
        session_id: sessionId,
        quality_level: timingHealth.quality_level,
        validation_rate: timingHealth.validation_rate,
        timing_health: timingHealth,
        warnings: warnings,
        summary: {
          total_detections: timingHealth.total_detections,
          usable_detections: timingHealth.usable_detections_count,
          degraded_detections: timingHealth.degraded_count,
          critical_issues: warnings.filter(w =>
            w.severity === QualityWarningSeverity.CRITICAL ||
            w.severity === QualityWarningSeverity.HIGH
          ).length,
          has_warnings: warnings.length > 0
        }
      };

      this.setCache(cacheKey, qualityInfo);
      return qualityInfo;
    } catch (error) {
      console.error('Failed to fetch session quality:', error);
      return null;
    }
  }

  /**
   * Get global quality metrics across all sessions
   */
  async getGlobalQualityMetrics(params?: QualityApiParams): Promise<GlobalQualityMetrics | null> {
    const cacheKey = `global_quality_${JSON.stringify(params || {})}`;
    const cached = this.getCached<GlobalQualityMetrics>(cacheKey);

    if (cached) {
      return cached;
    }

    try {
      const response = await this.retryRequest(() =>
        this.api.get('/api/monitoring/global-quality', { params })
      );

      const metrics: GlobalQualityMetrics = {
        total_sessions: response.data.total_sessions || 0,
        total_detections: response.data.total_detections || 0,
        overall_validation_rate: response.data.overall_validation_rate || 0,
        overall_quality_level: response.data.overall_quality_level || QualityLevel.UNKNOWN,
        sessions_with_issues: response.data.sessions_with_issues || 0,
        sessions_excellent: response.data.sessions_excellent || 0,
        sessions_good: response.data.sessions_good || 0,
        sessions_fair: response.data.sessions_fair || 0,
        sessions_poor: response.data.sessions_poor || 0,
        recent_warnings: response.data.recent_warnings || [],
        trend_data: response.data.trend_data || [],
        last_updated: response.data.last_updated || new Date().toISOString()
      };

      this.setCache(cacheKey, metrics, 60000); // Cache for 1 minute
      return metrics;
    } catch (error) {
      console.error('Failed to fetch global quality metrics:', error);
      return null;
    }
  }

  /**
   * Acknowledge/dismiss a quality warning
   */
  async acknowledgeWarning(warningId: string): Promise<boolean> {
    try {
      await this.api.post(`/api/monitoring/quality-warnings/${warningId}/acknowledge`);
      this.clearCachePattern('warnings_');
      return true;
    } catch (error) {
      console.error('Failed to acknowledge warning:', error);
      return false;
    }
  }

  /**
   * Clear cache for specific session
   */
  clearSessionCache(sessionId: string): void {
    this.clearCachePattern(`warnings_${sessionId}`);
    this.clearCachePattern(`timing_health_${sessionId}`);
    this.clearCachePattern(`session_quality_${sessionId}`);
  }

  /**
   * Clear all cache
   */
  clearAllCache(): void {
    this.cache.clear();
  }

  // Private helper methods

  private getCached<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) {
      return null;
    }

    const now = Date.now();
    if (now > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    return entry.data as T;
  }

  private setCache<T>(key: string, data: T, ttl: number = this.CACHE_TTL_MS): void {
    const now = Date.now();
    this.cache.set(key, {
      data,
      timestamp: now,
      expiresAt: now + ttl
    });
  }

  private clearCachePattern(pattern: string): void {
    const keysToDelete: string[] = [];
    this.cache.forEach((_, key) => {
      if (key.includes(pattern)) {
        keysToDelete.push(key);
      }
    });
    keysToDelete.forEach(key => this.cache.delete(key));
  }

  private async retryRequest<T>(
    requestFn: () => Promise<T>,
    retries: number = this.MAX_RETRIES
  ): Promise<T> {
    try {
      return await requestFn();
    } catch (error) {
      if (retries > 0 && this.isRetryableError(error)) {
        await this.delay(this.RETRY_DELAY_MS);
        return this.retryRequest(requestFn, retries - 1);
      }
      throw error;
    }
  }

  private isRetryableError(error: any): boolean {
    // Retry on network errors or 5xx server errors
    if (axios.isAxiosError(error)) {
      const status = error.response?.status;
      return !status || status >= 500;
    }
    return false;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const qualityApi = new QualityApiService();
