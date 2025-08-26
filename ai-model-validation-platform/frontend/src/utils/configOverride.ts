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
  RuntimeConfig 
} from './configurationManager';

/**
 * Get configuration value with runtime override support
 * @deprecated Use getConfigValueSync from configurationManager instead
 */
export function getConfigValue(key: keyof RuntimeConfig, fallback: string): string {
  console.warn(`⚠️ getConfigValue is deprecated, use getConfigValueSync from configurationManager`);
  return getConfigValueSync(key, fallback as any);
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

// Re-export types for backward compatibility
export type { RuntimeConfig } from './configurationManager';