#!/usr/bin/env node

/**
 * Build Performance Monitor
 * Tracks build performance impact of TypeScript fixes
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class PerformanceMonitor {
  constructor() {
    this.resultsPath = path.join(__dirname, 'performance-metrics.json');
    this.logPath = path.join(__dirname, 'performance-monitoring.log');
    this.benchmarks = [];
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(this.logPath, logMessage + '\n');
  }

  async measureBuildPerformance() {
    this.log('🏃 Measuring build performance...', 'INFO');
    
    const measurements = {};
    
    // 1. TypeScript compilation time
    measurements.typeCheck = await this.measureTypeCheck();
    
    // 2. Linting time
    measurements.linting = await this.measureLinting();
    
    // 3. Memory usage during type checking
    measurements.memory = await this.measureMemoryUsage();
    
    // 4. File system metrics
    measurements.fileSystem = await this.getFileSystemMetrics();
    
    const benchmark = {
      timestamp: new Date().toISOString(),
      measurements: measurements,
      overallScore: this.calculatePerformanceScore(measurements)
    };
    
    this.benchmarks.push(benchmark);
    this.saveBenchmarks();
    
    this.log(`📊 Performance measured - Score: ${benchmark.overallScore}/100`, 'INFO');
    
    return benchmark;
  }

  async measureTypeCheck() {
    const startTime = Date.now();
    const initialMemory = process.memoryUsage();
    
    try {
      execSync('npx tsc --noEmit --skipLibCheck', { 
        encoding: 'utf8',
        timeout: 30000 // 30 second max
      });
      
      const duration = Date.now() - startTime;
      const memoryUsed = process.memoryUsage().heapUsed - initialMemory.heapUsed;
      
      return {
        success: true,
        duration: duration,
        memoryUsed: memoryUsed,
        errorsFound: 0
      };
      
    } catch (error) {
      const duration = Date.now() - startTime;
      const output = error.stdout || error.message || '';
      const errorCount = (output.match(/error TS\d+:/g) || []).length;
      
      return {
        success: false,
        duration: duration,
        memoryUsed: process.memoryUsage().heapUsed - initialMemory.heapUsed,
        errorsFound: errorCount
      };
    }
  }

  async measureLinting() {
    const startTime = Date.now();
    
    try {
      const result = execSync('npm run lint:dev', { 
        encoding: 'utf8',
        timeout: 20000
      });
      
      const duration = Date.now() - startTime;
      const warnings = (result.match(/warning/g) || []).length;
      
      return {
        success: true,
        duration: duration,
        warningsFound: warnings
      };
      
    } catch (error) {
      const duration = Date.now() - startTime;
      const output = error.stdout || error.message || '';
      const warnings = (output.match(/warning/g) || []).length;
      
      return {
        success: false,
        duration: duration,
        warningsFound: warnings
      };
    }
  }

  async measureMemoryUsage() {
    const usage = process.memoryUsage();
    
    return {
      heapUsed: usage.heapUsed,
      heapTotal: usage.heapTotal,
      external: usage.external,
      rss: usage.rss
    };
  }

  async getFileSystemMetrics() {
    try {
      const srcPath = path.join(process.cwd(), 'src');
      const nodeModulesPath = path.join(process.cwd(), 'node_modules');
      
      const getSizeRecursive = (dirPath) => {
        let totalSize = 0;
        let fileCount = 0;
        
        try {
          const files = fs.readdirSync(dirPath, { withFileTypes: true });
          
          for (const file of files) {
            const fullPath = path.join(dirPath, file.name);
            
            if (file.isDirectory()) {
              const subMetrics = getSizeRecursive(fullPath);
              totalSize += subMetrics.size;
              fileCount += subMetrics.count;
            } else {
              const stats = fs.statSync(fullPath);
              totalSize += stats.size;
              fileCount++;
            }
          }
        } catch (error) {
          // Skip inaccessible directories
        }
        
        return { size: totalSize, count: fileCount };
      };
      
      const srcMetrics = getSizeRecursive(srcPath);
      
      return {
        srcSize: srcMetrics.size,
        srcFileCount: srcMetrics.count,
        srcSizeMB: Math.round(srcMetrics.size / (1024 * 1024) * 100) / 100
      };
      
    } catch (error) {
      return {
        srcSize: 0,
        srcFileCount: 0,
        srcSizeMB: 0,
        error: error.message
      };
    }
  }

  calculatePerformanceScore(measurements) {
    let score = 100;
    
    // TypeScript compilation performance
    if (measurements.typeCheck.duration > 60000) { // > 1 minute
      score -= 30;
    } else if (measurements.typeCheck.duration > 30000) { // > 30 seconds
      score -= 15;
    }
    
    // Linting performance
    if (measurements.linting.duration > 20000) { // > 20 seconds
      score -= 15;
    } else if (measurements.linting.duration > 10000) { // > 10 seconds
      score -= 8;
    }
    
    // Memory usage (penalize if over 500MB)
    const memoryMB = measurements.memory.heapUsed / (1024 * 1024);
    if (memoryMB > 500) {
      score -= 20;
    } else if (memoryMB > 300) {
      score -= 10;
    }
    
    // Error count impact
    if (measurements.typeCheck.errorsFound > 50) {
      score -= 25;
    } else if (measurements.typeCheck.errorsFound > 20) {
      score -= 15;
    }
    
    return Math.max(0, Math.round(score));
  }

  getPerformanceTrend() {
    if (this.benchmarks.length < 2) return 'insufficient-data';
    
    const recent = this.benchmarks.slice(-3);
    const scores = recent.map(b => b.overallScore);
    
    if (scores.length === 2) {
      return scores[1] > scores[0] ? 'improving' : scores[1] < scores[0] ? 'degrading' : 'stable';
    }
    
    if (scores.length === 3) {
      if (scores[2] > scores[1] && scores[1] > scores[0]) return 'improving';
      if (scores[2] < scores[1] && scores[1] < scores[0]) return 'degrading';
      return 'fluctuating';
    }
    
    return 'stable';
  }

  generatePerformanceReport() {
    if (this.benchmarks.length === 0) {
      return 'No performance data available. Run measurement first.';
    }
    
    const latest = this.benchmarks[this.benchmarks.length - 1];
    const trend = this.getPerformanceTrend();
    
    let report = '\n⚡ === Build Performance Report ===\n';
    report += `🕐 Timestamp: ${latest.timestamp}\n`;
    report += `📈 Performance Score: ${latest.overallScore}/100\n`;
    report += `📊 Trend: ${trend}\n`;
    report += `⏱️  TypeScript Check: ${latest.measurements.typeCheck.duration}ms\n`;
    report += `⏱️  Linting: ${latest.measurements.linting.duration}ms\n`;
    report += `💾 Memory Used: ${Math.round(latest.measurements.memory.heapUsed / (1024 * 1024))}MB\n`;
    report += `📁 Source Code: ${latest.measurements.fileSystem.srcSizeMB}MB (${latest.measurements.fileSystem.srcFileCount} files)\n`;
    
    if (latest.measurements.typeCheck.errorsFound > 0) {
      report += `🔥 TypeScript Errors: ${latest.measurements.typeCheck.errorsFound}\n`;
    }
    
    if (latest.measurements.linting.warningsFound > 0) {
      report += `⚠️  Lint Warnings: ${latest.measurements.linting.warningsFound}\n`;
    }
    
    report += '=====================================\n';
    
    this.log(report, 'REPORT');
    return report;
  }

  saveBenchmarks() {
    const data = {
      benchmarks: this.benchmarks,
      lastUpdated: new Date().toISOString(),
      summary: {
        totalMeasurements: this.benchmarks.length,
        averageScore: this.benchmarks.length > 0 ? 
          Math.round(this.benchmarks.reduce((sum, b) => sum + b.overallScore, 0) / this.benchmarks.length) : 0,
        trend: this.getPerformanceTrend()
      }
    };
    
    fs.writeFileSync(this.resultsPath, JSON.stringify(data, null, 2));
  }

  loadBenchmarks() {
    try {
      if (fs.existsSync(this.resultsPath)) {
        const data = JSON.parse(fs.readFileSync(this.resultsPath, 'utf8'));
        this.benchmarks = data.benchmarks || [];
      }
    } catch (error) {
      this.log(`Failed to load benchmarks: ${error.message}`, 'ERROR');
      this.benchmarks = [];
    }
  }

  getAgentPerformanceFeedback() {
    if (this.benchmarks.length === 0) {
      return {
        status: 'no-data',
        message: 'No performance measurements available'
      };
    }
    
    const latest = this.benchmarks[this.benchmarks.length - 1];
    
    return {
      timestamp: latest.timestamp,
      performanceScore: latest.overallScore,
      typeCheckDuration: latest.measurements.typeCheck.duration,
      lintingDuration: latest.measurements.linting.duration,
      memoryUsageMB: Math.round(latest.measurements.memory.heapUsed / (1024 * 1024)),
      trend: this.getPerformanceTrend(),
      recommendation: this.getPerformanceRecommendation(latest),
      alerts: this.checkPerformanceAlerts(latest)
    };
  }

  getPerformanceRecommendation(latest) {
    const recommendations = [];
    
    if (latest.overallScore >= 90) {
      recommendations.push('Excellent performance! Continue current approach.');
    } else if (latest.overallScore >= 70) {
      recommendations.push('Good performance. Minor optimizations possible.');
    } else {
      recommendations.push('Performance needs attention. Check for bottlenecks.');
    }
    
    if (latest.measurements.typeCheck.duration > 30000) {
      recommendations.push('TypeScript check is slow. Consider incremental compilation.');
    }
    
    if (latest.measurements.memory.heapUsed > 500 * 1024 * 1024) {
      recommendations.push('High memory usage detected. Monitor for memory leaks.');
    }
    
    return recommendations.join(' ');
  }

  checkPerformanceAlerts(latest) {
    const alerts = [];
    
    if (latest.overallScore < 50) {
      alerts.push({
        type: 'performance-critical',
        message: 'Performance score critically low',
        score: latest.overallScore
      });
    }
    
    if (latest.measurements.typeCheck.duration > 60000) {
      alerts.push({
        type: 'slow-compilation',
        message: 'TypeScript compilation extremely slow',
        duration: latest.measurements.typeCheck.duration
      });
    }
    
    return alerts;
  }
}

// CLI interface
if (require.main === module) {
  const monitor = new PerformanceMonitor();
  const command = process.argv[2];
  
  switch (command) {
    case 'measure':
      monitor.measureBuildPerformance();
      break;
    case 'report':
      monitor.loadBenchmarks();
      monitor.generatePerformanceReport();
      break;
    case 'feedback':
      monitor.loadBenchmarks();
      console.log(JSON.stringify(monitor.getAgentPerformanceFeedback(), null, 2));
      break;
    default:
      console.log('Build Performance Monitor');
      console.log('Usage: node performance-monitor.js [measure|report|feedback]');
      break;
  }
}

module.exports = PerformanceMonitor;