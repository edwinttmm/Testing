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
  User,
  LoginCredentials,
  RegisterData,
  AuthResponse
} from './types';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8001',
      timeout: 10000,
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

      // Handle auth errors
      if (error.response.status === 401) {
        localStorage.removeItem('authToken');
        localStorage.removeItem('user');
        // Redirect to login could be handled here
      }
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

  // Authentication
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await this.api.post<AuthResponse>('/api/auth/login', credentials);
    
    if (response.data.token) {
      localStorage.setItem('authToken', response.data.token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
    }
    
    return response.data;
  }

  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await this.api.post<AuthResponse>('/api/auth/register', data);
    
    if (response.data.token) {
      localStorage.setItem('authToken', response.data.token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
    }
    
    return response.data;
  }

  logout(): void {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
  }

  getCurrentUser(): User | null {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
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
    const response = await this.api.post<Project>('/api/projects', project);
    return response.data;
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

// Export individual functions for easier imports
export const {
  login,
  register,
  logout,
  getCurrentUser,
  getProjects,
  getProject,
  createProject,
  updateProject,
  deleteProject,
  getVideos,
  uploadVideo,
  getVideo,
  deleteVideo,
  getGroundTruth,
  getTestSessions,
  getTestSession,
  createTestSession,
  getTestResults,
  getDashboardStats,
  getChartData,
  healthCheck,
} = apiServiceInstance;

export default apiService;