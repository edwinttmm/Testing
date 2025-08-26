/**
 * Video URL Optimization Performance Tests
 * 
 * Tests the performance improvements for video URL enhancement operations
 */

import { VideoEnhancementCache } from '../src/utils/videoEnhancementCache';
import { fixVideoUrl, fixMultipleVideoUrls, getCacheStats, clearBaseUrlCache } from '../src/utils/videoUrlFixer';
import { videoUrlErrorHandler, safeEnhanceVideo } from '../src/utils/videoUrlErrorHandler';
import { VideoFile } from '../src/services/types';

describe('Video URL Optimization Performance Tests', () => {
  let cache: VideoEnhancementCache;
  
  beforeEach(() => {
    cache = new VideoEnhancementCache();
    clearBaseUrlCache();
    videoUrlErrorHandler.clearErrors();
  });

  describe('VideoEnhancementCache', () => {
    it('should cache and retrieve video enhancements efficiently', () => {
      const mockVideo: VideoFile = {
        id: 'test-video-1',
        filename: 'test.mp4',
        url: 'http://localhost:8000/uploads/test.mp4',
        originalName: 'test.mp4',
        fileSize: 1024,
        createdAt: new Date().toISOString(),
        uploadedAt: new Date().toISOString(),
        processingStatus: 'completed',
        groundTruthGenerated: false,
        detectionCount: 0
      };

      // Test cache miss
      expect(cache.get('test-video-1')).toBeNull();
      
      // Test cache set and hit
      cache.set('test-video-1', mockVideo);
      const cached = cache.get('test-video-1');
      expect(cached).toBeTruthy();
      expect(cached?.id).toBe('test-video-1');
      expect(cached?.filename).toBe('test.mp4');
    });

    it('should provide accurate cache statistics', () => {
      const mockVideo: VideoFile = {
        id: 'test-video-1',
        filename: 'test.mp4',
        url: 'http://155.138.239.131:8000/uploads/test.mp4',
        originalName: 'test.mp4',
        fileSize: 1024,
        createdAt: new Date().toISOString(),
        uploadedAt: new Date().toISOString(),
        processingStatus: 'completed',
        groundTruthGenerated: false,
        detectionCount: 0
      };

      // Generate cache hits and misses
      cache.get('non-existent'); // miss
      cache.set('test-video-1', mockVideo);
      cache.get('test-video-1'); // hit
      cache.get('test-video-1'); // hit

      const stats = cache.getStats();
      expect(stats.hits).toBe(2);
      expect(stats.misses).toBe(1);
      expect(stats.totalRequests).toBe(3);
      expect(stats.hitRate).toBeCloseTo(66.67, 1);
    });

    it('should handle LRU eviction properly', () => {
      const smallCache = new VideoEnhancementCache(2); // Max 2 items
      
      const video1: VideoFile = { id: '1', filename: 'test1.mp4', url: 'http://test.com/1', originalName: 'test1.mp4', fileSize: 1024, createdAt: new Date().toISOString(), uploadedAt: new Date().toISOString(), processingStatus: 'completed', groundTruthGenerated: false, detectionCount: 0 };
      const video2: VideoFile = { id: '2', filename: 'test2.mp4', url: 'http://test.com/2', originalName: 'test2.mp4', fileSize: 1024, createdAt: new Date().toISOString(), uploadedAt: new Date().toISOString(), processingStatus: 'completed', groundTruthGenerated: false, detectionCount: 0 };
      const video3: VideoFile = { id: '3', filename: 'test3.mp4', url: 'http://test.com/3', originalName: 'test3.mp4', fileSize: 1024, createdAt: new Date().toISOString(), uploadedAt: new Date().toISOString(), processingStatus: 'completed', groundTruthGenerated: false, detectionCount: 0 };

      smallCache.set('1', video1);
      smallCache.set('2', video2);
      smallCache.set('3', video3); // Should evict '1'

      expect(smallCache.get('1')).toBeNull(); // Evicted
      expect(smallCache.get('2')).toBeTruthy(); // Still there
      expect(smallCache.get('3')).toBeTruthy(); // Still there
    });
  });

  describe('Optimized videoUrlFixer', () => {
    it('should cache base URL configuration', () => {
      const start1 = performance.now();
      const url1 = fixVideoUrl('test.mp4');
      const end1 = performance.now();

      const start2 = performance.now();
      const url2 = fixVideoUrl('test2.mp4'); // Should use cached config
      const end2 = performance.now();

      expect(url1).toContain('155.138.239.131');
      expect(url2).toContain('155.138.239.131');
      
      // Second call should be faster (cached config)
      expect(end2 - start2).toBeLessThanOrEqual(end1 - start1);
    });

    it('should process multiple videos efficiently', () => {
      const testVideos = Array.from({ length: 100 }, (_, i) => ({
        id: `video-${i}`,
        filename: `test-${i}.mp4`,
        url: i % 3 === 0 ? `http://localhost:8000/uploads/test-${i}.mp4` : `test-${i}.mp4`
      }));

      const start = performance.now();
      fixMultipleVideoUrls(testVideos, { debug: false });
      const end = performance.now();

      const processingTime = end - start;
      expect(processingTime).toBeLessThan(100); // Should complete in under 100ms

      // Verify URLs were fixed correctly
      testVideos.forEach(video => {
        expect(video.url).toContain('155.138.239.131');
      });
    });

    it('should skip duplicate videos in batch processing', () => {
      const testVideos = [
        { id: 'video-1', filename: 'test.mp4', url: 'http://localhost:8000/test.mp4' },
        { id: 'video-1', filename: 'test.mp4', url: 'http://localhost:8000/test.mp4' }, // Duplicate
        { id: 'video-2', filename: 'test2.mp4', url: 'http://localhost:8000/test2.mp4' }
      ];

      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      fixMultipleVideoUrls(testVideos, { debug: true });

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Skipping duplicate video in batch')
      );

      consoleSpy.mockRestore();
    });

    it('should provide cache statistics', () => {
      fixVideoUrl('test1.mp4'); // This should populate the cache
      const stats = getCacheStats();
      
      expect(stats).toHaveProperty('hasCachedUrl');
      expect(stats).toHaveProperty('cacheAge');
      expect(stats).toHaveProperty('cacheTtl');
    });
  });

  describe('Error Handling and Recovery', () => {
    it('should handle enhancement errors gracefully', () => {
      const badVideo = {
        id: 'bad-video',
        // Missing required fields to trigger error
      };

      const mockEnhancer = jest.fn().mockImplementation(() => {
        throw new Error('Enhancement failed');
      });

      const result = safeEnhanceVideo(badVideo, mockEnhancer, {
        fallbackToId: true,
        skipOnError: false
      });

      expect(result).toBeTruthy(); // Should recover with fallback
      expect(result?.url).toContain('bad-video'); // Should use ID as fallback
    });

    it('should track error statistics', () => {
      const badVideo = { id: 'error-video' };
      const mockEnhancer = jest.fn().mockImplementation(() => {
        throw new TypeError('Parse error');
      });

      safeEnhanceVideo(badVideo, mockEnhancer);
      
      const stats = videoUrlErrorHandler.getErrorStats();
      expect(stats.totalHistoryErrors).toBeGreaterThan(0);
      expect(stats.errorsByType).toHaveProperty('PARSE_ERROR');
    });

    it('should identify problematic videos', () => {
      const problematicVideo = { id: 'problematic-video' };
      const mockEnhancer = jest.fn().mockImplementation(() => {
        throw new Error('Repeated failure');
      });

      // Trigger multiple errors for the same video
      for (let i = 0; i < 4; i++) {
        safeEnhanceVideo(problematicVideo, mockEnhancer);
      }

      expect(videoUrlErrorHandler.isProblematicVideo('problematic-video')).toBe(true);
    });
  });

  describe('Performance Benchmarks', () => {
    it('should enhance large batches of videos efficiently', () => {
      const largeVideoSet = Array.from({ length: 1000 }, (_, i) => ({
        id: `video-${i}`,
        filename: `test-${i}.mp4`,
        url: `http://localhost:8000/uploads/test-${i}.mp4`,
        originalName: `test-${i}.mp4`,
        fileSize: 1024 * (i + 1),
        createdAt: new Date().toISOString(),
        uploadedAt: new Date().toISOString(),
        processingStatus: 'completed' as const,
        groundTruthGenerated: false,
        detectionCount: i % 10
      }));

      const cache = new VideoEnhancementCache();
      const mockApiService = {
        enhanceVideoData: jest.fn().mockImplementation((video: any) => ({
          ...video,
          url: video.url.replace('localhost', '155.138.239.131')
        })),
        batchEnhanceVideos: function(videos: any[]) {
          const start = performance.now();
          const results: VideoFile[] = [];
          const processedIds = new Set<string>();

          for (const video of videos) {
            if (processedIds.has(video.id)) continue;
            processedIds.add(video.id);

            const cached = cache.get(video.id);
            if (cached) {
              results.push(cached);
            } else {
              const enhanced = this.enhanceVideoData(video);
              cache.set(video.id, enhanced);
              results.push(enhanced);
            }
          }

          const end = performance.now();
          return { results, processingTime: end - start };
        }
      };

      const { results, processingTime } = mockApiService.batchEnhanceVideos(largeVideoSet);
      
      expect(results).toHaveLength(1000);
      expect(processingTime).toBeLessThan(500); // Should complete in under 500ms
      
      const stats = cache.getStats();
      expect(stats.size).toBe(1000);
      expect(stats.hitRate).toBe(0); // First run, no cache hits
    });

    it('should show significant performance improvement with caching', () => {
      const testVideos = Array.from({ length: 100 }, (_, i) => ({
        id: `video-${i % 10}`, // Only 10 unique videos, lots of duplicates
        filename: `test-${i % 10}.mp4`,
        url: `http://localhost:8000/uploads/test-${i % 10}.mp4`,
        originalName: `test-${i % 10}.mp4`,
        fileSize: 1024,
        createdAt: new Date().toISOString(),
        uploadedAt: new Date().toISOString(),
        processingStatus: 'completed' as const,
        groundTruthGenerated: false,
        detectionCount: 0
      }));

      const cache = new VideoEnhancementCache();
      let enhancementCalls = 0;

      const mockEnhancer = jest.fn().mockImplementation((video: any) => {
        enhancementCalls++;
        // Simulate some processing time
        const start = Date.now();
        while (Date.now() - start < 1) { /* busy wait */ }
        return {
          ...video,
          url: video.url.replace('localhost', '155.138.239.131')
        };
      });

      // Process videos with caching
      const start = performance.now();
      testVideos.forEach(video => {
        const cached = cache.get(video.id);
        if (!cached) {
          const enhanced = mockEnhancer(video);
          cache.set(video.id, enhanced);
        }
      });
      const end = performance.now();

      const processingTime = end - start;
      expect(enhancementCalls).toBe(10); // Only unique videos were processed
      expect(processingTime).toBeLessThan(50); // Should be much faster due to caching

      const stats = cache.getStats();
      expect(stats.hitRate).toBeGreaterThan(80); // High cache hit rate
    });
  });
});

describe('Integration Tests', () => {
  it('should work with the complete optimization stack', () => {
    const cache = new VideoEnhancementCache();
    const testVideo = {
      id: 'integration-test-video',
      filename: 'integration-test.mp4',
      url: 'http://localhost:8000/uploads/integration-test.mp4'
    };

    // Test the complete flow: enhancement -> caching -> retrieval -> error handling
    const enhancedVideo = safeEnhanceVideo(testVideo, (video: any) => {
      const fixed = { ...video };
      fixed.url = fixVideoUrl(video.url, video.filename, video.id);
      return {
        ...fixed,
        originalName: video.filename,
        fileSize: 1024,
        createdAt: new Date().toISOString(),
        uploadedAt: new Date().toISOString(),
        processingStatus: 'completed' as const,
        groundTruthGenerated: false,
        detectionCount: 0
      };
    });

    expect(enhancedVideo).toBeTruthy();
    expect(enhancedVideo?.url).toContain('155.138.239.131');
    expect(enhancedVideo?.url).not.toContain('localhost');

    // Test caching
    cache.set(testVideo.id, enhancedVideo!);
    const cached = cache.get(testVideo.id);
    expect(cached).toEqual(enhancedVideo);

    // Test error stats
    const errorStats = videoUrlErrorHandler.getErrorStats();
    expect(errorStats).toHaveProperty('totalRecentErrors');
  });
});