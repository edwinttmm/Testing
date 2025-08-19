import { useEffect, useRef, useCallback, useState } from 'react';
import { io, Socket } from 'socket.io-client';

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
  const {
    url = process.env.REACT_APP_WS_URL || 'http://localhost:8001',
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectDelay = 1000,
    autoConnect = true,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const listenersRef = useRef<Map<string, Set<(...args: any[]) => void>>>(new Map());

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

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
          timeout: 20000,
          forceNew: false,
          reconnection: false, // We handle reconnection manually
        });
        socketPool.set(url, socket);
      }

      socketRef.current = socket;

      // Set up event listeners
      socket.on('connect', () => {
        setIsConnected(true);
        setError(null);
        reconnectCountRef.current = 0;
        clearReconnectTimeout();
        onConnect?.();
      });

      socket.on('disconnect', (reason) => {
        setIsConnected(false);
        onDisconnect?.();
        
        // Auto-reconnect for certain disconnect reasons
        if (reason === 'io server disconnect' || reason === 'transport close') {
          scheduleReconnect();
        }
      });

      socket.on('connect_error', (err) => {
        const error = new Error(`WebSocket connection error: ${err.message}`);
        setError(error);
        onError?.(error);
        scheduleReconnect();
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
  }, [url, onConnect, onDisconnect, onError, scheduleReconnect, clearReconnectTimeout]);

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
      socketRef.current.emit(event, data);
    } else {
      console.warn(`Cannot emit event '${event}': WebSocket not connected`);
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
      const currentListenerCount = Array.from(listenersRef.current.values())
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