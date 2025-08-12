// Performance optimization utilities
import React from 'react';

// Debounce hook for search inputs and API calls
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = React.useState<T>(value);

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// Throttle hook for scroll events and frequent updates
export function useThrottle<T>(value: T, limit: number): T {
  const [throttledValue, setThrottledValue] = React.useState<T>(value);
  const lastRun = React.useRef(Date.now());

  React.useEffect(() => {
    const handler = setTimeout(() => {
      if (Date.now() - lastRun.current >= limit) {
        setThrottledValue(value);
        lastRun.current = Date.now();
      }
    }, limit - (Date.now() - lastRun.current));

    return () => {
      clearTimeout(handler);
    };
  }, [value, limit]);

  return throttledValue;
}

// Intersection Observer hook for lazy loading
export function useIntersectionObserver(
  ref: React.RefObject<Element | HTMLImageElement | null>,
  options: IntersectionObserverInit = {}
): IntersectionObserverEntry | undefined {
  const [intersectionObserverEntry, setIntersectionObserverEntry] =
    React.useState<IntersectionObserverEntry>();

  React.useEffect(() => {
    if (ref.current && typeof IntersectionObserver === 'function') {
      const handler = (entries: IntersectionObserverEntry[]) => {
        setIntersectionObserverEntry(entries[0]);
      };

      const observer = new IntersectionObserver(handler, options);
      observer.observe(ref.current);

      return () => {
        setIntersectionObserverEntry(undefined);
        observer.disconnect();
      };
    }
    return () => {};
  }, [ref.current, options.threshold, options.root, options.rootMargin]);

  return intersectionObserverEntry;
}

// Virtual scrolling hook for large lists
interface VirtualScrollOptions {
  itemHeight: number;
  containerHeight: number;
  itemCount: number;
  overscan?: number;
}

export function useVirtualScroll(options: VirtualScrollOptions) {
  const [scrollTop, setScrollTop] = React.useState(0);
  const { itemHeight, containerHeight, itemCount, overscan = 3 } = options;

  const startIndex = Math.floor(scrollTop / itemHeight);
  const endIndex = Math.min(
    itemCount - 1,
    Math.floor((scrollTop + containerHeight) / itemHeight)
  );

  const visibleStartIndex = Math.max(0, startIndex - overscan);
  const visibleEndIndex = Math.min(itemCount - 1, endIndex + overscan);

  const offsetY = visibleStartIndex * itemHeight;

  const handleScroll = React.useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      setScrollTop(e.currentTarget.scrollTop);
    },
    []
  );

  return {
    startIndex: visibleStartIndex,
    endIndex: visibleEndIndex,
    offsetY,
    handleScroll,
  };
}

// Lazy component loader with error boundary
export function createLazyComponent<T extends React.ComponentType<any>>(
  importFunc: () => Promise<{ default: T }>,
  fallback?: React.ComponentType
) {
  const LazyComponent = React.lazy(importFunc);
  
  return React.memo(React.forwardRef<any, React.ComponentProps<T>>((props, ref) => {
    const FallbackComponent = fallback || (() => React.createElement('div', {}, 'Loading...'));
    return React.createElement(
      React.Suspense,
      { fallback: React.createElement(FallbackComponent) },
      React.createElement(LazyComponent as any, { ...props, ref })
    );
  }));
}

// Image lazy loading component
interface LazyImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  alt: string;
  placeholder?: string;
  threshold?: number;
}

export const LazyImage: React.FC<LazyImageProps> = ({
  src,
  alt,
  placeholder = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwIiB5PSI1NSIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSI+TG9hZGluZy4uLjwvdGV4dD48L3N2Zz4=',
  threshold = 0.1,
  ...props
}) => {
  const [imageSrc, setImageSrc] = React.useState(placeholder);
  const [isLoaded, setIsLoaded] = React.useState(false);
  const imgRef = React.useRef<HTMLImageElement>(null);
  
  const entry = useIntersectionObserver(imgRef, { threshold });
  const isIntersecting = entry?.isIntersecting;

  React.useEffect(() => {
    if (isIntersecting && !isLoaded) {
      const img = new Image();
      img.onload = () => {
        setImageSrc(src);
        setIsLoaded(true);
      };
      img.onerror = () => {
        console.error(`Failed to load image: ${src}`);
      };
      img.src = src;
    }
  }, [isIntersecting, isLoaded, src]);

  return React.createElement('img', {
    ...props,
    ref: imgRef,
    src: imageSrc,
    alt: alt,
    loading: "lazy",
    style: {
      transition: 'opacity 0.3s ease',
      opacity: isLoaded ? 1 : 0.7,
      ...props.style,
    }
  });
};

// Memoization utilities
export const shallowEqual = (obj1: any, obj2: any): boolean => {
  const keys1 = Object.keys(obj1);
  const keys2 = Object.keys(obj2);

  if (keys1.length !== keys2.length) {
    return false;
  }

  for (const key of keys1) {
    if (obj1[key] !== obj2[key]) {
      return false;
    }
  }

  return true;
};

export const deepEqual = (obj1: any, obj2: any): boolean => {
  if (obj1 === obj2) {
    return true;
  }

  if (obj1 == null || obj2 == null) {
    return false;
  }

  if (typeof obj1 !== 'object' || typeof obj2 !== 'object') {
    return false;
  }

  const keys1 = Object.keys(obj1);
  const keys2 = Object.keys(obj2);

  if (keys1.length !== keys2.length) {
    return false;
  }

  for (const key of keys1) {
    if (!deepEqual(obj1[key], obj2[key])) {
      return false;
    }
  }

  return true;
};

// Custom memo hook with custom comparison
export function useMemoCompare<T>(
  next: T,
  compare: (previous: T | undefined, next: T) => boolean
): T {
  const previousRef = React.useRef<T>(undefined);
  const memoizedRef = React.useRef<T>(undefined);

  if (!compare(previousRef.current, next)) {
    memoizedRef.current = next;
  }

  previousRef.current = next;
  return memoizedRef.current!;
}

// Performance profiler component
interface PerformanceProfilerProps {
  id: string;
  children: React.ReactNode;
  onRender?: (
    id: string,
    phase: 'mount' | 'update',
    actualDuration: number,
    baseDuration: number,
    startTime: number,
    commitTime: number,
    interactions: Set<any>
  ) => void;
}

export const PerformanceProfiler: React.FC<PerformanceProfilerProps> = ({
  id,
  children,
  onRender,
}) => {
  const defaultOnRender = React.useCallback(
    (
      id: string,
      phase: 'mount' | 'update',
      actualDuration: number,
      baseDuration: number,
      startTime: number,
      commitTime: number,
      interactions: Set<any>
    ) => {
      if (process.env.NODE_ENV === 'development') {
        console.log(`Component ${id} ${phase} took ${actualDuration}ms`);
        if (actualDuration > baseDuration * 2) {
          console.warn(`Component ${id} is rendering slowly`);
        }
      }
    },
    []
  );

  return React.createElement(
    React.Profiler,
    { id, onRender: (onRender || defaultOnRender) as any },
    children
  );
};

// Bundle size estimation
export const getBundleSize = (): Promise<number> => {
  return new Promise((resolve) => {
    if ('navigator' in window && 'serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        // Estimate based on cache size (rough approximation)
        if ('storage' in navigator && 'estimate' in navigator.storage) {
          navigator.storage.estimate().then((estimate) => {
            resolve(estimate.usage || 0);
          });
        } else {
          resolve(0);
        }
      }).catch(() => resolve(0));
    } else {
      resolve(0);
    }
  });
};

export default {
  useDebounce,
  useThrottle,
  useIntersectionObserver,
  useVirtualScroll,
  createLazyComponent,
  LazyImage,
  shallowEqual,
  deepEqual,
  useMemoCompare,
  PerformanceProfiler,
  getBundleSize,
};