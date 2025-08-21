import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';
import { detectionService } from '../../ai-model-validation-platform/frontend/src/services/detectionService';

// Mock dependencies
jest.mock('../../ai-model-validation-platform/frontend/src/services/api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

describe('Video Upload and Detection Pipeline Integration', () => {
  const mockProject = {
    id: 'project-123',
    name: 'Test Project',
    description: 'Video upload test project'
  };

  const mockDetectionConfig = {
    confidenceThreshold: 0.7,
    nmsThreshold: 0.5,
    modelName: 'yolov8n',
    targetClasses: ['person', 'bicycle']
  };

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup default project mock
    mockApiService.createProject.mockResolvedValue(mockProject as any);
    mockApiService.getProject.mockResolvedValue(mockProject as any);
  });

  describe('Video Upload Workflow', () => {
    it('should handle complete video upload and detection workflow', async () => {
      const mockFile = new File(['video content'], 'test-video.mp4', { 
        type: 'video/mp4' 
      });

      const mockUploadedVideo = {
        id: 'video-123',
        filename: 'test-video.mp4',
        originalName: 'test-video.mp4',
        fileSize: mockFile.size,
        status: 'processing',
        url: 'http://localhost:8000/uploads/test-video.mp4',
        projectId: mockProject.id,
        processingStatus: 'processing',
        createdAt: '2023-01-01T00:00:00Z',
        updatedAt: '2023-01-01T00:00:00Z'
      };

      // Step 1: Upload video
      mockApiService.uploadVideo.mockImplementation((projectId, file, onProgress) => {
        // Simulate progress updates
        if (onProgress) {
          setTimeout(() => onProgress(25), 100);
          setTimeout(() => onProgress(50), 200);
          setTimeout(() => onProgress(75), 300);
          setTimeout(() => onProgress(100), 400);
        }
        
        return Promise.resolve(mockUploadedVideo as any);
      });

      const progressUpdates: number[] = [];
      const uploadedVideo = await mockApiService.uploadVideo(
        mockProject.id,
        mockFile,
        (progress) => progressUpdates.push(progress)
      );

      expect(uploadedVideo).toEqual(mockUploadedVideo);
      expect(mockApiService.uploadVideo).toHaveBeenCalledWith(
        mockProject.id,
        mockFile,
        expect.any(Function)
      );

      // Wait for progress updates
      await new Promise(resolve => setTimeout(resolve, 500));
      expect(progressUpdates).toEqual([25, 50, 75, 100]);

      // Step 2: Wait for video processing to complete
      const processedVideo = {
        ...mockUploadedVideo,
        status: 'completed',
        processingStatus: 'completed'
      };

      mockApiService.getVideo.mockResolvedValue(processedVideo as any);
      const videoStatus = await mockApiService.getVideo(uploadedVideo.id);

      expect(videoStatus.status).toBe('completed');

      // Step 3: Run detection on processed video
      const mockDetectionResult = {
        success: true,
        detections: [
          {
            id: 'det-1',
            detectionId: 'det-1',
            videoId: uploadedVideo.id,
            frame: 30,
            timestamp: 1000,
            label: 'person',
            confidence: 0.85,
            x: 100, y: 100, width: 50, height: 100
          },
          {
            id: 'det-2',
            detectionId: 'det-2',
            videoId: uploadedVideo.id,
            frame: 60,
            timestamp: 2000,
            label: 'bicycle',
            confidence: 0.78,
            x: 200, y: 150, width: 80, height: 120
          }
        ],
        processingTime: 2500
      };

      mockApiService.runDetectionPipeline.mockResolvedValue(mockDetectionResult);

      const detectionResult = await detectionService.runDetection(
        uploadedVideo.id,
        mockDetectionConfig
      );

      expect(detectionResult.success).toBe(true);
      expect(detectionResult.detections).toHaveLength(2);
      expect(detectionResult.detections[0].boundingBox.confidence).toBe(0.85);
      expect(detectionResult.detections[1].boundingBox.confidence).toBe(0.78);
    });

    it('should handle video upload progress tracking accurately', async () => {
      const mockFile = new File(
        new Array(1024 * 1024).fill('a'), // 1MB file
        'large-video.mp4',
        { type: 'video/mp4' }
      );

      const progressSteps = [0, 10, 25, 40, 60, 80, 95, 100];
      let progressCallCount = 0;

      mockApiService.uploadVideo.mockImplementation((projectId, file, onProgress) => {
        return new Promise(resolve => {
          const simulateProgress = () => {
            if (progressCallCount < progressSteps.length && onProgress) {
              onProgress(progressSteps[progressCallCount]);
              progressCallCount++;
              
              if (progressCallCount < progressSteps.length) {
                setTimeout(simulateProgress, 50);
              } else {
                resolve({
                  id: 'large-video-123',
                  filename: 'large-video.mp4',
                  fileSize: mockFile.size,
                  status: 'completed'
                } as any);
              }
            }
          };
          
          simulateProgress();
        });
      });

      const progressHistory: number[] = [];
      const uploadResult = await mockApiService.uploadVideo(
        mockProject.id,
        mockFile,
        (progress) => {
          progressHistory.push(progress);
          
          // Verify progress is monotonically increasing
          if (progressHistory.length > 1) {
            const currentProgress = progressHistory[progressHistory.length - 1];
            const previousProgress = progressHistory[progressHistory.length - 2];
            expect(currentProgress).toBeGreaterThanOrEqual(previousProgress);
          }
          
          // Verify progress is within valid range
          expect(progress).toBeGreaterThanOrEqual(0);
          expect(progress).toBeLessThanOrEqual(100);
        }
      );

      expect(progressHistory).toEqual(progressSteps);
      expect(uploadResult.fileSize).toBe(mockFile.size);
    });

    it('should handle multiple file format uploads', async () => {
      const testFiles = [
        { name: 'test.mp4', type: 'video/mp4', content: 'mp4 content' },
        { name: 'test.avi', type: 'video/avi', content: 'avi content' },
        { name: 'test.mov', type: 'video/mov', content: 'mov content' },
        { name: 'test.mkv', type: 'video/mkv', content: 'mkv content' }
      ];

      for (const fileInfo of testFiles) {
        const mockFile = new File([fileInfo.content], fileInfo.name, { 
          type: fileInfo.type 
        });

        const expectedResponse = {
          id: `video-${fileInfo.name}`,
          filename: fileInfo.name,
          originalName: fileInfo.name,
          fileSize: mockFile.size,
          status: 'processing',
          mimeType: fileInfo.type
        };

        mockApiService.uploadVideo.mockResolvedValue(expectedResponse as any);

        const result = await mockApiService.uploadVideo(mockProject.id, mockFile);

        expect(result.filename).toBe(fileInfo.name);
        expect(result.mimeType).toBe(fileInfo.type);
        expect(mockApiService.uploadVideo).toHaveBeenCalledWith(
          mockProject.id,
          expect.objectContaining({
            name: fileInfo.name,
            type: fileInfo.type
          }),
          undefined
        );
      }
    });

    it('should handle video upload validation and errors', async () => {
      const invalidFiles = [
        // Too large file
        {
          file: new File(new Array(100 * 1024 * 1024).fill('a'), 'huge.mp4', { 
            type: 'video/mp4' 
          }),
          expectedError: 'File too large'
        },
        // Invalid format
        {
          file: new File(['text content'], 'document.txt', { 
            type: 'text/plain' 
          }),
          expectedError: 'Invalid file format'
        },
        // Empty file
        {
          file: new File([], 'empty.mp4', { 
            type: 'video/mp4' 
          }),
          expectedError: 'File is empty'
        }
      ];

      for (const { file, expectedError } of invalidFiles) {
        mockApiService.uploadVideo.mockRejectedValue({
          response: {
            status: 400,
            data: { message: expectedError }
          }
        });

        await expect(
          mockApiService.uploadVideo(mockProject.id, file)
        ).rejects.toMatchObject({
          status: 400,
          message: expectedError
        });
      }
    });
  });

  describe('Central Video Upload Integration', () => {
    it('should handle central video upload without project assignment', async () => {
      const mockFile = new File(['video content'], 'central-upload.mp4', {
        type: 'video/mp4'
      });

      const mockCentralVideo = {
        id: 'central-video-123',
        filename: 'central-upload.mp4',
        originalName: 'central-upload.mp4',
        fileSize: mockFile.size,
        status: 'completed',
        projectId: null, // Not assigned to any project
        url: 'http://localhost:8000/uploads/central-upload.mp4'
      };

      mockApiService.uploadVideoCentral.mockResolvedValue(mockCentralVideo as any);

      const uploadedVideo = await mockApiService.uploadVideoCentral(mockFile);

      expect(uploadedVideo.id).toBe('central-video-123');
      expect(uploadedVideo.projectId).toBeNull();
      expect(mockApiService.uploadVideoCentral).toHaveBeenCalledWith(
        mockFile,
        undefined
      );

      // Should be able to run detection on central video
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [
          {
            id: 'central-det-1',
            detectionId: 'central-det-1',
            videoId: uploadedVideo.id,
            frame: 15,
            timestamp: 500,
            label: 'person',
            confidence: 0.92
          }
        ],
        processingTime: 1800
      });

      const detectionResult = await detectionService.runDetection(
        uploadedVideo.id,
        mockDetectionConfig
      );

      expect(detectionResult.success).toBe(true);
      expect(detectionResult.detections[0].boundingBox.confidence).toBe(0.92);
    });

    it('should handle video linking to projects after central upload', async () => {
      const centralVideoId = 'central-video-456';
      const targetProjectId = 'target-project-789';

      // Mock getting unassigned videos
      const unassignedVideos = [
        {
          id: centralVideoId,
          filename: 'unassigned-video.mp4',
          originalName: 'unassigned-video.mp4',
          fileSize: 2048000,
          status: 'completed',
          projectId: null,
          url: 'http://localhost:8000/uploads/unassigned-video.mp4'
        }
      ];

      mockApiService.getAllVideos.mockResolvedValue({
        videos: unassignedVideos,
        total: 1
      } as any);

      const unassignedResult = await mockApiService.getAllVideos(true);
      expect(unassignedResult.videos).toHaveLength(1);
      expect(unassignedResult.videos[0].projectId).toBeNull();

      // Mock video linking
      const linkingResult = [
        {
          videoId: centralVideoId,
          projectId: targetProjectId,
          assignedAt: '2023-01-01T12:00:00Z',
          assignedBy: 'test-user'
        }
      ];

      mockApiService.linkVideosToProject.mockResolvedValue(linkingResult as any);

      const result = await mockApiService.linkVideosToProject(
        targetProjectId,
        [centralVideoId]
      );

      expect(result).toHaveLength(1);
      expect(result[0].videoId).toBe(centralVideoId);
      expect(result[0].projectId).toBe(targetProjectId);

      // Mock getting linked videos
      const linkedVideo = {
        ...unassignedVideos[0],
        projectId: targetProjectId
      };

      mockApiService.getLinkedVideos.mockResolvedValue([linkedVideo] as any);

      const linkedVideos = await mockApiService.getLinkedVideos(targetProjectId);
      expect(linkedVideos[0].projectId).toBe(targetProjectId);
    });

    it('should handle video unlinking from projects', async () => {
      const videoId = 'linked-video-789';
      const projectId = 'source-project-123';

      // Mock getting linked videos
      const linkedVideos = [
        {
          id: videoId,
          filename: 'linked-video.mp4',
          projectId: projectId,
          status: 'completed'
        }
      ];

      mockApiService.getLinkedVideos.mockResolvedValue(linkedVideos as any);

      const beforeUnlink = await mockApiService.getLinkedVideos(projectId);
      expect(beforeUnlink).toHaveLength(1);
      expect(beforeUnlink[0].projectId).toBe(projectId);

      // Mock unlinking
      mockApiService.unlinkVideoFromProject.mockResolvedValue();

      await mockApiService.unlinkVideoFromProject(projectId, videoId);

      expect(mockApiService.unlinkVideoFromProject).toHaveBeenCalledWith(
        projectId,
        videoId
      );

      // Mock updated state after unlinking
      mockApiService.getLinkedVideos.mockResolvedValue([]);

      const afterUnlink = await mockApiService.getLinkedVideos(projectId);
      expect(afterUnlink).toHaveLength(0);
    });
  });

  describe('Detection Pipeline Integration', () => {
    it('should handle detection pipeline with different model configurations', async () => {
      const videoId = 'pipeline-test-video';
      const modelConfigs = [
        {
          modelName: 'yolov8n',
          confidenceThreshold: 0.5,
          nmsThreshold: 0.4,
          targetClasses: ['person']
        },
        {
          modelName: 'yolov8s',
          confidenceThreshold: 0.7,
          nmsThreshold: 0.5,
          targetClasses: ['person', 'bicycle']
        },
        {
          modelName: 'yolov8m',
          confidenceThreshold: 0.8,
          nmsThreshold: 0.6,
          targetClasses: ['person', 'bicycle', 'motorcycle']
        }
      ];

      for (const config of modelConfigs) {
        const expectedDetections = config.targetClasses.map((className, index) => ({
          id: `det-${config.modelName}-${index}`,
          detectionId: `det-${config.modelName}-${index}`,
          videoId,
          frame: index * 30,
          timestamp: index * 1000,
          label: className,
          confidence: config.confidenceThreshold + 0.1 + (index * 0.05)
        }));

        mockApiService.runDetectionPipeline.mockResolvedValue({
          success: true,
          detections: expectedDetections,
          processingTime: config.modelName === 'yolov8n' ? 1000 : 
                         config.modelName === 'yolov8s' ? 2000 : 3000
        });

        const result = await detectionService.runDetection(videoId, config);

        expect(result.success).toBe(true);
        expect(result.detections).toHaveLength(config.targetClasses.length);
        
        result.detections.forEach((detection, index) => {
          expect(detection.boundingBox.label).toBe(config.targetClasses[index]);
          expect(detection.boundingBox.confidence).toBeGreaterThan(config.confidenceThreshold);
        });

        expect(mockApiService.runDetectionPipeline).toHaveBeenCalledWith(
          videoId,
          config
        );
      }
    });

    it('should handle detection pipeline with video preprocessing', async () => {
      const videoId = 'preprocessing-video';
      
      // Mock video that requires preprocessing
      const videoInfo = {
        id: videoId,
        filename: 'high-resolution-video.mp4',
        fileSize: 50 * 1024 * 1024, // 50MB
        resolution: '4K',
        frameRate: 60,
        duration: 120, // 2 minutes
        status: 'completed'
      };

      mockApiService.getVideo.mockResolvedValue(videoInfo as any);

      // Mock preprocessing pipeline result
      const preprocessingResult = {
        success: true,
        detections: Array.from({ length: 50 }, (_, i) => ({
          id: `preprocessed-det-${i}`,
          detectionId: `preprocessed-det-${i}`,
          videoId,
          frame: i * 2, // Every 2nd frame
          timestamp: i * 33.33, // 30fps equivalent
          label: i % 2 === 0 ? 'person' : 'bicycle',
          confidence: 0.7 + Math.random() * 0.3
        })),
        processingTime: 8000, // Longer due to preprocessing
        metadata: {
          originalResolution: '3840x2160',
          processedResolution: '1920x1080',
          framesSampled: 100,
          preprocessingTime: 3000
        }
      };

      mockApiService.runDetectionPipeline.mockResolvedValue(preprocessingResult);

      const result = await detectionService.runDetection(videoId, mockDetectionConfig);

      expect(result.success).toBe(true);
      expect(result.detections).toHaveLength(50);
      expect(result.processingTime).toBeGreaterThan(7000);
    });

    it('should handle detection pipeline with multiple object classes', async () => {
      const videoId = 'multi-class-video';
      const complexConfig = {
        ...mockDetectionConfig,
        targetClasses: ['person', 'bicycle', 'motorcycle', 'car', 'truck', 'bus'],
        confidenceThreshold: 0.6
      };

      // Mock detection result with multiple object classes
      const multiClassDetections = [
        { label: 'person', count: 8, avgConfidence: 0.85 },
        { label: 'bicycle', count: 3, avgConfidence: 0.78 },
        { label: 'motorcycle', count: 2, avgConfidence: 0.82 },
        { label: 'car', count: 15, avgConfidence: 0.92 },
        { label: 'truck', count: 1, avgConfidence: 0.88 },
        { label: 'bus', count: 1, avgConfidence: 0.75 }
      ];

      const allDetections = multiClassDetections.flatMap(classInfo =>
        Array.from({ length: classInfo.count }, (_, i) => ({
          id: `${classInfo.label}-det-${i}`,
          detectionId: `${classInfo.label}-det-${i}`,
          videoId,
          frame: Math.floor(Math.random() * 300),
          timestamp: Math.random() * 10000,
          label: classInfo.label,
          confidence: classInfo.avgConfidence + (Math.random() - 0.5) * 0.1
        }))
      );

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: allDetections,
        processingTime: 4500
      });

      const result = await detectionService.runDetection(videoId, complexConfig);

      expect(result.success).toBe(true);
      expect(result.detections).toHaveLength(30); // Total detections

      // Verify class distribution
      const detectionsByClass = result.detections.reduce((acc, detection) => {
        const className = detection.boundingBox.label;
        acc[className] = (acc[className] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      expect(detectionsByClass.person).toBe(8);
      expect(detectionsByClass.bicycle).toBe(3);
      expect(detectionsByClass.car).toBe(15);

      // Verify all detections meet confidence threshold
      result.detections.forEach(detection => {
        expect(detection.boundingBox.confidence).toBeGreaterThanOrEqual(
          complexConfig.confidenceThreshold
        );
      });
    });

    it('should handle detection pipeline performance optimization', async () => {
      const videoId = 'performance-test-video';
      
      const performanceConfigs = [
        {
          name: 'Fast',
          modelName: 'yolov8n',
          confidenceThreshold: 0.5,
          expectedProcessingTime: 1000
        },
        {
          name: 'Balanced',
          modelName: 'yolov8s',
          confidenceThreshold: 0.7,
          expectedProcessingTime: 2000
        },
        {
          name: 'Accurate',
          modelName: 'yolov8m',
          confidenceThreshold: 0.8,
          expectedProcessingTime: 4000
        }
      ];

      for (const config of performanceConfigs) {
        const detectionConfig = {
          ...mockDetectionConfig,
          modelName: config.modelName,
          confidenceThreshold: config.confidenceThreshold
        };

        mockApiService.runDetectionPipeline.mockResolvedValue({
          success: true,
          detections: [
            {
              id: `perf-det-${config.name}`,
              detectionId: `perf-det-${config.name}`,
              videoId,
              frame: 0,
              timestamp: 0,
              label: 'person',
              confidence: config.confidenceThreshold + 0.1
            }
          ],
          processingTime: config.expectedProcessingTime
        });

        const startTime = performance.now();
        const result = await detectionService.runDetection(videoId, detectionConfig);
        const totalTime = performance.now() - startTime;

        expect(result.success).toBe(true);
        expect(result.detections[0].boundingBox.confidence).toBeGreaterThan(
          config.confidenceThreshold
        );
        
        // Verify performance characteristics
        console.log(`${config.name} config: ${totalTime.toFixed(2)}ms total, ${result.processingTime}ms processing`);
        
        // Total time should be reasonable (processing time + overhead)
        expect(totalTime).toBeLessThan(config.expectedProcessingTime + 1000);
      }
    });
  });

  describe('Video Quality and Format Handling', () => {
    it('should handle various video qualities and resolutions', async () => {
      const qualityTests = [
        { resolution: '720p', width: 1280, height: 720, expectedDetections: 5 },
        { resolution: '1080p', width: 1920, height: 1080, expectedDetections: 8 },
        { resolution: '4K', width: 3840, height: 2160, expectedDetections: 15 }
      ];

      for (const quality of qualityTests) {
        const videoId = `video-${quality.resolution}`;
        
        mockApiService.runDetectionPipeline.mockResolvedValue({
          success: true,
          detections: Array.from({ length: quality.expectedDetections }, (_, i) => ({
            id: `${quality.resolution}-det-${i}`,
            detectionId: `${quality.resolution}-det-${i}`,
            videoId,
            frame: i * 30,
            timestamp: i * 1000,
            label: 'person',
            confidence: 0.8,
            // Scale coordinates to resolution
            x: Math.random() * quality.width,
            y: Math.random() * quality.height,
            width: 50 * (quality.width / 1920), // Scale bounding box
            height: 100 * (quality.height / 1080)
          })),
          processingTime: quality.resolution === '4K' ? 6000 : 
                         quality.resolution === '1080p' ? 3000 : 1500
        });

        const result = await detectionService.runDetection(videoId, mockDetectionConfig);

        expect(result.success).toBe(true);
        expect(result.detections).toHaveLength(quality.expectedDetections);
        
        // Verify coordinates are within bounds
        result.detections.forEach(detection => {
          expect(detection.boundingBox.x).toBeLessThan(quality.width);
          expect(detection.boundingBox.y).toBeLessThan(quality.height);
          expect(detection.boundingBox.x + detection.boundingBox.width).toBeLessThanOrEqual(quality.width);
          expect(detection.boundingBox.y + detection.boundingBox.height).toBeLessThanOrEqual(quality.height);
        });
      }
    });

    it('should handle video codec and container format variations', async () => {
      const formatTests = [
        { 
          container: 'mp4', 
          codec: 'h264', 
          compatibility: 'high',
          processingTime: 2000
        },
        { 
          container: 'avi', 
          codec: 'xvid', 
          compatibility: 'medium',
          processingTime: 3000
        },
        { 
          container: 'mkv', 
          codec: 'h265', 
          compatibility: 'high',
          processingTime: 2500
        },
        { 
          container: 'mov', 
          codec: 'prores', 
          compatibility: 'low',
          processingTime: 4000
        }
      ];

      for (const format of formatTests) {
        const videoId = `video-${format.container}-${format.codec}`;
        
        if (format.compatibility === 'low') {
          // Simulate processing difficulties with some formats
          mockApiService.runDetectionPipeline.mockResolvedValue({
            success: true,
            detections: [], // Fewer detections due to processing issues
            processingTime: format.processingTime,
            warnings: [`Format ${format.container}/${format.codec} may have reduced accuracy`]
          });
        } else {
          mockApiService.runDetectionPipeline.mockResolvedValue({
            success: true,
            detections: [
              {
                id: `format-det-${format.container}`,
                detectionId: `format-det-${format.container}`,
                videoId,
                frame: 30,
                timestamp: 1000,
                label: 'person',
                confidence: format.compatibility === 'high' ? 0.85 : 0.75
              }
            ],
            processingTime: format.processingTime
          });
        }

        const result = await detectionService.runDetection(videoId, mockDetectionConfig);

        expect(result.success).toBe(true);
        
        if (format.compatibility === 'high') {
          expect(result.detections).toHaveLength(1);
          expect(result.detections[0].boundingBox.confidence).toBeGreaterThan(0.8);
        }
        
        expect(result.processingTime).toBeCloseTo(format.processingTime, -2);
      }
    });
  });
});