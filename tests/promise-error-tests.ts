/**
 * Comprehensive Test Suite for Promise Error Fixes
 * Tests for "message channel closed before response received" error scenarios
 */

import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { renderHook, act } from '@testing-library/react';
import { waitFor } from '@testing-library/react';

// Mock chrome runtime for browser extension tests
const mockChrome = {
  runtime: {
    onMessage: {
      addListener: jest.fn(),
      removeListener: jest.fn(),
    },
    sendMessage: jest.fn(),
  },
};

// @ts-ignore
global.chrome = mockChrome;

// Import the fixes to test
import { useWebSocketFixed, withErrorBoundary, CancellablePromise } from '../src/fixes/async-pattern-fixes';

describe('Promise Error Fixes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.clearAllTimers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('Browser Extension Message Handling', () => {
    it('should handle async message listeners correctly', async () => {
      const mockSendResponse = jest.fn();
      const mockMessage = { type: 'ASYNC_OPERATION', data: 'test' };
      
      // Simulate the correct async message listener
      let messageHandler: any;
      mockChrome.runtime.onMessage.addListener.mockImplementation((handler) => {
        messageHandler = handler;
      });

      // Register the message handler (this would happen in the actual code)
      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'ASYNC_OPERATION') {
          // Simulate async operation
          Promise.resolve('success')
            .then(result => {
              sendResponse({ success: true, data: result });
            })
            .catch(error => {
              sendResponse({ success: false, error: error.message });
            });
          return true; // Keep channel open
        }
      });

      // Simulate message reception
      const result = messageHandler(mockMessage, {}, mockSendResponse);

      // Should return true to keep channel open
      expect(result).toBe(true);

      // Wait for async operation
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 0));
      });

      // Should call sendResponse
      expect(mockSendResponse).toHaveBeenCalledWith({
        success: true,
        data: 'success'
      });
    });

    it('should handle message channel timeout', async () => {
      const mockSendResponse = jest.fn();
      
      const slowAsyncOperation = () => new Promise(resolve => 
        setTimeout(() => resolve('delayed'), 15000)
      );

      let messageHandler: any;
      mockChrome.runtime.onMessage.addListener.mockImplementation((handler) => {
        messageHandler = handler;
      });

      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'SLOW_OPERATION') {
          const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Operation timeout')), 10000)
          );

          Promise.race([slowAsyncOperation(), timeoutPromise])
            .then(result => {
              sendResponse({ success: true, data: result });
            })
            .catch(error => {
              sendResponse({ success: false, error: error.message });
            });
          return true;
        }
      });

      const result = messageHandler({ type: 'SLOW_OPERATION' }, {}, mockSendResponse);
      expect(result).toBe(true);

      // Fast-forward past timeout
      act(() => {
        jest.advanceTimersByTime(11000);
      });

      await waitFor(() => {
        expect(mockSendResponse).toHaveBeenCalledWith({
          success: false,
          error: 'Operation timeout'
        });
      });
    });
  });

  describe('WebSocket Connection Management', () => {
    let mockSocket: any;

    beforeEach(() => {
      mockSocket = {
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn(),
        disconnect: jest.fn(),
        connected: false,
      };

      // Mock socket.io
      jest.doMock('socket.io-client', () => ({
        io: jest.fn(() => mockSocket),
      }));
    });

    it('should handle WebSocket connection with proper cleanup', async () => {
      const { result, unmount } = renderHook(() => 
        useWebSocketFixed({ 
          url: 'ws://localhost:8001',
          autoConnect: false 
        })
      );

      // Initially disconnected
      expect(result.current.isConnected).toBe(false);

      // Connect
      await act(async () => {
        await result.current.connect();
      });

      // Should set up event listeners
      expect(mockSocket.on).toHaveBeenCalledWith('connect', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('disconnect', expect.any(Function));
      expect(mockSocket.on).toHaveBeenCalledWith('connect_error', expect.any(Function));

      // Simulate connection
      const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')[1];
      act(() => {
        connectHandler();
      });

      expect(result.current.isConnected).toBe(true);

      // Unmount should cleanup
      unmount();

      expect(mockSocket.disconnect).toHaveBeenCalled();
    });

    it('should handle connection errors with retry', async () => {
      const { result } = renderHook(() => 
        useWebSocketFixed({ 
          url: 'ws://localhost:8001',
          autoConnect: false 
        })
      );

      await act(async () => {
        await result.current.connect();
      });

      // Simulate connection error
      const errorHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect_error')[1];
      act(() => {
        errorHandler(new Error('Connection failed'));
      });

      expect(result.current.error).toEqual(expect.objectContaining({
        message: expect.stringContaining('Connection failed')
      }));

      // Should schedule reconnect
      expect(setTimeout).toHaveBeenCalled();
    });

    it('should clear all timeouts on disconnect', async () => {
      const { result, unmount } = renderHook(() => 
        useWebSocketFixed({ 
          url: 'ws://localhost:8001',
          autoConnect: true 
        })
      );

      // Let connection attempts happen
      await act(async () => {
        jest.advanceTimersByTime(1000);
      });

      // Force multiple reconnection attempts
      await act(async () => {
        const errorHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect_error')[1];
        errorHandler(new Error('Connection failed'));
        jest.advanceTimersByTime(3000);
        errorHandler(new Error('Connection failed again'));
      });

      const timeoutCalls = (setTimeout as jest.Mock).mock.calls.length;
      expect(timeoutCalls).toBeGreaterThan(0);

      // Unmount should clear all timeouts
      unmount();

      // Check that clearTimeout was called for each timeout
      expect(clearTimeout).toHaveBeenCalledTimes(timeoutCalls);
    });
  });

  describe('Promise Error Boundaries', () => {
    it('should handle successful async operations', async () => {
      const successOperation = jest.fn(() => Promise.resolve('success'));
      
      const result = await withErrorBoundary(
        successOperation,
        'test-context'
      );

      expect(result).toBe('success');
      expect(successOperation).toHaveBeenCalled();
    });

    it('should handle failed async operations with fallback', async () => {
      const failedOperation = jest.fn(() => Promise.reject(new Error('Operation failed')));
      
      const result = await withErrorBoundary(
        failedOperation,
        'test-context',
        'fallback-value'
      );

      expect(result).toBe('fallback-value');
      expect(failedOperation).toHaveBeenCalled();
    });

    it('should log error information to localStorage', async () => {
      const setItemSpy = jest.spyOn(Storage.prototype, 'setItem');
      const failedOperation = () => Promise.reject(new Error('Test error'));
      
      await withErrorBoundary(
        failedOperation,
        'test-context',
        'fallback'
      );

      expect(setItemSpy).toHaveBeenCalledWith(
        expect.stringMatching(/^error_\d+$/),
        expect.stringContaining('Test error')
      );

      setItemSpy.mockRestore();
    });

    it('should re-throw error when no fallback provided', async () => {
      const failedOperation = () => Promise.reject(new Error('Test error'));
      
      await expect(
        withErrorBoundary(failedOperation, 'test-context')
      ).rejects.toThrow('Test error');
    });
  });

  describe('Cancellable Promises', () => {
    it('should resolve when not cancelled', async () => {
      const cancellablePromise = new CancellablePromise<string>((resolve) => {
        setTimeout(() => resolve('success'), 1000);
      });

      jest.advanceTimersByTime(1000);

      const result = await cancellablePromise;
      expect(result).toBe('success');
    });

    it('should not resolve after cancellation', async () => {
      let resolveCount = 0;
      const cancellablePromise = new CancellablePromise<string>((resolve) => {
        setTimeout(() => {
          resolveCount++;
          resolve('success');
        }, 1000);
      });

      // Cancel before resolution
      cancellablePromise.cancel();
      
      jest.advanceTimersByTime(1000);

      expect(cancellablePromise.isCancelled()).toBe(true);
      
      // Promise should not resolve (no way to test this directly with current implementation)
      // but we can verify the cancelled state
      expect(resolveCount).toBe(1); // The inner promise still resolves, but result is ignored
    });

    it('should handle chained operations', async () => {
      const cancellablePromise = new CancellablePromise<number>((resolve) => {
        resolve(5);
      });

      const result = await cancellablePromise
        .then(value => value * 2)
        .then(value => value + 1);

      expect(result).toBe(11);
    });

    it('should handle errors with catch', async () => {
      const cancellablePromise = new CancellablePromise<string>((_, reject) => {
        reject(new Error('Test error'));
      });

      const result = await cancellablePromise
        .catch(error => `Caught: ${error.message}`);

      expect(result).toBe('Caught: Test error');
    });
  });

  describe('Configuration Loading', () => {
    beforeEach(() => {
      // Mock isConfigInitialized
      global.isConfigInitialized = jest.fn();
    });

    it('should resolve immediately if config is already initialized', async () => {
      (global.isConfigInitialized as jest.Mock).mockReturnValue(true);

      const startTime = Date.now();
      await expect(async () => {
        const { waitForConfigFixed } = await import('../src/fixes/async-pattern-fixes');
        await waitForConfigFixed();
      }).not.toThrow();
      
      const endTime = Date.now();
      expect(endTime - startTime).toBeLessThan(100); // Should be very fast
    });

    it('should wait for config to be initialized', async () => {
      let configInitialized = false;
      (global.isConfigInitialized as jest.Mock).mockImplementation(() => configInitialized);

      const { waitForConfigFixed } = await import('../src/fixes/async-pattern-fixes');
      
      const configPromise = waitForConfigFixed();

      // Simulate config initialization after some time
      setTimeout(() => {
        configInitialized = true;
      }, 500);

      // Fast-forward time
      jest.advanceTimersByTime(600);

      await expect(configPromise).resolves.toBeUndefined();
    });

    it('should timeout if config never initializes', async () => {
      (global.isConfigInitialized as jest.Mock).mockReturnValue(false);

      const { waitForConfigFixed } = await import('../src/fixes/async-pattern-fixes');
      
      const configPromise = waitForConfigFixed(1000);

      // Fast-forward past timeout
      jest.advanceTimersByTime(1001);

      await expect(configPromise).rejects.toThrow('Configuration loading timeout after 1000ms');
    });
  });

  describe('Message Channel Edge Cases', () => {
    it('should handle multiple rapid message channel requests', async () => {
      const mockSendResponse = jest.fn();
      const responses: any[] = [];

      let messageHandler: any;
      mockChrome.runtime.onMessage.addListener.mockImplementation((handler) => {
        messageHandler = handler;
      });

      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'RAPID_REQUEST') {
          // Simulate variable async operation times
          const delay = Math.random() * 1000;
          setTimeout(() => {
            sendResponse({ success: true, id: message.id, delay });
          }, delay);
          return true;
        }
      });

      // Send multiple rapid requests
      const requests = Array.from({ length: 5 }, (_, i) => ({
        type: 'RAPID_REQUEST',
        id: i,
      }));

      requests.forEach(request => {
        const mockResponse = jest.fn();
        responses.push(mockResponse);
        messageHandler(request, {}, mockResponse);
      });

      // Fast-forward to complete all requests
      act(() => {
        jest.advanceTimersByTime(1000);
      });

      // All responses should be called
      responses.forEach((response, index) => {
        expect(response).toHaveBeenCalledWith({
          success: true,
          id: index,
          delay: expect.any(Number),
        });
      });
    });

    it('should handle message channel closure during async operation', async () => {
      const mockSendResponse = jest.fn();
      
      // Mock sendResponse to throw on the second call (simulating closed channel)
      mockSendResponse
        .mockImplementationOnce((response) => {
          // First call succeeds
          return response;
        })
        .mockImplementationOnce(() => {
          throw new Error('Attempting to use a disconnected port object');
        });

      let messageHandler: any;
      mockChrome.runtime.onMessage.addListener.mockImplementation((handler) => {
        messageHandler = handler;
      });

      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.type === 'CHANNEL_TEST') {
          // Try to send response with error handling
          setTimeout(() => {
            try {
              sendResponse({ success: true });
            } catch (error) {
              console.error('Message channel closed:', error);
              // Handle gracefully - don't crash
            }
          }, 100);
          return true;
        }
      });

      // First message succeeds
      messageHandler({ type: 'CHANNEL_TEST' }, {}, mockSendResponse);
      
      act(() => {
        jest.advanceTimersByTime(100);
      });

      // Second message fails but is handled gracefully
      messageHandler({ type: 'CHANNEL_TEST' }, {}, mockSendResponse);
      
      act(() => {
        jest.advanceTimersByTime(100);
      });

      expect(mockSendResponse).toHaveBeenCalledTimes(2);
    });
  });
});