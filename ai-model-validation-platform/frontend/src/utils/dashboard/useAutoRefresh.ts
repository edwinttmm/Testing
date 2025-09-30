/**
 * Custom hook for auto-refresh functionality with pause/resume capability
 */

import { useState, useEffect, useCallback, useRef } from 'react';

export interface AutoRefreshConfig {
  interval: number; // in milliseconds
  immediate?: boolean; // whether to call refreshFunction immediately
  enabled?: boolean; // whether auto-refresh is enabled by default
  maxRetries?: number; // maximum number of retry attempts on failure
  backoffMultiplier?: number; // backoff multiplier for retry attempts
}

export interface AutoRefreshState {
  isActive: boolean;
  isPaused: boolean;
  lastRefresh: Date | null;
  nextRefresh: Date | null;
  retryCount: number;
  error: string | null;
}

export interface AutoRefreshControls {
  start: () => void;
  stop: () => void;
  pause: () => void;
  resume: () => void;
  refresh: () => Promise<void>;
  setInterval: (newInterval: number) => void;
  reset: () => void;
}

export type AutoRefreshHook = [AutoRefreshState, AutoRefreshControls];

/**
 * Custom hook for managing auto-refresh functionality
 */
export const useAutoRefresh = (
  refreshFunction: () => Promise<void> | void,
  config: AutoRefreshConfig
): AutoRefreshHook => {
  const {
    interval,
    immediate = false,
    enabled = true,
    maxRetries = 3,
    backoffMultiplier = 2,
  } = config;

  const [state, setState] = useState<AutoRefreshState>({
    isActive: enabled,
    isPaused: false,
    lastRefresh: null,
    nextRefresh: null,
    retryCount: 0,
    error: null,
  });

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const currentIntervalRef = useRef(interval);

  /**
   * Clears all timers
   */
  const clearTimers = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  }, []);

  /**
   * Executes the refresh function with error handling and retry logic
   */
  const executeRefresh = useCallback(async () => {
    try {
      await refreshFunction();
      
      setState(prev => ({
        ...prev,
        lastRefresh: new Date(),
        nextRefresh: new Date(Date.now() + currentIntervalRef.current),
        retryCount: 0,
        error: null,
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      setState(prev => {
        const newRetryCount = prev.retryCount + 1;
        
        if (newRetryCount <= maxRetries) {
          // Schedule retry with exponential backoff
          const retryDelay = currentIntervalRef.current * Math.pow(backoffMultiplier, newRetryCount - 1);
          
          retryTimeoutRef.current = setTimeout(() => {
            executeRefresh();
          }, retryDelay);
          
          return {
            ...prev,
            retryCount: newRetryCount,
            error: `${errorMessage} (Retry ${newRetryCount}/${maxRetries})`,
            nextRefresh: new Date(Date.now() + retryDelay),
          };
        } else {
          // Max retries reached, stop auto-refresh
          return {
            ...prev,
            isActive: false,
            retryCount: newRetryCount,
            error: `${errorMessage} (Max retries reached)`,
            nextRefresh: null,
          };
        }
      });
    }
  }, [refreshFunction, maxRetries, backoffMultiplier]);

  /**
   * Starts the auto-refresh timer
   */
  const startTimer = useCallback(() => {
    clearTimers();
    
    if (immediate) {
      executeRefresh();
    }
    
    intervalRef.current = setInterval(() => {
      if (!state.isPaused) {
        executeRefresh();
      }
    }, currentIntervalRef.current);

    setState(prev => ({
      ...prev,
      nextRefresh: new Date(Date.now() + currentIntervalRef.current),
    }));
  }, [executeRefresh, immediate, clearTimers, state.isPaused]);

  /**
   * Control functions
   */
  const start = useCallback(() => {
    setState(prev => ({
      ...prev,
      isActive: true,
      isPaused: false,
      retryCount: 0,
      error: null,
    }));
  }, []);

  const stop = useCallback(() => {
    clearTimers();
    setState(prev => ({
      ...prev,
      isActive: false,
      isPaused: false,
      nextRefresh: null,
      retryCount: 0,
      error: null,
    }));
  }, [clearTimers]);

  const pause = useCallback(() => {
    setState(prev => ({
      ...prev,
      isPaused: true,
      nextRefresh: null,
    }));
  }, []);

  const resume = useCallback(() => {
    setState(prev => ({
      ...prev,
      isPaused: false,
      nextRefresh: new Date(Date.now() + currentIntervalRef.current),
    }));
  }, []);

  const refresh = useCallback(async () => {
    await executeRefresh();
  }, [executeRefresh]);

  const setInterval = useCallback((newInterval: number) => {
    currentIntervalRef.current = newInterval;
    
    if (state.isActive && !state.isPaused) {
      startTimer();
    }
  }, [state.isActive, state.isPaused, startTimer]);

  const reset = useCallback(() => {
    clearTimers();
    setState({
      isActive: enabled,
      isPaused: false,
      lastRefresh: null,
      nextRefresh: null,
      retryCount: 0,
      error: null,
    });
  }, [enabled, clearTimers]);

  /**
   * Effect to manage the timer based on state changes
   */
  useEffect(() => {
    if (state.isActive && !state.isPaused) {
      startTimer();
    } else {
      clearTimers();
    }

    return () => {
      clearTimers();
    };
  }, [state.isActive, state.isPaused, startTimer, clearTimers]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      clearTimers();
    };
  }, [clearTimers]);

  const controls: AutoRefreshControls = {
    start,
    stop,
    pause,
    resume,
    refresh,
    setInterval,
    reset,
  };

  return [state, controls];
};

/**
 * Hook for managing multiple auto-refresh instances
 */
export const useMultipleAutoRefresh = (
  refreshFunctions: Record<string, () => Promise<void> | void>,
  configs: Record<string, AutoRefreshConfig>
) => {
  const instances: Record<string, AutoRefreshHook> = {};
  
  Object.keys(refreshFunctions).forEach(key => {
    if (configs[key]) {
      instances[key] = useAutoRefresh(refreshFunctions[key], configs[key]);
    }
  });

  const startAll = useCallback(() => {
    Object.values(instances).forEach(([, controls]) => controls.start());
  }, [instances]);

  const stopAll = useCallback(() => {
    Object.values(instances).forEach(([, controls]) => controls.stop());
  }, [instances]);

  const pauseAll = useCallback(() => {
    Object.values(instances).forEach(([, controls]) => controls.pause());
  }, [instances]);

  const resumeAll = useCallback(() => {
    Object.values(instances).forEach(([, controls]) => controls.resume());
  }, [instances]);

  const refreshAll = useCallback(async () => {
    await Promise.allSettled(
      Object.values(instances).map(([, controls]) => controls.refresh())
    );
  }, [instances]);

  return {
    instances,
    controls: {
      startAll,
      stopAll,
      pauseAll,
      resumeAll,
      refreshAll,
    },
  };
};

/**
 * Hook for adaptive refresh intervals based on activity
 */
export const useAdaptiveAutoRefresh = (
  refreshFunction: () => Promise<void> | void,
  baseConfig: AutoRefreshConfig,
  activityThreshold: number = 30000 // 30 seconds
) => {
  const [lastActivity, setLastActivity] = useState(Date.now());
  const [currentInterval, setCurrentInterval] = useState(baseConfig.interval);
  
  const adaptedConfig = {
    ...baseConfig,
    interval: currentInterval,
  };

  const [state, controls] = useAutoRefresh(refreshFunction, adaptedConfig);

  /**
   * Updates last activity timestamp
   */
  const updateActivity = useCallback(() => {
    setLastActivity(Date.now());
  }, []);

  /**
   * Effect to adjust refresh interval based on user activity
   */
  useEffect(() => {
    const checkActivity = () => {
      const timeSinceActivity = Date.now() - lastActivity;
      
      if (timeSinceActivity > activityThreshold) {
        // User is inactive, slow down refresh
        const newInterval = Math.min(baseConfig.interval * 4, 300000); // Max 5 minutes
        if (newInterval !== currentInterval) {
          setCurrentInterval(newInterval);
          controls.setInterval(newInterval);
        }
      } else {
        // User is active, use base interval
        if (currentInterval !== baseConfig.interval) {
          setCurrentInterval(baseConfig.interval);
          controls.setInterval(baseConfig.interval);
        }
      }
    };

    const activityTimer = setInterval(checkActivity, 10000); // Check every 10 seconds

    // Listen for user activity events
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    
    events.forEach(event => {
      document.addEventListener(event, updateActivity, { passive: true });
    });

    return () => {
      clearInterval(activityTimer);
      events.forEach(event => {
        document.removeEventListener(event, updateActivity);
      });
    };
  }, [lastActivity, currentInterval, baseConfig.interval, activityThreshold, controls, updateActivity]);

  return [
    { ...state, currentInterval },
    { ...controls, updateActivity }
  ];
};

/**
 * Hook for conditional auto-refresh based on conditions
 */
export const useConditionalAutoRefresh = (
  refreshFunction: () => Promise<void> | void,
  config: AutoRefreshConfig,
  condition: () => boolean
) => {
  const [state, controls] = useAutoRefresh(
    async () => {
      if (condition()) {
        await refreshFunction();
      }
    },
    config
  );

  return [state, controls];
};