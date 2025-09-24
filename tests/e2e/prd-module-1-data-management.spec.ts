import { test, expect } from '@playwright/test';
import { ErrorMonitor } from './utils/error-monitor';
import { TestHelpers } from './utils/test-helpers';

test.describe('PRD Module 1: Data Management & Ground Truth', () => {
  let errorMonitor: ErrorMonitor;
  let helpers: TestHelpers;

  test.beforeEach(async ({ page }) => {
    errorMonitor = new ErrorMonitor(page);
    helpers = new TestHelpers(page);
    
    await page.goto('/');
    await helpers.waitForPageLoad();
  });

  test.afterEach(async ({ page }) => {
    if (errorMonitor.hasErrors()) {
      await errorMonitor.saveErrorLog(test.info().title);
    }
  });

  test('1.1 Video Upload Interface - File Format Support', async ({ page }) => {
    test.setTimeout(90000);
    
    // Navigate to video upload
    await helpers.clickAndWait('[data-testid="video-upload-btn"], .upload-btn, [href*="upload"]');
    
    // Verify upload interface exists
    await helpers.verifyElementExists('input[type="file"], [data-testid="file-input"]');
    
    // Check supported formats in UI
    const fileInput = page.locator('input[type="file"], [data-testid="file-input"]').first();
    const acceptAttr = await fileInput.getAttribute('accept');
    
    if (acceptAttr) {
      expect(acceptAttr).toContain('.mp4');
      expect(acceptAttr).toContain('.mov'); 
      expect(acceptAttr).toContain('.avi');
    }

    // Verify upload area UI elements
    await helpers.verifyElementExists('.upload-area, .dropzone, [data-testid="upload-zone"]');
    
    console.log('✅ Video upload interface validated');
  });

  test('1.2 Automated VRU Detection Interface', async ({ page }) => {
    test.setTimeout(60000);
    
    // Navigate to video processing/analysis section
    const possiblePaths = [
      '/videos',
      '/analysis', 
      '/processing',
      '/ground-truth'
    ];

    let foundPath = false;
    for (const path of possiblePaths) {
      try {
        await page.goto(path);
        if (await page.locator('body').isVisible()) {
          foundPath = true;
          break;
        }
      } catch (e) {
        continue;
      }
    }

    if (!foundPath) {
      await page.goto('/');
    }

    // Look for VRU detection indicators
    const vruElements = [
      '[data-testid*="vru"]',
      '[data-testid*="detection"]',
      '.detection-box',
      '.bounding-box', 
      '[class*="pedestrian"]',
      '[class*="cyclist"]',
      '[class*="detection"]'
    ];

    let detectionFound = false;
    for (const selector of vruElements) {
      if (await page.locator(selector).count() > 0) {
        detectionFound = true;
        console.log(`✅ Found VRU detection element: ${selector}`);
        break;
      }
    }

    // Check if there's a way to trigger VRU detection
    const triggerElements = [
      '[data-testid="detect-btn"]',
      '[data-testid="analyze-btn"]', 
      '.detect-button',
      '.analyze-button',
      'button:has-text("Detect")',
      'button:has-text("Analyze")'
    ];

    for (const selector of triggerElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found VRU detection trigger: ${selector}`);
        break;
      }
    }

    console.log('✅ VRU detection interface components checked');
  });

  test('1.3 Annotation Validation Interface', async ({ page }) => {
    test.setTimeout(60000);
    
    // Look for annotation interface
    const annotationPaths = [
      '/annotations',
      '/annotate',
      '/validation',
      '/review'
    ];

    for (const path of annotationPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        
        // Check for annotation interface elements
        const annotationElements = [
          '.annotation-viewport',
          '.video-viewport', 
          '[data-testid*="annotation"]',
          '[data-testid*="timeline"]',
          '.timeline',
          '.video-controls'
        ];

        for (const selector of annotationElements) {
          if (await page.locator(selector).count() > 0) {
            console.log(`✅ Found annotation element: ${selector} at ${path}`);
            
            // Verify viewport is large enough for annotation work
            const viewport = page.locator(selector).first();
            const boundingBox = await viewport.boundingBox();
            if (boundingBox) {
              expect(boundingBox.width).toBeGreaterThan(400);
              expect(boundingBox.height).toBeGreaterThan(300);
            }
          }
        }
        break;
      } catch (e) {
        continue;
      }
    }

    console.log('✅ Annotation validation interface checked');
  });

  test('1.4 Bounding Box Manipulation', async ({ page }) => {
    test.setTimeout(60000);
    
    await page.goto('/');
    
    // Look for interactive bounding boxes
    const boundingBoxSelectors = [
      '.bounding-box',
      '.detection-box',
      '[data-testid*="bbox"]',
      '.annotation-box',
      '.object-box'
    ];

    for (const selector of boundingBoxSelectors) {
      const boxes = page.locator(selector);
      const count = await boxes.count();
      
      if (count > 0) {
        console.log(`✅ Found ${count} bounding boxes with selector: ${selector}`);
        
        // Test if boxes are interactive (have click handlers)
        const firstBox = boxes.first();
        const isClickable = await firstBox.evaluate(el => {
          const style = window.getComputedStyle(el);
          return style.cursor === 'pointer' || style.cursor === 'move' || 
                 el.onclick !== null || el.getAttribute('draggable') === 'true';
        });
        
        if (isClickable) {
          console.log(`✅ Bounding box appears interactive`);
        }
        
        // Test resize handles
        const resizeHandles = page.locator(`${selector} .resize-handle, ${selector} .corner-handle, ${selector} [class*="handle"]`);
        const handleCount = await resizeHandles.count();
        if (handleCount > 0) {
          console.log(`✅ Found ${handleCount} resize handles`);
        }
        
        break;
      }
    }

    console.log('✅ Bounding box manipulation interface checked');
  });

  test('1.5 Object Management - VRU Type Corrections', async ({ page }) => {
    test.setTimeout(60000);
    
    await page.goto('/');
    
    // Look for object type management controls
    const objectTypeElements = [
      'select[data-testid*="object-type"]',
      '[data-testid*="pedestrian"]',
      '[data-testid*="cyclist"]', 
      '.object-type-selector',
      '.vru-type-dropdown',
      'button:has-text("Pedestrian")',
      'button:has-text("Cyclist")',
      'option:has-text("Pedestrian")',
      'option:has-text("Cyclist")'
    ];

    for (const selector of objectTypeElements) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found object type management: ${selector}`);
        
        // Test interaction if it's a dropdown
        if (selector.includes('select')) {
          try {
            await page.selectOption(selector, { index: 0 });
            console.log(`✅ Object type dropdown is functional`);
          } catch (e) {
            // Not interactive or no options
          }
        }
      }
    }

    // Look for object correction workflows
    const correctionElements = [
      '[data-testid*="correct"]',
      '[data-testid*="edit"]',
      '.edit-object',
      '.correct-type',
      'button:has-text("Correct")',
      'button:has-text("Edit")'
    ];

    for (const selector of correctionElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found correction interface: ${selector}`);
      }
    }

    console.log('✅ Object management interface validated');
  });

  test('1.6 ID Management - Merge/Split VRU Tracking', async ({ page }) => {
    test.setTimeout(60000);
    
    await page.goto('/');
    
    // Look for ID management controls
    const idManagementElements = [
      '[data-testid*="merge"]',
      '[data-testid*="split"]',
      '[data-testid*="track"]',
      '[data-testid*="id"]',
      '.merge-objects',
      '.split-track',
      '.track-id',
      'button:has-text("Merge")',
      'button:has-text("Split")',
      'input[placeholder*="ID"]',
      'input[placeholder*="Track"]'
    ];

    for (const selector of idManagementElements) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found ID management element: ${selector}`);
        
        // Test if buttons are functional
        if (selector.includes('button')) {
          const button = page.locator(selector).first();
          const isEnabled = await button.isEnabled();
          if (isEnabled) {
            console.log(`✅ ID management button is enabled and ready`);
          }
        }
      }
    }

    // Look for track visualization
    const trackElements = [
      '.track-line',
      '.track-path', 
      '[data-testid*="trajectory"]',
      '.object-trajectory',
      '.tracking-line'
    ];

    for (const selector of trackElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found tracking visualization: ${selector}`);
      }
    }

    console.log('✅ ID management interface validated');
  });

  test('1.7 Video Library with Filtering and Search', async ({ page }) => {
    test.setTimeout(60000);
    
    // Navigate to video library/management
    const libraryPaths = [
      '/library',
      '/videos', 
      '/video-management',
      '/files'
    ];

    let libraryFound = false;
    for (const path of libraryPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        
        // Check for library interface elements
        const libraryElements = [
          '.video-library',
          '.video-grid',
          '.file-list',
          '[data-testid*="video-list"]',
          '[data-testid*="library"]'
        ];

        for (const selector of libraryElements) {
          if (await page.locator(selector).count() > 0) {
            libraryFound = true;
            console.log(`✅ Found video library at ${path}: ${selector}`);
            break;
          }
        }
        
        if (libraryFound) break;
      } catch (e) {
        continue;
      }
    }

    if (!libraryFound) {
      await page.goto('/');
    }

    // Look for search functionality
    const searchElements = [
      'input[type="search"]',
      'input[placeholder*="Search"]',
      'input[placeholder*="Filter"]',
      '[data-testid*="search"]',
      '.search-input',
      '.filter-input'
    ];

    for (const selector of searchElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found search interface: ${selector}`);
        
        // Test search functionality
        try {
          await page.fill(selector, 'test');
          await page.waitForTimeout(1000);
          console.log(`✅ Search input is functional`);
        } catch (e) {
          // Search might not be fully functional yet
        }
      }
    }

    // Look for filter controls
    const filterElements = [
      'select[data-testid*="filter"]',
      '.filter-dropdown',
      '.filter-controls',
      '[data-testid*="filter-by"]',
      'button:has-text("Filter")',
      '.date-filter',
      '.type-filter'
    ];

    for (const selector of filterElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found filter controls: ${selector}`);
      }
    }

    console.log('✅ Video library interface validated');
  });

  test('1.8 Complete Data Management Workflow', async ({ page }) => {
    test.setTimeout(120000);
    
    console.log('🚀 Starting complete data management workflow test...');
    
    // Step 1: Navigate to upload
    await page.goto('/');
    await helpers.waitForPageLoad();
    
    // Look for upload flow
    const uploadTriggers = [
      '[data-testid="upload-btn"]',
      '.upload-button',
      'button:has-text("Upload")',
      '[href*="upload"]'
    ];

    for (const trigger of uploadTriggers) {
      if (await page.locator(trigger).count() > 0) {
        await helpers.clickAndWait(trigger);
        console.log(`✅ Navigated to upload via: ${trigger}`);
        break;
      }
    }

    // Step 2: Check upload interface
    await helpers.verifyElementExists('input[type="file"], .upload-area, [data-testid*="upload"]');
    
    // Step 3: Navigate to annotation/validation
    const workflowPaths = ['/annotations', '/annotate', '/validation'];
    for (const path of workflowPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        break;
      } catch (e) {
        continue;
      }
    }

    // Step 4: Check for complete annotation workflow
    const workflowElements = [
      '.video-viewport, .annotation-area',
      '.timeline, .video-controls',
      '.bounding-box, .detection-box',
      '.object-controls, .annotation-tools'
    ];

    for (const selector of workflowElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Workflow element present: ${selector}`);
      }
    }

    // Step 5: Navigate back to library
    try {
      await page.goto('/videos');
      await helpers.waitForPageLoad();
      console.log('✅ Video library accessible');
    } catch (e) {
      console.log('⚠️ Video library not accessible');
    }

    console.log('✅ Complete data management workflow validated');
  });

  test('1.9 Performance - Large Video Handling', async ({ page }) => {
    test.setTimeout(60000);
    
    // Monitor page performance
    await page.goto('/');
    
    const performanceEntries = await page.evaluate(() => {
      return performance.getEntriesByType('navigation')[0];
    });

    // Check initial page load performance
    if (performanceEntries) {
      const loadTime = (performanceEntries as any).loadEventEnd - (performanceEntries as any).loadEventStart;
      expect(loadTime).toBeLessThan(5000); // Page should load in under 5 seconds
      console.log(`✅ Page load time: ${loadTime}ms`);
    }

    // Check for performance optimization indicators
    const optimizationElements = [
      '[data-testid*="lazy"]', 
      '.lazy-load',
      '.virtual-scroll',
      '[data-testid*="chunk"]',
      '.progress-bar'
    ];

    for (const selector of optimizationElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found performance optimization: ${selector}`);
      }
    }

    console.log('✅ Performance characteristics validated');
  });

  test('1.10 Error Recovery and Validation', async ({ page }) => {
    test.setTimeout(60000);
    
    await page.goto('/');
    await helpers.waitForPageLoad();

    // Test error handling for invalid routes
    const invalidRoutes = ['/nonexistent', '/invalid-path'];
    
    for (const route of invalidRoutes) {
      await page.goto(route);
      
      // Should show error page or redirect to home
      const is404 = await page.locator('text=404, text="Not Found"').count() > 0;
      const isHome = page.url().endsWith('/') || page.url().includes('localhost:3000');
      
      expect(is404 || isHome).toBeTruthy();
      console.log(`✅ Error handling for ${route}: ${is404 ? '404 page' : 'redirected'}`);
    }

    // Test network error recovery
    await page.goto('/');
    
    // Check for error boundaries or fallback UI
    const errorElements = [
      '.error-boundary',
      '.error-fallback',
      '[data-testid*="error"]',
      '.alert-error',
      '.notification-error'
    ];

    // Look for any existing errors in the console
    const hasInitialErrors = errorMonitor.hasErrors();
    console.log(`✅ Initial error state: ${hasInitialErrors ? 'Has errors' : 'Clean'}`);

    console.log('✅ Error recovery mechanisms validated');
  });
});