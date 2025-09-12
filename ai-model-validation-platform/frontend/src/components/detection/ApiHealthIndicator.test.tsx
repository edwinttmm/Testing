import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ApiHealthIndicator from './ApiHealthIndicator';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock AbortSignal.timeout for older environments
if (!global.AbortSignal?.timeout) {
  global.AbortSignal = {
    ...global.AbortSignal,
    timeout: jest.fn(() => new AbortController().signal),
  } as any;
}

describe('ApiHealthIndicator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const mockHealthyResponse = {
    status: 'healthy',
    timestamp: '2023-01-01T00:00:00Z',
    api_version: '1.0.0',
    uptime: 3600,
    labjack: {
      connected: true,
      driver_version: '1.2.3',
      device_info: {
        model: 'T7',
        serial_number: '12345',
        firmware_version: '1.0.1',
      },
      windows_compatible: true,
    },
    frame80_detection: {
      ready: true,
      model_loaded: true,
      confidence_threshold: 0.8,
      last_detection: '2023-01-01T00:00:00Z',
      performance_metrics: {
        avg_inference_time: 50.5,
        fps: 30.0,
      },
    },
    system_info: {
      platform: 'Linux',
      python_version: '3.9.0',
      memory_usage: 45.2,
      cpu_usage: 25.8,
    },
  };

  const mockUnhealthyResponse = {
    ...mockHealthyResponse,
    status: 'unhealthy',
    labjack: {
      connected: false,
      windows_compatible: false,
      error_message: 'Driver not found',
    },
    frame80_detection: {
      ready: false,
      model_loaded: false,
      confidence_threshold: 0.8,
    },
  };

  it('renders loading state initially', () => {
    mockFetch.mockImplementationOnce(() => new Promise(() => {})); // Never resolves
    
    render(<ApiHealthIndicator />);
    
    expect(screen.getByText('Checking API Health...')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('renders healthy status correctly', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealthyResponse,
    });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('API Health Status')).toBeInTheDocument();
    });

    expect(screen.getByText('HEALTHY')).toBeInTheDocument();
    expect(screen.getByText('Connected: Yes')).toBeInTheDocument();
    expect(screen.getByText('Ready: Yes')).toBeInTheDocument();
    expect(screen.getByText('Model Loaded: Yes')).toBeInTheDocument();
    expect(screen.getByText('Windows Compatible: Yes')).toBeInTheDocument();
  });

  it('renders unhealthy status correctly', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUnhealthyResponse,
    });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('UNHEALTHY')).toBeInTheDocument();
    });

    expect(screen.getByText('Connected: No')).toBeInTheDocument();
    expect(screen.getByText('Ready: No')).toBeInTheDocument();
    expect(screen.getByText('Model Loaded: No')).toBeInTheDocument();
    expect(screen.getByText('Windows Compatible: No')).toBeInTheDocument();
    expect(screen.getByText('Driver not found')).toBeInTheDocument();
  });

  it('renders error state when fetch fails', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('Backend Connection Failed')).toBeInTheDocument();
    });

    expect(screen.getByText('Network error')).toBeInTheDocument();
    expect(screen.getByText(/Ensure the backend server is running/)).toBeInTheDocument();
  });

  it('renders error state when response is not ok', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('Backend Connection Failed')).toBeInTheDocument();
    });

    expect(screen.getByText('HTTP 500: Internal Server Error')).toBeInTheDocument();
  });

  it('calls onHealthChange callback when status changes', async () => {
    const onHealthChange = jest.fn();
    
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealthyResponse,
    });

    render(<ApiHealthIndicator onHealthChange={onHealthChange} />);

    await waitFor(() => {
      expect(onHealthChange).toHaveBeenCalledWith('healthy');
    });
  });

  it('refreshes manually when refresh button is clicked', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockHealthyResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockHealthyResponse, uptime: 7200 }),
      });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('3600 seconds')).toBeInTheDocument();
    });

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(screen.getByText('7200 seconds')).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('auto-refreshes at specified interval', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockHealthyResponse,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...mockHealthyResponse, uptime: 7200 }),
      });

    render(<ApiHealthIndicator refreshInterval={5000} />);

    await waitFor(() => {
      expect(screen.getByText('3600 seconds')).toBeInTheDocument();
    });

    // Fast-forward time by 5 seconds
    jest.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(screen.getByText('7200 seconds')).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('shows Windows compatibility warning when not compatible', async () => {
    const windowsIncompatibleResponse = {
      ...mockHealthyResponse,
      status: 'warning',
      labjack: {
        ...mockHealthyResponse.labjack,
        windows_compatible: false,
      },
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => windowsIncompatibleResponse,
    });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText(/Windows Compatibility Issue/)).toBeInTheDocument();
    });

    expect(
      screen.getByText(/LabJack drivers may not be properly installed/)
    ).toBeInTheDocument();
  });

  it('uses custom baseUrl when provided', async () => {
    const customBaseUrl = 'http://custom-server:9000';
    
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealthyResponse,
    });

    render(<ApiHealthIndicator baseUrl={customBaseUrl} />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        `${customBaseUrl}/health`,
        expect.objectContaining({
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        })
      );
    });
  });

  it('displays performance metrics correctly', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealthyResponse,
    });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('Memory Usage: 45.2%')).toBeInTheDocument();
      expect(screen.getByText('CPU Usage: 25.8%')).toBeInTheDocument();
      expect(screen.getByText('Avg Inference: 50.5ms')).toBeInTheDocument();
      expect(screen.getByText('FPS: 30.0')).toBeInTheDocument();
      expect(screen.getByText('Confidence Threshold: 80.0%')).toBeInTheDocument();
    });
  });

  it('displays system information correctly', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealthyResponse,
    });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('Platform: Linux')).toBeInTheDocument();
      expect(screen.getByText('Python: 3.9.0')).toBeInTheDocument();
      expect(screen.getByText('API Version: 1.0.0')).toBeInTheDocument();
      expect(screen.getByText('Uptime: 3600 seconds')).toBeInTheDocument();
    });
  });

  it('displays device information when available', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealthyResponse,
    });

    render(<ApiHealthIndicator />);

    await waitFor(() => {
      expect(screen.getByText('Model: T7')).toBeInTheDocument();
      expect(screen.getByText('Serial: 12345')).toBeInTheDocument();
      expect(screen.getByText('Firmware: 1.0.1')).toBeInTheDocument();
      expect(screen.getByText('Driver Version: 1.2.3')).toBeInTheDocument();
    });
  });
});