#!/usr/bin/env node

/**
 * Custom ESLint rule checker for logger vs console usage
 * Scans TypeScript files to recommend logger usage over console statements
 */

const fs = require('fs');
const path = require('path');

const COLORS = {
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  reset: '\x1b[0m'
};

function log(color, message) {
  console.log(`${COLORS[color]}${message}${COLORS.reset}`);
}

function scanDirectory(dir, results = { console: [], logger: [], total: 0 }) {
  const files = fs.readdirSync(dir);
  
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory() && !file.includes('node_modules') && !file.includes('.git')) {
      scanDirectory(filePath, results);
    } else if (file.endsWith('.ts') || file.endsWith('.tsx')) {
      results.total++;
      scanFile(filePath, results);
    }
  });
  
  return results;
}

function scanFile(filePath, results) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');
  
  lines.forEach((line, index) => {
    const trimmed = line.trim();
    
    // Check for console usage (excluding allowed ones)
    if (trimmed.includes('console.') && 
        !trimmed.includes('console.error') && 
        !trimmed.includes('console.warn') &&
        !trimmed.includes('// eslint-disable') &&
        !trimmed.startsWith('//')) {
      
      results.console.push({
        file: filePath,
        line: index + 1,
        content: trimmed,
        suggestion: getLoggerSuggestion(trimmed)
      });
    }
    
    // Check for logger usage
    if (trimmed.includes('logger.') || trimmed.includes('Logger.')) {
      results.logger.push({
        file: filePath,
        line: index + 1,
        content: trimmed
      });
    }
  });
}

function getLoggerSuggestion(consoleLine) {
  if (consoleLine.includes('console.log(')) {
    return consoleLine.replace('console.log(', 'logger.info(');
  } else if (consoleLine.includes('console.debug(')) {
    return consoleLine.replace('console.debug(', 'logger.debug(');
  } else if (consoleLine.includes('console.info(')) {
    return consoleLine.replace('console.info(', 'logger.info(');
  } else if (consoleLine.includes('console.trace(')) {
    return consoleLine.replace('console.trace(', 'logger.trace(');
  }
  return consoleLine.replace('console.', 'logger.');
}

function generateReport(results) {
  log('blue', '\n=== ESLint Logger Usage Report ===');
  log('green', `Files scanned: ${results.total}`);
  log('yellow', `Console statements found: ${results.console.length}`);
  log('green', `Logger statements found: ${results.logger.length}`);
  
  if (results.console.length > 0) {
    log('yellow', '\n--- Console statements to replace ---');
    results.console.forEach(item => {
      log('red', `${item.file}:${item.line}`);
      console.log(`  Current: ${item.content}`);
      console.log(`  Suggest: ${item.suggestion}\n`);
    });
  }
  
  if (results.logger.length > 0) {
    log('green', '\n--- Good logger usage found ---');
    results.logger.slice(0, 5).forEach(item => {
      log('green', `${item.file}:${item.line} - ${item.content}`);
    });
    if (results.logger.length > 5) {
      log('green', `... and ${results.logger.length - 5} more`);
    }
  }
  
  // Generate score
  const score = results.logger.length / (results.console.length + results.logger.length + 1) * 100;
  log('blue', `\nLogger adoption score: ${score.toFixed(1)}%`);
  
  if (score < 70) {
    log('yellow', 'Recommendation: Consider using logger more consistently');
  } else {
    log('green', 'Good job using logger consistently!');
  }
}

// Run the analysis
const srcDir = path.join(__dirname, '../src');
if (fs.existsSync(srcDir)) {
  const results = scanDirectory(srcDir);
  generateReport(results);
} else {
  log('red', 'Error: src directory not found');
  process.exit(1);
}