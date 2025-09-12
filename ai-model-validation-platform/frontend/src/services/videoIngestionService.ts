/**
 * Video Ingestion Service - Frontend Integration
 * Handles video upload and annotation workflow for PRD Module 1.1 & 1.2
 */

import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface VideoUploadResponse {
  success: boolean;
  data: {
    video_id: string;
    filename: string;
    status: string;
    file_size: number;
    duration?: number;
    message: string;
  };
}

export interface VideoAnnotation {
  id: string;
  tracking_id: string;
  frame_number: number;
  timestamp: number;
  vru_type: string;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  confidence: number;
  validated: boolean;
}

export interface VideoLibraryItem {
  id: string;
  filename: string;
  status: 'pending_annotation' | 'pending_validation' | 'validated' | 'processing' | 'error';
  processing_status: string;
  ground_truth_generated: boolean;
  detection_count: number;
  duration?: number;
  file_size: number;
  created_at: string;
  resolution?: string;
}

export interface VideoStatus {
  video_id: string;
  filename: string;
  status: string;
  processing_status: string;
  ground_truth_generated: boolean;
  annotation_count: number;
  duration?: number;
  file_size: number;
  created_at: string;
  workflow_stage: {
    current: string;
    next_action: string;
  };
}

export interface VideoAnnotationData {
  video_id: string;
  video_filename: string;
  status: string;
  annotations: VideoAnnotation[];
  total_annotations: number;
  validation_required: boolean;
}

class VideoIngestionService {
  private axiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: `${API_BASE_URL}/api/v1/videos`,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * PRD Module 1.1: Upload video file
   */
  async uploadVideo(
    file: File, 
    projectId?: string, 
    onProgress?: (progress: number) => void
  ): Promise<VideoUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    if (projectId) {
      formData.append('project_id', projectId);
    }

    try {
      const response = await this.axiosInstance.post('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(progress);
          }
        },
      });

      return response.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to upload video');
    }
  }

  /**
   * PRD Module 1.2: Trigger automated annotation
   */
  async processAnnotation(videoId: string): Promise<any> {
    try {
      const response = await this.axiosInstance.post(`/${videoId}/process-annotation`);
      return response.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to process annotation');
    }
  }

  /**
   * PRD Module 1.4: Get video library
   */
  async getVideoLibrary(
    status?: string, 
    projectId?: string
  ): Promise<{ videos: VideoLibraryItem[]; total_count: number }> {
    try {
      const params = new URLSearchParams();
      if (status) params.append('status', status);
      if (projectId) params.append('project_id', projectId);

      const response = await this.axiosInstance.get(`/library?${params.toString()}`);
      return response.data.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to get video library');
    }
  }

  /**
   * Get video annotations with bounding boxes
   */
  async getVideoAnnotations(videoId: string): Promise<VideoAnnotationData> {
    try {
      const response = await this.axiosInstance.get(`/${videoId}/annotations`);
      return response.data.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to get video annotations');
    }
  }

  /**
   * PRD Module 1.3: Validate video annotations
   */
  async validateVideoAnnotations(videoId: string): Promise<any> {
    try {
      const response = await this.axiosInstance.post(`/${videoId}/validate`);
      return response.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to validate annotations');
    }
  }

  /**
   * Get video processing status
   */
  async getVideoStatus(videoId: string): Promise<VideoStatus> {
    try {
      const response = await this.axiosInstance.get(`/${videoId}/status`);
      return response.data.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to get video status');
    }
  }

  /**
   * Get VRU tracking statistics
   */
  async getTrackingStats(videoId: string): Promise<any> {
    try {
      const response = await this.axiosInstance.get(`/${videoId}/tracking-stats`);
      return response.data.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to get tracking stats');
    }
  }

  /**
   * Delete video
   */
  async deleteVideo(videoId: string): Promise<any> {
    try {
      const response = await this.axiosInstance.delete(`/${videoId}`);
      return response.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Failed to delete video');
    }
  }

  /**
   * Check service health and YOLO availability
   */
  async checkHealth(): Promise<{
    service: string;
    status: string;
    yolo_model: string;
    real_ai_detection: boolean;
    supported_formats: string[];
    max_file_size_mb: number;
  }> {
    try {
      const response = await this.axiosInstance.get('/health');
      return response.data.data;
    } catch (error: any) {
      throw new Error('Service health check failed');
    }
  }

  /**
   * Poll video status until processing completes
   */
  async pollVideoStatus(
    videoId: string, 
    onStatusUpdate?: (status: VideoStatus) => void,
    maxAttempts: number = 30,
    intervalMs: number = 2000
  ): Promise<VideoStatus> {
    let attempts = 0;
    
    while (attempts < maxAttempts) {
      try {
        const status = await this.getVideoStatus(videoId);
        
        if (onStatusUpdate) {
          onStatusUpdate(status);
        }
        
        // Check if processing is complete
        if (status.status === 'pending_validation' || 
            status.status === 'validated' || 
            status.status === 'error') {
          return status;
        }
        
        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, intervalMs));
        attempts++;
        
      } catch (error) {
        attempts++;
        if (attempts >= maxAttempts) {
          throw error;
        }
        await new Promise(resolve => setTimeout(resolve, intervalMs));
      }
    }
    
    throw new Error('Video processing timeout');
  }

  /**
   * Validate file before upload
   */
  validateFile(file: File): { valid: boolean; error?: string } {
    // Check file type
    const allowedTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo'];
    const allowedExtensions = ['.mp4', '.mov', '.avi'];
    
    const fileName = file.name.toLowerCase();
    const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));
    const hasValidType = allowedTypes.includes(file.type);
    
    if (!hasValidExtension && !hasValidType) {
      return {
        valid: false,
        error: 'Unsupported file format. Please use MP4, MOV, or AVI files.'
      };
    }
    
    // Check file size (2GB limit)
    const maxSize = 2048 * 1024 * 1024; // 2GB in bytes
    if (file.size > maxSize) {
      return {
        valid: false,
        error: 'File too large. Maximum size is 2GB.'
      };
    }
    
    return { valid: true };
  }
}

export const videoIngestionService = new VideoIngestionService();
export default videoIngestionService;