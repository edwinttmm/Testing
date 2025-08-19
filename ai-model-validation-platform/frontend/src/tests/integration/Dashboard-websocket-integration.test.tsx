import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Dashboard from '../../pages/Dashboard';

// Create a simple mock for WebSocket service that returns expected values
const mockWebSocketService = {
  isConnected: true,
  connectionState: 'connected',
  subscribe: jest.fn(() => () => {}), // Always return unsubscribe function
  emit: jest.fn(),
  error: null
};

jest.mock('../../services/websocketService', () => ({
  useWebSocket: () => mockWebSocketService
}));

// Mock API services to return consistent data
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
    }
  ])
}));

const theme = createTheme();

describe('Dashboard WebSocket Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('successfully integrates WebSocket with Dashboard component', async () => {
    render(
      <ThemeProvider theme={theme}>
        <Dashboard />
      </ThemeProvider>
    );

    // Wait for component to finish loading
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    // Verify WebSocket integration is working
    expect(mockWebSocketService.subscribe).toHaveBeenCalled();
    expect(mockWebSocketService.emit).toHaveBeenCalledWith(
      'subscribe_dashboard_updates',
      expect.objectContaining({
        clientId: 'dashboard'
      })
    );

    // Check that real-time components are present
    await waitFor(() => {
      expect(screen.getByText('Live Updates')).toBeInTheDocument();
    });
  });

  test('handles WebSocket disconnection gracefully', async () => {
    // Mock disconnected state
    mockWebSocketService.isConnected = false;
    mockWebSocketService.connectionState = 'disconnected';

    render(
      <ThemeProvider theme={theme}>
        <Dashboard />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    // Should show offline status
    await waitFor(() => {
      expect(screen.getByText('Offline')).toBeInTheDocument();
    });
  });
});