/**
 * Browser Compatibility Test for Environment Configuration
 * 
 * This test ensures that envConfig.ts works correctly in browser environments
 * without throwing "process is not defined" errors.
 */

import { envConfig, getConfig, isValidConfig } from '../utils/envConfig';

describe('Environment Configuration - Browser Compatibility', () => {
  beforeEach(() => {
    // Clear any cached configuration
    envConfig.reload();
  });

  test('should load configuration without errors', () => {
    expect(() => {
      const config = getConfig();
      expect(config).toBeDefined();
    }).not.toThrow();
  });

  test('should have valid environment configuration', () => {
    const config = getConfig();
    
    // Environment should be one of the valid values
    expect(['development', 'production', 'test']).toContain(config.environment);
    
    // Boolean flags should be properly set
    expect(typeof config.isDevelopment).toBe('boolean');
    expect(typeof config.isProduction).toBe('boolean');
    expect(typeof config.isTest).toBe('boolean');
    
    // URLs should be strings
    expect(typeof config.apiUrl).toBe('string');
    expect(typeof config.wsUrl).toBe('string');
    expect(typeof config.socketioUrl).toBe('string');
    expect(typeof config.videoBaseUrl).toBe('string');
  });

  test('should have valid URL configurations', () => {
    const config = getConfig();
    
    // URLs should be valid
    expect(config.apiUrl).toMatch(/^https?:\/\//);
    expect(config.wsUrl).toMatch(/^wss?:\/\//);
    expect(config.socketioUrl).toMatch(/^https?:\/\//);
    expect(config.videoBaseUrl).toMatch(/^https?:\/\//);
  });

  test('should have proper numeric configurations', () => {
    const config = getConfig();
    
    // Timeouts should be positive numbers
    expect(config.apiTimeout).toBeGreaterThan(0);
    expect(config.wsTimeout).toBeGreaterThan(0);
    expect(config.connectionRetryAttempts).toBeGreaterThan(0);
    expect(config.connectionRetryDelay).toBeGreaterThan(0);
    expect(config.maxVideoSizeMB).toBeGreaterThan(0);
  });

  test('should have supported video formats array', () => {
    const config = getConfig();
    
    expect(Array.isArray(config.supportedVideoFormats)).toBe(true);
    expect(config.supportedVideoFormats.length).toBeGreaterThan(0);
  });

  test('should validate configuration successfully', () => {
    expect(isValidConfig()).toBe(true);
  });

  test('should provide service configurations', () => {
    expect(() => {
      envConfig.getServiceConfig('api');
      envConfig.getServiceConfig('websocket');
      envConfig.getServiceConfig('socketio');
      envConfig.getServiceConfig('video');
    }).not.toThrow();
  });

  test('should handle environment detection correctly', () => {
    const config = getConfig();
    
    // Environment flags should be mutually exclusive
    const envFlags = [config.isDevelopment, config.isProduction, config.isTest];
    const trueCount = envFlags.filter(flag => flag).length;
    expect(trueCount).toBe(1);
  });

  test('should work in simulated browser environment', () => {
    // Simulate browser environment by checking window object existence
    const isBrowser = typeof window !== 'undefined';
    
    expect(() => {
      const config = getConfig();
      
      if (isBrowser) {
        // In browser, URLs should use current hostname for defaults
        expect(config.apiUrl).toBeDefined();
        expect(config.wsUrl).toBeDefined();
        expect(config.socketioUrl).toBeDefined();
      }
    }).not.toThrow();
  });
});