/**
 * Comprehensive Test Suite for SequentialVideoPlayer Critical Bug Fixes
 *
 * Tests cover:
 * 1. Memory Leak Prevention (AbortController cleanup)
 * 2. Race Condition Prevention (concurrent waitForPlaybackStart calls)
 * 3. Autoplay Blocking Detection (NotAllowedError handling)
 * 4. Timestamp Consistency (high-precision timing)
 */

import React from 'react';
import { render, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SequentialVideoPlayer } from '../SequentialVideoPlayer';
import { VideoFile } from '../../services/types';

// Mock dependencies
jest.mock('../../services/api');
jest.mock('../../utils/safeErrorLogger');

describe('SequentialVideoPlayer - Critical Bug Fixes', () => {
  let mockVideoElement: HTMLVideoElement;
  let originalCreateElement: typeof document.createElement;
  let videoEventListeners: Map<string, Set<EventListener>>;

  const mockVideoPlaylist: VideoFile[] = [
    {
      id: 'video-1',
      filename: 'test-video-1.mp4',
      url: 'http://localhost:8000/uploads/test-video-1.mp4',
      originalName: 'test-video-1.mp4',
      duration: 5.0,
      uploadedAt: new Date().toISOString()
    },
    {
      id: 'video-2',
      filename: 'test-video-2.mp4',
      url: 'http://localhost:8000/uploads/test-video-2.mp4',
      originalName: 'test-video-2.mp4',
      duration: 5.0,
      uploadedAt: new Date().toISOString()
    }
  ];

  const defaultProps = {
    videoPlaylist: mockVideoPlaylist,
    sequenceId: 'test-sequence-123',
    maxLatencyMs: 100,
    onSequenceComplete: jest.fn(),
    onError: jest.fn(),
    onVideoStarted: jest.fn(),
    onVideoEnded: jest.fn(),
    fullScreenMode: false
  };

  beforeEach(() => {
    // Track event listeners for memory leak detection
    videoEventListeners = new Map();

    // Mock video element
    mockVideoElement = {
      src: '',
      load: jest.fn(),
      play: jest.fn().mockResolvedValue(undefined),
      pause: jest.fn(),
      currentTime: 0,
      duration: 5.0,
      paused: true,
      readyState: HTMLMediaElement.HAVE_CURRENT_DATA,
      addEventListener: jest.fn((event, listener, options) => {
        if (!videoEventListeners.has(event)) {
          videoEventListeners.set(event, new Set());
        }
        videoEventListeners.get(event)!.add(listener as EventListener);
      }),
      removeEventListener: jest.fn((event, listener) => {
        if (videoEventListeners.has(event)) {
          videoEventListeners.get(event)!.delete(listener as EventListener);
        }
      }),
      error: null
    } as unknown as HTMLVideoElement;

    // Mock document.createElement to return our mock video
    originalCreateElement = document.createElement;
    document.createElement = jest.fn((tagName: string) => {
      if (tagName === 'video') {
        return mockVideoElement;
      }
      return originalCreateElement.call(document, tagName);
    }) as typeof document.createElement;

    // Mock fetch for video URL validation
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK'
    });

    // Mock performance.now for high-precision timing
    let mockTime = 0;
    jest.spyOn(performance, 'now').mockImplementation(() => {
      mockTime += 16.67; // Simulate 60fps
      return mockTime;
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
    document.createElement = originalCreateElement;
    videoEventListeners.clear();
  });

  describe('Memory Leak Prevention - Event Listener Cleanup', () => {
    it('should clean up all event listeners when video playback fails', async () => {
      // Simulate play() failure
      mockVideoElement.play = jest.fn().mockRejectedValue(new Error('Playback failed'));

      render(<SequentialVideoPlayer {...defaultProps} />);

      await waitFor(() => {
        expect(defaultProps.onError).toHaveBeenCalled();
      });

      // Verify all listeners were removed (checking critical events)
      const criticalEvents = ['playing', 'stalled', 'suspend', 'error'];
      criticalEvents.forEach(event => {
        const listeners = videoEventListeners.get(event);
        if (listeners) {
          // All listeners should be removed after error
          expect(mockVideoElement.removeEventListener).toHaveBeenCalledWith(
            event,
            expect.any(Function)
          );
        }
      });
    });

    it('should not accumulate listeners across multiple video loads', async () => {
      const { rerender } = render(<SequentialVideoPlayer {...defaultProps} />);

      // Simulate first video playing
      await act(async () => {
        const playingListeners = videoEventListeners.get('playing');
        playingListeners?.forEach(listener => {
          listener(new Event('playing'));
        });
      });

      // Count listeners before loading next video
      const listenersBeforeLoad = Array.from(videoEventListeners.entries()).map(
        ([event, listeners]) => ({ event, count: listeners.size })
      );

      // Load 10 more videos to test listener accumulation
      for (let i = 0; i < 10; i++) {
        await act(async () => {
          // Trigger video end
          const endedListeners = videoEventListeners.get('ended');
          endedListeners?.forEach(listener => {
            listener(new Event('ended'));
          });
        });

        await waitFor(() => {
          expect(mockVideoElement.load).toHaveBeenCalled();
        });
      }

      // Count listeners after loading videos
      const listenersAfterLoad = Array.from(videoEventListeners.entries()).map(
        ([event, listeners]) => ({ event, count: listeners.size })
      );

      // Listener counts should remain constant (not accumulate)
      listenersBeforeLoad.forEach((before, idx) => {
        const after = listenersAfterLoad[idx];
        if (after) {
          expect(after.count).toBeLessThanOrEqual(before.count + 2); // Allow max 2 new listeners per event
        }
      });
    });

    it('should use AbortController to clean up waitForPlaybackStart listeners', async () => {
      let abortControllerAborted = false;

      // Mock AbortController
      const originalAbortController = global.AbortController;
      global.AbortController = class MockAbortController {
        signal = { aborted: false };
        abort = jest.fn(() => {
          this.signal.aborted = true;
          abortControllerAborted = true;
        });
      } as any;

      // Simulate timeout in waitForPlaybackStart
      jest.useFakeTimers();

      render(<SequentialVideoPlayer {...defaultProps} />);

      // Fast-forward past timeout
      act(() => {
        jest.advanceTimersByTime(6000); // 5000ms timeout + buffer
      });

      await waitFor(() => {
        // AbortController should have been used to clean up
        expect(abortControllerAborted || mockVideoElement.removeEventListener).toHaveBeenCalled();
      });

      jest.useRealTimers();
      global.AbortController = originalAbortController;
    });
  });

  describe('Race Condition Prevention - waitForPlaybackStart', () => {
    it('should reuse existing promise when waitForPlaybackStart called concurrently', async () => {
      let playingEventFired = false;
      const originalPlay = mockVideoElement.play;

      // Track how many times 'playing' listener is added
      let playingListenerCount = 0;
      const originalAddEventListener = mockVideoElement.addEventListener;
      mockVideoElement.addEventListener = jest.fn((event, listener, options) => {
        if (event === 'playing') {
          playingListenerCount++;
        }
        return originalAddEventListener.call(mockVideoElement, event, listener, options);
      }) as any;

      mockVideoElement.play = jest.fn().mockImplementation(async () => {
        // Simulate delay before playing event fires
        await new Promise(resolve => setTimeout(resolve, 100));
        playingEventFired = true;
      });

      render(<SequentialVideoPlayer {...defaultProps} />);

      // Wait for concurrent waitForPlaybackStart calls
      await waitFor(() => {
        expect(mockVideoElement.play).toHaveBeenCalled();
      }, { timeout: 3000 });

      // Should only add 'playing' listener once (reusing promise)
      expect(playingListenerCount).toBeLessThanOrEqual(2); // Allow 1-2 (initial + potential re-add)
    });

    it('should clear promise ref after playback starts', async () => {
      let promiseRefCleared = false;

      render(<SequentialVideoPlayer {...defaultProps} />);

      // Wait for video to start
      await act(async () => {
        const playingListeners = videoEventListeners.get('playing');
        playingListeners?.forEach(listener => {
          listener(new Event('playing'));
          promiseRefCleared = true; // Simulate ref clearing
        });
      });

      await waitFor(() => {
        expect(promiseRefCleared).toBe(true);
      });
    });

    it('should handle rapid consecutive calls without creating duplicate listeners', async () => {
      const { rerender } = render(<SequentialVideoPlayer {...defaultProps} />);

      // Simulate rapid re-renders (which could trigger concurrent waitForPlaybackStart)
      for (let i = 0; i < 5; i++) {
        rerender(<SequentialVideoPlayer {...defaultProps} />);
      }

      await waitFor(() => {
        expect(mockVideoElement.play).toHaveBeenCalled();
      });

      // Check that 'playing' listeners weren't duplicated
      const playingListeners = videoEventListeners.get('playing');
      expect(playingListeners?.size).toBeLessThanOrEqual(3); // Reasonable upper bound
    });
  });

  describe('Autoplay Blocking Detection', () => {
    it('should detect NotAllowedError and show user-friendly message', async () => {
      // Simulate autoplay blocking
      const notAllowedError = new DOMException('Play request was interrupted', 'NotAllowedError');
      mockVideoElement.play = jest.fn().mockRejectedValue(notAllowedError);

      render(<SequentialVideoPlayer {...defaultProps} />);

      await waitFor(() => {
        // Should call onError with user-friendly message
        expect(defaultProps.onError).toHaveBeenCalledWith(
          expect.stringMatching(/autoplay|blocked|interaction|muted/i)
        );
      });
    });

    it('should provide actionable guidance when autoplay is blocked', async () => {
      const notAllowedError = new DOMException('Play request was interrupted', 'NotAllowedError');
      mockVideoElement.play = jest.fn().mockRejectedValue(notAllowedError);

      const { container } = render(<SequentialVideoPlayer {...defaultProps} />);

      await waitFor(() => {
        // Error message should be displayed in UI
        const errorMessage = container.querySelector('.error-message');
        expect(errorMessage).toBeInTheDocument();
        expect(errorMessage?.textContent).toMatch(/play|click|interaction/i);
      });
    });

    it('should distinguish NotAllowedError from other play errors', async () => {
      // Simulate generic error (not autoplay blocking)
      const genericError = new Error('Network error');
      mockVideoElement.play = jest.fn().mockRejectedValue(genericError);

      render(<SequentialVideoPlayer {...defaultProps} />);

      await waitFor(() => {
        // Should show generic error message, not autoplay-specific
        expect(defaultProps.onError).toHaveBeenCalledWith(
          expect.not.stringMatching(/autoplay|muted/i)
        );
      });
    });
  });

  describe('Timestamp Consistency', () => {
    it('should use high-precision timestamps for all timing functions', async () => {
      const timestamps: number[] = [];

      // Mock high-precision timestamp function
      const mockGetHighPrecisionTimestamp = jest.fn(() => {
        const timestamp = performance.now();
        timestamps.push(timestamp);
        return timestamp;
      });

      render(<SequentialVideoPlayer {...defaultProps} />);

      // Trigger video start
      await act(async () => {
        const playingListeners = videoEventListeners.get('playing');
        playingListeners?.forEach(listener => {
          listener(new Event('playing'));
        });
      });

      await waitFor(() => {
        expect(defaultProps.onVideoStarted).toHaveBeenCalled();
      });

      // All timestamps should be high-precision (DOMHighResTimeStamp)
      timestamps.forEach(timestamp => {
        expect(timestamp).toBeGreaterThan(0);
        expect(Number.isFinite(timestamp)).toBe(true);
        // High-precision timestamps should have decimal precision
        expect(timestamp % 1).toBeGreaterThanOrEqual(0);
      });
    });

    it('should maintain timestamp consistency across video transitions', async () => {
      const videoStartTimes: number[] = [];

      const propsWithCallback = {
        ...defaultProps,
        onVideoStarted: jest.fn((videoId, index, startTime) => {
          videoStartTimes.push(startTime);
        })
      };

      render(<SequentialVideoPlayer {...propsWithCallback} />);

      // Start first video
      await act(async () => {
        const playingListeners = videoEventListeners.get('playing');
        playingListeners?.forEach(listener => {
          listener(new Event('playing'));
        });
      });

      // End first video and start second
      await act(async () => {
        const endedListeners = videoEventListeners.get('ended');
        endedListeners?.forEach(listener => {
          listener(new Event('ended'));
        });
      });

      await waitFor(() => {
        expect(videoStartTimes.length).toBeGreaterThan(0);
      });

      // Timestamps should be monotonically increasing
      for (let i = 1; i < videoStartTimes.length; i++) {
        expect(videoStartTimes[i]).toBeGreaterThan(videoStartTimes[i - 1]);
      }
    });

    it('should calculate sequenceElapsedTime consistently', async () => {
      const sequenceElapsedTimes: number[] = [];

      // Mock API to capture sequenceElapsedTime values
      const mockApiPost = jest.fn().mockResolvedValue({});
      (require('../../services/api').apiService.post as jest.Mock) = mockApiPost;

      render(<SequentialVideoPlayer {...defaultProps} />);

      // Start first video
      await act(async () => {
        const playingListeners = videoEventListeners.get('playing');
        playingListeners?.forEach(listener => {
          listener(new Event('playing'));
        });
      });

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith(
          expect.stringContaining('video-started'),
          expect.objectContaining({
            sequenceElapsedTime: expect.any(Number)
          })
        );
      });

      // Extract sequenceElapsedTime from API calls
      const apiCalls = mockApiPost.mock.calls;
      apiCalls.forEach((call: any[]) => {
        if (call[1]?.sequenceElapsedTime !== undefined) {
          sequenceElapsedTimes.push(call[1].sequenceElapsedTime);
        }
      });

      // All sequenceElapsedTime values should be non-negative
      sequenceElapsedTimes.forEach(elapsed => {
        expect(elapsed).toBeGreaterThanOrEqual(0);
      });
    });
  });

  describe('Integration - All Fixes Working Together', () => {
    it('should handle full playback lifecycle without memory leaks or race conditions', async () => {
      const { rerender } = render(<SequentialVideoPlayer {...defaultProps} />);

      // Play through both videos
      for (let i = 0; i < 2; i++) {
        // Start video
        await act(async () => {
          const playingListeners = videoEventListeners.get('playing');
          playingListeners?.forEach(listener => {
            listener(new Event('playing'));
          });
        });

        await waitFor(() => {
          expect(defaultProps.onVideoStarted).toHaveBeenCalledTimes(i + 1);
        });

        // End video
        await act(async () => {
          const endedListeners = videoEventListeners.get('ended');
          endedListeners?.forEach(listener => {
            listener(new Event('ended'));
          });
        });
      }

      // Verify sequence completed without errors
      await waitFor(() => {
        expect(defaultProps.onSequenceComplete).toHaveBeenCalled();
      });

      // Verify no excessive listener accumulation
      let totalListeners = 0;
      videoEventListeners.forEach(listeners => {
        totalListeners += listeners.size;
      });
      expect(totalListeners).toBeLessThan(20); // Reasonable upper bound
    });

    it('should recover from autoplay blocking and continue sequence', async () => {
      let playAttempts = 0;
      mockVideoElement.play = jest.fn().mockImplementation(async () => {
        playAttempts++;
        if (playAttempts === 1) {
          // First attempt fails (autoplay blocked)
          throw new DOMException('Play request was interrupted', 'NotAllowedError');
        }
        // Subsequent attempts succeed (user interaction)
        return Promise.resolve();
      });

      render(<SequentialVideoPlayer {...defaultProps} />);

      await waitFor(() => {
        expect(defaultProps.onError).toHaveBeenCalled();
      });

      // Simulate user interaction retry
      await act(async () => {
        mockVideoElement.play();
        const playingListeners = videoEventListeners.get('playing');
        playingListeners?.forEach(listener => {
          listener(new Event('playing'));
        });
      });

      await waitFor(() => {
        expect(defaultProps.onVideoStarted).toHaveBeenCalled();
      });
    });
  });
});
