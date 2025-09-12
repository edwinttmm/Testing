/**
 * Logging Configuration System
 * 
 * Centralized configuration for logging behavior across environments
 * with performance monitoring and feature flags
 */

import { LogLevel, LoggerFactory, RemoteLogConfig } from '../services/logger';

export interface LoggingConfig {
  // Core logging settings
  defaultLevel: LogLevel;
  enabledCategories: string[];
  componentLevels: Record<string, LogLevel>;
  
  // Environment-specific settings
  development: {
    showColors: boolean;
    showTimestamps: boolean;
    showPerformance: boolean;
    bufferSize: number;
  };
  
  production: {
    structuredFormat: boolean;
    errorOnly: boolean;
    enableRemote: boolean;
    bufferSize: number;
  };
  
  // Performance monitoring
  performance: {
    enabled: boolean;
    sampleRate: number; // 0-1, percentage of logs to include performance data
    memoryTracking: boolean;
    slowThreshold: number; // milliseconds
  };
  
  // Feature flags for specific logging categories
  features: {
    apiCalls: boolean;
    userActions: boolean;
    errorBoundaries: boolean;
    performanceMetrics: boolean;
    websocketEvents: boolean;
    routeChanges: boolean;
    componentLifecycle: boolean;
    stateChanges: boolean;
  };
  
  // Remote logging configuration
  remote?: RemoteLogConfig;
  
  // Security and privacy
  privacy: {
    sanitizeUrls: boolean;
    sanitizeUserData: boolean;
    excludeFields: string[];
    hashSensitiveData: boolean;
  };
}

/**
 * Environment detection utility
 */
export class EnvironmentDetector {
  private static _instance: EnvironmentDetector;
  private _environment: 'development' | 'production' | 'test';
  private _debugEnabled: boolean;
  
  private constructor() {
    this._environment = this.detectEnvironment();
    this._debugEnabled = this.detectDebugMode();
  }
  
  public static getInstance(): EnvironmentDetector {
    if (!EnvironmentDetector._instance) {
      EnvironmentDetector._instance = new EnvironmentDetector();
    }
    return EnvironmentDetector._instance;
  }
  
  private detectEnvironment(): 'development' | 'production' | 'test' {
    if (process.env.NODE_ENV === 'test') return 'test';
    if (process.env.NODE_ENV === 'development') return 'development';
    if (process.env.NODE_ENV === 'production') return 'production';
    
    // Fallback detection
    if (typeof window !== 'undefined' && window.location) {
      if (window.location.hostname === 'localhost' || 
          window.location.hostname === '127.0.0.1' ||
          window.location.hostname.startsWith('192.168.')) {
        return 'development';
      }
    }
    
    return 'production';
  }
  
  private detectDebugMode(): boolean {
    // Check various debug indicators
    const envDebug = process.env.REACT_APP_DEBUG === 'true' || process.env.REACT_APP_LOG_LEVEL === 'debug';
    
    if (typeof window !== 'undefined') {
      const urlDebug = window.location?.search?.includes('debug=true') || window.location?.hash?.includes('debug');
      const storageDebug = localStorage?.getItem('debug') === 'true';
      return !!(envDebug || urlDebug || storageDebug);
    }
    
    return !!envDebug;
  }
  
  public get environment() { return this._environment; }
  public get isDebugEnabled() { return this._debugEnabled; }
  public get isDevelopment() { return this._environment === 'development'; }
  public get isProduction() { return this._environment === 'production'; }
  public get isTest() { return this._environment === 'test'; }
}

/**
 * Default logging configuration
 */
export const createLoggingConfig = (): LoggingConfig => {
  const env = EnvironmentDetector.getInstance();
  
  const baseConfig: LoggingConfig = {
    defaultLevel: env.isDevelopment ? LogLevel.DEBUG : LogLevel.WARN,
    enabledCategories: env.isDevelopment ? ['*'] : ['error', 'warn'],
    componentLevels: {
      'api': env.isDevelopment ? LogLevel.DEBUG : LogLevel.ERROR,
      'websocket': env.isDevelopment ? LogLevel.INFO : LogLevel.ERROR,
      'auth': LogLevel.WARN,
      'router': env.isDevelopment ? LogLevel.INFO : LogLevel.ERROR,
      'performance': env.isDevelopment ? LogLevel.DEBUG : LogLevel.NONE,
      'video': env.isDevelopment ? LogLevel.DEBUG : LogLevel.WARN,
      'annotation': env.isDevelopment ? LogLevel.DEBUG : LogLevel.WARN,
      'detection': env.isDevelopment ? LogLevel.INFO : LogLevel.ERROR
    },
    
    development: {
      showColors: true,
      showTimestamps: true,
      showPerformance: true,
      bufferSize: 50
    },
    
    production: {
      structuredFormat: true,
      errorOnly: !env.isDebugEnabled,
      enableRemote: false, // Enable when remote endpoint is configured
      bufferSize: 100
    },
    
    performance: {
      enabled: env.isDevelopment || env.isDebugEnabled,
      sampleRate: env.isDevelopment ? 1.0 : 0.1,
      memoryTracking: env.isDevelopment,
      slowThreshold: 1000 // 1 second
    },
    
    features: {
      apiCalls: env.isDevelopment || env.isDebugEnabled,
      userActions: env.isDevelopment,
      errorBoundaries: true,
      performanceMetrics: env.isDevelopment || env.isDebugEnabled,
      websocketEvents: env.isDevelopment,
      routeChanges: env.isDevelopment,
      componentLifecycle: false, // Only enable for specific debugging
      stateChanges: false // Only enable for specific debugging
    },
    
    privacy: {
      sanitizeUrls: env.isProduction,
      sanitizeUserData: true,
      excludeFields: ['password', 'token', 'secret', 'key', 'auth'],
      hashSensitiveData: env.isProduction
    }
  };
  
  // Override with environment-specific settings
  if (env.isDevelopment) {
    // Development overrides
    baseConfig.defaultLevel = LogLevel.DEBUG;
    baseConfig.enabledCategories = ['*'];
  } else if (env.isProduction) {
    // Production overrides
    if (!env.isDebugEnabled) {
      baseConfig.defaultLevel = LogLevel.ERROR;
      baseConfig.enabledCategories = ['error'];
    }
  }
  
  // Environment variable overrides
  if (process.env.REACT_APP_LOG_LEVEL) {
    const envLevel = process.env.REACT_APP_LOG_LEVEL.toUpperCase();
    if (LogLevel[envLevel as keyof typeof LogLevel] !== undefined) {
      baseConfig.defaultLevel = LogLevel[envLevel as keyof typeof LogLevel];
    }
  }
  
  if (process.env.REACT_APP_LOG_CATEGORIES) {
    baseConfig.enabledCategories = process.env.REACT_APP_LOG_CATEGORIES.split(',').map(c => c.trim());
  }
  
  // Remote logging configuration
  const logEndpoint = process.env.REACT_APP_LOG_ENDPOINT;
  if (logEndpoint) {
    baseConfig.remote = {
      endpoint: logEndpoint,
      ...(process.env.REACT_APP_LOG_API_KEY && { apiKey: process.env.REACT_APP_LOG_API_KEY }),
      batchSize: parseInt(process.env.REACT_APP_LOG_BATCH_SIZE || '10'),
      flushInterval: parseInt(process.env.REACT_APP_LOG_FLUSH_INTERVAL || '30000'),
      enabled: process.env.REACT_APP_LOG_REMOTE_ENABLED === 'true'
    };
    baseConfig.production.enableRemote = baseConfig.remote?.enabled || false;
  }
  
  return baseConfig;
};

/**
 * Configuration manager for logging system
 */
export class LoggingConfigManager {
  private static _instance: LoggingConfigManager;
  private _config: LoggingConfig;
  private _factory: LoggerFactory;
  
  private constructor() {
    this._config = createLoggingConfig();
    this._factory = LoggerFactory.getInstance();
    this.applyConfiguration();
  }
  
  public static getInstance(): LoggingConfigManager {
    if (!LoggingConfigManager._instance) {
      LoggingConfigManager._instance = new LoggingConfigManager();
    }
    return LoggingConfigManager._instance;
  }
  
  /**
   * Apply configuration to logger factory
   */
  private applyConfiguration(): void {
    this._factory.updateConfig({
      minLevel: this._config.defaultLevel,
      enabledCategories: this._config.enabledCategories,
      ...(this._config.remote && { remoteConfig: this._config.remote })
    });
  }
  
  /**
   * Get current configuration
   */
  public getConfig(): LoggingConfig {
    return { ...this._config };
  }
  
  /**
   * Update configuration
   */
  public updateConfig(updates: Partial<LoggingConfig>): void {
    this._config = { ...this._config, ...updates };
    this.applyConfiguration();
  }
  
  /**
   * Check if a feature is enabled
   */
  public isFeatureEnabled(feature: keyof LoggingConfig['features']): boolean {
    return this._config.features[feature];
  }
  
  /**
   * Get log level for specific component
   */
  public getComponentLevel(component: string): LogLevel {
    return this._config.componentLevels[component] || this._config.defaultLevel;
  }
  
  /**
   * Enable/disable performance monitoring
   */
  public setPerformanceMonitoring(enabled: boolean): void {
    this._config.performance.enabled = enabled;
  }
  
  /**
   * Set debug mode dynamically
   */
  public setDebugMode(enabled: boolean): void {
    if (enabled) {
      this._config.defaultLevel = LogLevel.DEBUG;
      this._config.enabledCategories = ['*'];
      this._config.performance.enabled = true;
    } else {
      const env = EnvironmentDetector.getInstance();
      this._config.defaultLevel = env.isDevelopment ? LogLevel.INFO : LogLevel.WARN;
      this._config.enabledCategories = env.isDevelopment ? ['*'] : ['error', 'warn'];
      this._config.performance.enabled = env.isDevelopment;
    }
    this.applyConfiguration();
  }
  
  /**
   * Get performance configuration
   */
  public getPerformanceConfig() {
    return this._config.performance;
  }
  
  /**
   * Should log performance data for this sample
   */
  public shouldLogPerformance(): boolean {
    return this._config.performance.enabled && 
           Math.random() < this._config.performance.sampleRate;
  }
  
  /**
   * Sanitize sensitive data based on privacy settings
   */
  public sanitizeData(data: Record<string, unknown>): Record<string, unknown> {
    if (!this._config.privacy.sanitizeUserData) {
      return data;
    }
    
    const sanitized = { ...data };
    
    for (const field of this._config.privacy.excludeFields) {
      if (sanitized[field]) {
        sanitized[field] = '[REDACTED]';
      }
    }
    
    // Sanitize URLs if enabled
    if (this._config.privacy.sanitizeUrls && sanitized.url) {
      try {
        const url = new URL(String(sanitized.url));
        url.search = ''; // Remove query parameters
        sanitized.url = url.toString();
      } catch {
        sanitized.url = '[INVALID_URL]';
      }
    }
    
    return sanitized;
  }
}

/**
 * Initialize logging system with configuration
 */
export const initializeLogging = (): LoggingConfigManager => {
  const configManager = LoggingConfigManager.getInstance();
  
  // Set up global error handling
  if (typeof window !== 'undefined') {
    window.addEventListener('error', (event) => {
      const logger = LoggerFactory.getInstance().getLogger('global');
      logger.error('Uncaught error', {
        action: 'global_error',
        metadata: {
          message: event.message,
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno
        }
      }, event.error);
    });
    
    window.addEventListener('unhandledrejection', (event) => {
      const logger = LoggerFactory.getInstance().getLogger('global');
      logger.error('Unhandled promise rejection', {
        action: 'promise_rejection',
        metadata: {
          reason: event.reason
        }
      });
    });
  }
  
  return configManager;
};

// Export singleton instances for convenience
export const loggingConfig = LoggingConfigManager.getInstance();
export const environmentDetector = EnvironmentDetector.getInstance();