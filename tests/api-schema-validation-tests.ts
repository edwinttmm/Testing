/**
 * API Schema Validation Tests
 * 
 * Validates that API request/response schemas match expected TypeScript interfaces
 * and ensures data consistency between frontend and backend.
 */

import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { 
  Project, 
  ProjectCreate, 
  VideoFile, 
  TestSession, 
  GroundTruthAnnotation,
  Detection,
  BoundingBox,
  DashboardStats,
  ChartData,
  ApiError
} from '../ai-model-validation-platform/frontend/src/services/types';

// Initialize JSON Schema validator
const ajv = new Ajv({ allErrors: true });
addFormats(ajv);

// Define JSON Schemas for API validation
const projectSchema = {
  type: 'object',
  required: ['id', 'name', 'cameraModel', 'cameraView', 'signalType', 'createdAt', 'status'],
  properties: {
    id: { type: 'string', minLength: 1 },
    name: { type: 'string', minLength: 1, maxLength: 255 },
    description: { type: 'string', maxLength: 1000 },
    cameraModel: { type: 'string', minLength: 1 },
    cameraView: { 
      type: 'string',
      enum: ['Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior', 'Multi-angle']
    },
    signalType: {
      type: 'string',
      enum: ['GPIO', 'Network Packet', 'Serial', 'CAN Bus']
    },
    lensType: { type: 'string' },
    resolution: { type: 'string' },
    frameRate: { type: 'number', minimum: 1, maximum: 120 },
    createdAt: { type: 'string', format: 'date-time' },
    updatedAt: { type: 'string', format: 'date-time' },
    status: {
      type: 'string',
      enum: ['draft', 'active', 'testing', 'analysis', 'completed', 'archived']
    },
    testsCount: { type: 'number', minimum: 0 },
    accuracy: { type: 'number', minimum: 0, maximum: 1 },
    userId: { type: 'string' }
  },
  additionalProperties: true // Allow snake_case variants from API
};

const projectCreateSchema = {
  type: 'object',
  required: ['name', 'description', 'cameraModel', 'cameraView', 'signalType'],
  properties: {
    name: { type: 'string', minLength: 1, maxLength: 255 },
    description: { type: 'string', minLength: 1, maxLength: 1000 },
    cameraModel: { type: 'string', minLength: 1 },
    cameraView: { 
      type: 'string',
      enum: ['Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior', 'Multi-angle']
    },
    signalType: {
      type: 'string',
      enum: ['GPIO', 'Network Packet', 'Serial', 'CAN Bus']
    }
  },
  additionalProperties: false
};

const videoFileSchema = {
  type: 'object',
  required: ['id', 'projectId', 'filename', 'originalName', 'size', 'uploadedAt', 'url', 'status'],
  properties: {
    id: { type: 'string', minLength: 1 },
    projectId: { type: 'string', minLength: 1 },
    filename: { type: 'string', minLength: 1 },
    originalName: { type: 'string', minLength: 1 },
    name: { type: 'string' },
    size: { type: 'number', minimum: 0 },
    duration: { type: 'number', minimum: 0 },
    uploadedAt: { type: 'string', format: 'date-time' },
    createdAt: { type: 'string', format: 'date-time' },
    url: { type: 'string', format: 'uri' },
    status: {
      type: 'string',
      enum: ['uploading', 'processing', 'completed', 'failed']
    },
    groundTruthStatus: {
      type: 'string',
      enum: ['pending', 'processing', 'completed', 'failed']
    },
    groundTruthGenerated: { type: 'boolean' },
    detectionCount: { type: 'number', minimum: 0 },
    width: { type: 'number', minimum: 1 },
    height: { type: 'number', minimum: 1 },
    fps: { type: 'number', minimum: 1 },
    bitrate: { type: 'number', minimum: 0 },
    format: { type: 'string' },
    codec: { type: 'string' },
    thumbnailUrl: { type: 'string', format: 'uri' },
    metadata: { type: 'object' }
  },
  additionalProperties: true
};

const boundingBoxSchema = {
  type: 'object',
  required: ['x', 'y', 'width', 'height', 'label', 'confidence'],
  properties: {
    x: { type: 'number', minimum: 0 },
    y: { type: 'number', minimum: 0 },
    width: { type: 'number', minimum: 1 },
    height: { type: 'number', minimum: 1 },
    label: { type: 'string', minLength: 1 },
    confidence: { type: 'number', minimum: 0, maximum: 1 }
  },
  additionalProperties: false
};

const groundTruthAnnotationSchema = {
  type: 'object',
  required: ['id', 'videoId', 'detectionId', 'frameNumber', 'timestamp', 'vruType', 'boundingBox', 'validated', 'createdAt'],
  properties: {
    id: { type: 'string', minLength: 1 },
    videoId: { type: 'string', minLength: 1 },
    detectionId: { type: 'string', minLength: 1 },
    frameNumber: { type: 'number', minimum: 0 },
    timestamp: { type: 'number', minimum: 0 },
    vruType: {
      type: 'string',
      enum: ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair_user', 'scooter_rider']
    },
    boundingBox: boundingBoxSchema,
    occluded: { type: 'boolean' },
    truncated: { type: 'boolean' },
    difficult: { type: 'boolean' },
    notes: { type: 'string', maxLength: 1000 },
    annotator: { type: 'string' },
    validated: { type: 'boolean' },
    createdAt: { type: 'string', format: 'date-time' },
    updatedAt: { type: 'string', format: 'date-time' }
  },
  additionalProperties: false
};

const detectionSchema = {
  type: 'object',
  required: ['id', 'detectionId', 'timestamp', 'boundingBox', 'vruType', 'confidence', 'isGroundTruth', 'validated', 'createdAt'],
  properties: {
    id: { type: 'string', minLength: 1 },
    detectionId: { type: 'string', minLength: 1 },
    timestamp: { type: 'number', minimum: 0 },
    boundingBox: boundingBoxSchema,
    vruType: {
      type: 'string',
      enum: ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair_user', 'scooter_rider']
    },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
    isGroundTruth: { type: 'boolean' },
    notes: { type: 'string', maxLength: 1000 },
    validated: { type: 'boolean' },
    createdAt: { type: 'string', format: 'date-time' },
    updatedAt: { type: 'string', format: 'date-time' }
  },
  additionalProperties: false
};

const dashboardStatsSchema = {
  type: 'object',
  required: ['project_count', 'video_count', 'test_session_count', 'detection_event_count'],
  properties: {
    project_count: { type: 'number', minimum: 0 },
    video_count: { type: 'number', minimum: 0 },
    test_session_count: { type: 'number', minimum: 0 },
    detection_event_count: { type: 'number', minimum: 0 }
  },
  additionalProperties: true
};

const apiErrorSchema = {
  type: 'object',
  required: ['message', 'status'],
  properties: {
    message: { type: 'string', minLength: 1 },
    code: { type: 'string' },
    status: { type: 'number', minimum: 400, maximum: 599 },
    details: { type: 'object' }
  },
  additionalProperties: false
};

// Compile schemas
const validateProject = ajv.compile(projectSchema);
const validateProjectCreate = ajv.compile(projectCreateSchema);
const validateVideoFile = ajv.compile(videoFileSchema);
const validateBoundingBox = ajv.compile(boundingBoxSchema);
const validateGroundTruthAnnotation = ajv.compile(groundTruthAnnotationSchema);
const validateDetection = ajv.compile(detectionSchema);
const validateDashboardStats = ajv.compile(dashboardStatsSchema);
const validateApiError = ajv.compile(apiErrorSchema);

describe('API Schema Validation Tests', () => {
  describe('Project Schema Validation', () => {
    it('should validate valid project object', () => {
      const validProject: Project = {
        id: 'proj-123',
        name: 'Test Project',
        description: 'A test project',
        cameraModel: 'TestCam Pro',
        cameraView: 'Front-facing VRU',
        signalType: 'GPIO',
        lensType: '50mm',
        resolution: '1920x1080',
        frameRate: 30,
        createdAt: '2023-01-01T00:00:00Z',
        updatedAt: '2023-01-01T00:00:00Z',
        status: 'active',
        testsCount: 5,
        accuracy: 0.85,
        userId: 'user-123'
      };

      const isValid = validateProject(validProject);
      expect(isValid).toBe(true);
      expect(validateProject.errors).toBeNull();
    });

    it('should reject project with missing required fields', () => {
      const invalidProject = {
        name: 'Test Project'
        // Missing required fields
      };

      const isValid = validateProject(invalidProject);
      expect(isValid).toBe(false);
      expect(validateProject.errors).toBeDefined();
      expect(validateProject.errors!.length).toBeGreaterThan(0);
    });

    it('should reject project with invalid enum values', () => {
      const invalidProject: Partial<Project> = {
        id: 'proj-123',
        name: 'Test Project',
        description: 'Test',
        cameraModel: 'TestCam',
        cameraView: 'Invalid View' as any,
        signalType: 'Invalid Signal' as any,
        createdAt: '2023-01-01T00:00:00Z',
        status: 'invalid_status' as any
      };

      const isValid = validateProject(invalidProject);
      expect(isValid).toBe(false);
      expect(validateProject.errors).toBeDefined();
    });

    it('should validate project creation data', () => {
      const validProjectCreate: ProjectCreate = {
        name: 'New Project',
        description: 'A new test project',
        cameraModel: 'TestCam Pro',
        cameraView: 'Front-facing VRU',
        signalType: 'GPIO'
      };

      const isValid = validateProjectCreate(validProjectCreate);
      expect(isValid).toBe(true);
      expect(validateProjectCreate.errors).toBeNull();
    });

    it('should reject project creation with invalid data', () => {
      const invalidProjectCreate = {
        name: '', // Empty name should be invalid
        description: 'Valid description',
        cameraModel: 'TestCam',
        cameraView: 'Front-facing VRU',
        signalType: 'GPIO'
      };

      const isValid = validateProjectCreate(invalidProjectCreate);
      expect(isValid).toBe(false);
      expect(validateProjectCreate.errors).toBeDefined();
    });
  });

  describe('VideoFile Schema Validation', () => {
    it('should validate valid video file object', () => {
      const validVideoFile: VideoFile = {
        id: 'vid-123',
        projectId: 'proj-123',
        filename: 'test_video.mp4',
        originalName: 'test_video.mp4',
        size: 1024000,
        duration: 30,
        uploadedAt: '2023-01-01T00:00:00Z',
        url: 'https://example.com/video.mp4',
        status: 'completed',
        groundTruthStatus: 'completed',
        groundTruthGenerated: true,
        detectionCount: 15,
        width: 1920,
        height: 1080,
        fps: 30,
        bitrate: 5000000,
        format: 'mp4',
        codec: 'h264'
      };

      const isValid = validateVideoFile(validVideoFile);
      expect(isValid).toBe(true);
      expect(validateVideoFile.errors).toBeNull();
    });

    it('should reject video file with invalid URL', () => {
      const invalidVideoFile: Partial<VideoFile> = {
        id: 'vid-123',
        projectId: 'proj-123',
        filename: 'test_video.mp4',
        originalName: 'test_video.mp4',
        size: 1024000,
        uploadedAt: '2023-01-01T00:00:00Z',
        url: 'not-a-valid-url',
        status: 'completed'
      };

      const isValid = validateVideoFile(invalidVideoFile);
      expect(isValid).toBe(false);
      expect(validateVideoFile.errors).toBeDefined();
    });

    it('should reject video file with negative size', () => {
      const invalidVideoFile: Partial<VideoFile> = {
        id: 'vid-123',
        projectId: 'proj-123',
        filename: 'test_video.mp4',
        originalName: 'test_video.mp4',
        size: -1000, // Invalid negative size
        uploadedAt: '2023-01-01T00:00:00Z',
        url: 'https://example.com/video.mp4',
        status: 'completed'
      };

      const isValid = validateVideoFile(invalidVideoFile);
      expect(isValid).toBe(false);
      expect(validateVideoFile.errors).toBeDefined();
    });
  });

  describe('BoundingBox Schema Validation', () => {
    it('should validate valid bounding box', () => {
      const validBoundingBox: BoundingBox = {
        x: 100,
        y: 100,
        width: 80,
        height: 160,
        label: 'pedestrian',
        confidence: 0.85
      };

      const isValid = validateBoundingBox(validBoundingBox);
      expect(isValid).toBe(true);
      expect(validateBoundingBox.errors).toBeNull();
    });

    it('should reject bounding box with negative coordinates', () => {
      const invalidBoundingBox: BoundingBox = {
        x: -10, // Invalid negative x
        y: 100,
        width: 80,
        height: 160,
        label: 'pedestrian',
        confidence: 0.85
      };

      const isValid = validateBoundingBox(invalidBoundingBox);
      expect(isValid).toBe(false);
      expect(validateBoundingBox.errors).toBeDefined();
    });

    it('should reject bounding box with confidence out of range', () => {
      const invalidBoundingBox: BoundingBox = {
        x: 100,
        y: 100,
        width: 80,
        height: 160,
        label: 'pedestrian',
        confidence: 1.5 // Invalid confidence > 1
      };

      const isValid = validateBoundingBox(invalidBoundingBox);
      expect(isValid).toBe(false);
      expect(validateBoundingBox.errors).toBeDefined();
    });
  });

  describe('GroundTruthAnnotation Schema Validation', () => {
    it('should validate valid ground truth annotation', () => {
      const validAnnotation: GroundTruthAnnotation = {
        id: 'ann-123',
        videoId: 'vid-123',
        detectionId: 'det-123',
        frameNumber: 30,
        timestamp: 1.0,
        vruType: 'pedestrian',
        boundingBox: {
          x: 100, y: 100, width: 80, height: 160,
          label: 'pedestrian', confidence: 0.85
        },
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Clear pedestrian detection',
        annotator: 'user-123',
        validated: true,
        createdAt: '2023-01-01T00:00:00Z',
        updatedAt: '2023-01-01T00:00:00Z'
      };

      const isValid = validateGroundTruthAnnotation(validAnnotation);
      expect(isValid).toBe(true);
      expect(validateGroundTruthAnnotation.errors).toBeNull();
    });

    it('should reject annotation with invalid VRU type', () => {
      const invalidAnnotation: Partial<GroundTruthAnnotation> = {
        id: 'ann-123',
        videoId: 'vid-123',
        detectionId: 'det-123',
        frameNumber: 30,
        timestamp: 1.0,
        vruType: 'invalid_vru_type' as any,
        boundingBox: {
          x: 100, y: 100, width: 80, height: 160,
          label: 'pedestrian', confidence: 0.85
        },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        createdAt: '2023-01-01T00:00:00Z'
      };

      const isValid = validateGroundTruthAnnotation(invalidAnnotation);
      expect(isValid).toBe(false);
      expect(validateGroundTruthAnnotation.errors).toBeDefined();
    });
  });

  describe('Detection Schema Validation', () => {
    it('should validate valid detection object', () => {
      const validDetection: Detection = {
        id: 'det-123',
        detectionId: 'DET_PED_001',
        timestamp: 1.5,
        boundingBox: {
          x: 200, y: 150, width: 60, height: 120,
          label: 'cyclist', confidence: 0.92
        },
        vruType: 'cyclist',
        confidence: 0.92,
        isGroundTruth: false,
        notes: 'Cyclist moving left to right',
        validated: true,
        createdAt: '2023-01-01T00:00:00Z',
        updatedAt: '2023-01-01T00:00:00Z'
      };

      const isValid = validateDetection(validDetection);
      expect(isValid).toBe(true);
      expect(validateDetection.errors).toBeNull();
    });

    it('should reject detection with invalid confidence value', () => {
      const invalidDetection: Partial<Detection> = {
        id: 'det-123',
        detectionId: 'DET_PED_001',
        timestamp: 1.5,
        boundingBox: {
          x: 200, y: 150, width: 60, height: 120,
          label: 'cyclist', confidence: 0.92
        },
        vruType: 'cyclist',
        confidence: -0.1, // Invalid negative confidence
        isGroundTruth: false,
        validated: false,
        createdAt: '2023-01-01T00:00:00Z'
      };

      const isValid = validateDetection(invalidDetection);
      expect(isValid).toBe(false);
      expect(validateDetection.errors).toBeDefined();
    });
  });

  describe('DashboardStats Schema Validation', () => {
    it('should validate valid dashboard stats', () => {
      const validStats: DashboardStats = {
        project_count: 10,
        video_count: 50,
        test_session_count: 25,
        detection_event_count: 1000
      };

      const isValid = validateDashboardStats(validStats);
      expect(isValid).toBe(true);
      expect(validateDashboardStats.errors).toBeNull();
    });

    it('should reject dashboard stats with negative values', () => {
      const invalidStats: DashboardStats = {
        project_count: -5, // Invalid negative count
        video_count: 50,
        test_session_count: 25,
        detection_event_count: 1000
      };

      const isValid = validateDashboardStats(invalidStats);
      expect(isValid).toBe(false);
      expect(validateDashboardStats.errors).toBeDefined();
    });
  });

  describe('ApiError Schema Validation', () => {
    it('should validate valid API error', () => {
      const validError: ApiError = {
        message: 'Resource not found',
        code: 'RESOURCE_NOT_FOUND',
        status: 404,
        details: { resource: 'project', id: 'proj-123' }
      };

      const isValid = validateApiError(validError);
      expect(isValid).toBe(true);
      expect(validateApiError.errors).toBeNull();
    });

    it('should reject API error with invalid status code', () => {
      const invalidError: ApiError = {
        message: 'Invalid error',
        status: 200, // Status 200 is not an error status
        code: 'INVALID'
      };

      const isValid = validateApiError(invalidError);
      expect(isValid).toBe(false);
      expect(validateApiError.errors).toBeDefined();
    });

    it('should reject API error with empty message', () => {
      const invalidError: Partial<ApiError> = {
        message: '', // Empty message should be invalid
        status: 400,
        code: 'BAD_REQUEST'
      };

      const isValid = validateApiError(invalidError);
      expect(isValid).toBe(false);
      expect(validateApiError.errors).toBeDefined();
    });
  });

  describe('Schema Compatibility Tests', () => {
    it('should handle API response with snake_case fields', () => {
      // Simulate API response with snake_case fields
      const apiResponse = {
        id: 'proj-123',
        name: 'Test Project',
        description: 'Test',
        camera_model: 'TestCam', // snake_case
        camera_view: 'Front-facing VRU', // snake_case
        signal_type: 'GPIO', // snake_case
        created_at: '2023-01-01T00:00:00Z', // snake_case
        status: 'active'
      };

      // Should still validate with additionalProperties: true
      const isValid = validateProject(apiResponse);
      expect(isValid).toBe(true);
    });

    it('should validate arrays of objects', () => {
      const projectArray: Project[] = [
        {
          id: 'proj-1',
          name: 'Project 1',
          description: 'Test project 1',
          cameraModel: 'TestCam',
          cameraView: 'Front-facing VRU',
          signalType: 'GPIO',
          status: 'active',
          createdAt: '2023-01-01T00:00:00Z'
        },
        {
          id: 'proj-2',
          name: 'Project 2',
          description: 'Test project 2',
          cameraModel: 'TestCam2',
          cameraView: 'Rear-facing VRU',
          signalType: 'CAN Bus',
          status: 'draft',
          createdAt: '2023-01-01T00:00:00Z'
        }
      ];

      const arraySchema = {
        type: 'array',
        items: projectSchema
      };

      const validateProjectArray = ajv.compile(arraySchema);
      const isValid = validateProjectArray(projectArray);

      expect(isValid).toBe(true);
      expect(validateProjectArray.errors).toBeNull();
    });

    it('should validate nested object schemas', () => {
      const nestedObject = {
        project: {
          id: 'proj-123',
          name: 'Test Project',
          description: 'Test',
          cameraModel: 'TestCam',
          cameraView: 'Front-facing VRU',
          signalType: 'GPIO',
          status: 'active',
          createdAt: '2023-01-01T00:00:00Z'
        },
        videos: [
          {
            id: 'vid-123',
            projectId: 'proj-123',
            filename: 'test.mp4',
            originalName: 'test.mp4',
            size: 1000,
            uploadedAt: '2023-01-01T00:00:00Z',
            url: 'https://example.com/test.mp4',
            status: 'completed'
          }
        ]
      };

      const nestedSchema = {
        type: 'object',
        properties: {
          project: projectSchema,
          videos: {
            type: 'array',
            items: videoFileSchema
          }
        },
        required: ['project', 'videos']
      };

      const validateNested = ajv.compile(nestedSchema);
      const isValid = validateNested(nestedObject);

      expect(isValid).toBe(true);
      expect(validateNested.errors).toBeNull();
    });
  });

  describe('Custom Validation Rules', () => {
    beforeAll(() => {
      // Add custom format for detection IDs
      ajv.addFormat('detectionId', {
        type: 'string',
        validate: (data: string) => /^DET_[A-Z]{3}_\d{4}$/.test(data)
      });
    });

    it('should validate custom detection ID format', () => {
      const customSchema = {
        type: 'string',
        format: 'detectionId'
      };

      const validateDetectionId = ajv.compile(customSchema);

      expect(validateDetectionId('DET_PED_0001')).toBe(true);
      expect(validateDetectionId('DET_CYC_0042')).toBe(true);
      expect(validateDetectionId('invalid-id')).toBe(false);
      expect(validateDetectionId('DET_PED_999')).toBe(false); // Too short
    });

    it('should validate coordinate ranges for bounding boxes', () => {
      const customBoundingBoxSchema = {
        type: 'object',
        required: ['x', 'y', 'width', 'height', 'label', 'confidence'],
        properties: {
          x: { type: 'number', minimum: 0, maximum: 3840 }, // Max 4K width
          y: { type: 'number', minimum: 0, maximum: 2160 }, // Max 4K height
          width: { type: 'number', minimum: 1, maximum: 3840 },
          height: { type: 'number', minimum: 1, maximum: 2160 },
          label: { type: 'string', minLength: 1 },
          confidence: { type: 'number', minimum: 0, maximum: 1 }
        }
      };

      const validateCustomBoundingBox = ajv.compile(customBoundingBoxSchema);

      const validBox = {
        x: 100, y: 100, width: 80, height: 160,
        label: 'pedestrian', confidence: 0.85
      };

      const invalidBox = {
        x: 5000, y: 100, width: 80, height: 160, // x exceeds max
        label: 'pedestrian', confidence: 0.85
      };

      expect(validateCustomBoundingBox(validBox)).toBe(true);
      expect(validateCustomBoundingBox(invalidBox)).toBe(false);
    });
  });
});

// Helper function to format validation errors for debugging
export function formatValidationErrors(validator: Ajv.ValidateFunction): string[] {
  if (!validator.errors) return [];
  
  return validator.errors.map(error => 
    `${error.instancePath || 'root'}: ${error.message}`
  );
}

// Export validators for use in other test files
export {
  validateProject,
  validateProjectCreate,
  validateVideoFile,
  validateBoundingBox,
  validateGroundTruthAnnotation,
  validateDetection,
  validateDashboardStats,
  validateApiError
};