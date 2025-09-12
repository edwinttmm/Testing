/**
 * Sequential Video Auto-Advance Fix Test
 * 
 * This test specifically targets the fix for the auto-advance issue where
 * videos 2 and 3 were not automatically advancing after video 1 ended.
 * 
 * The fix involves using dual-channel event handling:
 * 1. Primary: VideoPlaybackManager state change callbacks
 * 2. Backup: Direct DOM event listeners
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { VideoFile } from '../services/types';

const theme = createTheme();

// Create test videos with realistic durations
const createTestVideo = (id: string, filename: string, duration = 3): VideoFile => ({
  id,
  filename,
  originalName: filename,
  url: `/test-videos/${filename}`,
  projectId: 'autoadvance-fix-test',
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

const testVideos: VideoFile[] = [
  createTestVideo('fix-test-1', 'video-1-fix-test.mp4', 2),
  createTestVideo('fix-test-2', 'video-2-fix-test.mp4', 2),
  createTestVideo('fix-test-3', 'video-3-fix-test.mp4', 2),
];

// Create a proper HTMLVideoElement mock that integrates with DOM
const createMockVideoElement = () => {
  // Create a real DOM element for proper integration
  const element = document.createElement('div') as any;
  element.tagName = 'VIDEO';
  
  // Add all video-specific properties and methods
  Object.assign(element, {
    currentTime: 0,
    duration: 2,
    readyState: 4, // HAVE_ENOUGH_DATA
    paused: false,
    ended: false,
    videoWidth: 640,
    videoHeight: 480,
    src: '',
    muted: false,
    volume: 1,
    play: jest.fn().mockResolvedValue(undefined),
    pause: jest.fn(),
    load: jest.fn(),
    addEventListener: element.addEventListener.bind(element),
    removeEventListener: element.removeEventListener.bind(element),
    dispatchEvent: element.dispatchEvent.bind(element),
    getBoundingClientRect: jest.fn().mockReturnValue({
      top: 0, left: 0, width: 640, height: 480, bottom: 480, right: 640
    })
  });

  return element as HTMLVideoElement;
};

// Track event listeners for testing
const eventListeners: { [key: string]: EventListener[] } = {};

beforeEach(() => {
  // Clear event listeners
  Object.keys(eventListeners).forEach(key => {
    eventListeners[key] = [];
  });

  // Store the original createElement to avoid infinite recursion
  const originalCreateElement = document.createElement.bind(document);

  // Mock createElement to return our controlled video elements
  jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
    if (tagName === 'video') {
      const element = createMockVideoElement();
      
      // Override addEventListener to capture handlers
      const originalAddEventListener = element.addEventListener;
      element.addEventListener = jest.fn((event: string, handler: EventListener) => {
        if (!eventListeners[event]) eventListeners[event] = [];
        eventListeners[event].push(handler);
        // Also call the original to maintain functionality
        originalAddEventListener.call(element, event, handler);
      });

      return element;
    }
    // Use the original createElement for non-video elements
    return originalCreateElement(tagName);
  });

  // Mock console to capture debug logs
  jest.spyOn(console, 'log').mockImplementation(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
  jest.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('Sequential Video Auto-Advance Fix', () => {
  const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <ThemeProvider theme={theme}>{children}</ThemeProvider>
  );

  test('should handle video end event through dual-channel approach', async () => {
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
        />
      </TestWrapper>
    );

    // Wait for component to initialize - look for control buttons that should always be present
    await waitFor(() => {
      expect(screen.getByLabelText('Start/Resume Playback')).toBeInTheDocument();
    });

    // Verify both event listeners are attached
    expect(eventListeners['ended']).toBeDefined();
    expect(eventListeners['ended'].length).toBeGreaterThan(0);
    expect(eventListeners['playing']).toBeDefined();
    expect(eventListeners['loadstart']).toBeDefined();

    console.log('🧪 Test: Event listeners attached:', Object.keys(eventListeners));

    // Simulate video 1 ending via DOM event
    act(() => {
      if (eventListeners['ended'] && eventListeners['ended'][0]) {
        console.log('🧪 Test: Triggering ended event for Video 1');
        eventListeners['ended'][0]({} as Event);
      }
    });

    // Wait for auto-advance to complete
    await waitFor(() => {
      expect(console.log).toHaveBeenCalledWith(
        expect.stringMatching(/🏁 Video "ended".*for:.*video-1-fix-test/)
      );
    }, { timeout: 3000 });

    // Verify the handleVideoEnd was called
    expect(console.log).toHaveBeenCalledWith(
      expect.stringMatching(/🔄 Auto-advance enabled, checking next video.../)
    );

    // Verify transition was attempted
    expect(console.log).toHaveBeenCalledWith(
      expect.stringMatching(/⏭️ Auto-advancing to next video immediately.../)
    );
  });

  test('should successfully transition from Video 1 to Video 2', async () => {
    const onVideoStart = jest.fn();
    const onVideoEnd = jest.fn();

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
          autoStart={true}
        />
      </TestWrapper>
    );

    // Wait for initialization - check for control buttons
    await waitFor(() => {
      expect(screen.getByLabelText('Start/Resume Playback')).toBeInTheDocument();
    });

    // Trigger video end
    act(() => {
      if (eventListeners['ended'] && eventListeners['ended'][0]) {
        eventListeners['ended'][0]({} as Event);
      }
    });

    // Wait for transition logs
    await waitFor(() => {
      expect(console.log).toHaveBeenCalledWith(
        expect.stringMatching(/🎯 advanceToNext\(\) called/)
      );
    }, { timeout: 2000 });

    // Verify next video index calculation
    expect(console.log).toHaveBeenCalledWith(
      expect.stringMatching(/🔢 getNextVideoIndex\(\) - current: 0, next calculated: 1/)
    );

    // Verify transition initiated
    expect(console.log).toHaveBeenCalledWith(
      expect.stringMatching(/🔄 transitionToVideo\(1\) called/)
    );

    // Verify video loading
    expect(console.log).toHaveBeenCalledWith(
      expect.stringMatching(/🎬 Loading video at index 1/)
    );
  });

  test('should complete full sequence without getting stuck', async () => {
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
          onVideoEnd={onVideoEnd}
          onPlaybackComplete={onPlaybackComplete}
          autoStart={true}
        />
      </TestWrapper>
    );

    // Wait for initialization - check for control buttons
    await waitFor(() => {
      expect(screen.getByLabelText('Start/Resume Playback')).toBeInTheDocument();
    });

    // Simulate all videos ending in sequence
    for (let i = 0; i < testVideos.length; i++) {
      console.log(`🧪 Test: Simulating Video ${i + 1} ending`);
      
      act(() => {
        if (eventListeners['ended'] && eventListeners['ended'][0]) {
          eventListeners['ended'][0]({} as Event);
        }
      });

      // For the last video, expect completion
      if (i === testVideos.length - 1) {
        await waitFor(() => {
          expect(console.log).toHaveBeenCalledWith(
            expect.stringMatching(/🏁 Last video completed - finishing playback sequence/)
          );
        }, { timeout: 2000 });

        await waitFor(() => {
          expect(console.log).toHaveBeenCalledWith(
            expect.stringMatching(/🎬 Sequential playback completed - all videos finished/)
          );
        }, { timeout: 2000 });
      } else {
        // Expect transition to next video
        await waitFor(() => {
          expect(console.log).toHaveBeenCalledWith(
            expect.stringMatching(new RegExp(`🔄 transitionToVideo\\(${i + 1}\\) called`))
          );
        }, { timeout: 2000 });
      }

      // Small delay between videos
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 50));
      });
    }

    // Verify final completion
    expect(onPlaybackComplete).toHaveBeenCalled();
  });

  test('should handle hasHandledCurrentVideoEnd flag correctly', async () => {
    const onVideoEnd = jest.fn();

    render(
      <TestWrapper>
        <SequentialVideoPlayer
          videos={testVideos}
          config={{
            autoAdvance: true,
            loopPlayback: false,
          }}
          onVideoEnd={onVideoEnd}
          autoStart={true}
        />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Start/Resume Playback')).toBeInTheDocument();
    });

    // Trigger ended event multiple times to test deduplication
    act(() => {
      if (eventListeners['ended'] && eventListeners['ended'][0]) {
        eventListeners['ended'][0]({} as Event);
        eventListeners['ended'][0]({} as Event); // Duplicate
        eventListeners['ended'][0]({} as Event); // Duplicate
      }
    });

    // Should only process once due to hasHandledCurrentVideoEnd flag
    await waitFor(() => {
      const endedLogs = (console.log as jest.Mock).mock.calls.filter(call =>
        call[0] && call[0].includes('🏁 Video "ended"')
      );
      expect(endedLogs.length).toBe(1); // Should only be called once
    }, { timeout: 1000 });
  });
});