/**
 * Dataset Management UI Tests
 * Tests for CRUD operations and file handling in dataset management
 */

import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { jest } from '@jest/globals';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { BrowserRouter } from 'react-router-dom';

// Mock drag and drop API
Object.defineProperty(window, 'DataTransfer', {
  value: class DataTransfer {
    constructor() {
      this.files = [];
      this.items = [];
      this.types = [];
    }
  }
});

// Mock modules
jest.mock('../../../src/services/api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock('../../../src/services/websocketService', () => ({
  __esModule: true,
  default: {
    connect: jest.fn(),
    disconnect: jest.fn(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
  },
}));

// Import components after mocking
import Datasets from '../../../src/pages/Datasets';
import Projects from '../../../src/pages/Projects';
import ProjectDetail from '../../../src/pages/ProjectDetail';
import apiService from '../../../src/services/api';

const theme = createTheme();

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={theme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('Dataset Management UI Tests', () => {
  let mockApiService: jest.Mocked<typeof apiService>;

  beforeEach(() => {
    mockApiService = apiService as jest.Mocked<typeof apiService>;
    jest.clearAllMocks();
    
    // Default mock implementations
    mockApiService.get.mockResolvedValue({ data: [] });
    mockApiService.post.mockResolvedValue({ data: {} });
    mockApiService.put.mockResolvedValue({ data: {} });
    mockApiService.delete.mockResolvedValue({ data: {} });
  });

  describe('Project Management', () => {
    const mockProjects = [
      {
        id: 'project-1',
        name: 'Highway Monitoring',
        description: 'Traffic monitoring on main highway',
        camera_model: 'HIKVISION DS-2CD2T47G1',
        camera_view: 'Front-facing VRU',
        signal_type: 'GPIO',
        status: 'Active',
        created_at: '2024-01-01T10:00:00Z',
        video_count: 15,
        detection_count: 1250
      },
      {
        id: 'project-2',
        name: 'Parking Lot Security',
        description: 'Security monitoring for parking areas',
        camera_model: 'AXIS P1448-LE',
        camera_view: 'Rear-facing VRU',
        signal_type: 'Network Packet',
        status: 'Draft',
        created_at: '2024-01-02T14:30:00Z',
        video_count: 8,
        detection_count: 0
      }
    ];

    beforeEach(() => {
      mockApiService.get.mockImplementation((url) => {
        if (url.includes('/projects')) {
          return Promise.resolve({ data: mockProjects });
        }
        return Promise.resolve({ data: [] });
      });
    });

    test('displays list of projects correctly', async () => {
      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
        expect(screen.getByText('Parking Lot Security')).toBeInTheDocument();
        expect(screen.getByText('15 videos')).toBeInTheDocument();
        expect(screen.getByText('1,250 detections')).toBeInTheDocument();
      });
    });

    test('creates new project successfully', async () => {
      const user = userEvent.setup();
      
      mockApiService.post.mockResolvedValue({
        data: {
          id: 'project-3',
          name: 'New Test Project',
          status: 'Active'
        }
      });

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      // Click create project button
      const createButton = screen.getByRole('button', { name: /create project/i });
      await user.click(createButton);

      // Fill out form
      await user.type(screen.getByLabelText(/project name/i), 'New Test Project');
      await user.type(screen.getByLabelText(/description/i), 'Test project description');
      await user.selectOptions(screen.getByLabelText(/camera model/i), 'HIKVISION DS-2CD2T47G1');
      await user.selectOptions(screen.getByLabelText(/camera view/i), 'Front-facing VRU');
      await user.selectOptions(screen.getByLabelText(/signal type/i), 'GPIO');

      // Submit form
      const submitButton = screen.getByRole('button', { name: /create/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledWith('/api/projects', {
          name: 'New Test Project',
          description: 'Test project description',
          camera_model: 'HIKVISION DS-2CD2T47G1',
          camera_view: 'Front-facing VRU',
          signal_type: 'GPIO'
        });
      });
    });

    test('validates project creation form', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      const createButton = screen.getByRole('button', { name: /create project/i });
      await user.click(createButton);

      // Try to submit without filling required fields
      const submitButton = screen.getByRole('button', { name: /create/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/project name is required/i)).toBeInTheDocument();
        expect(screen.getByText(/camera model is required/i)).toBeInTheDocument();
      });
    });

    test('edits existing project', async () => {
      const user = userEvent.setup();
      
      mockApiService.put.mockResolvedValue({
        data: {
          ...mockProjects[0],
          name: 'Updated Highway Monitoring'
        }
      });

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
      });

      // Click edit button for first project
      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      await user.click(editButtons[0]);

      // Update project name
      const nameInput = screen.getByDisplayValue('Highway Monitoring');
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Highway Monitoring');

      // Save changes
      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockApiService.put).toHaveBeenCalledWith(
          `/api/projects/${mockProjects[0].id}`,
          expect.objectContaining({
            name: 'Updated Highway Monitoring'
          })
        );
      });
    });

    test('deletes project with confirmation', async () => {
      const user = userEvent.setup();
      
      mockApiService.delete.mockResolvedValue({ data: {} });

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
      });

      // Click delete button
      const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
      await user.click(deleteButtons[0]);

      // Confirm deletion
      const confirmButton = screen.getByRole('button', { name: /confirm delete/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockApiService.delete).toHaveBeenCalledWith(`/api/projects/${mockProjects[0].id}`);
      });
    });

    test('filters projects by status', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
        expect(screen.getByText('Parking Lot Security')).toBeInTheDocument();
      });

      // Filter by Active status
      const statusFilter = screen.getByLabelText(/filter by status/i);
      await user.selectOptions(statusFilter, 'Active');

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
        expect(screen.queryByText('Parking Lot Security')).not.toBeInTheDocument();
      });
    });

    test('searches projects by name', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
        expect(screen.getByText('Parking Lot Security')).toBeInTheDocument();
      });

      // Search for "Highway"
      const searchInput = screen.getByPlaceholderText(/search projects/i);
      await user.type(searchInput, 'Highway');

      await waitFor(() => {
        expect(screen.getByText('Highway Monitoring')).toBeInTheDocument();
        expect(screen.queryByText('Parking Lot Security')).not.toBeInTheDocument();
      });
    });
  });

  describe('Video Management', () => {
    const mockVideos = [
      {
        id: 'video-1',
        filename: 'highway_cam_001.mp4',
        file_size: 52428800, // 50MB
        duration: 120.5,
        fps: 30,
        resolution: '1920x1080',
        status: 'uploaded',
        processing_status: 'completed',
        ground_truth_generated: true,
        created_at: '2024-01-01T10:00:00Z'
      },
      {
        id: 'video-2',
        filename: 'highway_cam_002.mp4',
        file_size: 67108864, // 64MB
        duration: 95.2,
        fps: 25,
        resolution: '1280x720',
        status: 'uploaded',
        processing_status: 'pending',
        ground_truth_generated: false,
        created_at: '2024-01-01T11:00:00Z'
      }
    ];

    beforeEach(() => {
      mockApiService.get.mockImplementation((url) => {
        if (url.includes('/videos')) {
          return Promise.resolve({ data: mockVideos });
        }
        if (url.includes('/projects/project-1')) {
          return Promise.resolve({
            data: {
              id: 'project-1',
              name: 'Highway Monitoring',
              videos: mockVideos
            }
          });
        }
        return Promise.resolve({ data: [] });
      });
    });

    test('displays video list in project detail', async () => {
      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('highway_cam_001.mp4')).toBeInTheDocument();
        expect(screen.getByText('highway_cam_002.mp4')).toBeInTheDocument();
        expect(screen.getByText('50.0 MB')).toBeInTheDocument();
        expect(screen.getByText('2:00')).toBeInTheDocument(); // Duration formatted
      });
    });

    test('uploads single video file', async () => {
      const user = userEvent.setup();
      
      const mockFile = new File(['video content'], 'test_video.mp4', {
        type: 'video/mp4'
      });

      mockApiService.post.mockResolvedValue({
        data: {
          id: 'video-3',
          filename: 'test_video.mp4',
          status: 'uploaded'
        }
      });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      // Upload video file
      const fileInput = screen.getByLabelText(/upload video/i);
      await user.upload(fileInput, mockFile);

      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledWith(
          '/api/videos/upload',
          expect.any(FormData),
          expect.objectContaining({
            headers: expect.objectContaining({
              'Content-Type': 'multipart/form-data'
            })
          })
        );
      });
    });

    test('uploads multiple video files', async () => {
      const user = userEvent.setup();
      
      const mockFiles = [
        new File(['video 1'], 'video1.mp4', { type: 'video/mp4' }),
        new File(['video 2'], 'video2.mp4', { type: 'video/mp4' }),
        new File(['video 3'], 'video3.mp4', { type: 'video/mp4' })
      ];

      mockApiService.post.mockResolvedValue({
        data: {
          uploaded_count: 3,
          failed_count: 0
        }
      });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      const fileInput = screen.getByLabelText(/upload video/i);
      await user.upload(fileInput, mockFiles);

      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledTimes(3);
      });
    });

    test('validates video file format', async () => {
      const user = userEvent.setup();
      
      const invalidFile = new File(['text content'], 'document.txt', {
        type: 'text/plain'
      });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      const fileInput = screen.getByLabelText(/upload video/i);
      await user.upload(fileInput, invalidFile);

      await waitFor(() => {
        expect(screen.getByText(/invalid file format/i)).toBeInTheDocument();
      });
    });

    test('handles large file upload with progress', async () => {
      const user = userEvent.setup();
      
      const largeFile = new File(['x'.repeat(100000000)], 'large_video.mp4', {
        type: 'video/mp4'
      });

      // Mock progress tracking
      let progressCallback: (event: any) => void;
      mockApiService.post.mockImplementation((url, data, config) => {
        if (config?.onUploadProgress) {
          progressCallback = config.onUploadProgress;
          // Simulate progress updates
          setTimeout(() => progressCallback({ loaded: 25000000, total: 100000000 }), 100);
          setTimeout(() => progressCallback({ loaded: 50000000, total: 100000000 }), 200);
          setTimeout(() => progressCallback({ loaded: 100000000, total: 100000000 }), 300);
        }
        return Promise.resolve({ data: { id: 'video-large', filename: 'large_video.mp4' } });
      });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      const fileInput = screen.getByLabelText(/upload video/i);
      await user.upload(fileInput, largeFile);

      // Check for progress indicator
      await waitFor(() => {
        expect(screen.getByRole('progressbar')).toBeInTheDocument();
      });

      // Wait for completion
      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      }, { timeout: 5000 });
    });

    test('supports drag and drop upload', async () => {
      const mockFile = new File(['video content'], 'dropped_video.mp4', {
        type: 'video/mp4'
      });

      mockApiService.post.mockResolvedValue({
        data: { id: 'video-dropped', filename: 'dropped_video.mp4' }
      });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      const dropZone = screen.getByTestId('video-drop-zone');
      
      // Simulate drag and drop
      const dragEnterEvent = new Event('dragenter', { bubbles: true });
      Object.defineProperty(dragEnterEvent, 'dataTransfer', {
        value: { files: [mockFile] }
      });
      
      const dropEvent = new Event('drop', { bubbles: true });
      Object.defineProperty(dropEvent, 'dataTransfer', {
        value: { files: [mockFile] }
      });

      fireEvent(dropZone, dragEnterEvent);
      fireEvent(dropZone, dropEvent);

      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalled();
      });
    });

    test('deletes video with confirmation', async () => {
      const user = userEvent.setup();
      
      mockApiService.delete.mockResolvedValue({ data: {} });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('highway_cam_001.mp4')).toBeInTheDocument();
      });

      // Click delete button for first video
      const deleteButtons = screen.getAllByRole('button', { name: /delete video/i });
      await user.click(deleteButtons[0]);

      // Confirm deletion
      const confirmButton = screen.getByRole('button', { name: /confirm delete/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockApiService.delete).toHaveBeenCalledWith(`/api/videos/${mockVideos[0].id}`);
      });
    });

    test('filters videos by processing status', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('highway_cam_001.mp4')).toBeInTheDocument();
        expect(screen.getByText('highway_cam_002.mp4')).toBeInTheDocument();
      });

      // Filter by completed status
      const statusFilter = screen.getByLabelText(/filter by processing status/i);
      await user.selectOptions(statusFilter, 'completed');

      await waitFor(() => {
        expect(screen.getByText('highway_cam_001.mp4')).toBeInTheDocument();
        expect(screen.queryByText('highway_cam_002.mp4')).not.toBeInTheDocument();
      });
    });

    test('sorts videos by different criteria', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('highway_cam_001.mp4')).toBeInTheDocument();
      });

      // Sort by file size
      const sortSelect = screen.getByLabelText(/sort by/i);
      await user.selectOptions(sortSelect, 'file_size');

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith(
          expect.stringContaining('/videos'),
          expect.objectContaining({
            params: expect.objectContaining({
              sort_by: 'file_size'
            })
          })
        );
      });
    });
  });

  describe('Ground Truth Management', () => {
    const mockGroundTruth = [
      {
        id: 'gt-1',
        video_id: 'video-1',
        timestamp: 15.5,
        frame_number: 465,
        class_label: 'person',
        x: 100,
        y: 150,
        width: 80,
        height: 200,
        confidence: 1.0,
        validated: true
      },
      {
        id: 'gt-2',
        video_id: 'video-1',
        timestamp: 23.2,
        frame_number: 696,
        class_label: 'car',
        x: 300,
        y: 200,
        width: 150,
        height: 100,
        confidence: 1.0,
        validated: false
      }
    ];

    beforeEach(() => {
      mockApiService.get.mockImplementation((url) => {
        if (url.includes('/ground-truth')) {
          return Promise.resolve({ data: mockGroundTruth });
        }
        return Promise.resolve({ data: [] });
      });
    });

    test('displays ground truth annotations', async () => {
      render(
        <TestWrapper>
          <Datasets />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('person')).toBeInTheDocument();
        expect(screen.getByText('car')).toBeInTheDocument();
        expect(screen.getByText('15.5s')).toBeInTheDocument();
        expect(screen.getByText('Validated')).toBeInTheDocument();
        expect(screen.getByText('Pending')).toBeInTheDocument();
      });
    });

    test('creates new ground truth annotation', async () => {
      const user = userEvent.setup();
      
      mockApiService.post.mockResolvedValue({
        data: {
          id: 'gt-3',
          class_label: 'bicycle',
          timestamp: 30.0
        }
      });

      render(
        <TestWrapper>
          <Datasets />
        </TestWrapper>
      );

      // Click add annotation button
      const addButton = screen.getByRole('button', { name: /add annotation/i });
      await user.click(addButton);

      // Fill annotation form
      await user.selectOptions(screen.getByLabelText(/class label/i), 'bicycle');
      await user.type(screen.getByLabelText(/timestamp/i), '30.0');
      await user.type(screen.getByLabelText(/x coordinate/i), '250');
      await user.type(screen.getByLabelText(/y coordinate/i), '300');
      await user.type(screen.getByLabelText(/width/i), '100');
      await user.type(screen.getByLabelText(/height/i), '80');

      // Submit annotation
      const submitButton = screen.getByRole('button', { name: /save annotation/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledWith(
          '/api/ground-truth',
          expect.objectContaining({
            class_label: 'bicycle',
            timestamp: 30.0,
            x: 250,
            y: 300,
            width: 100,
            height: 80
          })
        );
      });
    });

    test('validates ground truth annotation', async () => {
      const user = userEvent.setup();
      
      mockApiService.put.mockResolvedValue({
        data: { ...mockGroundTruth[1], validated: true }
      });

      render(
        <TestWrapper>
          <Datasets />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Pending')).toBeInTheDocument();
      });

      // Click validate button for unvalidated annotation
      const validateButtons = screen.getAllByRole('button', { name: /validate/i });
      await user.click(validateButtons[0]);

      await waitFor(() => {
        expect(mockApiService.put).toHaveBeenCalledWith(
          `/api/ground-truth/${mockGroundTruth[1].id}`,
          expect.objectContaining({
            validated: true
          })
        );
      });
    });

    test('exports ground truth data', async () => {
      const user = userEvent.setup();
      
      const mockBlob = new Blob(['annotation data'], { type: 'application/json' });
      mockApiService.get.mockResolvedValue({
        data: mockBlob,
        headers: { 'content-type': 'application/json' }
      });

      render(
        <TestWrapper>
          <Datasets />
        </TestWrapper>
      );

      const exportButton = screen.getByRole('button', { name: /export annotations/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith(
          '/api/ground-truth/export',
          expect.objectContaining({
            params: { format: 'json' }
          })
        );
      });
    });

    test('imports ground truth data', async () => {
      const user = userEvent.setup();
      
      const mockFile = new File([JSON.stringify(mockGroundTruth)], 'annotations.json', {
        type: 'application/json'
      });

      mockApiService.post.mockResolvedValue({
        data: {
          imported_count: 2,
          skipped_count: 0,
          error_count: 0
        }
      });

      render(
        <TestWrapper>
          <Datasets />
        </TestWrapper>
      );

      const importButton = screen.getByRole('button', { name: /import annotations/i });
      await user.click(importButton);

      const fileInput = screen.getByLabelText(/select file/i);
      await user.upload(fileInput, mockFile);

      const uploadButton = screen.getByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledWith(
          '/api/ground-truth/import',
          expect.any(FormData)
        );
        expect(screen.getByText(/imported 2 annotations/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling and Edge Cases', () => {
    test('handles API errors gracefully', async () => {
      mockApiService.get.mockRejectedValue(new Error('Network error'));

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/error loading projects/i)).toBeInTheDocument();
      });

      // Test retry functionality
      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledTimes(2);
      });
    });

    test('handles empty datasets gracefully', async () => {
      mockApiService.get.mockResolvedValue({ data: [] });

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/no projects found/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /create your first project/i })).toBeInTheDocument();
      });
    });

    test('handles file upload failures', async () => {
      const user = userEvent.setup();
      
      mockApiService.post.mockRejectedValue(new Error('Upload failed'));

      const mockFile = new File(['video content'], 'test_video.mp4', {
        type: 'video/mp4'
      });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      const fileInput = screen.getByLabelText(/upload video/i);
      await user.upload(fileInput, mockFile);

      await waitFor(() => {
        expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
      });
    });

    test('validates file size limits', async () => {
      const user = userEvent.setup();
      
      // Create mock file larger than 100MB
      const largeFile = new File(['x'.repeat(200000000)], 'huge_video.mp4', {
        type: 'video/mp4'
      });

      render(
        <TestWrapper>
          <ProjectDetail />
        </TestWrapper>
      );

      const fileInput = screen.getByLabelText(/upload video/i);
      await user.upload(fileInput, largeFile);

      await waitFor(() => {
        expect(screen.getByText(/file size exceeds limit/i)).toBeInTheDocument();
      });
    });
  });

  describe('Performance and Accessibility', () => {
    test('loads data efficiently with pagination', async () => {
      const largeDataset = Array.from({ length: 100 }, (_, i) => ({
        id: `project-${i}`,
        name: `Project ${i}`,
        status: 'Active'
      }));

      mockApiService.get.mockResolvedValue({
        data: {
          items: largeDataset.slice(0, 20),
          total: 100,
          page: 1,
          per_page: 20
        }
      });

      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Project 0')).toBeInTheDocument();
        expect(screen.getByText('Project 19')).toBeInTheDocument();
        expect(screen.queryByText('Project 20')).not.toBeInTheDocument();
      });

      // Test pagination
      const nextPageButton = screen.getByRole('button', { name: /next page/i });
      fireEvent.click(nextPageButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith(
          expect.stringContaining('/projects'),
          expect.objectContaining({
            params: expect.objectContaining({
              page: 2
            })
          })
        );
      });
    });

    test('supports keyboard navigation', async () => {
      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create project/i })).toBeInTheDocument();
      });

      // Test tab navigation
      const createButton = screen.getByRole('button', { name: /create project/i });
      createButton.focus();
      expect(createButton).toHaveFocus();

      // Test enter key activation
      fireEvent.keyDown(createButton, { key: 'Enter', code: 'Enter' });
      
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    test('provides proper ARIA labels', async () => {
      render(
        <TestWrapper>
          <Projects />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/projects list/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/search projects/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/filter by status/i)).toBeInTheDocument();
      });
    });
  });
});

export {};