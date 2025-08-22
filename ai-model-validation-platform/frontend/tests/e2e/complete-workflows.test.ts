/**
 * End-to-End Workflow Tests
 * 
 * Tests complete user journeys and system integration scenarios
 * for the AI Model Validation Platform
 */

import { describe, test, expect, beforeAll, afterAll, beforeEach } from '@jest/globals';
import { Page, Browser, chromium, firefox, webkit } from 'playwright';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs/promises';
import path from 'path';

// Test configuration
const TEST_CONFIG = {
  frontend_url: process.env.FRONTEND_URL || 'http://localhost:3000',
  backend_url: process.env.BACKEND_URL || 'http://localhost:8000',
  test_timeout: 60000,
  video_upload_timeout: 30000,
  detection_timeout: 45000
};

// Browser instances for cross-browser testing
let browsers: { name: string; browser: Browser }[] = [];
let backendProcess: ChildProcess | null = null;
let frontendProcess: ChildProcess | null = null;

// Test data paths
const TEST_DATA_DIR = path.join(__dirname, '../fixtures');
const TEST_VIDEO_PATH = path.join(TEST_DATA_DIR, 'test-video.mp4');
const LARGE_VIDEO_PATH = path.join(TEST_DATA_DIR, 'large-test-video.mp4');

// ============================================================================
// TEST SETUP AND TEARDOWN
// ============================================================================

beforeAll(async () => {
  // Start backend server
  if (process.env.START_SERVICES === 'true') {
    backendProcess = spawn('python', ['main.py'], {
      cwd: path.join(__dirname, '../../../backend'),
      stdio: 'pipe'
    });
    
    // Wait for backend to start
    await new Promise(resolve => setTimeout(resolve, 5000));
  }

  // Launch browsers for cross-browser testing
  const browserTypes = [chromium, firefox, webkit];
  const browserNames = ['chromium', 'firefox', 'webkit'];
  
  for (let i = 0; i < browserTypes.length; i++) {
    try {
      const browser = await browserTypes[i].launch({
        headless: process.env.HEADLESS !== 'false',
        slowMo: process.env.SLOW_MO ? parseInt(process.env.SLOW_MO) : 0
      });
      browsers.push({ name: browserNames[i], browser });
    } catch (error) {
      console.warn(`Failed to launch ${browserNames[i]}: ${error}`);
    }
  }

  // Ensure test data exists
  await ensureTestData();
}, 120000);

afterAll(async () => {
  // Close browsers
  for (const { browser } of browsers) {
    await browser.close();
  }

  // Stop services
  if (backendProcess) {
    backendProcess.kill();
  }
  if (frontendProcess) {
    frontendProcess.kill();
  }
});

// Helper function to ensure test data exists
async function ensureTestData() {
  try {
    await fs.access(TEST_DATA_DIR);
  } catch {
    await fs.mkdir(TEST_DATA_DIR, { recursive: true });
  }

  // Create test video files if they don't exist
  try {
    await fs.access(TEST_VIDEO_PATH);
  } catch {
    // Create a simple test video file (placeholder)
    await fs.writeFile(TEST_VIDEO_PATH, Buffer.alloc(1024 * 1024, 0x89)); // 1MB placeholder
  }

  try {
    await fs.access(LARGE_VIDEO_PATH);
  } catch {
    // Create a larger test video file (placeholder)
    await fs.writeFile(LARGE_VIDEO_PATH, Buffer.alloc(50 * 1024 * 1024, 0x89)); // 50MB placeholder
  }
}

// Helper function to create a new page
async function createPage(browserName: string = 'chromium'): Promise<Page> {
  const browserEntry = browsers.find(b => b.name === browserName);
  if (!browserEntry) {
    throw new Error(`Browser ${browserName} not available`);
  }

  const context = await browserEntry.browser.newContext({
    viewport: { width: 1920, height: 1080 },
    permissions: ['camera', 'microphone'],
    recordVideo: process.env.RECORD_VIDEO === 'true' ? {
      dir: path.join(__dirname, '../videos')
    } : undefined
  });

  return await context.newPage();
}

// Helper function to wait for backend health
async function waitForBackend(page: Page, timeout: number = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const response = await page.request.get(`${TEST_CONFIG.backend_url}/health`);
      if (response.ok()) return;
    } catch {
      // Continue waiting
    }
    await page.waitForTimeout(1000);
  }
  throw new Error('Backend not ready');
}

// ============================================================================
// COMPLETE USER JOURNEY TESTS
// ============================================================================

describe('Complete User Journey - Project Creation to Results', () => {
  test('should complete full workflow: project → video upload → annotation → test execution → results', async () => {
    const page = await createPage();
    
    try {
      // Wait for services to be ready
      await waitForBackend(page);
      
      // Navigate to application
      await page.goto(TEST_CONFIG.frontend_url);
      await page.waitForLoadState('networkidle');
      
      // Verify landing page
      await expect(page.locator('h1')).toContainText('AI Model Validation Platform');
      
      // ============================================================================
      // STEP 1: PROJECT CREATION
      // ============================================================================
      
      // Navigate to projects
      await page.click('text=Projects');
      await page.waitForURL('**/projects');
      
      // Create new project
      await page.click('button:has-text("Create Project")');
      
      // Fill project form
      await page.fill('[data-testid="project-name-input"]', 'E2E Test Project');
      await page.fill('[data-testid="project-description-input"]', 'End-to-end testing project for AI model validation');
      
      // Select camera type
      await page.click('[data-testid="camera-type-select"]');
      await page.click('text=Surveillance Camera');
      
      // Configure detection classes
      await page.check('input[value="person"]');
      await page.check('input[value="vehicle"]');
      
      // Set performance criteria
      await page.fill('[data-testid="accuracy-threshold"]', '0.85');
      await page.fill('[data-testid="latency-threshold"]', '100');
      
      // Submit project creation
      await page.click('button:has-text("Create")');
      
      // Verify project creation
      await expect(page.locator('[data-testid="success-message"]')).toContainText('Project created successfully');
      await expect(page.locator('text=E2E Test Project')).toBeVisible();
      
      // ============================================================================
      // STEP 2: VIDEO UPLOAD
      // ============================================================================
      
      // Navigate to video upload
      await page.click('[data-testid="upload-video-button"]');
      
      // Upload test video
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_VIDEO_PATH);
      
      // Verify file selection
      await expect(page.locator('[data-testid="selected-file"]')).toContainText('test-video.mp4');
      
      // Configure upload options
      await page.check('[data-testid="auto-process-checkbox"]');
      await page.check('[data-testid="generate-thumbnail-checkbox"]');
      
      // Start upload
      await page.click('button:has-text("Upload")');
      
      // Wait for upload progress
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
      
      // Wait for upload completion
      await expect(page.locator('[data-testid="upload-complete"]')).toBeVisible({
        timeout: TEST_CONFIG.video_upload_timeout
      });
      
      // Verify video appears in library
      await page.click('text=Video Library');
      await expect(page.locator('text=test-video.mp4')).toBeVisible();
      
      // ============================================================================
      // STEP 3: VIDEO ANNOTATION
      // ============================================================================
      
      // Open video for annotation
      await page.click('[data-testid="video-item"]:has-text("test-video.mp4")');
      await page.click('button:has-text("Annotate")');
      
      // Wait for video player to load
      await expect(page.locator('video')).toBeVisible();
      await page.waitForFunction(() => {
        const video = document.querySelector('video') as HTMLVideoElement;
        return video && video.readyState >= 2; // HAVE_CURRENT_DATA
      });
      
      // Enter annotation mode
      await page.click('[data-testid="annotation-mode-toggle"]');
      await expect(page.locator('[data-testid="annotation-tools"]')).toBeVisible();
      
      // Create rectangle annotation
      await page.click('[data-testid="rectangle-tool"]');
      
      // Draw annotation on video canvas
      const canvas = page.locator('[data-testid="annotation-canvas"]');
      await canvas.click({ position: { x: 100, y: 100 } });
      await canvas.click({ position: { x: 200, y: 200 } });
      
      // Fill annotation properties
      await page.fill('[data-testid="annotation-label"]', 'person');
      await page.fill('[data-testid="annotation-confidence"]', '1.0');
      await page.click('button:has-text("Save Annotation")');
      
      // Verify annotation saved
      await expect(page.locator('[data-testid="annotation-list"] >> text=person')).toBeVisible();
      
      // Create additional annotations
      await page.click('[data-testid="circle-tool"]');
      await canvas.click({ position: { x: 300, y: 150 } });
      await canvas.click({ position: { x: 350, y: 200 } });
      
      await page.fill('[data-testid="annotation-label"]', 'vehicle');
      await page.click('button:has-text("Save Annotation")');
      
      // Navigate through frames
      await page.click('[data-testid="next-frame-button"]');
      await page.click('[data-testid="next-frame-button"]');
      
      // Add temporal annotation
      await page.click('[data-testid="polygon-tool"]');
      const points = [{ x: 400, y: 100 }, { x: 450, y: 120 }, { x: 430, y: 180 }, { x: 380, y: 160 }];
      for (const point of points) {
        await canvas.click({ position: point });
      }
      await canvas.dblclick({ position: points[0] }); // Close polygon
      
      await page.fill('[data-testid="annotation-label"]', 'bicycle');
      await page.click('button:has-text("Save Annotation")');
      
      // Export annotations
      await page.click('[data-testid="export-annotations-button"]');
      await page.selectOption('[data-testid="export-format-select"]', 'COCO');
      await page.click('button:has-text("Export")');
      
      // Verify export
      await expect(page.locator('[data-testid="export-complete"]')).toBeVisible();
      
      // ============================================================================
      // STEP 4: TEST EXECUTION SETUP
      // ============================================================================
      
      // Navigate to test execution
      await page.click('text=Test Execution');
      await page.waitForURL('**/test-execution');
      
      // Select project
      await page.click('[data-testid="project-select"]');
      await page.click('text=E2E Test Project');
      
      // Configure test session
      await page.fill('[data-testid="session-name"]', 'E2E Test Session');
      
      // Select videos for testing
      await page.check('[data-testid="video-checkbox"]:has-text("test-video.mp4")');
      
      // Configure detection parameters
      await page.fill('[data-testid="confidence-threshold"]', '0.7');
      await page.fill('[data-testid="iou-threshold"]', '0.5');
      
      // Set performance criteria
      await page.fill('[data-testid="latency-limit"]', '100');
      await page.fill('[data-testid="accuracy-target"]', '0.85');
      
      // Enable real-time monitoring
      await page.check('[data-testid="realtime-monitoring"]');
      
      // Configure signal validation
      await page.check('[data-testid="signal-validation-enabled"]');
      await page.selectOption('[data-testid="signal-type-select"]', 'pedestrian_crossing');
      await page.fill('[data-testid="signal-latency-limit"]', '150');
      
      // ============================================================================
      // STEP 5: TEST EXECUTION
      // ============================================================================
      
      // Start test execution
      await page.click('button:has-text("Start Test")');
      
      // Verify test session created
      await expect(page.locator('[data-testid="test-status"]')).toContainText('Running');
      
      // Monitor real-time updates
      await expect(page.locator('[data-testid="detection-counter"]')).toBeVisible();
      await expect(page.locator('[data-testid="accuracy-meter"]')).toBeVisible();
      await expect(page.locator('[data-testid="latency-display"]')).toBeVisible();
      
      // Wait for detections to appear
      await expect(page.locator('[data-testid="detection-event"]').first()).toBeVisible({
        timeout: TEST_CONFIG.detection_timeout
      });
      
      // Verify detection details
      const firstDetection = page.locator('[data-testid="detection-event"]').first();
      await expect(firstDetection.locator('[data-testid="detection-class"]')).toBeVisible();
      await expect(firstDetection.locator('[data-testid="detection-confidence"]')).toBeVisible();
      await expect(firstDetection.locator('[data-testid="detection-latency"]')).toBeVisible();
      
      // Check validation result
      await expect(firstDetection.locator('[data-testid="validation-result"]')).toHaveClass(/TP|FP|FN/);
      
      // Monitor progress
      const progressBar = page.locator('[data-testid="test-progress"]');
      await expect(progressBar).toHaveAttribute('aria-valuenow', /[1-9]\d*/);
      
      // Wait for test completion
      await expect(page.locator('[data-testid="test-status"]')).toContainText('Completed', {
        timeout: TEST_CONFIG.test_timeout
      });
      
      // ============================================================================
      // STEP 6: RESULTS ANALYSIS
      // ============================================================================
      
      // Verify final metrics
      await expect(page.locator('[data-testid="final-accuracy"]')).toBeVisible();
      await expect(page.locator('[data-testid="final-precision"]')).toBeVisible();
      await expect(page.locator('[data-testid="final-recall"]')).toBeVisible();
      await expect(page.locator('[data-testid="final-f1-score"]')).toBeVisible();
      
      // Check pass/fail result
      const passFailResult = page.locator('[data-testid="pass-fail-result"]');
      await expect(passFailResult).toHaveClass(/(pass|fail)/);
      
      // Verify detailed metrics
      await expect(page.locator('[data-testid="total-detections"]')).not.toHaveText('0');
      await expect(page.locator('[data-testid="avg-latency"]')).toBeVisible();
      await expect(page.locator('[data-testid="max-latency"]')).toBeVisible();
      
      // View detection timeline
      await page.click('[data-testid="timeline-view-button"]');
      await expect(page.locator('[data-testid="detection-timeline"]')).toBeVisible();
      
      // Check performance charts
      await page.click('[data-testid="charts-view-button"]');
      await expect(page.locator('[data-testid="accuracy-chart"]')).toBeVisible();
      await expect(page.locator('[data-testid="latency-chart"]')).toBeVisible();
      
      // ============================================================================
      // STEP 7: EXPORT RESULTS
      // ============================================================================
      
      // Export test results
      await page.click('[data-testid="export-results-button"]');
      
      // Configure export options
      await page.check('[data-testid="include-raw-data"]');
      await page.check('[data-testid="include-metrics"]');
      await page.check('[data-testid="include-charts"]');
      
      // Select export format
      await page.selectOption('[data-testid="export-format-select"]', 'JSON');
      
      // Generate report
      await page.click('button:has-text("Generate Report")');
      
      // Verify export completion
      await expect(page.locator('[data-testid="export-complete"]')).toBeVisible();
      
      // Download results
      const downloadPromise = page.waitForEvent('download');
      await page.click('[data-testid="download-results-link"]');
      const download = await downloadPromise;
      
      // Verify download
      expect(download.suggestedFilename()).toMatch(/test-results.*\.json$/);
      
      // ============================================================================
      // STEP 8: AUDIT AND CLEANUP
      // ============================================================================
      
      // Navigate to audit logs
      await page.click('text=Audit Logs');
      
      // Verify all actions are logged
      await expect(page.locator('[data-testid="audit-entry"]:has-text("project_created")')).toBeVisible();
      await expect(page.locator('[data-testid="audit-entry"]:has-text("video_uploaded")')).toBeVisible();
      await expect(page.locator('[data-testid="audit-entry"]:has-text("annotation_created")')).toBeVisible();
      await expect(page.locator('[data-testid="audit-entry"]:has-text("test_executed")')).toBeVisible();
      
      // Verify system health
      await page.click('[data-testid="system-health-button"]');
      await expect(page.locator('[data-testid="system-status"]')).toHaveClass(/healthy|warning/);
      
      console.log('✅ Complete user journey test passed successfully');
      
    } finally {
      await page.close();
    }
  }, 180000); // 3 minute timeout
});

// ============================================================================
// PERFORMANCE AND STRESS TESTS
// ============================================================================

describe('Performance and Load Testing', () => {
  test('should handle concurrent video uploads', async () => {
    const pages = await Promise.all([
      createPage(),
      createPage(),
      createPage()
    ]);
    
    try {
      // Navigate all pages to upload interface
      await Promise.all(pages.map(async (page, index) => {
        await page.goto(`${TEST_CONFIG.frontend_url}/projects`);
        await page.waitForLoadState('networkidle');
        
        // Create unique project for each upload
        await page.click('button:has-text("Create Project")');
        await page.fill('[data-testid="project-name-input"]', `Concurrent Test ${index + 1}`);
        await page.click('button:has-text("Create")');
        
        await page.click('[data-testid="upload-video-button"]');
      }));
      
      // Start uploads simultaneously
      const uploadPromises = pages.map(async (page, index) => {
        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles(TEST_VIDEO_PATH);
        await page.click('button:has-text("Upload")');
        
        // Wait for completion
        await expect(page.locator('[data-testid="upload-complete"]')).toBeVisible({
          timeout: TEST_CONFIG.video_upload_timeout
        });
        
        return `Upload ${index + 1} completed`;
      });
      
      // Wait for all uploads to complete
      const results = await Promise.all(uploadPromises);
      expect(results).toHaveLength(3);
      
      console.log('✅ Concurrent upload test passed');
      
    } finally {
      await Promise.all(pages.map(page => page.close()));
    }
  });
  
  test('should handle large file upload with progress tracking', async () => {
    const page = await createPage();
    
    try {
      await page.goto(`${TEST_CONFIG.frontend_url}/projects`);
      
      // Create project for large file test
      await page.click('button:has-text("Create Project")');
      await page.fill('[data-testid="project-name-input"]', 'Large File Test');
      await page.click('button:has-text("Create")');
      
      // Upload large file
      await page.click('[data-testid="upload-video-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(LARGE_VIDEO_PATH);
      
      // Start upload
      await page.click('button:has-text("Upload")');
      
      // Monitor progress
      const progressBar = page.locator('[data-testid="upload-progress"]');
      await expect(progressBar).toBeVisible();
      
      // Check progress increments
      let lastProgress = 0;
      let progressIncreased = false;
      
      for (let i = 0; i < 10; i++) {
        await page.waitForTimeout(1000);
        
        const progressText = await progressBar.textContent();
        const currentProgress = parseInt(progressText?.match(/\d+/)?.[0] || '0');
        
        if (currentProgress > lastProgress) {
          progressIncreased = true;
          lastProgress = currentProgress;
        }
        
        if (currentProgress >= 100) break;
      }
      
      expect(progressIncreased).toBe(true);
      
      // Wait for completion
      await expect(page.locator('[data-testid="upload-complete"]')).toBeVisible({
        timeout: TEST_CONFIG.video_upload_timeout * 3 // Longer timeout for large file
      });
      
      console.log('✅ Large file upload test passed');
      
    } finally {
      await page.close();
    }
  });
  
  test('should maintain performance under continuous detection load', async () => {
    const page = await createPage();
    
    try {
      await page.goto(`${TEST_CONFIG.frontend_url}/test-execution`);
      
      // Setup continuous detection test
      await page.fill('[data-testid="session-name"]', 'Performance Load Test');
      await page.selectOption('[data-testid="test-duration-select"]', '60'); // 1 minute
      await page.check('[data-testid="continuous-detection"]');
      await page.fill('[data-testid="detection-rate"]', '10'); // 10 detections per second
      
      // Start performance test
      await page.click('button:has-text("Start Performance Test")');
      
      // Monitor system metrics
      const metricsPanel = page.locator('[data-testid="performance-metrics"]');
      await expect(metricsPanel).toBeVisible();
      
      // Check CPU usage stays reasonable
      const cpuUsage = page.locator('[data-testid="cpu-usage"]');
      await expect(cpuUsage).toBeVisible();
      
      // Monitor for 30 seconds
      for (let i = 0; i < 30; i++) {
        await page.waitForTimeout(1000);
        
        const cpuText = await cpuUsage.textContent();
        const cpuValue = parseFloat(cpuText?.match(/[\d.]+/)?.[0] || '0');
        
        // CPU should not exceed 90%
        expect(cpuValue).toBeLessThan(90);
        
        // Check memory usage
        const memoryUsage = page.locator('[data-testid="memory-usage"]');
        const memoryText = await memoryUsage.textContent();
        const memoryValue = parseFloat(memoryText?.match(/[\d.]+/)?.[0] || '0');
        
        // Memory should not exceed 85%
        expect(memoryValue).toBeLessThan(85);
      }
      
      // Verify detection count is reasonable
      const detectionCount = page.locator('[data-testid="detection-counter"]');
      const countText = await detectionCount.textContent();
      const count = parseInt(countText?.match(/\d+/)?.[0] || '0');
      
      // Should have processed detections (at least 100 in 30 seconds at 10/sec)
      expect(count).toBeGreaterThan(100);
      
      console.log(`✅ Performance test passed with ${count} detections processed`);
      
    } finally {
      await page.close();
    }
  });
});

// ============================================================================
// CROSS-BROWSER COMPATIBILITY TESTS
// ============================================================================

describe('Cross-Browser Compatibility', () => {
  test.each(['chromium', 'firefox', 'webkit'])(
    'should work correctly in %s',
    async (browserName) => {
      const page = await createPage(browserName);
      
      try {
        await page.goto(TEST_CONFIG.frontend_url);
        await page.waitForLoadState('networkidle');
        
        // Test basic functionality
        await expect(page.locator('h1')).toContainText('AI Model Validation Platform');
        
        // Test navigation
        await page.click('text=Projects');
        await page.waitForURL('**/projects');
        
        // Test video player support
        await page.goto(`${TEST_CONFIG.frontend_url}/test-execution`);
        
        // Check if browser supports required features
        const hasVideoSupport = await page.evaluate(() => {
          const video = document.createElement('video');
          return !!(video.canPlayType && video.canPlayType('video/mp4'));
        });
        
        expect(hasVideoSupport).toBe(true);
        
        // Test WebSocket support
        const hasWebSocketSupport = await page.evaluate(() => {
          return typeof WebSocket !== 'undefined';
        });
        
        expect(hasWebSocketSupport).toBe(true);
        
        // Test File API support
        const hasFileAPISupport = await page.evaluate(() => {
          return typeof FileReader !== 'undefined' && typeof FormData !== 'undefined';
        });
        
        expect(hasFileAPISupport).toBe(true);
        
        console.log(`✅ ${browserName} compatibility test passed`);
        
      } finally {
        await page.close();
      }
    }
  );
});

// ============================================================================
// ERROR HANDLING AND RECOVERY TESTS
// ============================================================================

describe('Error Handling and Recovery', () => {
  test('should handle network disconnection gracefully', async () => {
    const page = await createPage();
    
    try {
      await page.goto(TEST_CONFIG.frontend_url);
      
      // Start a test session
      await page.click('text=Test Execution');
      await page.fill('[data-testid="session-name"]', 'Network Test');
      await page.click('button:has-text("Start Test")');
      
      // Simulate network disconnection
      await page.route('**/*', route => route.abort());
      
      // Verify offline indicator appears
      await expect(page.locator('[data-testid="offline-indicator"]')).toBeVisible();
      
      // Restore network
      await page.unroute('**/*');
      
      // Verify reconnection
      await expect(page.locator('[data-testid="online-indicator"]')).toBeVisible();
      
      // Verify data sync after reconnection
      await expect(page.locator('[data-testid="sync-complete"]')).toBeVisible();
      
      console.log('✅ Network disconnection handling test passed');
      
    } finally {
      await page.close();
    }
  });
  
  test('should recover from server errors', async () => {
    const page = await createPage();
    
    try {
      await page.goto(TEST_CONFIG.frontend_url);
      
      // Mock server error
      await page.route('**/api/**', route => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal Server Error' })
        });
      });
      
      // Try to create a project
      await page.click('text=Projects');
      await page.click('button:has-text("Create Project")');
      await page.fill('[data-testid="project-name-input"]', 'Error Test');
      await page.click('button:has-text("Create")');
      
      // Verify error message
      await expect(page.locator('[data-testid="error-message"]')).toContainText('Internal Server Error');
      
      // Verify retry button
      await expect(page.locator('button:has-text("Retry")')).toBeVisible();
      
      // Restore normal API
      await page.unroute('**/api/**');
      
      // Retry operation
      await page.click('button:has-text("Retry")');
      
      // Verify success
      await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
      
      console.log('✅ Server error recovery test passed');
      
    } finally {
      await page.close();
    }
  });
});

// ============================================================================
// ACCESSIBILITY TESTS
// ============================================================================

describe('Accessibility Compliance', () => {
  test('should be fully keyboard navigable', async () => {
    const page = await createPage();
    
    try {
      await page.goto(TEST_CONFIG.frontend_url);
      
      // Test keyboard navigation
      await page.press('body', 'Tab');
      await expect(page.locator(':focus')).toBeVisible();
      
      // Navigate through main menu
      await page.press(':focus', 'Enter');
      await page.press('body', 'Tab');
      await page.press('body', 'Tab');
      
      // Test video player keyboard controls
      await page.goto(`${TEST_CONFIG.frontend_url}/test-execution`);
      
      // Focus video player
      await page.press('body', 'Tab');
      const focusedElement = page.locator(':focus');
      
      // Test space bar for play/pause
      await page.press(':focus', 'Space');
      
      // Test arrow keys for seeking
      await page.press(':focus', 'ArrowRight');
      await page.press(':focus', 'ArrowLeft');
      
      console.log('✅ Keyboard navigation test passed');
      
    } finally {
      await page.close();
    }
  });
  
  test('should have proper ARIA attributes', async () => {
    const page = await createPage();
    
    try {
      await page.goto(TEST_CONFIG.frontend_url);
      
      // Check main landmarks
      await expect(page.locator('[role="main"]')).toBeVisible();
      await expect(page.locator('[role="navigation"]')).toBeVisible();
      
      // Check button accessibility
      const buttons = page.locator('button');
      const buttonCount = await buttons.count();
      
      for (let i = 0; i < buttonCount; i++) {
        const button = buttons.nth(i);
        const ariaLabel = await button.getAttribute('aria-label');
        const textContent = await button.textContent();
        
        // Button should have accessible name
        expect(ariaLabel || textContent?.trim()).toBeTruthy();
      }
      
      // Check form accessibility
      await page.click('text=Projects');
      await page.click('button:has-text("Create Project")');
      
      const formInputs = page.locator('input, select, textarea');
      const inputCount = await formInputs.count();
      
      for (let i = 0; i < inputCount; i++) {
        const input = formInputs.nth(i);
        const id = await input.getAttribute('id');
        const ariaLabel = await input.getAttribute('aria-label');
        const ariaLabelledBy = await input.getAttribute('aria-labelledby');
        
        // Input should have associated label
        if (id) {
          const label = page.locator(`label[for="${id}"]`);
          const hasLabel = await label.count() > 0;
          expect(hasLabel || ariaLabel || ariaLabelledBy).toBeTruthy();
        }
      }
      
      console.log('✅ ARIA attributes test passed');
      
    } finally {
      await page.close();
    }
  });
});
