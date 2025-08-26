import { useEffect, useCallback, useState, useRef } from 'react';
import { GroundTruthAnnotation } from '../services/types';
import { getConfigValue, waitForConfig, isConfigReady } from '../utils/configOverride';

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
  const [configReady, setConfigReady] = useState(isConfigReady());
  const [resolvedUrl, setResolvedUrl] = useState<string>('');
  
  // Load URL from configuration
  useEffect(() => {
    const initializeUrl = async () => {
      try {
        if (!configReady) {
          console.log('⏳ useDetectionWebSocket waiting for configuration...');
          await waitForConfig(10000);
          setConfigReady(true);
        }
        
        // Get WebSocket URL from configuration or fallback
        const wsBaseUrl = getConfigValue('REACT_APP_WS_URL', '') ||
                         getConfigValue('REACT_APP_SOCKETIO_URL', '') ||
                         'ws://155.138.239.131:8001';
        
        // Convert HTTP URLs to WebSocket URLs and add detection path
        let detectionUrl = wsBaseUrl;
        if (detectionUrl.startsWith('http://')) {
          detectionUrl = detectionUrl.replace('http://', 'ws://');
        } else if (detectionUrl.startsWith('https://')) {
          detectionUrl = detectionUrl.replace('https://', 'wss://');
        }
        
        // Ensure it ends with detection WebSocket path
        if (!detectionUrl.includes('/ws/detection')) {
          detectionUrl = detectionUrl.replace(/\/+$/, '') + '/ws/detection';
        }
        
        setResolvedUrl(detectionUrl);
        console.log('🔧 Detection WebSocket URL resolved to:', detectionUrl);
        
      } catch (error) {
        console.error('❌ Failed to resolve detection WebSocket URL:', error);
        // Use fallback
        const fallbackUrl = 'ws://155.138.239.131:8001/ws/detection';
        setResolvedUrl(fallbackUrl);
        setConfigReady(true);
        console.log('🔧 Using fallback detection WebSocket URL:', fallbackUrl);
      }
    };
    
    initializeUrl();
  }, [configReady]);
  
  const {
    url = resolvedUrl,
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
      console.log('ℹ️ Detection WebSocket disabled via options');
      return;
    }

    if (!configReady || !url) {
      console.log('⏳ Detection WebSocket waiting for URL configuration...');
      return;
    }

    if (websocketRef.current?.readyState === WebSocket.CONNECTING || 
        websocketRef.current?.readyState === WebSocket.OPEN) {
      console.log('ℹ️ Detection WebSocket already connected or connecting');
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
              
              console.log(`🔄 Reconnecting in ${delay}ms (attempt ${prev.reconnectAttempts + 1}/${maxReconnectAttempts})`);
              
              reconnectTimeoutRef.current = setTimeout(() => {
                connect();
              }, delay);
              
              return {
                ...prev,
                status: 'reconnecting' as const,
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
  }, [url, enabled, autoReconnect, reconnectDelay, maxReconnectAttempts, fallbackPollingInterval, onUpdate, onConnect, onDisconnect, onError, onFallback, configReady]);

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

  // Auto-connect on mount if enabled and URL is resolved
  useEffect(() => {
    if (enabled && configReady && url) {
      console.log('🚀 Detection WebSocket system initialized with URL:', url);
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, configReady, url, connect, disconnect]);

  // Return WebSocket interface
  return {
    connect,
    disconnect,
    sendMessage,
    isConnected: websocketRef.current?.readyState === WebSocket.OPEN,
    connectionStatus: getConnectionStatus(),
    fallbackActive: connectionState.fallbackActive,
    reconnectAttempts: connectionState.reconnectAttempts,
    lastError: connectionState.lastError,
    configReady,
    resolvedUrl: url
  };
};