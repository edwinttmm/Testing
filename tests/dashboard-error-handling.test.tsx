import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { jest } from '@jest/globals';
import Dashboard from '../ai-model-validation-platform/frontend/src/pages/Dashboard';
import ErrorBoundary from '../ai-model-validation-platform/frontend/src/components/ui/ErrorBoundary';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import * as apiService from '../ai-model-validation-platform/frontend/src/services/api';

// Mock the API service
jest.mock('../ai-model-validation-platform/frontend/src/services/api');

const mockApiService = apiService as jest.Mocked<typeof apiService>;

const theme = createTheme();

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      <ErrorBoundary
        level="page"
        context="dashboard-test"
        enableRetry={true}
        maxRetries={3}
      >
        {component}
      </ErrorBoundary>
    </ThemeProvider>
  );
};

describe('Dashboard Error Handling - TDD Phase 1', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    console.error = jest.fn(); // Mock console.error to avoid noise
  });

  describe('Network Error Handling', () => {
    it('should display error message when API fails with network error', async () => {
      // FAILING TEST - This should fail because handleError function is broken
      const networkError = new Error('Network error - please check your connection');
      networkError.name = 'NetworkError';
      
      mockApiService.getDashboardStats.mockRejectedValue(networkError);

      renderWithProviders(<Dashboard />);

      // Wait for component to load and fail
      await waitFor(() => {
        expect(screen.getByText(/failed to load dashboard statistics/i)).toBeInTheDocument();
      });

      // Should show demo data message
      expect(screen.getByText(/showing demo data/i)).toBeInTheDocument();
      
      // Should not crash with uncaught error
      expect(console.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed to fetch dashboard stats'),
        networkError
      );
    });

    it('should retry API call when retry button is clicked', async () => {
      // FAILING TEST - Retry mechanism not implemented properly
      const networkError = new Error('Network error');
      mockApiService.getDashboardStats
        .mockRejectedValueOnce(networkError)
        .mockResolvedValueOnce({
          projectCount: 5,
          videoCount: 10,
          testCount: 15,
          averageAccuracy: 95.5,
          activeTests: 2,
          totalDetections: 100
        });

      renderWithProviders(<Dashboard />);

      // Wait for error to appear
      await waitFor(() => {
        expect(screen.getByText(/failed to load dashboard statistics/i)).toBeInTheDocument();
      });

      // Click retry (this should be implemented in error boundary)
      const retryButton = screen.queryByText(/try again/i);
      if (retryButton) {
        fireEvent.click(retryButton);
      }

      // Should eventually show success data
      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument(); // Project count
        expect(screen.getByText('95.5%')).toBeInTheDocument(); // Accuracy
      }, { timeout: 5000 });
    });
  });

  describe('HandleError Function Errors', () => {
    it('should not throw uncaught errors when handleError is called', async () => {
      // FAILING TEST - This is the main issue from the error report
      const consoleSpy = jest.spyOn(console, 'error');
      let uncaughtError: any = null;

      // Mock the problematic handleError scenario
      const problemError = {
        message: '[object Object]',
        stack: 'Error at handleError (bundle.js:59359:58)'
      };

      // Simulate the error that's happening in production
      window.addEventListener('error', (event) => {
        uncaughtError = event.error;
      });

      mockApiService.getDashboardStats.mockRejectedValue(problemError);

      renderWithProviders(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load dashboard statistics/i)).toBeInTheDocument();
      });

      // This should NOT have uncaught errors
      expect(uncaughtError).toBeNull();
      
      // Should have proper error logging instead
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('should handle malformed error objects gracefully', async () => {
      // FAILING TEST - Error boundary should handle any error type
      const malformedError = {
        toString: () => '[object Object]',
        message: undefined,
        stack: undefined
      };

      mockApiService.getDashboardStats.mockRejectedValue(malformedError);

      const renderResult = renderWithProviders(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load dashboard statistics/i)).toBeInTheDocument();
      });

      // Should not crash the entire component
      expect(renderResult.container).toBeInTheDocument();
      expect(screen.getByText(/Dashboard/i)).toBeInTheDocument();
    });
  });

  describe('Loading States and Error Recovery', () => {
    it('should show proper loading skeleton while fetching data', async () => {
      // FAILING TEST - Loading states might not be implemented properly
      let resolvePromise: (value: any) => void;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockApiService.getDashboardStats.mockReturnValue(promise as any);

      renderWithProviders(<Dashboard />);

      // Should show loading skeleton initially
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      
      // Should show skeleton components (this might fail if not implemented)
      const skeletons = screen.getAllByTestId(/skeleton/i);
      expect(skeletons.length).toBeGreaterThan(0);

      // Resolve the promise
      act(() => {
        resolvePromise!({
          projectCount: 3,
          videoCount: 7,
          testCount: 12,
          averageAccuracy: 88.9,
          activeTests: 1,
          totalDetections: 50
        });
      });

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
        expect(screen.getByText('88.9%')).toBeInTheDocument();
      });
    });

    it('should handle simultaneous multiple API failures gracefully', async () => {
      // FAILING TEST - Multiple simultaneous errors might cause issues
      const error1 = new Error('Dashboard stats failed');
      const error2 = new Error('Chart data failed');

      mockApiService.getDashboardStats.mockRejectedValue(error1);
      mockApiService.getChartData.mockRejectedValue(error2);

      renderWithProviders(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load dashboard statistics/i)).toBeInTheDocument();
      });

      // Should show fallback data and not crash
      expect(screen.getByText('0')).toBeInTheDocument(); // Fallback stats
      expect(screen.getByText('94.2%')).toBeInTheDocument(); // Fallback accuracy
    });
  });

  describe('UI Component Interactions', () => {
    it('should handle button clicks without errors', async () => {
      // FAILING TEST - UI buttons reported as non-functional
      mockApiService.getDashboardStats.mockResolvedValue({
        projectCount: 2,
        videoCount: 4,
        testCount: 6,
        averageAccuracy: 92.1,
        activeTests: 0,
        totalDetections: 25
      });

      renderWithProviders(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('2')).toBeInTheDocument();
      });

      // Try to find any interactive buttons/cards
      const interactiveElements = screen.getAllByRole('button');
      
      // Each button should be clickable without errors
      interactiveElements.forEach(button => {
        expect(() => {
          fireEvent.click(button);
        }).not.toThrow();
      });
    });

    it('should maintain accessibility attributes during error states', async () => {
      // FAILING TEST - Accessibility might be compromised during errors
      const error = new Error('API failure');
      mockApiService.getDashboardStats.mockRejectedValue(error);

      renderWithProviders(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load dashboard statistics/i)).toBeInTheDocument();
      });

      // Should maintain ARIA labels and roles even in error state
      const cards = screen.getAllByRole('region');
      expect(cards.length).toBeGreaterThan(0);

      cards.forEach(card => {
        expect(card).toHaveAttribute('aria-label');
      });
    });
  });

  describe('Real-time Connection Handling', () => {
    it('should handle WebSocket connection failures gracefully', async () => {
      // FAILING TEST - WebSocket errors causing issues
      const wsError = new Error('WebSocket connection failed');
      
      // Mock WebSocket failure scenario
      global.WebSocket = jest.fn().mockImplementation(() => {
        throw wsError;
      });

      mockApiService.getDashboardStats.mockResolvedValue({
        projectCount: 1,
        videoCount: 2,
        testCount: 3,
        averageAccuracy: 85.0,
        activeTests: 0,
        totalDetections: 10
      });

      renderWithProviders(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('1')).toBeInTheDocument();
      });

      // Should still render dashboard even without WebSocket
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText('85.0%')).toBeInTheDocument();
    });

    it('should display real-time connection status', async () => {
      // FAILING TEST - Real-time server connection status not shown properly
      mockApiService.getDashboardStats.mockResolvedValue({
        projectCount: 0,
        videoCount: 0,
        testCount: 0,
        averageAccuracy: 0,
        activeTests: 0,
        totalDetections: 0
      });

      renderWithProviders(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      // Should show some indication of real-time connection status
      // This will likely fail as it's not implemented yet
      const connectionIndicator = screen.queryByText(/connected|disconnected|connecting/i);
      expect(connectionIndicator).toBeInTheDocument();
    });
  });
});

describe('Error Boundary Integration Tests', () => {
  it('should catch and handle component rendering errors', async () => {
    // FAILING TEST - Error boundary should catch render errors
    const BrokenComponent = () => {
      throw new Error('Component rendering failed');
    };

    const { container } = render(
      <ThemeProvider theme={theme}>
        <ErrorBoundary
          level="component"
          context="broken-component"
          enableRetry={true}
        >
          <BrokenComponent />
        </ErrorBoundary>
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });

    // Should show retry button
    const retryButton = screen.getByText(/try again/i);
    expect(retryButton).toBeInTheDocument();

    // Container should not be empty (error boundary UI should render)
    expect(container.firstChild).not.toBeNull();
  });

  it('should provide error context and debugging information', async () => {
    // FAILING TEST - Error boundary should provide debugging info
    const TestError = new Error('Test error for debugging');
    
    const ErrorComponent = () => {
      throw TestError;
    };

    render(
      <ThemeProvider theme={theme}>
        <ErrorBoundary
          level="component"
          context="debug-test"
          enableRetry={false}
        >
          <ErrorComponent />
        </ErrorBoundary>
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });

    // In development mode, should show debug information
    if (process.env.NODE_ENV === 'development') {
      const showDetailsButton = screen.queryByText(/show details/i);
      if (showDetailsButton) {
        fireEvent.click(showDetailsButton);
        
        await waitFor(() => {
          expect(screen.getByText(/debug information/i)).toBeInTheDocument();
        });
      }
    }
  });
});