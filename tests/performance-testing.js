/**
 * UI Performance Testing Suite
 * Tests for load times, rendering performance, and responsiveness
 */

const puppeteer = require('puppeteer');
const lighthouse = require('lighthouse');
const chromeLauncher = require('chrome-launcher');

class UIPerformanceTester {
  constructor(baseUrl = 'http://localhost:3000') {
    this.baseUrl = baseUrl;
    this.browser = null;
    this.page = null;
    this.results = {
      loadTimes: {},
      coreWebVitals: {},
      lighthouse: {},
      interactions: {}
    };
  }

  async setup() {
    this.browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    this.page = await this.browser.newPage();
    
    // Set viewport for consistent testing
    await this.page.setViewport({ width: 1366, height: 768 });
  }

  async teardown() {
    if (this.browser) {
      await this.browser.close();
    }
  }

  async measurePageLoadTimes() {
    const pages = [
      '/',
      '/projects',
      '/test-execution',
      '/ground-truth',
      '/results'
    ];

    console.log('🚀 Measuring page load times...');

    for (const path of pages) {
      const url = `${this.baseUrl}${path}`;
      
      try {
        // Navigate and measure
        const startTime = Date.now();
        await this.page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });
        const endTime = Date.now();
        
        // Get performance metrics
        const performanceTiming = JSON.parse(
          await this.page.evaluate(() => JSON.stringify(performance.timing))
        );

        this.results.loadTimes[path] = {
          total: endTime - startTime,
          domContentLoaded: performanceTiming.domContentLoadedEventEnd - performanceTiming.navigationStart,
          firstByte: performanceTiming.responseStart - performanceTiming.navigationStart,
          domComplete: performanceTiming.domComplete - performanceTiming.navigationStart
        };

        console.log(`✓ ${path}: ${endTime - startTime}ms total load time`);
      } catch (error) {
        console.error(`✗ Failed to load ${path}:`, error.message);
        this.results.loadTimes[path] = { error: error.message };
      }
    }
  }

  async measureCoreWebVitals() {
    console.log('📊 Measuring Core Web Vitals...');
    
    try {
      await this.page.goto(this.baseUrl, { waitUntil: 'networkidle0' });
      
      const vitals = await this.page.evaluate(() => {
        return new Promise((resolve) => {
          const vitals = {};
          
          // Largest Contentful Paint (LCP)
          new PerformanceObserver((entryList) => {
            const entries = entryList.getEntries();
            if (entries.length > 0) {
              vitals.lcp = entries[entries.length - 1].startTime;
            }
          }).observe({ entryTypes: ['largest-contentful-paint'] });

          // First Input Delay (FID) simulation
          vitals.fid = 'Cannot measure in headless mode';

          // Cumulative Layout Shift (CLS)
          let cls = 0;
          new PerformanceObserver((entryList) => {
            for (const entry of entryList.getEntries()) {
              if (!entry.hadRecentInput) {
                cls += entry.value;
              }
            }
            vitals.cls = cls;
          }).observe({ entryTypes: ['layout-shift'] });

          setTimeout(() => resolve(vitals), 3000);
        });
      });

      this.results.coreWebVitals = vitals;
      console.log('✓ Core Web Vitals measured');
    } catch (error) {
      console.error('✗ Failed to measure Core Web Vitals:', error.message);
    }
  }

  async runLighthouseAudit() {
    console.log('🔍 Running Lighthouse audit...');
    
    try {
      const chrome = await chromeLauncher.launch({ chromeFlags: ['--headless'] });
      const options = {
        logLevel: 'info',
        output: 'json',
        onlyCategories: ['performance', 'accessibility', 'best-practices'],
        port: chrome.port,
      };

      const runnerResult = await lighthouse(this.baseUrl, options);
      await chrome.kill();

      this.results.lighthouse = {
        performance: runnerResult.lhr.categories.performance.score * 100,
        accessibility: runnerResult.lhr.categories.accessibility.score * 100,
        bestPractices: runnerResult.lhr.categories['best-practices'].score * 100,
        audits: {
          firstContentfulPaint: runnerResult.lhr.audits['first-contentful-paint'].displayValue,
          largestContentfulPaint: runnerResult.lhr.audits['largest-contentful-paint'].displayValue,
          cumulativeLayoutShift: runnerResult.lhr.audits['cumulative-layout-shift'].displayValue,
          totalBlockingTime: runnerResult.lhr.audits['total-blocking-time'].displayValue
        }
      };

      console.log(`✓ Lighthouse scores - Performance: ${this.results.lighthouse.performance}%, Accessibility: ${this.results.lighthouse.accessibility}%`);
    } catch (error) {
      console.error('✗ Lighthouse audit failed:', error.message);
    }
  }

  async measureInteractionResponsiveness() {
    console.log('⚡ Measuring interaction responsiveness...');
    
    try {
      await this.page.goto(`${this.baseUrl}/projects`, { waitUntil: 'networkidle0' });

      // Measure button click responsiveness
      const buttonClickTime = await this.page.evaluate(async () => {
        const button = document.querySelector('button[aria-label*="New"]') || 
                      document.querySelector('button:contains("New")') ||
                      document.querySelector('button');
        
        if (!button) return null;

        const startTime = performance.now();
        button.click();
        
        // Wait for any visual feedback or state change
        await new Promise(resolve => {
          const observer = new MutationObserver(() => {
            observer.disconnect();
            resolve();
          });
          observer.observe(document.body, { childList: true, subtree: true });
          
          // Fallback timeout
          setTimeout(resolve, 100);
        });
        
        return performance.now() - startTime;
      });

      // Measure form input responsiveness
      const inputResponseTime = await this.page.evaluate(async () => {
        const input = document.querySelector('input[type="text"]');
        if (!input) return null;

        const startTime = performance.now();
        input.focus();
        input.value = 'test';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        
        return performance.now() - startTime;
      });

      this.results.interactions = {
        buttonClick: buttonClickTime,
        inputResponse: inputResponseTime
      };

      console.log('✓ Interaction responsiveness measured');
    } catch (error) {
      console.error('✗ Failed to measure interactions:', error.message);
    }
  }

  async testResponsiveBreakpoints() {
    console.log('📱 Testing responsive breakpoints...');
    
    const breakpoints = [
      { name: 'Mobile', width: 375, height: 667 },
      { name: 'Tablet', width: 768, height: 1024 },
      { name: 'Desktop', width: 1366, height: 768 },
      { name: 'Large Desktop', width: 1920, height: 1080 }
    ];

    const responsiveResults = {};

    for (const breakpoint of breakpoints) {
      await this.page.setViewport({ 
        width: breakpoint.width, 
        height: breakpoint.height 
      });
      
      await this.page.goto(this.baseUrl, { waitUntil: 'networkidle0' });
      
      // Check for responsive elements
      const responsiveCheck = await this.page.evaluate(() => {
        const sidebar = document.querySelector('[role="navigation"]');
        const header = document.querySelector('header, [role="banner"]');
        const mainContent = document.querySelector('main, [role="main"]');
        
        return {
          hasSidebar: !!sidebar,
          hasHeader: !!header,
          hasMainContent: !!mainContent,
          sidebarVisible: sidebar ? getComputedStyle(sidebar).display !== 'none' : false,
          layoutOverflow: document.body.scrollWidth > window.innerWidth
        };
      });

      responsiveResults[breakpoint.name] = {
        viewport: { width: breakpoint.width, height: breakpoint.height },
        ...responsiveCheck
      };

      console.log(`✓ ${breakpoint.name} (${breakpoint.width}x${breakpoint.height}) tested`);
    }

    this.results.responsive = responsiveResults;
  }

  async measureMemoryUsage() {
    console.log('🧠 Measuring memory usage...');
    
    try {
      await this.page.goto(this.baseUrl, { waitUntil: 'networkidle0' });
      
      // Navigate through different pages to stress test memory
      const pages = ['/projects', '/test-execution', '/results', '/'];
      
      const memoryMeasurements = [];
      
      for (const path of pages) {
        await this.page.goto(`${this.baseUrl}${path}`, { waitUntil: 'networkidle0' });
        
        const metrics = await this.page.metrics();
        memoryMeasurements.push({
          path,
          jsHeapUsedSize: metrics.JSHeapUsedSize,
          jsHeapTotalSize: metrics.JSHeapTotalSize,
          nodes: metrics.Nodes,
          documents: metrics.Documents
        });
        
        // Wait between navigations
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      this.results.memory = {
        measurements: memoryMeasurements,
        peakUsage: Math.max(...memoryMeasurements.map(m => m.jsHeapUsedSize)),
        averageUsage: memoryMeasurements.reduce((sum, m) => sum + m.jsHeapUsedSize, 0) / memoryMeasurements.length
      };

      console.log('✓ Memory usage measured');
    } catch (error) {
      console.error('✗ Failed to measure memory usage:', error.message);
    }
  }

  async runAllTests() {
    console.log('🎯 Starting comprehensive UI performance testing...\n');
    
    try {
      await this.setup();
      
      await this.measurePageLoadTimes();
      await this.measureCoreWebVitals();
      await this.runLighthouseAudit();
      await this.measureInteractionResponsiveness();
      await this.testResponsiveBreakpoints();
      await this.measureMemoryUsage();
      
      await this.teardown();
      
      return this.generateReport();
    } catch (error) {
      console.error('🚨 Testing failed:', error.message);
      await this.teardown();
      throw error;
    }
  }

  generateReport() {
    const report = {
      timestamp: new Date().toISOString(),
      summary: this.generateSummary(),
      detailed: this.results,
      recommendations: this.generateRecommendations()
    };

    console.log('\n📋 PERFORMANCE TEST REPORT');
    console.log('=' .repeat(50));
    console.log(JSON.stringify(report.summary, null, 2));
    
    return report;
  }

  generateSummary() {
    const avgLoadTime = Object.values(this.results.loadTimes)
      .filter(result => !result.error)
      .reduce((sum, result, _, arr) => sum + result.total / arr.length, 0);

    return {
      averageLoadTime: `${Math.round(avgLoadTime)}ms`,
      lighthouseScores: this.results.lighthouse,
      coreWebVitals: this.results.coreWebVitals,
      interactionTimes: this.results.interactions,
      memoryUsage: {
        peak: `${Math.round(this.results.memory?.peakUsage / 1024 / 1024 || 0)}MB`,
        average: `${Math.round(this.results.memory?.averageUsage / 1024 / 1024 || 0)}MB`
      }
    };
  }

  generateRecommendations() {
    const recommendations = [];
    
    // Load time recommendations
    const avgLoadTime = Object.values(this.results.loadTimes)
      .filter(result => !result.error)
      .reduce((sum, result, _, arr) => sum + result.total / arr.length, 0);
      
    if (avgLoadTime > 3000) {
      recommendations.push({
        priority: 'high',
        category: 'performance',
        issue: 'Slow page load times',
        suggestion: 'Implement code splitting, optimize bundle size, use lazy loading'
      });
    }

    // Lighthouse score recommendations
    if (this.results.lighthouse.performance < 90) {
      recommendations.push({
        priority: 'high',
        category: 'performance',
        issue: 'Low Lighthouse performance score',
        suggestion: 'Optimize images, eliminate render-blocking resources, minimize main thread work'
      });
    }

    if (this.results.lighthouse.accessibility < 95) {
      recommendations.push({
        priority: 'medium',
        category: 'accessibility',
        issue: 'Accessibility score below recommended threshold',
        suggestion: 'Improve ARIA labels, ensure proper color contrast, enhance keyboard navigation'
      });
    }

    // Memory usage recommendations
    const peakMemoryMB = this.results.memory?.peakUsage / 1024 / 1024 || 0;
    if (peakMemoryMB > 100) {
      recommendations.push({
        priority: 'medium',
        category: 'memory',
        issue: 'High memory usage',
        suggestion: 'Implement component cleanup, optimize state management, reduce memory leaks'
      });
    }

    return recommendations;
  }
}

// Export for use in other test files
module.exports = UIPerformanceTester;

// Run tests if called directly
if (require.main === module) {
  const tester = new UIPerformanceTester();
  tester.runAllTests()
    .then(report => {
      console.log('\n✅ All performance tests completed successfully');
      process.exit(0);
    })
    .catch(error => {
      console.error('\n❌ Performance testing failed:', error);
      process.exit(1);
    });
}