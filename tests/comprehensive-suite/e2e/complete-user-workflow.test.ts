import { test, expect, Page } from '@playwright/test';
import { TEST_PROJECTS, TEST_VIDEOS, TEST_ANNOTATIONS } from '../fixtures/test-videos';

// E2E Tests for Complete User Workflow
test.describe('Complete User Workflow E2E Tests', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
    
    // Wait for app to load
    await page.waitForSelector('[data-testid="app-header"]', { timeout: 10000 });
  });

  test('Complete video upload → project creation → ground truth → annotations workflow', async ({ page }) => {
    // Step 1: Upload video to central store
    await test.step('Upload video file', async () => {
      await page.click('[data-testid="nav-ground-truth"]');
      await page.waitForSelector('[data-testid="video-upload-area"]');
      
      // Create a test video file
      const videoBuffer = Buffer.from('mock video content for e2e testing');
      
      // Upload video file
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'e2e-test-video.mp4',
        mimeType: 'video/mp4',
        buffer: videoBuffer
      });
      
      // Wait for upload to complete
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });
      
      // Verify video appears in the list
      await expect(page.locator('[data-testid="video-item"]')).toContainText('e2e-test-video.mp4');
    });

    // Step 2: Create new project
    await test.step('Create new project', async () => {
      await page.click('[data-testid="nav-projects"]');
      await page.click('[data-testid="create-project-btn"]');
      
      // Fill project form
      await page.fill('[data-testid="project-name"]', 'E2E Test Project');
      await page.fill('[data-testid="project-description"]', 'Project created during E2E testing');
      await page.selectOption('[data-testid="camera-model"]', 'TestCam v1.0');
      await page.selectOption('[data-testid="camera-view"]', 'Front-facing VRU');
      await page.selectOption('[data-testid="signal-type"]', 'GPIO');
      
      // Submit form
      await page.click('[data-testid="submit-project"]');
      
      // Wait for project creation success
      await expect(page.locator('[data-testid="success-notification"]')).toBeVisible();
      await expect(page.locator('[data-testid="project-card"]')).toContainText('E2E Test Project');
    });

    // Step 3: Link video to project
    await test.step('Link video to project', async () => {
      // Click on the created project
      await page.click('[data-testid="project-card"]:has-text("E2E Test Project")');
      
      // Click add video button
      await page.click('[data-testid="add-video-btn"]');
      
      // Select video from available videos
      await page.click('[data-testid="video-selection-dialog"]');
      await page.check('[data-testid="video-checkbox"]:has-text("e2e-test-video.mp4")');
      await page.click('[data-testid="link-videos-btn"]');
      
      // Verify video is linked
      await expect(page.locator('[data-testid="project-video"]')).toContainText('e2e-test-video.mp4');
    });

    // Step 4: Process ground truth data
    await test.step('Process ground truth data', async () => {
      // Click on video to view details
      await page.click('[data-testid="project-video"]:has-text("e2e-test-video.mp4")');
      
      // Trigger ground truth processing
      await page.click('[data-testid="process-ground-truth-btn"]');
      
      // Wait for processing to start
      await expect(page.locator('[data-testid="processing-indicator"]')).toBeVisible();
      
      // Wait for processing to complete (may take time in real scenario)
      await expect(page.locator('[data-testid="processing-complete"]')).toBeVisible({ timeout: 60000 });
      
      // Verify ground truth data is available
      await expect(page.locator('[data-testid="ground-truth-objects"]')).toBeVisible();
    });

    // Step 5: View and edit annotations
    await test.step('View and create annotations', async () => {
      // Navigate to annotation interface
      await page.click('[data-testid="annotate-video-btn"]');
      await page.waitForSelector('[data-testid="video-annotation-player"]');
      
      // Wait for video to load
      await expect(page.locator('video')).toBeVisible();
      
      // Enable annotation mode
      await page.click('[data-testid="annotation-mode-toggle"]');
      
      // Create new annotation by clicking on video
      await page.click('[data-testid="annotation-canvas"]', { position: { x: 200, y: 150 } });
      
      // Fill annotation details
      await page.selectOption('[data-testid="vru-type-select"]', 'pedestrian');
      await page.fill('[data-testid="annotation-notes"]', 'E2E test annotation');
      await page.click('[data-testid="save-annotation-btn"]');
      
      // Verify annotation is created
      await expect(page.locator('[data-testid="annotation-item"]')).toContainText('pedestrian');
    });

    // Step 6: Validate annotations
    await test.step('Validate annotations', async () => {
      // Click on annotation to select
      await page.click('[data-testid="annotation-item"]:first-child');
      
      // Validate the annotation
      await page.click('[data-testid="validate-annotation-btn"]');
      
      // Verify validation status
      await expect(page.locator('[data-testid="validation-status"]')).toContainText('Validated');
      await expect(page.locator('[data-testid="annotation-item"]')).toHaveClass(/validated/);
    });

    // Step 7: Create test session and run test
    await test.step('Run test execution', async () => {
      // Navigate to test execution
      await page.click('[data-testid="nav-test-execution"]');
      
      // Create new test session
      await page.click('[data-testid="new-test-session-btn"]');
      
      // Select project and video
      await page.selectOption('[data-testid="project-select"]', 'E2E Test Project');
      await page.selectOption('[data-testid="video-select"]', 'e2e-test-video.mp4');
      
      // Start test session
      await page.click('[data-testid="start-test-btn"]');
      
      // Wait for test to start
      await expect(page.locator('[data-testid="test-status"]')).toContainText('Running');
      
      // Wait for some test results
      await expect(page.locator('[data-testid="detection-events"]')).toBeVisible({ timeout: 30000 });
      
      // Stop the test
      await page.click('[data-testid="stop-test-btn"]');
      
      // Verify test completed
      await expect(page.locator('[data-testid="test-status"]')).toContainText('Completed');
    });

    // Step 8: View results and metrics
    await test.step('View test results', async () => {
      // Navigate to results page
      await page.click('[data-testid="nav-results"]');
      
      // Verify test results are displayed
      await expect(page.locator('[data-testid="test-results"]')).toBeVisible();
      await expect(page.locator('[data-testid="precision-metric"]')).toBeVisible();
      await expect(page.locator('[data-testid="recall-metric"]')).toBeVisible();
      
      // Check specific metrics have values
      const precision = await page.locator('[data-testid="precision-value"]').textContent();
      const recall = await page.locator('[data-testid="recall-value"]').textContent();
      
      expect(precision).toMatch(/\d+\.\d+%/);
      expect(recall).toMatch(/\d+\.\d+%/);
    });
  });

  test('Error recovery during workflow interruption', async ({ page }) => {
    // Test workflow resilience to interruptions
    
    await test.step('Start video upload', async () => {
      await page.click('[data-testid="nav-ground-truth"]');
      
      const videoBuffer = Buffer.from('large video content for interruption testing'.repeat(1000));
      
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'interruption-test-video.mp4',
        mimeType: 'video/mp4',
        buffer: videoBuffer
      });
      
      // Wait for upload to start
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
    });

    await test.step('Simulate network interruption', async () => {
      // Simulate network failure during upload
      await page.route('**/api/videos', route => {
        route.abort('internetdisconnected');
      });
      
      // Wait for error to be displayed
      await expect(page.locator('[data-testid="upload-error"]')).toBeVisible({ timeout: 10000 });
    });

    await test.step('Recover from interruption', async () => {
      // Re-enable network
      await page.unroute('**/api/videos');
      
      // Retry upload
      await page.click('[data-testid="retry-upload-btn"]');
      
      // Verify upload completes after retry
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });
    });
  });

  test('Large file upload workflow', async ({ page }) => {
    await test.step('Upload large video file', async () => {
      await page.click('[data-testid="nav-ground-truth"]');
      
      // Create a larger mock file
      const largeVideoBuffer = Buffer.alloc(50 * 1024 * 1024); // 50MB
      largeVideoBuffer.fill('large video data');
      
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'large-test-video.mp4',
        mimeType: 'video/mp4',
        buffer: largeVideoBuffer
      });
      
      // Monitor upload progress
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
      
      // Verify progress updates
      const progressBar = page.locator('[data-testid="progress-bar"]');
      await expect(progressBar).toHaveAttribute('aria-valuenow', /[1-9]/);
      
      // Wait for upload completion (longer timeout for large file)
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 120000 });
      
      // Verify file is listed
      await expect(page.locator('[data-testid="video-item"]')).toContainText('large-test-video.mp4');
    });

    await test.step('Process large video ground truth', async () => {
      // Click on the large video
      await page.click('[data-testid="video-item"]:has-text("large-test-video.mp4")');
      
      // Start ground truth processing
      await page.click('[data-testid="process-ground-truth-btn"]');
      
      // Verify processing starts
      await expect(page.locator('[data-testid="processing-indicator"]')).toBeVisible();
      
      // For large files, processing might take longer
      await expect(page.locator('[data-testid="processing-progress"]')).toBeVisible();
      
      // Wait for completion with extended timeout
      await expect(page.locator('[data-testid="processing-complete"]')).toBeVisible({ timeout: 180000 });
    });
  });

  test('Multi-user annotation collaboration workflow', async ({ page, browser }) => {
    // This test simulates multiple users working on annotations
    
    const secondContext = await browser.newContext();
    const secondPage = await secondContext.newPage();
    
    await test.step('User 1: Create project and upload video', async () => {
      // First user creates project
      await page.click('[data-testid="nav-projects"]');
      await page.click('[data-testid="create-project-btn"]');
      
      await page.fill('[data-testid="project-name"]', 'Collaboration Test Project');
      await page.fill('[data-testid="project-description"]', 'Multi-user annotation testing');
      await page.selectOption('[data-testid="camera-model"]', 'TestCam v1.0');
      await page.selectOption('[data-testid="camera-view"]', 'Front-facing VRU');
      await page.selectOption('[data-testid="signal-type"]', 'GPIO');
      
      await page.click('[data-testid="submit-project"]');
      await expect(page.locator('[data-testid="success-notification"]')).toBeVisible();
    });

    await test.step('User 1: Upload and link video', async () => {
      // Upload video
      await page.click('[data-testid="nav-ground-truth"]');
      
      const videoBuffer = Buffer.from('collaboration test video content');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'collaboration-video.mp4',
        mimeType: 'video/mp4',
        buffer: videoBuffer
      });
      
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });
      
      // Link to project
      await page.click('[data-testid="nav-projects"]');
      await page.click('[data-testid="project-card"]:has-text("Collaboration Test Project")');
      await page.click('[data-testid="add-video-btn"]');
      await page.check('[data-testid="video-checkbox"]:has-text("collaboration-video.mp4")');
      await page.click('[data-testid="link-videos-btn"]');
    });

    await test.step('User 1: Create initial annotations', async () => {
      await page.click('[data-testid="project-video"]:has-text("collaboration-video.mp4")');
      await page.click('[data-testid="annotate-video-btn"]');
      
      await page.click('[data-testid="annotation-mode-toggle"]');
      await page.click('[data-testid="annotation-canvas"]', { position: { x: 100, y: 100 } });
      
      await page.selectOption('[data-testid="vru-type-select"]', 'pedestrian');
      await page.fill('[data-testid="annotation-notes"]', 'User 1 annotation');
      await page.click('[data-testid="save-annotation-btn"]');
      
      await expect(page.locator('[data-testid="annotation-item"]')).toContainText('pedestrian');
    });

    await test.step('User 2: Access same project', async () => {
      // Second user navigates to the same project
      await secondPage.goto('/');
      await secondPage.waitForSelector('[data-testid="app-header"]');
      
      await secondPage.click('[data-testid="nav-projects"]');
      await secondPage.click('[data-testid="project-card"]:has-text("Collaboration Test Project")');
      
      // Verify they can see the video
      await expect(secondPage.locator('[data-testid="project-video"]')).toContainText('collaboration-video.mp4');
    });

    await test.step('User 2: Add additional annotations', async () => {
      await secondPage.click('[data-testid="project-video"]:has-text("collaboration-video.mp4")');
      await secondPage.click('[data-testid="annotate-video-btn"]');
      
      // Should see existing annotation from User 1
      await expect(secondPage.locator('[data-testid="annotation-item"]')).toContainText('User 1 annotation');
      
      // Add new annotation
      await secondPage.click('[data-testid="annotation-mode-toggle"]');
      await secondPage.click('[data-testid="annotation-canvas"]', { position: { x: 200, y: 150 } });
      
      await secondPage.selectOption('[data-testid="vru-type-select"]', 'cyclist');
      await secondPage.fill('[data-testid="annotation-notes"]', 'User 2 annotation');
      await secondPage.click('[data-testid="save-annotation-btn"]');
    });

    await test.step('Verify collaboration', async () => {
      // User 1 refreshes and sees User 2's annotation
      await page.reload();
      await page.waitForSelector('[data-testid="annotation-item"]');
      
      const annotations = page.locator('[data-testid="annotation-item"]');
      await expect(annotations).toHaveCount(2);
      
      // Verify both annotations are present
      await expect(page.locator('[data-testid="annotation-item"]')).toContainText('User 1 annotation');
      await expect(page.locator('[data-testid="annotation-item"]')).toContainText('User 2 annotation');
    });

    await secondContext.close();
  });

  test('Performance monitoring during workflow', async ({ page }) => {
    // Monitor performance metrics during the complete workflow
    
    await test.step('Monitor page load performance', async () => {
      const startTime = Date.now();
      
      await page.goto('/');
      await page.waitForSelector('[data-testid="app-header"]');
      
      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(5000); // Should load within 5 seconds
    });

    await test.step('Monitor video upload performance', async () => {
      await page.click('[data-testid="nav-ground-truth"]');
      
      const uploadStartTime = Date.now();
      const videoBuffer = Buffer.from('performance test video content');
      
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'performance-test-video.mp4',
        mimeType: 'video/mp4',
        buffer: videoBuffer
      });
      
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });
      
      const uploadTime = Date.now() - uploadStartTime;
      expect(uploadTime).toBeLessThan(15000); // Upload should complete within 15 seconds for small file
    });

    await test.step('Monitor annotation interface performance', async () => {
      await page.click('[data-testid="video-item"]:has-text("performance-test-video.mp4")');
      
      const annotationStartTime = Date.now();
      await page.click('[data-testid="annotate-video-btn"]');
      
      await page.waitForSelector('[data-testid="video-annotation-player"]');
      await expect(page.locator('video')).toBeVisible();
      
      const annotationLoadTime = Date.now() - annotationStartTime;
      expect(annotationLoadTime).toBeLessThan(3000); // Annotation interface should load within 3 seconds
      
      // Test video player responsiveness
      const seekStartTime = Date.now();
      await page.click('[data-testid="video-timeline"]', { position: { x: 200, y: 10 } });
      
      // Wait for video to respond to seek
      await page.waitForTimeout(500);
      const seekTime = Date.now() - seekStartTime;
      expect(seekTime).toBeLessThan(1000); // Seek should be responsive within 1 second
    });
  });

  test('Accessibility compliance during workflow', async ({ page }) => {
    // Test accessibility throughout the workflow
    
    await test.step('Check homepage accessibility', async () => {
      await page.goto('/');
      
      // Verify proper heading structure
      const h1 = page.locator('h1');
      await expect(h1).toBeVisible();
      
      // Verify navigation is keyboard accessible
      await page.keyboard.press('Tab');
      const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
      expect(['A', 'BUTTON', 'INPUT']).toContain(focusedElement);
    });

    await test.step('Check form accessibility', async () => {
      await page.click('[data-testid="nav-projects"]');
      await page.click('[data-testid="create-project-btn"]');
      
      // Verify form labels
      const nameLabel = page.locator('label[for="project-name"]');
      await expect(nameLabel).toBeVisible();
      
      // Verify form is keyboard navigable
      await page.keyboard.press('Tab');
      await page.keyboard.type('Accessibility Test Project');
      
      const nameInput = page.locator('[data-testid="project-name"]');
      const nameValue = await nameInput.inputValue();
      expect(nameValue).toBe('Accessibility Test Project');
    });

    await test.step('Check video player accessibility', async () => {
      // First upload a video
      await page.click('[data-testid="nav-ground-truth"]');
      
      const videoBuffer = Buffer.from('accessibility test video');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'accessibility-test.mp4',
        mimeType: 'video/mp4',
        buffer: videoBuffer
      });
      
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();
      
      await page.click('[data-testid="video-item"]');
      await page.click('[data-testid="annotate-video-btn"]');
      
      // Verify video has proper ARIA labels
      const video = page.locator('video');
      await expect(video).toHaveAttribute('aria-label');
      
      // Verify controls are keyboard accessible
      const playButton = page.locator('[data-testid="play-pause-btn"]');
      await expect(playButton).toHaveAttribute('aria-label');
      
      await playButton.focus();
      await page.keyboard.press('Space');
      // Should toggle play/pause
    });
  });

  test('Data persistence across browser sessions', async ({ page, browser }) => {
    let projectId: string;
    let videoId: string;
    
    await test.step('Create data in first session', async () => {
      // Create project
      await page.click('[data-testid="nav-projects"]');
      await page.click('[data-testid="create-project-btn"]');
      
      await page.fill('[data-testid="project-name"]', 'Persistence Test Project');
      await page.fill('[data-testid="project-description"]', 'Testing data persistence');
      await page.selectOption('[data-testid="camera-model"]', 'TestCam v1.0');
      await page.selectOption('[data-testid="camera-view"]', 'Front-facing VRU');
      await page.selectOption('[data-testid="signal-type"]', 'GPIO');
      
      await page.click('[data-testid="submit-project"]');
      await expect(page.locator('[data-testid="success-notification"]')).toBeVisible();
      
      // Extract project ID from URL or data attribute
      const projectCard = page.locator('[data-testid="project-card"]:has-text("Persistence Test Project")');
      projectId = await projectCard.getAttribute('data-project-id') || 'unknown';
      
      // Upload video
      await page.click('[data-testid="nav-ground-truth"]');
      
      const videoBuffer = Buffer.from('persistence test video');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'persistence-test.mp4',
        mimeType: 'video/mp4',
        buffer: videoBuffer
      });
      
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();
    });

    await test.step('Verify data persists in new session', async () => {
      // Close current browser and open new one
      const newContext = await browser.newContext();
      const newPage = await newContext.newPage();
      
      await newPage.goto('/');
      await newPage.waitForSelector('[data-testid="app-header"]');
      
      // Verify project exists
      await newPage.click('[data-testid="nav-projects"]');
      await expect(newPage.locator('[data-testid="project-card"]')).toContainText('Persistence Test Project');
      
      // Verify video exists
      await newPage.click('[data-testid="nav-ground-truth"]');
      await expect(newPage.locator('[data-testid="video-item"]')).toContainText('persistence-test.mp4');
      
      await newContext.close();
    });
  });
});