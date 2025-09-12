#!/usr/bin/env node

/**
 * Simple Frontend Tester - No external dependencies
 * Tests frontend without browser automation
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

class SimpleFrontendTester {
    constructor() {
        this.errors = [];
        this.warnings = [];
        this.networkErrors = [];
        this.testResults = [];
    }

    async testUrl(url, expectedStatus = 200) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            
            const request = http.get(url, (res) => {
                let data = '';
                
                res.on('data', chunk => {
                    data += chunk;
                });
                
                res.on('end', () => {
                    const endTime = Date.now();
                    const result = {
                        url: url,
                        status: res.statusCode,
                        statusText: res.statusMessage,
                        contentType: res.headers['content-type'],
                        contentLength: data.length,
                        responseTime: endTime - startTime,
                        success: res.statusCode === expectedStatus,
                        timestamp: new Date().toISOString()
                    };
                    
                    // Basic content analysis
                    if (data.includes('error') || data.includes('Error')) {
                        result.containsErrorText = true;
                        this.warnings.push({
                            type: 'content',
                            message: `Response from ${url} contains error text`,
                            url: url
                        });
                    }
                    
                    if (res.statusCode >= 400) {
                        this.networkErrors.push({
                            type: 'http',
                            url: url,
                            status: res.statusCode,
                            message: res.statusMessage
                        });
                    }
                    
                    this.testResults.push(result);
                    resolve(result);
                });
            });
            
            request.on('error', (error) => {
                this.errors.push({
                    type: 'network',
                    url: url,
                    message: error.message,
                    timestamp: new Date().toISOString()
                });
                reject(error);
            });
            
            request.setTimeout(10000, () => {
                request.destroy();
                reject(new Error(`Timeout testing ${url}`));
            });
        });
    }

    async testFrontendResources() {
        console.log('🧪 Testing Frontend Resources...');
        
        const resources = [
            'http://localhost:3000/',
            'http://localhost:3000/static/js/bundle.js',
            'http://localhost:3000/config.js',
            'http://localhost:3000/favicon.ico',
            'http://localhost:3000/manifest.json'
        ];
        
        for (const resource of resources) {
            try {
                console.log(`📡 Testing: ${resource}`);
                const result = await this.testUrl(resource);
                console.log(`   ✅ ${result.status} (${result.responseTime}ms, ${result.contentLength} bytes)`);
            } catch (error) {
                console.log(`   ❌ Failed: ${error.message}`);
            }
        }
    }

    async testApiEndpoints() {
        console.log('🔌 Testing API Endpoints...');
        
        const endpoints = [
            'http://localhost:8000/health',
            'http://localhost:8000/api/projects',
            'http://localhost:8000/api/datasets',
            'http://localhost:8000/docs'
        ];
        
        for (const endpoint of endpoints) {
            try {
                console.log(`🎯 Testing: ${endpoint}`);
                const result = await this.testUrl(endpoint);
                console.log(`   ✅ ${result.status} (${result.responseTime}ms)`);
            } catch (error) {
                console.log(`   ❌ Failed: ${error.message}`);
            }
        }
    }

    async testFrontendRoutes() {
        console.log('🚦 Testing Frontend Routes...');
        
        const routes = [
            'http://localhost:3000/projects',
            'http://localhost:3000/datasets',
            'http://localhost:3000/results',
            'http://localhost:3000/ground-truth'
        ];
        
        for (const route of routes) {
            try {
                console.log(`📍 Testing: ${route}`);
                const result = await this.testUrl(route);
                console.log(`   ✅ ${result.status} (${result.responseTime}ms)`);
            } catch (error) {
                console.log(`   ❌ Failed: ${error.message}`);
            }
        }
    }

    async analyzeJavaScriptBundle() {
        console.log('🔍 Analyzing JavaScript Bundle...');
        
        try {
            const result = await this.testUrl('http://localhost:3000/static/js/bundle.js');
            
            if (result.success) {
                // Get bundle content for analysis
                const bundleContent = await this.getUrlContent('http://localhost:3000/static/js/bundle.js');
                
                const analysis = {
                    size: bundleContent.length,
                    containsSourceMaps: bundleContent.includes('sourceMappingURL'),
                    containsReact: bundleContent.includes('React'),
                    containsReactDOM: bundleContent.includes('ReactDOM'),
                    containsErrorHandling: bundleContent.includes('componentDidCatch'),
                    containsConsoleError: bundleContent.includes('console.error'),
                    containsTypescript: bundleContent.includes('__typescript'),
                    minified: !bundleContent.includes('\\n  ') // Basic minification check
                };
                
                console.log('   📊 Bundle Analysis:');
                console.log(`      Size: ${(analysis.size / 1024 / 1024).toFixed(2)} MB`);
                console.log(`      Minified: ${analysis.minified}`);
                console.log(`      Source Maps: ${analysis.containsSourceMaps}`);
                console.log(`      React: ${analysis.containsReact}`);
                console.log(`      Error Handling: ${analysis.containsErrorHandling}`);
                
                // Check for common error patterns
                if (bundleContent.includes('Cannot read property')) {
                    this.warnings.push({
                        type: 'bundle',
                        message: 'Bundle contains "Cannot read property" errors',
                        severity: 'medium'
                    });
                }
                
                if (bundleContent.includes('undefined is not a function')) {
                    this.errors.push({
                        type: 'bundle',
                        message: 'Bundle contains function undefined errors',
                        severity: 'high'
                    });
                }
                
                return analysis;
            }
        } catch (error) {
            console.log(`   ❌ Bundle analysis failed: ${error.message}`);
        }
        
        return null;
    }

    async getUrlContent(url) {
        return new Promise((resolve, reject) => {
            http.get(url, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => resolve(data));
            }).on('error', reject);
        });
    }

    generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            summary: {
                totalTests: this.testResults.length,
                passedTests: this.testResults.filter(r => r.success).length,
                failedTests: this.testResults.filter(r => !r.success).length,
                totalErrors: this.errors.length,
                totalWarnings: this.warnings.length,
                networkErrors: this.networkErrors.length
            },
            testResults: this.testResults,
            errors: this.errors,
            warnings: this.warnings,
            networkErrors: this.networkErrors,
            recommendations: this.generateRecommendations()
        };
        
        return report;
    }

    generateRecommendations() {
        const recommendations = [];
        
        if (this.networkErrors.length > 0) {
            recommendations.push('Address network connectivity issues or missing resources');
        }
        
        if (this.errors.length > 0) {
            recommendations.push('Fix critical JavaScript errors in the application');
        }
        
        if (this.warnings.filter(w => w.type === 'bundle').length > 0) {
            recommendations.push('Review JavaScript bundle for runtime error patterns');
        }
        
        const failedApiTests = this.testResults.filter(r => r.url.includes(':8000') && !r.success);
        if (failedApiTests.length > 0) {
            recommendations.push('Backend API endpoints need attention - some are failing');
        }
        
        const failedFrontendTests = this.testResults.filter(r => r.url.includes(':3000') && !r.success);
        if (failedFrontendTests.length > 0) {
            recommendations.push('Frontend routing or static resources have issues');
        }
        
        if (recommendations.length === 0) {
            recommendations.push('Basic connectivity tests passed - deeper browser testing recommended');
        }
        
        return recommendations;
    }

    printReport() {
        const report = this.generateReport();
        
        console.log('\\n📊 SIMPLE FRONTEND TEST REPORT');
        console.log('================================');
        console.log(`Tests Run: ${report.summary.totalTests}`);
        console.log(`Passed: ${report.summary.passedTests}`);
        console.log(`Failed: ${report.summary.failedTests}`);
        console.log(`Errors: ${report.summary.totalErrors}`);
        console.log(`Warnings: ${report.summary.totalWarnings}`);
        console.log(`Network Errors: ${report.summary.networkErrors}`);
        
        if (report.errors.length > 0) {
            console.log('\\n🔴 ERRORS:');
            report.errors.forEach((error, i) => {
                console.log(`${i + 1}. [${error.type}] ${error.message}`);
            });
        }
        
        if (report.warnings.length > 0) {
            console.log('\\n🟡 WARNINGS:');
            report.warnings.forEach((warning, i) => {
                console.log(`${i + 1}. [${warning.type}] ${warning.message}`);
            });
        }
        
        console.log('\\n🎯 RECOMMENDATIONS:');
        report.recommendations.forEach((rec, i) => {
            console.log(`${i + 1}. ${rec}`);
        });
        
        return report;
    }
}

async function runSimpleFrontendTest() {
    const tester = new SimpleFrontendTester();
    
    try {
        await tester.testFrontendResources();
        await tester.testFrontendRoutes();
        await tester.testApiEndpoints();
        await tester.analyzeJavaScriptBundle();
        
        const report = tester.printReport();
        
        // Save report
        const reportPath = path.join(__dirname, `simple-frontend-test-${Date.now()}.json`);
        fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
        console.log(`\\n💾 Report saved: ${reportPath}`);
        
        return report;
    } catch (error) {
        console.error('❌ Test execution failed:', error);
        return null;
    }
}

// Run if called directly
if (require.main === module) {
    runSimpleFrontendTest().then(() => {
        process.exit(0);
    }).catch(error => {
        console.error('Fatal error:', error);
        process.exit(1);
    });
}

module.exports = { SimpleFrontendTester, runSimpleFrontendTest };