import { AnnotationShape, Point, AnnotationStyle } from '../../components/annotation/types';

// Utility imports (assuming these exist)
export const GeometryUtils = {
  calculateBoundingBox: (points: Point[]) => {
    if (points.length === 0) return { x: 0, y: 0, width: 0, height: 0 };
    const xs = points.map(p => p.x);
    const ys = points.map(p => p.y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  },
  
  pointInPolygon: (point: Point, polygon: Point[]): boolean => {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      if (((polygon[i].y > point.y) !== (polygon[j].y > point.y)) &&
          (point.x < (polygon[j].x - polygon[i].x) * (point.y - polygon[i].y) / (polygon[j].y - polygon[i].y) + polygon[i].x)) {
        inside = !inside;
      }
    }
    return inside;
  }
};

export const PerformanceUtils = {
  measureTime: <T>(fn: () => T): { result: T; duration: number } => {
    const start = performance.now();
    const result = fn();
    const duration = performance.now() - start;
    return { result, duration };
  },
  
  getMemoryUsage: (): { used: number; total: number } | null => {
    if ('memory' in performance) {
      return {
        used: (performance as any).memory.usedJSHeapSize,
        total: (performance as any).memory.totalJSHeapSize,
      };
    }
    return null;
  }
};

// Test utility functions and mock data for annotation testing

/**
 * Mock Canvas Context - Uses global mocks from setupTests.ts
 */
export const createMockCanvasContext = () => {
  // Use the global canvas context mock from setupTests.ts
  const context = global.getMockCanvasContext?.() || {
    clearRect: jest.fn(),
    save: jest.fn(),
    restore: jest.fn(),
    scale: jest.fn(),
    translate: jest.fn(),
    drawImage: jest.fn(),
    strokeStyle: '#000000',
    fillStyle: '#000000',
    lineWidth: 1,
    globalAlpha: 1,
    strokeRect: jest.fn(),
    fillRect: jest.fn(),
    beginPath: jest.fn(),
    moveTo: jest.fn(),
    lineTo: jest.fn(),
    closePath: jest.fn(),
    stroke: jest.fn(),
    fill: jest.fn(),
    arc: jest.fn(),
    setLineDash: jest.fn(),
    font: '10px Arial',
    textAlign: 'left' as CanvasTextAlign,
    textBaseline: 'alphabetic' as CanvasTextBaseline,
    fillText: jest.fn(),
    strokeText: jest.fn(),
    measureText: jest.fn(() => ({ width: 100 })),
    createLinearGradient: jest.fn(),
    createRadialGradient: jest.fn(),
    createPattern: jest.fn(),
    clip: jest.fn(),
    isPointInPath: jest.fn(() => true),
  };

  // Reset all mocks
  const resetMocks = () => {
    if (global.resetCanvasMocks) {
      global.resetCanvasMocks();
    } else {
      Object.values(context).forEach(mock => {
        if (typeof mock === 'function' && 'mockClear' in mock) {
          (mock as jest.Mock).mockClear();
        }
      });
    }
  };

  return { context, resetMocks };
};

/**
 * Setup Canvas Mock - Uses global setup from setupTests.ts
 */
export const setupCanvasMock = () => {
  const { context, resetMocks } = createMockCanvasContext();
  
  // Canvas mocks are already set up in setupTests.ts, just return the interface
  return { context, resetMocks };
};

/**
 * Mock Shape Factory
 */
export class MockShapeFactory {
  private static idCounter = 0;

  static rectangle(options: Partial<AnnotationShape> = {}): AnnotationShape {
    const id = options.id || `rect_${++this.idCounter}`;
    const x = options.boundingBox?.x || 50;
    const y = options.boundingBox?.y || 50;
    const width = options.boundingBox?.width || 100;
    const height = options.boundingBox?.height || 100;

    return {
      id,
      type: 'rectangle',
      points: [
        { x, y },
        { x: x + width, y },
        { x: x + width, y: y + height },
        { x, y: y + height },
      ],
      boundingBox: { x, y, width, height },
      style: {
        strokeColor: '#3498db',
        fillColor: 'rgba(52, 152, 219, 0.2)',
        strokeWidth: 2,
        fillOpacity: 0.2,
        ...options.style,
      },
      visible: true,
      selected: false,
      ...options,
    };
  }

  static polygon(points?: Point[], options: Partial<AnnotationShape> = {}): AnnotationShape {
    const id = options.id || `poly_${++this.idCounter}`;
    const defaultPoints = points || [
      { x: 100, y: 100 },
      { x: 200, y: 100 },
      { x: 150, y: 200 },
    ];

    const xs = defaultPoints.map(p => p.x);
    const ys = defaultPoints.map(p => p.y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);

    return {
      id,
      type: 'polygon',
      points: defaultPoints,
      boundingBox: {
        x: minX,
        y: minY,
        width: maxX - minX,
        height: maxY - minY,
      },
      style: {
        strokeColor: '#e74c3c',
        fillColor: 'rgba(231, 76, 60, 0.2)',
        strokeWidth: 2,
        fillOpacity: 0.2,
        ...options.style,
      },
      visible: true,
      selected: false,
      ...options,
    };
  }

  static point(point?: Point, options: Partial<AnnotationShape> = {}): AnnotationShape {
    const id = options.id || `point_${++this.idCounter}`;
    const defaultPoint = point || { x: 100, y: 100 };

    return {
      id,
      type: 'point',
      points: [defaultPoint],
      boundingBox: {
        x: defaultPoint.x - 5,
        y: defaultPoint.y - 5,
        width: 10,
        height: 10,
      },
      style: {
        strokeColor: '#f39c12',
        fillColor: 'rgba(243, 156, 18, 0.8)',
        strokeWidth: 2,
        fillOpacity: 0.8,
        ...options.style,
      },
      visible: true,
      selected: false,
      ...options,
    };
  }

  static brush(points?: Point[], options: Partial<AnnotationShape> = {}): AnnotationShape {
    const id = options.id || `brush_${++this.idCounter}`;
    const defaultPoints = points || [
      { x: 100, y: 100 },
      { x: 110, y: 105 },
      { x: 120, y: 110 },
      { x: 130, y: 115 },
    ];

    const xs = defaultPoints.map(p => p.x);
    const ys = defaultPoints.map(p => p.y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);

    return {
      id,
      type: 'brush',
      points: defaultPoints,
      boundingBox: {
        x: minX - 5,
        y: minY - 5,
        width: maxX - minX + 10,
        height: maxY - minY + 10,
      },
      style: {
        strokeColor: '#9b59b6',
        fillColor: 'rgba(155, 89, 182, 0.3)',
        strokeWidth: 5,
        fillOpacity: 0.3,
        ...options.style,
      },
      visible: true,
      selected: false,
      ...options,
    };
  }

  static resetCounter() {
    this.idCounter = 0;
  }
}

/**
 * Mock Event Factory
 */
export class MockEventFactory {
  static mouseEvent(
    type: string,
    coordinates: { clientX: number; clientY: number },
    options: Partial<MouseEvent> = {}
  ): MouseEvent {
    return new MouseEvent(type, {
      clientX: coordinates.clientX,
      clientY: coordinates.clientY,
      bubbles: true,
      cancelable: true,
      ...options,
    });
  }

  static keyboardEvent(
    type: string,
    key: string,
    options: Partial<KeyboardEvent> = {}
  ): KeyboardEvent {
    return new KeyboardEvent(type, {
      key,
      bubbles: true,
      cancelable: true,
      ...options,
    });
  }

  static pointerEvent(
    type: string,
    coordinates: { clientX: number; clientY: number },
    options: Partial<PointerEvent> = {}
  ): PointerEvent {
    return new PointerEvent(type, {
      clientX: coordinates.clientX,
      clientY: coordinates.clientY,
      bubbles: true,
      cancelable: true,
      pressure: 1,
      ...options,
    });
  }
}

// GeometryUtils now imported from centralized utility

/**
 * Animation Testing Utilities
 */
export const AnimationUtils = {
  /**
   * Mock requestAnimationFrame for testing
   */
  mockAnimationFrame() {
    let frameId = 0;
    const callbacks = new Map<number, FrameRequestCallback>();

    global.requestAnimationFrame = jest.fn((callback: FrameRequestCallback) => {
      const id = ++frameId;
      callbacks.set(id, callback);
      return id;
    });

    global.cancelAnimationFrame = jest.fn((id: number) => {
      callbacks.delete(id);
    });

    const triggerFrame = (timestamp = performance.now()) => {
      callbacks.forEach(callback => callback(timestamp));
      callbacks.clear();
    };

    return { triggerFrame };
  },

  /**
   * Wait for animation frame
   */
  waitForAnimationFrame(): Promise<void> {
    return new Promise(resolve => {
      requestAnimationFrame(() => resolve());
    });
  },
};

// PerformanceUtils now imported from centralized utility

/**
 * Test Data Generators
 */
export const TestDataGenerator = {
  /**
   * Generate random point within bounds
   */
  randomPoint(bounds = { minX: 0, minY: 0, maxX: 800, maxY: 600 }): Point {
    return {
      x: Math.random() * (bounds.maxX - bounds.minX) + bounds.minX,
      y: Math.random() * (bounds.maxY - bounds.minY) + bounds.minY,
    };
  },

  /**
   * Generate random polygon
   */
  randomPolygon(vertices = 5, center = { x: 400, y: 300 }, radius = 100): Point[] {
    const points: Point[] = [];
    for (let i = 0; i < vertices; i++) {
      const angle = (i / vertices) * 2 * Math.PI;
      const r = radius + (Math.random() - 0.5) * radius * 0.3; // Add some variation
      points.push({
        x: center.x + Math.cos(angle) * r,
        y: center.y + Math.sin(angle) * r,
      });
    }
    return points;
  },

  /**
   * Generate test shapes of different types
   */
  generateShapes(count: number): AnnotationShape[] {
    const shapes: AnnotationShape[] = [];
    const types: Array<'rectangle' | 'polygon' | 'point' | 'brush'> = ['rectangle', 'polygon', 'point', 'brush'];

    for (let i = 0; i < count; i++) {
      const type = types[i % types.length];
      
      switch (type) {
        case 'rectangle':
          shapes.push(MockShapeFactory.rectangle({
            boundingBox: {
              x: Math.random() * 700,
              y: Math.random() * 500,
              width: 50 + Math.random() * 100,
              height: 50 + Math.random() * 100,
            },
          }));
          break;
        case 'polygon':
          shapes.push(MockShapeFactory.polygon(this.randomPolygon()));
          break;
        case 'point':
          shapes.push(MockShapeFactory.point(this.randomPoint()));
          break;
        case 'brush':
          const brushPoints: Point[] = [];
          const startPoint = this.randomPoint();
          for (let j = 0; j < 10; j++) {
            brushPoints.push({
              x: startPoint.x + j * 10 + (Math.random() - 0.5) * 20,
              y: startPoint.y + (Math.random() - 0.5) * 20,
            });
          }
          shapes.push(MockShapeFactory.brush(brushPoints));
          break;
      }
    }

    return shapes;
  },

  /**
   * Generate stress test data
   */
  generateStressTestData(shapeCount = 1000): {
    shapes: AnnotationShape[];
    memoryEstimate: number;
  } {
    const shapes = this.generateShapes(shapeCount);
    
    // Rough memory estimate (in bytes)
    const memoryEstimate = shapes.length * 500; // Approximate size per shape
    
    return { shapes, memoryEstimate };
  },
};

/**
 * Assertion Helpers
 */
export const AssertionHelpers = {
  /**
   * Assert that canvas drawing occurred
   */
  expectCanvasDrawing(context: any, operations: string[]) {
    operations.forEach(operation => {
      expect(context[operation]).toHaveBeenCalled();
    });
  },

  /**
   * Assert shape properties
   */
  expectShapeProperties(shape: AnnotationShape, expected: Partial<AnnotationShape>) {
    Object.keys(expected).forEach(key => {
      expect(shape[key as keyof AnnotationShape]).toEqual(expected[key as keyof AnnotationShape]);
    });
  },

  /**
   * Assert point approximately equals
   */
  expectPointNear(actual: Point, expected: Point, tolerance = 1) {
    expect(Math.abs(actual.x - expected.x)).toBeLessThanOrEqual(tolerance);
    expect(Math.abs(actual.y - expected.y)).toBeLessThanOrEqual(tolerance);
  },

  /**
   * Assert bounding box contains point
   */
  expectBoundingBoxContains(bbox: { x: number; y: number; width: number; height: number }, point: Point) {
    expect(point.x).toBeGreaterThanOrEqual(bbox.x);
    expect(point.x).toBeLessThanOrEqual(bbox.x + bbox.width);
    expect(point.y).toBeGreaterThanOrEqual(bbox.y);
    expect(point.y).toBeLessThanOrEqual(bbox.y + bbox.height);
  },
};

/**
 * Test Environment Setup
 */
export const setupTestEnvironment = () => {
  const { context, resetMocks } = setupCanvasMock();
  const { triggerFrame } = AnimationUtils.mockAnimationFrame();
  
  // Mock performance API if not available
  if (typeof performance === 'undefined') {
    (global as any).performance = {
      now: jest.fn(() => Date.now()),
      mark: jest.fn(),
      measure: jest.fn(),
    };
  }

  // Mock ResizeObserver
  global.ResizeObserver = jest.fn(() => ({
    observe: jest.fn(),
    disconnect: jest.fn(),
    unobserve: jest.fn(),
  }));

  // Clean up function
  const cleanup = () => {
    resetMocks();
    MockShapeFactory.resetCounter();
    jest.clearAllTimers();
    jest.restoreAllMocks();
  };

  return {
    context,
    resetMocks,
    triggerFrame,
    cleanup,
  };
};

export default {
  MockShapeFactory,
  MockEventFactory,
  AnimationUtils,
  TestDataGenerator,
  AssertionHelpers,
  setupTestEnvironment,
};