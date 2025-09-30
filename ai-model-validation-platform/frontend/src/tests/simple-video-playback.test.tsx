/**
 * Simple Video Playback System - Test
 * 
 * Tests the new simplified video playback system to ensure it works correctly
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

import { SequentialVideoPlaybackSystem } from '../utils/sequentialVideoPlaybackSystem';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { VideoFile } from '../services/types';

// Mock video files for testing
const mockVideos: VideoFile[] = [
  {
    id: 'test-1',
    projectId: 'test-project',
    filename: 'test1.mp4',
    name: 'Test Video 1',
    url: 'data:video/mp4;base64,AAAAHGZ0eXBpc29tAAACAGlzb21pc28ybXA0MQAAAAhmcmVlAAAAIG1kYXQAAAKgBgX//wzcRem95tlIt5Ys2CDZI+7veDI=',
    duration: 10,
    size: 1000,
    fileSize: 1000,
    filePath: '/test1.mp4',
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
    id: 'test-2',
    projectId: 'test-project',
    filename: 'test2.mp4',
    name: 'Test Video 2',
    url: 'data:video/mp4;base64,AAAAHGZ0eXBpc29tAAACAGlzb21pc28ybXA0MQAAAAhmcmVlAAAAIG1kYXQAAAKgBgX//wzcRem95tlIt5Ys2CDZI+7veDI=',
    duration: 15,
    size: 1500,
    fileSize: 1500,
    filePath: '/test2.mp4',
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
    id: 'test-3',
    projectId: 'test-project',
    filename: 'test3.mp4',
    name: 'Test Video 3',
    url: 'data:video/mp4;base64,AAAAHGZ0eXBpc29tAAACAGlzb21pc28ybXA0MQAAAAhmcmVlAAAAIG1kYXQAAAKgBgX//wzcRem95tlIt5Ys2CDZI+7veDI=',
    duration: 20,
    size: 2000,
    fileSize: 2000,
    filePath: '/test3.mp4',
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

describe('Simple Video Playback System', () => {
  beforeAll(() => {
    // Mock HTMLVideoElement methods
    Object.defineProperty(HTMLVideoElement.prototype, 'play', {
      writable: true,
      value: jest.fn().mockImplementation(() => Promise.resolve()),
    });
    
    Object.defineProperty(HTMLVideoElement.prototype, 'pause', {
      writable: true,
      value: jest.fn(),
    });
    
    Object.defineProperty(HTMLVideoElement.prototype, 'load', {
      writable: true,
      value: jest.fn(),
    });
    
    Object.defineProperty(HTMLVideoElement.prototype, 'readyState', {
      writable: true,
      value: 4, // HAVE_ENOUGH_DATA
    });
    
    Object.defineProperty(HTMLVideoElement.prototype, 'duration', {
      writable: true,
      value: 10,
    });
    
    Object.defineProperty(HTMLVideoElement.prototype, 'currentTime', {
      writable: true,
      value: 0,
    });
  });

  test('SequentialVideoPlaybackSystem initializes correctly', () => {
    const container = document.createElement('div');
    const callbacks = {
      onVideoStart: jest.fn(),
      onVideoEnd: jest.fn(),
      onPlaybackComplete: jest.fn(),
      onVideoError: jest.fn(),
      onProgressUpdate: jest.fn(),
      onStateChange: jest.fn(),
    };

    const system = new SequentialVideoPlaybackSystem(container, callbacks);
    
    expect(system).toBeInstanceOf(SequentialVideoPlaybackSystem);
    expect(system.getState()).toEqual({
      currentIndex: 0,
      isPlaying: false,
      isTransitioning: false,
      videos: [],
      totalProgress: 0,
      errors: []
    });
    
    system.destroy();
  });

  test('SequentialVideoPlaybackSystem loads video queue', async () => {
    const container = document.createElement('div');
    const callbacks = {
      onVideoStart: jest.fn(),
      onVideoEnd: jest.fn(),
      onPlaybackComplete: jest.fn(),
      onVideoError: jest.fn(),
      onProgressUpdate: jest.fn(),
      onStateChange: jest.fn(),
    };

    const system = new SequentialVideoPlaybackSystem(container, callbacks);
    
    await system.loadVideoQueue(mockVideos);
    
    const state = system.getState();
    expect(state.videos).toEqual(mockVideos);
    expect(state.currentIndex).toBe(0);
    expect(callbacks.onStateChange).toHaveBeenCalled();
    
    system.destroy();
  });

  test('SequentialVideoPlayer component renders correctly', () => {
    const onVideoStart = jest.fn();
    const onVideoEnd = jest.fn();
    const onPlaybackComplete = jest.fn();

    render(
      <SequentialVideoPlayer
        videos={mockVideos}
        onVideoStart={onVideoStart}
        onVideoEnd={onVideoEnd}
        onPlaybackComplete={onPlaybackComplete}
        showControls={true}
        showProgress={true}
      />
    );

    // Check that the component renders
    expect(screen.getByText(/Sequential Playback Progress/i)).toBeInTheDocument();
    
    // Check that play button is present
    const playButton = screen.getByRole('button', { name: /start.*playback/i });
    expect(playButton).toBeInTheDocument();
  });

  test('SequentialVideoPlayer shows video information', async () => {
    render(
      <SequentialVideoPlayer
        videos={mockVideos}
        showControls={true}
        showProgress={true}
      />
    );

    // Wait for component to initialize
    await waitFor(() => {
      expect(screen.getByText(/Ready to play 3 videos/i)).toBeInTheDocument();
    });
    
    // Check progress information
    expect(screen.getByText(/0% Complete/i)).toBeInTheDocument();
  });

  test('SequentialVideoPlayer handles play button click', async () => {
    const user = userEvent.setup();
    const onVideoStart = jest.fn();

    render(
      <SequentialVideoPlayer
        videos={mockVideos}
        onVideoStart={onVideoStart}
        showControls={true}
      />
    );

    const playButton = screen.getByRole('button', { name: /start.*playback/i });
    await user.click(playButton);

    // Should show loading state
    await waitFor(() => {
      expect(screen.getByText(/Starting sequential playback/i)).toBeInTheDocument();
    });
  });

  test('Simple video queue management', async () => {
    const container = document.createElement('div');
    let currentState = null;
    
    const callbacks = {
      onVideoStart: jest.fn(),
      onVideoEnd: jest.fn(),
      onPlaybackComplete: jest.fn(),
      onVideoError: jest.fn(),
      onProgressUpdate: jest.fn(),
      onStateChange: (state) => {
        currentState = state;
      },
    };

    const system = new SequentialVideoPlaybackSystem(container, callbacks);
    
    // Load videos
    await system.loadVideoQueue(mockVideos);
    expect(currentState.videos.length).toBe(3);
    expect(currentState.currentIndex).toBe(0);
    
    // Get current video
    const currentVideo = system.getCurrentVideo();
    expect(currentVideo).toEqual(mockVideos[0]);
    expect(currentVideo.filename).toBe('test1.mp4');
    
    system.destroy();
  });

  test('Video state management', () => {
    const container = document.createElement('div');
    const system = new SequentialVideoPlaybackSystem(container, {});
    
    // Initial state
    const state = system.getState();
    expect(state.isPlaying).toBe(false);
    expect(state.isTransitioning).toBe(false);
    expect(state.currentIndex).toBe(0);
    expect(state.videos).toEqual([]);
    expect(state.totalProgress).toBe(0);
    expect(state.errors).toEqual([]);
    
    system.destroy();
  });

  test('Error handling', async () => {
    const container = document.createElement('div');
    const onVideoError = jest.fn();
    
    const callbacks = {
      onVideoError,
      onStateChange: jest.fn(),
    };

    const system = new SequentialVideoPlaybackSystem(container, callbacks);
    
    // Test with invalid video (should trigger error handling)
    const invalidVideo: VideoFile = {
      ...mockVideos[0],
      url: '', // Invalid URL
    };
    
    await system.loadVideoQueue([invalidVideo]);
    
    // Try to start playback - should handle error gracefully
    try {
      await system.startPlayback();
    } catch (error) {
      // Errors should be handled internally
    }
    
    system.destroy();
  });
});

console.log('✅ Simple video playback system tests loaded');