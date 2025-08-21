import { VideoFile } from '../services/types';

export interface ProjectContextResult {
  projectId: string | null;
  source: 'url' | 'video' | 'derived' | 'none';
  confidence: 'high' | 'medium' | 'low';
}

export interface ProjectContextOptions {
  urlProjectId?: string | null;
  selectedVideo?: VideoFile | null;
  derivedProjectId?: string | null;
  videos?: VideoFile[];
}

/**
 * Determines the best available project context for operations
 * Priority order: URL project ID > Video's project ID > Derived project ID
 */
export function getProjectContext(options: ProjectContextOptions): ProjectContextResult {
  const { urlProjectId, selectedVideo, derivedProjectId, videos = [] } = options;
  
  // Priority 1: URL project ID (highest confidence)
  if (urlProjectId) {
    return {
      projectId: urlProjectId,
      source: 'url',
      confidence: 'high'
    };
  }
  
  // Priority 2: Video's project ID (high confidence)
  const videoProjectId = selectedVideo?.projectId;
  if (videoProjectId) {
    return {
      projectId: videoProjectId,
      source: 'video',
      confidence: 'high'
    };
  }
  
  // Priority 3: Derived project ID (medium confidence)
  if (derivedProjectId) {
    return {
      projectId: derivedProjectId,
      source: 'derived',
      confidence: 'medium'
    };
  }
  
  // No project context available
  return {
    projectId: null,
    source: 'none',
    confidence: 'low'
  };
}

/**
 * Derives project context from a collection of videos
 * Returns the project ID if all videos belong to the same project
 */
export function deriveProjectFromVideos(videos: VideoFile[]): string | null {
  if (videos.length === 0) return null;
  
  const projectIds = [...new Set(videos.map(v => v.projectId).filter(Boolean))];
  
  // If all videos belong to the same project, return that project ID
  if (projectIds.length === 1 && projectIds[0]) {
    return projectIds[0];
  }
  
  // If videos belong to multiple projects or no project, return null
  return null;
}

/**
 * Validates if a project context is sufficient for annotation operations
 */
export function validateProjectContextForAnnotation(context: ProjectContextResult): {
  valid: boolean;
  reason?: string;
} {
  if (!context.projectId) {
    return {
      valid: false,
      reason: 'No project context available. Video must be associated with a project to enable annotations.'
    };
  }
  
  if (context.confidence === 'low') {
    return {
      valid: false,
      reason: 'Project context confidence is too low for annotation operations.'
    };
  }
  
  return { valid: true };
}

/**
 * Gets a human-readable description of the project context source
 */
export function getProjectContextDescription(context: ProjectContextResult): string {
  const { projectId, source, confidence } = context;
  
  if (!projectId) {
    return 'No project context available';
  }
  
  const projectIdDisplay = projectId.length > 8 ? `${projectId.slice(0, 8)}...` : projectId;
  
  switch (source) {
    case 'url':
      return `Project: ${projectIdDisplay} (from URL)`;
    case 'video':
      return `Project: ${projectIdDisplay} (from video metadata)`;
    case 'derived':
      return `Project: ${projectIdDisplay} (derived from videos)`;
    default:
      return `Project: ${projectIdDisplay} (unknown source)`;
  }
}

/**
 * Determines if project context is mixed (videos from different projects)
 */
export function isProjectContextMixed(videos: VideoFile[]): boolean {
  if (videos.length === 0) return false;
  
  const projectIds = [...new Set(videos.map(v => v.projectId).filter(Boolean))];
  return projectIds.length > 1;
}

/**
 * Gets statistics about project context in a video collection
 */
export function getProjectContextStats(videos: VideoFile[]): {
  totalVideos: number;
  assignedVideos: number;
  unassignedVideos: number;
  projectCount: number;
  projects: string[];
  isMixed: boolean;
} {
  const totalVideos = videos.length;
  const assignedVideos = videos.filter(v => v.projectId).length;
  const unassignedVideos = totalVideos - assignedVideos;
  
  const projects = [...new Set(videos.map(v => v.projectId).filter(Boolean))];
  const projectCount = projects.length;
  const isMixed = projectCount > 1;
  
  return {
    totalVideos,
    assignedVideos,
    unassignedVideos,
    projectCount,
    projects,
    isMixed
  };
}