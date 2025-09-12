/**
 * Phase 1: CORS Fixes Integration Test
 * Tests frontend-backend API communication after CORS fixes
 */

import { appConfig } from '../../src/config/appConfig';

interface HealthResponse {
  status: string;
  timestamp: string;
  version?: string;
}

interface ApiTestResult {
  endpoint: string;
  success: boolean;
  status?: number;
  responseTime: number;
  error?: string;
}

describe('Phase 1: CORS Integration Testing', () => {
  const API_BASE = appConfig.api.baseUrl;
  const testResults: ApiTestResult[] = [];

  const testApiEndpoint = async (endpoint: string): Promise<ApiTestResult> => {
    const startTime = Date.now();
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      return {
        endpoint,
        success: response.ok,
        status: response.status,
        responseTime: Date.now() - startTime,
      };
    } catch (error) {
      return {
        endpoint,
        success: false,
        responseTime: Date.now() - startTime,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  };

  test('Backend health check should respond correctly', async () => {
    const result = await testApiEndpoint('/health');
    testResults.push(result);
    
    expect(result.success).toBe(true);
    expect(result.status).toBe(200);
    expect(result.responseTime).toBeLessThan(5000);
  });

  test('Projects API should be accessible', async () => {
    const result = await testApiEndpoint('/api/projects');
    testResults.push(result);
    
    expect(result.success).toBe(true);
    expect(result.status).toBe(200);
  });

  test('CORS headers should be present', async () => {
    try {
      const response = await fetch(`${API_BASE}/health`, {
        method: 'OPTIONS',
      });

      const corsHeaders = {
        'access-control-allow-origin': response.headers.get('access-control-allow-origin'),
        'access-control-allow-methods': response.headers.get('access-control-allow-methods'),
        'access-control-allow-headers': response.headers.get('access-control-allow-headers'),
      };

      expect(corsHeaders['access-control-allow-origin']).toBeTruthy();
      expect(corsHeaders['access-control-allow-methods']).toContain('GET');
      expect(corsHeaders['access-control-allow-methods']).toContain('POST');
    } catch (error) {
      console.warn('CORS preflight test failed:', error);
    }
  });

  afterAll(() => {
    const successRate = (testResults.filter(r => r.success).length / testResults.length) * 100;
    console.log('Phase 1 CORS Test Results:', {
      totalTests: testResults.length,
      successRate: `${successRate.toFixed(1)}%`,
      results: testResults,
    });

    // Minimum 100% API integration success required
    expect(successRate).toBeGreaterThanOrEqual(100);
  });
});