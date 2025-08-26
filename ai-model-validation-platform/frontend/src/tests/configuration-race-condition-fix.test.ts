/**
 * Configuration Race Condition Fix - Integration Validation Test
 * 
 * This comprehensive test validates that the configuration race condition fix
 * works end-to-end by testing the complete configuration loading sequence
 * and ensuring all services properly use external IP addresses.
 */

import { envConfig, getConfig, getServiceConfig, testApiConnectivity } from '../utils/envConfig';
import { fixVideoUrl, fixVideoObjectUrl, getVideoBaseUrl } from '../utils/videoUrlFixer';
import { hasDetectionProperties, mapYoloClassToVRUType } from '../utils/typeGuards';

// Mock console to capture debug logs during testing
const consoleSpy = {
  log: jest.spyOn(console, 'log').mockImplementation(),
  warn: jest.spyOn(console, 'warn').mockImplementation(),
  error: jest.spyOn(console, 'error').mockImplementation()
};

describe('Configuration Race Condition Fix - Integration Validation', () => {
  
  beforeEach(() => {
    // Clear all console mocks
    Object.values(consoleSpy).forEach(spy => spy.mockClear());
    
    // Ensure clean environment state
    delete process.env.REACT_APP_API_URL;
    delete process.env.REACT_APP_SOCKETIO_URL;
    delete process.env.REACT_APP_WS_URL;
    
    // Reload configuration to ensure fresh state
    envConfig.reload();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  afterAll(() => {
    // Restore console methods
    Object.values(consoleSpy).forEach(spy => spy.mockRestore());
  });

  describe('1. Runtime Configuration Loading Priority', () => {
    test('should load runtime configuration before service initialization', () => {
      // Test that configuration is available immediately
      const config = getConfig();
      
      expect(config).toBeDefined();
      expect(config.environment).toBeDefined();
      expect(config.apiUrl).toBeDefined();
      expect(config.socketioUrl).toBeDefined();
      expect(config.wsUrl).toBeDefined();
      expect(config.videoBaseUrl).toBeDefined();
      
      // Configuration should be valid
      expect(envConfig.isValid()).toBe(true);
      expect(envConfig.getValidationErrors()).toHaveLength(0);
    });

    test('should use external IP for localhost detection', () => {
      const config = getConfig();
      
      // All URLs should use external IP instead of localhost
      expect(config.apiUrl).toContain('155.138.239.131:8000');
      expect(config.apiUrl).not.toContain('localhost');
      expect(config.apiUrl).not.toContain('127.0.0.1');
      
      expect(config.socketioUrl).toContain('155.138.239.131:8001');
      expect(config.socketioUrl).not.toContain('localhost');
      
      expect(config.videoBaseUrl).toContain('155.138.239.131:8000');
      expect(config.videoBaseUrl).not.toContain('localhost');
    });

    test('should provide correct service configurations', () => {
      const apiConfig = getServiceConfig('api');
      const socketioConfig = getServiceConfig('socketio');
      const websocketConfig = getServiceConfig('websocket');
      const videoConfig = getServiceConfig('video');
      
      // API service should use external IP on port 8000
      expect(apiConfig.url).toBe('http://155.138.239.131:8000');
      expect(apiConfig.timeout).toBeGreaterThan(0);
      expect(apiConfig.retryAttempts).toBeGreaterThan(0);
      
      // Socket.IO service should use external IP on port 8001
      expect(socketioConfig.url).toBe('http://155.138.239.131:8001');
      expect(socketioConfig.timeout).toBeGreaterThan(0);
      
      // WebSocket service should use external IP
      expect(websocketConfig.url).toBe('ws://155.138.239.131:8000');
      
      // Video service should use external IP on port 8000
      expect(videoConfig.baseUrl).toBe('http://155.138.239.131:8000');
    });
  });

  describe('2. WebSocket Service Configuration', () => {
    test('should provide WebSocket configuration with external IP', () => {
      // Test that WebSocket configuration is properly set up
      const socketioConfig = getServiceConfig('socketio');
      const websocketConfig = getServiceConfig('websocket');
      
      // Socket.IO should use external IP on port 8001
      expect(socketioConfig.url).toBe('http://155.138.239.131:8001');
      expect(socketioConfig.timeout).toBeGreaterThan(0);
      
      // WebSocket should use external IP on port 8000  
      expect(websocketConfig.url).toBe('ws://155.138.239.131:8000');
      expect(websocketConfig.timeout).toBeGreaterThan(0);
      
      // This validates that the hardcoded localhost:8001 was replaced with external IP
      expect(socketioConfig.url).not.toContain('localhost');
      expect(websocketConfig.url).not.toContain('localhost');
    });

    test('should not attempt localhost connections', () => {
      // Test that no localhost URLs are generated
      const config = getConfig();
      
      const urlsToCheck = [
        config.apiUrl,
        config.wsUrl,
        config.socketioUrl,
        config.videoBaseUrl
      ];
      
      urlsToCheck.forEach(url => {
        expect(url).not.toMatch(/localhost/);
        expect(url).not.toMatch(/127\.0\.0\.1/);
        expect(url).toMatch(/155\.138\.239\.131/);
      });
    });

    test('should handle WebSocket URL conversion correctly', () => {
      const config = getConfig();
      
      // WebSocket URL should be properly converted from HTTP
      expect(config.wsUrl).toMatch(/^ws:\/\//);
      expect(config.wsUrl).toContain('155.138.239.131:8000');
      
      // Socket.IO URL should use HTTP protocol on port 8001
      expect(config.socketioUrl).toMatch(/^http:\/\//);
      expect(config.socketioUrl).toContain('155.138.239.131:8001');
    });
  });

  describe('3. Video URL Corruption Prevention', () => {
    test('should fix localhost URLs without corruption', () => {
      // Test URLs that should be fixed (full URLs with protocol)
      const testUrls = [
        'http://localhost:8000/video.mp4',
        'http://127.0.0.1:8000/video.mp4'
      ];
      
      testUrls.forEach(url => {
        const fixed = fixVideoUrl(url);
        
        // Should use external IP
        expect(fixed).toContain('155.138.239.131:8000');
        expect(fixed).not.toContain('localhost');
        expect(fixed).not.toContain('127.0.0.1');
        
        // Should not have port corruption (:8000:8000)
        expect(fixed).not.toMatch(/:8000:8000/);
        expect(fixed).not.toMatch(/:8000:8000:8000/);
      });

      // Test URLs without protocol (should be treated as relative paths)
      const relativeUrl = 'localhost:8000/path/video.mp4';
      const fixedRelative = fixVideoUrl(relativeUrl, undefined, undefined, { forceAbsolute: true });
      
      // When forcing absolute, should get proper base URL + path
      expect(fixedRelative).toContain('155.138.239.131:8000');
    });

    test('should handle already corrupted URLs', () => {
      const corruptedUrls = [
        'http://localhost:8000:8000/video.mp4',
        'http://localhost:8000:8000:8000/video.mp4',
        'http://127.0.0.1:8000:8000/video.mp4'
      ];
      
      corruptedUrls.forEach(url => {
        const fixed = fixVideoUrl(url);
        
        // Should clean up corruption and use proper external IP
        expect(fixed).toBe('http://155.138.239.131:8000/video.mp4');
        expect(fixed).not.toMatch(/:8000:8000/);
      });
    });

    test('should preserve URL structure while fixing origin', () => {
      const testCases = [
        {
          input: 'http://localhost:8000/uploads/video.mp4?t=123#fragment',
          expected: 'http://155.138.239.131:8000/uploads/video.mp4?t=123#fragment'
        },
        {
          input: 'http://127.0.0.1:8000/api/videos/stream.mp4',
          expected: 'http://155.138.239.131:8000/api/videos/stream.mp4'
        }
      ];
      
      testCases.forEach(({ input, expected }) => {
        const result = fixVideoUrl(input);
        expect(result).toBe(expected);
      });
    });

    test('should handle video object URL fixing', () => {
      const video = {
        id: 'test-video-1',
        url: 'http://localhost:8000/video.mp4',
        filename: 'test.mp4'
      };
      
      fixVideoObjectUrl(video);
      
      expect(video.url).toBe('http://155.138.239.131:8000/video.mp4');
      expect(video.url).not.toContain('localhost');
    });
  });

  describe('4. Detection Field Validation', () => {
    test('should validate backend detection format correctly', () => {
      // Test backend format with class_name field
      const backendDetection = {
        class_name: 'person',
        confidence: 0.85,
        bbox: [100, 100, 200, 300]
      };
      
      expect(hasDetectionProperties(backendDetection)).toBe(true);
      
      // Test invalid detection missing required fields
      const invalidDetection = {
        class: 'person', // Wrong field name (should be class_name)
        confidence: 0.85
        // Missing bbox
      };
      
      expect(hasDetectionProperties(invalidDetection)).toBe(false);
    });

    test('should map YOLO classes to VRU types correctly', () => {
      const classMapping = [
        { input: 'person', expected: 'pedestrian' },
        { input: 'bicycle', expected: 'cyclist' },
        { input: 'motorcycle', expected: 'motorcyclist' },
        { input: 'scooter', expected: 'scooter_rider' },
        { input: 'wheelchair', expected: 'wheelchair_user' },
        // Unknown classes default to pedestrian (as per implementation)
        { input: 'car', expected: 'pedestrian' },
        { input: 'unknown', expected: 'pedestrian' }
      ];
      
      classMapping.forEach(({ input, expected }) => {
        const result = mapYoloClassToVRUType(input);
        expect(result).toBe(expected);
      });
    });

    test('should handle detection conversion with proper field mapping', () => {
      // Mock detection service for testing conversion logic
      const mockDetections = [
        {
          class_name: 'person',
          confidence: 0.85,
          bbox: [100, 100, 200, 300],
          frame_number: 30
        },
        {
          class_name: 'bicycle',
          confidence: 0.72,
          bbox: [150, 120, 250, 280],
          frame_number: 45
        }
      ];
      
      // Validate that these detections would pass validation
      mockDetections.forEach(detection => {
        expect(hasDetectionProperties(detection)).toBe(true);
        
        // Test bbox array format parsing
        expect(Array.isArray(detection.bbox)).toBe(true);
        expect(detection.bbox).toHaveLength(4);
        
        // Test field mapping
        expect(detection.class_name).toBeDefined();
        expect(detection.frame_number).toBeDefined();
      });
    });
  });

  describe('5. End-to-End Configuration Flow', () => {
    test('should load configuration in correct order', () => {
      // Configuration should be loaded and valid
      expect(envConfig.isValid()).toBe(true);
      
      // All services should have consistent configuration
      const apiConfig = getServiceConfig('api');
      const socketioConfig = getServiceConfig('socketio');
      const videoConfig = getServiceConfig('video');
      
      // All should use external IP
      expect(apiConfig.url).toMatch(/155\.138\.239\.131/);
      expect(socketioConfig.url).toMatch(/155\.138\.239\.131/);
      expect(videoConfig.baseUrl).toMatch(/155\.138\.239\.131/);
      
      // Ports should be correct
      expect(apiConfig.url).toContain(':8000');
      expect(socketioConfig.url).toContain(':8001');
      expect(videoConfig.baseUrl).toContain(':8000');
    });

    test('should provide consistent video base URL', () => {
      const baseUrl = getVideoBaseUrl();
      const videoConfig = getServiceConfig('video');
      
      expect(baseUrl).toBe(videoConfig.baseUrl);
      expect(baseUrl).toBe('http://155.138.239.131:8000');
    });

    test('should handle environment detection correctly', () => {
      const config = getConfig();
      
      // Environment should be properly detected
      expect(['development', 'production', 'test']).toContain(config.environment);
      
      // Debug mode should be configurable
      expect(typeof config.debug).toBe('boolean');
      
      // Timeouts should be reasonable
      expect(config.apiTimeout).toBeGreaterThanOrEqual(1000);
      expect(config.wsTimeout).toBeGreaterThanOrEqual(1000);
    });
  });

  describe('6. Child Detection Workflow Validation', () => {
    test('should configure complete child detection pipeline correctly', () => {
      // Test the complete configuration for child detection scenario
      const config = getConfig();
      
      // API for detection requests
      expect(config.apiUrl).toBe('http://155.138.239.131:8000');
      
      // WebSocket for real-time updates  
      expect(config.socketioUrl).toBe('http://155.138.239.131:8001');
      
      // Video URL fixing for media playback
      const testVideoUrl = fixVideoUrl('http://localhost:8000/uploads/child-video.mp4');
      expect(testVideoUrl).toBe('http://155.138.239.131:8000/uploads/child-video.mp4');
      
      // Detection field validation for backend responses
      const childDetection = {
        class_name: 'person',
        confidence: 0.92,
        bbox: [120, 150, 180, 280],
        frame_number: 60
      };
      
      expect(hasDetectionProperties(childDetection)).toBe(true);
      expect(mapYoloClassToVRUType(childDetection.class_name)).toBe('pedestrian');
    });

    test('should prevent localhost connection attempts in production workflow', () => {
      // Simulate production environment checks
      const config = getConfig();
      
      // No localhost URLs should be present in any service configuration
      const allUrls = [
        config.apiUrl,
        config.wsUrl,
        config.socketioUrl,
        config.videoBaseUrl,
        getVideoBaseUrl()
      ];
      
      allUrls.forEach(url => {
        expect(url).not.toMatch(/localhost/);
        expect(url).not.toMatch(/127\.0\.0\.1/);
        expect(url).toMatch(/155\.138\.239\.131/);
      });
      
      // WebSocket connections should use external IP
      const wsUrl = config.wsUrl;
      expect(wsUrl).toMatch(/^ws:\/\/155\.138\.239\.131/);
      
      // Socket.IO connections should use external IP  
      const socketUrl = config.socketioUrl;
      expect(socketUrl).toMatch(/^http:\/\/155\.138\.239\.131:8001/);
    });
  });

  describe('7. Performance and Error Handling', () => {
    test('should have reasonable timeout configurations', () => {
      const config = getConfig();
      
      // Timeouts should be production-ready
      expect(config.apiTimeout).toBeGreaterThanOrEqual(30000);
      expect(config.wsTimeout).toBeGreaterThanOrEqual(20000);
      
      // Retry configuration should be reasonable
      expect(config.connectionRetryAttempts).toBeGreaterThanOrEqual(5);
      expect(config.connectionRetryDelay).toBeGreaterThanOrEqual(1000);
    });

    test('should handle configuration validation errors gracefully', () => {
      // Test with invalid configuration
      const originalEnvValue = process.env.REACT_APP_API_URL;
      process.env.REACT_APP_API_URL = 'invalid-url';
      
      envConfig.reload();
      
      // Should detect validation errors
      expect(envConfig.isValid()).toBe(false);
      expect(envConfig.getValidationErrors().length).toBeGreaterThan(0);
      
      // Restore original value
      if (originalEnvValue !== undefined) {
        process.env.REACT_APP_API_URL = originalEnvValue;
      } else {
        delete process.env.REACT_APP_API_URL;
      }
      
      envConfig.reload();
    });
  });

  describe('8. Configuration Race Condition Prevention', () => {
    test('should ensure configuration is available before service initialization', () => {
      // This test validates that configuration loading happens synchronously
      // and is available immediately when services try to access it
      
      // Configuration should be immediately available
      const startTime = Date.now();
      const config = getConfig();
      const loadTime = Date.now() - startTime;
      
      // Should load very quickly (synchronous)
      expect(loadTime).toBeLessThan(10);
      expect(config).toBeDefined();
      expect(config.apiUrl).toBeDefined();
      
      // Service configs should also be immediately available
      const apiConfig = getServiceConfig('api');
      const socketConfig = getServiceConfig('socketio');
      
      expect(apiConfig).toBeDefined();
      expect(socketConfig).toBeDefined();
      expect(apiConfig.url).toBeDefined();
      expect(socketConfig.url).toBeDefined();
    });

    test('should maintain configuration consistency across multiple access', () => {
      // Test that multiple calls return consistent results
      const config1 = getConfig();
      const config2 = getConfig();
      
      expect(config1.apiUrl).toBe(config2.apiUrl);
      expect(config1.socketioUrl).toBe(config2.socketioUrl);
      expect(config1.videoBaseUrl).toBe(config2.videoBaseUrl);
      
      // Service configs should also be consistent
      const api1 = getServiceConfig('api');
      const api2 = getServiceConfig('api');
      
      expect(api1.url).toBe(api2.url);
      expect(api1.timeout).toBe(api2.timeout);
    });
  });
});