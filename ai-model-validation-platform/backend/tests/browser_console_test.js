/**
 * CRITICAL ERROR ANALYSIS - Browser Console Testing
 * Systematic page-by-page error documentation
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

class ConsoleErrorAnalyzer {
    constructor() {
        this.browser = null;
        this.page = null;
        this.errors = [];
        this.networkFailures = [];
        this.testResults = {
            pages: {},
            totalErrors: 0,
            totalNetworkFailures: 0,
            timestamp: new Date().toISOString()
        };
    }

    async initialize() {
        console.log('🚀 Initializing Browser Console Error Analysis...');
        this.browser = await puppeteer.launch({
            headless: false, // Keep visible to see what's happening
            defaultViewport: { width: 1200, height: 800 },
            devtools: true,
            args: ['--disable-web-security', '--disable-features=VizDisplayCompositor']
        });
        
        this.page = await this.browser.newPage();
        
        // Listen for console errors
        this.page.on('console', (msg) => {
            if (msg.type() === 'error') {
                const error = {
                    type: 'console_error',
                    message: msg.text(),
                    location: msg.location(),
                    timestamp: new Date().toISOString()
                };
                this.errors.push(error);
                console.log('❌ CONSOLE ERROR:', error.message);
            }
        });

        // Listen for network failures
        this.page.on('response', (response) => {
            if (!response.ok()) {
                const failure = {
                    type: 'network_failure',
                    url: response.url(),
                    status: response.status(),
                    statusText: response.statusText(),
                    timestamp: new Date().toISOString()
                };
                this.networkFailures.push(failure);
                console.log('🚫 NETWORK FAILURE:', failure.status, failure.url);
            }
        });

        // Listen for unhandled page errors
        this.page.on('pageerror', (error) => {
            const pageError = {
                type: 'page_error',
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString()
            };
            this.errors.push(pageError);
            console.log('💥 PAGE ERROR:', error.message);
        });

        console.log('✅ Browser initialized, starting systematic page testing...');
    }

    async testPage(url, pageName) {
        console.log(`\n🔍 Testing ${pageName} at ${url}...`);
        
        const pageErrors = [];
        const pageNetworkFailures = [];
        const startTime = Date.now();

        try {
            // Clear previous errors for this page
            const errorCountBefore = this.errors.length;
            const networkCountBefore = this.networkFailures.length;

            // Navigate to page
            await this.page.goto(url, { 
                waitUntil: 'networkidle2', 
                timeout: 30000 
            });

            // Wait for React to load
            await this.page.waitForTimeout(3000);

            // Try to interact with page elements
            try {
                await this.page.evaluate(() => {
                    // Trigger any lazy-loaded components
                    window.scrollTo(0, document.body.scrollHeight);
                });
                await this.page.waitForTimeout(2000);
            } catch (interactionError) {
                console.log('⚠️  Page interaction failed:', interactionError.message);
            }

            // Capture screenshot
            const screenshotPath = path.join(__dirname, `../screenshots/${pageName.replace(/[^a-zA-Z0-9]/g, '_')}.png`);
            await this.page.screenshot({ 
                path: screenshotPath,
                fullPage: true 
            });

            // Calculate page-specific errors
            const pageErrorsCount = this.errors.length - errorCountBefore;
            const pageNetworkCount = this.networkFailures.length - networkCountBefore;

            // Get page-specific errors
            const pageSpecificErrors = this.errors.slice(errorCountBefore);
            const pageSpecificNetwork = this.networkFailures.slice(networkCountBefore);

            const loadTime = Date.now() - startTime;

            this.testResults.pages[pageName] = {
                url,
                status: 'tested',
                loadTimeMs: loadTime,
                consoleErrors: pageSpecificErrors,
                networkFailures: pageSpecificNetwork,
                errorCount: pageSpecificErrors.length,
                networkFailureCount: pageSpecificNetwork.length,
                screenshot: screenshotPath,
                timestamp: new Date().toISOString()
            };

            console.log(`✅ ${pageName} tested - ${pageSpecificErrors.length} console errors, ${pageSpecificNetwork.length} network failures`);

        } catch (error) {
            console.log(`❌ Failed to test ${pageName}:`, error.message);
            
            this.testResults.pages[pageName] = {
                url,
                status: 'failed',
                error: error.message,
                timestamp: new Date().toISOString()
            };
        }
    }

    async runComprehensiveAnalysis() {
        await this.initialize();

        // Test all pages systematically
        const pagesToTest = [
            { url: 'http://localhost:3000', name: 'Homepage_Port_3000' },
            { url: 'http://localhost:3001', name: 'Homepage_Port_3001' },  
            { url: 'http://localhost:3002', name: 'Homepage_Port_3002' },
            { url: 'http://localhost:3000/projects', name: 'Projects_Page' },
            { url: 'http://localhost:3000/ground-truth', name: 'Ground_Truth_Page' },
            { url: 'http://localhost:3000/test-execution', name: 'Test_Execution_Page' },
            { url: 'http://localhost:3000/upload', name: 'Video_Upload_Page' },
            { url: 'http://localhost:3000/annotations', name: 'Annotations_Page' },
            { url: 'http://localhost:3000/settings', name: 'Settings_Page' },
        ];

        for (const pageConfig of pagesToTest) {
            await this.testPage(pageConfig.url, pageConfig.name);
            await this.page.waitForTimeout(1000); // Brief pause between tests
        }

        // Generate comprehensive report
        await this.generateReport();
        await this.browser.close();
    }

    async generateReport() {
        this.testResults.totalErrors = this.errors.length;
        this.testResults.totalNetworkFailures = this.networkFailures.length;
        
        const reportPath = path.join(__dirname, '../critical_error_inventory.json');
        fs.writeFileSync(reportPath, JSON.stringify(this.testResults, null, 2));

        console.log('\n📊 COMPREHENSIVE ERROR ANALYSIS COMPLETE');
        console.log(`📄 Full report saved to: ${reportPath}`);
        console.log(`🔥 Total Console Errors: ${this.testResults.totalErrors}`);
        console.log(`🚫 Total Network Failures: ${this.testResults.totalNetworkFailures}`);
        
        // Print summary by page
        console.log('\n📋 ERROR SUMMARY BY PAGE:');
        Object.entries(this.testResults.pages).forEach(([pageName, data]) => {
            if (data.status === 'tested') {
                console.log(`  ${pageName}: ${data.errorCount} errors, ${data.networkFailureCount} network failures`);
            } else {
                console.log(`  ${pageName}: FAILED TO TEST - ${data.error}`);
            }
        });
    }
}

// Run the analysis
(async () => {
    try {
        const analyzer = new ConsoleErrorAnalyzer();
        await analyzer.runComprehensiveAnalysis();
        console.log('✅ Analysis completed successfully');
        process.exit(0);
    } catch (error) {
        console.error('💥 Analysis failed:', error);
        process.exit(1);
    }
})();

module.exports = ConsoleErrorAnalyzer;