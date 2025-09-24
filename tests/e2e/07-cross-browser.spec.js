const { test, expect, devices } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('Cross-Browser Compatibility Testing', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
  });

  // Test core functionality across all browsers
  ['chromium', 'firefox', 'webkit'].forEach(browserName => {
    test(`should work correctly in ${browserName}`, async ({ page, browserName: currentBrowser }) => {
      if (currentBrowser !== browserName) return; // Skip if not current browser
      
      await helpers.login();
      await page.goto('/dashboard');
      
      // Test basic UI elements
      await expect(page.locator('[data-testid="dashboard-header"]')).toBeVisible();
      await expect(page.locator('[data-testid="navigation-menu"]')).toBeVisible();
      
      await helpers.takeScreenshot(`${browserName}-dashboard-loaded`);
      
      // Test ML model selection
      await page.click('[data-testid="video-processing-tab"]');
      await page.waitForSelector('[data-testid="model-select"]');
      await page.selectOption('[data-testid="model-select"]', 'yolov8');
      
      await helpers.takeScreenshot(`${browserName}-model-selected`);
      
      // Test WebSocket connection (browser-specific handling)
      await helpers.waitForWebSocketConnection();
      
      const websocketConnected = await page.evaluate(() => window.websocketConnected);
      expect(websocketConnected).toBe(true);
      
      await helpers.saveTestResults(`${browserName}-compatibility`, {
        browser: browserName,
        dashboard_loaded: true,
        ml_model_selection: true,
        websocket_connection: websocketConnected,
        timestamp: Date.now()
      });
    });
  });

  test('should handle CSS grid and flexbox layouts across browsers', async ({ page }) => {
    await helpers.login();
    await page.goto('/dashboard');
    
    // Test layout rendering
    const layoutElements = [
      '[data-testid="main-grid"]',
      '[data-testid="sidebar-flex"]',
      '[data-testid="video-container"]',
      '[data-testid="results-panel"]'
    ];
    
    const layoutResults = [];
    
    for (const selector of layoutElements) {
      const element = page.locator(selector);
      if (await element.isVisible()) {
        const boundingBox = await element.boundingBox();
        const styles = await element.evaluate(el => {
          const computed = getComputedStyle(el);
          return {
            display: computed.display,
            position: computed.position,
            width: computed.width,
            height: computed.height
          };
        });
        
        layoutResults.push({
          selector,
          visible: true,
          boundingBox,
          styles
        });
      } else {
        layoutResults.push({
          selector,
          visible: false
        });
      }
    }
    
    // Verify layouts are rendered properly
    const visibleElements = layoutResults.filter(result => result.visible);
    expect(visibleElements.length).toBeGreaterThan(2); // At least some elements visible
    
    await helpers.takeScreenshot('layout-compatibility-test');
    
    await helpers.saveTestResults('css-layout-compatibility', {
      elements_tested: layoutElements.length,
      visible_elements: visibleElements.length,
      layout_results: layoutResults,
      timestamp: Date.now()
    });
  });

  test('should handle JavaScript ES6+ features compatibility', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Test modern JavaScript features
    const jsFeatureTests = await page.evaluate(() => {
      const results = {};\n      
      // Test arrow functions
      try {\n        const arrow = () => 'test';\n        results.arrowFunctions = arrow() === 'test';\n      } catch (e) {\n        results.arrowFunctions = false;\n      }\n      \n      // Test async/await\n      try {\n        results.asyncAwait = typeof (async () => {}) === 'function';\n      } catch (e) {\n        results.asyncAwait = false;\n      }\n      \n      // Test template literals\n      try {\n        const test = 'world';\n        results.templateLiterals = `hello ${test}` === 'hello world';\n      } catch (e) {\n        results.templateLiterals = false;\n      }\n      \n      // Test destructuring\n      try {\n        const [a, b] = [1, 2];\n        const {x} = {x: 3};\n        results.destructuring = a === 1 && b === 2 && x === 3;\n      } catch (e) {\n        results.destructuring = false;\n      }\n      \n      // Test fetch API\n      results.fetchAPI = typeof fetch !== 'undefined';\n      \n      // Test WebSocket\n      results.webSocket = typeof WebSocket !== 'undefined';\n      \n      // Test local storage\n      results.localStorage = typeof localStorage !== 'undefined';\n      \n      return results;\n    });\n    \n    // Most features should be supported in modern browsers\n    expect(jsFeatureTests.arrowFunctions).toBe(true);\n    expect(jsFeatureTests.fetchAPI).toBe(true);\n    expect(jsFeatureTests.webSocket).toBe(true);\n    expect(jsFeatureTests.localStorage).toBe(true);\n    \n    await helpers.saveTestResults('javascript-compatibility', {\n      js_features: jsFeatureTests,\n      modern_features_supported: Object.values(jsFeatureTests).every(Boolean),\n      timestamp: Date.now()\n    });\n  });\n\n  test('should handle file upload across different browsers', async ({ page }) => {\n    await helpers.login();\n    await page.goto('/dashboard');\n    await page.click('[data-testid=\"video-processing-tab\"]');\n    \n    // Create a test file for upload\n    const fileContent = Buffer.from('test video data');\n    \n    // Test file upload functionality\n    const fileInput = page.locator('[data-testid=\"video-upload-input\"]');\n    \n    // Create temporary file\n    const fs = require('fs');\n    const path = require('path');\n    const testFilePath = path.join(__dirname, '../fixtures/test-upload.mp4');\n    \n    try {\n      fs.writeFileSync(testFilePath, fileContent);\n      \n      await fileInput.setInputFiles(testFilePath);\n      \n      // Wait for upload processing\n      await page.waitForSelector('[data-testid=\"upload-progress\"]', { timeout: 10000 });\n      \n      await helpers.takeScreenshot('file-upload-cross-browser');\n      \n      // Verify upload was processed\n      const uploadSuccess = await page.locator('[data-testid=\"upload-success\"]').isVisible({ timeout: 15000 });\n      expect(uploadSuccess).toBe(true);\n      \n    } finally {\n      // Cleanup\n      if (fs.existsSync(testFilePath)) {\n        fs.unlinkSync(testFilePath);\n      }\n    }\n    \n    await helpers.saveTestResults('file-upload-compatibility', {\n      upload_successful: true,\n      cross_browser_compatible: true,\n      timestamp: Date.now()\n    });\n  });\n\n  test('should handle video playback across browsers', async ({ page }) => {\n    await helpers.login();\n    await page.goto('/dashboard');\n    await page.click('[data-testid=\"video-processing-tab\"]');\n    \n    // Test video element support\n    const videoSupport = await page.evaluate(() => {\n      const video = document.createElement('video');\n      return {\n        canPlayMP4: video.canPlayType('video/mp4') !== '',\n        canPlayWebM: video.canPlayType('video/webm') !== '',\n        canPlayOgg: video.canPlayType('video/ogg') !== '',\n        supportsVideo: typeof video.play === 'function'\n      };\n    });\n    \n    expect(videoSupport.supportsVideo).toBe(true);\n    expect(videoSupport.canPlayMP4 || videoSupport.canPlayWebM).toBe(true); // At least one format\n    \n    // Test video player UI\n    if (await page.locator('[data-testid=\"video-player\"]').isVisible()) {\n      await helpers.takeScreenshot('video-player-cross-browser');\n      \n      const playerControls = [\n        '[data-testid=\"play-button\"]',\n        '[data-testid=\"pause-button\"]',\n        '[data-testid=\"progress-bar\"]',\n        '[data-testid=\"volume-control\"]'\n      ];\n      \n      const controlsVisible = await Promise.all(\n        playerControls.map(selector => \n          page.locator(selector).isVisible()\n        )\n      );\n      \n      const visibleControlsCount = controlsVisible.filter(Boolean).length;\n      expect(visibleControlsCount).toBeGreaterThan(2); // Most controls should be visible\n    }\n    \n    await helpers.saveTestResults('video-playback-compatibility', {\n      video_support: videoSupport,\n      video_formats_supported: Object.values(videoSupport).filter(Boolean).length,\n      timestamp: Date.now()\n    });\n  });\n\n  test('should handle responsive design across viewport sizes', async ({ page }) => {\n    await helpers.login();\n    \n    const viewportSizes = [\n      { width: 1920, height: 1080, name: 'desktop' },\n      { width: 1024, height: 768, name: 'tablet' },\n      { width: 375, height: 667, name: 'mobile' }\n    ];\n    \n    const responsiveResults = [];\n    \n    for (const viewport of viewportSizes) {\n      await page.setViewportSize(viewport);\n      await page.goto('/dashboard');\n      \n      // Test responsive elements\n      const mobileMenu = page.locator('[data-testid=\"mobile-menu\"]');\n      const desktopNav = page.locator('[data-testid=\"desktop-navigation\"]');\n      const sidebar = page.locator('[data-testid=\"sidebar\"]');\n      \n      const responsiveState = {\n        viewport: viewport.name,\n        dimensions: viewport,\n        mobile_menu_visible: await mobileMenu.isVisible(),\n        desktop_nav_visible: await desktopNav.isVisible(),\n        sidebar_visible: await sidebar.isVisible()\n      };\n      \n      responsiveResults.push(responsiveState);\n      \n      await helpers.takeScreenshot(`responsive-${viewport.name}`);\n      \n      // Test that critical elements are accessible\n      const criticalElements = [\n        '[data-testid=\"user-menu\"]',\n        '[data-testid=\"main-content\"]'\n      ];\n      \n      for (const selector of criticalElements) {\n        const element = page.locator(selector);\n        if (await element.isVisible()) {\n          const boundingBox = await element.boundingBox();\n          expect(boundingBox.width).toBeGreaterThan(0);\n          expect(boundingBox.height).toBeGreaterThan(0);\n        }\n      }\n    }\n    \n    // Verify responsive behavior\n    const mobileResult = responsiveResults.find(r => r.viewport === 'mobile');\n    const desktopResult = responsiveResults.find(r => r.viewport === 'desktop');\n    \n    // Mobile should show mobile menu, desktop should show desktop nav\n    if (mobileResult && desktopResult) {\n      expect(mobileResult.mobile_menu_visible || !mobileResult.desktop_nav_visible).toBe(true);\n      expect(desktopResult.desktop_nav_visible).toBe(true);\n    }\n    \n    await helpers.saveTestResults('responsive-design-compatibility', {\n      viewports_tested: viewportSizes.length,\n      responsive_results: responsiveResults,\n      responsive_working: true,\n      timestamp: Date.now()\n    });\n  });\n\n  test('should handle touch events on mobile browsers', async ({ page }) => {\n    // Simulate mobile device\n    await page.emulate(devices['iPhone 12']);\n    \n    await helpers.login();\n    await page.goto('/dashboard');\n    \n    // Test touch interactions\n    const touchTargets = [\n      '[data-testid=\"mobile-menu-button\"]',\n      '[data-testid=\"tab-button\"]',\n      '[data-testid=\"video-upload-button\"]'\n    ];\n    \n    const touchResults = [];\n    \n    for (const selector of touchTargets) {\n      const element = page.locator(selector);\n      if (await element.isVisible()) {\n        // Test tap interaction\n        await element.tap();\n        \n        // Wait for response\n        await page.waitForTimeout(500);\n        \n        touchResults.push({\n          selector,\n          tap_successful: true,\n          element_responsive: true\n        });\n        \n        await helpers.takeScreenshot(`touch-interaction-${selector.replace(/[^a-zA-Z0-9]/g, '_')}`);\n      }\n    }\n    \n    // Test swipe gestures if supported\n    const swipeArea = page.locator('[data-testid=\"swipe-area\"]');\n    if (await swipeArea.isVisible()) {\n      const box = await swipeArea.boundingBox();\n      \n      // Simulate swipe left\n      await page.touchscreen.tap(box.x + box.width * 0.8, box.y + box.height * 0.5);\n      await page.touchscreen.tap(box.x + box.width * 0.2, box.y + box.height * 0.5);\n      \n      await helpers.takeScreenshot('swipe-gesture-test');\n    }\n    \n    expect(touchResults.length).toBeGreaterThan(0);\n    \n    await helpers.saveTestResults('touch-interaction-compatibility', {\n      touch_targets_tested: touchResults.length,\n      touch_results: touchResults,\n      mobile_touch_working: true,\n      timestamp: Date.now()\n    });\n  });\n\n  test('should handle browser-specific WebGL capabilities', async ({ page }) => {\n    await helpers.login();\n    await page.goto('/dashboard');\n    \n    // Test WebGL support and capabilities\n    const webglCapabilities = await page.evaluate(() => {\n      const canvas = document.createElement('canvas');\n      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');\n      \n      if (!gl) {\n        return { supported: false };\n      }\n      \n      return {\n        supported: true,\n        renderer: gl.getParameter(gl.RENDERER),\n        vendor: gl.getParameter(gl.VENDOR),\n        version: gl.getParameter(gl.VERSION),\n        maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),\n        maxVertexAttribs: gl.getParameter(gl.MAX_VERTEX_ATTRIBS),\n        extensions: gl.getSupportedExtensions()\n      };\n    });\n    \n    if (webglCapabilities.supported) {\n      // Test WebGL-based features if available\n      await page.click('[data-testid=\"3d-visualization-tab\"]');\n      \n      if (await page.locator('[data-testid=\"webgl-canvas\"]').isVisible()) {\n        await helpers.takeScreenshot('webgl-visualization');\n        \n        // Test basic WebGL rendering\n        const renderingWorking = await page.evaluate(() => {\n          const canvas = document.querySelector('[data-testid=\"webgl-canvas\"]');\n          if (!canvas) return false;\n          \n          const gl = canvas.getContext('webgl');\n          if (!gl) return false;\n          \n          // Simple render test\n          gl.clearColor(1.0, 0.0, 0.0, 1.0);\n          gl.clear(gl.COLOR_BUFFER_BIT);\n          \n          return true;\n        });\n        \n        expect(renderingWorking).toBe(true);\n      }\n    }\n    \n    await helpers.saveTestResults('webgl-compatibility', {\n      webgl_capabilities: webglCapabilities,\n      webgl_features_working: webglCapabilities.supported,\n      timestamp: Date.now()\n    });\n  });\n});"}]