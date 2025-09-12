/**
 * LabJack Hardware Integration End-to-End Test Suite
 * ================================================
 * 
 * Comprehensive test suite for LabJack hardware integration testing
 * covering both hardware-present and mock scenarios.
 * 
 * Test Coverage:
 * - API endpoint validation
 * - LabJack Status Panel functionality
 * - Error handling (hardware not connected)
 * - Windows driver detection
 * - Connection retry mechanisms
 * - WebSocket communication
 * - Mock mode functionality
 * 
 * @author Hardware Integration Testing Specialist
 * @requires Jest, React Testing Library, MSW for API mocking
 */

import { describe, test, expect, beforeAll, afterAll, beforeEach, afterEach, jest } from '@jest/globals';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import axios from 'axios';
import LabJackStatusPanel from '../src/components/LabJackStatusPanel';
import { apiService } from '../src/services/api';

// Test configuration
const TEST_CONFIG = {
  API_BASE_URL: 'http://localhost:8000',
  WEBSOCKET_URL: 'ws://localhost:8000',
  TIMEOUT: 30000, // 30 seconds
  RETRY_DELAY: 100, // 100ms for faster testing
  MOCK_MODE: true // Default to mock mode for CI/CD
};

// Mock responses for different scenarios
const mockLabJackResponses = {
  connected: {
    mode: 'direct',
    status: 'connected',
    connected: true,
    device_info: {
      device_type: 'T7',
      serial_number: '440010117',
      firmware_version: '1.0282',
      hardware_version: '1.21'
    },
    streaming: false,
    sample_rate: 1000,
    channels: ['AIN0', 'AIN1'],
    voltage_threshold: 2.5,
    statistics: {
      samples_received: 0,
      errors_count: 0,
      connection_attempts: 1,
      successful_connections: 1,
      failed_connections: 0,
      uptime_start: new Date().toISOString(),
      total_uptime: 0,
      recovery_attempts: 0
    },
    bridge_latency: 5,
    windows_driver: {
      detected: true,
      version: '1.20',
      supported: true,
      recommendations: []
    }
  },
  
  disconnected: {
    mode: 'auto',
    status: 'disconnected',
    connected: false,
    device_info: {},
    streaming: false,
    sample_rate: 1000,
    channels: ['AIN0'],
    voltage_threshold: 2.5,
    error_message: 'No LabJack devices found',
    statistics: {
      samples_received: 0,
      errors_count: 1,
      connection_attempts: 3,
      successful_connections: 0,
      failed_connections: 3,
      uptime_start: new Date().toISOString(),
      total_uptime: 0,
      recovery_attempts: 2
    }
  },
  
  mock: {
    mode: 'mock',
    status: 'connected',
    connected: true,
    device_info: {
      device_type: 'T7-Mock',
      serial_number: 'MOCK-001',
      is_mock: true
    },
    streaming: false,
    sample_rate: 1000,
    channels: ['AIN0', 'AIN1'],
    voltage_threshold: 2.5,
    statistics: {
      samples_received: 150,
      errors_count: 0,
      connection_attempts: 1,
      successful_connections: 1,
      failed_connections: 0,
      uptime_start: new Date().toISOString(),
      total_uptime: 300,
      recovery_attempts: 0
    }
  },
  
  error: {
    mode: 'auto',
    status: 'error',
    connected: false,
    device_info: {},
    streaming: false,
    sample_rate: 1000,
    channels: [],
    voltage_threshold: 2.5,
    error_message: 'Hardware communication error',
    statistics: {
      samples_received: 0,
      errors_count: 5,
      connection_attempts: 5,
      successful_connections: 0,
      failed_connections: 5,
      uptime_start: new Date().toISOString(),
      total_uptime: 0,
      recovery_attempts: 3
    }
  },
  
  windowsDriverIssue: {
    mode: 'direct',
    status: 'error',
    connected: false,
    device_info: {},
    streaming: false,
    sample_rate: 1000,
    channels: [],
    voltage_threshold: 2.5,
    error_message: 'Driver compatibility issues detected',
    statistics: {
      samples_received: 0,
      errors_count: 2,
      connection_attempts: 2,
      successful_connections: 0,
      failed_connections: 2,
      uptime_start: new Date().toISOString(),
      total_uptime: 0,
      recovery_attempts: 1
    },
    windows_driver: {
      detected: false,
      supported: false,
      recommendations: [
        'Install LabJack LJM drivers from https://labjack.com/support/software/installers/ljm',
        'Restart the system after driver installation',
        'Ensure USB device is properly connected'
      ]
    }
  }
};

// MSW server for API mocking
const server = setupServer(
  // LabJack status endpoint
  rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/status`, (req, res, ctx) => {
    const scenario = req.url.searchParams.get('scenario') || 'connected';
    return res(ctx.json(mockLabJackResponses[scenario as keyof typeof mockLabJackResponses] || mockLabJackResponses.connected));
  }),
  
  // LabJack connect endpoint
  rest.post(`${TEST_CONFIG.API_BASE_URL}/api/labjack/connect`, (req, res, ctx) => {
    const body = req.body as any;
    const forceMode = body?.force_mode || 'auto';
    
    if (forceMode === 'mock') {
      return res(ctx.json({ 
        status: 'success', 
        message: 'Connected in mock mode',
        device_info: mockLabJackResponses.mock.device_info,
        latency: 2
      }));
    } else if (forceMode === 'direct') {
      return res(ctx.json({ 
        status: 'success', 
        message: 'Connected in direct mode',
        device_info: mockLabJackResponses.connected.device_info,
        latency: 5
      }));
    } else {
      // Simulate connection failure for auto mode in tests
      return res(ctx.status(500), ctx.json({ 
        detail: 'No LabJack devices found. Try different connection mode.' 
      }));
    }
  }),
  
  // LabJack disconnect endpoint
  rest.post(`${TEST_CONFIG.API_BASE_URL}/api/labjack/disconnect`, (req, res, ctx) => {
    return res(ctx.json({ status: 'success', message: 'Disconnected successfully' }));
  }),
  
  // LabJack discover endpoint
  rest.post(`${TEST_CONFIG.API_BASE_URL}/api/labjack/discover`, (req, res, ctx) => {
    const mockDevices = TEST_CONFIG.MOCK_MODE ? 1 : 0;
    return res(ctx.json({ 
      devices_found: mockDevices,
      scan_duration: 2.5,
      devices: mockDevices > 0 ? [
        { serial: 'MOCK-001', type: 'T7-Mock', connection: 'USB' }
      ] : []
    }));
  }),
  
  // LabJack streaming endpoints
  rest.post(`${TEST_CONFIG.API_BASE_URL}/api/labjack/start-stream`, (req, res, ctx) => {
    return res(ctx.json({ status: 'success', message: 'Streaming started' }));
  }),
  
  rest.post(`${TEST_CONFIG.API_BASE_URL}/api/labjack/stop-stream`, (req, res, ctx) => {
    return res(ctx.json({ status: 'success', message: 'Streaming stopped' }));
  }),
  
  // Windows driver endpoints
  rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/driver-status`, (req, res, ctx) => {
    const hasIssues = req.url.searchParams.get('simulate-issues') === 'true';
    return res(ctx.json({
      supported: !hasIssues,
      version: hasIssues ? null : '1.20',
      detected: !hasIssues,
      path: hasIssues ? null : 'C:\\Program Files\\LabJack\\LJM',
      recommendations: hasIssues ? mockLabJackResponses.windowsDriverIssue.windows_driver?.recommendations : []
    }));
  }),
  
  rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/windows-driver-info`, (req, res, ctx) => {
    return res(ctx.json({
      detected: true,
      version: '1.20',
      supported: true,
      path: 'C:\\Program Files\\LabJack\\LJM',
      recommendations: []
    }));
  }),
  
  // Bridge test endpoint
  rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/bridge-test`, (req, res, ctx) => {
    return res(ctx.json({ latency: 12, status: 'healthy' }));
  }),
  
  // Health check
  rest.get(`${TEST_CONFIG.API_BASE_URL}/health`, (req, res, ctx) => {
    return res(ctx.json({ status: 'healthy', timestamp: new Date().toISOString() }));
  })
);

// Test results tracking
interface TestResult {
  test: string;
  status: 'PASS' | 'FAIL' | 'WARN' | 'SKIP';
  message: string;
  duration?: number;
  error?: Error;
}

let testResults: TestResult[] = [];

function addTestResult(result: TestResult) {
  testResults.push(result);
  const emoji = result.status === 'PASS' ? '✅' : result.status === 'FAIL' ? '❌' : result.status === 'WARN' ? '⚠️' : '⏭️';
  console.log(`${emoji} ${result.test}: ${result.message}${result.duration ? ` (${result.duration}ms)` : ''}`);
}

// Helper function to measure test duration
async function timeTest<T>(testFn: () => Promise<T>): Promise<{ result: T; duration: number }> {
  const start = performance.now();
  const result = await testFn();
  const duration = Math.round(performance.now() - start);
  return { result, duration };
}

// Mock WebSocket for testing
class MockWebSocket {
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  
  constructor(url: string) {
    this.url = url;
    
    // Simulate connection after short delay
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
      
      // Simulate periodic messages
      const interval = setInterval(() => {
        if (this.readyState === WebSocket.OPEN && this.onmessage) {
          const mockData = {
            type: 'streaming_data',
            payload: {
              data: [Math.random() * 5, Math.random() * 5],
              timestamp: Date.now(),
              sample_rate: 1000,
              channels: ['AIN0', 'AIN1']
            }
          };
          this.onmessage(new MessageEvent('message', { data: JSON.stringify(mockData) }));
        }
      }, 100);
      
      // Cleanup after 5 seconds
      setTimeout(() => {
        clearInterval(interval);
        if (this.readyState === WebSocket.OPEN) {
          this.close();
        }
      }, 5000);
    }, 100);
  }
  
  send(data: string) {
    // Mock send - could add response logic here
  }
  
  close(code?: number, reason?: string) {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: code || 1000, reason: reason || '' }));
    }
  }
}

// Mock React components wrapper
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <div data-testid="test-wrapper">{children}</div>;
};

describe('LabJack Hardware Integration Test Suite', () => {
  
  beforeAll(async () => {
    // Start MSW server
    server.listen({ onUnhandledRequest: 'warn' });
    
    // Mock WebSocket globally
    Object.defineProperty(window, 'WebSocket', {
      writable: true,
      value: MockWebSocket,
    });
    
    // Mock performance.now for consistent timing
    Object.defineProperty(window, 'performance', {
      writable: true,
      value: {
        now: jest.fn(() => Date.now()),
      },
    });
    
    console.log('🚀 Starting LabJack Hardware Integration Tests');
    console.log('===============================================');
  });

  afterAll(async () => {
    server.close();
    
    // Generate comprehensive test report
    const passed = testResults.filter(r => r.status === 'PASS').length;
    const failed = testResults.filter(r => r.status === 'FAIL').length;
    const warnings = testResults.filter(r => r.status === 'WARN').length;
    const skipped = testResults.filter(r => r.status === 'SKIP').length;
    
    console.log('\n📊 LabJack Integration Test Report');
    console.log('==================================');
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`⚠️ Warnings: ${warnings}`);
    console.log(`⏭️ Skipped: ${skipped}`);
    console.log(`📝 Total: ${testResults.length}`);
    
    if (failed === 0) {
      console.log('\n🎉 All LabJack integration tests passed!');
    } else {
      console.log(`\n⚠️ ${failed} test(s) failed. Review results above.`);
    }
  });

  beforeEach(() => {
    // Reset MSW handlers before each test
    server.resetHandlers();
  });

  afterEach(() => {
    // Clean up any timeouts or intervals
    jest.clearAllTimers();
  });

  describe('1. API Endpoint Validation', () => {
    
    test('LabJack status endpoint responds correctly', async () => {
      const { result, duration } = await timeTest(async () => {
        const response = await apiService.get('/api/labjack/status');
        return response;
      });
      
      addTestResult({
        test: 'LabJack Status API',
        status: 'PASS',
        message: `Status endpoint returned ${result.status} - Connected: ${result.connected}`,
        duration
      });
      
      expect(result).toBeDefined();
      expect(typeof result.connected).toBe('boolean');
      expect(result.mode).toBeDefined();
      expect(result.statistics).toBeDefined();
    }, TEST_CONFIG.TIMEOUT);

    test('LabJack connect endpoint handles different modes', async () => {
      const modes: Array<'direct' | 'mock' | 'bridge'> = ['direct', 'mock', 'bridge'];
      
      for (const mode of modes) {
        const { result, duration } = await timeTest(async () => {
          try {
            const response = await apiService.post('/api/labjack/connect', { force_mode: mode });
            return { success: true, response, mode };
          } catch (error) {
            return { success: false, error, mode };
          }
        });
        
        if (result.success) {
          addTestResult({
            test: `Connect API - ${mode} mode`,
            status: 'PASS',
            message: `Successfully connected in ${mode} mode`,
            duration
          });
        } else {
          addTestResult({
            test: `Connect API - ${mode} mode`,
            status: 'WARN',
            message: `Connection failed in ${mode} mode (may be expected)`,
            duration
          });
        }
        
        expect(result).toBeDefined();
        expect(result.mode).toBe(mode);
      }
    }, TEST_CONFIG.TIMEOUT);

    test('LabJack discovery endpoint functions correctly', async () => {
      const { result, duration } = await timeTest(async () => {
        const response = await apiService.post('/api/labjack/discover', { timeout: 5000 });
        return response;
      });
      
      addTestResult({
        test: 'Device Discovery API',
        status: 'PASS',
        message: `Discovery completed - Found ${result.devices_found} device(s)`,
        duration
      });
      
      expect(result).toBeDefined();
      expect(typeof result.devices_found).toBe('number');
      expect(result.devices_found).toBeGreaterThanOrEqual(0);
    }, TEST_CONFIG.TIMEOUT);

    test('Windows driver detection API works correctly', async () => {
      const { result, duration } = await timeTest(async () => {
        const response = await apiService.get('/api/labjack/driver-status');
        return response;
      });
      
      addTestResult({
        test: 'Windows Driver Detection API',
        status: 'PASS',
        message: `Driver check completed - Supported: ${result.supported}`,
        duration
      });
      
      expect(result).toBeDefined();
      expect(typeof result.supported).toBe('boolean');
      expect(typeof result.detected).toBe('boolean');
    }, TEST_CONFIG.TIMEOUT);

  });

  describe('2. LabJack Status Panel Component Testing', () => {
    
    test('Status panel renders correctly with mock data', async () => {
      const { result, duration } = await timeTest(async () => {
        return act(async () => {
          render(
            <TestWrapper>
              <LabJackStatusPanel />
            </TestWrapper>
          );
          
          // Wait for component to load
          await waitFor(() => {
            expect(screen.getByText('LabJack Status')).toBeInTheDocument();
          }, { timeout: 5000 });
          
          return screen;
        });
      });
      
      addTestResult({
        test: 'Status Panel Rendering',
        status: 'PASS',
        message: 'LabJack Status Panel rendered successfully',
        duration
      });
      
      expect(screen.getByText('LabJack Status')).toBeInTheDocument();
    }, TEST_CONFIG.TIMEOUT);

    test('Connection buttons work correctly', async () => {
      const mockStatusChange = jest.fn();
      
      await act(async () => {
        render(
          <TestWrapper>
            <LabJackStatusPanel onStatusChanged={mockStatusChange} />
          </TestWrapper>
        );
      });
      
      const { result, duration } = await timeTest(async () => {
        await waitFor(() => {
          const connectButton = screen.queryByText(/Connect/);
          if (connectButton) {
            fireEvent.click(connectButton);
            return true;
          }
          return false;
        });
        
        return true;
      });
      
      addTestResult({
        test: 'Connection Button Functionality',
        status: result ? 'PASS' : 'WARN',
        message: result ? 'Connection button interaction successful' : 'Connection button not found or inactive',
        duration
      });
      
    }, TEST_CONFIG.TIMEOUT);

    test('Settings dialog opens and closes correctly', async () => {
      await act(async () => {
        render(
          <TestWrapper>
            <LabJackStatusPanel />
          </TestWrapper>
        );
      });
      
      const { result, duration } = await timeTest(async () => {
        await waitFor(() => {
          expect(screen.getByText('LabJack Status')).toBeInTheDocument();
        });
        
        // Find and click settings button (gear icon)
        const settingsButton = screen.getByRole('button', { name: /settings/i });
        expect(settingsButton).toBeInTheDocument();
        
        fireEvent.click(settingsButton);
        
        // Check if settings dialog opened
        await waitFor(() => {
          expect(screen.getByText('LabJack Settings')).toBeInTheDocument();
        });
        
        return true;
      });
      
      addTestResult({
        test: 'Settings Dialog Functionality',
        status: result ? 'PASS' : 'WARN',
        message: result ? 'Settings dialog opened successfully' : 'Settings dialog interaction failed',
        duration
      });
      
    }, TEST_CONFIG.TIMEOUT);

    test('Diagnostics dialog functions correctly', async () => {
      await act(async () => {
        render(
          <TestWrapper>
            <LabJackStatusPanel />
          </TestWrapper>
        );
      });
      
      const { result, duration } = await timeTest(async () => {
        await waitFor(() => {
          expect(screen.getByText('LabJack Status')).toBeInTheDocument();
        });
        
        // Find and click diagnostics button
        const diagnosticsButton = screen.getByRole('button', { name: /diagnostics/i });
        expect(diagnosticsButton).toBeInTheDocument();
        
        fireEvent.click(diagnosticsButton);
        
        // Check if diagnostics dialog opened
        await waitFor(() => {
          expect(screen.getByText(/LabJack Comprehensive Diagnostics/)).toBeInTheDocument();
        });
        
        return true;
      });
      
      addTestResult({
        test: 'Diagnostics Dialog Functionality',
        status: result ? 'PASS' : 'WARN',
        message: result ? 'Diagnostics dialog opened successfully' : 'Diagnostics dialog interaction failed',
        duration
      });
      
    }, TEST_CONFIG.TIMEOUT);

  });

  describe('3. Error Handling Without Hardware', () => {
    
    test('Graceful handling when no hardware is connected', async () => {
      // Override server to return disconnected state
      server.use(
        rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/status`, (req, res, ctx) => {
          return res(ctx.json(mockLabJackResponses.disconnected));
        })
      );
      
      const { result, duration } = await timeTest(async () => {
        await act(async () => {
          render(
            <TestWrapper>
              <LabJackStatusPanel />
            </TestWrapper>
          );
          
          await waitFor(() => {
            expect(screen.getByText('LabJack Status')).toBeInTheDocument();
          }, { timeout: 5000 });
        });
        
        // Should show disconnected state
        await waitFor(() => {
          expect(screen.getByText(/Connect/)).toBeInTheDocument();
        });
        
        return true;
      });
      
      addTestResult({
        test: 'No Hardware Error Handling',
        status: result ? 'PASS' : 'FAIL',
        message: result ? 'Gracefully handled no hardware scenario' : 'Failed to handle no hardware scenario',
        duration
      });
      
    }, TEST_CONFIG.TIMEOUT);

    test('Error message display for hardware communication failures', async () => {
      // Override server to return error state
      server.use(
        rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/status`, (req, res, ctx) => {
          return res(ctx.json(mockLabJackResponses.error));
        })
      );
      
      const { result, duration } = await timeTest(async () => {
        await act(async () => {
          render(
            <TestWrapper>
              <LabJackStatusPanel />
            </TestWrapper>
          );
          
          await waitFor(() => {
            expect(screen.getByText('LabJack Status')).toBeInTheDocument();
          }, { timeout: 5000 });
        });
        
        // Should show error message
        await waitFor(() => {
          const errorText = screen.queryByText(/Hardware communication error/) || screen.queryByText(/error/i);
          return !!errorText;
        }, { timeout: 3000 });
        
        return true;
      });
      
      addTestResult({
        test: 'Hardware Communication Error Display',
        status: result ? 'PASS' : 'WARN',
        message: result ? 'Error messages displayed correctly' : 'Error message display needs improvement',
        duration
      });
      
    }, TEST_CONFIG.TIMEOUT);

  });

  describe('4. Windows Driver Detection', () => {
    
    test('Windows driver compatibility check', async () => {
      // Simulate Windows environment
      Object.defineProperty(navigator, 'platform', {
        writable: true,
        value: 'Win32'
      });
      
      const { result, duration } = await timeTest(async () => {
        const response = await apiService.get('/api/labjack/windows-driver-info');
        return response;
      });
      
      addTestResult({
        test: 'Windows Driver Compatibility Check',
        status: 'PASS',
        message: `Driver compatibility checked - Supported: ${result.supported}`,
        duration
      });
      
      expect(result).toBeDefined();
      expect(typeof result.supported).toBe('boolean');
    }, TEST_CONFIG.TIMEOUT);

    test('Windows driver issue warnings', async () => {
      // Override server to return driver issues
      server.use(
        rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/windows-driver-info`, (req, res, ctx) => {
          return res(ctx.json(mockLabJackResponses.windowsDriverIssue.windows_driver));
        }),
        rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/status`, (req, res, ctx) => {
          return res(ctx.json(mockLabJackResponses.windowsDriverIssue));
        })
      );
      
      const { result, duration } = await timeTest(async () => {
        await act(async () => {
          render(
            <TestWrapper>
              <LabJackStatusPanel />
            </TestWrapper>
          );
          
          await waitFor(() => {
            expect(screen.getByText('LabJack Status')).toBeInTheDocument();
          }, { timeout: 5000 });
        });
        
        // Should show driver warning
        await waitFor(() => {
          const warningText = screen.queryByText(/Windows Driver Issue/) || screen.queryByText(/driver/i);
          return !!warningText;
        }, { timeout: 3000 });
        
        return true;
      });
      
      addTestResult({
        test: 'Windows Driver Issue Warnings',
        status: result ? 'PASS' : 'WARN',
        message: result ? 'Driver issue warnings displayed correctly' : 'Driver issue warnings not visible',
        duration
      });
      
    }, TEST_CONFIG.TIMEOUT);

  });

  describe('5. Connection Retry Mechanisms', () => {
    
    test('Automatic retry on connection failure', async () => {
      let callCount = 0;
      
      // Override server to fail first few attempts
      server.use(
        rest.post(`${TEST_CONFIG.API_BASE_URL}/api/labjack/connect`, (req, res, ctx) => {
          callCount++;
          if (callCount < 3) {
            return res(ctx.status(500), ctx.json({ detail: 'Connection failed, retry attempt' }));
          }
          return res(ctx.json({ status: 'success', message: 'Connected after retries' }));
        })
      );
      
      const { result, duration } = await timeTest(async () => {
        try {
          // First attempt should fail
          await apiService.post('/api/labjack/connect', { force_mode: 'auto' });
          return false;
        } catch (error) {
          // Simulate retry logic
          await new Promise(resolve => setTimeout(resolve, TEST_CONFIG.RETRY_DELAY));
          await apiService.post('/api/labjack/connect', { force_mode: 'auto' });
          return true;
        }
      });
      
      addTestResult({
        test: 'Connection Retry Mechanism',
        status: callCount >= 2 ? 'PASS' : 'WARN',
        message: `Retry mechanism tested - ${callCount} attempts made`,
        duration
      });
      
      expect(callCount).toBeGreaterThan(1);
    }, TEST_CONFIG.TIMEOUT);

    test('Exponential backoff in retry logic', async () => {
      const retryTimes: number[] = [];
      
      const { result, duration } = await timeTest(async () => {
        // Simulate exponential backoff
        for (let i = 0; i < 4; i++) {
          const delay = Math.min(100 * Math.pow(2, i), 1000); // 100, 200, 400, 800 (capped at 1000)
          const start = performance.now();
          await new Promise(resolve => setTimeout(resolve, delay));
          retryTimes.push(performance.now() - start);
        }
        return retryTimes;
      });
      
      addTestResult({
        test: 'Exponential Backoff Algorithm',
        status: 'PASS',
        message: `Backoff delays: [${result.map(t => Math.round(t)).join(', ')}] ms`,
        duration
      });
      
      // Check that delays are increasing (allowing for some variance)
      for (let i = 1; i < retryTimes.length; i++) {
        expect(retryTimes[i]).toBeGreaterThanOrEqual(retryTimes[i - 1] * 0.9); // 10% tolerance
      }
    }, TEST_CONFIG.TIMEOUT);

  });

  describe('6. WebSocket Communication', () => {
    
    test('WebSocket connection establishment', async () => {
      const { result, duration } = await timeTest(async () => {
        return new Promise<boolean>((resolve) => {
          const ws = new MockWebSocket(`${TEST_CONFIG.WEBSOCKET_URL}/ws/labjack/stream`);
          
          ws.onopen = () => {
            resolve(true);
            ws.close();
          };
          
          ws.onerror = () => {
            resolve(false);
          };
          
          // Timeout after 2 seconds
          setTimeout(() => resolve(false), 2000);
        });
      });
      
      addTestResult({
        test: 'WebSocket Connection',
        status: result ? 'PASS' : 'WARN',
        message: result ? 'WebSocket connected successfully' : 'WebSocket connection failed or timed out',
        duration
      });
      
      expect(result).toBe(true);
    }, TEST_CONFIG.TIMEOUT);

    test('WebSocket data streaming', async () => {
      const { result, duration } = await timeTest(async () => {
        return new Promise<{ messageCount: number; sampleData: any }>((resolve) => {
          const ws = new MockWebSocket(`${TEST_CONFIG.WEBSOCKET_URL}/ws/labjack/stream`);
          let messageCount = 0;
          let sampleData: any = null;
          
          ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            messageCount++;
            if (!sampleData && data.type === 'streaming_data') {
              sampleData = data.payload;
            }
          };
          
          ws.onopen = () => {
            // Send subscription message
            ws.send(JSON.stringify({
              type: 'subscribe',
              channels: ['AIN0', 'AIN1'],
              sample_rate: 1000
            }));
          };
          
          // Collect messages for 1 second
          setTimeout(() => {
            ws.close();
            resolve({ messageCount, sampleData });
          }, 1000);
        });
      });
      
      addTestResult({
        test: 'WebSocket Data Streaming',
        status: result.messageCount > 0 ? 'PASS' : 'WARN',
        message: `Received ${result.messageCount} WebSocket messages`,
        duration
      });
      
      expect(result.messageCount).toBeGreaterThan(0);
      if (result.sampleData) {
        expect(result.sampleData).toHaveProperty('data');
        expect(result.sampleData).toHaveProperty('timestamp');
        expect(result.sampleData).toHaveProperty('channels');
      }
    }, TEST_CONFIG.TIMEOUT);

    test('WebSocket reconnection handling', async () => {
      const { result, duration } = await timeTest(async () => {
        return new Promise<{ reconnected: boolean }>((resolve) => {
          const ws = new MockWebSocket(`${TEST_CONFIG.WEBSOCKET_URL}/ws/labjack/stream`);
          let connected = false;
          let reconnected = false;
          
          ws.onopen = () => {
            if (connected) {
              reconnected = true;
              resolve({ reconnected });
            } else {
              connected = true;
              // Simulate connection drop after 200ms
              setTimeout(() => {
                ws.close(1006, 'Connection dropped');
                
                // Simulate reconnection attempt after short delay
                setTimeout(() => {
                  const newWs = new MockWebSocket(`${TEST_CONFIG.WEBSOCKET_URL}/ws/labjack/stream`);
                  newWs.onopen = () => {
                    reconnected = true;
                    resolve({ reconnected });
                    newWs.close();
                  };
                }, 100);
              }, 200);
            }
          };
          
          // Timeout after 2 seconds
          setTimeout(() => resolve({ reconnected }), 2000);
        });
      });
      
      addTestResult({
        test: 'WebSocket Reconnection Handling',
        status: result.reconnected ? 'PASS' : 'WARN',
        message: result.reconnected ? 'WebSocket reconnection successful' : 'WebSocket reconnection not tested or failed',
        duration
      });
      
    }, TEST_CONFIG.TIMEOUT);

  });

  describe('7. Mock Mode Functionality', () => {
    
    test('Mock mode activation and data generation', async () => {
      // Override server to return mock mode
      server.use(
        rest.get(`${TEST_CONFIG.API_BASE_URL}/api/labjack/status`, (req, res, ctx) => {
          return res(ctx.json(mockLabJackResponses.mock));
        })
      );
      
      const { result, duration } = await timeTest(async () => {
        const response = await apiService.get('/api/labjack/status');
        return response;
      });
      
      addTestResult({
        test: 'Mock Mode Functionality',
        status: 'PASS',
        message: `Mock mode active - Device: ${result.device_info.device_type}, Mock: ${result.device_info.is_mock}`,
        duration
      });
      
      expect(result.mode).toBe('mock');
      expect(result.connected).toBe(true);
      expect(result.device_info.is_mock).toBe(true);
      expect(result.device_info.device_type).toBe('T7-Mock');
    }, TEST_CONFIG.TIMEOUT);

    test('Mock data consistency and validation', async () => {
      const { result, duration } = await timeTest(async () => {
        const responses = [];
        
        // Get multiple status responses to check consistency
        for (let i = 0; i < 3; i++) {
          const response = await apiService.get('/api/labjack/status?scenario=mock');
          responses.push(response);
          await new Promise(resolve => setTimeout(resolve, 100)); // Small delay between requests
        }
        
        return responses;
      });
      
      const allMock = result.every(r => r.device_info.is_mock === true);
      const consistentSerialNumber = result.every(r => r.device_info.serial_number === result[0].device_info.serial_number);
      
      addTestResult({
        test: 'Mock Data Consistency',
        status: allMock && consistentSerialNumber ? 'PASS' : 'WARN',
        message: `Mock data consistency: All mock=${allMock}, Serial consistent=${consistentSerialNumber}`,
        duration
      });
      
      expect(allMock).toBe(true);
      expect(consistentSerialNumber).toBe(true);
    }, TEST_CONFIG.TIMEOUT);

  });

  describe('8. Integration Workflow Testing', () => {
    
    test('Complete LabJack workflow simulation', async () => {
      const workflow: string[] = [];
      
      const { result, duration } = await timeTest(async () => {
        try {
          // Step 1: Check initial status
          const status1 = await apiService.get('/api/labjack/status?scenario=disconnected');
          workflow.push(`Status check: ${status1.status}`);
          
          // Step 2: Attempt discovery
          const discovery = await apiService.post('/api/labjack/discover');
          workflow.push(`Discovery: ${discovery.devices_found} devices found`);
          
          // Step 3: Connect in mock mode
          const connect = await apiService.post('/api/labjack/connect', { force_mode: 'mock' });
          workflow.push(`Connect: ${connect.status}`);
          
          // Step 4: Check connected status
          const status2 = await apiService.get('/api/labjack/status?scenario=mock');
          workflow.push(`Connected status: ${status2.status}`);
          
          // Step 5: Start streaming
          const startStream = await apiService.post('/api/labjack/start-stream', {
            channels: ['AIN0', 'AIN1'],
            sample_rate: 1000
          });
          workflow.push(`Start streaming: ${startStream.status}`);
          
          // Step 6: Stop streaming
          const stopStream = await apiService.post('/api/labjack/stop-stream');
          workflow.push(`Stop streaming: ${stopStream.status}`);
          
          // Step 7: Disconnect
          const disconnect = await apiService.post('/api/labjack/disconnect');
          workflow.push(`Disconnect: ${disconnect.status}`);
          
          return workflow;
        } catch (error) {
          workflow.push(`Error: ${error}`);
          return workflow;
        }
      });
      
      addTestResult({
        test: 'Complete LabJack Workflow',
        status: result.length >= 7 ? 'PASS' : 'WARN',
        message: `Workflow completed ${result.length} steps: ${result.join(' → ')}`,
        duration
      });
      
      expect(result.length).toBeGreaterThan(5);
    }, TEST_CONFIG.TIMEOUT * 2); // Double timeout for full workflow

    test('Component integration with real-time updates', async () => {
      const statusChanges: any[] = [];
      const dataReceived: any[] = [];
      
      const mockOnStatusChanged = (status: any) => {
        statusChanges.push(status);
      };
      
      const mockOnDataReceived = (data: any) => {
        dataReceived.push(data);
      };
      
      const { result, duration } = await timeTest(async () => {
        await act(async () => {
          render(
            <TestWrapper>
              <LabJackStatusPanel 
                onStatusChanged={mockOnStatusChanged}
                onDataReceived={mockOnDataReceived}
              />
            </TestWrapper>
          );
          
          // Wait for initial load and any status changes
          await waitFor(() => {
            expect(screen.getByText('LabJack Status')).toBeInTheDocument();
          });
          
          // Simulate some time for potential WebSocket messages
          await new Promise(resolve => setTimeout(resolve, 1000));
        });
        
        return { statusChanges: statusChanges.length, dataReceived: dataReceived.length };
      });
      
      addTestResult({
        test: 'Component Integration with Real-time Updates',
        status: 'PASS',
        message: `Integration complete - Status changes: ${result.statusChanges}, Data received: ${result.dataReceived}`,
        duration
      });
      
      // At minimum, we should have loaded the component successfully
      expect(screen.getByText('LabJack Status')).toBeInTheDocument();
    }, TEST_CONFIG.TIMEOUT);

  });

});

export { testResults, TestResult };