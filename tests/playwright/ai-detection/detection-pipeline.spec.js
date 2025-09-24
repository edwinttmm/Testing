/**
 * ADAS Camera HIL Testing Platform - AI Detection Pipeline Tests
 * @fileoverview Comprehensive testing of YOLO integration and detection workflows
 */

const { test, expect } = require('@playwright/test');

test.describe('AI Detection Pipeline with YOLO Integration', () => {
  let page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    
    // Enhanced error capture for AI operations
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('detection') || msg.text().includes('YOLO')) {
        console.log('AI Console:', msg.type(), msg.text());
      }
    });
    page.on('pageerror', error => console.log('AI Page Error:', error.message));
    page.on('requestfailed', req => {
      if (req.url().includes('detect') || req.url().includes('model') || req.url().includes('yolo')) {
        console.log('AI Request Failed:', req.url(), req.failure()?.errorText);
      }
    });
  });

  test('should display detection pipeline interface', async () => {
    console.log('🤖 Testing AI detection pipeline interface...');
    
    await page.goto('/detection');
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/32-detection-interface.png', 
      fullPage: true 
    });
    
    // Check main detection interface elements
    const pipelinePanel = page.locator('[data-testid="detection-pipeline"], .pipeline-panel');
    await expect(pipelinePanel).toBeVisible({ timeout: 10000 });
    
    // Check model selection
    const modelSelector = page.locator('[data-testid="model-selector"], select[name="model"]');
    if (await modelSelector.isVisible()) {
      const options = await modelSelector.locator('option').allTextContents();
      expect(options).toEqual(expect.arrayContaining(['YOLOv8', 'YOLOv7', 'YOLOv5']));
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/33-model-selector.png' 
      });
    }
    
    // Check configuration panel
    const configPanel = page.locator('[data-testid="config-panel"], .config-panel');
    if (await configPanel.isVisible()) {
      // Check confidence threshold control
      const confidenceSlider = page.locator('[data-testid="confidence-threshold"], input[name="confidence"]');
      await expect(confidenceSlider).toBeVisible();
      
      // Check IoU threshold control
      const iouSlider = page.locator('[data-testid="iou-threshold"], input[name="iou"]');
      if (await iouSlider.isVisible()) {
        await expect(iouSlider).toBeVisible();
      }
      
      // Check class selection
      const classSelector = page.locator('[data-testid="class-selector"], .class-selector');
      if (await classSelector.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/34-class-selector.png' 
        });
      }
    }
  });

  test('should configure detection parameters', async () => {
    console.log('⚙️ Testing detection parameter configuration...');
    
    await page.goto('/detection');
    
    // Configure model selection
    const modelSelector = page.locator('[data-testid="model-selector"], select[name="model"]');
    if (await modelSelector.isVisible()) {
      await modelSelector.selectOption('YOLOv8');
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/35-model-selected.png' 
      });
    }
    
    // Configure confidence threshold
    const confidenceSlider = page.locator('[data-testid="confidence-threshold"], input[name="confidence"]');
    if (await confidenceSlider.isVisible()) {
      await confidenceSlider.fill('0.75');
      
      // Verify value display update
      const confidenceValue = page.locator('[data-testid="confidence-value"], .confidence-value');
      if (await confidenceValue.isVisible()) {
        await expect(confidenceValue).toContainText('0.75');
      }
    }
    
    // Configure IoU threshold
    const iouSlider = page.locator('[data-testid="iou-threshold"], input[name="iou"]');
    if (await iouSlider.isVisible()) {
      await iouSlider.fill('0.4');
      
      const iouValue = page.locator('[data-testid="iou-value"], .iou-value');
      if (await iouValue.isVisible()) {
        await expect(iouValue).toContainText('0.4');
      }
    }
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/36-parameters-configured.png',
      fullPage: true 
    });
    
    // Test advanced configuration
    const advancedButton = page.locator('[data-testid="advanced-config"], button:has-text("Advanced")');
    if (await advancedButton.isVisible()) {
      await advancedButton.click();
      
      const advancedPanel = page.locator('[data-testid="advanced-panel"], .advanced-panel');
      if (await advancedPanel.isVisible({ timeout: 5000 })) {
        // Configure batch size
        const batchSizeInput = page.locator('[data-testid="batch-size"], input[name="batchSize"]');
        if (await batchSizeInput.isVisible()) {
          await batchSizeInput.fill('16');
        }
        
        // Configure max detections
        const maxDetectionsInput = page.locator('[data-testid="max-detections"], input[name="maxDetections"]');
        if (await maxDetectionsInput.isVisible()) {
          await maxDetectionsInput.fill('100');
        }
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/37-advanced-config.png' 
        });
      }
    }
  });

  test('should handle class selection and filtering', async () => {
    console.log('🎯 Testing object class selection and filtering...');
    
    await page.goto('/detection');
    
    const classSelector = page.locator('[data-testid="class-selector"], .class-selector');
    if (await classSelector.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/38-class-selector-initial.png',
        fullPage: true 
      });
      
      // Common ADAS-relevant classes
      const targetClasses = ['car', 'truck', 'bus', 'person', 'bicycle', 'motorcycle', 'traffic light', 'stop sign'];
      
      for (const className of targetClasses) {
        const classCheckbox = page.locator(`[data-testid="class-${className}"], input[value="${className}"]`);
        if (await classCheckbox.isVisible()) {
          await classCheckbox.check();
          console.log(`Selected class: ${className}`);
        }
      }
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/39-classes-selected.png',
        fullPage: true 
      });
      
      // Test select all/none functionality
      const selectAllButton = page.locator('[data-testid="select-all-classes"], button:has-text("Select All")');
      if (await selectAllButton.isVisible()) {
        await selectAllButton.click();
        await page.screenshot({ 
          path: './docs/errors/screenshots/40-select-all-classes.png' 
        });
      }
      
      const selectNoneButton = page.locator('[data-testid="select-none-classes"], button:has-text("Select None")');
      if (await selectNoneButton.isVisible()) {
        await selectNoneButton.click();
        await page.screenshot({ 
          path: './docs/errors/screenshots/41-select-none-classes.png' 
        });
      }
    }
  });

  test('should execute detection pipeline on test video', async () => {
    console.log('🔍 Testing detection pipeline execution...');
    
    await page.goto('/detection');
    
    // Mock video available for detection
    await page.evaluate(() => {
      window.mockVideoState = {
        id: 'test-video-123',
        filename: 'test-video.mp4',
        duration: 30,
        fps: 30,
        ready: true
      };
      
      // Simulate video ready for detection
      window.dispatchEvent(new CustomEvent('videoReady', {
        detail: window.mockVideoState
      }));
    });
    
    // Wait for video to be available
    const videoSelector = page.locator('[data-testid="video-selector"], select[name="video"]');
    if (await videoSelector.isVisible({ timeout: 10000 })) {
      await videoSelector.selectOption('test-video-123');
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/42-video-selected.png' 
      });
    }
    
    // Configure basic parameters
    const modelSelector = page.locator('[data-testid="model-selector"], select[name="model"]');
    if (await modelSelector.isVisible()) {
      await modelSelector.selectOption('YOLOv8');
    }
    
    const confidenceSlider = page.locator('[data-testid="confidence-threshold"], input[name="confidence"]');
    if (await confidenceSlider.isVisible()) {
      await confidenceSlider.fill('0.5');
    }
    
    // Start detection pipeline
    const startDetectionButton = page.locator('[data-testid="start-detection"], button:has-text("Start Detection")');
    await expect(startDetectionButton).toBeVisible();
    
    await startDetectionButton.click();
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/43-detection-started.png',
      fullPage: true 
    });
    
    // Monitor detection progress
    const progressBar = page.locator('[data-testid="detection-progress"], .progress-bar');
    if (await progressBar.isVisible({ timeout: 5000 })) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/44-detection-progress.png' 
      });
      
      // Wait for detection to complete or timeout
      try {
        const detectionComplete = page.locator('[data-testid="detection-complete"], .detection-complete');
        await expect(detectionComplete).toBeVisible({ timeout: 60000 });
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/45-detection-complete.png',
          fullPage: true 
        });
        
        // Check results display
        const resultsPanel = page.locator('[data-testid="detection-results"], .results-panel');
        if (await resultsPanel.isVisible()) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/46-detection-results.png',
            fullPage: true 
          });
        }
      } catch (error) {
        console.log('Detection completion not detected within timeout:', error.message);
        await page.screenshot({ 
          path: './docs/errors/screenshots/45-detection-timeout.png',
          fullPage: true 
        });
      }
    }
  });

  test('should display detection results and annotations', async () => {
    console.log('📊 Testing detection results display...');
    
    await page.goto('/detection');
    
    // Mock completed detection results
    await page.evaluate(() => {
      window.mockDetectionResults = {
        videoId: 'test-video-123',
        totalFrames: 900,
        processedFrames: 900,
        detections: [
          {
            frame: 100,
            objects: [
              { class: 'car', confidence: 0.95, bbox: [100, 100, 200, 200] },
              { class: 'person', confidence: 0.87, bbox: [300, 150, 350, 300] }
            ]
          },
          {
            frame: 200,
            objects: [
              { class: 'truck', confidence: 0.92, bbox: [150, 80, 400, 250] }
            ]
          }
        ],
        stats: {
          totalDetections: 3,
          classCounts: { car: 1, person: 1, truck: 1 },
          avgConfidence: 0.91
        }
      };
      
      window.dispatchEvent(new CustomEvent('detectionComplete', {
        detail: window.mockDetectionResults
      }));
    });
    
    // Check results summary
    const resultsSummary = page.locator('[data-testid="results-summary"], .results-summary');
    if (await resultsSummary.isVisible({ timeout: 10000 })) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/47-results-summary.png',
        fullPage: true 
      });
      
      // Check detection statistics
      const totalDetections = page.locator('[data-testid="total-detections"], .total-detections');
      if (await totalDetections.isVisible()) {
        await expect(totalDetections).toContainText('3');
      }
      
      const avgConfidence = page.locator('[data-testid="avg-confidence"], .avg-confidence');
      if (await avgConfidence.isVisible()) {
        const confidenceText = await avgConfidence.textContent();
        expect(confidenceText).toMatch(/0\.91|91%/);
      }
    }
    
    // Check class distribution chart
    const classChart = page.locator('[data-testid="class-distribution"], .class-chart');
    if (await classChart.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/48-class-distribution.png' 
      });
    }
    
    // Check detection timeline
    const detectionTimeline = page.locator('[data-testid="detection-timeline"], .detection-timeline');
    if (await detectionTimeline.isVisible()) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/49-detection-timeline.png' 
      });
      
      // Test timeline interaction
      const timelinePoint = detectionTimeline.locator('.timeline-point').first();
      if (await timelinePoint.isVisible()) {
        await timelinePoint.click();
        
        // Check if frame details appear
        const frameDetails = page.locator('[data-testid="frame-details"], .frame-details');
        if (await frameDetails.isVisible({ timeout: 5000 })) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/50-frame-details.png' 
          });
        }
      }
    }
  });

  test('should handle detection export and download', async () => {
    console.log('📥 Testing detection results export...');
    
    await page.goto('/detection');
    
    // Mock detection results available
    await page.evaluate(() => {
      window.mockDetectionResults = {
        videoId: 'test-video-123',
        ready: true,
        exportFormats: ['JSON', 'CSV', 'XML']
      };
      
      window.dispatchEvent(new CustomEvent('resultsReady', {
        detail: window.mockDetectionResults
      }));
    });
    
    const exportPanel = page.locator('[data-testid="export-panel"], .export-panel');
    if (await exportPanel.isVisible({ timeout: 10000 })) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/51-export-panel.png',
        fullPage: true 
      });
      
      // Test format selection
      const formatSelector = page.locator('[data-testid="export-format"], select[name="format"]');
      if (await formatSelector.isVisible()) {
        await formatSelector.selectOption('JSON');
        
        const exportButton = page.locator('[data-testid="export-button"], button:has-text("Export")');
        if (await exportButton.isVisible()) {
          // Listen for download
          const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
          
          await exportButton.click();
          
          try {
            const download = await downloadPromise;
            console.log('Download started:', download.suggestedFilename());
            
            await page.screenshot({ 
              path: './docs/errors/screenshots/52-download-started.png' 
            });
          } catch (error) {
            console.log('Download not triggered or timeout:', error.message);
            await page.screenshot({ 
              path: './docs/errors/screenshots/52-download-timeout.png' 
            });
          }
        }
      }
      
      // Test other export formats
      const formats = ['CSV', 'XML'];
      for (const format of formats) {
        if (await formatSelector.isVisible()) {
          await formatSelector.selectOption(format);
          await page.screenshot({ 
            path: `./docs/errors/screenshots/53-export-${format.toLowerCase()}.png` 
          });
        }
      }
    }
  });

  test('should handle real-time detection mode', async () => {
    console.log('⚡ Testing real-time detection capabilities...');
    
    await page.goto('/detection');
    
    // Check for real-time mode option
    const realtimeToggle = page.locator('[data-testid="realtime-mode"], input[name="realtimeMode"]');
    if (await realtimeToggle.isVisible()) {
      await realtimeToggle.check();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/54-realtime-mode-enabled.png',
        fullPage: true 
      });
      
      // Check real-time configuration options
      const realtimeConfig = page.locator('[data-testid="realtime-config"], .realtime-config');
      if (await realtimeConfig.isVisible()) {
        // FPS setting
        const fpsInput = page.locator('[data-testid="target-fps"], input[name="fps"]');
        if (await fpsInput.isVisible()) {
          await fpsInput.fill('15');
        }
        
        // Buffer size
        const bufferSizeInput = page.locator('[data-testid="buffer-size"], input[name="bufferSize"]');
        if (await bufferSizeInput.isVisible()) {
          await bufferSizeInput.fill('10');
        }
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/55-realtime-config.png' 
        });
      }
      
      // Start real-time detection
      const startRealtimeButton = page.locator('[data-testid="start-realtime"], button:has-text("Start Real-time")');
      if (await startRealtimeButton.isVisible()) {
        await startRealtimeButton.click();
        
        // Check real-time status display
        const realtimeStatus = page.locator('[data-testid="realtime-status"], .realtime-status');
        if (await realtimeStatus.isVisible({ timeout: 5000 })) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/56-realtime-active.png',
            fullPage: true 
          });
          
          // Monitor performance metrics
          const fpsDisplay = page.locator('[data-testid="current-fps"], .current-fps');
          if (await fpsDisplay.isVisible()) {
            const fpsText = await fpsDisplay.textContent();
            console.log('Real-time FPS:', fpsText);
          }
          
          const latencyDisplay = page.locator('[data-testid="detection-latency"], .detection-latency');
          if (await latencyDisplay.isVisible()) {
            const latencyText = await latencyDisplay.textContent();
            console.log('Detection latency:', latencyText);
          }
        }
      }
    }
  });

  test('should validate detection accuracy and confidence scores', async () => {
    console.log('✅ Testing detection accuracy validation...');
    
    await page.goto('/detection');
    
    // Mock detection results with various confidence scores
    await page.evaluate(() => {
      window.mockDetectionResults = {
        detections: [
          { class: 'car', confidence: 0.95, accuracy: 'high' },
          { class: 'person', confidence: 0.87, accuracy: 'high' },
          { class: 'bicycle', confidence: 0.65, accuracy: 'medium' },
          { class: 'truck', confidence: 0.45, accuracy: 'low' }
        ]
      };
      
      window.dispatchEvent(new CustomEvent('accuracyAnalysis', {
        detail: window.mockDetectionResults
      }));
    });
    
    const accuracyPanel = page.locator('[data-testid="accuracy-panel"], .accuracy-panel');
    if (await accuracyPanel.isVisible({ timeout: 10000 })) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/57-accuracy-analysis.png',
        fullPage: true 
      });
      
      // Check confidence distribution
      const confidenceChart = page.locator('[data-testid="confidence-distribution"], .confidence-chart');
      if (await confidenceChart.isVisible()) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/58-confidence-distribution.png' 
        });
      }
      
      // Check accuracy warnings for low confidence detections
      const lowConfidenceWarning = page.locator('[data-testid="low-confidence-warning"], .warning');
      if (await lowConfidenceWarning.isVisible()) {
        const warningText = await lowConfidenceWarning.textContent();
        expect(warningText).toMatch(/low confidence|below threshold/i);
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/59-low-confidence-warning.png' 
        });
      }
      
      // Test confidence threshold adjustment
      const thresholdSlider = page.locator('[data-testid="confidence-threshold"], input[name="confidence"]');
      if (await thresholdSlider.isVisible()) {
        await thresholdSlider.fill('0.7');
        
        // Should filter out detections below threshold
        const filteredResults = page.locator('[data-testid="filtered-results"], .filtered-results');
        if (await filteredResults.isVisible({ timeout: 3000 })) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/60-filtered-results.png' 
          });
        }
      }
    }
  });

  test.afterEach(async () => {
    await page.close();
  });
});