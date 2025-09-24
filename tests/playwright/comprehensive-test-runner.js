/**
 * ADAS Camera HIL Testing Platform - Comprehensive Test Runner
 * @fileoverview Master test execution script with reporting
 */

const { chromium, firefox, webkit } = require('playwright');
const fs = require('fs').promises;
const path = require('path');

class ComprehensiveTestRunner {
  constructor() {
    this.testResults = {
      summary: {
        totalTests: 0,
        passedTests: 0,
        failedTests: 0,
        skippedTests: 0,
        startTime: null,
        endTime: null,
        duration: 0,
        browsers: []
      },
      categories: {
        authentication: { tests: [], passed: 0, failed: 0 },
        videoProcessing: { tests: [], passed: 0, failed: 0 },
        aiDetection: { tests: [], passed: 0, failed: 0 },
        realtimeMonitoring: { tests: [], passed: 0, failed: 0 },
        labjackIntegration: { tests: [], passed: 0, failed: 0 },
        hilExecution: { tests: [], passed: 0, failed: 0 },
        performance: { tests: [], passed: 0, failed: 0 },
        crossBrowser: { tests: [], passed: 0, failed: 0 }
      },
      artifacts: {
        screenshots: [],
        videos: [],
        reports: []
      },
      errors: [],
      warnings: []
    };
    
    this.screenshots = [];
  }

  async runAllTests() {
    console.log('🎬 Starting ADAS Camera HIL Testing Platform Comprehensive Test Suite...');
    this.testResults.summary.startTime = new Date().toISOString();
    
    // Ensure directories exist
    await this.setupDirectories();
    
    // Test browsers
    const browsers = [
      { name: 'chromium', instance: chromium },
      { name: 'firefox', instance: firefox }
      // { name: 'webkit', instance: webkit } // Enable if Safari testing needed
    ];
    
    for (const browserInfo of browsers) {
      console.log(`\n🔍 Testing with ${browserInfo.name}...`);
      this.testResults.summary.browsers.push(browserInfo.name);
      
      const browser = await browserInfo.instance.launch({
        headless: false,
        slowMo: 100
      });
      
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        recordVideo: {
          dir: './docs/errors/videos/',
          size: { width: 1920, height: 1080 }
        }
      });
      
      const page = await context.newPage();
      await this.setupPageCapture(page);
      
      // Run test categories
      await this.runAuthenticationTests(page, browserInfo.name);
      await this.runVideoProcessingTests(page, browserInfo.name);
      await this.runAIDetectionTests(page, browserInfo.name);
      await this.runRealtimeMonitoringTests(page, browserInfo.name);
      await this.runLabJackIntegrationTests(page, browserInfo.name);
      await this.runHILExecutionTests(page, browserInfo.name);
      await this.runPerformanceTests(page, browserInfo.name);
      
      await browser.close();
      console.log(`✅ ${browserInfo.name} testing completed`);
    }
    
    // Generate final report
    this.testResults.summary.endTime = new Date().toISOString();
    this.testResults.summary.duration = 
      new Date(this.testResults.summary.endTime) - new Date(this.testResults.summary.startTime);
    
    const report = await this.generateComprehensiveReport();
    console.log('\n📊 Comprehensive Test Suite Summary:');
    console.log(`- Total Tests: ${this.testResults.summary.totalTests}`);
    console.log(`- Passed: ${this.testResults.summary.passedTests}`);
    console.log(`- Failed: ${this.testResults.summary.failedTests}`);
    console.log(`- Duration: ${Math.round(this.testResults.summary.duration / 1000)}s`);
    console.log(`- Screenshots: ${this.screenshots.length}`);
    
    return report;
  }

  async setupDirectories() {
    const directories = [
      './docs/errors/screenshots',
      './docs/errors/videos',
      './docs/errors/reports',
      './docs/errors/performance',
      './docs/errors/cross-browser'
    ];

    for (const dir of directories) {
      await fs.mkdir(dir, { recursive: true });
    }
  }

  async setupPageCapture(page) {
    page.on('console', msg => {
      if (msg.type() === 'error') {
        this.testResults.errors.push({
          timestamp: new Date().toISOString(),
          type: 'console_error',
          message: msg.text(),
          location: msg.location()
        });
      }
    });

    page.on('pageerror', error => {
      this.testResults.errors.push({
        timestamp: new Date().toISOString(),
        type: 'page_error',
        message: error.message,
        stack: error.stack
      });
    });

    page.on('requestfailed', req => {
      this.testResults.errors.push({
        timestamp: new Date().toISOString(),
        type: 'network_error',
        url: req.url(),
        method: req.method(),
        failure: req.failure()?.errorText
      });
    });
  }

  async takeScreenshot(page, filename, category) {
    const screenshotPath = `./docs/errors/screenshots/${filename}`;
    try {
      await page.screenshot({ 
        path: screenshotPath, 
        fullPage: true 
      });
      
      this.screenshots.push({
        filename,
        path: screenshotPath,
        category,
        timestamp: new Date().toISOString()
      });
      
      return true;
    } catch (error) {
      console.warn(`Could not take screenshot ${filename}:`, error.message);
      return false;
    }
  }

  async runAuthenticationTests(page, browser) {
    console.log('🔐 Running Authentication & Project Management Tests...');
    const category = 'authentication';
    
    try {
      // Test 1: Landing page load
      await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 30000 });
      await this.takeScreenshot(page, `${browser}-auth-01-landing.png`, category);
      
      const pageTitle = await page.title();
      const testResult = {
        name: 'Landing Page Load',
        browser,
        status: pageTitle.length > 0 ? 'passed' : 'failed',
        details: `Page title: ${pageTitle}`
      };
      
      this.testResults.categories[category].tests.push(testResult);
      if (testResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
      // Test 2: Navigation functionality
      const navElements = await page.$$('[role="navigation"], nav, [data-testid*="nav"]');
      const navTestResult = {
        name: 'Navigation Elements',
        browser,
        status: navElements.length > 0 ? 'passed' : 'failed',
        details: `Found ${navElements.length} navigation elements`
      };
      
      this.testResults.categories[category].tests.push(navTestResult);
      if (navTestResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
      await this.takeScreenshot(page, `${browser}-auth-02-navigation.png`, category);
      
    } catch (error) {
      this.testResults.categories[category].tests.push({
        name: 'Authentication Tests',
        browser,
        status: 'failed',
        error: error.message
      });
      this.testResults.categories[category].failed++;
      this.testResults.summary.failedTests++;
      this.testResults.summary.totalTests++;
    }
  }

  async runVideoProcessingTests(page, browser) {
    console.log('🎥 Running Video Upload & Processing Tests...');
    const category = 'videoProcessing';
    
    try {
      await page.goto('http://localhost:3000/upload', { waitUntil: 'networkidle', timeout: 30000 });
      await this.takeScreenshot(page, `${browser}-video-01-upload-page.png`, category);
      
      // Check for upload interface elements
      const uploadElements = await page.$$('input[type="file"], [data-testid*="upload"], .upload');
      const testResult = {
        name: 'Video Upload Interface',
        browser,
        status: uploadElements.length > 0 ? 'passed' : 'failed',
        details: `Found ${uploadElements.length} upload interface elements`
      };
      
      this.testResults.categories[category].tests.push(testResult);
      if (testResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
      await this.takeScreenshot(page, `${browser}-video-02-interface.png`, category);
      
    } catch (error) {
      this.testResults.categories[category].tests.push({
        name: 'Video Processing Tests',
        browser,
        status: 'failed',
        error: error.message
      });
      this.testResults.categories[category].failed++;
      this.testResults.summary.failedTests++;
      this.testResults.summary.totalTests++;
    }
  }

  async runAIDetectionTests(page, browser) {
    console.log('🤖 Running AI Detection Pipeline Tests...');
    const category = 'aiDetection';
    
    try {
      await page.goto('http://localhost:3000/detection', { waitUntil: 'networkidle', timeout: 30000 });
      await this.takeScreenshot(page, `${browser}-ai-01-detection-page.png`, category);
      
      // Check for AI detection elements
      const detectionElements = await page.$$('[data-testid*="detection"], [data-testid*="model"], .detection, .ai');
      const testResult = {
        name: 'AI Detection Interface',
        browser,
        status: detectionElements.length > 0 ? 'passed' : 'failed',
        details: `Found ${detectionElements.length} detection interface elements`
      };
      
      this.testResults.categories[category].tests.push(testResult);
      if (testResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
      await this.takeScreenshot(page, `${browser}-ai-02-interface.png`, category);
      
    } catch (error) {
      this.testResults.categories[category].tests.push({
        name: 'AI Detection Tests',
        browser,
        status: 'failed',
        error: error.message
      });
      this.testResults.categories[category].failed++;
      this.testResults.summary.failedTests++;
      this.testResults.summary.totalTests++;
    }
  }

  async runRealtimeMonitoringTests(page, browser) {
    console.log('📊 Running Real-time Monitoring Tests...');
    const category = 'realtimeMonitoring';
    
    try {
      await page.goto('http://localhost:3000/monitoring', { waitUntil: 'networkidle', timeout: 30000 });
      await this.takeScreenshot(page, `${browser}-monitoring-01-page.png`, category);
      
      // Check for monitoring elements
      const monitoringElements = await page.$$('[data-testid*="monitoring"], [data-testid*="chart"], .monitoring, .dashboard');
      const testResult = {
        name: 'Real-time Monitoring Interface',
        browser,
        status: monitoringElements.length > 0 ? 'passed' : 'failed',
        details: `Found ${monitoringElements.length} monitoring interface elements`
      };
      
      this.testResults.categories[category].tests.push(testResult);
      if (testResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
      await this.takeScreenshot(page, `${browser}-monitoring-02-interface.png`, category);
      
    } catch (error) {
      this.testResults.categories[category].tests.push({
        name: 'Realtime Monitoring Tests',
        browser,
        status: 'failed',
        error: error.message
      });
      this.testResults.categories[category].failed++;
      this.testResults.summary.failedTests++;
      this.testResults.summary.totalTests++;
    }
  }

  async runLabJackIntegrationTests(page, browser) {
    console.log('⚡ Running LabJack Hardware Integration Tests...');
    const category = 'labjackIntegration';
    
    try {
      await page.goto('http://localhost:3000/labjack', { waitUntil: 'networkidle', timeout: 30000 });
      await this.takeScreenshot(page, `${browser}-labjack-01-page.png`, category);
      
      // Check for LabJack elements
      const labjackElements = await page.$$('[data-testid*="labjack"], [data-testid*="hardware"], .labjack, .hardware');
      const testResult = {
        name: 'LabJack Hardware Interface',
        browser,
        status: labjackElements.length > 0 ? 'passed' : 'failed',
        details: `Found ${labjackElements.length} LabJack interface elements`
      };
      
      this.testResults.categories[category].tests.push(testResult);
      if (testResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
      await this.takeScreenshot(page, `${browser}-labjack-02-interface.png`, category);
      
    } catch (error) {
      this.testResults.categories[category].tests.push({
        name: 'LabJack Integration Tests',
        browser,
        status: 'failed',
        error: error.message
      });
      this.testResults.categories[category].failed++;
      this.testResults.summary.failedTests++;
      this.testResults.summary.totalTests++;
    }
  }

  async runHILExecutionTests(page, browser) {
    console.log('🚗 Running HIL Test Execution Tests...');
    const category = 'hilExecution';
    
    try {
      await page.goto('http://localhost:3000/hil-testing', { waitUntil: 'networkidle', timeout: 30000 });
      await this.takeScreenshot(page, `${browser}-hil-01-page.png`, category);
      
      // Check for HIL elements
      const hilElements = await page.$$('[data-testid*="hil"], [data-testid*="scenario"], .hil, .scenario');
      const testResult = {
        name: 'HIL Test Execution Interface',
        browser,
        status: hilElements.length > 0 ? 'passed' : 'failed',
        details: `Found ${hilElements.length} HIL interface elements`
      };
      
      this.testResults.categories[category].tests.push(testResult);
      if (testResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
      await this.takeScreenshot(page, `${browser}-hil-02-interface.png`, category);
      
    } catch (error) {
      this.testResults.categories[category].tests.push({
        name: 'HIL Execution Tests',
        browser,
        status: 'failed',
        error: error.message
      });
      this.testResults.categories[category].failed++;
      this.testResults.summary.failedTests++;
      this.testResults.summary.totalTests++;
    }
  }

  async runPerformanceTests(page, browser) {
    console.log('⚡ Running Performance Tests...');
    const category = 'performance';
    
    try {
      const startTime = Date.now();
      await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 30000 });
      const loadTime = Date.now() - startTime;
      
      await this.takeScreenshot(page, `${browser}-perf-01-load-test.png`, category);
      
      // Performance metrics
      const metrics = await page.evaluate(() => {
        return {
          loadTime: performance.timing.loadEventEnd - performance.timing.navigationStart,
          domReady: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart,
          firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0
        };
      });
      
      const testResult = {
        name: 'Page Load Performance',
        browser,
        status: loadTime < 10000 ? 'passed' : 'failed', // 10 second threshold
        details: `Load time: ${loadTime}ms, DOM ready: ${metrics.domReady}ms`
      };
      
      this.testResults.categories[category].tests.push(testResult);
      if (testResult.status === 'passed') {
        this.testResults.categories[category].passed++;
        this.testResults.summary.passedTests++;
      } else {
        this.testResults.categories[category].failed++;
        this.testResults.summary.failedTests++;
      }
      this.testResults.summary.totalTests++;
      
    } catch (error) {
      this.testResults.categories[category].tests.push({
        name: 'Performance Tests',
        browser,
        status: 'failed',
        error: error.message
      });
      this.testResults.categories[category].failed++;
      this.testResults.summary.failedTests++;
      this.testResults.summary.totalTests++;
    }
  }

  async generateComprehensiveReport() {
    const report = {
      metadata: {
        platform: 'ADAS Camera HIL Testing Platform',
        testSuite: 'Comprehensive Playwright Tests',
        timestamp: new Date().toISOString(),
        version: '1.0.0'
      },
      summary: this.testResults.summary,
      categories: this.testResults.categories,
      artifacts: {
        screenshots: this.screenshots,
        videos: this.testResults.artifacts.videos,
        reports: this.testResults.artifacts.reports
      },
      errors: this.testResults.errors,
      warnings: this.testResults.warnings
    };

    // Save JSON report
    const reportPath = './docs/errors/reports/comprehensive-test-results.json';
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));

    // Generate HTML report
    const htmlReport = this.generateHTMLReport(report);
    await fs.writeFile('./docs/errors/reports/comprehensive-test-results.html', htmlReport);

    console.log(`📝 Comprehensive test report saved to: ${reportPath}`);
    
    return report;
  }

  generateHTMLReport(report) {
    return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ADAS Camera HIL Testing Platform - Test Results</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .header { background: #2196F3; color: white; padding: 20px; border-radius: 8px; }
            .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
            .metric { background: #f5f5f5; padding: 15px; border-radius: 8px; text-align: center; }
            .passed { color: #4CAF50; }
            .failed { color: #f44336; }
            .category { margin: 20px 0; border: 1px solid #ddd; border-radius: 8px; }
            .category-header { background: #e3f2fd; padding: 10px; font-weight: bold; }
            .test-item { padding: 10px; border-bottom: 1px solid #eee; }
            .screenshots { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; margin: 20px 0; }
            .screenshot { border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
            .screenshot img { width: 100%; height: 200px; object-fit: cover; }
            .screenshot-info { padding: 10px; background: #f9f9f9; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>ADAS Camera HIL Testing Platform</h1>
            <h2>Comprehensive Test Results</h2>
            <p>Generated: ${report.metadata.timestamp}</p>
        </div>

        <div class="summary">
            <div class="metric">
                <h3>Total Tests</h3>
                <div style="font-size: 2em;">${report.summary.totalTests}</div>
            </div>
            <div class="metric">
                <h3 class="passed">Passed Tests</h3>
                <div style="font-size: 2em;" class="passed">${report.summary.passedTests}</div>
            </div>
            <div class="metric">
                <h3 class="failed">Failed Tests</h3>
                <div style="font-size: 2em;" class="failed">${report.summary.failedTests}</div>
            </div>
            <div class="metric">
                <h3>Duration</h3>
                <div style="font-size: 2em;">${Math.round(report.summary.duration / 1000)}s</div>
            </div>
        </div>

        <h2>Test Categories</h2>
        ${Object.entries(report.categories).map(([category, data]) => `
            <div class="category">
                <div class="category-header">
                    ${category.charAt(0).toUpperCase() + category.slice(1)} 
                    (Passed: <span class="passed">${data.passed}</span>, Failed: <span class="failed">${data.failed}</span>)
                </div>
                ${data.tests.map(test => `
                    <div class="test-item">
                        <strong>${test.name}</strong> [${test.browser}]: 
                        <span class="${test.status}">${test.status.toUpperCase()}</span>
                        ${test.details ? `<br><small>${test.details}</small>` : ''}
                        ${test.error ? `<br><small style="color: red;">Error: ${test.error}</small>` : ''}
                    </div>
                `).join('')}
            </div>
        `).join('')}

        <h2>Screenshots (${report.artifacts.screenshots.length} total)</h2>
        <div class="screenshots">
            ${report.artifacts.screenshots.slice(0, 20).map(screenshot => `
                <div class="screenshot">
                    <img src="${screenshot.path}" alt="${screenshot.filename}" />
                    <div class="screenshot-info">
                        <strong>${screenshot.filename}</strong><br>
                        Category: ${screenshot.category}<br>
                        Time: ${screenshot.timestamp}
                    </div>
                </div>
            `).join('')}
        </div>

        ${report.errors.length > 0 ? `
            <h2>Errors (${report.errors.length} total)</h2>
            <div style="background: #ffebee; padding: 15px; border-radius: 8px;">
                ${report.errors.slice(0, 10).map(error => `
                    <div style="margin-bottom: 10px; padding: 10px; background: white; border-radius: 4px;">
                        <strong>${error.type}</strong>: ${error.message}<br>
                        <small>Time: ${error.timestamp}</small>
                    </div>
                `).join('')}
            </div>
        ` : ''}
    </body>
    </html>`;
  }
}

// Run if called directly
if (require.main === module) {
  const runner = new ComprehensiveTestRunner();
  runner.runAllTests()
    .then(() => console.log('🎉 Comprehensive test suite completed successfully!'))
    .catch(error => {
      console.error('💥 Test suite failed:', error);
      process.exit(1);
    });
}

module.exports = { ComprehensiveTestRunner };