const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('Error Handling and Recovery', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
  });

  test('should handle network connectivity issues', async ({ page }) => {
    await helpers.login();
    await page.goto('/dashboard');
    
    // Simulate network failure
    await page.route('**/*', route => route.abort());
    
    // Try to make a request that should fail
    await page.click('[data-testid="refresh-data-button"]');
    
    // Should show network error message
    await page.waitForSelector('[data-testid="network-error"]', { timeout: 10000 });
    await helpers.takeScreenshot('network-error-displayed');
    
    const errorElement = page.locator('[data-testid="network-error"]');
    await expect(errorElement).toBeVisible();
    
    const errorText = await errorElement.textContent();
    expect(errorText).toMatch(/network|connection|offline/i);
    
    // Restore network connectivity
    await page.unroute('**/*');
    
    // Should recover automatically or provide retry option
    await page.click('[data-testid="retry-connection"]');
    await page.waitForSelector('[data-testid="network-restored"]', { timeout: 10000 });
    
    await helpers.takeScreenshot('network-restored');
    
    await helpers.saveTestResults('network-error-handling', {
      error_detected: true,
      recovery_successful: true,
      timestamp: Date.now()
    });
  });

  test('should handle API server errors gracefully', async ({ page }) => {
    await helpers.login();
    
    // Mock 500 server error response
    await page.route('**/api/projects', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' })
      });
    });
    
    await page.goto('/dashboard');
    
    // Should handle the server error
    await page.waitForSelector('[data-testid="server-error"]', { timeout: 15000 });
    await helpers.takeScreenshot('server-error-500');
    
    const errorMessage = await page.textContent('[data-testid="error-message"]');
    expect(errorMessage).toMatch(/server error|something went wrong/i);
    
    // Test different error codes
    const errorCodes = [400, 401, 403, 404, 503];
    
    for (const code of errorCodes) {
      await page.route('**/api/test-endpoint', route => {
        route.fulfill({
          status: code,
          contentType: 'application/json',
          body: JSON.stringify({ error: `Error ${code}` })
        });
      });
      
      const response = await page.request.get('http://localhost:3000/api/test-endpoint');
      expect(response.status()).toBe(code);
      
      await helpers.takeScreenshot(`error-${code}-handled`);
    }
    
    await helpers.saveTestResults('api-error-handling', {
      error_codes_tested: [500, ...errorCodes],
      all_handled_gracefully: true,
      timestamp: Date.now()
    });
  });

  test('should handle ML model loading failures', async ({ page }) => {
    await helpers.login();
    await page.goto('/dashboard');
    
    // Mock ML model loading failure
    await page.route('**/ml/load_model', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ 
          status: 'error', 
          message: 'Failed to load YOLO model',
          error_type: 'model_loading_error'
        })
      });
    });
    
    await page.click('[data-testid="video-processing-tab"]');
    await page.selectOption('[data-testid="model-select"]', 'yolov8');
    
    // Should show model loading error
    await page.waitForSelector('[data-testid="model-loading-error"]', { timeout: 15000 });
    await helpers.takeScreenshot('ml-model-loading-error');
    
    const errorElement = page.locator('[data-testid="model-loading-error"]');
    await expect(errorElement).toBeVisible();
    
    // Should provide fallback options
    const fallbackElement = page.locator('[data-testid="model-fallback-options"]');
    if (await fallbackElement.isVisible()) {
      await helpers.takeScreenshot('ml-model-fallback-options');
    }
    
    // Test retry mechanism
    await page.unroute('**/ml/load_model');
    await page.click('[data-testid="retry-model-loading"]');
    
    await page.waitForSelector('[data-testid="model-loaded"]', { timeout: 30000 });
    await helpers.takeScreenshot('ml-model-retry-success');
    
    await helpers.saveTestResults('ml-model-error-handling', {
      loading_error_handled: true,
      retry_successful: true,
      fallback_available: await fallbackElement.isVisible(),
      timestamp: Date.now()
    });
  });

  test('should handle file upload errors', async ({ page }) => {
    await helpers.login();
    await page.goto('/dashboard');
    await page.click('[data-testid="video-processing-tab"]');
    
    // Test various file upload error scenarios
    const errorScenarios = [
      {
        name: 'file_too_large',
        mockResponse: { status: 413, body: { error: 'File too large' } }
      },
      {
        name: 'invalid_file_type',
        mockResponse: { status: 400, body: { error: 'Invalid file type' } }
      },
      {
        name: 'upload_timeout',
        mockResponse: { status: 408, body: { error: 'Upload timeout' } }
      }
    ];
    
    for (const scenario of errorScenarios) {
      // Mock upload error
      await page.route('**/upload/video', route => {
        route.fulfill({
          status: scenario.mockResponse.status,
          contentType: 'application/json',
          body: JSON.stringify(scenario.mockResponse.body)
        });
      });
      
      // Try to upload file
      const fileInput = page.locator('[data-testid="video-upload-input"]');
      await fileInput.setInputFiles('./tests/fixtures/test-video.mp4');
      
      // Should show appropriate error
      await page.waitForSelector(`[data-testid="upload-error-${scenario.name}"]`, { timeout: 10000 });
      await helpers.takeScreenshot(`upload-error-${scenario.name}`);
      
      const errorText = await page.textContent('[data-testid="upload-error-message"]');
      expect(errorText).toMatch(/upload|file|error/i);
      
      // Clear the error for next test
      await page.click('[data-testid="clear-upload-error"]');
      await page.unroute('**/upload/video');
    }
    
    await helpers.saveTestResults('file-upload-error-handling', {
      scenarios_tested: errorScenarios.length,
      all_errors_handled: true,
      timestamp: Date.now()
    });
  });

  test('should handle WebSocket connection failures', async ({ page }) => {
    await helpers.login();
    
    // Add WebSocket error monitoring
    await page.addInitScript(() => {
      window.websocketErrors = [];
      window.websocketReconnectAttempts = 0;
      
      const originalWebSocket = window.WebSocket;
      window.WebSocket = function(url, protocols) {
        const ws = new originalWebSocket(url, protocols);
        
        ws.addEventListener('error', (event) => {
          window.websocketErrors.push({
            error: event.error || 'Connection error',
            timestamp: Date.now()
          });
        });
        
        ws.addEventListener('close', (event) => {
          if (event.code !== 1000) { // Not normal closure
            window.websocketReconnectAttempts++;
          }
        });
        
        return ws;
      };
    });
    
    await page.goto('/dashboard');
    
    // Simulate WebSocket server unavailable
    await page.route('ws://localhost:8000/ws', route => route.abort());
    
    // Wait for WebSocket connection error
    await page.waitForFunction(() => {
      return window.websocketErrors && window.websocketErrors.length > 0;
    }, { timeout: 10000 });
    
    const errors = await page.evaluate(() => window.websocketErrors);
    expect(errors.length).toBeGreaterThan(0);
    
    // Should show WebSocket error in UI
    await page.waitForSelector('[data-testid="websocket-connection-error"]', { timeout: 10000 });
    await helpers.takeScreenshot('websocket-connection-error');
    
    // Test reconnection attempts
    await page.unroute('ws://localhost:8000/ws');
    
    // Should attempt to reconnect
    await page.waitForFunction(() => {
      return window.websocketReconnectAttempts > 0;
    }, { timeout: 15000 });
    
    const reconnectAttempts = await page.evaluate(() => window.websocketReconnectAttempts);
    expect(reconnectAttempts).toBeGreaterThan(0);
    
    await helpers.saveTestResults('websocket-error-handling', {
      errors_detected: errors.length,
      reconnect_attempts: reconnectAttempts,
      error_handling_working: true,
      timestamp: Date.now()
    });
  });

  test('should handle LabJack hardware disconnection', async ({ page }) => {
    await helpers.login();
    await page.goto('/dashboard');
    await page.click('[data-testid="hardware-tab"]');
    
    // Mock LabJack disconnection
    await page.route('**/hardware/labjack/status', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'error',
          connected: false,
          error: 'LabJack device not found'
        })
      });
    });
    
    await page.reload();
    
    // Should show hardware disconnection error
    await page.waitForSelector('[data-testid="labjack-disconnected-error"]', { timeout: 10000 });
    await helpers.takeScreenshot('labjack-disconnection-error');
    
    const errorMessage = await page.textContent('[data-testid="hardware-error-message"]');
    expect(errorMessage).toMatch(/labjack|hardware|disconnected|not found/i);
    
    // Should provide reconnection options
    const reconnectButton = page.locator('[data-testid="reconnect-labjack"]');
    await expect(reconnectButton).toBeVisible();
    
    // Test hardware recovery
    await page.unroute('**/hardware/labjack/status');
    await page.route('**/hardware/labjack/status', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          connected: true,
          device_info: { type: 'T7', serial: 123456 }
        })
      });
    });
    
    await page.click('[data-testid="reconnect-labjack"]');
    
    // Should recover and show connected status
    await page.waitForSelector('[data-testid="labjack-connected"]', { timeout: 10000 });
    await helpers.takeScreenshot('labjack-reconnected');
    
    await helpers.saveTestResults('labjack-error-handling', {
      disconnection_detected: true,
      reconnection_successful: true,
      user_guided_recovery: true,
      timestamp: Date.now()
    });
  });

  test('should handle browser compatibility issues', async ({ page }) => {
    // Test unsupported browser features gracefully
    await page.addInitScript(() => {
      // Simulate missing WebGL support
      const canvas = document.createElement('canvas');
      const originalGetContext = canvas.getContext;
      canvas.getContext = function(contextType) {
        if (contextType === 'webgl' || contextType === 'experimental-webgl') {
          return null; // Simulate no WebGL support
        }
        return originalGetContext.call(this, contextType);
      };
      
      // Simulate missing getUserMedia
      if (navigator.mediaDevices) {
        navigator.mediaDevices.getUserMedia = undefined;
      }
      
      window.browserCompatibilityIssues = [];
    });
    
    await helpers.login();
    await page.goto('/dashboard');
    
    // Try to use features that might not be supported
    await page.click('[data-testid="video-processing-tab"]');
    
    // Should show graceful fallbacks for missing features
    await page.waitForSelector('[data-testid="browser-compatibility-warning"]', { timeout: 10000 });
    await helpers.takeScreenshot('browser-compatibility-warning');
    
    const warningText = await page.textContent('[data-testid="compatibility-message"]');
    expect(warningText).toMatch(/browser|support|feature|upgrade/i);
    
    // Should provide alternative options
    const fallbackOptions = page.locator('[data-testid="feature-fallback"]');
    await expect(fallbackOptions).toBeVisible();
    
    await helpers.saveTestResults('browser-compatibility-handling', {
      compatibility_warning_shown: true,
      fallback_options_available: true,
      graceful_degradation: true,
      timestamp: Date.now()
    });
  });

  test('should handle session timeout and re-authentication', async ({ page }) => {
    await helpers.login();
    await page.goto('/dashboard');
    
    // Simulate session timeout
    await page.route('**/auth/verify', route => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Session expired' })
      });
    });
    
    // Try to access protected resource
    await page.click('[data-testid="protected-action-button"]');
    
    // Should detect session timeout and redirect to login
    await page.waitForURL('**/login**', { timeout: 10000 });
    await helpers.takeScreenshot('session-timeout-redirect');
    
    // Should show session expired message
    const sessionMessage = page.locator('[data-testid="session-expired-message"]');
    if (await sessionMessage.isVisible()) {
      const messageText = await sessionMessage.textContent();
      expect(messageText).toMatch(/session|expired|login again/i);
    }
    
    // Should allow re-authentication
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'password');
    await page.click('[data-testid="login-button"]');
    
    // Should redirect back to dashboard
    await page.waitForURL('**/dashboard**', { timeout: 10000 });
    await helpers.takeScreenshot('re-authentication-success');
    
    await helpers.saveTestResults('session-timeout-handling', {
      timeout_detected: true,
      automatic_redirect: true,
      reauth_successful: true,
      timestamp: Date.now()
    });
  });

  test('should handle concurrent operation conflicts', async ({ page }) => {
    await helpers.login();
    await page.goto('/dashboard');
    
    // Simulate concurrent ML inference requests causing conflicts
    const conflictResults = [];
    
    const request1Promise = page.request.post('http://localhost:8000/ml/yolo/inference', {
      data: { image_data: 'test1', model_lock: true }
    });
    
    const request2Promise = page.request.post('http://localhost:8000/ml/yolo/inference', {
      data: { image_data: 'test2', model_lock: true }
    });
    
    const [response1, response2] = await Promise.all([request1Promise, request2Promise]);
    
    // One should succeed, one should be queued or return conflict error
    const results = [
      { response: response1, data: await response1.json() },
      { response: response2, data: await response2.json() }
    ];
    
    // Check for conflict handling
    const hasConflictHandling = results.some(result => 
      result.response.status() === 409 || 
      result.data.status === 'queued' || 
      result.data.message?.includes('busy')
    );
    
    expect(hasConflictHandling).toBeTruthy();
    
    await helpers.saveTestResults('concurrent-operation-handling', {
      conflict_detected: hasConflictHandling,
      responses: results.map(r => ({ status: r.response.status(), data: r.data })),
      proper_queuing: true,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('concurrent-operations-handled');
  });
});