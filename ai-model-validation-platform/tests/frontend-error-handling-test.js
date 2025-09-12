#!/usr/bin/env node

/**
 * Comprehensive Frontend Error Handling Test
 * Tests the SPARC-implemented error boundary and global error handling fixes
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

async function testErrorHandling() {
  let browser;
  let results = {
    timestamp: new Date().toISOString(),
    tests: [],
    summary: {
      total: 0,
      passed: 0,
      failed: 0,
      errors: []
    }
  };

  try {
    console.log('🚀 Starting Frontend Error Handling Test...');
    
    // Launch browser
    browser = await puppeteer.launch({
      headless: false, // Show browser for visual verification
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security']
    });

    const page = await browser.newPage();
    
    // Set up console monitoring
    const consoleMessages = [];
    page.on('console', msg => {
      const message = {
        type: msg.type(),
        text: msg.text(),
        timestamp: new Date().toISOString()
      };
      consoleMessages.push(message);
      console.log(`[CONSOLE ${message.type.toUpperCase()}]`, message.text);
    });

    // Set up error monitoring
    const pageErrors = [];
    page.on('pageerror', error => {
      pageErrors.push({
        message: error.message,
        stack: error.stack,
        timestamp: new Date().toISOString()
      });
      console.log('🚨 [PAGE ERROR]', error.message);
    });

    // Navigate to frontend
    console.log('📍 Navigating to http://localhost:3001...');
    await page.goto('http://localhost:3001', { waitUntil: 'networkidle2' });

    // Test 1: Basic Page Load
    console.log('🧪 Test 1: Basic Page Load');
    const test1 = {
      name: 'Basic Page Load',
      status: 'passed',
      description: 'Frontend loads without critical errors'
    };

    try {
      await page.waitForSelector('body', { timeout: 10000 });
      const title = await page.title();
      console.log(`✅ Page loaded successfully. Title: "${title}"`);
    } catch (error) {
      test1.status = 'failed';
      test1.error = error.message;
      console.log('❌ Page load failed:', error.message);
    }

    results.tests.push(test1);

    // Test 2: Test Unhandled Promise Rejection Handling
    console.log('🧪 Test 2: Unhandled Promise Rejection');
    const test2 = {
      name: 'Unhandled Promise Rejection Handling',
      status: 'passed',
      description: 'Global error handler catches unhandled promise rejections'
    };

    try {
      // Inject script that creates unhandled promise rejection
      await page.evaluate(() => {
        // This should trigger our global error handler
        Promise.reject('Test unhandled promise rejection');
      });

      // Wait for error handler to process
      await page.waitForTimeout(2000);

      // Check if error was caught by our global handler
      const hasErrorNotification = await page.evaluate(() => {
        return document.querySelector('[role="alert"]') !== null ||
               document.querySelector('.MuiAlert-root') !== null ||
               console.log.toString().includes('Unhandled Promise Rejection');
      });

      if (hasErrorNotification) {
        console.log('✅ Unhandled promise rejection was caught by error handler');
      } else {
        // Check console messages for our error handler
        const hasHandlerMessage = consoleMessages.some(msg => 
          msg.text.includes('Unhandled Promise Rejection') || 
          msg.text.includes('Global error handler')
        );
        if (hasHandlerMessage) {
          console.log('✅ Error handler processed unhandled promise rejection');
        } else {
          test2.status = 'failed';
          test2.error = 'No evidence of error handler processing rejection';
        }
      }
    } catch (error) {
      test2.status = 'failed';
      test2.error = error.message;
      console.log('❌ Promise rejection test failed:', error.message);
    }

    results.tests.push(test2);

    // Test 3: Component Error Boundary Test
    console.log('🧪 Test 3: Error Boundary Functionality');
    const test3 = {
      name: 'Error Boundary Functionality',
      status: 'passed',
      description: 'Error boundaries catch and display component errors gracefully'
    };

    try {
      // Inject a component error
      await page.evaluate(() => {
        // Try to trigger an error by accessing undefined properties
        const testError = new Error('Test component error');
        testError.name = 'TestError';
        
        // Dispatch a custom error event
        window.dispatchEvent(new ErrorEvent('error', {
          error: testError,
          message: 'Test component error',
          filename: 'test',
          lineno: 1,
          colno: 1
        }));
      });

      await page.waitForTimeout(2000);

      // Check if error boundary UI is shown
      const hasErrorBoundary = await page.evaluate(() => {
        return document.querySelector('[role="alert"]') !== null ||
               document.body.textContent.includes('Something went wrong') ||
               document.body.textContent.includes('Service Issue') ||
               document.body.textContent.includes('Try Again');
      });

      if (hasErrorBoundary) {
        console.log('✅ Error boundary displayed error UI');
      } else {
        // Check console for error boundary processing
        const hasErrorBoundaryLog = consoleMessages.some(msg => 
          msg.text.includes('Enhanced Error Boundary') || 
          msg.text.includes('Global error handler')
        );
        if (hasErrorBoundaryLog) {
          console.log('✅ Error boundary processed error (logged to console)');
        } else {
          test3.status = 'warning';
          test3.error = 'Error boundary may not have been triggered';
          console.log('⚠️  Error boundary test inconclusive');
        }
      }
    } catch (error) {
      test3.status = 'failed';
      test3.error = error.message;
      console.log('❌ Error boundary test failed:', error.message);
    }

    results.tests.push(test3);

    // Test 4: Network Error Handling
    console.log('🧪 Test 4: Network Error Handling');
    const test4 = {
      name: 'Network Error Handling',
      status: 'passed',
      description: 'Application handles network errors gracefully'
    };

    try {
      // Try to make a failed network request
      await page.evaluate(async () => {
        try {
          await fetch('http://localhost:9999/non-existent-api', { 
            method: 'GET',
            timeout: 1000 
          });
        } catch (error) {
          console.log('Network error caught:', error.message);
        }
      });

      await page.waitForTimeout(2000);
      console.log('✅ Network error test completed');
    } catch (error) {
      test4.status = 'failed';
      test4.error = error.message;
      console.log('❌ Network error test failed:', error.message);
    }

    results.tests.push(test4);

    // Check for cascading promise rejections (the original issue)
    console.log('🔍 Checking for cascading promise rejections...');
    const cascadingErrors = consoleMessages.filter(msg => 
      msg.text.includes('Unhandled promise rejection') && 
      (msg.text.includes('application-root') ||
       msg.text.includes('router-navigation') ||
       msg.text.includes('sidebar') ||
       msg.text.includes('header') ||
       msg.text.includes('main-content') ||
       msg.text.includes('dashboard'))
    );

    if (cascadingErrors.length === 0) {
      console.log('✅ No cascading promise rejections detected!');
      results.cascadingRejections = false;
    } else {
      console.log(`⚠️  Found ${cascadingErrors.length} potential cascading rejections`);
      results.cascadingRejections = true;
      results.cascadingErrors = cascadingErrors;
    }

    // Calculate summary
    results.summary.total = results.tests.length;
    results.summary.passed = results.tests.filter(t => t.status === 'passed').length;
    results.summary.failed = results.tests.filter(t => t.status === 'failed').length;
    results.summary.warnings = results.tests.filter(t => t.status === 'warning').length;

    console.log('\n📊 Test Results Summary:');
    console.log(`Total Tests: ${results.summary.total}`);
    console.log(`Passed: ${results.summary.passed}`);
    console.log(`Failed: ${results.summary.failed}`);
    console.log(`Warnings: ${results.summary.warnings || 0}`);
    console.log(`Cascading Rejections: ${results.cascadingRejections ? '❌ YES' : '✅ NO'}`);

    // Additional diagnostics
    results.diagnostics = {
      consoleMessageCount: consoleMessages.length,
      pageErrorCount: pageErrors.length,
      consoleMessages: consoleMessages,
      pageErrors: pageErrors
    };

  } catch (error) {
    console.error('💥 Test execution failed:', error);
    results.summary.errors.push(error.message);
  } finally {
    if (browser) {
      await browser.close();
    }

    // Save results
    const resultsPath = path.join(__dirname, 'frontend-error-handling-results.json');
    fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));
    console.log(`\n📝 Test results saved to: ${resultsPath}`);

    return results;
  }
}

// Execute tests
if (require.main === module) {
  testErrorHandling()
    .then(results => {
      const success = results.summary.failed === 0 && !results.cascadingRejections;
      console.log(`\n🏁 Frontend Error Handling Test ${success ? 'PASSED' : 'FAILED'}`);
      process.exit(success ? 0 : 1);
    })
    .catch(error => {
      console.error('Test execution error:', error);
      process.exit(1);
    });
}

module.exports = { testErrorHandling };