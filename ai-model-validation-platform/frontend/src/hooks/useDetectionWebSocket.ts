import { useEffect, useCallback, useState } from 'react';
import { GroundTruthAnnotation } from '../services/types';

// WebSocket functionality completely disabled - HTTP-only detection workflow
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
  status: 'disabled'; // Always disabled - no WebSocket connections
  reconnectAttempts: 0;
  lastError?: string;
  fallbackActive: false;
}

// HTTP-only detection hook - WebSocket functionality completely removed
export const useDetectionWebSocket = (options: UseDetectionWebSocketOptions = {}) => {
  const [connectionState] = useState<ConnectionState>({
    status: 'disabled',
    reconnectAttempts: 0,
    fallbackActive: false
  });

  // No polling or WebSocket functionality - clean HTTP-only approach
  // Functions removed to eliminate unused variable warnings

  // No-op connect function - WebSocket functionality completely disabled
  const connect = useCallback(() => {
    console.log('ℹ️ WebSocket functionality disabled - using HTTP-only detection');
    // No WebSocket connections will be attempted
  }, []);

  // No-op disconnect function - no connections to close
  const disconnect = useCallback(() => {
    console.log('ℹ️ HTTP-only mode - no connections to disconnect');
    // No cleanup needed since no WebSocket connections exist
  }, []);

  // No-op send function - no WebSocket to send messages to
  const sendMessage = useCallback((message: any) => {
    console.log('ℹ️ HTTP-only mode - no WebSocket messaging available');
    // Messages are not sent as WebSocket functionality is disabled
  }, []);

  // Always return false for WebSocket connection (removed to eliminate unused variable warnings)

  // Return HTTP-only status
  const getConnectionStatus = useCallback(() => {
    return {
      ...connectionState,
      isConnected: false,
      hasConnection: false // HTTP-only workflow, no persistent connection
    };
  }, [connectionState]);

  // No effect needed - WebSocket functionality completely disabled
  useEffect(() => {
    console.log('ℹ️ Detection system initialized in HTTP-only mode');
    // No WebSocket connections will be established
    return () => {
      // No cleanup needed
    };
  }, []);

  // Return HTTP-only interface - no WebSocket functionality
  return {
    connect,
    disconnect,
    sendMessage,
    isConnected: false, // Always false
    connectionStatus: getConnectionStatus(),
    fallbackActive: false, // No fallback polling
    reconnectAttempts: 0, // No reconnection attempts
    lastError: undefined // No WebSocket errors
  };
};