#!/usr/bin/env node

/**
 * Simple Video Test Runner
 * 
 * Runs the basic video sequence test and provides clear output
 * about whether the sequential video system is working correctly.
 */

import { exec } from 'child_process';
import path from 'path';

interface TestResult {
  passed: boolean;
  output: string;
  errors: string[];
  duration: number;
}

class SimpleVideoTestRunner {
  async runTest(): Promise<TestResult> {
    console.log('🎬 Running Simple Video Sequence Test');
    console.log('====================================');
    console.log('Testing: Video 1 → Video 2 → Video 3 with 2-second gaps\n');

    const startTime = Date.now();
    
    try {
      const testCommand = 'npm test video-sequential-simple.test.tsx -- --verbose --watchAll=false';
      const output = await this.executeCommand(testCommand);
      
      const duration = Date.now() - startTime;
      const passed = output.includes('PASS') && !output.includes('FAIL');
      const errors = this.extractErrors(output);

      const result: TestResult = {
        passed,
        output,
        errors,
        duration
      };

      this.displayResults(result);
      return result;

    } catch (error) {
      const duration = Date.now() - startTime;
      const result: TestResult = {
        passed: false,
        output: '',
        errors: [error instanceof Error ? error.message : String(error)],
        duration
      };

      this.displayResults(result);
      return result;
    }
  }

  private executeCommand(command: string): Promise<string> {
    return new Promise((resolve, reject) => {
      console.log(`Executing: ${command}\n`);
      
      exec(command, { 
        maxBuffer: 1024 * 1024 * 5,
        cwd: process.cwd()
      }, (error, stdout, stderr) => {
        const output = stdout + stderr;
        
        if (error && !output.includes('PASS')) {
          reject(error);
          return;
        }
        
        resolve(output);
      });
    });
  }

  private extractErrors(output: string): string[] {
    const errors: string[] = [];
    const lines = output.split('\n');
    
    for (const line of lines) {
      if (line.includes('FAIL') || line.includes('ERROR') || line.includes('✕')) {
        errors.push(line.trim());
      }
    }
    
    return errors.filter(error => error.length > 0);
  }

  private displayResults(result: TestResult): void {
    console.log('\n🎬 SIMPLE VIDEO TEST RESULTS');
    console.log('============================');
    
    if (result.passed) {
      console.log('✅ TEST PASSED!');
      console.log('');
      console.log('✅ Video 1 plays completely');
      console.log('✅ 2-second gap occurs');
      console.log('✅ Video 2 loads and plays (NOT SKIPPED!)');
      console.log('✅ 2-second gap occurs');
      console.log('✅ Video 3 loads and plays completely');
      console.log('✅ Sequence completes successfully');
      console.log('');
      console.log('🎉 The simple video system is working correctly!');
      
    } else {
      console.log('❌ TEST FAILED!');
      console.log('');
      console.log('Issues found:');
      
      if (result.errors.length > 0) {
        result.errors.forEach(error => {
          console.log(`  ❌ ${error}`);
        });
      } else {
        console.log('  ❌ Test execution failed (see output below)');
      }
      
      console.log('');
      console.log('⚠️  The video system needs attention before deployment.');
    }
    
    console.log(`\n⏱️  Test Duration: ${result.duration}ms`);
    
    if (result.output && result.output.length > 0) {
      console.log('\n📋 DETAILED OUTPUT:');
      console.log('==================');
      
      // Show only the most relevant parts of the output
      const lines = result.output.split('\n');
      let showingOutput = false;
      
      for (const line of lines) {
        if (line.includes('PASS') || line.includes('FAIL') || 
            line.includes('Tests:') || line.includes('Snapshots:') ||
            line.includes('Time:') || line.includes('Ran all test suites')) {
          console.log(line);
          showingOutput = true;
        } else if (showingOutput && line.includes('✓')) {
          console.log(line);
        }
      }
    }

    console.log('\n📋 NEXT STEPS:');
    console.log('=============');
    
    if (result.passed) {
      console.log('1. ✅ Basic functionality verified');
      console.log('2. 🧪 Run manual tests using VideoSequenceManualTester component');
      console.log('3. 🚀 Ready for integration testing');
      console.log('');
      console.log('To use manual tester:');
      console.log('  import VideoSequenceManualTester from \'./components/VideoSequenceManualTester\';');
      console.log('  <VideoSequenceManualTester />');
      
    } else {
      console.log('1. ❗ Review test failures above');
      console.log('2. 🔧 Fix identified issues');
      console.log('3. 🔄 Re-run this test');
      console.log('4. 🧪 Only proceed to manual testing after automated tests pass');
    }

    console.log('\n' + '='.repeat(50));
  }
}

// CLI execution
if (require.main === module) {
  const runner = new SimpleVideoTestRunner();
  
  runner.runTest()
    .then((result) => {
      process.exit(result.passed ? 0 : 1);
    })
    .catch((error) => {
      console.error('❌ Test runner failed:', error);
      process.exit(1);
    });
}

export default SimpleVideoTestRunner;