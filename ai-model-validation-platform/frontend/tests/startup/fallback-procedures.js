#!/usr/bin/env node

/**
 * Fallback Startup Procedures System
 * Implements alternative startup methods when primary startup fails
 */

const { spawn, exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class FallbackStartupSystem {
  constructor(options = {}) {
    this.config = {
      maxFallbackAttempts: options.maxFallbackAttempts || 5,
      fallbackDelay: options.fallbackDelay || 3000, // 3 seconds between attempts
      primaryTimeout: options.primaryTimeout || 120000, // 2 minutes
      fallbackTimeout: options.fallbackTimeout || 60000, // 1 minute per fallback
      saveResults: options.saveResults !== false,
      verbose: options.verbose !== false,
      outputFile: options.outputFile || path.join(process.cwd(), 'tests', 'startup', 'fallback-results.json')
    };
    
    this.fallbackResults = {
      startTime: null,
      endTime: null,
      primaryAttempt: null,
      fallbackAttempts: [],
      successfulMethod: null,
      failedMethods: [],
      systemInfo: {},
      recommendations: []
    };
    
    // Define fallback procedures in order of preference
    this.fallbackProcedures = [
      {
        name: 'primary',
        description: 'Standard npm start',
        command: 'npm',
        args: ['start'],
        env: {},
        priority: 1,
        timeout: this.config.primaryTimeout
      },
      {
        name: 'simple-mode',
        description: 'Simple mode with minimal checks',
        command: 'npm',
        args: ['run', 'start:simple'],
        env: {
          SKIP_PREFLIGHT_CHECK: 'true',
          TSC_COMPILE_ON_ERROR: 'true',
          ESLINT_NO_DEV_ERRORS: 'true'
        },
        priority: 2,
        timeout: this.config.fallbackTimeout
      },
      {
        name: 'fast-mode',
        description: 'Fast mode with minimal configuration',
        command: 'npm',
        args: ['run', 'start:fast'],
        env: {
          SKIP_PREFLIGHT_CHECK: 'true',
          ESLINT_NO_DEV_ERRORS: 'true'
        },
        priority: 3,
        timeout: this.config.fallbackTimeout
      },
      {
        name: 'alternative-port',
        description: 'Start on alternative port',
        command: 'npm',
        args: ['start'],
        env: {
          PORT: '3001',
          SKIP_PREFLIGHT_CHECK: 'true',
          TSC_COMPILE_ON_ERROR: 'true',
          ESLINT_NO_DEV_ERRORS: 'true'
        },
        priority: 4,
        timeout: this.config.fallbackTimeout
      },
      {
        name: 'memory-optimized',
        description: 'Memory optimized startup',
        command: 'node',
        args: ['--max-old-space-size=4096', '--optimize-for-size', 'node_modules/.bin/craco', 'start'],
        env: {
          NODE_OPTIONS: '--max-old-space-size=4096',
          SKIP_PREFLIGHT_CHECK: 'true',
          TSC_COMPILE_ON_ERROR: 'true',
          ESLINT_NO_DEV_ERRORS: 'true'
        },
        priority: 5,
        timeout: this.config.fallbackTimeout
      },
      {
        name: 'clean-install',
        description: 'Clean install and start',
        preCommand: 'rm -rf node_modules package-lock.json && npm install',
        command: 'npm',
        args: ['start'],
        env: {
          SKIP_PREFLIGHT_CHECK: 'true',
          ESLINT_NO_DEV_ERRORS: 'true'
        },
        priority: 6,
        timeout: this.config.fallbackTimeout + 60000, // Extra time for install
        requiresPreparation: true
      },
      {
        name: 'development-build',
        description: 'Development build mode',
        command: 'npm',
        args: ['run', 'build:dev'],
        env: {
          NODE_ENV: 'development',
          GENERATE_SOURCEMAP: 'false'
        },
        priority: 7,
        timeout: this.config.fallbackTimeout,
        buildOnly: true
      },
      {
        name: 'safe-mode',
        description: 'Safe mode with all checks disabled',
        command: 'npx',
        args: ['react-scripts', 'start'],
        env: {
          SKIP_PREFLIGHT_CHECK: 'true',
          TSC_COMPILE_ON_ERROR: 'true',
          ESLINT_NO_DEV_ERRORS: 'true',
          DISABLE_ESLINT_PLUGIN: 'true',
          GENERATE_SOURCEMAP: 'false'
        },
        priority: 8,
        timeout: this.config.fallbackTimeout
      }
    ];
  }

  async executeStartupFallback() {
    console.log('🔄 Starting Fallback Startup Procedures System');
    console.log('=' .repeat(60));
    
    this.fallbackResults.startTime = new Date();
    await this.initializeSystem();
    
    console.log(`📋 ${this.fallbackProcedures.length} fallback procedures available`);
    console.log(`⏱️ Primary timeout: ${this.config.primaryTimeout / 1000}s`);
    console.log(`🔄 Fallback timeout: ${this.config.fallbackTimeout / 1000}s each`);
    
    let currentProcedure = 0;
    let successful = false;
    
    // Try each fallback procedure
    while (currentProcedure < this.fallbackProcedures.length && !successful) {
      const procedure = this.fallbackProcedures[currentProcedure];
      
      try {
        console.log(`\n🎯 Attempting: ${procedure.name} (${procedure.description})`);
        
        const result = await this.executeProcedure(procedure);
        
        if (result.success) {
          successful = true;
          this.fallbackResults.successfulMethod = {
            ...procedure,
            result,
            attemptNumber: currentProcedure + 1
          };
          
          console.log(`✅ SUCCESS: ${procedure.name} started successfully!`);
          console.log(`📊 Startup time: ${result.startupTime}ms`);
          console.log(`🔌 Port: ${result.port || 'default'}`);
          
          break;
        } else {
          this.fallbackResults.failedMethods.push({
            ...procedure,
            result,
            attemptNumber: currentProcedure + 1
          });
          
          console.log(`❌ FAILED: ${procedure.name} - ${result.error}`);
          
          if (currentProcedure < this.fallbackProcedures.length - 1) {
            console.log(`⏳ Waiting ${this.config.fallbackDelay / 1000}s before next attempt...`);
            await this.delay(this.config.fallbackDelay);
          }
        }
      } catch (error) {
        console.log(`💥 ERROR in ${procedure.name}: ${error.message}`);
        this.fallbackResults.failedMethods.push({
          ...procedure,
          result: { success: false, error: error.message },
          attemptNumber: currentProcedure + 1
        });
      }
      
      currentProcedure++;
    }
    
    this.fallbackResults.endTime = new Date();
    await this.generateRecommendations();
    
    if (this.config.saveResults) {
      await this.saveResults();
      await this.generateReport();
    }
    
    if (successful) {
      console.log('\n🎉 Fallback system successfully started the application!');
      return this.fallbackResults.successfulMethod;
    } else {
      console.log('\n💀 All fallback procedures failed');
      throw new Error('All fallback startup procedures failed');
    }
  }

  async initializeSystem() {
    // Get system information
    const systemInfo = {
      platform: os.platform(),
      arch: os.arch(),
      nodeVersion: process.version,
      totalMemory: os.totalmem(),
      freeMemory: os.freemem(),
      cpuCount: os.cpus().length,
      workingDirectory: process.cwd(),
      timestamp: new Date().toISOString()
    };
    
    this.fallbackResults.systemInfo = systemInfo;
    
    console.log(`💻 System: ${systemInfo.platform} ${systemInfo.arch}`);
    console.log(`🧮 Memory: ${(systemInfo.totalMemory / 1024 / 1024 / 1024).toFixed(1)}GB total, ${(systemInfo.freeMemory / 1024 / 1024 / 1024).toFixed(1)}GB free`);
    console.log(`⚙️ Node.js: ${systemInfo.nodeVersion}`);
    
    // Create output directory
    if (this.config.saveResults) {
      await fs.mkdir(path.dirname(this.config.outputFile), { recursive: true });
    }
    
    // Clear any existing processes
    await this.cleanupExistingProcesses();
  }

  async cleanupExistingProcesses() {
    console.log('🧹 Cleaning up existing processes...');
    
    try {
      // Kill processes on common ports
      const ports = [3000, 3001, 3002, 3003];
      for (const port of ports) {
        await this.runCommand(`lsof -ti:${port} | xargs kill -9`).catch(() => {});
      }
      
      // Kill React development processes
      await this.runCommand('pkill -f "craco start"').catch(() => {});
      await this.runCommand('pkill -f "react-scripts start"').catch(() => {});
      await this.runCommand('pkill -f "webpack"').catch(() => {});
      
      // Wait for cleanup
      await this.delay(2000);
      
      console.log('✅ Process cleanup completed');
    } catch (error) {
      console.warn(`⚠️ Process cleanup warning: ${error.message}`);
    }
  }

  async executeProcedure(procedure) {
    const startTime = Date.now();
    const result = {
      procedure: procedure.name,
      success: false,
      startTime: new Date(),
      startupTime: 0,
      error: null,
      output: '',
      warnings: []
    };
    
    try {
      // Execute preparation command if required
      if (procedure.requiresPreparation && procedure.preCommand) {
        console.log(`  🔧 Preparing: ${procedure.preCommand}`);
        await this.runCommand(procedure.preCommand);
      }
      
      // Set up environment
      const env = {
        ...process.env,
        HOST: 'localhost',
        ...procedure.env
      };
      
      // Start the process
      const childProcess = await this.startProcess(procedure, env);
      
      // Wait for startup completion or timeout
      const startupResult = await this.waitForStartup(childProcess, procedure);
      
      result.success = startupResult.success;
      result.startupTime = Date.now() - startTime;
      result.output = startupResult.output;
      result.port = startupResult.port;
      result.pid = childProcess.pid;
      
      if (startupResult.success) {
        // Verify the application is actually working
        const healthCheck = await this.performHealthCheck(startupResult.port || 3000);
        result.healthCheck = healthCheck;
        
        if (!healthCheck.healthy) {
          result.warnings.push('Application started but health check failed');
        }
        
        // Keep process running for a moment to ensure stability
        await this.delay(5000);
        
        // Clean shutdown for testing
        if (!procedure.buildOnly) {
          childProcess.kill('SIGTERM');
          await this.delay(2000);
          if (!childProcess.killed) {
            childProcess.kill('SIGKILL');
          }
        }
      } else {
        result.error = startupResult.error;
        
        // Kill the process if it's still running
        if (!childProcess.killed) {
          childProcess.kill('SIGKILL');
        }
      }
      
    } catch (error) {
      result.success = false;
      result.error = error.message;
      result.startupTime = Date.now() - startTime;
    }
    
    result.endTime = new Date();
    return result;
  }

  async startProcess(procedure, env) {
    const spawnOptions = {
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
      detached: false
    };
    
    const childProcess = spawn(procedure.command, procedure.args, spawnOptions);
    
    // Store output for analysis
    childProcess.stdout.setEncoding('utf8');
    childProcess.stderr.setEncoding('utf8');
    
    return childProcess;
  }

  async waitForStartup(childProcess, procedure) {
    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        resolve({
          success: false,
          error: `Startup timeout after ${procedure.timeout}ms`,
          output: stdout + stderr
        });
      }, procedure.timeout);
      
      let stdout = '';
      let stderr = '';
      let resolved = false;
      
      const resolveOnce = (result) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          resolve(result);
        }
      };
      
      childProcess.stdout.on('data', (data) => {
        stdout += data;
        
        if (this.config.verbose) {
          process.stdout.write(`📤 ${data}`);
        }
        
        // Check for success patterns
        if (this.isStartupSuccessful(data)) {
          const port = this.extractPort(stdout + stderr);
          resolveOnce({
            success: true,
            output: stdout + stderr,
            port
          });
        }
      });
      
      childProcess.stderr.on('data', (data) => {
        stderr += data;
        
        if (this.config.verbose) {
          process.stderr.write(`📥 ${data}`);
        }
        
        // Check for critical errors
        if (this.isCriticalError(data)) {
          resolveOnce({
            success: false,
            error: `Critical error: ${data}`,
            output: stdout + stderr
          });
        }
      });
      
      childProcess.on('exit', (code) => {
        if (code !== 0) {
          resolveOnce({
            success: false,
            error: `Process exited with code ${code}`,
            output: stdout + stderr
          });
        }
      });
      
      childProcess.on('error', (error) => {
        resolveOnce({
          success: false,
          error: error.message,
          output: stdout + stderr
        });
      });
    });
  }

  isStartupSuccessful(output) {
    const successPatterns = [
      /webpack compiled/i,
      /compiled successfully/i,
      /Local:\s+http/i,
      /On Your Network:/i,
      /Development server is running/i,
      /App is running at/i
    ];
    
    return successPatterns.some(pattern => pattern.test(output));
  }

  isCriticalError(output) {
    const criticalPatterns = [
      /Cannot find module/i,
      /Module not found/i,
      /EADDRINUSE/i,
      /EACCES.*permission denied/i,
      /ENOENT.*no such file/i,
      /Failed to compile/i,
      /Error: EMFILE/i,
      /JavaScript heap out of memory/i
    ];
    
    return criticalPatterns.some(pattern => pattern.test(output));
  }

  extractPort(output) {
    const portMatches = output.match(/Local:\s+http:\/\/[^:]+:(\d+)/i) || 
                       output.match(/localhost:(\d+)/i) ||
                       output.match(/Port (\d+)/i);
    
    return portMatches ? parseInt(portMatches[1]) : null;
  }

  async performHealthCheck(port = 3000) {
    try {
      // Simple HTTP health check
      const response = await this.runCommand(`curl -s -o /dev/null -w "%{http_code}" http://localhost:${port}`);
      const statusCode = parseInt(response.stdout.trim());
      
      return {
        healthy: statusCode >= 200 && statusCode < 400,
        statusCode,
        port,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        healthy: false,
        error: error.message,
        port,
        timestamp: new Date().toISOString()
      };
    }
  }

  async runCommand(command) {
    return new Promise((resolve, reject) => {
      exec(command, { timeout: 10000 }, (error, stdout, stderr) => {
        if (error) {
          reject(new Error(`${error.message}\nstderr: ${stderr}`));
        } else {
          resolve({ stdout, stderr });
        }
      });
    });
  }

  async delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async generateRecommendations() {
    const recommendations = [];
    const failed = this.fallbackResults.failedMethods;
    const successful = this.fallbackResults.successfulMethod;
    
    // Analyze common failure patterns
    const commonErrors = {};
    failed.forEach(method => {
      if (method.result.error) {
        const errorType = this.categorizeError(method.result.error);
        commonErrors[errorType] = (commonErrors[errorType] || 0) + 1;
      }
    });
    
    // Generate specific recommendations based on failures
    if (commonErrors['PORT_CONFLICT']) {
      recommendations.push({
        priority: 'HIGH',
        category: 'Port Management',
        issue: 'Multiple port conflicts detected',
        solution: 'Implement automatic port selection or use port management script'
      });
    }
    
    if (commonErrors['MEMORY_ERROR']) {
      recommendations.push({
        priority: 'HIGH',
        category: 'Memory Management',
        issue: 'Memory-related startup failures',
        solution: 'Increase Node.js memory limit or implement memory optimization'
      });
    }
    
    if (commonErrors['MODULE_ERROR']) {
      recommendations.push({
        priority: 'MEDIUM',
        category: 'Dependencies',
        issue: 'Module or dependency issues',
        solution: 'Verify package.json and run clean install'
      });
    }
    
    if (commonErrors['PERMISSION_ERROR']) {
      recommendations.push({
        priority: 'HIGH',
        category: 'Permissions',
        issue: 'File system permission errors',
        solution: 'Check directory permissions and user access rights'
      });
    }
    
    // Success-based recommendations
    if (successful) {
      if (successful.result.warnings && successful.result.warnings.length > 0) {
        recommendations.push({
          priority: 'LOW',
          category: 'Optimization',
          issue: 'Successful startup had warnings',
          solution: 'Address startup warnings to improve reliability'
        });
      }
      
      if (successful.attemptNumber > 1) {
        recommendations.push({
          priority: 'MEDIUM',
          category: 'Primary Startup',
          issue: 'Primary startup method failed',
          solution: `Consider using ${successful.name} as primary startup method`
        });
      }
    } else {
      recommendations.push({
        priority: 'CRITICAL',
        category: 'System Health',
        issue: 'All fallback procedures failed',
        solution: 'Review system requirements, dependencies, and environment configuration'
      });
    }
    
    // Performance recommendations
    if (successful && successful.result.startupTime > 60000) {
      recommendations.push({
        priority: 'MEDIUM',
        category: 'Performance',
        issue: 'Slow startup time',
        solution: 'Optimize startup process or use faster fallback method as primary'
      });
    }
    
    this.fallbackResults.recommendations = recommendations;
  }

  categorizeError(error) {
    if (/EADDRINUSE|port.*already.*use/i.test(error)) return 'PORT_CONFLICT';
    if (/memory|heap/i.test(error)) return 'MEMORY_ERROR';
    if (/cannot find module|module not found/i.test(error)) return 'MODULE_ERROR';
    if (/EACCES|permission denied/i.test(error)) return 'PERMISSION_ERROR';
    if (/timeout/i.test(error)) return 'TIMEOUT_ERROR';
    if (/ENOENT|no such file/i.test(error)) return 'FILE_ERROR';
    return 'UNKNOWN_ERROR';
  }

  async saveResults() {
    await fs.writeFile(this.config.outputFile, JSON.stringify(this.fallbackResults, null, 2));
    console.log(`\n💾 Results saved to: ${this.config.outputFile}`);
  }

  async generateReport() {
    const reportPath = path.join(process.cwd(), 'tests', 'startup', 'fallback-procedures-report.md');
    
    const duration = this.fallbackResults.endTime - this.fallbackResults.startTime;
    const successful = this.fallbackResults.successfulMethod;
    const failed = this.fallbackResults.failedMethods;
    
    const report = `# Fallback Startup Procedures Report

Generated: ${new Date().toISOString()}
Duration: ${Math.round(duration / 1000)}s
Total Procedures: ${this.fallbackProcedures.length}
Success Rate: ${successful ? '1' : '0'}/${this.fallbackProcedures.length}

## System Information

- **Platform**: ${this.fallbackResults.systemInfo.platform} ${this.fallbackResults.systemInfo.arch}
- **Node.js Version**: ${this.fallbackResults.systemInfo.nodeVersion}
- **Total Memory**: ${(this.fallbackResults.systemInfo.totalMemory / 1024 / 1024 / 1024).toFixed(1)}GB
- **Free Memory**: ${(this.fallbackResults.systemInfo.freeMemory / 1024 / 1024 / 1024).toFixed(1)}GB

## Results Summary

${successful ? `### ✅ Successful Method: ${successful.name}

- **Description**: ${successful.description}
- **Attempt Number**: ${successful.attemptNumber}
- **Startup Time**: ${successful.result.startupTime}ms
- **Port**: ${successful.result.port || 'default'}
- **Command**: ${successful.command} ${successful.args.join(' ')}
${successful.result.healthCheck ? `- **Health Check**: ${successful.result.healthCheck.healthy ? 'Passed' : 'Failed'}` : ''}
` : '### ❌ No Successful Method\nAll fallback procedures failed.'}

## Failed Methods

${failed.map(method => `
### ❌ ${method.name} (Attempt ${method.attemptNumber})

- **Description**: ${method.description}
- **Command**: ${method.command} ${method.args.join(' ')}
- **Error**: ${method.result.error}
- **Duration**: ${method.result.startupTime}ms
${method.result.output ? `- **Output Sample**: \`${method.result.output.substring(0, 100)}...\`` : ''}
`).join('')}

## Recommendations

${this.fallbackResults.recommendations.map((rec, i) => `
${i + 1}. **${rec.priority}** - ${rec.category}
   - **Issue**: ${rec.issue}
   - **Solution**: ${rec.solution}
`).join('')}

## Emergency Startup Commands

Based on the test results, here are emergency startup commands in order of preference:

${successful ? `
1. **Recommended (Successful)**: 
   \`\`\`bash
   ${successful.env ? Object.entries(successful.env).map(([k, v]) => `${k}=${v}`).join(' ') + ' ' : ''}${successful.command} ${successful.args.join(' ')}
   \`\`\`
` : ''}

2. **Safe Mode**:
   \`\`\`bash
   SKIP_PREFLIGHT_CHECK=true TSC_COMPILE_ON_ERROR=true ESLINT_NO_DEV_ERRORS=true npm start
   \`\`\`

3. **Alternative Port**:
   \`\`\`bash
   PORT=3001 SKIP_PREFLIGHT_CHECK=true npm start
   \`\`\`

4. **Memory Optimized**:
   \`\`\`bash
   NODE_OPTIONS="--max-old-space-size=4096" npm start
   \`\`\`

5. **Clean Install**:
   \`\`\`bash
   rm -rf node_modules package-lock.json && npm install && npm start
   \`\`\`

## Troubleshooting Guide

### If Primary Startup Fails:
1. Check for port conflicts: \`lsof -i :3000\`
2. Kill existing processes: \`pkill -f "craco start"\`
3. Try alternative port: \`PORT=3001 npm start\`
4. Use safe mode with disabled checks

### If Memory Errors Occur:
1. Increase Node.js memory: \`NODE_OPTIONS="--max-old-space-size=4096" npm start\`
2. Clear caches: \`npm cache clean --force\`
3. Close other applications

### If Module Errors Occur:
1. Verify dependencies: \`npm ls\`
2. Clean install: \`rm -rf node_modules && npm install\`
3. Check package.json for issues

### If Permission Errors Occur:
1. Check directory permissions
2. Avoid running as root
3. Fix ownership: \`sudo chown -R $USER:$USER .\`
`;

    await fs.writeFile(reportPath, report);
    console.log(`📋 Report saved to: ${reportPath}`);
  }
}

// CLI Interface
if (require.main === module) {
  const fallbackSystem = new FallbackStartupSystem({
    verbose: process.argv.includes('--verbose') || process.argv.includes('-v'),
    saveResults: !process.argv.includes('--no-save')
  });
  
  console.log('🚀 Starting Fallback Startup Procedures Test');
  
  fallbackSystem.executeStartupFallback()
    .then(result => {
      console.log('\n🎉 Fallback system test completed successfully!');
      console.log(`✅ Successful method: ${result.name}`);
      console.log(`⏱️ Startup time: ${result.result.startupTime}ms`);
      process.exit(0);
    })
    .catch(error => {
      console.error('\n💀 Fallback system test failed completely');
      console.error(`❌ Error: ${error.message}`);
      process.exit(1);
    });
}

module.exports = FallbackStartupSystem;