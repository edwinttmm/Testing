/**
 * Runtime Configuration Override System
 * Automatically detects environment and configures appropriate API endpoints
 * This file is loaded before React app initialization to ensure configuration is available
 */

(function() {
  'use strict';
  
  console.log('🔧 Loading unified runtime configuration system...');
  
  // Environment Detection
  const hostname = window.location.hostname;
  const port = window.location.port;
  const protocol = window.location.protocol;
  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
  const isExternalIP = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname);
  
  let environment = 'development';
  let apiHost = hostname;
  let sslEnabled = protocol === 'https:';
  
  // Environment Detection Logic
  if (isLocalhost) {
    environment = 'development';
    apiHost = 'localhost';
  } else if (isExternalIP) {
    // CRITICAL: For localhost development, ALWAYS use localhost for API calls
    // Even when accessing from external IP, the backend runs on localhost
    environment = 'development';  // Changed from 'production' to 'development'
    apiHost = 'localhost';  // CRITICAL: Force localhost for API calls
    console.warn('🔧 EXTERNAL IP DETECTED:', hostname, '-> FORCING localhost for API calls (development mode)');
    console.log('🔧 Original hostname:', hostname, '| Using apiHost:', 'localhost');
  } else if (hostname.includes('155.138.239.131')) {
    // Override for specific IP - force localhost
    environment = 'development';
    apiHost = 'localhost';
    console.warn('🔧 LEGACY IP DETECTED: Redirecting to localhost');
  } else if (hostname.includes('.')) {
    // Domain name detected
    environment = hostname.includes('staging') ? 'staging' : 'production';
    apiHost = hostname;
  }
  
  // Docker Detection
  const isDocker = port === '3000' && (isExternalIP || hostname !== 'localhost');
  
  // Port Configuration
  const ports = {
    frontend: parseInt(port) || (sslEnabled ? 443 : 80),
    backend: 8000,
    websocket: 8000,
    socketio: 8000  // FIXED: Changed from 8001 to 8000 for consistency
  };
  
  // Protocol Configuration
  const apiProtocol = sslEnabled ? 'https' : 'http';
  const wsProtocol = sslEnabled ? 'wss' : 'ws';
  
  // Generate Configuration
  const config = {
    // Environment Information
    REACT_APP_ENVIRONMENT: environment,
    REACT_APP_PLATFORM: isDocker ? 'docker' : 'local',
    REACT_APP_SSL_ENABLED: sslEnabled.toString(),
    
    // API Configuration
    REACT_APP_API_URL: `${apiProtocol}://${apiHost}:${ports.backend}`,
    REACT_APP_WS_URL: `${wsProtocol}://${apiHost}:${ports.websocket}`,
    REACT_APP_SOCKETIO_URL: `${apiProtocol}://${apiHost}:${ports.socketio}`,
    REACT_APP_VIDEO_BASE_URL: `${apiProtocol}://${apiHost}:${ports.backend}`,
    
    // Feature Flags
    REACT_APP_DEBUG: (environment === 'development').toString(),
    REACT_APP_ANALYTICS: (environment === 'production').toString(),
    REACT_APP_MONITORING: (environment !== 'development').toString(),
    REACT_APP_CACHING: 'true',
    
    // Performance Configuration
    REACT_APP_REQUEST_TIMEOUT: environment === 'production' ? '30000' : '10000',
    REACT_APP_MAX_RETRIES: environment === 'production' ? '3' : '1',
    
    // Logging Configuration
    REACT_APP_LOG_LEVEL: environment === 'production' ? 'warn' : 'debug',
    REACT_APP_STRUCTURED_LOGS: (environment === 'production').toString(),
    
    // Security Configuration
    REACT_APP_CSP_ENABLED: (environment === 'production').toString(),
    REACT_APP_SECURITY_HEADERS: (environment !== 'development').toString(),

    // Optional: service token for trusted internal use; can also be provided via localStorage('api_token')
    REACT_APP_API_TOKEN: 'st_v1_0t7C9mQ2wX5pL8rS1uV4yB7dE0gH3kN6qT9zA2fJ5mR8xC1vD4pF7sG0jK3n'
  };
  
  // Apply Runtime Configuration
  window.RUNTIME_CONFIG = config;

  // If a token exists in localStorage (dev convenience), surface it via runtime config
  try {
    const lsToken = localStorage.getItem('api_token') || localStorage.getItem('access_token');
    if (lsToken) {
      window.RUNTIME_CONFIG.REACT_APP_API_TOKEN = lsToken;
      process.env.REACT_APP_API_TOKEN = lsToken;
    }
  } catch (e) {
    // ignore
  }
  
  // Ensure process.env exists for compatibility
  if (typeof process === 'undefined') {
    window.process = { env: {} };
  }
  
  // Apply configuration to process.env
  Object.assign(process.env, config);
  
  // CRITICAL CONFIGURATION LOGGING
  console.group('🔧 CONFIGURATION ANALYSIS');
  console.log('Original hostname detected:', hostname);
  console.log('Is localhost?', isLocalhost);
  console.log('Is external IP?', isExternalIP);
  console.log('Resolved apiHost:', apiHost);
  console.log('Final API URL:', config.REACT_APP_API_URL);
  console.groupEnd();
  
  console.log('✅ Runtime configuration applied:', {
    originalHostname: hostname,
    isLocalhost,
    isExternalIP,
    environment,
    platform: isDocker ? 'docker' : 'local',
    resolvedApiHost: apiHost,
    sslEnabled,
    ports,
    finalApiURL: config.REACT_APP_API_URL
  });
  
  // WARNING if still using external IP
  if (config.REACT_APP_API_URL.includes('155.138.239.131')) {
    console.error('🚨 CRITICAL ERROR: API URL still contains external IP!', config.REACT_APP_API_URL);
    console.error('🚨 This will cause connection failures!');
  } else {
    console.log('✅ API URL correctly uses localhost:', config.REACT_APP_API_URL);
  }
  
  // Configuration Validation (async)
  setTimeout(() => {
    validateConfiguration(config);
  }, 1000);
  
  // Enhanced Configuration Validation
  function validateConfiguration(config) {
    console.log('🧪 Validating runtime configuration...');
    
    const validationResults = [];
    
    // 1. Test API Connectivity
    testAPIConnectivity(config.REACT_APP_API_URL)
      .then(result => {
        validationResults.push({ test: 'API Connectivity', ...result });
        logValidationResults();
      });
    
    // 2. Validate URL Formats
    const urlTests = [
      { name: 'API URL', url: config.REACT_APP_API_URL },
      { name: 'WebSocket URL', url: config.REACT_APP_WS_URL },
      { name: 'SocketIO URL', url: config.REACT_APP_SOCKETIO_URL }
    ];
    
    urlTests.forEach(({ name, url }) => {
      try {
        new URL(url);
        validationResults.push({ test: name, passed: true, message: 'Valid URL format' });
      } catch (error) {
        validationResults.push({ test: name, passed: false, message: `Invalid URL: ${url}` });
      }
    });
    
    // 3. Check Configuration Completeness
    const requiredKeys = [
      'REACT_APP_API_URL',
      'REACT_APP_WS_URL', 
      'REACT_APP_SOCKETIO_URL',
      'REACT_APP_ENVIRONMENT'
    ];
    
    const missingKeys = requiredKeys.filter(key => !config[key]);
    if (missingKeys.length === 0) {
      validationResults.push({ test: 'Configuration Completeness', passed: true, message: 'All required keys present' });
    } else {
      validationResults.push({ test: 'Configuration Completeness', passed: false, message: `Missing keys: ${missingKeys.join(', ')}` });
    }
    
    // 4. Environment-Specific Validations
    if (environment === 'production') {
      const productionChecks = [
        { test: 'Debug Mode', passed: config.REACT_APP_DEBUG === 'false', message: 'Debug mode should be disabled in production' },
        { test: 'Analytics', passed: config.REACT_APP_ANALYTICS === 'true', message: 'Analytics should be enabled in production' },
        { test: 'SSL Check', passed: sslEnabled || hostname === 'localhost', message: 'SSL recommended for production' }
      ];
      
      validationResults.push(...productionChecks);
    }
    
    function logValidationResults() {
      const passed = validationResults.filter(r => r.passed);
      const failed = validationResults.filter(r => !r.passed);
      
      console.group('📊 Configuration Validation Results');
      console.log(`✅ Passed: ${passed.length}`);
      console.log(`❌ Failed: ${failed.length}`);
      
      if (failed.length > 0) {
        console.group('❌ Failed Tests');
        failed.forEach(({ test, message }) => {
          console.warn(`${test}: ${message}`);
        });
        console.groupEnd();
      }
      
      if (config.REACT_APP_DEBUG === 'true') {
        console.group('📋 All Results');
        validationResults.forEach(({ test, passed, message }) => {
          console.log(`${passed ? '✅' : '❌'} ${test}: ${message}`);
        });
        console.groupEnd();
      }
      
      console.groupEnd();
    }
  }
  
  // API Connectivity Test
  async function testAPIConnectivity(apiURL) {
    try {
      console.log(`🔗 Testing API connectivity: ${apiURL}/health`);
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${apiURL}/health`, { 
        method: 'GET',
        signal: controller.signal,
        mode: 'cors'
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        console.log('✅ API connectivity test passed');
        return { passed: true, message: 'API is accessible' };
      } else {
        console.warn(`⚠️ API connectivity test failed: ${response.status} ${response.statusText}`);
        return { passed: false, message: `API returned status: ${response.status}` };
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.warn('⚠️ API connectivity test timed out');
        return { passed: false, message: 'API request timed out' };
      } else {
        console.warn('⚠️ API connectivity test error:', error.message);
        return { passed: false, message: `API test error: ${error.message}` };
      }
    }
  }
  
  // CORS Test Helper
  window.testCORSConfiguration = function() {
    console.group('🔍 CORS Configuration Test');
    console.log('Current Origin:', window.location.origin);
    console.log('API URL:', config.REACT_APP_API_URL);
    console.log('WebSocket URL:', config.REACT_APP_WS_URL);
    
    // Test CORS preflight
    testAPIConnectivity(config.REACT_APP_API_URL + '/cors/test')
      .then(result => {
        console.log('CORS Test Result:', result);
      });
    
    console.groupEnd();
  };
  
  // Configuration Update Helper (for development)
  window.updateRuntimeConfig = function(updates) {
    console.log('🔄 Updating runtime configuration:', updates);
    
    Object.assign(window.RUNTIME_CONFIG, updates);
    Object.assign(process.env, updates);
    
    console.log('✅ Runtime configuration updated');
    
    // Trigger configuration re-validation
    setTimeout(() => validateConfiguration(window.RUNTIME_CONFIG), 100);
  };
  
  // Development helpers
  if (environment === 'development') {
    window.configDebug = {
      showConfig: () => console.log('Current Config:', window.RUNTIME_CONFIG),
      testAPI: () => testAPIConnectivity(config.REACT_APP_API_URL),
      testCORS: window.testCORSConfiguration,
      updateConfig: window.updateRuntimeConfig
    };
    
    console.log('🛠️ Development helpers available at window.configDebug');
  }
  
  // Export configuration for other scripts
  window.getConfig = function() {
    return { ...window.RUNTIME_CONFIG };
  };
  
  // GLOBAL API URL OVERRIDE SYSTEM
  // This intercepts any API calls that might still use the wrong URL
  const originalFetch = window.fetch;
  window.fetch = function(url, options) {
    // If URL contains the external IP, force redirect to localhost
    if (typeof url === 'string' && url.includes('155.138.239.131')) {
      console.warn('🚨 INTERCEPTED API call with external IP:', url);
      url = url.replace('155.138.239.131', 'localhost');
      console.log('✅ REDIRECTED to localhost:', url);
    }
    return originalFetch.call(this, url, options);
  };
  
  // Also override XMLHttpRequest for any legacy code
  const originalXHROpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, ...args) {
    if (typeof url === 'string' && url.includes('155.138.239.131')) {
      console.warn('🚨 INTERCEPTED XHR call with external IP:', url);
      url = url.replace('155.138.239.131', 'localhost');
      console.log('✅ REDIRECTED XHR to localhost:', url);
    }
    return originalXHROpen.call(this, method, url, ...args);
  };
  
  console.log('✅ Runtime configuration system initialized');
  console.log('🔧 Global API URL override system activated');
  
  // Force immediate configuration check
  setTimeout(() => {
    console.log('🔍 Final configuration check:');
    console.log('window.RUNTIME_CONFIG.REACT_APP_API_URL:', window.RUNTIME_CONFIG?.REACT_APP_API_URL);
    console.log('process.env.REACT_APP_API_URL:', process.env?.REACT_APP_API_URL);
    
    if (window.RUNTIME_CONFIG?.REACT_APP_API_URL?.includes('155.138.239.131')) {
      console.error('🚨 CONFIGURATION ERROR: Still using external IP!');
    } else {
      console.log('✅ Configuration correct: Using localhost');
    }
  }, 100);
  
})();
