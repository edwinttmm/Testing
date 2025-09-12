/**
 * Unified Configuration Manager
 * Implements 4-tier configuration hierarchy: runtime > env > files > defaults
 * Part of the Unified Configuration Architecture
 */

import { Environment, environmentDetector } from './services/EnvironmentDetector';

export interface ConfigSchema {
  environment: Environment;
  api: {
    baseURL: string;
    websocketURL: string;
    socketioURL: string;
    timeout: number;
    retries: number;
  };
  cors: {
    origins: string[];
    credentials: boolean;
    methods: string[];
    headers: string[];
  };
  features: {
    debugging: boolean;
    analytics: boolean;
    monitoring: boolean;
    caching: boolean;
    compression: boolean;
  };
  security: {
    ssl: boolean;
    headers: Record<string, string>;
    csp: boolean;
    hsts: boolean;
  };
  performance: {
    cacheTimeout: number;
    requestTimeout: number;
    maxRetries: number;
    batchSize: number;
  };
  logging: {
    level: 'debug' | 'info' | 'warn' | 'error';
    structured: boolean;
    console: boolean;
    file?: string;
  };
}

export interface ConfigHierarchy {
  defaults: Partial<ConfigSchema>;
  fileConfig: Partial<ConfigSchema>;
  envVars: Partial<ConfigSchema>;
  runtime: Partial<ConfigSchema>;
}

export class ConfigManager {
  private static instance: ConfigManager;
  private config: ConfigSchema | null = null;
  private cache = new Map<string, any>();
  private watchers: Array<(config: ConfigSchema) => void> = [];
  private validationErrors: string[] = [];
  
  static getInstance(): ConfigManager {
    if (!this.instance) {
      this.instance = new ConfigManager();
    }
    return this.instance;
  }

  /**
   * Initialize configuration with full hierarchy detection and merging
   */
  async initialize(): Promise<ConfigSchema> {
    if (this.config) return this.config;

    logger.info('Initializing unified configuration system...');

    try {
      // Step 1: Detect environment
      logger.info('Step 1: Environment detection');
      const environment = await environmentDetector.detectEnvironment();

      // Step 2: Load configuration hierarchy
      logger.info('Step 2: Loading configuration hierarchy');
      const hierarchy = await this.loadConfigurationHierarchy(environment);

      // Step 3: Merge configuration with priority
      logger.info('Step 3: Merging configuration hierarchy');
      this.config = this.mergeConfiguration(hierarchy, environment);

      // Step 4: Validate configuration
      logger.info('Step 4: Validating configuration');
      await this.validateConfiguration(this.config);

      // Step 5: Cache and notify watchers
      logger.info('Step 5: Caching and notifications');
      this.cacheConfiguration(this.config);
      this.notifyWatchers(this.config);

      logger.info('Configuration system initialized successfully');
      this.logConfigurationSummary(this.config);

      return this.config;
    } catch (error) {
      logger.error('Configuration initialization failed:', error);
      throw new Error(`Configuration initialization failed: ${error.message}`);
    }
  }

  /**
   * Load configuration from all hierarchy levels
   */
  private async loadConfigurationHierarchy(env: Environment): Promise<ConfigHierarchy> {
    const [defaults, fileConfig, envVars, runtime] = await Promise.all([
      this.loadDefaults(env),
      this.loadConfigFiles(env),
      this.loadEnvironmentVariables(),
      this.loadRuntimeOverrides()
    ]);

    return { defaults, fileConfig, envVars, runtime };
  }

  /**
   * Load default configuration values
   */
  private async loadDefaults(env: Environment): Promise<Partial<ConfigSchema>> {
    const isProduction = env.type === 'production';
    
    return {
      api: {
        timeout: isProduction ? 30000 : 10000,
        retries: isProduction ? 3 : 1
      },
      cors: {
        credentials: true,
        methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        headers: ['*']
      },
      features: {
        debugging: !isProduction,
        analytics: isProduction,
        monitoring: isProduction,
        caching: true,
        compression: isProduction
      },
      security: {
        ssl: isProduction,
        csp: isProduction,
        hsts: isProduction,
        headers: this.getDefaultSecurityHeaders(isProduction)
      },
      performance: {
        cacheTimeout: 300000, // 5 minutes
        requestTimeout: 30000,
        maxRetries: 3,
        batchSize: 50
      },
      logging: {
        level: isProduction ? 'info' : 'debug',
        structured: isProduction,
        console: true
      }
    };
  }

  /**
   * Load configuration from files
   */
  private async loadConfigFiles(env: Environment): Promise<Partial<ConfigSchema>> {
    try {
      const configPaths = [
        `/config/${env.type}.json`,
        `/config/${env.platform}.json`,
        '/config/app.json',
        './config.json'
      ];

      for (const path of configPaths) {
        try {
          const config = await this.loadConfigFile(path);
          if (config) {
            logger.info(`Loaded configuration from: ${path}`);
            return config;
          }
        } catch (error) {
          // Silently continue to next file
        }
      }

      logger.info('No configuration files found, using defaults');
      return {};
    } catch (error) {
      logger.warn('Error loading configuration files:', error.message);
      return {};
    }
  }

  /**
   * Load single configuration file
   */
  private async loadConfigFile(path: string): Promise<Partial<ConfigSchema> | null> {
    if (typeof window !== 'undefined') {
      // Browser environment - fetch from public folder
      try {
        const response = await fetch(path);
        if (response.ok) {
          return await response.json();
        }
      } catch {
        return null;
      }
    } else {
      // Node.js environment - read from filesystem
      try {
        const fs = await import('fs/promises');
        const content = await fs.readFile(path, 'utf-8');
        return JSON.parse(content);
      } catch {
        return null;
      }
    }
    return null;
  }

  /**
   * Load configuration from environment variables
   */
  private loadEnvironmentVariables(): Partial<ConfigSchema> {
    const envConfig: Partial<ConfigSchema> = {};

    // API configuration
    if (process.env.REACT_APP_API_URL || process.env.API_URL) {
      envConfig.api = {
        ...envConfig.api,
        baseURL: process.env.REACT_APP_API_URL || process.env.API_URL
      };
    }

    if (process.env.REACT_APP_WS_URL || process.env.WS_URL) {
      envConfig.api = {
        ...envConfig.api,
        websocketURL: process.env.REACT_APP_WS_URL || process.env.WS_URL
      };
    }

    if (process.env.REACT_APP_SOCKETIO_URL || process.env.SOCKETIO_URL) {
      envConfig.api = {
        ...envConfig.api,
        socketioURL: process.env.REACT_APP_SOCKETIO_URL || process.env.SOCKETIO_URL
      };
    }

    // CORS configuration
    const corsOrigins = process.env.CORS_ORIGINS || process.env.ALLOWED_ORIGINS;
    if (corsOrigins) {
      envConfig.cors = {
        ...envConfig.cors,
        origins: this.parseCORSOrigins(corsOrigins)
      };
    }

    // Feature flags
    const features: Partial<ConfigSchema['features']> = {};
    if (process.env.REACT_APP_DEBUG !== undefined) {
      features.debugging = process.env.REACT_APP_DEBUG === 'true';
    }
    if (process.env.REACT_APP_ANALYTICS !== undefined) {
      features.analytics = process.env.REACT_APP_ANALYTICS === 'true';
    }
    if (process.env.REACT_APP_MONITORING !== undefined) {
      features.monitoring = process.env.REACT_APP_MONITORING === 'true';
    }
    if (Object.keys(features).length > 0) {
      envConfig.features = features;
    }

    // Security configuration
    const security: Partial<ConfigSchema['security']> = {};
    if (process.env.SSL_ENABLED !== undefined) {
      security.ssl = process.env.SSL_ENABLED === 'true';
    }
    if (Object.keys(security).length > 0) {
      envConfig.security = security;
    }

    // Logging configuration
    const logging: Partial<ConfigSchema['logging']> = {};
    if (process.env.LOG_LEVEL) {
      logging.level = process.env.LOG_LEVEL.toLowerCase() as any;
    }
    if (process.env.LOG_FILE) {
      logging.file = process.env.LOG_FILE;
    }
    if (Object.keys(logging).length > 0) {
      envConfig.logging = logging;
    }

    return envConfig;
  }

  /**
   * Load runtime configuration overrides
   */
  private loadRuntimeOverrides(): Partial<ConfigSchema> {
    try {
      // Browser environment - check window.RUNTIME_CONFIG
      if (typeof window !== 'undefined') {
        const runtimeConfig = (window as any).RUNTIME_CONFIG;
        if (runtimeConfig) {
          logger.info('Runtime configuration overrides detected');
          return this.convertRuntimeConfig(runtimeConfig);
        }
      }

      // Node.js environment - check for runtime config file
      return {};
    } catch (error) {
      logger.warn('Error loading runtime overrides:', error.message);
      return {};
    }
  }

  /**
   * Convert runtime config format to ConfigSchema format
   */
  private convertRuntimeConfig(runtimeConfig: any): Partial<ConfigSchema> {
    const config: Partial<ConfigSchema> = {};

    if (runtimeConfig.REACT_APP_API_URL) {
      config.api = { ...config.api, baseURL: runtimeConfig.REACT_APP_API_URL };
    }
    if (runtimeConfig.REACT_APP_WS_URL) {
      config.api = { ...config.api, websocketURL: runtimeConfig.REACT_APP_WS_URL };
    }
    if (runtimeConfig.REACT_APP_SOCKETIO_URL) {
      config.api = { ...config.api, socketioURL: runtimeConfig.REACT_APP_SOCKETIO_URL };
    }

    return config;
  }

  /**
   * Merge configuration hierarchy with priority: runtime > env > file > defaults
   */
  private mergeConfiguration(hierarchy: ConfigHierarchy, environment: Environment): ConfigSchema {
    const { defaults, fileConfig, envVars, runtime } = hierarchy;

    // Deep merge configuration levels
    const baseConfig = this.deepMerge([
      defaults,
      fileConfig,
      envVars,
      runtime
    ]);

    // Generate dynamic configuration based on environment
    const dynamicConfig = this.generateDynamicConfig(environment, baseConfig);

    // Final merge including environment
    return {
      ...baseConfig,
      ...dynamicConfig,
      environment
    } as ConfigSchema;
  }

  /**
   * Generate dynamic configuration based on detected environment
   */
  private generateDynamicConfig(env: Environment, base: any): Partial<ConfigSchema> {
    const { network, type, platform } = env;
    
    // Generate API URLs based on detected environment
    const protocol = env.features.ssl ? 'https' : 'http';
    const wsProtocol = env.features.ssl ? 'wss' : 'ws';
    const host = network.externalIP || network.internalIP;

    return {
      api: {
        baseURL: base.api?.baseURL || `${protocol}://${host}:${network.ports.backend}`,
        websocketURL: base.api?.websocketURL || `${wsProtocol}://${host}:${network.ports.websocket}`,
        socketioURL: base.api?.socketioURL || `${protocol}://${host}:${network.ports.socketio}`,
        timeout: base.api?.timeout || (type === 'production' ? 30000 : 10000),
        retries: base.api?.retries || (type === 'production' ? 3 : 1)
      },
      cors: {
        origins: this.generateCORSOrigins(env, base.cors?.origins || []),
        credentials: base.cors?.credentials ?? true,
        methods: base.cors?.methods || ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        headers: base.cors?.headers || ['*']
      }
    };
  }

  /**
   * Generate CORS origins based on detected environment
   */
  private generateCORSOrigins(env: Environment, configuredOrigins: string[]): string[] {
    const origins = new Set(configuredOrigins);
    const { network, type } = env;
    
    // Always include localhost for development
    if (type === 'development') {
      origins.add('http://localhost:3000');
      origins.add('http://127.0.0.1:3000');
    }

    // Add detected IP origins
    const protocol = env.features.ssl ? 'https' : 'http';
    
    if (network.externalIP) {
      origins.add(`${protocol}://${network.externalIP}:${network.ports.frontend}`);
    }
    
    if (network.internalIP && network.internalIP !== network.externalIP) {
      origins.add(`${protocol}://${network.internalIP}:${network.ports.frontend}`);
    }

    return [...origins].filter(origin => origin && origin !== 'http://' && origin !== 'https://');
  }

  /**
   * Parse CORS origins from environment variable
   */
  private parseCORSOrigins(corsString: string): string[] {
    try {
      // Try parsing as JSON array first
      if (corsString.startsWith('[') && corsString.endsWith(']')) {
        return JSON.parse(corsString);
      }
      
      // Parse as comma-separated string
      return corsString.split(',')
        .map(origin => origin.trim())
        .filter(origin => origin);
    } catch (error) {
      logger.warn('Error parsing CORS origins:', error.message);
      return [corsString];
    }
  }

  /**
   * Deep merge multiple configuration objects
   */
  private deepMerge(objects: Array<Partial<ConfigSchema>>): Partial<ConfigSchema> {
    const result: any = {};
    
    for (const obj of objects) {
      if (!obj) continue;
      
      for (const [key, value] of Object.entries(obj)) {
        if (value === null || value === undefined) continue;
        
        if (typeof value === 'object' && !Array.isArray(value)) {
          result[key] = this.deepMerge([result[key] || {}, value]);
        } else {
          result[key] = value;
        }
      }
    }
    
    return result;
  }

  /**
   * Get default security headers
   */
  private getDefaultSecurityHeaders(isProduction: boolean): Record<string, string> {
    const headers: Record<string, string> = {
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'X-XSS-Protection': '1; mode=block'
    };

    if (isProduction) {
      headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains';
      headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';";
    }

    return headers;
  }

  /**
   * Validate configuration integrity
   */
  private async validateConfiguration(config: ConfigSchema): Promise<void> {
    this.validationErrors = [];

    // Validate API URLs
    this.validateURL(config.api.baseURL, 'API Base URL');
    this.validateWebSocketURL(config.api.websocketURL, 'WebSocket URL');
    this.validateURL(config.api.socketioURL, 'SocketIO URL');

    // Validate CORS configuration
    this.validateCORSConfiguration(config.cors);

    // Validate environment-specific requirements
    this.validateEnvironmentRequirements(config);

    // Test API connectivity (optional, non-blocking)
    this.testAPIConnectivity(config.api.baseURL).catch(error => {
      console.warn('⚠️ API connectivity test failed:', error.message);
    });

    if (this.validationErrors.length > 0) {
      logger.warn('Configuration validation warnings:', this.validationErrors);
    }
  }

  /**
   * Validate URL format
   */
  private validateURL(url: string, name: string): void {
    try {
      new URL(url);
    } catch (error) {
      this.validationErrors.push(`Invalid ${name}: ${url}`);
    }
  }

  /**
   * Validate WebSocket URL format
   */
  private validateWebSocketURL(url: string, name: string): void {
    if (!url.startsWith('ws://') && !url.startsWith('wss://')) {
      this.validationErrors.push(`Invalid ${name} protocol: ${url} (must start with ws:// or wss://)`);
    }
  }

  /**
   * Validate CORS configuration
   */
  private validateCORSConfiguration(cors: ConfigSchema['cors']): void {
    if (cors.origins.length === 0) {
      this.validationErrors.push('CORS origins list is empty - this may block frontend requests');
    }

    // Check for wildcard in production
    if (cors.origins.includes('*')) {
      this.validationErrors.push('CORS wildcard (*) detected - not recommended for production');
    }

    // Validate origin formats
    cors.origins.forEach(origin => {
      try {
        new URL(origin);
      } catch {
        this.validationErrors.push(`Invalid CORS origin URL: ${origin}`);
      }
    });
  }

  /**
   * Validate environment-specific requirements
   */
  private validateEnvironmentRequirements(config: ConfigSchema): void {
    const { environment, security } = config;

    if (environment.type === 'production') {
      if (!security.ssl) {
        this.validationErrors.push('SSL not enabled in production environment');
      }

      if (config.features.debugging) {
        this.validationErrors.push('Debug mode enabled in production');
      }
    }
  }

  /**
   * Test API connectivity
   */
  private async testAPIConnectivity(baseURL: string): Promise<void> {
    try {
      const response = await fetch(`${baseURL}/health`, {
        method: 'GET',
        timeout: 5000
      });

      if (response.ok) {
        logger.info('API connectivity test passed');
      } else {
        logger.warn(`API health check returned status: ${response.status}`);
      }
    } catch (error) {
      throw new Error(`API connectivity test failed: ${error.message}`);
    }
  }

  /**
   * Cache configuration
   */
  private cacheConfiguration(config: ConfigSchema): void {
    this.cache.set('current_config', config);
    this.cache.set('config_timestamp', Date.now());
  }

  /**
   * Notify configuration watchers
   */
  private notifyWatchers(config: ConfigSchema): void {
    this.watchers.forEach(watcher => {
      try {
        watcher(config);
      } catch (error) {
        logger.error('Configuration watcher error:', error);
      }
    });
  }

  /**
   * Log configuration summary
   */
  private logConfigurationSummary(config: ConfigSchema): void {
    logger.info('Configuration Summary:', {
      environment: config.environment.type,
      platform: config.environment.platform,
      apiBaseUrl: config.api.baseURL,
      websocketUrl: config.api.websocketURL,
      socketioUrl: config.api.socketioURL,
      corsOrigins: config.cors.origins.length,
      sslEnabled: config.security.ssl,
      debugMode: config.features.debugging
    });
  }

  // Public API methods

  /**
   * Get current configuration
   */
  getConfig(): ConfigSchema {
    if (!this.config) {
      throw new Error('Configuration not initialized. Call initialize() first.');
    }
    return this.config;
  }

  /**
   * Watch for configuration changes
   */
  watchConfig(callback: (config: ConfigSchema) => void): () => void {
    this.watchers.push(callback);
    
    // Return unwatch function
    return () => {
      const index = this.watchers.indexOf(callback);
      if (index > -1) {
        this.watchers.splice(index, 1);
      }
    };
  }

  /**
   * Force configuration refresh
   */
  async refresh(): Promise<ConfigSchema> {
    this.config = null;
    this.cache.clear();
    return this.initialize();
  }

  /**
   * Get configuration validation errors
   */
  getValidationErrors(): string[] {
    return [...this.validationErrors];
  }
}

// Export singleton instance
export const configManager = ConfigManager.getInstance();