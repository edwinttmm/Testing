const puppeteer = require('puppeteer');
const fs = require('fs');

async function testAllPages() {
    let browser;
    const errors = [];
    const screenshots = [];
    const consoleMessages = [];
    
    try {
        browser = await puppeteer.launch({ 
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        
        const page = await browser.newPage();
        
        // Monitor console messages
        page.on('console', msg => {
            const entry = {
                type: msg.type(),
                text: msg.text(),
                timestamp: new Date().toISOString(),
                url: page.url()
            };
            consoleMessages.push(entry);
            
            if (msg.type() === 'error') {
                console.error(`Console Error: ${msg.text()}`);
            }
        });
        
        // Monitor page errors
        page.on('pageerror', error => {
            errors.push({
                message: error.message,
                stack: error.stack,
                timestamp: new Date().toISOString(),
                url: page.url()
            });
            console.error(`Page Error: ${error.message}`);
        });
        
        const pages = [
            { path: '/', name: 'home' },
            { path: '/projects', name: 'projects' },
            { path: '/datasets', name: 'datasets' },
            { path: '/results', name: 'results' },
            { path: '/ground-truth', name: 'ground-truth' }
        ];
        
        for (const pageInfo of pages) {
            console.log(`Testing page: ${pageInfo.name}`);
            
            try {
                await page.goto(`http://localhost:3000${pageInfo.path}`, { 
                    waitUntil: 'networkidle2',
                    timeout: 30000 
                });
                
                // Wait a bit for any async operations
                await page.waitForTimeout(3000);
                
                // Take screenshot
                const screenshotPath = `${pageInfo.name}_page.png`;
                await page.screenshot({ 
                    path: screenshotPath, 
                    fullPage: true 
                });
                screenshots.push(screenshotPath);
                
                console.log(`✅ ${pageInfo.name} page loaded successfully`);
                
                // Try to interact with common elements
                if (pageInfo.name === 'projects') {
                    // Try to find and click create project button
                    try {
                        await page.click('button:has-text("Create"), button:has-text("New"), [class*="create"]');
                        await page.waitForTimeout(2000);
                        console.log('✅ Project creation interaction successful');
                    } catch (e) {
                        console.log('⚠️ Could not interact with create project button');
                    }
                }
                
            } catch (error) {
                console.error(`❌ Failed to load ${pageInfo.name}: ${error.message}`);
                errors.push({
                    page: pageInfo.name,
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
            }
        }
        
    } catch (error) {
        console.error('Browser test failed:', error);
        errors.push({
            general: error.message,
            timestamp: new Date().toISOString()
        });
    } finally {
        if (browser) {
            await browser.close();
        }
    }
    
    // Save results
    const results = {
        timestamp: new Date().toISOString(),
        errors: errors,
        screenshots: screenshots,
        consoleMessages: consoleMessages,
        summary: {
            totalErrors: errors.length,
            totalConsoleMessages: consoleMessages.length,
            consoleErrors: consoleMessages.filter(m => m.type === 'error').length,
            screenshotsTaken: screenshots.length
        }
    };
    
    fs.writeFileSync('browser-test-results.json', JSON.stringify(results, null, 2));
    
    console.log('\n=== BROWSER TEST SUMMARY ===');
    console.log(`Total Errors: ${results.summary.totalErrors}`);
    console.log(`Console Messages: ${results.summary.totalConsoleMessages}`);
    console.log(`Console Errors: ${results.summary.consoleErrors}`);
    console.log(`Screenshots: ${results.summary.screenshotsTaken}`);
    
    return results;
}

testAllPages().catch(console.error);
