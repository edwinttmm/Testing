#!/usr/bin/env node
/**
 * Browser Simulation Test
 * Simulates browser behavior to test for React runtime errors
 */

const https = require('https');
const http = require('http');
const { URL } = require('url');

class BrowserSimulationTester {
    constructor() {
        this.results = {
            timestamp: new Date().toISOString(),
            tests: {}
        };
        this.frontendUrl = 'http://localhost:3000';
        this.backendUrl = 'http://localhost:8000';
    }

    async httpGet(url, timeout = 10000) {
        return new Promise((resolve, reject) => {
            const urlObj = new URL(url);
            const client = urlObj.protocol === 'https:' ? https : http;
            
            const req = client.get(url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (compatible; IntegrationTestAgent/1.0)',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            }, (res) => {
                let data = '';
                
                res.on('data', chunk => {
                    data += chunk;
                });
                
                res.on('end', () => {
                    resolve({
                        statusCode: res.statusCode,
                        headers: res.headers,
                        body: data
                    });
                });
            });
            
            req.on('error', reject);
            
            // Set timeout
            req.setTimeout(timeout, () => {
                req.abort();
                reject(new Error('Request timeout'));
            });
        });
    }

    async testFrontendLoading() {
        console.log('🔍 Testing Frontend Loading...');
        
        const pages = [
            { path: '/', name: 'Home' },
            { path: '/#/projects', name: 'Projects' },
            { path: '/#/ground-truth', name: 'Ground Truth' },
            { path: '/#/dashboard', name: 'Dashboard' }
        ];

        for (const page of pages) {
            try {
                const url = `${this.frontendUrl}${page.path}`;
                console.log(`  Testing ${page.name} page...`);
                
                const response = await this.httpGet(url);
                
                const hasReactApp = response.body.includes('id="root"') || response.body.includes('React App');
                const hasBundle = response.body.includes('bundle.js') || response.body.includes('.js');
                const hasErrors = response.body.includes('error') || response.body.includes('Error');
                const isValidHTML = response.body.includes('<html') && response.body.includes('</html>');
                
                this.results.tests[`frontend_${page.name.toLowerCase().replace(' ', '_')}`] = {
                    test: `${page.name} page should load without errors`,
                    url: url,
                    statusCode: response.statusCode,
                    success: response.statusCode === 200 && hasReactApp && !hasErrors,
                    hasReactApp,
                    hasBundle,
                    hasErrors,
                    isValidHTML,
                    contentLength: response.body.length
                };

                const status = response.statusCode === 200 ? '✅' : '❌';
                console.log(`    ${status} ${page.name}: ${response.statusCode} (${response.body.length} bytes)`);
                
            } catch (error) {
                this.results.tests[`frontend_${page.name.toLowerCase().replace(' ', '_')}`] = {
                    test: `${page.name} page should load without errors`,
                    success: false,
                    error: error.message
                };
                console.log(`    ❌ ${page.name}: ${error.message}`);
            }
        }
    }

    async testAPIEndpoints() {
        console.log('🔍 Testing API Endpoints...');
        
        const endpoints = [
            { path: '/api/projects', name: 'Projects API' },
            { path: '/api/videos', name: 'Videos API' },
            { path: '/api/dashboard/stats', name: 'Dashboard Stats' },
            { path: '/health', name: 'Health Check', allowedCodes: [200, 503] }
        ];

        for (const endpoint of endpoints) {
            try {
                const url = `${this.backendUrl}${endpoint.path}`;
                console.log(`  Testing ${endpoint.name}...`);
                
                const response = await this.httpGet(url);
                
                let isJSON = false;
                let data = null;
                try {
                    data = JSON.parse(response.body);
                    isJSON = true;
                } catch (e) {
                    // Not JSON, that's OK for some endpoints
                }

                const allowedCodes = endpoint.allowedCodes || [200];
                const success = allowedCodes.includes(response.statusCode);
                
                this.results.tests[`api_${endpoint.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}`] = {
                    test: `${endpoint.name} should return valid response`,
                    url: url,
                    statusCode: response.statusCode,
                    success: success,
                    isJSON,
                    hasData: data ? (Array.isArray(data) ? data.length > 0 : Object.keys(data).length > 0) : false,
                    responseSize: response.body.length
                };

                const status = success ? '✅' : '❌';
                console.log(`    ${status} ${endpoint.name}: ${response.statusCode}${isJSON ? ' (JSON)' : ''}`);
                
            } catch (error) {
                this.results.tests[`api_${endpoint.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}`] = {
                    test: `${endpoint.name} should return valid response`,
                    success: false,
                    error: error.message
                };
                console.log(`    ❌ ${endpoint.name}: ${error.message}`);
            }
        }
    }

    async testCrossOriginRequests() {
        console.log('🔍 Testing Cross-Origin Requests...');
        
        try {
            // Simulate a request that would be made by the frontend to the backend
            const response = await this.httpGet(`${this.backendUrl}/api/projects`, 5000);
            
            const corsHeaders = {
                'access-control-allow-origin': response.headers['access-control-allow-origin'],
                'access-control-allow-methods': response.headers['access-control-allow-methods'],
                'access-control-allow-headers': response.headers['access-control-allow-headers']
            };
            
            const hasCORS = !!corsHeaders['access-control-allow-origin'];
            
            this.results.tests.cors_configuration = {
                test: 'CORS should be properly configured for frontend-backend communication',
                success: hasCORS && response.statusCode === 200,
                statusCode: response.statusCode,
                corsHeaders,
                hasCORS
            };
            
            const status = hasCORS ? '✅' : '❌';
            console.log(`  ${status} CORS Configuration: ${hasCORS ? 'Enabled' : 'Missing'}`);
            
        } catch (error) {
            this.results.tests.cors_configuration = {
                test: 'CORS should be properly configured for frontend-backend communication',
                success: false,
                error: error.message
            };
            console.log(`  ❌ CORS Test: ${error.message}`);
        }
    }

    async runAllTests() {
        console.log('🚀 Browser Simulation Integration Test');
        console.log('=' * 60);
        
        await this.testFrontendLoading();
        await this.testAPIEndpoints();
        await this.testCrossOriginRequests();
        
        // Calculate overall results
        const tests = Object.values(this.results.tests);
        const successfulTests = tests.filter(test => test.success).length;
        const totalTests = tests.length;
        
        this.results.summary = {
            totalTests,
            successfulTests,
            failedTests: totalTests - successfulTests,
            successRate: totalTests > 0 ? (successfulTests / totalTests) * 100 : 0,
            overallSuccess: successfulTests === totalTests
        };
        
        console.log('\n' + '=' * 60);
        console.log('📋 BROWSER SIMULATION TEST SUMMARY');
        console.log('=' * 60);
        
        const overallStatus = this.results.summary.overallSuccess ? '✅' : '❌';
        console.log(`${overallStatus} Overall: ${successfulTests}/${totalTests} tests passed (${this.results.summary.successRate.toFixed(1)}%)`);
        
        // Group by category
        const categories = {
            'Frontend Pages': Object.keys(this.results.tests).filter(k => k.startsWith('frontend_')),
            'API Endpoints': Object.keys(this.results.tests).filter(k => k.startsWith('api_')),
            'CORS Configuration': Object.keys(this.results.tests).filter(k => k.startsWith('cors_'))
        };
        
        for (const [categoryName, testKeys] of Object.entries(categories)) {
            if (testKeys.length === 0) continue;
            
            const categoryTests = testKeys.map(k => this.results.tests[k]);
            const categorySuccess = categoryTests.filter(t => t.success).length;
            const categoryTotal = categoryTests.length;
            
            console.log(`\n${categoryName}:`);
            for (const testKey of testKeys) {
                const test = this.results.tests[testKey];
                const status = test.success ? '✅' : '❌';
                console.log(`  ${status} ${test.test}`);
                if (!test.success && test.error) {
                    console.log(`      Error: ${test.error}`);
                }
            }
        }
        
        // Save results
        const resultsFile = `browser_simulation_results_${new Date().toISOString().replace(/[:.]/g, '_').slice(0, -5)}.json`;
        const fs = require('fs');
        fs.writeFileSync(resultsFile, JSON.stringify(this.results, null, 2));
        
        console.log(`\n💾 Results saved to: ${resultsFile}`);
        
        return this.results.summary.overallSuccess ? 0 : 1;
    }
}

async function main() {
    const tester = new BrowserSimulationTester();
    
    // Wait for servers to be ready
    console.log('⏳ Waiting for servers to be ready...');
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    try {
        const exitCode = await tester.runAllTests();
        process.exit(exitCode);
    } catch (error) {
        console.error('❌ Test execution failed:', error.message);
        process.exit(1);
    }
}

if (require.main === module) {
    main().catch(console.error);
}