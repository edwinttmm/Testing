#!/usr/bin/env node

/**
 * Performance Benchmarking System
 * Comprehensive startup time and resource benchmark tracking
 */

const { spawn, exec } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class PerformanceBenchmarkingSystem {
  constructor(options = {}) {
    this.config = {
      benchmarkRuns: options.runs || 5, // Number of benchmark runs
      warmupRuns: options.warmupRuns || 2, // Warmup runs to exclude from averages
      cooldownPeriod: options.cooldown || 10000, // 10 seconds between runs
      timeout: options.timeout || 180000, // 3 minutes timeout per run
      measureMemory: options.measureMemory !== false,
      measureCPU: options.measureCPU !== false,
      measureDisk: options.measureDisk !== false,
      measureNetwork: options.measureNetwork !== false,
      saveResults: options.saveResults !== false,
      outputFile: options.outputFile || path.join(process.cwd(), 'tests', 'startup', 'performance-benchmarks.json'),
      verbose: options.verbose !== false
    };
    
    this.benchmarkData = {
      startTime: null,
      endTime: null,
      configuration: { ...this.config },
      systemInfo: {},
      runs: [],
      warmupRuns: [],
      statistics: {},
      comparisons: {},
      recommendations: []
    };
    
    this.currentRun = 0;
    this.baseline = null;
  }

  async runBenchmarks() {
    console.log('🏃 Starting Performance Benchmarking System');
    console.log('=' .repeat(60));
    
    this.benchmarkData.startTime = new Date();
    await this.initializeBenchmarking();
    
    console.log(`📊 Benchmark runs: ${this.config.benchmarkRuns}`);
    console.log(`🔥 Warmup runs: ${this.config.warmupRuns}`);
    console.log(`⏱️ Cooldown period: ${this.config.cooldownPeriod / 1000}s`);
    console.log(`🎯 Timeout per run: ${this.config.timeout / 1000}s`);
    
    // Load baseline if exists
    await this.loadBaseline();
    
    // Run warmup benchmarks
    console.log('\n🔥 Starting warmup runs...');
    for (let i = 0; i < this.config.warmupRuns; i++) {
      const warmupRun = await this.runSingleBenchmark(true, i + 1);
      this.benchmarkData.warmupRuns.push(warmupRun);
      
      if (i < this.config.warmupRuns - 1) {
        console.log(`⏳ Cooldown ${this.config.cooldownPeriod / 1000}s...`);
        await this.delay(this.config.cooldownPeriod);
      }
    }
    
    console.log('\n📊 Starting benchmark runs...');
    
    // Run actual benchmarks
    for (let i = 0; i < this.config.benchmarkRuns; i++) {
      this.currentRun = i + 1;
      const benchmarkRun = await this.runSingleBenchmark(false, i + 1);
      this.benchmarkData.runs.push(benchmarkRun);
      
      this.displayRunResults(benchmarkRun);
      
      if (i < this.config.benchmarkRuns - 1) {
        console.log(`⏳ Cooldown ${this.config.cooldownPeriod / 1000}s...`);
        await this.delay(this.config.cooldownPeriod);
      }
    }
    
    // Calculate statistics
    await this.calculateStatistics();
    await this.performComparisons();
    await this.generateRecommendations();
    
    this.benchmarkData.endTime = new Date();
    
    if (this.config.saveResults) {
      await this.saveResults();
      await this.generateReport();
    }
    
    this.displayFinalResults();
    
    return this.benchmarkData;
  }

  async initializeBenchmarking() {
    // Get detailed system information
    const systemInfo = {
      platform: os.platform(),
      arch: os.arch(),
      nodeVersion: process.version,
      totalMemory: os.totalmem(),
      freeMemory: os.freemem(),
      cpuCount: os.cpus().length,
      cpuModel: os.cpus()[0]?.model || 'Unknown',
      cpuSpeed: os.cpus()[0]?.speed || 0,
      uptime: os.uptime(),
      loadAverage: os.loadavg(),
      networkInterfaces: Object.keys(os.networkInterfaces()),
      tmpDir: os.tmpdir(),
      homeDir: os.homedir(),
      timestamp: new Date().toISOString()
    };
    
    // Add disk information
    try {
      const diskInfo = await this.getDiskInfo();
      systemInfo.disk = diskInfo;
    } catch (error) {
      console.warn('⚠️ Could not get disk info:', error.message);
    }
    
    // Add package.json info
    try {
      const packagePath = path.join(process.cwd(), 'package.json');
      const packageJson = JSON.parse(await fs.readFile(packagePath, 'utf8'));
      systemInfo.projectInfo = {
        name: packageJson.name,
        version: packageJson.version,
        dependencies: Object.keys(packageJson.dependencies || {}).length,
        devDependencies: Object.keys(packageJson.devDependencies || {}).length
      };
    } catch (error) {
      console.warn('⚠️ Could not read package.json:', error.message);
    }
    
    this.benchmarkData.systemInfo = systemInfo;
    
    console.log(`💻 System: ${systemInfo.platform} ${systemInfo.arch}`);
    console.log(`🧮 Memory: ${(systemInfo.totalMemory / 1024 / 1024 / 1024).toFixed(1)}GB`);
    console.log(`⚙️ CPU: ${systemInfo.cpuModel} (${systemInfo.cpuCount} cores)`);
    console.log(`📦 Project: ${systemInfo.projectInfo?.name || 'Unknown'} v${systemInfo.projectInfo?.version || 'Unknown'}`);
    
    // Create output directory
    if (this.config.saveResults) {
      await fs.mkdir(path.dirname(this.config.outputFile), { recursive: true });
    }
    
    // Clear any existing processes
    await this.cleanupEnvironment();
  }

  async cleanupEnvironment() {
    console.log('🧹 Cleaning up environment...');
    
    try {
      // Kill existing processes
      await this.runCommand('pkill -f "craco start"').catch(() => {});
      await this.runCommand('pkill -f "react-scripts"').catch(() => {});
      await this.runCommand('pkill -f "webpack"').catch(() => {});
      
      // Clear ports
      const ports = [3000, 3001, 3002, 3003];
      for (const port of ports) {
        await this.runCommand(`lsof -ti:${port} | xargs kill -9`).catch(() => {});
      }
      
      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }
      
      await this.delay(2000);
      console.log('✅ Environment cleanup completed');
    } catch (error) {
      console.warn(`⚠️ Cleanup warning: ${error.message}`);
    }
  }

  async runSingleBenchmark(isWarmup = false, runNumber = 1) {
    const runType = isWarmup ? 'WARMUP' : 'BENCHMARK';
    console.log(`\n${runType === 'WARMUP' ? '🔥' : '📊'} ${runType} RUN ${runNumber}/${isWarmup ? this.config.warmupRuns : this.config.benchmarkRuns}`);
    
    const benchmarkRun = {
      runNumber,
      isWarmup,
      startTime: new Date(),
      phases: {},
      metrics: {},
      success: false,
      error: null
    };
    
    try {
      // Phase 1: Pre-startup measurements
      benchmarkRun.phases.preStartup = await this.measurePreStartup();
      
      // Phase 2: Application startup
      benchmarkRun.phases.startup = await this.measureStartup();
      
      // Phase 3: Post-startup measurements
      benchmarkRun.phases.postStartup = await this.measurePostStartup(benchmarkRun.phases.startup.process);
      
      // Phase 4: Runtime performance
      if (benchmarkRun.phases.startup.success) {
        benchmarkRun.phases.runtime = await this.measureRuntimePerformance(benchmarkRun.phases.startup.process);
      }
      
      // Phase 5: Cleanup
      benchmarkRun.phases.cleanup = await this.measureCleanup(benchmarkRun.phases.startup.process);
      
      // Calculate derived metrics
      benchmarkRun.metrics = this.calculateRunMetrics(benchmarkRun);
      benchmarkRun.success = benchmarkRun.phases.startup.success;
      
    } catch (error) {
      benchmarkRun.success = false;
      benchmarkRun.error = error.message;
      console.log(`❌ ${runType} run ${runNumber} failed: ${error.message}`);
    }
    
    benchmarkRun.endTime = new Date();
    benchmarkRun.totalDuration = benchmarkRun.endTime - benchmarkRun.startTime;
    
    return benchmarkRun;
  }

  async measurePreStartup() {
    const startTime = Date.now();
    
    const measurements = {
      timestamp: new Date(),
      system: {
        memory: this.getMemoryInfo(),
        cpu: await this.getCPUUsage(),
        disk: await this.getDiskUsage(),
        network: await this.getNetworkStats()
      },
      environment: {
        nodeModulesSize: await this.getNodeModulesSize(),
        cacheSize: await this.getCacheSize(),
        openFiles: await this.getOpenFileCount()
      }
    };
    
    measurements.duration = Date.now() - startTime;
    return measurements;
  }

  async measureStartup() {
    const startTime = Date.now();
    
    const measurements = {
      startTime: new Date(),
      success: false,
      process: null,
      metrics: {
        timeToFirstByte: 0,
        timeToInteractive: 0,
        timeToReady: 0,
        memoryAtStart: 0,
        memoryAtReady: 0,
        cpuPeakDuringStartup: 0
      }
    };
    
    try {
      // Start monitoring resources
      const resourceMonitor = this.startResourceMonitoring();
      
      // Launch the application
      const env = {
        ...process.env,
        HOST: 'localhost',
        PORT: '3000',
        SKIP_PREFLIGHT_CHECK: 'true',
        ESLINT_NO_DEV_ERRORS: 'true'
      };
      
      const childProcess = spawn('npm', ['start'], {
        env,
        stdio: ['pipe', 'pipe', 'pipe'],
        detached: false
      });
      
      measurements.process = childProcess;
      measurements.pid = childProcess.pid;
      measurements.metrics.memoryAtStart = process.memoryUsage().heapUsed;
      
      // Wait for startup completion
      const startupResult = await this.waitForApplicationReady(childProcess, resourceMonitor);
      
      Object.assign(measurements, startupResult);
      measurements.metrics.timeToReady = Date.now() - startTime;
      measurements.metrics.memoryAtReady = process.memoryUsage().heapUsed;
      
      // Stop resource monitoring
      const resourceStats = this.stopResourceMonitoring(resourceMonitor);
      measurements.resourceStats = resourceStats;
      
    } catch (error) {
      measurements.success = false;
      measurements.error = error.message;
    }
    
    measurements.endTime = new Date();
    measurements.duration = Date.now() - startTime;
    
    return measurements;
  }

  async measurePostStartup(process) {
    if (!process || !process.pid) return { error: 'No process to measure' };
    
    const startTime = Date.now();
    
    const measurements = {
      timestamp: new Date(),
      processInfo: await this.getProcessInfo(process.pid),
      performance: {
        responseTime: await this.measureResponseTime(),
        memoryUsage: this.getMemoryInfo(),
        cpuUsage: await this.getCPUUsage()
      },
      stability: await this.measureStability(process.pid)
    };
    
    measurements.duration = Date.now() - startTime;
    return measurements;
  }

  async measureRuntimePerformance(process) {
    if (!process || !process.pid) return { error: 'No process to measure' };
    
    const startTime = Date.now();
    const runtimeDuration = 30000; // 30 seconds of runtime measurement
    
    console.log(`  📈 Measuring runtime performance for ${runtimeDuration / 1000}s...`);
    
    const measurements = {
      startTime: new Date(),
      duration: runtimeDuration,
      samples: [],
      summary: {}
    };
    
    const sampleInterval = 2000; // Sample every 2 seconds
    const samples = [];
    
    const measurementPromise = new Promise((resolve) => {
      const interval = setInterval(async () => {
        try {
          const sample = {
            timestamp: Date.now(),
            memory: this.getMemoryInfo(),
            cpu: await this.getCPUUsage(),
            processInfo: await this.getProcessInfo(process.pid)
          };
          samples.push(sample);
        } catch (error) {
          // Process might have died
        }
      }, sampleInterval);
      
      setTimeout(() => {
        clearInterval(interval);
        resolve(samples);
      }, runtimeDuration);
    });
    
    measurements.samples = await measurementPromise;
    
    // Calculate runtime statistics
    if (measurements.samples.length > 0) {
      const memoryValues = measurements.samples.map(s => s.memory.heapUsed);
      const cpuValues = measurements.samples.filter(s => s.cpu.usage).map(s => s.cpu.usage);
      
      measurements.summary = {
        memoryMin: Math.min(...memoryValues),
        memoryMax: Math.max(...memoryValues),
        memoryAvg: memoryValues.reduce((a, b) => a + b, 0) / memoryValues.length,
        cpuMin: cpuValues.length > 0 ? Math.min(...cpuValues) : 0,
        cpuMax: cpuValues.length > 0 ? Math.max(...cpuValues) : 0,
        cpuAvg: cpuValues.length > 0 ? cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length : 0,
        sampleCount: measurements.samples.length
      };
    }
    
    measurements.endTime = new Date();
    measurements.totalDuration = Date.now() - startTime;
    
    return measurements;
  }

  async measureCleanup(process) {
    const startTime = Date.now();
    
    const measurements = {
      startTime: new Date(),
      success: false,
      shutdownTime: 0,
      finalMemory: this.getMemoryInfo()
    };
    
    try {
      if (process && !process.killed) {
        console.log(`  🧹 Shutting down process ${process.pid}...`);
        
        const shutdownStart = Date.now();
        process.kill('SIGTERM');
        
        // Wait for graceful shutdown
        await new Promise((resolve) => {
          const timeout = setTimeout(() => {
            if (!process.killed) {
              process.kill('SIGKILL');
            }
            resolve();
          }, 5000);
          
          process.on('exit', () => {
            clearTimeout(timeout);
            resolve();
          });
        });
        
        measurements.shutdownTime = Date.now() - shutdownStart;
        measurements.success = true;
      }
      
      // Force garbage collection
      if (global.gc) {
        global.gc();
      }
      
      // Wait for cleanup
      await this.delay(2000);
      
    } catch (error) {
      measurements.error = error.message;
    }
    
    measurements.endTime = new Date();
    measurements.duration = Date.now() - startTime;
    measurements.finalMemory = this.getMemoryInfo();
    
    return measurements;
  }

  startResourceMonitoring() {
    const monitor = {
      startTime: Date.now(),
      samples: [],
      interval: null
    };
    
    monitor.interval = setInterval(async () => {
      try {
        const sample = {
          timestamp: Date.now(),
          memory: this.getMemoryInfo(),
          cpu: await this.getCPUUsage()
        };
        monitor.samples.push(sample);
      } catch (error) {
        // Ignore errors during monitoring
      }
    }, 1000);
    
    return monitor;
  }

  stopResourceMonitoring(monitor) {
    if (monitor.interval) {
      clearInterval(monitor.interval);
    }
    
    const stats = {
      duration: Date.now() - monitor.startTime,
      sampleCount: monitor.samples.length,
      summary: {}
    };
    
    if (monitor.samples.length > 0) {
      const memoryValues = monitor.samples.map(s => s.memory.heapUsed);
      const cpuValues = monitor.samples.filter(s => s.cpu.usage).map(s => s.cpu.usage);
      
      stats.summary = {
        memoryPeak: Math.max(...memoryValues),
        memoryAverage: memoryValues.reduce((a, b) => a + b, 0) / memoryValues.length,
        cpuPeak: cpuValues.length > 0 ? Math.max(...cpuValues) : 0,
        cpuAverage: cpuValues.length > 0 ? cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length : 0
      };
    }
    
    return stats;
  }

  async waitForApplicationReady(process, monitor) {
    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        resolve({
          success: false,
          error: `Startup timeout after ${this.config.timeout}ms`,
          output: stdout + stderr
        });
      }, this.config.timeout);
      
      let stdout = '';
      let stderr = '';
      let resolved = false;
      let timeToFirstByte = 0;
      let timeToInteractive = 0;
      
      const resolveOnce = (result) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          resolve(result);
        }
      };
      
      process.stdout.on('data', (data) => {
        stdout += data;
        
        if (this.config.verbose) {
          process.stdout.write(data);
        }
        
        // Mark first output
        if (!timeToFirstByte) {
          timeToFirstByte = Date.now() - monitor.startTime;
        }
        
        // Check for compilation complete
        if (/webpack compiled|compiled successfully/i.test(data)) {
          timeToInteractive = Date.now() - monitor.startTime;
        }
        
        // Check for ready state
        if (this.isApplicationReady(data)) {
          resolveOnce({
            success: true,
            output: stdout + stderr,
            timeToFirstByte,
            timeToInteractive,
            port: this.extractPort(stdout + stderr)
          });
        }
      });
      
      process.stderr.on('data', (data) => {
        stderr += data;
        
        if (this.config.verbose) {
          process.stderr.write(data);
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
      
      process.on('exit', (code) => {
        if (code !== 0) {
          resolveOnce({
            success: false,
            error: `Process exited with code ${code}`,
            output: stdout + stderr
          });
        }
      });
      
      process.on('error', (error) => {
        resolveOnce({
          success: false,
          error: error.message,
          output: stdout + stderr
        });
      });
    });
  }

  isApplicationReady(output) {
    const readyPatterns = [
      /Local:\s+http/i,
      /On Your Network:/i,
      /webpack compiled successfully/i,
      /Compiled successfully/i
    ];
    
    return readyPatterns.some(pattern => pattern.test(output));
  }

  isCriticalError(output) {
    const criticalPatterns = [
      /Cannot find module/i,
      /Module not found/i,
      /EADDRINUSE/i,
      /Failed to compile/i,
      /JavaScript heap out of memory/i,
      /ENOENT/i
    ];
    
    return criticalPatterns.some(pattern => pattern.test(output));
  }

  extractPort(output) {
    const portMatch = output.match(/Local:\s+http:\/\/[^:]+:(\d+)/i);
    return portMatch ? parseInt(portMatch[1]) : 3000;
  }

  getMemoryInfo() {
    const memUsage = process.memoryUsage();
    return {
      ...memUsage,
      system: {
        total: os.totalmem(),
        free: os.freemem(),
        used: os.totalmem() - os.freemem()
      }
    };
  }

  async getCPUUsage() {
    return new Promise((resolve) => {
      const startUsage = process.cpuUsage();
      const startTime = Date.now();
      
      setTimeout(() => {
        const endUsage = process.cpuUsage(startUsage);
        const endTime = Date.now();
        const timeDiff = endTime - startTime;
        
        const usage = {
          user: endUsage.user / 1000, // Convert to milliseconds
          system: endUsage.system / 1000,
          total: (endUsage.user + endUsage.system) / 1000,
          usage: ((endUsage.user + endUsage.system) / 1000 / timeDiff) * 100,
          loadAverage: os.loadavg()
        };
        
        resolve(usage);
      }, 100);
    });
  }

  async getDiskInfo() {
    try {
      const result = await this.runCommand('df -h .');
      const lines = result.stdout.split('\n');
      if (lines.length > 1) {
        const parts = lines[1].split(/\s+/);
        return {
          filesystem: parts[0],
          size: parts[1],
          used: parts[2],
          available: parts[3],
          usePercent: parts[4]
        };
      }
    } catch (error) {
      return { error: error.message };
    }
  }

  async getDiskUsage() {
    try {
      const result = await this.runCommand('du -sh .');
      const size = result.stdout.split('\t')[0];
      return { projectSize: size };
    } catch (error) {
      return { error: error.message };
    }
  }

  async getNetworkStats() {
    try {
      // Simple network check
      const interfaces = os.networkInterfaces();
      const stats = {};
      
      for (const [name, addresses] of Object.entries(interfaces)) {
        stats[name] = addresses.filter(addr => !addr.internal);
      }
      
      return stats;
    } catch (error) {
      return { error: error.message };
    }
  }

  async getNodeModulesSize() {
    try {
      const result = await this.runCommand('du -sh node_modules 2>/dev/null || echo "0B"');
      return result.stdout.trim().split('\t')[0];
    } catch (error) {
      return 'Unknown';
    }
  }

  async getCacheSize() {
    try {
      const npmCache = await this.runCommand('npm config get cache');
      const cacheDir = npmCache.stdout.trim();
      const result = await this.runCommand(`du -sh "${cacheDir}" 2>/dev/null || echo "0B"`);
      return result.stdout.trim().split('\t')[0];
    } catch (error) {
      return 'Unknown';
    }
  }

  async getOpenFileCount() {
    try {
      const result = await this.runCommand('lsof | wc -l');
      return parseInt(result.stdout.trim());
    } catch (error) {
      return 0;
    }
  }

  async getProcessInfo(pid) {
    try {
      const result = await this.runCommand(`ps -p ${pid} -o pid,ppid,pcpu,pmem,vsz,rss,etime --no-headers`);
      const parts = result.stdout.trim().split(/\s+/);
      
      return {
        pid: parseInt(parts[0]),
        ppid: parseInt(parts[1]),
        cpu: parseFloat(parts[2]),
        memory: parseFloat(parts[3]),
        vsz: parseInt(parts[4]),
        rss: parseInt(parts[5]),
        etime: parts[6]
      };
    } catch (error) {
      return { error: error.message };
    }
  }

  async measureResponseTime() {
    try {
      const start = Date.now();
      await this.runCommand('curl -s -o /dev/null http://localhost:3000');
      return Date.now() - start;
    } catch (error) {
      return null;
    }
  }

  async measureStability(pid) {
    const measurements = [];
    const duration = 10000; // 10 seconds
    const interval = 1000; // 1 second intervals
    
    for (let i = 0; i < duration / interval; i++) {
      try {
        const info = await this.getProcessInfo(pid);
        measurements.push({
          timestamp: Date.now(),
          ...info
        });
        await this.delay(interval);
      } catch (error) {
        break;
      }
    }
    
    return {
      samples: measurements,
      stable: measurements.length === duration / interval
    };
  }

  calculateRunMetrics(run) {
    const metrics = {
      startupTime: 0,
      memoryEfficiency: 0,
      cpuEfficiency: 0,
      stabilityScore: 0,
      overallScore: 0
    };
    
    if (run.phases.startup?.success) {
      metrics.startupTime = run.phases.startup.duration;
      
      // Memory efficiency (lower is better)
      if (run.phases.postStartup?.performance?.memoryUsage) {
        const memUsed = run.phases.postStartup.performance.memoryUsage.heapUsed;
        const memTotal = run.phases.postStartup.performance.memoryUsage.system.total;
        metrics.memoryEfficiency = 100 - ((memUsed / memTotal) * 100);
      }
      
      // CPU efficiency during startup
      if (run.phases.startup?.resourceStats?.summary?.cpuAverage) {
        metrics.cpuEfficiency = Math.max(0, 100 - run.phases.startup.resourceStats.summary.cpuAverage);
      }
      
      // Stability score
      if (run.phases.postStartup?.stability?.stable) {
        metrics.stabilityScore = 100;
      }
      
      // Overall score (weighted average)
      const weights = {
        startup: 0.4,
        memory: 0.2,
        cpu: 0.2,
        stability: 0.2
      };
      
      const startupScore = Math.max(0, 100 - (metrics.startupTime / 1000)); // 1 point per second
      metrics.overallScore = (
        startupScore * weights.startup +
        metrics.memoryEfficiency * weights.memory +
        metrics.cpuEfficiency * weights.cpu +
        metrics.stabilityScore * weights.stability
      );
    }
    
    return metrics;
  }

  async calculateStatistics() {
    const validRuns = this.benchmarkData.runs.filter(run => run.success);
    
    if (validRuns.length === 0) {
      this.benchmarkData.statistics = { error: 'No successful runs to analyze' };
      return;
    }
    
    // Startup time statistics
    const startupTimes = validRuns.map(run => run.metrics.startupTime);
    const memoryUsages = validRuns.map(run => 
      run.phases.postStartup?.performance?.memoryUsage?.heapUsed || 0
    );
    const overallScores = validRuns.map(run => run.metrics.overallScore);
    
    this.benchmarkData.statistics = {
      runs: {
        total: this.benchmarkData.runs.length,
        successful: validRuns.length,
        failed: this.benchmarkData.runs.length - validRuns.length,
        successRate: (validRuns.length / this.benchmarkData.runs.length) * 100
      },
      startupTime: {
        min: Math.min(...startupTimes),
        max: Math.max(...startupTimes),
        average: startupTimes.reduce((a, b) => a + b, 0) / startupTimes.length,
        median: this.calculateMedian(startupTimes),
        standardDeviation: this.calculateStandardDeviation(startupTimes)
      },
      memoryUsage: {
        min: Math.min(...memoryUsages),
        max: Math.max(...memoryUsages),
        average: memoryUsages.reduce((a, b) => a + b, 0) / memoryUsages.length,
        median: this.calculateMedian(memoryUsages)
      },
      performance: {
        averageScore: overallScores.reduce((a, b) => a + b, 0) / overallScores.length,
        minScore: Math.min(...overallScores),
        maxScore: Math.max(...overallScores)
      }
    };
  }

  calculateMedian(values) {
    const sorted = values.slice().sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  calculateStandardDeviation(values) {
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const squareDiffs = values.map(value => Math.pow(value - avg, 2));
    const avgSquareDiff = squareDiffs.reduce((a, b) => a + b, 0) / values.length;
    return Math.sqrt(avgSquareDiff);
  }

  async performComparisons() {
    const stats = this.benchmarkData.statistics;
    
    if (!stats || stats.error) {
      this.benchmarkData.comparisons = { error: 'No statistics available for comparison' };
      return;
    }
    
    // Performance benchmarks (industry standards)
    const benchmarks = {
      excellent: { startupTime: 30000, memoryUsage: 500 * 1024 * 1024 }, // 30s, 500MB
      good: { startupTime: 60000, memoryUsage: 1000 * 1024 * 1024 }, // 60s, 1GB
      acceptable: { startupTime: 120000, memoryUsage: 2000 * 1024 * 1024 }, // 2min, 2GB
      poor: { startupTime: 180000, memoryUsage: 3000 * 1024 * 1024 } // 3min, 3GB
    };
    
    // Compare against benchmarks
    let performanceRating = 'poor';
    if (stats.startupTime.average <= benchmarks.excellent.startupTime && 
        stats.memoryUsage.average <= benchmarks.excellent.memoryUsage) {
      performanceRating = 'excellent';
    } else if (stats.startupTime.average <= benchmarks.good.startupTime && 
               stats.memoryUsage.average <= benchmarks.good.memoryUsage) {
      performanceRating = 'good';
    } else if (stats.startupTime.average <= benchmarks.acceptable.startupTime && 
               stats.memoryUsage.average <= benchmarks.acceptable.memoryUsage) {
      performanceRating = 'acceptable';
    }
    
    // Compare against baseline if available
    let baselineComparison = null;
    if (this.baseline) {
      baselineComparison = {
        startupTimeChange: stats.startupTime.average - this.baseline.startupTime.average,
        memoryUsageChange: stats.memoryUsage.average - this.baseline.memoryUsage.average,
        performanceScoreChange: stats.performance.averageScore - this.baseline.performance.averageScore
      };
    }
    
    this.benchmarkData.comparisons = {
      performanceRating,
      benchmarks,
      baseline: baselineComparison,
      consistencyScore: this.calculateConsistencyScore()
    };
  }

  calculateConsistencyScore() {
    const stats = this.benchmarkData.statistics;
    if (!stats || !stats.startupTime) return 0;
    
    // Lower standard deviation = higher consistency
    const maxAcceptableDeviation = stats.startupTime.average * 0.2; // 20% of average
    const actualDeviation = stats.startupTime.standardDeviation;
    
    return Math.max(0, 100 - ((actualDeviation / maxAcceptableDeviation) * 100));
  }

  async generateRecommendations() {
    const recommendations = [];
    const stats = this.benchmarkData.statistics;
    const comparisons = this.benchmarkData.comparisons;
    
    if (!stats || stats.error) {
      recommendations.push({
        priority: 'CRITICAL',
        category: 'Reliability',
        issue: 'No successful benchmark runs completed',
        solution: 'Investigate and fix critical startup failures'
      });
      this.benchmarkData.recommendations = recommendations;
      return;
    }
    
    // Startup time recommendations
    if (stats.startupTime.average > 120000) { // 2 minutes
      recommendations.push({
        priority: 'HIGH',
        category: 'Performance',
        issue: `Slow startup time: ${(stats.startupTime.average / 1000).toFixed(1)}s average`,
        solution: 'Optimize bundle size, implement code splitting, or use faster build tools'
      });
    } else if (stats.startupTime.average > 60000) { // 1 minute
      recommendations.push({
        priority: 'MEDIUM',
        category: 'Performance',
        issue: `Moderate startup time: ${(stats.startupTime.average / 1000).toFixed(1)}s average`,
        solution: 'Consider performance optimizations and dependency review'
      });
    }
    
    // Memory usage recommendations
    if (stats.memoryUsage.average > 2000 * 1024 * 1024) { // 2GB
      recommendations.push({
        priority: 'HIGH',
        category: 'Memory',
        issue: `High memory usage: ${(stats.memoryUsage.average / 1024 / 1024).toFixed(1)}MB average`,
        solution: 'Investigate memory leaks and optimize memory usage'
      });
    }
    
    // Consistency recommendations
    if (comparisons.consistencyScore < 70) {
      recommendations.push({
        priority: 'MEDIUM',
        category: 'Reliability',
        issue: `Inconsistent performance: ${comparisons.consistencyScore.toFixed(1)}% consistency`,
        solution: 'Investigate sources of performance variation'
      });
    }
    
    // Success rate recommendations
    if (stats.runs.successRate < 100) {
      recommendations.push({
        priority: 'HIGH',
        category: 'Reliability',
        issue: `Startup failures: ${(100 - stats.runs.successRate).toFixed(1)}% failure rate`,
        solution: 'Fix startup reliability issues before performance optimization'
      });
    }
    
    // Baseline comparison recommendations
    if (comparisons.baseline) {
      if (comparisons.baseline.startupTimeChange > 10000) { // 10s regression
        recommendations.push({
          priority: 'HIGH',
          category: 'Regression',
          issue: `Performance regression: ${(comparisons.baseline.startupTimeChange / 1000).toFixed(1)}s slower than baseline`,
          solution: 'Review recent changes that may have impacted startup performance'
        });
      }
    }
    
    // Positive recommendations
    if (comparisons.performanceRating === 'excellent') {
      recommendations.push({
        priority: 'INFO',
        category: 'Achievement',
        issue: 'Excellent startup performance achieved',
        solution: 'Consider documenting configuration and maintaining current performance'
      });
    }
    
    this.benchmarkData.recommendations = recommendations;
  }

  async loadBaseline() {
    try {
      const baselinePath = path.join(path.dirname(this.config.outputFile), 'performance-baseline.json');
      const baselineData = await fs.readFile(baselinePath, 'utf8');
      this.baseline = JSON.parse(baselineData).statistics;
      console.log(`📊 Loaded performance baseline from ${baselinePath}`);
    } catch (error) {
      console.log('📊 No baseline found, current run will become baseline');
    }
  }

  async saveBaseline() {
    try {
      const baselinePath = path.join(path.dirname(this.config.outputFile), 'performance-baseline.json');
      const baselineData = {
        createdAt: new Date().toISOString(),
        systemInfo: this.benchmarkData.systemInfo,
        statistics: this.benchmarkData.statistics
      };
      await fs.writeFile(baselinePath, JSON.stringify(baselineData, null, 2));
      console.log(`💾 Saved performance baseline to ${baselinePath}`);
    } catch (error) {
      console.warn(`⚠️ Could not save baseline: ${error.message}`);
    }
  }

  displayRunResults(run) {
    const success = run.success ? '✅' : '❌';
    const startupTime = run.success ? `${run.metrics.startupTime}ms` : 'Failed';
    const score = run.success ? `${run.metrics.overallScore.toFixed(1)}` : 'N/A';
    
    console.log(`  ${success} Run ${run.runNumber}: ${startupTime} (Score: ${score})`);
  }

  displayFinalResults() {
    console.log('\n' + '='.repeat(60));
    console.log('🏁 PERFORMANCE BENCHMARK RESULTS');
    console.log('='.repeat(60));
    
    const stats = this.benchmarkData.statistics;
    
    if (stats.error) {
      console.log('❌ No successful runs to report');
      return;
    }
    
    console.log(`📊 Success Rate: ${stats.runs.successful}/${stats.runs.total} (${stats.runs.successRate.toFixed(1)}%)`);
    console.log(`⏱️ Startup Time: ${(stats.startupTime.average / 1000).toFixed(1)}s avg (${(stats.startupTime.min / 1000).toFixed(1)}s - ${(stats.startupTime.max / 1000).toFixed(1)}s)`);
    console.log(`🧠 Memory Usage: ${(stats.memoryUsage.average / 1024 / 1024).toFixed(1)}MB avg`);
    console.log(`🎯 Performance Score: ${stats.performance.averageScore.toFixed(1)}/100`);
    console.log(`🔄 Consistency: ${this.benchmarkData.comparisons.consistencyScore.toFixed(1)}%`);
    console.log(`📈 Rating: ${this.benchmarkData.comparisons.performanceRating.toUpperCase()}`);
    
    // Show critical recommendations
    const criticalRecs = this.benchmarkData.recommendations.filter(r => r.priority === 'CRITICAL' || r.priority === 'HIGH');
    if (criticalRecs.length > 0) {
      console.log('\n🚨 CRITICAL RECOMMENDATIONS:');
      criticalRecs.forEach((rec, i) => {
        console.log(`${i + 1}. [${rec.priority}] ${rec.issue}`);
        console.log(`   Solution: ${rec.solution}`);
      });
    }
    
    console.log('\n📋 Detailed results saved to performance benchmarks file');
  }

  async runCommand(command) {
    return new Promise((resolve, reject) => {
      exec(command, { timeout: 30000 }, (error, stdout, stderr) => {
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

  async saveResults() {
    await fs.writeFile(this.config.outputFile, JSON.stringify(this.benchmarkData, null, 2));
    console.log(`💾 Results saved to: ${this.config.outputFile}`);
    
    // Save as baseline if this is a successful run
    if (this.benchmarkData.statistics && !this.benchmarkData.statistics.error) {
      await this.saveBaseline();
    }
  }

  async generateReport() {
    const reportPath = path.join(process.cwd(), 'tests', 'startup', 'performance-benchmark-report.md');
    const stats = this.benchmarkData.statistics;
    const comparisons = this.benchmarkData.comparisons;
    
    const report = `# Performance Benchmark Report

Generated: ${new Date().toISOString()}
Total Duration: ${Math.round((this.benchmarkData.endTime - this.benchmarkData.startTime) / 1000)}s
Benchmark Runs: ${this.config.benchmarkRuns}
Warmup Runs: ${this.config.warmupRuns}

## System Information

- **Platform**: ${this.benchmarkData.systemInfo.platform} ${this.benchmarkData.systemInfo.arch}
- **Node.js Version**: ${this.benchmarkData.systemInfo.nodeVersion}
- **CPU**: ${this.benchmarkData.systemInfo.cpuModel} (${this.benchmarkData.systemInfo.cpuCount} cores)
- **Memory**: ${(this.benchmarkData.systemInfo.totalMemory / 1024 / 1024 / 1024).toFixed(1)}GB
- **Project**: ${this.benchmarkData.systemInfo.projectInfo?.name || 'Unknown'} v${this.benchmarkData.systemInfo.projectInfo?.version || 'Unknown'}

## Performance Results

${stats.error ? `### ❌ Benchmark Failed
${stats.error}` : `
### 📊 Success Rate
- **Total Runs**: ${stats.runs.total}
- **Successful**: ${stats.runs.successful}
- **Failed**: ${stats.runs.failed}
- **Success Rate**: ${stats.runs.successRate.toFixed(1)}%

### ⏱️ Startup Time Analysis
- **Average**: ${(stats.startupTime.average / 1000).toFixed(2)}s
- **Minimum**: ${(stats.startupTime.min / 1000).toFixed(2)}s
- **Maximum**: ${(stats.startupTime.max / 1000).toFixed(2)}s
- **Median**: ${(stats.startupTime.median / 1000).toFixed(2)}s
- **Standard Deviation**: ${(stats.startupTime.standardDeviation / 1000).toFixed(2)}s

### 🧠 Memory Usage Analysis
- **Average**: ${(stats.memoryUsage.average / 1024 / 1024).toFixed(1)}MB
- **Minimum**: ${(stats.memoryUsage.min / 1024 / 1024).toFixed(1)}MB
- **Maximum**: ${(stats.memoryUsage.max / 1024 / 1024).toFixed(1)}MB
- **Median**: ${(stats.memoryUsage.median / 1024 / 1024).toFixed(1)}MB

### 🎯 Performance Scores
- **Average Score**: ${stats.performance.averageScore.toFixed(1)}/100
- **Best Score**: ${stats.performance.maxScore.toFixed(1)}/100
- **Worst Score**: ${stats.performance.minScore.toFixed(1)}/100
`}

## Benchmark Comparison

${comparisons.error ? `### ❌ No Comparison Data
${comparisons.error}` : `
### 📈 Performance Rating: ${comparisons.performanceRating.toUpperCase()}

### 🎯 Industry Benchmarks
- **Excellent**: < ${comparisons.benchmarks.excellent.startupTime / 1000}s startup, < ${comparisons.benchmarks.excellent.memoryUsage / 1024 / 1024}MB memory
- **Good**: < ${comparisons.benchmarks.good.startupTime / 1000}s startup, < ${comparisons.benchmarks.good.memoryUsage / 1024 / 1024}MB memory
- **Acceptable**: < ${comparisons.benchmarks.acceptable.startupTime / 1000}s startup, < ${comparisons.benchmarks.acceptable.memoryUsage / 1024 / 1024}MB memory

### 🔄 Consistency Score: ${comparisons.consistencyScore.toFixed(1)}%

${comparisons.baseline ? `### 📊 Baseline Comparison
- **Startup Time Change**: ${(comparisons.baseline.startupTimeChange / 1000).toFixed(2)}s ${comparisons.baseline.startupTimeChange >= 0 ? '(slower)' : '(faster)'}
- **Memory Usage Change**: ${(comparisons.baseline.memoryUsageChange / 1024 / 1024).toFixed(1)}MB ${comparisons.baseline.memoryUsageChange >= 0 ? '(more)' : '(less)'}
- **Performance Score Change**: ${comparisons.baseline.performanceScoreChange.toFixed(1)} points
` : '### 📊 No Baseline Available\nThis run will be saved as the new baseline for future comparisons.'}
`}

## Recommendations

${this.benchmarkData.recommendations.map((rec, i) => `
### ${i + 1}. [${rec.priority}] ${rec.category}
**Issue**: ${rec.issue}
**Solution**: ${rec.solution}
`).join('')}

## Individual Run Details

${this.benchmarkData.runs.map((run, i) => `
### Run ${run.runNumber} ${run.success ? '✅' : '❌'}
- **Status**: ${run.success ? 'SUCCESS' : 'FAILED'}
- **Duration**: ${run.totalDuration}ms
${run.success ? `- **Startup Time**: ${run.metrics.startupTime}ms
- **Overall Score**: ${run.metrics.overallScore.toFixed(1)}/100
- **Memory Efficiency**: ${run.metrics.memoryEfficiency.toFixed(1)}%
- **CPU Efficiency**: ${run.metrics.cpuEfficiency.toFixed(1)}%
- **Stability Score**: ${run.metrics.stabilityScore.toFixed(1)}%` : `- **Error**: ${run.error}`}
`).join('')}

## Performance Optimization Tips

1. **Startup Time Optimization**:
   - Implement code splitting and lazy loading
   - Optimize dependency tree and remove unused packages
   - Use faster build tools (Vite, esbuild)
   - Enable persistent caching

2. **Memory Optimization**:
   - Monitor for memory leaks during development
   - Optimize image and asset loading
   - Use React.memo and useMemo appropriately
   - Profile memory usage with Chrome DevTools

3. **Build Optimization**:
   - Enable production optimizations
   - Use tree shaking for unused code elimination
   - Optimize CSS and asset bundling
   - Configure webpack/bundler optimizations

4. **Development Experience**:
   - Use fast refresh for development
   - Optimize ESLint and TypeScript configurations
   - Use development-specific optimizations
   - Consider using development proxies

## Next Steps

1. Address high-priority recommendations
2. Run benchmarks regularly to track performance trends
3. Set up automated performance monitoring in CI/CD
4. Compare performance across different environments
5. Create performance budgets and alerts
`;

    await fs.writeFile(reportPath, report);
    console.log(`📋 Report saved to: ${reportPath}`);
  }
}

// CLI Interface
if (require.main === module) {
  const options = {
    runs: 5,
    warmupRuns: 2,
    verbose: process.argv.includes('--verbose') || process.argv.includes('-v'),
    saveResults: !process.argv.includes('--no-save')
  };
  
  // Parse command line options
  const runsArg = process.argv.find(arg => arg.startsWith('--runs='));
  if (runsArg) {
    options.runs = parseInt(runsArg.split('=')[1]);
  }
  
  const warmupArg = process.argv.find(arg => arg.startsWith('--warmup='));
  if (warmupArg) {
    options.warmupRuns = parseInt(warmupArg.split('=')[1]);
  }
  
  const benchmarker = new PerformanceBenchmarkingSystem(options);
  
  console.log('🏃 Starting Performance Benchmarking System');
  console.log(`📊 Configuration: ${options.runs} runs, ${options.warmupRuns} warmup runs`);
  
  // Enable garbage collection for more accurate memory measurements
  if (global.gc) {
    console.log('🗑️ Garbage collection enabled for accurate memory measurements');
  } else {
    console.log('⚠️ Run with --expose-gc for more accurate memory measurements');
  }
  
  benchmarker.runBenchmarks()
    .then(results => {
      console.log('\n🏁 Performance benchmarking completed successfully!');
      
      if (results.statistics && !results.statistics.error) {
        console.log(`📊 Average startup time: ${(results.statistics.startupTime.average / 1000).toFixed(1)}s`);
        console.log(`🎯 Performance rating: ${results.comparisons.performanceRating}`);
      }
      
      process.exit(0);
    })
    .catch(error => {
      console.error('\n💀 Performance benchmarking failed:');
      console.error(`❌ Error: ${error.message}`);
      process.exit(1);
    });
}

module.exports = PerformanceBenchmarkingSystem;