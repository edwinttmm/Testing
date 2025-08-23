/**
 * Debug Configuration Utility
 * Provides centralized debug logging configuration
 */

/**
 * Debug configuration interface
 */
interface DebugConfig {
  enabled: boolean;
  level: 'error' | 'warn' | 'info' | 'debug';
  components: {
    videoPlayer: boolean;
    annotations: boolean;
    api: boolean;
    upload: boolean;
    rendering: boolean;
  };
}

/**
 * Default debug configuration
 */
const defaultConfig: DebugConfig = {
  enabled: process.env.NODE_ENV === 'development',
  level: 'info',
  components: {
    videoPlayer: false, // Disable by default to reduce console spam
    annotations: false,
    api: false,
    upload: true, // Keep upload debugging enabled
    rendering: false,
  },
};

/**
 * Get debug configuration from environment or localStorage
 */
const getDebugConfig = (): DebugConfig => {
  try {
    const stored = localStorage.getItem('debug-config');
    if (stored) {
      return { ...defaultConfig, ...JSON.parse(stored) };
    }
  } catch (error) {
    // Fall back to default config
  }
  
  return defaultConfig;
};

let debugConfig = getDebugConfig();

/**
 * Update debug configuration
 */
export const setDebugConfig = (newConfig: Partial<DebugConfig>): void => {
  debugConfig = { ...debugConfig, ...newConfig };
  try {
    localStorage.setItem('debug-config', JSON.stringify(debugConfig));
  } catch (error) {
    console.warn('Failed to save debug config to localStorage');
  }
};

/**
 * Check if debug logging is enabled globally
 */
export const isDebugEnabled = (component?: keyof DebugConfig['components']): boolean => {
  if (!debugConfig.enabled) return false;
  
  if (component) {
    return debugConfig.components[component];
  }
  
  return true;
};

/**
 * Conditional console.log for development
 */
export const debugLog = (component: keyof DebugConfig['components'], message: string, ...args: unknown[]): void => {
  if (isDebugEnabled(component)) {
    console.log(`[${component.toUpperCase()}] ${message}`, ...args);
  }
};

/**
 * Conditional console.warn for development
 */
export const debugWarn = (component: keyof DebugConfig['components'], message: string, ...args: unknown[]): void => {
  if (isDebugEnabled(component)) {
    console.warn(`[${component.toUpperCase()}] ${message}`, ...args);
  }
};

/**
 * Conditional console.error for development
 */
export const debugError = (component: keyof DebugConfig['components'], message: string, ...args: unknown[]): void => {
  if (isDebugEnabled(component)) {
    console.error(`[${component.toUpperCase()}] ${message}`, ...args);
  }
};

/**
 * Performance timing utility
 */
export const debugTime = (component: keyof DebugConfig['components'], label: string): (() => void) => {
  if (!isDebugEnabled(component)) {
    return () => {}; // No-op function
  }
  
  const start = performance.now();
  console.time(`[${component.toUpperCase()}] ${label}`);
  
  return () => {
    const end = performance.now();
    console.timeEnd(`[${component.toUpperCase()}] ${label}`);
    
    if (end - start > 16) { // Warn if operation takes longer than one frame
      console.warn(`[${component.toUpperCase()}] Slow operation: ${label} took ${(end - start).toFixed(2)}ms`);
    }
  };
};

/**
 * Export current debug configuration
 */
export const getDebugConfigSnapshot = (): DebugConfig => ({ ...debugConfig });

/**
 * Reset debug configuration to defaults
 */
export const resetDebugConfig = (): void => {
  debugConfig = { ...defaultConfig };
  try {
    localStorage.removeItem('debug-config');
  } catch (error) {
    console.warn('Failed to remove debug config from localStorage');
  }
};