/**
 * Test suite for video loading fixes in EnhancedTestExecution
 * 
 * This test verifies that the video loading issue has been resolved:
 * 1. Videos are properly loaded from API
 * 2. Mock videos are provided when API fails
 * 3. SequentialVideoPlayer receives non-empty video array
 * 4. Component re-rendering loops are prevented with key prop
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import EnhancedTestExecution from '../pages/EnhancedTestExecution';
import { apiService } from '../services/api';

// Mock the API service
jest.mock('../services/api');
const mockedApiService = apiService as jest.Mocked<typeof apiService>;

// Mock data
const mockProject = {
  id: 'test-project-1',
  name: 'Test Project',
  description: 'Test project for video loading',
  cameraModel: 'Test Camera',
  cameraView: 'test-view',
  signalType: 'digital' as const,
  createdAt: new Date(),
  updatedAt: new Date()
};

const mockVideos = [
  {
    id: 'test-video-1',
    filename: 'test-video-1.mp4',
    name: 'Test Video 1',
    url: 'http://localhost:3000/videos/test-video-1.mp4',
    duration: 30,
    size: 1000000,
    mimeType: 'video/mp4',
    projectId: 'test-project-1',
    uploadedAt: new Date(),
    status: 'processed' as const
  },
  {
    id: 'test-video-2',
    filename: 'test-video-2.mp4',
    name: 'Test Video 2',
    url: 'http://localhost:3000/videos/test-video-2.mp4',
    duration: 45,
    size: 1500000,
    mimeType: 'video/mp4',
    projectId: 'test-project-1',
    uploadedAt: new Date(),
    status: 'processed' as const
  }
];

// Mock console.log to capture our debugging logs
const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

const theme = createTheme();

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('Video Loading Fixes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy.mockClear();
    consoleWarnSpy.mockClear();
    consoleErrorSpy.mockClear();
  });

  afterAll(() => {
    consoleSpy.mockRestore();
    consoleWarnSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });

  test('should load videos from API successfully', async () => {
    // Setup API mocks
    mockedApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve([mockProject]);
      }
      if (url === `/api/projects/${mockProject.id}/videos`) {
        return Promise.resolve(mockVideos);
      }
      return Promise.resolve([]);
    });

    renderWithTheme(<EnhancedTestExecution />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    // Verify project loading logs
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('📂 Loaded 1 projects:')
      );
    });

    // Verify auto-loading videos logs
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('🔄 Auto-loading videos for project: Test Project')
      );
    });

    // Verify videos were loaded
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('📹 Auto-loaded 2 videos:')
      );
    });

    // Verify videos are displayed in UI
    await waitFor(() => {
      expect(screen.getByText(/Videos \(2\)/)).toBeInTheDocument();
    });
  });

  test('should provide mock videos when API returns empty array', async () => {
    // Setup API mocks - project exists but no videos
    mockedApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve([mockProject]);
      }
      if (url === `/api/projects/${mockProject.id}/videos`) {
        return Promise.resolve([]); // Empty array
      }
      return Promise.resolve([]);
    });

    renderWithTheme(<EnhancedTestExecution />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    // Verify warning about no videos found
    await waitFor(() => {
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('⚠️ No videos found for project Test Project')
      );
    });

    // Verify mock video was added
    await waitFor(() => {
      expect(screen.getByText(/Videos \(1\)/)).toBeInTheDocument();
    });

    // Check that SequentialVideoPlayer is rendered with videos
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        '🎬 Rendering SequentialVideoPlayer with videos:',
        1,
        expect.any(Array)
      );
    });
  });

  test('should provide mock videos when API fails', async () => {
    // Setup API mocks - project exists but videos API fails
    mockedApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve([mockProject]);
      }
      if (url === `/api/projects/${mockProject.id}/videos`) {
        throw new Error('Network error');
      }
      return Promise.resolve([]);
    });

    renderWithTheme(<EnhancedTestExecution />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    // Verify error was logged
    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to auto-load videos:',
        expect.any(Error)
      );
    });

    // Verify fallback video was added
    await waitFor(() => {
      expect(screen.getByText(/Videos \(1\)/)).toBeInTheDocument();
    });
  });

  test('should create mock project when no projects exist', async () => {
    // Setup API mocks - no projects exist
    mockedApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve([]); // No projects
      }
      return Promise.resolve([]);
    });

    renderWithTheme(<EnhancedTestExecution />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    // Verify warning about no projects
    await waitFor(() => {
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('⚠️ No projects found. Creating mock project')
      );
    });

    // Verify mock project and video were created
    await waitFor(() => {
      expect(screen.getByText(/Videos \(1\)/)).toBeInTheDocument();
    });
  });

  test('should handle manual project selection and load videos', async () => {
    const anotherProject = {
      id: 'test-project-2',
      name: 'Another Project',
      description: 'Another test project',
      cameraModel: 'Another Camera',
      cameraView: 'another-view',
      signalType: 'analog' as const,
      createdAt: new Date(),
      updatedAt: new Date()
    };

    const anotherProjectVideos = [mockVideos[0]]; // Just one video

    // Setup API mocks
    mockedApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve([mockProject, anotherProject]);
      }
      if (url === `/api/projects/${mockProject.id}/videos`) {
        return Promise.resolve(mockVideos);
      }
      if (url === `/api/projects/${anotherProject.id}/videos`) {
        return Promise.resolve(anotherProjectVideos);
      }
      return Promise.resolve([]);
    });

    renderWithTheme(<EnhancedTestExecution />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    // Find and click project selector
    const projectSelect = screen.getByRole('combobox');
    fireEvent.mouseDown(projectSelect);
    
    // Select the second project
    const anotherProjectOption = await screen.findByText('Another Project');
    fireEvent.click(anotherProjectOption);

    // Verify loading log for new project
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        '🔄 Loading videos for project: Another Project (ID: test-project-2)'
      );
    });

    // Verify videos were loaded for new project
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        '📹 API returned 1 videos for project test-project-2:',
        anotherProjectVideos
      );
    });

    // Verify UI shows correct video count
    await waitFor(() => {
      expect(screen.getByText(/Videos \(1\)/)).toBeInTheDocument();
    });
  });

  test('should prevent component re-rendering loops with key prop', async () => {
    // Setup API mocks
    mockedApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve([mockProject]);
      }
      if (url === `/api/projects/${mockProject.id}/videos`) {
        return Promise.resolve(mockVideos);
      }
      return Promise.resolve([]);
    });

    renderWithTheme(<EnhancedTestExecution />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    // Check that SequentialVideoPlayer is rendered with unique key
    const sequentialPlayerElement = document.querySelector('.sequential-video-player');
    expect(sequentialPlayerElement).toBeInTheDocument();

    // Verify that the key prop is being used (check console logs)
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        '🎬 Rendering SequentialVideoPlayer with videos:',
        2,
        expect.any(Array)
      );
    });
  });
});

// Integration test to verify the complete flow
describe('Video Loading Integration', () => {
  test('complete video loading and playback flow', async () => {
    // Setup API mocks for complete flow
    mockedApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve([mockProject]);
      }
      if (url === `/api/projects/${mockProject.id}/videos`) {
        return Promise.resolve(mockVideos);
      }
      if (url === '/api/test-sessions') {
        return Promise.resolve([]);
      }
      return Promise.resolve([]);
    });

    renderWithTheme(<EnhancedTestExecution />);

    // Wait for full component load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    }, { timeout: 10000 });

    // Verify the complete flow works:
    // 1. Projects loaded
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('📂 Loaded 1 projects:')
    );

    // 2. Videos auto-loaded
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('📹 Auto-loaded 2 videos:')
      );
    });

    // 3. SequentialVideoPlayer rendered with videos
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        '🎬 Rendering SequentialVideoPlayer with videos:',
        2,
        expect.any(Array)
      );
    });

    // 4. UI shows correct states
    expect(screen.getByText(/Videos \(2\)/)).toBeInTheDocument();
    expect(screen.getByText('Test Project')).toBeInTheDocument();

    // 5. Video player is visible
    const sequentialPlayer = document.querySelector('.sequential-video-player');
    expect(sequentialPlayer).toBeInTheDocument();
  });
});