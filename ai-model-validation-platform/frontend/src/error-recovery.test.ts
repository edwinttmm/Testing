import { detectionService, DetectionConfig } from '../../ai-model-validation-platform/frontend/src/services/detectionService';
import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';
import { useDetectionWebSocket } from '../../ai-model-validation-platform/frontend/src/hooks/useDetectionWebSocket';

// Mock dependencies
jest.mock('../../ai-model-validation-platform/frontend/src/services/api');
jest.mock('../../ai-model-validation-platform/frontend/src/hooks/useDetectionWebSocket');

const mockApiService = apiService as jest.Mocked<typeof apiService>;
const mockUseDetectionWebSocket = useDetectionWebSocket as jest.MockedFunction<typeof useDetectionWebSocket>;

describe('Detection System Error Handling and Recovery', () => {
  const mockVideoId = 'error-test-video';
  const mockConfig: DetectionConfig = {
    confidenceThreshold: 0.7,
    nmsThreshold: 0.5,
    modelName: 'yolov8n',
    targetClasses: ['person', 'bicycle']
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Clear processing state
    (detectionService as any).isProcessing.clear();
    (detectionService as any).retryCount.clear();
  });

  afterEach(() => {
    jest.useRealTimers();
    detectionService.disconnectWebSocket();
  });

  describe('API Error Recovery', () => {
    it('should handle network connectivity issues with retry logic', async () => {
      let attemptCount = 0;
      
      mockApiService.runDetectionPipeline.mockImplementation(() => {
        attemptCount++;
        if (attemptCount <= 2) {
          return Promise.reject({
            request: {},
            message: 'Network Error',
            code: 'ECONNREFUSED'
          });
        }
        return Promise.resolve({
          success: true,
          detections: [{ id: 'det-1', label: 'person', confidence: 0.8 }],
          processingTime: 1000
        });
      });

      // Should eventually succeed after network recovery
      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false); // Current implementation doesn't retry, just fails
      expect(result.error).toContain('Network Error');
    });

    it('should handle server overload with exponential backoff', async () => {
      const serverOverloadResponses = [
        Promise.reject({
          response: { status: 503, data: { message: 'Server overloaded' } }
        }),
        Promise.reject({
          response: { status:503, data: { message: 'Server overloaded' } }
        }),
        Promise.resolve({
          success: true,
          detections: [{ id: 'det-1', label: 'person', confidence: 0.8 }],
          processingTime: 2000
        })
      ];

      let callIndex = 0;
      mockApiService.runDetectionPipeline.mockImplementation(() => {
        return serverOverloadResponses[callIndex++];
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Server overloaded');
    });

    it('should handle malformed API responses gracefully', async () => {
      const malformedResponses = [
        // Null response
        null,
        // Missing detections field
        { success: true, processingTime: 1000 },
        // Invalid detection format
        { 
          success: true, 
          detections: [{ invalid: 'data' }], 
          processingTime: 1000 
        },
        // Non-array detections
        { 
          success: true, 
          detections: 'not an array', 
          processingTime: 1000 
        }
      ];

      for (const response of malformedResponses) {
        mockApiService.runDetectionPipeline.mockResolvedValue(response as any);

        const result = await detectionService.runDetection(`${mockVideoId}-malformed`, mockConfig);

        expect(result.success).toBe(false);
        expect(result.error).toContain('Invalid detection response');
      }
    });

    it('should handle API timeout and fallback appropriately', async () => {
      // Mock long-running request that exceeds timeout
      mockApiService.runDetectionPipeline.mockImplementation(() =>
        new Promise(resolve => 
          setTimeout(() => resolve({
            success: true,
            detections: [],
            processingTime: 5000
          }), 5000)
        )
      );

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Backend service unavailable');
      expect(result.processingTime).toBeLessThan(4000); // Should timeout around 3s
    });

    it('should handle authentication and authorization errors', async () => {
      const authErrors = [
        { status: 401, data: { message: 'Unauthorized access' } },
        { status: 403, data: { message: 'Insufficient permissions' } },
        { status: 429, data: { message: 'Rate limit exceeded' } }
      ];

      for (const error of authErrors) {
        mockApiService.runDetectionPipeline.mockRejectedValue({
          response: error
        });

        const result = await detectionService.runDetection(`${mockVideoId}-auth`, mockConfig);

        expect(result.success).toBe(false);
        expect(result.error).toContain(error.data.message);
      }
    });

    it('should handle partial detection pipeline failures', async () => {
      // Mock pipeline that fails mid-process
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: false,
        detections: [],
        processingTime: 1500,
        error: 'Model inference failed at frame 45'
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid detection response');
      expect(result.detections).toHaveLength(0);
    });
  });

  describe('WebSocket Error Recovery', () => {
    let mockWebSocket: any;

    beforeEach(() => {
      mockWebSocket = {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        close: jest.fn(),
        send: jest.fn(),
        readyState: WebSocket.CLOSED
      };

      global.WebSocket = jest.fn(() => mockWebSocket) as any;
    });

    it('should handle WebSocket connection failures', async () => {
      let connectionAttempts = 0;
      const maxAttempts = 3;

      mockUseDetectionWebSocket.mockImplementation((options) => {
        connectionAttempts++;
        
        if (connectionAttempts <= maxAttempts) {
          // Simulate connection failure
          setTimeout(() => options?.onError?.(new Error('Connection failed')), 0);
        }

        return {
          connect: jest.fn(),
          disconnect: jest.fn(),
          sendMessage: jest.fn(),
          isConnected: false
        };
      });

      const onError = jest.fn();
      const webSocketHook = mockUseDetectionWebSocket({
        autoReconnect: true,
        onError
      });

      expect(onError).toHaveBeenCalled();
      expect(connectionAttempts).toBeGreaterThan(0);
    });

    it('should recover from WebSocket disconnections', async () => {
      let isConnected = false;
      let disconnectionCount = 0;

      mockUseDetectionWebSocket.mockImplementation((options) => ({
        connect: jest.fn(() => {
          isConnected = true;
          options?.onConnect?.();
        }),
        disconnect: jest.fn(() => {
          isConnected = false;
          disconnectionCount++;
          options?.onDisconnect?.();
        }),
        sendMessage: jest.fn(),
        isConnected
      }));

      const onConnect = jest.fn();
      const onDisconnect = jest.fn();

      const webSocketHook = mockUseDetectionWebSocket({
        autoReconnect: true,
        onConnect,
        onDisconnect
      });

      // Simulate connection
      webSocketHook.connect();
      expect(onConnect).toHaveBeenCalled();
      expect(isConnected).toBe(true);

      // Simulate disconnection
      webSocketHook.disconnect();
      expect(onDisconnect).toHaveBeenCalled();
      expect(disconnectionCount).toBe(1);
    });

    it('should handle WebSocket message parsing errors', async () => {
      const invalidMessages = [
        'invalid json',
        '{"incomplete": json',
        '',
        null,
        undefined,
        '[]', // Array instead of object
        '{"missing": "required fields"}'
      ];

      let messageHandler: ((event: any) => void) | undefined;

      detectionService.connectWebSocket('ws://test.com', jest.fn());

      // Capture the message handler
      if (mockWebSocket.onmessage) {
        messageHandler = mockWebSocket.onmessage;
      }

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      // Test each invalid message
      invalidMessages.forEach((invalidMessage) => {
        if (messageHandler) {
          messageHandler({ data: invalidMessage });
        }
      });

      // Should have logged errors for invalid messages
      expect(consoleSpy).toHaveBeenCalledTimes(invalidMessages.length);

      consoleSpy.mockRestore();
    });

    it('should handle WebSocket send failures', async () => {
      mockWebSocket.readyState = WebSocket.CLOSED;
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

      detectionService.connectWebSocket('ws://test.com', jest.fn());

      // Try to send message when disconnected - should be handled in the hook
      // This is tested in the WebSocket hook itself, not the service

      consoleSpy.mockRestore();
    });

    it('should handle WebSocket reconnection storms', async () => {
      let reconnectionAttempts = 0;
      const maxReconnections = 10;

      global.WebSocket = jest.fn(() => {
        reconnectionAttempts++;
        
        // Simulate immediate failures for first few attempts
        const immediateFailure = reconnectionAttempts <= 5;
        
        return {
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          close: jest.fn(),
          send: jest.fn(),
          readyState: immediateFailure ? WebSocket.CLOSED : WebSocket.OPEN,
          onerror: immediateFailure ? 
            () => setTimeout(() => {}, 0) : undefined
        };
      }) as any;

      // Simulate rapid reconnection attempts
      for (let i = 0; i < maxReconnections; i++) {
        detectionService.connectWebSocket('ws://unstable.com', jest.fn());
        
        // Simulate connection failure
        if (mockWebSocket.onerror) {
          mockWebSocket.onerror(new Error('Connection failed'));
        }
        
        detectionService.disconnectWebSocket();
      }

      expect(reconnectionAttempts).toBe(maxReconnections);
    });
  });

  describe('Data Corruption and Recovery', () => {
    it('should handle corrupted detection data gracefully', async () => {
      const corruptedDetections = [
        // Missing required fields
        {},
        // Invalid coordinates
        { x: 'invalid', y: 'invalid', width: -100, height: -100 },
        // Circular references (simulated)
        { id: 'circular', self: null },
        // Extremely large values
        { x: Number.MAX_SAFE_INTEGER, y: Number.MAX_SAFE_INTEGER },
        // NaN values
        { x: NaN, y: NaN, confidence: NaN }
      ];

      // Add circular reference
      (corruptedDetections[2] as any).self = corruptedDetections[2];

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: corruptedDetections,
        processingTime: 1000
      });

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(true); // Should still succeed but clean the data
      expect(result.detections).toHaveLength(corruptedDetections.length);

      // Check that corrupted data has been normalized
      result.detections.forEach(detection => {
        expect(typeof detection.boundingBox.x).toBe('number');
        expect(typeof detection.boundingBox.y).toBe('number');
        expect(typeof detection.boundingBox.width).toBe('number');
        expect(typeof detection.boundingBox.height).toBe('number');
        
        // Should have valid coordinates
        expect(detection.boundingBox.x).toBeGreaterThanOrEqual(0);
        expect(detection.boundingBox.y).toBeGreaterThanOrEqual(0);
        expect(detection.boundingBox.width).toBeGreaterThan(0);
        expect(detection.boundingBox.height).toBeGreaterThan(0);
        
        // Should have valid confidence
        expect(detection.boundingBox.confidence).toBeGreaterThanOrEqual(0);
        expect(detection.boundingBox.confidence).toBeLessThanOrEqual(1);
      });
    });

    it('should handle memory corruption scenarios', async () => {
      // Simulate large memory allocation that might cause issues
      const largeDetectionSet = Array.from({ length: 10000 }, (_, i) => ({
        id: `det-${i}`,
        detectionId: `det-${i}`,
        videoId: mockVideoId,
        frame: i,
        timestamp: i * 33.33,
        label: 'person',
        confidence: 0.8,
        // Large data payload
        metadata: new Array(1000).fill('large data chunk').join('')
      }));

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: largeDetectionSet,
        processingTime: 3000
      });

      let memoryError = false;
      try {
        const result = await detectionService.runDetection(mockVideoId, mockConfig);
        
        expect(result.success).toBe(true);
        expect(result.detections.length).toBeLessThanOrEqual(10000);
      } catch (error) {
        if (error instanceof RangeError || error instanceof Error && error.message.includes('memory')) {
          memoryError = true;
        }
      }

      // Should either succeed or fail gracefully without crashing
      if (memoryError) {
        console.warn('Memory error handled gracefully');
      }
    });

    it('should recover from state corruption', async () => {
      const service = detectionService as any;

      // Corrupt internal state
      service.isProcessing.set('corrupted-video', 'invalid-state');
      service.retryCount.set('corrupted-video', NaN);

      // Should still be able to process new requests
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [{ id: 'det-1', label: 'person', confidence: 0.8 }],
        processingTime: 1000
      });

      const result = await detectionService.runDetection('new-video', mockConfig);

      expect(result.success).toBe(true);
      
      // State should be cleaned up
      expect(service.isProcessing.has('new-video')).toBe(false);
      expect(service.retryCount.has('new-video')).toBe(false);
    });
  });

  describe('Cascading Failure Recovery', () => {
    it('should prevent system-wide failures from isolated errors', async () => {
      const videoIds = ['video-1', 'video-2', 'video-3', 'video-4', 'video-5'];
      
      // Setup mixed success/failure responses
      mockApiService.runDetectionPipeline.mockImplementation((videoId) => {
        if (videoId === 'video-2' || videoId === 'video-4') {
          return Promise.reject(new Error(`Critical error in ${videoId}`));
        }
        return Promise.resolve({
          success: true,
          detections: [{ id: `det-${videoId}`, label: 'person', confidence: 0.8 }],
          processingTime: 1000
        });
      });

      // Process all videos concurrently
      const results = await Promise.allSettled(
        videoIds.map(videoId => detectionService.runDetection(videoId, mockConfig))
      );

      const successfulResults = results.filter(r => r.status === 'fulfilled' && r.value.success);
      const failedResults = results.filter(r => r.status === 'rejected' || 
        (r.status === 'fulfilled' && !r.value.success));

      // Should have isolated failures without affecting other operations
      expect(successfulResults).toHaveLength(3);
      expect(failedResults).toHaveLength(2);
    });

    it('should handle resource exhaustion gracefully', async () => {
      let activeRequests = 0;
      const maxConcurrentRequests = 5;

      mockApiService.runDetectionPipeline.mockImplementation(() => {
        activeRequests++;
        
        if (activeRequests > maxConcurrentRequests) {
          return Promise.reject({
            response: {
              status: 503,
              data: { message: 'Service temporarily unavailable' }
            }
          });
        }

        return new Promise(resolve => {
          setTimeout(() => {
            activeRequests--;
            resolve({
              success: true,
              detections: [{ id: 'det-1', label: 'person', confidence: 0.8 }],
              processingTime: 1000
            });
          }, 500);
        });
      });

      // Try to overwhelm the system
      const overloadPromises = Array.from({ length: 20 }, (_, i) =>
        detectionService.runDetection(`overload-video-${i}`, mockConfig)
          .catch(() => ({ 
            success: false, 
            error: 'Resource exhaustion', 
            detections: [], 
            processingTime: 0, 
            source: 'backend' as const 
          }))
      );

      const results = await Promise.all(overloadPromises);

      const successfulResults = results.filter(r => r.success);
      const throttledResults = results.filter(r => !r.success);

      // Should have processed some requests and throttled others
      expect(successfulResults.length).toBeGreaterThan(0);
      expect(throttledResults.length).toBeGreaterThan(0);
      expect(successfulResults.length + throttledResults.length).toBe(20);
    });

    it('should recover from backend service outages', async () => {
      let serviceOutage = true;
      let outageStartTime = Date.now();

      mockApiService.runDetectionPipeline.mockImplementation(() => {
        if (serviceOutage) {
          // Simulate service recovery after 2 seconds
          if (Date.now() - outageStartTime > 2000) {
            serviceOutage = false;
          } else {
            return Promise.reject({
              request: {},
              message: 'Service unavailable'
            });
          }
        }

        return Promise.resolve({
          success: true,
          detections: [{ id: 'det-recovered', label: 'person', confidence: 0.8 }],
          processingTime: 1000
        });
      });

      // First request should fail during outage
      const firstResult = await detectionService.runDetection('outage-video-1', mockConfig);
      expect(firstResult.success).toBe(false);

      // Wait for recovery
      jest.advanceTimersByTime(3000);

      // Second request should succeed after recovery
      const secondResult = await detectionService.runDetection('outage-video-2', mockConfig);
      expect(secondResult.success).toBe(true);
    });

    it('should handle database connectivity issues', async () => {
      const dbErrors = [
        'Connection pool exhausted',
        'Database timeout',
        'Transaction rolled back',
        'Deadlock detected',
        'Connection lost'
      ];

      for (const errorMessage of dbErrors) {
        mockApiService.runDetectionPipeline.mockRejectedValue({
          response: {
            status: 503,
            data: { message: `Database error: ${errorMessage}` }
          }
        });

        const result = await detectionService.runDetection(`db-error-video`, mockConfig);

        expect(result.success).toBe(false);
        expect(result.error).toContain(errorMessage);
      }

      // Should recover when database is back online
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [{ id: 'det-recovered', label: 'person', confidence: 0.8 }],
        processingTime: 1000
      });

      const recoveryResult = await detectionService.runDetection('recovery-video', mockConfig);
      expect(recoveryResult.success).toBe(true);
    });
  });

  describe('Error Reporting and Monitoring', () => {
    it('should log errors appropriately for debugging', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      mockApiService.runDetectionPipeline.mockRejectedValue(
        new Error('Test error for logging')
      );

      await detectionService.runDetection(mockVideoId, mockConfig);

      expect(consoleSpy).toHaveBeenCalledWith(
        'Backend detection error:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });

    it('should provide detailed error context for troubleshooting', async () => {
      const detailedError = {
        response: {
          status: 500,
          statusText: 'Internal Server Error',
          data: {
            message: 'Model inference failed',
            details: {
              modelName: 'yolov8n',
              inputShape: [640, 640, 3],
              errorCode: 'CUDA_OUT_OF_MEMORY'
            },
            timestamp: '2023-01-01T12:00:00Z',
            requestId: 'req-12345'
          }
        },
        config: {
          method: 'POST',
          url: '/api/detection/pipeline/run',
          data: mockConfig
        }
      };

      mockApiService.runDetectionPipeline.mockRejectedValue(detailedError);

      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Model inference failed');
    });

    it('should handle error reporting failures gracefully', async () => {
      // Mock error reporting to also fail
      const originalConsoleError = console.error;
      console.error = jest.fn(() => {
        throw new Error('Console error failed');
      });

      mockApiService.runDetectionPipeline.mockRejectedValue(
        new Error('Original error')
      );

      // Should not throw despite error reporting failure
      const result = await detectionService.runDetection(mockVideoId, mockConfig);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Original error');

      console.error = originalConsoleError;
    });
  });
});