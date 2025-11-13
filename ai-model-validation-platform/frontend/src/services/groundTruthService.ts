/**
 * Ground Truth Service - Frontend Integration
 * Handles ground truth upload and validation
 */

import api from './api';

export interface GroundTruthUploadResponse {
  video_id: string;
  objects_created: number;
  objects_skipped: number;
  filename: string;
  status: string;
}

export interface GroundTruthValidationResponse {
  video_id: string;
  ground_truth_count: number;
  has_ground_truth: boolean;
  status: 'valid' | 'no_ground_truth';
}

export interface GroundTruthObject {
  timestamp?: number;
  video_time_seconds?: number;
  frame_number?: number;
  class_label?: string;
  vru_type?: string;
  class?: string;
  tracking_id?: string;
  confidence?: number;
  bbox_x?: number;
  bbox_y?: number;
  bbox_width?: number;
  bbox_height?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  validated?: boolean;
  difficult?: boolean;
}

/**
 * Upload ground truth file for a video
 *
 * @param videoId - Video ID to upload ground truth for
 * @param file - JSON or CSV file with ground truth data
 * @returns Upload result with objects created count
 */
export async function uploadGroundTruth(
  videoId: string,
  file: File
): Promise<GroundTruthUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`/api/ground-truth?video_id=${videoId}`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to upload ground truth');
  }

  return response.json();
}

/**
 * Validate ground truth availability for a video
 *
 * @param videoId - Video ID to validate
 * @returns Validation result with ground truth count and status
 */
export async function validateGroundTruth(
  videoId: string
): Promise<GroundTruthValidationResponse> {
  const response = await api.get(`/api/ground-truth/videos/${videoId}/ground-truth/validate`);
  return response.data;
}

/**
 * Check if a video has ground truth data
 *
 * @param videoId - Video ID to check
 * @returns True if video has ground truth data
 */
export async function hasGroundTruth(videoId: string): Promise<boolean> {
  try {
    const result = await validateGroundTruth(videoId);
    return result.has_ground_truth;
  } catch (error) {
    console.error('Error checking ground truth availability:', error);
    return false;
  }
}

/**
 * Example JSON format for ground truth upload:
 *
 * {
 *   "objects": [
 *     {
 *       "timestamp": 1.5,
 *       "class_label": "pedestrian",
 *       "frame_number": 45,
 *       "tracking_id": "track-001",
 *       "confidence": 0.95,
 *       "bbox_x": 100,
 *       "bbox_y": 200,
 *       "bbox_width": 50,
 *       "bbox_height": 80,
 *       "validated": true
 *     }
 *   ]
 * }
 *
 * Example CSV format:
 *
 * timestamp,class_label,frame_number,confidence,bbox_x,bbox_y,bbox_width,bbox_height
 * 1.5,pedestrian,45,0.95,100,200,50,80
 * 2.0,cyclist,60,0.88,150,250,60,90
 */
