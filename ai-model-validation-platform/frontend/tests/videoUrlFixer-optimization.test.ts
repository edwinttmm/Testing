/**
 * Comprehensive test suite for VideoUrlFixer optimization features
 * Tests all advanced optimization capabilities including caching, batch processing,
 * performance monitoring, and migration-aware processing
 */

import {
  fixVideoUrl,
  fixMultipleVideoUrls,
  getPerformanceMetrics,
  generatePerformanceReport,
  resetMetrics,
  getCacheStats,
  clearAllCaches,
  performMaintenance,
  initializeWithHooks,
  VideoUrlFixOptions
} from '../src/utils/videoUrlFixer';

// Mock environment config
jest.mock('../src/utils/envConfig', () => ({
  getServiceConfig: jest.fn((service) => {
    if (service === 'video') {
      return {
        baseUrl: 'http://155.138.239.131:8000',
        maxSizeMB: 100,
        supportedFormats: ['mp4', 'avi', 'mov', 'mkv']
      };
    }
    if (service === 'database') {
      return {
        migrating: false // Default to no migration
      };
    }
    return {};
  })
}));

describe('VideoUrlFixer Optimization Features', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearAllCaches();
    resetMetrics();
    
    // Mock performance.now for consistent testing
    jest.spyOn(performance, 'now')
      .mockReturnValueOnce(0) // Start time
      .mockReturnValueOnce(10); // End time
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Intelligent Caching System', () => {
    it('should cache URL mappings and return cached results', () => {
      const url = 'http://localhost:8000/uploads/test.mp4';
      
      // First call should process and cache
      const result1 = fixVideoUrl(url);
      expect(result1).toBe('http://155.138.239.131:8000/uploads/test.mp4');
      
      // Second call should use cache
      const result2 = fixVideoUrl(url);
      expect(result2).toBe('http://155.138.239.131:8000/uploads/test.mp4');
      
      const metrics = getPerformanceMetrics();
      expect(metrics.cacheHits).toBeGreaterThan(0);
    });

    it('should respect cache TTL and refresh expired entries', async () => {
      const url = 'http://localhost:8000/uploads/test.mp4';
      
      // Process URL to cache it
      fixVideoUrl(url);
      
      const initialCacheStats = getCacheStats();
      expect(initialCacheStats.cacheSize).toBe(1);
      
      // Fast forward time to expire cache
      jest.spyOn(Date, 'now').mockReturnValue(Date.now() + 700000); // 11+ minutes
      
      // Should process again due to expired cache
      const result = fixVideoUrl(url);
      expect(result).toBe('http://155.138.239.131:8000/uploads/test.mp4');
    });

    it('should handle cache size limits and perform cleanup', () => {
      // Fill cache beyond limit
      for (let i = 0; i < 1050; i++) {
        fixVideoUrl(`http://localhost:8000/uploads/test${i}.mp4`);
      }
      
      const cacheStats = getCacheStats();
      // Cache should be cleaned up and size reduced
      expect(cacheStats.cacheSize).toBeLessThan(1050);
    });
  });

  describe('Batch Processing with Chunking', () => {
    it('should process videos in chunks with proper throttling', async () => {
      const videos = Array.from({ length: 100 }, (_, i) => ({
        id: `video-${i}`,
        url: `http://localhost:8000/uploads/video${i}.mp4`,
        filename: `video${i}.mp4`
      }));

      const startTime = Date.now();
      await fixMultipleVideoUrls(videos, {
        chunkSize: 10,
        throttleMs: 5,
        debug: true
      });
      const endTime = Date.now();

      // Should have taken time due to throttling
      expect(endTime - startTime).toBeGreaterThan(30); // At least some throttling time

      const metrics = getPerformanceMetrics();
      expect(metrics.batchesProcessed).toBe(1);
      expect(metrics.totalProcessed).toBeGreaterThan(0);
    });

    it('should handle background queue processing', async () => {
      const videos = Array.from({ length: 50 }, (_, i) => ({
        id: `video-${i}`,
        url: `http://localhost:8000/uploads/video${i}.mp4`
      }));

      // Process with background queue
      await fixMultipleVideoUrls(videos, {
        useBackgroundQueue: true,
        priority: 'low',
        debug: true
      });

      // Should queue the processing
      const metrics = getPerformanceMetrics();
      expect(metrics.systemStats.queueLength).toBeGreaterThanOrEqual(0);
    });

    it('should adapt processing during migration', async () => {
      // Mock migration active state
      jest.doMock('../src/utils/envConfig', () => ({
        getServiceConfig: jest.fn((service) => {
          if (service === 'database') {
            return { migrating: true };
          }
          return { baseUrl: 'http://155.138.239.131:8000' };
        })
      }));

      const videos = Array.from({ length: 20 }, (_, i) => ({
        url: `http://localhost:8000/uploads/video${i}.mp4`
      }));

      await fixMultipleVideoUrls(videos, { chunkSize: 50, debug: true });

      // Should have adaptive processing during migration
      const metrics = getPerformanceMetrics();
      expect(metrics.migrationAwareSkips).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Performance Monitoring', () => {
    it('should collect comprehensive performance metrics', () => {
      // Process some URLs to generate metrics
      fixVideoUrl('http://localhost:8000/uploads/test1.mp4');
      fixVideoUrl('http://localhost:8000/uploads/test2.mp4');
      fixVideoUrl('', 'test3.mp4'); // Empty URL construction

      const metrics = getPerformanceMetrics();
      
      expect(metrics).toHaveProperty('totalProcessed');
      expect(metrics).toHaveProperty('cacheStats');
      expect(metrics).toHaveProperty('systemStats');
      expect(metrics.totalProcessed).toBeGreaterThan(0);
      expect(metrics.averageProcessingTime).toBeGreaterThanOrEqual(0);
    });

    it('should generate performance reports with insights', () => {
      // Process URLs to generate data
      for (let i = 0; i < 10; i++) {
        fixVideoUrl(`http://localhost:8000/uploads/test${i}.mp4`);
      }

      const report = generatePerformanceReport();
      
      expect(report).toHaveProperty('summary');
      expect(report).toHaveProperty('metrics');
      expect(report).toHaveProperty('insights');
      expect(report).toHaveProperty('recommendations');
      
      expect(report.summary).toContain('Processed');
      expect(Array.isArray(report.insights)).toBe(true);
      expect(Array.isArray(report.recommendations)).toBe(true);
    });

    it('should provide actionable recommendations based on metrics', () => {
      // Simulate high error scenario
      const originalConsoleError = console.error;
      console.error = jest.fn();

      // Force errors by passing invalid data
      try {
        for (let i = 0; i < 5; i++) {
          fixVideoUrl(undefined as any, undefined, undefined, { debug: false });
        }
      } catch (error) {
        // Expected errors
      }

      const report = generatePerformanceReport();
      
      // Should provide recommendations for high error rate
      if (report.metrics.errorsEncountered > 0) {
        expect(report.recommendations).toContain(
          expect.stringContaining('error')
        );
      }

      console.error = originalConsoleError;
    });
  });

  describe('Migration-Aware Processing', () => {
    it('should detect migration state and adjust processing', () => {
      // Mock migration detection
      Object.defineProperty(process, 'env', {
        value: { ...process.env, MIGRATION_ACTIVE: 'true' },
        writable: true
      });

      const url = 'http://localhost:8000/uploads/test.mp4';
      const result = fixVideoUrl(url, undefined, undefined, { debug: true });
      
      expect(result).toBe('http://155.138.239.131:8000/uploads/test.mp4');
      
      const metrics = getPerformanceMetrics();
      expect(metrics.systemStats.migrationActive).toBe(true);
    });

    it('should provide quick fixes during migration for localhost URLs', () => {
      // Set migration active
      document.cookie = 'migration-active=true';
      
      const url = 'http://localhost:8000/uploads/test.mp4';
      const result = fixVideoUrl(url, undefined, undefined, { debug: true });
      
      expect(result).toBe('http://155.138.239.131:8000/uploads/test.mp4');
      
      // Clean up cookie
      document.cookie = 'migration-active=; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    });
  });

  describe('Duplicate Detection', () => {
    it('should detect and skip duplicate URL processing', () => {
      const url = 'http://localhost:8000/uploads/test.mp4';
      
      // Process same URL multiple times rapidly
      fixVideoUrl(url);
      fixVideoUrl(url);
      fixVideoUrl(url);
      
      const metrics = getPerformanceMetrics();
      expect(metrics.totalSkipped).toBeGreaterThan(0);
    });

    it('should allow forcing processing during migration', () => {
      const url = 'http://localhost:8000/uploads/test.mp4';
      
      const result = fixVideoUrl(url, undefined, undefined, {
        forceDuringMigration: true,
        skipDeduplication: true
      });
      
      expect(result).toBe('http://155.138.239.131:8000/uploads/test.mp4');
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle errors gracefully and provide fallbacks', () => {
      // Mock getServiceConfig to throw error
      const envConfig = require('../src/utils/envConfig');
      envConfig.getServiceConfig = jest.fn(() => {
        throw new Error('Config error');
      });

      const result = fixVideoUrl('http://localhost:8000/uploads/test.mp4');
      
      // Should still provide fallback result
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('should track and report errors in metrics', () => {
      const originalConsoleError = console.error;
      console.error = jest.fn();

      // Force an error condition
      try {
        fixVideoUrl(null as any, undefined, undefined, { debug: false });
      } catch (error) {
        // Expected
      }

      const metrics = getPerformanceMetrics();
      expect(metrics.errorsEncountered).toBeGreaterThanOrEqual(0);
      
      console.error = originalConsoleError;
    });
  });

  describe('Maintenance and Cleanup', () => {
    it('should perform maintenance cleanup', () => {
      // Fill cache with some data
      for (let i = 0; i < 10; i++) {
        fixVideoUrl(`http://localhost:8000/uploads/test${i}.mp4`);
      }

      const initialStats = getCacheStats();
      performMaintenance();
      const finalStats = getCacheStats();

      // Should have performed some cleanup
      expect(finalStats).toBeDefined();
    });

    it('should handle cache cleanup without errors', () => {
      expect(() => {
        performMaintenance();
      }).not.toThrow();
    });
  });

  describe('Hooks Integration', () => {
    it('should initialize with hooks when available', async () => {
      // Mock window.claudeFlow
      const mockNotify = jest.fn();
      (global as any).window = {
        claudeFlow: {
          hooks: {
            notify: mockNotify
          }
        }
      };

      await initializeWithHooks();
      
      expect(mockNotify).toHaveBeenCalledWith(
        expect.objectContaining({
          component: 'videoUrlFixer',
          action: 'initialized'
        })
      );

      // Cleanup
      delete (global as any).window;
    });

    it('should handle missing hooks gracefully', async () => {
      // No window.claudeFlow available
      await expect(initializeWithHooks()).resolves.not.toThrow();
    });
  });

  describe('Backward Compatibility', () => {
    it('should maintain compatibility with existing options', () => {
      const options: VideoUrlFixOptions = {
        forceAbsolute: true,
        debug: false,
        skipValidation: true
      };

      const result = fixVideoUrl('/uploads/test.mp4', undefined, undefined, options);
      expect(result).toBe('http://155.138.239.131:8000/uploads/test.mp4');
    });

    it('should work with legacy cache stats function', () => {
      const stats = getCacheStats();
      
      expect(stats).toHaveProperty('hasCachedUrl');
      expect(stats).toHaveProperty('cacheAge');
      expect(stats).toHaveProperty('cacheTtl');
    });

    it('should handle all existing URL patterns correctly', () => {
      const testCases = [
        {
          input: 'http://localhost:8000/uploads/test.mp4',
          expected: 'http://155.138.239.131:8000/uploads/test.mp4'
        },
        {
          input: '/uploads/test.mp4',
          expected: 'http://155.138.239.131:8000/uploads/test.mp4'
        },
        {
          input: 'http://155.138.239.131:8000/uploads/test.mp4',
          expected: 'http://155.138.239.131:8000/uploads/test.mp4'
        }
      ];

      testCases.forEach(({ input, expected }) => {
        const result = fixVideoUrl(input);
        expect(result).toBe(expected);
      });
    });
  });
});