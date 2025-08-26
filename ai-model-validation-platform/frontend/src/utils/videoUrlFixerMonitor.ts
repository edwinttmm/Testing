/**
 * Video URL Fixer Performance Monitor
 * 
 * Provides real-time performance monitoring, alerting, and optimization
 * recommendations for the video URL fixing system during database migration
 * and normal operations.
 */

import {
  getPerformanceMetrics,
  generatePerformanceReport,
  performMaintenance,
  resetMetrics
} from './videoUrlFixer';

interface MonitorConfig {
  intervalMs: number;
  alertThresholds: {
    avgProcessingTimeMs: number;
    errorRate: number;
    cacheHitRate: number;
    queueLength: number;
    memoryUsageMB: number;
  };
  enableConsoleReports: boolean;
  enableAlerts: boolean;
  enableAutoOptimization: boolean;
}

interface PerformanceAlert {
  type: 'warning' | 'error' | 'info';
  metric: string;
  value: number;
  threshold: number;
  message: string;
  timestamp: Date;
  recommendation?: string;
}

class VideoUrlFixerMonitor {
  private config: MonitorConfig;
  private monitoringInterval: NodeJS.Timeout | null = null;
  private alerts: PerformanceAlert[] = [];
  private lastReportTime = 0;
  private historicalMetrics: Array<{
    timestamp: Date;
    metrics: ReturnType<typeof getPerformanceMetrics>;
  }> = [];

  constructor(config: Partial<MonitorConfig> = {}) {
    this.config = {
      intervalMs: 30000, // 30 seconds
      alertThresholds: {
        avgProcessingTimeMs: 10,
        errorRate: 0.05, // 5%
        cacheHitRate: 0.5, // 50%
        queueLength: 100,
        memoryUsageMB: 100
      },
      enableConsoleReports: process.env.NODE_ENV === 'development',
      enableAlerts: true,
      enableAutoOptimization: true,
      ...config
    };
  }

  /**
   * Start performance monitoring
   */
  start(): void {
    if (this.monitoringInterval) {
      this.stop();
    }

    console.log('📊 VideoUrlFixer Performance Monitor started');
    
    this.monitoringInterval = setInterval(() => {
      this.performMonitoringCycle();
    }, this.config.intervalMs) as NodeJS.Timeout;

    // Initial monitoring cycle
    this.performMonitoringCycle();
  }

  /**
   * Stop performance monitoring
   */
  stop(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
      console.log('📊 VideoUrlFixer Performance Monitor stopped');
    }
  }

  /**
   * Perform a complete monitoring cycle
   */
  private performMonitoringCycle(): void {
    try {
      const metrics = getPerformanceMetrics();
      const timestamp = new Date();
      
      // Store historical data (keep last 100 entries)
      this.historicalMetrics.push({ timestamp, metrics });
      if (this.historicalMetrics.length > 100) {
        this.historicalMetrics.shift();
      }

      // Check for alerts
      if (this.config.enableAlerts) {
        this.checkAlerts(metrics, timestamp);
      }

      // Auto-optimization
      if (this.config.enableAutoOptimization) {
        this.performAutoOptimization(metrics);
      }

      // Console reporting (throttled to every 5 minutes in production)
      const now = Date.now();
      const shouldReport = this.config.enableConsoleReports || 
                          (now - this.lastReportTime) > 300000; // 5 minutes

      if (shouldReport) {
        this.generateConsoleReport(metrics);
        this.lastReportTime = now;
      }

    } catch (error) {
      console.error('📊 VideoUrlFixer Monitor error:', error);
    }
  }

  /**
   * Check for performance alerts
   */
  private checkAlerts(metrics: ReturnType<typeof getPerformanceMetrics>, timestamp: Date): void {
    const { alertThresholds } = this.config;
    const newAlerts: PerformanceAlert[] = [];

    // Average processing time alert
    if (metrics.averageProcessingTime > alertThresholds.avgProcessingTimeMs) {
      newAlerts.push({
        type: 'warning',
        metric: 'avgProcessingTime',
        value: metrics.averageProcessingTime,
        threshold: alertThresholds.avgProcessingTimeMs,
        message: `High average processing time: ${metrics.averageProcessingTime.toFixed(2)}ms`,
        timestamp,
        recommendation: 'Consider cache optimization or reducing batch sizes'
      });
    }

    // Error rate alert
    const errorRate = metrics.totalProcessed > 0 ? 
      metrics.errorsEncountered / metrics.totalProcessed : 0;
    if (errorRate > alertThresholds.errorRate) {
      newAlerts.push({
        type: 'error',
        metric: 'errorRate',
        value: errorRate,
        threshold: alertThresholds.errorRate,
        message: `High error rate: ${(errorRate * 100).toFixed(1)}%`,
        timestamp,
        recommendation: 'Review input validation and error handling'
      });
    }

    // Cache hit rate alert
    if (metrics.cacheStats.cacheHitRate < alertThresholds.cacheHitRate && 
        metrics.totalProcessed > 50) {
      newAlerts.push({
        type: 'warning',
        metric: 'cacheHitRate',
        value: metrics.cacheStats.cacheHitRate,
        threshold: alertThresholds.cacheHitRate,
        message: `Low cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`,
        timestamp,
        recommendation: 'Increase cache TTL or review URL patterns'
      });
    }

    // Queue length alert
    if (metrics.systemStats.queueLength > alertThresholds.queueLength) {
      newAlerts.push({
        type: 'warning',
        metric: 'queueLength',
        value: metrics.systemStats.queueLength,
        threshold: alertThresholds.queueLength,
        message: `Large background queue: ${metrics.systemStats.queueLength} items`,
        timestamp,
        recommendation: 'Increase background processing capacity'
      });
    }

    // Memory usage estimation
    const estimatedMemoryMB = metrics.cacheStats.urlMappingCacheSize * 0.1; // Rough estimate
    if (estimatedMemoryMB > alertThresholds.memoryUsageMB) {
      newAlerts.push({
        type: 'warning',
        metric: 'memoryUsage',
        value: estimatedMemoryMB,
        threshold: alertThresholds.memoryUsageMB,
        message: `High estimated memory usage: ${estimatedMemoryMB.toFixed(1)}MB`,
        timestamp,
        recommendation: 'Trigger cache cleanup or reduce cache size limits'
      });
    }

    // Store and report new alerts
    if (newAlerts.length > 0) {
      this.alerts.push(...newAlerts);
      
      // Keep only last 50 alerts
      if (this.alerts.length > 50) {
        this.alerts = this.alerts.slice(-50);
      }

      // Report critical alerts immediately
      newAlerts
        .filter(alert => alert.type === 'error')
        .forEach(alert => {
          console.error(`🚨 VideoUrlFixer Alert: ${alert.message}`);
          if (alert.recommendation) {
            console.error(`💡 Recommendation: ${alert.recommendation}`);
          }
        });
    }
  }

  /**
   * Perform automatic optimizations based on metrics
   */
  private performAutoOptimization(metrics: ReturnType<typeof getPerformanceMetrics>): void {
    // Auto cleanup when cache gets large
    if (metrics.cacheStats.urlMappingCacheSize > 800) {
      console.log('🔧 VideoUrlFixer: Auto-triggering cache cleanup');
      performMaintenance();
    }

    // Reset metrics if they get too large (prevent overflow)
    if (metrics.totalProcessed > 1000000) {
      console.log('🔧 VideoUrlFixer: Auto-resetting metrics to prevent overflow');
      resetMetrics();
    }
  }

  /**
   * Generate console performance report
   */
  private generateConsoleReport(metrics: ReturnType<typeof getPerformanceMetrics>): void {
    const report = generatePerformanceReport();
    
    console.group('📊 VideoUrlFixer Performance Report');
    console.log('Summary:', report.summary);
    
    if (metrics.systemStats.migrationActive) {
      console.log('🔄 Migration Mode: ACTIVE');
      console.log(`Migration-aware skips: ${metrics.migrationAwareSkips}`);
    }

    console.log('Performance Metrics:');
    console.log(`  • Total processed: ${metrics.totalProcessed}`);
    console.log(`  • Average processing time: ${metrics.averageProcessingTime.toFixed(2)}ms`);
    console.log(`  • Cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`);
    console.log(`  • Queue length: ${metrics.systemStats.queueLength}`);
    
    if (report.insights.length > 0) {
      console.log('Insights:');
      report.insights.forEach(insight => console.log(`  • ${insight}`));
    }
    
    if (report.recommendations.length > 0) {
      console.log('Recommendations:');
      report.recommendations.forEach(rec => console.log(`  • ${rec}`));
    }

    // Show recent alerts
    const recentAlerts = this.alerts.filter(
      alert => Date.now() - alert.timestamp.getTime() < 300000 // Last 5 minutes
    );
    if (recentAlerts.length > 0) {
      console.log('Recent Alerts:');
      recentAlerts.forEach(alert => {
        const icon = alert.type === 'error' ? '🚨' : 
                    alert.type === 'warning' ? '⚠️' : 'ℹ️';
        console.log(`  ${icon} ${alert.message}`);
      });
    }
    
    console.groupEnd();
  }

  /**
   * Get current monitoring status
   */
  getStatus(): {
    isMonitoring: boolean;
    config: MonitorConfig;
    recentAlerts: PerformanceAlert[];
    metrics: ReturnType<typeof getPerformanceMetrics>;
    trend: {
      processingTimeChange: number;
      cacheHitRateChange: number;
      errorRateChange: number;
    };
  } {
    const metrics = getPerformanceMetrics();
    const recentAlerts = this.alerts.filter(
      alert => Date.now() - alert.timestamp.getTime() < 600000 // Last 10 minutes
    );

    // Calculate trends
    const trend = this.calculateTrends();

    return {
      isMonitoring: this.monitoringInterval !== null,
      config: this.config,
      recentAlerts,
      metrics,
      trend
    };
  }

  /**
   * Calculate performance trends
   */
  private calculateTrends(): {
    processingTimeChange: number;
    cacheHitRateChange: number;
    errorRateChange: number;
  } {
    if (this.historicalMetrics.length < 2) {
      return {
        processingTimeChange: 0,
        cacheHitRateChange: 0,
        errorRateChange: 0
      };
    }

    const recent = this.historicalMetrics.slice(-5); // Last 5 data points
    const older = this.historicalMetrics.slice(-10, -5); // Previous 5 data points

    const recentAvg = recent.reduce((sum, entry) => sum + entry.metrics.averageProcessingTime, 0) / recent.length;
    const olderAvg = older.length > 0 ? 
      older.reduce((sum, entry) => sum + entry.metrics.averageProcessingTime, 0) / older.length : recentAvg;

    const recentCacheHit = recent.reduce((sum, entry) => sum + entry.metrics.cacheStats.cacheHitRate, 0) / recent.length;
    const olderCacheHit = older.length > 0 ?
      older.reduce((sum, entry) => sum + entry.metrics.cacheStats.cacheHitRate, 0) / older.length : recentCacheHit;

    const recentErrorRate = recent.reduce((sum, entry) => {
      const rate = entry.metrics.totalProcessed > 0 ? 
        entry.metrics.errorsEncountered / entry.metrics.totalProcessed : 0;
      return sum + rate;
    }, 0) / recent.length;

    const olderErrorRate = older.length > 0 ? older.reduce((sum, entry) => {
      const rate = entry.metrics.totalProcessed > 0 ? 
        entry.metrics.errorsEncountered / entry.metrics.totalProcessed : 0;
      return sum + rate;
    }, 0) / older.length : recentErrorRate;

    return {
      processingTimeChange: recentAvg - olderAvg,
      cacheHitRateChange: recentCacheHit - olderCacheHit,
      errorRateChange: recentErrorRate - olderErrorRate
    };
  }

  /**
   * Export monitoring data for analysis
   */
  exportData(): {
    config: MonitorConfig;
    alerts: PerformanceAlert[];
    historicalMetrics: typeof this.historicalMetrics;
    exportTimestamp: Date;
  } {
    return {
      config: this.config,
      alerts: this.alerts,
      historicalMetrics: this.historicalMetrics,
      exportTimestamp: new Date()
    };
  }

  /**
   * Clear all monitoring data
   */
  clearData(): void {
    this.alerts = [];
    this.historicalMetrics = [];
    this.lastReportTime = 0;
  }
}

// Create default monitor instance
export const videoUrlFixerMonitor = new VideoUrlFixerMonitor();

// Auto-start monitoring in browser environment
if (typeof window !== 'undefined') {
  // Delay start to allow system initialization
  setTimeout(() => {
    videoUrlFixerMonitor.start();
  }, 5000);
}

export default VideoUrlFixerMonitor;