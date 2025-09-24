/**
 * ADAS Camera HIL Testing Platform - Runtime Error Capture
 * Captures console errors, network failures, and performance issues
 */

const puppeteer = require('puppeteer');
const fs = require('fs').promises;
const path = require('path');

class RuntimeErrorCapturer {
  constructor() {
    this.errors = {
      consoleErrors: [],
      networkFailures: [],
      jsExceptions: [],
      performanceIssues: [],
      webSocketErrors: [],
      reactErrors: [],
      typeScriptErrors: []
    };
    
    this.testResults = {
      basicNavigation: null,
      dataFetching: null,
      webSocketConnection: null,
      userInteractions: null
    };
  }

  async setupBrowser() {
    console.log('🚀 Starting browser with error capture...');
    
    this.browser = await puppeteer.launch({
      headless: false,
      slowMo: 100,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--remote-debugging-port=9222'
      ]
    });

    this.page = await this.browser.newPage();
    
    // Set viewport
    await this.page.setViewport({ width: 1920, height: 1080 });
    
    this.setupErrorListeners();
    return this.page;
  }

  setupErrorListeners() {
    console.log('🔍 Setting up error listeners...');

    // Console messages
    this.page.on('console', msg => {
      const timestamp = new Date().toISOString();
      const entry = {
        timestamp,
        type: msg.type(),
        text: msg.text(),
        location: msg.location()
      };

      if (['error', 'warning'].includes(msg.type())) {
        this.errors.consoleErrors.push(entry);
        console.log(`📝 Console ${msg.type()}: ${msg.text()}`);
      }
    });

    // JavaScript exceptions
    this.page.on('pageerror', error => {
      const timestamp = new Date().toISOString();
      const entry = {
        timestamp,
        name: error.name,
        message: error.message,
        stack: error.stack
      };
      
      this.errors.jsExceptions.push(entry);
      console.log(`❌ JS Exception: ${error.message}`);
    });

    // Network failures
    this.page.on('response', response => {
      if (response.status() >= 400) {
        const timestamp = new Date().toISOString();
        const entry = {
          timestamp,
          url: response.url(),
          status: response.status(),
          statusText: response.statusText(),
          method: response.request().method()
        };
        
        this.errors.networkFailures.push(entry);
        console.log(`🌐 Network Error: ${response.status()} ${response.url()}`);
      }
    });

    // Request failures
    this.page.on('requestfailed', request => {
      const timestamp = new Date().toISOString();
      const entry = {
        timestamp,
        url: request.url(),
        method: request.method(),
        failure: request.failure()?.errorText || 'Unknown failure'
      };
      
      this.errors.networkFailures.push(entry);
      console.log(`🚫 Request Failed: ${request.url()}`);
    });
  }

  async capturePageErrors() {
    try {
      console.log('🔍 Navigating to application...');
      await this.page.goto('http://localhost:3000', { 
        waitUntil: 'networkidle0',
        timeout: 30000 
      });

      // Wait for React app to load
      await this.page.waitForTimeout(3000);
      
      // Take screenshot of initial state
      await this.page.screenshot({ 
        path: './docs/errors/screenshots/initial-load.png',
        fullPage: true 
      });

      console.log('✅ Initial page load completed');
      this.testResults.basicNavigation = 'success';

    } catch (error) {
      console.log('❌ Page load failed:', error.message);
      this.testResults.basicNavigation = `failed: ${error.message}`;
      
      await this.page.screenshot({ 
        path: './docs/errors/screenshots/page-load-error.png',
        fullPage: true 
      });
    }
  }

  async testDataFetching() {
    console.log('📊 Testing API data fetching...');
    
    try {
      // Monitor network requests
      const apiRequests = [];
      this.page.on('response', response => {
        if (response.url().includes('/api/')) {
          apiRequests.push({
            url: response.url(),
            status: response.status(),
            timestamp: new Date().toISOString()
          });
        }
      });

      // Try to trigger API calls by navigating to different sections
      const navButtons = await this.page.$$('[data-testid*="nav"], [href*="/"], button');
      
      if (navButtons.length > 0) {
        for (let i = 0; i < Math.min(3, navButtons.length); i++) {
          try {
            await navButtons[i].click();
            await this.page.waitForTimeout(2000);
          } catch (clickError) {
            console.log(`⚠️ Could not click navigation element ${i}`);
          }
        }
      }

      console.log(`📡 Captured ${apiRequests.length} API requests`);
      this.testResults.dataFetching = `success: ${apiRequests.length} requests monitored`;

    } catch (error) {
      console.log('❌ Data fetching test failed:', error.message);
      this.testResults.dataFetching = `failed: ${error.message}`;
    }
  }

  async testWebSocketConnection() {
    console.log('🔌 Testing WebSocket connections...');
    
    try {
      // Inject code to monitor WebSocket connections
      await this.page.evaluateOnNewDocument(() => {
        const originalWebSocket = window.WebSocket;
        window.WebSocket = function(...args) {
          const ws = new originalWebSocket(...args);
          
          ws.addEventListener('open', () => {
            console.log('WebSocket connected:', args[0]);
          });
          
          ws.addEventListener('error', (error) => {
            console.error('WebSocket error:', error);
          });
          
          ws.addEventListener('close', (event) => {
            console.log('WebSocket closed:', event.code, event.reason);
          });
          
          return ws;
        };
      });

      // Wait for potential WebSocket connections
      await this.page.waitForTimeout(5000);
      
      this.testResults.webSocketConnection = 'monitoring completed';

    } catch (error) {
      console.log('❌ WebSocket test failed:', error.message);
      this.testResults.webSocketConnection = `failed: ${error.message}`;
    }
  }

  async testUserInteractions() {
    console.log('👆 Testing user interactions...');
    
    try {
      // Test form interactions
      const inputs = await this.page.$$('input[type="text"], input[type="email"], textarea');
      
      for (let i = 0; i < Math.min(2, inputs.length); i++) {
        try {
          await inputs[i].click();
          await inputs[i].type('test input');
          await this.page.waitForTimeout(500);
        } catch (inputError) {
          console.log(`⚠️ Could not interact with input ${i}`);
        }
      }

      // Test button clicks
      const buttons = await this.page.$$('button');
      
      for (let i = 0; i < Math.min(3, buttons.length); i++) {
        try {
          const isVisible = await buttons[i].isIntersectingViewport();
          if (isVisible) {
            await buttons[i].click();
            await this.page.waitForTimeout(1000);
          }
        } catch (buttonError) {
          console.log(`⚠️ Could not click button ${i}`);
        }
      }

      await this.page.screenshot({ 
        path: './docs/errors/screenshots/after-interactions.png',
        fullPage: true 
      });

      this.testResults.userInteractions = 'completed';

    } catch (error) {
      console.log('❌ User interaction test failed:', error.message);
      this.testResults.userInteractions = `failed: ${error.message}`;
    }
  }

  async capturePerformanceMetrics() {
    console.log('📊 Capturing performance metrics...');
    
    try {
      const metrics = await this.page.evaluate(() => {
        const perfData = performance.getEntriesByType('navigation')[0];
        const paintEntries = performance.getEntriesByType('paint');
        
        return {
          timestamp: new Date().toISOString(),
          loadComplete: perfData?.loadEventEnd - perfData?.loadEventStart,
          domContentLoaded: perfData?.domContentLoadedEventEnd - perfData?.domContentLoadedEventStart,
          firstPaint: paintEntries.find(entry => entry.name === 'first-paint')?.startTime,
          firstContentfulPaint: paintEntries.find(entry => entry.name === 'first-contentful-paint')?.startTime,
          memory: performance.memory ? {
            used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
            total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024),
            limit: Math.round(performance.memory.jsHeapSizeLimit / 1024 / 1024)
          } : null
        };
      });

      this.errors.performanceIssues.push(metrics);
      console.log(`💾 Memory usage: ${metrics.memory?.used || 'N/A'} MB`);

    } catch (error) {
      console.log('⚠️ Could not capture performance metrics:', error.message);
    }
  }

  async generateReport() {
    console.log('📝 Generating runtime error report...');
    
    const report = {
      timestamp: new Date().toISOString(),
      summary: {
        consoleErrors: this.errors.consoleErrors.length,
        networkFailures: this.errors.networkFailures.length,
        jsExceptions: this.errors.jsExceptions.length,
        performanceMetrics: this.errors.performanceIssues.length
      },
      testResults: this.testResults,
      detailedErrors: this.errors,
      applicationStatus: {
        frontend: 'http://localhost:3000',
        backend: 'Backend running with warnings'
      }
    };

    // Create directories if they don't exist
    await fs.mkdir('./docs/errors/screenshots', { recursive: true }).catch(() => {});
    
    // Save JSON report
    await fs.writeFile('./docs/errors/runtime-analysis-results.json', JSON.stringify(report, null, 2));
    
    return report;
  }

  async cleanup() {
    if (this.browser) {
      await this.browser.close();
    }
  }
}

async function runRuntimeAnalysis() {
  const capturer = new RuntimeErrorCapturer();
  
  try {
    await capturer.setupBrowser();
    await capturer.capturePageErrors();
    await capturer.testDataFetching();
    await capturer.testWebSocketConnection();
    await capturer.testUserInteractions();
    await capturer.capturePerformanceMetrics();
    
    const report = await capturer.generateReport();
    
    console.log('\n📊 Runtime Analysis Summary:');
    console.log(`Console Errors: ${report.summary.consoleErrors}`);
    console.log(`Network Failures: ${report.summary.networkFailures}`);
    console.log(`JS Exceptions: ${report.summary.jsExceptions}`);
    console.log(`Performance Metrics: ${report.summary.performanceMetrics}`);
    
    return report;
    
  } catch (error) {
    console.error('💥 Analysis failed:', error);
    throw error;
  } finally {
    await capturer.cleanup();
  }
}

module.exports = { RuntimeErrorCapturer, runRuntimeAnalysis };

// Run if called directly
if (require.main === module) {
  runRuntimeAnalysis()
    .then(() => console.log('🎉 Runtime analysis completed!'))
    .catch(error => {
      console.error('💥 Analysis failed:', error);
      process.exit(1);
    });
}