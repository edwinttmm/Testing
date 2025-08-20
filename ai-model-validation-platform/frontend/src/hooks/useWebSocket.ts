import { useEffect, useRef, useCallback, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import envConfig, { getServiceConfig, isDebugEnabled } from '../utils/envConfig';

interface UseWebSocketOptions {
  url?: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  socket: Socket | null;
  isConnected: boolean;
  error: Error | null;
  connect: () => void;
  disconnect: () => void;
  emit: (event: string, data?: any) => void;
  on: (event: string, callback: (...args: any[]) => void) => () => void;
}

// WebSocket connection pool to prevent multiple connections to the same URL
const socketPool = new Map<string, Socket>();

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  // Get WebSocket configuration from environment config
  const socketConfig = getServiceConfig('socketio');
  
  const {
    url = socketConfig.url,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = socketConfig.retryAttempts,
    reconnectDelay = socketConfig.retryDelay,
    autoConnect = true,
  } = options;
  
  if (isDebugEnabled()) {
    console.log('🔌 WebSocket initializing with config:', {
      url,
      reconnectAttempts,
      reconnectDelay,
      autoConnect
    });
  }

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const listenersRef = useRef<Map<string, Set<(...args: any[]) => void>>>(new Map());
  const scheduleReconnectRef = useRef<(() => void) | null>(null);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // Define connect function first, before scheduleReconnect
  const connect = useCallback(() => {
    if (socketRef.current?.connected) {
      return;
    }

    try {
      // Check socket pool first to reuse existing connections
      let socket = socketPool.get(url);
      
      if (!socket || socket.disconnected) {
        socket = io(url, {
          transports: ['websocket'],
          timeout: socketConfig.timeout,
          forceNew: false,
          reconnection: false, // We handle reconnection manually
          withCredentials: false, // Adjust based on environment
        });
        
        if (isDebugEnabled()) {
          console.log(`🔌 Creating new Socket.IO connection to ${url}`);
        }
        socketPool.set(url, socket);
      }

      socketRef.current = socket;

      // Set up event listeners
      socket.on('connect', () => {
        setIsConnected(true);
        setError(null);
        reconnectCountRef.current = 0;
        clearReconnectTimeout();
        
        if (isDebugEnabled()) {
          console.log('✅ WebSocket connected successfully');
        }
        
        onConnect?.();
      });

      socket.on('disconnect', (reason) => {
        setIsConnected(false);
        
        if (isDebugEnabled()) {
          console.warn(`🔌 WebSocket disconnected: ${reason}`);
        }
        
        onDisconnect?.();
        
        // Auto-reconnect for certain disconnect reasons
        if (reason === 'io server disconnect' || reason === 'transport close') {
          if (isDebugEnabled()) {
            console.log('🔄 Scheduling WebSocket reconnection...');
          }
          scheduleReconnectRef.current?.();
        }
      });

      socket.on('connect_error', (err) => {
        const error = new Error(`WebSocket connection error: ${err.message}`);
        setError(error);
        
        if (isDebugEnabled()) {
          console.error('❌ WebSocket connection error:', err.message);
        }
        
        onError?.(error);
        scheduleReconnectRef.current?.();
      });

      // Re-register existing listeners
      Array.from(listenersRef.current.entries()).forEach(([event, callbacks]) => {
        callbacks.forEach(callback => {
          socket!.on(event, callback);
        });
      });

      socket!.connect();
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown WebSocket error');
      setError(error);
      onError?.(error);
    }
  }, [url, onConnect, onDisconnect, onError, clearReconnectTimeout]);

  // Now define scheduleReconnect with connect in scope
  const scheduleReconnect = useCallback(() => {
    if (reconnectCountRef.current >= reconnectAttempts) {
      setError(new Error(`Failed to reconnect after ${reconnectAttempts} attempts`));
      return;
    }

    clearReconnectTimeout();
    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectCountRef.current++;
      connect();
    }, reconnectDelay * Math.pow(2, reconnectCountRef.current)); // Exponential backoff
  }, [reconnectAttempts, reconnectDelay, clearReconnectTimeout, connect]);

  // Assign scheduleReconnect to ref so it can be called from connect
  scheduleReconnectRef.current = scheduleReconnect;

  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    
    if (socketRef.current) {
      // Remove all our listeners
      Array.from(listenersRef.current.entries()).forEach(([event, callbacks]) => {
        callbacks.forEach(callback => {
          socketRef.current?.off(event, callback);
        });
      });
      
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    
    setIsConnected(false);
    setError(null);
  }, [clearReconnectTimeout]);

  const emit = useCallback((event: string, data?: any) => {
    if (socketRef.current?.connected) {
      if (isDebugEnabled()) {
        console.log(`📡 Emitting WebSocket event: ${event}`, data);
      }
      socketRef.current.emit(event, data);
    } else {
      const message = `Cannot emit event '${event}': WebSocket not connected`;
      console.warn(message);
      if (isDebugEnabled()) {
        console.warn('📡 WebSocket emit failed - not connected');
      }
    }
  }, []);

  const on = useCallback((event: string, callback: (...args: any[]) => void) => {
    // Track listeners for cleanup and reconnection
    if (!listenersRef.current.has(event)) {
      listenersRef.current.set(event, new Set());
    }
    listenersRef.current.get(event)!.add(callback);

    // Add listener to current socket if connected
    if (socketRef.current) {
      socketRef.current.on(event, callback);
    }

    // Return cleanup function
    return () => {
      const callbacks = listenersRef.current.get(event);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          listenersRef.current.delete(event);
        }
      }
      
      if (socketRef.current) {
        socketRef.current.off(event, callback);
      }
    };
  }, []);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      clearReconnectTimeout();
      
      // Only disconnect if we're the last component using this socket
      // In a real app, you'd want more sophisticated reference counting
      // eslint-disable-next-line react-hooks/exhaustive-deps
      const currentListeners = listenersRef.current;
      const currentListenerCount = Array.from(currentListeners.values())
        .reduce((total, set) => total + set.size, 0);
      
      if (currentListenerCount === 0) {
        disconnect();
        socketPool.delete(url);
      }
    };
  }, [autoConnect, connect, disconnect, clearReconnectTimeout, url]);

  return {
    socket: socketRef.current,
    isConnected,
    error,
    connect,
    disconnect,
    emit,
    on,
  };
};

export default useWebSocket;