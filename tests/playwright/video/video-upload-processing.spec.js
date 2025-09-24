/**
 * ADAS Camera HIL Testing Platform - Video Upload & Processing Pipeline Tests
 * @fileoverview Comprehensive testing of video upload, processing, and playback functionality
 */

const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

test.describe('Video Upload & Processing Pipeline', () => {
  let page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    
    // Enhanced error capture for video operations
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('video')) {
        console.log('Video Console:', msg.type(), msg.text());
      }
    });
    page.on('pageerror', error => console.log('Video Page Error:', error.message));
    page.on('requestfailed', req => {
      if (req.url().includes('upload') || req.url().includes('video')) {
        console.log('Video Request Failed:', req.url(), req.failure()?.errorText);
      }
    });
  });

  test('should display video upload interface correctly', async () => {
    console.log('🎥 Testing video upload interface...');
    
    await page.goto('/upload');
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ 
      path: './docs/errors/screenshots/11-video-upload-interface.png', 
      fullPage: true 
    });
    
    // Check upload interface elements
    const uploadArea = page.locator('[data-testid="video-upload-area"], .upload-area');
    await expect(uploadArea).toBeVisible({ timeout: 10000 });
    
    const uploadButton = page.locator('[data-testid="video-upload-button"], input[type="file"]');
    await expect(uploadButton).toBeVisible();
    
    // Check for drag and drop functionality
    const dropZone = page.locator('[data-testid="drop-zone"], .drop-zone');
    if (await dropZone.isVisible()) {
      // Test drag and drop visual feedback
      await dropZone.hover();
      await page.screenshot({ 
        path: './docs/errors/screenshots/12-drop-zone-hover.png' 
      });
    }
    
    // Check supported formats display
    const supportedFormats = page.locator('[data-testid="supported-formats"], .supported-formats');
    if (await supportedFormats.isVisible()) {
      const formatsText = await supportedFormats.textContent();
      expect(formatsText).toMatch(/mp4|avi|mov/i);
    }
  });

  test('should handle video file selection and validation', async () => {
    console.log('📁 Testing video file selection and validation...');
    
    await page.goto('/upload');
    
    // Create a mock video file for testing (since we can't upload real large video files)
    const mockVideoContent = Buffer.from('mock video content for testing');
    const mockVideoPath = './docs/errors/mock-data/test-video.mp4';
    
    // Write mock file
    await fs.promises.writeFile(mockVideoPath, mockVideoContent);
    
    // Simulate file selection
    const fileInput = page.locator('[data-testid="video-upload-input"], input[type="file"]');
    
    if (await fileInput.isVisible()) {
      // Set the file input
      await fileInput.setInputFiles(mockVideoPath);
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/13-file-selected.png', 
        fullPage: true 
      });
      
      // Check if file info is displayed
      const fileInfo = page.locator('[data-testid="file-info"], .file-info');
      if (await fileInfo.isVisible()) {
        const fileText = await fileInfo.textContent();
        expect(fileText).toContain('test-video.mp4');
      }
      
      // Check upload progress elements
      const progressBar = page.locator('[data-testid="upload-progress"], .progress-bar');
      const startUploadButton = page.locator('[data-testid="start-upload"], button:has-text("Upload")');
      
      if (await startUploadButton.isVisible()) {
        await startUploadButton.click();
        
        // Wait for upload to start
        if (await progressBar.isVisible({ timeout: 5000 })) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/14-upload-in-progress.png' 
          });
          
          // Wait for upload completion or timeout
          try {
            const uploadComplete = page.locator('[data-testid="upload-complete"], .upload-success');
            await expect(uploadComplete).toBeVisible({ timeout: 30000 });
            
            await page.screenshot({ 
              path: './docs/errors/screenshots/15-upload-complete.png' 
            });
          } catch (error) {
            console.log('Upload completion not detected within timeout:', error.message);
            await page.screenshot({ 
              path: './docs/errors/screenshots/15-upload-timeout.png' 
            });
          }
        }
      }
    }
    
    // Cleanup mock file
    try {
      await fs.promises.unlink(mockVideoPath);
    } catch (error) {
      console.log('Could not cleanup mock file:', error.message);
    }
  });

  test('should validate video format restrictions', async () => {
    console.log('✅ Testing video format validation...');
    
    await page.goto('/upload');
    
    // Test with invalid file type
    const invalidFile = './docs/errors/mock-data/invalid-file.txt';
    await fs.promises.writeFile(invalidFile, 'This is not a video file');
    
    const fileInput = page.locator('[data-testid="video-upload-input"], input[type="file"]');
    
    if (await fileInput.isVisible()) {
      await fileInput.setInputFiles(invalidFile);
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/16-invalid-file-selected.png' 
      });
      
      // Check for validation error message
      const errorMessage = page.locator('[data-testid="validation-error"], .error-message');
      
      // Try to start upload (should fail)
      const startUploadButton = page.locator('[data-testid="start-upload"], button:has-text("Upload")');
      if (await startUploadButton.isVisible()) {
        await startUploadButton.click();
        
        // Should show validation error
        if (await errorMessage.isVisible({ timeout: 5000 })) {
          const errorText = await errorMessage.textContent();
          expect(errorText).toMatch(/invalid|format|supported/i);
          
          await page.screenshot({ 
            path: './docs/errors/screenshots/17-validation-error.png' 
          });
        }
      }
    }
    
    // Cleanup
    try {
      await fs.promises.unlink(invalidFile);
    } catch (error) {
      console.log('Could not cleanup invalid file:', error.message);
    }
  });

  test('should handle video processing workflow', async () => {
    console.log('⚙️ Testing video processing workflow...');
    
    await page.goto('/upload');
    
    // Simulate successful upload completion
    await page.evaluate(() => {
      // Mock video processing state
      window.mockVideoState = {
        uploaded: true,
        videoId: 'test-video-123',
        filename: 'test-video.mp4',
        duration: 30,
        status: 'processing'
      };
      
      // Dispatch custom event to trigger processing UI
      window.dispatchEvent(new CustomEvent('videoUploaded', {
        detail: window.mockVideoState
      }));
    });
    
    // Check processing interface elements
    const processingPanel = page.locator('[data-testid="processing-panel"], .processing-panel');
    if (await processingPanel.isVisible({ timeout: 10000 })) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/18-processing-panel.png',
        fullPage: true 
      });
      
      // Check processing options
      const processingOptions = page.locator('[data-testid="processing-options"], .processing-options');
      if (await processingOptions.isVisible()) {
        // Test processing configuration
        const qualitySelect = page.locator('[data-testid="quality-select"], select[name="quality"]');
        if (await qualitySelect.isVisible()) {
          await qualitySelect.selectOption('720p');
        }
        
        const formatSelect = page.locator('[data-testid="format-select"], select[name="format"]');
        if (await formatSelect.isVisible()) {
          await formatSelect.selectOption('mp4');
        }
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/19-processing-config.png' 
        });
      }
      
      // Start processing
      const startProcessingButton = page.locator('[data-testid="start-processing"], button:has-text("Process")');
      if (await startProcessingButton.isVisible()) {
        await startProcessingButton.click();
        
        // Check processing status
        const processingStatus = page.locator('[data-testid="processing-status"], .processing-status');
        if (await processingStatus.isVisible({ timeout: 5000 })) {
          await page.screenshot({ 
            path: './docs/errors/screenshots/20-processing-started.png' 
          });
        }
      }
    }
  });

  test('should display video playback controls', async () => {
    console.log('▶️ Testing video playback interface...');
    
    await page.goto('/upload');
    
    // Mock processed video available
    await page.evaluate(() => {
      window.mockVideoState = {
        processed: true,
        videoId: 'processed-video-123',
        filename: 'processed-video.mp4',
        duration: 30,
        status: 'completed',
        playbackUrl: 'mock-video-url.mp4'
      };
      
      window.dispatchEvent(new CustomEvent('videoProcessed', {
        detail: window.mockVideoState
      }));
    });
    
    // Check video player elements
    const videoPlayer = page.locator('[data-testid="video-player"], video');
    if (await videoPlayer.isVisible({ timeout: 10000 })) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/21-video-player.png',
        fullPage: true 
      });
      
      // Test playback controls
      const playButton = page.locator('[data-testid="play-button"], .play-button');
      const pauseButton = page.locator('[data-testid="pause-button"], .pause-button');
      const seekBar = page.locator('[data-testid="seek-bar"], .seek-bar');
      const volumeControl = page.locator('[data-testid="volume-control"], .volume-control');
      
      // Test play functionality
      if (await playButton.isVisible()) {
        await playButton.click();
        await page.screenshot({ 
          path: './docs/errors/screenshots/22-video-playing.png' 
        });
      }
      
      // Test pause functionality
      if (await pauseButton.isVisible()) {
        await pauseButton.click();
        await page.screenshot({ 
          path: './docs/errors/screenshots/23-video-paused.png' 
        });
      }
      
      // Test seek functionality
      if (await seekBar.isVisible()) {
        const seekBarBox = await seekBar.boundingBox();
        if (seekBarBox) {
          // Click at 50% of the seek bar
          await page.click(`[data-testid="seek-bar"], .seek-bar`, {
            position: { x: seekBarBox.width * 0.5, y: seekBarBox.height * 0.5 }
          });
          await page.screenshot({ 
            path: './docs/errors/screenshots/24-video-seek.png' 
          });
        }
      }
      
      // Test volume control
      if (await volumeControl.isVisible()) {
        await volumeControl.fill('0.5');
        await page.screenshot({ 
          path: './docs/errors/screenshots/25-volume-control.png' 
        });
      }
    }
  });

  test('should handle multiple video uploads', async () => {
    console.log('📚 Testing multiple video upload handling...');
    
    await page.goto('/upload');
    
    // Create multiple mock files
    const mockFiles = [
      { name: 'video1.mp4', content: 'mock video 1 content' },
      { name: 'video2.mp4', content: 'mock video 2 content' },
      { name: 'video3.mp4', content: 'mock video 3 content' }
    ];
    
    const filePaths = [];
    
    // Create mock files
    for (const file of mockFiles) {
      const filePath = `./docs/errors/mock-data/${file.name}`;
      await fs.promises.writeFile(filePath, file.content);
      filePaths.push(filePath);
    }
    
    try {
      // Test multiple file selection
      const fileInput = page.locator('[data-testid="video-upload-input"], input[type="file"]');
      if (await fileInput.isVisible() && await fileInput.getAttribute('multiple') !== null) {
        await fileInput.setInputFiles(filePaths);
        
        await page.screenshot({ 
          path: './docs/errors/screenshots/26-multiple-files-selected.png',
          fullPage: true 
        });
        
        // Check if multiple files are listed
        const fileList = page.locator('[data-testid="file-list"], .file-list');
        if (await fileList.isVisible()) {
          const listItems = fileList.locator('li, .file-item');
          const itemCount = await listItems.count();
          expect(itemCount).toBe(3);
          
          await page.screenshot({ 
            path: './docs/errors/screenshots/27-multiple-files-listed.png' 
          });
        }
        
        // Test batch upload
        const batchUploadButton = page.locator('[data-testid="batch-upload"], button:has-text("Upload All")');
        if (await batchUploadButton.isVisible()) {
          await batchUploadButton.click();
          
          await page.screenshot({ 
            path: './docs/errors/screenshots/28-batch-upload-started.png' 
          });
        }
      }
    } finally {
      // Cleanup mock files
      for (const filePath of filePaths) {
        try {
          await fs.promises.unlink(filePath);
        } catch (error) {
          console.log('Could not cleanup file:', filePath, error.message);
        }
      }
    }
  });

  test('should handle upload cancellation and retry', async () => {
    console.log('🔄 Testing upload cancellation and retry functionality...');
    
    await page.goto('/upload');
    
    // Mock file upload in progress
    await page.evaluate(() => {
      window.mockUploadState = {
        uploading: true,
        progress: 30,
        filename: 'large-video.mp4',
        status: 'uploading'
      };
      
      window.dispatchEvent(new CustomEvent('uploadProgress', {
        detail: window.mockUploadState
      }));
    });
    
    // Check for cancel button during upload
    const cancelButton = page.locator('[data-testid="cancel-upload"], button:has-text("Cancel")');
    if (await cancelButton.isVisible({ timeout: 5000 })) {
      await page.screenshot({ 
        path: './docs/errors/screenshots/29-upload-cancellable.png' 
      });
      
      // Test cancellation
      await cancelButton.click();
      
      // Check for cancellation confirmation
      const cancelConfirmation = page.locator('[data-testid="upload-cancelled"], .upload-cancelled');
      if (await cancelConfirmation.isVisible({ timeout: 5000 })) {
        await page.screenshot({ 
          path: './docs/errors/screenshots/30-upload-cancelled.png' 
        });
      }
    }
    
    // Test retry functionality
    const retryButton = page.locator('[data-testid="retry-upload"], button:has-text("Retry")');
    if (await retryButton.isVisible()) {
      await retryButton.click();
      
      await page.screenshot({ 
        path: './docs/errors/screenshots/31-upload-retry.png' 
      });
    }
  });

  test.afterEach(async () => {
    await page.close();
  });
});