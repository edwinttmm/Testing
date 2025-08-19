import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Dashboard from '../../pages/Dashboard';

// Mock the WebSocket service
const mockSubscribe = jest.fn();
const mockEmit = jest.fn();
const mockUseWebSocket = {
  isConnected: true,
  connectionState: 'connected',
  subscribe: mockSubscribe,
  emit: mockEmit,
  error: null
};

jest.mock('../../services/websocketService', () => ({
  useWebSocket: () => mockUseWebSocket
}));

// Mock API services
jest.mock('../../services/api', () => ({
  getDashboardStats: jest.fn().mockResolvedValue({
    project_count: 5,
    video_count: 12,
    test_session_count: 8,
    detection_event_count: 156,
    confidence_intervals: {
      precision: [85, 95],
      recall: [80, 90],
      f1_score: [82, 92]
    },
    trend_analysis: {
      accuracy: 'improving',
      detectionRate: 'stable',
      performance: 'improving'
    },
    signal_processing_metrics: {
      totalSignals: 1250,
      successRate: 87.5,
      avgProcessingTime: 125
    },
    average_accuracy: 89.2,
    active_tests: 3,
    total_detections: 2340
  })
}));

jest.mock('../../services/enhancedApiService', () => ({
  getTestSessions: jest.fn().mockResolvedValue([
    {
      id: '1',
      name: 'Test Session 1',
      createdAt: new Date().toISOString(),
      metrics: { accuracy: 92.5 }
    },
    {
      id: '2',
      name: 'Test Session 2',
      createdAt: new Date(Date.now() - 3600000).toISOString(),
      metrics: { accuracy: 88.1 }
    }
  ])
}));

const theme = createTheme();

describe('Dashboard Real-time Updates', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSubscribe.mockImplementation((eventType: string, callback: Function) => {
      return () => {}; // Return unsubscribe function
    });
  });

  const renderDashboard = () => {
    return render(
      <ThemeProvider theme={theme}>
        <Dashboard />
      </ThemeProvider>
    );
  };

  test('renders dashboard with WebSocket connection status', async () => {
    renderDashboard();

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    // Check for live updates indicator (wait for it to appear after loading)
    await waitFor(() => {
      expect(screen.getByText('Live Updates')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('sets up WebSocket subscriptions on mount', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith('video_uploaded', expect.any(Function));
      expect(mockSubscribe).toHaveBeenCalledWith('project_created', expect.any(Function));
      expect(mockSubscribe).toHaveBeenCalledWith('test_completed', expect.any(Function));
      expect(mockSubscribe).toHaveBeenCalledWith('test_started', expect.any(Function));
      expect(mockSubscribe).toHaveBeenCalledWith('detection_event', expect.any(Function));
      expect(mockSubscribe).toHaveBeenCalledWith('signal_processed', expect.any(Function));
    });

    // Check that dashboard update subscription is requested
    expect(mockEmit).toHaveBeenCalledWith('subscribe_dashboard_updates', {
      clientId: 'dashboard',
      events: expect.arrayContaining([
        'video_uploaded', 'video_processed',
        'project_created', 'project_updated',
        'test_completed', 'test_session_completed'
      ])
    });
  });

  test('handles video upload events', async () => {
    let videoUploadCallback: Function;
    mockSubscribe.mockImplementation((eventType: string, callback: Function) => {
      if (eventType === 'video_uploaded') {
        videoUploadCallback = callback;
      }
      return () => {};
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Videos Processed')).toBeInTheDocument();
    });

    // Simulate video upload event
    act(() => {
      videoUploadCallback({
        id: 'video-123',
        filename: 'test-video.mp4',
        projectId: 'project-1'
      });
    });

    // Check for live updates indicator
    await waitFor(() => {
      expect(screen.getByText(/live updates/)).toBeInTheDocument();
    });
  });

  test('handles project creation events', async () => {
    let projectCreatedCallback: Function;
    mockSubscribe.mockImplementation((eventType: string, callback: Function) => {
      if (eventType === 'project_created') {
        projectCreatedCallback = callback;
      }
      return () => {};
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Active Projects')).toBeInTheDocument();
    });

    // Simulate project creation event
    act(() => {
      projectCreatedCallback({
        id: 'project-123',
        name: 'New Test Project',
        status: 'active'
      });
    });

    // Check for live updates counter
    await waitFor(() => {
      expect(screen.getByText(/live updates/)).toBeInTheDocument();
    });
  });

  test('handles test completion events', async () => {
    let testCompletedCallback: Function;
    mockSubscribe.mockImplementation((eventType: string, callback: Function) => {
      if (eventType === 'test_completed') {
        testCompletedCallback = callback;
      }
      return () => {};
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Tests Completed')).toBeInTheDocument();
    });

    // Simulate test completion event
    act(() => {
      testCompletedCallback({
        id: 'test-123',
        name: 'New Test Session',
        completedAt: new Date().toISOString(),
        metrics: { accuracy: 94.2 }
      });
    });

    // Check for updated session in recent sessions
    await waitFor(() => {
      expect(screen.getByText('New Test Session')).toBeInTheDocument();
    });
  });

  test('handles signal processing events', async () => {
    let signalProcessedCallback: Function;
    mockSubscribe.mockImplementation((eventType: string, callback: Function) => {
      if (eventType === 'signal_processed') {
        signalProcessedCallback = callback;
      }
      return () => {};
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Signal Processing')).toBeInTheDocument();
    });

    // Simulate signal processing event
    act(() => {
      signalProcessedCallback({
        success: true,
        processingTime: 150,
        signalType: 'CAN_BUS'
      });
    });

    // Check for live updates indicator
    await waitFor(() => {
      expect(screen.getByText(/live updates/)).toBeInTheDocument();
    });
  });

  test('shows connection status in system status panel', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/System Status.*LIVE/)).toBeInTheDocument();
      expect(screen.getByText(/WebSocket Connection ✅/)).toBeInTheDocument();
    });
  });

  test('handles disconnected state', async () => {
    // Mock disconnected state
    mockUseWebSocket.isConnected = false;
    mockUseWebSocket.connectionState = 'disconnected';

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Offline')).toBeInTheDocument();
      expect(screen.getByText(/System Status.*OFFLINE/)).toBeInTheDocument();
      expect(screen.getByText(/WebSocket Connection ❌/)).toBeInTheDocument();
    });
  });

  test('displays signal processing metrics with real-time status', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Signal Processing')).toBeInTheDocument();
    }, { timeout: 3000 });
    
    await waitFor(() => {
      expect(screen.getByText(/signals processed \(Live\)/)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('unsubscribes from events on unmount', async () => {
    const unsubscribeFunctions: jest.MockedFunction<any>[] = [];
    mockSubscribe.mockImplementation(() => {
      const unsubscribe = jest.fn();
      unsubscribeFunctions.push(unsubscribe);
      return unsubscribe;
    });

    const { unmount } = renderDashboard();

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalled();
    });

    // Unmount component
    unmount();

    // Check that unsubscribe functions were called
    unsubscribeFunctions.forEach(unsubscribe => {
      expect(unsubscribe).toHaveBeenCalled();
    });

    // Check that dashboard unsubscription was requested
    expect(mockEmit).toHaveBeenCalledWith('unsubscribe_dashboard_updates', {
      clientId: 'dashboard'
    });
  });
});