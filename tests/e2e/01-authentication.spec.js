const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('Authentication Flow', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
  });

  test('should load login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/Login/);
    await helpers.takeScreenshot('login-page-loaded');
  });

  test('should handle invalid login credentials', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', 'invalid@example.com');
    await page.fill('[data-testid="password-input"]', 'wrongpassword');
    await page.click('[data-testid="login-button"]');
    
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await helpers.takeScreenshot('login-invalid-credentials');
  });

  test('should successfully login with valid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'password');
    await page.click('[data-testid="login-button"]');
    
    // Wait for dashboard or redirect
    await page.waitForURL(/dashboard|home/, { timeout: 10000 });
    await helpers.takeScreenshot('login-success-dashboard');
  });

  test('should maintain session across page refreshes', async ({ page }) => {
    // Login first
    await helpers.login();
    
    // Refresh page
    await page.reload();
    
    // Should still be on dashboard
    await expect(page.url()).toContain('dashboard');
    await helpers.takeScreenshot('session-maintained-after-refresh');
  });

  test('should logout successfully', async ({ page }) => {
    await helpers.login();
    
    await page.click('[data-testid="logout-button"]');
    await page.waitForURL('/login');
    
    await expect(page.url()).toContain('/login');
    await helpers.takeScreenshot('logout-success');
  });

  test('should handle backend authentication API', async ({ page }) => {
    const response = await page.request.post('http://localhost:8000/auth/login', {
      data: {
        email: 'test@example.com',
        password: 'password'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('token');
    
    await helpers.saveTestResults('backend-auth-test', {
      status: response.status(),
      hasToken: !!data.token,
      timestamp: Date.now()
    });
  });
});

test.describe('User Registration', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
  });

  test('should display registration form', async ({ page }) => {
    await page.goto('/register');
    
    await expect(page.locator('[data-testid="register-form"]')).toBeVisible();
    await expect(page.locator('[data-testid="email-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="confirm-password-input"]')).toBeVisible();
    
    await helpers.takeScreenshot('registration-form-displayed');
  });

  test('should validate password requirements', async ({ page }) => {
    await page.goto('/register');
    
    await page.fill('[data-testid="email-input"]', 'newuser@example.com');
    await page.fill('[data-testid="password-input"]', '123');
    await page.fill('[data-testid="confirm-password-input"]', '123');
    await page.click('[data-testid="register-button"]');
    
    await expect(page.locator('[data-testid="password-error"]')).toBeVisible();
    await helpers.takeScreenshot('registration-password-validation');
  });

  test('should validate email format', async ({ page }) => {
    await page.goto('/register');
    
    await page.fill('[data-testid="email-input"]', 'invalid-email');
    await page.fill('[data-testid="password-input"]', 'SecurePass123!');
    await page.fill('[data-testid="confirm-password-input"]', 'SecurePass123!');
    await page.click('[data-testid="register-button"]');
    
    await expect(page.locator('[data-testid="email-error"]')).toBeVisible();
    await helpers.takeScreenshot('registration-email-validation');
  });
});