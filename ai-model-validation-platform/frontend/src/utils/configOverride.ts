/**
 * Configuration Override System
 * This ensures runtime configuration takes precedence over compile-time settings
 */

export interface RuntimeConfig {
  REACT_APP_API_URL: string;
  REACT_APP_WS_URL: string;
  REACT_APP_SOCKETIO_URL: string;
  REACT_APP_VIDEO_BASE_URL: string;
  REACT_APP_ENVIRONMENT?: string;
}

/**
 * Get configuration value with runtime override support
 */
export function getConfigValue(key: keyof RuntimeConfig, fallback: string): string {
  // Check runtime config first (from window.RUNTIME_CONFIG)
  if (typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG) {
    const runtimeValue = (window as any).RUNTIME_CONFIG[key];
    if (runtimeValue) {
      console.log(`🔧 Using runtime config for ${key}:`, runtimeValue);
      return runtimeValue;
    }
  }
  
  // Check environment variables
  const envValue = process.env[key];
  if (envValue) {
    console.log(`🔧 Using environment config for ${key}:`, envValue);
    return envValue;
  }
  
  // Use fallback
  console.log(`🔧 Using fallback config for ${key}:`, fallback);
  return fallback;
}

/**
 * Force override process.env with runtime config
 */
export function applyRuntimeConfigOverrides(): void {
  if (typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG) {
    const runtimeConfig = (window as any).RUNTIME_CONFIG;
    console.log('🔧 Applying runtime configuration overrides:', runtimeConfig);
    
    // Override process.env
    Object.keys(runtimeConfig).forEach(key => {
      process.env[key] = runtimeConfig[key];
    });
  }
}

/**
 * Get all configuration with overrides applied
 */
export function getFullConfig(): RuntimeConfig {
  return {
    REACT_APP_API_URL: getConfigValue('REACT_APP_API_URL', 'http://155.138.239.131:8000'),
    REACT_APP_WS_URL: getConfigValue('REACT_APP_WS_URL', 'ws://155.138.239.131:8000'),
    REACT_APP_SOCKETIO_URL: getConfigValue('REACT_APP_SOCKETIO_URL', 'http://155.138.239.131:8001'),
    REACT_APP_VIDEO_BASE_URL: getConfigValue('REACT_APP_VIDEO_BASE_URL', 'http://155.138.239.131:8000'),
    REACT_APP_ENVIRONMENT: getConfigValue('REACT_APP_ENVIRONMENT', 'production')
  };
}