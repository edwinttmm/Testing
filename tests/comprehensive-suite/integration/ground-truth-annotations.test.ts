import { describe, it, expect, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { apiService } from '../../../ai-model-validation-platform/frontend/src/services/api';
import { TEST_PROJECTS, TEST_VIDEOS, TEST_ANNOTATIONS, createMockVideoBlob } from '../fixtures/test-videos';
import type { GroundTruthAnnotation, AnnotationSession, VideoFile, Project } from '../../../ai-model-validation-platform/frontend/src/services/types';

describe('Ground Truth Processing and Annotations Integration Tests', () => {
  let createdProjectIds: string[] = [];
  let createdVideoIds: string[] = [];
  let createdAnnotationIds: string[] = [];
  let createdSessionIds: string[] = [];

  beforeAll(async () => {
    // Ensure API is accessible
    try {
      await apiService.healthCheck();
    } catch (error) {
      console.warn('API not available for integration tests');
      return;
    }
  });

  afterAll(async () => {
    // Cleanup created resources
    for (const annotationId of createdAnnotationIds) {
      try {
        await apiService.deleteAnnotation(annotationId);
      } catch (error) {
        console.warn(`Failed to cleanup annotation ${annotationId}:`, error);
      }
    }

    for (const videoId of createdVideoIds) {
      try {
        await apiService.deleteVideo(videoId);
      } catch (error) {
        console.warn(`Failed to cleanup video ${videoId}:`, error);
      }
    }

    for (const projectId of createdProjectIds) {
      try {
        await apiService.deleteProject(projectId);
      } catch (error) {
        console.warn(`Failed to cleanup project ${projectId}:`, error);
      }
    }
  });

  describe('Ground Truth Processing Workflow', () => {
    let testProject: Project;
    let testVideo: VideoFile;

    beforeEach(async () => {
      // Create test project and video for each test
      testProject = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(testProject.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      testVideo = await apiService.uploadVideo(testProject.id, file);
      createdVideoIds.push(testVideo.id);
    });

    it('should process uploaded video and generate ground truth data', async () => {
      // Act - Get ground truth data (this should trigger processing if not already done)
      const groundTruthData = await apiService.getGroundTruth(testVideo.id);

      // Assert
      expect(groundTruthData).toBeDefined();
      // Ground truth structure depends on backend implementation
      // At minimum, should have some metadata about the video
    });

    it('should track ground truth processing status', async () => {
      // Act
      let videoStatus = await apiService.getVideo(testVideo.id);

      // Assert
      expect(videoStatus.processing_status).toBeDefined();
      expect(videoStatus.processing_status).toBeOneOf(['pending', 'processing', 'completed', 'failed']);

      // If processing is still in progress, wait and check again
      if (videoStatus.processing_status === 'processing') {
        await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
        videoStatus = await apiService.getVideo(testVideo.id);
        expect(videoStatus.processing_status).toBeOneOf(['completed', 'failed']);
      }
    });

    it('should handle large video ground truth processing', async () => {
      // Arrange
      const largeVideoData = TEST_VIDEOS.large;
      const mockLargeVideoFile = createMockVideoBlob(largeVideoData);
      const largeFile = new File([mockLargeVideoFile], largeVideoData.filename, { type: largeVideoData.format });

      const largeVideo = await apiService.uploadVideo(testProject.id, largeFile);
      createdVideoIds.push(largeVideo.id);

      // Act
      const processingStart = Date.now();
      const groundTruthData = await apiService.getGroundTruth(largeVideo.id);
      const processingTime = Date.now() - processingStart;

      // Assert
      expect(groundTruthData).toBeDefined();
      // Large video processing should complete within reasonable time (adjusted for test environment)
      expect(processingTime).toBeLessThan(60000); // 60 seconds max for test
    });
  });

  describe('Annotation Creation and Management', () => {
    let testProject: Project;
    let testVideo: VideoFile;

    beforeEach(async () => {
      testProject = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(testProject.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      testVideo = await apiService.uploadVideo(testProject.id, file);
      createdVideoIds.push(testVideo.id);
    });

    it('should create new annotation for video', async () => {
      // Arrange
      const annotationData = {
        detectionId: TEST_ANNOTATIONS.pedestrian.detectionId,
        frameNumber: TEST_ANNOTATIONS.pedestrian.frameNumber,
        timestamp: TEST_ANNOTATIONS.pedestrian.timestamp,
        vruType: TEST_ANNOTATIONS.pedestrian.vruType,
        boundingBox: TEST_ANNOTATIONS.pedestrian.boundingBox,
        occluded: TEST_ANNOTATIONS.pedestrian.occluded,
        truncated: TEST_ANNOTATIONS.pedestrian.truncated,
        difficult: TEST_ANNOTATIONS.pedestrian.difficult,
        notes: 'Test annotation created during integration test',
        annotator: TEST_ANNOTATIONS.pedestrian.annotator,
        validated: false
      };

      // Act
      const createdAnnotation = await apiService.createAnnotation(testVideo.id, annotationData);

      // Assert
      expect(createdAnnotation).toBeDefined();
      expect(createdAnnotation.id).toBeDefined();
      expect(createdAnnotation.detectionId).toBe(annotationData.detectionId);
      expect(createdAnnotation.frameNumber).toBe(annotationData.frameNumber);
      expect(createdAnnotation.timestamp).toBe(annotationData.timestamp);
      expect(createdAnnotation.vruType).toBe(annotationData.vruType);
      expect(createdAnnotation.boundingBox).toEqual(annotationData.boundingBox);
      expect(createdAnnotation.validated).toBe(false);

      createdAnnotationIds.push(createdAnnotation.id);
    });

    it('should retrieve annotations for video', async () => {
      // Arrange - Create multiple annotations
      const annotations = [
        {
          ...TEST_ANNOTATIONS.pedestrian,
          detectionId: 'det-test-1',
          notes: 'First test annotation'
        },
        {
          ...TEST_ANNOTATIONS.cyclist,
          detectionId: 'det-test-2',
          notes: 'Second test annotation'
        }
      ];

      const createdAnnotations = [];
      for (const annotationData of annotations) {
        const created = await apiService.createAnnotation(testVideo.id, annotationData);
        createdAnnotations.push(created);
        createdAnnotationIds.push(created.id);
      }

      // Act
      const videoAnnotations = await apiService.getAnnotations(testVideo.id);

      // Assert
      expect(videoAnnotations).toBeDefined();
      expect(Array.isArray(videoAnnotations)).toBe(true);
      expect(videoAnnotations.length).toBeGreaterThanOrEqual(2);

      const annotationIds = videoAnnotations.map(a => a.id);
      createdAnnotations.forEach(annotation => {
        expect(annotationIds).toContain(annotation.id);
      });
    });

    it('should update existing annotation', async () => {
      // Arrange
      const annotationData = {
        ...TEST_ANNOTATIONS.pedestrian,
        detectionId: 'det-update-test',
        validated: false
      };

      const createdAnnotation = await apiService.createAnnotation(testVideo.id, annotationData);
      createdAnnotationIds.push(createdAnnotation.id);

      const updateData = {
        vruType: 'motorcyclist' as const,
        validated: true,
        notes: 'Updated during integration test',
        boundingBox: { x: 150, y: 75, width: 100, height: 150 }
      };

      // Act
      const updatedAnnotation = await apiService.updateAnnotation(createdAnnotation.id, updateData);

      // Assert
      expect(updatedAnnotation.id).toBe(createdAnnotation.id);
      expect(updatedAnnotation.vruType).toBe(updateData.vruType);
      expect(updatedAnnotation.validated).toBe(updateData.validated);
      expect(updatedAnnotation.notes).toBe(updateData.notes);
      expect(updatedAnnotation.boundingBox).toEqual(updateData.boundingBox);
    });

    it('should validate annotation', async () => {
      // Arrange
      const annotationData = {
        ...TEST_ANNOTATIONS.cyclist,
        detectionId: 'det-validation-test',
        validated: false
      };

      const createdAnnotation = await apiService.createAnnotation(testVideo.id, annotationData);
      createdAnnotationIds.push(createdAnnotation.id);

      // Act
      const validatedAnnotation = await apiService.validateAnnotation(createdAnnotation.id, true);

      // Assert
      expect(validatedAnnotation.id).toBe(createdAnnotation.id);
      expect(validatedAnnotation.validated).toBe(true);
    });

    it('should delete annotation', async () => {
      // Arrange
      const annotationData = {
        ...TEST_ANNOTATIONS.pedestrian,
        detectionId: 'det-delete-test'
      };

      const createdAnnotation = await apiService.createAnnotation(testVideo.id, annotationData);

      // Act
      await apiService.deleteAnnotation(createdAnnotation.id);

      // Assert
      const videoAnnotations = await apiService.getAnnotations(testVideo.id);
      const annotationIds = videoAnnotations.map(a => a.id);
      expect(annotationIds).not.toContain(createdAnnotation.id);

      // Remove from cleanup list since it's already deleted
      const index = createdAnnotationIds.indexOf(createdAnnotation.id);
      if (index > -1) createdAnnotationIds.splice(index, 1);
    });
  });

  describe('Annotation Sessions', () => {
    let testProject: Project;
    let testVideo: VideoFile;

    beforeEach(async () => {
      testProject = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(testProject.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      testVideo = await apiService.uploadVideo(testProject.id, file);
      createdVideoIds.push(testVideo.id);
    });

    it('should create annotation session', async () => {
      // Act
      const session = await apiService.createAnnotationSession(testVideo.id, testProject.id);

      // Assert
      expect(session).toBeDefined();
      expect(session.id).toBeDefined();
      expect(session.video_id).toBe(testVideo.id);
      expect(session.project_id).toBe(testProject.id);
      expect(session.status).toBe('active');

      createdSessionIds.push(session.id);
    });

    it('should update annotation session progress', async () => {
      // Arrange
      const session = await apiService.createAnnotationSession(testVideo.id, testProject.id);
      createdSessionIds.push(session.id);

      const updateData = {
        currentFrame: 150,
        totalDetections: 25,
        validatedDetections: 10,
        status: 'in_progress' as const
      };

      // Act
      const updatedSession = await apiService.updateAnnotationSession(session.id, updateData);

      // Assert
      expect(updatedSession.id).toBe(session.id);
      expect(updatedSession.currentFrame).toBe(updateData.currentFrame);
      expect(updatedSession.totalDetections).toBe(updateData.totalDetections);
      expect(updatedSession.validatedDetections).toBe(updateData.validatedDetections);
      expect(updatedSession.status).toBe(updateData.status);
    });
  });

  describe('Annotation Export and Import', () => {
    let testProject: Project;
    let testVideo: VideoFile;

    beforeEach(async () => {
      testProject = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(testProject.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      testVideo = await apiService.uploadVideo(testProject.id, file);
      createdVideoIds.push(testVideo.id);
    });

    it('should export annotations in multiple formats', async () => {
      // Arrange - Create some annotations first
      const annotationsData = [
        { ...TEST_ANNOTATIONS.pedestrian, detectionId: 'export-test-1' },
        { ...TEST_ANNOTATIONS.cyclist, detectionId: 'export-test-2' }
      ];

      for (const annotationData of annotationsData) {
        const created = await apiService.createAnnotation(testVideo.id, annotationData);
        createdAnnotationIds.push(created.id);
      }

      // Test different export formats
      const formats: Array<'json' | 'coco' | 'yolo' | 'pascal'> = ['json', 'coco', 'yolo', 'pascal'];

      for (const format of formats) {
        // Act
        const exportBlob = await apiService.exportAnnotations(testVideo.id, format);

        // Assert
        expect(exportBlob).toBeDefined();
        expect(exportBlob instanceof Blob).toBe(true);
        expect(exportBlob.size).toBeGreaterThan(0);
      }
    });

    it('should import annotations from file', async () => {
      // Arrange - Create a JSON annotation file
      const annotationsToImport = [
        {
          detection_id: 'import-test-1',
          frame_number: 100,
          timestamp: 3.33,
          vru_type: 'pedestrian',
          bounding_box: { x: 50, y: 25, width: 40, height: 80 },
          occluded: false,
          truncated: false,
          difficult: false,
          validated: false,
          annotator: 'import-test'
        }
      ];

      const jsonContent = JSON.stringify({ annotations: annotationsToImport });
      const importFile = new File([jsonContent], 'import-annotations.json', { type: 'application/json' });

      // Act
      const importResult = await apiService.importAnnotations(testVideo.id, importFile, 'json');

      // Assert
      expect(importResult).toBeDefined();
      expect(importResult.imported).toBeGreaterThan(0);
      expect(Array.isArray(importResult.errors)).toBe(true);

      // Verify annotations were imported
      const videoAnnotations = await apiService.getAnnotations(testVideo.id);
      const importedAnnotation = videoAnnotations.find(a => a.detectionId === 'import-test-1');
      expect(importedAnnotation).toBeDefined();
      
      if (importedAnnotation) {
        createdAnnotationIds.push(importedAnnotation.id);
      }
    });
  });

  describe('Annotation Filtering and Search', () => {
    let testProject: Project;
    let testVideo: VideoFile;

    beforeEach(async () => {
      testProject = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(testProject.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      testVideo = await apiService.uploadVideo(testProject.id, file);
      createdVideoIds.push(testVideo.id);
    });

    it('should filter annotations by frame range', async () => {
      // Arrange - Create annotations at different frames
      const annotationsData = [
        { ...TEST_ANNOTATIONS.pedestrian, frameNumber: 100, detectionId: 'filter-test-1' },
        { ...TEST_ANNOTATIONS.cyclist, frameNumber: 200, detectionId: 'filter-test-2' },
        { ...TEST_ANNOTATIONS.pedestrian, frameNumber: 300, detectionId: 'filter-test-3' }
      ];

      for (const annotationData of annotationsData) {
        const created = await apiService.createAnnotation(testVideo.id, annotationData);
        createdAnnotationIds.push(created.id);
      }

      // Act - Get all annotations and filter client-side (API filtering would need backend support)
      const allAnnotations = await apiService.getAnnotations(testVideo.id);
      const filteredAnnotations = allAnnotations.filter(a => 
        a.frameNumber >= 150 && a.frameNumber <= 250
      );

      // Assert
      expect(filteredAnnotations).toBeDefined();
      expect(filteredAnnotations.length).toBe(1);
      expect(filteredAnnotations[0].frameNumber).toBe(200);
    });

    it('should search annotations by detection ID', async () => {
      // Arrange
      const searchDetectionId = 'search-test-unique-id';
      const annotationData = {
        ...TEST_ANNOTATIONS.pedestrian,
        detectionId: searchDetectionId
      };

      const created = await apiService.createAnnotation(testVideo.id, annotationData);
      createdAnnotationIds.push(created.id);

      // Act
      const foundAnnotations = await apiService.getAnnotationsByDetection(searchDetectionId);

      // Assert
      expect(foundAnnotations).toBeDefined();
      expect(Array.isArray(foundAnnotations)).toBe(true);
      expect(foundAnnotations.length).toBeGreaterThanOrEqual(1);
      
      const foundAnnotation = foundAnnotations.find(a => a.id === created.id);
      expect(foundAnnotation).toBeDefined();
      expect(foundAnnotation?.detectionId).toBe(searchDetectionId);
    });
  });

  describe('Annotation Data Integrity', () => {
    let testProject: Project;
    let testVideo: VideoFile;

    beforeEach(async () => {
      testProject = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(testProject.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      testVideo = await apiService.uploadVideo(testProject.id, file);
      createdVideoIds.push(testVideo.id);
    });

    it('should maintain annotation consistency when video is deleted', async () => {
      // Arrange
      const annotationData = {
        ...TEST_ANNOTATIONS.pedestrian,
        detectionId: 'consistency-test'
      };

      const created = await apiService.createAnnotation(testVideo.id, annotationData);

      // Act - Delete the video
      await apiService.deleteVideo(testVideo.id);

      // Assert - Annotation should be deleted with video (cascade delete)
      await expect(apiService.getAnnotations(testVideo.id)).rejects.toThrow();

      // Remove from cleanup lists since they're already deleted
      const videoIndex = createdVideoIds.indexOf(testVideo.id);
      if (videoIndex > -1) createdVideoIds.splice(videoIndex, 1);

      const annotationIndex = createdAnnotationIds.indexOf(created.id);
      if (annotationIndex > -1) createdAnnotationIds.splice(annotationIndex, 1);
    });

    it('should validate annotation data integrity', async () => {
      // Arrange - Try to create annotation with invalid data
      const invalidAnnotationData = {
        detectionId: 'invalid-test',
        frameNumber: -1, // Invalid frame number
        timestamp: -5.0, // Invalid timestamp
        vruType: 'invalid_type' as any, // Invalid VRU type
        boundingBox: { x: -10, y: -10, width: 0, height: 0 }, // Invalid bounding box
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        annotator: ''
      };

      // Act & Assert
      await expect(
        apiService.createAnnotation(testVideo.id, invalidAnnotationData)
      ).rejects.toThrow();
    });

    it('should handle concurrent annotation operations safely', async () => {
      // Arrange
      const annotationsData = Array.from({ length: 5 }, (_, i) => ({
        ...TEST_ANNOTATIONS.pedestrian,
        detectionId: `concurrent-test-${i}`,
        frameNumber: i * 10
      }));

      // Act - Create annotations concurrently
      const createPromises = annotationsData.map(data => 
        apiService.createAnnotation(testVideo.id, data)
      );

      const createdAnnotations = await Promise.all(createPromises);

      // Assert
      expect(createdAnnotations).toHaveLength(5);
      createdAnnotations.forEach((annotation, index) => {
        expect(annotation).toBeDefined();
        expect(annotation.id).toBeDefined();
        expect(annotation.detectionId).toBe(`concurrent-test-${index}`);
        createdAnnotationIds.push(annotation.id);
      });

      // Verify all annotations exist
      const videoAnnotations = await apiService.getAnnotations(testVideo.id);
      const createdIds = createdAnnotations.map(a => a.id);
      const videoAnnotationIds = videoAnnotations.map(a => a.id);
      
      createdIds.forEach(id => {
        expect(videoAnnotationIds).toContain(id);
      });
    });
  });
});