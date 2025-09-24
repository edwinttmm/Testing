import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function globalTeardown(config: FullConfig) {
  console.log('🧹 Starting global test teardown...');
  
  // Compile final error report
  const finalLog = {
    teardown_time: new Date().toISOString(),
    test_session_complete: true,
    report_location: 'docs/errors/'
  };
  
  fs.writeFileSync('test-reports/error-logs/session-end.json', JSON.stringify(finalLog, null, 2));
  
  console.log('✅ Global teardown completed');
}

export default globalTeardown;