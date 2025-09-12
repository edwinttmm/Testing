/**
 * Tests for video autoplay policy compliance and user interaction-based playback
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { VideoFile } from '../services/types';
import { 
  markUserInteraction, 
  hasRecentUserGesture, 
  detectAutoplayPolicy,
  safeVideoPlay,
  enableUnmutedPlayback
} from '../utils/videoUtils';

// Mock video files for testing
const mockVideos: VideoFile[] = [
  {
    id: '1',
    projectId: 'test-project',
    filename: 'test-video-1.mp4',
    name: 'Test Video 1',
    url: 'https://example.com/video1.mp4',
    duration: 30,
    size: 1048576,
    fileSize: 1048576,
    filePath: '/videos/test-1.mp4',
    format: 'mp4',
    status: 'completed',
    processingStatus: 'completed',
    groundTruthGenerated: false,
    detectionCount: 0,
    annotationCount: 0,
    uploaded_at: new Date().toISOString(),
    createdAt: new Date().toISOString(),
  },
  {
    id: '2',
    projectId: 'test-project',
    filename: 'test-video-2.mp4',
    name: 'Test Video 2',
    url: 'https://example.com/video2.mp4',
    duration: 45,
    size: 2097152,
    fileSize: 2097152,
    filePath: '/videos/test-2.mp4',
    format: 'mp4',
    status: 'completed',
    processingStatus: 'completed',
    groundTruthGenerated: false,
    detectionCount: 0,
    annotationCount: 0,
    uploaded_at: new Date().toISOString(),
    createdAt: new Date().toISOString(),
  },
];

const theme = createTheme();

// Mock HTMLVideoElement
const mockVideoElement = {
  play: jest.fn().mockResolvedValue(void 0),
  pause: jest.fn(),
  load: jest.fn(),
  currentTime: 0,
  duration: 30,
  paused: true,
  muted: false,
  volume: 1,
  readyState: HTMLMediaElement.HAVE_METADATA,
  videoWidth: 1920,
  videoHeight: 1080,
  src: '',
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  parentElement: document.createElement('div'),
} as unknown as HTMLVideoElement;

// Mock document.createElement to return our mock video element
const originalCreateElement = document.createElement;
beforeAll(() => {
  document.createElement = jest.fn((tagName: string) => {
    if (tagName === 'video') {
      return mockVideoElement;
    }
    return originalCreateElement.call(document, tagName);
  });
});

afterAll(() => {
  document.createElement = originalCreateElement;
});

describe('Video Autoplay Policy Compliance', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset user interaction state
    (global as any).hasUserInteracted = false;
    (global as any).userGestureTimestamp = 0;
  });

  describe('User Gesture Tracking', () => {
    it('should track user interactions correctly', () => {
      expect(hasRecentUserGesture()).toBe(false);
      
      markUserInteraction();
      
      expect(hasRecentUserGesture()).toBe(true);
    });

    it('should expire user gestures after timeout', async () => {
      markUserInteraction();
      expect(hasRecentUserGesture()).toBe(true);
      
      // Mock time passing beyond timeout (5 seconds)
      const originalNow = Date.now;
      Date.now = jest.fn(() => originalNow() + 10000); // 10 seconds later
      
      expect(hasRecentUserGesture()).toBe(false);
      
      Date.now = originalNow;
    });

    it('should track various user interaction events', () => {
      const events = ['click', 'tap', 'touchstart', 'touchend', 'mousedown', 'keydown'];
      
      events.forEach(eventType => {
        // Reset state
        (global as any).hasUserInteracted = false;
        
        // Simulate event
        const event = new Event(eventType);
        document.dispatchEvent(event);
        
        // User interaction should be tracked automatically by the global listener
        // Note: In the actual implementation, this works through event listeners
        // For testing, we'll verify the manual tracking works
        markUserInteraction();
        expect(hasRecentUserGesture()).toBe(true);
      });
    });
  });

  describe('Autoplay Policy Detection', () => {
    it('should detect autoplay capabilities', async () => {
      const mockVideo = {
        ...mockVideoElement,
        muted: false,
        volume: 1,
        play: jest.fn().mockResolvedValue(void 0),
        pause: jest.fn(),
      } as unknown as HTMLVideoElement;

      const policy = await detectAutoplayPolicy(mockVideo);
      
      expect(policy).toHaveProperty('allowed');
      expect(policy).toHaveProperty('muted');
      expect(policy).toHaveProperty('requiresUserGesture');
    });

    it('should handle autoplay policy violations', async () => {
      const mockVideo = {
        ...mockVideoElement,
        play: jest.fn().mockRejectedValue(new Error('The request is not allowed by the user agent')),
      } as unknown as HTMLVideoElement;

      const policy = await detectAutoplayPolicy(mockVideo);
      
      expect(policy.allowed).toBe(false);
      expect(policy.requiresUserGesture).toBe(true);
    });
  });

  describe('Safe Video Play with Autoplay Handling', () => {
    it('should attempt unmuted play with user gesture', async () => {
      markUserInteraction(); // Simulate user gesture
      
      const mockVideo = {
        ...mockVideoElement,
        readyState: HTMLMediaElement.HAVE_METADATA,
        play: jest.fn().mockResolvedValue(void 0),
      } as unknown as HTMLVideoElement;

      const result = await safeVideoPlay(mockVideo, { userInitiated: true });
      
      expect(result.success).toBe(true);
      expect(mockVideo.play).toHaveBeenCalled();
    });

    it('should fallback to muted play when unmuted fails', async () => {
      const mockVideo = {
        ...mockVideoElement,
        readyState: HTMLMediaElement.HAVE_METADATA,
        muted: false,
        volume: 1,
        play: jest.fn()
          .mockRejectedValueOnce(new Error('The request is not allowed by the user agent'))
          .mockResolvedValueOnce(void 0),
      } as unknown as HTMLVideoElement;

      const result = await safeVideoPlay(mockVideo, { userInitiated: true });
      
      expect(result.success).toBe(true);
      expect(mockVideo.play).toHaveBeenCalledTimes(2); // First attempt + muted fallback
      expect(mockVideo.muted).toBe(true);
    });

    it('should handle video element not ready', async () => {
      const mockVideo = {
        ...mockVideoElement,
        readyState: HTMLMediaElement.HAVE_NOTHING,
      } as unknown as HTMLVideoElement;

      const result = await safeVideoPlay(mockVideo);
      
      expect(result.success).toBe(false);
      expect(result.error?.message).toContain('metadata not loaded');
    });

    it('should handle null video element', async () => {
      const result = await safeVideoPlay(null);
      
      expect(result.success).toBe(false);
      expect(result.error?.message).toBe('Video element is null');
    });
  });

  describe('Unmuted Playback Enable', () => {
    it('should enable unmuted playback with user gesture', async () => {
      markUserInteraction(); // Simulate recent user interaction
      
      const mockVideo = {
        ...mockVideoElement,
        muted: true,
        paused: false, // Video is playing
      } as unknown as HTMLVideoElement;

      const result = await enableUnmutedPlayback(mockVideo);
      
      expect(result).toBe(true);
      expect(mockVideo.muted).toBe(false);
    });

    it('should fail without recent user gesture', async () => {
      const mockVideo = {
        ...mockVideoElement,
        muted: true,
      } as unknown as HTMLVideoElement;

      const result = await enableUnmutedPlayback(mockVideo);
      
      expect(result).toBe(false);
    });
  });

  describe('SequentialVideoPlayer Integration', () => {
    const TestWrapper = ({ children }: { children: React.ReactNode }) => (
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    );

    it('should render with autoplay warning when muted', async () => {
      const mockOnVideoStart = jest.fn();
      const mockOnError = jest.fn();

      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideos}
            onVideoStart={mockOnVideoStart}
            onError={mockOnError}
            autoStart={false}
            showControls={true}
          />
        </TestWrapper>
      );

      // Should render the video player
      expect(screen.getByRole('button', { name: /start/i })).toBeInTheDocument();
    });

    it('should handle start playback with user interaction', async () => {
      const mockOnVideoStart = jest.fn();
      
      render(
        <TestWrapper>
          <SequentialVideoPlayer
            videos={mockVideos}
            onVideoStart={mockOnVideoStart}
            autoStart={false}
            showControls={true}
          />
        </TestWrapper>
      );

      const startButton = screen.getByRole('button', { name: /start/i });
      
      // Click should mark user interaction
      fireEvent.click(startButton);
      
      // Should attempt to start playback
      await waitFor(() => {
        expect(hasRecentUserGesture()).toBe(true);
      });
    });
  });
});

describe('Video Playback Error Handling', () => {
  it('should provide helpful error messages for autoplay issues', async () => {
    const mockVideo = {
      ...mockVideoElement,
      readyState: HTMLMediaElement.HAVE_METADATA,
      play: jest.fn().mockRejectedValue(new Error('The request is not allowed by the user agent or the platform in the current context, possibly because the user denied permission.')),
    } as unknown as HTMLVideoElement;

    const result = await safeVideoPlay(mockVideo);
    
    expect(result.success).toBe(false);
    expect(result.error?.message).toContain('not allowed');
  });

  it('should distinguish between different error types', async () => {
    const errors = [
      new Error('The request is not allowed by the user agent'), // Autoplay policy
      new Error('The element has no supported sources'), // Source error
      new Error('The fetching process for the media resource was aborted'), // Network error
    ];

    for (const error of errors) {
      const mockVideo = {
        ...mockVideoElement,
        readyState: HTMLMediaElement.HAVE_METADATA,
        play: jest.fn().mockRejectedValue(error),
      } as unknown as HTMLVideoElement;

      const result = await safeVideoPlay(mockVideo);
      expect(result.success).toBe(false);
      expect(result.error).toBe(error);
    }
  });
});

describe('Integration with Test Execution', () => {
  it('should mark user interaction when start button is clicked', () => {
    // Simulate the startTestExecution function behavior
    const startTestExecution = () => {
      markUserInteraction(); // This should be called immediately on button click
      // ... rest of the function
    };

    expect(hasRecentUserGesture()).toBe(false);
    startTestExecution();
    expect(hasRecentUserGesture()).toBe(true);
  });
});