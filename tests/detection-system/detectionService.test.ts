import { detectionService, DetectionConfig, DetectionResult } from '../../ai-model-validation-platform/frontend/src/services/detectionService';
import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';

// Mock the API service
jest.mock('../../ai-model-validation-platform/frontend/src/services/api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

describe('DetectionService', () => {
  const mockVideoId = 'test-video-123';
  const mockConfig: DetectionConfig = {
    confidenceThreshold: 0.7,
    nmsThreshold: 0.5,
    modelName: 'yolov8n',
    targetClasses: ['person', 'bicycle'],
    maxRetries: 3,
    retryDelay: 1000,
    useFallback: false
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Clear any processing state
    (detectionService as any).isProcessing.clear();
    (detectionService as any).retryCount.clear();
  });

  afterEach(() => {
    // Disconnect WebSocket if connected
    detectionService.disconnectWebSocket();
  });

  describe('runDetection', () => {
    it('should successfully run detection with backend service', async () => {
      // Mock successful backend response
      const mockDetections = [
        {
          id: 'det-1',
          detectionId: 'det-1',
          frame: 0,
          timestamp: 0,
          vruType: 'pedestrian',
          x: 100,
          y: 100,
          width: 50,
          height: 100,
          label: 'person',
          confidence: 0.85
        }
      ];

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: mockDetections,
        processingTime: 1500,
        error: undefined
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(true);
      expect(result.detections).toHaveLength(1);
      expect(result.detections[0].boundingBox.confidence).toBe(0.85);
      expect(result.source).toBe('backend');
      expect(result.processingTime).toBeGreaterThan(0);
      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledWith(mockVideoId, mockConfig);
    });

    it('should prevent concurrent detection requests for same video', async () => {
      // Mock a slow backend response
      mockApiService.runDetectionPipeline.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({
          success: true,
          detections: [],
          processingTime: 2000
        }), 1000))
      );

      // Start first detection
      const firstDetection = detectionService.runDetection(mockVideoId, mockConfig);
      
      // Immediately start second detection
      const secondDetection = detectionService.runDetection(mockVideoId, mockConfig);

      const [firstResult, secondResult] = await Promise.all([firstDetection, secondDetection]);

      expect(firstResult.success).toBe(true);
      expect(secondResult.success).toBe(false);
      expect(secondResult.error).toContain('Detection already in progress');
      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledTimes(1);
    });

    it('should handle backend timeout gracefully', async () => {
      // Mock timeout scenario
      mockApiService.runDetectionPipeline.mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 5000)) // Longer than 3s timeout
      );

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Backend service unavailable');
      expect(result.source).toBe('backend');
    });

    it('should handle backend errors appropriately', async () => {
      mockApiService.runDetectionPipeline.mockRejectedValue(new Error('Network error'));

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Network error');
      expect(result.source).toBe('backend');
    });

    it('should handle invalid backend response', async () => {
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: null as any,
        processingTime: 1000
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid detection response from backend');
    });

    it('should convert detections to annotations correctly', async () => {
      const mockDetections = [
        {
          id: 'det-1',
          detectionId: 'det-1',
          frame: 5,
          timestamp: 166.67,
          vruType: 'cyclist',
          bbox: {
            x: 200,
            y: 150,
            width: 80,
            height: 120
          },
          label: 'bicycle',
          confidence: 0.92,
          occluded: false,
          truncated: true,
          difficult: false
        }
      ];

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: mockDetections,
        processingTime: 1200
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(true);
      expect(result.detections[0]).toMatchObject({
        id: 'det-1',
        videoId: mockVideoId,
        detectionId: 'det-1',
        frameNumber: 5,
        timestamp: 166.67,
        vruType: 'cyclist',
        boundingBox: {
          x: 200,
          y: 150,
          width: 80,
          height: 120,
          label: 'bicycle',
          confidence: 0.92
        },
        occluded: false,
        truncated: true,
        difficult: false,
        validated: false
      });
    });

    it('should handle fallback detection when enabled', async () => {
      const fallbackConfig = { ...mockConfig, useFallback: true };
      
      mockApiService.runDetectionPipeline.mockRejectedValue(new Error('Backend unavailable'));

      const result = await detectionService.runDetection(mockVideoId, fallbackConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Detection service unavailable');
      expect(result.source).toBe('fallback');
    });

    it('should clean up processing state after completion', async () => {
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [],
        processingTime: 1000
      });

      await detectionService.runDetection(mockVideoId, mockConfig);

      // Should be able to run detection again immediately
      const secondResult = await detectionService.runDetection(mockVideoId, mockConfig);
      expect(secondResult.success).toBe(true);
    });

    it('should clean up processing state after error', async () => {
      mockApiService.runDetectionPipeline.mockRejectedValue(new Error('Test error'));

      await detectionService.runDetection(mockVideoId, mockConfig);

      // Should be able to run detection again immediately
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [],
        processingTime: 1000
      });

      const secondResult = await detectionService.runDetection(mockVideoId, mockConfig);
      expect(secondResult.success).toBe(true);
    });
  });

  describe('WebSocket Connection', () => {
    let mockWebSocket: any;
    let originalWebSocket: any;

    beforeEach(() => {
      originalWebSocket = global.WebSocket;
      mockWebSocket = {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        close: jest.fn(),
        send: jest.fn(),
        readyState: WebSocket.OPEN
      };

      global.WebSocket = jest.fn(() => mockWebSocket) as any;
    });

    afterEach(() => {
      global.WebSocket = originalWebSocket;
    });

    it('should connect WebSocket successfully', () => {
      const mockOnUpdate = jest.fn();
      const wsUrl = 'ws://localhost:8000/ws/detection';

      detectionService.connectWebSocket(wsUrl, mockOnUpdate);

      expect(WebSocket).toHaveBeenCalledWith(wsUrl);
      expect(mockWebSocket.onopen).toBeDefined();
      expect(mockWebSocket.onmessage).toBeDefined();
      expect(mockWebSocket.onerror).toBeDefined();
      expect(mockWebSocket.onclose).toBeDefined();
    });

    it('should handle WebSocket messages correctly', () => {
      const mockOnUpdate = jest.fn();
      const testData = { 
        type: 'detection', 
        videoId: mockVideoId, 
        annotation: { id: 'test' } 
      };

      detectionService.connectWebSocket('ws://test.com', mockOnUpdate);

      // Simulate message received
      const messageEvent = {
        data: JSON.stringify(testData)
      };
      mockWebSocket.onmessage(messageEvent);

      expect(mockOnUpdate).toHaveBeenCalledWith(testData);
    });

    it('should handle invalid WebSocket messages gracefully', () => {
      const mockOnUpdate = jest.fn();
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      detectionService.connectWebSocket('ws://test.com', mockOnUpdate);

      // Simulate invalid message
      const messageEvent = {
        data: 'invalid json'
      };
      mockWebSocket.onmessage(messageEvent);

      expect(mockOnUpdate).not.toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalledWith('WebSocket message parse error:', expect.any(Error));
      
      consoleSpy.mockRestore();
    });

    it('should attempt reconnection on close', (done) => {
      const mockOnUpdate = jest.fn();
      const originalSetTimeout = global.setTimeout;
      
      global.setTimeout = jest.fn((callback, delay) => {
        expect(delay).toBe(5000);
        // Don't actually call the callback to avoid infinite loop
        return 123 as any;
      }) as any;

      detectionService.connectWebSocket('ws://test.com', mockOnUpdate);

      // Simulate connection close
      mockWebSocket.onclose();

      expect(global.setTimeout).toHaveBeenCalled();
      
      global.setTimeout = originalSetTimeout;
      done();
    });

    it('should disconnect WebSocket properly', () => {
      const mockOnUpdate = jest.fn();
      detectionService.connectWebSocket('ws://test.com', mockOnUpdate);

      detectionService.disconnectWebSocket();

      expect(mockWebSocket.close).toHaveBeenCalled();
    });

    it('should handle WebSocket connection errors', () => {
      const mockOnUpdate = jest.fn();
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      detectionService.connectWebSocket('ws://test.com', mockOnUpdate);

      // Simulate connection error
      const errorEvent = new Error('Connection failed');
      mockWebSocket.onerror(errorEvent);

      expect(consoleSpy).toHaveBeenCalledWith('WebSocket error:', errorEvent);
      
      consoleSpy.mockRestore();
    });
  });

  describe('Edge Cases and Error Conditions', () => {
    it('should handle missing detection config gracefully', async () => {
      const minimalConfig: DetectionConfig = {
        confidenceThreshold: 0.5,
        nmsThreshold: 0.4,
        modelName: 'yolov8n',
        targetClasses: ['person']
      };

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [],
        processingTime: 1000
      });

      const result = await detectionService.runDetection(mockVideoId, minimalConfig);

      expect(result.success).toBe(true);
      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledWith(mockVideoId, minimalConfig);
    });

    it('should handle empty detections array', async () => {
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [],
        processingTime: 500
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(true);
      expect(result.detections).toHaveLength(0);
    });

    it('should handle malformed detection objects', async () => {
      const malformedDetections = [
        {
          // Missing required fields
          confidence: 0.8
        },
        {
          id: 'det-2',
          // Missing bbox, should use defaults
          label: 'person'
        }
      ];

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: malformedDetections,
        processingTime: 1000
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(true);
      expect(result.detections).toHaveLength(2);
      
      // Should have default values for missing fields
      expect(result.detections[0].boundingBox.x).toBe(0);
      expect(result.detections[0].boundingBox.y).toBe(0);
      expect(result.detections[0].boundingBox.width).toBe(100);
      expect(result.detections[0].boundingBox.height).toBe(100);
      expect(result.detections[0].vruType).toBe('pedestrian');
    });

    it('should handle WebSocket connection failures', () => {
      const mockOnUpdate = jest.fn();
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      // Mock WebSocket constructor to throw
      global.WebSocket = jest.fn(() => {
        throw new Error('WebSocket connection failed');
      }) as any;

      detectionService.connectWebSocket('ws://invalid.com', mockOnUpdate);

      expect(consoleSpy).toHaveBeenCalledWith('Failed to connect WebSocket:', expect.any(Error));
      
      consoleSpy.mockRestore();
    });
  });

  describe('Performance and Concurrency', () => {
    it('should handle multiple detection requests for different videos', async () => {
      const videoIds = ['video-1', 'video-2', 'video-3'];
      
      mockApiService.runDetectionPipeline.mockImplementation((videoId) =>
        Promise.resolve({
          success: true,
          detections: [{ id: `det-${videoId}`, videoId }],
          processingTime: 1000
        })
      );

      const promises = videoIds.map(id => detectionService.runDetection(id, mockConfig));
      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      results.forEach((result, index) => {
        expect(result.success).toBe(true);
        expect(result.detections[0].videoId).toBe(videoIds[index]);
      });
      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledTimes(3);
    });

    it('should measure processing time accurately', async () => {
      const startTime = Date.now();
      
      mockApiService.runDetectionPipeline.mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve({
          success: true,
          detections: [],
          processingTime: 100
        }), 50))
      );

      const result = await detectionService.runDetection(mockVideoId, mockConfig);
      const endTime = Date.now();

      expect(result.success).toBe(true);
      expect(result.processingTime).toBeGreaterThan(40); // Allow some variance
      expect(result.processingTime).toBeLessThan(endTime - startTime + 10);
    });

    it('should handle rapid sequential detection requests', async () => {
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [],
        processingTime: 100
      });

      const requests = [];
      for (let i = 0; i < 5; i++) {
        requests.push(detectionService.runDetection(`video-${i}`, mockConfig));
      }

      const results = await Promise.all(requests);
      
      results.forEach(result => {
        expect(result.success).toBe(true);
      });
      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledTimes(5);
    });
  });
});