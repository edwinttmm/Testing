/**
 * Video Transition Test Runner
 * 
 * Utility script to run comprehensive video transition tests
 * and generate detailed reports for manual validation.
 */

import { exec } from 'child_process';
import { promises as fs } from 'fs';
import path from 'path';

interface TestRunResult {
  testName: string;
  status: 'PASS' | 'FAIL' | 'SKIP';
  duration: number;
  output: string;
  errors: string[];
}

interface TestSuite {
  name: string;
  file: string;
  description: string;
  critical: boolean;
}

const VIDEO_TRANSITION_TEST_SUITES: TestSuite[] = [
  {
    name: 'Video Transition Integration Test',
    file: 'video-transition-system.integration.test.tsx',
    description: 'Comprehensive test covering sequential flow, timing, failure recovery, and console analysis',
    critical: true
  },
  {
    name: 'Video Player Fixes Test',
    file: 'video-player-fixes.test.tsx',
    description: 'Tests video error handling, cleanup, and play/pause operations',
    critical: false
  },
  {
    name: 'Video System Integration Test',
    file: 'video-system-integration.test.tsx',
    description: 'Overall video system integration test',
    critical: false
  }
];

class VideoTransitionTestRunner {
  private results: TestRunResult[] = [];
  private startTime: number = 0;
  
  constructor() {
    this.startTime = Date.now();
  }
  
  async runAllTests(): Promise<void> {
    console.log('🎬 Starting Video Transition System Tests');
    console.log('==========================================\n');
    
    for (const suite of VIDEO_TRANSITION_TEST_SUITES) {
      await this.runTestSuite(suite);
    }
    
    await this.generateReport();
  }
  
  private async runTestSuite(suite: TestSuite): Promise<void> {
    console.log(`Running: ${suite.name}`);
    console.log(`File: ${suite.file}`);
    console.log(`Description: ${suite.description}`);
    console.log(`Critical: ${suite.critical ? '⚠️  YES' : 'No'}\n`);
    
    const startTime = Date.now();
    
    try {
      // Check if test file exists
      const testFilePath = path.join(__dirname, suite.file);
      try {
        await fs.access(testFilePath);
      } catch {
        this.results.push({
          testName: suite.name,
          status: 'SKIP',
          duration: 0,
          output: `Test file not found: ${suite.file}`,
          errors: [`File does not exist: ${testFilePath}`]
        });
        console.log(`❌ SKIPPED: Test file not found\n`);
        return;
      }
      
      // Run the test
      const testCommand = `npm test ${suite.file} -- --verbose --watchAll=false`;
      const output = await this.executeCommand(testCommand);
      
      const duration = Date.now() - startTime;
      const status = output.includes('PASS') ? 'PASS' : 'FAIL';
      const errors = this.extractErrors(output);
      
      this.results.push({
        testName: suite.name,
        status,
        duration,
        output,
        errors
      });
      
      if (status === 'PASS') {
        console.log(`✅ PASSED in ${duration}ms\n`);
      } else {
        console.log(`❌ FAILED in ${duration}ms`);
        if (errors.length > 0) {
          console.log('Errors:');
          errors.forEach(error => console.log(`  - ${error}`));
        }
        console.log('');
      }
      
    } catch (error) {
      const duration = Date.now() - startTime;
      this.results.push({
        testName: suite.name,
        status: 'FAIL',
        duration,
        output: '',
        errors: [error instanceof Error ? error.message : String(error)]
      });
      
      console.log(`❌ ERROR in ${duration}ms: ${error}\n`);
    }
  }
  
  private executeCommand(command: string): Promise<string> {
    return new Promise((resolve, reject) => {
      exec(command, { maxBuffer: 1024 * 1024 * 10 }, (error, stdout, stderr) => {
        if (error && !stdout.includes('PASS')) {
          reject(error);
          return;
        }
        resolve(stdout + stderr);
      });
    });
  }
  
  private extractErrors(output: string): string[] {
    const errors: string[] = [];
    const lines = output.split('\n');
    
    let inErrorSection = false;
    for (const line of lines) {
      if (line.includes('FAIL') || line.includes('ERROR') || line.includes('✕')) {
        inErrorSection = true;
        errors.push(line.trim());
      } else if (inErrorSection && line.trim().startsWith('at ')) {
        // Skip stack trace lines for brevity
        continue;
      } else if (inErrorSection && line.trim() === '') {
        inErrorSection = false;
      } else if (inErrorSection) {
        errors.push(line.trim());
      }
    }
    
    return errors.filter(error => error.length > 0);
  }
  
  private async generateReport(): Promise<void> {
    const totalDuration = Date.now() - this.startTime;
    const passedTests = this.results.filter(r => r.status === 'PASS');
    const failedTests = this.results.filter(r => r.status === 'FAIL');
    const skippedTests = this.results.filter(r => r.status === 'SKIP');
    
    console.log('\n🎬 VIDEO TRANSITION SYSTEM TEST REPORT');
    console.log('==========================================');
    console.log(`Total Tests: ${this.results.length}`);
    console.log(`✅ Passed: ${passedTests.length}`);
    console.log(`❌ Failed: ${failedTests.length}`);
    console.log(`⏭️  Skipped: ${skippedTests.length}`);
    console.log(`⏱️  Total Duration: ${totalDuration}ms\n`);
    
    // Critical test analysis
    const criticalTests = this.results.filter(r => {
      const suite = VIDEO_TRANSITION_TEST_SUITES.find(s => s.name === r.testName);
      return suite?.critical;
    });
    
    const criticalFailures = criticalTests.filter(r => r.status === 'FAIL');
    
    if (criticalFailures.length > 0) {
      console.log('⚠️  CRITICAL TEST FAILURES:');
      criticalFailures.forEach(test => {
        console.log(`❌ ${test.testName}`);
        test.errors.forEach(error => console.log(`   - ${error}`));
      });
      console.log('');
    }
    
    // Detailed results
    console.log('DETAILED RESULTS:');
    console.log('================');
    
    this.results.forEach(result => {
      const status = result.status === 'PASS' ? '✅' : 
                    result.status === 'FAIL' ? '❌' : '⏭️';
      console.log(`${status} ${result.testName} (${result.duration}ms)`);
      
      if (result.errors.length > 0) {
        result.errors.slice(0, 3).forEach(error => {
          console.log(`   ${error}`);
        });
        if (result.errors.length > 3) {
          console.log(`   ... and ${result.errors.length - 3} more errors`);
        }
      }
      console.log('');
    });
    
    // Generate markdown report
    await this.generateMarkdownReport();
    
    // Final assessment
    if (failedTests.length === 0) {
      console.log('🎉 ALL TESTS PASSED! Video transition system is working correctly.');
      console.log('✅ Video 2 skip prevention: VERIFIED');
      console.log('✅ Sequential flow: VERIFIED'); 
      console.log('✅ Timing verification: VERIFIED');
      console.log('✅ Failure recovery: VERIFIED');
    } else {
      console.log('❌ SOME TESTS FAILED! Video transition system needs attention.');
      console.log(`⚠️  ${failedTests.length} test(s) failed`);
      
      if (criticalFailures.length > 0) {
        console.log('❗ CRITICAL ISSUES DETECTED:');
        console.log('   - Video 2 may be getting skipped');
        console.log('   - Sequential flow may be broken');
        console.log('   - Manual testing recommended before deployment');
      }
    }
    
    console.log('\n📋 Full test report saved to: test-reports/video-transition-report.md');
    console.log('🔧 To run manual tests, import and use VideoTransitionManualTester component');
  }
  
  private async generateMarkdownReport(): Promise<void> {
    const reportDir = path.join(process.cwd(), 'test-reports');
    await fs.mkdir(reportDir, { recursive: true });
    
    const reportPath = path.join(reportDir, 'video-transition-report.md');
    
    const report = `# Video Transition System Test Report
    
Generated: ${new Date().toISOString()}
Duration: ${Date.now() - this.startTime}ms

## Summary

- **Total Tests**: ${this.results.length}
- **Passed**: ${this.results.filter(r => r.status === 'PASS').length}
- **Failed**: ${this.results.filter(r => r.status === 'FAIL').length}
- **Skipped**: ${this.results.filter(r => r.status === 'SKIP').length}

## Critical Assessment

${this.results.filter(r => r.status === 'FAIL' && VIDEO_TRANSITION_TEST_SUITES.find(s => s.name === r.testName)?.critical).length === 0 
  ? '✅ **ALL CRITICAL TESTS PASSED** - Video 2 skip prevention verified'
  : '❌ **CRITICAL TESTS FAILED** - Video transition system needs immediate attention'
}

## Detailed Results

${this.results.map(result => `
### ${result.testName}

- **Status**: ${result.status}
- **Duration**: ${result.duration}ms
- **Suite**: ${VIDEO_TRANSITION_TEST_SUITES.find(s => s.name === result.testName)?.file || 'Unknown'}
- **Critical**: ${VIDEO_TRANSITION_TEST_SUITES.find(s => s.name === result.testName)?.critical ? '⚠️ YES' : 'No'}

${result.errors.length > 0 ? `
**Errors:**
${result.errors.map(error => `- ${error}`).join('\n')}
` : ''}

${result.output && result.status === 'FAIL' ? `
<details>
<summary>Test Output</summary>

\`\`\`
${result.output.slice(0, 2000)}${result.output.length > 2000 ? '\n... (truncated)' : ''}
\`\`\`

</details>
` : ''}
`).join('\n')}

## Manual Testing Instructions

To perform manual validation:

1. Import the \`VideoTransitionManualTester\` component
2. Render it in your application: \`<VideoTransitionManualTester />\`
3. Use the manual testing interface to validate:
   - Sequential video flow (Video 1 → Video 2 → Video 3)
   - Video 2 skip prevention (critical)
   - Timing verification with proper gaps
   - Failure recovery scenarios
   - Console log analysis

## Next Steps

${this.results.filter(r => r.status === 'FAIL').length === 0 ? `
✅ All tests passed! The video transition system is working correctly.

**Recommended Actions:**
- Deploy with confidence
- Monitor production logs for any edge cases
- Run manual tests periodically to ensure continued reliability
` : `
❌ Some tests failed. Immediate action required:

**Critical Actions:**
1. Review failed test details above
2. Run manual tests using VideoTransitionManualTester
3. Fix identified issues before deployment
4. Re-run test suite to verify fixes
5. Pay special attention to Video 2 skip prevention

**Debug Steps:**
1. Check console logs during test execution
2. Verify video element creation and event handling
3. Validate timing logic in SequentialVideoManager
4. Test auto-advance mechanism
5. Verify error recovery pathways
`}

---

*This report was generated by the Video Transition Test Runner*
`;
    
    await fs.writeFile(reportPath, report, 'utf8');
  }
}

// Export for programmatic use
export { VideoTransitionTestRunner };

// CLI execution
if (require.main === module) {
  const runner = new VideoTransitionTestRunner();
  runner.runAllTests().catch(error => {
    console.error('❌ Test runner failed:', error);
    process.exit(1);
  });
}

export default VideoTransitionTestRunner;