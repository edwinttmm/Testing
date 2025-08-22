/**
 * Test Data Factories for Integration Tests
 * 
 * Provides consistent mock data for testing AI model validation platform workflows
 */

import { VideoFile, Project, TestSession, DetectionEvent, GroundTruthAnnotation } from '../../src/services/types';

// ============================================================================
// PROJECT FACTORIES
// ============================================================================

export interface MockProjectOptions {
  id?: string;
  name?: string;
  description?: string;
  status?: 'active' | 'inactive' | 'completed';
  videoCount?: number;
  createdAt?: string;
  updatedAt?: string;
}

export const createMockProject = (options: MockProjectOptions = {}): Project => {
  const defaultProject: Project = {
    id: options.id || 'project-123',
    name: options.name || 'Test Project',
    description: options.description || 'A test project for integration testing',
    status: options.status || 'active',
    videoCount: options.videoCount || 3,
    createdAt: options.createdAt || new Date().toISOString(),
    updatedAt: options.updatedAt || new Date().toISOString(),
    metadata: {
      camera_type: 'surveillance',
      detection_classes: ['person', 'vehicle', 'bicycle'],
      performance_criteria: {
        min_accuracy: 0.85,
        max_latency_ms: 100,
        min_recall: 0.8
      }
    }
  };

  return { ...defaultProject, ...options };
};

export const createMockProjectList = (count: number = 3): Project[] => {
  return Array.from({ length: count }, (_, index) => 
    createMockProject({
      id: `project-${index + 1}`,
      name: `Test Project ${index + 1}`,
      videoCount: Math.floor(Math.random() * 10) + 1
    })
  );
};

// ============================================================================
// VIDEO FACTORIES
// ============================================================================

export interface MockVideoOptions {
  id?: string;
  filename?: string;
  originalName?: string;
  fileSize?: number;
  mimeType?: string;
  duration?: number;
  width?: number;
  height?: number;
  frameRate?: number;
  status?: 'uploading' | 'processing' | 'ready' | 'error';
  uploadTimestamp?: string;
  processingProgress?: number;
  url?: string;
  thumbnailUrl?: string;
}

export const createMockVideo = (options: MockVideoOptions = {}): VideoFile => {
  const defaultVideo: VideoFile = {
    id: options.id || 'video-123',
    filename: options.filename || 'test-video.mp4',
    originalName: options.originalName || 'test-video.mp4',
    fileSize: options.fileSize || 10485760, // 10MB
    mimeType: options.mimeType || 'video/mp4',
    duration: options.duration || 60.0,
    width: options.width || 1920,
    height: options.height || 1080,
    frameRate: options.frameRate || 30,
    status: options.status || 'ready',
    uploadTimestamp: options.uploadTimestamp || new Date().toISOString(),
    processingProgress: options.processingProgress || 100,
    url: options.url || '/api/videos/video-123/stream',
    thumbnailUrl: options.thumbnailUrl || '/api/videos/video-123/thumbnail',
    metadata: {
      codec: 'h264',
      bitrate: 5000000,
      container: 'mp4',
      audio_channels: 2,
      processing_log: [
        {
          timestamp: new Date().toISOString(),
          stage: 'upload_complete',
          status: 'success'
        },
        {
          timestamp: new Date().toISOString(),
          stage: 'processing_complete',
          status: 'success'
        }
      ]
    }
  };

  return { ...defaultVideo, ...options };
};

export const createMockVideoList = (count: number = 5): VideoFile[] => {
  return Array.from({ length: count }, (_, index) => 
    createMockVideo({
      id: `video-${index + 1}`,
      filename: `test-video-${index + 1}.mp4`,
      originalName: `Test Video ${index + 1}.mp4`,
      duration: Math.random() * 120 + 30 // 30-150 seconds
    })
  );
};

// ============================================================================
// TEST SESSION FACTORIES
// ============================================================================

export interface MockTestSessionOptions {
  id?: string;
  projectId?: string;
  name?: string;
  status?: 'created' | 'running' | 'paused' | 'completed' | 'failed';
  startTime?: string;
  endTime?: string;
  videoIds?: string[];
  configuration?: any;
  metrics?: any;
  progress?: number;
}

export const createMockTestSession = (options: MockTestSessionOptions = {}): TestSession => {
  const defaultSession: TestSession = {
    id: options.id || 'session-123',
    projectId: options.projectId || 'project-123',
    name: options.name || 'Integration Test Session',
    status: options.status || 'created',
    startTime: options.startTime || new Date().toISOString(),
    endTime: options.endTime || null,
    videoIds: options.videoIds || ['video-123', 'video-124'],
    configuration: options.configuration || {
      latency_threshold_ms: 100,
      accuracy_threshold: 0.85,
      detection_classes: ['person', 'vehicle'],
      real_time_monitoring: true,
      signal_processing: {
        enabled: true,
        signal_type: 'pedestrian_crossing',
        validation_criteria: {
          max_latency_ms: 150,
          min_confidence: 0.8
        }
      }
    },
    metrics: options.metrics || {
      total_detections: 0,
      true_positives: 0,
      false_positives: 0,
      false_negatives: 0,
      accuracy: 0,
      precision: 0,
      recall: 0,
      f1_score: 0,
      avg_latency_ms: 0,
      max_latency_ms: 0,
      throughput_fps: 0
    },
    progress: options.progress || 0
  };

  return { ...defaultSession, ...options };
};

export const createMockTestSessionList = (count: number = 3): TestSession[] => {
  return Array.from({ length: count }, (_, index) => 
    createMockTestSession({
      id: `session-${index + 1}`,
      name: `Test Session ${index + 1}`,
      status: index === 0 ? 'running' : index === 1 ? 'completed' : 'created'
    })
  );
};

// ============================================================================
// DETECTION EVENT FACTORIES
// ============================================================================

export interface MockDetectionEventOptions {
  id?: string;
  testSessionId?: string;
  videoId?: string;
  timestamp?: number;
  frameNumber?: number;
  classLabel?: string;
  confidence?: number;
  bbox?: { x: number; y: number; width: number; height: number };
  validationResult?: 'TP' | 'FP' | 'FN' | 'TN';
  latencyMs?: number;
  signalTimestamp?: number;
  detectionLatency?: number;
  metadata?: any;
}

export const createMockDetectionEvent = (options: MockDetectionEventOptions = {}): DetectionEvent => {
  const defaultEvent: DetectionEvent = {
    id: options.id || 'detection-123',
    testSessionId: options.testSessionId || 'session-123',
    videoId: options.videoId || 'video-123',
    timestamp: options.timestamp || Date.now(),
    frameNumber: options.frameNumber || Math.floor(Math.random() * 1800), // 0-1800 frames (60 seconds at 30fps)
    classLabel: options.classLabel || 'person',
    confidence: options.confidence || Math.random() * 0.3 + 0.7, // 0.7-1.0
    bbox: options.bbox || {
      x: Math.floor(Math.random() * 1000),
      y: Math.floor(Math.random() * 600),
      width: Math.floor(Math.random() * 200) + 50,
      height: Math.floor(Math.random() * 300) + 100
    },
    validationResult: options.validationResult || 'TP',
    latencyMs: options.latencyMs || Math.floor(Math.random() * 50) + 30, // 30-80ms
    signalTimestamp: options.signalTimestamp || Date.now() - 1000,
    detectionLatency: options.detectionLatency || Math.floor(Math.random() * 100) + 50,
    metadata: options.metadata || {
      detection_method: 'YOLO',
      model_version: 'v8',
      processing_time_ms: Math.floor(Math.random() * 30) + 10,
      gpu_utilization: Math.random() * 0.5 + 0.3
    }
  };

  return { ...defaultEvent, ...options };
};

export const createMockDetectionEventList = (count: number = 10): DetectionEvent[] => {
  return Array.from({ length: count }, (_, index) => {
    const validationResults: Array<'TP' | 'FP' | 'FN' | 'TN'> = ['TP', 'FP', 'FN', 'TN'];
    const classLabels = ['person', 'vehicle', 'bicycle', 'dog'];
    
    return createMockDetectionEvent({
      id: `detection-${index + 1}`,
      frameNumber: index * 30, // One detection every second
      validationResult: validationResults[index % validationResults.length],
      classLabel: classLabels[index % classLabels.length]
    });
  });
};

// ============================================================================
// ANNOTATION FACTORIES
// ============================================================================

export interface MockAnnotationOptions {
  id?: string;
  videoId?: string;
  frameNumber?: number;
  classLabel?: string;
  confidence?: number;
  bbox?: { x: number; y: number; width: number; height: number };
  shape?: 'rectangle' | 'circle' | 'polygon';
  points?: Array<{ x: number; y: number }>;
  metadata?: any;
  createdAt?: string;
  updatedAt?: string;
}

export const createMockAnnotation = (options: MockAnnotationOptions = {}): GroundTruthAnnotation => {
  const defaultAnnotation: GroundTruthAnnotation = {
    id: options.id || 'annotation-123',
    videoId: options.videoId || 'video-123',
    frameNumber: options.frameNumber || Math.floor(Math.random() * 1800),
    classLabel: options.classLabel || 'person',
    confidence: options.confidence || 1.0, // Ground truth has 100% confidence
    bbox: options.bbox || {
      x: Math.floor(Math.random() * 1000),
      y: Math.floor(Math.random() * 600),
      width: Math.floor(Math.random() * 200) + 50,
      height: Math.floor(Math.random() * 300) + 100
    },
    shape: options.shape || 'rectangle',
    points: options.points || [],
    metadata: options.metadata || {
      annotator: 'test-user',
      annotation_tool: 'manual',
      review_status: 'approved',
      quality_score: 0.95
    },
    createdAt: options.createdAt || new Date().toISOString(),
    updatedAt: options.updatedAt || new Date().toISOString()
  };

  return { ...defaultAnnotation, ...options };
};

export const createMockAnnotationList = (count: number = 5): GroundTruthAnnotation[] => {
  return Array.from({ length: count }, (_, index) => {
    const classLabels = ['person', 'vehicle', 'bicycle', 'traffic_light', 'stop_sign'];
    const shapes: Array<'rectangle' | 'circle' | 'polygon'> = ['rectangle', 'circle', 'polygon'];
    
    return createMockAnnotation({
      id: `annotation-${index + 1}`,
      frameNumber: index * 60, // One annotation per 2 seconds
      classLabel: classLabels[index % classLabels.length],
      shape: shapes[index % shapes.length]
    });
  });
};

// ============================================================================
// WEBSOCKET MESSAGE FACTORIES
// ============================================================================

export interface MockWebSocketMessageOptions {
  type?: string;
  data?: any;
  timestamp?: string;
}

export const createMockWebSocketMessage = (options: MockWebSocketMessageOptions = {}) => {
  return {
    type: options.type || 'test_message',
    data: options.data || {},
    timestamp: options.timestamp || new Date().toISOString()
  };
};

export const createVideoProcessingMessage = (videoId: string, status: string, progress: number = 100) => {
  return createMockWebSocketMessage({
    type: 'video_processing_status',
    data: {
      video_id: videoId,
      status,
      progress_percentage: progress,
      estimated_completion: new Date(Date.now() + 30000).toISOString()
    }
  });
};

export const createTestSessionUpdateMessage = (sessionId: string, metrics: any) => {
  return createMockWebSocketMessage({
    type: 'test_session_update',
    data: {
      test_session_id: sessionId,
      status: 'running',
      current_detections: metrics.detections || 0,
      metrics: {
        accuracy: metrics.accuracy || 0.85,
        latency_avg: metrics.latency || 75,
        throughput: metrics.throughput || 15
      }
    }
  });
};

export const createDetectionEventMessage = (sessionId: string, detection: Partial<DetectionEvent>) => {
  return createMockWebSocketMessage({
    type: 'detection_event',
    data: {
      test_session_id: sessionId,
      detection_id: detection.id || 'det-123',
      timestamp: detection.timestamp || Date.now(),
      confidence: detection.confidence || 0.9,
      validation_result: detection.validationResult || 'TP',
      latency_ms: detection.latencyMs || 65,
      class_label: detection.classLabel || 'person'
    }
  });
};

export const createSystemAlertMessage = (alertType: string, severity: string = 'info', message: string = 'Test alert') => {
  return createMockWebSocketMessage({
    type: 'system_alert',
    data: {
      alert_type: alertType,
      severity,
      message,
      metadata: {
        component: 'test',
        action_required: severity === 'error'
      }
    }
  });
};

// ============================================================================
// PERFORMANCE METRICS FACTORIES
// ============================================================================

export interface MockPerformanceMetrics {
  cpu_usage?: number;
  memory_usage?: number;
  gpu_usage?: number;
  processing_fps?: number;
  detection_latency?: number;
  network_latency?: number;
  disk_io?: number;
  queue_length?: number;
}

export const createMockPerformanceMetrics = (options: MockPerformanceMetrics = {}): MockPerformanceMetrics => {
  return {
    cpu_usage: options.cpu_usage || Math.random() * 30 + 40, // 40-70%
    memory_usage: options.memory_usage || Math.random() * 20 + 60, // 60-80%
    gpu_usage: options.gpu_usage || Math.random() * 40 + 30, // 30-70%
    processing_fps: options.processing_fps || Math.random() * 10 + 25, // 25-35 fps
    detection_latency: options.detection_latency || Math.random() * 50 + 50, // 50-100ms
    network_latency: options.network_latency || Math.random() * 20 + 10, // 10-30ms
    disk_io: options.disk_io || Math.random() * 50 + 100, // 100-150 MB/s
    queue_length: options.queue_length || Math.floor(Math.random() * 10) // 0-9 items
  };
};

// ============================================================================
// FILE UPLOAD SIMULATION
// ============================================================================

export const createMockFile = (name: string = 'test-video.mp4', size: number = 10485760, type: string = 'video/mp4'): File => {
  const content = new Array(size).fill('a').join('');
  return new File([content], name, { type });
};

export const createMockFileList = (files: Array<{ name: string; size?: number; type?: string }>): FileList => {
  const fileList = files.map(file => 
    createMockFile(file.name, file.size, file.type)
  );
  
  // Create a proper FileList object
  const dt = new DataTransfer();
  fileList.forEach(file => dt.items.add(file));
  return dt.files;
};

// ============================================================================
// ERROR SIMULATION
// ============================================================================

export interface MockApiError {
  status: number;
  message: string;
  details?: any;
}

export const createMockApiError = (status: number = 500, message: string = 'Internal Server Error', details?: any): MockApiError => {
  return {
    status,
    message,
    details: details || {
      error_code: 'TEST_ERROR',
      timestamp: new Date().toISOString(),
      request_id: 'test-request-123'
    }
  };
};

export const createNetworkError = () => createMockApiError(0, 'Network Error');
export const createValidationError = (field: string = 'test_field') => 
  createMockApiError(400, 'Validation Error', { field, message: `Invalid ${field}` });
export const createAuthError = () => createMockApiError(401, 'Unauthorized');
export const createNotFoundError = (resource: string = 'resource') => 
  createMockApiError(404, `${resource} not found`);
export const createServerError = () => createMockApiError(500, 'Internal Server Error');

// ============================================================================
// INTEGRATION TEST SCENARIOS
// ============================================================================

export const createCompleteTestScenario = () => {
  const project = createMockProject({ id: 'scenario-project' });
  const videos = createMockVideoList(3).map((video, index) => ({
    ...video,
    id: `scenario-video-${index + 1}`
  }));
  const testSession = createMockTestSession({ 
    id: 'scenario-session',
    projectId: project.id,
    videoIds: videos.map(v => v.id)
  });
  const detections = createMockDetectionEventList(15).map((detection, index) => ({
    ...detection,
    id: `scenario-detection-${index + 1}`,
    testSessionId: testSession.id,
    videoId: videos[index % videos.length].id
  }));
  const annotations = createMockAnnotationList(10).map((annotation, index) => ({
    ...annotation,
    id: `scenario-annotation-${index + 1}`,
    videoId: videos[index % videos.length].id
  }));

  return {
    project,
    videos,
    testSession,
    detections,
    annotations
  };
};

export const createVideoProcessingScenario = (videoId: string = 'processing-video') => {
  const video = createMockVideo({ 
    id: videoId, 
    status: 'processing', 
    processingProgress: 0 
  });
  
  const progressMessages = [
    createVideoProcessingMessage(videoId, 'processing', 25),
    createVideoProcessingMessage(videoId, 'processing', 50),
    createVideoProcessingMessage(videoId, 'processing', 75),
    createVideoProcessingMessage(videoId, 'completed', 100)
  ];

  return { video, progressMessages };
};

export const createRealtimeTestScenario = (sessionId: string = 'realtime-session') => {
  const session = createMockTestSession({ id: sessionId, status: 'running' });
  
  const updates = [
    createTestSessionUpdateMessage(sessionId, { detections: 5, accuracy: 0.85, latency: 75 }),
    createTestSessionUpdateMessage(sessionId, { detections: 12, accuracy: 0.88, latency: 72 }),
    createTestSessionUpdateMessage(sessionId, { detections: 20, accuracy: 0.91, latency: 68 })
  ];

  const detectionEvents = [
    createDetectionEventMessage(sessionId, { validationResult: 'TP', confidence: 0.95 }),
    createDetectionEventMessage(sessionId, { validationResult: 'FP', confidence: 0.65 }),
    createDetectionEventMessage(sessionId, { validationResult: 'TP', confidence: 0.88 })
  ];

  return { session, updates, detectionEvents };
};
