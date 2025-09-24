const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('LabJack Hardware Integration', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
    await helpers.login();
  });

  test('should detect LabJack T7 hardware', async ({ page }) => {
    // Test LabJack hardware detection through backend API
    const response = await page.request.get('http://localhost:8000/hardware/labjack/detect');
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    
    // Should detect LabJack T7 attached to WSL
    expect(data.status).toBe('success');
    expect(data.devices).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          device_type: 'T7',
          connection_type: expect.any(String),
          serial_number: expect.any(Number)
        })
      ])
    );
    
    await helpers.saveTestResults('labjack-detection', {
      status: data.status,
      devices_found: data.devices.length,
      t7_detected: data.devices.some(d => d.device_type === 'T7'),
      devices: data.devices,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('labjack-detected');
  });

  test('should display LabJack status in UI', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Navigate to hardware section
    await page.click('[data-testid="hardware-tab"]');
    await helpers.takeScreenshot('hardware-tab-opened');
    
    // Wait for LabJack status to load
    await page.waitForSelector('[data-testid="labjack-status"]', { timeout: 10000 });
    
    const statusElement = page.locator('[data-testid="labjack-status"]');
    await expect(statusElement).toBeVisible();
    
    const statusText = await statusElement.textContent();
    expect(statusText).toMatch(/Connected|Online|T7/);
    
    await helpers.takeScreenshot('labjack-status-displayed');
  });

  test('should configure LabJack channels', async ({ page }) => {
    await page.goto('/dashboard');
    await page.click('[data-testid="hardware-tab"]');
    
    // Configure analog input channel
    await page.click('[data-testid="configure-labjack"]');
    await helpers.takeScreenshot('labjack-config-dialog');
    
    // Set up AIN0 channel
    await page.selectOption('[data-testid="channel-select"]', 'AIN0');
    await page.fill('[data-testid="channel-range"]', '10.0');
    await page.selectOption('[data-testid="channel-resolution"]', '8');
    await page.click('[data-testid="save-channel-config"]');
    
    // Verify configuration saved
    await page.waitForSelector('[data-testid="config-saved-success"]');
    await helpers.takeScreenshot('labjack-channel-configured');
    
    // Test the configuration via backend
    const response = await page.request.get('http://localhost:8000/hardware/labjack/config');
    expect(response.status()).toBe(200);
    
    const configData = await response.json();
    expect(configData.channels).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: 'AIN0',
          range: 10.0,
          resolution: 8
        })
      ])
    );
  });

  test('should read analog values from LabJack', async ({ page }) => {
    await page.goto('/dashboard');
    await page.click('[data-testid="hardware-tab"]');
    
    // Start reading analog values
    await page.click('[data-testid="start-analog-reading"]');
    await helpers.takeScreenshot('analog-reading-started');
    
    // Wait for analog values to appear
    await page.waitForSelector('[data-testid="analog-values"]', { timeout: 15000 });
    
    const valuesElement = page.locator('[data-testid="analog-values"]');
    await expect(valuesElement).toBeVisible();
    
    // Check that we're getting numeric values
    const valuesText = await valuesElement.textContent();
    expect(valuesText).toMatch(/\d+\.\d+/); // Should contain decimal numbers
    
    await helpers.takeScreenshot('analog-values-displayed');
    
    // Test backend analog reading API
    const response = await page.request.get('http://localhost:8000/hardware/labjack/read/analog');
    expect(response.status()).toBe(200);
    
    const readingData = await response.json();
    expect(readingData.status).toBe('success');
    expect(readingData.readings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          channel: expect.any(String),
          value: expect.any(Number),
          timestamp: expect.any(Number)
        })
      ])
    );
    
    await helpers.saveTestResults('labjack-analog-reading', {
      readings_count: readingData.readings.length,
      sample_reading: readingData.readings[0],
      timestamp: Date.now()
    });
  });

  test('should control digital outputs on LabJack', async ({ page }) => {
    await page.goto('/dashboard');
    await page.click('[data-testid="hardware-tab"]');
    
    // Test digital output control
    await page.click('[data-testid="digital-output-section"]');
    await helpers.takeScreenshot('digital-output-section');
    
    // Set FIO0 to high
    await page.click('[data-testid="fio0-high-button"]');
    await page.waitForSelector('[data-testid="fio0-status-high"]');
    
    // Verify through backend API
    const response = await page.request.post('http://localhost:8000/hardware/labjack/digital/write', {
      data: {
        channel: 'FIO0',
        state: 1
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.status).toBe('success');
    expect(data.channel).toBe('FIO0');
    expect(data.state).toBe(1);
    
    await helpers.takeScreenshot('digital-output-high');
    
    // Set FIO0 to low
    await page.click('[data-testid="fio0-low-button"]');
    await page.waitForSelector('[data-testid="fio0-status-low"]');
    
    await helpers.takeScreenshot('digital-output-low');
    
    await helpers.saveTestResults('labjack-digital-control', {
      digital_control_working: true,
      channels_tested: ['FIO0'],
      timestamp: Date.now()
    });
  });

  test('should stream data from LabJack', async ({ page }) => {
    await page.goto('/dashboard');
    await page.click('[data-testid="hardware-tab"]');
    
    // Start data streaming
    await page.click('[data-testid="start-streaming"]');
    await helpers.takeScreenshot('streaming-started');
    
    // Configure streaming parameters
    await page.fill('[data-testid="sample-rate-input"]', '1000');
    await page.selectOption('[data-testid="streaming-channels"]', ['AIN0', 'AIN1']);
    await page.click('[data-testid="apply-streaming-config"]');
    
    // Wait for streaming data
    await page.waitForSelector('[data-testid="streaming-data"]', { timeout: 20000 });
    
    const streamingElement = page.locator('[data-testid="streaming-data"]');
    await expect(streamingElement).toBeVisible();
    
    // Verify we're receiving streamed data
    await page.waitForFunction(() => {
      const element = document.querySelector('[data-testid="streaming-data"]');
      return element && element.textContent.includes('samples');
    }, { timeout: 10000 });
    
    await helpers.takeScreenshot('streaming-data-received');
    
    // Test backend streaming API
    const response = await page.request.get('http://localhost:8000/hardware/labjack/stream/status');
    expect(response.status()).toBe(200);
    
    const streamData = await response.json();
    expect(streamData.status).toBe('success');
    expect(streamData.streaming).toBe(true);
    expect(streamData.sample_rate).toBe(1000);
    
    await helpers.saveTestResults('labjack-streaming', {
      streaming_active: streamData.streaming,
      sample_rate: streamData.sample_rate,
      channels: streamData.channels,
      timestamp: Date.now()
    });
    
    // Stop streaming
    await page.click('[data-testid="stop-streaming"]');
    await page.waitForSelector('[data-testid="streaming-stopped"]');
  });

  test('should handle LabJack connection errors gracefully', async ({ page }) => {
    // Test error handling when LabJack is disconnected (simulated)
    const response = await page.request.post('http://localhost:8000/hardware/labjack/simulate_disconnect');
    
    await page.goto('/dashboard');
    await page.click('[data-testid="hardware-tab"]');
    
    // Should show disconnected status
    await page.waitForSelector('[data-testid="labjack-disconnected"]', { timeout: 10000 });
    await helpers.takeScreenshot('labjack-disconnected');
    
    const statusElement = page.locator('[data-testid="labjack-status"]');
    const statusText = await statusElement.textContent();
    expect(statusText).toMatch(/Disconnected|Offline|Error/);
    
    // Try to reconnect
    await page.click('[data-testid="reconnect-labjack"]');
    
    // Restore connection (simulated)
    await page.request.post('http://localhost:8000/hardware/labjack/simulate_connect');
    
    // Should reconnect
    await page.waitForSelector('[data-testid="labjack-connected"]', { timeout: 10000 });
    await helpers.takeScreenshot('labjack-reconnected');
    
    await helpers.saveTestResults('labjack-error-handling', {
      disconnect_handled: true,
      reconnect_successful: true,
      timestamp: Date.now()
    });
  });

  test('should measure LabJack performance', async ({ page }) => {
    const performanceResults = [];
    
    // Test multiple analog readings for performance
    for (let i = 0; i < 20; i++) {
      const startTime = Date.now();
      
      const response = await page.request.get('http://localhost:8000/hardware/labjack/read/analog/AIN0');
      
      const endTime = Date.now();
      const data = await response.json();
      
      performanceResults.push({
        iteration: i + 1,
        status: response.status(),
        reading_time_ms: endTime - startTime,
        value: data.value,
        timestamp: Date.now()
      });
    }
    
    const avgTime = performanceResults.reduce((sum, result) => sum + result.reading_time_ms, 0) / 20;
    const minTime = Math.min(...performanceResults.map(r => r.reading_time_ms));
    const maxTime = Math.max(...performanceResults.map(r => r.reading_time_ms));
    
    expect(avgTime).toBeLessThan(100); // Should be under 100ms on average
    
    await helpers.saveTestResults('labjack-performance', {
      iterations: 20,
      avg_reading_time_ms: avgTime,
      min_reading_time_ms: minTime,
      max_reading_time_ms: maxTime,
      all_results: performanceResults,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('labjack-performance-tested');
  });

  test('should integrate LabJack with ML pipeline', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Configure LabJack as trigger for ML inference
    await page.click('[data-testid="hardware-tab"]');
    await page.click('[data-testid="ml-integration-tab"]');
    
    // Set up trigger configuration
    await page.selectOption('[data-testid="trigger-channel"]', 'AIN0');
    await page.fill('[data-testid="trigger-threshold"]', '5.0');
    await page.selectOption('[data-testid="trigger-action"]', 'start_yolo_inference');
    await page.click('[data-testid="save-trigger-config"]');
    
    await helpers.takeScreenshot('labjack-ml-integration-configured');
    
    // Test the integration
    const response = await page.request.post('http://localhost:8000/hardware/labjack/trigger/simulate', {
      data: {
        channel: 'AIN0',
        value: 6.0 // Above threshold
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.status).toBe('success');
    expect(data.ml_inference_triggered).toBe(true);
    
    // Wait for ML inference results
    await page.waitForSelector('[data-testid="triggered-ml-results"]', { timeout: 30000 });
    await helpers.takeScreenshot('labjack-triggered-ml-inference');
    
    await helpers.saveTestResults('labjack-ml-integration', {
      trigger_configured: true,
      ml_inference_triggered: true,
      integration_working: true,
      timestamp: Date.now()
    });
  });
});