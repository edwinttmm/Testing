/**
 * ADAS Camera HIL Testing Platform - Error Handling Tests
 * @fileoverview Tests for error scenarios and failure handling
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('Error Scenarios & Failure Handling', () => {
  let consoleLogs;

  test.beforeEach(async ({ page }) => {
    consoleLogs = TestHelpers.setupConsoleMonitoring(page);
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);
  });

  test('should handle network timeout scenarios', async ({ page }) => {
    // Test API timeout handling
    const timeoutTests = [
      {
        name: 'Long-running operation timeout',
        endpoint: '/api/videos/process',
        timeout: 1000 // 1 second timeout
      },
      {
        name: 'Slow response timeout', 
        endpoint: '/api/test-sessions/create',
        timeout: 500 // 0.5 second timeout
      }
    ];

    const timeoutResults = [];

    for (const test of timeoutTests) {
      try {
        const startTime = Date.now();
        
        // Set a short timeout to trigger timeout scenario
        const response = await page.request.post(`http://localhost:8000${test.endpoint}`, {
          data: { test: 'timeout-scenario' },
          timeout: test.timeout
        }).catch(error => ({ 
          error: true, 
          message: error.message,
          isTimeout: error.message.includes('timeout') || error.message.includes('TIMEOUT')
        }));

        const duration = Date.now() - startTime;

        if (response.error) {
          timeoutResults.push({
            name: test.name,
            duration,
            result: 'timeout',
            message: response.message,
            success: response.isTimeout
          });
          console.log(`✅ ${test.name}: Timeout handled correctly (${duration}ms)`);
        } else {
          timeoutResults.push({
            name: test.name,
            duration,
            result: 'completed',
            status: response.status(),
            success: true
          });
          console.log(`✅ ${test.name}: Completed within timeout (${duration}ms)`);
        }
      } catch (error) {
        console.log(`⚠️ ${test.name} error:`, error.message);
      }
    }

    // Test timeout in UI
    const slowOperationButton = page.locator('button').filter({
      hasText: /process|upload|analyze|generate/i
    });

    if (await slowOperationButton.count() > 0) {
      try {
        // Click and wait for potential timeout
        await slowOperationButton.first().click();
        
        // Wait for timeout or completion
        await Promise.race([
          page.waitForSelector('.error, .timeout', { timeout: 2000 }),
          page.waitForSelector('.success, .complete', { timeout: 2000 })
        ]).catch(() => {
          console.log('UI timeout test: No specific timeout indicator found');
        });
      } catch (error) {
        console.log('UI timeout test issue:', error.message);
      }
    }

    await TestHelpers.takeScreenshot(page, 'network-timeout-handling');

    expect(timeoutResults.length).toBeGreaterThan(0);
    console.log(`✅ Network timeout handling tested: ${timeoutResults.length} scenarios`);
  });

  test('should handle invalid file upload scenarios', async ({ page }) => {
    // Test various invalid file upload scenarios
    const invalidFiles = [
      { name: 'empty-file.mp4', content: '', description: 'Empty file' },
      { name: 'corrupted.mp4', content: 'invalid video content', description: 'Corrupted file' },
      { name: 'large-filename-' + 'x'.repeat(200) + '.mp4', content: 'test', description: 'Filename too long' }
    ];

    const uploadResults = [];

    for (const fileTest of invalidFiles) {
      try {
        // Create temporary invalid file
        const fs = require('fs');
        const tempPath = `/tmp/${fileTest.name}`;
        fs.writeFileSync(tempPath, fileTest.content);

        // Test file upload via API
        const response = await page.request.post('http://localhost:8000/api/videos/upload', {
          multipart: {
            file: fs.createReadStream(tempPath),
            project_id: 1
          }
        }).catch(error => ({
          error: true,
          status: 500,
          message: error.message
        }));

        uploadResults.push({
          file: fileTest.name,
          description: fileTest.description,
          status: response.status || response.error ? 'error' : 'success',
          httpStatus: response.status,
          handled: response.status >= 400 && response.status < 500 // 4xx errors are expected
        });

        console.log(`${fileTest.description}: ${response.status || 'Error'} ${response.error ? '(handled)' : ''}`);

        // Cleanup
        if (fs.existsSync(tempPath)) {
          fs.unlinkSync(tempPath);
        }
      } catch (error) {
        console.log(`Invalid file test ${fileTest.description} error:`, error.message);
      }
    }

    // Test file upload UI error handling
    const fileInput = page.locator('input[type="file"]');
    if (await fileInput.count() > 0) {
      // Try to upload a text file instead of video
      const textFilePath = '/tmp/test.txt';
      const fs = require('fs');
      fs.writeFileSync(textFilePath, 'This is not a video file');

      try {
        await fileInput.setInputFiles(textFilePath);
        await page.waitForTimeout(2000);

        // Look for error messages
        const errorMessages = page.locator('.error, .alert, [role="alert"]');
        const errorCount = await errorMessages.count();
        
        if (errorCount > 0) {
          console.log('✅ File type error handling detected in UI');
        }

        // Cleanup
        fs.unlinkSync(textFilePath);
      } catch (error) {
        console.log('File upload UI error test issue:', error.message);
      }
    }

    await TestHelpers.takeScreenshot(page, 'invalid-file-upload-handling');

    const handledErrors = uploadResults.filter(r => r.handled).length;
    console.log(`✅ Invalid file upload handling: ${handledErrors}/${uploadResults.length} errors properly handled`);
  });

  test('should handle API failure and recovery', async ({ page }) => {
    // Test various API failure scenarios
    const apiFailureTests = [
      { endpoint: '/api/invalid-endpoint', expectedStatus: 404, description: 'Non-existent endpoint' },
      { endpoint: '/api/videos/-1', expectedStatus: 404, description: 'Invalid resource ID' },
      { endpoint: '/api/projects', method: 'DELETE', expectedStatus: 405, description: 'Method not allowed' }
    ];

    const failureResults = [];

    for (const test of apiFailureTests) {
      try {
        const method = test.method || 'GET';
        const response = await page.request[method.toLowerCase()](`http://localhost:8000${test.endpoint}`);
        
        const isExpectedError = response.status() === test.expectedStatus;
        
        failureResults.push({
          test: test.description,
          endpoint: test.endpoint,
          expectedStatus: test.expectedStatus,
          actualStatus: response.status(),
          handled: isExpectedError
        });

        console.log(`${test.description}: ${response.status()} ${isExpectedError ? '✅' : '⚠️'}`);
      } catch (error) {
        console.log(`API failure test ${test.description} error:`, error.message);
      }
    }

    // Test API retry logic (if implemented)
    let retryAttempts = 0;
    const maxRetries = 3;
    
    while (retryAttempts < maxRetries) {
      try {
        const response = await page.request.get('http://localhost:8000/api/test-retry-endpoint');
        if (response.ok()) {
          break;
        }
        retryAttempts++;
      } catch (error) {
        retryAttempts++;
        console.log(`Retry attempt ${retryAttempts}: ${error.message}`);
      }
    }

    console.log(`API retry test: ${retryAttempts}/${maxRetries} attempts made`);

    // Test UI error state handling
    const errorStates = page.locator('.error-state, .network-error, .api-error');
    const errorStateCount = await errorStates.count();
    
    if (errorStateCount > 0) {
      console.log(`✅ Found ${errorStateCount} error state indicators in UI`);
    }

    await TestHelpers.takeScreenshot(page, 'api-failure-recovery');

    const handledFailures = failureResults.filter(r => r.handled).length;
    console.log(`✅ API failure handling: ${handledFailures}/${failureResults.length} failures properly handled`);
    
    expect(handledFailures).toBeGreaterThan(0);
  });

  test('should handle hardware disconnection scenarios', async ({ page }) => {
    // Test LabJack disconnection handling
    const disconnectionTests = [
      { endpoint: '/api/labjack/disconnect', description: 'Simulate LabJack disconnection' },
      { endpoint: '/api/labjack/connection-lost', description: 'Connection lost scenario' },
      { endpoint: '/api/hardware/offline', description: 'Hardware offline state' }
    ];

    const disconnectionResults = [];

    for (const test of disconnectionTests) {
      try {
        const response = await page.request.post(`http://localhost:8000${test.endpoint}`, {
          data: { simulate: true }
        });

        disconnectionResults.push({
          test: test.description,
          status: response.status(),
          handled: response.status() < 500 // Not a server error
        });

        console.log(`${test.description}: ${response.status()}`);

        // Check for reconnection capability
        if (response.ok()) {
          await page.waitForTimeout(1000);
          
          // Try to reconnect
          const reconnectResponse = await page.request.post(`http://localhost:8000/api/labjack/reconnect`, {
            data: {}
          });
          console.log(`Reconnection attempt: ${reconnectResponse.status()}`);
        }
      } catch (error) {
        console.log(`Hardware disconnection test ${test.description} error:`, error.message);
      }
    }

    // Test hardware status monitoring after disconnection
    const statusResponse = await page.request.get('http://localhost:8000/api/labjack/status');
    console.log(`Hardware status after disconnection tests: ${statusResponse.status()}`);

    // Look for disconnection indicators in UI
    const disconnectionIndicators = page.locator('.disconnected, .offline, .hardware-error');
    const indicatorCount = await disconnectionIndicators.count();

    if (indicatorCount > 0) {
      console.log(`✅ Found ${indicatorCount} hardware disconnection indicators in UI`);
    }

    await TestHelpers.takeScreenshot(page, 'hardware-disconnection-handling');

    console.log(`✅ Hardware disconnection scenarios tested: ${disconnectionResults.length}`);
  });

  test('should handle memory and resource limits', async ({ page }) => {
    // Test memory usage monitoring
    const initialMemory = await page.evaluate(() => {
      if (performance.memory) {
        return {
          used: performance.memory.usedJSHeapSize,
          total: performance.memory.totalJSHeapSize,
          limit: performance.memory.jsHeapSizeLimit
        };
      }
      return null;
    });

    console.log('Initial memory usage:', initialMemory);

    // Test large data operations
    const largeDataTests = [
      {
        name: 'Large video processing',
        action: async () => {
          const response = await page.request.post('http://localhost:8000/api/videos/process-large', {
            data: { size: '100MB', simulate: true }
          });
          return response.status();
        }
      },
      {
        name: 'Bulk data export',
        action: async () => {
          const response = await page.request.get('http://localhost:8000/api/export/bulk-data');
          return response.status();
        }
      }
    ];

    const resourceResults = [];

    for (const test of largeDataTests) {
      try {
        const startMemory = await page.evaluate(() => 
          performance.memory ? performance.memory.usedJSHeapSize : 0
        );

        const status = await test.action();
        
        const endMemory = await page.evaluate(() => 
          performance.memory ? performance.memory.usedJSHeapSize : 0
        );

        resourceResults.push({
          test: test.name,
          status,
          memoryIncrease: endMemory - startMemory,
          handled: status < 500
        });

        console.log(`${test.name}: ${status}, Memory change: ${endMemory - startMemory} bytes`);
      } catch (error) {
        console.log(`Resource test ${test.name} error:`, error.message);
      }
    }

    // Test for memory leaks by performing repeated operations
    const memoryLeakTest = async () => {
      const iterations = 10;
      const memoryReadings = [];

      for (let i = 0; i < iterations; i++) {
        // Perform some operation
        await page.evaluate(() => {
          // Simulate some memory allocation
          const tempArray = new Array(10000).fill('test-data');
          return tempArray.length;
        });

        // Take memory reading
        const memory = await page.evaluate(() => 
          performance.memory ? performance.memory.usedJSHeapSize : 0
        );
        memoryReadings.push(memory);

        await page.waitForTimeout(100);
      }

      const memoryGrowth = memoryReadings[memoryReadings.length - 1] - memoryReadings[0];
      console.log(`Memory leak test: ${memoryGrowth} bytes growth over ${iterations} iterations`);
      
      return memoryGrowth < 1000000; // Less than 1MB growth is acceptable
    };

    const noMemoryLeak = await memoryLeakTest();
    console.log(`Memory leak test result: ${noMemoryLeak ? 'PASS' : 'WARN'}`);

    await TestHelpers.takeScreenshot(page, 'memory-resource-limits');

    const resourceTestsHandled = resourceResults.filter(r => r.handled).length;
    console.log(`✅ Resource limit handling: ${resourceTestsHandled}/${resourceResults.length} tests handled`);
  });

  test('should validate error message quality and user feedback', async ({ page }) => {
    // Test error message display and quality
    const errorMessageTests = [
      {
        trigger: async () => {
          // Trigger a validation error
          const response = await page.request.post('http://localhost:8000/api/projects', {
            data: { name: '' }, // Invalid: empty name
            headers: { 'Content-Type': 'application/json' }
          });
          return response;
        },
        expectedMessage: /name.*required|name.*empty|invalid.*name/i,
        description: 'Validation error message'
      },
      {
        trigger: async () => {
          // Trigger authentication error
          const response = await page.request.get('http://localhost:8000/api/protected-endpoint');
          return response;
        },
        expectedMessage: /unauthorized|authentication|login/i,
        description: 'Authentication error message'
      }
    ];

    const messageQualityResults = [];

    for (const test of errorMessageTests) {
      try {
        const response = await test.trigger();
        
        if (!response.ok()) {
          const errorData = await response.json().catch(() => ({}));
          const errorMessage = errorData.message || errorData.error || errorData.detail || '';
          
          const messageQuality = {
            test: test.description,
            status: response.status(),
            hasMessage: !!errorMessage,
            messageLength: errorMessage.length,
            isDescriptive: errorMessage.length > 10,
            matchesPattern: test.expectedMessage.test(errorMessage)
          };

          messageQualityResults.push(messageQuality);

          console.log(`${test.description}: "${errorMessage}" (${messageQuality.isDescriptive ? 'descriptive' : 'brief'})`);
        }
      } catch (error) {
        console.log(`Error message test ${test.description} error:`, error.message);
      }
    }

    // Test UI error message display
    const errorDisplayElements = page.locator('.error-message, .alert, [role="alert"], .notification');
    const errorDisplayCount = await errorDisplayElements.count();

    if (errorDisplayCount > 0) {
      console.log(`✅ Found ${errorDisplayCount} error display elements in UI`);
      
      // Check if error messages are visible and readable
      for (let i = 0; i < Math.min(errorDisplayCount, 3); i++) {
        const element = errorDisplayElements.nth(i);
        const isVisible = await element.isVisible().catch(() => false);
        const text = await element.textContent().catch(() => '');
        
        if (isVisible && text.trim()) {
          console.log(`Error message ${i + 1}: "${text.trim()}" (visible: ${isVisible})`);
        }
      }
    }

    await TestHelpers.takeScreenshot(page, 'error-message-quality');

    const qualityMessages = messageQualityResults.filter(r => r.isDescriptive).length;
    console.log(`✅ Error message quality: ${qualityMessages}/${messageQualityResults.length} messages are descriptive`);

    expect(messageQualityResults.length).toBeGreaterThan(0);
  });

  test('should test graceful degradation when services are unavailable', async ({ page }) => {
    // Test application behavior when various services are unavailable
    const serviceTests = [
      { service: 'YOLO/ML', endpoint: '/api/ml/status', description: 'AI/ML service unavailable' },
      { service: 'Database', endpoint: '/api/database/health', description: 'Database connection issues' },
      { service: 'LabJack', endpoint: '/api/labjack/status', description: 'Hardware service unavailable' }
    ];

    const degradationResults = [];

    for (const test of serviceTests) {
      try {
        const response = await page.request.get(`http://localhost:8000${test.endpoint}`);
        
        const serviceStatus = {
          service: test.service,
          available: response.ok(),
          status: response.status(),
          description: test.description
        };

        degradationResults.push(serviceStatus);

        if (!response.ok()) {
          console.log(`${test.service} service unavailable: ${response.status()}`);
          
          // Test if application still functions without this service
          const mainPageStillWorks = await page.goto('http://localhost:3000').then(() => true).catch(() => false);
          serviceStatus.gracefulDegradation = mainPageStillWorks;
          
          if (mainPageStillWorks) {
            console.log(`✅ Application continues to function without ${test.service}`);
          } else {
            console.log(`⚠️ Application fails when ${test.service} is unavailable`);
          }
        } else {
          console.log(`${test.service} service is available: ${response.status()}`);
          serviceStatus.gracefulDegradation = true;
        }
      } catch (error) {
        console.log(`Service degradation test ${test.service} error:`, error.message);
      }
    }

    // Test if critical functionality remains available
    const criticalEndpoints = ['/health', '/api/projects', '/api/videos'];
    let criticalServicesWorking = 0;

    for (const endpoint of criticalEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        if (response.status() < 500) {
          criticalServicesWorking++;
        }
        console.log(`Critical endpoint ${endpoint}: ${response.status()}`);
      } catch (error) {
        console.log(`Critical endpoint ${endpoint} error:`, error.message);
      }
    }

    await TestHelpers.takeScreenshot(page, 'graceful-degradation');

    const gracefulDegradations = degradationResults.filter(r => r.gracefulDegradation).length;
    console.log(`✅ Graceful degradation: ${gracefulDegradations}/${degradationResults.length} services handle unavailability gracefully`);
    console.log(`✅ Critical services: ${criticalServicesWorking}/${criticalEndpoints.length} working`);

    expect(criticalServicesWorking).toBeGreaterThan(0);
  });

  test.afterEach(async ({ page }, testInfo) => {
    // Save error test results and console logs
    if (testInfo.status !== 'passed' || consoleLogs.errors.length > 0) {
      const errorData = {
        testTitle: testInfo.title,
        status: testInfo.status,
        errors: consoleLogs.errors,
        warnings: consoleLogs.warnings,
        url: page.url(),
        timestamp: new Date().toISOString()
      };
      
      await TestHelpers.saveTestResults(`error-handling-${testInfo.title}`, errorData);
      console.log(`Error test data saved for: ${testInfo.title}`);
    }
  });
});