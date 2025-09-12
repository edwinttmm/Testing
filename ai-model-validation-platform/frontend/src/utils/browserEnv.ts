/**
 * Browser-Compatible Environment Variable Access
 * 
 * This module provides safe access to environment variables in browser environments
 * where process.env is not available. It uses webpack's DefinePlugin injected variables.
 * 
 * CRITICAL FIX FOR: "process is not defined" errors in browser
 */

/**
 * Browser-safe environment variable accessor
 * In React applications, webpack DefinePlugin replaces process.env.VARIABLE_NAME 
 * with actual string values at build time, so we can safely access them.
 */
class BrowserEnvironment {
  private cache = new Map<string, string>();
  
  /**
   * Get environment variable value with fallback
   * This method safely accesses webpack-injected environment variables
   */
  get(key: string, defaultValue: string = ''): string {
    // Check cache first
    if (this.cache.has(key)) {
      return this.cache.get(key)!;
    }

    let value: string;

    try {
      // In browser, webpack DefinePlugin will have replaced these with actual values
      // We use a switch statement to allow webpack to properly replace these at build time
      switch (key) {
        case 'NODE_ENV':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.NODE_ENV || 'development';
          break;
        case 'REACT_APP_API_URL':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_URL || '';
          break;
        case 'REACT_APP_WS_URL':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_WS_URL || '';
          break;
        case 'REACT_APP_SOCKETIO_URL':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_SOCKETIO_URL || '';
          break;
        case 'REACT_APP_VIDEO_BASE_URL':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_VIDEO_BASE_URL || '';
          break;
        case 'REACT_APP_ENVIRONMENT':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_ENVIRONMENT || '';
          break;
        case 'REACT_APP_DEBUG':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_DEBUG || '';
          break;
        case 'REACT_APP_LOG_LEVEL':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_LOG_LEVEL || '';
          break;
        case 'REACT_APP_ENABLE_MOCK_DATA':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_ENABLE_MOCK_DATA || '';
          break;
        case 'REACT_APP_ENABLE_DEBUG_PANELS':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_ENABLE_DEBUG_PANELS || '';
          break;
        case 'REACT_APP_ENABLE_PERFORMANCE_MONITORING':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_ENABLE_PERFORMANCE_MONITORING || '';
          break;
        case 'REACT_APP_DISABLE_WEBSOCKET':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_DISABLE_WEBSOCKET || '';
          break;
        case 'REACT_APP_DISABLE_SOCKETIO':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_DISABLE_SOCKETIO || '';
          break;
        case 'REACT_APP_WEBSOCKET_HEALTH_CHECK':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_WEBSOCKET_HEALTH_CHECK || '';
          break;
        case 'REACT_APP_API_TIMEOUT':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_TIMEOUT || '';
          break;
        case 'REACT_APP_WS_TIMEOUT':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_WS_TIMEOUT || '';
          break;
        case 'REACT_APP_CONNECTION_RETRY_ATTEMPTS':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_CONNECTION_RETRY_ATTEMPTS || '';
          break;
        case 'REACT_APP_CONNECTION_RETRY_DELAY':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_CONNECTION_RETRY_DELAY || '';
          break;
        case 'REACT_APP_MAX_VIDEO_SIZE_MB':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_MAX_VIDEO_SIZE_MB || '';
          break;
        case 'REACT_APP_SUPPORTED_VIDEO_FORMATS':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_SUPPORTED_VIDEO_FORMATS || '';
          break;
        case 'REACT_APP_SECURE_COOKIES':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.REACT_APP_SECURE_COOKIES || '';
          break;
        case 'DOCKER':
          // @ts-ignore - webpack will replace this at build time
          value = typeof process !== 'undefined' && process.env && process.env.DOCKER || '';
          break;
        default:
          value = defaultValue;
      }
    } catch (error) {
      // Fallback for any errors accessing environment variables
      console.warn(`Failed to access environment variable ${key}:`, error);
      value = defaultValue;
    }

    // Use provided default if value is empty
    if (!value) {
      value = defaultValue;
    }

    // Cache the result
    this.cache.set(key, value);
    
    return value;
  }

  /**
   * Get boolean environment variable
   */
  getBoolean(key: string, defaultValue: boolean = false): boolean {
    const value = this.get(key, '').toLowerCase();
    if (value === '') return defaultValue;
    return value === 'true' || value === '1' || value === 'yes';
  }

  /**
   * Get number environment variable
   */
  getNumber(key: string, defaultValue: number = 0): number {
    const value = this.get(key, '');
    if (value === '') return defaultValue;
    const parsed = parseInt(value, 10);
    return isNaN(parsed) ? defaultValue : parsed;
  }

  /**
   * Get array environment variable (comma-separated)
   */
  getArray(key: string, defaultValue: string[] = []): string[] {
    const value = this.get(key, '');
    if (value === '') return defaultValue;
    return value.split(',').map(item => item.trim()).filter(Boolean);
  }

  /**
   * Check if running in browser environment
   */
  isBrowser(): boolean {
    return typeof window !== 'undefined' && typeof document !== 'undefined';
  }

  /**
   * Check if running in Node.js environment
   */
  isNode(): boolean {
    return typeof process !== 'undefined' && process.versions && !!process.versions.node;
  }

  /**
   * Get current environment (development, production, test)
   */
  getEnvironment(): 'development' | 'production' | 'test' {
    const nodeEnv = this.get('NODE_ENV', 'development');
    const explicitEnv = this.get('REACT_APP_ENVIRONMENT', '');
    
    // Use explicit environment if set
    if (explicitEnv && ['development', 'production', 'test'].includes(explicitEnv)) {
      return explicitEnv as 'development' | 'production' | 'test';
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

  /**
   * Clear environment variable cache
   */
  clearCache(): void {
    this.cache.clear();
  }
}

// Export singleton instance
export const browserEnv = new BrowserEnvironment();

// Export convenience functions for backward compatibility
export const getEnv = (key: string, defaultValue: string = '') => browserEnv.get(key, defaultValue);
export const getBooleanEnv = (key: string, defaultValue: boolean = false) => browserEnv.getBoolean(key, defaultValue);
export const getNumberEnv = (key: string, defaultValue: number = 0) => browserEnv.getNumber(key, defaultValue);
export const getArrayEnv = (key: string, defaultValue: string[] = []) => browserEnv.getArray(key, defaultValue);
export const isBrowser = () => browserEnv.isBrowser();
export const isNode = () => browserEnv.isNode();
export const getCurrentEnvironment = () => browserEnv.getEnvironment();

export default browserEnv;