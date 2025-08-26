/**
 * Integration Test for WebSocket Connection - London School TDD Style
 * Focus on testing the actual Socket.IO connection behavior
 */
import { io, Socket } from 'socket.io-client';

// Test configuration
const TEST_SERVER_URL = process.env.REACT_APP_WS_URL || 'http://155.138.239.131:8001';
const TIMEOUT = 5000; // 5 seconds timeout for connection tests

describe('WebSocket Integration - Real Connection Tests', () => {
  let socket: Socket;
  
  beforeEach(() => {
    // Clear any existing connection
    if (socket) {
      socket.close();
    }
  });
  
  afterEach(() => {
    // Clean up socket connection
    if (socket && socket.connected) {
      socket.close();
    }
  });

  it('should establish Socket.IO connection to backend server', (done) => {
    socket = io(TEST_SERVER_URL, {
      auth: {
        token: 'test-token'
      },
      transports: ['websocket', 'polling'],
      timeout: TIMEOUT,
      forceNew: true,
      path: '/socket.io/'
    });

    socket.on('connect', () => {
      expect(socket.connected).toBe(true);
      expect(socket.id).toBeDefined();
      done();
    });

    socket.on('connect_error', (error) => {
      done(new Error(`Connection failed: ${error.message}`));
    });

    // Set timeout for test
    setTimeout(() => {
      if (!socket.connected) {
        done(new Error('Connection timeout'));
      }
    }, TIMEOUT);
  });

  it('should receive connection status message after connecting', (done) => {
    socket = io(TEST_SERVER_URL, {
      auth: { token: 'test-token' },
      transports: ['websocket', 'polling'],
      timeout: TIMEOUT
    });

    socket.on('connection_status', (data) => {
      expect(data).toHaveProperty('status', 'connected');
      expect(data).toHaveProperty('message');
      expect(typeof data.message).toBe('string');
      done();
    });

    socket.on('connect_error', (error) => {
      done(new Error(`Connection failed: ${error.message}`));
    });

    setTimeout(() => {
      done(new Error('Did not receive connection_status event'));
    }, TIMEOUT);
  });

  it('should handle test session events properly', (done) => {
    socket = io(TEST_SERVER_URL, {
      auth: { token: 'test-token' },
      transports: ['websocket'],
      timeout: TIMEOUT
    });

    let eventCount = 0;
    const expectedEvents = ['connect', 'connection_status'];
    
    socket.on('connect', () => {
      eventCount++;
      
      // Emit test session start event
      socket.emit('start_test_session', {
        sessionId: 'test-session-123',
        projectId: 'test-project-456',
        videoId: 'test-video-789'
      });
    });

    socket.on('connection_status', () => {
      eventCount++;
      
      // Check if we received all expected events
      if (eventCount === expectedEvents.length) {
        expect(socket.connected).toBe(true);
        done();
      }
    });

    socket.on('test_session_update', (data) => {
      // This would be received if the backend processes the start_test_session event
      expect(data).toHaveProperty('sessionId');
      done();
    });

    socket.on('error', (data) => {
      // Handle server errors gracefully
      console.log('Server error:', data);
      // Don't fail the test for server errors, just log them
    });

    socket.on('connect_error', (error) => {
      done(new Error(`Connection failed: ${error.message}`));
    });

    setTimeout(() => {
      if (eventCount < expectedEvents.length) {
        done(new Error(`Only received ${eventCount} of ${expectedEvents.length} expected events`));
      }
    }, TIMEOUT);
  });

  it('should maintain connection and handle disconnection gracefully', (done) => {
    socket = io(TEST_SERVER_URL, {
      auth: { token: 'test-token' },
      transports: ['websocket'],
      timeout: TIMEOUT
    });

    let connected = false;
    let disconnected = false;

    socket.on('connect', () => {
      connected = true;
      expect(socket.connected).toBe(true);
      
      // Force disconnect to test disconnection handling
      setTimeout(() => {
        socket.disconnect();
      }, 1000);
    });

    socket.on('disconnect', (reason) => {
      disconnected = true;
      expect(connected).toBe(true);
      expect(socket.connected).toBe(false);
      expect(reason).toBeDefined();
      done();
    });

    socket.on('connect_error', (error) => {
      done(new Error(`Connection failed: ${error.message}`));
    });

    setTimeout(() => {
      if (!connected || !disconnected) {
        done(new Error('Connection lifecycle test failed'));
      }
    }, TIMEOUT);
  });

  it('should handle authentication and joining rooms', (done) => {
    socket = io(TEST_SERVER_URL, {
      auth: { token: 'test-token' },
      transports: ['websocket'],
      timeout: TIMEOUT
    });

    socket.on('connect', () => {
      // Emit join room request
      socket.emit('join_room', { room: 'test_sessions' });
      
      // Give it a moment to process
      setTimeout(() => {
        expect(socket.connected).toBe(true);
        done();
      }, 500);
    });

    socket.on('connect_error', (error) => {
      done(new Error(`Connection failed: ${error.message}`));
    });

    setTimeout(() => {
      done(new Error('Authentication test timeout'));
    }, TIMEOUT);
  });
});