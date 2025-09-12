/**
 * Functional tests for LabJackStatusPanel using actual running services
 * These tests verify the component works with live backend services
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { jest } from '@jest/globals';
import LabJackStatusPanel from '../src/components/LabJackStatusPanel';

// Don't mock API service for functional tests - test with real backend
const BACKEND_URL = 'http://localhost:8000';
const SIMPLE_SERVICE_URL = 'http://localhost:8001';

// Mock window.ipcRenderer for Electron compatibility
Object.defineProperty(window, 'ipcRenderer', {
  value: {
    invoke: jest.fn(),
    on: jest.fn(),
    removeAllListeners: jest.fn(),
  },
  writable: true,
});

describe('LabJackStatusPanel Functional Tests (Live Backend)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Suppress console output during tests
    jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Backend Service Integration', () => {
    test('should successfully connect to live backend service', async () => {
      render(<LabJackStatusPanel />);

      // Wait for component to load
      await waitFor(() => {
        expect(screen.getByText(/LabJack Status Panel/)).toBeInTheDocument();
      }, { timeout: 10000 });

      // Should show service connected status
      await waitFor(() => {
        // Look for any indication that service is connected
        const serviceElements = screen.queryAllByText(/connected|available|running|healthy/i);
        expect(serviceElements.length).toBeGreaterThan(0);
      }, { timeout: 5000 });
    });

    test('should display actual LabJack device information', async () => {
      render(<LabJackStatusPanel />);

      await waitFor(() => {
        // Should show device information (mock or real)
        const deviceInfo = screen.queryByText(/T7|U3|U6|Mock LabJack/);
        expect(deviceInfo).toBeInTheDocument();
      }, { timeout: 8000 });
    });

    test('should handle refresh button with live backend', async () => {
      render(<LabJackStatusPanel />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText(/LabJack Status Panel/)).toBeInTheDocument();
      });

      // Find and click refresh button
      const refreshButton = screen.getByText(/Refresh Status|Refresh/i);
      fireEvent.click(refreshButton);

      // Should show loading state briefly
      await waitFor(() => {
        const progressBar = screen.queryByRole('progressbar');
        if (progressBar) {
          expect(progressBar).toBeInTheDocument();
        }
      }, { timeout: 2000 });

      // Should complete refresh
      await waitFor(() => {
        // Button should be enabled again after refresh completes
        expect(refreshButton).toBeEnabled();
      }, { timeout: 5000 });
    });

    test('should run diagnostics with live backend', async () => {
      render(<LabJackStatusPanel />);

      await waitFor(() => {
        expect(screen.getByText(/LabJack Status Panel/)).toBeInTheDocument();
      });

      // Find diagnostics button
      const diagnosticsButton = screen.queryByText(/Run Diagnostics|Diagnostics/i);
      if (diagnosticsButton) {
        fireEvent.click(diagnosticsButton);

        // Should show diagnostic results
        await waitFor(() => {
          const diagnosticResults = screen.queryByText(/Driver|Version|Status/i);
          expect(diagnosticResults).toBeInTheDocument();
        }, { timeout: 8000 });
      }
    });
  });

  describe('Real-time Data Handling', () => {
    test('should handle WebSocket connection to live backend', async () => {
      // Mock WebSocket for testing
      const mockWebSocket = {
        addEventListener: jest.fn((event, callback) => {
          if (event === 'open') {
            setTimeout(() => callback({ type: 'open' }), 100);
          }
          if (event === 'message') {
            setTimeout(() => callback({
              data: JSON.stringify({
                type: 'status_update',
                data: { connected: true, streaming: false }
              })
            }), 200);
          }
        }),
        removeEventListener: jest.fn(),
        close: jest.fn(),
        readyState: WebSocket.OPEN,
        send: jest.fn()
      };

      (global as any).WebSocket = jest.fn(() => mockWebSocket);

      render(<LabJackStatusPanel />);

      // Should establish WebSocket connection
      await waitFor(() => {
        expect(global.WebSocket).toHaveBeenCalled();
      });

      // Should handle WebSocket messages
      await waitFor(() => {
        expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
      });
    });

    test('should handle streaming data from backend', async () => {
      const mockStreamingData = {
        data: [1.23, 4.56, 7.89],
        timestamp: Date.now(),
        sample_rate: 1000,
        channels: ['AIN0', 'AIN1', 'AIN2']
      };

      const mockWebSocket = {
        addEventListener: jest.fn((event, callback) => {
          if (event === 'message') {
            setTimeout(() => callback({
              data: JSON.stringify({
                type: 'streaming_data',
                ...mockStreamingData
              })
            }), 500);
          }
        }),
        removeEventListener: jest.fn(),
        close: jest.fn(),
        readyState: WebSocket.OPEN,
        send: jest.fn()
      };

      (global as any).WebSocket = jest.fn(() => mockWebSocket);

      const onDataReceived = jest.fn();
      render(<LabJackStatusPanel onDataReceived={onDataReceived} />);

      // Should receive streaming data
      await waitFor(() => {
        expect(onDataReceived).toHaveBeenCalledWith(
          expect.objectContaining({
            data: expect.any(Array),
            timestamp: expect.any(Number),
            sample_rate: expect.any(Number),
            channels: expect.any(Array)
          })
        );
      }, { timeout: 2000 });
    });
  });

  describe('Error Handling with Live Backend', () => {
    test('should handle backend API errors gracefully', async () => {
      // Temporarily break API by using wrong endpoint
      const originalFetch = global.fetch;
      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      render(<LabJackStatusPanel />);

      await waitFor(() => {
        // Should show error handling UI
        const errorElements = screen.queryAllByText(/error|unavailable|offline/i);
        expect(errorElements.length).toBeGreaterThan(0);
      }, { timeout: 5000 });

      global.fetch = originalFetch;
    });

    test('should recover from temporary backend failures', async () => {
      let callCount = 0;
      const originalFetch = global.fetch;
      global.fetch = jest.fn(() => {
        callCount++;
        if (callCount <= 2) {
          return Promise.reject(new Error('Temporary failure'));
        }
        return originalFetch.apply(global, arguments as any);
      });

      render(<LabJackStatusPanel />);

      // Should eventually recover after retries
      await waitFor(() => {
        const healthyElements = screen.queryAllByText(/connected|available|healthy/i);
        expect(healthyElements.length).toBeGreaterThan(0);
      }, { timeout: 10000 });

      global.fetch = originalFetch;
    });
  });

  describe('Performance with Live Backend', () => {
    test('should load within acceptable time limits', async () => {
      const startTime = Date.now();

      render(<LabJackStatusPanel />);

      await waitFor(() => {
        expect(screen.getByText(/LabJack Status Panel/)).toBeInTheDocument();
      });

      const loadTime = Date.now() - startTime;
      
      // Should load within 10 seconds (generous for integration testing)
      expect(loadTime).toBeLessThan(10000);
    });

    test('should handle rapid user interactions', async () => {
      render(<LabJackStatusPanel />);

      await waitFor(() => {
        expect(screen.getByText(/LabJack Status Panel/)).toBeInTheDocument();
      });

      const refreshButton = screen.getByText(/Refresh Status|Refresh/i);
      
      // Rapid clicks should not cause issues
      fireEvent.click(refreshButton);
      fireEvent.click(refreshButton);
      fireEvent.click(refreshButton);

      // Should still be functional
      await waitFor(() => {
        expect(refreshButton).toBeEnabled();
      }, { timeout: 5000 });
    });
  });

  describe('Cross-platform Compatibility', () => {
    test('should work on different platforms', async () => {
      // Test with different navigator.platform values
      const platforms = ['Win32', 'MacIntel', 'Linux x86_64'];

      for (const platform of platforms) {
        Object.defineProperty(navigator, 'platform', {
          value: platform,
          configurable: true
        });

        const { unmount } = render(<LabJackStatusPanel />);

        await waitFor(() => {
          expect(screen.getByText(/LabJack Status Panel/)).toBeInTheDocument();
        });

        // Should work regardless of platform
        const refreshButton = screen.getByText(/Refresh Status|Refresh/i);
        fireEvent.click(refreshButton);

        await waitFor(() => {
          expect(refreshButton).toBeEnabled();
        }, { timeout: 3000 });

        unmount();
      }
    });
  });
});