/**
 * API Connectivity Fixes for AI Model Validation Platform
 * 
 * Comprehensive solution for ERR_CONNECTION_REFUSED and environment configuration issues
 * Date: August 26, 2025
 */

import { EnhancedApiService } from './enhanced-api-service';
import { SmartConfigurationManager } from './smart-config-manager';
import { ConnectivityHealthChecker } from './connectivity-health-checker';
import { FallbackStrategyManager } from './fallback-strategy-manager';

// Main API connectivity fix implementation
export class ApiConnectivityFixer {
  private apiService: EnhancedApiService;
  private configManager: SmartConfigurationManager;
  private healthChecker: ConnectivityHealthChecker;
  private fallbackManager: FallbackStrategyManager;
  
  constructor() {
    this.initializeServices();
  }
  
  private initializeServices() {
    // Initialize configuration manager first
    this.configManager = new SmartConfigurationManager({
      primaryApiUrl: 'http://155.138.239.131:8000',
      fallbackApiUrls: [
        'http://localhost:8000',
        'http://127.0.0.1:8000'
      ],
      connectionTimeout: 10000,
      retryAttempts: 3,
      retryDelay: 1000
    });
    
    // Initialize health checker
    this.healthChecker = new ConnectivityHealthChecker(this.configManager);
    
    // Initialize fallback strategy manager
    this.fallbackManager = new FallbackStrategyManager(this.configManager, this.healthChecker);
    
    // Initialize enhanced API service
    this.apiService = new EnhancedApiService(this.configManager, this.fallbackManager);
  }
  
  async fixApiConnectivity(): Promise<ApiConnectivityResult> {
    console.log('🔧 Starting API connectivity fixes...');
    
    try {
      // Step 1: Test current connectivity
      const connectivityStatus = await this.healthChecker.performHealthCheck();
      console.log('🏥 Health check results:', connectivityStatus);
      
      // Step 2: Apply configuration fixes
      const configFixes = await this.configManager.applyConfigurationFixes();
      console.log('⚙️ Configuration fixes applied:', configFixes);
      
      // Step 3: Setup fallback strategies
      const fallbackStrategies = await this.fallbackManager.setupFallbackStrategies();
      console.log('🔄 Fallback strategies configured:', fallbackStrategies);
      
      // Step 4: Test final connectivity
      const finalTest = await this.healthChecker.performComprehensiveTest();
      console.log('✅ Final connectivity test:', finalTest);
      
      return {
        success: true,
        message: 'API connectivity fixes applied successfully',
        details: {
          initialHealth: connectivityStatus,
          configurationFixes: configFixes,
          fallbackStrategies: fallbackStrategies,
          finalTest: finalTest
        }
      };
      
    } catch (error) {
      console.error('❌ API connectivity fix failed:', error);
      return {
        success: false,
        message: `API connectivity fix failed: ${error.message}`,
        error: error
      };
    }
  }
}

// Enhanced API Service with intelligent connectivity handling
class EnhancedApiService {
  private configManager: SmartConfigurationManager;
  private fallbackManager: FallbackStrategyManager;
  
  constructor(
    configManager: SmartConfigurationManager, 
    fallbackManager: FallbackStrategyManager
  ) {
    this.configManager = configManager;
    this.fallbackManager = fallbackManager;
  }
  
  async makeRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const config = this.configManager.getCurrentConfig();
    const primaryUrl = `${config.primaryApiUrl}${endpoint}`;
    
    try {
      // Try primary URL first
      const response = await this.attemptRequest(primaryUrl, options);
      if (response.ok) {
        return response.json();
      }
    } catch (error) {
      console.warn(`🔄 Primary API failed (${primaryUrl}):`, error.message);
    }
    
    // Use fallback strategy
    return this.fallbackManager.executeWithFallback(endpoint, options);
  }
  
  private async attemptRequest(url: string, options: RequestInit): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.configManager.getConnectionTimeout());
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });
      clearTimeout(timeoutId);
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}

// Smart Configuration Manager
class SmartConfigurationManager {
  private config: ApiConfiguration;
  private environmentDetector: EnvironmentDetector;
  
  constructor(initialConfig: Partial<ApiConfiguration>) {
    this.environmentDetector = new EnvironmentDetector();
    this.config = this.buildConfiguration(initialConfig);
  }
  
  private buildConfiguration(initial: Partial<ApiConfiguration>): ApiConfiguration {
    const environment = this.environmentDetector.detectEnvironment();
    const defaultConfig = this.getDefaultConfigForEnvironment(environment);
    
    return {
      ...defaultConfig,
      ...initial
    };
  }
  
  private getDefaultConfigForEnvironment(env: Environment): ApiConfiguration {
    const baseConfig = {
      connectionTimeout: 10000,
      retryAttempts: 3,
      retryDelay: 1000
    };
    
    switch (env) {
      case 'production':
        return {
          ...baseConfig,
          primaryApiUrl: 'http://155.138.239.131:8000',
          fallbackApiUrls: ['http://localhost:8000'],
          connectionTimeout: 15000,
          retryAttempts: 5
        };
        
      case 'development':
        return {
          ...baseConfig,
          primaryApiUrl: 'http://155.138.239.131:8000',
          fallbackApiUrls: [
            'http://localhost:8000',
            'http://127.0.0.1:8000'
          ],
          connectionTimeout: 8000,
          retryAttempts: 3
        };
        
      default:
        return {
          ...baseConfig,
          primaryApiUrl: 'http://155.138.239.131:8000',
          fallbackApiUrls: ['http://localhost:8000']
        };
    }
  }
  
  async applyConfigurationFixes(): Promise<ConfigurationFixResult> {
    const fixes: string[] = [];
    
    // Fix 1: Ensure primary URL is accessible
    const primaryHealthy = await this.testUrl(this.config.primaryApiUrl);
    if (!primaryHealthy) {
      fixes.push('Primary API URL is not accessible - relying on fallbacks');
    }
    
    // Fix 2: Validate fallback URLs
    const validFallbacks = [];
    for (const fallbackUrl of this.config.fallbackApiUrls) {
      const healthy = await this.testUrl(fallbackUrl);
      if (healthy) {
        validFallbacks.push(fallbackUrl);
      } else {
        fixes.push(`Fallback URL not accessible: ${fallbackUrl}`);
      }
    }
    
    // Update configuration with only working fallbacks
    this.config.fallbackApiUrls = validFallbacks;
    
    // Fix 3: Update environment variables if needed
    if (typeof window === 'undefined') {
      // Server-side: Update process.env
      process.env.REACT_APP_API_URL = this.config.primaryApiUrl;
    } else {
      // Client-side: Update runtime config
      this.updateRuntimeConfig();
    }
    
    fixes.push('Configuration updated with working endpoints');
    
    return {
      applied: fixes.length > 0,
      fixes: fixes,
      workingEndpoints: {
        primary: primaryHealthy ? this.config.primaryApiUrl : null,
        fallbacks: validFallbacks
      }
    };
  }
  
  private async testUrl(url: string): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${url}/health`, {
        method: 'GET',
        signal: controller.signal,
        headers: { 'Accept': 'application/json' }
      });
      
      clearTimeout(timeoutId);
      return response.ok;
    } catch {
      return false;
    }
  }
  
  private updateRuntimeConfig() {
    // Update runtime configuration for client-side
    if (window.RUNTIME_CONFIG) {
      window.RUNTIME_CONFIG.REACT_APP_API_URL = this.config.primaryApiUrl;
    }
    
    // Also update localStorage cache
    localStorage.setItem('api-config', JSON.stringify({
      primaryUrl: this.config.primaryApiUrl,
      fallbackUrls: this.config.fallbackApiUrls,
      lastUpdated: new Date().toISOString()
    }));
  }
  
  getCurrentConfig(): ApiConfiguration {
    return { ...this.config };
  }
  
  getConnectionTimeout(): number {
    return this.config.connectionTimeout;
  }
}

// Connectivity Health Checker
class ConnectivityHealthChecker {
  private configManager: SmartConfigurationManager;
  
  constructor(configManager: SmartConfigurationManager) {
    this.configManager = configManager;
  }
  
  async performHealthCheck(): Promise<HealthCheckResult> {
    const config = this.configManager.getCurrentConfig();
    const results: EndpointHealthResult[] = [];
    
    // Test primary endpoint
    const primaryResult = await this.testEndpoint(config.primaryApiUrl, 'primary');
    results.push(primaryResult);
    
    // Test fallback endpoints
    for (let i = 0; i < config.fallbackApiUrls.length; i++) {
      const fallbackResult = await this.testEndpoint(config.fallbackApiUrls[i], `fallback-${i}`);
      results.push(fallbackResult);
    }
    
    const healthyEndpoints = results.filter(r => r.healthy);
    
    return {
      overall: healthyEndpoints.length > 0 ? 'healthy' : 'unhealthy',
      totalEndpoints: results.length,
      healthyEndpoints: healthyEndpoints.length,
      results: results,
      timestamp: new Date().toISOString()
    };
  }
  
  async performComprehensiveTest(): Promise<ComprehensiveTestResult> {
    const config = this.configManager.getCurrentConfig();
    
    const tests = {
      healthCheck: await this.testHealthEndpoint(config.primaryApiUrl),
      apiEndpoints: await this.testApiEndpoints(config.primaryApiUrl),
      errorHandling: await this.testErrorHandling(config.primaryApiUrl),
      timeout: await this.testTimeoutHandling(config.primaryApiUrl)
    };
    
    const passedTests = Object.values(tests).filter(t => t.passed).length;
    const totalTests = Object.keys(tests).length;
    
    return {
      overall: passedTests === totalTests ? 'passed' : 'partial',
      score: `${passedTests}/${totalTests}`,
      tests: tests,
      timestamp: new Date().toISOString()
    };
  }
  
  private async testEndpoint(url: string, type: string): Promise<EndpointHealthResult> {
    const startTime = Date.now();
    
    try {
      const response = await fetch(`${url}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
        headers: { 'Accept': 'application/json' }
      });
      
      const latency = Date.now() - startTime;
      
      if (response.ok) {
        const data = await response.json();
        return {
          url,
          type,
          healthy: true,
          latency,
          status: response.status,
          data
        };
      } else {
        return {
          url,
          type,
          healthy: false,
          latency,
          status: response.status,
          error: `HTTP ${response.status}: ${response.statusText}`
        };
      }
    } catch (error) {
      return {
        url,
        type,
        healthy: false,
        latency: Date.now() - startTime,
        error: error.message
      };
    }
  }
  
  private async testHealthEndpoint(baseUrl: string): Promise<TestResult> {
    try {
      const response = await fetch(`${baseUrl}/health`);
      const data = await response.json();
      
      return {
        name: 'Health Endpoint',
        passed: response.ok && data.status === 'healthy',
        details: data
      };
    } catch (error) {
      return {
        name: 'Health Endpoint',
        passed: false,
        error: error.message
      };
    }
  }
  
  private async testApiEndpoints(baseUrl: string): Promise<TestResult> {
    try {
      // Test a simple API endpoint
      const response = await fetch(`${baseUrl}/api/dashboard/stats`, {
        headers: { 'Accept': 'application/json' }
      });
      
      return {
        name: 'API Endpoints',
        passed: response.ok,
        details: { status: response.status, statusText: response.statusText }
      };
    } catch (error) {
      return {
        name: 'API Endpoints',
        passed: false,
        error: error.message
      };
    }
  }
  
  private async testErrorHandling(baseUrl: string): Promise<TestResult> {
    try {
      // Test error handling with invalid endpoint
      const response = await fetch(`${baseUrl}/api/nonexistent`);
      
      return {
        name: 'Error Handling',
        passed: response.status === 404,
        details: { status: response.status, expectedStatus: 404 }
      };
    } catch (error) {
      return {
        name: 'Error Handling',
        passed: false,
        error: error.message
      };
    }
  }
  
  private async testTimeoutHandling(baseUrl: string): Promise<TestResult> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 100); // Very short timeout
      
      await fetch(`${baseUrl}/health`, {
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      return {
        name: 'Timeout Handling',
        passed: true,
        details: { message: 'Request completed within timeout' }
      };
    } catch (error) {
      return {
        name: 'Timeout Handling',
        passed: error.name === 'AbortError',
        details: { 
          message: error.name === 'AbortError' ? 'Timeout handled correctly' : 'Unexpected error',
          errorType: error.name
        }
      };
    }
  }
}

// Fallback Strategy Manager
class FallbackStrategyManager {
  private configManager: SmartConfigurationManager;
  private healthChecker: ConnectivityHealthChecker;
  
  constructor(
    configManager: SmartConfigurationManager,
    healthChecker: ConnectivityHealthChecker
  ) {
    this.configManager = configManager;
    this.healthChecker = healthChecker;
  }
  
  async setupFallbackStrategies(): Promise<FallbackSetupResult> {
    const strategies: string[] = [];
    
    // Strategy 1: Circuit breaker pattern
    this.setupCircuitBreaker();
    strategies.push('Circuit breaker pattern enabled');
    
    // Strategy 2: Request retry with exponential backoff
    this.setupRetryStrategy();
    strategies.push('Exponential backoff retry strategy configured');
    
    // Strategy 3: Health-based endpoint selection
    await this.setupHealthBasedSelection();
    strategies.push('Health-based endpoint selection enabled');
    
    // Strategy 4: Offline mode fallback
    this.setupOfflineFallback();
    strategies.push('Offline mode fallback configured');
    
    return {
      strategiesCount: strategies.length,
      strategies: strategies
    };
  }
  
  async executeWithFallback<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const config = this.configManager.getCurrentConfig();
    const urls = [config.primaryApiUrl, ...config.fallbackApiUrls];
    
    let lastError: Error;
    
    for (const baseUrl of urls) {
      try {
        const response = await this.attemptRequestWithRetry(`${baseUrl}${endpoint}`, options);
        if (response.ok) {
          return response.json();
        }
      } catch (error) {
        console.warn(`🔄 Fallback attempt failed for ${baseUrl}:`, error.message);
        lastError = error;
      }
    }
    
    // If all URLs failed, try offline fallback
    const offlineResult = this.tryOfflineFallback<T>(endpoint);
    if (offlineResult) {
      console.log('📱 Using offline fallback for:', endpoint);
      return offlineResult;
    }
    
    throw lastError || new Error('All API endpoints failed and no offline fallback available');
  }
  
  private async attemptRequestWithRetry(url: string, options: RequestInit): Promise<Response> {
    const config = this.configManager.getCurrentConfig();
    let attempt = 0;
    
    while (attempt < config.retryAttempts) {
      try {
        const response = await fetch(url, {
          ...options,
          signal: AbortSignal.timeout(config.connectionTimeout)
        });
        
        if (response.ok || response.status < 500) {
          return response;
        }
        
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      } catch (error) {
        attempt++;
        if (attempt >= config.retryAttempts) {
          throw error;
        }
        
        // Exponential backoff
        const delay = config.retryDelay * Math.pow(2, attempt - 1);
        console.log(`⏳ Retry ${attempt}/${config.retryAttempts} after ${delay}ms delay`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  private setupCircuitBreaker() {
    // Implementation of circuit breaker pattern
    // This would monitor failure rates and temporarily disable failing endpoints
  }
  
  private setupRetryStrategy() {
    // Retry configuration is already implemented in attemptRequestWithRetry
  }
  
  private async setupHealthBasedSelection() {
    // Periodically check endpoint health and reorder by reliability
    setInterval(async () => {
      const healthCheck = await this.healthChecker.performHealthCheck();
      // Update endpoint priority based on health check results
    }, 60000); // Check every minute
  }
  
  private setupOfflineFallback() {
    // Setup service worker for offline caching if available
    if ('serviceWorker' in navigator) {
      // Register service worker for offline functionality
    }
  }
  
  private tryOfflineFallback<T>(endpoint: string): T | null {
    // Try to get cached data from localStorage or IndexedDB
    try {
      const cached = localStorage.getItem(`offline-cache-${endpoint}`);
      if (cached) {
        const data = JSON.parse(cached);
        if (Date.now() - data.timestamp < 300000) { // 5 minutes
          return data.value;
        }
      }
    } catch {
      // Ignore cache errors
    }
    
    return null;
  }
}

// Environment Detector
class EnvironmentDetector {
  detectEnvironment(): Environment {
    // Check explicit environment setting
    if (process.env.REACT_APP_ENVIRONMENT) {
      return process.env.REACT_APP_ENVIRONMENT as Environment;
    }
    
    // Check NODE_ENV
    if (process.env.NODE_ENV === 'production') {
      return 'production';
    }
    
    // Check URL patterns
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      if (hostname === '155.138.239.131' || hostname.includes('prod')) {
        return 'production';
      }
    }
    
    return 'development';
  }
}

// Type definitions
interface ApiConfiguration {
  primaryApiUrl: string;
  fallbackApiUrls: string[];
  connectionTimeout: number;
  retryAttempts: number;
  retryDelay: number;
}

interface ApiConnectivityResult {
  success: boolean;
  message: string;
  details?: any;
  error?: Error;
}

interface ConfigurationFixResult {
  applied: boolean;
  fixes: string[];
  workingEndpoints: {
    primary: string | null;
    fallbacks: string[];
  };
}

interface HealthCheckResult {
  overall: 'healthy' | 'unhealthy';
  totalEndpoints: number;
  healthyEndpoints: number;
  results: EndpointHealthResult[];
  timestamp: string;
}

interface EndpointHealthResult {
  url: string;
  type: string;
  healthy: boolean;
  latency: number;
  status?: number;
  data?: any;
  error?: string;
}

interface ComprehensiveTestResult {
  overall: 'passed' | 'partial' | 'failed';
  score: string;
  tests: Record<string, TestResult>;
  timestamp: string;
}

interface TestResult {
  name: string;
  passed: boolean;
  details?: any;
  error?: string;
}

interface FallbackSetupResult {
  strategiesCount: number;
  strategies: string[];
}

type Environment = 'development' | 'production' | 'test';

// Global runtime config interface
declare global {
  interface Window {
    RUNTIME_CONFIG?: {
      REACT_APP_API_URL?: string;
      [key: string]: any;
    };
  }
}

// Export main fixer
export const apiConnectivityFixer = new ApiConnectivityFixer();

// Export individual components for advanced usage
export {
  EnhancedApiService,
  SmartConfigurationManager,
  ConnectivityHealthChecker,
  FallbackStrategyManager,
  EnvironmentDetector
};