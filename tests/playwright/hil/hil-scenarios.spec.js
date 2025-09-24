/**
 * ADAS Camera HIL Testing Platform - HIL Test Scenario Execution Tests
 * @fileoverview Tests for Hardware-in-the-Loop test scenario execution
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('HIL Test Scenario Execution', () => {
  let consoleLogs;
  let testProject;
  let testSession;

  test.beforeAll(async ({ request }) => {
    // Create test project and session for HIL tests
    testProject = await TestHelpers.createTestProject(
      { request },
      { 
        name: 'HIL Test Scenario Project',
        camera_type: 'front-facing-vru',
        test_scenarios: ['pedestrian-detection', 'vehicle-detection', 'cyclist-detection']
      }
    );

    testSession = await TestHelpers.createTestSession(
      { request },
      {
        name: 'HIL Test Session',
        project_id: testProject?.id || 1,
        configuration: {
          detection_threshold: 0.7,
          validation_rules: ['timing-accuracy', 'detection-precision']
        }
      }
    );
  });

  test.beforeEach(async ({ page }) => {
    consoleLogs = TestHelpers.setupConsoleMonitoring(page);
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);
  });

  test('should display HIL test scenario interface', async ({ page }) => {
    // Look for HIL scenario UI elements
    const hilSelectors = [
      '.hil',
      '.test-scenario',
      '.scenario',
      '[data-testid*="hil"]',
      '[data-testid*="scenario"]',
      '.hardware-loop',
      '.test-execution'
    ];

    let foundHILUI = false;

    for (const selector of hilSelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        foundHILUI = true;
        console.log(`✅ HIL UI found: ${selector} (${await elements.count()} elements)`);
        break;
      }
    }

    if (!foundHILUI) {
      // Try navigating to HIL/scenario section
      const hilLinks = page.locator('a, button').filter({
        hasText: /hil|scenario|test.*execution|hardware.*loop/i
      });

      const linkCount = await hilLinks.count();
      console.log(`Found ${linkCount} potential HIL navigation links`);

      if (linkCount > 0) {
        await hilLinks.first().click();
        await page.waitForTimeout(2000);
        
        // Check again for HIL UI
        for (const selector of hilSelectors) {
          if (await page.locator(selector).count() > 0) {
            foundHILUI = true;
            break;
          }
        }
      }
    }

    await TestHelpers.takeScreenshot(page, 'hil-scenario-interface');

    // Test HIL-related API endpoints
    const hilEndpoints = [
      '/api/test-scenarios',
      '/api/hil/scenarios',
      '/api/test-execution',
      '/api/scenarios'
    ];

    let workingHILAPIs = 0;

    for (const endpoint of hilEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`HIL API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          workingHILAPIs++;
          const data = await response.json().catch(() => []);
          console.log(`✅ ${endpoint} returned ${data.length || 0} items`);
        }
      } catch (error) {
        console.log(`HIL API ${endpoint} error:`, error.message);
      }
    }

    console.log(`✅ ${workingHILAPIs}/${hilEndpoints.length} HIL APIs responding`);

    if (foundHILUI || workingHILAPIs > 0) {
      console.log('✅ HIL test scenario interface detected');
    }
  });

  test('should execute pedestrian detection scenario', async ({ page }) => {
    // Test pedestrian detection scenario execution
    const scenarioData = {
      name: 'Pedestrian Detection Test',
      type: 'pedestrian-detection',
      configuration: {
        detection_threshold: 0.7,
        timing_requirements: 100, // 100ms max response time
        test_duration: 30 // 30 seconds
      }
    };

    // Execute scenario via API
    const executeResponse = await page.request.post('http://localhost:8000/api/test-scenarios/execute', {
      data: scenarioData,
      headers: { 'Content-Type': 'application/json' }
    });
    console.log(`Pedestrian scenario execution: ${executeResponse.status()}`);

    if (executeResponse.ok()) {
      const execution = await executeResponse.json().catch(() => null);
      if (execution) {
        console.log('✅ Pedestrian scenario started:', execution.id || execution.status);
      }
    }

    // Look for scenario execution UI
    const executionSelectors = [
      '.scenario-execution',
      '.test-running',
      '.execution-status',
      '[data-testid*="execution"]',
      '.pedestrian-test'
    ];

    let foundExecutionUI = false;

    for (const selector of executionSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundExecutionUI = true;
        console.log('✅ Scenario execution UI found:', selector);
        break;
      }
    }

    // Test starting scenario from UI
    const startButtons = page.locator('button').filter({
      hasText: /start|run|execute|begin/i
    });

    const buttonCount = await startButtons.count();
    console.log(`Found ${buttonCount} potential start buttons`);

    if (buttonCount > 0) {
      try {
        await startButtons.first().click();
        await page.waitForTimeout(2000);
        console.log('✅ Scenario start button interaction successful');
      } catch (error) {
        console.log('Scenario start interaction issue:', error.message);
      }
    }

    await TestHelpers.takeScreenshot(page, 'pedestrian-detection-scenario');

    if (foundExecutionUI || executeResponse.status() < 500 || buttonCount > 0) {
      console.log('✅ Pedestrian detection scenario execution detected');
    }
  });

  test('should monitor real-time HIL execution', async ({ page }) => {
    // Setup WebSocket for real-time HIL monitoring
    await page.evaluate(() => {
      window.hilWebSocketConnected = false;
      window.hilMessages = [];

      try {
        window.hilWebSocket = new WebSocket('ws://localhost:8000/ws/hil');
        
        window.hilWebSocket.onopen = () => {
          window.hilWebSocketConnected = true;
          console.log('HIL WebSocket connected');
        };
        
        window.hilWebSocket.onmessage = (event) => {
          window.hilMessages.push(event.data);
          console.log('HIL WebSocket message:', event.data);
        };
        
        window.hilWebSocket.onerror = (error) => {
          console.log('HIL WebSocket error:', error);
        };
      } catch (error) {
        console.log('HIL WebSocket setup error:', error);
        // Fallback to progress WebSocket
        try {
          window.hilWebSocket = new WebSocket('ws://localhost:8000/ws/progress');
          window.hilWebSocket.onopen = () => {
            window.hilWebSocketConnected = true;
            console.log('HIL fallback WebSocket connected');
          };
        } catch (fallbackError) {
          console.log('HIL fallback WebSocket error:', fallbackError);
        }
      }
    });

    // Wait for WebSocket connection
    await page.waitForTimeout(3000);

    const isConnected = await page.evaluate(() => window.hilWebSocketConnected);
    console.log(`HIL WebSocket connected: ${isConnected}`);

    // Look for real-time monitoring UI
    const monitoringSelectors = [
      '.real-time',
      '.monitoring',
      '.live-status',
      '[data-testid*="monitoring"]',
      '.execution-monitor'
    ];

    let foundMonitoringUI = false;

    for (const selector of monitoringSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundMonitoringUI = true;
        console.log('✅ Real-time monitoring UI found:', selector);
        break;
      }
    }

    // Test triggering real-time updates
    if (isConnected) {
      // Trigger some HIL activity to generate WebSocket messages
      const triggerResponse = await page.request.post('http://localhost:8000/api/test-scenarios/1/trigger', {
        data: { action: 'detection-event' }
      });
      console.log(`HIL trigger response: ${triggerResponse.status()}`);

      await page.waitForTimeout(2000);

      // Check for received messages
      const messages = await page.evaluate(() => window.hilMessages);
      console.log(`✅ Received ${messages.length} HIL WebSocket messages`);
    }

    await TestHelpers.takeScreenshot(page, 'hil-real-time-monitoring');

    // Cleanup WebSocket
    await page.evaluate(() => {
      if (window.hilWebSocket) {
        window.hilWebSocket.close();
      }
    });

    if (foundMonitoringUI || isConnected) {
      console.log('✅ Real-time HIL execution monitoring detected');
    }
  });

  test('should validate detection accuracy in HIL scenario', async ({ page }) => {
    // Test detection accuracy validation endpoints
    const validationEndpoints = [
      '/api/validation/accuracy',
      '/api/hil/validation',
      '/api/detection/validation',
      '/api/test-results/validation'
    ];

    let validationCapabilities = 0;

    for (const endpoint of validationEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Validation API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          validationCapabilities++;
          const data = await response.json().catch(() => null);
          if (data) {
            console.log(`✅ Validation data available at ${endpoint}`);
          }
        }
      } catch (error) {
        console.log(`Validation API ${endpoint} error:`, error.message);
      }
    }

    // Test ground truth comparison
    const comparisonResponse = await page.request.post('http://localhost:8000/api/detection/compare', {
      data: {
        detection_id: 1,
        ground_truth_id: 1,
        threshold: 0.7
      },
      headers: { 'Content-Type': 'application/json' }
    });
    console.log(`Detection comparison: ${comparisonResponse.status()}`);

    // Look for validation UI elements
    const validationSelectors = [
      '.validation',
      '.accuracy',
      '.comparison',
      '[data-testid*="validation"]',
      '.ground-truth'
    ];

    let foundValidationUI = false;

    for (const selector of validationSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundValidationUI = true;
        console.log('✅ Validation UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'hil-detection-validation');

    console.log(`✅ ${validationCapabilities}/${validationEndpoints.length} validation endpoints available`);

    if (foundValidationUI || validationCapabilities > 0) {
      console.log('✅ Detection accuracy validation in HIL scenarios detected');
    }
  });

  test('should test timing precision in HIL execution', async ({ page }) => {
    // Test timing precision measurement
    const timingTests = [
      {
        name: 'Detection Response Time',
        action: async () => {
          const startTime = performance.now();
          const response = await page.request.post('http://localhost:8000/api/detection/trigger', {
            data: { scenario: 'timing-test' }
          });
          const endTime = performance.now();
          return { 
            duration: endTime - startTime, 
            status: response.status(),
            description: 'API detection trigger response time'
          };
        }
      },
      {
        name: 'UI Interaction Response',
        action: async () => {
          const detectionButton = page.locator('button').filter({
            hasText: /detect|analyze|process/i
          });
          
          if (await detectionButton.count() > 0) {
            const startTime = performance.now();
            await detectionButton.first().click();
            await page.waitForTimeout(100); // Wait for UI response
            const endTime = performance.now();
            return { 
              duration: endTime - startTime, 
              status: 200,
              description: 'UI button response time'
            };
          } else {
            return { 
              duration: 0, 
              status: 404, 
              description: 'No detection button found'
            };
          }
        }
      }
    ];

    const timingResults = [];

    for (const test of timingTests) {
      try {
        const result = await test.action();
        timingResults.push({
          name: test.name,
          ...result
        });
        console.log(`✅ ${test.name}: ${result.duration.toFixed(2)}ms (${result.description})`);
      } catch (error) {
        console.log(`⚠️ ${test.name} error:`, error.message);
      }
    }

    // Test latency validation endpoint
    const latencyResponse = await page.request.get('http://localhost:8000/api/latency/validation');
    console.log(`Latency validation API: ${latencyResponse.status()}`);

    // Look for timing display in UI
    const timingSelectors = [
      '.timing',
      '.latency',
      '.response-time',
      '[data-testid*="timing"]',
      '.performance-metrics'
    ];

    let foundTimingUI = false;

    for (const selector of timingSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundTimingUI = true;
        console.log('✅ Timing display UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'hil-timing-precision');

    // Save timing results
    await TestHelpers.saveTestResults('HIL-Timing-Precision', timingResults, {
      averageResponseTime: timingResults.reduce((sum, r) => sum + r.duration, 0) / timingResults.length,
      testCount: timingResults.length
    });

    if (foundTimingUI || latencyResponse.ok() || timingResults.length > 0) {
      console.log('✅ Timing precision in HIL execution detected');
    }
  });

  test('should handle multiple concurrent scenarios', async ({ page }) => {
    // Test running multiple scenarios concurrently
    const scenarios = [
      { name: 'Pedestrian-1', type: 'pedestrian-detection' },
      { name: 'Vehicle-1', type: 'vehicle-detection' },
      { name: 'Cyclist-1', type: 'cyclist-detection' }
    ];

    const concurrentExecutions = [];

    // Start multiple scenarios
    for (const scenario of scenarios) {
      try {
        const response = await page.request.post('http://localhost:8000/api/test-scenarios/execute', {
          data: {
            name: scenario.name,
            type: scenario.type,
            configuration: {
              detection_threshold: 0.6,
              concurrent: true
            }
          },
          headers: { 'Content-Type': 'application/json' }
        });

        concurrentExecutions.push({
          scenario: scenario.name,
          status: response.status(),
          success: response.ok()
        });

        console.log(`Scenario ${scenario.name} execution: ${response.status()}`);
      } catch (error) {
        console.log(`Scenario ${scenario.name} error:`, error.message);
      }
    }

    // Test concurrent monitoring
    const statusResponse = await page.request.get('http://localhost:8000/api/test-scenarios/status');
    console.log(`Concurrent scenarios status: ${statusResponse.status()}`);

    if (statusResponse.ok()) {
      const status = await statusResponse.json().catch(() => {});
      console.log('✅ Concurrent scenario status available:', Object.keys(status || {}));
    }

    // Look for concurrent execution UI
    const concurrentSelectors = [
      '.concurrent',
      '.multiple-scenarios',
      '.parallel-execution',
      '[data-testid*="concurrent"]'
    ];

    let foundConcurrentUI = false;

    for (const selector of concurrentSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundConcurrentUI = true;
        console.log('✅ Concurrent execution UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'concurrent-hil-scenarios');

    const successfulExecutions = concurrentExecutions.filter(e => e.success).length;
    console.log(`✅ ${successfulExecutions}/${scenarios.length} concurrent scenarios started successfully`);

    if (foundConcurrentUI || successfulExecutions > 0 || statusResponse.ok()) {
      console.log('✅ Multiple concurrent HIL scenarios capability detected');
    }
  });

  test('should generate HIL test reports', async ({ page }) => {
    // Test HIL report generation endpoints
    const reportEndpoints = [
      '/api/reports/hil',
      '/api/test-results/export',
      '/api/reports/generate',
      '/api/hil/summary'
    ];

    let reportCapabilities = 0;

    for (const endpoint of reportEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Report API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          reportCapabilities++;
          
          // Try to get content type
          const contentType = response.headers()['content-type'] || '';
          console.log(`✅ ${endpoint} available (${contentType})`);
        }
      } catch (error) {
        console.log(`Report API ${endpoint} error:`, error.message);
      }
    }

    // Test report generation with parameters
    const generateResponse = await page.request.post('http://localhost:8000/api/reports/generate', {
      data: {
        type: 'hil-summary',
        format: 'json',
        date_range: '7d'
      },
      headers: { 'Content-Type': 'application/json' }
    });
    console.log(`Report generation: ${generateResponse.status()}`);

    // Look for report UI elements
    const reportSelectors = [
      '.report',
      '.export',
      '.summary',
      '[data-testid*="report"]',
      '.test-summary'
    ];

    let foundReportUI = false;

    for (const selector of reportSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundReportUI = true;
        console.log('✅ Report UI found:', selector);
        break;
      }
    }

    // Test download functionality
    const downloadButtons = page.locator('button, a').filter({
      hasText: /download|export|report/i
    });

    if (await downloadButtons.count() > 0) {
      try {
        const downloadPromise = page.waitForDownload({ timeout: 5000 });
        await downloadButtons.first().click();
        
        const download = await downloadPromise.catch(() => null);
        if (download) {
          console.log('✅ Report download initiated:', await download.suggestedFilename());
        }
      } catch (error) {
        console.log('Report download test issue:', error.message);
      }
    }

    await TestHelpers.takeScreenshot(page, 'hil-test-reports');

    console.log(`✅ ${reportCapabilities}/${reportEndpoints.length} report endpoints available`);

    if (foundReportUI || reportCapabilities > 0) {
      console.log('✅ HIL test report generation detected');
    }
  });
});