# End-to-End Test Scenarios - AI Model Validation Platform

## Overview

End-to-end (E2E) tests validate complete user workflows from the frontend UI through to the backend services and database. These tests ensure the entire system works cohesively and delivers the expected user experience.

## Test Environment Setup

### Browser Testing Configuration
```javascript
// playwright.config.js
module.exports = {
  testDir: 'tests/e2e',
  timeout: 60000,
  retries: 2,
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
    viewport: { width: 1280, height: 720 },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] }
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] }
    },
    {
      name: 'mobile',
      use: { ...devices['iPhone 13'] }
    }
  ],
  webServer: {
    command: 'npm start',
    port: 3000,
    reuseExistingServer: !process.env.CI
  }
};
```

## Complete User Workflow Tests

### 1. User Registration and Authentication Workflow

```javascript
// tests/e2e/auth/user_registration_flow.spec.js

import { test, expect } from '@playwright/test';

test.describe('User Registration and Authentication', () => {
  
  test('complete user registration workflow', async ({ page }) => {
    // Step 1: Navigate to registration page
    await page.goto('/register');
    await expect(page.getByRole('heading', { name: 'Create Account' })).toBeVisible();
    
    // Step 2: Fill registration form
    const timestamp = Date.now();
    const testUser = {
      email: `test.user.${timestamp}@example.com`,
      password: 'SecurePassword123!',
      fullName: 'Test User E2E',
      confirmPassword: 'SecurePassword123!'
    };
    
    await page.getByLabel('Email').fill(testUser.email);
    await page.getByLabel('Full Name').fill(testUser.fullName);
    await page.getByLabel('Password', { exact: true }).fill(testUser.password);
    await page.getByLabel('Confirm Password').fill(testUser.confirmPassword);
    
    // Step 3: Submit registration
    await page.getByRole('button', { name: 'Create Account' }).click();
    
    // Step 4: Verify registration success
    await expect(page.getByText('Account created successfully')).toBeVisible();
    await expect(page).toHaveURL('/login');
    
    // Step 5: Login with new account
    await page.getByLabel('Email').fill(testUser.email);
    await page.getByLabel('Password').fill(testUser.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    // Step 6: Verify successful login
    await expect(page).toHaveURL('/dashboard');
    await expect(page.getByText(`Welcome, ${testUser.fullName}`)).toBeVisible();
  });
  
  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/login');
    
    await page.getByLabel('Email').fill('nonexistent@example.com');
    await page.getByLabel('Password').fill('wrongpassword');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    await expect(page.getByText('Invalid email or password')).toBeVisible();
    await expect(page).toHaveURL('/login');
  });
  
  test('session timeout redirects to login', async ({ page, context }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page).toHaveURL('/dashboard');
    
    // Simulate token expiration by clearing localStorage
    await context.clearCookies();
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
    });
    
    // Try to access protected page
    await page.goto('/projects');
    
    // Should redirect to login
    await expect(page).toHaveURL('/login');
    await expect(page.getByText('Session expired. Please log in again.')).toBeVisible();
  });
});
```

### 2. Project Management Workflow

```javascript
// tests/e2e/projects/project_management_flow.spec.js

import { test, expect } from '@playwright/test';

test.describe('Project Management Workflow', () => {
  
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page).toHaveURL('/dashboard');
  });
  
  test('complete project creation and configuration workflow', async ({ page }) => {
    // Step 1: Navigate to projects page
    await page.getByRole('link', { name: 'Projects' }).click();
    await expect(page).toHaveURL('/projects');
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    
    // Step 2: Open create project dialog
    await page.getByRole('button', { name: 'New Project' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Create New Project' })).toBeVisible();
    
    // Step 3: Fill project form
    const projectName = `E2E Test Project ${Date.now()}`;
    await page.getByLabel('Project Name').fill(projectName);
    await page.getByLabel('Description').fill('End-to-end test project for validation');
    
    // Camera configuration
    await page.getByLabel('Camera Model').click();
    await page.getByRole('option', { name: 'FLIR Blackfly S' }).click();
    
    await page.getByLabel('Camera View').click();
    await page.getByRole('option', { name: 'Front-facing VRU' }).click();
    
    await page.getByLabel('Lens Type').click();
    await page.getByRole('option', { name: 'Wide-angle' }).click();
    
    await page.getByLabel('Resolution').click();
    await page.getByRole('option', { name: '1920x1080' }).click();
    
    await page.getByLabel('Frame Rate').fill('30');
    
    await page.getByLabel('Signal Type').click();
    await page.getByRole('option', { name: 'GPIO' }).click();
    
    // Step 4: Submit project creation
    await page.getByRole('button', { name: 'Create Project' }).click();
    
    // Step 5: Verify project creation success
    await expect(page.getByText('Project created successfully')).toBeVisible();
    await expect(page.getByRole('dialog')).not.toBeVisible();
    
    // Step 6: Verify project appears in list
    await expect(page.getByText(projectName)).toBeVisible();
    await expect(page.getByText('Active')).toBeVisible();
    
    // Step 7: Open project details
    await page.getByText(projectName).click();
    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/);
    await expect(page.getByRole('heading', { name: projectName })).toBeVisible();
    
    // Step 8: Verify project configuration details
    await expect(page.getByText('FLIR Blackfly S')).toBeVisible();
    await expect(page.getByText('Front-facing VRU')).toBeVisible();
    await expect(page.getByText('1920x1080')).toBeVisible();
    await expect(page.getByText('GPIO')).toBeVisible();
  });
  
  test('project search and filtering', async ({ page }) => {
    await page.goto('/projects');
    
    // Create multiple test projects first
    const projects = ['Highway Detection', 'Urban Intersection', 'School Zone'];
    
    for (const projectName of projects) {
      await page.getByRole('button', { name: 'New Project' }).click();
      await page.getByLabel('Project Name').fill(projectName);
      await page.getByLabel('Camera Model').click();
      await page.getByRole('option').first().click();
      await page.getByLabel('Camera View').click();
      await page.getByRole('option').first().click();
      await page.getByLabel('Signal Type').click();
      await page.getByRole('option').first().click();
      await page.getByRole('button', { name: 'Create Project' }).click();
      await expect(page.getByText('Project created successfully')).toBeVisible();
    }
    
    // Test search functionality
    await page.getByPlaceholder('Search projects...').fill('Highway');
    await expect(page.getByText('Highway Detection')).toBeVisible();
    await expect(page.getByText('Urban Intersection')).not.toBeVisible();
    
    // Test status filtering
    await page.getByLabel('Status Filter').click();
    await page.getByRole('option', { name: 'Active' }).click();
    
    // Clear search to show all active projects
    await page.getByPlaceholder('Search projects...').clear();
    
    // Verify all active projects are shown
    for (const projectName of projects) {
      await expect(page.getByText(projectName)).toBeVisible();
    }
  });
});
```

### 3. Video Upload and Processing Workflow

```javascript
// tests/e2e/videos/video_processing_flow.spec.js

import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Video Upload and Processing Workflow', () => {
  
  let projectId;
  
  test.beforeEach(async ({ page }) => {
    // Login and create a test project
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    // Create test project
    await page.goto('/projects');
    await page.getByRole('button', { name: 'New Project' }).click();
    await page.getByLabel('Project Name').fill('Video Test Project');
    await page.getByLabel('Camera Model').click();
    await page.getByRole('option').first().click();
    await page.getByLabel('Camera View').click();
    await page.getByRole('option').first().click();
    await page.getByLabel('Signal Type').click();
    await page.getByRole('option').first().click();
    await page.getByRole('button', { name: 'Create Project' }).click();
    
    // Extract project ID from URL
    await page.getByText('Video Test Project').click();
    projectId = page.url().split('/').pop();
  });
  
  test('complete video upload and ground truth generation', async ({ page }) => {
    // Step 1: Navigate to video upload section
    await expect(page.getByRole('heading', { name: 'Videos' })).toBeVisible();
    
    // Step 2: Upload video file
    const videoPath = path.join(__dirname, '../../fixtures/videos/test_video.mp4');
    
    await page.getByText('Upload Video').click();
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(videoPath);
    
    // Step 3: Verify upload progress
    await expect(page.getByText('Uploading...')).toBeVisible();
    await expect(page.getByText('Upload complete')).toBeVisible({ timeout: 30000 });
    
    // Step 4: Verify video appears in list
    await expect(page.getByText('test_video.mp4')).toBeVisible();
    await expect(page.getByText('Processing')).toBeVisible();
    
    // Step 5: Wait for processing to complete
    await expect(page.getByText('Completed')).toBeVisible({ timeout: 60000 });
    
    // Step 6: View ground truth data
    await page.getByText('test_video.mp4').click();
    await page.getByRole('tab', { name: 'Ground Truth' }).click();
    
    // Step 7: Verify ground truth visualization
    await expect(page.getByText('Ground Truth Objects')).toBeVisible();
    await expect(page.locator('.video-player')).toBeVisible();
    await expect(page.locator('.bounding-box')).toBeVisible();
    
    // Step 8: Verify ground truth data table
    await expect(page.locator('table')).toBeVisible();
    await expect(page.getByText('Timestamp')).toBeVisible();
    await expect(page.getByText('Object Type')).toBeVisible();
    await expect(page.getByText('Confidence')).toBeVisible();
  });
  
  test('video upload validation and error handling', async ({ page }) => {
    // Test invalid file type
    const textFilePath = path.join(__dirname, '../../fixtures/invalid_file.txt');
    
    await page.getByText('Upload Video').click();
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(textFilePath);
    
    await expect(page.getByText('Invalid file type. Please upload a video file.')).toBeVisible();
    
    // Test oversized file (mock large file)
    await page.evaluate(() => {
      // Create a mock large file
      const largeFile = new File(['x'.repeat(1000000000)], 'large_video.mp4', {
        type: 'video/mp4'
      });
      
      // Simulate file selection
      const input = document.querySelector('input[type="file"]');
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(largeFile);
      input.files = dataTransfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    
    await expect(page.getByText('File size exceeds maximum limit')).toBeVisible();
  });
});
```

### 4. Test Execution and Validation Workflow

```javascript
// tests/e2e/testing/test_execution_flow.spec.js

import { test, expect } from '@playwright/test';

test.describe('Test Execution and Validation Workflow', () => {
  
  let projectId, videoId;
  
  test.beforeEach(async ({ page }) => {
    // Setup: Login, create project, upload video
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    // Navigate to existing project with processed video
    await page.goto('/projects');
    await page.getByText('Test Project').first().click();
    projectId = page.url().split('/').pop();
  });
  
  test('complete test session creation and execution', async ({ page }) => {
    // Step 1: Navigate to test execution
    await page.getByRole('tab', { name: 'Test Execution' }).click();
    await expect(page.getByRole('heading', { name: 'Test Sessions' })).toBeVisible();
    
    // Step 2: Create new test session
    await page.getByRole('button', { name: 'New Test Session' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    
    // Step 3: Configure test session
    const sessionName = `E2E Test Session ${Date.now()}`;
    await page.getByLabel('Session Name').fill(sessionName);
    
    await page.getByLabel('Select Video').click();
    await page.getByRole('option').first().click();
    
    await page.getByLabel('Tolerance (ms)').fill('100');
    
    // Step 4: Start test session
    await page.getByRole('button', { name: 'Start Test Session' }).click();
    
    // Step 5: Verify session creation
    await expect(page.getByText('Test session created successfully')).toBeVisible();
    await expect(page.getByText(sessionName)).toBeVisible();
    await expect(page.getByText('Running')).toBeVisible();
    
    // Step 6: Simulate Raspberry Pi detection events
    // This would normally come from hardware, but we simulate via API calls
    await page.evaluate(async (sessionId) => {
      // Simulate detection events
      const events = [
        { timestamp: 10.5, confidence: 0.89, class_label: 'pedestrian' },
        { timestamp: 25.2, confidence: 0.76, class_label: 'cyclist' },
        { timestamp: 45.8, confidence: 0.93, class_label: 'pedestrian' }
      ];
      
      for (const event of events) {
        await fetch('/api/detection-events', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          },
          body: JSON.stringify({
            test_session_id: sessionId,
            ...event
          })
        });
      }
    }, 'test-session-id');
    
    // Step 7: Monitor test progress
    await page.getByText('View Live Results').click();
    await expect(page.getByText('Detection Events')).toBeVisible();
    await expect(page.locator('.detection-event')).toHaveCount(3);
    
    // Step 8: Complete test session
    await page.getByRole('button', { name: 'Stop Test Session' }).click();
    await expect(page.getByText('Completed')).toBeVisible();
    
    // Step 9: View final results
    await page.getByText('View Results').click();
    await expect(page).toHaveURL(/\/results\/[a-f0-9-]+/);
    await expect(page.getByRole('heading', { name: 'Test Results' })).toBeVisible();
  });
  
  test('real-time detection monitoring', async ({ page }) => {
    // Create and start test session
    await page.getByRole('tab', { name: 'Test Execution' }).click();
    await page.getByRole('button', { name: 'New Test Session' }).click();
    await page.getByLabel('Session Name').fill('Real-time Test');
    await page.getByLabel('Select Video').click();
    await page.getByRole('option').first().click();
    await page.getByRole('button', { name: 'Start Test Session' }).click();
    
    // Open live monitoring
    await page.getByText('View Live Results').click();
    
    // Verify real-time updates (WebSocket connection)
    await expect(page.getByText('Live Detection Feed')).toBeVisible();
    await expect(page.locator('.status-indicator.connected')).toBeVisible();
    
    // Simulate real-time detection
    await page.evaluate(() => {
      // Mock WebSocket message
      window.dispatchEvent(new CustomEvent('detection-event', {
        detail: {
          timestamp: Date.now() / 1000,
          confidence: 0.87,
          class_label: 'pedestrian',
          validation_result: 'TP'
        }
      }));
    });
    
    // Verify real-time display update
    await expect(page.locator('.detection-event').last()).toBeVisible();
    await expect(page.getByText('TP')).toBeVisible();
  });
});
```

### 5. Results Analysis and Reporting Workflow

```javascript
// tests/e2e/results/results_analysis_flow.spec.js

import { test, expect } from '@playwright/test';

test.describe('Results Analysis and Reporting Workflow', () => {
  
  test.beforeEach(async ({ page }) => {
    // Login and navigate to results page
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.goto('/results');
  });
  
  test('comprehensive results analysis workflow', async ({ page }) => {
    // Step 1: View results overview
    await expect(page.getByRole('heading', { name: 'Test Results' })).toBeVisible();
    await expect(page.getByText('Recent Test Sessions')).toBeVisible();
    
    // Step 2: Select a completed test session
    await page.getByText('Completed Test Session').first().click();
    
    // Step 3: Verify results dashboard
    await expect(page.getByText('Performance Metrics')).toBeVisible();
    await expect(page.locator('.metric-card')).toHaveCount(4); // Precision, Recall, F1, Accuracy
    
    // Step 4: Analyze detailed metrics
    const precisionValue = await page.locator('[data-testid="precision-value"]').textContent();
    const recallValue = await page.locator('[data-testid="recall-value"]').textContent();
    const f1Value = await page.locator('[data-testid="f1-value"]').textContent();
    const accuracyValue = await page.locator('[data-testid="accuracy-value"]').textContent();
    
    // Verify metrics are displayed as percentages
    expect(precisionValue).toMatch(/\d+\.\d+%/);
    expect(recallValue).toMatch(/\d+\.\d+%/);
    expect(f1Value).toMatch(/\d+\.\d+%/);
    expect(accuracyValue).toMatch(/\d+\.\d+%/);
    
    // Step 5: View detection timeline
    await page.getByRole('tab', { name: 'Timeline' }).click();
    await expect(page.locator('.timeline-chart')).toBeVisible();
    await expect(page.getByText('Ground Truth Events')).toBeVisible();
    await expect(page.getByText('Detection Events')).toBeVisible();
    
    // Step 6: Analyze confusion matrix
    await page.getByRole('tab', { name: 'Confusion Matrix' }).click();
    await expect(page.locator('.confusion-matrix')).toBeVisible();
    await expect(page.getByText('True Positives')).toBeVisible();
    await expect(page.getByText('False Positives')).toBeVisible();
    await expect(page.getByText('False Negatives')).toBeVisible();
    
    // Step 7: View detailed event list
    await page.getByRole('tab', { name: 'Events' }).click();
    await expect(page.locator('table')).toBeVisible();
    
    // Verify event details table
    await expect(page.getByText('Timestamp')).toBeVisible();
    await expect(page.getByText('Detection Type')).toBeVisible();
    await expect(page.getByText('Confidence')).toBeVisible();
    await expect(page.getByText('Validation Result')).toBeVisible();
    
    // Step 8: Filter events by validation result
    await page.getByLabel('Filter by Result').click();
    await page.getByRole('option', { name: 'True Positives' }).click();
    
    // Verify only TP events are shown
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();
    for (let i = 0; i < rowCount; i++) {
      await expect(rows.nth(i).getByText('TP')).toBeVisible();
    }
  });
  
  test('report generation and export', async ({ page }) => {
    // Navigate to completed test session
    await page.getByText('Completed Test Session').first().click();
    
    // Step 1: Generate PDF report
    await page.getByRole('button', { name: 'Generate Report' }).click();
    await expect(page.getByText('Generating report...')).toBeVisible();
    
    // Step 2: Verify report generation completion
    await expect(page.getByText('Report generated successfully')).toBeVisible({ timeout: 30000 });
    
    // Step 3: Download report
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download PDF' }).click();
    const download = await downloadPromise;
    
    // Verify download
    expect(download.suggestedFilename()).toMatch(/test-results-.*\.pdf/);
    
    // Step 4: Export raw data
    const csvDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export CSV' }).click();
    const csvDownload = await csvDownloadPromise;
    
    // Verify CSV export
    expect(csvDownload.suggestedFilename()).toMatch(/detection-events-.*\.csv/);
  });
  
  test('results comparison across sessions', async ({ page }) => {
    // Step 1: Navigate to comparison view
    await page.getByRole('button', { name: 'Compare Sessions' }).click();
    await expect(page.getByRole('heading', { name: 'Session Comparison' })).toBeVisible();
    
    // Step 2: Select sessions for comparison
    await page.getByLabel('Session 1').click();
    await page.getByRole('option').first().click();
    
    await page.getByLabel('Session 2').click();
    await page.getByRole('option').nth(1).click();
    
    // Step 3: Generate comparison
    await page.getByRole('button', { name: 'Compare' }).click();
    
    // Step 4: Verify comparison charts
    await expect(page.locator('.comparison-chart')).toBeVisible();
    await expect(page.getByText('Precision Comparison')).toBeVisible();
    await expect(page.getByText('Recall Comparison')).toBeVisible();
    
    // Step 5: View side-by-side metrics
    await expect(page.locator('.metrics-comparison')).toBeVisible();
    await expect(page.getByText('Session 1 Metrics')).toBeVisible();
    await expect(page.getByText('Session 2 Metrics')).toBeVisible();
  });
});
```

### 6. Hardware Integration Workflow

```javascript
// tests/e2e/hardware/raspberry_pi_integration.spec.js

import { test, expect } from '@playwright/test';

test.describe('Raspberry Pi Hardware Integration', () => {
  
  test('raspberry pi device configuration and testing', async ({ page }) => {
    // Step 1: Login and navigate to hardware settings
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    await page.goto('/settings');
    await page.getByRole('tab', { name: 'Hardware' }).click();
    
    // Step 2: Configure Raspberry Pi connection
    await expect(page.getByRole('heading', { name: 'Raspberry Pi Configuration' })).toBeVisible();
    
    await page.getByLabel('Device IP Address').fill('192.168.1.100');
    await page.getByLabel('Port').fill('8080');
    await page.getByLabel('API Key').fill('test-api-key-123');
    
    // Step 3: Test connection
    await page.getByRole('button', { name: 'Test Connection' }).click();
    await expect(page.getByText('Testing connection...')).toBeVisible();
    
    // Mock successful connection
    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('pi-connection-test', {
        detail: { status: 'success', message: 'Connection established' }
      }));
    });
    
    await expect(page.getByText('Connection successful')).toBeVisible();
    
    // Step 4: Save configuration
    await page.getByRole('button', { name: 'Save Configuration' }).click();
    await expect(page.getByText('Configuration saved')).toBeVisible();
    
    // Step 5: View device status
    await expect(page.getByText('Device Status: Connected')).toBeVisible();
    await expect(page.getByText('Temperature:')).toBeVisible();
    await expect(page.getByText('CPU Usage:')).toBeVisible();
    await expect(page.getByText('Memory Usage:')).toBeVisible();
  });
  
  test('real-time detection from raspberry pi', async ({ page, context }) => {
    // Setup WebSocket mock for Pi communication
    await context.addInitScript(() => {
      class MockWebSocket {
        constructor(url) {
          this.url = url;
          this.readyState = WebSocket.CONNECTING;
          setTimeout(() => {
            this.readyState = WebSocket.OPEN;
            if (this.onopen) this.onopen();
          }, 100);
        }
        
        send(data) {
          // Mock detection event response
          setTimeout(() => {
            if (this.onmessage) {
              this.onmessage({
                data: JSON.stringify({
                  type: 'detection',
                  timestamp: Date.now() / 1000,
                  confidence: 0.87,
                  class_label: 'pedestrian',
                  bounding_box: { x: 100, y: 100, width: 50, height: 100 }
                })
              });
            }
          }, 50);
        }
        
        close() {
          this.readyState = WebSocket.CLOSED;
          if (this.onclose) this.onclose();
        }
      }
      
      window.WebSocket = MockWebSocket;
    });
    
    // Login and start test session
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    // Navigate to live testing
    await page.goto('/test-execution');
    await page.getByRole('button', { name: 'Start Live Testing' }).click();
    
    // Verify Pi connection status
    await expect(page.getByText('Raspberry Pi: Connected')).toBeVisible();
    
    // Verify live feed
    await expect(page.locator('.live-video-feed')).toBeVisible();
    await expect(page.getByText('Live Detection Feed')).toBeVisible();
    
    // Wait for detection events
    await expect(page.locator('.detection-event')).toBeVisible({ timeout: 5000 });
    
    // Verify detection details
    await expect(page.getByText('pedestrian')).toBeVisible();
    await expect(page.getByText('87%')).toBeVisible(); // confidence
  });
});
```

## Cross-Browser Compatibility Tests

```javascript
// tests/e2e/compatibility/cross_browser.spec.js

import { test, expect } from '@playwright/test';

const browsers = ['chromium', 'firefox', 'webkit'];

browsers.forEach(browser => {
  test.describe(`Cross-browser compatibility - ${browser}`, () => {
    
    test.use({ browserName: browser });
    
    test('basic functionality works across browsers', async ({ page }) => {
      // Test core functionality in each browser
      await page.goto('/login');
      
      // Verify UI elements render correctly
      await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
      await expect(page.getByLabel('Email')).toBeVisible();
      await expect(page.getByLabel('Password')).toBeVisible();
      
      // Test form interaction
      await page.getByLabel('Email').fill('test@example.com');
      await page.getByLabel('Password').fill('password');
      
      // Verify input values
      await expect(page.getByLabel('Email')).toHaveValue('test@example.com');
      await expect(page.getByLabel('Password')).toHaveValue('password');
      
      // Test navigation
      await page.getByRole('button', { name: 'Sign In' }).click();
      await expect(page).toHaveURL('/dashboard');
    });
    
    test('responsive design works correctly', async ({ page }) => {
      // Test mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/dashboard');
      
      // Verify mobile navigation
      await expect(page.getByRole('button', { name: 'Menu' })).toBeVisible();
      
      // Test tablet viewport
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.reload();
      
      // Verify tablet layout
      await expect(page.getByRole('navigation')).toBeVisible();
      
      // Test desktop viewport
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.reload();
      
      // Verify desktop layout
      await expect(page.locator('.sidebar')).toBeVisible();
    });
  });
});
```

## Performance E2E Tests

```javascript
// tests/e2e/performance/performance_validation.spec.js

import { test, expect } from '@playwright/test';

test.describe('Performance Validation', () => {
  
  test('page load performance meets requirements', async ({ page }) => {
    // Start performance monitoring
    await page.goto('/dashboard');
    
    // Measure page load metrics
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0];
      return {
        loadTime: navigation.loadEventEnd - navigation.loadEventStart,
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime
      };
    });
    
    // Assert performance requirements
    expect(performanceMetrics.loadTime).toBeLessThan(2000); // 2 second load time
    expect(performanceMetrics.domContentLoaded).toBeLessThan(1000); // 1 second DOM ready
    expect(performanceMetrics.firstContentfulPaint).toBeLessThan(1500); // 1.5 second FCP
  });
  
  test('video processing UI responsiveness', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    // Navigate to project with large video
    await page.goto('/projects/test-project-id');
    
    // Start video processing
    const startTime = Date.now();
    await page.getByText('Process Video').click();
    
    // Verify UI remains responsive during processing
    await expect(page.getByText('Processing...')).toBeVisible();
    
    // Test UI interactions during processing
    await page.getByRole('tab', { name: 'Settings' }).click();
    const tabClickTime = Date.now() - startTime;
    
    // Assert UI responsiveness
    expect(tabClickTime).toBeLessThan(500); // Tab switch under 500ms
    
    // Verify processing progress updates
    await expect(page.getByText(/\d+% complete/)).toBeVisible();
  });
});
```

## Test Data Management for E2E Tests

```javascript
// tests/e2e/utils/test_data.js

export class E2ETestDataManager {
  
  constructor() {
    this.testUsers = new Map();
    this.testProjects = new Map();
    this.testSessions = new Map();
  }
  
  async createTestUser(page, userData = {}) {
    const defaultUser = {
      email: `test.${Date.now()}@example.com`,
      password: 'SecurePassword123!',
      fullName: 'E2E Test User'
    };
    
    const user = { ...defaultUser, ...userData };
    
    // Register user via UI
    await page.goto('/register');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Full Name').fill(user.fullName);
    await page.getByLabel('Password').fill(user.password);
    await page.getByLabel('Confirm Password').fill(user.password);
    await page.getByRole('button', { name: 'Create Account' }).click();
    
    // Store user data
    const userId = `user-${Date.now()}`;
    this.testUsers.set(userId, user);
    
    return { id: userId, ...user };
  }
  
  async loginUser(page, user) {
    await page.goto('/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.waitForURL('/dashboard');
  }
  
  async createTestProject(page, projectData = {}) {
    const defaultProject = {
      name: `Test Project ${Date.now()}`,
      description: 'E2E test project',
      cameraModel: 'FLIR Blackfly S',
      cameraView: 'Front-facing VRU',
      signalType: 'GPIO'
    };
    
    const project = { ...defaultProject, ...projectData };
    
    // Create project via UI
    await page.goto('/projects');
    await page.getByRole('button', { name: 'New Project' }).click();
    await page.getByLabel('Project Name').fill(project.name);
    await page.getByLabel('Description').fill(project.description);
    // ... fill other fields
    await page.getByRole('button', { name: 'Create Project' }).click();
    
    // Extract project ID from URL
    await page.getByText(project.name).click();
    const projectId = page.url().split('/').pop();
    
    this.testProjects.set(projectId, project);
    
    return { id: projectId, ...project };
  }
  
  async cleanup(page) {
    // Clean up test data
    for (const [projectId] of this.testProjects) {
      try {
        await page.goto(`/projects/${projectId}`);
        await page.getByRole('button', { name: 'Delete Project' }).click();
        await page.getByRole('button', { name: 'Confirm Delete' }).click();
      } catch (error) {
        console.warn(`Failed to cleanup project ${projectId}:`, error);
      }
    }
    
    // Clear collections
    this.testUsers.clear();
    this.testProjects.clear();
    this.testSessions.clear();
  }
}
```

## Test Execution Configuration

```javascript
// tests/e2e/config/global-setup.js

import { chromium } from '@playwright/test';

export default async function globalSetup() {
  // Start test services
  console.log('Starting E2E test environment...');
  
  // Wait for backend to be ready
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  let retries = 30;
  while (retries > 0) {
    try {
      const response = await page.goto('http://localhost:8000/health');
      if (response.ok()) {
        console.log('Backend service is ready');
        break;
      }
    } catch (error) {
      console.log(`Waiting for backend... ${retries} retries left`);
      await new Promise(resolve => setTimeout(resolve, 1000));
      retries--;
    }
  }
  
  if (retries === 0) {
    throw new Error('Backend service failed to start');
  }
  
  await browser.close();
  console.log('E2E test environment ready');
}
```

This comprehensive E2E test specification ensures complete user workflow validation while providing maintainable and scalable test scenarios that cover all critical system functionalities.