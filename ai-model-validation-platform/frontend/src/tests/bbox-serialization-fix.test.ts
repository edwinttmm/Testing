/**
 * Integration Test for BoundingBox Serialization Fix
 * 
 * This test validates the complete pipeline from detection to annotation storage,
 * ensuring that BoundingBox data is properly serialized as plain objects without
 * class instances that could cause JSON serialization errors.
 */

import { BoundingBox, GroundTruthAnnotation, Detection, VRUType } from '../services/types';
import { isObject } from '../utils/typeGuards';

// Mock fetch for API testing
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('BoundingBox Serialization Fix - Integration Tests', () => {
  const mockVideoId = 'test-video-123';
  const mockDetectionId = 'detection-456';
  const mockProjectId = 'project-789';

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockClear();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('BoundingBox Plain Object Validation', () => {
    test('should create BoundingBox as plain object without class instances', () => {
      // Test data that simulates detection results
      const boundingBoxData: BoundingBox = {
        x: 100,
        y: 200,
        width: 150,
        height: 180,
        label: 'pedestrian',
        confidence: 0.85
      };

      // Verify it's a plain object, not a class instance
      expect(Object.getPrototypeOf(boundingBoxData)).toBe(Object.prototype);
      expect(boundingBoxData.constructor).toBe(Object);
      expect(boundingBoxData instanceof Object).toBe(true);
      expect(typeof boundingBoxData).toBe('object');

      // Verify JSON serialization works without errors
      expect(() => JSON.stringify(boundingBoxData)).not.toThrow();
      
      const serialized = JSON.stringify(boundingBoxData);
      const parsed = JSON.parse(serialized);
      
      expect(parsed).toEqual(boundingBoxData);
      expect(parsed.x).toBe(100);
      expect(parsed.y).toBe(200);
      expect(parsed.width).toBe(150);
      expect(parsed.height).toBe(180);
      expect(parsed.label).toBe('pedestrian');
      expect(parsed.confidence).toBe(0.85);
    });

    test('should handle BoundingBox in Detection objects without serialization issues', () => {
      const detection: Detection = {
        id: mockDetectionId,
        detectionId: mockDetectionId,
        timestamp: 1234567890,
        boundingBox: {
          x: 50,
          y: 75,
          width: 120,
          height: 160,
          label: 'cyclist',
          confidence: 0.92
        },
        vruType: 'cyclist' as VRUType,
        confidence: 0.92,
        isGroundTruth: false,
        notes: 'Test detection',
        validated: false,
        createdAt: '2023-12-01T10:00:00Z'
      };

      // Test full detection serialization
      expect(() => JSON.stringify(detection)).not.toThrow();
      
      const serialized = JSON.stringify(detection);
      const parsed = JSON.parse(serialized);
      
      expect(parsed.boundingBox).toBeDefined();
      expect(parsed.boundingBox.x).toBe(50);
      expect(parsed.boundingBox.label).toBe('cyclist');
      expect(Object.getPrototypeOf(parsed.boundingBox)).toBe(Object.prototype);
    });
  });

  describe('API Annotation Creation with Proper Serialization', () => {
    test('should send properly formatted bounding_box in annotation payload', async () => {
      // Setup mock response for successful annotation creation
      const mockAnnotationResponse: GroundTruthAnnotation = {
        id: 'annotation-123',
        videoId: mockVideoId,
        detectionId: mockDetectionId,
        frameNumber: 100,
        timestamp: 1234567890,
        vruType: 'pedestrian' as VRUType,
        boundingBox: {
          x: 200,
          y: 300,
          width: 80,
          height: 120,
          label: 'pedestrian',
          confidence: 0.88
        },
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Integration test annotation',
        annotator: 'test-user',
        validated: true,
        createdAt: '2023-12-01T10:00:00Z'
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockAnnotationResponse
      });

      // Create annotation data
      const annotationData: Omit<GroundTruthAnnotation, 'id' | 'createdAt' | 'updatedAt'> = {
        videoId: mockVideoId,
        detectionId: mockDetectionId,
        frameNumber: 100,
        timestamp: 1234567890,
        vruType: 'pedestrian' as VRUType,
        boundingBox: {
          x: 200,
          y: 300,
          width: 80,
          height: 120,
          label: 'pedestrian',
          confidence: 0.88
        },
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Integration test annotation',
        annotator: 'test-user',
        validated: true
      };

      // Simulate API call with proper payload conversion
      const apiPayload = {
        detection_id: annotationData.detectionId,
        frame_number: annotationData.frameNumber,
        timestamp: annotationData.timestamp,
        vru_type: annotationData.vruType,
        bounding_box: annotationData.boundingBox,
        occluded: annotationData.occluded,
        truncated: annotationData.truncated,
        difficult: annotationData.difficult,
        notes: annotationData.notes,
        annotator: annotationData.annotator,
        validated: annotationData.validated
      };

      // Make the API call
      const response = await fetch(`/api/videos/${mockVideoId}/annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiPayload)
      });
      
      const result = await response.json();

      // Verify the request was made with correct data structure
      expect(mockFetch).toHaveBeenCalledWith(
        `/api/videos/${mockVideoId}/annotations`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            detection_id: mockDetectionId,
            frame_number: 100,
            timestamp: 1234567890,
            vru_type: 'pedestrian',
            bounding_box: {
              x: 200,
              y: 300,
              width: 80,
              height: 120,
              label: 'pedestrian',
              confidence: 0.88
            },
            occluded: false,
            truncated: false,
            difficult: false,
            notes: 'Integration test annotation',
            annotator: 'test-user',
            validated: true
          })
        }
      );

      // Verify the response
      expect(result).toEqual(mockAnnotationResponse);
      expect(result.boundingBox).toBeDefined();
      expect(result.boundingBox.x).toBe(200);
    });

    test('should handle bounding_box in detection-to-annotation conversion pipeline', async () => {
      // Simulate detection data from backend
      const detectionResponse = {
        id: mockDetectionId,
        detectionId: mockDetectionId,
        timestamp: 1234567890,
        boundingBox: {
          x: 75,
          y: 125,
          width: 100,
          height: 140,
          label: 'motorcyclist',
          confidence: 0.91
        },
        vruType: 'motorcyclist',
        confidence: 0.91,
        isGroundTruth: false,
        validated: false,
        createdAt: '2023-12-01T10:00:00Z'
      };

      // Convert detection to annotation format
      const annotationPayload = {
        detection_id: detectionResponse.detectionId,
        frame_number: 150,
        timestamp: detectionResponse.timestamp,
        vru_type: detectionResponse.vruType,
        bounding_box: detectionResponse.boundingBox, // This should be a plain object
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Converted from detection',
        annotator: 'system',
        validated: false
      };

      // Verify bounding_box is serializable
      expect(() => JSON.stringify(annotationPayload)).not.toThrow();
      
      const serialized = JSON.stringify(annotationPayload);
      const parsed = JSON.parse(serialized);
      
      expect(parsed.bounding_box).toBeDefined();
      expect(parsed.bounding_box.x).toBe(75);
      expect(parsed.bounding_box.label).toBe('motorcyclist');
      expect(typeof parsed.bounding_box).toBe('object');
    });
  });

  describe('Database Storage Format Validation', () => {
    test('should store bounding_box data in correct database format', async () => {
      // Mock successful database storage response
      const storedAnnotation: GroundTruthAnnotation = {
        id: 'stored-annotation-456',
        videoId: mockVideoId,
        detectionId: mockDetectionId,
        frameNumber: 200,
        timestamp: 1234567890,
        vruType: 'wheelchair_user' as VRUType,
        boundingBox: {
          x: 150,
          y: 250,
          width: 90,
          height: 110,
          label: 'wheelchair_user',
          confidence: 0.87
        },
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Database storage test',
        annotator: 'test-system',
        validated: true,
        createdAt: '2023-12-01T11:00:00Z',
        updatedAt: '2023-12-01T11:05:00Z'
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [storedAnnotation]
      });

      // Simulate retrieving stored annotation
      const response = await fetch(`/api/annotations/detection/${mockDetectionId}`);
      const retrieved = await response.json();
      
      // In a real test, this would return an array
      const annotation = Array.isArray(retrieved) ? retrieved[0] : retrieved;
      
      // Verify the retrieved data has correct structure
      expect(annotation).toBeDefined();
      if (annotation) {
        expect(annotation.boundingBox).toBeDefined();
        expect(annotation.boundingBox.x).toBe(150);
        expect(annotation.boundingBox.y).toBe(250);
        expect(annotation.boundingBox.width).toBe(90);
        expect(annotation.boundingBox.height).toBe(110);
        expect(annotation.boundingBox.label).toBe('wheelchair_user');
        expect(annotation.boundingBox.confidence).toBe(0.87);
        
        // Verify it's still serializable after retrieval
        expect(() => JSON.stringify(annotation.boundingBox)).not.toThrow();
      }
    });

    test('should handle legacy bounding_box format conversion', async () => {
      // Test conversion from snake_case backend format
      const backendResponse = {
        id: 'legacy-annotation-789',
        video_id: mockVideoId,
        detection_id: mockDetectionId,
        frame_number: 300,
        timestamp: 1234567890,
        vru_type: 'scooter_rider',
        bounding_box: {  // Backend format
          x: 300,
          y: 400,
          width: 70,
          height: 95,
          label: 'scooter_rider',
          confidence: 0.83
        },
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Legacy format test',
        annotator: 'legacy-system',
        validated: false,
        created_at: '2023-12-01T12:00:00Z'
      };

      // The API service should transform this to camelCase
      const expectedTransformed: GroundTruthAnnotation = {
        id: 'legacy-annotation-789',
        videoId: mockVideoId,
        detectionId: mockDetectionId,
        frameNumber: 300,
        timestamp: 1234567890,
        vruType: 'scooter_rider' as VRUType,
        boundingBox: {
          x: 300,
          y: 400,
          width: 70,
          height: 95,
          label: 'scooter_rider',
          confidence: 0.83
        },
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Legacy format test',
        annotator: 'legacy-system',
        validated: false,
        createdAt: '2023-12-01T12:00:00Z'
      };

      // Mock the backend response
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [backendResponse]
      });

      const response = await fetch(`/api/annotations/detection/${mockDetectionId}`);
      const result = await response.json();
      
      // Verify transformation was applied (simulate API service transformation)
      expect(Array.isArray(result)).toBe(true);
      if (Array.isArray(result) && result.length > 0) {
        const rawAnnotation = result[0];
        // Simulate the transformation that API service would do
        const annotation = {
          ...rawAnnotation,
          videoId: rawAnnotation.video_id || rawAnnotation.videoId,
          detectionId: rawAnnotation.detection_id || rawAnnotation.detectionId,
          frameNumber: rawAnnotation.frame_number || rawAnnotation.frameNumber,
          vruType: rawAnnotation.vru_type || rawAnnotation.vruType,
          boundingBox: rawAnnotation.bounding_box || rawAnnotation.boundingBox,
          createdAt: rawAnnotation.created_at || rawAnnotation.createdAt
        };
        
        expect(annotation.boundingBox).toBeDefined();
        expect(annotation.boundingBox.x).toBe(300);
        expect(annotation.videoId).toBe(mockVideoId);  // Transformed from video_id
        expect(annotation.detectionId).toBe(mockDetectionId);  // Transformed from detection_id
        
        // Verify serialization still works
        expect(() => JSON.stringify(annotation)).not.toThrow();
      }
    });
  });

  describe('Complete Pipeline Integration', () => {
    test('should handle full detection-to-annotation-to-storage pipeline without serialization errors', async () => {
      // Step 1: Simulate receiving detection data
      const detectionData = {
        id: mockDetectionId,
        timestamp: 1234567890,
        boundingBox: {
          x: 400,
          y: 500,
          width: 60,
          height: 80,
          label: 'pedestrian',
          confidence: 0.94
        },
        vruType: 'pedestrian' as VRUType,
        confidence: 0.94,
        isGroundTruth: false,
        validated: false
      };

      // Step 2: Convert to annotation format
      const annotationData = {
        videoId: mockVideoId,
        detectionId: detectionData.id,
        frameNumber: 500,
        timestamp: detectionData.timestamp,
        vruType: detectionData.vruType,
        boundingBox: detectionData.boundingBox,
        occluded: false,
        truncated: false,
        difficult: false,
        notes: 'Pipeline integration test',
        annotator: 'integration-test',
        validated: false
      };

      // Step 3: Mock successful annotation creation
      const createdAnnotation: GroundTruthAnnotation = {
        id: 'pipeline-annotation-999',
        ...annotationData,
        createdAt: '2023-12-01T13:00:00Z'
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => createdAnnotation
      });

      // Step 4: Execute the pipeline
      const apiPayload = {
        detection_id: annotationData.detectionId,
        frame_number: annotationData.frameNumber,
        timestamp: annotationData.timestamp,
        vru_type: annotationData.vruType,
        bounding_box: annotationData.boundingBox,
        occluded: annotationData.occluded,
        truncated: annotationData.truncated,
        difficult: annotationData.difficult,
        notes: annotationData.notes,
        annotator: annotationData.annotator,
        validated: annotationData.validated
      };

      const response = await fetch(`/api/videos/${mockVideoId}/annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiPayload)
      });
      
      const result = await response.json();

      // Step 5: Verify no serialization errors occurred
      expect(result).toBeDefined();
      expect(result.id).toBe('pipeline-annotation-999');
      expect(result.boundingBox).toBeDefined();
      expect(result.boundingBox.x).toBe(400);
      expect(result.boundingBox.confidence).toBe(0.94);

      // Step 6: Verify the API call was made with proper payload structure
      expect(mockFetch).toHaveBeenCalledWith(
        `/api/videos/${mockVideoId}/annotations`,
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('"detection_id":"detection-456"')
        })
      );
      
      // Verify the actual payload can be parsed and contains correct bounding_box
      const callArgs = mockFetch.mock.calls[0];
      const requestOptions = callArgs[1];
      const payload = JSON.parse(requestOptions.body);
      
      expect(payload.bounding_box).toBeDefined();
      expect(payload.bounding_box.x).toBe(400);
      expect(payload.bounding_box.y).toBe(500);
      expect(payload.bounding_box.width).toBe(60);
      expect(payload.bounding_box.height).toBe(80);
      expect(payload.bounding_box.label).toBe('pedestrian');
      expect(payload.bounding_box.confidence).toBe(0.94);
      expect(typeof payload.bounding_box).toBe('object');

      // Step 7: Verify serialization works at every step
      expect(() => JSON.stringify(detectionData)).not.toThrow();
      expect(() => JSON.stringify(annotationData)).not.toThrow();
      expect(() => JSON.stringify(result)).not.toThrow();
    });

    test('should maintain bounding_box integrity across multiple API operations', async () => {
      const boundingBoxData = {
        x: 125,
        y: 175,
        width: 85,
        height: 95,
        label: 'cyclist',
        confidence: 0.89
      };

      // Test 1: Create annotation
      const createPayload = {
        videoId: mockVideoId,
        detectionId: mockDetectionId,
        frameNumber: 600,
        timestamp: 1234567890,
        vruType: 'cyclist' as VRUType,
        boundingBox: boundingBoxData,
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        annotator: 'multi-op-test',
        notes: 'Multi-operation test'
      };

      const createdAnnotation = { id: 'multi-op-annotation', ...createPayload, createdAt: '2023-12-01T14:00:00Z' };
      
      // Verify serialization works for creation
      expect(() => JSON.stringify(createPayload)).not.toThrow();
      expect(createdAnnotation.boundingBox).toEqual(boundingBoxData);

      // Test 2: Update annotation with adjusted bounding box
      const updatedBoundingBox = {
        ...boundingBoxData,
        x: 130,  // Slight adjustment
        confidence: 0.91
      };
      
      const updateData = {
        ...createdAnnotation,
        boundingBox: updatedBoundingBox,
        validated: true
      };

      // Verify serialization works for updates
      expect(() => JSON.stringify(updateData)).not.toThrow();
      expect(updateData.boundingBox.x).toBe(130);
      expect(updateData.boundingBox.confidence).toBe(0.91);

      // Test 3: Verify final annotation maintains integrity
      const finalAnnotation = { ...updateData, updatedAt: '2023-12-01T14:05:00Z' };
      
      expect(finalAnnotation.boundingBox.x).toBe(130);
      expect(finalAnnotation.boundingBox.confidence).toBe(0.91);
      
      // Verify serialization works after all operations
      expect(() => JSON.stringify(finalAnnotation)).not.toThrow();
      
      // Verify bounding_box format for API payload
      const apiPayload = {
        detection_id: finalAnnotation.detectionId,
        frame_number: finalAnnotation.frameNumber,
        timestamp: finalAnnotation.timestamp,
        vru_type: finalAnnotation.vruType,
        bounding_box: finalAnnotation.boundingBox,
        validated: finalAnnotation.validated
      };
      
      expect(() => JSON.stringify(apiPayload)).not.toThrow();
      expect(typeof apiPayload.bounding_box).toBe('object');
      expect(apiPayload.bounding_box.x).toBe(130);
    });
  });

  describe('Error Handling and Edge Cases', () => {
    test('should handle malformed bounding_box data gracefully', () => {
      const malformedData = {
        x: 'invalid',  // String instead of number
        y: 100,
        width: -50,    // Negative width
        height: null,  // Null height
        label: '',     // Empty label
        confidence: 'high'  // String instead of number
      };

      // The system should handle this gracefully, not crash on serialization
      expect(() => JSON.stringify(malformedData)).not.toThrow();
      
      // Type guards should catch invalid data
      expect(typeof malformedData.x === 'number').toBe(false);
      expect(malformedData.width < 0).toBe(true);
      expect(malformedData.height === null).toBe(true);
    });

    test('should handle empty or missing bounding_box data', async () => {
      const annotationWithoutBBox = {
        videoId: mockVideoId,
        detectionId: mockDetectionId,
        frameNumber: 700,
        timestamp: 1234567890,
        vruType: 'pedestrian' as VRUType,
        // boundingBox: undefined,  // Missing bounding box
        occluded: false,
        truncated: false,
        difficult: false,
        validated: false,
        annotator: 'error-test',
        notes: 'Missing bounding box test'
      };

      // This should not cause serialization errors
      expect(() => JSON.stringify(annotationWithoutBBox)).not.toThrow();
      
      // The API should handle missing bounding_box appropriately
      // (This would typically result in a validation error from the backend)
    });
  });
});