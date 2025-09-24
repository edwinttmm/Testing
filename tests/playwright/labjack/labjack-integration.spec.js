/**
 * ADAS Camera HIL Testing Platform - LabJack Hardware Integration Tests
 * @fileoverview Comprehensive testing of LabJack hardware interface and timing validation
 */

const { test, expect } = require('@playwright/test');

test.describe('LabJack Hardware Integration UI', () => {
  let page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    
    // Enhanced error capture for hardware operations
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('labjack') || msg.text().includes('hardware')) {
        console.log('Hardware Console:', msg.type(), msg.text());
      }
    });
    page.on('pageerror', error => console.log('Hardware Page Error:', error.message));
    page.on('requestfailed', req => {
      if (req.url().includes('labjack') || req.url().includes('hardware') || req.url().includes('signal')) {
        console.log('Hardware Request Failed:', req.url(), req.failure()?.errorText);
      }
    });
  });

  test('should display LabJack hardware status interface', async () => {
    console.log('⚡ Testing LabJack hardware status interface...');
    
    await page.goto('/labjack');
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/85-labjack-interface.png', 
      fullPage: true 
    });
    
    // Check main hardware interface elements
    const hardwarePanel = page.locator('[data-testid="hardware-panel"], .hardware-panel');
    await expect(hardwarePanel).toBeVisible({ timeout: 10000 });
    
    // Check device status display
    const deviceStatus = page.locator('[data-testid="device-status"], .device-status');
    if (await deviceStatus.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/86-device-status.png' 
      });
    }
    
    // Check connection controls
    const connectButton = page.locator('[data-testid="connect-device"], button:has-text("Connect")');
    const disconnectButton = page.locator('[data-testid="disconnect-device"], button:has-text("Disconnect")');
    const scanButton = page.locator('[data-testid="scan-devices"], button:has-text("Scan")');
    
    // At least one control should be visible
    const controlsVisible = await connectButton.isVisible() || 
                           await disconnectButton.isVisible() || 
                           await scanButton.isVisible();
    expect(controlsVisible).toBe(true);
  });

  test('should handle device scanning and detection', async () => {
    console.log('🔍 Testing LabJack device scanning and detection...');
    
    await page.goto('/labjack');
    
    const scanButton = page.locator('[data-testid="scan-devices"], button:has-text("Scan")');
    if (await scanButton.isVisible()) {
      await scanButton.click();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/87-device-scan-started.png' 
      });
      
      // Mock device scan results
      await page.evaluate(() => {
        window.mockDeviceResults = {
          devices: [
            {
              id: 'T7-001',
              name: 'LabJack T7',
              serialNumber: '470028123',
              connectionType: 'USB',
              status: 'available',
              firmwareVersion: '1.0.25'
            },
            {
              id: 'T4-001',
              name: 'LabJack T4',
              serialNumber: '480015456',
              connectionType: 'Ethernet',
              status: 'connected',
              firmwareVersion: '1.0.12',
              ipAddress: '192.168.1.100'
            }
          ]
        };
        
        window.dispatchEvent(new CustomEvent('devicesFound', {
          detail: window.mockDeviceResults
        }));
      });
      
      // Check device list
      const deviceList = page.locator('[data-testid="device-list"], .device-list');
      if (await deviceList.isVisible({ timeout: 10000 })) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/88-devices-found.png',
          fullPage: true 
        });
        
        // Check individual device entries
        const deviceItems = deviceList.locator('[data-testid*="device-item"], .device-item');
        const deviceCount = await deviceItems.count();
        expect(deviceCount).toBeGreaterThanOrEqual(1);
        
        // Test device selection
        const firstDevice = deviceItems.first();
        await firstDevice.click();
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/89-device-selected.png' 
        });
      }
    }
  });

  test('should handle device connection and disconnection', async () => {
    console.log('🔌 Testing LabJack device connection workflow...');
    
    await page.goto('/labjack');
    
    // Mock device available for connection
    await page.evaluate(() => {
      window.mockSelectedDevice = {
        id: 'T7-001',
        name: 'LabJack T7',
        serialNumber: '470028123',
        status: 'available'
      };
      
      window.dispatchEvent(new CustomEvent('deviceSelected', {
        detail: window.mockSelectedDevice
      }));
    });
    
    const connectButton = page.locator('[data-testid="connect-device"], button:has-text("Connect")');
    if (await connectButton.isVisible({ timeout: 5000 })) {
      await connectButton.click();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/90-connection-attempt.png' 
      });
      
      // Mock successful connection
      await page.evaluate(() => {
        window.mockConnectionResult = {
          success: true,
          device: {
            ...window.mockSelectedDevice,
            status: 'connected',
            connectionTime: new Date().toISOString()
          }
        };
        
        window.dispatchEvent(new CustomEvent('deviceConnected', {
          detail: window.mockConnectionResult
        }));
      });
      
      // Check connection success indicator
      const connectionSuccess = page.locator('[data-testid="connection-success"], .connection-success');
      if (await connectionSuccess.isVisible({ timeout: 10000 })) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/91-device-connected.png',
          fullPage: true 
        });
      }
      
      // Check that disconnect button becomes available
      const disconnectButton = page.locator('[data-testid="disconnect-device"], button:has-text("Disconnect")');
      if (await disconnectButton.isVisible()) {
        await disconnectButton.click();
        
        // Mock disconnection
        await page.evaluate(() => {
          window.dispatchEvent(new CustomEvent('deviceDisconnected', {
            detail: { device: window.mockSelectedDevice }
          }));
        });
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/92-device-disconnected.png' 
        });
      }
    }
  });

  test('should configure channel settings and I/O parameters', async () => {
    console.log('⚙️ Testing LabJack channel configuration...');
    
    await page.goto('/labjack');
    
    // Mock connected device
    await page.evaluate(() => {
      window.mockConnectedDevice = {
        id: 'T7-001',
        status: 'connected',
        channels: {
          analog: ['AIN0', 'AIN1', 'AIN2', 'AIN3'],
          digital: ['DIO0', 'DIO1', 'DIO2', 'DIO3'],
          timer: ['CIO0', 'CIO1']
        }
      };
      
      window.dispatchEvent(new CustomEvent('deviceReady', {
        detail: window.mockConnectedDevice
      }));
    });
    
    // Navigate to configuration tab
    const configTab = page.locator('[data-testid="config-tab"], button:has-text("Configuration")');
    if (await configTab.isVisible()) {
      await configTab.click();
      
      const configPanel = page.locator('[data-testid="config-panel"], .config-panel');
      if (await configPanel.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/93-channel-config.png',
          fullPage: true 
        });
        
        // Configure analog input channels
        const analogSection = page.locator('[data-testid="analog-config"], .analog-config');
        if (await analogSection.isVisible()) {
          // Configure AIN0 for voltage measurement
          const ain0Config = page.locator('[data-testid="ain0-config"]');
          if (await ain0Config.isVisible()) {
            const ain0Type = ain0Config.locator('select[name="type"]');
            if (await ain0Type.isVisible()) {
              await ain0Type.selectOption('voltage');
            }
            
            const ain0Range = ain0Config.locator('select[name="range"]');
            if (await ain0Range.isVisible()) {
              await ain0Range.selectOption('±10V');
            }
            
            const ain0Resolution = ain0Config.locator('select[name="resolution"]');
            if (await ain0Resolution.isVisible()) {
              await ain0Resolution.selectOption('12-bit');
            }
          }
          
          await page.screenshot({ 
            path: './docs/errors/screenshots/94-analog-config.png' 
          });
        }
        
        // Configure digital I/O channels
        const digitalSection = page.locator('[data-testid="digital-config"], .digital-config');
        if (await digitalSection.isVisible()) {
          // Configure DIO0 as output
          const dio0Config = page.locator('[data-testid="dio0-config"]');
          if (await dio0Config.isVisible()) {
            const dio0Direction = dio0Config.locator('select[name="direction"]');
            if (await dio0Direction.isVisible()) {
              await dio0Direction.selectOption('output');
            }
            
            const dio0Initial = dio0Config.locator('select[name="initialState"]');
            if (await dio0Initial.isVisible()) {
              await dio0Initial.selectOption('low');
            }
          }
          
          await page.screenshot({ 
            path: './docs/errors/screenshots/95-digital-config.png' 
          });
        }
        
        // Apply configuration
        const applyConfigButton = page.locator('[data-testid="apply-config"], button:has-text("Apply")');
        if (await applyConfigButton.isVisible()) {
          await applyConfigButton.click();
          
          const configApplied = page.locator('[data-testid="config-applied"], .config-success');
          if (await configApplied.isVisible({ timeout: 5000 })) {
            await page.screenshot({ 
              path: './docs/errors/screenshots/96-config-applied.png' 
            });
          }
        }
      }
    }
  });

  test('should monitor real-time signal data', async () => {
    console.log('📊 Testing real-time signal monitoring...');
    
    await page.goto('/labjack');
    
    // Mock active monitoring session
    await page.evaluate(() => {
      window.mockSignalData = {
        channels: {
          AIN0: { value: 3.14, unit: 'V', timestamp: Date.now() },
          AIN1: { value: 1.85, unit: 'V', timestamp: Date.now() },
          DIO0: { value: 1, unit: 'digital', timestamp: Date.now() },
          DIO1: { value: 0, unit: 'digital', timestamp: Date.now() }
        },
        sampleRate: 1000, // Hz
        isMonitoring: true
      };
      
      window.dispatchEvent(new CustomEvent('signalDataUpdate', {
        detail: window.mockSignalData
      }));
    });
    
    const monitoringTab = page.locator('[data-testid="monitoring-tab"], button:has-text("Monitoring")');
    if (await monitoringTab.isVisible()) {
      await monitoringTab.click();
      
      const monitoringPanel = page.locator('[data-testid="monitoring-panel"], .monitoring-panel');
      if (await monitoringPanel.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/97-signal-monitoring.png',
          fullPage: true 
        });
        
        // Check real-time value displays
        const ain0Value = page.locator('[data-testid="ain0-value"], .channel-value');
        if (await ain0Value.isVisible()) {
          await expect(ain0Value).toContainText('3.14');
        }
        
        const ain1Value = page.locator('[data-testid="ain1-value"], .channel-value');
        if (await ain1Value.isVisible()) {
          await expect(ain1Value).toContainText('1.85');
        }
        
        // Check signal charts
        const signalChart = page.locator('[data-testid="signal-chart"], .signal-chart');
        if (await signalChart.isVisible()) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/98-signal-charts.png' 
          });
        }
        
        // Test monitoring controls
        const startMonitoringButton = page.locator('[data-testid="start-monitoring"], button:has-text("Start")');
        const stopMonitoringButton = page.locator('[data-testid="stop-monitoring"], button:has-text("Stop")');
        
        if (await stopMonitoringButton.isVisible()) {
          await stopMonitoringButton.click();
          await page.screenshot({ 
            path: './docs/errors/screenshots/99-monitoring-stopped.png' 
          });
        }
        
        if (await startMonitoringButton.isVisible()) {
          await startMonitoringButton.click();
          await page.screenshot({ 
            path: './docs/errors/screenshots/100-monitoring-started.png' 
          });
        }
      }
    }
  });

  test('should validate timing precision and synchronization', async () => {
    console.log('⏱️ Testing timing precision validation...');
    
    await page.goto('/labjack');
    
    // Mock timing validation session
    await page.evaluate(() => {
      window.mockTimingData = {
        testResults: {
          averageLatency: 0.245, // ms
          jitter: 0.012, // ms
          maxLatency: 0.310, // ms
          minLatency: 0.201, // ms
          samplesCount: 10000,
          targetFrequency: 1000, // Hz
          actualFrequency: 999.87, // Hz
          accuracy: 99.987, // %
          precision: 'sub-millisecond'
        },
        thresholds: {
          maxLatency: 1.0, // ms
          maxJitter: 0.1, // ms
          minAccuracy: 99.0 // %
        },
        status: 'passed'
      };
      
      window.dispatchEvent(new CustomEvent('timingValidation', {
        detail: window.mockTimingData
      }));
    });
    
    const timingTab = page.locator('[data-testid="timing-tab"], button:has-text("Timing")');
    if (await timingTab.isVisible()) {
      await timingTab.click();
      
      const timingPanel = page.locator('[data-testid="timing-panel"], .timing-panel');
      if (await timingPanel.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/101-timing-validation.png',
          fullPage: true 
        });
        
        // Check timing metrics display
        const latencyDisplay = page.locator('[data-testid="average-latency"], .latency-value');
        if (await latencyDisplay.isVisible()) {
          await expect(latencyDisplay).toContainText('0.245');
        }
        
        const jitterDisplay = page.locator('[data-testid="jitter-value"], .jitter-value');
        if (await jitterDisplay.isVisible()) {
          await expect(jitterDisplay).toContainText('0.012');
        }
        
        const accuracyDisplay = page.locator('[data-testid="accuracy-value"], .accuracy-value');
        if (await accuracyDisplay.isVisible()) {
          await expect(accuracyDisplay).toContainText('99.987');
        }
        
        // Check timing validation status
        const validationStatus = page.locator('[data-testid="timing-status"], .validation-status');
        if (await validationStatus.isVisible()) {
          const statusText = await validationStatus.textContent();
          expect(statusText).toMatch(/passed|success|valid/i);
          
          await page.screenshot({ 
            path: './docs/errors/screenshots/102-timing-status.png' 
          });
        }
        
        // Check timing charts
        const timingChart = page.locator('[data-testid="timing-chart"], .timing-chart');
        if (await timingChart.isVisible()) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/103-timing-charts.png' 
          });
        }
        
        // Test timing validation controls
        const runTimingTestButton = page.locator('[data-testid="run-timing-test"], button:has-text("Run Test")');
        if (await runTimingTestButton.isVisible()) {
          await runTimingTestButton.click();
          
          const testInProgress = page.locator('[data-testid="test-in-progress"], .test-progress');
          if (await testInProgress.isVisible({ timeout: 5000 })) {
            await page.screenshot({ 
              path: './docs/errors/screenshots/104-timing-test-running.png' 
            });
          }
        }
      }
    }
  });

  test('should handle HIL test scenario integration', async () => {
    console.log('🚗 Testing HIL test scenario integration...');
    
    await page.goto('/labjack');
    
    // Mock HIL scenario setup
    await page.evaluate(() => {
      window.mockHILScenario = {
        name: 'Urban Intersection Scenario',
        description: 'Vehicle approaching controlled intersection with pedestrian crossing',
        signals: {
          vehicleSpeed: { channel: 'AIN0', unit: 'km/h', value: 45 },
          brakePressed: { channel: 'DIO0', unit: 'boolean', value: false },
          pedestrianDetected: { channel: 'DIO1', unit: 'boolean', value: true },
          trafficLightState: { channel: 'AIN1', unit: 'V', value: 2.5 } // Green = 2.5V
        },
        expectedBehavior: {
          detectionTime: { max: 500, unit: 'ms' },
          brakeResponse: { max: 800, unit: 'ms' },
          decelerationRate: { min: 3.0, unit: 'm/s²' }
        },
        status: 'ready'
      };
      
      window.dispatchEvent(new CustomEvent('hilScenarioLoaded', {
        detail: window.mockHILScenario
      }));
    });
    
    const hilTab = page.locator('[data-testid="hil-tab"], button:has-text("HIL Testing")');
    if (await hilTab.isVisible()) {
      await hilTab.click();
      
      const hilPanel = page.locator('[data-testid="hil-panel"], .hil-panel');
      if (await hilPanel.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/105-hil-scenario.png',
          fullPage: true 
        });
        
        // Check scenario details
        const scenarioName = page.locator('[data-testid="scenario-name"], .scenario-name');
        if (await scenarioName.isVisible()) {
          await expect(scenarioName).toContainText('Urban Intersection');
        }
        
        // Check signal mapping
        const signalMapping = page.locator('[data-testid="signal-mapping"], .signal-mapping');
        if (await signalMapping.isVisible()) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/106-signal-mapping.png' 
          });
        }
        
        // Check expected behavior criteria
        const behaviorCriteria = page.locator('[data-testid="behavior-criteria"], .behavior-criteria');
        if (await behaviorCriteria.isVisible()) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/107-behavior-criteria.png' 
          });
        }
        
        // Start HIL test execution
        const runHILTestButton = page.locator('[data-testid="run-hil-test"], button:has-text("Run HIL Test")');
        if (await runHILTestButton.isVisible()) {
          await runHILTestButton.click();
          
          // Mock test execution
          await page.evaluate(() => {
            window.mockHILResults = {
              testStarted: true,
              currentPhase: 'signal_injection',
              progress: 25,
              results: {
                detectionTime: 342, // ms
                brakeResponse: 687, // ms
                status: 'running'
              }
            };
            
            window.dispatchEvent(new CustomEvent('hilTestUpdate', {
              detail: window.mockHILResults
            }));
          });
          
          const testProgress = page.locator('[data-testid="hil-test-progress"], .test-progress');
          if (await testProgress.isVisible({ timeout: 5000 })) {
            await page.screenshot({ 
              path: './docs/errors/screenshots/108-hil-test-running.png',
              fullPage: true 
            });
          }
        }
      }
    }
  });

  test('should display hardware diagnostics and health status', async () => {
    console.log('🏥 Testing hardware diagnostics and health monitoring...');
    
    await page.goto('/labjack');
    
    // Mock hardware diagnostics data
    await page.evaluate(() => {
      window.mockDiagnostics = {
        deviceHealth: {
          temperature: 42.3, // °C
          voltage: 5.02, // V
          current: 0.245, // A
          uptime: 147623, // seconds
          errorCount: 0,
          warningCount: 2,
          status: 'healthy'
        },
        channelHealth: {
          AIN0: { status: 'ok', noise: 0.002, drift: 0.001 },
          AIN1: { status: 'ok', noise: 0.003, drift: 0.001 },
          DIO0: { status: 'ok', switchCount: 1247 },
          DIO1: { status: 'warning', switchCount: 0, lastActivity: null }
        },
        calibration: {
          lastCalibration: '2024-01-10T14:30:00Z',
          nextDue: '2024-04-10T14:30:00Z',
          status: 'current'
        }
      };
      
      window.dispatchEvent(new CustomEvent('diagnosticsUpdate', {
        detail: window.mockDiagnostics
      }));
    });
    
    const diagnosticsTab = page.locator('[data-testid="diagnostics-tab"], button:has-text("Diagnostics")');
    if (await diagnosticsTab.isVisible()) {
      await diagnosticsTab.click();
      
      const diagnosticsPanel = page.locator('[data-testid="diagnostics-panel"], .diagnostics-panel');
      if (await diagnosticsPanel.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/109-hardware-diagnostics.png',
          fullPage: true 
        });
        
        // Check device health metrics
        const temperatureDisplay = page.locator('[data-testid="device-temperature"], .temperature-value');
        if (await temperatureDisplay.isVisible()) {
          await expect(temperatureDisplay).toContainText('42.3');
        }
        
        const voltageDisplay = page.locator('[data-testid="device-voltage"], .voltage-value');
        if (await voltageDisplay.isVisible()) {
          await expect(voltageDisplay).toContainText('5.02');
        }
        
        // Check health status indicator
        const healthStatus = page.locator('[data-testid="health-status"], .health-status');
        if (await healthStatus.isVisible()) {
          const statusText = await healthStatus.textContent();
          expect(statusText).toMatch(/healthy|ok|normal/i);
        }
        
        // Check channel health
        const channelHealthSection = page.locator('[data-testid="channel-health"], .channel-health');
        if (await channelHealthSection.isVisible()) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/110-channel-health.png' 
          });
          
          // Check for warning indicators
          const warningIndicators = channelHealthSection.locator('.warning, [data-status="warning"]');
          const warningCount = await warningIndicators.count();
          expect(warningCount).toBeGreaterThan(0); // Should have DIO1 warning
        }
        
        // Check calibration status
        const calibrationSection = page.locator('[data-testid="calibration-status"], .calibration-status');
        if (await calibrationSection.isVisible()) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/111-calibration-status.png' 
          });
        }
        
        // Test diagnostic export
        const exportDiagnosticsButton = page.locator('[data-testid="export-diagnostics"], button:has-text("Export")');
        if (await exportDiagnosticsButton.isVisible()) {
          // Listen for download
          const downloadPromise = page.waitForEvent('download', { timeout: 5000 });
          
          await exportDiagnosticsButton.click();
          
          try {
            const download = await downloadPromise;
            console.log('Diagnostics export started:', download.suggestedFilename());
            
            await page.screenshot({ 
              path: './docs/errors/screenshots/112-diagnostics-export.png' 
            });
          } catch (error) {
            console.log('Diagnostics export timeout:', error.message);
          }
        }
      }
    }
  });

  test.afterEach(async () => {
    await page.close();
  });
});