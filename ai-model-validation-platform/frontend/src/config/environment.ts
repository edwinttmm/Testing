/**
 * Environment Configuration Service
 * Provides centralized configuration management for different environments
 */

export interface EnvironmentConfig {
  environment: 'development' | 'production' | 'test';
  apiUrl: string;
  wsUrl: string;
  socketioUrl: string;
  videoBaseUrl: string;
  debug: boolean;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  enableMockData: boolean;
  enableDebugPanels: boolean;
  enablePerformanceMonitoring: boolean;
  maxVideoSizeMB: number;
  supportedVideoFormats: string[];
  apiTimeout: number;
  wsTimeout: number;
  connectionRetryAttempts: number;
  connectionRetryDelay: number;
  secureCookies?: boolean;
}

class EnvironmentService {
  private config: EnvironmentConfig;

  constructor() {
    this.config = this.loadEnvironmentConfig();
  }

  private loadEnvironmentConfig(): EnvironmentConfig {
    const env = process.env.NODE_ENV || 'development';
    
    // Base configuration
    const baseConfig = {
      environment: env as 'development' | 'production' | 'test',
      debug: process.env.REACT_APP_DEBUG === 'true',
      logLevel: (process.env.REACT_APP_LOG_LEVEL || 'info') as 'debug' | 'info' | 'warn' | 'error',
      enableMockData: process.env.REACT_APP_ENABLE_MOCK_DATA === 'true',
      enableDebugPanels: process.env.REACT_APP_ENABLE_DEBUG_PANELS === 'true',
      enablePerformanceMonitoring: process.env.REACT_APP_ENABLE_PERFORMANCE_MONITORING === 'true',
      maxVideoSizeMB: parseInt(process.env.REACT_APP_MAX_VIDEO_SIZE_MB || '100', 10),
      supportedVideoFormats: (process.env.REACT_APP_SUPPORTED_VIDEO_FORMATS || 'mp4,avi,mov,mkv').split(','),
      apiTimeout: parseInt(process.env.REACT_APP_API_TIMEOUT || '30000', 10),
      wsTimeout: parseInt(process.env.REACT_APP_WS_TIMEOUT || '20000', 10),
      connectionRetryAttempts: parseInt(process.env.REACT_APP_CONNECTION_RETRY_ATTEMPTS || '5', 10),
      connectionRetryDelay: parseInt(process.env.REACT_APP_CONNECTION_RETRY_DELAY || '1000', 10),
    };

    // Environment-specific URLs with fallback logic
    const urls = this.getEnvironmentUrls();

    return {
      ...baseConfig,
      ...urls,
      secureCookies: process.env.REACT_APP_SECURE_COOKIES === 'true',
    };
  }

  private getEnvironmentUrls() {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const isSecure = protocol === 'https:';
    
    // Check for explicit environment variables first
    if (process.env.REACT_APP_API_URL) {
      return {
        apiUrl: process.env.REACT_APP_API_URL,
        wsUrl: process.env.REACT_APP_WS_URL || this.convertToWsUrl(process.env.REACT_APP_API_URL),
        socketioUrl: process.env.REACT_APP_SOCKETIO_URL || process.env.REACT_APP_API_URL,
        videoBaseUrl: process.env.REACT_APP_VIDEO_BASE_URL || process.env.REACT_APP_API_URL,
      };
    }

    // Dynamic URL detection based on current hostname
    const apiPort = this.getApiPort();
    const wsProtocol = isSecure ? 'wss:' : 'ws:';
    const httpProtocol = isSecure ? 'https:' : 'http:';
    
    const apiUrl = `${httpProtocol}//${hostname}:${apiPort}`;
    const wsUrl = `${wsProtocol}//${hostname}:${apiPort}`;
    
    return {
      apiUrl,
      wsUrl,
      socketioUrl: apiUrl,
      videoBaseUrl: apiUrl,
    };
  }

  private getApiPort(): number {
    const hostname = window.location.hostname;
    
    // Production server - update with actual production URL when deployed
    if (hostname === '155.138.239.131' || hostname.includes('production-domain')) {
      return 8000;
    }
    
    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 8000;
    }
    
    // Default port
    return 8000;
  }

  private convertToWsUrl(httpUrl: string): string {
    return httpUrl.replace(/^https?:/, window.location.protocol === 'https:' ? 'wss:' : 'ws:');
  }

  public getConfig(): EnvironmentConfig {
    return { ...this.config };
  }

  public get(key: keyof EnvironmentConfig): any {
    return this.config[key];
  }

  public isDevelopment(): boolean {
    return this.config.environment === 'development';
  }

  public isProduction(): boolean {
    return this.config.environment === 'production';
  }

  public isTest(): boolean {
    return this.config.environment === 'test';
  }

  public getApiUrl(): string {
    return this.config.apiUrl;
  }

  public getWsUrl(): string {
    return this.config.wsUrl;
  }

  public getVideoBaseUrl(): string {
    return this.config.videoBaseUrl;
  }

  public shouldEnableDebug(): boolean {
    return this.config.debug;
  }

  public getLogLevel(): string {
    return this.config.logLevel;
  }

  // Method to log current configuration (for debugging)
  public logConfiguration(): void {
    if (this.config.debug) {
      console.group('🔧 Environment Configuration');
      console.table({
        Environment: this.config.environment,
        'API URL': this.config.apiUrl,
        'WebSocket URL': this.config.wsUrl,
        'Video Base URL': this.config.videoBaseUrl,
        'Debug Mode': this.config.debug,
        'Log Level': this.config.logLevel,
      });
      console.groupEnd();
    }
  }

  // Validate configuration for potential issues
  public validateConfiguration(): { valid: boolean; warnings: string[] } {
    const warnings: string[] = [];
    
    if (!this.config.apiUrl) {
      warnings.push('API URL not configured');
    }
    
    if (!this.config.wsUrl) {
      warnings.push('WebSocket URL not configured');
    }
    
    if (this.config.apiTimeout < 5000) {
      warnings.push('API timeout is very low (< 5 seconds)');
    }
    
    if (this.config.connectionRetryAttempts < 3) {
      warnings.push('Connection retry attempts is low (< 3)');
    }

    return {
      valid: warnings.length === 0,
      warnings
    };
  }
}

// Export singleton instance
export const environmentService = new EnvironmentService();
export default environmentService;

// Initialize and log configuration on import
environmentService.logConfiguration();