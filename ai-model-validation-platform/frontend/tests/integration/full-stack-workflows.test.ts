/**
 * Full-Stack Integration Tests for AI Model Validation Platform
 * 
 * Tests complete end-to-end workflows:
 * 1. Video Upload & Processing
 * 2. Annotation Workflow
 * 3. Test Execution Workflow  
 * 4. Real-time Communication
 */

import { describe, test, expect, beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import WS from 'jest-websocket-mock';
import { BrowserRouter } from 'react-router-dom';

// Components under test
import App from '../../src/App';
import TestExecution from '../../src/pages/TestExecution-fixed';
import Projects from '../../src/pages/Projects';
import AccessibleVideoPlayer from '../../src/components/AccessibleVideoPlayer';

// Services and utilities
import { apiService } from '../../src/services/api';
import { websocketService } from '../../src/services/websocketService';
import { VideoFile, Project, TestSession, DetectionEvent } from '../../src/services/types';

// Test data factories
import {
  createMockProject,
  createMockVideo,
  createMockTestSession,
  createMockDetectionEvent,
  createMockAnnotation
} from '../helpers/test-factories';

// Test environment setup
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

// Mock WebSocket server
let wsServer: WS;

// Mock API server
const apiServer = setupServer(
  // Project endpoints
  rest.get(`${API_BASE_URL}/api/projects`, (req, res, ctx) => {
    return res(ctx.json([createMockProject(), createMockProject({ id: '2', name: 'Project 2' })]));
  }),

  rest.post(`${API_BASE_URL}/api/projects`, (req, res, ctx) => {
    return res(ctx.json(createMockProject({ id: 'new-project' })));
  }),

  // Video endpoints
  rest.get(`${API_BASE_URL}/api/videos`, (req, res, ctx) => {
    return res(ctx.json([createMockVideo(), createMockVideo({ id: '2', filename: 'test2.mp4' })]));
  }),

  rest.post(`${API_BASE_URL}/api/videos/upload`, async (req, res, ctx) => {
    const formData = await req.formData();
    const file = formData.get('file') as File;
    
    if (!file) {
      return res(ctx.status(400), ctx.json({ detail: 'No file provided' }));
    }

    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 100));

    return res(ctx.json({
      id: 'uploaded-video-id',
      filename: file.name,
      originalName: file.name,
      fileSize: file.size,
      mimeType: file.type,
      uploadTimestamp: new Date().toISOString(),
      status: 'processing'
    }));
  }),

  // Test session endpoints
  rest.post(`${API_BASE_URL}/api/test-sessions`, (req, res, ctx) => {
    return res(ctx.json(createMockTestSession()));
  }),

  rest.get(`${API_BASE_URL}/api/test-sessions/:id`, (req, res, ctx) => {
    return res(ctx.json(createMockTestSession({ id: req.params.id as string })));
  }),

  // Detection endpoints
  rest.get(`${API_BASE_URL}/api/test-sessions/:id/detections`, (req, res, ctx) => {
    return res(ctx.json([
      createMockDetectionEvent(),
      createMockDetectionEvent({ id: '2', validationResult: 'FP' })
    ]));
  }),

  // Annotation endpoints
  rest.post(`${API_BASE_URL}/api/annotations/videos/:videoId/annotations`, (req, res, ctx) => {
    return res(ctx.json(createMockAnnotation()));
  }),

  rest.get(`${API_BASE_URL}/api/annotations/videos/:videoId/annotations`, (req, res, ctx) => {
    return res(ctx.json([createMockAnnotation()]));
  })
);

// Test setup and teardown
beforeAll(() => {
  apiServer.listen({ onUnhandledRequest: 'error' });
  
  // Setup WebSocket mock
  wsServer = new WS(WS_URL);
  
  // Mock file reading
  global.FileReader = class {
    result: any = null;
    error: any = null;
    readyState: number = 0;
    onload: any = null;
    onerror: any = null;
    onabort: any = null;

    readAsDataURL(file: File) {
      this.readyState = 2;
      this.result = `data:${file.type};base64,${btoa('mock-file-content')}`;
      if (this.onload) this.onload({ target: this });
    }

    readAsArrayBuffer(file: File) {
      this.readyState = 2;
      this.result = new ArrayBuffer(8);
      if (this.onload) this.onload({ target: this });
    }
  } as any;

  // Mock HTMLVideoElement
  global.HTMLVideoElement.prototype.play = jest.fn().mockResolvedValue(undefined);
  global.HTMLVideoElement.prototype.pause = jest.fn();
  global.HTMLVideoElement.prototype.load = jest.fn();
  Object.defineProperty(global.HTMLVideoElement.prototype, 'duration', {
    writable: true,
    value: 60
  });
  Object.defineProperty(global.HTMLVideoElement.prototype, 'currentTime', {
    writable: true,
    value: 0
  });
});

afterAll(() => {
  apiServer.close();
  wsServer.close();
});

beforeEach(() => {
  // Reset WebSocket mock
  wsServer.clean();
});

afterEach(() => {
  apiServer.resetHandlers();
});

// Helper function to render with router
const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

// ============================================================================
// WORKFLOW 1: VIDEO UPLOAD & PROCESSING
// ============================================================================

describe('Video Upload & Processing Workflow', () => {
  test('should complete end-to-end video upload and processing pipeline', async () => {
    const user = userEvent.setup();

    // Render Projects page
    renderWithRouter(<Projects />);

    // Wait for projects to load
    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
    });

    // Create a new project
    const createProjectButton = screen.getByRole('button', { name: /create.*project/i });
    await user.click(createProjectButton);

    // Fill project form
    const projectNameInput = screen.getByLabelText(/project name/i);
    await user.type(projectNameInput, 'Integration Test Project');

    const projectDescInput = screen.getByLabelText(/description/i);
    await user.type(projectDescInput, 'Test project for integration testing');

    // Submit project creation
    const submitButton = screen.getByRole('button', { name: /create/i });
    await user.click(submitButton);

    // Verify project creation
    await waitFor(() => {
      expect(screen.getByText('Integration Test Project')).toBeInTheDocument();
    });

    // Navigate to video upload
    const uploadVideoButton = screen.getByRole('button', { name: /upload.*video/i });
    await user.click(uploadVideoButton);

    // Create mock video file
    const mockFile = new File(['mock video content'], 'test-video.mp4', {
      type: 'video/mp4'
    });

    // Simulate file selection
    const fileInput = screen.getByLabelText(/choose.*file/i) as HTMLInputElement;
    await user.upload(fileInput, mockFile);

    // Verify file selection
    expect(fileInput.files![0]).toBe(mockFile);
    expect(screen.getByText('test-video.mp4')).toBeInTheDocument();

    // Start upload
    const uploadButton = screen.getByRole('button', { name: /upload/i });
    await user.click(uploadButton);

    // Verify upload progress
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    // Wait for upload completion
    await waitFor(() => {
      expect(screen.getByText(/upload.*complete/i)).toBeInTheDocument();
    }, { timeout: 5000 });

    // Verify backend processing notification via WebSocket
    await wsServer.connected;
    wsServer.send(JSON.stringify({
      type: 'video_processing_status',
      data: {
        video_id: 'uploaded-video-id',
        status: 'processing',
        progress_percentage: 50
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/processing.*50%/i)).toBeInTheDocument();
    });

    // Complete processing
    wsServer.send(JSON.stringify({
      type: 'video_processing_status',
      data: {
        video_id: 'uploaded-video-id',
        status: 'completed',
        progress_percentage: 100
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/processing.*complete/i)).toBeInTheDocument();
    });
  });

  test('should handle upload errors gracefully', async () => {
    const user = userEvent.setup();

    // Mock upload failure
    apiServer.use(
      rest.post(`${API_BASE_URL}/api/videos/upload`, (req, res, ctx) => {
        return res(ctx.status(400), ctx.json({ detail: 'Upload failed' }));
      })
    );

    renderWithRouter(<Projects />);

    // Attempt upload
    const uploadButton = screen.getByRole('button', { name: /upload.*video/i });
    await user.click(uploadButton);

    const mockFile = new File(['mock content'], 'invalid-file.txt', {
      type: 'text/plain'
    });

    const fileInput = screen.getByLabelText(/choose.*file/i);
    await user.upload(fileInput, mockFile);

    const submitButton = screen.getByRole('button', { name: /upload/i });
    await user.click(submitButton);

    // Verify error handling
    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
    });

    // Verify retry functionality
    const retryButton = screen.getByRole('button', { name: /retry/i });
    expect(retryButton).toBeInTheDocument();
  });

  test('should validate video format and size limits', async () => {
    const user = userEvent.setup();
    
    renderWithRouter(<Projects />);

    const uploadButton = screen.getByRole('button', { name: /upload.*video/i });
    await user.click(uploadButton);

    // Test invalid file type
    const invalidFile = new File(['content'], 'document.pdf', {
      type: 'application/pdf'
    });

    const fileInput = screen.getByLabelText(/choose.*file/i);
    await user.upload(fileInput, invalidFile);

    await waitFor(() => {
      expect(screen.getByText(/unsupported.*file.*type/i)).toBeInTheDocument();
    });

    // Test file size limit
    const largeFile = new File(['x'.repeat(100 * 1024 * 1024)], 'large-video.mp4', {
      type: 'video/mp4'
    });

    await user.upload(fileInput, largeFile);

    await waitFor(() => {
      expect(screen.getByText(/file.*too.*large/i)).toBeInTheDocument();
    });
  });
});

// ============================================================================
// WORKFLOW 2: ANNOTATION WORKFLOW
// ============================================================================

describe('Annotation Workflow', () => {
  test('should create and manage video annotations end-to-end', async () => {
    const user = userEvent.setup();
    const mockVideo = createMockVideo();

    // Render video player with annotation tools
    render(
      <AccessibleVideoPlayer
        video={mockVideo}
        annotations={[]}
        annotationMode={true}
        frameRate={30}
        onAnnotationSelect={jest.fn()}
        onTimeUpdate={jest.fn()}
        onCanvasClick={jest.fn()}
      />
    );

    // Wait for video to load
    await waitFor(() => {
      expect(screen.getByRole('video')).toBeInTheDocument();
    });

    // Enter annotation mode
    const annotationButton = screen.getByRole('button', { name: /annotation.*mode/i });
    await user.click(annotationButton);

    // Verify annotation tools are available
    expect(screen.getByRole('button', { name: /rectangle/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /circle/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /polygon/i })).toBeInTheDocument();

    // Create rectangle annotation
    const rectangleButton = screen.getByRole('button', { name: /rectangle/i });
    await user.click(rectangleButton);

    // Simulate canvas click for annotation creation
    const canvas = screen.getByRole('img', { name: /video.*canvas/i });
    fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100 });
    fireEvent.mouseMove(canvas, { clientX: 200, clientY: 200 });
    fireEvent.mouseUp(canvas, { clientX: 200, clientY: 200 });

    // Verify annotation creation dialog
    await waitFor(() => {
      expect(screen.getByText(/annotation.*properties/i)).toBeInTheDocument();
    });

    // Fill annotation properties
    const labelInput = screen.getByLabelText(/label/i);
    await user.type(labelInput, 'Person');

    const confidenceInput = screen.getByLabelText(/confidence/i);
    await user.clear(confidenceInput);
    await user.type(confidenceInput, '0.85');

    // Save annotation
    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    // Verify annotation persistence
    await waitFor(() => {
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('0.85')).toBeInTheDocument();
    });

    // Test annotation editing
    const annotationElement = screen.getByText('Person').closest('[role="button"]');
    await user.click(annotationElement!);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    // Modify annotation
    const editLabelInput = screen.getByDisplayValue('Person');
    await user.clear(editLabelInput);
    await user.type(editLabelInput, 'Pedestrian');

    const updateButton = screen.getByRole('button', { name: /update/i });
    await user.click(updateButton);

    // Verify update
    await waitFor(() => {
      expect(screen.getByText('Pedestrian')).toBeInTheDocument();
    });

    // Test annotation deletion
    const deleteButton = screen.getByRole('button', { name: /delete/i });
    await user.click(deleteButton);

    // Confirm deletion
    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    await user.click(confirmButton);

    // Verify deletion
    await waitFor(() => {
      expect(screen.queryByText('Pedestrian')).not.toBeInTheDocument();
    });
  });

  test('should support frame-by-frame annotation navigation', async () => {
    const user = userEvent.setup();
    const mockVideo = createMockVideo();
    const mockAnnotations = [
      createMockAnnotation({ frameNumber: 10 }),
      createMockAnnotation({ frameNumber: 20 }),
      createMockAnnotation({ frameNumber: 30 })
    ];

    const onTimeUpdate = jest.fn();
    const onAnnotationSelect = jest.fn();

    render(
      <AccessibleVideoPlayer
        video={mockVideo}
        annotations={mockAnnotations}
        annotationMode={true}
        frameRate={30}
        onAnnotationSelect={onAnnotationSelect}
        onTimeUpdate={onTimeUpdate}
        onCanvasClick={jest.fn()}
      />
    );

    // Navigate to frame with annotation
    const frameInput = screen.getByLabelText(/frame.*number/i);
    await user.clear(frameInput);
    await user.type(frameInput, '10');

    // Jump to frame
    const goToFrameButton = screen.getByRole('button', { name: /go.*to.*frame/i });
    await user.click(goToFrameButton);

    // Verify frame navigation
    expect(onTimeUpdate).toHaveBeenCalledWith(expect.any(Number), 10);

    // Navigate between annotation frames
    const nextAnnotationButton = screen.getByRole('button', { name: /next.*annotation/i });
    await user.click(nextAnnotationButton);

    // Verify navigation to next annotation
    expect(onTimeUpdate).toHaveBeenCalledWith(expect.any(Number), 20);

    const prevAnnotationButton = screen.getByRole('button', { name: /previous.*annotation/i });
    await user.click(prevAnnotationButton);

    // Verify navigation to previous annotation
    expect(onTimeUpdate).toHaveBeenCalledWith(expect.any(Number), 10);
  });

  test('should export annotations in multiple formats', async () => {
    const user = userEvent.setup();
    
    // Mock annotation export endpoint
    apiServer.use(
      rest.post(`${API_BASE_URL}/api/annotations/export`, (req, res, ctx) => {
        return res(
          ctx.set('Content-Type', 'application/json'),
          ctx.set('Content-Disposition', 'attachment; filename="annotations.json"'),
          ctx.json({
            format: 'COCO',
            annotations: [createMockAnnotation()],
            metadata: {
              video_id: 'test-video',
              export_timestamp: new Date().toISOString()
            }
          })
        );
      })
    );

    renderWithRouter(<Projects />);

    // Navigate to annotations export
    const exportButton = screen.getByRole('button', { name: /export.*annotations/i });
    await user.click(exportButton);

    // Select export format
    const formatSelect = screen.getByLabelText(/export.*format/i);
    await user.click(formatSelect);
    
    const cocoOption = screen.getByText('COCO');
    await user.click(cocoOption);

    // Configure export options
    const includeMetadataCheckbox = screen.getByLabelText(/include.*metadata/i);
    await user.click(includeMetadataCheckbox);

    // Start export
    const startExportButton = screen.getByRole('button', { name: /start.*export/i });
    await user.click(startExportButton);

    // Verify export completion
    await waitFor(() => {
      expect(screen.getByText(/export.*complete/i)).toBeInTheDocument();
    });

    // Verify download link
    const downloadLink = screen.getByRole('link', { name: /download/i });
    expect(downloadLink).toHaveAttribute('href', expect.stringContaining('annotations'));
  });
});

// ============================================================================
// WORKFLOW 3: TEST EXECUTION WORKFLOW
// ============================================================================

describe('Test Execution Workflow', () => {
  test('should execute complete test session with real-time monitoring', async () => {
    const user = userEvent.setup();
    const mockProject = createMockProject();
    const mockVideos = [createMockVideo(), createMockVideo({ id: '2' })];

    // Mock test session endpoints
    apiServer.use(
      rest.post(`${API_BASE_URL}/api/test-sessions`, (req, res, ctx) => {
        return res(ctx.json(createMockTestSession({ status: 'running' })));
      }),
      rest.get(`${API_BASE_URL}/api/test-sessions/:id/status`, (req, res, ctx) => {
        return res(ctx.json({ 
          status: 'running',
          progress: 45,
          current_video: 1,
          total_videos: 2
        }));
      })
    );

    render(<TestExecution />);

    // Configure test session
    const projectSelect = screen.getByLabelText(/project/i);
    await user.click(projectSelect);
    await user.click(screen.getByText(mockProject.name));

    // Configure test parameters
    const latencyThresholdInput = screen.getByLabelText(/latency.*threshold/i);
    await user.clear(latencyThresholdInput);
    await user.type(latencyThresholdInput, '100');

    const accuracyThresholdInput = screen.getByLabelText(/accuracy.*threshold/i);
    await user.clear(accuracyThresholdInput);
    await user.type(accuracyThresholdInput, '0.9');

    // Enable real-time monitoring
    const realtimeCheckbox = screen.getByLabelText(/real.*time.*monitoring/i);
    await user.click(realtimeCheckbox);

    // Start test execution
    const startTestButton = screen.getByRole('button', { name: /start.*test/i });
    await user.click(startTestButton);

    // Verify test session creation
    await waitFor(() => {
      expect(screen.getByText(/test.*session.*created/i)).toBeInTheDocument();
    });

    // Wait for WebSocket connection
    await wsServer.connected;

    // Simulate real-time test progress updates
    wsServer.send(JSON.stringify({
      type: 'test_session_update',
      data: {
        test_session_id: 'test-session-id',
        status: 'running',
        current_detections: 5,
        progress_percentage: 25,
        metrics: {
          accuracy: 0.92,
          latency_avg: 85,
          throughput: 15
        }
      }
    }));

    // Verify real-time updates
    await waitFor(() => {
      expect(screen.getByText(/25%/)).toBeInTheDocument();
      expect(screen.getByText(/accuracy.*0.92/i)).toBeInTheDocument();
      expect(screen.getByText(/latency.*85/i)).toBeInTheDocument();
    });

    // Simulate detection events
    wsServer.send(JSON.stringify({
      type: 'detection_event',
      data: {
        test_session_id: 'test-session-id',
        detection_id: 'detection-1',
        timestamp: Date.now(),
        confidence: 0.95,
        validation_result: 'TP',
        latency_ms: 75
      }
    }));

    // Verify detection display
    await waitFor(() => {
      expect(screen.getByText(/true positive/i)).toBeInTheDocument();
      expect(screen.getByText(/0.95/)).toBeInTheDocument();
      expect(screen.getByText(/75.*ms/i)).toBeInTheDocument();
    });

    // Complete test session
    wsServer.send(JSON.stringify({
      type: 'test_session_complete',
      data: {
        test_session_id: 'test-session-id',
        status: 'completed',
        final_metrics: {
          total_detections: 25,
          true_positives: 20,
          false_positives: 3,
          false_negatives: 2,
          accuracy: 0.91,
          precision: 0.87,
          recall: 0.91,
          f1_score: 0.89,
          avg_latency: 78,
          max_latency: 120,
          pass_fail_result: 'PASS'
        }
      }
    }));

    // Verify test completion
    await waitFor(() => {
      expect(screen.getByText(/test.*completed/i)).toBeInTheDocument();
      expect(screen.getByText(/PASS/i)).toBeInTheDocument();
      expect(screen.getByText(/91%/)).toBeInTheDocument();
    });

    // Verify results export options
    expect(screen.getByRole('button', { name: /export.*results/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate.*report/i })).toBeInTheDocument();
  });

  test('should handle test session failures and recovery', async () => {
    const user = userEvent.setup();

    // Mock test session failure
    apiServer.use(
      rest.post(`${API_BASE_URL}/api/test-sessions`, (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ detail: 'Test execution failed' }));
      })
    );

    render(<TestExecution />);

    // Configure and start test
    const startTestButton = screen.getByRole('button', { name: /start.*test/i });
    await user.click(startTestButton);

    // Verify error handling
    await waitFor(() => {
      expect(screen.getByText(/test.*execution.*failed/i)).toBeInTheDocument();
    });

    // Verify recovery options
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /diagnose/i })).toBeInTheDocument();

    // Test retry functionality
    apiServer.use(
      rest.post(`${API_BASE_URL}/api/test-sessions`, (req, res, ctx) => {
        return res(ctx.json(createMockTestSession()));
      })
    );

    const retryButton = screen.getByRole('button', { name: /retry/i });
    await user.click(retryButton);

    // Verify successful retry
    await waitFor(() => {
      expect(screen.getByText(/test.*session.*created/i)).toBeInTheDocument();
    });
  });

  test('should validate signal processing workflow', async () => {
    const user = userEvent.setup();

    // Mock signal validation endpoints
    apiServer.use(
      rest.post(`${API_BASE_URL}/api/signal-validation/process`, (req, res, ctx) => {
        return res(ctx.json({
          signal_id: 'signal-123',
          processing_status: 'completed',
          detected_signals: [
            {
              timestamp: 1.5,
              signal_type: 'pedestrian_crossing',
              confidence: 0.92,
              metadata: { x: 100, y: 200, width: 50, height: 80 }
            }
          ],
          validation_results: {
            latency_ms: 65,
            accuracy: 0.94,
            meets_criteria: true
          }
        }));
      })
    );

    render(<TestExecution />);

    // Enable signal processing
    const signalProcessingCheckbox = screen.getByLabelText(/signal.*processing/i);
    await user.click(signalProcessingCheckbox);

    // Configure signal type
    const signalTypeSelect = screen.getByLabelText(/signal.*type/i);
    await user.click(signalTypeSelect);
    await user.click(screen.getByText('Pedestrian Crossing'));

    // Set latency threshold
    const latencyInput = screen.getByLabelText(/signal.*latency/i);
    await user.clear(latencyInput);
    await user.type(latencyInput, '100');

    // Start signal validation
    const validateButton = screen.getByRole('button', { name: /validate.*signals/i });
    await user.click(validateButton);

    // Wait for processing
    await waitFor(() => {
      expect(screen.getByText(/processing.*signals/i)).toBeInTheDocument();
    });

    // Verify results
    await waitFor(() => {
      expect(screen.getByText(/signal.*detected/i)).toBeInTheDocument();
      expect(screen.getByText(/65.*ms/i)).toBeInTheDocument();
      expect(screen.getByText(/94%/i)).toBeInTheDocument();
      expect(screen.getByText(/criteria.*met/i)).toBeInTheDocument();
    });
  });
});

// ============================================================================
// WORKFLOW 4: REAL-TIME COMMUNICATION
// ============================================================================

describe('Real-time Communication', () => {
  test('should maintain WebSocket connection health and handle reconnection', async () => {
    const user = userEvent.setup();

    render(<TestExecution />);

    // Wait for WebSocket connection
    await wsServer.connected;

    // Verify connection status indicator
    await waitFor(() => {
      expect(screen.getByTestId('websocket-status')).toHaveAttribute('data-status', 'connected');
    });

    // Simulate connection loss
    wsServer.close();

    // Verify disconnection handling
    await waitFor(() => {
      expect(screen.getByTestId('websocket-status')).toHaveAttribute('data-status', 'disconnected');
      expect(screen.getByText(/connection.*lost/i)).toBeInTheDocument();
    });

    // Verify reconnection attempt
    await waitFor(() => {
      expect(screen.getByText(/reconnecting/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Simulate successful reconnection
    wsServer = new WS(WS_URL);
    await wsServer.connected;

    // Verify reconnection success
    await waitFor(() => {
      expect(screen.getByTestId('websocket-status')).toHaveAttribute('data-status', 'connected');
      expect(screen.getByText(/reconnected/i)).toBeInTheDocument();
    });
  });

  test('should synchronize data across multiple components', async () => {
    const user = userEvent.setup();

    // Render multiple components that use WebSocket
    render(
      <BrowserRouter>
        <div>
          <TestExecution />
          <Projects />
        </div>
      </BrowserRouter>
    );

    await wsServer.connected;

    // Send project update via WebSocket
    wsServer.send(JSON.stringify({
      type: 'project_updated',
      data: {
        project_id: 'project-123',
        name: 'Updated Project Name',
        status: 'active',
        video_count: 5
      }
    }));

    // Verify both components receive update
    await waitFor(() => {
      const projectElements = screen.getAllByText('Updated Project Name');
      expect(projectElements.length).toBeGreaterThan(0);
    });

    // Send detection event update
    wsServer.send(JSON.stringify({
      type: 'detection_event',
      data: {
        test_session_id: 'session-123',
        detection_count: 10,
        latest_detection: {
          id: 'det-456',
          confidence: 0.88,
          validation_result: 'TP'
        }
      }
    }));

    // Verify real-time counter updates
    await waitFor(() => {
      expect(screen.getByText(/10.*detections/i)).toBeInTheDocument();
    });
  });

  test('should handle message queuing during connection outages', async () => {
    const user = userEvent.setup();

    render(<TestExecution />);
    await wsServer.connected;

    // Start a test session
    const startButton = screen.getByRole('button', { name: /start.*test/i });
    await user.click(startButton);

    // Disconnect WebSocket
    wsServer.close();

    // Try to send updates while disconnected
    // These should be queued
    await user.click(screen.getByRole('button', { name: /pause.*test/i }));
    await user.click(screen.getByRole('button', { name: /resume.*test/i }));

    // Reconnect
    wsServer = new WS(WS_URL);
    await wsServer.connected;

    // Verify queued messages are sent
    await waitFor(() => {
      expect(wsServer).toHaveReceivedMessages([
        expect.stringContaining('pause'),
        expect.stringContaining('resume')
      ]);
    });
  });

  test('should provide real-time performance monitoring', async () => {
    render(<TestExecution />);
    await wsServer.connected;

    // Send performance metrics
    wsServer.send(JSON.stringify({
      type: 'performance_metrics',
      data: {
        cpu_usage: 65.5,
        memory_usage: 78.2,
        gpu_usage: 45.8,
        processing_fps: 28.5,
        detection_latency: 82,
        network_latency: 15
      }
    }));

    // Verify metrics display
    await waitFor(() => {
      expect(screen.getByText(/cpu.*65.5%/i)).toBeInTheDocument();
      expect(screen.getByText(/memory.*78.2%/i)).toBeInTheDocument();
      expect(screen.getByText(/28.5.*fps/i)).toBeInTheDocument();
      expect(screen.getByText(/82.*ms/i)).toBeInTheDocument();
    });

    // Send alert for high resource usage
    wsServer.send(JSON.stringify({
      type: 'system_alert',
      data: {
        alert_type: 'high_cpu_usage',
        severity: 'warning',
        message: 'CPU usage exceeds 90%',
        timestamp: new Date().toISOString()
      }
    }));

    // Verify alert display
    await waitFor(() => {
      expect(screen.getByText(/cpu.*usage.*exceeds.*90%/i)).toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveClass('MuiAlert-standardWarning');
    });
  });
});

// ============================================================================
// CROSS-COMPONENT SYNCHRONIZATION TESTS
// ============================================================================

describe('Cross-Component Synchronization', () => {
  test('should maintain data consistency across page navigation', async () => {
    const user = userEvent.setup();

    renderWithRouter(<App />);
    await wsServer.connected;

    // Navigate to projects page
    const projectsLink = screen.getByRole('link', { name: /projects/i });
    await user.click(projectsLink);

    // Create project
    const createButton = screen.getByRole('button', { name: /create.*project/i });
    await user.click(createButton);

    // Fill project details
    await user.type(screen.getByLabelText(/project name/i), 'Sync Test Project');
    await user.click(screen.getByRole('button', { name: /create/i }));

    // Navigate to test execution
    const testLink = screen.getByRole('link', { name: /test.*execution/i });
    await user.click(testLink);

    // Verify project appears in dropdown
    const projectSelect = screen.getByLabelText(/project/i);
    await user.click(projectSelect);
    
    await waitFor(() => {
      expect(screen.getByText('Sync Test Project')).toBeInTheDocument();
    });

    // Navigate back to projects
    const backToProjectsLink = screen.getByRole('link', { name: /projects/i });
    await user.click(backToProjectsLink);

    // Verify project still exists
    await waitFor(() => {
      expect(screen.getByText('Sync Test Project')).toBeInTheDocument();
    });
  });

  test('should handle concurrent user actions across components', async () => {
    const user = userEvent.setup();
    
    // Mock concurrent operation endpoints
    let uploadCount = 0;
    apiServer.use(
      rest.post(`${API_BASE_URL}/api/videos/upload`, (req, res, ctx) => {
        uploadCount++;
        return res(ctx.json({
          id: `video-${uploadCount}`,
          filename: `concurrent-upload-${uploadCount}.mp4`,
          status: 'processing'
        }));
      })
    );

    renderWithRouter(<Projects />);
    await wsServer.connected;

    // Simulate multiple concurrent uploads
    const uploadButtons = screen.getAllByRole('button', { name: /upload.*video/i });
    
    // Start multiple uploads simultaneously
    await Promise.all([
      user.click(uploadButtons[0]),
      user.click(uploadButtons[0]),
      user.click(uploadButtons[0])
    ]);

    // Verify each upload is handled independently
    await waitFor(() => {
      expect(screen.getByText('concurrent-upload-1.mp4')).toBeInTheDocument();
      expect(screen.getByText('concurrent-upload-2.mp4')).toBeInTheDocument();
      expect(screen.getByText('concurrent-upload-3.mp4')).toBeInTheDocument();
    });

    // Verify progress tracking for each upload
    wsServer.send(JSON.stringify({
      type: 'video_processing_status',
      data: {
        video_id: 'video-1',
        status: 'processing',
        progress_percentage: 30
      }
    }));

    wsServer.send(JSON.stringify({
      type: 'video_processing_status',
      data: {
        video_id: 'video-2',
        status: 'processing',
        progress_percentage: 60
      }
    }));

    // Verify independent progress tracking
    await waitFor(() => {
      expect(screen.getByText(/30%/)).toBeInTheDocument();
      expect(screen.getByText(/60%/)).toBeInTheDocument();
    });
  });

  test('should propagate state changes through component hierarchy', async () => {
    const user = userEvent.setup();

    renderWithRouter(<App />);
    await wsServer.connected;

    // Change global settings that affect multiple components
    const settingsButton = screen.getByRole('button', { name: /settings/i });
    await user.click(settingsButton);

    // Enable debug mode
    const debugModeCheckbox = screen.getByLabelText(/debug.*mode/i);
    await user.click(debugModeCheckbox);

    // Apply settings
    const applyButton = screen.getByRole('button', { name: /apply/i });
    await user.click(applyButton);

    // Verify debug information appears in child components
    await waitFor(() => {
      expect(screen.getByTestId('debug-info')).toBeInTheDocument();
    });

    // Navigate to different pages and verify debug mode persists
    await user.click(screen.getByRole('link', { name: /projects/i }));
    expect(screen.getByTestId('debug-info')).toBeInTheDocument();

    await user.click(screen.getByRole('link', { name: /test.*execution/i }));
    expect(screen.getByTestId('debug-info')).toBeInTheDocument();
  });
});
