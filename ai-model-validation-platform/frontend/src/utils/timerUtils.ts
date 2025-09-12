/**
 * Timer Utilities for Cross-Platform Compatibility
 * Provides consistent timer types and utilities for DOM and Node.js environments
 */

// Cross-platform timer handle types
export type TimerHandle = number | NodeJS.Timeout;
export type IntervalHandle = number | NodeJS.Timeout;
export type TimeoutHandle = number | NodeJS.Timeout;

/**
 * Safe setTimeout that returns the correct type for the environment
 */
export const safeSetTimeout = (callback: () => void, delay: number): TimeoutHandle => {
  return setTimeout(callback, delay) as TimeoutHandle;
};

/**
 * Safe setInterval that returns the correct type for the environment
 */
export const safeSetInterval = (callback: () => void, delay: number): IntervalHandle => {
  return setInterval(callback, delay) as IntervalHandle;
};

/**
 * Safe clearTimeout that handles both number and NodeJS.Timeout types
 */
export const safeClearTimeout = (handle: TimeoutHandle | null | undefined): void => {
  if (handle !== null && handle !== undefined) {
    if (typeof handle === 'number') {
      clearTimeout(handle);
    } else {
      clearTimeout(handle as NodeJS.Timeout);
    }
  }
};

/**
 * Safe clearInterval that handles both number and NodeJS.Timeout types
 */
export const safeClearInterval = (handle: IntervalHandle | null | undefined): void => {
  if (handle !== null && handle !== undefined) {
    if (typeof handle === 'number') {
      clearInterval(handle);
    } else {
      clearInterval(handle as NodeJS.Timeout);
    }
  }
};

/**
 * Timer manager class for handling multiple timers with automatic cleanup
 */
export class TimerManager {
  private timeouts = new Set<TimeoutHandle>();
  private intervals = new Set<IntervalHandle>();

  /**
   * Creates a managed timeout
   */
  setTimeout(callback: () => void, delay: number): TimeoutHandle {
    const handle = safeSetTimeout(() => {
      this.timeouts.delete(handle);
      callback();
    }, delay);
    this.timeouts.add(handle);
    return handle;
  }

  /**
   * Creates a managed interval
   */
  setInterval(callback: () => void, delay: number): IntervalHandle {
    const handle = safeSetInterval(callback, delay);
    this.intervals.add(handle);
    return handle;
  }

  /**
   * Clears a specific timeout
   */
  clearTimeout(handle: TimeoutHandle | null | undefined): void {
    if (handle !== null && handle !== undefined) {
      safeClearTimeout(handle);
      this.timeouts.delete(handle);
    }
  }

  /**
   * Clears a specific interval
   */
  clearInterval(handle: IntervalHandle | null | undefined): void {
    if (handle !== null && handle !== undefined) {
      safeClearInterval(handle);
      this.intervals.delete(handle);
    }
  }

  /**
   * Clears all managed timers
   */
  clearAll(): void {
    // Clear all timeouts
    this.timeouts.forEach(handle => safeClearTimeout(handle));
    this.timeouts.clear();

    // Clear all intervals
    this.intervals.forEach(handle => safeClearInterval(handle));
    this.intervals.clear();
  }

  /**
   * Get the count of active timers
   */
  getActiveCount(): { timeouts: number; intervals: number; total: number } {
    return {
      timeouts: this.timeouts.size,
      intervals: this.intervals.size,
      total: this.timeouts.size + this.intervals.size
    };
  }
}

/**
 * Default timer manager instance for global use
 */
export const defaultTimerManager = new TimerManager();

/**
 * Hook-friendly timer utilities
 */
export const timerUtils = {
  setTimeout: safeSetTimeout,
  setInterval: safeSetInterval,
  clearTimeout: safeClearTimeout,
  clearInterval: safeClearInterval,
  createManager: () => new TimerManager()
};