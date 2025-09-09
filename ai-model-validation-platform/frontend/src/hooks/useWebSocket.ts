import { useEffect, useRef, useCallback, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { getServiceConfig, isDebugEnabled } from '../utils/envConfig';
import { waitForConfig, isConfigInitialized } from '../utils/configurationManager';
import logger from '../utils/safeErrorLogger';
import { TimerHandle, safeSetTimeout, safeClearTimeout } from '../utils/timerUtils';

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
  emit: (event: string, data?: unknown) => void;
  on: <T = unknown>(event: string, callback: (data: T) => void) => () => void;
  configReady: boolean;
}

// WebSocket connection pool to prevent multiple connections to the same URL
const socketPool = new Map<string, Socket>();

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const [configLoaded, setConfigLoaded] = useState(isConfigInitialized());
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimeoutRef = useRef<TimerHandle | null>(null);
  const reconnectCountRef = useRef(0);
  const listenersRef = useRef<Map<string, Set<(data: unknown) => void>>>(new Map());
  const scheduleReconnectRef = useRef<(() => void) | null>(null);
  
  // Wait for configuration to load before getting socket config
  const [socketConfig, setSocketConfig] = useState(() => {
    if (isConfigInitialized()) {
      return getServiceConfig('socketio');
    }
    return { url: '', retryAttempts: 5, retryDelay: 1000, timeout: 20000 };
  });
  
  const {
    url = socketConfig.url,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = socketConfig.retryAttempts,
    reconnectDelay = socketConfig.retryDelay,
    autoConnect = true,
  } = options;
  
  if (isDebugEnabled() && configLoaded && url) {
    logger.debug('🔌 WebSocket initializing with config:', {
      url,
      reconnectAttempts,
      reconnectDelay,
      autoConnect,
      configLoaded
    });
  }

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      safeClearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // Load configuration asynchronously
  useEffect(() => {
    if (!configLoaded) {
      if (isDebugEnabled()) {
        logger.debug('⏳ WebSocket waiting for runtime configuration to load...');
      }
      
      waitForConfig()
        .then(() => {
          setConfigLoaded(true);
          const newConfig = getServiceConfig('socketio');
          setSocketConfig(newConfig);
          if (isDebugEnabled()) {
            logger.debug('🔧 WebSocket configuration loaded:', newConfig);
          }
        })
        .catch((err: unknown) => {
          logger.error('❌ Failed to load WebSocket configuration:', err);
          setError(new Error('Configuration loading failed'));
          // Use fallback configuration with correct production URL
          const fallbackConfig = {
            url: 'http://localhost:8001',
            retryAttempts: 5,
            retryDelay: 1000,
            timeout: 20000
          };
          setSocketConfig(fallbackConfig);
          setConfigLoaded(true);
          if (isDebugEnabled()) {
            logger.debug('🔧 Using fallback WebSocket configuration:', fallbackConfig);
          }
        });
    }
  }, [configLoaded]);

  // Define connect function first, before scheduleReconnect
  const connect = useCallback(() => {
    if (!configLoaded) {
      if (isDebugEnabled()) {
        logger.debug('⏳ WebSocket connect() called but configuration not ready yet');
      }
      return;
    }

    if (!url) {
      logger.warn('⚠️ WebSocket cannot connect: no URL configured');
      setError(new Error('No WebSocket URL configured'));
      return;
    }

    if (socketRef.current?.connected) {
      if (isDebugEnabled()) {
        logger.debug('ℹ️ WebSocket already connected');
      }
      return;
    }

    try {
      // Check socket pool first to reuse existing connections
      let socket = socketPool.get(url || '');
      
      if (!socket || socket.disconnected) {
        socket = io(url || '', {
          transports: ['websocket'],
          timeout: socketConfig.timeout || 20000,
          forceNew: false,
          reconnection: false, // We handle reconnection manually
          withCredentials: false, // Adjust based on environment
        });
        
        if (isDebugEnabled()) {
          logger.debug(`🔌 Creating new Socket.IO connection to ${url}`);
        }
        socketPool.set(url || '', socket);
      }

      socketRef.current = socket;

      // Set up event listeners
      socket.on('connect', () => {
        setIsConnected(true);
        setError(null);
        reconnectCountRef.current = 0;
        clearReconnectTimeout();
        
        if (isDebugEnabled()) {
          logger.debug('✅ WebSocket connected successfully to', url);
        }
        
        onConnect?.();
      });

      socket.on('disconnect', (reason) => {
        setIsConnected(false);
        
        if (isDebugEnabled()) {
          logger.warn(`🔌 WebSocket disconnected from ${url}: ${reason}`);
        }
        
        onDisconnect?.();
        
        // Auto-reconnect for certain disconnect reasons
        if (reason === 'io server disconnect' || reason === 'transport close') {
          if (isDebugEnabled()) {
            logger.debug('🔄 Scheduling WebSocket reconnection...');
          }
          scheduleReconnectRef.current?.();
        }
      });

      socket.on('connect_error', (err) => {
        const error = new Error(`WebSocket connection error: ${err.message}`);
        setError(error);
        
        if (isDebugEnabled()) {
          logger.error('❌ WebSocket connection error', { url, error: err.message });
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
  }, [url, onConnect, onDisconnect, onError, clearReconnectTimeout, socketConfig.timeout, configLoaded]);

  // Now define scheduleReconnect with connect in scope
  const scheduleReconnect = useCallback(() => {
    if (reconnectCountRef.current >= (reconnectAttempts || 5)) {
      setError(new Error(`Failed to reconnect after ${reconnectAttempts} attempts`));
      return;
    }

    clearReconnectTimeout();
    reconnectTimeoutRef.current = safeSetTimeout(() => {
      reconnectCountRef.current++;
      connect();
    }, (reconnectDelay || 1000) * Math.pow(2, reconnectCountRef.current)); // Exponential backoff
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

  const emit = useCallback((event: string, data?: unknown) => {
    if (socketRef.current?.connected) {
      if (isDebugEnabled()) {
        logger.debug(`📡 Emitting WebSocket event: ${event}`, data);
      }
      socketRef.current.emit(event, data);
    } else {
      const message = `Cannot emit event '${event}': WebSocket not connected`;
      logger.warn(message);
      if (isDebugEnabled()) {
        logger.warn('📡 WebSocket emit failed - not connected to', url);
      }
    }
  }, [url]);

  const on = useCallback(<T = unknown>(event: string, callback: (data: T) => void) => {
    // Track listeners for cleanup and reconnection
    if (!listenersRef.current.has(event)) {
      listenersRef.current.set(event, new Set());
    }
    const callbacks = listenersRef.current.get(event);
    if (callbacks) {
      callbacks.add(callback as (data: unknown) => void);
    }

    // Add listener to current socket if connected
    if (socketRef.current) {
      socketRef.current.on(event, callback as (data: unknown) => void);
    }

    // Return cleanup function
    return () => {
      const callbacks = listenersRef.current.get(event);
      if (callbacks) {
        callbacks.delete(callback as (data: unknown) => void);
        if (callbacks.size === 0) {
          listenersRef.current.delete(event);
        }
      }
      
      if (socketRef.current) {
        socketRef.current.off(event, callback as (data: unknown) => void);
      }
    };
  }, []);

  // Auto-connect on mount if enabled and configuration is loaded
  useEffect(() => {
    if (autoConnect && configLoaded && url) {
      if (isDebugEnabled()) {
        logger.debug('🚀 WebSocket auto-connecting with loaded configuration to', url);
      }
      connect();
    }

    return () => {
      clearReconnectTimeout();
      
      // Only disconnect if we're the last component using this socket
      // In a real app, you'd want more sophisticated reference counting
      const currentListeners = listenersRef.current;
      const currentListenerCount = Array.from(currentListeners.values())
        .reduce((total, set) => total + set.size, 0);
      
      if (currentListenerCount === 0) {
        disconnect();
        socketPool.delete(url || '');
      }
    };
  }, [autoConnect, configLoaded, url, connect, disconnect, clearReconnectTimeout]);

  return {
    socket: socketRef.current,
    isConnected,
    error,
    connect,
    disconnect,
    emit,
    on,
    configReady: configLoaded,
  };
};

export default useWebSocket;