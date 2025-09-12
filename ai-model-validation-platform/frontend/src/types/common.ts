/**
 * Common TypeScript interfaces to replace 'any' types throughout the application
 */

// Error handling interfaces
export interface ErrorContext {
  component?: string;
  action?: string;
  method?: string;
  url?: string;
  status?: number;
  timestamp?: Date;
  userAgent?: string;
  userFriendlyMessage?: string;
  originalMessage?: string;
}

export interface ErrorResponse {
  message: string;
  code?: string;
  status?: number;
  details?: unknown;
  context?: ErrorContext;
}

export interface ApiErrorData {
  message?: string;
  detail?: string;
  error?: string;
  status?: number;
}

export interface NetworkErrorContext extends ErrorContext {
  originalError: Error;
}

// Logging interfaces
export interface LogContext {
  action?: string;
  metadata?: Record<string, unknown>;
  performance?: {
    timestamp: number;
    duration: number;
  };
}

export interface LogLevel {
  level: 'debug' | 'info' | 'warn' | 'error';
  message: string;
  context?: LogContext;
  error?: Error;
}

// API response types
export interface AxiosResponseData<T = unknown> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
}

// Model configuration types
export interface ModelConfiguration {
  id: string;
  name: string;
  type: string;
  config: Record<string, unknown>;
}

// Generic function types
export interface GenericCallback<T = void> {
  (data: T): void;
}

export interface GenericCallbackWithEvent<T = void, E = Event> {
  (data: T, event?: E): void;
}

export interface GenericAsyncCallback<T = unknown, R = void> {
  (data: T): Promise<R>;
}

export interface GenericAsyncCallbackWithEvent<T = unknown, R = void, E = Event> {
  (data: T, event?: E): Promise<R>;
}

// WebSocket event types  
export interface WebSocketEventData {
  type: string;
  payload: unknown;
  timestamp: number;
}

// Component prop types
export interface BaseComponentProps {
  children?: React.ReactNode | undefined;
  className?: string | undefined;
  style?: React.CSSProperties | undefined;
}

export interface ComponentProps extends BaseComponentProps {
  id?: string | undefined;
  'data-testid'?: string | undefined;
}

// Performance metrics
export interface PerformanceMetrics {
  timestamp: number;
  duration: number;
  operation: string;
  slow: boolean;
}

// Function argument types
export type FunctionArgument = string | number | boolean | object | null | undefined;

// Error transformer function
export interface ErrorTransformer {
  (error: Error): string;
}

// Retry callback function
export interface RetryCallback {
  (attempt: number, error: Error): void;
}

// Generic error callback
export interface ErrorCallback {
  (error: Error): void;
}

// Test execution specific types
export interface TestConfiguration {
  modelName: string;
  confidenceThreshold: number;
  nmsThreshold: number;
  targetClasses: string[];
}

export interface TestResult {
  id: string;
  success: boolean;
  message: string;
  data?: unknown;
  error?: string;
}

// Video enhancement types
export interface VideoEnhancement {
  videoId: string;
  url: string;
  processed: boolean;
  metadata?: Record<string, unknown>;
}

// State change logging
export interface StateChangeLog {
  stateName: string;
  oldValue: string; // JSON stringified
  newValue: string; // JSON stringified
}