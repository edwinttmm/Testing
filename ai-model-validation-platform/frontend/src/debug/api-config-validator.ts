/**
 * API Configuration Validator
 * Comprehensive tool to diagnose and fix API configuration issues
 */

interface ConfigDiagnostic {
  test: string;
  status: 'PASS' | 'FAIL' | 'WARN';
  message: string;
  details?: any;
}

export class ApiConfigValidator {
  private diagnostics: ConfigDiagnostic[] = [];

  async runDiagnostics(): Promise<ConfigDiagnostic[]> {
    this.diagnostics = [];
    
    // Test 1: Runtime Config Loading
    this.testRuntimeConfigLoading();
    
    // Test 2: Process.env Override
    this.testProcessEnvOverride();
    
    // Test 3: API Service Configuration
    await this.testApiServiceConfig();
    
    // Test 4: Network Connectivity
    await this.testNetworkConnectivity();
    
    // Test 5: Module Load Order
    this.testModuleLoadOrder();
    
    return this.diagnostics;
  }

  private testRuntimeConfigLoading(): void {
    const hasRuntimeConfig = typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG;
    
    if (hasRuntimeConfig) {
      const config = (window as any).RUNTIME_CONFIG;
      this.diagnostics.push({
        test: 'Runtime Config Loading',
        status: 'PASS',
        message: 'window.RUNTIME_CONFIG is loaded correctly',
        details: config
      });
    } else {
      this.diagnostics.push({
        test: 'Runtime Config Loading',
        status: 'FAIL',
        message: 'window.RUNTIME_CONFIG is not available - config.js may not be loaded',
      });
    }
  }

  private testProcessEnvOverride(): void {
    const expectedApiUrl = 'http://155.138.239.131:8000';
    const actualApiUrl = process.env.REACT_APP_API_URL;
    
    if (actualApiUrl === expectedApiUrl) {
      this.diagnostics.push({
        test: 'Process.env Override',
        status: 'PASS',
        message: 'process.env.REACT_APP_API_URL correctly overridden',
        details: { expected: expectedApiUrl, actual: actualApiUrl }
      });
    } else if (actualApiUrl) {
      this.diagnostics.push({
        test: 'Process.env Override',
        status: 'WARN',
        message: 'process.env.REACT_APP_API_URL is set but not to expected value',
        details: { expected: expectedApiUrl, actual: actualApiUrl }
      });
    } else {
      this.diagnostics.push({
        test: 'Process.env Override',
        status: 'FAIL',
        message: 'process.env.REACT_APP_API_URL is not set - runtime config override failed',
        details: { expected: expectedApiUrl, actual: actualApiUrl }
      });
    }
  }

  private async testApiServiceConfig(): Promise<void> {
    try {
      // Dynamic import to avoid circular dependencies
      const { apiService } = await import('../services/api');
      const config = apiService.getConfiguration();
      
      const expectedUrl = 'http://155.138.239.131:8000';
      if (config.baseURL === expectedUrl) {
        this.diagnostics.push({
          test: 'API Service Configuration',
          status: 'PASS',
          message: 'API service configured with correct base URL',
          details: config
        });
      } else {
        this.diagnostics.push({
          test: 'API Service Configuration',
          status: 'FAIL',
          message: 'API service configured with wrong base URL',
          details: { expected: expectedUrl, actual: config.baseURL, fullConfig: config }
        });
      }
    } catch (error) {
      this.diagnostics.push({
        test: 'API Service Configuration',
        status: 'FAIL',
        message: 'Failed to get API service configuration',
        details: { error: error instanceof Error ? error.message : String(error) }
      });
    }
  }

  private async testNetworkConnectivity(): Promise<void> {
    const testUrls = [
      'http://155.138.239.131:8000/health',
      'http://localhost:8000/health'
    ];

    for (const url of testUrls) {
      try {
        const response = await fetch(url, { 
          method: 'HEAD', 
          signal: AbortSignal.timeout(5000) 
        });
        
        this.diagnostics.push({
          test: `Network Connectivity - ${url}`,
          status: 'PASS',
          message: `Successfully connected to ${url}`,
          details: { status: response.status, statusText: response.statusText }
        });
      } catch (error: any) {
        this.diagnostics.push({
          test: `Network Connectivity - ${url}`,
          status: url.includes('localhost') ? 'WARN' : 'FAIL',
          message: `Failed to connect to ${url}`,
          details: { error: error instanceof Error ? error.message : String(error) }
        });
      }
    }
  }

  private testModuleLoadOrder(): void {
    // Check if config.js script is loaded before React bundle
    const scripts = Array.from(document.querySelectorAll('script'));
    const configScript = scripts.find(s => s.src.includes('config.js'));
    const reactScript = scripts.find(s => s.src.includes('bundle.js') || s.src.includes('main.'));
    
    if (configScript && reactScript) {
      const configIndex = scripts.indexOf(configScript);
      const reactIndex = scripts.indexOf(reactScript);
      
      if (configIndex < reactIndex) {
        this.diagnostics.push({
          test: 'Module Load Order',
          status: 'PASS',
          message: 'config.js loads before React bundle - correct order',
        });
      } else {
        this.diagnostics.push({
          test: 'Module Load Order',
          status: 'FAIL',
          message: 'config.js loads after React bundle - incorrect order',
          details: { configIndex, reactIndex }
        });
      }
    } else {
      this.diagnostics.push({
        test: 'Module Load Order',
        status: 'WARN',
        message: 'Cannot determine script load order',
        details: { configScript: !!configScript, reactScript: !!reactScript }
      });
    }
  }

  printReport(): void {
    console.log('=== API Configuration Diagnostic Report ===');
    
    const passed = this.diagnostics.filter(d => d.status === 'PASS').length;
    const failed = this.diagnostics.filter(d => d.status === 'FAIL').length;
    const warnings = this.diagnostics.filter(d => d.status === 'WARN').length;
    
    console.log(`\nSummary: ${passed} PASS, ${failed} FAIL, ${warnings} WARN\n`);
    
    this.diagnostics.forEach(diagnostic => {
      const icon = diagnostic.status === 'PASS' ? '✅' : 
                  diagnostic.status === 'FAIL' ? '❌' : '⚠️';
      
      console.log(`${icon} ${diagnostic.test}: ${diagnostic.message}`);
      if (diagnostic.details) {
        console.log('   Details:', diagnostic.details);
      }
    });
    
    // Recommendations
    console.log('\n=== Recommendations ===');
    
    const failedTests = this.diagnostics.filter(d => d.status === 'FAIL');
    if (failedTests.some(t => t.test === 'Runtime Config Loading')) {
      console.log('🔧 Ensure public/config.js is accessible and loaded in HTML');
    }
    
    if (failedTests.some(t => t.test === 'Process.env Override')) {
      console.log('🔧 Configuration is now handled automatically by configurationManager');
    }
    
    if (failedTests.some(t => t.test === 'API Service Configuration')) {
      console.log('🔧 API service may be instantiated before runtime config is applied');
    }
    
    if (failedTests.some(t => t.test.includes('Network Connectivity'))) {
      console.log('🔧 Check if backend server is running and accessible');
    }
  }
}

// Usage functions
export async function runConfigDiagnostics(): Promise<void> {
  const validator = new ApiConfigValidator();
  await validator.runDiagnostics();
  validator.printReport();
}

// Auto-run diagnostics in development
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  // Run diagnostics after a short delay to allow initial setup
  setTimeout(runConfigDiagnostics, 2000);
}