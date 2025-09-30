/**
 * Video Project Service
 * 
 * Service for managing many-to-many relationships between videos and projects
 * in the shared video architecture where videos have projectId: null.
 */

import { apiService } from './api';
import { Project, VideoFile } from './types';

export interface VideoProjectAssignment {
  video_id: string;
  project_id: string;
  link_id: string;
  created_at: string;
  reason?: string;
}

export interface VideoProjectCount {
  video_id: string;
  linked_project_count: number;
  is_shared: boolean;
}

export class VideoProjectService {
  /**
   * Get all projects that a video is linked to
   */
  async getVideoProjects(videoId: string): Promise<Project[]> {
    try {
      const response = await apiService.api.get(`/api/video-project-links/videos/${videoId}/projects`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get projects for video ${videoId}:`, error);
      throw error;
    }
  }

  /**
   * Get all videos linked to a project
   */
  async getProjectVideos(projectId: string, includeShared: boolean = true): Promise<VideoFile[]> {
    try {
      const response = await apiService.api.get(
        `/api/video-project-links/projects/${projectId}/videos?include_shared=${includeShared}`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to get videos for project ${projectId}:`, error);
      throw error;
    }
  }

  /**
   * Link a video to a project
   */
  async assignVideoToProject(videoId: string, projectId: string, reason?: string): Promise<VideoProjectAssignment> {
    try {
      const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
      const response = await apiService.api.post(
        `/api/video-project-links/videos/${videoId}/projects/${projectId}${params}`
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to assign video ${videoId} to project ${projectId}:`, error);
      throw error;
    }
  }

  /**
   * Remove the link between a video and project
   */
  async unassignVideoFromProject(videoId: string, projectId: string): Promise<void> {
    try {
      await apiService.api.delete(`/api/video-project-links/videos/${videoId}/projects/${projectId}`);
    } catch (error) {
      console.error(`Failed to unassign video ${videoId} from project ${projectId}:`, error);
      throw error;
    }
  }

  /**
   * Get the number of projects a video is linked to
   */
  async getVideoProjectCount(videoId: string): Promise<VideoProjectCount> {
    try {
      const response = await apiService.api.get(`/api/video-project-links/videos/${videoId}/projects/count`);
      return response.data;
    } catch (error) {
      console.error(`Failed to get project count for video ${videoId}:`, error);
      throw error;
    }
  }

  /**
   * Check if a video is linked to a specific project
   */
  async isVideoLinkedToProject(videoId: string, projectId: string): Promise<boolean> {
    try {
      const projects = await this.getVideoProjects(videoId);
      return projects.some(project => project.id === projectId);
    } catch (error) {
      console.error(`Failed to check if video ${videoId} is linked to project ${projectId}:`, error);
      return false;
    }
  }

  /**
   * Get all videos that are shared across multiple projects
   */
  async getSharedVideos(): Promise<VideoFile[]> {
    try {
      // This would require a new backend endpoint or we fetch all projects and their videos
      // For now, we'll implement a client-side approach
      const projects = await apiService.getProjects();
      const allVideoIds = new Set<string>();
      const sharedVideoIds = new Set<string>();
      
      for (const project of projects) {
        const videos = await this.getProjectVideos(project.id);
        for (const video of videos) {
          if (allVideoIds.has(video.id)) {
            sharedVideoIds.add(video.id);
          }
          allVideoIds.add(video.id);
        }
      }
      
      // Return videos that appear in multiple projects
      if (sharedVideoIds.size > 0) {
        const firstProject = projects[0];
        if (firstProject) {
          const allVideos = await this.getProjectVideos(firstProject.id);
          return allVideos.filter(video => sharedVideoIds.has(video.id));
        }
      }
      
      return [];
    } catch (error) {
      console.error('Failed to get shared videos:', error);
      return [];
    }
  }

  /**
   * Resolve project context from a list of videos
   * Returns the common project if all videos belong to the same single project
   */
  async resolveProjectContext(videos: VideoFile[]): Promise<string | null> {
    if (videos.length === 0) return null;
    
    try {
      // Get project assignments for all videos
      const videoProjectMaps = await Promise.all(
        videos.map(async (video) => ({
          videoId: video.id,
          projects: await this.getVideoProjects(video.id)
        }))
      );
      
      // Find common projects across all videos
      if (videoProjectMaps.length === 0) return null;
      
      const firstVideoProjects = new Set(videoProjectMaps[0].projects.map(p => p.id));
      
      for (let i = 1; i < videoProjectMaps.length; i++) {
        const currentVideoProjects = new Set(videoProjectMaps[i].projects.map(p => p.id));
        
        // Keep only projects that are common to all videos so far
        for (const projectId of firstVideoProjects) {
          if (!currentVideoProjects.has(projectId)) {
            firstVideoProjects.delete(projectId);
          }
        }
      }
      
      // If exactly one project is common to all videos, return it
      if (firstVideoProjects.size === 1) {
        return Array.from(firstVideoProjects)[0];
      }
      
      // No single common project
      return null;
      
    } catch (error) {
      console.error('Failed to resolve project context:', error);
      return null;
    }
  }

  /**
   * Get project name for a video (returns first linked project name)
   */
  async getVideoProjectName(videoId: string): Promise<string | null> {
    try {
      const projects = await this.getVideoProjects(videoId);
      if (projects.length > 0) {
        return projects[0].name;
      }
      return null;
    } catch (error) {
      console.error(`Failed to get project name for video ${videoId}:`, error);
      return null;
    }
  }

  /**
   * Bulk assign multiple videos to a project
   */
  async bulkAssignVideosToProject(videoIds: string[], projectId: string, reason?: string): Promise<VideoProjectAssignment[]> {
    try {
      const assignments = await Promise.all(
        videoIds.map(videoId => this.assignVideoToProject(videoId, projectId, reason))
      );
      return assignments;
    } catch (error) {
      console.error(`Failed to bulk assign videos to project ${projectId}:`, error);
      throw error;
    }
  }

  /**
   * Bulk unassign multiple videos from a project
   */
  async bulkUnassignVideosFromProject(videoIds: string[], projectId: string): Promise<void> {
    try {
      await Promise.all(
        videoIds.map(videoId => this.unassignVideoFromProject(videoId, projectId))
      );
    } catch (error) {
      console.error(`Failed to bulk unassign videos from project ${projectId}:`, error);
      throw error;
    }
  }
}

// Export singleton instance
export const videoProjectService = new VideoProjectService();
export default videoProjectService;