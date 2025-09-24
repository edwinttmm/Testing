/**
 * HIL Ground Truth Loading Test
 * 
 * This test validates the comprehensive ground truth loading functionality
 * implemented to fix the "0 of 0 tests" issue in HIL test execution.
 * 
 * Test Coverage:
 * - Ground truth data loading with error handling
 * - Retry logic for failed API calls
 * - Fallback mechanisms 
 * - UI feedback and validation
 * - Child.mp4 specific testing
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { apiService } from '../services/api';
import HILTestExecutionPRD from '../pages/HILTestExecutionPRD';

// Mock dependencies
jest.mock('../services/api');
jest.mock('../utils/videoUtils', () => ({
  markUserInteraction: jest.fn()
}));

const mockApiService = apiService as jest.Mocked<typeof apiService>;

// Mock WebSocket hook
jest.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: true,
    emit: jest.fn(),
    subscribe: jest.fn()
  })
}));

// Mock navigation
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate
}));

describe('HIL Ground Truth Loading', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock successful LabJack status
    mockApiService.get.mockImplementation((url: string) => {
      if (url.includes('/api/labjack/status')) {
        return Promise.resolve({
          connected: true,
          status: 'connected',
          mode: 'auto',
          device_info: {
            device_type: 'LabJack T7',
            serial_number: 'TEST123'
          },
          signal_type: 'TTL',
          voltage_threshold: 2.5
        });
      }
      return Promise.resolve({});
    });
  });

  const setupMockProject = () => {
    const mockProject = {
      id: 'test-project-123',
      name: 'Test Project',
      status: 'active',
      videoCount: 1
    };

    const mockVideo = {
      id: 'child-video-456',
      filename: 'Child.mp4',
      status: 'validated',
      processing_status: 'completed',
      file_path: '/uploads/Child.mp4',
      fps: 30,
      duration: 30000
    };

    mockApiService.getProjects.mockResolvedValue([mockProject]);
    mockApiService.getAllVideos.mockResolvedValue({
      videos: [mockVideo]
    });

    return { mockProject, mockVideo };
  };

  const setupMockAnnotations = (videoId: string, annotationCount: number = 8) => {
    const mockAnnotations = Array.from({ length: annotationCount }, (_, index) => ({
      id: `annotation_${index + 1}`,
      timestamp: (index + 1) * 3000, // Every 3 seconds
      frame_number: (index + 1) * 90, // 30 FPS
      confidence: 0.9 + (index * 0.01),
      bbox: {
        x: 100 + (index * 10),
        y: 100 + (index * 10),
        width: 80,
        height: 60
      }
    }));

    mockApiService.getAnnotations.mockResolvedValue(mockAnnotations);
    return mockAnnotations;
  };

  test('should successfully load ground truth data for Child.mp4', async () => {
    const { mockProject, mockVideo } = setupMockProject();
    const mockAnnotations = setupMockAnnotations(mockVideo.id, 5);

    render(<HILTestExecutionPRD />);

    // Wait for component to load and select project
    await waitFor(() => {
      expect(screen.getByText('HIL Test Execution')).toBeInTheDocument();
    });

    // Select the test project
    const projectSelect = screen.getByLabelText('Select Project');
    await act(async () => {
      fireEvent.mouseDown(projectSelect);
    });
    
    const projectOption = screen.getByText('Test Project');
    await act(async () => {
      fireEvent.click(projectOption);
    });

    // Wait for ground truth loading
    await waitFor(() => {
      expect(screen.getByText(/5 Expected Detections Loaded/)).toBeInTheDocument();
    }, { timeout: 5000 });

    // Verify API calls were made correctly
    expect(mockApiService.getAnnotations).toHaveBeenCalledWith(mockVideo.id);
    expect(mockApiService.getAnnotations).toHaveBeenCalledTimes(1);

    // Verify ground truth status is displayed
    expect(screen.getByText('4. Ground Truth Status')).toBeInTheDocument();
    expect(screen.getByText(/Child\.mp4/)).toBeInTheDocument();
  });

  test('should handle ground truth loading failure with retry logic', async () => {
    const { mockProject, mockVideo } = setupMockProject();

    // Mock API failure then success
    let callCount = 0;
    mockApiService.getAnnotations.mockImplementation(() => {
      callCount++;
      if (callCount <= 2) {
        return Promise.reject(new Error('Network error'));
      }
      return Promise.resolve([
        {
          id: 'retry_annotation_1',
          timestamp: 5000,
          frame_number: 150,
          confidence: 0.95
        }
      ]);
    });

    render(<HILTestExecutionPRD />);

    // Select project to trigger ground truth loading
    await waitFor(() => {
      const projectSelect = screen.getByLabelText('Select Project');
      fireEvent.mouseDown(projectSelect);
    });
    
    const projectOption = screen.getByText('Test Project');
    fireEvent.click(projectOption);

    // Wait for retry logic to complete
    await waitFor(() => {
      expect(screen.getByText(/1 Expected Detections Loaded/)).toBeInTheDocument();
    }, { timeout: 10000 });

    // Verify retry attempts were made
    expect(mockApiService.getAnnotations).toHaveBeenCalledTimes(3);
  });

  test('should use fallback loading mechanisms when primary API fails', async () => {
    const { mockProject, mockVideo } = setupMockProject();

    // Mock primary API failure
    mockApiService.getAnnotations.mockRejectedValue(new Error('Primary API failed'));

    // Mock fallback ground truth endpoint
    mockApiService.get.mockImplementation((url: string) => {
      if (url.includes('/api/labjack/status')) {
        return Promise.resolve({
          connected: true,
          status: 'connected'
        });
      }
      if (url.includes(`/api/videos/${mockVideo.id}/ground-truth`)) {
        return Promise.resolve({
          annotations: [
            {
              id: 'fallback_1',
              timestamp: 2000,
              frame_number: 60,
              confidence: 0.8
            },
            {
              id: 'fallback_2', 
              timestamp: 6000,
              frame_number: 180,
              confidence: 0.85
            }
          ]
        });
      }
      return Promise.resolve({});
    });

    render(<HILTestExecutionPRD />);

    // Select project
    const projectSelect = screen.getByLabelText('Select Project');
    fireEvent.mouseDown(projectSelect);
    fireEvent.click(screen.getByText('Test Project'));

    // Wait for fallback loading
    await waitFor(() => {
      expect(screen.getByText(/2 Expected Detections Loaded/)).toBeInTheDocument();
    }, { timeout: 8000 });
  });

  test('should provide mock data for Child.mp4 when all loading methods fail', async () => {
    const { mockProject } = setupMockProject();
    
    // Mock video with Child.mp4 filename specifically
    const childVideo = {
      id: 'child-video-specific',
      filename: 'Child.mp4',
      status: 'validated',
      processing_status: 'completed',
      file_path: '/uploads/Child.mp4',
      fps: 30
    };

    mockApiService.getAllVideos.mockResolvedValue({
      videos: [childVideo]
    });

    // Mock all API failures
    mockApiService.getAnnotations.mockRejectedValue(new Error('All APIs failed'));
    mockApiService.get.mockImplementation((url: string) => {
      if (url.includes('/api/labjack/status')) {
        return Promise.resolve({ connected: true, status: 'connected' });
      }
      return Promise.reject(new Error('All endpoints failed'));
    });

    render(<HILTestExecutionPRD />);

    // Select project
    const projectSelect = screen.getByLabelText('Select Project');
    fireEvent.mouseDown(projectSelect);
    fireEvent.click(screen.getByText('Test Project'));

    // Wait for mock data fallback
    await waitFor(() => {
      expect(screen.getByText(/8 mock detections for testing/)).toBeInTheDocument();
    }, { timeout: 8000 });

    // Verify mock data message
    expect(screen.getByText(/Using.*mock detections for testing/)).toBeInTheDocument();
  });

  test('should validate test start conditions include ground truth data', async () => {
    const { mockProject, mockVideo } = setupMockProject();
    
    // Mock no annotations found
    mockApiService.getAnnotations.mockResolvedValue([]);

    render(<HILTestExecutionPRD />);

    // Select project (which will fail to load ground truth)
    const projectSelect = screen.getByLabelText('Select Project');
    fireEvent.mouseDown(projectSelect);
    fireEvent.click(screen.getByText('Test Project'));

    // Wait for ground truth loading attempt
    await waitFor(() => {
      expect(screen.getByText('No Ground Truth Data')).toBeInTheDocument();
    });

    // Verify start test button is disabled
    const startButton = screen.getByRole('button', { name: /Start HIL Test/i });
    expect(startButton).toBeDisabled();

    // Verify validation error message
    expect(screen.getByText(/No ground truth detections loaded/)).toBeInTheDocument();
  });

  test('should allow manual ground truth reload', async () => {
    const { mockProject, mockVideo } = setupMockProject();
    const mockAnnotations = setupMockAnnotations(mockVideo.id, 3);

    render(<HILTestExecutionPRD />);

    // Select project
    const projectSelect = screen.getByLabelText('Select Project');
    fireEvent.mouseDown(projectSelect);
    fireEvent.click(screen.getByText('Test Project'));

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText(/3 Expected Detections Loaded/)).toBeInTheDocument();
    });

    // Clear API mock and set new data
    jest.clearAllMocks();
    mockApiService.getAnnotations.mockResolvedValue([
      {
        id: 'reloaded_1',
        timestamp: 1000,
        frame_number: 30,
        confidence: 0.99
      }
    ]);

    // Click reload button
    const reloadButton = screen.getByRole('button', { name: /Reload Ground Truth/i });
    fireEvent.click(reloadButton);

    // Wait for reload
    await waitFor(() => {
      expect(screen.getByText(/1 Expected Detections Loaded/)).toBeInTheDocument();
    });

    expect(mockApiService.getAnnotations).toHaveBeenCalledTimes(1);
  });

  test('should display detailed ground truth information in UI', async () => {
    const { mockProject, mockVideo } = setupMockProject();
    setupMockAnnotations(mockVideo.id, 2);

    render(<HILTestExecutionPRD />);

    // Select project
    const projectSelect = screen.getByLabelText('Select Project');
    fireEvent.mouseDown(projectSelect);
    fireEvent.click(screen.getByText('Test Project'));

    await waitFor(() => {
      expect(screen.getByText(/2 Expected Detections Loaded/)).toBeInTheDocument();
    });

    // Verify detailed information is shown
    expect(screen.getByText('4. Ground Truth Status')).toBeInTheDocument();
    expect(screen.getByText(/Video: Child\.mp4/)).toBeInTheDocument();
    expect(screen.getByText(/Expected detection times:/)).toBeInTheDocument();
    expect(screen.getByText(/3\.0s, 6\.0s/)).toBeInTheDocument();
  });

  test('should prevent test start when ground truth loading fails completely', async () => {
    const { mockProject, mockVideo } = setupMockProject();

    // Mock complete failure (no fallbacks work)
    mockApiService.getAnnotations.mockRejectedValue(new Error('Complete failure'));
    mockApiService.get.mockImplementation((url: string) => {
      if (url.includes('/api/labjack/status')) {
        return Promise.resolve({ connected: true, status: 'connected' });
      }
      return Promise.reject(new Error('All endpoints failed'));
    });

    // Mock video that's NOT Child.mp4 (so no mock fallback)
    const regularVideo = {
      id: 'regular-video',
      filename: 'regular.mp4',
      status: 'validated',
      processing_status: 'completed'
    };

    mockApiService.getAllVideos.mockResolvedValue({
      videos: [regularVideo]
    });

    render(<HILTestExecutionPRD />);

    // Select project
    const projectSelect = screen.getByLabelText('Select Project');
    fireEvent.mouseDown(projectSelect);
    fireEvent.click(screen.getByText('Test Project'));

    await waitFor(() => {
      expect(screen.getByText('No Ground Truth Data')).toBeInTheDocument();
    });

    // Verify validation error appears
    expect(screen.getByText(/No ground truth detections loaded/)).toBeInTheDocument();
    
    // Verify start button is disabled
    const startButton = screen.getByRole('button', { name: /Start HIL Test/i });
    expect(startButton).toBeDisabled();
  });
});

export {};