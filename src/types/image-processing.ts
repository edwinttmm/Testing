/**
 * TypeScript definitions for image processing system
 */

export interface ImageProcessingCapabilities {
  resize: boolean;
  crop: boolean;
  rotate: boolean;
  filter: boolean;
  objectDetection: boolean;
  faceDetection: boolean;
  textRecognition: boolean;
  colorAnalysis: boolean;
  edgeDetection: boolean;
  backgroundRemoval: boolean;
}

export interface ImageProcessingOptions {
  quality?: number;
  format?: 'jpeg' | 'png' | 'webp' | 'avif';
  width?: number;
  height?: number;
  fit?: 'cover' | 'contain' | 'fill' | 'inside' | 'outside';
  position?: string;
  background?: string | { r: number; g: number; b: number; alpha?: number };
  blur?: number;
  sharpen?: boolean;
  brightness?: number;
  contrast?: number;
  saturation?: number;
  hue?: number;
  gamma?: number;
}

export interface ImageData {
  data: Uint8Array | Uint8ClampedArray | ArrayBuffer;
  width: number;
  height: number;
  channels: number;
  format: string;
  metadata?: {
    exif?: any;
    icc?: any;
    iptc?: any;
    xmp?: any;
  };
}

export interface ProcessingResult {
  success: boolean;
  data?: ImageData;
  metadata?: any;
  processingTime: number;
  library: string;
  backend: string;
  error?: string;
}

export interface DetectionResult {
  type: 'object' | 'face' | 'text' | 'edge';
  confidence: number;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  label?: string;
  properties?: Record<string, any>;
}

export interface AnalysisResult {
  dominantColors: Array<{
    color: { r: number; g: number; b: number };
    percentage: number;
    hex: string;
  }>;
  brightness: number;
  contrast: number;
  sharpness: number;
  dimensions: { width: number; height: number };
  fileSize: number;
  format: string;
}

// Library-specific interfaces
export interface TensorFlowProcessor {
  loadModel(modelUrl: string): Promise<any>;
  predict(imageData: ImageData, model: any): Promise<DetectionResult[]>;
  classifyImage(imageData: ImageData): Promise<Array<{ className: string; probability: number }>>;
  detectObjects(imageData: ImageData): Promise<DetectionResult[]>;
  resize(imageData: ImageData, width: number, height: number): Promise<ImageData>;
}

export interface OpenCVProcessor {
  load(imageData: ImageData): any; // cv.Mat
  resize(mat: any, width: number, height: number): any;
  crop(mat: any, x: number, y: number, width: number, height: number): any;
  rotate(mat: any, angle: number): any;
  applyFilter(mat: any, filter: string): any;
  detectEdges(mat: any): any;
  detectFaces(mat: any): DetectionResult[];
  toImageData(mat: any): ImageData;
}

export interface JimpProcessor {
  read(input: string | Buffer | ArrayBuffer): Promise<any>;
  resize(image: any, width: number, height: number): any;
  crop(image: any, x: number, y: number, width: number, height: number): any;
  rotate(image: any, angle: number): any;
  brightness(image: any, value: number): any;
  contrast(image: any, value: number): any;
  blur(image: any, radius: number): any;
  getBuffer(image: any, format: string): Promise<Buffer>;
}

export interface SharpProcessor {
  resize(options: { width?: number; height?: number; fit?: string }): any;
  crop(options: { left: number; top: number; width: number; height: number }): any;
  rotate(angle: number): any;
  blur(sigma?: number): any;
  sharpen(options?: { sigma?: number; flat?: number; jagged?: number }): any;
  modulate(options: { brightness?: number; saturation?: number; hue?: number }): any;
  toBuffer(options?: { format?: string; quality?: number }): Promise<Buffer>;
  metadata(): Promise<any>;
}

export interface CanvasProcessor {
  createCanvas(width: number, height: number): HTMLCanvasElement;
  getContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D;
  loadImage(source: string | ArrayBuffer): Promise<HTMLImageElement>;
  drawImage(ctx: CanvasRenderingContext2D, image: HTMLImageElement, options: any): void;
  getImageData(ctx: CanvasRenderingContext2D): ImageData;
  toBlob(canvas: HTMLCanvasElement, format?: string, quality?: number): Promise<Blob>;
}

// Unified processor interface
export interface ImageProcessor {
  readonly library: 'tensorflow' | 'opencv' | 'jimp' | 'sharp' | 'canvas';
  readonly capabilities: ImageProcessingCapabilities;
  readonly isGPUAccelerated: boolean;

  // Core operations
  resize(imageData: ImageData, options: { width: number; height: number }): Promise<ProcessingResult>;
  crop(imageData: ImageData, options: { x: number; y: number; width: number; height: number }): Promise<ProcessingResult>;
  rotate(imageData: ImageData, angle: number): Promise<ProcessingResult>;
  
  // Filters and adjustments
  applyFilter(imageData: ImageData, filter: string, intensity?: number): Promise<ProcessingResult>;
  adjustBrightness(imageData: ImageData, value: number): Promise<ProcessingResult>;
  adjustContrast(imageData: ImageData, value: number): Promise<ProcessingResult>;
  blur(imageData: ImageData, radius: number): Promise<ProcessingResult>;
  sharpen(imageData: ImageData, intensity?: number): Promise<ProcessingResult>;

  // Analysis and detection
  analyze(imageData: ImageData): Promise<AnalysisResult>;
  detectObjects(imageData: ImageData): Promise<DetectionResult[]>;
  detectFaces(imageData: ImageData): Promise<DetectionResult[]>;
  detectEdges(imageData: ImageData): Promise<ProcessingResult>;

  // Utility methods
  loadImage(source: string | ArrayBuffer | Buffer): Promise<ImageData>;
  saveImage(imageData: ImageData, options: ImageProcessingOptions): Promise<ArrayBuffer>;
  getMetadata(imageData: ImageData): Promise<any>;
}

// Environment and configuration types
export interface EnvironmentConfig {
  platform: 'web' | 'node';
  hasGPU: boolean;
  hasWebGL: boolean;
  hasWebGL2: boolean;
  supportedFormats: string[];
  maxImageSize: { width: number; height: number };
  memoryLimit: number;
  preferredLibrary?: string;
  fallbackLibrary?: string;
}

export interface LibraryStatus {
  name: string;
  loaded: boolean;
  version?: string;
  backend?: string;
  error?: string;
  capabilities: ImageProcessingCapabilities;
}

export interface ProcessorFactory {
  createProcessor(preferredLibrary?: string): Promise<ImageProcessor>;
  getAvailableProcessors(): Promise<LibraryStatus[]>;
  getBestProcessor(requirements?: Partial<ImageProcessingCapabilities>): Promise<ImageProcessor>;
}

// Error types
export class ImageProcessingError extends Error {
  constructor(
    message: string,
    public code: string,
    public library?: string,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'ImageProcessingError';
  }
}

export class LibraryLoadError extends Error {
  constructor(
    message: string,
    public library: string,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'LibraryLoadError';
  }
}

export class GPUNotAvailableError extends Error {
  constructor(message: string = 'GPU acceleration not available') {
    super(message);
    this.name = 'GPUNotAvailableError';
  }
}

// Event types for React integration
export interface ProcessingEvent {
  type: 'start' | 'progress' | 'complete' | 'error';
  progress?: number;
  result?: ProcessingResult;
  error?: string;
}

export type ProcessingEventHandler = (event: ProcessingEvent) => void;