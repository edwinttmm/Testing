/**
 * COMPREHENSIVE PRD MODULE 1-4 PLAYWRIGHT TEST SUITE
 * AI Model Validation Platform - Complete UI and Backend Testing
 * 
 * This test suite covers ALL PRD requirements:
 * - Module 1: Video Management & Processing
 * - Module 2: Object Detection & Annotation
 * - Module 3: HIL Test Environment & LabJack Integration  
 * - Module 4: Performance Analysis & Reporting
 * 
 * Includes comprehensive console error capture and analysis
 */

const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// Test configuration
const CONFIG = {
    frontend: 'http://localhost:3000',
    backend: 'http://localhost:8000',
    testTimeout: 120000, // 2 minutes per test
    consoleLogFile: '/home/rigade/Testing/docs/errors/console_errors.log',
    screenshotDir: '/home/rigade/Testing/docs/errors/screenshots',
    testVideoPath: '/home/rigade/Testing/test_videos/sample_adas_video.mp4'
};

// Console error tracking
let consoleErrors = [];
let consoleWarnings = [];
let networkErrors = [];
let reactErrors = [];

// Helper function to log errors
function logError(type, message, details = {}) {
    const timestamp = new Date().toISOString();
    const error = {
        timestamp,
        type,
        message,
        details,
        stack: details.stack || 'No stack trace'
    };
    
    consoleErrors.push(error);
    
    // Write to log file immediately
    const logEntry = `[${timestamp}] ${type}: ${message}\n${JSON.stringify(details, null, 2)}\n\n`;
    fs.appendFileSync(CONFIG.consoleLogFile, logEntry);
}

// Test setup and teardown
test.beforeAll(async () => {
    // Ensure directories exist
    fs.mkdirSync(path.dirname(CONFIG.consoleLogFile), { recursive: true });
    fs.mkdirSync(CONFIG.screenshotDir, { recursive: true });
    
    // Clear previous log
    fs.writeFileSync(CONFIG.consoleLogFile, `PRD COMPREHENSIVE TEST LOG - ${new Date().toISOString()}\n\n`);
    
    console.log('🚀 Starting PRD Comprehensive Test Suite');
    console.log(`📊 Frontend: ${CONFIG.frontend}`);
    console.log(`🔧 Backend: ${CONFIG.backend}`);
    console.log(`📝 Console logs: ${CONFIG.consoleLogFile}`);
});

test.beforeEach(async ({ page }) => {
    // Clear error arrays for each test
    consoleErrors = [];
    consoleWarnings = [];
    networkErrors = [];
    reactErrors = [];
    
    // Set up console monitoring
    page.on('console', msg => {
        const type = msg.type();
        const text = msg.text();
        
        if (type === 'error') {
            logError('CONSOLE_ERROR', text, { 
                location: msg.location(),
                args: msg.args().map(arg => arg.toString())
            });
        } else if (type === 'warn') {
            consoleWarnings.push({ type, text, timestamp: new Date().toISOString() });
        }
        
        // Capture React errors
        if (text.includes('React') || text.includes('Warning:') || text.includes('Error:')) {
            reactErrors.push({ type, text, timestamp: new Date().toISOString() });
            logError('REACT_ERROR', text, { type });
        }
    });
    
    // Monitor page errors  
    page.on('pageerror', error => {
        logError('PAGE_ERROR', error.message, { 
            name: error.name,
            stack: error.stack
        });
    });
    
    // Monitor network failures
    page.on('response', response => {
        if (response.status() >= 400) {
            networkErrors.push({
                url: response.url(),
                status: response.status(),
                statusText: response.statusText(),
                timestamp: new Date().toISOString()
            });
            
            logError('NETWORK_ERROR', `${response.status()} ${response.statusText()}`, {
                url: response.url(),
                status: response.status()
            });
        }
    });
    
    // Monitor request failures
    page.on('requestfailed', request => {
        logError('REQUEST_FAILED', request.failure().errorText, {
            url: request.url(),
            method: request.method(),
            failure: request.failure()
        });
    });
});

test.afterEach(async ({ page }, testInfo) => {
    // Take screenshot on failure
    if (testInfo.status !== 'passed') {
        const screenshotPath = path.join(CONFIG.screenshotDir, `${testInfo.title.replace(/\s+/g, '_')}_failure.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true });
        logError('TEST_FAILURE', `Test failed: ${testInfo.title}`, { 
            screenshotPath,
            errors: consoleErrors.length,
            warnings: consoleWarnings.length,
            networkErrors: networkErrors.length
        });
    }
    
    // Log test completion
    const errorSummary = {
        test: testInfo.title,
        status: testInfo.status,
        duration: testInfo.duration,
        consoleErrors: consoleErrors.length,
        consoleWarnings: consoleWarnings.length,
        networkErrors: networkErrors.length,
        reactErrors: reactErrors.length
    };
    
    fs.appendFileSync(CONFIG.consoleLogFile, `TEST SUMMARY: ${JSON.stringify(errorSummary, null, 2)}\n\n`);
});

// PRD MODULE 1: VIDEO MANAGEMENT & PROCESSING
test.describe('PRD Module 1: Video Management & Processing', () => {
    
    test('1.1 Video Library Access and Navigation', async ({ page }) => {
        await page.goto(CONFIG.frontend);
        
        // Wait for app to load
        await page.waitForSelector('[data-testid="app-header"]', { timeout: 30000 });
        
        // Check for critical React errors
        expect(reactErrors.length).toBe(0);
        
        // Navigate to video library
        await page.click('text=Video Library');
        await page.waitForSelector('[data-testid="video-library"]', { timeout: 15000 });
        
        // Verify video categories exist
        const categories = ['front-facing-vru', 'rear-facing-vru', 'in-cab-driver-behavior', 'multi-angle-scenarios'];
        for (const category of categories) {
            await expect(page.locator(`[data-testid="category-${category}"]`)).toBeVisible();
        }
        
        // Check for console errors during navigation
        const navigationErrors = consoleErrors.filter(e => e.timestamp > Date.now() - 10000);
        expect(navigationErrors.length).toBe(0);
    });
    
    test('1.2 Video Upload Functionality', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/videos`);
        
        // Wait for upload interface
        await page.waitForSelector('[data-testid="video-upload"]', { timeout: 15000 });
        
        // Test file selection
        const fileInput = page.locator('input[type="file"]');
        await expect(fileInput).toBeVisible();
        
        // Test upload validation
        await page.click('[data-testid="upload-button"]');
        
        // Should show validation message
        await expect(page.locator('text=Please select a video file')).toBeVisible();
        
        // Check for upload-related errors
        const uploadErrors = consoleErrors.filter(e => e.message.includes('upload'));
        expect(uploadErrors.length).toBe(0);
    });
    
    test('1.3 Video Processing Pipeline', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/videos`);
        
        // Check processing status indicators
        await page.waitForSelector('[data-testid="processing-status"]', { timeout: 15000 });
        
        // Verify processing stages displayed
        const stages = ['Upload', 'Validation', 'Processing', 'Ready'];
        for (const stage of stages) {
            await expect(page.locator(`text=${stage}`)).toBeVisible();
        }
        
        // Test WebSocket connection for progress
        await page.evaluate(() => {
            if (!window.WebSocket) {
                throw new Error('WebSocket not available');
            }
        });
    });
});

// PRD MODULE 2: OBJECT DETECTION & ANNOTATION  
test.describe('PRD Module 2: Object Detection & Annotation', () => {
    
    test('2.1 AI Pre-annotation with YOLO Integration', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/annotation`);
        
        // Wait for annotation interface
        await page.waitForSelector('[data-testid="annotation-canvas"]', { timeout: 15000 });
        
        // Check for AI detection controls
        await expect(page.locator('[data-testid="ai-detection-toggle"]')).toBeVisible();
        await expect(page.locator('[data-testid="detection-confidence"]')).toBeVisible();
        
        // Test detection classes
        const classes = ['Person', 'Vehicle', 'Bicycle', 'Object'];
        for (const cls of classes) {
            await expect(page.locator(`text=${cls}`)).toBeVisible();
        }
        
        // Verify no YOLO-related errors in console
        const yoloErrors = consoleErrors.filter(e => 
            e.message.includes('YOLO') || e.message.includes('detection')
        );
        expect(yoloErrors.length).toBe(0);
    });
    
    test('2.2 Manual Annotation Tools', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/annotation`);
        
        // Wait for annotation tools
        await page.waitForSelector('[data-testid="annotation-tools"]', { timeout: 15000 });
        
        // Check annotation tools
        const tools = ['select', 'rectangle', 'polygon', 'point'];
        for (const tool of tools) {
            await expect(page.locator(`[data-testid="tool-${tool}"]`)).toBeVisible();
        }
        
        // Test annotation creation (if canvas available)
        const canvas = page.locator('[data-testid="annotation-canvas"]');
        if (await canvas.isVisible()) {
            await canvas.click({ position: { x: 100, y: 100 } });
        }
        
        // Check for annotation errors
        const annotationErrors = consoleErrors.filter(e => 
            e.message.includes('annotation') || e.message.includes('canvas')
        );
        expect(annotationErrors.length).toBe(0);
    });
    
    test('2.3 Ground Truth Export Formats', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/annotation`);
        
        // Wait for export controls
        await page.waitForSelector('[data-testid="export-controls"]', { timeout: 15000 });
        
        // Check export format options
        const formats = ['JSON', 'CSV', 'COCO', 'YOLO'];
        for (const format of formats) {
            await expect(page.locator(`text=${format}`)).toBeVisible();
        }
        
        // Test export functionality
        await page.click('[data-testid="export-json"]');
        
        // Should not cause errors
        const exportErrors = consoleErrors.filter(e => e.message.includes('export'));
        expect(exportErrors.length).toBe(0);
    });
});

// PRD MODULE 3: HIL TEST ENVIRONMENT & LABJACK
test.describe('PRD Module 3: HIL Test Environment & LabJack Integration', () => {
    
    test('3.1 Hardware Connection Status', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/testing`);
        
        // Wait for HIL interface
        await page.waitForSelector('[data-testid="hil-interface"]', { timeout: 15000 });
        
        // Check LabJack connection status
        await expect(page.locator('[data-testid="labjack-status"]')).toBeVisible();
        
        // Verify connection status displays properly
        const statusText = await page.locator('[data-testid="labjack-status"]').textContent();
        expect(['Connected', 'Not Detected', 'Connecting']).toContain(statusText.trim());
        
        // Check for hardware-related errors
        const hardwareErrors = consoleErrors.filter(e => 
            e.message.includes('LabJack') || e.message.includes('hardware')
        );
        // Allow some hardware warnings in development
        expect(hardwareErrors.filter(e => e.type === 'CONSOLE_ERROR').length).toBe(0);
    });
    
    test('3.2 Signal Validation Interface', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/testing`);
        
        // Wait for signal validation controls
        await page.waitForSelector('[data-testid="signal-validation"]', { timeout: 15000 });
        
        // Check signal monitoring controls
        await expect(page.locator('[data-testid="start-monitoring"]')).toBeVisible();
        await expect(page.locator('[data-testid="signal-status"]')).toBeVisible();
        
        // Test signal monitoring UI
        await page.click('[data-testid="start-monitoring"]');
        
        // Should show monitoring active state
        await expect(page.locator('text=Monitoring Active')).toBeVisible({ timeout: 10000 });
        
        // Check for signal validation errors
        const signalErrors = consoleErrors.filter(e => 
            e.message.includes('signal') || e.message.includes('monitoring')
        );
        expect(signalErrors.length).toBe(0);
    });
    
    test('3.3 Precision Timing System', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/testing`);
        
        // Wait for timing interface
        await page.waitForSelector('[data-testid="timing-interface"]', { timeout: 15000 });
        
        // Check timing precision display
        await expect(page.locator('[data-testid="timing-precision"]')).toBeVisible();
        
        // Verify sub-millisecond timing capability
        const timingText = await page.locator('[data-testid="timing-precision"]').textContent();
        expect(timingText).toContain('μs'); // Should show microsecond precision
        
        // Check for timing-related errors
        const timingErrors = consoleErrors.filter(e => 
            e.message.includes('timing') || e.message.includes('precision')
        );
        expect(timingErrors.length).toBe(0);
    });
});

// PRD MODULE 4: PERFORMANCE ANALYSIS & REPORTING
test.describe('PRD Module 4: Performance Analysis & Reporting', () => {
    
    test('4.1 Real-time Dashboard', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/dashboard`);
        
        // Wait for dashboard to load
        await page.waitForSelector('[data-testid="dashboard"]', { timeout: 15000 });
        
        // Check dashboard widgets
        const widgets = ['detection-stats', 'timing-analysis', 'test-results', 'system-health'];
        for (const widget of widgets) {
            await expect(page.locator(`[data-testid="${widget}"]`)).toBeVisible();
        }
        
        // Verify charts and graphs render
        await expect(page.locator('canvas, svg')).toHaveCount({ min: 2 }); // At least 2 charts
        
        // Check for dashboard rendering errors
        const dashboardErrors = consoleErrors.filter(e => 
            e.message.includes('chart') || e.message.includes('dashboard')
        );
        expect(dashboardErrors.length).toBe(0);
    });
    
    test('4.2 Performance Metrics and Reports', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/reports`);
        
        // Wait for reports interface
        await page.waitForSelector('[data-testid="reports-interface"]', { timeout: 15000 });
        
        // Check report types
        const reportTypes = ['detection-performance', 'timing-analysis', 'test-summary', 'comparison'];
        for (const type of reportTypes) {
            await expect(page.locator(`[data-testid="report-${type}"]`)).toBeVisible();
        }
        
        // Test report generation
        await page.click('[data-testid="generate-report"]');
        
        // Should show progress or results
        await expect(page.locator('[data-testid="report-status"]')).toBeVisible({ timeout: 10000 });
        
        // Check for report generation errors
        const reportErrors = consoleErrors.filter(e => 
            e.message.includes('report') || e.message.includes('generation')
        );
        expect(reportErrors.length).toBe(0);
    });
    
    test('4.3 Statistical Analysis and Comparisons', async ({ page }) => {
        await page.goto(`${CONFIG.frontend}/analysis`);
        
        // Wait for analysis interface
        await page.waitForSelector('[data-testid="analysis-interface"]', { timeout: 15000 });
        
        // Check statistical tools
        await expect(page.locator('[data-testid="confidence-intervals"]')).toBeVisible();
        await expect(page.locator('[data-testid="statistical-tests"]')).toBeVisible();
        
        // Verify analysis controls
        const controls = ['t-test', 'chi-square', 'regression', 'correlation'];
        for (const control of controls) {
            await expect(page.locator(`text=${control}`)).toBeVisible();
        }
        
        // Check for statistical analysis errors
        const analysisErrors = consoleErrors.filter(e => 
            e.message.includes('statistical') || e.message.includes('analysis')
        );
        expect(analysisErrors.length).toBe(0);
    });
});

// COMPREHENSIVE ERROR DETECTION TESTS
test.describe('Comprehensive Error Detection & Analysis', () => {
    
    test('5.1 TypeScript Compilation Errors', async ({ page }) => {
        await page.goto(CONFIG.frontend);
        
        // Wait for app initialization
        await page.waitForTimeout(5000);
        
        // Check for TypeScript errors
        const tsErrors = consoleErrors.filter(e => 
            e.message.includes('TypeScript') || 
            e.message.includes('TS') ||
            e.message.includes('type error')
        );
        
        expect(tsErrors.length).toBe(0);
    });
    
    test('5.2 React Component Errors and Warnings', async ({ page }) => {
        await page.goto(CONFIG.frontend);
        
        // Navigate through all major components
        const routes = ['/videos', '/annotation', '/testing', '/dashboard', '/reports'];
        
        for (const route of routes) {
            await page.goto(`${CONFIG.frontend}${route}`);
            await page.waitForTimeout(2000);
        }
        
        // Filter React-specific warnings and errors
        const reactIssues = reactErrors.filter(e => 
            e.text.includes('Warning:') || 
            e.text.includes('React') ||
            e.text.includes('component')
        );
        
        // Log React issues for analysis
        if (reactIssues.length > 0) {
            logError('REACT_ANALYSIS', `Found ${reactIssues.length} React issues`, { issues: reactIssues });
        }
        
        // Critical React errors should be 0
        const criticalReactErrors = reactIssues.filter(e => e.type === 'error');
        expect(criticalReactErrors.length).toBe(0);
    });
    
    test('5.3 Network API Errors and Timeouts', async ({ page }) => {
        await page.goto(CONFIG.frontend);
        
        // Test all major API endpoints
        const apiTests = [
            '/api/videos',
            '/api/projects', 
            '/api/annotations',
            '/api/test-sessions',
            '/api/dashboard',
            '/api/labjack/status',
            '/api/labjack/devices'
        ];
        
        for (const endpoint of apiTests) {
            const response = await page.request.get(`${CONFIG.backend}${endpoint}`);
            expect(response.status()).toBeLessThan(500); // No server errors
        }
        
        // Check for network-related console errors
        const networkIssues = networkErrors.filter(e => e.status >= 500);
        expect(networkIssues.length).toBe(0);
    });
    
    test('5.4 Memory Leaks and Performance Issues', async ({ page }) => {
        await page.goto(CONFIG.frontend);
        
        // Measure initial performance
        const initialMetrics = await page.evaluate(() => performance.now());
        
        // Navigate through app multiple times
        for (let i = 0; i < 3; i++) {
            await page.goto(`${CONFIG.frontend}/videos`);
            await page.waitForTimeout(1000);
            await page.goto(`${CONFIG.frontend}/annotation`);
            await page.waitForTimeout(1000);
            await page.goto(`${CONFIG.frontend}/dashboard`);
            await page.waitForTimeout(1000);
        }
        
        // Check for performance warnings
        const performanceErrors = consoleErrors.filter(e => 
            e.message.includes('memory') || 
            e.message.includes('performance') ||
            e.message.includes('leak')
        );
        
        expect(performanceErrors.length).toBe(0);
    });
});

// FINAL ERROR SUMMARY TEST
test('6.0 Final Error Summary and Analysis', async ({ page }) => {
    // This test runs last to provide comprehensive summary
    
    // Wait for all previous tests to complete
    await page.goto(CONFIG.frontend);
    await page.waitForTimeout(2000);
    
    // Generate comprehensive error report
    const errorSummary = {
        timestamp: new Date().toISOString(),
        totalConsoleErrors: consoleErrors.length,
        totalConsoleWarnings: consoleWarnings.length,
        totalNetworkErrors: networkErrors.length,
        totalReactErrors: reactErrors.length,
        criticalErrors: consoleErrors.filter(e => e.type === 'CONSOLE_ERROR').length,
        pageErrors: consoleErrors.filter(e => e.type === 'PAGE_ERROR').length,
        networkFailures: consoleErrors.filter(e => e.type === 'NETWORK_ERROR').length,
        requestFailures: consoleErrors.filter(e => e.type === 'REQUEST_FAILED').length
    };
    
    // Write final summary
    const summaryPath = '/home/rigade/Testing/docs/errors/FINAL_ERROR_SUMMARY.json';
    fs.writeFileSync(summaryPath, JSON.stringify(errorSummary, null, 2));
    
    // Write detailed error log
    const detailedErrorsPath = '/home/rigade/Testing/docs/errors/DETAILED_ERRORS.json';
    fs.writeFileSync(detailedErrorsPath, JSON.stringify({
        consoleErrors,
        consoleWarnings,
        networkErrors,
        reactErrors
    }, null, 2));
    
    console.log('📊 ERROR SUMMARY:', errorSummary);
    
    // Test should pass if no critical errors found
    expect(errorSummary.criticalErrors).toBe(0);
});