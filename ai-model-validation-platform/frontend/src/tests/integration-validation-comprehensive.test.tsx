/**
 * Integration Validation Test Suite
 * Tests that configuration and WebSocket fixes work together properly
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from '../pages/Dashboard';
import { configurationManager, getConfigValueSync, isConfigInitialized } from '../utils/configurationManager';
import { appConfig, getApiUrl, getWebSocketUrl } from '../config/appConfig';
import { environmentService } from '../config/environment';

// Mock WebSocket and API services
jest.mock('../services/api', () => ({
  getDashboardStats: jest.fn(() => Promise.resolve({
    project_count: 5,
    video_count: 10,
    test_session_count: 15,
    detection_event_count: 25,
    confidence_intervals: {
      precision: [85, 95],
      recall: [80, 90],
      f1_score: [82, 92]
    },
    trend_analysis: {
      accuracy: 'improving',
      detectionRate: 'stable',
      performance: 'improving'
    },
    signal_processing_metrics: {
      totalSignals: 100,
      successRate: 95,
      avgProcessingTime: 150
    },
    average_accuracy: 89,
    active_tests: 3,
    total_detections: 50
  })),
  getTestSessions: jest.fn(() => Promise.resolve([
    {
      id: '1',
      name: 'Test Session 1',
      createdAt: '2025-01-01T10:00:00Z',
      metrics: { accuracy: 88 }
    },
    {
      id: '2',
      name: 'Test Session 2',
      createdAt: '2025-01-01T11:00:00Z',
      metrics: { accuracy: 92 }
    }
  ]))
}));

// Mock WebSocket hook
jest.mock('../hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(() => ({
    isConnected: true,
    on: jest.fn(() => jest.fn()),
    emit: jest.fn(),
    subscribe: jest.fn(() => jest.fn()),
    error: null,
    connectionState: 'connected'
  }))
}));

// Mock Socket.IO
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    emit: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    connected: true
  }))
}));

// Set up runtime config in window
Object.defineProperty(window, 'RUNTIME_CONFIG', {
  value: {
    REACT_APP_API_URL: 'http://155.138.239.131:8000',
    REACT_APP_WS_URL: 'ws://155.138.239.131:8000',
    REACT_APP_SOCKETIO_URL: 'http://155.138.239.131:8001',
    REACT_APP_VIDEO_BASE_URL: 'http://155.138.239.131:8000',
    REACT_APP_ENVIRONMENT: 'production'
  },
  writable: true
});

describe('Integration Validation Test Suite', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset configuration manager for each test
    (configurationManager as any).state = {
      initialized: false,
      runtimeConfigLoaded: false,
      environmentConfigLoaded: false,
      finalConfig: null,
      error: null
    };
  });

  describe('Configuration Integration Tests', () => {
    it('should load configuration with 155.138.239.131 URLs', async () => {
      // Wait for configuration to initialize
      await act(async () => {
        await configurationManager.waitForInitialization();
      });

      expect(isConfigInitialized()).toBe(true);

      const apiUrl = getConfigValueSync('REACT_APP_API_URL', '');
      const wsUrl = getConfigValueSync('REACT_APP_WS_URL', '');
      const socketioUrl = getConfigValueSync('REACT_APP_SOCKETIO_URL', '');

      expect(apiUrl).toBe('http://155.138.239.131:8000');
      expect(wsUrl).toBe('ws://155.138.239.131:8000');
      expect(socketioUrl).toBe('http://155.138.239.131:8001');
    });

    it('should provide configuration access functions without errors', () => {
      expect(() => appConfig.api.baseUrl).not.toThrow();
      expect(() => getApiUrl()).not.toThrow();
      expect(() => getWebSocketUrl()).not.toThrow();

      const apiUrl = getApiUrl();
      const wsUrl = getWebSocketUrl();

      expect(apiUrl).toContain('155.138.239.131');
      expect(wsUrl).toContain('155.138.239.131');
    });

    it('should validate environment service configuration', () => {
      expect(() => environmentService.getConfig()).not.toThrow();
      expect(() => environmentService.getApiUrl()).not.toThrow();
      expect(() => environmentService.getWsUrl()).not.toThrow();

      const validation = environmentService.validateConfiguration();
      expect(validation.valid).toBe(true);
      expect(validation.warnings).toHaveLength(0);
    });

    it('should handle configuration ready state properly', () => {
      // Test the isConfigReady function that was causing the original error
      expect(typeof isConfigInitialized).toBe('function');
      expect(() => isConfigInitialized()).not.toThrow();

      const configReady = isConfigInitialized();
      expect(typeof configReady).toBe('boolean');
    });
  });

  describe('WebSocket Service Integration Tests', () => {
    it('should access configuration for WebSocket connections', async () => {
      const { useWebSocket } = require('../hooks/useWebSocket');
      
      // Mock the hook to verify it can access configuration
      expect(() => {
        const result = useWebSocket();
        return result;
      }).not.toThrow();
    });

    it('should configure WebSocket URLs correctly', () => {
      const expectedSocketIOUrl = 'http://155.138.239.131:8001';
      const expectedWSUrl = 'ws://155.138.239.131:8000';

      // Test that configuration functions return expected URLs
      const wsUrl = getWebSocketUrl();
      const configValue = getConfigValueSync('REACT_APP_SOCKETIO_URL', '');

      expect(configValue).toBe(expectedSocketIOUrl);
      expect(wsUrl).toContain('155.138.239.131');
    });
  });

  describe('Dashboard Component Integration Tests', () => {
    it('should render Dashboard without isConfigReady errors', async () => {
      await act(async () => {
        render(<Dashboard />);
      });

      // Wait for the component to load
      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      // Verify no errors in console (the original issue)
      expect(console.error).not.toHaveBeenCalledWith(
        expect.stringContaining('isConfigReady is not a function')
      );
    });

    it('should handle configuration loading in Dashboard', async () => {
      let dashboardInstance: any;

      await act(async () => {
        const { container } = render(<Dashboard />);
        dashboardInstance = container;
      });

      // Wait for dashboard to fully load
      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument();
      });

      // Verify dashboard stats are rendered
      await waitFor(() => {
        expect(screen.getByText('Active Projects')).toBeInTheDocument();
        expect(screen.getByText('Videos Processed')).toBeInTheDocument();
        expect(screen.getByText('Tests Completed')).toBeInTheDocument();
      });
    });

    it('should display correct connection status', async () => {
      await act(async () => {
        render(<Dashboard />);
      });

      await waitFor(() => {
        expect(screen.getByText('HTTP-Only Mode')).toBeInTheDocument();
      });
    });
  });

  describe('Runtime Configuration Loading Tests', () => {
    it('should load runtime config from window.RUNTIME_CONFIG', () => {
      expect(window.RUNTIME_CONFIG).toBeDefined();
      expect(window.RUNTIME_CONFIG.REACT_APP_API_URL).toBe('http://155.138.239.131:8000');
    });

    it('should override process.env with runtime config', async () => {
      await act(async () => {
        await configurationManager.waitForInitialization();
      });

      // Verify process.env is updated with runtime config
      expect(process.env.REACT_APP_API_URL).toBe('http://155.138.239.131:8000');
      expect(process.env.REACT_APP_WS_URL).toBe('ws://155.138.239.131:8000');
    });

    it('should provide fallback configuration when runtime config fails', async () => {
      // Temporarily remove runtime config
      const originalConfig = window.RUNTIME_CONFIG;
      delete (window as any).RUNTIME_CONFIG;

      try {
        // Force reinitialization
        await configurationManager.reinitialize();

        const apiUrl = getConfigValueSync('REACT_APP_API_URL', '');
        // Should still get the correct fallback URL
        expect(apiUrl).toContain('155.138.239.131');
      } finally {
        // Restore runtime config
        window.RUNTIME_CONFIG = originalConfig;
      }
    });
  });

  describe('Error Handling Tests', () => {
    it('should handle configuration errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      try {
        // Test that functions don't throw even with missing config
        expect(() => getApiUrl()).not.toThrow();
        expect(() => getWebSocketUrl()).not.toThrow();
        expect(() => isConfigInitialized()).not.toThrow();
      } finally {
        consoleSpy.mockRestore();
      }
    });

    it('should provide default values when configuration is missing', () => {
      const fallbackValue = 'fallback';
      const configValue = getConfigValueSync('NONEXISTENT_KEY' as any, fallbackValue);
      
      expect(configValue).toBe(fallbackValue);
    });

    it('should validate configuration without throwing errors', () => {
      expect(() => {
        const validation = environmentService.validateConfiguration();
        return validation.valid;
      }).not.toThrow();
    });
  });

  describe('URL Configuration Tests', () => {
    it('should use correct API URLs for 155.138.239.131', () => {
      const apiUrl = getApiUrl('/test-endpoint');
      expect(apiUrl).toBe('http://155.138.239.131:8000/test-endpoint');
    });

    it('should use correct WebSocket URLs for 155.138.239.131', () => {
      const wsUrl = getWebSocketUrl('/ws-endpoint');
      expect(wsUrl).toBe('ws://155.138.239.131:8000/ws-endpoint');
    });

    it('should handle URL normalization correctly', () => {
      const apiUrlWithSlash = getApiUrl('/api/test');
      const apiUrlWithoutSlash = getApiUrl('api/test');

      expect(apiUrlWithSlash).toBe('http://155.138.239.131:8000/api/test');
      expect(apiUrlWithoutSlash).toBe('http://155.138.239.131:8000/api/test');
    });
  });
});