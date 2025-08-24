import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import { AppError } from '../utils/errorTypes';
import {
  Project,
  ProjectCreate,
  ProjectUpdate,
  VideoFile,
  TestSession,
  TestSessionCreate,
  ChartData,
  PassFailCriteria,
  StatisticalValidation,
  VideoAssignment,
  SignalProcessingResult,
  VideoLibraryOrganization,
  VideoQualityAssessment,
  DetectionPipelineConfig,
  DetectionPipelineResult,
  EnhancedDashboardStats,
  SignalType,
  GroundTruthAnnotation,
  AnnotationSession
} from './types';
import {
  isObject,
  isString,
  isNumber,
  isAxiosError,
  parseErrorResponse,
  safeGet,
  safeSpread,
  hasResponseData,
  convertToVideoFile,
  safeConvertArray,
  isApiErrorResponse,
  safeParams,
  safeExtractErrorData
} from '../utils/typeGuards';
import { ErrorFactory } from '../utils/errorTypes';
import errorReporting from './errorReporting';
import { apiCache } from '../utils/apiCache';
import envConfig, { getServiceConfig, isDebugEnabled } from '../utils/envConfig';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    // Get API configuration from environment config manager
    const apiConfig = getServiceConfig('api');
    
    if (isDebugEnabled()) {
      console.log('🔧 API Service initializing with config:', {
        url: apiConfig.url,
        timeout: apiConfig.timeout,
        retryAttempts: apiConfig.retryAttempts,
        retryDelay: apiConfig.retryDelay
      });
    }

    this.api = axios.create({
      baseURL: apiConfig.url || 'http://localhost:8000',
      timeout: apiConfig.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
    
    // Validate configuration and test connectivity
    this.validateAndTestConfiguration();
  }
  
  private async validateAndTestConfiguration() {
    const config = envConfig.getConfig();
    const validationErrors = envConfig.getValidationErrors();
    
    if (validationErrors.length > 0) {
      console.error('❌ API Service Configuration Errors:', validationErrors);
    }
    
    // Test API connectivity in development mode
    if (config.isDevelopment || config.debug) {
      try {
        const connectivityTest = await envConfig.testApiConnectivity();
        if (connectivityTest.connected) {
          console.log(`✅ API connectivity verified (${connectivityTest.latency}ms latency)`);
        } else {
          console.warn('⚠️ API connectivity issue:', connectivityTest.error);
        }
      } catch (error) {
        console.warn('⚠️ API connectivity test failed:', error);
      }
    }
  }

  private setupInterceptors() {
    // Request interceptor - no auth required
    this.api.interceptors.request.use(
      (config) => {
        // No authentication required - removed token handling
        return config;
      },
      (error) => {
        throw this.handleError(error);
      }
    );

    // Response interceptor - handle responses and errors
    this.api.interceptors.response.use(
      (response: AxiosResponse) => {
        // Backend already provides camelCase data - no transformation needed
        return response;
      },
      (error: AxiosError) => {
        throw this.handleError(error);
      }
    );
  }

  private handleError(error: AxiosError | unknown): AppError {
    const apiError: AppError = {
      name: 'ApiError',
      message: 'An unexpected error occurred',
      status: 500,
    };

    let customError: Error;
    let errorMessage = 'An unexpected error occurred';

    try {
      if (isAxiosError(error) && error.response) {
        // Server responded with error status
        apiError.status = error.response.status;
        const responseData = error.response.data;
        
        // Safely extract error message using type guards
        if (isString(responseData)) {
          errorMessage = responseData;
        } else if (isObject(responseData)) {
          const messageFromData = safeGet(responseData, 'message', undefined);
          const detailFromData = safeGet(responseData, 'detail', undefined);
          const errorFromData = safeGet(responseData, 'error', undefined);
          
          errorMessage = (isString(messageFromData) ? messageFromData : null) ||
                        (isString(detailFromData) ? detailFromData : null) ||
                        (isString(errorFromData) ? errorFromData : null) ||
                        `Server error: ${error.response.status}`;
        } else {
          errorMessage = `HTTP ${error.response.status}: ${error.response.statusText || 'Unknown error'}`;
        }
        
        apiError.message = errorMessage;
        if (isObject(responseData)) {
          apiError.details = responseData;
        }

        // Create custom error for error boundary handling
        const errorContext = {
          originalError: error,
          method: safeGet(error, 'config.method', undefined),
          url: safeGet(error, 'config.url', undefined)
        };
        
        customError = ErrorFactory.createApiError(
          error.response as any,
          (isObject(responseData) ? responseData : {}) as Record<string, unknown>,
          errorContext
        );

      } else if (isAxiosError(error) && error.request) {
        // Network error - no response received
        errorMessage = 'Network error - please check your connection';
        apiError.message = errorMessage;
        apiError.code = 'NETWORK_ERROR';
        
        const networkErrorContext = {
          originalError: error,
          method: safeGet(error, 'config.method', undefined),
          url: safeGet(error, 'config.url', undefined)
        };
        
        customError = ErrorFactory.createNetworkError(
          undefined,
          networkErrorContext
        );

      } else if (isAxiosError(error) && error.code === 'ECONNABORTED') {
        // Request timeout
        errorMessage = 'Request timeout - please try again';
        apiError.message = errorMessage;
        apiError.code = 'TIMEOUT_ERROR';
        customError = new Error(errorMessage);

      } else {
        // Request setup error or other error
        const parsedError = parseErrorResponse(error);
        errorMessage = parsedError.message;
        
        apiError.message = errorMessage;
        apiError.status = parsedError.status || 500;
        customError = new Error(`Request error: ${errorMessage}`);
      }

      // Safely build error context using type guards
      const errorContext: Record<string, unknown> = {
        timestamp: new Date().toISOString(),
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown'
      };
      
      if (isAxiosError(error)) {
        const method = safeGet(error, 'config.method', undefined);
        const url = safeGet(error, 'config.url', undefined);
        const status = safeGet(error, 'response.status', undefined);
        const statusText = safeGet(error, 'response.statusText', undefined);
        const code = safeGet(error, 'code', undefined);
        
        if (isString(method)) errorContext.method = method;
        if (isString(url)) errorContext.url = url;
        if (isNumber(status)) errorContext.status = status;
        if (isString(statusText)) errorContext.statusText = statusText;
        if (isString(code)) errorContext.errorCode = code;
      }
      
      // Report error to error reporting service
      try {
        errorReporting.reportApiError(customError, 'api-service', errorContext);
      } catch (reportingError) {
        console.warn('Failed to report error:', reportingError);
      }

      // Safe console logging
      console.error('API Error:', {
        message: apiError.message,
        status: apiError.status,
        code: apiError.code,
        context: errorContext
      });

      return apiError;

    } catch (handlingError) {
      // Fallback error handling if something goes wrong in error processing
      console.error('Error in error handling:', handlingError);
      
      const fallbackError: AppError = {
        name: 'UnknownError',
        message: 'An unexpected error occurred',
        status: 500,
        code: 'UNKNOWN_ERROR'
      };

      return fallbackError;
    }
  }

  // Transform backend snake_case responses to frontend camelCase
  private transformResponseData(data: unknown): unknown {
    if (!isObject(data) && !Array.isArray(data)) {
      return data;
    }

    // Handle arrays
    if (Array.isArray(data)) {
      return data.map(item => this.transformResponseData(item));
    }

    // Handle objects - using type guard
    if (!isObject(data)) return data;
    const transformed: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      let newKey = key;
      
      // Transform common snake_case fields to camelCase
      const fieldMappings: { [key: string]: string } = {
        'project_id': 'projectId',
        'video_id': 'videoId', 
        'file_size': 'fileSize',
        'file_path': 'filePath',
        'created_at': 'createdAt',
        'updated_at': 'updatedAt',
        'uploaded_at': 'uploadedAt',
        'ground_truth_generated': 'groundTruthGenerated',
        'ground_truth_status': 'groundTruthStatus',
        'processing_status': 'processingStatus',
        'detection_count': 'detectionCount',
        'test_session_id': 'testSessionId',
        'original_name': 'originalName',
        'camera_model': 'cameraModel',
        'camera_view': 'cameraView',
        'lens_type': 'lensType',
        'frame_rate': 'frameRate',
        'signal_type': 'signalType',
        'owner_id': 'ownerId',
        'class_label': 'classLabel',
        'validation_result': 'validationResult',
        'bounding_box': 'boundingBox'
      };

      if (fieldMappings[key]) {
        newKey = fieldMappings[key];
      }

      // Recursively transform nested objects
      transformed[newKey] = this.transformResponseData(value);
    }

    return transformed;
  }

  // Add URL field to video responses if missing or relative
  private enhanceVideoData(video: unknown): VideoFile {
    // Use safe conversion with type guards
    const convertedVideo = convertToVideoFile(video);
    if (!convertedVideo) {
      throw new Error('Unable to convert video data to VideoFile format');
    }
    
    const videoObj = { ...convertedVideo };
    console.log('🚨 enhanceVideoData called for video:', { 
      id: videoObj.id, 
      filename: videoObj.filename, 
      originalUrl: videoObj.url
    });
    
    if (videoObj.filename || videoObj.id) {
      const videoConfig = getServiceConfig('video');
      
      console.log('🚨 enhanceVideoData - Video config baseUrl:', videoConfig.baseUrl);
      console.log('🚨 enhanceVideoData - Original video URL:', videoObj.url);
      console.log('🚨 enhanceVideoData - Video filename:', videoObj.filename);
      console.log('🚨 enhanceVideoData - Video ID:', videoObj.id);
      
      // Convert relative URLs to absolute URLs
      if (isString(videoObj.url) && videoObj.url.startsWith('/')) {
        console.log('🚨 enhanceVideoData - Converting relative URL to absolute');
        const videoConfig = getServiceConfig('video');
        videoObj.url = `${videoConfig.baseUrl}${videoObj.url}`;
        console.log('🚨 enhanceVideoData - Enhanced video URL:', videoObj.url, 'from relative path');
      } else if (!videoObj.url || videoObj.url === '') {
        console.log('🚨 enhanceVideoData - URL missing or empty, constructing from filename');
        // If URL is missing or empty, try to construct from backend base URL and filename
        if (isString(videoObj.filename) && videoObj.filename.trim()) {
          const videoConfig = getServiceConfig('video');
          videoObj.url = `${videoConfig.baseUrl}/uploads/${videoObj.filename}`;
          console.log('🚨 enhanceVideoData - Constructed video URL from filename:', videoObj.url);
        } else {
          console.warn('🚨 enhanceVideoData - Video object is missing both URL and filename. ID:', videoObj.id);
          videoObj.url = '';
        }
      } else {
        console.log('🚨 enhanceVideoData - Video URL already absolute:', videoObj.url);
      }
    }
    
    console.log('🚨 enhanceVideoData - Final enhanced video:', { 
      id: videoObj.id, 
      filename: videoObj.filename, 
      finalUrl: videoObj.url
    });
    
    return videoObj;
  }

  // Enhanced request method with caching and deduplication
  private async cachedRequest<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
    url: string,
    data?: unknown,
    config?: Record<string, unknown>
  ): Promise<T> {
    // Cache key generation for request tracking
    const params = config?.params;
    
    // Only cache GET requests
    if (method === 'GET') {
      // Check cache first
      const cached = apiCache.get<T>(method, url, safeParams(params));
      if (cached !== null) {
        if (isDebugEnabled()) {
          console.log(`📋 Cache hit for ${method} ${url}`);
        }
        return cached as T;
      }

      // Check for pending request to avoid duplication
      const pending = apiCache.getPendingRequest(method, url, safeParams(params));
      if (pending) {
        if (isDebugEnabled()) {
          console.log(`⏳ Request deduplication for ${method} ${url}`);
        }
        return pending as Promise<T>;
      }
    }

    // Make the actual request
    const requestPromise = this.api.request<T>({
      method: method.toLowerCase(),
      url,
      data,
      ...config,
    }).then(response => {
      // Cache successful GET responses
      if (method === 'GET') {
        apiCache.set(method, url, response.data, safeParams(params));
        if (isDebugEnabled()) {
          console.log(`💾 Cached response for ${method} ${url}`);
        }
      }
      return response.data;
    }).catch(error => {
      if (isDebugEnabled()) {
        console.error(`❌ Request failed for ${method} ${url}:`, error.message);
      }
      throw error;
    });

    // Track pending request for deduplication
    if (method === 'GET') {
      apiCache.setPendingRequest(method, url, requestPromise, safeParams(params));
    }

    return requestPromise;
  }
  
  /**
   * Get current configuration information
   */
  getConfiguration() {
    return {
      baseURL: this.api.defaults.baseURL,
      timeout: this.api.defaults.timeout,
      environment: envConfig.getConfig().environment,
      isValid: envConfig.isValid(),
      validationErrors: envConfig.getValidationErrors()
    };
  }

  /**
   * Force clear video-related cache entries
   */
  clearVideoCache() {
    apiCache.invalidatePattern('/api/videos');
    apiCache.invalidatePattern('/api/projects');
    apiCache.invalidatePattern('/api/ground-truth/videos');
  }
  
  /**
   * Test connectivity to the API
   */
  async testConnectivity() {
    return envConfig.testApiConnectivity();
  }

  // Project CRUD
  async getProjects(skip: number = 0, limit: number = 100): Promise<Project[]> {
    return this.cachedRequest<Project[]>('GET', '/api/projects', undefined, {
      params: { skip, limit }
    });
  }

  async getProject(id: string): Promise<Project> {
    return this.cachedRequest<Project>('GET', `/api/projects/${id}`);
  }

  async createProject(project: ProjectCreate): Promise<Project> {
    try {
      const result = await this.cachedRequest<Project>('POST', '/api/projects', project);
      // Invalidate projects cache after creating a new project
      apiCache.invalidatePattern('/api/projects');
      apiCache.invalidatePattern('/api/dashboard');
      return result;
    } catch (error: unknown) {
      console.error('API Service - Project creation failed:', error);
      throw error;
    }
  }

  async updateProject(id: string, updates: ProjectUpdate): Promise<Project> {
    const result = await this.cachedRequest<Project>('PUT', `/api/projects/${id}`, updates);
    // Invalidate related cache entries
    apiCache.invalidate('GET', `/api/projects/${id}`);
    apiCache.invalidatePattern('/api/projects');
    apiCache.invalidatePattern('/api/dashboard');
    return result;
  }

  async deleteProject(id: string): Promise<void> {
    await this.cachedRequest<void>('DELETE', `/api/projects/${id}`);
    // Invalidate related cache entries
    apiCache.invalidate('GET', `/api/projects/${id}`);
    apiCache.invalidatePattern('/api/projects');
    apiCache.invalidatePattern('/api/dashboard');
  }

  // Video management
  async getVideos(projectId: string): Promise<VideoFile[]> {
    console.log('🚨 apiService.getVideos called for project:', projectId);
    // Temporarily bypass cache to ensure enhancement runs
    const response = await this.api.get<VideoFile[]>(`/api/projects/${projectId}/videos?t=${Date.now()}`);
    console.log('🚨 apiService.getVideos - Raw response from backend:', response.data);
    // Enhance video data with proper URLs and status mapping
    const enhancedVideos = response.data.map(video => this.enhanceVideoData(video));
    console.log('🚨 apiService.getVideos - Enhanced videos:', enhancedVideos);
    return enhancedVideos;
  }

  async uploadVideo(projectId: string, file: File, onProgress?: (progress: number) => void): Promise<VideoFile> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.api.post<VideoFile>(`/api/projects/${projectId}/videos`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          onProgress(progress);
        }
      },
    });

    return response.data;
  }

  // Central video upload (no project required)
  async uploadVideoCentral(file: File, onProgress?: (progress: number) => void): Promise<VideoFile> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.api.post<VideoFile>('/api/videos', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          onProgress(progress);
        }
      },
    });

    // Invalidate video-related caches
    apiCache.invalidatePattern('/api/videos');
    apiCache.invalidatePattern('/api/projects');
    
    return response.data;
  }

  // Get all videos from central store
  async getAllVideos(unassigned: boolean = false, skip: number = 0, limit: number = 100): Promise<{videos: VideoFile[], total: number}> {
    const response = await this.cachedRequest<{videos: VideoFile[], total: number}>('GET', '/api/videos', undefined, {
      params: { unassigned, skip, limit }
    });
    
    // Filter out invalid videos and enhance valid ones
    if (response.videos) {
      // Filter out videos with invalid IDs or missing data
      const validVideos = response.videos.filter(video => 
        video && 
        video.id && 
        typeof video.id === 'string' &&
        video.id.trim().length > 0 &&
        (video.filename || video.originalName)
      );

      if (validVideos.length !== response.videos.length) {
        console.warn(`⚠️ Filtered out ${response.videos.length - validVideos.length} invalid video records`);
      }

      // Enhance video data with proper URLs and status mapping
      response.videos = validVideos.map(video => this.enhanceVideoData(video));
      
      // Update total count
      response.total = validVideos.length;

      // Clear stale video cache for videos that no longer exist
      const validVideoIds = response.videos.map(v => v.id);
      try {
        // Clear video URL cache for non-existent videos
        const { videoUtils } = await import('../utils/videoUtils');
        videoUtils.clearStaleVideoCache(validVideoIds);
        
        // Also clear localStorage cache for missing videos
        if (typeof window !== 'undefined') {
          try {
            const videoCache = localStorage.getItem('video-cache');
            if (videoCache) {
              const cache = JSON.parse(videoCache);
              let cacheModified = false;
              
              // Remove cache entries for videos that no longer exist
              for (const cachedVideoId in cache) {
                if (!validVideoIds.includes(cachedVideoId)) {
                  delete cache[cachedVideoId];
                  cacheModified = true;
                  if (isDebugEnabled()) {
                    console.log(`🧹 Cleared localStorage cache for missing video: ${cachedVideoId}`);
                  }
                }
              }
              
              if (cacheModified) {
                localStorage.setItem('video-cache', JSON.stringify(cache));
              }
            }
          } catch (storageError) {
            console.warn('Failed to clear localStorage video cache:', storageError);
          }
        }
      } catch (e) {
        console.warn('Could not clear stale video cache:', e);
      }
    }
    
    return response;
  }

  async getVideo(videoId: string): Promise<VideoFile> {
    const response = await this.api.get(`/api/videos/${videoId}`);
    if (!hasResponseData(response) || !isObject(response.data)) {
      throw new Error('Invalid video response from server');
    }
    return this.enhanceVideoData(response.data);
  }

  async deleteVideo(videoId: string): Promise<void> {
    await this.api.delete(`/api/videos/${videoId}`);
  }

  // Ground truth - Enhanced with fallback data and proper error handling
  async getGroundTruth(videoId: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/videos/${videoId}/ground-truth`);
      
      // Transform ground truth data to ensure proper structure
      if (hasResponseData(response) && isObject(response.data)) {
        const objectsData = safeGet(response.data, 'objects', []);
        if (Array.isArray(objectsData)) {
          (response.data as any).objects = objectsData.map((obj: unknown) => {
            if (!isObject(obj)) return obj;
          
          // Safely extract bounding box data
          const boundingBoxData = safeGet(obj, 'bounding_box', safeGet(obj, 'boundingBox', {}));
          const boundingBox = isObject(boundingBoxData) ? boundingBoxData : {
            x: safeGet(obj, 'x', 0),
            y: safeGet(obj, 'y', 0),
            width: safeGet(obj, 'width', 100),
            height: safeGet(obj, 'height', 100),
            confidence: safeGet(obj, 'confidence', 1.0),
            label: safeGet(obj, 'class_label', safeGet(obj, 'classLabel', 'unknown'))
          };
          
          return {
            ...obj,
            boundingBox,
            vruType: safeGet(obj, 'vru_type', safeGet(obj, 'vruType', 
              this.mapClassToVruType(safeGet(obj, 'class_label', safeGet(obj, 'classLabel', ''))))),
            detectionId: safeGet(obj, 'detection_id', safeGet(obj, 'detectionId', safeGet(obj, 'id', ''))),
            frameNumber: safeGet(obj, 'frame_number', safeGet(obj, 'frameNumber', 0)),
            timestamp: safeGet(obj, 'timestamp', 0),
            validated: safeGet(obj, 'validated', false),
            occluded: safeGet(obj, 'occluded', false),
            truncated: safeGet(obj, 'truncated', false),
            difficult: safeGet(obj, 'difficult', false)
          };
          });
        }
      }
      
      return response.data || {
        video_id: videoId,
        objects: [],
        total_detections: 0,
        status: 'pending',
        message: 'No ground truth data available'
      };
    } catch (error: unknown) {
      console.warn(`Ground truth fetch failed for video ${videoId}:`, error);
      // Return empty ground truth structure as fallback
      return {
        video_id: videoId,
        objects: [],
        total_detections: 0,
        status: 'error',
        message: 'Failed to load ground truth data'
      };
    }
  }

  // Helper method to map class labels to VRU types
  private mapClassToVruType(classLabel: unknown): string {
    if (!isString(classLabel)) {
      return 'pedestrian';
    }
    
    const mapping: { [key: string]: string } = {
      'person': 'pedestrian',
      'pedestrian': 'pedestrian',
      'bicycle': 'cyclist',
      'cyclist': 'cyclist',
      'motorcycle': 'motorcyclist',
      'motorcyclist': 'motorcyclist',
      'wheelchair': 'wheelchair_user',
      'scooter': 'scooter_rider'
    };
    
    return mapping[classLabel.toLowerCase()] || 'pedestrian';
  }

  // Annotation endpoints
  async getAnnotations(videoId: string): Promise<GroundTruthAnnotation[]> {
    return this.cachedRequest<GroundTruthAnnotation[]>('GET', `/api/videos/${videoId}/annotations`);
  }

  async createAnnotation(videoId: string, annotation: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'>): Promise<GroundTruthAnnotation> {
    const result = await this.cachedRequest<GroundTruthAnnotation>('POST', `/api/videos/${videoId}/annotations`, {
      detection_id: annotation.detectionId,
      frame_number: annotation.frameNumber,
      timestamp: annotation.timestamp,
      vru_type: annotation.vruType,
      bounding_box: annotation.boundingBox,
      occluded: annotation.occluded,
      truncated: annotation.truncated,
      difficult: annotation.difficult,
      notes: annotation.notes,
      annotator: annotation.annotator,
      validated: annotation.validated
    });
    // Invalidate cache for video annotations
    apiCache.invalidatePattern(`/api/videos/${videoId}/annotations`);
    return result;
  }

  async updateAnnotation(annotationId: string, updates: Partial<GroundTruthAnnotation>): Promise<GroundTruthAnnotation> {
    const result = await this.cachedRequest<GroundTruthAnnotation>('PUT', `/api/annotations/${annotationId}`, {
      detection_id: updates.detectionId,
      frame_number: updates.frameNumber,
      timestamp: updates.timestamp,
      vru_type: updates.vruType,
      bounding_box: updates.boundingBox,
      occluded: updates.occluded,
      truncated: updates.truncated,
      difficult: updates.difficult,
      notes: updates.notes,
      annotator: updates.annotator,
      validated: updates.validated
    });
    // Invalidate related cache entries
    apiCache.invalidatePattern('/api/videos');
    apiCache.invalidatePattern('/api/annotations');
    return result;
  }

  async deleteAnnotation(annotationId: string): Promise<void> {
    await this.cachedRequest<void>('DELETE', `/api/annotations/${annotationId}`);
    // Invalidate related cache entries
    apiCache.invalidatePattern('/api/videos');
    apiCache.invalidatePattern('/api/annotations');
  }

  async validateAnnotation(annotationId: string, validated: boolean): Promise<GroundTruthAnnotation> {
    const result = await this.cachedRequest<GroundTruthAnnotation>('PATCH', `/api/annotations/${annotationId}/validate`, {
      validated
    });
    // Invalidate related cache entries
    apiCache.invalidatePattern('/api/videos');
    apiCache.invalidatePattern('/api/annotations');
    return result;
  }

  async getAnnotationsByDetection(detectionId: string): Promise<GroundTruthAnnotation[]> {
    return this.cachedRequest<GroundTruthAnnotation[]>('GET', `/api/annotations/detection/${detectionId}`);
  }

  async createAnnotationSession(videoId: string, projectId: string): Promise<AnnotationSession> {
    const result = await this.cachedRequest<AnnotationSession>('POST', '/api/annotation-sessions', {
      video_id: videoId,
      project_id: projectId
    });
    return result;
  }

  async getAnnotationSession(sessionId: string): Promise<AnnotationSession> {
    return this.cachedRequest<AnnotationSession>('GET', `/api/annotation-sessions/${sessionId}`);
  }

  async updateAnnotationSession(sessionId: string, updates: Partial<AnnotationSession>): Promise<AnnotationSession> {
    const result = await this.cachedRequest<AnnotationSession>('PUT', `/api/annotation-sessions/${sessionId}`, {
      status: updates.status,
      current_frame: updates.currentFrame,
      total_detections: updates.totalDetections,
      validated_detections: updates.validatedDetections
    });
    return result;
  }

  async exportAnnotations(videoId: string, format: 'coco' | 'yolo' | 'pascal' | 'json' = 'json'): Promise<Blob> {
    const response = await this.api.get(`/api/videos/${videoId}/annotations/export`, {
      params: { format },
      responseType: 'blob'
    });
    return response.data;
  }

  async importAnnotations(videoId: string, file: File, format: 'coco' | 'yolo' | 'pascal' | 'json' = 'json'): Promise<{imported: number, errors: string[]}> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('format', format);

    const result = await this.cachedRequest<{imported: number, errors: string[]}>('POST', `/api/videos/${videoId}/annotations/import`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    // Invalidate cache after import
    apiCache.invalidatePattern(`/api/videos/${videoId}/annotations`);
    return result;
  }

  // Test sessions
  async getTestSessions(projectId?: string): Promise<TestSession[]> {
    const params = projectId ? { project_id: projectId } : {};
    const response = await this.api.get<TestSession[]>('/api/test-sessions', { params });
    return response.data;
  }

  async getTestSession(sessionId: string): Promise<TestSession> {
    const response = await this.api.get<TestSession>(`/api/test-sessions/${sessionId}`);
    return response.data;
  }

  async createTestSession(testSession: TestSessionCreate): Promise<TestSession> {
    const response = await this.api.post<TestSession>('/api/test-sessions', testSession);
    return response.data;
  }

  async getTestResults(sessionId: string): Promise<any> {
    const response = await this.api.get(`/api/test-sessions/${sessionId}/results`);
    return response.data;
  }

  // Dashboard
  async getDashboardStats(): Promise<EnhancedDashboardStats> {
    return this.cachedRequest<EnhancedDashboardStats>('GET', '/api/dashboard/stats');
  }

  async getChartData(): Promise<ChartData> {
    return this.cachedRequest<ChartData>('GET', '/api/dashboard/charts');
  }

  // Health check with enhanced error handling
  async healthCheck(): Promise<{ status: string, environment?: string, timestamp?: string }> {
    try {
      const result = await this.cachedRequest<{ status: string, environment?: string, timestamp?: string }>('GET', '/health');
      if (isDebugEnabled()) {
        console.log('✅ Health check passed:', result);
      }
      return result;
    } catch (error: unknown) {
      const errorMessage = parseErrorResponse(error).message;
      console.error('❌ Health check failed:', errorMessage);
      throw error;
    }
  }

  // Video Library Management
  async organizeVideoLibrary(projectId: string): Promise<VideoLibraryOrganization> {
    return this.cachedRequest<VideoLibraryOrganization>('GET', `/api/video-library/organize/${projectId}`);
  }

  async assessVideoQuality(videoId: string): Promise<VideoQualityAssessment> {
    return this.cachedRequest<VideoQualityAssessment>('GET', `/api/video-library/quality-assessment/${videoId}`);
  }

  // Detection Pipeline
  async runDetectionPipeline(videoId: string, config: DetectionPipelineConfig): Promise<DetectionPipelineResult> {
    return this.cachedRequest<DetectionPipelineResult>('POST', '/api/detection/pipeline/run', { 
      video_id: videoId,
      confidence_threshold: config.confidenceThreshold,
      nms_threshold: config.nmsThreshold,
      model_name: config.modelName,
      target_classes: config.targetClasses
    });
  }

  async getAvailableModels(): Promise<{models: string[], default: string, recommended: string}> {
    return this.cachedRequest('GET', '/api/detection/models/available');
  }

  // Get detection results for a video
  async getVideoDetections(videoId: string): Promise<any[]> {
    try {
      const response = await this.api.get(`/api/videos/${videoId}/detections`);
      return response.data.detections || [];
    } catch (error: unknown) {
      console.error('Failed to fetch video detections:', error);
      const errorData = isAxiosError(error) ? safeExtractErrorData(error.response) : null;
      throw ErrorFactory.createApiError(errorData || {}, {}, { originalError: error });
    }
  }

  // Get detection results for a test session  
  async getTestSessionDetections(sessionId: string): Promise<any[]> {
    try {
      const response = await this.api.get(`/api/test-sessions/${sessionId}/detections`);
      return response.data.detections || [];
    } catch (error: unknown) {
      console.error('Failed to fetch session detections:', error);
      const errorData = isAxiosError(error) ? safeExtractErrorData(error.response) : null;
      throw ErrorFactory.createApiError(errorData || {}, {}, { originalError: error });
    }
  }

  // Signal Processing
  async processSignal(signalType: SignalType, signalData: unknown, config?: Record<string, unknown>): Promise<SignalProcessingResult> {
    return this.cachedRequest<SignalProcessingResult>('POST', '/api/signals/process', {
      signal_type: signalType,
      signal_data: signalData,
      processing_config: config
    });
  }

  async getSupportedProtocols(): Promise<{protocols: string[], capabilities: Record<string, string[]>}> {
    return this.cachedRequest('GET', '/api/signals/protocols/supported');
  }

  // Enhanced Project Management
  async configurePassFailCriteria(projectId: string, criteria: Omit<PassFailCriteria, 'id' | 'projectId' | 'createdAt'>): Promise<PassFailCriteria> {
    return this.cachedRequest<PassFailCriteria>('POST', `/api/projects/${projectId}/criteria/configure`, {
      min_precision: criteria.minPrecision,
      min_recall: criteria.minRecall,
      min_f1_score: criteria.minF1Score,
      max_latency_ms: criteria.maxLatencyMs
    });
  }

  async getIntelligentAssignments(projectId: string): Promise<VideoAssignment[]> {
    return this.cachedRequest<VideoAssignment[]>('GET', `/api/projects/${projectId}/assignments/intelligent`);
  }

  // Statistical Validation
  async runStatisticalValidation(testSessionId: string, confidenceLevel: number = 0.95): Promise<StatisticalValidation> {
    return this.cachedRequest<StatisticalValidation>('POST', '/api/validation/statistical/run', {
      test_session_id: testSessionId,
      confidence_level: confidenceLevel
    });
  }

  async getConfidenceIntervals(sessionId: string): Promise<{precision: [number, number], recall: [number, number], f1_score: [number, number], accuracy: [number, number], confidence_level: number, sample_size: number}> {
    return this.cachedRequest('GET', `/api/validation/confidence-intervals/${sessionId}`);
  }

  // ID Generation
  async generateId(strategy: 'uuid4' | 'snowflake' | 'composite'): Promise<{id: string, strategy: string, timestamp: string}> {
    return this.cachedRequest('POST', `/api/ids/generate/${strategy}`);
  }

  async getAvailableIdStrategies(): Promise<{strategies: string[], default: string, descriptions: Record<string, string>}> {
    return this.cachedRequest('GET', '/api/ids/strategies/available');
  }

  // Video Library and Ground Truth Integration
  async getAvailableGroundTruthVideos(): Promise<VideoFile[]> {
    const response = await this.cachedRequest<VideoFile[]>('GET', '/api/ground-truth/videos/available');
    // Enhance video data with proper URLs and status mapping
    return response.map(video => this.enhanceVideoData(video));
  }

  async linkVideosToProject(projectId: string, videoIds: string[]): Promise<VideoAssignment[]> {
    const result = await this.cachedRequest<VideoAssignment[]>('POST', `/api/projects/${projectId}/videos/link`, {
      video_ids: videoIds
    });
    // Invalidate related cache entries
    apiCache.invalidate('GET', `/api/projects/${projectId}`);
    apiCache.invalidatePattern('/api/projects');
    apiCache.invalidatePattern(`/api/projects/${projectId}/videos`);
    return result;
  }

  async getLinkedVideos(projectId: string): Promise<VideoFile[]> {
    const response = await this.cachedRequest<VideoFile[]>('GET', `/api/projects/${projectId}/videos/linked`);
    // Enhance video data with proper URLs and status mapping
    return response.map(video => this.enhanceVideoData(video));
  }

  async unlinkVideoFromProject(projectId: string, videoId: string): Promise<void> {
    await this.cachedRequest<void>('DELETE', `/api/projects/${projectId}/videos/${videoId}/unlink`);
    // Invalidate related cache entries
    apiCache.invalidate('GET', `/api/projects/${projectId}`);
    apiCache.invalidatePattern('/api/projects');
    apiCache.invalidatePattern(`/api/projects/${projectId}/videos`);
  }

  // Generic request methods for custom endpoints
  async get<T = unknown>(url: string, config?: Record<string, unknown>): Promise<T> {
    const response = await this.api.get<T>(url, config);
    return response.data;
  }

  async post<T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
    const response = await this.api.post<T>(url, data, config);
    return response.data;
  }

  async put<T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
    const response = await this.api.put<T>(url, data, config);
    return response.data;
  }

  async delete<T = unknown>(url: string, config?: Record<string, unknown>): Promise<T> {
    const response = await this.api.delete<T>(url, config);
    return response.data;
  }
}

// Create and export singleton instance
const apiServiceInstance = new ApiService();
export const apiService = apiServiceInstance;

// Export individual functions for easier imports (properly bound)
export const getProjects = apiServiceInstance.getProjects.bind(apiServiceInstance);
export const getProject = apiServiceInstance.getProject.bind(apiServiceInstance);
export const createProject = apiServiceInstance.createProject.bind(apiServiceInstance);
export const updateProject = apiServiceInstance.updateProject.bind(apiServiceInstance);
export const deleteProject = apiServiceInstance.deleteProject.bind(apiServiceInstance);
export const getVideos = apiServiceInstance.getVideos.bind(apiServiceInstance);
export const uploadVideo = apiServiceInstance.uploadVideo.bind(apiServiceInstance);
export const uploadVideoCentral = apiServiceInstance.uploadVideoCentral.bind(apiServiceInstance);
export const getAllVideos = apiServiceInstance.getAllVideos.bind(apiServiceInstance);
export const getVideo = apiServiceInstance.getVideo.bind(apiServiceInstance);
export const deleteVideo = apiServiceInstance.deleteVideo.bind(apiServiceInstance);
export const getGroundTruth = apiServiceInstance.getGroundTruth.bind(apiServiceInstance);
export const getTestSessions = apiServiceInstance.getTestSessions.bind(apiServiceInstance);
export const getTestSession = apiServiceInstance.getTestSession.bind(apiServiceInstance);
export const createTestSession = apiServiceInstance.createTestSession.bind(apiServiceInstance);
export const getTestResults = apiServiceInstance.getTestResults.bind(apiServiceInstance);
export const getDashboardStats = apiServiceInstance.getDashboardStats.bind(apiServiceInstance);
export const organizeVideoLibrary = apiServiceInstance.organizeVideoLibrary.bind(apiServiceInstance);
export const assessVideoQuality = apiServiceInstance.assessVideoQuality.bind(apiServiceInstance);
export const runDetectionPipeline = apiServiceInstance.runDetectionPipeline.bind(apiServiceInstance);
export const getAvailableModels = apiServiceInstance.getAvailableModels.bind(apiServiceInstance);
export const getVideoDetections = apiServiceInstance.getVideoDetections.bind(apiServiceInstance);
export const getTestSessionDetections = apiServiceInstance.getTestSessionDetections.bind(apiServiceInstance);
export const processSignal = apiServiceInstance.processSignal.bind(apiServiceInstance);
export const getSupportedProtocols = apiServiceInstance.getSupportedProtocols.bind(apiServiceInstance);
export const configurePassFailCriteria = apiServiceInstance.configurePassFailCriteria.bind(apiServiceInstance);
export const getIntelligentAssignments = apiServiceInstance.getIntelligentAssignments.bind(apiServiceInstance);
export const runStatisticalValidation = apiServiceInstance.runStatisticalValidation.bind(apiServiceInstance);
export const getConfidenceIntervals = apiServiceInstance.getConfidenceIntervals.bind(apiServiceInstance);
export const generateId = apiServiceInstance.generateId.bind(apiServiceInstance);
export const getAvailableIdStrategies = apiServiceInstance.getAvailableIdStrategies.bind(apiServiceInstance);
export const getChartData = apiServiceInstance.getChartData.bind(apiServiceInstance);
export const healthCheck = apiServiceInstance.healthCheck.bind(apiServiceInstance);
export const getAvailableGroundTruthVideos = apiServiceInstance.getAvailableGroundTruthVideos.bind(apiServiceInstance);
export const linkVideosToProject = apiServiceInstance.linkVideosToProject.bind(apiServiceInstance);
export const getLinkedVideos = apiServiceInstance.getLinkedVideos.bind(apiServiceInstance);
export const unlinkVideoFromProject = apiServiceInstance.unlinkVideoFromProject.bind(apiServiceInstance);
export const getAnnotations = apiServiceInstance.getAnnotations.bind(apiServiceInstance);
export const createAnnotation = apiServiceInstance.createAnnotation.bind(apiServiceInstance);
export const updateAnnotation = apiServiceInstance.updateAnnotation.bind(apiServiceInstance);
export const deleteAnnotation = apiServiceInstance.deleteAnnotation.bind(apiServiceInstance);
export const validateAnnotation = apiServiceInstance.validateAnnotation.bind(apiServiceInstance);
export const getAnnotationsByDetection = apiServiceInstance.getAnnotationsByDetection.bind(apiServiceInstance);
export const createAnnotationSession = apiServiceInstance.createAnnotationSession.bind(apiServiceInstance);
export const getAnnotationSession = apiServiceInstance.getAnnotationSession.bind(apiServiceInstance);
export const updateAnnotationSession = apiServiceInstance.updateAnnotationSession.bind(apiServiceInstance);
export const exportAnnotations = apiServiceInstance.exportAnnotations.bind(apiServiceInstance);
export const importAnnotations = apiServiceInstance.importAnnotations.bind(apiServiceInstance);

export default apiService;