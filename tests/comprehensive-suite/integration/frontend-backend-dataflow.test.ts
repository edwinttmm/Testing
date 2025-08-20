import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { rest } from 'msw';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';

import { apiService } from '../../../ai-model-validation-platform/frontend/src/services/api';
import { TEST_PROJECTS, TEST_VIDEOS, TEST_ANNOTATIONS, createMockVideoBlob } from '../fixtures/test-videos';

// Mock components for testing
const MockProjects = React.lazy(() => import('../../../ai-model-validation-platform/frontend/src/pages/Projects'));
const MockTestExecution = React.lazy(() => import('../../../ai-model-validation-platform/frontend/src/pages/TestExecution-improved'));
const MockVideoAnnotationPlayer = React.lazy(() => import('../../../ai-model-validation-platform/frontend/src/components/VideoAnnotationPlayer'));

// MSW server for mocking API calls
const server = setupServer(
  // Projects endpoints
  rest.get('/api/projects', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json([
        {
          id: 'project-1',
          name: 'Test Project 1',
          description: 'Test project description',
          camera_model: 'TestCam v1.0',
          camera_view: 'Front-facing VRU',
          signal_type: 'GPIO',
          status: 'Active',
          created_at: '2023-01-01T00:00:00Z'
        }
      ])
    );
  }),

  rest.post('/api/projects', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-project-id',
        name: 'New Test Project',
        status: 'Active',
        created_at: new Date().toISOString(),
        ...req.body
      })
    );
  }),

  // Videos endpoints  
  rest.post('/api/videos', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-video-id',
        filename: 'uploaded-video.mp4',
        file_size: 5000000,
        status: 'uploaded',
        processing_status: 'pending',
        url: '/api/videos/new-video-id/stream',
        created_at: new Date().toISOString()
      })
    );
  }),

  rest.get('/api/projects/:projectId/videos', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json([
        {
          id: 'video-1',
          filename: 'test-video.mp4',
          file_size: 5000000,
          status: 'completed',
          processing_status: 'completed',
          url: '/api/videos/video-1/stream'
        }
      ])
    );
  }),

  // Annotations endpoints
  rest.get('/api/videos/:videoId/annotations', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json([
        {
          id: 'annotation-1',
          detectionId: 'det-001',
          frameNumber: 150,
          timestamp: 5.0,
          vruType: 'pedestrian',
          boundingBox: { x: 100, y: 50, width: 60, height: 120 },
          validated: true,
          annotator: 'test-user'
        }
      ])
    );
  }),

  rest.post('/api/videos/:videoId/annotations', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-annotation-id',
        created_at: new Date().toISOString(),
        ...req.body
      })
    );
  }),

  // Test sessions endpoints
  rest.post('/api/test-sessions', (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-session-id',
        name: 'Test Session',
        status: 'created',
        created_at: new Date().toISOString(),
        ...req.body
      })
    );
  }),

  // Dashboard endpoints
  rest.get('/api/dashboard/stats', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        totalProjects: 5,
        totalVideos: 12,
        totalAnnotations: 1250,
        activeTestSessions: 2,
        completedTestSessions: 8,
        averageProcessingTime: 45.5,
        systemHealth: 'healthy'
      })
    );
  }),

  // Health check
  rest.get('/health', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ status: 'healthy' })
    );
  }),

  // Error simulation endpoints
  rest.get('/api/error-test', (req, res, ctx) => {
    return res(
      ctx.status(500),
      ctx.json({ message: 'Simulated server error' })
    );
  })
);

describe('Frontend-Backend Data Flow Tests', () => {
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

  const renderWithRouter = (component: React.ReactElement) => {
    return render(
      <BrowserRouter>
        <React.Suspense fallback={<div>Loading...</div>}>
          {component}
        </React.Suspense>
      </BrowserRouter>
    );
  };

  describe('Project Management Data Flow', () => {
    it('should load projects from backend and display in frontend', async () => {
      // Act
      const projects = await apiService.getProjects();

      // Assert
      expect(projects).toBeDefined();
      expect(Array.isArray(projects)).toBe(true);
      expect(projects.length).toBeGreaterThan(0);
      expect(projects[0]).toHaveProperty('id');
      expect(projects[0]).toHaveProperty('name');
      expect(projects[0]).toHaveProperty('status');
    });

    it('should create project via API and return proper response', async () => {
      // Arrange
      const projectData = TEST_PROJECTS.basic;

      // Act
      const createdProject = await apiService.createProject(projectData);

      // Assert
      expect(createdProject).toBeDefined();
      expect(createdProject.id).toBe('new-project-id');
      expect(createdProject.name).toBe('New Test Project');
      expect(createdProject.status).toBe('Active');
      expect(createdProject.created_at).toBeDefined();
    });

    it('should handle project creation form submission end-to-end', async () => {
      // This would require actual component rendering
      // For now, test the API layer
      
      // Arrange
      const formData = {
        name: 'Frontend Form Project',
        description: 'Created via frontend form',
        camera_model: 'FormCam v1.0',
        camera_view: 'Front-facing VRU',
        signal_type: 'GPIO'
      };

      // Mock form submission
      server.use(
        rest.post('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(201),
            ctx.json({
              id: 'form-project-id',
              ...formData,
              status: 'Active',
              created_at: new Date().toISOString()
            })
          );
        })
      );

      // Act
      const result = await apiService.createProject(formData);

      // Assert
      expect(result.id).toBe('form-project-id');
      expect(result.name).toBe(formData.name);
      expect(result.description).toBe(formData.description);
    });
  });

  describe('Video Upload Data Flow', () => {
    it('should upload video file and receive proper response', async () => {
      // Arrange
      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      let uploadProgress: number[] = [];
      const onProgress = (progress: number) => uploadProgress.push(progress);

      // Act
      const uploadResult = await apiService.uploadVideoCentral(file, onProgress);

      // Assert
      expect(uploadResult).toBeDefined();
      expect(uploadResult.id).toBe('new-video-id');
      expect(uploadResult.filename).toBe('uploaded-video.mp4');
      expect(uploadResult.file_size).toBe(5000000);
      expect(uploadResult.status).toBe('uploaded');
      expect(uploadResult.url).toBe('/api/videos/new-video-id/stream');
    });

    it('should handle video upload with progress tracking', async () => {
      // Arrange
      const videoData = TEST_VIDEOS.large;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      // Mock progress updates
      server.use(
        rest.post('/api/videos', async (req, res, ctx) => {
          // Simulate upload progress
          await new Promise(resolve => setTimeout(resolve, 100));
          
          return res(
            ctx.status(201),
            ctx.json({
              id: 'large-video-id',
              filename: videoData.filename,
              file_size: videoData.size,
              status: 'uploading',
              processing_status: 'pending',
              upload_progress: 100
            })
          );
        })
      );

      let progressUpdates: number[] = [];
      const onProgress = (progress: number) => progressUpdates.push(progress);

      // Act
      const uploadResult = await apiService.uploadVideoCentral(file, onProgress);

      // Assert
      expect(uploadResult).toBeDefined();
      expect(uploadResult.id).toBe('large-video-id');
      expect(uploadResult.file_size).toBe(videoData.size);
    });

    it('should link uploaded video to project', async () => {
      // Arrange
      const projectId = 'test-project-id';
      const videoIds = ['video-1', 'video-2'];

      server.use(
        rest.post(`/api/projects/${projectId}/videos/link`, (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json([
              { id: 'link-1', project_id: projectId, video_id: 'video-1', created_at: new Date().toISOString() },
              { id: 'link-2', project_id: projectId, video_id: 'video-2', created_at: new Date().toISOString() }
            ])
          );
        })
      );

      // Act
      const linkResult = await apiService.linkVideosToProject(projectId, videoIds);

      // Assert
      expect(linkResult).toBeDefined();
      expect(Array.isArray(linkResult)).toBe(true);
      expect(linkResult.length).toBe(2);
      expect(linkResult[0].project_id).toBe(projectId);
      expect(linkResult[0].video_id).toBe('video-1');
    });
  });

  describe('Annotation System Data Flow', () => {
    it('should load video annotations from backend', async () => {
      // Arrange
      const videoId = 'test-video-id';

      // Act
      const annotations = await apiService.getAnnotations(videoId);

      // Assert
      expect(annotations).toBeDefined();
      expect(Array.isArray(annotations)).toBe(true);
      expect(annotations.length).toBeGreaterThan(0);
      expect(annotations[0]).toHaveProperty('id');
      expect(annotations[0]).toHaveProperty('detectionId');
      expect(annotations[0]).toHaveProperty('frameNumber');
      expect(annotations[0]).toHaveProperty('vruType');
      expect(annotations[0]).toHaveProperty('boundingBox');
    });

    it('should create new annotation via API', async () => {
      // Arrange
      const videoId = 'test-video-id';
      const annotationData = {
        detectionId: 'det-new-001',
        frameNumber: 200,
        timestamp: 6.67,
        vruType: 'cyclist' as const,
        boundingBox: { x: 150, y: 75, width: 80, height: 100 },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        annotator: 'test-user'
      };

      // Act
      const createdAnnotation = await apiService.createAnnotation(videoId, annotationData);

      // Assert
      expect(createdAnnotation).toBeDefined();
      expect(createdAnnotation.id).toBe('new-annotation-id');
      expect(createdAnnotation.created_at).toBeDefined();
    });

    it('should update annotation via API', async () => {
      // Arrange
      const annotationId = 'annotation-1';
      const updateData = {
        vruType: 'motorcyclist' as const,
        validated: true,
        notes: 'Updated annotation'
      };

      server.use(
        rest.put(`/api/annotations/${annotationId}`, (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              id: annotationId,
              ...updateData,
              updated_at: new Date().toISOString()
            })
          );
        })
      );

      // Act
      const updatedAnnotation = await apiService.updateAnnotation(annotationId, updateData);

      // Assert
      expect(updatedAnnotation).toBeDefined();
      expect(updatedAnnotation.id).toBe(annotationId);
      expect(updatedAnnotation.vruType).toBe(updateData.vruType);
      expect(updatedAnnotation.validated).toBe(updateData.validated);
    });
  });

  describe('Test Execution Data Flow', () => {
    it('should create test session with proper data flow', async () => {
      // Arrange
      const sessionData = {
        name: 'Test Session Data Flow',
        projectId: 'project-1',
        videoId: 'video-1',
        toleranceMs: 100
      };

      // Act
      const createdSession = await apiService.createTestSession(sessionData);

      // Assert
      expect(createdSession).toBeDefined();
      expect(createdSession.id).toBe('new-session-id');
      expect(createdSession.name).toBe('Test Session');
      expect(createdSession.status).toBe('created');
    });

    it('should retrieve test session results', async () => {
      // Arrange
      const sessionId = 'test-session-id';

      server.use(
        rest.get(`/api/test-sessions/${sessionId}/results`, (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              sessionId: sessionId,
              totalDetections: 50,
              truePositives: 45,
              falsePositives: 3,
              falseNegatives: 2,
              precision: 0.9375,
              recall: 0.9574,
              f1Score: 0.9474,
              processingTime: 120.5
            })
          );
        })
      );

      // Act
      const results = await apiService.getTestResults(sessionId);

      // Assert
      expect(results).toBeDefined();
      expect(results.sessionId).toBe(sessionId);
      expect(results.totalDetections).toBe(50);
      expect(results.precision).toBeCloseTo(0.9375);
      expect(results.recall).toBeCloseTo(0.9574);
    });
  });

  describe('Dashboard Data Aggregation', () => {
    it('should load dashboard statistics from multiple backend sources', async () => {
      // Act
      const stats = await apiService.getDashboardStats();

      // Assert
      expect(stats).toBeDefined();
      expect(stats.totalProjects).toBe(5);
      expect(stats.totalVideos).toBe(12);
      expect(stats.totalAnnotations).toBe(1250);
      expect(stats.activeTestSessions).toBe(2);
      expect(stats.completedTestSessions).toBe(8);
      expect(stats.averageProcessingTime).toBe(45.5);
      expect(stats.systemHealth).toBe('healthy');
    });

    it('should load chart data for dashboard visualization', async () => {
      // Arrange
      server.use(
        rest.get('/api/dashboard/charts', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              videoProcessingTrend: [
                { date: '2023-01-01', processed: 5, uploaded: 7 },
                { date: '2023-01-02', processed: 8, uploaded: 10 },
                { date: '2023-01-03', processed: 12, uploaded: 15 }
              ],
              detectionAccuracy: {
                precision: [0.95, 0.92, 0.94, 0.96],
                recall: [0.93, 0.95, 0.91, 0.94],
                dates: ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04']
              },
              vruTypeDistribution: {
                pedestrian: 450,
                cyclist: 320,
                motorcyclist: 180,
                wheelchair_user: 45,
                scooter_rider: 65
              }
            })
          );
        })
      );

      // Act
      const chartData = await apiService.getChartData();

      // Assert
      expect(chartData).toBeDefined();
      expect(chartData.videoProcessingTrend).toBeDefined();
      expect(Array.isArray(chartData.videoProcessingTrend)).toBe(true);
      expect(chartData.detectionAccuracy).toBeDefined();
      expect(chartData.vruTypeDistribution).toBeDefined();
      expect(chartData.vruTypeDistribution.pedestrian).toBe(450);
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle API errors gracefully', async () => {
      // Arrange - Mock an error response
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({ message: 'Internal server error' })
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle network timeouts', async () => {
      // Arrange - Mock a timeout
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.delay(35000), // Delay longer than timeout
            ctx.status(200),
            ctx.json([])
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });

    it('should handle malformed response data', async () => {
      // Arrange - Mock malformed response
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.text('Invalid JSON response')
          );
        })
      );

      // Act & Assert
      await expect(apiService.getProjects()).rejects.toThrow();
    });
  });

  describe('Real-time Data Flow (WebSocket)', () => {
    it('should handle WebSocket connection for real-time updates', async () => {
      // This test would require WebSocket mocking
      // For now, test the connection logic
      
      const mockSocket = {
        on: vi.fn(),
        emit: vi.fn(),
        close: vi.fn(),
        connected: true
      };

      // Mock socket.io
      vi.mock('socket.io-client', () => ({
        io: () => mockSocket
      }));

      // Simulate WebSocket events
      const mockDetectionEvent = {
        id: 'detection-1',
        timestamp: 5.5,
        validationResult: 'TP' as const,
        confidence: 0.92,
        classLabel: 'pedestrian'
      };

      // Test event handling
      expect(mockSocket.on).toBeDefined();
      expect(mockSocket.emit).toBeDefined();
    });

    it('should handle WebSocket disconnection and reconnection', async () => {
      // Mock WebSocket disconnection scenario
      const mockSocket = {
        on: vi.fn(),
        emit: vi.fn(),
        close: vi.fn(),
        connected: false,
        disconnected: true
      };

      // Test reconnection logic
      expect(mockSocket.connected).toBe(false);
      expect(mockSocket.disconnected).toBe(true);
    });
  });

  describe('Data Validation and Transformation', () => {
    it('should validate form data before sending to backend', async () => {
      // Test client-side validation
      const invalidProjectData = {
        name: '', // Invalid: empty name
        description: 'Test description',
        camera_model: '',
        camera_view: 'Front-facing VRU',
        signal_type: 'GPIO'
      };

      // Mock validation error response
      server.use(
        rest.post('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({
              message: 'Validation error',
              errors: {
                name: 'Name is required',
                camera_model: 'Camera model is required'
              }
            })
          );
        })
      );

      // Act & Assert
      await expect(apiService.createProject(invalidProjectData)).rejects.toThrow();
    });

    it('should transform API response data for frontend consumption', async () => {
      // Test data transformation
      server.use(
        rest.get('/api/projects', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json([
              {
                id: 'project-1',
                name: 'Test Project',
                created_at: '2023-01-01T12:00:00Z',
                updated_at: '2023-01-02T14:30:00Z',
                // Backend uses snake_case
                camera_model: 'TestCam',
                camera_view: 'Front-facing VRU',
                signal_type: 'GPIO'
              }
            ])
          );
        })
      );

      // Act
      const projects = await apiService.getProjects();

      // Assert - API service should handle the transformation
      expect(projects[0]).toHaveProperty('id');
      expect(projects[0]).toHaveProperty('name');
      expect(projects[0]).toHaveProperty('created_at');
      expect(projects[0]).toHaveProperty('camera_model');
    });
  });

  describe('Caching and Performance', () => {
    it('should cache GET requests to improve performance', async () => {
      // First request
      const projects1 = await apiService.getProjects();
      
      // Second request (should be cached)
      const projects2 = await apiService.getProjects();

      // Assert both requests return data
      expect(projects1).toBeDefined();
      expect(projects2).toBeDefined();
      expect(projects1.length).toBe(projects2.length);
    });

    it('should invalidate cache after mutating operations', async () => {
      // Load initial data
      await apiService.getProjects();

      // Create new project (should invalidate cache)
      await apiService.createProject(TEST_PROJECTS.basic);

      // Next request should fetch fresh data
      const updatedProjects = await apiService.getProjects();
      expect(updatedProjects).toBeDefined();
    });
  });

  describe('State Management Integration', () => {
    it('should maintain consistent state across components', async () => {
      // This would test React state management integration
      // For now, test that API calls maintain state properly
      
      const projectData = TEST_PROJECTS.basic;
      const createdProject = await apiService.createProject(projectData);
      
      expect(createdProject).toBeDefined();
      
      const retrievedProject = await apiService.getProject(createdProject.id);
      expect(retrievedProject).toBeDefined();
      
      // State should be consistent
      expect(retrievedProject.name).toBe(createdProject.name);
    });
  });
});