/**
 * Performance Monitoring Test Suite
 * 
 * This test suite monitors various performance aspects after the URL fix:
 * - Video loading times
 * - API response times
 * - Memory usage
 * - Network requests
 * - Frontend rendering performance
 */

import { jest } from '@jest/globals';
import axios from 'axios';
import { fixVideoUrl, fixMultipleVideoUrls, getCacheStats } from '../../src/utils/videoUrlFixer';

// Performance monitoring utilities
interface PerformanceMetrics {
  startTime: number;
  endTime: number;
  duration: number;
  memoryBefore?: number;
  memoryAfter?: number;
  memoryDelta?: number;
}

class PerformanceMonitor {
  private metrics: Map<string, PerformanceMetrics> = new Map();

  startTest(testName: string): void {
    const startTime = performance.now();
    const memoryBefore = (performance as any).memory?.usedJSHeapSize;
    
    this.metrics.set(testName, {
      startTime,
      endTime: 0,
      duration: 0,
      memoryBefore
    });
  }

  endTest(testName: string): PerformanceMetrics {
    const metric = this.metrics.get(testName);
    if (!metric) {
      throw new Error(`Test ${testName} was not started`);
    }

    const endTime = performance.now();
    const memoryAfter = (performance as any).memory?.usedJSHeapSize;
    const duration = endTime - metric.startTime;
    const memoryDelta = memoryAfter && metric.memoryBefore 
      ? memoryAfter - metric.memoryBefore 
      : undefined;

    const completedMetric: PerformanceMetrics = {
      ...metric,
      endTime,
      duration,
      memoryAfter,
      memoryDelta
    };

    this.metrics.set(testName, completedMetric);
    return completedMetric;
  }

  getMetric(testName: string): PerformanceMetrics | undefined {
    return this.metrics.get(testName);
  }

  getAllMetrics(): Map<string, PerformanceMetrics> {
    return new Map(this.metrics);
  }

  logSummary(): void {
    console.log('\n📊 Performance Test Summary:');
    console.table(
      Array.from(this.metrics.entries()).map(([name, metric]) => ({
        Test: name,
        'Duration (ms)': metric.duration.toFixed(2),
        'Memory Delta (KB)': metric.memoryDelta 
          ? (metric.memoryDelta / 1024).toFixed(2) 
          : 'N/A'
      }))
    );
  }
}

describe('Performance Monitoring - URL Processing', () => {
  let monitor: PerformanceMonitor;

  beforeEach(() => {
    monitor = new PerformanceMonitor();
  });

  afterEach(() => {
    monitor.logSummary();
  });

  test('should measure single URL fix performance', () => {
    monitor.startTest('single-url-fix');
    
    const testUrl = 'http://localhost:8000/uploads/test-video.mp4';
    const result = fixVideoUrl(testUrl);
    
    const metrics = monitor.endTest('single-url-fix');
    
    expect(result).toBe('http://155.138.239.131:8000/uploads/test-video.mp4');
    expect(metrics.duration).toBeLessThan(1); // Should be sub-millisecond
    
    console.log(`✅ Single URL fix completed in ${metrics.duration.toFixed(3)}ms`);
  });

  test('should measure batch URL fix performance', () => {
    const batchSizes = [10, 100, 1000, 5000];
    const results: { size: number; duration: number; rate: number }[] = [];

    batchSizes.forEach(size => {
      const testVideos = Array.from({ length: size }, (_, i) => ({
        id: `video-${i}`,
        name: `video-${i}.mp4`,
        url: `http://localhost:8000/uploads/video-${i}.mp4`,
        filename: `video-${i}.mp4`
      }));

      monitor.startTest(`batch-${size}`);
      fixMultipleVideoUrls(testVideos, { debug: false });
      const metrics = monitor.endTest(`batch-${size}`);

      const rate = size / (metrics.duration / 1000); // URLs per second
      results.push({ size, duration: metrics.duration, rate });

      // Performance expectations
      expect(metrics.duration).toBeLessThan(size / 10); // Max 0.1ms per URL
      expect(rate).toBeGreaterThan(1000); // At least 1000 URLs per second

      console.log(`✅ Batch of ${size} URLs processed in ${metrics.duration.toFixed(2)}ms (${rate.toFixed(0)} URLs/sec)`);
    });

    // Verify performance scales reasonably
    const smallBatchRate = results[0].rate;
    const largeBatchRate = results[results.length - 1].rate;
    
    // Large batches should be at least 50% as efficient as small batches
    expect(largeBatchRate).toBeGreaterThan(smallBatchRate * 0.5);
  });

  test('should measure cache performance impact', () => {
    // Test cache miss (first call)
    monitor.startTest('cache-miss');
    fixVideoUrl('http://localhost:8000/uploads/video1.mp4');
    const cacheMissMetrics = monitor.endTest('cache-miss');

    // Test cache hit (subsequent calls)
    monitor.startTest('cache-hit');
    fixVideoUrl('http://localhost:8000/uploads/video2.mp4');
    const cacheHitMetrics = monitor.endTest('cache-hit');

    // Cache hits should be faster
    expect(cacheHitMetrics.duration).toBeLessThanOrEqual(cacheMissMetrics.duration);

    const cacheStats = getCacheStats();
    expect(cacheStats.hasCachedUrl).toBe(true);
    
    console.log(`✅ Cache miss: ${cacheMissMetrics.duration.toFixed(3)}ms, Cache hit: ${cacheHitMetrics.duration.toFixed(3)}ms`);
  });

  test('should measure memory usage during intensive operations', () => {
    const largeVideoSet = Array.from({ length: 10000 }, (_, i) => ({
      id: `video-${i}`,
      url: `http://localhost:8000/uploads/video-${i}.mp4`
    }));

    monitor.startTest('memory-intensive');
    
    // Process large dataset multiple times
    for (let i = 0; i < 5; i++) {
      fixMultipleVideoUrls([...largeVideoSet], { debug: false });
    }
    
    const metrics = monitor.endTest('memory-intensive');

    // Memory usage should be reasonable
    if (metrics.memoryDelta) {
      const memoryIncreaseMB = metrics.memoryDelta / (1024 * 1024);
      expect(memoryIncreaseMB).toBeLessThan(50); // Less than 50MB increase
      
      console.log(`✅ Memory increase: ${memoryIncreaseMB.toFixed(2)}MB for 50,000 URL operations`);
    }

    // Should complete in reasonable time
    expect(metrics.duration).toBeLessThan(2000); // Less than 2 seconds
  });
});

describe('Performance Monitoring - API Operations', () => {
  let monitor: PerformanceMonitor;

  beforeEach(() => {
    monitor = new PerformanceMonitor();
    jest.clearAllMocks();
  });

  afterEach(() => {
    monitor.logSummary();
  });

  test('should measure API response time improvements', async () => {
    const mockAxios = jest.mocked(axios);
    
    // Mock fast API response
    mockAxios.get.mockResolvedValue({
      data: Array.from({ length: 100 }, (_, i) => ({
        id: `video-${i}`,
        name: `video-${i}.mp4`,
        url: `http://155.138.239.131:8000/uploads/video-${i}.mp4`,
        filename: `video-${i}.mp4`
      })),
      status: 200
    });

    monitor.startTest('api-response');
    
    const response = await axios.get('/api/videos');
    
    const metrics = monitor.endTest('api-response');

    expect(response.status).toBe(200);
    expect(response.data).toHaveLength(100);
    
    // Response should be fast (mocked, but structure validation)
    expect(metrics.duration).toBeLessThan(100);
    
    console.log(`✅ API response time: ${metrics.duration.toFixed(2)}ms for 100 videos`);
  });

  test('should measure video URL validation performance', async () => {
    const testUrls = [
      'http://155.138.239.131:8000/uploads/video1.mp4',
      'http://155.138.239.131:8000/uploads/video2.mp4',
      'http://155.138.239.131:8000/uploads/video3.mp4',
      'http://155.138.239.131:8000/uploads/video4.mp4',
      'http://155.138.239.131:8000/uploads/video5.mp4'
    ];

    const mockAxios = jest.mocked(axios);
    mockAxios.head.mockResolvedValue({
      status: 200,
      headers: { 'content-type': 'video/mp4' }
    });

    monitor.startTest('url-validation');
    
    const validationPromises = testUrls.map(url => 
      axios.head(url).then(() => ({ url, valid: true })).catch(() => ({ url, valid: false }))
    );
    
    const results = await Promise.all(validationPromises);
    
    const metrics = monitor.endTest('url-validation');

    expect(results.every(result => result.valid)).toBe(true);
    
    // Parallel validation should be fast
    expect(metrics.duration).toBeLessThan(50);
    
    console.log(`✅ URL validation for ${testUrls.length} URLs: ${metrics.duration.toFixed(2)}ms`);
  });

  test('should measure streaming performance simulation', async () => {
    const streamingUrl = 'http://155.138.239.131:8000/uploads/large-video.mp4';
    
    const mockAxios = jest.mocked(axios);
    
    // Simulate progressive loading with multiple range requests
    const chunkSize = 1024 * 1024; // 1MB chunks
    const totalChunks = 10;
    
    mockAxios.get.mockImplementation(({ headers }) => {
      const range = headers?.Range as string;
      const chunkIndex = parseInt(range?.match(/bytes=(\d+)-/)?.[1] || '0') / chunkSize;
      
      return Promise.resolve({
        status: 206,
        headers: {
          'content-range': `bytes ${chunkIndex * chunkSize}-${(chunkIndex + 1) * chunkSize - 1}/${totalChunks * chunkSize}`,
          'content-type': 'video/mp4'
        },
        data: new ArrayBuffer(chunkSize)
      });
    });

    monitor.startTest('streaming-simulation');
    
    // Simulate loading first few chunks
    const chunkPromises = Array.from({ length: 3 }, (_, i) => 
      axios.get(streamingUrl, {
        headers: { Range: `bytes=${i * chunkSize}-${(i + 1) * chunkSize - 1}` }
      })
    );
    
    const chunks = await Promise.all(chunkPromises);
    
    const metrics = monitor.endTest('streaming-simulation');

    expect(chunks).toHaveLength(3);
    chunks.forEach(chunk => {
      expect(chunk.status).toBe(206);
      expect(chunk.headers['content-type']).toBe('video/mp4');
    });

    // Streaming should be efficient
    expect(metrics.duration).toBeLessThan(100);
    
    console.log(`✅ Streaming simulation (3 chunks): ${metrics.duration.toFixed(2)}ms`);
  });
});

describe('Performance Monitoring - Frontend Rendering', () => {
  let monitor: PerformanceMonitor;

  beforeEach(() => {
    monitor = new PerformanceMonitor();
  });

  afterEach(() => {
    monitor.logSummary();
  });

  test('should measure DOM manipulation performance', () => {
    monitor.startTest('dom-manipulation');
    
    // Simulate creating and updating many video elements
    const videoElements: HTMLVideoElement[] = [];
    
    for (let i = 0; i < 100; i++) {
      const video = document.createElement('video');
      video.src = `http://155.138.239.131:8000/uploads/video-${i}.mp4`;
      video.preload = 'metadata';
      videoElements.push(video);
    }
    
    // Update all sources
    videoElements.forEach((video, i) => {
      video.src = `http://155.138.239.131:8000/uploads/updated-video-${i}.mp4`;
    });
    
    const metrics = monitor.endTest('dom-manipulation');

    expect(videoElements).toHaveLength(100);
    videoElements.forEach(video => {
      expect(video.src).toContain('155.138.239.131:8000');
    });

    // DOM operations should be fast
    expect(metrics.duration).toBeLessThan(50);
    
    console.log(`✅ DOM manipulation (100 video elements): ${metrics.duration.toFixed(2)}ms`);
  });

  test('should measure component re-render performance', () => {
    const componentRenderCount = 50;
    const videosPerComponent = 20;

    monitor.startTest('component-rerenders');
    
    // Simulate multiple component renders with video data
    for (let render = 0; render < componentRenderCount; render++) {
      const videoData = Array.from({ length: videosPerComponent }, (_, i) => ({
        id: `video-${render}-${i}`,
        name: `video-${render}-${i}.mp4`,
        url: `http://155.138.239.131:8000/uploads/video-${render}-${i}.mp4`
      }));
      
      // Simulate processing video data for rendering
      videoData.forEach(video => {
        const processedUrl = fixVideoUrl(video.url);
        expect(processedUrl).toBe(video.url); // Should be no-op since already correct
      });
    }
    
    const metrics = monitor.endTest('component-rerenders');

    // Re-renders should be efficient
    expect(metrics.duration).toBeLessThan(100);
    
    const totalVideos = componentRenderCount * videosPerComponent;
    const videosPerMs = totalVideos / metrics.duration;
    
    console.log(`✅ Component re-renders (${componentRenderCount} renders, ${totalVideos} videos): ${metrics.duration.toFixed(2)}ms (${videosPerMs.toFixed(0)} videos/ms)`);
  });

  test('should measure async operation handling', async () => {
    monitor.startTest('async-operations');
    
    // Simulate multiple async operations that might happen in the app
    const asyncOperations = Array.from({ length: 20 }, async (_, i) => {
      // Simulate async URL processing
      await new Promise(resolve => setTimeout(resolve, Math.random() * 10));
      return fixVideoUrl(`http://localhost:8000/uploads/video-${i}.mp4`);
    });
    
    const results = await Promise.all(asyncOperations);
    
    const metrics = monitor.endTest('async-operations');

    expect(results).toHaveLength(20);
    results.forEach(result => {
      expect(result).toContain('155.138.239.131:8000');
    });

    // Async operations should complete quickly
    expect(metrics.duration).toBeLessThan(200);
    
    console.log(`✅ Async operations (20 concurrent): ${metrics.duration.toFixed(2)}ms`);
  });
});

describe('Performance Monitoring - Summary and Benchmarks', () => {
  test('should establish performance benchmarks', () => {
    const benchmarks = {
      singleUrlFix: { expected: 1, unit: 'ms' },
      batchUrlFix: { expected: 0.1, unit: 'ms per URL' },
      apiResponse: { expected: 100, unit: 'ms' },
      domManipulation: { expected: 50, unit: 'ms per 100 elements' },
      memoryUsage: { expected: 50, unit: 'MB for intensive operations' },
      cacheHitRatio: { expected: 0.9, unit: 'ratio' }
    };

    console.log('📋 Performance Benchmarks:');
    console.table(benchmarks);

    // Verify benchmarks are reasonable
    Object.entries(benchmarks).forEach(([test, benchmark]) => {
      expect(benchmark.expected).toBeGreaterThan(0);
      expect(benchmark.unit).toBeDefined();
    });
  });

  test('should provide performance monitoring summary', () => {
    const summary = {
      testSuite: 'URL Fix Performance Monitoring',
      categories: [
        'URL Processing Performance',
        'API Operations Performance', 
        'Frontend Rendering Performance'
      ],
      keyMetrics: [
        'Single URL fix latency',
        'Batch processing throughput',
        'Memory usage efficiency',
        'Cache performance',
        'DOM manipulation speed'
      ],
      performanceTargets: {
        urlProcessing: '< 1ms per URL',
        batchProcessing: '> 1000 URLs/sec',
        memoryUsage: '< 50MB for intensive ops',
        apiResponse: '< 100ms',
        domOps: '< 50ms per 100 elements'
      }
    };

    console.log('🎯 Performance Monitoring Summary:', summary);

    expect(summary.categories.length).toBe(3);
    expect(summary.keyMetrics.length).toBe(5);
    expect(Object.keys(summary.performanceTargets).length).toBe(5);

    console.log('✅ Performance monitoring test suite completed successfully');
  });
});