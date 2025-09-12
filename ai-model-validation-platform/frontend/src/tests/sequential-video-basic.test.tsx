/**
 * Basic Sequential Video Test
 * 
 * Simple test to verify the sequential video system works with basic functionality
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { VideoFile } from '../services/types';

// Mock video files for testing
const mockVideos: VideoFile[] = [
  {
    id: '1',
    name: 'Test Video 1',
    filename: 'video1.mp4',
    url: '/test/video1.mp4',
    duration: 10,
    size: 1024,
    mimeType: 'video/mp4',
    uploadedAt: new Date(),
  },
  {
    id: '2',
    name: 'Test Video 2',
    filename: 'video2.mp4',
    url: '/test/video2.mp4',
    duration: 15,
    size: 2048,
    mimeType: 'video/mp4',
    uploadedAt: new Date(),
  },
];

describe('Sequential Video Basic Functionality', () => {
  beforeEach(() => {
    // Mock video element methods
    HTMLMediaElement.prototype.load = jest.fn();
    HTMLMediaElement.prototype.play = jest.fn().mockResolvedValue(undefined);
    HTMLMediaElement.prototype.pause = jest.fn();
    
    // Mock fullscreen API
    document.requestFullscreen = jest.fn().mockResolvedValue(undefined);
    document.exitFullscreen = jest.fn().mockResolvedValue(undefined);
    
    // Mock video readyState
    Object.defineProperty(HTMLMediaElement.prototype, 'readyState', {
      get: () => HTMLMediaElement.HAVE_ENOUGH_DATA,
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders without crashing', () => {
    render(<SequentialVideoPlayer videos={mockVideos} />);
    expect(screen.getByText(/Sequential Playback Progress/i)).toBeInTheDocument();
  });

  test('displays video count correctly', () => {
    render(<SequentialVideoPlayer videos={mockVideos} />);
    expect(screen.getByText(/2 videos/i)).toBeInTheDocument();
  });

  test('shows control buttons', () => {
    render(<SequentialVideoPlayer videos={mockVideos} showControls={true} />);
    
    // Should have play button initially
    const playButton = screen.getByLabelText(/start.*playback/i);
    expect(playButton).toBeInTheDocument();
    
    // Should have fullscreen button
    const fullscreenButton = screen.getByLabelText(/enter fullscreen/i);
    expect(fullscreenButton).toBeInTheDocument();
  });

  test('shows progress bar when enabled', () => {
    render(<SequentialVideoPlayer videos={mockVideos} showProgress={true} />);
    
    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toBeInTheDocument();
  });

  test('hides controls when disabled', () => {
    render(<SequentialVideoPlayer videos={mockVideos} showControls={false} />);
    
    const playButton = screen.queryByLabelText(/start.*playback/i);
    expect(playButton).not.toBeInTheDocument();
  });

  test('hides progress when disabled', () => {
    render(<SequentialVideoPlayer videos={mockVideos} showProgress={false} />);
    
    const progressText = screen.queryByText(/Sequential Playback Progress/i);
    expect(progressText).not.toBeInTheDocument();
  });

  test('handles empty video array', () => {
    render(<SequentialVideoPlayer videos={[]} />);
    
    // Should show 0 videos
    expect(screen.getByText(/0 videos/i)).toBeInTheDocument();
  });

  test('displays current video information', async () => {
    render(<SequentialVideoPlayer videos={mockVideos} autoStart={false} />);
    
    // Should display first video info initially
    expect(screen.getByText(/Video 1 of 2/i)).toBeInTheDocument();
  });
});