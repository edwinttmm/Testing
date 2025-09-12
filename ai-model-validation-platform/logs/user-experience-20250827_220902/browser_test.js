const puppeteer = require('puppeteer');

async function testPages() {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [];
    const warnings = [];
    
    // Listen for console messages
    page.on('console', msg => {
        const type = msg.type();
        const text = msg.text();
        const location = msg.location();
        
        if (type === 'error') {
            errors.push({
                type: 'error',
                text: text,
                url: page.url(),
                location: location
            });
            console.error(`ERROR on ${page.url()}: ${text}`);
        } else if (type === 'warning') {
            warnings.push({
                type: 'warning', 
                text: text,
                url: page.url(),
                location: location
            });
            console.warn(`WARNING on ${page.url()}: ${text}`);
        }
    });
    
    // Listen for page errors
    page.on('pageerror', error => {
        errors.push({
            type: 'pageerror',
            message: error.message,
            stack: error.stack,
            url: page.url()
        });
        console.error(`PAGE ERROR on ${page.url()}: ${error.message}`);
    });
    
    // Test pages
    const pages = [
        'http://localhost:3000/',
        'http://localhost:3000/projects',
        'http://localhost:3000/datasets',
        'http://localhost:3000/results',
        'http://localhost:3000/ground-truth'
    ];
    
    for (const url of pages) {
        console.log(`Testing ${url}...`);
        try {
            await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
            await page.waitForTimeout(3000); // Wait for any async operations
        } catch (err) {
            console.error(`Failed to load ${url}: ${err.message}`);
            errors.push({
                type: 'navigation',
                url: url,
                error: err.message
            });
        }
    }
    
    await browser.close();
    
    // Save results
    const fs = require('fs');
    fs.writeFileSync('browser_errors.json', JSON.stringify({ errors, warnings }, null, 2));
    
    console.log(`\n=== Browser Test Summary ===`);
    console.log(`Errors found: ${errors.length}`);
    console.log(`Warnings found: ${warnings.length}`);
    
    return { errors, warnings };
}

testPages().catch(console.error);
