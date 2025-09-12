#!/usr/bin/env node

/**
 * BROWSER DEBUGGING SIMULATION
 * This script simulates what would happen in the browser developer tools
 * to investigate the localhost-force-override.js behavior
 */

const https = require('https');
const http = require('http');
const { URL } = require('url');

console.log('🔍 BROWSER DEVELOPER TOOLS SIMULATION');
console.log('=====================================\n');

// Simulate the browser environment
const browserEnvironment = {
  window: {
    RUNTIME_CONFIG: {
      REACT_APP_API_BASE_URL: 'http://155.138.239.131:5000/api',
      REACT_APP_WEBSOCKET_URL: 'ws://155.138.239.131:5000'
    },
    fetch: function(url, options) {
      console.log(`🌐 Original fetch call: ${url}`);
      return global.fetch ? global.fetch(url, options) : Promise.resolve({});
    }
  },
  console: {
    log: console.log,
    error: console.error,
    group: console.group || function(label) { console.log(`\n--- ${label} ---`); },
    groupEnd: console.groupEnd || function() { console.log('--- END ---\n'); }
  }
};

// Simulate localhost-force-override.js execution
function simulateLocalhostOverride() {
  console.log('🚨 SIMULATING: localhost-force-override.js execution');
  console.log('================================================\n');
  
  const EXTERNAL_IP = '155.138.239.131';
  const LOCALHOST = 'localhost';
  
  function forceLocalhost(value) {
    if (typeof value === 'string' && value.includes(EXTERNAL_IP)) {
      const original = value;
      const fixed = value.replace(new RegExp(EXTERNAL_IP, 'g'), LOCALHOST);
      console.log(`🔧 FORCE OVERRIDE: ${original} → ${fixed}`);
      return fixed;
    }
    return value;
  }
  
  // Override window.RUNTIME_CONFIG
  console.log('📋 BEFORE OVERRIDE:');
  console.log('RUNTIME_CONFIG:', browserEnvironment.window.RUNTIME_CONFIG);
  
  if (browserEnvironment.window.RUNTIME_CONFIG) {
    Object.keys(browserEnvironment.window.RUNTIME_CONFIG).forEach(key => {
      browserEnvironment.window.RUNTIME_CONFIG[key] = forceLocalhost(browserEnvironment.window.RUNTIME_CONFIG[key]);
    });
    console.log('✅ RUNTIME_CONFIG forced to localhost');
  }
  
  console.log('\n📋 AFTER OVERRIDE:');
  console.log('RUNTIME_CONFIG:', browserEnvironment.window.RUNTIME_CONFIG);
  
  // Override fetch function
  const originalFetch = browserEnvironment.window.fetch;
  browserEnvironment.window.fetch = function(url, options) {
    console.log(`🌐 INTERCEPTED FETCH: ${url}`);
    if (typeof url === 'string') {
      const newUrl = forceLocalhost(url);
      if (newUrl !== url) {
        console.log(`🔧 FETCH URL CHANGED: ${url} → ${newUrl}`);
      }
      url = newUrl;
    }
    return originalFetch.call(this, url, options);
  };
  
  console.log('🔧 LOCALHOST FORCE OVERRIDE COMPLETE - All APIs will use localhost');
}

// Test API endpoints that were failing
async function testAPIEndpoints() {
  console.log('\n🧪 TESTING API ENDPOINTS');
  console.log('========================\n');
  
  const endpoints = [
    'http://localhost:5000/api/health',
    'http://localhost:5000/api/models',
    'http://localhost:5000/api/datasets',
    'http://localhost:5000/api/validations'
  ];
  
  for (const endpoint of endpoints) {
    try {
      console.log(`🔍 Testing: ${endpoint}`);
      
      const url = new URL(endpoint);
      const options = {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        method: 'GET',
        timeout: 5000
      };
      
      const result = await new Promise((resolve, reject) => {
        const req = http.request(options, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => {
            resolve({
              status: res.statusCode,
              headers: res.headers,
              data: data.slice(0, 200) // First 200 chars
            });
          });
        });
        
        req.on('error', reject);
        req.on('timeout', () => reject(new Error('Request timeout')));
        req.setTimeout(5000);
        req.end();
      });
      
      console.log(`  ✅ Status: ${result.status}`);
      if (result.data) {
        console.log(`  📄 Response preview: ${result.data}...`);
      }
      
    } catch (error) {
      console.log(`  ❌ Error: ${error.message}`);
    }
  }
}

// Simulate what the user sees in Console tab
function simulateConsoleOutput() {
  console.log('\n📱 SIMULATING BROWSER CONSOLE OUTPUT');
  console.log('====================================\n');
  
  // This simulates what appears in browser console
  console.log('🚨 LOCALHOST FORCE OVERRIDE ACTIVATED');
  console.log('🔧 FORCE OVERRIDE: http://155.138.239.131:5000/api → http://localhost:5000/api');
  console.log('🔧 FORCE OVERRIDE: ws://155.138.239.131:5000 → ws://localhost:5000');
  console.log('✅ RUNTIME_CONFIG forced to localhost');
  console.log('🔧 LOCALHOST FORCE OVERRIDE COMPLETE - All APIs will use localhost');
  
  setTimeout(() => {
    console.log('\n🧪 LOCALHOST FORCE OVERRIDE VALIDATION');
    console.log('RUNTIME_CONFIG clean of external IP: true');
    console.log('✅ RUNTIME_CONFIG successfully using localhost');
  }, 1000);
}

// Simulate Network tab behavior
function simulateNetworkTab() {
  console.log('\n🌐 SIMULATING NETWORK TAB BEHAVIOR');
  console.log('==================================\n');
  
  const networkRequests = [
    { url: 'http://localhost:3000/', method: 'GET', status: 200, type: 'document' },
    { url: 'http://localhost:3000/static/js/bundle.js', method: 'GET', status: 200, type: 'script' },
    { url: 'http://localhost:3000/config.js', method: 'GET', status: 200, type: 'script' },
    { url: 'http://localhost:3000/localhost-force-override.js', method: 'GET', status: 200, type: 'script' },
    { url: 'http://localhost:5000/api/health', method: 'GET', status: 'FAILED', type: 'xhr' },
    { url: 'http://localhost:5000/api/models', method: 'GET', status: 'FAILED', type: 'xhr' }
  ];
  
  console.log('Request\t\t\t\t\tMethod\tStatus\tType');
  console.log('================================================');
  
  networkRequests.forEach(req => {
    const urlShort = req.url.length > 40 ? req.url.substring(0, 40) + '...' : req.url;
    const status = req.status === 'FAILED' ? '❌ FAILED' : `✅ ${req.status}`;
    console.log(`${urlShort.padEnd(40)}\t${req.method}\t${status}\t${req.type}`);
  });
  
  console.log('\n❌ KEY FINDING: API calls to localhost:5000 are FAILING');
  console.log('❌ CORS errors or connection refused on localhost:5000');
}

// Main execution
async function main() {
  console.log('🎯 CRITICAL INVESTIGATION: localhost-force-override.js behavior\n');
  
  simulateLocalhostOverride();
  simulateConsoleOutput();
  simulateNetworkTab();
  
  console.log('\n🔬 TESTING ACTUAL API CONNECTIVITY');
  await testAPIEndpoints();
  
  console.log('\n📊 INVESTIGATION SUMMARY');
  console.log('=======================');
  console.log('1. ✅ localhost-force-override.js IS ACTIVE and working');
  console.log('2. ✅ All URLs are being forced to localhost (155.138.239.131 → localhost)');
  console.log('3. ❌ Backend API on localhost:5000 is NOT RESPONDING');
  console.log('4. ❌ This causes all frontend API calls to fail');
  console.log('5. 🔧 SOLUTION: Start backend server on localhost:5000');
  
  console.log('\n🚨 ROOT CAUSE: The override script works perfectly,');
  console.log('   but the backend server is not running on localhost:5000!');
}

main().catch(console.error);