/**
 * Error reporting service for the AI Model Validation Platform
 * Handles error tracking, analytics, and reporting to external services
 */

interface ErrorReport {
  errorId: string;
  message: string;
  stack?: string;
  componentStack?: string;
  level: 'app' | 'page' | 'component';
  context: string;
  timestamp: string;
  userAgent: string;
  url: string;
  userId?: string;
  sessionId?: string;
  additionalData?: Record<string, any>;
}

interface ErrorReportingConfig {
  apiEndpoint?: string;
  apiKey?: string;
  enableConsoleLogging: boolean;
  enableRemoteLogging: boolean;
  sampleRate: number;
  ignoreErrors: string[];
  maxRetries: number;
}

class ErrorReportingService {
  private config: ErrorReportingConfig;
  private sessionId: string;
  private pendingReports: ErrorReport[] = [];
  private retryQueue: ErrorReport[] = [];

  constructor(config: Partial<ErrorReportingConfig> = {}) {
    this.config = {
      enableConsoleLogging: process.env.NODE_ENV === 'development',
      enableRemoteLogging: process.env.NODE_ENV === 'production',
      sampleRate: 1.0, // Report all errors by default
      ignoreErrors: [
        'Script error',
        'Non-Error promise rejection captured',
        'ResizeObserver loop limit exceeded',
        'Loading chunk',
      ],
      maxRetries: 3,
      ...config,
    };

    this.sessionId = this.generateSessionId();
    this.setupGlobalErrorHandlers();
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private setupGlobalErrorHandlers(): void {
    // Handle unhandled errors
    window.addEventListener('error', (event) => {
      this.reportError({
        message: event.message,
        stack: event.error?.stack,
        level: 'app',
        context: 'global-error-handler',
        additionalData: {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
        },
      });
    });

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.reportError({
        message: event.reason?.message || 'Unhandled Promise Rejection',
        stack: event.reason?.stack,
        level: 'app',
        context: 'unhandled-promise-rejection',
        additionalData: {
          reason: event.reason,
        },
      });
    });

    // Handle resource loading errors
    window.addEventListener('error', (event) => {
      if (event.target !== window) {
        this.reportError({
          message: 'Resource loading error',
          level: 'app',
          context: 'resource-loading-error',
          additionalData: {
            element: (event.target as any)?.tagName,
            source: (event.target as any)?.src || (event.target as any)?.href,
          },
        });
      }
    }, true);
  }

  public reportError(errorData: Partial<ErrorReport> & { message: string }): void {
    // Check if error should be ignored
    if (this.shouldIgnoreError(errorData.message)) {
      return;
    }

    // Apply sampling
    if (Math.random() > this.config.sampleRate) {
      return;
    }

    const report: ErrorReport = {
      errorId: this.generateErrorId(),
      level: 'component',
      context: 'unknown',
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      sessionId: this.sessionId,
      ...errorData,
    };

    this.processErrorReport(report);
  }

  private shouldIgnoreError(message: string): boolean {
    return this.config.ignoreErrors.some(pattern => 
      message.toLowerCase().includes(pattern.toLowerCase())
    );
  }

  private generateErrorId(): string {
    return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private processErrorReport(report: ErrorReport): void {
    // Console logging
    if (this.config.enableConsoleLogging) {
      this.logToConsole(report);
    }

    // Remote logging
    if (this.config.enableRemoteLogging) {
      this.sendToRemoteService(report);
    }

    // Store in pending reports for debugging
    this.pendingReports.push(report);
    
    // Keep only last 100 reports to prevent memory leaks
    if (this.pendingReports.length > 100) {
      this.pendingReports = this.pendingReports.slice(-100);
    }
  }

  private logToConsole(report: ErrorReport): void {
    const groupName = `🚨 Error Report (${report.level.toUpperCase()})`;
    console.group(groupName);
    console.error('Message:', report.message);
    console.log('Error ID:', report.errorId);
    console.log('Context:', report.context);
    console.log('Timestamp:', report.timestamp);
    
    if (report.stack) {
      console.log('Stack Trace:', report.stack);
    }
    
    if (report.componentStack) {
      console.log('Component Stack:', report.componentStack);
    }
    
    if (report.additionalData) {
      console.log('Additional Data:', report.additionalData);
    }
    
    console.groupEnd();
  }

  private async sendToRemoteService(report: ErrorReport): Promise<void> {
    if (!this.config.apiEndpoint) {
      return;
    }

    try {
      const response = await fetch(this.config.apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.config.apiKey && { 'Authorization': `Bearer ${this.config.apiKey}` }),
        },
        body: JSON.stringify(report),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Remove from retry queue if it was there
      this.retryQueue = this.retryQueue.filter(r => r.errorId !== report.errorId);

    } catch (error) {
      console.warn('Failed to send error report to remote service:', error);
      
      // Add to retry queue
      if (!this.retryQueue.find(r => r.errorId === report.errorId)) {
        this.retryQueue.push(report);
        this.scheduleRetry(report);
      }
    }
  }

  private scheduleRetry(report: ErrorReport): void {
    // Exponential backoff retry
    const retryCount = report.additionalData?.retryCount || 0;
    
    if (retryCount < this.config.maxRetries) {
      const delay = Math.min(1000 * Math.pow(2, retryCount), 30000); // Max 30s delay
      
      setTimeout(() => {
        const updatedReport = {
          ...report,
          additionalData: {
            ...report.additionalData,
            retryCount: retryCount + 1,
          },
        };
        
        this.sendToRemoteService(updatedReport);
      }, delay);
    }
  }

  // Public methods for error boundary integration
  public reportBoundaryError(
    error: Error,
    errorInfo: { componentStack: string },
    level: 'app' | 'page' | 'component',
    context: string
  ): void {
    this.reportError({
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      level,
      context,
      additionalData: {
        errorName: error.name,
        errorBoundary: true,
      },
    });
  }

  public reportApiError(
    error: Error,
    context: string,
    requestDetails?: {
      method?: string;
      url?: string;
      status?: number;
      statusText?: string;
    }
  ): void {
    this.reportError({
      message: error.message,
      stack: error.stack,
      level: 'component',
      context: `api-${context}`,
      additionalData: {
        errorType: 'api',
        ...requestDetails,
      },
    });
  }

  public reportWebSocketError(
    event: Event,
    context: string,
    connectionDetails?: {
      url?: string;
      readyState?: number;
      reconnectAttempts?: number;
    }
  ): void {
    this.reportError({
      message: `WebSocket error: ${event.type}`,
      level: 'component',
      context: `websocket-${context}`,
      additionalData: {
        errorType: 'websocket',
        eventType: event.type,
        ...connectionDetails,
      },
    });
  }

  // Utility methods
  public getPendingReports(): ErrorReport[] {
    return [...this.pendingReports];
  }

  public getRetryQueue(): ErrorReport[] {
    return [...this.retryQueue];
  }

  public clearPendingReports(): void {
    this.pendingReports = [];
  }

  public updateConfig(newConfig: Partial<ErrorReportingConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }
}

// Create singleton instance
export const errorReporting = new ErrorReportingService({
  // Configure based on environment
  apiEndpoint: process.env.REACT_APP_ERROR_REPORTING_ENDPOINT,
  apiKey: process.env.REACT_APP_ERROR_REPORTING_API_KEY,
  enableRemoteLogging: process.env.REACT_APP_ENABLE_ERROR_REPORTING === 'true',
});

export default errorReporting;
export type { ErrorReport, ErrorReportingConfig };