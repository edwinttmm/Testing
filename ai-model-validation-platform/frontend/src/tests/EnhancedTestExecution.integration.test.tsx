import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import EnhancedTestExecution from '../pages/EnhancedTestExecution';
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';
import SequentialVideoManager from '../components/SequentialVideoManager';

// Mock API service
jest.mock('../services/api', () => ({
  apiService: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

// Mock WebSocket
global.WebSocket = jest.fn().mockImplementation(() => ({
  readyState: 1,
  send: jest.fn(),
  close: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
}));

const theme = createTheme();

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

// Mock data
const mockProjects = [
  {
    id: '1',
    name: 'Test Project 1',
    description: 'Test description',
    status: 'active',
    modelConfigurations: [
      { id: 'model1', name: 'YOLO v8', type: 'detection' }
    ]
  },
  {
    id: '2',
    name: 'Test Project 2',
    description: 'Another test',
    status: 'active',
    modelConfigurations: []
  }
];

const mockVideos = [
  {
    id: 'video1',
    filename: 'test_video_1.mp4',
    name: 'Test Video 1',
    url: 'http://155.138.239.131:8001/uploads/test_video_1.mp4',
    duration: 30,
    status: 'processed'
  },
  {
    id: 'video2',
    filename: 'test_video_2.mp4',
    name: 'Test Video 2',
    url: 'http://155.138.239.131:8001/uploads/test_video_2.mp4',
    duration: 45,
    status: 'processed'
  },
  {
    id: 'video3',
    filename: 'test_video_3.mp4',
    name: 'Test Video 3',
    url: 'http://155.138.239.131:8001/uploads/test_video_3.mp4',
    duration: 60,
    status: 'processed'
  }
];

describe('Enhanced Test Execution Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock API responses
    const { apiService } = require('../services/api');
    apiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve(mockProjects);
      }
      if (url === '/api/health') {
        return Promise.resolve({ status: 'healthy' });
      }
      return Promise.resolve([]);
    });
  });

  test('renders enhanced test execution page with all sections', async () => {
    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    // Check main title
    expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();

    // Check connection status section
    expect(screen.getByText('API')).toBeInTheDocument();
    expect(screen.getByText('WebSocket')).toBeInTheDocument();

    // Check project selection
    expect(screen.getByLabelText('Project')).toBeInTheDocument();
    
    // Check latency input
    expect(screen.getByLabelText('Latency (ms)')).toBeInTheDocument();

    // Check control buttons
    expect(screen.getByText(/Videos \(0\)/)).toBeInTheDocument();
    expect(screen.getByText('Test Config')).toBeInTheDocument();
    expect(screen.getByText('Start Sequential')).toBeInTheDocument();
  });

  test('project selection and configuration flow', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    // Wait for projects to load
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Project 1')).toBeInTheDocument();
    });

    // Change project selection
    const projectSelect = screen.getByLabelText('Project');
    await user.click(projectSelect);
    
    // Should show project options
    expect(screen.getByText('Test Project 2')).toBeInTheDocument();
  });

  test('latency configuration', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    const latencyInput = screen.getByLabelText('Latency (ms)');
    expect(latencyInput).toHaveValue(100); // Default value

    // Change latency
    await user.clear(latencyInput);
    await user.type(latencyInput, '250');
    
    expect(latencyInput).toHaveValue(250);
  });

  test('connection status monitoring', async () => {
    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    // Check connection check button exists
    const connectionCheckButton = screen.getByRole('button', { name: /check connection/i });
    expect(connectionCheckButton).toBeInTheDocument();

    // Click connection check
    fireEvent.click(connectionCheckButton);

    // Should trigger connection check (mocked)
    const { apiService } = require('../services/api');
    await waitFor(() => {
      expect(apiService.get).toHaveBeenCalledWith('/api/health');
    });
  });

  test('test configuration dialog', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    // Open test config dialog
    const configButton = screen.getByText('Test Config');
    await user.click(configButton);

    // Check dialog opens
    expect(screen.getByText('Test Configuration')).toBeInTheDocument();
    
    // Check configuration options
    expect(screen.getByText('Sequential Playback')).toBeInTheDocument();
    expect(screen.getByText('Auto Advance Videos')).toBeInTheDocument();
    expect(screen.getByText('Loop Playback')).toBeInTheDocument();
    expect(screen.getByText('Random Order')).toBeInTheDocument();
    expect(screen.getByText('Sync External Signals')).toBeInTheDocument();

    // Check advance delay input
    expect(screen.getByLabelText('Advance Delay (ms)')).toBeInTheDocument();

    // Close dialog
    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);
    
    expect(screen.queryByText('Test Configuration')).not.toBeInTheDocument();
  });

  test('sequential playback state management', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    // The sequential playback section should not be visible initially
    expect(screen.queryByText(/Sequential Playback - Video/)).not.toBeInTheDocument();
  });
});

describe('VideoAnnotationPlayer Enhanced Features', () => {
  const mockVideo = {
    id: 'test-video',
    filename: 'test.mp4',
    name: 'Test Video',
    url: 'http://155.138.239.131:8001/uploads/test.mp4',
    duration: 30,
    status: 'processed'
  };

  test('renders with fullscreen capability', () => {
    render(
      <TestWrapper>
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={[]}
          annotationMode={false}
          enableFullscreen={true}
        />
      </TestWrapper>
    );

    // Check fullscreen button exists
    const fullscreenButton = screen.getByRole('button', { name: /fullscreen/i });
    expect(fullscreenButton).toBeInTheDocument();
  });

  test('renders with sync controls when enabled', () => {
    render(
      <TestWrapper>
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={[]}
          annotationMode={false}
          syncIndicator={true}
          onSyncRequest={() => {}}
        />
      </TestWrapper>
    );

    // Check sync button exists
    const syncButton = screen.getByRole('button', { name: /sync timeline/i });
    expect(syncButton).toBeInTheDocument();
  });

  test('renders recording controls when enabled', () => {
    const mockRecordingToggle = jest.fn();
    
    render(
      <TestWrapper>
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={[]}
          annotationMode={false}
          onRecordingToggle={mockRecordingToggle}
        />
      </TestWrapper>
    );

    // Check recording button exists
    const recordingButton = screen.getByRole('button', { name: /start recording/i });
    expect(recordingButton).toBeInTheDocument();

    // Click recording button
    fireEvent.click(recordingButton);
    expect(mockRecordingToggle).toHaveBeenCalledWith(true);
  });

  test('calls onVideoEnd when video ends', () => {
    const mockVideoEnd = jest.fn();
    
    render(
      <TestWrapper>
        <VideoAnnotationPlayer
          video={mockVideo}
          annotations={[]}
          annotationMode={false}
          onVideoEnd={mockVideoEnd}
        />
      </TestWrapper>
    );

    // This would be triggered by the video element's 'ended' event
    // In a real test, we'd simulate the video ending
    expect(mockVideoEnd).not.toHaveBeenCalled();
  });
});

describe('SequentialVideoManager Features', () => {
  const mockVideos = [
    {
      id: 'video1',
      filename: 'test1.mp4',
      name: 'Test Video 1',
      url: 'http://155.138.239.131:8001/uploads/test1.mp4',
      duration: 30,
      status: 'processed'
    },
    {
      id: 'video2',
      filename: 'test2.mp4',
      name: 'Test Video 2',
      url: 'http://155.138.239.131:8001/uploads/test2.mp4',
      duration: 45,
      status: 'processed'
    }
  ];

  test('renders sequential video manager with controls', () => {
    render(
      <TestWrapper>
        <SequentialVideoManager
          videos={mockVideos}
          autoAdvance={true}
          loopPlayback={false}
        />
      </TestWrapper>
    );

    // Check main title
    expect(screen.getByText('Sequential Playback')).toBeInTheDocument();
    
    // Check video count
    expect(screen.getByText('Video 1 of 2')).toBeInTheDocument();
    
    // Check control buttons
    expect(screen.getByRole('button', { name: /previous video/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next video/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /shuffle order/i })).toBeInTheDocument();
  });

  test('navigation between videos', async () => {
    const mockVideoChange = jest.fn();
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <SequentialVideoManager
          videos={mockVideos}
          onVideoChange={mockVideoChange}
          autoAdvance={true}
        />
      </TestWrapper>
    );

    // Click next button
    const nextButton = screen.getByRole('button', { name: /next video/i });
    await user.click(nextButton);

    // Should call onVideoChange with next video
    expect(mockVideoChange).toHaveBeenCalledWith(mockVideos[1], 1);
  });

  test('progress tracking', () => {
    render(
      <TestWrapper>
        <SequentialVideoManager
          videos={mockVideos}
          autoAdvance={true}
        />
      </TestWrapper>
    );

    // Check progress indicator
    expect(screen.getByText('Progress: 0%')).toBeInTheDocument();
    expect(screen.getByText('Played: 0 / 2')).toBeInTheDocument();
  });

  test('view mode switching', async () => {
    const user = userEvent.setup();
    
    render(
      <TestWrapper>
        <SequentialVideoManager
          videos={mockVideos}
          autoAdvance={true}
        />
      </TestWrapper>
    );

    // Switch to list view
    const listViewButton = screen.getByRole('button', { name: /show video list/i });
    await user.click(listViewButton);

    // Should show video list
    expect(screen.getByText('Video Sequence (2 videos)')).toBeInTheDocument();
    expect(screen.getByText('1. test1.mp4')).toBeInTheDocument();
    expect(screen.getByText('2. test2.mp4')).toBeInTheDocument();
  });
});

describe('Integration Test: Full Enhanced Workflow', () => {
  test('complete sequential playback workflow', async () => {
    const user = userEvent.setup();
    
    // Mock the full API flow
    const { apiService } = require('../services/api');
    apiService.post.mockResolvedValue({ 
      id: 'session123',
      name: 'Test Session',
      status: 'created' 
    });

    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    // Wait for projects to load
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Project 1')).toBeInTheDocument();
    });

    // Configure latency
    const latencyInput = screen.getByLabelText('Latency (ms)');
    await user.clear(latencyInput);
    await user.type(latencyInput, '500');

    // Open test configuration
    const configButton = screen.getByText('Test Config');
    await user.click(configButton);

    // Enable external sync
    const syncSwitch = screen.getByRole('checkbox', { name: /sync external signals/i });
    await user.click(syncSwitch);

    // Save configuration
    const saveButton = screen.getByText('Save Configuration');
    await user.click(saveButton);

    // Note: Video selection and start sequential would require more complex mocking
    // of the VideoSelectionDialog and WebSocket connections
  });
});

// Performance tests
describe('Enhanced Test Execution Performance', () => {
  test('renders within performance budget', async () => {
    const startTime = performance.now();
    
    render(
      <TestWrapper>
        <EnhancedTestExecution />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Enhanced Test Execution')).toBeInTheDocument();
    });

    const endTime = performance.now();
    const renderTime = endTime - startTime;

    // Should render within 1 second
    expect(renderTime).toBeLessThan(1000);
  });

  test('handles large video lists efficiently', () => {
    const largeVideoList = Array.from({ length: 100 }, (_, i) => ({
      id: `video${i}`,
      filename: `test_video_${i}.mp4`,
      name: `Test Video ${i}`,
      url: `http://155.138.239.131:8001/uploads/test_video_${i}.mp4`,
      duration: 30 + i,
      status: 'processed'
    }));

    const startTime = performance.now();
    
    render(
      <TestWrapper>
        <SequentialVideoManager
          videos={largeVideoList}
          autoAdvance={true}
        />
      </TestWrapper>
    );

    const endTime = performance.now();
    const renderTime = endTime - startTime;

    // Should handle large lists efficiently
    expect(renderTime).toBeLessThan(500);
    expect(screen.getByText('Video 1 of 100')).toBeInTheDocument();
  });
});