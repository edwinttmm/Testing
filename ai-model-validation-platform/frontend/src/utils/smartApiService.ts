/**
 * Smart API Service with Enhanced Error Handling
 * 
 * This service extends the existing API service with intelligent connectivity handling,
 * automatic fallback strategies, and robust error recovery.
 */

import axios, { AxiosInstance, AxiosResponse, AxiosError } from 'axios';
import { AppError, ErrorFactory } from './errorTypes';
import { envConfig, getServiceConfig, isDebugEnabled } from './envConfig';
import { apiCache } from './apiCache';
import errorReporting from '../services/errorReporting';
import {
  isObject,
  isString,
  isNumber,
  isAxiosError,
  parseErrorResponse,
  safeGet,
} from './typeGuards';

interface SmartApiConfig {
  primaryBaseUrl: string;
  fallbackBaseUrls: string[];
  timeout: number;
  retryAttempts: number;
  retryDelay: number;
  enableFallback: boolean;
  enableOfflineMode: boolean;
}

interface ConnectivityStatus {
  isOnline: boolean;
  primaryAvailable: boolean;
  fallbacksAvailable: string[];
  lastChecked: number;
}

interface RequestOptions {
  skipFallback?: boolean;
  skipCache?: boolean;
  skipRetry?: boolean;
  customTimeout?: number;
}

class SmartApiService {
  private primaryApi!: AxiosInstance;
  private fallbackApis: AxiosInstance[] = [];
  private config!: SmartApiConfig;
  private connectivityStatus!: ConnectivityStatus;
  private circuitBreaker: Map<string, { failures: number; nextTry: number }> = new Map();
  
  constructor() {
    this.loadConfiguration();
    this.initializeApiInstances();
    this.initializeConnectivityMonitoring();
  }
  
  private loadConfiguration() {
    const serviceConfig = getServiceConfig('api');
    const envConfiguration = envConfig.getConfig();
    
    this.config = {
      primaryBaseUrl: envConfiguration.apiUrl,
      fallbackBaseUrls: [
        'http://localhost:8000',
        'http://127.0.0.1:8000'
      ],
      timeout: serviceConfig.timeout || 30000,
      retryAttempts: serviceConfig.retryAttempts || 3,
      retryDelay: serviceConfig.retryDelay || 1000,
      enableFallback: true,
      enableOfflineMode: true
    };
    
    this.connectivityStatus = {
      isOnline: navigator.onLine,
      primaryAvailable: true,
      fallbacksAvailable: [],
      lastChecked: Date.now()
    };
    
    if (isDebugEnabled()) {
      console.log('🧮 Smart API Service Configuration:', {
        primary: this.config.primaryBaseUrl,
        fallbacks: this.config.fallbackBaseUrls,
        timeout: this.config.timeout,
        retryAttempts: this.config.retryAttempts
      });
    }
  }
  
  private initializeApiInstances() {
    // Primary API instance
    this.primaryApi = this.createApiInstance(this.config.primaryBaseUrl);
    
    // Fallback API instances
    this.fallbackApis = this.config.fallbackBaseUrls.map(url => 
      this.createApiInstance(url)
    );
  }
  
  private createApiInstance(baseURL: string): AxiosInstance {
    const api = axios.create({
      baseURL,
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    // Add request interceptor for debugging
    api.interceptors.request.use(
      (config) => {
        if (isDebugEnabled()) {
          console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
        }
        return config;
      },
      (error) => Promise.reject(error)
    );
    
    // Add response interceptor for error handling
    api.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error: AxiosError) => {
        // Update circuit breaker status
        this.updateCircuitBreaker(error.config?.baseURL || '', false);
        return Promise.reject(error);
      }
    );
    
    return api;
  }
  
  private initializeConnectivityMonitoring() {
    // Monitor online/offline status
    window.addEventListener('online', () => {
      this.connectivityStatus.isOnline = true;
      this.performHealthCheck();
    });
    
    window.addEventListener('offline', () => {
      this.connectivityStatus.isOnline = false;
    });
    
    // Periodic health check
    setInterval(() => {
      this.performHealthCheck();
    }, 60000); // Every minute
    
    // Initial health check
    this.performHealthCheck();
  }
  
  private async performHealthCheck(): Promise<void> {
    if (!this.connectivityStatus.isOnline) return;
    
    try {
      // Check primary API
      const primaryHealthy = await this.testEndpoint(this.config.primaryBaseUrl);
      this.connectivityStatus.primaryAvailable = primaryHealthy;
      
      // Check fallback APIs
      this.connectivityStatus.fallbacksAvailable = [];
      for (const fallbackUrl of this.config.fallbackBaseUrls) {
        const fallbackHealthy = await this.testEndpoint(fallbackUrl);
        if (fallbackHealthy) {
          this.connectivityStatus.fallbacksAvailable.push(fallbackUrl);
        }
      }
      
      this.connectivityStatus.lastChecked = Date.now();
      
      if (isDebugEnabled()) {
        console.log('🏥 Connectivity Status:', this.connectivityStatus);
      }
      
    } catch (error) {
      console.warn('⚠️ Health check failed:', error);
    }
  }
  
  private async testEndpoint(baseUrl: string): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${baseUrl}/health`, {
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
  
  private updateCircuitBreaker(baseUrl: string, success: boolean) {
    const key = baseUrl;
    const current = this.circuitBreaker.get(key) || { failures: 0, nextTry: 0 };
    
    if (success) {
      // Reset on success
      this.circuitBreaker.set(key, { failures: 0, nextTry: 0 });
    } else {
      // Increment failures and set next retry time
      const failures = current.failures + 1;
      const backoffDelay = Math.min(300000, 1000 * Math.pow(2, failures)); // Max 5 minutes
      const nextTry = Date.now() + backoffDelay;
      
      this.circuitBreaker.set(key, { failures, nextTry });
      
      if (isDebugEnabled()) {
        console.log(`🚨 Circuit breaker updated for ${baseUrl}:`, { failures, nextTryIn: backoffDelay });
      }
    }
  }
  
  private isCircuitBreakerOpen(baseUrl: string): boolean {
    const state = this.circuitBreaker.get(baseUrl);
    return Boolean(state && state.failures >= 5 && Date.now() < state.nextTry);
  }
  
  async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
    url: string,
    data?: any,
    options: RequestOptions = {}
  ): Promise<T> {
    // Check if we should use cache first
    if (method === 'GET' && !options.skipCache) {
      const cached = apiCache.get<T>(method, url);
      if (cached !== null) {
        if (isDebugEnabled()) {
          console.log(`📋 Cache hit: ${method} ${url}`);
        }
        return cached as T;
      }
    }
    
    let lastError: Error | undefined;
    
    // Try primary API first
    if (this.connectivityStatus.primaryAvailable && !this.isCircuitBreakerOpen(this.config.primaryBaseUrl)) {
      try {
        const response = await this.executeRequest<T>(this.primaryApi, method, url, data, options);
        this.updateCircuitBreaker(this.config.primaryBaseUrl, true);
        
        // Cache successful GET responses
        if (method === 'GET' && !options.skipCache) {
          apiCache.set(method, url, response);
        }
        
        return response;
      } catch (error) {
        lastError = error as Error;
        this.updateCircuitBreaker(this.config.primaryBaseUrl, false);
        
        if (isDebugEnabled()) {
          console.warn(`🔄 Primary API failed, trying fallbacks:`, (error as Error).message);
        }
      }
    }
    
    // Try fallback APIs if enabled
    if (this.config.enableFallback && !options.skipFallback) {
      for (const fallbackApi of this.fallbackApis) {
        const fallbackUrl = fallbackApi.defaults.baseURL || '';
        
        if (!this.connectivityStatus.fallbacksAvailable.includes(fallbackUrl) || 
            this.isCircuitBreakerOpen(fallbackUrl)) {
          continue;
        }
        
        try {
          const response = await this.executeRequest<T>(fallbackApi, method, url, data, options);
          this.updateCircuitBreaker(fallbackUrl, true);
          
          if (isDebugEnabled()) {
            console.log(`✅ Fallback API succeeded: ${fallbackUrl}`);
          }
          
          // Cache successful GET responses
          if (method === 'GET' && !options.skipCache) {
            apiCache.set(method, url, response);
          }
          
          return response;
        } catch (error) {
          lastError = error as Error;
          this.updateCircuitBreaker(fallbackUrl, false);
          
          if (isDebugEnabled()) {
            const errorMessage = (error instanceof Error) ? error.message : String(error);
            console.warn(`🔄 Fallback failed (${fallbackUrl}):`, errorMessage);
          }
        }
      }
    }
    
    // Try offline mode if enabled
    if (this.config.enableOfflineMode && method === 'GET') {
      const offlineData = this.tryOfflineMode<T>(url);
      if (offlineData) {
        console.log(`📱 Using offline data for: ${url}`);
        return offlineData;
      }
    }
    
    // All options exhausted
    const finalError = this.handleFinalError(lastError ?? new Error('All API endpoints failed'));
    
    // Report the error
    errorReporting.reportApiError(
      finalError,
      'smart-api-service',
      {
        url,
        method,
        status: finalError.status || 0,
        statusText: finalError.message
      }
    );
    
    throw finalError;
  }
  
  private async executeRequest<T>(
    api: AxiosInstance,
    method: string,
    url: string,
    data?: any,
    options: RequestOptions = {}
  ): Promise<T> {
    const requestConfig: any = {
      method: method.toLowerCase(),
      url,
      data,
    };
    
    if (options.customTimeout) {
      requestConfig.timeout = options.customTimeout;
    }
    
    let attempt = 0;
    const maxAttempts = options.skipRetry ? 1 : this.config.retryAttempts;
    
    while (attempt < maxAttempts) {
      try {
        const response = await api.request<T>(requestConfig);
        return response.data;
      } catch (error) {
        attempt++;
        
        if (attempt >= maxAttempts) {
          throw error;
        }
        
        // Only retry on network errors or 5xx server errors
        if (isAxiosError(error)) {
          const status = error.response?.status;
          if (status && status >= 400 && status < 500) {
            // Don't retry client errors
            throw error;
          }
        }
        
        // Exponential backoff
        const delay = this.config.retryDelay * Math.pow(2, attempt - 1);
        
        if (isDebugEnabled()) {
          console.log(`⏳ Retry ${attempt}/${maxAttempts} after ${delay}ms`);
        }
        
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    // This should never be reached, but TypeScript requires a return
    throw new Error('All retry attempts failed');
  }
  
  private tryOfflineMode<T>(url: string): T | null {
    try {
      // Try localStorage cache first
      const cacheKey = `offline-${url}`;
      const cached = localStorage.getItem(cacheKey);
      
      if (cached) {
        const data = JSON.parse(cached);
        const maxAge = 5 * 60 * 1000; // 5 minutes
        
        if (Date.now() - data.timestamp < maxAge) {
          return data.value;
        }
      }
      
      // Try API cache as fallback
      return apiCache.get<T>('GET', url) as T;
    } catch {
      return null;
    }
  }
  
  private handleFinalError(error: Error): AppError {
    if (isAxiosError(error)) {
      const status = error.response?.status || 0;
      const message = this.getErrorMessage(error);
      
      const appError: AppError = {
        name: 'ApiError',
        message,
        status,
        details: error.response?.data as Record<string, unknown>
      };
      
      // Only add code if it exists
      if (error.code !== undefined) {
        appError.code = error.code;
      }
      
      return appError;
    }
    
    const networkError: AppError = {
      name: 'NetworkError',
      message: error.message || 'Network connectivity failed',
      status: 0
    };
    
    // Add code property
    networkError.code = 'NETWORK_ERROR';
    
    return networkError;
  }
  
  private getErrorMessage(error: AxiosError): string {
    // Handle specific error scenarios
    if (error.code === 'ECONNREFUSED' || error.message.includes('ECONNREFUSED')) {
      return 'Unable to connect to the server. Please check if the backend service is running or try again later.';
    }
    
    if (error.code === 'ENOTFOUND' || error.message.includes('ENOTFOUND')) {
      return 'Server not found. Please check your network connection and server configuration.';
    }
    
    if (error.code === 'ETIMEDOUT' || error.message.includes('timeout')) {
      return 'Request timed out. The server may be overloaded or your connection is slow.';
    }
    
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;
      
      if (isString(data)) {
        return data;
      }
      
      if (isObject(data)) {
        const message = safeGet(data, 'message', undefined);
        const detail = safeGet(data, 'detail', undefined);
        const errorMsg = safeGet(data, 'error', undefined);
        
        return (isString(message) ? message : null) ||
               (isString(detail) ? detail : null) ||
               (isString(errorMsg) ? errorMsg : null) ||
               `Server error: HTTP ${status}`;
      }
      
      return `HTTP ${status}: ${error.response.statusText}`;
    }
    
    return error.message || 'An unexpected network error occurred';
  }
  
  // Convenience methods
  async get<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', url, undefined, options);
  }
  
  async post<T>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', url, data, options);
  }
  
  async put<T>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', url, data, options);
  }
  
  async delete<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', url, undefined, options);
  }
  
  async patch<T>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PATCH', url, data, options);
  }
  
  // Status and configuration methods
  getConnectivityStatus(): ConnectivityStatus {
    return { ...this.connectivityStatus };
  }
  
  getConfiguration(): SmartApiConfig {
    return { ...this.config };
  }
  
  async testConnectivity(): Promise<boolean> {
    await this.performHealthCheck();
    return this.connectivityStatus.primaryAvailable || 
           this.connectivityStatus.fallbacksAvailable.length > 0;
  }
  
  clearCache(): void {
    apiCache.clear();
  }
  
  resetCircuitBreakers(): void {
    this.circuitBreaker.clear();
  }
  
  // Store data for offline access
  storeForOfflineAccess(url: string, data: any): void {
    try {
      const cacheKey = `offline-${url}`;
      const cacheData = {
        value: data,
        timestamp: Date.now()
      };
      
      localStorage.setItem(cacheKey, JSON.stringify(cacheData));
    } catch (error) {
      console.warn('Failed to store offline data:', error);
    }
  }
}

// Create and export singleton instance
export const smartApiService = new SmartApiService();

// Export the class for testing or advanced usage
export { SmartApiService };

export default smartApiService;