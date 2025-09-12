// Simple Frontend Test without puppeteer
// Tests basic frontend functionality

const http = require('http');
const https = require('https');
const fs = require('fs');

function makeRequest(url) {
    return new Promise((resolve, reject) => {
        const client = url.startsWith('https:') ? https : http;
        const req = client.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve({
                status: res.statusCode,
                headers: res.headers,
                body: data
            }));
        });
        req.on('error', reject);
        req.setTimeout(5000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
    });
}

async function testFrontendBasics() {
    console.log('🚀 Starting Basic Frontend Test...');
    const results = {
        timestamp: new Date().toISOString(),
        tests: {},
        success: true,
        errors: []
    };
    
    try {
        // Test frontend homepage
        console.log('🌐 Testing frontend homepage...');
        const homepage = await makeRequest('http://localhost:3000/');
        results.tests.homepage = {
            status: homepage.status,
            success: homepage.status === 200,
            hasHtml: homepage.body.includes('<html'),
            hasReact: homepage.body.includes('react'),
            hasConfig: homepage.body.includes('config.js')
        };
        console.log(`${homepage.status === 200 ? '✅' : '❌'} Homepage: ${homepage.status}`);
        
        // Test config.js
        console.log('⚙️ Testing config.js...');
        const config = await makeRequest('http://localhost:3000/config.js');
        results.tests.config = {
            status: config.status,
            success: config.status === 200,
            hasBackendUrl: config.body.includes('BACKEND_URL') || config.body.includes('localhost:8000')
        };
        console.log(`${config.status === 200 ? '✅' : '❌'} Config: ${config.status}`);
        
        // Test backend connectivity from frontend perspective
        console.log('🔌 Testing backend API from frontend...');
        const api = await makeRequest('http://localhost:8000/api/projects');
        results.tests.api = {
            status: api.status,
            success: api.status === 200,
            hasData: api.body.length > 0,
            isJson: api.body.startsWith('[') || api.body.startsWith('{')
        };
        console.log(`${api.status === 200 ? '✅' : '❌'} API: ${api.status}`);
        
        // Test health endpoint
        console.log('🏥 Testing health endpoint...');
        const health = await makeRequest('http://localhost:8000/health');
        results.tests.health = {
            status: health.status,
            success: health.status === 200,
            isJson: health.body.startsWith('{'),
            hasStatus: health.body.includes('status')
        };
        console.log(`${health.status === 200 ? '✅' : '❌'} Health: ${health.status}`);
        
    } catch (error) {
        console.log('❌ Test error:', error.message);
        results.errors.push(error.message);
        results.success = false;
    }
    
    // Calculate overall success
    const testResults = Object.values(results.tests);
    const successfulTests = testResults.filter(t => t.success).length;
    const totalTests = testResults.length;
    
    results.summary = {
        total: totalTests,
        passed: successfulTests,
        failed: totalTests - successfulTests,
        successRate: totalTests > 0 ? (successfulTests / totalTests * 100).toFixed(1) : 0
    };
    
    results.success = successfulTests === totalTests && results.errors.length === 0;
    
    console.log('\n📋 Test Summary:');
    console.log(`📊 Tests: ${successfulTests}/${totalTests} passed (${results.summary.successRate}%)`);
    console.log(`${results.success ? '✅ PASS' : '❌ FAIL'} Overall: ${results.success ? 'All tests passed' : 'Some tests failed'}`);
    
    return results;
}

// Run test
testFrontendBasics()
    .then(results => {
        console.log('\n💾 Saving results...');
        fs.writeFileSync('simple_frontend_test_results.json', JSON.stringify(results, null, 2));
        console.log('✅ Results saved to simple_frontend_test_results.json');
        process.exit(results.success ? 0 : 1);
    })
    .catch(error => {
        console.error('❌ Test execution failed:', error);
        process.exit(1);
    });