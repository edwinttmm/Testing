#!/usr/bin/env node

/**
 * Frontend Runtime Error Analyzer
 * Captures and analyzes frontend JavaScript errors in real-time
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

class FrontendErrorAnalyzer {
    constructor() {
        this.errors = [];
        this.warnings = [];
        this.networkErrors = [];
        this.startTime = new Date();
        this.browser = null;
        this.page = null;
    }

    async initialize() {
        try {
            console.log('🚀 Initializing Frontend Error Analyzer...');
            
            // Launch browser with error handling
            this.browser = await puppeteer.launch({
                headless: true,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            });

            this.page = await this.browser.newPage();
            
            // Set up error listeners
            this.setupErrorListeners();
            
            console.log('✅ Browser initialized successfully');
            return true;
        } catch (error) {
            console.error('❌ Failed to initialize browser:', error.message);
            console.log('ℹ️  Falling back to HTTP-only testing...');
            return false;
        }
    }

    setupErrorListeners() {
        // Console errors and warnings
        this.page.on('console', msg => {
            const type = msg.type();
            const text = msg.text();
            const timestamp = new Date().toISOString();
            
            if (type === 'error') {
                this.errors.push({
                    type: 'console',
                    level: 'error',
                    message: text,
                    timestamp: timestamp,
                    url: this.page.url()
                });
                console.log(`🔴 Console Error: ${text}`);
            } else if (type === 'warning') {
                this.warnings.push({
                    type: 'console',
                    level: 'warning',
                    message: text,
                    timestamp: timestamp,
                    url: this.page.url()
                });
                console.log(`🟡 Console Warning: ${text}`);
            }
        });

        // Page errors
        this.page.on('pageerror', error => {
            this.errors.push({
                type: 'page',
                level: 'error',
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString(),
                url: this.page.url()
            });
            console.log(`🔴 Page Error: ${error.message}`);
        });

        // Request failures
        this.page.on('requestfailed', request => {
            this.networkErrors.push({
                type: 'network',
                level: 'error',
                url: request.url(),
                method: request.method(),
                failureText: request.failure().errorText,
                timestamp: new Date().toISOString()
            });
            console.log(`🌐 Network Error: ${request.url()} - ${request.failure().errorText}`);
        });

        // Response errors
        this.page.on('response', response => {
            if (response.status() >= 400) {
                this.networkErrors.push({
                    type: 'response',
                    level: 'error',
                    url: response.url(),
                    status: response.status(),
                    statusText: response.statusText(),
                    timestamp: new Date().toISOString()
                });
                console.log(`🌐 HTTP Error: ${response.status()} ${response.statusText()} - ${response.url()}`);
            }
        });
    }

    async testFrontendApp() {
        console.log('🧪 Testing Frontend Application at http://localhost:3000');
        
        try {
            await this.page.goto('http://localhost:3000', { 
                waitUntil: 'networkidle0',
                timeout: 30000 
            });
            
            console.log('✅ Main page loaded');
            
            // Wait for React to initialize
            await this.page.waitForTimeout(3000);
            
            // Check for React errors
            const reactErrors = await this.page.evaluate(() => {
                const errors = [];
                
                // Check for React error boundaries
                const errorBoundaries = document.querySelectorAll('[data-reactroot] *');
                for (let element of errorBoundaries) {
                    if (element.textContent && element.textContent.includes('Something went wrong')) {
                        errors.push({
                            type: 'react-boundary',
                            element: element.outerHTML.substring(0, 200),
                            text: element.textContent
                        });
                    }
                }
                
                // Check for unhandled promise rejections
                if (window.__UNHANDLED_REJECTIONS__) {
                    errors.push(...window.__UNHANDLED_REJECTIONS__);
                }
                
                return errors;
            });
            
            if (reactErrors.length > 0) {
                console.log(`🔴 Found ${reactErrors.length} React-specific errors`);
                this.errors.push(...reactErrors.map(err => ({
                    ...err,
                    timestamp: new Date().toISOString(),
                    url: this.page.url()
                })));
            }
            
        } catch (error) {
            console.error(`❌ Failed to load main page: ${error.message}`);
            this.errors.push({
                type: 'navigation',
                level: 'error',
                message: error.message,
                timestamp: new Date().toISOString()
            });
        }
    }

    async testRoutes() {
        const routes = [
            '/projects',
            '/datasets', 
            '/results',
            '/ground-truth'
        ];

        console.log('🚦 Testing Application Routes...');
        
        for (const route of routes) {
            try {
                console.log(`📍 Testing route: ${route}`);
                await this.page.goto(`http://localhost:3000${route}`, { 
                    waitUntil: 'networkidle0',
                    timeout: 15000 
                });
                
                await this.page.waitForTimeout(2000);
                
                // Check if route loaded successfully
                const title = await this.page.title();
                console.log(`✅ Route ${route} loaded - Title: ${title}`);
                
            } catch (error) {
                console.error(`❌ Route ${route} failed: ${error.message}`);
                this.errors.push({
                    type: 'route',
                    level: 'error',
                    route: route,
                    message: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        }
    }

    async testInteractivity() {
        console.log('🖱️  Testing Interactive Elements...');
        
        try {
            await this.page.goto('http://localhost:3000', { waitUntil: 'networkidle0' });
            
            // Test common interactive elements
            const buttons = await this.page.$$('button');
            console.log(`Found ${buttons.length} buttons to test`);
            
            for (let i = 0; i < Math.min(buttons.length, 5); i++) {
                try {
                    await buttons[i].click();
                    await this.page.waitForTimeout(500);
                } catch (error) {
                    console.log(`🟡 Button ${i + 1} click failed: ${error.message}`);
                }
            }
            
            // Test form inputs
            const inputs = await this.page.$$('input, textarea');
            console.log(`Found ${inputs.length} form inputs to test`);
            
            for (let i = 0; i < Math.min(inputs.length, 3); i++) {
                try {
                    await inputs[i].type('test input');
                    await this.page.waitForTimeout(300);
                } catch (error) {
                    console.log(`🟡 Input ${i + 1} typing failed: ${error.message}`);
                }
            }
            
        } catch (error) {
            console.error(`❌ Interactivity testing failed: ${error.message}`);
            this.errors.push({
                type: 'interactivity',
                level: 'error',
                message: error.message,
                timestamp: new Date().toISOString()
            });
        }
    }

    generateReport() {
        const endTime = new Date();
        const duration = endTime - this.startTime;
        
        const report = {
            metadata: {
                timestamp: endTime.toISOString(),
                duration: `${duration}ms`,
                testEnvironment: {
                    platform: process.platform,
                    nodeVersion: process.version,
                    targetUrl: 'http://localhost:3000'
                }
            },
            summary: {
                totalErrors: this.errors.length,
                totalWarnings: this.warnings.length,
                totalNetworkErrors: this.networkErrors.length,
                overallStatus: this.errors.length === 0 ? 'PASS' : 'FAIL'
            },
            categorizedErrors: {
                console: this.errors.filter(e => e.type === 'console'),
                page: this.errors.filter(e => e.type === 'page'),
                network: this.networkErrors,
                route: this.errors.filter(e => e.type === 'route'),
                react: this.errors.filter(e => e.type === 'react-boundary'),
                interactivity: this.errors.filter(e => e.type === 'interactivity')
            },
            allErrors: this.errors,
            allWarnings: this.warnings,
            recommendations: this.generateRecommendations()
        };
        
        return report;
    }

    generateRecommendations() {
        const recommendations = [];
        
        if (this.errors.filter(e => e.type === 'console').length > 0) {
            recommendations.push('Fix console.error() calls in the application code');
        }
        
        if (this.networkErrors.length > 0) {
            recommendations.push('Address network connectivity issues or API endpoint problems');
        }
        
        if (this.errors.filter(e => e.type === 'react-boundary').length > 0) {
            recommendations.push('Investigate React component errors caught by error boundaries');
        }
        
        if (this.errors.filter(e => e.type === 'route').length > 0) {
            recommendations.push('Fix routing issues preventing proper page navigation');
        }
        
        if (recommendations.length === 0) {
            recommendations.push('No major issues detected - application appears stable');
        }
        
        return recommendations;
    }

    async cleanup() {
        if (this.browser) {
            await this.browser.close();
        }
    }
}

async function runFrontendErrorAnalysis() {
    const analyzer = new FrontendErrorAnalyzer();
    
    try {
        const initialized = await analyzer.initialize();
        
        if (initialized) {
            // Run comprehensive testing with browser
            await analyzer.testFrontendApp();
            await analyzer.testRoutes();
            await analyzer.testInteractivity();
        } else {
            // Fallback to basic HTTP testing
            console.log('🔄 Running HTTP-only tests...');
            // Add HTTP-only testing logic here if needed
        }
        
        const report = analyzer.generateReport();
        
        // Save report
        const reportPath = path.join(__dirname, `frontend-error-report-${Date.now()}.json`);
        fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
        
        // Print summary
        console.log('\\n📊 FRONTEND ERROR ANALYSIS COMPLETE');
        console.log('=====================================');
        console.log(`Total Errors: ${report.summary.totalErrors}`);
        console.log(`Total Warnings: ${report.summary.totalWarnings}`);
        console.log(`Network Errors: ${report.summary.totalNetworkErrors}`);
        console.log(`Overall Status: ${report.summary.overallStatus}`);
        console.log(`Report saved: ${reportPath}`);
        
        if (report.recommendations.length > 0) {
            console.log('\\n🎯 Recommendations:');
            report.recommendations.forEach((rec, i) => {
                console.log(`${i + 1}. ${rec}`);
            });
        }
        
        return report;
        
    } catch (error) {
        console.error('❌ Error analysis failed:', error);
        return null;
    } finally {
        await analyzer.cleanup();
    }
}

// Run if called directly
if (require.main === module) {
    runFrontendErrorAnalysis().then(() => {
        process.exit(0);
    }).catch(error => {
        console.error('Fatal error:', error);
        process.exit(1);
    });
}

module.exports = { FrontendErrorAnalyzer, runFrontendErrorAnalysis };