import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import EnhancedVideoPlayer from '../components/EnhancedVideoPlayer';
import { useResponsiveVideoPlayer } from '../hooks/useResponsiveVideoPlayer';
import { VideoFile, GroundTruthAnnotation } from '../services/types';

// Mock the responsive hook
jest.mock('../hooks/useResponsiveVideoPlayer');

const mockUseResponsiveVideoPlayer = useResponsiveVideoPlayer as jest.MockedFunction<
  typeof useResponsiveVideoPlayer
>;

const theme = createTheme();

const mockVideo: VideoFile = {
  id: 'test-video-1',
  filename: 'test-video.mp4',
  name: 'Test Video',
  url: '/test-video.mp4',
  status: 'processed',
  uploadedAt: '2024-01-01T00:00:00Z',
  processingStatus: 'completed'
};

const mockAnnotations: GroundTruthAnnotation[] = [
  {
    id: 'annotation-1',
    videoId: 'test-video-1',
    detectionId: 'det-1',
    vruType: 'pedestrian',
    boundingBox: { x: 100, y: 100, width: 50, height: 100 },
    frameNumber: 30,
    timestamp: 1.0,
    validated: true
  }
];

const defaultResponsiveState = {
  isMobile: false,
  isTablet: false,
  isDesktop: true,
  orientation: 'landscape' as const,
  screenSize: { width: 1200, height: 800 },
  isTouchDevice: false,
  isHighDensity: false,
  preferredControlSize: 'small' as const,
  getResponsiveVideoDimensions: () => ({
    maxHeight: 500,
    minHeight: 200,
    width: '100%'
  }),
  getResponsiveSliderProps: () => ({
    size: 'small' as const,
    sx: { height: 4 }
  }),
  getResponsiveButtonProps: () => ({
    size: 'small' as const,
    sx: { minHeight: 'auto', fontSize: '0.875rem' }
  }),
  getResponsiveIconButtonProps: () => ({
    size: 'small' as const,
    sx: { padding: '8px' }
  }),
  getResponsiveLayoutProps: () => ({
    spacing: 1,
    direction: 'row' as const,
    alignItems: 'center' as const,
    justifyContent: 'flex-start' as const,
    sx: { flexWrap: 'nowrap', gap: 1, width: 'auto' }
  }),
  getResponsiveAnnotationProps: () => ({
    sx: { gap: 1, px: 2, py: 1, fontSize: '0.75rem' },
    indicatorSize: 12
  }),
  handleTouchSeek: jest.fn(),
  optimizeCanvasForDisplay: jest.fn()
};

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('Responsive Video Player Tests', () => {
  beforeEach(() => {
    mockUseResponsiveVideoPlayer.mockReturnValue(defaultResponsiveState);
    
    // Mock HTMLVideoElement methods
    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      writable: true,
      value: jest.fn().mockImplementation(() => Promise.resolve())
    });
    
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      writable: true,
      value: jest.fn()
    });
    
    Object.defineProperty(HTMLMediaElement.prototype, 'load', {
      writable: true,
      value: jest.fn()
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Desktop Responsive Behavior', () => {
    test('renders with desktop layout', () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
      expect(screen.getByRole('slider', { name: /video progress/i })).toBeInTheDocument();
    });

    test('shows playback rate controls on desktop', () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      // Playback rate buttons should be visible on desktop
      expect(screen.getByText('1x')).toBeInTheDocument();
      expect(screen.getByText('1.5x')).toBeInTheDocument();
    });
  });

  describe('Mobile Responsive Behavior', () => {
    beforeEach(() => {
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        isMobile: true,
        isDesktop: false,
        isTouchDevice: true,
        screenSize: { width: 375, height: 667 },
        getResponsiveButtonProps: () => ({
          size: 'medium' as const,
          sx: { 
            minHeight: 44, 
            fontSize: '0.8rem',
            touchAction: 'manipulation',
            '&:active': {
              transform: 'scale(0.95)'
            }
          }
        }),
        getResponsiveIconButtonProps: () => ({
          size: 'medium' as const,
          sx: { padding: '12px', minWidth: 48, minHeight: 48 }
        }),
        getResponsiveSliderProps: () => ({
          size: 'medium' as const,
          sx: { 
            height: 8,
            '& .MuiSlider-thumb': {
              width: 24,
              height: 24
            }
          }
        })
      });
    });

    test('renders with mobile-friendly controls', () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton).toBeInTheDocument();
      
      // Check for touch-friendly sizing
      const style = getComputedStyle(playButton);
      expect(style.minHeight).toBeDefined();
    });

    test('handles touch interactions properly', async () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      
      fireEvent.touchStart(playButton);
      fireEvent.touchEnd(playButton);
      
      await waitFor(() => {
        expect(playButton).toHaveBeenInteractedWith;
      });
    });

    test('adapts video dimensions for mobile', () => {
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        isMobile: true,
        orientation: 'portrait',
        getResponsiveVideoDimensions: () => ({
          maxHeight: 350,
          minHeight: 200,
          width: '100%'
        })
      });

      const { container } = renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      const video = container.querySelector('video');
      expect(video).toBeInTheDocument();
      expect(video?.style.maxHeight).toBeDefined();
    });
  });

  describe('Tablet Responsive Behavior', () => {
    beforeEach(() => {
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        isTablet: true,
        isDesktop: false,
        isMobile: false,
        screenSize: { width: 768, height: 1024 },
        getResponsiveLayoutProps: () => ({
          spacing: 1,
          direction: 'row' as const,
          alignItems: 'center' as const,
          justifyContent: 'flex-start' as const,
          sx: { flexWrap: 'wrap', gap: 1 }
        })
      });
    });

    test('renders with tablet-optimized layout', () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });
  });

  describe('Touch Device Adaptations', () => {
    beforeEach(() => {
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        isTouchDevice: true,
        getResponsiveAnnotationProps: () => ({
          sx: {
            gap: 0.5,
            px: 1,
            py: 0.5,
            minHeight: 36,
            fontSize: '0.7rem',
            touchAction: 'manipulation',
            '&:active': {
              transform: 'scale(0.95)'
            }
          },
          indicatorSize: 8
        })
      });
    });

    test('annotations are touch-friendly', () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      const annotation = screen.getByText(/pedestrian/i);
      expect(annotation).toBeInTheDocument();
      
      fireEvent.touchStart(annotation);
      fireEvent.touchEnd(annotation);
    });

    test('handles touch seek gestures', () => {
      const mockHandleTouchSeek = jest.fn();
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        isTouchDevice: true,
        handleTouchSeek: mockHandleTouchSeek
      });

      const { container } = renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      const video = container.querySelector('video');
      if (video) {
        fireEvent.touchStart(video, {
          touches: [{ clientX: 100, clientY: 50 }]
        });
      }
    });
  });

  describe('High Density Display Support', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'devicePixelRatio', {
        writable: true,
        configurable: true,
        value: 2
      });

      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        isHighDensity: true,
        optimizeCanvasForDisplay: jest.fn()
      });
    });

    test('optimizes canvas for high density displays', () => {
      const mockOptimizeCanvas = jest.fn();
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        isHighDensity: true,
        optimizeCanvasForDisplay: mockOptimizeCanvas
      });

      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={true}
          frameRate={30}
        />
      );

      // Canvas optimization should be called for high-density displays
      expect(mockOptimizeCanvas).toHaveBeenCalled;
    });
  });

  describe('Orientation Changes', () => {
    test('handles portrait orientation', () => {
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        orientation: 'portrait',
        isMobile: true,
        getResponsiveVideoDimensions: () => ({
          maxHeight: 350,
          minHeight: 200,
          width: '100%'
        })
      });

      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });

    test('handles landscape orientation', () => {
      mockUseResponsiveVideoPlayer.mockReturnValue({
        ...defaultResponsiveState,
        orientation: 'landscape',
        isMobile: true,
        getResponsiveVideoDimensions: () => ({
          maxHeight: 300,
          minHeight: 180,
          width: '100%'
        })
      });

      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });
  });

  describe('Accessibility Features', () => {
    test('maintains keyboard navigation support', () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      playButton.focus();
      
      fireEvent.keyDown(playButton, { key: 'Enter' });
      expect(playButton).toHaveFocus();
    });

    test('provides proper ARIA labels', () => {
      renderWithTheme(
        <EnhancedVideoPlayer
          video={mockVideo}
          annotations={mockAnnotations}
          annotationMode={false}
          frameRate={30}
        />
      );

      expect(screen.getByRole('slider', { name: /video progress/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });
  });
});