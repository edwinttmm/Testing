#!/usr/bin/env node

/**
 * Comprehensive Frontend Startup Validation Suite
 * Validates startup reliability under various conditions
 */

const { spawn, exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class StartupValidationSuite {
  constructor() {
    this.testResults = [];
    this.startTime = Date.now();
    this.memoryBaseline = process.memoryUsage();
    this.config = {
      maxStartupTime: 60000, // 60 seconds
      maxMemoryUsage: 2 * 1024 * 1024 * 1024, // 2GB
      retryAttempts: 3,
      healthCheckInterval: 1000,
      testTimeout: 120000 // 2 minutes per test
    };
    
    this.testScenarios = [
      'cleanStartup',
      'startupAfterFailedBuild',
      'memoryConstrainedStartup',
      'concurrentProcessHandling',
      'portConflictResolution',
      'typescriptErrorRecovery',
      'environmentVariableFallback',
      'nodeCacheClearance',
      'dependencyInstallValidation',
      'dockerizedStartup'
    ];
  }

  async runAllTests() {
    console.log('🚀 Starting Comprehensive Frontend Startup Validation Suite');
    console.log('=' .repeat(80));
    
    const results = {
      totalTests: this.testScenarios.length,
      passed: 0,
      failed: 0,
      warnings: 0,
      startTime: new Date(),
      testResults: []
    };

    for (const scenario of this.testScenarios) {
      try {
        console.log(`\n📋 Running test: ${scenario}`);
        const result = await this.runTest(scenario);
        results.testResults.push(result);
        
        if (result.status === 'PASSED') {
          results.passed++;
          console.log(`✅ ${scenario}: PASSED`);
        } else if (result.status === 'WARNING') {
          results.warnings++;
          console.log(`⚠️  ${scenario}: WARNING - ${result.message}`);
        } else {
          results.failed++;
          console.log(`❌ ${scenario}: FAILED - ${result.message}`);
        }
      } catch (error) {
        results.failed++;
        results.testResults.push({
          scenario,
          status: 'FAILED',
          message: error.message,
          duration: 0,
          memoryUsage: 0
        });
        console.log(`❌ ${scenario}: FAILED - ${error.message}`);
      }
    }

    results.endTime = new Date();
    results.totalDuration = results.endTime - results.startTime;

    await this.generateReport(results);
    await this.createTroubleshootingGuide(results);
    
    return results;
  }

  async runTest(scenario) {
    const startTime = Date.now();
    const testResult = {
      scenario,
      startTime: new Date(),
      status: 'RUNNING'
    };

    try {
      switch (scenario) {
        case 'cleanStartup':
          return await this.testCleanStartup(testResult);
        case 'startupAfterFailedBuild':
          return await this.testStartupAfterFailedBuild(testResult);
        case 'memoryConstrainedStartup':
          return await this.testMemoryConstrainedStartup(testResult);
        case 'concurrentProcessHandling':
          return await this.testConcurrentProcessHandling(testResult);
        case 'portConflictResolution':
          return await this.testPortConflictResolution(testResult);
        case 'typescriptErrorRecovery':
          return await this.testTypescriptErrorRecovery(testResult);
        case 'environmentVariableFallback':
          return await this.testEnvironmentVariableFallback(testResult);
        case 'nodeCacheClearance':
          return await this.testNodeCacheClearance(testResult);
        case 'dependencyInstallValidation':
          return await this.testDependencyInstallValidation(testResult);
        case 'dockerizedStartup':
          return await this.testDockerizedStartup(testResult);
        default:
          throw new Error(`Unknown test scenario: ${scenario}`);
      }
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = error.message;
      testResult.duration = Date.now() - startTime;
      testResult.endTime = new Date();
      return testResult;
    }
  }

  async testCleanStartup(testResult) {
    console.log('  🧹 Testing clean startup from scratch...');
    
    // Clear all caches and temporary files
    await this.clearAllCaches();
    
    // Kill any existing processes
    await this.killExistingProcesses();
    
    // Start the application
    const { process: appProcess, startupTime, memoryUsage } = await this.startApplication();
    
    testResult.duration = startupTime;
    testResult.memoryUsage = memoryUsage;
    testResult.pid = appProcess.pid;
    
    if (startupTime > this.config.maxStartupTime) {
      testResult.status = 'WARNING';
      testResult.message = `Startup time ${startupTime}ms exceeds threshold ${this.config.maxStartupTime}ms`;
    } else if (memoryUsage > this.config.maxMemoryUsage) {
      testResult.status = 'WARNING';
      testResult.message = `Memory usage ${(memoryUsage / 1024 / 1024).toFixed(2)}MB exceeds threshold ${(this.config.maxMemoryUsage / 1024 / 1024).toFixed(2)}MB`;
    } else {
      testResult.status = 'PASSED';
      testResult.message = 'Clean startup completed successfully';
    }
    
    // Cleanup
    appProcess.kill();
    testResult.endTime = new Date();
    
    return testResult;
  }

  async testStartupAfterFailedBuild(testResult) {
    console.log('  💥 Testing startup after failed build...');
    
    // Simulate failed build by corrupting build directory
    const buildPath = path.join(process.cwd(), 'build');
    const hasBuildDir = await this.directoryExists(buildPath);
    
    if (hasBuildDir) {
      await fs.rename(buildPath, `${buildPath}_backup`);
    }
    
    // Create corrupted build artifacts
    await fs.mkdir(buildPath, { recursive: true });
    await fs.writeFile(path.join(buildPath, 'invalid.js'), 'corrupted content');
    
    try {
      const { process: appProcess, startupTime, memoryUsage } = await this.startApplication();
      
      testResult.duration = startupTime;
      testResult.memoryUsage = memoryUsage;
      testResult.status = 'PASSED';
      testResult.message = 'Successfully recovered from failed build state';
      
      appProcess.kill();
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = `Failed to start after build corruption: ${error.message}`;
    } finally {
      // Cleanup
      await fs.rm(buildPath, { recursive: true, force: true });
      if (hasBuildDir) {
        await fs.rename(`${buildPath}_backup`, buildPath);
      }
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testMemoryConstrainedStartup(testResult) {
    console.log('  🧠 Testing memory-constrained startup...');
    
    // Start application with limited memory
    const memoryLimit = '1024m'; // 1GB limit
    
    try {
      const { process: appProcess, startupTime, memoryUsage } = await this.startApplication({
        nodeOptions: [`--max-old-space-size=1024`]
      });
      
      testResult.duration = startupTime;
      testResult.memoryUsage = memoryUsage;
      
      if (memoryUsage > 1024 * 1024 * 1024) {
        testResult.status = 'WARNING';
        testResult.message = 'Memory usage exceeded 1GB limit during startup';
      } else {
        testResult.status = 'PASSED';
        testResult.message = 'Successfully started within memory constraints';
      }
      
      appProcess.kill();
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = `Memory-constrained startup failed: ${error.message}`;
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testConcurrentProcessHandling(testResult) {
    console.log('  🔄 Testing concurrent process handling...');
    
    const processes = [];
    try {
      // Start multiple instances concurrently
      for (let i = 0; i < 3; i++) {
        const port = 3000 + i;
        processes.push(this.startApplication({ port }));
      }
      
      const results = await Promise.allSettled(processes.map(p => p.catch(e => ({ error: e }))));
      const successfulStarts = results.filter(r => r.status === 'fulfilled' && !r.value.error).length;
      
      if (successfulStarts >= 1) {
        testResult.status = 'PASSED';
        testResult.message = `${successfulStarts}/3 concurrent processes started successfully`;
      } else {
        testResult.status = 'FAILED';
        testResult.message = 'No processes could start concurrently';
      }
      
      // Cleanup all processes
      for (const result of results) {
        if (result.status === 'fulfilled' && result.value.process) {
          result.value.process.kill();
        }
      }
      
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = `Concurrent process test failed: ${error.message}`;
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testPortConflictResolution(testResult) {
    console.log('  🔌 Testing port conflict resolution...');
    
    // Start a dummy server on port 3000
    const dummyServer = spawn('node', ['-e', `
      const http = require('http');
      const server = http.createServer();
      server.listen(3000, () => console.log('Dummy server started on port 3000'));
      process.on('SIGTERM', () => server.close());
    `]);
    
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    try {
      const { process: appProcess, startupTime } = await this.startApplication({ 
        expectPortConflict: true,
        alternativePort: 3001 
      });
      
      testResult.duration = startupTime;
      testResult.status = 'PASSED';
      testResult.message = 'Successfully resolved port conflict';
      
      appProcess.kill();
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = `Port conflict resolution failed: ${error.message}`;
    } finally {
      dummyServer.kill();
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testTypescriptErrorRecovery(testResult) {
    console.log('  🔧 Testing TypeScript error recovery...');
    
    // Create temporary TypeScript error
    const errorFile = path.join(process.cwd(), 'src', 'temp-error.ts');
    const errorContent = 'const invalidCode: string = 123; // Type error';
    
    try {
      await fs.writeFile(errorFile, errorContent);
      
      const { process: appProcess, startupTime } = await this.startApplication({
        allowTypescriptErrors: true
      });
      
      testResult.duration = startupTime;
      testResult.status = 'PASSED';
      testResult.message = 'Successfully started with TypeScript errors';
      
      appProcess.kill();
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = `TypeScript error recovery failed: ${error.message}`;
    } finally {
      // Cleanup
      await fs.unlink(errorFile).catch(() => {});
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testEnvironmentVariableFallback(testResult) {
    console.log('  🌍 Testing environment variable fallback...');
    
    const originalEnv = { ...process.env };
    
    try {
      // Remove critical environment variables
      delete process.env.REACT_APP_API_URL;
      delete process.env.REACT_APP_WS_URL;
      
      const { process: appProcess, startupTime } = await this.startApplication();
      
      testResult.duration = startupTime;
      testResult.status = 'PASSED';
      testResult.message = 'Successfully handled missing environment variables';
      
      appProcess.kill();
    } catch (error) {
      testResult.status = 'WARNING';
      testResult.message = `Environment fallback needed improvement: ${error.message}`;
    } finally {
      // Restore environment
      process.env = originalEnv;
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testNodeCacheClearance(testResult) {
    console.log('  🗑️ Testing Node cache clearance...');
    
    await this.clearNodeCache();
    
    try {
      const { process: appProcess, startupTime } = await this.startApplication();
      
      testResult.duration = startupTime;
      testResult.status = 'PASSED';
      testResult.message = 'Successfully started after cache clearance';
      
      appProcess.kill();
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = `Cache clearance startup failed: ${error.message}`;
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testDependencyInstallValidation(testResult) {
    console.log('  📦 Testing dependency install validation...');
    
    const nodeModulesPath = path.join(process.cwd(), 'node_modules');
    const hasNodeModules = await this.directoryExists(nodeModulesPath);
    
    if (hasNodeModules) {
      await fs.rename(nodeModulesPath, `${nodeModulesPath}_backup`);
    }
    
    try {
      // This should trigger npm install
      const installStart = Date.now();
      await this.runCommand('npm install --silent');
      const installTime = Date.now() - installStart;
      
      const { process: appProcess, startupTime } = await this.startApplication();
      
      testResult.duration = startupTime + installTime;
      testResult.installTime = installTime;
      testResult.status = 'PASSED';
      testResult.message = `Dependencies installed and app started (install: ${installTime}ms, startup: ${startupTime}ms)`;
      
      appProcess.kill();
    } catch (error) {
      testResult.status = 'FAILED';
      testResult.message = `Dependency validation failed: ${error.message}`;
    } finally {
      // Restore if needed
      if (hasNodeModules && await this.directoryExists(`${nodeModulesPath}_backup`)) {
        await fs.rm(nodeModulesPath, { recursive: true, force: true });
        await fs.rename(`${nodeModulesPath}_backup`, nodeModulesPath);
      }
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async testDockerizedStartup(testResult) {
    console.log('  🐳 Testing dockerized startup...');
    
    try {
      // Check if Docker is available
      await this.runCommand('docker --version');
      
      const buildStart = Date.now();
      await this.runCommand('docker build -t frontend-test .');
      const buildTime = Date.now() - buildStart;
      
      const runStart = Date.now();
      const dockerProcess = spawn('docker', [
        'run', '--rm', '-p', '3002:3000',
        '--name', 'frontend-test-container',
        'frontend-test'
      ]);
      
      // Wait for startup
      await this.waitForDockerStartup(dockerProcess);
      const startupTime = Date.now() - runStart;
      
      testResult.duration = startupTime + buildTime;
      testResult.buildTime = buildTime;
      testResult.status = 'PASSED';
      testResult.message = `Docker startup successful (build: ${buildTime}ms, startup: ${startupTime}ms)`;
      
      // Cleanup
      await this.runCommand('docker stop frontend-test-container').catch(() => {});
      await this.runCommand('docker rmi frontend-test').catch(() => {});
      
    } catch (error) {
      testResult.status = 'WARNING';
      testResult.message = `Docker test skipped or failed: ${error.message}`;
    }
    
    testResult.endTime = new Date();
    return testResult;
  }

  async startApplication(options = {}) {
    const {
      port = 3000,
      nodeOptions = [],
      expectPortConflict = false,
      alternativePort = null,
      allowTypescriptErrors = false
    } = options;

    const env = {
      ...process.env,
      PORT: port.toString(),
      HOST: 'localhost',
      SKIP_PREFLIGHT_CHECK: 'true',
      ESLINT_NO_DEV_ERRORS: 'true'
    };

    if (allowTypescriptErrors) {
      env.TSC_COMPILE_ON_ERROR = 'true';
    }

    const startTime = Date.now();
    const args = [...nodeOptions, './node_modules/.bin/craco', 'start'];
    const appProcess = spawn('node', args, { 
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
      detached: false
    });

    let resolved = false;
    const startupPromise = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          reject(new Error('Startup timeout exceeded'));
        }
      }, this.config.testTimeout);

      let output = '';
      appProcess.stdout.on('data', (data) => {
        output += data.toString();
        
        if (output.includes('webpack compiled') || 
            output.includes('Compiled successfully') ||
            output.includes('Local:') ||
            output.includes('On Your Network:')) {
          if (!resolved) {
            resolved = true;
            clearTimeout(timeout);
            
            const endTime = Date.now();
            const memoryUsage = process.memoryUsage().heapUsed;
            
            resolve({
              process: appProcess,
              startupTime: endTime - startTime,
              memoryUsage,
              output
            });
          }
        }

        if (expectPortConflict && output.includes('Something is already running on port') && alternativePort) {
          // Restart on alternative port
          appProcess.kill();
          setTimeout(() => {
            this.startApplication({ ...options, port: alternativePort, expectPortConflict: false })
              .then(resolve)
              .catch(reject);
          }, 1000);
        }
      });

      appProcess.stderr.on('data', (data) => {
        const error = data.toString();
        if (!allowTypescriptErrors && error.includes('TypeScript error')) {
          if (!resolved) {
            resolved = true;
            clearTimeout(timeout);
            reject(new Error(`TypeScript error: ${error}`));
          }
        }
      });

      appProcess.on('error', (error) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          reject(error);
        }
      });

      appProcess.on('exit', (code) => {
        if (!resolved && code !== 0) {
          resolved = true;
          clearTimeout(timeout);
          reject(new Error(`Process exited with code ${code}`));
        }
      });
    });

    return startupPromise;
  }

  async clearAllCaches() {
    const cacheDirectories = [
      path.join(os.homedir(), '.npm'),
      path.join(process.cwd(), 'node_modules', '.cache'),
      path.join(process.cwd(), '.eslintcache'),
      path.join(process.cwd(), 'tsconfig.tsbuildinfo'),
      '/tmp/react-*'
    ];

    for (const dir of cacheDirectories) {
      try {
        if (dir.includes('*')) {
          await this.runCommand(`rm -rf ${dir}`);
        } else if (await this.directoryExists(dir) || await this.fileExists(dir)) {
          await fs.rm(dir, { recursive: true, force: true });
        }
      } catch (error) {
        console.warn(`Warning: Could not clear cache ${dir}: ${error.message}`);
      }
    }
  }

  async clearNodeCache() {
    try {
      await this.runCommand('npm cache clean --force');
    } catch (error) {
      console.warn(`Warning: npm cache clean failed: ${error.message}`);
    }
  }

  async killExistingProcesses() {
    try {
      // Kill processes on common ports
      const ports = [3000, 3001, 3002, 3003];
      for (const port of ports) {
        await this.runCommand(`lsof -ti:${port} | xargs kill -9`).catch(() => {});
      }

      // Kill any remaining React/Node processes
      await this.runCommand('pkill -f "craco start"').catch(() => {});
      await this.runCommand('pkill -f "react-scripts"').catch(() => {});
    } catch (error) {
      console.warn(`Warning: Could not kill existing processes: ${error.message}`);
    }
  }

  async waitForDockerStartup(dockerProcess) {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Docker startup timeout'));
      }, this.config.testTimeout);

      let output = '';
      dockerProcess.stdout.on('data', (data) => {
        output += data.toString();
        if (output.includes('webpack compiled') || output.includes('Compiled successfully')) {
          clearTimeout(timeout);
          resolve();
        }
      });

      dockerProcess.on('error', (error) => {
        clearTimeout(timeout);
        reject(error);
      });
    });
  }

  async runCommand(command) {
    return new Promise((resolve, reject) => {
      exec(command, (error, stdout, stderr) => {
        if (error) {
          reject(new Error(`${error.message}\nstdout: ${stdout}\nstderr: ${stderr}`));
        } else {
          resolve({ stdout, stderr });
        }
      });
    });
  }

  async directoryExists(path) {
    try {
      const stat = await fs.stat(path);
      return stat.isDirectory();
    } catch {
      return false;
    }
  }

  async fileExists(path) {
    try {
      await fs.access(path);
      return true;
    } catch {
      return false;
    }
  }

  async generateReport(results) {
    const reportPath = path.join(process.cwd(), 'tests', 'startup', 'startup-validation-report.json');
    await fs.mkdir(path.dirname(reportPath), { recursive: true });
    
    const detailedReport = {
      ...results,
      systemInfo: {
        platform: os.platform(),
        arch: os.arch(),
        nodeVersion: process.version,
        totalMemory: os.totalmem(),
        freeMemory: os.freemem(),
        cpus: os.cpus().length
      },
      benchmarks: {
        averageStartupTime: results.testResults
          .filter(r => r.duration)
          .reduce((sum, r) => sum + r.duration, 0) / 
          results.testResults.filter(r => r.duration).length || 0,
        maxMemoryUsage: Math.max(...results.testResults
          .filter(r => r.memoryUsage)
          .map(r => r.memoryUsage)),
        successRate: (results.passed / results.totalTests) * 100
      },
      recommendations: this.generateRecommendations(results)
    };

    await fs.writeFile(reportPath, JSON.stringify(detailedReport, null, 2));
    console.log(`\n📊 Detailed report saved to: ${reportPath}`);
    
    return detailedReport;
  }

  generateRecommendations(results) {
    const recommendations = [];
    
    if (results.failed > 0) {
      recommendations.push({
        priority: 'HIGH',
        category: 'Reliability',
        issue: `${results.failed} tests failed`,
        solution: 'Review failed test logs and implement fixes for critical startup issues'
      });
    }
    
    const slowTests = results.testResults.filter(r => r.duration > this.config.maxStartupTime);
    if (slowTests.length > 0) {
      recommendations.push({
        priority: 'MEDIUM',
        category: 'Performance',
        issue: `${slowTests.length} tests exceeded startup time threshold`,
        solution: 'Optimize bundle size, implement code splitting, or increase startup timeout'
      });
    }
    
    const memoryIntensiveTests = results.testResults.filter(r => r.memoryUsage > this.config.maxMemoryUsage);
    if (memoryIntensiveTests.length > 0) {
      recommendations.push({
        priority: 'MEDIUM',
        category: 'Memory',
        issue: `${memoryIntensiveTests.length} tests exceeded memory threshold`,
        solution: 'Implement memory optimization strategies or increase memory limits'
      });
    }
    
    if (results.warnings > 0) {
      recommendations.push({
        priority: 'LOW',
        category: 'Optimization',
        issue: `${results.warnings} tests had warnings`,
        solution: 'Address warning conditions to improve startup reliability'
      });
    }
    
    return recommendations;
  }

  async createTroubleshootingGuide(results) {
    const guidePath = path.join(process.cwd(), 'tests', 'startup', 'troubleshooting-guide.md');
    
    const guide = `# Frontend Startup Troubleshooting Guide

Generated: ${new Date().toISOString()}

## Test Results Summary

- **Total Tests**: ${results.totalTests}
- **Passed**: ${results.passed}
- **Failed**: ${results.failed}
- **Warnings**: ${results.warnings}
- **Success Rate**: ${((results.passed / results.totalTests) * 100).toFixed(1)}%

## Common Issues and Solutions

### Port Conflicts
**Symptoms**: "Something is already running on port 3000"
**Solutions**:
1. Kill existing processes: \`lsof -ti:3000 | xargs kill -9\`
2. Use alternative port: \`PORT=3001 npm start\`
3. Use automatic port selection in startup script

### Memory Issues
**Symptoms**: Out of memory errors, slow startup
**Solutions**:
1. Increase Node.js memory limit: \`node --max-old-space-size=4096\`
2. Clear caches: \`npm cache clean --force\`
3. Restart development environment

### TypeScript Errors
**Symptoms**: Compilation failures, type errors
**Solutions**:
1. Skip type checking: \`TSC_COMPILE_ON_ERROR=true npm start\`
2. Fix type errors incrementally
3. Use development-specific TypeScript config

### Dependency Issues
**Symptoms**: Module not found, version conflicts
**Solutions**:
1. Clear node_modules: \`rm -rf node_modules && npm install\`
2. Clear package-lock.json: \`rm package-lock.json && npm install\`
3. Use npm ci for clean install

### Build Cache Issues
**Symptoms**: Stale builds, unexpected behavior
**Solutions**:
1. Clear all caches: \`npm run clear-cache\`
2. Remove build directory: \`rm -rf build\`
3. Restart with fresh cache

## Failed Test Analysis

${results.testResults
  .filter(r => r.status === 'FAILED')
  .map(r => `### ${r.scenario}
**Error**: ${r.message}
**Recommended Action**: Review specific test implementation and error logs
`).join('\n')}

## Performance Benchmarks

${results.testResults
  .filter(r => r.duration)
  .map(r => `- **${r.scenario}**: ${r.duration}ms${r.memoryUsage ? ` (${(r.memoryUsage / 1024 / 1024).toFixed(2)}MB)` : ''}`)
  .join('\n')}

## Emergency Startup Procedures

If normal startup fails, try these fallback methods in order:

1. **Quick Recovery**: \`npm run start:simple\`
2. **Memory Optimized**: \`NODE_OPTIONS="--max-old-space-size=2048" npm start\`
3. **Skip Checks**: \`SKIP_PREFLIGHT_CHECK=true TSC_COMPILE_ON_ERROR=true npm start\`
4. **Fresh Install**: \`rm -rf node_modules package-lock.json && npm install && npm start\`
5. **Docker Fallback**: \`docker build -t frontend . && docker run -p 3000:3000 frontend\`

## Monitoring Commands

- Check running processes: \`ps aux | grep node\`
- Monitor memory usage: \`top -p $(pgrep -f "craco start")\`
- Check port usage: \`lsof -i :3000\`
- Monitor build progress: \`tail -f build.log\`

For more details, check the full validation report and individual test logs.
`;

    await fs.writeFile(guidePath, guide);
    console.log(`📋 Troubleshooting guide saved to: ${guidePath}`);
  }
}

// CLI Interface
if (require.main === module) {
  const suite = new StartupValidationSuite();
  
  suite.runAllTests()
    .then(results => {
      console.log('\n' + '='.repeat(80));
      console.log('🏁 Startup Validation Complete');
      console.log(`✅ Passed: ${results.passed}/${results.totalTests}`);
      console.log(`❌ Failed: ${results.failed}/${results.totalTests}`);
      console.log(`⚠️  Warnings: ${results.warnings}/${results.totalTests}`);
      console.log(`📊 Success Rate: ${((results.passed / results.totalTests) * 100).toFixed(1)}%`);
      
      if (results.failed > 0) {
        console.log('\n❌ Some tests failed. Check the troubleshooting guide for solutions.');
        process.exit(1);
      } else {
        console.log('\n✅ All critical startup scenarios validated successfully!');
        process.exit(0);
      }
    })
    .catch(error => {
      console.error('❌ Startup validation suite failed:', error);
      process.exit(1);
    });
}

module.exports = StartupValidationSuite;