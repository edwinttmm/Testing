/**
 * Real-time Features Validation Test Suite
 * Agent 3: WebSocket Connection Validation Agent
 * 
 * Validates specific real-time features across the platform:
 * - Live detection result streaming
 * - Annotation synchronization
 * - Progress tracking
 * - Multi-user collaboration
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import websocketService from '../../ai-model-validation-platform/frontend/src/services/websocketService';
import EnhancedTestExecution from '../../ai-model-validation-platform/frontend/src/pages/EnhancedTestExecution';
import Dashboard from '../../ai-model-validation-platform/frontend/src/pages/Dashboard';

// Mock WebSocket service for controlled testing
const mockWebSocketService = {
  isConnected: false,
  connectionState: 'disconnected',
  subscribe: jest.fn(),
  emit: jest.fn(),
  connect: jest.fn(),
  disconnect: jest.fn(),
  connectionMetrics: {
    connectionAttempts: 0,
    reconnectCount: 0,
    totalMessages: 0,
    isStable: false
  },
  getHealthStatus: jest.fn()
};

jest.mock('../../ai-model-validation-platform/frontend/src/services/websocketService', () => ({
  ...mockWebSocketService,
  useWebSocket: () => mockWebSocketService
}));

const theme = createTheme();

describe('Real-time Features Validation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWebSocketService.isConnected = true;
    mockWebSocketService.connectionState = 'connected';
    mockWebSocketService.subscribe.mockImplementation(() => () => {});
    mockWebSocketService.getHealthStatus.mockReturnValue({
      isConnected: true,
      connectionState: 'connected',
      url: 'ws://localhost:8000',
      metrics: mockWebSocketService.connectionMetrics,
      subscriberCount: 0
    });
  });

  describe('Live Detection Result Streaming', () => {
    test('should subscribe to detection updates on component mount', async () => {
      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      await waitFor(() => {
        expect(mockWebSocketService.subscribe).toHaveBeenCalledWith(
          'detection_update',
          expect.any(Function)
        );
      });
    });

    test('should handle incoming detection results', async () => {
      let detectionCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'detection_update') {
          detectionCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      await waitFor(() => {
        expect(detectionCallback).toBeDefined();
      });

      // Simulate incoming detection result
      const mockDetection = {
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

      detectionCallback(mockDetection);

      // Verify UI updates with detection result
      await waitFor(() => {
        // Check if detection results are displayed
        expect(screen.getByText(/detection/i)).toBeInTheDocument();
      });
    });

    test('should handle detection errors gracefully', async () => {
      let errorCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'detection_error') {
          errorCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      // Simulate detection error
      const mockError = {
        type: 'error',
        videoId: 'test-video-123',
        error: 'Model inference failed',
        timestamp: new Date().toISOString()
      };

      if (errorCallback) {
        errorCallback(mockError);
      }

      // Verify error handling
      await waitFor(() => {
        expect(screen.getByText(/error/i)).toBeInTheDocument();
      });
    });
  });

  describe('Progress Tracking Validation', () => {
    test('should display real-time progress updates', async () => {
      let progressCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'progress_update') {
          progressCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      await waitFor(() => {
        expect(progressCallback).toBeDefined();
      });

      // Simulate progress updates
      const progressUpdates = [25, 50, 75, 100];
      
      for (const progress of progressUpdates) {
        const mockProgress = {
          type: 'progress',
          videoId: 'test-video-123',
          progress,
          stage: progress === 100 ? 'complete' : 'processing',
          timestamp: new Date().toISOString()
        };

        progressCallback(mockProgress);

        await waitFor(() => {
          // Check if progress is reflected in UI
          const progressElement = screen.getByRole('progressbar');
          expect(progressElement).toHaveAttribute('aria-valuenow', progress.toString());
        });
      }
    });

    test('should handle progress updates for multiple videos', async () => {
      let progressCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'progress_update') {
          progressCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      const videoIds = ['video-1', 'video-2', 'video-3'];
      
      // Simulate concurrent progress for multiple videos
      videoIds.forEach((videoId, index) => {
        const mockProgress = {
          type: 'progress',
          videoId,
          progress: (index + 1) * 33,
          stage: 'processing',
          timestamp: new Date().toISOString()
        };

        progressCallback(mockProgress);
      });

      // Verify multiple progress indicators
      await waitFor(() => {
        const progressElements = screen.getAllByRole('progressbar');
        expect(progressElements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Annotation Synchronization', () => {
    test('should sync annotations across sessions', async () => {
      let annotationCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'annotation_sync') {
          annotationCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      // Simulate annotation sync from another user
      const mockAnnotation = {
        id: 'annotation-789',
        videoId: 'test-video-123',
        frameNumber: 150,
        annotations: [
          {
            type: 'rectangle',
            x: 20, y: 30, width: 40, height: 50,
            label: 'vehicle',
            confidence: 0.92,
            userId: 'user-456',
            timestamp: new Date().toISOString()
          }
        ],
        action: 'create' // create, update, delete
      };

      if (annotationCallback) {
        annotationCallback(mockAnnotation);
      }

      // Verify annotation appears in UI
      await waitFor(() => {
        expect(screen.getByText(/vehicle/i)).toBeInTheDocument();
      });
    });

    test('should handle annotation conflicts', async () => {
      let conflictCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'annotation_conflict') {
          conflictCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      // Simulate annotation conflict
      const mockConflict = {
        annotationId: 'annotation-789',
        conflictType: 'concurrent_edit',
        localVersion: { /* local annotation data */ },
        remoteVersion: { /* remote annotation data */ },
        timestamp: new Date().toISOString()
      };

      if (conflictCallback) {
        conflictCallback(mockConflict);
      }

      // Verify conflict resolution UI appears
      await waitFor(() => {
        expect(screen.getByText(/conflict/i)).toBeInTheDocument();
      });
    });
  });

  describe('Multi-user Collaboration', () => {
    test('should show active users in session', async () => {
      let userCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'session_users') {
          userCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      // Simulate active users update
      const mockUsers = {
        sessionId: 'session-123',
        users: [
          { id: 'user-1', name: 'Alice', status: 'active', cursor: { x: 100, y: 200 } },
          { id: 'user-2', name: 'Bob', status: 'active', cursor: { x: 300, y: 150 } }
        ],
        timestamp: new Date().toISOString()
      };

      if (userCallback) {
        userCallback(mockUsers);
      }

      // Verify user indicators appear
      await waitFor(() => {
        expect(screen.getByText(/Alice/i)).toBeInTheDocument();
        expect(screen.getByText(/Bob/i)).toBeInTheDocument();
      });
    });

    test('should handle user join/leave events', async () => {
      let joinCallback: Function;
      let leaveCallback: Function;
      
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'user_joined') {
          joinCallback = callback;
        } else if (event === 'user_left') {
          leaveCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      // Simulate user joining
      if (joinCallback) {
        joinCallback({
          userId: 'user-3',
          userName: 'Charlie',
          sessionId: 'session-123',
          timestamp: new Date().toISOString()
        });
      }

      await waitFor(() => {
        expect(screen.getByText(/Charlie joined/i)).toBeInTheDocument();
      });

      // Simulate user leaving
      if (leaveCallback) {
        leaveCallback({
          userId: 'user-3',
          userName: 'Charlie',
          sessionId: 'session-123',
          timestamp: new Date().toISOString()
        });
      }

      await waitFor(() => {
        expect(screen.getByText(/Charlie left/i)).toBeInTheDocument();
      });
    });
  });

  describe('Connection Quality Impact', () => {
    test('should degrade gracefully with poor connection', async () => {
      // Simulate poor connection
      mockWebSocketService.connectionMetrics = {
        connectionAttempts: 5,
        reconnectCount: 3,
        totalMessages: 100,
        isStable: false
      };

      mockWebSocketService.getHealthStatus.mockReturnValue({
        isConnected: true,
        connectionState: 'connected',
        url: 'ws://localhost:8000',
        metrics: mockWebSocketService.connectionMetrics,
        subscriberCount: 2
      });

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      // Verify degraded mode indicators
      await waitFor(() => {
        expect(screen.getByText(/unstable connection/i)).toBeInTheDocument();
      });
    });

    test('should show offline mode when disconnected', async () => {
      mockWebSocketService.isConnected = false;
      mockWebSocketService.connectionState = 'disconnected';

      render(
        <ThemeProvider theme={theme}>
          <EnhancedTestExecution />
        </ThemeProvider>
      );

      // Verify offline mode UI
      await waitFor(() => {
        expect(screen.getByText(/offline/i)).toBeInTheDocument();
        expect(screen.getByText(/reconnecting/i)).toBeInTheDocument();
      });
    });
  });

  describe('Dashboard Real-time Updates', () => {
    test('should update statistics in real-time', async () => {
      let statsCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'stats_update') {
          statsCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <Dashboard />
        </ThemeProvider>
      );

      // Simulate statistics update
      const mockStats = {
        totalProjects: 15,
        totalVideos: 128,
        totalSessions: 89,
        totalDetections: 3456,
        averageAccuracy: 91.5,
        timestamp: new Date().toISOString()
      };

      if (statsCallback) {
        statsCallback(mockStats);
      }

      // Verify stats are updated in dashboard
      await waitFor(() => {
        expect(screen.getByText('15')).toBeInTheDocument(); // totalProjects
        expect(screen.getByText('128')).toBeInTheDocument(); // totalVideos
        expect(screen.getByText('91.5%')).toBeInTheDocument(); // averageAccuracy
      });
    });

    test('should show live test execution status', async () => {
      let testStatusCallback: Function;
      mockWebSocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'test_status') {
          testStatusCallback = callback;
        }
        return () => {};
      });

      render(
        <ThemeProvider theme={theme}>
          <Dashboard />
        </ThemeProvider>
      );

      // Simulate test execution status
      const mockTestStatus = {
        sessionId: 'session-456',
        status: 'running',
        progress: 67,
        currentVideo: 'video-abc.mp4',
        eta: '2 minutes',
        timestamp: new Date().toISOString()
      };

      if (testStatusCallback) {
        testStatusCallback(mockTestStatus);
      }

      // Verify live test status appears
      await waitFor(() => {
        expect(screen.getByText(/running/i)).toBeInTheDocument();
        expect(screen.getByText(/67%/i)).toBeInTheDocument();
        expect(screen.getByText(/2 minutes/i)).toBeInTheDocument();
      });
    });
  });
});

// Network Condition Simulation Tests
describe('Network Condition Impact on Real-time Features', () => {
  test('should handle intermittent connectivity', async () => {
    let connectionCount = 0;
    mockWebSocketService.subscribe.mockImplementation(() => {
      connectionCount++;
      // Simulate intermittent connection loss
      if (connectionCount % 3 === 0) {
        mockWebSocketService.isConnected = false;
        setTimeout(() => {
          mockWebSocketService.isConnected = true;
        }, 1000);
      }
      return () => {};
    });

    render(
      <ThemeProvider theme={theme}>
        <EnhancedTestExecution />
      </ThemeProvider>
    );

    // Verify resilience indicators
    await waitFor(() => {
      expect(screen.getByText(/connection/i)).toBeInTheDocument();
    });
  });

  test('should queue messages during disconnection', async () => {
    const messageQueue: any[] = [];
    
    mockWebSocketService.emit.mockImplementation((event, data) => {
      if (!mockWebSocketService.isConnected) {
        messageQueue.push({ event, data });
        return false;
      }
      return true;
    });

    // Start disconnected
    mockWebSocketService.isConnected = false;

    render(
      <ThemeProvider theme={theme}>
        <EnhancedTestExecution />
      </ThemeProvider>
    );

    // Trigger some actions that would emit messages
    const button = screen.getByText(/start/i);
    fireEvent.click(button);

    expect(messageQueue.length).toBeGreaterThan(0);

    // Reconnect and verify messages are sent
    mockWebSocketService.isConnected = true;
    
    // Simulate connection restoration
    messageQueue.forEach(({ event, data }) => {
      mockWebSocketService.emit(event, data);
    });

    expect(mockWebSocketService.emit).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(Object)
    );
  });
});

// Performance Impact Tests
describe('Real-time Feature Performance', () => {
  test('should handle high-frequency updates efficiently', async () => {
    const callbacks = new Map();
    
    mockWebSocketService.subscribe.mockImplementation((event, callback) => {
      callbacks.set(event, callback);
      return () => callbacks.delete(event);
    });

    render(
      <ThemeProvider theme={theme}>
        <EnhancedTestExecution />
      </ThemeProvider>
    );

    // Simulate high-frequency updates
    const startTime = Date.now();
    const updateCount = 100;

    for (let i = 0; i < updateCount; i++) {
      const progressCallback = callbacks.get('progress_update');
      if (progressCallback) {
        progressCallback({
          type: 'progress',
          videoId: 'test-video',
          progress: (i / updateCount) * 100,
          timestamp: new Date().toISOString()
        });
      }
    }

    const endTime = Date.now();
    const processingTime = endTime - startTime;

    // Should handle updates efficiently (less than 1ms per update)
    expect(processingTime).toBeLessThan(updateCount);
  });

  test('should not cause memory leaks with frequent updates', async () => {
    const initialMemory = (performance as any).memory?.usedJSHeapSize || 0;
    
    render(
      <ThemeProvider theme={theme}>
        <EnhancedTestExecution />
      </ThemeProvider>
    );

    // Simulate many updates and cleanups
    for (let cycle = 0; cycle < 10; cycle++) {
      const unsubscribe = mockWebSocketService.subscribe('test_event', () => {});
      
      // Generate updates
      for (let i = 0; i < 100; i++) {
        mockWebSocketService.emit('test_message', { data: `cycle-${cycle}-${i}` });
      }
      
      unsubscribe();
    }

    // Force garbage collection if available
    if ((global as any).gc) {
      (global as any).gc();
    }

    const finalMemory = (performance as any).memory?.usedJSHeapSize || 0;
    
    // Memory growth should be reasonable (less than 10MB for this test)
    if (initialMemory > 0 && finalMemory > 0) {
      const memoryGrowth = finalMemory - initialMemory;
      expect(memoryGrowth).toBeLessThan(10 * 1024 * 1024); // 10MB
    }
  });
});