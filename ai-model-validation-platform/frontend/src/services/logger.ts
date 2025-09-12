/**
 * Production-Ready Logging System
 * 
 * Features:
 * - Environment-aware logging (dev shows all, production filters)
 * - Structured logging with context
 * - Performance-optimized (no-op in production unless enabled)
 * - Log levels with color coding in development
 * - Component-scoped logging
 * - Remote logging preparation
 * - Memory-efficient buffering
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 99
}

export interface LogContext {
  component?: string;
  action?: string;
  userId?: string;
  sessionId?: string;
  requestId?: string;
  metadata?: Record<string, unknown>;
  performance?: {
    timestamp: number;
    duration?: number;
    memory?: number;
    memoryDelta?: number;
  };
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: LogContext;
  error?: Error;
  stack?: string;
}

export interface RemoteLogConfig {
  endpoint: string;
  apiKey?: string;
  batchSize?: number;
  flushInterval?: number;
  enabled?: boolean;
}

export class Logger {
  private component: string;
  private minLevel: LogLevel;
  private isDevelopment: boolean;
  private enabledCategories: Set<string>;
  private logBuffer: LogEntry[] = [];
  private maxBufferSize = 100;
  private remoteConfig?: RemoteLogConfig;

  // Color codes for development console output
  private static readonly COLORS: Record<LogLevel | 'reset', string> = {
    [LogLevel.DEBUG]: '\x1b[36m', // Cyan
    [LogLevel.INFO]: '\x1b[32m',  // Green
    [LogLevel.WARN]: '\x1b[33m',  // Yellow
    [LogLevel.ERROR]: '\x1b[31m', // Red
    [LogLevel.NONE]: '\x1b[37m',  // White
    reset: '\x1b[0m'
  };

  constructor(
    component: string,
    minLevel: LogLevel = LogLevel.INFO,
    enabledCategories?: string[],
    remoteConfig?: RemoteLogConfig
  ) {
    this.component = component;
    this.minLevel = minLevel;
    this.isDevelopment = process.env.NODE_ENV === 'development';
    this.enabledCategories = new Set(enabledCategories || []);
    if (remoteConfig !== undefined) {
      this.remoteConfig = remoteConfig;
    }

    // Environment-specific level override
    const envLogLevel = process.env.REACT_APP_LOG_LEVEL?.toUpperCase();
    if (envLogLevel && LogLevel[envLogLevel as keyof typeof LogLevel] !== undefined) {
      this.minLevel = LogLevel[envLogLevel as keyof typeof LogLevel];
    }

    // Enable all categories in development
    if (this.isDevelopment) {
      this.enabledCategories.add('*');
    }

    // Production optimization - disable debug by default
    if (!this.isDevelopment && this.minLevel < LogLevel.WARN && !process.env.REACT_APP_DEBUG) {
      this.minLevel = LogLevel.WARN;
    }
  }

  /**
   * Performance-optimized logging method
   * Returns immediately if logging is disabled for this level
   */
  private shouldLog(level: LogLevel, category?: string): boolean {
    // Fast path - level check first
    if (level < this.minLevel) {
      return false;
    }

    // Category check
    if (category && !this.enabledCategories.has('*') && !this.enabledCategories.has(category)) {
      return false;
    }

    // Production override - only errors unless debug flag is set
    if (!this.isDevelopment && level < LogLevel.ERROR && !process.env.REACT_APP_DEBUG) {
      return false;
    }

    return true;
  }

  /**
   * Create structured log entry
   */
  private createLogEntry(
    level: LogLevel,
    message: string,
    context?: LogContext,
    error?: Error
  ): LogEntry {
    const timestamp = new Date().toISOString();
    
    const logEntry: LogEntry = {
      timestamp,
      level,
      message,
      context: {
        component: this.component,
        ...context,
        performance: {
          timestamp: Date.now(),
          ...(this.getMemoryUsage() !== undefined && { memory: this.getMemoryUsage() }),
          ...context?.performance
        }
      } as LogContext
    };

    if (error !== undefined) {
      logEntry.error = error;
      if (error.stack !== undefined) {
        logEntry.stack = error.stack;
      }
    }

    return logEntry;
  }

  /**
   * Get memory usage (only in development or when performance monitoring is enabled)
   */
  private getMemoryUsage(): number | undefined {
    if (this.isDevelopment || process.env.REACT_APP_ENABLE_PERFORMANCE_MONITORING === 'true') {
      // Type assertion for performance.memory browser support
      const performanceWithMemory = performance as Performance & {
        memory?: {
          usedJSHeapSize: number;
          totalJSHeapSize: number;
          jsHeapSizeLimit: number;
        };
      };
      return performanceWithMemory.memory?.usedJSHeapSize;
    }
    return undefined;
  }

  /**
   * Format log for console output in development
   */
  private formatForConsole(entry: LogEntry): string[] {
    const levelName = LogLevel[entry.level];
    const color = Logger.COLORS[entry.level];
    const reset = Logger.COLORS.reset;
    
    const prefix = `${color}[${levelName}]${reset} ${entry.timestamp} [${entry.context?.component}]`;
    
    const parts = [prefix, entry.message];
    
    if (entry.context && Object.keys(entry.context).length > 1) {
      parts.push(JSON.stringify(entry.context, null, 2));
    }
    
    if (entry.error) {
      parts.push(entry.error.stack || entry.error.message);
    }
    
    return parts;
  }

  /**
   * Log a message with optional context
   */
  private log(
    level: LogLevel,
    message: string,
    context?: LogContext,
    error?: Error
  ): void {
    // Performance check - exit early if logging is disabled
    if (!this.shouldLog(level, context?.action)) {
      return;
    }

    const entry = this.createLogEntry(level, message, context, error);
    
    // Add to buffer for potential remote logging
    this.addToBuffer(entry);
    
    // Console output
    this.outputToConsole(entry);
    
    // Remote logging if configured
    this.sendToRemote(entry);
  }

  /**
   * Add entry to buffer for remote logging
   */
  private addToBuffer(entry: LogEntry): void {
    if (this.remoteConfig?.enabled) {
      this.logBuffer.push(entry);
      
      // Prevent memory leaks
      if (this.logBuffer.length > this.maxBufferSize) {
        this.logBuffer.shift();
      }
      
      // Auto-flush if batch size reached
      if (this.logBuffer.length >= (this.remoteConfig.batchSize || 10)) {
        this.flushBuffer();
      }
    }
  }

  /**
   * Output to console (development) or structured logging (production)
   */
  private outputToConsole(entry: LogEntry): void {
    if (this.isDevelopment) {
      const formatted = this.formatForConsole(entry);
      
      switch (entry.level) {
        case LogLevel.DEBUG:
          console.debug(...formatted);
          break;
        case LogLevel.INFO:
          console.info(...formatted);
          break;
        case LogLevel.WARN:
          console.warn(...formatted);
          break;
        case LogLevel.ERROR:
          console.error(...formatted);
          break;
      }
    } else {
      // Production: structured logging for external systems
      const structured = {
        '@timestamp': entry.timestamp,
        level: LogLevel[entry.level],
        message: entry.message,
        component: this.component,
        ...entry.context,
        error: entry.error ? {
          name: entry.error.name,
          message: entry.error.message,
          stack: entry.stack
        } : undefined
      };
      
      // Only use console methods that won't be stripped in production
      if (entry.level >= LogLevel.ERROR) {
        console.error(JSON.stringify(structured));
      } else if (entry.level >= LogLevel.WARN) {
        console.warn(JSON.stringify(structured));
      }
    }
  }

  /**
   * Send logs to remote service
   */
  private sendToRemote(_entry: LogEntry): void {
    if (!this.remoteConfig?.enabled || !this.remoteConfig.endpoint) {
      return;
    }

    // Implement remote logging (placeholder for future implementation)
    // This would typically batch logs and send via fetch/axios
  }

  /**
   * Flush log buffer to remote service
   */
  public flushBuffer(): Promise<void> {
    return new Promise((resolve) => {
      if (!this.remoteConfig?.enabled || this.logBuffer.length === 0) {
        resolve();
        return;
      }

      // Implement actual remote flushing here
      const logs = [...this.logBuffer];
      this.logBuffer = [];
      
      // Send logs to remote endpoint
      // For now, just resolve immediately
      resolve();
    });
  }

  /**
   * Public logging methods
   */
  public debug(message: string, context?: LogContext): void {
    this.log(LogLevel.DEBUG, message, context);
  }

  public info(message: string, context?: LogContext): void {
    this.log(LogLevel.INFO, message, context);
  }

  public warn(message: string, context?: LogContext, error?: Error): void {
    this.log(LogLevel.WARN, message, context, error);
  }

  public error(message: string, context?: LogContext, error?: Error): void {
    this.log(LogLevel.ERROR, message, context, error);
  }

  /**
   * Performance logging helper
   */
  public time(label: string): () => void {
    const startTime = performance.now();
    const startMemory = this.getMemoryUsage();
    
    return () => {
      const duration = performance.now() - startTime;
      const endMemory = this.getMemoryUsage();
      
      this.debug(`Performance: ${label}`, {
        action: 'performance',
        performance: {
          timestamp: Date.now(),
          duration,
          ...(endMemory !== undefined && { memory: endMemory }),
          ...(startMemory !== undefined && endMemory !== undefined && { memoryDelta: endMemory - startMemory })
        }
      });
    };
  }

  /**
   * Create child logger with additional context
   */
  public child(additionalContext: Partial<LogContext>): Logger {
    const childLogger = new Logger(
      this.component,
      this.minLevel,
      Array.from(this.enabledCategories),
      this.remoteConfig
    );
    
    // Store additional context for child logger using proper typing
    interface ChildLoggerWithContext extends Logger {
      _additionalContext?: Partial<LogContext>;
    }
    (childLogger as ChildLoggerWithContext)._additionalContext = additionalContext;
    
    // Override public methods to include additional context
    const originalDebug = childLogger.debug.bind(childLogger);
    const originalInfo = childLogger.info.bind(childLogger);
    const originalWarn = childLogger.warn.bind(childLogger);
    const originalError = childLogger.error.bind(childLogger);
    
    childLogger.debug = (message: string, context?: LogContext) => {
      const mergedContext = { ...additionalContext, ...context };
      return originalDebug(message, mergedContext);
    };
    
    childLogger.info = (message: string, context?: LogContext) => {
      const mergedContext = { ...additionalContext, ...context };
      return originalInfo(message, mergedContext);
    };
    
    childLogger.warn = (message: string, context?: LogContext, error?: Error) => {
      const mergedContext = { ...additionalContext, ...context };
      return originalWarn(message, mergedContext, error);
    };
    
    childLogger.error = (message: string, context?: LogContext, error?: Error) => {
      const mergedContext = { ...additionalContext, ...context };
      return originalError(message, mergedContext, error);
    };
    
    return childLogger;
  }

  /**
   * Configure remote logging
   */
  public configureRemote(config: RemoteLogConfig): void {
    this.remoteConfig = config;
  }

  /**
   * Get current log level
   */
  public getLevel(): LogLevel {
    return this.minLevel;
  }

  /**
   * Set log level dynamically
   */
  public setLevel(level: LogLevel): void {
    this.minLevel = level;
  }

  /**
   * Enable/disable categories
   */
  public setCategories(categories: string[]): void {
    this.enabledCategories = new Set(categories);
  }
}

/**
 * Logger factory for creating component-specific loggers
 */
export class LoggerFactory {
  private static instance: LoggerFactory;
  private loggers: Map<string, Logger> = new Map();
  private globalConfig: {
    minLevel: LogLevel;
    enabledCategories: string[];
    remoteConfig?: RemoteLogConfig;
  };

  private constructor() {
    const remoteConfig = this.getRemoteConfig();
    this.globalConfig = {
      minLevel: this.getDefaultLogLevel(),
      enabledCategories: this.getDefaultCategories(),
      ...(remoteConfig && { remoteConfig })
    };
  }

  public static getInstance(): LoggerFactory {
    if (!LoggerFactory.instance) {
      LoggerFactory.instance = new LoggerFactory();
    }
    return LoggerFactory.instance;
  }

  /**
   * Get or create logger for component
   */
  public getLogger(component: string): Logger {
    if (!this.loggers.has(component)) {
      const logger = new Logger(
        component,
        this.globalConfig.minLevel,
        this.globalConfig.enabledCategories,
        this.globalConfig.remoteConfig
      );
      this.loggers.set(component, logger);
    }
    return this.loggers.get(component)!;
  }

  /**
   * Update configuration for all loggers
   */
  public updateConfig(config: Partial<LoggerFactory['globalConfig']>): void {
    this.globalConfig = { ...this.globalConfig, ...config };
    
    // Update existing loggers
    this.loggers.forEach((logger) => {
      if (config.minLevel !== undefined) {
        logger.setLevel(config.minLevel);
      }
      if (config.enabledCategories) {
        logger.setCategories(config.enabledCategories);
      }
      if (config.remoteConfig) {
        logger.configureRemote(config.remoteConfig);
      }
    });
  }

  /**
   * Get default log level from environment
   */
  private getDefaultLogLevel(): LogLevel {
    const envLevel = process.env.REACT_APP_LOG_LEVEL?.toUpperCase();
    if (envLevel && LogLevel[envLevel as keyof typeof LogLevel] !== undefined) {
      return LogLevel[envLevel as keyof typeof LogLevel];
    }
    
    return process.env.NODE_ENV === 'development' ? LogLevel.DEBUG : LogLevel.WARN;
  }

  /**
   * Get default categories from environment
   */
  private getDefaultCategories(): string[] {
    const envCategories = process.env.REACT_APP_LOG_CATEGORIES;
    if (envCategories) {
      return envCategories.split(',').map(c => c.trim());
    }
    
    return process.env.NODE_ENV === 'development' ? ['*'] : [];
  }

  /**
   * Get remote logging configuration
   */
  private getRemoteConfig(): RemoteLogConfig | undefined {
    const endpoint = process.env.REACT_APP_LOG_ENDPOINT;
    const apiKey = process.env.REACT_APP_LOG_API_KEY;
    
    if (endpoint) {
      return {
        endpoint,
        ...(apiKey && { apiKey }),
        batchSize: parseInt(process.env.REACT_APP_LOG_BATCH_SIZE || '10'),
        flushInterval: parseInt(process.env.REACT_APP_LOG_FLUSH_INTERVAL || '30000'),
        enabled: process.env.REACT_APP_LOG_REMOTE_ENABLED === 'true'
      };
    }
    
    return undefined;
  }

  /**
   * Flush all logger buffers
   */
  public async flushAll(): Promise<void> {
    const promises = Array.from(this.loggers.values()).map(logger => logger.flushBuffer());
    await Promise.all(promises);
  }
}

/**
 * Default logger instance for convenience
 */
export const logger = LoggerFactory.getInstance().getLogger('app');

/**
 * Convenience function to get component-specific logger
 */
export const getLogger = (component: string): Logger => 
  LoggerFactory.getInstance().getLogger(component);