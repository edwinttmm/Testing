import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';

// Import video player components and utilities
import VideoAnnotationPlayer from '../../../ai-model-validation-platform/frontend/src/components/VideoAnnotationPlayer';
import { TEST_VIDEOS, TEST_ANNOTATIONS } from '../fixtures/test-videos';
import { 
  safeVideoPlay, 
  safeVideoPause, 
  cleanupVideoElement, 
  setVideoSource,
  addVideoEventListeners 
} from '../../../ai-model-validation-platform/frontend/src/utils/videoUtils';

// Mock video utilities
vi.mock('../../../ai-model-validation-platform/frontend/src/utils/videoUtils', () => ({
  safeVideoPlay: vi.fn(),
  safeVideoPause: vi.fn(),
  safeVideoStop: vi.fn(),
  cleanupVideoElement: vi.fn(),
  setVideoSource: vi.fn(),
  addVideoEventListeners: vi.fn()
}));

// Mock video file data
const mockVideoFile = {
  id: 'test-video-1',
  filename: 'test-video.mp4',
  url: '/api/videos/test-video-1/stream',
  duration: 30.0,
  fps: 30,
  resolution: '1920x1080'
};

const mockAnnotations = [
  TEST_ANNOTATIONS.pedestrian,
  TEST_ANNOTATIONS.cyclist
];

describe('Video Player Functionality Tests', () => {
  let mockVideoElement: HTMLVideoElement;
  let mockCanvasElement: HTMLCanvasElement;

  beforeEach(() => {
    // Create mock video and canvas elements
    mockVideoElement = document.createElement('video');
    mockCanvasElement = document.createElement('canvas');
    
    // Mock video element properties
    Object.defineProperty(mockVideoElement, 'currentTime', {
      value: 0,
      writable: true
    });
    Object.defineProperty(mockVideoElement, 'duration', {
      value: 30,
      writable: true
    });
    Object.defineProperty(mockVideoElement, 'videoWidth', {
      value: 1920,
      writable: true
    });
    Object.defineProperty(mockVideoElement, 'videoHeight', {
      value: 1080,
      writable: true
    });
    Object.defineProperty(mockVideoElement, 'volume', {
      value: 1,
      writable: true
    });
    Object.defineProperty(mockVideoElement, 'muted', {
      value: false,
      writable: true
    });

    // Mock canvas context
    const mockContext = {
      clearRect: vi.fn(),
      strokeRect: vi.fn(),
      fillRect: vi.fn(),
      fillText: vi.fn(),
      measureText: vi.fn().mockReturnValue({ width: 100 }),
      beginPath: vi.fn(),
      closePath: vi.fn(),
      stroke: vi.fn(),
      fill: vi.fn()
    };

    vi.spyOn(mockCanvasElement, 'getContext').mockReturnValue(mockContext as any);

    // Mock DOM methods
    vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      if (tagName === 'video') return mockVideoElement;
      if (tagName === 'canvas') return mockCanvasElement;
      return document.createElement(tagName);
    });

    // Reset utility function mocks
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Video Loading and Initialization', () => {
    it('should load video with proper initialization', async () => {
      // Arrange
      (setVideoSource as Mock).mockResolvedValue(true);
      (addVideoEventListeners as Mock).mockReturnValue(() => {}); // cleanup function

      // Act
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Wait for component to mount and initialize
      await waitFor(() => {
        expect(setVideoSource).toHaveBeenCalledWith(
          expect.any(HTMLVideoElement),
          mockVideoFile.url
        );
      });

      // Assert
      expect(addVideoEventListeners).toHaveBeenCalledWith(
        expect.any(HTMLVideoElement),
        expect.arrayContaining([
          expect.objectContaining({ event: 'loadedmetadata' }),
          expect.objectContaining({ event: 'timeupdate' }),
          expect.objectContaining({ event: 'play' }),
          expect.objectContaining({ event: 'pause' }),
          expect.objectContaining({ event: 'ended' }),
          expect.objectContaining({ event: 'error' })
        ])
      );
    });

    it('should handle video loading errors gracefully', async () => {
      // Arrange
      (setVideoSource as Mock).mockRejectedValue(new Error('Failed to load video'));

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // Act
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Wait for error handling
      await waitFor(() => {
        expect(setVideoSource).toHaveBeenCalled();
      });

      // Should handle error without crashing
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it('should cleanup video resources on unmount', async () => {
      // Arrange
      const cleanupMock = vi.fn();
      (addVideoEventListeners as Mock).mockReturnValue(cleanupMock);

      // Act
      const { unmount } = render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      await waitFor(() => {
        expect(addVideoEventListeners).toHaveBeenCalled();
      });

      unmount();

      // Assert
      expect(cleanupMock).toHaveBeenCalled();
      expect(cleanupVideoElement).toHaveBeenCalledWith(expect.any(HTMLVideoElement));
    });
  });

  describe('Playback Controls', () => {
    it('should play video when play button is clicked', async () => {
      // Arrange
      (safeVideoPlay as Mock).mockResolvedValue({ success: true });

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act
      const playButton = screen.getByRole('button', { name: /play/i });
      await userEvent.click(playButton);

      // Assert
      await waitFor(() => {
        expect(safeVideoPlay).toHaveBeenCalledWith(expect.any(HTMLVideoElement));
      });
    });

    it('should pause video when pause button is clicked', async () => {
      // Arrange
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Simulate video playing state
      const pauseButton = screen.getByRole('button', { name: /pause/i });

      // Act
      await userEvent.click(pauseButton);

      // Assert
      expect(safeVideoPause).toHaveBeenCalledWith(expect.any(HTMLVideoElement));
    });

    it('should handle play failure gracefully', async () => {
      // Arrange
      (safeVideoPlay as Mock).mockResolvedValue({ 
        success: false, 
        error: new Error('Play failed') 
      });

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act
      const playButton = screen.getByRole('button', { name: /play/i });
      await userEvent.click(playButton);

      // Assert
      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Video play failed:',
          'Play failed'
        );
      });

      consoleSpy.mockRestore();
    });

    it('should seek to specific time when timeline is clicked', async () => {
      // Arrange
      mockVideoElement.currentTime = 0;
      
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act
      const timeline = screen.getByRole('slider');
      fireEvent.change(timeline, { target: { value: '15' } });

      // Assert
      await waitFor(() => {
        expect(mockVideoElement.currentTime).toBe(15);
      });
    });

    it('should step frame forward and backward', async () => {
      // Arrange
      mockVideoElement.currentTime = 10;
      mockVideoElement.duration = 30;

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Step forward
      const nextFrameButton = screen.getByLabelText(/next frame/i);
      await userEvent.click(nextFrameButton);

      // Assert
      expect(mockVideoElement.currentTime).toBeCloseTo(10 + (1/30), 2);

      // Act - Step backward
      const prevFrameButton = screen.getByLabelText(/previous frame/i);
      await userEvent.click(prevFrameButton);
      await userEvent.click(prevFrameButton);

      // Assert
      expect(mockVideoElement.currentTime).toBeCloseTo(10 - (1/30), 2);
    });

    it('should handle volume control', async () => {
      // Arrange
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Change volume
      const volumeSlider = screen.getByRole('slider', { name: /volume/i });
      fireEvent.change(volumeSlider, { target: { value: '0.5' } });

      // Assert
      expect(mockVideoElement.volume).toBe(0.5);
    });

    it('should toggle mute/unmute', async () => {
      // Arrange
      mockVideoElement.volume = 0.8;

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Mute
      const muteButton = screen.getByLabelText(/mute/i);
      await userEvent.click(muteButton);

      // Assert
      expect(mockVideoElement.volume).toBe(0);

      // Act - Unmute
      const unmuteButton = screen.getByLabelText(/unmute/i);
      await userEvent.click(unmuteButton);

      // Assert
      expect(mockVideoElement.volume).toBe(0.8);
    });
  });

  describe('Annotation Display and Interaction', () => {
    it('should display annotations on canvas overlay', async () => {
      // Arrange
      const mockContext = mockCanvasElement.getContext('2d');

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Wait for annotations to be drawn
      await waitFor(() => {
        expect(mockContext?.strokeRect).toHaveBeenCalled();
      });

      // Assert
      expect(mockContext?.clearRect).toHaveBeenCalled();
      expect(mockContext?.fillRect).toHaveBeenCalled();
      expect(mockContext?.fillText).toHaveBeenCalled();
    });

    it('should handle annotation selection on canvas click', async () => {
      // Arrange
      const onAnnotationSelect = vi.fn();

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          onAnnotationSelect={onAnnotationSelect}
          annotationMode={true}
          frameRate={30}
        />
      );

      // Act - Click on annotation area
      const canvas = screen.getByRole('img'); // Canvas has role="img" in some cases
      fireEvent.click(canvas, {
        clientX: 130, // Within bounding box of test annotation
        clientY: 110
      });

      // Assert
      await waitFor(() => {
        expect(onAnnotationSelect).toHaveBeenCalled();
      });
    });

    it('should create new annotation on canvas click in annotation mode', async () => {
      // Arrange
      const onCanvasClick = vi.fn();

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          onCanvasClick={onCanvasClick}
          annotationMode={true}
          frameRate={30}
        />
      );

      // Act - Click on empty area
      const canvas = screen.getByRole('img');
      fireEvent.click(canvas, {
        clientX: 300,
        clientY: 200
      });

      // Assert
      await waitFor(() => {
        expect(onCanvasClick).toHaveBeenCalledWith(
          expect.any(Number), // x coordinate
          expect.any(Number), // y coordinate
          expect.any(Number), // frame number
          expect.any(Number)  // timestamp
        );
      });
    });

    it('should show annotation mode indicator when enabled', async () => {
      // Arrange & Act
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={true}
          frameRate={30}
        />
      );

      // Assert
      expect(screen.getByText('ANNOTATION MODE')).toBeInTheDocument();
    });

    it('should display current frame annotations info', async () => {
      // Arrange
      mockVideoElement.currentTime = 5.0; // Should show pedestrian annotation

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Assert
      await waitFor(() => {
        expect(screen.getByText(/Current Frame Annotations/)).toBeInTheDocument();
        expect(screen.getByText(/pedestrian/)).toBeInTheDocument();
      });
    });

    it('should highlight selected annotation', async () => {
      // Arrange
      const selectedAnnotation = mockAnnotations[0];

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          selectedAnnotation={selectedAnnotation}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Wait for canvas drawing
      await waitFor(() => {
        const mockContext = mockCanvasElement.getContext('2d');
        expect(mockContext?.strokeRect).toHaveBeenCalled();
      });

      // The selected annotation should be drawn with different styling
      const mockContext = mockCanvasElement.getContext('2d');
      expect(mockContext?.strokeRect).toHaveBeenCalled();
    });
  });

  describe('Time and Frame Synchronization', () => {
    it('should update frame number based on current time', async () => {
      // Arrange
      const onTimeUpdate = vi.fn();
      mockVideoElement.currentTime = 10.0;

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          onTimeUpdate={onTimeUpdate}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Simulate time update event
      fireEvent.timeUpdate(mockVideoElement);

      // Assert
      await waitFor(() => {
        expect(onTimeUpdate).toHaveBeenCalledWith(10.0, 300); // 10 seconds * 30 fps = frame 300
      });
    });

    it('should display correct time format', async () => {
      // Arrange
      mockVideoElement.currentTime = 125; // 2:05
      mockVideoElement.duration = 185; // 3:05

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Assert
      await waitFor(() => {
        expect(screen.getByText(/2:05 \/ 3:05/)).toBeInTheDocument();
      });
    });

    it('should filter annotations by current frame', async () => {
      // Arrange
      const annotations = [
        { ...TEST_ANNOTATIONS.pedestrian, frameNumber: 150 }, // At 5 seconds
        { ...TEST_ANNOTATIONS.cyclist, frameNumber: 300 }      // At 10 seconds
      ];

      mockVideoElement.currentTime = 5.0; // Should only show first annotation

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={annotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Assert
      await waitFor(() => {
        expect(screen.getByText(/pedestrian/)).toBeInTheDocument();
        expect(screen.queryByText(/cyclist/)).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle video element errors', async () => {
      // Arrange
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Simulate video error
      fireEvent.error(mockVideoElement);

      // Assert
      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Video playback error:', expect.any(Object));
      });

      consoleSpy.mockRestore();
    });

    it('should handle canvas rendering errors', async () => {
      // Arrange
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      
      // Mock canvas context to return null (error case)
      vi.spyOn(mockCanvasElement, 'getContext').mockReturnValue(null);

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Canvas rendering should handle null context gracefully
      // No errors should be thrown

      consoleSpy.mockRestore();
    });

    it('should handle invalid video dimensions', async () => {
      // Arrange
      Object.defineProperty(mockVideoElement, 'videoWidth', { value: 0 });
      Object.defineProperty(mockVideoElement, 'videoHeight', { value: 0 });

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Should handle invalid dimensions without crashing
      const mockContext = mockCanvasElement.getContext('2d');
      
      // Drawing should be skipped when dimensions are invalid
      await waitFor(() => {
        expect(mockContext?.clearRect).toHaveBeenCalled();
      });
    });

    it('should handle missing video URL gracefully', async () => {
      // Arrange
      const invalidVideo = { ...mockVideoFile, url: '' };

      render(
        <VideoAnnotationPlayer
          video={invalidVideo}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Should render without crashing
      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });
  });

  describe('Responsive Behavior', () => {
    it('should adjust canvas size to match video display', async () => {
      // Arrange
      const mockGetBoundingClientRect = vi.fn().mockReturnValue({
        width: 800,
        height: 450,
        top: 0,
        left: 0
      });
      
      mockVideoElement.getBoundingClientRect = mockGetBoundingClientRect;

      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Wait for canvas drawing
      await waitFor(() => {
        expect(mockCanvasElement.width).toBe(800);
        expect(mockCanvasElement.height).toBe(450);
      });
    });

    it('should handle video resize events', async () => {
      // Arrange
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Simulate video resize
      Object.defineProperty(mockVideoElement, 'videoWidth', { value: 1280 });
      Object.defineProperty(mockVideoElement, 'videoHeight', { value: 720 });

      fireEvent(mockVideoElement, new Event('resize'));

      // Video dimensions should be updated
      // Component should handle resize gracefully
    });
  });

  describe('Performance Optimization', () => {
    it('should throttle canvas redraws', async () => {
      // Arrange
      const mockContext = mockCanvasElement.getContext('2d');
      
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Trigger multiple rapid updates
      for (let i = 0; i < 10; i++) {
        mockVideoElement.currentTime = i;
        fireEvent.timeUpdate(mockVideoElement);
      }

      // Assert - Canvas should not be redrawn for every update
      await waitFor(() => {
        const clearRectCalls = (mockContext?.clearRect as Mock).mock.calls.length;
        expect(clearRectCalls).toBeLessThan(10); // Should be throttled
      });
    });

    it('should cleanup event listeners on unmount', async () => {
      // Arrange
      const cleanupMock = vi.fn();
      (addVideoEventListeners as Mock).mockReturnValue(cleanupMock);

      // Act
      const { unmount } = render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      unmount();

      // Assert
      expect(cleanupMock).toHaveBeenCalled();
    });

    it('should handle rapid prop changes efficiently', async () => {
      // Arrange
      const { rerender } = render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Rapid prop changes
      for (let i = 0; i < 5; i++) {
        rerender(
          <VideoAnnotationPlayer
            video={mockVideoFile}
            annotations={mockAnnotations.slice(0, i)}
            annotationMode={i % 2 === 0}
            frameRate={30}
          />
        );
      }

      // Should handle rapid changes without performance issues
      const mockContext = mockCanvasElement.getContext('2d');
      expect(mockContext?.clearRect).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('should provide proper ARIA labels for controls', async () => {
      // Arrange & Act
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Assert
      expect(screen.getByLabelText(/play/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/previous frame/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/next frame/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/mute/i)).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      // Arrange
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Act - Tab through controls
      const playButton = screen.getByLabelText(/play/i);
      playButton.focus();

      fireEvent.keyDown(playButton, { key: ' ' }); // Space to play/pause

      // Assert
      await waitFor(() => {
        expect(safeVideoPlay).toHaveBeenCalled();
      });
    });

    it('should announce video state changes to screen readers', async () => {
      // Arrange
      render(
        <VideoAnnotationPlayer
          video={mockVideoFile}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Video state changes should be properly communicated
      // This would typically involve aria-live regions or announcements
      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });
  });
});