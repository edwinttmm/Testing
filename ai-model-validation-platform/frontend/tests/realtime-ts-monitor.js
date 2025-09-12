#!/usr/bin/env node

/**
 * Real-time TypeScript Monitoring System
 * Provides immediate feedback to agents working on TypeScript fixes
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class RealtimeTSMonitor {
  constructor() {
    this.monitoringActive = false;
    this.validationResults = [];
    this.alertThresholds = {
      errorIncrease: 5,
      warningIncrease: 15,
      buildTimeIncrease: 30000 // 30 seconds
    };
    this.logPath = path.join(__dirname, 'realtime-monitoring.log');
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(this.logPath, logMessage + '\n');
  }

  async quickValidation() {
    const startTime = Date.now();
    
    try {
      // Ultra-fast validation using tsc with minimal options
      const typeResult = await this.ultraFastTypeCheck();
      const fileCount = await this.getQuickFileCount();
      
      const result = {
        timestamp: new Date().toISOString(),
        fileCount: fileCount,
        typeCheck: typeResult,
        totalErrors: typeResult.errorCount,
        validationDuration: Date.now() - startTime,
        status: typeResult.success ? 'PASS' : 'FAIL'
      };
      
      this.validationResults.push(result);
      
      // Keep only last 50 results
      if (this.validationResults.length > 50) {
        this.validationResults = this.validationResults.slice(-50);
      }
      
      this.checkForAlerts(result);
      
      return result;
      
    } catch (error) {
      this.log(`Validation error: ${error.message}`, 'ERROR');
      return {
        timestamp: new Date().toISOString(),
        error: error.message,
        status: 'ERROR'
      };
    }
  }

  async ultraFastTypeCheck() {
    try {
      // Use incremental compilation for speed
      const result = execSync(
        'npx tsc --noEmit --skipLibCheck --incremental --pretty false', 
        { 
          encoding: 'utf8',
          timeout: 20000, // 20 second max
          cwd: process.cwd()
        }
      );
      
      return {
        success: true,
        errorCount: 0,
        errors: [],
        output: 'No errors found'
      };
      
    } catch (error) {
      const output = error.stdout || error.message || '';
      
      // Count unique error lines
      const errorLines = output.split('\n').filter(line => 
        line.match(/^[^(]*\(\d+,\d+\): error TS\d+:/) // Proper TS error format
      );
      
      return {
        success: false,
        errorCount: errorLines.length,
        errors: errorLines.slice(0, 5), // First 5 errors for quick feedback
        output: output.slice(0, 500) // Truncate for performance
      };
    }
  }

  async getQuickFileCount() {
    try {
      const result = execSync("find src -name '*.ts' -o -name '*.tsx' | wc -l", { 
        encoding: 'utf8',
        timeout: 5000
      });
      return parseInt(result.trim());
    } catch (error) {
      return 0;
    }
  }

  checkForAlerts(result) {
    const lastResult = this.validationResults[this.validationResults.length - 2];
    
    if (!lastResult) return;
    
    // Check for error increase
    if (result.totalErrors > lastResult.totalErrors + this.alertThresholds.errorIncrease) {
      this.log(`🚨 ALERT: TypeScript errors increased by ${result.totalErrors - lastResult.totalErrors}!`, 'ALERT');
      this.notifyAgents('error-spike', {
        increase: result.totalErrors - lastResult.totalErrors,
        total: result.totalErrors
      });
    }
    
    // Check for performance regression
    if (result.validationDuration > lastResult.validationDuration + this.alertThresholds.buildTimeIncrease) {
      this.log(`⏰ ALERT: Validation time increased significantly!`, 'ALERT');
      this.notifyAgents('performance-regression', {
        oldTime: lastResult.validationDuration,
        newTime: result.validationDuration
      });
    }
    
    // Check for major improvement
    if (lastResult.totalErrors > 0 && result.totalErrors === 0) {
      this.log(`🎉 CELEBRATION: Zero TypeScript errors achieved!`, 'SUCCESS');
      this.notifyAgents('zero-errors-achieved', {
        previousErrors: lastResult.totalErrors
      });
    }
  }

  notifyAgents(eventType, data) {
    const notification = {
      timestamp: new Date().toISOString(),
      event: eventType,
      data: data,
      recommendation: this.getEventRecommendation(eventType, data)
    };
    
    // Save notification for agents to read
    const notificationPath = path.join(__dirname, 'agent-notifications.json');
    let notifications = [];
    
    try {
      if (fs.existsSync(notificationPath)) {
        notifications = JSON.parse(fs.readFileSync(notificationPath, 'utf8'));
      }
    } catch (error) {
      // Start fresh if file is corrupted
    }
    
    notifications.push(notification);
    
    // Keep only last 20 notifications
    if (notifications.length > 20) {
      notifications = notifications.slice(-20);
    }
    
    fs.writeFileSync(notificationPath, JSON.stringify(notifications, null, 2));
    
    this.log(`📢 Agent notification sent: ${eventType}`, 'INFO');
  }

  getEventRecommendation(eventType, data) {
    switch (eventType) {
      case 'error-spike':
        return 'STOP: Review recent changes. Potential regression introduced. Revert if necessary.';
      case 'performance-regression':
        return 'Performance degraded. Check for complex type operations or circular dependencies.';
      case 'zero-errors-achieved':
        return 'SUCCESS! Shift focus to warning reduction and build optimization.';
      default:
        return 'Continue monitoring and validation.';
    }
  }

  getCurrentStatus() {
    const latestResult = this.validationResults[this.validationResults.length - 1];
    
    if (!latestResult) {
      return {
        status: 'no-data',
        message: 'No validation data available'
      };
    }
    
    return {
      status: latestResult.status,
      timestamp: latestResult.timestamp,
      errorCount: latestResult.totalErrors,
      fileCount: latestResult.fileCount,
      lastValidationDuration: latestResult.validationDuration,
      trend: this.calculateTrend(),
      recommendation: this.getRecommendation(latestResult)
    };
  }

  calculateTrend() {
    if (this.validationResults.length < 3) return 'insufficient-data';
    
    const recent = this.validationResults.slice(-3);
    const errorCounts = recent.map(r => r.totalErrors);
    
    if (errorCounts[2] < errorCounts[1] && errorCounts[1] < errorCounts[0]) {
      return 'improving';
    } else if (errorCounts[2] > errorCounts[1] && errorCounts[1] > errorCounts[0]) {
      return 'degrading';
    } else {
      return 'stable';
    }
  }

  getRecommendation(result) {
    if (result.totalErrors === 0) {
      return 'Perfect! Zero errors. Focus on warnings and performance.';
    }
    
    if (result.totalErrors > 50) {
      return 'High error count. Focus on major type issues and imports.';
    }
    
    if (result.totalErrors > 20) {
      return 'Moderate errors. Continue systematic fixes.';
    }
    
    return 'Low error count. Detailed type refinement needed.';
  }

  async startRealtimeMonitoring(intervalMs = 15000) {
    this.log('🔄 Starting real-time TypeScript monitoring...', 'INFO');
    this.monitoringActive = true;
    
    const monitor = async () => {
      if (!this.monitoringActive) return;
      
      try {
        await this.quickValidation();
        setTimeout(monitor, intervalMs);
      } catch (error) {
        this.log(`Monitoring error: ${error.message}`, 'ERROR');
        setTimeout(monitor, intervalMs * 2); // Back off on error
      }
    };
    
    // Start monitoring
    monitor();
  }

  stopMonitoring() {
    this.monitoringActive = false;
    this.log('⏹️  Real-time monitoring stopped', 'INFO');
  }

  getValidationHistory() {
    return {
      totalValidations: this.validationResults.length,
      results: this.validationResults.slice(-10), // Last 10 results
      trend: this.calculateTrend(),
      averageValidationTime: this.calculateAverageValidationTime()
    };
  }

  calculateAverageValidationTime() {
    if (this.validationResults.length === 0) return 0;
    
    const times = this.validationResults
      .filter(r => r.validationDuration)
      .map(r => r.validationDuration);
    
    return times.length > 0 ? Math.round(times.reduce((a, b) => a + b, 0) / times.length) : 0;
  }
}

// CLI interface
if (require.main === module) {
  const monitor = new RealtimeTSMonitor();
  const command = process.argv[2];
  
  switch (command) {
    case 'start':
      const interval = parseInt(process.argv[3]) || 15000;
      monitor.startRealtimeMonitoring(interval);
      break;
    case 'validate':
      monitor.quickValidation();
      break;
    case 'status':
      console.log(JSON.stringify(monitor.getCurrentStatus(), null, 2));
      break;
    case 'history':
      console.log(JSON.stringify(monitor.getValidationHistory(), null, 2));
      break;
    case 'stop':
      monitor.stopMonitoring();
      break;
    default:
      console.log('Real-time TypeScript Monitor');
      console.log('Usage: node realtime-ts-monitor.js [start|validate|status|history|stop]');
      console.log('  start [interval]  - Start monitoring (default: 15s)');
      console.log('  validate         - Run single validation');
      console.log('  status          - Get current status');
      console.log('  history         - Get validation history');
      console.log('  stop            - Stop monitoring');
      break;
  }
}

module.exports = RealtimeTSMonitor;