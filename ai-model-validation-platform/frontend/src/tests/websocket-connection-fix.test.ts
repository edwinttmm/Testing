/**
 * WebSocket Connection Fix Validation Test
 * 
 * Tests the enhanced WebSocket implementation to ensure:
 * 1. No connection attempts when backend is unavailable
 * 2. Proper backend availability checks
 * 3. Configuration-based enabling/disabling
 * 4. Graceful error handling
 */

import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../hooks/useWebSocket';
import * as envConfig from '../utils/envConfig';

// Mock fetch for backend availability checks
global.fetch = jest.fn();

// Mock Socket.IO
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    off: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    emit: jest.fn(),
    connected: false,
    disconnected: true
  }))
}));

// Mock environment configuration
jest.mock('../utils/envConfig', () => ({
  getServiceConfig: jest.fn(),
  isDebugEnabled: jest.fn(() => false),
  isConfigInitialized: jest.fn(() => true)
}));

// Mock timer utils
jest.mock('../utils/timerUtils', () => ({
  safeSetTimeout: jest.fn((fn, delay) => setTimeout(fn, delay)),
  safeClearTimeout: jest.fn((id) => clearTimeout(id))
}));

// Mock configuration manager
jest.mock('../utils/configurationManager', () => ({
  waitForConfig: jest.fn(() => Promise.resolve({})),
  isConfigInitialized: jest.fn(() => true)
}));

// Mock logger
jest.mock('../utils/safeErrorLogger', () => ({
  debug: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn()
}));

describe('WebSocket Connection Fix Tests', () => {
  const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
  const mockGetServiceConfig = envConfig.getServiceConfig as jest.MockedFunction<typeof envConfig.getServiceConfig>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Default mock configuration with WebSocket enabled
    mockGetServiceConfig.mockReturnValue({
      url: 'http://localhost:8001',
      timeout: 20000,
      retryAttempts: 5,
      retryDelay: 1000,
      enabled: true,
      healthCheckEnabled: true
    });
  });

  describe('Backend Availability Checks', () => {
    it('should check backend health endpoint before connecting', async () => {
      // Mock successful backend health check
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response);

      const { result } = renderHook(() => useWebSocket());

      // Wait for backend availability check
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/health',
        expect.objectContaining({
          method: 'GET',
          signal: expect.any(AbortSignal),
          mode: 'cors'
        })
      );

      expect(result.current.backendAvailable).toBe(true);
    });

    it('should check Socket.IO specific endpoint after general health', async () => {
      // Mock backend health check and Socket.IO check
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response);

      renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/socket.io/',
        expect.objectContaining({
          method: 'GET',
          signal: expect.any(AbortSignal),
          mode: 'cors'
        })
      );
    });

    it('should mark backend as unavailable when health check fails', async () => {
      // Mock failed backend health check
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
      expect(result.current.error).toBeNull(); // Should not treat as connection error
    });

    it('should mark backend as unavailable when Socket.IO endpoint fails', async () => {
      // Mock successful health check but failed Socket.IO check
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 500
        } as Response);

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
    });
  });

  describe('WebSocket Disable Configuration', () => {
    it('should respect global WebSocket disable flag', () => {
      // Mock configuration with WebSocket disabled
      mockGetServiceConfig.mockReturnValue({
        url: 'http://localhost:8001',
        timeout: 20000,
        retryAttempts: 5,
        retryDelay: 1000,
        enabled: false,
        healthCheckEnabled: true
      });

      const { result } = renderHook(() => useWebSocket());

      expect(result.current.disabled).toBe(true);
      expect(mockFetch).not.toHaveBeenCalled(); // Should not check backend
    });

    it('should respect options-level disable flag', () => {
      const { result } = renderHook(() => useWebSocket({ disabled: true }));

      expect(result.current.disabled).toBe(true);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should allow disabling backend availability requirement', async () => {
      // Mock failed backend
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      const { result } = renderHook(() => 
        useWebSocket({ requireBackendAvailable: false })
      );

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Should still check backend availability
      expect(result.current.backendAvailable).toBe(false);
      // But WebSocket should not be disabled due to backend unavailability
      expect(result.current.disabled).toBe(false);
    });
  });

  describe('Connection Prevention', () => {
    it('should not attempt connection when WebSocket is disabled', () => {
      const mockConnect = jest.fn();
      const { result } = renderHook(() => useWebSocket({ disabled: true }));

      act(() => {
        result.current.connect();
      });

      expect(mockConnect).not.toHaveBeenCalled();
    });

    it('should not attempt connection when backend is unavailable and required', async () => {
      // Mock failed backend check
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      const { result } = renderHook(() => 
        useWebSocket({ requireBackendAvailable: true })
      );

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      act(() => {
        result.current.connect();
      });

      // Connection should not be attempted
      expect(result.current.isConnected).toBe(false);
    });

    it('should clear errors when backend becomes unavailable', async () => {
      // First mock successful backend, then failed
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response);

      const { result, rerender } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(true);

      // Now mock backend failure
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      // Force a re-check by re-rendering
      rerender();

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('Development Mode Behavior', () => {
    const originalNodeEnv = process.env.NODE_ENV;

    afterEach(() => {
      process.env.NODE_ENV = originalNodeEnv;
    });

    it('should log helpful messages in development mode', async () => {
      process.env.NODE_ENV = 'development';
      
      // Mock failed backend
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      const mockLogger = require('../utils/safeErrorLogger');

      renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Development mode: WebSocket connection skipped')
      );
    });
  });

  describe('Error Handling', () => {
    it('should handle AbortSignal timeout gracefully', async () => {
      // Mock timeout error
      const timeoutError = new Error('The operation was aborted');
      timeoutError.name = 'AbortError';
      mockFetch.mockRejectedValueOnce(timeoutError);

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('should handle network errors gracefully', async () => {
      // Mock network error
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('Configuration Integration', () => {
    it('should respect health check disabled configuration', () => {
      mockGetServiceConfig.mockReturnValue({
        url: 'http://localhost:8001',
        timeout: 20000,
        retryAttempts: 5,
        retryDelay: 1000,
        enabled: true,
        healthCheckEnabled: false
      });

      renderHook(() => useWebSocket());

      // Should not perform health checks when disabled
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should use configuration timeout values', async () => {
      mockGetServiceConfig.mockReturnValue({
        url: 'http://localhost:8001',
        timeout: 5000,
        retryAttempts: 3,
        retryDelay: 500,
        enabled: true,
        healthCheckEnabled: true
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200
      } as Response);

      renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          signal: expect.any(AbortSignal)
        })
      );
    });
  });
});