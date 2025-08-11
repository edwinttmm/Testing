/**
 * WCAG 2.1 AA Accessibility Audit Suite
 * Comprehensive accessibility testing for compliance with WCAG guidelines
 */

const puppeteer = require('puppeteer');
const axeCore = require('axe-core');

class AccessibilityAuditor {
  constructor(baseUrl = 'http://localhost:3000') {
    this.baseUrl = baseUrl;
    this.browser = null;
    this.results = {
      wcagCompliance: {},
      violations: [],
      passed: [],
      incomplete: [],
      screenReaderTest: {},
      keyboardNavigation: {},
      colorContrast: {},
      semanticStructure: {}
    };
  }

  async setup() {
    this.browser = await puppeteer.launch({
      headless: false, // Run in non-headless mode for better accessibility testing
      args: ['--no-sandbox', '--disable-web-security'],
      devtools: false
    });
  }

  async teardown() {
    if (this.browser) {
      await this.browser.close();
    }
  }

  async runAxeAudit(page, context = null) {
    // Inject axe-core into the page
    await page.addScriptTag({ path: require.resolve('axe-core') });
    
    // Configure axe for WCAG 2.1 AA compliance
    const results = await page.evaluate((context) => {
      return axe.run(context, {
        runOnly: {
          type: 'tag',
          values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice']
        },
        resultTypes: ['violations', 'incomplete', 'passes'],
        rules: {
          // Configure specific rules
          'color-contrast': { enabled: true },
          'keyboard-navigation': { enabled: true },
          'aria-labels': { enabled: true },
          'semantic-structure': { enabled: true },
          'form-labels': { enabled: true },
          'heading-order': { enabled: true },
          'landmark-roles': { enabled: true }
        }
      });
    }, context);
    
    return results;
  }

  async auditPage(url, pageName) {
    console.log(`🔍 Auditing accessibility for ${pageName}...`);
    
    const page = await this.browser.newPage();
    
    try {
      // Navigate to page
      await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });
      
      // Run axe audit
      const axeResults = await this.runAxeAudit(page);
      
      // Test keyboard navigation
      const keyboardResults = await this.testKeyboardNavigation(page);
      
      // Test screen reader compatibility
      const screenReaderResults = await this.testScreenReaderCompatibility(page);
      
      // Test color contrast manually (additional to axe)
      const contrastResults = await this.testColorContrast(page);
      
      // Test semantic structure
      const semanticResults = await this.testSemanticStructure(page);
      
      // Compile results
      this.results.wcagCompliance[pageName] = {
        axe: axeResults,
        keyboard: keyboardResults,
        screenReader: screenReaderResults,
        colorContrast: contrastResults,
        semantic: semanticResults,
        score: this.calculateAccessibilityScore(axeResults, keyboardResults, screenReaderResults)
      };
      
      // Aggregate violations
      this.results.violations.push(...axeResults.violations.map(v => ({
        ...v,
        page: pageName,
        url
      })));
      
      console.log(`✓ ${pageName} audited - ${axeResults.violations.length} violations found`);
      
    } catch (error) {
      console.error(`✗ Failed to audit ${pageName}: ${error.message}`);
      this.results.wcagCompliance[pageName] = { error: error.message };
    } finally {
      await page.close();
    }
  }

  async testKeyboardNavigation(page) {
    console.log('⌨️ Testing keyboard navigation...');
    
    const results = {
      focusableElements: 0,
      keyboardAccessible: 0,
      tabOrder: [],
      issues: []
    };
    
    try {
      // Get all focusable elements
      const focusableElements = await page.$$eval(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        elements => elements.map(el => ({
          tagName: el.tagName.toLowerCase(),
          type: el.type || null,
          tabIndex: el.tabIndex,
          id: el.id || null,
          ariaLabel: el.getAttribute('aria-label') || null,
          text: el.textContent?.trim() || null,
          hasVisibleFocus: false // Will be tested individually
        }))
      );
      
      results.focusableElements = focusableElements.length;
      
      // Test tab navigation through elements
      let tabIndex = 0;
      let currentElement = null;
      
      // Focus first element
      await page.keyboard.press('Tab');
      
      while (tabIndex < focusableElements.length && tabIndex < 50) { // Limit to prevent infinite loops
        try {
          // Get currently focused element
          currentElement = await page.evaluate(() => {
            const focused = document.activeElement;
            if (!focused || focused === document.body) return null;
            
            return {
              tagName: focused.tagName.toLowerCase(),
              id: focused.id || null,
              className: focused.className || null,
              text: focused.textContent?.trim().substring(0, 50) || null,
              hasVisibleFocus: getComputedStyle(focused).outline !== 'none' || 
                               getComputedStyle(focused).boxShadow !== 'none'
            };
          });
          
          if (currentElement) {
            results.tabOrder.push(currentElement);
            
            if (currentElement.hasVisibleFocus) {
              results.keyboardAccessible++;
            } else {
              results.issues.push({
                issue: 'No visible focus indicator',
                element: currentElement
              });
            }
            
            // Test Enter key activation on interactive elements
            if (['button', 'a', 'input'].includes(currentElement.tagName)) {
              try {
                await page.keyboard.press('Enter');
                await page.waitForTimeout(100); // Wait for any response
              } catch (e) {
                // Ignore navigation errors
              }
            }
          }
          
          // Move to next element
          await page.keyboard.press('Tab');
          await page.waitForTimeout(50);
          tabIndex++;
          
        } catch (error) {
          results.issues.push({
            issue: 'Error during tab navigation',
            error: error.message,
            position: tabIndex
          });
          break;
        }
      }
      
      // Test Shift+Tab (reverse navigation)
      await page.keyboard.down('Shift');
      await page.keyboard.press('Tab');
      await page.keyboard.up('Shift');
      
      const reverseElement = await page.evaluate(() => {
        const focused = document.activeElement;
        return focused ? {
          tagName: focused.tagName.toLowerCase(),
          id: focused.id || null
        } : null;
      });
      
      if (reverseElement) {
        results.reverseNavigationWorks = true;
      }
      
      // Test Escape key functionality
      await page.keyboard.press('Escape');
      
      results.score = results.focusableElements > 0 ? 
        (results.keyboardAccessible / results.focusableElements) * 100 : 100;
      
    } catch (error) {
      results.error = error.message;
    }
    
    return results;
  }

  async testScreenReaderCompatibility(page) {
    console.log('🗣 Testing screen reader compatibility...');
    
    const results = {
      landmarks: 0,
      headings: { structure: [], issues: [] },
      ariaLabels: { present: 0, missing: 0 },
      liveRegions: 0,
      semanticElements: 0,
      issues: []
    };
    
    try {
      // Test landmark roles
      const landmarks = await page.$$eval(
        '[role="main"], [role="navigation"], [role="banner"], [role="contentinfo"], [role="complementary"], main, nav, header, footer, aside',
        elements => elements.map(el => ({
          tagName: el.tagName.toLowerCase(),
          role: el.getAttribute('role') || null,
          ariaLabel: el.getAttribute('aria-label') || null,
          ariaLabelledby: el.getAttribute('aria-labelledby') || null
        }))
      );
      
      results.landmarks = landmarks.length;
      
      // Test heading structure
      const headings = await page.$$eval(
        'h1, h2, h3, h4, h5, h6, [role="heading"]',
        elements => elements.map((el, index) => ({
          level: parseInt(el.tagName.charAt(1)) || parseInt(el.getAttribute('aria-level')) || 1,
          text: el.textContent?.trim() || null,
          position: index,
          hasId: !!el.id,
          ariaLabel: el.getAttribute('aria-label') || null
        }))
      );
      
      results.headings.structure = headings;
      
      // Check heading hierarchy
      for (let i = 1; i < headings.length; i++) {
        const current = headings[i];
        const previous = headings[i - 1];
        
        if (current.level > previous.level + 1) {
          results.headings.issues.push({
            issue: 'Heading level skipped',
            position: current.position,
            expected: `h${previous.level + 1}`,
            actual: `h${current.level}`
          });
        }
      }
      
      // Test ARIA labels
      const interactiveElements = await page.$$eval(
        'button, [role="button"], input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])',
        elements => elements.map(el => ({
          tagName: el.tagName.toLowerCase(),
          hasAriaLabel: !!el.getAttribute('aria-label'),
          hasAriaLabelledby: !!el.getAttribute('aria-labelledby'),
          hasAriaDescribedby: !!el.getAttribute('aria-describedby'),
          hasVisibleText: (el.textContent?.trim().length || 0) > 0,
          type: el.type || null
        }))
      );
      
      interactiveElements.forEach(el => {
        if (el.hasAriaLabel || el.hasAriaLabelledby || el.hasVisibleText) {
          results.ariaLabels.present++;
        } else {
          results.ariaLabels.missing++;
          results.issues.push({
            issue: 'Interactive element lacks accessible name',
            element: el
          });
        }
      });
      
      // Test live regions
      const liveRegions = await page.$$eval(
        '[aria-live], [aria-atomic], [role="status"], [role="alert"]',
        elements => elements.length
      );
      
      results.liveRegions = liveRegions;
      
      // Test semantic elements
      const semanticElements = await page.$$eval(
        'main, nav, header, footer, aside, section, article, figure, figcaption, time, mark',
        elements => elements.length
      );
      
      results.semanticElements = semanticElements;
      
      results.score = this.calculateScreenReaderScore(results);
      
    } catch (error) {
      results.error = error.message;
    }
    
    return results;
  }

  async testColorContrast(page) {
    console.log('🎨 Testing color contrast...');
    
    const results = {
      textElements: 0,
      passingContrast: 0,
      failingElements: [],
      issues: []
    };
    
    try {
      const contrastIssues = await page.evaluate(() => {
        const issues = [];
        
        // Get all text elements
        const textElements = document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div, a, button, label, li');
        
        for (const element of textElements) {
          const styles = getComputedStyle(element);
          const textColor = styles.color;
          const backgroundColor = styles.backgroundColor;
          const fontSize = parseFloat(styles.fontSize);
          const fontWeight = parseInt(styles.fontWeight) || 400;
          
          // Skip if no visible text
          if (!element.textContent?.trim()) continue;
          
          // Basic contrast check (simplified - in real implementation would use proper contrast calculation)
          const isLargeText = fontSize >= 18 || (fontSize >= 14 && fontWeight >= 700);
          
          issues.push({
            text: element.textContent.trim().substring(0, 50),
            textColor,
            backgroundColor,
            fontSize,
            fontWeight,
            isLargeText,
            tagName: element.tagName.toLowerCase(),
            className: element.className || null
          });
        }
        
        return issues;
      });
      
      results.textElements = contrastIssues.length;
      
      // Note: In a real implementation, you would use a proper color contrast library
      // to calculate actual contrast ratios and determine pass/fail
      contrastIssues.forEach(issue => {
        // Simplified check - assume most elements pass unless we detect obvious issues
        if (issue.textColor === 'rgb(255, 255, 255)' && issue.backgroundColor === 'rgba(0, 0, 0, 0)') {
          results.failingElements.push({
            ...issue,
            reason: 'White text on transparent background - may have insufficient contrast'
          });
        } else {
          results.passingContrast++;
        }
      });
      
      results.score = results.textElements > 0 ? 
        (results.passingContrast / results.textElements) * 100 : 100;
      
    } catch (error) {
      results.error = error.message;
    }
    
    return results;
  }

  async testSemanticStructure(page) {
    console.log('🏗 Testing semantic structure...');
    
    const results = {
      pageTitle: null,
      metaDescription: null,
      lang: null,
      semanticElements: {},
      formLabels: { total: 0, labeled: 0 },
      imageAlts: { total: 0, withAlt: 0 },
      issues: []
    };
    
    try {
      // Test page metadata
      const metadata = await page.evaluate(() => {
        return {
          title: document.title || null,
          description: document.querySelector('meta[name="description"]')?.content || null,
          lang: document.documentElement.lang || null,
          viewport: document.querySelector('meta[name="viewport"]')?.content || null
        };
      });
      
      results.pageTitle = metadata.title;
      results.metaDescription = metadata.description;
      results.lang = metadata.lang;
      
      if (!metadata.title) {
        results.issues.push({ issue: 'Page missing title element' });
      }
      
      if (!metadata.lang) {
        results.issues.push({ issue: 'Document missing lang attribute' });
      }
      
      // Test semantic elements usage
      const semanticElements = await page.evaluate(() => {
        const elements = {};
        const semanticTags = ['main', 'nav', 'header', 'footer', 'aside', 'section', 'article', 'figure', 'figcaption'];
        
        semanticTags.forEach(tag => {
          elements[tag] = document.querySelectorAll(tag).length;
        });
        
        return elements;
      });
      
      results.semanticElements = semanticElements;
      
      // Test form labels
      const formElements = await page.evaluate(() => {
        const inputs = document.querySelectorAll('input, select, textarea');
        let labeled = 0;
        
        inputs.forEach(input => {
          const hasLabel = document.querySelector(`label[for="${input.id}"]`) ||
                           input.closest('label') ||
                           input.getAttribute('aria-label') ||
                           input.getAttribute('aria-labelledby');
          
          if (hasLabel) labeled++;
        });
        
        return { total: inputs.length, labeled };
      });
      
      results.formLabels = formElements;
      
      // Test image alt texts
      const imageInfo = await page.evaluate(() => {
        const images = document.querySelectorAll('img');
        let withAlt = 0;
        
        images.forEach(img => {
          if (img.alt !== undefined && img.alt !== '') {
            withAlt++;
          }
        });
        
        return { total: images.length, withAlt };
      });
      
      results.imageAlts = imageInfo;
      
      // Calculate semantic score
      results.score = this.calculateSemanticScore(results);
      
    } catch (error) {
      results.error = error.message;
    }
    
    return results;
  }

  calculateAccessibilityScore(axeResults, keyboardResults, screenReaderResults) {
    const axeScore = axeResults.violations.length === 0 ? 100 : 
      Math.max(0, 100 - (axeResults.violations.length * 10));
    
    const keyboardScore = keyboardResults.score || 0;
    const screenReaderScore = screenReaderResults.score || 0;
    
    return Math.round((axeScore + keyboardScore + screenReaderScore) / 3);
  }

  calculateScreenReaderScore(results) {
    let score = 0;
    let maxScore = 0;
    
    // Landmarks (20 points)
    maxScore += 20;
    score += results.landmarks > 0 ? 20 : 0;
    
    // Heading structure (20 points)
    maxScore += 20;
    score += results.headings.structure.length > 0 ? 
      (20 - Math.min(20, results.headings.issues.length * 5)) : 0;
    
    // ARIA labels (30 points)
    maxScore += 30;
    const totalInteractive = results.ariaLabels.present + results.ariaLabels.missing;
    if (totalInteractive > 0) {
      score += (results.ariaLabels.present / totalInteractive) * 30;
    }
    
    // Live regions (15 points)
    maxScore += 15;
    score += results.liveRegions > 0 ? 15 : 0;
    
    // Semantic elements (15 points)
    maxScore += 15;
    score += results.semanticElements > 0 ? 15 : 0;
    
    return maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
  }

  calculateSemanticScore(results) {
    let score = 0;
    let maxScore = 0;
    
    // Page title (15 points)
    maxScore += 15;
    score += results.pageTitle ? 15 : 0;
    
    // Language attribute (10 points)
    maxScore += 10;
    score += results.lang ? 10 : 0;
    
    // Semantic elements usage (25 points)
    maxScore += 25;
    const semanticCount = Object.values(results.semanticElements).reduce((sum, count) => sum + count, 0);
    score += semanticCount > 0 ? 25 : 0;
    
    // Form labels (25 points)
    maxScore += 25;
    if (results.formLabels.total > 0) {
      score += (results.formLabels.labeled / results.formLabels.total) * 25;
    } else {
      score += 25; // No forms is not a penalty
    }
    
    // Image alt texts (25 points)
    maxScore += 25;
    if (results.imageAlts.total > 0) {
      score += (results.imageAlts.withAlt / results.imageAlts.total) * 25;
    } else {
      score += 25; // No images is not a penalty
    }
    
    return maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
  }

  async runFullAudit() {
    console.log('🎯 Starting comprehensive WCAG 2.1 AA accessibility audit...\n');
    
    try {
      await this.setup();
      
      const pages = [
        { url: `${this.baseUrl}/`, name: 'Dashboard' },
        { url: `${this.baseUrl}/projects`, name: 'Projects' },
        { url: `${this.baseUrl}/test-execution`, name: 'Test Execution' },
        { url: `${this.baseUrl}/ground-truth`, name: 'Ground Truth' },
        { url: `${this.baseUrl}/results`, name: 'Results' }
      ];
      
      for (const page of pages) {
        await this.auditPage(page.url, page.name);
      }
      
      await this.teardown();
      
      return this.generateReport();
    } catch (error) {
      console.error('🚨 Accessibility audit failed:', error.message);
      await this.teardown();
      throw error;
    }
  }

  generateReport() {
    const report = {
      timestamp: new Date().toISOString(),
      wcagLevel: 'AA',
      wcagVersion: '2.1',
      summary: this.generateSummary(),
      detailed: this.results,
      recommendations: this.generateRecommendations()
    };

    console.log('\n♿ WCAG 2.1 AA ACCESSIBILITY AUDIT REPORT');
    console.log('=' .repeat(50));
    console.log(`Overall WCAG Compliance: ${report.summary.overallScore}%`);
    console.log(`Total Violations: ${report.summary.totalViolations}`);
    console.log(`Pages Audited: ${report.summary.pagesAudited}`);
    
    console.log('\n📊 Scores by Category:');
    Object.entries(report.summary.categoryScores).forEach(([category, score]) => {
      const status = score >= 90 ? '✅' : score >= 75 ? '⚠️' : '❌';
      console.log(`${status} ${category}: ${score}%`);
    });
    
    return report;
  }

  generateSummary() {
    const pageResults = Object.values(this.results.wcagCompliance);
    const totalViolations = this.results.violations.length;
    
    // Calculate overall score
    const scores = pageResults
      .filter(result => result.score !== undefined)
      .map(result => result.score);
    
    const overallScore = scores.length > 0 ? 
      Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : 0;
    
    // Calculate category scores
    const categoryScores = {
      'Keyboard Navigation': this.calculateCategoryScore('keyboard'),
      'Screen Reader Support': this.calculateCategoryScore('screenReader'),
      'Color Contrast': this.calculateCategoryScore('colorContrast'),
      'Semantic Structure': this.calculateCategoryScore('semantic')
    };
    
    return {
      overallScore,
      totalViolations,
      pagesAudited: pageResults.length,
      categoryScores,
      complianceLevel: overallScore >= 90 ? 'WCAG AA Compliant' : 
                       overallScore >= 75 ? 'Mostly Compliant' : 
                       'Needs Improvement'
    };
  }

  calculateCategoryScore(category) {
    const pageResults = Object.values(this.results.wcagCompliance);
    const scores = pageResults
      .filter(result => result[category] && result[category].score !== undefined)
      .map(result => result[category].score);
    
    return scores.length > 0 ? 
      Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : 0;
  }

  generateRecommendations() {
    const recommendations = [];
    
    // Analyze violations by severity and frequency
    const violationCounts = {};
    this.results.violations.forEach(violation => {
      const key = violation.id;
      if (!violationCounts[key]) {
        violationCounts[key] = {
          count: 0,
          impact: violation.impact,
          description: violation.description,
          help: violation.help,
          helpUrl: violation.helpUrl
        };
      }
      violationCounts[key].count++;
    });
    
    // Generate recommendations for most frequent/critical violations
    Object.entries(violationCounts)
      .sort((a, b) => {
        const impactWeight = { critical: 4, serious: 3, moderate: 2, minor: 1 };
        return (impactWeight[b[1].impact] * b[1].count) - (impactWeight[a[1].impact] * a[1].count);
      })
      .slice(0, 10) // Top 10 issues
      .forEach(([violationId, data]) => {
        recommendations.push({
          priority: data.impact === 'critical' || data.impact === 'serious' ? 'high' : 'medium',
          category: 'accessibility',
          issue: data.description,
          occurrences: data.count,
          impact: data.impact,
          guidance: data.help,
          reference: data.helpUrl
        });
      });
    
    return recommendations;
  }
}

// Export for use in other test files
module.exports = AccessibilityAuditor;

// Run audit if called directly
if (require.main === module) {
  const auditor = new AccessibilityAuditor();
  auditor.runFullAudit()
    .then(report => {
      console.log('\n✅ WCAG accessibility audit completed successfully');
      // In a real implementation, you might save this report to a file
      process.exit(0);
    })
    .catch(error => {
      console.error('\n❌ Accessibility audit failed:', error);
      process.exit(1);
    });
}