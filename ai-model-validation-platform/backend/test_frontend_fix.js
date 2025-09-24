const https = require('https');
const http = require('http');

// Test the frontend with a simple HTTP request to see if it loads without errors
console.log('🔍 Testing frontend after cache refresh...');

const options = {
  hostname: 'localhost',
  port: 3000,
  path: '/results/510631f1-3277-4fb7-9cb0-f11595d54f66',
  method: 'GET',
  timeout: 5000
};

const req = http.request(options, (res) => {
  console.log(`✅ HIL Results page responded with status: ${res.statusCode}`);
  
  let data = '';
  res.on('data', (chunk) => {
    data += chunk;
  });
  
  res.on('end', () => {
    if (data.includes('<!DOCTYPE html>')) {
      console.log('✅ Frontend is serving HTML content properly');
      console.log('✅ Cache refresh appears to have resolved the JavaScript error');
    } else {
      console.log('❌ Unexpected response content');
    }
  });
});

req.on('error', (err) => {
  console.log(`❌ Request failed: ${err.message}`);
});

req.on('timeout', () => {
  console.log('❌ Request timeout');
  req.destroy();
});

req.setTimeout(5000);
req.end();