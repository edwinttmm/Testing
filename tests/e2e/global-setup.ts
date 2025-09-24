import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function globalSetup(config: FullConfig) {
  // Create error logging directories
  const errorDir = path.join(__dirname, '../../docs/errors');
  if (!fs.existsSync(errorDir)) {
    fs.mkdirSync(errorDir, { recursive: true });
  }

  // Initialize error log files
  const timestamp = new Date().toISOString();
  const errorLogFile = path.join(errorDir, 'playwright-errors.log');
  
  fs.writeFileSync(errorLogFile, `# Playwright Error Log - Started ${timestamp}\n\n`);
  
  console.log('🚀 Global setup complete - Error monitoring initialized');
}

export default globalSetup;