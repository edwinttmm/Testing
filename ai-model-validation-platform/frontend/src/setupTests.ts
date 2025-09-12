/**
 * SPARC + TDD London School Enhanced Test Setup
 * Global test configuration and environment setup
 */

// Polyfill for TextEncoder/TextDecoder in test environment
import { TextEncoder, TextDecoder } from 'util';

import '@testing-library/jest-dom';
(global as Record<string, unknown>).TextEncoder = TextEncoder;
(global as Record<string, unknown>).TextDecoder = TextDecoder;

// Basic test environment setup without MSW for now
// Global console warnings suppression for known issues
// Test environment console override - keeping as-is for test infrastructure
const originalConsoleWarn = console.warn;
console.warn = (...args: unknown[]) => {
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

// Global error handler for unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  // Test environment error handling - keeping console.error for test infrastructure
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Mock modules that are problematic in test environment
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => children,
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

// Mock axios for testing
jest.mock('axios', () => ({
  __esModule: true,
  default: {
    create: jest.fn(() => ({
      get: jest.fn(() => Promise.resolve({ data: {} })),
      post: jest.fn(() => Promise.resolve({ data: {} })),
      put: jest.fn(() => Promise.resolve({ data: {} })),
      delete: jest.fn(() => Promise.resolve({ data: {} })),
      patch: jest.fn(() => Promise.resolve({ data: {} })),
      interceptors: {
        request: { use: jest.fn(), eject: jest.fn() },
        response: { use: jest.fn(), eject: jest.fn() }
      }
    })),
    get: jest.fn(() => Promise.resolve({ data: {} })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
    put: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
    patch: jest.fn(() => Promise.resolve({ data: {} })),
    interceptors: {
      request: { use: jest.fn(), eject: jest.fn() },
      response: { use: jest.fn(), eject: jest.fn() }
    }
  },
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
    configReady: true, // Add missing property
  })),
}));

// Mock file upload APIs
Object.defineProperty(window, 'File', {
  value: class MockFile {
    constructor(
      public parts: (string | ArrayBuffer | Blob)[],
      public name: string, 
      public options: FilePropertyBag = {}
    ) {
      this.size = parts.reduce((acc, part) => {
        if (typeof part === 'string') return acc + part.length;
        if (part instanceof ArrayBuffer) return acc + part.byteLength;
        if (part instanceof Blob) return acc + part.size;
        return acc;
      }, 0);
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

// ========================================
// COMPREHENSIVE CANVAS MOCKING
// ========================================

// Create comprehensive CanvasRenderingContext2D mock
const createMockCanvasContext = (): Partial<CanvasRenderingContext2D> => {
  const context = {
    // Drawing rectangle methods
    clearRect: jest.fn(),
    fillRect: jest.fn(),
    strokeRect: jest.fn(),
    
    // Path methods
    beginPath: jest.fn(),
    closePath: jest.fn(),
    moveTo: jest.fn(),
    lineTo: jest.fn(),
    bezierCurveTo: jest.fn(),
    quadraticCurveTo: jest.fn(),
    arc: jest.fn(),
    arcTo: jest.fn(),
    ellipse: jest.fn(),
    rect: jest.fn(),
    
    // Drawing methods
    fill: jest.fn(),
    stroke: jest.fn(),
    drawImage: jest.fn(),
    
    // Text methods
    fillText: jest.fn(),
    strokeText: jest.fn(),
    measureText: jest.fn(() => ({ 
      width: 50, 
      actualBoundingBoxLeft: 0,
      actualBoundingBoxRight: 50,
      fontBoundingBoxAscent: 10,
      fontBoundingBoxDescent: 2,
      actualBoundingBoxAscent: 8,
      actualBoundingBoxDescent: 2,
      emHeightAscent: 10,
      emHeightDescent: 2,
      hangingBaseline: 8,
      alphabeticBaseline: 0,
      ideographicBaseline: -2,
    })),
    
    // Transform methods
    save: jest.fn(),
    restore: jest.fn(),
    scale: jest.fn(),
    rotate: jest.fn(),
    translate: jest.fn(),
    transform: jest.fn(),
    setTransform: jest.fn(),
    resetTransform: jest.fn(),
    
    // Clipping methods
    clip: jest.fn(),
    
    // Image data methods
    createImageData: jest.fn(() => ({
      data: new Uint8ClampedArray(4),
      width: 1,
      height: 1,
      colorSpace: 'srgb' as PredefinedColorSpace,
    })),
    getImageData: jest.fn(() => ({
      data: new Uint8ClampedArray(4),
      width: 1,
      height: 1,
      colorSpace: 'srgb' as PredefinedColorSpace,
    })),
    putImageData: jest.fn(),
    
    // Line styles
    setLineDash: jest.fn(),
    getLineDash: jest.fn(() => []),
    
    // Gradient and pattern methods
    createLinearGradient: jest.fn(() => ({
      addColorStop: jest.fn(),
    } as CanvasGradient)),
    createRadialGradient: jest.fn(() => ({
      addColorStop: jest.fn(),
    } as CanvasGradient)),
    createConicGradient: jest.fn(() => ({
      addColorStop: jest.fn(),
    } as CanvasGradient)),
    createPattern: jest.fn(() => ({} as CanvasPattern)),
    
    // Hit detection
    isPointInPath: jest.fn(() => false),
    isPointInStroke: jest.fn(() => false),
    
    // Canvas state - cast as unknown first, then as HTMLCanvasElement
    canvas: ({
      width: 800,
      height: 600,
      toDataURL: jest.fn(() => 'data:image/png;base64,'),
      toBlob: jest.fn(),
      transferControlToOffscreen: jest.fn(),
      captureStream: jest.fn(),
      getContext: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      getBoundingClientRect: jest.fn(() => ({
        left: 0,
        top: 0,
        right: 800,
        bottom: 600,
        width: 800,
        height: 600,
        x: 0,
        y: 0,
        toJSON: jest.fn(),
      })),
    } as unknown as HTMLCanvasElement),
    
    // Drawing style properties (getters/setters)
    strokeStyle: '#000000',
    fillStyle: '#000000',
    globalAlpha: 1,
    lineWidth: 1,
    lineCap: 'butt' as CanvasLineCap,
    lineJoin: 'miter' as CanvasLineJoin,
    miterLimit: 10,
    lineDashOffset: 0,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    shadowBlur: 0,
    shadowColor: 'rgba(0, 0, 0, 0)',
    globalCompositeOperation: 'source-over' as GlobalCompositeOperation,
    font: '10px sans-serif',
    textAlign: 'start' as CanvasTextAlign,
    textBaseline: 'alphabetic' as CanvasTextBaseline,
    direction: 'inherit' as CanvasDirection,
    letterSpacing: '0px',
    fontKerning: 'auto' as CanvasFontKerning,
    fontStretch: 'normal' as CanvasFontStretch,
    fontVariantCaps: 'normal' as CanvasFontVariantCaps,
    textRendering: 'auto' as CanvasTextRendering,
    wordSpacing: '0px',
    imageSmoothingEnabled: true,
    imageSmoothingQuality: 'low' as ImageSmoothingQuality,
    
    // Filter property
    filter: 'none',
  };
  
  return context;
};

// Global canvas context instance
const mockCanvasContext = createMockCanvasContext();

// Mock HTMLCanvasElement.getContext method
const originalGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = jest.fn((contextType: string): any => {
  if (contextType === '2d') {
    return mockCanvasContext;
  }
  if (contextType === 'webgl' || contextType === 'webgl2') {
    // Mock WebGL context for basic compatibility
    return {
      clearColor: jest.fn(),
      clear: jest.fn(),
      drawArrays: jest.fn(),
      createProgram: jest.fn(),
      createShader: jest.fn(),
      deleteProgram: jest.fn(),
      deleteShader: jest.fn(),
      deleteBuffer: jest.fn(),
      deleteTexture: jest.fn(),
    };
  }
  return null;
});

// Mock HTMLCanvasElement properties and methods
Object.defineProperty(HTMLCanvasElement.prototype, 'width', {
  get: jest.fn(() => 800),
  set: jest.fn(),
  configurable: true,
});

Object.defineProperty(HTMLCanvasElement.prototype, 'height', {
  get: jest.fn(() => 600),
  set: jest.fn(),
  configurable: true,
});

HTMLCanvasElement.prototype.getBoundingClientRect = jest.fn(() => ({
  left: 0,
  top: 0,
  right: 800,
  bottom: 600,
  width: 800,
  height: 600,
  x: 0,
  y: 0,
  toJSON: jest.fn(),
}));

HTMLCanvasElement.prototype.toDataURL = jest.fn(() => 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==');
HTMLCanvasElement.prototype.toBlob = jest.fn((callback: BlobCallback) => {
  const blob = new Blob(['fake-canvas-data'], { type: 'image/png' });
  callback(blob);
});

// Mock other HTML elements that might need getBoundingClientRect
const mockGetBoundingClientRect = () => ({
  left: 0,
  top: 0,
  right: 800,
  bottom: 600,
  width: 800,
  height: 600,
  x: 0,
  y: 0,
  toJSON: jest.fn(),
});

HTMLDivElement.prototype.getBoundingClientRect = jest.fn(mockGetBoundingClientRect);
HTMLElement.prototype.getBoundingClientRect = jest.fn(mockGetBoundingClientRect);

// Mock requestAnimationFrame and cancelAnimationFrame for canvas animation loops
const originalRequestAnimationFrame = global.requestAnimationFrame;
const originalCancelAnimationFrame = global.cancelAnimationFrame;

global.requestAnimationFrame = jest.fn((callback: FrameRequestCallback) => {
  return setTimeout(() => callback(Date.now()), 16) as unknown as number;
});

global.cancelAnimationFrame = jest.fn((id: number) => {
  clearTimeout(id);
});

// Mock ResizeObserver for responsive canvas components
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock IntersectionObserver for viewport-based optimizations
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
  root: null,
  rootMargin: '',
  thresholds: [],
}));

// Mock Performance API for performance testing
global.performance.mark = jest.fn();
global.performance.measure = jest.fn();
global.performance.clearMarks = jest.fn();
global.performance.clearMeasures = jest.fn();
global.performance.getEntriesByName = jest.fn(() => []);
global.performance.getEntriesByType = jest.fn(() => []);

// Utility function to reset canvas mocks
global.resetCanvasMocks = () => {
  Object.values(mockCanvasContext).forEach(mock => {
    if (typeof mock === 'function' && mock && typeof (mock as jest.Mock).mockClear === 'function') {
      (mock as jest.Mock).mockClear();
    }
  });
};

// Utility function to get canvas mock context
global.getMockCanvasContext = () => mockCanvasContext;

// Add cleanup after each test
afterEach(() => {
  if (global.resetCanvasMocks) {
    global.resetCanvasMocks();
  }
});

// Cleanup function for restoring originals if needed
global.restoreCanvasMocks = () => {
  HTMLCanvasElement.prototype.getContext = originalGetContext;
  global.requestAnimationFrame = originalRequestAnimationFrame;
  global.cancelAnimationFrame = originalCancelAnimationFrame;
};

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