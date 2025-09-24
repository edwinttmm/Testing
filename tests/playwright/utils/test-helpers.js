/**
 * ADAS Camera HIL Testing Platform - Test Helpers
 * @fileoverview Utility functions for Playwright tests
 */

const { expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

class TestHelpers {
  /**
   * Wait for element to be visible with retry logic
   */
  static async waitForElement(page, selector, timeout = 30000) {
    const element = page.locator(selector);
    await element.waitFor({ state: 'visible', timeout });
    return element;
  }

  /**
   * Take screenshot with timestamp
   */
  static async takeScreenshot(page, name, testInfo) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const screenshotPath = `docs/errors/screenshots/${name}-${timestamp}.png`;
    await page.screenshot({ path: screenshotPath, fullPage: true });
    
    // Attach to test report
    if (testInfo) {
      await testInfo.attach(`${name}-screenshot`, {
        path: screenshotPath,
        contentType: 'image/png'
      });
    }
    
    return screenshotPath;
  }

  /**
   * Wait for API response and validate
   */
  static async waitForApiResponse(page, urlPattern, timeout = 30000) {
    return page.waitForResponse(
      response => response.url().includes(urlPattern) && response.status() === 200,
      { timeout }
    );
  }

  /**
   * Upload test video file
   */
  static async uploadTestVideo(page, videoPath = null) {
    // Create a small test video file if none provided
    if (!videoPath) {
      videoPath = await this.createTestVideoFile();
    }

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(videoPath);
    
    // Wait for upload to start
    await page.waitForSelector('.upload-progress, .uploading', { timeout: 5000 });
    
    return videoPath;
  }

  /**
   * Create a minimal test video file
   */
  static async createTestVideoFile() {
    const testVideoPath = '/tmp/test-video.mp4';
    
    // Create a minimal MP4 file (just headers for testing)
    const minimalMp4Buffer = Buffer.from([
      0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70, // ftyp box
      0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
      0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
      0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31
    ]);
    
    fs.writeFileSync(testVideoPath, minimalMp4Buffer);
    return testVideoPath;
  }

  /**
   * Wait for video processing to complete
   */
  static async waitForVideoProcessing(page, timeout = 120000) {
    // Wait for processing indicators to disappear
    await page.waitForFunction(
      () => {
        const processingElements = document.querySelectorAll('.processing, .uploading, [data-testid="processing"]');
        return processingElements.length === 0;
      },
      { timeout }
    );
  }

  /**
   * Check API health
   */
  static async checkApiHealth(page, baseUrl = 'http://localhost:8000') {
    const response = await page.request.get(`${baseUrl}/health`);
    expect(response.ok()).toBeTruthy();
    return response;
  }

  /**
   * Create test project via API
   */
  static async createTestProject(page, projectData = {}) {
    const defaultProject = {
      name: `Test Project ${Date.now()}`,
      description: 'Automated test project',
      camera_type: 'front-facing-vru',
      test_scenarios: ['scenario_1']
    };

    const project = { ...defaultProject, ...projectData };
    
    const response = await page.request.post('http://localhost:8000/api/projects', {
      data: project,
      headers: { 'Content-Type': 'application/json' }
    });

    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Create test session via API
   */
  static async createTestSession(page, sessionData = {}) {
    const defaultSession = {
      name: `Test Session ${Date.now()}`,
      project_id: 1,
      configuration: {
        detection_threshold: 0.5,
        validation_rules: []
      }
    };

    const session = { ...defaultSession, ...sessionData };
    
    const response = await page.request.post('http://localhost:8000/api/test-sessions', {
      data: session,
      headers: { 'Content-Type': 'application/json' }
    });

    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Wait for WebSocket connection
   */
  static async waitForWebSocket(page, timeout = 10000) {
    return page.waitForFunction(
      () => {
        return window.WebSocket && window.websocketConnected === true;
      },
      { timeout }
    );
  }

  /**
   * Simulate LabJack hardware connection
   */
  static async simulateLabJackConnection(page) {
    const response = await page.request.post('http://localhost:8001/api/labjack/simulate-connection', {
      data: { device_id: 'test-t7-device', status: 'connected' }
    });
    return response;
  }

  /**
   * Generate performance metrics
   */
  static async measurePerformance(page, action) {
    const startTime = Date.now();
    
    // Start performance monitoring
    await page.evaluate(() => performance.mark('test-start'));
    
    // Execute action
    await action();
    
    // End performance monitoring
    await page.evaluate(() => performance.mark('test-end'));
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    // Get detailed performance metrics
    const metrics = await page.evaluate(() => {
      performance.measure('test-duration', 'test-start', 'test-end');
      return performance.getEntriesByName('test-duration')[0];
    });

    return {
      duration,
      performanceEntry: metrics,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Validate console errors
   */
  static setupConsoleMonitoring(page) {
    const errors = [];
    const warnings = [];

    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      } else if (msg.type() === 'warning') {
        warnings.push(msg.text());
      }
    });

    page.on('pageerror', error => {
      errors.push(error.message);
    });

    return { errors, warnings };
  }

  /**
   * Wait for multiple elements to be ready
   */
  static async waitForPageReady(page, selectors = []) {
    const defaultSelectors = [
      'main, .main-content, #root',
      'nav, .navigation',
      '.loading'  // Should be absent
    ];
    
    const allSelectors = [...defaultSelectors, ...selectors];
    
    for (const selector of allSelectors) {
      if (selector === '.loading') {
        // Wait for loading to disappear
        await page.waitForSelector(selector, { state: 'detached', timeout: 30000 }).catch(() => {
          // Loading element might not exist, which is fine
        });
      } else {
        await page.waitForSelector(selector, { timeout: 30000 });
      }
    }
  }

  /**
   * Save test results to file
   */
  static async saveTestResults(testName, results, metrics = {}) {
    const resultsDir = 'docs/errors/reports';
    if (!fs.existsSync(resultsDir)) {
      fs.mkdirSync(resultsDir, { recursive: true });
    }

    const resultData = {
      testName,
      timestamp: new Date().toISOString(),
      results,
      metrics,
      environment: {
        nodeVersion: process.version,
        platform: process.platform,
        url: 'http://localhost:3000'
      }
    };

    const filename = `${testName.replace(/\s+/g, '-').toLowerCase()}-${Date.now()}.json`;
    const filepath = path.join(resultsDir, filename);
    
    fs.writeFileSync(filepath, JSON.stringify(resultData, null, 2));
    return filepath;
  }
}

module.exports = TestHelpers;