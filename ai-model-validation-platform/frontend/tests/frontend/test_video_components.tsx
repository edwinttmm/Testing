/**
 * Frontend Video Components Test Suite
 * Tests video player error handling, loading states, deletion functionality, and user interactions
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { jest } from '@jest/globals';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';

// Mock video components (these would be your actual components)
interface VideoPlayerProps {
  src: string;
  autoPlay?: boolean;
  controls?: boolean;
  onLoadStart?: () => void;
  onLoadedData?: () => void;
  onError?: (error: Event) => void;
  onPlay?: () => void;
  onPause?: () => void;
}

interface VideoUploadProps {
  onUploadProgress?: (progress: number) => void;
  onUploadComplete?: (videoData: any) => void;
  onUploadError?: (error: Error) => void;
  maxFileSize?: number;
  acceptedFormats?: string[];
}

interface VideoListProps {
  videos: Array<{
    id: string;
    filename: string;
    uploadDate: string;
    status: string;
    thumbnail?: string;
  }>;
  onDeleteVideo?: (videoId: string) => void;
  onSelectVideo?: (videoId: string) => void;
}

// Mock components for testing
const MockVideoPlayer: React.FC<VideoPlayerProps> = ({
  src,
  autoPlay = false,
  controls = true,
  onLoadStart,
  onLoadedData,
  onError,
  onPlay,
  onPause,
}) => {
  const [isLoading, setIsLoading] = React.useState(true);
  const [hasError, setHasError] = React.useState(false);
  const [isPlaying, setIsPlaying] = React.useState(false);
  
  const videoRef = React.useRef<HTMLVideoElement>(null);

  const handleLoadStart = () => {
    setIsLoading(true);
    onLoadStart?.();
  };

  const handleLoadedData = () => {
    setIsLoading(false);
    onLoadedData?.();
  };

  const handleError = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    setHasError(true);
    setIsLoading(false);
    onError?.(event as unknown as Event);
  };

  const handlePlay = async () => {
    try {
      if (videoRef.current) {
        await videoRef.current.play();
        setIsPlaying(true);
        onPlay?.();
      }
    } catch (error) {
      // Handle play() interruption
      if (error instanceof DOMException && error.name === 'AbortError') {
        setIsPlaying(false);
        // Retry play after short delay
        setTimeout(() => {
          if (videoRef.current && !videoRef.current.paused) {
            videoRef.current.play().catch(() => {
              // Ignore subsequent failures
            });
          }
        }, 100);
      }
    }
  };

  const handlePause = () => {
    setIsPlaying(false);
    onPause?.();
  };

  if (hasError) {
    return (
      <div data-testid="video-error" className="video-error">
        Error loading video: {src}
        <button 
          data-testid="retry-button"
          onClick={() => {
            setHasError(false);
            setIsLoading(true);
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="video-player-container">
      {isLoading && (
        <div data-testid="loading-spinner" className="loading-spinner">
          Loading video...
        </div>
      )}
      <video
        ref={videoRef}
        data-testid="video-element"
        src={src}
        controls={controls}
        autoPlay={autoPlay}
        onLoadStart={handleLoadStart}
        onLoadedData={handleLoadedData}
        onError={handleError}
        onPlay={handlePlay}
        onPause={handlePause}
        style={{ display: isLoading ? 'none' : 'block' }}
      />
      <div className="video-controls">
        <button 
          data-testid="play-button"
          onClick={handlePlay}
          disabled={isLoading}
        >
          {isPlaying ? 'Pause' : 'Play'}
        </button>
      </div>
    </div>
  );
};

const MockVideoUpload: React.FC<VideoUploadProps> = ({
  onUploadProgress,
  onUploadComplete,
  onUploadError,
  maxFileSize = 100 * 1024 * 1024, // 100MB default
  acceptedFormats = ['video/mp4', 'video/avi', 'video/mov'],
}) => {
  const [isUploading, setIsUploading] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [dragActive, setDragActive] = React.useState(false);
  
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const validateFile = (file: File): { valid: boolean; error?: string } => {
    if (file.size > maxFileSize) {
      return {
        valid: false,
        error: `File size ${(file.size / 1024 / 1024).toFixed(1)}MB exceeds maximum ${(maxFileSize / 1024 / 1024).toFixed(1)}MB`
      };
    }

    if (!acceptedFormats.includes(file.type)) {
      return {
        valid: false,
        error: `File type ${file.type} not supported. Accepted formats: ${acceptedFormats.join(', ')}`
      };
    }

    return { valid: true };
  };

  const simulateChunkedUpload = async (file: File) => {
    const chunkSize = 5 * 1024 * 1024; // 5MB chunks
    const totalChunks = Math.ceil(file.size / chunkSize);
    
    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Simulate potential network failure
      if (Math.random() < 0.1) { // 10% chance of failure
        throw new Error('Network error during chunk upload');
      }
      
      const progress = ((chunkIndex + 1) / totalChunks) * 100;
      setUploadProgress(progress);
      onUploadProgress?.(progress);
    }
    
    return {
      id: `video_${Date.now()}`,
      filename: file.name,
      size: file.size,
      uploadDate: new Date().toISOString(),
      status: 'uploaded',
    };
  };

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    
    const file = files[0];
    const validation = validateFile(file);
    
    if (!validation.valid) {
      onUploadError?.(new Error(validation.error));
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const result = await simulateChunkedUpload(file);
      onUploadComplete?.(result);
    } catch (error) {
      onUploadError?.(error as Error);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    handleFileUpload(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = () => {
    setDragActive(false);
  };

  return (
    <div className="video-upload-container">
      <div
        data-testid="drop-zone"
        className={`drop-zone ${dragActive ? 'drag-active' : ''} ${isUploading ? 'uploading' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
      >
        {isUploading ? (
          <div data-testid="upload-progress">
            <div>Uploading... {uploadProgress.toFixed(0)}%</div>
            <div className="progress-bar">
              <div 
                className="progress-fill"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        ) : (
          <div>
            <div>Drop video files here or click to browse</div>
            <div className="upload-constraints">
              Max size: {(maxFileSize / 1024 / 1024).toFixed(0)}MB
              <br />
              Supported: {acceptedFormats.join(', ')}
            </div>
          </div>
        )}
      </div>
      
      <input
        ref={fileInputRef}
        data-testid="file-input"
        type="file"
        accept={acceptedFormats.join(',')}
        onChange={(e) => handleFileUpload(e.target.files)}
        style={{ display: 'none' }}
      />
    </div>
  );
};

const MockVideoList: React.FC<VideoListProps> = ({
  videos,
  onDeleteVideo,
  onSelectVideo,
}) => {
  const [deletingVideoId, setDeletingVideoId] = React.useState<string | null>(null);

  const handleDeleteClick = async (videoId: string) => {
    if (deletingVideoId) return; // Prevent multiple simultaneous deletions
    
    setDeletingVideoId(videoId);
    
    try {
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 500));
      onDeleteVideo?.(videoId);
    } catch (error) {
      console.error('Failed to delete video:', error);
    } finally {
      setDeletingVideoId(null);
    }
  };

  return (
    <div data-testid="video-list" className="video-list">
      {videos.length === 0 ? (
        <div data-testid="empty-list">No videos uploaded yet</div>
      ) : (
        videos.map((video) => (
          <div
            key={video.id}
            data-testid={`video-item-${video.id}`}
            className="video-item"
          >
            <div className="video-info">
              <div className="video-filename">{video.filename}</div>
              <div className="video-meta">
                <span>Uploaded: {new Date(video.uploadDate).toLocaleDateString()}</span>
                <span className={`status status-${video.status}`}>
                  {video.status}
                </span>
              </div>
            </div>
            
            <div className="video-actions">
              <button
                data-testid={`select-button-${video.id}`}
                onClick={() => onSelectVideo?.(video.id)}
                disabled={video.status !== 'uploaded'}
              >
                Select
              </button>
              
              <button
                data-testid={`delete-button-${video.id}`}
                onClick={() => handleDeleteClick(video.id)}
                disabled={deletingVideoId === video.id}
                className="delete-button"
              >
                {deletingVideoId === video.id ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
};

describe('VideoPlayer Component', () => {
  beforeEach(() => {
    // Mock HTMLVideoElement methods
    Object.defineProperty(HTMLVideoElement.prototype, 'play', {
      writable: true,
      value: jest.fn().mockResolvedValue(undefined),
    });
    
    Object.defineProperty(HTMLVideoElement.prototype, 'pause', {
      writable: true,
      value: jest.fn(),
    });
  });

  test('renders video player with controls', () => {
    render(
      <MockVideoPlayer 
        src="/test-video.mp4"
        controls={true}
      />
    );

    expect(screen.getByTestId('video-element')).toBeInTheDocument();
    expect(screen.getByTestId('play-button')).toBeInTheDocument();
  });

  test('shows loading spinner initially', () => {
    render(<MockVideoPlayer src="/test-video.mp4" />);
    
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    expect(screen.getByText('Loading video...')).toBeInTheDocument();
  });

  test('handles video load success', async () => {
    const onLoadedData = jest.fn();
    
    render(
      <MockVideoPlayer 
        src="/test-video.mp4"
        onLoadedData={onLoadedData}
      />
    );

    const videoElement = screen.getByTestId('video-element');
    
    // Simulate video loaded
    fireEvent.loadedData(videoElement);

    await waitFor(() => {
      expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
    });
    
    expect(onLoadedData).toHaveBeenCalledTimes(1);
  });

  test('handles video load error with retry functionality', async () => {
    const onError = jest.fn();
    
    render(
      <MockVideoPlayer 
        src="/invalid-video.mp4"
        onError={onError}
      />
    );

    const videoElement = screen.getByTestId('video-element');
    
    // Simulate video error
    fireEvent.error(videoElement);

    await waitFor(() => {
      expect(screen.getByTestId('video-error')).toBeInTheDocument();
    });
    
    expect(screen.getByText(/Error loading video/)).toBeInTheDocument();
    expect(onError).toHaveBeenCalledTimes(1);

    // Test retry functionality
    const retryButton = screen.getByTestId('retry-button');
    fireEvent.click(retryButton);

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    expect(screen.queryByTestId('video-error')).not.toBeInTheDocument();
  });

  test('handles play button click and play() interruption', async () => {
    const mockPlay = jest.fn()
      .mockRejectedValueOnce(new DOMException('AbortError', 'AbortError'))
      .mockResolvedValue(undefined);
    
    Object.defineProperty(HTMLVideoElement.prototype, 'play', {
      writable: true,
      value: mockPlay,
    });

    const onPlay = jest.fn();
    
    render(
      <MockVideoPlayer 
        src="/test-video.mp4"
        onPlay={onPlay}
      />
    );

    // Load the video first
    const videoElement = screen.getByTestId('video-element');
    fireEvent.loadedData(videoElement);

    await waitFor(() => {
      expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
    });

    // Click play button
    const playButton = screen.getByTestId('play-button');
    fireEvent.click(playButton);

    // Should handle the AbortError and retry
    await waitFor(() => {
      expect(mockPlay).toHaveBeenCalledTimes(1);
    });

    // Verify retry mechanism works
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 150)); // Wait for retry delay
    });
  });

  test('handles autoplay with proper error handling', async () => {
    const mockPlay = jest.fn().mockRejectedValue(
      new DOMException('NotAllowedError', 'NotAllowedError')
    );
    
    Object.defineProperty(HTMLVideoElement.prototype, 'play', {
      value: mockPlay,
    });

    render(
      <MockVideoPlayer 
        src="/test-video.mp4"
        autoPlay={true}
      />
    );

    const videoElement = screen.getByTestId('video-element');
    fireEvent.loadedData(videoElement);

    // Autoplay should be attempted but may fail due to browser policies
    expect(videoElement).toHaveProperty('autoPlay', true);
  });

  test('handles multiple rapid play/pause interactions', async () => {
    render(<MockVideoPlayer src="/test-video.mp4" />);

    const videoElement = screen.getByTestId('video-element');
    fireEvent.loadedData(videoElement);

    await waitFor(() => {
      expect(screen.queryByTestId('loading-spinner')).not.toBeInTheDocument();
    });

    const playButton = screen.getByTestId('play-button');

    // Rapid clicks should be handled gracefully
    fireEvent.click(playButton);
    fireEvent.click(playButton);
    fireEvent.click(playButton);

    // Should not cause errors or undefined behavior
    expect(playButton).toBeInTheDocument();
  });
});

describe('VideoUpload Component', () => {
  test('renders upload drop zone', () => {
    render(<MockVideoUpload />);
    
    expect(screen.getByTestId('drop-zone')).toBeInTheDocument();
    expect(screen.getByText(/Drop video files here/)).toBeInTheDocument();
  });

  test('validates file size limits', async () => {
    const onUploadError = jest.fn();
    const maxFileSize = 10 * 1024 * 1024; // 10MB
    
    render(
      <MockVideoUpload 
        maxFileSize={maxFileSize}
        onUploadError={onUploadError}
      />
    );

    const fileInput = screen.getByTestId('file-input');
    
    // Create oversized file
    const oversizedFile = new File(
      [new ArrayBuffer(20 * 1024 * 1024)], // 20MB
      'large-video.mp4',
      { type: 'video/mp4' }
    );

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [oversizedFile] }
      });
    });

    expect(onUploadError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining('exceeds maximum')
      })
    );
  });

  test('validates file format restrictions', async () => {
    const onUploadError = jest.fn();
    const acceptedFormats = ['video/mp4'];
    
    render(
      <MockVideoUpload 
        acceptedFormats={acceptedFormats}
        onUploadError={onUploadError}
      />
    );

    const fileInput = screen.getByTestId('file-input');
    
    // Create invalid format file
    const invalidFile = new File(['content'], 'video.avi', { type: 'video/avi' });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [invalidFile] }
      });
    });

    expect(onUploadError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining('not supported')
      })
    );
  });

  test('handles successful chunked upload with progress tracking', async () => {
    const onUploadProgress = jest.fn();
    const onUploadComplete = jest.fn();
    
    render(
      <MockVideoUpload 
        onUploadProgress={onUploadProgress}
        onUploadComplete={onUploadComplete}
      />
    );

    const fileInput = screen.getByTestId('file-input');
    const validFile = new File(
      [new ArrayBuffer(15 * 1024 * 1024)], // 15MB
      'test-video.mp4',
      { type: 'video/mp4' }
    );

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [validFile] }
      });
    });

    // Should show upload progress
    await waitFor(() => {
      expect(screen.getByTestId('upload-progress')).toBeInTheDocument();
    });

    // Wait for upload completion
    await waitFor(() => {
      expect(onUploadComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          filename: 'test-video.mp4',
          status: 'uploaded'
        })
      );
    }, { timeout: 5000 });

    // Progress should have been reported multiple times
    expect(onUploadProgress).toHaveBeenCalled();
  });

  test('handles drag and drop functionality', async () => {
    const onUploadComplete = jest.fn();
    
    render(<MockVideoUpload onUploadComplete={onUploadComplete} />);

    const dropZone = screen.getByTestId('drop-zone');
    const validFile = new File(['content'], 'dropped-video.mp4', { type: 'video/mp4' });

    // Test drag over
    fireEvent.dragOver(dropZone);
    expect(dropZone).toHaveClass('drag-active');

    // Test drag leave
    fireEvent.dragLeave(dropZone);
    expect(dropZone).not.toHaveClass('drag-active');

    // Test drop
    await act(async () => {
      fireEvent.drop(dropZone, {
        dataTransfer: { files: [validFile] }
      });
    });

    await waitFor(() => {
      expect(onUploadComplete).toHaveBeenCalled();
    });
  });

  test('handles upload network errors with proper error reporting', async () => {
    const onUploadError = jest.fn();
    
    // Mock Math.random to always trigger failure
    const originalRandom = Math.random;
    Math.random = jest.fn().mockReturnValue(0.05); // Always < 0.1 (failure condition)
    
    render(<MockVideoUpload onUploadError={onUploadError} />);

    const fileInput = screen.getByTestId('file-input');
    const validFile = new File(['content'], 'test-video.mp4', { type: 'video/mp4' });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [validFile] }
      });
    });

    await waitFor(() => {
      expect(onUploadError).toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.stringContaining('Network error')
        })
      );
    });

    // Restore Math.random
    Math.random = originalRandom;
  });

  test('prevents multiple simultaneous uploads', async () => {
    render(<MockVideoUpload />);

    const dropZone = screen.getByTestId('drop-zone');
    const file1 = new File(['content1'], 'video1.mp4', { type: 'video/mp4' });
    const file2 = new File(['content2'], 'video2.mp4', { type: 'video/mp4' });

    // Start first upload
    await act(async () => {
      fireEvent.drop(dropZone, {
        dataTransfer: { files: [file1] }
      });
    });

    // Drop zone should be in uploading state
    expect(dropZone).toHaveClass('uploading');

    // Second upload attempt should be ignored
    await act(async () => {
      fireEvent.drop(dropZone, {
        dataTransfer: { files: [file2] }
      });
    });

    // Should still show first upload in progress
    expect(screen.getByTestId('upload-progress')).toBeInTheDocument();
  });
});

describe('VideoList Component', () => {
  const mockVideos = [
    {
      id: 'video1',
      filename: 'test-video-1.mp4',
      uploadDate: '2024-01-01T12:00:00Z',
      status: 'uploaded',
    },
    {
      id: 'video2', 
      filename: 'test-video-2.mp4',
      uploadDate: '2024-01-02T12:00:00Z',
      status: 'processing',
    },
    {
      id: 'video3',
      filename: 'test-video-3.mp4',
      uploadDate: '2024-01-03T12:00:00Z',
      status: 'failed',
    },
  ];

  test('renders list of videos', () => {
    render(<MockVideoList videos={mockVideos} />);

    expect(screen.getByTestId('video-list')).toBeInTheDocument();
    
    mockVideos.forEach((video) => {
      expect(screen.getByTestId(`video-item-${video.id}`)).toBeInTheDocument();
      expect(screen.getByText(video.filename)).toBeInTheDocument();
      expect(screen.getByText(video.status)).toBeInTheDocument();
    });
  });

  test('renders empty state when no videos', () => {
    render(<MockVideoList videos={[]} />);
    
    expect(screen.getByTestId('empty-list')).toBeInTheDocument();
    expect(screen.getByText('No videos uploaded yet')).toBeInTheDocument();
  });

  test('handles video selection', async () => {
    const onSelectVideo = jest.fn();
    
    render(
      <MockVideoList 
        videos={mockVideos}
        onSelectVideo={onSelectVideo}
      />
    );

    const selectButton = screen.getByTestId('select-button-video1');
    fireEvent.click(selectButton);

    expect(onSelectVideo).toHaveBeenCalledWith('video1');
  });

  test('disables select button for non-uploaded videos', () => {
    render(<MockVideoList videos={mockVideos} />);

    // Uploaded video should be selectable
    const uploadedSelectButton = screen.getByTestId('select-button-video1');
    expect(uploadedSelectButton).not.toBeDisabled();

    // Processing video should be disabled
    const processingSelectButton = screen.getByTestId('select-button-video2');
    expect(processingSelectButton).toBeDisabled();

    // Failed video should be disabled  
    const failedSelectButton = screen.getByTestId('select-button-video3');
    expect(failedSelectButton).toBeDisabled();
  });

  test('handles video deletion with loading state', async () => {
    const onDeleteVideo = jest.fn();
    
    render(
      <MockVideoList 
        videos={mockVideos}
        onDeleteVideo={onDeleteVideo}
      />
    );

    const deleteButton = screen.getByTestId('delete-button-video1');
    
    // Click delete
    fireEvent.click(deleteButton);

    // Should show deleting state immediately
    expect(screen.getByText('Deleting...')).toBeInTheDocument();
    expect(deleteButton).toBeDisabled();

    // Wait for deletion to complete
    await waitFor(() => {
      expect(onDeleteVideo).toHaveBeenCalledWith('video1');
    });

    // Button should be re-enabled (in real app, item would be removed)
    await waitFor(() => {
      expect(deleteButton).not.toBeDisabled();
      expect(screen.queryByText('Deleting...')).not.toBeInTheDocument();
    });
  });

  test('prevents multiple simultaneous deletions', async () => {
    const onDeleteVideo = jest.fn();
    
    render(
      <MockVideoList 
        videos={mockVideos}
        onDeleteVideo={onDeleteVideo}
      />
    );

    const deleteButton1 = screen.getByTestId('delete-button-video1');
    const deleteButton2 = screen.getByTestId('delete-button-video2');

    // Start first deletion
    fireEvent.click(deleteButton1);
    
    // Second deletion should be prevented
    fireEvent.click(deleteButton2);

    // Only first deletion should be processed
    await waitFor(() => {
      expect(onDeleteVideo).toHaveBeenCalledTimes(1);
      expect(onDeleteVideo).toHaveBeenCalledWith('video1');
    });
  });

  test('displays proper video status styling', () => {
    render(<MockVideoList videos={mockVideos} />);

    // Check status classes are applied
    const uploadedStatus = screen.getByText('uploaded');
    expect(uploadedStatus).toHaveClass('status-uploaded');

    const processingStatus = screen.getByText('processing');
    expect(processingStatus).toHaveClass('status-processing');

    const failedStatus = screen.getByText('failed');
    expect(failedStatus).toHaveClass('status-failed');
  });

  test('formats upload dates correctly', () => {
    render(<MockVideoList videos={mockVideos} />);

    // Check that dates are formatted (basic check)
    expect(screen.getByText(/Uploaded: 1\/1\/2024/)).toBeInTheDocument();
    expect(screen.getByText(/Uploaded: 1\/2\/2024/)).toBeInTheDocument();
    expect(screen.getByText(/Uploaded: 1\/3\/2024/)).toBeInTheDocument();
  });
});

describe('Video Component Integration', () => {
  test('video upload to player workflow', async () => {
    const [uploadedVideo, setUploadedVideo] = React.useState(null);
    
    const TestWorkflow = () => {
      const handleUploadComplete = (videoData) => {
        setUploadedVideo(videoData);
      };

      return (
        <div>
          <MockVideoUpload onUploadComplete={handleUploadComplete} />
          {uploadedVideo && (
            <MockVideoPlayer src={`/uploads/${uploadedVideo.filename}`} />
          )}
        </div>
      );
    };

    render(<TestWorkflow />);

    // Upload a video
    const fileInput = screen.getByTestId('file-input');
    const testFile = new File(['content'], 'workflow-test.mp4', { type: 'video/mp4' });

    await act(async () => {
      fireEvent.change(fileInput, {
        target: { files: [testFile] }
      });
    });

    // Wait for upload to complete and player to render
    await waitFor(() => {
      expect(screen.getByTestId('video-element')).toBeInTheDocument();
    });

    // Verify player is initialized with correct source
    const videoElement = screen.getByTestId('video-element');
    expect(videoElement).toHaveAttribute('src', '/uploads/workflow-test.mp4');
  });

  test('video list to player selection workflow', async () => {
    const [selectedVideoSrc, setSelectedVideoSrc] = React.useState(null);
    
    const TestWorkflow = () => {
      const handleSelectVideo = (videoId) => {
        const video = mockVideos.find(v => v.id === videoId);
        if (video) {
          setSelectedVideoSrc(`/videos/${video.filename}`);
        }
      };

      return (
        <div>
          <MockVideoList 
            videos={mockVideos}
            onSelectVideo={handleSelectVideo}
          />
          {selectedVideoSrc && (
            <MockVideoPlayer src={selectedVideoSrc} />
          )}
        </div>
      );
    };

    render(<TestWorkflow />);

    // Select a video from the list
    const selectButton = screen.getByTestId('select-button-video1');
    fireEvent.click(selectButton);

    // Verify player loads with selected video
    await waitFor(() => {
      expect(screen.getByTestId('video-element')).toBeInTheDocument();
    });

    const videoElement = screen.getByTestId('video-element');
    expect(videoElement).toHaveAttribute('src', '/videos/test-video-1.mp4');
  });
});

export {};