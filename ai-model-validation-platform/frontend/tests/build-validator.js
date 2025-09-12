#!/usr/bin/env node

/**
 * Build Validation System
 * Validates builds, tracks performance, and ensures component functionality
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class BuildValidator {
  constructor() {
    this.resultsPath = path.join(__dirname, 'build-validation-results.json');
    this.logPath = path.join(__dirname, 'build-validation.log');
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}\n`;
    
    console.log(logMessage.trim());
    fs.appendFileSync(this.logPath, logMessage);
  }

  async validateBuild() {
    this.log('Starting build validation...', 'INFO');
    
    const results = {
      timestamp: new Date().toISOString(),
      typeCheck: await this.runTypeCheck(),
      linting: await this.runLinting(),
      build: await this.runBuild(),
      tests: await this.runTests(),
      bundleAnalysis: await this.analyzeBundleSize()
    };
    
    results.overall = this.calculateOverallStatus(results);
    
    this.saveResults(results);
    this.logResults(results);
    
    return results;
  }

  async runTypeCheck() {
    const startTime = Date.now();
    try {
      const output = execSync('npm run typecheck', { 
        encoding: 'utf8',
        timeout: 120000
      });
      
      return {
        success: true,
        duration: Date.now() - startTime,
        errors: [],
        output: output.trim()
      };
    } catch (error) {
      const output = error.stdout || error.message;
      const errorLines = output.split('\n').filter(line => 
        line.includes('error TS')
      );
      
      return {
        success: false,
        duration: Date.now() - startTime,
        errors: errorLines,
        errorCount: errorLines.length,
        output: output
      };
    }
  }

  async runLinting() {
    const startTime = Date.now();
    try {
      const output = execSync('npm run lint:prod', { 
        encoding: 'utf8',
        timeout: 60000
      });
      
      return {
        success: true,
        duration: Date.now() - startTime,
        warnings: [],
        output: output.trim()
      };
    } catch (error) {
      const output = error.stdout || error.message;
      const warningLines = output.split('\n').filter(line => 
        line.includes('warning') || line.includes('✖')
      );
      
      return {
        success: false,
        duration: Date.now() - startTime,
        warnings: warningLines,
        warningCount: warningLines.length,
        output: output
      };
    }
  }

  async runBuild() {
    const startTime = Date.now();
    try {
      // Clean build directory first
      if (fs.existsSync('build')) {
        fs.rmSync('build', { recursive: true, force: true });
      }
      
      const output = execSync('npm run build', { 
        encoding: 'utf8',
        timeout: 300000 // 5 minutes
      });
      
      const buildStats = this.analyzeBuildOutput(output);
      
      return {
        success: true,
        duration: Date.now() - startTime,
        output: output.trim(),
        stats: buildStats
      };
    } catch (error) {
      const output = error.stdout || error.message;
      
      return {
        success: false,
        duration: Date.now() - startTime,
        error: error.message,
        output: output
      };
    }
  }

  async runTests() {
    const startTime = Date.now();
    try {
      const output = execSync('npm test -- --watchAll=false --coverage=false', { 
        encoding: 'utf8',
        timeout: 180000 // 3 minutes
      });
      
      const testStats = this.parseTestResults(output);
      
      return {
        success: true,
        duration: Date.now() - startTime,
        stats: testStats,
        output: output.trim()
      };
    } catch (error) {
      const output = error.stdout || error.message;
      const testStats = this.parseTestResults(output);
      
      return {
        success: false,
        duration: Date.now() - startTime,
        error: error.message,
        stats: testStats,
        output: output
      };
    }
  }

  analyzeBuildOutput(output) {
    const stats = {
      fileCount: 0,
      totalSize: 0,
      jsSize: 0,
      cssSize: 0,
      chunks: []
    };
    
    // Parse webpack build output
    const lines = output.split('\n');
    
    for (const line of lines) {
      if (line.includes('static/js/') || line.includes('static/css/')) {
        const sizeMatch = line.match(/(\d+\.?\d*)\s*(\w+)/);
        if (sizeMatch) {
          const size = parseFloat(sizeMatch[1]);
          const unit = sizeMatch[2];
          let sizeInBytes = size;
          
          if (unit === 'kB' || unit === 'KB') sizeInBytes *= 1024;
          if (unit === 'MB') sizeInBytes *= 1024 * 1024;
          
          stats.totalSize += sizeInBytes;
          stats.fileCount++;
          
          if (line.includes('static/js/')) {
            stats.jsSize += sizeInBytes;
          } else if (line.includes('static/css/')) {
            stats.cssSize += sizeInBytes;
          }
          
          stats.chunks.push({
            file: line.split(/\s+/)[1],
            size: sizeInBytes,
            type: line.includes('static/js/') ? 'js' : 'css'
          });
        }
      }
    }
    
    return stats;
  }

  parseTestResults(output) {
    const stats = {
      totalTests: 0,
      passedTests: 0,
      failedTests: 0,
      testSuites: 0,
      passedSuites: 0,
      failedSuites: 0
    };
    
    const lines = output.split('\n');
    
    for (const line of lines) {
      if (line.includes('Test Suites:')) {
        const match = line.match(/(\d+) passed.*?(\d+) total/);
        if (match) {
          stats.passedSuites = parseInt(match[1]);
          stats.testSuites = parseInt(match[2]);
          stats.failedSuites = stats.testSuites - stats.passedSuites;
        }
      }
      
      if (line.includes('Tests:')) {
        const match = line.match(/(\d+) passed.*?(\d+) total/);
        if (match) {
          stats.passedTests = parseInt(match[1]);
          stats.totalTests = parseInt(match[2]);
          stats.failedTests = stats.totalTests - stats.passedTests;
        }
      }
    }
    
    return stats;
  }

  async analyzeBundleSize() {
    try {
      const buildPath = path.join(process.cwd(), 'build');
      if (!fs.existsSync(buildPath)) {
        return { error: 'Build directory not found' };
      }
      
      const staticPath = path.join(buildPath, 'static');
      const analysis = {
        totalSize: 0,
        fileCount: 0,
        largestFiles: [],
        sizeByType: {
          js: 0,
          css: 0,
          other: 0
        }
      };
      
      const scanDirectory = (dir) => {
        const files = fs.readdirSync(dir, { withFileTypes: true });
        
        for (const file of files) {
          const fullPath = path.join(dir, file.name);
          
          if (file.isDirectory()) {
            scanDirectory(fullPath);
          } else {
            const stats = fs.statSync(fullPath);
            const relativePath = path.relative(buildPath, fullPath);
            
            analysis.totalSize += stats.size;
            analysis.fileCount++;
            
            const ext = path.extname(file.name).toLowerCase();
            if (ext === '.js') {
              analysis.sizeByType.js += stats.size;
            } else if (ext === '.css') {
              analysis.sizeByType.css += stats.size;
            } else {
              analysis.sizeByType.other += stats.size;
            }
            
            analysis.largestFiles.push({
              path: relativePath,
              size: stats.size
            });
          }
        }
      };
      
      if (fs.existsSync(staticPath)) {
        scanDirectory(staticPath);
      }
      
      // Sort by size and keep top 10
      analysis.largestFiles.sort((a, b) => b.size - a.size);
      analysis.largestFiles = analysis.largestFiles.slice(0, 10);
      
      return analysis;
    } catch (error) {
      return { error: error.message };
    }
  }

  calculateOverallStatus(results) {
    const issues = [];
    
    if (!results.typeCheck.success) {
      issues.push(`TypeScript errors: ${results.typeCheck.errorCount || 0}`);
    }
    
    if (!results.linting.success) {
      issues.push(`Linting warnings: ${results.linting.warningCount || 0}`);
    }
    
    if (!results.build.success) {
      issues.push('Build failed');
    }
    
    if (!results.tests.success) {
      issues.push(`Test failures: ${results.tests.stats?.failedTests || 0}`);
    }
    
    return {
      success: issues.length === 0,
      issues: issues,
      score: this.calculateHealthScore(results)
    };
  }

  calculateHealthScore(results) {
    let score = 100;
    
    // TypeScript errors penalty
    if (!results.typeCheck.success) {
      score -= Math.min(50, results.typeCheck.errorCount * 2);
    }
    
    // Linting warnings penalty
    if (!results.linting.success) {
      score -= Math.min(30, results.linting.warningCount * 0.5);
    }
    
    // Build failure penalty
    if (!results.build.success) {
      score -= 40;
    }
    
    // Test failure penalty
    if (!results.tests.success && results.tests.stats) {
      score -= results.tests.stats.failedTests * 5;
    }
    
    return Math.max(0, Math.round(score));
  }

  saveResults(results) {
    fs.writeFileSync(this.resultsPath, JSON.stringify(results, null, 2));
  }

  logResults(results) {
    this.log('\n=== Build Validation Results ===', 'REPORT');
    this.log(`Overall Status: ${results.overall.success ? '✅ PASS' : '❌ FAIL'}`, 'REPORT');
    this.log(`Health Score: ${results.overall.score}/100`, 'REPORT');
    
    if (results.overall.issues.length > 0) {
      this.log('Issues:', 'REPORT');
      results.overall.issues.forEach(issue => {
        this.log(`  - ${issue}`, 'REPORT');
      });
    }
    
    this.log(`TypeScript: ${results.typeCheck.success ? '✅' : '❌'} (${results.typeCheck.duration}ms)`, 'REPORT');
    this.log(`Linting: ${results.linting.success ? '✅' : '❌'} (${results.linting.duration}ms)`, 'REPORT');
    this.log(`Build: ${results.build.success ? '✅' : '❌'} (${results.build.duration}ms)`, 'REPORT');
    this.log(`Tests: ${results.tests.success ? '✅' : '❌'} (${results.tests.duration}ms)`, 'REPORT');
    
    if (results.bundleAnalysis && !results.bundleAnalysis.error) {
      const totalSizeMB = (results.bundleAnalysis.totalSize / (1024 * 1024)).toFixed(2);
      this.log(`Bundle Size: ${totalSizeMB}MB (${results.bundleAnalysis.fileCount} files)`, 'REPORT');
    }
    
    this.log('=================================\n', 'REPORT');
  }

  getValidationSummary() {
    try {
      if (fs.existsSync(this.resultsPath)) {
        return JSON.parse(fs.readFileSync(this.resultsPath, 'utf8'));
      }
    } catch (error) {
      this.log(`Error loading results: ${error.message}`, 'ERROR');
    }
    
    return null;
  }
}

// CLI interface
if (require.main === module) {
  const validator = new BuildValidator();
  const command = process.argv[2];
  
  switch (command) {
    case 'validate':
      validator.validateBuild();
      break;
    case 'summary':
      const summary = validator.getValidationSummary();
      if (summary) {
        console.log(JSON.stringify(summary, null, 2));
      } else {
        console.log('No validation results found. Run validation first.');
      }
      break;
    default:
      console.log('Usage: node build-validator.js [validate|summary]');
      break;
  }
}

module.exports = BuildValidator;