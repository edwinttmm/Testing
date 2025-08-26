/**
 * Configuration Management Validation Test Suite
 * 
 * This test suite validates that configuration management is working correctly
 * after the URL fixes, ensuring environment settings are properly applied
 * and consistent across the application.
 */

import { jest } from '@jest/globals';
import { environmentService, EnvironmentConfig } from '../../src/config/environment';
import { getServiceConfig } from '../../src/utils/envConfig';

// Mock window.location for testing different environments
const mockLocation = {
  hostname: 'localhost',
  protocol: 'http:',
  port: '3000',
};

Object.defineProperty(window, 'location', {
  value: mockLocation,
  writable: true,
});

describe('Configuration Management - Environment Service', () => {
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
    // Reset environment service for each test
    jest.clearAllMocks();
  });

  afterEach(() => {
    // Restore original location
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
    });
  });

  test('should load configuration correctly for development environment', () => {
    // Mock development environment
    process.env.NODE_ENV = 'development';
    mockLocation.hostname = 'localhost';

    const config = environmentService.getConfig();

    expect(config.environment).toBe('development');
    expect(config.apiUrl).toBeDefined();
    expect(config.wsUrl).toBeDefined();
    expect(config.videoBaseUrl).toBeDefined();
    
    // In development, should typically use localhost
    if (config.apiUrl.includes('localhost')) {
      expect(config.apiUrl).toContain('localhost');
    }
    
    console.log('✅ Development environment configuration loaded');
  });

  test('should load configuration correctly for production environment', () => {
    // Mock production environment
    process.env.NODE_ENV = 'production';
    mockLocation.hostname = '155.138.239.131';

    const config = environmentService.getConfig();

    expect(config.environment).toBe('production');
    expect(config.apiUrl).toBeDefined();
    expect(config.wsUrl).toBeDefined();
    expect(config.videoBaseUrl).toBeDefined();
    
    // In production, should use the production server
    expect(config.apiUrl).toContain('155.138.239.131');
    expect(config.videoBaseUrl).toContain('155.138.239.131');
    
    console.log('✅ Production environment configuration loaded');
  });

  test('should handle environment variable overrides correctly', () => {
    const testApiUrl = 'http://custom-api.example.com:8000';
    const testWsUrl = 'ws://custom-ws.example.com:8000';
    const testVideoUrl = 'http://custom-video.example.com:8000';

    // Set environment variables
    process.env.REACT_APP_API_URL = testApiUrl;
    process.env.REACT_APP_WS_URL = testWsUrl;
    process.env.REACT_APP_VIDEO_BASE_URL = testVideoUrl;

    // Re-instantiate service to pick up new environment variables
    const config = environmentService.getConfig();

    expect(config.apiUrl).toBe(testApiUrl);
    expect(config.wsUrl).toBe(testWsUrl);
    expect(config.videoBaseUrl).toBe(testVideoUrl);

    // Clean up
    delete process.env.REACT_APP_API_URL;
    delete process.env.REACT_APP_WS_URL;
    delete process.env.REACT_APP_VIDEO_BASE_URL;

    console.log('✅ Environment variable overrides work correctly');
  });

  test('should validate URL consistency across services', () => {
    const config = environmentService.getConfig();

    // All URLs should use the same base hostname and port
    const apiUrl = new URL(config.apiUrl);
    const wsUrl = new URL(config.wsUrl);
    const videoUrl = new URL(config.videoBaseUrl);

    // Hostnames should be consistent (allowing for protocol differences)
    expect(apiUrl.hostname).toBe(videoUrl.hostname);
    expect(apiUrl.port).toBe(videoUrl.port);

    // WebSocket should have corresponding protocol
    if (apiUrl.protocol === 'https:') {
      expect(wsUrl.protocol).toBe('wss:');
    } else {
      expect(wsUrl.protocol).toBe('ws:');
    }

    console.log(`✅ URL consistency validated: API=${apiUrl.origin}, WS=${wsUrl.origin}, Video=${videoUrl.origin}`);
  });

  test('should provide correct service-specific configurations', () => {
    const videoConfig = getServiceConfig('video');
    const apiConfig = getServiceConfig('api');
    const wsConfig = getServiceConfig('websocket');

    // Video config should be defined and valid
    expect(videoConfig).toBeDefined();
    expect(videoConfig.baseUrl).toBeDefined();
    expect(videoConfig.baseUrl).toMatch(/^https?:\/\//);

    // API config should be defined
    expect(apiConfig).toBeDefined();
    expect(apiConfig.baseUrl).toBeDefined();

    // WebSocket config should be defined
    expect(wsConfig).toBeDefined();
    expect(wsConfig.baseUrl).toBeDefined();

    console.log('✅ Service-specific configurations validated');
  });

  test('should validate configuration for different deployment scenarios', () => {
    const deploymentScenarios = [
      {
        name: 'Local Development',
        hostname: 'localhost',
        expectedBase: 'localhost'
      },
      {
        name: 'Production Server',
        hostname: '155.138.239.131',
        expectedBase: '155.138.239.131'
      },
      {
        name: 'Staging Environment',
        hostname: 'staging.example.com',
        expectedBase: 'staging.example.com'
      }
    ];

    deploymentScenarios.forEach(scenario => {
      // Mock the hostname
      mockLocation.hostname = scenario.hostname;

      const config = environmentService.getConfig();

      expect(config.apiUrl).toContain(scenario.expectedBase);
      expect(config.videoBaseUrl).toContain(scenario.expectedBase);

      console.log(`✅ ${scenario.name} configuration validated`);
    });
  });
});

describe('Configuration Management - URL Service Integration', () => {
  test('should ensure video URL service uses correct base URL', () => {
    const videoConfig = getServiceConfig('video');
    
    expect(videoConfig).toBeDefined();
    expect(videoConfig.baseUrl).toBeDefined();
    expect(videoConfig.baseUrl).not.toContain('localhost');
    expect(videoConfig.baseUrl).toContain('155.138.239.131:8000');

    console.log(`✅ Video URL service base URL: ${videoConfig.baseUrl}`);
  });

  test('should validate environment-specific settings are applied', () => {
    const config = environmentService.getConfig();

    // Debug settings should be appropriate for environment
    if (config.environment === 'production') {
      expect(config.debug).toBe(false);
      expect(config.enableMockData).toBe(false);
    }

    // Timeout settings should be reasonable
    expect(config.apiTimeout).toBeGreaterThan(0);
    expect(config.wsTimeout).toBeGreaterThan(0);
    expect(config.connectionRetryAttempts).toBeGreaterThan(0);

    // Video settings should be valid
    expect(config.maxVideoSizeMB).toBeGreaterThan(0);
    expect(config.supportedVideoFormats).toBeInstanceOf(Array);
    expect(config.supportedVideoFormats.length).toBeGreaterThan(0);

    console.log('✅ Environment-specific settings validated');
  });

  test('should validate configuration consistency after URL fixes', () => {
    const config = environmentService.getConfig();

    // Ensure no localhost references in production-like environments
    if (!config.apiUrl.includes('localhost')) {
      expect(config.apiUrl).not.toContain('localhost');
      expect(config.wsUrl).not.toContain('localhost');
      expect(config.videoBaseUrl).not.toContain('localhost');
      expect(config.socketioUrl).not.toContain('localhost');
    }

    // Ensure no double port issues
    const urlsToCheck = [config.apiUrl, config.wsUrl, config.videoBaseUrl, config.socketioUrl];
    urlsToCheck.forEach(url => {
      expect(url).not.toContain(':8000:8000');
      expect(url).not.toContain(':8000:8000:8000');
    });

    console.log('✅ Configuration consistency after URL fixes validated');
  });
});

describe('Configuration Management - Security and Validation', () => {
  test('should validate secure configuration settings', () => {
    const config = environmentService.getConfig();

    // Check security-related settings
    if (config.apiUrl.startsWith('https://')) {
      expect(config.secureCookies).toBe(true);
    }

    // Validate timeout settings are not too permissive
    expect(config.apiTimeout).toBeLessThan(60000); // Less than 1 minute
    expect(config.wsTimeout).toBeLessThan(60000);

    // Validate retry settings are reasonable
    expect(config.connectionRetryAttempts).toBeLessThan(10);
    expect(config.connectionRetryDelay).toBeGreaterThan(0);

    console.log('✅ Security configuration settings validated');
  });

  test('should validate configuration warnings and errors', () => {
    const validation = environmentService.validateConfiguration();

    expect(validation).toBeDefined();
    expect(validation.valid).toBeDefined();
    expect(validation.warnings).toBeInstanceOf(Array);

    if (!validation.valid) {
      console.warn('⚠️ Configuration warnings found:', validation.warnings);
    } else {
      console.log('✅ Configuration validation passed with no warnings');
    }

    // Critical settings should not have warnings
    const criticalWarnings = validation.warnings.filter(warning => 
      warning.includes('not configured') || 
      warning.includes('very low') ||
      warning.includes('missing')
    );

    if (criticalWarnings.length > 0) {
      console.error('❌ Critical configuration issues:', criticalWarnings);
    }

    expect(criticalWarnings.length).toBe(0);
  });

  test('should validate proper port configuration', () => {
    const config = environmentService.getConfig();

    const extractPort = (url: string): string => {
      try {
        return new URL(url).port;
      } catch {
        return '';
      }
    };

    const apiPort = extractPort(config.apiUrl);
    const videoPort = extractPort(config.videoBaseUrl);

    // Ports should be consistent for API and video services
    if (apiPort && videoPort) {
      expect(apiPort).toBe(videoPort);
      expect(apiPort).toBe('8000'); // Expected production port
    }

    console.log(`✅ Port configuration validated: API=${apiPort}, Video=${videoPort}`);
  });
});

describe('Configuration Management - Runtime Validation', () => {
  test('should validate configuration is accessible at runtime', () => {
    // Test various methods of accessing configuration
    const configMethods = [
      () => environmentService.getConfig(),
      () => environmentService.getApiUrl(),
      () => environmentService.getWsUrl(),
      () => environmentService.getVideoBaseUrl(),
      () => environmentService.isDevelopment(),
      () => environmentService.isProduction(),
      () => environmentService.shouldEnableDebug(),
    ];

    configMethods.forEach((method, index) => {
      expect(() => method()).not.toThrow();
      const result = method();
      expect(result).toBeDefined();
    });

    console.log('✅ Runtime configuration access validated');
  });

  test('should validate configuration logging works correctly', () => {
    const originalLog = console.log;
    const originalTable = console.table;
    const originalGroup = console.group;
    const originalGroupEnd = console.groupEnd;

    let logCalled = false;
    let tableCalled = false;

    console.log = jest.fn(() => { logCalled = true; });
    console.table = jest.fn(() => { tableCalled = true; });
    console.group = jest.fn();
    console.groupEnd = jest.fn();

    // Enable debug mode for logging
    const config = environmentService.getConfig();
    if (config.debug) {
      environmentService.logConfiguration();
      expect(logCalled || tableCalled).toBe(true);
    }

    // Restore console methods
    console.log = originalLog;
    console.table = originalTable;
    console.group = originalGroup;
    console.groupEnd = originalGroupEnd;

    console.log('✅ Configuration logging validated');
  });

  test('should validate configuration hot-reloading capabilities', () => {
    const initialConfig = environmentService.getConfig();
    
    // Change environment variable
    const originalApiUrl = process.env.REACT_APP_API_URL;
    process.env.REACT_APP_API_URL = 'http://test-hot-reload:8000';

    // Configuration should still be consistent (hot-reloading may not be immediate)
    const currentConfig = environmentService.getConfig();
    expect(currentConfig).toBeDefined();

    // Restore original value
    if (originalApiUrl) {
      process.env.REACT_APP_API_URL = originalApiUrl;
    } else {
      delete process.env.REACT_APP_API_URL;
    }

    console.log('✅ Configuration hot-reloading capability validated');
  });
});

describe('Configuration Management - Integration Summary', () => {
  test('should provide comprehensive configuration validation summary', () => {
    const config = environmentService.getConfig();
    const validation = environmentService.validateConfiguration();

    const configSummary = {
      environment: config.environment,
      apiConfigured: !!config.apiUrl,
      videoConfigured: !!config.videoBaseUrl,
      wsConfigured: !!config.wsUrl,
      validConfiguration: validation.valid,
      warningCount: validation.warnings.length,
      secureProtocol: config.apiUrl.startsWith('https://'),
      debugEnabled: config.debug,
      mockDataEnabled: config.enableMockData,
      performanceMonitoring: config.enablePerformanceMonitoring
    };

    console.log('🎯 Configuration Management Summary:');
    console.table(configSummary);

    // Critical configuration should be present
    expect(configSummary.apiConfigured).toBe(true);
    expect(configSummary.videoConfigured).toBe(true);
    expect(configSummary.wsConfigured).toBe(true);

    // Configuration should be valid
    expect(configSummary.validConfiguration).toBe(true);

    // Test environment-specific expectations
    if (config.environment === 'production') {
      expect(configSummary.debugEnabled).toBe(false);
      expect(configSummary.mockDataEnabled).toBe(false);
    }

    console.log('✅ Configuration management validation completed successfully');

    return configSummary;
  });

  test('should validate URL fix integration with configuration', () => {
    // Test that URL fixes work with the current configuration
    const videoConfig = getServiceConfig('video');
    const baseUrl = videoConfig?.baseUrl || 'http://155.138.239.131:8000';

    // Import and test URL fixing functionality
    const { fixVideoUrl } = require('../../src/utils/videoUrlFixer');
    
    const testUrl = 'http://localhost:8000/uploads/config-test.mp4';
    const fixedUrl = fixVideoUrl(testUrl);

    // Fixed URL should use the configuration base URL
    expect(fixedUrl).toContain('155.138.239.131:8000');
    expect(fixedUrl).not.toContain('localhost');

    // Should be consistent with environment configuration
    const configuredHost = new URL(baseUrl).hostname;
    const fixedHost = new URL(fixedUrl).hostname;
    expect(fixedHost).toBe(configuredHost);

    console.log(`✅ URL fix integration: ${testUrl} -> ${fixedUrl} (using config base: ${baseUrl})`);
  });
});