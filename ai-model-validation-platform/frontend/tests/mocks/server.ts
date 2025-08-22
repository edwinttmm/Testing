/**
 * Mock Server for Integration Tests
 * 
 * MSW (Mock Service Worker) setup for API mocking during integration tests
 */

import { setupServer } from 'msw/node';
import { rest } from 'msw';
import {
  createMockProject,
  createMockProjectList,
  createMockVideo,
  createMockVideoList,
  createMockTestSession,
  createMockTestSessionList,
  createMockDetectionEvent,
  createMockDetectionEventList,
  createMockAnnotation,
  createMockAnnotationList,
  createMockApiError
} from '../helpers/test-factories';

// Base URL for API
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ============================================================================
// API ENDPOINT HANDLERS
// ============================================================================

const handlers = [
  // ============================================================================
  // HEALTH CHECK
  // ============================================================================
  rest.get(`${API_BASE}/health`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: '1.0.0',
        services: {
          database: 'connected',
          websocket: 'active',
          ml_pipeline: 'ready'
        }
      })
    );
  }),

  // ============================================================================
  // PROJECT ENDPOINTS
  // ============================================================================
  rest.get(`${API_BASE}/api/projects`, (req, res, ctx) => {
    const page = req.url.searchParams.get('page') || '1';
    const limit = req.url.searchParams.get('limit') || '10';
    const search = req.url.searchParams.get('search');
    
    let projects = createMockProjectList(25);
    
    // Apply search filter
    if (search) {
      projects = projects.filter(project => 
        project.name.toLowerCase().includes(search.toLowerCase()) ||
        project.description.toLowerCase().includes(search.toLowerCase())
      );
    }
    
    // Apply pagination
    const pageNum = parseInt(page);
    const limitNum = parseInt(limit);
    const startIndex = (pageNum - 1) * limitNum;
    const endIndex = startIndex + limitNum;
    const paginatedProjects = projects.slice(startIndex, endIndex);
    
    return res(
      ctx.status(200),
      ctx.json({
        projects: paginatedProjects,
        total: projects.length,
        page: pageNum,
        limit: limitNum,
        total_pages: Math.ceil(projects.length / limitNum)
      })
    );
  }),

  rest.get(`${API_BASE}/api/projects/:id`, (req, res, ctx) => {
    const { id } = req.params;
    
    if (id === 'not-found') {
      return res(
        ctx.status(404),
        ctx.json({ detail: 'Project not found' })
      );
    }
    
    return res(
      ctx.status(200),
      ctx.json(createMockProject({ id: id as string }))
    );
  }),

  rest.post(`${API_BASE}/api/projects`, async (req, res, ctx) => {
    const body = await req.json();
    
    // Validate required fields
    if (!body.name) {
      return res(
        ctx.status(400),
        ctx.json({ detail: 'Project name is required' })
      );
    }
    
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const newProject = createMockProject({
      id: `project-${Date.now()}`,
      name: body.name,
      description: body.description,
      status: 'active'
    });
    
    return res(
      ctx.status(201),
      ctx.json(newProject)
    );
  }),

  rest.put(`${API_BASE}/api/projects/:id`, async (req, res, ctx) => {
    const { id } = req.params;
    const body = await req.json();
    
    const updatedProject = createMockProject({
      id: id as string,
      ...body,
      updatedAt: new Date().toISOString()
    });
    
    return res(
      ctx.status(200),
      ctx.json(updatedProject)
    );
  }),

  rest.delete(`${API_BASE}/api/projects/:id`, (req, res, ctx) => {
    return res(
      ctx.status(204)
    );
  }),

  // ============================================================================
  // VIDEO ENDPOINTS
  // ============================================================================
  rest.get(`${API_BASE}/api/videos`, (req, res, ctx) => {
    const projectId = req.url.searchParams.get('project_id');
    const status = req.url.searchParams.get('status');
    
    let videos = createMockVideoList(15);
    
    // Apply filters
    if (status) {
      videos = videos.filter(video => video.status === status);
    }
    
    return res(
      ctx.status(200),
      ctx.json({
        videos,
        total: videos.length
      })
    );
  }),

  rest.get(`${API_BASE}/api/videos/:id`, (req, res, ctx) => {
    const { id } = req.params;
    
    return res(
      ctx.status(200),
      ctx.json(createMockVideo({ id: id as string }))
    );
  }),

  rest.post(`${API_BASE}/api/videos/upload`, async (req, res, ctx) => {
    // Simulate upload processing time
    const uploadDelay = Math.random() * 1000 + 500; // 500-1500ms
    await new Promise(resolve => setTimeout(resolve, uploadDelay));
    
    // Check if this should simulate an error
    const shouldError = req.url.searchParams.get('simulate_error');
    if (shouldError) {
      return res(
        ctx.status(500),
        ctx.json({ detail: 'Upload processing failed' })
      );
    }
    
    const newVideo = createMockVideo({
      id: `video-${Date.now()}`,
      status: 'processing',
      processingProgress: 0
    });
    
    return res(
      ctx.status(201),
      ctx.json(newVideo)
    );
  }),

  rest.get(`${API_BASE}/api/videos/:id/stream`, (req, res, ctx) => {
    // Mock video stream endpoint
    return res(
      ctx.status(200),
      ctx.set('Content-Type', 'video/mp4'),
      ctx.set('Accept-Ranges', 'bytes'),
      ctx.body('mock-video-stream-data')
    );
  }),

  rest.get(`${API_BASE}/api/videos/:id/thumbnail`, (req, res, ctx) => {
    // Mock thumbnail endpoint
    return res(
      ctx.status(200),
      ctx.set('Content-Type', 'image/jpeg'),
      ctx.body('mock-thumbnail-data')
    );
  }),

  // ============================================================================
  // TEST SESSION ENDPOINTS
  // ============================================================================
  rest.get(`${API_BASE}/api/test-sessions`, (req, res, ctx) => {
    const projectId = req.url.searchParams.get('project_id');
    const status = req.url.searchParams.get('status');
    
    let sessions = createMockTestSessionList(10);
    
    // Apply filters
    if (status) {
      sessions = sessions.filter(session => session.status === status);
    }
    
    return res(
      ctx.status(200),
      ctx.json({
        sessions,
        total: sessions.length
      })
    );
  }),

  rest.get(`${API_BASE}/api/test-sessions/:id`, (req, res, ctx) => {
    const { id } = req.params;
    
    return res(
      ctx.status(200),
      ctx.json(createMockTestSession({ id: id as string }))
    );
  }),

  rest.post(`${API_BASE}/api/test-sessions`, async (req, res, ctx) => {
    const body = await req.json();
    
    // Simulate session creation delay
    await new Promise(resolve => setTimeout(resolve, 200));
    
    const newSession = createMockTestSession({
      id: `session-${Date.now()}`,
      name: body.name,
      projectId: body.project_id,
      configuration: body.configuration,
      status: 'created'
    });
    
    return res(
      ctx.status(201),
      ctx.json(newSession)
    );
  }),

  rest.post(`${API_BASE}/api/test-sessions/:id/start`, (req, res, ctx) => {
    const { id } = req.params;
    
    return res(
      ctx.status(200),
      ctx.json({
        session_id: id,
        status: 'running',
        started_at: new Date().toISOString()
      })
    );
  }),

  rest.post(`${API_BASE}/api/test-sessions/:id/stop`, (req, res, ctx) => {
    const { id } = req.params;
    
    return res(
      ctx.status(200),
      ctx.json({
        session_id: id,
        status: 'stopped',
        stopped_at: new Date().toISOString()
      })
    );
  }),

  // ============================================================================
  // DETECTION ENDPOINTS
  // ============================================================================
  rest.get(`${API_BASE}/api/test-sessions/:id/detections`, (req, res, ctx) => {
    const { id } = req.params;
    const limit = req.url.searchParams.get('limit') || '50';
    const offset = req.url.searchParams.get('offset') || '0';
    
    const detections = createMockDetectionEventList(parseInt(limit));
    
    return res(
      ctx.status(200),
      ctx.json({
        detections,
        total: 1000, // Simulate large dataset
        limit: parseInt(limit),
        offset: parseInt(offset)
      })
    );
  }),

  rest.get(`${API_BASE}/api/detections/:id`, (req, res, ctx) => {
    const { id } = req.params;
    
    return res(
      ctx.status(200),
      ctx.json(createMockDetectionEvent({ id: id as string }))
    );
  }),

  // ============================================================================
  // ANNOTATION ENDPOINTS
  // ============================================================================
  rest.get(`${API_BASE}/api/annotations/videos/:videoId/annotations`, (req, res, ctx) => {
    const { videoId } = req.params;
    const frameNumber = req.url.searchParams.get('frame_number');
    
    let annotations = createMockAnnotationList(20);
    
    // Filter by frame if specified
    if (frameNumber) {
      const frame = parseInt(frameNumber);
      annotations = annotations.filter(ann => 
        Math.abs(ann.frameNumber - frame) <= 5
      );
    }
    
    return res(
      ctx.status(200),
      ctx.json({
        annotations,
        video_id: videoId,
        total: annotations.length
      })
    );
  }),

  rest.post(`${API_BASE}/api/annotations/videos/:videoId/annotations`, async (req, res, ctx) => {
    const { videoId } = req.params;
    const body = await req.json();
    
    const newAnnotation = createMockAnnotation({
      id: `annotation-${Date.now()}`,
      videoId: videoId as string,
      ...body
    });
    
    return res(
      ctx.status(201),
      ctx.json(newAnnotation)
    );
  }),

  rest.put(`${API_BASE}/api/annotations/:id`, async (req, res, ctx) => {
    const { id } = req.params;
    const body = await req.json();
    
    const updatedAnnotation = createMockAnnotation({
      id: id as string,
      ...body,
      updatedAt: new Date().toISOString()
    });
    
    return res(
      ctx.status(200),
      ctx.json(updatedAnnotation)
    );
  }),

  rest.delete(`${API_BASE}/api/annotations/:id`, (req, res, ctx) => {
    return res(
      ctx.status(204)
    );
  }),

  rest.post(`${API_BASE}/api/annotations/export`, async (req, res, ctx) => {
    const body = await req.json();
    
    // Simulate export processing
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const exportData = {
      format: body.format || 'COCO',
      annotations: createMockAnnotationList(body.annotation_count || 10),
      metadata: {
        export_timestamp: new Date().toISOString(),
        video_id: body.video_id,
        total_annotations: body.annotation_count || 10
      }
    };
    
    return res(
      ctx.status(200),
      ctx.set('Content-Type', 'application/json'),
      ctx.set('Content-Disposition', 'attachment; filename="annotations.json"'),
      ctx.json(exportData)
    );
  }),

  // ============================================================================
  // SIGNAL VALIDATION ENDPOINTS
  // ============================================================================
  rest.post(`${API_BASE}/api/signal-validation/process`, async (req, res, ctx) => {
    const body = await req.json();
    
    // Simulate signal processing
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const result = {
      signal_id: `signal-${Date.now()}`,
      processing_status: 'completed',
      detected_signals: [
        {
          timestamp: 1.5,
          signal_type: body.signal_type || 'pedestrian_crossing',
          confidence: 0.92,
          metadata: { x: 100, y: 200, width: 50, height: 80 }
        },
        {
          timestamp: 3.2,
          signal_type: body.signal_type || 'pedestrian_crossing',
          confidence: 0.87,
          metadata: { x: 150, y: 180, width: 60, height: 90 }
        }
      ],
      validation_results: {
        latency_ms: Math.floor(Math.random() * 50) + 50,
        accuracy: Math.random() * 0.2 + 0.8,
        meets_criteria: Math.random() > 0.2
      }
    };
    
    return res(
      ctx.status(200),
      ctx.json(result)
    );
  }),

  // ============================================================================
  // ANALYTICS AND METRICS
  // ============================================================================
  rest.get(`${API_BASE}/api/analytics/dashboard`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        total_projects: 15,
        total_videos: 127,
        total_test_sessions: 43,
        active_sessions: 3,
        recent_activity: [
          {
            id: '1',
            type: 'test_completed',
            timestamp: new Date().toISOString(),
            description: 'Test session "Vehicle Detection" completed'
          },
          {
            id: '2',
            type: 'video_uploaded',
            timestamp: new Date(Date.now() - 300000).toISOString(),
            description: 'Video "highway-traffic.mp4" uploaded'
          }
        ],
        performance_metrics: {
          avg_detection_latency: 78,
          avg_accuracy: 0.91,
          system_uptime: 99.7,
          processing_queue_length: 5
        }
      })
    );
  }),

  // ============================================================================
  // ERROR SIMULATION ENDPOINTS
  // ============================================================================
  rest.get(`${API_BASE}/api/simulate/error/:type`, (req, res, ctx) => {
    const { type } = req.params;
    
    switch (type) {
      case 'network':
        return res.networkError('Network error simulated');
      
      case 'timeout':
        // Never resolve to simulate timeout
        return new Promise(() => {});
      
      case 'server-error':
        return res(
          ctx.status(500),
          ctx.json({ detail: 'Internal server error simulated' })
        );
      
      case 'validation-error':
        return res(
          ctx.status(400),
          ctx.json({ 
            detail: 'Validation error',
            errors: {
              field: 'test_field',
              message: 'Invalid value provided'
            }
          })
        );
      
      case 'unauthorized':
        return res(
          ctx.status(401),
          ctx.json({ detail: 'Unauthorized access' })
        );
      
      default:
        return res(
          ctx.status(400),
          ctx.json({ detail: 'Unknown error type' })
        );
    }
  })
];

// ============================================================================
// SERVER SETUP
// ============================================================================

// Create mock server
export const server = setupServer(...handlers);

// ============================================================================
// DYNAMIC HANDLERS
// ============================================================================

// Helper function to add custom handlers during tests
export const addHandler = (handler: any) => {
  server.use(handler);
};

// Helper function to simulate API delays
export const simulateDelay = (ms: number) => {
  return server.use(
    rest.all('*', async (req, res, ctx) => {
      await new Promise(resolve => setTimeout(resolve, ms));
      return req.passthrough();
    })
  );
};

// Helper function to simulate intermittent failures
export const simulateFailureRate = (failureRate: number = 0.1) => {
  return server.use(
    rest.all('*', (req, res, ctx) => {
      if (Math.random() < failureRate) {
        return res(
          ctx.status(500),
          ctx.json({ detail: 'Random failure simulation' })
        );
      }
      return req.passthrough();
    })
  );
};

// ============================================================================
// WEBSOCKET MOCK HELPERS
// ============================================================================

export const mockWebSocketMessages = {
  videoProcessingUpdate: (videoId: string, progress: number, status: string = 'processing') => ({
    type: 'video_processing_status',
    data: {
      video_id: videoId,
      status,
      progress_percentage: progress,
      timestamp: new Date().toISOString()
    }
  }),
  
  detectionEvent: (sessionId: string, detection: any) => ({
    type: 'detection_event',
    data: {
      test_session_id: sessionId,
      ...detection,
      timestamp: new Date().toISOString()
    }
  }),
  
  testSessionUpdate: (sessionId: string, metrics: any) => ({
    type: 'test_session_update',
    data: {
      test_session_id: sessionId,
      ...metrics,
      timestamp: new Date().toISOString()
    }
  }),
  
  systemAlert: (alertType: string, message: string, severity: string = 'info') => ({
    type: 'system_alert',
    data: {
      alert_type: alertType,
      message,
      severity,
      timestamp: new Date().toISOString()
    }
  })
};

const server = setupServer(...handlers);
server.listen({
  onUnhandledRequest: 'warn'
});

console.log('✅ Mock server setup completed');
