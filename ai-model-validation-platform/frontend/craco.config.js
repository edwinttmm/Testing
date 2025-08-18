const { BundleAnalyzerPlugin } = require('webpack-bundle-analyzer');
const path = require('path');
const { detectGPU } = require('./src/utils/gpu-detection.js');

// Detect environment and GPU capabilities
const gpuInfo = detectGPU();
const isWindows = process.platform === 'win32';
const isMingw = process.env.MSYSTEM && process.env.MSYSTEM.includes('MINGW');

console.log('🔧 CRACO Config - Environment Detection:');
console.log('  Platform:', process.platform);
console.log('  Windows:', isWindows);
console.log('  MINGW64:', isMingw);
console.log('  GPU:', gpuInfo.name, '(' + gpuInfo.mode + ')');

module.exports = {
  devServer: {
    setupMiddlewares: (middlewares, devServer) => {
      // Health check endpoint
      devServer.app.get('/api/health', (req, res) => {
        res.json({
          status: 'ok',
          timestamp: new Date().toISOString(),
          environment: process.env.NODE_ENV,
          gpu: gpuInfo
        });
      });
      return middlewares;
    },
    proxy: {
      '/api': {
        target: process.env.REACT_APP_API_URL || 'http://155.138.239.131:8000',
        changeOrigin: true,
        secure: false,
        logLevel: 'debug',
        onError: (err, req, res) => {
          console.error('Proxy error:', err.message);
          res.status(500).json({ error: 'Proxy error', message: err.message });
        }
      }
    },
    compress: true,
    hot: true,
    liveReload: true,
    allowedHosts: 'all',
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
      'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization'
    }
  },
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
        
        // Windows/MINGW64 specific optimizations
        if (isWindows || isMingw) {
          webpackConfig.resolve.fallback = {
            ...webpackConfig.resolve.fallback,
            "path": require.resolve("path-browserify"),
            "os": require.resolve("os-browserify/browser"),
            "crypto": require.resolve("crypto-browserify"),
            "stream": require.resolve("stream-browserify"),
            "buffer": require.resolve("buffer")
          };
        }
      }
      
      // Path aliases for cleaner imports
      webpackConfig.resolve.alias = {
        ...webpackConfig.resolve.alias,
        '@': path.resolve(__dirname, 'src'),
        '@components': path.resolve(__dirname, 'src/components'),
        '@pages': path.resolve(__dirname, 'src/pages'),
        '@services': path.resolve(__dirname, 'src/services'),
        '@utils': path.resolve(__dirname, 'src/utils'),
        '@types': path.resolve(__dirname, 'src/types'),
        '@hooks': path.resolve(__dirname, 'src/hooks'),
        '@tests': path.resolve(__dirname, 'src/tests')
      };
      
      // GPU-aware optimizations
      if (gpuInfo.available) {
        webpackConfig.optimization.splitChunks.cacheGroups.gpu = {
          test: /[\/]node_modules[\/](@tensorflow|three\.js)[\/]/,
          name: 'gpu-libraries',
          chunks: 'all',
          priority: 40
        };
      }

      return webpackConfig;
    },
  },
  babel: {
    plugins: [
      // Fix Babel loose mode consistency
      [
        '@babel/plugin-transform-class-properties',
        {
          loose: true,
        },
      ],
      [
        '@babel/plugin-transform-private-methods',
        {
          loose: true,
        },
      ],
      [
        '@babel/plugin-transform-private-property-in-object',
        {
          loose: true,
        },
      ],
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
    presets: [
      [
        '@babel/preset-env',
        {
          loose: true,
          targets: {
            browsers: [
              '>0.2%',
              'not dead',
              'not op_mini all'
            ]
          },
          useBuiltIns: 'entry',
          corejs: 3
        }
      ],
      '@babel/preset-react',
      '@babel/preset-typescript'
    ]
  },
  jest: {
    configure: {
      testEnvironment: 'jsdom',
      setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],
      moduleNameMapper: {
        '^@/(.*)$': '<rootDir>/src/$1',
        '^@components/(.*)$': '<rootDir>/src/components/$1',
        '^@pages/(.*)$': '<rootDir>/src/pages/$1',
        '^@services/(.*)$': '<rootDir>/src/services/$1',
        '^@utils/(.*)$': '<rootDir>/src/utils/$1',
        '^@types/(.*)$': '<rootDir>/src/types/$1',
        '^@hooks/(.*)$': '<rootDir>/src/hooks/$1',
        '^@tests/(.*)$': '<rootDir>/src/tests/$1'
      },
      collectCoverageFrom: [
        'src/**/*.{ts,tsx}',
        '!src/**/*.d.ts',
        '!src/index.tsx',
        '!src/reportWebVitals.ts'
      ],
      coverageThreshold: {
        global: {
          branches: 70,
          functions: 70,
          lines: 70,
          statements: 70
        }
      },
      testMatch: [
        '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
        '<rootDir>/src/**/*.(test|spec).{js,jsx,ts,tsx}'
      ],
      transformIgnorePatterns: [
        '[/\\\\]node_modules[/\\\\].+\\.(js|jsx|mjs|cjs|ts|tsx)$',
        '^.+\\.module\\.(css|sass|scss)$'
      ]
    }
  },
};