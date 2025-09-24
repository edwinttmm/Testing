const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');

test.describe('WebSocket Real-time Communication', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
    await helpers.login();
  });

  test('should establish WebSocket connection', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Inject WebSocket monitoring script
    await page.addInitScript(() => {
      window.websocketEvents = [];
      const originalWebSocket = window.WebSocket;
      window.WebSocket = function(url, protocols) {
        const ws = new originalWebSocket(url, protocols);
        
        ws.addEventListener('open', () => {
          window.websocketEvents.push({ type: 'open', timestamp: Date.now() });
          window.websocketConnected = true;
        });
        
        ws.addEventListener('message', (event) => {
          window.websocketEvents.push({ 
            type: 'message', 
            data: event.data, 
            timestamp: Date.now() 
          });
        });
        
        ws.addEventListener('error', (event) => {
          window.websocketEvents.push({ 
            type: 'error', 
            error: event.error, 
            timestamp: Date.now() 
          });
        });
        
        ws.addEventListener('close', () => {
          window.websocketEvents.push({ type: 'close', timestamp: Date.now() });
          window.websocketConnected = false;
        });
        
        return ws;
      };
    });
    
    await page.reload();
    await helpers.waitForWebSocketConnection();
    
    const events = await page.evaluate(() => window.websocketEvents);
    expect(events.some(event => event.type === 'open')).toBeTruthy();
    
    await helpers.takeScreenshot('websocket-connected');
    await helpers.saveTestResults('websocket-connection', {
      connected: true,
      events: events,
      timestamp: Date.now()
    });
  });

  test('should receive real-time detection updates', async ({ page }) => {
    await page.goto('/dashboard');
    await helpers.waitForWebSocketConnection();
    
    // Start a detection process to trigger WebSocket messages
    await page.click('[data-testid="start-realtime-detection"]');
    
    // Wait for WebSocket messages
    await page.waitForFunction(() => {
      return window.websocketEvents && 
             window.websocketEvents.some(event => 
               event.type === 'message' && 
               event.data.includes('detection_result')
             );
    }, { timeout: 30000 });
    
    const events = await page.evaluate(() => window.websocketEvents);
    const detectionMessages = events.filter(event => 
      event.type === 'message' && 
      event.data.includes('detection_result')
    );
    
    expect(detectionMessages.length).toBeGreaterThan(0);
    
    await helpers.takeScreenshot('realtime-detection-updates');
    await helpers.saveTestResults('websocket-detection-updates', {
      detection_messages_received: detectionMessages.length,
      total_events: events.length,
      timestamp: Date.now()
    });
  });

  test('should handle WebSocket reconnection', async ({ page }) => {
    await page.goto('/dashboard');
    await helpers.waitForWebSocketConnection();
    
    // Simulate connection loss by navigating away and back
    await page.goto('/about');
    await page.waitForTimeout(2000);
    await page.goto('/dashboard');
    
    // Should reconnect automatically
    await helpers.waitForWebSocketConnection();
    
    const events = await page.evaluate(() => window.websocketEvents);
    const openEvents = events.filter(event => event.type === 'open');
    
    expect(openEvents.length).toBeGreaterThan(1); // Should have reconnected
    
    await helpers.takeScreenshot('websocket-reconnected');
    await helpers.saveTestResults('websocket-reconnection', {
      reconnection_successful: true,
      open_events_count: openEvents.length,
      timestamp: Date.now()
    });
  });

  test('should send and receive WebSocket messages', async ({ page }) => {
    await page.goto('/dashboard');
    await helpers.waitForWebSocketConnection();
    
    // Send a test message through the UI
    await page.fill('[data-testid="websocket-message-input"]', 'Test message');
    await page.click('[data-testid="send-websocket-message"]');
    
    // Wait for response
    await page.waitForFunction(() => {
      return window.websocketEvents && 
             window.websocketEvents.some(event => 
               event.type === 'message' && 
               event.data.includes('Test message')
             );
    }, { timeout: 10000 });
    
    const events = await page.evaluate(() => window.websocketEvents);
    const responseMessage = events.find(event => 
      event.type === 'message' && 
      event.data.includes('Test message')
    );
    
    expect(responseMessage).toBeTruthy();
    
    await helpers.takeScreenshot('websocket-message-sent');
  });

  test('should handle multiple concurrent WebSocket connections', async ({ browser }) => {
    const contexts = await Promise.all([
      browser.newContext(),
      browser.newContext(),
      browser.newContext()
    ]);
    
    const pages = await Promise.all(
      contexts.map(context => context.newPage())
    );
    
    const helpers = pages.map(page => new TestHelpers(page));
    
    // Login and connect all pages
    await Promise.all(pages.map(async (page, index) => {
      await helpers[index].login();
      await page.goto('/dashboard');
      
      // Add WebSocket monitoring
      await page.addInitScript(() => {
        window.websocketEvents = [];
        window.websocketConnected = false;
        const originalWebSocket = window.WebSocket;
        window.WebSocket = function(url, protocols) {
          const ws = new originalWebSocket(url, protocols);
          ws.addEventListener('open', () => {
            window.websocketConnected = true;
          });
          return ws;
        };
      });
      
      await page.reload();
      await helpers[index].waitForWebSocketConnection();
    }));
    
    // Verify all connections are established
    const connections = await Promise.all(
      pages.map(page => page.evaluate(() => window.websocketConnected))
    );
    
    expect(connections.every(connected => connected === true)).toBeTruthy();
    
    // Cleanup
    await Promise.all(contexts.map(context => context.close()));
    
    await helpers[0].saveTestResults('multiple-websocket-connections', {
      concurrent_connections: 3,
      all_connected: true,
      timestamp: Date.now()
    });
  });

  test('should measure WebSocket latency', async ({ page }) => {
    await page.goto('/dashboard');
    await helpers.waitForWebSocketConnection();
    
    const latencyResults = [];
    
    // Measure latency over multiple ping-pong cycles
    for (let i = 0; i < 10; i++) {
      const startTime = Date.now();
      
      // Send ping message
      await page.evaluate((timestamp) => {
        if (window.websocket && window.websocket.readyState === WebSocket.OPEN) {
          window.websocket.send(JSON.stringify({
            type: 'ping',
            timestamp: timestamp
          }));
        }
      }, startTime);
      
      // Wait for pong response
      await page.waitForFunction((sentTime) => {
        return window.websocketEvents && 
               window.websocketEvents.some(event => 
                 event.type === 'message' && 
                 event.data.includes('pong') &&
                 event.timestamp > sentTime
               );
      }, startTime, { timeout: 5000 });
      
      const endTime = Date.now();
      latencyResults.push(endTime - startTime);
      
      await page.waitForTimeout(500); // Wait between pings
    }
    
    const avgLatency = latencyResults.reduce((sum, latency) => sum + latency, 0) / 10;
    const minLatency = Math.min(...latencyResults);
    const maxLatency = Math.max(...latencyResults);
    
    expect(avgLatency).toBeLessThan(1000); // Should be under 1 second
    
    await helpers.saveTestResults('websocket-latency', {
      iterations: 10,
      avg_latency_ms: avgLatency,
      min_latency_ms: minLatency,
      max_latency_ms: maxLatency,
      all_results: latencyResults,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('websocket-latency-tested');
  });

  test('should handle WebSocket error scenarios', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Add error tracking
    await page.addInitScript(() => {
      window.websocketErrors = [];
      const originalWebSocket = window.WebSocket;
      window.WebSocket = function(url, protocols) {
        const ws = new originalWebSocket(url, protocols);
        
        ws.addEventListener('error', (event) => {
          window.websocketErrors.push({
            error: event.error,
            timestamp: Date.now()
          });
        });
        
        return ws;
      };
    });
    
    // Try to connect to invalid WebSocket endpoint
    await page.evaluate(() => {
      try {
        const ws = new WebSocket('ws://localhost:9999/invalid');
        ws.addEventListener('error', (event) => {
          window.websocketErrors.push({
            error: 'Connection failed',
            timestamp: Date.now()
          });
        });
      } catch (error) {
        window.websocketErrors.push({
          error: error.message,
          timestamp: Date.now()
        });
      }
    });
    
    await page.waitForTimeout(3000); // Wait for error handling
    
    const errors = await page.evaluate(() => window.websocketErrors);
    expect(errors.length).toBeGreaterThan(0);
    
    await helpers.saveTestResults('websocket-error-handling', {
      errors_caught: errors.length,
      error_details: errors,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('websocket-errors-handled');
  });
});