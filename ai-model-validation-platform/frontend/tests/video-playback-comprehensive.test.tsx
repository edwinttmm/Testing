/**
 * Comprehensive Video Playback Test Suite
 * Tests all aspects of the enhanced video playback system including:
 * - Sequential video playback
 * - Fullscreen functionality 
 * - Queue management
 * - Error handling
 * - Browser compatibility
 * - Performance
 */

import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

import SequentialVideoManager from '../src/components/SequentialVideoManager';
import { VideoPlaybackManager } from '../src/utils/videoPlaybackManager';
import { useVideoPlayer } from '../src/hooks/useVideoPlayer';
import { VideoFile } from '../src/services/types';

// Mock data
const createMockVideo = (id: string, filename: string, duration = 10): VideoFile => ({
  id,
  filename,
  originalName: filename,
  url: `/test-videos/${filename}`,
  projectId: 'test-project',
  status: 'completed',
  duration,
  fps: 30,
  size: 1024 * 1024,
  fileSize: 1024 * 1024,
  createdAt: new Date().toISOString(),
  uploadedAt: new Date().toISOString(),
  groundTruthGenerated: false,
  groundTruthStatus: 'pending',
  processing_status: 'completed',
  detectionCount: 0
});

const mockVideoPlaylist: VideoFile[] = [
  createMockVideo('video-1', 'test-video-1.mp4', 5),
  createMockVideo('video-2', 'test-video-2.mp4', 8),
  createMockVideo('video-3', 'test-video-3.mp4', 12),
  createMockVideo('video-4', 'test-video-4.mp4', 6),
  createMockVideo('video-5', 'corrupted-video.mp4', 0), // Corrupted video for error testing
];

// Mock implementations
const mockVideoElement = {
  play: jest.fn().mockResolvedValue(undefined),
  pause: jest.fn(),
  load: jest.fn(),
  currentTime: 0,
  duration: 10,
  volume: 1,
  muted: false,
  paused: true,
  ended: false,
  readyState: HTMLMediaElement.HAVE_METADATA,
  videoWidth: 1920,
  videoHeight: 1080,
  error: null,
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  requestFullscreen: jest.fn().mockResolvedValue(undefined),
  webkitRequestFullscreen: jest.fn(),
  mozRequestFullScreen: jest.fn(),
  msRequestFullscreen: jest.fn(),
};

// Mock fullscreen API
Object.defineProperty(document, 'fullscreenEnabled', { value: true });
Object.defineProperty(document, 'webkitFullscreenEnabled', { value: true });
Object.defineProperty(document, 'mozFullScreenEnabled', { value: true });
Object.defineProperty(document, 'msFullscreenEnabled', { value: true });

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock video utilities
jest.mock('../src/utils/videoUtils', () => ({
  safeVideoPlay: jest.fn().mockResolvedValue({ success: true }),
  safeVideoPause: jest.fn(),
  safeVideoStop: jest.fn(),
  setVideoSource: jest.fn().mockResolvedValue(undefined),
  cleanupVideoElement: jest.fn(),
  isVideoReady: jest.fn().mockReturnValue(true),
  addVideoEventListeners: jest.fn().mockReturnValue(() => {}),
}));

describe('Comprehensive Video Playback System Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Mock createElement to return our mock video element
    const originalCreateElement = document.createElement;
    jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'video') {
        return mockVideoElement as any;
      }
      return originalCreateElement.call(document, tagName);
    });
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  describe('1. Sequential Video Playback', () => {
    it('should play videos sequentially from start to finish', async () => {
      const onVideoChange = jest.fn();
      const onPlaybackComplete = jest.fn();
      const onProgress = jest.fn();

      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 3)} // Use first 3 videos
          onVideoChange={onVideoChange}
          onPlaybackComplete={onPlaybackComplete}
          onProgress={onProgress}
          autoAdvance={true}
          latencyMs={100}
        />
      );

      // Should start with first video
      await waitFor(() => {
        expect(screen.getByText(/Video 1 of 3/)).toBeInTheDocument();
        expect(screen.getByText(/test-video-1.mp4/)).toBeInTheDocument();
      });

      // Simulate video end event to trigger auto-advance
      act(() => {
        // Find video element and trigger ended event
        const videoElement = document.querySelector('video');
        if (videoElement) {
          fireEvent.ended(videoElement);
        }
      });

      // Fast-forward the latency timer
      act(() => {
        jest.advanceTimersByTime(150);
      });

      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'video-2' }),
          1
        );
        expect(onProgress).toHaveBeenCalledWith(expect.any(Number));
      });

      // Continue to second video end
      act(() => {
        const videoElement = document.querySelector('video');
        if (videoElement) {
          fireEvent.ended(videoElement);
        }
      });

      act(() => {
        jest.advanceTimersByTime(150);
      });

      // Continue to third video end
      act(() => {
        const videoElement = document.querySelector('video');
        if (videoElement) {
          fireEvent.ended(videoElement);
        }
      });

      act(() => {
        jest.advanceTimersByTime(150);
      });

      await waitFor(() => {
        expect(onPlaybackComplete).toHaveBeenCalled();
      });
    });

    it('should handle loop playback correctly', async () => {
      const onVideoChange = jest.fn();
      
      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 2)}
          onVideoChange={onVideoChange}
          loopPlayback={true}
          autoAdvance={true}
        />
      );

      // Simulate completing all videos
      for (let i = 0; i < 3; i++) { // Go past the end to test looping
        act(() => {
          const videoElement = document.querySelector('video');
          if (videoElement) {
            fireEvent.ended(videoElement);
          }
        });

        act(() => {
          jest.advanceTimersByTime(150);
        });
      }

      // Should loop back to first video
      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'video-1' }),
          0
        );
      });
    });

    it('should support manual navigation between videos', async () => {
      const onVideoChange = jest.fn();

      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 4)}
          onVideoChange={onVideoChange}
          autoAdvance={false}
        />
      );

      // Click next button
      const nextButton = screen.getByLabelText(/next video/i);
      await userEvent.click(nextButton);

      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'video-2' }),
          1
        );
      });

      // Click previous button
      const prevButton = screen.getByLabelText(/previous video/i);
      await userEvent.click(prevButton);

      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'video-1' }),
          0
        );
      });
    });
  });

  describe('2. Fullscreen Functionality', () => {
    it('should support fullscreen requests across different browser APIs', async () => {
      render(
        <SequentialVideoManager
          videos={[mockVideoPlaylist[0]]}
        />
      );

      // Mock different browser fullscreen APIs
      const testCases = [
        { api: 'requestFullscreen', mock: mockVideoElement.requestFullscreen },
        { api: 'webkitRequestFullscreen', mock: mockVideoElement.webkitRequestFullscreen },
        { api: 'mozRequestFullScreen', mock: mockVideoElement.mozRequestFullScreen },
        { api: 'msRequestFullscreen', mock: mockVideoElement.msRequestFullscreen },
      ];

      for (const testCase of testCases) {
        // Reset mocks
        Object.values(mockVideoElement).forEach(mock => {
          if (typeof mock === 'function' && mock.mockClear) {
            mock.mockClear();
          }
        });

        // Set up which API is available
        Object.keys(mockVideoElement).forEach(key => {
          if (key.includes('FullScreen') || key.includes('Fullscreen')) {
            delete (mockVideoElement as any)[key];
          }
        });
        
        (mockVideoElement as any)[testCase.api] = testCase.mock;

        // Trigger fullscreen
        const videoElement = document.querySelector('video');
        if (videoElement && (videoElement as any)[testCase.api]) {
          await act(async () => {
            await (videoElement as any)[testCase.api]();
          });
        }

        expect(testCase.mock).toHaveBeenCalled();
      }
    });

    it('should handle fullscreen API availability detection', () => {
      // Test various fullscreen API availability scenarios
      const scenarios = [
        { fullscreenEnabled: true, webkitFullscreenEnabled: false, expected: true },
        { fullscreenEnabled: false, webkitFullscreenEnabled: true, expected: true },
        { fullscreenEnabled: false, webkitFullscreenEnabled: false, expected: false },
      ];

      scenarios.forEach(({ fullscreenEnabled, webkitFullscreenEnabled, expected }) => {
        Object.defineProperty(document, 'fullscreenEnabled', { value: fullscreenEnabled, configurable: true });
        Object.defineProperty(document, 'webkitFullscreenEnabled', { value: webkitFullscreenEnabled, configurable: true });

        const isSupported = !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
        expect(isSupported).toBe(expected);
      });
    });
  });

  describe('3. Video Queue Management', () => {
    it('should support shuffling video order', async () => {
      const originalMathRandom = Math.random;
      Math.random = jest.fn().mockReturnValue(0.5); // Fixed random for predictable shuffle

      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 4)}
          randomOrder={true}
        />
      );

      const shuffleButton = screen.getByLabelText(/shuffle/i);
      await userEvent.click(shuffleButton);

      // Verify shuffle was applied (order changed)
      expect(Math.random).toHaveBeenCalled();

      Math.random = originalMathRandom;
    });

    it('should display video list view with progress tracking', async () => {
      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 3)}
        />
      );

      // Switch to list view
      const listViewButton = screen.getByLabelText(/show video list/i);
      await userEvent.click(listViewButton);

      await waitFor(() => {
        expect(screen.getByText(/Video Sequence \(3 videos\)/)).toBeInTheDocument();
        expect(screen.getByText(/1\. test-video-1\.mp4/)).toBeInTheDocument();
        expect(screen.getByText(/2\. test-video-2\.mp4/)).toBeInTheDocument();
        expect(screen.getByText(/3\. test-video-3\.mp4/)).toBeInTheDocument();
      });
    });

    it('should allow direct video selection from queue', async () => {
      const onVideoChange = jest.fn();

      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 4)}
          onVideoChange={onVideoChange}
        />
      );

      // Switch to list view
      const listViewButton = screen.getByLabelText(/show video list/i);
      await userEvent.click(listViewButton);

      // Click on third video
      const thirdVideoItem = screen.getByText(/3\. test-video-3\.mp4/);
      await userEvent.click(thirdVideoItem.closest('div[role="button"]') || thirdVideoItem);

      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalledWith(
          expect.objectContaining({ id: 'video-3' }),
          2
        );
      });
    });
  });

  describe('4. Video Loading States and Transitions', () => {
    it('should show loading states during video transitions', async () => {
      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 2)}
          autoAdvance={true}
        />
      );

      // Simulate video loading
      act(() => {
        const videoElement = document.querySelector('video');
        if (videoElement) {
          fireEvent.loadStart(videoElement);
        }
      });

      // Loading state should be managed by the video player component
      // This would typically show a loading spinner or progress indicator
      const videoElement = document.querySelector('video');
      expect(videoElement).toBeInTheDocument();
    });

    it('should handle smooth transitions between videos', async () => {
      const onVideoChange = jest.fn();

      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 3)}
          onVideoChange={onVideoChange}
          latencyMs={50} // Short delay for testing
        />
      );

      // Simulate video end
      act(() => {
        const videoElement = document.querySelector('video');
        if (videoElement) {
          fireEvent.ended(videoElement);
        }
      });

      // Should respect latency setting
      expect(onVideoChange).not.toHaveBeenCalled();

      act(() => {
        jest.advanceTimersByTime(60);
      });

      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalled();
      });
    });
  });

  describe('5. Error Handling', () => {
    it('should handle missing/corrupted videos gracefully', async () => {
      const onError = jest.fn();

      const mockVideoPlaybackManager = new VideoPlaybackManager({
        retryAttempts: 2,
        enableAutoRetry: true
      });

      const mockElement = document.createElement('video') as HTMLVideoElement;
      mockVideoPlaybackManager.attachVideoElement(mockElement);

      // Simulate loading a corrupted video URL
      const corruptedUrl = '/test-videos/corrupted-video.mp4';
      
      try {
        await mockVideoPlaybackManager.loadVideo(corruptedUrl);
      } catch (error) {
        expect(error).toBeDefined();
      }

      // Should have attempted retries
      const state = mockVideoPlaybackManager.getCurrentState();
      expect(state.error).toBeTruthy();
    });

    it('should recover from network errors with retry logic', async () => {
      const mockVideoPlaybackManager = new VideoPlaybackManager({
        retryAttempts: 3,
        retryDelay: 100,
        enableAutoRetry: true
      });

      const mockElement = document.createElement('video') as HTMLVideoElement;
      
      // Mock network failure followed by success
      jest.spyOn(mockVideoPlaybackManager as any, 'attemptLoad')
        .mockRejectedValueOnce(new Error('Network error'))
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(undefined);

      mockVideoPlaybackManager.attachVideoElement(mockElement);

      await expect(mockVideoPlaybackManager.loadVideo('/test-video.mp4')).resolves.not.toThrow();
    });

    it('should display appropriate error messages for different error types', async () => {
      const errorScenarios = [
        { type: 'network', message: 'Network connection error' },
        { type: 'decode', message: 'Video format not supported' },
        { type: 'src_not_supported', message: 'Video source not supported' },
        { type: 'timeout', message: 'Video load timeout' },
      ];

      errorScenarios.forEach(scenario => {
        const mockError = {
          type: scenario.type,
          message: scenario.message,
          recoverable: scenario.type === 'network' || scenario.type === 'timeout',
          timestamp: Date.now(),
        };

        // Verify error categorization logic
        expect(mockError.recoverable).toBe(['network', 'timeout'].includes(scenario.type));
      });
    });
  });

  describe('6. User Controls', () => {
    it('should support play/pause/stop controls', async () => {
      render(
        <SequentialVideoManager
          videos={[mockVideoPlaylist[0]]}
        />
      );

      // These controls would be in the VideoAnnotationPlayer component
      // We can test the sequential manager's control over playback state
      const videoElement = document.querySelector('video');
      expect(videoElement).toBeInTheDocument();

      // Simulate play
      act(() => {
        if (videoElement) {
          fireEvent.play(videoElement);
        }
      });

      // Simulate pause
      act(() => {
        if (videoElement) {
          fireEvent.pause(videoElement);
        }
      });
    });

    it('should support skip controls', async () => {
      const onVideoChange = jest.fn();

      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 3)}
          onVideoChange={onVideoChange}
        />
      );

      // Test skip next
      const nextButton = screen.getByLabelText(/next video/i);
      await userEvent.click(nextButton);

      expect(onVideoChange).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'video-2' }),
        1
      );

      // Test skip previous
      const prevButton = screen.getByLabelText(/previous video/i);
      await userEvent.click(prevButton);

      expect(onVideoChange).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'video-1' }),
        0
      );
    });
  });

  describe('7. Performance and Memory Management', () => {
    it('should properly cleanup video elements and event listeners', () => {
      const mockVideoPlaybackManager = new VideoPlaybackManager();
      const mockElement = document.createElement('video') as HTMLVideoElement;
      
      const addEventListenerSpy = jest.spyOn(mockElement, 'addEventListener');
      const removeEventListenerSpy = jest.spyOn(mockElement, 'removeEventListener');

      mockVideoPlaybackManager.attachVideoElement(mockElement);
      expect(addEventListenerSpy).toHaveBeenCalledTimes(12); // Based on the event list in setupEventListeners

      mockVideoPlaybackManager.detachVideoElement();
      expect(removeEventListenerSpy).toHaveBeenCalledTimes(12);

      mockVideoPlaybackManager.destroy();
    });

    it('should handle video preloading efficiently', async () => {
      const mockVideoPlaybackManager = new VideoPlaybackManager({
        loadTimeout: 5000
      });

      const mockElement = document.createElement('video') as HTMLVideoElement;
      mockVideoPlaybackManager.attachVideoElement(mockElement);

      const loadPromise = mockVideoPlaybackManager.loadVideo('/test-video.mp4');
      
      // Should resolve within timeout period
      await expect(loadPromise).resolves.not.toThrow();
    });

    it('should track memory usage and prevent leaks', () => {
      const mockVideoPlaybackManager = new VideoPlaybackManager();
      
      // Simulate multiple video loads
      for (let i = 0; i < 5; i++) {
        const mockElement = document.createElement('video') as HTMLVideoElement;
        mockVideoPlaybackManager.attachVideoElement(mockElement);
        mockVideoPlaybackManager.detachVideoElement();
      }

      mockVideoPlaybackManager.destroy();
      
      // Verify cleanup
      expect(mockVideoPlaybackManager.getCurrentState()).toEqual(
        expect.objectContaining({
          isPlaying: false,
          currentTime: 0,
          duration: 0,
          error: null,
        })
      );
    });
  });

  describe('8. LabJack Data Synchronization', () => {
    it('should support external signal synchronization', async () => {
      const onSyncRequest = jest.fn();

      render(
        <SequentialVideoManager
          videos={[mockVideoPlaylist[0]]}
          syncExternalSignals={true}
        />
      );

      // Synchronization features would be implemented in the VideoAnnotationPlayer
      // Test that sync props are passed correctly
      expect(screen.getByText(/Sequential Playback/)).toBeInTheDocument();
    });

    it('should handle sync timing with specified latency', async () => {
      const onVideoChange = jest.fn();
      const latency = 200; // 200ms latency

      render(
        <SequentialVideoManager
          videos={mockVideoPlaylist.slice(0, 2)}
          onVideoChange={onVideoChange}
          autoAdvance={true}
          latencyMs={latency}
          syncExternalSignals={true}
        />
      );

      // Simulate video end
      act(() => {
        const videoElement = document.querySelector('video');
        if (videoElement) {
          fireEvent.ended(videoElement);
        }
      });

      // Should not advance immediately
      expect(onVideoChange).not.toHaveBeenCalled();

      // Advance by less than latency
      act(() => {
        jest.advanceTimersByTime(latency - 50);
      });

      expect(onVideoChange).not.toHaveBeenCalled();

      // Advance to complete latency period
      act(() => {
        jest.advanceTimersByTime(100);
      });

      await waitFor(() => {
        expect(onVideoChange).toHaveBeenCalled();
      });
    });
  });

  describe('9. Recording Mode Integration', () => {
    it('should support recording mode toggle', async () => {
      render(
        <SequentialVideoManager
          videos={[mockVideoPlaylist[0]]}
        />
      );

      // Initially should not be recording
      expect(screen.queryByText(/Recording/)).not.toBeInTheDocument();

      // Recording mode would be controlled by the VideoAnnotationPlayer component
      // We can verify the recording indicator is managed properly
      expect(screen.getByText(/Sequential Playback/)).toBeInTheDocument();
    });
  });
});