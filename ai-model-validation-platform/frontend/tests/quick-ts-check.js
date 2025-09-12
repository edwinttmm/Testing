#!/usr/bin/env node

/**
 * Quick TypeScript Status Check
 * Fast assessment without full compilation
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class QuickTSCheck {
  constructor() {
    this.srcPath = path.join(process.cwd(), 'src');
  }

  log(message) {
    console.log(`[${new Date().toISOString()}] ${message}`);
  }

  quickSyntaxCheck() {
    try {
      // Quick syntax validation without full type checking
      const result = execSync('tsc --noEmit --skipLibCheck --pretty false src/**/*.{ts,tsx} 2>&1 || true', { 
        encoding: 'utf8',
        timeout: 30000 // 30 second timeout
      });
      
      const errors = result.split('\n').filter(line => 
        line.includes('error TS') && !line.trim() === ''
      );
      
      return {
        success: errors.length === 0,
        errorCount: errors.length,
        errors: errors.slice(0, 10), // Show first 10 errors
        output: result
      };
    } catch (error) {
      return {
        success: false,
        errorCount: -1,
        errors: ['Syntax check failed: ' + error.message],
        output: error.message
      };
    }
  }

  countFiles() {
    const count = { ts: 0, tsx: 0, total: 0 };
    
    const countInDir = (dir) => {
      try {
        const files = fs.readdirSync(dir, { withFileTypes: true });
        
        for (const file of files) {
          const fullPath = path.join(dir, file.name);
          
          if (file.isDirectory() && !file.name.startsWith('.')) {
            countInDir(fullPath);
          } else if (file.isFile()) {
            if (file.name.endsWith('.ts')) {
              count.ts++;
              count.total++;
            } else if (file.name.endsWith('.tsx')) {
              count.tsx++;
              count.total++;
            }
          }
        }
      } catch (error) {
        // Skip directories we can't read
      }
    };
    
    countInDir(this.srcPath);
    return count;
  }

  async runQuickCheck() {
    this.log('Running quick TypeScript check...');
    
    const fileCount = this.countFiles();
    this.log(`Found ${fileCount.total} TypeScript files (${fileCount.ts} .ts, ${fileCount.tsx} .tsx)`);
    
    const syntaxCheck = this.quickSyntaxCheck();
    
    const report = {
      timestamp: new Date().toISOString(),
      fileCount: fileCount,
      syntaxCheck: syntaxCheck,
      status: syntaxCheck.success ? 'PASS' : 'FAIL'
    };
    
    this.log(`Quick check result: ${report.status}`);
    this.log(`Error count: ${syntaxCheck.errorCount}`);
    
    if (syntaxCheck.errors.length > 0) {
      this.log('Sample errors:');
      syntaxCheck.errors.forEach((error, index) => {
        this.log(`  ${index + 1}. ${error}`);
      });
    }
    
    // Save results
    fs.writeFileSync(
      path.join(__dirname, 'quick-ts-check-results.json'),
      JSON.stringify(report, null, 2)
    );
    
    return report;
  }
}

// CLI interface
if (require.main === module) {
  const checker = new QuickTSCheck();
  checker.runQuickCheck();
}

module.exports = QuickTSCheck;