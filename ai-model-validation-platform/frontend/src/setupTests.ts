/**
 * SPARC + TDD London School Enhanced Test Setup
 * Global test configuration and environment setup
 */

// Polyfill for TextEncoder/TextDecoder in test environment
import { TextEncoder, TextDecoder } from 'util';
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

import '@testing-library/jest-dom';
import { setupServer } from 'msw/node';
import { apiMockHandlers } from './tests/mocks/api.mock';
import { setupTestEnvironment } from './tests/helpers/test-utils';

// Setup MSW server globally
export const server = setupServer(...apiMockHandlers);

// Polyfill for Node.js environment
if (typeof global.TextEncoder === 'undefined') {
  const { TextEncoder, TextDecoder } = require('util');
  global.TextEncoder = TextEncoder;
  global.TextDecoder = TextDecoder;
}

// Global test setup
beforeAll(() => {
  // Start MSW server
  server.listen({
    onUnhandledRequest: 'warn',
  });
  
  // Setup test environment
  setupTestEnvironment();
  
  // Global console warnings suppression for known issues
  const originalConsoleWarn = console.warn;
  console.warn = (...args: any[]) => {
    // Suppress known React 19 warnings during testing
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('ReactDOM.render is deprecated') ||
       args[0].includes('Warning: validateDOMNesting'))
    ) {
      return;
    }
    originalConsoleWarn.apply(console, args);
  };
});

// Clean up after each test
afterEach(() => {
  server.resetHandlers();
  
  // Clear any remaining timeouts/intervals
  jest.clearAllTimers();
  
  // Clean up any open modals or overlays
  const modals = document.querySelectorAll('[role="dialog"]');
  modals.forEach(modal => modal.remove());
  
  // Clean up any tooltip portals
  const tooltips = document.querySelectorAll('[role="tooltip"]');
  tooltips.forEach(tooltip => tooltip.remove());
});

// Global cleanup
afterAll(() => {
  server.close();
});

// Global error handler for unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Mock modules that are problematic in test environment
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => children,
  LineChart: () => 'div',
  Line: () => 'div',
  XAxis: () => 'div',
  YAxis: () => 'div',
  CartesianGrid: () => 'div',
  Tooltip: () => 'div',
  Legend: () => 'div',
  BarChart: () => 'div',
  Bar: () => 'div',
  PieChart: () => 'div',
  Pie: () => 'div',
  Cell: () => 'div',
}));

// Mock WebSocket for testing
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    connected: true,
  })),
}));

// Mock file upload APIs
Object.defineProperty(window, 'File', {
  value: class MockFile {
    constructor(public parts: any[], public name: string, public options: any = {}) {
      this.size = parts.reduce((acc, part) => acc + (part.length || part.size || 0), 0);
      this.type = options.type || 'text/plain';
      this.lastModified = options.lastModified || Date.now();
    }
    size: number;
    type: string;
    lastModified: number;
  },
});

Object.defineProperty(window, 'FileList', {
  value: class MockFileList extends Array {
    item(index: number) {
      return this[index] || null;
    }
  },
});

// Mock drag and drop APIs
Object.defineProperty(window, 'DataTransfer', {
  value: class MockDataTransfer {
    dropEffect = 'none';
    effectAllowed = 'uninitialized';
    files = [];
    items = [];
    types = [];
    
    clearData() {}
    getData() { return ''; }
    setData() {}
    setDragImage() {}
  },
});

// Enhanced test timeout for complex interactions
jest.setTimeout(10000);

// Custom matchers for better assertions
expect.extend({
  toBeInViewport(element: HTMLElement) {
    const rect = element.getBoundingClientRect();
    const isVisible = (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
    
    return {
      pass: isVisible,
      message: () => isVisible 
        ? `Expected element not to be in viewport`
        : `Expected element to be in viewport`,
    };
  },
  
  toHaveValidForm(form: HTMLFormElement) {
    const isValid = form.checkValidity();
    return {
      pass: isValid,
      message: () => isValid
        ? `Expected form to be invalid`
        : `Expected form to be valid`,
    };
  },
});

// Add custom matchers to TypeScript
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeInViewport(): R;
      toHaveValidForm(): R;
    }
  }
}