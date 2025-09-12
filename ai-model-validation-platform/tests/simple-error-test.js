#!/usr/bin/env node

/**
 * Simple Frontend Error Handling Verification
 * Tests that the frontend compiles and serves without critical errors
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

async function testFrontend() {
  const results = {
    timestamp: new Date().toISOString(),
    tests: {
      compilation: { status: 'unknown', description: 'Frontend compilation check' },
      accessibility: { status: 'unknown', description: 'Frontend HTTP accessibility' },
      eslint: { status: 'unknown', description: 'ESLint configuration validity' },
      errorBoundary: { status: 'unknown', description: 'Error boundary implementation exists' }
    },
    summary: { passed: 0, failed: 0, total: 4 }
  };

  console.log('🚀 Starting Simple Frontend Error Handling Test...\n');

  // Test 1: Compilation Check (check build logs)
  console.log('🧪 Test 1: Compilation Status');
  try {
    const buildLogPath = path.join(process.cwd(), 'frontend', 'build.log');
    if (fs.existsSync(buildLogPath)) {
      const buildLog = fs.readFileSync(buildLogPath, 'utf8');
      if (buildLog.includes('webpack compiled with') && !buildLog.includes('failed')) {
        results.tests.compilation.status = 'passed';
        console.log('✅ Frontend compilation successful');
      } else {
        results.tests.compilation.status = 'failed';
        results.tests.compilation.error = 'Build log indicates compilation issues';
        console.log('❌ Frontend compilation had issues');
      }
    } else {
      results.tests.compilation.status = 'warning';
      results.tests.compilation.error = 'Build log not found';
      console.log('⚠️  Build log not found (may not have been built yet)');
    }
  } catch (error) {
    results.tests.compilation.status = 'failed';
    results.tests.compilation.error = error.message;
  }

  // Test 2: HTTP Accessibility
  console.log('\n🧪 Test 2: HTTP Accessibility');
  try {
    const response = await checkHttpEndpoint('http://localhost:3001');
    if (response.statusCode === 200) {
      results.tests.accessibility.status = 'passed';
      console.log('✅ Frontend accessible on http://localhost:3001');
    } else {
      results.tests.accessibility.status = 'failed';
      results.tests.accessibility.error = `HTTP ${response.statusCode}`;
      console.log(`❌ Frontend returned HTTP ${response.statusCode}`);
    }
  } catch (error) {
    results.tests.accessibility.status = 'failed';
    results.tests.accessibility.error = error.message;
    console.log('❌ Frontend not accessible:', error.message);
  }

  // Test 3: ESLint Configuration
  console.log('\n🧪 Test 3: ESLint Configuration');
  try {
    const packageJsonPath = path.join(process.cwd(), 'frontend', 'package.json');
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    
    if (packageJson.devDependencies && 
        packageJson.devDependencies['@typescript-eslint/eslint-plugin'] &&
        packageJson.devDependencies['@typescript-eslint/parser'] &&
        packageJson.devDependencies['eslint']) {
      results.tests.eslint.status = 'passed';
      console.log('✅ ESLint dependencies properly configured');
    } else {
      results.tests.eslint.status = 'failed';
      results.tests.eslint.error = 'Missing ESLint TypeScript dependencies';
      console.log('❌ ESLint dependencies missing');
    }
  } catch (error) {
    results.tests.eslint.status = 'failed';
    results.tests.eslint.error = error.message;
  }

  // Test 4: Error Boundary Implementation
  console.log('\n🧪 Test 4: Error Boundary Implementation');
  try {
    const errorBoundaryPath = path.join(process.cwd(), 'frontend', 'src', 'utils', 'enhancedErrorBoundary.tsx');
    const globalErrorHandlerPath = path.join(process.cwd(), 'frontend', 'src', 'components', 'ui', 'GlobalErrorHandler.tsx');
    const appPath = path.join(process.cwd(), 'frontend', 'src', 'App.tsx');
    
    const errorBoundaryExists = fs.existsSync(errorBoundaryPath);
    const globalHandlerExists = fs.existsSync(globalErrorHandlerPath);
    const appContent = fs.readFileSync(appPath, 'utf8');
    const appIntegratesHandlers = appContent.includes('EnhancedErrorBoundary') && 
                                  appContent.includes('GlobalErrorHandler');
    
    if (errorBoundaryExists && globalHandlerExists && appIntegratesHandlers) {
      results.tests.errorBoundary.status = 'passed';
      console.log('✅ Error boundary and global error handler properly implemented');
      
      // Check for promise rejection handling
      const errorBoundaryContent = fs.readFileSync(errorBoundaryPath, 'utf8');
      if (errorBoundaryContent.includes('unhandledrejection') && 
          errorBoundaryContent.includes('handleUnhandledRejection')) {
        console.log('✅ Promise rejection handling implemented');
      } else {
        console.log('⚠️  Promise rejection handling may be limited');
      }
    } else {
      results.tests.errorBoundary.status = 'failed';
      results.tests.errorBoundary.error = 'Error handling implementation incomplete';
      console.log('❌ Error handling implementation incomplete');
    }
  } catch (error) {
    results.tests.errorBoundary.status = 'failed';
    results.tests.errorBoundary.error = error.message;
  }

  // Calculate summary
  Object.values(results.tests).forEach(test => {
    if (test.status === 'passed') results.summary.passed++;
    else if (test.status === 'failed') results.summary.failed++;
  });

  console.log('\n📊 Test Results Summary:');
  console.log(`Total Tests: ${results.summary.total}`);
  console.log(`Passed: ${results.summary.passed}`);
  console.log(`Failed: ${results.summary.failed}`);

  // Save results
  const resultsPath = path.join(__dirname, 'simple-error-test-results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));
  console.log(`\n📝 Results saved to: ${resultsPath}`);

  return results;
}

function checkHttpEndpoint(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, (response) => {
      resolve({ statusCode: response.statusCode, headers: response.headers });
    });
    
    request.on('error', (error) => {
      reject(error);
    });
    
    request.setTimeout(5000, () => {
      request.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

// Execute if run directly
if (require.main === module) {
  testFrontend()
    .then(results => {
      const success = results.summary.failed === 0;
      console.log(`\n🏁 Simple Error Test ${success ? 'PASSED' : 'FAILED'}`);
      process.exit(success ? 0 : 1);
    })
    .catch(error => {
      console.error('Test execution error:', error);
      process.exit(1);
    });
}

module.exports = { testFrontend };