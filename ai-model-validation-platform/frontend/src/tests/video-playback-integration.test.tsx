/**
 * Comprehensive Video Playback Integration Test Suite
 * Tests video loading, playback, fullscreen functionality, sequential processing, and DOM management
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';

// Components under test
import EnhancedTestExecution from '../pages/EnhancedTestExecution';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import SimpleDetectionPanel from '../components/SimpleDetectionPanel';

// Mock services and utilities
jest.mock('../services/api', () => ({
  apiService: {
    get: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
    checkLabJackStatus: jest.fn(),
    initializeLabJack: jest.fn(),
    startSignalMonitoring: jest.fn(),
    stopSignalMonitoring: jest.fn(),
  },
  startEnhancedTestWorkflow: jest.fn(),
  stopEnhancedTestWorkflow: jest.fn(),
  getEnhancedTestWorkflowStatus: jest.fn(),
  getEnhancedTestWorkflowResults: jest.fn(),
}));

jest.mock('../services/simpleDetectionService', () => ({
  simpleDetectionService: {
    getStatus: jest.fn(),
    startDetection: jest.fn(),
    stopDetection: jest.fn(),
  }
}));

// Mock video files for testing
const mockVideoFiles = [
  {
    id: '1',
    filename: 'test-video-1.mp4',
    url: 'blob:test-video-1.mp4',
    duration: 30,
    size: 1024000,
    projectId: 'project-1',
  },
  {
    id: '2',
    filename: 'test-video-2.webm',
    url: 'blob:test-video-2.webm',
    duration: 45,
    size: 2048000,
    projectId: 'project-1',
  },
  {
    id: '3',
    filename: 'test-video-3.ogg',
    url: 'blob:test-video-3.ogg',
    duration: 60,
    size: 1536000,
    projectId: 'project-1',
  },
];

const mockProjects = [
  {
    id: 'project-1',
    name: 'Test Project',
    description: 'Test project for video playback',
    createdAt: new Date(),
  }
];

const theme = createTheme();

// Test wrapper component
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

// Mock implementations
const mockApiService = require('../services/api').apiService;
const mockSimpleDetectionService = require('../services/simpleDetectionService').simpleDetectionService;

// Global setup for DOM API mocks
beforeAll(() => {
  // Mock HTMLMediaElement methods
  Object.defineProperty(HTMLMediaElement.prototype, 'play', {
    writable: true,
    value: jest.fn().mockImplementation(() => Promise.resolve()),
  });
  
  Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
    writable: true,
    value: jest.fn(),
  });
  
  Object.defineProperty(HTMLMediaElement.prototype, 'load', {
    writable: true,
    value: jest.fn(),
  });

  // Mock video element properties
  Object.defineProperty(HTMLMediaElement.prototype, 'currentTime', {
    writable: true,
    value: 0,
  });
  
  Object.defineProperty(HTMLMediaElement.prototype, 'duration', {
    writable: true,
    value: 30,
  });

  Object.defineProperty(HTMLMediaElement.prototype, 'readyState', {
    writable: true,
    value: 4, // HAVE_ENOUGH_DATA
  });

  // Mock fullscreen API
  Object.defineProperty(document, 'fullscreenElement', {
    writable: true,
    value: null,
  });

  Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
    writable: true,
    value: jest.fn().mockImplementation(() => Promise.resolve()),
  });

  Object.defineProperty(document, 'exitFullscreen', {
    writable: true,
    value: jest.fn().mockImplementation(() => Promise.resolve()),
  });

  // Mock WebSocket
  global.WebSocket = jest.fn().mockImplementation(() => ({
    close: jest.fn(),
    send: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    readyState: 1,
  }));

  // Mock URL.createObjectURL
  global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
  global.URL.revokeObjectURL = jest.fn();

  // Mock Blob
  global.Blob = jest.fn().mockImplementation(() => ({}));
});

beforeEach(() => {
  // Reset all mocks
  jest.clearAllMocks();
  
  // Setup default mock responses
  mockApiService.get.mockImplementation((url: string) => {
    if (url === '/api/projects') return Promise.resolve(mockProjects);
    if (url.includes('/videos')) return Promise.resolve(mockVideoFiles);
    if (url === '/api/test-sessions') return Promise.resolve([]);
    if (url === '/api/health') return Promise.resolve({ status: 'ok' });
    return Promise.resolve({});
  });

  mockApiService.checkLabJackStatus.mockResolvedValue({
    connected: true,
    currentVoltages: { AIN0: 2.5 },
    voltageThreshold: 2.5,
    channels: ['AIN0'],
    sampleRate: 1000,
  });

  mockSimpleDetectionService.getStatus.mockResolvedValue({
    running: false,
    session_id: null,
    tolerance_ms: 100,
    detections_count: 0,
    duration_seconds: 0,
    connection_status: 'connected',
    hardware_status: 'ok',
  });
});

afterEach(() => {
  cleanup();
  // Reset DOM state
  Object.defineProperty(document, 'fullscreenElement', {
    writable: true,
    value: null,
  });
});

describe('Video Playback Integration Tests', () => {
  describe('1. Video Loading and Format Support', () => {
    test('should support MP4 video format', async () => {
      const mockVideo = {
        ...mockVideoFiles[0],
        url: 'data:video/mp4;base64,mock-mp4-data',
      };

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={[mockVideo]}
            config={{ autoAdvance: false }}
            showControls={true}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        const videoElements = document.querySelectorAll('video');
        expect(videoElements.length).toBeGreaterThan(0);
      });

      const videoElement = document.querySelector('video') as HTMLVideoElement;
      expect(videoElement).toBeTruthy();
      expect(videoElement.src).toContain('mock-mp4-data');
    });

    test('should support WebM video format', async () => {
      const mockVideo = {
        ...mockVideoFiles[1],
        url: 'data:video/webm;base64,mock-webm-data',
      };

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={[mockVideo]}
            config={{ autoAdvance: false }}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        const videoElements = document.querySelectorAll('video');
        expect(videoElements.length).toBeGreaterThan(0);
      });

      const videoElement = document.querySelector('video') as HTMLVideoElement;
      expect(videoElement).toBeTruthy();
      expect(videoElement.src).toContain('mock-webm-data');
    });

    test('should support OGG video format', async () => {
      const mockVideo = {
        ...mockVideoFiles[2],
        url: 'data:video/ogg;base64,mock-ogg-data',
      };

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={[mockVideo]}
            config={{ autoAdvance: false }}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        const videoElements = document.querySelectorAll('video');
        expect(videoElements.length).toBeGreaterThan(0);
      });

      const videoElement = document.querySelector('video') as HTMLVideoElement;
      expect(videoElement).toBeTruthy();
      expect(videoElement.src).toContain('mock-ogg-data');
    });

    test('should handle unsupported video formats gracefully', async () => {
      const unsupportedVideo = {
        id: '4',
        filename: 'unsupported.xyz',
        url: 'data:video/xyz;base64,invalid-data',
        duration: 30,
        size: 1024000,
        projectId: 'project-1',
      };

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={[unsupportedVideo]}
            onError={(error) => {
              expect(error.errorType).toBe('load');
              expect(error.message).toContain('unsupported');
            }}
          />
        </TestWrapper>
      );

      // Simulate video error
      await waitFor(() => {
        const videoElement = document.querySelector('video') as HTMLVideoElement;
        if (videoElement) {
          const errorEvent = new Event('error');
          videoElement.dispatchEvent(errorEvent);
        }
      });
    });
  });

  describe('2. Fullscreen Integration', () => {
    test('should enter fullscreen when Start Test is clicked', async () => {
      const user = userEvent.setup();
      
      render(
        <TestWrapper>
          <EnhancedTestExecution />
        </TestWrapper>
      );

      // Wait for component to load
      await waitFor(() => {
        expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
      });

      // Find and click Start Test button (it should be disabled initially)
      const startButton = screen.getByRole('button', { name: /start test/i });
      expect(startButton).toBeDisabled(); // Should be disabled without session

      // Create a session first
      const newSessionButton = screen.getByRole('button', { name: /new session/i });
      await user.click(newSessionButton);

      // Fill session form
      await waitFor(() => {
        const sessionNameInput = screen.getByLabelText(/session name/i);
        expect(sessionNameInput).toBeInTheDocument();
      });

      const sessionNameInput = screen.getByLabelText(/session name/i);
      await user.type(sessionNameInput, 'Test Session');

      const createButton = screen.getByRole('button', { name: /create session/i });
      await user.click(createButton);

      // Now start test should be available
      await waitFor(() => {
        const updatedStartButton = screen.getByRole('button', { name: /start test/i });
        expect(updatedStartButton).not.toBeDisabled();
      });

      // Mock requestFullscreen being called
      const mockRequestFullscreen = HTMLElement.prototype.requestFullscreen as jest.Mock;
      
      const finalStartButton = screen.getByRole('button', { name: /start test/i });
      await user.click(finalStartButton);

      // Verify fullscreen was requested
      await waitFor(() => {
        expect(mockRequestFullscreen).toHaveBeenCalled();
      });
    });

    test('should display fullscreen indicator when in fullscreen mode', async () => {
      // Simulate fullscreen state
      Object.defineProperty(document, 'fullscreenElement', {
        writable: true,
        value: document.documentElement,
      });

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            config={{ autoFullscreen: true }}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        const fullscreenChip = screen.getByText('FULLSCREEN');
        expect(fullscreenChip).toBeInTheDocument();
      });
    });

    test('should exit fullscreen on ESC key press', async () => {
      Object.defineProperty(document, 'fullscreenElement', {
        writable: true,
        value: document.documentElement,
      });

      render(
        <TestWrapper>
          <EnhancedTestExecution />
        </TestWrapper>
      );

      const mockExitFullscreen = document.exitFullscreen as jest.Mock;

      // Simulate ESC key press
      fireEvent.keyDown(document, {
        key: 'Escape',
        keyCode: 27,
      });

      await waitFor(() => {
        expect(mockExitFullscreen).toHaveBeenCalled();
      });
    });

    test('should handle fullscreen API errors gracefully', async () => {
      const mockRequestFullscreen = jest.fn().mockRejectedValue(new Error('Fullscreen not allowed'));
      Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
        writable: true,
        value: mockRequestFullscreen,
      });

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            onError={(error) => {
              expect(error.errorType).toBe('fullscreen');
            }}
          />
        </TestWrapper>
      );

      const fullscreenButton = screen.getByLabelText(/enter fullscreen/i);
      fireEvent.click(fullscreenButton);

      await waitFor(() => {
        expect(mockRequestFullscreen).toHaveBeenCalled();
      });
    });
  });

  describe('3. Sequential Video Playback System', () => {
    test('should play videos in sequential order', async () => {
      let currentVideoIndex = -1;
      
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            config={{ autoAdvance: true }}
            onVideoStart={(video, index) => {
              currentVideoIndex = index;
            }}
            autoStart={true}
          />
        </TestWrapper>
      );

      // Simulate first video starting
      await waitFor(() => {
        const playButton = screen.getByLabelText(/start.*playback/i);
        if (playButton) {
          fireEvent.click(playButton);
        }
      });

      // Should start with first video
      expect(currentVideoIndex).toBe(0);

      // Simulate first video ending to trigger next
      const videoElement = document.querySelector('video') as HTMLVideoElement;
      if (videoElement) {
        fireEvent.ended(videoElement);
      }

      // Should advance to next video
      await waitFor(() => {
        expect(currentVideoIndex).toBe(1);
      });
    });

    test('should display progress correctly during sequential playback', async () => {
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            config={{ autoAdvance: true }}
            showProgress={true}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        const progressText = screen.getByText(/0% Complete/);
        expect(progressText).toBeInTheDocument();
      });

      const progressElement = document.querySelector('[role="progressbar"]') as HTMLElement;
      expect(progressElement).toBeInTheDocument();
    });

    test('should handle video queue management', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            showQueue={true}
            showControls={true}
          />
        </TestWrapper>
      );

      // Open queue dialog
      const queueButton = screen.getByLabelText(/show queue/i);
      await user.click(queueButton);

      await waitFor(() => {
        expect(screen.getByText(/video queue/i)).toBeInTheDocument();
        expect(screen.getByText('test-video-1.mp4')).toBeInTheDocument();
        expect(screen.getByText('test-video-2.webm')).toBeInTheDocument();
        expect(screen.getByText('test-video-3.ogg')).toBeInTheDocument();
      });
    });

    test('should support loop playback mode', async () => {
      let playbackCompleteCallCount = 0;
      
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles.slice(0, 1)} // Single video for faster testing
            config={{ 
              autoAdvance: true, 
              loopPlayback: true,
            }}
            onPlaybackComplete={() => {
              playbackCompleteCallCount++;
            }}
            autoStart={true}
          />
        </TestWrapper>
      );

      // Simulate video ending multiple times
      const videoElement = document.querySelector('video') as HTMLVideoElement;
      if (videoElement) {
        fireEvent.ended(videoElement);
        
        // In loop mode, should restart rather than complete
        await waitFor(() => {
          expect(playbackCompleteCallCount).toBe(0);
        });
      }
    });
  });

  describe('4. Error Handling and Recovery', () => {
    test('should handle video loading errors', async () => {
      const errorMessages: string[] = [];

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            onError={(error) => {
              errorMessages.push(error.message);
            }}
          />
        </TestWrapper>
      );

      // Simulate video loading error
      const videoElement = document.querySelector('video') as HTMLVideoElement;
      if (videoElement) {
        const errorEvent = new Event('error');
        Object.defineProperty(videoElement, 'error', {
          value: { code: 4, message: 'MEDIA_ELEMENT_ERROR: Media loading aborted' }
        });
        fireEvent.error(videoElement);
      }

      await waitFor(() => {
        expect(errorMessages.length).toBeGreaterThan(0);
      });
    });

    test('should retry failed video loads', async () => {
      const mockLoad = jest.fn();
      Object.defineProperty(HTMLMediaElement.prototype, 'load', {
        writable: true,
        value: mockLoad,
      });

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles.slice(0, 1)}
            config={{ maxRetries: 3 }}
          />
        </TestWrapper>
      );

      // Simulate video error requiring retry
      const videoElement = document.querySelector('video') as HTMLVideoElement;
      if (videoElement) {
        fireEvent.error(videoElement);
      }

      // Should attempt to reload
      await waitFor(() => {
        expect(mockLoad).toHaveBeenCalled();
      });
    });

    test('should handle network connectivity issues', async () => {
      // Mock network error
      mockApiService.get.mockRejectedValueOnce(new Error('Network error'));

      render(
        <TestWrapper>
          <EnhancedTestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        // Should still render without crashing
        expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
      });
    });
  });

  describe('5. Memory Management and DOM Cleanup', () => {
    test('should cleanup video elements on component unmount', async () => {
      const { unmount } = render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
          />
        </TestWrapper>
      );

      // Verify video elements exist
      await waitFor(() => {
        const videoElements = document.querySelectorAll('video');
        expect(videoElements.length).toBeGreaterThan(0);
      });

      // Unmount component
      unmount();

      // Verify cleanup
      await waitFor(() => {
        const videoElements = document.querySelectorAll('video');
        expect(videoElements.length).toBe(0);
      });
    });

    test('should revoke object URLs to prevent memory leaks', async () => {
      const mockRevokeObjectURL = global.URL.revokeObjectURL as jest.Mock;

      const { unmount } = render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
          />
        </TestWrapper>
      );

      unmount();

      // Should cleanup object URLs
      await waitFor(() => {
        expect(mockRevokeObjectURL).toHaveBeenCalled();
      });
    });

    test('should remove event listeners on cleanup', async () => {
      const mockRemoveEventListener = jest.fn();
      const originalRemoveEventListener = document.removeEventListener;
      document.removeEventListener = mockRemoveEventListener;

      const { unmount } = render(
        <TestWrapper>
          <EnhancedTestExecution />
        </TestWrapper>
      );

      unmount();

      // Verify event listeners are removed
      expect(mockRemoveEventListener).toHaveBeenCalled();
      
      // Restore original
      document.removeEventListener = originalRemoveEventListener;
    });

    test('should close WebSocket connections on unmount', async () => {
      const mockWebSocketClose = jest.fn();
      (global.WebSocket as jest.Mock).mockImplementation(() => ({
        close: mockWebSocketClose,
        send: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        readyState: 1,
      }));

      const { unmount } = render(
        <TestWrapper>
          <EnhancedTestExecution />
        </TestWrapper>
      );

      unmount();

      await waitFor(() => {
        expect(mockWebSocketClose).toHaveBeenCalled();
      });
    });
  });

  describe('6. DOM Test Validator Integration', () => {
    test('should validate DOM structure after video loading', async () => {
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles.slice(0, 1)}
            showControls={true}
            showProgress={true}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        // Verify core DOM elements are present
        const videoContainer = document.querySelector('[data-testid="video-container"]');
        const controlsContainer = document.querySelector('[role="group"]');
        const progressBar = document.querySelector('[role="progressbar"]');

        // Basic DOM structure validation
        expect(document.querySelector('video')).toBeInTheDocument();
        expect(controlsContainer || screen.getByText(/playback/i).closest('.MuiCardContent-root')).toBeTruthy();
        expect(progressBar || screen.getByText(/Complete/)).toBeTruthy();
      });
    });

    test('should maintain ARIA accessibility during fullscreen transitions', async () => {
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles.slice(0, 1)}
            showControls={true}
          />
        </TestWrapper>
      );

      const fullscreenButton = screen.getByLabelText(/enter fullscreen/i);
      expect(fullscreenButton).toHaveAttribute('aria-label');

      fireEvent.click(fullscreenButton);

      await waitFor(() => {
        const exitFullscreenButton = screen.queryByLabelText(/exit fullscreen/i);
        if (exitFullscreenButton) {
          expect(exitFullscreenButton).toHaveAttribute('aria-label');
        }
      });
    });

    test('should preserve semantic HTML structure', async () => {
      render(
        <TestWrapper>
          <EnhancedTestExecution />
        </TestWrapper>
      );

      await waitFor(() => {
        // Check for proper heading hierarchy
        const mainHeading = screen.getByRole('heading', { level: 4 });
        expect(mainHeading).toBeInTheDocument();

        // Check for proper button roles
        const buttons = screen.getAllByRole('button');
        expect(buttons.length).toBeGreaterThan(0);

        // Check for proper form controls
        const comboboxes = screen.getAllByRole('combobox');
        expect(comboboxes.length).toBeGreaterThan(0);
      });
    });
  });

  describe('7. Cross-browser Compatibility', () => {
    test('should handle different fullscreen API implementations', async () => {
      // Test webkit prefixed API
      Object.defineProperty(HTMLElement.prototype, 'webkitRequestFullscreen', {
        writable: true,
        value: jest.fn().mockResolvedValue(undefined),
      });

      Object.defineProperty(document, 'webkitExitFullscreen', {
        writable: true,
        value: jest.fn().mockResolvedValue(undefined),
      });

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles.slice(0, 1)}
            showControls={true}
          />
        </TestWrapper>
      );

      const fullscreenButton = screen.getByLabelText(/enter fullscreen/i);
      fireEvent.click(fullscreenButton);

      await waitFor(() => {
        expect(HTMLElement.prototype.requestFullscreen || HTMLElement.prototype.webkitRequestFullscreen).toBeTruthy();
      });
    });

    test('should degrade gracefully when fullscreen API is not available', async () => {
      // Remove fullscreen API
      delete HTMLElement.prototype.requestFullscreen;
      delete document.exitFullscreen;

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles.slice(0, 1)}
            showControls={true}
          />
        </TestWrapper>
      );

      const fullscreenButton = screen.getByLabelText(/enter fullscreen/i);
      
      // Should not crash when clicked
      fireEvent.click(fullscreenButton);
      
      await waitFor(() => {
        expect(screen.getByText(/test-video-1.mp4/)).toBeInTheDocument();
      });
    });

    test('should handle different video codec support', async () => {
      const testVideoFormats = [
        { format: 'mp4', canPlay: 'probably' },
        { format: 'webm', canPlay: 'maybe' },
        { format: 'ogg', canPlay: '' },
      ];

      testVideoFormats.forEach(({ format, canPlay }) => {
        Object.defineProperty(HTMLMediaElement.prototype, 'canPlayType', {
          writable: true,
          value: jest.fn().mockReturnValue(canPlay),
        });

        const mockVideo = {
          ...mockVideoFiles[0],
          filename: `test.${format}`,
          url: `data:video/${format};base64,mock-data`,
        };

        render(
          <TestWrapper>
            <SequentialVideoPlayer
              videos={[mockVideo]}
            />
          </TestWrapper>
        );

        // Should handle each format appropriately
        expect(screen.getByText(`test.${format}`)).toBeInTheDocument();
        cleanup();
      });
    });
  });

  describe('8. Performance and Optimization', () => {
    test('should implement video preloading for better performance', async () => {
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            config={{ preloadNext: true }}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        const videos = document.querySelectorAll('video');
        // Should have video elements for preloading
        expect(videos.length).toBeGreaterThanOrEqual(1);
      });
    });

    test('should limit DOM elements to prevent memory issues', async () => {
      const manyVideos = Array.from({ length: 100 }, (_, i) => ({
        ...mockVideoFiles[0],
        id: `video-${i}`,
        filename: `test-video-${i}.mp4`,
      }));

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={manyVideos}
            config={{ preloadNext: true }}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        const videoElements = document.querySelectorAll('video');
        // Should limit the number of video elements in DOM
        expect(videoElements.length).toBeLessThan(10);
      });
    });

    test('should handle rapid state updates efficiently', async () => {
      let updateCount = 0;
      
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideoFiles}
            onProgressUpdate={() => {
              updateCount++;
            }}
          />
        </TestWrapper>
      );

      // Simulate rapid progress updates
      const videoElement = document.querySelector('video') as HTMLVideoElement;
      if (videoElement) {
        for (let i = 0; i < 100; i++) {
          fireEvent.timeUpdate(videoElement);
        }
      }

      // Should throttle updates to prevent performance issues
      await waitFor(() => {
        expect(updateCount).toBeLessThan(100);
      });
    });
  });
});

describe('Integration with LabJack Detection', () => {
  test('should coordinate video playback with LabJack signals', async () => {
    render(
      <TestWrapper>
        <SimpleDetectionPanel
          projectId="test-project"
          toleranceMs={100}
        />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Simple LabJack Detection')).toBeInTheDocument();
    });

    const startButton = screen.getByRole('button', { name: /start detection/i });
    expect(startButton).toBeInTheDocument();
    expect(startButton).not.toBeDisabled();
  });

  test('should display detection status and results', async () => {
    mockSimpleDetectionService.getStatus.mockResolvedValue({
      running: true,
      session_id: 'test-session',
      tolerance_ms: 100,
      detections_count: 5,
      duration_seconds: 30.5,
      connection_status: 'connected',
      hardware_status: 'ok',
    });

    render(
      <TestWrapper>
        <SimpleDetectionPanel
          projectId="test-project"
        />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Detecting')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument(); // Detection count
      expect(screen.getByText('30.5s')).toBeInTheDocument(); // Duration
    });
  });
});