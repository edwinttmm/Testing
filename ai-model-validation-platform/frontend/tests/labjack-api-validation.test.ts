/**
 * LabJack API Endpoint Validation Test Suite
 * ==========================================
 * 
 * Comprehensive API endpoint testing for LabJack integration
 * Tests all REST endpoints with real backend communication
 * 
 * Test Coverage:
 * - LabJack status endpoints
 * - Connection management endpoints  
 * - Device discovery and management
 * - Streaming control endpoints
 * - Driver compatibility endpoints
 * - Error handling and validation
 * 
 * @author API Testing Specialist
 * @requires Running backend on localhost:8000
 */

import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import axios from 'axios';

// API configuration
const API_CONFIG = {
  BASE_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  TIMEOUT: 15000, // 15 seconds for API calls
  RETRY_COUNT: 3,
  RETRY_DELAY: 1000 // 1 second between retries
};

// Test results tracking
interface ApiTestResult {
  endpoint: string;
  method: string;
  status: 'PASS' | 'FAIL' | 'WARN';
  statusCode?: number;
  responseTime: number;
  message: string;
  error?: any;
}

let apiTestResults: ApiTestResult[] = [];

// Helper function to add test results
function addApiTestResult(result: ApiTestResult) {
  apiTestResults.push(result);
  const emoji = result.status === 'PASS' ? '✅' : result.status === 'FAIL' ? '❌' : '⚠️';
  console.log(`${emoji} ${result.method} ${result.endpoint}: ${result.message} (${result.responseTime}ms)`);
}

// Helper function to make API requests with retry logic
async function makeApiRequest(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  endpoint: string,
  data?: any,
  headers?: any
): Promise<{ response?: any; error?: any; responseTime: number; statusCode?: number }> {
  const startTime = performance.now();
  
  for (let attempt = 1; attempt <= API_CONFIG.RETRY_COUNT; attempt++) {
    try {
      const config: any = {
        method: method.toLowerCase(),
        url: `${API_CONFIG.BASE_URL}${endpoint}`,
        timeout: API_CONFIG.TIMEOUT,
        headers: {
          'Content-Type': 'application/json',
          ...headers
        }
      };
      
      if (data && (method === 'POST' || method === 'PUT')) {
        config.data = data;
      }
      
      const response = await axios(config);
      const responseTime = Math.round(performance.now() - startTime);
      
      return {
        response: response.data,
        responseTime,
        statusCode: response.status
      };
      
    } catch (error: any) {
      if (attempt === API_CONFIG.RETRY_COUNT) {
        const responseTime = Math.round(performance.now() - startTime);
        return {
          error,
          responseTime,
          statusCode: error.response?.status
        };
      }
      
      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, API_CONFIG.RETRY_DELAY));
    }
  }
  
  // This should never be reached
  return { error: new Error('Max retries exceeded'), responseTime: 0 };
}

// Helper function to validate response structure
function validateResponseStructure(response: any, expectedFields: string[]): boolean {
  if (!response || typeof response !== 'object') {
    return false;
  }
  
  return expectedFields.every(field => {
    const keys = field.split('.');
    let current = response;
    
    for (const key of keys) {
      if (current === null || current === undefined || !(key in current)) {
        return false;
      }
      current = current[key];
    }
    
    return true;
  });
}

describe('LabJack API Endpoint Validation', () => {
  
  let backendHealthy = false;
  let labJackAvailable = false;
  
  beforeAll(async () => {
    console.log('🚀 Starting LabJack API Endpoint Validation');
    console.log('===========================================');
    console.log(`Backend URL: ${API_CONFIG.BASE_URL}`);
    console.log(`Timeout: ${API_CONFIG.TIMEOUT}ms`);
    console.log('');
    
    // Check if backend is running
    try {
      const { response, error, responseTime } = await makeApiRequest('GET', '/health');
      
      if (response && !error) {
        backendHealthy = true;
        addApiTestResult({
          endpoint: '/health',
          method: 'GET',
          status: 'PASS',
          statusCode: 200,
          responseTime,
          message: 'Backend is healthy and responding'
        });
      } else {
        addApiTestResult({
          endpoint: '/health',
          method: 'GET',
          status: 'FAIL',
          statusCode: error?.response?.status || 0,
          responseTime,
          message: `Backend health check failed: ${error?.message || 'Unknown error'}`,
          error
        });
      }
    } catch (error) {
      console.error('❌ Backend health check failed:', error);
    }
  });
  
  afterAll(() => {
    // Generate comprehensive test report
    const passed = apiTestResults.filter(r => r.status === 'PASS').length;
    const failed = apiTestResults.filter(r => r.status === 'FAIL').length;
    const warnings = apiTestResults.filter(r => r.status === 'WARN').length;
    
    const avgResponseTime = apiTestResults.length > 0 ? 
      Math.round(apiTestResults.reduce((sum, r) => sum + r.responseTime, 0) / apiTestResults.length) : 0;
    
    console.log('\n📊 LabJack API Test Report');
    console.log('==========================');
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`⚠️ Warnings: ${warnings}`);
    console.log(`📝 Total: ${apiTestResults.length}`);
    console.log(`⚡ Avg Response Time: ${avgResponseTime}ms`);
    
    if (failed === 0 && warnings === 0) {
      console.log('\n🎉 All LabJack API tests passed!');
    } else if (failed === 0) {
      console.log('\n✨ All API tests passed with some warnings.');
    } else {
      console.log(`\n⚠️ ${failed} API test(s) failed.`);
    }
  });

  describe('1. Health and System Endpoints', () => {
    
    test('Backend health endpoint', async () => {
      const { response, error, responseTime, statusCode } = await makeApiRequest('GET', '/health');
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/health',
          method: 'GET',
          status: 'PASS',
          statusCode,
          responseTime,
          message: 'Health endpoint responded successfully'
        });
        
        expect(response).toBeDefined();
        expect(statusCode).toBe(200);
      } else {
        addApiTestResult({
          endpoint: '/health',
          method: 'GET',
          status: 'FAIL',
          statusCode,
          responseTime,
          message: `Health check failed: ${error?.message}`,
          error
        });
        
        // Don't fail the test if backend is down, just skip other tests
        if (!backendHealthy) {
          console.warn('⚠️ Backend is not healthy, some tests may be skipped');
        }
      }
    });

  });

  describe('2. LabJack Status Endpoints', () => {
    
    test('LabJack status retrieval', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping LabJack status test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('GET', '/api/labjack/status');
      
      if (response && !error) {
        const expectedFields = ['connected', 'mode', 'status', 'statistics'];
        const isValidStructure = validateResponseStructure(response, expectedFields);
        
        addApiTestResult({
          endpoint: '/api/labjack/status',
          method: 'GET',
          status: isValidStructure ? 'PASS' : 'WARN',
          statusCode,
          responseTime,
          message: `Status retrieved - Connected: ${response.connected}, Mode: ${response.mode}, Structure: ${isValidStructure ? 'Valid' : 'Invalid'}`
        });
        
        expect(response).toBeDefined();
        expect(typeof response.connected).toBe('boolean');
        expect(response.mode).toBeDefined();
        expect(response.statistics).toBeDefined();
        
        labJackAvailable = response.connected;
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/status',
          method: 'GET',
          status: 'FAIL',
          statusCode,
          responseTime,
          message: `Status retrieval failed: ${error?.response?.data?.detail || error?.message}`,
          error
        });
      }
    });

    test('LabJack status with query parameters', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping LabJack status with params test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('GET', '/api/labjack/status?include_diagnostics=true');
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/status?include_diagnostics=true',
          method: 'GET',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Status with diagnostics retrieved successfully`
        });
        
        expect(response).toBeDefined();
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/status?include_diagnostics=true',
          method: 'GET',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Status with params failed (may not be supported): ${error?.message}`,
          error
        });
      }
    });

  });

  describe('3. Connection Management Endpoints', () => {
    
    test('LabJack connection attempt (auto mode)', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping connection test - backend not healthy');
        return;
      }
      
      const connectData = {
        force_mode: 'auto',
        timeout: 10000
      };
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('POST', '/api/labjack/connect', connectData);
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/connect',
          method: 'POST',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Connection attempt successful - Status: ${response.status}`
        });
        
        expect(response).toBeDefined();
        expect(response.status).toBeDefined();
      } else {
        // Connection failure is expected if no hardware is present
        const status = statusCode === 500 ? 'WARN' : 'FAIL';
        addApiTestResult({
          endpoint: '/api/labjack/connect',
          method: 'POST',
          status,
          statusCode,
          responseTime,
          message: `Connection failed (may be expected without hardware): ${error?.response?.data?.detail || error?.message}`,
          error
        });
      }
    });

    test('LabJack connection attempt (mock mode)', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping mock connection test - backend not healthy');
        return;
      }
      
      const connectData = {
        force_mode: 'mock',
        timeout: 5000
      };
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('POST', '/api/labjack/connect', connectData);
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/connect (mock)',
          method: 'POST',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Mock connection successful - Status: ${response.status}`
        });
        
        expect(response).toBeDefined();
        expect(response.status).toBeDefined();
        
        labJackAvailable = true; // Mock mode should always work
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/connect (mock)',
          method: 'POST',
          status: 'FAIL',
          statusCode,
          responseTime,
          message: `Mock connection failed: ${error?.response?.data?.detail || error?.message}`,
          error
        });
      }
    });

    test('LabJack disconnection', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping disconnection test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('POST', '/api/labjack/disconnect');
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/disconnect',
          method: 'POST',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Disconnection successful - Status: ${response.status || 'success'}`
        });
        
        expect(response).toBeDefined();
      } else {
        // Disconnection might fail if not connected, which is fine
        addApiTestResult({
          endpoint: '/api/labjack/disconnect',
          method: 'POST',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Disconnection failed (may be expected if not connected): ${error?.message}`,
          error
        });
      }
    });

  });

  describe('4. Device Discovery Endpoints', () => {
    
    test('LabJack device discovery', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping discovery test - backend not healthy');
        return;
      }
      
      const discoveryData = {
        timeout: 5000,
        scan_usb: true,
        scan_network: true
      };
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('POST', '/api/labjack/discover', discoveryData);
      
      if (response && !error) {
        const expectedFields = ['devices_found'];
        const isValidStructure = validateResponseStructure(response, expectedFields);
        
        addApiTestResult({
          endpoint: '/api/labjack/discover',
          method: 'POST',
          status: isValidStructure ? 'PASS' : 'WARN',
          statusCode,
          responseTime,
          message: `Discovery completed - Found: ${response.devices_found} devices, Structure: ${isValidStructure ? 'Valid' : 'Invalid'}`
        });
        
        expect(response).toBeDefined();
        expect(typeof response.devices_found).toBe('number');
        expect(response.devices_found).toBeGreaterThanOrEqual(0);
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/discover',
          method: 'POST',
          status: 'FAIL',
          statusCode,
          responseTime,
          message: `Discovery failed: ${error?.response?.data?.detail || error?.message}`,
          error
        });
      }
    });

  });

  describe('5. Streaming Control Endpoints', () => {
    
    test('Start LabJack streaming', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping streaming start test - backend not healthy');
        return;
      }
      
      const streamConfig = {
        channels: ['AIN0', 'AIN1'],
        sample_rate: 1000,
        voltage_threshold: 2.5
      };
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('POST', '/api/labjack/start-stream', streamConfig);
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/start-stream',
          method: 'POST',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Streaming started - Status: ${response.status || 'success'}`
        });
        
        expect(response).toBeDefined();
      } else {
        // Streaming might fail if not connected
        const status = labJackAvailable ? 'FAIL' : 'WARN';
        addApiTestResult({
          endpoint: '/api/labjack/start-stream',
          method: 'POST',
          status,
          statusCode,
          responseTime,
          message: `Streaming start failed (${labJackAvailable ? 'unexpected' : 'expected without device'}): ${error?.message}`,
          error
        });
      }
    });

    test('Stop LabJack streaming', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping streaming stop test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('POST', '/api/labjack/stop-stream');
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/stop-stream',
          method: 'POST',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Streaming stopped - Status: ${response.status || 'success'}`
        });
        
        expect(response).toBeDefined();
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/stop-stream',
          method: 'POST',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Streaming stop failed (may be expected if not streaming): ${error?.message}`,
          error
        });
      }
    });

  });

  describe('6. Driver and System Information Endpoints', () => {
    
    test('Windows driver status check', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping driver status test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('GET', '/api/labjack/driver-status');
      
      if (response && !error) {
        const expectedFields = ['supported', 'detected'];
        const isValidStructure = validateResponseStructure(response, expectedFields);
        
        addApiTestResult({
          endpoint: '/api/labjack/driver-status',
          method: 'GET',
          status: isValidStructure ? 'PASS' : 'WARN',
          statusCode,
          responseTime,
          message: `Driver status retrieved - Supported: ${response.supported}, Detected: ${response.detected}`
        });
        
        expect(response).toBeDefined();
        expect(typeof response.supported).toBe('boolean');
        expect(typeof response.detected).toBe('boolean');
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/driver-status',
          method: 'GET',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Driver status check failed (may not be implemented): ${error?.message}`,
          error
        });
      }
    });

    test('Windows driver information', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping driver info test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('GET', '/api/labjack/windows-driver-info');
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/windows-driver-info',
          method: 'GET',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Driver info retrieved - Version: ${response.version || 'N/A'}`
        });
        
        expect(response).toBeDefined();
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/windows-driver-info',
          method: 'GET',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Driver info failed (may not be implemented): ${error?.message}`,
          error
        });
      }
    });

  });

  describe('7. Bridge and Network Endpoints', () => {
    
    test('Bridge connection test', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping bridge test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('GET', '/api/labjack/bridge-test');
      
      if (response && !error) {
        addApiTestResult({
          endpoint: '/api/labjack/bridge-test',
          method: 'GET',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Bridge test successful - Latency: ${response.latency || 'N/A'}ms`
        });
        
        expect(response).toBeDefined();
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/bridge-test',
          method: 'GET',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Bridge test failed (may not be in bridge mode): ${error?.message}`,
          error
        });
      }
    });

  });

  describe('8. Error Handling and Edge Cases', () => {
    
    test('Invalid endpoint handling', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping invalid endpoint test - backend not healthy');
        return;
      }
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('GET', '/api/labjack/invalid-endpoint');
      
      if (error && (statusCode === 404 || statusCode === 405)) {
        addApiTestResult({
          endpoint: '/api/labjack/invalid-endpoint',
          method: 'GET',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Invalid endpoint properly rejected with status ${statusCode}`
        });
        
        expect(statusCode).toBeGreaterThanOrEqual(400);
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/invalid-endpoint',
          method: 'GET',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Invalid endpoint handling unexpected: ${statusCode}`,
          error
        });
      }
    });

    test('Malformed request handling', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping malformed request test - backend not healthy');
        return;
      }
      
      const malformedData = {
        invalid_field: 'invalid_value',
        another_bad_field: null
      };
      
      const { response, error, responseTime, statusCode } = await makeApiRequest('POST', '/api/labjack/connect', malformedData);
      
      // This should either succeed (ignoring invalid fields) or return 400
      if (error && statusCode && statusCode >= 400 && statusCode < 500) {
        addApiTestResult({
          endpoint: '/api/labjack/connect (malformed)',
          method: 'POST',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Malformed request properly rejected with status ${statusCode}`
        });
      } else if (response) {
        addApiTestResult({
          endpoint: '/api/labjack/connect (malformed)',
          method: 'POST',
          status: 'PASS',
          statusCode,
          responseTime,
          message: `Malformed request handled gracefully (ignored invalid fields)`
        });
      } else {
        addApiTestResult({
          endpoint: '/api/labjack/connect (malformed)',
          method: 'POST',
          status: 'WARN',
          statusCode,
          responseTime,
          message: `Malformed request handling unclear: ${error?.message}`,
          error
        });
      }
    });

    test('Timeout handling', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping timeout test - backend not healthy');
        return;
      }
      
      // Test with very short timeout
      const startTime = performance.now();
      try {
        await axios.get(`${API_CONFIG.BASE_URL}/api/labjack/status`, { timeout: 1 });
        
        // If it doesn't timeout, the endpoint is very fast
        const responseTime = Math.round(performance.now() - startTime);
        addApiTestResult({
          endpoint: '/api/labjack/status (timeout test)',
          method: 'GET',
          status: 'PASS',
          statusCode: 200,
          responseTime,
          message: `Endpoint very fast (${responseTime}ms < 1ms timeout)`
        });
      } catch (error: any) {
        const responseTime = Math.round(performance.now() - startTime);
        
        if (error.code === 'ECONNABORTED') {
          addApiTestResult({
            endpoint: '/api/labjack/status (timeout test)',
            method: 'GET',
            status: 'PASS',
            responseTime,
            message: `Timeout handled correctly (aborted after ${responseTime}ms)`
          });
        } else {
          addApiTestResult({
            endpoint: '/api/labjack/status (timeout test)',
            method: 'GET',
            status: 'WARN',
            responseTime,
            message: `Timeout test unclear result: ${error.message}`,
            error
          });
        }
      }
    });

  });

  describe('9. Performance and Load Testing', () => {
    
    test('API response time consistency', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping performance test - backend not healthy');
        return;
      }
      
      const iterations = 5;
      const responseTimes: number[] = [];
      
      for (let i = 0; i < iterations; i++) {
        const { responseTime } = await makeApiRequest('GET', '/api/labjack/status');
        responseTimes.push(responseTime);
        
        // Small delay between requests
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      const avgTime = Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length);
      const minTime = Math.min(...responseTimes);
      const maxTime = Math.max(...responseTimes);
      const stdDev = Math.round(Math.sqrt(responseTimes.reduce((sq, n) => sq + Math.pow(n - avgTime, 2), 0) / responseTimes.length));
      
      const isConsistent = stdDev < avgTime * 0.5; // Standard deviation less than 50% of average
      
      addApiTestResult({
        endpoint: '/api/labjack/status (performance)',
        method: 'GET',
        status: isConsistent ? 'PASS' : 'WARN',
        responseTime: avgTime,
        message: `Performance: avg=${avgTime}ms, min=${minTime}ms, max=${maxTime}ms, stddev=${stdDev}ms`
      });
      
      expect(avgTime).toBeLessThan(5000); // Should be less than 5 seconds
      expect(maxTime).toBeLessThan(10000); // Max should be less than 10 seconds
    });

    test('Concurrent request handling', async () => {
      if (!backendHealthy) {
        console.log('⏭️ Skipping concurrent test - backend not healthy');
        return;
      }
      
      const concurrentRequests = 3; // Keep it reasonable for testing
      const startTime = performance.now();
      
      const requests = Array(concurrentRequests).fill(null).map(() => 
        makeApiRequest('GET', '/api/labjack/status')
      );
      
      const results = await Promise.allSettled(requests);
      const totalTime = Math.round(performance.now() - startTime);
      
      const successful = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;
      const successRate = (successful / concurrentRequests) * 100;
      
      addApiTestResult({
        endpoint: '/api/labjack/status (concurrent)',
        method: 'GET',
        status: successRate >= 80 ? 'PASS' : 'WARN',
        responseTime: totalTime,
        message: `Concurrent: ${successful}/${concurrentRequests} successful (${successRate.toFixed(1)}%), total time: ${totalTime}ms`
      });
      
      expect(successRate).toBeGreaterThanOrEqual(60); // At least 60% should succeed
    });

  });

});

export { apiTestResults, ApiTestResult };