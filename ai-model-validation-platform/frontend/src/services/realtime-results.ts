import { RealTimeUpdate, StreamingConnection, EnhancedTestExecution } from '../types/enhanced-results';

export class RealTimeResultsService {
  private ws: WebSocket | null = null;
  private subscribers: Map<string, Set<(update: RealTimeUpdate) => void>> = new Map();
  private connectionStateSubscribers: Set<(connection: StreamingConnection) => void> = new Set();
  private currentConnection: StreamingConnection | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private connectionTimeout: NodeJS.Timeout | null = null;

  constructor() {
    this.setupConnectionMonitoring();
  }

  /**
   * Subscribe to real-time updates for a specific session
   */
  subscribe(sessionId: string, callback: (update: RealTimeUpdate) => void): () => void {
    if (!this.subscribers.has(sessionId)) {
      this.subscribers.set(sessionId, new Set());
    }
    
    this.subscribers.get(sessionId)!.add(callback);

    // Auto-connect if not connected
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connect();
    }

    // Return unsubscribe function
    return () => {
      const sessionSubscribers = this.subscribers.get(sessionId);
      if (sessionSubscribers) {
        sessionSubscribers.delete(callback);
        if (sessionSubscribers.size === 0) {
          this.subscribers.delete(sessionId);
        }
      }

      // Disconnect if no more subscribers
      if (this.subscribers.size === 0) {
        this.disconnect();
      }
    };
  }

  /**
   * Subscribe to connection state changes
   */
  subscribeToConnectionState(callback: (connection: StreamingConnection) => void): () => void {
    this.connectionStateSubscribers.add(callback);
    
    // Send current connection state immediately
    if (this.currentConnection) {
      callback(this.currentConnection);
    }

    return () => {
      this.connectionStateSubscribers.delete(callback);
    };
  }

  /**
   * Connect to the WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.updateConnectionState({
        sessionId: 'system',
        isConnected: false,
        lastUpdate: new Date().toISOString(),
        connectionStatus: 'connecting',
        messageCount: 0,
        errorCount: 0,
        latency: 0
      });

      const wsUrl = this.getWebSocketUrl();
      this.ws = new WebSocket(wsUrl);

      // Connection timeout
      this.connectionTimeout = setTimeout(() => {
        if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
          this.ws.close();
          reject(new Error('Connection timeout'));
        }
      }, 10000);

      this.ws.onopen = () => {
        if (this.connectionTimeout) {
          clearTimeout(this.connectionTimeout);
        }

        this.reconnectAttempts = 0;
        this.updateConnectionState({
          sessionId: 'system',
          isConnected: true,
          lastUpdate: new Date().toISOString(),
          connectionStatus: 'connected',
          messageCount: 0,
          errorCount: 0,
          latency: 0
        });

        this.startHeartbeat();
        resolve();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.updateConnectionState({
          ...this.currentConnection!,
          connectionStatus: 'error',
          errorCount: this.currentConnection?.errorCount ? this.currentConnection.errorCount + 1 : 1
        });
        reject(error);
      };

      this.ws.onclose = (event) => {
        if (this.connectionTimeout) {
          clearTimeout(this.connectionTimeout);
        }

        this.stopHeartbeat();
        this.updateConnectionState({
          ...this.currentConnection!,
          isConnected: false,
          connectionStatus: 'disconnected'
        });

        // Auto-reconnect if there are subscribers
        if (this.subscribers.size > 0 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };
    });
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    this.stopHeartbeat();
    
    if (this.connectionTimeout) {
      clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.updateConnectionState({
      sessionId: 'system',
      isConnected: false,
      lastUpdate: new Date().toISOString(),
      connectionStatus: 'disconnected',
      messageCount: this.currentConnection?.messageCount || 0,
      errorCount: this.currentConnection?.errorCount || 0,
      latency: 0
    });
  }

  /**
   * Get current connection status
   */
  getConnectionStatus(): StreamingConnection | null {
    return this.currentConnection;
  }

  /**
   * Request historical updates for a session
   */
  async requestSessionHistory(sessionId: string, fromTimestamp?: string): Promise<RealTimeUpdate[]> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }

    return new Promise((resolve, reject) => {
      const requestId = this.generateRequestId();
      const timeout = setTimeout(() => {
        reject(new Error('Request timeout'));
      }, 10000);

      const handleResponse = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data.requestId === requestId && data.type === 'session_history_response') {
            clearTimeout(timeout);
            this.ws?.removeEventListener('message', handleResponse);
            resolve(data.updates || []);
          }
        } catch (error) {
          // Ignore parsing errors for other messages
        }
      };

      this.ws.addEventListener('message', handleResponse);
      
      this.ws.send(JSON.stringify({
        type: 'request_session_history',
        requestId,
        sessionId,
        fromTimestamp
      }));
    });
  }

  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = process.env.REACT_APP_WS_HOST || window.location.hostname;
    const port = process.env.REACT_APP_WS_PORT || '8001';
    return `${protocol}//${host}:${port}/ws/results`;
  }

  private handleMessage(event: MessageEvent): void {
    const startTime = performance.now();
    
    try {
      const update: RealTimeUpdate = JSON.parse(event.data);
      const latency = performance.now() - startTime;

      // Update connection metrics
      this.updateConnectionState({
        ...this.currentConnection!,
        lastUpdate: new Date().toISOString(),
        messageCount: this.currentConnection!.messageCount + 1,
        latency
      });

      // Route message to appropriate subscribers
      const sessionSubscribers = this.subscribers.get(update.sessionId);
      if (sessionSubscribers) {
        sessionSubscribers.forEach(callback => {
          try {
            callback(update);
          } catch (error) {
            console.error('Error in subscriber callback:', error);
          }
        });
      }

      // Also route to system-wide subscribers if it's a system message
      if (update.sessionId === 'system') {
        this.subscribers.forEach(sessionSubscribers => {
          sessionSubscribers.forEach(callback => {
            try {
              callback(update);
            } catch (error) {
              console.error('Error in system subscriber callback:', error);
            }
          });
        });
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
      this.updateConnectionState({
        ...this.currentConnection!,
        errorCount: this.currentConnection!.errorCount + 1
      });
    }
  }

  private updateConnectionState(newState: StreamingConnection): void {
    this.currentConnection = newState;
    this.connectionStateSubscribers.forEach(callback => {
      try {
        callback(newState);
      } catch (error) {
        console.error('Error in connection state callback:', error);
      }
    });
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff

    this.updateConnectionState({
      ...this.currentConnection!,
      connectionStatus: 'reconnecting'
    });

    setTimeout(() => {
      this.connect().catch(error => {
        console.error('Reconnection failed:', error);
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        } else {
          this.updateConnectionState({
            ...this.currentConnection!,
            connectionStatus: 'error'
          });
        }
      });
    }, delay);
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        const startTime = performance.now();
        this.ws.send(JSON.stringify({
          type: 'ping',
          timestamp: Date.now()
        }));

        // Measure response time when pong is received
        const handlePong = (event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'pong') {
              const latency = performance.now() - startTime;
              this.updateConnectionState({
                ...this.currentConnection!,
                latency
              });
              this.ws?.removeEventListener('message', handlePong);
            }
          } catch (error) {
            // Ignore parsing errors
          }
        };

        this.ws.addEventListener('message', handlePong);
      }
    }, 30000); // Heartbeat every 30 seconds
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private setupConnectionMonitoring(): void {
    // Monitor network connectivity
    window.addEventListener('online', () => {
      if (this.subscribers.size > 0 && (!this.ws || this.ws.readyState !== WebSocket.OPEN)) {
        this.connect().catch(error => {
          console.error('Failed to reconnect after coming online:', error);
        });
      }
    });

    window.addEventListener('offline', () => {
      this.updateConnectionState({
        ...this.currentConnection!,
        connectionStatus: 'disconnected'
      });
    });

    // Monitor page visibility
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        // Reconnect if needed when page becomes visible
        if (this.subscribers.size > 0 && (!this.ws || this.ws.readyState !== WebSocket.OPEN)) {
          this.connect().catch(error => {
            console.error('Failed to reconnect on page visibility:', error);
          });
        }
      }
    });
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Send a command to the server (e.g., to start/stop test execution)
   */
  sendCommand(command: string, data: Record<string, unknown>): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      const requestId = this.generateRequestId();
      const timeout = setTimeout(() => {
        reject(new Error('Command timeout'));
      }, 30000);

      const handleResponse = (event: MessageEvent) => {
        try {
          const response = JSON.parse(event.data);
          if (response.requestId === requestId) {
            clearTimeout(timeout);
            this.ws?.removeEventListener('message', handleResponse);
            
            if (response.error) {
              reject(new Error(response.error));
            } else {
              resolve();
            }
          }
        } catch (error) {
          // Ignore parsing errors for other messages
        }
      };

      this.ws.addEventListener('message', handleResponse);
      
      this.ws.send(JSON.stringify({
        type: 'command',
        command,
        data,
        requestId,
        timestamp: Date.now()
      }));
    });
  }

  /**
   * Clean up all resources
   */
  destroy(): void {
    this.disconnect();
    this.subscribers.clear();
    this.connectionStateSubscribers.clear();
    
    // Remove event listeners
    window.removeEventListener('online', this.connect);
    window.removeEventListener('offline', this.disconnect);
    document.removeEventListener('visibilitychange', () => {});
  }
}

// Singleton instance
export const realTimeResultsService = new RealTimeResultsService();
export default realTimeResultsService;