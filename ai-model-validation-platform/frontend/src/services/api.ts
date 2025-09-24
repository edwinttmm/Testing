import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import { AppError, ErrorFactory } from '../utils/errorTypes';
import { getConfigValueSync, isConfigInitialized } from '../utils/configurationManager';
import { fixVideoObjectUrl } from '../utils/videoUrlFixer';
import { ApiErrorData } from '../types/common';
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
  DetectionPipelineResponse,
  EnhancedDashboardStats,
  SignalType,
  CameraType,
  GroundTruthAnnotation,
  AnnotationSession,
  VideoStatus,
  ValidationStatus,
  VideoValidationStatus
} from './types';
import {
  isObject,
  isString,
  isNumber,
  isAxiosError,
  parseErrorResponse,
  safeGet,
  hasResponseData,
  convertToVideoFile,
  safeParams,
  safeExtractErrorData
} from '../utils/typeGuards';
import errorReporting from './errorReporting';
import { apiCache } from '../utils/apiCache';
import envConfig, { getServiceConfig, isDebugEnabled } from '../utils/envConfig';
import { videoEnhancementCache } from '../utils/videoEnhancementCache';
import { ComponentLogger } from '../utils/loggingUtils';

// Configuration is now handled automatically by configurationManager

const mapBackendStatusToFrontendStatus = (
  backendStatus: VideoStatus | string,
  validationStatus?: ValidationStatus | string
): VideoValidationStatus => {
  // Handle direct string status from API response
  if (typeof backendStatus === 'string') {
    // Direct mapping for string status values from backend
    switch (backendStatus.toLowerCase()) {
      case 'validated':
        return VideoValidationStatus.VALIDATED;
      case 'validating':
        return VideoValidationStatus.VALIDATING;
      case 'processing':
        return VideoValidationStatus.PROCESSING;
      case 'completed':
        return VideoValidationStatus.ANNOTATED;
      case 'uploaded':
        return VideoValidationStatus.UPLOADED;
      case 'error':
      case 'failed':
        return VideoValidationStatus.ERROR;
      default:
        // Check if it matches processing_status patterns
        if (backendStatus === 'completed' || backendStatus === 'ready') {
          return VideoValidationStatus.ANNOTATED;
        }
        return VideoValidationStatus.UPLOADED;
    }
  }
  
  // Original enum-based logic for backward compatibility
  if (backendStatus === VideoStatus.ERROR) {
    return VideoValidationStatus.ERROR;
  }
  if (backendStatus === VideoStatus.PROCESSING) {
    return VideoValidationStatus.PROCESSING;
  }
  if (validationStatus === ValidationStatus.VALIDATED || validationStatus === 'validated') {
    return VideoValidationStatus.VALIDATED;
  }
  if (validationStatus === ValidationStatus.VALIDATING || validationStatus === 'validating') {
    return VideoValidationStatus.VALIDATING;
  }
  if (backendStatus === VideoStatus.COMPLETED) {
    return VideoValidationStatus.ANNOTATED;
  }
  if (backendStatus === VideoStatus.UPLOADED) {
    return VideoValidationStatus.UPLOADED;
  }
  return VideoValidationStatus.UPLOADED;
};

class ApiService {
  private api: AxiosInstance;
  private logger: ComponentLogger;

  constructor() {
    this.logger = new ComponentLogger('ApiService');
    
    // Always use explicit base URL to avoid proxy issues
    const useDevProxy = false; // Force disable proxy to fix routing issues
    // Compute base URL with environment overrides
    const envBase = process.env.REACT_APP_API_URL || (isConfigInitialized() ? getConfigValueSync('REACT_APP_API_URL', 'http://localhost:8000') : 'http://localhost:8000');
    // Always use the explicit API URL for reliable routing
    const developmentBaseURL = envBase.includes('localhost') ? envBase : 'http://localhost:8000';
    const apiConfig = getServiceConfig('api');
    
    this.logger.logger.info('API Service initializing', {
      action: 'service_init',
      metadata: {
        baseURL: developmentBaseURL,
        originalBaseURL: envBase,
        configUrl: apiConfig.url,
        timeout: apiConfig.timeout,
        retryAttempts: apiConfig.retryAttempts,
        retryDelay: apiConfig.retryDelay,
        configInitialized: isConfigInitialized()
      }
    });

    this.api = axios.create({
      baseURL: developmentBaseURL,
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
      this.logger.logger.error('API Service Configuration Errors', {
        action: 'config_validation',
        metadata: {
          errorCount: validationErrors.length,
          errors: validationErrors
        }
      });
    }
    
    // Test API connectivity in development mode
    if (config.isDevelopment || config.debug) {
      const connectivityTimer = this.logger.logger.time('api-connectivity-test');
      
      try {
        const connectivityTest = await envConfig.testApiConnectivity();
        connectivityTimer();
        
        if (connectivityTest.connected) {
          this.logger.logger.info('API connectivity verified', {
            action: 'connectivity_test',
            performance: {
              timestamp: Date.now(),
              duration: connectivityTest.latency ?? 0
            },
            metadata: {
              latency: `${connectivityTest.latency}ms`,
              status: 'connected'
            }
          });
        } else {
          this.logger.logger.warn('API connectivity issue detected', {
            action: 'connectivity_test',
            metadata: {
              error: connectivityTest.error,
              status: 'disconnected'
            }
          });
        }
      } catch (error) {
        connectivityTimer();
        this.logger.logger.warn('API connectivity test failed', {
          action: 'connectivity_test',
          metadata: {
            status: 'test_failed'
          }
        }, error as Error);
      }
    }
  }

  private setupInterceptors() {
    // Request interceptor - no auth required
    this.api.interceptors.request.use(
      (config) => {
        // Attach shared service token (if configured) for backend auth
        try {
          const token = (typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG?.REACT_APP_API_TOKEN)
            || process.env.REACT_APP_API_TOKEN
            || (typeof window !== 'undefined' ? window.localStorage?.getItem('api_token') : undefined)
            || (typeof window !== 'undefined' ? window.localStorage?.getItem('access_token') : undefined);
          if (token) {
            config.headers = config.headers || {};
            if (!('Authorization' in config.headers)) {
              (config.headers as any).Authorization = `Bearer ${token}`;
            }
          }
        } catch {
          // Best-effort; continue without token
        }
        return config;
      },
      (error) => {
        throw this.handleError(error);
      }
    );

    // Response interceptor - handle responses and errors
    this.api.interceptors.response.use(
      (response: AxiosResponse) => {
        // Backend uses camelCase serializers - apply minimal transformation
        if (response.data) {
          response.data = this.transformResponseData(response.data);
        }
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
    let userFriendlyMessage = '';

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

        // Generate user-friendly messages based on status code
        switch (error.response.status) {
          case 503:
            userFriendlyMessage = 'The service is temporarily unavailable. Please try again in a few moments.';
            break;
          case 405:
            userFriendlyMessage = 'This operation is not currently supported. Please try a different action.';
            break;
          case 404:
            // More specific handling for missing endpoints
            if (safeGet(error, 'config.url', '').includes('/ground-truth/')) {
              userFriendlyMessage = 'Ground truth endpoint is not available. Using alternative video source.';
            } else {
              userFriendlyMessage = 'The requested resource was not found. It may have been moved or deleted.';
            }
            break;
          case 403:
            userFriendlyMessage = 'You don\'t have permission to access this resource.';
            break;
          case 401:
            userFriendlyMessage = 'Your session has expired. Please refresh the page and try again.';
            break;
          case 400:
            userFriendlyMessage = 'The request contains invalid data. Please check your input and try again.';
            break;
          case 500:
            userFriendlyMessage = 'An internal server error occurred. Our team has been notified.';
            break;
          default:
            userFriendlyMessage = `Server error (${error.response.status}). Please try again or contact support if the problem persists.`;
        }
        
        apiError.message = userFriendlyMessage || errorMessage;
        if (isObject(responseData)) {
          apiError.details = responseData;
        }

        // Create custom error for error boundary handling
        const errorContext = {
          originalError: error,
          method: safeGet(error, 'config.method', undefined),
          url: safeGet(error, 'config.url', undefined),
          userFriendlyMessage
        };
        
        customError = ErrorFactory.createApiError(
          error.response as unknown as Record<string, unknown>,
          (isObject(responseData) ? responseData : {}) as Record<string, unknown>,
          errorContext
        );

      } else if (isAxiosError(error) && error.request) {
        // Network error - no response received
        if (error.code === 'ERR_NETWORK' || !navigator.onLine) {
          errorMessage = 'No internet connection. Please check your network and try again.';
          userFriendlyMessage = 'You appear to be offline. Please check your internet connection.';
        } else {
          errorMessage = 'Network error - unable to reach the server';
          userFriendlyMessage = 'Unable to connect to the server. Please check your connection and try again.';
        }
        
        apiError.message = userFriendlyMessage || errorMessage;
        apiError.code = 'NETWORK_ERROR';
        
        const networkErrorContext = {
          originalError: error,
          method: safeGet(error, 'config.method', undefined),
          url: safeGet(error, 'config.url', undefined),
          userFriendlyMessage
        };
        
        customError = ErrorFactory.createNetworkError(
          undefined,
          networkErrorContext
        );

      } else if (isAxiosError(error) && error.code === 'ECONNABORTED') {
        // Request timeout
        errorMessage = 'Request timeout - please try again';
        userFriendlyMessage = 'The request took too long to complete. Please try again.';
        apiError.message = userFriendlyMessage;
        apiError.code = 'TIMEOUT_ERROR';
        customError = new Error(errorMessage);

      } else if (isAxiosError(error) && error.code === 'ERR_CANCELED') {
        // Request was cancelled
        errorMessage = 'Request was cancelled';
        userFriendlyMessage = 'The operation was cancelled.';
        apiError.message = userFriendlyMessage;
        apiError.code = 'CANCELLED_ERROR';
        customError = new Error(errorMessage);

      } else {
        // Request setup error or other error
        const parsedError = parseErrorResponse(error);
        errorMessage = parsedError.message;
        userFriendlyMessage = 'An unexpected error occurred. Please try again.';
        
        apiError.message = userFriendlyMessage;
        apiError.status = parsedError.status || 500;
        customError = new Error(`Request error: ${errorMessage}`);
      }

      // Safely build error context using type guards
      const errorContext: Record<string, unknown> = {
        timestamp: new Date().toISOString(),
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
        userFriendlyMessage,
        originalMessage: errorMessage
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

      // Safe console logging with both technical and user-friendly messages
      console.error('API Error:', {
        userMessage: apiError.message,
        technicalMessage: errorMessage,
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
        message: 'An unexpected error occurred. Please refresh the page and try again.',
        status: 500,
        code: 'UNKNOWN_ERROR'
      };

      return fallbackError;
    }
  }

  // Backend now uses camelCase serializers - minimal transformation needed
  private transformResponseData(data: unknown): unknown {
    // Backend already provides camelCase data via Pydantic serializers
    // Only minimal transformation needed for specific cases
    if (!isObject(data) && !Array.isArray(data)) {
      return data;
    }

    // Handle arrays
    if (Array.isArray(data)) {
      return data.map(item => this.transformResponseData(item));
    }

    // Handle objects - minimal processing since backend uses camelCase
    if (!isObject(data)) return data;
    const transformed: Record<string, unknown> = { ...data };
    
    // Handle any remaining snake_case fields for backward compatibility
    if ('created_at' in data && !('createdAt' in data)) {
      transformed.createdAt = data.created_at;
      delete transformed.created_at;
    }
    if ('updated_at' in data && !('updatedAt' in data)) {
      transformed.updatedAt = data.updated_at;
      delete transformed.updated_at;
    }

    return transformed;
  }

  // Add URL field to video responses if missing or relative
  private enhanceVideoData(video: unknown): VideoFile {
    // Use safe conversion with type guards
    const convertedVideo = convertToVideoFile(video) as VideoFile & { status: VideoStatus, validationStatus: ValidationStatus };
    if (!convertedVideo) {
      throw new Error('Unable to convert video data to VideoFile format');
    }
    
    const videoObj = convertedVideo && typeof convertedVideo === 'object' ? { ...convertedVideo } : convertedVideo;
    if (isDebugEnabled()) {
      console.log('🚨 enhanceVideoData called for video:', { 
        id: videoObj.id, 
        filename: videoObj.filename, 
        originalUrl: videoObj.url
      });
    }
    
    // Use the video URL fixer utility to ensure proper URL construction
    fixVideoObjectUrl(videoObj, { debug: isDebugEnabled() });

    // Map backend status to frontend status
    videoObj.status = mapBackendStatusToFrontendStatus(videoObj.status, videoObj.validationStatus);
    
    if (isDebugEnabled()) {
      console.log('🚨 enhanceVideoData - Final enhanced video:', { 
        id: videoObj.id, 
        filename: videoObj.filename, 
        finalUrl: videoObj.url,
        status: videoObj.status
      });
    }
    
    return videoObj;
  }

  // Enhanced request method with caching and deduplication and retry logic
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

    // Retry configuration
    const maxRetries = 3;
    const retryDelay = (attempt: number) => Math.min(1000 * Math.pow(2, attempt), 10000); // Exponential backoff
    
    const executeRequest = async (attempt: number = 0): Promise<T> => {
      try {
        const response = await this.api.request<T>({
          method: method.toLowerCase(),
          url,
          data,
          ...config,
        });

        // Cache successful GET responses
        if (method === 'GET') {
          apiCache.set(method, url, response.data, safeParams(params));
          if (isDebugEnabled()) {
            console.log(`💾 Cached response for ${method} ${url}`);
          }
        }
        
        return response.data;
      } catch (error: unknown) {
        if (isDebugEnabled()) {
          console.error(`❌ Request failed for ${method} ${url} (attempt ${attempt + 1}):`, (error as Error)?.message || 'Unknown error');
        }

        // Determine if we should retry
        const shouldRetry = attempt < maxRetries && this.shouldRetryRequest(error);
        
        if (shouldRetry) {
          if (isDebugEnabled()) {
            console.log(`🔄 Retrying ${method} ${url} in ${retryDelay(attempt)}ms (attempt ${attempt + 2}/${maxRetries + 1})`);
          }
          
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, retryDelay(attempt)));
          return executeRequest(attempt + 1);
        }
        
        throw error;
      }
    };

    const requestPromise = executeRequest().catch(error => {
      // Ensure errors are properly handled and re-thrown
      throw this.handleError(error);
    });

    // Track pending request for deduplication
    if (method === 'GET') {
      apiCache.setPendingRequest(method, url, requestPromise, safeParams(params));
    }

    return requestPromise;
  }

  private shouldRetryRequest(error: Error | unknown): boolean {
    // Don't retry on client errors (4xx) except for 408, 429
    if (isAxiosError(error) && error.response) {
      const status = error.response.status;
      
      // Retry on server errors (5xx)
      if (status >= 500) {
        return true;
      }
      
      // Retry on specific client errors
      if (status === 408 || status === 429) { // Request Timeout, Too Many Requests
        return true;
      }
      
      // Don't retry on other client errors
      return false;
    }
    
    // Retry on network errors
    if (isAxiosError(error) && (error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK')) {
      return true;
    }
    
    // Don't retry on cancelled requests
    if (isAxiosError(error) && error.code === 'ERR_CANCELED') {
      return false;
    }
    
    // Retry on other unknown errors
    return true;
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
    // Clear video enhancement cache as well
    videoEnhancementCache.clear();
  }
  
  /**
   * Test connectivity to the API
   */
  async testConnectivity() {
    return envConfig.testApiConnectivity();
  }

  /**
   * Get video enhancement cache statistics
   */
  getVideoEnhancementStats() {
    return videoEnhancementCache.getStats();
  }

  /**
   * Clear specific video from enhancement cache
   */
  clearVideoEnhancement(videoId: string) {
    videoEnhancementCache.delete(videoId);
  }

  /**
   * Batch enhance multiple videos efficiently with deduplication
   */
  private batchEnhanceVideos(videos: unknown[]): VideoFile[] {
    if (!videos || videos.length === 0) {
      return [];
    }

    const startTime = performance.now();
    const results: VideoFile[] = [];
    const processedIds = new Set<string>();

    for (const video of videos) {
      try {
        const convertedVideo = convertToVideoFile(video);
        if (!convertedVideo || !convertedVideo.id) {
          continue; // Skip invalid videos
        }

        // Skip duplicates within the same batch
        if (processedIds.has(convertedVideo.id)) {
          if (isDebugEnabled()) {
            console.log('⚠️ Skipping duplicate video in batch:', convertedVideo.id);
          }
          continue;
        }
        processedIds.add(convertedVideo.id);

        const enhanced = this.enhanceVideoData(video);
        results.push(enhanced);
      } catch (error) {
        console.error('❌ Error in batch video enhancement:', error);
        // Continue processing other videos
      }
    }

    const endTime = performance.now();
    if (isDebugEnabled()) {
      console.log(`⚡ Batch enhanced ${results.length} videos in ${(endTime - startTime).toFixed(2)}ms`);
    }

    return results;
  }

  // Project CRUD
  async getProjects(skip: number = 0, limit: number = 100): Promise<Project[]> {
    const response = await this.cachedRequest<{projects: Project[]} | Project[]>('GET', '/api/projects', undefined, {
      params: { skip, limit }
    });
    // Handle both array and object-wrapped responses
    if (Array.isArray(response)) return response as Project[];
    return (response && (response as {projects?: Project[]}).projects) || [];
  }

  async getProject(id: string): Promise<Project> {
    return this.cachedRequest<Project>('GET', `/api/projects/${id}`);
  }

  async createProject(project: ProjectCreate): Promise<Project> {
    try {
      const result = await this.cachedRequest<Project | { success?: boolean; data?: Project }>('POST', '/api/projects', project);
      const projectObj = (result && (result as any).data) ? (result as any).data as Project : (result as Project);
      // Invalidate projects cache after creating a new project
      apiCache.invalidatePattern('/api/projects');
      apiCache.invalidatePattern('/api/dashboard');
      return projectObj;
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

    // Prefer project-based central upload path for better compatibility
    try {
      // 1) Find or create a central project
      let centralProjectId: string | null = null;
      const projects = await this.getProjects(0, 100);
      const central = projects.find(p => p.name === 'Central Store');
      if (central) {
        centralProjectId = central.id;
      } else {
        const created = await this.createProject({
          name: 'Central Store',
          description: 'Central video storage',
          cameraModel: 'Generic',
          cameraView: (CameraType as any).FRONT_FACING_VRU || 'Front-facing VRU',
          signalType: (SignalType as any).GPIO || 'GPIO',
        } as any);
        centralProjectId = created.id;
      }
      // 2) Upload to the project upload endpoint
      if (centralProjectId) {
        return await this.uploadVideo(centralProjectId, file, onProgress);
      }
      throw new Error('Unable to determine central project for upload');
    } catch (fallbackErr) {
      // Final fallback: try direct central upload if supported by backend
      try {
        const response = await this.api.post<VideoFile>('/api/videos/upload', formData, {
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

        apiCache.invalidatePattern('/api/videos');
        apiCache.invalidatePattern('/api/projects');
        return response.data;
      } catch (err) {
        throw this.handleError(err);
      }
    }
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
    try {
      const response = await this.api.get(`/api/videos/${videoId}`);
      if (!hasResponseData(response) || !isObject(response.data)) {
        throw new Error('Invalid video response from server');
      }
      return this.enhanceVideoData(response.data);
    } catch (primaryError) {
      // Fallback 1: Try v1 route
      try {
        const fallback = await this.api.get(`/api/v1/videos/${videoId}`);
        if (!hasResponseData(fallback) || !isObject(fallback.data)) {
          throw primaryError;
        }
        return this.enhanceVideoData(fallback.data as any);
      } catch (fallbackError1) {
        // Fallback 2: Get from video list and filter by ID
        try {
          const listResponse = await this.api.get('/api/videos');
          if (hasResponseData(listResponse) && isObject(listResponse.data) && Array.isArray(listResponse.data.videos)) {
            const video = listResponse.data.videos.find((v: any) => v.id === videoId);
            if (video) {
              return this.enhanceVideoData(video);
            }
          }
          // If no video found in list, throw original error
          throw primaryError;
        } catch (fallbackError2) {
          // All fallbacks failed, throw the most descriptive error
          throw primaryError;
        }
      }
    }
  }

  async deleteVideo(videoId: string): Promise<void> {
    await this.api.delete(`/api/videos/${videoId}`);
  }

  async validateVideo(videoId: string, validated: boolean): Promise<void> {
    try {
      // Use POST method first as backend supports both POST and PATCH
      await this.api.post(`/api/videos/${videoId}/validate`, { validated });
      // Invalidate cached video lists/details
      apiCache.invalidatePattern('/api/videos');
      apiCache.invalidatePattern(`/api/videos/${videoId}`);
    } catch (err) {
      // Fallback 1: PATCH same route
      try {
        await this.api.patch(`/api/videos/${videoId}/validate`, { validated });
        apiCache.invalidatePattern('/api/videos');
        apiCache.invalidatePattern(`/api/videos/${videoId}`);
        return;
      } catch (_) {}
      // Fallback 2: v1 status route widely supported in routers
      const newStatus = validated ? 'validated' : 'annotated';
      await this.api.put(`/api/v1/videos/${videoId}/status`, {
        status: newStatus,
        reason: validated ? 'manual_validation' : 'manual_invalidation'
      });
      apiCache.invalidatePattern('/api/videos');
      apiCache.invalidatePattern(`/api/videos/${videoId}`);
    }
  }

  // Ground truth - Enhanced with fallback data and proper error handling
  async getGroundTruth(videoId: string): Promise<Record<string, unknown>> {
    try {
      const response = await this.api.get(`/api/videos/${videoId}/ground-truth`);
      
      // Transform ground truth data to ensure proper structure
      if (hasResponseData(response) && isObject(response.data)) {
        const objectsData = safeGet(response.data, 'objects', []);
        if (Array.isArray(objectsData)) {
          (response.data as Record<string, unknown>).objects = objectsData.map((obj: unknown) => {
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

  // Ground truth events - Get ground truth events for a video
  async getGroundTruthEvents(videoId: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/videos/${videoId}/ground-truth-events`);
      
      if (hasResponseData(response) && isObject(response.data)) {
        const data = response.data as Record<string, unknown>;
        const events = safeGet(data, 'data.ground_truth_events', safeGet(data, 'ground_truth_events', []));
        
        if (Array.isArray(events)) {
          return {
            success: true,
            data: {
              ground_truth_events: events.map((event: any) => ({
                id: event.id || `gt_${Math.random()}`,
                timestamp: event.timestamp || 0,
                video_frame: event.video_frame || event.frame_number || (event.timestamp * 24) || 0,
                x: event.x || 0,
                y: event.y || 0,
                width: event.width || 100,
                height: event.height || 100,
                class_label: event.class_label || 'pedestrian',
                confidence: event.confidence || 1.0,
                frame_number: event.frame_number || event.video_frame || 0,
                validated: event.validated || true,
                difficult: event.difficult || false
              }))
            }
          };
        }
      }
      
      return {
        success: true,
        data: {
          ground_truth_events: []
        }
      };
    } catch (error: unknown) {
      console.warn(`Ground truth events fetch failed for video ${videoId}:`, error);
      return {
        success: false,
        error: 'Failed to fetch ground truth events',
        data: {
          ground_truth_events: []
        }
      };
    }
  }

  // Enhanced HIL endpoints with ground truth integration
  async getEnhancedHILResults(sessionId: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`);
      return response.data;
    } catch (error: unknown) {
      console.warn(`Enhanced HIL results fetch failed for session ${sessionId}:`, error);
      throw error;
    }
  }

  async getEnhancedHILResultsWithGroundTruth(sessionId: string): Promise<any> {
    try {
      const response = await this.api.get(`/api/enhanced-hil/test-sessions/${sessionId}/ground-truth-comparison`);
      return response.data;
    } catch (error: unknown) {
      console.warn(`Enhanced HIL ground truth comparison fetch failed for session ${sessionId}:`, error);
      throw error;
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
    // Backend expects camelCase data with proper serialization
    const result = await this.cachedRequest<GroundTruthAnnotation>('POST', `/api/videos/${videoId}/annotations`, {
      detectionId: annotation.detectionId,
      frameNumber: annotation.frameNumber,
      timestamp: annotation.timestamp,
      endTimestamp: annotation.endTimestamp,
      vruType: annotation.vruType,
      classLabel: annotation.classLabel,
      boundingBox: {
        x: Number(annotation.boundingBox.x) || 0,
        y: Number(annotation.boundingBox.y) || 0,
        width: Number(annotation.boundingBox.width) || 50,
        height: Number(annotation.boundingBox.height) || 100,
        confidence: Number(annotation.boundingBox.confidence) || 1.0
      },
      occluded: annotation.occluded,
      truncated: annotation.truncated,
      difficult: annotation.difficult,
      validationStatus: annotation.validationStatus,
      validated: annotation.validated,
      confidence: annotation.confidence,
      notes: annotation.notes,
      annotator: annotation.annotator
    });
    // Invalidate cache for video annotations
    apiCache.invalidatePattern(`/api/videos/${videoId}/annotations`);
    return result;
  }

  async updateAnnotation(annotationId: string, updates: Partial<GroundTruthAnnotation>): Promise<GroundTruthAnnotation> {
    // Backend expects camelCase data
    const updateData: Record<string, unknown> = {};
    
    if (updates.detectionId !== undefined) updateData.detectionId = updates.detectionId;
    if (updates.frameNumber !== undefined) updateData.frameNumber = updates.frameNumber;
    if (updates.timestamp !== undefined) updateData.timestamp = updates.timestamp;
    if (updates.endTimestamp !== undefined) updateData.endTimestamp = updates.endTimestamp;
    if (updates.vruType !== undefined) updateData.vruType = updates.vruType;
    if (updates.classLabel !== undefined) updateData.classLabel = updates.classLabel;
    if (updates.boundingBox !== undefined) {
      updateData.boundingBox = {
        x: Number(updates.boundingBox.x) || 0,
        y: Number(updates.boundingBox.y) || 0,
        width: Number(updates.boundingBox.width) || 50,
        height: Number(updates.boundingBox.height) || 100,
        confidence: Number(updates.boundingBox.confidence) || 1.0
      };
    }
    if (updates.occluded !== undefined) updateData.occluded = updates.occluded;
    if (updates.truncated !== undefined) updateData.truncated = updates.truncated;
    if (updates.difficult !== undefined) updateData.difficult = updates.difficult;
    if (updates.validationStatus !== undefined) updateData.validationStatus = updates.validationStatus;
    if (updates.validated !== undefined) updateData.validated = updates.validated;
    if (updates.confidence !== undefined) updateData.confidence = updates.confidence;
    if (updates.notes !== undefined) updateData.notes = updates.notes;
    if (updates.annotator !== undefined) updateData.annotator = updates.annotator;

    const result = await this.cachedRequest<GroundTruthAnnotation>('PUT', `/api/annotations/${annotationId}`, updateData);
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
    try {
      console.log(`Validating annotation ${annotationId}: ${validated}`);
      
      const response = await this.post<GroundTruthAnnotation>(
        `/api/videos/annotations/${annotationId}/validate`,
        { validated }
      );
      
      // Invalidate related cache entries
      apiCache.invalidatePattern('/api/videos');
      apiCache.invalidatePattern('/api/annotations');
      
      return response;
    } catch (error) {
      console.error('Annotation validation failed, using fallback:', error);
      
      // Fallback to mock response if API fails
      const mockAnnotation: GroundTruthAnnotation = {
        id: annotationId,
        video_id: '', // Will be filled by the calling component
        vru_type: 'pedestrian' as VRUType,
        frame_number: 0,
        timestamp: 0,
        bounding_box: { x: 0, y: 0, width: 0, height: 0 },
        confidence: 1.0,
        validated: validated,
        created_at: new Date().toISOString(),
      };
      
      // Invalidate related cache entries
      apiCache.invalidatePattern('/api/videos');
      apiCache.invalidatePattern('/api/annotations');
      return mockAnnotation;
    }
  }

  async getAnnotationsByDetection(detectionId: string): Promise<GroundTruthAnnotation[]> {
    return this.cachedRequest<GroundTruthAnnotation[]>('GET', `/api/annotations/detection/${detectionId}`);
  }

  async createAnnotationSession(videoId: string, projectId: string): Promise<AnnotationSession> {
    const result = await this.cachedRequest<AnnotationSession>('POST', '/api/annotation-sessions', {
      videoId: videoId,
      projectId: projectId
    });
    return result;
  }

  async getAnnotationSession(sessionId: string): Promise<AnnotationSession> {
    return this.cachedRequest<AnnotationSession>('GET', `/api/annotation-sessions/${sessionId}`);
  }

  async updateAnnotationSession(sessionId: string, updates: Partial<AnnotationSession>): Promise<AnnotationSession> {
    const result = await this.cachedRequest<AnnotationSession>('PUT', `/api/annotation-sessions/${sessionId}`, {
      status: updates.status,
      currentFrame: updates.currentFrame,
      totalDetections: updates.totalDetections,
      validatedDetections: updates.validatedDetections
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
    try {
      const params = projectId ? { projectId: projectId } : {};
      const response = await this.api.get<TestSession[]>('/api/test-sessions', { params });
      return Array.isArray(response.data) ? response.data : [];
    } catch (e) {
      // Gracefully degrade when backend returns 500 so UI can still render
      if (isDebugEnabled()) console.warn('getTestSessions failed, returning empty list:', e);
      return [];
    }
  }

  // Get enhanced test results sessions for a specific project
  async getEnhancedTestResultsSessions(projectId: string, limit: number = 10): Promise<any[]> {
    try {
      return this.cachedRequest<any[]>('GET', `/api/results/projects/${projectId}/sessions`, undefined, { params: { limit } });
    } catch (error) {
      console.warn('Enhanced results API not available for project sessions:', error);
      // Fallback to regular sessions
      return this.getTestSessions(projectId);
    }
  }

  async getTestSession(sessionId: string): Promise<TestSession> {
    const response = await this.api.get<TestSession>(`/api/test-sessions/${sessionId}`);
    return response.data;
  }

  async createTestSession(testSession: TestSessionCreate): Promise<TestSession> {
    const response = await this.api.post<TestSession>('/api/test-sessions', testSession);
    return response.data;
  }

  async getTestResults(sessionId: string): Promise<Record<string, unknown>> {
    try {
      // First try the enhanced results API for detailed session results
      const response = await this.cachedRequest<any>('GET', `/api/results/sessions/${sessionId}/detailed`);
      return response;
    } catch (error) {
      console.warn('Enhanced results API not available, falling back to standard API:', error);
      // Fallback to standard API
      const response = await this.api.get(`/api/test-sessions/${sessionId}/results`);
      return response.data;
    }
  }

  // Dashboard
  async getDashboardStats(): Promise<EnhancedDashboardStats> {
    // Prefer enhanced stats; gracefully fall back to basic stats and expand
    try {
      return await this.cachedRequest<EnhancedDashboardStats>('GET', '/api/dashboard/stats/enhanced');
    } catch (err) {
      if (isAxiosError(err)) {
        try {
          const basic = await this.cachedRequest<{
            project_count: number;
            video_count: number;
            test_session_count: number;
            detection_event_count: number;
            average_accuracy: number;
            active_tests: number;
          }>('GET', '/api/dashboard/stats');
          // Expand to EnhancedDashboardStats with sensible defaults
          const enhanced: EnhancedDashboardStats = {
            ...basic,
            total_detections: basic.detection_event_count,
            confidence_intervals: { precision: [0, 0], recall: [0, 0], f1_score: [0, 0] },
            trend_analysis: { accuracy: 'stable', detectionRate: 'stable', performance: 'stable' },
            signal_processing_metrics: { totalSignals: basic.detection_event_count, successRate: basic.average_accuracy, avgProcessingTime: 0 },
          } as EnhancedDashboardStats;
          return enhanced;
        } catch (fallbackErr) {
          throw this.handleError(fallbackErr);
        }
      }
      throw this.handleError(err);
    }
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

  // Detection Pipeline with enhanced result handling and extended timeout
  async runDetectionPipeline(videoId: string, config: DetectionPipelineConfig): Promise<DetectionPipelineResult> {
    const result = await this.cachedRequest<DetectionPipelineResponse>('POST', '/api/detection/pipeline/run', { 
      video_id: videoId,  // Backend expects video_id, not videoId
      confidence_threshold: config.confidenceThreshold,
      nms_threshold: config.nmsThreshold,
      model_name: config.modelName,
      target_classes: config.targetClasses
    }, {
      timeout: 120000  // 120 seconds to handle real YOLOv8 processing (70s + buffer)
    });
    
    // Ensure the result conforms to DetectionPipelineResult interface
    // Backend returns DetectionPipelineResponse with snake_case - normalize to frontend format
    const baseResult = {
      videoId: result.videoId || result.video_id || videoId,
      detections: result.detections || [],
      processingTime: result.processingTime || result.processing_time || 0,
      modelUsed: result.modelUsed || result.model_used || config.modelName || 'unknown',
      totalDetections: result.totalDetections || result.total_detections || (result.detections ? result.detections.length : 0),
      confidenceDistribution: result.confidenceDistribution || result.confidence_distribution || {},
      success: result.success !== undefined ? result.success : true
    };
    
    // Build final result with conditional error property for exactOptionalPropertyTypes
    const normalizedResult: DetectionPipelineResult = result.error
      ? { ...baseResult, error: result.error }
      : baseResult;
    
    return normalizedResult;
  }

  async getAvailableModels(): Promise<{models: string[], default: string, recommended: string}> {
    return this.cachedRequest('GET', '/api/detection/models/available');
  }

  // Get detection results for a video
  async getVideoDetections(videoId: string): Promise<Record<string, unknown>[]> {
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
  async getTestSessionDetections(sessionId: string): Promise<Record<string, unknown>[]> {
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
      signalType: signalType,
      signalData: signalData,
      processingConfig: config
    });
  }

  async getSupportedProtocols(): Promise<{protocols: string[], capabilities: Record<string, string[]>}> {
    return this.cachedRequest('GET', '/api/signals/protocols/supported');
  }

  // Enhanced Project Management
  async configurePassFailCriteria(projectId: string, criteria: Omit<PassFailCriteria, 'id' | 'projectId' | 'createdAt'>): Promise<PassFailCriteria> {
    return this.cachedRequest<PassFailCriteria>('POST', `/api/projects/${projectId}/criteria/configure`, {
      minPrecision: criteria.minPrecision,
      minRecall: criteria.minRecall,
      minF1Score: criteria.minF1Score,
      maxLatencyMs: criteria.maxLatencyMs
    });
  }

  async getIntelligentAssignments(projectId: string): Promise<VideoAssignment[]> {
    return this.cachedRequest<VideoAssignment[]>('GET', `/api/projects/${projectId}/assignments/intelligent`);
  }

  // Statistical Validation
  async runStatisticalValidation(testSessionId: string, confidenceLevel: number = 0.95): Promise<StatisticalValidation> {
    return this.cachedRequest<StatisticalValidation>('POST', '/api/validation/statistical/run', {
      testSessionId: testSessionId,
      confidenceLevel: confidenceLevel
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

  // Video Library and Ground Truth Integration with fallback
  async getAvailableGroundTruthVideos(): Promise<VideoFile[]> {
    try {
      const response = await this.cachedRequest<VideoFile[]>('GET', '/api/ground-truth/videos/available');
      // Enhance video data with proper URLs and status mapping - optimized batch processing
      return this.batchEnhanceVideos(response);
    } catch (error) {
      console.warn('Ground truth videos endpoint not available, falling back to general videos:', error);
      
      // Fallback to general videos endpoint
      try {
        const allVideosResponse = await this.getAllVideos();
        const videos = allVideosResponse.videos || [];
        console.log('✅ Fallback successful - loaded videos from /api/videos:', videos.length);
        return videos;
      } catch (fallbackError) {
        console.error('Both ground truth and general videos endpoints failed:', fallbackError);
        // Return empty array rather than throwing to prevent page crashes
        return [];
      }
    }
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
    // Enhance video data with proper URLs and status mapping - optimized batch processing
    return this.batchEnhanceVideos(response);
  }

  async unlinkVideoFromProject(projectId: string, videoId: string): Promise<void> {
    await this.cachedRequest<void>('DELETE', `/api/projects/${projectId}/videos/${videoId}/unlink`);
    // Invalidate related cache entries
    apiCache.invalidate('GET', `/api/projects/${projectId}`);
    apiCache.invalidatePattern('/api/projects');
    apiCache.invalidatePattern(`/api/projects/${projectId}/videos`);
  }

  async integrateAnnotationIntoGroundTruth(annotationId: string): Promise<any> {
    return this.cachedRequest('POST', `/api/ground-truth/integrate/annotation/${annotationId}`);
  }

  // LabJack Signal Validation endpoints
  async checkLabJackStatus(): Promise<{connected: boolean, mock_mode?: boolean, voltage_threshold?: number, channels?: string[], sample_rate?: number, current_voltages?: Record<string, number>, error?: string}> {
    // Don't cache LabJack status - always fetch fresh data
    return this.get<{connected: boolean, mock_mode?: boolean, voltage_threshold?: number, channels?: string[], sample_rate?: number, current_voltages?: Record<string, number>, error?: string}>('/api/labjack/status');
  }

  async initializeLabJack(config?: {voltage_threshold?: {lower: number, upper: number}, channels?: string[], sample_rate?: number}): Promise<{status: string, message: string, mock_mode?: boolean, error?: string}> {
    return this.cachedRequest<{status: string, message: string, mock_mode?: boolean, error?: string}>('POST', '/api/signal-validation/labjack/initialize', config || {});
  }

  async configureLabJack(config: {voltage_threshold?: number, channels?: string[], sample_rate?: number}): Promise<{status: string, message: string}> {
    return this.cachedRequest<{status: string, message: string}>('POST', '/api/signal-validation/labjack/configure', config);
  }

  async startSignalMonitoring(testSessionId: string = 'default-session'): Promise<{status: string, message: string, test_session_id?: string}> {
    return this.cachedRequest<{status: string, message: string, test_session_id?: string}>('POST', `/api/signal-validation/monitoring/start/${testSessionId}`, {});
  }

  async stopSignalMonitoring(): Promise<{status: string, message: string}> {
    return this.cachedRequest<{status: string, message: string}>('POST', '/api/signal-validation/monitoring/stop', {});
  }

  async getSignalStatistics(testSessionId: string): Promise<{total_signals: number, valid_signals: number, invalid_signals: number, average_delay: number, statistics: Record<string, unknown>}> {
    return this.cachedRequest<{total_signals: number, valid_signals: number, invalid_signals: number, average_delay: number, statistics: Record<string, unknown>}>('GET', `/api/signal-validation/statistics/${testSessionId}`);
  }

  async testSignalValidationConnection(): Promise<{status: string, components: Record<string, unknown>}> {
    return this.cachedRequest<{status: string, components: Record<string, unknown>}>('GET', '/api/signal-validation/test-connection');
  }

  // Enhanced Test Workflow endpoints
  async startEnhancedTestWorkflow(config: {
    projectId: string;
    detectionWindowMs: number;
    voltageThreshold: number;
    sampleRate: number;
    channels: string[];
  }): Promise<{message: string; projectId: string; videoCount: number; sessionId: string}> {
    return this.cachedRequest<{message: string; projectId: string; videoCount: number; sessionId: string}>('POST', '/api/enhanced-test-workflow/start', {
      project_id: config.projectId,
      detection_window_ms: config.detectionWindowMs,
      voltage_threshold: config.voltageThreshold,
      sample_rate: config.sampleRate,
      channels: config.channels
    });
  }

  async stopEnhancedTestWorkflow(): Promise<{message: string; results: unknown[]}> {
    return this.cachedRequest<{message: string; results: unknown[]}>('POST', '/api/enhanced-test-workflow/stop', {});
  }

  async getEnhancedTestWorkflowStatus(): Promise<{
    active: boolean;
    currentVideo: number;
    totalVideos: number;
    resultsCount: number;
    sessionId?: string;
  }> {
    return this.cachedRequest<{
      active: boolean;
      currentVideo: number;
      totalVideos: number;
      resultsCount: number;
      sessionId?: string;
    }>('GET', '/api/enhanced-test-workflow/status');
  }

  async getEnhancedTestWorkflowResults(): Promise<{
    active: boolean;
    results: Array<{
      videoId: string;
      videoName: string;
      expectedDetectionTime: number;
      actualDetectionTime?: number;
      detectionDelayMs?: number;
      status: 'pass' | 'fail_no_detection' | 'fail_timeout';
    }>;
    summary: {
      totalVideos: number;
      passed: number;
      failed: number;
      avgLatency: number;
    };
  }> {
    return this.cachedRequest('GET', '/api/enhanced-test-workflow/results');
  }

  // Enhanced Test Session Management - integrate with existing sessions
  async getEnhancedTestSessions(projectId?: string): Promise<Array<{
    id: string;
    name: string;
    projectId: string;
    status: 'created' | 'running' | 'completed' | 'failed';
    videoCount: number;
    results?: unknown[];
    createdAt: string;
    completedAt?: string;
  }>> {
    const params = projectId ? { projectId } : {};
    return this.cachedRequest('GET', '/api/enhanced-test-workflow/sessions', undefined, { params });
  }

  async createEnhancedTestSession(sessionData: {
    name: string;
    description?: string;
    projectId: string;
    videoIds: string[];
    config: {
      detectionWindowMs: number;
      voltageThreshold: number;
      sampleRate: number;
      channels: string[];
    };
  }): Promise<{
    id: string;
    name: string;
    projectId: string;
    status: 'created';
    sessionData: unknown;
  }> {
    return this.cachedRequest('POST', '/api/enhanced-test-workflow/sessions', {
      name: sessionData.name,
      description: sessionData.description,
      project_id: sessionData.projectId,
      video_ids: sessionData.videoIds,
      config: sessionData.config
    });
  }

  async runEnhancedTestSession(sessionId: string): Promise<{
    message: string;
    sessionId: string;
    status: string;
  }> {
    return this.cachedRequest('POST', `/api/enhanced-test-workflow/sessions/${sessionId}/run`, {});
  }

  async getEnhancedTestSessionResults(sessionId: string): Promise<{
    sessionId: string;
    results: unknown[];
    summary: {
      totalVideos: number;
      passed: number;
      failed: number;
      avgDetectionDelay: number;
      testDuration: number;
    };
  }> {
    return this.cachedRequest('GET', `/api/enhanced-test-workflow/sessions/${sessionId}/results`);
  }

  // Boundary Box API Endpoints
  async validateBoundingBox(boundingBox: unknown, frameSize?: { width: number; height: number }): Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
    atFrameOrigin: boolean;
    requiresSnapping: boolean;
    snapPoints?: Array<{ x: number; y: number; type: string }>;
  }> {
    return this.cachedRequest('POST', '/api/boundary/validate', {
      boundingBox,
      frameSize
    });
  }

  async processBoundingBox(boundingBox: unknown, options: {
    enableSnapping?: boolean;
    snappingConfig?: unknown;
    frameSize?: { width: number; height: number };
  }): Promise<{
    processedBox: unknown;
    modifications: string[];
    snappingApplied: boolean;
    stability: number;
  }> {
    return this.cachedRequest('POST', '/api/boundary/process', {
      boundingBox,
      options
    });
  }

  async getFrame80DebugData(videoId: string): Promise<{
    debugData: Array<{
      frameNumber: number;
      boundingBox: unknown;
      expectedCoordinates: string;
      actualCoordinates: string;
      hasSnappingIssue: boolean;
      confidenceLevel: number;
      detectionId: string;
      timestamp: string;
    }>;
  }> {
    return this.cachedRequest('GET', `/api/boundary/debug/frame-80/${videoId}`);
  }

  async fixFrame80Issues(videoId: string, frameNumber: number = 80): Promise<{
    success: boolean;
    fixedBox?: unknown;
    message: string;
  }> {
    return this.cachedRequest('POST', '/api/boundary/fix/frame-80', {
      videoId,
      frameNumber
    });
  }

  async updateSnappingConfig(config: unknown): Promise<{ success: boolean }> {
    return this.cachedRequest('POST', '/api/boundary/snapping/config', config);
  }

  async calculateBoundingBoxAccuracy(boundingBox: unknown, groundTruth?: unknown): Promise<{
    accuracy: number;
  }> {
    return this.cachedRequest('POST', '/api/boundary/accuracy', {
      boundingBox,
      groundTruth
    });
  }

  async batchProcessBoundingBoxes(boundingBoxes: unknown[], options: {
    enableSnapping?: boolean;
    snappingConfig?: unknown;
    frameSize?: { width: number; height: number };
  }): Promise<{
    results: Array<{
      success: boolean;
      processedBox: unknown;
      originalBox: unknown;
      modifications: string[];
      processingTime: number;
      snappingApplied: boolean;
      stability: number;
    }>;
  }> {
    return this.cachedRequest('POST', '/api/boundary/batch-process', {
      boundingBoxes,
      options
    });
  }

  // Pedestrian Detection API Endpoints
  async detectPedestriansInFrame(videoId: string, frameNumber: number, config: {
    confidenceThreshold: number;
    nmsThreshold: number;
    modelName: string;
    targetClasses: string[];
    enableTracking: boolean;
    trackingPersistence: number;
  }, frameData?: number[]): Promise<{
    detections: Array<{
      id: string;
      type: string;
      confidence: number;
      boundingBox: unknown;
      trackingId: string;
      attributes: unknown;
    }>;
    objects: Array<unknown>; // For compatibility with existing code
  }> {
    return this.cachedRequest('POST', '/api/pedestrian/detect-frame', {
      videoId,
      frameNumber,
      config,
      frameData
    });
  }

  async detectPedestriansInFrameRange(videoId: string, startFrame: number, endFrame: number, config: {
    confidenceThreshold: number;
    nmsThreshold: number;
    modelName: string;
    targetClasses: string[];
    enableTracking: boolean;
    trackingPersistence: number;
  }): Promise<{
    results: Record<number, Array<unknown>>;
  }> {
    return this.cachedRequest('POST', '/api/pedestrian/detect-range', {
      videoId,
      startFrame,
      endFrame,
      config
    });
  }

  async analyzeFrame80Pedestrians(videoId: string): Promise<{
    issues: string[];
    recommendations: string[];
    hasDetection: boolean;
    confidence: number;
    coordinates: string;
    boundingBox: unknown;
  }> {
    return this.cachedRequest('GET', `/api/pedestrian/analyze-frame-80/${videoId}`);
  }

  async analyzeConfidenceLevels(trackingId: string, frameRange?: { start: number; end: number }): Promise<{
    frameNumber: number;
    confidence: number;
    confidenceHistory: number[];
    stabilityScore: number;
    isStable: boolean;
    confidenceVariation: number;
    recommendedAction: 'accept' | 'review' | 'reject';
  }> {
    return this.cachedRequest('POST', '/api/pedestrian/analyze-confidence', {
      trackingId,
      frameRange
    });
  }

  async updatePedestrianDetectionConfig(config: {
    confidenceThreshold: number;
    nmsThreshold: number;
    modelName: string;
    targetClasses: string[];
    enableTracking: boolean;
    trackingPersistence: number;
  }): Promise<{ success: boolean }> {
    return this.cachedRequest('POST', '/api/pedestrian/config', config);
  }

  // Backend Integration with Node.js Boundary Detection System
  async callBoundaryDetectionSystem(endpoint: string, data: unknown): Promise<unknown> {
    // Integrate with the Node.js boundary detection system in /src/boundary-detection/
    return this.cachedRequest('POST', `/api/boundary-detection/${endpoint}`, data);
  }

  async validateAndProcessBoundaryBox(boundingBox: unknown): Promise<{
    isValid: boolean;
    processedBox: unknown;
    modifications: string[];
    validation: unknown;
    processing: unknown;
  }> {
    return this.cachedRequest('POST', '/api/boundary-detection/validate-and-process', {
      boundingBox
    });
  }

  async checkBoundarySnapping(boundingBox: unknown): Promise<{
    hasSnapping: boolean;
    errors: string[];
    originalBox: unknown;
    message: string;
  }> {
    return this.cachedRequest('POST', '/api/boundary-detection/check-snapping', {
      boundingBox
    });
  }

  async processPedestrianDetectionFrame(frameData: {
    frameNumber: number;
    image?: unknown;
    metadata?: unknown;
  }): Promise<{
    success: boolean;
    frameNumber: number;
    objects: Array<{
      id: string;
      type: string;
      confidence: number;
      boundingBox: unknown;
      trackingId: string;
      attributes: unknown;
    }>;
    processingTime: number;
    modelVersion: string;
  }> {
    return this.cachedRequest('POST', '/api/boundary-detection/pedestrian-detection', frameData);
  }

  async getBoundaryDetectionStatistics(): Promise<{
    totalFramesProcessed: number;
    averageConfidence: number;
    detectionsByFrame: Record<number, number>;
    consistencyIssues: Array<{
      frame: number;
      issue: string;
      coordinates: string;
    }>;
  }> {
    return this.cachedRequest('GET', '/api/boundary-detection/statistics');
  }

  async validatePedestrianDetection(detection: unknown): Promise<{
    isValid: boolean;
    issues: string[];
    detection: unknown;
  }> {
    return this.cachedRequest('POST', '/api/boundary-detection/validate-detection', {
      detection
    });
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
export const getEnhancedTestSessions = apiServiceInstance.getEnhancedTestSessions.bind(apiServiceInstance);
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
export const integrateAnnotationIntoGroundTruth = apiServiceInstance.integrateAnnotationIntoGroundTruth.bind(apiServiceInstance);
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
export const checkLabJackStatus = apiServiceInstance.checkLabJackStatus.bind(apiServiceInstance);
export const initializeLabJack = apiServiceInstance.initializeLabJack.bind(apiServiceInstance);
export const configureLabJack = apiServiceInstance.configureLabJack.bind(apiServiceInstance);
export const startSignalMonitoring = apiServiceInstance.startSignalMonitoring.bind(apiServiceInstance);
export const stopSignalMonitoring = apiServiceInstance.stopSignalMonitoring.bind(apiServiceInstance);
export const getSignalStatistics = apiServiceInstance.getSignalStatistics.bind(apiServiceInstance);
export const testSignalValidationConnection = apiServiceInstance.testSignalValidationConnection.bind(apiServiceInstance);
export const startEnhancedTestWorkflow = apiServiceInstance.startEnhancedTestWorkflow.bind(apiServiceInstance);
export const stopEnhancedTestWorkflow = apiServiceInstance.stopEnhancedTestWorkflow.bind(apiServiceInstance);
export const getEnhancedTestWorkflowStatus = apiServiceInstance.getEnhancedTestWorkflowStatus.bind(apiServiceInstance);
export const getEnhancedTestWorkflowResults = apiServiceInstance.getEnhancedTestWorkflowResults.bind(apiServiceInstance);
export const createEnhancedTestSession = apiServiceInstance.createEnhancedTestSession.bind(apiServiceInstance);
export const runEnhancedTestSession = apiServiceInstance.runEnhancedTestSession.bind(apiServiceInstance);
export const getEnhancedTestSessionResults = apiServiceInstance.getEnhancedTestSessionResults.bind(apiServiceInstance);

// Boundary Box API Exports
export const validateBoundingBox = apiServiceInstance.validateBoundingBox.bind(apiServiceInstance);
export const processBoundingBox = apiServiceInstance.processBoundingBox.bind(apiServiceInstance);
export const getFrame80DebugData = apiServiceInstance.getFrame80DebugData.bind(apiServiceInstance);
export const fixFrame80Issues = apiServiceInstance.fixFrame80Issues.bind(apiServiceInstance);
export const updateSnappingConfig = apiServiceInstance.updateSnappingConfig.bind(apiServiceInstance);
export const calculateBoundingBoxAccuracy = apiServiceInstance.calculateBoundingBoxAccuracy.bind(apiServiceInstance);
export const batchProcessBoundingBoxes = apiServiceInstance.batchProcessBoundingBoxes.bind(apiServiceInstance);

// Pedestrian Detection API Exports
export const detectPedestriansInFrame = apiServiceInstance.detectPedestriansInFrame.bind(apiServiceInstance);
export const detectPedestriansInFrameRange = apiServiceInstance.detectPedestriansInFrameRange.bind(apiServiceInstance);
export const analyzeFrame80Pedestrians = apiServiceInstance.analyzeFrame80Pedestrians.bind(apiServiceInstance);
export const analyzeConfidenceLevels = apiServiceInstance.analyzeConfidenceLevels.bind(apiServiceInstance);
export const updatePedestrianDetectionConfig = apiServiceInstance.updatePedestrianDetectionConfig.bind(apiServiceInstance);

// Backend Integration Exports
export const callBoundaryDetectionSystem = apiServiceInstance.callBoundaryDetectionSystem.bind(apiServiceInstance);
export const validateAndProcessBoundaryBox = apiServiceInstance.validateAndProcessBoundaryBox.bind(apiServiceInstance);
export const checkBoundarySnapping = apiServiceInstance.checkBoundarySnapping.bind(apiServiceInstance);
export const processPedestrianDetectionFrame = apiServiceInstance.processPedestrianDetectionFrame.bind(apiServiceInstance);
export const getBoundaryDetectionStatistics = apiServiceInstance.getBoundaryDetectionStatistics.bind(apiServiceInstance);
export const validatePedestrianDetection = apiServiceInstance.validatePedestrianDetection.bind(apiServiceInstance);

export default apiService;
