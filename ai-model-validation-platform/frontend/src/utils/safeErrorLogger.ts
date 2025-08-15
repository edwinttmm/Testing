/**
 * Safe Error Logger - Prevents [object Object] runtime errors
 * Provides centralized error logging with proper error message extraction
 */

import { getErrorMessage, getApiErrorMessage, getWebSocketErrorMessage } from './errorUtils';

export enum LogLevel {
  ERROR = 'error',
  WARN = 'warn', 
  INFO = 'info',
  DEBUG = 'debug'
}

export interface LogContext {
  component?: string;
  function?: string;
  userId?: string;
  sessionId?: string;
  requestId?: string;
  url?: string;
  timestamp?: string;
  [key: string]: any;
}

class SafeErrorLogger {
  private isDevelopment: boolean = process.env.NODE_ENV === 'development';
  private logLevel: LogLevel = this.isDevelopment ? LogLevel.DEBUG : LogLevel.ERROR;

  /**
   * Safely extracts string representation from any value
   * Prevents [object Object] by ensuring proper serialization
   */
  private safeStringify(value: unknown): string {
    if (value === null) return 'null';
    if (value === undefined) return 'undefined';
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    
    // Handle Error objects specifically
    if (value instanceof Error) {
      return getErrorMessage(value);
    }

    // Handle objects that might contain errors
    if (value && typeof value === 'object') {
      try {
        // Check for common error patterns
        if ('message' in value || 'error' in value || 'detail' in value) {
          return getErrorMessage(value);
        }

        // For other objects, safely stringify with fallback
        const stringified = JSON.stringify(value, null, 2);
        return stringified.length > 500 
          ? `${stringified.substring(0, 497)}...` 
          : stringified;
      } catch (stringifyError) {
        return `[Object: ${value.constructor?.name || 'Unknown'}]`;
      }
    }

    return String(value);
  }

  /**
   * Safely formats multiple arguments for logging
   */
  private formatArgs(args: unknown[]): string[] {
    return args.map(arg => this.safeStringify(arg));
  }

  /**
   * Adds context information to log messages
   */
  private buildLogMessage(message: string, context?: LogContext): string {
    if (!context && !this.isDevelopment) {
      return message;
    }

    const timestamp = new Date().toISOString();
    const contextInfo: LogContext = {
      timestamp,
      ...(typeof window !== 'undefined' && window.location.href ? { url: window.location.href } : {}),
      ...(typeof navigator !== 'undefined' && navigator.userAgent ? { userAgent: navigator.userAgent } : {}),
      ...context
    };

    if (this.isDevelopment) {
      return `[${timestamp}] ${message}`;
    }

    // In production, include structured context
    return `${message} | Context: ${JSON.stringify(contextInfo)}`;
  }

  /**
   * Safe console.error replacement
   */
  public error(message: string, error?: unknown, context?: LogContext): void {
    try {
      const safeMessage = this.buildLogMessage(message, context);
      
      if (error) {
        const safeError = this.safeStringify(error);
        if (this.isDevelopment) {
          console.error(safeMessage, safeError);
          
          // In development, also log the actual error object for debugging
          if (error instanceof Error && error.stack) {
            console.error('Stack trace:', error.stack);
          }
        } else {
          console.error(`${safeMessage}: ${safeError}`);
        }
      } else {
        console.error(safeMessage);
      }
    } catch (loggingError) {
      // Fallback logging if something goes wrong
      console.error('SafeErrorLogger failed:', message, 'Original error:', String(error));
    }
  }

  /**
   * Safe console.warn replacement
   */
  public warn(message: string, data?: unknown, context?: LogContext): void {
    if (this.logLevel === LogLevel.ERROR) return;

    try {
      const safeMessage = this.buildLogMessage(message, context);
      
      if (data) {
        const safeData = this.safeStringify(data);
        console.warn(safeMessage, safeData);
      } else {
        console.warn(safeMessage);
      }
    } catch (loggingError) {
      console.warn('SafeErrorLogger warn failed:', message);
    }
  }

  /**
   * Safe console.log replacement for info logging
   */
  public info(message: string, data?: unknown, context?: LogContext): void {
    if (this.logLevel === LogLevel.ERROR || this.logLevel === LogLevel.WARN) return;

    try {
      const safeMessage = this.buildLogMessage(message, context);
      
      if (data) {
        const safeData = this.safeStringify(data);
        console.log(safeMessage, safeData);
      } else {
        console.log(safeMessage);
      }
    } catch (loggingError) {
      console.log('SafeErrorLogger info failed:', message);
    }
  }

  /**
   * Debug logging (development only)
   */
  public debug(message: string, data?: unknown, context?: LogContext): void {
    if (!this.isDevelopment || this.logLevel !== LogLevel.DEBUG) return;

    try {
      const safeMessage = this.buildLogMessage(message, context);
      
      if (data) {
        const safeData = this.safeStringify(data);
        console.debug(safeMessage, safeData);
      } else {
        console.debug(safeMessage);
      }
    } catch (loggingError) {
      console.debug('SafeErrorLogger debug failed:', message);
    }
  }

  /**
   * Specialized API error logging
   */
  public apiError(message: string, error: unknown, context?: LogContext): void {
    const apiErrorMessage = getApiErrorMessage(error);
    this.error(`API Error - ${message}`, apiErrorMessage, {
      ...context,
      errorType: 'api',
      component: context?.component || 'api-service'
    });
  }

  /**
   * Specialized WebSocket error logging
   */
  public websocketError(message: string, error: unknown, context?: LogContext): void {
    const wsErrorMessage = getWebSocketErrorMessage(error);
    this.error(`WebSocket Error - ${message}`, wsErrorMessage, {
      ...context,
      errorType: 'websocket',
      component: context?.component || 'websocket-service'
    });
  }

  /**
   * Component error logging with React context
   */
  public componentError(componentName: string, error: unknown, context?: LogContext): void {
    this.error(`Component Error in ${componentName}`, error, {
      ...context,
      component: componentName,
      errorType: 'component'
    });
  }

  /**
   * Batch error logging for multiple errors
   */
  public logBatch(errors: Array<{ message: string; error: unknown; context?: LogContext }>): void {
    errors.forEach(({ message, error, context }, index) => {
      this.error(`[Batch ${index + 1}/${errors.length}] ${message}`, error, context);
    });
  }

  /**
   * Performance timing with error handling
   */
  public time(label: string): void {
    try {
      console.time(label);
    } catch (error) {
      this.warn('Failed to start timer', label);
    }
  }

  public timeEnd(label: string): void {
    try {
      console.timeEnd(label);
    } catch (error) {
      this.warn('Failed to end timer', label);
    }
  }

  /**
   * Set log level dynamically
   */
  public setLogLevel(level: LogLevel): void {
    this.logLevel = level;
  }

  /**
   * Get current log level
   */
  public getLogLevel(): LogLevel {
    return this.logLevel;
  }
}

// Create and export singleton instance
const safeLogger = new SafeErrorLogger();

// Export individual functions for easier migration from console.* calls
export const safeConsoleError = (message: string, error?: unknown, context?: LogContext) => 
  safeLogger.error(message, error, context);

export const safeConsoleWarn = (message: string, data?: unknown, context?: LogContext) => 
  safeLogger.warn(message, data, context);

export const safeConsoleLog = (message: string, data?: unknown, context?: LogContext) => 
  safeLogger.info(message, data, context);

export const safeConsoleDebug = (message: string, data?: unknown, context?: LogContext) => 
  safeLogger.debug(message, data, context);

// Specialized logging functions
export const logApiError = (message: string, error: unknown, context?: LogContext) =>
  safeLogger.apiError(message, error, context);

export const logWebSocketError = (message: string, error: unknown, context?: LogContext) =>
  safeLogger.websocketError(message, error, context);

export const logComponentError = (componentName: string, error: unknown, context?: LogContext) =>
  safeLogger.componentError(componentName, error, context);

// Default export
export default safeLogger;

// LogContext is already exported as interface above