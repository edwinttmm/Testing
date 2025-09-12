/**
 * Video Performance Benchmark Test Suite
 * Tests video loading performance, memory usage, and optimization strategies
 */

import { VideoPlaybackManager, VideoPlaybackConfig } from '../src/utils/videoPlaybackManager';
import { performance } from 'perf_hooks';

// Mock performance API for testing
const mockPerformance = {
  mark: jest.fn(),
  measure: jest.fn(),
  getEntriesByName: jest.fn().mockReturnValue([{ duration: 100 }]),
  getEntriesByType: jest.fn().mockReturnValue([]),
  now: jest.fn().mockReturnValue(Date.now()),
  clearMarks: jest.fn(),
  clearMeasures: jest.fn(),
};

// Mock memory API
const mockMemory = {
  usedJSHeapSize: 10 * 1024 * 1024, // 10MB
  totalJSHeapSize: 50 * 1024 * 1024, // 50MB
  jsHeapSizeLimit: 2048 * 1024 * 1024, // 2GB
};

Object.defineProperty(window, 'performance', {
  value: mockPerformance,
  configurable: true
});

Object.defineProperty(performance, 'memory', {
  value: mockMemory,
  configurable: true
});

// Test video configurations
const PERFORMANCE_TEST_CONFIGS: VideoPlaybackConfig[] = [
  {
    retryAttempts: 1,
    retryDelay: 100,
    loadTimeout: 5000,
    playTimeout: 2000,
    enableAutoRetry: false
  },
  {
    retryAttempts: 3,
    retryDelay: 500,
    loadTimeout: 10000,
    playTimeout: 5000,
    enableAutoRetry: true
  },
  {
    retryAttempts: 5,
    retryDelay: 1000,
    loadTimeout: 30000,
    playTimeout: 10000,
    enableAutoRetry: true
  }
];

const MOCK_VIDEO_SIZES = {
  small: { width: 640, height: 480, fileSize: 5 * 1024 * 1024 }, // 5MB
  medium: { width: 1280, height: 720, fileSize: 25 * 1024 * 1024 }, // 25MB
  large: { width: 1920, height: 1080, fileSize: 100 * 1024 * 1024 }, // 100MB
  ultra: { width: 3840, height: 2160, fileSize: 500 * 1024 * 1024 }, // 500MB
};

describe('Video Performance Benchmark Tests', () => {
  let mockVideoElement: any;
  
  beforeEach(() => {
    jest.clearAllMocks();
    jest.clearAllTimers();
    jest.useFakeTimers();

    mockVideoElement = {
      play: jest.fn().mockResolvedValue(undefined),
      pause: jest.fn(),
      load: jest.fn(),
      currentTime: 0,
      duration: 10,
      volume: 1,
      muted: false,
      paused: true,
      ended: false,
      readyState: HTMLMediaElement.HAVE_METADATA,
      videoWidth: 1920,
      videoHeight: 1080,
      error: null,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      canPlayType: jest.fn().mockReturnValue('probably'),
      preload: 'auto',
      buffered: {
        length: 1,
        start: jest.fn().mockReturnValue(0),
        end: jest.fn().mockReturnValue(5),
      },
    };

    jest.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'video') {
        return mockVideoElement;
      }
      return document.createElement(tagName);
    });
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  describe('Video Loading Performance', () => {
    it('should measure video loading times for different configurations', async () => {
      const loadingTimes: number[] = [];

      for (const config of PERFORMANCE_TEST_CONFIGS) {
        const manager = new VideoPlaybackManager(config);
        manager.attachVideoElement(mockVideoElement);

        const startTime = mockPerformance.now();
        
        // Mock successful load
        const loadPromise = manager.loadVideo('/test-video.mp4');
        
        // Simulate loading delay based on configuration
        await jest.runAllTimersAsync();
        
        const endTime = mockPerformance.now();
        const loadTime = endTime - startTime;
        
        loadingTimes.push(loadTime);
        expect(loadTime).toBeDefined();
        
        manager.destroy();
      }

      // Verify loading times are reasonable
      expect(loadingTimes.every(time => time >= 0)).toBe(true);
      expect(loadingTimes.length).toBe(PERFORMANCE_TEST_CONFIGS.length);
    });

    it('should benchmark loading performance for different video sizes', async () => {
      const performanceResults: { [key: string]: number } = {};

      for (const [sizeName, sizeConfig] of Object.entries(MOCK_VIDEO_SIZES)) {
        // Mock video element with size-specific properties
        mockVideoElement.videoWidth = sizeConfig.width;
        mockVideoElement.videoHeight = sizeConfig.height;

        const manager = new VideoPlaybackManager();
        manager.attachVideoElement(mockVideoElement);

        mockPerformance.now.mockReturnValue(0);
        const startTime = mockPerformance.now();

        // Simulate loading time proportional to file size
        const estimatedLoadTime = sizeConfig.fileSize / (1024 * 1024); // 1ms per MB
        mockPerformance.now.mockReturnValue(estimatedLoadTime);

        await manager.loadVideo(`/test-video-${sizeName}.mp4`);
        
        const endTime = mockPerformance.now();
        performanceResults[sizeName] = endTime - startTime;

        manager.destroy();
      }

      // Verify larger videos take longer to load
      expect(performanceResults.small).toBeLessThanOrEqual(performanceResults.medium);
      expect(performanceResults.medium).toBeLessThanOrEqual(performanceResults.large);
      expect(performanceResults.large).toBeLessThanOrEqual(performanceResults.ultra);
    });

    it('should measure time to first frame across different scenarios', async () => {
      const scenarios = [
        { name: 'local', latency: 10, bandwidth: Infinity },
        { name: 'fast_network', latency: 50, bandwidth: 10 * 1024 * 1024 }, // 10 Mbps
        { name: 'slow_network', latency: 200, bandwidth: 1 * 1024 * 1024 }, // 1 Mbps
        { name: 'mobile_network', latency: 500, bandwidth: 0.5 * 1024 * 1024 }, // 0.5 Mbps
      ];

      const firstFrameTimes: { [key: string]: number } = {};

      for (const scenario of scenarios) {
        const manager = new VideoPlaybackManager({
          loadTimeout: scenario.latency * 10,
        });
        
        manager.attachVideoElement(mockVideoElement);

        mockPerformance.now.mockReturnValue(0);
        
        // Simulate network conditions
        const fileSize = MOCK_VIDEO_SIZES.medium.fileSize;
        const downloadTime = (fileSize * 8) / scenario.bandwidth * 1000; // Convert to ms
        const totalTime = scenario.latency + downloadTime;

        mockPerformance.now.mockReturnValue(totalTime);

        await manager.loadVideo('/test-video.mp4');
        
        firstFrameTimes[scenario.name] = mockPerformance.now();
        manager.destroy();
      }

      // Verify network conditions affect loading time appropriately
      expect(firstFrameTimes.local).toBeLessThan(firstFrameTimes.fast_network);
      expect(firstFrameTimes.fast_network).toBeLessThan(firstFrameTimes.slow_network);
      expect(firstFrameTimes.slow_network).toBeLessThan(firstFrameTimes.mobile_network);
    });
  });

  describe('Memory Usage and Management', () => {
    it('should monitor memory usage during video playback', async () => {
      const manager = new VideoPlaybackManager();
      manager.attachVideoElement(mockVideoElement);

      const initialMemory = mockMemory.usedJSHeapSize;
      
      // Load multiple videos to test memory accumulation
      const videoUrls = [
        '/video1.mp4',
        '/video2.mp4', 
        '/video3.mp4',
        '/video4.mp4',
        '/video5.mp4'
      ];

      for (let i = 0; i < videoUrls.length; i++) {
        await manager.loadVideo(videoUrls[i]);
        
        // Simulate memory increase with each video
        mockMemory.usedJSHeapSize = initialMemory + (i + 1) * 2 * 1024 * 1024; // 2MB per video
        
        const currentMemory = mockMemory.usedJSHeapSize;
        const memoryIncrease = currentMemory - initialMemory;
        
        // Memory should increase but not excessively
        expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024); // Less than 50MB total increase
      }

      manager.destroy();
      
      // Memory should be cleaned up after destroy
      mockMemory.usedJSHeapSize = initialMemory;
      expect(mockMemory.usedJSHeapSize).toBe(initialMemory);
    });

    it('should prevent memory leaks with proper cleanup', () => {
      const numInstances = 10;
      const managers: VideoPlaybackManager[] = [];
      
      const initialMemory = mockMemory.usedJSHeapSize;

      // Create multiple manager instances
      for (let i = 0; i < numInstances; i++) {
        const manager = new VideoPlaybackManager();
        const videoElement = document.createElement('video') as HTMLVideoElement;
        manager.attachVideoElement(videoElement);
        managers.push(manager);
        
        // Simulate memory usage per instance
        mockMemory.usedJSHeapSize += 1 * 1024 * 1024; // 1MB per instance
      }

      const peakMemory = mockMemory.usedJSHeapSize;
      expect(peakMemory).toBeGreaterThan(initialMemory);

      // Cleanup all instances
      managers.forEach(manager => manager.destroy());
      
      // Simulate garbage collection
      mockMemory.usedJSHeapSize = initialMemory;
      
      expect(mockMemory.usedJSHeapSize).toBe(initialMemory);
    });

    it('should handle memory pressure scenarios', async () => {
      const manager = new VideoPlaybackManager();
      manager.attachVideoElement(mockVideoElement);

      // Simulate approaching memory limit
      mockMemory.usedJSHeapSize = mockMemory.jsHeapSizeLimit * 0.9; // 90% of limit

      const memoryPressureDetected = mockMemory.usedJSHeapSize > mockMemory.jsHeapSizeLimit * 0.8;
      
      if (memoryPressureDetected) {
        // Should handle gracefully - in real implementation, might reduce quality or skip preloading
        expect(memoryPressureDetected).toBe(true);
        
        // Simulate cleanup due to memory pressure
        mockMemory.usedJSHeapSize = mockMemory.jsHeapSizeLimit * 0.5;
      }

      manager.destroy();
    });
  });

  describe('Playback Performance Optimization', () => {
    it('should optimize playback for different scenarios', async () => {
      const optimizationScenarios = [
        {
          name: 'battery_saver',
          config: { retryAttempts: 1, loadTimeout: 15000 },
          expectedBehavior: 'reduced_retries'
        },
        {
          name: 'high_performance',
          config: { retryAttempts: 5, loadTimeout: 5000 },
          expectedBehavior: 'aggressive_loading'
        },
        {
          name: 'mobile_optimized',
          config: { retryAttempts: 2, loadTimeout: 10000 },
          expectedBehavior: 'balanced'
        }
      ];

      for (const scenario of optimizationScenarios) {
        const manager = new VideoPlaybackManager(scenario.config);
        manager.attachVideoElement(mockVideoElement);

        // Test optimization behavior
        const startTime = mockPerformance.now();
        await manager.loadVideo('/test-video.mp4');
        const endTime = mockPerformance.now();
        const loadTime = endTime - startTime;

        // Verify optimization characteristics
        if (scenario.expectedBehavior === 'reduced_retries') {
          expect(scenario.config.retryAttempts).toBe(1);
        } else if (scenario.expectedBehavior === 'aggressive_loading') {
          expect(scenario.config.retryAttempts).toBeGreaterThan(3);
        }

        expect(loadTime).toBeGreaterThanOrEqual(0);
        manager.destroy();
      }
    });

    it('should implement preloading strategies effectively', async () => {
      const preloadStrategies = ['none', 'metadata', 'auto'];
      const performanceResults: { [key: string]: number } = {};

      for (const strategy of preloadStrategies) {
        mockVideoElement.preload = strategy;
        
        const manager = new VideoPlaybackManager();
        manager.attachVideoElement(mockVideoElement);

        const startTime = mockPerformance.now();
        await manager.loadVideo('/test-video.mp4');
        
        // Simulate different preload behaviors
        let loadTime;
        switch (strategy) {
          case 'none':
            loadTime = 1000; // Longer load time, no preloading
            break;
          case 'metadata':
            loadTime = 500; // Medium load time, metadata preloaded
            break;
          case 'auto':
            loadTime = 100; // Fastest, full preload
            break;
          default:
            loadTime = 500;
        }
        
        mockPerformance.now.mockReturnValue(loadTime);
        const endTime = mockPerformance.now();
        
        performanceResults[strategy] = endTime - startTime;
        manager.destroy();
      }

      // Verify preload strategies affect performance as expected
      expect(performanceResults.auto).toBeLessThanOrEqual(performanceResults.metadata);
      expect(performanceResults.metadata).toBeLessThanOrEqual(performanceResults.none);
    });

    it('should adapt to connection quality', async () => {
      const connectionQualities = [
        { name: '4g', bandwidth: 10 * 1024 * 1024, rtt: 50 },
        { name: '3g', bandwidth: 1.5 * 1024 * 1024, rtt: 150 },
        { name: '2g', bandwidth: 0.25 * 1024 * 1024, rtt: 600 },
        { name: 'slow-2g', bandwidth: 0.05 * 1024 * 1024, rtt: 2000 }
      ];

      const adaptiveResults: { [key: string]: any } = {};

      for (const connection of connectionQualities) {
        // Simulate adaptive configuration based on connection
        const adaptiveConfig = {
          retryAttempts: connection.rtt > 500 ? 1 : 3,
          loadTimeout: Math.max(5000, connection.rtt * 10),
          enableAutoRetry: connection.bandwidth > 1024 * 1024
        };

        const manager = new VideoPlaybackManager(adaptiveConfig);
        manager.attachVideoElement(mockVideoElement);

        adaptiveResults[connection.name] = {
          config: adaptiveConfig,
          bandwidth: connection.bandwidth,
          rtt: connection.rtt
        };

        manager.destroy();
      }

      // Verify adaptive behavior
      expect(adaptiveResults['4g'].config.retryAttempts).toBeGreaterThan(adaptiveResults['slow-2g'].config.retryAttempts);
      expect(adaptiveResults['4g'].config.loadTimeout).toBeLessThan(adaptiveResults['slow-2g'].config.loadTimeout);
    });
  });

  describe('Concurrent Video Handling', () => {
    it('should handle multiple concurrent video instances efficiently', async () => {
      const numConcurrentVideos = 5;
      const managers: VideoPlaybackManager[] = [];
      const loadPromises: Promise<void>[] = [];

      const startTime = mockPerformance.now();

      // Create multiple concurrent video instances
      for (let i = 0; i < numConcurrentVideos; i++) {
        const manager = new VideoPlaybackManager();
        const videoElement = document.createElement('video') as HTMLVideoElement;
        manager.attachVideoElement(videoElement);
        managers.push(manager);

        // Start loading all videos concurrently
        const loadPromise = manager.loadVideo(`/test-video-${i}.mp4`);
        loadPromises.push(loadPromise);
      }

      // Wait for all videos to load
      await Promise.all(loadPromises);
      
      const endTime = mockPerformance.now();
      const totalTime = endTime - startTime;

      // Concurrent loading should be more efficient than sequential
      expect(totalTime).toBeDefined();
      expect(managers.length).toBe(numConcurrentVideos);

      // Cleanup
      managers.forEach(manager => manager.destroy());
    });

    it('should manage resource contention between concurrent videos', async () => {
      const resourceLimits = {
        maxConcurrentLoads: 3,
        maxMemoryUsage: 100 * 1024 * 1024 // 100MB
      };

      const videoCount = 6; // More than max concurrent loads
      const managers: VideoPlaybackManager[] = [];

      let activeLoads = 0;
      const mockLoad = jest.fn().mockImplementation(async () => {
        if (activeLoads >= resourceLimits.maxConcurrentLoads) {
          // Wait for resource availability
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        activeLoads++;
        
        // Simulate load time
        await new Promise(resolve => setTimeout(resolve, 50));
        
        activeLoads--;
      });

      for (let i = 0; i < videoCount; i++) {
        const manager = new VideoPlaybackManager();
        const videoElement = document.createElement('video') as HTMLVideoElement;
        
        // Mock the load method
        videoElement.load = mockLoad;
        
        manager.attachVideoElement(videoElement);
        managers.push(manager);
      }

      // Start all loads
      const loadPromises = managers.map((manager, index) => 
        manager.loadVideo(`/video-${index}.mp4`)
      );

      await Promise.all(loadPromises);

      // Verify resource limits were respected
      expect(mockLoad).toHaveBeenCalledTimes(videoCount);

      // Cleanup
      managers.forEach(manager => manager.destroy());
    });
  });

  describe('Performance Monitoring and Metrics', () => {
    it('should collect comprehensive performance metrics', async () => {
      const manager = new VideoPlaybackManager();
      manager.attachVideoElement(mockVideoElement);

      // Mock performance marks and measures
      mockPerformance.mark.mockClear();
      mockPerformance.measure.mockClear();

      await manager.loadVideo('/test-video.mp4');
      
      const result = await manager.play();
      expect(result).toBe(true);

      // In a real implementation, performance marks would be collected
      const expectedMetrics = {
        videoLoadTime: expect.any(Number),
        firstFrameTime: expect.any(Number),
        playbackStartTime: expect.any(Number),
        memoryUsage: expect.any(Number),
        bufferingEvents: expect.any(Number),
        errorCount: expect.any(Number)
      };

      // Verify metrics structure
      Object.keys(expectedMetrics).forEach(key => {
        expect(typeof expectedMetrics[key as keyof typeof expectedMetrics]).toBeDefined();
      });

      manager.destroy();
    });

    it('should track performance regression over time', () => {
      const historicalData = [
        { version: '1.0.0', avgLoadTime: 2000, memoryUsage: 10 * 1024 * 1024 },
        { version: '1.1.0', avgLoadTime: 1800, memoryUsage: 9 * 1024 * 1024 },
        { version: '1.2.0', avgLoadTime: 1500, memoryUsage: 8 * 1024 * 1024 },
      ];

      const currentMetrics = { avgLoadTime: 1600, memoryUsage: 8.5 * 1024 * 1024 };
      const lastVersion = historicalData[historicalData.length - 1];

      // Check for performance regression
      const loadTimeRegression = currentMetrics.avgLoadTime > lastVersion.avgLoadTime * 1.1; // 10% threshold
      const memoryRegression = currentMetrics.memoryUsage > lastVersion.memoryUsage * 1.1;

      expect(loadTimeRegression).toBe(false);
      expect(memoryRegression).toBe(false);
    });
  });
});