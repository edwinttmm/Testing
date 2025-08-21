import { detectionService } from '../../ai-model-validation-platform/frontend/src/services/detectionService';
import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';
import { useDetectionWebSocket } from '../../ai-model-validation-platform/frontend/src/hooks/useDetectionWebSocket';

// Mock dependencies
jest.mock('../../ai-model-validation-platform/frontend/src/services/api');
jest.mock('../../ai-model-validation-platform/frontend/src/hooks/useDetectionWebSocket');

const mockApiService = apiService as jest.Mocked<typeof apiService>;
const mockUseDetectionWebSocket = useDetectionWebSocket as jest.MockedFunction<typeof useDetectionWebSocket>;

describe('End-to-End Detection Workflow', () => {
  const mockProject = {
    id: 'project-123',
    name: 'Test Project',
    description: 'E2E test project'
  };

  const mockVideo = {
    id: 'video-123',
    filename: 'test-video.mp4',
    originalName: 'test-video.mp4',
    fileSize: 1024000,
    status: 'completed',
    url: 'http://localhost:8000/uploads/test-video.mp4',
    projectId: mockProject.id
  };

  const mockDetectionConfig = {
    confidenceThreshold: 0.7,
    nmsThreshold: 0.5,
    modelName: 'yolov8n',
    targetClasses: ['person', 'bicycle']
  };

  let mockWebSocketCallbacks: any = {};

  beforeEach(() => {
    jest.clearAllMocks();
    mockWebSocketCallbacks = {};

    // Mock WebSocket hook
    mockUseDetectionWebSocket.mockReturnValue({
      connect: jest.fn(),
      disconnect: jest.fn(),
      sendMessage: jest.fn(),
      isConnected: true
    });

    // Setup common API mocks
    mockApiService.createProject.mockResolvedValue(mockProject as any);
    mockApiService.getProject.mockResolvedValue(mockProject as any);
    mockApiService.uploadVideo.mockResolvedValue(mockVideo as any);
    mockApiService.getVideos.mockResolvedValue([mockVideo] as any);
    mockApiService.getVideo.mockResolvedValue(mockVideo as any);
  });

  describe('Complete Detection Workflow', () => {
    it('should complete full workflow: project creation → video upload → detection → annotations', async () => {
      // Step 1: Create project
      const project = await mockApiService.createProject({
        name: 'E2E Test Project',
        description: 'End-to-end testing project'
      });

      expect(project).toEqual(mockProject);
      expect(mockApiService.createProject).toHaveBeenCalledWith({
        name: 'E2E Test Project',
        description: 'End-to-end testing project'
      });

      // Step 2: Upload video
      const mockFile = new File(['video data'], 'test.mp4', { type: 'video/mp4' });
      const progressCallback = jest.fn();

      const uploadedVideo = await mockApiService.uploadVideo(
        project.id,
        mockFile,
        progressCallback
      );

      expect(uploadedVideo).toEqual(mockVideo);
      expect(mockApiService.uploadVideo).toHaveBeenCalledWith(
        project.id,
        mockFile,
        progressCallback
      );

      // Step 3: Run detection
      const mockDetectionResult = {
        success: true,
        detections: [
          {
            id: 'ann-1',
            videoId: uploadedVideo.id,
            detectionId: 'det-1',
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
            validated: false,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
          }
        ],
        source: 'backend' as const,
        processingTime: 1500
      };

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [
          {
            id: 'det-1',
            detectionId: 'det-1',
            frame: 5,
            timestamp: 166.67,
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
      });

      const detectionResult = await detectionService.runDetection(
        uploadedVideo.id,
        mockDetectionConfig
      );

      expect(detectionResult.success).toBe(true);
      expect(detectionResult.detections).toHaveLength(1);
      expect(detectionResult.detections[0].boundingBox.confidence).toBe(0.85);

      // Step 4: Create and validate annotations
      const detectedAnnotation = detectionResult.detections[0];
      
      mockApiService.createAnnotation.mockResolvedValue({
        id: 'ann-created-1',
        ...detectedAnnotation
      } as any);

      const createdAnnotation = await mockApiService.createAnnotation(
        uploadedVideo.id,
        detectedAnnotation
      );

      expect(createdAnnotation.id).toBe('ann-created-1');
      expect(mockApiService.createAnnotation).toHaveBeenCalledWith(
        uploadedVideo.id,
        detectedAnnotation
      );

      // Step 5: Validate annotation
      mockApiService.validateAnnotation.mockResolvedValue({
        ...createdAnnotation,
        validated: true
      } as any);

      const validatedAnnotation = await mockApiService.validateAnnotation(
        createdAnnotation.id,
        true
      );

      expect(validatedAnnotation.validated).toBe(true);
      expect(mockApiService.validateAnnotation).toHaveBeenCalledWith(
        createdAnnotation.id,
        true
      );
    });

    it('should handle workflow with real-time WebSocket updates', async () => {
      const mockDetectionUpdates = [
        { type: 'progress', videoId: mockVideo.id, progress: 25 },
        { type: 'detection', videoId: mockVideo.id, annotation: { id: 'det-1' } },
        { type: 'progress', videoId: mockVideo.id, progress: 75 },
        { type: 'complete', videoId: mockVideo.id, data: { totalDetections: 5 } }
      ];

      let updateCallback: ((update: any) => void) | undefined;

      // Capture the update callback when WebSocket hook is called
      mockUseDetectionWebSocket.mockImplementation((options) => {
        updateCallback = options?.onUpdate;
        return {
          connect: jest.fn(),
          disconnect: jest.fn(),
          sendMessage: jest.fn(),
          isConnected: true
        };
      });

      // Simulate WebSocket integration
      const receivedUpdates: any[] = [];
      const webSocketHook = mockUseDetectionWebSocket({
        onUpdate: (update) => {
          receivedUpdates.push(update);
        }
      });

      // Simulate receiving updates
      if (updateCallback) {
        mockDetectionUpdates.forEach(update => updateCallback!(update));
      }

      expect(receivedUpdates).toHaveLength(4);
      expect(receivedUpdates[0].type).toBe('progress');
      expect(receivedUpdates[0].progress).toBe(25);
      expect(receivedUpdates[3].type).toBe('complete');
    });

    it('should handle workflow with multiple videos in batch', async () => {
      const mockVideos = [
        { ...mockVideo, id: 'video-1', filename: 'video-1.mp4' },
        { ...mockVideo, id: 'video-2', filename: 'video-2.mp4' },
        { ...mockVideo, id: 'video-3', filename: 'video-3.mp4' }
      ];

      // Mock batch video upload
      mockApiService.uploadVideo
        .mockResolvedValueOnce(mockVideos[0] as any)
        .mockResolvedValueOnce(mockVideos[1] as any)
        .mockResolvedValueOnce(mockVideos[2] as any);

      // Mock batch detection
      mockApiService.runDetectionPipeline.mockImplementation((videoId) =>
        Promise.resolve({
          success: true,
          detections: [
            {
              id: `det-${videoId}`,
              detectionId: `det-${videoId}`,
              videoId,
              frame: 0,
              timestamp: 0,
              label: 'person',
              confidence: 0.8
            }
          ],
          processingTime: 1000 + Math.random() * 500
        })
      );

      // Step 1: Upload multiple videos
      const files = mockVideos.map((_, index) => 
        new File([`video ${index + 1} data`], `video-${index + 1}.mp4`, { 
          type: 'video/mp4' 
        })
      );

      const uploadPromises = files.map(file => 
        mockApiService.uploadVideo(mockProject.id, file)
      );

      const uploadedVideos = await Promise.all(uploadPromises);

      expect(uploadedVideos).toHaveLength(3);
      expect(uploadedVideos.map(v => v.id)).toEqual(['video-1', 'video-2', 'video-3']);

      // Step 2: Run detection on all videos
      const detectionPromises = uploadedVideos.map(video =>
        detectionService.runDetection(video.id, mockDetectionConfig)
      );

      const detectionResults = await Promise.all(detectionPromises);

      expect(detectionResults).toHaveLength(3);
      detectionResults.forEach((result, index) => {
        expect(result.success).toBe(true);
        expect(result.detections[0].detectionId).toBe(`det-video-${index + 1}`);
      });

      // Step 3: Create annotations from all detections
      const annotationPromises = detectionResults.flatMap((result, videoIndex) =>
        result.detections.map(detection => {
          mockApiService.createAnnotation.mockResolvedValue({
            id: `ann-${videoIndex}-${detection.detectionId}`,
            ...detection
          } as any);

          return mockApiService.createAnnotation(
            uploadedVideos[videoIndex].id,
            detection
          );
        })
      );

      const createdAnnotations = await Promise.all(annotationPromises);

      expect(createdAnnotations).toHaveLength(3);
      expect(mockApiService.createAnnotation).toHaveBeenCalledTimes(3);
    });
  });

  describe('Error Recovery Scenarios', () => {
    it('should handle video upload failure and retry', async () => {
      const mockFile = new File(['video data'], 'test.mp4', { type: 'video/mp4' });

      // First upload fails, second succeeds
      mockApiService.uploadVideo
        .mockRejectedValueOnce(new Error('Upload failed'))
        .mockResolvedValueOnce(mockVideo as any);

      // Initial upload fails
      await expect(mockApiService.uploadVideo(mockProject.id, mockFile))
        .rejects.toThrow('Upload failed');

      // Retry succeeds
      const retryResult = await mockApiService.uploadVideo(mockProject.id, mockFile);
      expect(retryResult).toEqual(mockVideo);
    });

    it('should handle detection pipeline failure with fallback', async () => {
      // Mock pipeline failure
      mockApiService.runDetectionPipeline.mockRejectedValue(
        new Error('Detection pipeline unavailable')
      );

      const result = await detectionService.runDetection(
        mockVideo.id,
        mockDetectionConfig
      );

      expect(result.success).toBe(false);
      expect(result.error).toContain('Detection pipeline unavailable');
      expect(result.detections).toHaveLength(0);
    });

    it('should handle network disconnection and reconnection', async () => {
      let isConnected = false;
      
      mockUseDetectionWebSocket.mockImplementation((options) => ({
        connect: jest.fn(() => { isConnected = true; }),
        disconnect: jest.fn(() => { isConnected = false; }),
        sendMessage: jest.fn(),
        isConnected
      }));

      const webSocketHook = mockUseDetectionWebSocket({
        autoReconnect: true,
        onConnect: () => console.log('Connected'),
        onDisconnect: () => console.log('Disconnected')
      });

      // Initial connection
      webSocketHook.connect();
      expect(isConnected).toBe(true);

      // Simulate disconnection
      webSocketHook.disconnect();
      expect(isConnected).toBe(false);

      // Simulate reconnection
      webSocketHook.connect();
      expect(isConnected).toBe(true);
    });

    it('should handle partial annotation failures', async () => {
      const mockDetections = [
        {
          id: 'det-1',
          videoId: mockVideo.id,
          detectionId: 'det-1',
          frameNumber: 0,
          timestamp: 0,
          vruType: 'pedestrian',
          boundingBox: {
            x: 100, y: 100, width: 50, height: 100,
            label: 'person', confidence: 0.8
          },
          occluded: false, truncated: false, difficult: false,
          validated: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        },
        {
          id: 'det-2',
          videoId: mockVideo.id,
          detectionId: 'det-2',
          frameNumber: 1,
          timestamp: 33.33,
          vruType: 'cyclist',
          boundingBox: {
            x: 200, y: 150, width: 60, height: 120,
            label: 'bicycle', confidence: 0.9
          },
          occluded: false, truncated: false, difficult: false,
          validated: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        }
      ];

      // First annotation succeeds, second fails
      mockApiService.createAnnotation
        .mockResolvedValueOnce({ id: 'ann-1', ...mockDetections[0] } as any)
        .mockRejectedValueOnce(new Error('Annotation creation failed'));

      const results = await Promise.allSettled(
        mockDetections.map(detection =>
          mockApiService.createAnnotation(mockVideo.id, detection)
        )
      );

      expect(results[0].status).toBe('fulfilled');
      expect(results[1].status).toBe('rejected');

      // Should be able to retry failed annotation
      mockApiService.createAnnotation.mockResolvedValueOnce({
        id: 'ann-2', ...mockDetections[1]
      } as any);

      const retryResult = await mockApiService.createAnnotation(
        mockVideo.id, 
        mockDetections[1]
      );

      expect(retryResult.id).toBe('ann-2');
    });

    it('should handle concurrent detection requests gracefully', async () => {
      const videoIds = ['video-1', 'video-2', 'video-3'];

      // Mock one detection to fail, others to succeed
      mockApiService.runDetectionPipeline
        .mockResolvedValueOnce({
          success: true,
          detections: [{ id: 'det-1', videoId: 'video-1' }],
          processingTime: 1000
        })
        .mockRejectedValueOnce(new Error('Pipeline overloaded'))
        .mockResolvedValueOnce({
          success: true,
          detections: [{ id: 'det-3', videoId: 'video-3' }],
          processingTime: 1200
        });

      const detectionPromises = videoIds.map(videoId =>
        detectionService.runDetection(videoId, mockDetectionConfig)
          .catch(error => ({ success: false, error: error.message }))
      );

      const results = await Promise.all(detectionPromises);

      expect(results[0]).toMatchObject({ success: true });
      expect(results[1]).toMatchObject({ success: false });
      expect(results[2]).toMatchObject({ success: true });
    });
  });

  describe('Data Consistency and Validation', () => {
    it('should maintain data consistency across workflow steps', async () => {
      // Step 1: Create project with metadata
      const projectWithMetadata = {
        ...mockProject,
        metadata: { testRun: 'e2e-consistency-test' }
      };

      mockApiService.createProject.mockResolvedValue(projectWithMetadata as any);
      const createdProject = await mockApiService.createProject({
        name: 'Consistency Test',
        description: 'Testing data consistency'
      });

      // Step 2: Verify project data is preserved through video upload
      const videoWithProjectRef = {
        ...mockVideo,
        projectId: createdProject.id,
        metadata: { inheritedFrom: createdProject.id }
      };

      mockApiService.uploadVideo.mockResolvedValue(videoWithProjectRef as any);
      const uploadedVideo = await mockApiService.uploadVideo(
        createdProject.id,
        new File(['test'], 'test.mp4', { type: 'video/mp4' })
      );

      expect(uploadedVideo.projectId).toBe(createdProject.id);

      // Step 3: Verify annotation references are correct
      const detectionWithRefs = {
        id: 'det-1',
        videoId: uploadedVideo.id,
        detectionId: 'det-1',
        frameNumber: 0,
        timestamp: 0,
        vruType: 'pedestrian',
        boundingBox: {
          x: 100, y: 100, width: 50, height: 100,
          label: 'person', confidence: 0.8
        },
        occluded: false, truncated: false, difficult: false,
        validated: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [
          {
            id: 'det-1',
            detectionId: 'det-1',
            videoId: uploadedVideo.id,
            frame: 0,
            timestamp: 0,
            label: 'person',
            confidence: 0.8,
            x: 100, y: 100, width: 50, height: 100
          }
        ],
        processingTime: 1000
      });

      const detectionResult = await detectionService.runDetection(
        uploadedVideo.id,
        mockDetectionConfig
      );

      expect(detectionResult.detections[0].videoId).toBe(uploadedVideo.id);

      // Step 4: Verify annotation creation maintains references
      mockApiService.createAnnotation.mockResolvedValue({
        ...detectionWithRefs,
        id: 'ann-1',
        projectId: createdProject.id // Should inherit project reference
      } as any);

      const annotation = await mockApiService.createAnnotation(
        uploadedVideo.id,
        detectionResult.detections[0]
      );

      expect(annotation.videoId).toBe(uploadedVideo.id);
      expect(annotation.projectId).toBe(createdProject.id);
    });

    it('should validate annotation data integrity', async () => {
      const validAnnotation = {
        detectionId: 'det-valid',
        frameNumber: 10,
        timestamp: 333.33,
        vruType: 'pedestrian',
        boundingBox: {
          x: 150, y: 200, width: 80, height: 150,
          label: 'person', confidence: 0.92
        },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: true,
        notes: 'Clear detection with high confidence',
        annotator: 'test-annotator'
      };

      mockApiService.createAnnotation.mockResolvedValue({
        id: 'ann-valid',
        videoId: mockVideo.id,
        ...validAnnotation,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      } as any);

      const result = await mockApiService.createAnnotation(
        mockVideo.id,
        validAnnotation
      );

      // Verify all fields are preserved
      expect(result.detectionId).toBe(validAnnotation.detectionId);
      expect(result.frameNumber).toBe(validAnnotation.frameNumber);
      expect(result.timestamp).toBe(validAnnotation.timestamp);
      expect(result.vruType).toBe(validAnnotation.vruType);
      expect(result.boundingBox).toEqual(validAnnotation.boundingBox);
      expect(result.validated).toBe(validAnnotation.validated);
      expect(result.notes).toBe(validAnnotation.notes);
      expect(result.annotator).toBe(validAnnotation.annotator);
    });

    it('should handle timestamp synchronization correctly', async () => {
      const frameRate = 30; // 30 FPS
      const frameNumber = 90;
      const expectedTimestamp = frameNumber / frameRate * 1000; // 3000ms

      const detectionWithTimestamp = {
        id: 'det-sync',
        detectionId: 'det-sync',
        videoId: mockVideo.id,
        frame: frameNumber,
        timestamp: expectedTimestamp,
        label: 'person',
        confidence: 0.85
      };

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [detectionWithTimestamp],
        processingTime: 800
      });

      const result = await detectionService.runDetection(
        mockVideo.id,
        mockDetectionConfig
      );

      expect(result.detections[0].frameNumber).toBe(frameNumber);
      expect(result.detections[0].timestamp).toBe(expectedTimestamp);
    });
  });
});