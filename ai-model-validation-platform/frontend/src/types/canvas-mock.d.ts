/**
 * TypeScript declarations for canvas mock utilities
 */

declare global {
  namespace jest {
    interface Matchers<R> {
      toBeInViewport(): R;
      toHaveValidForm(): R;
    }
  }

  interface Window {
    resetCanvasMocks: () => void;
    getMockCanvasContext: () => Partial<CanvasRenderingContext2D>;
    restoreCanvasMocks: () => void;
  }

  var resetCanvasMocks: () => void;
  var getMockCanvasContext: () => Partial<CanvasRenderingContext2D>;
  var restoreCanvasMocks: () => void;
}

export interface MockCanvasContext extends Partial<CanvasRenderingContext2D> {
  // Additional mock-specific properties
  mockClear?: () => void;
  mockReset?: () => void;
}

export interface CanvasMockUtils {
  context: MockCanvasContext;
  resetMocks: () => void;
  cleanup: () => void;
}

export {};