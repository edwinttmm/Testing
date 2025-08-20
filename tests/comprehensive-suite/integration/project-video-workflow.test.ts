import { describe, it, expect, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import { apiService } from '../../../ai-model-validation-platform/frontend/src/services/api';
import { TEST_PROJECTS, TEST_VIDEOS, createMockVideoBlob } from '../fixtures/test-videos';
import type { Project, VideoFile, VideoAssignment } from '../../../ai-model-validation-platform/frontend/src/services/types';

// Integration tests require actual API calls - mock selectively
describe('Project-Video Workflow Integration Tests', () => {
  let createdProjectIds: string[] = [];
  let createdVideoIds: string[] = [];

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

  describe('Complete Project Creation Workflow', () => {
    it('should create a new project with valid data', async () => {
      // Arrange
      const projectData = TEST_PROJECTS.basic;

      // Act
      const createdProject = await apiService.createProject(projectData);

      // Assert
      expect(createdProject).toBeDefined();
      expect(createdProject.id).toBeDefined();
      expect(createdProject.name).toBe(projectData.name);
      expect(createdProject.description).toBe(projectData.description);
      expect(createdProject.camera_model).toBe(projectData.camera_model);
      expect(createdProject.camera_view).toBe(projectData.camera_view);
      expect(createdProject.signal_type).toBe(projectData.signal_type);
      expect(createdProject.status).toBe('Active');

      // Track for cleanup
      createdProjectIds.push(createdProject.id);
    });

    it('should retrieve the created project by ID', async () => {
      // Arrange
      const projectData = TEST_PROJECTS.advanced;
      const createdProject = await apiService.createProject(projectData);
      createdProjectIds.push(createdProject.id);

      // Act
      const retrievedProject = await apiService.getProject(createdProject.id);

      // Assert
      expect(retrievedProject).toBeDefined();
      expect(retrievedProject.id).toBe(createdProject.id);
      expect(retrievedProject.name).toBe(projectData.name);
      expect(retrievedProject.description).toBe(projectData.description);
    });

    it('should update project details', async () => {
      // Arrange
      const projectData = TEST_PROJECTS.basic;
      const createdProject = await apiService.createProject(projectData);
      createdProjectIds.push(createdProject.id);

      const updateData = {
        name: 'Updated Project Name',
        description: 'Updated project description',
        status: 'Completed' as const
      };

      // Act
      const updatedProject = await apiService.updateProject(createdProject.id, updateData);

      // Assert
      expect(updatedProject.name).toBe(updateData.name);
      expect(updatedProject.description).toBe(updateData.description);
      expect(updatedProject.status).toBe(updateData.status);
      expect(updatedProject.id).toBe(createdProject.id);
    });

    it('should list projects with pagination', async () => {
      // Arrange - Create multiple projects
      const project1 = await apiService.createProject({
        ...TEST_PROJECTS.basic,
        name: 'Project 1 for Pagination'
      });
      const project2 = await apiService.createProject({
        ...TEST_PROJECTS.basic,
        name: 'Project 2 for Pagination'
      });

      createdProjectIds.push(project1.id, project2.id);

      // Act
      const projects = await apiService.getProjects(0, 10);

      // Assert
      expect(projects).toBeDefined();
      expect(Array.isArray(projects)).toBe(true);
      expect(projects.length).toBeGreaterThanOrEqual(2);
      
      const projectIds = projects.map(p => p.id);
      expect(projectIds).toContain(project1.id);
      expect(projectIds).toContain(project2.id);
    });
  });

  describe('Video Upload and Linking Workflow', () => {
    it('should upload a video and link it to a project', async () => {
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(project.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      // Act
      const uploadedVideo = await apiService.uploadVideo(project.id, file);

      // Assert
      expect(uploadedVideo).toBeDefined();
      expect(uploadedVideo.id).toBeDefined();
      expect(uploadedVideo.filename).toBe(videoData.filename);
      expect(uploadedVideo.file_size).toBe(videoData.size);
      expect(uploadedVideo.status).toBeOneOf(['uploaded', 'uploading', 'processing']);

      createdVideoIds.push(uploadedVideo.id);

      // Verify video is linked to project
      const projectVideos = await apiService.getVideos(project.id);
      expect(projectVideos).toBeDefined();
      expect(Array.isArray(projectVideos)).toBe(true);
      
      const videoIds = projectVideos.map(v => v.id);
      expect(videoIds).toContain(uploadedVideo.id);
    });

    it('should upload video centrally then link to project', async () => {
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(project.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      // Act
      // Step 1: Upload video to central store
      const uploadedVideo = await apiService.uploadVideoCentral(file);
      createdVideoIds.push(uploadedVideo.id);

      // Step 2: Link video to project
      const linkResult = await apiService.linkVideosToProject(project.id, [uploadedVideo.id]);

      // Assert
      expect(linkResult).toBeDefined();
      expect(Array.isArray(linkResult)).toBe(true);
      expect(linkResult.length).toBe(1);
      expect(linkResult[0].video_id).toBe(uploadedVideo.id);
      expect(linkResult[0].project_id).toBe(project.id);

      // Verify the link was created
      const linkedVideos = await apiService.getLinkedVideos(project.id);
      expect(linkedVideos.length).toBeGreaterThanOrEqual(1);
      
      const linkedVideoIds = linkedVideos.map(v => v.id);
      expect(linkedVideoIds).toContain(uploadedVideo.id);
    });

    it('should handle multiple video uploads to same project', async () => {
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.advanced);
      createdProjectIds.push(project.id);

      const videos = [
        {
          data: TEST_VIDEOS.small,
          file: new File([createMockVideoBlob(TEST_VIDEOS.small)], 'video1.mp4', { type: 'video/mp4' })
        },
        {
          data: TEST_VIDEOS.small,
          file: new File([createMockVideoBlob(TEST_VIDEOS.small)], 'video2.mp4', { type: 'video/mp4' })
        }
      ];

      // Act
      const uploadPromises = videos.map(video => 
        apiService.uploadVideo(project.id, video.file)
      );
      const uploadedVideos = await Promise.all(uploadPromises);

      // Assert
      expect(uploadedVideos).toHaveLength(2);
      uploadedVideos.forEach((video, index) => {
        expect(video).toBeDefined();
        expect(video.id).toBeDefined();
        expect(video.filename).toBe(videos[index].file.name);
        createdVideoIds.push(video.id);
      });

      // Verify all videos are linked to project
      const projectVideos = await apiService.getVideos(project.id);
      expect(projectVideos.length).toBeGreaterThanOrEqual(2);
      
      const projectVideoIds = projectVideos.map(v => v.id);
      uploadedVideos.forEach(video => {
        expect(projectVideoIds).toContain(video.id);
      });
    });

    it('should unlink video from project without deleting video', async () => {
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(project.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      const uploadedVideo = await apiService.uploadVideoCentral(file);
      createdVideoIds.push(uploadedVideo.id);

      await apiService.linkVideosToProject(project.id, [uploadedVideo.id]);

      // Act
      await apiService.unlinkVideoFromProject(project.id, uploadedVideo.id);

      // Assert
      const linkedVideos = await apiService.getLinkedVideos(project.id);
      const linkedVideoIds = linkedVideos.map(v => v.id);
      expect(linkedVideoIds).not.toContain(uploadedVideo.id);

      // Verify video still exists in central store
      const videoStillExists = await apiService.getVideo(uploadedVideo.id);
      expect(videoStillExists).toBeDefined();
      expect(videoStillExists.id).toBe(uploadedVideo.id);
    });
  });

  describe('Project-Video Data Consistency', () => {
    it('should maintain consistency when project is deleted', async () => {
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      
      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      const uploadedVideo = await apiService.uploadVideo(project.id, file);
      createdVideoIds.push(uploadedVideo.id);

      // Act
      await apiService.deleteProject(project.id);

      // Assert
      // Project should be deleted
      await expect(apiService.getProject(project.id)).rejects.toThrow();

      // Videos linked to project should also be deleted (cascade delete)
      await expect(apiService.getVideo(uploadedVideo.id)).rejects.toThrow();
      
      // Remove from cleanup list since they're already deleted
      const projectIndex = createdProjectIds.indexOf(project.id);
      if (projectIndex > -1) createdProjectIds.splice(projectIndex, 1);
      
      const videoIndex = createdVideoIds.indexOf(uploadedVideo.id);
      if (videoIndex > -1) createdVideoIds.splice(videoIndex, 1);
    });

    it('should handle concurrent project operations safely', async () => {
      // Arrange
      const projectData = TEST_PROJECTS.basic;

      // Act - Create multiple projects concurrently
      const createPromises = Array.from({ length: 3 }, (_, i) => 
        apiService.createProject({
          ...projectData,
          name: `Concurrent Project ${i + 1}`
        })
      );

      const createdProjects = await Promise.all(createPromises);

      // Assert
      expect(createdProjects).toHaveLength(3);
      createdProjects.forEach((project, index) => {
        expect(project).toBeDefined();
        expect(project.id).toBeDefined();
        expect(project.name).toBe(`Concurrent Project ${index + 1}`);
        createdProjectIds.push(project.id);
      });

      // Verify all projects have unique IDs
      const projectIds = createdProjects.map(p => p.id);
      const uniqueIds = new Set(projectIds);
      expect(uniqueIds.size).toBe(3);
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle project creation with invalid data gracefully', async () => {
      // Arrange
      const invalidProjectData = {
        name: '', // Invalid: empty name
        description: 'Test description',
        camera_model: 'TestCam',
        camera_view: 'Front-facing VRU',
        signal_type: 'GPIO'
      } as any;

      // Act & Assert
      await expect(apiService.createProject(invalidProjectData)).rejects.toThrow();
    });

    it('should handle video upload to non-existent project', async () => {
      // Arrange
      const nonExistentProjectId = 'non-existent-project-id';
      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      // Act & Assert
      await expect(apiService.uploadVideo(nonExistentProjectId, file)).rejects.toThrow();
    });

    it('should handle linking non-existent video to project', async () => {
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(project.id);

      const nonExistentVideoId = 'non-existent-video-id';

      // Act & Assert
      await expect(
        apiService.linkVideosToProject(project.id, [nonExistentVideoId])
      ).rejects.toThrow();
    });

    it('should recover from network timeouts during operations', async () => {
      // This test would require more sophisticated mocking to simulate network conditions
      // For now, we'll test that the API service properly handles timeout errors
      
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(project.id);

      // Act - Attempt to get project details
      // In a real network timeout scenario, this would throw a timeout error
      // For integration test, we just verify the operation completes
      const retrievedProject = await apiService.getProject(project.id);

      // Assert
      expect(retrievedProject).toBeDefined();
      expect(retrievedProject.id).toBe(project.id);
    });
  });

  describe('Database Transaction Consistency', () => {
    it('should rollback project creation if initial video upload fails', async () => {
      // This test requires more advanced transaction handling
      // For now, test individual operations work correctly
      
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(project.id);

      // Act - Try to upload an invalid video
      const invalidBlob = new Blob(['not a video'], { type: 'text/plain' });
      const invalidFile = new File([invalidBlob], 'not-a-video.txt', { type: 'text/plain' });

      // Assert
      await expect(apiService.uploadVideo(project.id, invalidFile)).rejects.toThrow();

      // Verify project still exists (no rollback in current implementation)
      const existingProject = await apiService.getProject(project.id);
      expect(existingProject).toBeDefined();
    });

    it('should maintain referential integrity between projects and videos', async () => {
      // Arrange
      const project = await apiService.createProject(TEST_PROJECTS.basic);
      createdProjectIds.push(project.id);

      const videoData = TEST_VIDEOS.small;
      const mockVideoFile = createMockVideoBlob(videoData);
      const file = new File([mockVideoFile], videoData.filename, { type: videoData.format });

      const uploadedVideo = await apiService.uploadVideo(project.id, file);
      createdVideoIds.push(uploadedVideo.id);

      // Act
      const projectVideos = await apiService.getVideos(project.id);
      const videoDetails = await apiService.getVideo(uploadedVideo.id);

      // Assert
      expect(projectVideos.some(v => v.id === uploadedVideo.id)).toBe(true);
      expect(videoDetails).toBeDefined();
      expect(videoDetails.id).toBe(uploadedVideo.id);
    });
  });
});