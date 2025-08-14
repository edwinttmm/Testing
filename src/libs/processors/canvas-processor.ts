/**
 * Canvas Image Processor
 * Basic image processing using HTML5 Canvas API (CPU-only fallback)
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

export class CanvasImageProcessor implements ImageProcessor {
  readonly library = 'canvas' as const;
  readonly isGPUAccelerated = false;
  readonly capabilities: ImageProcessingCapabilities = {
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
  };

  constructor(private canvasUtils: any) {}

  /**
   * Resize image using Canvas
   */
  async resize(
    imageData: ImageData,
    options: { width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const canvas = this.canvasUtils.createElement(options.width, options.height);
      const ctx = this.canvasUtils.getContext(canvas);

      // Create source canvas
      const sourceCanvas = this.canvasUtils.createElement(imageData.width, imageData.height);
      const sourceCtx = this.canvasUtils.getContext(sourceCanvas);

      // Put original image data
      const canvasImageData = new window.ImageData(
        new Uint8ClampedArray(imageData.data),
        imageData.width,
        imageData.height
      );
      sourceCtx.putImageData(canvasImageData, 0, 0);

      // Draw resized image
      ctx.drawImage(sourceCanvas, 0, 0, options.width, options.height);

      // Get result
      const resultImageData = ctx.getImageData(0, 0, options.width, options.height);
      const result = this.canvasImageDataToImageData(resultImageData);

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
   * Crop image using Canvas
   */
  async crop(
    imageData: ImageData,
    options: { x: number; y: number; width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const canvas = this.canvasUtils.createElement(options.width, options.height);
      const ctx = this.canvasUtils.getContext(canvas);

      // Create source canvas
      const sourceCanvas = this.canvasUtils.createElement(imageData.width, imageData.height);
      const sourceCtx = this.canvasUtils.getContext(sourceCanvas);

      // Put original image data
      const canvasImageData = new window.ImageData(
        new Uint8ClampedArray(imageData.data),
        imageData.width,
        imageData.height
      );
      sourceCtx.putImageData(canvasImageData, 0, 0);

      // Draw cropped image
      ctx.drawImage(
        sourceCanvas,
        options.x, options.y, options.width, options.height,
        0, 0, options.width, options.height
      );

      // Get result
      const resultImageData = ctx.getImageData(0, 0, options.width, options.height);
      const result = this.canvasImageDataToImageData(resultImageData);

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
   * Rotate image using Canvas
   */
  async rotate(imageData: ImageData, angle: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      // Calculate new dimensions after rotation
      const radians = (angle * Math.PI) / 180;
      const cos = Math.abs(Math.cos(radians));
      const sin = Math.abs(Math.sin(radians));
      const newWidth = Math.ceil(imageData.width * cos + imageData.height * sin);
      const newHeight = Math.ceil(imageData.width * sin + imageData.height * cos);

      const canvas = this.canvasUtils.createElement(newWidth, newHeight);
      const ctx = this.canvasUtils.getContext(canvas);

      // Create source canvas
      const sourceCanvas = this.canvasUtils.createElement(imageData.width, imageData.height);
      const sourceCtx = this.canvasUtils.getContext(sourceCanvas);

      // Put original image data
      const canvasImageData = new window.ImageData(
        new Uint8ClampedArray(imageData.data),
        imageData.width,
        imageData.height
      );
      sourceCtx.putImageData(canvasImageData, 0, 0);

      // Rotate and draw
      ctx.translate(newWidth / 2, newHeight / 2);
      ctx.rotate(radians);
      ctx.drawImage(sourceCanvas, -imageData.width / 2, -imageData.height / 2);

      // Get result
      const resultImageData = ctx.getImageData(0, 0, newWidth, newHeight);
      const result = this.canvasImageDataToImageData(resultImageData);

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
   * Apply filter (limited support)
   */
  async applyFilter(
    imageData: ImageData,
    filter: string,
    intensity: number = 1.0
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const canvas = this.canvasUtils.createElement(imageData.width, imageData.height);
      const ctx = this.canvasUtils.getContext(canvas);

      // Put original image data
      const canvasImageData = new window.ImageData(
        new Uint8ClampedArray(imageData.data),
        imageData.width,
        imageData.height
      );
      ctx.putImageData(canvasImageData, 0, 0);

      // Apply CSS filters (limited browser support)
      switch (filter.toLowerCase()) {
        case 'blur':
          ctx.filter = `blur(${intensity * 5}px)`;
          break;
        case 'brightness':
          ctx.filter = `brightness(${1 + intensity})`;
          break;
        case 'contrast':
          ctx.filter = `contrast(${1 + intensity})`;
          break;
        case 'grayscale':
          ctx.filter = 'grayscale(100%)';
          break;
        case 'sepia':
          ctx.filter = 'sepia(100%)';
          break;
        case 'invert':
          ctx.filter = 'invert(100%)';
          break;
        default:
          throw new Error(`Filter ${filter} not supported by Canvas processor`);
      }

      // Redraw with filter
      ctx.drawImage(canvas, 0, 0);

      // Get result
      const resultImageData = ctx.getImageData(0, 0, imageData.width, imageData.height);
      const result = this.canvasImageDataToImageData(resultImageData);

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
   * Adjust brightness using Canvas
   */
  async adjustBrightness(imageData: ImageData, value: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const data = new Uint8ClampedArray(imageData.data);
      const adjustment = value * 255;

      // Apply brightness adjustment pixel by pixel
      for (let i = 0; i < data.length; i += 4) {
        data[i] = Math.max(0, Math.min(255, data[i] + adjustment));     // R
        data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + adjustment)); // G
        data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + adjustment)); // B
        // Alpha channel (i + 3) remains unchanged
      }

      const result: ImageData = {
        data,
        width: imageData.width,
        height: imageData.height,
        channels: imageData.channels,
        format: imageData.format,
      };

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
   * Adjust contrast using Canvas
   */
  async adjustContrast(imageData: ImageData, value: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const data = new Uint8ClampedArray(imageData.data);
      const factor = (259 * (value * 255 + 255)) / (255 * (259 - value * 255));

      // Apply contrast adjustment pixel by pixel
      for (let i = 0; i < data.length; i += 4) {
        data[i] = Math.max(0, Math.min(255, factor * (data[i] - 128) + 128));         // R
        data[i + 1] = Math.max(0, Math.min(255, factor * (data[i + 1] - 128) + 128)); // G
        data[i + 2] = Math.max(0, Math.min(255, factor * (data[i + 2] - 128) + 128)); // B
        // Alpha channel (i + 3) remains unchanged
      }

      const result: ImageData = {
        data,
        width: imageData.width,
        height: imageData.height,
        channels: imageData.channels,
        format: imageData.format,
      };

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
   * Blur image (limited support)
   */
  async blur(imageData: ImageData, radius: number): Promise<ProcessingResult> {
    return this.applyFilter(imageData, 'blur', radius / 5);
  }

  /**
   * Sharpen image (not supported)
   */
  async sharpen(imageData: ImageData, intensity?: number): Promise<ProcessingResult> {
    return {
      success: false,
      processingTime: 0,
      library: this.library,
      backend: 'CPU',
      error: 'Sharpen not supported by Canvas processor',
    };
  }

  /**
   * Analyze image colors and properties
   */
  async analyze(imageData: ImageData): Promise<AnalysisResult> {
    const data = imageData.data;
    const colorCounts = new Map<string, number>();
    let totalPixels = 0;
    let brightnessSum = 0;

    // Analyze pixels
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      
      // Calculate brightness (luminance)
      const brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      brightnessSum += brightness;
      totalPixels++;

      // Quantize colors for dominant color calculation
      const quantizedR = Math.floor(r / 32) * 32;
      const quantizedG = Math.floor(g / 32) * 32;
      const quantizedB = Math.floor(b / 32) * 32;
      const colorKey = `${quantizedR},${quantizedG},${quantizedB}`;
      
      colorCounts.set(colorKey, (colorCounts.get(colorKey) || 0) + 1);
    }

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

    const averageBrightness = brightnessSum / totalPixels;

    return {
      dominantColors,
      brightness: averageBrightness,
      contrast: 0.5, // Placeholder
      sharpness: 0.5, // Placeholder
      dimensions: { width: imageData.width, height: imageData.height },
      fileSize: imageData.data.length,
      format: imageData.format || 'unknown',
    };
  }

  /**
   * Object detection (not supported)
   */
  async detectObjects(imageData: ImageData): Promise<DetectionResult[]> {
    console.warn('Object detection not supported by Canvas processor');
    return [];
  }

  /**
   * Face detection (not supported)
   */
  async detectFaces(imageData: ImageData): Promise<DetectionResult[]> {
    console.warn('Face detection not supported by Canvas processor');
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
      error: 'Edge detection not supported by Canvas processor',
    };
  }

  /**
   * Load image from URL
   */
  async loadImage(source: string | ArrayBuffer | Buffer): Promise<ImageData> {
    if (typeof source === 'string') {
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          const canvas = this.canvasUtils.createElement(img.width, img.height);
          const ctx = this.canvasUtils.getContext(canvas);
          ctx.drawImage(img, 0, 0);
          
          const imageData = ctx.getImageData(0, 0, img.width, img.height);
          resolve(this.canvasImageDataToImageData(imageData));
        };
        img.onerror = reject;
        img.src = source;
      });
    } else {
      throw new ImageProcessingError(
        'Loading from ArrayBuffer/Buffer not implemented for Canvas processor',
        'NOT_IMPLEMENTED'
      );
    }
  }

  /**
   * Save image as blob
   */
  async saveImage(imageData: ImageData, options: ImageProcessingOptions): Promise<ArrayBuffer> {
    const canvas = this.canvasUtils.createElement(imageData.width, imageData.height);
    const ctx = this.canvasUtils.getContext(canvas);

    const canvasImageData = new window.ImageData(
      new Uint8ClampedArray(imageData.data),
      imageData.width,
      imageData.height
    );
    ctx.putImageData(canvasImageData, 0, 0);

    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob: Blob | null) => {
          if (blob) {
            blob.arrayBuffer().then(resolve).catch(reject);
          } else {
            reject(new Error('Failed to create blob'));
          }
        },
        `image/${options.format || 'png'}`,
        options.quality || 0.9
      );
    });
  }

  /**
   * Get image metadata (basic)
   */
  async getMetadata(imageData: ImageData): Promise<any> {
    return {
      width: imageData.width,
      height: imageData.height,
      channels: imageData.channels,
      format: imageData.format,
      hasAlpha: imageData.channels === 4,
    };
  }

  // Private helper methods

  private canvasImageDataToImageData(canvasImageData: globalThis.ImageData): ImageData {
    return {
      data: new Uint8Array(canvasImageData.data),
      width: canvasImageData.width,
      height: canvasImageData.height,
      channels: 4,
      format: 'rgba',
    };
  }
}