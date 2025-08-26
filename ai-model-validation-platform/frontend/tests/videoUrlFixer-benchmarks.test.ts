/**
 * Performance benchmark tests for VideoUrlFixer optimization system
 * Tests performance characteristics, memory usage, and scalability
 */

import {
  fixVideoUrl,
  fixMultipleVideoUrls,
  getPerformanceMetrics,
  resetMetrics,
  clearAllCaches,
  performMaintenance
} from '../src/utils/videoUrlFixer';

// Mock environment config for consistent benchmarks
jest.mock('../src/utils/envConfig', () => ({
  getServiceConfig: jest.fn((service) => {
    if (service === 'video') {
      return { baseUrl: 'http://155.138.239.131:8000' };
    }
    return {};
  })
}));

describe('VideoUrlFixer Performance Benchmarks', () => {
  beforeEach(() => {
    clearAllCaches();
    resetMetrics();
  });

  describe('Single URL Processing Performance', () => {
    it('should process single URLs efficiently', () => {
      const iterations = 1000;
      const testUrls = [
        'http://localhost:8000/uploads/test.mp4',
        '/uploads/relative.mp4',
        'http://155.138.239.131:8000/uploads/correct.mp4',
        ''
      ];

      const startTime = performance.now();
      
      for (let i = 0; i < iterations; i++) {
        const url = testUrls[i % testUrls.length];
        fixVideoUrl(url, `test${i}.mp4`, `id${i}`);
      }
      
      const endTime = performance.now();
      const totalTime = endTime - startTime;
      const avgTimePerUrl = totalTime / iterations;
      
      console.log(`Single URL Processing Benchmark:
        - Total iterations: ${iterations}
        - Total time: ${totalTime.toFixed(2)}ms
        - Average per URL: ${avgTimePerUrl.toFixed(3)}ms
        - Throughput: ${(iterations / totalTime * 1000).toFixed(0)} URLs/sec`);
      
      // Performance assertions
      expect(avgTimePerUrl).toBeLessThan(5); // Should be under 5ms per URL
      expect(totalTime).toBeLessThan(5000); // Should complete in under 5 seconds
    });

    it('should demonstrate cache performance benefits', () => {
      const testUrl = 'http://localhost:8000/uploads/test.mp4';
      const iterations = 100;
      
      // First run - no cache
      clearAllCaches();
      const startCold = performance.now();
      for (let i = 0; i < iterations; i++) {
        fixVideoUrl(testUrl);
      }
      const endCold = performance.now();
      const coldTime = endCold - startCold;
      
      // Second run - with cache
      const startWarm = performance.now();
      for (let i = 0; i < iterations; i++) {
        fixVideoUrl(testUrl);
      }
      const endWarm = performance.now();
      const warmTime = endWarm - startWarm;
      
      const metrics = getPerformanceMetrics();
      const speedup = coldTime / warmTime;
      
      console.log(`Cache Performance Benchmark:
        - Cold run time: ${coldTime.toFixed(2)}ms
        - Warm run time: ${warmTime.toFixed(2)}ms
        - Speedup: ${speedup.toFixed(2)}x
        - Cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`);
      
      expect(speedup).toBeGreaterThan(1.5); // Should be at least 50% faster
      expect(metrics.cacheStats.cacheHitRate).toBeGreaterThan(0.8); // High hit rate
    });
  });

  describe('Batch Processing Performance', () => {
    it('should handle large batch processing efficiently', async () => {
      const batchSizes = [100, 500, 1000, 2000];
      const results: Array<{ size: number; time: number; throughput: number }> = [];
      
      for (const size of batchSizes) {
        const videos = Array.from({ length: size }, (_, i) => ({
          id: `video-${i}`,
          url: i % 3 === 0 ? `http://localhost:8000/uploads/video${i}.mp4` : 
               i % 3 === 1 ? `/uploads/video${i}.mp4` :
               `http://155.138.239.131:8000/uploads/video${i}.mp4`,
          filename: `video${i}.mp4`
        }));
        
        resetMetrics();
        const startTime = performance.now();
        
        await fixMultipleVideoUrls(videos, {
          chunkSize: Math.min(50, size / 4),
          throttleMs: 0, // No throttling for benchmarks
          debug: false
        });
        
        const endTime = performance.now();
        const processingTime = endTime - startTime;
        const throughput = size / processingTime * 1000; // videos per second
        
        results.push({ size, time: processingTime, throughput });
        
        console.log(`Batch ${size} videos: ${processingTime.toFixed(2)}ms (${throughput.toFixed(0)} videos/sec)`);
      }
      
      // Performance assertions
      for (const result of results) {
        expect(result.throughput).toBeGreaterThan(50); // Minimum throughput
        expect(result.time).toBeLessThan(result.size * 10); // Max 10ms per video
      }
      
      // Should scale reasonably well
      const smallBatch = results.find(r => r.size === 100);
      const largeBatch = results.find(r => r.size === 2000);
      if (smallBatch && largeBatch) {
        const efficiencyRatio = (largeBatch.throughput / smallBatch.throughput);
        expect(efficiencyRatio).toBeGreaterThan(0.5); // Should maintain at least 50% efficiency
      }
    });

    it('should demonstrate chunk size optimization', async () => {
      const videoCount = 500;
      const videos = Array.from({ length: videoCount }, (_, i) => ({
        url: `http://localhost:8000/uploads/video${i}.mp4`
      }));
      
      const chunkSizes = [5, 10, 25, 50, 100];
      const results: Array<{ chunkSize: number; time: number }> = [];
      
      for (const chunkSize of chunkSizes) {
        resetMetrics();
        const startTime = performance.now();
        
        await fixMultipleVideoUrls(videos, {
          chunkSize,
          throttleMs: 1,
          debug: false
        });
        
        const endTime = performance.now();
        const processingTime = endTime - startTime;
        
        results.push({ chunkSize, time: processingTime });
        console.log(`Chunk size ${chunkSize}: ${processingTime.toFixed(2)}ms`);
      }
      
      // Find optimal chunk size (should be somewhere in the middle)
      const optimalResult = results.reduce((min, current) => 
        current.time < min.time ? current : min
      );
      
      console.log(`Optimal chunk size: ${optimalResult.chunkSize}`);\n      
      expect(optimalResult.chunkSize).toBeGreaterThan(5);
      expect(optimalResult.chunkSize).toBeLessThan(100);
    });
  });

  describe('Memory Usage and Scaling', () => {
    it('should maintain reasonable memory usage under load', () => {
      const initialMemory = process.memoryUsage();
      
      // Process large number of unique URLs to test cache limits
      for (let i = 0; i < 2000; i++) {
        fixVideoUrl(`http://localhost:8000/uploads/video${i}.mp4`);
      }
      
      const afterProcessingMemory = process.memoryUsage();
      performMaintenance(); // Trigger cleanup
      const afterCleanupMemory = process.memoryUsage();
      
      const memoryIncrease = afterProcessingMemory.heapUsed - initialMemory.heapUsed;
      const memoryAfterCleanup = afterCleanupMemory.heapUsed - initialMemory.heapUsed;
      
      console.log(`Memory Usage Benchmark:
        - Initial heap: ${(initialMemory.heapUsed / 1024 / 1024).toFixed(2)} MB
        - After processing: ${(afterProcessingMemory.heapUsed / 1024 / 1024).toFixed(2)} MB
        - After cleanup: ${(afterCleanupMemory.heapUsed / 1024 / 1024).toFixed(2)} MB
        - Memory increase: ${(memoryIncrease / 1024 / 1024).toFixed(2)} MB`);
      
      // Should not use excessive memory
      expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024); // Less than 50MB increase
      
      // Cleanup should help reduce memory usage
      expect(memoryAfterCleanup).toBeLessThanOrEqual(afterProcessingMemory.heapUsed);
    });

    it('should handle cache size limits effectively', () => {
      const cacheLimit = 1000;
      
      // Fill cache beyond limit
      for (let i = 0; i < cacheLimit * 1.5; i++) {
        fixVideoUrl(`http://localhost:8000/uploads/video${i}.mp4`);
      }
      
      const metrics = getPerformanceMetrics();
      
      console.log(`Cache Size Management:
        - URLs processed: ${cacheLimit * 1.5}
        - Cache size: ${metrics.cacheStats.urlMappingCacheSize}
        - Cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`);
      
      // Cache should be limited
      expect(metrics.cacheStats.urlMappingCacheSize).toBeLessThan(cacheLimit * 1.2);
      
      // Should still maintain reasonable performance
      expect(metrics.averageProcessingTime).toBeLessThan(10);
    });
  });

  describe('Concurrent Processing Simulation', () => {
    it('should handle concurrent requests efficiently', async () => {
      const concurrentRequests = 100;
      const urlsPerRequest = 10;
      
      const promises: Promise<void>[] = [];
      const startTime = performance.now();
      
      for (let i = 0; i < concurrentRequests; i++) {
        const videos = Array.from({ length: urlsPerRequest }, (_, j) => ({
          url: `http://localhost:8000/uploads/batch${i}_video${j}.mp4`
        }));
        
        promises.push(fixMultipleVideoUrls(videos, { 
          chunkSize: 5,
          throttleMs: 0,
          debug: false 
        }));
      }
      
      await Promise.all(promises);
      const endTime = performance.now();
      
      const totalTime = endTime - startTime;
      const totalVideos = concurrentRequests * urlsPerRequest;
      const throughput = totalVideos / totalTime * 1000;
      
      console.log(`Concurrent Processing Benchmark:
        - Concurrent requests: ${concurrentRequests}
        - Videos per request: ${urlsPerRequest}
        - Total videos: ${totalVideos}
        - Total time: ${totalTime.toFixed(2)}ms
        - Throughput: ${throughput.toFixed(0)} videos/sec`);
      
      const metrics = getPerformanceMetrics();
      
      expect(throughput).toBeGreaterThan(100); // Should handle at least 100 videos/sec
      expect(metrics.errorsEncountered).toBe(0); // No errors in concurrent processing
    });
  });

  describe('Migration Mode Performance', () => {
    it('should maintain acceptable performance during migration', () => {
      // Mock migration active
      jest.doMock('../src/utils/envConfig', () => ({
        getServiceConfig: jest.fn((service) => {
          if (service === 'database') {
            return { migrating: true };
          }
          return { baseUrl: 'http://155.138.239.131:8000' };
        })
      }));
      
      const iterations = 500;
      const testUrls = Array.from({ length: iterations }, (_, i) => 
        `http://localhost:8000/uploads/video${i}.mp4`
      );
      
      const startTime = performance.now();
      
      testUrls.forEach(url => {
        fixVideoUrl(url);
      });
      
      const endTime = performance.now();
      const totalTime = endTime - startTime;
      const avgTime = totalTime / iterations;
      
      const metrics = getPerformanceMetrics();
      
      console.log(`Migration Mode Performance:
        - Iterations: ${iterations}
        - Total time: ${totalTime.toFixed(2)}ms
        - Average per URL: ${avgTime.toFixed(3)}ms
        - Migration-aware skips: ${metrics.migrationAwareSkips}`);
      
      // Should still be reasonably fast during migration
      expect(avgTime).toBeLessThan(10); // Under 10ms average
      expect(metrics.migrationAwareSkips).toBeGreaterThan(0); // Should use optimization
    });
  });

  describe('Regression Detection', () => {
    it('should maintain performance baseline', () => {
      const baselineThresholds = {
        avgProcessingTime: 5, // 5ms per URL
        batchThroughput: 200, // 200 URLs per second
        cacheHitRateAfter100: 0.8, // 80% hit rate after processing
        memoryPerUrl: 100 // 100 bytes per URL max
      };
      
      // Test single URL performance
      const singleUrlIterations = 100;
      const startMemory = process.memoryUsage().heapUsed;
      const startTime = performance.now();
      
      for (let i = 0; i < singleUrlIterations; i++) {
        fixVideoUrl(`http://localhost:8000/uploads/test${i % 10}.mp4`);
      }
      
      const endTime = performance.now();
      const endMemory = process.memoryUsage().heapUsed;
      
      const avgTime = (endTime - startTime) / singleUrlIterations;
      const memoryPerUrl = (endMemory - startMemory) / singleUrlIterations;
      const metrics = getPerformanceMetrics();
      
      console.log(`Performance Regression Check:
        - Avg processing time: ${avgTime.toFixed(3)}ms (baseline: <${baselineThresholds.avgProcessingTime}ms)
        - Memory per URL: ${memoryPerUrl.toFixed(0)} bytes (baseline: <${baselineThresholds.memoryPerUrl} bytes)
        - Cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}% (baseline: >${baselineThresholds.cacheHitRateAfter100 * 100}%)`);
      
      // Regression checks
      expect(avgTime).toBeLessThan(baselineThresholds.avgProcessingTime);
      expect(memoryPerUrl).toBeLessThan(baselineThresholds.memoryPerUrl);
      expect(metrics.cacheStats.cacheHitRate).toBeGreaterThan(baselineThresholds.cacheHitRateAfter100);
    });
  });
});