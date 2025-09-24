/**
 * ADAS Camera HIL Testing Platform - Runtime Console Error Analysis
 * Using Playwright for comprehensive browser automation and error capture
 */

const { chromium, firefox, webkit } = require('playwright');
const fs = require('fs');
const path = require('path');

class RuntimeErrorAnalyzer {
  constructor() {
    this.errors = [];
    this.networkFailures = [];
    this.performanceMetrics = [];
    this.consoleMessages = [];
    this.screenshots = [];
    this.testResults = {
      projectManagement: [],
      videoUpload: [],
      detectionPipeline: [],
      realtimeMonitoring: [],
      labjackIntegration: []
    };
  }

  async setupBrowser(browserType = 'chromium') {
    console.log(`🚀 Setting up ${browserType} browser...`);
    
    const browserOptions = {
      headless: false, // Enable GUI for detailed debugging
      slowMo: 100,     // Add delay between actions for observation
      args: [
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--enable-logging',
        '--v=1'
      ]
    };

    let browser;
    switch (browserType) {
      case 'firefox':
        browser = await firefox.launch(browserOptions);
        break;
      case 'webkit':
        browser = await webkit.launch(browserOptions);
        break;
      default:
        browser = await chromium.launch(browserOptions);
    }

    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      recordVideo: {
        dir: './docs/errors/videos/',
        size: { width: 1920, height: 1080 }
      }
    });

    return { browser, context };
  }

  async setupErrorCapture(page) {
    console.log('🔍 Setting up comprehensive error capture...');

    // Capture console messages
    page.on('console', msg => {
      const timestamp = new Date().toISOString();
      const consoleEntry = {
        timestamp,
        type: msg.type(),
        text: msg.text(),
        location: msg.location()
      };
      
      this.consoleMessages.push(consoleEntry);
      
      if (['error', 'warning'].includes(msg.type())) {
        console.log(`📝 Console ${msg.type()}: ${msg.text()}`);
      }
    });

    // Capture JavaScript exceptions
    page.on('pageerror', error => {
      const timestamp = new Date().toISOString();
      const errorEntry = {
        timestamp,
        type: 'pageerror',
        name: error.name,
        message: error.message,
        stack: error.stack
      };
      
      this.errors.push(errorEntry);
      console.log(`❌ JavaScript Error: ${error.message}`);
    });

    // Capture network failures
    page.on('response', response => {
      const timestamp = new Date().toISOString();
      if (response.status() >= 400) {
        const failureEntry = {
          timestamp,
          url: response.url(),
          status: response.status(),
          statusText: response.statusText(),
          method: response.request().method(),
          headers: response.headers()
        };
        
        this.networkFailures.push(failureEntry);
        console.log(`🌐 Network Error: ${response.status()} ${response.url()}`);
      }
    });

    // Capture request failures
    page.on('requestfailed', request => {
      const timestamp = new Date().toISOString();
      const failureEntry = {
        timestamp,
        url: request.url(),
        method: request.method(),
        failure: request.failure(),
        error: 'Request failed'
      };
      
      this.networkFailures.push(failureEntry);
      console.log(`🚫 Request Failed: ${request.url()} - ${request.failure()?.errorText}`);
    });

    // Capture WebSocket errors
    page.on('websocket', ws => {
      ws.on('close', () => {
        console.log('🔌 WebSocket connection closed');
      });
      
      ws.on('socketerror', data => {
        const timestamp = new Date().toISOString();
        this.errors.push({
          timestamp,
          type: 'websocket_error',
          data
        });
        console.log('⚡ WebSocket Error:', data);
      });
    });
  }

  async capturePerformanceMetrics(page) {
    console.log('📊 Capturing performance metrics...');
    
    try {
      // Core Web Vitals and performance metrics
      const metrics = await page.evaluate(() => {
        return new Promise((resolve) => {
          if (typeof window.performance === 'undefined') {
            resolve({ error: 'Performance API not available' });
            return;
          }

          const perfData = {
            timestamp: new Date().toISOString(),
            navigation: performance.getEntriesByType('navigation')[0],
            paint: performance.getEntriesByType('paint'),
            memory: performance.memory ? {
              usedJSHeapSize: performance.memory.usedJSHeapSize,
              totalJSHeapSize: performance.memory.totalJSHeapSize,
              jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
            } : null,
            timing: performance.timing
          };

          // Core Web Vitals
          if (window.chrome && window.chrome.loadTimes) {
            perfData.loadTimes = window.chrome.loadTimes();
          }

          resolve(perfData);
        });
      });

      this.performanceMetrics.push(metrics);
      
      if (metrics.memory) {
        const memoryUsageMB = Math.round(metrics.memory.usedJSHeapSize / 1024 / 1024);
        console.log(`💾 Memory Usage: ${memoryUsageMB} MB`);
      }
    } catch (error) {
      console.log('⚠️ Could not capture performance metrics:', error.message);
    }
  }

  async takeScreenshot(page, filename) {
    const screenshotPath = `./docs/errors/screenshots/${filename}`;
    await page.screenshot({ 
      path: screenshotPath, 
      fullPage: true 
    });
    this.screenshots.push({
      filename,
      path: screenshotPath,
      timestamp: new Date().toISOString()
    });
    console.log(`📸 Screenshot saved: ${filename}`);
  }

  async testProjectManagement(page) {
    console.log('🏗️ Testing Project Creation and Management...');
    
    try {
      await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
      await this.capturePerformanceMetrics(page);
      await this.takeScreenshot(page, 'project-management-initial.png');

      // Test project creation
      await page.click('[data-testid="create-project-button"]', { timeout: 5000 });
      await page.waitForSelector('[data-testid="project-form"]', { timeout: 10000 });
      
      await page.fill('[data-testid="project-name"]', 'Test ADAS Project');
      await page.fill('[data-testid="project-description"]', 'Runtime error testing project');
      
      await this.takeScreenshot(page, 'project-creation-form.png');
      
      await page.click('[data-testid="submit-project"]');
      await page.waitForSelector('[data-testid="project-success"]', { timeout: 15000 });
      
      this.testResults.projectManagement.push({
        test: 'Project Creation',
        status: 'success',
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      await this.takeScreenshot(page, 'project-management-error.png');
      this.testResults.projectManagement.push({
        test: 'Project Creation',
        status: 'failed',
        error: error.message,
        timestamp: new Date().toISOString()
      });
      console.log('❌ Project management test failed:', error.message);
    }
  }

  async testVideoUpload(page) {
    console.log('🎥 Testing Video Upload and Processing...');
    
    try {
      await page.goto('http://localhost:3000/upload', { waitUntil: 'networkidle' });
      await this.takeScreenshot(page, 'video-upload-initial.png');

      // Test video upload interface
      const fileInput = await page.$('[data-testid="video-upload-input"]');
      if (fileInput) {
        // Create a mock video file for testing
        const mockVideoPath = './docs/errors/mock-test-video.mp4';
        await fileInput.setInputFiles(mockVideoPath);
        
        await page.click('[data-testid="start-upload"]');
        await page.waitForSelector('[data-testid="upload-progress"]', { timeout: 10000 });
        
        this.testResults.videoUpload.push({
          test: 'Video Upload',
          status: 'success',
          timestamp: new Date().toISOString()
        });
      }

    } catch (error) {
      await this.takeScreenshot(page, 'video-upload-error.png');
      this.testResults.videoUpload.push({
        test: 'Video Upload',
        status: 'failed',
        error: error.message,
        timestamp: new Date().toISOString()
      });
      console.log('❌ Video upload test failed:', error.message);
    }
  }

  async testDetectionPipeline(page) {
    console.log('🔍 Testing Detection Pipeline Execution...');
    
    try {
      await page.goto('http://localhost:3000/pipeline', { waitUntil: 'networkidle' });
      await this.takeScreenshot(page, 'detection-pipeline-initial.png');

      // Test pipeline configuration
      await page.click('[data-testid="configure-pipeline"]');
      await page.waitForSelector('[data-testid="pipeline-config"]', { timeout: 10000 });
      
      // Configure detection parameters
      await page.selectOption('[data-testid="model-select"]', 'yolo-v8');
      await page.fill('[data-testid="confidence-threshold"]', '0.5');
      
      await this.takeScreenshot(page, 'pipeline-configuration.png');
      
      await page.click('[data-testid="start-pipeline"]');
      await page.waitForSelector('[data-testid="pipeline-running"]', { timeout: 20000 });
      
      this.testResults.detectionPipeline.push({
        test: 'Pipeline Execution',
        status: 'success',
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      await this.takeScreenshot(page, 'detection-pipeline-error.png');
      this.testResults.detectionPipeline.push({
        test: 'Pipeline Execution',
        status: 'failed',
        error: error.message,
        timestamp: new Date().toISOString()
      });
      console.log('❌ Detection pipeline test failed:', error.message);
    }
  }

  async testRealtimeMonitoring(page) {
    console.log('📊 Testing Real-time Test Session Monitoring...');
    
    try {
      await page.goto('http://localhost:3000/monitoring', { waitUntil: 'networkidle' });
      await this.takeScreenshot(page, 'realtime-monitoring-initial.png');

      // Wait for WebSocket connection
      await page.waitForFunction(
        () => window.WebSocket && window.socketConnection,
        { timeout: 15000 }
      );

      // Test real-time data updates
      await page.waitForSelector('[data-testid="live-metrics"]', { timeout: 10000 });
      
      // Check for data flow
      const metricsUpdated = await page.waitForFunction(
        () => {
          const metrics = document.querySelector('[data-testid="metrics-value"]');
          return metrics && metrics.textContent !== '0';
        },
        { timeout: 30000 }
      );

      if (metricsUpdated) {
        this.testResults.realtimeMonitoring.push({
          test: 'Real-time Monitoring',
          status: 'success',
          timestamp: new Date().toISOString()
        });
      }

    } catch (error) {
      await this.takeScreenshot(page, 'realtime-monitoring-error.png');
      this.testResults.realtimeMonitoring.push({
        test: 'Real-time Monitoring',
        status: 'failed',
        error: error.message,
        timestamp: new Date().toISOString()
      });
      console.log('❌ Real-time monitoring test failed:', error.message);
    }
  }

  async testLabJackIntegration(page) {
    console.log('⚡ Testing LabJack Hardware Integration UI...');
    
    try {
      await page.goto('http://localhost:3000/labjack', { waitUntil: 'networkidle' });
      await this.takeScreenshot(page, 'labjack-integration-initial.png');

      // Test hardware connection status
      await page.waitForSelector('[data-testid="labjack-status"]', { timeout: 10000 });
      
      // Test hardware configuration
      await page.click('[data-testid="configure-labjack"]');
      await page.waitForSelector('[data-testid="labjack-config-panel"]', { timeout: 5000 });
      
      // Configure channels
      await page.fill('[data-testid="channel-config"]', '{"AIN0": "voltage", "DIO0": "output"}');
      await page.click('[data-testid="apply-config"]');
      
      await this.takeScreenshot(page, 'labjack-configuration.png');
      
      this.testResults.labjackIntegration.push({
        test: 'LabJack Integration',
        status: 'success',
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      await this.takeScreenshot(page, 'labjack-integration-error.png');
      this.testResults.labjackIntegration.push({
        test: 'LabJack Integration',
        status: 'failed',
        error: error.message,
        timestamp: new Date().toISOString()
      });
      console.log('❌ LabJack integration test failed:', error.message);
    }
  }

  async generateReport() {
    console.log('📝 Generating comprehensive runtime error report...');
    
    const report = {
      timestamp: new Date().toISOString(),
      summary: {
        totalErrors: this.errors.length,
        networkFailures: this.networkFailures.length,
        consoleMessages: this.consoleMessages.length,
        screenshotsTaken: this.screenshots.length
      },
      errors: this.errors,
      networkFailures: this.networkFailures,
      consoleMessages: this.consoleMessages,
      performanceMetrics: this.performanceMetrics,
      testResults: this.testResults,
      screenshots: this.screenshots
    };

    const reportPath = './docs/errors/05_runtime_console_errors.json';
    await fs.promises.writeFile(reportPath, JSON.stringify(report, null, 2));
    
    return report;
  }
}

async function runComprehensiveRuntimeAnalysis() {
  const analyzer = new RuntimeErrorAnalyzer();
  
  console.log('🎬 Starting ADAS Camera HIL Testing Platform Runtime Analysis...');
  
  // Create necessary directories
  await fs.promises.mkdir('./docs/errors/screenshots', { recursive: true });
  await fs.promises.mkdir('./docs/errors/videos', { recursive: true });

  const browsers = ['chromium', 'firefox']; // Test on multiple browsers
  
  for (const browserType of browsers) {
    console.log(`\n🔍 Testing with ${browserType}...`);
    
    const { browser, context } = await analyzer.setupBrowser(browserType);
    const page = await context.newPage();
    
    await analyzer.setupErrorCapture(page);
    
    // Run all test workflows
    await analyzer.testProjectManagement(page);
    await analyzer.testVideoUpload(page);
    await analyzer.testDetectionPipeline(page);
    await analyzer.testRealtimeMonitoring(page);
    await analyzer.testLabJackIntegration(page);
    
    await browser.close();
    console.log(`✅ ${browserType} testing completed`);
  }
  
  const report = await analyzer.generateReport();
  console.log('\n📊 Runtime Analysis Summary:');
  console.log(`- Total Errors: ${report.summary.totalErrors}`);
  console.log(`- Network Failures: ${report.summary.networkFailures}`);
  console.log(`- Console Messages: ${report.summary.consoleMessages}`);
  console.log(`- Screenshots: ${report.summary.screenshotsTaken}`);
  
  return report;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { RuntimeErrorAnalyzer, runComprehensiveRuntimeAnalysis };
}

// Run if called directly
if (require.main === module) {
  runComprehensiveRuntimeAnalysis()
    .then(() => console.log('🎉 Analysis completed successfully!'))
    .catch(error => {
      console.error('💥 Analysis failed:', error);
      process.exit(1);
    });
}