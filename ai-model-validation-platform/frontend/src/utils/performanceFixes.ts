/**
 * Performance optimization utilities for React components
 * Fixes common performance issues and memory leaks
 */

import React, { useCallback, useEffect, useRef, useMemo } from 'react';
import { debounce } from 'lodash';

/**
 * Debounced callback hook to prevent excessive API calls
 */
export const useDebouncedCallback = <T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number = 300
): T => {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  return useCallback(
    debounce((...args: unknown[]) => callbackRef.current(...args), delay),
    [delay]
  ) as T;
};

/**
 * Optimized effect hook that handles cleanup properly
 */
export const useOptimizedEffect = (
  effect: () => void | (() => void),
  deps: React.DependencyList
) => {
  const cleanupRef = useRef<(() => void) | void>();

  useEffect(() => {
    // Clean up previous effect if needed
    if (cleanupRef.current) {
      cleanupRef.current();
    }
    
    cleanupRef.current = effect();
    
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
      }
    };
  }, deps);
  
  return undefined; // Explicit return for void function
};

/**
 * Memoized stable reference to prevent unnecessary re-renders
 */
export const useStableCallback = <T extends (...args: unknown[]) => unknown>(callback: T): T => {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;
  
  return useCallback((...args: unknown[]) => callbackRef.current(...args), []) as T;
};

/**
 * Performance monitoring hook for components
 */
export const usePerformanceMonitor = (componentName: string) => {
  const renderCount = useRef(0);
  const lastRenderTime = useRef(Date.now());
  
  const logPerformance = useCallback(() => {
    const now = Date.now();
    const timeSinceLastRender = now - lastRenderTime.current;
    renderCount.current++;
    
    if (renderCount.current > 10 && timeSinceLastRender < 100) {
      console.warn(`⚠️ Performance Issue: ${componentName} rendered ${renderCount.current} times in quick succession`);
    }
    
    lastRenderTime.current = now;
  }, [componentName]);
  
  useEffect(() => {
    logPerformance();
  });
  
  return { renderCount: renderCount.current };
};

/**
 * Intersection Observer hook for lazy loading
 */
export const useIntersectionObserver = (
  callback: (isIntersecting: boolean) => void,
  options: IntersectionObserverInit = {}
) => {
  const targetRef = useRef<Element | null>(null);
  
  useEffect(() => {
    const element = targetRef.current;
    if (!element) return;
    
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        callback(entry.isIntersecting);
      },
      {
        threshold: 0.1,
        ...options,
      }
    );
    
    observer.observe(element);
    
    return () => {
      observer.disconnect();
    };
  }, [callback, options]);
  
  return targetRef;
};

/**
 * Virtual scrolling helper for large lists
 */
export const useVirtualScroll = (
  items: unknown[],
  itemHeight: number,
  containerHeight: number,
  buffer: number = 5
) => {
  const scrollTop = useRef(0);
  
  const visibleItems = useMemo(() => {
    const start = Math.max(0, Math.floor(scrollTop.current / itemHeight) - buffer);
    const end = Math.min(
      items.length,
      Math.ceil((scrollTop.current + containerHeight) / itemHeight) + buffer
    );
    
    return {
      start,
      end,
      items: items.slice(start, end),
      totalHeight: items.length * itemHeight,
      offsetY: start * itemHeight,
    };
  }, [items, itemHeight, containerHeight, buffer]);
  
  const onScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    scrollTop.current = e.currentTarget.scrollTop;
  }, []);
  
  return { visibleItems, onScroll };
};

/**
 * Async data fetching hook with error handling
 */
export const useAsyncData = <T>(
  fetchFunction: () => Promise<T>,
  deps: React.DependencyList = []
) => {
  const [data, setData] = React.useState<T | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<Error | null>(null);
  const cancelRef = useRef<boolean>(false);
  
  useEffect(() => {
    let isCancelled = false;
    cancelRef.current = false;
    
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const result = await fetchFunction();
        
        if (!isCancelled && !cancelRef.current) {
          setData(result);
        }
      } catch (err) {
        if (!isCancelled && !cancelRef.current) {
          setError(err instanceof Error ? err : new Error('Unknown error'));
        }
      } finally {
        if (!isCancelled && !cancelRef.current) {
          setLoading(false);
        }
      }
    };
    
    fetchData();
    
    return () => {
      isCancelled = true;
      cancelRef.current = true;
    };
  }, deps);
  
  const refetch = useCallback(() => {
    cancelRef.current = false;
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const result = await fetchFunction();
        
        if (!cancelRef.current) {
          setData(result);
        }
      } catch (err) {
        if (!cancelRef.current) {
          setError(err instanceof Error ? err : new Error('Unknown error'));
        }
      } finally {
        if (!cancelRef.current) {
          setLoading(false);
        }
      }
    };
    
    fetchData();
  }, [fetchFunction]);
  
  return { data, loading, error, refetch };
};

/**
 * Memory leak prevention for subscriptions
 */
export const useSubscription = <T>(
  subscribe: (callback: (value: T) => void) => () => void,
  deps: React.DependencyList = []
) => {
  const [value, setValue] = React.useState<T | null>(null);
  
  useEffect(() => {
    const unsubscribe = subscribe(setValue);
    
    return () => {
      unsubscribe();
    };
  }, deps);
  
  return value;
};