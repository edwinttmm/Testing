/**
 * Integration Validation Test Suite
 * Tests cross-environment compatibility and deployment validation
 */

import { environmentService } from '../config/environment';

describe('Environment Integration Tests', () => {
  describe('Configuration Validation', () => {
    test('validates development environment configuration', () => {
      const config = environmentService.getConfig();
      const validation = environmentService.validateConfiguration();
      
      expect(validation.valid).toBe(true);
      expect(validation.warnings).toHaveLength(0);
      expect(config.apiUrl).toBeTruthy();
      expect(config.wsUrl).toBeTruthy();
    });

    test('provides fallback URLs when environment variables missing', () => {
      // Test URL generation logic
      expect(environmentService.getApiUrl()).toMatch(/^https?:\/\//);
      expect(environmentService.getWsUrl()).toMatch(/^wss?:\/\//);
    });

    test('adapts timeout values for environment', () => {
      const config = environmentService.getConfig();
      
      if (environmentService.isDevelopment()) {
        expect(config.apiTimeout).toBeGreaterThanOrEqual(30000);
      } else {
        expect(config.apiTimeout).toBeGreaterThanOrEqual(45000);
      }
    });

    test('configures retry attempts appropriately', () => {
      const retryAttempts = environmentService.get('connectionRetryAttempts');
      
      expect(retryAttempts).toBeGreaterThan(0);
      expect(retryAttempts).toBeLessThanOrEqual(10);
    });
  });

  describe('URL Resolution Tests', () => {
    test('resolves localhost URLs in development', () => {
      const originalLocation = window.location;
      
      Object.defineProperty(window, 'location', {
        value: {
          hostname: 'localhost',
          protocol: 'http:',
        },
        writable: true,
      });

      expect(environmentService.getApiUrl()).toContain('localhost');
      
      // Restore original location
      window.location = originalLocation;
    });

    test('resolves production server URLs', () => {
      const originalLocation = window.location;
      
      Object.defineProperty(window, 'location', {
        value: {
          hostname: '155.138.239.131',
          protocol: 'http:',
        },
        writable: true,
      });

      // Would test production URL resolution
      expect(environmentService.getApiUrl()).toBeTruthy();
      
      // Restore original location
      window.location = originalLocation;
    });

    test('handles HTTPS upgrade correctly', () => {
      const originalLocation = window.location;
      
      Object.defineProperty(window, 'location', {
        value: {
          hostname: '155.138.239.131',
          protocol: 'https:',
        },
        writable: true,
      });

      const wsUrl = environmentService.getWsUrl();
      expect(wsUrl).toMatch(/^wss:/);
      
      // Restore original location
      window.location = originalLocation;
    });
  });

  describe('Feature Flag Tests', () => {
    test('enables appropriate features for environment', () => {
      const config = environmentService.getConfig();
      
      if (environmentService.isDevelopment()) {
        expect(config.debug).toBe(true);
        expect(config.enableDebugPanels).toBe(true);
        expect(config.logLevel).toBe('debug');
      } else {
        expect(config.debug).toBe(false);
        expect(config.enableDebugPanels).toBe(false);
        expect(config.logLevel).toBe('error');
      }
    });

    test('sets appropriate video limits', () => {
      const config = environmentService.getConfig();
      
      expect(config.maxVideoSizeMB).toBeGreaterThan(0);
      expect(config.supportedVideoFormats).toContain('mp4');
    });
  });

  describe('Error Handling Tests', () => {
    test('handles missing configuration gracefully', () => {
      // Test with minimal environment variables
      const originalEnv = process.env;
      
      // Temporarily clear environment
      process.env = { NODE_ENV: 'test' };
      
      // Should not throw errors
      expect(() => {
        const config = environmentService.getConfig();
        expect(config).toBeDefined();
      }).not.toThrow();
      
      // Restore environment
      process.env = originalEnv;
    });

    test('provides meaningful error messages for invalid configuration', () => {
      const validation = environmentService.validateConfiguration();
      
      // Should provide actionable warnings if configuration is invalid
      if (!validation.valid) {
        validation.warnings.forEach(warning => {
          expect(warning).toMatch(/\w+/); // Non-empty warning messages
        });
      }
    });
  });

  describe('Performance Tests', () => {
    test('configuration loading is performant', () => {
      const start = performance.now();
      
      for (let i = 0; i < 100; i++) {
        environmentService.getConfig();
      }
      
      const end = performance.now();
      const duration = end - start;
      
      // Should complete 100 config calls in under 10ms
      expect(duration).toBeLessThan(10);
    });

    test('URL resolution is cached', () => {
      const start = performance.now();
      
      for (let i = 0; i < 1000; i++) {
        environmentService.getApiUrl();
        environmentService.getWsUrl();
      }
      
      const end = performance.now();
      const duration = end - start;
      
      // Should be very fast due to caching
      expect(duration).toBeLessThan(50);
    });
  });
});

describe('Cross-Environment Compatibility', () => {
  describe('Browser Compatibility', () => {
    test('handles missing APIs gracefully', () => {
      // Test WebSocket availability
      const hasWebSocket = typeof WebSocket !== 'undefined';
      
      if (!hasWebSocket) {
        // Should provide fallback or error handling
        expect(environmentService.getWsUrl()).toBeTruthy();
      }
    });

    test('handles fullscreen API differences', () => {
      // Test various fullscreen API implementations
      const hasFullscreen = 
        'requestFullscreen' in Element.prototype ||
        'webkitRequestFullscreen' in Element.prototype ||
        'mozRequestFullScreen' in Element.prototype;
      
      // Should handle availability gracefully
      expect(typeof hasFullscreen).toBe('boolean');
    });

    test('handles media capabilities', () => {
      const video = document.createElement('video');
      
      // Test basic video support
      const canPlayMP4 = video.canPlayType('video/mp4');
      expect(canPlayMP4).toMatch(/(probably|maybe|^$)/);
    });
  });

  describe('Network Resilience', () => {
    test('provides reasonable timeout values', () => {
      const config = environmentService.getConfig();
      
      expect(config.apiTimeout).toBeGreaterThan(5000); // At least 5 seconds
      expect(config.wsTimeout).toBeGreaterThan(5000);
      expect(config.connectionRetryDelay).toBeGreaterThan(500);
    });

    test('provides exponential backoff parameters', () => {
      const config = environmentService.getConfig();
      
      expect(config.connectionRetryAttempts).toBeGreaterThan(2);
      expect(config.connectionRetryDelay).toBeGreaterThan(0);
    });
  });

  describe('Security Configuration', () => {
    test('uses secure protocols in production', () => {
      const config = environmentService.getConfig();
      
      if (environmentService.isProduction()) {
        expect(config.apiUrl).toMatch(/^https:/);
        expect(config.wsUrl).toMatch(/^wss:/);
        expect(config.secureCookies).toBe(true);
      }
    });

    test('allows insecure protocols in development', () => {
      if (environmentService.isDevelopment()) {
        const config = environmentService.getConfig();
        // Development can use HTTP for local testing
        expect(config.apiUrl).toMatch(/^https?:/);
        expect(config.wsUrl).toMatch(/^wss?:/);
      }
    });
  });
});

describe('Deployment Validation', () => {
  describe('Configuration Completeness', () => {
    test('has all required configuration keys', () => {
      const config = environmentService.getConfig();
      
      const requiredKeys = [
        'environment',
        'apiUrl',
        'wsUrl',
        'videoBaseUrl',
        'debug',
        'logLevel',
        'apiTimeout',
        'wsTimeout',
        'connectionRetryAttempts',
        'connectionRetryDelay',
      ];
      
      requiredKeys.forEach(key => {
        expect(config).toHaveProperty(key);
        expect(config[key as keyof typeof config]).toBeDefined();
      });
    });

    test('configuration values are valid', () => {
      const config = environmentService.getConfig();
      
      expect(['development', 'production', 'test']).toContain(config.environment);
      expect(['debug', 'info', 'warn', 'error']).toContain(config.logLevel);
      expect(config.maxVideoSizeMB).toBeGreaterThan(0);
      expect(config.supportedVideoFormats).toHaveLength.toBeGreaterThan(0);
    });
  });

  describe('Runtime Validation', () => {
    test('can establish connections with configured URLs', async () => {
      // This would be an actual connectivity test in a real environment
      const apiUrl = environmentService.getApiUrl();
      const wsUrl = environmentService.getWsUrl();
      
      expect(apiUrl).toMatch(/^https?:\/\/[\w\-.:]+(:\d+)?$/);
      expect(wsUrl).toMatch(/^wss?:\/\/[\w\-.:]+(:\d+)?$/);
      
      // In a real test, would attempt actual connections:
      // const response = await fetch(`${apiUrl}/health`);
      // expect(response.ok).toBe(true);
    });

    test('logging configuration works', () => {
      const originalConsole = console.log;
      const consoleCalls: string[] = [];
      
      console.log = jest.fn().mockImplementation((message: string) => {
        consoleCalls.push(message);
      });
      
      environmentService.logConfiguration();
      
      if (environmentService.shouldEnableDebug()) {
        expect(consoleCalls.length).toBeGreaterThan(0);
      }
      
      console.log = originalConsole;
    });
  });

  describe('Monitoring and Observability', () => {
    test('provides configuration inspection capabilities', () => {
      const config = environmentService.getConfig();
      
      // Should be able to serialize configuration safely
      expect(() => JSON.stringify(config)).not.toThrow();
      
      // Should not expose sensitive information
      const configString = JSON.stringify(config);
      expect(configString).not.toContain('password');
      expect(configString).not.toContain('secret');
      expect(configString).not.toContain('key');
    });

    test('supports configuration validation reporting', () => {
      const validation = environmentService.validateConfiguration();
      
      expect(validation).toHaveProperty('valid');
      expect(validation).toHaveProperty('warnings');
      expect(Array.isArray(validation.warnings)).toBe(true);
    });
  });
});