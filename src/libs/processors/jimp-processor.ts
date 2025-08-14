/**
 * Jimp Image Processor
 * CPU-only image processing using Jimp library
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

export class JimpImageProcessor implements ImageProcessor {
  readonly library = 'jimp' as const;
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

  constructor(private Jimp: any) {}

  /**
   * Resize image using Jimp
   */
  async resize(
    imageData: ImageData,
    options: { width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      const image = await this.Jimp.read(buffer);
      
      image.resize(options.width, options.height);
      
      const result = await this.jimpToImageData(image);

      return {
        success: true,
        data: result,
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
   * Crop image using Jimp
   */
  async crop(
    imageData: ImageData,
    options: { x: number; y: number; width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      const image = await this.Jimp.read(buffer);
      
      image.crop(options.x, options.y, options.width, options.height);
      
      const result = await this.jimpToImageData(image);

      return {
        success: true,
        data: result,
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
   * Rotate image using Jimp
   */
  async rotate(imageData: ImageData, angle: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const buffer = this.imageDataToBuffer(imageData);
      const image = await this.Jimp.read(buffer);
      
      image.rotate(angle);
      
      const result = await this.jimpToImageData(image);

      return {
        success: true,
        data: result,
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
      const image = await this.Jimp.read(buffer);

      switch (filter.toLowerCase()) {
        case 'blur':
          image.blur(Math.max(1, intensity * 10));
          break;
        case 'sharpen':
          // Jimp doesn't have built-in sharpen, simulate with negative blur
          image.convolute([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
          ]);
          break;
        case 'grayscale':
          image.greyscale();
          break;
        case 'sepia':
          image.sepia();
          break;
        case 'invert':
          image.invert();
          break;
        case 'posterize':
          image.posterize(Math.max(2, Math.round(intensity * 10)));
          break;
        default:
          throw new Error(`Unknown filter: ${filter}`);
      }

      const result = await this.jimpToImageData(image);

      return {
        success: true,
        data: result,
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
      const image = await this.Jimp.read(buffer);
      
      // Convert value from [-1, 1] to Jimp's expected range
      const adjustment = value * 100;
      image.brightness(adjustment);
      
      const result = await this.jimpToImageData(image);

      return {
        success: true,
        data: result,
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
      const image = await this.Jimp.read(buffer);
      
      // Convert value to Jimp's expected range
      const adjustment = value * 100;
      image.contrast(adjustment);
      
      const result = await this.jimpToImageData(image);

      return {
        success: true,
        data: result,
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
    return this.applyFilter(imageData, 'blur', radius / 10);
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
      const image = await this.Jimp.read(buffer);

      // Calculate basic statistics
      const colorCounts = new Map<string, number>();
      let totalPixels = 0;
      let brightnesSum = 0;

      image.scan(0, 0, image.bitmap.width, image.bitmap.height, function(x, y, idx) {
        const red = this.bitmap.data[idx + 0];
        const green = this.bitmap.data[idx + 1];
        const blue = this.bitmap.data[idx + 2];
        
        // Calculate brightness (luminance)
        const brightness = (0.299 * red + 0.587 * green + 0.114 * blue) / 255;
        brightnesSum += brightness;
        totalPixels++;

        // Quantize colors for dominant color calculation
        const quantizedR = Math.floor(red / 32) * 32;
        const quantizedG = Math.floor(green / 32) * 32;
        const quantizedB = Math.floor(blue / 32) * 32;
        const colorKey = `${quantizedR},${quantizedG},${quantizedB}`;
        
        colorCounts.set(colorKey, (colorCounts.get(colorKey) || 0) + 1);
      });

      // Find dominant colors
      const sortedColors = Array.from(colorCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

      const dominantColors = sortedColors.map(([colorKey, count]) => {
        const [r, g, b] = colorKey.split(',').map(Number);
        const percentage = (count / totalPixels) * 100;
        const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
        
        return {
          color: { r, g, b },
          percentage,
          hex,
        };
      });

      const averageBrightness = brightnesSum / totalPixels;

      return {
        dominantColors,
        brightness: averageBrightness,
        contrast: 0.5, // Placeholder - would need more complex calculation
        sharpness: 0.5, // Placeholder - would need edge detection
        dimensions: { width: imageData.width, height: imageData.height },
        fileSize: imageData.data.length,
        format: imageData.format || 'unknown',
      };
    } catch (error) {
      throw new ImageProcessingError(`Analysis failed: ${error}`, 'ANALYSIS_FAILED');
    }
  }

  /**
   * Object detection (not supported)
   */
  async detectObjects(imageData: ImageData): Promise<DetectionResult[]> {
    console.warn('Object detection not supported by Jimp processor');
    return [];
  }

  /**
   * Face detection (not supported)
   */
  async detectFaces(imageData: ImageData): Promise<DetectionResult[]> {
    console.warn('Face detection not supported by Jimp processor');
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
      error: 'Edge detection not supported by Jimp processor',
    };
  }

  /**
   * Load image from various sources
   */
  async loadImage(source: string | ArrayBuffer | Buffer): Promise<ImageData> {
    try {
      const image = await this.Jimp.read(source);
      return this.jimpToImageData(image);
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
      const image = await this.Jimp.read(buffer);

      // Apply quality if specified
      if (options.quality !== undefined) {
        image.quality(Math.round(options.quality * 100));
      }

      // Determine format
      const format = options.format || 'png';
      const mimeType = `image/${format}`;

      const outputBuffer = await image.getBufferAsync(mimeType);
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
      const image = await this.Jimp.read(buffer);

      return {
        width: image.bitmap.width,
        height: image.bitmap.height,
        channels: image.bitmap.channels || 4,
        format: imageData.format,
        hasAlpha: image.hasAlpha(),
        colorType: image.getColorType(),
      };
    } catch (error) {
      throw new ImageProcessingError(`Failed to get metadata: ${error}`, 'METADATA_FAILED');
    }
  }

  // Private helper methods

  private imageDataToBuffer(imageData: ImageData): Buffer {
    // Create a simple PNG-like buffer from ImageData
    // In a real implementation, you might want to use a proper image encoder
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    canvas.width = imageData.width;
    canvas.height = imageData.height;

    const canvasImageData = new window.ImageData(
      new Uint8ClampedArray(imageData.data),
      imageData.width,
      imageData.height
    );
    ctx.putImageData(canvasImageData, 0, 0);

    // Convert canvas to buffer (this is a simplified approach)
    const dataURL = canvas.toDataURL('image/png');
    const base64 = dataURL.split(',')[1];
    
    if (typeof Buffer !== 'undefined') {
      return Buffer.from(base64, 'base64');
    } else {
      // Fallback for environments without Buffer
      const binaryString = atob(base64);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      return bytes as any;
    }
  }

  private async jimpToImageData(image: any): Promise<ImageData> {
    const { width, height } = image.bitmap;
    const data = new Uint8Array(image.bitmap.data);

    return {
      data,
      width,
      height,
      channels: image.bitmap.channels || 4,
      format: 'rgba',
    };
  }
}