/**
 * Render Optimizations Utility
 * Provides utilities for preventing unnecessary re-renders and optimizing component performance
 */

import { useCallback, useRef, useEffect } from 'react';

/**
 * Prevents excessive function calls by debouncing
 */
export const useDebounce = <T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T => {
  const timeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  return useCallback(
    ((...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      
      timeoutRef.current = setTimeout(() => {
        callback(...args);
      }, delay);
    }) as T,
    [callback, delay]
  );
};

/**
 * Throttles function calls to prevent excessive execution
 */
export const useThrottle = <T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T => {
  const lastCallRef = useRef<number>(0);
  const timeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  return useCallback(
    ((...args: Parameters<T>) => {
      const now = Date.now();
      const timeSinceLastCall = now - lastCallRef.current;

      if (timeSinceLastCall >= delay) {
        lastCallRef.current = now;
        callback(...args);
      } else if (!timeoutRef.current) {
        timeoutRef.current = setTimeout(() => {
          lastCallRef.current = Date.now();
          callback(...args);
          timeoutRef.current = undefined;
        }, delay - timeSinceLastCall);
      }
    }) as T,
    [callback, delay]
  );
};

/**
 * Prevents component re-renders when props haven't actually changed
 */
export const useShallowMemo = <T>(value: T, dependencies: any[]): T => {
  const ref = useRef<T>(value);
  const depsRef = useRef(dependencies);

  // Check if dependencies have changed using shallow comparison
  const hasChanged = dependencies.some((dep, index) => dep !== depsRef.current[index]);

  if (hasChanged) {
    ref.current = value;
    depsRef.current = dependencies;
  }

  return ref.current;
};

/**
 * Optimized canvas drawing hook that prevents unnecessary redraws
 */
export const useOptimizedCanvasDraw = (
  canvasRef: React.RefObject<HTMLCanvasElement>,
  drawFunction: () => void,
  dependencies: any[]
) => {
  const lastDepsRef = useRef(dependencies);
  const isDrawingRef = useRef(false);

  useEffect(() => {
    // Check if dependencies have actually changed
    const hasChanged = dependencies.some((dep, index) => dep !== lastDepsRef.current[index]);
    
    if (!hasChanged || isDrawingRef.current) return;

    isDrawingRef.current = true;
    
    requestAnimationFrame(() => {
      if (canvasRef.current) {
        drawFunction();
      }
      isDrawingRef.current = false;
    });

    lastDepsRef.current = dependencies;
  }, dependencies);
};

/**
 * Performance monitoring hook for debugging render performance
 */
export const useRenderPerformance = (componentName: string, enabled: boolean = process.env.NODE_ENV === 'development') => {
  const renderCountRef = useRef(0);
  const lastRenderTimeRef = useRef(Date.now());

  useEffect(() => {
    if (!enabled) return;

    renderCountRef.current += 1;
    const now = Date.now();
    const timeSinceLastRender = now - lastRenderTimeRef.current;

    if (timeSinceLastRender < 16) { // Less than 60fps
      console.warn(`${componentName} is rendering too frequently (${timeSinceLastRender}ms since last render)`);
    }

    if (renderCountRef.current % 10 === 0) {
      console.log(`${componentName} render count: ${renderCountRef.current}`);
    }

    lastRenderTimeRef.current = now;
  });
};

/**
 * Stable callback hook that prevents unnecessary re-creation
 */
export const useStableCallback = <T extends (...args: any[]) => any>(callback: T): T => {
  const callbackRef = useRef(callback);
  
  useEffect(() => {
    callbackRef.current = callback;
  });

  return useCallback(
    ((...args: any[]) => callbackRef.current(...args)) as T,
    []
  );
};