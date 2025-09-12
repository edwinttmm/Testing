/**
 * React Hook for Unified Configuration
 * Provides React integration for the unified configuration system
 */

import { useState, useEffect, useContext, createContext, ReactNode } from 'react';
import { ConfigSchema, configManager } from '../ConfigManager';
import { environmentDetector } from '../services/EnvironmentDetector';

export interface ConfigContextType {
  config: ConfigSchema | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  isReady: boolean;
}

// Create configuration context
const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

// Configuration Provider component
export interface ConfigProviderProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function ConfigProvider({ children, fallback }: ConfigProviderProps) {
  const [config, setConfig] = useState<ConfigSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  const initializeConfig = async () => {
    try {
      setLoading(true);
      setError(null);

      console.log('🚀 Initializing configuration system...');
      
      const initializedConfig = await configManager.initialize();
      setConfig(initializedConfig);
      setIsReady(true);
      
      console.log('✅ Configuration system ready');
      
      // Log configuration summary for debugging
      if (initializedConfig.features.debugging) {
        console.log('📊 Configuration loaded:', {
          environment: initializedConfig.environment.type,
          platform: initializedConfig.environment.platform,
          apiURL: initializedConfig.api.baseURL,
          corsOrigins: initializedConfig.cors.origins.length
        });
      }
      
    } catch (err) {
      console.error('❌ Configuration initialization failed:', err);
      setError(err instanceof Error ? err.message : 'Configuration initialization failed');
      setIsReady(false);
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    await initializeConfig();
  };

  useEffect(() => {
    initializeConfig();

    // Set up configuration watcher for hot reloading
    const unwatch = configManager.watchConfig((newConfig) => {
      console.log('🔄 Configuration updated');
      setConfig(newConfig);
    });

    // Set up environment change detection (for development)
    const handleVisibilityChange = () => {
      if (!document.hidden && config?.features.debugging) {
        // Re-detect environment when tab becomes visible (development only)
        setTimeout(() => {
          environmentDetector.detectEnvironment(true).then(() => {
            console.log('🔄 Environment re-detected');
          });
        }, 1000);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      unwatch();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const contextValue: ConfigContextType = {
    config,
    loading,
    error,
    refresh,
    isReady
  };

  if (loading && fallback) {
    return <>{fallback}</>;
  }

  return (
    <ConfigContext.Provider value={contextValue}>
      {children}
    </ConfigContext.Provider>
  );
}

// Main hook to use configuration
export function useConfig(): ConfigContextType {
  const context = useContext(ConfigContext);
  
  if (context === undefined) {
    throw new Error('useConfig must be used within a ConfigProvider');
  }
  
  return context;
}

// Specialized hooks for different configuration sections

export function useAPIConfig() {
  const { config, isReady } = useConfig();
  
  if (!isReady || !config) {
    return null;
  }
  
  return config.api;
}

export function useCORSConfig() {
  const { config, isReady } = useConfig();
  
  if (!isReady || !config) {
    return null;
  }
  
  return config.cors;
}

export function useEnvironmentInfo() {
  const { config, isReady } = useConfig();
  
  if (!isReady || !config) {
    return null;
  }
  
  return config.environment;
}

export function useFeatureFlags() {
  const { config, isReady } = useConfig();
  
  if (!isReady || !config) {
    return null;
  }
  
  return config.features;
}

export function useSecurityConfig() {
  const { config, isReady } = useConfig();
  
  if (!isReady || !config) {
    return null;
  }
  
  return config.security;
}

// Hook for environment-based conditional rendering
export function useEnvironmentConditional() {
  const environment = useEnvironmentInfo();
  
  return {
    isDevelopment: environment?.type === 'development',
    isStaging: environment?.type === 'staging',
    isProduction: environment?.type === 'production',
    isLocal: environment?.platform === 'local',
    isDocker: environment?.platform === 'docker',
    isCloud: environment?.platform === 'cloud',
    isSSL: environment?.features.ssl || false
  };
}

// Hook for configuration validation
export function useConfigValidation() {
  const { config, error } = useConfig();
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  
  useEffect(() => {
    if (config) {
      const errors = configManager.getValidationErrors();
      setValidationErrors(errors);
    }
  }, [config]);
  
  return {
    hasErrors: !!error || validationErrors.length > 0,
    initializationError: error,
    validationErrors,
    allErrors: error ? [error, ...validationErrors] : validationErrors
  };
}

// Hook for runtime configuration updates
export function useRuntimeConfig() {
  const { refresh } = useConfig();
  
  const updateRuntimeConfig = (updates: Record<string, any>) => {
    if (typeof window !== 'undefined') {
      // Update window.RUNTIME_CONFIG
      window.RUNTIME_CONFIG = {
        ...((window as any).RUNTIME_CONFIG || {}),
        ...updates
      };
      
      // Update process.env for compatibility
      Object.assign(process.env, updates);
      
      // Refresh configuration
      refresh();
      
      console.log('🔄 Runtime configuration updated:', updates);
    }
  };
  
  return {
    updateRuntimeConfig,
    currentRuntimeConfig: typeof window !== 'undefined' ? (window as any).RUNTIME_CONFIG : {}
  };
}

// Development-only hook for configuration debugging
export function useConfigDebug() {
  const { config, loading, error } = useConfig();
  const environment = useEnvironmentInfo();
  
  // Only enable in development
  if (environment?.type !== 'development') {
    return null;
  }
  
  const logCurrentConfig = () => {
    console.group('🔧 Current Configuration');
    console.log('Config Object:', config);
    console.log('Environment:', environment);
    console.log('Loading:', loading);
    console.log('Error:', error);
    console.log('Validation Errors:', configManager.getValidationErrors());
    console.groupEnd();
  };
  
  const testAPIConnectivity = async () => {
    if (!config) return;
    
    try {
      console.log('🧪 Testing API connectivity...');
      const response = await fetch(`${config.api.baseURL}/health`);
      console.log('✅ API Test Result:', response.status, response.statusText);
    } catch (err) {
      console.error('❌ API Test Failed:', err);
    }
  };
  
  const testCORSConfiguration = () => {
    if (!config) return;
    
    console.group('🔍 CORS Configuration Test');
    console.log('Configured Origins:', config.cors.origins);
    console.log('Current Origin:', window.location.origin);
    console.log('Origin Allowed:', config.cors.origins.includes(window.location.origin));
    console.groupEnd();
  };
  
  return {
    logCurrentConfig,
    testAPIConnectivity,
    testCORSConfiguration,
    environmentSummary: environment ? environmentDetector.getEnvironmentSummary() : null
  };
}