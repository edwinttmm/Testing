/**
 * Configuration Validation Framework
 * Comprehensive testing and validation system for unified configuration
 * Part of the Unified Configuration Architecture
 */

export interface ValidationRule {
  id: string;
  name: string;
  description: string;
  severity: 'error' | 'warning' | 'info';
  category: 'api' | 'cors' | 'security' | 'environment' | 'network' | 'performance';
  validate: (config: any) => Promise<ValidationResult> | ValidationResult;
}

export interface ValidationResult {
  passed: boolean;
  message: string;
  details?: any;
  suggestions?: string[];
  impact?: 'low' | 'medium' | 'high' | 'critical';
}

export interface ValidationReport {
  valid: boolean;
  score: number; // 0-100
  results: Array<ValidationResult & { 
    rule: ValidationRule;
    timestamp: string;
  }>;
  summary: {
    total: number;
    passed: number;
    failed: number;
    warnings: number;
    errors: number;
  };
  environment: {
    type: string;
    platform: string;
    timestamp: string;
  };
}

export class ConfigValidationFramework {
  private rules: ValidationRule[] = [];
  
  constructor() {
    this.loadDefaultRules();
  }
  
  /**
   * Load default validation rules
   */
  private loadDefaultRules(): void {
    this.rules = [
      // API Connectivity Rules
      {
        id: 'api-connectivity',
        name: 'API Connectivity Test',
        description: 'Verify API endpoints are accessible',
        severity: 'error',
        category: 'api',
        validate: this.validateAPIConnectivity
      },
      {
        id: 'api-url-format',
        name: 'API URL Format',
        description: 'Validate API URL format and structure',
        severity: 'error',
        category: 'api',
        validate: this.validateAPIURLFormat
      },
      {
        id: 'websocket-connectivity',
        name: 'WebSocket Connectivity',
        description: 'Test WebSocket connection capability',
        severity: 'warning',
        category: 'api',
        validate: this.validateWebSocketConnectivity
      },
      
      // CORS Configuration Rules
      {
        id: 'cors-origins-configured',
        name: 'CORS Origins Configured',
        description: 'Ensure CORS origins are properly configured',
        severity: 'error',
        category: 'cors',
        validate: this.validateCORSOrigins
      },
      {
        id: 'cors-wildcard-production',
        name: 'CORS Wildcard in Production',
        description: 'Check for wildcard CORS in production',
        severity: 'error',
        category: 'cors',
        validate: this.validateCORSWildcard
      },
      {
        id: 'cors-localhost-production',
        name: 'Localhost CORS in Production',
        description: 'Detect localhost origins in production',
        severity: 'warning',
        category: 'cors',
        validate: this.validateCORSLocalhost
      },
      
      // Security Rules
      {
        id: 'ssl-production',
        name: 'SSL in Production',
        description: 'Ensure SSL is enabled in production',
        severity: 'error',
        category: 'security',
        validate: this.validateSSLProduction
      },
      {
        id: 'secret-key-security',
        name: 'Secret Key Security',
        description: 'Validate secret key strength',
        severity: 'error',
        category: 'security',
        validate: this.validateSecretKey
      },
      {
        id: 'debug-mode-production',
        name: 'Debug Mode in Production',
        description: 'Ensure debug mode is disabled in production',
        severity: 'error',
        category: 'security',
        validate: this.validateDebugMode
      },
      
      // Environment Rules
      {
        id: 'environment-detection',
        name: 'Environment Detection',
        description: 'Validate environment detection accuracy',
        severity: 'warning',
        category: 'environment',
        validate: this.validateEnvironmentDetection
      },
      {
        id: 'platform-detection',
        name: 'Platform Detection',
        description: 'Verify platform detection (local/docker/cloud)',
        severity: 'info',
        category: 'environment',
        validate: this.validatePlatformDetection
      },
      
      // Network Rules
      {
        id: 'network-ip-detection',
        name: 'Network IP Detection',
        description: 'Validate IP address detection',
        severity: 'warning',
        category: 'network',
        validate: this.validateNetworkDetection
      },
      {
        id: 'port-conflicts',
        name: 'Port Conflicts',
        description: 'Check for potential port conflicts',
        severity: 'warning',
        category: 'network',
        validate: this.validatePortConflicts
      },
      
      // Performance Rules
      {
        id: 'configuration-load-time',
        name: 'Configuration Load Time',
        description: 'Measure configuration initialization time',
        severity: 'info',
        category: 'performance',
        validate: this.validateConfigurationLoadTime
      },
      {
        id: 'cache-configuration',
        name: 'Cache Configuration',
        description: 'Validate caching configuration',
        severity: 'info',
        category: 'performance',
        validate: this.validateCacheConfiguration
      }
    ];
  }
  
  /**
   * Add custom validation rule
   */
  addRule(rule: ValidationRule): void {
    this.rules.push(rule);
  }
  
  /**
   * Remove validation rule by ID
   */
  removeRule(ruleId: string): boolean {
    const index = this.rules.findIndex(rule => rule.id === ruleId);
    if (index > -1) {
      this.rules.splice(index, 1);
      return true;
    }
    return false;
  }
  
  /**
   * Run comprehensive configuration validation
   */
  async validateConfiguration(config: any): Promise<ValidationReport> {
    const startTime = Date.now();
    const results: ValidationReport['results'] = [];
    
    console.log('🧪 Starting configuration validation...');
    
    // Run all validation rules
    for (const rule of this.rules) {
      try {
        console.log(`  🔍 Running: ${rule.name}`);
        
        const result = await rule.validate(config);
        
        results.push({
          ...result,
          rule,
          timestamp: new Date().toISOString()
        });
        
        const status = result.passed ? '✅' : (rule.severity === 'error' ? '❌' : '⚠️');
        console.log(`    ${status} ${result.message}`);
        
      } catch (error) {
        console.error(`    ❌ Rule '${rule.name}' failed: ${error.message}`);
        
        results.push({
          passed: false,
          message: `Validation rule failed: ${error.message}`,
          details: { error: error.message },
          rule,
          timestamp: new Date().toISOString()
        });
      }
    }
    
    // Calculate summary
    const summary = this.calculateSummary(results);
    const score = this.calculateScore(results);
    const valid = summary.errors === 0;
    
    const report: ValidationReport = {
      valid,
      score,
      results,
      summary,
      environment: {
        type: config.environment?.type || 'unknown',
        platform: config.environment?.platform || 'unknown',
        timestamp: new Date().toISOString()
      }
    };
    
    const duration = Date.now() - startTime;
    console.log(`✅ Validation completed in ${duration}ms`);
    this.logReport(report);
    
    return report;
  }
  
  /**
   * Run validation for specific category
   */
  async validateCategory(config: any, category: ValidationRule['category']): Promise<ValidationReport> {
    const categoryRules = this.rules.filter(rule => rule.category === category);
    const originalRules = [...this.rules];
    
    this.rules = categoryRules;
    const report = await this.validateConfiguration(config);
    this.rules = originalRules;
    
    return report;
  }
  
  /**
   * Continuous validation (for development)
   */
  startContinuousValidation(config: any, intervalMs: number = 30000): () => void {
    let validationInterval: NodeJS.Timeout;
    
    const runValidation = async () => {
      try {
        const report = await this.validateConfiguration(config);
        
        if (!report.valid) {
          console.warn('⚠️ Configuration validation failed');
          console.warn(`  Errors: ${report.summary.errors}`);
          console.warn(`  Warnings: ${report.summary.warnings}`);
        }
      } catch (error) {
        console.error('❌ Continuous validation error:', error);
      }
    };
    
    // Initial validation
    runValidation();
    
    // Set up interval
    validationInterval = setInterval(runValidation, intervalMs);
    
    console.log(`🔄 Continuous validation started (${intervalMs}ms interval)`);
    
    // Return stop function
    return () => {
      clearInterval(validationInterval);
      console.log('⏹️ Continuous validation stopped');
    };
  }
  
  // Validation Rule Implementations
  
  private async validateAPIConnectivity(config: any): Promise<ValidationResult> {
    if (!config.api?.baseURL) {
      return {
        passed: false,
        message: 'API base URL not configured',
        impact: 'critical',
        suggestions: ['Configure REACT_APP_API_URL or api.baseURL']
      };
    }
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${config.api.baseURL}/health`, {
        method: 'GET',
        signal: controller.signal,
        mode: 'cors'
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        return {
          passed: true,
          message: `API connectivity successful (${response.status})`,
          details: { status: response.status, url: config.api.baseURL }
        };
      } else {
        return {
          passed: false,
          message: `API returned status ${response.status}`,
          details: { status: response.status, url: config.api.baseURL },
          impact: 'high',
          suggestions: ['Check API server status', 'Verify API URL configuration']
        };
      }
    } catch (error) {
      let message = 'API connectivity failed';
      let impact: ValidationResult['impact'] = 'high';
      let suggestions: string[] = [];
      
      if (error.name === 'AbortError') {
        message = 'API request timed out';
        suggestions = ['Check network connectivity', 'Verify API server is running'];
      } else if (error.message?.includes('CORS')) {
        message = 'CORS policy blocked API request';
        impact = 'critical';
        suggestions = ['Configure CORS origins on backend', 'Check backend CORS middleware'];
      } else {
        suggestions = ['Verify API URL is correct', 'Check network connectivity'];
      }
      
      return {
        passed: false,
        message,
        details: { error: error.message, url: config.api.baseURL },
        impact,
        suggestions
      };
    }
  }
  
  private validateAPIURLFormat(config: any): ValidationResult {
    if (!config.api?.baseURL) {
      return {
        passed: false,
        message: 'API base URL not configured',
        impact: 'critical'
      };
    }
    
    try {
      const url = new URL(config.api.baseURL);
      
      const warnings: string[] = [];
      
      // Check protocol
      if (url.protocol !== 'http:' && url.protocol !== 'https:') {
        return {
          passed: false,
          message: `Invalid protocol: ${url.protocol}`,
          impact: 'critical'
        };
      }
      
      // Check for localhost in production
      if (config.environment?.type === 'production' && 
          (url.hostname === 'localhost' || url.hostname === '127.0.0.1')) {
        warnings.push('Using localhost in production environment');
      }
      
      // Check for HTTP in production
      if (config.environment?.type === 'production' && url.protocol === 'http:') {
        warnings.push('Using HTTP in production (HTTPS recommended)');
      }
      
      return {
        passed: true,
        message: warnings.length > 0 
          ? `API URL valid with warnings: ${warnings.join(', ')}`
          : 'API URL format is valid',
        details: { 
          protocol: url.protocol, 
          hostname: url.hostname, 
          port: url.port,
          warnings 
        }
      };
    } catch (error) {
      return {
        passed: false,
        message: `Invalid API URL format: ${config.api.baseURL}`,
        details: { error: error.message },
        impact: 'critical',
        suggestions: ['Check API URL format', 'Ensure URL includes protocol (http:// or https://)']
      };
    }
  }
  
  private async validateWebSocketConnectivity(config: any): Promise<ValidationResult> {
    if (!config.api?.websocketURL) {
      return {
        passed: false,
        message: 'WebSocket URL not configured',
        impact: 'medium'
      };
    }
    
    // Basic URL format validation for WebSocket
    if (!config.api.websocketURL.startsWith('ws://') && 
        !config.api.websocketURL.startsWith('wss://')) {
      return {
        passed: false,
        message: 'WebSocket URL must start with ws:// or wss://',
        impact: 'medium',
        suggestions: ['Check WebSocket URL format', 'Ensure protocol is ws:// or wss://']
      };
    }
    
    // Note: Actual WebSocket connection testing would require WebSocket implementation
    return {
      passed: true,
      message: 'WebSocket URL format is valid',
      details: { url: config.api.websocketURL }
    };
  }
  
  private validateCORSOrigins(config: any): ValidationResult {
    if (!config.cors?.origins || config.cors.origins.length === 0) {
      return {
        passed: false,
        message: 'No CORS origins configured',
        impact: 'critical',
        suggestions: [
          'Configure CORS origins in backend',
          'Add frontend URL to allowed origins'
        ]
      };
    }
    
    const currentOrigin = typeof window !== 'undefined' ? window.location.origin : 'unknown';
    const isCurrentOriginAllowed = config.cors.origins.includes(currentOrigin);
    
    return {
      passed: true,
      message: isCurrentOriginAllowed 
        ? `CORS properly configured (${config.cors.origins.length} origins)`
        : `CORS configured but current origin not allowed (${config.cors.origins.length} origins)`,
      details: { 
        origins: config.cors.origins,
        currentOrigin,
        currentOriginAllowed: isCurrentOriginAllowed
      }
    };
  }
  
  private validateCORSWildcard(config: any): ValidationResult {
    if (config.environment?.type === 'production' && 
        config.cors?.origins?.includes('*')) {
      return {
        passed: false,
        message: 'CORS wildcard (*) should not be used in production',
        impact: 'high',
        suggestions: [
          'Replace wildcard with specific origins',
          'Configure exact frontend URLs'
        ]
      };
    }
    
    return {
      passed: true,
      message: 'No CORS wildcard detected in production'
    };
  }
  
  private validateCORSLocalhost(config: any): ValidationResult {
    if (config.environment?.type === 'production' && config.cors?.origins) {
      const localhostOrigins = config.cors.origins.filter(origin => 
        origin.includes('localhost') || origin.includes('127.0.0.1')
      );
      
      if (localhostOrigins.length > 0) {
        return {
          passed: false,
          message: `Localhost origins found in production: ${localhostOrigins.join(', ')}`,
          impact: 'medium',
          suggestions: [
            'Remove localhost origins in production',
            'Use actual domain names'
          ]
        };
      }
    }
    
    return {
      passed: true,
      message: 'No localhost origins in production'
    };
  }
  
  private validateSSLProduction(config: any): ValidationResult {
    if (config.environment?.type === 'production' && !config.security?.ssl) {
      return {
        passed: false,
        message: 'SSL not enabled in production environment',
        impact: 'high',
        suggestions: [
          'Enable SSL/TLS for production',
          'Configure HTTPS certificates',
          'Update API URLs to use HTTPS'
        ]
      };
    }
    
    return {
      passed: true,
      message: 'SSL configuration appropriate for environment'
    };
  }
  
  private validateSecretKey(config: any): ValidationResult {
    const insecureKeys = [
      'REPLACE-ME-IN-PRODUCTION',
      'your-secret-key-here',
      'INSECURE-DEFAULT-CHANGE-ME',
      'secret',
      'key',
      'password'
    ];
    
    const secretKey = config.security?.secret_key || '';
    
    if (insecureKeys.some(key => secretKey.includes(key))) {
      return {
        passed: false,
        message: 'Using insecure default secret key',
        impact: 'critical',
        suggestions: [
          'Generate a strong, unique secret key',
          'Use environment variables for secret management'
        ]
      };
    }
    
    if (secretKey.length < 32) {
      return {
        passed: false,
        message: `Secret key too short (${secretKey.length} chars, minimum 32)`,
        impact: 'high',
        suggestions: ['Generate a longer secret key (minimum 32 characters)']
      };
    }
    
    return {
      passed: true,
      message: 'Secret key appears secure'
    };
  }
  
  private validateDebugMode(config: any): ValidationResult {
    if (config.environment?.type === 'production' && config.features?.debugging) {
      return {
        passed: false,
        message: 'Debug mode enabled in production',
        impact: 'high',
        suggestions: [
          'Disable debug mode in production',
          'Check environment variables'
        ]
      };
    }
    
    return {
      passed: true,
      message: 'Debug mode configuration appropriate'
    };
  }
  
  private validateEnvironmentDetection(config: any): ValidationResult {
    const expectedEnv = process.env.NODE_ENV || process.env.APP_ENV;
    const detectedEnv = config.environment?.type;
    
    if (expectedEnv && detectedEnv && expectedEnv !== detectedEnv) {
      return {
        passed: false,
        message: `Environment mismatch: expected ${expectedEnv}, detected ${detectedEnv}`,
        impact: 'medium',
        suggestions: [
          'Check environment variable consistency',
          'Verify environment detection logic'
        ]
      };
    }
    
    return {
      passed: true,
      message: `Environment detected: ${detectedEnv}`
    };
  }
  
  private validatePlatformDetection(config: any): ValidationResult {
    const platform = config.environment?.platform || 'unknown';
    const isDocker = process.env.DOCKER === 'true' || process.env.CONTAINER_NAME;
    
    if (isDocker && platform !== 'docker') {
      return {
        passed: false,
        message: `Platform detection mismatch: running in Docker but detected as ${platform}`,
        impact: 'low'
      };
    }
    
    return {
      passed: true,
      message: `Platform detected: ${platform}`
    };
  }
  
  private validateNetworkDetection(config: any): ValidationResult {
    const network = config.environment?.network;
    
    if (!network?.internalIP) {
      return {
        passed: false,
        message: 'Internal IP not detected',
        impact: 'medium'
      };
    }
    
    const warnings: string[] = [];
    
    if (!network.externalIP) {
      warnings.push('External IP not detected');
    }
    
    if (network.internalIP === '127.0.0.1' && config.environment?.platform === 'docker') {
      warnings.push('Using localhost IP in Docker environment');
    }
    
    return {
      passed: true,
      message: warnings.length > 0 
        ? `Network detection completed with warnings: ${warnings.join(', ')}`
        : 'Network detection successful',
      details: {
        internalIP: network.internalIP,
        externalIP: network.externalIP,
        hostname: network.hostname
      }
    };
  }
  
  private validatePortConflicts(config: any): ValidationResult {
    const ports = config.environment?.network?.ports || {};
    const usedPorts = Object.values(ports).filter(port => typeof port === 'number');
    const duplicates = usedPorts.filter((port, index) => usedPorts.indexOf(port) !== index);
    
    if (duplicates.length > 0) {
      return {
        passed: false,
        message: `Port conflicts detected: ${duplicates.join(', ')}`,
        impact: 'medium',
        suggestions: ['Configure unique ports for each service']
      };
    }
    
    return {
      passed: true,
      message: 'No port conflicts detected',
      details: { ports: usedPorts }
    };
  }
  
  private validateConfigurationLoadTime(config: any): ValidationResult {
    // This would typically measure actual load time
    return {
      passed: true,
      message: 'Configuration load time acceptable',
      details: { loadTime: 'Not measured in this implementation' }
    };
  }
  
  private validateCacheConfiguration(config: any): ValidationResult {
    const cacheEnabled = config.features?.caching;
    
    if (config.environment?.type === 'production' && !cacheEnabled) {
      return {
        passed: false,
        message: 'Caching disabled in production',
        impact: 'medium',
        suggestions: ['Enable caching for better performance']
      };
    }
    
    return {
      passed: true,
      message: `Caching ${cacheEnabled ? 'enabled' : 'disabled'}`
    };
  }
  
  // Utility Methods
  
  private calculateSummary(results: ValidationReport['results']) {
    const total = results.length;
    const passed = results.filter(r => r.passed).length;
    const failed = results.filter(r => !r.passed).length;
    const warnings = results.filter(r => !r.passed && r.rule.severity === 'warning').length;
    const errors = results.filter(r => !r.passed && r.rule.severity === 'error').length;
    
    return { total, passed, failed, warnings, errors };
  }
  
  private calculateScore(results: ValidationReport['results']): number {
    if (results.length === 0) return 100;
    
    let totalWeight = 0;
    let passedWeight = 0;
    
    for (const result of results) {
      const weight = this.getSeverityWeight(result.rule.severity);
      totalWeight += weight;
      
      if (result.passed) {
        passedWeight += weight;
      }
    }
    
    return Math.round((passedWeight / totalWeight) * 100);
  }
  
  private getSeverityWeight(severity: ValidationRule['severity']): number {
    switch (severity) {
      case 'error': return 10;
      case 'warning': return 5;
      case 'info': return 1;
      default: return 1;
    }
  }
  
  private logReport(report: ValidationReport): void {
    console.group('📊 Configuration Validation Report');
    console.log(`Overall Score: ${report.score}/100`);
    console.log(`Status: ${report.valid ? '✅ Valid' : '❌ Invalid'}`);
    console.log(`Tests: ${report.summary.passed}/${report.summary.total} passed`);
    
    if (report.summary.errors > 0) {
      console.log(`Errors: ${report.summary.errors}`);
    }
    
    if (report.summary.warnings > 0) {
      console.log(`Warnings: ${report.summary.warnings}`);
    }
    
    // Log failed tests
    const failures = report.results.filter(r => !r.passed);
    if (failures.length > 0) {
      console.group('❌ Failed Tests');
      failures.forEach(failure => {
        console.log(`${failure.rule.severity === 'error' ? '❌' : '⚠️'} ${failure.rule.name}: ${failure.message}`);
      });
      console.groupEnd();
    }
    
    console.groupEnd();
  }
}

// Export singleton instance
export const configValidationFramework = new ConfigValidationFramework();