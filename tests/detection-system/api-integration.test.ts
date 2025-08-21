import axios from 'axios';
import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';
import { DetectionConfig } from '../../ai-model-validation-platform/frontend/src/services/detectionService';

// Mock axios for controlled testing
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('API Integration - Detection System', () => {
  const mockVideoId = 'test-video-123';
  const mockProjectId = 'test-project-456';
  const mockApiInstance = {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
    defaults: { baseURL: 'http://localhost:8000', timeout: 30000 },
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() }
    },
    request: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockedAxios.create.mockReturnValue(mockApiInstance as any);
  });

  describe('Detection Pipeline API', () => {
    const mockConfig: DetectionConfig = {
      confidenceThreshold: 0.7,
      nmsThreshold: 0.5,
      modelName: 'yolov8n',
      targetClasses: ['person', 'bicycle']
    };

    it('should call detection pipeline with correct parameters', async () => {
      const mockResponse = {
        success: true,
        detections: [
          {
            id: 'det-1',
            detectionId: 'det-1',
            frame: 0,
            timestamp: 0,
            vruType: 'pedestrian',
            x: 100,
            y: 100,
            width: 50,
            height: 100,
            label: 'person',
            confidence: 0.85
          }
        ],
        processingTime: 1500
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.runDetectionPipeline(mockVideoId, mockConfig);

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'post',
        url: '/api/detection/pipeline/run',
        data: {
          video_id: mockVideoId,
          confidence_threshold: 0.7,
          nms_threshold: 0.5,
          model_name: 'yolov8n',
          target_classes: ['person', 'bicycle']
        }
      });

      expect(result).toEqual(mockResponse);
    });

    it('should handle detection pipeline errors', async () => {
      const errorResponse = {
        response: {
          status: 500,
          data: {
            message: 'Detection pipeline failed: model not found'
          }
        }
      };

      mockApiInstance.request.mockRejectedValue(errorResponse);

      await expect(apiService.runDetectionPipeline(mockVideoId, mockConfig))
        .rejects.toMatchObject({
          status: 500,
          message: 'Detection pipeline failed: model not found'
        });
    });

    it('should handle network timeout errors', async () => {
      mockApiInstance.request.mockRejectedValue({
        code: 'ECONNABORTED',
        message: 'timeout of 30000ms exceeded'
      });

      await expect(apiService.runDetectionPipeline(mockVideoId, mockConfig))
        .rejects.toMatchObject({
          code: 'TIMEOUT_ERROR',
          message: 'Request timeout - please try again'
        });
    });

    it('should handle network connection errors', async () => {
      mockApiInstance.request.mockRejectedValue({
        request: {},
        message: 'Network Error'
      });

      await expect(apiService.runDetectionPipeline(mockVideoId, mockConfig))
        .rejects.toMatchObject({
          code: 'NETWORK_ERROR',
          message: 'Network error - please check your connection'
        });
    });
  });

  describe('Available Models API', () => {
    it('should fetch available detection models', async () => {
      const mockResponse = {
        models: ['yolov8n', 'yolov8s', 'yolov8m', 'yolov8l'],
        default: 'yolov8n',
        recommended: 'yolov8s'
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.getAvailableModels();

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'get',
        url: '/api/detection/models/available'
      });

      expect(result).toEqual(mockResponse);
    });

    it('should handle empty models response', async () => {
      mockApiInstance.request.mockResolvedValue({ 
        data: { models: [], default: '', recommended: '' } 
      });

      const result = await apiService.getAvailableModels();

      expect(result.models).toHaveLength(0);
    });
  });

  describe('Video API Integration', () => {
    it('should fetch videos with enhanced data', async () => {
      const mockVideos = [
        {
          id: 'video-1',
          filename: 'test-video-1.mp4',
          original_name: 'Test Video 1',
          file_size: 1024000,
          created_at: '2023-01-01T00:00:00Z',
          processing_status: 'completed',
          url: '/uploads/test-video-1.mp4'
        },
        {
          id: 'video-2',
          filename: 'test-video-2.mp4',
          original_name: 'Test Video 2',
          file_size: 2048000,
          created_at: '2023-01-02T00:00:00Z',
          processing_status: 'processing',
          url: ''  // Missing URL should be constructed
        }
      ];

      mockApiInstance.get.mockResolvedValue({ data: mockVideos });

      const result = await apiService.getVideos(mockProjectId);

      expect(mockApiInstance.get).toHaveBeenCalledWith(
        expect.stringContaining(`/api/projects/${mockProjectId}/videos`)
      );

      // Check URL enhancement
      expect(result[0].url).toBe('http://localhost:8000/uploads/test-video-1.mp4');
      expect(result[1].url).toBe('http://localhost:8000/uploads/test-video-2.mp4');
      
      // Check status mapping
      expect(result[0].status).toBe('completed');
      expect(result[1].status).toBe('processing');
    });

    it('should handle video upload with progress tracking', async () => {
      const mockFile = new File(['video content'], 'test.mp4', { type: 'video/mp4' });
      const mockResponse = {
        id: 'uploaded-video-123',
        filename: 'test.mp4',
        originalName: 'test.mp4',
        fileSize: 1024,
        status: 'processing'
      };

      mockApiInstance.post.mockResolvedValue({ data: mockResponse });

      const progressCallback = jest.fn();
      const result = await apiService.uploadVideo(mockProjectId, mockFile, progressCallback);

      expect(mockApiInstance.post).toHaveBeenCalledWith(
        `/api/projects/${mockProjectId}/videos`,
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: expect.any(Function)
        })
      );

      expect(result).toEqual(mockResponse);
    });

    it('should handle upload progress events', async () => {
      const mockFile = new File(['video content'], 'test.mp4', { type: 'video/mp4' });
      const progressCallback = jest.fn();

      mockApiInstance.post.mockImplementation((url, data, config) => {
        // Simulate progress event
        if (config?.onUploadProgress) {
          config.onUploadProgress({ loaded: 512, total: 1024 });
        }
        return Promise.resolve({ data: { id: 'test' } });
      });

      await apiService.uploadVideo(mockProjectId, mockFile, progressCallback);

      expect(progressCallback).toHaveBeenCalledWith(50);
    });

    it('should handle central video upload', async () => {
      const mockFile = new File(['video content'], 'test.mp4', { type: 'video/mp4' });
      const mockResponse = {
        id: 'central-video-123',
        filename: 'test.mp4',
        originalName: 'test.mp4',
        fileSize: 1024,
        status: 'completed'
      };

      mockApiInstance.post.mockResolvedValue({ data: mockResponse });

      const result = await apiService.uploadVideoCentral(mockFile);

      expect(mockApiInstance.post).toHaveBeenCalledWith(
        '/api/videos',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      );

      expect(result).toEqual(mockResponse);
    });

    it('should get all videos with filtering', async () => {
      const mockResponse = {
        videos: [
          { id: 'video-1', filename: 'test1.mp4', projectId: null },
          { id: 'video-2', filename: 'test2.mp4', projectId: 'project-1' }
        ],
        total: 2
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.getAllVideos(true, 0, 50);

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'get',
        url: '/api/videos',
        params: { unassigned: true, skip: 0, limit: 50 }
      });

      expect(result).toEqual(mockResponse);
    });

    it('should filter out invalid videos', async () => {
      const mockResponse = {
        videos: [
          { id: 'valid-video', filename: 'valid.mp4' },
          { id: '', filename: 'invalid.mp4' }, // Invalid - empty ID
          { id: null, filename: 'null-id.mp4' }, // Invalid - null ID
          { id: 'no-filename' }, // Invalid - no filename
          { id: 'valid-video-2', filename: 'valid2.mp4' }
        ],
        total: 5
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.getAllVideos();

      // Should filter out invalid videos
      expect(result.videos).toHaveLength(2);
      expect(result.total).toBe(2);
      expect(result.videos[0].id).toBe('valid-video');
      expect(result.videos[1].id).toBe('valid-video-2');
    });
  });

  describe('Annotation API Integration', () => {
    const mockAnnotation = {
      detectionId: 'det-123',
      frameNumber: 5,
      timestamp: 166.67,
      vruType: 'pedestrian',
      boundingBox: {
        x: 100,
        y: 100,
        width: 50,
        height: 100,
        label: 'person',
        confidence: 0.85
      },
      occluded: false,
      truncated: false,
      difficult: false,
      notes: 'Clear detection',
      annotator: 'test-user',
      validated: false
    };

    it('should get annotations for a video', async () => {
      const mockResponse = [
        {
          id: 'ann-1',
          videoId: mockVideoId,
          ...mockAnnotation
        }
      ];

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.getAnnotations(mockVideoId);

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'get',
        url: `/api/videos/${mockVideoId}/annotations`
      });

      expect(result).toEqual(mockResponse);
    });

    it('should create new annotation with correct format', async () => {
      const mockResponse = {
        id: 'new-ann-123',
        videoId: mockVideoId,
        ...mockAnnotation,
        createdAt: '2023-01-01T00:00:00Z',
        updatedAt: '2023-01-01T00:00:00Z'
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.createAnnotation(mockVideoId, mockAnnotation);

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'post',
        url: `/api/videos/${mockVideoId}/annotations`,
        data: {
          detection_id: mockAnnotation.detectionId,
          frame_number: mockAnnotation.frameNumber,
          timestamp: mockAnnotation.timestamp,
          vru_type: mockAnnotation.vruType,
          bounding_box: mockAnnotation.boundingBox,
          occluded: mockAnnotation.occluded,
          truncated: mockAnnotation.truncated,
          difficult: mockAnnotation.difficult,
          notes: mockAnnotation.notes,
          annotator: mockAnnotation.annotator,
          validated: mockAnnotation.validated
        }
      });

      expect(result).toEqual(mockResponse);
    });

    it('should update annotation', async () => {
      const annotationId = 'ann-123';
      const updates = { validated: true, notes: 'Updated notes' };
      const mockResponse = {
        id: annotationId,
        ...mockAnnotation,
        ...updates,
        updatedAt: '2023-01-02T00:00:00Z'
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.updateAnnotation(annotationId, updates);

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'put',
        url: `/api/annotations/${annotationId}`,
        data: expect.objectContaining({
          validated: true,
          notes: 'Updated notes'
        })
      });

      expect(result).toEqual(mockResponse);
    });

    it('should delete annotation', async () => {
      const annotationId = 'ann-123';

      mockApiInstance.request.mockResolvedValue({ data: null });

      await apiService.deleteAnnotation(annotationId);

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'delete',
        url: `/api/annotations/${annotationId}`
      });
    });

    it('should validate annotation', async () => {
      const annotationId = 'ann-123';
      const mockResponse = {
        id: annotationId,
        ...mockAnnotation,
        validated: true
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.validateAnnotation(annotationId, true);

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'patch',
        url: `/api/annotations/${annotationId}/validate`,
        data: { validated: true }
      });

      expect(result).toEqual(mockResponse);
    });

    it('should export annotations', async () => {
      const mockBlob = new Blob(['annotation data'], { type: 'application/json' });

      mockApiInstance.get.mockResolvedValue({ data: mockBlob });

      const result = await apiService.exportAnnotations(mockVideoId, 'json');

      expect(mockApiInstance.get).toHaveBeenCalledWith(
        `/api/videos/${mockVideoId}/annotations/export`,
        {
          params: { format: 'json' },
          responseType: 'blob'
        }
      );

      expect(result).toBe(mockBlob);
    });

    it('should import annotations', async () => {
      const mockFile = new File(['annotation data'], 'annotations.json', { 
        type: 'application/json' 
      });
      const mockResponse = {
        imported: 10,
        errors: []
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.importAnnotations(mockVideoId, mockFile, 'json');

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'post',
        url: `/api/videos/${mockVideoId}/annotations/import`,
        data: expect.any(FormData),
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      expect(result).toEqual(mockResponse);
    });
  });

  describe('Ground Truth API Integration', () => {
    it('should fetch ground truth data with proper transformation', async () => {
      const mockGroundTruth = {
        video_id: mockVideoId,
        objects: [
          {
            id: 'gt-1',
            detection_id: 'det-1',
            frame_number: 0,
            timestamp: 0,
            class_label: 'person',
            vru_type: 'pedestrian',
            bounding_box: {
              x: 100,
              y: 100,
              width: 50,
              height: 100
            },
            confidence: 0.95,
            validated: true
          }
        ],
        total_detections: 1,
        status: 'completed'
      };

      mockApiInstance.get.mockResolvedValue({ data: mockGroundTruth });

      const result = await apiService.getGroundTruth(mockVideoId);

      expect(mockApiInstance.get).toHaveBeenCalledWith(
        `/api/videos/${mockVideoId}/ground-truth`
      );

      expect(result.objects[0]).toMatchObject({
        boundingBox: {
          x: 100,
          y: 100,
          width: 50,
          height: 100,
          confidence: 0.95,
          label: 'person'
        },
        vruType: 'pedestrian',
        detectionId: 'det-1',
        frameNumber: 0,
        timestamp: 0,
        validated: true
      });
    });

    it('should handle missing ground truth data', async () => {
      mockApiInstance.get.mockRejectedValue({
        response: { status: 404, data: 'Not found' }
      });

      const result = await apiService.getGroundTruth(mockVideoId);

      expect(result).toMatchObject({
        video_id: mockVideoId,
        objects: [],
        total_detections: 0,
        status: 'error',
        message: 'Failed to load ground truth data'
      });
    });

    it('should handle malformed ground truth objects', async () => {
      const mockGroundTruth = {
        video_id: mockVideoId,
        objects: [
          {
            // Missing required fields - should get defaults
            class_label: 'person'
          },
          {
            // Partial data
            detection_id: 'det-2',
            confidence: 0.8
          }
        ],
        total_detections: 2,
        status: 'completed'
      };

      mockApiInstance.get.mockResolvedValue({ data: mockGroundTruth });

      const result = await apiService.getGroundTruth(mockVideoId);

      // Should provide default values for missing fields
      expect(result.objects[0]).toMatchObject({
        boundingBox: {
          x: 0,
          y: 0,
          width: 100,
          height: 100,
          confidence: 1.0,
          label: 'person'
        },
        vruType: 'pedestrian',
        frameNumber: 0,
        timestamp: 0,
        validated: false,
        occluded: false,
        truncated: false,
        difficult: false
      });
    });

    it('should map class labels to VRU types correctly', async () => {
      const mockGroundTruth = {
        video_id: mockVideoId,
        objects: [
          { class_label: 'person' },
          { class_label: 'bicycle' },
          { class_label: 'motorcycle' },
          { class_label: 'unknown_class' }
        ],
        total_detections: 4,
        status: 'completed'
      };

      mockApiInstance.get.mockResolvedValue({ data: mockGroundTruth });

      const result = await apiService.getGroundTruth(mockVideoId);

      expect(result.objects[0].vruType).toBe('pedestrian');
      expect(result.objects[1].vruType).toBe('cyclist');
      expect(result.objects[2].vruType).toBe('motorcyclist');
      expect(result.objects[3].vruType).toBe('pedestrian'); // Default fallback
    });
  });

  describe('Health Check and Connectivity', () => {
    it('should perform health check successfully', async () => {
      const mockResponse = {
        status: 'healthy',
        environment: 'development',
        timestamp: '2023-01-01T00:00:00Z'
      };

      mockApiInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await apiService.healthCheck();

      expect(mockApiInstance.request).toHaveBeenCalledWith({
        method: 'get',
        url: '/health'
      });

      expect(result).toEqual(mockResponse);
    });

    it('should handle health check failures', async () => {
      mockApiInstance.request.mockRejectedValue({
        response: { status: 503, data: 'Service unavailable' }
      });

      await expect(apiService.healthCheck())
        .rejects.toMatchObject({
          status: 503,
          message: 'Service unavailable'
        });
    });

    it('should test connectivity', async () => {
      // Mock the environment config connectivity test
      const mockConnectivityTest = jest.spyOn(
        require('../../ai-model-validation-platform/frontend/src/utils/envConfig').default,
        'testApiConnectivity'
      ).mockResolvedValue({
        connected: true,
        latency: 45,
        error: null
      });

      const result = await apiService.testConnectivity();

      expect(result.connected).toBe(true);
      expect(result.latency).toBe(45);

      mockConnectivityTest.mockRestore();
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle various HTTP error codes', async () => {
      const errorCodes = [400, 401, 403, 404, 500, 502, 503];

      for (const code of errorCodes) {
        mockApiInstance.request.mockRejectedValue({
          response: {
            status: code,
            data: { message: `Error ${code}` }
          }
        });

        await expect(apiService.runDetectionPipeline(mockVideoId, {
          confidenceThreshold: 0.5,
          nmsThreshold: 0.4,
          modelName: 'yolov8n',
          targetClasses: ['person']
        })).rejects.toMatchObject({
          status: code,
          message: `Error ${code}`
        });
      }
    });

    it('should handle malformed error responses', async () => {
      mockApiInstance.request.mockRejectedValue({
        response: {
          status: 500,
          data: 'Plain text error message'
        }
      });

      await expect(apiService.runDetectionPipeline(mockVideoId, {
        confidenceThreshold: 0.5,
        nmsThreshold: 0.4,
        modelName: 'yolov8n',
        targetClasses: ['person']
      })).rejects.toMatchObject({
        status: 500,
        message: 'Plain text error message'
      });
    });

    it('should prevent object-object error messages', async () => {
      mockApiInstance.request.mockRejectedValue({
        message: { complex: 'object', nested: { data: 'should not appear' } }
      });

      await expect(apiService.runDetectionPipeline(mockVideoId, {
        confidenceThreshold: 0.5,
        nmsThreshold: 0.4,
        modelName: 'yolov8n',
        targetClasses: ['person']
      })).rejects.toMatchObject({
        message: 'An error occurred while processing your request'
      });
    });
  });
});