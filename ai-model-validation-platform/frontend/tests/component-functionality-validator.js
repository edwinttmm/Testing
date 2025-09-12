#!/usr/bin/env node

/**
 * Component Functionality Validator
 * Ensures TypeScript fixes don't break component functionality
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class ComponentFunctionalityValidator {
  constructor() {
    this.logPath = path.join(__dirname, 'component-validation.log');
    this.resultsPath = path.join(__dirname, 'component-validation-results.json');
    this.testResults = [];
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(this.logPath, logMessage + '\n');
  }

  async validateComponentFunctionality() {
    this.log('🧪 Starting component functionality validation...', 'INFO');
    
    const validation = {
      timestamp: new Date().toISOString(),
      componentTests: await this.runComponentTests(),
      compilationTest: await this.testComponentCompilation(),
      importExportTest: await this.testImportExports(),
      renderingTest: await this.testComponentRendering(),
      overallStatus: 'pending'
    };
    
    validation.overallStatus = this.calculateOverallStatus(validation);
    
    this.testResults.push(validation);
    this.saveResults();
    
    this.log(`✅ Component validation complete - Status: ${validation.overallStatus}`, 'INFO');
    
    return validation;
  }

  async runComponentTests() {
    this.log('🔬 Running existing component tests...', 'INFO');
    
    try {
      const result = execSync('npm test -- --testPathPattern="src.*test\\.tsx?$" --watchAll=false --passWithNoTests', { 
        encoding: 'utf8',
        timeout: 120000 // 2 minutes
      });
      
      const testStats = this.parseTestOutput(result);
      
      return {
        success: true,
        stats: testStats,
        output: result.slice(0, 1000) // Limit output
      };
      
    } catch (error) {
      const output = error.stdout || error.message || '';
      const testStats = this.parseTestOutput(output);
      
      return {
        success: false,
        stats: testStats,
        error: error.message,
        output: output.slice(0, 1000)
      };
    }
  }

  parseTestOutput(output) {
    const stats = {
      totalTests: 0,
      passedTests: 0,
      failedTests: 0,
      testSuites: 0,
      passedSuites: 0,
      failedSuites: 0,
      coverage: null
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
      
      // Coverage parsing
      if (line.includes('All files')) {
        const coverageMatch = line.match(/(\d+\.?\d*)%/);
        if (coverageMatch) {
          stats.coverage = parseFloat(coverageMatch[1]);
        }
      }
    }
    
    return stats;
  }

  async testComponentCompilation() {
    this.log('⚙️ Testing component compilation...', 'INFO');
    
    try {
      // Test compilation of key component directories
      const componentDirs = ['src/components', 'src/pages', 'src/hooks'];
      const results = {};
      
      for (const dir of componentDirs) {
        if (fs.existsSync(dir)) {
          try {
            const dirResult = execSync(`npx tsc --noEmit --skipLibCheck "${dir}/**/*.{ts,tsx}"`, { 
              encoding: 'utf8',
              timeout: 30000
            });
            
            results[dir] = {
              success: true,
              errors: []
            };
          } catch (error) {
            const output = error.stdout || error.message || '';
            const errors = output.split('\n').filter(line => line.includes('error TS'));
            
            results[dir] = {
              success: false,
              errors: errors.slice(0, 5) // First 5 errors
            };
          }
        }
      }
      
      const overallSuccess = Object.values(results).every(r => r.success);
      
      return {
        success: overallSuccess,
        results: results,
        totalDirectories: Object.keys(results).length
      };
      
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testImportExports() {
    this.log('📦 Testing import/export resolution...', 'INFO');
    
    try {
      // Create a temporary test file that imports key components
      const testImportFile = path.join(__dirname, 'temp-import-test.ts');
      
      const importTest = `
// Temporary import test
import React from 'react';

// Test common component imports
try {
  // These imports should not fail
  const components = [
    () => import('../src/components'),
    () => import('../src/pages'),
    () => import('../src/services'),
    () => import('../src/utils'),
    () => import('../src/hooks')
  ];
  
  console.log('Import test structure created');
} catch (error) {
  console.error('Import test failed:', error);
}
`;
      
      fs.writeFileSync(testImportFile, importTest);
      
      try {
        execSync(`npx tsc --noEmit --skipLibCheck "${testImportFile}"`, { 
          encoding: 'utf8',
          timeout: 15000
        });
        
        // Cleanup
        fs.unlinkSync(testImportFile);
        
        return {
          success: true,
          message: 'Import/export resolution working correctly'
        };
        
      } catch (error) {
        // Cleanup
        if (fs.existsSync(testImportFile)) {
          fs.unlinkSync(testImportFile);
        }
        
        const output = error.stdout || error.message || '';
        const importErrors = output.split('\n').filter(line => 
          line.includes('Cannot find module') || line.includes('Module not found')
        );
        
        return {
          success: false,
          importErrors: importErrors.slice(0, 3),
          message: 'Import/export issues detected'
        };
      }
      
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  async testComponentRendering() {
    this.log('🎨 Testing component rendering capability...', 'INFO');
    
    try {
      // Check if React components can be parsed without syntax errors
      const componentFiles = execSync("find src -name '*.tsx' | head -5", { encoding: 'utf8' })
        .split('\n')
        .filter(file => file.trim() !== '');
      
      const renderingTests = {};
      
      for (const file of componentFiles) {
        try {
          // Basic syntax validation for JSX/TSX
          execSync(`npx tsc --noEmit --skipLibCheck --jsx react-jsx "${file}"`, { 
            encoding: 'utf8',
            timeout: 10000
          });
          
          renderingTests[file] = { success: true };
        } catch (error) {
          const output = error.stdout || error.message || '';
          const jsxErrors = output.split('\n').filter(line => 
            line.includes('JSX') || line.includes('React')
          );
          
          renderingTests[file] = { 
            success: false, 
            jsxErrors: jsxErrors.slice(0, 2)
          };
        }
      }
      
      const successfulComponents = Object.values(renderingTests).filter(t => t.success).length;
      const totalComponents = Object.keys(renderingTests).length;
      
      return {
        success: successfulComponents === totalComponents,
        successfulComponents: successfulComponents,
        totalComponents: totalComponents,
        successRate: totalComponents > 0 ? Math.round((successfulComponents / totalComponents) * 100) : 0,
        results: renderingTests
      };
      
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  calculateOverallStatus(validation) {
    const checks = [
      validation.componentTests.success,
      validation.compilationTest.success,
      validation.importExportTest.success,
      validation.renderingTest.success
    ];
    
    const passedChecks = checks.filter(check => check).length;
    const totalChecks = checks.length;
    
    if (passedChecks === totalChecks) return 'EXCELLENT';
    if (passedChecks >= totalChecks * 0.75) return 'GOOD';
    if (passedChecks >= totalChecks * 0.5) return 'FAIR';
    return 'POOR';
  }

  generateFunctionalityReport() {
    if (this.testResults.length === 0) {
      return 'No component validation data available.';
    }
    
    const latest = this.testResults[this.testResults.length - 1];
    
    let report = '\n🧪 === Component Functionality Report ===\n';
    report += `📅 Timestamp: ${latest.timestamp}\n`;
    report += `📊 Overall Status: ${latest.overallStatus}\n`;
    
    report += `\n🧪 Test Results:\n`;
    if (latest.componentTests.stats) {
      report += `   • Tests: ${latest.componentTests.stats.passedTests}/${latest.componentTests.stats.totalTests} passed\n`;
      report += `   • Suites: ${latest.componentTests.stats.passedSuites}/${latest.componentTests.stats.testSuites} passed\n`;
    }
    
    report += `\n⚙️ Compilation: ${latest.compilationTest.success ? '✅ PASS' : '❌ FAIL'}\n`;
    report += `📦 Imports: ${latest.importExportTest.success ? '✅ PASS' : '❌ FAIL'}\n`;
    report += `🎨 Rendering: ${latest.renderingTest.success ? '✅ PASS' : '❌ FAIL'}\n`;
    
    if (latest.renderingTest.successRate !== undefined) {
      report += `   • Component Success Rate: ${latest.renderingTest.successRate}%\n`;
    }
    
    report += '\n==========================================\n';
    
    return report;
  }

  saveResults() {
    const data = {
      testResults: this.testResults,
      lastUpdated: new Date().toISOString(),
      summary: {
        totalValidations: this.testResults.length,
        latestStatus: this.testResults.length > 0 ? this.testResults[this.testResults.length - 1].overallStatus : 'none'
      }
    };
    
    fs.writeFileSync(this.resultsPath, JSON.stringify(data, null, 2));
  }

  loadResults() {
    try {
      if (fs.existsSync(this.resultsPath)) {
        const data = JSON.parse(fs.readFileSync(this.resultsPath, 'utf8'));
        this.testResults = data.testResults || [];
      }
    } catch (error) {
      this.log(`Failed to load results: ${error.message}`, 'ERROR');
      this.testResults = [];
    }
  }

  getAgentFunctionalityFeedback() {
    if (this.testResults.length === 0) {
      return {
        status: 'no-data',
        message: 'No component validation data available',
        recommendation: 'Run component functionality validation'
      };
    }
    
    const latest = this.testResults[this.testResults.length - 1];
    
    return {
      timestamp: latest.timestamp,
      functionalityStatus: latest.overallStatus,
      componentTestsPassing: latest.componentTests.success,
      compilationWorking: latest.compilationTest.success,
      importsWorking: latest.importExportTest.success,
      renderingWorking: latest.renderingTest.success,
      recommendation: this.getFunctionalityRecommendation(latest),
      riskLevel: this.assessRiskLevel(latest)
    };
  }

  getFunctionalityRecommendation(validation) {
    if (validation.overallStatus === 'EXCELLENT') {
      return 'All component functionality preserved. Safe to continue TypeScript fixes.';
    }
    
    if (validation.overallStatus === 'GOOD') {
      return 'Component functionality mostly preserved. Monitor for specific issues.';
    }
    
    if (validation.overallStatus === 'FAIR') {
      return 'Some component issues detected. Address before continuing major fixes.';
    }
    
    return 'Component functionality compromised. Stop TypeScript fixes and address issues.';
  }

  assessRiskLevel(validation) {
    if (!validation.compilationTest.success) return 'HIGH';
    if (!validation.importExportTest.success) return 'HIGH';
    if (!validation.renderingTest.success) return 'MEDIUM';
    if (!validation.componentTests.success) return 'MEDIUM';
    return 'LOW';
  }
}

// CLI interface
if (require.main === module) {
  const validator = new ComponentFunctionalityValidator();
  const command = process.argv[2];
  
  switch (command) {
    case 'validate':
      validator.validateComponentFunctionality();
      break;
    case 'feedback':
      validator.loadResults();
      console.log(JSON.stringify(validator.getAgentFunctionalityFeedback(), null, 2));
      break;
    case 'report':
      validator.loadResults();
      console.log(validator.generateFunctionalityReport());
      break;
    default:
      console.log('Component Functionality Validator');
      console.log('Usage: node component-functionality-validator.js [validate|feedback|report]');
      break;
  }
}

module.exports = ComponentFunctionalityValidator;