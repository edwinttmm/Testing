// No-operation module to replace webpack-dev-server client modules
// This ensures NO client-side webpack dev server code gets injected

module.exports = function noop() {
  // Do nothing - completely disable webpack dev server client functionality
};

// Export empty functions for any expected client API
module.exports.sendMessage = function() {};
module.exports.connect = function() {};
module.exports.disconnect = function() {};
module.exports.reload = function() {};
module.exports.overlay = {
  showMessage: function() {},
  clear: function() {}
};

// Prevent any websocket connections
if (typeof window !== 'undefined') {
  window.__webpack_dev_server_client__ = undefined;
  window.__webpack_hot_update__ = undefined;
  window.__webpack_require__ = window.__webpack_require__ || function() { return {}; };
}