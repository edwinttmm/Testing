/**
 * Integration Test Setup
 * 
 * Global setup and configuration for integration testing
 */

import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';
import { server } from '../mocks/server';
import 'jest-canvas-mock';

// ============================================================================
// TESTING LIBRARY CONFIGURATION
// ============================================================================

// Configure testing library
configure({
  testIdAttribute: 'data-testid',
  asyncUtilTimeout: 5000,
  computedStyleSupportsPseudoElements: true
});

// ============================================================================
// MOCK SERVER SETUP
// ============================================================================

// Start mock server before all tests
beforeAll(() => {
  server.listen({
    onUnhandledRequest: 'warn'
  });
});

// Reset handlers after each test
afterEach(() => {
  server.resetHandlers();
});

// Close server after all tests
afterAll(() => {
  server.close();
});

// ============================================================================
// GLOBAL MOCKS
// ============================================================================

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
  }
  
  callback: IntersectionObserverCallback;
  options?: IntersectionObserverInit;
  
  observe(target: Element) {
    // Immediately trigger callback for testing
    this.callback([
      {
        target,
        isIntersecting: true,
        intersectionRatio: 1,
        boundingClientRect: target.getBoundingClientRect(),
        intersectionRect: target.getBoundingClientRect(),
        rootBounds: null,
        time: Date.now()
      }
    ], this);
  }
  
  unobserve() {}
  disconnect() {}
};

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }
  
  callback: ResizeObserverCallback;
  
  observe(target: Element) {
    // Immediately trigger callback for testing
    this.callback([
      {
        target,
        contentRect: {
          x: 0,
          y: 0,
          width: 1920,
          height: 1080,
          top: 0,
          right: 1920,
          bottom: 1080,
          left: 0
        } as DOMRectReadOnly,
        borderBoxSize: [],
        contentBoxSize: [],
        devicePixelContentBoxSize: []
      }
    ], this);
  }
  
  unobserve() {}
  disconnect() {}
};

// Mock requestAnimationFrame
global.requestAnimationFrame = (callback: FrameRequestCallback) => {
  return setTimeout(() => callback(Date.now()), 16); // ~60fps
};

global.cancelAnimationFrame = (id: number) => {
  clearTimeout(id);
};

// Mock performance API
if (!global.performance) {
  global.performance = {
    now: () => Date.now(),
    mark: () => {},
    measure: () => {},
    getEntriesByName: () => [],
    getEntriesByType: () => [],
    clearMarks: () => {},
    clearMeasures: () => {}
  } as any;
}

// Add memory property for performance testing
if (!('memory' in global.performance)) {
  Object.defineProperty(global.performance, 'memory', {
    get: () => ({
      usedJSHeapSize: Math.floor(Math.random() * 100000000) + 50000000, // 50-150MB
      totalJSHeapSize: 200000000, // 200MB
      jsHeapSizeLimit: 4000000000 // 4GB
    })
  });
}

// ============================================================================
// WEBSOCKET MOCKING
// ============================================================================

// Mock WebSocket for integration tests
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  
  readyState: number = MockWebSocket.CONNECTING;
  url: string;
  protocol: string = '';
  
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  
  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    
    // Simulate connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }
  
  send(data: string | ArrayBuffer | Blob) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    
    // Echo back for testing
    setTimeout(() => {
      if (this.onmessage) {
        this.onmessage(new MessageEvent('message', { data }));
      }
    }, 1);
  }
  
  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    setTimeout(() => {
      if (this.onclose) {
        this.onclose(new CloseEvent('close', { code, reason }));
      }
    }, 1);
  }
  
  addEventListener(type: string, listener: EventListener) {
    switch (type) {
      case 'open':
        this.onopen = listener as any;
        break;
      case 'close':
        this.onclose = listener as any;
        break;
      case 'message':
        this.onmessage = listener as any;
        break;
      case 'error':
        this.onerror = listener as any;
        break;
    }
  }
  
  removeEventListener() {}
}

global.WebSocket = MockWebSocket as any;

// ============================================================================
// MEDIA ELEMENT MOCKING
// ============================================================================

// Mock HTMLVideoElement
Object.defineProperty(global.HTMLVideoElement.prototype, 'load', {
  writable: true,
  value: jest.fn()
});

Object.defineProperty(global.HTMLVideoElement.prototype, 'play', {
  writable: true,
  value: jest.fn().mockResolvedValue(undefined)
});

Object.defineProperty(global.HTMLVideoElement.prototype, 'pause', {
  writable: true,
  value: jest.fn()
});

Object.defineProperty(global.HTMLVideoElement.prototype, 'currentTime', {
  writable: true,
  value: 0
});

Object.defineProperty(global.HTMLVideoElement.prototype, 'duration', {
  writable: true,
  value: 60
});

Object.defineProperty(global.HTMLVideoElement.prototype, 'readyState', {
  writable: true,
  value: 4 // HAVE_ENOUGH_DATA
});

Object.defineProperty(global.HTMLVideoElement.prototype, 'videoWidth', {
  writable: true,
  value: 1920
});

Object.defineProperty(global.HTMLVideoElement.prototype, 'videoHeight', {
  writable: true,
  value: 1080
});

// Mock HTMLCanvasElement
Object.defineProperty(global.HTMLCanvasElement.prototype, 'getContext', {
  writable: true,
  value: jest.fn().mockReturnValue({
    fillRect: jest.fn(),
    clearRect: jest.fn(),
    getImageData: jest.fn().mockReturnValue({
      data: new Uint8ClampedArray(4)
    }),
    putImageData: jest.fn(),
    createImageData: jest.fn().mockReturnValue({
      data: new Uint8ClampedArray(4)
    }),
    setTransform: jest.fn(),
    drawImage: jest.fn(),
    save: jest.fn(),
    restore: jest.fn(),
    beginPath: jest.fn(),
    moveTo: jest.fn(),
    lineTo: jest.fn(),
    closePath: jest.fn(),
    stroke: jest.fn(),
    fill: jest.fn(),
    arc: jest.fn(),
    rect: jest.fn(),
    measureText: jest.fn().mockReturnValue({ width: 100 }),
    canvas: {
      width: 1920,
      height: 1080
    }
  })
});

// ============================================================================
// FILE API MOCKING
// ============================================================================

// Mock File constructor
global.File = class File extends Blob {
  name: string;
  lastModified: number;
  webkitRelativePath: string;
  
  constructor(fileBits: BlobPart[], fileName: string, options?: FilePropertyBag) {
    super(fileBits, options);
    this.name = fileName;
    this.lastModified = options?.lastModified || Date.now();
    this.webkitRelativePath = '';
  }
};

// Mock FileReader
global.FileReader = class FileReader extends EventTarget {
  result: any = null;
  error: any = null;
  readyState: number = 0;
  
  onload: ((this: FileReader, ev: ProgressEvent<FileReader>) => any) | null = null;
  onerror: ((this: FileReader, ev: ProgressEvent<FileReader>) => any) | null = null;
  onabort: ((this: FileReader, ev: ProgressEvent<FileReader>) => any) | null = null;
  onloadstart: ((this: FileReader, ev: ProgressEvent<FileReader>) => any) | null = null;
  onloadend: ((this: FileReader, ev: ProgressEvent<FileReader>) => any) | null = null;
  onprogress: ((this: FileReader, ev: ProgressEvent<FileReader>) => any) | null = null;
  
  abort() {
    this.readyState = 2;
  }
  
  readAsArrayBuffer(file: Blob) {
    this.readyState = 1;
    setTimeout(() => {
      this.readyState = 2;
      this.result = new ArrayBuffer(8);
      if (this.onload) {
        this.onload({ target: this } as any);
      }
    }, 10);
  }
  
  readAsDataURL(file: Blob) {
    this.readyState = 1;
    setTimeout(() => {
      this.readyState = 2;
      this.result = `data:${file.type};base64,${btoa('mock-file-content')}`;
      if (this.onload) {
        this.onload({ target: this } as any);
      }
    }, 10);
  }
  
  readAsText(file: Blob) {
    this.readyState = 1;
    setTimeout(() => {
      this.readyState = 2;
      this.result = 'mock file content';
      if (this.onload) {
        this.onload({ target: this } as any);
      }
    }, 10);
  }
  
  readAsBinaryString(file: Blob) {
    this.readyState = 1;
    setTimeout(() => {
      this.readyState = 2;
      this.result = 'mock binary content';
      if (this.onload) {
        this.onload({ target: this } as any);
      }
    }, 10);
  }
} as any;

// ============================================================================
// URL MOCKING
// ============================================================================

// Mock URL.createObjectURL
if (!global.URL) {
  global.URL = {
    createObjectURL: jest.fn().mockReturnValue('blob:mock-url'),
    revokeObjectURL: jest.fn()
  } as any;
} else {
  global.URL.createObjectURL = jest.fn().mockReturnValue('blob:mock-url');
  global.URL.revokeObjectURL = jest.fn();
}

// ============================================================================
// CUSTOM JEST MATCHERS
// ============================================================================

// Add custom matchers for integration testing
expect.extend({
  toBeWithinRange(received: number, floor: number, ceiling: number) {
    const pass = received >= floor && received <= ceiling;
    if (pass) {
      return {
        message: () => `expected ${received} not to be within range ${floor} - ${ceiling}`,
        pass: true
      };
    } else {
      return {
        message: () => `expected ${received} to be within range ${floor} - ${ceiling}`,
        pass: false
      };
    }
  },
  
  toHavePerformanceWithin(received: any, maxTime: number) {
    const duration = received.endTime - received.startTime;
    const pass = duration <= maxTime;
    
    if (pass) {
      return {
        message: () => `expected operation to take more than ${maxTime}ms, but took ${duration}ms`,
        pass: true
      };
    } else {
      return {
        message: () => `expected operation to take less than ${maxTime}ms, but took ${duration}ms`,
        pass: false
      };
    }
  },
  
  toHaveMemoryUsageUnder(received: any, maxMemoryMB: number) {
    const memoryUsageMB = received / 1024 / 1024;
    const pass = memoryUsageMB <= maxMemoryMB;
    
    if (pass) {
      return {
        message: () => `expected memory usage to be over ${maxMemoryMB}MB, but was ${memoryUsageMB.toFixed(2)}MB`,
        pass: true
      };
    } else {
      return {
        message: () => `expected memory usage to be under ${maxMemoryMB}MB, but was ${memoryUsageMB.toFixed(2)}MB`,
        pass: false
      };
    }
  }
});

// Extend Jest matchers type definition
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeWithinRange(floor: number, ceiling: number): R;
      toHavePerformanceWithin(maxTime: number): R;
      toHaveMemoryUsageUnder(maxMemoryMB: number): R;
    }
  }
}

// ============================================================================
// ERROR HANDLING
// ============================================================================

// Catch unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Enhanced error logging for tests
const originalError = console.error;
console.error = (...args: any[]) => {
  // Filter out expected React warnings in tests
  const message = args[0];
  if (typeof message === 'string') {
    // Ignore specific React warnings that are expected in tests
    if (
      message.includes('Warning: ReactDOM.render is no longer supported') ||
      message.includes('Warning: validateDOMNesting') ||
      message.includes('Warning: Each child in a list should have a unique "key" prop')
    ) {
      return;
    }
  }
  
  originalError.apply(console, args);
};

// ============================================================================
// TEST UTILITIES
// ============================================================================

// Global test utilities
global.testUtils = {
  // Wait for async operations
  waitForAsync: (ms: number = 0) => new Promise(resolve => setTimeout(resolve, ms)),
  
  // Create mock video file
  createMockVideoFile: (name: string = 'test-video.mp4', size: number = 1024 * 1024) => {
    return new File([new ArrayBuffer(size)], name, { type: 'video/mp4' });
  },
  
  // Trigger video events
  triggerVideoEvent: (video: HTMLVideoElement, eventType: string, data?: any) => {
    const event = new Event(eventType);
    Object.assign(event, data);
    video.dispatchEvent(event);
  },
  
  // Mock WebSocket server responses
  mockWebSocketMessage: (ws: WebSocket, message: any) => {
    if (ws.onmessage) {
      ws.onmessage(new MessageEvent('message', { data: JSON.stringify(message) }));
    }
  }
};

// Type declaration for global test utilities
declare global {
  interface Window {
    testUtils: typeof global.testUtils;
  }
  
  var testUtils: {
    waitForAsync: (ms?: number) => Promise<void>;
    createMockVideoFile: (name?: string, size?: number) => File;
    triggerVideoEvent: (video: HTMLVideoElement, eventType: string, data?: any) => void;
    mockWebSocketMessage: (ws: WebSocket, message: any) => void;
  };
}

console.log('✅ Integration test setup completed');
