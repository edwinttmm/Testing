#!/usr/bin/env node

/**
 * TypeScript Monitoring and Validation System
 * Continuously monitors TypeScript fixes and provides real-time feedback
 */

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

class TypeScriptMonitor {
  constructor() {
    this.metricsPath = path.join(__dirname, 'typescript-metrics.json');
    this.logPath = path.join(__dirname, 'typescript-monitoring.log');
    this.baselineMetrics = null;
    this.currentMetrics = null;
    this.monitoringActive = false;
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}\n`;
    
    console.log(logMessage.trim());
    fs.appendFileSync(this.logPath, logMessage);
  }

  async getTypeScriptErrors() {
    try {
      const result = execSync('npm run typecheck', { 
        encoding: 'utf8',
        cwd: process.cwd(),
        timeout: 120000 // 2 minutes timeout
      });
      
      return {
        success: true,
        errors: [],
        output: result,
        errorCount: 0
      };
    } catch (error) {
      const output = error.stdout || error.message;
      const errorLines = output.split('\n').filter(line => 
        line.includes('error TS') || line.includes('Error:')
      );
      
      return {
        success: false,
        errors: errorLines,
        output: output,
        errorCount: errorLines.length
      };
    }
  }

  async getBuildStatus() {
    try {
      const startTime = Date.now();
      const result = execSync('npm run build:dev', { 
        encoding: 'utf8',
        cwd: process.cwd(),
        timeout: 180000 // 3 minutes timeout
      });
      const buildTime = Date.now() - startTime;
      
      return {
        success: true,
        buildTime,
        output: result,
        warnings: this.extractWarnings(result)
      };
    } catch (error) {
      const buildTime = Date.now() - Date.now();
      const output = error.stdout || error.message;
      
      return {
        success: false,
        buildTime,
        output: output,
        errors: this.extractErrors(output),
        warnings: this.extractWarnings(output)
      };
    }
  }

  extractWarnings(output) {
    return output.split('\n').filter(line => 
      line.includes('warning') || line.includes('Warning')
    );
  }

  extractErrors(output) {
    return output.split('\n').filter(line => 
      line.includes('error') || line.includes('Error') || line.includes('Failed')
    );
  }

  async runBaseline() {
    this.log('Running baseline TypeScript analysis...', 'INFO');
    
    const typeScriptResult = await this.getTypeScriptErrors();
    const buildResult = await this.getBuildStatus();
    
    this.baselineMetrics = {
      timestamp: new Date().toISOString(),
      typeScript: typeScriptResult,
      build: buildResult,
      totalErrors: typeScriptResult.errorCount + (buildResult.errors?.length || 0),
      totalWarnings: buildResult.warnings?.length || 0
    };
    
    this.saveMetrics();
    
    this.log(`Baseline established: ${this.baselineMetrics.totalErrors} errors, ${this.baselineMetrics.totalWarnings} warnings`, 'INFO');
    
    return this.baselineMetrics;
  }

  async runValidation() {
    this.log('Running TypeScript validation...', 'INFO');
    
    const typeScriptResult = await this.getTypeScriptErrors();
    const buildResult = await this.getBuildStatus();
    
    this.currentMetrics = {
      timestamp: new Date().toISOString(),
      typeScript: typeScriptResult,
      build: buildResult,
      totalErrors: typeScriptResult.errorCount + (buildResult.errors?.length || 0),
      totalWarnings: buildResult.warnings?.length || 0
    };
    
    this.saveMetrics();
    
    const report = this.generateProgressReport();
    this.log(report, 'REPORT');
    
    return this.currentMetrics;
  }

  generateProgressReport() {
    if (!this.baselineMetrics || !this.currentMetrics) {
      return 'No baseline or current metrics available for comparison';
    }
    
    const errorChange = this.currentMetrics.totalErrors - this.baselineMetrics.totalErrors;
    const warningChange = this.currentMetrics.totalWarnings - this.baselineMetrics.totalWarnings;
    
    let report = '\n=== TypeScript Progress Report ===\n';
    report += `Baseline: ${this.baselineMetrics.totalErrors} errors, ${this.baselineMetrics.totalWarnings} warnings\n`;
    report += `Current:  ${this.currentMetrics.totalErrors} errors, ${this.currentMetrics.totalWarnings} warnings\n`;
    
    if (errorChange < 0) {
      report += `✅ Errors reduced by ${Math.abs(errorChange)}\n`;
    } else if (errorChange > 0) {
      report += `❌ Errors increased by ${errorChange}\n`;
    } else {
      report += `⏸️  No change in error count\n`;
    }
    
    if (warningChange < 0) {
      report += `✅ Warnings reduced by ${Math.abs(warningChange)}\n`;
    } else if (warningChange > 0) {
      report += `⚠️  Warnings increased by ${warningChange}\n`;
    } else {
      report += `⏸️  No change in warning count\n`;
    }
    
    const buildStatus = this.currentMetrics.build.success ? '✅ PASS' : '❌ FAIL';
    report += `Build Status: ${buildStatus}\n`;
    report += `Build Time: ${this.currentMetrics.build.buildTime}ms\n`;
    
    if (this.currentMetrics.totalErrors === 0) {
      report += '\n🎉 ZERO ERRORS ACHIEVED! 🎉\n';
    }
    
    report += '================================\n';
    
    return report;
  }

  detectRegressions() {
    if (!this.baselineMetrics || !this.currentMetrics) return [];
    
    const regressions = [];
    
    // Check for new TypeScript errors
    const newErrors = this.currentMetrics.typeScript.errors.filter(error => 
      !this.baselineMetrics.typeScript.errors.includes(error)
    );
    
    if (newErrors.length > 0) {
      regressions.push({
        type: 'typescript',
        description: 'New TypeScript errors introduced',
        errors: newErrors
      });
    }
    
    // Check for build failures
    if (this.baselineMetrics.build.success && !this.currentMetrics.build.success) {
      regressions.push({
        type: 'build',
        description: 'Build broke - was passing, now failing',
        errors: this.currentMetrics.build.errors
      });
    }
    
    return regressions;
  }

  saveMetrics() {
    const metrics = {
      baseline: this.baselineMetrics,
      current: this.currentMetrics,
      lastUpdated: new Date().toISOString()
    };
    
    fs.writeFileSync(this.metricsPath, JSON.stringify(metrics, null, 2));
  }

  loadMetrics() {
    try {
      if (fs.existsSync(this.metricsPath)) {
        const metrics = JSON.parse(fs.readFileSync(this.metricsPath, 'utf8'));
        this.baselineMetrics = metrics.baseline;
        this.currentMetrics = metrics.current;
      }
    } catch (error) {
      this.log(`Error loading metrics: ${error.message}`, 'ERROR');
    }
  }

  async startContinuousMonitoring(intervalMs = 30000) {
    this.log('Starting continuous TypeScript monitoring...', 'INFO');
    this.monitoringActive = true;
    
    // Initial baseline if not exists
    if (!this.baselineMetrics) {
      await this.runBaseline();
    }
    
    const monitor = async () => {
      if (!this.monitoringActive) return;
      
      try {
        await this.runValidation();
        
        const regressions = this.detectRegressions();
        if (regressions.length > 0) {
          this.log('🚨 REGRESSIONS DETECTED!', 'ERROR');
          regressions.forEach(regression => {
            this.log(`  ${regression.type}: ${regression.description}`, 'ERROR');
          });
        }
        
      } catch (error) {
        this.log(`Monitoring error: ${error.message}`, 'ERROR');
      }
      
      setTimeout(monitor, intervalMs);
    };
    
    monitor();
  }

  stopMonitoring() {
    this.monitoringActive = false;
    this.log('TypeScript monitoring stopped', 'INFO');
  }

  // Agent coordination methods
  provideAgentFeedback() {
    if (!this.currentMetrics) return null;
    
    return {
      errorCount: this.currentMetrics.totalErrors,
      warningCount: this.currentMetrics.totalWarnings,
      buildStatus: this.currentMetrics.build.success,
      buildTime: this.currentMetrics.build.buildTime,
      regressions: this.detectRegressions(),
      recommendation: this.getRecommendation()
    };
  }

  getRecommendation() {
    if (!this.currentMetrics) return 'Run initial validation';
    
    if (this.currentMetrics.totalErrors === 0) {
      return 'Excellent! Zero TypeScript errors achieved. Focus on reducing warnings.';
    }
    
    if (this.currentMetrics.totalErrors > 50) {
      return 'High error count. Focus on major type issues first.';
    }
    
    if (!this.currentMetrics.build.success) {
      return 'Build failing. Address build errors as priority.';
    }
    
    return 'Continue with systematic error reduction.';
  }
}

// CLI interface
if (require.main === module) {
  const monitor = new TypeScriptMonitor();
  const command = process.argv[2];
  
  switch (command) {
    case 'baseline':
      monitor.runBaseline();
      break;
    case 'validate':
      monitor.runValidation();
      break;
    case 'monitor':
      const interval = parseInt(process.argv[3]) || 30000;
      monitor.startContinuousMonitoring(interval);
      break;
    case 'status':
      monitor.loadMetrics();
      console.log(JSON.stringify(monitor.provideAgentFeedback(), null, 2));
      break;
    case 'report':
      monitor.loadMetrics();
      console.log(monitor.generateProgressReport());
      break;
    default:
      console.log('Usage: node typescript-monitor.js [baseline|validate|monitor|status|report]');
      break;
  }
}

module.exports = TypeScriptMonitor;