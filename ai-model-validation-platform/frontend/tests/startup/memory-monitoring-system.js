#!/usr/bin/env node

/**
 * Real-time Memory Monitoring System
 * Monitors Node.js process memory usage during startup and runtime
 */

const { spawn } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class MemoryMonitoringSystem {
  constructor(options = {}) {
    this.config = {
      monitoringInterval: options.interval || 1000, // 1 second
      maxMemoryThreshold: options.maxMemory || 2 * 1024 * 1024 * 1024, // 2GB
      warningThreshold: options.warningMemory || 1.5 * 1024 * 1024 * 1024, // 1.5GB
      criticalThreshold: options.criticalMemory || 1.8 * 1024 * 1024 * 1024, // 1.8GB
      maxDuration: options.maxDuration || 300000, // 5 minutes
      sampleInterval: 500, // High frequency sampling
      alertInterval: 5000, // Alert frequency
      outputFile: options.outputFile || path.join(process.cwd(), 'tests', 'startup', 'memory-monitoring-results.json')
    };
    
    this.monitoringData = {
      startTime: null,
      endTime: null,
      samples: [],
      alerts: [],
      summary: {},
      processes: new Map()
    };
    
    this.isMonitoring = false;
    this.monitoringTimer = null;
    this.alertTimer = null;
  }

  async startMonitoring(targetProcessName = 'node') {
    console.log('🧠 Starting Real-time Memory Monitoring System');
    console.log('=' .repeat(60));
    
    this.monitoringData.startTime = new Date();
    this.isMonitoring = true;
    
    await this.initializeMonitoring();
    
    // Start periodic monitoring
    this.monitoringTimer = setInterval(() => {
      this.collectMemoryData();
    }, this.config.sampleInterval);
    
    // Start alert monitoring
    this.alertTimer = setInterval(() => {
      this.checkAlerts();
    }, this.config.alertInterval);
    
    // Monitor system resources
    this.systemMonitorTimer = setInterval(() => {
      this.collectSystemData();
    }, this.config.monitoringInterval);
    
    console.log(`📊 Monitoring started - Target: ${targetProcessName}`);
    console.log(`📈 Sample interval: ${this.config.sampleInterval}ms`);
    console.log(`⚠️  Warning threshold: ${(this.config.warningThreshold / 1024 / 1024).toFixed(0)}MB`);
    console.log(`🚨 Critical threshold: ${(this.config.criticalThreshold / 1024 / 1024).toFixed(0)}MB`);
    
    return this.startRealtimeDashboard();
  }

  async stopMonitoring() {
    this.isMonitoring = false;
    
    if (this.monitoringTimer) {
      clearInterval(this.monitoringTimer);
    }
    
    if (this.alertTimer) {
      clearInterval(this.alertTimer);
    }
    
    if (this.systemMonitorTimer) {
      clearInterval(this.systemMonitorTimer);
    }
    
    this.monitoringData.endTime = new Date();
    this.generateSummary();
    
    await this.saveResults();
    await this.generateReport();
    
    console.log('\n🏁 Memory monitoring stopped');
    return this.monitoringData;
  }

  async initializeMonitoring() {
    // Get initial system state
    const systemInfo = {
      totalMemory: os.totalmem(),
      freeMemory: os.freemem(),
      platform: os.platform(),
      arch: os.arch(),
      nodeVersion: process.version,
      cpuCount: os.cpus().length,
      uptime: os.uptime()
    };
    
    this.monitoringData.systemInfo = systemInfo;
    
    // Create output directory
    await fs.mkdir(path.dirname(this.config.outputFile), { recursive: true });
    
    console.log(`💻 System: ${systemInfo.platform} ${systemInfo.arch}`);
    console.log(`🧮 Total Memory: ${(systemInfo.totalMemory / 1024 / 1024 / 1024).toFixed(1)}GB`);
    console.log(`🆓 Free Memory: ${(systemInfo.freeMemory / 1024 / 1024 / 1024).toFixed(1)}GB`);
  }

  async collectMemoryData() {
    try {
      const processes = await this.getNodeProcesses();
      const timestamp = Date.now();
      const systemMemory = this.getSystemMemoryInfo();
      
      const sample = {
        timestamp,
        time: new Date().toISOString(),
        processes: [],
        systemMemory,
        totalNodeMemory: 0
      };
      
      for (const proc of processes) {
        const memoryInfo = await this.getProcessMemoryInfo(proc);
        if (memoryInfo) {
          sample.processes.push(memoryInfo);
          sample.totalNodeMemory += memoryInfo.memoryUsage.heapUsed;
        }
      }
      
      this.monitoringData.samples.push(sample);
      
      // Keep only recent samples to prevent memory bloat
      if (this.monitoringData.samples.length > 1000) {
        this.monitoringData.samples = this.monitoringData.samples.slice(-1000);
      }
      
      // Real-time console output (throttled)
      if (this.monitoringData.samples.length % 10 === 0) {
        this.displayRealtimeStats(sample);
      }
      
    } catch (error) {
      console.warn(`Warning: Failed to collect memory data: ${error.message}`);
    }
  }

  async getNodeProcesses() {
    return new Promise((resolve) => {
      const processes = [];
      const ps = spawn('ps', ['aux']);
      let output = '';
      
      ps.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      ps.on('close', () => {
        const lines = output.split('\n').slice(1); // Skip header
        
        for (const line of lines) {
          if (line.includes('node') || line.includes('craco') || line.includes('react-scripts')) {
            const parts = line.trim().split(/\s+/);
            if (parts.length >= 11) {
              processes.push({
                user: parts[0],
                pid: parseInt(parts[1]),
                cpu: parseFloat(parts[2]),
                mem: parseFloat(parts[3]),
                vsz: parseInt(parts[4]),
                rss: parseInt(parts[5]),
                command: parts.slice(10).join(' ')
              });
            }
          }
        }
        
        resolve(processes);
      });
      
      ps.on('error', () => resolve([]));
    });
  }

  async getProcessMemoryInfo(process) {
    try {
      // Try to get detailed memory info if it's our process
      if (process.pid === process.pid) {
        return {
          pid: process.pid,
          command: process.command,
          cpu: process.cpu,
          memoryUsage: {
            rss: process.rss * 1024, // Convert from KB to bytes
            heapTotal: process.rss * 1024,
            heapUsed: process.rss * 1024 * 0.8, // Estimate
            external: 0,
            arrayBuffers: 0
          },
          systemMemory: {
            vsz: process.vsz * 1024,
            rss: process.rss * 1024,
            memPercent: process.mem
          }
        };
      }
      
      return {
        pid: process.pid,
        command: process.command,
        cpu: process.cpu,
        memoryUsage: {
          heapUsed: process.rss * 1024,
          rss: process.rss * 1024
        },
        systemMemory: {
          vsz: process.vsz * 1024,
          rss: process.rss * 1024,
          memPercent: process.mem
        }
      };
    } catch (error) {
      return null;
    }
  }

  getSystemMemoryInfo() {
    return {
      totalMemory: os.totalmem(),
      freeMemory: os.freemem(),
      usedMemory: os.totalmem() - os.freemem(),
      usagePercent: ((os.totalmem() - os.freemem()) / os.totalmem()) * 100,
      loadAverage: os.loadavg()
    };
  }

  collectSystemData() {
    const systemData = {
      timestamp: Date.now(),
      time: new Date().toISOString(),
      memory: this.getSystemMemoryInfo(),
      uptime: os.uptime(),
      loadAverage: os.loadavg()
    };
    
    if (!this.monitoringData.systemSamples) {
      this.monitoringData.systemSamples = [];
    }
    
    this.monitoringData.systemSamples.push(systemData);
    
    // Keep only recent samples
    if (this.monitoringData.systemSamples.length > 300) {
      this.monitoringData.systemSamples = this.monitoringData.systemSamples.slice(-300);
    }
  }

  checkAlerts() {
    const latestSample = this.monitoringData.samples[this.monitoringData.samples.length - 1];
    if (!latestSample) return;
    
    const totalMemoryUsage = latestSample.totalNodeMemory;
    const systemMemoryUsage = latestSample.systemMemory.usedMemory;
    
    // Check Node.js process memory alerts
    if (totalMemoryUsage > this.config.criticalThreshold) {
      this.createAlert('CRITICAL', 'Node.js memory usage exceeded critical threshold', {
        currentUsage: totalMemoryUsage,
        threshold: this.config.criticalThreshold,
        processes: latestSample.processes
      });
    } else if (totalMemoryUsage > this.config.warningThreshold) {
      this.createAlert('WARNING', 'Node.js memory usage approaching critical level', {
        currentUsage: totalMemoryUsage,
        threshold: this.config.warningThreshold
      });
    }
    
    // Check system memory alerts
    const systemUsagePercent = latestSample.systemMemory.usagePercent;
    if (systemUsagePercent > 90) {
      this.createAlert('CRITICAL', 'System memory usage critical', {
        systemUsagePercent,
        freeMemory: latestSample.systemMemory.freeMemory
      });
    } else if (systemUsagePercent > 80) {
      this.createAlert('WARNING', 'System memory usage high', {
        systemUsagePercent
      });
    }
    
    // Check for memory leaks (rapid growth)
    this.checkMemoryLeaks();
  }

  checkMemoryLeaks() {
    if (this.monitoringData.samples.length < 60) return; // Need enough samples
    
    const recentSamples = this.monitoringData.samples.slice(-60); // Last 60 samples
    const startMemory = recentSamples[0].totalNodeMemory;
    const endMemory = recentSamples[recentSamples.length - 1].totalNodeMemory;
    
    const growthRate = (endMemory - startMemory) / startMemory;
    const timeSpan = recentSamples[recentSamples.length - 1].timestamp - recentSamples[0].timestamp;
    
    // Alert if memory grew more than 50% in the last 60 seconds
    if (growthRate > 0.5 && timeSpan < 60000) {
      this.createAlert('WARNING', 'Potential memory leak detected', {
        growthRate: `${(growthRate * 100).toFixed(1)}%`,
        timeSpan: `${timeSpan / 1000}s`,
        startMemory,
        endMemory
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
    
    this.monitoringData.alerts.push(alert);
    
    // Console output based on level
    const icon = level === 'CRITICAL' ? '🚨' : '⚠️';
    const color = level === 'CRITICAL' ? '\x1b[31m' : '\x1b[33m'; // Red or Yellow
    const reset = '\x1b[0m';
    
    console.log(`${icon} ${color}[${level}]${reset} ${message}`);
    
    if (data.currentUsage) {
      console.log(`   Memory: ${(data.currentUsage / 1024 / 1024).toFixed(1)}MB`);
    }
    
    if (data.systemUsagePercent) {
      console.log(`   System: ${data.systemUsagePercent.toFixed(1)}%`);
    }
  }

  displayRealtimeStats(sample) {
    const memoryMB = (sample.totalNodeMemory / 1024 / 1024).toFixed(1);
    const systemPercent = sample.systemMemory.usagePercent.toFixed(1);
    const processCount = sample.processes.length;
    const uptime = Math.floor((Date.now() - this.monitoringData.startTime.getTime()) / 1000);
    
    // Clear previous line and show current stats
    process.stdout.write('\r\x1b[K'); // Clear line
    process.stdout.write(`📊 Node.js: ${memoryMB}MB | System: ${systemPercent}% | Processes: ${processCount} | Uptime: ${uptime}s`);
  }

  async startRealtimeDashboard() {
    const dashboardPath = path.join(process.cwd(), 'tests', 'startup', 'memory-dashboard.html');
    
    const dashboardHTML = `<!DOCTYPE html>
<html>
<head>
    <title>Memory Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .dashboard { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .panel { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .alert-critical { background: #ffebee; border-left: 4px solid #f44336; }
        .alert-warning { background: #fff3e0; border-left: 4px solid #ff9800; }
        .stats { display: flex; justify-content: space-between; margin-bottom: 20px; }
        .stat { text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; }
        .chart-container { position: relative; height: 300px; }
    </style>
</head>
<body>
    <h1>🧠 Real-time Memory Monitoring Dashboard</h1>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value" id="currentMemory">0MB</div>
            <div>Node.js Memory</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="systemMemory">0%</div>
            <div>System Memory</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="processCount">0</div>
            <div>Processes</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="uptime">0s</div>
            <div>Monitoring Time</div>
        </div>
    </div>
    
    <div class="dashboard">
        <div class="panel">
            <h3>Memory Usage Over Time</h3>
            <div class="chart-container">
                <canvas id="memoryChart"></canvas>
            </div>
        </div>
        
        <div class="panel">
            <h3>System Resources</h3>
            <div class="chart-container">
                <canvas id="systemChart"></canvas>
            </div>
        </div>
        
        <div class="panel">
            <h3>Process List</h3>
            <div id="processList"></div>
        </div>
        
        <div class="panel">
            <h3>Recent Alerts</h3>
            <div id="alertsList"></div>
        </div>
    </div>

    <script>
        // Chart configuration
        const memoryChart = new Chart(document.getElementById('memoryChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Node.js Memory (MB)',
                    data: [],
                    borderColor: '#2196F3',
                    backgroundColor: 'rgba(33, 150, 243, 0.1)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Memory (MB)'
                        }
                    }
                }
            }
        });
        
        const systemChart = new Chart(document.getElementById('systemChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'System Memory %',
                    data: [],
                    borderColor: '#FF9800',
                    backgroundColor: 'rgba(255, 152, 0, 0.1)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Usage %'
                        }
                    }
                }
            }
        });

        // Auto-refresh data
        setInterval(updateDashboard, 2000);
        
        function updateDashboard() {
            fetch('memory-monitoring-results.json')
                .then(response => response.json())
                .then(data => {
                    updateStats(data);
                    updateCharts(data);
                    updateProcessList(data);
                    updateAlerts(data);
                })
                .catch(error => console.log('Data not available yet'));
        }
        
        function updateStats(data) {
            if (data.samples && data.samples.length > 0) {
                const latest = data.samples[data.samples.length - 1];
                document.getElementById('currentMemory').textContent = 
                    Math.round(latest.totalNodeMemory / 1024 / 1024) + 'MB';
                document.getElementById('systemMemory').textContent = 
                    latest.systemMemory.usagePercent.toFixed(1) + '%';
                document.getElementById('processCount').textContent = latest.processes.length;
            }
            
            if (data.startTime) {
                const uptime = Math.floor((Date.now() - new Date(data.startTime).getTime()) / 1000);
                document.getElementById('uptime').textContent = uptime + 's';
            }
        }
        
        function updateCharts(data) {
            if (!data.samples) return;
            
            const recentSamples = data.samples.slice(-50); // Last 50 samples
            const labels = recentSamples.map(s => new Date(s.timestamp).toLocaleTimeString());
            const memoryData = recentSamples.map(s => Math.round(s.totalNodeMemory / 1024 / 1024));
            const systemData = recentSamples.map(s => s.systemMemory.usagePercent);
            
            memoryChart.data.labels = labels;
            memoryChart.data.datasets[0].data = memoryData;
            memoryChart.update('none');
            
            systemChart.data.labels = labels;
            systemChart.data.datasets[0].data = systemData;
            systemChart.update('none');
        }
        
        function updateProcessList(data) {
            if (!data.samples || data.samples.length === 0) return;
            
            const latest = data.samples[data.samples.length - 1];
            const processList = document.getElementById('processList');
            
            processList.innerHTML = latest.processes
                .map(p => \`
                    <div style="margin-bottom: 10px; padding: 8px; background: #f9f9f9; border-radius: 4px;">
                        <strong>PID \${p.pid}</strong> - \${Math.round(p.memoryUsage.heapUsed / 1024 / 1024)}MB
                        <br><small>\${p.command}</small>
                    </div>
                \`).join('');
        }
        
        function updateAlerts(data) {
            if (!data.alerts) return;
            
            const alertsList = document.getElementById('alertsList');
            const recentAlerts = data.alerts.slice(-5); // Last 5 alerts
            
            alertsList.innerHTML = recentAlerts
                .map(a => \`
                    <div class="alert-\${a.level.toLowerCase()}" style="margin-bottom: 10px; padding: 10px; border-radius: 4px;">
                        <strong>\${a.level}</strong> - \${a.message}
                        <br><small>\${new Date(a.timestamp).toLocaleString()}</small>
                    </div>
                \`).join('');
        }
        
        // Initial load
        updateDashboard();
    </script>
</body>
</html>`;
    
    await fs.writeFile(dashboardPath, dashboardHTML);
    console.log(`🌐 Dashboard available at: file://${dashboardPath}`);
    
    return dashboardPath;
  }

  generateSummary() {
    if (this.monitoringData.samples.length === 0) return;
    
    const memoryValues = this.monitoringData.samples.map(s => s.totalNodeMemory);
    const systemValues = this.monitoringData.samples.map(s => s.systemMemory.usagePercent);
    
    this.monitoringData.summary = {
      duration: this.monitoringData.endTime - this.monitoringData.startTime,
      totalSamples: this.monitoringData.samples.length,
      memory: {
        min: Math.min(...memoryValues),
        max: Math.max(...memoryValues),
        average: memoryValues.reduce((a, b) => a + b, 0) / memoryValues.length,
        final: memoryValues[memoryValues.length - 1]
      },
      system: {
        minUsage: Math.min(...systemValues),
        maxUsage: Math.max(...systemValues),
        averageUsage: systemValues.reduce((a, b) => a + b, 0) / systemValues.length
      },
      alerts: {
        total: this.monitoringData.alerts.length,
        critical: this.monitoringData.alerts.filter(a => a.level === 'CRITICAL').length,
        warning: this.monitoringData.alerts.filter(a => a.level === 'WARNING').length
      },
      thresholds: {
        warningExceeded: memoryValues.some(v => v > this.config.warningThreshold),
        criticalExceeded: memoryValues.some(v => v > this.config.criticalThreshold)
      }
    };
  }

  async saveResults() {
    await fs.writeFile(this.config.outputFile, JSON.stringify(this.monitoringData, null, 2));
    console.log(`\n💾 Results saved to: ${this.config.outputFile}`);
  }

  async generateReport() {
    const reportPath = path.join(process.cwd(), 'tests', 'startup', 'memory-monitoring-report.md');
    const summary = this.monitoringData.summary;
    
    const report = `# Memory Monitoring Report

Generated: ${new Date().toISOString()}
Duration: ${Math.round(summary.duration / 1000)}s
Total Samples: ${summary.totalSamples}

## Memory Usage Summary

- **Peak Usage**: ${(summary.memory.max / 1024 / 1024).toFixed(1)}MB
- **Average Usage**: ${(summary.memory.average / 1024 / 1024).toFixed(1)}MB
- **Final Usage**: ${(summary.memory.final / 1024 / 1024).toFixed(1)}MB
- **Memory Growth**: ${((summary.memory.final - summary.memory.min) / 1024 / 1024).toFixed(1)}MB

## System Resources

- **Peak System Usage**: ${summary.system.maxUsage.toFixed(1)}%
- **Average System Usage**: ${summary.system.averageUsage.toFixed(1)}%

## Threshold Analysis

- **Warning Threshold Exceeded**: ${summary.thresholds.warningExceeded ? 'YES' : 'NO'}
- **Critical Threshold Exceeded**: ${summary.thresholds.criticalExceeded ? 'YES' : 'NO'}

## Alerts Summary

- **Total Alerts**: ${summary.alerts.total}
- **Critical Alerts**: ${summary.alerts.critical}
- **Warning Alerts**: ${summary.alerts.warning}

## Recommendations

${this.generateRecommendations()}

## Alert Details

${this.monitoringData.alerts.map(a => `
### ${a.level} - ${new Date(a.timestamp).toLocaleString()}
${a.message}
${a.data ? '```json\n' + JSON.stringify(a.data, null, 2) + '\n```' : ''}
`).join('')}
`;

    await fs.writeFile(reportPath, report);
    console.log(`📋 Report saved to: ${reportPath}`);
  }

  generateRecommendations() {
    const recommendations = [];
    const summary = this.monitoringData.summary;
    
    if (summary.memory.max > this.config.criticalThreshold) {
      recommendations.push('🚨 CRITICAL: Memory usage exceeded critical threshold. Consider increasing Node.js memory limit or optimizing memory usage.');
    }
    
    if (summary.memory.max > this.config.warningThreshold) {
      recommendations.push('⚠️ WARNING: Memory usage approaching limits. Monitor for memory leaks and optimize where possible.');
    }
    
    if (summary.alerts.total > 5) {
      recommendations.push('📊 High alert frequency detected. Review startup process and optimize resource usage.');
    }
    
    const memoryGrowth = summary.memory.final - summary.memory.min;
    if (memoryGrowth > 500 * 1024 * 1024) { // 500MB growth
      recommendations.push('📈 Significant memory growth detected during monitoring. Investigate potential memory leaks.');
    }
    
    if (summary.system.maxUsage > 90) {
      recommendations.push('🖥️ System memory usage critical. Consider increasing system memory or reducing other applications.');
    }
    
    if (recommendations.length === 0) {
      recommendations.push('✅ Memory usage appears healthy and within acceptable limits.');
    }
    
    return recommendations.map((r, i) => `${i + 1}. ${r}`).join('\n');
  }
}

// CLI Interface
if (require.main === module) {
  const monitor = new MemoryMonitoringSystem();
  
  // Handle graceful shutdown
  process.on('SIGINT', async () => {
    console.log('\n🛑 Stopping memory monitoring...');
    await monitor.stopMonitoring();
    process.exit(0);
  });
  
  process.on('SIGTERM', async () => {
    await monitor.stopMonitoring();
    process.exit(0);
  });
  
  // Start monitoring
  monitor.startMonitoring()
    .then(dashboardPath => {
      console.log(`\n🌐 Dashboard: ${dashboardPath}`);
      console.log('Press Ctrl+C to stop monitoring');
      
      // Keep the process running
      setInterval(() => {
        // Keep alive
      }, 1000);
    })
    .catch(error => {
      console.error('❌ Memory monitoring failed:', error);
      process.exit(1);
    });
}

module.exports = MemoryMonitoringSystem;