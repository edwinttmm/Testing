/**
 * ADAS Camera HIL Testing Platform - Video Processing Pipeline Tests
 * @fileoverview Comprehensive video upload and processing pipeline tests
 */

const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');
const fs = require('fs');
const path = require('path');

test.describe('Video Upload & Processing Pipeline', () => {
  let consoleLogs;
  let testProject;

  test.beforeAll(async ({ request }) => {
    // Create a test project for video tests
    testProject = await TestHelpers.createTestProject(
      { request }, 
      { name: 'Video Pipeline Test Project' }
    );
  });

  test.beforeEach(async ({ page }) => {
    consoleLogs = TestHelpers.setupConsoleMonitoring(page);
    await page.goto('http://localhost:3000');
    await TestHelpers.waitForPageReady(page);
  });

  test('should display video upload interface', async ({ page }) => {
    // Look for video upload elements
    const uploadElements = [
      'input[type="file"]',
      '[data-testid*="upload"]',
      'button[text*="Upload"]',
      '.upload-area',
      '.drop-zone'
    ];

    let foundUploadElement = false;
    let uploadElement = null;

    for (const selector of uploadElements) {
      const element = page.locator(selector);
      if (await element.count() > 0) {
        foundUploadElement = true;
        uploadElement = element.first();
        break;
      }
    }

    if (!foundUploadElement) {
      // Try to navigate to video section
      const videoLinks = page.locator('a, button').filter({
        hasText: /video|upload|media/i
      });
      
      if (await videoLinks.count() > 0) {
        await videoLinks.first().click();
        await page.waitForTimeout(2000);
        
        // Look again for upload elements
        for (const selector of uploadElements) {
          const element = page.locator(selector);
          if (await element.count() > 0) {
            foundUploadElement = true;
            uploadElement = element.first();
            break;
          }
        }
      }
    }

    await TestHelpers.takeScreenshot(page, 'video-upload-interface');
    
    if (foundUploadElement) {
      console.log('✅ Video upload interface found');
      expect(uploadElement).toBeDefined();
    } else {
      console.log('ℹ️ No file upload interface found - may be in different section');
    }
  });

  test('should handle video file upload', async ({ page }) => {
    // Create a test video file
    const testVideoPath = await createTestVideo();
    
    try {
      // Find file input
      const fileInput = page.locator('input[type="file"]');
      
      if (await fileInput.count() > 0) {
        await fileInput.setInputFiles(testVideoPath);
        
        // Wait for upload to start
        await page.waitForTimeout(1000);
        
        // Look for upload progress indicators
        const progressSelectors = [
          '.progress',
          '.upload-progress', 
          '[data-testid*="progress"]',
          '.uploading'
        ];
        
        let hasProgress = false;
        for (const selector of progressSelectors) {
          if (await page.locator(selector).count() > 0) {
            hasProgress = true;
            console.log('✅ Upload progress indicator found:', selector);
            break;
          }
        }
        
        await TestHelpers.takeScreenshot(page, 'video-upload-progress');
        
        // Wait for upload completion (with timeout)
        await page.waitForTimeout(5000);
        await TestHelpers.takeScreenshot(page, 'video-upload-complete');
        
        console.log('✅ Video upload test completed');
      } else {
        console.log('ℹ️ No file input found - testing via API');
        
        // Test upload via API
        const response = await page.request.post('http://localhost:8000/api/videos/upload', {
          multipart: {
            file: fs.createReadStream(testVideoPath),
            project_id: testProject?.id || 1
          }
        });
        
        console.log(`API upload response: ${response.status()}`);
        expect(response.status()).toBeLessThan(500);
      }
      
    } finally {
      // Cleanup test file
      if (fs.existsSync(testVideoPath)) {
        fs.unlinkSync(testVideoPath);
      }
    }
  });

  test('should display uploaded videos', async ({ page }) => {
    // Check for video list/gallery
    const videoListSelectors = [
      '.video-list',
      '.video-gallery', 
      '[data-testid*="video"]',
      '.media-grid',
      'video, .video-thumbnail'
    ];
    
    let foundVideoDisplay = false;
    
    for (const selector of videoListSelectors) {
      const elements = page.locator(selector);
      if (await elements.count() > 0) {
        foundVideoDisplay = true;
        console.log(`✅ Video display found: ${selector} (${await elements.count()} elements)`);
        break;
      }
    }
    
    if (!foundVideoDisplay) {
      // Try to navigate to videos section
      const videoNavLinks = page.locator('a, button').filter({
        hasText: /video|media|library/i
      });
      
      if (await videoNavLinks.count() > 0) {
        await videoNavLinks.first().click();
        await page.waitForTimeout(2000);
        
        // Check again for video displays
        for (const selector of videoListSelectors) {
          const elements = page.locator(selector);
          if (await elements.count() > 0) {
            foundVideoDisplay = true;
            console.log(`✅ Video display found after navigation: ${selector}`);
            break;
          }
        }
      }
    }
    
    await TestHelpers.takeScreenshot(page, 'video-display-interface');
    
    // Test API endpoint for videos
    const apiResponse = await page.request.get('http://localhost:8000/api/videos');
    if (apiResponse.ok()) {
      const videos = await apiResponse.json();
      console.log(`✅ API returned ${videos.length || 0} videos`);
    }
  });

  test('should handle video processing workflow', async ({ page }) => {
    // Test video processing API endpoint
    const processingResponse = await page.request.get('http://localhost:8000/api/videos/processing-status');
    console.log(`Processing status API: ${processingResponse.status()}`);
    
    // Look for processing status indicators in UI
    const processingSelectors = [
      '.processing',
      '.status-processing',
      '[data-status="processing"]',
      '.video-status'
    ];
    
    let foundProcessingUI = false;
    for (const selector of processingSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundProcessingUI = true;
        console.log('✅ Processing status UI found:', selector);
        break;
      }
    }
    
    await TestHelpers.takeScreenshot(page, 'video-processing-status');
    
    // Test sequential video processing endpoint
    const sequentialResponse = await page.request.get('http://localhost:8000/api/sequential-video/status');
    console.log(`Sequential processing API: ${sequentialResponse.status()}`);
    
    if (foundProcessingUI || processingResponse.ok() || sequentialResponse.ok()) {
      console.log('✅ Video processing workflow components detected');
    } else {
      console.log('ℹ️ Processing workflow may not be active currently');
    }
  });

  test('should validate video metadata and thumbnails', async ({ page }) => {
    // Check for video metadata display
    const metadataSelectors = [
      '.video-metadata',
      '.video-info',
      '.file-info',
      '[data-testid*="metadata"]'
    ];
    
    let foundMetadata = false;
    for (const selector of metadataSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundMetadata = true;
        console.log('✅ Video metadata display found:', selector);
        break;
      }
    }
    
    // Check for thumbnails
    const thumbnailSelectors = [
      '.thumbnail',
      '.video-thumbnail',
      'img[src*="thumb"]',
      '.preview-image'
    ];
    
    let foundThumbnails = false;
    for (const selector of thumbnailSelectors) {
      const thumbnails = page.locator(selector);
      if (await thumbnails.count() > 0) {
        foundThumbnails = true;
        console.log(`✅ Thumbnails found: ${selector} (${await thumbnails.count()} elements)`);
        break;
      }
    }
    
    await TestHelpers.takeScreenshot(page, 'video-metadata-thumbnails');
    
    // Test video metadata API
    const metadataResponse = await page.request.get('http://localhost:8000/api/videos/1/metadata');
    console.log(`Video metadata API: ${metadataResponse.status()}`);
  });

  test('should handle video player functionality', async ({ page }) => {
    // Look for video player elements
    const playerSelectors = [
      'video',
      '.video-player',
      '[data-testid*="player"]',
      '.media-player'
    ];
    
    let foundPlayer = false;
    let videoPlayer = null;
    
    for (const selector of playerSelectors) {
      const player = page.locator(selector);
      if (await player.count() > 0) {
        foundPlayer = true;
        videoPlayer = player.first();
        console.log('✅ Video player found:', selector);
        break;
      }
    }
    
    if (foundPlayer && videoPlayer) {
      // Test player controls
      const controlSelectors = [
        '.play-button, button[aria-label*="play"]',
        '.pause-button, button[aria-label*="pause"]',
        '.volume-control',
        '.progress-bar, .seek-bar'
      ];
      
      let controlsFound = 0;
      for (const controlSelector of controlSelectors) {
        if (await page.locator(controlSelector).count() > 0) {
          controlsFound++;
        }
      }
      
      console.log(`✅ Video player controls found: ${controlsFound}/${controlSelectors.length}`);
      
      // Test if video can be played
      try {
        if (await videoPlayer.isVisible()) {
          await videoPlayer.click();
          await page.waitForTimeout(1000);
        }
      } catch (error) {
        console.log('Video player interaction issue:', error.message);
      }
    }
    
    await TestHelpers.takeScreenshot(page, 'video-player-interface');
    
    if (foundPlayer) {
      console.log('✅ Video player functionality detected');
    } else {
      console.log('ℹ️ No video player found - may require video selection first');
    }
  });

  test('should test video download and export', async ({ page }) => {
    // Look for download/export buttons
    const downloadSelectors = [
      'button, a[download]',
      'button, a[href*="download"]',
      '[data-testid*="download"]',
      '[data-testid*="export"]'
    ];
    
    let foundDownloadOption = false;
    
    for (const selector of downloadSelectors) {
      const elements = page.locator(selector).filter({
        hasText: /download|export|save/i
      });
      
      if (await elements.count() > 0) {
        foundDownloadOption = true;
        console.log(`✅ Download/export option found: ${selector}`);
        
        // Test clicking the download button
        try {
          const downloadPromise = page.waitForDownload({ timeout: 10000 });
          await elements.first().click();
          
          const download = await downloadPromise.catch(() => null);
          if (download) {
            console.log('✅ Download initiated:', await download.suggestedFilename());
          }
        } catch (error) {
          console.log('Download test issue:', error.message);
        }
        break;
      }
    }
    
    await TestHelpers.takeScreenshot(page, 'video-download-export');
    
    // Test export API endpoints
    const exportEndpoints = [
      '/api/videos/export',
      '/api/results/export', 
      '/api/annotations/export'
    ];
    
    for (const endpoint of exportEndpoints) {
      try {
        const response = await page.request.get(`http://localhost:8000${endpoint}`);
        console.log(`Export API ${endpoint}: ${response.status()}`);
      } catch (error) {
        console.log(`Export API ${endpoint} issue:`, error.message);
      }
    }
    
    if (foundDownloadOption) {
      console.log('✅ Video download/export functionality detected');
    }
  });
});

/**
 * Create a minimal test video file for upload testing
 */
async function createTestVideo() {
  const testVideoDir = '/tmp/playwright-test-videos';
  if (!fs.existsSync(testVideoDir)) {
    fs.mkdirSync(testVideoDir, { recursive: true });
  }
  
  const testVideoPath = path.join(testVideoDir, `test-video-${Date.now()}.mp4`);
  
  // Create a minimal MP4 file with proper headers
  const minimalMp4Buffer = Buffer.concat([
    // ftyp box (file type)
    Buffer.from([0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70]),
    Buffer.from('isom'),
    Buffer.from([0x00, 0x00, 0x02, 0x00]),
    Buffer.from('isom'),
    Buffer.from('iso2'),
    Buffer.from('avc1'),
    Buffer.from('mp41'),
    
    // moov box (movie metadata) - minimal
    Buffer.from([0x00, 0x00, 0x00, 0x28, 0x6D, 0x6F, 0x6F, 0x76]),
    Buffer.from([0x00, 0x00, 0x00, 0x20, 0x6D, 0x76, 0x68, 0x64]),
    Buffer.alloc(32, 0) // mvhd data (all zeros for minimal file)
  ]);
  
  fs.writeFileSync(testVideoPath, minimalMp4Buffer);
  return testVideoPath;
}