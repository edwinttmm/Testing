// Frontend Integration Test
// Tests that the frontend loads without promise rejection errors

const puppeteer = require('puppeteer');

async function testFrontendIntegration() {
    console.log('🚀 Starting Frontend Integration Test...');
    
    let browser;
    try {
        browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        
        const page = await browser.newPage();
        
        // Capture console errors
        const consoleErrors = [];
        const promiseRejections = [];
        
        page.on('console', msg => {
            if (msg.type() === 'error') {
                consoleErrors.push(msg.text());
                console.log('❌ Console Error:', msg.text());
            }
        });
        
        page.on('pageerror', error => {
            consoleErrors.push(error.message);
            console.log('❌ Page Error:', error.message);
        });
        
        // Listen for unhandled promise rejections
        page.evaluateOnNewDocument(() => {
            window.addEventListener('unhandledrejection', event => {
                window.promiseRejections = window.promiseRejections || [];
                window.promiseRejections.push(event.reason);
                console.error('Unhandled Promise Rejection:', event.reason);
            });
        });
        
        console.log('🌐 Loading frontend at http://localhost:3000...');
        await page.goto('http://localhost:3000', {
            waitUntil: 'networkidle2',
            timeout: 30000
        });
        
        // Wait for React to load
        await page.waitForTimeout(3000);
        
        // Check for unhandled promise rejections
        const rejections = await page.evaluate(() => {
            return window.promiseRejections || [];
        });
        
        promiseRejections.push(...rejections);
        
        // Test navigation links
        console.log('🔍 Testing navigation links...');
        const navLinks = await page.$$('nav a, .nav-link, [role="navigation"] a');
        console.log(`Found ${navLinks.length} navigation links`);
        
        // Test API integration
        console.log('🔌 Testing API integration...');
        const apiResponse = await page.evaluate(async () => {
            try {
                const response = await fetch('http://localhost:8000/api/projects');
                return {
                    status: response.status,
                    ok: response.ok,
                    data: await response.json()
                };
            } catch (error) {
                return { error: error.message };
            }
        });
        
        console.log('📊 API Response:', apiResponse);
        
        // Generate test results
        const results = {
            timestamp: new Date().toISOString(),
            frontend: {
                loaded: true,
                url: 'http://localhost:3000'
            },
            errors: {
                console: consoleErrors,
                promiseRejections: promiseRejections,
                total: consoleErrors.length + promiseRejections.length
            },
            navigation: {
                linksFound: navLinks.length,
                working: navLinks.length > 0
            },
            api: {
                backend: apiResponse
            },
            success: consoleErrors.length === 0 && promiseRejections.length === 0
        };
        
        console.log('\n📋 Test Results:');
        console.log(`✅ Frontend Loaded: ${results.frontend.loaded}`);
        console.log(`${results.errors.total === 0 ? '✅' : '❌'} Errors: ${results.errors.total}`);
        console.log(`${results.navigation.working ? '✅' : '❌'} Navigation: ${results.navigation.linksFound} links`);
        console.log(`${apiResponse.ok ? '✅' : '❌'} API Integration: ${apiResponse.status || 'Failed'}`);
        console.log(`${results.success ? '✅ PASS' : '❌ FAIL'} Overall: ${results.success ? 'No errors found' : 'Errors detected'}`);
        
        return results;
        
    } catch (error) {
        console.log('❌ Test failed:', error.message);
        return {
            success: false,
            error: error.message,
            timestamp: new Date().toISOString()
        };
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

// Run the test if this file is executed directly
if (require.main === module) {
    testFrontendIntegration()
        .then(results => {
            console.log('\n📄 Saving results to frontend_test_results.json...');
            require('fs').writeFileSync('frontend_test_results.json', JSON.stringify(results, null, 2));
            process.exit(results.success ? 0 : 1);
        })
        .catch(error => {
            console.error('Test execution failed:', error);
            process.exit(1);
        });
}

module.exports = testFrontendIntegration;