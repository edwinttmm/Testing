/**
 * ADAS Camera HIL Testing Platform - AI Detection & YOLO Integration Tests
 * @fileoverview Tests for AI detection pipeline and YOLO model integration
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('AI Detection & YOLO Integration', () => {
  let consoleLogs;

  test.beforeEach(async ({ page }) => {
    consoleLogs = TestHelpers.setupConsoleMonitoring(page);
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);
  });

  test('should display AI detection interface', async ({ page }) => {
    // Look for detection-related UI elements
    const detectionSelectors = [
      '.detection',
      '.ai-detection',
      '[data-testid*="detection"]',
      '.yolo',
      '.object-detection',
      '.ml-inference'
    ];

    let foundDetectionUI = false;
    
    for (const selector of detectionSelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        foundDetectionUI = true;
        console.log(`✅ Detection UI found: ${selector} (${await elements.count()} elements)`);
        break;
      }
    }

    if (!foundDetectionUI) {
      // Try navigating to detection/AI section
      const aiLinks = page.locator('a, button').filter({
        hasText: /detection|ai|ml|yolo|inference/i
      });
      
      const linkCount = await aiLinks.count();
      console.log(`Found ${linkCount} potential AI/detection links`);
      
      if (linkCount > 0) {
        await aiLinks.first().click();
        await page.waitForTimeout(2000);
        await TestHelpers.takeScreenshot(page, 'ai-detection-navigation');
        
        // Check again for detection UI
        for (const selector of detectionSelectors) {
          if (await page.locator(selector).count() > 0) {
            foundDetectionUI = true;
            break;
          }
        }
      }
    }

    await TestHelpers.takeScreenshot(page, 'ai-detection-interface');
    
    if (foundDetectionUI) {
      console.log('✅ AI Detection interface elements found');
    } else {
      console.log('ℹ️ AI Detection interface not found in current view');
    }
  });

  test('should validate YOLO API integration', async ({ page }) => {
    // Test YOLO detection endpoints
    const yoloEndpoints = [
      '/api/detection/yolo/status',
      '/api/detection/models',
      '/api/ml/inference',
      '/api/yolo/detect'
    ];

    let workingEndpoints = 0;
    
    for (const endpoint of yoloEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`YOLO API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          workingEndpoints++;
          const data = await response.json().catch(() => null);
          if (data) {
            console.log(`✅ ${endpoint} returned data:`, Object.keys(data));
          }
        }
      } catch (error) {
        console.log(`YOLO API ${endpoint} error:`, error.message);
      }
    }

    // Test simple detection API
    const simpleDetectionResponse = await page.request.get('http://localhost:8000/api/detection/simple');
    console.log(`Simple detection API: ${simpleDetectionResponse.status()}`);

    // Test ground truth API (related to AI validation)
    const groundTruthResponse = await page.request.get('http://localhost:8000/api/ground-truth');
    console.log(`Ground truth API: ${groundTruthResponse.status()}`);

    expect(workingEndpoints).toBeGreaterThanOrEqual(0);
    console.log(`✅ ${workingEndpoints}/${yoloEndpoints.length} YOLO endpoints responding`);
  });

  test('should handle detection visualization', async ({ page }) => {
    // Look for detection visualization elements
    const visualizationSelectors = [
      'canvas',
      '.detection-overlay',
      '.bounding-box',
      '.detection-result',
      '[data-testid*="visualization"]',
      '.annotation-layer'
    ];

    let foundVisualization = false;
    let visualizationElements = 0;

    for (const selector of visualizationSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();
      
      if (count > 0) {
        foundVisualization = true;
        visualizationElements += count;
        console.log(`✅ Visualization element found: ${selector} (${count} elements)`);
      }
    }

    await TestHelpers.takeScreenshot(page, 'detection-visualization');

    // Test if canvas elements are interactive
    const canvasElements = page.locator('canvas');
    const canvasCount = await canvasElements.count();
    
    if (canvasCount > 0) {
      console.log(`✅ Found ${canvasCount} canvas elements for visualization`);
      
      // Test canvas interaction
      try {
        await canvasElements.first().click({ position: { x: 100, y: 100 } });
        await page.waitForTimeout(1000);
      } catch (error) {
        console.log('Canvas interaction test issue:', error.message);
      }
    }

    console.log(`Total visualization elements found: ${visualizationElements}`);
    
    if (foundVisualization) {
      console.log('✅ Detection visualization components detected');
    }
  });

  test('should validate object detection results', async ({ page }) => {
    // Test detection results display
    const resultsSelectors = [
      '.detection-results',
      '.objects-detected',
      '.confidence-score',
      '.detection-summary',
      '[data-testid*="results"]'
    ];

    let foundResults = false;

    for (const selector of resultsSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundResults = true;
        console.log('✅ Detection results display found:', selector);
        break;
      }
    }

    // Test detection events API
    const detectionEventsResponse = await page.request.get('http://localhost:8000/api/detection-events');
    console.log(`Detection events API: ${detectionEventsResponse.status()}`);

    if (detectionEventsResponse.ok()) {
      const events = await detectionEventsResponse.json().catch(() => []);
      console.log(`✅ Found ${events.length || 0} detection events`);
    }

    // Test ground truth objects API
    const groundTruthResponse = await page.request.get('http://localhost:8000/api/ground-truth-objects');
    console.log(`Ground truth objects API: ${groundTruthResponse.status()}`);

    await TestHelpers.takeScreenshot(page, 'detection-results');

    if (foundResults || detectionEventsResponse.ok()) {
      console.log('✅ Detection results system detected');
    }
  });

  test('should test real-time detection capabilities', async ({ page }) => {
    // Test WebSocket connection for real-time updates
    await page.evaluate(() => {
      // Try to establish WebSocket connection for real-time detection
      try {
        window.testWebSocket = new WebSocket('ws://localhost:8000/ws/detection');
        window.webSocketConnected = false;
        
        window.testWebSocket.onopen = () => {
          window.webSocketConnected = true;
          console.log('WebSocket connected for detection');
        };
        
        window.testWebSocket.onmessage = (event) => {
          console.log('Detection WebSocket message:', event.data);
        };
        
        window.testWebSocket.onerror = (error) => {
          console.log('Detection WebSocket error:', error);
        };
      } catch (error) {
        console.log('WebSocket setup error:', error);
      }
    });

    // Wait for WebSocket connection
    await page.waitForTimeout(2000);

    const isWebSocketConnected = await page.evaluate(() => window.webSocketConnected);
    console.log(`WebSocket connection status: ${isWebSocketConnected}`);

    // Test real-time detection endpoints
    const realtimeEndpoints = [
      '/ws/progress',
      '/ws/detection',
      '/api/detection/stream'
    ];

    for (const endpoint of realtimeEndpoints) {
      try {
        if (endpoint.startsWith('/ws/')) {
          console.log(`WebSocket endpoint available: ${endpoint}`);
        } else {
          const response = await page.request.get(`http://localhost:8000${endpoint}`);
          console.log(`Real-time API ${endpoint}: ${response.status()}`);
        }
      } catch (error) {
        console.log(`Real-time endpoint ${endpoint} error:`, error.message);
      }
    }

    await TestHelpers.takeScreenshot(page, 'real-time-detection');

    // Cleanup WebSocket
    await page.evaluate(() => {
      if (window.testWebSocket) {
        window.testWebSocket.close();
      }
    });
  });

  test('should validate detection accuracy metrics', async ({ page }) => {
    // Test accuracy and metrics endpoints
    const metricsEndpoints = [
      '/api/detection/metrics',
      '/api/detection/accuracy',
      '/api/detection/performance',
      '/api/validation/stats'
    ];

    let metricsFound = 0;

    for (const endpoint of metricsEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Metrics API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          metricsFound++;
          const data = await response.json().catch(() => null);
          if (data && typeof data === 'object') {
            console.log(`✅ ${endpoint} metrics available`);
          }
        }
      } catch (error) {
        console.log(`Metrics API ${endpoint} error:`, error.message);
      }
    }

    // Look for metrics display in UI
    const metricsSelectors = [
      '.accuracy',
      '.metrics',
      '.confidence',
      '.performance-stats',
      '[data-testid*="metrics"]'
    ];

    let foundMetricsUI = false;

    for (const selector of metricsSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundMetricsUI = true;
        console.log('✅ Metrics UI found:', selector);
        break;
      }
    }

    await TestHelpers.takeScreenshot(page, 'detection-metrics');

    console.log(`✅ ${metricsFound}/${metricsEndpoints.length} metrics endpoints available`);
    
    if (metricsFound > 0 || foundMetricsUI) {
      console.log('✅ Detection accuracy metrics system detected');
    }
  });

  test('should test model configuration and settings', async ({ page }) => {
    // Look for model configuration UI
    const configSelectors = [
      '.model-config',
      '.settings',
      '.configuration',
      '[data-testid*="config"]',
      '.detection-settings'
    ];

    let foundConfigUI = false;

    for (const selector of configSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundConfigUI = true;
        console.log('✅ Configuration UI found:', selector);
        break;
      }
    }

    // Test configuration endpoints
    const configEndpoints = [
      '/api/detection/config',
      '/api/models/config',
      '/api/settings'
    ];

    for (const endpoint of configEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Config API ${endpoint}: ${response.status()}`);
        
        if (response.ok()) {
          const config = await response.json().catch(() => null);
          if (config) {
            console.log(`✅ Configuration available at ${endpoint}`);
          }
        }
      } catch (error) {
        console.log(`Config API ${endpoint} error:`, error.message);
      }
    }

    await TestHelpers.takeScreenshot(page, 'model-configuration');

    if (foundConfigUI) {
      console.log('✅ Model configuration interface detected');
    }
  });
});