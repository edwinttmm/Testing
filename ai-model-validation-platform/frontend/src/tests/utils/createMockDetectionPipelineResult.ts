/**
 * Utility for creating properly typed DetectionPipelineResult mocks for tests
 * This resolves the interface alignment issues by providing a standard way to mock API responses
 */
import { DetectionPipelineResult } from '../../services/types';

export const createMockDetectionPipelineResult = (
  overrides: Partial<DetectionPipelineResult> = {}
): DetectionPipelineResult => ({
  videoId: 'test-video-123',
  detections: [],
  processingTime: 1000,
  modelUsed: 'yolov8n',
  totalDetections: 0,
  confidenceDistribution: {},
  ...overrides
});

/**
 * Converts legacy test mock objects with 'success' property to proper DetectionPipelineResult
 */
export const convertLegacyMockToDetectionPipelineResult = (
  legacyMock: any,
  videoId: string = 'test-video'
): DetectionPipelineResult => {
  return {
    videoId,
    detections: legacyMock.detections || [],
    processingTime: legacyMock.processingTime || 1000,
    modelUsed: legacyMock.modelUsed || 'test-model',
    totalDetections: legacyMock.detections?.length || 0,
    confidenceDistribution: legacyMock.confidenceDistribution || {}
  };
};

/**
 * Creates mock with realistic detection data
 */
export const createMockDetectionPipelineResultWithDetections = (
  videoId: string,
  detectionCount: number = 2
): DetectionPipelineResult => {
  const detections = Array.from({ length: detectionCount }, (_, index) => ({
    id: `det-${index + 1}`,
    detectionId: `DET_PED_${String(index + 1).padStart(4, '0')}`,
    frame: (index + 1) * 30,
    timestamp: (index + 1) * 1.0,
    vruType: index % 2 === 0 ? 'pedestrian' : 'cyclist',
    x: 100 + index * 50,
    y: 100 + index * 30,
    width: 80,
    height: 160,
    label: index % 2 === 0 ? 'person' : 'bicycle',
    confidence: 0.85 + (index * 0.05)
  }));

  return {
    videoId,
    detections,
    processingTime: 1500,
    modelUsed: 'yolov8n',
    totalDetections: detections.length,
    confidenceDistribution: {
      '0.8-0.9': Math.ceil(detections.length / 2),
      '0.9-1.0': Math.floor(detections.length / 2)
    }
  };
};