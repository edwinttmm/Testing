#!/usr/bin/env node

/**
 * Process Health Monitoring System
 * Monitors Node.js process health during startup with automatic recovery
 */

const { spawn, exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class ProcessHealthMonitor {
  constructor(options = {}) {
    this.config = {
      healthCheckInterval: options.healthCheckInterval || 2000, // 2 seconds
      recoveryAttempts: options.recoveryAttempts || 3,
      healthTimeout: options.healthTimeout || 10000, // 10 seconds
      processTimeout: options.processTimeout || 120000, // 2 minutes
      cpuThreshold: options.cpuThreshold || 80, // 80% CPU usage
      memoryThreshold: options.memoryThreshold || 2048, // 2GB in MB
      responseTimeout: options.responseTimeout || 5000, // 5 seconds
      autoRestart: options.autoRestart !== false, // Default true
      outputFile: options.outputFile || path.join(process.cwd(), 'tests', 'startup', 'process-health-results.json')
    };
    
    this.healthData = {
      startTime: null,
      endTime: null,
      processHistory: [],
      healthChecks: [],
      recoveryActions: [],
      alerts: [],
      summary: {}
    };
    
    this.isMonitoring = false;
    this.currentProcess = null;
    this.healthTimer = null;
    this.recoveryInProgress = false;
  }

  async startMonitoring(command, args = [], options = {}) {
    console.log('🏥 Starting Process Health Monitoring System');
    console.log('=' .repeat(60));
    
    this.healthData.startTime = new Date();
    this.isMonitoring = true;
    
    await this.initializeMonitoring();
    
    console.log(`📋 Command: ${command} ${args.join(' ')}`);
    console.log(`⏱️ Health check interval: ${this.config.healthCheckInterval}ms`);
    console.log(`🔄 Auto-restart: ${this.config.autoRestart ? 'Enabled' : 'Disabled'}`);
    console.log(`🚨 CPU threshold: ${this.config.cpuThreshold}%`);
    console.log(`🧠 Memory threshold: ${this.config.memoryThreshold}MB`);
    
    return this.startProcessWithHealthChecks(command, args, options);
  }

  async stopMonitoring() {
    this.isMonitoring = false;
    
    if (this.healthTimer) {
      clearInterval(this.healthTimer);
    }
    
    if (this.currentProcess && !this.currentProcess.killed) {
      console.log('🛑 Stopping monitored process...');
      this.currentProcess.kill('SIGTERM');
      
      // Force kill if not stopped in 5 seconds
      setTimeout(() => {
        if (this.currentProcess && !this.currentProcess.killed) {
          this.currentProcess.kill('SIGKILL');
        }
      }, 5000);
    }
    
    this.healthData.endTime = new Date();
    this.generateSummary();
    
    await this.saveResults();
    await this.generateReport();
    
    console.log('\n🏁 Process health monitoring stopped');
    return this.healthData;
  }

  async initializeMonitoring() {
    // Create output directory
    await fs.mkdir(path.dirname(this.config.outputFile), { recursive: true });
    
    // Get system info
    const systemInfo = {
      platform: os.platform(),
      arch: os.arch(),
      nodeVersion: process.version,
      totalMemory: os.totalmem(),
      cpuCount: os.cpus().length,
      uptime: os.uptime()
    };
    
    this.healthData.systemInfo = systemInfo;
    
    console.log(`💻 System: ${systemInfo.platform} ${systemInfo.arch}`);
    console.log(`🧮 Memory: ${(systemInfo.totalMemory / 1024 / 1024 / 1024).toFixed(1)}GB`);
    console.log(`⚙️ CPUs: ${systemInfo.cpuCount}`);
  }

  async startProcessWithHealthChecks(command, args, options) {
    const processInfo = {
      command,
      args,
      startTime: new Date(),
      pid: null,
      status: 'STARTING',
      healthChecks: [],
      restartCount: 0
    };
    
    this.healthData.processHistory.push(processInfo);
    
    try {
      // Start the process
      const process = await this.launchProcess(command, args, options);
      this.currentProcess = process;
      processInfo.pid = process.pid;
      processInfo.status = 'RUNNING';
      
      console.log(`🚀 Process started with PID: ${process.pid}`);
      
      // Start health monitoring
      this.startHealthChecks(processInfo);
      
      // Monitor process events
      this.setupProcessEventHandlers(process, processInfo);
      
      return new Promise((resolve, reject) => {
        // Wait for initial startup completion
        const startupTimeout = setTimeout(() => {
          if (processInfo.status === 'RUNNING') {
            resolve({
              process,
              pid: process.pid,
              healthData: this.healthData
            });
          } else {
            reject(new Error('Process startup timeout'));
          }
        }, this.config.processTimeout);
        
        process.on('exit', (code) => {
          clearTimeout(startupTimeout);
          if (code === 0) {
            resolve({ process, pid: process.pid, healthData: this.healthData });
          } else {
            reject(new Error(`Process exited with code ${code}`));
          }
        });
        
        process.on('error', (error) => {
          clearTimeout(startupTimeout);
          reject(error);
        });
      });
      
    } catch (error) {
      processInfo.status = 'FAILED';
      processInfo.error = error.message;
      throw error;
    }
  }

  async launchProcess(command, args, options = {}) {
    const env = {
      ...process.env,
      ...options.env
    };
    
    const spawnOptions = {
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
      detached: false,
      ...options.spawnOptions
    };
    
    const childProcess = spawn(command, args, spawnOptions);
    
    // Capture output for analysis
    let stdout = '';
    let stderr = '';
    
    childProcess.stdout.on('data', (data) => {
      stdout += data.toString();
      this.analyzeOutput('stdout', data.toString());
    });
    
    childProcess.stderr.on('data', (data) => {
      stderr += data.toString();
      this.analyzeOutput('stderr', data.toString());
    });
    
    // Store output references
    childProcess.capturedOutput = { stdout, stderr };
    
    return childProcess;
  }

  setupProcessEventHandlers(process, processInfo) {
    process.on('exit', (code, signal) => {
      console.log(`💀 Process ${process.pid} exited with code ${code}, signal ${signal}`);
      processInfo.status = 'EXITED';
      processInfo.exitCode = code;
      processInfo.exitSignal = signal;
      processInfo.endTime = new Date();
      
      this.handleProcessExit(processInfo, code, signal);
    });
    
    process.on('error', (error) => {
      console.log(`❌ Process ${process.pid} error: ${error.message}`);
      processInfo.status = 'ERROR';
      processInfo.error = error.message;
      
      this.createAlert('CRITICAL', `Process error: ${error.message}`, {
        pid: process.pid,
        error: error.message
      });
    });
    
    process.on('disconnect', () => {
      console.log(`🔌 Process ${process.pid} disconnected`);
      processInfo.status = 'DISCONNECTED';
    });
  }

  startHealthChecks(processInfo) {
    this.healthTimer = setInterval(async () => {
      if (!this.isMonitoring || this.recoveryInProgress) return;
      
      try {
        const healthCheck = await this.performHealthCheck(processInfo);
        this.healthData.healthChecks.push(healthCheck);
        processInfo.healthChecks.push(healthCheck);
        
        // Evaluate health status
        await this.evaluateProcessHealth(healthCheck, processInfo);
        
      } catch (error) {
        console.warn(`⚠️ Health check failed: ${error.message}`);
        this.createAlert('WARNING', `Health check failed: ${error.message}`, {
          pid: processInfo.pid
        });
      }
    }, this.config.healthCheckInterval);
  }

  async performHealthCheck(processInfo) {
    const timestamp = Date.now();
    const healthCheck = {
      timestamp,
      time: new Date().toISOString(),
      pid: processInfo.pid,
      status: 'UNKNOWN'
    };
    
    try {
      // Get process stats
      const processStats = await this.getProcessStats(processInfo.pid);
      healthCheck.processStats = processStats;
      
      // Check if process is responsive
      const responseCheck = await this.checkProcessResponsiveness(processInfo.pid);
      healthCheck.responsive = responseCheck;
      
      // Get system resource usage
      const systemStats = await this.getSystemStats();
      healthCheck.systemStats = systemStats;
      
      // Calculate health score
      healthCheck.healthScore = this.calculateHealthScore(processStats, responseCheck, systemStats);
      
      // Determine overall status
      if (healthCheck.healthScore >= 80) {
        healthCheck.status = 'HEALTHY';
      } else if (healthCheck.healthScore >= 60) {
        healthCheck.status = 'WARNING';
      } else {
        healthCheck.status = 'UNHEALTHY';
      }
      
      // Real-time display
      this.displayHealthStatus(healthCheck);
      
    } catch (error) {
      healthCheck.status = 'ERROR';
      healthCheck.error = error.message;
    }
    
    return healthCheck;
  }

  async getProcessStats(pid) {
    return new Promise((resolve, reject) => {
      exec(`ps -p ${pid} -o pid,ppid,pcpu,pmem,vsz,rss,etime,state,comm --no-headers`, (error, stdout) => {
        if (error) {
          reject(new Error(`Process ${pid} not found or inaccessible`));
          return;
        }
        
        const parts = stdout.trim().split(/\s+/);
        if (parts.length >= 9) {
          resolve({
            pid: parseInt(parts[0]),
            ppid: parseInt(parts[1]),
            cpu: parseFloat(parts[2]),
            memory: parseFloat(parts[3]),
            vsz: parseInt(parts[4]),
            rss: parseInt(parts[5]),
            etime: parts[6],
            state: parts[7],
            command: parts[8]
          });
        } else {
          reject(new Error('Failed to parse process stats'));
        }
      });
    });
  }

  async checkProcessResponsiveness(pid) {
    // Simple responsiveness check by sending a signal
    try {
      process.kill(pid, 0); // Signal 0 just checks if process exists
      
      // Additional checks could include:
      // - HTTP endpoint health check for web servers
      // - File system activity monitoring
      // - Port listening verification
      
      return {
        responsive: true,
        responseTime: 0, // Could implement actual response time measurement
        lastResponse: new Date().toISOString()
      };
    } catch (error) {
      return {
        responsive: false,
        error: error.message
      };
    }
  }

  async getSystemStats() {
    return {
      totalMemory: os.totalmem(),
      freeMemory: os.freemem(),
      usedMemory: os.totalmem() - os.freemem(),
      memoryUsagePercent: ((os.totalmem() - os.freemem()) / os.totalmem()) * 100,
      loadAverage: os.loadavg(),
      uptime: os.uptime()
    };
  }

  calculateHealthScore(processStats, responseCheck, systemStats) {
    let score = 100;
    
    // CPU usage impact (0-30 points deduction)
    if (processStats.cpu > this.config.cpuThreshold) {
      score -= Math.min(30, (processStats.cpu - this.config.cpuThreshold) / 2);
    }
    
    // Memory usage impact (0-30 points deduction)
    const memoryMB = (processStats.rss * 1024) / 1024 / 1024; // Convert KB to MB
    if (memoryMB > this.config.memoryThreshold) {
      score -= Math.min(30, (memoryMB - this.config.memoryThreshold) / 100);
    }
    
    // Process state impact
    if (processStats.state === 'Z') { // Zombie process
      score -= 50;
    } else if (processStats.state === 'T') { // Stopped process
      score -= 40;
    } else if (processStats.state === 'D') { // Uninterruptible sleep
      score -= 20;
    }
    
    // Responsiveness impact (0-20 points deduction)
    if (!responseCheck.responsive) {
      score -= 20;
    }
    
    // System resource pressure (0-20 points deduction)
    if (systemStats.memoryUsagePercent > 90) {
      score -= 10;
    }
    if (systemStats.loadAverage[0] > os.cpus().length * 2) {
      score -= 10;
    }
    
    return Math.max(0, Math.round(score));
  }

  displayHealthStatus(healthCheck) {
    const statusIcon = {
      'HEALTHY': '✅',
      'WARNING': '⚠️',
      'UNHEALTHY': '🔴',
      'ERROR': '❌'
    };
    
    const cpuUsage = healthCheck.processStats ? healthCheck.processStats.cpu.toFixed(1) : 'N/A';
    const memoryUsage = healthCheck.processStats ? 
      ((healthCheck.processStats.rss * 1024) / 1024 / 1024).toFixed(1) : 'N/A';
    
    process.stdout.write(`\r${statusIcon[healthCheck.status]} Health: ${healthCheck.healthScore}/100 | CPU: ${cpuUsage}% | Memory: ${memoryUsage}MB | ${healthCheck.status}`);
  }

  async evaluateProcessHealth(healthCheck, processInfo) {
    // Trigger recovery actions based on health status
    if (healthCheck.status === 'UNHEALTHY' || healthCheck.healthScore < 30) {
      await this.triggerRecoveryAction('RESTART', processInfo, 'Process health critically low');
    } else if (healthCheck.status === 'WARNING' && healthCheck.healthScore < 50) {
      await this.triggerRecoveryAction('ALERT', processInfo, 'Process health degraded');
    }
    
    // Check for specific conditions
    if (healthCheck.processStats) {
      if (healthCheck.processStats.cpu > this.config.cpuThreshold * 1.5) {
        await this.triggerRecoveryAction('CPU_LIMIT', processInfo, 'High CPU usage detected');
      }
      
      const memoryMB = (healthCheck.processStats.rss * 1024) / 1024 / 1024;
      if (memoryMB > this.config.memoryThreshold * 1.2) {
        await this.triggerRecoveryAction('MEMORY_LIMIT', processInfo, 'High memory usage detected');
      }
    }
    
    if (!healthCheck.responsive) {
      await this.triggerRecoveryAction('UNRESPONSIVE', processInfo, 'Process not responding');
    }
  }

  async triggerRecoveryAction(actionType, processInfo, reason) {
    if (this.recoveryInProgress) return;
    
    const recoveryAction = {
      timestamp: Date.now(),
      time: new Date().toISOString(),
      type: actionType,
      reason,
      pid: processInfo.pid,
      processInfo: { ...processInfo }
    };
    
    this.healthData.recoveryActions.push(recoveryAction);
    
    console.log(`\n🔧 Recovery Action: ${actionType} - ${reason}`);
    
    switch (actionType) {
      case 'RESTART':
        if (this.config.autoRestart && processInfo.restartCount < this.config.recoveryAttempts) {
          await this.restartProcess(processInfo, recoveryAction);
        } else {
          this.createAlert('CRITICAL', `Process needs restart but auto-restart disabled or max attempts reached`, {
            pid: processInfo.pid,
            restartCount: processInfo.restartCount
          });
        }
        break;
        
      case 'ALERT':
        this.createAlert('WARNING', `Process health degraded: ${reason}`, {
          pid: processInfo.pid,
          healthScore: processInfo.healthChecks[processInfo.healthChecks.length - 1]?.healthScore
        });
        break;
        
      case 'CPU_LIMIT':
        await this.handleHighCpuUsage(processInfo, recoveryAction);
        break;
        
      case 'MEMORY_LIMIT':
        await this.handleHighMemoryUsage(processInfo, recoveryAction);
        break;
        
      case 'UNRESPONSIVE':
        await this.handleUnresponsiveProcess(processInfo, recoveryAction);
        break;
    }
  }

  async restartProcess(processInfo, recoveryAction) {
    this.recoveryInProgress = true;
    
    try {
      console.log(`🔄 Restarting process ${processInfo.pid} (attempt ${processInfo.restartCount + 1}/${this.config.recoveryAttempts})`);
      
      // Kill the current process
      if (this.currentProcess && !this.currentProcess.killed) {
        this.currentProcess.kill('SIGTERM');
        
        // Wait for graceful shutdown
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        if (!this.currentProcess.killed) {
          this.currentProcess.kill('SIGKILL');
        }
      }
      
      // Wait before restart
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Start new process
      const newProcess = await this.launchProcess(processInfo.command, processInfo.args);
      this.currentProcess = newProcess;
      
      // Update process info
      processInfo.restartCount++;
      processInfo.pid = newProcess.pid;
      processInfo.status = 'RESTARTED';
      processInfo.lastRestartTime = new Date();
      
      this.setupProcessEventHandlers(newProcess, processInfo);
      
      recoveryAction.success = true;
      recoveryAction.newPid = newProcess.pid;
      
      console.log(`✅ Process restarted successfully with PID: ${newProcess.pid}`);
      
    } catch (error) {
      recoveryAction.success = false;
      recoveryAction.error = error.message;
      
      this.createAlert('CRITICAL', `Process restart failed: ${error.message}`, {
        originalPid: processInfo.pid,
        restartAttempt: processInfo.restartCount + 1
      });
      
      console.log(`❌ Process restart failed: ${error.message}`);
    } finally {
      this.recoveryInProgress = false;
    }
  }

  async handleHighCpuUsage(processInfo, recoveryAction) {
    console.log(`⚡ Handling high CPU usage for process ${processInfo.pid}`);
    
    // Could implement CPU throttling or process nice adjustment
    try {
      // Lower process priority
      exec(`renice +10 ${processInfo.pid}`, (error) => {
        if (error) {
          recoveryAction.success = false;
          recoveryAction.error = error.message;
        } else {
          recoveryAction.success = true;
          recoveryAction.action = 'Process priority lowered';
          console.log(`📉 Process priority lowered for PID ${processInfo.pid}`);
        }
      });
    } catch (error) {
      recoveryAction.success = false;
      recoveryAction.error = error.message;
    }
  }

  async handleHighMemoryUsage(processInfo, recoveryAction) {
    console.log(`🧠 Handling high memory usage for process ${processInfo.pid}`);
    
    // Could implement memory cleanup or garbage collection trigger
    recoveryAction.action = 'Memory usage alert logged';
    recoveryAction.success = true;
    
    this.createAlert('WARNING', `High memory usage detected`, {
      pid: processInfo.pid,
      memoryUsage: processInfo.healthChecks[processInfo.healthChecks.length - 1]?.processStats?.rss
    });
  }

  async handleUnresponsiveProcess(processInfo, recoveryAction) {
    console.log(`📡 Handling unresponsive process ${processInfo.pid}`);
    
    try {
      // Send signal to check if process can respond
      process.kill(processInfo.pid, 'SIGUSR1');
      
      // Wait for response
      await new Promise(resolve => setTimeout(resolve, this.config.responseTimeout));
      
      // Check if process is still alive
      const isAlive = await this.checkProcessAlive(processInfo.pid);
      
      if (!isAlive) {
        recoveryAction.action = 'Process confirmed dead, will restart';
        await this.restartProcess(processInfo, recoveryAction);
      } else {
        recoveryAction.action = 'Process responsive after signal';
        recoveryAction.success = true;
      }
      
    } catch (error) {
      recoveryAction.success = false;
      recoveryAction.error = error.message;
    }
  }

  async checkProcessAlive(pid) {
    try {
      process.kill(pid, 0);
      return true;
    } catch {
      return false;
    }
  }

  analyzeOutput(source, output) {
    // Analyze output for known error patterns
    const errorPatterns = [
      /Error:/i,
      /Exception:/i,
      /Failed to/i,
      /Cannot find module/i,
      /EADDRINUSE/i,
      /ECONNREFUSED/i,
      /Out of memory/i,
      /Maximum call stack/i
    ];
    
    const warningPatterns = [
      /Warning:/i,
      /Deprecated/i,
      /npm WARN/i
    ];
    
    const successPatterns = [
      /compiled successfully/i,
      /webpack compiled/i,
      /Local:\s+http/i,
      /On Your Network:/i
    ];
    
    for (const pattern of errorPatterns) {
      if (pattern.test(output)) {
        this.createAlert('ERROR', `Error detected in ${source}`, {
          output: output.substring(0, 200),
          pattern: pattern.toString()
        });
        break;
      }
    }
    
    for (const pattern of warningPatterns) {
      if (pattern.test(output)) {
        this.createAlert('WARNING', `Warning detected in ${source}`, {
          output: output.substring(0, 200),
          pattern: pattern.toString()
        });
        break;
      }
    }
    
    for (const pattern of successPatterns) {
      if (pattern.test(output)) {
        console.log(`\n🎉 Success pattern detected: ${output.trim()}`);
        break;
      }
    }
  }

  handleProcessExit(processInfo, code, signal) {
    if (code !== 0 && this.config.autoRestart && processInfo.restartCount < this.config.recoveryAttempts) {
      console.log(`🔄 Process exited unexpectedly (code: ${code}), attempting restart...`);
      
      setTimeout(async () => {
        const recoveryAction = {
          timestamp: Date.now(),
          time: new Date().toISOString(),
          type: 'AUTO_RESTART',
          reason: `Process exited with code ${code}`,
          pid: processInfo.pid
        };
        
        await this.restartProcess(processInfo, recoveryAction);
      }, 2000);
    } else {
      this.createAlert('INFO', `Process exited`, {
        pid: processInfo.pid,
        code,
        signal,
        restartCount: processInfo.restartCount
      });
    }
  }

  createAlert(level, message, data = {}) {
    const alert = {
      timestamp: Date.now(),
      time: new Date().toISOString(),
      level,
      message,
      data
    };
    
    this.healthData.alerts.push(alert);
    
    const icon = {
      'CRITICAL': '🚨',
      'ERROR': '❌',
      'WARNING': '⚠️',
      'INFO': 'ℹ️'
    };
    
    console.log(`\n${icon[level]} [${level}] ${message}`);
  }

  generateSummary() {
    const duration = this.healthData.endTime - this.healthData.startTime;
    const totalHealthChecks = this.healthData.healthChecks.length;
    const healthyChecks = this.healthData.healthChecks.filter(c => c.status === 'HEALTHY').length;
    const recoveryActions = this.healthData.recoveryActions.length;
    const alerts = this.healthData.alerts;
    
    this.healthData.summary = {
      duration,
      totalHealthChecks,
      healthyChecks,
      healthyPercentage: totalHealthChecks > 0 ? (healthyChecks / totalHealthChecks) * 100 : 0,
      recoveryActions,
      alerts: {
        total: alerts.length,
        critical: alerts.filter(a => a.level === 'CRITICAL').length,
        errors: alerts.filter(a => a.level === 'ERROR').length,
        warnings: alerts.filter(a => a.level === 'WARNING').length
      },
      processStability: this.calculateProcessStability()
    };
  }

  calculateProcessStability() {
    const processes = this.healthData.processHistory;
    const totalRestarts = processes.reduce((sum, p) => sum + p.restartCount, 0);
    const totalCrashes = processes.filter(p => p.exitCode !== 0 && p.exitCode !== null).length;
    
    let stability = 100;
    stability -= totalRestarts * 20; // -20 points per restart
    stability -= totalCrashes * 30; // -30 points per crash
    stability -= this.healthData.recoveryActions.length * 5; // -5 points per recovery action
    
    return Math.max(0, stability);
  }

  async saveResults() {
    await fs.writeFile(this.config.outputFile, JSON.stringify(this.healthData, null, 2));
    console.log(`\n💾 Results saved to: ${this.config.outputFile}`);
  }

  async generateReport() {
    const reportPath = path.join(process.cwd(), 'tests', 'startup', 'process-health-report.md');
    const summary = this.healthData.summary;
    
    const report = `# Process Health Monitoring Report

Generated: ${new Date().toISOString()}
Duration: ${Math.round(summary.duration / 1000)}s
Total Health Checks: ${summary.totalHealthChecks}

## Health Summary

- **Healthy Checks**: ${summary.healthyChecks}/${summary.totalHealthChecks} (${summary.healthyPercentage.toFixed(1)}%)
- **Recovery Actions**: ${summary.recoveryActions}
- **Process Stability**: ${summary.processStability.toFixed(1)}/100

## Alert Summary

- **Total Alerts**: ${summary.alerts.total}
- **Critical**: ${summary.alerts.critical}
- **Errors**: ${summary.alerts.errors}
- **Warnings**: ${summary.alerts.warnings}

## Process History

${this.healthData.processHistory.map(p => `
### Process ${p.pid || 'Unknown'}
- **Command**: ${p.command} ${p.args.join(' ')}
- **Status**: ${p.status}
- **Restart Count**: ${p.restartCount}
- **Start Time**: ${p.startTime}
${p.endTime ? `- **End Time**: ${p.endTime}` : ''}
${p.exitCode !== undefined ? `- **Exit Code**: ${p.exitCode}` : ''}
`).join('')}

## Recovery Actions

${this.healthData.recoveryActions.map(r => `
### ${r.type} - ${new Date(r.timestamp).toLocaleString()}
- **Reason**: ${r.reason}
- **PID**: ${r.pid}
- **Success**: ${r.success !== undefined ? (r.success ? 'Yes' : 'No') : 'Unknown'}
${r.error ? `- **Error**: ${r.error}` : ''}
${r.action ? `- **Action**: ${r.action}` : ''}
`).join('')}

## Recommendations

${this.generateHealthRecommendations()}
`;

    await fs.writeFile(reportPath, report);
    console.log(`📋 Report saved to: ${reportPath}`);
  }

  generateHealthRecommendations() {
    const recommendations = [];
    const summary = this.healthData.summary;
    
    if (summary.processStability < 70) {
      recommendations.push('🔄 LOW STABILITY: Consider investigating root cause of frequent restarts and crashes');
    }
    
    if (summary.healthyPercentage < 80) {
      recommendations.push('⚠️ LOW HEALTH: Monitor resource usage and optimize process performance');
    }
    
    if (summary.alerts.critical > 0) {
      recommendations.push('🚨 CRITICAL ALERTS: Review critical alerts and implement fixes');
    }
    
    if (summary.recoveryActions > 5) {
      recommendations.push('🔧 HIGH RECOVERY: Frequent recovery actions indicate underlying issues');
    }
    
    const highCpuActions = this.healthData.recoveryActions.filter(r => r.type === 'CPU_LIMIT').length;
    if (highCpuActions > 0) {
      recommendations.push('⚡ CPU OPTIMIZATION: Consider optimizing code or increasing resources');
    }
    
    const memoryActions = this.healthData.recoveryActions.filter(r => r.type === 'MEMORY_LIMIT').length;
    if (memoryActions > 0) {
      recommendations.push('🧠 MEMORY OPTIMIZATION: Consider memory optimization or leak detection');
    }
    
    if (recommendations.length === 0) {
      recommendations.push('✅ Process health appears stable and well-managed');
    }
    
    return recommendations.map((r, i) => `${i + 1}. ${r}`).join('\n');
  }
}

// CLI Interface
if (require.main === module) {
  const monitor = new ProcessHealthMonitor();
  
  // Handle graceful shutdown
  process.on('SIGINT', async () => {
    console.log('\n🛑 Stopping process health monitoring...');
    await monitor.stopMonitoring();
    process.exit(0);
  });
  
  process.on('SIGTERM', async () => {
    await monitor.stopMonitoring();
    process.exit(0);
  });
  
  // Get command line arguments
  const args = process.argv.slice(2);
  const command = args[0] || 'npm';
  const commandArgs = args.slice(1) || ['start'];
  
  console.log(`🎯 Monitoring: ${command} ${commandArgs.join(' ')}`);
  
  // Start monitoring
  monitor.startMonitoring(command, commandArgs)
    .then(result => {
      console.log(`\n✅ Process monitoring started successfully`);
      console.log(`📊 PID: ${result.pid}`);
      console.log('Press Ctrl+C to stop monitoring');
      
      // Keep the process running
      setInterval(() => {
        // Keep alive
      }, 1000);
    })
    .catch(error => {
      console.error(`❌ Process health monitoring failed: ${error.message}`);
      process.exit(1);
    });
}

module.exports = ProcessHealthMonitor;