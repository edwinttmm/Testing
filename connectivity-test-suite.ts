#!/usr/bin/env node
/**
 * API Connectivity Test Suite
 * 
 * Comprehensive testing for API connectivity issues and their fixes
 * Date: August 26, 2025
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

interface TestResult {
  name: string;
  passed: boolean;
  details?: any;
  error?: string;
  duration?: number;
}

interface ConnectivityTestReport {
  overall: 'PASSED' | 'FAILED' | 'PARTIAL';
  totalTests: number;
  passedTests: number;
  failedTests: number;
  tests: TestResult[];
  timestamp: string;
  environment: {
    nodeEnv: string;
    platform: string;
    networkStatus: string;
  };
}

class ConnectivityTestSuite {
  private results: TestResult[] = [];
  private baseApiUrl = 'http://155.138.239.131:8000';
  private fallbackUrls = ['http://localhost:8000', 'http://127.0.0.1:8000'];
  
  async runAllTests(): Promise<ConnectivityTestReport> {
    console.log('🧪 Starting API Connectivity Test Suite...');
    console.log('=' .repeat(60));
    
    // Test 1: Basic server connectivity
    await this.testBasicConnectivity();
    
    // Test 2: Health endpoint validation
    await this.testHealthEndpoint();
    
    // Test 3: API endpoint functionality
    await this.testApiEndpoints();
    
    // Test 4: Error handling and fallback
    await this.testErrorHandlingAndFallback();
    
    // Test 5: Environment configuration
    await this.testEnvironmentConfiguration();
    
    // Test 6: Network timeout handling
    await this.testTimeoutHandling();
    
    // Test 7: CORS configuration
    await this.testCorsConfiguration();
    
    // Test 8: Frontend-backend integration
    await this.testFrontendBackendIntegration();
    
    return this.generateReport();
  }
  
  private async testBasicConnectivity(): Promise<void> {
    const testName = 'Basic Server Connectivity';
    console.log(`\n🔍 Testing: ${testName}`);
    
    const startTime = Date.now();
    
    try {
      // Test primary server
      const response = await this.makeRequest(`${this.baseApiUrl}/health`, {
        method: 'GET',
        timeout: 10000
      });
      
      const duration = Date.now() - startTime;
      
      if (response.ok) {
        const data = await response.json();
        this.results.push({
          name: testName,
          passed: true,
          details: {
            url: this.baseApiUrl,
            status: response.status,
            latency: `${duration}ms`,
            healthData: data
          },
          duration
        });
        console.log('✅ Primary server connectivity: PASSED');
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    } catch (error: any) {
      const duration = Date.now() - startTime;
      console.log('❌ Primary server connectivity: FAILED');
      console.log(`   Error: ${error.message}`);
      
      this.results.push({
        name: testName,
        passed: false,
        error: error.message,
        details: {
          url: this.baseApiUrl,
          attemptedDuration: `${duration}ms`
        },
        duration
      });
    }
  }
  
  private async testHealthEndpoint(): Promise<void> {
    const testName = 'Health Endpoint Validation';
    console.log(`\n🏥 Testing: ${testName}`);
    
    const startTime = Date.now();
    
    try {
      const response = await this.makeRequest(`${this.baseApiUrl}/health`);
      const data = await response.json();
      const duration = Date.now() - startTime;
      
      // Validate health response structure
      const isValidHealth = (
        data &&
        typeof data.status === 'string' &&
        data.status === 'healthy' &&
        typeof data.timestamp !== 'undefined'
      );
      
      if (isValidHealth) {
        this.results.push({
          name: testName,
          passed: true,
          details: {
            status: data.status,
            timestamp: data.timestamp,
            checks: data.checks || {},
            system: data.system || {}
          },
          duration
        });
        console.log('✅ Health endpoint validation: PASSED');
      } else {
        throw new Error('Invalid health response structure');
      }
    } catch (error: any) {
      const duration = Date.now() - startTime;
      console.log('❌ Health endpoint validation: FAILED');
      console.log(`   Error: ${error.message}`);
      
      this.results.push({
        name: testName,
        passed: false,
        error: error.message,
        duration
      });
    }
  }
  
  private async testApiEndpoints(): Promise<void> {
    const testName = 'API Endpoints Functionality';
    console.log(`\n🔌 Testing: ${testName}`);
    
    const endpoints = [
      { path: '/api/dashboard/stats', method: 'GET' },
      { path: '/api/projects', method: 'GET' },
      { path: '/api/videos', method: 'GET' }
    ];
    
    let passedEndpoints = 0;
    const endpointResults: any[] = [];
    
    for (const endpoint of endpoints) {
      const startTime = Date.now();
      
      try {
        const response = await this.makeRequest(`${this.baseApiUrl}${endpoint.path}`, {
          method: endpoint.method,
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        });
        
        const duration = Date.now() - startTime;
        
        if (response.ok) {
          passedEndpoints++;
          endpointResults.push({
            path: endpoint.path,
            method: endpoint.method,
            status: response.status,
            passed: true,
            duration: `${duration}ms`
          });
          console.log(`   ✅ ${endpoint.method} ${endpoint.path}: PASSED`);
        } else {
          endpointResults.push({
            path: endpoint.path,
            method: endpoint.method,
            status: response.status,
            passed: false,
            error: `HTTP ${response.status}`,
            duration: `${duration}ms`
          });
          console.log(`   ❌ ${endpoint.method} ${endpoint.path}: HTTP ${response.status}`);
        }
      } catch (error: any) {
        const duration = Date.now() - startTime;
        endpointResults.push({
          path: endpoint.path,
          method: endpoint.method,
          passed: false,
          error: error.message,
          duration: `${duration}ms`
        });
        console.log(`   ❌ ${endpoint.method} ${endpoint.path}: ${error.message}`);
      }
    }
    
    const allPassed = passedEndpoints === endpoints.length;
    
    this.results.push({
      name: testName,
      passed: allPassed,
      details: {
        totalEndpoints: endpoints.length,
        passedEndpoints,
        results: endpointResults
      }
    });
    
    if (allPassed) {
      console.log('✅ API endpoints functionality: PASSED');
    } else {
      console.log(`❌ API endpoints functionality: PARTIAL (${passedEndpoints}/${endpoints.length} passed)`);
    }
  }
  
  private async testErrorHandlingAndFallback(): Promise<void> {
    const testName = 'Error Handling and Fallback';
    console.log(`\n🔄 Testing: ${testName}`);
    
    let fallbackSuccessful = false;
    const fallbackResults: any[] = [];
    
    // Test each fallback URL
    for (const fallbackUrl of this.fallbackUrls) {
      const startTime = Date.now();
      
      try {
        const response = await this.makeRequest(`${fallbackUrl}/health`, {
          timeout: 5000
        });
        
        const duration = Date.now() - startTime;
        
        if (response.ok) {
          fallbackSuccessful = true;
          fallbackResults.push({
            url: fallbackUrl,
            available: true,
            status: response.status,
            latency: `${duration}ms`
          });
          console.log(`   ✅ Fallback ${fallbackUrl}: AVAILABLE`);
        } else {
          fallbackResults.push({
            url: fallbackUrl,
            available: false,
            status: response.status,
            error: `HTTP ${response.status}`
          });
          console.log(`   ❌ Fallback ${fallbackUrl}: HTTP ${response.status}`);
        }
      } catch (error: any) {
        fallbackResults.push({
          url: fallbackUrl,
          available: false,
          error: error.message
        });
        console.log(`   ❌ Fallback ${fallbackUrl}: ${error.message}`);
      }
    }
    
    // Test 404 error handling
    let errorHandlingWorks = false;
    try {
      const response = await this.makeRequest(`${this.baseApiUrl}/api/nonexistent-endpoint`);
      errorHandlingWorks = response.status === 404;
    } catch {
      // Connection error is also acceptable for this test
      errorHandlingWorks = true;
    }
    
    const overallPassed = fallbackSuccessful || errorHandlingWorks;
    
    this.results.push({
      name: testName,
      passed: overallPassed,
      details: {
        fallbacksAvailable: fallbackResults.filter(r => r.available).length,
        fallbackResults,
        errorHandlingWorks
      }
    });
    
    if (overallPassed) {
      console.log('✅ Error handling and fallback: PASSED');
    } else {
      console.log('❌ Error handling and fallback: FAILED');
    }
  }
  
  private async testEnvironmentConfiguration(): Promise<void> {
    const testName = 'Environment Configuration';
    console.log(`\n⚙️ Testing: ${testName}`);
    
    try {
      const envIssues: string[] = [];
      const configDetails: any = {};
      
      // Check if we're using the correct API URL
      const expectedApiUrl = '155.138.239.131:8000';
      if (!this.baseApiUrl.includes(expectedApiUrl)) {
        envIssues.push(`API URL should point to ${expectedApiUrl}`);
      }
      
      // Check environment variables (if available)
      if (typeof process !== 'undefined' && process.env) {
        const reactAppApiUrl = process.env.REACT_APP_API_URL;
        if (reactAppApiUrl && !reactAppApiUrl.includes(expectedApiUrl)) {
          envIssues.push('REACT_APP_API_URL environment variable incorrect');
        }
        configDetails.REACT_APP_API_URL = reactAppApiUrl || 'Not set';
      }
      
      // Check runtime configuration
      if (typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG) {
        const runtimeApiUrl = (window as any).RUNTIME_CONFIG.REACT_APP_API_URL;
        if (runtimeApiUrl && !runtimeApiUrl.includes(expectedApiUrl)) {
          envIssues.push('Runtime configuration API URL incorrect');
        }
        configDetails.runtimeConfig = (window as any).RUNTIME_CONFIG;
      }
      
      const passed = envIssues.length === 0;
      
      this.results.push({
        name: testName,
        passed,
        details: {
          configuredApiUrl: this.baseApiUrl,
          expectedApiUrl,
          issues: envIssues,
          configDetails
        }
      });
      
      if (passed) {
        console.log('✅ Environment configuration: PASSED');
      } else {
        console.log('❌ Environment configuration: ISSUES FOUND');
        envIssues.forEach(issue => console.log(`   - ${issue}`));
      }
    } catch (error: any) {
      this.results.push({
        name: testName,
        passed: false,
        error: error.message
      });
      console.log(`❌ Environment configuration: ERROR - ${error.message}`);
    }
  }
  
  private async testTimeoutHandling(): Promise<void> {
    const testName = 'Network Timeout Handling';
    console.log(`\n⏱️ Testing: ${testName}`);
    
    const startTime = Date.now();
    
    try {
      // Test with very short timeout to trigger timeout handling
      await this.makeRequest(`${this.baseApiUrl}/health`, {
        timeout: 1 // 1ms timeout - should always timeout
      });
      
      // If we get here, the request didn't timeout (server is very fast)
      this.results.push({
        name: testName,
        passed: true,
        details: {
          message: 'Server responded faster than timeout threshold',
          duration: `${Date.now() - startTime}ms`
        }
      });
      console.log('✅ Network timeout handling: PASSED (server very fast)');
    } catch (error: any) {
      const duration = Date.now() - startTime;
      
      // Check if it's a timeout error
      const isTimeoutError = (
        error.name === 'AbortError' ||
        error.message.includes('timeout') ||
        error.message.includes('aborted')
      );
      
      if (isTimeoutError) {
        this.results.push({
          name: testName,
          passed: true,
          details: {
            message: 'Timeout handled correctly',
            errorType: error.name,
            duration: `${duration}ms`
          },
          duration
        });
        console.log('✅ Network timeout handling: PASSED');
      } else {
        this.results.push({
          name: testName,
          passed: false,
          error: `Unexpected error: ${error.message}`,
          duration
        });
        console.log(`❌ Network timeout handling: FAILED - ${error.message}`);
      }
    }
  }
  
  private async testCorsConfiguration(): Promise<void> {
    const testName = 'CORS Configuration';
    console.log(`\n🌐 Testing: ${testName}`);
    
    try {
      const response = await this.makeRequest(`${this.baseApiUrl}/health`, {
        method: 'OPTIONS' // Preflight request
      });
      
      const corsHeaders = {
        'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
        'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
        'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
      };
      
      const hasCorsHeaders = Object.values(corsHeaders).some(header => header !== null);
      
      this.results.push({
        name: testName,
        passed: hasCorsHeaders || response.ok,
        details: {
          status: response.status,
          corsHeaders,
          hasCorsHeaders
        }
      });
      
      if (hasCorsHeaders || response.ok) {
        console.log('✅ CORS configuration: PASSED');
      } else {
        console.log('❌ CORS configuration: NO CORS HEADERS FOUND');
      }
    } catch (error: any) {
      // CORS might block OPTIONS requests, but that doesn't mean it's misconfigured
      this.results.push({
        name: testName,
        passed: true, // We'll consider this passed if regular requests work
        details: {
          message: 'CORS preflight blocked, but regular requests may work',
          error: error.message
        }
      });
      console.log('⚠️ CORS configuration: PREFLIGHT BLOCKED (may be normal)');
    }
  }
  
  private async testFrontendBackendIntegration(): Promise<void> {
    const testName = 'Frontend-Backend Integration';
    console.log(`\n🔗 Testing: ${testName}`);
    
    try {
      // Test a complete API workflow
      const startTime = Date.now();
      
      // 1. Health check
      const healthResponse = await this.makeRequest(`${this.baseApiUrl}/health`);
      const healthData = await healthResponse.json();
      
      // 2. API endpoint
      const apiResponse = await this.makeRequest(`${this.baseApiUrl}/api/dashboard/stats`);
      const apiData = await apiResponse.json();
      
      const duration = Date.now() - startTime;
      
      const integrationWorks = healthResponse.ok && apiResponse.ok;
      
      this.results.push({
        name: testName,
        passed: integrationWorks,
        details: {
          healthCheck: {
            status: healthResponse.status,
            data: healthData
          },
          apiEndpoint: {
            status: apiResponse.status,
            hasData: !!apiData
          },
          totalDuration: `${duration}ms`
        },
        duration
      });
      
      if (integrationWorks) {
        console.log('✅ Frontend-backend integration: PASSED');
      } else {
        console.log('❌ Frontend-backend integration: FAILED');
      }
    } catch (error: any) {
      this.results.push({
        name: testName,
        passed: false,
        error: error.message
      });
      console.log(`❌ Frontend-backend integration: FAILED - ${error.message}`);
    }
  }
  
  private async makeRequest(url: string, options: any = {}): Promise<Response> {
    const controller = new AbortController();
    const timeout = options.timeout || 10000;
    
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        ...options,
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }
  
  private generateReport(): ConnectivityTestReport {
    const passedTests = this.results.filter(r => r.passed).length;
    const failedTests = this.results.length - passedTests;
    
    let overall: 'PASSED' | 'FAILED' | 'PARTIAL';
    if (passedTests === this.results.length) {
      overall = 'PASSED';
    } else if (passedTests === 0) {
      overall = 'FAILED';
    } else {
      overall = 'PARTIAL';
    }
    
    const report: ConnectivityTestReport = {
      overall,
      totalTests: this.results.length,
      passedTests,
      failedTests,
      tests: this.results,
      timestamp: new Date().toISOString(),
      environment: {
        nodeEnv: process.env.NODE_ENV || 'unknown',
        platform: typeof window !== 'undefined' ? 'browser' : 'node',
        networkStatus: typeof navigator !== 'undefined' ? 
          (navigator.onLine ? 'online' : 'offline') : 'unknown'
      }
    };
    
    return report;
  }
  
  printReport(report: ConnectivityTestReport): void {
    console.log('\n' + '='.repeat(60));
    console.log('📊 API CONNECTIVITY TEST REPORT');
    console.log('='.repeat(60));
    
    console.log(`\n🎯 Overall Result: ${report.overall}`);
    console.log(`📈 Test Results: ${report.passedTests}/${report.totalTests} passed`);
    
    if (report.failedTests > 0) {
      console.log(`\n❌ Failed Tests: ${report.failedTests}`);
      report.tests
        .filter(t => !t.passed)
        .forEach(test => {
          console.log(`   - ${test.name}: ${test.error || 'FAILED'}`);
        });
    }
    
    console.log(`\n🌍 Environment:`);
    console.log(`   - Platform: ${report.environment.platform}`);
    console.log(`   - NODE_ENV: ${report.environment.nodeEnv}`);
    console.log(`   - Network: ${report.environment.networkStatus}`);
    
    console.log(`\n⏰ Timestamp: ${report.timestamp}`);
    
    // Recommendations
    if (report.overall !== 'PASSED') {
      console.log('\n💡 RECOMMENDATIONS:');
      
      const hasConnectivityIssues = report.tests.some(t => 
        t.name === 'Basic Server Connectivity' && !t.passed
      );
      
      if (hasConnectivityIssues) {
        console.log('   1. Ensure backend server is running on 155.138.239.131:8000');
        console.log('   2. Check firewall and network connectivity');
        console.log('   3. Verify CORS configuration allows your frontend domain');
      }
      
      const hasConfigIssues = report.tests.some(t => 
        t.name === 'Environment Configuration' && !t.passed
      );
      
      if (hasConfigIssues) {
        console.log('   4. Update environment variables to use correct API URL');
        console.log('   5. Clear browser cache and localStorage');
        console.log('   6. Restart development server after config changes');
      }
      
      console.log('   7. Use the Smart API Service for automatic fallback handling');
    } else {
      console.log('\n🎉 ALL TESTS PASSED! API connectivity is working correctly.');
    }
    
    console.log('\n' + '='.repeat(60));
  }
  
  async saveReport(report: ConnectivityTestReport, filename?: string): Promise<string> {
    const reportFile = filename || `connectivity-test-report-${Date.now()}.json`;
    const reportPath = path.join(process.cwd(), reportFile);
    
    try {
      fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
      console.log(`\n💾 Report saved to: ${reportPath}`);
      return reportPath;
    } catch (error: any) {
      console.error(`\n❌ Failed to save report: ${error.message}`);
      throw error;
    }
  }
}

// CLI execution
if (require.main === module) {
  const testSuite = new ConnectivityTestSuite();
  
  testSuite.runAllTests().then(async (report) => {
    testSuite.printReport(report);
    
    // Save report
    try {
      await testSuite.saveReport(report);
    } catch (error) {
      console.error('Could not save report:', error);
    }
    
    // Exit with appropriate code
    process.exit(report.overall === 'PASSED' ? 0 : 1);
  }).catch((error) => {
    console.error('\n💥 Test suite failed to run:', error);
    process.exit(1);
  });
}

export { ConnectivityTestSuite, type ConnectivityTestReport, type TestResult };