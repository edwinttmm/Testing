/**
 * Image Processor Factory
 * Creates appropriate image processors based on available libraries and GPU capabilities
 */

import { 
  type ImageProcessor, 
  type ProcessorFactory, 
  type LibraryStatus, 
  type ImageProcessingCapabilities,
  ImageProcessingError 
} from '../types/image-processing';
import { libraryLoader, type LibraryLoadResult } from '../config/library-loader';
import { TensorFlowImageProcessor } from './processors/tensorflow-processor';
import { OpenCVImageProcessor } from './processors/opencv-processor';
import { JimpImageProcessor } from './processors/jimp-processor';
import { SharpImageProcessor } from './processors/sharp-processor';
import { CanvasImageProcessor } from './processors/canvas-processor';

export class ImageProcessorFactory implements ProcessorFactory {
  private loadResult: LibraryLoadResult | null = null;
  private processorCache = new Map<string, ImageProcessor>();

  /**
   * Create an image processor with optimal library selection
   */
  async createProcessor(preferredLibrary?: string): Promise<ImageProcessor> {
    const loadResult = await this.ensureLibrariesLoaded();
    
    // Check cache first
    const cacheKey = preferredLibrary || 'auto';
    if (this.processorCache.has(cacheKey)) {
      return this.processorCache.get(cacheKey)!;
    }

    let processor: ImageProcessor;

    if (preferredLibrary) {
      processor = await this.createSpecificProcessor(preferredLibrary, loadResult);
    } else {
      processor = await this.createBestProcessor(loadResult);
    }

    this.processorCache.set(cacheKey, processor);
    return processor;
  }

  /**
   * Get status of all available processors
   */
  async getAvailableProcessors(): Promise<LibraryStatus[]> {
    const loadResult = await this.ensureLibrariesLoaded();
    const statuses: LibraryStatus[] = [];

    // TensorFlow.js status
    if (loadResult.libraries.tensorflow) {
      try {
        const tf = loadResult.libraries.tensorflow;
        statuses.push({
          name: 'TensorFlow.js',
          loaded: true,
          version: tf.version?.tfjs || 'unknown',
          backend: tf.getBackend?.() || loadResult.config.tensorflow.backend,
          capabilities: {
            resize: true,
            crop: true,
            rotate: true,
            filter: true,
            objectDetection: true,
            faceDetection: false,
            textRecognition: false,
            colorAnalysis: true,
            edgeDetection: true,
            backgroundRemoval: true,
          },
        });
      } catch (error) {
        statuses.push({
          name: 'TensorFlow.js',
          loaded: false,
          error: `Error: ${error}`,
          capabilities: {} as ImageProcessingCapabilities,
        });
      }
    }

    // OpenCV.js status
    if (loadResult.libraries.opencv) {
      statuses.push({
        name: 'OpenCV.js',
        loaded: true,
        backend: loadResult.config.opencv.useGPU ? 'GPU' : 'CPU',
        capabilities: {
          resize: true,
          crop: true,
          rotate: true,
          filter: true,
          objectDetection: true,
          faceDetection: true,
          textRecognition: false,
          colorAnalysis: true,
          edgeDetection: true,
          backgroundRemoval: true,
        },
      });
    }

    // Jimp status
    if (loadResult.libraries.jimp) {
      statuses.push({
        name: 'Jimp',
        loaded: true,
        backend: 'CPU',
        capabilities: {
          resize: true,
          crop: true,
          rotate: true,
          filter: true,
          objectDetection: false,
          faceDetection: false,
          textRecognition: false,
          colorAnalysis: true,
          edgeDetection: false,
          backgroundRemoval: false,
        },
      });
    }

    // Sharp status
    if (loadResult.libraries.sharp) {
      statuses.push({
        name: 'Sharp',
        loaded: true,
        backend: 'CPU',
        capabilities: {
          resize: true,
          crop: true,
          rotate: true,
          filter: true,
          objectDetection: false,
          faceDetection: false,
          textRecognition: false,
          colorAnalysis: true,
          edgeDetection: false,
          backgroundRemoval: false,
        },
      });
    }

    // Canvas status
    if (loadResult.libraries.canvas) {
      statuses.push({
        name: 'Canvas',
        loaded: true,
        backend: 'CPU',
        capabilities: {
          resize: true,
          crop: true,
          rotate: true,
          filter: false,
          objectDetection: false,
          faceDetection: false,
          textRecognition: false,
          colorAnalysis: true,
          edgeDetection: false,
          backgroundRemoval: false,
        },
      });
    }

    return statuses;
  }

  /**
   * Get the best processor based on requirements and available libraries
   */
  async getBestProcessor(requirements?: Partial<ImageProcessingCapabilities>): Promise<ImageProcessor> {
    const loadResult = await this.ensureLibrariesLoaded();
    const statuses = await this.getAvailableProcessors();

    if (requirements) {
      // Find processor that meets requirements
      const compatibleProcessors = statuses.filter(status => 
        this.meetsRequirements(status.capabilities, requirements)
      );

      if (compatibleProcessors.length === 0) {
        throw new ImageProcessingError(
          'No available processor meets the specified requirements',
          'NO_COMPATIBLE_PROCESSOR'
        );
      }

      // Prefer GPU-accelerated processors
      const bestProcessor = compatibleProcessors.find(p => 
        p.backend === 'webgl' || p.name === 'TensorFlow.js'
      ) || compatibleProcessors[0];

      return this.createSpecificProcessor(
        this.getLibraryKeyFromName(bestProcessor.name),
        loadResult
      );
    }

    return this.createBestProcessor(loadResult);
  }

  /**
   * Create a specific processor by library name
   */
  private async createSpecificProcessor(
    library: string, 
    loadResult: LibraryLoadResult
  ): Promise<ImageProcessor> {
    switch (library.toLowerCase()) {
      case 'tensorflow':
        if (!loadResult.libraries.tensorflow) {
          throw new ImageProcessingError('TensorFlow.js not available', 'LIBRARY_NOT_LOADED');
        }
        return new TensorFlowImageProcessor(
          loadResult.libraries.tensorflow,
          loadResult.config.tensorflow.useGPU
        );

      case 'opencv':
        if (!loadResult.libraries.opencv) {
          throw new ImageProcessingError('OpenCV.js not available', 'LIBRARY_NOT_LOADED');
        }
        return new OpenCVImageProcessor(
          loadResult.libraries.opencv,
          loadResult.config.opencv.useGPU
        );

      case 'jimp':
        if (!loadResult.libraries.jimp) {
          throw new ImageProcessingError('Jimp not available', 'LIBRARY_NOT_LOADED');
        }
        return new JimpImageProcessor(loadResult.libraries.jimp);

      case 'sharp':
        if (!loadResult.libraries.sharp) {
          throw new ImageProcessingError('Sharp not available', 'LIBRARY_NOT_LOADED');
        }
        return new SharpImageProcessor(loadResult.libraries.sharp);

      case 'canvas':
        if (!loadResult.libraries.canvas) {
          throw new ImageProcessingError('Canvas not available', 'LIBRARY_NOT_LOADED');
        }
        return new CanvasImageProcessor(loadResult.libraries.canvas);

      default:
        throw new ImageProcessingError(`Unknown library: ${library}`, 'UNKNOWN_LIBRARY');
    }
  }

  /**
   * Create the best available processor
   */
  private async createBestProcessor(loadResult: LibraryLoadResult): Promise<ImageProcessor> {
    const libs = loadResult.libraries;

    // Priority order: GPU TensorFlow > OpenCV > CPU TensorFlow > Sharp > Jimp > Canvas
    if (libs.tensorflow && loadResult.config.tensorflow.useGPU) {
      return new TensorFlowImageProcessor(libs.tensorflow, true);
    }

    if (libs.opencv) {
      return new OpenCVImageProcessor(libs.opencv, loadResult.config.opencv.useGPU);
    }

    if (libs.tensorflow) {
      return new TensorFlowImageProcessor(libs.tensorflow, false);
    }

    if (libs.sharp) {
      return new SharpImageProcessor(libs.sharp);
    }

    if (libs.jimp) {
      return new JimpImageProcessor(libs.jimp);
    }

    if (libs.canvas) {
      return new CanvasImageProcessor(libs.canvas);
    }

    throw new ImageProcessingError(
      'No image processing libraries available',
      'NO_LIBRARIES_AVAILABLE'
    );
  }

  /**
   * Check if processor capabilities meet requirements
   */
  private meetsRequirements(
    capabilities: ImageProcessingCapabilities,
    requirements: Partial<ImageProcessingCapabilities>
  ): boolean {
    for (const [key, required] of Object.entries(requirements)) {
      if (required && !capabilities[key as keyof ImageProcessingCapabilities]) {
        return false;
      }
    }
    return true;
  }

  /**
   * Convert processor name to library key
   */
  private getLibraryKeyFromName(name: string): string {
    switch (name.toLowerCase()) {
      case 'tensorflow.js': return 'tensorflow';
      case 'opencv.js': return 'opencv';
      case 'jimp': return 'jimp';
      case 'sharp': return 'sharp';
      case 'canvas': return 'canvas';
      default: return name.toLowerCase();
    }
  }

  /**
   * Ensure libraries are loaded
   */
  private async ensureLibrariesLoaded(): Promise<LibraryLoadResult> {
    if (!this.loadResult) {
      this.loadResult = await libraryLoader.loadLibraries();
    }
    return this.loadResult;
  }

  /**
   * Clear processor cache and reload libraries
   */
  async refresh(): Promise<void> {
    this.loadResult = null;
    this.processorCache.clear();
    libraryLoader.reset();
    await this.ensureLibrariesLoaded();
  }

  /**
   * Get cache statistics
   */
  getCacheStats(): { size: number; keys: string[] } {
    return {
      size: this.processorCache.size,
      keys: Array.from(this.processorCache.keys()),
    };
  }
}

// Singleton factory instance
export const imageProcessorFactory = new ImageProcessorFactory();

/**
 * Convenience function to get a processor quickly
 */
export async function getImageProcessor(preferredLibrary?: string): Promise<ImageProcessor> {
  return await imageProcessorFactory.createProcessor(preferredLibrary);
}

/**
 * Convenience function to get the best processor for specific needs
 */
export async function getBestImageProcessor(
  requirements?: Partial<ImageProcessingCapabilities>
): Promise<ImageProcessor> {
  return await imageProcessorFactory.getBestProcessor(requirements);
}