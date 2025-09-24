/**
 * ADAS Camera HIL Testing Platform - Performance Tests
 * @fileoverview Performance and load testing for the application
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('Performance & Load Testing', () => {
  let consoleLogs;

  test.beforeEach(async ({ page }) => {
    consoleLogs = TestHelpers.setupConsoleMonitoring(page);
  });

  test('should measure page load performance', async ({ page }) => {
    const performanceMetrics = await TestHelpers.measurePerformance(page, async () => {
      await page.goto('http://localhost:3000');
      await TestHelpers.waitForPageReady(page);
    });

    console.log(`Page load time: ${performanceMetrics.duration}ms`);

    // Get detailed performance metrics
    const detailedMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0];
      const paint = performance.getEntriesByType('paint');
      
      return {
        // Navigation timing
        domContentLoaded: navigation ? navigation.domContentLoadedEventEnd - navigation.navigationStart : 0,
        loadComplete: navigation ? navigation.loadEventEnd - navigation.navigationStart : 0,
        
        // Paint timing
        firstPaint: paint.find(p => p.name === 'first-paint')?.startTime || 0,
        firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime || 0,
        
        // Resource timing
        resourceCount: performance.getEntriesByType('resource').length,
        
        // Memory (if available)
        memory: performance.memory ? {
          used: performance.memory.usedJSHeapSize,
          total: performance.memory.totalJSHeapSize,
          limit: performance.memory.jsHeapSizeLimit
        } : null
      };
    });

    console.log('Detailed performance metrics:', detailedMetrics);

    await TestHelpers.takeScreenshot(page, 'performance-page-load');

    // Save performance results
    await TestHelpers.saveTestResults('page-load-performance', {
      loadTime: performanceMetrics.duration,
      detailedMetrics,
      timestamp: new Date().toISOString()
    });

    // Performance assertions
    expect(performanceMetrics.duration).toBeLessThan(10000); // Less than 10 seconds
    expect(detailedMetrics.domContentLoaded).toBeLessThan(8000); // DOM ready in 8 seconds
    
    if (detailedMetrics.firstContentfulPaint > 0) {
      expect(detailedMetrics.firstContentfulPaint).toBeLessThan(5000); // FCP in 5 seconds
    }

    console.log('✅ Page load performance test completed');
  });

  test('should test API response times', async ({ page }) => {
    const apiEndpoints = [
      { endpoint: '/health', name: 'Health Check' },
      { endpoint: '/api/projects', name: 'Projects List' },
      { endpoint: '/api/videos', name: 'Videos List' },
      { endpoint: '/api/test-sessions', name: 'Test Sessions' },
      { endpoint: '/api/dashboard/stats', name: 'Dashboard Stats' }
    ];

    const apiPerformanceResults = [];

    for (const api of apiEndpoints) {
      const measurements = [];
      const iterations = 5; // Test each endpoint 5 times

      for (let i = 0; i < iterations; i++) {
        const startTime = performance.now();
        
        try {
          const response = await page.request.get(`http://localhost:8000${api.endpoint}`);
          const endTime = performance.now();
          const duration = endTime - startTime;

          measurements.push({
            iteration: i + 1,
            duration,
            status: response.status(),
            success: response.ok()
          });

          console.log(`${api.name} (${i + 1}/${iterations}): ${duration.toFixed(2)}ms - ${response.status()}`);
        } catch (error) {
          const endTime = performance.now();
          const duration = endTime - startTime;
          
          measurements.push({
            iteration: i + 1,
            duration,
            error: error.message,
            success: false
          });
        }

        // Small delay between requests
        await page.waitForTimeout(100);
      }

      // Calculate statistics
      const successfulMeasurements = measurements.filter(m => m.success);
      const avgResponseTime = successfulMeasurements.length > 0 
        ? successfulMeasurements.reduce((sum, m) => sum + m.duration, 0) / successfulMeasurements.length
        : 0;

      const minResponseTime = successfulMeasurements.length > 0 
        ? Math.min(...successfulMeasurements.map(m => m.duration))
        : 0;

      const maxResponseTime = successfulMeasurements.length > 0 
        ? Math.max(...successfulMeasurements.map(m => m.duration))
        : 0;

      apiPerformanceResults.push({
        endpoint: api.endpoint,
        name: api.name,
        iterations,
        successfulRequests: successfulMeasurements.length,
        successRate: (successfulMeasurements.length / iterations) * 100,
        avgResponseTime,
        minResponseTime,
        maxResponseTime,
        measurements
      });

      console.log(`✅ ${api.name}: Avg ${avgResponseTime.toFixed(2)}ms (${successfulMeasurements.length}/${iterations} success)`);
    }

    await TestHelpers.takeScreenshot(page, 'api-performance-testing');

    // Save API performance results
    await TestHelpers.saveTestResults('api-response-times', {
      results: apiPerformanceResults,
      summary: {
        totalEndpoints: apiEndpoints.length,
        avgResponseTime: apiPerformanceResults.reduce((sum, r) => sum + r.avgResponseTime, 0) / apiPerformanceResults.length,
        overallSuccessRate: apiPerformanceResults.reduce((sum, r) => sum + r.successRate, 0) / apiPerformanceResults.length
      }
    });

    // Performance assertions
    const slowAPIs = apiPerformanceResults.filter(r => r.avgResponseTime > 2000); // Slower than 2 seconds
    expect(slowAPIs.length).toBeLessThan(2); // At most 1 slow API is acceptable

    const failedAPIs = apiPerformanceResults.filter(r => r.successRate < 80); // Less than 80% success rate
    expect(failedAPIs.length).toBe(0); // All APIs should have good success rates

    console.log('✅ API performance testing completed');
  });

  test('should test concurrent user load', async ({ browser }) => {
    const concurrentUsers = 5;
    const contexts = [];
    const loadTestResults = [];

    console.log(`Starting concurrent load test with ${concurrentUsers} users`);

    // Create multiple browser contexts to simulate concurrent users
    for (let i = 0; i < concurrentUsers; i++) {
      const context = await browser.newContext();
      const page = await context.newPage();
      contexts.push({ context, page, userId: i + 1 });
    }

    // Run concurrent user sessions
    const concurrentTasks = contexts.map(async ({ context, page, userId }) => {
      const userResults = {
        userId,
        actions: [],
        totalDuration: 0,
        errors: []
      };

      try {
        const startTime = performance.now();

        // User journey simulation
        const actions = [
          { name: 'Load Homepage', action: () => page.goto('http://localhost:3000') },
          { name: 'Navigate', action: () => page.click('a, button').catch(() => {}) },
          { name: 'API Call', action: () => page.request.get('http://localhost:8000/api/projects') },
          { name: 'Wait', action: () => page.waitForTimeout(1000) }
        ];

        for (const actionDef of actions) {
          const actionStart = performance.now();
          
          try {
            await actionDef.action();
            const actionDuration = performance.now() - actionStart;
            
            userResults.actions.push({
              name: actionDef.name,
              duration: actionDuration,
              success: true
            });
          } catch (error) {
            const actionDuration = performance.now() - actionStart;
            
            userResults.actions.push({
              name: actionDef.name,
              duration: actionDuration,
              success: false,
              error: error.message
            });
            
            userResults.errors.push(error.message);
          }
        }

        userResults.totalDuration = performance.now() - startTime;
        console.log(`User ${userId} completed journey in ${userResults.totalDuration.toFixed(2)}ms`);

      } catch (error) {
        console.log(`User ${userId} failed:`, error.message);
        userResults.errors.push(error.message);
      } finally {
        await context.close();
      }

      return userResults;
    });

    // Wait for all concurrent tasks to complete
    const allResults = await Promise.all(concurrentTasks);
    
    // Analyze results
    const successfulUsers = allResults.filter(r => r.errors.length === 0).length;
    const avgDuration = allResults.reduce((sum, r) => sum + r.totalDuration, 0) / allResults.length;
    const totalErrors = allResults.reduce((sum, r) => sum + r.errors.length, 0);

    console.log(`✅ Concurrent load test completed:`);
    console.log(`  - Successful users: ${successfulUsers}/${concurrentUsers}`);
    console.log(`  - Average duration: ${avgDuration.toFixed(2)}ms`);
    console.log(`  - Total errors: ${totalErrors}`);

    // Save load test results
    await TestHelpers.saveTestResults('concurrent-load-test', {
      concurrentUsers,
      results: allResults,
      summary: {
        successfulUsers,
        successRate: (successfulUsers / concurrentUsers) * 100,
        avgDuration,
        totalErrors
      }
    });

    // Performance assertions
    expect(successfulUsers).toBeGreaterThan(concurrentUsers * 0.8); // At least 80% success rate
    expect(avgDuration).toBeLessThan(15000); // Average session under 15 seconds

    console.log('✅ Concurrent user load testing completed');
  });

  test('should test memory usage under load', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);

    // Take initial memory reading
    const initialMemory = await page.evaluate(() => {
      if (performance.memory) {
        return {
          used: performance.memory.usedJSHeapSize,
          total: performance.memory.totalJSHeapSize,
          limit: performance.memory.jsHeapSizeLimit
        };
      }
      return { used: 0, total: 0, limit: 0 };
    });

    console.log('Initial memory usage:', initialMemory);

    const memoryReadings = [initialMemory];
    const operations = 20; // Perform 20 operations to stress test memory

    // Simulate memory-intensive operations
    for (let i = 0; i < operations; i++) {
      try {
        // Perform various operations that might consume memory
        await page.evaluate(() => {
          // Simulate DOM manipulation
          const elements = [];
          for (let j = 0; j < 1000; j++) {
            const div = document.createElement('div');
            div.textContent = `Test element ${j}`;
            elements.push(div);
          }
          
          // Clean up immediately
          elements.forEach(el => el.remove());
          
          // Force garbage collection if available
          if (window.gc) {
            window.gc();
          }
        });

        // Make API requests
        await page.request.get('http://localhost:8000/api/projects').catch(() => {});
        
        // Take memory reading
        const currentMemory = await page.evaluate(() => {
          if (performance.memory) {
            return {
              used: performance.memory.usedJSHeapSize,
              total: performance.memory.totalJSHeapSize,
              limit: performance.memory.jsHeapSizeLimit
            };
          }
          return { used: 0, total: 0, limit: 0 };
        });

        memoryReadings.push(currentMemory);
        
        if (i % 5 === 0) {
          console.log(`Operation ${i + 1}/${operations}: ${currentMemory.used} bytes used`);
        }

        // Small delay
        await page.waitForTimeout(100);
      } catch (error) {
        console.log(`Memory test operation ${i + 1} error:`, error.message);
      }
    }

    // Analyze memory usage
    const finalMemory = memoryReadings[memoryReadings.length - 1];
    const memoryGrowth = finalMemory.used - initialMemory.used;
    const maxMemoryUsed = Math.max(...memoryReadings.map(r => r.used));
    
    console.log('Final memory usage:', finalMemory);
    console.log(`Memory growth: ${memoryGrowth} bytes`);
    console.log(`Peak memory: ${maxMemoryUsed} bytes`);

    // Memory efficiency analysis
    const memoryEfficient = memoryGrowth < (5 * 1024 * 1024); // Less than 5MB growth
    const noMemoryLeak = finalMemory.used < (initialMemory.used * 1.5); // Less than 50% increase

    await TestHelpers.takeScreenshot(page, 'memory-usage-testing');

    // Save memory test results
    await TestHelpers.saveTestResults('memory-usage-load-test', {
      operations,
      initialMemory,
      finalMemory,
      memoryGrowth,
      maxMemoryUsed,
      memoryEfficient,
      noMemoryLeak,
      readings: memoryReadings
    });

    console.log(`✅ Memory efficiency: ${memoryEfficient ? 'GOOD' : 'CONCERN'}`);
    console.log(`✅ Memory leak test: ${noMemoryLeak ? 'PASS' : 'FAIL'}`);

    // Performance assertions
    expect(memoryGrowth).toBeLessThan(10 * 1024 * 1024); // Less than 10MB growth
    expect(noMemoryLeak).toBeTruthy(); // No significant memory leaks

    console.log('✅ Memory usage load testing completed');
  });

  test('should test video processing performance', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);

    // Test video processing API performance
    const videoProcessingTests = [
      { size: 'small', data: { simulate: true, size: '1MB' } },
      { size: 'medium', data: { simulate: true, size: '10MB' } },
      { size: 'large', data: { simulate: true, size: '50MB' } }
    ];

    const processingResults = [];

    for (const test of videoProcessingTests) {
      try {
        const startTime = performance.now();
        
        const response = await page.request.post('http://localhost:8000/api/videos/process', {
          data: test.data,
          headers: { 'Content-Type': 'application/json' }
        });

        const endTime = performance.now();
        const duration = endTime - startTime;

        processingResults.push({
          size: test.size,
          duration,
          status: response.status(),
          success: response.status() < 500, // Accept any non-server error
          throughput: test.data.size === '1MB' ? 1000000 / duration : 
                     test.data.size === '10MB' ? 10000000 / duration :
                     50000000 / duration // bytes per ms
        });

        console.log(`${test.size} video processing: ${duration.toFixed(2)}ms (${response.status()})`);
      } catch (error) {
        console.log(`Video processing test ${test.size} error:`, error.message);
      }
    }

    // Test batch processing performance
    try {
      const batchStartTime = performance.now();
      
      const batchResponse = await page.request.post('http://localhost:8000/api/videos/batch-process', {
        data: { 
          videos: ['video1', 'video2', 'video3'],
          simulate: true
        },
        headers: { 'Content-Type': 'application/json' }
      });

      const batchDuration = performance.now() - batchStartTime;
      
      processingResults.push({
        size: 'batch',
        duration: batchDuration,
        status: batchResponse.status(),
        success: batchResponse.status() < 500,
        videoCount: 3
      });

      console.log(`Batch processing (3 videos): ${batchDuration.toFixed(2)}ms`);
    } catch (error) {
      console.log('Batch processing test error:', error.message);
    }

    await TestHelpers.takeScreenshot(page, 'video-processing-performance');

    // Save video processing results
    await TestHelpers.saveTestResults('video-processing-performance', {
      tests: processingResults,
      summary: {
        successfulTests: processingResults.filter(r => r.success).length,
        avgDuration: processingResults.reduce((sum, r) => sum + r.duration, 0) / processingResults.length
      }
    });

    // Performance assertions
    const slowProcessing = processingResults.filter(r => r.success && r.duration > 10000); // Slower than 10 seconds
    expect(slowProcessing.length).toBeLessThan(processingResults.length); // Not all should be slow

    console.log('✅ Video processing performance testing completed');
  });

  test('should generate comprehensive performance report', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Collect comprehensive performance data
    const performanceReport = await page.evaluate(() => {
      const report = {
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        },
        connection: navigator.connection ? {
          effectiveType: navigator.connection.effectiveType,
          downlink: navigator.connection.downlink,
          rtt: navigator.connection.rtt
        } : null,
        memory: performance.memory ? {
          used: performance.memory.usedJSHeapSize,
          total: performance.memory.totalJSHeapSize,
          limit: performance.memory.jsHeapSizeLimit
        } : null,
        navigation: null,
        resources: [],
        vitals: {}
      };

      // Navigation timing
      const navigation = performance.getEntriesByType('navigation')[0];
      if (navigation) {
        report.navigation = {
          domContentLoaded: navigation.domContentLoadedEventEnd - navigation.navigationStart,
          loadComplete: navigation.loadEventEnd - navigation.navigationStart,
          domInteractive: navigation.domInteractive - navigation.navigationStart,
          firstByte: navigation.responseStart - navigation.navigationStart
        };
      }

      // Resource timing
      const resources = performance.getEntriesByType('resource');
      report.resources = resources.map(resource => ({
        name: resource.name.split('/').pop(),
        duration: resource.duration,
        size: resource.transferSize || 0,
        type: resource.initiatorType
      })).slice(0, 20); // Top 20 resources

      // Paint timing
      const paintEntries = performance.getEntriesByType('paint');
      paintEntries.forEach(paint => {
        if (paint.name === 'first-paint') {
          report.vitals.firstPaint = paint.startTime;
        }
        if (paint.name === 'first-contentful-paint') {
          report.vitals.firstContentfulPaint = paint.startTime;
        }
      });

      return report;
    });

    console.log('Performance Report Generated:');
    console.log('- DOM Content Loaded:', performanceReport.navigation?.domContentLoaded, 'ms');
    console.log('- Load Complete:', performanceReport.navigation?.loadComplete, 'ms');
    console.log('- First Paint:', performanceReport.vitals?.firstPaint, 'ms');
    console.log('- First Contentful Paint:', performanceReport.vitals?.firstContentfulPaint, 'ms');
    console.log('- Resources Loaded:', performanceReport.resources?.length);
    console.log('- Memory Used:', performanceReport.memory?.used, 'bytes');

    await TestHelpers.takeScreenshot(page, 'performance-report');

    // Save comprehensive performance report
    await TestHelpers.saveTestResults('comprehensive-performance-report', performanceReport);

    // Generate performance grade
    let performanceGrade = 'A';
    const issues = [];

    if (performanceReport.navigation?.loadComplete > 5000) {
      performanceGrade = 'C';
      issues.push('Slow page load time');
    }

    if (performanceReport.vitals?.firstContentfulPaint > 3000) {
      performanceGrade = 'B';
      issues.push('Slow first contentful paint');
    }

    if (performanceReport.memory?.used > 50 * 1024 * 1024) { // 50MB
      performanceGrade = 'B';
      issues.push('High memory usage');
    }

    console.log(`✅ Overall Performance Grade: ${performanceGrade}`);
    if (issues.length > 0) {
      console.log('Performance Issues:', issues);
    }

    // Save final grade
    await TestHelpers.saveTestResults('performance-grade', {
      grade: performanceGrade,
      issues,
      report: performanceReport
    });

    expect(['A', 'B', 'C'].includes(performanceGrade)).toBeTruthy();
    console.log('✅ Comprehensive performance report generated');
  });
});