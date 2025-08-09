// Simple test to verify API service configuration
import { apiService } from './api';
import { ProjectCreate } from './types';

// Test function that can be used in the browser console
export const testApiService = async () => {
  console.log('Testing API Service...');
  
  try {
    // Test health check (doesn't require auth)
    console.log('1. Testing health check...');
    const health = await apiService.healthCheck();
    console.log('✅ Health check passed:', health);
    
    return true;
  } catch (error) {
    console.error('❌ API Service test failed:', error);
    return false;
  }
};

// Example usage patterns for developers
export const apiExamples = {
  // Project management
  async createProject(projectData: ProjectCreate) {
    return await apiService.createProject(projectData);
  },
  
  async getProjects() {
    return await apiService.getProjects();
  },
  
  // Video upload
  async uploadVideo(projectId: string, file: File, onProgress?: (progress: number) => void) {
    return await apiService.uploadVideo(projectId, file, onProgress);
  },
  
  // Dashboard data
  async getDashboard() {
    const stats = await apiService.getDashboardStats();
    const charts = await apiService.getChartData();
    return { stats, charts };
  }
};

// Add to window for debugging in development
if (process.env.NODE_ENV === 'development') {
  (window as any).apiService = apiService;
  (window as any).testApiService = testApiService;
  (window as any).apiExamples = apiExamples;
}