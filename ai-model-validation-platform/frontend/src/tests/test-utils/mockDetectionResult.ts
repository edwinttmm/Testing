/**
 * Test utility for creating properly typed DetectionPipelineResult mocks
 */
import { DetectionPipelineResult } from '../../services/types';

export const createMockDetectionResult = (overrides: Partial<DetectionPipelineResult> = {}): DetectionPipelineResult => ({
  videoId: 'test-video',
  detections: [],
  processingTime: 1000,
  modelUsed: 'test-model',
  totalDetections: 0,
  confidenceDistribution: {},
  ...overrides
});

export const createMockDetectionWithSuccess = (
  videoId: string,
  detections: any[] = [],
  processingTime: number = 1000
): DetectionPipelineResult => ({
  videoId,
  detections,
  processingTime,
  modelUsed: 'test-model',
  totalDetections: detections.length,
  confidenceDistribution: detections.length > 0 ? { '0.8-1.0': detections.length } : {}
});

/**
 * Converts legacy test format with 'success' property to proper DetectionPipelineResult
 */
export const convertLegacyMockResult = (legacyResult: any): DetectionPipelineResult => {
  return {
    videoId: legacyResult.videoId || 'test-video',
    detections: legacyResult.detections || [],
    processingTime: legacyResult.processingTime || 1000,
    modelUsed: legacyResult.modelUsed || 'test-model',
    totalDetections: legacyResult.detections?.length || 0,
    confidenceDistribution: legacyResult.confidenceDistribution || {}
  };
};