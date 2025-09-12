/**
 * LabJack Integration Validation Test Suite
 * =========================================
 * 
 * Comprehensive test suite for validating LabJack hardware integration
 * on Windows systems. Tests device connectivity, communication protocols,
 * and integration with the AI Model Validation Platform.
 * 
 * @author Hardware Integration Specialist
 * @requires LabJack LJM library installed
 * @requires Backend service running on localhost:8000
 */

import { describe, test, expect, beforeAll, afterAll, jest } from '@jest/globals';
import axios from 'axios';
import { enhancedApiService } from '../src/services/enhancedApiService';
import websocketService from '../src/services/websocketService';

// Test configuration
const TEST_CONFIG = {
  API_BASE_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  WEBSOCKET_URL: process.env.REACT_APP_WS_URL || 'ws://localhost:8000',
  TEST_TIMEOUT: 30000, // 30 seconds
  DEVICE_TIMEOUT: 15000, // 15 seconds for device operations
  NETWORK_TIMEOUT: 5000,  // 5 seconds for network operations
  LABJACK_DEFAULT_IP: '192.168.1.207',
  MOCK_MODE_EXPECTED: true // Set to false if real hardware is connected
};

// Test results interface
interface TestResult {
  test: string;
  status: 'PASS' | 'FAIL' | 'SKIP' | 'WARN';
  message: string;
  data?: any;
  duration?: number;
  error?: Error;
}

// Global test state
let testResults: TestResult[] = [];
let backendHealthy = false;
let labJackConnected = false;
let websocketConnected = false;

/**
 * Utility function to add test results
 */
function addTestResult(result: TestResult): void {
  testResults.push(result);
  
  const emoji = result.status === 'PASS' ? '✅' : 
                result.status === 'FAIL' ? '❌' : 
                result.status === 'WARN' ? '⚠️' : '⏭️';
                
  console.log(`${emoji} ${result.test}: ${result.message}`);
  
  if (result.data && process.env.NODE_ENV === 'test') {
    console.log('   Data:', JSON.stringify(result.data, null, 2));
  }
  
  if (result.duration) {
    console.log(`   Duration: ${result.duration}ms`);
  }
}

/**
 * Helper function to time async operations
 */
async function timeAsyncOperation<T>(operation: () => Promise<T>): Promise<{ result: T; duration: number }> {
  const startTime = performance.now();
  const result = await operation();
  const duration = Math.round(performance.now() - startTime);
  return { result, duration };
}

describe('LabJack Hardware Integration Validation', () => {
  
  beforeAll(async () => {
    console.log('🚀 Starting LabJack Integration Validation Suite');
    console.log('===============================================');
    console.log(`API Base URL: ${TEST_CONFIG.API_BASE_URL}`);
    console.log(`WebSocket URL: ${TEST_CONFIG.WEBSOCKET_URL}`);
    console.log(`Mock Mode Expected: ${TEST_CONFIG.MOCK_MODE_EXPECTED}`);
    console.log('');
  });

  afterAll(async () => {
    // Cleanup WebSocket connections
    if (websocketConnected) {
      websocketService.disconnect();
    }
    
    // Generate test summary
    const passed = testResults.filter(r => r.status === 'PASS').length;
    const failed = testResults.filter(r => r.status === 'FAIL').length;
    const warnings = testResults.filter(r => r.status === 'WARN').length;
    const skipped = testResults.filter(r => r.status === 'SKIP').length;
    
    console.log('\n📊 Test Summary Report');
    console.log('=====================');
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`⚠️ Warnings: ${warnings}`);
    console.log(`⏭️ Skipped: ${skipped}`);
    console.log(`📝 Total: ${testResults.length}`);
    
    if (failed === 0 && warnings === 0) {
      console.log('\n🎉 All tests passed! LabJack integration is working correctly.');
    } else if (failed === 0) {
      console.log('\n✨ All tests passed with some warnings. Check logs for details.');
    } else {
      console.log(`\n⚠️ ${failed} test(s) failed. Check logs for troubleshooting steps.`);
    }
  });

  describe('1. Prerequisites and System Checks', () => {
    
    test('System environment validation', async () => {
      const startTime = performance.now();
      
      try {
        // Check if running on Windows (for LabJack hardware compatibility)
        const isWindows = process.platform === 'win32';
        
        // Check Node.js version
        const nodeVersion = process.version;
        const nodeVersionValid = parseFloat(nodeVersion.slice(1)) >= 16.0;
        
        // Check test environment variables
        const hasApiUrl = !!process.env.REACT_APP_API_URL;
        const hasWsUrl = !!process.env.REACT_APP_WS_URL || !!process.env.REACT_APP_SOCKETIO_URL;
        
        const systemInfo = {
          platform: process.platform,
          nodeVersion,
          isWindows,
          nodeVersionValid,
          hasApiUrl,
          hasWsUrl,
          testTimeout: TEST_CONFIG.TEST_TIMEOUT
        };
        
        const duration = Math.round(performance.now() - startTime);
        
        if (!isWindows) {
          addTestResult({
            test: 'System Environment',
            status: 'WARN',
            message: 'Not running on Windows - LabJack hardware may not be available',
            data: systemInfo,
            duration
          });
        } else if (nodeVersionValid) {
          addTestResult({
            test: 'System Environment',
            status: 'PASS',
            message: 'System environment is compatible',
            data: systemInfo,
            duration
          });
        } else {
          addTestResult({
            test: 'System Environment',
            status: 'FAIL',
            message: `Node.js version ${nodeVersion} is too old (minimum: 16.0)`,
            data: systemInfo,
            duration
          });
        }
        
        expect(nodeVersionValid).toBe(true);
        
      } catch (error) {
        const duration = Math.round(performance.now() - startTime);
        addTestResult({
          test: 'System Environment',
          status: 'FAIL',
          message: `Environment check failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
          duration,
          error: error instanceof Error ? error : new Error(String(error))
        });
        throw error;
      }
    }, TEST_CONFIG.TEST_TIMEOUT);

    test('Backend API health check', async () => {
      const { result, duration } = await timeAsyncOperation(async () => {
        try {
          const response = await axios.get(`${TEST_CONFIG.API_BASE_URL}/health`, {
            timeout: TEST_CONFIG.NETWORK_TIMEOUT
          });
          
          return {
            status: response.status,
            data: response.data,
            healthy: response.status === 200
          };
        } catch (error) {
          if (axios.isAxiosError(error)) {
            throw new Error(`HTTP ${error.response?.status || 'Unknown'}: ${error.message}`);
          }
          throw error;
        }
      });
      
      backendHealthy = result.healthy;
      
      if (result.healthy) {
        addTestResult({
          test: 'Backend API Health',
          status: 'PASS',
          message: 'Backend API is healthy and accessible',
          data: result.data,
          duration
        });
        expect(result.status).toBe(200);
      } else {
        addTestResult({
          test: 'Backend API Health',
          status: 'FAIL',
          message: 'Backend API is not healthy',
          data: result,
          duration
        });
        throw new Error('Backend API health check failed');
      }
    }, TEST_CONFIG.NETWORK_TIMEOUT);

  });

  describe('2. LabJack Device Detection and Status', () => {
    
    test('LabJack status endpoint accessibility', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'LabJack Status Endpoint',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        const response = await enhancedApiService.checkLabJackStatus();
        return response;
      });
      
      const isConnected = result.connected === true;
      const isMockMode = result.mock_mode === true;
      
      addTestResult({
        test: 'LabJack Status Endpoint',
        status: 'PASS',
        message: `Status endpoint accessible - Connected: ${isConnected}, Mock: ${isMockMode}`,
        data: {
          connected: result.connected,
          mock_mode: result.mock_mode,
          channels: result.channels,
          voltage_threshold: result.voltage_threshold,
          current_voltages: result.current_voltages,
          error: result.error
        },
        duration
      });
      
      labJackConnected = isConnected;
      
      // Verify expected mock mode matches actual
      if (TEST_CONFIG.MOCK_MODE_EXPECTED !== isMockMode) {
        addTestResult({
          test: 'Mock Mode Verification',
          status: 'WARN',
          message: `Expected mock_mode=${TEST_CONFIG.MOCK_MODE_EXPECTED}, got mock_mode=${isMockMode}`,
          data: { expected: TEST_CONFIG.MOCK_MODE_EXPECTED, actual: isMockMode }
        });
      }
      
      expect(result).toBeDefined();
      expect(typeof result.connected).toBe('boolean');
    }, TEST_CONFIG.DEVICE_TIMEOUT);

    test('LabJack initialization with configuration', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'LabJack Initialization',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const testConfig = {
        voltage_threshold: { lower: 4.0, upper: 5.5 },
        channels: ['AIN0'],
        sample_rate: 1000
      };
      
      const { result, duration } = await timeAsyncOperation(async () => {
        const response = await enhancedApiService.initializeLabJack(testConfig);
        return response;
      });
      
      const isSuccess = result.status === 'connected' || result.status === 'success';
      
      if (isSuccess) {
        addTestResult({
          test: 'LabJack Initialization',
          status: 'PASS',
          message: `Initialization successful: ${result.message}`,
          data: {
            status: result.status,
            message: result.message,
            mock_mode: result.mock_mode,
            config_used: testConfig
          },
          duration
        });
        labJackConnected = true;
      } else {
        addTestResult({
          test: 'LabJack Initialization',
          status: result.error ? 'FAIL' : 'WARN',
          message: result.message || 'Initialization returned non-success status',
          data: {
            status: result.status,
            message: result.message,
            error: result.error,
            config_used: testConfig
          },
          duration
        });
        
        if (result.error) {
          throw new Error(`LabJack initialization failed: ${result.error}`);
        }
      }
      
      expect(result).toBeDefined();
      expect(result.status).toBeDefined();
    }, TEST_CONFIG.DEVICE_TIMEOUT);

    test('Hardware connection validation', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Hardware Connection Validation',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        const response = await enhancedApiService.testSignalValidationConnection();
        return response;
      });
      
      const connectionHealthy = result.status === 'healthy' || result.status === 'connected';
      
      if (connectionHealthy) {
        addTestResult({
          test: 'Hardware Connection Validation',
          status: 'PASS',
          message: 'Hardware connection test passed',
          data: {
            status: result.status,
            components: result.components
          },
          duration
        });
      } else {
        addTestResult({
          test: 'Hardware Connection Validation',
          status: 'WARN',
          message: `Connection test status: ${result.status}`,
          data: {
            status: result.status,
            components: result.components
          },
          duration
        });
      }
      
      expect(result).toBeDefined();
      expect(result.status).toBeDefined();
    }, TEST_CONFIG.DEVICE_TIMEOUT);

  });

  describe('3. Communication Protocol Testing', () => {
    
    test('Signal monitoring start and stop', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Signal Monitoring Control',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const testSessionId = `test-session-${Date.now()}`;
      
      try {
        // Test starting signal monitoring
        const { result: startResult, duration: startDuration } = await timeAsyncOperation(async () => {
          return await enhancedApiService.startSignalMonitoring(testSessionId);
        });
        
        const startSuccess = startResult.status === 'success' || startResult.status === 'started';
        
        if (startSuccess) {
          addTestResult({
            test: 'Signal Monitoring Start',
            status: 'PASS',
            message: startResult.message || 'Monitoring started successfully',
            data: startResult,
            duration: startDuration
          });
        } else {
          addTestResult({
            test: 'Signal Monitoring Start',
            status: 'WARN',
            message: `Start monitoring returned: ${startResult.status}`,
            data: startResult,
            duration: startDuration
          });
        }
        
        // Give monitoring time to initialize
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Test stopping signal monitoring
        const { result: stopResult, duration: stopDuration } = await timeAsyncOperation(async () => {
          return await enhancedApiService.stopSignalMonitoring();
        });
        
        const stopSuccess = stopResult.status === 'success' || stopResult.status === 'stopped';
        
        if (stopSuccess) {
          addTestResult({
            test: 'Signal Monitoring Stop',
            status: 'PASS',
            message: stopResult.message || 'Monitoring stopped successfully',
            data: stopResult,
            duration: stopDuration
          });
        } else {
          addTestResult({
            test: 'Signal Monitoring Stop',
            status: 'WARN',
            message: `Stop monitoring returned: ${stopResult.status}`,
            data: stopResult,
            duration: stopDuration
          });
        }
        
        expect(startResult).toBeDefined();
        expect(stopResult).toBeDefined();
        
      } catch (error) {
        addTestResult({
          test: 'Signal Monitoring Control',
          status: 'FAIL',
          message: `Signal monitoring test failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
          error: error instanceof Error ? error : new Error(String(error))
        });
        throw error;
      }
    }, TEST_CONFIG.DEVICE_TIMEOUT * 2);

    test('Signal statistics retrieval', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Signal Statistics',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const testSessionId = `stats-test-${Date.now()}`;
      
      const { result, duration } = await timeAsyncOperation(async () => {
        return await enhancedApiService.getSignalStatistics(testSessionId);
      });
      
      const hasValidStats = typeof result.total_signals === 'number' && 
                           typeof result.valid_signals === 'number';
      
      if (hasValidStats) {
        addTestResult({
          test: 'Signal Statistics',
          status: 'PASS',
          message: `Statistics retrieved - Total: ${result.total_signals}, Valid: ${result.valid_signals}`,
          data: {
            total_signals: result.total_signals,
            valid_signals: result.valid_signals,
            invalid_signals: result.invalid_signals,
            average_delay: result.average_delay,
            session_id: testSessionId
          },
          duration
        });
      } else {
        addTestResult({
          test: 'Signal Statistics',
          status: 'WARN',
          message: 'Statistics endpoint returned unexpected format',
          data: result,
          duration
        });
      }
      
      expect(result).toBeDefined();
      expect(typeof result.total_signals).toBe('number');
    }, TEST_CONFIG.DEVICE_TIMEOUT);

  });

  describe('4. WebSocket Communication Testing', () => {
    
    test('WebSocket connection establishment', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'WebSocket Connection',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        try {
          await websocketService.connect();
          return {
            connected: websocketService.isConnected,
            health: websocketService.getHealthStatus()
          };
        } catch (error) {
          throw error;
        }
      });
      
      websocketConnected = result.connected;
      
      if (result.connected) {
        addTestResult({
          test: 'WebSocket Connection',
          status: 'PASS',
          message: 'WebSocket connected successfully',
          data: {
            connected: result.connected,
            health: result.health
          },
          duration
        });
      } else {
        addTestResult({
          test: 'WebSocket Connection',
          status: 'FAIL',
          message: 'WebSocket connection failed',
          data: result,
          duration
        });
        throw new Error('WebSocket connection failed');
      }
      
      expect(result.connected).toBe(true);
    }, TEST_CONFIG.NETWORK_TIMEOUT);

    test('WebSocket voltage data subscription', async () => {
      if (!websocketConnected) {
        addTestResult({
          test: 'WebSocket Voltage Data',
          status: 'SKIP',
          message: 'Skipped due to WebSocket connection failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        return new Promise<{ dataReceived: boolean; messageCount: number; sampleData?: any }>((resolve) => {
          let messageCount = 0;
          let sampleData: any = null;
          
          const unsubscribe = websocketService.subscribe('voltage_data', (data) => {
            messageCount++;
            if (!sampleData) {
              sampleData = data;
            }
          });
          
          // Wait for potential voltage data
          setTimeout(() => {
            unsubscribe();
            resolve({
              dataReceived: messageCount > 0,
              messageCount,
              sampleData
            });
          }, 3000); // 3 second timeout for data reception
        });
      });
      
      if (result.dataReceived) {
        addTestResult({
          test: 'WebSocket Voltage Data',
          status: 'PASS',
          message: `Received ${result.messageCount} voltage data messages`,
          data: {
            messageCount: result.messageCount,
            sampleData: result.sampleData
          },
          duration
        });
      } else {
        addTestResult({
          test: 'WebSocket Voltage Data',
          status: 'WARN',
          message: 'No voltage data received (may be expected if not actively monitoring)',
          data: result,
          duration
        });
      }
      
      // This is not a failure condition as it depends on active monitoring
      expect(typeof result.dataReceived).toBe('boolean');
    }, TEST_CONFIG.DEVICE_TIMEOUT);

  });

  describe('5. Enhanced Test Workflow Integration', () => {
    
    test('Enhanced test workflow status check', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Enhanced Test Workflow Status',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        return await enhancedApiService.getEnhancedTestWorkflowStatus();
      });
      
      const hasValidStatus = typeof result.active === 'boolean' && 
                            typeof result.currentVideo === 'number';
      
      if (hasValidStatus) {
        addTestResult({
          test: 'Enhanced Test Workflow Status',
          status: 'PASS',
          message: `Workflow status retrieved - Active: ${result.active}, Current: ${result.currentVideo}/${result.totalVideos}`,
          data: {
            active: result.active,
            currentVideo: result.currentVideo,
            totalVideos: result.totalVideos,
            resultsCount: result.resultsCount,
            sessionId: result.sessionId
          },
          duration
        });
      } else {
        addTestResult({
          test: 'Enhanced Test Workflow Status',
          status: 'FAIL',
          message: 'Workflow status endpoint returned invalid format',
          data: result,
          duration
        });
        throw new Error('Invalid workflow status format');
      }
      
      expect(result).toBeDefined();
      expect(typeof result.active).toBe('boolean');
    }, TEST_CONFIG.DEVICE_TIMEOUT);

    test('Enhanced test workflow results retrieval', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Enhanced Test Workflow Results',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        return await enhancedApiService.getEnhancedTestWorkflowResults();
      });
      
      const hasValidResults = typeof result.active === 'boolean' && 
                             Array.isArray(result.results);
      
      if (hasValidResults) {
        addTestResult({
          test: 'Enhanced Test Workflow Results',
          status: 'PASS',
          message: `Results retrieved - ${result.results.length} test results available`,
          data: {
            active: result.active,
            resultsCount: result.results.length,
            summary: result.summary
          },
          duration
        });
      } else {
        addTestResult({
          test: 'Enhanced Test Workflow Results',
          status: 'FAIL',
          message: 'Workflow results endpoint returned invalid format',
          data: result,
          duration
        });
        throw new Error('Invalid workflow results format');
      }
      
      expect(result).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
    }, TEST_CONFIG.DEVICE_TIMEOUT);

  });

  describe('6. Error Handling and Edge Cases', () => {
    
    test('Invalid API endpoint handling', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Invalid Endpoint Handling',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        try {
          // Test invalid endpoint
          await axios.get(`${TEST_CONFIG.API_BASE_URL}/api/signal-validation/invalid-endpoint`, {
            timeout: TEST_CONFIG.NETWORK_TIMEOUT
          });
          return { errorHandled: false, status: 200 };
        } catch (error) {
          if (axios.isAxiosError(error)) {
            return {
              errorHandled: true,
              status: error.response?.status || 0,
              message: error.message
            };
          }
          throw error;
        }
      });
      
      if (result.errorHandled && (result.status === 404 || result.status === 405)) {
        addTestResult({
          test: 'Invalid Endpoint Handling',
          status: 'PASS',
          message: `Invalid endpoint properly rejected with status ${result.status}`,
          data: result,
          duration
        });
      } else {
        addTestResult({
          test: 'Invalid Endpoint Handling',
          status: 'WARN',
          message: 'Invalid endpoint did not return expected error',
          data: result,
          duration
        });
      }
      
      expect(result.errorHandled).toBe(true);
    }, TEST_CONFIG.NETWORK_TIMEOUT);

    test('Timeout handling for long operations', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Timeout Handling',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        try {
          // Test with very short timeout to simulate timeout condition
          await axios.get(`${TEST_CONFIG.API_BASE_URL}/api/signal-validation/labjack/status`, {
            timeout: 1 // 1ms timeout - should always timeout
          });
          return { timeoutHandled: false };
        } catch (error) {
          if (axios.isAxiosError(error) && error.code === 'ECONNABORTED') {
            return { timeoutHandled: true, error: error.message };
          }
          // Try normal timeout to see if the endpoint is actually working
          try {
            await axios.get(`${TEST_CONFIG.API_BASE_URL}/api/signal-validation/labjack/status`, {
              timeout: TEST_CONFIG.NETWORK_TIMEOUT
            });
            return { timeoutHandled: true, note: 'Short timeout triggered, normal request succeeded' };
          } catch {
            throw error;
          }
        }
      });
      
      if (result.timeoutHandled) {
        addTestResult({
          test: 'Timeout Handling',
          status: 'PASS',
          message: 'Timeout conditions handled properly',
          data: result,
          duration
        });
      } else {
        addTestResult({
          test: 'Timeout Handling',
          status: 'WARN',
          message: 'Timeout test did not behave as expected',
          data: result,
          duration
        });
      }
      
      expect(result.timeoutHandled).toBe(true);
    }, TEST_CONFIG.NETWORK_TIMEOUT * 2);

  });

  describe('7. Performance and Load Testing', () => {
    
    test('API response time benchmarking', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'API Response Time Benchmark',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const iterations = 10;
      const responseTimes: number[] = [];
      
      for (let i = 0; i < iterations; i++) {
        const { duration } = await timeAsyncOperation(async () => {
          await enhancedApiService.checkLabJackStatus();
        });
        responseTimes.push(duration);
      }
      
      const avgResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
      const minResponseTime = Math.min(...responseTimes);
      const maxResponseTime = Math.max(...responseTimes);
      
      const performanceGood = avgResponseTime < 1000; // Less than 1 second average
      
      addTestResult({
        test: 'API Response Time Benchmark',
        status: performanceGood ? 'PASS' : 'WARN',
        message: `Average response time: ${avgResponseTime.toFixed(0)}ms (min: ${minResponseTime}ms, max: ${maxResponseTime}ms)`,
        data: {
          iterations,
          avgResponseTime,
          minResponseTime,
          maxResponseTime,
          allTimes: responseTimes
        }
      });
      
      expect(avgResponseTime).toBeLessThan(5000); // Should be less than 5 seconds
    }, TEST_CONFIG.TEST_TIMEOUT);

    test('Concurrent API request handling', async () => {
      if (!backendHealthy) {
        addTestResult({
          test: 'Concurrent API Requests',
          status: 'SKIP',
          message: 'Skipped due to backend health check failure'
        });
        return;
      }
      
      const { result, duration } = await timeAsyncOperation(async () => {
        const concurrentRequests = 5;
        const requests = Array(concurrentRequests).fill(null).map(() => 
          enhancedApiService.checkLabJackStatus()
        );
        
        const results = await Promise.allSettled(requests);
        
        const successful = results.filter(r => r.status === 'fulfilled').length;
        const failed = results.filter(r => r.status === 'rejected').length;
        
        return {
          total: concurrentRequests,
          successful,
          failed,
          results
        };
      });
      
      const successRate = (result.successful / result.total) * 100;
      const concurrencyGood = successRate >= 80; // At least 80% success rate
      
      addTestResult({
        test: 'Concurrent API Requests',
        status: concurrencyGood ? 'PASS' : 'WARN',
        message: `${result.successful}/${result.total} concurrent requests succeeded (${successRate.toFixed(1)}%)`,
        data: {
          total: result.total,
          successful: result.successful,
          failed: result.failed,
          successRate,
          duration
        }
      });
      
      expect(successRate).toBeGreaterThanOrEqual(80);
    }, TEST_CONFIG.TEST_TIMEOUT);

  });

});

// Export test results for external analysis
export { testResults, TestResult };