#!/usr/bin/env node
/**
 * MINGW64 Validation Report Generator
 * Consolidates all validation test results into a comprehensive report
 */

const fs = require('fs');
const path = require('path');

class ValidationReportGenerator {
    constructor(timestamp) {
        this.timestamp = timestamp || new Date().toISOString().replace(/:/g, '-').split('.')[0];
        this.resultsDir = path.join(__dirname, '../../mingw64-validation/results');
        this.report = {
            metadata: {
                timestamp: this.timestamp,
                platform: process.platform,
                architecture: process.arch,
                nodeVersion: process.version,
                environment: 'MINGW64'
            },
            summary: {
                totalTests: 0,
                passed: 0,
                failed: 0,
                warnings: 0,
                skipped: 0
            },
            categories: {},
            recommendations: [],
            criticalIssues: [],
            performanceMetrics: {},
            compatibilityMatrix: {}
        };
    }

    async generateReport() {
        console.log('📊 Generating MINGW64 Validation Report...\n');

        try {
            await this.collectResults();
            this.analyzeResults();
            this.generateRecommendations();
            this.createCompatibilityMatrix();
            this.writeReports();
            this.displaySummary();
        } catch (error) {
            console.error('❌ Report generation failed:', error.message);
            process.exit(1);
        }
    }

    async collectResults() {
        console.log('🔍 Collecting test results...');

        const resultFiles = [
            { name: 'environment', file: `environment_${this.timestamp}.log` },
            { name: 'dependencies', file: `dependencies_${this.timestamp}.log` },
            { name: 'cross-platform', file: `cross-platform_${this.timestamp}.log` },
            { name: 'build', file: `build_${this.timestamp}.log` },
            { name: 'runtime', file: `runtime_${this.timestamp}.log` },
            { name: 'gpu-fallback', file: `gpu-fallback_${this.timestamp}.log` },
            { name: 'performance', file: `performance_${this.timestamp}.log` },
            { name: 'cicd', file: `cicd_${this.timestamp}.log` }
        ];

        for (const result of resultFiles) {
            const filePath = path.join(this.resultsDir, result.file);
            
            if (fs.existsSync(filePath)) {
                const content = fs.readFileSync(filePath, 'utf8');
                this.report.categories[result.name] = this.parseLogFile(content, result.name);
                console.log(`  ✅ Processed ${result.name} results`);
            } else {
                console.log(`  ⚠️  ${result.name} results not found`);
                this.report.categories[result.name] = {
                    status: 'skipped',
                    tests: [],
                    summary: { passed: 0, failed: 0, warnings: 0, skipped: 1 }
                };
            }
        }

        // Also check for validation-report.json from the main validator
        const validationReportPath = path.join(__dirname, '../../mingw64-validation/validation-report.json');
        if (fs.existsSync(validationReportPath)) {
            const validationReport = JSON.parse(fs.readFileSync(validationReportPath, 'utf8'));
            this.mergeValidationReport(validationReport);
            console.log('  ✅ Merged main validation report');
        }
    }

    parseLogFile(content, category) {
        const lines = content.split('\n');
        const result = {
            status: 'unknown',
            tests: [],
            summary: { passed: 0, failed: 0, warnings: 0, skipped: 0 },
            details: {},
            issues: []
        };

        let currentTest = null;
        let inTestSection = false;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();

            // Detect test sections
            if (line.match(/^\[\d+\/\d+\]/)) {
                if (currentTest) {
                    result.tests.push(currentTest);
                }

                currentTest = {
                    name: line.replace(/^\[\d+\/\d+\]\s*/, ''),
                    status: 'unknown',
                    details: [],
                    startLine: i
                };
                inTestSection = true;
            }

            // Detect test results
            if (line.includes('✅')) {
                const testName = line.replace(/.*✅\s*/, '');
                if (currentTest) {
                    currentTest.status = 'passed';
                    currentTest.details.push(testName);
                }
                result.summary.passed++;
            } else if (line.includes('❌')) {
                const testName = line.replace(/.*❌\s*/, '');
                if (currentTest) {
                    currentTest.status = 'failed';
                    currentTest.details.push(testName);
                }
                result.summary.failed++;
                result.issues.push(testName);
            } else if (line.includes('⚠️')) {
                const testName = line.replace(/.*⚠️\s*/, '');
                if (currentTest) {
                    if (currentTest.status !== 'failed') {
                        currentTest.status = 'warning';
                    }
                    currentTest.details.push(testName);
                }
                result.summary.warnings++;
            }

            // Detect summary sections
            if (line.includes('Summary') || line.includes('Passed:') || line.includes('Failed:')) {
                const passedMatch = line.match(/Passed:\s*(\d+)/);
                const failedMatch = line.match(/Failed:\s*(\d+)/);
                
                if (passedMatch) result.summary.passed = parseInt(passedMatch[1]);
                if (failedMatch) result.summary.failed = parseInt(failedMatch[1]);
            }
        }

        // Add the last test
        if (currentTest) {
            result.tests.push(currentTest);
        }

        // Determine overall status
        if (result.summary.failed > 0) {
            result.status = 'failed';
        } else if (result.summary.warnings > 0) {
            result.status = 'warning';
        } else if (result.summary.passed > 0) {
            result.status = 'passed';
        } else {
            result.status = 'skipped';
        }

        return result;
    }

    mergeValidationReport(validationReport) {
        // Merge validation report data
        if (validationReport.results) {
            Object.keys(validationReport.results).forEach(category => {
                const categoryData = validationReport.results[category];
                if (this.report.categories[category]) {
                    // Merge additional details
                    this.report.categories[category].validationDetails = categoryData;
                } else {
                    this.report.categories[category] = {
                        status: categoryData.failed > 0 ? 'failed' : categoryData.warnings > 0 ? 'warning' : 'passed',
                        tests: [],
                        summary: {
                            passed: categoryData.passed || 0,
                            failed: categoryData.failed || 0,
                            warnings: categoryData.warnings || 0,
                            skipped: 0
                        },
                        validationDetails: categoryData
                    };
                }
            });
        }
    }

    analyzeResults() {
        console.log('📈 Analyzing results...');

        // Calculate total summary
        Object.values(this.report.categories).forEach(category => {
            this.report.summary.totalTests += (category.summary.passed + category.summary.failed + category.summary.warnings + category.summary.skipped);
            this.report.summary.passed += category.summary.passed;
            this.report.summary.failed += category.summary.failed;
            this.report.summary.warnings += category.summary.warnings;
            this.report.summary.skipped += category.summary.skipped;

            // Collect critical issues
            if (category.status === 'failed' && category.issues) {
                this.report.criticalIssues.push(...category.issues.map(issue => ({
                    category: category.name,
                    issue: issue,
                    severity: 'high'
                })));
            }
        });

        // Calculate success rate
        const totalAttempted = this.report.summary.totalTests - this.report.summary.skipped;
        this.report.summary.successRate = totalAttempted > 0 ? 
            ((this.report.summary.passed / totalAttempted) * 100).toFixed(2) : 0;

        // Performance metrics analysis
        this.analyzePerformanceMetrics();
    }

    analyzePerformanceMetrics() {
        const performance = this.report.categories.performance;
        if (performance && performance.validationDetails) {
            this.report.performanceMetrics = {
                buildTime: 'Not measured',
                bundleSize: 'Not measured',
                startupTime: 'Not measured',
                memoryUsage: 'Not measured',
                overall: performance.status
            };
        }
    }

    generateRecommendations() {
        console.log('💡 Generating recommendations...');

        const recommendations = [];

        // Environment recommendations
        if (this.report.categories.environment && this.report.categories.environment.status === 'failed') {
            recommendations.push({
                category: 'environment',
                priority: 'high',
                title: 'Fix Environment Issues',
                description: 'Critical environment setup issues detected that may prevent development.',
                actions: [
                    'Verify MSYS2/MINGW64 installation',
                    'Check PATH configuration',
                    'Ensure Node.js and npm are properly installed',
                    'Verify Windows version compatibility'
                ]
            });
        }

        // Dependency recommendations
        if (this.report.categories.dependencies && this.report.categories.dependencies.status !== 'passed') {
            recommendations.push({
                category: 'dependencies',
                priority: 'high',
                title: 'Resolve Dependency Issues',
                description: 'Dependency conflicts or compatibility issues found.',
                actions: [
                    'Run npm audit to check for vulnerabilities',
                    'Update React and TypeScript to compatible versions',
                    'Verify Material-UI compatibility with React 19',
                    'Check for peer dependency warnings'
                ]
            });
        }

        // Cross-platform recommendations
        if (this.report.categories['cross-platform'] && this.report.categories['cross-platform'].status !== 'passed') {
            recommendations.push({
                category: 'cross-platform',
                priority: 'medium',
                title: 'Improve Cross-Platform Compatibility',
                description: 'Some cross-platform features may not work correctly.',
                actions: [
                    'Use path.posix for consistent path handling',
                    'Configure proper line ending handling in Git',
                    'Test file permissions on Windows',
                    'Verify Unicode support in development tools'
                ]
            });
        }

        // Build recommendations
        if (this.report.categories.build && this.report.categories.build.status !== 'passed') {
            recommendations.push({
                category: 'build',
                priority: 'high',
                title: 'Fix Build Process',
                description: 'Build process issues detected that may prevent deployment.',
                actions: [
                    'Fix TypeScript compilation errors',
                    'Optimize build performance',
                    'Configure proper production build settings',
                    'Test build artifacts in target environment'
                ]
            });
        }

        // Performance recommendations
        if (this.report.categories.performance && this.report.categories.performance.status !== 'passed') {
            recommendations.push({
                category: 'performance',
                priority: 'medium',
                title: 'Optimize Performance',
                description: 'Performance issues may affect user experience.',
                actions: [
                    'Optimize bundle size through code splitting',
                    'Implement lazy loading for large components',
                    'Configure proper caching strategies',
                    'Monitor memory usage and fix leaks'
                ]
            });
        }

        // GPU/Fallback recommendations
        if (this.report.categories['gpu-fallback'] && this.report.categories['gpu-fallback'].status !== 'passed') {
            recommendations.push({
                category: 'gpu-fallback',
                priority: 'medium',
                title: 'Improve Hardware Compatibility',
                description: 'GPU fallback mechanisms may not work properly.',
                actions: [
                    'Test WebGL fallback to Canvas 2D',
                    'Implement progressive enhancement',
                    'Add hardware capability detection',
                    'Optimize CPU-based rendering paths'
                ]
            });
        }

        // CI/CD recommendations
        if (this.report.categories.cicd && this.report.categories.cicd.status !== 'passed') {
            recommendations.push({
                category: 'cicd',
                priority: 'low',
                title: 'Enhance CI/CD Compatibility',
                description: 'Automation and deployment processes could be improved.',
                actions: [
                    'Add comprehensive test scripts',
                    'Configure environment variable handling',
                    'Set up proper Docker configuration',
                    'Add security scanning to CI pipeline'
                ]
            });
        }

        this.report.recommendations = recommendations;
    }

    createCompatibilityMatrix() {
        this.report.compatibilityMatrix = {
            'Windows 10/11': this.getCompatibilityStatus(['environment', 'cross-platform']),
            'MINGW64': this.getCompatibilityStatus(['environment', 'build']),
            'Node.js 18+': this.getCompatibilityStatus(['environment', 'dependencies']),
            'React 19.1.1': this.getCompatibilityStatus(['dependencies', 'build', 'runtime']),
            'TypeScript 5+': this.getCompatibilityStatus(['dependencies', 'build']),
            'Material-UI 7+': this.getCompatibilityStatus(['dependencies', 'runtime']),
            'WebGL/Canvas': this.getCompatibilityStatus(['gpu-fallback', 'runtime']),
            'CI/CD Systems': this.getCompatibilityStatus(['cicd', 'build']),
            'Docker': this.getCompatibilityStatus(['cicd']),
            'Production Build': this.getCompatibilityStatus(['build', 'performance'])
        };
    }

    getCompatibilityStatus(categories) {
        const statuses = categories.map(cat => this.report.categories[cat]?.status || 'unknown');
        
        if (statuses.includes('failed')) return '❌ Incompatible';
        if (statuses.includes('warning')) return '⚠️ Partial';
        if (statuses.every(status => status === 'passed')) return '✅ Compatible';
        return '❓ Unknown';
    }

    writeReports() {
        console.log('📝 Writing reports...');

        // Write JSON report
        const jsonReportPath = path.join(this.resultsDir, `comprehensive-report-${this.timestamp}.json`);
        fs.writeFileSync(jsonReportPath, JSON.stringify(this.report, null, 2));

        // Write HTML report
        this.writeHTMLReport();

        // Write text summary
        this.writeTextSummary();

        console.log(`  ✅ JSON report: ${jsonReportPath}`);
    }

    writeHTMLReport() {
        const htmlReportPath = path.join(this.resultsDir, `report-${this.timestamp}.html`);
        
        const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MINGW64 Validation Report - ${this.timestamp}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; line-height: 1.6; }
        .header { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric { background: white; padding: 20px; border-radius: 8px; border: 1px solid #e9ecef; text-align: center; }
        .metric h3 { margin: 0 0 10px 0; color: #495057; }
        .metric .value { font-size: 2em; font-weight: bold; }
        .passed { color: #28a745; }
        .failed { color: #dc3545; }
        .warning { color: #ffc107; }
        .skipped { color: #6c757d; }
        .category { margin-bottom: 30px; }
        .category h2 { color: #495057; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; }
        .test { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .recommendations { background: #e3f2fd; padding: 20px; border-radius: 8px; margin-top: 30px; }
        .recommendation { background: white; margin: 10px 0; padding: 15px; border-radius: 5px; border-left: 4px solid #2196f3; }
        .compatibility-matrix { margin-top: 30px; }
        .compatibility-matrix table { width: 100%; border-collapse: collapse; }
        .compatibility-matrix th, .compatibility-matrix td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .compatibility-matrix th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔧 MINGW64 Dependency Validation Report</h1>
        <p><strong>Generated:</strong> ${this.timestamp}</p>
        <p><strong>Environment:</strong> ${this.report.metadata.environment} (${this.report.metadata.platform}/${this.report.metadata.architecture})</p>
        <p><strong>Node.js:</strong> ${this.report.metadata.nodeVersion}</p>
    </div>

    <div class="summary">
        <div class="metric">
            <h3>Total Tests</h3>
            <div class="value">${this.report.summary.totalTests}</div>
        </div>
        <div class="metric">
            <h3>Passed</h3>
            <div class="value passed">${this.report.summary.passed}</div>
        </div>
        <div class="metric">
            <h3>Failed</h3>
            <div class="value failed">${this.report.summary.failed}</div>
        </div>
        <div class="metric">
            <h3>Warnings</h3>
            <div class="value warning">${this.report.summary.warnings}</div>
        </div>
        <div class="metric">
            <h3>Success Rate</h3>
            <div class="value">${this.report.summary.successRate}%</div>
        </div>
    </div>

    ${this.generateCategoryHTML()}
    ${this.generateCompatibilityMatrixHTML()}
    ${this.generateRecommendationsHTML()}

</body>
</html>`;

        fs.writeFileSync(htmlReportPath, html);
        console.log(`  ✅ HTML report: ${htmlReportPath}`);
    }

    generateCategoryHTML() {
        return Object.entries(this.report.categories).map(([name, data]) => `
            <div class="category">
                <h2>${name.charAt(0).toUpperCase() + name.slice(1)} - ${this.getStatusEmoji(data.status)} ${data.status}</h2>
                <p><strong>Summary:</strong> ${data.summary.passed} passed, ${data.summary.failed} failed, ${data.summary.warnings} warnings</p>
                ${data.tests.map(test => `
                    <div class="test">
                        <strong>${this.getStatusEmoji(test.status)} ${test.name}</strong>
                        ${test.details.length > 0 ? `<ul>${test.details.map(detail => `<li>${detail}</li>`).join('')}</ul>` : ''}
                    </div>
                `).join('')}
            </div>
        `).join('');
    }

    generateCompatibilityMatrixHTML() {
        return `
            <div class="compatibility-matrix">
                <h2>🔄 Compatibility Matrix</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Component</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${Object.entries(this.report.compatibilityMatrix).map(([component, status]) => `
                            <tr>
                                <td>${component}</td>
                                <td>${status}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    generateRecommendationsHTML() {
        if (this.report.recommendations.length === 0) {
            return '<div class="recommendations"><h2>✅ No Recommendations</h2><p>All systems are functioning properly!</p></div>';
        }

        return `
            <div class="recommendations">
                <h2>💡 Recommendations</h2>
                ${this.report.recommendations.map(rec => `
                    <div class="recommendation">
                        <h3>🔧 ${rec.title} (${rec.priority} priority)</h3>
                        <p>${rec.description}</p>
                        <ul>
                            ${rec.actions.map(action => `<li>${action}</li>`).join('')}
                        </ul>
                    </div>
                `).join('')}
            </div>
        `;
    }

    writeTextSummary() {
        const summaryPath = path.join(this.resultsDir, `summary-${this.timestamp}.txt`);
        
        const summary = `
MINGW64 DEPENDENCY VALIDATION SUMMARY
=====================================
Generated: ${this.timestamp}
Environment: ${this.report.metadata.environment}
Platform: ${this.report.metadata.platform}/${this.report.metadata.architecture}
Node.js: ${this.report.metadata.nodeVersion}

OVERALL RESULTS
===============
Total Tests: ${this.report.summary.totalTests}
Passed: ${this.report.summary.passed}
Failed: ${this.report.summary.failed}
Warnings: ${this.report.summary.warnings}
Skipped: ${this.report.summary.skipped}
Success Rate: ${this.report.summary.successRate}%

CATEGORY BREAKDOWN
==================
${Object.entries(this.report.categories).map(([name, data]) => 
`${name.toUpperCase()}: ${data.status} (${data.summary.passed}P/${data.summary.failed}F/${data.summary.warnings}W)`
).join('\n')}

COMPATIBILITY MATRIX
====================
${Object.entries(this.report.compatibilityMatrix).map(([component, status]) => 
`${component}: ${status}`
).join('\n')}

${this.report.recommendations.length > 0 ? `
RECOMMENDATIONS
===============
${this.report.recommendations.map((rec, i) => 
`${i + 1}. ${rec.title} (${rec.priority})
   ${rec.description}
   Actions: ${rec.actions.join(', ')}
`).join('\n')}
` : 'No recommendations - all systems functioning properly!'}

CRITICAL ISSUES
===============
${this.report.criticalIssues.length > 0 ? 
    this.report.criticalIssues.map(issue => `- ${issue.category}: ${issue.issue}`).join('\n') :
    'No critical issues detected.'
}
`;

        fs.writeFileSync(summaryPath, summary.trim());
        console.log(`  ✅ Text summary: ${summaryPath}`);
    }

    getStatusEmoji(status) {
        const emojis = {
            'passed': '✅',
            'failed': '❌',
            'warning': '⚠️',
            'skipped': '⏭️',
            'unknown': '❓'
        };
        return emojis[status] || '❓';
    }

    displaySummary() {
        console.log('\n' + '='.repeat(60));
        console.log('📊 MINGW64 VALIDATION REPORT SUMMARY');
        console.log('='.repeat(60));
        console.log(`📅 Generated: ${this.timestamp}`);
        console.log(`🎯 Success Rate: ${this.report.summary.successRate}%`);
        console.log(`✅ Passed: ${this.report.summary.passed}`);
        console.log(`❌ Failed: ${this.report.summary.failed}`);
        console.log(`⚠️  Warnings: ${this.report.summary.warnings}`);
        console.log(`⏭️  Skipped: ${this.report.summary.skipped}`);
        
        if (this.report.criticalIssues.length > 0) {
            console.log(`\n🚨 Critical Issues: ${this.report.criticalIssues.length}`);
        }

        if (this.report.recommendations.length > 0) {
            console.log(`💡 Recommendations: ${this.report.recommendations.length}`);
        }

        console.log('\n📄 Reports Generated:');
        console.log(`  - JSON: comprehensive-report-${this.timestamp}.json`);
        console.log(`  - HTML: report-${this.timestamp}.html`);
        console.log(`  - Text: summary-${this.timestamp}.txt`);
        
        console.log('='.repeat(60) + '\n');
    }
}

// CLI Interface
if (require.main === module) {
    const timestamp = process.argv[2] || new Date().toISOString().replace(/:/g, '-').split('.')[0];
    const generator = new ValidationReportGenerator(timestamp);
    
    generator.generateReport()
        .then(() => {
            console.log('✅ Report generation completed successfully!');
            process.exit(0);
        })
        .catch((error) => {
            console.error('❌ Report generation failed:', error.message);
            process.exit(1);
        });
}

module.exports = ValidationReportGenerator;