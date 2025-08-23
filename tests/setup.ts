/**
 * Jest test setup configuration for API integration tests
 */

import { jest } from '@jest/globals';

// Mock DOM APIs for jsdom environment
Object.defineProperty(window, 'location', {
  value: {
    hostname: 'localhost',
    protocol: 'http:',
    href: 'http://localhost:3000'
  },
  writable: true
});

Object.defineProperty(navigator, 'onLine', {
  writable: true,
  value: true
});

// Mock console to avoid noise in tests unless specifically testing console output
const originalConsole = global.console;
global.console = {
  ...originalConsole,
  log: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn()
};

// Mock timers for consistent test execution
beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
  jest.clearAllMocks();
});

// Mock FormData for file upload tests
global.FormData = class MockFormData {
  private data: Map<string, any> = new Map();

  append(key: string, value: any) {
    this.data.set(key, value);
  }

  get(key: string) {
    return this.data.get(key);
  }

  has(key: string) {
    return this.data.has(key);
  }

  delete(key: string) {
    this.data.delete(key);
  }
} as any;

// Mock File constructor for file upload tests
global.File = class MockFile {
  name: string;
  size: number;
  type: string;
  lastModified: number;

  constructor(chunks: any[], filename: string, options: any = {}) {
    this.name = filename;
    this.size = chunks.reduce((size, chunk) => {
      if (typeof chunk === 'string') {
        return size + chunk.length;
      } else if (chunk instanceof ArrayBuffer) {
        return size + chunk.byteLength;
      }
      return size;
    }, 0);
    this.type = options.type || '';
    this.lastModified = options.lastModified || Date.now();
  }
} as any;

// Mock ArrayBuffer for binary data tests
if (!global.ArrayBuffer) {
  global.ArrayBuffer = class MockArrayBuffer {
    byteLength: number;

    constructor(length: number) {
      this.byteLength = length;
    }
  } as any;
}

// Increase timeout for performance tests
jest.setTimeout(60000);

// Mock process.memoryUsage for memory tests
const mockMemoryUsage = jest.fn(() => ({
  rss: 50 * 1024 * 1024,      // 50MB
  heapTotal: 30 * 1024 * 1024, // 30MB  
  heapUsed: 20 * 1024 * 1024,  // 20MB
  external: 5 * 1024 * 1024,   // 5MB
  arrayBuffers: 1 * 1024 * 1024 // 1MB
}));

Object.defineProperty(process, 'memoryUsage', {
  value: mockMemoryUsage
});

// Mock global.gc for memory tests
global.gc = jest.fn();

// Mock performance.now for performance tests
const mockPerformanceNow = jest.fn(() => Date.now());
Object.defineProperty(global, 'performance', {
  value: {
    now: mockPerformanceNow
  }
});

// Mock URL for various tests
if (!global.URL) {
  global.URL = class MockURL {
    href: string;
    hostname: string;
    protocol: string;

    constructor(url: string) {
      this.href = url;
      const parts = url.split('://');
      this.protocol = parts[0] + ':';
      this.hostname = parts[1]?.split('/')[0] || 'localhost';
    }
  } as any;
}

// Suppress specific warnings during tests
const originalWarn = console.warn;
console.warn = (...args: any[]) => {
  // Suppress specific warnings that are expected in tests
  const message = args[0];
  if (typeof message === 'string') {
    if (message.includes('WebSocket') || 
        message.includes('Failed to report error') ||
        message.includes('Could not clear stale video cache')) {
      return; // Suppress these warnings
    }
  }
  originalWarn.apply(console, args);
};

// Global error handler for unhandled promise rejections in tests
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Export test utilities
export const testUtils = {
  mockMemoryUsage,
  mockPerformanceNow,
  
  // Helper to simulate network delays
  delay: (ms: number) => new Promise(resolve => setTimeout(resolve, ms)),
  
  // Helper to create mock responses
  createMockResponse: (data: any, status: number = 200) => ({
    data,
    status,
    statusText: status < 400 ? 'OK' : 'Error',
    headers: { 'content-type': 'application/json' }
  }),
  
  // Helper to create mock errors
  createMockError: (status: number, message: string, code?: string) => {
    const error: any = new Error(message);
    error.response = {
      status,
      data: { message },
      statusText: `HTTP ${status}`
    };
    if (code) error.code = code;
    return error;
  },

  // Helper to reset all mocks
  resetAllMocks: () => {
    jest.clearAllMocks();
    mockMemoryUsage.mockClear();
    mockPerformanceNow.mockClear();
  }
};

export default testUtils;