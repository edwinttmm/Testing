/**
 * Real Detection Hook for Frame 80 Pedestrian Detection
 * Manages state for actual detection processing and API integration
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { detectionApi, BoundaryBox, DetectionResponse } from '../services/detectionApi';
import { videoProcessor, VideoMetadata, ProcessedFrame } from '../services/videoProcessor';

export interface DetectionState {
  // Video state
  videoFile: File | null;
  videoMetadata: VideoMetadata | null;
  currentFrame: number;
  isPlaying: boolean;
  
  // Detection state
  detections: BoundaryBox[];
  isDetecting: boolean;
  detectionError: string | null;
  lastDetectionTime: number | null;
  
  // Frame 80 specific
  frame80Data: ProcessedFrame | null;
  frame80Detections: BoundaryBox[];
  frame80Processed: boolean;
  
  // API status
  apiStatus: 'checking' | 'healthy' | 'unhealthy';
  apiMessage: string;
  
  // UI state
  selectedBox: string | null;
  snapToGrid: boolean;
  gridSize: number;
  zoom: number;
  
  // Performance metrics
  processingTime: number;
  frameRate: number;
  memoryUsage: number;
}

export interface DetectionActions {
  // Video actions
  loadVideo: (file: File) => Promise<void>;
  setCurrentFrame: (frame: number) => void;
  setIsPlaying: (playing: boolean) => void;
  
  // Detection actions
  detectCurrentFrame: () => Promise<void>;
  detectFrame80: () => Promise<void>;
  startRealTimeDetection: () => void;
  stopRealTimeDetection: () => void;
  clearDetections: () => void;
  
  // UI actions
  setSelectedBox: (id: string | null) => void;
  setSnapToGrid: (snap: boolean) => void;
  setGridSize: (size: number) => void;
  setZoom: (zoom: number) => void;
  
  // Utility actions
  snapBoxToGrid: (box: BoundaryBox) => BoundaryBox;
  exportDetections: () => string;
  resetState: () => void;
}

const initialState: DetectionState = {
  videoFile: null,
  videoMetadata: null,
  currentFrame: 80,
  isPlaying: false,
  detections: [],
  isDetecting: false,
  detectionError: null,
  lastDetectionTime: null,
  frame80Data: null,
  frame80Detections: [],
  frame80Processed: false,
  apiStatus: 'checking',
  apiMessage: 'Checking API status...',
  selectedBox: null,
  snapToGrid: true,
  gridSize: 20,
  zoom: 1,
  processingTime: 0,
  frameRate: 0,
  memoryUsage: 0
};

export function useDetection(): DetectionState & DetectionActions {
  const [state, setState] = useState<DetectionState>(initialState);
  const detectionIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const frameRateRef = useRef({ lastUpdate: 0, frameCount: 0 });

  // Check API health on mount
  useEffect(() => {
    checkApiHealth();
  }, []);

  // Auto-detect Frame 80 when current frame changes to 80
  useEffect(() => {
    if (state.currentFrame === 80 && state.videoFile && !state.frame80Processed) {
      detectFrame80();
    }
  }, [state.currentFrame, state.videoFile]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRealTimeDetection();
      detectionApi.cancelRequests();
      videoProcessor.cleanup();
    };
  }, []);

  const checkApiHealth = useCallback(async () => {
    setState(prev => ({ ...prev, apiStatus: 'checking', apiMessage: 'Checking API status...' }));
    
    try {
      const health = await detectionApi.healthCheck();
      setState(prev => ({
        ...prev,
        apiStatus: health.status,
        apiMessage: health.message
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        apiStatus: 'unhealthy',
        apiMessage: `API check failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      }));
    }
  }, []);

  const loadVideo = useCallback(async (file: File) => {
    try {
      setState(prev => ({ ...prev, isDetecting: true, detectionError: null }));
      
      // Validate video file
      const validation = videoProcessor.validateVideoFile(file);
      if (!validation.valid) {
        throw new Error(validation.error);
      }
      
      // Load video and extract metadata
      const metadata = await videoProcessor.loadVideo(file);
      
      setState(prev => ({
        ...prev,
        videoFile: file,
        videoMetadata: metadata,
        currentFrame: 80, // Start at Frame 80
        detections: [],
        frame80Processed: false,
        isDetecting: false
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        detectionError: `Failed to load video: ${error instanceof Error ? error.message : 'Unknown error'}`,
        isDetecting: false
      }));
    }
  }, []);

  const setCurrentFrame = useCallback((frame: number) => {
    setState(prev => ({ ...prev, currentFrame: frame }));
  }, []);

  const setIsPlaying = useCallback((playing: boolean) => {
    setState(prev => ({ ...prev, isPlaying: playing }));
    
    if (playing) {
      startRealTimeDetection();
    } else {
      stopRealTimeDetection();
    }
  }, []);

  const detectCurrentFrame = useCallback(async () => {
    if (!state.videoFile || state.isDetecting) return;
    
    const startTime = performance.now();
    setState(prev => ({ ...prev, isDetecting: true, detectionError: null }));
    
    try {
      // Extract current frame
      const frameData = await videoProcessor.extractFrame({
        frameNumber: state.currentFrame,
        quality: 0.8
      });
      
      // Detect objects
      const detectionResponse = await detectionApi.detectObjects({
        frameNumber: state.currentFrame,
        imageData: frameData.imageData,
        confidence_threshold: state.currentFrame === 80 ? 0.99 : 0.7
      });
      
      const processingTime = performance.now() - startTime;
      
      setState(prev => ({
        ...prev,
        detections: state.snapToGrid 
          ? detectionResponse.detections.map(box => detectionApi.snapBoundaryBoxToGrid(box, state.gridSize))
          : detectionResponse.detections,
        isDetecting: false,
        lastDetectionTime: Date.now(),
        processingTime
      }));
      
      // Update frame rate
      updateFrameRate();
      
    } catch (error) {
      setState(prev => ({
        ...prev,
        detectionError: `Detection failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        isDetecting: false
      }));
    }
  }, [state.videoFile, state.isDetecting, state.currentFrame, state.snapToGrid, state.gridSize]);

  const detectFrame80 = useCallback(async () => {
    if (!state.videoFile || state.frame80Processed) return;
    
    setState(prev => ({ ...prev, isDetecting: true, detectionError: null }));
    
    try {
      // Extract Frame 80 with high quality
      const frame80Data = await videoProcessor.extractFrame80();
      
      // Process Frame 80 with optimized settings
      const detectionResponse = await detectionApi.processFrame80(frame80Data);
      
      // Apply snap-to-grid if enabled
      const detections = state.snapToGrid
        ? detectionResponse.detections.map(box => detectionApi.snapBoundaryBoxToGrid(box, state.gridSize))
        : detectionResponse.detections;
      
      setState(prev => ({
        ...prev,
        frame80Data,
        frame80Detections: detections,
        frame80Processed: true,
        detections: detections, // Also update main detections if we're on frame 80
        isDetecting: false,
        lastDetectionTime: Date.now()
      }));
      
    } catch (error) {
      setState(prev => ({
        ...prev,
        detectionError: `Frame 80 detection failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        isDetecting: false
      }));
    }
  }, [state.videoFile, state.frame80Processed, state.snapToGrid, state.gridSize]);

  const startRealTimeDetection = useCallback(() => {
    if (detectionIntervalRef.current) return;
    
    detectionIntervalRef.current = setInterval(() => {
      if (state.isPlaying && !state.isDetecting) {
        detectCurrentFrame();
        
        // Advance frame
        const nextFrame = (state.currentFrame + 1) % (state.videoMetadata?.totalFrames || 100);
        setCurrentFrame(nextFrame);
      }
    }, 1000 / 30); // 30 FPS
  }, [state.isPlaying, state.isDetecting, state.currentFrame, state.videoMetadata, detectCurrentFrame]);

  const stopRealTimeDetection = useCallback(() => {
    if (detectionIntervalRef.current) {
      clearInterval(detectionIntervalRef.current);
      detectionIntervalRef.current = null;
    }
  }, []);

  const clearDetections = useCallback(() => {
    setState(prev => ({
      ...prev,
      detections: [],
      frame80Detections: [],
      frame80Processed: false,
      selectedBox: null
    }));
  }, []);

  const setSelectedBox = useCallback((id: string | null) => {
    setState(prev => ({ ...prev, selectedBox: id }));
  }, []);

  const setSnapToGrid = useCallback((snap: boolean) => {
    setState(prev => ({ ...prev, snapToGrid: snap }));
    
    // Re-snap existing detections if enabled
    if (snap) {
      setState(prev => ({
        ...prev,
        detections: prev.detections.map(box => detectionApi.snapBoundaryBoxToGrid(box, prev.gridSize)),
        frame80Detections: prev.frame80Detections.map(box => detectionApi.snapBoundaryBoxToGrid(box, prev.gridSize))
      }));
    }
  }, []);

  const setGridSize = useCallback((size: number) => {
    setState(prev => ({ ...prev, gridSize: size }));
    
    // Re-snap existing detections if snap-to-grid is enabled
    if (state.snapToGrid) {
      setState(prev => ({
        ...prev,
        detections: prev.detections.map(box => detectionApi.snapBoundaryBoxToGrid(box, size)),
        frame80Detections: prev.frame80Detections.map(box => detectionApi.snapBoundaryBoxToGrid(box, size))
      }));
    }
  }, [state.snapToGrid]);

  const setZoom = useCallback((zoom: number) => {
    setState(prev => ({ ...prev, zoom: Math.max(0.1, Math.min(5, zoom)) }));
  }, []);

  const snapBoxToGrid = useCallback((box: BoundaryBox): BoundaryBox => {
    return detectionApi.snapBoundaryBoxToGrid(box, state.gridSize);
  }, [state.gridSize]);

  const exportDetections = useCallback((): string => {
    const exportData = {
      timestamp: new Date().toISOString(),
      videoMetadata: state.videoMetadata,
      currentFrame: state.currentFrame,
      frame80Data: {
        processed: state.frame80Processed,
        detections: state.frame80Detections
      },
      allDetections: state.detections,
      settings: {
        snapToGrid: state.snapToGrid,
        gridSize: state.gridSize,
        zoom: state.zoom
      }
    };
    
    return JSON.stringify(exportData, null, 2);
  }, [state]);

  const resetState = useCallback(() => {
    stopRealTimeDetection();
    detectionApi.cancelRequests();
    videoProcessor.cleanup();
    setState(initialState);
  }, [stopRealTimeDetection]);

  const updateFrameRate = useCallback(() => {
    const now = performance.now();
    frameRateRef.current.frameCount++;
    
    if (now - frameRateRef.current.lastUpdate > 1000) {
      const fps = frameRateRef.current.frameCount;
      setState(prev => ({ ...prev, frameRate: fps }));
      
      frameRateRef.current.frameCount = 0;
      frameRateRef.current.lastUpdate = now;
    }
  }, []);

  return {
    ...state,
    loadVideo,
    setCurrentFrame,
    setIsPlaying,
    detectCurrentFrame,
    detectFrame80,
    startRealTimeDetection,
    stopRealTimeDetection,
    clearDetections,
    setSelectedBox,
    setSnapToGrid,
    setGridSize,
    setZoom,
    snapBoxToGrid,
    exportDetections,
    resetState
  };
}