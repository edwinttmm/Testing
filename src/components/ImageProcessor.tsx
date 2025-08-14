/**
 * React Component for Image Processing
 * Provides a complete image processing interface with GPU detection
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useImageProcessor } from '../hooks/useImageProcessor';
import type { ImageData, ProcessingResult, DetectionResult } from '../types/image-processing';

interface ImageProcessorProps {
  className?: string;
  onImageLoaded?: (imageData: ImageData) => void;
  onProcessingComplete?: (result: ProcessingResult) => void;
  onError?: (error: string) => void;
  enableDragDrop?: boolean;
  enablePreview?: boolean;
  showControls?: boolean;
  showCapabilities?: boolean;
  maxWidth?: number;
  maxHeight?: number;
}

export const ImageProcessor: React.FC<ImageProcessorProps> = ({
  className = '',
  onImageLoaded,
  onProcessingComplete,
  onError,
  enableDragDrop = true,
  enablePreview = true,
  showControls = true,
  showCapabilities = true,
  maxWidth = 800,
  maxHeight = 600,
}) => {
  // Image processor hook
  const {
    processor,
    isLoading,
    isInitialized,
    error: processorError,
    gpuCapabilities,
    availableLibraries,
    processorCapabilities,
    processImage,
    analyzeImage,
    detectObjects,
    detectFaces,
    loadImage,
    saveImage,
    switchProcessor,
  } = useImageProcessor({
    autoInitialize: true,
    onProcessingEvent: (event) => {
      if (event.type === 'error' && event.error) {
        onError?.(event.error);
      } else if (event.type === 'complete' && event.result) {
        onProcessingComplete?.(event.result);
      }
    },
  });

  // Local state
  const [currentImage, setCurrentImage] = useState<ImageData | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [processingOperation, setProcessingOperation] = useState<string>('');
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [detectionResults, setDetectionResults] = useState<DetectionResult[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Handle file selection
  const handleFileSelect = useCallback(async (file: File) => {
    if (!processor) return;

    try {
      const url = URL.createObjectURL(file);
      const imageData = await loadImage(url);
      
      setCurrentImage(imageData);
      updatePreview(imageData);
      onImageLoaded?.(imageData);
      
      URL.revokeObjectURL(url);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load image';
      onError?.(errorMessage);
    }
  }, [processor, loadImage, onImageLoaded, onError]);

  // Update preview canvas
  const updatePreview = useCallback((imageData: ImageData) => {
    if (!enablePreview || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Calculate display dimensions
    const aspectRatio = imageData.width / imageData.height;
    let displayWidth = Math.min(imageData.width, maxWidth);
    let displayHeight = displayWidth / aspectRatio;

    if (displayHeight > maxHeight) {
      displayHeight = maxHeight;
      displayWidth = displayHeight * aspectRatio;
    }

    canvas.width = displayWidth;
    canvas.height = displayHeight;

    // Draw image
    const canvasImageData = new window.ImageData(
      new Uint8ClampedArray(imageData.data),
      imageData.width,
      imageData.height
    );

    // Create temporary canvas for scaling
    const tempCanvas = document.createElement('canvas');
    const tempCtx = tempCanvas.getContext('2d')!;
    tempCanvas.width = imageData.width;
    tempCanvas.height = imageData.height;
    tempCtx.putImageData(canvasImageData, 0, 0);

    // Draw scaled image
    ctx.drawImage(tempCanvas, 0, 0, displayWidth, displayHeight);

    // Create preview URL for download
    canvas.toBlob((blob) => {
      if (blob) {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(URL.createObjectURL(blob));
      }
    });
  }, [enablePreview, maxWidth, maxHeight, previewUrl]);

  // Process image with operation
  const handleProcessImage = useCallback(async (operation: string, options: any = {}) => {
    if (!currentImage || !processor) return;

    setProcessingOperation(operation);

    try {
      const result = await processImage(currentImage, operation, options);
      
      if (result.success && result.data) {
        setCurrentImage(result.data);
        updatePreview(result.data);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Processing failed';
      onError?.(errorMessage);
    } finally {
      setProcessingOperation('');
    }
  }, [currentImage, processor, processImage, updatePreview, onError]);

  // Analyze current image
  const handleAnalyze = useCallback(async () => {
    if (!currentImage || !processor) return;

    try {
      const result = await analyzeImage(currentImage);
      setAnalysisResult(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Analysis failed';
      onError?.(errorMessage);
    }
  }, [currentImage, processor, analyzeImage, onError]);

  // Detect objects
  const handleDetectObjects = useCallback(async () => {
    if (!currentImage || !processor) return;

    try {
      const results = await detectObjects(currentImage);
      setDetectionResults(results);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Object detection failed';
      onError?.(errorMessage);
    }
  }, [currentImage, processor, detectObjects, onError]);

  // Detect faces
  const handleDetectFaces = useCallback(async () => {
    if (!currentImage || !processor) return;

    try {
      const results = await detectFaces(currentImage);
      setDetectionResults(results);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Face detection failed';
      onError?.(errorMessage);
    }
  }, [currentImage, processor, detectFaces, onError]);

  // Save processed image
  const handleSave = useCallback(async (format: string = 'png') => {
    if (!currentImage || !processor) return;

    try {
      const buffer = await saveImage(currentImage, { format, quality: 0.9 });
      const blob = new Blob([buffer], { type: `image/${format}` });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `processed-image.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      URL.revokeObjectURL(url);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Save failed';
      onError?.(errorMessage);
    }
  }, [currentImage, processor, saveImage, onError]);

  // Drag and drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (enableDragDrop) {
      setIsDragging(true);
    }
  }, [enableDragDrop]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (!enableDragDrop) return;

    const files = Array.from(e.dataTransfer.files);
    const imageFile = files.find(file => file.type.startsWith('image/'));
    
    if (imageFile) {
      handleFileSelect(imageFile);
    }
  }, [enableDragDrop, handleFileSelect]);

  // Cleanup preview URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  return (
    <div className={`image-processor ${className}`}>
      {/* Status and Error Display */}
      {!isInitialized && (
        <div className="status">
          {isLoading ? 'Initializing image processor...' : 'Image processor not ready'}
        </div>
      )}
      
      {(processorError || !processor) && (
        <div className="error">
          Error: {processorError || 'Processor not available'}
        </div>
      )}

      {/* GPU Capabilities Info */}
      {showCapabilities && gpuCapabilities && (
        <div className="capabilities-info">
          <h3>System Capabilities</h3>
          <div>
            <strong>GPU Available:</strong> {gpuCapabilities.hasGPU ? 'Yes' : 'No'}
            {gpuCapabilities.hasWebGL && <span> (WebGL)</span>}
            {gpuCapabilities.hasWebGL2 && <span> (WebGL2)</span>}
          </div>
          {gpuCapabilities.renderer && (
            <div><strong>Renderer:</strong> {gpuCapabilities.renderer}</div>
          )}
          <div><strong>Platform:</strong> {gpuCapabilities.platform}</div>
          <div><strong>OS:</strong> {gpuCapabilities.os}</div>
        </div>
      )}

      {/* Available Libraries */}
      {showCapabilities && availableLibraries.length > 0 && (
        <div className="libraries-info">
          <h3>Available Libraries</h3>
          <div className="library-list">
            {availableLibraries.map((lib) => (
              <div key={lib.name} className="library-item">
                <strong>{lib.name}</strong>
                <span className={`status ${lib.loaded ? 'loaded' : 'error'}`}>
                  {lib.loaded ? '✓' : '✗'}
                </span>
                {lib.backend && <span className="backend">({lib.backend})</span>}
                {processor?.library === lib.name.toLowerCase().replace('.js', '') && (
                  <span className="active">ACTIVE</span>
                )}
                <button 
                  onClick={() => switchProcessor(lib.name.toLowerCase().replace('.js', ''))}
                  disabled={!lib.loaded || isLoading}
                >
                  Use
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* File Input */}
      <div 
        className={`file-input-area ${isDragging ? 'dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileSelect(file);
          }}
          style={{ display: 'none' }}
        />
        
        <button 
          onClick={() => fileInputRef.current?.click()}
          disabled={!isInitialized || isLoading}
        >
          Select Image
        </button>
        
        {enableDragDrop && (
          <div className="drag-drop-hint">
            or drag and drop an image here
          </div>
        )}
      </div>

      {/* Preview Canvas */}
      {enablePreview && (
        <div className="preview-area">
          <canvas
            ref={canvasRef}
            className="preview-canvas"
            style={{
              border: '1px solid #ccc',
              maxWidth: '100%',
              height: 'auto',
            }}
          />
          
          {/* Detection Results Overlay */}
          {detectionResults.length > 0 && (
            <div className="detection-overlay">
              {detectionResults.map((detection, index) => (
                <div
                  key={index}
                  className="detection-box"
                  style={{
                    position: 'absolute',
                    left: detection.boundingBox.x,
                    top: detection.boundingBox.y,
                    width: detection.boundingBox.width,
                    height: detection.boundingBox.height,
                    border: '2px solid red',
                    backgroundColor: 'rgba(255, 0, 0, 0.1)',
                  }}
                >
                  {detection.label && (
                    <span className="detection-label">
                      {detection.label} ({Math.round(detection.confidence * 100)}%)
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Processing Controls */}
      {showControls && currentImage && processor && (
        <div className="processing-controls">
          <h3>Processing Operations</h3>
          
          {/* Basic Operations */}
          <div className="operation-group">
            <h4>Basic Operations</h4>
            <button 
              onClick={() => handleProcessImage('resize', { width: 400, height: 300 })}
              disabled={!!processingOperation}
            >
              Resize (400x300)
            </button>
            <button 
              onClick={() => handleProcessImage('crop', { x: 50, y: 50, width: 200, height: 200 })}
              disabled={!!processingOperation}
            >
              Crop (200x200)
            </button>
            <button 
              onClick={() => handleProcessImage('rotate', { angle: 90 })}
              disabled={!!processingOperation}
            >
              Rotate 90°
            </button>
          </div>

          {/* Filters */}
          <div className="operation-group">
            <h4>Filters</h4>
            <button 
              onClick={() => handleProcessImage('blur', { radius: 5 })}
              disabled={!!processingOperation}
            >
              Blur
            </button>
            <button 
              onClick={() => handleProcessImage('sharpen')}
              disabled={!!processingOperation || !processorCapabilities?.filter}
            >
              Sharpen
            </button>
            <button 
              onClick={() => handleProcessImage('filter', { filter: 'grayscale' })}
              disabled={!!processingOperation}
            >
              Grayscale
            </button>
          </div>

          {/* Adjustments */}
          <div className="operation-group">
            <h4>Adjustments</h4>
            <button 
              onClick={() => handleProcessImage('brightness', { value: 0.2 })}
              disabled={!!processingOperation}
            >
              Brighten
            </button>
            <button 
              onClick={() => handleProcessImage('brightness', { value: -0.2 })}
              disabled={!!processingOperation}
            >
              Darken
            </button>
            <button 
              onClick={() => handleProcessImage('contrast', { value: 0.3 })}
              disabled={!!processingOperation}
            >
              More Contrast
            </button>
          </div>

          {/* Analysis and Detection */}
          <div className="operation-group">
            <h4>Analysis & Detection</h4>
            <button 
              onClick={handleAnalyze}
              disabled={!!processingOperation}
            >
              Analyze Colors
            </button>
            {processorCapabilities?.objectDetection && (
              <button 
                onClick={handleDetectObjects}
                disabled={!!processingOperation}
              >
                Detect Objects
              </button>
            )}
            {processorCapabilities?.faceDetection && (
              <button 
                onClick={handleDetectFaces}
                disabled={!!processingOperation}
              >
                Detect Faces
              </button>
            )}
            {processorCapabilities?.edgeDetection && (
              <button 
                onClick={() => handleProcessImage('edges')}
                disabled={!!processingOperation}
              >
                Edge Detection
              </button>
            )}
          </div>

          {/* Save Options */}
          <div className="operation-group">
            <h4>Save</h4>
            <button onClick={() => handleSave('png')}>Save as PNG</button>
            <button onClick={() => handleSave('jpeg')}>Save as JPEG</button>
            <button onClick={() => handleSave('webp')}>Save as WebP</button>
          </div>
        </div>
      )}

      {/* Processing Status */}
      {processingOperation && (
        <div className="processing-status">
          Processing: {processingOperation}...
        </div>
      )}

      {/* Analysis Results */}
      {analysisResult && (
        <div className="analysis-results">
          <h3>Analysis Results</h3>
          <div>
            <strong>Dimensions:</strong> {analysisResult.dimensions.width} x {analysisResult.dimensions.height}
          </div>
          <div>
            <strong>Brightness:</strong> {Math.round(analysisResult.brightness * 100)}%
          </div>
          <div>
            <strong>File Size:</strong> {Math.round(analysisResult.fileSize / 1024)} KB
          </div>
          <div>
            <strong>Format:</strong> {analysisResult.format}
          </div>
          {analysisResult.dominantColors && analysisResult.dominantColors.length > 0 && (
            <div>
              <strong>Dominant Colors:</strong>
              <div className="color-palette">
                {analysisResult.dominantColors.map((color: any, index: number) => (
                  <div 
                    key={index}
                    className="color-swatch"
                    style={{
                      backgroundColor: color.hex,
                      width: '30px',
                      height: '30px',
                      display: 'inline-block',
                      margin: '2px',
                      border: '1px solid #ccc',
                    }}
                    title={`${color.hex} (${Math.round(color.percentage)}%)`}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};