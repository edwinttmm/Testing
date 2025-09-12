#!/usr/bin/env node

/**
 * TypeScript Validation Monitor
 * Continuously validates TypeScript fixes and tracks progress
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class TypeScriptValidationMonitor {
  constructor() {
    this.baseline = null;
    this.validationHistory = [];
    this.memoryStorePath = path.join(__dirname, '..', 'memory', 'typescript-test-results.json');
    this.progressMemoryPath = path.join(__dirname, '..', 'memory', 'typescript-fixes-progress.json');
    
    // Ensure memory directory exists
    const memoryDir = path.dirname(this.memoryStorePath);
    if (!fs.existsSync(memoryDir)) {
      fs.mkdirSync(memoryDir, { recursive: true });
    }
  }

  async establishBaseline() {
    console.log('🔍 Establishing TypeScript baseline...');
    
    try {
      const result = execSync('npm run typecheck', { 
        encoding: 'utf8',
        cwd: process.cwd(),
        stdio: 'pipe'
      });
      
      this.baseline = {
        timestamp: new Date().toISOString(),
        errors: 0,
        output: result,
        status: 'success'
      };
      
      console.log('✅ Baseline: No TypeScript errors found');
      
    } catch (error) {
      const errorCount = this.countErrors(error.stdout || error.message);
      
      this.baseline = {
        timestamp: new Date().toISOString(),
        errors: errorCount,
        output: error.stdout || error.message,
        status: 'error'
      };
      
      console.log(`📊 Baseline: ${errorCount} TypeScript errors found`);
    }
    
    this.saveValidationResults();
    return this.baseline;
  }

  countErrors(output) {
    if (!output) return 0;
    
    // Count TypeScript error patterns
    const errorPatterns = [
      /error TS\d+:/gi,
      /Type '.*' is not assignable to type/gi,
      /Property '.*' does not exist/gi,
      /Cannot find module/gi,
      /has no exported member/gi
    ];
    
    let totalErrors = 0;
    errorPatterns.forEach(pattern => {
      const matches = output.match(pattern);
      if (matches) totalErrors += matches.length;
    });
    
    return totalErrors;
  }

  async runValidation() {
    console.log('🧪 Running TypeScript validation...');
    
    try {
      const result = execSync('npm run typecheck', { 
        encoding: 'utf8',
        cwd: process.cwd(),
        stdio: 'pipe'
      });
      
      const validation = {
        timestamp: new Date().toISOString(),
        errors: 0,
        output: result,
        status: 'success',
        improvement: this.baseline ? this.baseline.errors - 0 : 0
      };
      
      this.validationHistory.push(validation);
      console.log('✅ TypeScript validation passed - No errors!');
      
      return validation;
      
    } catch (error) {
      const errorCount = this.countErrors(error.stdout || error.message);
      
      const validation = {
        timestamp: new Date().toISOString(),
        errors: errorCount,
        output: error.stdout || error.message,
        status: 'error',
        improvement: this.baseline ? this.baseline.errors - errorCount : 0
      };
      
      this.validationHistory.push(validation);
      
      if (this.baseline && errorCount > this.baseline.errors) {
        console.log(`🚨 ALERT: Error count increased from ${this.baseline.errors} to ${errorCount}`);
        this.alertErrorIncrease(validation);
      } else if (validation.improvement > 0) {
        console.log(`📈 Progress: Fixed ${validation.improvement} errors (${errorCount} remaining)`);
      }
      
      return validation;
    }
  }

  alertErrorIncrease(validation) {
    console.log('🚨 TypeScript Error Increase Alert:');
    console.log(`Previous errors: ${this.baseline.errors}`);
    console.log(`Current errors: ${validation.errors}`);
    console.log(`Increase: +${validation.errors - this.baseline.errors}`);
    
    // Store alert in memory
    const alertData = {
      type: 'typescript-error-increase',
      timestamp: validation.timestamp,
      previousErrors: this.baseline.errors,
      currentErrors: validation.errors,
      increase: validation.errors - this.baseline.errors
    };
    
    this.saveToMemory('typescript-alerts', alertData);
  }

  async monitorProgressUpdates() {
    console.log('👀 Monitoring for typescript-fixes-progress updates...');
    
    // Check if progress file exists and has been updated
    if (fs.existsSync(this.progressMemoryPath)) {
      const stats = fs.statSync(this.progressMemoryPath);
      const lastModified = stats.mtime;
      
      // If file was modified recently (within last 30 seconds), run validation
      const thirtySecondsAgo = new Date(Date.now() - 30000);
      
      if (lastModified > thirtySecondsAgo) {
        console.log('📝 Progress update detected, running validation...');
        const validation = await this.runValidation();
        this.saveValidationResults();
        
        // Notify about progress
        execSync(`npx claude-flow@alpha hooks notify --message "TypeScript validation completed: ${validation.errors} errors"`, {
          stdio: 'inherit'
        });
        
        return validation;
      }
    }
    
    return null;
  }

  saveValidationResults() {
    const results = {
      baseline: this.baseline,
      latestValidation: this.validationHistory[this.validationHistory.length - 1] || null,
      history: this.validationHistory,
      summary: {
        totalValidations: this.validationHistory.length,
        currentErrors: this.validationHistory[this.validationHistory.length - 1]?.errors || this.baseline?.errors || 0,
        totalImprovement: this.baseline ? 
          this.baseline.errors - (this.validationHistory[this.validationHistory.length - 1]?.errors || this.baseline.errors) : 0,
        lastUpdated: new Date().toISOString()
      }
    };
    
    fs.writeFileSync(this.memoryStorePath, JSON.stringify(results, null, 2));
    console.log(`💾 Validation results saved to memory`);
  }

  saveToMemory(key, data) {
    const memoryFile = path.join(path.dirname(this.memoryStorePath), `${key}.json`);
    let existingData = {};
    
    if (fs.existsSync(memoryFile)) {
      existingData = JSON.parse(fs.readFileSync(memoryFile, 'utf8'));
    }
    
    existingData[new Date().toISOString()] = data;
    fs.writeFileSync(memoryFile, JSON.stringify(existingData, null, 2));
  }

  async startContinuousMonitoring() {
    console.log('🚀 Starting continuous TypeScript validation monitoring...');
    
    // Establish baseline
    await this.establishBaseline();
    
    // Monitor every 10 seconds
    setInterval(async () => {
      try {
        await this.monitorProgressUpdates();
      } catch (error) {
        console.error('❌ Error during monitoring:', error.message);
      }
    }, 10000);
    
    console.log('📊 Monitoring active - checking for updates every 10 seconds...');
  }

  getStatusReport() {
    const latest = this.validationHistory[this.validationHistory.length - 1];
    const current = latest || this.baseline;
    
    return {
      currentErrors: current?.errors || 0,
      totalImprovement: this.baseline ? this.baseline.errors - (current?.errors || 0) : 0,
      validationCount: this.validationHistory.length,
      lastValidation: current?.timestamp || 'Never',
      status: current?.status || 'unknown'
    };
  }
}

// CLI Interface
if (require.main === module) {
  const monitor = new TypeScriptValidationMonitor();
  
  const command = process.argv[2];
  
  switch (command) {
    case 'baseline':
      monitor.establishBaseline();
      break;
      
    case 'validate':
      monitor.runValidation().then(result => {
        monitor.saveValidationResults();
        console.log('Validation completed');
      });
      break;
      
    case 'monitor':
      monitor.startContinuousMonitoring();
      break;
      
    case 'status':
      const status = monitor.getStatusReport();
      console.log('📊 TypeScript Validation Status:');
      console.log(`Current Errors: ${status.currentErrors}`);
      console.log(`Total Improvement: ${status.totalImprovement}`);
      console.log(`Validations Run: ${status.validationCount}`);
      console.log(`Last Validation: ${status.lastValidation}`);
      console.log(`Status: ${status.status}`);
      break;
      
    default:
      console.log('Usage: node typescript-validation-monitor.js [baseline|validate|monitor|status]');
      break;
  }
}

module.exports = TypeScriptValidationMonitor;