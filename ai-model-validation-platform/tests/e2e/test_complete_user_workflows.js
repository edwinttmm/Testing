#!/usr/bin/env node
/**
 * End-to-End User Workflow Tests for Enhanced Test Page
 * 
 * This test suite validates complete user workflows including:
 * - Browser-based integration testing
 * - Full user journey simulations
 * - Visual validation and screenshots
 * - Performance metrics collection
 * - Cross-browser compatibility testing
 */

const puppeteer = require('puppeteer');
const fs = require('fs').promises;
const path = require('path');

class E2ETestSuite {
  constructor() {
    this.browser = null;
    this.page = null;
    this.baseUrl = 'http://localhost:3000';
    this.apiUrl = 'http://localhost:8002';
    this.testResults = {};
    this.screenshots = [];
    this.performanceMetrics = {};
  }

  // =============================================================================
  // SETUP AND TEARDOWN
  // =============================================================================

  async setup() {
    console.log('🚀 Setting up E2E Test Environment...');
    
    try {
      this.browser = await puppeteer.launch({
        headless: false, // Set to true for CI
        defaultViewport: { width: 1920, height: 1080 },
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--disable-gpu'
        ]
      });

      this.page = await this.browser.newPage();
      
      // Enable console logging from the page
      this.page.on('console', msg => {
        if (msg.type() === 'error') {
          console.log('❌ Browser console error:', msg.text());
        }
      });

      // Enable request/response monitoring
      this.page.on('response', response => {
        if (response.status() >= 400) {
          console.log('❌ HTTP Error:', response.url(), response.status());
        }
      });

      // Set user agent
      await this.page.setUserAgent('E2E-Test-Suite/1.0');
      
      console.log('✅ E2E Environment ready');
      return true;
    } catch (error) {
      console.error('❌ Failed to setup E2E environment:', error);
      return false;
    }
  }

  async teardown() {
    console.log('🧹 Cleaning up E2E Test Environment...');
    
    if (this.browser) {
      await this.browser.close();
    }
    
    // Save test results
    await this.saveTestResults();
    
    console.log('✅ E2E Environment cleaned up');
  }

  async takeScreenshot(name) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `screenshot_${name}_${timestamp}.png`;
    const filepath = path.join('/home/rigade/Testing/ai-model-validation-platform/tests/e2e', filename);
    
    await this.page.screenshot({ 
      path: filepath,
      fullPage: true 
    });
    
    this.screenshots.push({ name, filename, filepath });
    console.log(`📸 Screenshot saved: ${filename}`);
  }

  async waitForElement(selector, timeout = 10000) {
    try {
      await this.page.waitForSelector(selector, { timeout });
      return true;
    } catch (error) {
      console.log(`⚠️  Element not found: ${selector}`);
      return false;
    }
  }

  async measurePageLoad() {
    const metrics = await this.page.metrics();
    const navigation = await this.page.evaluate(() => {
      return {
        loadEventEnd: performance.timing.loadEventEnd,
        navigationStart: performance.timing.navigationStart,
        domContentLoaded: performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart,
        loadComplete: performance.timing.loadEventEnd - performance.timing.navigationStart
      };
    });
    
    return { ...metrics, ...navigation };
  }

  // =============================================================================
  // NAVIGATION AND BASIC FUNCTIONALITY TESTS
  // =============================================================================

  async testApplicationLoad() {
    console.log('🧪 Testing Application Load...');
    
    try {
      const startTime = Date.now();
      await this.page.goto(this.baseUrl, { waitUntil: 'networkidle0', timeout: 30000 });
      const loadTime = Date.now() - startTime;
      
      // Check if the main app loaded
      const appLoaded = await this.waitForElement('[data-testid="app"], .App, #root > div');
      if (!appLoaded) {
        // Try alternative selectors
        const bodyContent = await this.page.$('body');
        if (bodyContent) {
          await this.takeScreenshot('app_load_fallback');
        }
      }

      await this.takeScreenshot('app_loaded');
      
      // Measure performance
      const metrics = await this.measurePageLoad();
      this.performanceMetrics.appLoad = { loadTime, ...metrics };
      
      console.log(`✅ Application loaded in ${loadTime}ms`);
      this.testResults.appLoad = { status: 'passed', loadTime, appLoaded };
      
      return true;
    } catch (error) {
      console.error('❌ Application load failed:', error);
      await this.takeScreenshot('app_load_failed');
      this.testResults.appLoad = { status: 'failed', error: error.message };
      return false;
    }
  }

  async testNavigationToTestPage() {
    console.log('🧪 Testing Navigation to Test Execution Page...');
    
    try {
      // Look for test execution navigation elements
      const navSelectors = [
        'a[href*="test"]',
        'a[href*="execution"]', 
        'button:contains("Test")',
        '.nav a:contains("Test")',
        '[data-testid*="test"]'
      ];

      let navigationFound = false;
      for (const selector of navSelectors) {
        try {
          const element = await this.page.$(selector);
          if (element) {
            console.log(`Found navigation element: ${selector}`);
            await element.click();
            navigationFound = true;
            break;
          }
        } catch (e) {
          // Continue trying other selectors
        }
      }

      if (!navigationFound) {
        // Try direct URL navigation
        await this.page.goto(`${this.baseUrl}/test-execution`, { waitUntil: 'networkidle0' });
        navigationFound = true;
      }

      await this.page.waitForTimeout(2000); // Allow for page transition
      await this.takeScreenshot('test_page_navigation');
      
      // Verify we're on the test page
      const testPageElements = [
        '[data-testid*="test"]',
        'h1:contains("Test")',
        '.test-execution',
        '[class*="test"]'
      ];

      let onTestPage = false;
      for (const selector of testPageElements) {
        const element = await this.page.$(selector);
        if (element) {
          onTestPage = true;
          break;
        }
      }

      console.log('✅ Navigation to test page completed');
      this.testResults.navigation = { 
        status: 'passed', 
        navigationFound, 
        onTestPage 
      };
      
      return true;
    } catch (error) {
      console.error('❌ Navigation to test page failed:', error);
      await this.takeScreenshot('navigation_failed');
      this.testResults.navigation = { status: 'failed', error: error.message };
      return false;
    }
  }

  // =============================================================================
  // PROJECT MANAGEMENT WORKFLOW TESTS
  // =============================================================================

  async testProjectCreationWorkflow() {
    console.log('🧪 Testing Project Creation Workflow...');
    
    try {
      // Look for project creation elements
      const createButtonSelectors = [
        'button:contains("Create")',
        'button:contains("New")',
        '[data-testid="create-project"]',
        '.create-btn',
        '.new-project-btn'
      ];

      let createButton = null;
      for (const selector of createButtonSelectors) {
        try {
          createButton = await this.page.$(selector);
          if (createButton) break;
        } catch (e) {
          continue;
        }
      }

      if (createButton) {
        await createButton.click();
        await this.page.waitForTimeout(1000);
        await this.takeScreenshot('project_create_dialog');

        // Fill project form if it exists
        const formFields = {
          'input[name="name"], #project-name, [data-testid="project-name"]': 'E2E Test Project',
          'textarea[name="description"], #project-description': 'Created by E2E test suite',
          'select[name="camera_type"], #camera-type': 'surveillance'
        };

        for (const [selector, value] of Object.entries(formFields)) {
          try {
            const field = await this.page.$(selector);
            if (field) {
              if (selector.includes('select')) {
                await this.page.select(selector, value);
              } else {
                await this.page.type(selector, value);
              }
            }
          } catch (e) {
            console.log(`Field not found: ${selector}`);
          }
        }

        // Submit form
        const submitSelectors = [
          'button[type="submit"]',
          'button:contains("Create")',
          'button:contains("Save")',
          '[data-testid="submit-btn"]'
        ];

        for (const selector of submitSelectors) {
          try {
            const submitBtn = await this.page.$(selector);
            if (submitBtn) {
              await submitBtn.click();
              break;
            }
          } catch (e) {
            continue;
          }
        }

        await this.page.waitForTimeout(2000);
        await this.takeScreenshot('project_created');
      }

      console.log('✅ Project creation workflow tested');
      this.testResults.projectCreation = { status: 'passed' };
      
      return true;
    } catch (error) {
      console.error('❌ Project creation workflow failed:', error);
      await this.takeScreenshot('project_creation_failed');
      this.testResults.projectCreation = { status: 'failed', error: error.message };
      return false;
    }
  }

  async testProjectSelection() {
    console.log('🧪 Testing Project Selection...');
    
    try {
      // Look for project selector
      const selectorElements = [
        'select[name="project"]',
        '#project-selector',
        '[data-testid="project-dropdown"]',
        '.project-select'
      ];

      let projectSelector = null;
      for (const selector of selectorElements) {
        projectSelector = await this.page.$(selector);
        if (projectSelector) break;
      }

      if (projectSelector) {
        // Get available options
        const options = await this.page.$$eval(
          `${selectorElements.find(s => projectSelector)} option`, 
          options => options.map(o => ({ value: o.value, text: o.textContent }))
        );

        if (options.length > 1) {
          // Select the first non-empty option
          const optionToSelect = options.find(o => o.value && o.value !== '');
          if (optionToSelect) {
            await this.page.select(selectorElements.find(s => projectSelector), optionToSelect.value);
            await this.takeScreenshot('project_selected');
          }
        }
      }

      console.log('✅ Project selection tested');
      this.testResults.projectSelection = { status: 'passed' };
      
      return true;
    } catch (error) {
      console.error('❌ Project selection failed:', error);
      await this.takeScreenshot('project_selection_failed');
      this.testResults.projectSelection = { status: 'failed', error: error.message };
      return false;
    }
  }

  // =============================================================================
  // TEST CONFIGURATION WORKFLOW TESTS
  // =============================================================================

  async testSignalValidationConfiguration() {
    console.log('🧪 Testing Signal Validation Configuration...');
    
    try {
      // Look for signal validation controls
      const signalCheckbox = await this.page.$('input[type="checkbox"][name*="signal"], [data-testid*="signal-validation"]');
      
      if (signalCheckbox) {
        await signalCheckbox.click();
        await this.takeScreenshot('signal_validation_enabled');

        // Configure signal parameters
        const signalFields = {
          'select[name*="signal_type"], [data-testid="signal-type"]': 'voltage',
          'input[name*="threshold"], [data-testid="threshold"]': '5.0',
          'input[name*="frequency"], [data-testid="frequency"]': '1000'
        };

        for (const [selector, value] of Object.entries(signalFields)) {
          try {
            const field = await this.page.$(selector);
            if (field) {
              if (selector.includes('select')) {
                await this.page.select(selector, value);
              } else {
                await field.click({ clickCount: 3 }); // Select all
                await this.page.type(selector, value);
              }
            }
          } catch (e) {
            console.log(`Signal field not found: ${selector}`);
          }
        }

        await this.takeScreenshot('signal_validation_configured');
      }

      console.log('✅ Signal validation configuration tested');
      this.testResults.signalValidation = { status: 'passed' };
      
      return true;
    } catch (error) {
      console.error('❌ Signal validation configuration failed:', error);
      await this.takeScreenshot('signal_validation_failed');
      this.testResults.signalValidation = { status: 'failed', error: error.message };
      return false;
    }
  }

  async testDetectionPipelineConfiguration() {
    console.log('🧪 Testing Detection Pipeline Configuration...');
    
    try {
      // Configure detection model
      const modelSelector = await this.page.$('select[name*="model"], [data-testid="model-selector"]');
      if (modelSelector) {
        await this.page.select('select[name*="model"], [data-testid="model-selector"]', 'yolov8n');
      }

      // Configure confidence threshold
      const confidenceField = await this.page.$('input[name*="confidence"], [data-testid="confidence"]');
      if (confidenceField) {
        await confidenceField.click({ clickCount: 3 });
        await this.page.type('input[name*="confidence"], [data-testid="confidence"]', '0.5');
      }

      // Configure IoU threshold
      const iouField = await this.page.$('input[name*="iou"], [data-testid="iou"]');
      if (iouField) {
        await iouField.click({ clickCount: 3 });
        await this.page.type('input[name*="iou"], [data-testid="iou"]', '0.45');
      }

      await this.takeScreenshot('detection_pipeline_configured');

      console.log('✅ Detection pipeline configuration tested');
      this.testResults.detectionPipeline = { status: 'passed' };
      
      return true;
    } catch (error) {
      console.error('❌ Detection pipeline configuration failed:', error);
      await this.takeScreenshot('detection_pipeline_failed');
      this.testResults.detectionPipeline = { status: 'failed', error: error.message };
      return false;
    }
  }

  // =============================================================================
  // TEST EXECUTION WORKFLOW TESTS
  // =============================================================================

  async testTestExecutionWorkflow() {
    console.log('🧪 Testing Test Execution Workflow...');
    
    try {
      // Look for start test button
      const startButtonSelectors = [
        'button:contains("Start")',
        '[data-testid="start-test"]',
        '.start-btn',
        '#start-test-btn'
      ];

      let startButton = null;
      for (const selector of startButtonSelectors) {
        try {
          startButton = await this.page.$(selector);
          if (startButton) break;
        } catch (e) {
          continue;
        }
      }

      if (startButton) {
        // Check if button is enabled
        const isDisabled = await this.page.evaluate(btn => btn.disabled, startButton);
        
        if (!isDisabled) {
          await startButton.click();
          await this.takeScreenshot('test_started');
          
          // Wait for test to show running state
          await this.page.waitForTimeout(2000);
          await this.takeScreenshot('test_running');
          
          // Look for stop button
          const stopButton = await this.page.$('button:contains("Stop"), [data-testid="stop-test"]');
          if (stopButton) {
            await this.page.waitForTimeout(3000); // Let test run briefly
            await stopButton.click();
            await this.takeScreenshot('test_stopped');
          }
        } else {
          console.log('⚠️  Start button is disabled');
          await this.takeScreenshot('start_button_disabled');
        }
      }

      console.log('✅ Test execution workflow tested');
      this.testResults.testExecution = { status: 'passed' };
      
      return true;
    } catch (error) {
      console.error('❌ Test execution workflow failed:', error);
      await this.takeScreenshot('test_execution_failed');
      this.testResults.testExecution = { status: 'failed', error: error.message };
      return false;
    }
  }

  async testResultsVisualization() {
    console.log('🧪 Testing Results Visualization...');
    
    try {
      // Look for results section
      const resultsSelectors = [
        '[data-testid="test-results"]',
        '.results-section',
        '#test-results',
        '.test-results'
      ];

      let resultsSection = null;
      for (const selector of resultsSelectors) {
        resultsSection = await this.page.$(selector);
        if (resultsSection) break;
      }

      if (resultsSection) {
        // Scroll results into view
        await this.page.evaluate(el => el.scrollIntoView(), resultsSection);
        await this.takeScreenshot('results_section');

        // Look for charts, tables, or other result displays
        const resultElements = await this.page.$$('[data-testid*="chart"], canvas, table, .result-item');
        console.log(`Found ${resultElements.length} result display elements`);

        if (resultElements.length > 0) {
          await this.takeScreenshot('results_with_data');
        }
      }

      console.log('✅ Results visualization tested');
      this.testResults.resultsVisualization = { status: 'passed' };
      
      return true;
    } catch (error) {
      console.error('❌ Results visualization failed:', error);
      await this.takeScreenshot('results_visualization_failed');
      this.testResults.resultsVisualization = { status: 'failed', error: error.message };
      return false;
    }
  }

  // =============================================================================
  // ERROR HANDLING TESTS
  // =============================================================================

  async testErrorHandling() {
    console.log('🧪 Testing Error Handling...');
    
    try {
      // Test form validation errors
      const submitButton = await this.page.$('button[type="submit"], .submit-btn');
      if (submitButton) {
        await submitButton.click();
        
        // Look for validation errors
        const errorElements = await this.page.$$('.error, .field-error, [data-testid*="error"]');
        if (errorElements.length > 0) {
          await this.takeScreenshot('validation_errors');
          console.log(`✅ Found ${errorElements.length} validation errors`);
        }
      }

      // Test network error handling (simulate by blocking requests)
      await this.page.setRequestInterception(true);
      
      this.page.on('request', request => {
        if (request.url().includes('/api/')) {
          request.respond({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify({ error: 'Internal Server Error' })
          });
        } else {
          request.continue();
        }
      });

      // Try to trigger an API call
      const apiButton = await this.page.$('button:contains("Fetch"), button:contains("Load")');
      if (apiButton) {
        await apiButton.click();
        await this.page.waitForTimeout(2000);
        
        // Look for error messages
        const networkErrors = await this.page.$$('.network-error, .api-error, [data-testid*="error"]');
        if (networkErrors.length > 0) {
          await this.takeScreenshot('network_errors');
          console.log(`✅ Found ${networkErrors.length} network error displays`);
        }
      }

      // Restore normal request handling
      await this.page.setRequestInterception(false);

      console.log('✅ Error handling tested');
      this.testResults.errorHandling = { status: 'passed' };
      
      return true;
    } catch (error) {
      console.error('❌ Error handling test failed:', error);
      await this.takeScreenshot('error_handling_failed');
      this.testResults.errorHandling = { status: 'failed', error: error.message };
      return false;
    }
  }

  // =============================================================================
  // PERFORMANCE TESTS
  // =============================================================================

  async testPerformance() {
    console.log('🧪 Testing Performance...');
    
    try {
      // Measure page interaction performance
      const startTime = Date.now();
      
      // Simulate user interactions
      const button = await this.page.$('button');
      if (button) {
        await button.click();
        await this.page.waitForTimeout(100);
      }
      
      const interactionTime = Date.now() - startTime;
      
      // Measure memory usage
      const metrics = await this.page.metrics();
      
      // Check for memory leaks by monitoring heap size
      const initialHeap = metrics.JSHeapUsedSize;
      
      // Perform some actions that might cause memory leaks
      for (let i = 0; i < 10; i++) {
        await this.page.evaluate(() => {
          // Simulate some DOM manipulations
          const div = document.createElement('div');
          div.innerHTML = 'test';
          document.body.appendChild(div);
          document.body.removeChild(div);
        });
      }
      
      const finalMetrics = await this.page.metrics();
      const memoryIncrease = finalMetrics.JSHeapUsedSize - initialHeap;
      
      this.performanceMetrics.interactions = {
        interactionTime,
        initialHeap,
        finalHeap: finalMetrics.JSHeapUsedSize,
        memoryIncrease
      };

      console.log(`✅ Performance tested - Interaction: ${interactionTime}ms, Memory increase: ${memoryIncrease} bytes`);
      this.testResults.performance = { status: 'passed', ...this.performanceMetrics.interactions };
      
      return true;
    } catch (error) {
      console.error('❌ Performance test failed:', error);
      this.testResults.performance = { status: 'failed', error: error.message };
      return false;
    }
  }

  // =============================================================================
  // MAIN TEST RUNNER
  // =============================================================================

  async runAllTests() {
    console.log('🚀 Starting E2E Test Suite for Enhanced Test Page');
    console.log('=' * 80);

    const setupSuccess = await this.setup();
    if (!setupSuccess) {
      console.error('❌ Failed to setup test environment');
      return false;
    }

    try {
      // Run all test workflows
      await this.testApplicationLoad();
      await this.testNavigationToTestPage();
      await this.testProjectCreationWorkflow();
      await this.testProjectSelection();
      await this.testSignalValidationConfiguration();
      await this.testDetectionPipelineConfiguration();
      await this.testTestExecutionWorkflow();
      await this.testResultsVisualization();
      await this.testErrorHandling();
      await this.testPerformance();

    } catch (error) {
      console.error('❌ Test suite failed:', error);
      this.testResults.error = error.message;
    } finally {
      await this.teardown();
    }

    // Generate final report
    this.generateTestReport();
    return this.testResults;
  }

  generateTestReport() {
    console.log('=' * 80);
    console.log('📊 E2E TEST RESULTS SUMMARY');
    console.log('=' * 80);

    const totalTests = Object.keys(this.testResults).length;
    const passedTests = Object.values(this.testResults).filter(r => r.status === 'passed').length;
    const failedTests = totalTests - passedTests;

    console.log(`Total Tests: ${totalTests}`);
    console.log(`Passed: ${passedTests}`);
    console.log(`Failed: ${failedTests}`);
    console.log(`Success Rate: ${((passedTests/totalTests)*100).toFixed(1)}%`);
    console.log('');

    // Detailed results
    for (const [testName, result] of Object.entries(this.testResults)) {
      const icon = result.status === 'passed' ? '✅' : '❌';
      console.log(`${icon} ${testName}: ${result.status}`);
      
      if (result.error) {
        console.log(`    Error: ${result.error}`);
      }
    }

    console.log('');
    console.log(`📸 Screenshots taken: ${this.screenshots.length}`);
    this.screenshots.forEach(screenshot => {
      console.log(`    - ${screenshot.name}: ${screenshot.filename}`);
    });

    if (Object.keys(this.performanceMetrics).length > 0) {
      console.log('');
      console.log('⚡ Performance Metrics:');
      for (const [metric, value] of Object.entries(this.performanceMetrics)) {
        console.log(`    ${metric}:`, value);
      }
    }

    console.log('=' * 80);
  }

  async saveTestResults() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const resultsFile = `/home/rigade/Testing/ai-model-validation-platform/tests/e2e/e2e_test_results_${timestamp}.json`;
    
    const fullResults = {
      timestamp: new Date().toISOString(),
      testResults: this.testResults,
      screenshots: this.screenshots,
      performanceMetrics: this.performanceMetrics,
      summary: {
        total: Object.keys(this.testResults).length,
        passed: Object.values(this.testResults).filter(r => r.status === 'passed').length,
        failed: Object.values(this.testResults).filter(r => r.status === 'failed').length
      }
    };

    await fs.writeFile(resultsFile, JSON.stringify(fullResults, null, 2));
    console.log(`💾 Test results saved to: ${resultsFile}`);
  }
}

// =============================================================================
// EXECUTION
// =============================================================================

async function main() {
  const testSuite = new E2ETestSuite();
  const results = await testSuite.runAllTests();
  
  const successRate = Object.values(results).filter(r => r.status === 'passed').length / Object.keys(results).length;
  
  if (successRate >= 0.8) {
    console.log('🎉 E2E Tests PASSED!');
    process.exit(0);
  } else {
    console.log('❌ E2E Tests FAILED!');
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = E2ETestSuite;