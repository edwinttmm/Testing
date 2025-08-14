import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import {
  ApiResponse,
  ApiError,
  Project,
  ProjectCreate,
  ProjectUpdate,
  VideoFile,
  VideoUpload,
  TestSession,
  TestSessionCreate,
  DashboardStats,
  ChartData,
  User
} from './types';
import { NetworkError, AppError as CustomApiError, ErrorFactory } from '../utils/errorTypes';
import errorReporting from './errorReporting';
import { apiCache } from '../utils/apiCache';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
      timeout: 30000, // Increased timeout to 30 seconds
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor - no auth required
    this.api.interceptors.request.use(
      (config) => {
        // No authentication required - removed token handling
        return config;
      },
      (error) => {
        return Promise.reject(this.handleError(error));
      }
    );

    // Response interceptor - handle responses and errors
    this.api.interceptors.response.use(
      (response: AxiosResponse) => {
        return response;
      },
      (error: AxiosError) => {
        return Promise.reject(this.handleError(error));
      }
    );
  }

  private handleError(error: AxiosError | any): ApiError {
    const apiError: ApiError = {
      message: 'An unexpected error occurred',
      status: 500,
    };

    let customError: Error;
    let errorMessage = 'An unexpected error occurred';

    try {
      if (error?.response) {
        // Server responded with error status
        apiError.status = error.response.status;
        const responseData = error.response.data;
        
        // Safely extract error message
        if (typeof responseData === 'string') {
          errorMessage = responseData;
        } else if (responseData && typeof responseData === 'object') {
          errorMessage = responseData.message || 
                       responseData.detail || 
                       responseData.error || 
                       `Server error: ${error.response.status}`;
        } else {
          errorMessage = `HTTP ${error.response.status}: ${error.response.statusText || 'Unknown error'}`;
        }
        
        apiError.message = errorMessage;
        apiError.details = responseData;

        // Create custom error for error boundary handling
        customError = ErrorFactory.createApiError(
          error.response,
          responseData,
          { 
            originalError: error,
            method: error.config?.method,
            url: error.config?.url 
          }
        );

      } else if (error?.request) {
        // Network error - no response received
        errorMessage = 'Network error - please check your connection';
        apiError.message = errorMessage;
        apiError.code = 'NETWORK_ERROR';
        
        customError = ErrorFactory.createNetworkError(
          undefined,
          { 
            originalError: error,
            method: error.config?.method,
            url: error.config?.url 
          }
        );

      } else if (error?.code === 'ECONNABORTED') {
        // Request timeout
        errorMessage = 'Request timeout - please try again';
        apiError.message = errorMessage;
        apiError.code = 'TIMEOUT_ERROR';
        customError = new Error(errorMessage);

      } else {
        // Request setup error or other error
        errorMessage = error?.message || 'Unknown error occurred';
        
        // Prevent [object Object] error messages
        if (errorMessage === '[object Object]' || typeof errorMessage !== 'string') {
          errorMessage = 'An error occurred while processing your request';
        }
        
        apiError.message = errorMessage;
        customError = new Error(`Request error: ${errorMessage}`);
      }

      // Safely build error context
      const errorContext: Record<string, any> = {
        timestamp: new Date().toISOString(),
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown'
      };
      
      if (error?.config?.method) errorContext.method = error.config.method;
      if (error?.config?.url) errorContext.url = error.config.url;
      if (error?.response?.status) errorContext.status = error.response.status;
      if (error?.response?.statusText) errorContext.statusText = error.response.statusText;
      if (error?.code) errorContext.errorCode = error.code;
      
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
      
      const fallbackError: ApiError = {
        message: 'An unexpected error occurred',
        status: 500,
        code: 'UNKNOWN_ERROR'
      };

      return fallbackError;
    }
  }


  // Enhanced request method with caching and deduplication
  private async cachedRequest<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    url: string,
    data?: any,
    config?: any
  ): Promise<T> {
    const cacheKey = method + url;
    const params = config?.params;
    
    // Only cache GET requests
    if (method === 'GET') {
      // Check cache first
      const cached = apiCache.get<T>(method, url, params);
      if (cached !== null) {
        return cached;
      }

      // Check for pending request to avoid duplication
      const pending = apiCache.getPendingRequest(method, url, params);
      if (pending) {
        return pending;
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
        apiCache.set(method, url, response.data, params);
      }
      return response.data;
    });

    // Track pending request for deduplication
    if (method === 'GET') {
      apiCache.setPendingRequest(method, url, requestPromise, params);
    }

    return requestPromise;
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
    } catch (error: any) {
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
    const response = await this.api.get<VideoFile[]>(`/api/projects/${projectId}/videos`);
    return response.data;
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

  async getVideo(videoId: string): Promise<VideoFile> {
    const response = await this.api.get<VideoFile>(`/api/videos/${videoId}`);
    return response.data;
  }

  async deleteVideo(videoId: string): Promise<void> {
    await this.api.delete(`/api/videos/${videoId}`);
  }

  // Ground truth
  async getGroundTruth(videoId: string): Promise<any> {
    const response = await this.api.get(`/api/videos/${videoId}/ground-truth`);
    return response.data;
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
  async getDashboardStats(): Promise<DashboardStats> {
    return this.cachedRequest<DashboardStats>('GET', '/api/dashboard/stats');
  }

  async getChartData(): Promise<ChartData> {
    return this.cachedRequest<ChartData>('GET', '/api/dashboard/charts');
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    return this.cachedRequest<{ status: string }>('GET', '/health');
  }

  // Generic request methods for custom endpoints
  async get<T = any>(url: string, config?: any): Promise<T> {
    const response = await this.api.get<T>(url, config);
    return response.data;
  }

  async post<T = any>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.api.post<T>(url, data, config);
    return response.data;
  }

  async put<T = any>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.api.put<T>(url, data, config);
    return response.data;
  }

  async delete<T = any>(url: string, config?: any): Promise<T> {
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
export const getVideo = apiServiceInstance.getVideo.bind(apiServiceInstance);
export const deleteVideo = apiServiceInstance.deleteVideo.bind(apiServiceInstance);
export const getGroundTruth = apiServiceInstance.getGroundTruth.bind(apiServiceInstance);
export const getTestSessions = apiServiceInstance.getTestSessions.bind(apiServiceInstance);
export const getTestSession = apiServiceInstance.getTestSession.bind(apiServiceInstance);
export const createTestSession = apiServiceInstance.createTestSession.bind(apiServiceInstance);
export const getTestResults = apiServiceInstance.getTestResults.bind(apiServiceInstance);
export const getDashboardStats = apiServiceInstance.getDashboardStats.bind(apiServiceInstance);
export const getChartData = apiServiceInstance.getChartData.bind(apiServiceInstance);
export const healthCheck = apiServiceInstance.healthCheck.bind(apiServiceInstance);

export default apiService;