/**
 * Environment Configuration Utility
 * 
 * Provides centralized environment configuration management with:
 * - Automatic environment detection
 * - Configuration validation
 * - Fallback handling
 * - Runtime connectivity checks
 */

export type Environment = 'development' | 'production' | 'test';

export interface EnvironmentConfig {
  // Environment identification
  environment: Environment;
  isDevelopment: boolean;
  isProduction: boolean;
  isTest: boolean;
  
  // API Configuration
  apiUrl: string;
  wsUrl: string;
  socketioUrl: string;
  videoBaseUrl: string;
  
  // Feature flags
  debug: boolean;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  enableMockData: boolean;
  enableDebugPanels: boolean;
  enablePerformanceMonitoring: boolean;
  
  // Network configuration
  apiTimeout: number;
  wsTimeout: number;
  connectionRetryAttempts: number;
  connectionRetryDelay: number;
  
  // Video configuration
  maxVideoSizeMB: number;
  supportedVideoFormats: string[];
  
  // Security
  secureCookies: boolean;
}

class EnvironmentConfigManager {
  private config: EnvironmentConfig;
  private validationErrors: string[] = [];
  
  constructor() {
    this.config = this.loadConfiguration();
    this.validateConfiguration();
  }
  
  private loadConfiguration(): EnvironmentConfig {
    // Detect environment
    const nodeEnv = process.env.NODE_ENV || 'development';
    const environment = this.detectEnvironment(nodeEnv);
    
    // Load base configuration
    const config: EnvironmentConfig = {
      // Environment
      environment,
      isDevelopment: environment === 'development',
      isProduction: environment === 'production',
      isTest: environment === 'test',
      
      // API Configuration with smart defaults
      apiUrl: this.getConfigValue('REACT_APP_API_URL', this.getDefaultApiUrl()),
      wsUrl: this.getConfigValue('REACT_APP_WS_URL', this.getDefaultWsUrl()),
      socketioUrl: this.getConfigValue('REACT_APP_SOCKETIO_URL', this.getDefaultSocketioUrl()),
      videoBaseUrl: this.getConfigValue('REACT_APP_VIDEO_BASE_URL', this.getDefaultVideoBaseUrl()),
      
      // Feature flags
      debug: this.getBooleanConfig('REACT_APP_DEBUG', environment === 'development'),
      logLevel: this.getConfigValue('REACT_APP_LOG_LEVEL', environment === 'production' ? 'error' : 'debug') as any,
      enableMockData: this.getBooleanConfig('REACT_APP_ENABLE_MOCK_DATA', false),
      enableDebugPanels: this.getBooleanConfig('REACT_APP_ENABLE_DEBUG_PANELS', environment === 'development'),
      enablePerformanceMonitoring: this.getBooleanConfig('REACT_APP_ENABLE_PERFORMANCE_MONITORING', true),
      
      // Network configuration
      apiTimeout: this.getNumberConfig('REACT_APP_API_TIMEOUT', environment === 'production' ? 45000 : 30000),
      wsTimeout: this.getNumberConfig('REACT_APP_WS_TIMEOUT', environment === 'production' ? 30000 : 20000),
      connectionRetryAttempts: this.getNumberConfig('REACT_APP_CONNECTION_RETRY_ATTEMPTS', environment === 'production' ? 10 : 5),
      connectionRetryDelay: this.getNumberConfig('REACT_APP_CONNECTION_RETRY_DELAY', environment === 'production' ? 2000 : 1000),
      
      // Video configuration
      maxVideoSizeMB: this.getNumberConfig('REACT_APP_MAX_VIDEO_SIZE_MB', environment === 'production' ? 500 : 100),
      supportedVideoFormats: this.getArrayConfig('REACT_APP_SUPPORTED_VIDEO_FORMATS', ['mp4', 'avi', 'mov', 'mkv']),
      
      // Security
      secureCookies: this.getBooleanConfig('REACT_APP_SECURE_COOKIES', environment === 'production'),
    };
    
    if (config.debug) {
      console.log('🔧 Environment Configuration Loaded:', {
        environment: config.environment,
        apiUrl: config.apiUrl,
        wsUrl: config.wsUrl,
        socketioUrl: config.socketioUrl,
        videoBaseUrl: config.videoBaseUrl,
        debug: config.debug
      });
    }
    
    return config;
  }
  
  private detectEnvironment(nodeEnv: string): Environment {
    // Check explicit environment override
    const explicitEnv = process.env.REACT_APP_ENVIRONMENT;
    if (explicitEnv && ['development', 'production', 'test'].includes(explicitEnv)) {
      return explicitEnv as Environment;
    }
    
    // Map NODE_ENV to our environment types
    switch (nodeEnv) {
      case 'production':
        return 'production';
      case 'test':
        return 'test';
      case 'development':
      default:
        return 'development';
    }
  }
  
  private getDefaultApiUrl(): string {
    // Smart default based on current location
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      const protocol = window.location.protocol;
      
      // Handle specific production server
      if (hostname === '155.138.239.131') {
        return 'http://155.138.239.131:8000';
      }
      
      // Handle local development
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8000';
      }
      
      // Generic fallback
      return `${protocol}//${hostname}:8000`;
    }
    
    // Server-side rendering fallback
    return 'http://localhost:8000';
  }
  
  private getDefaultWsUrl(): string {
    const apiUrl = this.getDefaultApiUrl();
    return apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  }
  
  private getDefaultSocketioUrl(): string {
    const apiUrl = this.getDefaultApiUrl();
    return apiUrl.replace(':8000', ':8001');
  }
  
  private getDefaultVideoBaseUrl(): string {
    return this.getDefaultApiUrl();
  }
  
  private getConfigValue(key: string, defaultValue: string): string {
    const value = process.env[key];
    return value || defaultValue;
  }
  
  private getBooleanConfig(key: string, defaultValue: boolean): boolean {
    const value = process.env[key];
    if (value === undefined) return defaultValue;
    return value.toLowerCase() === 'true';
  }
  
  private getNumberConfig(key: string, defaultValue: number): number {
    const value = process.env[key];
    if (value === undefined) return defaultValue;
    const parsed = parseInt(value, 10);
    return isNaN(parsed) ? defaultValue : parsed;
  }
  
  private getArrayConfig(key: string, defaultValue: string[]): string[] {
    const value = process.env[key];
    if (!value) return defaultValue;
    return value.split(',').map(item => item.trim()).filter(Boolean);
  }
  
  private validateConfiguration(): void {
    this.validationErrors = [];
    
    // Validate required URLs
    if (!this.isValidUrl(this.config.apiUrl)) {
      this.validationErrors.push(`Invalid API URL: ${this.config.apiUrl}`);
    }
    
    if (!this.isValidWebSocketUrl(this.config.wsUrl)) {
      this.validationErrors.push(`Invalid WebSocket URL: ${this.config.wsUrl}`);
    }
    
    if (!this.isValidUrl(this.config.socketioUrl)) {
      this.validationErrors.push(`Invalid Socket.IO URL: ${this.config.socketioUrl}`);
    }
    
    if (!this.isValidUrl(this.config.videoBaseUrl)) {
      this.validationErrors.push(`Invalid Video Base URL: ${this.config.videoBaseUrl}`);
    }
    
    // Validate timeouts
    if (this.config.apiTimeout < 1000) {
      this.validationErrors.push(`API timeout too low: ${this.config.apiTimeout}ms (minimum 1000ms)`);
    }
    
    if (this.config.wsTimeout < 1000) {
      this.validationErrors.push(`WebSocket timeout too low: ${this.config.wsTimeout}ms (minimum 1000ms)`);
    }
    
    // Validate retry configuration
    if (this.config.connectionRetryAttempts < 1 || this.config.connectionRetryAttempts > 50) {
      this.validationErrors.push(`Invalid retry attempts: ${this.config.connectionRetryAttempts} (must be 1-50)`);
    }
    
    if (this.config.connectionRetryDelay < 100) {
      this.validationErrors.push(`Retry delay too low: ${this.config.connectionRetryDelay}ms (minimum 100ms)`);
    }
    
    // Validate video configuration
    if (this.config.maxVideoSizeMB < 1 || this.config.maxVideoSizeMB > 2000) {
      this.validationErrors.push(`Invalid max video size: ${this.config.maxVideoSizeMB}MB (must be 1-2000MB)`);
    }
    
    if (this.config.supportedVideoFormats.length === 0) {
      this.validationErrors.push('No supported video formats configured');
    }
    
    // Log validation results
    if (this.validationErrors.length > 0) {
      console.error('❌ Environment Configuration Validation Errors:', this.validationErrors);
    } else if (this.config.debug) {
      console.log('✅ Environment Configuration Validated Successfully');
    }
  }
  
  private isValidUrl(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }
  
  private isValidWebSocketUrl(url: string): boolean {
    return url.startsWith('ws://') || url.startsWith('wss://') || this.isValidUrl(url);
  }
  
  /**
   * Get the current environment configuration
   */
  getConfig(): EnvironmentConfig {
    return { ...this.config };
  }
  
  /**
   * Get validation errors
   */
  getValidationErrors(): string[] {
    return [...this.validationErrors];
  }
  
  /**
   * Check if configuration is valid
   */
  isValid(): boolean {
    return this.validationErrors.length === 0;
  }
  
  /**
   * Test API connectivity
   */
  async testApiConnectivity(): Promise<{connected: boolean, error?: string, latency?: number}> {
    const startTime = Date.now();
    
    try {
      const response = await fetch(`${this.config.apiUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(10000), // 10 second timeout for health check
        headers: {
          'Accept': 'application/json'
        }
      });
      
      const latency = Date.now() - startTime;
      
      if (response.ok) {
        if (this.config.debug) {
          console.log(`✅ API connectivity test passed (${latency}ms)`);
        }
        return { connected: true, latency };
      } else {
        const error = `HTTP ${response.status}: ${response.statusText}`;
        console.warn(`⚠️ API connectivity test failed: ${error}`);
        return { connected: false, error, latency };
      }
      
    } catch (error: any) {
      const latency = Date.now() - startTime;
      const errorMessage = error.message || 'Unknown connection error';
      console.error('❌ API connectivity test failed:', errorMessage);
      return { connected: false, error: errorMessage, latency };
    }
  }
  
  /**
   * Get environment-specific configuration for a service
   */
  getServiceConfig(service: 'api' | 'websocket' | 'socketio' | 'video') {
    switch (service) {
      case 'api':
        return {
          url: this.config.apiUrl,
          timeout: this.config.apiTimeout,
          retryAttempts: this.config.connectionRetryAttempts,
          retryDelay: this.config.connectionRetryDelay
        };
      
      case 'websocket':
        return {
          url: this.config.wsUrl,
          timeout: this.config.wsTimeout,
          retryAttempts: this.config.connectionRetryAttempts,
          retryDelay: this.config.connectionRetryDelay
        };
      
      case 'socketio':
        return {
          url: this.config.socketioUrl,
          timeout: this.config.wsTimeout,
          retryAttempts: this.config.connectionRetryAttempts,
          retryDelay: this.config.connectionRetryDelay
        };
      
      case 'video':
        return {
          baseUrl: this.config.videoBaseUrl,
          maxSizeMB: this.config.maxVideoSizeMB,
          supportedFormats: this.config.supportedVideoFormats
        };
      
      default:
        throw new Error(`Unknown service: ${service}`);
    }
  }
  
  /**
   * Reload configuration (useful for testing)
   */
  reload(): void {
    this.config = this.loadConfiguration();
    this.validateConfiguration();
  }
}

// Export singleton instance
export const envConfig = new EnvironmentConfigManager();

// Export individual functions for convenience
export const getConfig = () => envConfig.getConfig();
export const isValidConfig = () => envConfig.isValid();
export const getValidationErrors = () => envConfig.getValidationErrors();
export const testApiConnectivity = () => envConfig.testApiConnectivity();
export const getServiceConfig = (service: Parameters<typeof envConfig.getServiceConfig>[0]) => 
  envConfig.getServiceConfig(service);

// Export environment checks
export const isDevelopment = () => envConfig.getConfig().isDevelopment;
export const isProduction = () => envConfig.getConfig().isProduction;
export const isDebugEnabled = () => envConfig.getConfig().debug;

export default envConfig;