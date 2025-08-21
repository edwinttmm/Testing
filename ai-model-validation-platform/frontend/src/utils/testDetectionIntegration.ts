/**
 * Detection Integration Test Utility
 * 
 * This utility tests the detection system integration with the backend
 */

import { detectionService } from '../services/detectionService';
import { apiService } from '../services/api';
import { getServiceConfig } from './envConfig';

export interface IntegrationTestResult {
  success: boolean;
  message: string;
  details?: any;
  duration?: number;
}

class DetectionIntegrationTester {
  /**
   * Test backend connectivity
   */
  async testBackendConnectivity(): Promise<IntegrationTestResult> {
    const startTime = Date.now();
    
    try {
      const health = await apiService.healthCheck();
      const duration = Date.now() - startTime;
      
      return {
        success: true,
        message: 'Backend connectivity successful',
        details: health,
        duration
      };
    } catch (error: any) {
      return {
        success: false,
        message: `Backend connectivity failed: ${error.message}`,
        details: error,
        duration: Date.now() - startTime
      };
    }
  }

  /**
   * Test detection models availability
   */
  async testDetectionModels(): Promise<IntegrationTestResult> {
    const startTime = Date.now();
    
    try {
      const models = await apiService.getAvailableModels();
      const duration = Date.now() - startTime;
      
      if (!models.models || models.models.length === 0) {
        return {
          success: false,
          message: 'No detection models available',
          details: models,
          duration
        };
      }
      
      return {
        success: true,
        message: `Found ${models.models.length} detection models`,
        details: models,
        duration
      };
    } catch (error: any) {
      return {
        success: false,
        message: `Failed to fetch detection models: ${error.message}`,
        details: error,
        duration: Date.now() - startTime
      };
    }
  }

  /**
   * Test WebSocket connection
   */
  async testWebSocketConnection(): Promise<IntegrationTestResult> {
    const startTime = Date.now();
    
    return new Promise((resolve) => {
      const wsConfig = getServiceConfig('websocket');
      const testUrl = `${wsConfig.url}/ws/detection/test`;
      
      try {
        const ws = new WebSocket(testUrl);
        
        const timeout = setTimeout(() => {
          ws.close();
          resolve({
            success: false,
            message: 'WebSocket connection timeout',
            duration: Date.now() - startTime
          });
        }, 5000);
        
        ws.onopen = () => {
          clearTimeout(timeout);
          ws.close();
          resolve({
            success: true,
            message: 'WebSocket connection successful',
            duration: Date.now() - startTime
          });
        };
        
        ws.onerror = (error) => {
          clearTimeout(timeout);
          resolve({
            success: false,
            message: 'WebSocket connection failed',
            details: error,
            duration: Date.now() - startTime
          });
        };
        
      } catch (error: any) {
        resolve({
          success: false,
          message: `WebSocket setup failed: ${error.message}`,
          details: error,
          duration: Date.now() - startTime
        });
      }
    });
  }

  /**
   * Test detection service with mock data
   */
  async testDetectionService(): Promise<IntegrationTestResult> {
    const startTime = Date.now();
    const testVideoId = 'test-video-' + Date.now();
    
    try {
      const result = await detectionService.runDetection(testVideoId, {
        confidenceThreshold: 0.5,
        nmsThreshold: 0.4,
        modelName: 'yolov8n',
        targetClasses: ['person', 'bicycle'],
        maxRetries: 1,
        retryDelay: 1000,
        useFallback: true
      });
      
      const duration = Date.now() - startTime;
      
      return {
        success: result.success,
        message: result.success 
          ? `Detection service test passed with ${result.detections.length} detections`
          : `Detection service test failed: ${result.error}`,
        details: result,
        duration
      };
    } catch (error: any) {
      return {
        success: false,
        message: `Detection service test error: ${error.message}`,
        details: error,
        duration: Date.now() - startTime
      };
    }
  }

  /**
   * Run all integration tests
   */
  async runFullTest(): Promise<{
    overall: IntegrationTestResult;
    individual: {
      backend: IntegrationTestResult;
      models: IntegrationTestResult;
      websocket: IntegrationTestResult;
      detection: IntegrationTestResult;
    };
  }> {
    console.log('🧪 Running detection integration tests...');
    
    const [backend, models, websocket, detection] = await Promise.allSettled([
      this.testBackendConnectivity(),
      this.testDetectionModels(),
      this.testWebSocketConnection(),
      this.testDetectionService()
    ]);
    
    const backendResult = backend.status === 'fulfilled' ? backend.value : {
      success: false,
      message: 'Backend test crashed',
      details: backend.reason
    };
    
    const modelsResult = models.status === 'fulfilled' ? models.value : {
      success: false,
      message: 'Models test crashed',
      details: models.reason
    };
    
    const websocketResult = websocket.status === 'fulfilled' ? websocket.value : {
      success: false,
      message: 'WebSocket test crashed',
      details: websocket.reason
    };
    
    const detectionResult = detection.status === 'fulfilled' ? detection.value : {
      success: false,
      message: 'Detection test crashed',
      details: detection.reason
    };
    
    const successCount = [backendResult, modelsResult, websocketResult, detectionResult]
      .filter(r => r.success).length;
    
    const overall: IntegrationTestResult = {
      success: successCount >= 3, // At least 3/4 tests should pass
      message: `Integration test completed: ${successCount}/4 tests passed`,
      details: {
        passedTests: successCount,
        totalTests: 4,
        criticalTestsPassed: backendResult.success && detectionResult.success
      }
    };
    
    return {
      overall,
      individual: {
        backend: backendResult,
        models: modelsResult,
        websocket: websocketResult,
        detection: detectionResult
      }
    };
  }
}

// Export singleton instance
export const detectionIntegrationTester = new DetectionIntegrationTester();

// Export convenience function for quick testing
export const runDetectionIntegrationTest = () => detectionIntegrationTester.runFullTest();

// Export individual test functions
export const testBackendConnectivity = () => detectionIntegrationTester.testBackendConnectivity();
export const testDetectionModels = () => detectionIntegrationTester.testDetectionModels();
export const testWebSocketConnection = () => detectionIntegrationTester.testWebSocketConnection();
export const testDetectionService = () => detectionIntegrationTester.testDetectionService();

export default detectionIntegrationTester;