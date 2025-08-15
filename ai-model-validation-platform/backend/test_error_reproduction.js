#!/usr/bin/env node

/**
 * Error Reproduction Testing Script
 * Tests various scenarios to trigger [object Object] errors
 */

const axios = require('axios');
const WebSocket = require('ws');

const FRONTEND_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';

// Test scenarios that might trigger [object Object] errors
const testScenarios = [
  {
    name: 'Invalid Project Creation',
    test: async () => {
      try {
        const response = await axios.post(`${BACKEND_URL}/api/projects`, {
          invalidField: 'test',
          // Missing required fields
        });
        return { success: false, error: 'Should have failed' };
      } catch (error) {
        return { 
          success: true, 
          error: error.response?.data || error.message,
          status: error.response?.status 
        };
      }
    }
  },
  
  {
    name: 'Invalid JSON Payload',
    test: async () => {
      try {
        const response = await axios.post(`${BACKEND_URL}/api/projects`, 
          'invalid json string', 
          { headers: { 'Content-Type': 'application/json' } }
        );
        return { success: false, error: 'Should have failed' };
      } catch (error) {
        return { 
          success: true, 
          error: error.response?.data || error.message,
          status: error.response?.status 
        };
      }
    }
  },

  {
    name: 'Missing Content-Type Header',
    test: async () => {
      try {
        const response = await axios.post(`${BACKEND_URL}/api/projects`, {
          name: 'Test'
        }, { headers: {} });
        return { success: true, data: response.data };
      } catch (error) {
        return { 
          success: false, 
          error: error.response?.data || error.message,
          status: error.response?.status 
        };
      }
    }
  },

  {
    name: 'Network Timeout Simulation',
    test: async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/projects`, {
          timeout: 1 // 1ms timeout to force timeout error
        });
        return { success: true, data: response.data };
      } catch (error) {
        return { 
          success: true, 
          error: error.code || error.message,
          isTimeout: error.code === 'ECONNABORTED'
        };
      }
    }
  },

  {
    name: 'Large Payload Test',
    test: async () => {
      try {
        const largeData = 'x'.repeat(10000000); // 10MB string
        const response = await axios.post(`${BACKEND_URL}/api/projects`, {
          name: 'Large Test',
          description: largeData
        });
        return { success: true, data: response.data };
      } catch (error) {
        return { 
          success: true, 
          error: error.response?.data || error.message,
          status: error.response?.status 
        };
      }
    }
  },

  {
    name: 'Concurrent Request Stress Test',
    test: async () => {
      const promises = [];
      for (let i = 0; i < 10; i++) {
        promises.push(
          axios.get(`${BACKEND_URL}/api/projects`).catch(err => ({
            error: err.response?.data || err.message,
            status: err.response?.status
          }))
        );
      }
      
      const results = await Promise.all(promises);
      const errors = results.filter(r => r.error);
      return { 
        success: true, 
        totalRequests: 10,
        errors: errors.length,
        errorDetails: errors
      };
    }
  }
];

async function runTests() {
  console.log('🧪 Starting Error Reproduction Tests...\n');
  
  for (const scenario of testScenarios) {
    console.log(`📋 Testing: ${scenario.name}`);
    
    try {
      const startTime = Date.now();
      const result = await scenario.test();
      const duration = Date.now() - startTime;
      
      console.log(`  ⏱️  Duration: ${duration}ms`);
      console.log(`  📊 Result:`, JSON.stringify(result, null, 2));
      
      // Check for [object Object] patterns
      const resultStr = JSON.stringify(result);
      if (resultStr.includes('[object Object]')) {
        console.log('  🚨 FOUND [object Object] ERROR!');
      }
      
    } catch (error) {
      console.log(`  ❌ Test failed:`, error.message);
      if (error.message.includes('[object Object]')) {
        console.log('  🚨 FOUND [object Object] ERROR IN EXCEPTION!');
      }
    }
    
    console.log('');
  }
  
  console.log('🏁 Error reproduction tests completed');
}

// Browser simulation tests using HTTP requests to mimic frontend behavior
async function simulateBrowserWorkflows() {
  console.log('\n🌐 Starting Browser Workflow Simulation...\n');
  
  const workflows = [
    {
      name: 'Dashboard Load Simulation',
      steps: [
        () => axios.get(`${BACKEND_URL}/api/projects`),
        () => axios.get(`${BACKEND_URL}/health`)
      ]
    },
    {
      name: 'Project Creation Workflow',
      steps: [
        () => axios.post(`${BACKEND_URL}/api/projects`, {
          name: 'Test Project',
          description: 'Test Description',
          cameraModel: 'Test Camera',
          cameraView: 'Front-facing VRU',
          signalType: 'GPIO'
        }),
        (projectId) => axios.get(`${BACKEND_URL}/api/projects/${projectId}`)
      ]
    },
    {
      name: 'Error Boundary Test',
      steps: [
        () => axios.get(`${BACKEND_URL}/api/projects/invalid-uuid`),
        () => axios.delete(`${BACKEND_URL}/api/projects/nonexistent`),
        () => axios.put(`${BACKEND_URL}/api/projects/invalid`, { invalid: 'data' })
      ]
    }
  ];
  
  for (const workflow of workflows) {
    console.log(`🔄 Running: ${workflow.name}`);
    
    let context = null;
    for (let i = 0; i < workflow.steps.length; i++) {
      try {
        console.log(`  Step ${i + 1}...`);
        const result = await workflow.steps[i](context);
        console.log(`    ✅ Success: ${result.status}`);
        
        // Extract project ID for chained requests
        if (result.data?.id) {
          context = result.data.id;
        }
        
      } catch (error) {
        console.log(`    ❌ Error: ${error.response?.status || 'Network'} - ${error.response?.data || error.message}`);
        
        // Check for [object Object] in errors
        const errorStr = JSON.stringify(error.response?.data || error.message);
        if (errorStr.includes('[object Object]')) {
          console.log('    🚨 FOUND [object Object] ERROR!');
        }
      }
    }
    console.log('');
  }
}

// Run all tests
async function main() {
  try {
    await runTests();
    await simulateBrowserWorkflows();
    
    console.log('\n📈 Summary:');
    console.log('- Check logs above for any [object Object] errors');
    console.log('- Monitor browser console at http://localhost:3000 for additional errors');
    console.log('- Test completed successfully');
    
  } catch (error) {
    console.error('💥 Test suite failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { testScenarios, simulateBrowserWorkflows };