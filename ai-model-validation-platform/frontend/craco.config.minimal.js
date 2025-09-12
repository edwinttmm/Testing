// Minimal CRACO config for debugging Docker startup issues
const path = require('path');

console.log('🔧 MINIMAL CRACO Config - Debug Mode');
console.log('  Environment:', process.env.NODE_ENV);
console.log('  Docker:', process.env.DOCKER);
console.log('  Host:', process.env.HOST);
console.log('  Port:', process.env.PORT);

module.exports = {
  devServer: {
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: 'all',
    headers: {
      'Access-Control-Allow-Origin': '*',
    },
    client: {
      webSocketURL: {
        hostname: '0.0.0.0',
        pathname: '/ws',
        port: 3000,
      },
    },
    // Minimal health check endpoint
    setupMiddlewares: (middlewares, devServer) => {
      devServer.app.get('/health', (req, res) => {
        res.json({ status: 'ok', timestamp: Date.now() });
      });
      return middlewares;
    },
  },
  webpack: {
    configure: (webpackConfig) => {
      // Minimal path aliases
      webpackConfig.resolve.alias = {
        ...webpackConfig.resolve.alias,
        '@': path.resolve(__dirname, 'src'),
      };
      return webpackConfig;
    },
  },
};