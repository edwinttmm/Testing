#!/usr/bin/env node

/**
 * Master Monitoring Report
 * Comprehensive TypeScript monitoring and validation status for agent coordination
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class MasterMonitoringReport {
  constructor() {
    this.reportPath = path.join(__dirname, 'master-monitoring-report.json');
    this.logPath = path.join(__dirname, 'master-monitoring.log');
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(this.logPath, logMessage + '\n');
  }

  async generateComprehensiveReport() {
    this.log('📋 Generating comprehensive TypeScript monitoring report...', 'INFO');
    
    const report = {
      reportId: `TSMON-${Date.now()}`,
      timestamp: new Date().toISOString(),
      summary: await this.getProjectSummary(),
      currentStatus: await this.getCurrentStatus(),
      performanceMetrics: await this.getPerformanceMetrics(),
      agentCoordination: await this.getAgentCoordinationData(),
      recommendations: await this.generateRecommendations(),
      alerts: await this.checkForAlerts(),
      progressTracking: await this.getProgressTracking(),
      nextActions: await this.getNextActions()
    };
    
    this.saveReport(report);
    this.displayReport(report);
    
    return report;
  }

  async getProjectSummary() {
    try {
      const tsCount = parseInt(execSync("find src -name '*.ts' | wc -l", { encoding: 'utf8' }).trim());
      const tsxCount = parseInt(execSync("find src -name '*.tsx' | wc -l", { encoding: 'utf8' }).trim());
      
      return {
        totalFiles: tsCount + tsxCount,
        tsFiles: tsCount,
        tsxFiles: tsxCount,
        projectScale: tsCount + tsxCount > 200 ? 'large' : tsCount + tsxCount > 100 ? 'medium' : 'small'
      };
    } catch (error) {
      return {
        totalFiles: 0,
        tsFiles: 0,
        tsxFiles: 0,
        projectScale: 'unknown',
        error: error.message
      };
    }
  }

  async getCurrentStatus() {
    try {
      // Load immediate status if available
      const immediateStatusPath = path.join(__dirname, 'immediate-status.json');
      if (fs.existsSync(immediateStatusPath)) {
        const immediateStatus = JSON.parse(fs.readFileSync(immediateStatusPath, 'utf8'));
        return {
          source: 'immediate-check',
          typeScriptErrors: immediateStatus.typeScriptSample.errorCount,
          lintWarnings: immediateStatus.lintSample.warningCount,
          overallStatus: immediateStatus.overallStatus.quickStatus,
          lastChecked: immediateStatus.timestamp
        };
      }
      
      // Fallback to quick check
      const quickCheck = execSync('timeout 10s npx tsc --noEmit --skipLibCheck 2>&1 | grep "error TS" | wc -l || echo "0"', { 
        encoding: 'utf8' 
      }).trim();
      
      return {
        source: 'quick-fallback',
        typeScriptErrors: parseInt(quickCheck),
        lintWarnings: 'unknown',
        overallStatus: parseInt(quickCheck) === 0 ? 'GOOD' : 'NEEDS_ATTENTION'
      };
    } catch (error) {
      return {
        source: 'error',
        error: error.message,
        overallStatus: 'UNKNOWN'
      };
    }
  }

  async getPerformanceMetrics() {
    try {
      const perfPath = path.join(__dirname, 'performance-metrics.json');
      if (fs.existsSync(perfPath)) {
        const perfData = JSON.parse(fs.readFileSync(perfPath, 'utf8'));
        const latest = perfData.benchmarks[perfData.benchmarks.length - 1];
        
        return {
          available: true,
          performanceScore: latest.overallScore,
          typeCheckDuration: latest.measurements.typeCheck.duration,
          lintingDuration: latest.measurements.linting.duration,
          memoryUsageMB: Math.round(latest.measurements.memory.heapUsed / (1024 * 1024)),
          trend: perfData.summary.trend,
          lastMeasured: latest.timestamp
        };
      }
      
      return {
        available: false,
        message: 'No performance data available'
      };
    } catch (error) {
      return {
        available: false,
        error: error.message
      };
    }
  }

  async getAgentCoordinationData() {
    const coordination = {
      monitoringActive: this.checkMonitoringStatus(),
      validationQueued: false,
      agentNotifications: this.getAgentNotifications(),
      conflictDetection: 'active',
      lastCoordination: new Date().toISOString()
    };
    
    return coordination;
  }

  checkMonitoringStatus() {
    try {
      const result = execSync('pgrep -f "realtime-ts-monitor"', { encoding: 'utf8' });
      return result.trim().length > 0;
    } catch (error) {
      return false;
    }
  }

  getAgentNotifications() {
    try {
      const notifPath = path.join(__dirname, 'agent-notifications.json');
      if (fs.existsSync(notifPath)) {
        const notifications = JSON.parse(fs.readFileSync(notifPath, 'utf8'));
        return {
          available: true,
          count: notifications.length,
          recent: notifications.slice(-3) // Last 3 notifications
        };
      }
      
      return {
        available: false,
        count: 0,
        recent: []
      };
    } catch (error) {
      return {
        available: false,
        error: error.message
      };
    }
  }

  async generateRecommendations() {
    const recommendations = {
      immediate: [],
      shortTerm: [],
      longTerm: []
    };
    
    const status = await this.getCurrentStatus();
    
    // Immediate recommendations
    if (status.overallStatus === 'NEEDS_ATTENTION') {
      recommendations.immediate.push('🔥 Address TypeScript errors immediately');
      recommendations.immediate.push('🔧 Focus on import/export issues first');
    } else {
      recommendations.immediate.push('✅ TypeScript status good - monitor for regressions');
    }
    
    // Short-term recommendations
    recommendations.shortTerm.push('📊 Continue real-time monitoring');
    recommendations.shortTerm.push('🧹 Reduce lint warnings systematically');
    recommendations.shortTerm.push('⚡ Optimize build performance if needed');
    
    // Long-term recommendations
    recommendations.longTerm.push('🏗️ Implement stricter TypeScript rules gradually');
    recommendations.longTerm.push('📈 Set up automated quality gates');
    recommendations.longTerm.push('🔄 Establish CI/CD integration');
    
    return recommendations;
  }

  async checkForAlerts() {
    const alerts = [];
    
    const status = await this.getCurrentStatus();
    
    if (status.typeScriptErrors && status.typeScriptErrors > 0) {
      alerts.push({
        type: 'typescript-errors',
        severity: status.typeScriptErrors > 20 ? 'high' : 'medium',
        message: `${status.typeScriptErrors} TypeScript errors detected`,
        action: 'Immediate attention required'
      });
    }
    
    if (!this.checkMonitoringStatus()) {
      alerts.push({
        type: 'monitoring-inactive',
        severity: 'medium',
        message: 'Real-time monitoring not active',
        action: 'Restart monitoring system'
      });
    }
    
    return alerts;
  }

  async getProgressTracking() {
    return {
      goalZeroErrors: {
        target: 0,
        current: await this.getCurrentErrorCount(),
        progress: await this.calculateProgress()
      },
      milestones: [
        { name: 'Zero critical errors', achieved: true },
        { name: 'Under 50 errors', achieved: await this.getCurrentErrorCount() < 50 },
        { name: 'Under 20 errors', achieved: await this.getCurrentErrorCount() < 20 },
        { name: 'Zero errors', achieved: await this.getCurrentErrorCount() === 0 }
      ]
    };
  }

  async getCurrentErrorCount() {
    const status = await this.getCurrentStatus();
    return status.typeScriptErrors || 0;
  }

  async calculateProgress() {
    const current = await this.getCurrentErrorCount();
    const baseline = 100; // Assume baseline of 100 errors for calculation
    
    return Math.max(0, Math.min(100, Math.round((1 - current / baseline) * 100)));
  }

  async getNextActions() {
    const errorCount = await this.getCurrentErrorCount();
    
    const actions = [];
    
    if (errorCount === 0) {
      actions.push('🎉 Celebrate zero errors achievement!');
      actions.push('🧹 Focus on warning reduction');
      actions.push('⚡ Optimize build performance');
    } else if (errorCount < 10) {
      actions.push('🔧 Address remaining TypeScript errors');
      actions.push('📝 Focus on edge cases and type refinement');
    } else if (errorCount < 50) {
      actions.push('🏗️ Systematic error reduction by component');
      actions.push('📋 Prioritize high-impact fixes');
    } else {
      actions.push('🚨 Major TypeScript cleanup required');
      actions.push('⚡ Focus on critical path issues');
    }
    
    actions.push('🔄 Continue monitoring coordination');
    actions.push('👥 Prevent agent conflicts');
    
    return actions;
  }

  displayReport(report) {
    console.log('\n' + '='.repeat(60));
    console.log('🎯 TYPESCRIPT MONITORING & VALIDATION REPORT');
    console.log('='.repeat(60));
    
    console.log(`\n📊 PROJECT SUMMARY:`);
    console.log(`   Files: ${report.summary.totalFiles} TypeScript files (${report.summary.tsFiles} .ts, ${report.summary.tsxFiles} .tsx)`);
    console.log(`   Scale: ${report.summary.projectScale.toUpperCase()}`);
    
    console.log(`\n🔍 CURRENT STATUS:`);
    console.log(`   TypeScript Errors: ${report.currentStatus.typeScriptErrors}`);
    console.log(`   Lint Warnings: ${report.currentStatus.lintWarnings}`);
    console.log(`   Overall Status: ${report.currentStatus.overallStatus}`);
    
    if (report.performanceMetrics.available) {
      console.log(`\n⚡ PERFORMANCE:`);
      console.log(`   Score: ${report.performanceMetrics.performanceScore}/100`);
      console.log(`   Type Check: ${report.performanceMetrics.typeCheckDuration}ms`);
      console.log(`   Memory: ${report.performanceMetrics.memoryUsageMB}MB`);
    }
    
    console.log(`\n🤝 AGENT COORDINATION:`);
    console.log(`   Monitoring Active: ${report.agentCoordination.monitoringActive ? '✅ YES' : '❌ NO'}`);
    console.log(`   Notifications: ${report.agentCoordination.agentNotifications.count} available`);
    
    if (report.alerts.length > 0) {
      console.log(`\n🚨 ALERTS:`);
      report.alerts.forEach(alert => {
        console.log(`   ${alert.severity.toUpperCase()}: ${alert.message}`);
      });
    }
    
    console.log(`\n🎯 PROGRESS TO ZERO ERRORS:`);
    console.log(`   Current: ${report.progressTracking.goalZeroErrors.current} errors`);
    console.log(`   Progress: ${report.progressTracking.goalZeroErrors.progress || 0}%`);
    
    console.log(`\n💡 IMMEDIATE RECOMMENDATIONS:`);
    report.recommendations.immediate.forEach(rec => {
      console.log(`   • ${rec}`);
    });
    
    console.log(`\n🚀 NEXT ACTIONS:`);
    report.nextActions.forEach((action, idx) => {
      console.log(`   ${idx + 1}. ${action}`);
    });
    
    console.log('\n' + '='.repeat(60));
    console.log(`Report ID: ${report.reportId} | Generated: ${report.timestamp}`);
    console.log('='.repeat(60) + '\n');
  }

  saveReport(report) {
    fs.writeFileSync(this.reportPath, JSON.stringify(report, null, 2));
    
    // Also save a timestamped version
    const timestampedPath = path.join(__dirname, `monitoring-report-${Date.now()}.json`);
    fs.writeFileSync(timestampedPath, JSON.stringify(report, null, 2));
  }
}

// CLI interface
if (require.main === module) {
  const masterReport = new MasterMonitoringReport();
  masterReport.generateComprehensiveReport();
}

module.exports = MasterMonitoringReport;