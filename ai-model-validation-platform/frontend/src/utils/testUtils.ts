/**
 * Type-safe test utilities for mock creation and validation
 */

import { 
  DetectionPipelineResult, 
  Project, 
  VideoFile, 
  GroundTruthAnnotation, 
  Detection,
  ProjectStatus,
  CameraType,
  SignalType,
  VRUType,
  VideoStatus
} from '../services/types';
import { Dataset } from '../types/global';

// Type-safe detection result mock creator
export const createMockDetectionResult = (overrides: Partial<DetectionPipelineResult> = {}): DetectionPipelineResult => ({
  videoId: 'test-video',
  detections: [],
  processingTime: 1000,
  modelUsed: 'test-model',
  totalDetections: 0,
  confidenceDistribution: {
    '0.8-0.9': 0,
    '0.9-1.0': 0
  },
  ...overrides
});

export const createMockProject = (overrides: Partial<Project> = {}): Project => ({
  id: 'test-project-id',
  name: 'Test Project',
  description: 'A test project',
  cameraModel: 'Test Camera',
  cameraView: CameraType.FRONT_FACING_VRU,
  signalType: SignalType.GPIO,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  status: ProjectStatus.ACTIVE,
  ownerId: 'test-owner-id',
  ...overrides
});

// Type-safe video file mock creator
export const createMockVideoFile = (overrides: Partial<VideoFile> = {}): VideoFile => ({
  id: 'test-video-id',
  filename: 'test-video.mp4',
  originalName: 'test-video.mp4',
  url: '/api/videos/test-video.mp4',
  projectId: 'test-project-id',
  status: VideoStatus.VALIDATED,
  duration: 30,
  frameRate: 30, // Added missing frameRate property
  fps: 30,
  size: 1024000,
  fileSize: 1024000,
  createdAt: new Date().toISOString(),
  uploadedAt: new Date().toISOString(),
  groundTruthGenerated: false,
  groundTruthStatus: 'pending',
  processing_status: 'completed', // Properly set processing_status
  processingStatus: 'completed', // Backward compatibility
  detectionCount: 0,
  annotationCount: 0,
  ...overrides
});

// Type-safe ground truth annotation mock creator
export const createMockGroundTruthAnnotation = (overrides: Partial<GroundTruthAnnotation> = {}): GroundTruthAnnotation => ({
  id: 'test-annotation-id',
  videoId: 'test-video-id',
  frameNumber: 0,
  timestamp: 0,
  boundingBox: {
    x: 0,
    y: 0,
    width: 100,
    height: 100,
    label: 'person',
    confidence: 0.95
  },
  vruType: VRUType.PEDESTRIAN,
  detectionId: 'test-detection-id',
  validated: false,
  validationStatus: 'pending',
  occluded: false,
  truncated: false,
  difficult: false,
  createdAt: '2024-01-01T00:00:00.000Z',
  ...overrides
});

// Type-safe detection mock creator
export const createMockDetection = (overrides: Partial<Detection> = {}): Detection => ({
  id: 'test-detection-id',
  videoId: 'test-video-id', // Add required videoId field
  detectionId: 'test-detection-id',
  frameNumber: 0, // Add required frameNumber field
  classId: 1, // Add required classId field
  className: 'test-detection', // Add required className field
  validationStatus: 'pending', // Add required validationStatus field
  boundingBox: {
    x: 0,
    y: 0,
    width: 100,
    height: 100,
    label: 'test-detection',
    confidence: 0.9
  },
  vruType: VRUType.PEDESTRIAN,
  confidence: 0.95,
  isGroundTruth: false,
  validated: false,
  createdAt: '2024-01-01T00:00:00.000Z',
  timestamp: 0,
  ...overrides
});

// Additional mock utility for video metadata subset
export const createMockVideoMetadata = (overrides: Partial<Pick<VideoFile, 'id' | 'filename' | 'duration' | 'fps' | 'size' | 'fileSize'>> = {}) => ({
  id: 'test-video-id',
  filename: 'test-video.mp4',
  duration: 30,
  fps: 30,
  size: 1024000,
  fileSize: 1024000,
  ...overrides
});

// Type guards with null checks
export const isDetectionPipelineResult = (obj: any): obj is DetectionPipelineResult => {
  return obj !== null && 
         obj !== undefined &&
         typeof obj === 'object' &&
         typeof obj.videoId === 'string' &&
         Array.isArray(obj.detections) &&
         typeof obj.processingTime === 'number' &&
         typeof obj.modelUsed === 'string' &&
         typeof obj.totalDetections === 'number' &&
         obj.confidenceDistribution !== null &&
         obj.confidenceDistribution !== undefined &&
         typeof obj.confidenceDistribution === 'object';
};

export const isProject = (obj: any): obj is Project => {
  return obj !== null && 
         obj !== undefined &&
         typeof obj === 'object' &&
         typeof obj.id === 'string' &&
         typeof obj.name === 'string' &&
         typeof obj.created_at === 'string';
};

// Dataset type guard - Using imported Dataset interface
export const isDataset = (obj: any): obj is Dataset => {
  return obj !== null && 
         obj !== undefined &&
         typeof obj === 'object' &&
         typeof obj.id === 'string' &&
         typeof obj.name === 'string' &&
         typeof obj.project_id === 'string';
};

export const isGroundTruthAnnotation = (obj: any): obj is GroundTruthAnnotation => {
  return obj !== null && 
         obj !== undefined &&
         typeof obj === 'object' &&
         typeof obj.id === 'string' &&
         typeof obj.videoId === 'string' &&
         typeof obj.frameNumber === 'number' &&
         obj.boundingBox !== null &&
         obj.boundingBox !== undefined &&
         typeof obj.boundingBox === 'object';
};

// Safe property access helpers
export const safeGetProperty = <T, K extends keyof T>(obj: T | null | undefined, key: K): T[K] | undefined => {
  if (obj === null || obj === undefined) {
    return undefined;
  }
  return obj[key];
};

export const safeGetNestedProperty = <T>(obj: any, path: string): T | undefined => {
  if (obj === null || obj === undefined) {
    return undefined;
  }
  
  const keys = path.split('.');
  let current = obj;
  
  for (const key of keys) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return undefined;
    }
    current = current[key];
  }
  
  return current as T;
};

// API response validation
export const validateApiResponse = <T>(
  response: any,
  validator: (obj: any) => obj is T
): T | null => {
  if (!validator(response)) {
    console.error('API response validation failed:', response);
    return null;
  }
  return response;
};

// Mock WebSocket for testing
export const createMockWebSocket = (overrides: Partial<any> = {}) => ({
  connect: jest.fn(),
  disconnect: jest.fn(),
  sendMessage: jest.fn(),
  isConnected: true,
  connectionStatus: {
    isConnected: true,
    hasConnection: true,
    status: 'connected' as const,
    reconnectAttempts: 0,
    lastError: null,
    fallbackActive: false
  },
  lastMessage: null,
  messageHistory: [],
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  ...overrides
});

// Mock user event for testing
export const createMockUserEvent = () => ({
  click: jest.fn(),
  type: jest.fn(),
  clear: jest.fn(),
  selectOptions: jest.fn(),
  upload: jest.fn(),
  hover: jest.fn(),
  unhover: jest.fn(),
  tab: jest.fn(),
  keyboard: jest.fn(),
  pointer: jest.fn(),
  setup: jest.fn().mockReturnValue({
    click: jest.fn(),
    type: jest.fn(),
    clear: jest.fn(),
    selectOptions: jest.fn(),
    upload: jest.fn(),
    hover: jest.fn(),
    unhover: jest.fn(),
    tab: jest.fn(),
    keyboard: jest.fn(),
    pointer: jest.fn()
  })
});