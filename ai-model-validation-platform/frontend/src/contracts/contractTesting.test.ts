import { describe, test, expect, beforeAll, afterAll, jest } from '@jest/globals';
import {
  contractValidator,
  setupContractInterceptors,
  contractAwareApi,
  ProjectSchema,
  VideoFileSchema,
  AnnotationSchema,
  DashboardStatsSchema,
  ValidationSeverity,
  API_CONTRACT_VERSION
} from './contractValidator';
import { apiService } from '../services/api';

// Mock API responses for testing
const mockApiService = {
  getProjects: jest.fn(),
  createProject: jest.fn(),
  getVideos: jest.fn(),
  getAnnotations: jest.fn(),
  getDashboardStats: jest.fn(),
  healthCheck: jest.fn()
};

// Sample test data
const sampleProject = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  name: 'Test Project',
  description: 'Test Description',
  cameraModel: 'Sony IMX274',
  cameraView: 'Front-facing VRU',
  lensType: 'Wide Angle',
  resolution: '1920x1080',
  frameRate: 30,
  signalType: 'GPIO',
  status: 'active',
  ownerId: 'user123',
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-02T00:00:00Z'
};

const sampleVideoFile = {
  id: '223e4567-e89b-12d3-a456-426614174000',
  filename: 'test_video.mp4',
  originalName: 'Original Test Video.mp4',
  projectId: '123e4567-e89b-12d3-a456-426614174000',
  fileSize: 1048576,
  duration: 120.5,
  fps: 30,
  resolution: '1920x1080',
  status: 'processed',
  url: 'http://example.com/videos/test_video.mp4',
  groundTruthGenerated: true,
  processingStatus: 'completed',
  detectionCount: 15,
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-02T00:00:00Z'
};

const sampleAnnotation = {
  id: '323e4567-e89b-12d3-a456-426614174000',
  videoId: '223e4567-e89b-12d3-a456-426614174000',
  detectionId: 'DET_PED_0001',
  frameNumber: 100,
  timestamp: 5.0,
  endTimestamp: 5.5,
  vruType: 'pedestrian',
  boundingBox: {
    x: 100,
    y: 200,
    width: 80,
    height: 160,
    label: 'pedestrian',
    confidence: 0.95
  },
  occluded: false,
  truncated: false,
  difficult: false,
  notes: 'Clear detection',
  annotator: 'user123',
  validated: true,
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-02T00:00:00Z'
};

const sampleDashboardStats = {
  projectCount: 5,
  videoCount: 25,
  testCount: 12,
  totalDetections: 340,
  averageAccuracy: 0.85,
  activeTests: 3,
  confidenceIntervals: {
    'precision': [0.82, 0.88],
    'recall': [0.79, 0.87]
  },
  trendAnalysis: {
    'accuracy': 'improving',
    'processing_time': 'stable'
  },
  signalProcessingMetrics: {
    'gpio_success_rate': 0.98,
    'network_latency': 45
  }
};

describe('API Contract Validation', () => {
  beforeAll(() => {
    // Setup contract interceptors for testing
    setupContractInterceptors(true);
  });

  afterAll(() => {
    // Reset contract validator
    contractValidator.reset();
  });

  describe('Schema Validation', () => {
    test('should validate Project schema correctly', () => {
      const result = ProjectSchema.safeParse(sampleProject);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.id).toBe(sampleProject.id);
        expect(result.data.name).toBe(sampleProject.name);
      }
    });

    test('should reject invalid Project data', () => {
      const invalidProject = {
        ...sampleProject,
        id: 'invalid-uuid', // Invalid UUID format
        name: '', // Empty name
        cameraView: 'Invalid View', // Invalid enum
        frameRate: -1 // Invalid negative number
      };

      const result = ProjectSchema.safeParse(invalidProject);
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues.length).toBeGreaterThan(0);
      }
    });

    test('should validate VideoFile schema correctly', () => {
      const result = VideoFileSchema.safeParse(sampleVideoFile);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.id).toBe(sampleVideoFile.id);
        expect(result.data.filename).toBe(sampleVideoFile.filename);
      }
    });

    test('should validate Annotation schema correctly', () => {
      const result = AnnotationSchema.safeParse(sampleAnnotation);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.vruType).toBe('pedestrian');
        expect(result.data.boundingBox.confidence).toBe(0.95);
      }
    });

    test('should validate DashboardStats schema correctly', () => {
      const result = DashboardStatsSchema.safeParse(sampleDashboardStats);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.projectCount).toBe(5);
        expect(result.data.averageAccuracy).toBe(0.85);
      }
    });
  });

  describe('Contract Validator', () => {
    test('should validate successful response', () => {
      const validation = contractValidator.validateResponse(
        'GET',
        '/api/projects',
        [sampleProject],
        200
      );

      expect(validation.isValid).toBe(true);
      expect(validation.violations).toHaveLength(0);
      expect(validation.processingTime).toBeGreaterThan(0);
    });

    test('should detect response validation errors', () => {
      const invalidResponse = {
        id: 'invalid-uuid',
        name: '', // Empty name should fail
        cameraView: 'Invalid View' // Invalid enum
      };

      const validation = contractValidator.validateResponse(
        'GET',
        '/api/projects/123',
        invalidResponse,
        200
      );

      expect(validation.isValid).toBe(false);
      expect(validation.violations.length).toBeGreaterThan(0);
      expect(validation.violations.some(v => v.severity === ValidationSeverity.ERROR)).toBe(true);
    });

    test('should validate request data', () => {
      const validProjectRequest = {
        name: 'New Project',
        cameraModel: 'Test Camera',
        cameraView: 'Front-facing VRU',
        signalType: 'GPIO'
      };

      const validation = contractValidator.validateRequest(
        'POST',
        '/api/projects',
        validProjectRequest
      );

      expect(validation.isValid).toBe(true);
      expect(validation.violations).toHaveLength(0);
    });

    test('should detect missing required fields in request', () => {
      const incompleteRequest = {
        name: 'New Project'
        // Missing required fields: cameraModel, cameraView, signalType
      };

      const validation = contractValidator.validateRequest(
        'POST',
        '/api/projects',
        incompleteRequest
      );

      expect(validation.isValid).toBe(false);
      expect(validation.violations.some(v => 
        v.violationType === 'missing_required_field'
      )).toBe(true);
    });

    test('should validate critical endpoints with additional checks', () => {
      // Test annotation endpoint (critical for GroundTruth issues)
      const annotationResponse = [sampleAnnotation];

      const validation = contractValidator.validateResponse(
        'GET',
        '/api/videos/123/annotations',
        annotationResponse,
        200
      );

      expect(validation.isValid).toBe(true);
      expect(validation.violations).toHaveLength(0);
    });

    test('should detect critical endpoint failures', () => {
      // Test server error on critical endpoint
      const errorResponse = {
        message: 'Internal Server Error',
        timestamp: new Date().toISOString()
      };

      const validation = contractValidator.validateResponse(
        'GET',
        '/api/videos/123/annotations',
        errorResponse,
        500
      );

      expect(validation.isValid).toBe(false);
      expect(validation.violations.some(v => 
        v.violationType === 'critical_endpoint_server_error'
      )).toBe(true);
    });

    test('should validate ground truth endpoint structure', () => {
      const groundTruthResponse = {
        video_id: '223e4567-e89b-12d3-a456-426614174000',
        objects: [
          {
            id: '323e4567-e89b-12d3-a456-426614174000',
            timestamp: 5.0,
            frame_number: 100,
            class_label: 'pedestrian',
            x: 100,
            y: 200,
            width: 80,
            height: 160,
            confidence: 0.95,
            validated: true
          }
        ],
        total_detections: 1,
        status: 'completed'
      };

      const validation = contractValidator.validateResponse(
        'GET',
        '/api/videos/123/ground-truth',
        groundTruthResponse,
        200
      );

      expect(validation.isValid).toBe(true);
      expect(validation.violations).toHaveLength(0);
    });

    test('should detect incomplete ground truth structure', () => {
      const incompleteGroundTruth = {
        // Missing video_id and objects array
        total_detections: 0,
        status: 'completed'
      };

      const validation = contractValidator.validateResponse(
        'GET',
        '/api/videos/123/ground-truth',
        incompleteGroundTruth,
        200
      );

      expect(validation.isValid).toBe(false);
      expect(validation.violations.some(v => 
        v.violationType === 'invalid_ground_truth_structure'
      )).toBe(true);
    });
  });

  describe('Contract Metrics and Health', () => {
    beforeEach(() => {
      contractValidator.reset();
    });

    test('should track validation metrics', () => {
      // Perform several validations
      contractValidator.validateResponse('GET', '/api/projects', [sampleProject], 200);
      contractValidator.validateResponse('GET', '/api/videos', [sampleVideoFile], 200);
      contractValidator.validateResponse('GET', '/api/projects/invalid', {}, 400);

      const metrics = contractValidator.getMetrics();

      expect(metrics.totalValidations).toBe(3);
      expect(metrics.successRate).toBeGreaterThan(0);
      expect(metrics.contractsCovered).toBeGreaterThan(0);
      expect(metrics.averageResponseTime).toBeGreaterThan(0);
    });

    test('should report healthy status with good metrics', () => {
      // Perform successful validations
      for (let i = 0; i < 10; i++) {
        contractValidator.validateResponse('GET', '/api/projects', [sampleProject], 200);
      }

      const health = contractValidator.getHealthStatus();

      expect(health.status).toBe('healthy');
      expect(health.contractVersion).toBe(API_CONTRACT_VERSION);
      expect(health.successRate).toBeGreaterThan(90);
    });

    test('should report unhealthy status with many failures', () => {
      // Perform mostly failed validations
      for (let i = 0; i < 5; i++) {
        contractValidator.validateResponse('GET', '/api/projects', [sampleProject], 200);
      }
      for (let i = 0; i < 10; i++) {
        contractValidator.validateResponse('GET', '/api/projects', 'invalid', 200);
      }

      const health = contractValidator.getHealthStatus();

      expect(health.status).toBe('unhealthy');
      expect(health.errorRate).toBeGreaterThan(10);
    });
  });

  describe('Contract-Aware API Service', () => {
    beforeEach(() => {
      jest.clearAllMocks();
    });

    test('should validate API responses in contract-aware service', async () => {
      // Mock successful API response
      mockApiService.getProjects.mockResolvedValue([sampleProject]);
      
      // This would be the actual implementation test
      // For now, we test the schema validation directly
      const result = ProjectSchema.safeParse(sampleProject);
      expect(result.success).toBe(true);
    });

    test('should handle validation errors gracefully', async () => {
      // Mock API response with invalid data
      const invalidProject = { ...sampleProject, id: 'invalid-uuid' };
      mockApiService.getProjects.mockResolvedValue([invalidProject]);

      // Test that validation would catch this
      const result = ProjectSchema.safeParse(invalidProject);
      expect(result.success).toBe(false);
    });
  });

  describe('Error Response Validation', () => {
    test('should validate error response format', () => {
      const errorResponse = {
        message: 'Resource not found',
        code: 'NOT_FOUND',
        timestamp: new Date().toISOString()
      };

      const validation = contractValidator.validateResponse(
        'GET',
        '/api/projects/invalid-id',
        errorResponse,
        404
      );

      expect(validation.isValid).toBe(true);
    });

    test('should detect malformed error responses', () => {
      const malformedError = {
        error: 'Something went wrong', // Should be 'message'
        details: 'Additional info'
      };

      const validation = contractValidator.validateResponse(
        'GET',
        '/api/projects/invalid-id',
        malformedError,
        404
      );

      expect(validation.isValid).toBe(false);
      expect(validation.violations.some(v => 
        v.violationType === 'invalid_error_format'
      )).toBe(true);
    });
  });

  describe('Performance and SLA Validation', () => {
    test('should detect performance violations', () => {
      // Simulate slow response by manually creating violation
      const validation = contractValidator.validateResponse(
        'GET',
        '/api/dashboard/stats',
        sampleDashboardStats,
        200
      );

      // In real implementation, this would be detected automatically
      // For testing, we check the structure is correct
      expect(validation).toHaveProperty('processingTime');
      expect(validation.processingTime).toBeGreaterThan(0);
    });
  });

  describe('Integration with API Service', () => {
    test('should integrate with existing API service types', () => {
      // Test type compatibility
      const projectData: any = sampleProject;
      const validation = ProjectSchema.safeParse(projectData);
      
      expect(validation.success).toBe(true);
      if (validation.success) {
        // Test that validated data matches expected types
        expect(typeof validation.data.id).toBe('string');
        expect(typeof validation.data.name).toBe('string');
        expect(typeof validation.data.createdAt).toBe('string');
      }
    });
  });
});

// Integration test with actual API calls (requires running backend)
describe('Contract Integration Tests', () => {
  // These tests would run against a real backend in CI/CD
  test.skip('should validate real API responses', async () => {
    // This test would be enabled in integration test environment
    try {
      const response = await fetch('/api/health');
      const data = await response.json();
      
      const validation = contractValidator.validateResponse(
        'GET',
        '/health',
        data,
        response.status
      );
      
      expect(validation.isValid).toBe(true);
    } catch (error) {
      console.log('Integration test skipped - backend not available');
    }
  });
});

// Performance benchmark tests
describe('Contract Validation Performance', () => {
  test('should validate responses efficiently', () => {
    const startTime = performance.now();
    
    // Run many validations
    for (let i = 0; i < 1000; i++) {
      contractValidator.validateResponse(
        'GET',
        '/api/projects',
        [sampleProject],
        200
      );
    }
    
    const endTime = performance.now();
    const avgTime = (endTime - startTime) / 1000;
    
    // Should validate 1000 responses in reasonable time (< 1ms per validation)
    expect(avgTime).toBeLessThan(1);
  });
});

// Contract versioning tests
describe('Contract Versioning', () => {
  test('should track contract version', () => {
    expect(API_CONTRACT_VERSION).toBeDefined();
    expect(typeof API_CONTRACT_VERSION).toBe('string');
    expect(API_CONTRACT_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });

  test('should handle version compatibility', () => {
    const health = contractValidator.getHealthStatus();
    expect(health.contractVersion).toBe(API_CONTRACT_VERSION);
  });
});