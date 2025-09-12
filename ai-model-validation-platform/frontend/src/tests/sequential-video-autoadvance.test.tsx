/**
 * Sequential Video Auto-Advance Test
 * 
 * Specific test to verify that videos automatically advance from Video 1 to Video 2
 * and through the complete sequence without user intervention.
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { VideoFile } from '../services/types';

// Mock data - small set to focus on auto-advance behavior
const createTestVideo = (id: string, filename: string, duration = 3): VideoFile => ({
  id,
  filename,
  originalName: filename,
  url: `/test-videos/${filename}`,
  projectId: 'autoadvance-test',
  status: 'completed',
  duration,
  fps: 30,
  size: 1024 * 512,
  fileSize: 1024 * 512,
  createdAt: new Date().toISOString(),
  uploadedAt: new Date().toISOString(),
  groundTruthGenerated: false,
  groundTruthStatus: 'pending',
  processing_status: 'completed',
  detectionCount: 0
});

const testVideos: VideoFile[] = [
  createTestVideo('auto-test-1', 'video-1.mp4', 2), // Short 2-second video
  createTestVideo('auto-test-2', 'video-2.mp4', 2), // Short 2-second video  
  createTestVideo('auto-test-3', 'video-3.mp4', 2), // Short 2-second video
];

const theme = createTheme();

// Mock the video element to simulate video playback events
const mockVideoElement = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  play: jest.fn().mockResolvedValue(undefined),
  pause: jest.fn(),
  load: jest.fn(),
  currentTime: 0,
  duration: 2,
  readyState: 4, // HAVE_ENOUGH_DATA
  paused: false,
  ended: false,
  src: '',
  setAttribute: jest.fn(),
  style: {},
  parentElement: document.createElement('div'),
  dispatchEvent: jest.fn(),
} as unknown as HTMLVideoElement;

// Track video events for testing
const videoEvents: { [key: string]: EventListener } = {};

beforeEach(() => {
  // Reset mocks
  jest.clearAllMocks();
  
  // Mock document.createElement to return our mock video element
  jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
    if (tagName === 'video') {
      // Override addEventListener to capture event handlers
      mockVideoElement.addEventListener = jest.fn((event: string, handler: EventListener) => {
        videoEvents[event] = handler;
      });
      return mockVideoElement;
    }
    return document.createElement(tagName);
  });

  // Mock console methods to capture debug output
  jest.spyOn(console, 'log').mockImplementation(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('Sequential Video Auto-Advance', () => {
  const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <ThemeProvider theme={theme}>{children}</ThemeProvider>
  );

  test('should auto-advance from Video 1 to Video 2 when first video ends', async () => {
    const onVideoStart = jest.fn();
    const onVideoEnd = jest.fn();
    const onPlaybackComplete = jest.fn();

    render(
      <TestWrapper>
        <SequentialVideoPlayer
          videos={testVideos}
          config={{
            autoAdvance: true,
            loopPlayback: false,
            transitionDelay: 10, // Minimal delay for testing
          }}
          onVideoStart={onVideoStart}
          onVideoEnd={onVideoEnd}
          onPlaybackComplete={onPlaybackComplete}
          autoStart={true}
          showControls={true}
          showProgress={true}
        />
      </TestWrapper>
    );

    // Wait for component to initialize
    await waitFor(() => {
      expect(screen.getByText(/Sequential Playback Progress/i)).toBeInTheDocument();
    });

    // Verify Video 1 is currently playing
    await waitFor(() => {
      expect(screen.getByText(/Video 1 of 3/i)).toBeInTheDocument();
    });

    // Simulate Video 1 ending
    act(() => {
      if (videoEvents['ended']) {
        console.log('🧪 Test: Triggering video "ended" event for Video 1');
        videoEvents['ended']({} as Event);
      }
    });

    // Wait for auto-advance to occur
    await waitFor(() => {
      expect(onVideoEnd).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'auto-test-1' }),
        0
      );
    }, { timeout: 5000 });

    // Verify Video 2 started
    await waitFor(() => {
      expect(onVideoStart).toHaveBeenCalledWith(
        expect.objectContaining({ id: 'auto-test-2' }),
        1
      );
    }, { timeout: 5000 });

    // Check console logs for debug information
    expect(console.log).toHaveBeenCalledWith(
      expect.stringContaining('🏁 Video "ended" event fired for:')
    );
    
    expect(console.log).toHaveBeenCalledWith(
      expect.stringContaining('🔄 Auto-advance enabled, checking next video...')
    );
    
    expect(console.log).toHaveBeenCalledWith(
      expect.stringContaining('⏭️ Auto-advancing to next video immediately...')
    );
  });

  test('should complete full sequence: Video 1 → Video 2 → Video 3 → Complete', async () => {
    const onVideoStart = jest.fn();
    const onVideoEnd = jest.fn();
    const onPlaybackComplete = jest.fn();

    render(
      <TestWrapper>
        <SequentialVideoPlayer
          videos={testVideos}
          config={{
            autoAdvance: true,
            loopPlayback: false,
            transitionDelay: 10,
          }}
          onVideoStart={onVideoStart}
          onVideoEnd={onVideoEnd}
          onPlaybackComplete={onPlaybackComplete}
          autoStart={true}
        />
      </TestWrapper>
    );

    // Wait for initialization
    await waitFor(() => {
      expect(screen.getByText(/Video 1 of 3/i)).toBeInTheDocument();
    });

    // Simulate complete sequence: Video 1 → Video 2 → Video 3 → Complete
    for (let videoIndex = 0; videoIndex < testVideos.length; videoIndex++) {
      console.log(`🧪 Test: Simulating Video ${videoIndex + 1} ending`);
      
      act(() => {
        if (videoEvents['ended']) {
          videoEvents['ended']({} as Event);
        }
      });

      // Wait for appropriate callbacks
      if (videoIndex < testVideos.length - 1) {
        // Not the last video - should advance to next
        await waitFor(() => {
          expect(onVideoEnd).toHaveBeenCalledWith(
            expect.objectContaining({ id: testVideos[videoIndex].id }),
            videoIndex
          );
        }, { timeout: 2000 });

        await waitFor(() => {
          expect(onVideoStart).toHaveBeenCalledWith(
            expect.objectContaining({ id: testVideos[videoIndex + 1].id }),
            videoIndex + 1
          );
        }, { timeout: 2000 });
      } else {
        // Last video - should complete playback
        await waitFor(() => {
          expect(onPlaybackComplete).toHaveBeenCalled();
        }, { timeout: 2000 });
      }

      // Small delay between video transitions
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 50));
      });
    }

    // Verify complete sequence was called
    expect(onVideoStart).toHaveBeenCalledTimes(3); // All videos started
    expect(onVideoEnd).toHaveBeenCalledTimes(3); // All videos ended
    expect(onPlaybackComplete).toHaveBeenCalledTimes(1); // Sequence completed
  });

  test('should handle auto-advance failures gracefully with retry', async () => {
    const onVideoEnd = jest.fn();
    const onError = jest.fn();

    // Mock a video element that fails to load the second video
    const failingVideoElement = {
      ...mockVideoElement,
      play: jest.fn()
        .mockResolvedValueOnce(undefined) // First video plays fine
        .mockRejectedValueOnce(new Error('Network error')) // Second video fails
        .mockResolvedValueOnce(undefined), // Third video (retry) works
    };

    jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'video') {
        failingVideoElement.addEventListener = jest.fn((event: string, handler: EventListener) => {
          videoEvents[event] = handler;
        });
        return failingVideoElement as unknown as HTMLVideoElement;
      }
      return document.createElement(tagName);
    });

    render(
      <TestWrapper>
        <SequentialVideoPlayer
          videos={testVideos}
          config={{
            autoAdvance: true,
            loopPlayback: false,
            maxRetries: 2,
          }}
          onVideoEnd={onVideoEnd}
          onError={onError}
          autoStart={true}
        />
      </TestWrapper>
    );

    // Wait for initialization
    await waitFor(() => {
      expect(screen.getByText(/Sequential Playback Progress/i)).toBeInTheDocument();
    });

    // Simulate Video 1 ending
    act(() => {
      if (videoEvents['ended']) {
        videoEvents['ended']({} as Event);
      }
    });

    // Wait for error handling and retry logic
    await waitFor(() => {
      expect(console.log).toHaveBeenCalledWith(
        expect.stringContaining('❌ Failed to advance to next video:')
      );
    }, { timeout: 3000 });

    // Verify retry mechanism was triggered
    await waitFor(() => {
      expect(console.log).toHaveBeenCalledWith(
        expect.stringContaining('⏭️ Auto-advancing to next video immediately...')
      );
    }, { timeout: 2000 });
  });

  test('should not auto-advance when autoAdvance is disabled', async () => {
    const onVideoEnd = jest.fn();
    const onVideoStart = jest.fn();

    render(
      <TestWrapper>
        <SequentialVideoPlayer
          videos={testVideos}
          config={{
            autoAdvance: false, // Disabled auto-advance
            loopPlayback: false,
          }}
          onVideoEnd={onVideoEnd}
          onVideoStart={onVideoStart}
          autoStart={true}
        />
      </TestWrapper>
    );

    // Wait for initialization
    await waitFor(() => {
      expect(screen.getByText(/Video 1 of 3/i)).toBeInTheDocument();
    });

    // Simulate Video 1 ending
    act(() => {
      if (videoEvents['ended']) {
        videoEvents['ended']({} as Event);
      }
    });

    // Wait and verify no auto-advance occurred
    await waitFor(() => {
      expect(onVideoEnd).toHaveBeenCalledTimes(1);
    });

    // Should stay on Video 1 and not advance
    expect(onVideoStart).toHaveBeenCalledTimes(1); // Only initial start
    
    // Check for the "auto-advance disabled" log message
    expect(console.log).toHaveBeenCalledWith(
      expect.stringContaining('⏸️ Auto-advance disabled - waiting for manual control')
    );
  });
});