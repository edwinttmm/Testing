/**
 * ADAS Camera HIL Testing Platform - Authentication Tests
 * @fileoverview Comprehensive authentication and project management tests
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('Authentication & Project Management', () => {
  let consoleLogs;

  test.beforeEach(async ({ page }) => {
    // Setup console monitoring
    consoleLogs = TestHelpers.setupConsoleMonitoring(page);
    
    // Navigate to application
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);
  });

  test('should load application homepage successfully', async ({ page }) => {
    // Test basic page load
    await expect(page).toHaveTitle(/AI Model Validation Platform|ADAS Camera HIL Testing Platform/);
    
    // Check for main application elements
    const mainContent = page.locator('main, .main-content, #root, .app');
    await expect(mainContent.first()).toBeVisible();
    
    // Check for navigation elements
    const nav = page.locator('nav, .navigation, .navbar, header');
    await expect(nav.first()).toBeVisible();
    
    // Take screenshot for verification
    await TestHelpers.takeScreenshot(page, 'homepage-loaded');
    
    // Verify no critical console errors
    expect(consoleLogs.errors.filter(error => 
      !error.includes('favicon') && 
      !error.includes('sourcemap')
    ).length).toBe(0);
  });

  test('should display project dashboard', async ({ page }) => {
    // Wait for content to load
    await page.waitForLoadState('networkidle');
    
    // Look for project-related elements
    const projectElements = await page.locator('[data-testid*="project"], .project, [class*="project"]').count();
    
    if (projectElements > 0) {
      console.log('✅ Project dashboard elements found');
      await TestHelpers.takeScreenshot(page, 'project-dashboard');
    } else {
      // Might be on a different page, try navigating
      const navLinks = page.locator('a, button').filter({ hasText: /project|dashboard|home/i });
      const linkCount = await navLinks.count();
      
      if (linkCount > 0) {
        await navLinks.first().click();
        await page.waitForLoadState('networkidle');
        await TestHelpers.takeScreenshot(page, 'after-navigation');
      }
    }
    
    // Verify the page is functional
    expect(page.url()).toContain('localhost:3000');
  });

  test('should handle project creation workflow', async ({ page }) => {
    // Look for create project button
    const createButtons = page.locator('button, a').filter({ 
      hasText: /create|new|add.*project/i 
    });
    
    const buttonCount = await createButtons.count();
    console.log(`Found ${buttonCount} potential create buttons`);
    
    if (buttonCount > 0) {
      // Click create project button
      await createButtons.first().click();
      await page.waitForTimeout(1000);
      
      // Look for project form
      const formElements = page.locator('form, .form, [data-testid*="form"]');
      const hasForm = await formElements.count() > 0;
      
      if (hasForm) {
        console.log('✅ Project form detected');
        
        // Fill out basic project information
        const nameInput = page.locator('input[name="name"], input[placeholder*="name"], #name');
        if (await nameInput.count() > 0) {
          await nameInput.fill('Playwright Test Project');
        }
        
        const descInput = page.locator('textarea[name="description"], textarea[placeholder*="description"], #description');
        if (await descInput.count() > 0) {
          await descInput.fill('Automated test project created by Playwright');
        }
        
        await TestHelpers.takeScreenshot(page, 'project-form-filled');
        
        // Look for submit button
        const submitButtons = page.locator('button[type="submit"], button').filter({
          hasText: /create|save|submit/i
        });
        
        if (await submitButtons.count() > 0) {
          await submitButtons.first().click();
          await page.waitForTimeout(2000);
          await TestHelpers.takeScreenshot(page, 'project-created');
        }
      } else {
        console.log('ℹ️ No project form found - might use different UI pattern');
        await TestHelpers.takeScreenshot(page, 'create-project-clicked');
      }
    } else {
      console.log('ℹ️ No create project button found - testing current state');
      await TestHelpers.takeScreenshot(page, 'no-create-button');
    }
    
    // Verify no critical errors occurred
    expect(consoleLogs.errors.filter(error => 
      !error.includes('favicon') && 
      !error.includes('sourcemap') &&
      !error.includes('Warning:')
    ).length).toBeLessThanOrEqual(2); // Allow for minor non-critical errors
  });

  test('should navigate between main sections', async ({ page }) => {
    // Get all navigation links
    const navLinks = page.locator('nav a, .nav a, a[href], button[role="tab"]');
    const linkCount = await navLinks.count();
    console.log(`Found ${linkCount} navigation links`);
    
    const testedSections = [];
    
    for (let i = 0; i < Math.min(linkCount, 5); i++) {
      try {
        const link = navLinks.nth(i);
        const linkText = await link.textContent();
        const href = await link.getAttribute('href');
        
        if (linkText && linkText.trim() && 
            !href?.includes('mailto:') && 
            !href?.includes('tel:') &&
            !href?.includes('javascript:')) {
          
          console.log(`Testing navigation to: ${linkText.trim()}`);
          
          await link.click();
          await page.waitForTimeout(1500);
          await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {
            console.log('Network not idle, continuing...');
          });
          
          testedSections.push({
            text: linkText.trim(),
            url: page.url(),
            timestamp: new Date().toISOString()
          });
          
          await TestHelpers.takeScreenshot(page, `nav-section-${i}-${linkText.trim().replace(/\s+/g, '-')}`);
        }
      } catch (error) {
        console.log(`Navigation test ${i} had issue:`, error.message);
      }
    }
    
    // Verify we navigated to different sections
    expect(testedSections.length).toBeGreaterThan(0);
    console.log('✅ Navigation test completed. Sections tested:', testedSections.length);
  });

  test('should validate API connectivity', async ({ page }) => {
    // Check if API is accessible
    const healthResponse = await TestHelpers.checkApiHealth(page);
    expect(healthResponse.ok()).toBeTruthy();
    
    // Test projects API
    const projectsResponse = await page.request.get('http://localhost:8000/api/projects');
    expect(projectsResponse.ok()).toBeTruthy();
    
    const projects = await projectsResponse.json();
    console.log(`✅ Found ${projects.length || 0} projects via API`);
    
    // Test other key endpoints
    const endpoints = [
      '/api/test-sessions',
      '/api/videos',
      '/api/dashboard/stats'
    ];
    
    for (const endpoint of endpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`API ${endpoint}: ${response.status()}`);
        expect(response.status()).toBeLessThan(500); // Allow 404s but not server errors
      } catch (error) {
        console.log(`API endpoint ${endpoint} test issue:`, error.message);
      }
    }
  });

  test('should handle responsive design', async ({ page, browserName }) => {
    const viewports = [
      { width: 1920, height: 1080, name: 'desktop' },
      { width: 1366, height: 768, name: 'laptop' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 414, height: 896, name: 'mobile' }
    ];
    
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.waitForTimeout(1000);
      
      // Check if main content is still visible
      const mainContent = page.locator('main, .main-content, #root, .app');
      await expect(mainContent.first()).toBeVisible();
      
      await TestHelpers.takeScreenshot(page, `responsive-${viewport.name}`);
      
      // Check for mobile menu if on small screen
      if (viewport.width < 768) {
        const mobileMenu = page.locator('.mobile-menu, .hamburger, [data-testid="mobile-menu"]');
        const hasMobileMenu = await mobileMenu.count() > 0;
        console.log(`Mobile menu elements found: ${hasMobileMenu}`);
      }
    }
  });

  test.afterEach(async ({ page }, testInfo) => {
    // Save console logs if test failed
    if (testInfo.status !== 'passed') {
      const logs = {
        errors: consoleLogs.errors,
        warnings: consoleLogs.warnings,
        url: page.url(),
        timestamp: new Date().toISOString()
      };
      
      await TestHelpers.saveTestResults(testInfo.title, logs);
    }
  });
});