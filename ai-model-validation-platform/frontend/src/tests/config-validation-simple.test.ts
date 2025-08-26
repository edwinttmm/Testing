/**
 * Simple Configuration Validation Test
 * Validates that configuration loading works without React components
 */

import { configurationManager, getConfigValueSync, isConfigInitialized } from '../utils/configurationManager';
import { appConfig, getApiUrl, getWebSocketUrl } from '../config/appConfig';
import { environmentService } from '../config/environment';

// Set up runtime config in jsdom environment
const mockRuntimeConfig = {
  REACT_APP_API_URL: 'http://155.138.239.131:8000',
  REACT_APP_WS_URL: 'ws://155.138.239.131:8000',
  REACT_APP_SOCKETIO_URL: 'http://155.138.239.131:8001',
  REACT_APP_VIDEO_BASE_URL: 'http://155.138.239.131:8000',
  REACT_APP_ENVIRONMENT: 'production'
};

// Mock window.RUNTIME_CONFIG
Object.defineProperty(window, 'RUNTIME_CONFIG', {
  value: mockRuntimeConfig,
  writable: true
});

describe('Configuration Validation Tests', () => {
  beforeAll(async () => {
    // Wait for configuration to initialize
    await configurationManager.waitForInitialization();
  });

  beforeEach(() => {
    // Ensure runtime config is available
    (window as any).RUNTIME_CONFIG = mockRuntimeConfig;
  });

  describe('Configuration Manager', () => {
    it('should initialize successfully', () => {
      expect(isConfigInitialized()).toBe(true);
    });

    it('should load runtime configuration with correct URLs', async () => {
      const apiUrl = await configurationManager.getConfigValue('REACT_APP_API_URL', '');
      const wsUrl = await configurationManager.getConfigValue('REACT_APP_WS_URL', '');
      const socketioUrl = await configurationManager.getConfigValue('REACT_APP_SOCKETIO_URL', '');

      expect(apiUrl).toBe('http://155.138.239.131:8000');
      expect(wsUrl).toBe('ws://155.138.239.131:8000');
      expect(socketioUrl).toBe('http://155.138.239.131:8001');
    });

    it('should provide synchronous configuration access after initialization', () => {
      const apiUrl = getConfigValueSync('REACT_APP_API_URL', '');
      const wsUrl = getConfigValueSync('REACT_APP_WS_URL', '');

      expect(apiUrl).toBe('http://155.138.239.131:8000');
      expect(wsUrl).toBe('ws://155.138.239.131:8000');
    });
  });

  describe('App Configuration', () => {
    it('should provide correct API configuration', () => {
      expect(appConfig.api.baseUrl).toContain('155.138.239.131');
      expect(appConfig.websocket.url).toContain('155.138.239.131');
    });

    it('should generate correct API URLs', () => {
      const baseUrl = getApiUrl();
      const endpointUrl = getApiUrl('/api/test');

      expect(baseUrl).toBe('http://155.138.239.131:8000');
      expect(endpointUrl).toBe('http://155.138.239.131:8000/api/test');
    });

    it('should generate correct WebSocket URLs', () => {
      const baseWsUrl = getWebSocketUrl();
      const endpointWsUrl = getWebSocketUrl('/ws/test');

      expect(baseWsUrl).toContain('155.138.239.131');
      expect(endpointWsUrl).toContain('155.138.239.131');
    });
  });

  describe('Environment Service', () => {
    it('should provide configuration without throwing errors', () => {
      expect(() => environmentService.getConfig()).not.toThrow();
      expect(() => environmentService.getApiUrl()).not.toThrow();
      expect(() => environmentService.getWsUrl()).not.toThrow();
    });

    it('should validate configuration successfully', () => {
      const validation = environmentService.validateConfiguration();
      expect(validation.valid).toBe(true);
      expect(validation.warnings).toEqual([]);
    });

    it('should provide URLs with correct IP address', () => {
      const apiUrl = environmentService.getApiUrl();
      const wsUrl = environmentService.getWsUrl();

      expect(apiUrl).toContain('155.138.239.131');
      expect(wsUrl).toContain('155.138.239.131');
    });
  });

  describe('Function Availability Tests', () => {
    it('should have isConfigInitialized function available', () => {
      expect(typeof isConfigInitialized).toBe('function');
      expect(() => isConfigInitialized()).not.toThrow();
    });

    it('should have getConfigValueSync function available', () => {
      expect(typeof getConfigValueSync).toBe('function');
      expect(() => getConfigValueSync('REACT_APP_API_URL', '')).not.toThrow();
    });

    it('should have configuration functions return expected types', () => {
      const apiUrl = getApiUrl();
      const wsUrl = getWebSocketUrl();

      expect(typeof apiUrl).toBe('string');
      expect(typeof wsUrl).toBe('string');
      expect(apiUrl.length).toBeGreaterThan(0);
      expect(wsUrl.length).toBeGreaterThan(0);
    });
  });

  describe('Error Handling', () => {
    it('should handle missing configuration keys gracefully', () => {
      const fallbackValue = 'test-fallback';
      const result = getConfigValueSync('NON_EXISTENT_KEY' as any, fallbackValue);
      
      expect(result).toBe(fallbackValue);
    });

    it('should provide fallback URLs when needed', () => {
      const apiUrl = getApiUrl();
      const wsUrl = getWebSocketUrl();

      // Should always provide a valid URL, either configured or fallback
      expect(apiUrl).toMatch(/^https?:\/\/.+/);
      expect(wsUrl).toMatch(/^wss?:\/\/.+/);
    });
  });

  describe('Runtime Configuration Override', () => {
    it('should use window.RUNTIME_CONFIG when available', () => {
      expect((window as any).RUNTIME_CONFIG).toBeDefined();
      expect((window as any).RUNTIME_CONFIG.REACT_APP_API_URL).toBe('http://155.138.239.131:8000');
    });

    it('should prioritize runtime config over environment variables', async () => {
      // Set a different env var
      const originalEnv = process.env.REACT_APP_API_URL;
      process.env.REACT_APP_API_URL = 'http://different-url.com';

      try {
        // Runtime config should still win
        const apiUrl = await configurationManager.getConfigValue('REACT_APP_API_URL', '');
        expect(apiUrl).toBe('http://155.138.239.131:8000');
      } finally {
        // Restore original env
        if (originalEnv !== undefined) {
          process.env.REACT_APP_API_URL = originalEnv;
        } else {
          delete process.env.REACT_APP_API_URL;
        }
      }
    });
  });
});