/**
 * Application Configuration
 * Centralized configuration management with environment-specific settings
 * Enhanced with runtime configuration override support
 */

import { getConfigValue, applyRuntimeConfigOverrides } from '../utils/configOverride';

// Apply runtime overrides immediately
applyRuntimeConfigOverrides();

export interface AppConfig {
  // API Configuration
  api: {
    baseUrl: string;
    timeout: number;
    retries: number;
    retryDelay: number;
  };
  
  // WebSocket Configuration
  websocket: {
    url: string;
    reconnectAttempts: number;
    reconnectDelay: number;
    heartbeatInterval: number;
  };
  
  // Feature Flags
  features: {
    realTimeUpdates: boolean;
    advancedAnalytics: boolean;
    videoAnnotation: boolean;
    batchProcessing: boolean;
    experimentalFeatures: boolean;
  };
  
  // Performance Settings
  performance: {
    enableCaching: boolean;
    cacheTimeout: number;
    virtualScrolling: boolean;
    lazyLoading: boolean;
    maxConcurrentRequests: number;
  };
  
  // UI/UX Settings
  ui: {
    theme: 'light' | 'dark' | 'auto';
    responsiveBreakpoints: boolean;
    animationsEnabled: boolean;
    autoSave: boolean;
    autoSaveInterval: number;
  };
  
  // Development Settings
  development: {
    enableDebugMode: boolean;
    showPerformanceMetrics: boolean;
    mockApiResponses: boolean;
    verboseLogging: boolean;
  };
}

const getEnvironmentConfig = (): Partial<AppConfig> => {
  const env = process.env.NODE_ENV || 'development';
  const isDevelopment = env === 'development';
  const isProduction = env === 'production';
  
  // Determine API base URL with runtime override support
  const getApiBaseUrl = (): string => {
    // Use the runtime-aware config getter
    const configUrl = getConfigValue('REACT_APP_API_URL', '');
    if (configUrl) {
      return configUrl;
    }
    
    // Auto-detect based on current hostname in browser
    if (typeof window !== 'undefined') {
      const { hostname, protocol } = window.location;
      
      // Development defaults - Updated to use external IP
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://155.138.239.131:8000';
      }
      
      // Production defaults
      return `${protocol}//${hostname}:8000`;
    }
    
    // Fallback for server-side rendering - Updated to use external IP
    return 'http://155.138.239.131:8000';
  };
  
  // Determine WebSocket URL with runtime override support
  const getWebSocketUrl = (): string => {
    // Use the runtime-aware config getter
    const configUrl = getConfigValue('REACT_APP_WS_URL', '');
    if (configUrl) {
      return configUrl;
    }
    
    const apiUrl = getApiBaseUrl();
    return apiUrl.replace(/^http/, 'ws');
  };
  
  return {
    api: {
      baseUrl: getApiBaseUrl(),
      timeout: isDevelopment ? 30000 : 15000,
      retries: 3,
      retryDelay: 1000,
    },
    
    websocket: {
      url: getWebSocketUrl(),
      reconnectAttempts: isProduction ? 10 : 5,
      reconnectDelay: 1000,
      heartbeatInterval: 30000,
    },
    
    features: {
      realTimeUpdates: true,
      advancedAnalytics: isProduction,
      videoAnnotation: true,
      batchProcessing: true,
      experimentalFeatures: isDevelopment,
    },
    
    performance: {
      enableCaching: isProduction,
      cacheTimeout: 5 * 60 * 1000, // 5 minutes
      virtualScrolling: true,
      lazyLoading: isProduction,
      maxConcurrentRequests: 5,
    },
    
    ui: {
      theme: 'light' as const,
      responsiveBreakpoints: true,
      animationsEnabled: !process.env.REACT_APP_REDUCED_MOTION,
      autoSave: true,
      autoSaveInterval: 30000, // 30 seconds
    },
    
    development: {
      enableDebugMode: isDevelopment && !!process.env.REACT_APP_DEBUG,
      showPerformanceMetrics: isDevelopment,
      mockApiResponses: isDevelopment && !!process.env.REACT_APP_MOCK_API,
      verboseLogging: isDevelopment,
    },
  };
};

// Default configuration
const defaultConfig: AppConfig = {
  api: {
    baseUrl: 'http://155.138.239.131:8000',
    timeout: 30000,
    retries: 3,
    retryDelay: 1000,
  },
  
  websocket: {
    url: 'ws://155.138.239.131:8000',
    reconnectAttempts: 5,
    reconnectDelay: 1000,
    heartbeatInterval: 30000,
  },
  
  features: {
    realTimeUpdates: true,
    advancedAnalytics: false,
    videoAnnotation: true,
    batchProcessing: true,
    experimentalFeatures: false,
  },
  
  performance: {
    enableCaching: false,
    cacheTimeout: 5 * 60 * 1000,
    virtualScrolling: false,
    lazyLoading: false,
    maxConcurrentRequests: 3,
  },
  
  ui: {
    theme: 'light',
    responsiveBreakpoints: true,
    animationsEnabled: true,
    autoSave: true,
    autoSaveInterval: 30000,
  },
  
  development: {
    enableDebugMode: false,
    showPerformanceMetrics: false,
    mockApiResponses: false,
    verboseLogging: false,
  },
};

// Merge environment config with defaults
const environmentConfig = getEnvironmentConfig();
export const appConfig: AppConfig = {
  ...defaultConfig,
  ...environmentConfig,
  // Deep merge nested objects
  api: { ...defaultConfig.api, ...environmentConfig.api },
  websocket: { ...defaultConfig.websocket, ...environmentConfig.websocket },
  features: { ...defaultConfig.features, ...environmentConfig.features },
  performance: { ...defaultConfig.performance, ...environmentConfig.performance },
  ui: { ...defaultConfig.ui, ...environmentConfig.ui },
  development: { ...defaultConfig.development, ...environmentConfig.development },
};

// Configuration validation
export const validateConfig = (): { isValid: boolean; errors: string[] } => {
  const errors: string[] = [];
  
  // Validate API URL
  try {
    new URL(appConfig.api.baseUrl);
  } catch {
    errors.push(`Invalid API base URL: ${appConfig.api.baseUrl}`);
  }
  
  // Validate timeout values
  if (appConfig.api.timeout < 1000) {
    errors.push('API timeout should be at least 1000ms');
  }
  
  // Validate retry settings
  if (appConfig.api.retries < 0 || appConfig.api.retries > 10) {
    errors.push('API retries should be between 0 and 10');
  }
  
  return {
    isValid: errors.length === 0,
    errors,
  };
};

// Configuration helpers
export const isFeatureEnabled = (feature: keyof AppConfig['features']): boolean => {
  return appConfig.features[feature];
};

export const isDevelopment = (): boolean => {
  return process.env.NODE_ENV === 'development';
};

export const isProduction = (): boolean => {
  return process.env.NODE_ENV === 'production';
};

export const getApiUrl = (endpoint: string = ''): string => {
  const baseUrl = appConfig.api.baseUrl.replace(/\/$/, '');
  const cleanEndpoint = endpoint.replace(/^\//, '');
  return cleanEndpoint ? `${baseUrl}/${cleanEndpoint}` : baseUrl;
};

export const getWebSocketUrl = (endpoint: string = ''): string => {
  const baseUrl = appConfig.websocket.url.replace(/\/$/, '');
  const cleanEndpoint = endpoint.replace(/^\//, '');
  return cleanEndpoint ? `${baseUrl}/${cleanEndpoint}` : baseUrl;
};

// Log configuration on startup (development only)
if (appConfig.development.enableDebugMode) {
  console.group('🔧 Application Configuration');
  console.log('Environment:', process.env.NODE_ENV);
  console.log('API Base URL:', appConfig.api.baseUrl);
  console.log('WebSocket URL:', appConfig.websocket.url);
  console.log('Features:', appConfig.features);
  console.log('Performance:', appConfig.performance);
  console.groupEnd();
  
  const validation = validateConfig();
  if (!validation.isValid) {
    console.warn('⚠️ Configuration validation errors:', validation.errors);
  }
}

export default appConfig;