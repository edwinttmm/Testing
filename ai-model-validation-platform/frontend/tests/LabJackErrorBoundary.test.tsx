import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { jest } from '@jest/globals';
import LabJackErrorBoundary from '../src/components/LabJackErrorBoundary';

// Component that throws an error for testing
const ThrowError = ({ shouldThrow = false }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test error for error boundary');
  }
  return <div>Child component</div>;
};

describe('LabJackErrorBoundary', () => {
  beforeEach(() => {
    // Mock console.error to avoid noise in test output
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('should render children when there is no error', () => {
    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={false} />
      </LabJackErrorBoundary>
    );

    expect(screen.getByText('Child component')).toBeInTheDocument();
  });

  test('should display error UI when child component throws', () => {
    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    // Should show error boundary UI
    expect(screen.getByText('LabJack Component Error')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong with the LabJack status panel')).toBeInTheDocument();
    expect(screen.getByText('Test error for error boundary')).toBeInTheDocument();
  });

  test('should display troubleshooting information', () => {
    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    // Should show troubleshooting tips
    expect(screen.getByText('Backend Service Not Running')).toBeInTheDocument();
    expect(screen.getByText('Network Connection Issues')).toBeInTheDocument();
    expect(screen.getByText('LabJack Hardware Issues')).toBeInTheDocument();
    expect(screen.getByText('Component Configuration')).toBeInTheDocument();
  });

  test('should display suggested actions', () => {
    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    // Should show suggested actions
    expect(screen.getByText('Suggested Actions:')).toBeInTheDocument();
    expect(screen.getByText(/Start the backend service/)).toBeInTheDocument();
    expect(screen.getByText(/Check LabJack hardware connections/)).toBeInTheDocument();
    expect(screen.getByText(/Refresh the page or reset the component/)).toBeInTheDocument();
  });

  test('should reset error state when reset button is clicked', () => {
    const { rerender } = render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    // Should show error UI
    expect(screen.getByText('LabJack Component Error')).toBeInTheDocument();

    // Click reset button
    const resetButton = screen.getByText('Reset Component');
    fireEvent.click(resetButton);

    // Re-render with non-throwing component
    rerender(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={false} />
      </LabJackErrorBoundary>
    );

    // Should show child component again
    expect(screen.getByText('Child component')).toBeInTheDocument();
  });

  test('should refresh page when refresh button is clicked', () => {
    // Mock window.location.reload
    const mockReload = jest.fn();
    Object.defineProperty(window, 'location', {
      value: { reload: mockReload },
      writable: true
    });

    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    // Click refresh button
    const refreshButton = screen.getByText('Refresh Page');
    fireEvent.click(refreshButton);

    expect(mockReload).toHaveBeenCalled();
  });

  test('should show development error details in development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';

    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    // Should show development error details
    expect(screen.getByText('Development Error Details')).toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  test('should not show development error details in production mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';

    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    // Should not show development error details
    expect(screen.queryByText('Development Error Details')).not.toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  test('should log errors to console', () => {
    const consoleSpy = jest.spyOn(console, 'error');

    render(
      <LabJackErrorBoundary>
        <ThrowError shouldThrow={true} />
      </LabJackErrorBoundary>
    );

    expect(consoleSpy).toHaveBeenCalledWith('LabJack Component Error:', expect.any(Error));
    expect(consoleSpy).toHaveBeenCalledWith('Error Info:', expect.any(Object));
  });
});