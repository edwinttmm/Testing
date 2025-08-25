import axios, { AxiosInstance, AxiosResponse, AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import {
  ApiError,
  Project,
  ProjectCreate,
  ProjectUpdate,
  VideoFile,
  TestSession,
  TestSessionCreate,
  DashboardStats,
  ChartData
} from './types';
import { ErrorFactory } from '../utils/errorTypes';
import errorReporting from './errorReporting';
import { apiCache } from '../utils/apiCache';

interface RetryConfig {
  maxRetries: number;
  backoffFactor: number;
  retryableErrorCodes: string[];
  retryableStatusCodes: number[];
}

interface RequestMetrics {
  startTime: number;
  endTime?: number;
  duration?: number;
  retryCount: number;
  cacheHit?: boolean;
}

class EnhancedApiService {
  private api: AxiosInstance;
  private retryConfig: RetryConfig;
  private pendingRequests: Map<string, Promise<unknown>>;
  private requestMetrics: Map<string, RequestMetrics>;
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private isOnline: boolean = navigator.onLine;
  private baseURL: string;

  constructor() {
    this.baseURL = process.env.REACT_APP_API_URL || 'http://155.138.239.131:8000';
    this.pendingRequests = new Map();
    this.requestMetrics = new Map();
    
    this.retryConfig = {
      maxRetries: 3,
      backoffFactor: 2,
      retryableErrorCodes: ['ECONNRESET', 'ENOTFOUND', 'ECONNABORTED', 'ETIMEDOUT', 'NETWORK_ERROR'],
      retryableStatusCodes: [408, 429, 500, 502, 503, 504]
    };

    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
    this.setupHealthCheck();
    this.setupNetworkListeners();
  }

  private setupInterceptors() {
    // Request interceptor
    this.api.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // Add request ID for tracking
        const requestId = this.generateRequestId();
        (config as any).metadata = { requestId, startTime: Date.now() };
        
        // Track request metrics
        this.requestMetrics.set(requestId, {
          startTime: Date.now(),
          retryCount: 0
        });

        // Add correlation ID for debugging
        if (!config.headers) {
          config.headers = {} as any;
        }
        (config.headers as any)['X-Correlation-ID'] = requestId;
        
        console.log(`🚀 API Request [${requestId}]: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('Request interceptor error:', error);
        throw this.handleError(error);
      }
    );

    // Response interceptor
    this.api.interceptors.response.use(
      (response: AxiosResponse) => {
        const requestId = (response.config as any)?.metadata?.requestId;
        if (requestId) {
          const metrics = this.requestMetrics.get(requestId);
          if (metrics) {
            metrics.endTime = Date.now();
            metrics.duration = metrics.endTime - metrics.startTime;
            console.log(`✅ API Success [${requestId}]: ${metrics.duration}ms`);
          }
        }
        return response;
      },
      (error: AxiosError) => {
        const requestId = (error.config as any)?.metadata?.requestId;
        if (requestId) {
          const metrics = this.requestMetrics.get(requestId);
          if (metrics) {
            metrics.endTime = Date.now();
            metrics.duration = metrics.endTime - metrics.startTime;
            console.error(`❌ API Error [${requestId}]: ${metrics.duration}ms - ${error.message}`);
          }
        }
        throw this.handleError(error);
      }
    );
  }

  private setupHealthCheck() {
    // Periodic health check
    this.healthCheckInterval = setInterval(async () => {
      try {
        await this.healthCheck();
        console.log('🩺 Health check: OK');
      } catch (error) {
        console.warn('🩺 Health check failed:', error);
      }
    }, 60000); // Check every minute
  }

  private setupNetworkListeners() {
    window.addEventListener('online', () => {
      console.log('📶 Network: Online');
      this.isOnline = true;
    });

    window.addEventListener('offline', () => {
      console.log('📶 Network: Offline');
      this.isOnline = false;
    });
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateCacheKey(method: string, url: string, params?: Record<string, unknown>, data?: Record<string, unknown> | FormData): string {
    const key = `${method.toUpperCase()}_${url}`;
    if (params) {
      const paramString = new URLSearchParams(params as Record<string, string>).toString();
      return `${key}_${paramString}`;
    }
    if (data && method !== 'GET') {
      if (data instanceof FormData) {
        // For FormData, create a simple key based on size and type
        return `${key}_formdata_${Date.now()}`;
      } else {
        const dataString = JSON.stringify(data);
        return `${key}_${btoa(dataString)}`;
      }
    }
    return key;
  }

  private isRetryableError(error: AxiosError): boolean {
    // Check error code
    if (error.code && this.retryConfig.retryableErrorCodes.includes(error.code)) {
      return true;
    }

    // Check status code
    if (error.response?.status && this.retryConfig.retryableStatusCodes.includes(error.response.status)) {
      return true;
    }

    // Check for specific error types
    if (error.message.toLowerCase().includes('network')) {
      return true;
    }

    return false;
  }

  private calculateBackoffDelay(attempt: number): number {
    const baseDelay = 1000; // 1 second
    const maxDelay = 30000; // 30 seconds
    const delay = baseDelay * Math.pow(this.retryConfig.backoffFactor, attempt);
    
    // Add jitter to prevent thundering herd
    const jitter = Math.random() * 0.1 * delay;
    return Math.min(delay + jitter, maxDelay);
  }

  private async executeWithRetry<T>(
    requestFn: () => Promise<T>,
    requestId: string
  ): Promise<T> {
    let lastError: unknown;
    const metrics = this.requestMetrics.get(requestId);

    for (let attempt = 0; attempt <= this.retryConfig.maxRetries; attempt++) {
      try {
        if (metrics) {
          metrics.retryCount = attempt;
        }

        if (attempt > 0) {
          const delay = this.calculateBackoffDelay(attempt - 1);
          console.log(`🔄 Retry attempt ${attempt}/${this.retryConfig.maxRetries} after ${delay}ms`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }

        return await requestFn();
      } catch (error) {
        lastError = error;
        
        // Don't retry if it's not a retryable error
        if (!this.isRetryableError(error as AxiosError)) {
          console.log(`⏭️  Non-retryable error, failing immediately: ${(error as Error).message || 'unknown error'}`);
          break;
        }

        // Don't retry if we're offline
        if (!this.isOnline) {
          console.log('📶 Offline, not retrying');
          break;
        }

        // Don't retry on the last attempt
        if (attempt === this.retryConfig.maxRetries) {
          console.log(`🛑 Max retries (${this.retryConfig.maxRetries}) reached`);
          break;
        }

        console.warn(`⚠️  Attempt ${attempt + 1} failed: ${(error as Error).message || 'unknown error'}`);
      }
    }

    throw lastError;
  }

  private handleError(error: AxiosError | any): ApiError {
    const apiError: ApiError = {
      name: 'ApiError',
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
        if (!this.isOnline) {
          errorMessage = 'You appear to be offline. Please check your internet connection.';
          apiError.code = 'OFFLINE_ERROR';
        } else {
          errorMessage = 'Network error - please check your connection';
          apiError.code = 'NETWORK_ERROR';
        }
        
        apiError.message = errorMessage;
        
        customError = ErrorFactory.createNetworkError(
          undefined,
          { 
            originalError: error,
            method: error.config?.method,
            url: error.config?.url,
            isOffline: !this.isOnline
          }
        );

      } else if (error?.code === 'ECONNABORTED') {
        // Request timeout
        errorMessage = 'Request timeout - the server is taking too long to respond';
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

      // Build comprehensive error context
      const errorContext: Record<string, any> = {
        timestamp: new Date().toISOString(),
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
        isOnline: this.isOnline,
        baseURL: this.baseURL
      };
      
      if (error?.config?.method) errorContext.method = error.config.method;
      if (error?.config?.url) errorContext.url = error.config.url;
      if (error?.response?.status) errorContext.status = error.response.status;
      if (error?.response?.statusText) errorContext.statusText = error.response.statusText;
      if (error?.code) errorContext.errorCode = error.code;
      
      const requestId = error?.config?.metadata?.requestId;
      if (requestId) {
        errorContext.requestId = requestId;
        const metrics = this.requestMetrics.get(requestId);
        if (metrics) {
          errorContext.metrics = metrics;
        }
      }
      
      // Report error to monitoring service
      try {
        errorReporting.reportApiError(customError, 'enhanced-api-service', errorContext);
      } catch (reportingError) {
        console.warn('Failed to report error:', reportingError);
      }

      // Enhanced console logging
      console.error('🚨 Enhanced API Error:', {
        message: apiError.message,
        status: apiError.status,
        code: apiError.code,
        context: errorContext
      });

      return apiError;

    } catch (handlingError) {
      // Fallback error handling
      console.error('💥 Error in error handling:', handlingError);
      
      return {
        name: 'CriticalError',
        message: 'A critical error occurred',
        status: 500,
        code: 'ERROR_HANDLER_FAILED'
      };
    }
  }

  // Enhanced request method with caching, deduplication, and retry logic
  private async enhancedRequest<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
    url: string,
    data?: Record<string, unknown> | FormData,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const cacheKey = this.generateCacheKey(method, url, config?.params, data);
    const requestId = this.generateRequestId();
    
    // Check cache for GET requests
    if (method === 'GET') {
      const cached = apiCache.get<T>(method, url, config?.params);
      if (cached !== null) {
        console.log(`📦 Cache hit for ${method} ${url}`);
        const metrics = this.requestMetrics.get(requestId);
        if (metrics) {
          metrics.cacheHit = true;
          metrics.endTime = Date.now();
          metrics.duration = 0;
        }
        return cached;
      }

      // Check for pending duplicate requests
      const pending = this.pendingRequests.get(cacheKey);
      if (pending) {
        console.log(`🔄 Deduplicating request: ${method} ${url}`);
        return pending as Promise<T>;
      }
    }

    // Create the request function
    const requestFn = async (): Promise<T> => {
      const requestConfig: AxiosRequestConfig = {
        method: method.toLowerCase() as any,
        url,
        data,
        ...config,
      };
      
      // Add metadata separately to avoid TypeScript issues
      (requestConfig as any).metadata = { requestId };

      const response = await this.api.request<T>(requestConfig);
      
      // Cache successful GET responses
      if (method === 'GET') {
        apiCache.set(method, url, response.data, config?.params);
      }
      
      return response.data;
    };

    // Execute request with retry logic
    const requestPromise = this.executeWithRetry(requestFn, requestId);

    // Track pending GET requests for deduplication
    if (method === 'GET') {
      this.pendingRequests.set(cacheKey, requestPromise);
      requestPromise.finally(() => {
        this.pendingRequests.delete(cacheKey);
      });
    }

    try {
      const result = await requestPromise;
      
      // Invalidate related cache entries for mutations
      if (method !== 'GET') {
        this.invalidateRelatedCache(url, method);
      }
      
      return result;
    } finally {
      // Cleanup metrics after some time to prevent memory leaks
      setTimeout(() => {
        this.requestMetrics.delete(requestId);
      }, 300000); // 5 minutes
    }
  }

  private invalidateRelatedCache(url: string, method: string) {
    // Define cache invalidation patterns
    const patterns = [
      { urlPattern: '/api/projects/', invalidates: ['/api/projects', '/api/dashboard'] },
      { urlPattern: '/api/videos/', invalidates: ['/api/projects/', '/api/dashboard'] },
      { urlPattern: '/api/test-sessions/', invalidates: ['/api/dashboard', '/api/projects/'] }
    ];

    patterns.forEach(pattern => {
      if (url.includes(pattern.urlPattern)) {
        pattern.invalidates.forEach(invalidatePattern => {
          apiCache.invalidatePattern(invalidatePattern);
        });
      }
    });
  }

  // Public API methods - Enhanced versions of existing methods

  // Project CRUD
  async getProjects(skip: number = 0, limit: number = 100): Promise<Project[]> {
    return this.enhancedRequest<Project[]>('GET', '/api/projects', undefined, {
      params: { skip, limit }
    });
  }

  async getProject(id: string): Promise<Project> {
    return this.enhancedRequest<Project>('GET', `/api/projects/${id}`);
  }

  async createProject(project: ProjectCreate): Promise<Project> {
    try {
      const result = await this.enhancedRequest<Project>('POST', '/api/projects', project);
      console.log('✅ Project created successfully:', result.id);
      return result;
    } catch (error: unknown) {
      console.error('❌ Project creation failed:', error);
      throw error;
    }
  }

  async updateProject(id: string, updates: ProjectUpdate): Promise<Project> {
    const result = await this.enhancedRequest<Project>('PUT', `/api/projects/${id}`, updates);
    console.log('✅ Project updated successfully:', id);
    return result;
  }

  async deleteProject(id: string): Promise<void> {
    await this.enhancedRequest<void>('DELETE', `/api/projects/${id}`);
    console.log('✅ Project deleted successfully:', id);
  }

  // Video management with enhanced upload tracking
  async getVideos(projectId: string): Promise<VideoFile[]> {
    return this.enhancedRequest<VideoFile[]>('GET', `/api/projects/${projectId}/videos`);
  }

  async uploadVideo(
    projectId: string, 
    file: File, 
    onProgress?: (progress: number) => void
  ): Promise<VideoFile> {
    const formData = new FormData();
    formData.append('file', file);

    console.log(`📤 Starting video upload: ${file.name} (${file.size} bytes)`);

    return this.enhancedRequest<VideoFile>('POST', `/api/projects/${projectId}/videos`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000, // 5 minutes for large files
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          console.log(`📤 Upload progress: ${progress}%`);
          onProgress(progress);
        }
      },
    });
  }

  async getVideo(videoId: string): Promise<VideoFile> {
    return this.enhancedRequest<VideoFile>('GET', `/api/videos/${videoId}`);
  }

  async deleteVideo(videoId: string): Promise<void> {
    await this.enhancedRequest<void>('DELETE', `/api/videos/${videoId}`);
    console.log('✅ Video deleted successfully:', videoId);
  }

  // Ground truth
  async getGroundTruth(videoId: string): Promise<any> {
    return this.enhancedRequest<any>('GET', `/api/videos/${videoId}/ground-truth`);
  }

  // Test sessions
  async getTestSessions(projectId?: string): Promise<TestSession[]> {
    const params = projectId ? { project_id: projectId } : {};
    return this.enhancedRequest<TestSession[]>('GET', '/api/test-sessions', undefined, { params });
  }

  async getTestSession(sessionId: string): Promise<TestSession> {
    return this.enhancedRequest<TestSession>('GET', `/api/test-sessions/${sessionId}`);
  }

  async createTestSession(testSession: TestSessionCreate): Promise<TestSession> {
    return this.enhancedRequest<TestSession>('POST', '/api/test-sessions', testSession);
  }

  async getTestResults(sessionId: string): Promise<any> {
    return this.enhancedRequest<any>('GET', `/api/test-sessions/${sessionId}/results`);
  }

  // Dashboard - Enhanced with real-time capabilities
  async getDashboardStats(): Promise<DashboardStats> {
    return this.enhancedRequest<DashboardStats>('GET', '/api/dashboard/stats');
  }

  async getChartData(): Promise<ChartData> {
    return this.enhancedRequest<ChartData>('GET', '/api/dashboard/charts');
  }

  // Health check with enhanced metrics
  async healthCheck(): Promise<{ status: string; timestamp: string; responseTime: string; version?: string }> {
    const startTime = Date.now();
    const result = await this.enhancedRequest<{ status: string }>('GET', '/health');
    const duration = Date.now() - startTime;
    
    return {
      ...result,
      timestamp: new Date().toISOString(),
      responseTime: `${duration}ms`
    };
  }

  // Utility methods
  getMetrics(requestId?: string) {
    if (requestId) {
      return this.requestMetrics.get(requestId);
    }
    return Array.from(this.requestMetrics.entries()).map(([id, metrics]) => ({
      requestId: id,
      ...metrics
    }));
  }

  clearCache() {
    apiCache.clear();
    console.log('🗑️  API cache cleared');
  }

  getHealthStatus() {
    return {
      isOnline: this.isOnline,
      baseURL: this.baseURL,
      pendingRequests: this.pendingRequests.size,
      cacheSize: 0, // apiCache.size() - needs implementation
      uptime: Date.now() - (this.requestMetrics.values().next().value?.startTime || Date.now())
    };
  }

  // Cleanup method
  destroy() {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
    }
    this.pendingRequests.clear();
    this.requestMetrics.clear();
    this.clearCache();
  }

  // Generic request methods for custom endpoints
  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.enhancedRequest<T>('GET', url, undefined, config);
  }

  async post<T = unknown>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    return this.enhancedRequest<T>('POST', url, data, config);
  }

  async put<T = unknown>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    return this.enhancedRequest<T>('PUT', url, data, config);
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.enhancedRequest<T>('DELETE', url, undefined, config);
  }

  async patch<T = unknown>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    return this.enhancedRequest<T>('PATCH', url, data, config);
  }
}

// Create and export singleton instance
const enhancedApiService = new EnhancedApiService();
export { enhancedApiService };

// Export individual functions for easier imports (properly bound)
export const getProjects = enhancedApiService.getProjects.bind(enhancedApiService);
export const getProject = enhancedApiService.getProject.bind(enhancedApiService);
export const createProject = enhancedApiService.createProject.bind(enhancedApiService);
export const updateProject = enhancedApiService.updateProject.bind(enhancedApiService);
export const deleteProject = enhancedApiService.deleteProject.bind(enhancedApiService);
export const getVideos = enhancedApiService.getVideos.bind(enhancedApiService);
export const uploadVideo = enhancedApiService.uploadVideo.bind(enhancedApiService);
export const getVideo = enhancedApiService.getVideo.bind(enhancedApiService);
export const deleteVideo = enhancedApiService.deleteVideo.bind(enhancedApiService);
export const getGroundTruth = enhancedApiService.getGroundTruth.bind(enhancedApiService);
export const getTestSessions = enhancedApiService.getTestSessions.bind(enhancedApiService);
export const getTestSession = enhancedApiService.getTestSession.bind(enhancedApiService);
export const createTestSession = enhancedApiService.createTestSession.bind(enhancedApiService);
export const getTestResults = enhancedApiService.getTestResults.bind(enhancedApiService);
export const getDashboardStats = enhancedApiService.getDashboardStats.bind(enhancedApiService);
export const getChartData = enhancedApiService.getChartData.bind(enhancedApiService);
export const healthCheck = enhancedApiService.healthCheck.bind(enhancedApiService);

export default enhancedApiService;