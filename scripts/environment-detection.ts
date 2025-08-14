/**
 * Comprehensive Environment Detection and Configuration System
 * Supports Windows MINGW64, Linux, and cross-platform deployment
 */

export interface SystemCapabilities {
  platform: {
    os: string;
    arch: string;
    version?: string;
    isWindows: boolean;
    isLinux: boolean;
    isMingw: boolean;
  };
  runtime: {
    node: string;
    npm: string;
    typescript?: string;
  };
  hardware: {
    cpu: {
      model: string;
      cores: number;
      architecture: string;
      features: string[];
    };
    memory: {
      total: number;
      available: number;
      heap: number;
    };
    gpu: {
      available: boolean;
      vendor?: 'nvidia' | 'amd' | 'intel' | 'unknown';
      memory?: number;
      compute?: string;
      webgl?: boolean;
    };
  };
  network: {
    online: boolean;
    connection?: string;
  };
  features: {
    webassembly: boolean;
    sharedArrayBuffer: boolean;
    offscreenCanvas: boolean;
    webWorkers: boolean;
    serviceWorker: boolean;
  };
}

export interface OptimizationConfig {
  imageProcessing: {
    maxSize: number;
    quality: number;
    format: 'webp' | 'jpeg' | 'png';
    fallbackFormat: 'jpeg' | 'png';
    batchSize: number;
  };
  bundling: {
    splitChunks: boolean;
    treeShaking: boolean;
    compression: boolean;
    minification: boolean;
  };
  caching: {
    serviceWorker: boolean;
    memoryLimit: number;
    storageLimit: number;
    strategy: 'aggressive' | 'conservative' | 'balanced';
  };
  performance: {
    lazyLoading: boolean;
    preloading: boolean;
    prefetching: boolean;
    criticalResourceHints: boolean;
  };
}

class EnvironmentDetector {
  private capabilities: SystemCapabilities | null = null;
  private config: OptimizationConfig | null = null;

  /**
   * Detect comprehensive system capabilities
   */
  async detectCapabilities(): Promise<SystemCapabilities> {
    if (this.capabilities) {
      return this.capabilities;
    }

    const capabilities: SystemCapabilities = {
      platform: await this.detectPlatform(),
      runtime: await this.detectRuntime(),
      hardware: await this.detectHardware(),
      network: await this.detectNetwork(),
      features: await this.detectFeatures(),
    };

    this.capabilities = capabilities;
    return capabilities;
  }

  /**
   * Platform detection with MINGW64 support
   */
  private async detectPlatform() {
    const isNode = typeof process !== 'undefined';
    
    if (isNode) {
      // Node.js environment
      return {
        os: process.platform,
        arch: process.arch,
        version: process.version,
        isWindows: process.platform === 'win32',
        isLinux: process.platform === 'linux',
        isMingw: !!(process.env.MSYSTEM && process.env.MSYSTEM.includes('MINGW')),
      };
    } else {
      // Browser environment
      const userAgent = navigator.userAgent;
      return {
        os: this.parseUserAgent(userAgent),
        arch: 'unknown',
        isWindows: userAgent.includes('Windows'),
        isLinux: userAgent.includes('Linux'),
        isMingw: false,
      };
    }
  }

  /**
   * Runtime version detection
   */
  private async detectRuntime() {
    const isNode = typeof process !== 'undefined';
    
    if (isNode) {
      const nodeVersion = process.version;
      const npmVersion = await this.getNpmVersion();
      const tsVersion = await this.getTypeScriptVersion();
      
      return {
        node: nodeVersion,
        npm: npmVersion,
        typescript: tsVersion,
      };
    } else {
      return {
        node: 'browser',
        npm: 'browser',
      };
    }
  }

  /**
   * Hardware capability detection
   */
  private async detectHardware() {
    const isNode = typeof process !== 'undefined';
    
    if (isNode) {
      // Node.js environment - use os module
      try {
        const os = require('os');
        const cpuInfo = os.cpus()[0];
        const memInfo = {
          total: os.totalmem(),
          available: os.freemem(),
          heap: process.memoryUsage().heapTotal,
        };

        return {
          cpu: {
            model: cpuInfo.model,
            cores: os.cpus().length,
            architecture: os.arch(),
            features: await this.detectCpuFeatures(),
          },
          memory: memInfo,
          gpu: await this.detectGpu(),
        };
      } catch (error) {
        console.warn('Failed to detect hardware:', error);
        return this.getDefaultHardwareInfo();
      }
    } else {
      // Browser environment
      return {
        cpu: {
          model: 'unknown',
          cores: navigator.hardwareConcurrency || 4,
          architecture: 'unknown',
          features: [],
        },
        memory: {
          total: (performance as any).memory?.jsHeapSizeLimit || 2147483648,
          available: (performance as any).memory?.usedJSHeapSize || 1073741824,
          heap: (performance as any).memory?.totalJSHeapSize || 1073741824,
        },
        gpu: await this.detectWebGpu(),
      };
    }
  }

  /**
   * GPU detection with fallback strategies
   */
  private async detectGpu() {
    try {
      // Try to detect GPU using nvidia-ml-py equivalent for Node.js
      const { exec } = require('child_process');
      
      return new Promise((resolve) => {
        // Try nvidia-smi first
        exec('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits', (error, stdout) => {
          if (!error && stdout.trim()) {
            const [name, memory] = stdout.trim().split(',');
            resolve({
              available: true,
              vendor: 'nvidia' as const,
              memory: parseInt(memory.trim()),
              compute: name.trim(),
              webgl: false,
            });
            return;
          }

          // Try AMD GPU detection
          exec('rocm-smi --showproductname', (error, stdout) => {
            if (!error && stdout.trim()) {
              resolve({
                available: true,
                vendor: 'amd' as const,
                memory: 0,
                compute: stdout.trim(),
                webgl: false,
              });
              return;
            }

            // No GPU detected - CPU only
            resolve({
              available: false,
              webgl: false,
            });
          });
        });
      });
    } catch (error) {
      return {
        available: false,
        webgl: false,
      };
    }
  }

  /**
   * WebGL/WebGPU detection for browser environments
   */
  private async detectWebGpu() {
    try {
      // Check WebGL support
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
      
      if (gl) {
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        const vendor = debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'unknown';
        const renderer = debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'unknown';
        
        return {
          available: true,
          vendor: this.parseGpuVendor(vendor),
          compute: renderer,
          webgl: true,
        };
      }

      // Check WebGPU support
      if ('gpu' in navigator) {
        const adapter = await (navigator as any).gpu.requestAdapter();
        if (adapter) {
          return {
            available: true,
            vendor: 'unknown' as const,
            compute: 'WebGPU',
            webgl: false,
          };
        }
      }

      return {
        available: false,
        webgl: false,
      };
    } catch (error) {
      return {
        available: false,
        webgl: false,
      };
    }
  }

  /**
   * Network capability detection
   */
  private async detectNetwork() {
    try {
      if (typeof navigator !== 'undefined' && 'onLine' in navigator) {
        return {
          online: navigator.onLine,
          connection: (navigator as any).connection?.effectiveType || 'unknown',
        };
      }
      
      return {
        online: true,
        connection: 'unknown',
      };
    } catch (error) {
      return {
        online: true,
        connection: 'unknown',
      };
    }
  }

  /**
   * Feature detection for optimization
   */
  private async detectFeatures() {
    try {
      return {
        webassembly: typeof WebAssembly !== 'undefined',
        sharedArrayBuffer: typeof SharedArrayBuffer !== 'undefined',
        offscreenCanvas: typeof OffscreenCanvas !== 'undefined',
        webWorkers: typeof Worker !== 'undefined',
        serviceWorker: 'serviceWorker' in navigator,
      };
    } catch (error) {
      return {
        webassembly: false,
        sharedArrayBuffer: false,
        offscreenCanvas: false,
        webWorkers: false,
        serviceWorker: false,
      };
    }
  }

  /**
   * Generate optimized configuration based on capabilities
   */
  async generateOptimizationConfig(): Promise<OptimizationConfig> {
    if (this.config) {
      return this.config;
    }

    const capabilities = await this.detectCapabilities();
    
    const config: OptimizationConfig = {
      imageProcessing: {
        maxSize: capabilities.hardware.gpu.available ? 4096 : 2048,
        quality: capabilities.hardware.gpu.available ? 0.9 : 0.8,
        format: capabilities.features.webassembly ? 'webp' : 'jpeg',
        fallbackFormat: 'jpeg',
        batchSize: capabilities.hardware.gpu.available ? 4 : 1,
      },
      bundling: {
        splitChunks: true,
        treeShaking: true,
        compression: true,
        minification: !capabilities.platform.isMingw, // Disable for MINGW64 debugging
      },
      caching: {
        serviceWorker: capabilities.features.serviceWorker,
        memoryLimit: Math.min(capabilities.hardware.memory.available * 0.1, 536870912), // 10% or 512MB max
        storageLimit: 2147483648, // 2GB
        strategy: capabilities.hardware.gpu.available ? 'aggressive' : 'conservative',
      },
      performance: {
        lazyLoading: true,
        preloading: capabilities.network.online,
        prefetching: capabilities.network.connection !== 'slow-2g',
        criticalResourceHints: true,
      },
    };

    this.config = config;
    return config;
  }

  /**
   * Utility methods
   */
  private parseUserAgent(userAgent: string): string {
    if (userAgent.includes('Windows')) return 'win32';
    if (userAgent.includes('Mac')) return 'darwin';
    if (userAgent.includes('Linux')) return 'linux';
    return 'unknown';
  }

  private parseGpuVendor(vendor: string): 'nvidia' | 'amd' | 'intel' | 'unknown' {
    const v = vendor.toLowerCase();
    if (v.includes('nvidia')) return 'nvidia';
    if (v.includes('amd') || v.includes('ati')) return 'amd';
    if (v.includes('intel')) return 'intel';
    return 'unknown';
  }

  private async getNpmVersion(): Promise<string> {
    try {
      const { exec } = require('child_process');
      return new Promise((resolve) => {
        exec('npm --version', (error, stdout) => {
          resolve(error ? 'unknown' : stdout.trim());
        });
      });
    } catch (error) {
      return 'unknown';
    }
  }

  private async getTypeScriptVersion(): Promise<string | undefined> {
    try {
      const { exec } = require('child_process');
      return new Promise((resolve) => {
        exec('npx tsc --version', (error, stdout) => {
          if (error) {
            resolve(undefined);
          } else {
            const match = stdout.match(/Version (\d+\.\d+\.\d+)/);
            resolve(match ? match[1] : undefined);
          }
        });
      });
    } catch (error) {
      return undefined;
    }
  }

  private async detectCpuFeatures(): Promise<string[]> {
    try {
      const { exec } = require('child_process');
      return new Promise((resolve) => {
        exec('lscpu | grep Flags || cat /proc/cpuinfo | grep flags', (error, stdout) => {
          if (error) {
            resolve([]);
          } else {
            const flagsLine = stdout.split('\n').find(line => line.includes('flags') || line.includes('Flags'));
            if (flagsLine) {
              const flags = flagsLine.split(':')[1]?.trim().split(/\s+/) || [];
              resolve(flags.filter(flag => ['sse', 'sse2', 'sse3', 'sse4', 'avx', 'avx2'].some(f => flag.includes(f))));
            } else {
              resolve([]);
            }
          }
        });
      });
    } catch (error) {
      return [];
    }
  }

  private getDefaultHardwareInfo() {
    return {
      cpu: {
        model: 'unknown',
        cores: 4,
        architecture: 'x64',
        features: [],
      },
      memory: {
        total: 8589934592, // 8GB
        available: 4294967296, // 4GB
        heap: 1073741824, // 1GB
      },
      gpu: {
        available: false,
        webgl: false,
      },
    };
  }
}

/**
 * Singleton instance for global access
 */
export const environmentDetector = new EnvironmentDetector();

/**
 * Quick detection methods for common use cases
 */
export const quickDetect = {
  async isGpuAvailable(): Promise<boolean> {
    const caps = await environmentDetector.detectCapabilities();
    return caps.hardware.gpu.available;
  },

  async isMingwEnvironment(): Promise<boolean> {
    const caps = await environmentDetector.detectCapabilities();
    return caps.platform.isMingw;
  },

  async getOptimalImageConfig() {
    const config = await environmentDetector.generateOptimizationConfig();
    return config.imageProcessing;
  },

  async getCacheStrategy() {
    const config = await environmentDetector.generateOptimizationConfig();
    return config.caching;
  },
};

/**
 * Export types for external use
 */
export type { SystemCapabilities, OptimizationConfig };