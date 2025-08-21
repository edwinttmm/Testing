import { useEffect, useRef, useCallback } from 'react';
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
  onUpdate?: (update: DetectionUpdate) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export const useDetectionWebSocket = (options: UseDetectionWebSocketOptions = {}) => {
  const wsConfig = getServiceConfig('websocket');
  const {
    url = `${wsConfig.url}/ws/detection`,
    autoReconnect = true, // Enable auto-reconnect for better UX
    reconnectDelay = 5000, // Reasonable delay
    onUpdate,
    onConnect,
    onDisconnect,
    onError
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectedRef = useRef(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      // Temporarily disable WebSocket due to 403 authentication issues
      console.log('🚧 WebSocket disabled - backend requires authentication');
      return;
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log('Detection WebSocket connected');
        isConnectedRef.current = true;
        onConnect?.();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const update: DetectionUpdate = JSON.parse(event.data);
          onUpdate?.(update);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('Detection WebSocket error:', error);
        onError?.(error);
      };

      wsRef.current.onclose = (event) => {
        console.log('Detection WebSocket disconnected:', event.code, event.reason);
        isConnectedRef.current = false;
        onDisconnect?.();

        // Auto-reconnect if enabled and not a normal closure
        if (autoReconnect && event.code !== 1000 && !reconnectTimeoutRef.current) {
          console.log(`WebSocket reconnecting in ${reconnectDelay}ms...`);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectTimeoutRef.current = null;
            connect();
          }, reconnectDelay);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [url, autoReconnect, reconnectDelay, onUpdate, onConnect, onDisconnect, onError]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  const isConnected = useCallback(() => {
    return wsRef.current?.readyState === WebSocket.OPEN;
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connect,
    disconnect,
    sendMessage,
    isConnected: isConnected()
  };
};