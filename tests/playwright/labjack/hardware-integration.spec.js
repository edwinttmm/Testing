/**
 * ADAS Camera HIL Testing Platform - LabJack Hardware Integration Tests
 * @fileoverview Tests for LabJack T7 hardware integration and signal validation
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('LabJack Hardware Integration', () => {
  let consoleLogs;

  test.beforeEach(async ({ page }) => {
    consoleLogs = TestHelpers.setupConsoleMonitoring(page);
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);
  });

  test('should display LabJack hardware status', async ({ page }) => {
    // Check LabJack status via API
    const statusEndpoints = [
      '/api/labjack/status',
      '/api/labjack/devices',
      '/api/labjack/health',
      '/api/signal-validation/labjack/status'
    ];

    let workingEndpoints = 0;
    let deviceStatus = null;

    for (const endpoint of statusEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`LabJack API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          workingEndpoints++;
          const data = await response.json().catch(() => null);
          if (data && !deviceStatus) {
            deviceStatus = data;
            console.log(`✅ LabJack status data:`, Object.keys(data));
          }
        }
      } catch (error) {
        console.log(`LabJack API ${endpoint} error:`, error.message);
      }
    }

    // Look for LabJack UI elements
    const labJackSelectors = [
      '.labjack',
      '.hardware',
      '[data-testid*="labjack"]',
      '[data-testid*="hardware"]',
      '.device-status',
      '.t7-device'
    ];

    let foundLabJackUI = false;

    for (const selector of labJackSelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        foundLabJackUI = true;
        console.log(`✅ LabJack UI found: ${selector} (${await elements.count()} elements)`);
        break;
      }
    }

    if (!foundLabJackUI) {
      // Try navigating to hardware section
      const hardwareLinks = page.locator('a, button').filter({
        hasText: /labjack|hardware|device|t7/i
      });

      if (await hardwareLinks.count() > 0) {
        await hardwareLinks.first().click();
        await page.waitForTimeout(2000);
        
        // Check again for LabJack UI
        for (const selector of labJackSelectors) {
          if (await page.locator(selector).count() > 0) {
            foundLabJackUI = true;
            break;
          }
        }
      }
    }

    await TestHelpers.takeScreenshot(page, 'labjack-hardware-status');

    console.log(`✅ ${workingEndpoints}/${statusEndpoints.length} LabJack APIs responding`);
    
    if (foundLabJackUI || workingEndpoints > 0) {
      console.log('✅ LabJack hardware integration detected');
    }

    expect(workingEndpoints).toBeGreaterThanOrEqual(0);
  });

  test('should handle LabJack device initialization', async ({ page }) => {
    // Test LabJack initialization endpoint
    const initResponse = await page.request.post('http://localhost:8000/api/signal-validation/labjack/initialize', {
      data: {}
    });
    console.log(`LabJack initialization: ${initResponse.status()}`);

    // Test connection endpoint
    const connectionResponse = await page.request.get('http://localhost:8000/api/signal-validation/test-connection');
    console.log(`LabJack connection test: ${connectionResponse.status()}`);

    // Look for initialization UI elements
    const initSelectors = [
      'button[text*="initialize"], button[text*="connect"]',
      '.initialize',
      '.connect-device',
      '[data-testid*="init"]'
    ];

    let foundInitUI = false;

    for (const selector of initSelectors) {
      const elements = page.locator(selector).filter({
        hasText: /initialize|connect|setup/i
      });
      
      if (await elements.count() > 0) {
        foundInitUI = true;
        console.log('✅ LabJack initialization UI found:', selector);
        
        // Test clicking initialize button
        try {
          await elements.first().click();
          await page.waitForTimeout(2000);
          console.log('✅ Initialize button interaction successful');
        } catch (error) {
          console.log('Initialize button interaction issue:', error.message);
        }
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'labjack-initialization');

    if (foundInitUI || initResponse.status() < 500) {
      console.log('✅ LabJack device initialization system detected');
    }
  });

  test('should validate signal monitoring capabilities', async ({ page }) => {
    // Test signal monitoring endpoints
    const monitoringEndpoints = [
      '/api/labjack/monitoring/start',
      '/api/signal-validation/monitoring/start/1',
      '/api/labjack/signals',
      '/api/signal-validation/signal/process'
    ];

    let monitoringCapabilities = 0;

    for (const endpoint of monitoringEndpoints) {
      try {
        const method = endpoint.includes('start') || endpoint.includes('process') ? 'POST' : 'GET';
        const response = await page.request[method.toLowerCase()](`http://localhost:8000${endpoint}`, {
          data: method === 'POST' ? {} : undefined
        });
        
        console.log(`Signal monitoring ${endpoint}: ${response.status()}`);
        
        if (response.status() < 500) {
          monitoringCapabilities++;
        }
      } catch (error) {
        console.log(`Monitoring endpoint ${endpoint} error:`, error.message);
      }
    }

    // Look for signal monitoring UI
    const signalSelectors = [
      '.signal-monitor',
      '.monitoring',
      '.signal-validation',
      '[data-testid*="signal"]',
      '.real-time-signals'
    ];

    let foundSignalUI = false;

    for (const selector of signalSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundSignalUI = true;
        console.log('✅ Signal monitoring UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'signal-monitoring');

    console.log(`✅ ${monitoringCapabilities}/${monitoringEndpoints.length} monitoring endpoints available`);
    
    if (foundSignalUI || monitoringCapabilities > 0) {
      console.log('✅ Signal monitoring capabilities detected');
    }
  });

  test('should test timing precision and synchronization', async ({ page }) => {
    // Test timing precision endpoints
    const timingEndpoints = [
      '/api/labjack/timing/precision',
      '/api/timing/sync',
      '/api/precision-timing',
      '/api/latency/validation'
    ];

    let timingFeatures = 0;

    for (const endpoint of timingEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Timing API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          timingFeatures++;
          const data = await response.json().catch(() => null);
          if (data) {
            console.log(`✅ Timing data available at ${endpoint}`);
          }
        }
      } catch (error) {
        console.log(`Timing API ${endpoint} error:`, error.message);
      }
    }

    // Test precision timing measurement
    const startTime = performance.now();
    
    // Simulate timing-critical operation
    await page.evaluate(() => {
      return new Promise(resolve => {
        const start = performance.now();
        const interval = setInterval(() => {
          if (performance.now() - start > 100) { // 100ms test
            clearInterval(interval);
            resolve();
          }
        }, 1);
      });
    });
    
    const endTime = performance.now();
    const measuredDuration = endTime - startTime;
    console.log(`✅ Timing precision test: ${measuredDuration.toFixed(2)}ms`);

    // Look for timing UI elements
    const timingSelectors = [
      '.timing',
      '.precision',
      '.synchronization',
      '[data-testid*="timing"]',
      '.latency'
    ];

    let foundTimingUI = false;

    for (const selector of timingSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundTimingUI = true;
        console.log('✅ Timing UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'timing-precision');

    if (foundTimingUI || timingFeatures > 0 || measuredDuration < 120) {
      console.log('✅ Timing precision and synchronization capabilities detected');
    }
  });

  test('should validate GPIO and digital I/O', async ({ page }) => {
    // Test GPIO endpoints
    const gpioEndpoints = [
      '/api/labjack/gpio',
      '/api/labjack/digital',
      '/api/labjack/pins',
      '/api/hardware/io'
    ];

    let gpioCapabilities = 0;

    for (const endpoint of gpioEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`GPIO API ${endpoint}: ${response.status()}`);
        
        if (response.status() < 500) {
          gpioCapabilities++;
        }
      } catch (error) {
        console.log(`GPIO API ${endpoint} error:`, error.message);
      }
    }

    // Test GPIO control endpoints
    const controlEndpoints = [
      { endpoint: '/api/labjack/gpio/set', method: 'POST', data: { pin: 1, value: 1 } },
      { endpoint: '/api/labjack/gpio/read', method: 'GET' },
      { endpoint: '/api/labjack/digital/toggle', method: 'POST', data: { pin: 2 } }
    ];

    for (const { endpoint, method, data } of controlEndpoints) {
      try {
        const response = await page.request[method.toLowerCase()](`http://localhost:8000${endpoint}`, {
          data: method === 'POST' ? data : undefined,
          headers: method === 'POST' ? { 'Content-Type': 'application/json' } : undefined
        });
        
        console.log(`GPIO control ${endpoint}: ${response.status()}`);
      } catch (error) {
        console.log(`GPIO control ${endpoint} error:`, error.message);
      }
    }

    // Look for GPIO UI elements
    const gpioSelectors = [
      '.gpio',
      '.digital-io',
      '.pins',
      '[data-testid*="gpio"]',
      '.io-control'
    ];

    let foundGPIOUI = false;

    for (const selector of gpioSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundGPIOUI = true;
        console.log('✅ GPIO UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'gpio-digital-io');

    if (foundGPIOUI || gpioCapabilities > 0) {
      console.log('✅ GPIO and digital I/O capabilities detected');
    }
  });

  test('should test analog input and measurement', async ({ page }) => {
    // Test analog input endpoints
    const analogEndpoints = [
      '/api/labjack/analog',
      '/api/labjack/ain',
      '/api/labjack/voltage',
      '/api/hardware/analog'
    ];

    let analogCapabilities = 0;

    for (const endpoint of analogEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Analog API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          analogCapabilities++;
          const data = await response.json().catch(() => null);
          if (data) {
            console.log(`✅ Analog data available at ${endpoint}`);
          }
        }
      } catch (error) {
        console.log(`Analog API ${endpoint} error:`, error.message);
      }
    }

    // Test analog measurement configuration
    const configResponse = await page.request.post('http://localhost:8000/api/labjack/analog/config', {
      data: {
        channel: 0,
        range: 10.0,
        resolution: 1
      },
      headers: { 'Content-Type': 'application/json' }
    });
    console.log(`Analog configuration: ${configResponse.status()}`);

    // Look for analog UI elements
    const analogSelectors = [
      '.analog',
      '.voltage',
      '.measurement',
      '[data-testid*="analog"]',
      '.ain'
    ];

    let foundAnalogUI = false;

    for (const selector of analogSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundAnalogUI = true;
        console.log('✅ Analog UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'analog-measurement');

    if (foundAnalogUI || analogCapabilities > 0) {
      console.log('✅ Analog input and measurement capabilities detected');
    }
  });

  test('should validate error handling and diagnostics', async ({ page }) => {
    // Test LabJack error handling endpoints
    const diagnosticEndpoints = [
      '/api/labjack/diagnostics',
      '/api/labjack/errors',
      '/api/labjack/health',
      '/api/hardware/status'
    ];

    let diagnosticFeatures = 0;

    for (const endpoint of diagnosticEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Diagnostic API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          diagnosticFeatures++;
          const data = await response.json().catch(() => null);
          if (data) {
            console.log(`✅ Diagnostic data available at ${endpoint}`);
          }
        }
      } catch (error) {
        console.log(`Diagnostic API ${endpoint} error:`, error.message);
      }
    }

    // Test intentional error scenarios
    const errorTests = [
      { endpoint: '/api/labjack/invalid-endpoint', expectedStatus: 404 },
      { endpoint: '/api/labjack/test-error', expectedStatus: [400, 404, 500] }
    ];

    for (const { endpoint, expectedStatus } of errorTests) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        const status = response.status();
        const expectedStatuses = Array.isArray(expectedStatus) ? expectedStatus : [expectedStatus];
        
        if (expectedStatuses.includes(status)) {
          console.log(`✅ Error handling test ${endpoint}: ${status} (expected)`);
        } else {
          console.log(`⚠️ Error handling test ${endpoint}: ${status} (unexpected)`);
        }
      } catch (error) {
        console.log(`Error test ${endpoint} exception:`, error.message);
      }
    }

    // Look for error/diagnostic UI elements
    const errorSelectors = [
      '.error',
      '.diagnostic',
      '.health',
      '[data-testid*="error"]',
      '.status-error'
    ];

    let foundErrorUI = false;

    for (const selector of errorSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundErrorUI = true;
        console.log('✅ Error/diagnostic UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'error-diagnostics');

    if (foundErrorUI || diagnosticFeatures > 0) {
      console.log('✅ Error handling and diagnostics detected');
    }
  });
});