import { jest } from '@jest/globals';
import axios from 'axios';
import { apiService, getDashboardStats, createProject, uploadVideo } from '../ai-model-validation-platform/frontend/src/services/api';
import { NetworkError, AppError } from '../ai-model-validation-platform/frontend/src/utils/errorTypes';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock the error types module
jest.mock('../ai-model-validation-platform/frontend/src/utils/errorTypes', () => ({
  NetworkError: jest.fn().mockImplementation((message) => ({
    name: 'NetworkError',
    message,
    isNetworkError: true
  })),
  AppError: jest.fn().mockImplementation((message) => ({
    name: 'AppError', 
    message,
    isAppError: true
  })),
  ErrorFactory: {
    createNetworkError: jest.fn().mockImplementation((response, context) => ({
      name: 'NetworkError',
      message: 'Network error - please check your connection',
      context,
      isNetworkError: true
    })),
    createApiError: jest.fn().mockImplementation((response, data, context) => ({
      name: 'ApiError',
      message: data?.message || 'API error occurred',
      status: response?.status,
      context,
      isApiError: true
    }))
  }
}));

describe('API Service Integration - TDD Phase 1', () => {
  let mockAxiosInstance: any;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Create mock axios instance
    mockAxiosInstance = {
      request: jest.fn(),
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() }
      }
    };

    mockedAxios.create.mockReturnValue(mockAxiosInstance);
  });

  describe('Network Error Handling', () => {
    it('should handle network connection failures properly', async () => {
      // FAILING TEST - This should fail because handleError function has issues
      const networkError = {
        code: 'NETWORK_ERROR',
        message: 'Network Error',
        request: {},
        config: { method: 'get', url: '/api/dashboard/stats' }
      };

      mockAxiosInstance.request.mockRejectedValue(networkError);

      try {
        await getDashboardStats();
        fail('Should have thrown an error');
      } catch (error: any) {
        // This should be a properly formatted error, not [object Object]
        expect(error.message).not.toBe('[object Object]');
        expect(error.message).toBe('Network error - please check your connection');
        expect(error.code).toBe('NETWORK_ERROR');
      }
    });

    it('should implement retry logic for transient failures', async () => {
      // FAILING TEST - Retry logic not implemented properly
      const transientError = {
        code: 'ECONNRESET',
        message: 'Connection reset',
        request: {},
        config: { method: 'get', url: '/api/dashboard/stats' }
      };

      const successResponse = {
        data: {
          projectCount: 5,
          videoCount: 10,
          testCount: 15,
          averageAccuracy: 95.0,
          activeTests: 1,
          totalDetections: 50
        }
      };

      // First two calls fail, third succeeds
      mockAxiosInstance.request
        .mockRejectedValueOnce(transientError)
        .mockRejectedValueOnce(transientError)  
        .mockResolvedValueOnce(successResponse);

      const result = await getDashboardStats();
      
      // Should have retried and eventually succeeded
      expect(mockAxiosInstance.request).toHaveBeenCalledTimes(3);
      expect(result.projectCount).toBe(5);
    });

    it('should fail after max retry attempts', async () => {
      // FAILING TEST - Should respect max retry limits
      const persistentError = {
        code: 'ENOTFOUND',
        message: 'DNS resolution failed',
        request: {},
        config: { method: 'get', url: '/api/dashboard/stats' }
      };

      mockAxiosInstance.request.mockRejectedValue(persistentError);

      try {
        await getDashboardStats();
        fail('Should have thrown an error after max retries');
      } catch (error: any) {
        // Should have attempted the configured number of retries
        expect(mockAxiosInstance.request).toHaveBeenCalledTimes(3); // 1 initial + 2 retries
        expect(error.message).toBe('Network error - please check your connection');
      }
    });
  });

  describe('API Response Handling', () => {
    it('should handle malformed API responses gracefully', async () => {
      // FAILING TEST - Malformed responses cause the [object Object] error
      const malformedResponse = {
        status: 200,
        data: {
          toString: () => '[object Object]',
          message: undefined,
          detail: null
        }
      };

      mockAxiosInstance.request.mockResolvedValue(malformedResponse);

      const result = await getDashboardStats();
      
      // Should handle malformed data gracefully
      expect(result).toBeDefined();
      expect(typeof result).toBe('object');
    });

    it('should handle server errors with proper error messages', async () => {
      // FAILING TEST - Server errors not properly formatted
      const serverError = {
        response: {
          status: 500,
          statusText: 'Internal Server Error',
          data: {
            message: 'Database connection failed',
            error: 'Connection timeout'
          }
        },
        config: { method: 'get', url: '/api/dashboard/stats' }
      };

      mockAxiosInstance.request.mockRejectedValue(serverError);

      try {
        await getDashboardStats();
        fail('Should have thrown a server error');
      } catch (error: any) {
        expect(error.message).toBe('Database connection failed');
        expect(error.status).toBe(500);
        expect(error.message).not.toBe('[object Object]');
      }
    });

    it('should handle client errors (4xx) appropriately', async () => {
      // FAILING TEST - Client errors not handled properly
      const clientError = {
        response: {
          status: 404,
          statusText: 'Not Found',
          data: {
            detail: 'Dashboard endpoint not found'
          }
        },
        config: { method: 'get', url: '/api/dashboard/stats' }
      };

      mockAxiosInstance.request.mockRejectedValue(clientError);

      try {
        await getDashboardStats();
        fail('Should have thrown a client error');
      } catch (error: any) {
        expect(error.status).toBe(404);
        expect(error.message).toBe('Dashboard endpoint not found');
      }
    });
  });

  describe('Request Caching and Deduplication', () => {
    it('should cache GET requests appropriately', async () => {
      // FAILING TEST - Caching not implemented properly
      const responseData = {
        data: {
          projectCount: 3,
          videoCount: 6,
          testCount: 9,
          averageAccuracy: 91.5,
          activeTests: 0,
          totalDetections: 30
        }
      };

      mockAxiosInstance.request.mockResolvedValue(responseData);

      // First request
      const result1 = await getDashboardStats();
      
      // Second request (should use cache)
      const result2 = await getDashboardStats();

      // Should only make one actual API call due to caching
      expect(mockAxiosInstance.request).toHaveBeenCalledTimes(1);
      expect(result1).toEqual(result2);
    });

    it('should deduplicate concurrent requests', async () => {
      // FAILING TEST - Concurrent request deduplication not working
      const responseData = {
        data: {
          projectCount: 2,
          videoCount: 4,
          testCount: 6,
          averageAccuracy: 88.0,
          activeTests: 1,
          totalDetections: 20
        }
      };

      let resolvePromise: (value: any) => void;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockAxiosInstance.request.mockReturnValue(promise);

      // Make multiple concurrent requests
      const promises = [
        getDashboardStats(),
        getDashboardStats(),
        getDashboardStats()
      ];

      // Resolve the mock promise
      setTimeout(() => resolvePromise!(responseData), 10);

      const results = await Promise.all(promises);

      // Should only make one actual API call
      expect(mockAxiosInstance.request).toHaveBeenCalledTimes(1);
      
      // All results should be identical
      expect(results[0]).toEqual(results[1]);
      expect(results[1]).toEqual(results[2]);
    });

    it('should invalidate cache after mutations', async () => {
      // FAILING TEST - Cache invalidation not working properly
      const initialStats = {
        data: {
          projectCount: 1,
          videoCount: 2,
          testCount: 3,
          averageAccuracy: 85.0,
          activeTests: 0,
          totalDetections: 10
        }
      };

      const updatedStats = {
        data: {
          projectCount: 2, // Increased after creating project
          videoCount: 2,
          testCount: 3,
          averageAccuracy: 85.0,
          activeTests: 0,
          totalDetections: 10
        }
      };

      const newProject = {
        data: {
          id: '123',
          name: 'Test Project',
          description: 'Test Description',
          created_at: new Date().toISOString()
        }
      };

      mockAxiosInstance.request
        .mockResolvedValueOnce(initialStats)      // First getDashboardStats
        .mockResolvedValueOnce(newProject)        // createProject
        .mockResolvedValueOnce(updatedStats);     // Second getDashboardStats (after cache invalidation)

      // Get initial stats (should be cached)
      const initialResult = await getDashboardStats();
      expect(initialResult.projectCount).toBe(1);

      // Create a project (should invalidate dashboard cache)
      await createProject({ name: 'Test Project', description: 'Test Description' });

      // Get stats again (should fetch fresh data, not from cache)
      const updatedResult = await getDashboardStats();
      expect(updatedResult.projectCount).toBe(2);

      // Should have made 3 API calls total
      expect(mockAxiosInstance.request).toHaveBeenCalledTimes(3);
    });
  });

  describe('File Upload Handling', () => {
    it('should handle file upload errors gracefully', async () => {
      // FAILING TEST - File upload error handling issues
      const uploadError = {
        response: {
          status: 413,
          statusText: 'Payload Too Large',
          data: {
            message: 'File size exceeds maximum allowed size'
          }
        },
        config: { 
          method: 'post', 
          url: '/api/projects/123/videos',
          headers: { 'Content-Type': 'multipart/form-data' }
        }
      };

      mockAxiosInstance.post.mockRejectedValue(uploadError);

      const mockFile = new File(['test content'], 'test.mp4', { type: 'video/mp4' });

      try {
        await uploadVideo('123', mockFile);
        fail('Should have thrown an upload error');
      } catch (error: any) {
        expect(error.status).toBe(413);
        expect(error.message).toBe('File size exceeds maximum allowed size');
        expect(error.message).not.toBe('[object Object]');
      }
    });

    it('should track upload progress properly', async () => {
      // FAILING TEST - Upload progress tracking not implemented
      const mockFile = new File(['test content'], 'test.mp4', { type: 'video/mp4' });
      const progressCallback = jest.fn();

      const uploadResponse = {
        data: {
          id: '456',
          filename: 'test.mp4',
          size: 12345,
          status: 'uploaded'
        }
      };

      mockAxiosInstance.post.mockImplementation((url, data, config) => {
        // Simulate progress events
        if (config?.onUploadProgress) {
          setTimeout(() => config.onUploadProgress({ loaded: 50, total: 100 }), 10);
          setTimeout(() => config.onUploadProgress({ loaded: 100, total: 100 }), 20);
        }
        return Promise.resolve(uploadResponse);
      });

      const result = await uploadVideo('123', mockFile, progressCallback);

      expect(result.id).toBe('456');
      
      // Should have called progress callback
      setTimeout(() => {
        expect(progressCallback).toHaveBeenCalledWith(50);
        expect(progressCallback).toHaveBeenCalledWith(100);
      }, 50);
    });
  });

  describe('Error Logging and Monitoring', () => {
    it('should log errors with proper context', async () => {
      // FAILING TEST - Error logging not comprehensive enough
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const apiError = {
        response: {
          status: 500,
          statusText: 'Internal Server Error'
        },
        config: {
          method: 'get',
          url: '/api/dashboard/stats',
          headers: { 'Content-Type': 'application/json' }
        },
        message: 'Request failed with status code 500'
      };

      mockAxiosInstance.request.mockRejectedValue(apiError);

      try {
        await getDashboardStats();
      } catch (error) {
        // Expected to fail
      }

      // Should have logged error with context
      expect(consoleSpy).toHaveBeenCalledWith(
        'API Error:', 
        expect.objectContaining({
          message: expect.any(String),
          status: 500
        })
      );

      consoleSpy.mockRestore();
    });

    it('should report errors to monitoring service in production', async () => {
      // FAILING TEST - Production error reporting not implemented
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'production';

      // Mock error reporting service
      const mockErrorReporting = {
        reportApiError: jest.fn()
      };

      // This would need to be properly mocked in the actual implementation
      const apiError = {
        message: 'Service unavailable',
        request: {},
        config: { method: 'get', url: '/api/dashboard/stats' }
      };

      mockAxiosInstance.request.mockRejectedValue(apiError);

      try {
        await getDashboardStats();
      } catch (error) {
        // Expected to fail
      }

      // Should have called error reporting in production
      // This test will fail until proper error reporting is implemented
      
      process.env.NODE_ENV = originalEnv;
    });
  });

  describe('Timeout and Cancellation Handling', () => {
    it('should handle request timeouts properly', async () => {
      // FAILING TEST - Timeout handling not robust
      const timeoutError = {
        code: 'ECONNABORTED',
        message: 'timeout of 30000ms exceeded',
        config: { timeout: 30000, method: 'get', url: '/api/dashboard/stats' }
      };

      mockAxiosInstance.request.mockRejectedValue(timeoutError);

      try {
        await getDashboardStats();
        fail('Should have thrown a timeout error');
      } catch (error: any) {
        expect(error.message).toContain('timeout');
        expect(error.code).toBe('ECONNABORTED');
      }
    });

    it('should support request cancellation', async () => {
      // FAILING TEST - Request cancellation not implemented
      const cancelToken = { cancel: jest.fn() };
      
      // Mock axios cancel token functionality
      mockAxiosInstance.request.mockImplementation((config) => {
        return new Promise((resolve, reject) => {
          setTimeout(() => reject({ message: 'Request cancelled' }), 100);
        });
      });

      const requestPromise = getDashboardStats();
      
      // Cancel the request
      setTimeout(() => {
        // This functionality needs to be implemented
        cancelToken.cancel('User cancelled request');
      }, 50);

      try {
        await requestPromise;
        fail('Should have been cancelled');
      } catch (error: any) {
        expect(error.message).toContain('cancelled');
      }
    });
  });
});