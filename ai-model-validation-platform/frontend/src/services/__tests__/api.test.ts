import { apiService } from '../api';
import { Project, ProjectCreate, CameraType, SignalType, ProjectStatus } from '../types';

// Mock axios
jest.mock('axios');

describe('API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Project API', () => {
    test('getProjects returns project list', async () => {
      const mockProjects: Project[] = [
        {
          id: '1',
          name: 'Test Project',
          description: 'Test Description',
          cameraModel: 'Test Camera',
          cameraView: CameraType.FRONT_FACING_VRU,
          signalType: SignalType.GPIO,
          createdAt: '2023-01-01',
          status: ProjectStatus.ACTIVE,
          testsCount: 0,
          accuracy: 95.5,
        },
      ];

      const mockGet = jest.fn().mockResolvedValue({ data: mockProjects });
      (apiService as any).api = { get: mockGet };

      const result = await apiService.getProjects();

      expect(mockGet).toHaveBeenCalledWith('/api/projects', { params: { skip: 0, limit: 100 } });
      expect(result).toEqual(mockProjects);
    });

    test('createProject creates new project', async () => {
      const newProject: ProjectCreate = {
        name: 'New Project',
        description: 'New Description',
        cameraModel: 'New Camera',
        cameraView: CameraType.FRONT_FACING_VRU,
        signalType: SignalType.GPIO,
      };

      const createdProject: Project = {
        id: '2',
        ...newProject,
        createdAt: '2023-01-01',
        status: ProjectStatus.ACTIVE,
        testsCount: 0,
        accuracy: 0,
      };

      const mockPost = jest.fn().mockResolvedValue({ data: createdProject });
      (apiService as any).api = { post: mockPost };

      const result = await apiService.createProject(newProject);

      expect(mockPost).toHaveBeenCalledWith('/api/projects', newProject);
      expect(result).toEqual(createdProject);
    });

    test('getProject returns single project', async () => {
      const mockProject: Project = {
        id: '1',
        name: 'Test Project',
        description: 'Test Description',
        cameraModel: 'Test Camera',
        cameraView: CameraType.FRONT_FACING_VRU,
        signalType: SignalType.GPIO,
        createdAt: '2023-01-01',
        status: ProjectStatus.ACTIVE,
        testsCount: 0,
        accuracy: 95.5,
      };

      const mockGet = jest.fn().mockResolvedValue({ data: mockProject });
      (apiService as any).api = { get: mockGet };

      const result = await apiService.getProject('1');

      expect(mockGet).toHaveBeenCalledWith('/api/projects/1');
      expect(result).toEqual(mockProject);
    });
  });

  describe('Dashboard API', () => {
    test('getDashboardStats returns statistics', async () => {
      const mockStats = {
        projectCount: 5,
        videoCount: 10,
        testCount: 15,
        averageAccuracy: 94.2,
        activeTests: 2,
        totalDetections: 100,
      };

      const mockGet = jest.fn().mockResolvedValue({ data: mockStats });
      (apiService as any).api = { get: mockGet };

      const result = await apiService.getDashboardStats();

      expect(mockGet).toHaveBeenCalledWith('/api/dashboard/stats');
      expect(result).toEqual(mockStats);
    });
  });

  describe('File Upload API', () => {
    test('uploadVideo uploads file with progress', async () => {
      const mockFile = new File(['test'], 'test.mp4', { type: 'video/mp4' });
      const mockResponse = {
        data: {
          id: 'video-1',
          filename: 'test.mp4',
          status: 'uploaded',
          projectId: 'project-1',
        },
      };

      const mockPost = jest.fn().mockResolvedValue(mockResponse);
      (apiService as any).api = { post: mockPost };

      const mockProgressCallback = jest.fn();
      const result = await apiService.uploadVideo('project-1', mockFile, mockProgressCallback);

      expect(mockPost).toHaveBeenCalledWith(
        '/api/projects/project-1/videos',
        expect.any(FormData),
        expect.objectContaining({
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: expect.any(Function),
        })
      );
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Error Handling', () => {
    test('handles network errors', async () => {
      const mockGet = jest.fn().mockRejectedValue({
        request: {},
        message: 'Network Error',
      });
      (apiService as any).api = { get: mockGet };

      await expect(apiService.getProjects()).rejects.toMatchObject({
        message: 'Network error - please check your connection',
        code: 'NETWORK_ERROR',
        status: 500,
      });
    });

    test('handles API errors', async () => {
      const mockGet = jest.fn().mockRejectedValue({
        response: {
          status: 404,
          data: {
            detail: 'Project not found',
          },
        },
      });
      (apiService as any).api = { get: mockGet };

      await expect(apiService.getProject('non-existent')).rejects.toMatchObject({
        message: 'Project not found',
        status: 404,
      });
    });
  });

  describe('Health Check', () => {
    test('healthCheck returns status', async () => {
      const mockResponse = { status: 'healthy' };
      const mockGet = jest.fn().mockResolvedValue({ data: mockResponse });
      (apiService as any).api = { get: mockGet };

      const result = await apiService.healthCheck();

      expect(mockGet).toHaveBeenCalledWith('/health');
      expect(result).toEqual(mockResponse);
    });
  });
});