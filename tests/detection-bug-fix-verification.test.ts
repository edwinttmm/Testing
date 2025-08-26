/**
 * Test to verify the detection conversion bug fix
 * Tests the hasDetectionProperties function and class mapping
 */

import { hasDetectionProperties, mapYoloClassToVRUType } from '../ai-model-validation-platform/frontend/src/utils/typeGuards';

describe('Detection Conversion Bug Fix', () => {
  
  describe('hasDetectionProperties', () => {
    it('should accept valid YOLO detection objects', () => {
      // Typical YOLO detection object structure
      const yoloDetection = {
        confidence: 0.85,
        class: 'person',
        bbox: [100, 200, 80, 160], // x, y, width, height
        x: 100,
        y: 200,
        width: 80,
        height: 160
      };
      
      expect(hasDetectionProperties(yoloDetection)).toBe(true);
    });
    
    it('should accept detection objects with alternative property names', () => {
      const detection1 = {
        conf: 0.90,
        label: 'person',
        box: [50, 100, 60, 120]
      };
      
      const detection2 = {
        score: 0.75,
        name: 'bicycle',
        x1: 10, y1: 20, x2: 110, y2: 220
      };
      
      expect(hasDetectionProperties(detection1)).toBe(true);
      expect(hasDetectionProperties(detection2)).toBe(true);
    });
    
    it('should reject objects without required detection properties', () => {
      const invalidObjects = [
        { detections: [] }, // Old container format
        { confidence: 0.8 }, // Missing bbox and class
        { class: 'person' }, // Missing confidence and bbox
        { x: 10, y: 20 }, // Missing confidence and class
        null,
        undefined,
        'not an object',
        []
      ];
      
      invalidObjects.forEach(obj => {
        expect(hasDetectionProperties(obj)).toBe(false);
      });
    });
  });
  
  describe('mapYoloClassToVRUType', () => {
    it('should map person classes to pedestrian', () => {
      const personClasses = ['person', 'people', 'human', 'child', 'children', 'pedestrian'];
      personClasses.forEach(className => {
        expect(mapYoloClassToVRUType(className)).toBe('pedestrian');
      });
    });
    
    it('should map bicycle classes to cyclist', () => {
      const bicycleClasses = ['bicycle', 'bike', 'cyclist', 'bicyclist'];
      bicycleClasses.forEach(className => {
        expect(mapYoloClassToVRUType(className)).toBe('cyclist');
      });
    });
    
    it('should handle case insensitive mapping', () => {
      expect(mapYoloClassToVRUType('PERSON')).toBe('pedestrian');
      expect(mapYoloClassToVRUType('Person')).toBe('pedestrian');
      expect(mapYoloClassToVRUType('BICYCLE')).toBe('cyclist');
    });
    
    it('should default to pedestrian for unknown classes', () => {
      expect(mapYoloClassToVRUType('unknown_class')).toBe('pedestrian');
      expect(mapYoloClassToVRUType('')).toBe('pedestrian');
    });
  });
  
  describe('Integration Test - Backend Detection Processing', () => {
    it('should properly filter and convert backend detections', () => {
      // Simulated backend response
      const backendDetections = [
        {
          confidence: 0.89,
          class: 'person',
          bbox: [320, 240, 80, 160],
          frame: 30,
          timestamp: 1.0
        },
        {
          confidence: 0.76,
          class: 'person', 
          bbox: [450, 280, 70, 150],
          frame: 30,
          timestamp: 1.0
        }
      ];
      
      // Test filtering
      const validDetections = backendDetections.filter(hasDetectionProperties);
      expect(validDetections).toHaveLength(2);
      
      // Test class mapping
      validDetections.forEach(det => {
        const vruType = mapYoloClassToVRUType(det.class);
        expect(vruType).toBe('pedestrian');
      });
    });
  });
});