import { 
  getProjectContext, 
  deriveProjectFromVideos, 
  validateProjectContextForAnnotation,
  getProjectContextDescription,
  isProjectContextMixed,
  getProjectContextStats
} from '../projectContext';
import { VideoFile } from '../../services/types';

// Mock video data
const mockVideo1: VideoFile = {
  id: 'video-1',
  projectId: 'project-123',
  filename: 'test1.mp4',
  originalName: 'test1.mp4',
  size: 1024,
  duration: 30,
  uploadedAt: '2023-01-01T00:00:00Z',
  url: 'http://example.com/video1.mp4',
  status: 'completed'
};

const mockVideo2: VideoFile = {
  id: 'video-2',
  projectId: 'project-456',
  filename: 'test2.mp4',
  originalName: 'test2.mp4',
  size: 2048,
  duration: 45,
  uploadedAt: '2023-01-01T00:00:00Z',
  url: 'http://example.com/video2.mp4',
  status: 'completed'
};

const mockVideoNoProject: VideoFile = {
  id: 'video-3',
  projectId: '',
  filename: 'test3.mp4',
  originalName: 'test3.mp4',
  size: 1536,
  duration: 60,
  uploadedAt: '2023-01-01T00:00:00Z',
  url: 'http://example.com/video3.mp4',
  status: 'completed'
};

describe('projectContext utils', () => {
  describe('getProjectContext', () => {
    it('should prioritize URL project ID', () => {
      const result = getProjectContext({
        urlProjectId: 'url-project',
        selectedVideo: mockVideo1,
        derivedProjectId: 'derived-project'
      });
      
      expect(result.projectId).toBe('url-project');
      expect(result.source).toBe('url');
      expect(result.confidence).toBe('high');
    });

    it('should use video project ID if no URL project ID', () => {
      const result = getProjectContext({
        selectedVideo: mockVideo1,
        derivedProjectId: 'derived-project'
      });
      
      expect(result.projectId).toBe('project-123');
      expect(result.source).toBe('video');
      expect(result.confidence).toBe('high');
    });

    it('should use derived project ID as fallback', () => {
      const result = getProjectContext({
        selectedVideo: mockVideoNoProject,
        derivedProjectId: 'derived-project'
      });
      
      expect(result.projectId).toBe('derived-project');
      expect(result.source).toBe('derived');
      expect(result.confidence).toBe('medium');
    });

    it('should return no context when nothing available', () => {
      const result = getProjectContext({
        selectedVideo: mockVideoNoProject
      });
      
      expect(result.projectId).toBeNull();
      expect(result.source).toBe('none');
      expect(result.confidence).toBe('low');
    });
  });

  describe('deriveProjectFromVideos', () => {
    it('should return project ID when all videos have same project', () => {
      const videos = [
        { ...mockVideo1, projectId: 'same-project' },
        { ...mockVideo2, projectId: 'same-project' }
      ];
      
      const result = deriveProjectFromVideos(videos);
      expect(result).toBe('same-project');
    });

    it('should return null when videos have different projects', () => {
      const videos = [mockVideo1, mockVideo2];
      
      const result = deriveProjectFromVideos(videos);
      expect(result).toBeNull();
    });

    it('should return null for empty array', () => {
      const result = deriveProjectFromVideos([]);
      expect(result).toBeNull();
    });
  });

  describe('validateProjectContextForAnnotation', () => {
    it('should validate high confidence context', () => {
      const context = {
        projectId: 'project-123',
        source: 'url' as const,
        confidence: 'high' as const
      };
      
      const result = validateProjectContextForAnnotation(context);
      expect(result.valid).toBe(true);
      expect(result.reason).toBeUndefined();
    });

    it('should reject context without project ID', () => {
      const context = {
        projectId: null,
        source: 'none' as const,
        confidence: 'low' as const
      };
      
      const result = validateProjectContextForAnnotation(context);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain('No project context available');
    });

    it('should reject low confidence context', () => {
      const context = {
        projectId: 'project-123',
        source: 'derived' as const,
        confidence: 'low' as const
      };
      
      const result = validateProjectContextForAnnotation(context);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain('confidence is too low');
    });
  });

  describe('getProjectContextStats', () => {
    it('should calculate stats correctly', () => {
      const videos = [mockVideo1, mockVideo2, mockVideoNoProject];
      
      const stats = getProjectContextStats(videos);
      
      expect(stats.totalVideos).toBe(3);
      expect(stats.assignedVideos).toBe(2);
      expect(stats.unassignedVideos).toBe(1);
      expect(stats.projectCount).toBe(2);
      expect(stats.isMixed).toBe(true);
      expect(stats.projects).toContain('project-123');
      expect(stats.projects).toContain('project-456');
    });
  });
});