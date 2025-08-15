#!/usr/bin/env node

/**
 * Browser Error Monitoring Script
 * Simulates browser interactions and monitors for [object Object] errors
 */

const axios = require('axios');

const FRONTEND_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';

// Simulate browser console error checking
async function checkBrowserConsoleErrors() {
  console.log('🔍 Checking for Browser Console Errors...\n');
  
  // Test frontend static assets
  try {
    const response = await axios.get(FRONTEND_URL);
    console.log('✅ Frontend accessible');
    
    // Extract script tags and check for bundle.js
    const scriptMatches = response.data.match(/<script[^>]*src="([^"]*)"[^>]*>/g);
    if (scriptMatches) {
      console.log('📦 Found script tags:');
      for (const script of scriptMatches) {
        const srcMatch = script.match(/src="([^"]*)"/);
        if (srcMatch) {
          const src = srcMatch[1];
          console.log(`  - ${src}`);
          
          // Check if bundle.js is accessible
          if (src.includes('bundle.js') || src.includes('.js')) {
            try {
              const fullUrl = src.startsWith('http') ? src : `${FRONTEND_URL}${src}`;
              const jsResponse = await axios.get(fullUrl, {
                headers: { 'Accept': 'application/javascript' }
              });
              console.log(`    ✅ Accessible (${jsResponse.data.length} bytes)`);
            } catch (jsError) {
              console.log(`    ❌ Error loading: ${jsError.message}`);
            }
          }
        }
      }
    }
    
  } catch (error) {
    console.log('❌ Frontend not accessible:', error.message);
  }
  
  console.log('');
}

// Simulate frontend API calls that might trigger errors
async function simulateFrontendApiCalls() {
  console.log('🌐 Simulating Frontend API Calls...\n');
  
  const apiCalls = [
    {
      name: 'Load Projects Dashboard',
      call: () => axios.get(`${BACKEND_URL}/api/projects`),
      expectedError: false
    },
    {
      name: 'Get Non-existent Project',
      call: () => axios.get(`${BACKEND_URL}/api/projects/invalid-uuid-format`),
      expectedError: true
    },
    {
      name: 'Create Project with Missing Fields',
      call: () => axios.post(`${BACKEND_URL}/api/projects`, {
        // Missing required fields to trigger validation error
        description: 'Test'
      }),
      expectedError: true
    },
    {
      name: 'Create Project with Invalid Data Types',
      call: () => axios.post(`${BACKEND_URL}/api/projects`, {
        name: 123, // Should be string
        description: null,
        cameraModel: [],
        cameraView: {},
        signalType: 'invalid'
      }),
      expectedError: true
    },
    {
      name: 'Update Non-existent Project',
      call: () => axios.put(`${BACKEND_URL}/api/projects/00000000-0000-0000-0000-000000000000`, {
        name: 'Updated'
      }),
      expectedError: true
    },
    {
      name: 'Delete Non-existent Project',
      call: () => axios.delete(`${BACKEND_URL}/api/projects/fake-id`),
      expectedError: true
    }
  ];
  
  for (const apiCall of apiCalls) {
    console.log(`📞 ${apiCall.name}`);
    
    try {
      const response = await apiCall.call();
      console.log(`  ✅ Success: ${response.status}`);
      
      if (apiCall.expectedError) {
        console.log('  ⚠️  Expected error but got success');
      }
      
    } catch (error) {
      console.log(`  📊 Error Response:`);
      console.log(`    Status: ${error.response?.status || 'Network Error'}`);
      console.log(`    Data:`, JSON.stringify(error.response?.data || error.message, null, 2));
      
      // Check for [object Object] patterns
      const errorStr = JSON.stringify(error.response?.data || error.message);
      if (errorStr.includes('[object Object]')) {
        console.log('  🚨 FOUND [object Object] ERROR!');
      }
      
      // Check for malformed error responses that could cause frontend issues
      if (error.response?.data && typeof error.response.data === 'object') {
        const data = error.response.data;
        if (data.toString() === '[object Object]') {
          console.log('  🚨 Response data toString() returns [object Object]!');
        }
      }
    }
    
    console.log('');
  }
}

// Test error handling edge cases
async function testErrorHandlingEdgeCases() {
  console.log('🧪 Testing Error Handling Edge Cases...\n');
  
  const edgeCases = [
    {
      name: 'Circular Reference in Response',
      test: async () => {
        // This would be handled on the backend, but let's test frontend parsing
        try {
          const response = await axios.get(`${BACKEND_URL}/api/projects`);
          // Simulate circular reference issue
          const data = response.data;
          if (Array.isArray(data) && data.length > 0) {
            // Test if frontend can handle data properly
            console.log(`  📋 Projects loaded: ${data.length} items`);
            console.log(`  🔍 First project:`, JSON.stringify(data[0], null, 2));
          }
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      }
    },
    
    {
      name: 'Undefined/Null Response Handling',
      test: async () => {
        try {
          // Test how frontend handles empty responses
          const response = await axios.get(`${BACKEND_URL}/api/projects/nonexistent`, {
            validateStatus: () => true // Accept all status codes
          });
          
          console.log(`  📊 Response status: ${response.status}`);
          console.log(`  📊 Response data:`, response.data);
          
          // Check if this could cause [object Object] when stringified
          const stringified = String(response.data);
          if (stringified === '[object Object]') {
            console.log('  🚨 Response stringifies to [object Object]!');
            return { success: false, error: 'Object stringification issue' };
          }
          
          return { success: true };
        } catch (error) {
          return { success: false, error: error.message };
        }
      }
    },
    
    {
      name: 'Large Error Response',
      test: async () => {
        try {
          // Create a large invalid payload to trigger detailed error
          const largeInvalidData = {};
          for (let i = 0; i < 100; i++) {
            largeInvalidData[`field${i}`] = `invalid_value_${i}`;
          }
          
          const response = await axios.post(`${BACKEND_URL}/api/projects`, largeInvalidData);
          return { success: false, error: 'Should have failed' };
        } catch (error) {
          const errorData = error.response?.data;
          console.log(`  📊 Error response size:`, JSON.stringify(errorData).length);
          
          // Check if large error responses are handled properly
          if (errorData && typeof errorData === 'object') {
            const stringified = String(errorData);
            if (stringified === '[object Object]') {
              console.log('  🚨 Large error response becomes [object Object]!');
              return { success: false, error: 'Large object stringification issue' };
            }
          }
          
          return { success: true };
        }
      }
    }
  ];
  
  for (const edgeCase of edgeCases) {
    console.log(`🔬 Testing: ${edgeCase.name}`);
    
    try {
      const result = await edgeCase.test();
      console.log(`  📊 Result:`, result.success ? '✅ Passed' : `❌ ${result.error}`);
    } catch (error) {
      console.log(`  💥 Test failed:`, error.message);
    }
    
    console.log('');
  }
}

// Monitor timing-based errors
async function monitorTimingErrors() {
  console.log('⏱️  Monitoring Timing-Based Errors...\n');
  
  // Test rapid-fire requests that might cause race conditions
  console.log('🏃 Testing rapid API calls...');
  
  const rapidCalls = [];
  for (let i = 0; i < 5; i++) {
    rapidCalls.push(
      axios.get(`${BACKEND_URL}/api/projects`).catch(error => ({
        error: error.response?.data || error.message,
        timing: Date.now()
      }))
    );
  }
  
  const results = await Promise.all(rapidCalls);
  console.log(`  📊 Completed ${results.length} rapid calls`);
  
  const errors = results.filter(r => r.error);
  if (errors.length > 0) {
    console.log(`  ⚠️  ${errors.length} calls had errors:`);
    errors.forEach((error, idx) => {
      console.log(`    ${idx + 1}:`, error.error);
      if (JSON.stringify(error.error).includes('[object Object]')) {
        console.log('    🚨 FOUND [object Object] in rapid call error!');
      }
    });
  } else {
    console.log('  ✅ All rapid calls succeeded');
  }
  
  console.log('');
}

async function main() {
  console.log('🕵️  Browser Error Monitoring Started\n');
  console.log('=' .repeat(50));
  
  try {
    await checkBrowserConsoleErrors();
    await simulateFrontendApiCalls();
    await testErrorHandlingEdgeCases();
    await monitorTimingErrors();
    
    console.log('📋 Monitoring Summary:');
    console.log('- Checked frontend accessibility and script loading');
    console.log('- Tested various API error scenarios');
    console.log('- Verified error response handling');
    console.log('- Monitored timing-based error conditions');
    console.log('\n🎯 To find actual [object Object] errors, check:');
    console.log('  1. Browser console at http://localhost:3000');
    console.log('  2. React DevTools error boundaries');
    console.log('  3. Network tab for failed requests');
    console.log('  4. Application error logs');
    
  } catch (error) {
    console.error('💥 Monitoring failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { 
  checkBrowserConsoleErrors, 
  simulateFrontendApiCalls, 
  testErrorHandlingEdgeCases,
  monitorTimingErrors 
};