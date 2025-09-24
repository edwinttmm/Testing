const { test, expect } = require('@playwright/test');
const TestHelpers = require('../utils/test-helpers');
const fs = require('fs').promises;
const path = require('path');

test.describe('YOLOv8 ML Pipeline Tests', () => {
  let helpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
    await helpers.login(); // Ensure authenticated for ML tests
  });

  test('should load YOLO model in backend venv', async ({ page }) => {
    // Test backend YOLO model loading using venv
    const response = await page.request.post('http://localhost:8000/ml/load_model', {
      data: {
        model_type: 'yolov8',
        model_size: 'n'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.status).toBe('success');
    expect(data.model_loaded).toBe(true);
    
    await helpers.saveTestResults('yolo-model-loading', {
      status: response.status(),
      model_loaded: data.model_loaded,
      model_type: data.model_type,
      backend_venv: true,
      ultralytics_version: data.ultralytics_version,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('yolo-model-loaded');
  });

  test('should validate ultralytics installation in backend venv', async ({ page }) => {
    // Verify ultralytics is properly installed in backend venv
    const response = await page.request.get('http://localhost:8000/ml/health');
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.ultralytics_installed).toBe(true);
    expect(data.ultralytics_version).toMatch(/8\.3\.187/);
    
    await helpers.saveTestResults('ultralytics-health-check', {
      ultralytics_installed: data.ultralytics_installed,
      version: data.ultralytics_version,
      backend_venv_active: data.backend_venv_active,
      timestamp: Date.now()
    });
  });

  test('should perform YOLO inference on test image', async ({ page }) => {
    // Create a test image for inference
    const testImageData = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAhEAACAQMDBQAAAAAAAAAAAAABAgMABAUGIWGRkqGx/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAhEQACAQIHAQAAAAAAAAAAAAABAgADBAUREiExYUFxkf/aAAwDAQACEQMRAD8A0XGAlCaSSWghRAQAAEBEQAQBAQAAQABAAA=';
    
    const response = await page.request.post('http://localhost:8000/ml/yolo/inference', {
      data: {
        image_data: testImageData,
        confidence: 0.5,
        model_size: 'n'
      }
    });
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.status).toBe('success');
    expect(data).toHaveProperty('detections');
    expect(data).toHaveProperty('inference_time');
    
    await helpers.saveTestResults('yolo-inference-test', {
      status: data.status,
      detections_count: data.detections.length,
      inference_time_ms: data.inference_time,
      model_size: 'n',
      confidence_threshold: 0.5,
      timestamp: Date.now()
    });
    
    await helpers.takeScreenshot('yolo-inference-results');
  });

  test('should handle batch YOLO inference', async ({ page }) => {
    const batchData = {
      images: [
        'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...',
        'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...'
      ],
      confidence: 0.6,
      model_size: 'n'
    };
    
    const startTime = Date.now();
    const response = await page.request.post('http://localhost:8000/ml/yolo/batch_inference', {
      data: batchData
    });
    const endTime = Date.now();
    
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.status).toBe('success');
    expect(data.results).toHaveLength(2);
    
    await helpers.saveTestResults('yolo-batch-inference', {
      status: data.status,
      batch_size: 2,
      total_time_ms: endTime - startTime,
      avg_inference_time: data.avg_inference_time,
      results_count: data.results.length,
      timestamp: Date.now()
    });
  });

  test('should measure YOLO inference performance', async ({ page }) => {
    const performanceResults = [];
    
    // Test multiple inference calls to measure performance
    for (let i = 0; i < 10; i++) {
      const startTime = performance.now();
      const response = await page.request.post('http://localhost:8000/ml/yolo/inference', {
        data: {
          image_data: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...',
          confidence: 0.5
        }
      });
      const endTime = performance.now();
      
      const data = await response.json();
      performanceResults.push({
        iteration: i + 1,
        status: response.status(),
        inference_time_ms: endTime - startTime,
        backend_inference_time: data.inference_time,
        timestamp: Date.now()
      });
    }
    
    const avgTime = performanceResults.reduce((sum, result) => sum + result.inference_time_ms, 0) / 10;
    const minTime = Math.min(...performanceResults.map(r => r.inference_time_ms));
    const maxTime = Math.max(...performanceResults.map(r => r.inference_time_ms));
    
    expect(avgTime).toBeLessThan(5000); // Should complete within 5 seconds on average
    
    await helpers.saveTestResults('yolo-performance-test', {
      iterations: 10,
      avg_time_ms: avgTime,
      min_time_ms: minTime,
      max_time_ms: maxTime,
      all_results: performanceResults,
      backend_venv_ultralytics: true,
      timestamp: Date.now()
    });
  });

  test('should handle video processing with YOLO', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Navigate to video processing section
    await page.click('[data-testid="video-processing-tab"]');
    await helpers.takeScreenshot('video-processing-page');
    
    // Select YOLO model
    await helpers.selectMLModel('yolov8');
    await helpers.takeScreenshot('yolo-model-selected');
    
    // Test video upload (mock small video file)
    const mockVideoPath = path.join(__dirname, '../fixtures/test-video.mp4');
    // Create a small test video file if it doesn't exist
    try {
      await fs.access(mockVideoPath);
    } catch {
      // Create minimal test video data
      await fs.writeFile(mockVideoPath, Buffer.from('mock video data for testing'));
    }
    
    await helpers.uploadVideo(mockVideoPath);
    await helpers.takeScreenshot('video-uploaded');
    
    // Start processing
    await helpers.startDetection();
    await helpers.takeScreenshot('video-processing-started');
    
    // Wait for processing results
    await helpers.waitForDetectionResults();
    await helpers.takeScreenshot('video-processing-completed');
    
    // Verify results display
    const resultsElement = page.locator('[data-testid="detection-results"]');
    await expect(resultsElement).toBeVisible();
    
    const resultsText = await resultsElement.textContent();
    expect(resultsText).toContain('detection');
  });

  test('should validate ML model switching', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Test switching between different YOLO model sizes
    const modelSizes = ['n', 's', 'm'];
    
    for (const size of modelSizes) {
      const response = await page.request.post('http://localhost:8000/ml/switch_model', {
        data: {
          model_type: 'yolov8',
          model_size: size
        }
      });
      
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data.status).toBe('success');
      expect(data.current_model).toContain(size);
      
      await helpers.takeScreenshot(`yolo-model-${size}-loaded`);
    }
    
    await helpers.saveTestResults('model-switching-test', {
      models_tested: modelSizes,
      all_successful: true,
      backend_venv: true,
      timestamp: Date.now()
    });
  });

  test('should handle concurrent YOLO inference requests', async ({ page }) => {
    const concurrentRequests = 5;
    const promises = [];
    
    for (let i = 0; i < concurrentRequests; i++) {
      const promise = page.request.post('http://localhost:8000/ml/yolo/inference', {
        data: {
          image_data: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...',
          confidence: 0.5,
          request_id: i
        }
      });
      promises.push(promise);
    }
    
    const startTime = Date.now();
    const responses = await Promise.all(promises);
    const endTime = Date.now();
    
    // Verify all requests succeeded
    responses.forEach((response, index) => {
      expect(response.status()).toBe(200);
    });
    
    await helpers.saveTestResults('concurrent-inference-test', {
      concurrent_requests: concurrentRequests,
      total_time_ms: endTime - startTime,
      all_successful: responses.every(r => r.status() === 200),
      avg_time_per_request: (endTime - startTime) / concurrentRequests,
      backend_venv_ultralytics: true,
      timestamp: Date.now()
    });
  });
});