import React from 'react';
import { io, Socket } from 'socket.io-client';
import { logWebSocketError, safeConsoleError, safeConsoleWarn } from '../utils/safeErrorLogger';
import { isValidWebSocketData, isConnectionStatus, isObject, isString } from '../utils/typeGuards';

export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string;
  id?: string;
}

export interface ConnectionMetrics {
  connectionAttempts: number;
  lastConnected?: Date;
  lastDisconnected?: Date;
  reconnectCount: number;
  totalMessages: number;
  isStable: boolean;
}

export interface WebSocketServiceOptions {
  url?: string;
  autoConnect?: boolean;
  reconnection?: boolean;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
  timeout?: number;
  enableHeartbeat?: boolean;
  heartbeatInterval?: number;
}

class WebSocketService {
  private socket: Socket | null = null;
  private url: string;
  private options: WebSocketServiceOptions;
  private subscribers: Map<string, Set<(data: unknown) => void>> = new Map();
  private connectionState: 'disconnected' | 'connecting' | 'connected' | 'error' = 'disconnected';
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private metrics: ConnectionMetrics;
  private lastError: Error | null = null;

  constructor(options: WebSocketServiceOptions = {}) {
    // Dynamic WebSocket URL detection with fallback
    const getWebSocketUrl = () => {
      if (options.url || process.env.REACT_APP_WS_URL) {
        return options.url || process.env.REACT_APP_WS_URL;
      }
      
      const hostname = window.location.hostname;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      
      // Development environment (localhost)
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'ws://localhost:8000';
      }
      
      // Handle specific production server (155.138.239.131)
      if (hostname === '155.138.239.131') {
        return 'ws://155.138.239.131:8000';
      }
      
      // Generic fallback for other environments
      return `${protocol}//${hostname}:8000`;
    };

    this.url = getWebSocketUrl()!;
    this.options = {
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      timeout: 20000,
      enableHeartbeat: true,
      heartbeatInterval: 30000,
      ...options
    };

    this.metrics = {
      connectionAttempts: 0,
      reconnectCount: 0,
      totalMessages: 0,
      isStable: false
    };

    if (this.options.autoConnect) {
      this.connect();
    }

    // Setup cleanup on page unload
    window.addEventListener('beforeunload', () => {
      this.disconnect();
    });
  }

  connect(): Promise<boolean> {
    return new Promise((resolve, reject) => {
      if (this.socket && this.connectionState === 'connected') {
        console.log('🔌 WebSocket already connected');
        resolve(true);
        return;
      }

      try {
        this.connectionState = 'connecting';
        this.metrics.connectionAttempts++;
        
        console.log(`🔌 Connecting to WebSocket: ${this.url}`);

        this.socket = io(this.url, {
          transports: ['websocket', 'polling'],
          timeout: this.options.timeout || 20000,
          reconnection: this.options.reconnection !== false,
          reconnectionAttempts: this.options.reconnectionAttempts || 10,
          reconnectionDelay: this.options.reconnectionDelay || 1000,
        });

        // Connection success
        this.socket.on('connect', () => {
          console.log('✅ WebSocket connected');
          this.connectionState = 'connected';
          this.metrics.lastConnected = new Date();
          this.metrics.isStable = true;
          this.lastError = null;
          
          this.startHeartbeat();
          this.notifySubscribers('connection', { status: 'connected', metrics: this.metrics });
          resolve(true);
        });

        // Connection error
        this.socket.on('connect_error', (error) => {
          logWebSocketError('Connection failed', error, { function: 'connect_error' });
          this.connectionState = 'error';
          this.lastError = error;
          this.metrics.isStable = false;
          
          this.notifySubscribers('connection', { status: 'error', error: error.message });
          reject(error);
        });

        // Disconnection
        this.socket.on('disconnect', (reason) => {
          safeConsoleWarn('WebSocket disconnected', reason, { function: 'disconnect', component: 'websocket-service' });
          this.connectionState = 'disconnected';
          this.metrics.lastDisconnected = new Date();
          this.metrics.isStable = false;
          
          this.stopHeartbeat();
          this.notifySubscribers('connection', { status: 'disconnected', reason });

          // Attempt reconnection if it wasn't intentional
          if (reason !== 'io client disconnect' && this.options.reconnection) {
            this.scheduleReconnection();
          }
        });

        // Reconnection attempt
        this.socket.on('reconnect_attempt', (attempt) => {
          console.log(`🔄 WebSocket reconnection attempt ${attempt}/${this.options.reconnectionAttempts}`);
          this.metrics.reconnectCount++;
          this.notifySubscribers('connection', { status: 'reconnecting', attempt });
        });

        // Successful reconnection
        this.socket.on('reconnect', (attempt) => {
          console.log(`✅ WebSocket reconnected after ${attempt} attempts`);
          this.connectionState = 'connected';
          this.metrics.lastConnected = new Date();
          this.metrics.isStable = true;
          
          this.startHeartbeat();
          this.notifySubscribers('connection', { status: 'reconnected', attempts: attempt });
        });

        // Failed to reconnect
        this.socket.on('reconnect_failed', () => {
          logWebSocketError('Failed to reconnect after all attempts', 'Maximum reconnection attempts exceeded', { function: 'reconnect_failed' });
          this.connectionState = 'error';
          this.metrics.isStable = false;
          
          this.notifySubscribers('connection', { status: 'reconnect_failed' });
        });

        // Handle all incoming messages
        this.socket.onAny((eventName: string, data: unknown) => {
          if (!eventName.startsWith('connect')) {
            this.metrics.totalMessages++;
            console.log(`📨 WebSocket message [${eventName}]:`, data);
            
            const message: WebSocketMessage<unknown> = {
              type: eventName,
              payload: data,
              timestamp: new Date().toISOString()
            };
            
            this.notifySubscribers(eventName, message.payload);
            this.notifySubscribers('*', message); // Wildcard subscribers
          }
        });

      } catch (error) {
        logWebSocketError('Setup failed', error, { function: 'connect' });
        this.connectionState = 'error';
        this.lastError = error as Error;
        reject(error);
      }
    });
  }

  disconnect(): void {
    console.log('🔌 Disconnecting WebSocket...');
    
    this.stopHeartbeat();
    this.clearReconnectTimer();
    
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    
    this.connectionState = 'disconnected';
    this.notifySubscribers('connection', { status: 'disconnected', reason: 'manual' });
  }

  private scheduleReconnection(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = this.calculateReconnectDelay();
    console.log(`🔄 Scheduling reconnection in ${delay}ms`);

    this.reconnectTimer = setTimeout(() => {
      if (this.connectionState !== 'connected') {
        this.connect().catch(error => {
          logWebSocketError('Scheduled reconnection failed', error, { function: 'scheduleReconnection' });
        });
      }
    }, delay);
  }

  private calculateReconnectDelay(): number {
    const baseDelay = this.options.reconnectionDelay || 1000;
    const attempt = this.metrics.reconnectCount;
    const maxDelay = 30000; // 30 seconds max
    
    // Exponential backoff with jitter
    const delay = Math.min(baseDelay * Math.pow(1.5, attempt), maxDelay);
    const jitter = Math.random() * 0.1 * delay;
    
    return delay + jitter;
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startHeartbeat(): void {
    if (!this.options.enableHeartbeat) return;

    this.stopHeartbeat();
    
    this.heartbeatTimer = setInterval(() => {
      if (this.connectionState === 'connected' && this.socket) {
        console.log('💓 WebSocket heartbeat');
        this.socket.emit('ping', { timestamp: Date.now() });
      }
    }, this.options.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private notifySubscribers(eventType: string, data: unknown): void {
    const subscribers = this.subscribers.get(eventType);
    if (subscribers) {
      subscribers.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          logWebSocketError(`Subscriber callback failed for ${eventType}`, error, { function: 'notifySubscribers', eventType });
        }
      });
    }
  }

  // Public subscription methods
  subscribe<T = unknown>(eventType: string, callback: (data: T) => void): () => void {
    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, new Set());
    }
    
    this.subscribers.get(eventType)!.add(callback as (data: unknown) => void);
    
    console.log(`🔔 Subscribed to WebSocket event: ${eventType}`);

    // Return unsubscribe function
    return () => {
      const subscribers = this.subscribers.get(eventType);
      if (subscribers) {
        subscribers.delete(callback as (data: unknown) => void);
        if (subscribers.size === 0) {
          this.subscribers.delete(eventType);
        }
      }
      console.log(`🔕 Unsubscribed from WebSocket event: ${eventType}`);
    };
  }

  // Send message to server
  emit<T = unknown>(eventType: string, data?: T): boolean {
    if (this.connectionState !== 'connected' || !this.socket) {
      safeConsoleWarn(`Cannot emit ${eventType}: WebSocket not connected`, { connectionState: this.connectionState, hasSocket: !!this.socket }, { function: 'emit', eventType });
      return false;
    }

    // Validate data before sending
    if (data !== undefined && !isValidWebSocketData(data)) {
      console.warn(`⚠️ Invalid data for WebSocket emit [${eventType}]:`, data);
      return false;
    }

    try {
      console.log(`📤 WebSocket emit [${eventType}]:`, data);
      this.socket.emit(eventType, data);
      return true;
    } catch (error) {
      logWebSocketError(`Emit failed for ${eventType}`, error, { function: 'emit', eventType });
      return false;
    }
  }

  // Getters for status information
  get isConnected(): boolean {
    return this.connectionState === 'connected';
  }

  get connectionStatus(): string {
    return this.connectionState;
  }

  get connectionMetrics(): ConnectionMetrics {
    return { ...this.metrics };
  }

  get lastConnectionError(): Error | null {
    return this.lastError;
  }

  // Advanced features
  waitForConnection(timeout: number = 10000): Promise<boolean> {
    return new Promise((resolve, reject) => {
      if (this.isConnected) {
        resolve(true);
        return;
      }

      const timeoutTimer = setTimeout(() => {
        unsubscribe();
        reject(new Error('WebSocket connection timeout'));
      }, timeout);

      const unsubscribe = this.subscribe('connection', (data: unknown) => {
        if (!isObject(data)) {
          console.warn('⚠️ Invalid connection data received:', data);
          return;
        }
        
        const status = safeGet(data, 'status', '');
        if (!isConnectionStatus(status)) {
          console.warn('⚠️ Invalid connection status received:', status);
          return;
        }
        
        if (status === 'connected') {
          clearTimeout(timeoutTimer);
          unsubscribe();
          resolve(true);
        } else if (status === 'error' || status === 'reconnect_failed') {
          clearTimeout(timeoutTimer);
          unsubscribe();
          const errorMessage = safeGet(data, 'error', 'unknown error');
          reject(new Error(`WebSocket connection failed: ${errorMessage}`));
        }
      });

      // Trigger connection if not already connecting
      if (this.connectionState === 'disconnected') {
        this.connect().catch(reject);
      }
    });
  }

  // Utility method to check service health
  getHealthStatus() {
    return {
      isConnected: this.isConnected,
      connectionState: this.connectionState,
      url: this.url,
      metrics: this.metrics,
      lastError: this.lastError?.message,
      subscriberCount: Array.from(this.subscribers.values()).reduce((total, set) => total + set.size, 0)
    };
  }
}

// Create and export singleton instance
const websocketService = new WebSocketService();

// React hook for using WebSocket in components
export const useWebSocket = (eventType?: string) => {
  const [connectionState, setConnectionState] = React.useState(websocketService.connectionStatus);
  const [isConnected, setIsConnected] = React.useState(websocketService.isConnected);
  const [lastMessage, setLastMessage] = React.useState<WebSocketMessage<unknown> | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    // Subscribe to connection events
    const unsubscribeConnection = websocketService.subscribe('connection', (data: unknown) => {
      if (!isObject(data)) {
        console.warn('⚠️ Invalid connection data in hook:', data);
        return;
      }
      
      const status = data.status;
      if (!isConnectionStatus(status)) {
        console.warn('⚠️ Invalid connection status in hook:', status);
        return;
      }
      
      setConnectionState(status);
      setIsConnected(status === 'connected');
      
      if (status === 'error') {
        const errorMessage = isString(data.error) ? data.error : 'Connection error';
        setError(errorMessage);
      } else {
        setError(null);
      }
    });

    // Subscribe to specific event type if provided
    let unsubscribeEvent: (() => void) | undefined;
    if (eventType) {
      unsubscribeEvent = websocketService.subscribe(eventType, (data: unknown) => {
        if (!isValidWebSocketData(data)) {
          console.warn(`⚠️ Invalid WebSocket data for event ${eventType}:`, data);
          return;
        }
        
        setLastMessage({
          type: eventType,
          payload: data,
          timestamp: new Date().toISOString()
        });
      });
    }

    // Cleanup subscriptions
    return () => {
      unsubscribeConnection();
      if (unsubscribeEvent) {
        unsubscribeEvent();
      }
    };
  }, [eventType]);

  const emit = React.useCallback(<T = unknown>(type: string, data?: T) => {
    return websocketService.emit(type, data);
  }, []);

  const subscribe = React.useCallback(<T = unknown>(type: string, callback: (data: T) => void) => {
    return websocketService.subscribe(type, callback);
  }, []);

  return {
    isConnected,
    connectionState,
    lastMessage,
    error,
    emit,
    subscribe,
    metrics: websocketService.connectionMetrics,
    healthStatus: websocketService.getHealthStatus()
  };
};

export default websocketService;