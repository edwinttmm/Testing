/**
 * Performance utility functions for testing and optimization
 */
export const PerformanceUtils = {
  /**
   * Measure execution time of a function
   */
  measureTime<T>(fn: () => T): { result: T; duration: number } {
    const start = performance.now();
    const result = fn();
    const duration = performance.now() - start;
    return { result, duration };
  },

  /**
   * Get memory usage information if available
   */
  getMemoryUsage(): { used: number; total: number } | null {
    if ('memory' in performance) {
      return {
        used: (performance as any).memory.usedJSHeapSize,
        total: (performance as any).memory.totalJSHeapSize,
      };
    }
    return null;
  },

  /**
   * Benchmark a function execution multiple times
   */
  benchmark<T>(fn: () => T, iterations: number = 100): {
    averageTime: number;
    minTime: number;
    maxTime: number;
    totalTime: number;
    iterations: number;
  } {
    const times: number[] = [];
    
    for (let i = 0; i < iterations; i++) {
      const { duration } = this.measureTime(fn);
      times.push(duration);
    }
    
    const totalTime = times.reduce((sum, time) => sum + time, 0);
    const averageTime = totalTime / iterations;
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    
    return {
      averageTime,
      minTime,
      maxTime,
      totalTime,
      iterations
    };
  },

  /**
   * Throttle function execution
   */
  throttle<T extends (...args: any[]) => any>(
    func: T,
    limit: number
  ): (...args: Parameters<T>) => void {
    let inThrottle: boolean;
    return function (this: any, ...args: Parameters<T>) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  },

  /**
   * Debounce function execution
   */
  debounce<T extends (...args: any[]) => any>(
    func: T,
    wait: number,
    immediate: boolean = false
  ): (...args: Parameters<T>) => void {
    let timeout: NodeJS.Timeout | null;
    return function (this: any, ...args: Parameters<T>) {
      const later = () => {
        timeout = null;
        if (!immediate) func.apply(this, args);
      };
      const callNow = immediate && !timeout;
      if (timeout) clearTimeout(timeout);
      timeout = setTimeout(later, wait);
      if (callNow) func.apply(this, args);
    };
  },

  /**
   * Monitor frame rate
   */
  monitorFrameRate(duration: number = 1000): Promise<{
    averageFPS: number;
    frameCount: number;
    duration: number;
  }> {
    return new Promise((resolve) => {
      let frameCount = 0;
      const startTime = performance.now();
      const lastFrameTime = startTime;
      
      const countFrame = (timestamp: number) => {
        frameCount++;
        if (timestamp - startTime < duration) {
          requestAnimationFrame(countFrame);
        } else {
          const actualDuration = timestamp - startTime;
          const averageFPS = (frameCount * 1000) / actualDuration;
          resolve({
            averageFPS,
            frameCount,
            duration: actualDuration
          });
        }
      };
      
      requestAnimationFrame(countFrame);
    });
  },

  /**
   * Simple performance mark
   */
  mark(name: string): void {
    if (performance.mark) {
      performance.mark(name);
    }
  },

  /**
   * Measure between two performance marks
   */
  measure(name: string, startMark: string, endMark: string): number {
    if (performance.measure && performance.getEntriesByName) {
      performance.measure(name, startMark, endMark);
      const entries = performance.getEntriesByName(name);
      return entries.length > 0 ? entries[entries.length - 1].duration : 0;
    }
    return 0;
  }
};

export default PerformanceUtils;