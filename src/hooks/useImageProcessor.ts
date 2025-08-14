/**
 * React Hook for Image Processing
 * Provides easy access to image processing capabilities with GPU detection
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  type ImageProcessor, 
  type ProcessingResult, 
  type LibraryStatus,
  type ImageProcessingCapabilities,
  type AnalysisResult,
  type DetectionResult,
  type ProcessingEvent,
  type ProcessingEventHandler,
  ImageProcessingError 
} from '../types/image-processing';
import { imageProcessorFactory } from '../libs/image-processor-factory';
import { gpuDetector, type GPUCapabilities } from '../utils/gpu-detector';

export interface UseImageProcessorOptions {
  preferredLibrary?: string;
  requirements?: Partial<ImageProcessingCapabilities>;
  onProcessingEvent?: ProcessingEventHandler;
  autoInitialize?: boolean;
}

export interface UseImageProcessorResult {
  // State
  processor: ImageProcessor | null;
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;
  
  // GPU and capabilities info
  gpuCapabilities: GPUCapabilities | null;
  availableLibraries: LibraryStatus[];
  processorCapabilities: ImageProcessingCapabilities | null;
  
  // Processing methods
  processImage: (
    imageData: ImageData, 
    operation: string, 
    options?: any
  ) => Promise<ProcessingResult>;
  
  analyzeImage: (imageData: ImageData) => Promise<AnalysisResult>;
  detectObjects: (imageData: ImageData) => Promise<DetectionResult[]>;
  detectFaces: (imageData: ImageData) => Promise<DetectionResult[]>;
  
  // Utility methods
  loadImage: (source: string | ArrayBuffer | Buffer) => Promise<ImageData>;
  saveImage: (imageData: ImageData, options?: any) => Promise<ArrayBuffer>;
  
  // Control methods
  initialize: (options?: UseImageProcessorOptions) => Promise<void>;
  reinitialize: () => Promise<void>;
  switchProcessor: (library: string) => Promise<void>;
  
  // Performance tracking
  processingHistory: ProcessingEvent[];
  clearHistory: () => void;
}

export function useImageProcessor(
  options: UseImageProcessorOptions = {}
): UseImageProcessorResult {
  const {
    preferredLibrary,
    requirements,
    onProcessingEvent,
    autoInitialize = true,
  } = options;

  // State
  const [processor, setProcessor] = useState<ImageProcessor | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gpuCapabilities, setGpuCapabilities] = useState<GPUCapabilities | null>(null);
  const [availableLibraries, setAvailableLibraries] = useState<LibraryStatus[]>([]);
  const [processingHistory, setProcessingHistory] = useState<ProcessingEvent[]>([]);

  // Memoized processor capabilities
  const processorCapabilities = useMemo(() => {
    return processor?.capabilities || null;
  }, [processor]);

  // Event handler wrapper
  const handleProcessingEvent = useCallback((event: ProcessingEvent) => {
    setProcessingHistory(prev => [...prev.slice(-49), event]); // Keep last 50 events
    onProcessingEvent?.(event);
  }, [onProcessingEvent]);

  // Initialize processor
  const initialize = useCallback(async (initOptions?: UseImageProcessorOptions) => {
    const opts = { ...options, ...initOptions };
    
    setIsLoading(true);
    setError(null);
    
    try {
      handleProcessingEvent({ type: 'start' });

      // Detect GPU capabilities
      const capabilities = await gpuDetector.detectCapabilities();
      setGpuCapabilities(capabilities);

      // Get available libraries
      const libraries = await imageProcessorFactory.getAvailableProcessors();
      setAvailableLibraries(libraries);

      // Create processor
      const newProcessor = opts.requirements
        ? await imageProcessorFactory.getBestProcessor(opts.requirements)
        : await imageProcessorFactory.createProcessor(opts.preferredLibrary);

      setProcessor(newProcessor);
      setIsInitialized(true);
      
      handleProcessingEvent({ 
        type: 'complete',
        result: {
          success: true,
          processingTime: 0,
          library: newProcessor.library,
          backend: newProcessor.isGPUAccelerated ? 'GPU' : 'CPU',
        }
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      handleProcessingEvent({ 
        type: 'error', 
        error: errorMessage 
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, handleProcessingEvent]);

  // Reinitialize processor
  const reinitialize = useCallback(async () => {
    setIsInitialized(false);
    setProcessor(null);
    await imageProcessorFactory.refresh();
    await initialize();
  }, [initialize]);

  // Switch to different processor
  const switchProcessor = useCallback(async (library: string) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const newProcessor = await imageProcessorFactory.createProcessor(library);
      setProcessor(newProcessor);
      
      handleProcessingEvent({
        type: 'complete',
        result: {
          success: true,
          processingTime: 0,
          library: newProcessor.library,
          backend: newProcessor.isGPUAccelerated ? 'GPU' : 'CPU',
        }
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      handleProcessingEvent({ type: 'error', error: errorMessage });
    } finally {
      setIsLoading(false);
    }
  }, [handleProcessingEvent]);

  // Generic image processing method
  const processImage = useCallback(async (
    imageData: ImageData, 
    operation: string, 
    options: any = {}
  ): Promise<ProcessingResult> => {
    if (!processor) {
      throw new ImageProcessingError('Processor not initialized', 'NOT_INITIALIZED');
    }

    handleProcessingEvent({ type: 'start' });

    try {
      let result: ProcessingResult;

      switch (operation.toLowerCase()) {
        case 'resize':
          result = await processor.resize(imageData, options);
          break;
        case 'crop':
          result = await processor.crop(imageData, options);
          break;
        case 'rotate':
          result = await processor.rotate(imageData, options.angle || 0);
          break;
        case 'blur':
          result = await processor.blur(imageData, options.radius || 5);
          break;
        case 'sharpen':
          result = await processor.sharpen(imageData, options.intensity);
          break;
        case 'brightness':
          result = await processor.adjustBrightness(imageData, options.value || 0);
          break;
        case 'contrast':
          result = await processor.adjustContrast(imageData, options.value || 0);
          break;
        case 'filter':
          result = await processor.applyFilter(imageData, options.filter, options.intensity);
          break;
        case 'edges':
          result = await processor.detectEdges(imageData);
          break;
        default:
          throw new ImageProcessingError(`Unknown operation: ${operation}`, 'UNKNOWN_OPERATION');
      }

      handleProcessingEvent({ type: 'complete', result });
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      const result: ProcessingResult = {
        success: false,
        processingTime: 0,
        library: processor.library,
        backend: processor.isGPUAccelerated ? 'GPU' : 'CPU',
        error: errorMessage,
      };
      
      handleProcessingEvent({ type: 'error', error: errorMessage, result });
      return result;
    }
  }, [processor, handleProcessingEvent]);

  // Analyze image
  const analyzeImage = useCallback(async (imageData: ImageData): Promise<AnalysisResult> => {
    if (!processor) {
      throw new ImageProcessingError('Processor not initialized', 'NOT_INITIALIZED');
    }

    handleProcessingEvent({ type: 'start' });

    try {
      const result = await processor.analyze(imageData);
      handleProcessingEvent({ 
        type: 'complete', 
        result: { 
          success: true, 
          processingTime: 0, 
          library: processor.library, 
          backend: processor.isGPUAccelerated ? 'GPU' : 'CPU' 
        } 
      });
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      handleProcessingEvent({ type: 'error', error: errorMessage });
      throw err;
    }
  }, [processor, handleProcessingEvent]);

  // Detect objects
  const detectObjects = useCallback(async (imageData: ImageData): Promise<DetectionResult[]> => {
    if (!processor) {
      throw new ImageProcessingError('Processor not initialized', 'NOT_INITIALIZED');
    }

    handleProcessingEvent({ type: 'start' });

    try {
      const results = await processor.detectObjects(imageData);
      handleProcessingEvent({ 
        type: 'complete', 
        result: { 
          success: true, 
          processingTime: 0, 
          library: processor.library, 
          backend: processor.isGPUAccelerated ? 'GPU' : 'CPU' 
        } 
      });
      return results;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      handleProcessingEvent({ type: 'error', error: errorMessage });
      throw err;
    }
  }, [processor, handleProcessingEvent]);

  // Detect faces
  const detectFaces = useCallback(async (imageData: ImageData): Promise<DetectionResult[]> => {
    if (!processor) {
      throw new ImageProcessingError('Processor not initialized', 'NOT_INITIALIZED');
    }

    handleProcessingEvent({ type: 'start' });

    try {
      const results = await processor.detectFaces(imageData);
      handleProcessingEvent({ 
        type: 'complete', 
        result: { 
          success: true, 
          processingTime: 0, 
          library: processor.library, 
          backend: processor.isGPUAccelerated ? 'GPU' : 'CPU' 
        } 
      });
      return results;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      handleProcessingEvent({ type: 'error', error: errorMessage });
      throw err;
    }
  }, [processor, handleProcessingEvent]);

  // Load image
  const loadImage = useCallback(async (source: string | ArrayBuffer | Buffer): Promise<ImageData> => {
    if (!processor) {
      throw new ImageProcessingError('Processor not initialized', 'NOT_INITIALIZED');
    }

    return await processor.loadImage(source);
  }, [processor]);

  // Save image
  const saveImage = useCallback(async (imageData: ImageData, saveOptions: any = {}): Promise<ArrayBuffer> => {
    if (!processor) {
      throw new ImageProcessingError('Processor not initialized', 'NOT_INITIALIZED');
    }

    return await processor.saveImage(imageData, saveOptions);
  }, [processor]);

  // Clear processing history
  const clearHistory = useCallback(() => {
    setProcessingHistory([]);
  }, []);

  // Auto-initialize on mount
  useEffect(() => {
    if (autoInitialize && !isInitialized && !isLoading) {
      initialize();
    }
  }, [autoInitialize, isInitialized, isLoading, initialize]);

  return {
    // State
    processor,
    isLoading,
    isInitialized,
    error,
    
    // Capabilities and info
    gpuCapabilities,
    availableLibraries,
    processorCapabilities,
    
    // Processing methods
    processImage,
    analyzeImage,
    detectObjects,
    detectFaces,
    
    // Utility methods
    loadImage,
    saveImage,
    
    // Control methods
    initialize,
    reinitialize,
    switchProcessor,
    
    // Performance tracking
    processingHistory,
    clearHistory,
  };
}