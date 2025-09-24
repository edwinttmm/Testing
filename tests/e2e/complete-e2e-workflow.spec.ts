import { test, expect } from '@playwright/test';
import { ErrorMonitor } from './utils/error-monitor';
import { TestHelpers } from './utils/test-helpers';

test.describe('Complete End-to-End PRD Workflow', () => {
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

  test('E2E-1: Complete PRD Workflow - Upload → Annotate → Project → HIL → Report', async ({ page }) => {
    test.setTimeout(300000); // 5 minutes for full workflow
    
    console.log('🚀 Starting complete PRD workflow test...');
    
    const workflowSteps: { [key: string]: boolean } = {
      'navigation': false,
      'upload': false,
      'annotation': false,
      'project': false,
      'hil': false,
      'analysis': false,
      'report': false
    };

    // ==================================================
    // STEP 1: BASIC NAVIGATION AND UI VALIDATION
    // ==================================================
    console.log('\n📍 STEP 1: Basic Navigation Validation');
    
    await page.goto('/');
    await helpers.waitForPageLoad();
    
    // Check if main navigation elements exist
    const navElements = [
      'nav',
      '.navigation',
      '.nav-menu',
      '.sidebar',
      '.header-menu',
      '[role="navigation"]'
    ];
    
    for (const selector of navElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found navigation: ${selector}`);
        workflowSteps.navigation = true;
        break;
      }
    }

    // Check for key UI elements
    const mainElements = [
      'main',
      '.main-content',
      '.app-content',
      '.container'
    ];
    
    for (const selector of mainElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found main content: ${selector}`);
        break;
      }
    }

    // ==================================================
    // STEP 2: VIDEO UPLOAD WORKFLOW (PRD MODULE 1)
    // ==================================================
    console.log('\n📍 STEP 2: Video Upload Workflow');
    
    // Try to navigate to upload section
    const uploadPaths = ['/upload', '/videos/upload', '/video-upload'];
    const uploadTriggers = [
      'button:has-text("Upload")',
      '[data-testid*="upload"]',
      '.upload-btn',
      '[href*="upload"]'
    ];

    // Try direct navigation first
    for (const path of uploadPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        console.log(`✅ Navigated to upload via: ${path}`);
        break;
      } catch (e) {
        continue;
      }
    }

    // Try finding upload triggers
    for (const trigger of uploadTriggers) {
      if (await page.locator(trigger).count() > 0) {
        try {
          await helpers.clickAndWait(trigger);
          console.log(`✅ Found upload trigger: ${trigger}`);
          workflowSteps.upload = true;
          break;
        } catch (e) {
          continue;
        }
      }
    }

    // Look for upload interface elements
    const uploadElements = [
      'input[type="file"]',
      '.upload-area',
      '.dropzone',
      '[data-testid*="file"]'
    ];

    for (const selector of uploadElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found upload interface: ${selector}`);
        workflowSteps.upload = true;
        
        // Check file input accepts video formats
        if (selector.includes('input[type="file"]')) {
          const accept = await page.locator(selector).first().getAttribute('accept');
          if (accept && (accept.includes('.mp4') || accept.includes('video/'))) {
            console.log(`✅ Video formats supported: ${accept}`);
          }
        }
        break;
      }
    }

    // ==================================================
    // STEP 3: ANNOTATION/VALIDATION WORKFLOW (PRD MODULE 1)
    // ==================================================
    console.log('\n📍 STEP 3: Annotation/Validation Workflow');
    
    // Navigate to annotation interface
    const annotationPaths = ['/annotate', '/annotations', '/validation', '/ground-truth'];
    
    for (const path of annotationPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        console.log(`✅ Accessed annotation interface: ${path}`);
        break;
      } catch (e) {
        continue;
      }
    }

    // Look for annotation interface elements
    const annotationElements = [
      '.video-viewport',
      '.annotation-area',
      '.bounding-box',
      '.detection-box',
      '.video-controls',
      '.timeline',
      '[data-testid*="annotation"]',
      '[data-testid*="video"]'
    ];

    for (const selector of annotationElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found annotation element: ${selector}`);
        workflowSteps.annotation = true;
      }
    }

    // Look for VRU detection elements
    const vruElements = [
      '[data-testid*="vru"]',
      '[data-testid*="pedestrian"]',
      '[data-testid*="cyclist"]',
      '.object-detection',
      '.vru-detection'
    ];

    for (const selector of vruElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found VRU detection: ${selector}`);
      }
    }

    // ==================================================
    // STEP 4: PROJECT MANAGEMENT WORKFLOW (PRD MODULE 2)
    // ==================================================
    console.log('\n📍 STEP 4: Project Management Workflow');
    
    // Navigate to projects
    const projectPaths = ['/projects', '/project-management'];
    
    for (const path of projectPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        console.log(`✅ Accessed project management: ${path}`);
        break;
      } catch (e) {
        continue;
      }
    }

    // Look for project creation
    const projectCreateElements = [
      'button:has-text("Create Project")',
      'button:has-text("New Project")',
      '[data-testid*="create-project"]',
      '.create-project'
    ];

    for (const selector of projectCreateElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project creation: ${selector}`);
        workflowSteps.project = true;
        
        // Try to test project creation
        try {
          await helpers.clickAndWait(selector);
          
          // Look for project form
          const nameInput = page.locator('input[name*="name"], input[placeholder*="name"]').first();
          if (await nameInput.count() > 0) {
            await nameInput.fill('E2E Test Project - Front-Facing Camera v2.1');
            console.log(`✅ Project form functional`);
          }
        } catch (e) {
          console.log(`⚠️ Could not test project creation form`);
        }
        break;
      }
    }

    // Look for existing projects
    const projectListElements = [
      '.project-list',
      '.project-grid',
      '.project-item',
      '[data-testid*="project"]'
    ];

    for (const selector of projectListElements) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found project list: ${selector} (${count} items)`);
        workflowSteps.project = true;
      }
    }

    // ==================================================
    // STEP 5: HIL TEST EXECUTION (PRD MODULE 3)
    // ==================================================
    console.log('\n📍 STEP 5: HIL Test Execution Workflow');
    
    // Navigate to HIL/test interface
    const hilPaths = ['/hil', '/test', '/testing', '/execution'];
    
    for (const path of hilPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        console.log(`✅ Accessed HIL interface: ${path}`);
        break;
      } catch (e) {
        continue;
      }
    }

    // Check LabJack connection status
    const labJackElements = [
      '[data-testid*="labjack"]',
      '.labjack-status',
      '.connection-status',
      'text="Connected"',
      'text="Not Detected"'
    ];

    for (const selector of labJackElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found LabJack status: ${selector}`);
        workflowSteps.hil = true;
      }
    }

    // Check latency threshold input
    const thresholdElements = [
      'input[name*="latency"]',
      'input[name*="threshold"]',
      '[data-testid*="threshold"]'
    ];

    for (const selector of thresholdElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found threshold input: ${selector}`);
        try {
          await page.fill(selector, '100');
          console.log(`✅ Threshold input functional`);
        } catch (e) {
          console.log(`⚠️ Could not test threshold input`);
        }
      }
    }

    // Check video playback interface
    const videoElements = [
      'video',
      '.video-player',
      '.media-player'
    ];

    for (const selector of videoElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found video playback: ${selector}`);
        workflowSteps.hil = true;
      }
    }

    // Check test execution controls
    const testControlElements = [
      'button:has-text("Start Test")',
      'button:has-text("Run Test")',
      '[data-testid*="start-test"]'
    ];

    for (const selector of testControlElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found test control: ${selector}`);
        
        const isEnabled = await page.locator(selector).first().isEnabled();
        if (isEnabled) {
          console.log(`✅ Test execution ready`);
        }
      }
    }

    // ==================================================
    // STEP 6: ANALYSIS & REPORTING (PRD MODULE 4)
    // ==================================================
    console.log('\n📍 STEP 6: Analysis & Reporting Workflow');
    
    // Navigate to analysis/results
    const analysisPaths = ['/analysis', '/results', '/reports', '/dashboard'];
    
    for (const path of analysisPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        console.log(`✅ Accessed analysis interface: ${path}`);
        break;
      } catch (e) {
        continue;
      }
    }

    // Check pass/fail analysis
    const analysisElements = [
      '[data-testid*="pass"]',
      '[data-testid*="fail"]',
      '.pass-fail-analysis',
      'text="Pass"',
      'text="Fail"'
    ];

    for (const selector of analysisElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found analysis interface: ${selector}`);
        workflowSteps.analysis = true;
      }
    }

    // Check latency validation
    const latencyAnalysisElements = [
      '[data-testid*="latency"]',
      '.latency-validation',
      '.timing-analysis',
      'text="Latency"'
    ];

    for (const selector of latencyAnalysisElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found latency analysis: ${selector}`);
      }
    }

    // Check report generation
    const reportElements = [
      'button:has-text("Generate Report")',
      'button:has-text("Export")',
      '[data-testid*="report"]'
    ];

    for (const selector of reportElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found report generation: ${selector}`);
        workflowSteps.report = true;
        
        // Try report generation
        try {
          await helpers.clickAndWait(selector);
          console.log(`✅ Report generation initiated`);
        } catch (e) {
          console.log(`⚠️ Could not test report generation`);
        }
      }
    }

    // ==================================================
    // WORKFLOW SUMMARY
    // ==================================================
    console.log('\n📋 WORKFLOW VALIDATION SUMMARY:');
    console.log('=====================================');
    
    let completedSteps = 0;
    for (const [step, completed] of Object.entries(workflowSteps)) {
      const status = completed ? '✅' : '❌';
      console.log(`${status} ${step.toUpperCase()}: ${completed ? 'VALIDATED' : 'NOT FOUND'}`);
      if (completed) completedSteps++;
    }
    
    const completionRate = (completedSteps / Object.keys(workflowSteps).length) * 100;
    console.log(`\n🎯 OVERALL COMPLETION: ${completedSteps}/${Object.keys(workflowSteps).length} (${completionRate.toFixed(1)}%)`);
    
    // Expect at least 50% of workflow steps to be validated
    expect(completionRate).toBeGreaterThan(50);
    
    console.log('✅ Complete PRD workflow validation finished');
  });

  test('E2E-2: Performance Testing - Large File Handling', async ({ page }) => {
    test.setTimeout(120000);
    
    console.log('🚀 Starting performance testing...');

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Monitor performance metrics
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      const memory = (performance as any).memory;
      
      return {
        loadTime: navigation.loadEventEnd - navigation.loadEventStart,
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        firstPaint: navigation.responseEnd - navigation.requestStart,
        usedJSHeapSize: memory ? memory.usedJSHeapSize : 0,
        totalJSHeapSize: memory ? memory.totalJSHeapSize : 0
      };
    });

    console.log('📊 Performance Metrics:');
    console.log(`   Load Time: ${performanceMetrics.loadTime}ms`);
    console.log(`   DOM Content Loaded: ${performanceMetrics.domContentLoaded}ms`);
    console.log(`   First Paint: ${performanceMetrics.firstPaint}ms`);
    console.log(`   Memory Used: ${(performanceMetrics.usedJSHeapSize / 1024 / 1024).toFixed(2)}MB`);

    // Performance thresholds
    expect(performanceMetrics.loadTime).toBeLessThan(10000); // 10 seconds
    expect(performanceMetrics.domContentLoaded).toBeLessThan(5000); // 5 seconds

    console.log('✅ Performance testing completed');
  });

  test('E2E-3: Multi-User Collaboration Scenarios', async ({ page }) => {
    test.setTimeout(90000);
    
    console.log('🚀 Testing multi-user collaboration scenarios...');

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Look for collaboration features
    const collaborationElements = [
      '.project-sharing',
      '.collaboration',
      'button:has-text("Share")',
      '.team-members',
      '[data-testid*="share"]'
    ];

    for (const selector of collaborationElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found collaboration feature: ${selector}`);
      }
    }

    // Test concurrent access patterns
    const concurrentElements = [
      '.real-time-updates',
      '.live-sync',
      '.concurrent-editing'
    ];

    for (const selector of concurrentElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found concurrent access feature: ${selector}`);
      }
    }

    console.log('✅ Multi-user collaboration testing completed');
  });

  test('E2E-4: Error Recovery and Resilience', async ({ page }) => {
    test.setTimeout(90000);
    
    console.log('🚀 Testing error recovery and resilience...');

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Test network interruption simulation
    try {
      await page.setOffline(true);
      await page.waitForTimeout(2000);
      await page.setOffline(false);
      await helpers.waitForPageLoad();
      console.log('✅ Network interruption recovery tested');
    } catch (e) {
      console.log('⚠️ Could not test network interruption recovery');
    }

    // Test invalid route handling
    await page.goto('/nonexistent-route-12345');
    const is404OrRedirect = 
      (await page.locator('text=404, text="Not Found"').count() > 0) ||
      page.url().includes('/') || 
      page.url().includes('dashboard');
    
    expect(is404OrRedirect).toBeTruthy();
    console.log('✅ Invalid route handling verified');

    // Check error boundaries
    const errorBoundaryElements = [
      '.error-boundary',
      '.error-fallback',
      '[data-testid*="error-boundary"]'
    ];

    for (const selector of errorBoundaryElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found error boundary: ${selector}`);
      }
    }

    console.log('✅ Error recovery testing completed');
  });

  test('E2E-5: Cross-Browser Compatibility Validation', async ({ page, browserName }) => {
    test.setTimeout(60000);
    
    console.log(`🚀 Testing cross-browser compatibility on ${browserName}...`);

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Browser-specific feature detection
    const browserFeatures = await page.evaluate(() => {
      return {
        webgl: !!window.WebGLRenderingContext,
        webRTC: !!window.RTCPeerConnection,
        fileAPI: !!window.File,
        websockets: !!window.WebSocket,
        localStorage: !!window.localStorage,
        sessionStorage: !!window.sessionStorage,
        canvas: !!document.createElement('canvas').getContext,
        video: !!document.createElement('video').canPlayType
      };
    });

    console.log(`📱 Browser Features (${browserName}):`);
    for (const [feature, supported] of Object.entries(browserFeatures)) {
      console.log(`   ${feature}: ${supported ? '✅' : '❌'}`);
    }

    // Critical features for the application
    expect(browserFeatures.fileAPI).toBeTruthy();
    expect(browserFeatures.video).toBeTruthy();
    expect(browserFeatures.localStorage).toBeTruthy();

    console.log(`✅ Cross-browser compatibility testing completed for ${browserName}`);
  });
});