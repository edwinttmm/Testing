/**
 * LabJack Integration Test Runner
 * ==============================
 * 
 * Comprehensive test runner for all LabJack hardware integration tests
 * Executes tests in proper sequence and generates detailed reports
 * 
 * @author Hardware Integration Test Specialist
 * @requires Node.js, Jest, Backend running on localhost:8000
 */

import { spawn } from 'child_process';
import { existsSync, writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

// Test configuration
const TEST_CONFIG = {
  BACKEND_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  FRONTEND_URL: process.env.REACT_APP_URL || 'http://localhost:3000',
  OUTPUT_DIR: join(process.cwd(), 'tests/results'),
  REPORT_FILE: 'labjack-integration-report.json',
  LOG_FILE: 'labjack-test-execution.log',
  TIMEOUT: 300000, // 5 minutes total timeout
  PARALLEL_TESTS: false, // Run tests sequentially for hardware testing
};

// Test suite definitions
const TEST_SUITES = [
  {
    name: 'LabJack API Validation',
    file: 'labjack-api-validation.test.ts',
    description: 'Tests all LabJack REST API endpoints',
    timeout: 180000, // 3 minutes
    critical: true
  },
  {
    name: 'LabJack Hardware Integration',
    file: 'labjack-hardware-integration.test.ts',
    description: 'Tests LabJack Status Panel and WebSocket communication',
    timeout: 240000, // 4 minutes
    critical: true
  },
  {
    name: 'LabJack Integration Validation',
    file: 'labjack-integration-validation.test.ts',
    description: 'Legacy comprehensive validation tests',
    timeout: 180000, // 3 minutes
    critical: false
  }
];

// Test results interface
interface TestSuiteResult {
  name: string;
  file: string;
  status: 'PASSED' | 'FAILED' | 'SKIPPED' | 'TIMEOUT';
  duration: number;
  tests: {
    total: number;
    passed: number;
    failed: number;
    skipped: number;
  };
  coverage?: {
    lines: number;
    functions: number;
    branches: number;
    statements: number;
  };
  errors: string[];
  warnings: string[];
  output: string[];
}

interface TestReport {
  timestamp: string;
  environment: {
    backend_url: string;
    frontend_url: string;
    node_version: string;
    platform: string;
  };
  summary: {
    total_suites: number;
    passed_suites: number;
    failed_suites: number;
    skipped_suites: number;
    total_duration: number;
    total_tests: number;
    overall_status: 'PASSED' | 'FAILED' | 'PARTIAL';
  };
  suites: TestSuiteResult[];
  recommendations: string[];
}

// Logger utility
class TestLogger {
  private logs: string[] = [];
  
  log(level: 'INFO' | 'WARN' | 'ERROR', message: string) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${level}: ${message}`;
    console.log(logEntry);
    this.logs.push(logEntry);
  }
  
  info(message: string) { this.log('INFO', message); }
  warn(message: string) { this.log('WARN', message); }
  error(message: string) { this.log('ERROR', message); }
  
  getLogs(): string[] { return [...this.logs]; }
  
  saveLogs(filepath: string) {
    writeFileSync(filepath, this.logs.join('\\n'), 'utf8');
  }
}

// Test runner class
class LabJackTestRunner {
  private logger: TestLogger;
  private results: TestSuiteResult[] = [];
  private startTime: number = 0;
  
  constructor() {
    this.logger = new TestLogger();
  }
  
  async run(): Promise<TestReport> {
    this.startTime = Date.now();
    
    this.logger.info('🚀 Starting LabJack Integration Test Suite');
    this.logger.info('==========================================');
    this.logger.info(`Backend URL: ${TEST_CONFIG.BACKEND_URL}`);
    this.logger.info(`Frontend URL: ${TEST_CONFIG.FRONTEND_URL}`);
    this.logger.info(`Output Directory: ${TEST_CONFIG.OUTPUT_DIR}`);
    this.logger.info('');
    
    // Ensure output directory exists
    this.ensureOutputDirectory();
    
    // Check prerequisites
    const prerequisitesOk = await this.checkPrerequisites();
    if (!prerequisitesOk) {
      this.logger.error('Prerequisites check failed. Aborting test execution.');
      return this.generateReport('FAILED');
    }
    
    // Run test suites
    for (const suite of TEST_SUITES) {
      if (TEST_CONFIG.PARALLEL_TESTS) {
        // TODO: Implement parallel execution if needed
        this.logger.warn('Parallel execution not yet implemented, running sequentially');
      }
      
      const result = await this.runTestSuite(suite);
      this.results.push(result);
      
      // Stop on critical failure if configured
      if (result.status === 'FAILED' && suite.critical) {
        this.logger.error(`Critical test suite '${suite.name}' failed. Consider stopping here.`);
        // Continue for now, but could break here based on configuration
      }
    }
    
    // Generate final report
    const report = this.generateReport();
    this.saveReport(report);
    this.printSummary(report);
    
    return report;
  }
  
  private ensureOutputDirectory() {
    if (!existsSync(TEST_CONFIG.OUTPUT_DIR)) {
      mkdirSync(TEST_CONFIG.OUTPUT_DIR, { recursive: true });
      this.logger.info(`Created output directory: ${TEST_CONFIG.OUTPUT_DIR}`);
    }
  }
  
  private async checkPrerequisites(): Promise<boolean> {
    this.logger.info('🔍 Checking Prerequisites');
    this.logger.info('------------------------');
    
    let allGood = true;
    
    // Check Node.js version
    const nodeVersion = process.version;
    const nodeVersionNumber = parseFloat(nodeVersion.slice(1));
    if (nodeVersionNumber < 16.0) {
      this.logger.error(`Node.js version ${nodeVersion} is too old (minimum: 16.0)`);
      allGood = false;
    } else {
      this.logger.info(`✅ Node.js version: ${nodeVersion}`);
    }
    
    // Check if backend is running
    try {
      const response = await fetch(`${TEST_CONFIG.BACKEND_URL}/health`);
      if (response.ok) {
        this.logger.info(`✅ Backend is running at ${TEST_CONFIG.BACKEND_URL}`);
      } else {
        this.logger.error(`❌ Backend responded with status ${response.status}`);
        allGood = false;
      }
    } catch (error) {
      this.logger.error(`❌ Backend not reachable at ${TEST_CONFIG.BACKEND_URL}: ${error}`);
      allGood = false;
    }
    
    // Check if test files exist
    for (const suite of TEST_SUITES) {
      const testFile = join(process.cwd(), 'tests', suite.file);
      if (existsSync(testFile)) {
        this.logger.info(`✅ Test file exists: ${suite.file}`);
      } else {
        this.logger.error(`❌ Test file not found: ${testFile}`);
        allGood = false;
      }
    }
    
    this.logger.info('');
    return allGood;
  }
  
  private async runTestSuite(suite: any): Promise<TestSuiteResult> {
    this.logger.info(`🧪 Running Test Suite: ${suite.name}`);
    this.logger.info(`📝 Description: ${suite.description}`);
    this.logger.info(`⏱️ Timeout: ${suite.timeout / 1000}s`);
    
    const startTime = Date.now();
    const result: TestSuiteResult = {
      name: suite.name,
      file: suite.file,
      status: 'SKIPPED',
      duration: 0,
      tests: { total: 0, passed: 0, failed: 0, skipped: 0 },
      errors: [],
      warnings: [],
      output: []
    };
    
    try {
      const jestResult = await this.executeJestTest(suite.file, suite.timeout);
      
      result.duration = Date.now() - startTime;
      result.status = jestResult.success ? 'PASSED' : 'FAILED';
      result.tests = jestResult.testResults;
      result.errors = jestResult.errors;
      result.warnings = jestResult.warnings;
      result.output = jestResult.output;
      result.coverage = jestResult.coverage;
      
      if (jestResult.success) {
        this.logger.info(`✅ ${suite.name} completed successfully in ${result.duration}ms`);
      } else {
        this.logger.error(`❌ ${suite.name} failed after ${result.duration}ms`);
        this.logger.error(`Errors: ${jestResult.errors.join(', ')}`);
      }
      
    } catch (error) {
      result.duration = Date.now() - startTime;
      result.status = 'FAILED';
      result.errors.push(String(error));
      
      this.logger.error(`❌ ${suite.name} threw exception: ${error}`);
    }
    
    this.logger.info('');
    return result;
  }
  
  private executeJestTest(testFile: string, timeout: number): Promise<any> {
    return new Promise((resolve, reject) => {
      const jestArgs = [
        '--testPathPattern=' + testFile,
        '--verbose',
        '--json',
        '--coverage',
        '--testTimeout=' + timeout,
        '--detectOpenHandles',
        '--forceExit'
      ];
      
      this.logger.info(`Running: npx jest ${jestArgs.join(' ')}`);
      
      const jest = spawn('npx', ['jest', ...jestArgs], {
        cwd: process.cwd(),
        env: {
          ...process.env,
          NODE_ENV: 'test',
          REACT_APP_API_URL: TEST_CONFIG.BACKEND_URL,
          CI: 'true'
        }
      });
      
      let stdout = '';
      let stderr = '';
      
      jest.stdout.on('data', (data) => {
        stdout += data.toString();
      });
      
      jest.stderr.on('data', (data) => {
        stderr += data.toString();
      });
      
      const timer = setTimeout(() => {
        jest.kill('SIGTERM');
        reject(new Error(`Test suite timed out after ${timeout}ms`));
      }, timeout);
      
      jest.on('close', (code) => {
        clearTimeout(timer);
        
        try {
          // Parse Jest JSON output
          const lines = stdout.split('\\n').filter(line => line.trim());
          const jsonLine = lines.find(line => line.startsWith('{') && line.includes('testResults'));
          
          if (jsonLine) {
            const jestOutput = JSON.parse(jsonLine);
            
            const result = {
              success: code === 0,
              testResults: {
                total: jestOutput.numTotalTests || 0,
                passed: jestOutput.numPassedTests || 0,
                failed: jestOutput.numFailedTests || 0,
                skipped: jestOutput.numSkippedTests || 0
              },
              coverage: jestOutput.coverageMap ? {
                lines: Math.round((jestOutput.coverageMap.getCoverageSummary?.().lines.pct || 0) * 100) / 100,
                functions: Math.round((jestOutput.coverageMap.getCoverageSummary?.().functions.pct || 0) * 100) / 100,
                branches: Math.round((jestOutput.coverageMap.getCoverageSummary?.().branches.pct || 0) * 100) / 100,
                statements: Math.round((jestOutput.coverageMap.getCoverageSummary?.().statements.pct || 0) * 100) / 100
              } : undefined,
              errors: stderr ? [stderr] : [],
              warnings: [],
              output: stdout.split('\\n').filter(line => line.trim())
            };
            
            resolve(result);
          } else {
            // Fallback parsing if JSON output isn't found
            const passed = (stdout.match(/✓/g) || []).length;
            const failed = (stdout.match(/✕/g) || []).length;
            const total = passed + failed;
            
            resolve({
              success: code === 0,
              testResults: { total, passed, failed, skipped: 0 },
              errors: code !== 0 ? [stderr || 'Test failed'] : [],
              warnings: [],
              output: stdout.split('\\n').filter(line => line.trim())
            });
          }
        } catch (parseError) {
          resolve({
            success: code === 0,
            testResults: { total: 0, passed: 0, failed: 0, skipped: 0 },
            errors: [String(parseError)],
            warnings: [],
            output: [stdout, stderr].filter(s => s.trim())
          });
        }
      });
      
      jest.on('error', (error) => {
        clearTimeout(timer);
        reject(error);
      });
    });
  }
  
  private generateReport(overrideStatus?: string): TestReport {
    const endTime = Date.now();
    const totalDuration = endTime - this.startTime;
    
    const totalSuites = this.results.length;
    const passedSuites = this.results.filter(r => r.status === 'PASSED').length;
    const failedSuites = this.results.filter(r => r.status === 'FAILED').length;
    const skippedSuites = this.results.filter(r => r.status === 'SKIPPED').length;
    
    const totalTests = this.results.reduce((sum, r) => sum + r.tests.total, 0);
    
    let overallStatus: 'PASSED' | 'FAILED' | 'PARTIAL' = 'PASSED';
    if (overrideStatus === 'FAILED' || failedSuites > 0) {
      overallStatus = failedSuites === totalSuites ? 'FAILED' : 'PARTIAL';
    }
    
    const recommendations = this.generateRecommendations();
    
    return {
      timestamp: new Date().toISOString(),
      environment: {
        backend_url: TEST_CONFIG.BACKEND_URL,
        frontend_url: TEST_CONFIG.FRONTEND_URL,
        node_version: process.version,
        platform: process.platform
      },
      summary: {
        total_suites: totalSuites,
        passed_suites: passedSuites,
        failed_suites: failedSuites,
        skipped_suites: skippedSuites,
        total_duration: totalDuration,
        total_tests: totalTests,
        overall_status: overallStatus
      },
      suites: this.results,
      recommendations
    };
  }
  
  private generateRecommendations(): string[] {
    const recommendations: string[] = [];
    
    const failedSuites = this.results.filter(r => r.status === 'FAILED');
    const slowSuites = this.results.filter(r => r.duration > 60000); // > 1 minute
    
    if (failedSuites.length > 0) {
      recommendations.push('Review failed test suites and check hardware connectivity');
      recommendations.push('Ensure LabJack drivers are properly installed on Windows systems');
      recommendations.push('Check that the backend is running and accessible');
    }
    
    if (slowSuites.length > 0) {
      recommendations.push('Some test suites took longer than expected - consider optimizing');
    }
    
    const totalErrors = this.results.reduce((sum, r) => sum + r.errors.length, 0);
    if (totalErrors > 0) {
      recommendations.push('Review error logs for specific failure details');
    }
    
    if (this.results.some(r => r.tests.total === 0)) {
      recommendations.push('Some test suites had no tests executed - check test file paths');
    }
    
    // Add general recommendations
    recommendations.push('Test both with and without LabJack hardware connected');
    recommendations.push('Verify Windows drivers are installed if testing on Windows');
    recommendations.push('Check WebSocket connectivity for real-time features');
    
    return recommendations;
  }
  
  private saveReport(report: TestReport) {
    const reportPath = join(TEST_CONFIG.OUTPUT_DIR, TEST_CONFIG.REPORT_FILE);
    const logPath = join(TEST_CONFIG.OUTPUT_DIR, TEST_CONFIG.LOG_FILE);
    
    try {
      writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
      this.logger.info(`📊 Test report saved to: ${reportPath}`);
      
      this.logger.saveLogs(logPath);
      this.logger.info(`📋 Test logs saved to: ${logPath}`);
    } catch (error) {
      this.logger.error(`Failed to save report: ${error}`);
    }
  }
  
  private printSummary(report: TestReport) {
    console.log('\\n📊 LabJack Integration Test Summary');
    console.log('====================================');
    console.log(`🕐 Total Duration: ${Math.round(report.summary.total_duration / 1000)}s`);
    console.log(`📦 Test Suites: ${report.summary.total_suites}`);
    console.log(`✅ Passed: ${report.summary.passed_suites}`);
    console.log(`❌ Failed: ${report.summary.failed_suites}`);
    console.log(`⏭️ Skipped: ${report.summary.skipped_suites}`);
    console.log(`🧪 Total Tests: ${report.summary.total_tests}`);
    console.log(`🎯 Overall Status: ${report.summary.overall_status}`);
    
    if (report.recommendations.length > 0) {
      console.log('\\n💡 Recommendations:');
      report.recommendations.forEach(rec => console.log(`   • ${rec}`));
    }
    
    console.log('\\n📁 Output Files:');
    console.log(`   • Report: ${join(TEST_CONFIG.OUTPUT_DIR, TEST_CONFIG.REPORT_FILE)}`);
    console.log(`   • Logs: ${join(TEST_CONFIG.OUTPUT_DIR, TEST_CONFIG.LOG_FILE)}`);
    
    if (report.summary.overall_status === 'PASSED') {
      console.log('\\n🎉 All LabJack integration tests completed successfully!');
    } else if (report.summary.overall_status === 'PARTIAL') {
      console.log('\\n⚠️ Some tests failed, but critical functionality may still work.');
    } else {
      console.log('\\n❌ LabJack integration tests failed. Review the report for details.');
    }
  }
}

// Main execution
if (require.main === module) {
  const runner = new LabJackTestRunner();
  
  runner.run()
    .then((report) => {
      process.exit(report.summary.overall_status === 'FAILED' ? 1 : 0);
    })
    .catch((error) => {
      console.error('❌ Test runner failed:', error);
      process.exit(1);
    });
}

export default LabJackTestRunner;