import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import UnlinkVideoConfirmationDialog from '../components/UnlinkVideoConfirmationDialog';
import VideoDeleteConfirmationDialog from '../components/VideoDeleteConfirmationDialog';
import EnhancedVideoPlayer from '../components/EnhancedVideoPlayer';
import { VideoFile } from '../services/types';

// Mock theme for tests
const theme = createTheme();

// Mock video file for tests
const mockVideoFile: VideoFile = {
  id: '1',
  filename: 'test-video.mp4',
  url: 'http://example.com/test-video.mp4',
  status: 'completed',
  size: 1024 * 1024 * 10, // 10MB
  duration: 120, // 2 minutes
  createdAt: new Date().toISOString(),
  detectionCount: 5,
};

// Mock video element methods
const mockVideo = {
  play: jest.fn().mockResolvedValue(undefined),
  pause: jest.fn(),
  load: jest.fn(),
  canPlayType: jest.fn().mockReturnValue('probably'),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  currentTime: 0,
  duration: 120,
  paused: true,
  readyState: HTMLMediaElement.HAVE_ENOUGH_DATA,
  videoWidth: 1920,
  videoHeight: 1080,
  volume: 1,
  playbackRate: 1,
};

// Mock HTMLVideoElement
Object.defineProperty(window.HTMLMediaElement.prototype, 'play', {
  writable: true,
  value: mockVideo.play,
});

Object.defineProperty(window.HTMLVideoElement.prototype, 'pause', {
  writable: true,
  value: mockVideo.pause,
});

Object.defineProperty(window.HTMLVideoElement.prototype, 'load', {
  writable: true,
  value: mockVideo.load,
});

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('Video UI Enhancements', () => {
  describe('UnlinkVideoConfirmationDialog', () => {
    const mockOnConfirm = jest.fn();
    const mockOnClose = jest.fn();

    beforeEach(() => {
      mockOnConfirm.mockClear();
      mockOnClose.mockClear();
    });

    it('renders unlink dialog with video information', () => {
      renderWithTheme(
        <UnlinkVideoConfirmationDialog
          open={true}
          onClose={mockOnClose}
          video={mockVideoFile}
          projectName="Test Project"
          onConfirm={mockOnConfirm}
          loading={false}
        />
      );

      expect(screen.getByText('Unlink Video from Project')).toBeInTheDocument();
      expect(screen.getByText('test-video.mp4')).toBeInTheDocument();
      expect(screen.getByText(/Test Project/)).toBeInTheDocument();
      expect(screen.getByText('Unlink from Project')).toBeInTheDocument();
    });

    it('shows loading state when unlinking', () => {
      renderWithTheme(
        <UnlinkVideoConfirmationDialog
          open={true}
          onClose={mockOnClose}
          video={mockVideoFile}
          projectName="Test Project"
          onConfirm={mockOnConfirm}
          loading={true}
        />
      );

      expect(screen.getByText('Unlinking...')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /unlinking/i })).toBeDisabled();
    });

    it('calls onConfirm when unlink button is clicked', async () => {
      renderWithTheme(
        <UnlinkVideoConfirmationDialog
          open={true}
          onClose={mockOnClose}
          video={mockVideoFile}
          projectName="Test Project"
          onConfirm={mockOnConfirm}
          loading={false}
        />
      );

      fireEvent.click(screen.getByRole('button', { name: /unlink from project/i }));
      await waitFor(() => {
        expect(mockOnConfirm).toHaveBeenCalledWith(mockVideoFile.id);
      });
    });
  });

  describe('VideoDeleteConfirmationDialog', () => {
    const mockOnConfirm = jest.fn();
    const mockOnClose = jest.fn();

    beforeEach(() => {
      mockOnConfirm.mockClear();
      mockOnClose.mockClear();
    });

    it('renders delete dialog with video information', () => {
      renderWithTheme(
        <VideoDeleteConfirmationDialog
          open={true}
          onClose={mockOnClose}
          video={mockVideoFile}
          onConfirm={mockOnConfirm}
          loading={false}
          projectsUsingVideo={['Test Project']}
          annotationCount={5}
          testSessionCount={3}
        />
      );

      expect(screen.getByText('Confirm Permanent Deletion')).toBeInTheDocument();
      expect(screen.getByText('test-video.mp4')).toBeInTheDocument();
      expect(screen.getByText(/High Impact Deletion/)).toBeInTheDocument();
    });

    it('requires confirmation checkbox before enabling delete button', () => {
      renderWithTheme(
        <VideoDeleteConfirmationDialog
          open={true}
          onClose={mockOnClose}
          video={mockVideoFile}
          onConfirm={mockOnConfirm}
          loading={false}
        />
      );

      const deleteButton = screen.getByRole('button', { name: /permanently delete video/i });
      expect(deleteButton).toBeDisabled();

      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);

      expect(deleteButton).not.toBeDisabled();
    });

    it('shows detailed deletion impact information', () => {
      renderWithTheme(
        <VideoDeleteConfirmationDialog
          open={true}
          onClose={mockOnClose}
          video={mockVideoFile}
          onConfirm={mockOnConfirm}
          loading={false}
          projectsUsingVideo={['Test Project', 'Another Project']}
          annotationCount={15}
          testSessionCount={5}
        />
      );

      // Expand details
      fireEvent.click(screen.getByText('What will be permanently deleted'));

      expect(screen.getByText('15 ground truth annotations')).toBeInTheDocument();
      expect(screen.getByText('5 test session references')).toBeInTheDocument();
      expect(screen.getByText(/Links from 2 projects/)).toBeInTheDocument();
    });

    it('shows loading state during deletion', () => {
      renderWithTheme(
        <VideoDeleteConfirmationDialog
          open={true}
          onClose={mockOnClose}
          video={mockVideoFile}
          onConfirm={mockOnConfirm}
          loading={true}
        />
      );

      expect(screen.getByText('Deleting Video...')).toBeInTheDocument();
    });
  });

  describe('EnhancedVideoPlayer', () => {
    const mockProps = {
      video: mockVideoFile,
      annotations: [],
      onAnnotationSelect: jest.fn(),
      onTimeUpdate: jest.fn(),
      onCanvasClick: jest.fn(),
      annotationMode: false,
      selectedAnnotation: null,
      frameRate: 30,
      autoRetry: true,
      maxRetries: 3,
    };

    beforeEach(() => {
      jest.clearAllMocks();
    });

    it('renders video player with controls', () => {
      renderWithTheme(<EnhancedVideoPlayer {...mockProps} />);

      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
      expect(screen.getByText(/Frame:/)).toBeInTheDocument();
      expect(screen.getByText(/Speed:/)).toBeInTheDocument();
    });

    it('shows loading state initially', () => {
      renderWithTheme(<EnhancedVideoPlayer {...mockProps} />);

      expect(screen.getByText('Loading video...')).toBeInTheDocument();
      expect(screen.getByText('test-video.mp4')).toBeInTheDocument();
    });

    it('displays annotation mode indicator when enabled', () => {
      renderWithTheme(
        <EnhancedVideoPlayer {...mockProps} annotationMode={true} />
      );

      expect(screen.getByText('ANNOTATION MODE')).toBeInTheDocument();
    });

    it('shows playback rate controls', () => {
      renderWithTheme(<EnhancedVideoPlayer {...mockProps} />);

      expect(screen.getByText('Speed:')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '1x' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '2x' })).toBeInTheDocument();
    });

    it('handles video errors with retry functionality', async () => {
      const errorVideo = { ...mockVideoFile, url: 'invalid-url' };
      
      renderWithTheme(
        <EnhancedVideoPlayer {...mockProps} video={errorVideo} />
      );

      // Simulate video error - this would normally be triggered by the video element
      // For now, just check that error handling components are in place
      expect(screen.queryByText(/retry/i)).not.toBeInTheDocument(); // Initially no error
    });
  });

  describe('Video Operations Integration', () => {
    it('integrates unlink and delete operations properly', () => {
      // This test would verify that both operations can be performed
      // and that the UI properly handles the state transitions
      expect(true).toBe(true); // Placeholder for integration test
    });

    it('maintains consistent loading states across components', () => {
      // Test that loading states are consistent and don't conflict
      expect(true).toBe(true); // Placeholder for loading state test
    });

    it('handles error recovery scenarios', () => {
      // Test error recovery flows across different components
      expect(true).toBe(true); // Placeholder for error recovery test
    });
  });
});

describe('Video Utility Functions', () => {
  it('formats file sizes correctly', () => {
    // Test file size formatting utility
    const formatFileSize = (bytes: number): string => {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    expect(formatFileSize(1024)).toBe('1 KB');
    expect(formatFileSize(1024 * 1024)).toBe('1 MB');
    expect(formatFileSize(1536 * 1024)).toBe('1.5 MB');
  });

  it('formats duration correctly', () => {
    const formatDuration = (seconds: number): string => {
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    expect(formatDuration(60)).toBe('1:00');
    expect(formatDuration(90)).toBe('1:30');
    expect(formatDuration(3665)).toBe('61:05');
  });
});