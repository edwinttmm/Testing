/**
 * SPARC + TDD London School Enhanced Test Utilities
 * Comprehensive test helper suite for AI Model Validation Platform
 */

import React, { ReactElement, PropsWithChildren } from 'react';
import { render, RenderOptions, RenderResult } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { createTheme } from '@mui/material/styles';
import userEvent from '@testing-library/user-event';

// Enhanced theme for testing
const testTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

// Test wrapper with all necessary providers
interface AllTheProvidersProps {
  children: React.ReactNode;
}

const AllTheProviders: React.FC<AllTheProvidersProps> = ({ children }) => {
  return (
    <BrowserRouter>
      <ThemeProvider theme={testTheme}>
        {children}
      </ThemeProvider>
    </BrowserRouter>
  );
};

// Enhanced render function
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  wrapper?: React.ComponentType<PropsWithChildren>;
  initialEntries?: string[];
}

const customRender = (
  ui: ReactElement,
  options: CustomRenderOptions = {}
): RenderResult & { user: ReturnType<typeof userEvent.setup> } => {
  const { wrapper = AllTheProviders, ...renderOptions } = options;
  
  const user = userEvent.setup();
  
  const result = render(ui, {
    wrapper,
    ...renderOptions,
  });

  return {
    user,
    ...result,
  };
};

// Test data generators for London School TDD approach
export const testDataGenerators = {
  project: (overrides = {}) => ({
    id: 'test-project-1',
    name: 'Test Project',
    description: 'A test project for validation',
    status: 'active',
    createdAt: '2023-01-01T00:00:00Z',
    updatedAt: '2023-01-01T00:00:00Z',
    ...overrides,
  }),
  
  dataset: (overrides = {}) => ({
    id: 'test-dataset-1',
    name: 'Test Dataset',
    type: 'image',
    size: 1000,
    format: 'JPEG',
    createdAt: '2023-01-01T00:00:00Z',
    ...overrides,
  }),
  
  model: (overrides = {}) => ({
    id: 'test-model-1',
    name: 'Test Model',
    version: '1.0.0',
    type: 'classification',
    accuracy: 0.95,
    status: 'trained',
    ...overrides,
  }),
  
  validationResult: (overrides = {}) => ({
    id: 'test-result-1',
    projectId: 'test-project-1',
    modelId: 'test-model-1',
    accuracy: 0.92,
    precision: 0.89,
    recall: 0.91,
    f1Score: 0.90,
    timestamp: '2023-01-01T00:00:00Z',
    ...overrides,
  }),
};

// Mock API responses
export const mockApiResponses = {
  projects: {
    getAll: () => [
      testDataGenerators.project(),
      testDataGenerators.project({ id: 'test-project-2', name: 'Project 2' }),
    ],
    getById: (id: string) => testDataGenerators.project({ id }),
    create: (data: any) => testDataGenerators.project({ ...data, id: 'new-project' }),
    update: (id: string, data: any) => testDataGenerators.project({ id, ...data }),
    delete: (id: string) => ({ success: true }),
  },
  
  datasets: {
    getAll: () => [
      testDataGenerators.dataset(),
      testDataGenerators.dataset({ id: 'test-dataset-2', name: 'Dataset 2' }),
    ],
    getById: (id: string) => testDataGenerators.dataset({ id }),
  },
  
  models: {
    getAll: () => [
      testDataGenerators.model(),
      testDataGenerators.model({ id: 'test-model-2', name: 'Model 2' }),
    ],
    getById: (id: string) => testDataGenerators.model({ id }),
  },
};

// Test environment setup
export const setupTestEnvironment = () => {
  // Mock window.matchMedia for responsive tests
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(), // deprecated
      removeListener: jest.fn(), // deprecated
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });

  // Mock ResizeObserver
  global.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };

  // Mock IntersectionObserver with proper interface
  global.IntersectionObserver = class MockIntersectionObserver {
    root = null;
    rootMargin = '0px';
    thresholds = [0];
    constructor() {}
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() { return []; }
  } as any;

  // Mock GPU detection for consistent testing
  jest.mock('@/utils/gpu-detection', () => ({
    detectGPU: () => ({
      available: false,
      vendor: 'none',
      name: 'CPU-only (test)',
      mode: 'cpu'
    }),
    getOptimalConfig: () => ({
      imageProcessing: {
        maxSize: 2048,
        quality: 0.8,
        format: 'jpeg',
        batchSize: 1
      }
    })
  }));
};

// Test assertions helpers
export const testAssertions = {
  expectElementToBeVisible: (element: HTMLElement) => {
    expect(element).toBeInTheDocument();
    expect(element).toBeVisible();
  },
  
  expectElementToHaveAccessibleName: (element: HTMLElement, name: string) => {
    expect(element).toHaveAccessibleName(name);
  },
  
  expectFormFieldToBeRequired: (field: HTMLElement) => {
    expect(field).toBeRequired();
    expect(field).toBeInvalid();
  },
  
  expectApiCallToHaveBeenMade: (mockFn: jest.Mock, expectedUrl: string, expectedMethod = 'GET') => {
    expect(mockFn).toHaveBeenCalledWith(
      expect.objectContaining({
        url: expectedUrl,
        method: expectedMethod,
      })
    );
  },
};

// Performance testing utilities
export const performanceTestUtils = {
  measureRenderTime: async (renderFn: () => void) => {
    const start = performance.now();
    renderFn();
    const end = performance.now();
    return end - start;
  },
  
  expectRenderTimeBelow: (renderTime: number, threshold: number) => {
    expect(renderTime).toBeLessThan(threshold);
  },
};

// Accessibility testing helpers
export const a11yTestHelpers = {
  expectNoA11yViolations: async (container: HTMLElement) => {
    const axeCore = await import('axe-core');
    const results = await axeCore.run(container);
    expect(results.violations).toHaveLength(0);
  },
  
  expectKeyboardNavigation: async (user: ReturnType<typeof userEvent.setup>, elements: HTMLElement[]) => {
    for (let i = 0; i < elements.length; i++) {
      await user.tab();
      expect(elements[i]).toHaveFocus();
    }
  },
};

// Export everything for easy imports
export {
  customRender as render,
  testTheme,
  AllTheProviders,
};

// Re-export everything from testing library
export * from '@testing-library/react';
export { userEvent };