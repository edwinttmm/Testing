/**
 * Enhanced LabJack Logger and Debugging Utility
 * 
 * This utility provides comprehensive logging, debugging, and monitoring
 * capabilities specifically for LabJack hardware integration operations.
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  CRITICAL = 4,
}

export interface LogEntry {
  timestamp: number;
  level: LogLevel;
  category: string;
  message: string;
  data?: any;
  context?: {
    sessionId?: string;
    deviceId?: string;
    operationType?: string;
    userId?: string;
  };
  performance?: {
    duration?: number;
    memoryUsage?: number;
    cpuLoad?: number;
  };
  error?: {
    code?: string;
    stack?: string;
    cause?: string;
  };
}

export interface PerformanceMetrics {
  connectionTime: number;
  dataTransferRate: number;
  errorRate: number;
  averageLatency: number;
  totalOperations: number;
  successfulOperations: number;
  memoryUsage: number;
}

class LabJackLogger {
  private logs: LogEntry[] = [];
  private maxLogEntries: number = 1000;
  private currentLogLevel: LogLevel = LogLevel.INFO;
  private isWindowsEnvironment: boolean;
  private performanceTracker: Map<string, { start: number; context: any }> = new Map();
  private metrics: PerformanceMetrics = {
    connectionTime: 0,
    dataTransferRate: 0,
    errorRate: 0,
    averageLatency: 0,
    totalOperations: 0,
    successfulOperations: 0,
    memoryUsage: 0,
  };

  constructor() {
    this.isWindowsEnvironment = navigator.platform.toLowerCase().includes('win');
    this.setupPerformanceMonitoring();
    
    // Set debug level based on environment
    if (process.env.NODE_ENV === 'development') {
      this.currentLogLevel = LogLevel.DEBUG;
    }
  }

  private setupPerformanceMonitoring(): void {
    // Monitor memory usage periodically
    setInterval(() => {
      if ('memory' in performance) {
        this.metrics.memoryUsage = (performance as any).memory?.usedJSHeapSize || 0;
      }
    }, 5000);

    // Setup error rate monitoring
    window.addEventListener('error', (event) => {
      if (event.error?.message?.toLowerCase().includes('labjack')) {
        this.updateErrorRate();
      }
    });
  }

  private updateErrorRate(): void {
    this.metrics.errorRate = 
      (this.metrics.totalOperations - this.metrics.successfulOperations) / 
      Math.max(this.metrics.totalOperations, 1);
  }

  setLogLevel(level: LogLevel): void {
    this.currentLogLevel = level;
    this.info('Logger', `Log level set to ${LogLevel[level]}`, { level });
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.currentLogLevel;
  }

  private createLogEntry(
    level: LogLevel,
    category: string,
    message: string,
    data?: any,
    context?: any,
    error?: any
  ): LogEntry {
    const entry: LogEntry = {
      timestamp: Date.now(),
      level,
      category,
      message,
      data,
      context: {
        ...context,
        isWindows: this.isWindowsEnvironment,
        userAgent: navigator.userAgent,
      },
    };

    // Add performance data if available
    if ('memory' in performance) {
      entry.performance = {
        memoryUsage: (performance as any).memory?.usedJSHeapSize || 0,
      };
    }

    // Add error details if provided
    if (error) {
      entry.error = {
        code: error.code,
        stack: error.stack,
        cause: error.cause?.toString(),
      };
    }

    return entry;
  }

  private addLog(entry: LogEntry): void {
    this.logs.push(entry);
    
    // Trim logs if exceeding max entries
    if (this.logs.length > this.maxLogEntries) {
      this.logs = this.logs.slice(-this.maxLogEntries);
    }

    // Console output with enhanced formatting
    this.outputToConsole(entry);
  }

  private outputToConsole(entry: LogEntry): void {
    if (!this.shouldLog(entry.level)) return;

    const timestamp = new Date(entry.timestamp).toISOString();
    const levelStr = LogLevel[entry.level].padEnd(8);
    const categoryStr = entry.category.padEnd(12);
    
    const prefix = `[${timestamp}] ${levelStr} [${categoryStr}]`;
    const style = this.getConsoleStyle(entry.level);

    switch (entry.level) {
      case LogLevel.DEBUG:
        console.debug(`%c${prefix} ${entry.message}`, style, entry.data);
        break;
      case LogLevel.INFO:
        console.info(`%c${prefix} ${entry.message}`, style, entry.data);
        break;
      case LogLevel.WARN:
        console.warn(`%c${prefix} ${entry.message}`, style, entry.data);
        break;
      case LogLevel.ERROR:
      case LogLevel.CRITICAL:
        console.error(`%c${prefix} ${entry.message}`, style, entry.data, entry.error);
        break;
    }
  }

  private getConsoleStyle(level: LogLevel): string {
    const styles = {
      [LogLevel.DEBUG]: 'color: #888; font-weight: normal;',
      [LogLevel.INFO]: 'color: #0066cc; font-weight: bold;',
      [LogLevel.WARN]: 'color: #ff8800; font-weight: bold;',
      [LogLevel.ERROR]: 'color: #cc0000; font-weight: bold;',
      [LogLevel.CRITICAL]: 'color: #ffffff; background-color: #cc0000; font-weight: bold; padding: 2px 4px;',
    };
    return styles[level] || '';
  }

  // Public logging methods
  debug(category: string, message: string, data?: any, context?: any): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      const entry = this.createLogEntry(LogLevel.DEBUG, category, message, data, context);
      this.addLog(entry);
    }
  }

  info(category: string, message: string, data?: any, context?: any): void {
    if (this.shouldLog(LogLevel.INFO)) {
      const entry = this.createLogEntry(LogLevel.INFO, category, message, data, context);
      this.addLog(entry);
    }
  }

  warn(category: string, message: string, data?: any, context?: any): void {
    if (this.shouldLog(LogLevel.WARN)) {
      const entry = this.createLogEntry(LogLevel.WARN, category, message, data, context);
      this.addLog(entry);
    }
  }

  error(category: string, message: string, error?: Error, data?: any, context?: any): void {
    if (this.shouldLog(LogLevel.ERROR)) {
      const entry = this.createLogEntry(LogLevel.ERROR, category, message, data, context, error);
      this.addLog(entry);
      this.updateErrorRate();
    }
  }

  critical(category: string, message: string, error?: Error, data?: any, context?: any): void {
    const entry = this.createLogEntry(LogLevel.CRITICAL, category, message, data, context, error);
    this.addLog(entry);
    this.updateErrorRate();
    
    // For critical errors, also try to notify external monitoring
    this.reportCriticalError(entry);
  }

  // Performance tracking methods
  startPerformanceTracker(operationId: string, context?: any): void {
    this.performanceTracker.set(operationId, {
      start: performance.now(),
      context: context || {},
    });
    
    this.debug('Performance', `Started tracking operation: ${operationId}`, { operationId, context });
  }

  endPerformanceTracker(operationId: string, success: boolean = true): number | null {
    const tracker = this.performanceTracker.get(operationId);
    if (!tracker) {
      this.warn('Performance', `No performance tracker found for operation: ${operationId}`, { operationId });
      return null;
    }

    const duration = performance.now() - tracker.start;
    this.performanceTracker.delete(operationId);

    // Update metrics
    this.metrics.totalOperations++;
    if (success) {
      this.metrics.successfulOperations++;
    }
    
    // Update average latency
    this.metrics.averageLatency = 
      (this.metrics.averageLatency * (this.metrics.totalOperations - 1) + duration) / 
      this.metrics.totalOperations;

    this.info('Performance', `Operation completed: ${operationId}`, {
      operationId,
      duration: Math.round(duration * 100) / 100,
      success,
      context: tracker.context,
    });

    return duration;
  }

  // Specialized LabJack logging methods
  logConnectionAttempt(mode: string, attempt: number, context?: any): void {
    this.info('Connection', `Attempting to connect via ${mode} mode (attempt ${attempt})`, {
      mode,
      attempt,
      isWindows: this.isWindowsEnvironment,
      ...context,
    });
  }

  logConnectionSuccess(mode: string, deviceInfo: any, latency?: number): void {
    this.metrics.connectionTime = latency || 0;
    this.info('Connection', `Successfully connected via ${mode} mode`, {
      mode,
      deviceInfo,
      latency,
      isWindows: this.isWindowsEnvironment,
    });
  }

  logConnectionFailure(mode: string, error: Error, context?: any): void {
    this.error('Connection', `Connection failed via ${mode} mode: ${error.message}`, error, {
      mode,
      isWindows: this.isWindowsEnvironment,
      ...context,
    });
  }

  logDataStreaming(sampleRate: number, channels: string[], bufferSize: number): void {
    this.info('Streaming', `Data streaming started`, {
      sampleRate,
      channels,
      bufferSize,
      estimatedDataRate: sampleRate * channels.length,
    });
  }

  logDataReceived(dataPoints: number, voltage: number[], channels: string[]): void {
    this.metrics.dataTransferRate = dataPoints;
    
    this.debug('Data', `Received ${dataPoints} data points`, {
      dataPoints,
      channels,
      voltageRange: voltage.length > 0 ? {
        min: Math.min(...voltage),
        max: Math.max(...voltage),
        avg: voltage.reduce((a, b) => a + b, 0) / voltage.length,
      } : null,
    });
  }

  logWindowsDriverIssue(issue: string, recommendations?: string[]): void {
    this.warn('Windows', `Driver issue detected: ${issue}`, {
      issue,
      recommendations,
      platform: navigator.platform,
      userAgent: navigator.userAgent,
    });
  }

  logDiagnosticTest(testName: string, result: 'passed' | 'failed', details?: any, duration?: number): void {
    const level = result === 'passed' ? LogLevel.INFO : LogLevel.ERROR;
    const message = `Diagnostic test ${testName}: ${result.toUpperCase()}`;
    
    if (level === LogLevel.INFO) {
      this.info('Diagnostic', message, { testName, result, details, duration });
    } else {
      this.error('Diagnostic', message, undefined, { testName, result, details, duration });
    }
  }

  // Utility methods
  getRecentLogs(count: number = 50, level?: LogLevel): LogEntry[] {
    let filteredLogs = this.logs;
    
    if (level !== undefined) {
      filteredLogs = this.logs.filter(log => log.level >= level);
    }
    
    return filteredLogs.slice(-count);
  }

  getLogsByCategory(category: string, count: number = 50): LogEntry[] {
    return this.logs
      .filter(log => log.category.toLowerCase() === category.toLowerCase())
      .slice(-count);
  }

  getPerformanceMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  exportLogs(format: 'json' | 'csv' = 'json'): string {
    if (format === 'csv') {
      const headers = ['timestamp', 'level', 'category', 'message', 'data'];
      const csvRows = [
        headers.join(','),
        ...this.logs.map(log => [
          new Date(log.timestamp).toISOString(),
          LogLevel[log.level],
          log.category,
          `"${log.message.replace(/"/g, '""')}"`,
          log.data ? `"${JSON.stringify(log.data).replace(/"/g, '""')}"` : '',
        ].join(',')),
      ];
      return csvRows.join('\n');
    }
    
    return JSON.stringify(this.logs, null, 2);
  }

  clearLogs(): void {
    const clearedCount = this.logs.length;
    this.logs = [];
    this.info('Logger', `Cleared ${clearedCount} log entries`);
  }

  private async reportCriticalError(entry: LogEntry): Promise<void> {
    // This could send to external monitoring service
    try {
      // For now, just log to localStorage for persistence
      const criticalLogs = JSON.parse(localStorage.getItem('labjack-critical-logs') || '[]');
      criticalLogs.push(entry);
      
      // Keep only last 10 critical errors
      if (criticalLogs.length > 10) {
        criticalLogs.splice(0, criticalLogs.length - 10);
      }
      
      localStorage.setItem('labjack-critical-logs', JSON.stringify(criticalLogs));
    } catch (error) {
      console.error('Failed to persist critical error:', error);
    }
  }

  // Cleanup method
  destroy(): void {
    this.performanceTracker.clear();
    this.logs = [];
  }
}

// Export singleton instance
export const labjackLogger = new LabJackLogger();

// Export utility function for easy performance tracking
export function withPerformanceTracking<T>(
  operationId: string,
  operation: () => Promise<T>,
  context?: any
): Promise<T> {
  return new Promise(async (resolve, reject) => {
    labjackLogger.startPerformanceTracker(operationId, context);
    
    try {
      const result = await operation();
      labjackLogger.endPerformanceTracker(operationId, true);
      resolve(result);
    } catch (error) {
      labjackLogger.endPerformanceTracker(operationId, false);
      labjackLogger.error('Operation', `Operation ${operationId} failed`, error as Error, context);
      reject(error);
    }
  });
}

export default labjackLogger;