#!/usr/bin/env node

/**
 * TypeScript Monitoring Dashboard
 * Central dashboard for all TypeScript fix monitoring and agent coordination
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const TypeScriptMonitor = require('./typescript-monitor');
const PerformanceMonitor = require('./performance-monitor');
const AgentCoordinationSystem = require('./agent-coordination-system');
const ComponentFunctionalityValidator = require('./component-functionality-validator');

class MonitoringDashboard {
  constructor() {
    this.dashboardPath = path.join(__dirname, 'monitoring-dashboard.json');
    this.logPath = path.join(__dirname, 'monitoring-dashboard.log');
    
    // Initialize all monitoring systems
    this.tsMonitor = new TypeScriptMonitor();
    this.perfMonitor = new PerformanceMonitor();
    this.coordinator = new AgentCoordinationSystem();
    this.funcValidator = new ComponentFunctionalityValidator();
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(this.logPath, logMessage + '\n');
  }

  async generateDashboard() {
    this.log('📊 Generating comprehensive monitoring dashboard...', 'INFO');
    
    // Load all monitoring data
    this.tsMonitor.loadMetrics();
    this.perfMonitor.loadBenchmarks();
    this.coordinator.loadCoordinationState();
    this.funcValidator.loadResults();
    
    const dashboard = {
      dashboardId: `DASH-${Date.now()}`,
      timestamp: new Date().toISOString(),
      systemHealth: await this.assessSystemHealth(),
      typeScriptStatus: this.tsMonitor.provideAgentFeedback(),
      performanceMetrics: this.perfMonitor.getAgentPerformanceFeedback(),
      agentCoordination: this.coordinator.provideFeedbackToAgents(),
      componentFunctionality: this.funcValidator.getAgentFunctionalityFeedback(),
      overallAssessment: null,
      agentRecommendations: null,
      criticalAlerts: null
    };
    
    dashboard.overallAssessment = this.calculateOverallAssessment(dashboard);
    dashboard.agentRecommendations = this.generateAgentRecommendations(dashboard);
    dashboard.criticalAlerts = this.checkCriticalAlerts(dashboard);
    
    this.saveDashboard(dashboard);
    this.displayDashboard(dashboard);
    
    return dashboard;
  }

  async assessSystemHealth() {
    const health = {
      monitoring: this.checkMonitoringProcesses(),
      fileSystem: this.checkFileSystemHealth(),
      buildSystem: await this.checkBuildSystemHealth(),
      overallHealth: 'pending'
    };
    
    // Calculate overall health
    const healthChecks = [
      health.monitoring.active,
      health.fileSystem.accessible,
      health.buildSystem.operational
    ];
    
    const passingChecks = healthChecks.filter(check => check).length;
    
    if (passingChecks === 3) health.overallHealth = 'excellent';
    else if (passingChecks === 2) health.overallHealth = 'good';
    else if (passingChecks === 1) health.overallHealth = 'poor';
    else health.overallHealth = 'critical';
    
    return health;
  }

  checkMonitoringProcesses() {
    try {
      const processes = execSync('pgrep -f "ts-monitor\\|realtime.*monitor"', { encoding: 'utf8' });
      return {
        active: processes.trim().length > 0,
        processCount: processes.trim().split('\n').filter(p => p.trim()).length
      };
    } catch (error) {
      return {
        active: false,
        processCount: 0
      };
    }
  }

  checkFileSystemHealth() {
    try {
      const srcExists = fs.existsSync('src');
      const testsExists = fs.existsSync('tests');
      const nodeModulesExists = fs.existsSync('node_modules');
      
      return {
        accessible: srcExists && testsExists,
        srcDirectory: srcExists,
        testsDirectory: testsExists,
        dependencies: nodeModulesExists
      };
    } catch (error) {
      return {
        accessible: false,
        error: error.message
      };
    }
  }

  async checkBuildSystemHealth() {
    try {
      // Quick package.json validation
      const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
      const hasRequiredScripts = ['build', 'typecheck', 'lint'].every(script => 
        packageJson.scripts && packageJson.scripts[script]
      );
      
      return {
        operational: hasRequiredScripts,
        scriptsAvailable: hasRequiredScripts,
        dependencies: Object.keys(packageJson.dependencies || {}).length,
        devDependencies: Object.keys(packageJson.devDependencies || {}).length
      };
    } catch (error) {
      return {
        operational: false,
        error: error.message
      };
    }
  }

  calculateOverallAssessment(dashboard) {
    const assessments = [];
    
    // TypeScript assessment
    if (dashboard.typeScriptStatus && dashboard.typeScriptStatus.status !== 'no-data') {
      if (dashboard.typeScriptStatus.errorCount === 0) {
        assessments.push('🎉 Zero TypeScript errors achieved!');
      } else if (dashboard.typeScriptStatus.errorCount < 10) {
        assessments.push('🔧 Low error count - nearing completion');
      } else {
        assessments.push('⚠️ TypeScript errors need attention');
      }
    }
    
    // Performance assessment
    if (dashboard.performanceMetrics && dashboard.performanceMetrics.performanceScore) {
      if (dashboard.performanceMetrics.performanceScore >= 80) {
        assessments.push('⚡ Excellent build performance');
      } else if (dashboard.performanceMetrics.performanceScore >= 60) {
        assessments.push('📈 Good build performance');
      } else {
        assessments.push('🐌 Build performance needs optimization');
      }
    }
    
    // Coordination assessment
    if (dashboard.agentCoordination.coordinationHealth === 'excellent') {
      assessments.push('🤝 Perfect agent coordination');
    } else {
      assessments.push('👥 Agent coordination working');
    }
    
    return {
      summary: assessments.join(' | '),
      status: assessments.length > 0 ? 'operational' : 'needs-attention',
      keyMetrics: {
        tsErrors: dashboard.typeScriptStatus?.errorCount || 'unknown',
        perfScore: dashboard.performanceMetrics?.performanceScore || 'unknown',
        agentHealth: dashboard.agentCoordination?.coordinationHealth || 'unknown'
      }
    };
  }

  generateAgentRecommendations(dashboard) {
    const recommendations = {
      immediate: [],
      coordination: [],
      performance: []
    };
    
    // Immediate actions based on current state
    if (dashboard.typeScriptStatus?.errorCount === 0) {
      recommendations.immediate.push('🎯 Shift focus to warning reduction');
      recommendations.immediate.push('🧹 Clean up lint warnings');
    } else if (dashboard.typeScriptStatus?.errorCount > 0) {
      recommendations.immediate.push('🔥 Continue TypeScript error fixes');
      recommendations.immediate.push('📋 Prioritize import/type definition issues');
    }
    
    // Coordination recommendations
    if (dashboard.agentCoordination.fileConflicts > 0) {
      recommendations.coordination.push('⚠️ Resolve file access conflicts');
      recommendations.coordination.push('📝 Coordinate file access with other agents');
    } else {
      recommendations.coordination.push('✅ No conflicts - continue collaborative work');
    }
    
    // Performance recommendations
    if (dashboard.performanceMetrics?.performanceScore < 70) {
      recommendations.performance.push('⚡ Optimize TypeScript compilation');
      recommendations.performance.push('💾 Monitor memory usage');
    }
    
    return recommendations;
  }

  checkCriticalAlerts(dashboard) {
    const alerts = [];
    
    // Critical TypeScript errors
    if (dashboard.typeScriptStatus?.errorCount > 100) {
      alerts.push({
        type: 'critical-errors',
        severity: 'HIGH',
        message: 'Very high TypeScript error count',
        action: 'Stop other work and focus on critical fixes'
      });
    }
    
    // Build system failure
    if (dashboard.systemHealth.buildSystem && !dashboard.systemHealth.buildSystem.operational) {
      alerts.push({
        type: 'build-system-failure',
        severity: 'CRITICAL',
        message: 'Build system not operational',
        action: 'Fix build configuration immediately'
      });
    }
    
    // Component functionality failure
    if (dashboard.componentFunctionality?.riskLevel === 'HIGH') {
      alerts.push({
        type: 'component-failure',
        severity: 'HIGH',
        message: 'Component functionality at risk',
        action: 'Validate component integrity before continuing'
      });
    }
    
    return alerts;
  }

  displayDashboard(dashboard) {
    console.log('\n' + '='.repeat(80));
    console.log('🎯 TYPESCRIPT MONITORING DASHBOARD');
    console.log('='.repeat(80));
    
    console.log(`\n🏥 SYSTEM HEALTH: ${dashboard.systemHealth.overallHealth.toUpperCase()}`);
    console.log(`   Monitoring Active: ${dashboard.systemHealth.monitoring.active ? '✅' : '❌'}`);
    console.log(`   File System: ${dashboard.systemHealth.fileSystem.accessible ? '✅' : '❌'}`);
    console.log(`   Build System: ${dashboard.systemHealth.buildSystem.operational ? '✅' : '❌'}`);
    
    console.log(`\n📊 CURRENT STATUS:`);
    console.log(`   TypeScript Errors: ${dashboard.overallAssessment.keyMetrics.tsErrors}`);
    console.log(`   Performance Score: ${dashboard.overallAssessment.keyMetrics.perfScore}/100`);
    console.log(`   Agent Coordination: ${dashboard.overallAssessment.keyMetrics.agentHealth}`);
    
    if (dashboard.criticalAlerts.length > 0) {
      console.log(`\n🚨 CRITICAL ALERTS:`);
      dashboard.criticalAlerts.forEach(alert => {
        console.log(`   ${alert.severity}: ${alert.message}`);
        console.log(`   Action: ${alert.action}`);
      });
    }
    
    console.log(`\n💡 AGENT RECOMMENDATIONS:`);
    dashboard.agentRecommendations.immediate.forEach(rec => {
      console.log(`   • ${rec}`);
    });
    
    console.log(`\n🤝 COORDINATION STATUS:`);
    console.log(`   Active Agents: ${dashboard.agentCoordination.activeAgents}`);
    console.log(`   File Conflicts: ${dashboard.agentCoordination.fileConflicts}`);
    console.log(`   Health: ${dashboard.agentCoordination.coordinationHealth}`);
    
    console.log(`\n📈 ASSESSMENT: ${dashboard.overallAssessment.summary}`);
    
    console.log('\n' + '='.repeat(80));
    console.log(`Dashboard ID: ${dashboard.dashboardId} | ${dashboard.timestamp}`);
    console.log('='.repeat(80) + '\n');
  }

  saveDashboard(dashboard) {
    fs.writeFileSync(this.dashboardPath, JSON.stringify(dashboard, null, 2));
    
    // Keep historical dashboards
    const historyPath = path.join(__dirname, 'dashboard-history');
    if (!fs.existsSync(historyPath)) {
      fs.mkdirSync(historyPath, { recursive: true });
    }
    
    const historyFile = path.join(historyPath, `dashboard-${Date.now()}.json`);
    fs.writeFileSync(historyFile, JSON.stringify(dashboard, null, 2));
  }

  async startRealtimeDashboard(updateIntervalMs = 45000) {
    this.log('🚀 Starting real-time monitoring dashboard...', 'INFO');
    
    const update = async () => {
      try {
        await this.generateDashboard();
        setTimeout(update, updateIntervalMs);
      } catch (error) {
        this.log(`Dashboard update failed: ${error.message}`, 'ERROR');
        setTimeout(update, updateIntervalMs * 2); // Back off on error
      }
    };
    
    // Initial dashboard
    await this.generateDashboard();
    
    // Start periodic updates
    setTimeout(update, updateIntervalMs);
  }
}

// CLI interface
if (require.main === module) {
  const dashboard = new MonitoringDashboard();
  const command = process.argv[2];
  
  switch (command) {
    case 'generate':
      dashboard.generateDashboard();
      break;
    case 'realtime':
      const interval = parseInt(process.argv[3]) || 45000;
      dashboard.startRealtimeDashboard(interval);
      break;
    default:
      console.log('TypeScript Monitoring Dashboard');
      console.log('Usage: node monitoring-dashboard.js [generate|realtime]');
      console.log('  generate         - Generate single dashboard report');
      console.log('  realtime [ms]    - Start real-time dashboard (default: 45s)');
      break;
  }
}

module.exports = MonitoringDashboard;