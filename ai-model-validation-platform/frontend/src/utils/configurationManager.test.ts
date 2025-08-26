/**
 * ConfigurationManager Test Suite
 * Tests the runtime configuration override precedence system
 */

import { configurationManager, getConfigValueSync, isConfigInitialized } from './configurationManager';

// Mock window object for testing
const mockWindow = global.window as any;

describe('ConfigurationManager', () => {
  beforeEach(() => {
    // Clear any existing configuration
    if (mockWindow) {
      delete mockWindow.RUNTIME_CONFIG;
    }
    
    // Reset environment variables
    delete process.env.REACT_APP_API_URL;
    delete process.env.REACT_APP_WS_URL;
    delete process.env.REACT_APP_SOCKETIO_URL;
    delete process.env.REACT_APP_VIDEO_BASE_URL;
  });

  test('should use default configuration when no overrides are present', async () => {
    await configurationManager.reinitialize();
    
    const config = configurationManager.getFullConfigSync();
    expect(config.REACT_APP_API_URL).toBe('http://155.138.239.131:8000');
    expect(config.REACT_APP_WS_URL).toBe('ws://155.138.239.131:8000');
    expect(config.REACT_APP_SOCKETIO_URL).toBe('http://155.138.239.131:8001');
    expect(config.REACT_APP_VIDEO_BASE_URL).toBe('http://155.138.239.131:8000');
  });

  test('should override with environment variables', async () => {
    process.env.REACT_APP_API_URL = 'http://env-api:9000';
    process.env.REACT_APP_WS_URL = 'ws://env-ws:9000';
    
    await configurationManager.reinitialize();
    
    const config = configurationManager.getFullConfigSync();
    expect(config.REACT_APP_API_URL).toBe('http://env-api:9000');
    expect(config.REACT_APP_WS_URL).toBe('ws://env-ws:9000');
    // Should still use defaults for others
    expect(config.REACT_APP_SOCKETIO_URL).toBe('http://155.138.239.131:8001');
  });

  test('should prioritize runtime config over environment variables', async () => {
    // Set environment variables
    process.env.REACT_APP_API_URL = 'http://env-api:9000';
    process.env.REACT_APP_WS_URL = 'ws://env-ws:9000';
    
    // Set runtime config
    if (mockWindow) {
      mockWindow.RUNTIME_CONFIG = {
        REACT_APP_API_URL: 'http://runtime-api:7000',
        REACT_APP_WS_URL: 'ws://runtime-ws:7000',
        REACT_APP_SOCKETIO_URL: 'http://runtime-socketio:7001',
        REACT_APP_VIDEO_BASE_URL: 'http://runtime-video:7000'
      };
    }
    
    await configurationManager.reinitialize();
    
    const config = configurationManager.getFullConfigSync();
    expect(config.REACT_APP_API_URL).toBe('http://runtime-api:7000');
    expect(config.REACT_APP_WS_URL).toBe('ws://runtime-ws:7000');
    expect(config.REACT_APP_SOCKETIO_URL).toBe('http://runtime-socketio:7001');
    expect(config.REACT_APP_VIDEO_BASE_URL).toBe('http://runtime-video:7000');
  });

  test('should provide correct precedence: runtime > env > default', async () => {
    // Only set runtime config for API URL
    if (mockWindow) {
      mockWindow.RUNTIME_CONFIG = {
        REACT_APP_API_URL: 'http://runtime-api:7000'
      };
    }
    
    // Set env config for WS URL
    process.env.REACT_APP_WS_URL = 'ws://env-ws:9000';
    
    await configurationManager.reinitialize();
    
    const config = configurationManager.getFullConfigSync();
    expect(config.REACT_APP_API_URL).toBe('http://runtime-api:7000'); // Runtime wins
    expect(config.REACT_APP_WS_URL).toBe('ws://env-ws:9000'); // Env wins over default
    expect(config.REACT_APP_SOCKETIO_URL).toBe('http://155.138.239.131:8001'); // Default
    expect(config.REACT_APP_VIDEO_BASE_URL).toBe('http://155.138.239.131:8000'); // Default
  });

  test('should handle getConfigValueSync correctly', async () => {
    if (mockWindow) {
      mockWindow.RUNTIME_CONFIG = {
        REACT_APP_API_URL: 'http://runtime-api:7000'
      };
    }
    
    await configurationManager.reinitialize();
    
    const apiUrl = getConfigValueSync('REACT_APP_API_URL', 'fallback');
    expect(apiUrl).toBe('http://runtime-api:7000');
    
    const wsUrl = getConfigValueSync('REACT_APP_WS_URL', 'fallback-ws');
    expect(wsUrl).toBe('ws://155.138.239.131:8000'); // Default, not fallback
  });

  test('should indicate initialization status correctly', async () => {
    expect(isConfigInitialized()).toBe(true); // Should be initialized from previous tests
    
    await configurationManager.reinitialize();
    expect(isConfigInitialized()).toBe(true);
  });

  test('should handle missing window object gracefully', async () => {
    // This simulates server-side rendering
    const originalWindow = global.window;
    delete (global as any).window;
    
    try {
      await configurationManager.reinitialize();
      const config = configurationManager.getFullConfigSync();
      expect(config.REACT_APP_API_URL).toBe('http://155.138.239.131:8000');
    } finally {
      (global as any).window = originalWindow;
    }
  });

  test('should execute onReady callbacks correctly', (done) => {
    configurationManager.onReady(() => {
      expect(isConfigInitialized()).toBe(true);
      done();
    });
  });

  test('should handle configuration errors gracefully', async () => {
    // This test would need to simulate an error condition
    // For now, just ensure the system doesn't crash
    const state = configurationManager.getState();
    expect(state).toHaveProperty('initialized');
    expect(state).toHaveProperty('runtimeConfigLoaded');
    expect(state).toHaveProperty('environmentConfigLoaded');
    expect(state).toHaveProperty('finalConfig');
    expect(state).toHaveProperty('error');
  });
});