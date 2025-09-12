const path = require('path');

module.exports = {
  devServer: {
    host: 'localhost',
    port: 3000,
    compress: true,
    hot: true,
    liveReload: true,
    allowedHosts: 'all',
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
      'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization'
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  },
  webpack: {
    configure: (webpackConfig) => {
      // Simple path aliases
      webpackConfig.resolve.alias = {
        ...webpackConfig.resolve.alias,
        '@': path.resolve(__dirname, 'src'),
        '@components': path.resolve(__dirname, 'src/components'),
        '@pages': path.resolve(__dirname, 'src/pages'),
        '@services': path.resolve(__dirname, 'src/services'),
        '@utils': path.resolve(__dirname, 'src/utils'),
        '@types': path.resolve(__dirname, 'src/types'),
        '@hooks': path.resolve(__dirname, 'src/hooks')
      };
      return webpackConfig;
    },
  },
  typescript: {
    enableTypeChecking: false // Disable TypeScript checking for faster startup
  }
};