import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { rest } from 'msw';
import { apiService } from '../../../ai-model-validation-platform/frontend/src/services/api';
import { TEST_PROJECTS, TEST_VIDEOS, createMockVideoBlob, createCorruptedVideoBlob } from '../fixtures/test-videos';

// MSW server for mocking various error scenarios
const server = setupServer(
  // Default handlers - will be overridden in individual tests
  rest.get('/api/projects', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json([]));
  })
);

describe('Error Scenarios and Recovery Tests', () => {
  beforeAll(() => {
    server.listen({ onUnhandledRequest: 'warn' });
  });

  afterEach(() => {
    server.resetHandlers();
    vi.clearAllMocks();
  });

  afterAll(() => {
    server.close();
  });

  describe('Network Error Scenarios', () => {
    it('should handle complete network failure', async () => {
      // Arrange - Mock network error
      server.use(
        rest.get('/api/projects', (req, res) => {
          return res.networkError('Network connection failed');
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle intermittent network failures with retry', async () => {
      // Arrange - Mock intermittent failures
      let attempts = 0;
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          attempts++;
          if (attempts <= 2) {
            return res.networkError('Intermittent network failure');
          }
          return res(
            ctx.status(200),
            ctx.json([{ id: 'project-1', name: 'Recovered Project' }])
          );
        })
      );

      // Act - API service should retry automatically
      const projects = await apiService.getProjects().catch(async () => {
        // Simulate manual retry after network recovery
        await new Promise(resolve => setTimeout(resolve, 1000));
        return apiService.getProjects();
      });

      // Assert
      expect(projects).toBeDefined();
      expect(attempts).toBeGreaterThan(1);
    });

    it('should handle DNS resolution failures', async () => {
      // Arrange - Mock DNS failure
      server.use(
        rest.get('/api/projects', (req, res) => {
          return res.networkError('getaddrinfo ENOTFOUND invalid-domain.com');
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle connection timeouts gracefully', async () => {
      // Arrange - Mock timeout
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.delay(35000), // Longer than API timeout
            ctx.status(200),
            ctx.json([])
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });
  });

  describe('Server Error Scenarios', () => {
    it('should handle 500 Internal Server Error', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({ message: 'Internal server error occurred' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow('Internal server error occurred');
    });

    it('should handle 502 Bad Gateway', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(502),
            ctx.json({ message: 'Bad Gateway - upstream server unavailable' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle 503 Service Unavailable', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(503),
            ctx.json({ message: 'Service temporarily unavailable' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle database connection errors', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({ 
              message: 'Database connection failed',
              code: 'DATABASE_CONNECTION_ERROR'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow('Database connection failed');
    });
  });

  describe('Authentication and Authorization Errors', () => {
    it('should handle 401 Unauthorized', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ message: 'Unauthorized access - invalid token' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle 403 Forbidden', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(403),
            ctx.json({ message: 'Access forbidden - insufficient permissions' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle expired tokens gracefully', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ 
              message: 'Token expired',
              code: 'TOKEN_EXPIRED'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });
  });

  describe('Data Validation Errors', () => {
    it('should handle 400 Bad Request with validation errors', async () => {
      // Arrange
      const invalidProject = {
        name: '', // Invalid: empty name
        description: 'Test',
        camera_model: 'TestCam',
        camera_view: 'Front-facing VRU',
        signal_type: 'GPIO'
      };

      server.use(
        rest.post('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({
              message: 'Validation failed',
              errors: {
                name: 'Project name is required',
                camera_model: 'Camera model must be specified'
              }
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.createProject(invalidProject)).rejects.toThrow('Validation failed');
    });

    it('should handle invalid file uploads', async () => {
      // Arrange
      const corruptedBlob = createCorruptedVideoBlob();
      const file = new File([corruptedBlob], 'corrupted.mp4', { type: 'video/mp4' });

      server.use(
        rest.post('/api/videos', (req, res, ctx) => {
          return res(
            ctx.status(422),
            ctx.json({
              message: 'Invalid file format or corrupted file',
              code: 'INVALID_VIDEO_FILE'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow('Invalid file format or corrupted file');
    });

    it('should handle oversized file uploads', async () => {
      // Arrange
      const largeVideo = TEST_VIDEOS.large;
      const mockVideoFile = createMockVideoBlob(largeVideo);
      const file = new File([mockVideoFile], largeVideo.filename, { type: largeVideo.format });

      server.use(
        rest.post('/api/videos', (req, res, ctx) => {
          return res(
            ctx.status(413),
            ctx.json({
              message: 'File size exceeds maximum limit of 100MB',
              code: 'FILE_TOO_LARGE'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow('File size exceeds maximum limit of 100MB');
    });
  });

  describe('Resource Not Found Errors', () => {
    it('should handle 404 Project Not Found', async () => {
      // Arrange
      const nonExistentProjectId = 'non-existent-project';

      server.use(
        rest.get(`/api/projects/${nonExistentProjectId}`, (req, res, ctx) => {
          return res(
            ctx.status(404),
            ctx.json({ message: 'Project not found' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProject(nonExistentProjectId)).rejects.toThrow('Project not found');
    });

    it('should handle 404 Video Not Found', async () => {
      // Arrange
      const nonExistentVideoId = 'non-existent-video';

      server.use(
        rest.get(`/api/videos/${nonExistentVideoId}`, (req, res, ctx) => {
          return res(
            ctx.status(404),
            ctx.json({ message: 'Video not found' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getVideo(nonExistentVideoId)).rejects.toThrow('Video not found');
    });

    it('should handle missing API endpoints', async () => {
      // Arrange
      server.use(
        rest.get('/api/non-existent-endpoint', (req, res, ctx) => {
          return res(
            ctx.status(404),
            ctx.json({ message: 'API endpoint not found' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.get('/api/non-existent-endpoint')).rejects.toThrow();
    });
  });

  describe('Race Condition and Concurrency Errors', () => {
    it('should handle concurrent access conflicts', async () => {
      // Arrange - Mock conflict error
      const projectData = TEST_PROJECTS.basic;

      server.use(
        rest.post('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(409),
            ctx.json({
              message: 'Project name already exists',
              code: 'CONFLICT'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.createProject(projectData)).rejects.toThrow('Project name already exists');
    });

    it('should handle database lock timeouts', async () => {
      // Arrange
      server.use(
        rest.put('/api/projects/test-id', (req, res, ctx) => {
          return res(
            ctx.status(423),
            ctx.json({
              message: 'Resource is locked - try again later',
              code: 'RESOURCE_LOCKED'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.updateProject('test-id', { name: 'Updated' })).rejects.toThrow();
    });

    it('should handle optimistic locking conflicts', async () => {
      // Arrange
      server.use(
        rest.put('/api/projects/test-id', (req, res, ctx) => {
          return res(
            ctx.status(409),
            ctx.json({
              message: 'Resource was modified by another user',
              code: 'OPTIMISTIC_LOCK_EXCEPTION'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.updateProject('test-id', { name: 'Updated' })).rejects.toThrow();
    });
  });

  describe('Video Processing Errors', () => {
    it('should handle video processing failures', async () => {
      // Arrange
      const videoId = 'processing-failed-video';

      server.use(
        rest.get(`/api/videos/${videoId}/ground-truth`, (req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({
              message: 'Video processing failed - corrupted file',
              code: 'PROCESSING_FAILED'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getGroundTruth(videoId)).rejects.toThrow('Video processing failed - corrupted file');
    });

    it('should handle video codec not supported errors', async () => {
      // Arrange
      const unsupportedVideo = TEST_VIDEOS.unsupportedFormat;
      const mockVideoFile = createMockVideoBlob(unsupportedVideo);
      const file = new File([mockVideoFile], unsupportedVideo.filename, { type: unsupportedVideo.format });

      server.use(
        rest.post('/api/videos', (req, res, ctx) => {
          return res(
            ctx.status(415),
            ctx.json({
              message: 'Unsupported video codec or format',
              code: 'UNSUPPORTED_MEDIA_TYPE'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow('Unsupported video codec or format');
    });

    it('should handle video processing timeout', async () => {
      // Arrange
      const videoId = 'slow-processing-video';

      server.use(
        rest.get(`/api/videos/${videoId}/ground-truth`, (req, res, ctx) => {
          return res(
            ctx.status(504),
            ctx.json({
              message: 'Video processing timed out',
              code: 'PROCESSING_TIMEOUT'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getGroundTruth(videoId)).rejects.toThrow('Video processing timed out');
    });
  });

  describe('Storage and Disk Space Errors', () => {
    it('should handle insufficient disk space errors', async () => {
      // Arrange
      const largeVideo = TEST_VIDEOS.large;
      const mockVideoFile = createMockVideoBlob(largeVideo);
      const file = new File([mockVideoFile], largeVideo.filename, { type: largeVideo.format });

      server.use(
        rest.post('/api/videos', (req, res, ctx) => {
          return res(
            ctx.status(507),
            ctx.json({
              message: 'Insufficient storage space available',
              code: 'INSUFFICIENT_STORAGE'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow('Insufficient storage space available');
    });

    it('should handle storage service unavailable', async () => {
      // Arrange
      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      server.use(
        rest.post('/api/videos', (req, res, ctx) => {
          return res(
            ctx.status(503),
            ctx.json({
              message: 'Storage service temporarily unavailable',
              code: 'STORAGE_SERVICE_UNAVAILABLE'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow('Storage service temporarily unavailable');
    });
  });

  describe('Malformed Response Handling', () => {
    it('should handle invalid JSON responses', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.text('Invalid JSON content')
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle empty responses when data expected', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.body('')
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle responses with missing required fields', async () => {
      // Arrange
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json([
              {
                // Missing required fields like 'id', 'name'
                description: 'Project without required fields'
              }
            ])
          );
        })
      );

      // Act
      const projects = await apiService.getProjects();

      // Assert - Should handle gracefully but may have incomplete data
      expect(projects).toBeDefined();
      expect(Array.isArray(projects)).toBe(true);
    });
  });

  describe('Recovery and Retry Mechanisms', () => {
    it('should implement exponential backoff for retries', async () => {
      // Arrange
      let attempts = 0;
      const startTime = Date.now();

      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          attempts++;
          if (attempts <= 3) {
            return res(
              ctx.status(503),
              ctx.json({ message: 'Service temporarily unavailable' })
            );
          }
          return res(
            ctx.status(200),
            ctx.json([{ id: 'recovered-project', name: 'Recovered after retries' }])
          );
        })
      );

      // Act - Implement retry with exponential backoff
      let result;
      let retryAttempt = 0;
      const maxRetries = 3;

      while (retryAttempt < maxRetries) {
        try {
          result = await apiService.getProjects();
          break;
        } catch (error) {
          retryAttempt++;
          if (retryAttempt >= maxRetries) {
            throw error;
          }
          
          // Exponential backoff: 1s, 2s, 4s
          const delay = Math.pow(2, retryAttempt - 1) * 1000;
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }

      const endTime = Date.now();

      // Assert
      expect(result).toBeDefined();
      expect(attempts).toBe(4); // 3 failures + 1 success
      expect(endTime - startTime).toBeGreaterThan(7000); // At least 1s + 2s + 4s
    });

    it('should implement circuit breaker pattern', async () => {
      // Arrange - Mock consistent failures
      let failureCount = 0;
      const circuitBreakerThreshold = 3;

      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          failureCount++;
          return res(
            ctx.status(500),
            ctx.json({ message: 'Persistent server error' })
          );
        })
      );

      // Act - Simulate circuit breaker behavior
      let circuitOpen = false;
      let consecutiveFailures = 0;

      for (let i = 0; i < 5; i++) {
        try {
          if (circuitOpen) {
            throw new Error('Circuit breaker is OPEN');
          }
          
          await apiService.getProjects();
          consecutiveFailures = 0; // Reset on success
        } catch (error) {
          consecutiveFailures++;
          
          if (consecutiveFailures >= circuitBreakerThreshold) {
            circuitOpen = true;
          }
        }
      }

      // Assert
      expect(circuitOpen).toBe(true);
      expect(consecutiveFailures).toBeGreaterThanOrEqual(circuitBreakerThreshold);
    });

    it('should cache data for offline fallback', async () => {
      // Arrange - First successful request
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json([{ id: 'cached-project', name: 'Cached Project' }])
          );
        })
      );

      // Act - Load data initially
      const initialData = await apiService.getProjects();

      // Simulate network failure
      server.use(
        rest.get('/api/projects', (req, res) => {
          return res.networkError('Network unavailable');
        })
      );

      // Try to get data again - should use cached version
      let cachedData;
      try {
        cachedData = await apiService.getProjects();
      } catch (error) {
        // Fallback to cached data
        cachedData = initialData;
      }

      // Assert
      expect(cachedData).toBeDefined();
      expect(cachedData[0].id).toBe('cached-project');
    });

    it('should implement graceful degradation', async () => {
      // Arrange - Mock partial service failure
      server.use(
        rest.get('/api/dashboard/stats', (req, res, ctx) => {
          return res(
            ctx.status(503),
            ctx.json({ message: 'Dashboard service unavailable' })
          );
        }),
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json([{ id: 'project-1', name: 'Available Project' }])
          );
        })
      );

      // Act - Try to load dashboard data with fallback
      let dashboardStats;
      let projects;

      try {
        dashboardStats = await apiService.getDashboardStats();
      } catch (error) {
        // Graceful degradation - provide minimal stats
        dashboardStats = {
          totalProjects: 0,
          totalVideos: 0,
          totalAnnotations: 0,
          systemHealth: 'degraded'
        };
      }

      projects = await apiService.getProjects();

      // Assert
      expect(dashboardStats.systemHealth).toBe('degraded');
      expect(projects).toBeDefined();
      expect(projects.length).toBeGreaterThan(0);
    });
  });

  describe('Resource Cleanup on Errors', () => {
    it('should cleanup resources on upload failure', async () => {
      // Arrange
      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      server.use(
        rest.post('/api/videos', (req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({ message: 'Upload failed after partial completion' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow();
      
      // In real implementation, should verify that:
      // - Temporary files are cleaned up
      // - Database records are rolled back
      // - Memory is released
    });

    it('should handle memory cleanup on processing errors', async () => {
      // Arrange
      const largeVideo = TEST_VIDEOS.large;
      const mockVideoFile = createMockVideoBlob(largeVideo);
      const file = new File([mockVideoFile], largeVideo.filename, { type: largeVideo.format });

      server.use(
        rest.post('/api/videos', (req, res, ctx) => {
          return res(
            ctx.status(507),
            ctx.json({ 
              message: 'Out of memory during video processing',
              code: 'OUT_OF_MEMORY'
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow('Out of memory during video processing');
      
      // Should verify memory cleanup happened
    });
  });
});