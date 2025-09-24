import { Page, ConsoleMessage } from '@playwright/test';
import fs from 'fs';
import path from 'path';

export interface ErrorCapture {
  timestamp: string;
  type: 'console' | 'typescript' | 'react' | 'network' | 'performance';
  level: 'error' | 'warning' | 'info';
  message: string;
  stack?: string;
  url?: string;
  lineNumber?: number;
  columnNumber?: number;
  source?: string;
}

export class ErrorMonitor {
  private errors: ErrorCapture[] = [];
  private testName: string;
  
  constructor(testName: string) {
    this.testName = testName;
  }
  
  async setupPageMonitoring(page: Page): Promise<void> {
    // Console error monitoring
    page.on('console', (msg: ConsoleMessage) => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        this.captureError({
          timestamp: new Date().toISOString(),
          type: 'console',
          level: msg.type() as 'error' | 'warning',
          message: msg.text(),
          source: 'browser-console'
        });
      }
    });
    
    // JavaScript errors
    page.on('pageerror', (error) => {
      this.captureError({
        timestamp: new Date().toISOString(),
        type: 'react',
        level: 'error',
        message: error.message,
        stack: error.stack,
        source: 'javascript-runtime'
      });
    });
    
    // Network errors
    page.on('response', (response) => {
      if (response.status() >= 400) {
        this.captureError({
          timestamp: new Date().toISOString(),
          type: 'network',
          level: response.status() >= 500 ? 'error' : 'warning',
          message: `HTTP ${response.status()} - ${response.url()}`,
          url: response.url(),
          source: 'network-request'
        });
      }
    });
    
    // Request failures
    page.on('requestfailed', (request) => {
      this.captureError({
        timestamp: new Date().toISOString(),
        type: 'network',
        level: 'error',
        message: `Request failed: ${request.url()} - ${request.failure()?.errorText}`,
        url: request.url(),
        source: 'network-failure'
      });
    });
  }
  
  captureError(error: ErrorCapture): void {
    this.errors.push(error);
    console.error(`[${this.testName}] ${error.type.toUpperCase()}: ${error.message}`);
  }
  
  async captureTypeScriptErrors(page: Page): Promise<void> {
    // Check for TypeScript compilation errors in the browser
    const tsErrors = await page.evaluate(() => {
      const errors: any[] = [];
      
      // Check for React DevTools errors
      if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
        const hook = window.__REACT_DEVTOOLS_GLOBAL_HOOK__;
        if (hook.renderers) {
          hook.renderers.forEach((renderer: any) => {
            if (renderer._currentFiber && renderer._currentFiber.errors) {
              renderer._currentFiber.errors.forEach((error: any) => {
                errors.push({
                  type: 'react',
                  message: error.message || 'React component error',
                  stack: error.stack
                });
              });
            }
          });
        }
      }
      
      // Check for TypeScript errors in the console
      const logs = (window as any).__TEST_LOGS__ || [];
      logs.forEach((log: any) => {
        if (log.level === 'error' && log.message.includes('TS')) {
          errors.push({
            type: 'typescript',
            message: log.message,
            source: 'typescript-compiler'
          });
        }
      });
      
      return errors;
    });
    
    tsErrors.forEach(error => {
      this.captureError({
        timestamp: new Date().toISOString(),
        type: error.type,
        level: 'error',
        message: error.message,
        stack: error.stack,
        source: error.source || 'typescript-detection'
      });
    });
  }
  
  async capturePerformanceIssues(page: Page): Promise<void> {
    const metrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      const memory = (performance as any).memory;
      
      return {
        loadTime: navigation.loadEventEnd - navigation.loadEventStart,
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        memoryUsed: memory ? memory.usedJSHeapSize : 0,
        memoryLimit: memory ? memory.jsHeapSizeLimit : 0
      };
    });
    
    // Flag performance issues
    if (metrics.loadTime > 5000) {
      this.captureError({
        timestamp: new Date().toISOString(),
        type: 'performance',
        level: 'warning',
        message: `Slow page load: ${metrics.loadTime}ms`,
        source: 'performance-monitor'
      });
    }
    
    if (metrics.memoryUsed > metrics.memoryLimit * 0.8) {
      this.captureError({
        timestamp: new Date().toISOString(),
        type: 'performance',
        level: 'error',
        message: `High memory usage: ${(metrics.memoryUsed / 1024 / 1024).toFixed(2)}MB`,
        source: 'performance-monitor'
      });
    }
  }
  
  getErrors(): ErrorCapture[] {
    return [...this.errors];
  }
  
  getErrorsByType(type: ErrorCapture['type']): ErrorCapture[] {
    return this.errors.filter(error => error.type === type);
  }
  
  hasErrors(): boolean {
    return this.errors.length > 0;
  }
  
  hasCriticalErrors(): boolean {
    return this.errors.some(error => error.level === 'error');
  }
  
  async saveErrorLog(): Promise<void> {
    const logPath = `test-reports/error-logs/${this.testName.replace(/\s+/g, '-')}-errors.json`;
    const errorData = {
      testName: this.testName,
      timestamp: new Date().toISOString(),
      totalErrors: this.errors.length,
      criticalErrors: this.errors.filter(e => e.level === 'error').length,
      warnings: this.errors.filter(e => e.level === 'warning').length,
      errorsByType: {
        console: this.getErrorsByType('console').length,
        typescript: this.getErrorsByType('typescript').length,
        react: this.getErrorsByType('react').length,
        network: this.getErrorsByType('network').length,
        performance: this.getErrorsByType('performance').length
      },
      errors: this.errors
    };
    
    fs.writeFileSync(logPath, JSON.stringify(errorData, null, 2));
  }
}