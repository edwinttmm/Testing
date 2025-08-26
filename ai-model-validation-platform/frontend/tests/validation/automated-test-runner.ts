/**
 * Automated Test Runner for Deployment Verification
 * 
 * This script can be run after deployment to execute all validation tests
 * and generate a comprehensive report.
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

interface TestResult {
  testSuite: string;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  errors: string[];
  warnings: string[];
}

interface TestReport {
  timestamp: string;
  environment: string;
  totalTests: number;
  totalPassed: number;
  totalFailed: number;
  totalSkipped: number;
  totalDuration: number;
  suites: TestResult[];
  summary: {
    overallSuccess: boolean;
    criticalFailures: string[];
    recommendations: string[];
  };
}

class AutomatedTestRunner {
  private results: TestResult[] = [];
  private startTime: number = 0;

  constructor(private outputDir: string = './test-results') {
    this.ensureOutputDirectory();
  }

  private ensureOutputDirectory(): void {
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
  }

  private runTestSuite(testSuite: string, testFile: string): TestResult {
    console.log(`\n🏃‍♂️ Running test suite: ${testSuite}`);
    
    const startTime = Date.now();
    let result: TestResult = {
      testSuite,
      passed: 0,
      failed: 0,
      skipped: 0,
      duration: 0,
      errors: [],
      warnings: []
    };

    try {
      // Run Jest test for the specific file
      const command = `npm test -- --testPathPattern="${testFile}" --verbose --json`;
      const output = execSync(command, { 
        encoding: 'utf-8',
        maxBuffer: 1024 * 1024 * 10, // 10MB buffer
        timeout: 120000 // 2 minute timeout
      });

      // Parse Jest JSON output
      const jsonOutput = this.extractJsonFromOutput(output);
      if (jsonOutput) {
        const testResults = JSON.parse(jsonOutput);
        
        result.passed = testResults.numPassedTests || 0;
        result.failed = testResults.numFailedTests || 0;
        result.skipped = testResults.numPendingTests || 0;
        
        // Extract error messages
        if (testResults.testResults && testResults.testResults[0]) {
          const suiteResult = testResults.testResults[0];
          if (suiteResult.assertionResults) {
            suiteResult.assertionResults.forEach((test: any) => {
              if (test.status === 'failed' && test.failureMessages) {
                result.errors.push(...test.failureMessages);
              }
            });
          }
        }
      }

      console.log(`✅ ${testSuite}: ${result.passed} passed, ${result.failed} failed, ${result.skipped} skipped`);

    } catch (error: any) {
      console.error(`❌ ${testSuite} failed to run:`, error.message);
      result.failed = 1;
      result.errors.push(error.message);
    }

    result.duration = Date.now() - startTime;
    return result;
  }

  private extractJsonFromOutput(output: string): string | null {
    // Jest sometimes outputs additional text before/after JSON
    const lines = output.split('\n');
    let jsonStart = -1;
    let jsonEnd = -1;
    
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith('{') && jsonStart === -1) {
        jsonStart = i;
      }
      if (lines[i].trim().endsWith('}') && jsonStart !== -1) {
        jsonEnd = i;
        break;
      }
    }
    
    if (jsonStart !== -1 && jsonEnd !== -1) {
      return lines.slice(jsonStart, jsonEnd + 1).join('\n');
    }
    
    return null;
  }

  private generateReport(): TestReport {
    const endTime = Date.now();
    const totalDuration = endTime - this.startTime;

    const totalTests = this.results.reduce((sum, r) => sum + r.passed + r.failed + r.skipped, 0);
    const totalPassed = this.results.reduce((sum, r) => sum + r.passed, 0);
    const totalFailed = this.results.reduce((sum, r) => sum + r.failed, 0);
    const totalSkipped = this.results.reduce((sum, r) => sum + r.skipped, 0);

    const criticalFailures: string[] = [];
    const recommendations: string[] = [];

    // Analyze results for critical failures
    this.results.forEach(result => {
      if (result.testSuite === 'comprehensive-fix-validation' && result.failed > 0) {
        criticalFailures.push('Core URL fixing functionality has failures');
      }
      if (result.testSuite === 'deployment-verification' && result.failed > 0) {
        criticalFailures.push('Deployment verification failed - check server configuration');
      }
      if (result.testSuite === 'performance-monitoring' && result.failed > 0) {
        recommendations.push('Performance targets not met - consider optimization');
      }
    });

    const overallSuccess = totalFailed === 0 && criticalFailures.length === 0;

    return {
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
      totalTests,
      totalPassed,
      totalFailed,
      totalSkipped,
      totalDuration,
      suites: this.results,
      summary: {
        overallSuccess,
        criticalFailures,
        recommendations
      }
    };
  }

  private saveReport(report: TestReport): void {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `validation-report-${timestamp}.json`;
    const filepath = path.join(this.outputDir, filename);

    fs.writeFileSync(filepath, JSON.stringify(report, null, 2));
    console.log(`📄 Report saved to: ${filepath}`);

    // Also create a latest report
    const latestPath = path.join(this.outputDir, 'latest-validation-report.json');
    fs.writeFileSync(latestPath, JSON.stringify(report, null, 2));
  }

  private printReport(report: TestReport): void {
    console.log('\n' + '='.repeat(80));
    console.log('🎯 DEPLOYMENT VALIDATION REPORT');
    console.log('='.repeat(80));
    
    console.log(`📅 Timestamp: ${report.timestamp}`);
    console.log(`🌍 Environment: ${report.environment}`);
    console.log(`⏱️ Total Duration: ${(report.totalDuration / 1000).toFixed(2)}s`);
    console.log();

    // Summary statistics
    console.log('📊 SUMMARY:');
    console.log(`   Total Tests: ${report.totalTests}`);
    console.log(`   ✅ Passed: ${report.totalPassed}`);
    console.log(`   ❌ Failed: ${report.totalFailed}`);
    console.log(`   ⏭️ Skipped: ${report.totalSkipped}`);
    console.log(`   📈 Success Rate: ${((report.totalPassed / report.totalTests) * 100).toFixed(1)}%`);
    console.log();

    // Suite breakdown
    console.log('📋 TEST SUITES:');
    report.suites.forEach(suite => {
      const status = suite.failed === 0 ? '✅' : '❌';
      console.log(`   ${status} ${suite.testSuite}`);
      console.log(`      Passed: ${suite.passed}, Failed: ${suite.failed}, Skipped: ${suite.skipped}`);
      console.log(`      Duration: ${(suite.duration / 1000).toFixed(2)}s`);
      
      if (suite.errors.length > 0) {
        console.log(`      Errors: ${suite.errors.length}`);
      }
    });
    console.log();

    // Critical issues
    if (report.summary.criticalFailures.length > 0) {
      console.log('🚨 CRITICAL FAILURES:');
      report.summary.criticalFailures.forEach(failure => {
        console.log(`   ❌ ${failure}`);
      });
      console.log();
    }

    // Recommendations
    if (report.summary.recommendations.length > 0) {
      console.log('💡 RECOMMENDATIONS:');
      report.summary.recommendations.forEach(rec => {
        console.log(`   💡 ${rec}`);
      });
      console.log();
    }

    // Overall result
    if (report.summary.overallSuccess) {
      console.log('🎉 DEPLOYMENT VALIDATION SUCCESSFUL!');
      console.log('   All critical tests passed. The URL fix deployment appears to be working correctly.');
    } else {
      console.log('⚠️ DEPLOYMENT VALIDATION ISSUES DETECTED');
      console.log('   Please review the failures and recommendations above.');
    }
    
    console.log('='.repeat(80));
  }

  async runAllValidationTests(): Promise<TestReport> {
    console.log('🚀 Starting automated deployment validation tests...');
    this.startTime = Date.now();

    // Define test suites to run
    const testSuites = [
      {
        name: 'comprehensive-fix-validation',
        file: 'comprehensive-fix-validation.test.ts',
        description: 'Core URL fixing functionality'
      },
      {
        name: 'deployment-verification',
        file: 'deployment-verification.test.ts',
        description: 'Real deployment environment checks'
      },
      {
        name: 'performance-monitoring',
        file: 'performance-monitoring.test.ts',
        description: 'Performance and optimization validation'
      }
    ];

    // Run each test suite
    for (const suite of testSuites) {
      console.log(`\n📋 Testing: ${suite.description}`);
      const result = this.runTestSuite(suite.name, suite.file);
      this.results.push(result);
    }

    // Generate comprehensive report
    const report = this.generateReport();
    
    // Save and display report
    this.saveReport(report);
    this.printReport(report);

    return report;
  }

  // Quick validation for CI/CD pipelines
  async runQuickValidation(): Promise<boolean> {
    console.log('⚡ Running quick validation checks...');
    
    try {
      // Run only critical tests
      const criticalResult = this.runTestSuite(
        'critical-validation',
        'comprehensive-fix-validation.test.ts'
      );
      
      return criticalResult.failed === 0;
    } catch (error) {
      console.error('Quick validation failed:', error);
      return false;
    }
  }

  // Generate HTML report
  generateHtmlReport(report: TestReport): void {
    const html = `
<!DOCTYPE html>
<html>
<head>
    <title>Deployment Validation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f0f0f0; padding: 20px; border-radius: 8px; }
        .success { color: #28a745; }
        .failure { color: #dc3545; }
        .warning { color: #ffc107; }
        .suite { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 20px 0; }
        .metric { text-align: center; padding: 10px; background: #f8f9fa; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Deployment Validation Report</h1>
        <p><strong>Timestamp:</strong> ${report.timestamp}</p>
        <p><strong>Environment:</strong> ${report.environment}</p>
        <p><strong>Status:</strong> <span class="${report.summary.overallSuccess ? 'success' : 'failure'}">
            ${report.summary.overallSuccess ? '✅ Success' : '❌ Issues Detected'}
        </span></p>
    </div>

    <div class="metrics">
        <div class="metric">
            <h3>${report.totalTests}</h3>
            <p>Total Tests</p>
        </div>
        <div class="metric">
            <h3 class="success">${report.totalPassed}</h3>
            <p>Passed</p>
        </div>
        <div class="metric">
            <h3 class="failure">${report.totalFailed}</h3>
            <p>Failed</p>
        </div>
        <div class="metric">
            <h3>${(report.totalDuration / 1000).toFixed(2)}s</h3>
            <p>Duration</p>
        </div>
    </div>

    <h2>Test Suites</h2>
    ${report.suites.map(suite => `
        <div class="suite">
            <h3>${suite.failed === 0 ? '✅' : '❌'} ${suite.testSuite}</h3>
            <p>Passed: ${suite.passed} | Failed: ${suite.failed} | Skipped: ${suite.skipped}</p>
            <p>Duration: ${(suite.duration / 1000).toFixed(2)}s</p>
            ${suite.errors.length > 0 ? `
                <details>
                    <summary>Errors (${suite.errors.length})</summary>
                    <pre>${suite.errors.join('\n\n')}</pre>
                </details>
            ` : ''}
        </div>
    `).join('')}

    ${report.summary.criticalFailures.length > 0 ? `
        <h2 class="failure">🚨 Critical Failures</h2>
        <ul>
            ${report.summary.criticalFailures.map(failure => `<li class="failure">${failure}</li>`).join('')}
        </ul>
    ` : ''}

    ${report.summary.recommendations.length > 0 ? `
        <h2 class="warning">💡 Recommendations</h2>
        <ul>
            ${report.summary.recommendations.map(rec => `<li class="warning">${rec}</li>`).join('')}
        </ul>
    ` : ''}
</body>
</html>`;

    const htmlPath = path.join(this.outputDir, 'validation-report.html');
    fs.writeFileSync(htmlPath, html);
    console.log(`📄 HTML report saved to: ${htmlPath}`);
  }
}

// CLI interface
if (require.main === module) {
  const args = process.argv.slice(2);
  const runner = new AutomatedTestRunner();

  if (args.includes('--quick')) {
    runner.runQuickValidation().then(success => {
      process.exit(success ? 0 : 1);
    });
  } else {
    runner.runAllValidationTests().then(report => {
      if (args.includes('--html')) {
        runner.generateHtmlReport(report);
      }
      process.exit(report.summary.overallSuccess ? 0 : 1);
    });
  }
}

export default AutomatedTestRunner;