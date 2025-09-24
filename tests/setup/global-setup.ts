import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting global test setup...');
  
  // Create necessary directories
  const testDirs = [
    'test-reports',
    'test-reports/screenshots',
    'test-reports/videos',
    'test-reports/error-logs',
    'docs/errors'
  ];
  
  testDirs.forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
      console.log(`Created directory: ${dir}`);
    }
  });
  
  // Initialize error tracking
  const errorLog = {
    setup_time: new Date().toISOString(),
    console_errors: [],
    typescript_errors: [],
    react_errors: [],
    network_errors: [],
    performance_issues: []
  };
  
  fs.writeFileSync('test-reports/error-logs/session-start.json', JSON.stringify(errorLog, null, 2));
  
  console.log('✅ Global setup completed');
}

export default globalSetup;