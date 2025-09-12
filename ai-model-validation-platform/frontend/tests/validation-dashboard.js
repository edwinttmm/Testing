#!/usr/bin/env node

/**
 * TypeScript Validation Dashboard
 * Provides real-time dashboard for TypeScript validation progress
 */

const fs = require('fs');
const path = require('path');

class ValidationDashboard {
  constructor() {
    this.memoryStorePath = path.join(__dirname, '..', 'memory', 'typescript-test-results.json');
    this.progressMemoryPath = path.join(__dirname, '..', 'memory', 'typescript-fixes-progress.json');
  }

  loadValidationResults() {
    if (!fs.existsSync(this.memoryStorePath)) {
      return null;
    }
    
    try {
      return JSON.parse(fs.readFileSync(this.memoryStorePath, 'utf8'));
    } catch (error) {
      console.error('❌ Error loading validation results:', error.message);
      return null;
    }
  }

  loadProgressData() {
    if (!fs.existsSync(this.progressMemoryPath)) {
      return null;
    }
    
    try {
      return JSON.parse(fs.readFileSync(this.progressMemoryPath, 'utf8'));
    } catch (error) {
      return null;
    }
  }

  displayDashboard() {
    console.clear();
    console.log('╭─────────────────────────────────────────────────────────────╮');
    console.log('│           🧪 TypeScript Validation Dashboard                │');
    console.log('├─────────────────────────────────────────────────────────────┤');
    
    const results = this.loadValidationResults();
    const progress = this.loadProgressData();
    
    if (!results) {
      console.log('│ ⚠️  No validation data available yet                        │');
      console.log('╰─────────────────────────────────────────────────────────────╯');
      return;
    }
    
    const { baseline, summary, latestValidation } = results;
    
    // Baseline Info
    console.log('│ 📊 BASELINE METRICS:                                        │');
    if (baseline) {
      console.log(`│    Initial Errors: ${baseline.errors.toString().padEnd(37)} │`);
      console.log(`│    Established: ${baseline.timestamp.substring(0, 19).padEnd(40)} │`);
    }
    console.log('├─────────────────────────────────────────────────────────────┤');
    
    // Current Status
    console.log('│ 🎯 CURRENT STATUS:                                          │');
    console.log(`│    Current Errors: ${summary.currentErrors.toString().padEnd(37)} │`);
    console.log(`│    Total Fixed: ${summary.totalImprovement.toString().padEnd(40)} │`);
    console.log(`│    Validations Run: ${summary.totalValidations.toString().padEnd(36)} │`);
    
    // Progress Indicator
    if (baseline && baseline.errors > 0) {
      const progressPercent = Math.round((summary.totalImprovement / baseline.errors) * 100);
      const progressBar = '█'.repeat(Math.floor(progressPercent / 5)) + 
                         '░'.repeat(20 - Math.floor(progressPercent / 5));
      console.log(`│    Progress: [${progressBar}] ${progressPercent}%${' '.repeat(10 - progressPercent.toString().length)} │`);
    }
    
    console.log('├─────────────────────────────────────────────────────────────┤');
    
    // Latest Validation
    if (latestValidation) {
      console.log('│ 🔍 LATEST VALIDATION:                                       │');
      console.log(`│    Status: ${latestValidation.status.padEnd(45)} │`);
      console.log(`│    Time: ${latestValidation.timestamp.substring(11, 19).padEnd(47)} │`);
      
      if (latestValidation.improvement !== undefined) {
        const improvementText = latestValidation.improvement > 0 ? 
          `+${latestValidation.improvement} fixed` : 
          latestValidation.improvement < 0 ? 
          `${latestValidation.improvement} new errors` : 
          'no change';
        console.log(`│    Change: ${improvementText.padEnd(44)} │`);
      }
    }
    
    console.log('├─────────────────────────────────────────────────────────────┤');
    
    // Progress Updates
    if (progress) {
      console.log('│ 📝 RECENT CODER UPDATES:                                    │');
      const updates = Object.entries(progress).slice(-3);
      updates.forEach(([timestamp, update]) => {
        const time = timestamp.substring(11, 19);
        const message = update.message || 'Progress update';
        const truncatedMessage = message.length > 35 ? 
          message.substring(0, 32) + '...' : 
          message;
        console.log(`│    ${time} - ${truncatedMessage.padEnd(38)} │`);
      });
    }
    
    console.log('├─────────────────────────────────────────────────────────────┤');
    
    // Target Achievement
    if (summary.currentErrors === 0) {
      console.log('│ 🎉 TARGET ACHIEVED: Zero TypeScript errors!                 │');
    } else {
      console.log(`│ 🎯 TARGET: ${summary.currentErrors} errors remaining to fix${''.padEnd(18)} │`);
    }
    
    console.log('╰─────────────────────────────────────────────────────────────╯');
    console.log(`Last updated: ${new Date().toISOString().substring(11, 19)}`);
  }

  startRealtimeDashboard() {
    console.log('🚀 Starting real-time TypeScript validation dashboard...');
    
    // Initial display
    this.displayDashboard();
    
    // Update every 5 seconds
    setInterval(() => {
      this.displayDashboard();
    }, 5000);
  }
}

// CLI Interface
if (require.main === module) {
  const dashboard = new ValidationDashboard();
  
  const command = process.argv[2];
  
  switch (command) {
    case 'show':
      dashboard.displayDashboard();
      break;
      
    case 'watch':
      dashboard.startRealtimeDashboard();
      break;
      
    default:
      console.log('Usage: node validation-dashboard.js [show|watch]');
      break;
  }
}

module.exports = ValidationDashboard;