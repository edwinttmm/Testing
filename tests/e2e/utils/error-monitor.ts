import { Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';

export class ErrorMonitor {
  private errors: Array<{
    timestamp: string;
    type: string;
    message: string;
    url?: string;
    stack?: string;
  }> = [];

  private networkFailures: Array<{
    timestamp: string;
    url: string;
    method: string;
    errorText: string;
  }> = [];

  constructor(private page: Page) {
    this.setupMonitoring();
  }

  private setupMonitoring() {
    // Monitor console errors and warnings
    this.page.on('console', (msg) => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        const error = {
          timestamp: new Date().toISOString(),
          type: msg.type(),
          message: msg.text(),
          stack: msg.location() ? `${msg.location().url}:${msg.location().lineNumber}` : undefined,
        };
        
        this.errors.push(error);
        console.log(`🔴 Console ${error.type}: ${error.message}`);
        
        if (error.stack) {
          console.log(`   at ${error.stack}`);
        }
      }
    });

    // Monitor network failures
    this.page.on('requestfailed', (request) => {
      const failure = {
        timestamp: new Date().toISOString(),
        url: request.url(),
        method: request.method(),
        errorText: request.failure()?.errorText || 'Unknown error',
      };
      
      this.networkFailures.push(failure);
      console.log(`🌐 Network failure: ${failure.method} ${failure.url} - ${failure.errorText}`);
    });

    // Monitor page crashes
    this.page.on('crash', () => {
      console.log('💥 PAGE CRASHED!');
      this.errors.push({
        timestamp: new Date().toISOString(),
        type: 'crash',
        message: 'Page crashed',
      });
    });

    // Monitor JavaScript errors
    this.page.on('pageerror', (error) => {
      const pageError = {
        timestamp: new Date().toISOString(),
        type: 'pageerror',
        message: error.message,
        stack: error.stack,
      };
      
      this.errors.push(pageError);
      console.log(`🔥 Page error: ${pageError.message}`);
      if (pageError.stack) {
        console.log(`   Stack: ${pageError.stack}`);
      }
    });
  }

  getErrors() {
    return this.errors;
  }

  getNetworkFailures() {
    return this.networkFailures;
  }

  async saveErrorLog(testName: string) {
    const errorDir = path.join(__dirname, '../../../docs/errors');
    if (!fs.existsSync(errorDir)) {
      fs.mkdirSync(errorDir, { recursive: true });
    }

    const logFile = path.join(errorDir, `${testName.replace(/[^a-zA-Z0-9]/g, '_')}_errors.log`);
    
    const logContent = [
      `# Error Log for Test: ${testName}`,
      `# Generated: ${new Date().toISOString()}`,
      '',
      '## Console Errors/Warnings:',
      ...this.errors.map(e => `[${e.timestamp}] ${e.type.toUpperCase()}: ${e.message}${e.stack ? ` (${e.stack})` : ''}`),
      '',
      '## Network Failures:',
      ...this.networkFailures.map(f => `[${f.timestamp}] ${f.method} ${f.url}: ${f.errorText}`),
      '',
    ].join('\n');

    fs.writeFileSync(logFile, logContent);
    console.log(`📝 Error log saved: ${logFile}`);
  }

  hasErrors(): boolean {
    return this.errors.length > 0 || this.networkFailures.length > 0;
  }

  clearErrors() {
    this.errors = [];
    this.networkFailures = [];
  }
}