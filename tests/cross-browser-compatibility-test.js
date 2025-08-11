/**
 * Cross-Browser Compatibility Testing Suite
 * Tests UI consistency across different browsers and platforms
 */

const puppeteer = require('puppeteer');

class CrossBrowserTester {
  constructor(baseUrl = 'http://localhost:3000') {
    this.baseUrl = baseUrl;
    this.browsers = [];
    this.results = {
      compatibility: {},
      screenshots: {},
      performance: {},
      featureSupport: {}
    };
  }

  async setup() {
    // Launch multiple browser instances for testing
    const browserConfigs = [
      {
        name: 'Chrome',
        options: { headless: true, args: ['--no-sandbox'] }
      },
      {
        name: 'Firefox',
        product: 'firefox',
        options: { headless: true }
      },
      {
        name: 'Safari',
        // Note: Safari testing requires actual Safari browser
        skip: process.platform !== 'darwin'
      }
    ];

    for (const config of browserConfigs) {
      if (config.skip) continue;
      
      try {
        const browser = await puppeteer.launch({
          product: config.product,
          ...config.options
        });
        
        this.browsers.push({
          name: config.name,
          instance: browser
        });
        
        console.log(`✓ ${config.name} browser launched successfully`);
      } catch (error) {
        console.warn(`⚠ Failed to launch ${config.name}: ${error.message}`);
      }
    }
  }

  async teardown() {
    for (const browser of this.browsers) {
      await browser.instance.close();
    }
  }

  async testLayoutConsistency() {
    console.log('🎨 Testing layout consistency across browsers...');
    
    const pages = ['/', '/projects', '/test-execution', '/dashboard'];
    
    for (const path of pages) {
      const url = `${this.baseUrl}${path}`;
      const pageResults = {};
      
      for (const browser of this.browsers) {
        try {
          const page = await browser.instance.newPage();
          await page.setViewport({ width: 1366, height: 768 });
          await page.goto(url, { waitUntil: 'networkidle0' });
          
          // Capture layout metrics
          const layoutMetrics = await page.evaluate(() => {
            const body = document.body;
            const header = document.querySelector('header, [role="banner"]');
            const nav = document.querySelector('nav, [role="navigation"]');
            const main = document.querySelector('main, [role="main"]');
            
            return {
              bodyDimensions: {
                width: body.offsetWidth,
                height: body.offsetHeight,
                scrollWidth: body.scrollWidth,
                scrollHeight: body.scrollHeight
              },
              headerHeight: header ? header.offsetHeight : 0,
              navWidth: nav ? nav.offsetWidth : 0,
              mainContentArea: main ? {
                width: main.offsetWidth,
                height: main.offsetHeight
              } : null,
              hasHorizontalScroll: body.scrollWidth > window.innerWidth,
              hasVerticalOverflow: body.scrollHeight > window.innerHeight
            };
          });
          
          // Check for layout issues
          const layoutIssues = this.analyzeLayout(layoutMetrics);
          
          pageResults[browser.name] = {
            metrics: layoutMetrics,
            issues: layoutIssues,
            status: layoutIssues.length === 0 ? 'pass' : 'warning'
          };
          
          await page.close();
          
        } catch (error) {
          pageResults[browser.name] = {
            error: error.message,
            status: 'fail'
          };
        }
      }
      
      this.results.compatibility[path] = pageResults;
    }
  }

  analyzeLayout(metrics) {
    const issues = [];
    
    // Check for horizontal overflow
    if (metrics.hasHorizontalScroll) {
      issues.push({
        severity: 'warning',
        issue: 'Horizontal scrolling detected',
        description: 'Content may be wider than viewport'
      });
    }
    
    // Check for unusual header height
    if (metrics.headerHeight > 100) {
      issues.push({
        severity: 'info',
        issue: 'Large header height',
        description: `Header height is ${metrics.headerHeight}px`
      });
    }
    
    // Check navigation width consistency
    if (metrics.navWidth > 0 && (metrics.navWidth < 200 || metrics.navWidth > 300)) {
      issues.push({
        severity: 'info',
        issue: 'Unusual navigation width',
        description: `Navigation width is ${metrics.navWidth}px`
      });
    }
    
    return issues;
  }

  async testInteractiveElements() {
    console.log('🖱 Testing interactive elements across browsers...');
    
    for (const browser of this.browsers) {
      const page = await browser.instance.newPage();
      const interactionResults = {};
      
      try {
        await page.goto(this.baseUrl, { waitUntil: 'networkidle0' });
        
        // Test button interactions
        const buttonTest = await this.testButtons(page);
        interactionResults.buttons = buttonTest;
        
        // Test form interactions
        await page.goto(`${this.baseUrl}/projects`, { waitUntil: 'networkidle0' });
        const formTest = await this.testForms(page);
        interactionResults.forms = formTest;
        
        // Test navigation interactions
        const navTest = await this.testNavigation(page);
        interactionResults.navigation = navTest;
        
        this.results.compatibility[`interactions_${browser.name}`] = interactionResults;
        
      } catch (error) {
        this.results.compatibility[`interactions_${browser.name}`] = {
          error: error.message
        };
      }
      
      await page.close();
    }
  }

  async testButtons(page) {
    const results = {
      clickable: 0,
      total: 0,
      issues: []
    };
    
    try {
      const buttons = await page.$$('button, [role="button"], input[type="button"], input[type="submit"]');
      results.total = buttons.length;
      
      for (const button of buttons) {
        try {
          const isVisible = await button.isIntersectingViewport();
          const isEnabled = await page.evaluate(el => !el.disabled, button);
          
          if (isVisible && isEnabled) {
            await button.click();
            results.clickable++;
            
            // Wait for any potential navigation or state changes
            await page.waitForTimeout(100);
          }
        } catch (error) {
          results.issues.push({
            element: 'button',
            issue: error.message
          });
        }
      }
      
      results.successRate = (results.clickable / results.total) * 100;
      
    } catch (error) {
      results.error = error.message;
    }
    
    return results;
  }

  async testForms(page) {
    const results = {
      inputs: 0,
      workingInputs: 0,
      selects: 0,
      workingSelects: 0,
      issues: []
    };
    
    try {
      // Test text inputs
      const textInputs = await page.$$('input[type="text"], input[type="email"], textarea');
      results.inputs = textInputs.length;
      
      for (const input of textInputs) {
        try {
          await input.focus();
          await input.type('test input');
          
          const value = await page.evaluate(el => el.value, input);
          if (value === 'test input') {
            results.workingInputs++;
          }
          
          await input.click({ clickCount: 3 }); // Select all
          await input.type(''); // Clear
        } catch (error) {
          results.issues.push({
            element: 'text input',
            issue: error.message
          });
        }
      }
      
      // Test select dropdowns
      const selects = await page.$$('select');
      results.selects = selects.length;
      
      for (const select of selects) {
        try {
          const options = await select.$$('option');
          if (options.length > 1) {
            await select.select(await page.evaluate(opt => opt.value, options[1]));
            results.workingSelects++;
          }
        } catch (error) {
          results.issues.push({
            element: 'select',
            issue: error.message
          });
        }
      }
      
    } catch (error) {
      results.error = error.message;
    }
    
    return results;
  }

  async testNavigation(page) {
    const results = {
      links: 0,
      workingLinks: 0,
      issues: []
    };
    
    try {
      const navLinks = await page.$$('nav a, [role="navigation"] a, [role="menuitem"]');
      results.links = navLinks.length;
      
      for (const link of navLinks) {
        try {
          const href = await page.evaluate(el => el.href || el.getAttribute('href'), link);
          
          if (href && !href.includes('javascript:') && !href.includes('#')) {
            await link.click();
            
            // Wait for navigation
            await page.waitForTimeout(500);
            
            // Check if we navigated successfully
            const currentUrl = page.url();
            if (currentUrl !== this.baseUrl) {
              results.workingLinks++;
            }
            
            // Go back to test page
            await page.goBack();
            await page.waitForTimeout(200);
          }
        } catch (error) {
          results.issues.push({
            element: 'navigation link',
            issue: error.message
          });
        }
      }
      
    } catch (error) {
      results.error = error.message;
    }
    
    return results;
  }

  async captureVisualComparison() {
    console.log('📸 Capturing visual comparisons across browsers...');
    
    const pages = ['/', '/projects', '/test-execution'];
    
    for (const path of pages) {
      const url = `${this.baseUrl}${path}`;
      
      for (const browser of this.browsers) {
        try {
          const page = await browser.instance.newPage();
          await page.setViewport({ width: 1366, height: 768 });
          await page.goto(url, { waitUntil: 'networkidle0' });
          
          const screenshot = await page.screenshot({
            fullPage: true,
            encoding: 'base64'
          });
          
          if (!this.results.screenshots[path]) {
            this.results.screenshots[path] = {};
          }
          
          this.results.screenshots[path][browser.name] = screenshot;
          
          await page.close();
          
        } catch (error) {
          console.error(`Failed to capture ${browser.name} screenshot for ${path}: ${error.message}`);
        }
      }
    }
  }

  async testFeatureSupport() {
    console.log('🧪 Testing modern web feature support...');
    
    const features = [
      'CSS Grid',
      'CSS Flexbox',
      'CSS Custom Properties',
      'ES6 Modules',
      'Intersection Observer',
      'Resize Observer',
      'WebSockets',
      'Local Storage',
      'Session Storage',
      'IndexedDB',
      'Service Workers'
    ];
    
    for (const browser of this.browsers) {
      const page = await browser.instance.newPage();
      
      try {
        await page.goto(this.baseUrl, { waitUntil: 'networkidle0' });
        
        const featureSupport = await page.evaluate((features) => {
          const support = {};
          
          // CSS Feature Detection
          support['CSS Grid'] = CSS.supports('display', 'grid');
          support['CSS Flexbox'] = CSS.supports('display', 'flex');
          support['CSS Custom Properties'] = CSS.supports('--custom', 'property');
          
          // JavaScript Feature Detection
          support['ES6 Modules'] = typeof Symbol !== 'undefined' && typeof Symbol.iterator !== 'undefined';
          support['Intersection Observer'] = 'IntersectionObserver' in window;
          support['Resize Observer'] = 'ResizeObserver' in window;
          support['WebSockets'] = 'WebSocket' in window;
          support['Local Storage'] = 'localStorage' in window && localStorage !== null;
          support['Session Storage'] = 'sessionStorage' in window && sessionStorage !== null;
          support['IndexedDB'] = 'indexedDB' in window;
          support['Service Workers'] = 'serviceWorker' in navigator;
          
          return support;
        }, features);
        
        this.results.featureSupport[browser.name] = featureSupport;
        
      } catch (error) {
        this.results.featureSupport[browser.name] = {
          error: error.message
        };
      }
      
      await page.close();
    }
  }

  async runAllTests() {
    console.log('🌐 Starting comprehensive cross-browser testing...\n');
    
    try {
      await this.setup();
      
      if (this.browsers.length === 0) {
        throw new Error('No browsers available for testing');
      }
      
      await this.testLayoutConsistency();
      await this.testInteractiveElements();
      await this.captureVisualComparison();
      await this.testFeatureSupport();
      
      await this.teardown();
      
      return this.generateReport();
    } catch (error) {
      console.error('🚨 Cross-browser testing failed:', error.message);
      await this.teardown();
      throw error;
    }
  }

  generateReport() {
    const report = {
      timestamp: new Date().toISOString(),
      browsersTestedCount: this.browsers.length,
      summary: this.generateSummary(),
      detailed: this.results,
      recommendations: this.generateRecommendations()
    };

    console.log('\n🎯 CROSS-BROWSER COMPATIBILITY REPORT');
    console.log('=' .repeat(50));
    console.log(`Browsers Tested: ${this.browsers.map(b => b.name).join(', ')}`);
    console.log(`Overall Compatibility: ${report.summary.overallCompatibility}%`);
    console.log('\nKey Findings:');
    report.recommendations.forEach(rec => {
      console.log(`${rec.priority === 'high' ? '🔴' : '🟡'} ${rec.issue}`);
    });
    
    return report;
  }

  generateSummary() {
    const browserNames = this.browsers.map(b => b.name);
    const totalTests = Object.keys(this.results.compatibility).length;
    let passingTests = 0;

    // Count passing tests
    Object.values(this.results.compatibility).forEach(pageResult => {
      if (typeof pageResult === 'object' && !pageResult.error) {
        const browserResults = Object.values(pageResult);
        const allPassing = browserResults.every(result => 
          result.status === 'pass' || result.status === 'warning'
        );
        if (allPassing) passingTests++;
      }
    });

    const overallCompatibility = totalTests > 0 ? Math.round((passingTests / totalTests) * 100) : 0;

    return {
      browsersTestedCount: browserNames.length,
      browserNames,
      overallCompatibility,
      totalTests,
      passingTests,
      featureSupport: this.summarizeFeatureSupport()
    };
  }

  summarizeFeatureSupport() {
    const featureSummary = {};
    
    Object.values(this.results.featureSupport).forEach(browserFeatures => {
      Object.entries(browserFeatures).forEach(([feature, supported]) => {
        if (!featureSummary[feature]) {
          featureSummary[feature] = { supported: 0, total: 0 };
        }
        featureSummary[feature].total++;
        if (supported) featureSummary[feature].supported++;
      });
    });

    return Object.entries(featureSummary).map(([feature, data]) => ({
      feature,
      supportPercentage: Math.round((data.supported / data.total) * 100)
    }));
  }

  generateRecommendations() {
    const recommendations = [];
    
    // Analyze layout consistency issues
    Object.entries(this.results.compatibility).forEach(([page, results]) => {
      if (typeof results === 'object' && !results.error) {
        const issues = Object.values(results).flatMap(r => r.issues || []);
        const criticalIssues = issues.filter(i => i.severity === 'warning');
        
        if (criticalIssues.length > 0) {
          recommendations.push({
            priority: 'high',
            category: 'layout',
            page,
            issue: `Layout inconsistencies detected on ${page}`,
            details: criticalIssues.map(i => i.issue).join(', '),
            suggestion: 'Review CSS for browser-specific differences and add vendor prefixes where needed'
          });
        }
      }
    });

    // Analyze feature support
    const unsupportedFeatures = this.summarizeFeatureSupport()
      .filter(f => f.supportPercentage < 100);
    
    if (unsupportedFeatures.length > 0) {
      recommendations.push({
        priority: 'medium',
        category: 'features',
        issue: 'Some modern web features not universally supported',
        details: unsupportedFeatures.map(f => `${f.feature}: ${f.supportPercentage}%`).join(', '),
        suggestion: 'Consider polyfills or feature detection for unsupported features'
      });
    }

    return recommendations;
  }
}

// Export for use in other test files
module.exports = CrossBrowserTester;

// Run tests if called directly
if (require.main === module) {
  const tester = new CrossBrowserTester();
  tester.runAllTests()
    .then(report => {
      console.log('\n✅ Cross-browser testing completed successfully');
      process.exit(0);
    })
    .catch(error => {
      console.error('\n❌ Cross-browser testing failed:', error);
      process.exit(1);
    });
}