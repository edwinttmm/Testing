/**
 * BASIC ADVANCED FEATURE TEST SUITE
 * AI Model Validation Platform - Quick Feature Validation
 * 
 * This script performs basic testing of advanced features without complex dependencies
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

class BasicFeatureTestSuite {
    constructor() {
        this.frontendUrl = 'http://localhost:3000';
        this.backendUrl = 'http://localhost:8000';
        this.testResults = {
            timestamp: new Date().toISOString(),
            backend: {},
            frontend: {},
            issues: [],
            recommendations: []
        };
    }

    async runBasicTests() {
        console.log('🚀 STARTING BASIC ADVANCED FEATURE TESTS\n');
        
        try {
            // 1. Backend API Tests
            await this.testBackendApis();
            
            // 2. Frontend Accessibility Tests  
            await this.testFrontendAccess();
            
            // 3. Integration Tests
            await this.testBasicIntegration();
            
            // Generate report
            await this.generateReport();
            
        } catch (error) {
            console.error('❌ Basic test suite failed:', error);
            this.testResults.issues.push({
                component: 'Test Suite',
                severity: 'critical',
                issue: 'Test suite execution failed',
                error: error.message
            });
        }
    }

    async testBackendApis() {
        console.log('🔧 Testing Backend API Endpoints...');
        
        const endpoints = [
            { path: '/health', expected: 200, name: 'Health Check' },
            { path: '/api/dashboard/stats', expected: 200, name: 'Dashboard Stats' },
            { path: '/api/projects', expected: 200, name: 'Projects List' },
            { path: '/api/videos', expected: 200, name: 'Videos List' },
            { path: '/api/detection/models/available', expected: 200, name: 'Available Models' },
            { path: '/api/signals/protocols/supported', expected: 200, name: 'Signal Protocols' }
        ];

        const results = {};
        
        for (const endpoint of endpoints) {
            try {
                const response = await this.makeHttpRequest(this.backendUrl + endpoint.path);
                results[endpoint.name] = {
                    status: response.statusCode,
                    success: response.statusCode === endpoint.expected,
                    responseTime: response.responseTime,
                    dataSize: response.data ? response.data.length : 0
                };
                
                if (response.statusCode === endpoint.expected) {
                    console.log(`✅ ${endpoint.name}: ${response.statusCode} (${response.responseTime}ms)`);
                } else {
                    console.log(`❌ ${endpoint.name}: ${response.statusCode} (expected ${endpoint.expected})`);
                    this.testResults.issues.push({
                        component: 'Backend API',
                        severity: 'high',
                        issue: `${endpoint.name} returned ${response.statusCode}, expected ${endpoint.expected}`
                    });
                }
            } catch (error) {
                console.log(`❌ ${endpoint.name}: Failed - ${error.message}`);
                results[endpoint.name] = {
                    success: false,
                    error: error.message
                };
                this.testResults.issues.push({
                    component: 'Backend API',
                    severity: 'critical',
                    issue: `${endpoint.name} failed: ${error.message}`
                });
            }
        }
        
        this.testResults.backend = results;
        console.log('✅ Backend API testing completed\n');
    }

    async testFrontendAccess() {
        console.log('🌐 Testing Frontend Accessibility...');
        
        const frontendTests = {
            mainPage: false,
            staticAssets: false,
            jsErrors: false
        };

        try {
            // Test main page accessibility
            const mainPageResponse = await this.makeHttpRequest(this.frontendUrl);
            frontendTests.mainPage = mainPageResponse.statusCode === 200;
            
            if (frontendTests.mainPage) {
                console.log(`✅ Main Page: Accessible (${mainPageResponse.responseTime}ms)`);
                
                // Check for React app indicators in HTML
                const hasReact = mainPageResponse.data && (
                    mainPageResponse.data.includes('react') || 
                    mainPageResponse.data.includes('root') ||
                    mainPageResponse.data.includes('App')
                );
                
                if (hasReact) {
                    console.log('✅ React App: Detected in HTML');
                } else {
                    console.log('⚠️ React App: Not clearly detected in HTML');
                }
                
            } else {
                console.log(`❌ Main Page: Not accessible (${mainPageResponse.statusCode})`);
                this.testResults.issues.push({
                    component: 'Frontend Access',
                    severity: 'critical',
                    issue: `Frontend not accessible: ${mainPageResponse.statusCode}`
                });
            }
            
        } catch (error) {
            console.log(`❌ Frontend Access: ${error.message}`);
            this.testResults.issues.push({
                component: 'Frontend Access',
                severity: 'critical',
                issue: `Frontend access failed: ${error.message}`
            });
        }

        this.testResults.frontend = frontendTests;
        console.log('✅ Frontend accessibility testing completed\n');
    }

    async testBasicIntegration() {
        console.log('🔗 Testing Basic Integration...');
        
        const integrationTests = {
            backendToFrontend: false,
            dataFlow: false,
            apiResponseTimes: []
        };

        try {
            // Test data flow by checking if backend has data that frontend would display
            const projectsResponse = await this.makeHttpRequest(this.backendUrl + '/api/projects');
            const videosResponse = await this.makeHttpRequest(this.backendUrl + '/api/videos');
            const dashboardResponse = await this.makeHttpRequest(this.backendUrl + '/api/dashboard/stats');
            
            integrationTests.apiResponseTimes = [
                { endpoint: 'projects', time: projectsResponse.responseTime },
                { endpoint: 'videos', time: videosResponse.responseTime },
                { endpoint: 'dashboard', time: dashboardResponse.responseTime }
            ];
            
            // Check if we have meaningful data
            let projectsData, videosData, dashboardData;
            
            try {
                projectsData = JSON.parse(projectsResponse.data);
                videosData = JSON.parse(videosResponse.data);
                dashboardData = JSON.parse(dashboardResponse.data);
                
                integrationTests.dataFlow = !!(
                    (Array.isArray(projectsData) && projectsData.length > 0) ||
                    (videosData.videos && videosData.videos.length > 0) ||
                    (dashboardData.projectCount !== undefined)
                );
                
                if (integrationTests.dataFlow) {
                    console.log('✅ Data Flow: Backend has data for frontend');
                    console.log(`   📊 Projects: ${projectsData.length || 0}`);
                    console.log(`   🎥 Videos: ${videosData.videos ? videosData.videos.length : 0}`);
                    console.log(`   📈 Dashboard: ${JSON.stringify(dashboardData)}`);
                } else {
                    console.log('⚠️ Data Flow: Limited data available');
                }
                
            } catch (parseError) {
                console.log('⚠️ Data Flow: Could not parse API responses');
                this.testResults.issues.push({
                    component: 'Integration',
                    severity: 'medium',
                    issue: 'API responses not in expected JSON format'
                });
            }
            
            // Check performance thresholds
            const slowApis = integrationTests.apiResponseTimes.filter(api => api.time > 1000);
            if (slowApis.length > 0) {
                console.log(`⚠️ Performance: ${slowApis.length} APIs are slow (>1s)`);
                slowApis.forEach(api => {
                    console.log(`   📡 ${api.endpoint}: ${api.time}ms`);
                });
                
                this.testResults.issues.push({
                    component: 'Performance',
                    severity: 'medium',
                    issue: `Slow API responses detected: ${slowApis.map(a => a.endpoint).join(', ')}`
                });
            } else {
                console.log('✅ Performance: All APIs respond within acceptable time');
            }
            
        } catch (error) {
            console.log(`❌ Integration Testing: ${error.message}`);
            this.testResults.issues.push({
                component: 'Integration',
                severity: 'high',
                issue: `Integration testing failed: ${error.message}`
            });
        }

        this.testResults.integration = integrationTests;
        console.log('✅ Basic integration testing completed\n');
    }

    async makeHttpRequest(url, options = {}) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const urlObj = new URL(url);
            const client = urlObj.protocol === 'https:' ? https : http;
            
            const req = client.get(url, {
                timeout: 10000,
                ...options
            }, (res) => {
                let data = '';
                
                res.on('data', (chunk) => {
                    data += chunk;
                });
                
                res.on('end', () => {
                    resolve({
                        statusCode: res.statusCode,
                        headers: res.headers,
                        data: data,
                        responseTime: Date.now() - startTime
                    });
                });
            });
            
            req.on('error', reject);
            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timeout'));
            });
        });
    }

    async generateReport() {
        console.log('📋 Generating Basic Test Report...');
        
        // Calculate summary statistics
        const backendTests = Object.values(this.testResults.backend);
        const backendSuccess = backendTests.filter(test => test.success).length;
        const backendTotal = backendTests.length;
        
        const criticalIssues = this.testResults.issues.filter(i => i.severity === 'critical').length;
        const highIssues = this.testResults.issues.filter(i => i.severity === 'high').length;
        const mediumIssues = this.testResults.issues.filter(i => i.severity === 'medium').length;
        
        const summary = {
            timestamp: this.testResults.timestamp,
            backendApiTests: {
                passed: backendSuccess,
                total: backendTotal,
                successRate: backendTotal > 0 ? `${((backendSuccess / backendTotal) * 100).toFixed(1)}%` : '0%'
            },
            frontendTests: {
                mainPageAccessible: this.testResults.frontend.mainPage
            },
            integrationTests: {
                dataFlowWorking: this.testResults.integration?.dataFlow || false
            },
            issues: {
                critical: criticalIssues,
                high: highIssues,
                medium: mediumIssues,
                total: this.testResults.issues.length
            },
            overallStatus: criticalIssues === 0 ? (highIssues === 0 ? 'GOOD' : 'WARNING') : 'CRITICAL'
        };
        
        // Generate recommendations
        this.generateRecommendations(summary);
        
        // Save detailed report
        const reportPath = path.join(__dirname, `basic_feature_test_report_${Date.now()}.json`);
        const fullReport = {
            summary,
            detailedResults: this.testResults,
            recommendations: this.testResults.recommendations
        };
        
        fs.writeFileSync(reportPath, JSON.stringify(fullReport, null, 2));
        
        // Display console summary
        console.log('\n🎯 BASIC ADVANCED FEATURE TEST RESULTS');
        console.log('=====================================');
        console.log(`Overall Status: ${summary.overallStatus}`);
        console.log(`Backend APIs: ${summary.backendApiTests.passed}/${summary.backendApiTests.total} (${summary.backendApiTests.successRate})`);
        console.log(`Frontend: ${summary.frontendTests.mainPageAccessible ? 'Accessible' : 'Not Accessible'}`);
        console.log(`Integration: ${summary.integrationTests.dataFlowWorking ? 'Working' : 'Issues Detected'}`);
        console.log(`Issues: ${summary.issues.critical} Critical, ${summary.issues.high} High, ${summary.issues.medium} Medium`);
        console.log(`Report: ${reportPath}`);
        
        if (this.testResults.issues.length > 0) {
            console.log('\n🔍 ISSUES FOUND:');
            this.testResults.issues.forEach((issue, index) => {
                console.log(`${index + 1}. [${issue.severity.toUpperCase()}] ${issue.component}: ${issue.issue}`);
            });
        }
        
        if (this.testResults.recommendations.length > 0) {
            console.log('\n💡 RECOMMENDATIONS:');
            this.testResults.recommendations.forEach((rec, index) => {
                console.log(`${index + 1}. [${rec.priority.toUpperCase()}] ${rec.category}: ${rec.recommendation}`);
            });
        }
        
        console.log('\n✅ Basic Advanced Feature Testing Completed!');
        
        return fullReport;
    }

    generateRecommendations(summary) {
        if (summary.backendApiTests.successRate !== '100%') {
            this.testResults.recommendations.push({
                category: 'Backend API',
                priority: 'high',
                recommendation: 'Fix failing backend API endpoints to ensure full functionality'
            });
        }
        
        if (!summary.frontendTests.mainPageAccessible) {
            this.testResults.recommendations.push({
                category: 'Frontend',
                priority: 'critical',
                recommendation: 'Frontend application is not accessible - check if React development server is running'
            });
        }
        
        if (!summary.integrationTests.dataFlowWorking) {
            this.testResults.recommendations.push({
                category: 'Integration',
                priority: 'medium',
                recommendation: 'Consider adding test data to demonstrate system functionality'
            });
        }
        
        if (summary.issues.critical > 0) {
            this.testResults.recommendations.push({
                category: 'System Stability',
                priority: 'critical',
                recommendation: 'Address critical issues immediately - system may not function properly'
            });
        }
        
        // Performance recommendations
        const integration = this.testResults.integration;
        if (integration && integration.apiResponseTimes) {
            const avgResponseTime = integration.apiResponseTimes.reduce((sum, api) => sum + api.time, 0) / integration.apiResponseTimes.length;
            if (avgResponseTime > 500) {
                this.testResults.recommendations.push({
                    category: 'Performance',
                    priority: 'medium',
                    recommendation: `API response times averaging ${avgResponseTime.toFixed(0)}ms - consider optimization`
                });
            }
        }
    }
}

// Main execution function
async function runBasicAdvancedFeatureTests() {
    const testSuite = new BasicFeatureTestSuite();
    
    try {
        const report = await testSuite.runBasicTests();
        return report;
    } catch (error) {
        console.error('💥 Basic test execution failed:', error);
        throw error;
    }
}

// Export for use in other modules
module.exports = { BasicFeatureTestSuite, runBasicAdvancedFeatureTests };

// Run if called directly
if (require.main === module) {
    runBasicAdvancedFeatureTests()
        .then(() => {
            process.exit(0);
        })
        .catch(error => {
            console.error('Test execution failed:', error);
            process.exit(1);
        });
}