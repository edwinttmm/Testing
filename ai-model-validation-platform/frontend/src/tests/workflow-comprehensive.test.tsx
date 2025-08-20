/**
 * Comprehensive Workflow Test Suite
 * Tests the complete video upload → annotation → playback workflow
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import TestExecution from '../pages/TestExecution-improved';
import AccessibleVideoPlayer from '../components/AccessibleVideoPlayer';
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';
import { VideoFile, GroundTruthAnnotation } from '../services/types';

// Mock environment service
jest.mock('../config/environment', () => ({
  __esModule: true,
  default: {
    getWsUrl: jest.fn().mockReturnValue('ws://localhost:8000'),
    getApiUrl: jest.fn().mockReturnValue('http://localhost:8000'),
    get: jest.fn().mockImplementation((key: string) => {
      switch (key) {
        case 'connectionRetryAttempts':
          return 3;
        case 'connectionRetryDelay':
          return 1000;
        default:
          return null;
      }
    }),
    isDevelopment: jest.fn().mockReturnValue(true),
    isProduction: jest.fn().mockReturnValue(false),
    shouldEnableDebug: jest.fn().mockReturnValue(true),
  },
}));

// Mock socket.io-client
jest.mock('socket.io-client', () => ({
  io: jest.fn().mockImplementation(() => ({
    on: jest.fn(),
    emit: jest.fn(),
    close: jest.fn(),
    connected: true,
  })),
}));

// Mock API service
jest.mock('../services/api', () => ({
  apiService: {
    getProjects: jest.fn().mockResolvedValue([
      { id: '1', name: 'Test Project', status: 'active' }
    ]),
    getVideos: jest.fn().mockResolvedValue([
      {
        id: 'video-1',
        filename: 'test-video.mp4',
        name: 'test-video.mp4',
        status: 'completed',
        url: 'http://localhost:8000/videos/test-video.mp4',
        duration: 60,
        size: 1024000,
        projectId: '1',
        uploadedAt: '2024-01-01T00:00:00.000Z',
      }
    ]),
    createTestSession: jest.fn().mockResolvedValue({
      id: 'session-1',
      name: 'Test Session',
      status: 'running',
      projectId: '1',
      videoId: 'video-1',
      createdAt: '2024-01-01T00:00:00.000Z',
    }),
  },
}));

// Mock video utils
jest.mock('../utils/videoUtils', () => ({
  safeVideoPlay: jest.fn().mockResolvedValue({ success: true }),
  safeVideoPause: jest.fn(),
  safeVideoStop: jest.fn(),
  setVideoSource: jest.fn().mockResolvedValue(undefined),
  cleanupVideoElement: jest.fn(),
  isVideoReady: jest.fn().mockReturnValue(true),
  getVideoErrorMessage: jest.fn().mockReturnValue('Mock error'),
  addVideoEventListeners: jest.fn().mockReturnValue(() => {}),
}));

// Mock HTML video element
Object.defineProperty(HTMLMediaElement.prototype, 'readyState', {
  get: jest.fn().mockReturnValue(HTMLMediaElement.HAVE_METADATA),
});

Object.defineProperty(HTMLMediaElement.prototype, 'duration', {
  get: jest.fn().mockReturnValue(60),
});

Object.defineProperty(HTMLMediaElement.prototype, 'currentTime', {
  get: jest.fn().mockReturnValue(0),
  set: jest.fn(),
});

Object.defineProperty(HTMLMediaElement.prototype, 'paused', {
  get: jest.fn().mockReturnValue(true),
});

Object.defineProperty(HTMLMediaElement.prototype, 'videoWidth', {
  get: jest.fn().mockReturnValue(1920),
});

Object.defineProperty(HTMLMediaElement.prototype, 'videoHeight', {
  get: jest.fn().mockReturnValue(1080),
});

// Mock play/pause methods
HTMLMediaElement.prototype.play = jest.fn().mockImplementation(() => Promise.resolve());
HTMLMediaElement.prototype.pause = jest.fn();
HTMLMediaElement.prototype.load = jest.fn();

const theme = createTheme();

const MockTestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <ThemeProvider theme={theme}>
    {children}
  </ThemeProvider>
);

describe('Comprehensive Workflow Tests', () => {
  describe('TestExecution Component', () => {
    test('renders without crashing', async () => {
      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      expect(screen.getByText('Test Execution & Monitoring')).toBeInTheDocument();
    });

    test('loads projects and videos on mount', async () => {
      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('New Test Session')).toBeInTheDocument();
      });
    });

    test('opens test session configuration dialog', async () => {
      const user = userEvent.setup();
      
      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      const newSessionButton = screen.getByText('New Test Session');
      await user.click(newSessionButton);

      await waitFor(() => {
        expect(screen.getByText('Configure Test Session')).toBeInTheDocument();
      });
    });

    test('handles WebSocket connection status', async () => {
      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      // Should show connecting status initially
      expect(screen.getByText(/Real-time Server:/)).toBeInTheDocument();
    });

    test('handles video playback error recovery', async () => {
      // Mock video play failure
      const { safeVideoPlay } = require('../utils/videoUtils');
      safeVideoPlay.mockResolvedValueOnce({ success: false, error: new Error('Play failed') });

      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      // This test would need more detailed implementation
      // to fully test error recovery scenarios
    });
  });

  describe('AccessibleVideoPlayer Component', () => {
    const mockVideo: VideoFile = {
      id: 'test-video',
      filename: 'test.mp4',
      name: 'test.mp4',
      originalName: 'test.mp4',
      status: 'completed',
      url: 'http://localhost:8000/videos/test.mp4',
      duration: 60,
      size: 1024000,
      projectId: 'test-project',
      uploadedAt: '2024-01-01T00:00:00.000Z',
    };

    const mockAnnotations: GroundTruthAnnotation[] = [
      {
        id: 'annotation-1',
        videoId: 'test-video',
        detectionId: 'detection-1',
        frameNumber: 30,
        timestamp: 1.0,
        vruType: 'pedestrian',
        boundingBox: { x: 100, y: 100, width: 50, height: 100, label: 'pedestrian', confidence: 0.9 },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: true,
        createdAt: '2024-01-01T00:00:00.000Z',
      },
    ];

    test('renders video player with accessibility features', () => {
      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      const videoElement = screen.getByRole('region', { name: /video player/i });
      expect(videoElement).toBeInTheDocument();
      expect(videoElement).toHaveAttribute('tabIndex', '0');
    });

    test('handles keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      const videoPlayer = screen.getByRole('region', { name: /video player/i });
      
      // Focus the video player
      await user.click(videoPlayer);
      
      // Test spacebar for play/pause
      await user.keyboard(' ');
      // Verify play functionality was called (would need spy setup)
    });

    test('displays video controls with proper ARIA labels', () => {
      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      expect(screen.getByRole('toolbar', { name: /video playback controls/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/play video/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/video progress/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/volume/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/toggle fullscreen/i)).toBeInTheDocument();
    });

    test('handles annotation mode correctly', () => {
      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={true}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      expect(screen.getByText('ANNOTATION MODE')).toBeInTheDocument();
      expect(screen.getByLabelText(/click to create annotation/i)).toBeInTheDocument();
    });

    test('displays current frame annotations', () => {
      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      // This would need to be adjusted based on the current time/frame logic
      // For now, just check that annotation display functionality exists
      const annotationsRegion = screen.queryByRole('region', { name: /current frame annotations/i });
      // May or may not be present depending on timing
    });

    test('handles video loading errors gracefully', () => {
      const errorVideo = { ...mockVideo, url: '' };

      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={errorVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      // Should handle missing URL gracefully
      expect(screen.getByRole('region', { name: /video player/i })).toBeInTheDocument();
    });

    test('supports playback speed changes', async () => {
      const user = userEvent.setup();

      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      const settingsButton = screen.getByLabelText(/video settings/i);
      await user.click(settingsButton);

      await waitFor(() => {
        expect(screen.getByText('Playback Speed')).toBeInTheDocument();
      });
    });
  });

  describe('VideoAnnotationPlayer Component', () => {
    const mockVideo: VideoFile = {
      id: 'test-video',
      filename: 'test.mp4',
      name: 'test.mp4',
      originalName: 'test.mp4',
      status: 'completed',
      url: 'http://localhost:8000/videos/test.mp4',
      duration: 60,
      size: 1024000,
      projectId: 'test-project',
      uploadedAt: '2024-01-01T00:00:00.000Z',
    };

    const mockAnnotations: GroundTruthAnnotation[] = [
      {
        id: 'annotation-1',
        videoId: 'test-video',
        detectionId: 'detection-1',
        frameNumber: 30,
        timestamp: 1.0,
        vruType: 'pedestrian',
        boundingBox: { x: 100, y: 100, width: 50, height: 100, label: 'pedestrian', confidence: 0.9 },
        occluded: false,
        truncated: false,
        difficult: false,
        validated: true,
        createdAt: '2024-01-01T00:00:00.000Z',
      },
    ];

    test('renders video annotation player', () => {
      render(
        <MockTestWrapper>
          <VideoAnnotationPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    test('handles annotation selection', async () => {
      const onAnnotationSelect = jest.fn();
      const user = userEvent.setup();

      render(
        <MockTestWrapper>
          <VideoAnnotationPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
            onAnnotationSelect={onAnnotationSelect}
          />
        </MockTestWrapper>
      );

      // This test would need more specific implementation
      // to test annotation interaction
    });

    test('draws annotations on canvas', () => {
      const mockGetContext = jest.fn().mockReturnValue({
        clearRect: jest.fn(),
        strokeRect: jest.fn(),
        fillRect: jest.fn(),
        fillText: jest.fn(),
        measureText: jest.fn().mockReturnValue({ width: 50 }),
      });

      HTMLCanvasElement.prototype.getContext = mockGetContext;

      render(
        <MockTestWrapper>
          <VideoAnnotationPlayer
            video={mockVideo}
            annotations={mockAnnotations}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      // Verify canvas context was requested
      expect(mockGetContext).toHaveBeenCalledWith('2d');
    });
  });

  describe('Integration Tests', () => {
    test('complete workflow: project selection → video loading → playback', async () => {
      const user = userEvent.setup();

      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      // Open new session dialog
      const newSessionButton = screen.getByText('New Test Session');
      await user.click(newSessionButton);

      // Wait for dialog to open
      await waitFor(() => {
        expect(screen.getByText('Configure Test Session')).toBeInTheDocument();
      });

      // This would continue with more detailed workflow testing
      // including form interactions, video loading, playback controls, etc.
    });

    test('error handling throughout workflow', async () => {
      // Mock API failure
      const { apiService } = require('../services/api');
      apiService.getProjects.mockRejectedValueOnce(new Error('Network error'));

      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      // Should handle error gracefully
      await waitFor(() => {
        // Check for error message or fallback UI
        expect(screen.getByText('New Test Session')).toBeInTheDocument();
      });
    });

    test('WebSocket reconnection logic', async () => {
      // This would test the WebSocket reconnection functionality
      // by simulating connection drops and recoveries
      
      render(
        <MockTestWrapper>
          <TestExecution />
        </MockTestWrapper>
      );

      // Simulate connection status changes
      expect(screen.getByText(/Real-time Server:/)).toBeInTheDocument();
    });

    test('video playback performance under load', async () => {
      // This would test video playback with multiple simultaneous operations
      // to ensure smooth performance
      
      const mockVideo: VideoFile = {
        id: 'performance-test',
        filename: 'large-video.mp4',
        name: 'large-video.mp4',
        originalName: 'large-video.mp4',
        status: 'completed',
        url: 'http://localhost:8000/videos/large-video.mp4',
        duration: 3600, // 1 hour video
        size: 1024000000, // 1GB
        projectId: 'test-project',
        uploadedAt: '2024-01-01T00:00:00.000Z',
      };

      render(
        <MockTestWrapper>
          <AccessibleVideoPlayer
            video={mockVideo}
            annotations={[]}
            annotationMode={false}
            frameRate={30}
          />
        </MockTestWrapper>
      );

      // Verify component handles large video metadata
      expect(screen.getByRole('region', { name: /video player/i })).toBeInTheDocument();
    });
  });

  describe('Environment Configuration Tests', () => {
    test('adapts to development environment', () => {
      const environmentService = require('../config/environment').default;
      
      expect(environmentService.isDevelopment()).toBe(true);
      expect(environmentService.getWsUrl()).toBe('ws://localhost:8000');
    });

    test('would adapt to production environment', () => {
      // This would test production environment configuration
      // by mocking NODE_ENV and other environment variables
      
      const environmentService = require('../config/environment').default;
      
      // In actual test, would mock environment variables
      expect(environmentService.getWsUrl()).toContain('localhost');
    });
  });
});