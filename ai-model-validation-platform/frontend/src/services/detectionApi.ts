/**
 * Real Detection API Service for Frame 80 Pedestrian Detection
 * Integrates with backend API at localhost:8000 for actual detection processing
 */

export interface BoundaryBox {
  id: string;
  type: 'pedestrian' | 'vehicle' | 'cyclist' | 'object';
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
  color: string;
  timestamp: number;
  frameNumber: number;
}

export interface DetectionRequest {
  frameNumber: number;
  imageData: string; // base64 encoded image data
  confidence_threshold?: number;
  detection_types?: string[];
}

export interface DetectionResponse {
  success: boolean;
  frame_number: number;
  detections: BoundaryBox[];
  processing_time_ms: number;
  model_version: string;
  error?: string;
}

export interface VideoFrameData {
  frameNumber: number;
  timestamp: number;
  imageData: string;
  width: number;
  height: number;
}

class DetectionApiService {
  private baseUrl: string;
  private abortController: AbortController | null = null;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  /**
   * Extract frame data from video file
   */
  async extractFrame(videoFile: File, frameNumber: number): Promise<VideoFrameData> {
    return new Promise((resolve, reject) => {
      const video = document.createElement('video');
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');

      if (!ctx) {
        reject(new Error('Could not get canvas context for frame extraction'));
        return;
      }

      video.onloadedmetadata = () => {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Calculate time for frame 80 (assuming 30fps)
        const frameTime = frameNumber / 30;
        video.currentTime = frameTime;
      };

      video.onseeked = () => {
        ctx.drawImage(video, 0, 0);
        const imageData = canvas.toDataURL('image/jpeg', 0.8);
        
        resolve({
          frameNumber,
          timestamp: Date.now(),
          imageData,
          width: canvas.width,
          height: canvas.height
        });
      };

      video.onerror = () => {
        reject(new Error('Failed to load video for frame extraction'));
      };

      const url = URL.createObjectURL(videoFile);
      video.src = url;
      video.load();
    });
  }

  /**
   * Process frame for pedestrian detection via backend API
   */
  async detectObjects(request: DetectionRequest): Promise<DetectionResponse> {
    // Cancel any pending request
    if (this.abortController) {
      this.abortController.abort();
    }
    
    this.abortController = new AbortController();

    try {
      const response = await fetch(`${this.baseUrl}/api/simple-detection/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: `detection_${Date.now()}`,
          frame_number: request.frameNumber,
          image_data: request.imageData,
          confidence_threshold: request.confidence_threshold || 0.7,
          detection_types: request.detection_types || ['pedestrian', 'vehicle', 'cyclist']
        }),
        signal: this.abortController.signal
      });

      if (!response.ok) {
        throw new Error(`Detection API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      // Transform backend response to our format
      return {
        success: true,
        frame_number: data.frame_number || request.frameNumber,
        detections: data.detections.map((det: any, index: number) => ({
          id: `${det.type}_${request.frameNumber}_${index}`,
          type: det.type,
          x: Math.round(det.bbox[0]),
          y: Math.round(det.bbox[1]),
          width: Math.round(det.bbox[2] - det.bbox[0]),
          height: Math.round(det.bbox[3] - det.bbox[1]),
          confidence: det.confidence,
          color: this.getDetectionColor(det.type),
          timestamp: Date.now(),
          frameNumber: request.frameNumber
        })),
        processing_time_ms: data.processing_time || 0,
        model_version: data.model_version || 'unknown'
      };
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Detection request was cancelled');
      }
      
      throw new Error(`Detection failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Process Frame 80 specifically with optimized settings for pedestrian detection
   */
  async processFrame80(videoFrameData: VideoFrameData): Promise<DetectionResponse> {
    const request: DetectionRequest = {
      frameNumber: 80,
      imageData: videoFrameData.imageData,
      confidence_threshold: 0.99, // High confidence for Frame 80
      detection_types: ['pedestrian'] // Focus on pedestrians
    };

    return this.detectObjects(request);
  }

  /**
   * Real-time detection stream for continuous processing
   */
  async *streamDetections(videoFile: File, startFrame: number = 0, endFrame: number = 100): AsyncGenerator<DetectionResponse> {
    for (let frameNumber = startFrame; frameNumber <= endFrame; frameNumber++) {
      try {
        const frameData = await this.extractFrame(videoFile, frameNumber);
        const detection = await this.detectObjects({
          frameNumber,
          imageData: frameData.imageData,
          confidence_threshold: frameNumber === 80 ? 0.99 : 0.7,
          detection_types: frameNumber === 80 ? ['pedestrian'] : ['pedestrian', 'vehicle', 'cyclist']
        });
        
        yield detection;
      } catch (error) {
        console.error(`Failed to process frame ${frameNumber}:`, error);
        // Continue with next frame
      }
    }
  }

  /**
   * Check if backend API is available
   */
  async healthCheck(): Promise<{ status: 'healthy' | 'unhealthy'; message: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        timeout: 5000
      } as RequestInit);

      if (response.ok) {
        return { status: 'healthy', message: 'Backend API is available' };
      } else {
        return { status: 'unhealthy', message: `API returned ${response.status}` };
      }
    } catch (error) {
      return { 
        status: 'unhealthy', 
        message: `Cannot connect to backend: ${error instanceof Error ? error.message : 'Unknown error'}` 
      };
    }
  }

  /**
   * Snap coordinates to grid
   */
  snapToGrid(x: number, y: number, gridSize: number): { x: number; y: number } {
    return {
      x: Math.round(x / gridSize) * gridSize,
      y: Math.round(y / gridSize) * gridSize
    };
  }

  /**
   * Snap boundary box to grid
   */
  snapBoundaryBoxToGrid(box: BoundaryBox, gridSize: number): BoundaryBox {
    const snappedTopLeft = this.snapToGrid(box.x, box.y, gridSize);
    const snappedBottomRight = this.snapToGrid(box.x + box.width, box.y + box.height, gridSize);
    
    return {
      ...box,
      x: snappedTopLeft.x,
      y: snappedTopLeft.y,
      width: snappedBottomRight.x - snappedTopLeft.x,
      height: snappedBottomRight.y - snappedTopLeft.y
    };
  }

  /**
   * Cancel ongoing detection requests
   */
  cancelRequests(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  /**
   * Get color for detection type
   */
  private getDetectionColor(type: string): string {
    const colors = {
      pedestrian: '#ff4444',
      vehicle: '#4444ff',
      cyclist: '#44ff44',
      object: '#ffff44'
    };
    return colors[type as keyof typeof colors] || '#888888';
  }
}

// Singleton instance
export const detectionApi = new DetectionApiService();

// Export for testing with different base URLs
export { DetectionApiService };