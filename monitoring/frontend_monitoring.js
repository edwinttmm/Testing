
// Frontend performance monitoring (React)
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

class PerformanceMonitor {
  constructor() {
    this.metrics = [];
    this.setupWebVitalsTracking();
    this.setupCustomMetrics();
  }

  setupWebVitalsTracking() {
    const sendMetric = (metric) => {
      this.metrics.push({
        name: metric.name,
        value: metric.value,
        timestamp: Date.now(),
        id: metric.id
      });
      
      // Send to backend
      this.sendToBackend(metric);
    };

    getCLS(sendMetric);
    getFID(sendMetric);
    getFCP(sendMetric);
    getLCP(sendMetric);
    getTTFB(sendMetric);
  }

  setupCustomMetrics() {
    // Track component render times
    this.trackComponentPerformance();
    
    // Track API call times
    this.trackAPIPerformance();
    
    // Track resource loading
    this.trackResourceLoading();
  }

  trackComponentPerformance() {
    // React DevTools Profiler API
    const measureRender = (id, phase, actualDuration) => {
      if (actualDuration > 16) { // > 1 frame at 60fps
        this.sendMetric({
          name: 'component_render_time',
          value: actualDuration,
          metadata: { component: id, phase }
        });
      }
    };

    // Wrap components with Profiler
    return measureRender;
  }

  trackAPIPerformance() {
    const originalFetch = window.fetch;
    
    window.fetch = async (...args) => {
      const start = performance.now();
      
      try {
        const response = await originalFetch(...args);
        const duration = performance.now() - start;
        
        this.sendMetric({
          name: 'api_request_duration',
          value: duration,
          metadata: {
            url: args[0],
            status: response.status,
            method: args[1]?.method || 'GET'
          }
        });
        
        return response;
      } catch (error) {
        const duration = performance.now() - start;
        
        this.sendMetric({
          name: 'api_request_error',
          value: duration,
          metadata: {
            url: args[0],
            error: error.message
          }
        });
        
        throw error;
      }
    };
  }

  trackResourceLoading() {
    // Monitor resource loading performance
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 1000) { // Slow resource
          this.sendMetric({
            name: 'resource_loading_time',
            value: entry.duration,
            metadata: {
              resource: entry.name,
              type: entry.initiatorType
            }
          });
        }
      }
    });
    
    observer.observe({ entryTypes: ['resource'] });
  }

  sendMetric(metric) {
    // Send to monitoring endpoint
    fetch('/api/metrics/frontend', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ...metric,
        timestamp: Date.now(),
        userAgent: navigator.userAgent,
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        }
      })
    }).catch(console.error);
  }

  sendToBackend(metric) {
    // Send web vitals to backend
    this.sendMetric({
      name: `web_vitals_${metric.name.toLowerCase()}`,
      value: metric.value,
      metadata: {
        id: metric.id,
        rating: this.getRating(metric.name, metric.value)
      }
    });
  }

  getRating(name, value) {
    const thresholds = {
      CLS: [0.1, 0.25],
      FID: [100, 300],
      FCP: [1800, 3000],
      LCP: [2500, 4000],
      TTFB: [800, 1800]
    };
    
    const [good, poor] = thresholds[name] || [0, 0];
    
    if (value <= good) return 'good';
    if (value <= poor) return 'needs-improvement';
    return 'poor';
  }
}

// Initialize performance monitoring
const performanceMonitor = new PerformanceMonitor();
export default performanceMonitor;
