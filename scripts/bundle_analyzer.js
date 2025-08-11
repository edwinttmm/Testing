#!/usr/bin/env node
/**
 * Bundle Size Analysis Script
 * Analyzes webpack bundle and provides optimization recommendations
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class BundleAnalyzer {
    constructor(buildDir = 'build') {
        this.buildDir = buildDir;
        this.staticDir = path.join(buildDir, 'static');
        this.jsDir = path.join(this.staticDir, 'js');
        this.cssDir = path.join(this.staticDir, 'css');
    }

    analyzeBundleSizes() {
        const analysis = {
            timestamp: new Date().toISOString(),
            totalSize: 0,
            gzippedSize: 0,
            files: {
                javascript: [],
                css: [],
                assets: []
            },
            recommendations: []
        };

        try {
            // Analyze JavaScript files
            if (fs.existsSync(this.jsDir)) {
                const jsFiles = fs.readdirSync(this.jsDir);
                for (const file of jsFiles) {
                    if (file.endsWith('.js')) {
                        const filePath = path.join(this.jsDir, file);
                        const stats = fs.statSync(filePath);
                        const sizeKB = Math.round(stats.size / 1024);
                        
                        analysis.files.javascript.push({
                            name: file,
                            size: stats.size,
                            sizeKB: sizeKB,
                            type: this.getFileType(file)
                        });
                        
                        analysis.totalSize += stats.size;
                    }
                }
            }

            // Analyze CSS files
            if (fs.existsSync(this.cssDir)) {
                const cssFiles = fs.readdirSync(this.cssDir);
                for (const file of cssFiles) {
                    if (file.endsWith('.css')) {
                        const filePath = path.join(this.cssDir, file);
                        const stats = fs.statSync(filePath);
                        const sizeKB = Math.round(stats.size / 1024);
                        
                        analysis.files.css.push({
                            name: file,
                            size: stats.size,
                            sizeKB: sizeKB
                        });
                        
                        analysis.totalSize += stats.size;
                    }
                }
            }

            // Sort files by size
            analysis.files.javascript.sort((a, b) => b.size - a.size);
            analysis.files.css.sort((a, b) => b.size - a.size);

            // Calculate total sizes
            analysis.totalSizeKB = Math.round(analysis.totalSize / 1024);
            analysis.totalSizeMB = Math.round(analysis.totalSize / 1024 / 1024 * 100) / 100;

            // Generate recommendations
            analysis.recommendations = this.generateRecommendations(analysis);

            return analysis;

        } catch (error) {
            console.error('Error analyzing bundle:', error);
            return { error: error.message };
        }
    }

    getFileType(filename) {
        if (filename.includes('main.')) return 'main';
        if (filename.includes('chunk.')) return 'chunk';
        if (filename.includes('vendor.')) return 'vendor';
        if (filename.match(/^\d+\./)) return 'chunk';
        return 'unknown';
    }

    generateRecommendations(analysis) {
        const recommendations = [];

        // Check total bundle size
        if (analysis.totalSizeMB > 5) {
            recommendations.push({
                type: 'critical',
                category: 'bundle-size',
                message: `Total bundle size (${analysis.totalSizeMB}MB) is very large. Consider aggressive code splitting.`,
                impact: 'high'
            });
        } else if (analysis.totalSizeMB > 2) {
            recommendations.push({
                type: 'warning',
                category: 'bundle-size',
                message: `Total bundle size (${analysis.totalSizeMB}MB) could be optimized. Target < 2MB.`,
                impact: 'medium'
            });
        }

        // Check individual JavaScript files
        const largeJSFiles = analysis.files.javascript.filter(f => f.sizeKB > 500);
        if (largeJSFiles.length > 0) {
            recommendations.push({
                type: 'warning',
                category: 'large-files',
                message: `Large JavaScript files detected: ${largeJSFiles.map(f => `${f.name} (${f.sizeKB}KB)`).join(', ')}`,
                impact: 'medium',
                solution: 'Implement code splitting and lazy loading'
            });
        }

        // Check for missing code splitting
        const mainFiles = analysis.files.javascript.filter(f => f.type === 'main');
        const chunkFiles = analysis.files.javascript.filter(f => f.type === 'chunk');
        
        if (mainFiles.length > 0 && chunkFiles.length === 0) {
            recommendations.push({
                type: 'info',
                category: 'code-splitting',
                message: 'No code splitting detected. Implement route-based splitting.',
                impact: 'low',
                solution: 'Use React.lazy() and dynamic imports'
            });
        }

        // Check vendor bundle
        const vendorFiles = analysis.files.javascript.filter(f => f.type === 'vendor');
        if (vendorFiles.length === 0) {
            recommendations.push({
                type: 'info',
                category: 'vendor-splitting',
                message: 'No vendor bundle detected. Consider splitting vendor code.',
                impact: 'low',
                solution: 'Configure webpack to create vendor chunks'
            });
        }

        return recommendations;
    }

    analyzePackageJson() {
        const packageJsonPath = path.join(process.cwd(), 'package.json');
        
        if (!fs.existsSync(packageJsonPath)) {
            return { error: 'package.json not found' };
        }

        const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        const dependencies = packageJson.dependencies || {};
        const devDependencies = packageJson.devDependencies || {};

        const heavyDependencies = [
            '@mui/material',
            '@mui/x-data-grid',
            '@mui/x-date-pickers',
            'recharts',
            'socket.io-client'
        ];

        const analysis = {
            totalDependencies: Object.keys(dependencies).length,
            totalDevDependencies: Object.keys(devDependencies).length,
            heavyDependenciesFound: [],
            optimizationOpportunities: []
        };

        // Check for heavy dependencies
        for (const dep of heavyDependencies) {
            if (dependencies[dep]) {
                analysis.heavyDependenciesFound.push({
                    name: dep,
                    version: dependencies[dep],
                    recommendation: this.getDependencyRecommendation(dep)
                });
            }
        }

        // General optimization opportunities
        if (dependencies['@mui/material']) {
            analysis.optimizationOpportunities.push({
                type: 'tree-shaking',
                message: 'Enable MUI tree shaking with babel plugin',
                solution: 'Install @babel/plugin-transform-imports'
            });
        }

        if (dependencies['lodash']) {
            analysis.optimizationOpportunities.push({
                type: 'import-optimization',
                message: 'Use specific lodash imports instead of full library',
                solution: 'Import specific functions: import debounce from "lodash/debounce"'
            });
        }

        return analysis;
    }

    getDependencyRecommendation(dep) {
        const recommendations = {
            '@mui/material': 'Large UI library. Use tree shaking and import only needed components.',
            '@mui/x-data-grid': 'Heavy grid component. Consider virtualization for large datasets.',
            '@mui/x-date-pickers': 'Date picker library. Import only specific pickers needed.',
            'recharts': 'Chart library. Consider lighter alternatives for simple charts.',
            'socket.io-client': 'WebSocket library. Ensure it\'s only loaded when needed.'
        };
        
        return recommendations[dep] || 'Check if this dependency is necessary.';
    }

    generateOptimizationScript() {
        return `
# Bundle Optimization Steps

## 1. Install Analysis Tools
npm install --save-dev webpack-bundle-analyzer
npm install --save-dev @babel/plugin-transform-imports

## 2. Add Bundle Analysis Script to package.json
{
  "scripts": {
    "analyze": "npm run build && npx webpack-bundle-analyzer build/static/js/*.js"
  }
}

## 3. Configure Babel for Tree Shaking (create .babelrc)
{
  "plugins": [
    ["@babel/plugin-transform-imports", {
      "@mui/material": {
        "transform": "@mui/material/{{member}}",
        "preventFullImport": true
      },
      "@mui/icons-material": {
        "transform": "@mui/icons-material/{{member}}",
        "preventFullImport": true
      }
    }]
  ]
}

## 4. Implement Code Splitting
// Replace direct imports with lazy loading
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const Projects = React.lazy(() => import('./pages/Projects'));

// Wrap routes with Suspense
<Suspense fallback={<div>Loading...</div>}>
  <Routes>
    <Route path="/dashboard" element={<Dashboard />} />
  </Routes>
</Suspense>

## 5. Optimize MUI Imports
// Instead of:
import { Button, TextField, Box } from '@mui/material';

// Use:
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';

## 6. Run Analysis
npm run analyze
        `.trim();
    }

    generateReport() {
        console.log('🔍 Analyzing Bundle Sizes...\n');
        
        const bundleAnalysis = this.analyzeBundleSizes();
        const packageAnalysis = this.analyzePackageJson();

        if (bundleAnalysis.error) {
            console.log('❌ Bundle analysis failed:', bundleAnalysis.error);
            console.log('💡 Run "npm run build" first to generate bundle files.\n');
        } else {
            console.log('📦 Bundle Analysis Results:');
            console.log(`Total Size: ${bundleAnalysis.totalSizeMB} MB (${bundleAnalysis.totalSizeKB} KB)`);
            console.log(`JavaScript Files: ${bundleAnalysis.files.javascript.length}`);
            console.log(`CSS Files: ${bundleAnalysis.files.css.length}\n`);

            if (bundleAnalysis.files.javascript.length > 0) {
                console.log('📄 Largest JavaScript Files:');
                bundleAnalysis.files.javascript.slice(0, 5).forEach(file => {
                    console.log(`  ${file.name}: ${file.sizeKB} KB (${file.type})`);
                });
                console.log('');
            }

            if (bundleAnalysis.recommendations.length > 0) {
                console.log('⚠️  Recommendations:');
                bundleAnalysis.recommendations.forEach(rec => {
                    const icon = rec.type === 'critical' ? '🚨' : 
                               rec.type === 'warning' ? '⚠️' : 'ℹ️';
                    console.log(`  ${icon} ${rec.message}`);
                    if (rec.solution) {
                        console.log(`     Solution: ${rec.solution}`);
                    }
                });
                console.log('');
            }
        }

        console.log('📋 Package Analysis:');
        console.log(`Dependencies: ${packageAnalysis.totalDependencies}`);
        console.log(`Dev Dependencies: ${packageAnalysis.totalDevDependencies}\n`);

        if (packageAnalysis.heavyDependenciesFound.length > 0) {
            console.log('⚖️  Heavy Dependencies:');
            packageAnalysis.heavyDependenciesFound.forEach(dep => {
                console.log(`  ${dep.name} ${dep.version}`);
                console.log(`    ${dep.recommendation}\n`);
            });
        }

        if (packageAnalysis.optimizationOpportunities.length > 0) {
            console.log('🚀 Optimization Opportunities:');
            packageAnalysis.optimizationOpportunities.forEach(opp => {
                console.log(`  • ${opp.message}`);
                console.log(`    ${opp.solution}\n`);
            });
        }

        console.log('🛠️  Optimization Script:');
        console.log(this.generateOptimizationScript());

        // Save detailed analysis to file
        const detailedReport = {
            timestamp: new Date().toISOString(),
            bundleAnalysis,
            packageAnalysis,
            optimizationScript: this.generateOptimizationScript()
        };

        fs.writeFileSync('bundle-analysis-report.json', JSON.stringify(detailedReport, null, 2));
        console.log('\n📊 Detailed report saved to: bundle-analysis-report.json');
    }
}

// Run the analyzer
if (require.main === module) {
    const analyzer = new BundleAnalyzer();
    analyzer.generateReport();
}

module.exports = BundleAnalyzer;