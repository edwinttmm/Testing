import { detectionService, DetectionConfig } from '../../ai-model-validation-platform/frontend/src/services/detectionService';
import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';

// Mock the API service
jest.mock('../../ai-model-validation-platform/frontend/src/services/api', () => ({
  apiService: {
    runDetectionPipeline: jest.fn(),
    getAnnotations: jest.fn(),
    createAnnotation: jest.fn(),
  }
}));

// Mock environment config
jest.mock('../../ai-model-validation-platform/frontend/src/utils/envConfig', () => ({
  getServiceConfig: jest.fn(() => ({
    url: 'ws://localhost:8000'
  })),
  isDebugEnabled: jest.fn(() => true)
}));

describe('Detection Workflow Integration Tests', () => {
  const mockApiService = apiService as jest.Mocked<typeof apiService>;
  let mockWebSocket: any;
  let originalWebSocket: any;

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();
    
    // Mock WebSocket
    originalWebSocket = global.WebSocket;
    mockWebSocket = {
      close: jest.fn(),
      send: jest.fn(),
      readyState: WebSocket.CLOSED,
      onopen: null,
      onclose: null,
      onmessage: null,
      onerror: null
    };
    global.WebSocket = jest.fn(() => mockWebSocket) as any;
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    detectionService.disconnectWebSocket();
  });

  describe('Complete Detection Workflow', () => {
    const testVideoId = 'test-video-123';
    const testConfig: DetectionConfig = {
      confidenceThreshold: 0.5,
      nmsThreshold: 0.4,
      modelName: 'yolov8s',
      targetClasses: ['person', 'bicycle'],
      maxRetries: 2,
      retryDelay: 1000,
      useFallback: true
    };

    it('should successfully complete detection with backend', async () => {
      // Mock successful backend response
      const mockDetections = [
        {
          id: 'det-1',
          detectionId: 'DET_PED_0001',
          frame: 30,
          timestamp: 1.0,
          vruType: 'pedestrian',
          x: 100,
          y: 100,
          width: 50,
          height: 100,
          confidence: 0.85,
          label: 'person'
        }
      ];

      mockApiService.runDetectionPipeline.mockResolvedValue({
        detections: mockDetections,
        processingTime: 2500
      });

      const result = await detectionService.runDetection(testVideoId, testConfig);

      expect(result.success).toBe(true);
      expect(result.source).toBe('backend');
      expect(result.detections).toHaveLength(1);
      expect(result.detections[0].vruType).toBe('pedestrian');
      expect(result.detections[0].boundingBox.confidence).toBe(0.85);
      expect(result.processingTime).toBeGreaterThan(0);
    });

    it('should fallback to mock data when backend fails', async () => {
      // Mock backend failure
      mockApiService.runDetectionPipeline.mockRejectedValue(new Error('Network Error'));

      const result = await detectionService.runDetection(testVideoId, testConfig);

      expect(result.success).toBe(true);
      expect(result.source).toBe('fallback');
      expect(result.detections).toHaveLength(2); // Mock generates 2 detections
      expect(result.detections[0].vruType).toBe('pedestrian');
      expect(result.detections[1].vruType).toBe('cyclist');
    });

    it('should prevent duplicate detection runs', async () => {
      mockApiService.runDetectionPipeline.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({ detections: [] }), 1000))
      );

      // Start two detection runs simultaneously
      const promise1 = detectionService.runDetection(testVideoId, testConfig);
      const promise2 = detectionService.runDetection(testVideoId, testConfig);

      const [result1, result2] = await Promise.all([promise1, promise2]);

      expect(result1.success).toBe(true);
      expect(result2.success).toBe(false);
      expect(result2.error).toContain('already in progress');
    });

    it('should handle timeout errors appropriately', async () => {
      // Mock a slow backend response
      mockApiService.runDetectionPipeline.mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 35000)) // Longer than timeout
      );

      const result = await detectionService.runDetection(testVideoId, {
        ...testConfig,
        useFallback: false
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Detection timed out');
    });
  });

  describe('WebSocket Integration', () => {
    const testVideoId = 'test-video-ws';

    it('should establish WebSocket connection for real-time updates', () => {
      const updateCallback = jest.fn();
      
      detectionService.connectWebSocket(testVideoId, updateCallback);

      expect(WebSocket).toHaveBeenCalledWith(`ws://localhost:8000/ws/detection/${testVideoId}`);
      expect(mockWebSocket.onopen).toBeDefined();
      expect(mockWebSocket.onmessage).toBeDefined();
    });

    it('should handle WebSocket authentication failures gracefully', () => {
      const updateCallback = jest.fn();
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      detectionService.connectWebSocket(testVideoId, updateCallback);

      // Simulate authentication failure
      const authError = new Error('Authentication failed');
      mockWebSocket.onerror(authError);

      expect(consoleSpy).toHaveBeenCalledWith('WebSocket error:', authError);
      
      consoleSpy.mockRestore();
    });

    it('should process real-time detection updates', () => {
      const updateCallback = jest.fn();
      
      detectionService.connectWebSocket(testVideoId, updateCallback);

      const testUpdate = {
        type: 'detection',
        videoId: testVideoId,
        detection: {
          id: 'real-time-det-1',
          confidence: 0.92,
          bbox: { x: 150, y: 200, width: 80, height: 160 }
        }
      };

      // Simulate incoming WebSocket message
      mockWebSocket.onmessage({
        data: JSON.stringify(testUpdate)
      });

      expect(updateCallback).toHaveBeenCalledWith(testUpdate);
    });

    it('should handle WebSocket reconnection attempts', (done) => {
      const updateCallback = jest.fn();
      let reconnectAttempts = 0;
      
      // Override setTimeout to track reconnection attempts
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = jest.fn((callback, delay) => {
        if (delay === 5000) { // Reconnection delay
          reconnectAttempts++;
          if (reconnectAttempts === 1) {
            callback();
            global.setTimeout = originalSetTimeout;
            done();
          }
        }
        return originalSetTimeout(callback, delay);
      }) as any;

      detectionService.connectWebSocket(testVideoId, updateCallback);

      // Simulate unexpected disconnection
      mockWebSocket.onclose({ code: 1006, reason: 'Connection lost' });
    });
  });

  describe('Error Recovery & Resilience', () => {
    it('should provide user-friendly error messages', async () => {
      const errorScenarios = [
        {
          mockError: { status: 404 },
          expectedMessage: 'Video not found on server'
        },
        {
          mockError: { status: 422 },
          expectedMessage: 'Invalid video format'
        },
        {
          mockError: { status: 500 },
          expectedMessage: 'Server error during detection'
        },
        {
          mockError: new Error('Network Error'),
          expectedMessage: 'Network connection failed'
        }
      ];

      for (const scenario of errorScenarios) {
        mockApiService.runDetectionPipeline.mockRejectedValue(scenario.mockError);
        
        const result = await detectionService.runDetection('test-video', {
          ...testConfig,
          useFallback: false
        });

        expect(result.success).toBe(false);
        expect(result.error).toContain(scenario.expectedMessage);
      }
    });

    it('should maintain service state consistency during failures', async () => {
      const videoId = 'consistency-test';
      
      // Start detection that will fail
      mockApiService.runDetectionPipeline.mockRejectedValue(new Error('Service unavailable'));
      
      const result1 = await detectionService.runDetection(videoId, {
        ...testConfig,
        useFallback: false
      });
      
      expect(result1.success).toBe(false);

      // Next detection should work normally
      mockApiService.runDetectionPipeline.mockResolvedValue({
        detections: [],
        processingTime: 1000
      });

      const result2 = await detectionService.runDetection(videoId, testConfig);
      expect(result2.success).toBe(true);
    });

    it('should cleanup resources properly on service destruction', () => {
      const videoId = 'cleanup-test';
      const updateCallback = jest.fn();
      
      // Establish WebSocket connection
      detectionService.connectWebSocket(videoId, updateCallback);
      
      // Disconnect WebSocket
      detectionService.disconnectWebSocket();
      
      expect(mockWebSocket.close).toHaveBeenCalled();
    });
  });

  describe('Performance & Optimization', () => {
    it('should track and report processing times accurately', async () => {
      const startTime = Date.now();
      
      mockApiService.runDetectionPipeline.mockImplementation(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({
            detections: [],
            processingTime: 1500
          }), 100)
        )
      );

      const result = await detectionService.runDetection('perf-test', testConfig);

      expect(result.success).toBe(true);
      expect(result.processingTime).toBeGreaterThan(100);
      expect(result.processingTime).toBeLessThan(Date.now() - startTime + 100);
    });

    it('should convert backend detections to proper annotation format', async () => {
      const mockBackendDetection = {
        id: 'backend-det-1',
        frame: 45,
        timestamp: 1.5,
        vruType: 'cyclist',
        bbox: {
          x: 200,
          y: 180,
          width: 120,
          height: 180
        },
        confidence: 0.92,
        label: 'bicycle'
      };

      mockApiService.runDetectionPipeline.mockResolvedValue({
        detections: [mockBackendDetection],
        processingTime: 2000
      });

      const result = await detectionService.runDetection('format-test', testConfig);

      expect(result.success).toBe(true);
      expect(result.detections[0]).toMatchObject({
        videoId: 'format-test',
        detectionId: expect.any(String),
        frameNumber: 45,
        timestamp: 1.5,
        vruType: 'cyclist',
        boundingBox: {
          x: 200,
          y: 180,
          width: 120,
          height: 180,
          label: 'cyclist',
          confidence: 0.92
        },
        validated: false
      });
    });
  });

  describe('Configuration Validation', () => {
    it('should handle various configuration parameters', async () => {
      const configVariations: DetectionConfig[] = [
        {
          confidenceThreshold: 0.3,
          nmsThreshold: 0.6,
          modelName: 'yolov8n',
          targetClasses: ['person']
        },
        {
          confidenceThreshold: 0.8,
          nmsThreshold: 0.3,
          modelName: 'yolov8x',
          targetClasses: ['person', 'bicycle', 'motorcycle', 'car', 'bus', 'truck']
        }
      ];

      mockApiService.runDetectionPipeline.mockResolvedValue({
        detections: [],
        processingTime: 1000
      });

      for (const config of configVariations) {
        const result = await detectionService.runDetection('config-test', config);
        
        expect(result.success).toBe(true);
        expect(mockApiService.runDetectionPipeline).toHaveBeenCalledWith('config-test', {
          confidenceThreshold: config.confidenceThreshold,
          nmsThreshold: config.nmsThreshold,
          modelName: config.modelName,
          targetClasses: config.targetClasses
        });
      }
    });
  });
});