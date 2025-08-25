// Runtime Configuration Override
// This file provides runtime configuration that overrides compile-time settings
// Place this in /public to ensure it's always loaded fresh

window.RUNTIME_CONFIG = {
  REACT_APP_API_URL: 'http://155.138.239.131:8000',
  REACT_APP_WS_URL: 'ws://155.138.239.131:8000',
  REACT_APP_SOCKETIO_URL: 'http://155.138.239.131:8001',
  REACT_APP_VIDEO_BASE_URL: 'http://155.138.239.131:8000',
  REACT_APP_ENVIRONMENT: 'production'
};

// Override process.env at runtime
if (typeof process === 'undefined') {
  window.process = { env: {} };
}

Object.assign(process.env, window.RUNTIME_CONFIG);

console.log('🔧 Runtime Config Loaded:', window.RUNTIME_CONFIG);