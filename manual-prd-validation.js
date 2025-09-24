const { chromium } = require('playwright');

async function validatePRDCompliance() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  const results = {
    timestamp: new Date().toISOString(),
    frontend_status: 'unknown',
    module_1_data_management: {
      score: 0,
      max_score: 10,
      findings: []
    },
    module_2_project_management: {
      score: 0,
      max_score: 10,
      findings: []
    },
    module_3_hil_test_execution: {
      score: 0,
      max_score: 10,
      findings: []
    },
    module_4_analysis_reporting: {
      score: 0,
      max_score: 10,
      findings: []
    },
    console_errors: [],
    network_failures: [],
    performance_metrics: {}
  };

  // Monitor errors
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      results.console_errors.push({
        timestamp: new Date().toISOString(),
        message: msg.text(),
        location: msg.location()
      });
    }
  });

  page.on('requestfailed', (request) => {
    results.network_failures.push({
      timestamp: new Date().toISOString(),
      url: request.url(),
      method: request.method(),
      error: request.failure()?.errorText
    });
  });

  try {
    console.log('🚀 Starting PRD compliance validation...');
    
    // Navigate to frontend
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    results.frontend_status = 'accessible';
    console.log('✅ Frontend accessible');

    // Get performance metrics
    const perfMetrics = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      return {
        load_time: nav.loadEventEnd - nav.loadEventStart,
        dom_content_loaded: nav.domContentLoadedEventEnd - nav.domContentLoadedEventStart,
        first_paint: nav.responseEnd - nav.requestStart
      };
    });
    results.performance_metrics = perfMetrics;

    // MODULE 1: Data Management & Ground Truth
    console.log('\n📋 Testing Module 1: Data Management & Ground Truth');
    
    // Check for video upload interface
    const uploadElements = await page.$$('input[type="file"], .upload-area, [data-testid*="upload"]');
    if (uploadElements.length > 0) {
      results.module_1_data_management.score += 2;
      results.module_1_data_management.findings.push('✅ Video upload interface found');
    } else {
      results.module_1_data_management.findings.push('❌ Video upload interface not found');
    }

    // Check for video formats support
    try {
      const fileInput = await page.$('input[type="file"]');
      if (fileInput) {
        const accept = await fileInput.getAttribute('accept');
        if (accept && (accept.includes('.mp4') || accept.includes('video/'))) {
          results.module_1_data_management.score += 1;
          results.module_1_data_management.findings.push('✅ Video format support detected');
        }
      }
    } catch (e) {}

    // Check for annotation interface
    const annotationElements = await page.$$('.video-viewport, .annotation-area, .bounding-box, [data-testid*="annotation"]');
    if (annotationElements.length > 0) {
      results.module_1_data_management.score += 2;
      results.module_1_data_management.findings.push('✅ Annotation interface elements found');
    } else {
      results.module_1_data_management.findings.push('❌ Annotation interface not found');
    }

    // Check for VRU detection elements
    const vruElements = await page.$$('[data-testid*="vru"], [data-testid*="detection"], .detection-box');
    if (vruElements.length > 0) {
      results.module_1_data_management.score += 2;
      results.module_1_data_management.findings.push('✅ VRU detection interface elements found');
    } else {
      results.module_1_data_management.findings.push('❌ VRU detection interface not found');
    }

    // Check for video library/management
    const libraryElements = await page.$$('.video-library, .video-grid, [data-testid*="library"], [data-testid*="videos"]');
    if (libraryElements.length > 0) {
      results.module_1_data_management.score += 2;
      results.module_1_data_management.findings.push('✅ Video library interface found');
    } else {
      results.module_1_data_management.findings.push('❌ Video library interface not found');
    }

    // Check for search functionality
    const searchElements = await page.$$('input[type="search"], input[placeholder*="Search"], [data-testid*="search"]');
    if (searchElements.length > 0) {
      results.module_1_data_management.score += 1;
      results.module_1_data_management.findings.push('✅ Search functionality found');
    } else {
      results.module_1_data_management.findings.push('❌ Search functionality not found');
    }

    // MODULE 2: Project Management
    console.log('\n📋 Testing Module 2: Project Management');
    
    // Check for project creation
    const projectCreateElements = await page.$$('button:has-text("Create"), button:has-text("New"), [data-testid*="create-project"]');
    if (projectCreateElements.length > 0) {
      results.module_2_project_management.score += 2;
      results.module_2_project_management.findings.push('✅ Project creation interface found');
    } else {
      results.module_2_project_management.findings.push('❌ Project creation interface not found');
    }

    // Check for project list
    const projectListElements = await page.$$('.project-list, .project-grid, .project-item, [data-testid*="project"]');
    if (projectListElements.length > 0) {
      results.module_2_project_management.score += 2;
      results.module_2_project_management.findings.push('✅ Project list interface found');
    } else {
      results.module_2_project_management.findings.push('❌ Project list interface not found');
    }

    // Try navigation to projects
    try {
      await page.goto('http://localhost:3000/projects', { waitUntil: 'networkidle' });
      results.module_2_project_management.score += 2;
      results.module_2_project_management.findings.push('✅ Projects route accessible');
    } catch (e) {
      results.module_2_project_management.findings.push('❌ Projects route not accessible');
    }

    // Check for project management actions
    const projectActionsElements = await page.$$('button:has-text("Edit"), button:has-text("Delete"), .project-actions');
    if (projectActionsElements.length > 0) {
      results.module_2_project_management.score += 2;
      results.module_2_project_management.findings.push('✅ Project management actions found');
    } else {
      results.module_2_project_management.findings.push('❌ Project management actions not found');
    }

    // Check for add videos to project
    const addVideoElements = await page.$$('button:has-text("Add Video"), [data-testid*="add-video"]');
    if (addVideoElements.length > 0) {
      results.module_2_project_management.score += 2;
      results.module_2_project_management.findings.push('✅ Add videos to project functionality found');
    } else {
      results.module_2_project_management.findings.push('❌ Add videos to project functionality not found');
    }

    // MODULE 3: HIL Test Execution
    console.log('\n📋 Testing Module 3: HIL Test Execution');
    
    // Navigate back to home
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' });

    // Check for LabJack connection status
    const labJackElements = await page.$$('[data-testid*="labjack"], .labjack-status, .connection-status');
    const connectionText = await page.$eval('body', (body) => body.textContent || '');
    if (labJackElements.length > 0 || connectionText.includes('Connected') || connectionText.includes('Not Detected')) {
      results.module_3_hil_test_execution.score += 2;
      results.module_3_hil_test_execution.findings.push('✅ LabJack connection status interface found');
    } else {
      results.module_3_hil_test_execution.findings.push('❌ LabJack connection status not found');
    }

    // Check for latency threshold input
    const thresholdElements = await page.$$('input[name*="latency"], input[name*="threshold"], [data-testid*="threshold"]');
    if (thresholdElements.length > 0) {
      results.module_3_hil_test_execution.score += 2;
      results.module_3_hil_test_execution.findings.push('✅ Latency threshold input found');
    } else {
      results.module_3_hil_test_execution.findings.push('❌ Latency threshold input not found');
    }

    // Check for video playback interface
    const videoElements = await page.$$('video, .video-player, .media-player');
    if (videoElements.length > 0) {
      results.module_3_hil_test_execution.score += 2;
      results.module_3_hil_test_execution.findings.push('✅ Video playback interface found');
    } else {
      results.module_3_hil_test_execution.findings.push('❌ Video playback interface not found');
    }

    // Check for test execution controls
    const testControlElements = await page.$$('button:has-text("Start"), button:has-text("Run"), [data-testid*="start-test"]');
    if (testControlElements.length > 0) {
      results.module_3_hil_test_execution.score += 2;
      results.module_3_hil_test_execution.findings.push('✅ Test execution controls found');
    } else {
      results.module_3_hil_test_execution.findings.push('❌ Test execution controls not found');
    }

    // Check for timing displays
    const timingElements = await page.$$('[data-testid*="timing"], .timing-display, .precision-timing');
    if (timingElements.length > 0) {
      results.module_3_hil_test_execution.score += 2;
      results.module_3_hil_test_execution.findings.push('✅ Timing display interface found');
    } else {
      results.module_3_hil_test_execution.findings.push('❌ Timing display interface not found');
    }

    // MODULE 4: Analysis & Reporting
    console.log('\n📋 Testing Module 4: Analysis & Reporting');
    
    // Check for analysis interface
    const analysisElements = await page.$$('[data-testid*="analysis"], .analysis-results, [data-testid*="pass"], [data-testid*="fail"]');
    if (analysisElements.length > 0) {
      results.module_4_analysis_reporting.score += 2;
      results.module_4_analysis_reporting.findings.push('✅ Analysis interface found');
    } else {
      results.module_4_analysis_reporting.findings.push('❌ Analysis interface not found');
    }

    // Check for pass/fail indicators
    const passFailText = await page.$eval('body', (body) => body.textContent || '');
    if (passFailText.includes('Pass') || passFailText.includes('Fail')) {
      results.module_4_analysis_reporting.score += 2;
      results.module_4_analysis_reporting.findings.push('✅ Pass/Fail analysis indicators found');
    } else {
      results.module_4_analysis_reporting.findings.push('❌ Pass/Fail analysis indicators not found');
    }

    // Check for report generation
    const reportElements = await page.$$('button:has-text("Report"), button:has-text("Generate"), [data-testid*="report"]');
    if (reportElements.length > 0) {
      results.module_4_analysis_reporting.score += 2;
      results.module_4_analysis_reporting.findings.push('✅ Report generation functionality found');
    } else {
      results.module_4_analysis_reporting.findings.push('❌ Report generation functionality not found');
    }

    // Check for statistics/metrics
    const statsElements = await page.$$('.statistics, .metrics, [data-testid*="stat"]');
    const percentagePattern = /%/;
    if (statsElements.length > 0 || percentagePattern.test(passFailText)) {
      results.module_4_analysis_reporting.score += 2;
      results.module_4_analysis_reporting.findings.push('✅ Statistical metrics found');
    } else {
      results.module_4_analysis_reporting.findings.push('❌ Statistical metrics not found');
    }

    // Check for failure snapshots
    const snapshotElements = await page.$$('img[src*="failure"], .snapshot, [data-testid*="snapshot"]');
    if (snapshotElements.length > 0) {
      results.module_4_analysis_reporting.score += 2;
      results.module_4_analysis_reporting.findings.push('✅ Failure snapshot functionality found');
    } else {
      results.module_4_analysis_reporting.findings.push('❌ Failure snapshot functionality not found');
    }

    console.log('✅ PRD validation completed');

  } catch (error) {
    console.error('❌ Error during validation:', error);
    results.frontend_status = 'error';
  } finally {
    await browser.close();
  }

  return results;
}

// Run validation
validatePRDCompliance().then((results) => {
  const fs = require('fs');
  
  // Save detailed JSON results
  fs.writeFileSync('/home/rigade/Testing/docs/errors/prd-validation-results.json', JSON.stringify(results, null, 2));
  
  // Calculate overall scores
  const totalScore = results.module_1_data_management.score + 
                    results.module_2_project_management.score + 
                    results.module_3_hil_test_execution.score + 
                    results.module_4_analysis_reporting.score;
  
  const maxTotalScore = results.module_1_data_management.max_score + 
                       results.module_2_project_management.max_score + 
                       results.module_3_hil_test_execution.max_score + 
                       results.module_4_analysis_reporting.max_score;
  
  const overallPercentage = (totalScore / maxTotalScore) * 100;

  console.log('\n' + '='.repeat(80));
  console.log('🎯 PRD COMPLIANCE VALIDATION SUMMARY');
  console.log('='.repeat(80));
  console.log(`📊 Overall Score: ${totalScore}/${maxTotalScore} (${overallPercentage.toFixed(1)}%)`);
  console.log(`🌐 Frontend Status: ${results.frontend_status}`);
  console.log(`⚡ Page Load Time: ${results.performance_metrics.load_time || 'N/A'}ms`);
  console.log(`🚫 Console Errors: ${results.console_errors.length}`);
  console.log(`🌐 Network Failures: ${results.network_failures.length}`);
  
  console.log('\n📋 MODULE SCORES:');
  console.log(`Module 1 - Data Management: ${results.module_1_data_management.score}/${results.module_1_data_management.max_score}`);
  console.log(`Module 2 - Project Management: ${results.module_2_project_management.score}/${results.module_2_project_management.max_score}`);
  console.log(`Module 3 - HIL Test Execution: ${results.module_3_hil_test_execution.score}/${results.module_3_hil_test_execution.max_score}`);
  console.log(`Module 4 - Analysis & Reporting: ${results.module_4_analysis_reporting.score}/${results.module_4_analysis_reporting.max_score}`);
  
  console.log('\n📄 Detailed results saved to: /home/rigade/Testing/docs/errors/prd-validation-results.json');
  console.log('='.repeat(80));
});