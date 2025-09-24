/**
 * Video Status Utility Functions
 * Centralizes video status logic and transitions
 */

import { VideoStatus, VideoValidationStatus } from '../services/types';

export interface StatusTransition {
  from: VideoStatus;
  to: VideoStatus;
  allowed: boolean;
  requiresGroundTruth?: boolean;
  description: string;
}

/**
 * Define valid status transitions
 */
export const VALID_STATUS_TRANSITIONS: StatusTransition[] = [
  {
    from: VideoStatus.UPLOADED,
    to: VideoStatus.PROCESSING,
    allowed: true,
    description: 'Start processing uploaded video'
  },
  {
    from: VideoStatus.UPLOADED,
    to: VideoStatus.VALIDATED,
    allowed: true,
    requiresGroundTruth: true,
    description: 'Direct validation for pre-processed videos'
  },
  {
    from: VideoStatus.PROCESSING,
    to: VideoStatus.COMPLETED,
    allowed: true,
    description: 'Processing completed successfully'
  },
  {
    from: VideoStatus.PROCESSING,
    to: VideoStatus.ERROR,
    allowed: true,
    description: 'Processing failed'
  },
  {
    from: VideoStatus.COMPLETED,
    to: VideoStatus.VALIDATED,
    allowed: true,
    requiresGroundTruth: true,
    description: 'Validate completed video'
  },
  {
    from: VideoStatus.VALIDATED,
    to: VideoStatus.COMPLETED,
    allowed: true,
    description: 'Invalidate video back to completed'
  },
  {
    from: VideoStatus.ERROR,
    to: VideoStatus.PROCESSING,
    allowed: true,
    description: 'Retry processing after error'
  },
  {
    from: VideoStatus.ERROR,
    to: VideoStatus.UPLOADED,
    allowed: true,
    description: 'Reset to uploaded status'
  }
];

/**
 * Check if a status transition is valid
 */
export function isValidStatusTransition(
  fromStatus: VideoStatus,
  toStatus: VideoStatus,
  hasGroundTruth: boolean = false
): boolean {
  const transition = VALID_STATUS_TRANSITIONS.find(
    t => t.from === fromStatus && t.to === toStatus
  );
  
  if (!transition || !transition.allowed) {
    return false;
  }
  
  // Check ground truth requirement
  if (transition.requiresGroundTruth && !hasGroundTruth) {
    return false;
  }
  
  return true;
}

/**
 * Get available status transitions for a video
 */
export function getAvailableTransitions(
  currentStatus: VideoStatus,
  hasGroundTruth: boolean = false
): StatusTransition[] {
  return VALID_STATUS_TRANSITIONS.filter(
    t => t.from === currentStatus && 
    t.allowed && 
    (!t.requiresGroundTruth || hasGroundTruth)
  );
}

/**
 * Get status display information
 */
export interface StatusDisplayInfo {
  label: string;
  color: 'success' | 'warning' | 'error' | 'info' | 'default';
  description: string;
  icon: string;
}

export function getStatusDisplayInfo(status: VideoStatus): StatusDisplayInfo {
  switch (status) {
    case VideoStatus.UPLOADED:
      return {
        label: 'Uploaded',
        color: 'info',
        description: 'Video uploaded and ready for processing',
        icon: '📥'
      };
    case VideoStatus.PROCESSING:
      return {
        label: 'Processing',
        color: 'warning',
        description: 'AI processing in progress',
        icon: '⚙️'
      };
    case VideoStatus.COMPLETED:
      return {
        label: 'Completed',
        color: 'warning',
        description: 'Processing completed, awaiting validation',
        icon: '✅'
      };
    case VideoStatus.VALIDATED:
      return {
        label: 'Validated',
        color: 'success',
        description: 'Video validated and ready for testing',
        icon: '🔍'
      };
    case VideoStatus.ERROR:
      return {
        label: 'Error',
        color: 'error',
        description: 'Processing failed',
        icon: '❌'
      };
    case VideoStatus.PENDING_ANNOTATION:
      return {
        label: 'Pending Annotation',
        color: 'info',
        description: 'Waiting for manual annotation',
        icon: '📝'
      };
    case VideoStatus.PENDING_VALIDATION:
      return {
        label: 'Pending Validation',
        color: 'warning',
        description: 'Waiting for validation review',
        icon: '⏳'
      };
    default:
      return {
        label: 'Unknown',
        color: 'default',
        description: 'Unknown status',
        icon: '❓'
      };
  }
}

/**
 * Check if video is ready for testing
 */
export function isVideoReadyForTesting(
  status: VideoStatus,
  hasGroundTruth: boolean
): boolean {
  return status === VideoStatus.VALIDATED && hasGroundTruth;
}

/**
 * Check if video can be validated
 */
export function canValidateVideo(
  status: VideoStatus,
  hasGroundTruth: boolean
): boolean {
  return isValidStatusTransition(status, VideoStatus.VALIDATED, hasGroundTruth);
}

/**
 * Check if video can be invalidated
 */
export function canInvalidateVideo(status: VideoStatus): boolean {
  return status === VideoStatus.VALIDATED;
}

/**
 * Get status priority for sorting (lower number = higher priority)
 */
export function getStatusPriority(status: VideoStatus): number {
  switch (status) {
    case VideoStatus.ERROR:
      return 1; // Highest priority - needs attention
    case VideoStatus.PROCESSING:
      return 2; // High priority - in progress
    case VideoStatus.COMPLETED:
      return 3; // Medium priority - ready for validation
    case VideoStatus.UPLOADED:
      return 4; // Medium priority - ready for processing
    case VideoStatus.PENDING_VALIDATION:
      return 5; // Lower priority - waiting
    case VideoStatus.PENDING_ANNOTATION:
      return 6; // Lower priority - waiting
    case VideoStatus.VALIDATED:
      return 7; // Lowest priority - complete
    default:
      return 8; // Unknown status
  }
}

/**
 * Filter videos by status
 */
export function filterVideosByStatus(
  videos: Array<{ status: VideoStatus }>,
  statuses: VideoStatus[]
): Array<{ status: VideoStatus }> {
  return videos.filter(video => statuses.includes(video.status));
}

/**
 * Group videos by status
 */
export function groupVideosByStatus<T extends { status: VideoStatus }>(
  videos: T[]
): Record<VideoStatus, T[]> {
  return videos.reduce((groups, video) => {
    const status = video.status;
    if (!groups[status]) {
      groups[status] = [];
    }
    groups[status].push(video);
    return groups;
  }, {} as Record<VideoStatus, T[]>);
}

/**
 * Convert VideoValidationStatus to VideoStatus for compatibility
 */
export function convertValidationStatusToVideoStatus(validationStatus: VideoValidationStatus): VideoStatus {
  const statusMapping: Record<VideoValidationStatus, VideoStatus> = {
    [VideoValidationStatus.UPLOADED]: VideoStatus.UPLOADED,
    [VideoValidationStatus.PROCESSING]: VideoStatus.PROCESSING,
    [VideoValidationStatus.PROCESSING_FAILED]: VideoStatus.ERROR,
    [VideoValidationStatus.ANNOTATED]: VideoStatus.COMPLETED,
    [VideoValidationStatus.VALIDATING]: VideoStatus.PROCESSING,
    [VideoValidationStatus.VALIDATION_FAILED]: VideoStatus.ERROR,
    [VideoValidationStatus.VALIDATED]: VideoStatus.VALIDATED,
    [VideoValidationStatus.READY_FOR_TESTING]: VideoStatus.VALIDATED,
    [VideoValidationStatus.IN_TESTING]: VideoStatus.VALIDATED,
    [VideoValidationStatus.TESTED]: VideoStatus.VALIDATED,
    [VideoValidationStatus.ARCHIVED]: VideoStatus.VALIDATED,
    [VideoValidationStatus.ERROR]: VideoStatus.ERROR
  };
  
  return statusMapping[validationStatus] || VideoStatus.UPLOADED;
}

/**
 * Convert VideoStatus to VideoValidationStatus for compatibility
 */
export function convertVideoStatusToValidationStatus(videoStatus: VideoStatus): VideoValidationStatus {
  const statusMapping: Record<VideoStatus, VideoValidationStatus> = {
    [VideoStatus.UPLOADED]: VideoValidationStatus.UPLOADED,
    [VideoStatus.PROCESSING]: VideoValidationStatus.PROCESSING,
    [VideoStatus.COMPLETED]: VideoValidationStatus.ANNOTATED,
    [VideoStatus.VALIDATED]: VideoValidationStatus.VALIDATED,
    [VideoStatus.ERROR]: VideoValidationStatus.ERROR,
    [VideoStatus.PENDING_ANNOTATION]: VideoValidationStatus.ANNOTATED,
    [VideoStatus.PENDING_VALIDATION]: VideoValidationStatus.VALIDATING
  };
  
  return statusMapping[videoStatus] || VideoValidationStatus.UPLOADED;
}

/**
 * Check if two status values are equivalent (cross-enum compatibility)
 */
export function isStatusEquivalent(
  status1: VideoStatus | VideoValidationStatus,
  status2: VideoStatus | VideoValidationStatus
): boolean {
  // If both are the same type, do direct comparison
  if (typeof status1 === typeof status2) {
    return status1 === status2;
  }
  
  // Convert both to VideoStatus for comparison
  const normalizedStatus1 = typeof status1 === 'string' && status1 in VideoValidationStatus 
    ? convertValidationStatusToVideoStatus(status1 as VideoValidationStatus)
    : status1 as VideoStatus;
    
  const normalizedStatus2 = typeof status2 === 'string' && status2 in VideoValidationStatus
    ? convertValidationStatusToVideoStatus(status2 as VideoValidationStatus) 
    : status2 as VideoStatus;
    
  return normalizedStatus1 === normalizedStatus2;
}