/**
 * Detection Format Validation Test
 * Tests the fixed hasDetectionProperties function with actual backend response formats
 */
import { hasDetectionProperties, mapYoloClassToVRUType } from './typeGuards';

// Mock backend detection response format based on actual logs
const mockBackendDetections = [
  {
    id: "det_001",
    class_name: "pedestrian",
    confidence: 0.85,
    bbox: [100, 150, 80, 120], // [x, y, width, height]
    frame_number: 30,
    timestamp: 1.5
  },
  {
    id: "det_002", 
    class_name: "cyclist",
    confidence: 0.72,
    bbox: [200, 180, 60, 100], // [x, y, width, height]
    frame_number: 45,
    timestamp: 2.1
  },
  {
    // Alternative format with coordinates
    id: "det_003",
    class_name: "pedestrian",
    confidence: 0.91,
    bbox: [50, 100, 130, 220], // [x1, y1, x2, y2] - should be detected and converted
    frame_number: 60,
    timestamp: 2.8
  }
];

// Invalid detection formats that should be filtered out
const invalidDetections = [
  {
    // Missing confidence
    id: "invalid_001",
    class_name: "pedestrian",
    bbox: [100, 150, 80, 120],
    frame_number: 30
  },
  {
    // Missing class_name
    id: "invalid_002", 
    confidence: 0.75,
    bbox: [100, 150, 80, 120],
    frame_number: 30
  },
  {
    // Missing bbox
    id: "invalid_003",
    class_name: "cyclist",
    confidence: 0.82,
    frame_number: 30
  },
  {
    // Invalid bbox format
    id: "invalid_004",
    class_name: "pedestrian",
    confidence: 0.75,
    bbox: [100, 150], // Too few coordinates
    frame_number: 30
  }
];

describe('Detection Format Validation', () => {
  describe('hasDetectionProperties', () => {
    test('should validate correct backend detection format', () => {
      mockBackendDetections.forEach((detection, index) => {
        const result = hasDetectionProperties(detection);
        expect(result).toBe(true, `Detection ${index} should be valid: ${JSON.stringify(detection)}`);
      });
    });

    test('should reject invalid detection formats', () => {
      invalidDetections.forEach((detection, index) => {
        const result = hasDetectionProperties(detection);
        expect(result).toBe(false, `Invalid detection ${index} should be rejected: ${JSON.stringify(detection)}`);
      });
    });

    test('should handle mixed valid/invalid detection arrays', () => {
      const mixedArray = [...mockBackendDetections, ...invalidDetections];
      const validCount = mixedArray.filter(hasDetectionProperties).length;
      
      expect(validCount).toBe(mockBackendDetections.length);
    });

    test('should handle alternative property names', () => {
      const alternativeFormats = [
        {
          id: "alt_001",
          className: "pedestrian", // camelCase instead of snake_case
          confidence: 0.88,
          bbox: [100, 150, 80, 120],
          frameNumber: 30
        },
        {
          id: "alt_002",
          label: "cyclist", // label instead of class_name
          confidence: 0.75,
          boundingBox: [200, 180, 60, 100], // boundingBox instead of bbox
          frame_number: 45
        }
      ];

      alternativeFormats.forEach((detection, index) => {
        const result = hasDetectionProperties(detection);
        expect(result).toBe(true, `Alternative format ${index} should be valid: ${JSON.stringify(detection)}`);
      });
    });
  });

  describe('mapYoloClassToVRUType', () => {
    test('should map YOLO classes to VRU types correctly', () => {
      expect(mapYoloClassToVRUType('person')).toBe('pedestrian');
      expect(mapYoloClassToVRUType('pedestrian')).toBe('pedestrian');
      expect(mapYoloClassToVRUType('bicycle')).toBe('cyclist');
      expect(mapYoloClassToVRUType('cyclist')).toBe('cyclist');
      expect(mapYoloClassToVRUType('motorcycle')).toBe('motorcyclist');
      expect(mapYoloClassToVRUType('unknown_class')).toBe('pedestrian'); // default fallback
    });
  });
});

// Export for testing in other modules
export {
  mockBackendDetections,
  invalidDetections
};