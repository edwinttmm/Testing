import React from 'react';
import { io, Socket } from 'socket.io-client';
import { logWebSocketError, safeConsoleError, safeConsoleWarn } from '../utils/safeErrorLogger';
import { isValidWebSocketData, isConnectionStatus, isObject, isString, safeGet } from '../utils/typeGuards';
import { getConfigValueSync, waitForConfig, isConfigInitialized } from '../utils/configurationManager';

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
  private url: string = '';
  private urlResolved: boolean = false;
  private configReady: boolean = false;
  private options: WebSocketServiceOptions;
  private subscribers: Map<string, Set<(data: unknown) => void>> = new Map();
  private connectionState: 'disconnected' | 'connecting' | 'connected' | 'error' = 'disconnected';
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private metrics: ConnectionMetrics;
  private lastError: Error | null = null;
  private connectionQueue: (() => void)[] = [];

  // PROTOCOL #39: Event buffer and ordering for lifecycle events
  private eventBuffer: Map<number, any> = new Map();
  private lastProcessedSequence: number = 0;

  // PROTOCOL #47: Auto-rejoin session rooms on reconnection
  private currentSessionId: string | null = null;
  private pendingEvents: any[] = [];
  private isReconnecting: boolean = false;

  constructor(options: WebSocketServiceOptions = {}) {
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

    this.configReady = isConfigInitialized();

    // Initialize URL asynchronously
    this.initializeUrl().then(() => {
      if (this.options.autoConnect) {
        this.connect();
      }
    });

    // Setup cleanup on page unload
    window.addEventListener('beforeunload', () => {
      this.disconnect();
    });
  }

  private async initializeUrl(): Promise<void> {
    try {
      // Wait for configuration to be ready
      if (!this.configReady) {
        console.log('⏳ WebSocketService waiting for runtime configuration...');
        await waitForConfig();
        this.configReady = true;
      }

      // Dynamic WebSocket URL detection with runtime override support
      const getWebSocketUrl = () => {
        if (this.options.url) {
          return this.options.url;
        }
        
        // Use runtime-aware config getter - prioritize Socket.IO URL
        const configUrl = getConfigValueSync('REACT_APP_SOCKETIO_URL', '') ||
                          getConfigValueSync('REACT_APP_WS_URL', '');
        if (configUrl) {
          console.log('🔧 Using configured WebSocket URL:', configUrl);
          return configUrl;
        }
        
        const hostname = window.location.hostname;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        
        // Development environment (localhost) - Updated to use external IP
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
          return 'http://localhost:8000'; // Backend API port
        }
        
        // Handle production server - configurable via environment
        if (hostname === 'localhost' || hostname.includes('production-domain')) {
          const isSecure = window.location.protocol === 'https:';
          const httpProtocol = isSecure ? 'https:' : 'http:';
          return `${httpProtocol}//${hostname}:8001`; // Socket.IO port
        }
        
        // Generic fallback for other environments
        const httpProtocol = protocol === 'wss:' ? 'https:' : 'http:';
        return `${httpProtocol}//${hostname}:8001`;
      };

      this.url = getWebSocketUrl()!;
      this.urlResolved = true;
      
      console.log('🔧 WebSocketService URL resolved to:', this.url);
      
      // Process any queued connection attempts
      this.connectionQueue.forEach(callback => callback());
      this.connectionQueue = [];
      
    } catch (error) {
      console.error('❌ Failed to initialize WebSocket URL:', error);
      // Use fallback URL
      this.url = 'http://localhost:8001';
      this.urlResolved = true;
      console.log('🔧 Using fallback WebSocket URL:', this.url);
      
      // Process queued connections with fallback
      this.connectionQueue.forEach(callback => callback());
      this.connectionQueue = [];
    }
  }

  // Join a test session room for event isolation
  joinSession(sessionId: string): Promise<boolean> {
    return new Promise((resolve, reject) => {
      if (!this.socket || this.connectionState !== 'connected') {
        reject(new Error('WebSocket not connected - cannot join session room'));
        return;
      }

      if (!sessionId) {
        reject(new Error('session_id required to join session room'));
        return;
      }

      console.log(`📥 Joining session room: ${sessionId}`);

      // Emit join_session event
      this.socket.emit('join_session', { session_id: sessionId });

      // Wait for confirmation with timeout
      const timeout = setTimeout(() => {
        reject(new Error('Session join timeout'));
      }, 5000);

      this.socket.once('session_joined', (data: any) => {
        clearTimeout(timeout);
        console.log(`✅ Joined session room: ${data.room || sessionId}`);
        this.currentSessionId = sessionId;
        resolve(true);
      });
    });
  }

  // Leave a test session room
  leaveSession(sessionId: string): Promise<boolean> {
    return new Promise((resolve, reject) => {
      if (!this.socket) {
        // Already disconnected, consider it success
        resolve(true);
        return;
      }

      if (!sessionId) {
        reject(new Error('session_id required to leave session room'));
        return;
      }

      console.log(`📤 Leaving session room: ${sessionId}`);

      this.socket.emit('leave_session', { session_id: sessionId }, (response: any) => {
        if (response && response.success) {
          console.log(`✅ Successfully left session room: ${sessionId}`);
          resolve(true);
        } else {
          const error = response?.error || 'Unknown error leaving session';
          console.error(`❌ Failed to leave session room: ${error}`);
          reject(new Error(error));
        }
      });
    });
  }

  connect(): Promise<boolean> {
    return new Promise((resolve, reject) => {
      // If URL not resolved yet, queue the connection
      if (!this.urlResolved) {
        console.log('⏳ WebSocket URL not resolved yet, queueing connection...');
        this.connectionQueue.push(() => {
          this.connect().then(resolve).catch(reject);
        });
        return;
      }

      if (this.socket && this.connectionState === 'connected') {
        console.log('🔌 WebSocket already connected');
        resolve(true);
        return;
      }

      if (!this.url) {
        reject(new Error('WebSocket URL not configured'));
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
          randomizationFactor: 0.5,
          autoConnect: true,
          upgrade: true,
          rememberUpgrade: true,
          // pingTimeout: 60000, // Removed - not available in socket.io v4
          // pingInterval: 25000, // Removed - not available in socket.io v4
          // Enhanced for HIL testing reliability
          forceNew: false,
          withCredentials: false
        });

        // Connection success
        this.socket.on('connect', () => {
          console.log('✅ Socket.IO connected to', this.url);
          this.connectionState = 'connected';
          this.metrics.lastConnected = new Date();
          this.metrics.isStable = true;
          this.lastError = null;

          // Note: No longer subscribing to general updates - clients join session rooms instead

          this.startHeartbeat();
          this.notifySubscribers('connection', { status: 'connected', metrics: this.metrics });
          resolve(true);
        });

        // Connection error
        this.socket.on('connect_error', (error) => {
          logWebSocketError('Socket.IO connection failed', error, { function: 'connect_error', url: this.url });
          this.connectionState = 'error';
          this.lastError = error;
          this.metrics.isStable = false;
          
          this.notifySubscribers('connection', { status: 'error', error: error.message });
          
          // Only reject on first connection attempt, let reconnection handle retries
          if (this.metrics.connectionAttempts === 1) {
            reject(error);
          }
        });

        // Disconnection
        this.socket.on('disconnect', (reason) => {
          safeConsoleWarn('Socket.IO disconnected', reason, { function: 'disconnect', component: 'websocket-service', url: this.url });
          this.connectionState = 'disconnected';
          this.metrics.lastDisconnected = new Date();
          this.metrics.isStable = false;
          
          this.stopHeartbeat();
          this.notifySubscribers('connection', { status: 'disconnected', reason });

          // Enhanced reconnection logic for HIL testing
          const shouldReconnect = [
            'io server disconnect',
            'transport close',
            'transport error',
            'ping timeout'
          ].includes(reason);
          
          if (shouldReconnect && this.options.reconnection) {
            this.scheduleReconnection();
          }
        });

        // Handle Socket.IO specific reconnection events
        this.socket.on('reconnecting', (attempt) => {
          console.log(`🔄 Socket.IO reconnection attempt ${attempt}/${this.options.reconnectionAttempts} to ${this.url}`);
          this.metrics.reconnectCount++;
          this.notifySubscribers('connection', { status: 'reconnecting', attempt });
        });

        // PROTOCOL #47: Track reconnection attempts
        this.socket.on('reconnect_attempt', (attemptNumber) => {
          console.log(`🔄 Reconnection attempt ${attemptNumber}/10`);
        });

        // Successful reconnection
        this.socket.on('reconnect', async (attempt) => {
          console.log(`✅ Socket.IO reconnected to ${this.url} after ${attempt} attempts`);
          this.connectionState = 'connected';
          this.metrics.lastConnected = new Date();
          this.metrics.isStable = true;
          this.isReconnecting = true;

          // PROTOCOL #47: Auto-rejoin session room if we were in one
          if (this.currentSessionId) {
            console.log('🔄 WebSocket reconnected - auto-rejoining session room');
            try {
              await this.joinSession(this.currentSessionId);
              console.log('✅ Auto-rejoin successful');

              // Process buffered events
              this.flushPendingEvents();
            } catch (error) {
              console.error('❌ Auto-rejoin failed:', error);
            } finally {
              this.isReconnecting = false;
            }
          } else {
            this.isReconnecting = false;
          }

          this.startHeartbeat();
          this.notifySubscribers('connection', { status: 'reconnected', attempts: attempt, needsRejoin: !this.currentSessionId });
        });

        // Failed to reconnect
        this.socket.on('reconnect_failed', () => {
          logWebSocketError('Socket.IO failed to reconnect after all attempts', 'Maximum reconnection attempts exceeded', { function: 'reconnect_failed', url: this.url });
          this.connectionState = 'error';
          this.metrics.isStable = false;
          this.isReconnecting = false;

          console.error('❌ Reconnection failed after 10 attempts');
          this.notifySubscribers('connection', { status: 'reconnect_failed' });
        });
        
        // Handle server heartbeat for HIL testing
        this.socket.on('heartbeat_ping', (data) => {
          console.log('💓 Received heartbeat ping from server');
          this.socket?.emit('heartbeat_pong', { timestamp: Date.now(), ...data });
        });
        
        // Handle pong responses
        this.socket.on('pong', (data) => {
          console.log('🏓 Received pong from server', data);
        });
        
        // Handle subscription confirmations
        this.socket.on('subscription_confirmed', (data) => {
          console.log('✅ Subscription confirmed:', data);
        });

        // Handle subscription errors
        this.socket.on('subscription_error', (data) => {
          console.error('❌ Subscription error:', data);
        });

        // Handle detection events for real-time updates
        this.socket.on('detection_event', (data) => {
          console.log('🎯 Detection event received:', data);
          this.notifySubscribers('detection_event', data);
        });

        // Handle all incoming messages
        this.socket.onAny((eventName: string, data: unknown) => {
          if (!eventName.startsWith('connect')) {
            this.metrics.totalMessages++;
            console.log(`📨 WebSocket message [${eventName}] from ${this.url}:`, data);
            
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
        logWebSocketError('Setup failed', error, { function: 'connect', url: this.url });
        this.connectionState = 'error';
        this.lastError = error as Error;
        reject(error);
      }
    });
  }

  disconnect(sessionId?: string): void {
    console.log('🔌 Disconnecting WebSocket from', this.url, '...');

    // Leave session room if sessionId provided
    if (sessionId && this.socket) {
      this.leaveSession(sessionId).catch(error => {
        console.error('Error leaving session room during disconnect:', error);
      });
    }

    // PROTOCOL #47: Clear session tracking
    this.currentSessionId = null;
    this.pendingEvents = [];
    this.isReconnecting = false;

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
    console.log(`🔄 Scheduling reconnection to ${this.url} in ${delay}ms`);

    this.reconnectTimer = setTimeout(() => {
      if (this.connectionState !== 'connected') {
        this.connect().catch(error => {
          logWebSocketError('Scheduled reconnection failed', error, { function: 'scheduleReconnection', url: this.url });
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
        console.log('💓 Socket.IO heartbeat ping to', this.url);
        this.socket.emit('ping', { timestamp: Date.now(), client_id: this.socket.id });
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
          logWebSocketError(`Subscriber callback failed for ${eventType}`, error, { function: 'notifySubscribers', eventType, url: this.url });
        }
      });
    }
  }

  // Public subscription methods for Socket.IO events
  subscribe<T = unknown>(eventType: string, callback: (data: T) => void): () => void {
    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, new Set());
    }

    // PROTOCOL #47: Wrap callback to buffer events during reconnection
    const wrappedCallback = (data: T) => {
      if (this.isReconnecting) {
        // Buffer events during reconnection
        this.pendingEvents.push({ event: eventType, data });
        console.log(`📦 Buffered event during reconnection: ${eventType}`);
      } else {
        // Process event normally
        callback(data);
      }
    };

    this.subscribers.get(eventType)!.add(wrappedCallback as (data: unknown) => void);

    console.log(`🔔 Subscribed to Socket.IO event: ${eventType} on ${this.url}`);

    // Also subscribe on the socket if connected
    if (this.socket && this.connectionState === 'connected') {
      this.socket.on(eventType, wrappedCallback as (data: unknown) => void);
    }

    // Return unsubscribe function
    return () => {
      const subscribers = this.subscribers.get(eventType);
      if (subscribers) {
        subscribers.delete(wrappedCallback as (data: unknown) => void);
        if (subscribers.size === 0) {
          this.subscribers.delete(eventType);
        }
      }

      // Remove from socket too
      if (this.socket) {
        this.socket.off(eventType, wrappedCallback as (data: unknown) => void);
      }

      console.log(`🔕 Unsubscribed from Socket.IO event: ${eventType} on ${this.url}`);
    };
  }

  // Send message to server
  emit<T = unknown>(eventType: string, data?: T): boolean {
    if (this.connectionState !== 'connected' || !this.socket) {
      safeConsoleWarn(`Cannot emit ${eventType}: Socket.IO not connected`, { connectionState: this.connectionState, hasSocket: !!this.socket, url: this.url }, { function: 'emit', eventType });
      return false;
    }

    // Validate data before sending
    if (data !== undefined && !isValidWebSocketData(data)) {
      console.warn(`⚠️ Invalid data for Socket.IO emit [${eventType}] to ${this.url}:`, data);
      return false;
    }

    try {
      console.log(`📤 Socket.IO emit [${eventType}] to ${this.url}:`, data);
      this.socket.emit(eventType, data);
      return true;
    } catch (error) {
      logWebSocketError(`Socket.IO emit failed for ${eventType}`, error, { function: 'emit', eventType, url: this.url });
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
        reject(new Error(`WebSocket connection timeout to ${this.url}`));
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
          reject(new Error(`WebSocket connection failed to ${this.url}: ${errorMessage}`));
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
      urlResolved: this.urlResolved,
      configReady: this.configReady,
      metrics: this.metrics,
      lastError: this.lastError?.message,
      subscriberCount: Array.from(this.subscribers.values()).reduce((total, set) => total + set.size, 0),
      queuedConnections: this.connectionQueue.length
    };
  }

  /**
   * PROTOCOL #39: Subscribe to lifecycle events with sequence number ordering
   * Ensures events are processed in the correct order even if they arrive out of order
   */
  subscribeToLifecycleEvents(callback: (event: any) => void): () => void {
    console.log('🔔 Subscribing to video_lifecycle events with sequence ordering');

    return this.subscribe('video_lifecycle', (event: any) => {
      const seq = event.sequence_number;

      if (typeof seq !== 'number') {
        console.warn('⚠️ Lifecycle event missing sequence_number, processing immediately:', event);
        callback(event);
        return;
      }

      // Buffer event
      this.eventBuffer.set(seq, event);
      console.log(`📥 Buffered lifecycle event: ${event.event} (seq: ${seq})`);

      // Process in order
      this.processBufferedEvents(callback);
    });
  }

  /**
   * PROTOCOL #39: Process buffered events in sequence order
   * Maintains a buffer of up to 100 events and processes them in order
   */
  private processBufferedEvents(callback: (event: any) => void): void {
    // Process events in sequence order
    let nextSeq = this.lastProcessedSequence + 1;

    while (this.eventBuffer.has(nextSeq)) {
      const event = this.eventBuffer.get(nextSeq)!;
      this.eventBuffer.delete(nextSeq);

      console.log(`✅ Processing lifecycle event in order: ${event.event} (seq: ${nextSeq})`);
      callback(event);

      this.lastProcessedSequence = nextSeq;
      nextSeq++;
    }

    // Cleanup old buffered events (keep last 100)
    if (this.eventBuffer.size > 100) {
      const oldestAllowed = this.lastProcessedSequence - 50;
      for (const [seq] of this.eventBuffer) {
        if (seq < oldestAllowed) {
          console.log(`🧹 Cleaning up old buffered event (seq: ${seq})`);
          this.eventBuffer.delete(seq);
        }
      }
    }
  }

  /**
   * PROTOCOL #47: Flush pending events after reconnection
   * Process all buffered events that were received during reconnection
   */
  private flushPendingEvents(): void {
    if (this.pendingEvents.length === 0) {
      return;
    }

    console.log(`📤 Flushing ${this.pendingEvents.length} buffered events`);

    // Group by event type
    const eventGroups = new Map<string, any[]>();

    for (const { event, data } of this.pendingEvents) {
      if (!eventGroups.has(event)) {
        eventGroups.set(event, []);
      }
      eventGroups.get(event)!.push(data);
    }

    // Process buffered events through subscribers
    for (const [event, dataArray] of eventGroups) {
      for (const data of dataArray) {
        this.notifySubscribers(event, data);
      }
      console.log(`📤 Flushed ${dataArray.length} ${event} events`);
    }

    // Clear buffer
    this.pendingEvents = [];
  }

  // Sequence subscription support for multi-video testing
  // FIX #5: WebSocket Subscriptions - Subscribe to correct events (video_started, video_ended)
  subscribeToSequence(sequenceId: string) {
    if (!sequenceId) {
      console.error('❌ Cannot subscribe to sequence: sequenceId is required');
      return null;
    }

    console.log(`🎬 Subscribing to sequence: ${sequenceId}`);

    // Emit subscription request to backend
    this.emit('subscribe_sequence', { sequence_id: sequenceId });

    // Return subscription handlers
    return {
      // PROTOCOL #39: Use lifecycle events with sequence numbers
      onVideoStarted: (callback: (data: unknown) => void) => {
        console.log(`📹 Setting up video started handler for sequence ${sequenceId}`);
        return this.subscribeToLifecycleEvents((event: any) => {
          if (event.event === 'video_started') {
            callback(event);
          }
        });
      },
      // PROTOCOL #39: Use lifecycle events with sequence numbers
      onVideoEnded: (callback: (data: unknown) => void) => {
        console.log(`🎬 Setting up video ended handler for sequence ${sequenceId}`);
        return this.subscribeToLifecycleEvents((event: any) => {
          if (event.event === 'video_ended') {
            callback(event);
          }
        });
      },
      onVideoCompleted: (callback: (data: unknown) => void) => {
        console.log(`✅ Setting up video completed handler for sequence ${sequenceId}`);
        return this.subscribe('video_completed', callback);
      },
      onSequenceCompleted: (callback: (data: unknown) => void) => {
        console.log(`🏁 Setting up sequence completed handler for sequence ${sequenceId}`);
        return this.subscribe('sequence_completed', callback);
      },
      unsubscribe: () => {
        console.log(`🔕 Unsubscribing from sequence: ${sequenceId}`);
        this.emit('unsubscribe_sequence', { sequence_id: sequenceId });
      }
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