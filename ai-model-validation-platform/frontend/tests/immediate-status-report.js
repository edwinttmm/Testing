#!/usr/bin/env node

/**
 * Immediate TypeScript Status Report
 * Provides instant feedback without waiting for full compilation
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function log(message) {
  console.log(`[${new Date().toISOString()}] ${message}`);
}

function getErrorSample() {
  try {
    // Run a very limited type check to get error samples
    const result = execSync(
      'timeout 15s npx tsc --noEmit --skipLibCheck --pretty false 2>&1 || true', 
      { encoding: 'utf8' }
    );
    
    const errors = result.split('\n')
      .filter(line => line.includes('error TS'))
      .slice(0, 5); // First 5 errors only
    
    return {
      sampleErrors: errors,
      hasErrors: errors.length > 0,
      errorCount: errors.length >= 5 ? '5+' : errors.length
    };
  } catch (error) {
    return {
      sampleErrors: [],
      hasErrors: false,
      errorCount: 'unknown',
      checkFailed: true
    };
  }
}

function getLintSample() {
  try {
    const result = execSync('timeout 10s npm run lint:dev 2>&1 || true', { encoding: 'utf8' });
    
    const warnings = result.split('\n')
      .filter(line => line.includes('warning') || line.includes('✖'))
      .slice(0, 3); // First 3 warnings
    
    return {
      sampleWarnings: warnings,
      hasWarnings: warnings.length > 0,
      warningCount: warnings.length >= 3 ? '3+' : warnings.length
    };
  } catch (error) {
    return {
      sampleWarnings: [],
      hasWarnings: false,
      warningCount: 'unknown',
      checkFailed: true
    };
  }
}

function getFileStats() {
  try {
    const tsCount = execSync("find src -name '*.ts' | wc -l", { encoding: 'utf8' }).trim();
    const tsxCount = execSync("find src -name '*.tsx' | wc -l", { encoding: 'utf8' }).trim();
    
    return {
      tsFiles: parseInt(tsCount),
      tsxFiles: parseInt(tsxCount),
      totalFiles: parseInt(tsCount) + parseInt(tsxCount)
    };
  } catch (error) {
    return {
      tsFiles: 0,
      tsxFiles: 0,
      totalFiles: 0,
      error: error.message
    };
  }
}

async function generateImmediateReport() {
  log('🚀 Generating immediate TypeScript status report...');
  
  const fileStats = getFileStats();
  log(`📁 Found ${fileStats.totalFiles} TypeScript files (${fileStats.tsFiles} .ts, ${fileStats.tsxFiles} .tsx)`);
  
  const errorSample = getErrorSample();
  const lintSample = getLintSample();
  
  const report = {
    timestamp: new Date().toISOString(),
    fileStatistics: fileStats,
    typeScriptSample: errorSample,
    lintSample: lintSample,
    overallStatus: {
      hasTypeScriptErrors: errorSample.hasErrors,
      hasLintWarnings: lintSample.hasWarnings,
      quickStatus: errorSample.hasErrors ? 'NEEDS_ATTENTION' : 'GOOD'
    },
    agentRecommendations: generateAgentRecommendations(errorSample, lintSample, fileStats)
  };
  
  // Display report
  console.log('\n🎯 === IMMEDIATE TYPESCRIPT STATUS REPORT ===');
  console.log(`📊 Project: ${fileStats.totalFiles} TypeScript files`);
  console.log(`🔍 Type Errors: ${errorSample.errorCount} (sample)`);
  console.log(`⚠️  Lint Warnings: ${lintSample.warningCount} (sample)`);
  console.log(`📈 Status: ${report.overallStatus.quickStatus}`);
  
  if (errorSample.sampleErrors.length > 0) {
    console.log('\n🔥 Sample TypeScript Errors:');
    errorSample.sampleErrors.forEach((error, idx) => {
      console.log(`  ${idx + 1}. ${error.trim()}`);
    });
  }
  
  if (lintSample.sampleWarnings.length > 0) {
    console.log('\n⚠️  Sample Lint Warnings:');
    lintSample.sampleWarnings.forEach((warning, idx) => {
      console.log(`  ${idx + 1}. ${warning.trim()}`);
    });
  }
  
  console.log('\n💡 Agent Recommendations:');
  report.agentRecommendations.forEach((rec, idx) => {
    console.log(`  ${idx + 1}. ${rec}`);
  });
  
  console.log('===============================================\n');
  
  // Save for other processes
  fs.writeFileSync(
    path.join(__dirname, 'immediate-status.json'),
    JSON.stringify(report, null, 2)
  );
  
  return report;
}

function generateAgentRecommendations(errorSample, lintSample, fileStats) {
  const recommendations = [];
  
  if (errorSample.hasErrors) {
    recommendations.push('🔧 Focus on TypeScript error resolution - errors detected');
    recommendations.push('📝 Prioritize import/export issues and type definitions');
  } else {
    recommendations.push('✅ TypeScript errors under control - focus on warnings');
  }
  
  if (lintSample.hasWarnings) {
    recommendations.push('🧹 Address linting warnings for code quality');
  }
  
  if (fileStats.totalFiles > 200) {
    recommendations.push('🏗️  Large codebase - consider incremental fixes by component');
  }
  
  recommendations.push('⚡ Use real-time monitoring for immediate feedback');
  recommendations.push('🔄 Coordinate with other agents to prevent conflicts');
  
  return recommendations;
}

// Run immediately if called directly
if (require.main === module) {
  generateImmediateReport();
}

module.exports = { generateImmediateReport };