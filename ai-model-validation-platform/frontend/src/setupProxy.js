const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Default backend to FastAPI on :8000; allow override via REACT_APP_BACKEND_URL
  const TARGET = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
  const SERVICE_TOKEN = process.env.REACT_APP_SERVICE_TOKEN;

  app.use('/api', createProxyMiddleware({
    target: TARGET,
    changeOrigin: true
  }));

  app.use('/labjack', createProxyMiddleware({
    target: TARGET,
    changeOrigin: true
  }));

  // Service-token proxy: /svc/* → /labjack/* with header injected
  app.use('/svc', createProxyMiddleware({
    target: TARGET,
    changeOrigin: true,
    pathRewrite: { '^/svc': '/labjack' },
    onProxyReq: (proxyReq) => {
      if (SERVICE_TOKEN) proxyReq.setHeader('X-Service-Token', SERVICE_TOKEN);
    }
  }));
};
