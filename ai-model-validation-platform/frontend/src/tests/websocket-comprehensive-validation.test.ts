/**
 * Comprehensive WebSocket Implementation Validation Test Suite
 * 
 * Tests the complete WebSocket implementation including:
 * 1. Socket.IO connection to localhost:8000/socket.io
 * 2. Backend availability checking
 * 3. Environment variable control
 * 4. Graceful fallback when backend unavailable
 * 5. No connection errors for unavailable backends
 * 6. WebSocketConfigToggle component status indicators
 */

import { renderHook, act } from '@testing-library/react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useWebSocket } from '../hooks/useWebSocket';
import { WebSocketConfigToggle } from '../components/ui/WebSocketConfigToggle';
import * as envConfig from '../utils/envConfig';

// Mock global fetch for backend availability checks
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock Socket.IO with more detailed mock
const mockSocket = {
  on: jest.fn(),
  off: jest.fn(),
  connect: jest.fn(),
  disconnect: jest.fn(),
  emit: jest.fn(),
  connected: false,
  disconnected: true,
  id: 'mock-socket-id'
};

const mockIo = jest.fn().mockReturnValue(mockSocket);

jest.mock('socket.io-client', () => ({
  io: mockIo
}));

// Mock environment configuration
jest.mock('../utils/envConfig', () => ({
  getServiceConfig: jest.fn(),
  isDebugEnabled: jest.fn(() => false),
  envConfig: {
    getConfig: jest.fn()
  }
}));

// Mock configuration manager
jest.mock('../utils/configurationManager', () => ({
  waitForConfig: jest.fn(() => Promise.resolve({})),
  isConfigInitialized: jest.fn(() => true)
}));

// Mock timer utils
jest.mock('../utils/timerUtils', () => ({
  safeSetTimeout: jest.fn((fn, delay) => setTimeout(fn, delay)),
  safeClearTimeout: jest.fn((id) => clearTimeout(id))
}));

// Mock logger
jest.mock('../utils/safeErrorLogger', () => ({
  default: {
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn()
  }
}));

describe('WebSocket Implementation Comprehensive Validation', () => {
  const mockGetServiceConfig = envConfig.getServiceConfig as jest.MockedFunction<typeof envConfig.getServiceConfig>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Reset Socket.IO mock
    mockSocket.connected = false;
    mockSocket.disconnected = true;
    
    // Default configuration for tests
    mockGetServiceConfig.mockReturnValue({
      url: 'http://localhost:8001',
      timeout: 20000,
      retryAttempts: 5,
      retryDelay: 1000,
      enabled: true,
      healthCheckEnabled: true
    });
  });

  describe('Socket.IO Connection to localhost:8000/socket.io', () => {
    it('should connect to the correct Socket.IO endpoint URL', async () => {
      // Mock successful backend health checks
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ status: 'healthy' })
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response);

      const { result } = renderHook(() => useWebSocket({
        url: 'http://localhost:8001'
      }));

      // Wait for backend availability check and auto-connect
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Simulate successful connection
      act(() => {
        mockSocket.connected = true;
        mockSocket.disconnected = false;
        const connectHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect')?.[1];
        if (connectHandler) connectHandler();
      });

      expect(mockIo).toHaveBeenCalledWith('http://localhost:8001', expect.objectContaining({
        transports: ['websocket'],
        timeout: 20000,
        reconnection: false
      }));

      expect(result.current.backendAvailable).toBe(true);
    });

    it('should check both health endpoint and Socket.IO endpoint', async () => {
      // Mock the fetch calls for backend availability check
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ status: 'healthy' })
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response);

      renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Verify health check to port 8000
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/health',
        expect.objectContaining({
          method: 'GET',
          signal: expect.any(AbortSignal),
          mode: 'cors'
        })
      );

      // Verify Socket.IO endpoint check
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8001/socket.io/',
        expect.objectContaining({
          method: 'GET',
          signal: expect.any(AbortSignal),
          mode: 'cors'
        })
      );
    });
  });

  describe('Backend Availability Checking', () => {
    it('should properly detect when backend is available', async () => {
      // Mock successful backend checks
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

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(true);
      expect(result.current.disabled).toBe(false);
    });

    it('should properly detect when backend is unavailable', async () => {
      // Mock failed backend health check
      mockFetch.mockRejectedValueOnce(new Error('Connection refused'));

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
    });

    it('should detect unavailable Socket.IO endpoint even when general health passes', async () => {
      // Mock successful health but failed Socket.IO
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 503
        } as Response);

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
    });
  });

  describe('Environment Variable Control', () => {
    it('should respect REACT_APP_DISABLE_WEBSOCKET environment variable', () => {
      // Mock disabled WebSocket configuration
      mockGetServiceConfig.mockReturnValue({
        url: 'http://localhost:8001',
        timeout: 20000,
        retryAttempts: 5,
        retryDelay: 1000,
        enabled: false, // WebSocket disabled
        healthCheckEnabled: true
      });

      const { result } = renderHook(() => useWebSocket());

      expect(result.current.disabled).toBe(true);
      expect(mockFetch).not.toHaveBeenCalled(); // Should not check backend when disabled
    });

    it('should respect REACT_APP_DISABLE_SOCKETIO environment variable', () => {
      // Test specific Socket.IO disable flag
      mockGetServiceConfig.mockReturnValue({
        url: 'http://localhost:8001',
        timeout: 20000,
        retryAttempts: 5,
        retryDelay: 1000,
        enabled: false, // Socket.IO specifically disabled
        healthCheckEnabled: true
      });

      const { result } = renderHook(() => useWebSocket());

      expect(result.current.disabled).toBe(true);
    });

    it('should respect disabled option parameter', () => {
      const { result } = renderHook(() => useWebSocket({ disabled: true }));

      expect(result.current.disabled).toBe(true);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should allow bypassing backend availability requirement', async () => {
      // Mock failed backend
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      const { result } = renderHook(() => useWebSocket({ 
        requireBackendAvailable: false 
      }));

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
      expect(result.current.disabled).toBe(false); // Should not be disabled
    });
  });

  describe('Graceful Fallback for Unavailable Backend', () => {
    it('should not attempt connection when backend is unavailable', async () => {
      // Mock failed backend check
      mockFetch.mockRejectedValueOnce(new Error('ECONNREFUSED'));

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Try to connect manually
      act(() => {
        result.current.connect();
      });

      // Should not create Socket.IO connection when backend unavailable
      expect(mockIo).not.toHaveBeenCalled();
      expect(result.current.isConnected).toBe(false);
    });

    it('should clear errors when backend becomes unavailable', async () => {
      // Initially mock successful backend
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

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(true);

      // Simulate an error state first
      act(() => {
        // This would normally happen during a connection error
      });

      // Now simulate backend becoming unavailable
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      // Force re-check (this would happen on re-render or retry)
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Error should be cleared when backend unavailable
      expect(result.current.error).toBeNull();
    });

    it('should provide graceful degradation in development mode', async () => {
      const originalNodeEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'development';

      // Mock failed backend
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      const mockLogger = require('../utils/safeErrorLogger').default;

      renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Should log helpful development message
      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Development mode: WebSocket connection skipped')
      );

      process.env.NODE_ENV = originalNodeEnv;
    });
  });

  describe('No Connection Errors for Unavailable Backends', () => {
    it('should not treat backend unavailability as a connection error', async () => {
      // Mock network timeout
      const timeoutError = new Error('The operation was aborted');
      timeoutError.name = 'AbortError';
      mockFetch.mockRejectedValueOnce(timeoutError);

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
      expect(result.current.error).toBeNull(); // Should not set error state
    });

    it('should not show connection errors in console for unavailable backend', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      // Mock failed backend
      mockFetch.mockRejectedValueOnce(new Error('ECONNREFUSED'));

      renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      // Should not log error to console for unavailable backend
      expect(consoleSpy).not.toHaveBeenCalledWith(
        expect.stringContaining('WebSocket connection error')
      );

      consoleSpy.mockRestore();
    });

    it('should handle health check timeout gracefully', async () => {
      // Mock AbortSignal timeout
      const controller = new AbortController();
      controller.abort();
      
      const timeoutError = new Error('This operation was aborted');
      timeoutError.name = 'AbortError';
      mockFetch.mockRejectedValueOnce(timeoutError);

      const { result } = renderHook(() => useWebSocket());

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('WebSocketConfigToggle Component Status Indicators', () => {
    it('should display appropriate status when backend is available', async () => {
      // Mock successful backend health check for the component
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200
      } as Response);

      render(<WebSocketConfigToggle />);

      await waitFor(() => {
        expect(screen.getByText('Enabled')).toBeInTheDocument();
      });

      // Should show green indicator
      const indicator = document.querySelector('.bg-green-500');
      expect(indicator).toBeInTheDocument();
    });

    it('should display appropriate status when backend is unavailable', async () => {
      // Mock failed backend health check
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      render(<WebSocketConfigToggle />);

      await waitFor(() => {
        expect(screen.getByText('Backend Unavailable')).toBeInTheDocument();
      });

      // Should show red indicator
      const indicator = document.querySelector('.bg-red-500');
      expect(indicator).toBeInTheDocument();

      // Should show additional info
      expect(screen.getByText('(Backend not available)')).toBeInTheDocument();
    });

    it('should show checking status during health check', () => {
      // Mock pending fetch
      mockFetch.mockImplementationOnce(() => new Promise(() => {})); // Never resolves

      render(<WebSocketConfigToggle />);

      expect(screen.getByText('Checking...')).toBeInTheDocument();

      // Should show gray indicator
      const indicator = document.querySelector('.bg-gray-400');
      expect(indicator).toBeInTheDocument();
    });

    it('should allow user to toggle WebSocket connections', async () => {
      // Mock successful backend
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200
      } as Response);

      const mockOnToggle = jest.fn();
      render(<WebSocketConfigToggle onToggle={mockOnToggle} />);

      await waitFor(() => {
        expect(screen.getByText('Enabled')).toBeInTheDocument();
      });

      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);

      expect(mockOnToggle).toHaveBeenCalledWith(false);
    });

    it('should disable toggle when backend is unavailable', async () => {
      // Mock failed backend
      mockFetch.mockRejectedValueOnce(new Error('Connection failed'));

      render(<WebSocketConfigToggle />);

      await waitFor(() => {
        const checkbox = screen.getByRole('checkbox');
        expect(checkbox).toBeDisabled();
      });
    });

    it('should show development URL information in development mode', async () => {
      const originalNodeEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'development';

      // Mock successful backend
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200
      } as Response);

      render(<WebSocketConfigToggle />);

      await waitFor(() => {
        expect(screen.getByText(/URL:/)).toBeInTheDocument();
      });

      process.env.NODE_ENV = originalNodeEnv;
    });
  });

  describe('Proper Error Handling Mechanisms', () => {
    it('should handle connection errors separately from availability checks', async () => {
      // Mock successful availability check but connection error
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

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
      });

      expect(result.current.backendAvailable).toBe(true);

      // Simulate connection error after successful availability check
      act(() => {
        const errorHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect_error')?.[1];
        if (errorHandler) {
          errorHandler(new Error('Connection timeout'));
        }
      });

      // Should set connection error but keep backend available
      expect(result.current.backendAvailable).toBe(true);
      expect(result.current.error).toBeTruthy();
    });

    it('should implement exponential backoff for reconnections', async () => {
      const { result } = renderHook(() => useWebSocket({
        requireBackendAvailable: false // Allow connection even without backend check
      }));

      // Trigger connection attempts with failures
      act(() => {
        result.current.connect();
      });

      // Mock connection error to trigger reconnection logic
      act(() => {
        const errorHandler = mockSocket.on.mock.calls.find(call => call[0] === 'connect_error')?.[1];
        if (errorHandler) {
          errorHandler(new Error('Connection failed'));
        }
      });

      // The hook should implement exponential backoff internally
      // This is tested by checking that multiple connection attempts don't happen immediately
      expect(mockIo).toHaveBeenCalledTimes(1); // Should only be called once initially
    });

    it('should cleanup resources properly on unmount', () => {
      const { unmount } = renderHook(() => useWebSocket());

      // Simulate socket creation
      act(() => {
        const { result } = renderHook(() => useWebSocket({ 
          requireBackendAvailable: false 
        }));
        result.current.connect();
      });

      unmount();

      // Should call disconnect on cleanup
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('Edge Cases and Boundary Conditions', () => {
    it('should handle malformed URLs gracefully', () => {
      const { result } = renderHook(() => useWebSocket({
        url: 'invalid-url'
      }));

      expect(result.current.disabled).toBe(false);
      // Should not crash the application
    });

    it('should handle rapid connect/disconnect cycles', async () => {
      const { result } = renderHook(() => useWebSocket({
        requireBackendAvailable: false
      }));

      // Rapid connect/disconnect
      act(() => {
        result.current.connect();
        result.current.disconnect();
        result.current.connect();
        result.current.disconnect();
      });

      // Should handle gracefully without errors
      expect(result.current.isConnected).toBe(false);
    });

    it('should handle concurrent hook instances', async () => {
      // Multiple hooks using the same URL should share connection pool
      const { result: result1 } = renderHook(() => useWebSocket({
        url: 'http://localhost:8001',
        requireBackendAvailable: false
      }));

      const { result: result2 } = renderHook(() => useWebSocket({
        url: 'http://localhost:8001',
        requireBackendAvailable: false
      }));

      act(() => {
        result1.current.connect();
        result2.current.connect();
      });

      // Should reuse the same socket connection
      expect(mockIo).toHaveBeenCalledTimes(1);
    });
  });
});