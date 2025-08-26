/**
 * Configuration Override System (DEPRECATED)
 * 
 * This file is deprecated in favor of configurationManager.ts
 * These functions are kept for backward compatibility but redirect to the new system
 * 
 * @deprecated Use configurationManager.ts instead
 */

import { 
  getConfigValueSync, 
  getFullConfigSync, 
  configurationManager,
  waitForConfig as waitForConfigManager,
  isConfigInitialized,
  RuntimeConfig 
} from './configurationManager';

/**
 * Get configuration value with runtime override support
 * @deprecated Use getConfigValueSync from configurationManager instead
 */
export function getConfigValue(key: keyof RuntimeConfig, fallback: string): string {
  console.warn(`⚠️ getConfigValue is deprecated, use getConfigValueSync from configurationManager`);
  const result = getConfigValueSync(key, fallback as RuntimeConfig[keyof RuntimeConfig]);
  return result || fallback;
}

/**
 * Force override process.env with runtime config
 * @deprecated Configuration is now handled automatically by configurationManager
 */
export function applyRuntimeConfigOverrides(): void {
  console.warn(`⚠️ applyRuntimeConfigOverrides is deprecated, configuration is handled automatically`);
  // No-op - configuration manager handles this automatically
}

/**
 * Get all configuration with overrides applied
 * @deprecated Use getFullConfigSync from configurationManager instead
 */
export function getFullConfig(): RuntimeConfig {
  console.warn(`⚠️ getFullConfig is deprecated, use getFullConfigSync from configurationManager`);
  return getFullConfigSync();
}

/**
 * Wait for configuration to be ready
 * @deprecated Use waitForConfig from configurationManager instead
 */
export function waitForConfig(): Promise<void> {
  console.warn(`⚠️ waitForConfig is deprecated, use waitForConfig from configurationManager`);
  return waitForConfigManager();
}

/**
 * Check if configuration is ready
 * @deprecated Use isConfigInitialized from configurationManager instead
 */
export function isConfigReady(): boolean {
  console.warn(`⚠️ isConfigReady is deprecated, use isConfigInitialized from configurationManager`);
  return isConfigInitialized();
}

// Re-export types for backward compatibility
export type { RuntimeConfig } from './configurationManager';