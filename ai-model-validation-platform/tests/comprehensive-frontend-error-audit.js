#!/usr/bin/env node

/**
 * Comprehensive Frontend Error Discovery Tool
 * Frontend Error Discovery Specialist - Queen's Hive-Mind
 * 
 * MISSION: Complete frontend error audit with full stack testing integration
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

class FrontendErrorAuditor {
    constructor() {
        this.errors = {
            console: [],
            network: [],
            runtime: [],
            ui: [],
            integration: []
        };
        this.browser = null;
        this.page = null;
        this.startTime = new Date();
    }

    async initialize() {
        console.log('🔍 FRONTEND ERROR DISCOVERY SPECIALIST - INITIALIZING');
        console.log('Mission: Complete frontend error audit with full stack integration');
        
        try {
            // Launch browser with extensive logging
            this.browser = await puppeteer.launch({
                headless: true,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-default-apps',
                    '--disable-extensions'
                ]
            });

            this.page = await this.browser.newPage();
            
            // Set up comprehensive error monitoring
            await this.setupErrorMonitoring();
            
            console.log('✅ Browser initialized with error monitoring');
            return true;
        } catch (error) {
            console.error('❌ Browser initialization failed:', error.message);
            return false;
        }
    }

    async setupErrorMonitoring() {
        // Monitor console messages and errors
        this.page.on('console', msg => {
            const type = msg.type();
            const text = msg.text();
            
            if (type === 'error' || type === 'warn') {
                this.errors.console.push({
                    type,
                    message: text,
                    timestamp: new Date().toISOString(),
                    severity: type === 'error' ? 'HIGH' : 'MEDIUM'
                });
            }
            
            console.log(`📋 Console [${type.toUpperCase()}]: ${text}`);
        });

        // Monitor page errors (JavaScript exceptions)
        this.page.on('pageerror', error => {
            this.errors.runtime.push({
                type: 'javascript_exception',
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString(),
                severity: 'HIGH'
            });
            console.log('💥 JavaScript Exception:', error.message);
        });

        // Monitor failed network requests
        this.page.on('requestfailed', request => {
            const failure = request.failure();
            this.errors.network.push({
                type: 'network_failure',
                url: request.url(),
                method: request.method(),
                error: failure ? failure.errorText : 'Unknown error',
                timestamp: new Date().toISOString(),
                severity: 'HIGH'
            });
            console.log('🌐 Network Failed:', request.url(), '-', failure ? failure.errorText : 'Unknown');
        });

        // Monitor response errors
        this.page.on('response', response => {
            if (!response.ok()) {
                this.errors.network.push({
                    type: 'http_error',
                    url: response.url(),
                    status: response.status(),
                    statusText: response.statusText(),
                    timestamp: new Date().toISOString(),
                    severity: response.status() >= 500 ? 'HIGH' : 'MEDIUM'
                });
                console.log(`📡 HTTP Error: ${response.status()} ${response.statusText()} - ${response.url()}`);
            }
        });

        // Enable request interception for detailed monitoring
        await this.page.setRequestInterception(true);
        this.page.on('request', request => {
            console.log(`→ ${request.method()} ${request.url()}`);
            request.continue();
        });
    }

    async testFrontend() {
        console.log('\n🎯 STARTING COMPREHENSIVE FRONTEND TESTING');
        
        try {
            // Test 1: Homepage Load
            console.log('\n1️⃣ Testing Homepage Load...');
            const response = await this.page.goto('http://localhost:3001', {
                waitUntil: 'networkidle2',
                timeout: 30000
            });
            
            if (!response || !response.ok()) {
                this.errors.integration.push({
                    type: 'page_load_failure',
                    url: 'http://localhost:3001',
                    status: response ? response.status() : 'NO_RESPONSE',
                    timestamp: new Date().toISOString(),
                    severity: 'CRITICAL'
                });
                console.log('❌ Homepage failed to load');
                return false;
            }
            
            console.log('✅ Homepage loaded successfully');

            // Test 2: React App Render
            await this.testReactAppRender();

            // Test 3: Navigation and Routes
            await this.testNavigation();

            // Test 4: API Integration
            await this.testAPIIntegration();

            // Test 5: Component Functionality
            await this.testComponentFunctionality();

            // Test 6: WebSocket Connections
            await this.testWebSocketConnections();

            return true;

        } catch (error) {
            this.errors.runtime.push({
                type: 'test_execution_error',
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString(),
                severity: 'CRITICAL'
            });
            console.log('❌ Frontend testing failed:', error.message);
            return false;
        }
    }

    async testReactAppRender() {
        console.log('\n2️⃣ Testing React App Render...');
        
        try {
            // Wait for React to load
            await this.page.waitForSelector('#root', { timeout: 10000 });
            
            // Check if React app rendered
            const reactContent = await this.page.$eval('#root', el => el.innerHTML);
            
            if (!reactContent || reactContent.length < 100) {
                this.errors.ui.push({
                    type: 'react_render_failure',
                    message: 'React app did not render properly',
                    content_length: reactContent ? reactContent.length : 0,
                    timestamp: new Date().toISOString(),
                    severity: 'HIGH'
                });
                console.log('❌ React app render failed');
            } else {
                console.log('✅ React app rendered successfully');
            }

        } catch (error) {
            this.errors.ui.push({
                type: 'react_wait_timeout',
                message: error.message,
                timestamp: new Date().toISOString(),
                severity: 'HIGH'
            });
            console.log('❌ React app wait timeout:', error.message);
        }
    }

    async testNavigation() {
        console.log('\n3️⃣ Testing Navigation...');
        
        const routes = [
            { path: '/projects', name: 'Projects' },
            { path: '/datasets', name: 'Datasets' },
            { path: '/ground-truth', name: 'Ground Truth' },
            { path: '/results', name: 'Results' }
        ];

        for (const route of routes) {
            try {
                console.log(`   📍 Testing route: ${route.path}`);
                
                await this.page.goto(`http://localhost:3001${route.path}`, {
                    waitUntil: 'networkidle2',
                    timeout: 15000
                });

                // Wait for page content
                await this.page.waitForTimeout(2000);

                console.log(`   ✅ ${route.name} page loaded`);

            } catch (error) {
                this.errors.ui.push({
                    type: 'navigation_failure',
                    route: route.path,
                    message: error.message,
                    timestamp: new Date().toISOString(),
                    severity: 'MEDIUM'
                });
                console.log(`   ❌ ${route.name} page failed:`, error.message);
            }
        }
    }

    async testAPIIntegration() {
        console.log('\n4️⃣ Testing API Integration...');
        
        try {
            // Navigate to a page that makes API calls
            await this.page.goto('http://localhost:3001/projects', {
                waitUntil: 'networkidle2',
                timeout: 15000
            });

            // Wait for API calls to complete
            await this.page.waitForTimeout(5000);

            // Check for API error patterns in the page content
            const pageContent = await this.page.content();
            
            if (pageContent.includes('Error loading') || pageContent.includes('Failed to fetch')) {
                this.errors.integration.push({
                    type: 'api_error_in_ui',
                    message: 'API errors detected in UI',
                    timestamp: new Date().toISOString(),
                    severity: 'HIGH'
                });
                console.log('❌ API errors detected in UI');
            } else {
                console.log('✅ API integration appears functional');
            }

        } catch (error) {
            this.errors.integration.push({
                type: 'api_integration_test_error',
                message: error.message,
                timestamp: new Date().toISOString(),
                severity: 'MEDIUM'
            });
            console.log('❌ API integration test failed:', error.message);
        }
    }

    async testComponentFunctionality() {
        console.log('\n5️⃣ Testing Component Functionality...');
        
        try {
            // Test button clicks, form interactions, etc.
            await this.page.goto('http://localhost:3001/projects', {
                waitUntil: 'networkidle2',
                timeout: 15000
            });

            // Look for interactive elements
            const buttons = await this.page.$$('button');
            const forms = await this.page.$$('form');
            const inputs = await this.page.$$('input');

            console.log(`   📊 Found ${buttons.length} buttons, ${forms.length} forms, ${inputs.length} inputs`);

            // Test a simple button click if available
            if (buttons.length > 0) {
                try {
                    await buttons[0].click();
                    await this.page.waitForTimeout(1000);
                    console.log('   ✅ Button interaction test passed');
                } catch (clickError) {
                    this.errors.ui.push({
                        type: 'component_interaction_failure',
                        message: `Button click failed: ${clickError.message}`,
                        timestamp: new Date().toISOString(),
                        severity: 'MEDIUM'
                    });
                    console.log('   ❌ Button interaction failed');
                }
            }

        } catch (error) {
            this.errors.ui.push({
                type: 'component_test_error',
                message: error.message,
                timestamp: new Date().toISOString(),
                severity: 'MEDIUM'
            });
            console.log('❌ Component functionality test failed:', error.message);
        }
    }

    async testWebSocketConnections() {
        console.log('\n6️⃣ Testing WebSocket Connections...');
        
        try {
            // Check for WebSocket connections in the network tab
            await this.page.goto('http://localhost:3001', {
                waitUntil: 'networkidle2',
                timeout: 15000
            });

            // Wait for potential WebSocket connections
            await this.page.waitForTimeout(5000);

            // Note: WebSocket testing is complex with Puppeteer
            // We're monitoring for WebSocket errors in the console monitoring
            console.log('✅ WebSocket monitoring active (errors tracked in console)');

        } catch (error) {
            this.errors.integration.push({
                type: 'websocket_test_error',
                message: error.message,
                timestamp: new Date().toISOString(),
                severity: 'LOW'
            });
            console.log('❌ WebSocket test failed:', error.message);
        }
    }

    async generateReport() {
        console.log('\n📊 GENERATING COMPREHENSIVE ERROR REPORT');
        
        const endTime = new Date();
        const testDuration = (endTime - this.startTime) / 1000;

        const report = {
            test_session: {
                start_time: this.startTime.toISOString(),
                end_time: endTime.toISOString(),
                duration_seconds: testDuration,
                frontend_url: 'http://localhost:3001',
                backend_url: 'http://localhost:8000'
            },
            error_summary: {
                total_errors: this.getTotalErrorCount(),
                console_errors: this.errors.console.length,
                network_errors: this.errors.network.length,
                runtime_errors: this.errors.runtime.length,
                ui_errors: this.errors.ui.length,
                integration_errors: this.errors.integration.length
            },
            severity_breakdown: this.getSeverityBreakdown(),
            detailed_errors: this.errors,
            recommendations: this.generateRecommendations()
        };

        // Save report
        const reportPath = path.join(__dirname, `frontend-error-audit-${Date.now()}.json`);
        fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

        console.log(`\n📝 Report saved to: ${reportPath}`);
        
        // Print summary
        this.printErrorSummary(report);
        
        return report;
    }

    getTotalErrorCount() {
        return Object.values(this.errors).reduce((total, errorArray) => total + errorArray.length, 0);
    }

    getSeverityBreakdown() {
        const severity = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
        
        Object.values(this.errors).forEach(errorArray => {
            errorArray.forEach(error => {
                severity[error.severity] = (severity[error.severity] || 0) + 1;
            });
        });
        
        return severity;
    }

    generateRecommendations() {
        const recommendations = [];
        
        if (this.errors.console.length > 5) {
            recommendations.push({
                priority: 'HIGH',
                category: 'Console Cleanup',
                issue: `${this.errors.console.length} console errors found`,
                action: 'Implement structured logging and remove console.log statements'
            });
        }

        if (this.errors.network.length > 0) {
            recommendations.push({
                priority: 'HIGH',
                category: 'Network Issues',
                issue: `${this.errors.network.length} network errors found`,
                action: 'Fix API endpoints and implement proper error handling'
            });
        }

        if (this.errors.runtime.length > 0) {
            recommendations.push({
                priority: 'CRITICAL',
                category: 'JavaScript Errors',
                issue: `${this.errors.runtime.length} JavaScript runtime errors found`,
                action: 'Fix JavaScript exceptions and implement error boundaries'
            });
        }

        return recommendations;
    }

    printErrorSummary(report) {
        console.log('\n' + '='.repeat(80));
        console.log('🔍 FRONTEND ERROR AUDIT SUMMARY');
        console.log('='.repeat(80));
        
        console.log(`⏱️  Test Duration: ${report.test_session.duration_seconds.toFixed(2)}s`);
        console.log(`🎯 Total Errors Found: ${report.error_summary.total_errors}`);
        
        console.log('\n📊 Error Breakdown:');
        console.log(`   Console Errors: ${report.error_summary.console_errors}`);
        console.log(`   Network Errors: ${report.error_summary.network_errors}`);
        console.log(`   Runtime Errors: ${report.error_summary.runtime_errors}`);
        console.log(`   UI Errors: ${report.error_summary.ui_errors}`);
        console.log(`   Integration Errors: ${report.error_summary.integration_errors}`);

        console.log('\n🚨 Severity Breakdown:');
        Object.entries(report.severity_breakdown).forEach(([severity, count]) => {
            if (count > 0) {
                console.log(`   ${severity}: ${count}`);
            }
        });

        console.log('\n💡 Top Recommendations:');
        report.recommendations.slice(0, 3).forEach((rec, index) => {
            console.log(`   ${index + 1}. [${rec.priority}] ${rec.category}: ${rec.action}`);
        });

        console.log('\n' + '='.repeat(80));
    }

    async cleanup() {
        if (this.browser) {
            await this.browser.close();
        }
    }
}

// Main execution
async function main() {
    const auditor = new FrontendErrorAuditor();
    
    try {
        const initialized = await auditor.initialize();
        if (!initialized) {
            console.log('❌ Failed to initialize browser auditor');
            process.exit(1);
        }

        const testPassed = await auditor.testFrontend();
        const report = await auditor.generateReport();

        await auditor.cleanup();

        // Exit with error code if critical issues found
        const criticalErrors = report.severity_breakdown.CRITICAL || 0;
        process.exit(criticalErrors > 0 ? 1 : 0);

    } catch (error) {
        console.error('❌ Audit failed:', error);
        await auditor.cleanup();
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = FrontendErrorAuditor;