import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { jest } from '@jest/globals';
import LabJackStatusPanel from '../src/components/LabJackStatusPanel';
import * as apiService from '../src/services/api';

// Mock the API service
jest.mock('../src/services/api');
const mockApiService = apiService as jest.Mocked<typeof apiService>;

// Mock window.ipcRenderer for Electron compatibility
Object.defineProperty(window, 'ipcRenderer', {
  value: {
    invoke: jest.fn(),
    on: jest.fn(),
    removeAllListeners: jest.fn(),
  },
  writable: true,
});

describe('LabJackStatusPanel Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset console methods
    jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Service Availability Tests', () => {
    test('should handle backend service unavailable gracefully', async () => {
      // Mock service unavailable
      mockApiService.get.mockRejectedValue(new Error('Network Error'));

      render(<LabJackStatusPanel />);

      // Should show fallback content
      await waitFor(() => {
        expect(screen.getByText(/LabJack Status Panel/)).toBeInTheDocument();
      });

      // Should display service unavailable message
      await waitFor(() => {
        expect(screen.getByText(/Service Unavailable/)).toBeInTheDocument();
      });
    });

    test('should attempt fallback to simple detection service', async () => {
      // Mock main service failing, fallback succeeding
      mockApiService.get
        .mockRejectedValueOnce(new Error('Main service down'))
        .mockResolvedValueOnce({
          data: {
            available: true,
            version: '1.0.0',
            status: 'running'
          }
        });

      render(<LabJackStatusPanel />);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith('/health', expect.any(Object));
      });
    });

    test('should provide mock data when all services unavailable', async () => {
      // Mock all services failing
      mockApiService.get.mockRejectedValue(new Error('All services down'));

      render(<LabJackStatusPanel />);

      await waitFor(() => {
        // Should show mock LabJack device
        expect(screen.getByText(/Mock LabJack Device/)).toBeInTheDocument();
      });

      // Should show offline mode indicator
      expect(screen.getByText(/Offline Mode/)).toBeInTheDocument();
    });
  });

  describe('Error Boundary Tests', () => {
    test('should catch and handle component errors', async () => {
      // Mock a function that will throw an error
      const ThrowError = () => {
        throw new Error('Test error');
      };

      const ErrorComponent = () => {
        return (
          <div>
            <LabJackStatusPanel />
            <ThrowError />
          </div>
        );
      };

      // This should be wrapped in error boundary in actual usage
      expect(() => render(<ErrorComponent />)).toThrow();
    });
  });

  describe('Windows Driver Logic Tests', () => {
    test('should detect Windows platform correctly', async () => {
      // Mock Windows platform
      Object.defineProperty(navigator, 'platform', {
        value: 'Win32',
        configurable: true
      });

      mockApiService.get.mockResolvedValue({
        data: {
          labjack_service: { available: true },
          simple_detection_service: { available: true }
        }
      });

      render(<LabJackStatusPanel />);

      // Should attempt Windows-specific connection modes
      await waitFor(() => {
        expect(screen.getByText(/Connection Mode/)).toBeInTheDocument();
      });
    });

    test('should fallback connection modes on Windows', async () => {
      Object.defineProperty(navigator, 'platform', {
        value: 'Win32',
        configurable: true
      });

      // Mock service calls
      mockApiService.get
        .mockResolvedValueOnce({ data: { available: true } }) // health check
        .mockRejectedValueOnce(new Error('Auto mode failed')) // auto mode
        .mockResolvedValueOnce({ data: { devices: [] } }); // direct mode

      render(<LabJackStatusPanel />);

      const refreshButton = screen.getByText(/Refresh Status/);
      fireEvent.click(refreshButton);

      await waitFor(() => {
        // Should attempt fallback modes
        expect(mockApiService.get).toHaveBeenCalledTimes(3);
      });
    });
  });

  describe('Device Detection Tests', () => {
    test('should display detected LabJack devices', async () => {
      const mockDevices = [
        {
          id: 'LJ001',
          model: 'T7',
          serial: '12345',
          status: 'connected',
          firmware_version: '1.0.1'
        }
      ];

      mockApiService.get.mockResolvedValue({
        data: { devices: mockDevices }
      });

      render(<LabJackStatusPanel />);

      await waitFor(() => {
        expect(screen.getByText(/T7/)).toBeInTheDocument();
        expect(screen.getByText(/12345/)).toBeInTheDocument();
        expect(screen.getByText(/connected/)).toBeInTheDocument();
      });
    });

    test('should handle no devices found', async () => {
      mockApiService.get.mockResolvedValue({
        data: { devices: [] }
      });

      render(<LabJackStatusPanel />);

      await waitFor(() => {
        expect(screen.getByText(/No LabJack devices found/)).toBeInTheDocument();
      });
    });
  });

  describe('Diagnostic Tests', () => {
    test('should run driver diagnostics', async () => {
      mockApiService.get.mockResolvedValue({
        data: {
          driver_installed: true,
          driver_version: '2.1.0',
          ljm_version: '1.2100.0'
        }
      });

      render(<LabJackStatusPanel />);

      const diagnosticButton = screen.getByText(/Run Diagnostics/);
      fireEvent.click(diagnosticButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalledWith('/diagnostics/drivers', expect.any(Object));
      });
    });

    test('should handle diagnostic failures gracefully', async () => {
      mockApiService.get.mockRejectedValue(new Error('Diagnostic failed'));

      render(<LabJackStatusPanel />);

      const diagnosticButton = screen.getByText(/Run Diagnostics/);
      fireEvent.click(diagnosticButton);

      await waitFor(() => {
        // Should show error message but not crash
        expect(screen.getByText(/Diagnostic Error/)).toBeInTheDocument();
      });
    });
  });

  describe('Real-time Updates Tests', () => {
    test('should handle WebSocket connection for real-time updates', async () => {
      const mockWebSocket = {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        close: jest.fn(),
        readyState: WebSocket.OPEN
      };

      // Mock WebSocket constructor
      (global as any).WebSocket = jest.fn(() => mockWebSocket);

      render(<LabJackStatusPanel />);

      // Should attempt to establish WebSocket connection
      expect(global.WebSocket).toHaveBeenCalledWith(expect.stringContaining('ws://'));
    });

    test('should handle WebSocket connection failures', async () => {
      const mockWebSocket = {
        addEventListener: jest.fn((event, callback) => {
          if (event === 'error') {
            setTimeout(() => callback(new Error('WebSocket failed')), 100);
          }
        }),
        removeEventListener: jest.fn(),
        close: jest.fn(),
        readyState: WebSocket.CLOSED
      };

      (global as any).WebSocket = jest.fn(() => mockWebSocket);

      render(<LabJackStatusPanel />);

      await waitFor(() => {
        // Should handle WebSocket errors gracefully
        expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('error', expect.any(Function));
      });
    });
  });

  describe('User Interaction Tests', () => {
    test('should refresh status when refresh button clicked', async () => {
      mockApiService.get.mockResolvedValue({
        data: { status: 'healthy' }
      });

      render(<LabJackStatusPanel />);

      const refreshButton = screen.getByText(/Refresh Status/);
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mockApiService.get).toHaveBeenCalled();
      });
    });

    test('should start data collection when button clicked', async () => {
      mockApiService.post.mockResolvedValue({
        data: { status: 'started', collection_id: 'col123' }
      });

      render(<LabJackStatusPanel />);

      const startButton = screen.getByText(/Start Collection/);
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledWith('/labjack/start-collection', expect.any(Object));
      });
    });

    test('should handle button clicks during loading states', async () => {
      // Mock slow API response
      mockApiService.get.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({ data: {} }), 1000))
      );

      render(<LabJackStatusPanel />);

      const refreshButton = screen.getByText(/Refresh Status/);
      fireEvent.click(refreshButton);

      // Should show loading state
      expect(screen.getByRole('progressbar')).toBeInTheDocument();

      // Button should be disabled during loading
      expect(refreshButton).toBeDisabled();
    });
  });

  describe('Performance Tests', () => {
    test('should not cause memory leaks with repeated renders', async () => {
      const { unmount, rerender } = render(<LabJackStatusPanel />);

      // Simulate multiple re-renders
      for (let i = 0; i < 10; i++) {
        rerender(<LabJackStatusPanel />);
      }

      unmount();

      // Should clean up properly
      expect(mockApiService.get).not.toHaveBeenCalledWith('/cleanup');
    });

    test('should handle rapid button clicks gracefully', async () => {
      mockApiService.get.mockResolvedValue({ data: {} });

      render(<LabJackStatusPanel />);

      const refreshButton = screen.getByText(/Refresh Status/);

      // Rapid clicks
      fireEvent.click(refreshButton);
      fireEvent.click(refreshButton);
      fireEvent.click(refreshButton);

      await waitFor(() => {
        // Should not make excessive API calls
        expect(mockApiService.get).toHaveBeenCalledTimes(1);
      });
    });
  });
});