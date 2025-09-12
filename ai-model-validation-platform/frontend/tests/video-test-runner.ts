/**
 * Automated Video Test Runner
 * Orchestrates and executes comprehensive video playback testing
 */

import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';

interface TestSuite {
  name: string;
  file: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  estimatedDuration: number; // in seconds
  dependencies: string[];
}

interface TestResult {
  suite: string;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  coverage?: {
    lines: number;
    functions: number;
    branches: number;
    statements: number;
  };
  errors: string[];
}

interface TestReport {
  timestamp: string;
  totalDuration: number;
  totalTests: number;
  passedTests: number;
  failedTests: number;
  skippedTests: number;
  coverage: {
    overall: number;
    details: {
      lines: number;
      functions: number;
      branches: number;
      statements: number;
    };
  };
  suites: TestResult[];
  recommendations: string[];
}

class VideoTestRunner {
  private testSuites: TestSuite[] = [
    {
      name: 'Comprehensive Playback',
      file: 'video-playback-comprehensive.test.tsx',
      description: 'Core video playback functionality, sequential playback, queue management',
      priority: 'high',
      estimatedDuration: 120,
      dependencies: []
    },
    {
      name: 'Browser Compatibility',
      file: 'video-browser-compatibility.test.tsx',
      description: 'Cross-browser compatibility, fullscreen APIs, codec support',
      priority: 'high',
      estimatedDuration: 90,
      dependencies: ['Comprehensive Playback']
    },
    {
      name: 'Performance Benchmarks',
      file: 'video-performance-benchmarks.test.tsx',
      description: 'Loading performance, memory usage, optimization strategies',
      priority: 'medium',
      estimatedDuration: 180,
      dependencies: ['Comprehensive Playback']
    },
    {
      name: 'LabJack Integration',
      file: 'video-labjack-integration.test.tsx',
      description: 'Hardware synchronization, timing precision, data correlation',
      priority: 'medium',
      estimatedDuration: 150,
      dependencies: ['Comprehensive Playback']
    },
    {
      name: 'Existing System Integration',
      file: '../src/tests/video-system-integration.test.tsx',
      description: 'Integration with existing video annotation system',
      priority: 'high',
      estimatedDuration: 60,
      dependencies: []
    }
  ];

  private testResults: TestResult[] = [];
  private startTime: number = 0;

  async runAllTests(options: {
    parallel?: boolean;
    coverage?: boolean;
    browser?: string;
    timeout?: number;
    verbose?: boolean;
  } = {}): Promise<TestReport> {
    const {
      parallel = true,
      coverage = true,
      browser = 'jsdom',
      timeout = 600000, // 10 minutes default
      verbose = false
    } = options;

    this.startTime = Date.now();
    console.log('🚀 Starting comprehensive video playback test suite...');

    if (coverage) {
      console.log('📊 Coverage reporting enabled');
    }

    if (parallel) {
      await this.runTestsInParallel(coverage, timeout, verbose);
    } else {
      await this.runTestsSequentially(coverage, timeout, verbose);
    }

    return this.generateReport();
  }

  private async runTestsInParallel(coverage: boolean, timeout: number, verbose: boolean): Promise<void> {
    // Group tests by dependencies
    const independentTests = this.testSuites.filter(suite => suite.dependencies.length === 0);
    const dependentTests = this.testSuites.filter(suite => suite.dependencies.length > 0);

    // Run independent tests first
    console.log(`🔄 Running ${independentTests.length} independent tests in parallel...`);
    
    const independentPromises = independentTests.map(suite => 
      this.runSingleTest(suite, coverage, timeout, verbose)
    );
    
    await Promise.allSettled(independentPromises);

    // Run dependent tests (can still be parallel within dependency groups)
    console.log(`🔄 Running ${dependentTests.length} dependent tests...`);
    
    const dependentPromises = dependentTests.map(suite => 
      this.runSingleTest(suite, coverage, timeout, verbose)
    );
    
    await Promise.allSettled(dependentPromises);
  }

  private async runTestsSequentially(coverage: boolean, timeout: number, verbose: boolean): Promise<void> {
    console.log(`🔄 Running ${this.testSuites.length} tests sequentially...`);
    
    for (const suite of this.testSuites) {
      await this.runSingleTest(suite, coverage, timeout, verbose);
    }
  }

  private async runSingleTest(
    suite: TestSuite, 
    coverage: boolean, 
    timeout: number, 
    verbose: boolean
  ): Promise<void> {
    const startTime = Date.now();
    console.log(`🧪 Running ${suite.name}...`);

    try {
      // Build Jest command
      const jestCommand = this.buildJestCommand(suite, coverage, timeout, verbose);
      
      if (verbose) {
        console.log(`   Command: ${jestCommand}`);
      }

      // Execute test
      const result = execSync(jestCommand, {
        cwd: process.cwd(),
        encoding: 'utf8',
        timeout: timeout
      });

      // Parse results
      const testResult = this.parseJestOutput(result, suite.name, Date.now() - startTime);
      this.testResults.push(testResult);

      const status = testResult.failed > 0 ? '❌' : '✅';
      console.log(`${status} ${suite.name}: ${testResult.passed} passed, ${testResult.failed} failed (${testResult.duration}ms)`);

    } catch (error: any) {
      console.error(`❌ ${suite.name} failed:`, error.message);
      
      this.testResults.push({
        suite: suite.name,
        passed: 0,
        failed: 1,
        skipped: 0,
        duration: Date.now() - startTime,
        errors: [error.message]
      });
    }
  }

  private buildJestCommand(
    suite: TestSuite, 
    coverage: boolean, 
    timeout: number, 
    verbose: boolean
  ): string {
    const commands = ['npx', 'jest'];
    
    // Test file
    const testPath = path.join('tests', suite.file);
    commands.push(`"${testPath}"`);
    
    // Coverage
    if (coverage) {
      commands.push('--coverage');
      commands.push('--coverageDirectory=coverage/video-tests');
      commands.push('--coverageReporters=json,lcov,text-summary');
    }

    // Timeout
    commands.push(`--testTimeout=${timeout}`);
    
    // Environment
    commands.push('--testEnvironment=jsdom');
    
    // Verbose output
    if (verbose) {
      commands.push('--verbose');
    }

    // Other Jest options
    commands.push('--detectOpenHandles');
    commands.push('--forceExit');
    commands.push('--maxWorkers=1'); // Prevent conflicts in parallel execution
    
    return commands.join(' ');
  }

  private parseJestOutput(output: string, suiteName: string, duration: number): TestResult {
    const result: TestResult = {
      suite: suiteName,
      passed: 0,
      failed: 0,
      skipped: 0,
      duration,
      errors: []
    };

    try {
      // Parse test results from Jest output
      const lines = output.split('\n');
      
      for (const line of lines) {
        // Look for test summary line
        if (line.includes('Tests:')) {
          const match = line.match(/(\d+) passed.*?(\d+) failed.*?(\d+) skipped/);
          if (match) {
            result.passed = parseInt(match[1]);
            result.failed = parseInt(match[2]);
            result.skipped = parseInt(match[3]);
          }
        }

        // Look for coverage information
        if (line.includes('All files')) {
          const coverageMatch = line.match(/(\d+\.?\d*)\s*\|\s*(\d+\.?\d*)\s*\|\s*(\d+\.?\d*)\s*\|\s*(\d+\.?\d*)/);
          if (coverageMatch) {
            result.coverage = {
              statements: parseFloat(coverageMatch[1]),
              branches: parseFloat(coverageMatch[2]),
              functions: parseFloat(coverageMatch[3]),
              lines: parseFloat(coverageMatch[4])
            };
          }
        }

        // Collect error messages
        if (line.includes('FAIL') || line.includes('Error:')) {
          result.errors.push(line.trim());
        }
      }
    } catch (error) {
      console.warn(`Warning: Could not parse Jest output for ${suiteName}:`, error);
    }

    return result;
  }

  private generateReport(): TestReport {
    const totalDuration = Date.now() - this.startTime;
    const totalTests = this.testResults.reduce((sum, r) => sum + r.passed + r.failed + r.skipped, 0);
    const passedTests = this.testResults.reduce((sum, r) => sum + r.passed, 0);
    const failedTests = this.testResults.reduce((sum, r) => sum + r.failed, 0);
    const skippedTests = this.testResults.reduce((sum, r) => sum + r.skipped, 0);

    // Calculate overall coverage
    const coverageResults = this.testResults.filter(r => r.coverage);
    const overallCoverage = coverageResults.length > 0 
      ? coverageResults.reduce((sum, r) => sum + (r.coverage?.statements || 0), 0) / coverageResults.length
      : 0;

    const avgCoverage = {
      lines: coverageResults.reduce((sum, r) => sum + (r.coverage?.lines || 0), 0) / (coverageResults.length || 1),
      functions: coverageResults.reduce((sum, r) => sum + (r.coverage?.functions || 0), 0) / (coverageResults.length || 1),
      branches: coverageResults.reduce((sum, r) => sum + (r.coverage?.branches || 0), 0) / (coverageResults.length || 1),
      statements: coverageResults.reduce((sum, r) => sum + (r.coverage?.statements || 0), 0) / (coverageResults.length || 1)
    };

    const report: TestReport = {
      timestamp: new Date().toISOString(),
      totalDuration,
      totalTests,
      passedTests,
      failedTests,
      skippedTests,
      coverage: {
        overall: overallCoverage,
        details: avgCoverage
      },
      suites: this.testResults,
      recommendations: this.generateRecommendations()
    };

    return report;
  }

  private generateRecommendations(): string[] {
    const recommendations: string[] = [];
    const failedSuites = this.testResults.filter(r => r.failed > 0);
    const lowCoverage = this.testResults.filter(r => r.coverage && r.coverage.statements < 80);

    if (failedSuites.length > 0) {
      recommendations.push(`${failedSuites.length} test suites have failing tests. Review error messages and fix issues.`);
    }

    if (lowCoverage.length > 0) {
      recommendations.push(`${lowCoverage.length} test suites have low coverage (<80%). Consider adding more test cases.`);
    }

    const longRunningSuites = this.testResults.filter(r => r.duration > 60000); // > 1 minute
    if (longRunningSuites.length > 0) {
      recommendations.push(`${longRunningSuites.length} test suites took longer than 1 minute. Consider optimizing test performance.`);
    }

    if (this.testResults.length < this.testSuites.length) {
      recommendations.push(`${this.testSuites.length - this.testResults.length} test suites did not complete. Check for configuration issues.`);
    }

    if (recommendations.length === 0) {
      recommendations.push('All tests passed successfully! Consider adding edge case tests for even better coverage.');
    }

    return recommendations;
  }

  async saveReport(report: TestReport, outputPath?: string): Promise<void> {
    const defaultPath = path.join(process.cwd(), 'coverage', 'video-test-report.json');
    const filePath = outputPath || defaultPath;

    // Ensure directory exists
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    fs.writeFileSync(filePath, JSON.stringify(report, null, 2));
    console.log(`📄 Test report saved to: ${filePath}`);

    // Also generate a summary report
    const summaryPath = filePath.replace('.json', '-summary.txt');
    const summary = this.generateTextSummary(report);
    fs.writeFileSync(summaryPath, summary);
    console.log(`📄 Summary report saved to: ${summaryPath}`);
  }

  private generateTextSummary(report: TestReport): string {
    const lines = [
      '🎬 Video Playback System Test Report',
      '=' .repeat(50),
      '',
      `📅 Generated: ${report.timestamp}`,
      `⏱️  Total Duration: ${(report.totalDuration / 1000).toFixed(1)}s`,
      '',
      '📊 Test Results:',
      `   Total Tests: ${report.totalTests}`,
      `   ✅ Passed: ${report.passedTests}`,
      `   ❌ Failed: ${report.failedTests}`,
      `   ⏭️  Skipped: ${report.skippedTests}`,
      `   📈 Success Rate: ${((report.passedTests / report.totalTests) * 100).toFixed(1)}%`,
      '',
      '🎯 Coverage:',
      `   Overall: ${report.coverage.overall.toFixed(1)}%`,
      `   Lines: ${report.coverage.details.lines.toFixed(1)}%`,
      `   Functions: ${report.coverage.details.functions.toFixed(1)}%`,
      `   Branches: ${report.coverage.details.branches.toFixed(1)}%`,
      `   Statements: ${report.coverage.details.statements.toFixed(1)}%`,
      '',
      '🧪 Test Suites:',
    ];

    report.suites.forEach(suite => {
      const status = suite.failed > 0 ? '❌' : '✅';
      lines.push(`   ${status} ${suite.suite}: ${suite.passed}/${suite.passed + suite.failed} (${suite.duration}ms)`);
    });

    lines.push('');
    lines.push('💡 Recommendations:');
    report.recommendations.forEach(rec => {
      lines.push(`   • ${rec}`);
    });

    return lines.join('\n');
  }

  displayResults(report: TestReport): void {
    console.log('\n' + '='.repeat(60));
    console.log('🎬 VIDEO PLAYBACK SYSTEM TEST RESULTS');
    console.log('='.repeat(60));
    console.log(`📅 Completed: ${report.timestamp}`);
    console.log(`⏱️  Duration: ${(report.totalDuration / 1000).toFixed(1)} seconds`);
    console.log();
    
    // Summary
    const successRate = (report.passedTests / report.totalTests) * 100;
    const statusIcon = successRate === 100 ? '🎉' : successRate >= 80 ? '✅' : '⚠️';
    
    console.log(`${statusIcon} Test Summary:`);
    console.log(`   📊 ${report.totalTests} total tests`);
    console.log(`   ✅ ${report.passedTests} passed`);
    console.log(`   ❌ ${report.failedTests} failed`);
    console.log(`   ⏭️  ${report.skippedTests} skipped`);
    console.log(`   📈 ${successRate.toFixed(1)}% success rate`);
    console.log();

    // Coverage
    console.log('📊 Coverage Report:');
    console.log(`   Overall: ${report.coverage.overall.toFixed(1)}%`);
    console.log(`   Lines: ${report.coverage.details.lines.toFixed(1)}%`);
    console.log(`   Functions: ${report.coverage.details.functions.toFixed(1)}%`);
    console.log(`   Branches: ${report.coverage.details.branches.toFixed(1)}%`);
    console.log(`   Statements: ${report.coverage.details.statements.toFixed(1)}%`);
    console.log();

    // Individual suites
    console.log('🧪 Suite Results:');
    report.suites.forEach(suite => {
      const status = suite.failed > 0 ? '❌' : '✅';
      const durationSeconds = (suite.duration / 1000).toFixed(1);
      console.log(`   ${status} ${suite.suite}`);
      console.log(`      📊 ${suite.passed} passed, ${suite.failed} failed, ${suite.skipped} skipped`);
      console.log(`      ⏱️  ${durationSeconds}s`);
      if (suite.errors.length > 0) {
        suite.errors.forEach(error => {
          console.log(`      🔥 ${error}`);
        });
      }
    });
    console.log();

    // Recommendations
    console.log('💡 Recommendations:');
    report.recommendations.forEach(rec => {
      console.log(`   • ${rec}`);
    });
    console.log();
    
    console.log('='.repeat(60));
  }
}

// CLI interface
if (require.main === module) {
  const runner = new VideoTestRunner();
  
  const args = process.argv.slice(2);
  const options = {
    parallel: !args.includes('--sequential'),
    coverage: !args.includes('--no-coverage'),
    verbose: args.includes('--verbose'),
    timeout: args.includes('--timeout') ? parseInt(args[args.indexOf('--timeout') + 1]) : 600000
  };

  runner.runAllTests(options)
    .then(report => {
      runner.displayResults(report);
      return runner.saveReport(report);
    })
    .then(() => {
      const hasFailures = runner['testResults'].some(r => r.failed > 0);
      process.exit(hasFailures ? 1 : 0);
    })
    .catch(error => {
      console.error('❌ Test runner failed:', error);
      process.exit(1);
    });
}

export { VideoTestRunner, TestReport, TestResult };
export default VideoTestRunner;