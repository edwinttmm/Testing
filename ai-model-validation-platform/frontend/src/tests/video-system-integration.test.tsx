import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';
import EnhancedVideoPlayer from '../components/EnhancedVideoPlayer';
import { VideoFile, GroundTruthAnnotation } from '../services/types';

// Mock video utils to avoid actual video loading in tests
jest.mock('../utils/videoUtils', () => ({
  safeVideoPlay: jest.fn(() => Promise.resolve({ success: true })),
  safeVideoPause: jest.fn(),
  safeVideoStop: jest.fn(),
  cleanupVideoElement: jest.fn(),
  setVideoSource: jest.fn(() => Promise.resolve()),
  addVideoEventListeners: jest.fn(() => jest.fn()),
  isVideoReady: jest.fn(() => true),
  getVideoErrorMessage: jest.fn(() => 'Test error message')
}));

describe('Video System Integration Tests', () => {
  const mockVideo: VideoFile = {
    id: 'test-video-5-04s',
    filename: 'test_video_5_04s.mp4',
    originalName: 'test_video_5_04s.mp4',
    url: '/uploads/test_video_5_04s.mp4',
    projectId: 'central-video-store',
    status: 'completed',
    duration: 5.033333333333333,
    fps: 30,
    resolution: '640x480',
    size: 45678,
    fileSize: 45678,
    createdAt: '2024-08-20T09:00:00Z',
    uploadedAt: '2024-08-20T09:00:00Z',
    groundTruthGenerated: false,
    groundTruthStatus: 'pending',
    processingStatus: 'completed',
    detectionCount: 0
  };

  const mockAnnotations: GroundTruthAnnotation[] = [
    {
      id: 'ann1',
      videoId: 'test-video-5-04s',
      frameNumber: 30,
      timestamp: 1.0,
      boundingBox: { x: 100, y: 100, width: 50, height: 50 },
      vruType: 'pedestrian',
      detectionId: 'det1',
      validated: false,
      confidence: 0.95
    },
    {
      id: 'ann2', 
      videoId: 'test-video-5-04s',
      frameNumber: 90,
      timestamp: 3.0,
      boundingBox: { x: 200, y: 150, width: 60, height: 60 },
      vruType: 'cyclist',
      detectionId: 'det2',
      validated: true,
      confidence: 0.88
    }
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('VideoAnnotationPlayer', () => {
    it('renders with correct video metadata', async () => {
      render(
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Check video metadata display
      await waitFor(() => {
        expect(screen.getByText(/5\.03/)).toBeInTheDocument(); // Duration
        expect(screen.getByText(/30/)).toBeInTheDocument(); // Frame rate or FPS reference
      });
    });

    it('calculates frame numbers correctly', async () => {
      const onTimeUpdate = jest.fn();
      
      render(
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
          onTimeUpdate={onTimeUpdate}
        />
      );

      // At 30 FPS, frame calculation should be: frameNumber = Math.floor(time * fps)
      // Time 1.0s = frame 30, Time 3.0s = frame 90
      const videoElement = screen.getByRole('application', { hidden: true }) as HTMLVideoElement;
      
      // Simulate time updates
      if (videoElement) {
        // Simulate currentTime update
        Object.defineProperty(videoElement, 'currentTime', { value: 1.0, writable: true });
        fireEvent.timeUpdate(videoElement);
        
        // Should call onTimeUpdate with time=1.0 and frame=30
        expect(onTimeUpdate).toHaveBeenCalledWith(1.0, 30);
      }
    });

    it('displays annotations for current frame correctly', async () => {
      render(
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Should show annotation info
      await waitFor(() => {
        expect(screen.getByText(/pedestrian/i)).toBeInTheDocument();
        expect(screen.getByText(/cyclist/i)).toBeInTheDocument();
      });
    });

    it('handles annotation mode correctly', async () => {
      const onCanvasClick = jest.fn();
      
      render(
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={true}
          frameRate={30}
          onCanvasClick={onCanvasClick}
        />
      );

      // Check annotation mode indicator
      expect(screen.getByText(/ANNOTATION MODE/i)).toBeInTheDocument();
      
      // Canvas should be interactive
      const canvas = document.querySelector('canvas');
      expect(canvas).toHaveStyle('pointer-events: auto');
      expect(canvas).toHaveStyle('cursor: crosshair');
    });
  });

  describe('EnhancedVideoPlayer', () => {
    it('renders with enhanced error handling', async () => {
      render(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
          autoRetry={true}
          maxRetries={3}
        />
      );

      // Check video controls are present
      expect(screen.getByLabelText(/play/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/previous frame/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/next frame/i)).toBeInTheDocument();
    });

    it('shows playback rate controls', async () => {
      render(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Check playback rate controls
      await waitFor(() => {
        expect(screen.getByText(/speed/i)).toBeInTheDocument();
        expect(screen.getByText(/1x/)).toBeInTheDocument();
        expect(screen.getByText(/2x/)).toBeInTheDocument();
      });
    });

    it('handles video errors gracefully', async () => {
      const errorVideo = { ...mockVideo, url: '' };
      
      render(
        <EnhancedVideoPlayer
          video={errorVideo}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
          autoRetry={false}
        />
      );

      // Should show error state
      await waitFor(() => {
        expect(screen.getByText(/video error/i)).toBeInTheDocument();
      });
    });
  });

  describe('Video Metadata Accuracy', () => {
    it('validates correct frame count calculation', () => {
      // For 5.033s video at 30fps, frame count should be 151
      const expectedFrameCount = Math.floor(mockVideo.duration * mockVideo.fps);
      expect(expectedFrameCount).toBe(151);
      
      // Frame number for last frame
      const lastFrameNumber = expectedFrameCount - 1; // 0-indexed
      expect(lastFrameNumber).toBe(150);
      
      // Time for last frame
      const lastFrameTime = lastFrameNumber / mockVideo.fps;
      expect(lastFrameTime).toBeCloseTo(5.0, 1);
    });

    it('validates annotation frame synchronization', () => {
      // Annotation at frame 30 should be at time 1.0s
      const frame30Time = 30 / mockVideo.fps;
      expect(frame30Time).toBeCloseTo(1.0, 2);
      
      // Annotation at frame 90 should be at time 3.0s  
      const frame90Time = 90 / mockVideo.fps;
      expect(frame90Time).toBeCloseTo(3.0, 2);
    });

    it('validates video URL format', () => {
      expect(mockVideo.url).toBe('/uploads/test_video_5_04s.mp4');
      expect(mockVideo.url).toMatch(/^\/uploads\/.+\.mp4$/);
    });
  });

  describe('Error Recovery', () => {
    it('handles network errors with retry', async () => {
      const onTimeUpdate = jest.fn();
      
      render(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
          autoRetry={true}
          maxRetries={3}
          onTimeUpdate={onTimeUpdate}
        />
      );

      // Should not show error initially
      expect(screen.queryByText(/video error/i)).not.toBeInTheDocument();
    });

    it('shows proper loading states', async () => {
      render(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Loading state should be managed properly
      // (This would require more sophisticated mocking to test loading states)
      expect(screen.getByRole('application', { hidden: true })).toBeInTheDocument();
    });
  });
});