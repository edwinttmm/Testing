/**
 * Logging Utilities and Integration Helpers
 * 
 * This file provides utility functions and examples for using the new logging system
 * to replace console.log statements throughout the application.
 */

import { getLogger, Logger, LogContext } from '../services/logger';
import { loggingConfig } from '../config/logging.config';
import { PerformanceMetrics, FunctionArgument } from '../types/common';

/**
 * Component-specific logger helpers
 */
export class ComponentLogger {
  public logger: Logger; // Make public to allow external access

  constructor(componentName: string) {
    this.logger = getLogger(componentName);
  }

  /**
   * Log API calls with performance tracking
   */
  logApiCall(
    method: string,
    url: string,
    duration?: number,
    status?: number,
    error?: Error
  ): void {
    const context: LogContext = {
      action: 'api_call',
      metadata: {
        method,
        url: loggingConfig.sanitizeData({ url }).url,
        status,
        duration
      }
    };

    if (error) {
      this.logger.error(`API call failed: ${method} ${url}`, context, error);
    } else if (status && status >= 400) {
      this.logger.warn(`API call returned error: ${method} ${url}`, context);
    } else {
      this.logger.info(`API call completed: ${method} ${url}`, context);
    }
  }

  /**
   * Log user interactions
   */
  logUserAction(action: string, target?: string, metadata?: Record<string, unknown>): void {
    if (!loggingConfig.isFeatureEnabled('userActions')) {
      return;
    }

    this.logger.info(`User action: ${action}`, {
      action: 'user_interaction',
      metadata: {
        action,
        target,
        timestamp: Date.now(),
        ...metadata
      }
    });
  }

  /**
   * Log component lifecycle events
   */
  logLifecycle(event: 'mount' | 'unmount' | 'update', metadata?: Record<string, unknown>): void {
    if (!loggingConfig.isFeatureEnabled('componentLifecycle')) {
      return;
    }

    this.logger.debug(`Component ${event}`, {
      action: 'lifecycle',
      metadata: {
        event,
        ...metadata
      }
    });
  }

  /**
   * Log performance metrics
   */
  logPerformance(operation: string, duration: number, metadata?: Record<string, unknown>): void {
    if (!loggingConfig.isFeatureEnabled('performanceMetrics')) {
      return;
    }

    const level = duration > loggingConfig.getPerformanceConfig().slowThreshold ? 'warn' : 'debug';
    const message = `Performance: ${operation} took ${duration.toFixed(2)}ms`;

    this.logger[level](message, {
      action: 'performance',
      performance: {
        timestamp: Date.now(),
        duration
      },
      metadata: {
        operation,
        slow: duration > loggingConfig.getPerformanceConfig().slowThreshold,
        ...metadata
      }
    });
  }

  /**
   * Log state changes (for debugging)
   */
  logStateChange(stateName: string, oldValue: unknown, newValue: unknown): void {
    if (!loggingConfig.isFeatureEnabled('stateChanges')) {
      return;
    }

    this.logger.debug(`State change: ${stateName}`, {
      action: 'state_change',
      metadata: {
        stateName,
        oldValue: JSON.stringify(oldValue),
        newValue: JSON.stringify(newValue)
      }
    });
  }

  /**
   * Log WebSocket events
   */
  logWebSocketEvent(event: string, data?: unknown, error?: Error): void {
    if (!loggingConfig.isFeatureEnabled('websocketEvents')) {
      return;
    }

    const context: LogContext = {
      action: 'websocket',
      metadata: {
        event,
        dataSize: data ? JSON.stringify(data).length : 0
      }
    };

    if (error) {
      this.logger.error(`WebSocket error: ${event}`, context, error);
    } else {
      this.logger.info(`WebSocket event: ${event}`, context);
    }
  }

  /**
   * Log route changes
   */
  logRouteChange(from: string, to: string, metadata?: Record<string, unknown>): void {
    if (!loggingConfig.isFeatureEnabled('routeChanges')) {
      return;
    }

    this.logger.info(`Route change: ${from} → ${to}`, {
      action: 'navigation',
      metadata: {
        from,
        to,
        ...metadata
      }
    });
  }
}

/**
 * Performance tracking decorator
 */
export function withPerformanceLogging<T extends (...args: FunctionArgument[]) => unknown>(
  fn: T,
  componentName: string,
  operationName: string
): T {
  const logger = getLogger(componentName);
  
  return ((...args: FunctionArgument[]) => {
    const endTimer = logger.time(`${operationName}(${args.map(a => typeof a).join(', ')})`);
    
    try {
      const result = fn(...args);
      
      // Handle promises with proper type checking
      if (result && typeof result === 'object' && 'then' in result && typeof (result as { then: unknown }).then === 'function') {
        return (result as Promise<unknown>).finally(() => {
          endTimer();
        });
      }
      
      endTimer();
      return result;
    } catch (error) {
      endTimer();
      logger.error(`Error in ${operationName}`, {
        action: 'function_error',
        metadata: { operationName, argsCount: args.length }
      }, error as Error);
      throw error;
    }
  }) as T;
}

/**
 * Error boundary logging helper
 */
export function logErrorBoundary(
  error: Error,
  errorInfo: { componentStack: string },
  componentName: string
): void {
  const logger = getLogger('ErrorBoundary');
  
  logger.error(`Error caught by error boundary in ${componentName}`, {
    action: 'error_boundary',
    metadata: {
      componentName,
      componentStack: errorInfo.componentStack,
      errorName: error.name,
      errorMessage: error.message
    }
  }, error);
}

/**
 * Migration helper: Replace console.log usage
 * 
 * Usage examples:
 * 
 * BEFORE:
 * console.log('User clicked button', buttonId);
 * 
 * AFTER:
 * const logger = new ComponentLogger('ButtonComponent');
 * logger.logUserAction('click', 'button', { buttonId });
 * 
 * BEFORE:
 * console.log('API response:', response);
 * 
 * AFTER:
 * const logger = new ComponentLogger('ApiService');
 * logger.logApiCall('GET', '/api/data', duration, response.status);
 */

/**
 * Quick migration functions for common patterns
 */
export class LoggingMigration {
  /**
   * Replace console.log with appropriate logger method
   */
  static replaceConsoleLog(
    logger: ComponentLogger,
    level: 'debug' | 'info' | 'warn' | 'error',
    message: string,
    data?: unknown
  ): void {
    const context: LogContext = data ? {
      metadata: { data: JSON.stringify(data) }
    } : {};

    switch (level) {
      case 'debug':
        logger.logger.debug(message, context);
        break;
      case 'info':
        logger.logger.info(message, context);
        break;
      case 'warn':
        logger.logger.warn(message, context);
        break;
      case 'error':
        logger.logger.error(message, context);
        break;
    }
  }

  /**
   * Create logger for existing component
   */
  static createComponentLogger(componentName: string): ComponentLogger {
    return new ComponentLogger(componentName);
  }

  /**
   * Batch replace console.log in component
   */
  static setupComponentLogging(componentName: string) {
    const logger = new ComponentLogger(componentName);
    
    return {
      debug: (message: string, data?: unknown) => 
        LoggingMigration.replaceConsoleLog(logger, 'debug', message, data),
      info: (message: string, data?: unknown) => 
        LoggingMigration.replaceConsoleLog(logger, 'info', message, data),
      warn: (message: string, data?: unknown) => 
        LoggingMigration.replaceConsoleLog(logger, 'warn', message, data),
      error: (message: string, data?: unknown) => 
        LoggingMigration.replaceConsoleLog(logger, 'error', message, data),
      
      // Specialized logging methods
      logApiCall: logger.logApiCall.bind(logger),
      logUserAction: logger.logUserAction.bind(logger),
      logPerformance: logger.logPerformance.bind(logger),
      logWebSocketEvent: logger.logWebSocketEvent.bind(logger),
      logRouteChange: logger.logRouteChange.bind(logger)
    };
  }
}

/**
 * Console.log replacement patterns
 */
export const createLoggerReplacements = (componentName: string) => {
  const logger = getLogger(componentName);
  
  return {
    // Direct replacements
    log: (message: string, ...args: FunctionArgument[]) => 
      logger.info(message, { metadata: { args } }),
    debug: (message: string, ...args: FunctionArgument[]) => 
      logger.debug(message, { metadata: { args } }),
    info: (message: string, ...args: FunctionArgument[]) => 
      logger.info(message, { metadata: { args } }),
    warn: (message: string, ...args: FunctionArgument[]) => 
      logger.warn(message, { metadata: { args } }),
    error: (message: string, ...args: FunctionArgument[]) => 
      logger.error(message, { metadata: { args } }),
    
    // Performance tracking
    time: (label: string) => logger.time(label),
    
    // Structured logging
    logWithContext: (message: string, context: LogContext) => 
      logger.info(message, context)
  };
};

/**
 * Hook for React components
 */
export function useComponentLogger(componentName: string) {
  return createLoggerReplacements(componentName);
}

/**
 * Global error handler integration
 */
export function setupGlobalLogging(): void {
  const logger = getLogger('global');
  
  // Override console methods in development for migration assistance
  if (process.env.NODE_ENV === 'development' && process.env.REACT_APP_LOG_MIGRATION_WARNINGS === 'true') {
    const originalConsole = {
      log: console.log,
      debug: console.debug,
      info: console.info,
      warn: console.warn,
      error: console.error
    };
    
    console.log = (...args) => {
      logger.warn('console.log detected - consider migrating to structured logging', {
        metadata: { args: args.map(a => typeof a) }
      });
      originalConsole.log(...args);
    };
    
    // Similar overrides for other console methods...
  }
}

// Export commonly used instances
export const apiLogger = new ComponentLogger('API');
export const wsLogger = new ComponentLogger('WebSocket');
export const routerLogger = new ComponentLogger('Router');
export const performanceLogger = new ComponentLogger('Performance');