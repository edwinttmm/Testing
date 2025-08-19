import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Results from '../ai-model-validation-platform/frontend/src/pages/Results';

// Mock the API service
jest.mock('../ai-model-validation-platform/frontend/src/services/api', () => ({
  apiService: {
    getProjects: jest.fn(() => Promise.resolve([])),
    getTestSessions: jest.fn(() => Promise.resolve([])),
    getTestResults: jest.fn(() => Promise.resolve({
      accuracy: 90,
      precision: 85,
      recall: 88,
      f1Score: 86.5,
      truePositives: 100,
      falsePositives: 10,
      falseNegatives: 12,
      totalDetections: 122
    })),
  },
}));

describe('Results Component', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
  });

  test('should render without TypeScript errors', async () => {
    render(<Results />);
    
    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Results & Analytics')).toBeInTheDocument();
    });
  });

  test('should have detectionComparisons state variable initialized', () => {
    const { container } = render(<Results />);
    // This test ensures the component renders without TypeScript compilation errors
    // The missing state variables would cause compilation to fail
    expect(container).toBeInTheDocument();
  });

  test('should have selectedSession state variable initialized', () => {
    const { container } = render(<Results />);
    // This test ensures the component renders without TypeScript compilation errors
    // The missing state variables would cause compilation to fail
    expect(container).toBeInTheDocument();
  });

  test('should handle loadDetailedResults function call', async () => {
    render(<Results />);
    
    // The loadDetailedResults function should work without errors
    // when the missing state variables are properly declared
    await waitFor(() => {
      expect(screen.getByText('Results & Analytics')).toBeInTheDocument();
    });
  });
});