/**
 * ADAS Camera HIL Testing Platform - Real-time Test Session Monitoring Tests
 * @fileoverview Comprehensive testing of real-time monitoring and WebSocket functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Real-time Test Session Monitoring', () => {
  let page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    
    // Enhanced error capture for WebSocket and real-time operations
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('websocket') || msg.text().includes('socket')) {
        console.log('Monitoring Console:', msg.type(), msg.text());
      }
    });
    page.on('pageerror', error => console.log('Monitoring Page Error:', error.message));
    page.on('requestfailed', req => {
      if (req.url().includes('ws') || req.url().includes('monitoring') || req.url().includes('session')) {
        console.log('Monitoring Request Failed:', req.url(), req.failure()?.errorText);
      }
    });
  });

  test('should display real-time monitoring dashboard', async () => {
    console.log('📊 Testing real-time monitoring dashboard...');
    
    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/61-monitoring-dashboard.png', 
      fullPage: true 
    });
    
    // Check main monitoring interface elements
    const monitoringDashboard = page.locator('[data-testid="monitoring-dashboard"], .monitoring-dashboard');
    await expect(monitoringDashboard).toBeVisible({ timeout: 10000 });
    
    // Check session selector
    const sessionSelector = page.locator('[data-testid="session-selector"], select[name="session"]');
    if (await sessionSelector.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/62-session-selector.png' 
      });
    }
    
    // Check monitoring controls
    const startMonitoringButton = page.locator('[data-testid="start-monitoring"], button:has-text("Start Monitoring")');
    await expect(startMonitoringButton).toBeVisible();
    
    const pauseMonitoringButton = page.locator('[data-testid="pause-monitoring"], button:has-text("Pause")');
    const stopMonitoringButton = page.locator('[data-testid="stop-monitoring"], button:has-text("Stop")');
    
    // Check status indicators
    const connectionStatus = page.locator('[data-testid="connection-status"], .connection-status');
    if (await connectionStatus.isVisible()) {
      await expect(connectionStatus).toBeVisible();
    }
  });

  test('should establish WebSocket connection for real-time updates', async () => {
    console.log('🔌 Testing WebSocket connection establishment...');
    
    await page.goto('/monitoring');
    
    // Mock WebSocket connection establishment
    await page.evaluate(() => {
      window.mockWebSocket = {
        readyState: WebSocket.OPEN,
        url: 'ws://localhost:8000/ws/progress',
        connected: true
      };
      
      // Simulate WebSocket connection event
      window.dispatchEvent(new CustomEvent('websocketConnected', {
        detail: { url: 'ws://localhost:8000/ws/progress', status: 'connected' }
      }));
    });
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/63-websocket-connected.png',
      fullPage: true 
    });
    
    // Check connection status indicator
    const connectionIndicator = page.locator('[data-testid="ws-connection-indicator"], .connection-indicator');
    if (await connectionIndicator.isVisible()) {
      const statusText = await connectionIndicator.textContent();
      expect(statusText).toMatch(/connected|online|active/i);
    }
    
    // Check for real-time data containers
    const realtimeMetrics = page.locator('[data-testid="realtime-metrics"], .realtime-metrics');
    await expect(realtimeMetrics).toBeVisible({ timeout: 10000 });
    
    // Check for live data updates
    const lastUpdateTime = page.locator('[data-testid="last-update-time"], .last-update');
    if (await lastUpdateTime.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/64-realtime-updates.png' 
      });
    }
  });

  test('should display live test session metrics', async () => {
    console.log('📈 Testing live test session metrics display...');
    
    await page.goto('/monitoring');
    
    // Mock active test session with live metrics
    await page.evaluate(() => {
      window.mockSessionMetrics = {
        sessionId: 'test-session-123',
        startTime: new Date().toISOString(),
        status: 'running',
        metrics: {
          framesProcessed: 1250,
          totalFrames: 3000,
          detections: 45,
          avgConfidence: 0.87,
          processingRate: 25.5,
          memoryUsage: 68.2,
          cpuUsage: 42.1
        }
      };
      
      window.dispatchEvent(new CustomEvent('sessionMetricsUpdate', {
        detail: window.mockSessionMetrics
      }));
    });
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/65-session-metrics.png',
      fullPage: true 
    });
    
    // Check progress indicators
    const progressBar = page.locator('[data-testid="session-progress"], .progress-bar');
    if (await progressBar.isVisible()) {
      // Should show ~42% progress (1250/3000)
      const progressValue = await progressBar.getAttribute('value') || await progressBar.getAttribute('aria-valuenow');
      if (progressValue) {
        expect(parseFloat(progressValue)).toBeCloseTo(41.7, 1);
      }
    }
    
    // Check detection count
    const detectionCount = page.locator('[data-testid="detection-count"], .detection-count');
    if (await detectionCount.isVisible()) {
      await expect(detectionCount).toContainText('45');
    }
    
    // Check processing rate
    const processingRate = page.locator('[data-testid="processing-rate"], .processing-rate');
    if (await processingRate.isVisible()) {
      await expect(processingRate).toContainText('25.5');
    }
    
    // Check system performance metrics
    const memoryUsage = page.locator('[data-testid="memory-usage"], .memory-usage');
    if (await memoryUsage.isVisible()) {
      await expect(memoryUsage).toContainText('68.2');
    }
    
    const cpuUsage = page.locator('[data-testid="cpu-usage"], .cpu-usage');
    if (await cpuUsage.isVisible()) {
      await expect(cpuUsage).toContainText('42.1');
    }
  });

  test('should display real-time charts and visualizations', async () => {
    console.log('📊 Testing real-time charts and visualizations...');
    
    await page.goto('/monitoring');
    
    // Mock chart data updates
    await page.evaluate(() => {
      const now = Date.now();
      window.mockChartData = {
        timestamps: [],
        detectionRate: [],
        confidence: [],
        latency: []
      };
      
      // Generate mock time series data
      for (let i = 0; i < 20; i++) {
        const timestamp = now - (19 - i) * 1000; // Last 20 seconds
        window.mockChartData.timestamps.push(timestamp);
        window.mockChartData.detectionRate.push(Math.random() * 30 + 10);
        window.mockChartData.confidence.push(Math.random() * 0.3 + 0.7);
        window.mockChartData.latency.push(Math.random() * 50 + 25);
      }
      
      window.dispatchEvent(new CustomEvent('chartDataUpdate', {
        detail: window.mockChartData
      }));
    });
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/66-realtime-charts.png',
      fullPage: true 
    });
    
    // Check for chart containers
    const detectionRateChart = page.locator('[data-testid="detection-rate-chart"], .detection-rate-chart');
    if (await detectionRateChart.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/67-detection-rate-chart.png' 
      });
    }
    
    const confidenceChart = page.locator('[data-testid="confidence-chart"], .confidence-chart');
    if (await confidenceChart.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/68-confidence-chart.png' 
      });
    }
    
    const latencyChart = page.locator('[data-testid="latency-chart"], .latency-chart');
    if (await latencyChart.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/69-latency-chart.png' 
      });
    }
    
    // Test chart interaction
    const chartLegend = page.locator('[data-testid="chart-legend"], .chart-legend');
    if (await chartLegend.isVisible()) {
      const legendItem = chartLegend.locator('li, .legend-item').first();
      if (await legendItem.isVisible()) {
        await legendItem.click();
        await page.screenshot({ 
          path: './docs/errors/screenshots/70-chart-interaction.png' 
        });
      }
    }
  });

  test('should handle test session control operations', async () => {
    console.log('🎮 Testing test session control operations...');
    
    await page.goto('/monitoring');
    
    // Mock active test session
    await page.evaluate(() => {
      window.mockActiveSession = {
        sessionId: 'control-test-session',
        status: 'ready',
        canStart: true,
        canPause: false,
        canStop: false
      };
      
      window.dispatchEvent(new CustomEvent('sessionReady', {
        detail: window.mockActiveSession
      }));
    });
    
    // Test start session
    const startButton = page.locator('[data-testid="start-session"], button:has-text("Start")');
    if (await startButton.isVisible()) {
      await startButton.click();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/71-session-started.png',
        fullPage: true 
      });
      
      // Mock session started state
      await page.evaluate(() => {
        window.mockActiveSession = {
          ...window.mockActiveSession,
          status: 'running',
          canStart: false,
          canPause: true,
          canStop: true
        };
        
        window.dispatchEvent(new CustomEvent('sessionStarted', {
          detail: window.mockActiveSession
        }));
      });
    }
    
    // Test pause session
    const pauseButton = page.locator('[data-testid="pause-session"], button:has-text("Pause")');
    if (await pauseButton.isVisible({ timeout: 5000 })) {
      await pauseButton.click();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/72-session-paused.png' 
      });
    }
    
    // Test resume session
    const resumeButton = page.locator('[data-testid="resume-session"], button:has-text("Resume")');
    if (await resumeButton.isVisible({ timeout: 5000 })) {
      await resumeButton.click();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/73-session-resumed.png' 
      });
    }
    
    // Test stop session
    const stopButton = page.locator('[data-testid="stop-session"], button:has-text("Stop")');
    if (await stopButton.isVisible()) {
      await stopButton.click();
      
      // Check for confirmation dialog
      const confirmDialog = page.locator('[data-testid="stop-confirmation"], .confirmation-dialog');
      if (await confirmDialog.isVisible({ timeout: 3000 })) {
        const confirmButton = confirmDialog.locator('button:has-text("Confirm")');
        await confirmButton.click();
      }
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/74-session-stopped.png' 
      });
    }
  });

  test('should display session history and logs', async () => {
    console.log('📜 Testing session history and logs display...');
    
    await page.goto('/monitoring');
    
    // Mock session history
    await page.evaluate(() => {
      window.mockSessionHistory = {
        sessions: [
          {
            id: 'session-1',
            name: 'ADAS Test Run 1',
            startTime: '2024-01-15T10:30:00Z',
            endTime: '2024-01-15T11:15:00Z',
            status: 'completed',
            detections: 145,
            accuracy: 94.2
          },
          {
            id: 'session-2',
            name: 'Highway Scenario Test',
            startTime: '2024-01-15T14:20:00Z',
            endTime: null,
            status: 'running',
            detections: 67,
            accuracy: 91.8
          },
          {
            id: 'session-3',
            name: 'Urban Environment Test',
            startTime: '2024-01-14T16:45:00Z',
            endTime: '2024-01-14T17:30:00Z',
            status: 'failed',
            detections: 23,
            accuracy: 87.1,
            error: 'Connection timeout'
          }
        ],
        logs: [
          { timestamp: '2024-01-15T11:15:23Z', level: 'info', message: 'Session completed successfully' },
          { timestamp: '2024-01-15T11:14:58Z', level: 'warn', message: 'Low confidence detection: 0.42' },
          { timestamp: '2024-01-15T11:14:45Z', level: 'info', message: 'Processing frame 2850/3000' }
        ]
      };
      
      window.dispatchEvent(new CustomEvent('historyLoaded', {
        detail: window.mockSessionHistory
      }));
    });
    
    // Navigate to history tab
    const historyTab = page.locator('[data-testid="history-tab"], button:has-text("History")');
    if (await historyTab.isVisible()) {
      await historyTab.click();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/75-session-history.png',
        fullPage: true 
      });
      
      // Check session list
      const sessionList = page.locator('[data-testid="session-list"], .session-list');
      if (await sessionList.isVisible()) {
        const sessionItems = sessionList.locator('[data-testid*="session-item"], .session-item');
        const sessionCount = await sessionItems.count();
        expect(sessionCount).toBe(3);
        
        // Test session details view
        const firstSession = sessionItems.first();
        await firstSession.click();
        
        const sessionDetails = page.locator('[data-testid="session-details"], .session-details');
        if (await sessionDetails.isVisible({ timeout: 5000 })) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/76-session-details.png' 
          });
        }
      }
    }
    
    // Check logs panel
    const logsTab = page.locator('[data-testid="logs-tab"], button:has-text("Logs")');
    if (await logsTab.isVisible()) {
      await logsTab.click();
      
      const logsPanel = page.locator('[data-testid="logs-panel"], .logs-panel');
      if (await logsPanel.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/77-session-logs.png',
          fullPage: true 
        });
        
        // Check log filtering
        const logFilter = page.locator('[data-testid="log-filter"], select[name="logLevel"]');
        if (await logFilter.isVisible()) {
          await logFilter.selectOption('error');
          await page.screenshot({ 
            path: './docs/errors/screenshots/78-filtered-logs.png' 
          });
        }
      }
    }
  });

  test('should handle WebSocket disconnection and reconnection', async () => {
    console.log('🔄 Testing WebSocket disconnection and reconnection handling...');
    
    await page.goto('/monitoring');
    
    // Mock initial connection
    await page.evaluate(() => {
      window.mockWebSocketState = { connected: true };
      window.dispatchEvent(new CustomEvent('websocketConnected'));
    });
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/79-websocket-initial-connection.png' 
    });
    
    // Simulate disconnection
    await page.evaluate(() => {
      window.mockWebSocketState = { connected: false, error: 'Connection lost' };
      window.dispatchEvent(new CustomEvent('websocketDisconnected', {
        detail: { reason: 'Connection lost' }
      }));
    });
    
    // Check disconnection warning
    const disconnectionWarning = page.locator('[data-testid="connection-warning"], .connection-warning');
    if (await disconnectionWarning.isVisible({ timeout: 5000 })) {
      const warningText = await disconnectionWarning.textContent();
      expect(warningText).toMatch(/disconnected|connection lost|offline/i);
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/80-websocket-disconnected.png' 
      });
    }
    
    // Test manual reconnection
    const reconnectButton = page.locator('[data-testid="reconnect-button"], button:has-text("Reconnect")');
    if (await reconnectButton.isVisible()) {
      await reconnectButton.click();
      
      // Simulate reconnection
      await page.evaluate(() => {
        window.mockWebSocketState = { connected: true, reconnected: true };
        window.dispatchEvent(new CustomEvent('websocketReconnected'));
      });
      
      const reconnectionSuccess = page.locator('[data-testid="connection-success"], .connection-success');
      if (await reconnectionSuccess.isVisible({ timeout: 5000 })) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/81-websocket-reconnected.png' 
        });
      }
    }
    
    // Test automatic reconnection attempt
    const autoReconnectStatus = page.locator('[data-testid="auto-reconnect-status"], .auto-reconnect');
    if (await autoReconnectStatus.isVisible()) {
      await expect(autoReconnectStatus).toContainText(/attempting|retry|reconnect/i);
    }
  });

  test('should export monitoring data and reports', async () => {
    console.log('📊 Testing monitoring data export functionality...');
    
    await page.goto('/monitoring');
    
    // Mock monitoring data available for export
    await page.evaluate(() => {
      window.mockMonitoringData = {
        sessionId: 'export-test-session',
        duration: 2700, // 45 minutes
        totalFrames: 4050,
        totalDetections: 189,
        exportFormats: ['JSON', 'CSV', 'PDF Report']
      };
      
      window.dispatchEvent(new CustomEvent('dataReadyForExport', {
        detail: window.mockMonitoringData
      }));
    });
    
    const exportTab = page.locator('[data-testid="export-tab"], button:has-text("Export")');
    if (await exportTab.isVisible()) {
      await exportTab.click();
      
      const exportPanel = page.locator('[data-testid="export-panel"], .export-panel');
      if (await exportPanel.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/82-export-panel.png',
          fullPage: true 
        });
        
        // Test different export formats
        const formatSelector = page.locator('[data-testid="export-format"], select[name="format"]');
        if (await formatSelector.isVisible()) {
          const formats = ['JSON', 'CSV', 'PDF Report'];
          
          for (const format of formats) {
            await formatSelector.selectOption(format);
            
            const exportButton = page.locator('[data-testid="export-button"], button:has-text("Export")');
            if (await exportButton.isVisible()) {
              // Listen for download
              const downloadPromise = page.waitForEvent('download', { timeout: 5000 });
              
              await exportButton.click();
              
              try {
                const download = await downloadPromise;
                console.log(`${format} download started:`, download.suggestedFilename());
                
                await page.screenshot({ 
                  path: `./docs/errors/screenshots/83-export-${format.toLowerCase().replace(' ', '-')}.png` 
                });
              } catch (error) {
                console.log(`${format} download timeout:`, error.message);
              }
            }
          }
        }
        
        // Test export options
        const includeCharts = page.locator('[data-testid="include-charts"], input[name="includeCharts"]');
        if (await includeCharts.isVisible()) {
          await includeCharts.check();
        }
        
        const includeRawData = page.locator('[data-testid="include-raw-data"], input[name="includeRawData"]');
        if (await includeRawData.isVisible()) {
          await includeRawData.check();
        }
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/84-export-options.png' 
        });
      }
    }
  });

  test.afterEach(async () => {
    await page.close();
  });
});