/**
 * Sharp Image Processor
 * High-performance image processing for Node.js using Sharp
 */

import {
  type ImageProcessor,
  type ImageProcessingCapabilities,
  type ImageData,
  type ProcessingResult,
  type DetectionResult,
  type AnalysisResult,
  type ImageProcessingOptions,
  ImageProcessingError,
} from '../../types/image-processing';

export class SharpImageProcessor implements ImageProcessor {
  readonly library = 'sharp' as const;
  readonly isGPUAccelerated = false;
  readonly capabilities: ImageProcessingCapabilities = {
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
  };

  constructor(private sharp: any) {}

  /**
   * Resize image using Sharp
   */
  async resize(
    imageData: ImageData,
    options: { width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      
      const result = await this.sharp(buffer)
        .resize(options.width, options.height)
        .png()
        .toBuffer({ resolveWithObject: true });

      const outputImageData = await this.bufferToImageData(result.data, result.info);

      return {
        success: true,
        data: outputImageData,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
        error: `Resize failed: ${error}`,
      };
    }
  }

  /**
   * Crop image using Sharp
   */
  async crop(
    imageData: ImageData,
    options: { x: number; y: number; width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      
      const result = await this.sharp(buffer)
        .extract({
          left: options.x,
          top: options.y,
          width: options.width,
          height: options.height,
        })
        .png()
        .toBuffer({ resolveWithObject: true });

      const outputImageData = await this.bufferToImageData(result.data, result.info);

      return {
        success: true,
        data: outputImageData,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
        error: `Crop failed: ${error}`,
      };
    }
  }

  /**
   * Rotate image using Sharp
   */
  async rotate(imageData: ImageData, angle: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      
      const result = await this.sharp(buffer)
        .rotate(angle)
        .png()
        .toBuffer({ resolveWithObject: true });

      const outputImageData = await this.bufferToImageData(result.data, result.info);

      return {
        success: true,
        data: outputImageData,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
        error: `Rotation failed: ${error}`,
      };
    }
  }

  /**
   * Apply filter to image
   */
  async applyFilter(
    imageData: ImageData,
    filter: string,
    intensity: number = 1.0
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      let sharpInstance = this.sharp(buffer);

      switch (filter.toLowerCase()) {
        case 'blur':
          sharpInstance = sharpInstance.blur(intensity * 5);
          break;
        case 'sharpen':
          sharpInstance = sharpInstance.sharpen({
            sigma: intensity,
            flat: 1,
            jagged: 2,
          });
          break;
        case 'grayscale':
          sharpInstance = sharpInstance.grayscale();
          break;
        case 'median':
          sharpInstance = sharpInstance.median(Math.max(1, Math.round(intensity * 5)));
          break;
        case 'normalize':
          sharpInstance = sharpInstance.normalize();
          break;
        default:
          throw new Error(`Unknown filter: ${filter}`);
      }

      const result = await sharpInstance.png().toBuffer({ resolveWithObject: true });
      const outputImageData = await this.bufferToImageData(result.data, result.info);

      return {
        success: true,
        data: outputImageData,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
        error: `Filter application failed: ${error}`,
      };
    }
  }

  /**
   * Adjust brightness
   */
  async adjustBrightness(imageData: ImageData, value: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      
      // Convert value from [-1, 1] to Sharp's expected range
      const brightness = 1 + value;
      
      const result = await this.sharp(buffer)
        .modulate({ brightness })
        .png()
        .toBuffer({ resolveWithObject: true });

      const outputImageData = await this.bufferToImageData(result.data, result.info);

      return {
        success: true,
        data: outputImageData,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
        error: `Brightness adjustment failed: ${error}`,
      };
    }
  }

  /**
   * Adjust contrast
   */
  async adjustContrast(imageData: ImageData, value: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      
      // Use linear transformation for contrast adjustment
      const result = await this.sharp(buffer)
        .linear(1 + value, -(128 * value))
        .png()
        .toBuffer({ resolveWithObject: true });

      const outputImageData = await this.bufferToImageData(result.data, result.info);

      return {
        success: true,
        data: outputImageData,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: 'CPU',
        error: `Contrast adjustment failed: ${error}`,
      };
    }
  }

  /**
   * Blur image
   */
  async blur(imageData: ImageData, radius: number): Promise<ProcessingResult> {
    return this.applyFilter(imageData, 'blur', radius / 5);
  }

  /**
   * Sharpen image
   */
  async sharpen(imageData: ImageData, intensity?: number): Promise<ProcessingResult> {
    return this.applyFilter(imageData, 'sharpen', intensity || 1.0);
  }

  /**
   * Analyze image colors and properties
   */
  async analyze(imageData: ImageData): Promise<AnalysisResult> {
    try {
      const buffer = this.imageDataToBuffer(imageData);
      
      // Get basic metadata
      const metadata = await this.sharp(buffer).metadata();
      
      // Get statistics
      const stats = await this.sharp(buffer).stats();
      
      // Calculate dominant colors (simplified using channel means)
      const dominantColors = stats.channels.length >= 3 ? [
        {
          color: {
            r: Math.round(stats.channels[0].mean),
            g: Math.round(stats.channels[1].mean),
            b: Math.round(stats.channels[2].mean),
          },
          percentage: 100,
          hex: `#${Math.round(stats.channels[0].mean).toString(16).padStart(2, '0')}${Math.round(stats.channels[1].mean).toString(16).padStart(2, '0')}${Math.round(stats.channels[2].mean).toString(16).padStart(2, '0')}`,
        },
      ] : [];

      // Calculate overall brightness
      const brightness = stats.channels.length >= 3 
        ? (stats.channels[0].mean + stats.channels[1].mean + stats.channels[2].mean) / (3 * 255)
        : stats.channels[0].mean / 255;

      return {
        dominantColors,
        brightness,
        contrast: 0.5, // Placeholder - would need histogram analysis
        sharpness: 0.5, // Placeholder - would need edge detection
        dimensions: { 
          width: metadata.width || imageData.width, 
          height: metadata.height || imageData.height 
        },
        fileSize: imageData.data.length,
        format: metadata.format || imageData.format || 'unknown',
      };
    } catch (error) {
      throw new ImageProcessingError(`Analysis failed: ${error}`, 'ANALYSIS_FAILED');
    }
  }

  /**
   * Object detection (not supported)
   */
  async detectObjects(imageData: ImageData): Promise<DetectionResult[]> {
    console.warn('Object detection not supported by Sharp processor');
    return [];
  }

  /**
   * Face detection (not supported)
   */
  async detectFaces(imageData: ImageData): Promise<DetectionResult[]> {
    console.warn('Face detection not supported by Sharp processor');
    return [];
  }

  /**
   * Edge detection (not supported)
   */
  async detectEdges(imageData: ImageData): Promise<ProcessingResult> {
    return {
      success: false,
      processingTime: 0,
      library: this.library,
      backend: 'CPU',
      error: 'Edge detection not supported by Sharp processor',
    };
  }

  /**
   * Load image from various sources
   */
  async loadImage(source: string | ArrayBuffer | Buffer): Promise<ImageData> {
    try {
      let buffer: Buffer;

      if (typeof source === 'string') {
        // Handle URLs or file paths
        if (source.startsWith('http') || source.startsWith('data:')) {
          throw new ImageProcessingError(
            'URL loading not implemented for Sharp processor',
            'NOT_IMPLEMENTED'
          );
        } else {
          // File path
          buffer = await require('fs').promises.readFile(source);
        }
      } else if (source instanceof ArrayBuffer) {
        buffer = Buffer.from(source);
      } else {
        buffer = source as Buffer;
      }

      const metadata = await this.sharp(buffer).metadata();
      const { data, info } = await this.sharp(buffer)
        .ensureAlpha()
        .raw()
        .toBuffer({ resolveWithObject: true });

      return {
        data: new Uint8Array(data),
        width: info.width,
        height: info.height,
        channels: info.channels,
        format: metadata.format || 'unknown',
      };
    } catch (error) {
      throw new ImageProcessingError(`Failed to load image: ${error}`, 'LOAD_FAILED');
    }
  }

  /**
   * Save image with specified options
   */
  async saveImage(imageData: ImageData, options: ImageProcessingOptions): Promise<ArrayBuffer> {
    try {
      const buffer = this.imageDataToBuffer(imageData);
      let sharpInstance = this.sharp(buffer);

      // Apply format and quality
      const format = options.format || 'png';
      const quality = options.quality ? Math.round(options.quality * 100) : 90;

      switch (format) {
        case 'jpeg':
          sharpInstance = sharpInstance.jpeg({ quality });
          break;
        case 'webp':
          sharpInstance = sharpInstance.webp({ quality });
          break;
        case 'avif':
          sharpInstance = sharpInstance.avif({ quality });
          break;
        default:
          sharpInstance = sharpInstance.png();
      }

      const outputBuffer = await sharpInstance.toBuffer();
      return outputBuffer.buffer.slice(
        outputBuffer.byteOffset,
        outputBuffer.byteOffset + outputBuffer.byteLength
      );
    } catch (error) {
      throw new ImageProcessingError(`Failed to save image: ${error}`, 'SAVE_FAILED');
    }
  }

  /**
   * Get image metadata
   */
  async getMetadata(imageData: ImageData): Promise<any> {
    try {
      const buffer = this.imageDataToBuffer(imageData);
      const metadata = await this.sharp(buffer).metadata();

      return {
        width: metadata.width,
        height: metadata.height,
        channels: metadata.channels,
        format: metadata.format,
        space: metadata.space,
        density: metadata.density,
        hasAlpha: metadata.hasAlpha,
        hasProfile: metadata.hasProfile,
        exif: metadata.exif,
        icc: metadata.icc,
        iptc: metadata.iptc,
        xmp: metadata.xmp,
      };
    } catch (error) {
      throw new ImageProcessingError(`Failed to get metadata: ${error}`, 'METADATA_FAILED');
    }
  }

  // Private helper methods

  private imageDataToBuffer(imageData: ImageData): Buffer {
    // Sharp expects raw pixel data
    return Buffer.from(imageData.data);
  }

  private async bufferToImageData(buffer: Buffer, info: any): Promise<ImageData> {
    // Convert Sharp output back to ImageData format
    const { data } = await this.sharp(buffer)
      .ensureAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });

    return {
      data: new Uint8Array(data),
      width: info.width,
      height: info.height,
      channels: info.channels,
      format: info.format || 'rgba',
    };
  }
}