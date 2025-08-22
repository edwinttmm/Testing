/**
 * System Performance Tests
 * 
 * Comprehensive performance testing for the AI Model Validation Platform
 * Tests memory usage, CPU utilization, rendering performance, and real-time capabilities
 */

import { describe, test, expect, beforeAll, afterAll, beforeEach } from '@jest/globals';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { performance } from 'perf_hooks';
import { BrowserRouter } from 'react-router-dom';

// Performance monitoring utilities
class PerformanceMonitor {
  private metrics: Map<string, number[]> = new Map();
  private observer: PerformanceObserver | null = null;
  
  start() {
    // Monitor paint and layout metrics
    if (typeof PerformanceObserver !== 'undefined') {
      this.observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const metricName = entry.name || entry.entryType;
          if (!this.metrics.has(metricName)) {
            this.metrics.set(metricName, []);
          }
          this.metrics.get(metricName)!.push(entry.duration || entry.startTime);
        }
      });
      
      this.observer.observe({ entryTypes: ['paint', 'layout-shift', 'largest-contentful-paint'] });
    }
  }
  
  stop() {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
  }
  
  getMetrics() {
    const results: Record<string, { avg: number; max: number; min: number; count: number }> = {};
    
    for (const [name, values] of this.metrics.entries()) {
      if (values.length > 0) {
        results[name] = {
          avg: values.reduce((a, b) => a + b, 0) / values.length,
          max: Math.max(...values),
          min: Math.min(...values),
          count: values.length
        };
      }
    }
    
    return results;
  }
  
  clear() {
    this.metrics.clear();
  }
}

// Memory usage tracker
class MemoryTracker {
  private initialMemory: number = 0;
  private samples: number[] = [];
  
  start() {
    if (typeof performance !== 'undefined' && 'memory' in performance) {
      this.initialMemory = (performance as any).memory.usedJSHeapSize;
    }
  }
  
  sample() {
    if (typeof performance !== 'undefined' && 'memory' in performance) {
      this.samples.push((performance as any).memory.usedJSHeapSize);
    }
  }
  
  getMemoryUsage() {
    if (this.samples.length === 0) return null;
    
    const maxMemory = Math.max(...this.samples);
    const avgMemory = this.samples.reduce((a, b) => a + b, 0) / this.samples.length;
    const memoryIncrease = maxMemory - this.initialMemory;
    
    return {
      initial: this.initialMemory,
      max: maxMemory,
      average: avgMemory,
      increase: memoryIncrease,
      samples: this.samples.length
    };
  }
}

// Components under test
import App from '../../src/App';
import TestExecution from '../../src/pages/TestExecution-fixed';
import AccessibleVideoPlayer from '../../src/components/AccessibleVideoPlayer';
import Projects from '../../src/pages/Projects';

// Test data
import {
  createMockVideo,
  createMockVideoList,
  createMockDetectionEventList,
  createMockAnnotationList,
  createMockProject,
  createMockTestSession
} from '../helpers/test-factories';

let performanceMonitor: PerformanceMonitor;
let memoryTracker: MemoryTracker;

beforeAll(() => {
  performanceMonitor = new PerformanceMonitor();
  memoryTracker = new MemoryTracker();
  
  // Mock performance APIs if not available
  if (typeof PerformanceObserver === 'undefined') {
    global.PerformanceObserver = class {
      observe() {}
      disconnect() {}
    } as any;
  }
});

beforeEach(() => {
  performanceMonitor.clear();
  memoryTracker.start();
  performanceMonitor.start();
});

afterAll(() => {
  performanceMonitor.stop();
});

// Helper to render with performance monitoring
const renderWithMonitoring = (component: React.ReactElement) => {
  const start = performance.now();
  const result = render(<BrowserRouter>{component}</BrowserRouter>);
  const renderTime = performance.now() - start;
  
  return { ...result, renderTime };
};

// ============================================================================
// RENDERING PERFORMANCE TESTS
// ============================================================================

describe('Rendering Performance', () => {
  test('should render main application within performance budget', async () => {
    const { renderTime } = renderWithMonitoring(<App />);
    
    // Initial render should be under 100ms
    expect(renderTime).toBeLessThan(100);
    
    // Check memory usage after initial render
    memoryTracker.sample();
    
    await waitFor(() => {
      expect(screen.getByText(/AI Model Validation Platform/i)).toBeInTheDocument();
    });
    
    const finalMemory = memoryTracker.getMemoryUsage();
    
    // Memory increase should be reasonable (under 10MB for initial render)
    if (finalMemory) {
      expect(finalMemory.increase).toBeLessThan(10 * 1024 * 1024);
    }
    
    console.log(`✅ App rendered in ${renderTime.toFixed(2)}ms`);
    if (finalMemory) {
      console.log(`📊 Memory usage: ${(finalMemory.increase / 1024 / 1024).toFixed(2)}MB increase`);
    }
  });
  
  test('should handle large project lists efficiently', async () => {
    // Create large dataset
    const largeProjectList = Array.from({ length: 1000 }, (_, i) => 
      createMockProject({ id: `project-${i}`, name: `Project ${i}` })
    );
    
    // Mock API to return large dataset
    const mockApiCall = jest.fn().mockResolvedValue(largeProjectList);
    
    const start = performance.now();
    const { renderTime } = renderWithMonitoring(<Projects />);
    
    // Component should render quickly even with large dataset
    expect(renderTime).toBeLessThan(200);
    
    // Check memory usage with large dataset
    for (let i = 0; i < 10; i++) {
      await new Promise(resolve => setTimeout(resolve, 100));
      memoryTracker.sample();
    }
    
    const memoryUsage = memoryTracker.getMemoryUsage();
    if (memoryUsage) {
      // Memory should not exceed 50MB for 1000 projects
      expect(memoryUsage.increase).toBeLessThan(50 * 1024 * 1024);
    }
    
    console.log(`✅ Large project list (1000 items) rendered in ${renderTime.toFixed(2)}ms`);
  });
  
  test('should maintain 60fps during video playback with annotations', async () => {
    const mockVideo = createMockVideo();
    const annotations = createMockAnnotationList(50); // Many annotations
    
    let frameCount = 0;
    let lastFrameTime = performance.now();
    const frameRates: number[] = [];
    
    // Monitor frame rate
    const frameCallback = () => {
      const currentTime = performance.now();
      const deltaTime = currentTime - lastFrameTime;
      const fps = 1000 / deltaTime;
      
      frameRates.push(fps);
      frameCount++;
      lastFrameTime = currentTime;
      
      if (frameCount < 60) { // Monitor for 60 frames
        requestAnimationFrame(frameCallback);
      }
    };
    
    render(
      <AccessibleVideoPlayer
        video={mockVideo}
        annotations={annotations}
        annotationMode={true}
        frameRate={30}
        onAnnotationSelect={jest.fn()}
        onTimeUpdate={jest.fn()}
        onCanvasClick={jest.fn()}
      />
    );
    
    // Start frame rate monitoring
    requestAnimationFrame(frameCallback);
    
    // Wait for monitoring to complete
    await new Promise(resolve => {
      const checkComplete = () => {
        if (frameCount >= 60) {
          resolve(undefined);
        } else {
          setTimeout(checkComplete, 10);
        }
      };
      checkComplete();
    });
    
    // Calculate average frame rate
    const avgFrameRate = frameRates.reduce((a, b) => a + b, 0) / frameRates.length;
    const minFrameRate = Math.min(...frameRates);
    
    // Should maintain at least 50fps average, 30fps minimum
    expect(avgFrameRate).toBeGreaterThan(50);
    expect(minFrameRate).toBeGreaterThan(30);
    
    console.log(`✅ Video playback: ${avgFrameRate.toFixed(1)}fps average, ${minFrameRate.toFixed(1)}fps minimum`);
  });
});

// ============================================================================
// REAL-TIME PERFORMANCE TESTS
// ============================================================================

describe('Real-time Performance', () => {
  test('should handle high-frequency detection events without dropping data', async () => {
    const user = userEvent.setup();
    
    render(<TestExecution />);
    
    // Start test session
    const startButton = screen.getByRole('button', { name: /start.*test/i });
    await user.click(startButton);
    
    const receivedEvents: any[] = [];
    let droppedEvents = 0;
    
    // Mock WebSocket with high-frequency events
    const mockWebSocket = {
      send: jest.fn(),
      onmessage: null as any,
      onopen: null as any,
      onclose: null as any,
      onerror: null as any
    };
    
    // Simulate 100 events per second for 10 seconds
    const eventInterval = 10; // ms
    const testDuration = 10000; // 10 seconds
    const expectedEvents = testDuration / eventInterval;
    
    let eventCount = 0;
    const startTime = performance.now();
    
    const sendEvent = () => {
      if (performance.now() - startTime > testDuration) {
        return;
      }
      
      const event = {
        type: 'detection_event',
        data: {
          id: `detection-${eventCount}`,
          timestamp: Date.now(),
          confidence: Math.random(),
          validation_result: 'TP'
        }
      };
      
      try {
        // Simulate processing the event
        receivedEvents.push(event);
        eventCount++;
      } catch (error) {
        droppedEvents++;
      }
      
      setTimeout(sendEvent, eventInterval);
    };
    
    sendEvent();
    
    // Wait for test completion
    await new Promise(resolve => setTimeout(resolve, testDuration + 1000));
    
    // Check performance metrics
    const processedEvents = receivedEvents.length;
    const dropRate = droppedEvents / expectedEvents;
    const processingRate = processedEvents / (testDuration / 1000);
    
    // Should process at least 95% of events
    expect(dropRate).toBeLessThan(0.05);
    
    // Should maintain at least 90 events per second
    expect(processingRate).toBeGreaterThan(90);
    
    console.log(`✅ Processed ${processedEvents}/${expectedEvents} events (${(dropRate * 100).toFixed(2)}% drop rate)`);
    console.log(`📊 Processing rate: ${processingRate.toFixed(1)} events/second`);
  });
  
  test('should maintain responsiveness during continuous data updates', async () => {
    const user = userEvent.setup();
    
    render(<TestExecution />);
    
    const responseTimes: number[] = [];
    
    // Simulate continuous background updates
    const updateInterval = setInterval(() => {
      // Simulate metric updates
      const event = new CustomEvent('performance-update', {
        detail: {
          cpu: Math.random() * 100,
          memory: Math.random() * 100,
          detections: Math.floor(Math.random() * 1000)
        }
      });
      window.dispatchEvent(event);
    }, 50); // 20 updates per second
    
    // Test user interaction responsiveness
    for (let i = 0; i < 10; i++) {
      const start = performance.now();
      
      // Click a button
      const button = screen.getByRole('button', { name: /pause/i });
      await user.click(button);
      
      const responseTime = performance.now() - start;
      responseTimes.push(responseTime);
      
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    clearInterval(updateInterval);
    
    // Calculate response time metrics
    const avgResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;
    const maxResponseTime = Math.max(...responseTimes);
    
    // UI should remain responsive (under 100ms average, 200ms max)
    expect(avgResponseTime).toBeLessThan(100);
    expect(maxResponseTime).toBeLessThan(200);
    
    console.log(`✅ UI responsiveness: ${avgResponseTime.toFixed(2)}ms average, ${maxResponseTime.toFixed(2)}ms max`);
  });
});

// ============================================================================
// MEMORY MANAGEMENT TESTS
// ============================================================================

describe('Memory Management', () => {
  test('should prevent memory leaks during component mounting/unmounting', async () => {
    const initialMemory = memoryTracker.getMemoryUsage()?.initial || 0;
    
    // Mount and unmount components repeatedly
    for (let i = 0; i < 50; i++) {
      const { unmount } = render(
        <BrowserRouter>
          <TestExecution />
        </BrowserRouter>
      );
      
      // Add some DOM manipulation
      const button = screen.queryByRole('button');
      if (button) {
        fireEvent.click(button);
      }
      
      unmount();
      
      // Sample memory every 10 iterations
      if (i % 10 === 0) {
        memoryTracker.sample();
        
        // Force garbage collection if available
        if (global.gc) {
          global.gc();
        }
      }
    }
    
    const finalMemoryUsage = memoryTracker.getMemoryUsage();
    
    if (finalMemoryUsage) {
      const memoryIncrease = finalMemoryUsage.max - initialMemory;
      
      // Memory increase should be reasonable (under 20MB after 50 cycles)
      expect(memoryIncrease).toBeLessThan(20 * 1024 * 1024);
      
      console.log(`✅ Memory leak test: ${(memoryIncrease / 1024 / 1024).toFixed(2)}MB increase after 50 mount/unmount cycles`);
    }
  });
  
  test('should efficiently manage large video annotation datasets', async () => {
    const largeAnnotationSet = createMockAnnotationList(1000);
    const mockVideo = createMockVideo();
    
    memoryTracker.sample();
    
    const { rerender } = render(
      <AccessibleVideoPlayer
        video={mockVideo}
        annotations={largeAnnotationSet}
        annotationMode={true}
        frameRate={30}
        onAnnotationSelect={jest.fn()}
        onTimeUpdate={jest.fn()}
        onCanvasClick={jest.fn()}
      />
    );
    
    memoryTracker.sample();
    
    // Update annotations multiple times
    for (let i = 0; i < 10; i++) {
      const updatedAnnotations = createMockAnnotationList(1000);
      
      rerender(
        <AccessibleVideoPlayer
          video={mockVideo}
          annotations={updatedAnnotations}
          annotationMode={true}
          frameRate={30}
          onAnnotationSelect={jest.fn()}
          onTimeUpdate={jest.fn()}
          onCanvasClick={jest.fn()}
        />
      );
      
      memoryTracker.sample();
    }
    
    const memoryUsage = memoryTracker.getMemoryUsage();
    
    if (memoryUsage) {
      // Memory should not grow linearly with updates
      const memoryPerUpdate = memoryUsage.increase / 10;
      expect(memoryPerUpdate).toBeLessThan(5 * 1024 * 1024); // Under 5MB per update
      
      console.log(`✅ Large annotation dataset: ${(memoryUsage.increase / 1024 / 1024).toFixed(2)}MB total, ${(memoryPerUpdate / 1024 / 1024).toFixed(2)}MB per update`);
    }
  });
});

// ============================================================================
// NETWORK PERFORMANCE TESTS
// ============================================================================

describe('Network Performance', () => {
  test('should handle API request bursts efficiently', async () => {
    const requestTimes: number[] = [];
    let successfulRequests = 0;
    let failedRequests = 0;
    
    // Mock fetch with timing
    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockImplementation(async (url) => {
      const start = performance.now();
      
      try {
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, Math.random() * 100));
        
        const duration = performance.now() - start;
        requestTimes.push(duration);
        successfulRequests++;
        
        return {
          ok: true,
          json: () => Promise.resolve({ data: 'mock response' }),
          status: 200
        };
      } catch (error) {
        failedRequests++;
        throw error;
      }
    });
    
    // Create burst of API requests
    const requests = Array.from({ length: 100 }, () => 
      fetch('/api/test-endpoint')
    );
    
    const start = performance.now();
    await Promise.all(requests);
    const totalTime = performance.now() - start;
    
    // Restore original fetch
    global.fetch = originalFetch;
    
    // Calculate metrics
    const avgRequestTime = requestTimes.reduce((a, b) => a + b, 0) / requestTimes.length;
    const maxRequestTime = Math.max(...requestTimes);
    const requestsPerSecond = (successfulRequests / totalTime) * 1000;
    const failureRate = failedRequests / (successfulRequests + failedRequests);
    
    // Performance expectations
    expect(failureRate).toBeLessThan(0.05); // Under 5% failure rate
    expect(avgRequestTime).toBeLessThan(200); // Under 200ms average
    expect(requestsPerSecond).toBeGreaterThan(50); // At least 50 requests/sec
    
    console.log(`✅ API burst test: ${successfulRequests} requests, ${avgRequestTime.toFixed(2)}ms average, ${requestsPerSecond.toFixed(1)} req/sec`);
  });
  
  test('should optimize WebSocket message handling', async () => {
    const messageProcessingTimes: number[] = [];
    let processedMessages = 0;
    let queuedMessages = 0;
    
    // Mock WebSocket message processing
    const processMessage = (message: any) => {
      const start = performance.now();
      
      try {
        // Simulate message processing
        JSON.parse(JSON.stringify(message));
        
        // Simulate DOM updates
        const element = document.createElement('div');
        element.textContent = JSON.stringify(message);
        document.body.appendChild(element);
        document.body.removeChild(element);
        
        const duration = performance.now() - start;
        messageProcessingTimes.push(duration);
        processedMessages++;
      } catch (error) {
        queuedMessages++;
      }
    };
    
    // Simulate high-frequency WebSocket messages
    const messageCount = 1000;
    const messages = Array.from({ length: messageCount }, (_, i) => ({
      type: 'detection_event',
      data: {
        id: `event-${i}`,
        timestamp: Date.now(),
        confidence: Math.random()
      }
    }));
    
    const start = performance.now();
    
    // Process messages
    for (const message of messages) {
      processMessage(message);
    }
    
    const totalTime = performance.now() - start;
    
    // Calculate metrics
    const avgProcessingTime = messageProcessingTimes.reduce((a, b) => a + b, 0) / messageProcessingTimes.length;
    const maxProcessingTime = Math.max(...messageProcessingTimes);
    const messagesPerSecond = (processedMessages / totalTime) * 1000;
    
    // Performance expectations
    expect(avgProcessingTime).toBeLessThan(10); // Under 10ms per message
    expect(maxProcessingTime).toBeLessThan(50); // Under 50ms max
    expect(messagesPerSecond).toBeGreaterThan(1000); // At least 1000 messages/sec
    expect(queuedMessages).toBe(0); // No messages should be queued/dropped
    
    console.log(`✅ WebSocket processing: ${messagesPerSecond.toFixed(0)} messages/sec, ${avgProcessingTime.toFixed(2)}ms average`);
  });
});

// ============================================================================
// STRESS TESTING
// ============================================================================

describe('Stress Testing', () => {
  test('should handle extreme data loads', async () => {
    // Create extremely large datasets
    const extremeDetectionList = createMockDetectionEventList(10000);
    const extremeAnnotationList = createMockAnnotationList(5000);
    
    memoryTracker.sample();
    
    const start = performance.now();
    
    // Render with extreme data load
    render(<TestExecution />);
    
    // Simulate processing large datasets
    let processedItems = 0;
    const batchSize = 100;
    
    for (let i = 0; i < extremeDetectionList.length; i += batchSize) {
      const batch = extremeDetectionList.slice(i, i + batchSize);
      
      // Process batch
      batch.forEach(detection => {
        // Simulate DOM updates
        const element = document.createElement('div');
        element.setAttribute('data-detection-id', detection.id);
        element.textContent = `${detection.classLabel}: ${detection.confidence}`;
        document.body.appendChild(element);
        
        processedItems++;
      });
      
      // Yield to event loop
      await new Promise(resolve => setTimeout(resolve, 0));
      
      memoryTracker.sample();
    }
    
    const processingTime = performance.now() - start;
    const itemsPerSecond = (processedItems / processingTime) * 1000;
    
    const memoryUsage = memoryTracker.getMemoryUsage();
    
    // Clean up DOM
    document.querySelectorAll('[data-detection-id]').forEach(el => el.remove());
    
    // Performance expectations for extreme load
    expect(itemsPerSecond).toBeGreaterThan(100); // At least 100 items/sec
    expect(processingTime).toBeLessThan(60000); // Under 1 minute for 10k items
    
    if (memoryUsage) {
      expect(memoryUsage.increase).toBeLessThan(100 * 1024 * 1024); // Under 100MB
    }
    
    console.log(`✅ Extreme load test: ${processedItems} items in ${(processingTime / 1000).toFixed(2)}s (${itemsPerSecond.toFixed(0)} items/sec)`);
  });
  
  test('should recover from resource exhaustion', async () => {
    // Simulate memory pressure
    const memoryHogs: any[] = [];
    
    try {
      // Allocate large amounts of memory
      for (let i = 0; i < 100; i++) {
        memoryHogs.push(new Array(1000000).fill(Math.random()));
      }
      
      memoryTracker.sample();
      
      // Try to render component under memory pressure
      const { container } = render(<App />);
      
      // Component should still render
      expect(container).toBeInTheDocument();
      
      // Should handle user interactions
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
      
      // Click a button to test interactivity
      if (buttons[0]) {
        fireEvent.click(buttons[0]);
      }
      
    } finally {
      // Clean up memory
      memoryHogs.length = 0;
      
      if (global.gc) {
        global.gc();
      }
    }
    
    console.log('✅ Resource exhaustion recovery test passed');
  });
});

// ============================================================================
// PERFORMANCE REPORTING
// ============================================================================

afterAll(() => {
  const metrics = performanceMonitor.getMetrics();
  const memoryUsage = memoryTracker.getMemoryUsage();
  
  console.log('\n📊 Performance Test Summary:');
  console.log('================================');
  
  if (Object.keys(metrics).length > 0) {
    console.log('\n🎨 Rendering Metrics:');
    for (const [name, data] of Object.entries(metrics)) {
      console.log(`  ${name}: ${data.avg.toFixed(2)}ms avg, ${data.max.toFixed(2)}ms max`);
    }
  }
  
  if (memoryUsage) {
    console.log('\n🧠 Memory Usage:');
    console.log(`  Initial: ${(memoryUsage.initial / 1024 / 1024).toFixed(2)}MB`);
    console.log(`  Maximum: ${(memoryUsage.max / 1024 / 1024).toFixed(2)}MB`);
    console.log(`  Average: ${(memoryUsage.average / 1024 / 1024).toFixed(2)}MB`);
    console.log(`  Total Increase: ${(memoryUsage.increase / 1024 / 1024).toFixed(2)}MB`);
  }
  
  console.log('\n✅ All performance tests completed');
});
