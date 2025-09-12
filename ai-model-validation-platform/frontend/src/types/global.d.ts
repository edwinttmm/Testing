/**
 * Global Type Declarations
 * Provides missing global types and interfaces for the application
 */

// Global window interface extensions using declare global pattern
// Re-export existing enums from services/types for global access
import { CameraType, SignalType, ProjectStatus } from '../services/types';

declare global {
  interface Window {
    RUNTIME_CONFIG: {
      REACT_APP_API_URL: string;
      REACT_APP_WS_URL?: string;
      REACT_APP_SOCKETIO_URL?: string;
      REACT_APP_VIDEO_BASE_URL?: string;
      REACT_APP_ENVIRONMENT?: string;
    };
    
    // Error Reporting Integration
    errorReporter?: {
      reportError: (data: Record<string, unknown>) => void;
    };
    
    // Error Tracking Service
    errorTracker?: {
      reportBatch: (errors: unknown[]) => void;
    };
    
    // Analytics Integration
    analytics?: {
      track: (event: string, data: Record<string, unknown>) => void;
    };
    
    // Claude Flow Integration
    claudeFlow?: {
      hooks?: {
        notify: (data: Record<string, unknown>) => Promise<void>;
      };
    };
    
    // Runtime Configuration Store
    runtimeConfig?: Record<string, unknown>;
    
    // Global Error Handler Setup Flag
    __globalErrorHandlerSetup?: boolean;
  }
}
export { CameraType, SignalType, ProjectStatus };

// Dataset interface (referenced in testUtils but not defined)
export interface Dataset {
  id: string;
  name: string;
  description?: string | undefined;
  project_id: string;
  projectId?: string | undefined;
  video_count?: number | undefined;
  created_at: string;
  updated_at: string;
  status?: string | undefined;
}

// Point interface for geometry operations
export interface Point {
  x: number;
  y: number;
}

// Rectangle interface for geometry operations
export interface Rectangle {
  x: number;
  y: number;
  width: number;
  height: number;
}

// Enhanced WebSocket connection status
export interface WebSocketConnectionStatus {
  isConnected: boolean;
  hasConnection: boolean;
  status: 'connected' | 'disconnected' | 'connecting' | 'reconnecting' | 'error';
  reconnectAttempts: number;
  lastError: Error | null;
  fallbackActive: boolean;
  reconnectTimeout?: number | undefined;
  maxReconnectAttempts?: number | undefined;
}

// Mock implementations for testing
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeWithinRange(floor: number, ceiling: number): R;
    }
  }
}

// Canvas mock types
export interface MockCanvasContext {
  clearRect: jest.Mock;
  save: jest.Mock;
  restore: jest.Mock;
  scale: jest.Mock;
  translate: jest.Mock;
  drawImage: jest.Mock;
  strokeStyle: string;
  fillStyle: string;
  lineWidth: number;
  globalAlpha: number;
  strokeRect: jest.Mock;
  fillRect: jest.Mock;
  beginPath: jest.Mock;
  moveTo: jest.Mock;
  lineTo: jest.Mock;
  closePath: jest.Mock;
  stroke: jest.Mock;
  fill: jest.Mock;
  arc: jest.Mock;
  setLineDash: jest.Mock;
  font: string;
  textAlign: CanvasTextAlign;
  textBaseline: CanvasTextBaseline;
  fillText: jest.Mock;
  strokeText: jest.Mock;
  measureText: jest.Mock;
  createLinearGradient: jest.Mock;
  createRadialGradient: jest.Mock;
  createPattern: jest.Mock;
  clip: jest.Mock;
  isPointInPath: jest.Mock;
}

// Performance measurement interfaces
export interface PerformanceBenchmark {
  name: string;
  avgTime: number;
  totalTime: number;
}

export interface MemoryUsage {
  used: number;
  total: number;
}

// Animation frame mock interface
export interface AnimationFrameMock {
  triggerFrame: (timestamp?: number) => void;
}

// Test environment setup interface
export interface TestEnvironmentSetup {
  context: MockCanvasContext;
  resetMocks: () => void;
  triggerFrame: (timestamp?: number) => void;
  cleanup: () => void;
}

// Timer types for cross-platform compatibility (DOM/Node.js)
export type TimerHandle = number | NodeJS.Timeout;
export type IntervalHandle = number | NodeJS.Timeout;
export type TimeoutHandle = number | NodeJS.Timeout;

// Timer utility functions
export interface TimerUtils {
  setTimeout: (callback: () => void, delay: number) => TimeoutHandle;
  setInterval: (callback: () => void, delay: number) => IntervalHandle;
  clearTimeout: (handle: TimeoutHandle | null | undefined) => void;
  clearInterval: (handle: IntervalHandle | null | undefined) => void;
}