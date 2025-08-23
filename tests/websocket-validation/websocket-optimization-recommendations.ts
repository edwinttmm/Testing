/**
 * WebSocket Optimization Recommendations
 * Agent 3: WebSocket Connection Validation Agent
 * 
 * Concrete implementation suggestions for identified issues
 */

import { io, Socket } from 'socket.io-client';

// =============================================================================
// CRITICAL FIX 1: Detection WebSocket Re-enablement
// =============================================================================

/**
 * Enhanced Detection WebSocket Hook
 * Replaces the disabled useDetectionWebSocket with full functionality
 */
export interface DetectionWebSocketOptions {
  videoId: string;
  enableProgressUpdates?: boolean;
  enableRealTimeResults?: boolean;
  reconnectOnFailure?: boolean;
  maxReconnectAttempts?: number;
}

export interface DetectionResult {
  detectionId: string;
  videoId: string;
  frameNumber: number;
  confidence: number;
  label: string;
  bbox: { x: number; y: number; width: number; height: number };
  timestamp: string;
}

export interface DetectionProgress {
  videoId: string;
  progress: number; // 0-100
  stage: 'initializing' | 'processing' | 'analyzing' | 'complete' | 'error';
  estimatedTimeRemaining?: number;
  currentFrame?: number;
  totalFrames?: number;
}

export const useEnhancedDetectionWebSocket = (options: DetectionWebSocketOptions) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<DetectionProgress | null>(null);
  const [results, setResults] = useState<DetectionResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(async () => {
    try {
      const newSocket = io('/detection', {
        transports: ['websocket'],
        auth: { videoId: options.videoId },
        timeout: 10000,
        reconnection: options.reconnectOnFailure ?? true,
        reconnectionAttempts: options.maxReconnectAttempts ?? 5
      });

      newSocket.on('connect', () => {
        setIsConnected(true);
        setError(null);
      });

      newSocket.on('disconnect', () => {
        setIsConnected(false);
      });

      newSocket.on('detection_progress', (progressData: DetectionProgress) => {
        if (options.enableProgressUpdates) {
          setProgress(progressData);
        }
      });

      newSocket.on('detection_result', (result: DetectionResult) => {
        if (options.enableRealTimeResults) {
          setResults(prev => [...prev, result]);
        }
      });

      newSocket.on('detection_error', (errorData: { message: string; code?: string }) => {
        setError(errorData.message);
        setProgress(prev => prev ? { ...prev, stage: 'error' } : null);
      });

      newSocket.on('detection_complete', (finalResults: DetectionResult[]) => {
        setResults(finalResults);
        setProgress(prev => prev ? { ...prev, stage: 'complete', progress: 100 } : null);
      });

      setSocket(newSocket);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    }
  }, [options]);

  const startDetection = useCallback((config: {
    confidenceThreshold: number;
    modelName: string;
    targetClasses: string[];
  }) => {
    if (socket && isConnected) {
      socket.emit('start_detection', {
        videoId: options.videoId,
        config
      });
    }
  }, [socket, isConnected, options.videoId]);

  const stopDetection = useCallback(() => {
    if (socket && isConnected) {
      socket.emit('stop_detection', { videoId: options.videoId });
    }
  }, [socket, isConnected, options.videoId]);

  const disconnect = useCallback(() => {
    if (socket) {
      socket.disconnect();
      setSocket(null);
      setIsConnected(false);
    }
  }, [socket]);

  return {
    connect,
    disconnect,
    startDetection,
    stopDetection,
    isConnected,
    progress,
    results,
    error,
    clearResults: () => setResults([])
  };
};

// =============================================================================
// OPTIMIZATION 2: Enhanced WebSocket Service with Advanced Features
// =============================================================================

interface AdvancedWebSocketOptions {
  url: string;
  authentication?: {
    token: string;
    refreshToken?: string;
    onTokenExpired?: () => Promise<string>;
  };
  rateLimiting?: {
    maxRequestsPerSecond: number;
    burstAllowance: number;
  };
  messageQueuing?: {
    enabled: boolean;
    maxQueueSize: number;
    persistQueue: boolean;
  };
  compression?: {
    enabled: boolean;
    threshold: number; // Compress messages larger than this (bytes)
  };
  monitoring?: {
    enabled: boolean;
    metricsEndpoint?: string;
    reportingInterval: number;
  };
}

class AdvancedWebSocketService {
  private socket: Socket | null = null;
  private options: AdvancedWebSocketOptions;
  private messageQueue: Array<{ event: string; data: unknown }> = [];
  private rateLimiter: Map<string, number[]> = new Map();
  private metrics: {
    messagesSent: number;
    messagesReceived: number;
    connectionUptime: number;
    averageLatency: number;
    errorCount: number;
  } = {
    messagesSent: 0,
    messagesReceived: 0,
    connectionUptime: 0,
    averageLatency: 0,
    errorCount: 0
  };

  constructor(options: AdvancedWebSocketOptions) {
    this.options = options;
  }

  async connect(): Promise<boolean> {
    try {
      const socketOptions: any = {
        transports: ['websocket', 'polling'],
        timeout: 20000,
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000
      };

      // Add authentication if provided
      if (this.options.authentication) {
        socketOptions.auth = {
          token: this.options.authentication.token
        };
      }

      // Enable compression if configured
      if (this.options.compression?.enabled) {
        socketOptions.compression = true;
      }

      this.socket = io(this.options.url, socketOptions);

      return new Promise((resolve, reject) => {
        this.socket!.on('connect', () => {
          this.setupEventHandlers();
          this.processQueuedMessages();
          resolve(true);
        });

        this.socket!.on('connect_error', (error) => {
          this.metrics.errorCount++;
          reject(error);
        });

        this.socket!.on('auth_error', async (error) => {
          if (this.options.authentication?.onTokenExpired) {
            try {
              const newToken = await this.options.authentication.onTokenExpired();
              this.socket!.auth = { token: newToken };
              this.socket!.connect();
            } catch (refreshError) {
              reject(refreshError);
            }
          } else {
            reject(new Error('Authentication failed: ' + error.message));
          }
        });
      });
    } catch (error) {
      this.metrics.errorCount++;
      throw error;
    }
  }

  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('disconnect', () => {
      if (this.options.monitoring?.enabled) {
        this.reportMetrics();
      }
    });

    this.socket.onAny((eventName: string, data: unknown) => {
      this.metrics.messagesReceived++;
      
      // Handle compressed messages
      if (this.options.compression?.enabled && this.isCompressedMessage(data)) {
        data = this.decompressMessage(data);
      }

      this.handleIncomingMessage(eventName, data);
    });
  }

  emit<T>(eventName: string, data: T): boolean {
    if (!this.socket?.connected) {
      if (this.options.messageQueuing?.enabled) {
        this.queueMessage(eventName, data);
        return false;
      }
      return false;
    }

    // Apply rate limiting
    if (this.options.rateLimiting && !this.checkRateLimit(eventName)) {
      console.warn(`Rate limit exceeded for event: ${eventName}`);
      return false;
    }

    try {
      let messageData = data;

      // Apply compression if configured and message is large enough
      if (this.options.compression?.enabled) {
        const messageSize = JSON.stringify(data).length;
        if (messageSize > this.options.compression.threshold) {
          messageData = this.compressMessage(data) as T;
        }
      }

      this.socket.emit(eventName, messageData);
      this.metrics.messagesSent++;
      return true;
    } catch (error) {
      this.metrics.errorCount++;
      console.error('Failed to emit message:', error);
      return false;
    }
  }

  private queueMessage(eventName: string, data: unknown): void {
    if (!this.options.messageQueuing?.enabled) return;

    const maxSize = this.options.messageQueuing.maxQueueSize || 1000;
    
    if (this.messageQueue.length >= maxSize) {
      this.messageQueue.shift(); // Remove oldest message
    }

    this.messageQueue.push({ event: eventName, data });

    // Persist queue if configured
    if (this.options.messageQueuing.persistQueue) {
      this.persistMessageQueue();
    }
  }

  private processQueuedMessages(): void {
    while (this.messageQueue.length > 0 && this.socket?.connected) {
      const { event, data } = this.messageQueue.shift()!;
      this.emit(event, data);
    }
  }

  private checkRateLimit(eventName: string): boolean {
    if (!this.options.rateLimiting) return true;

    const now = Date.now();
    const windowMs = 1000; // 1 second window
    const maxRequests = this.options.rateLimiting.maxRequestsPerSecond;

    let requests = this.rateLimiter.get(eventName) || [];
    
    // Remove old requests outside the time window
    requests = requests.filter(timestamp => now - timestamp < windowMs);
    
    if (requests.length >= maxRequests) {
      return false;
    }

    requests.push(now);
    this.rateLimiter.set(eventName, requests);
    return true;
  }

  private handleIncomingMessage(eventName: string, data: unknown): void {
    // Emit to subscribers (implementation depends on existing subscriber pattern)
    console.log(`Received ${eventName}:`, data);
  }

  private compressMessage(data: unknown): unknown {
    // Implement compression logic (e.g., using pako or similar library)
    return data; // Placeholder
  }

  private decompressMessage(data: unknown): unknown {
    // Implement decompression logic
    return data; // Placeholder
  }

  private isCompressedMessage(data: unknown): boolean {
    // Check if message is compressed
    return false; // Placeholder
  }

  private persistMessageQueue(): void {
    try {
      localStorage.setItem('websocket_queue', JSON.stringify(this.messageQueue));
    } catch (error) {
      console.warn('Failed to persist message queue:', error);
    }
  }

  private reportMetrics(): void {
    if (!this.options.monitoring?.enabled) return;

    const report = {
      timestamp: new Date().toISOString(),
      metrics: this.metrics,
      queueSize: this.messageQueue.length,
      rateLimiterState: Object.fromEntries(this.rateLimiter)
    };

    if (this.options.monitoring.metricsEndpoint) {
      fetch(this.options.monitoring.metricsEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report)
      }).catch(error => console.warn('Failed to report metrics:', error));
    }

    console.log('WebSocket Metrics:', report);
  }

  getMetrics() {
    return { ...this.metrics, queueSize: this.messageQueue.length };
  }
}

// =============================================================================
// OPTIMIZATION 3: WebSocket Security Enhancements
// =============================================================================

interface SecureWebSocketConfig {
  jwtToken: string;
  refreshEndpoint: string;
  allowedEvents: string[];
  rateLimits: Record<string, { requests: number; windowMs: number }>;
  encryptionKey?: string;
}

class SecureWebSocketService {
  private config: SecureWebSocketConfig;
  private socket: Socket | null = null;
  private tokenRefreshTimer: NodeJS.Timeout | null = null;

  constructor(config: SecureWebSocketConfig) {
    this.config = config;
  }

  async connect(): Promise<void> {
    const socket = io('/secure', {
      auth: { token: this.config.jwtToken },
      transports: ['websocket'],
      upgrade: true,
      rememberUpgrade: true
    });

    socket.on('connect', () => {
      this.setupTokenRefresh();
      this.setupEventValidation();
    });

    socket.on('auth_required', () => {
      this.refreshToken();
    });

    socket.on('rate_limit_exceeded', (data: { event: string; retryAfter: number }) => {
      console.warn(`Rate limit exceeded for ${data.event}. Retry after ${data.retryAfter}ms`);
    });

    socket.on('unauthorized_event', (data: { event: string }) => {
      console.error(`Unauthorized event attempted: ${data.event}`);
    });

    this.socket = socket;
  }

  private setupTokenRefresh(): void {
    // Refresh token every 50 minutes (assuming 60min expiry)
    this.tokenRefreshTimer = setInterval(async () => {
      await this.refreshToken();
    }, 50 * 60 * 1000);
  }

  private async refreshToken(): Promise<void> {
    try {
      const response = await fetch(this.config.refreshEndpoint, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.config.jwtToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const { token } = await response.json();
        this.config.jwtToken = token;
        
        if (this.socket) {
          this.socket.auth = { token };
          this.socket.emit('token_updated', { token });
        }
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
    }
  }

  private setupEventValidation(): void {
    if (!this.socket) return;

    const originalEmit = this.socket.emit.bind(this.socket);
    
    this.socket.emit = (eventName: string, ...args: any[]) => {
      // Validate event is allowed
      if (!this.config.allowedEvents.includes(eventName)) {
        console.warn(`Event ${eventName} not in allowed list`);
        return this.socket as Socket;
      }

      // Check rate limits
      const rateLimit = this.config.rateLimits[eventName];
      if (rateLimit && !this.checkEventRateLimit(eventName, rateLimit)) {
        console.warn(`Rate limit exceeded for event: ${eventName}`);
        return this.socket as Socket;
      }

      // Encrypt sensitive data if encryption key is provided
      if (this.config.encryptionKey && this.isSensitiveEvent(eventName)) {
        args = args.map(arg => this.encryptData(arg));
      }

      return originalEmit(eventName, ...args);
    };
  }

  private checkEventRateLimit(eventName: string, limit: { requests: number; windowMs: number }): boolean {
    // Implementation would track requests per event type
    return true; // Placeholder
  }

  private isSensitiveEvent(eventName: string): boolean {
    const sensitiveEvents = ['user_data', 'authentication', 'payment_info'];
    return sensitiveEvents.includes(eventName);
  }

  private encryptData(data: unknown): unknown {
    // Implement encryption logic
    return data; // Placeholder
  }

  disconnect(): void {
    if (this.tokenRefreshTimer) {
      clearInterval(this.tokenRefreshTimer);
    }
    
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }
}

// =============================================================================
// OPTIMIZATION 4: Performance Monitoring and Analytics
// =============================================================================

interface WebSocketAnalytics {
  connectionQuality: {
    averageLatency: number;
    packetLoss: number;
    jitter: number;
    uptime: number;
  };
  messageStats: {
    totalSent: number;
    totalReceived: number;
    averageMessageSize: number;
    messageThroughput: number;
  };
  errorStats: {
    connectionErrors: number;
    messageErrors: number;
    timeoutErrors: number;
    errorRate: number;
  };
}

class WebSocketAnalyticsService {
  private analytics: WebSocketAnalytics;
  private latencyHistory: number[] = [];
  private messageHistory: Array<{ timestamp: number; size: number; type: 'sent' | 'received' }> = [];
  private connectionStartTime: number = 0;

  constructor() {
    this.analytics = this.initializeAnalytics();
  }

  private initializeAnalytics(): WebSocketAnalytics {
    return {
      connectionQuality: {
        averageLatency: 0,
        packetLoss: 0,
        jitter: 0,
        uptime: 0
      },
      messageStats: {
        totalSent: 0,
        totalReceived: 0,
        averageMessageSize: 0,
        messageThroughput: 0
      },
      errorStats: {
        connectionErrors: 0,
        messageErrors: 0,
        timeoutErrors: 0,
        errorRate: 0
      }
    };
  }

  recordLatency(latency: number): void {
    this.latencyHistory.push(latency);
    
    // Keep only last 100 measurements
    if (this.latencyHistory.length > 100) {
      this.latencyHistory.shift();
    }

    this.analytics.connectionQuality.averageLatency = 
      this.latencyHistory.reduce((a, b) => a + b) / this.latencyHistory.length;

    // Calculate jitter (variance in latency)
    const avg = this.analytics.connectionQuality.averageLatency;
    const variance = this.latencyHistory
      .map(l => Math.pow(l - avg, 2))
      .reduce((a, b) => a + b) / this.latencyHistory.length;
    
    this.analytics.connectionQuality.jitter = Math.sqrt(variance);
  }

  recordMessage(size: number, type: 'sent' | 'received'): void {
    this.messageHistory.push({
      timestamp: Date.now(),
      size,
      type
    });

    // Keep only last 1000 messages
    if (this.messageHistory.length > 1000) {
      this.messageHistory.shift();
    }

    if (type === 'sent') {
      this.analytics.messageStats.totalSent++;
    } else {
      this.analytics.messageStats.totalReceived++;
    }

    // Calculate average message size
    const totalSize = this.messageHistory.reduce((sum, msg) => sum + msg.size, 0);
    this.analytics.messageStats.averageMessageSize = totalSize / this.messageHistory.length;

    // Calculate throughput (messages per second over last minute)
    const oneMinuteAgo = Date.now() - 60000;
    const recentMessages = this.messageHistory.filter(msg => msg.timestamp > oneMinuteAgo);
    this.analytics.messageStats.messageThroughput = recentMessages.length / 60;
  }

  recordError(errorType: 'connection' | 'message' | 'timeout'): void {
    switch (errorType) {
      case 'connection':
        this.analytics.errorStats.connectionErrors++;
        break;
      case 'message':
        this.analytics.errorStats.messageErrors++;
        break;
      case 'timeout':
        this.analytics.errorStats.timeoutErrors++;
        break;
    }

    const totalOperations = this.analytics.messageStats.totalSent + 
                           this.analytics.messageStats.totalReceived;
    const totalErrors = this.analytics.errorStats.connectionErrors +
                       this.analytics.errorStats.messageErrors +
                       this.analytics.errorStats.timeoutErrors;
    
    this.analytics.errorStats.errorRate = totalErrors / (totalOperations || 1);
  }

  startConnectionTimer(): void {
    this.connectionStartTime = Date.now();
  }

  updateUptime(): void {
    if (this.connectionStartTime > 0) {
      this.analytics.connectionQuality.uptime = Date.now() - this.connectionStartTime;
    }
  }

  getAnalytics(): WebSocketAnalytics {
    this.updateUptime();
    return { ...this.analytics };
  }

  generateReport(): string {
    const analytics = this.getAnalytics();
    
    return `
WebSocket Connection Report
==========================
Connection Quality:
  Average Latency: ${analytics.connectionQuality.averageLatency.toFixed(2)}ms
  Jitter: ${analytics.connectionQuality.jitter.toFixed(2)}ms
  Uptime: ${(analytics.connectionQuality.uptime / 1000 / 60).toFixed(2)} minutes

Message Statistics:
  Messages Sent: ${analytics.messageStats.totalSent}
  Messages Received: ${analytics.messageStats.totalReceived}
  Average Message Size: ${analytics.messageStats.averageMessageSize.toFixed(2)} bytes
  Throughput: ${analytics.messageStats.messageThroughput.toFixed(2)} msg/sec

Error Statistics:
  Connection Errors: ${analytics.errorStats.connectionErrors}
  Message Errors: ${analytics.errorStats.messageErrors}
  Timeout Errors: ${analytics.errorStats.timeoutErrors}
  Error Rate: ${(analytics.errorStats.errorRate * 100).toFixed(2)}%
    `.trim();
  }
}

// =============================================================================
// EXPORT OPTIMIZED IMPLEMENTATIONS
// =============================================================================

export {
  AdvancedWebSocketService,
  SecureWebSocketService,
  WebSocketAnalyticsService,
  useEnhancedDetectionWebSocket
};

export type {
  AdvancedWebSocketOptions,
  SecureWebSocketConfig,
  WebSocketAnalytics,
  DetectionWebSocketOptions,
  DetectionResult,
  DetectionProgress
};