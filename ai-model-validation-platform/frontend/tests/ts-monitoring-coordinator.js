#!/usr/bin/env node

/**
 * TypeScript Monitoring Coordinator
 * Real-time coordination system for TypeScript fix validation
 */

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');
const chokidar = require('fs').watchFile ? require('fs') : null;

class TSMonitoringCoordinator {
  constructor() {
    this.metricsPath = path.join(__dirname, 'ts-coordination-metrics.json');
    this.logPath = path.join(__dirname, 'ts-coordination.log');
    this.baseline = null;
    this.lastValidation = null;
    this.validationQueue = [];
    this.isValidating = false;
    this.agentFeedback = new Map();
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(this.logPath, logMessage + '\n');
  }

  async establishBaseline() {
    this.log('Establishing TypeScript baseline...', 'INFO');
    
    try {
      // Fast file count
      const fileStats = await this.getFileStatistics();
      
      // Quick lint check for warnings
      const lintResult = await this.runQuickLint();
      
      // Try a quick type check with shorter timeout
      const typeResult = await this.runFastTypeCheck();
      
      this.baseline = {
        timestamp: new Date().toISOString(),
        files: fileStats,
        typeCheck: typeResult,
        lint: lintResult,
        totalErrors: typeResult.errorCount,
        totalWarnings: lintResult.warningCount,
        buildAttempted: false
      };
      
      this.saveMetrics();
      
      this.log(`✅ Baseline established: ${fileStats.total} files, ${typeResult.errorCount} TS errors, ${lintResult.warningCount} lint warnings`, 'INFO');
      
      return this.baseline;
      
    } catch (error) {
      this.log(`❌ Failed to establish baseline: ${error.message}`, 'ERROR');
      throw error;
    }
  }

  async getFileStatistics() {
    const stats = { ts: 0, tsx: 0, total: 0, components: 0, services: 0, utils: 0 };
    const srcPath = path.join(process.cwd(), 'src');
    
    const countFiles = (dir, category = 'general') => {
      try {
        const files = fs.readdirSync(dir, { withFileTypes: true });
        
        for (const file of files) {
          const fullPath = path.join(dir, file.name);
          
          if (file.isDirectory() && !file.name.startsWith('.')) {
            let subCategory = category;
            if (file.name === 'components') subCategory = 'components';
            else if (file.name === 'services') subCategory = 'services';
            else if (file.name === 'utils') subCategory = 'utils';
            
            countFiles(fullPath, subCategory);
          } else if (file.isFile()) {
            if (file.name.endsWith('.ts')) {
              stats.ts++;
              stats.total++;
              if (category === 'components') stats.components++;
              else if (category === 'services') stats.services++;
              else if (category === 'utils') stats.utils++;
            } else if (file.name.endsWith('.tsx')) {
              stats.tsx++;
              stats.total++;
              if (category === 'components') stats.components++;
            }
          }
        }
      } catch (error) {
        // Skip inaccessible directories
      }
    };
    
    countFiles(srcPath);
    return stats;
  }

  async runFastTypeCheck() {
    try {
      const startTime = Date.now();
      
      // Use tsc with limited scope for faster checking
      const result = execSync(
        'npx tsc --noEmit --skipLibCheck --incremental false --tsBuildInfoFile /tmp/.tsbuildinfo.tmp', 
        { 
          encoding: 'utf8',
          timeout: 45000, // 45 second timeout
          cwd: process.cwd()
        }
      );
      
      return {
        success: true,
        errorCount: 0,
        errors: [],
        duration: Date.now() - startTime,
        output: result.slice(0, 1000) // Limit output size
      };
      
    } catch (error) {
      const duration = Date.now() - Date.now();
      const output = error.stdout || error.message || '';
      const errors = output.split('\n').filter(line => 
        line.includes('error TS') && line.trim() !== ''
      );
      
      return {
        success: false,
        errorCount: errors.length,
        errors: errors.slice(0, 20), // Limit to first 20 errors
        duration: duration,
        output: output.slice(0, 2000) // Limit output size
      };
    }
  }

  async runQuickLint() {
    try {
      const startTime = Date.now();
      
      const result = execSync('npm run lint:dev', { 
        encoding: 'utf8',
        timeout: 30000, // 30 second timeout
        cwd: process.cwd()
      });
      
      const warnings = result.split('\n').filter(line => 
        line.includes('warning') || line.includes('✖')
      );
      
      return {
        success: warnings.length === 0,
        warningCount: warnings.length,
        warnings: warnings.slice(0, 10), // First 10 warnings
        duration: Date.now() - startTime,
        output: result.slice(0, 1000)
      };
      
    } catch (error) {
      const output = error.stdout || error.message || '';
      const warnings = output.split('\n').filter(line => 
        line.includes('warning') || line.includes('✖')
      );
      
      return {
        success: false,
        warningCount: warnings.length,
        warnings: warnings.slice(0, 10),
        duration: Date.now() - Date.now(),
        output: output.slice(0, 1000)
      };
    }
  }

  async performValidation() {
    if (this.isValidating) {
      this.log('Validation already in progress, skipping...', 'WARN');
      return this.lastValidation;
    }
    
    this.isValidating = true;
    this.log('🔍 Starting TypeScript validation...', 'INFO');
    
    try {
      const fileStats = await this.getFileStatistics();
      const typeResult = await this.runFastTypeCheck();
      const lintResult = await this.runQuickLint();
      
      this.lastValidation = {
        timestamp: new Date().toISOString(),
        files: fileStats,
        typeCheck: typeResult,
        lint: lintResult,
        totalErrors: typeResult.errorCount,
        totalWarnings: lintResult.warningCount
      };
      
      this.saveMetrics();
      this.generateProgressReport();
      this.checkForRegressions();
      
      return this.lastValidation;
      
    } catch (error) {
      this.log(`❌ Validation failed: ${error.message}`, 'ERROR');
      throw error;
    } finally {
      this.isValidating = false;
    }
  }

  generateProgressReport() {
    if (!this.baseline || !this.lastValidation) {
      this.log('⚠️  Cannot generate progress report - missing baseline or validation data', 'WARN');
      return;
    }
    
    const errorChange = this.lastValidation.totalErrors - this.baseline.totalErrors;
    const warningChange = this.lastValidation.totalWarnings - this.baseline.totalWarnings;
    
    let report = '\n📊 === TypeScript Progress Report ===\n';
    report += `📁 Files: ${this.lastValidation.files.total} TypeScript files\n`;
    report += `🏁 Baseline: ${this.baseline.totalErrors} errors, ${this.baseline.totalWarnings} warnings\n`;
    report += `📍 Current:  ${this.lastValidation.totalErrors} errors, ${this.lastValidation.totalWarnings} warnings\n`;
    
    if (errorChange < 0) {
      report += `✅ Errors reduced by ${Math.abs(errorChange)}\n`;
    } else if (errorChange > 0) {
      report += `❌ Errors increased by ${errorChange}\n`;
    } else {
      report += `➖ No change in error count\n`;
    }
    
    if (warningChange < 0) {
      report += `✅ Warnings reduced by ${Math.abs(warningChange)}\n`;
    } else if (warningChange > 0) {
      report += `⚠️  Warnings increased by ${warningChange}\n`;
    } else {
      report += `➖ No change in warning count\n`;
    }
    
    // Performance metrics
    report += `⏱️  Type check: ${this.lastValidation.typeCheck.duration}ms\n`;
    report += `⏱️  Lint check: ${this.lastValidation.lint.duration}ms\n`;
    
    // Goal progress
    if (this.lastValidation.totalErrors === 0) {
      report += '\n🎉 ZERO TYPESCRIPT ERRORS ACHIEVED! 🎉\n';
    } else {
      const progress = Math.max(0, Math.round((1 - this.lastValidation.totalErrors / Math.max(this.baseline.totalErrors, 1)) * 100));
      report += `🎯 Progress toward zero errors: ${progress}%\n`;
    }
    
    report += '==========================================\n';
    
    this.log(report, 'REPORT');
  }

  checkForRegressions() {
    if (!this.baseline || !this.lastValidation) return;
    
    const regressions = [];
    
    // Error count regression
    if (this.lastValidation.totalErrors > this.baseline.totalErrors) {
      regressions.push({
        type: 'typescript-errors',
        severity: 'high',
        message: `TypeScript errors increased by ${this.lastValidation.totalErrors - this.baseline.totalErrors}`,
        before: this.baseline.totalErrors,
        after: this.lastValidation.totalErrors
      });
    }
    
    // Warning count significant increase
    if (this.lastValidation.totalWarnings > this.baseline.totalWarnings + 10) {
      regressions.push({
        type: 'lint-warnings',
        severity: 'medium',
        message: `Lint warnings increased significantly by ${this.lastValidation.totalWarnings - this.baseline.totalWarnings}`,
        before: this.baseline.totalWarnings,
        after: this.lastValidation.totalWarnings
      });
    }
    
    if (regressions.length > 0) {
      this.log('🚨 REGRESSIONS DETECTED:', 'ERROR');
      regressions.forEach(regression => {
        this.log(`  ${regression.severity.toUpperCase()}: ${regression.message}`, 'ERROR');
      });
    }
    
    return regressions;
  }

  provideAgentFeedback() {
    if (!this.lastValidation) {
      return {
        status: 'no-data',
        message: 'No validation data available. Run baseline first.',
        recommendation: 'Establish baseline metrics'
      };
    }
    
    const feedback = {
      timestamp: new Date().toISOString(),
      status: this.lastValidation.totalErrors === 0 ? 'success' : 'in-progress',
      metrics: {
        totalFiles: this.lastValidation.files.total,
        errorCount: this.lastValidation.totalErrors,
        warningCount: this.lastValidation.totalWarnings,
        typeCheckDuration: this.lastValidation.typeCheck.duration,
        lintDuration: this.lastValidation.lint.duration
      },
      progress: this.baseline ? {
        errorReduction: this.baseline.totalErrors - this.lastValidation.totalErrors,
        warningReduction: this.baseline.totalWarnings - this.lastValidation.totalWarnings,
        progressPercent: Math.round((1 - this.lastValidation.totalErrors / Math.max(this.baseline.totalErrors, 1)) * 100)
      } : null,
      regressions: this.checkForRegressions(),
      recommendation: this.getAgentRecommendation()
    };
    
    return feedback;
  }

  getAgentRecommendation() {
    if (!this.lastValidation) return 'Run initial validation';
    
    if (this.lastValidation.totalErrors === 0) {
      return 'Excellence achieved! Zero TypeScript errors. Focus on warning reduction and build optimization.';
    }
    
    if (this.lastValidation.totalErrors > 100) {
      return 'High error count detected. Prioritize critical type safety issues and any imports.';
    }
    
    if (this.lastValidation.totalErrors > 50) {
      return 'Moderate error count. Focus on component-level fixes and systematic type resolution.';
    }
    
    return 'Low error count. Continue with detailed fixes and edge case handling.';
  }

  saveMetrics() {
    const data = {
      baseline: this.baseline,
      lastValidation: this.lastValidation,
      agentFeedback: Object.fromEntries(this.agentFeedback),
      lastUpdated: new Date().toISOString()
    };
    
    fs.writeFileSync(this.metricsPath, JSON.stringify(data, null, 2));
  }

  loadMetrics() {
    try {
      if (fs.existsSync(this.metricsPath)) {
        const data = JSON.parse(fs.readFileSync(this.metricsPath, 'utf8'));
        this.baseline = data.baseline;
        this.lastValidation = data.lastValidation;
        this.agentFeedback = new Map(Object.entries(data.agentFeedback || {}));
      }
    } catch (error) {
      this.log(`Failed to load metrics: ${error.message}`, 'ERROR');
    }
  }

  async startContinuousMonitoring(intervalMs = 60000) {
    this.log('🚀 Starting continuous TypeScript monitoring...', 'INFO');
    
    // Load existing metrics
    this.loadMetrics();
    
    // Establish baseline if needed
    if (!this.baseline) {
      await this.establishBaseline();
    }
    
    // Start periodic validation
    const monitor = async () => {
      try {
        await this.performValidation();
      } catch (error) {
        this.log(`Monitoring cycle failed: ${error.message}`, 'ERROR');
      }
      
      setTimeout(monitor, intervalMs);
    };
    
    // Initial validation
    setTimeout(monitor, 5000); // Start after 5 seconds
    
    this.log(`✅ Continuous monitoring active (${intervalMs}ms intervals)`, 'INFO');
  }
}

// CLI interface
if (require.main === module) {
  const coordinator = new TSMonitoringCoordinator();
  const command = process.argv[2];
  
  switch (command) {
    case 'baseline':
      coordinator.establishBaseline();
      break;
    case 'validate':
      coordinator.loadMetrics();
      coordinator.performValidation();
      break;
    case 'monitor':
      const interval = parseInt(process.argv[3]) || 60000;
      coordinator.startContinuousMonitoring(interval);
      break;
    case 'feedback':
      coordinator.loadMetrics();
      console.log(JSON.stringify(coordinator.provideAgentFeedback(), null, 2));
      break;
    case 'report':
      coordinator.loadMetrics();
      coordinator.generateProgressReport();
      break;
    default:
      console.log('TypeScript Monitoring Coordinator');
      console.log('Usage: node ts-monitoring-coordinator.js [baseline|validate|monitor|feedback|report]');
      console.log('  baseline  - Establish initial metrics');
      console.log('  validate  - Run validation check');
      console.log('  monitor   - Start continuous monitoring');
      console.log('  feedback  - Get agent feedback JSON');
      console.log('  report    - Generate progress report');
      break;
  }
}

module.exports = TSMonitoringCoordinator;