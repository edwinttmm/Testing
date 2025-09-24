/**
 * ADAS Camera HIL Testing Platform - Global Playwright Teardown
 * @fileoverview Global teardown for Playwright test environment
 */

async function globalTeardown(config) {
  console.log('🔄 Starting ADAS HIL Testing Platform Global Teardown');

  try {
    // Cleanup test data
    if (process.env.TEST_PROJECT_ID) {
      console.log('🧹 Cleaning up test project:', process.env.TEST_PROJECT_ID);
      // Could add cleanup API calls here if needed
    }

    // Cleanup temporary files
    const fs = require('fs');
    const path = require('path');
    
    const tempPaths = [
      './tests/playwright/fixtures/auth-state.json',
      './docs/errors/videos/',
      './docs/errors/screenshots/'
    ];

    for (const tempPath of tempPaths) {
      try {
        if (fs.existsSync(tempPath)) {
          if (fs.statSync(tempPath).isDirectory()) {
            // Keep directory structure, just clean files
            const files = fs.readdirSync(tempPath);
            for (const file of files) {
              if (file.endsWith('.webm') || file.endsWith('.png')) {
                fs.unlinkSync(path.join(tempPath, file));
              }
            }
          } else {
            fs.unlinkSync(tempPath);
          }
        }
      } catch (cleanupError) {
        console.log('⚠️ Cleanup warning for:', tempPath, cleanupError.message);
      }
    }

    console.log('✅ Global teardown completed successfully');
  } catch (error) {
    console.error('❌ Global teardown failed:', error);
  }
}

module.exports = globalTeardown;