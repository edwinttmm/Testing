import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { useDetectionWebSocket, DetectionUpdate } from '../../ai-model-validation-platform/frontend/src/hooks/useDetectionWebSocket';

describe('useDetectionWebSocket', () => {
  let mockWebSocket: any;
  let originalWebSocket: any;

  beforeEach(() => {
    originalWebSocket = global.WebSocket;
    mockWebSocket = {
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      close: jest.fn(),
      send: jest.fn(),
      readyState: WebSocket.CLOSED
    };

    global.WebSocket = jest.fn(() => mockWebSocket) as any;
    jest.clearAllTimers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
    jest.useRealTimers();
  });

  describe('Connection Management', () => {
    it('should establish WebSocket connection on mount', () => {
      const { result } = renderHook(() => useDetectionWebSocket());

      expect(WebSocket).toHaveBeenCalledWith('ws://localhost:8000/ws/detection');
      expect(mockWebSocket.onopen).toBeDefined();
      expect(mockWebSocket.onmessage).toBeDefined();
      expect(mockWebSocket.onerror).toBeDefined();
      expect(mockWebSocket.onclose).toBeDefined();
    });

    it('should use custom WebSocket URL when provided', () => {
      const customUrl = 'ws://custom.example.com:9000/ws';
      
      const { result } = renderHook(() => 
        useDetectionWebSocket({ url: customUrl })
      );

      expect(WebSocket).toHaveBeenCalledWith(customUrl);
    });

    it('should not create duplicate connections', () => {
      mockWebSocket.readyState = WebSocket.OPEN;
      
      const { result } = renderHook(() => useDetectionWebSocket());

      // Try to connect again
      act(() => {
        result.current.connect();
      });

      expect(WebSocket).toHaveBeenCalledTimes(1);
    });

    it('should call onConnect callback when connection opens', () => {
      const onConnect = jest.fn();
      
      const { result } = renderHook(() => 
        useDetectionWebSocket({ onConnect })
      );

      act(() => {
        mockWebSocket.onopen();
      });

      expect(onConnect).toHaveBeenCalled();
    });

    it('should call onDisconnect callback when connection closes', () => {
      const onDisconnect = jest.fn();
      
      const { result } = renderHook(() => 
        useDetectionWebSocket({ onDisconnect })
      );

      act(() => {
        mockWebSocket.onclose();
      });

      expect(onDisconnect).toHaveBeenCalled();
    });

    it('should call onError callback on connection error', () => {
      const onError = jest.fn();
      const errorEvent = new Error('Connection failed');
      
      const { result } = renderHook(() => 
        useDetectionWebSocket({ onError })
      );

      act(() => {
        mockWebSocket.onerror(errorEvent);
      });

      expect(onError).toHaveBeenCalledWith(errorEvent);
    });

    it('should disconnect WebSocket on unmount', () => {
      const { unmount } = renderHook(() => useDetectionWebSocket());

      unmount();

      expect(mockWebSocket.close).toHaveBeenCalled();
    });
  });

  describe('Message Handling', () => {
    it('should parse and forward valid detection updates', () => {
      const onUpdate = jest.fn();
      const testUpdate: DetectionUpdate = {
        type: 'detection',
        videoId: 'test-video',
        annotation: {
          id: 'test-annotation',
          videoId: 'test-video',
          detectionId: 'det-123',
          frameNumber: 5,
          timestamp: 166.67,
          vruType: 'pedestrian',
          boundingBox: {
            x: 100,
            y: 100,
            width: 50,
            height: 100,
            label: 'person',
            confidence: 0.85
          },
          occluded: false,
          truncated: false,
          difficult: false,
          validated: false,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        }
      };

      renderHook(() => useDetectionWebSocket({ onUpdate }));

      act(() => {
        mockWebSocket.onmessage({
          data: JSON.stringify(testUpdate)
        });
      });

      expect(onUpdate).toHaveBeenCalledWith(testUpdate);
    });

    it('should handle progress updates', () => {
      const onUpdate = jest.fn();
      const progressUpdate: DetectionUpdate = {
        type: 'progress',
        videoId: 'test-video',
        progress: 45
      };

      renderHook(() => useDetectionWebSocket({ onUpdate }));

      act(() => {
        mockWebSocket.onmessage({
          data: JSON.stringify(progressUpdate)
        });
      });

      expect(onUpdate).toHaveBeenCalledWith(progressUpdate);
    });

    it('should handle completion updates', () => {
      const onUpdate = jest.fn();
      const completeUpdate: DetectionUpdate = {
        type: 'complete',
        videoId: 'test-video',
        data: {
          totalDetections: 15,
          processingTime: 2500
        }
      };

      renderHook(() => useDetectionWebSocket({ onUpdate }));

      act(() => {
        mockWebSocket.onmessage({
          data: JSON.stringify(completeUpdate)
        });
      });

      expect(onUpdate).toHaveBeenCalledWith(completeUpdate);
    });

    it('should handle error updates', () => {
      const onUpdate = jest.fn();
      const errorUpdate: DetectionUpdate = {
        type: 'error',
        videoId: 'test-video',
        error: 'Detection pipeline failed: model not found'
      };

      renderHook(() => useDetectionWebSocket({ onUpdate }));

      act(() => {
        mockWebSocket.onmessage({
          data: JSON.stringify(errorUpdate)
        });
      });

      expect(onUpdate).toHaveBeenCalledWith(errorUpdate);
    });

    it('should handle invalid JSON messages gracefully', () => {
      const onUpdate = jest.fn();
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      renderHook(() => useDetectionWebSocket({ onUpdate }));

      act(() => {
        mockWebSocket.onmessage({
          data: 'invalid json data'
        });
      });

      expect(onUpdate).not.toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to parse WebSocket message:', 
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    it('should handle empty messages', () => {
      const onUpdate = jest.fn();

      renderHook(() => useDetectionWebSocket({ onUpdate }));

      act(() => {
        mockWebSocket.onmessage({
          data: ''
        });
      });

      expect(onUpdate).not.toHaveBeenCalled();
    });
  });

  describe('Auto-Reconnection', () => {
    it('should not auto-reconnect by default', () => {
      renderHook(() => useDetectionWebSocket());

      act(() => {
        mockWebSocket.onclose();
      });

      // Fast-forward time
      act(() => {
        jest.advanceTimersByTime(15000);
      });

      expect(WebSocket).toHaveBeenCalledTimes(1);
    });

    it('should auto-reconnect when enabled', () => {
      renderHook(() => 
        useDetectionWebSocket({ autoReconnect: true })
      );

      act(() => {
        mockWebSocket.onclose();
      });

      // Fast-forward to trigger reconnection
      act(() => {
        jest.advanceTimersByTime(10000);
      });

      expect(WebSocket).toHaveBeenCalledTimes(2);
    });

    it('should use custom reconnection delay', () => {
      const customDelay = 5000;
      
      renderHook(() => 
        useDetectionWebSocket({ 
          autoReconnect: true, 
          reconnectDelay: customDelay 
        })
      );

      act(() => {
        mockWebSocket.onclose();
      });

      // Should not reconnect before delay
      act(() => {
        jest.advanceTimersByTime(customDelay - 1000);
      });
      expect(WebSocket).toHaveBeenCalledTimes(1);

      // Should reconnect after delay
      act(() => {
        jest.advanceTimersByTime(1000);
      });
      expect(WebSocket).toHaveBeenCalledTimes(2);
    });

    it('should clear reconnection timeout on manual disconnect', () => {
      const { result } = renderHook(() => 
        useDetectionWebSocket({ autoReconnect: true })
      );

      act(() => {
        mockWebSocket.onclose();
      });

      act(() => {
        result.current.disconnect();
      });

      // Fast-forward past reconnection delay
      act(() => {
        jest.advanceTimersByTime(15000);
      });

      // Should not have attempted reconnection
      expect(WebSocket).toHaveBeenCalledTimes(1);
    });

    it('should not create multiple reconnection timeouts', () => {
      renderHook(() => 
        useDetectionWebSocket({ autoReconnect: true })
      );

      // Trigger multiple close events
      act(() => {
        mockWebSocket.onclose();
        mockWebSocket.onclose();
        mockWebSocket.onclose();
      });

      act(() => {
        jest.advanceTimersByTime(10000);
      });

      // Should only reconnect once
      expect(WebSocket).toHaveBeenCalledTimes(2);
    });
  });

  describe('Message Sending', () => {
    it('should send messages when connected', () => {
      mockWebSocket.readyState = WebSocket.OPEN;
      
      const { result } = renderHook(() => useDetectionWebSocket());
      const testMessage = { type: 'subscribe', videoId: 'test-video' };

      act(() => {
        result.current.sendMessage(testMessage);
      });

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(testMessage));
    });

    it('should not send messages when disconnected', () => {
      mockWebSocket.readyState = WebSocket.CLOSED;
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      const { result } = renderHook(() => useDetectionWebSocket());
      const testMessage = { type: 'subscribe', videoId: 'test-video' };

      act(() => {
        result.current.sendMessage(testMessage);
      });

      expect(mockWebSocket.send).not.toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalledWith('WebSocket is not connected');
      
      consoleSpy.mockRestore();
    });

    it('should handle complex message objects', () => {
      mockWebSocket.readyState = WebSocket.OPEN;
      
      const { result } = renderHook(() => useDetectionWebSocket());
      const complexMessage = {
        type: 'detection_request',
        videoId: 'test-video',
        config: {
          confidenceThreshold: 0.7,
          nmsThreshold: 0.5,
          modelName: 'yolov8n',
          targetClasses: ['person', 'bicycle']
        },
        metadata: {
          timestamp: Date.now(),
          requestId: 'req-123'
        }
      };

      act(() => {
        result.current.sendMessage(complexMessage);
      });

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(complexMessage));
    });
  });

  describe('Connection Status', () => {
    it('should return correct connection status', () => {
      mockWebSocket.readyState = WebSocket.CONNECTING;
      
      const { result } = renderHook(() => useDetectionWebSocket());

      expect(result.current.isConnected).toBe(false);

      mockWebSocket.readyState = WebSocket.OPEN;
      
      // Re-render to get updated status
      const { result: result2 } = renderHook(() => useDetectionWebSocket());
      expect(result2.current.isConnected).toBe(true);
    });

    it('should provide manual connection control', () => {
      const { result } = renderHook(() => useDetectionWebSocket());

      expect(typeof result.current.connect).toBe('function');
      expect(typeof result.current.disconnect).toBe('function');

      act(() => {
        result.current.connect();
      });

      // Should attempt connection (WebSocket constructor called twice - initial + manual)
      expect(WebSocket).toHaveBeenCalledTimes(2);

      act(() => {
        result.current.disconnect();
      });

      expect(mockWebSocket.close).toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('should handle WebSocket constructor errors', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      
      global.WebSocket = jest.fn(() => {
        throw new Error('WebSocket not supported');
      }) as any;

      renderHook(() => useDetectionWebSocket());

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to create WebSocket connection:', 
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    it('should handle network errors gracefully', () => {
      const onError = jest.fn();
      
      renderHook(() => useDetectionWebSocket({ onError }));

      const networkError = new Error('Network unreachable');
      
      act(() => {
        mockWebSocket.onerror(networkError);
      });

      expect(onError).toHaveBeenCalledWith(networkError);
    });

    it('should handle unexpected disconnections', () => {
      const onDisconnect = jest.fn();
      
      renderHook(() => useDetectionWebSocket({ 
        onDisconnect,
        autoReconnect: true 
      }));

      // Simulate unexpected disconnection
      act(() => {
        mockWebSocket.onclose();
      });

      expect(onDisconnect).toHaveBeenCalled();

      // Should attempt to reconnect
      act(() => {
        jest.advanceTimersByTime(10000);
      });

      expect(WebSocket).toHaveBeenCalledTimes(2);
    });
  });

  describe('Environment Variables', () => {
    const originalEnv = process.env;

    afterEach(() => {
      process.env = originalEnv;
    });

    it('should use environment variable for WebSocket URL', () => {
      process.env.REACT_APP_WS_URL = 'ws://env.example.com:8080/ws';
      
      renderHook(() => useDetectionWebSocket());

      expect(WebSocket).toHaveBeenCalledWith('ws://env.example.com:8080/ws');
    });

    it('should fallback to default URL when environment variable is not set', () => {
      delete process.env.REACT_APP_WS_URL;
      
      renderHook(() => useDetectionWebSocket());

      expect(WebSocket).toHaveBeenCalledWith('ws://localhost:8000/ws/detection');
    });
  });
});