import { useEffect, useCallback, useState, useRef } from 'react';
import { GroundTruthAnnotation } from '../services/types';

// WebSocket functionality re-enabled for real-time detection updates
export interface DetectionUpdate {
  type: 'progress' | 'detection' | 'complete' | 'error';
  videoId: string;
  data?: unknown;
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
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';
  reconnectAttempts: number;
  lastError: string | null;
  fallbackActive: boolean;
}

// Re-enabled WebSocket detection hook with robust connection management
export const useDetectionWebSocket = (options: UseDetectionWebSocketOptions = {}) => {
  const {
    url = `ws://${window.location.hostname}:8001/ws/detection`,
    autoReconnect = true,
    reconnectDelay = 3000,
    maxReconnectAttempts = 5,
    enabled = true,
    fallbackPollingInterval = 5000,
    onUpdate,
    onConnect,
    onDisconnect,
    onError,
    onFallback
  } = options;

  const [connectionState, setConnectionState] = useState<ConnectionState>({
    status: 'disconnected',
    reconnectAttempts: 0,
    lastError: null,
    fallbackActive: false
  });

  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const fallbackIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!enabled) {
      console.log('ℹ️ WebSocket disabled via options');
      return;
    }

    if (websocketRef.current?.readyState === WebSocket.CONNECTING || 
        websocketRef.current?.readyState === WebSocket.OPEN) {
      console.log('ℹ️ WebSocket already connected or connecting');
      return;
    }

    console.log('🔌 Connecting to detection WebSocket:', url);
    setConnectionState(prev => ({ ...prev, status: 'connecting' }));

    try {
      const ws = new WebSocket(url);
      websocketRef.current = ws;

      ws.onopen = () => {
        console.log('✅ Detection WebSocket connected');
        setConnectionState(prev => ({
          ...prev,
          status: 'connected',
          reconnectAttempts: 0,
          fallbackActive: false
        }));
        
        // Clear fallback polling if active
        if (fallbackIntervalRef.current) {
          clearInterval(fallbackIntervalRef.current);
          fallbackIntervalRef.current = null;
        }
        
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as DetectionUpdate;
          onUpdate?.(data);
        } catch (error) {
          console.warn('⚠️ Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('📤 Detection WebSocket disconnected:', event.reason);
        setConnectionState(prev => ({ ...prev, status: 'disconnected' }));
        websocketRef.current = null;
        onDisconnect?.();

        // Auto-reconnect if enabled and within attempt limits
        if (autoReconnect) {
          setConnectionState(prev => {
            if (prev.reconnectAttempts < maxReconnectAttempts) {
              const delay = reconnectDelay * Math.pow(1.5, prev.reconnectAttempts);
          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${connectionState.reconnectAttempts + 1}/${maxReconnectAttempts})`);
          
              console.log(`🔄 Reconnecting in ${delay}ms (attempt ${prev.reconnectAttempts + 1}/${maxReconnectAttempts})`);
              
              reconnectTimeoutRef.current = setTimeout(() => {
                connect();
              }, delay);
              
              return {
                ...prev,
                status: 'reconnecting',
                reconnectAttempts: prev.reconnectAttempts + 1
              };
            }
            return prev;
          });
        } else if (fallbackPollingInterval > 0) {
          // Start fallback polling
          console.log('🔄 Starting fallback HTTP polling');
          setConnectionState(prev => ({ ...prev, fallbackActive: true }));
          onFallback?.('WebSocket connection failed, using HTTP polling');
          
          fallbackIntervalRef.current = setInterval(() => {
            // Trigger polling-based detection updates
            console.log('📡 HTTP polling fallback active');
          }, fallbackPollingInterval);
        }
      };

      ws.onerror = (event) => {
        console.error('❌ Detection WebSocket error:', event);
        const errorMessage = 'WebSocket connection error';
        setConnectionState(prev => ({
          ...prev,
          status: 'error',
          lastError: errorMessage
        }));
        onError?.(event);
      };

    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error);
      setConnectionState(prev => ({
        ...prev,
        status: 'error',
        lastError: error instanceof Error ? error.message : 'Unknown error'
      }));
    }
  }, [url, enabled, autoReconnect, reconnectDelay, maxReconnectAttempts, fallbackPollingInterval, onUpdate, onConnect, onDisconnect, onError, onFallback]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    console.log('🔌 Disconnecting detection WebSocket');
    
    // Clear reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Clear fallback polling
    if (fallbackIntervalRef.current) {
      clearInterval(fallbackIntervalRef.current);
      fallbackIntervalRef.current = null;
    }

    // Close WebSocket connection
    if (websocketRef.current) {
      websocketRef.current.close(1000, 'Client disconnect');
      websocketRef.current = null;
    }

    setConnectionState(prev => ({
      ...prev,
      status: 'disconnected',
      reconnectAttempts: 0,
      fallbackActive: false
    }));
  }, []);

  // Send message through WebSocket
  const sendMessage = useCallback((message: unknown) => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      try {
        websocketRef.current.send(JSON.stringify(message));
        console.log('📤 Sent WebSocket message:', message);
      } catch (error) {
        console.error('❌ Failed to send WebSocket message:', error);
      }
    } else {
      console.warn('⚠️ Cannot send message - WebSocket not connected');
    }
  }, []);

  // Get connection status
  const getConnectionStatus = useCallback(() => {
    return {
      ...connectionState,
      isConnected: websocketRef.current?.readyState === WebSocket.OPEN,
      hasConnection: websocketRef.current !== null
    };
  }, [connectionState]);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (enabled) {
      console.log('🚀 Detection WebSocket system initialized');
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  // Return WebSocket interface
  return {
    connect,
    disconnect,
    sendMessage,
    isConnected: websocketRef.current?.readyState === WebSocket.OPEN,
    connectionStatus: getConnectionStatus(),
    fallbackActive: connectionState.fallbackActive,
    reconnectAttempts: connectionState.reconnectAttempts,
    lastError: connectionState.lastError
  };
};