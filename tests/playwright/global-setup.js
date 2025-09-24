/**
 * ADAS Camera HIL Testing Platform - Global Playwright Setup
 * @fileoverview Global setup for Playwright test environment
 */

const { chromium } = require('@playwright/test');

async function globalSetup(config) {
  console.log('🚀 Starting ADAS HIL Testing Platform Global Setup');

  // Create browser for authentication
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Check if frontend is available
    console.log('🔍 Checking frontend availability at http://localhost:3000');
    await page.goto('http://localhost:3000', { timeout: 30000 });
    console.log('✅ Frontend is available');

    // Check if backend is available
    console.log('🔍 Checking backend API at http://localhost:8000');
    const response = await page.request.get('http://localhost:8000/health');
    if (response.ok()) {
      console.log('✅ Backend API is available');
    } else {
      console.log('⚠️ Backend API may not be fully ready');
    }

    // Setup test data and authentication if needed
    await setupTestData(page);

    // Store authentication state
    await context.storageState({ path: './tests/playwright/fixtures/auth-state.json' });
    console.log('✅ Authentication state stored');

  } catch (error) {
    console.error('❌ Global setup failed:', error);
    throw error;
  } finally {
    await browser.close();
  }

  console.log('✅ Global setup completed successfully');
}

async function setupTestData(page) {
  console.log('🔧 Setting up test data...');
  
  try {
    // Create test project if needed
    const createProjectResponse = await page.request.post('http://localhost:8000/api/projects', {
      data: {
        name: 'Playwright Test Project',
        description: 'Automated test project for Playwright E2E tests',
        camera_type: 'front-facing-vru',
        test_scenarios: ['scenario_1', 'scenario_2']
      },
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (createProjectResponse.ok()) {
      const project = await createProjectResponse.json();
      console.log('✅ Test project created:', project.id);
      
      // Store project ID for tests
      process.env.TEST_PROJECT_ID = project.id;
    }
  } catch (error) {
    console.log('⚠️ Test data setup had issues:', error.message);
  }
}

module.exports = globalSetup;