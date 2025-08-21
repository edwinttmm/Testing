import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { useDetectionWebSocket, DetectionUpdate } from '../../ai-model-validation-platform/frontend/src/hooks/useDetectionWebSocket';

describe('useDetectionWebSocket Enhanced Features', () => {
  let mockWebSocket: any;
  let originalWebSocket: any;

  beforeEach(() => {
    originalWebSocket = global.WebSocket;
    mockWebSocket = {
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      close: jest.fn(),
      send: jest.fn(),
      readyState: WebSocket.CLOSED,
      onopen: null,
      onclose: null,
      onmessage: null,
      onerror: null
    };

    global.WebSocket = jest.fn(() => mockWebSocket) as any;
    jest.clearAllTimers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    jest.useRealTimers();
  });

  describe('Enhanced Connection Management', () => {
    it('should handle disabled WebSocket gracefully', () => {
      const { result } = renderHook(() => 
        useDetectionWebSocket({ enabled: false })
      );

      expect(WebSocket).not.toHaveBeenCalled();
      expect(result.current.connectionStatus.status).toBe('disabled');
      expect(result.current.isConnected).toBe(false);
    });

    it('should provide detailed connection status', () => {
      const { result } = renderHook(() => useDetectionWebSocket());

      expect(result.current.connectionStatus).toHaveProperty('status');
      expect(result.current.connectionStatus).toHaveProperty('reconnectAttempts');
      expect(result.current.connectionStatus).toHaveProperty('fallbackActive');
      expect(result.current.connectionStatus).toHaveProperty('isConnected');
      expect(result.current.connectionStatus).toHaveProperty('hasConnection');
    });

    it('should track reconnection attempts', () => {
      const { result } = renderHook(() => 
        useDetectionWebSocket({ autoReconnect: true, maxReconnectAttempts: 2 })
      );

      // Simulate connection failure
      act(() => {
        mockWebSocket.onclose({ code: 1006, reason: 'Connection lost' });
      });

      expect(result.current.reconnectAttempts).toBe(1);

      // Fast-forward to trigger reconnection
      act(() => {
        jest.advanceTimersByTime(5000);
      });

      // Simulate another failure
      act(() => {
        mockWebSocket.onclose({ code: 1006, reason: 'Connection lost again' });
      });

      expect(result.current.reconnectAttempts).toBe(2);
    });

    it('should handle authentication errors with fallback', () => {
      const onFallback = jest.fn();
      const { result } = renderHook(() => 
        useDetectionWebSocket({ onFallback })
      );

      // Simulate authentication error (403)
      act(() => {
        mockWebSocket.onclose({ code: 1008, reason: 'Authentication failed' });
      });

      expect(onFallback).toHaveBeenCalledWith('WebSocket authentication failed (403/auth error), falling back to HTTP polling');
      expect(result.current.fallbackActive).toBe(true);
    });
  });

  describe('Fallback Polling Mechanism', () => {
    it('should start HTTP polling when WebSocket fails', () => {
      const onUpdate = jest.fn();
      const onFallback = jest.fn();
      
      const { result } = renderHook(() => 
        useDetectionWebSocket({ 
          onUpdate, 
          onFallback,
          maxReconnectAttempts: 1,
          fallbackPollingInterval: 1000
        })
      );

      // Simulate max reconnect attempts reached
      act(() => {
        mockWebSocket.onclose({ code: 1006, reason: 'Connection lost' });
      });

      act(() => {
        jest.advanceTimersByTime(5000);
      });

      act(() => {
        mockWebSocket.onclose({ code: 1006, reason: 'Connection lost again' });
      });

      expect(result.current.fallbackActive).toBe(true);

      // Verify polling is working
      act(() => {
        jest.advanceTimersByTime(1000);
      });

      expect(onUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'progress',
          videoId: 'fallback',
          data: expect.objectContaining({
            fallback: true,
            timestamp: expect.any(Number)
          })
        })
      );
    });

    it('should stop fallback polling when WebSocket reconnects', () => {
      const { result } = renderHook(() => 
        useDetectionWebSocket({ 
          maxReconnectAttempts: 1,
          fallbackPollingInterval: 1000
        })
      );

      // Start fallback polling
      act(() => {
        mockWebSocket.onclose({ code: 1008, reason: 'Auth failed' });
      });

      expect(result.current.fallbackActive).toBe(true);

      // Simulate successful WebSocket connection
      act(() => {
        result.current.connect();
        mockWebSocket.readyState = WebSocket.OPEN;
        mockWebSocket.onopen();
      });

      expect(result.current.fallbackActive).toBe(false);
      expect(result.current.isConnected).toBe(true);
    });

    it('should clear fallback polling on disconnect', () => {
      const { result } = renderHook(() => 
        useDetectionWebSocket({ fallbackPollingInterval: 500 })
      );

      // Start fallback polling
      act(() => {
        mockWebSocket.onclose({ code: 1008, reason: 'Auth failed' });
      });

      expect(result.current.fallbackActive).toBe(true);

      // Disconnect
      act(() => {
        result.current.disconnect();
      });

      expect(result.current.fallbackActive).toBe(false);
    });
  });

  describe('Error Handling & Recovery', () => {
    it('should handle WebSocket constructor failures', () => {
      const onFallback = jest.fn();
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      global.WebSocket = jest.fn(() => {
        throw new Error('WebSocket not supported');
      }) as any;

      const { result } = renderHook(() => 
        useDetectionWebSocket({ onFallback, maxReconnectAttempts: 1 })
      );

      expect(consoleSpy).toHaveBeenCalledWith(
        '❌ Failed to create WebSocket connection:', 
        expect.any(Error)
      );

      expect(result.current.connectionStatus.status).toBe('failed');
      expect(result.current.lastError).toContain('WebSocket not supported');
      
      consoleSpy.mockRestore();
    });

    it('should provide user-friendly error messages', () => {
      const { result } = renderHook(() => useDetectionWebSocket());

      act(() => {
        mockWebSocket.onerror(new Event('error'));
        mockWebSocket.onclose({ code: 1011, reason: 'Server error' });
      });

      expect(result.current.lastError).toBe('Server error');
      expect(result.current.connectionStatus.status).toBe('disconnected');
    });

    it('should handle different closure codes appropriately', () => {
      const onFallback = jest.fn();
      const { result } = renderHook(() => 
        useDetectionWebSocket({ onFallback })
      );

      // Normal closure - should not trigger fallback
      act(() => {
        mockWebSocket.onclose({ code: 1000, reason: 'Normal closure' });
      });

      expect(onFallback).not.toHaveBeenCalled();
      expect(result.current.fallbackActive).toBe(false);

      // Authentication error - should trigger fallback
      act(() => {
        mockWebSocket.onclose({ code: 1008, reason: 'Authentication failed' });
      });

      expect(onFallback).toHaveBeenCalled();
      expect(result.current.fallbackActive).toBe(true);
    });
  });

  describe('Message Handling & Type Safety', () => {
    it('should handle null WebSocket reference safely', () => {
      const { result } = renderHook(() => useDetectionWebSocket());

      // Manually set WebSocket to null
      act(() => {
        result.current.disconnect();
      });

      // Try to send message with null WebSocket
      act(() => {
        result.current.sendMessage({ type: 'test' });
      });

      // Should not throw error
      expect(result.current.isConnected).toBe(false);
    });

    it('should handle message sending with proper error handling', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      mockWebSocket.readyState = WebSocket.OPEN;
      mockWebSocket.send = jest.fn(() => {
        throw new Error('Send failed');
      });

      const { result } = renderHook(() => useDetectionWebSocket());

      act(() => {
        result.current.sendMessage({ type: 'test' });
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to send WebSocket message:', 
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });

    it('should validate connection status consistently', () => {
      const { result } = renderHook(() => useDetectionWebSocket());

      expect(result.current.connectionStatus.isConnected).toBe(result.current.isConnected);

      mockWebSocket.readyState = WebSocket.OPEN;
      // Force re-render to update connection status
      const { result: result2 } = renderHook(() => useDetectionWebSocket());
      
      expect(result2.current.connectionStatus.hasConnection).toBe(
        result2.current.isConnected || result2.current.fallbackActive
      );
    });
  });

  describe('Configuration & Options', () => {
    it('should respect custom configuration options', () => {
      const customOptions = {
        autoReconnect: false,
        maxReconnectAttempts: 5,
        reconnectDelay: 3000,
        fallbackPollingInterval: 2000,
        enabled: true
      };

      const { result } = renderHook(() => 
        useDetectionWebSocket(customOptions)
      );

      // Test that options are respected
      act(() => {
        mockWebSocket.onclose({ code: 1006, reason: 'Connection lost' });
      });

      // Should not auto-reconnect when disabled
      act(() => {
        jest.advanceTimersByTime(5000);
      });

      expect(result.current.reconnectAttempts).toBe(0);
    });

    it('should handle custom URLs correctly', () => {
      const customUrl = 'wss://custom.domain.com:9000/ws/detection';
      
      renderHook(() => 
        useDetectionWebSocket({ url: customUrl })
      );

      expect(WebSocket).toHaveBeenCalledWith(customUrl);
    });
  });

  describe('Cleanup & Memory Management', () => {
    it('should clean up all resources on unmount', () => {
      const { unmount } = renderHook(() => 
        useDetectionWebSocket({ 
          autoReconnect: true,
          fallbackPollingInterval: 1000
        })
      );

      // Start fallback polling
      act(() => {
        mockWebSocket.onclose({ code: 1008, reason: 'Auth failed' });
      });

      // Unmount component
      unmount();

      // Verify all resources are cleaned up
      expect(mockWebSocket.close).toHaveBeenCalledWith(1000, 'Manual disconnect');
      
      // Verify no intervals are running after unmount
      act(() => {
        jest.advanceTimersByTime(5000);
      });
    });

    it('should prevent memory leaks from multiple timeouts', () => {
      const { result } = renderHook(() => 
        useDetectionWebSocket({ autoReconnect: true })
      );

      // Trigger multiple quick failures
      for (let i = 0; i < 5; i++) {
        act(() => {
          mockWebSocket.onclose({ code: 1006, reason: 'Connection lost' });
        });
      }

      // Should only create one timeout
      act(() => {
        jest.advanceTimersByTime(5000);
      });

      // Verify only one reconnection attempt
      expect(WebSocket).toHaveBeenCalledTimes(2); // Initial + one reconnect
    });
  });
});