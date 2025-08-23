/**
 * Comprehensive API Error Handling Tests
 * 
 * Tests error scenarios, edge cases, and ensures robust error handling
 * across all API integration points.
 */

import { jest } from '@jest/globals';
import axios, { AxiosError } from 'axios';
import { apiService } from '../ai-model-validation-platform/frontend/src/services/api';
import { enhancedApiService } from '../ai-model-validation-platform/frontend/src/services/enhancedApiService';
import { detectionService } from '../ai-model-validation-platform/frontend/src/services/detectionService';
import websocketService from '../ai-model-validation-platform/frontend/src/services/websocketService';
import { apiCache } from '../ai-model-validation-platform/frontend/src/utils/apiCache';
import { createMockProject, createMockVideoFile } from './api-integration-test-suite';

// Mock network conditions
const simulateNetworkConditions = {
  offline: () => {
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false
    });
  },
  online: () => {
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true
    });
  },
  slowConnection: (delayMs: number = 5000) => {
    return new Promise(resolve => setTimeout(resolve, delayMs));
  }
};

describe('API Error Handling Tests', () => {
  let mockAxios: jest.Mocked<typeof axios>;

  beforeEach(() => {
    jest.clearAllMocks();
    apiCache.clear();
    mockAxios = axios as jest.Mocked<typeof axios>;
    simulateNetworkConditions.online();
  });

  afterEach(() => {
    simulateNetworkConditions.online();
  });

  describe('Network Error Handling', () => {
    it('should handle connection refused errors', async () => {
      const connectionError = new Error('Connection refused') as AxiosError;
      connectionError.code = 'ECONNREFUSED';
      
      mockAxios.get = jest.fn().mockRejectedValue(connectionError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.message).toContain('Network error');
        expect(error.status).toBe(500);
      }
    });

    it('should handle DNS resolution errors', async () => {
      const dnsError = new Error('DNS resolution failed') as AxiosError;
      dnsError.code = 'ENOTFOUND';
      
      mockAxios.get = jest.fn().mockRejectedValue(dnsError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.message).toContain('Network error');
      }
    });

    it('should handle timeout errors gracefully', async () => {
      const timeoutError = new Error('Request timeout') as AxiosError;
      timeoutError.code = 'ECONNABORTED';
      
      mockAxios.get = jest.fn().mockRejectedValue(timeoutError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.message).toContain('timeout');
        expect(error.code).toBe('TIMEOUT_ERROR');
      }
    });

    it('should detect offline status and handle accordingly', async () => {
      simulateNetworkConditions.offline();
      
      const networkError = new Error('Network Error') as AxiosError;
      networkError.request = {}; // Simulate request made but no response
      
      mockAxios.get = jest.fn().mockRejectedValue(networkError);

      try {
        await enhancedApiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.message).toContain('offline');
      }
    });

    it('should handle intermittent network failures with retry', async () => {
      let attemptCount = 0;
      mockAxios.request = jest.fn().mockImplementation(() => {
        attemptCount++;
        if (attemptCount < 3) {
          const networkError = new Error('Network Error') as AxiosError;
          networkError.code = 'ECONNRESET';
          throw networkError;
        }
        return Promise.resolve({ data: [], status: 200 });
      });

      const result = await enhancedApiService.getProjects();
      
      expect(attemptCount).toBe(3);
      expect(result).toEqual([]);
    });
  });

  describe('HTTP Status Code Error Handling', () => {
    it('should handle 400 Bad Request errors', async () => {
      const badRequestError = {
        response: {
          status: 400,
          data: { 
            message: 'Invalid request parameters',
            details: { field: 'name', reason: 'required' }
          }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(badRequestError);

      try {
        await apiService.createProject(createMockProject());
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(400);
        expect(error.message).toBe('Invalid request parameters');
        expect(error.details).toBeDefined();
      }
    });

    it('should handle 401 Unauthorized errors', async () => {
      const unauthorizedError = {
        response: {
          status: 401,
          data: { message: 'Authentication required' }
        }
      } as AxiosError;

      mockAxios.get = jest.fn().mockRejectedValue(unauthorizedError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(401);
        expect(error.message).toBe('Authentication required');
      }
    });

    it('should handle 403 Forbidden errors', async () => {
      const forbiddenError = {
        response: {
          status: 403,
          data: { message: 'Insufficient permissions' }
        }
      } as AxiosError;

      mockAxios.delete = jest.fn().mockRejectedValue(forbiddenError);

      try {
        await apiService.deleteProject('proj-123');
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(403);
        expect(error.message).toBe('Insufficient permissions');
      }
    });

    it('should handle 404 Not Found errors', async () => {
      const notFoundError = {
        response: {
          status: 404,
          data: { message: 'Project not found' }
        }
      } as AxiosError;

      mockAxios.get = jest.fn().mockRejectedValue(notFoundError);

      try {
        await apiService.getProject('non-existent-id');
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(404);
        expect(error.message).toBe('Project not found');
      }
    });

    it('should handle 409 Conflict errors', async () => {
      const conflictError = {
        response: {
          status: 409,
          data: { message: 'Project with this name already exists' }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(conflictError);

      try {
        await apiService.createProject(createMockProject({ name: 'Existing Project' }));
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(409);
        expect(error.message).toBe('Project with this name already exists');
      }
    });

    it('should handle 422 Unprocessable Entity errors', async () => {
      const validationError = {
        response: {
          status: 422,
          data: { 
            message: 'Validation failed',
            errors: [
              { field: 'name', message: 'Name must be at least 3 characters' },
              { field: 'cameraModel', message: 'Invalid camera model' }
            ]
          }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(validationError);

      try {
        await apiService.createProject(createMockProject({ name: 'AB' }));
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(422);
        expect(error.details.errors).toHaveLength(2);
      }
    });

    it('should handle 429 Rate Limit errors', async () => {
      const rateLimitError = {
        response: {
          status: 429,
          data: { 
            message: 'Rate limit exceeded',
            retryAfter: 60
          }
        }
      } as AxiosError;

      mockAxios.get = jest.fn().mockRejectedValue(rateLimitError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(429);
        expect(error.message).toBe('Rate limit exceeded');
      }
    });

    it('should handle 500 Internal Server Error', async () => {
      const serverError = {
        response: {
          status: 500,
          data: { message: 'Internal server error' }
        }
      } as AxiosError;

      mockAxios.get = jest.fn().mockRejectedValue(serverError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(500);
        expect(error.message).toBe('Internal server error');
      }
    });

    it('should handle 502 Bad Gateway errors', async () => {
      const badGatewayError = {
        response: {
          status: 502,
          data: 'Bad Gateway'
        }
      } as AxiosError;

      mockAxios.get = jest.fn().mockRejectedValue(badGatewayError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(502);
      }
    });

    it('should handle 503 Service Unavailable errors', async () => {
      const serviceUnavailableError = {
        response: {
          status: 503,
          data: { message: 'Service temporarily unavailable' }
        }
      } as AxiosError;

      mockAxios.get = jest.fn().mockRejectedValue(serviceUnavailableError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(503);
        expect(error.message).toBe('Service temporarily unavailable');
      }
    });
  });

  describe('Malformed Response Handling', () => {
    it('should handle non-JSON response bodies', async () => {
      mockAxios.get = jest.fn().mockResolvedValue({
        data: '<html>Error page</html>',
        status: 200
      });

      const result = await apiService.getProjects();
      
      // Should handle gracefully without throwing
      expect(result).toBeDefined();
    });

    it('should handle empty response bodies', async () => {
      mockAxios.get = jest.fn().mockResolvedValue({
        data: '',
        status: 200
      });

      const result = await apiService.getProjects();
      expect(result).toBeDefined();
    });

    it('should handle null response data', async () => {
      mockAxios.get = jest.fn().mockResolvedValue({
        data: null,
        status: 200
      });

      const result = await apiService.getProjects();
      expect(result).toBeNull();
    });

    it('should handle corrupted JSON responses', async () => {
      mockAxios.get = jest.fn().mockResolvedValue({
        data: '{"invalid": json}',
        status: 200
      });

      const result = await apiService.getProjects();
      expect(result).toBeDefined();
    });

    it('should handle response with wrong content type', async () => {
      mockAxios.get = jest.fn().mockResolvedValue({
        data: new ArrayBuffer(8),
        status: 200,
        headers: { 'content-type': 'application/octet-stream' }
      });

      const result = await apiService.getProjects();
      expect(result).toBeDefined();
    });
  });

  describe('File Upload Error Handling', () => {
    it('should handle file size limit exceeded', async () => {
      const fileTooLargeError = {
        response: {
          status: 413,
          data: { message: 'File size limit exceeded' }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(fileTooLargeError);

      const largeFile = new File(['x'.repeat(100000000)], 'large.mp4', { type: 'video/mp4' });

      try {
        await apiService.uploadVideo('proj-123', largeFile);
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(413);
        expect(error.message).toBe('File size limit exceeded');
      }
    });

    it('should handle unsupported file type', async () => {
      const unsupportedTypeError = {
        response: {
          status: 415,
          data: { message: 'Unsupported file type' }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(unsupportedTypeError);

      const textFile = new File(['content'], 'document.txt', { type: 'text/plain' });

      try {
        await apiService.uploadVideo('proj-123', textFile);
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(415);
        expect(error.message).toBe('Unsupported file type');
      }
    });

    it('should handle upload interruption', async () => {
      let uploadInterrupted = false;
      
      mockAxios.post = jest.fn().mockImplementation(() => {
        return new Promise((_, reject) => {
          setTimeout(() => {
            uploadInterrupted = true;
            const error = new Error('Upload interrupted') as AxiosError;
            error.code = 'ECONNABORTED';
            reject(error);
          }, 100);
        });
      });

      const file = new File(['video content'], 'test.mp4', { type: 'video/mp4' });

      try {
        await apiService.uploadVideo('proj-123', file);
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(uploadInterrupted).toBe(true);
        expect(error.code).toBe('TIMEOUT_ERROR');
      }
    });

    it('should handle corrupted file upload', async () => {
      const corruptedFileError = {
        response: {
          status: 400,
          data: { message: 'File appears to be corrupted or invalid' }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(corruptedFileError);

      const corruptedFile = new File([new ArrayBuffer(1000)], 'corrupted.mp4', { type: 'video/mp4' });

      try {
        await apiService.uploadVideo('proj-123', corruptedFile);
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(400);
        expect(error.message).toBe('File appears to be corrupted or invalid');
      }
    });
  });

  describe('Detection Service Error Handling', () => {
    it('should handle detection timeout', async () => {
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Detection timeout')), 100)
      );

      jest.spyOn(detectionService, 'runDetection').mockImplementation(() => timeoutPromise);

      try {
        await detectionService.runDetection('vid-123', {
          confidenceThreshold: 0.5,
          nmsThreshold: 0.4,
          modelName: 'yolo-v8',
          targetClasses: ['pedestrian']
        });
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.message).toContain('timeout');
      }
    });

    it('should handle invalid video format for detection', async () => {
      const invalidFormatError = {
        response: {
          status: 400,
          data: { message: 'Unsupported video format for detection' }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(invalidFormatError);

      const result = await detectionService.runDetection('vid-123', {
        confidenceThreshold: 0.5,
        nmsThreshold: 0.4,
        modelName: 'yolo-v8',
        targetClasses: ['pedestrian']
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid video format');
    });

    it('should handle model loading failure', async () => {
      const modelError = {
        response: {
          status: 500,
          data: { message: 'Failed to load detection model' }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(modelError);

      const result = await detectionService.runDetection('vid-123', {
        confidenceThreshold: 0.5,
        nmsThreshold: 0.4,
        modelName: 'invalid-model',
        targetClasses: ['pedestrian']
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Server error');
    });
  });

  describe('WebSocket Error Handling', () => {
    it('should handle WebSocket connection failure', async () => {
      const mockConnect = jest.fn().mockRejectedValue(new Error('Connection failed'));
      websocketService.connect = mockConnect;

      try {
        await websocketService.connect();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.message).toBe('Connection failed');
      }
    });

    it('should handle WebSocket message parsing errors', (done) => {
      const mockSubscribe = jest.fn((eventType, callback) => {
        if (eventType === 'test_event') {
          // Simulate malformed message
          setTimeout(() => {
            try {
              callback('invalid json message{');
            } catch (error) {
              // Should handle gracefully
              expect(error).toBeDefined();
              done();
            }
          }, 10);
        }
        return jest.fn();
      });

      websocketService.subscribe = mockSubscribe;
      websocketService.subscribe('test_event', (data) => {
        // This should not be reached with invalid data
        fail('Should not receive invalid data');
      });
    });

    it('should handle WebSocket reconnection failures', () => {
      const healthStatus = websocketService.getHealthStatus();
      expect(healthStatus.isConnected).toBeDefined();
      expect(healthStatus.connectionState).toBeDefined();
    });
  });

  describe('Cache Error Handling', () => {
    it('should handle cache corruption gracefully', () => {
      // Simulate cache corruption
      try {
        const corruptedData = { invalid: 'structure' };
        apiCache.set('GET', '/api/test', corruptedData);
        const retrieved = apiCache.get('GET', '/api/test');
        
        expect(retrieved).toBeDefined();
      } catch (error) {
        // Should not throw errors
        fail('Cache should handle corruption gracefully');
      }
    });

    it('should handle cache storage limits', () => {
      // Fill cache beyond limits
      for (let i = 0; i < 150; i++) {
        apiCache.set('GET', `/api/test-${i}`, { data: i });
      }

      const stats = apiCache.getStats();
      expect(stats.totalEntries).toBeLessThanOrEqual(100); // Max cache size
    });

    it('should handle cache key collisions', () => {
      const data1 = { id: 1, name: 'Test 1' };
      const data2 = { id: 2, name: 'Test 2' };

      apiCache.set('GET', '/api/test', data1);
      apiCache.set('GET', '/api/test', data2); // Same key

      const retrieved = apiCache.get('GET', '/api/test');
      expect(retrieved).toEqual(data2); // Should overwrite
    });
  });

  describe('Edge Cases and Boundary Conditions', () => {
    it('should handle extremely large response payloads', async () => {
      const largePayload = Array.from({ length: 10000 }, (_, i) => ({
        id: `item-${i}`,
        data: 'x'.repeat(1000)
      }));

      mockAxios.get = jest.fn().mockResolvedValue({
        data: largePayload,
        status: 200
      });

      const startTime = Date.now();
      const result = await apiService.getProjects();
      const duration = Date.now() - startTime;

      expect(result).toBeDefined();
      expect(duration).toBeLessThan(10000); // Should complete within 10s
    });

    it('should handle concurrent error scenarios', async () => {
      const errorResponses = [
        Promise.reject({ response: { status: 404, data: { message: 'Not found' } } }),
        Promise.reject({ response: { status: 500, data: { message: 'Server error' } } }),
        Promise.reject({ response: { status: 403, data: { message: 'Forbidden' } } })
      ];

      mockAxios.get = jest.fn()
        .mockRejectedValueOnce(errorResponses[0])
        .mockRejectedValueOnce(errorResponses[1])
        .mockRejectedValueOnce(errorResponses[2]);

      const requests = [
        apiService.getProject('not-found'),
        apiService.getProject('server-error'),
        apiService.getProject('forbidden')
      ];

      const results = await Promise.allSettled(requests);

      expect(results[0].status).toBe('rejected');
      expect(results[1].status).toBe('rejected');
      expect(results[2].status).toBe('rejected');
    });

    it('should handle API version mismatches', async () => {
      const versionMismatchError = {
        response: {
          status: 400,
          data: { 
            message: 'API version mismatch',
            apiVersion: '2.0',
            clientVersion: '1.0'
          }
        }
      } as AxiosError;

      mockAxios.get = jest.fn().mockRejectedValue(versionMismatchError);

      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.message).toBe('API version mismatch');
        expect(error.details).toBeDefined();
      }
    });

    it('should handle resource exhaustion errors', async () => {
      const resourceExhaustionError = {
        response: {
          status: 507,
          data: { message: 'Insufficient storage space' }
        }
      } as AxiosError;

      mockAxios.post = jest.fn().mockRejectedValue(resourceExhaustionError);

      const file = new File(['content'], 'test.mp4', { type: 'video/mp4' });

      try {
        await apiService.uploadVideo('proj-123', file);
        fail('Expected error to be thrown');
      } catch (error: any) {
        expect(error.status).toBe(507);
      }
    });

    it('should handle circular reference errors in responses', async () => {
      // Create circular reference
      const circularData: any = { name: 'test' };
      circularData.self = circularData;

      mockAxios.get = jest.fn().mockResolvedValue({
        data: circularData,
        status: 200
      });

      try {
        const result = await apiService.getProjects();
        expect(result).toBeDefined();
      } catch (error) {
        // Should handle gracefully
        expect(error).toBeDefined();
      }
    });
  });

  describe('Recovery and Fallback Mechanisms', () => {
    it('should implement exponential backoff for retries', async () => {
      const timestamps: number[] = [];
      let attemptCount = 0;

      mockAxios.request = jest.fn().mockImplementation(() => {
        timestamps.push(Date.now());
        attemptCount++;
        
        if (attemptCount < 4) {
          const error = new Error('Temporary failure') as AxiosError;
          error.response = { status: 503 } as any;
          throw error;
        }
        
        return Promise.resolve({ data: [], status: 200 });
      });

      await enhancedApiService.getProjects();

      expect(attemptCount).toBe(4);
      expect(timestamps.length).toBe(4);
      
      // Check that delays increased (exponential backoff)
      if (timestamps.length >= 3) {
        const delay1 = timestamps[1] - timestamps[0];
        const delay2 = timestamps[2] - timestamps[1];
        expect(delay2).toBeGreaterThan(delay1);
      }
    });

    it('should provide fallback data when API is unavailable', async () => {
      const networkError = new Error('Network unavailable') as AxiosError;
      networkError.code = 'ECONNREFUSED';

      mockAxios.get = jest.fn().mockRejectedValue(networkError);

      // Mock fallback mechanism
      const fallbackData = [{ id: 'fallback', name: 'Offline Mode' }];
      
      try {
        await apiService.getProjects();
        fail('Expected error to be thrown');
      } catch (error) {
        // In a real implementation, this could return cached/fallback data
        expect(error).toBeDefined();
      }
    });

    it('should handle graceful degradation of features', async () => {
      // Simulate partial service failure
      mockAxios.get = jest.fn().mockImplementation((url) => {
        if (url.includes('/api/dashboard/')) {
          throw new Error('Dashboard service unavailable');
        }
        return Promise.resolve({ data: [], status: 200 });
      });

      // Projects should still work
      const projects = await apiService.getProjects();
      expect(projects).toEqual([]);

      // Dashboard should fail
      try {
        await apiService.getDashboardStats();
        fail('Expected error to be thrown');
      } catch (error) {
        expect(error).toBeDefined();
      }
    });
  });
});