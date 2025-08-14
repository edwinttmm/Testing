/**
 * GPU Detection and Environment Utility
 * Provides runtime detection of GPU capabilities and environment configuration
 */

export interface GPUCapabilities {
  hasGPU: boolean;
  hasWebGL: boolean;
  hasWebGL2: boolean;
  vendor?: string;
  renderer?: string;
  maxTextureSize?: number;
  memoryInfo?: {
    totalJSHeapSize?: number;
    usedJSHeapSize?: number;
    jsHeapSizeLimit?: number;
  };
  platform: 'web' | 'node';
  os: 'windows' | 'mac' | 'linux' | 'unknown';
  architecture: 'x64' | 'arm64' | 'x86' | 'unknown';
}

export interface LibraryConfig {
  tensorflow: {
    useGPU: boolean;
    backend: 'webgl' | 'cpu' | 'wasm';
    package: '@tensorflow/tfjs' | '@tensorflow/tfjs-cpu' | '@tensorflow/tfjs-node';
  };
  opencv: {
    useGPU: boolean;
    useWasm: boolean;
    package: 'opencv.js' | 'opencv4nodejs';
  };
  fallback: {
    useJimp: boolean;
    useSharp: boolean;
    useCanvas: boolean;
  };
}

class GPUDetector {
  private capabilities: GPUCapabilities | null = null;
  private libraryConfig: LibraryConfig | null = null;

  /**
   * Detect GPU capabilities and environment
   */
  async detectCapabilities(): Promise<GPUCapabilities> {
    if (this.capabilities) {
      return this.capabilities;
    }

    const capabilities: GPUCapabilities = {
      hasGPU: false,
      hasWebGL: false,
      hasWebGL2: false,
      platform: typeof window !== 'undefined' ? 'web' : 'node',
      os: this.detectOS(),
      architecture: this.detectArchitecture(),
    };

    // Web environment detection
    if (typeof window !== 'undefined') {
      capabilities.hasWebGL = this.detectWebGL();
      capabilities.hasWebGL2 = this.detectWebGL2();
      capabilities.hasGPU = capabilities.hasWebGL || capabilities.hasWebGL2;

      if (capabilities.hasWebGL) {
        const glInfo = this.getWebGLInfo();
        capabilities.vendor = glInfo.vendor;
        capabilities.renderer = glInfo.renderer;
        capabilities.maxTextureSize = glInfo.maxTextureSize;
      }

      // Memory info
      if ('memory' in performance) {
        capabilities.memoryInfo = {
          totalJSHeapSize: (performance as any).memory.totalJSHeapSize,
          usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
          jsHeapSizeLimit: (performance as any).memory.jsHeapSizeLimit,
        };
      }
    }
    // Node.js environment detection
    else {
      capabilities.hasGPU = await this.detectNodeGPU();
    }

    this.capabilities = capabilities;
    return capabilities;
  }

  /**
   * Generate optimal library configuration based on capabilities
   */
  async getLibraryConfig(): Promise<LibraryConfig> {
    if (this.libraryConfig) {
      return this.libraryConfig;
    }

    const capabilities = await this.detectCapabilities();
    
    const config: LibraryConfig = {
      tensorflow: {
        useGPU: capabilities.hasGPU && capabilities.hasWebGL2,
        backend: capabilities.hasWebGL2 ? 'webgl' : capabilities.hasWebGL ? 'webgl' : 'cpu',
        package: capabilities.platform === 'web' 
          ? (capabilities.hasGPU ? '@tensorflow/tfjs' : '@tensorflow/tfjs-cpu')
          : '@tensorflow/tfjs-node',
      },
      opencv: {
        useGPU: capabilities.hasGPU && capabilities.platform === 'web',
        useWasm: capabilities.platform === 'web' && !capabilities.hasGPU,
        package: capabilities.platform === 'web' ? 'opencv.js' : 'opencv4nodejs',
      },
      fallback: {
        useJimp: !capabilities.hasGPU || capabilities.platform === 'node',
        useSharp: capabilities.platform === 'node',
        useCanvas: capabilities.platform === 'web' && !capabilities.hasWebGL,
      },
    };

    this.libraryConfig = config;
    return config;
  }

  /**
   * Check if environment supports GPU acceleration
   */
  async isGPUAvailable(): Promise<boolean> {
    const capabilities = await this.detectCapabilities();
    return capabilities.hasGPU;
  }

  /**
   * Get recommended backend for TensorFlow.js
   */
  async getRecommendedTFBackend(): Promise<'webgl' | 'cpu' | 'wasm'> {
    const config = await this.getLibraryConfig();
    return config.tensorflow.backend;
  }

  /**
   * Detect WebGL support
   */
  private detectWebGL(): boolean {
    try {
      const canvas = document.createElement('canvas');
      return !!(
        canvas.getContext('webgl') || 
        canvas.getContext('experimental-webgl')
      );
    } catch (e) {
      return false;
    }
  }

  /**
   * Detect WebGL2 support
   */
  private detectWebGL2(): boolean {
    try {
      const canvas = document.createElement('canvas');
      return !!canvas.getContext('webgl2');
    } catch (e) {
      return false;
    }
  }

  /**
   * Get WebGL renderer information
   */
  private getWebGLInfo(): {
    vendor?: string;
    renderer?: string;
    maxTextureSize?: number;
  } {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      
      if (!gl) return {};

      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      
      return {
        vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : undefined,
        renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : undefined,
        maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
      };
    } catch (e) {
      return {};
    }
  }

  /**
   * Detect operating system
   */
  private detectOS(): 'windows' | 'mac' | 'linux' | 'unknown' {
    if (typeof window !== 'undefined') {
      const platform = navigator.platform.toLowerCase();
      if (platform.includes('win')) return 'windows';
      if (platform.includes('mac')) return 'mac';
      if (platform.includes('linux')) return 'linux';
    } else if (typeof process !== 'undefined') {
      const platform = process.platform;
      if (platform === 'win32') return 'windows';
      if (platform === 'darwin') return 'mac';
      if (platform === 'linux') return 'linux';
    }
    return 'unknown';
  }

  /**
   * Detect system architecture
   */
  private detectArchitecture(): 'x64' | 'arm64' | 'x86' | 'unknown' {
    if (typeof process !== 'undefined') {
      const arch = process.arch;
      if (arch === 'x64') return 'x64';
      if (arch === 'arm64') return 'arm64';
      if (arch === 'ia32') return 'x86';
    }
    return 'unknown';
  }

  /**
   * Detect GPU in Node.js environment
   */
  private async detectNodeGPU(): Promise<boolean> {
    try {
      // Check for NVIDIA GPU
      if (process.platform === 'win32') {
        const { execSync } = await import('child_process');
        try {
          execSync('nvidia-smi', { stdio: 'ignore' });
          return true;
        } catch (e) {
          // NVIDIA driver not found
        }
      }
      
      // Check for other GPU indicators
      // This is a basic check - more sophisticated detection would require native modules
      return false;
    } catch (e) {
      return false;
    }
  }

  /**
   * Reset detector state (useful for testing)
   */
  reset(): void {
    this.capabilities = null;
    this.libraryConfig = null;
  }
}

// Singleton instance
export const gpuDetector = new GPUDetector();

// Environment variable overrides
export const ENV_CONFIG = {
  FORCE_CPU_ONLY: process.env.REACT_APP_FORCE_CPU_ONLY === 'true',
  DISABLE_GPU_DETECTION: process.env.REACT_APP_DISABLE_GPU_DETECTION === 'true',
  PREFERRED_BACKEND: process.env.REACT_APP_PREFERRED_BACKEND as 'webgl' | 'cpu' | 'wasm',
  DEBUG_GPU_INFO: process.env.REACT_APP_DEBUG_GPU_INFO === 'true',
};

/**
 * Utility function to get GPU status with environment overrides
 */
export async function getGPUStatus(): Promise<GPUCapabilities & { configOverride?: boolean }> {
  const capabilities = await gpuDetector.detectCapabilities();
  
  if (ENV_CONFIG.FORCE_CPU_ONLY) {
    return {
      ...capabilities,
      hasGPU: false,
      hasWebGL: false,
      hasWebGL2: false,
      configOverride: true,
    };
  }
  
  return capabilities;
}

/**
 * Utility function to check if we should use GPU acceleration
 */
export async function shouldUseGPU(): Promise<boolean> {
  if (ENV_CONFIG.FORCE_CPU_ONLY || ENV_CONFIG.DISABLE_GPU_DETECTION) {
    return false;
  }
  
  return await gpuDetector.isGPUAvailable();
}