/**
 * Bounding Box Positioning Fix Test
 * Verifies that bounding boxes are correctly positioned on video overlays
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import EnhancedVideoPlayer from '../components/EnhancedVideoPlayer';
import { VideoFile, GroundTruthAnnotation } from '../services/types';

// Mock video utils
jest.mock('../utils/videoUtils', () => ({
  safeVideoPlay: jest.fn().mockResolvedValue({ success: true }),
  safeVideoPause: jest.fn(),
  cleanupVideoElement: jest.fn(),
  setVideoSource: jest.fn().mockResolvedValue(undefined),
  addVideoEventListeners: jest.fn().mockReturnValue(jest.fn()),
  getVideoErrorMessage: jest.fn().mockReturnValue('Mock error'),
  isVideoReady: jest.fn().mockReturnValue(true),
}));

// Mock video URL fixer
jest.mock('../utils/videoUrlFixer', () => ({
  fixVideoUrl: jest.fn().mockReturnValue('http://example.com/test-video.mp4'),
}));

describe('Bounding Box Positioning Fix', () => {
  const mockVideo: VideoFile = {
    id: 'test-video-id',
    projectId: 'test-project-id',
    filename: 'test-video.mp4',
    fileSize: 1000000,
    url: 'http://example.com/test-video.mp4',
    duration: 30,
    fps: 30,
    resolution: '640x480',
    frameCount: 900,
    status: 'completed',
    processingStatus: 'completed',
    groundTruthGenerated: true,
    detectionCount: 0,
    annotationCount: 1,
    createdAt: '2024-01-01T00:00:00Z',
  };

  const mockAnnotations: GroundTruthAnnotation[] = [
    {
      id: 'ann-1',
      videoId: 'test-video-id',
      detectionId: 'det-1',
      frameNumber: 1,
      timestamp: 0.033,
      vruType: 'pedestrian',
      boundingBox: {
        x: 100,     // Native video coordinates (640x480)
        y: 150,     // Native video coordinates
        width: 80,  // Native video dimensions
        height: 120, // Native video dimensions
        confidence: 0.9,
        label: 'pedestrian'
      },
      occluded: false,
      truncated: false,
      difficult: false,
      validationStatus: 'validated',
      validated: true,
      createdAt: '2024-01-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    // Mock HTMLVideoElement properties
    Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {
      get: () => 640, // Native video width
    });
    Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {
      get: () => 480, // Native video height
    });
    Object.defineProperty(HTMLVideoElement.prototype, 'getBoundingClientRect', {
      value: () => ({
        width: 320,  // Displayed video width (50% scale)
        height: 240, // Displayed video height (50% scale)
        top: 0,
        left: 0,
        bottom: 240,
        right: 320,
      }),
    });
  });

  test('should correctly scale bounding box coordinates from native to display size', () => {
    // Mock canvas context
    const mockContext = {
      clearRect: jest.fn(),
      strokeRect: jest.fn(),
      fillRect: jest.fn(),
      fillText: jest.fn(),
      measureText: jest.fn().mockReturnValue({ width: 100 }),
      strokeStyle: '',
      lineWidth: 0,
      fillStyle: '',
      font: '',
    };

    const mockCanvas = {
      getContext: jest.fn().mockReturnValue(mockContext),
      width: 0,
      height: 0,
    };

    jest.spyOn(React, 'useRef').mockImplementation((initial) => {
      if (initial === null) {
        return { current: mockCanvas };
      }
      return { current: initial };
    });

    render(
      <EnhancedVideoPlayer
        video={mockVideo}
        annotations={mockAnnotations}
        annotationMode={false}
        frameRate={30}
      />
    );

    // Simulate video loaded
    const videoElement = document.querySelector('video');
    if (videoElement) {
      fireEvent(videoElement, new Event('loadedmetadata'));
      fireEvent(videoElement, new Event('canplay'));
    }

    // Check that bounding box is drawn with correct scaled coordinates
    expect(mockContext.strokeRect).toHaveBeenCalledWith(
      50,   // x: 100 * (320/640) = 50 (scaled to display size)
      75,   // y: 150 * (240/480) = 75 (scaled to display size)
      40,   // width: 80 * (320/640) = 40 (scaled to display size)
      60    // height: 120 * (240/480) = 60 (scaled to display size)
    );
  });

  test('should correctly convert click coordinates from display to native video coordinates', () => {
    const mockOnCanvasClick = jest.fn();
    
    render(
      <EnhancedVideoPlayer
        video={mockVideo}
        annotations={mockAnnotations}
        annotationMode={true}
        onCanvasClick={mockOnCanvasClick}
        frameRate={30}
      />
    );

    // Mock canvas getBoundingClientRect
    const mockCanvasElement = {
      getBoundingClientRect: () => ({
        width: 320,
        height: 240,
        top: 0,
        left: 0,
        bottom: 240,
        right: 320,
      }),
    };

    jest.spyOn(React, 'useRef').mockImplementation((initial) => {
      if (initial === null) {
        return { current: mockCanvasElement };
      }
      return { current: initial };
    });

    const canvas = screen.getByRole('img', { hidden: true }); // Canvas has img role when accessible
    
    // Click at display coordinates (160, 120) - center of displayed video
    fireEvent.click(canvas, {
      clientX: 160,
      clientY: 120,
    });

    // Should convert to native video coordinates: (160 * 640/320, 120 * 480/240) = (320, 240)
    expect(mockOnCanvasClick).toHaveBeenCalledWith(
      320, // Native x coordinate
      240, // Native y coordinate
      expect.any(Number), // frame number
      expect.any(Number)  // timestamp
    );
  });

  test('should handle edge cases with zero video dimensions', () => {
    // Mock video element with zero dimensions
    Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {
      get: () => 0,
    });
    Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {
      get: () => 0,
    });

    const mockContext = {
      clearRect: jest.fn(),
      strokeRect: jest.fn(),
      fillRect: jest.fn(),
      fillText: jest.fn(),
      measureText: jest.fn().mockReturnValue({ width: 100 }),
    };

    jest.spyOn(React, 'useRef').mockImplementation((initial) => {
      if (initial === null) {
        return { current: { getContext: () => mockContext, width: 0, height: 0 } };
      }
      return { current: initial };
    });

    render(
      <EnhancedVideoPlayer
        video={mockVideo}
        annotations={mockAnnotations}
        annotationMode={false}
        frameRate={30}
      />
    );

    // Should not draw annotations when video dimensions are zero
    expect(mockContext.strokeRect).not.toHaveBeenCalled();
  });

  test('should maintain aspect ratio when video is scaled', () => {
    // Test with different aspect ratio scaling
    Object.defineProperty(HTMLVideoElement.prototype, 'getBoundingClientRect', {
      value: () => ({
        width: 480,  // 3:4 aspect ratio (not matching native 4:3)
        height: 360,
        top: 0,
        left: 0,
        bottom: 360,
        right: 480,
      }),
    });

    const mockContext = {
      clearRect: jest.fn(),
      strokeRect: jest.fn(),
      fillRect: jest.fn(),
      fillText: jest.fn(),
      measureText: jest.fn().mockReturnValue({ width: 100 }),
      strokeStyle: '',
      lineWidth: 0,
      fillStyle: '',
      font: '',
    };

    jest.spyOn(React, 'useRef').mockImplementation((initial) => {
      if (initial === null) {
        return { current: { getContext: () => mockContext, width: 0, height: 0 } };
      }
      return { current: initial };
    });

    render(
      <EnhancedVideoPlayer
        video={mockVideo}
        annotations={mockAnnotations}
        annotationMode={false}
        frameRate={30}
      />
    );

    const videoElement = document.querySelector('video');
    if (videoElement) {
      fireEvent(videoElement, new Event('loadedmetadata'));
    }

    // Check scaling factors: x = 480/640 = 0.75, y = 360/480 = 0.75
    expect(mockContext.strokeRect).toHaveBeenCalledWith(
      75,   // x: 100 * 0.75
      112.5, // y: 150 * 0.75 
      60,   // width: 80 * 0.75
      90    // height: 120 * 0.75
    );
  });
});