import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ErrorBoundary, { withErrorBoundary } from '../components/ui/ErrorBoundary';
import WebSocketErrorBoundary from '../components/ui/WebSocketErrorBoundary';
import AsyncErrorBoundary from '../components/ui/AsyncErrorBoundary';
import { NetworkError, ApiError, ErrorFactory } from '../utils/errorTypes';

// Mock console methods to avoid noise in tests
const originalConsoleError = console.error;
const originalConsoleGroup = console.group;
const originalConsoleGroupEnd = console.groupEnd;

beforeAll(() => {
  console.error = jest.fn();
  console.group = jest.fn();
  console.groupEnd = jest.fn();
});

afterAll(() => {
  console.error = originalConsoleError;
  console.group = originalConsoleGroup;
  console.groupEnd = originalConsoleGroupEnd;
});

// Component that throws an error
const ThrowError: React.FC<{ shouldThrow?: boolean; errorMessage?: string }> = ({ 
  shouldThrow = true, 
  errorMessage = 'Test error' 
}) => {
  if (shouldThrow) {
    throw new Error(errorMessage);
  }
  return <div data-testid="success">No error</div>;
};

// Component that throws an error on button click
const ThrowErrorOnClick: React.FC = () => {
  const handleClick = () => {
    throw new Error('Click error');
  };

  return <button onClick={handleClick} data-testid="error-button">Click to throw error</button>;
};

describe('ErrorBoundary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">Child component</div>
      </ErrorBoundary>
    );

    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('renders error UI when child component throws', () => {
    render(
      <ErrorBoundary>
        <ThrowError errorMessage="Test error message" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    // The error message is transformed by the error boundary, so we check for the generic message
    expect(screen.getByText(/an unexpected error occurred/i)).toBeInTheDocument();
  });

  it('calls onError callback when error occurs', () => {
    const onErrorMock = jest.fn();
    
    render(
      <ErrorBoundary onError={onErrorMock}>
        <ThrowError errorMessage="Callback test error" />
      </ErrorBoundary>
    );

    expect(onErrorMock).toHaveBeenCalledWith(
      expect.any(Error),
      expect.any(Object),
      expect.any(String)
    );
  });

  it('displays retry button for recoverable errors', () => {
    render(
      <ErrorBoundary enableRetry={true}>
        <ThrowError errorMessage="Network connection failed" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/try again/i)).toBeInTheDocument();
  });

  it('allows custom fallback component', () => {
    const CustomFallback = <div data-testid="custom-fallback">Custom error UI</div>;

    render(
      <ErrorBoundary fallback={CustomFallback}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
    expect(screen.getByText('Custom error UI')).toBeInTheDocument();
  });

  it('resets error state when retry is clicked', async () => {
    let shouldThrow = true;

    const DynamicComponent = () => <ThrowError shouldThrow={shouldThrow} />;

    const { rerender } = render(
      <ErrorBoundary enableRetry={true}>
        <DynamicComponent />
      </ErrorBoundary>
    );

    // Error should be displayed
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();

    // Change condition and click retry - look for the button by role
    shouldThrow = false;
    const retryButton = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(retryButton);

    // Wait for error boundary to reset and component to re-render
    await waitFor(() => {
      expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
    });
  });

  it('categorizes different error types correctly', () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    // Test network error
    rerender(
      <ErrorBoundary>
        <ThrowError errorMessage="fetch failed" />
      </ErrorBoundary>
    );
    expect(screen.getByText(/network connection issue/i)).toBeInTheDocument();

    // Test API error
    rerender(
      <ErrorBoundary>
        <ThrowError errorMessage="API request failed with 500" />
      </ErrorBoundary>
    );
    expect(screen.getByText(/service temporarily unavailable/i)).toBeInTheDocument();

    // Test WebSocket error
    rerender(
      <ErrorBoundary>
        <ThrowError errorMessage="WebSocket connection closed" />
      </ErrorBoundary>
    );
    expect(screen.getByText(/real-time connection lost/i)).toBeInTheDocument();
  });

  it('limits retry attempts', () => {
    render(
      <ErrorBoundary enableRetry={true} maxRetries={2}>
        <ThrowError errorMessage="Network error" />
      </ErrorBoundary>
    );

    const retryButton = screen.getByText(/try again/i);
    
    // First retry
    fireEvent.click(retryButton);
    expect(screen.getByText(/try again \(1\/3\)/i)).toBeInTheDocument();

    // Second retry
    fireEvent.click(screen.getByText(/try again \(1\/3\)/i));
    expect(screen.getByText(/try again \(2\/3\)/i)).toBeInTheDocument();

    // Third retry should not be available after maxRetries (2)
    fireEvent.click(screen.getByText(/try again \(2\/3\)/i));
    expect(screen.queryByText(/try again/i)).not.toBeInTheDocument();
  });

  it('shows debug details in development mode', () => {
    // Mock process.env for this test
    const originalEnv = process.env;
    process.env = { ...originalEnv, NODE_ENV: 'development' };

    render(
      <ErrorBoundary>
        <ThrowError errorMessage="Debug test error" />
      </ErrorBoundary>
    );

    const showDetailsButton = screen.getByText(/show details/i);
    fireEvent.click(showDetailsButton);

    expect(screen.getByText(/debug information/i)).toBeInTheDocument();
    expect(screen.getByText(/error id:/i)).toBeInTheDocument();
    expect(screen.getByText(/error type:/i)).toBeInTheDocument();

    process.env = originalEnv;
  });
});

describe('withErrorBoundary HOC', () => {
  it('wraps component with error boundary', () => {
    const TestComponent = () => <div data-testid="wrapped">Wrapped component</div>;
    const WrappedComponent = withErrorBoundary(TestComponent, {
      level: 'component',
      context: 'test-hoc',
    });

    render(<WrappedComponent />);
    expect(screen.getByTestId('wrapped')).toBeInTheDocument();
  });

  it('catches errors in wrapped component', () => {
    const WrappedErrorComponent = withErrorBoundary(ThrowError, {
      level: 'component',
      context: 'test-hoc-error',
    });

    render(<WrappedErrorComponent />);
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });
});

describe('WebSocketErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <WebSocketErrorBoundary>
        <div data-testid="websocket-child">WebSocket content</div>
      </WebSocketErrorBoundary>
    );

    expect(screen.getByTestId('websocket-child')).toBeInTheDocument();
  });

  it('shows WebSocket-specific error message', () => {
    render(
      <WebSocketErrorBoundary>
        <ThrowError errorMessage="WebSocket connection failed" />
      </WebSocketErrorBoundary>
    );

    expect(screen.getByText(/real-time connection lost/i)).toBeInTheDocument();
    expect(screen.getByText(/live data connection has been interrupted/i)).toBeInTheDocument();
  });

  it('shows reconnect button when reconnectAction is provided', () => {
    const reconnectMock = jest.fn();

    render(
      <WebSocketErrorBoundary reconnectAction={reconnectMock}>
        <ThrowError errorMessage="WebSocket error" />
      </WebSocketErrorBoundary>
    );

    // Look for the button with the reconnect text inside it
    const reconnectButton = screen.getByRole('button', { name: /reconnect/i });
    expect(reconnectButton).toBeInTheDocument();

    fireEvent.click(reconnectButton);
    expect(reconnectMock).toHaveBeenCalled();
  });

  it('displays connection status correctly', () => {
    render(
      <WebSocketErrorBoundary connectionStatus="connecting">
        <ThrowError />
      </WebSocketErrorBoundary>
    );

    expect(screen.getByText(/status: reconnecting/i)).toBeInTheDocument();
    expect(screen.getByText(/attempting to reconnect/i)).toBeInTheDocument();
  });
});

describe('AsyncErrorBoundary', () => {
  it('shows loading state during async operation', async () => {
    const asyncOp = () => new Promise(resolve => setTimeout(resolve, 100));

    render(
      <AsyncErrorBoundary asyncOperation={asyncOp}>
        <div data-testid="async-content">Async content</div>
      </AsyncErrorBoundary>
    );

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByTestId('async-content')).toBeInTheDocument();
    });
  });

  it('shows error state when async operation fails', async () => {
    const asyncOp = () => Promise.reject(new Error('Async operation failed'));

    render(
      <AsyncErrorBoundary asyncOperation={asyncOp}>
        <div data-testid="async-content">Async content</div>
      </AsyncErrorBoundary>
    );

    await waitFor(() => {
      expect(screen.getByText(/async operation failed/i)).toBeInTheDocument();
    });
  });

  it('provides custom loading component', () => {
    const CustomLoader = <div data-testid="custom-loader">Custom loading...</div>;
    const asyncOp = () => new Promise(resolve => setTimeout(resolve, 100));

    render(
      <AsyncErrorBoundary asyncOperation={asyncOp} loadingComponent={CustomLoader}>
        <div>Content</div>
      </AsyncErrorBoundary>
    );

    expect(screen.getByTestId('custom-loader')).toBeInTheDocument();
  });
});

describe('Error Type Categorization', () => {
  it('correctly categorizes network errors', () => {
    render(
      <ErrorBoundary>
        <ThrowError errorMessage="Failed to fetch" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/network connection issue/i)).toBeInTheDocument();
  });

  it('correctly categorizes API errors', () => {
    render(
      <ErrorBoundary>
        <ThrowError errorMessage="API endpoint returned 404" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/service temporarily unavailable/i)).toBeInTheDocument();
  });

  it('correctly categorizes chunk loading errors', () => {
    render(
      <ErrorBoundary>
        <ThrowError errorMessage="Loading chunk 5 failed" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/failed to load application resources/i)).toBeInTheDocument();
  });
});