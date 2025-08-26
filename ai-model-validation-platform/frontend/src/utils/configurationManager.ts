/**
 * Configuration Manager
 * Ensures runtime configuration loads and applies before any service initialization
 * Provides proper initialization guard and precedence handling
 */

export interface RuntimeConfig {
  REACT_APP_API_URL: string;
  REACT_APP_WS_URL: string;
  REACT_APP_SOCKETIO_URL: string;
  REACT_APP_VIDEO_BASE_URL: string;
  REACT_APP_ENVIRONMENT?: string;
}

export interface ConfigState {
  initialized: boolean;
  runtimeConfigLoaded: boolean;
  environmentConfigLoaded: boolean;
  finalConfig: RuntimeConfig | null;
  error: string | null;
}

class ConfigurationManager {
  private state: ConfigState = {
    initialized: false,
    runtimeConfigLoaded: false,
    environmentConfigLoaded: false,
    finalConfig: null,
    error: null
  };

  private initializationPromise: Promise<void> | null = null;
  private initializationResolve: (() => void) | null = null;
  private initializationReject: ((error: Error) => void) | null = null;
  private readyCallbacks: (() => void)[] = [];

  constructor() {
    this.startInitialization();
  }

  /**
   * Start the configuration initialization process
   */
  private startInitialization(): void {
    if (this.initializationPromise) {
      return;
    }

    this.initializationPromise = new Promise<void>((resolve, reject) => {
      this.initializationResolve = resolve;
      this.initializationReject = reject;
    });

    // Start initialization process
    this.initializeConfiguration();
  }

  /**
   * Initialize configuration with proper loading sequence
   */
  private async initializeConfiguration(): Promise<void> {
    try {
      console.log('🔧 ConfigurationManager: Starting initialization...');

      // Step 1: Wait for DOM to be ready
      await this.waitForDOMReady();

      // Step 2: Check for runtime config (window.RUNTIME_CONFIG)
      await this.waitForRuntimeConfig();

      // Step 3: Load environment config
      this.loadEnvironmentConfig();

      // Step 4: Apply precedence and create final config
      this.createFinalConfiguration();

      // Step 5: Mark as initialized
      this.state.initialized = true;
      console.log('✅ ConfigurationManager: Initialization complete');
      console.log('🔧 Final Configuration:', this.state.finalConfig);

      // Notify waiting services
      if (this.initializationResolve) {
        this.initializationResolve();
      }

      // Execute ready callbacks
      this.readyCallbacks.forEach(callback => {
        try {
          callback();
        } catch (error) {
          console.error('Error in ready callback:', error);
        }
      });

    } catch (error) {
      console.error('❌ ConfigurationManager: Initialization failed:', error);
      this.state.error = error instanceof Error ? error.message : String(error);
      
      if (this.initializationReject) {
        this.initializationReject(error instanceof Error ? error : new Error(String(error)));
      }
    }
  }

  /**
   * Wait for DOM to be ready
   */
  private waitForDOMReady(): Promise<void> {
    return new Promise<void>((resolve) => {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => resolve());
      } else {
        resolve();
      }
    });
  }

  /**
   * Wait for runtime configuration to be available
   */
  private waitForRuntimeConfig(): Promise<void> {
    return new Promise<void>((resolve) => {
      const maxWaitTime = 5000; // 5 seconds max wait
      const checkInterval = 50; // Check every 50ms
      let elapsed = 0;

      const checkForRuntimeConfig = () => {
        // Check if runtime config is available
        if (typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG) {
          console.log('🔧 Runtime config found:', (window as any).RUNTIME_CONFIG);
          this.state.runtimeConfigLoaded = true;
          resolve();
          return;
        }

        elapsed += checkInterval;

        if (elapsed >= maxWaitTime) {
          console.warn('⚠️ Runtime config not found within timeout, proceeding with environment config');
          resolve();
          return;
        }

        setTimeout(checkForRuntimeConfig, checkInterval);
      };

      checkForRuntimeConfig();
    });
  }

  /**
   * Load environment configuration
   */
  private loadEnvironmentConfig(): void {
    this.state.environmentConfigLoaded = true;
    console.log('🔧 Environment config loaded from process.env');
  }

  /**
   * Create final configuration with proper precedence
   */
  private createFinalConfiguration(): void {
    const defaults: RuntimeConfig = {
      REACT_APP_API_URL: 'http://155.138.239.131:8000',
      REACT_APP_WS_URL: 'ws://155.138.239.131:8000',
      REACT_APP_SOCKETIO_URL: 'http://155.138.239.131:8001',
      REACT_APP_VIDEO_BASE_URL: 'http://155.138.239.131:8000',
      REACT_APP_ENVIRONMENT: 'production'
    };

    // Apply precedence: runtime config > environment > defaults
    const finalConfig: RuntimeConfig = { ...defaults };

    // Apply environment variables
    Object.keys(defaults).forEach(key => {
      const envValue = process.env[key as keyof RuntimeConfig];
      if (envValue) {
        (finalConfig as any)[key] = envValue;
      }
    });

    // Apply runtime config overrides (highest precedence)
    if (this.state.runtimeConfigLoaded && typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG) {
      const runtimeConfig = (window as any).RUNTIME_CONFIG;
      Object.keys(runtimeConfig).forEach(key => {
        if (key in finalConfig) {
          (finalConfig as any)[key] = runtimeConfig[key];
        }
      });

      // Also update process.env to ensure compatibility
      Object.keys(runtimeConfig).forEach(key => {
        process.env[key] = runtimeConfig[key];
      });
    }

    this.state.finalConfig = finalConfig;
  }

  /**
   * Wait for configuration to be initialized
   */
  async waitForInitialization(): Promise<void> {
    if (this.state.initialized) {
      return;
    }

    if (!this.initializationPromise) {
      throw new Error('Configuration initialization was never started');
    }

    await this.initializationPromise;
  }

  /**
   * Get configuration value with initialization guard
   */
  async getConfigValue<K extends keyof RuntimeConfig>(key: K, fallback: RuntimeConfig[K]): Promise<RuntimeConfig[K]> {
    await this.waitForInitialization();

    if (!this.state.finalConfig) {
      console.warn(`⚠️ Final config not available, using fallback for ${key}`);
      return fallback;
    }

    const value = this.state.finalConfig[key];
    return value || fallback;
  }

  /**
   * Get configuration value synchronously (only after initialization)
   */
  getConfigValueSync<K extends keyof RuntimeConfig>(key: K, fallback: RuntimeConfig[K]): RuntimeConfig[K] {
    if (!this.state.initialized) {
      console.warn(`⚠️ Configuration not yet initialized, using fallback for ${key}`);
      return fallback;
    }

    if (!this.state.finalConfig) {
      return fallback;
    }

    const value = this.state.finalConfig[key];
    return value || fallback;
  }

  /**
   * Get full configuration
   */
  async getFullConfig(): Promise<RuntimeConfig> {
    await this.waitForInitialization();
    return this.state.finalConfig || this.getDefaultConfig();
  }

  /**
   * Get full configuration synchronously (only after initialization)
   */
  getFullConfigSync(): RuntimeConfig {
    if (!this.state.initialized || !this.state.finalConfig) {
      return this.getDefaultConfig();
    }
    return this.state.finalConfig;
  }

  /**
   * Check if configuration is initialized
   */
  isInitialized(): boolean {
    return this.state.initialized;
  }

  /**
   * Get initialization state
   */
  getState(): ConfigState {
    return { ...this.state };
  }

  /**
   * Register callback to execute when configuration is ready
   */
  onReady(callback: () => void): void {
    if (this.state.initialized) {
      // Already initialized, execute immediately
      try {
        callback();
      } catch (error) {
        console.error('Error in ready callback:', error);
      }
    } else {
      // Not initialized yet, register for later execution
      this.readyCallbacks.push(callback);
    }
  }

  /**
   * Force reinitialization (for testing)
   */
  async reinitialize(): Promise<void> {
    this.state = {
      initialized: false,
      runtimeConfigLoaded: false,
      environmentConfigLoaded: false,
      finalConfig: null,
      error: null
    };

    this.initializationPromise = null;
    this.initializationResolve = null;
    this.initializationReject = null;
    this.readyCallbacks = [];

    this.startInitialization();
    await this.waitForInitialization();
  }

  private getDefaultConfig(): RuntimeConfig {
    return {
      REACT_APP_API_URL: 'http://155.138.239.131:8000',
      REACT_APP_WS_URL: 'ws://155.138.239.131:8000',
      REACT_APP_SOCKETIO_URL: 'http://155.138.239.131:8001',
      REACT_APP_VIDEO_BASE_URL: 'http://155.138.239.131:8000',
      REACT_APP_ENVIRONMENT: 'production'
    };
  }
}

// Export singleton instance
export const configurationManager = new ConfigurationManager();

// Export convenience functions
export const waitForConfig = () => configurationManager.waitForInitialization();
export const getConfigValue = <K extends keyof RuntimeConfig>(key: K, fallback: RuntimeConfig[K]) =>
  configurationManager.getConfigValue(key, fallback);
export const getConfigValueSync = <K extends keyof RuntimeConfig>(key: K, fallback: RuntimeConfig[K]) =>
  configurationManager.getConfigValueSync(key, fallback);
export const getFullConfig = () => configurationManager.getFullConfig();
export const getFullConfigSync = () => configurationManager.getFullConfigSync();
export const isConfigInitialized = () => configurationManager.isInitialized();
export const onConfigReady = (callback: () => void) => configurationManager.onReady(callback);

export default configurationManager;