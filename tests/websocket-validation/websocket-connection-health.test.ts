/**
 * WebSocket Connection Health Validation Test Suite
 * Agent 3: WebSocket Connection Validation Agent
 * 
 * Tests comprehensive WebSocket functionality including:
 * - Connection establishment and authentication
 * - Real-time message handling
 * - Error recovery and reconnection
 * - Performance under load
 * - Memory leak detection
 */

import { io, Socket } from 'socket.io-client';
import websocketService, { useWebSocket } from '../../ai-model-validation-platform/frontend/src/services/websocketService';
import { useDetectionWebSocket } from '../../ai-model-validation-platform/frontend/src/hooks/useDetectionWebSocket';

// Test environment configuration
const TEST_WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';
const TEST_SOCKETIO_URL = process.env.REACT_APP_SOCKETIO_URL || 'http://localhost:8001';
const CONNECTION_TIMEOUT = 10000; // 10 seconds
const HIGH_LOAD_MESSAGES = 1000;

describe('WebSocket Connection Health Validation', () => {
  let testSocket: Socket;

  afterEach(async () => {
    if (testSocket) {
      testSocket.disconnect();
      testSocket = null;
    }
    // Clean up websocket service
    websocketService.disconnect();
    await new Promise(resolve => setTimeout(resolve, 100)); // Allow cleanup
  });

  describe('Connection Establishment', () => {
    test('should establish WebSocket connection successfully', async () => {
      const connectionPromise = new Promise<boolean>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          transports: ['websocket', 'polling'],
          timeout: CONNECTION_TIMEOUT,
          forceNew: true,
        });

        testSocket.on('connect', () => {
          expect(testSocket.connected).toBe(true);
          expect(testSocket.id).toBeDefined();
          resolve(true);
        });

        testSocket.on('connect_error', (error) => {
          reject(new Error(`Connection failed: ${error.message}`));
        });

        setTimeout(() => reject(new Error('Connection timeout')), CONNECTION_TIMEOUT);
      });

      await expect(connectionPromise).resolves.toBe(true);
    });

    test('should handle connection authentication flow', async () => {
      const authPromise = new Promise<void>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          auth: { 
            token: 'test-auth-token',
            clientType: 'validation-test' 
          },
          transports: ['websocket'],
          timeout: CONNECTION_TIMEOUT,
        });

        testSocket.on('connect', () => {
          // Send authentication test
          testSocket.emit('authenticate', { token: 'test-auth-token' });
        });

        testSocket.on('auth_success', (data) => {
          expect(data).toHaveProperty('authenticated', true);
          resolve();
        });

        testSocket.on('auth_error', (error) => {
          reject(new Error(`Authentication failed: ${error.message}`));
        });

        testSocket.on('connect_error', (error) => {
          reject(new Error(`Connection failed: ${error.message}`));
        });

        setTimeout(() => reject(new Error('Authentication timeout')), CONNECTION_TIMEOUT);
      });

      await expect(authPromise).resolves.toBeUndefined();
    });

    test('should detect and report connection metrics', async () => {
      const startTime = Date.now();
      
      const metricsPromise = new Promise<void>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          transports: ['websocket'],
          timeout: CONNECTION_TIMEOUT,
        });

        testSocket.on('connect', () => {
          const connectionTime = Date.now() - startTime;
          
          // Validate connection metrics
          expect(connectionTime).toBeLessThan(5000); // Should connect within 5s
          expect(testSocket.connected).toBe(true);
          expect(testSocket.transport?.name).toBeDefined();
          
          // Test ping-pong for latency measurement
          const pingStart = Date.now();
          testSocket.emit('ping', { timestamp: pingStart });
        });

        testSocket.on('pong', (data) => {
          const latency = Date.now() - data.timestamp;
          expect(latency).toBeLessThan(1000); // Should have low latency
          resolve();
        });

        testSocket.on('connect_error', (error) => {
          reject(new Error(`Connection failed: ${error.message}`));
        });

        setTimeout(() => reject(new Error('Metrics test timeout')), CONNECTION_TIMEOUT);
      });

      await expect(metricsPromise).resolves.toBeUndefined();
    });
  });

  describe('Real-time Message Handling', () => {
    beforeEach((done) => {
      testSocket = io(TEST_SOCKETIO_URL, {
        transports: ['websocket'],
        timeout: CONNECTION_TIMEOUT,
      });

      testSocket.on('connect', () => done());
      testSocket.on('connect_error', (error) => done(error));
    });

    test('should handle detection update messages correctly', (done) => {
      const testDetection = {
        type: 'detection',
        videoId: 'test-video-123',
        data: {
          detectionId: 'det-456',
          confidence: 0.85,
          label: 'person',
          bbox: { x: 100, y: 100, width: 50, height: 100 }
        },
        timestamp: new Date().toISOString()
      };

      testSocket.on('detection_update', (received) => {
        try {
          expect(received).toEqual(expect.objectContaining({
            type: 'detection',
            videoId: 'test-video-123',
            data: expect.objectContaining({
              detectionId: expect.any(String),
              confidence: expect.any(Number),
              label: expect.any(String)
            })
          }));
          done();
        } catch (error) {
          done(error);
        }
      });

      // Simulate server sending detection update
      setTimeout(() => {
        testSocket.emit('simulate_detection', testDetection);
      }, 100);
    });

    test('should handle progress update streams', (done) => {
      let progressCount = 0;
      const expectedProgress = [25, 50, 75, 100];

      testSocket.on('progress_update', (data) => {
        try {
          expect(data).toHaveProperty('type', 'progress');
          expect(data).toHaveProperty('videoId');
          expect(data).toHaveProperty('progress');
          expect(typeof data.progress).toBe('number');
          expect(data.progress).toBe(expectedProgress[progressCount]);
          
          progressCount++;
          if (progressCount === expectedProgress.length) {
            done();
          }
        } catch (error) {
          done(error);
        }
      });

      // Simulate progressive updates
      expectedProgress.forEach((progress, index) => {
        setTimeout(() => {
          testSocket.emit('simulate_progress', {
            type: 'progress',
            videoId: 'test-video-progress',
            progress
          });
        }, (index + 1) * 200);
      });
    });

    test('should handle annotation synchronization', (done) => {
      const testAnnotation = {
        id: 'annotation-123',
        videoId: 'test-video-456',
        frameNumber: 100,
        annotations: [
          {
            type: 'rectangle',
            x: 10, y: 20, width: 30, height: 40,
            label: 'test-object',
            confidence: 0.9
          }
        ],
        timestamp: new Date().toISOString()
      };

      testSocket.on('annotation_sync', (received) => {
        try {
          expect(received).toEqual(expect.objectContaining({
            id: 'annotation-123',
            videoId: 'test-video-456',
            frameNumber: 100,
            annotations: expect.arrayContaining([
              expect.objectContaining({
                type: 'rectangle',
                label: 'test-object',
                confidence: 0.9
              })
            ])
          }));
          done();
        } catch (error) {
          done(error);
        }
      });

      setTimeout(() => {
        testSocket.emit('sync_annotation', testAnnotation);
      }, 100);
    });
  });

  describe('Error Recovery and Reconnection', () => {
    test('should handle network disconnection gracefully', async () => {
      const reconnectionPromise = new Promise<void>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          transports: ['websocket'],
          reconnection: true,
          reconnectionAttempts: 3,
          reconnectionDelay: 1000,
          timeout: CONNECTION_TIMEOUT,
        });

        let wasConnected = false;
        let wasDisconnected = false;
        let wasReconnected = false;

        testSocket.on('connect', () => {
          if (!wasConnected) {
            wasConnected = true;
            // Simulate network disconnection after 1 second
            setTimeout(() => {
              testSocket.disconnect();
            }, 1000);
          } else if (wasDisconnected && !wasReconnected) {
            wasReconnected = true;
            resolve();
          }
        });

        testSocket.on('disconnect', (reason) => {
          wasDisconnected = true;
          expect(['transport close', 'io client disconnect']).toContain(reason);
          
          // Trigger reconnection
          setTimeout(() => {
            testSocket.connect();
          }, 500);
        });

        testSocket.on('reconnect', () => {
          wasReconnected = true;
        });

        testSocket.on('connect_error', (error) => {
          if (!wasConnected) {
            reject(new Error(`Initial connection failed: ${error.message}`));
          }
        });

        setTimeout(() => {
          if (!wasReconnected) {
            reject(new Error('Reconnection failed'));
          }
        }, CONNECTION_TIMEOUT);
      });

      await expect(reconnectionPromise).resolves.toBeUndefined();
    });

    test('should handle server restart during active session', async () => {
      const sessionRecoveryPromise = new Promise<void>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          transports: ['websocket'],
          reconnection: true,
          reconnectionAttempts: 5,
          reconnectionDelay: 1000,
        });

        let sessionId: string;
        let sessionRecovered = false;

        testSocket.on('connect', () => {
          if (!sessionId) {
            // Start a test session
            testSocket.emit('start_session', { 
              type: 'validation-test',
              metadata: { testId: 'server-restart-test' }
            });
          } else if (!sessionRecovered) {
            // After reconnection, try to resume session
            testSocket.emit('resume_session', { sessionId });
          }
        });

        testSocket.on('session_started', (data) => {
          sessionId = data.sessionId;
          expect(sessionId).toBeDefined();
          
          // Simulate server restart by forcing disconnection
          setTimeout(() => {
            testSocket.disconnect();
            // Attempt reconnection after brief delay
            setTimeout(() => testSocket.connect(), 2000);
          }, 1000);
        });

        testSocket.on('session_resumed', (data) => {
          expect(data.sessionId).toBe(sessionId);
          sessionRecovered = true;
          resolve();
        });

        testSocket.on('session_recovery_failed', (error) => {
          reject(new Error(`Session recovery failed: ${error.message}`));
        });

        setTimeout(() => {
          reject(new Error('Session recovery test timeout'));
        }, CONNECTION_TIMEOUT * 2);
      });

      await expect(sessionRecoveryPromise).resolves.toBeUndefined();
    });
  });

  describe('Performance Under Load', () => {
    test('should handle high-frequency message streams', async () => {
      const highFrequencyPromise = new Promise<void>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          transports: ['websocket'],
          timeout: CONNECTION_TIMEOUT,
        });

        let messageCount = 0;
        const startTime = Date.now();
        const targetMessages = HIGH_LOAD_MESSAGES / 10; // Reduced for test performance

        testSocket.on('connect', () => {
          // Start high-frequency message stream
          testSocket.emit('start_high_frequency_test', { 
            messageCount: targetMessages,
            interval: 10 // 10ms between messages
          });
        });

        testSocket.on('high_frequency_message', (data) => {
          messageCount++;
          expect(data).toHaveProperty('sequenceNumber');
          expect(data.sequenceNumber).toBe(messageCount);

          if (messageCount === targetMessages) {
            const totalTime = Date.now() - startTime;
            const messagesPerSecond = (messageCount / totalTime) * 1000;
            
            expect(messagesPerSecond).toBeGreaterThan(50); // At least 50 msg/sec
            resolve();
          }
        });

        testSocket.on('connect_error', (error) => {
          reject(new Error(`Connection failed: ${error.message}`));
        });

        setTimeout(() => {
          reject(new Error(`High frequency test timeout. Received ${messageCount}/${targetMessages} messages`));
        }, CONNECTION_TIMEOUT);
      });

      await expect(highFrequencyPromise).resolves.toBeUndefined();
    });

    test('should maintain connection stability under concurrent operations', async () => {
      const concurrentOperationsPromise = new Promise<void>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          transports: ['websocket'],
          timeout: CONNECTION_TIMEOUT,
        });

        const operations = [
          'detection_stream',
          'progress_updates', 
          'annotation_sync',
          'heartbeat_ping'
        ];

        let completedOperations = 0;
        const startTime = Date.now();

        testSocket.on('connect', () => {
          // Start multiple concurrent operations
          operations.forEach((operation, index) => {
            setTimeout(() => {
              testSocket.emit('start_concurrent_operation', {
                operation,
                duration: 5000, // 5 seconds
                frequency: 100 // Every 100ms
              });
            }, index * 100); // Stagger start times
          });
        });

        testSocket.on('operation_completed', (data) => {
          completedOperations++;
          expect(data).toHaveProperty('operation');
          expect(operations).toContain(data.operation);
          
          if (completedOperations === operations.length) {
            const totalTime = Date.now() - startTime;
            expect(totalTime).toBeLessThan(8000); // Should complete within 8 seconds
            expect(testSocket.connected).toBe(true); // Connection should remain stable
            resolve();
          }
        });

        testSocket.on('disconnect', () => {
          reject(new Error('Connection lost during concurrent operations'));
        });

        setTimeout(() => {
          reject(new Error(`Concurrent operations test timeout. Completed ${completedOperations}/${operations.length} operations`));
        }, CONNECTION_TIMEOUT * 1.5);
      });

      await expect(concurrentOperationsPromise).resolves.toBeUndefined();
    });
  });

  describe('Memory Leak Detection', () => {
    test('should properly cleanup event listeners and connections', async () => {
      const memoryTestPromise = new Promise<void>((resolve, reject) => {
        const initialConnections = io.Manager.prototype.sockets?.size || 0;
        const sockets: Socket[] = [];

        // Create multiple connections
        for (let i = 0; i < 10; i++) {
          const socket = io(TEST_SOCKETIO_URL, {
            transports: ['websocket'],
            forceNew: true,
          });

          socket.on('connect', () => {
            // Add event listeners to simulate real usage
            socket.on('test_event', () => {});
            socket.on('another_event', () => {});
          });

          sockets.push(socket);
        }

        // Wait for all connections
        setTimeout(() => {
          const connectedCount = sockets.filter(s => s.connected).length;
          expect(connectedCount).toBe(10);

          // Disconnect all sockets
          sockets.forEach(socket => {
            socket.removeAllListeners();
            socket.disconnect();
          });

          // Wait for cleanup
          setTimeout(() => {
            const finalConnections = io.Manager.prototype.sockets?.size || 0;
            expect(finalConnections).toBeLessThanOrEqual(initialConnections + 1); // Allow some tolerance
            resolve();
          }, 1000);
        }, 2000);

        setTimeout(() => reject(new Error('Memory leak test timeout')), CONNECTION_TIMEOUT);
      });

      await expect(memoryTestPromise).resolves.toBeUndefined();
    });

    test('should handle message buffer limits correctly', async () => {
      const bufferTestPromise = new Promise<void>((resolve, reject) => {
        testSocket = io(TEST_SOCKETIO_URL, {
          transports: ['websocket'],
          timeout: CONNECTION_TIMEOUT,
        });

        let bufferOverflowDetected = false;

        testSocket.on('connect', () => {
          // Send messages faster than they can be processed
          for (let i = 0; i < 1000; i++) {
            testSocket.emit('buffer_test_message', {
              sequenceId: i,
              data: 'x'.repeat(1000) // 1KB per message
            });
          }
        });

        testSocket.on('buffer_overflow_warning', () => {
          bufferOverflowDetected = true;
        });

        testSocket.on('buffer_test_complete', (stats) => {
          expect(stats).toHaveProperty('messagesProcessed');
          expect(stats).toHaveProperty('messagesDropped');
          expect(stats.messagesProcessed).toBeGreaterThan(0);
          
          // Buffer overflow handling should be graceful
          if (bufferOverflowDetected) {
            expect(stats.messagesDropped).toBeGreaterThan(0);
          }
          
          resolve();
        });

        setTimeout(() => {
          reject(new Error('Buffer test timeout'));
        }, CONNECTION_TIMEOUT);
      });

      await expect(bufferTestPromise).resolves.toBeUndefined();
    });
  });
});

// WebSocket Service Integration Tests
describe('WebSocket Service Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should initialize with correct configuration', () => {
    expect(websocketService).toBeDefined();
    expect(typeof websocketService.connect).toBe('function');
    expect(typeof websocketService.disconnect).toBe('function');
    expect(typeof websocketService.subscribe).toBe('function');
    expect(typeof websocketService.emit).toBe('function');
  });

  test('should provide connection health status', () => {
    const healthStatus = websocketService.getHealthStatus();
    
    expect(healthStatus).toHaveProperty('isConnected');
    expect(healthStatus).toHaveProperty('connectionState');
    expect(healthStatus).toHaveProperty('url');
    expect(healthStatus).toHaveProperty('metrics');
    expect(healthStatus).toHaveProperty('subscriberCount');
    expect(typeof healthStatus.isConnected).toBe('boolean');
    expect(typeof healthStatus.connectionState).toBe('string');
    expect(typeof healthStatus.subscriberCount).toBe('number');
  });

  test('should handle subscription cleanup properly', () => {
    const mockCallback = jest.fn();
    const unsubscribe = websocketService.subscribe('test-event', mockCallback);
    
    expect(typeof unsubscribe).toBe('function');
    
    // Should not crash when calling unsubscribe
    expect(() => unsubscribe()).not.toThrow();
  });
});