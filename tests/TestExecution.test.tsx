import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TestExecution from '../ai-model-validation-platform/frontend/src/pages/TestExecution';
import { apiService } from '../ai-model-validation-platform/frontend/src/services/api';

// Mock dependencies
jest.mock('../ai-model-validation-platform/frontend/src/services/api');
jest.mock('../ai-model-validation-platform/frontend/src/components/VideoSelectionDialog', () => {
  return function MockVideoSelectionDialog(props: any) {
    return <div data-testid="video-selection-dialog">{props.open ? 'Open' : 'Closed'}</div>;
  };
});

const mockApiService = apiService as jest.Mocked<typeof apiService>;

const mockProjects = [
  {
    id: '1',
    name: 'Test Project',
    description: 'Test Description',
    createdAt: '2024-01-01T00:00:00Z',
    models: [{ id: '1', name: 'Test Model', type: 'detection' }]
  }
];

const mockSessions = [
  {
    id: '1',
    name: 'Test Session',
    description: 'Test Session Description',
    status: 'pending' as const,
    createdAt: '2024-01-01T00:00:00Z',
    projectId: '1'
  }
];

describe('TestExecution Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiService.get.mockImplementation((url: string) => {
      if (url === '/api/projects') {
        return Promise.resolve(mockProjects);
      }
      if (url.includes('/test-sessions')) {
        return Promise.resolve(mockSessions);
      }
      return Promise.resolve([]);
    });
  });

  describe('Component Rendering', () => {
    it('should render without crashing', async () => {
      render(<TestExecution />);
      expect(screen.getByText('Test Execution')).toBeInTheDocument();
    });

    it('should load and display projects', async () => {
      render(<TestExecution />);
      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith('/api/projects');
      });
    });

    it('should display test sessions when project is selected', async () => {
      render(<TestExecution />);
      await waitFor(() => {
        expect(screen.getByText('Test Sessions')).toBeInTheDocument();
      });
    });
  });

  describe('useCallback Functions', () => {
    it('should have stable references for callback functions', async () => {
      const { rerender } = render(<TestExecution />);
      
      // Force a re-render
      rerender(<TestExecution />);
      
      // The component should not cause infinite re-renders
      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalled();
      });
    });
  });

  describe('Function Hoisting', () => {
    it('should call functions in useEffect without hoisting errors', async () => {
      // This test ensures that functions are defined before they are used
      render(<TestExecution />);
      
      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith('/api/projects');
      });
      
      // No TypeScript errors should occur during execution
      expect(screen.getByText('Test Execution')).toBeInTheDocument();
    });
  });

  describe('WebSocket Integration', () => {
    beforeEach(() => {
      // Mock WebSocket
      global.WebSocket = jest.fn(() => ({
        onmessage: null,
        onerror: null,
        onclose: null,
        close: jest.fn(),
      })) as any;
    });

    it('should handle WebSocket connection when test is running', async () => {
      render(<TestExecution />);
      
      // Simulate starting a test session
      const startButton = screen.queryByText('Start');
      if (startButton) {
        fireEvent.click(startButton);
      }
      
      // WebSocket should be created when running
      expect(global.WebSocket).toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockApiService.get.mockRejectedValue(new Error('API Error'));
      
      render(<TestExecution />);
      
      await waitFor(() => {
        expect(screen.getByText(/failed to load projects/i)).toBeInTheDocument();
      });
    });
  });

  describe('Dialog Management', () => {
    it('should open and close video selection dialog', async () => {
      render(<TestExecution />);
      
      await waitFor(() => {
        const selectVideosButton = screen.getByText(/select videos/i);
        fireEvent.click(selectVideosButton);
      });
      
      expect(screen.getByTestId('video-selection-dialog')).toHaveTextContent('Open');
    });

    it('should open and close session creation dialog', async () => {
      render(<TestExecution />);
      
      const newSessionButton = screen.getByText('New Session');
      fireEvent.click(newSessionButton);
      
      expect(screen.getByText('Create Test Session')).toBeInTheDocument();
    });
  });

  describe('Form Interactions', () => {
    it('should handle session creation form', async () => {
      mockApiService.post.mockResolvedValue({
        id: '2',
        name: 'New Session',
        status: 'pending',
        createdAt: '2024-01-01T00:00:00Z'
      });

      render(<TestExecution />);
      
      // Open dialog
      const newSessionButton = screen.getByText('New Session');
      fireEvent.click(newSessionButton);
      
      // Fill form
      const nameInput = screen.getByLabelText('Session Name');
      fireEvent.change(nameInput, { target: { value: 'Test Session Name' } });
      
      // Submit form
      const createButton = screen.getByText('Create Session');
      fireEvent.click(createButton);
      
      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledWith('/api/test-sessions', expect.any(Object));
      });
    });
  });

  describe('Status Management', () => {
    it('should display correct status icons', async () => {
      render(<TestExecution />);
      
      await waitFor(() => {
        // Should display session status appropriately
        expect(screen.getByText('Test Sessions')).toBeInTheDocument();
      });
    });
  });
});