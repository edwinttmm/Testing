/**
 * Localhost Configuration Test
 * Verifies that the application correctly uses localhost URLs for development
 */

console.log('🔧 Testing Localhost Configuration...');

// Test environment variables
const testEnvVars = {
  REACT_APP_API_URL: process.env.REACT_APP_API_URL,
  REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
  REACT_APP_SOCKETIO_URL: process.env.REACT_APP_SOCKETIO_URL,
  REACT_APP_VIDEO_BASE_URL: process.env.REACT_APP_VIDEO_BASE_URL,
  REACT_APP_ENVIRONMENT: process.env.REACT_APP_ENVIRONMENT,
  NODE_ENV: process.env.NODE_ENV
};

console.group('📋 Environment Variables');
Object.entries(testEnvVars).forEach(([key, value]) => {
  const isLocalhost = value && value.includes('localhost');
  console.log(`${isLocalhost ? '✅' : '❌'} ${key}: ${value || 'undefined'}`);
});
console.groupEnd();

// Test configuration validation
const expectedUrls = {
  'API URL': 'http://localhost:8000',
  'WebSocket URL': 'ws://localhost:8000', 
  'Socket.IO URL': 'http://localhost:8001',
  'Video Base URL': 'http://localhost:8000'
};

console.group('🎯 Configuration Validation');
let allValid = true;

if (testEnvVars.REACT_APP_API_URL !== expectedUrls['API URL']) {
  console.error(`❌ API URL mismatch: expected ${expectedUrls['API URL']}, got ${testEnvVars.REACT_APP_API_URL}`);
  allValid = false;
} else {
  console.log('✅ API URL correctly configured');
}

if (testEnvVars.REACT_APP_WS_URL !== expectedUrls['WebSocket URL']) {
  console.error(`❌ WebSocket URL mismatch: expected ${expectedUrls['WebSocket URL']}, got ${testEnvVars.REACT_APP_WS_URL}`);
  allValid = false;
} else {
  console.log('✅ WebSocket URL correctly configured');
}

if (testEnvVars.REACT_APP_SOCKETIO_URL !== expectedUrls['Socket.IO URL']) {
  console.error(`❌ Socket.IO URL mismatch: expected ${expectedUrls['Socket.IO URL']}, got ${testEnvVars.REACT_APP_SOCKETIO_URL}`);
  allValid = false;
} else {
  console.log('✅ Socket.IO URL correctly configured');
}

if (testEnvVars.REACT_APP_VIDEO_BASE_URL !== expectedUrls['Video Base URL']) {
  console.error(`❌ Video Base URL mismatch: expected ${expectedUrls['Video Base URL']}, got ${testEnvVars.REACT_APP_VIDEO_BASE_URL}`);
  allValid = false;
} else {
  console.log('✅ Video Base URL correctly configured');
}

console.groupEnd();

// Test runtime configuration if available
if (typeof window !== 'undefined' && window.RUNTIME_CONFIG) {
  console.group('🔧 Runtime Configuration');
  const runtimeConfig = window.RUNTIME_CONFIG;
  
  console.log('Runtime API URL:', runtimeConfig.REACT_APP_API_URL);
  console.log('Runtime WS URL:', runtimeConfig.REACT_APP_WS_URL);
  console.log('Runtime Socket.IO URL:', runtimeConfig.REACT_APP_SOCKETIO_URL);
  
  const runtimeValid = 
    runtimeConfig.REACT_APP_API_URL === expectedUrls['API URL'] &&
    runtimeConfig.REACT_APP_WS_URL === expectedUrls['WebSocket URL'] &&
    runtimeConfig.REACT_APP_SOCKETIO_URL === expectedUrls['Socket.IO URL'];
    
  console.log(`${runtimeValid ? '✅' : '❌'} Runtime configuration is ${runtimeValid ? 'valid' : 'invalid'}`);
  console.groupEnd();
}

// Final summary
console.group('📊 Test Summary');
if (allValid) {
  console.log('✅ All localhost configurations are valid!');
  console.log('🚀 Ready for local development');
} else {
  console.error('❌ Configuration issues detected');
  console.log('📝 Please check your .env.local file');
}
console.groupEnd();

// Export for programmatic use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    isValid: allValid,
    testResults: testEnvVars,
    expectedUrls
  };
}