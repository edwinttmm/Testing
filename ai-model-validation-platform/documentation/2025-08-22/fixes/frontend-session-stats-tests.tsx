/**
 * Frontend Component Tests for Session Stats
 * Tests for real-time updates and data display components
 */

import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { jest } from '@jest/globals';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { BrowserRouter } from 'react-router-dom';

// Mock modules before imports
jest.mock('../../../src/services/websocketService', () => ({
  __esModule: true,
  default: {
    connect: jest.fn(),
    disconnect: jest.fn(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    emit: jest.fn(),
  },
}));

jest.mock('../../../src/services/api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

// Import components after mocking
import Dashboard from '../../../src/pages/Dashboard';
import TestExecution from '../../../src/pages/TestExecution';
import websocketService from '../../../src/services/websocketService';
import apiService from '../../../src/services/api';

const theme = createTheme();

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('Session Stats Components', () => {
  let mockWebsocketService: jest.Mocked<typeof websocketService>;
  let mockApiService: jest.Mocked<typeof apiService>;

  beforeEach(() => {
    mockWebsocketService = websocketService as jest.Mocked<typeof websocketService>;
    mockApiService = apiService as jest.Mocked<typeof apiService>;
    
    // Reset all mocks
    jest.clearAllMocks();
    
    // Default mock implementations
    mockWebsocketService.connect.mockResolvedValue(undefined);
    mockWebsocketService.disconnect.mockResolvedValue(undefined);
    mockWebsocketService.subscribe.mockReturnValue(() => {});
    mockWebsocketService.unsubscribe.mockReturnValue(undefined);
    
    mockApiService.get.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Dashboard Session Stats', () => {
    const mockDashboardStats = {
      totalProjects: 5,
      activeProjects: 3,
      totalVideos: 25,
      processedVideos: 20,
      totalDetections: 1250,
      avgConfidence: 0.847,
      processingStatus: {
        completed: 20,
        processing: 3,
        pending: 2,
        failed: 0
      },
      recentActivity: [
        {
          id: '1',
          type: 'detection_completed',
          projectName: 'Highway Monitoring',
          timestamp: new Date().toISOString(),
          details: 'Processed 45 detections'
        }
      ]
    };

    beforeEach(() => {
      mockApiService.get.mockImplementation((url) => {
        if (url.includes('/dashboard/stats')) {
          return Promise.resolve({ data: mockDashboardStats });
        }
        return Promise.resolve({ data: {} });
      });
    });

    test('renders dashboard stats correctly', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument(); // Total projects
        expect(screen.getByText('3')).toBeInTheDocument(); // Active projects
        expect(screen.getByText('25')).toBeInTheDocument(); // Total videos
        expect(screen.getByText('1,250')).toBeInTheDocument(); // Total detections
      });
    });

    test('updates stats in real-time via websocket', async () => {
      let websocketCallback: (data: any) => void;
      
      mockWebsocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'stats_update') {
          websocketCallback = callback;
        }
        return () => {};
      });

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument();
      });

      // Simulate websocket update
      act(() => {
        websocketCallback!({
          totalProjects: 6,
          activeProjects: 4,
          totalVideos: 30,
          totalDetections: 1500
        });
      });

      await waitFor(() => {
        expect(screen.getByText('6')).toBeInTheDocument(); // Updated total projects
        expect(screen.getByText('4')).toBeInTheDocument(); // Updated active projects
        expect(screen.getByText('30')).toBeInTheDocument(); // Updated total videos
        expect(screen.getByText('1,500')).toBeInTheDocument(); // Updated total detections
      });
    });

    test('handles websocket connection errors gracefully', async () => {
      mockWebsocketService.connect.mockRejectedValue(new Error('Connection failed'));

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        // Should still show initial data from API
        expect(screen.getByText('5')).toBeInTheDocument();
      });

      // Should display connection error indicator
      expect(screen.getByText(/connection/i)).toBeInTheDocument();
    });

    test('displays processing status breakdown', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Completed: 20')).toBeInTheDocument();
        expect(screen.getByText('Processing: 3')).toBeInTheDocument();
        expect(screen.getByText('Pending: 2')).toBeInTheDocument();
        expect(screen.getByText('Failed: 0')).toBeInTheDocument();
      });
    });

    test('shows recent activity feed', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
        expect(screen.getByText('Processed 45 detections')).toBeInTheDocument();
      });
    });

    test('refreshes stats on manual refresh button click', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith('/api/dashboard/stats');
      });
    });
  });

  describe('Test Execution Session Stats', () => {
    const mockTestSession = {
      id: 'session-123',
      name: 'Highway Detection Test',
      status: 'running',
      startedAt: new Date().toISOString(),
      progress: 0.65,
      stats: {
        framesProcessed: 650,
        totalFrames: 1000,
        detectionsFound: 45,
        currentFps: 28.5,
        averageConfidence: 0.82,
        classDistribution: {
          person: 20,
          car: 15,
          bicycle: 8,
          motorcycle: 2
        }
      }
    };

    beforeEach(() => {
      mockApiService.get.mockImplementation((url) => {
        if (url.includes('/test-sessions/')) {
          return Promise.resolve({ data: mockTestSession });
        }
        if (url.includes('/detection/status/')) {
          return Promise.resolve({ data: mockTestSession.stats });
        }
        return Promise.resolve({ data: {} });
      });
    });

    test('displays test session progress correctly', async () => {
      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Highway Detection Test')).toBeInTheDocument();
        expect(screen.getByText('Running')).toBeInTheDocument();
        expect(screen.getByText('65%')).toBeInTheDocument(); // Progress
        expect(screen.getByText('650 / 1,000')).toBeInTheDocument(); // Frames
      });
    });

    test('updates detection stats in real-time', async () => {
      let detectionUpdateCallback: (data: any) => void;
      
      mockWebsocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'detection_update') {
          detectionUpdateCallback = callback;
        }
        return () => {};
      });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('45')).toBeInTheDocument(); // Initial detections
      });

      // Simulate real-time detection update
      act(() => {
        detectionUpdateCallback!({
          sessionId: 'session-123',
          framesProcessed: 700,
          detectionsFound: 52,
          currentFps: 29.2,
          newDetections: [
            {
              classLabel: 'person',
              confidence: 0.89,
              timestamp: 23.5
            }
          ]
        });
      });

      await waitFor(() => {
        expect(screen.getByText('52')).toBeInTheDocument(); // Updated detections
        expect(screen.getByText('700')).toBeInTheDocument(); // Updated frames
        expect(screen.getByText('29.2 FPS')).toBeInTheDocument(); // Updated FPS
      });
    });

    test('displays class distribution chart', async () => {
      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Person: 20')).toBeInTheDocument();
        expect(screen.getByText('Car: 15')).toBeInTheDocument();
        expect(screen.getByText('Bicycle: 8')).toBeInTheDocument();
        expect(screen.getByText('Motorcycle: 2')).toBeInTheDocument();
      });
    });

    test('shows performance metrics', async () => {
      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('28.5 FPS')).toBeInTheDocument();
        expect(screen.getByText('82%')).toBeInTheDocument(); // Average confidence
      });
    });

    test('handles session completion', async () => {
      let sessionCompleteCallback: (data: any) => void;
      
      mockWebsocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'session_complete') {
          sessionCompleteCallback = callback;
        }
        return () => {};
      });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Running')).toBeInTheDocument();
      });

      // Simulate session completion
      act(() => {
        sessionCompleteCallback!({
          sessionId: 'session-123',
          status: 'completed',
          finalStats: {
            totalDetections: 67,
            processingTime: 120,
            averageAccuracy: 0.94
          }
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Completed')).toBeInTheDocument();
        expect(screen.getByText('67')).toBeInTheDocument(); // Final detection count
        expect(screen.getByText('2:00')).toBeInTheDocument(); // Processing time
      });
    });

    test('displays error states appropriately', async () => {
      mockApiService.get.mockRejectedValue(new Error('API Error'));

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/error loading/i)).toBeInTheDocument();
      });
    });
  });

  describe('Real-time Performance Monitoring', () => {
    test('monitors memory usage', async () => {
      const mockMemoryStats = {
        memoryUsage: 245.6, // MB
        gpuMemory: 512.3,
        cpuUsage: 67.8,
        diskSpace: 89.2
      };

      mockApiService.get.mockResolvedValue({ data: mockMemoryStats });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('245.6 MB')).toBeInTheDocument();
        expect(screen.getByText('512.3 MB')).toBeInTheDocument();
        expect(screen.getByText('67.8%')).toBeInTheDocument();
      });
    });

    test('shows performance warnings', async () => {
      let performanceWarningCallback: (data: any) => void;
      
      mockWebsocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'performance_warning') {
          performanceWarningCallback = callback;
        }
        return () => {};
      });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      // Simulate performance warning
      act(() => {
        performanceWarningCallback!({
          type: 'high_memory',
          message: 'Memory usage is above 80%',
          severity: 'warning',
          value: 85.2
        });
      });

      await waitFor(() => {
        expect(screen.getByText(/memory usage is above 80%/i)).toBeInTheDocument();
      });
    });

    test('tracks processing throughput', async () => {
      let throughputUpdateCallback: (data: any) => void;
      
      mockWebsocketService.subscribe.mockImplementation((event, callback) => {
        if (event === 'throughput_update') {
          throughputUpdateCallback = callback;
        }
        return () => {};
      });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      // Simulate throughput updates
      act(() => {
        throughputUpdateCallback!({
          currentThroughput: 28.5, // FPS
          averageThroughput: 26.8,
          peakThroughput: 31.2,
          processingEfficiency: 92.5
        });
      });

      await waitFor(() => {
        expect(screen.getByText('28.5 FPS')).toBeInTheDocument();
        expect(screen.getByText('26.8 FPS')).toBeInTheDocument();
        expect(screen.getByText('31.2 FPS')).toBeInTheDocument();
      });
    });
  });

  describe('Historical Data Visualization', () => {
    test('renders detection timeline chart', async () => {
      const mockTimelineData = [
        { timestamp: '2024-01-01T10:00:00Z', detections: 5, confidence: 0.8 },
        { timestamp: '2024-01-01T10:01:00Z', detections: 3, confidence: 0.9 },
        { timestamp: '2024-01-01T10:02:00Z', detections: 7, confidence: 0.7 }
      ];

      mockApiService.get.mockResolvedValue({ data: mockTimelineData });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        // Check for chart container
        expect(screen.getByRole('img', { name: /detection timeline/i })).toBeInTheDocument();
      });
    });

    test('displays confidence distribution', async () => {
      const mockConfidenceData = {
        bins: [
          { range: '0.5-0.6', count: 12 },
          { range: '0.6-0.7', count: 23 },
          { range: '0.7-0.8', count: 35 },
          { range: '0.8-0.9', count: 28 },
          { range: '0.9-1.0', count: 15 }
        ]
      };

      mockApiService.get.mockResolvedValue({ data: mockConfidenceData });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('0.5-0.6: 12')).toBeInTheDocument();
        expect(screen.getByText('0.8-0.9: 28')).toBeInTheDocument();
      });
    });
  });

  describe('Export and Reporting', () => {
    test('exports session statistics', async () => {
      const mockBlob = new Blob(['csv data'], { type: 'text/csv' });
      global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
      global.URL.revokeObjectURL = jest.fn();

      mockApiService.get.mockResolvedValue({
        data: mockBlob,
        headers: { 'content-type': 'text/csv' }
      });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      const exportButton = screen.getByRole('button', { name: /export csv/i });
      fireEvent.click(exportButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith(
          expect.stringContaining('/export'),
          expect.objectContaining({
            params: { format: 'csv' }
          })
        );
      });
    });

    test('generates session report', async () => {
      const mockReport = {
        sessionId: 'session-123',
        summary: {
          totalDetections: 67,
          averageConfidence: 0.85,
          processingTime: 120,
          accuracy: 0.92
        },
        recommendations: [
          'Consider adjusting confidence threshold',
          'Optimize frame rate for better performance'
        ]
      };

      mockApiService.get.mockResolvedValue({ data: mockReport });

      render(
        <TestWrapper>
          <TestExecution />
        </TestWrapper>
      );

      const reportButton = screen.getByRole('button', { name: /generate report/i });
      fireEvent.click(reportButton);

      await waitFor(() => {
        expect(screen.getByText('67')).toBeInTheDocument(); // Total detections
        expect(screen.getByText('85%')).toBeInTheDocument(); // Average confidence
        expect(screen.getByText('Consider adjusting confidence threshold')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility and Usability', () => {
    test('supports keyboard navigation', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      
      // Test keyboard interaction
      refreshButton.focus();
      fireEvent.keyDown(refreshButton, { key: 'Enter', code: 'Enter' });

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalled();
      });
    });

    test('provides screen reader labels', async () => {
      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/total projects count/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/detection statistics/i)).toBeInTheDocument();
      });
    });

    test('displays loading states', async () => {
      // Delay API response
      mockApiService.get.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({ data: {} }), 100))
      );

      render(
        <TestWrapper>
          <Dashboard />
        </TestWrapper>
      );

      expect(screen.getByRole('progressbar')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });
    });
  });
});

export {};