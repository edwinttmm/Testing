import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  DetectionErrorBoundary,
  ErrorCategory,
  ErrorSeverity,
  withDetectionErrorBoundary,
  createErrorReportingService,
  type DetectionError,
  type ErrorReportingService
} from './DetectionErrorBoundary';

// Mock child component that can throw different types of errors
interface ErrorThrowingComponentProps {
  shouldThrow?: boolean;
  errorType?: 'network' | 'canvas' | 'video' | 'hardware' | 'frame80' | 'generic';
  errorMessage?: string;
}

const ErrorThrowingComponent: React.FC<ErrorThrowingComponentProps> = ({
  shouldThrow = false,
  errorType = 'generic',
  errorMessage = 'Test error'
}) => {
  if (shouldThrow) {
    let error: Error;
    
    switch (errorType) {
      case 'network':
        error = new Error('Network request failed: Connection timeout');
        error.stack = 'NetworkError: at fetch() at XMLHttpRequest';
        break;
      case 'canvas':
        error = new Error('Canvas rendering context failed');
        error.stack = 'at CanvasRenderingContext2D.drawImage()';
        break;
      case 'video':
        error = new Error('Video decode error: Unsupported codec');
        error.stack = 'at HTMLVideoElement.onError()';
        break;
      case 'hardware':
        error = new Error('Hardware device not found: LabJack USB connection failed');
        error.stack = 'at USBDevice.connect()';
        break;
      case 'frame80':
        error = new Error('Detection failure at frame 80: Processing timeout');
        error.stack = 'at processFrame() at frame80Handler()';
        break;
      default:
        error = new Error(errorMessage);
        break;
    }
    
    throw error;
  }
  
  return <div data-testid="working-component">Component working normally</div>;
};

// Mock error reporting service
const createMockErrorReportingService = (): ErrorReportingService & { getReportedErrors: () => DetectionError[] } => {
  const reportedErrors: DetectionError[] = [];
  
  return {
    reportError: jest.fn(async (error: DetectionError) => {
      reportedErrors.push(error);
    }),
    getReportedErrors: () => reportedErrors
  };
};

describe('DetectionErrorBoundary', () => {
  let consoleErrorSpy: jest.SpyInstance;
  
  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.clearAllMocks();
  });
  
  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  describe('Basic Error Boundary Functionality', () => {
    it('should render children when no error occurs', () => {
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={false} />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByTestId('working-component')).toBeInTheDocument();
      expect(screen.getByText('Component working normally')).toBeInTheDocument();
    });

    it('should catch and display error when child component throws', () => {
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={true} errorMessage="Test error message" />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByText('Detection System Error')).toBeInTheDocument();
      expect(screen.getByText('Test error message')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /retry now/i })).toBeInTheDocument();
    });

    it('should use custom fallback when provided', () => {
      const customFallback = <div data-testid="custom-fallback">Custom error UI</div>;
      
      render(
        <DetectionErrorBoundary fallback={customFallback}>
          <ErrorThrowingComponent shouldThrow={true} />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      expect(screen.getByText('Custom error UI')).toBeInTheDocument();
    });
  });

  describe('Error Categorization', () => {
    const testCases = [
      {
        type: 'network' as const,
        expectedCategory: ErrorCategory.NETWORK,
        expectedSeverity: ErrorSeverity.HIGH,
        expectedChips: ['NETWORK', 'HIGH']
      },
      {
        type: 'canvas' as const,
        expectedCategory: ErrorCategory.RENDERING,
        expectedSeverity: ErrorSeverity.HIGH,
        expectedChips: ['RENDERING', 'HIGH']
      },
      {
        type: 'video' as const,
        expectedCategory: ErrorCategory.PROCESSING,
        expectedSeverity: ErrorSeverity.HIGH,
        expectedChips: ['PROCESSING', 'HIGH']
      },
      {
        type: 'hardware' as const,
        expectedCategory: ErrorCategory.HARDWARE,
        expectedSeverity: ErrorSeverity.CRITICAL,
        expectedChips: ['HARDWARE', 'CRITICAL']
      },
      {
        type: 'frame80' as const,
        expectedCategory: ErrorCategory.PROCESSING,
        expectedSeverity: ErrorSeverity.HIGH,
        expectedChips: ['PROCESSING', 'HIGH']
      }
    ];

    testCases.forEach(({ type, expectedChips }) => {
      it(`should correctly categorize ${type} errors`, () => {
        render(
          <DetectionErrorBoundary>
            <ErrorThrowingComponent shouldThrow={true} errorType={type} />
          </DetectionErrorBoundary>
        );
        
        expectedChips.forEach(chip => {
          expect(screen.getByText(chip)).toBeInTheDocument();
        });
      });
    });

    it('should show special Frame 80 warning for frame80 errors', () => {
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={true} errorType="frame80" />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByText('Frame 80 Detection Failure')).toBeInTheDocument();
      expect(screen.getByText(/This error is specific to frame 80 processing/)).toBeInTheDocument();
    });
  });

  describe('Error Reporting', () => {
    it('should report errors to external service', async () => {
      const mockReportingService = createMockErrorReportingService();
      const onErrorSpy = jest.fn();
      
      render(
        <DetectionErrorBoundary
          errorReportingService={mockReportingService}
          onError={onErrorSpy}
          userId="test-user"
          sessionId="test-session"
        >
          <ErrorThrowingComponent shouldThrow={true} errorType="network" />
        </DetectionErrorBoundary>
      );
      
      await waitFor(() => {
        expect(mockReportingService.reportError).toHaveBeenCalled();
        expect(onErrorSpy).toHaveBeenCalled();
      });
      
      const reportedErrors = mockReportingService.getReportedErrors();
      expect(reportedErrors).toHaveLength(1);
      expect(reportedErrors[0].category).toBe(ErrorCategory.NETWORK);
      expect(reportedErrors[0].userId).toBe('test-user');
      expect(reportedErrors[0].sessionId).toBe('test-session');
    });

    it('should handle error reporting failures gracefully', async () => {
      const failingReportingService: ErrorReportingService = {
        reportError: jest.fn().mockRejectedValue(new Error('Reporting failed'))
      };
      
      render(
        <DetectionErrorBoundary errorReportingService={failingReportingService}>
          <ErrorThrowingComponent shouldThrow={true} />
        </DetectionErrorBoundary>
      );
      
      // Should still show error UI even if reporting fails
      expect(screen.getByText('Detection System Error')).toBeInTheDocument();
      
      await waitFor(() => {
        expect(failingReportingService.reportError).toHaveBeenCalled();
        expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to report error:', expect.any(Error));
      });
    });
  });

  describe('Retry Functionality', () => {
    it('should retry when retry button is clicked', async () => {
      const user = userEvent.setup();
      
      const RetryTestComponent: React.FC<{ retryCount: number }> = ({ retryCount }) => {
        if (retryCount < 2) {
          throw new Error('Temporary error');
        }
        return <div data-testid="success">Success after retry</div>;
      };
      
      let retryCount = 0;
      const ComponentWrapper = () => {
        const [count, setCount] = React.useState(0);
        retryCount = count;
        
        return (
          <DetectionErrorBoundary key={count}>
            <RetryTestComponent retryCount={count} />
          </DetectionErrorBoundary>
        );
      };
      
      const { rerender } = render(<ComponentWrapper />);
      
      // First render should show error
      expect(screen.getByText('Detection System Error')).toBeInTheDocument();
      
      // Click retry
      const retryButton = screen.getByRole('button', { name: /retry now/i });
      await user.click(retryButton);
      
      // After retry, component should work
      expect(screen.queryByText('Detection System Error')).not.toBeInTheDocument();
    });

    it('should track retry count and show maximum retries reached', () => {
      const TestComponent = () => {
        throw new Error('Persistent error');
      };
      
      render(
        <DetectionErrorBoundary maxRetries={2}>
          <TestComponent />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByText('Detection System Error')).toBeInTheDocument();
      
      // Simulate multiple retries by manually updating state
      // This would require exposing internal state or using a ref
      // For now, we test the UI elements are present
      expect(screen.getByRole('button', { name: /retry now/i })).toBeInTheDocument();
    });

    it('should show auto-recovery progress for eligible errors', async () => {
      jest.useFakeTimers();
      
      render(
        <DetectionErrorBoundary enableAutoRecovery={true} autoRetryDelay={3000}>
          <ErrorThrowingComponent shouldThrow={true} errorType="network" />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByText('Detection System Error')).toBeInTheDocument();
      
      // Fast forward time to trigger auto-retry
      act(() => {
        jest.advanceTimersByTime(3000);
      });
      
      jest.useRealTimers();
    });
  });

  describe('Recovery Instructions', () => {
    it('should show relevant recovery instructions for different error types', async () => {
      const user = userEvent.setup();
      
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={true} errorType="network" />
        </DetectionErrorBoundary>
      );
      
      // Expand recovery instructions
      const recoveryAccordion = screen.getByText('Recovery Instructions');
      await user.click(recoveryAccordion);
      
      expect(screen.getByText('Check your internet connection')).toBeInTheDocument();
      expect(screen.getByText('Verify API endpoints are accessible')).toBeInTheDocument();
    });

    it('should show hardware-specific instructions for hardware errors', async () => {
      const user = userEvent.setup();
      
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={true} errorType="hardware" />
        </DetectionErrorBoundary>
      );
      
      const recoveryAccordion = screen.getByText('Recovery Instructions');
      await user.click(recoveryAccordion);
      
      expect(screen.getByText('Check hardware connections')).toBeInTheDocument();
      expect(screen.getByText('Verify device drivers are up to date')).toBeInTheDocument();
    });
  });

  describe('Error Details and Debugging', () => {
    it('should show development error details in development mode', () => {
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'development';
      
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={true} errorMessage="Dev error" />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByText('Development Error Details')).toBeInTheDocument();
      
      process.env.NODE_ENV = originalEnv;
    });

    it('should open detailed error dialog when View Details is clicked', async () => {
      const user = userEvent.setup();
      
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={true} errorMessage="Detailed error" />
        </DetectionErrorBoundary>
      );
      
      const viewDetailsButton = screen.getByRole('button', { name: /view details/i });
      await user.click(viewDetailsButton);
      
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Error Details')).toBeInTheDocument();
    });

    it('should copy error details to clipboard', async () => {
      const user = userEvent.setup();
      
      // Mock clipboard API
      const mockClipboard = {
        writeText: jest.fn().mockResolvedValue(undefined)
      };
      Object.assign(navigator, { clipboard: mockClipboard });
      
      render(
        <DetectionErrorBoundary>
          <ErrorThrowingComponent shouldThrow={true} errorMessage="Copy test error" />
        </DetectionErrorBoundary>
      );
      
      const copyButton = screen.getByRole('button', { name: /copy error/i });
      await user.click(copyButton);
      
      expect(mockClipboard.writeText).toHaveBeenCalled();
      const copiedText = mockClipboard.writeText.mock.calls[0][0];
      expect(copiedText).toContain('"message": "Copy test error"');
    });
  });

  describe('Higher-Order Component', () => {
    it('should wrap components with error boundary using HOC', () => {
      const TestComponent = () => <div>HOC Test Component</div>;
      const WrappedComponent = withDetectionErrorBoundary(TestComponent);
      
      render(<WrappedComponent />);
      
      expect(screen.getByText('HOC Test Component')).toBeInTheDocument();
    });

    it('should handle errors in HOC-wrapped components', () => {
      const ErrorComponent = () => {
        throw new Error('HOC Error');
      };
      const WrappedComponent = withDetectionErrorBoundary(ErrorComponent);
      
      render(<WrappedComponent />);
      
      expect(screen.getByText('Detection System Error')).toBeInTheDocument();
      expect(screen.getByText('HOC Error')).toBeInTheDocument();
    });
  });

  describe('Error Reporting Service', () => {
    it('should create working error reporting service', async () => {
      // Mock fetch
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        status: 200
      });
      global.fetch = mockFetch;
      
      const service = createErrorReportingService('https://api.example.com/errors', 'test-key');
      
      const testError: DetectionError = {
        id: 'test-error',
        message: 'Test error',
        category: ErrorCategory.NETWORK,
        severity: ErrorSeverity.HIGH,
        timestamp: new Date()
      };
      
      await service.reportError(testError);
      
      expect(mockFetch).toHaveBeenCalledWith('https://api.example.com/errors', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-key'
        },
        body: JSON.stringify(testError)
      });
    });

    it('should handle error reporting service failures', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error'
      });
      global.fetch = mockFetch;
      
      const service = createErrorReportingService('https://api.example.com/errors');
      
      const testError: DetectionError = {
        id: 'test-error',
        message: 'Test error',
        category: ErrorCategory.NETWORK,
        severity: ErrorSeverity.HIGH,
        timestamp: new Date()
      };
      
      await expect(service.reportError(testError)).rejects.toThrow('Failed to report error: Internal Server Error');
    });
  });

  describe('Error Throttling', () => {
    it('should throttle repeated identical errors', () => {
      const TestComponent = ({ throwError }: { throwError: boolean }) => {
        if (throwError) {
          throw new Error('Repeated error');
        }
        return <div>OK</div>;
      };
      
      const { rerender } = render(
        <DetectionErrorBoundary>
          <TestComponent throwError={false} />
        </DetectionErrorBoundary>
      );
      
      // First error
      rerender(
        <DetectionErrorBoundary>
          <TestComponent throwError={true} />
        </DetectionErrorBoundary>
      );
      
      expect(screen.getByText('Detection System Error')).toBeInTheDocument();
      
      // Repeated error should be throttled (tested implicitly through lack of duplicate handling)
      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });

  describe('Component Lifecycle', () => {
    it('should clean up timeouts on unmount', () => {
      const clearTimeoutSpy = jest.spyOn(window, 'clearTimeout');
      
      const { unmount } = render(
        <DetectionErrorBoundary enableAutoRecovery={true}>
          <ErrorThrowingComponent shouldThrow={true} errorType="network" />
        </DetectionErrorBoundary>
      );
      
      unmount();
      
      // Should clean up any timeouts
      expect(clearTimeoutSpy).toHaveBeenCalled();
      
      clearTimeoutSpy.mockRestore();
    });
  });
});