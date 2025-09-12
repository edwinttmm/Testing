import React from 'react';
import { render, screen } from '@testing-library/react';
import { jest } from '@jest/globals';
import SafeLabJackStatusPanel from '../src/components/SafeLabJackStatusPanel';

// Mock the LabJackStatusPanel component
jest.mock('../src/components/LabJackStatusPanel', () => {
  return function MockLabJackStatusPanel(props: any) {
    return <div data-testid="labjack-status-panel">Mock LabJack Panel {JSON.stringify(props)}</div>;
  };
});

// Mock the LabJackErrorBoundary component
jest.mock('../src/components/LabJackErrorBoundary', () => {
  return function MockLabJackErrorBoundary({ children }: { children: React.ReactNode }) {
    return <div data-testid="error-boundary">{children}</div>;
  };
});

describe('SafeLabJackStatusPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should render LabJackStatusPanel wrapped in error boundary', () => {
    render(<SafeLabJackStatusPanel />);

    expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    expect(screen.getByTestId('labjack-status-panel')).toBeInTheDocument();
  });

  test('should pass props to LabJackStatusPanel', () => {
    const mockOnDataReceived = jest.fn();
    const mockOnStatusChanged = jest.fn();

    render(
      <SafeLabJackStatusPanel
        onDataReceived={mockOnDataReceived}
        onStatusChanged={mockOnStatusChanged}
      />
    );

    const panelElement = screen.getByTestId('labjack-status-panel');
    expect(panelElement).toBeInTheDocument();
    
    // Props are passed through (mocked component shows props as JSON)
    expect(panelElement.textContent).toContain('onDataReceived');
    expect(panelElement.textContent).toContain('onStatusChanged');
  });

  test('should handle optional props correctly', () => {
    render(<SafeLabJackStatusPanel />);

    const panelElement = screen.getByTestId('labjack-status-panel');
    expect(panelElement).toBeInTheDocument();
    
    // Should handle missing optional props
    expect(panelElement.textContent).toContain('Mock LabJack Panel');
  });

  test('should maintain proper component hierarchy', () => {
    render(<SafeLabJackStatusPanel />);

    const errorBoundary = screen.getByTestId('error-boundary');
    const labJackPanel = screen.getByTestId('labjack-status-panel');

    // LabJackStatusPanel should be inside ErrorBoundary
    expect(errorBoundary).toContainElement(labJackPanel);
  });
});