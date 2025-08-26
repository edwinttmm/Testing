/**
 * Async Pattern Fixes for "message channel closed before response received" Error
 * 
 * This file contains corrected patterns for handling async operations
 * in browser extensions and WebSocket connections.
 */

// ============================================================================
// 1. BROWSER EXTENSION MESSAGE HANDLING FIXES
// ============================================================================

/**
 * CORRECT: Async message listener with proper response handling
 */
const correctAsyncMessageListener = () => {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Handle async operations correctly
    if (message.type === 'ASYNC_OPERATION') {
      handleAsyncOperation(message.data)
        .then(result => {
          sendResponse({ success: true, data: result });
        })
        .catch(error => {
          sendResponse({ success: false, error: error.message });
        });
      
      // CRITICAL: Return true to keep message channel open for async response
      return true;
    }
  });
};

/**
 * CORRECT: Promise-based message handling with timeout
 */
const handleAsyncOperation = async (data: any): Promise<any> => {
  return new Promise((resolve, reject) => {
    // Set timeout to prevent hanging promises
    const timeoutId = setTimeout(() => {
      reject(new Error('Operation timeout after 10 seconds'));
    }, 10000);

    // Perform actual async operation
    performOperation(data)
      .then(result => {
        clearTimeout(timeoutId);
        resolve(result);
      })
      .catch(error => {
        clearTimeout(timeoutId);
        reject(error);
      });
  });
};

// ============================================================================
// 2. WEBSOCKET CONNECTION FIXES
// ============================================================================

/**
 * CORRECT: WebSocket hook with proper cleanup
 */
export const useWebSocketFixed = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const configPromiseRef = useRef<Promise<any> | null>(null);
  const cleanupFunctionsRef = useRef<(() => void)[]>([]);

  // FIXED: Proper promise cleanup and error handling
  const connect = useCallback(async () => {
    try {
      // Cancel any existing config loading
      if (configPromiseRef.current) {
        configPromiseRef.current = null;
      }

      // Load configuration with proper error handling
      configPromiseRef.current = waitForConfig();
      await configPromiseRef.current;

      // Create WebSocket connection
      const socket = io(options.url || '', {
        timeout: 20000,
        reconnection: false, // Handle manually
      });

      socketRef.current = socket;

      // Set up event listeners with error boundaries
      socket.on('connect', () => {
        setIsConnected(true);
        setError(null);
        clearReconnectTimeout();
      });

      socket.on('disconnect', (reason) => {
        setIsConnected(false);
        if (reason !== 'io client disconnect') {
          scheduleReconnect();
        }
      });

      socket.on('connect_error', (err) => {
        const error = new Error(`Connection failed: ${err.message}`);
        setError(error);
        scheduleReconnect();
      });

    } catch (error) {
      const errorMsg = error instanceof Error ? error : new Error('Unknown error');
      setError(errorMsg);
    }
  }, [options.url]);

  // FIXED: Proper reconnection with cleanup
  const scheduleReconnect = useCallback(() => {
    clearReconnectTimeout();
    
    const timeoutId = setTimeout(() => {
      connect().catch(error => {
        console.error('Reconnection failed:', error);
      });
    }, 3000);
    
    reconnectTimeoutRef.current = timeoutId;
    
    // Add to cleanup functions
    const cleanup = () => clearTimeout(timeoutId);
    cleanupFunctionsRef.current.push(cleanup);
  }, [connect]);

  // FIXED: Comprehensive cleanup
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    // Clear all timeouts and cleanup functions
    clearReconnectTimeout();
    cleanupFunctionsRef.current.forEach(cleanup => cleanup());
    cleanupFunctionsRef.current = [];
    
    // Cancel any pending config promises
    configPromiseRef.current = null;
    
    // Disconnect socket
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    
    setIsConnected(false);
    setError(null);
  }, [clearReconnectTimeout]);

  // FIXED: Proper effect cleanup
  useEffect(() => {
    if (options.autoConnect) {
      connect().catch(error => {
        console.error('Auto-connect failed:', error);
      });
    }

    return () => {
      disconnect();
    };
  }, [connect, disconnect, options.autoConnect]);

  return {
    socket: socketRef.current,
    isConnected,
    error,
    connect,
    disconnect,
    emit: (event: string, data?: unknown) => {
      if (socketRef.current?.connected) {
        socketRef.current.emit(event, data);
      }
    },
    on: (event: string, callback: (data: any) => void) => {
      if (socketRef.current) {
        socketRef.current.on(event, callback);
      }
      return () => {
        if (socketRef.current) {
          socketRef.current.off(event, callback);
        }
      };
    },
    configReady: true,
  };
};

// ============================================================================
// 3. CONFIGURATION MANAGEMENT FIXES
// ============================================================================

/**
 * CORRECT: Configuration loading with proper error handling
 */
export const waitForConfigFixed = (timeout: number = 10000): Promise<void> => {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error(`Configuration loading timeout after ${timeout}ms`));
    }, timeout);

    const checkConfig = () => {
      if (isConfigInitialized()) {
        clearTimeout(timeoutId);
        resolve();
      } else {
        // Check again in 100ms
        setTimeout(checkConfig, 100);
      }
    };

    checkConfig();
  });
};

/**
 * CORRECT: Async operation with cancellation support
 */
export class CancellablePromise<T> {
  private promise: Promise<T>;
  private cancelled = false;

  constructor(executor: (resolve: (value: T) => void, reject: (reason?: any) => void) => void) {
    this.promise = new Promise<T>((resolve, reject) => {
      executor(
        (value: T) => {
          if (!this.cancelled) resolve(value);
        },
        (reason?: any) => {
          if (!this.cancelled) reject(reason);
        }
      );
    });
  }

  then<TResult1 = T, TResult2 = never>(
    onfulfilled?: ((value: T) => TResult1 | PromiseLike<TResult1>) | null,
    onrejected?: ((reason: any) => TResult2 | PromiseLike<TResult2>) | null
  ): Promise<TResult1 | TResult2> {
    return this.promise.then(onfulfilled, onrejected);
  }

  catch<TResult = never>(
    onrejected?: ((reason: any) => TResult | PromiseLike<TResult>) | null
  ): Promise<T | TResult> {
    return this.promise.catch(onrejected);
  }

  cancel() {
    this.cancelled = true;
  }

  isCancelled() {
    return this.cancelled;
  }
}

// ============================================================================
// 4. ERROR BOUNDARY UTILITY
// ============================================================================

/**
 * CORRECT: Promise error boundary with logging
 */
export const withErrorBoundary = async <T>(
  operation: () => Promise<T>,
  context: string,
  fallback?: T
): Promise<T | undefined> => {
  try {
    const result = await operation();
    return result;
  } catch (error) {
    console.error(`Error in ${context}:`, error);
    
    // Store error information for debugging
    const errorInfo = {
      context,
      error: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString(),
      stack: error instanceof Error ? error.stack : undefined
    };
    
    // Could store in local storage or send to error reporting service
    localStorage.setItem(`error_${Date.now()}`, JSON.stringify(errorInfo));
    
    if (fallback !== undefined) {
      return fallback;
    }
    
    // Re-throw if no fallback
    throw error;
  }
};

// ============================================================================
// 5. USAGE EXAMPLES
// ============================================================================

/**
 * Example: Using the fixed WebSocket hook
 */
const ExampleComponent: React.FC = () => {
  const { socket, isConnected, error, connect, disconnect } = useWebSocketFixed({
    url: 'ws://localhost:8001',
    autoConnect: true,
  });

  useEffect(() => {
    if (error) {
      console.error('WebSocket error:', error.message);
      // Handle error appropriately
    }
  }, [error]);

  return (
    <div>
      <p>Status: {isConnected ? 'Connected' : 'Disconnected'}</p>
      {error && <p>Error: {error.message}</p>}
      <button onClick={() => connect()}>Connect</button>
      <button onClick={() => disconnect()}>Disconnect</button>
    </div>
  );
};

/**
 * Example: Using error boundary for async operations
 */
const handleAsyncOperationSafely = async () => {
  await withErrorBoundary(
    async () => {
      const result = await someAsyncOperation();
      return result;
    },
    'handleAsyncOperationSafely'
  );
};