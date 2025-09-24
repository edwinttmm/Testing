const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('Performance and Load Testing', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
    await helpers.login();
  });

  test('should measure page load performance', async ({ page }) => {
    const performanceEntries = [];
    
    // Measure dashboard load time
    const startTime = Date.now();
    await page.goto('/dashboard');
    await page.waitForLoadState('domcontentloaded');
    const domContentLoadedTime = Date.now();
    await page.waitForLoadState('networkidle');
    const networkIdleTime = Date.now();
    
    const loadTimes = {
      total_load_time: networkIdleTime - startTime,
      dom_content_loaded: domContentLoadedTime - startTime,
      network_idle: networkIdleTime - domContentLoadedTime
    };
    
    expect(loadTimes.total_load_time).toBeLessThan(5000); // Under 5 seconds
    expect(loadTimes.dom_content_loaded).toBeLessThan(3000); // Under 3 seconds
    
    await helpers.takeScreenshot('dashboard-loaded-performance');
    
    // Measure performance metrics from browser
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0];
      return {
        dns_lookup: navigation.domainLookupEnd - navigation.domainLookupStart,
        connection: navigation.connectEnd - navigation.connectStart,
        request: navigation.responseStart - navigation.requestStart,
        response: navigation.responseEnd - navigation.responseStart,
        dom_processing: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        load_event: navigation.loadEventEnd - navigation.loadEventStart
      };
    });
    
    await helpers.saveTestResults('page-load-performance', {
      load_times: loadTimes,
      performance_metrics: performanceMetrics,
      timestamp: Date.now()
    });
  });

  test('should measure API response times', async ({ page }) => {
    const apiEndpoints = [
      { url: '/health', method: 'GET' },
      { url: '/auth/verify', method: 'GET' },
      { url: '/ml/models', method: 'GET' },
      { url: '/hardware/labjack/status', method: 'GET' },
      { url: '/projects', method: 'GET' }
    ];
    
    const apiPerformance = [];
    
    for (const endpoint of apiEndpoints) {
      const measurements = [];
      
      // Test each endpoint 5 times
      for (let i = 0; i < 5; i++) {
        const startTime = Date.now();
        
        const response = await page.request.get(`http://localhost:8000${endpoint.url}`);
        
        const endTime = Date.now();
        const responseTime = endTime - startTime;
        
        measurements.push({
          iteration: i + 1,
          response_time: responseTime,
          status: response.status(),
          timestamp: Date.now()
        });
        
        expect(response.status()).toBeLessThan(500); // No server errors
        expect(responseTime).toBeLessThan(2000); // Under 2 seconds
      }
      
      const avgResponseTime = measurements.reduce((sum, m) => sum + m.response_time, 0) / 5;
      const minResponseTime = Math.min(...measurements.map(m => m.response_time));
      const maxResponseTime = Math.max(...measurements.map(m => m.response_time));
      
      apiPerformance.push({
        endpoint: endpoint.url,
        avg_response_time: avgResponseTime,
        min_response_time: minResponseTime,
        max_response_time: maxResponseTime,
        measurements: measurements
      });
    }
    
    await helpers.saveTestResults('api-performance', {
      endpoints_tested: apiEndpoints.length,
      api_performance: apiPerformance,
      timestamp: Date.now()
    });
  });

  test('should test ML inference performance under load', async ({ page }) => {
    const concurrentRequests = 10;
    const testImage = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAhEAACAQMDBQAAAAAAAAAAAAABAgMABAUGIWGRkqGx/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAhEQACAQIHAQAAAAAAAAAAAAABAgADBAUREiExYUFxkf/aAAwDAQACEQMRAD8A0XGAlCaSSWghRAQAAEBEQAQBAQAAQABAAA=';
    
    const loadTestResults = [];
    
    // Test concurrent ML inference requests
    const startTime = Date.now();
    
    const promises = Array(concurrentRequests).fill(null).map(async (_, index) => {
      const requestStartTime = Date.now();
      
      try {
        const response = await page.request.post('http://localhost:8000/ml/yolo/inference', {
          data: {
            image_data: testImage,
            confidence: 0.5,
            request_id: `load_test_${index}`
          }
        });
        
        const requestEndTime = Date.now();
        const responseTime = requestEndTime - requestStartTime;
        const data = await response.json();
        
        return {
          request_id: index,
          status: response.status(),
          response_time: responseTime,
          inference_time: data.inference_time,
          success: response.status() === 200,
          timestamp: Date.now()
        };
      } catch (error) {
        return {
          request_id: index,
          status: 'error',
          response_time: Date.now() - requestStartTime,
          error: error.message,
          success: false,
          timestamp: Date.now()
        };
      }
    });
    
    const results = await Promise.all(promises);
    const totalTime = Date.now() - startTime;
    
    const successfulRequests = results.filter(r => r.success);
    const failedRequests = results.filter(r => !r.success);
    
    const avgResponseTime = successfulRequests.reduce((sum, r) => sum + r.response_time, 0) / successfulRequests.length;
    const avgInferenceTime = successfulRequests.reduce((sum, r) => sum + (r.inference_time || 0), 0) / successfulRequests.length;
    
    expect(successfulRequests.length).toBeGreaterThan(concurrentRequests * 0.8); // At least 80% success rate
    expect(avgResponseTime).toBeLessThan(10000); // Under 10 seconds average
    
    await helpers.saveTestResults('ml-load-testing', {
      concurrent_requests: concurrentRequests,
      total_time: totalTime,
      successful_requests: successfulRequests.length,
      failed_requests: failedRequests.length,
      success_rate: (successfulRequests.length / concurrentRequests) * 100,
      avg_response_time: avgResponseTime,
      avg_inference_time: avgInferenceTime,
      all_results: results,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('ml-load-test-completed');
  });

  test('should measure memory usage during operations', async ({ page }) => {
    // Monitor memory usage during various operations
    const memorySnapshots = [];
    
    // Initial memory snapshot
    const initialMetrics = await page.evaluate(() => ({
      used_heap: performance.memory?.usedJSHeapSize || 0,
      total_heap: performance.memory?.totalJSHeapSize || 0,
      heap_limit: performance.memory?.jsHeapSizeLimit || 0
    }));
    
    memorySnapshots.push({
      operation: 'initial',
      metrics: initialMetrics,
      timestamp: Date.now()
    });
    
    // Load dashboard
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    
    const dashboardMetrics = await page.evaluate(() => ({
      used_heap: performance.memory?.usedJSHeapSize || 0,
      total_heap: performance.memory?.totalJSHeapSize || 0,
      heap_limit: performance.memory?.jsHeapSizeLimit || 0
    }));
    
    memorySnapshots.push({
      operation: 'dashboard_loaded',
      metrics: dashboardMetrics,
      timestamp: Date.now()
    });
    
    // Simulate heavy operations
    await page.click('[data-testid="video-processing-tab"]');
    await page.waitForTimeout(2000);
    
    const videoTabMetrics = await page.evaluate(() => ({
      used_heap: performance.memory?.usedJSHeapSize || 0,
      total_heap: performance.memory?.totalJSHeapSize || 0,
      heap_limit: performance.memory?.jsHeapSizeLimit || 0
    }));
    
    memorySnapshots.push({
      operation: 'video_tab_loaded',
      metrics: videoTabMetrics,
      timestamp: Date.now()
    });
    
    // Check for memory leaks (simplified)
    const memoryIncrease = dashboardMetrics.used_heap - initialMetrics.used_heap;
    const memoryUsagePercent = (dashboardMetrics.used_heap / dashboardMetrics.heap_limit) * 100;
    
    expect(memoryUsagePercent).toBeLessThan(80); // Should use less than 80% of available heap
    
    await helpers.saveTestResults('memory-usage', {
      snapshots: memorySnapshots,
      memory_increase_bytes: memoryIncrease,
      memory_usage_percent: memoryUsagePercent,
      potential_leak: memoryIncrease > 50 * 1024 * 1024, // More than 50MB increase
      timestamp: Date.now()
    });
  });

  test('should test database performance', async ({ page }) => {
    const dbOperations = [
      { operation: 'create_project', method: 'POST', endpoint: '/projects' },
      { operation: 'list_projects', method: 'GET', endpoint: '/projects' },
      { operation: 'get_project', method: 'GET', endpoint: '/projects/1' },
      { operation: 'update_project', method: 'PUT', endpoint: '/projects/1' },
      { operation: 'delete_project', method: 'DELETE', endpoint: '/projects/1' }
    ];
    
    const dbPerformance = [];
    
    for (const op of dbOperations) {
      const measurements = [];
      
      for (let i = 0; i < 3; i++) {
        const startTime = Date.now();
        
        let response;
        const data = op.operation === 'create_project' ? 
          { name: `Test Project ${Date.now()}`, description: 'Test project' } : {};
        
        switch (op.method) {
          case 'POST':
            response = await page.request.post(`http://localhost:8000${op.endpoint}`, { data });
            break;
          case 'PUT':
            response = await page.request.put(`http://localhost:8000${op.endpoint}`, { data });
            break;
          case 'DELETE':
            response = await page.request.delete(`http://localhost:8000${op.endpoint}`);
            break;
          default:
            response = await page.request.get(`http://localhost:8000${op.endpoint}`);
        }
        
        const endTime = Date.now();
        const responseTime = endTime - startTime;
        
        measurements.push({
          iteration: i + 1,
          response_time: responseTime,
          status: response.status(),
          timestamp: Date.now()
        });
        
        // Add small delay between operations
        await page.waitForTimeout(100);
      }
      
      const avgResponseTime = measurements.reduce((sum, m) => sum + m.response_time, 0) / 3;
      
      dbPerformance.push({
        operation: op.operation,
        avg_response_time: avgResponseTime,
        measurements: measurements
      });
      
      expect(avgResponseTime).toBeLessThan(1000); // Database operations under 1 second
    }
    
    await helpers.saveTestResults('database-performance', {
      operations_tested: dbOperations.length,
      db_performance: dbPerformance,
      timestamp: Date.now()
    });
  });

  test('should test WebSocket performance under load', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Setup WebSocket monitoring
    await page.addInitScript(() => {
      window.websocketMessages = [];
      window.websocketLatency = [];
      
      const originalWebSocket = window.WebSocket;
      window.WebSocket = function(url, protocols) {
        const ws = new originalWebSocket(url, protocols);
        
        ws.addEventListener('message', (event) => {
          const data = JSON.parse(event.data);
          if (data.type === 'pong' && data.timestamp) {
            const latency = Date.now() - data.timestamp;
            window.websocketLatency.push(latency);
          }
          window.websocketMessages.push({
            data: event.data,
            timestamp: Date.now()
          });
        });
        
        return ws;
      };
    });
    
    await helpers.waitForWebSocketConnection();
    
    // Send multiple ping messages to measure latency under load
    const pingCount = 20;
    
    for (let i = 0; i < pingCount; i++) {
      await page.evaluate((timestamp) => {
        if (window.websocket && window.websocket.readyState === WebSocket.OPEN) {
          window.websocket.send(JSON.stringify({
            type: 'ping',
            timestamp: timestamp
          }));
        }
      }, Date.now());
      
      await page.waitForTimeout(100); // Small delay between pings
    }
    
    // Wait for all responses
    await page.waitForFunction(() => {
      return window.websocketLatency && window.websocketLatency.length >= 15; // At least 75% responses
    }, { timeout: 15000 });
    
    const latencyResults = await page.evaluate(() => window.websocketLatency);
    const messageCount = await page.evaluate(() => window.websocketMessages.length);
    
    const avgLatency = latencyResults.reduce((sum, latency) => sum + latency, 0) / latencyResults.length;
    const minLatency = Math.min(...latencyResults);
    const maxLatency = Math.max(...latencyResults);
    
    expect(avgLatency).toBeLessThan(500); // Average latency under 500ms
    expect(latencyResults.length).toBeGreaterThan(pingCount * 0.7); // At least 70% response rate
    
    await helpers.saveTestResults('websocket-load-performance', {
      ping_count: pingCount,
      responses_received: latencyResults.length,
      response_rate: (latencyResults.length / pingCount) * 100,
      avg_latency: avgLatency,
      min_latency: minLatency,
      max_latency: maxLatency,
      total_messages: messageCount,
      latency_results: latencyResults,
      timestamp: Date.now()
    });
  });

  test('should measure end-to-end workflow performance', async ({ page }) => {
    const workflowStartTime = Date.now();
    const workflowSteps = [];
    
    // Step 1: Login
    let stepStartTime = Date.now();
    await helpers.login();
    workflowSteps.push({
      step: 'login',
      duration: Date.now() - stepStartTime
    });
    
    // Step 2: Create project
    stepStartTime = Date.now();
    await helpers.createProject('Performance Test Project');
    workflowSteps.push({
      step: 'create_project',
      duration: Date.now() - stepStartTime
    });
    
    // Step 3: Navigate to video processing
    stepStartTime = Date.now();
    await page.click('[data-testid="video-processing-tab"]');
    await page.waitForSelector('[data-testid="video-upload-section"]');
    workflowSteps.push({
      step: 'navigate_video_processing',
      duration: Date.now() - stepStartTime
    });
    
    // Step 4: Load ML model
    stepStartTime = Date.now();
    await helpers.selectMLModel('yolov8');
    workflowSteps.push({
      step: 'load_ml_model',
      duration: Date.now() - stepStartTime
    });
    
    // Step 5: Start detection (simulated)
    stepStartTime = Date.now();
    const response = await page.request.post('http://localhost:8000/ml/yolo/inference', {
      data: {
        image_data: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...',
        confidence: 0.5
      }
    });
    workflowSteps.push({
      step: 'ml_inference',
      duration: Date.now() - stepStartTime,
      status: response.status()
    });
    
    const totalWorkflowTime = Date.now() - workflowStartTime;
    
    expect(totalWorkflowTime).toBeLessThan(30000); // Complete workflow under 30 seconds
    
    await helpers.saveTestResults('end-to-end-workflow-performance', {
      total_workflow_time: totalWorkflowTime,
      workflow_steps: workflowSteps,
      steps_count: workflowSteps.length,
      avg_step_time: workflowSteps.reduce((sum, step) => sum + step.duration, 0) / workflowSteps.length,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('end-to-end-workflow-completed');
  });
});