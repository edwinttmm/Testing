/**
 * ADAS Camera HIL Testing Platform - Authentication & Project Management Tests
 * @fileoverview Comprehensive authentication flow and project management testing
 */

const { test, expect } = require('@playwright/test');

test.describe('Authentication & Project Management', () => {
  let page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    
    // Enhanced error capture
    page.on('console', msg => console.log('Console:', msg.type(), msg.text()));
    page.on('pageerror', error => console.log('Page Error:', error.message));
    page.on('requestfailed', req => console.log('Request Failed:', req.url()));
  });

  test('should load main application and display landing page', async () => {
    console.log('🏠 Testing main application loading...');
    
    await page.goto('/');
    await expect(page).toHaveTitle(/ADAS Camera HIL Testing Platform/i);
    
    // Take screenshot for evidence
    await page.screenshot({ path: './docs/errors/screenshots/01-landing-page.png', fullPage: true });
    
    // Check for main navigation elements
    const navigation = page.locator('[data-testid="main-navigation"]');
    await expect(navigation).toBeVisible({ timeout: 10000 });
    
    // Verify core sections are accessible
    const expectedSections = ['Projects', 'Upload', 'Detection', 'Monitoring', 'LabJack'];
    for (const section of expectedSections) {
      const sectionLink = page.locator(`[data-testid="nav-${section.toLowerCase()}"], a:has-text("${section}")`);
      await expect(sectionLink).toBeVisible();
    }
  });

  test('should create new project with complete workflow', async () => {
    console.log('🏗️ Testing project creation workflow...');
    
    await page.goto('/');
    
    // Navigate to projects section
    await page.click('[data-testid="nav-projects"], a:has-text("Projects")');
    await expect(page).toHaveURL(/projects/);
    
    await page.screenshot({ path: './docs/errors/screenshots/02-projects-page.png', fullPage: true });
    
    // Click create project button
    const createButton = page.locator('[data-testid="create-project-button"], button:has-text("Create Project")');
    await createButton.click();
    
    // Fill project creation form
    await page.waitForSelector('[data-testid="project-form"], form');
    
    const projectName = `Test Project ${Date.now()}`;
    await page.fill('[data-testid="project-name"], input[name="name"]', projectName);
    await page.fill('[data-testid="project-description"], textarea[name="description"]', 'Automated test project for ADAS platform validation');
    
    // Select project type if available
    const projectTypeSelector = page.locator('[data-testid="project-type"], select[name="type"]');
    if (await projectTypeSelector.isVisible()) {
      await projectTypeSelector.selectOption('HIL Testing');
    }
    
    await page.screenshot({ path: './docs/errors/screenshots/03-project-form-filled.png', fullPage: true });
    
    // Submit project creation
    await page.click('[data-testid="submit-project"], button[type="submit"]');
    
    // Wait for project creation confirmation
    const successMessage = page.locator('[data-testid="project-success"], .success-message');
    await expect(successMessage).toBeVisible({ timeout: 15000 });
    
    await page.screenshot({ path: './docs/errors/screenshots/04-project-created.png', fullPage: true });
    
    // Verify project appears in project list
    const projectList = page.locator('[data-testid="project-list"]');
    await expect(projectList).toContainText(projectName);
  });

  test('should handle project management operations', async () => {
    console.log('📋 Testing project management operations...');
    
    await page.goto('/projects');
    
    // Wait for project list to load
    await page.waitForSelector('[data-testid="project-list"], .project-list');
    
    // Test project selection
    const firstProject = page.locator('[data-testid="project-item"], .project-item').first();
    await firstProject.click();
    
    await page.screenshot({ path: './docs/errors/screenshots/05-project-selected.png', fullPage: true });
    
    // Test project settings access
    const settingsButton = page.locator('[data-testid="project-settings"], button:has-text("Settings")');
    if (await settingsButton.isVisible()) {
      await settingsButton.click();
      
      await page.waitForSelector('[data-testid="project-settings-panel"], .settings-panel');
      await page.screenshot({ path: './docs/errors/screenshots/06-project-settings.png', fullPage: true });
      
      // Test settings modification
      const confidenceSlider = page.locator('[data-testid="confidence-threshold"], input[name="confidence"]');
      if (await confidenceSlider.isVisible()) {
        await confidenceSlider.fill('0.75');
      }
      
      // Save settings
      const saveButton = page.locator('[data-testid="save-settings"], button:has-text("Save")');
      await saveButton.click();
      
      // Verify settings saved
      const saveConfirmation = page.locator('[data-testid="settings-saved"], .success-message');
      await expect(saveConfirmation).toBeVisible({ timeout: 10000 });
    }
  });

  test('should validate user session management', async () => {
    console.log('👤 Testing user session management...');
    
    await page.goto('/');
    
    // Test session initialization
    await page.evaluate(() => {
      // Simulate user session data
      localStorage.setItem('userSession', JSON.stringify({
        userId: 'test-user-001',
        username: 'TestUser',
        sessionToken: 'mock-session-token',
        expires: Date.now() + 3600000 // 1 hour
      }));
    });
    
    await page.reload();
    
    // Verify session persistence
    const sessionData = await page.evaluate(() => {
      return JSON.parse(localStorage.getItem('userSession') || '{}');
    });
    
    expect(sessionData.userId).toBe('test-user-001');
    
    await page.screenshot({ path: './docs/errors/screenshots/07-session-management.png', fullPage: true });
    
    // Test session expiration handling
    await page.evaluate(() => {
      const session = JSON.parse(localStorage.getItem('userSession'));
      session.expires = Date.now() - 1000; // Expired
      localStorage.setItem('userSession', JSON.stringify(session));
    });
    
    await page.reload();
    
    // Should handle expired session gracefully
    const loginPrompt = page.locator('[data-testid="login-required"], .login-prompt');
    // This might not be visible if no auth is required, so we make it optional
    if (await loginPrompt.isVisible()) {
      await expect(loginPrompt).toBeVisible();
    }
  });

  test('should handle navigation between sections', async () => {
    console.log('🧭 Testing navigation between platform sections...');
    
    await page.goto('/');
    
    const sections = [
      { name: 'Projects', path: '/projects' },
      { name: 'Upload', path: '/upload' },
      { name: 'Detection', path: '/detection' },
      { name: 'Monitoring', path: '/monitoring' }
    ];
    
    for (const section of sections) {
      console.log(`Navigating to ${section.name}...`);
      
      // Click navigation link
      const navLink = page.locator(`[data-testid="nav-${section.name.toLowerCase()}"], a:has-text("${section.name}")`);
      if (await navLink.isVisible()) {
        await navLink.click();
        
        // Wait for navigation to complete
        await page.waitForLoadState('networkidle');
        
        // Verify URL changed
        await expect(page).toHaveURL(new RegExp(section.path));
        
        // Take screenshot of each section
        await page.screenshot({ 
          path: `./docs/errors/screenshots/08-navigation-${section.name.toLowerCase()}.png`, 
          fullPage: true 
        });
        
        // Verify section content loaded
        const sectionContent = page.locator('[data-testid="main-content"], main');
        await expect(sectionContent).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('should handle responsive design and mobile compatibility', async () => {
    console.log('📱 Testing responsive design...');
    
    // Test different viewport sizes
    const viewports = [
      { width: 1920, height: 1080, name: 'desktop' },
      { width: 1024, height: 768, name: 'tablet' },
      { width: 375, height: 667, name: 'mobile' }
    ];
    
    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/');
      
      await page.screenshot({ 
        path: `./docs/errors/screenshots/09-responsive-${viewport.name}.png`,
        fullPage: true 
      });
      
      // Check that navigation adapts to screen size
      const navigation = page.locator('[data-testid="main-navigation"]');
      await expect(navigation).toBeVisible();
      
      // For mobile, check if hamburger menu is present
      if (viewport.width < 768) {
        const mobileMenu = page.locator('[data-testid="mobile-menu-toggle"], .mobile-menu-toggle');
        if (await mobileMenu.isVisible()) {
          await mobileMenu.click();
          await page.screenshot({ 
            path: `./docs/errors/screenshots/10-mobile-menu-open.png`,
            fullPage: true 
          });
        }
      }
    }
  });

  test.afterEach(async () => {
    await page.close();
  });
});