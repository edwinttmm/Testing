/**
 * Video Lifecycle Events Integration Test
 *
 * Tests that video player components correctly emit VIDEO_STARTED and VIDEO_ENDED
 * events with proper timestamp synchronization.
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react';
import HILVideoPlayer from '../components/HILVideoPlayer';
import { clockSyncService } from '../services/clockSyncService';
import websocketService from '../services/websocketService';
import { VideoFile, DetectionOutcome } from '../services/types';

// Mock services
jest.mock('../services/clockSyncService');
jest.mock('../services/websocketService');

describe('Video Lifecycle Events Integration', () => {
  const mockClockSyncService = clockSyncService as jest.Mocked<typeof clockSyncService>;
  const mockWebSocketService = websocketService as jest.Mocked<typeof websocketService>;

  const mockVideoPlaylist: VideoFile[] = [
    {
      id: 'test-video-1',
      filename: 'test-video-1.mp4',
      filePath: '/uploads/test-video-1.mp4',
      url: 'http://localhost:8000/uploads/test-video-1.mp4',
      duration: 5.0,
      originalName: 'test-video-1.mp4',
      uploadDate: new Date().toISOString(),
    },
  ];

  const mockDetectionEvents = [];

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Mock clock sync service
    mockClockSyncService.synchronize = jest.fn().mockResolvedValue(10.5);
    mockClockSyncService.getSynchronizedTime = jest.fn().mockReturnValue(1703119711531);
    mockClockSyncService.getOffset = jest.fn().mockReturnValue(10.5);
    mockClockSyncService.isDriftAcceptable = jest.fn().mockReturnValue(true);
    mockClockSyncService.autoSyncIfNeeded = jest.fn().mockResolvedValue(undefined);

    // Mock WebSocket service
    mockWebSocketService.isConnected = true;
    mockWebSocketService.emit = jest.fn().mockReturnValue(true);
  });

  describe('HILVideoPlayer', () => {
    it('should initialize clock sync when test starts', async () => {
      const { rerender } = render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={false}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={jest.fn()}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      // Clock sync should not be called yet
      expect(mockClockSyncService.synchronize).not.toHaveBeenCalled();

      // Start test
      rerender(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={jest.fn()}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      // Wait for clock sync to be called
      await waitFor(() => {
        expect(mockClockSyncService.synchronize).toHaveBeenCalledTimes(1);
      });
    });

    it('should emit VIDEO_STARTED event when video starts playing', async () => {
      const onVideoStart = jest.fn();

      const { container } = render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={jest.fn()}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
          onVideoStart={onVideoStart}
        />
      );

      // Get video element
      const videoElement = container.querySelector('video');
      expect(videoElement).toBeTruthy();

      if (videoElement) {
        // Simulate video playing
        const playEvent = new Event('play');
        videoElement.dispatchEvent(playEvent);

        // Wait for WebSocket emit to be called
        await waitFor(() => {
          expect(mockWebSocketService.emit).toHaveBeenCalledWith(
            'video-lifecycle',
            expect.objectContaining({
              event: 'VIDEO_STARTED',
              videoId: 'test-video-1',
              timestamp: 1703119711531,
              clockOffset: 10.5,
              videoIndex: 0,
            })
          );
        });
      }
    });

    it('should emit VIDEO_ENDED event when video ends', async () => {
      const onVideoEnd = jest.fn();

      const { container } = render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={onVideoEnd}
          onVideoError={jest.fn()}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      // Get video element
      const videoElement = container.querySelector('video') as HTMLVideoElement;
      expect(videoElement).toBeTruthy();

      if (videoElement) {
        // Mock video duration
        Object.defineProperty(videoElement, 'currentTime', {
          writable: true,
          value: 5.0,
        });

        // Simulate video ended
        const endedEvent = new Event('ended');
        videoElement.dispatchEvent(endedEvent);

        // Wait for WebSocket emit to be called
        await waitFor(() => {
          expect(mockWebSocketService.emit).toHaveBeenCalledWith(
            'video-lifecycle',
            expect.objectContaining({
              event: 'VIDEO_ENDED',
              videoId: 'test-video-1',
              timestamp: 1703119711531,
              duration: 5.0,
              clockOffset: 10.5,
              videoIndex: 0,
            })
          );
        });

        expect(onVideoEnd).toHaveBeenCalledTimes(1);
      }
    });

    it('should emit VIDEO_ERROR event on video error', async () => {
      const onVideoError = jest.fn();

      const { container } = render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={onVideoError}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      // Get video element
      const videoElement = container.querySelector('video') as HTMLVideoElement;
      expect(videoElement).toBeTruthy();

      if (videoElement) {
        // Mock video error
        Object.defineProperty(videoElement, 'error', {
          writable: true,
          value: {
            code: MediaError.MEDIA_ERR_NETWORK,
            message: 'Network error',
          },
        });

        // Simulate video error
        const errorEvent = new Event('error');
        videoElement.dispatchEvent(errorEvent);

        // Wait for WebSocket emit to be called
        await waitFor(() => {
          expect(mockWebSocketService.emit).toHaveBeenCalledWith(
            'video-lifecycle',
            expect.objectContaining({
              event: 'VIDEO_ERROR',
              videoId: 'test-video-1',
              timestamp: 1703119711531,
              error: 'Network error occurred while loading video',
              errorCode: MediaError.MEDIA_ERR_NETWORK,
              videoIndex: 0,
            })
          );
        });

        expect(onVideoError).toHaveBeenCalledWith(
          expect.stringContaining('Network error occurred while loading video')
        );
      }
    });

    it('should warn if WebSocket is not connected', async () => {
      // Mock WebSocket disconnected
      mockWebSocketService.isConnected = false;

      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

      const { container } = render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={jest.fn()}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      const videoElement = container.querySelector('video');

      if (videoElement) {
        // Simulate video playing
        const playEvent = new Event('play');
        videoElement.dispatchEvent(playEvent);

        // Wait for warning
        await waitFor(() => {
          expect(consoleWarnSpy).toHaveBeenCalledWith(
            expect.stringContaining('WebSocket not connected')
          );
        });

        // Emit should not be called
        expect(mockWebSocketService.emit).not.toHaveBeenCalled();
      }

      consoleWarnSpy.mockRestore();
    });

    it('should include clock offset in all lifecycle events', async () => {
      const { container } = render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={jest.fn()}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      const videoElement = container.querySelector('video') as HTMLVideoElement;

      if (videoElement) {
        // Simulate video playing
        const playEvent = new Event('play');
        videoElement.dispatchEvent(playEvent);

        await waitFor(() => {
          expect(mockWebSocketService.emit).toHaveBeenCalledWith(
            'video-lifecycle',
            expect.objectContaining({
              clockOffset: 10.5,
            })
          );
        });

        // Simulate video ended
        Object.defineProperty(videoElement, 'currentTime', { value: 5.0 });
        const endedEvent = new Event('ended');
        videoElement.dispatchEvent(endedEvent);

        await waitFor(() => {
          const calls = mockWebSocketService.emit.mock.calls.filter(
            (call) => call[0] === 'video-lifecycle' && call[1].event === 'VIDEO_ENDED'
          );
          expect(calls.length).toBeGreaterThan(0);
          expect(calls[0][1]).toMatchObject({
            clockOffset: 10.5,
          });
        });
      }
    });
  });

  describe('Clock Synchronization', () => {
    it('should re-sync clock every 30 seconds during test', async () => {
      jest.useFakeTimers();

      render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={jest.fn()}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      // Wait for initial sync
      await waitFor(() => {
        expect(mockClockSyncService.synchronize).toHaveBeenCalledTimes(1);
      });

      // Fast-forward 30 seconds
      jest.advanceTimersByTime(30000);

      // Check that autoSyncIfNeeded was called
      await waitFor(() => {
        expect(mockClockSyncService.autoSyncIfNeeded).toHaveBeenCalled();
      });

      jest.useRealTimers();
    });

    it('should handle clock sync failures gracefully', async () => {
      // Mock clock sync failure
      mockClockSyncService.synchronize = jest.fn().mockRejectedValue(new Error('Sync failed'));

      const onVideoError = jest.fn();

      render(
        <HILVideoPlayer
          videoPlaylist={mockVideoPlaylist}
          currentVideoIndex={0}
          testInProgress={true}
          isFullScreen={false}
          detectionEvents={mockDetectionEvents}
          maxLatencyMs={100}
          onVideoEnd={jest.fn()}
          onVideoError={onVideoError}
          onNextVideo={jest.fn()}
          onPreviousVideo={jest.fn()}
          onToggleFullScreen={jest.fn()}
        />
      );

      // Wait for error callback
      await waitFor(() => {
        expect(onVideoError).toHaveBeenCalledWith(
          expect.stringContaining('Clock sync failed')
        );
      });
    });
  });
});
