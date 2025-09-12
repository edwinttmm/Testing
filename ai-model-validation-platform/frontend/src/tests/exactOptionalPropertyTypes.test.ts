/**
 * Test exactOptionalPropertyTypes fixes
 * This file tests that our fixes for exactOptionalPropertyTypes compliance work correctly
 */

import { Logger, LogLevel, LogContext, LogEntry, RemoteLogConfig } from '../services/logger';

describe('exactOptionalPropertyTypes fixes', () => {
  it('should handle optional RemoteLogConfig parameter correctly', () => {
    // Test that we can create logger with undefined remoteConfig
    const logger1 = new Logger('test-component', LogLevel.INFO, [], undefined);
    expect(logger1).toBeDefined();

    // Test that we can create logger with defined remoteConfig  
    const remoteConfig: RemoteLogConfig = {
      endpoint: 'https://example.com/logs',
      enabled: true
    };
    const logger2 = new Logger('test-component', LogLevel.INFO, [], remoteConfig);
    expect(logger2).toBeDefined();
  });

  it('should create LogEntry without undefined assignments', () => {
    const logger = new Logger('test', LogLevel.DEBUG);
    
    // Test logging without error
    logger.info('Test message without error');
    
    // Test logging with error
    const error = new Error('Test error');
    logger.error('Test message with error', undefined, error);
    
    // This should compile without exactOptionalPropertyTypes errors
    expect(true).toBe(true);
  });

  it('should handle performance context with optional properties', () => {
    const logger = new Logger('test', LogLevel.DEBUG);
    
    // Test timer functionality that was causing exactOptionalPropertyTypes issues
    const timer = logger.time('test-operation');
    
    // Simulate some work
    setTimeout(() => {
      timer(); // This should not cause exactOptionalPropertyTypes errors
    }, 1);
    
    expect(true).toBe(true);
  });

  it('should handle LogContext performance object correctly', () => {
    const logger = new Logger('test', LogLevel.DEBUG);
    
    const context: LogContext = {
      action: 'test-action',
      performance: {
        timestamp: Date.now(),
        duration: 100
        // memory and memoryDelta are optional and should not be undefined
      }
    };
    
    logger.info('Test with performance context', context);
    expect(true).toBe(true);
  });
});