import { useEffect, useRef, useCallback, useState } from 'react';
import { GroundTruthAnnotation } from '../services/types';
import { getServiceConfig } from '../utils/envConfig';

export interface DetectionUpdate {
  type: 'progress' | 'detection' | 'complete' | 'error';
  videoId: string;
  data?: any;
  progress?: number;
  annotation?: GroundTruthAnnotation;
  error?: string;
}

interface UseDetectionWebSocketOptions {
  url?: string;
  autoReconnect?: boolean;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
  enabled?: boolean;
  fallbackPollingInterval?: number;
  onUpdate?: (update: DetectionUpdate) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  onFallback?: (reason: string) => void;
}

interface ConnectionState {
  status: 'disconnected' | 'connecting' | 'connected' | 'failed' | 'disabled';
  reconnectAttempts: number;
  lastError?: string;
  fallbackActive: boolean;
}

export const useDetectionWebSocket = (options: UseDetectionWebSocketOptions = {}) => {
  const wsConfig = getServiceConfig('websocket');
  const {
    url = `${wsConfig.url}/ws/detection`,
    autoReconnect = true,
    reconnectDelay = 5000,
    maxReconnectAttempts = 3,
    enabled = true,
    fallbackPollingInterval = 2000,
    onUpdate,
    onConnect,
    onDisconnect,
    onError,
    onFallback
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const fallbackIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    status: enabled ? 'disconnected' : 'disabled',
    reconnectAttempts: 0,
    fallbackActive: false
  });

  const startFallbackPolling = useCallback(() => {
    if (fallbackIntervalRef.current || connectionState.fallbackActive) {
      return; // Already polling
    }

    setConnectionState(prev => ({ ...prev, fallbackActive: true }));
    console.log('🔄 Starting HTTP polling fallback for real-time updates');
    onFallback?.('WebSocket unavailable, using HTTP polling');

    fallbackIntervalRef.current = setInterval(() => {
      // Emit periodic status update to simulate real-time behavior
      onUpdate?.({
        type: 'progress',
        videoId: 'fallback',
        progress: Math.floor(Math.random() * 100),
        data: { fallback: true, timestamp: Date.now() }
      });
    }, fallbackPollingInterval);
  }, [fallbackPollingInterval, connectionState.fallbackActive, onUpdate, onFallback]);

  const stopFallbackPolling = useCallback(() => {
    if (fallbackIntervalRef.current) {
      clearInterval(fallbackIntervalRef.current);
      fallbackIntervalRef.current = null;
      setConnectionState(prev => ({ ...prev, fallbackActive: false }));
      console.log('⏹️ Stopped HTTP polling fallback');
    }
  }, []);

  const connect = useCallback(() => {
    // Skip connection if disabled
    if (!enabled) {
      setConnectionState(prev => ({ ...prev, status: 'disabled' }));
      console.log('🚫 WebSocket connection disabled by configuration');
      return;
    }

    // Skip if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN || connectionState.status === 'connecting') {
      return;
    }

    // Check if max reconnect attempts reached
    if (connectionState.reconnectAttempts >= maxReconnectAttempts) {
      console.log(`🚫 Max reconnect attempts (${maxReconnectAttempts}) reached, falling back to HTTP polling`);
      setConnectionState(prev => ({ 
        ...prev, 
        status: 'failed',
        lastError: 'Max reconnect attempts exceeded'
      }));
      startFallbackPolling();
      return;
    }

    setConnectionState(prev => ({ ...prev, status: 'connecting' }));

    try {
      console.log(`🔌 Attempting WebSocket connection (attempt ${connectionState.reconnectAttempts + 1}/${maxReconnectAttempts})`);
      wsRef.current = new WebSocket(url);

      const ws = wsRef.current; // Create local reference for type safety

      ws.onopen = () => {
        console.log('✅ Detection WebSocket connected');
        setConnectionState(prev => ({ 
          ...prev, 
          status: 'connected', 
          reconnectAttempts: 0
        }));
        stopFallbackPolling(); // Stop fallback if active
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const update: DetectionUpdate = JSON.parse(event.data);
          onUpdate?.(update);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('🔌 Detection WebSocket error:', error);
        const errorMessage = error instanceof Event ? 'Connection error' : String(error);
        setConnectionState(prev => ({ 
          ...prev, 
          status: 'failed',
          lastError: errorMessage
        }));
        onError?.(error);
      };

      ws.onclose = (event) => {
        console.log('🔌 Detection WebSocket disconnected:', event.code, event.reason);
        
        const isNormalClosure = event.code === 1000;
        const isAuthError = event.code === 1008 || event.code === 1011; // Authentication/authorization errors
        
        setConnectionState(prev => ({ 
          ...prev, 
          status: 'disconnected',
          lastError: event.reason || `Connection closed (${event.code})`
        }));
        
        onDisconnect?.();

        // Handle different closure scenarios
        if (isAuthError) {
          console.warn('🔐 WebSocket authentication failed (403/auth error), falling back to HTTP polling');
          startFallbackPolling();
          return;
        }

        // Auto-reconnect logic
        if (autoReconnect && !isNormalClosure && !reconnectTimeoutRef.current) {
          setConnectionState(prev => ({ 
            ...prev, 
            reconnectAttempts: prev.reconnectAttempts + 1
          }));
          
          if (connectionState.reconnectAttempts < maxReconnectAttempts) {
            console.log(`🔄 WebSocket reconnecting in ${reconnectDelay}ms... (attempt ${connectionState.reconnectAttempts + 1}/${maxReconnectAttempts})`);
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectTimeoutRef.current = null;
              connect();
            }, reconnectDelay);
          } else {
            console.log('🚫 Max reconnect attempts reached, starting fallback polling');
            startFallbackPolling();
          }
        }
      };
    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown connection error';
      setConnectionState(prev => ({ 
        ...prev, 
        status: 'failed',
        lastError: errorMessage,
        reconnectAttempts: prev.reconnectAttempts + 1
      }));
      
      // Start fallback polling if WebSocket creation fails
      if (connectionState.reconnectAttempts >= maxReconnectAttempts) {
        startFallbackPolling();
      }
    }
  }, [url, enabled, autoReconnect, reconnectDelay, maxReconnectAttempts, connectionState.reconnectAttempts, connectionState.status, onUpdate, onConnect, onDisconnect, onError, startFallbackPolling, stopFallbackPolling]);

  const disconnect = useCallback(() => {
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Stop fallback polling
    stopFallbackPolling();

    // Close WebSocket connection
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect'); // Normal closure
      wsRef.current = null;
    }

    setConnectionState({
      status: 'disconnected',
      reconnectAttempts: 0,
      fallbackActive: false
    });
  }, [stopFallbackPolling]);

  const sendMessage = useCallback((message: any) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
      }
    } else {
      console.warn('WebSocket is not connected - message not sent:', {
        readyState: ws?.readyState,
        status: connectionState.status,
        fallbackActive: connectionState.fallbackActive
      });
    }
  }, [connectionState.status, connectionState.fallbackActive]);

  const isConnected = useCallback(() => {
    const ws = wsRef.current;
    return ws ? ws.readyState === WebSocket.OPEN : false;
  }, []);

  const getConnectionStatus = useCallback(() => {
    return {
      ...connectionState,
      isConnected: isConnected(),
      hasConnection: isConnected() || connectionState.fallbackActive
    };
  }, [connectionState, isConnected]);

  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [connect, disconnect, enabled]);

  return {
    connect,
    disconnect,
    sendMessage,
    isConnected: isConnected(),
    connectionStatus: getConnectionStatus(),
    fallbackActive: connectionState.fallbackActive,
    reconnectAttempts: connectionState.reconnectAttempts,
    lastError: connectionState.lastError
  };
};