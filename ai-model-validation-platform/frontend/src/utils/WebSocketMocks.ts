/**
 * WebSocket Mock Utilities for Testing
 * Provides comprehensive mocking for WebSocket connections and related functionality
 */

import { WebSocketConnectionStatus } from '../types/global';

/**
 * Mock WebSocket implementation for testing
 */
export class MockWebSocket implements Partial<WebSocket> {
  public readyState: number = WebSocket.CONNECTING;
  public url: string;
  public protocol?: string;
  public binaryType: BinaryType = 'blob';
  public bufferedAmount: number = 0;
  public extensions: string = '';

  // Event handlers
  public onopen: ((this: WebSocket, ev: Event) => any) | null = null;
  public onclose: ((this: WebSocket, ev: CloseEvent) => any) | null = null;
  public onmessage: ((this: WebSocket, ev: MessageEvent) => any) | null = null;
  public onerror: ((this: WebSocket, ev: Event) => any) | null = null;

  private eventListeners: Map<string, EventListener[]> = new Map();
  private messageQueue: any[] = [];

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocol = Array.isArray(protocols) ? (protocols[0] || '') : (protocols || '');
    
    // Simulate async connection
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      this.triggerEvent('open', new Event('open'));
    }, 100);
  }

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    this.messageQueue.push(data);
  }

  close(code?: number, reason?: string): void {
    this.readyState = WebSocket.CLOSED;
    const closeEventInit: CloseEventInit = {};
    if (code !== undefined) closeEventInit.code = code;
    if (reason !== undefined) closeEventInit.reason = reason;
    const closeEvent = new CloseEvent('close', closeEventInit);
    this.triggerEvent('close', closeEvent);
  }

  addEventListener(type: string, listener: EventListener): void {
    if (!this.eventListeners.has(type)) {
      this.eventListeners.set(type, []);
    }
    this.eventListeners.get(type)!.push(listener);
  }

  removeEventListener(type: string, listener: EventListener): void {
    const listeners = this.eventListeners.get(type);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  dispatchEvent(event: Event): boolean {
    this.triggerEvent(event.type, event);
    return true;
  }

  // Testing utilities
  simulateMessage(data: any): void {
    if (this.readyState === WebSocket.OPEN) {
      const messageEvent = new MessageEvent('message', { data });
      this.triggerEvent('message', messageEvent);
    }
  }

  simulateError(error?: string): void {
    const errorEvent = new Event('error');
    (errorEvent as any).message = error || 'Mock WebSocket error';
    this.triggerEvent('error', errorEvent);
  }

  simulateClose(code = 1000, reason = 'Normal closure'): void {
    this.readyState = WebSocket.CLOSED;
    const closeEvent = new CloseEvent('close', { code, reason });
    this.triggerEvent('close', closeEvent);
  }

  getMessageQueue(): any[] {
    return [...this.messageQueue];
  }

  clearMessageQueue(): void {
    this.messageQueue = [];
  }

  private triggerEvent(type: string, event: Event): void {
    // Call event handler property
    const handler = (this as any)[`on${type}`];
    if (handler) {
      handler.call(this, event);
    }

    // Call event listeners
    const listeners = this.eventListeners.get(type);
    if (listeners) {
      listeners.forEach(listener => listener(event));
    }
  }

  // WebSocket constants
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
}

/**
 * Mock WebSocket hook for React testing
 */
export const createMockWebSocketHook = (overrides: Partial<any> = {}) => ({
  socket: null,
  isConnected: false,
  error: null,
  connect: jest.fn(),
  disconnect: jest.fn(),
  emit: jest.fn(),
  on: jest.fn(() => jest.fn()),
  off: jest.fn(),
  configReady: true,
  connectionStatus: {
    isConnected: false,
    hasConnection: false,
    status: 'disconnected' as const,
    reconnectAttempts: 0,
    lastError: null,
    fallbackActive: false
  } as WebSocketConnectionStatus,
  lastMessage: null,
  messageHistory: [],
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,
  reconnectDelay: 1000,
  ...overrides
});

/**
 * Mock Socket.IO implementation
 */
export const createMockSocketIO = (overrides: Partial<any> = {}) => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    emit: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    connected: true,
    id: 'mock-socket-id',
    close: jest.fn(),
    open: jest.fn(),
    removeListener: jest.fn(),
    removeAllListeners: jest.fn(),
    listeners: jest.fn(() => []),
    eventNames: jest.fn(() => []),
    ...overrides
  }))
});

/**
 * Global WebSocket mock setup for testing environments
 */
export const setupGlobalWebSocketMocks = () => {
  // Mock WebSocket constructor
  (global as any).WebSocket = MockWebSocket;
  
  // Mock WebSocket constants
  (global as any).WebSocket.CONNECTING = 0;
  (global as any).WebSocket.OPEN = 1;
  (global as any).WebSocket.CLOSING = 2;
  (global as any).WebSocket.CLOSED = 3;

  // Mock MessageEvent and CloseEvent if not available
  if (typeof MessageEvent === 'undefined') {
    (global as any).MessageEvent = class MessageEvent extends Event {
      data: any;
      constructor(type: string, eventInitDict?: { data?: any }) {
        super(type);
        this.data = eventInitDict?.data;
      }
    };
  }

  if (typeof CloseEvent === 'undefined') {
    (global as any).CloseEvent = class CloseEvent extends Event {
      code: number;
      reason: string;
      wasClean: boolean;
      constructor(type: string, eventInitDict?: { code?: number; reason?: string; wasClean?: boolean }) {
        super(type);
        this.code = eventInitDict?.code || 1000;
        this.reason = eventInitDict?.reason || '';
        this.wasClean = eventInitDict?.wasClean || true;
      }
    };
  }
};

/**
 * WebSocket connection status mock
 */
export const createMockConnectionStatus = (overrides: Partial<WebSocketConnectionStatus> = {}): WebSocketConnectionStatus => ({
  isConnected: false,
  hasConnection: false,
  status: 'disconnected',
  reconnectAttempts: 0,
  lastError: null,
  fallbackActive: false,
  ...overrides
});

/**
 * Mock WebSocket server responses
 */
export const mockWebSocketResponses = {
  connectionSuccess: { type: 'connection', status: 'success', timestamp: Date.now() },
  connectionError: { type: 'connection', status: 'error', message: 'Connection failed', timestamp: Date.now() },
  dataUpdate: { type: 'data', payload: { updates: [] }, timestamp: Date.now() },
  heartbeat: { type: 'heartbeat', timestamp: Date.now() },
  authSuccess: { type: 'auth', status: 'authenticated', user: { id: 'mock-user' }, timestamp: Date.now() },
  authFailure: { type: 'auth', status: 'failed', message: 'Authentication failed', timestamp: Date.now() }
};

/**
 * Utility to clean up WebSocket mocks
 */
export const cleanupWebSocketMocks = () => {
  // Reset global WebSocket if it was mocked
  if ((global as any).WebSocket === MockWebSocket) {
    delete (global as any).WebSocket;
  }
  
  // Clear any timers that might have been set
  jest.clearAllTimers();
  jest.restoreAllMocks();
};