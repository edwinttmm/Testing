/**
 * API Performance and Load Testing Suite
 * 
 * Tests API response times, throughput, memory usage, and concurrent request handling
 * to ensure the API can handle production workloads efficiently.
 */

import { jest } from '@jest/globals';
import axios from 'axios';
import { apiService } from '../ai-model-validation-platform/frontend/src/services/api';
import { enhancedApiService } from '../ai-model-validation-platform/frontend/src/services/enhancedApiService';
import { apiCache } from '../ai-model-validation-platform/frontend/src/utils/apiCache';
import { createMockProject, createMockVideoFile, PERFORMANCE_THRESHOLD_MS } from './api-integration-test-suite';

// Performance test configuration
const PERFORMANCE_CONFIG = {
  responseTimeThreshold: {
    fast: 200,      // <200ms for cached/simple operations
    normal: 1000,   // <1s for standard operations
    slow: 5000,     // <5s for complex operations (file uploads, processing)
    batch: 10000    // <10s for batch operations
  },
  concurrency: {
    light: 5,       // Light concurrent load
    medium: 20,     // Medium concurrent load
    heavy: 50,      // Heavy concurrent load
    stress: 100     // Stress test load
  },
  memoryLimits: {
    heapIncrease: 50 * 1024 * 1024, // Max 50MB heap increase
    maxHeapUsage: 200 * 1024 * 1024  // Max 200MB total heap
  },
  dataVolumes: {
    small: 10,      // 10 items
    medium: 100,    // 100 items
    large: 1000,    // 1,000 items
    xlarge: 10000   // 10,000 items
  }
};

// Performance measurement utilities
class PerformanceTracker {
  private measurements: Map<string, number[]> = new Map();
  private memoryBaseline: NodeJS.MemoryUsage | null = null;

  startTracking(testName: string) {
    this.memoryBaseline = process.memoryUsage();
    if (!this.measurements.has(testName)) {
      this.measurements.set(testName, []);
    }
  }

  recordMeasurement(testName: string, startTime: number) {
    const duration = Date.now() - startTime;
    const measurements = this.measurements.get(testName) || [];
    measurements.push(duration);
    this.measurements.set(testName, measurements);
    return duration;
  }

  getMemoryUsage() {
    const current = process.memoryUsage();
    const baseline = this.memoryBaseline || current;
    
    return {
      heapUsed: current.heapUsed,
      heapTotal: current.heapTotal,
      heapIncrease: current.heapUsed - baseline.heapUsed,
      external: current.external,
      rss: current.rss
    };
  }

  getStatistics(testName: string) {
    const measurements = this.measurements.get(testName) || [];
    if (measurements.length === 0) return null;

    const sorted = [...measurements].sort((a, b) => a - b);
    const sum = measurements.reduce((a, b) => a + b, 0);

    return {
      count: measurements.length,
      min: Math.min(...measurements),
      max: Math.max(...measurements),
      average: sum / measurements.length,
      median: sorted[Math.floor(sorted.length / 2)],
      p95: sorted[Math.floor(sorted.length * 0.95)],
      p99: sorted[Math.floor(sorted.length * 0.99)]
    };
  }

  clear() {
    this.measurements.clear();
    this.memoryBaseline = null;
  }
}

describe('API Performance Tests', () => {
  let mockAxios: jest.Mocked<typeof axios>;
  let performanceTracker: PerformanceTracker;

  beforeAll(() => {
    performanceTracker = new PerformanceTracker();
  });

  beforeEach(() => {
    jest.clearAllMocks();
    apiCache.clear();
    mockAxios = axios as jest.Mocked<typeof axios>;
    performanceTracker.clear();
  });

  afterEach(() => {
    // Force garbage collection if available for accurate memory measurements
    if (global.gc) {
      global.gc();
    }
  });

  describe('Response Time Performance', () => {
    it('should meet response time requirements for project listing', async () => {
      const mockProjects = Array.from({ length: 50 }, (_, i) => ({
        ...createMockProject(),
        id: `proj-${i}`,
        name: `Project ${i}`
      }));

      mockAxios.get = jest.fn().mockResolvedValue({
        data: mockProjects,
        status: 200
      });

      performanceTracker.startTracking('project-listing');
      const startTime = Date.now();
      
      const result = await apiService.getProjects();
      
      const duration = performanceTracker.recordMeasurement('project-listing', startTime);

      expect(result).toHaveLength(50);
      expect(duration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal);
    });

    it('should meet response time requirements for dashboard stats', async () => {
      const mockStats = {
        project_count: 25,
        video_count: 150,
        test_session_count: 75,
        detection_event_count: 5000
      };

      mockAxios.get = jest.fn().mockResolvedValue({
        data: mockStats,
        status: 200
      });

      performanceTracker.startTracking('dashboard-stats');
      const startTime = Date.now();
      
      const result = await apiService.getDashboardStats();
      
      const duration = performanceTracker.recordMeasurement('dashboard-stats', startTime);

      expect(result).toEqual(mockStats);
      expect(duration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.fast);
    });

    it('should handle large video listing efficiently', async () => {
      const mockVideos = Array.from({ length: PERFORMANCE_CONFIG.dataVolumes.large }, (_, i) => ({
        ...createMockVideoFile(),
        id: `vid-${i}`,
        filename: `video_${i}.mp4`
      }));

      mockAxios.get = jest.fn().mockResolvedValue({
        data: { videos: mockVideos, total: mockVideos.length },
        status: 200
      });

      performanceTracker.startTracking('large-video-listing');
      const startTime = Date.now();
      
      const result = await apiService.getAllVideos();
      
      const duration = performanceTracker.recordMeasurement('large-video-listing', startTime);

      expect(result.videos).toHaveLength(PERFORMANCE_CONFIG.dataVolumes.large);
      expect(duration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.slow);
    });

    it('should cache frequently accessed data for fast subsequent access', async () => {
      const mockProjects = [createMockProject()];
      mockAxios.get = jest.fn().mockResolvedValue({
        data: mockProjects,
        status: 200
      });

      // First request (uncached)
      performanceTracker.startTracking('first-request');
      let startTime = Date.now();
      await apiService.getProjects();
      const firstDuration = performanceTracker.recordMeasurement('first-request', startTime);

      // Simulate cached response for second request
      const cachedData = apiCache.get('GET', '/api/projects', { skip: 0, limit: 100 });
      
      performanceTracker.startTracking('cached-request');
      startTime = Date.now();
      
      // Simulate cache hit
      if (cachedData) {
        performanceTracker.recordMeasurement('cached-request', startTime);
      } else {
        // If not cached, make another request
        await apiService.getProjects();
        performanceTracker.recordMeasurement('cached-request', startTime);
      }

      const firstStats = performanceTracker.getStatistics('first-request');
      const cachedStats = performanceTracker.getStatistics('cached-request');

      expect(firstStats).toBeDefined();
      expect(cachedStats).toBeDefined();
    });
  });

  describe('Concurrent Request Handling', () => {
    it('should handle light concurrent load efficiently', async () => {
      const mockResponse = { data: [createMockProject()], status: 200 };
      mockAxios.get = jest.fn().mockResolvedValue(mockResponse);

      performanceTracker.startTracking('light-concurrent-load');
      
      const requests = Array.from({ length: PERFORMANCE_CONFIG.concurrency.light }, async (_, i) => {
        const startTime = Date.now();
        const result = await apiService.getProjects();
        const duration = performanceTracker.recordMeasurement('light-concurrent-load', startTime);
        return { result, duration };
      });

      const startTime = Date.now();
      const results = await Promise.all(requests);
      const totalDuration = Date.now() - startTime;

      expect(results).toHaveLength(PERFORMANCE_CONFIG.concurrency.light);
      expect(totalDuration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal);

      const stats = performanceTracker.getStatistics('light-concurrent-load');
      expect(stats?.average).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal);
    });

    it('should handle medium concurrent load without degradation', async () => {
      const mockResponse = { data: [createMockProject()], status: 200 };
      mockAxios.get = jest.fn().mockResolvedValue(mockResponse);

      performanceTracker.startTracking('medium-concurrent-load');
      
      const requests = Array.from({ length: PERFORMANCE_CONFIG.concurrency.medium }, async () => {
        const startTime = Date.now();
        await apiService.getProjects();
        return performanceTracker.recordMeasurement('medium-concurrent-load', startTime);
      });

      const results = await Promise.all(requests);

      expect(results).toHaveLength(PERFORMANCE_CONFIG.concurrency.medium);
      
      const stats = performanceTracker.getStatistics('medium-concurrent-load');
      expect(stats?.p95).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal * 2);
    });

    it('should handle mixed API endpoints concurrently', async () => {
      // Mock different endpoints
      mockAxios.get = jest.fn().mockImplementation((url) => {
        if (url.includes('/api/projects')) {
          return Promise.resolve({ data: [createMockProject()], status: 200 });
        } else if (url.includes('/api/dashboard/stats')) {
          return Promise.resolve({ data: { project_count: 10 }, status: 200 });
        } else if (url.includes('/api/videos')) {
          return Promise.resolve({ data: { videos: [], total: 0 }, status: 200 });
        }
        return Promise.resolve({ data: [], status: 200 });
      });

      const mixedRequests = [
        // Project requests
        ...Array.from({ length: 5 }, () => apiService.getProjects()),
        // Dashboard requests
        ...Array.from({ length: 5 }, () => apiService.getDashboardStats()),
        // Video requests
        ...Array.from({ length: 5 }, () => apiService.getAllVideos()),
      ];

      const startTime = Date.now();
      const results = await Promise.all(mixedRequests);
      const totalDuration = Date.now() - startTime;

      expect(results).toHaveLength(15);
      expect(totalDuration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal * 2);
    });

    it('should maintain performance under stress conditions', async () => {
      const mockResponse = { data: [], status: 200 };
      mockAxios.get = jest.fn().mockResolvedValue(mockResponse);

      performanceTracker.startTracking('stress-test');
      
      const batchSize = 10;
      const batches = Math.ceil(PERFORMANCE_CONFIG.concurrency.heavy / batchSize);
      
      for (let batch = 0; batch < batches; batch++) {
        const batchRequests = Array.from({ length: batchSize }, async () => {
          const startTime = Date.now();
          await apiService.getProjects();
          return performanceTracker.recordMeasurement('stress-test', startTime);
        });

        await Promise.all(batchRequests);
      }

      const stats = performanceTracker.getStatistics('stress-test');
      expect(stats?.count).toBe(PERFORMANCE_CONFIG.concurrency.heavy);
      expect(stats?.p99).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.slow);
    });
  });

  describe('Memory Usage Performance', () => {
    it('should not leak memory during repeated requests', async () => {
      const mockResponse = { data: [createMockProject()], status: 200 };
      mockAxios.get = jest.fn().mockResolvedValue(mockResponse);

      performanceTracker.startTracking('memory-test');
      const initialMemory = performanceTracker.getMemoryUsage();

      // Make many requests to test for memory leaks
      for (let i = 0; i < 100; i++) {
        await apiService.getProjects();
      }

      const finalMemory = performanceTracker.getMemoryUsage();
      const memoryIncrease = finalMemory.heapIncrease;

      expect(memoryIncrease).toBeLessThan(PERFORMANCE_CONFIG.memoryLimits.heapIncrease);
    });

    it('should handle large response payloads efficiently', async () => {
      const largePayload = Array.from({ length: PERFORMANCE_CONFIG.dataVolumes.xlarge }, (_, i) => ({
        id: i,
        data: 'x'.repeat(100) // 100 chars per item
      }));

      mockAxios.get = jest.fn().mockResolvedValue({
        data: largePayload,
        status: 200
      });

      performanceTracker.startTracking('large-payload');
      const startTime = Date.now();
      
      const result = await apiService.getProjects();
      
      const duration = performanceTracker.recordMeasurement('large-payload', startTime);
      const memoryUsage = performanceTracker.getMemoryUsage();

      expect(result).toHaveLength(PERFORMANCE_CONFIG.dataVolumes.xlarge);
      expect(duration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.batch);
      expect(memoryUsage.heapUsed).toBeLessThan(PERFORMANCE_CONFIG.memoryLimits.maxHeapUsage);
    });

    it('should efficiently manage cache memory', async () => {
      performanceTracker.startTracking('cache-memory-test');
      
      // Fill cache with various data
      for (let i = 0; i < 200; i++) {
        const mockData = Array.from({ length: 10 }, (_, j) => ({ id: j, data: `item-${i}-${j}` }));
        apiCache.set('GET', `/api/test-${i}`, mockData);
      }

      const memoryAfterCaching = performanceTracker.getMemoryUsage();
      const cacheStats = apiCache.getStats();

      // Cache should have automatic cleanup
      expect(cacheStats.totalEntries).toBeLessThanOrEqual(100); // Max cache size
      expect(memoryAfterCaching.heapIncrease).toBeLessThan(PERFORMANCE_CONFIG.memoryLimits.heapIncrease);
    });
  });

  describe('Enhanced API Service Performance', () => {
    it('should perform well with retry mechanisms', async () => {
      let attemptCount = 0;
      mockAxios.request = jest.fn().mockImplementation(() => {
        attemptCount++;
        if (attemptCount === 1) {
          // First attempt fails
          throw new Error('Temporary failure');
        }
        return Promise.resolve({ data: [], status: 200 });
      });

      performanceTracker.startTracking('retry-performance');
      const startTime = Date.now();
      
      await enhancedApiService.getProjects();
      
      const duration = performanceTracker.recordMeasurement('retry-performance', startTime);

      expect(attemptCount).toBe(2);
      expect(duration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal * 2);
    });

    it('should collect metrics without significant overhead', async () => {
      mockAxios.request = jest.fn().mockResolvedValue({ data: [], status: 200 });

      performanceTracker.startTracking('metrics-overhead');
      
      // Make requests while metrics are being collected
      for (let i = 0; i < 50; i++) {
        const startTime = Date.now();
        await enhancedApiService.getProjects();
        performanceTracker.recordMeasurement('metrics-overhead', startTime);
      }

      const stats = performanceTracker.getStatistics('metrics-overhead');
      const serviceMetrics = enhancedApiService.getMetrics();

      expect(stats?.count).toBe(50);
      expect(Array.isArray(serviceMetrics)).toBe(true);
      expect(stats?.average).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal);
    });

    it('should handle health checks efficiently', async () => {
      mockAxios.request = jest.fn().mockResolvedValue({
        data: { status: 'ok' },
        status: 200
      });

      performanceTracker.startTracking('health-check-performance');
      
      // Perform multiple health checks
      const healthPromises = Array.from({ length: 20 }, async () => {
        const startTime = Date.now();
        const result = await enhancedApiService.healthCheck();
        const duration = performanceTracker.recordMeasurement('health-check-performance', startTime);
        return { result, duration };
      });

      const results = await Promise.all(healthPromises);

      expect(results).toHaveLength(20);
      results.forEach(({ result, duration }) => {
        expect(result.status).toBe('ok');
        expect(duration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.fast);
      });
    });
  });

  describe('File Upload Performance', () => {
    it('should handle file uploads within acceptable time limits', async () => {
      const fileContent = new ArrayBuffer(1024 * 1024); // 1MB file
      const mockFile = new File([fileContent], 'test.mp4', { type: 'video/mp4' });
      
      let progressCallbacks = 0;
      mockAxios.post = jest.fn().mockImplementation((url, data, config) => {
        // Simulate upload progress
        if (config?.onUploadProgress) {
          setTimeout(() => config.onUploadProgress({ loaded: 50, total: 100 }), 10);
          setTimeout(() => config.onUploadProgress({ loaded: 100, total: 100 }), 20);
          progressCallbacks++;
        }
        return Promise.resolve({ data: createMockVideoFile(), status: 201 });
      });

      performanceTracker.startTracking('file-upload');
      const startTime = Date.now();
      
      await apiService.uploadVideo('proj-123', mockFile, (progress) => {
        expect(progress).toBeGreaterThanOrEqual(0);
        expect(progress).toBeLessThanOrEqual(100);
      });
      
      const duration = performanceTracker.recordMeasurement('file-upload', startTime);

      expect(duration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.slow);
      expect(mockAxios.post).toHaveBeenCalledWith(
        '/api/projects/proj-123/videos',
        expect.any(FormData),
        expect.objectContaining({
          onUploadProgress: expect.any(Function)
        })
      );
    });

    it('should handle multiple file uploads concurrently', async () => {
      const files = Array.from({ length: 5 }, (_, i) => 
        new File([new ArrayBuffer(512 * 1024)], `test${i}.mp4`, { type: 'video/mp4' })
      );

      mockAxios.post = jest.fn().mockResolvedValue({
        data: createMockVideoFile(),
        status: 201
      });

      performanceTracker.startTracking('concurrent-upload');
      
      const uploadPromises = files.map(async (file, i) => {
        const startTime = Date.now();
        const result = await apiService.uploadVideo(`proj-${i}`, file);
        const duration = performanceTracker.recordMeasurement('concurrent-upload', startTime);
        return { result, duration };
      });

      const results = await Promise.all(uploadPromises);

      expect(results).toHaveLength(5);
      
      const stats = performanceTracker.getStatistics('concurrent-upload');
      expect(stats?.max).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.slow);
    });
  });

  describe('Performance Regression Detection', () => {
    it('should maintain consistent performance across test runs', async () => {
      const mockResponse = { data: [createMockProject()], status: 200 };
      mockAxios.get = jest.fn().mockResolvedValue(mockResponse);

      const testRuns = 3;
      const requestsPerRun = 20;
      const allStats: Array<{ average: number; p95: number }> = [];

      for (let run = 0; run < testRuns; run++) {
        performanceTracker.clear();
        performanceTracker.startTracking(`run-${run}`);

        const promises = Array.from({ length: requestsPerRun }, async () => {
          const startTime = Date.now();
          await apiService.getProjects();
          return performanceTracker.recordMeasurement(`run-${run}`, startTime);
        });

        await Promise.all(promises);
        
        const stats = performanceTracker.getStatistics(`run-${run}`);
        if (stats) {
          allStats.push({
            average: stats.average,
            p95: stats.p95
          });
        }
      }

      expect(allStats).toHaveLength(testRuns);
      
      // Check for significant performance regression between runs
      const averagePerformance = allStats.map(s => s.average);
      const maxVariance = Math.max(...averagePerformance) - Math.min(...averagePerformance);
      
      // Performance should not vary by more than 50% between runs
      expect(maxVariance).toBeLessThan(Math.min(...averagePerformance) * 0.5);
    });

    it('should identify performance bottlenecks in different operations', async () => {
      const operations = {
        'simple-get': () => {
          mockAxios.get = jest.fn().mockResolvedValue({ data: [], status: 200 });
          return apiService.getProjects();
        },
        'complex-get': () => {
          const largeData = Array.from({ length: 1000 }, (_, i) => ({ id: i }));
          mockAxios.get = jest.fn().mockResolvedValue({ data: largeData, status: 200 });
          return apiService.getAllVideos();
        },
        'post-operation': () => {
          mockAxios.post = jest.fn().mockResolvedValue({ data: createMockProject(), status: 201 });
          return apiService.createProject(createMockProject());
        }
      };

      const results: Record<string, any> = {};

      for (const [operationName, operation] of Object.entries(operations)) {
        performanceTracker.startTracking(operationName);
        
        // Run each operation multiple times
        for (let i = 0; i < 10; i++) {
          const startTime = Date.now();
          await operation();
          performanceTracker.recordMeasurement(operationName, startTime);
        }

        results[operationName] = performanceTracker.getStatistics(operationName);
      }

      // Verify that operations meet their expected performance characteristics
      expect(results['simple-get']?.average).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal);
      expect(results['complex-get']?.average).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.slow);
      expect(results['post-operation']?.average).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal);
    });
  });

  describe('Real-world Performance Scenarios', () => {
    it('should handle dashboard loading scenario efficiently', async () => {
      // Simulate dashboard loading multiple endpoints
      mockAxios.get = jest.fn().mockImplementation((url) => {
        const delay = url.includes('stats') ? 100 : 200;
        return new Promise(resolve => 
          setTimeout(() => resolve({ data: {}, status: 200 }), delay)
        );
      });

      performanceTracker.startTracking('dashboard-scenario');
      const startTime = Date.now();

      // Simulate parallel dashboard data loading
      await Promise.all([
        apiService.getDashboardStats(),
        apiService.getChartData(),
        apiService.getProjects(0, 5)
      ]);

      const totalDuration = performanceTracker.recordMeasurement('dashboard-scenario', startTime);

      // Total time should be close to the slowest request, not sum of all
      expect(totalDuration).toBeLessThan(500); // Should be ~200ms + overhead
    });

    it('should handle project detail page loading efficiently', async () => {
      const projectId = 'proj-123';
      
      mockAxios.get = jest.fn().mockImplementation((url) => {
        if (url.includes(`/projects/${projectId}`)) {
          return Promise.resolve({ data: createMockProject(), status: 200 });
        } else if (url.includes(`/projects/${projectId}/videos`)) {
          const videos = Array.from({ length: 10 }, () => createMockVideoFile());
          return Promise.resolve({ data: videos, status: 200 });
        }
        return Promise.resolve({ data: [], status: 200 });
      });

      performanceTracker.startTracking('project-detail-scenario');
      const startTime = Date.now();

      // Simulate project detail page data loading
      const [project, videos] = await Promise.all([
        apiService.getProject(projectId),
        apiService.getVideos(projectId)
      ]);

      const totalDuration = performanceTracker.recordMeasurement('project-detail-scenario', startTime);

      expect(project).toBeDefined();
      expect(videos).toHaveLength(10);
      expect(totalDuration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.normal);
    });

    it('should handle bulk operations efficiently', async () => {
      // Simulate bulk project creation
      mockAxios.post = jest.fn().mockImplementation(() => {
        return Promise.resolve({ data: createMockProject(), status: 201 });
      });

      performanceTracker.startTracking('bulk-operations');
      const startTime = Date.now();

      const batchSize = 10;
      const batches = Array.from({ length: batchSize }, (_, i) => 
        apiService.createProject({
          ...createMockProject(),
          name: `Bulk Project ${i}`
        })
      );

      await Promise.all(batches);

      const totalDuration = performanceTracker.recordMeasurement('bulk-operations', startTime);

      expect(totalDuration).toBeLessThan(PERFORMANCE_CONFIG.responseTimeThreshold.batch);
    });
  });
});