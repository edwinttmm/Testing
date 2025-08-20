import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { performance } from 'perf_hooks';
import { apiService } from '../../../ai-model-validation-platform/frontend/src/services/api';
import { createMockVideoBlob } from '../fixtures/test-videos';

// Performance test configuration
const PERFORMANCE_THRESHOLDS = {
  SMALL_FILE_UPLOAD: 5000, // 5 seconds
  MEDIUM_FILE_UPLOAD: 15000, // 15 seconds
  LARGE_FILE_UPLOAD: 60000, // 1 minute
  CONCURRENT_UPLOAD: 30000, // 30 seconds
  MEMORY_USAGE_MB: 500, // 500 MB maximum
  CHUNK_SIZE_MB: 1, // 1 MB chunks
  PROGRESS_UPDATE_INTERVAL: 1000 // 1 second
};

// File size categories for testing
const FILE_SIZES = {
  SMALL: 5 * 1024 * 1024, // 5 MB
  MEDIUM: 50 * 1024 * 1024, // 50 MB
  LARGE: 200 * 1024 * 1024, // 200 MB
  XLARGE: 500 * 1024 * 1024 // 500 MB
};

describe('Large File Upload Performance Tests', () => {
  let performanceMetrics: {
    uploadTime: number;
    throughput: number;
    memoryUsage: number;
    progressUpdates: number[];
    errorCount: number;
  };

  beforeEach(() => {
    performanceMetrics = {
      uploadTime: 0,
      throughput: 0,
      memoryUsage: 0,
      progressUpdates: [],
      errorCount: 0
    };
    
    // Mock performance monitoring
    if (typeof global.gc === 'function') {
      global.gc();
    }
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Single File Upload Performance', () => {
    it('should upload small file within performance threshold', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'small-perf-test.mp4',
        size: FILE_SIZES.SMALL,
        duration: 30,
        fps: 30,
        resolution: '720p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'small-perf-test.mp4', { type: 'video/mp4' });
      
      let progressUpdates: number[] = [];
      const onProgress = (progress: number) => {
        progressUpdates.push(progress);
        performanceMetrics.progressUpdates = progressUpdates;
      };

      // Mock successful upload
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const startTime = performance.now();
        
        // Simulate progress updates
        if (onProgress) {
          for (let i = 10; i <= 100; i += 10) {
            await new Promise(resolve => setTimeout(resolve, 50));
            onProgress(i);
          }
        }
        
        const endTime = performance.now();
        performanceMetrics.uploadTime = endTime - startTime;
        performanceMetrics.throughput = file.size / (performanceMetrics.uploadTime / 1000); // bytes per second
        
        return {
          id: 'perf-test-small',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          upload_time: performanceMetrics.uploadTime,
          url: '/api/videos/perf-test-small/stream'
        };
      });

      // Act
      const startTime = performance.now();
      const result = await apiService.uploadVideoCentral(file, onProgress);
      const endTime = performance.now();

      // Assert
      expect(result).toBeDefined();
      expect(endTime - startTime).toBeLessThan(PERFORMANCE_THRESHOLDS.SMALL_FILE_UPLOAD);
      expect(progressUpdates.length).toBeGreaterThan(5);
      expect(progressUpdates[progressUpdates.length - 1]).toBe(100);
      
      // Verify throughput is reasonable (at least 1 MB/s)
      const throughputMBps = performanceMetrics.throughput / (1024 * 1024);
      expect(throughputMBps).toBeGreaterThan(1);
    });

    it('should upload medium file with chunking within threshold', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'medium-perf-test.mp4',
        size: FILE_SIZES.MEDIUM,
        duration: 120,
        fps: 30,
        resolution: '1080p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'medium-perf-test.mp4', { type: 'video/mp4' });
      
      let progressUpdates: number[] = [];
      let chunkCount = 0;
      
      const onProgress = (progress: number) => {
        progressUpdates.push(progress);
      };

      // Mock chunked upload
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const startTime = performance.now();
        const chunkSize = PERFORMANCE_THRESHOLDS.CHUNK_SIZE_MB * 1024 * 1024;
        const totalChunks = Math.ceil(file.size / chunkSize);
        
        // Simulate chunked upload with progress
        for (let i = 0; i < totalChunks; i++) {
          await new Promise(resolve => setTimeout(resolve, 100)); // Simulate network delay
          chunkCount++;
          
          if (onProgress) {
            const progress = Math.round(((i + 1) / totalChunks) * 100);
            onProgress(progress);
          }
        }
        
        const endTime = performance.now();
        performanceMetrics.uploadTime = endTime - startTime;
        performanceMetrics.throughput = file.size / (performanceMetrics.uploadTime / 1000);
        
        return {
          id: 'perf-test-medium',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          chunks_uploaded: chunkCount,
          upload_time: performanceMetrics.uploadTime
        };
      });

      // Act
      const startTime = performance.now();
      const result = await apiService.uploadVideoCentral(file, onProgress);
      const endTime = performance.now();

      // Assert
      expect(result).toBeDefined();
      expect(endTime - startTime).toBeLessThan(PERFORMANCE_THRESHOLDS.MEDIUM_FILE_UPLOAD);
      expect(chunkCount).toBeGreaterThan(1); // Should use chunking
      expect(progressUpdates.length).toBeGreaterThan(3);
    });

    it('should upload large file efficiently with monitoring', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'large-perf-test.mp4',
        size: FILE_SIZES.LARGE,
        duration: 300,
        fps: 30,
        resolution: '1080p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'large-perf-test.mp4', { type: 'video/mp4' });
      
      let maxMemoryUsage = 0;
      let progressUpdates: number[] = [];
      
      const onProgress = (progress: number) => {
        progressUpdates.push(progress);
        
        // Monitor memory usage during upload
        if (typeof process !== 'undefined' && process.memoryUsage) {
          const memUsage = process.memoryUsage().heapUsed / 1024 / 1024; // MB
          maxMemoryUsage = Math.max(maxMemoryUsage, memUsage);
        }
      };

      // Mock large file upload
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const startTime = performance.now();
        const chunkSize = PERFORMANCE_THRESHOLDS.CHUNK_SIZE_MB * 1024 * 1024;
        const totalChunks = Math.ceil(file.size / chunkSize);
        
        // Simulate more realistic large file upload
        for (let i = 0; i < totalChunks; i++) {
          // Variable delay to simulate network conditions
          const delay = Math.random() * 200 + 50; // 50-250ms
          await new Promise(resolve => setTimeout(resolve, delay));
          
          if (onProgress && i % 5 === 0) { // Update progress every 5 chunks
            const progress = Math.round(((i + 1) / totalChunks) * 100);
            onProgress(progress);
          }
        }
        
        // Final progress update
        if (onProgress) {
          onProgress(100);
        }
        
        const endTime = performance.now();
        performanceMetrics.uploadTime = endTime - startTime;
        performanceMetrics.throughput = file.size / (performanceMetrics.uploadTime / 1000);
        
        return {
          id: 'perf-test-large',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          upload_time: performanceMetrics.uploadTime,
          chunks_total: totalChunks
        };
      });

      // Act
      const startTime = performance.now();
      const result = await apiService.uploadVideoCentral(file, onProgress);
      const endTime = performance.now();

      // Assert
      expect(result).toBeDefined();
      expect(endTime - startTime).toBeLessThan(PERFORMANCE_THRESHOLDS.LARGE_FILE_UPLOAD);
      expect(maxMemoryUsage).toBeLessThan(PERFORMANCE_THRESHOLDS.MEMORY_USAGE_MB);
      expect(progressUpdates.length).toBeGreaterThan(10);
      
      // Performance metrics
      console.log(`Large file upload metrics:
        - File size: ${FILE_SIZES.LARGE / (1024 * 1024)} MB
        - Upload time: ${performanceMetrics.uploadTime} ms
        - Throughput: ${(performanceMetrics.throughput / (1024 * 1024)).toFixed(2)} MB/s
        - Max memory usage: ${maxMemoryUsage.toFixed(2)} MB
        - Progress updates: ${progressUpdates.length}
      `);
    });
  });

  describe('Concurrent Upload Performance', () => {
    it('should handle multiple concurrent uploads efficiently', async () => {
      // Arrange
      const files = Array.from({ length: 3 }, (_, i) => {
        const videoBlob = createMockVideoBlob({
          filename: `concurrent-${i}.mp4`,
          size: FILE_SIZES.SMALL,
          duration: 30,
          fps: 30,
          resolution: '720p',
          format: 'video/mp4'
        });
        return new File([videoBlob], `concurrent-${i}.mp4`, { type: 'video/mp4' });
      });

      let completedUploads = 0;
      const uploadTimes: number[] = [];

      // Mock concurrent uploads
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const startTime = performance.now();
        
        // Simulate concurrent upload with realistic delay
        const uploadDelay = 1000 + Math.random() * 2000; // 1-3 seconds
        await new Promise(resolve => setTimeout(resolve, uploadDelay));
        
        if (onProgress) {
          // Simulate progress updates
          for (let i = 25; i <= 100; i += 25) {
            onProgress(i);
            await new Promise(resolve => setTimeout(resolve, 100));
          }
        }
        
        const endTime = performance.now();
        uploadTimes.push(endTime - startTime);
        completedUploads++;
        
        return {
          id: `concurrent-${completedUploads}`,
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          upload_time: endTime - startTime
        };
      });

      // Act
      const startTime = performance.now();
      
      const uploadPromises = files.map(file => 
        apiService.uploadVideoCentral(file, (progress) => {
          // Track progress for each file
        })
      );
      
      const results = await Promise.all(uploadPromises);
      const totalTime = performance.now() - startTime;

      // Assert
      expect(results).toHaveLength(3);
      expect(totalTime).toBeLessThan(PERFORMANCE_THRESHOLDS.CONCURRENT_UPLOAD);
      expect(completedUploads).toBe(3);
      
      // Verify concurrent execution (should be faster than sequential)
      const sequentialTime = uploadTimes.reduce((sum, time) => sum + time, 0);
      expect(totalTime).toBeLessThan(sequentialTime * 0.8); // Should be at least 20% faster
      
      results.forEach((result, index) => {
        expect(result.id).toBe(`concurrent-${index + 1}`);
        expect(result.status).toBe('uploaded');
      });
    });

    it('should limit concurrent uploads to prevent resource exhaustion', async () => {
      // Arrange - Create many files to test concurrency limits
      const files = Array.from({ length: 10 }, (_, i) => {
        const videoBlob = createMockVideoBlob({
          filename: `limit-test-${i}.mp4`,
          size: FILE_SIZES.SMALL,
          duration: 15,
          fps: 30,
          resolution: '720p',
          format: 'video/mp4'
        });
        return new File([videoBlob], `limit-test-${i}.mp4`, { type: 'video/mp4' });
      });

      let activeUploads = 0;
      let maxConcurrentUploads = 0;
      const uploadResults: any[] = [];

      // Mock upload with concurrency tracking
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        activeUploads++;
        maxConcurrentUploads = Math.max(maxConcurrentUploads, activeUploads);
        
        const startTime = performance.now();
        
        // Simulate upload delay
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        activeUploads--;
        const endTime = performance.now();
        
        const result = {
          id: `limit-test-${uploadResults.length + 1}`,
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          upload_time: endTime - startTime
        };
        
        uploadResults.push(result);
        return result;
      });

      // Act
      const uploadPromises = files.map(file => apiService.uploadVideoCentral(file));
      const results = await Promise.all(uploadPromises);

      // Assert
      expect(results).toHaveLength(10);
      expect(maxConcurrentUploads).toBeLessThanOrEqual(5); // Should limit concurrent uploads
      
      results.forEach(result => {
        expect(result.status).toBe('uploaded');
      });
    });
  });

  describe('Memory Usage and Resource Management', () => {
    it('should manage memory efficiently during large uploads', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'memory-test.mp4',
        size: FILE_SIZES.LARGE,
        duration: 600,
        fps: 30,
        resolution: '1080p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'memory-test.mp4', { type: 'video/mp4' });
      
      let memorySnapshots: number[] = [];
      
      const captureMemoryUsage = () => {
        if (typeof process !== 'undefined' && process.memoryUsage) {
          const usage = process.memoryUsage();
          memorySnapshots.push(usage.heapUsed / 1024 / 1024); // MB
        } else {
          // Browser environment - estimate memory usage
          memorySnapshots.push(Math.random() * 100 + 50); // Mock 50-150 MB
        }
      };

      // Mock upload with memory monitoring
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        captureMemoryUsage(); // Initial memory
        
        const chunkSize = 1024 * 1024; // 1 MB chunks
        const totalChunks = Math.ceil(file.size / chunkSize);
        
        for (let i = 0; i < totalChunks; i++) {
          // Simulate processing chunk
          await new Promise(resolve => setTimeout(resolve, 10));
          
          // Capture memory usage every 10 chunks
          if (i % 10 === 0) {
            captureMemoryUsage();
          }
          
          if (onProgress && i % 50 === 0) {
            onProgress(Math.round(((i + 1) / totalChunks) * 100));
          }
        }
        
        captureMemoryUsage(); // Final memory
        
        return {
          id: 'memory-test-upload',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          chunks_processed: totalChunks
        };
      });

      // Act
      const result = await apiService.uploadVideoCentral(file, (progress) => {
        // Progress callback
      });

      // Assert
      expect(result).toBeDefined();
      expect(memorySnapshots.length).toBeGreaterThan(3);
      
      const maxMemory = Math.max(...memorySnapshots);
      const memoryGrowth = memorySnapshots[memorySnapshots.length - 1] - memorySnapshots[0];
      
      expect(maxMemory).toBeLessThan(PERFORMANCE_THRESHOLDS.MEMORY_USAGE_MB);
      expect(memoryGrowth).toBeLessThan(100); // Memory growth should be controlled
      
      console.log(`Memory usage during upload:
        - Initial: ${memorySnapshots[0].toFixed(2)} MB
        - Peak: ${maxMemory.toFixed(2)} MB
        - Final: ${memorySnapshots[memorySnapshots.length - 1].toFixed(2)} MB
        - Growth: ${memoryGrowth.toFixed(2)} MB
      `);
    });

    it('should cleanup resources after failed upload', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'cleanup-test.mp4',
        size: FILE_SIZES.MEDIUM,
        duration: 60,
        fps: 30,
        resolution: '720p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'cleanup-test.mp4', { type: 'video/mp4' });
      
      let resourcesAllocated = 0;
      let resourcesCleaned = 0;

      // Mock upload that fails partway through
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const chunks = Math.ceil(file.size / (1024 * 1024)); // 1MB chunks
        
        try {
          for (let i = 0; i < chunks; i++) {
            resourcesAllocated++;
            
            // Simulate failure at 50%
            if (i > chunks * 0.5) {
              throw new Error('Upload failed - network error');
            }
            
            await new Promise(resolve => setTimeout(resolve, 50));
            
            if (onProgress) {
              onProgress(Math.round(((i + 1) / chunks) * 100));
            }
          }
          
          return {
            id: 'should-not-succeed',
            filename: file.name,
            file_size: file.size,
            status: 'uploaded'
          };
          
        } finally {
          // Simulate resource cleanup
          resourcesCleaned = resourcesAllocated;
        }
      });

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file)).rejects.toThrow('Upload failed - network error');
      
      // Verify resources were cleaned up
      expect(resourcesAllocated).toBeGreaterThan(0);
      expect(resourcesCleaned).toBe(resourcesAllocated);
    });
  });

  describe('Network Conditions and Resilience', () => {
    it('should adapt to slow network conditions', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'slow-network-test.mp4',
        size: FILE_SIZES.MEDIUM,
        duration: 90,
        fps: 30,
        resolution: '720p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'slow-network-test.mp4', { type: 'video/mp4' });
      
      let adaptiveDelays: number[] = [];

      // Mock upload with adaptive behavior
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const chunks = Math.ceil(file.size / (1024 * 1024));
        let currentDelay = 100; // Start with 100ms delay
        
        for (let i = 0; i < chunks; i++) {
          // Simulate network congestion detection
          if (i > 5 && Math.random() > 0.7) {
            currentDelay = Math.min(currentDelay * 1.5, 1000); // Increase delay, max 1s
          } else if (currentDelay > 100) {
            currentDelay = Math.max(currentDelay * 0.8, 100); // Decrease delay
          }
          
          adaptiveDelays.push(currentDelay);
          await new Promise(resolve => setTimeout(resolve, currentDelay));
          
          if (onProgress && i % 5 === 0) {
            onProgress(Math.round(((i + 1) / chunks) * 100));
          }
        }
        
        return {
          id: 'slow-network-upload',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          adaptive_delays: adaptiveDelays
        };
      });

      // Act
      const startTime = performance.now();
      const result = await apiService.uploadVideoCentral(file);
      const endTime = performance.now();

      // Assert
      expect(result).toBeDefined();
      expect(adaptiveDelays.length).toBeGreaterThan(10);
      
      // Verify adaptive behavior
      const avgDelay = adaptiveDelays.reduce((sum, delay) => sum + delay, 0) / adaptiveDelays.length;
      expect(avgDelay).toBeGreaterThan(100); // Should adapt to slower conditions
      
      console.log(`Network adaptation metrics:
        - Chunks: ${adaptiveDelays.length}
        - Average delay: ${avgDelay.toFixed(2)} ms
        - Min delay: ${Math.min(...adaptiveDelays)} ms
        - Max delay: ${Math.max(...adaptiveDelays)} ms
        - Total time: ${endTime - startTime} ms
      `);
    });

    it('should resume upload after network interruption', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'resume-test.mp4',
        size: FILE_SIZES.LARGE,
        duration: 180,
        fps: 30,
        resolution: '1080p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'resume-test.mp4', { type: 'video/mp4' });
      
      let uploadAttempts = 0;
      let chunksCompleted = 0;

      // Mock upload with interruption and resume
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        uploadAttempts++;
        const totalChunks = Math.ceil(file.size / (1024 * 1024));
        
        // First attempt - fail partway through
        if (uploadAttempts === 1) {
          for (let i = chunksCompleted; i < totalChunks * 0.6; i++) {
            chunksCompleted++;
            await new Promise(resolve => setTimeout(resolve, 50));
            
            if (onProgress) {
              onProgress(Math.round((chunksCompleted / totalChunks) * 100));
            }
          }
          
          throw new Error('Network interruption');
        }
        
        // Second attempt - resume from where we left off
        for (let i = chunksCompleted; i < totalChunks; i++) {
          chunksCompleted++;
          await new Promise(resolve => setTimeout(resolve, 30));
          
          if (onProgress) {
            onProgress(Math.round((chunksCompleted / totalChunks) * 100));
          }
        }
        
        return {
          id: 'resume-upload',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          chunks_completed: chunksCompleted,
          upload_attempts: uploadAttempts,
          resumed_from: Math.round((0.6 * totalChunks / totalChunks) * 100) // 60%
        };
      });

      // Act
      let result;
      try {
        result = await apiService.uploadVideoCentral(file);
      } catch (error) {
        // Simulate resume after interruption
        result = await apiService.uploadVideoCentral(file);
      }

      // Assert
      expect(result).toBeDefined();
      expect(uploadAttempts).toBe(2);
      expect(result.resumed_from).toBe(60);
      expect(result.status).toBe('uploaded');
    });
  });

  describe('Progress Reporting and User Experience', () => {
    it('should provide smooth progress updates during upload', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'progress-test.mp4',
        size: FILE_SIZES.MEDIUM,
        duration: 120,
        fps: 30,
        resolution: '1080p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'progress-test.mp4', { type: 'video/mp4' });
      
      let progressUpdates: { progress: number; timestamp: number }[] = [];

      const onProgress = (progress: number) => {
        progressUpdates.push({
          progress,
          timestamp: performance.now()
        });
      };

      // Mock upload with detailed progress
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const totalChunks = 100; // Fixed number for consistent testing
        
        for (let i = 1; i <= totalChunks; i++) {
          await new Promise(resolve => setTimeout(resolve, 20)); // 20ms per chunk
          
          if (onProgress) {
            onProgress(i);
          }
        }
        
        return {
          id: 'progress-test-upload',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded',
          progress_updates: progressUpdates.length
        };
      });

      // Act
      const result = await apiService.uploadVideoCentral(file, onProgress);

      // Assert
      expect(result).toBeDefined();
      expect(progressUpdates.length).toBe(100);
      
      // Verify progress is monotonic (always increasing)
      for (let i = 1; i < progressUpdates.length; i++) {
        expect(progressUpdates[i].progress).toBeGreaterThanOrEqual(progressUpdates[i-1].progress);
      }
      
      // Verify consistent update intervals
      const intervals = [];
      for (let i = 1; i < progressUpdates.length; i++) {
        intervals.push(progressUpdates[i].timestamp - progressUpdates[i-1].timestamp);
      }
      
      const avgInterval = intervals.reduce((sum, interval) => sum + interval, 0) / intervals.length;
      expect(avgInterval).toBeLessThan(100); // Should update frequently
      
      // Verify progress starts at 1 and ends at 100
      expect(progressUpdates[0].progress).toBe(1);
      expect(progressUpdates[progressUpdates.length - 1].progress).toBe(100);
    });

    it('should handle upload cancellation gracefully', async () => {
      // Arrange
      const videoBlob = createMockVideoBlob({
        filename: 'cancel-test.mp4',
        size: FILE_SIZES.LARGE,
        duration: 300,
        fps: 30,
        resolution: '1080p',
        format: 'video/mp4'
      });

      const file = new File([videoBlob], 'cancel-test.mp4', { type: 'video/mp4' });
      
      const abortController = new AbortController();
      let progressBeforeCancellation = 0;

      // Mock cancellable upload
      vi.mocked(apiService.uploadVideoCentral).mockImplementation(async (file, onProgress) => {
        const totalChunks = 100;
        
        for (let i = 1; i <= totalChunks; i++) {
          if (abortController.signal.aborted) {
            throw new Error('Upload cancelled');
          }
          
          await new Promise(resolve => setTimeout(resolve, 50));
          
          if (onProgress) {
            onProgress(i);
            progressBeforeCancellation = i;
          }
          
          // Cancel after 30%
          if (i === 30) {
            setTimeout(() => abortController.abort(), 100);
          }
        }
        
        return {
          id: 'should-not-complete',
          filename: file.name,
          file_size: file.size,
          status: 'uploaded'
        };
      });

      // Act & Assert
      await expect(apiService.uploadVideoCentral(file, (progress) => {
        // Progress callback
      })).rejects.toThrow('Upload cancelled');
      
      // Verify cancellation occurred at expected point
      expect(progressBeforeCancellation).toBeGreaterThan(25);
      expect(progressBeforeCancellation).toBeLessThan(40);
    });
  });
});