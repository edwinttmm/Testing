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

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8001',
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

  private handleError(error: AxiosError): ApiError {
    const apiError: ApiError = {
      message: 'An unexpected error occurred',
      status: 500,
    };

    if (error.response) {
      // Server responded with error status
      apiError.status = error.response.status;
      const responseData = error.response.data as any;
      apiError.message = responseData?.message || responseData?.detail || error.message;
      apiError.details = error.response.data;

    } else if (error.request) {
      // Network error
      apiError.message = 'Network error - please check your connection';
      apiError.code = 'NETWORK_ERROR';
    } else {
      // Request setup error
      apiError.message = error.message;
    }

    console.error('API Error:', apiError);
    return apiError;
  }


  // Project CRUD
  async getProjects(skip: number = 0, limit: number = 100): Promise<Project[]> {
    const response = await this.api.get<Project[]>('/api/projects', {
      params: { skip, limit }
    });
    return response.data;
  }

  async getProject(id: string): Promise<Project> {
    const response = await this.api.get<Project>(`/api/projects/${id}`);
    return response.data;
  }

  async createProject(project: ProjectCreate): Promise<Project> {
    console.log('API Service - Creating project with data:', project);
    console.log('API Service - Base URL:', this.api.defaults.baseURL);
    
    // Try fetch first as a fallback
    try {
      console.log('API Service - Trying fetch method first...');
      const baseURL = this.api.defaults.baseURL || 'http://localhost:8001';
      const url = `${baseURL}/api/projects`;
      
      console.log('API Service - Fetch URL:', url);
      console.log('API Service - Fetch payload:', JSON.stringify(project));
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(project)
      });
      
      console.log('API Service - Fetch response status:', response.status);
      console.log('API Service - Fetch response headers:', response.headers);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('API Service - Fetch error response:', errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('API Service - Fetch success result:', result);
      return result;
      
    } catch (fetchError: any) {
      console.error('API Service - Fetch method failed:', fetchError);
      
      // Fallback to axios method
      console.log('API Service - Falling back to axios method...');
      try {
        const response = await this.api.post<Project>('/api/projects', project);
        console.log('API Service - Axios success response:', response.data);
        return response.data;
      } catch (axiosError: any) {
        console.error('API Service - Both fetch and axios failed');
        console.error('API Service - Fetch error:', fetchError);
        console.error('API Service - Axios error:', axiosError);
        console.error('API Service - Axios error details:', {
          message: axiosError.message,
          code: axiosError.code,
          response: axiosError.response,
          request: axiosError.request
        });
        
        // Throw the more descriptive error
        throw axiosError.response ? axiosError : fetchError;
      }
    }
  }

  async updateProject(id: string, updates: ProjectUpdate): Promise<Project> {
    const response = await this.api.put<Project>(`/api/projects/${id}`, updates);
    return response.data;
  }

  async deleteProject(id: string): Promise<void> {
    await this.api.delete(`/api/projects/${id}`);
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
    const response = await this.api.get<DashboardStats>('/api/dashboard/stats');
    return response.data;
  }

  async getChartData(): Promise<ChartData> {
    const response = await this.api.get<ChartData>('/api/dashboard/charts');
    return response.data;
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    const response = await this.api.get<{ status: string }>('/health');
    return response.data;
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