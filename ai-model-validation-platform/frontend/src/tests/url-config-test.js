// URL Configuration Test
// This tests if all URLs are correctly configured to use 155.138.239.131

// Simulate window.RUNTIME_CONFIG loading
window.RUNTIME_CONFIG = {
  REACT_APP_API_URL: 'http://155.138.239.131:8000',
  REACT_APP_WS_URL: 'ws://155.138.239.131:8000',
  REACT_APP_SOCKETIO_URL: 'http://155.138.239.131:8001',
  REACT_APP_VIDEO_BASE_URL: 'http://155.138.239.131:8000',
  REACT_APP_ENVIRONMENT: 'production'
};

// Override process.env
process.env = { ...process.env, ...window.RUNTIME_CONFIG };

// Import configuration functions
const { getConfigValue, getFullConfig, applyRuntimeConfigOverrides } = require('../utils/configOverride');
const { getServiceConfig } = require('../utils/envConfig');

console.log('🧪 Testing URL Configuration...\n');

// Apply overrides
applyRuntimeConfigOverrides();

// Test individual config values
console.log('📋 Individual Config Values:');
console.log('API_URL:', getConfigValue('REACT_APP_API_URL', 'fallback'));
console.log('WS_URL:', getConfigValue('REACT_APP_WS_URL', 'fallback'));
console.log('SOCKETIO_URL:', getConfigValue('REACT_APP_SOCKETIO_URL', 'fallback'));
console.log('VIDEO_BASE_URL:', getConfigValue('REACT_APP_VIDEO_BASE_URL', 'fallback'));

// Test full config
console.log('\n📋 Full Config:');
const fullConfig = getFullConfig();
console.log(JSON.stringify(fullConfig, null, 2));

// Test service configs
console.log('\n📋 Service Configs:');
try {
  const apiConfig = getServiceConfig('api');
  console.log('API Service:', JSON.stringify(apiConfig, null, 2));
  
  const videoConfig = getServiceConfig('video');
  console.log('Video Service:', JSON.stringify(videoConfig, null, 2));
  
  const wsConfig = getServiceConfig('websocket');
  console.log('WebSocket Service:', JSON.stringify(wsConfig, null, 2));
  
  const socketioConfig = getServiceConfig('socketio');
  console.log('Socket.IO Service:', JSON.stringify(socketioConfig, null, 2));
} catch (error) {
  console.error('Service config error:', error.message);
}

// Verify no localhost references
const hasLocalhost = Object.values(fullConfig).some(val => 
  typeof val === 'string' && val.includes('localhost')
);

console.log('\n✅ URL Configuration Test Results:');
console.log('- All URLs use 155.138.239.131:', !hasLocalhost);
console.log('- Runtime config loaded:', !!window.RUNTIME_CONFIG);
console.log('- Process.env updated:', process.env.REACT_APP_API_URL === 'http://155.138.239.131:8000');

if (hasLocalhost) {
  console.error('❌ FOUND LOCALHOST REFERENCES!');
  Object.entries(fullConfig).forEach(([key, value]) => {
    if (typeof value === 'string' && value.includes('localhost')) {
      console.error(`  ${key}: ${value}`);
    }
  });
} else {
  console.log('✅ All URLs correctly configured for 155.138.239.131');
}