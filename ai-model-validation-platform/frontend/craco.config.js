const { BundleAnalyzerPlugin } = require('webpack-bundle-analyzer');

module.exports = {
  webpack: {
    configure: (webpackConfig, { env }) => {
      // Production optimizations
      if (env === 'production') {
        // Add bundle analyzer
        if (process.env.ANALYZE) {
          webpackConfig.plugins.push(
            new BundleAnalyzerPlugin({
              analyzerMode: 'static',
              openAnalyzer: false,
              reportFilename: 'bundle-analysis-report.html',
              generateStatsFile: true,
              statsFilename: 'bundle-analysis-report.json',
            })
          );
        }

        // Enhanced code splitting
        webpackConfig.optimization.splitChunks = {
          chunks: 'all',
          minSize: 20000,
          maxSize: 244000,
          cacheGroups: {
            default: {
              minChunks: 2,
              priority: -20,
              reuseExistingChunk: true,
            },
            vendor: {
              test: /[\\/]node_modules[\\/]/,
              name: 'vendors',
              priority: -10,
              chunks: 'all',
            },
            mui: {
              test: /[\\/]node_modules[\\/]@mui[\\/]/,
              name: 'mui',
              chunks: 'all',
              priority: 20,
            },
            react: {
              test: /[\\/]node_modules[\\/](react|react-dom|react-router-dom)[\\/]/,
              name: 'react',
              chunks: 'all',
              priority: 30,
            },
            icons: {
              test: /[\\/]node_modules[\\/]@mui[\\/]icons-material[\\/]/,
              name: 'mui-icons',
              chunks: 'all',
              priority: 25,
            },
            charts: {
              test: /[\\/]node_modules[\\/]recharts[\\/]/,
              name: 'charts',
              chunks: 'all',
              priority: 15,
            },
            common: {
              name: 'common',
              minChunks: 2,
              priority: 5,
              reuseExistingChunk: true,
            },
          },
        };

        // Tree shaking optimizations
        webpackConfig.optimization.usedExports = true;
        webpackConfig.optimization.sideEffects = false;
      }

      return webpackConfig;
    },
  },
  babel: {
    plugins: [
      // Optimize Material-UI imports
      [
        'babel-plugin-import',
        {
          libraryName: '@mui/material',
          libraryDirectory: '',
          camel2DashComponentName: false,
        },
        'core',
      ],
      [
        'babel-plugin-import',
        {
          libraryName: '@mui/icons-material',
          libraryDirectory: '',
          camel2DashComponentName: false,
        },
        'icons',
      ],
    ],
  },
};