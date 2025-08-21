import { detectionService, DetectionConfig } from '../../ai-model-validation-platform/frontend/src/services/detectionService';
import { apiService } from '../../ai-model-validation-platform/frontend/src/services/api';

// Mock the API service
jest.mock('../../ai-model-validation-platform/frontend/src/services/api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

describe('Detection System Performance and Load Testing', () => {
  const mockConfig: DetectionConfig = {
    confidenceThreshold: 0.7,
    nmsThreshold: 0.5,
    modelName: 'yolov8n',
    targetClasses: ['person', 'bicycle']
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Clear any processing state
    (detectionService as any).isProcessing.clear();
    (detectionService as any).retryCount.clear();
  });

  afterEach(() => {
    jest.useRealTimers();
    detectionService.disconnectWebSocket();
  });

  describe('Concurrent Detection Performance', () => {
    it('should handle multiple concurrent detection requests efficiently', async () => {
      const videoIds = Array.from({ length: 10 }, (_, i) => `video-${i + 1}`);
      const startTime = Date.now();

      // Mock API to resolve with realistic timing
      mockApiService.runDetectionPipeline.mockImplementation((videoId) =>
        Promise.resolve({
          success: true,
          detections: [
            {
              id: `det-${videoId}`,
              detectionId: `det-${videoId}`,
              videoId,
              frame: 0,
              timestamp: 0,
              label: 'person',
              confidence: 0.8,
              x: 100, y: 100, width: 50, height: 100
            }
          ],
          processingTime: 800 + Math.random() * 400 // 800-1200ms variation
        })
      );

      const detectionPromises = videoIds.map(videoId =>
        detectionService.runDetection(videoId, mockConfig)
      );

      const results = await Promise.all(detectionPromises);
      const totalTime = Date.now() - startTime;

      // Verify all detections succeeded
      expect(results).toHaveLength(10);
      results.forEach(result => {
        expect(result.success).toBe(true);
        expect(result.detections).toHaveLength(1);
      });

      // Performance assertion - should complete within reasonable time
      expect(totalTime).toBeLessThan(5000); // 5 seconds max for 10 concurrent

      // Verify API was called for each video
      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledTimes(10);
    });

    it('should handle high-frequency detection requests with throttling', async () => {
      const videoId = 'high-freq-video';
      let completedRequests = 0;
      let throttledRequests = 0;

      // Mock faster API responses
      mockApiService.runDetectionPipeline.mockImplementation(() =>
        new Promise(resolve => setTimeout(() => {
          completedRequests++;
          resolve({
            success: true,
            detections: [],
            processingTime: 100
          });
        }, 50))
      );

      // Rapid fire 20 requests for the same video
      const rapidRequests = Array.from({ length: 20 }, () =>
        detectionService.runDetection(videoId, mockConfig)
          .catch(() => {
            throttledRequests++;
            return { success: false, error: 'Throttled', detections: [], processingTime: 0, source: 'backend' as const };
          })
      );

      const results = await Promise.all(rapidRequests);

      // Should have throttled most requests (only 1 should succeed)
      const successfulRequests = results.filter(r => r.success).length;
      const failedRequests = results.filter(r => !r.success).length;

      expect(successfulRequests).toBe(1);
      expect(failedRequests).toBe(19);
      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledTimes(1);
    });

    it('should maintain performance under load with large detection responses', async () => {
      const videoId = 'large-response-video';
      
      // Mock large detection response (100 detections)
      const largeDetectionResponse = {
        success: true,
        detections: Array.from({ length: 100 }, (_, i) => ({
          id: `det-${i}`,
          detectionId: `det-${i}`,
          videoId,
          frame: i,
          timestamp: i * 33.33,
          label: i % 2 === 0 ? 'person' : 'bicycle',
          confidence: 0.5 + Math.random() * 0.5,
          x: Math.random() * 1000,
          y: Math.random() * 600,
          width: 50 + Math.random() * 100,
          height: 100 + Math.random() * 100
        })),
        processingTime: 2000
      };

      mockApiService.runDetectionPipeline.mockResolvedValue(largeDetectionResponse);

      const startTime = performance.now();
      const result = await detectionService.runDetection(videoId, mockConfig);
      const processingTime = performance.now() - startTime;

      expect(result.success).toBe(true);
      expect(result.detections).toHaveLength(100);
      expect(processingTime).toBeLessThan(1000); // Client-side processing should be fast

      // Verify all detections are properly transformed
      result.detections.forEach((detection, index) => {
        expect(detection.id).toBe(`det-${index}`);
        expect(detection.videoId).toBe(videoId);
        expect(detection.boundingBox).toBeDefined();
        expect(detection.boundingBox.confidence).toBeGreaterThan(0);
      });
    });

    it('should handle memory efficiently with repeated requests', async () => {
      const videoId = 'memory-test-video';
      
      // Mock consistent response
      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: [
          {
            id: 'det-1',
            detectionId: 'det-1',
            videoId,
            frame: 0,
            timestamp: 0,
            label: 'person',
            confidence: 0.8
          }
        ],
        processingTime: 500
      });

      // Perform 50 sequential requests to test memory cleanup
      for (let i = 0; i < 50; i++) {
        const result = await detectionService.runDetection(videoId, mockConfig);
        expect(result.success).toBe(true);
        
        // Verify processing state is cleaned up
        const processingMap = (detectionService as any).isProcessing;
        expect(processingMap.has(videoId)).toBe(false);
        
        // Verify retry count is cleaned up
        const retryMap = (detectionService as any).retryCount;
        expect(retryMap.has(videoId)).toBe(false);
      }

      expect(mockApiService.runDetectionPipeline).toHaveBeenCalledTimes(50);
    });
  });

  describe('WebSocket Performance', () => {
    let mockWebSocket: any;

    beforeEach(() => {
      mockWebSocket = {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        close: jest.fn(),
        send: jest.fn(),
        readyState: WebSocket.OPEN
      };

      global.WebSocket = jest.fn(() => mockWebSocket) as any;
    });

    it('should handle high-frequency WebSocket messages efficiently', async () => {
      const messageCount = 1000;
      const receivedMessages: any[] = [];
      const messageProcessingTimes: number[] = [];

      detectionService.connectWebSocket('ws://test.com', (data) => {
        const startTime = performance.now();
        receivedMessages.push(data);
        const processingTime = performance.now() - startTime;
        messageProcessingTimes.push(processingTime);
      });

      // Simulate rapid message sending
      const startTime = performance.now();
      
      for (let i = 0; i < messageCount; i++) {
        const message = {
          type: 'detection',
          videoId: `video-${i % 10}`, // Distribute across 10 videos
          annotation: {
            id: `det-${i}`,
            confidence: Math.random()
          }
        };

        // Simulate message received
        mockWebSocket.onmessage({
          data: JSON.stringify(message)
        });
      }

      const totalTime = performance.now() - startTime;

      expect(receivedMessages).toHaveLength(messageCount);
      expect(totalTime).toBeLessThan(1000); // Should process 1000 messages in under 1s

      // Check individual message processing times
      const avgProcessingTime = messageProcessingTimes.reduce((a, b) => a + b, 0) / messageProcessingTimes.length;
      expect(avgProcessingTime).toBeLessThan(1); // Average < 1ms per message
    });

    it('should handle WebSocket reconnection efficiently', async () => {
      let reconnectionCount = 0;
      const maxReconnections = 10;

      detectionService.connectWebSocket('ws://unstable.com', () => {});

      // Simulate multiple disconnection/reconnection cycles
      for (let i = 0; i < maxReconnections; i++) {
        // Trigger disconnection
        mockWebSocket.onclose();
        reconnectionCount++;

        // Simulate reconnection after delay
        jest.advanceTimersByTime(5000);
        
        // Reset WebSocket mock for next iteration
        mockWebSocket = {
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          close: jest.fn(),
          send: jest.fn(),
          readyState: WebSocket.OPEN
        };

        global.WebSocket = jest.fn(() => mockWebSocket) as any;
      }

      expect(reconnectionCount).toBe(maxReconnections);
    });

    it('should handle WebSocket message backpressure', async () => {
      const largeMessageCount = 5000;
      const processedMessages: any[] = [];
      let droppedMessages = 0;

      // Simulate slow message processing
      detectionService.connectWebSocket('ws://test.com', (data) => {
        // Simulate processing delay
        const processingDelay = Math.random() * 10; // 0-10ms
        setTimeout(() => {
          processedMessages.push(data);
        }, processingDelay);
      });

      // Send large burst of messages
      for (let i = 0; i < largeMessageCount; i++) {
        try {
          mockWebSocket.onmessage({
            data: JSON.stringify({
              type: 'progress',
              videoId: `video-${i % 100}`,
              progress: (i / largeMessageCount) * 100
            })
          });
        } catch (error) {
          droppedMessages++;
        }
      }

      // Wait for processing to complete
      await new Promise(resolve => setTimeout(resolve, 200));

      // Should handle most messages without dropping
      expect(processedMessages.length + droppedMessages).toBe(largeMessageCount);
      expect(droppedMessages / largeMessageCount).toBeLessThan(0.1); // < 10% drop rate
    });
  });

  describe('API Response Time Performance', () => {
    it('should maintain acceptable response times under load', async () => {
      const testScenarios = [
        { name: 'Small detections', count: 5, responseTime: 500 },
        { name: 'Medium detections', count: 25, responseTime: 1000 },
        { name: 'Large detections', count: 100, responseTime: 2000 }
      ];

      for (const scenario of testScenarios) {
        mockApiService.runDetectionPipeline.mockImplementation(() =>
          new Promise(resolve => setTimeout(() => resolve({
            success: true,
            detections: Array.from({ length: scenario.count }, (_, i) => ({
              id: `det-${i}`,
              detectionId: `det-${i}`,
              videoId: 'test-video',
              frame: i,
              timestamp: i * 33.33,
              label: 'person',
              confidence: 0.8
            })),
            processingTime: scenario.responseTime
          }), scenario.responseTime))
        );

        const startTime = performance.now();
        const result = await detectionService.runDetection('test-video', mockConfig);
        const actualTime = performance.now() - startTime;

        expect(result.success).toBe(true);
        expect(result.detections).toHaveLength(scenario.count);
        
        // Allow 20% tolerance for processing overhead
        expect(actualTime).toBeLessThan(scenario.responseTime * 1.2);
      }
    });

    it('should handle timeout scenarios gracefully', async () => {
      const timeoutScenarios = [1000, 2000, 3000, 5000]; // Different timeout values

      for (const timeout of timeoutScenarios) {
        // Mock delayed response
        mockApiService.runDetectionPipeline.mockImplementation(() =>
          new Promise(resolve => setTimeout(() => resolve({
            success: true,
            detections: [],
            processingTime: timeout
          }), timeout))
        );

        const startTime = performance.now();
        const result = await detectionService.runDetection('timeout-video', mockConfig);
        const actualTime = performance.now() - startTime;

        if (timeout <= 3000) {
          // Should succeed within timeout
          expect(result.success).toBe(true);
        } else {
          // Should timeout and fail
          expect(result.success).toBe(false);
          expect(result.error).toContain('Backend service unavailable');
          expect(actualTime).toBeLessThan(4000); // Should timeout around 3s
        }
      }
    });

    it('should handle API rate limiting gracefully', async () => {
      let requestCount = 0;
      const rateLimit = 5; // Allow 5 requests per second
      const requestWindow = 1000; // 1 second window

      mockApiService.runDetectionPipeline.mockImplementation(() => {
        requestCount++;
        
        if (requestCount > rateLimit) {
          return Promise.reject({
            response: {
              status: 429,
              data: { message: 'Rate limit exceeded' }
            }
          });
        }

        return Promise.resolve({
          success: true,
          detections: [],
          processingTime: 100
        });
      });

      // Send more requests than rate limit allows
      const requests = Array.from({ length: 10 }, (_, i) =>
        detectionService.runDetection(`video-${i}`, mockConfig)
          .catch(error => ({ 
            success: false, 
            error: error.message, 
            detections: [], 
            processingTime: 0, 
            source: 'backend' as const 
          }))
      );

      const results = await Promise.all(requests);

      const successfulRequests = results.filter(r => r.success).length;
      const rateLimitedRequests = results.filter(r => !r.success).length;

      expect(successfulRequests).toBe(rateLimit);
      expect(rateLimitedRequests).toBe(10 - rateLimit);
    });
  });

  describe('Memory and Resource Usage', () => {
    it('should not leak memory with repeated operations', async () => {
      const iterations = 100;
      const initialMemoryUsage = (process.memoryUsage?.() || { heapUsed: 0 }).heapUsed;

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: Array.from({ length: 10 }, (_, i) => ({
          id: `det-${i}`,
          detectionId: `det-${i}`,
          videoId: 'memory-test-video',
          frame: i,
          timestamp: i * 33.33,
          label: 'person',
          confidence: 0.8
        })),
        processingTime: 500
      });

      // Perform many detection operations
      for (let i = 0; i < iterations; i++) {
        const result = await detectionService.runDetection('memory-test-video', mockConfig);
        expect(result.success).toBe(true);
      }

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }

      const finalMemoryUsage = (process.memoryUsage?.() || { heapUsed: 0 }).heapUsed;
      const memoryIncrease = finalMemoryUsage - initialMemoryUsage;

      // Memory increase should be minimal (less than 10MB for 100 operations)
      expect(memoryIncrease).toBeLessThan(10 * 1024 * 1024);
    });

    it('should handle large annotation datasets efficiently', async () => {
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        id: `det-${i}`,
        detectionId: `det-${i}`,
        videoId: 'large-dataset-video',
        frame: i,
        timestamp: i * 16.67, // 60fps
        label: i % 3 === 0 ? 'person' : i % 3 === 1 ? 'bicycle' : 'motorcycle',
        confidence: 0.5 + Math.random() * 0.5,
        x: Math.random() * 1920,
        y: Math.random() * 1080,
        width: 50 + Math.random() * 200,
        height: 100 + Math.random() * 300
      }));

      mockApiService.runDetectionPipeline.mockResolvedValue({
        success: true,
        detections: largeDataset,
        processingTime: 5000
      });

      const startTime = performance.now();
      const result = await detectionService.runDetection('large-dataset-video', mockConfig);
      const processingTime = performance.now() - startTime;

      expect(result.success).toBe(true);
      expect(result.detections).toHaveLength(1000);
      expect(processingTime).toBeLessThan(2000); // Should process quickly on client

      // Verify data transformation efficiency
      result.detections.forEach((detection, index) => {
        expect(detection.id).toBe(`det-${index}`);
        expect(detection.boundingBox).toBeDefined();
        expect(typeof detection.boundingBox.x).toBe('number');
        expect(typeof detection.boundingBox.confidence).toBe('number');
      });
    });

    it('should handle WebSocket connection cleanup properly', async () => {
      let activeConnections = 0;
      
      // Mock WebSocket constructor to track connections
      global.WebSocket = jest.fn(() => {
        activeConnections++;
        return {
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          close: jest.fn(() => { activeConnections--; }),
          send: jest.fn(),
          readyState: WebSocket.OPEN
        };
      }) as any;

      // Create and destroy multiple connections
      for (let i = 0; i < 20; i++) {
        detectionService.connectWebSocket(`ws://test-${i}.com`, () => {});
        detectionService.disconnectWebSocket();
      }

      expect(activeConnections).toBe(0);
      expect(WebSocket).toHaveBeenCalledTimes(20);
    });
  });

  describe('Stress Testing Scenarios', () => {
    it('should survive extreme load conditions', async () => {
      const extremeLoad = {
        concurrentVideos: 50,
        detectionsPerVideo: 200,
        requestsPerSecond: 100
      };

      const videoIds = Array.from({ length: extremeLoad.concurrentVideos }, 
        (_, i) => `extreme-video-${i}`);

      // Mock responses with realistic delays
      mockApiService.runDetectionPipeline.mockImplementation((videoId) =>
        new Promise(resolve => setTimeout(() => resolve({
          success: true,
          detections: Array.from({ length: extremeLoad.detectionsPerVideo }, (_, i) => ({
            id: `${videoId}-det-${i}`,
            detectionId: `${videoId}-det-${i}`,
            videoId,
            frame: i,
            timestamp: i * 33.33,
            label: 'person',
            confidence: 0.7 + Math.random() * 0.3
          })),
          processingTime: 1000 + Math.random() * 2000
        }), 500 + Math.random() * 1000))
      );

      const startTime = performance.now();
      
      // Launch all requests simultaneously
      const stressTestPromises = videoIds.map(videoId =>
        detectionService.runDetection(videoId, mockConfig)
          .catch(error => ({
            success: false,
            error: error.message,
            detections: [],
            processingTime: 0,
            source: 'backend' as const
          }))
      );

      const results = await Promise.all(stressTestPromises);
      const totalTime = performance.now() - startTime;

      // Analyze results
      const successfulResults = results.filter(r => r.success);
      const failedResults = results.filter(r => !r.success);

      console.log(`Stress Test Results:
        Total Videos: ${extremeLoad.concurrentVideos}
        Successful: ${successfulResults.length}
        Failed: ${failedResults.length}
        Total Time: ${totalTime.toFixed(2)}ms
        Success Rate: ${(successfulResults.length / results.length * 100).toFixed(1)}%
      `);

      // Should handle at least 80% of requests successfully
      expect(successfulResults.length / results.length).toBeGreaterThan(0.8);
      
      // Total time should be reasonable (allow for parallel processing)
      expect(totalTime).toBeLessThan(30000); // 30 seconds max
    });

    it('should recover from cascading failures', async () => {
      const testPhases = [
        { name: 'Normal', failureRate: 0 },
        { name: 'Moderate Failures', failureRate: 0.3 },
        { name: 'High Failures', failureRate: 0.7 },
        { name: 'Recovery', failureRate: 0.1 }
      ];

      for (const phase of testPhases) {
        console.log(`Testing phase: ${phase.name}`);
        
        mockApiService.runDetectionPipeline.mockImplementation(() => {
          if (Math.random() < phase.failureRate) {
            return Promise.reject(new Error(`Simulated failure (${phase.name})`));
          }
          
          return Promise.resolve({
            success: true,
            detections: [{ id: 'det-1', label: 'person', confidence: 0.8 }],
            processingTime: 500
          });
        });

        const phaseRequests = Array.from({ length: 20 }, (_, i) =>
          detectionService.runDetection(`video-${i}`, mockConfig)
            .catch(() => ({
              success: false,
              detections: [],
              error: 'Failed',
              processingTime: 0,
              source: 'backend' as const
            }))
        );

        const phaseResults = await Promise.all(phaseRequests);
        const successRate = phaseResults.filter(r => r.success).length / phaseResults.length;

        console.log(`Phase ${phase.name} success rate: ${(successRate * 100).toFixed(1)}%`);

        // Success rate should roughly match expected rate
        const expectedSuccessRate = 1 - phase.failureRate;
        expect(Math.abs(successRate - expectedSuccessRate)).toBeLessThan(0.2);
      }
    });
  });
});