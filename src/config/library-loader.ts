/**
 * Dynamic Library Loader
 * Conditionally loads image processing libraries based on GPU capabilities
 */

import { gpuDetector, type LibraryConfig, type GPUCapabilities } from '../utils/gpu-detector';

export interface LoadedLibraries {
  tensorflow?: any;
  opencv?: any;
  jimp?: any;
  sharp?: any;
  canvas?: any;
}

export interface LibraryLoadResult {
  success: boolean;
  libraries: LoadedLibraries;
  config: LibraryConfig;
  capabilities: GPUCapabilities;
  errors: string[];
}

class LibraryLoader {
  private loadedLibraries: LoadedLibraries = {};
  private loadPromise: Promise<LibraryLoadResult> | null = null;

  /**
   * Load all compatible libraries based on GPU capabilities
   */
  async loadLibraries(): Promise<LibraryLoadResult> {
    if (this.loadPromise) {
      return this.loadPromise;
    }

    this.loadPromise = this.performLoad();
    return this.loadPromise;
  }

  private async performLoad(): Promise<LibraryLoadResult> {
    const capabilities = await gpuDetector.detectCapabilities();
    const config = await gpuDetector.getLibraryConfig();
    const errors: string[] = [];

    console.log('🔍 GPU Detection Results:', capabilities);
    console.log('📦 Library Configuration:', config);

    // Load TensorFlow.js
    try {
      this.loadedLibraries.tensorflow = await this.loadTensorFlow(config);
      console.log('✅ TensorFlow.js loaded successfully');
    } catch (error) {
      const errorMsg = `Failed to load TensorFlow.js: ${error}`;
      console.warn('⚠️', errorMsg);
      errors.push(errorMsg);
    }

    // Load OpenCV.js
    try {
      this.loadedLibraries.opencv = await this.loadOpenCV(config);
      console.log('✅ OpenCV.js loaded successfully');
    } catch (error) {
      const errorMsg = `Failed to load OpenCV.js: ${error}`;
      console.warn('⚠️', errorMsg);
      errors.push(errorMsg);
    }

    // Load fallback libraries
    if (config.fallback.useJimp) {
      try {
        this.loadedLibraries.jimp = await this.loadJimp();
        console.log('✅ Jimp loaded successfully');
      } catch (error) {
        const errorMsg = `Failed to load Jimp: ${error}`;
        console.warn('⚠️', errorMsg);
        errors.push(errorMsg);
      }
    }

    if (config.fallback.useSharp && capabilities.platform === 'node') {
      try {
        this.loadedLibraries.sharp = await this.loadSharp();
        console.log('✅ Sharp loaded successfully');
      } catch (error) {
        const errorMsg = `Failed to load Sharp: ${error}`;
        console.warn('⚠️', errorMsg);
        errors.push(errorMsg);
      }
    }

    if (config.fallback.useCanvas && capabilities.platform === 'web') {
      try {
        this.loadedLibraries.canvas = await this.loadCanvas();
        console.log('✅ Canvas API ready');
      } catch (error) {
        const errorMsg = `Failed to initialize Canvas: ${error}`;
        console.warn('⚠️', errorMsg);
        errors.push(errorMsg);
      }
    }

    return {
      success: errors.length === 0 || Object.keys(this.loadedLibraries).length > 0,
      libraries: this.loadedLibraries,
      config,
      capabilities,
      errors,
    };
  }

  /**
   * Load TensorFlow.js with appropriate backend
   */
  private async loadTensorFlow(config: LibraryConfig): Promise<any> {
    let tf: any;

    // Dynamic import based on configuration
    if (config.tensorflow.useGPU && config.tensorflow.backend === 'webgl') {
      // Load GPU-enabled TensorFlow.js
      tf = await import('@tensorflow/tfjs');
      
      // Set backend to WebGL
      await tf.setBackend('webgl');
      await tf.ready();
      
      console.log('🎮 TensorFlow.js using WebGL backend');
    } else {
      // Load CPU-only version or fallback
      try {
        tf = await import('@tensorflow/tfjs-cpu');
        await tf.setBackend('cpu');
        await tf.ready();
        console.log('🖥️ TensorFlow.js using CPU backend');
      } catch (e) {
        // Fallback to main package with CPU backend
        tf = await import('@tensorflow/tfjs');
        await tf.setBackend('cpu');
        await tf.ready();
        console.log('🖥️ TensorFlow.js fallback to CPU backend');
      }
    }

    return tf;
  }

  /**
   * Load OpenCV.js
   */
  private async loadOpenCV(config: LibraryConfig): Promise<any> {
    if (typeof window !== 'undefined') {
      // Web environment - load OpenCV.js
      return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        
        if (config.opencv.useGPU) {
          // Load GPU-enabled version (if available)
          script.src = 'https://cdn.jsdelivr.net/npm/opencv.js@latest/opencv.js';
        } else {
          // Load WASM version
          script.src = 'https://cdn.jsdelivr.net/npm/opencv.js@latest/opencv.js';
        }

        script.onload = () => {
          const cv = (window as any).cv;
          if (cv && cv.imread) {
            cv.onRuntimeInitialized = () => {
              console.log('🔧 OpenCV.js initialized');
              resolve(cv);
            };
          } else {
            reject(new Error('OpenCV.js failed to initialize'));
          }
        };

        script.onerror = () => reject(new Error('Failed to load OpenCV.js script'));
        document.head.appendChild(script);
      });
    } else {
      // Node.js environment
      try {
        const cv = await import('opencv4nodejs');
        return cv;
      } catch (e) {
        throw new Error('opencv4nodejs not available in Node.js environment');
      }
    }
  }

  /**
   * Load Jimp (CPU-only image processing)
   */
  private async loadJimp(): Promise<any> {
    try {
      const Jimp = await import('jimp');
      return Jimp.default || Jimp;
    } catch (e) {
      throw new Error('Jimp not available');
    }
  }

  /**
   * Load Sharp (Node.js only)
   */
  private async loadSharp(): Promise<any> {
    if (typeof window !== 'undefined') {
      throw new Error('Sharp is not available in browser environment');
    }

    try {
      const sharp = await import('sharp');
      return sharp.default || sharp;
    } catch (e) {
      throw new Error('Sharp not available');
    }
  }

  /**
   * Initialize Canvas API
   */
  private async loadCanvas(): Promise<any> {
    if (typeof window === 'undefined') {
      throw new Error('Canvas API not available in Node.js environment');
    }

    // Canvas API is built-in, just return a helper object
    return {
      createElement: (width: number, height: number) => {
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        return canvas;
      },
      getContext: (canvas: HTMLCanvasElement, type: '2d' | 'webgl' | 'webgl2' = '2d') => {
        return canvas.getContext(type);
      },
    };
  }

  /**
   * Get loaded libraries
   */
  getLoadedLibraries(): LoadedLibraries {
    return this.loadedLibraries;
  }

  /**
   * Check if a specific library is loaded
   */
  isLibraryLoaded(library: keyof LoadedLibraries): boolean {
    return !!this.loadedLibraries[library];
  }

  /**
   * Reset loader state
   */
  reset(): void {
    this.loadedLibraries = {};
    this.loadPromise = null;
  }
}

// Singleton instance
export const libraryLoader = new LibraryLoader();

/**
 * Convenience function to ensure libraries are loaded
 */
export async function ensureLibrariesLoaded(): Promise<LibraryLoadResult> {
  return await libraryLoader.loadLibraries();
}

/**
 * Get best available library for image processing
 */
export async function getBestImageLibrary(): Promise<{
  library: 'tensorflow' | 'opencv' | 'jimp' | 'sharp' | 'canvas';
  instance: any;
} | null> {
  const result = await libraryLoader.loadLibraries();
  const libs = result.libraries;

  // Priority order based on capabilities
  if (libs.tensorflow && result.config.tensorflow.useGPU) {
    return { library: 'tensorflow', instance: libs.tensorflow };
  }
  
  if (libs.opencv) {
    return { library: 'opencv', instance: libs.opencv };
  }
  
  if (libs.tensorflow) {
    return { library: 'tensorflow', instance: libs.tensorflow };
  }
  
  if (libs.sharp) {
    return { library: 'sharp', instance: libs.sharp };
  }
  
  if (libs.jimp) {
    return { library: 'jimp', instance: libs.jimp };
  }
  
  if (libs.canvas) {
    return { library: 'canvas', instance: libs.canvas };
  }

  return null;
}