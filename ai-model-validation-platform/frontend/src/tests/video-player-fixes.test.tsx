/**
 * Comprehensive Test Suite for Video Player Fixes
 * Tests video error handling, cleanup, and play/pause operations
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';
import { useVideoPlayer } from '../hooks/useVideoPlayer';
import {
  safeVideoPlay,
  safeVideoPause,
  cleanupVideoElement,
  setVideoSource,
  isVideoReady,
} from '../utils/videoUtils';

// Mock video data
const mockVideo = {
  id: 'test-video-1',
  filename: 'test-video.mp4',
  url: 'https://example.com/test-video.mp4',
  duration: 60,
  size: 1024 * 1024,
  status: 'completed' as const,
  createdAt: new Date().toISOString(),
};

const mockAnnotations = [
  {
    id: 'annotation-1',
    videoId: 'test-video-1',
    frameNumber: 30,
    timestamp: 1.0,
    vruType: 'pedestrian' as const,
    detectionId: 'det-001',
    boundingBox: {
      x: 100,
      y: 100,
      width: 50,
      height: 100,
      confidence: 0.95,
    },
    validated: true,
    difficult: false,
  },
];

// Mock HTMLVideoElement methods
const mockVideoElement = {
  play: jest.fn(),
  pause: jest.fn(),
  load: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  currentTime: 0,
  duration: 60,
  paused: true,
  videoWidth: 640,
  videoHeight: 480,
  src: '',
  volume: 1,
  muted: false,
  readyState: HTMLMediaElement.HAVE_METADATA,
  error: null,
  removeAttribute: jest.fn(),
};

describe('Video Player Fixes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockVideoElement.play.mockResolvedValue(undefined);
    mockVideoElement.paused = true;
    mockVideoElement.currentTime = 0;
    mockVideoElement.error = null;
  });

  afterEach(() => {
    cleanup();
  });

  describe('Video Utilities', () => {
    test('safeVideoPlay handles successful play', async () => {
      const result = await safeVideoPlay(mockVideoElement as any);
      
      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
      expect(mockVideoElement.play).toHaveBeenCalledTimes(1);
    });

    test('safeVideoPlay handles play() rejection', async () => {
      const playError = new Error('NotAllowedError: play() failed');
      mockVideoElement.play.mockRejectedValueOnce(playError);
      
      const result = await safeVideoPlay(mockVideoElement as any);
      
      expect(result.success).toBe(false);
      expect(result.error).toBe(playError);
    });

    test('safeVideoPlay handles null video element', async () => {
      const result = await safeVideoPlay(null);
      
      expect(result.success).toBe(false);
      expect(result.error?.message).toBe('Video element not available');
    });

    test('cleanupVideoElement properly cleans up', () => {
      mockVideoElement.paused = false;
      mockVideoElement.src = 'https://example.com/video.mp4';
      
      cleanupVideoElement(mockVideoElement as any);
      
      expect(mockVideoElement.pause).toHaveBeenCalled();
      expect(mockVideoElement.removeAttribute).toHaveBeenCalledWith('src');
      expect(mockVideoElement.src).toBe('');
      expect(mockVideoElement.load).toHaveBeenCalled();
    });

    test('isVideoReady detects ready video', () => {
      const readyVideo = {
        readyState: HTMLMediaElement.HAVE_METADATA,
        duration: 60,
        videoWidth: 640,
        videoHeight: 480,
      };
      
      expect(isVideoReady(readyVideo as any)).toBe(true);
    });
  });
});