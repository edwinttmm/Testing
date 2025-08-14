// Performance monitoring utilities for React components
import { onCLS, onFID, onFCP, onLCP, onTTFB } from 'web-vitals';
import React, { useEffect, memo, useRef, useLayoutEffect } from 'react';

interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
}

class PerformanceMonitor {
  private metrics: PerformanceMetric[] = [];
  private observers: PerformanceObserver[] = [];

  constructor() {
    this.initWebVitals();
    this.initCustomMetrics();
  }

  private initWebVitals() {
    // Collect Core Web Vitals
    onCLS((metric) => this.recordMetric('CLS', metric.value));
    onFID((metric) => this.recordMetric('FID', metric.value));
    onFCP((metric) => this.recordMetric('FCP', metric.value));
    onLCP((metric) => this.recordMetric('LCP', metric.value));
    onTTFB((metric) => this.recordMetric('TTFB', metric.value));
  }

  private initCustomMetrics() {
    // Monitor long tasks
    if ('PerformanceObserver' in window) {
      try {
        const longTaskObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            this.recordMetric('Long Task', entry.duration);
          }
        });
        longTaskObserver.observe({ entryTypes: ['longtask'] });
        this.observers.push(longTaskObserver);
      } catch (e) {
        console.warn('Long task observer not supported:', e);
      }

      // Monitor navigation timing
      try {
        const navigationObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            const navEntry = entry as PerformanceNavigationTiming;
            this.recordMetric('DOM Content Loaded', navEntry.domContentLoadedEventEnd - navEntry.fetchStart);
            this.recordMetric('Load Complete', navEntry.loadEventEnd - navEntry.fetchStart);
          }
        });
        navigationObserver.observe({ entryTypes: ['navigation'] });
        this.observers.push(navigationObserver);
      } catch (e) {
        console.warn('Navigation observer not supported:', e);
      }

      // Monitor resource loading
      try {
        const resourceObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            const resourceEntry = entry as PerformanceResourceTiming;
            if (resourceEntry.initiatorType === 'script' || resourceEntry.initiatorType === 'link') {
              this.recordMetric(`Resource Load: ${resourceEntry.name.split('/').pop()}`, resourceEntry.duration);
            }
          }
        });
        resourceObserver.observe({ entryTypes: ['resource'] });
        this.observers.push(resourceObserver);
      } catch (e) {
        console.warn('Resource observer not supported:', e);
      }
    }
  }

  private recordMetric(name: string, value: number) {
    this.metrics.push({
      name,
      value,
      timestamp: Date.now(),
    });

    // Keep only last 100 metrics to prevent memory leak
    if (this.metrics.length > 100) {
      this.metrics = this.metrics.slice(-100);
    }

    // Log significant metrics
    if (name === 'LCP' && value > 2500) {
      console.warn(`Poor LCP detected: ${value}ms`);
    } else if (name === 'FID' && value > 100) {
      console.warn(`Poor FID detected: ${value}ms`);
    } else if (name === 'CLS' && value > 0.1) {
      console.warn(`Poor CLS detected: ${value}`);
    } else if (name === 'Long Task' && value > 50) {
      console.warn(`Long task detected: ${value}ms`);
    }
  }

  getMetrics(): PerformanceMetric[] {
    return [...this.metrics];
  }

  getMetricsSummary() {
    const summary: { [key: string]: { count: number; total: number; avg: number; max: number } } = {};

    this.metrics.forEach(metric => {
      if (!summary[metric.name]) {
        summary[metric.name] = { count: 0, total: 0, avg: 0, max: 0 };
      }
      
      const s = summary[metric.name];
      s.count++;
      s.total += metric.value;
      s.max = Math.max(s.max, metric.value);
      s.avg = s.total / s.count;
    });

    return summary;
  }

  // Component-specific performance tracking
  startTimer(componentName: string): () => void {
    const startTime = performance.now();
    
    return () => {
      const duration = performance.now() - startTime;
      this.recordMetric(`Component Render: ${componentName}`, duration);
    };
  }

  // API call performance tracking
  trackApiCall(endpoint: string, duration: number) {
    this.recordMetric(`API Call: ${endpoint}`, duration);
  }

  // Bundle size tracking
  trackBundleSize() {
    if ('navigator' in window && 'connection' in navigator) {
      const connection = (navigator as any).connection;
      if (connection) {
        this.recordMetric('Effective Connection Type', this.connectionTypeToNumber(connection.effectiveType));
        this.recordMetric('Downlink Speed', connection.downlink);
      }
    }

    // Track JavaScript bundle size
    const scripts = document.querySelectorAll('script[src]');
    let totalSize = 0;
    
    scripts.forEach(script => {
      const src = script.getAttribute('src');
      if (src && src.includes('static/js/')) {
        // Estimate size based on typical compression ratios
        totalSize += this.estimateScriptSize(src);
      }
    });

    if (totalSize > 0) {
      this.recordMetric('Estimated Bundle Size (KB)', Math.round(totalSize / 1024));
    }
  }

  private connectionTypeToNumber(type: string): number {
    const types: { [key: string]: number } = {
      'slow-2g': 1,
      '2g': 2,
      '3g': 3,
      '4g': 4,
      '5g': 5,
    };
    return types[type] || 0;
  }

  private estimateScriptSize(src: string): number {
    // Very rough estimation based on filename patterns
    if (src.includes('main.')) return 200000; // ~200KB main bundle
    if (src.includes('chunk.')) return 50000;  // ~50KB per chunk
    if (src.includes('vendor.')) return 300000; // ~300KB vendor bundle
    return 10000; // ~10KB default
  }

  // Memory usage tracking
  trackMemoryUsage() {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      this.recordMetric('JS Heap Used (MB)', Math.round(memory.usedJSHeapSize / 1024 / 1024));
      this.recordMetric('JS Heap Total (MB)', Math.round(memory.totalJSHeapSize / 1024 / 1024));
      this.recordMetric('JS Heap Limit (MB)', Math.round(memory.jsHeapSizeLimit / 1024 / 1024));
    }
  }

  // Generate performance report
  generateReport(): string {
    const summary = this.getMetricsSummary();
    const report = ['=== Performance Report ===\n'];

    // Core Web Vitals
    report.push('Core Web Vitals:');
    ['CLS', 'FID', 'FCP', 'LCP', 'TTFB'].forEach(metric => {
      if (summary[metric]) {
        const s = summary[metric];
        report.push(`  ${metric}: ${s.avg.toFixed(2)}ms (max: ${s.max.toFixed(2)}ms)`);
      }
    });

    // Component performance
    report.push('\nComponent Performance:');
    Object.keys(summary)
      .filter(key => key.startsWith('Component Render:'))
      .forEach(key => {
        const s = summary[key];
        const componentName = key.replace('Component Render: ', '');
        report.push(`  ${componentName}: ${s.avg.toFixed(2)}ms avg (${s.count} renders)`);
      });

    // API performance
    report.push('\nAPI Performance:');
    Object.keys(summary)
      .filter(key => key.startsWith('API Call:'))
      .forEach(key => {
        const s = summary[key];
        const endpoint = key.replace('API Call: ', '');
        report.push(`  ${endpoint}: ${s.avg.toFixed(2)}ms avg (${s.count} calls)`);
      });

    return report.join('\n');
  }

  // Cleanup
  destroy() {
    this.observers.forEach(observer => observer.disconnect());
    this.observers = [];
    this.metrics = [];
  }
}

// Singleton instance
export const performanceMonitor = new PerformanceMonitor();

// React hook for component performance tracking
export function usePerformanceTracking(componentName: string) {
  useEffect(() => {
    const endTimer = performanceMonitor.startTimer(componentName);
    return endTimer;
  }, [componentName]);
}

// HOC for performance tracking
export function withPerformanceTracking<T extends object>(
  Component: React.ComponentType<T>,
  componentName?: string
) {
  const WrappedComponent = memo<T>((props: T) => {
    const endTimer = useRef<(() => void) | null>(null);

    useLayoutEffect(() => {
      endTimer.current = performanceMonitor.startTimer(componentName || Component.name);
      return () => {
        if (endTimer.current) {
          endTimer.current();
        }
      };
    });

    return React.createElement(Component, props);
  });

  WrappedComponent.displayName = `withPerformanceTracking(${componentName || Component.name})`;
  return WrappedComponent;
}

export default performanceMonitor;