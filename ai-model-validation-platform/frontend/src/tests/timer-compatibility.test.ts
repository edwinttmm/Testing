/**
 * Timer Compatibility Tests
 * Ensures cross-platform timer functionality works correctly
 */

import { 
  safeSetTimeout, 
  safeSetInterval, 
  safeClearTimeout, 
  safeClearInterval,
  TimerManager,
  defaultTimerManager
} from '../utils/timerUtils';

// Mock timers for testing
jest.useFakeTimers();

describe('Timer Utilities', () => {
  beforeEach(() => {
    jest.clearAllTimers();
    defaultTimerManager.clearAll();
  });

  afterEach(() => {
    jest.clearAllTimers();
    defaultTimerManager.clearAll();
  });

  describe('safeSetTimeout', () => {
    it('should set timeout and return handle', () => {
      const callback = jest.fn();
      const handle = safeSetTimeout(callback, 1000);
      
      expect(handle).toBeDefined();
      expect(callback).not.toHaveBeenCalled();
      
      jest.advanceTimersByTime(1000);
      expect(callback).toHaveBeenCalledTimes(1);
    });

    it('should handle timeout handle correctly', () => {
      const callback = jest.fn();
      const handle = safeSetTimeout(callback, 1000);
      
      safeClearTimeout(handle);
      jest.advanceTimersByTime(1000);
      
      expect(callback).not.toHaveBeenCalled();
    });
  });

  describe('safeSetInterval', () => {
    it('should set interval and return handle', () => {
      const callback = jest.fn();
      const handle = safeSetInterval(callback, 1000);
      
      expect(handle).toBeDefined();
      expect(callback).not.toHaveBeenCalled();
      
      jest.advanceTimersByTime(2500);
      expect(callback).toHaveBeenCalledTimes(2);
    });

    it('should handle interval handle correctly', () => {
      const callback = jest.fn();
      const handle = safeSetInterval(callback, 1000);
      
      jest.advanceTimersByTime(1500);
      expect(callback).toHaveBeenCalledTimes(1);
      
      safeClearInterval(handle);
      jest.advanceTimersByTime(1000);
      
      expect(callback).toHaveBeenCalledTimes(1);
    });
  });

  describe('safeClear functions', () => {
    it('should handle null/undefined gracefully', () => {
      expect(() => safeClearTimeout(null)).not.toThrow();
      expect(() => safeClearTimeout(undefined)).not.toThrow();
      expect(() => safeClearInterval(null)).not.toThrow();
      expect(() => safeClearInterval(undefined)).not.toThrow();
    });
  });

  describe('TimerManager', () => {
    let timerManager: TimerManager;

    beforeEach(() => {
      timerManager = new TimerManager();
    });

    afterEach(() => {
      timerManager.clearAll();
    });

    it('should manage timeouts', () => {
      const callback = jest.fn();
      const handle = timerManager.setTimeout(callback, 1000);
      
      expect(handle).toBeDefined();
      expect(timerManager.getActiveCount().timeouts).toBe(1);
      
      jest.advanceTimersByTime(1000);
      expect(callback).toHaveBeenCalledTimes(1);
      expect(timerManager.getActiveCount().timeouts).toBe(0);
    });

    it('should manage intervals', () => {
      const callback = jest.fn();
      const handle = timerManager.setInterval(callback, 1000);
      
      expect(handle).toBeDefined();
      expect(timerManager.getActiveCount().intervals).toBe(1);
      
      jest.advanceTimersByTime(2500);
      expect(callback).toHaveBeenCalledTimes(2);
      expect(timerManager.getActiveCount().intervals).toBe(1);
    });

    it('should clear specific timers', () => {
      const timeoutCallback = jest.fn();
      const intervalCallback = jest.fn();
      
      const timeoutHandle = timerManager.setTimeout(timeoutCallback, 1000);
      const intervalHandle = timerManager.setInterval(intervalCallback, 1000);
      
      expect(timerManager.getActiveCount().total).toBe(2);
      
      timerManager.clearTimeout(timeoutHandle);
      expect(timerManager.getActiveCount().timeouts).toBe(0);
      expect(timerManager.getActiveCount().intervals).toBe(1);
      
      timerManager.clearInterval(intervalHandle);
      expect(timerManager.getActiveCount().total).toBe(0);
    });

    it('should clear all timers', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      const callback3 = jest.fn();
      
      timerManager.setTimeout(callback1, 1000);
      timerManager.setInterval(callback2, 1000);
      timerManager.setTimeout(callback3, 2000);
      
      expect(timerManager.getActiveCount().total).toBe(3);
      
      timerManager.clearAll();
      expect(timerManager.getActiveCount().total).toBe(0);
      
      jest.advanceTimersByTime(3000);
      expect(callback1).not.toHaveBeenCalled();
      expect(callback2).not.toHaveBeenCalled();
      expect(callback3).not.toHaveBeenCalled();
    });

    it('should handle clearing null/undefined handles', () => {
      expect(() => timerManager.clearTimeout(null)).not.toThrow();
      expect(() => timerManager.clearTimeout(undefined)).not.toThrow();
      expect(() => timerManager.clearInterval(null)).not.toThrow();
      expect(() => timerManager.clearInterval(undefined)).not.toThrow();
    });

    it('should provide accurate active count', () => {
      expect(timerManager.getActiveCount()).toEqual({
        timeouts: 0,
        intervals: 0,
        total: 0
      });
      
      timerManager.setTimeout(() => {}, 1000);
      timerManager.setTimeout(() => {}, 2000);
      timerManager.setInterval(() => {}, 1000);
      
      expect(timerManager.getActiveCount()).toEqual({
        timeouts: 2,
        intervals: 1,
        total: 3
      });
    });
  });

  describe('defaultTimerManager', () => {
    it('should be available as singleton', () => {
      expect(defaultTimerManager).toBeInstanceOf(TimerManager);
      
      const callback = jest.fn();
      defaultTimerManager.setTimeout(callback, 1000);
      
      expect(defaultTimerManager.getActiveCount().total).toBe(1);
      jest.advanceTimersByTime(1000);
      expect(callback).toHaveBeenCalled();
    });
  });
});

describe('Timer Type Compatibility', () => {
  it('should work with DOM timer types', () => {
    const callback = jest.fn();
    const domTimeout: number = window.setTimeout(callback, 1000) as any;
    
    // Should not throw when clearing DOM timer handle
    expect(() => safeClearTimeout(domTimeout)).not.toThrow();
  });

  it('should handle mixed timer handle types', () => {
    const callback = jest.fn();
    
    // Test with different handle types that might exist in different environments
    const handles = [
      safeSetTimeout(callback, 1000),
      safeSetInterval(callback, 1000)
    ];
    
    handles.forEach(handle => {
      expect(handle).toBeDefined();
      expect(typeof handle === 'number' || typeof handle === 'object').toBe(true);
    });
    
    // Cleanup should work regardless of handle type
    safeClearTimeout(handles[0]);
    safeClearInterval(handles[1]);
  });
});