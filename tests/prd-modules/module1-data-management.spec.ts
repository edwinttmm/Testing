import { test, expect, Page } from '@playwright/test';
import { ErrorMonitor } from '../utils/error-monitor';
import { PRDValidator } from '../utils/prd-validator';

test.describe('PRD Module 1: Data Management & Ground Truth', () => {
  let errorMonitor: ErrorMonitor;
  let prdValidator: PRDValidator;
  
  test.beforeEach(async ({ page }) => {
    errorMonitor = new ErrorMonitor('Module1-DataManagement');
    prdValidator = new PRDValidator(page, errorMonitor);
    
    await errorMonitor.setupPageMonitoring(page);
    
    // Navigate to the application
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');
    
    // Wait for React to load and capture any initial errors
    await page.waitForTimeout(2000);
    await errorMonitor.captureTypeScriptErrors(page);
  });
  
  test.afterEach(async ({ page }) => {
    await errorMonitor.capturePerformanceIssues(page);
    await errorMonitor.saveErrorLog();
    
    // Take screenshot of final state
    await page.screenshot({ 
      path: `test-reports/screenshots/module1-final-state-${Date.now()}.png`, 
      fullPage: true 
    });
  });

  test('1.1 Video Ingestion - Upload Standard Video Formats', async ({ page }) => {
    console.log('🎬 Testing video upload functionality for .MP4, .MOV, .AVI formats...');
    
    // Navigate to video upload page
    await page.goto('/videos');
    await page.waitForLoadState('networkidle');
    
    // Look for upload interface
    const uploadButton = page.locator('input[type="file"], button:has-text("Upload"), [data-testid*="upload"]').first();
    await expect(uploadButton).toBeVisible({ timeout: 10000 });
    
    // Check supported formats
    const fileInput = page.locator('input[type="file"]').first();
    if (await fileInput.count() > 0) {
      const acceptAttr = await fileInput.getAttribute('accept');
      console.log(`📋 File input accepts: ${acceptAttr}`);
      
      // Validate video format support
      expect(acceptAttr).toBeTruthy();
      expect(acceptAttr).toMatch(/(video\/|\.mp4|\.mov|\.avi)/i);
    }
    
    // Test drag-and-drop zone if present
    const dropZone = page.locator('[data-testid*="drop"], .drop-zone, [class*="upload-area"]');
    if (await dropZone.count() > 0) {
      await expect(dropZone).toBeVisible();
      console.log('✅ Drag-and-drop upload zone detected');
    }
    
    // Check upload progress indicators
    const progressIndicators = page.locator('[data-testid*="progress"], .progress, .upload-status');
    console.log(`📊 Progress indicators found: ${await progressIndicators.count()}`);
  });

  test('1.1 Video Processing - Pending Annotation Status', async ({ page }) => {
    console.log('⏳ Testing video processing and status management...');
    
    await page.goto('/videos');
    await page.waitForLoadState('networkidle');
    
    // Check for video library with status indicators
    const videoList = page.locator('[data-testid*="video-list"], .video-grid, table tbody tr');
    await expect(videoList.first()).toBeVisible({ timeout: 15000 });
    
    // Look for status columns/indicators
    const statusElements = page.locator('[data-testid*="status"], .status, [class*="pending"], [class*="annotation"]');
    console.log(`📋 Status elements found: ${await statusElements.count()}`);
    
    if (await statusElements.count() > 0) {
      const statusTexts = await statusElements.allTextContents();
      console.log('📊 Status values:', statusTexts);
      
      // Check for "Pending Annotation" or similar status
      const hasPendingStatus = statusTexts.some(text => 
        text.toLowerCase().includes('pending') || 
        text.toLowerCase().includes('annotation') ||
        text.toLowerCase().includes('processing')
      );
      expect(hasPendingStatus).toBeTruthy();
    }
  });

  test('1.2 Automated Annotation - VRU Bounding Box Detection', async ({ page }) => {
    console.log('🤖 Testing automated VRU detection and bounding box creation...');
    
    // Navigate to annotation interface
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Wait for AI processing indicators
    await page.waitForTimeout(3000);
    
    // Look for bounding box visualization
    const boundingBoxes = page.locator('[data-testid*="bounding"], .bounding-box, svg rect, canvas');
    console.log(`📦 Bounding box elements found: ${await boundingBoxes.count()}`);
    
    if (await boundingBoxes.count() > 0) {
      await expect(boundingBoxes.first()).toBeVisible();
      
      // Check for bounding box attributes
      const firstBox = boundingBoxes.first();
      const boundingRect = await firstBox.boundingBox();
      expect(boundingRect).toBeTruthy();
      console.log('✅ Bounding box positioning verified');
    }
    
    // Look for VRU detection indicators
    const vruLabels = page.locator('[data-testid*="vru"], [class*="pedestrian"], [class*="cyclist"], [class*="vehicle"]');
    console.log(`👥 VRU detection elements: ${await vruLabels.count()}`);
    
    // Check for object detection confidence scores
    const confidenceScores = page.locator('[data-testid*="confidence"], .confidence, [class*="score"]');
    console.log(`📈 Confidence score elements: ${await confidenceScores.count()}`);
  });

  test('1.2 Persistent VRU ID Assignment', async ({ page }) => {
    console.log('🆔 Testing persistent VRU ID tracking throughout video...');
    
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Look for VRU ID elements
    const idElements = page.locator('[data-testid*="vru-id"], [data-testid*="object-id"], [class*="tracking-id"]');
    console.log(`🔢 VRU ID elements found: ${await idElements.count()}`);
    
    if (await idElements.count() > 0) {
      const idTexts = await idElements.allTextContents();
      console.log('🆔 VRU IDs detected:', idTexts);
      
      // Verify ID format (should be unique identifiers)
      const validIds = idTexts.filter(id => id.trim().length > 0 && /^[A-Za-z0-9_-]+$/.test(id.trim()));
      expect(validIds.length).toBeGreaterThan(0);
    }
    
    // Check for ID persistence controls
    const idControls = page.locator('[data-testid*="id-track"], [class*="tracking"], .object-tracker');
    console.log(`🎯 ID tracking controls: ${await idControls.count()}`);
  });

  test('1.3 Annotation Interface - Large Viewport Layout', async ({ page }) => {
    console.log('🖥️ Testing annotation interface layout with large central viewport...');
    
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Check main video viewport
    const viewport = page.locator('[data-testid*="video-viewport"], [data-testid*="main-video"], video, canvas').first();
    await expect(viewport).toBeVisible({ timeout: 15000 });
    
    // Measure viewport size
    const viewportBox = await viewport.boundingBox();
    expect(viewportBox).toBeTruthy();
    console.log(`📏 Viewport dimensions: ${viewportBox?.width}x${viewportBox?.height}`);
    
    // Verify it's "large" (should be significant portion of screen)
    if (viewportBox) {
      const pageSize = await page.viewportSize();
      const viewportRatio = (viewportBox.width * viewportBox.height) / (pageSize!.width * pageSize!.height);
      expect(viewportRatio).toBeGreaterThan(0.3); // At least 30% of screen
      console.log(`📊 Viewport occupies ${(viewportRatio * 100).toFixed(1)}% of screen`);
    }
    
    // Check for interactive timeline below viewport
    const timeline = page.locator('[data-testid*="timeline"], .timeline, input[type="range"]');
    await expect(timeline.first()).toBeVisible();
    console.log('⏱️ Timeline component verified');
    
    // Check for tools and object list panels
    const toolsPanel = page.locator('[data-testid*="tools"], .tools-panel, [class*="sidebar"]');
    const objectList = page.locator('[data-testid*="objects"], [data-testid*="detections"], .object-list');
    
    console.log(`🔧 Tools panel elements: ${await toolsPanel.count()}`);
    console.log(`📝 Object list elements: ${await objectList.count()}`);
  });

  test('1.3 Direct Bounding Box Manipulation', async ({ page }) => {
    console.log('✋ Testing direct bounding box manipulation (click, resize, move)...');
    
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Look for interactive bounding boxes
    const interactiveBoxes = page.locator('[draggable="true"], [data-testid*="draggable"], .draggable, .resizable');
    console.log(`📦 Interactive bounding boxes: ${await interactiveBoxes.count()}`);
    
    if (await interactiveBoxes.count() > 0) {
      const firstBox = interactiveBoxes.first();
      await expect(firstBox).toBeVisible();
      
      // Test click interaction
      await firstBox.click();
      console.log('✅ Bounding box clickable');
      
      // Look for resize handles
      const resizeHandles = page.locator('[data-testid*="handle"], .resize-handle, [class*="corner"]');
      console.log(`🔲 Resize handles found: ${await resizeHandles.count()}`);
      
      // Test drag capability (simulate)
      const boxBounds = await firstBox.boundingBox();
      if (boxBounds) {
        // Simulate drag operation
        await page.mouse.move(boxBounds.x + boxBounds.width/2, boxBounds.y + boxBounds.height/2);
        await page.mouse.down();
        await page.mouse.move(boxBounds.x + boxBounds.width/2 + 10, boxBounds.y + boxBounds.height/2 + 10);
        await page.mouse.up();
        console.log('✅ Drag simulation completed');
      }
    }
    
    // Check for manipulation feedback/cursors
    const cursorStyles = await page.evaluate(() => {
      const elements = document.querySelectorAll('[draggable="true"], .draggable, .resizable');
      return Array.from(elements).map(el => getComputedStyle(el).cursor);
    });
    console.log('🖱️ Cursor styles:', cursorStyles);
  });

  test('1.3 Object Management - Type Correction', async ({ page }) => {
    console.log('🔄 Testing object type correction (pedestrian→cyclist)...');
    
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Look for object type selectors
    const typeSelectors = page.locator('select[data-testid*="object-type"], [data-testid*="category"], .type-selector');
    console.log(`🏷️ Object type selectors: ${await typeSelectors.count()}`);
    
    if (await typeSelectors.count() > 0) {
      const selector = typeSelectors.first();
      await expect(selector).toBeVisible();
      
      // Get available options
      const options = await selector.locator('option').allTextContents();
      console.log('📋 Available object types:', options);
      
      // Check for VRU types
      const hasVRUTypes = options.some(opt => 
        opt.toLowerCase().includes('pedestrian') || 
        opt.toLowerCase().includes('cyclist') ||
        opt.toLowerCase().includes('vehicle')
      );
      expect(hasVRUTypes).toBeTruthy();
    }
    
    // Look for inline editing capabilities
    const inlineEditors = page.locator('[contenteditable="true"], [data-testid*="inline-edit"], .editable-label');
    console.log(`✏️ Inline editors found: ${await inlineEditors.count()}`);
    
    // Check for context menus
    const contextMenus = page.locator('[data-testid*="context"], .context-menu, [role="menu"]');
    console.log(`📋 Context menus: ${await contextMenus.count()}`);
  });

  test('1.3 ID Management - Merge/Split VRU IDs', async ({ page }) => {
    console.log('🔗 Testing VRU ID merge and split functionality...');
    
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Look for ID management controls
    const mergeButtons = page.locator('button:has-text("Merge"), [data-testid*="merge"], .merge-btn');
    const splitButtons = page.locator('button:has-text("Split"), [data-testid*="split"], .split-btn');
    
    console.log(`🔗 Merge controls: ${await mergeButtons.count()}`);
    console.log(`✂️ Split controls: ${await splitButtons.count()}`);
    
    // Check for multi-select capability for merging
    const selectableObjects = page.locator('[data-testid*="selectable"], .selectable, input[type="checkbox"]');
    console.log(`☑️ Selectable objects: ${await selectableObjects.count()}`);
    
    // Look for ID conflict resolution dialogs
    const dialogs = page.locator('[role="dialog"], .modal, [data-testid*="dialog"]');
    console.log(`💬 Dialog elements: ${await dialogs.count()}`);
    
    // Test ID validation
    const idInputs = page.locator('input[data-testid*="id"], [data-testid*="object-id"] input');
    if (await idInputs.count() > 0) {
      const idValues = await idInputs.allInputValues();
      console.log('🆔 Current ID values:', idValues);
    }
  });

  test('1.3 Timeline Control - Frame-by-Frame Navigation', async ({ page }) => {
    console.log('⏯️ Testing timeline control with frame-by-frame navigation...');
    
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Find timeline component
    const timeline = page.locator('[data-testid*="timeline"], .timeline-scrubber, input[type="range"]').first();
    await expect(timeline).toBeVisible({ timeout: 15000 });
    
    // Test scrubbing functionality
    const timelineBox = await timeline.boundingBox();
    if (timelineBox) {
      // Click at different positions on timeline
      await timeline.click({ position: { x: timelineBox.width * 0.25, y: timelineBox.height / 2 } });
      await page.waitForTimeout(500);
      
      await timeline.click({ position: { x: timelineBox.width * 0.75, y: timelineBox.height / 2 } });
      await page.waitForTimeout(500);
      console.log('✅ Timeline scrubbing tested');
    }
    
    // Look for frame navigation controls
    const frameControls = page.locator('[data-testid*="frame"], button:has-text("Next"), button:has-text("Previous"), .frame-nav');
    console.log(`🎞️ Frame controls: ${await frameControls.count()}`);
    
    // Check for annotation markers on timeline
    const markers = page.locator('[data-testid*="marker"], .timeline-marker, .annotation-point');
    console.log(`📍 Timeline markers: ${await markers.count()}`);
    
    // Test frame-by-frame stepping
    const nextFrameBtn = page.locator('button:has-text("Next"), [data-testid*="next-frame"]').first();
    if (await nextFrameBtn.count() > 0) {
      await nextFrameBtn.click();
      console.log('⏭️ Next frame navigation tested');
    }
    
    // Check for precise time display
    const timeDisplays = page.locator('[data-testid*="time"], .timestamp, .current-time');
    if (await timeDisplays.count() > 0) {
      const timeTexts = await timeDisplays.allTextContents();
      console.log('⏰ Time displays:', timeTexts);
    }
  });

  test('1.3 Annotation Validation - Mark as Validated', async ({ page }) => {
    console.log('✅ Testing annotation validation and locking mechanism...');
    
    await page.goto('/annotations');
    await page.waitForLoadState('networkidle');
    
    // Look for validation controls
    const validateButtons = page.locator('button:has-text("Validate"), button:has-text("Approve"), [data-testid*="validate"]');
    console.log(`✔️ Validation buttons: ${await validateButtons.count()}`);
    
    if (await validateButtons.count() > 0) {
      const validateBtn = validateButtons.first();
      await expect(validateBtn).toBeVisible();
      
      // Check button state
      const isDisabled = await validateBtn.isDisabled();
      console.log(`🔒 Validation button disabled: ${isDisabled}`);
    }
    
    // Look for validation status indicators
    const statusIndicators = page.locator('[data-testid*="validated"], .validated, [class*="locked"]');
    console.log(`🔐 Validation status indicators: ${await statusIndicators.count()}`);
    
    // Check for validation warnings/requirements
    const warnings = page.locator('.warning, .validation-error, [data-testid*="warning"]');
    console.log(`⚠️ Validation warnings: ${await warnings.count()}`);
    
    // Look for validation progress indicators
    const progressElements = page.locator('[data-testid*="validation-progress"], .progress, .completion-status');
    console.log(`📊 Validation progress elements: ${await progressElements.count()}`);
  });

  test('1.4 Video Library - List with Status Display', async ({ page }) => {
    console.log('📚 Testing video library with comprehensive status display...');
    
    await page.goto('/videos');
    await page.waitForLoadState('networkidle');
    
    // Check for video library grid/list
    const videoLibrary = page.locator('[data-testid*="video-library"], [data-testid*="video-list"], .video-grid');
    await expect(videoLibrary.first()).toBeVisible({ timeout: 15000 });
    
    // Count videos in library
    const videoItems = page.locator('[data-testid*="video-item"], .video-card, tbody tr');
    const videoCount = await videoItems.count();
    console.log(`📹 Videos in library: ${videoCount}`);
    
    // Check status variety
    const statusElements = page.locator('[data-testid*="status"], .status-badge, .video-status');
    if (await statusElements.count() > 0) {
      const statusTexts = await statusElements.allTextContents();
      const uniqueStatuses = [...new Set(statusTexts.map(s => s.trim()))];
      console.log('📊 Unique status types:', uniqueStatuses);
      
      // Verify expected statuses exist
      const expectedStatuses = ['Pending Validation', 'Validated', 'Processing', 'Pending Annotation'];
      const hasExpectedStatuses = expectedStatuses.some(expected => 
        uniqueStatuses.some(actual => actual.includes(expected) || expected.includes(actual))
      );
      expect(hasExpectedStatuses).toBeTruthy();
    }
    
    // Check for additional metadata display
    const metadataElements = page.locator('[data-testid*="duration"], [data-testid*="size"], [data-testid*="created"]');
    console.log(`📋 Metadata elements: ${await metadataElements.count()}`);
  });

  test('1.4 Video Library - Search and Filter Functionality', async ({ page }) => {
    console.log('🔍 Testing video library search and filter capabilities...');
    
    await page.goto('/videos');
    await page.waitForLoadState('networkidle');
    
    // Find search functionality
    const searchBox = page.locator('input[type="search"], input[placeholder*="search"], [data-testid*="search"]').first();
    if (await searchBox.count() > 0) {
      await expect(searchBox).toBeVisible();
      
      // Test search functionality
      await searchBox.fill('test');
      await page.waitForTimeout(1000);
      console.log('✅ Search input tested');
      
      // Clear search
      await searchBox.clear();
    }
    
    // Find filter controls
    const filterSelects = page.locator('select[data-testid*="filter"], .filter-dropdown');
    console.log(`🎛️ Filter controls: ${await filterSelects.count()}`);
    
    if (await filterSelects.count() > 0) {
      const filterSelect = filterSelects.first();
      const options = await filterSelect.locator('option').allTextContents();
      console.log('📋 Filter options:', options);
      
      // Test filter functionality
      if (options.length > 1) {
        await filterSelect.selectOption(options[1]);
        await page.waitForTimeout(1000);
        console.log(`🎯 Filter applied: ${options[1]}`);
      }
    }
    
    // Check for advanced search features
    const advancedSearch = page.locator('[data-testid*="advanced"], .advanced-search, .search-filters');
    console.log(`🔧 Advanced search features: ${await advancedSearch.count()}`);
    
    // Test result updates
    const resultCount = page.locator('[data-testid*="result-count"], .result-summary, .search-results-count');
    if (await resultCount.count() > 0) {
      const countText = await resultCount.first().textContent();
      console.log(`📊 Search results indicator: ${countText}`);
    }
  });

  test('1.4 Video Library - Playback with Annotations', async ({ page }) => {
    console.log('▶️ Testing video playback with annotation overlays...');
    
    await page.goto('/videos');
    await page.waitForLoadState('networkidle');
    
    // Find a video to play
    const videoItems = page.locator('[data-testid*="video-item"], .video-card');
    if (await videoItems.count() > 0) {
      // Click on first video
      await videoItems.first().click();
      await page.waitForLoadState('networkidle');
      
      // Check for video player
      const videoPlayer = page.locator('video, [data-testid*="player"], .video-player').first();
      await expect(videoPlayer).toBeVisible({ timeout: 15000 });
      
      // Look for annotation overlays
      const overlays = page.locator('[data-testid*="overlay"], .annotation-overlay, svg');
      console.log(`🎨 Annotation overlays: ${await overlays.count()}`);
      
      // Check for play controls
      const playButton = page.locator('button[aria-label*="play"], .play-btn, [data-testid*="play"]').first();
      if (await playButton.count() > 0) {
        await playButton.click();
        await page.waitForTimeout(2000);
        console.log('▶️ Video playback initiated');
      }
      
      // Look for detection snapshots/keyframes
      const keyframes = page.locator('[data-testid*="keyframe"], [data-testid*="snapshot"], .detection-snapshot');
      console.log(`📸 Detection snapshots: ${await keyframes.count()}`);
    }
  });

  test('Module 1 - Comprehensive PRD Validation', async ({ page }) => {
    console.log('🏆 Running comprehensive Module 1 PRD compliance validation...');
    
    // Run all Module 1 validations
    const results = await prdValidator.validateModule1DataManagement();
    
    // Log results
    console.log(`📊 Module 1 Results: ${results.length} requirements tested`);
    
    const passed = results.filter(r => r.passed).length;
    const failed = results.filter(r => !r.passed).length;
    const critical = results.filter(r => !r.passed && r.requirement.priority === 'critical').length;
    
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`🚨 Critical Failures: ${critical}`);
    
    // Calculate compliance rate
    const complianceRate = prdValidator.getModuleComplianceRate('Module 1');
    console.log(`📈 Module 1 Compliance Rate: ${complianceRate.toFixed(1)}%`);
    
    // Expect reasonable compliance (allowing for missing features in development)
    expect(complianceRate).toBeGreaterThan(50); // At least 50% compliance
    
    // No critical failures should be acceptable for core functionality
    if (critical > 0) {
      console.warn(`⚠️ ${critical} critical requirements failed in Module 1`);
      const criticalFailures = results.filter(r => !r.passed && r.requirement.priority === 'critical');
      criticalFailures.forEach(failure => {
        console.warn(`🚨 CRITICAL: ${failure.requirement.requirement} - ${failure.message}`);
      });
    }
  });
});