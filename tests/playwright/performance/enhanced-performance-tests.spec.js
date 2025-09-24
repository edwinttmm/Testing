/**
 * Enhanced Performance Testing for ADAS Camera HIL Testing Platform
 * @fileoverview Comprehensive performance testing with load testing and monitoring
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');
const EnhancedTestHelpers = require('../utils/enhanced-test-helpers');

test.describe('Enhanced Performance Testing', () => {
  test('should measure page load performance with detailed metrics', async ({ page, browser }) => {
    const testName = 'page-load-performance';
    console.log(`🚀 Starting ${testName}`);
    
    const performanceMetrics = await EnhancedTestHelpers.measurePerformance(page, async () => {
      await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    });
    
    console.log('Performance metrics:', performanceMetrics);
    
    // Detailed performance analysis
    const detailedMetrics = await page.evaluate(() => {
      const timing = performance.timing;
      const navigation = performance.getEntriesByType('navigation')[0];
      
      return {
        // Core Web Vitals
        domContentLoaded: timing.domContentLoadedEventEnd - timing.domContentLoadedEventStart,
        loadComplete: timing.loadEventEnd - timing.loadEventStart,
        
        // Navigation timing
        dnsLookup: timing.domainLookupEnd - timing.domainLookupStart,
        tcpConnection: timing.connectEnd - timing.connectStart,
        serverResponse: timing.responseEnd - timing.requestStart,
        domProcessing: timing.domComplete - timing.domLoading,
        
        // Resource timing
        resourceCount: performance.getEntriesByType('resource').length,
        
        // Navigation API (if available)
        navigationTiming: navigation ? {
          domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
          loadEvent: navigation.loadEventEnd - navigation.loadEventStart,
          transferSize: navigation.transferSize
        } : null
      };
    });
    
    console.log('Detailed performance metrics:', detailedMetrics);
    
    // Performance assertions
    expect(performanceMetrics.duration).toBeLessThan(10000); // 10 seconds max
    expect(detailedMetrics.domContentLoaded).toBeLessThan(3000); // 3 seconds for DOM ready
    
    await EnhancedTestHelpers.saveTestResults(testName, {
      basicMetrics: performanceMetrics,
      detailedMetrics,
      thresholds: {
        maxPageLoad: 10000,
        maxDomReady: 3000
      }
    });
  });
  
  test('should perform concurrent user load testing', async ({ browser }) => {
    const testName = 'concurrent-load-testing';
    console.log(`🚀 Starting ${testName}`);
    
    const userCount = 3;
    const testDuration = 30000; // 30 seconds
    
    const loadTestResults = await EnhancedTestHelpers.performLoadTest(browser, userCount, testDuration);
    
    console.log('Load test results:', JSON.stringify(loadTestResults.summary, null, 2));
    
    // Analyze results
    const { summary, results } = loadTestResults;
    
    // Expectations for load test
    expect(summary.totalErrors).toBeLessThan(summary.totalActions * 0.1); // Less than 10% error rate
    expect(summary.avgActionsPerUser).toBeGreaterThan(5); // At least 5 actions per user
    
    // Check individual user performance
    const userErrorRates = results.map(user => ({
      userId: user.userId,
      errorRate: user.errors.length / Math.max(user.actions.length, 1)
    }));
    
    console.log('User error rates:', userErrorRates);
    
    await EnhancedTestHelpers.saveTestResults(testName, {
      loadTestResults,
      userErrorRates,
      testConfiguration: {
        userCount,
        testDuration,
        targetUrl: 'http://localhost:3000'
      }
    });
  });
  
  test('should test API response times under load', async ({ page }) => {
    const testName = 'api-performance-load';
    console.log(`🚀 Starting ${testName}`);
    
    const endpoints = [
      '/health',
      '/api/projects',
      '/api/videos',
      '/api/test-sessions',
      '/api/dashboard/stats'
    ];
    
    const apiResults = [];
    const requestCount = 10; // Multiple requests per endpoint
    
    for (const endpoint of endpoints) {
      const endpointResults = [];
      
      for (let i = 0; i < requestCount; i++) {
        const startTime = Date.now();
        
        try {
          const response = await page.request.get(`http://localhost:8000${endpoint}`);
          const endTime = Date.now();
          
          endpointResults.push({
            requestNumber: i + 1,
            responseTime: endTime - startTime,
            status: response.status(),
            success: response.ok()
          });
        } catch (error) {
          endpointResults.push({
            requestNumber: i + 1,
            responseTime: null,
            status: null,
            success: false,
            error: error.message
          });
        }
      }
      
      // Calculate statistics for this endpoint
      const successfulRequests = endpointResults.filter(r => r.success);
      const responseTimes = successfulRequests.map(r => r.responseTime);
      
      const stats = {
        endpoint,
        totalRequests: requestCount,
        successfulRequests: successfulRequests.length,
        successRate: successfulRequests.length / requestCount,
        avgResponseTime: responseTimes.length > 0 ? responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length : null,
        minResponseTime: responseTimes.length > 0 ? Math.min(...responseTimes) : null,
        maxResponseTime: responseTimes.length > 0 ? Math.max(...responseTimes) : null,
        requests: endpointResults
      };
      
      apiResults.push(stats);
      
      console.log(`${endpoint}: ${stats.successRate * 100}% success, avg ${stats.avgResponseTime}ms`);
      
      // Performance expectations
      expect(stats.successRate).toBeGreaterThan(0.8); // 80% success rate minimum
      if (stats.avgResponseTime) {
        expect(stats.avgResponseTime).toBeLessThan(2000); // 2 second average max
      }
    }
    
    await EnhancedTestHelpers.saveTestResults(testName, {
      apiPerformanceResults: apiResults,
      testConfiguration: {
        requestsPerEndpoint: requestCount,
        baseUrl: 'http://localhost:8000'
      }
    });
  });
  
  test('should test memory usage and resource consumption', async ({ page }) => {
    const testName = 'memory-resource-testing';
    console.log(`🚀 Starting ${testName}`);
    
    // Initial memory measurement
    const initialMemory = await page.evaluate(() => {
      if (performance.memory) {
        return {
          usedJSHeapSize: performance.memory.usedJSHeapSize,
          totalJSHeapSize: performance.memory.totalJSHeapSize,
          jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
        };
      }
      return null;
    });
    
    console.log('Initial memory:', initialMemory);
    
    // Perform memory-intensive operations
    const operations = [
      () => page.reload(),
      () => page.evaluate(() => {
        // Create some objects to test memory
        const data = [];
        for (let i = 0; i < 1000; i++) {
          data.push({ id: i, data: 'test'.repeat(100) });
        }
        window.testData = data;
      }),
      () => page.goto('http://localhost:3000')
    ];
    
    const memoryMeasurements = [initialMemory];
    
    for (const operation of operations) {
      await operation();
      await page.waitForTimeout(1000); // Wait for stabilization
      
      const memory = await page.evaluate(() => {
        if (performance.memory) {
          return {
            usedJSHeapSize: performance.memory.usedJSHeapSize,
            totalJSHeapSize: performance.memory.totalJSHeapSize,
            jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
          };
        }
        return null;
      });
      
      memoryMeasurements.push(memory);
    }
    
    console.log('Memory measurements:', memoryMeasurements);
    
    // Resource count analysis
    const resourceCounts = await page.evaluate(() => {
      const resources = performance.getEntriesByType('resource');
      const resourceTypes = {};
      
      resources.forEach(resource => {
        const type = resource.initiatorType || 'other';
        resourceTypes[type] = (resourceTypes[type] || 0) + 1;
      });
      
      return {
        totalResources: resources.length,
        resourceTypes,
        largestResources: resources
          .sort((a, b) => (b.transferSize || 0) - (a.transferSize || 0))
          .slice(0, 10)
          .map(r => ({
            name: r.name.split('/').pop(),
            transferSize: r.transferSize,
            duration: r.duration
          }))
      };
    });
    
    console.log('Resource analysis:', resourceCounts);
    
    // Memory usage should not grow excessively
    if (initialMemory && memoryMeasurements.length > 1) {
      const finalMemory = memoryMeasurements[memoryMeasurements.length - 1];
      const memoryGrowth = finalMemory.usedJSHeapSize - initialMemory.usedJSHeapSize;
      const memoryGrowthMB = memoryGrowth / (1024 * 1024);
      
      console.log(`Memory growth: ${memoryGrowthMB.toFixed(2)}MB`);
      
      // Memory should not grow more than 50MB during basic operations
      expect(memoryGrowthMB).toBeLessThan(50);
    }
    
    // Resource count should be reasonable
    expect(resourceCounts.totalResources).toBeLessThan(200);
    
    await EnhancedTestHelpers.saveTestResults(testName, {
      memoryMeasurements,
      resourceCounts,
      memoryGrowthAnalysis: initialMemory ? {
        initialUsed: initialMemory.usedJSHeapSize,
        finalUsed: memoryMeasurements[memoryMeasurements.length - 1]?.usedJSHeapSize,
        growthBytes: memoryMeasurements[memoryMeasurements.length - 1]?.usedJSHeapSize - initialMemory.usedJSHeapSize
      } : null
    });
  });
  
  test('should test network performance under different conditions', async ({ page }) => {
    const testName = 'network-performance-conditions';
    console.log(`🚀 Starting ${testName}`);
    
    const networkConditions = ['fast', 'slow'];
    const results = [];
    
    for (const condition of networkConditions) {
      console.log(`Testing network condition: ${condition}`);
      
      // Apply network condition
      await EnhancedTestHelpers.simulateNetworkConditions(page, condition);
      
      const startTime = Date.now();
      
      try {
        // Test page load under this condition
        await page.goto('http://localhost:3000', { 
          waitUntil: 'networkidle',
          timeout: condition === 'slow' ? 30000 : 15000
        });
        
        const loadTime = Date.now() - startTime;
        
        // Test API calls under this condition
        const apiStartTime = Date.now();
        const apiResponse = await page.request.get('http://localhost:8000/api/projects');
        const apiTime = Date.now() - apiStartTime;
        
        results.push({
          condition,
          pageLoadTime: loadTime,
          apiResponseTime: apiTime,
          apiSuccess: apiResponse.ok(),
          success: true
        });
        
        console.log(`${condition} network - Page: ${loadTime}ms, API: ${apiTime}ms`);
        
      } catch (error) {
        results.push({
          condition,
          pageLoadTime: null,
          apiResponseTime: null,
          apiSuccess: false,
          success: false,
          error: error.message
        });
        
        console.log(`${condition} network failed: ${error.message}`);
      }
    }
    
    // Analyze performance differences
    const fastResult = results.find(r => r.condition === 'fast');
    const slowResult = results.find(r => r.condition === 'slow');
    
    let performanceComparison = null;
    if (fastResult?.success && slowResult?.success) {
      performanceComparison = {
        pageLoadDifference: slowResult.pageLoadTime - fastResult.pageLoadTime,
        apiResponseDifference: slowResult.apiResponseTime - fastResult.apiResponseTime,
        slowdownFactor: {
          pageLoad: slowResult.pageLoadTime / fastResult.pageLoadTime,
          api: slowResult.apiResponseTime / fastResult.apiResponseTime
        }
      };
      
      console.log('Performance comparison:', performanceComparison);
    }
    
    await EnhancedTestHelpers.saveTestResults(testName, {
      networkConditionResults: results,
      performanceComparison,
      testConfiguration: {
        conditions: networkConditions,
        baseUrl: 'http://localhost:3000'
      }
    });
    
    // At least fast network should work
    expect(fastResult?.success).toBeTruthy();
  });
  
  test('should test real-time WebSocket performance', async ({ page }) => {
    const testName = 'websocket-performance';
    console.log(`🚀 Starting ${testName}`);
    
    // Test WebSocket connection and message performance
    const wsPerformance = await page.evaluate(async () => {
      return new Promise((resolve) => {
        const results = {
          connectionTime: null,
          messageLatencies: [],
          messagesReceived: 0,
          connectionSuccess: false,
          error: null
        };
        
        try {
          const startTime = Date.now();
          const ws = new WebSocket('ws://localhost:8000/ws/progress');
          
          ws.onopen = () => {
            results.connectionTime = Date.now() - startTime;
            results.connectionSuccess = true;
            
            // Send test messages to measure latency
            for (let i = 0; i < 5; i++) {
              setTimeout(() => {
                const msgStartTime = Date.now();
                ws.send(JSON.stringify({ test: true, id: i, timestamp: msgStartTime }));
              }, i * 1000);
            }
            
            // Close connection after tests
            setTimeout(() => {
              ws.close();
              resolve(results);
            }, 8000);
          };
          
          ws.onmessage = (event) => {
            results.messagesReceived++;
            
            try {
              const data = JSON.parse(event.data);
              if (data.timestamp) {
                const latency = Date.now() - data.timestamp;
                results.messageLatencies.push(latency);
              }
            } catch (e) {
              // Ignore parsing errors
            }
          };
          
          ws.onerror = (error) => {
            results.error = 'WebSocket error';
            resolve(results);
          };
          
          // Timeout after 10 seconds
          setTimeout(() => {
            if (!results.connectionSuccess) {
              results.error = 'Connection timeout';
            }
            ws.close();
            resolve(results);
          }, 10000);
          
        } catch (error) {
          results.error = error.message;
          resolve(results);
        }
      });
    });
    
    console.log('WebSocket performance results:', wsPerformance);
    
    // Calculate statistics if we have latency data
    let latencyStats = null;
    if (wsPerformance.messageLatencies.length > 0) {
      const latencies = wsPerformance.messageLatencies;
      latencyStats = {
        avgLatency: latencies.reduce((a, b) => a + b, 0) / latencies.length,
        minLatency: Math.min(...latencies),
        maxLatency: Math.max(...latencies),
        messageCount: latencies.length
      };
      
      console.log('Latency statistics:', latencyStats);
    }
    
    await EnhancedTestHelpers.saveTestResults(testName, {
      webSocketPerformance: wsPerformance,
      latencyStatistics: latencyStats,
      testConfiguration: {
        wsUrl: 'ws://localhost:8000/ws/progress',
        testDuration: 8000,
        messageCount: 5
      }
    });
    
    // WebSocket connection should succeed
    expect(wsPerformance.connectionSuccess).toBeTruthy();
    
    // Connection time should be reasonable
    if (wsPerformance.connectionTime) {
      expect(wsPerformance.connectionTime).toBeLessThan(3000); // 3 seconds max
    }
  });
});

test.afterAll(async () => {
  console.log('🏁 Enhanced Performance tests completed');
});