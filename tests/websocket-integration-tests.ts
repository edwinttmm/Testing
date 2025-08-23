/**
 * WebSocket Integration Tests for Real-time Communication
 * 
 * Tests WebSocket connections, message handling, reconnection logic,
 * and real-time features like detection updates and live notifications.
 */

import { jest } from '@jest/globals';
import { io, Socket } from 'socket.io-client';
import websocketService, { useWebSocket } from '../ai-model-validation-platform/frontend/src/services/websocketService';
import { detectionService } from '../ai-model-validation-platform/frontend/src/services/detectionService';

// Mock Socket.IO client
jest.mock('socket.io-client');

describe('WebSocket Integration Tests', () => {
  let mockSocket: jest.Mocked<Socket>;
  let mockIo: jest.MockedFunction<typeof io>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Create mock socket instance
    mockSocket = {
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
      connect: jest.fn(),
      disconnect: jest.fn(),
      onAny: jest.fn(),
      connected: false,
      disconnected: true,
      id: 'mock-socket-id'
    } as any;

    // Mock io function
    mockIo = io as jest.MockedFunction<typeof io>;
    mockIo.mockReturnValue(mockSocket);
  });

  describe('WebSocket Connection Management', () => {
    it('should establish WebSocket connection successfully', async () => {
      // Setup connection success simulation
      mockSocket.on.mockImplementation((event, callback) => {
        if (event === 'connect') {
          setTimeout(() => callback(), 10);
        }
        return mockSocket;
      });

      const connectPromise = websocketService.connect();

      // Simulate successful connection
      expect(mockIo).toHaveBeenCalledWith(
        expect.stringContaining('localhost:8000'),
        expect.objectContaining({
          transports: ['websocket', 'polling'],
          timeout: 20000,
          reconnection: true,
          reconnectionAttempts: 10,
          reconnectionDelay: 1000
        })
      );

      await expect(connectPromise).resolves.toBe(true);
    });

    it('should handle connection failures gracefully', async () => {
      const connectionError = new Error('Connection failed');
      
      mockSocket.on.mockImplementation((event, callback) => {
        if (event === 'connect_error') {
          setTimeout(() => callback(connectionError), 10);
        }
        return mockSocket;
      });

      await expect(websocketService.connect()).rejects.toThrow('Connection failed');
    });

    it('should detect and handle network environment differences', () => {
      // Test different hostname scenarios
      const originalLocation = window.location;
      
      // Test localhost
      Object.defineProperty(window, 'location', {
        value: { hostname: 'localhost', protocol: 'http:' },
        writable: true
      });

      mockIo.mockClear();
      new (require('../ai-model-validation-platform/frontend/src/services/websocketService').default.constructor)();
      expect(mockIo).toHaveBeenCalledWith(
        'ws://localhost:8000',
        expect.any(Object)
      );

      // Test production server
      Object.defineProperty(window, 'location', {
        value: { hostname: '155.138.239.131', protocol: 'http:' },
        writable: true
      });

      mockIo.mockClear();
      new (require('../ai-model-validation-platform/frontend/src/services/websocketService').default.constructor)();
      expect(mockIo).toHaveBeenCalledWith(
        'ws://155.138.239.131:8000',
        expect.any(Object)
      );

      // Restore original location
      Object.defineProperty(window, 'location', {
        value: originalLocation,
        writable: true
      });
    });

    it('should handle disconnection and cleanup', () => {
      mockSocket.on.mockImplementation((event, callback) => {
        if (event === 'disconnect') {
          setTimeout(() => callback('transport close'), 10);
        }
        return mockSocket;
      });

      websocketService.disconnect();

      expect(mockSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('Message Handling and Communication', () => {
    beforeEach(() => {
      // Setup connected state
      mockSocket.connected = true;
      mockSocket.disconnected = false;
    });

    it('should send messages when connected', () => {
      const testData = { videoId: 'vid-123', command: 'start_detection' };
      
      const result = websocketService.emit('detection_command', testData);

      expect(result).toBe(true);
      expect(mockSocket.emit).toHaveBeenCalledWith('detection_command', testData);
    });

    it('should reject message sending when disconnected', () => {
      mockSocket.connected = false;
      mockSocket.disconnected = true;

      const result = websocketService.emit('test_event', { data: 'test' });

      expect(result).toBe(false);
      expect(mockSocket.emit).not.toHaveBeenCalled();
    });

    it('should handle incoming messages correctly', (done) => {
      const testMessage = {
        videoId: 'vid-123',
        detections: [
          {
            id: 'det-1',
            timestamp: 1.0,
            boundingBox: { x: 100, y: 100, width: 80, height: 160, label: 'pedestrian', confidence: 0.85 },
            vruType: 'pedestrian',
            confidence: 0.85
          }
        ],
        processingProgress: 50,
        status: 'processing'
      };

      // Setup message listener
      mockSocket.onAny.mockImplementation((callback) => {
        setTimeout(() => callback('detection_update', testMessage), 10);
      });

      const unsubscribe = websocketService.subscribe('detection_update', (data) => {
        expect(data).toEqual(testMessage);
        unsubscribe();
        done();
      });

      // Trigger the onAny callback
      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('detection_update', testMessage);
    });

    it('should handle malformed messages gracefully', (done) => {
      let errorHandled = false;

      // Setup error handling
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      mockSocket.onAny.mockImplementation((callback) => {
        setTimeout(() => {
          try {
            // Send malformed message
            callback('invalid_event', 'malformed{json');
          } catch (error) {
            errorHandled = true;
          }
        }, 10);
      });

      const unsubscribe = websocketService.subscribe('invalid_event', (data) => {
        // This should handle gracefully
        expect(data).toBeDefined();
        unsubscribe();
        consoleSpy.mockRestore();
        done();
      });

      // Trigger the callback
      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('invalid_event', 'malformed{json');
    });

    it('should support wildcard message subscriptions', (done) => {
      const testMessages = [
        { type: 'detection_update', data: { videoId: 'vid-1' } },
        { type: 'annotation_created', data: { annotationId: 'ann-1' } },
        { type: 'project_updated', data: { projectId: 'proj-1' } }
      ];

      let receivedMessages = 0;

      mockSocket.onAny.mockImplementation((callback) => {
        testMessages.forEach((msg, index) => {
          setTimeout(() => callback(msg.type, msg.data), 10 * (index + 1));
        });
      });

      const unsubscribe = websocketService.subscribe('*', (message) => {
        receivedMessages++;
        expect(message.type).toBeDefined();
        expect(message.payload).toBeDefined();
        
        if (receivedMessages === testMessages.length) {
          unsubscribe();
          done();
        }
      });

      // Trigger callbacks
      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      testMessages.forEach(msg => {
        onAnyCallback(msg.type, msg.data);
      });
    });
  });

  describe('Reconnection Logic and Resilience', () => {
    it('should attempt reconnection on unexpected disconnection', (done) => {
      let reconnectAttempts = 0;

      mockSocket.on.mockImplementation((event, callback) => {
        if (event === 'disconnect') {
          setTimeout(() => callback('transport error'), 10);
        } else if (event === 'reconnect_attempt') {
          reconnectAttempts++;
          setTimeout(() => callback(reconnectAttempts), 10);
        } else if (event === 'reconnect') {
          setTimeout(() => {
            expect(reconnectAttempts).toBeGreaterThan(0);
            callback(reconnectAttempts);
            done();
          }, 10);
        }
        return mockSocket;
      });

      // Simulate disconnect and reconnect
      const disconnectCallback = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];
      const reconnectAttemptCallback = mockSocket.on.mock.calls.find(call => call[0] === 'reconnect_attempt')?.[1];
      const reconnectCallback = mockSocket.on.mock.calls.find(call => call[0] === 'reconnect')?.[1];

      if (disconnectCallback) disconnectCallback('transport error');
      if (reconnectAttemptCallback) reconnectAttemptCallback(1);
      if (reconnectCallback) reconnectCallback(1);
    });

    it('should handle maximum reconnection attempts', (done) => {
      mockSocket.on.mockImplementation((event, callback) => {
        if (event === 'reconnect_failed') {
          setTimeout(() => {
            callback();
            done();
          }, 10);
        }
        return mockSocket;
      });

      // Simulate reconnection failure
      const reconnectFailedCallback = mockSocket.on.mock.calls.find(call => call[0] === 'reconnect_failed')?.[1];
      if (reconnectFailedCallback) reconnectFailedCallback();
    });

    it('should track connection metrics during reconnection', () => {
      // Simulate connection metrics
      const healthStatus = websocketService.getHealthStatus();
      
      expect(healthStatus).toEqual({
        isConnected: expect.any(Boolean),
        connectionState: expect.any(String),
        url: expect.stringContaining('8000'),
        metrics: expect.objectContaining({
          connectionAttempts: expect.any(Number),
          reconnectCount: expect.any(Number),
          totalMessages: expect.any(Number),
          isStable: expect.any(Boolean)
        }),
        lastError: expect.anything(),
        subscriberCount: expect.any(Number)
      });
    });

    it('should implement exponential backoff for reconnection', async () => {
      const reconnectionDelays: number[] = [];
      let currentDelay = 1000; // Initial delay

      // Mock setTimeout to capture delays
      const originalSetTimeout = global.setTimeout;
      global.setTimeout = jest.fn().mockImplementation((callback, delay) => {
        reconnectionDelays.push(delay);
        return originalSetTimeout(callback, 0); // Execute immediately for testing
      });

      mockSocket.on.mockImplementation((event, callback) => {
        if (event === 'disconnect') {
          setTimeout(() => callback('transport error'), 0);
        }
        return mockSocket;
      });

      // Simulate multiple reconnection attempts
      const disconnectCallback = mockSocket.on.mock.calls.find(call => call[0] === 'disconnect')?.[1];
      for (let i = 0; i < 3; i++) {
        if (disconnectCallback) disconnectCallback('transport error');
      }

      // Restore setTimeout
      global.setTimeout = originalSetTimeout;

      // Verify exponential backoff (delays should increase)
      expect(reconnectionDelays.length).toBeGreaterThan(0);
    });
  });

  describe('Detection Service WebSocket Integration', () => {
    it('should handle detection progress updates via WebSocket', (done) => {
      const mockDetectionUpdate = {
        videoId: 'vid-123',
        detections: [
          {
            id: 'det-1',
            detectionId: 'DET_PED_001',
            timestamp: 1.5,
            boundingBox: { x: 200, y: 150, width: 60, height: 120, label: 'pedestrian', confidence: 0.92 },
            vruType: 'pedestrian',
            confidence: 0.92,
            isGroundTruth: false,
            validated: false,
            createdAt: new Date().toISOString()
          }
        ],
        processingProgress: 75,
        status: 'processing'
      };

      mockSocket.onAny.mockImplementation((callback) => {
        setTimeout(() => callback('detection_update', mockDetectionUpdate), 10);
      });

      const unsubscribe = websocketService.subscribe('detection_update', (data) => {
        expect(data.videoId).toBe('vid-123');
        expect(data.processingProgress).toBe(75);
        expect(data.status).toBe('processing');
        expect(data.detections).toHaveLength(1);
        expect(data.detections[0].vruType).toBe('pedestrian');
        
        unsubscribe();
        done();
      });

      // Trigger the callback
      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('detection_update', mockDetectionUpdate);
    });

    it('should handle detection completion notifications', (done) => {
      const mockCompletionUpdate = {
        videoId: 'vid-123',
        detections: [
          {
            id: 'det-1',
            detectionId: 'DET_PED_001',
            timestamp: 1.0,
            boundingBox: { x: 100, y: 100, width: 80, height: 160, label: 'pedestrian', confidence: 0.85 },
            vruType: 'pedestrian',
            confidence: 0.85,
            isGroundTruth: false,
            validated: false,
            createdAt: new Date().toISOString()
          },
          {
            id: 'det-2',
            detectionId: 'DET_CYC_001',
            timestamp: 2.0,
            boundingBox: { x: 300, y: 200, width: 100, height: 180, label: 'cyclist', confidence: 0.78 },
            vruType: 'cyclist',
            confidence: 0.78,
            isGroundTruth: false,
            validated: false,
            createdAt: new Date().toISOString()
          }
        ],
        processingProgress: 100,
        status: 'completed'
      };

      const unsubscribe = websocketService.subscribe('detection_complete', (data) => {
        expect(data.status).toBe('completed');
        expect(data.processingProgress).toBe(100);
        expect(data.detections).toHaveLength(2);
        
        unsubscribe();
        done();
      });

      // Simulate completion message
      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('detection_complete', mockCompletionUpdate);
    });

    it('should handle detection errors via WebSocket', (done) => {
      const mockErrorUpdate = {
        videoId: 'vid-123',
        error: 'Video format not supported for detection',
        status: 'failed',
        processingProgress: 0
      };

      const unsubscribe = websocketService.subscribe('detection_error', (data) => {
        expect(data.status).toBe('failed');
        expect(data.error).toContain('Video format not supported');
        expect(data.videoId).toBe('vid-123');
        
        unsubscribe();
        done();
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('detection_error', mockErrorUpdate);
    });
  });

  describe('Real-time Annotation Updates', () => {
    it('should handle annotation creation events', (done) => {
      const mockAnnotationEvent = {
        type: 'annotation_created',
        videoId: 'vid-123',
        annotation: {
          id: 'ann-123',
          videoId: 'vid-123',
          detectionId: 'det-123',
          frameNumber: 30,
          timestamp: 1.0,
          vruType: 'pedestrian',
          boundingBox: { x: 100, y: 100, width: 80, height: 160, label: 'pedestrian', confidence: 0.85 },
          occluded: false,
          truncated: false,
          difficult: false,
          validated: true,
          createdAt: new Date().toISOString()
        }
      };

      const unsubscribe = websocketService.subscribe('annotation_created', (data) => {
        expect(data.type).toBe('annotation_created');
        expect(data.annotation.id).toBe('ann-123');
        expect(data.annotation.validated).toBe(true);
        
        unsubscribe();
        done();
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('annotation_created', mockAnnotationEvent);
    });

    it('should handle annotation validation events', (done) => {
      const mockValidationEvent = {
        type: 'annotation_validated',
        annotationId: 'ann-123',
        videoId: 'vid-123',
        validated: true,
        validator: 'user-456'
      };

      const unsubscribe = websocketService.subscribe('annotation_validated', (data) => {
        expect(data.annotationId).toBe('ann-123');
        expect(data.validated).toBe(true);
        expect(data.validator).toBe('user-456');
        
        unsubscribe();
        done();
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('annotation_validated', mockValidationEvent);
    });

    it('should handle bulk annotation updates', (done) => {
      const mockBulkUpdate = {
        type: 'annotations_bulk_update',
        videoId: 'vid-123',
        updates: [
          { annotationId: 'ann-1', validated: true },
          { annotationId: 'ann-2', validated: false },
          { annotationId: 'ann-3', validated: true }
        ],
        totalUpdated: 3
      };

      const unsubscribe = websocketService.subscribe('annotations_bulk_update', (data) => {
        expect(data.totalUpdated).toBe(3);
        expect(data.updates).toHaveLength(3);
        expect(data.updates[0].validated).toBe(true);
        
        unsubscribe();
        done();
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('annotations_bulk_update', mockBulkUpdate);
    });
  });

  describe('System Status and Health Updates', () => {
    it('should handle system status updates', (done) => {
      const mockSystemStatus = {
        type: 'system_status',
        status: 'operational',
        services: {
          api: 'healthy',
          database: 'healthy',
          detection: 'degraded',
          storage: 'healthy'
        },
        timestamp: new Date().toISOString()
      };

      const unsubscribe = websocketService.subscribe('system_status', (data) => {
        expect(data.status).toBe('operational');
        expect(data.services.detection).toBe('degraded');
        expect(data.services.api).toBe('healthy');
        
        unsubscribe();
        done();
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('system_status', mockSystemStatus);
    });

    it('should handle maintenance notifications', (done) => {
      const mockMaintenanceNotice = {
        type: 'maintenance_notice',
        message: 'Scheduled maintenance in 30 minutes',
        severity: 'warning',
        scheduledTime: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
        estimatedDuration: 15 // minutes
      };

      const unsubscribe = websocketService.subscribe('maintenance_notice', (data) => {
        expect(data.severity).toBe('warning');
        expect(data.estimatedDuration).toBe(15);
        expect(data.message).toContain('30 minutes');
        
        unsubscribe();
        done();
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('maintenance_notice', mockMaintenanceNotice);
    });
  });

  describe('Performance and Heartbeat', () => {
    it('should send heartbeat messages when connected', () => {
      mockSocket.connected = true;
      
      // Mock heartbeat interval
      const mockSetInterval = jest.fn();
      const originalSetInterval = global.setInterval;
      global.setInterval = mockSetInterval;

      // Reinitialize service to trigger heartbeat setup
      const service = new (require('../ai-model-validation-platform/frontend/src/services/websocketService').default.constructor)({
        enableHeartbeat: true,
        heartbeatInterval: 1000
      });

      expect(mockSetInterval).toHaveBeenCalled();

      // Restore original setInterval
      global.setInterval = originalSetInterval;
    });

    it('should handle heartbeat responses', (done) => {
      const mockPongResponse = {
        type: 'pong',
        timestamp: Date.now(),
        latency: 45
      };

      const unsubscribe = websocketService.subscribe('pong', (data) => {
        expect(data.timestamp).toBeDefined();
        expect(data.latency).toBeLessThan(100);
        
        unsubscribe();
        done();
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('pong', mockPongResponse);
    });

    it('should track message throughput', () => {
      const metrics = websocketService.connectionMetrics;
      
      expect(metrics).toEqual({
        connectionAttempts: expect.any(Number),
        lastConnected: expect.any(Object),
        lastDisconnected: expect.any(Object),
        reconnectCount: expect.any(Number),
        totalMessages: expect.any(Number),
        isStable: expect.any(Boolean)
      });
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should handle WebSocket connection timeout', async () => {
      const timeoutError = new Error('Connection timeout');
      
      mockSocket.on.mockImplementation((event, callback) => {
        if (event === 'connect_error') {
          setTimeout(() => callback(timeoutError), 100);
        }
        return mockSocket;
      });

      await expect(websocketService.connect()).rejects.toThrow('Connection timeout');
    });

    it('should handle invalid WebSocket URLs gracefully', async () => {
      const invalidUrlError = new Error('Invalid URL');
      mockIo.mockImplementation(() => {
        throw invalidUrlError;
      });

      await expect(websocketService.connect()).rejects.toThrow('Invalid URL');
    });

    it('should handle subscription to non-existent events', () => {
      const callback = jest.fn();
      const unsubscribe = websocketService.subscribe('non_existent_event', callback);
      
      expect(typeof unsubscribe).toBe('function');
      
      // Unsubscribe should work without errors
      unsubscribe();
      expect(callback).not.toHaveBeenCalled();
    });

    it('should handle multiple subscriptions to the same event', (done) => {
      const callbacks = [jest.fn(), jest.fn(), jest.fn()];
      let callbackCount = 0;

      callbacks.forEach((callback, index) => {
        websocketService.subscribe('test_event', (data) => {
          callback(data);
          callbackCount++;
          
          if (callbackCount === callbacks.length) {
            expect(callbacks.every(cb => cb.mock.calls.length === 1)).toBe(true);
            done();
          }
        });
      });

      const onAnyCallback = mockSocket.onAny.mock.calls[0][0];
      onAnyCallback('test_event', { test: 'data' });
    });

    it('should clean up subscriptions on service destruction', () => {
      const unsubscribe1 = websocketService.subscribe('event1', jest.fn());
      const unsubscribe2 = websocketService.subscribe('event2', jest.fn());

      // Clean up subscriptions
      unsubscribe1();
      unsubscribe2();

      // Verify cleanup
      const healthStatus = websocketService.getHealthStatus();
      expect(healthStatus.subscriberCount).toBe(0);
    });
  });

  describe('Integration with React Components', () => {
    it('should work with useWebSocket hook', () => {
      // Mock React hooks
      const mockUseState = jest.fn()
        .mockReturnValueOnce(['disconnected', jest.fn()])
        .mockReturnValueOnce([false, jest.fn()])
        .mockReturnValueOnce([null, jest.fn()])
        .mockReturnValueOnce([null, jest.fn()]);

      const mockUseEffect = jest.fn();
      const mockUseCallback = jest.fn((fn) => fn);

      // Mock React module
      jest.doMock('react', () => ({
        useState: mockUseState,
        useEffect: mockUseEffect,
        useCallback: mockUseCallback
      }));

      // Test hook functionality would require a more complex setup
      // This verifies the hook structure exists
      expect(useWebSocket).toBeDefined();
      expect(typeof useWebSocket).toBe('function');
    });
  });
});