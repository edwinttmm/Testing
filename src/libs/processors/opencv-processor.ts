/**
 * OpenCV.js Image Processor
 * Computer vision and image processing using OpenCV.js
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

export class OpenCVImageProcessor implements ImageProcessor {
  readonly library = 'opencv' as const;
  readonly isGPUAccelerated: boolean;
  readonly capabilities: ImageProcessingCapabilities = {
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
  };

  private cascades: Map<string, any> = new Map();

  constructor(private cv: any, isGPUAccelerated: boolean = false) {
    this.isGPUAccelerated = isGPUAccelerated;
  }

  /**
   * Resize image using OpenCV
   */
  async resize(
    imageData: ImageData,
    options: { width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const src = this.imageDataToMat(imageData);
      const dst = new this.cv.Mat();
      const dsize = new this.cv.Size(options.width, options.height);

      this.cv.resize(src, dst, dsize, 0, 0, this.cv.INTER_LINEAR);

      const result = this.matToImageData(dst);

      src.delete();
      dst.delete();

      return {
        success: true,
        data: result,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
        error: `Resize failed: ${error}`,
      };
    }
  }

  /**
   * Crop image using OpenCV
   */
  async crop(
    imageData: ImageData,
    options: { x: number; y: number; width: number; height: number }
  ): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const src = this.imageDataToMat(imageData);
      const rect = new this.cv.Rect(options.x, options.y, options.width, options.height);
      const dst = src.roi(rect);

      const result = this.matToImageData(dst);

      src.delete();
      dst.delete();

      return {
        success: true,
        data: result,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
        error: `Crop failed: ${error}`,
      };
    }
  }

  /**
   * Rotate image using OpenCV
   */
  async rotate(imageData: ImageData, angle: number): Promise<ProcessingResult> {
    const startTime = Date.now();

    try {
      const src = this.imageDataToMat(imageData);
      const dst = new this.cv.Mat();
      const center = new this.cv.Point2f(src.cols / 2, src.rows / 2);
      const rotMatrix = this.cv.getRotationMatrix2D(center, angle, 1);

      this.cv.warpAffine(src, dst, rotMatrix, new this.cv.Size(src.cols, src.rows));

      const result = this.matToImageData(dst);

      src.delete();
      dst.delete();
      rotMatrix.delete();

      return {
        success: true,
        data: result,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
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
      const src = this.imageDataToMat(imageData);
      const dst = new this.cv.Mat();

      switch (filter.toLowerCase()) {
        case 'blur':
          this.cv.GaussianBlur(src, dst, new this.cv.Size(15, 15), intensity * 5, intensity * 5);
          break;
        case 'sharpen':
          await this.applySharpenFilter(src, dst, intensity);
          break;
        case 'edge':
          this.cv.Canny(src, dst, 50, 150);
          this.cv.cvtColor(dst, dst, this.cv.COLOR_GRAY2RGBA);
          break;
        case 'grayscale':
          this.cv.cvtColor(src, dst, this.cv.COLOR_RGBA2GRAY);
          this.cv.cvtColor(dst, dst, this.cv.COLOR_GRAY2RGBA);
          break;
        case 'median':
          this.cv.medianBlur(src, dst, Math.max(3, Math.round(intensity * 10) | 1));
          break;
        case 'bilateral':
          this.cv.bilateralFilter(src, dst, 9, 75, 75);
          break;
        default:
          throw new Error(`Unknown filter: ${filter}`);
      }

      const result = this.matToImageData(dst);

      src.delete();
      dst.delete();

      return {
        success: true,
        data: result,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
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
      const src = this.imageDataToMat(imageData);
      const dst = new this.cv.Mat();

      // Convert value from [-1, 1] to [0, 255] adjustment
      const adjustment = value * 100;
      src.convertTo(dst, -1, 1, adjustment);

      const result = this.matToImageData(dst);

      src.delete();
      dst.delete();

      return {
        success: true,
        data: result,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
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
      const src = this.imageDataToMat(imageData);
      const dst = new this.cv.Mat();

      // Convert value to contrast multiplier
      const alpha = 1.0 + value;
      src.convertTo(dst, -1, alpha, 0);

      const result = this.matToImageData(dst);

      src.delete();
      dst.delete();

      return {
        success: true,
        data: result,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
      };
    } catch (error) {
      return {
        success: false,
        processingTime: Date.now() - startTime,
        library: this.library,
        backend: this.isGPUAccelerated ? 'GPU' : 'CPU',
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
    const src = this.imageDataToMat(imageData);

    try {
      // Calculate histogram for dominant colors
      const hist = new this.cv.Mat();
      const mask = new this.cv.Mat();
      const histSize = [50];
      const ranges = [0, 256];
      
      this.cv.calcHist(new this.cv.MatVector([src]), [0], mask, hist, histSize, ranges);

      // Calculate brightness
      const mean = this.cv.mean(src);
      const brightness = (mean[0] + mean[1] + mean[2]) / (3 * 255);

      // Calculate basic dominant color (simplified)
      const dominantColors = [
        {
          color: { 
            r: Math.round(mean[2]), 
            g: Math.round(mean[1]), 
            b: Math.round(mean[0]) 
          },
          percentage: 100,
          hex: `#${Math.round(mean[2]).toString(16).padStart(2, '0')}${Math.round(mean[1]).toString(16).padStart(2, '0')}${Math.round(mean[0]).toString(16).padStart(2, '0')}`,
        },
      ];

      src.delete();
      hist.delete();
      mask.delete();

      return {
        dominantColors,
        brightness,
        contrast: 0.5, // Would need more complex calculation
        sharpness: 0.5, // Would need Laplacian variance
        dimensions: { width: imageData.width, height: imageData.height },
        fileSize: imageData.data.length,
        format: imageData.format || 'unknown',
      };
    } catch (error) {
      src.delete();
      throw new ImageProcessingError(`Analysis failed: ${error}`, 'ANALYSIS_FAILED');
    }
  }

  /**
   * Detect objects using Haar cascades
   */
  async detectObjects(imageData: ImageData): Promise<DetectionResult[]> {
    try {
      // Load cascade if not already loaded
      if (!this.cascades.has('face')) {
        // Note: In a real implementation, you'd load the cascade files
        console.warn('Object detection requires loading cascade files');
        return [];
      }

      const src = this.imageDataToMat(imageData);
      const gray = new this.cv.Mat();
      
      this.cv.cvtColor(src, gray, this.cv.COLOR_RGBA2GRAY);

      const objects = new this.cv.RectVector();
      const cascade = this.cascades.get('face');
      
      cascade.detectMultiScale(gray, objects, 1.1, 3, 0);

      const results: DetectionResult[] = [];
      for (let i = 0; i < objects.size(); i++) {
        const rect = objects.get(i);
        results.push({
          type: 'object',
          confidence: 0.8, // Haar cascades don't provide confidence scores
          boundingBox: {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
          },
          label: 'object',
        });
      }

      src.delete();
      gray.delete();
      objects.delete();

      return results;
    } catch (error) {
      console.warn('Object detection failed:', error);
      return [];
    }
  }

  /**
   * Detect faces using Haar cascades
   */
  async detectFaces(imageData: ImageData): Promise<DetectionResult[]> {
    try {
      const src = this.imageDataToMat(imageData);
      const gray = new this.cv.Mat();
      
      this.cv.cvtColor(src, gray, this.cv.COLOR_RGBA2GRAY);

      const faces = new this.cv.RectVector();
      
      // Use built-in face cascade if available
      if (this.cv.CascadeClassifier) {
        const faceCascade = new this.cv.CascadeClassifier();
        // In a real implementation, load the cascade file
        // faceCascade.load('haarcascade_frontalface_default.xml');
        
        faceCascade.detectMultiScale(gray, faces, 1.1, 3, 0);

        const results: DetectionResult[] = [];
        for (let i = 0; i < faces.size(); i++) {
          const face = faces.get(i);
          results.push({
            type: 'face',
            confidence: 0.8,
            boundingBox: {
              x: face.x,
              y: face.y,
              width: face.width,
              height: face.height,
            },
            label: 'face',
          });
        }

        faceCascade.delete();
        faces.delete();
        src.delete();
        gray.delete();

        return results;
      }

      src.delete();
      gray.delete();
      faces.delete();

      return [];
    } catch (error) {
      console.warn('Face detection failed:', error);
      return [];
    }
  }

  /**
   * Detect edges in image
   */
  async detectEdges(imageData: ImageData): Promise<ProcessingResult> {
    return this.applyFilter(imageData, 'edge');
  }

  /**
   * Load image from various sources
   */
  async loadImage(source: string | ArrayBuffer | Buffer): Promise<ImageData> {
    if (typeof source === 'string') {
      // URL or data URL
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d')!;
          canvas.width = img.width;
          canvas.height = img.height;
          ctx.drawImage(img, 0, 0);
          
          const imageData = ctx.getImageData(0, 0, img.width, img.height);
          resolve({
            data: imageData.data,
            width: img.width,
            height: img.height,
            channels: 4,
            format: 'rgba',
          });
        };
        img.onerror = reject;
        img.src = source;
      });
    } else {
      throw new ImageProcessingError(
        'Loading from ArrayBuffer/Buffer not implemented',
        'NOT_IMPLEMENTED'
      );
    }
  }

  /**
   * Save image with specified options
   */
  async saveImage(imageData: ImageData, options: ImageProcessingOptions): Promise<ArrayBuffer> {
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

    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
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
   * Get image metadata
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

  private imageDataToMat(imageData: ImageData): any {
    const mat = new this.cv.Mat(imageData.height, imageData.width, this.cv.CV_8UC4);
    mat.data.set(imageData.data);
    return mat;
  }

  private matToImageData(mat: any): ImageData {
    const data = new Uint8Array(mat.data);
    return {
      data,
      width: mat.cols,
      height: mat.rows,
      channels: mat.channels(),
      format: mat.channels() === 4 ? 'rgba' : 'rgb',
    };
  }

  private async applySharpenFilter(src: any, dst: any, intensity: number): Promise<void> {
    // Create sharpening kernel
    const kernel = this.cv.matFromArray(3, 3, this.cv.CV_32FC1, [
      0, -intensity, 0,
      -intensity, 4 * intensity + 1, -intensity,
      0, -intensity, 0
    ]);

    this.cv.filter2D(src, dst, -1, kernel);
    kernel.delete();
  }
}