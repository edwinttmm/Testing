import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function globalTeardown(config: FullConfig) {
  const timestamp = new Date().toISOString();
  const errorLogFile = path.join(__dirname, '../../docs/errors/playwright-errors.log');
  
  if (fs.existsSync(errorLogFile)) {
    fs.appendFileSync(errorLogFile, `\n# Test run completed: ${timestamp}\n`);
  }
  
  console.log('🏁 Global teardown complete - Error logs saved');
}

export default globalTeardown;