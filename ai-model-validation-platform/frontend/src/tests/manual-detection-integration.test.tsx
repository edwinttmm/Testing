import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import DetectionControls from '../components/DetectionControls';
import DetectionResultsPanel from '../components/DetectionResultsPanel';
import VideoAnnotationPlayer from '../components/VideoAnnotationPlayer';
import { VideoFile, GroundTruthAnnotation } from '../services/types';

// Mock the detection service
jest.mock('../services/detectionService', () => ({
  detectionService: {
    runDetection: jest.fn(),
  },
}));

// Mock the API service
jest.mock('../services/api', () => ({
  apiService: {
    createAnnotation: jest.fn(),
  },
}));

const theme = createTheme();

const mockVideo: VideoFile = {
  id: 'test-video-id',
  filename: 'test-video.mp4',
  url: 'https://example.com/test-video.mp4',
  duration: 60,
  file_size: 1024000,
  status: 'completed',
  created_at: new Date().toISOString(),
  projectId: 'test-project',
};

const mockAnnotations: GroundTruthAnnotation[] = [
  {
    id: 'ann-1',
    videoId: 'test-video-id',
    detectionId: 'DET_PED_001',
    frameNumber: 30,
    timestamp: 1.0,
    vruType: 'pedestrian',
    boundingBox: {
      x: 100,
      y: 100,
      width: 50,
      height: 100,
      label: 'pedestrian',
      confidence: 0.85,
    },
    occluded: false,
    truncated: false,
    difficult: false,
    validated: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

describe('Manual Detection Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const renderWithTheme = (component: React.ReactElement) => {
    return render(
      <ThemeProvider theme={theme}>
        {component}
      </ThemeProvider>
    );
  };

  test('DetectionControls shows manual start button initially', () => {
    const mockHandlers = {
      onDetectionStart: jest.fn(),
      onDetectionComplete: jest.fn(),
      onDetectionError: jest.fn(),
    };

    renderWithTheme(
      <DetectionControls
        video={mockVideo}
        {...mockHandlers}
      />
    );

    // Should show start button initially
    expect(screen.getByText('Start Detection')).toBeInTheDocument();
    expect(screen.queryByText('Stop Detection')).not.toBeInTheDocument();
  });

  test('DetectionControls can be started manually', async () => {
    const mockHandlers = {
      onDetectionStart: jest.fn(),
      onDetectionComplete: jest.fn(),
      onDetectionError: jest.fn(),
    };

    renderWithTheme(
      <DetectionControls
        video={mockVideo}
        {...mockHandlers}
      />
    );

    const startButton = screen.getByText('Start Detection');
    fireEvent.click(startButton);

    // Should call the start handler
    expect(mockHandlers.onDetectionStart).toHaveBeenCalled();
  });

  test('DetectionResultsPanel shows empty state initially', () => {
    renderWithTheme(
      <DetectionResultsPanel
        detections={[]}
        loading={false}
        error={null}
        isRunning={false}
      />
    );

    expect(screen.getByText('No Detections Found')).toBeInTheDocument();
    expect(screen.getByText('Use the detection controls above to analyze this video for VRU objects.')).toBeInTheDocument();
  });

  test('DetectionResultsPanel shows running state', () => {
    renderWithTheme(
      <DetectionResultsPanel
        detections={[]}
        loading={false}
        error={null}
        isRunning={true}
      />
    );

    expect(screen.getByText('Running Detection Pipeline...')).toBeInTheDocument();
  });

  test('DetectionResultsPanel displays results after detection', () => {
    const mockDetections = mockAnnotations.map(annotation => ({
      id: annotation.id,
      timestamp: annotation.timestamp,
      frameNumber: annotation.frameNumber,
      confidence: annotation.boundingBox.confidence || 1.0,
      classLabel: annotation.vruType,
      vruType: annotation.vruType,
      boundingBox: annotation.boundingBox,
    }));

    renderWithTheme(
      <DetectionResultsPanel
        detections={mockDetections}
        loading={false}
        error={null}
        isRunning={false}
      />
    );

    expect(screen.getByText('Detection Results (1)')).toBeInTheDocument();
    expect(screen.getByText('pedestrian')).toBeInTheDocument();
    expect(screen.getByText('85.0%')).toBeInTheDocument();
  });

  test('VideoAnnotationPlayer can display detection controls', () => {
    const mockDetectionControls = (
      <div data-testid="detection-controls">Mock Detection Controls</div>
    );

    renderWithTheme(
      <VideoAnnotationPlayer
        video={mockVideo}
        annotations={mockAnnotations}
        annotationMode={false}
        showDetectionControls={true}
        detectionControlsComponent={mockDetectionControls}
        frameRate={30}
      />
    );

    expect(screen.getByTestId('detection-controls')).toBeInTheDocument();
  });

  test('VideoAnnotationPlayer hides detection controls when not enabled', () => {
    const mockDetectionControls = (
      <div data-testid="detection-controls">Mock Detection Controls</div>
    );

    renderWithTheme(
      <VideoAnnotationPlayer
        video={mockVideo}
        annotations={mockAnnotations}
        annotationMode={false}
        showDetectionControls={false}
        detectionControlsComponent={mockDetectionControls}
        frameRate={30}
      />
    );

    expect(screen.queryByTestId('detection-controls')).not.toBeInTheDocument();
  });

  test('Manual detection workflow integration', async () => {
    let detectionStarted = false;
    let detectionCompleted = false;
    let detectionResults: any[] = [];

    const MockIntegratedComponent = () => {
      const [isRunning, setIsRunning] = React.useState(false);
      const [results, setResults] = React.useState<any[]>([]);
      const [error, setError] = React.useState<string | null>(null);

      const handleDetectionStart = () => {
        detectionStarted = true;
        setIsRunning(true);
        setError(null);
        setResults([]);
      };

      const handleDetectionComplete = (annotations: any[]) => {
        detectionCompleted = true;
        setIsRunning(false);
        setResults(annotations);
        detectionResults = annotations;
      };

      const handleDetectionError = (errorMessage: string) => {
        setIsRunning(false);
        setError(errorMessage);
      };

      return (
        <div>
          <DetectionControls
            video={mockVideo}
            onDetectionStart={handleDetectionStart}
            onDetectionComplete={handleDetectionComplete}
            onDetectionError={handleDetectionError}
          />
          <DetectionResultsPanel
            detections={results.map(annotation => ({
              id: annotation.id,
              timestamp: annotation.timestamp,
              frameNumber: annotation.frameNumber,
              confidence: annotation.boundingBox?.confidence || 1.0,
              classLabel: annotation.vruType,
              vruType: annotation.vruType,
              boundingBox: annotation.boundingBox,
            }))}
            loading={false}
            error={error}
            isRunning={isRunning}
          />
        </div>
      );
    };

    renderWithTheme(<MockIntegratedComponent />);

    // Initially should show start button and empty results
    expect(screen.getByText('Start Detection')).toBeInTheDocument();
    expect(screen.getByText('No Detections Found')).toBeInTheDocument();

    // Click start detection
    const startButton = screen.getByText('Start Detection');
    fireEvent.click(startButton);

    // Should have started
    expect(detectionStarted).toBe(true);
  });

  test('Detection controls advanced settings work', () => {
    const mockHandlers = {
      onDetectionStart: jest.fn(),
      onDetectionComplete: jest.fn(),
      onDetectionError: jest.fn(),
    };

    renderWithTheme(
      <DetectionControls
        video={mockVideo}
        {...mockHandlers}
      />
    );

    // Click advanced button
    const advancedButton = screen.getByText('Advanced');
    fireEvent.click(advancedButton);

    // Should show advanced settings
    expect(screen.getByText('Detection Configuration')).toBeInTheDocument();
    expect(screen.getByLabelText('Model')).toBeInTheDocument();
  });
});