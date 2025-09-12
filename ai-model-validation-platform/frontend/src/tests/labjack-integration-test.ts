/**
 * LabJack Integration Test Script
 * 
 * This script tests the frontend-backend LabJack integration to verify:
 * 1. API endpoint connectivity
 * 2. LabJack initialization 
 * 3. Status checking
 * 4. WebSocket connections for real-time voltage monitoring
 * 5. Error handling and fallbacks
 */

import { enhancedApiService } from '../services/enhancedApiService';
import websocketService from '../services/websocketService';

interface TestResult {
  test: string;
  status: 'PASS' | 'FAIL' | 'SKIP';
  message: string;
  data?: any;
}

class LabJackIntegrationTest {
  private results: TestResult[] = [];
  private baseUrl: string;

  constructor() {
    this.baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  }

  private log(test: string, status: 'PASS' | 'FAIL' | 'SKIP', message: string, data?: any) {
    const result: TestResult = { test, status, message, data };
    this.results.push(result);
    
    const emoji = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⏭️';
    console.log(`${emoji} ${test}: ${message}`);
    
    if (data) {
      console.log('   Data:', JSON.stringify(data, null, 2));
    }
  }

  async testApiHealth(): Promise<void> {
    try {
      const response = await enhancedApiService.healthCheck();
      this.log(
        'API Health Check',
        'PASS',
        `API is healthy - Response time: ${response.responseTime}`,
        response
      );
    } catch (error) {
      this.log(
        'API Health Check',
        'FAIL',
        `API health check failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        error
      );
    }
  }

  async testLabJackStatusCheck(): Promise<boolean> {
    try {
      const status = await enhancedApiService.checkLabJackStatus();
      
      this.log(
        'LabJack Status Check',
        'PASS',
        `Status retrieved - Connected: ${status.connected}`,
        {
          connected: status.connected,
          mock_mode: status.mock_mode,
          channels: status.channels,
          voltage_threshold: status.voltage_threshold,
          current_voltages: status.current_voltages
        }
      );
      
      return status.connected;
    } catch (error) {
      this.log(
        'LabJack Status Check',
        'FAIL',
        `Status check failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        error
      );
      return false;
    }
  }

  async testLabJackInitialization(): Promise<boolean> {
    try {
      const config = {
        voltage_threshold: { lower: 4.0, upper: 5.5 },
        channels: ['AIN0'],
        sample_rate: 1000
      };
      
      const response = await enhancedApiService.initializeLabJack(config);
      
      const isSuccess = response.status === 'connected' || response.status === 'success';
      
      this.log(
        'LabJack Initialization',
        isSuccess ? 'PASS' : 'FAIL',
        response.message || 'Initialization completed',
        {
          status: response.status,
          mock_mode: response.mock_mode,
          message: response.message,
          error: response.error
        }
      );
      
      return isSuccess;
    } catch (error) {
      this.log(
        'LabJack Initialization',
        'FAIL',
        `Initialization failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        error
      );
      return false;
    }
  }

  async testSignalMonitoring(): Promise<boolean> {
    try {
      const startResponse = await enhancedApiService.startSignalMonitoring();
      
      if (startResponse.status === 'success' || startResponse.status === 'started') {
        this.log(
          'Signal Monitoring Start',
          'PASS',
          startResponse.message || 'Monitoring started successfully',
          startResponse
        );
        
        // Give monitoring a moment to start
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Try to stop monitoring
        const stopResponse = await enhancedApiService.stopSignalMonitoring();
        
        this.log(
          'Signal Monitoring Stop',
          'PASS',
          stopResponse.message || 'Monitoring stopped successfully',
          stopResponse
        );
        
        return true;
      } else {
        this.log(
          'Signal Monitoring Start',
          'FAIL',
          `Failed to start monitoring: ${startResponse.message}`,
          startResponse
        );
        return false;
      }
    } catch (error) {
      this.log(
        'Signal Monitoring',
        'FAIL',
        `Monitoring test failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        error
      );
      return false;
    }
  }

  async testWebSocketConnection(): Promise<boolean> {
    try {
      // Test basic WebSocket connection
      await websocketService.connect();
      
      if (websocketService.isConnected) {
        this.log(
          'WebSocket Connection',
          'PASS',
          'Successfully connected to WebSocket service',
          websocketService.getHealthStatus()
        );
        
        // Test voltage monitoring WebSocket
        let voltageDataReceived = false;
        
        const unsubscribe = websocketService.subscribe('voltage_data', (data) => {
          voltageDataReceived = true;
          this.log(
            'WebSocket Voltage Data',
            'PASS',
            'Received voltage data from WebSocket',
            data
          );
        });
        
        // Wait for potential voltage data
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        unsubscribe();
        
        if (!voltageDataReceived) {
          this.log(
            'WebSocket Voltage Data',
            'SKIP',
            'No voltage data received (may be expected if LabJack not actively monitoring)'
          );
        }
        
        websocketService.disconnect();
        return true;
      } else {
        this.log(
          'WebSocket Connection',
          'FAIL',
          'Failed to connect to WebSocket service'
        );
        return false;
      }
    } catch (error) {
      this.log(
        'WebSocket Connection',
        'FAIL',
        `WebSocket test failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        error
      );
      return false;
    }
  }

  async testErrorHandling(): Promise<void> {
    try {
      // Test invalid configuration
      const invalidConfig = {
        voltage_threshold: { lower: -10, upper: 20 }, // Invalid range
        channels: ['INVALID_CHANNEL'],
        sample_rate: -1
      };
      
      try {
        await enhancedApiService.initializeLabJack(invalidConfig);
        this.log(
          'Error Handling - Invalid Config',
          'FAIL',
          'Expected error for invalid config, but none was thrown'
        );
      } catch (error) {
        this.log(
          'Error Handling - Invalid Config',
          'PASS',
          'Properly handled invalid configuration',
          error instanceof Error ? error.message : 'Unknown error'
        );
      }
    } catch (error) {
      this.log(
        'Error Handling',
        'FAIL',
        `Error handling test failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        error
      );
    }
  }

  async runAllTests(): Promise<TestResult[]> {
    console.log('🧪 Starting LabJack Integration Tests...\n');
    
    // Test API connectivity first
    await this.testApiHealth();
    
    // Test LabJack functionality
    const statusWorking = await this.testLabJackStatusCheck();
    
    if (statusWorking) {
      const initWorking = await this.testLabJackInitialization();
      
      if (initWorking) {
        await this.testSignalMonitoring();
      } else {
        this.log('Signal Monitoring', 'SKIP', 'Skipped due to initialization failure');
      }
    } else {
      this.log('LabJack Initialization', 'SKIP', 'Skipped due to status check failure');
      this.log('Signal Monitoring', 'SKIP', 'Skipped due to status check failure');
    }
    
    // Test WebSocket regardless of LabJack status
    await this.testWebSocketConnection();
    
    // Test error handling
    await this.testErrorHandling();
    
    // Print summary
    this.printSummary();
    
    return this.results;
  }

  private printSummary(): void {
    const passed = this.results.filter(r => r.status === 'PASS').length;
    const failed = this.results.filter(r => r.status === 'FAIL').length;
    const skipped = this.results.filter(r => r.status === 'SKIP').length;
    
    console.log('\n📊 Test Summary:');
    console.log(`   ✅ Passed: ${passed}`);
    console.log(`   ❌ Failed: ${failed}`);
    console.log(`   ⏭️  Skipped: ${skipped}`);
    console.log(`   📝 Total: ${this.results.length}`);
    
    if (failed === 0) {
      console.log('\n🎉 All tests passed! LabJack integration is working correctly.');
    } else {
      console.log(`\n⚠️  ${failed} test(s) failed. Check the logs above for details.`);
    }
    
    // Provide suggestions based on results
    const failedTests = this.results.filter(r => r.status === 'FAIL');
    if (failedTests.length > 0) {
      console.log('\n💡 Troubleshooting suggestions:');
      
      failedTests.forEach(result => {
        switch (result.test) {
          case 'API Health Check':
            console.log('   - Check if the backend server is running on the correct port');
            console.log('   - Verify REACT_APP_API_URL environment variable is set correctly');
            break;
          case 'LabJack Status Check':
          case 'LabJack Initialization':
            console.log('   - Ensure the backend signal validation service is running');
            console.log('   - Check if LabJack hardware is connected (mock mode should still work)');
            console.log('   - Verify the LabJack API endpoints are properly configured');
            break;
          case 'WebSocket Connection':
            console.log('   - Check if the WebSocket server is running on the correct port');
            console.log('   - Verify REACT_APP_SOCKETIO_URL or REACT_APP_WS_URL is set correctly');
            console.log('   - Ensure no firewall is blocking WebSocket connections');
            break;
        }
      });
    }
  }
}

// Export for use in tests or manual execution
export default LabJackIntegrationTest;

// Self-executing function for direct script usage
if (typeof window !== 'undefined' && window.location) {
  // Running in browser - can be called manually
  (window as any).testLabJackIntegration = async () => {
    const test = new LabJackIntegrationTest();
    return await test.runAllTests();
  };
  
  console.log('LabJack Integration Test loaded. Run testLabJackIntegration() in console to start tests.');
}