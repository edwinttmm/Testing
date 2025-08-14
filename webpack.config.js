/**
 * Webpack Configuration for GPU Detection and Library Loading
 * Supports conditional bundling based on environment and runtime capabilities
 */

const path = require('path');
const webpack = require('webpack');

module.exports = (env, argv) => {
  const isProduction = argv.mode === 'production';
  const isDevelopment = !isProduction;

  // Environment variables for build-time configuration
  const FORCE_CPU_ONLY = process.env.REACT_APP_FORCE_CPU_ONLY === 'true';
  const DISABLE_GPU_DETECTION = process.env.REACT_APP_DISABLE_GPU_DETECTION === 'true';
  const PREFERRED_BACKEND = process.env.REACT_APP_PREFERRED_BACKEND || 'auto';
  const MINGW64_COMPAT = process.env.MINGW64_COMPAT === 'true';

  const config = {
    entry: './src/index.tsx',
    
    output: {
      path: path.resolve(__dirname, 'dist'),
      filename: isProduction ? '[name].[contenthash].js' : '[name].js',
      chunkFilename: isProduction ? '[name].[contenthash].chunk.js' : '[name].chunk.js',
      clean: true,
      publicPath: '/',
    },

    resolve: {
      extensions: ['.tsx', '.ts', '.js', '.jsx'],
      alias: {
        '@': path.resolve(__dirname, 'src'),
        '@utils': path.resolve(__dirname, 'src/utils'),
        '@config': path.resolve(__dirname, 'src/config'),
        '@libs': path.resolve(__dirname, 'src/libs'),
        '@components': path.resolve(__dirname, 'src/components'),
        '@hooks': path.resolve(__dirname, 'src/hooks'),
        '@types': path.resolve(__dirname, 'src/types'),
      },
      fallback: {
        // Node.js polyfills for browser
        'fs': false,
        'path': require.resolve('path-browserify'),
        'crypto': require.resolve('crypto-browserify'),
        'stream': require.resolve('stream-browserify'),
        'buffer': require.resolve('buffer'),
        'process': require.resolve('process/browser'),
        'util': require.resolve('util'),
        'assert': require.resolve('assert'),
        'url': require.resolve('url'),
        'querystring': require.resolve('querystring-es3'),
        // Disable Node.js specific modules for browser builds
        'child_process': false,
        'cluster': false,
        'dgram': false,
        'dns': false,
        'http': false,
        'http2': false,
        'https': false,
        'net': false,
        'os': false,
        'tls': false,
        'vm': false,
        'zlib': false,
      },
    },

    module: {
      rules: [
        {
          test: /\.tsx?$/,
          use: [
            {
              loader: 'ts-loader',
              options: {
                configFile: 'tsconfig.json',
                transpileOnly: isDevelopment,
              },
            },
          ],
          exclude: /node_modules/,
        },
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader'],
        },
        {
          test: /\.(png|jpe?g|gif|svg|webp|avif)$/i,
          type: 'asset/resource',
          generator: {
            filename: 'images/[name].[hash][ext]',
          },
        },
        {
          test: /\.(woff|woff2|eot|ttf|otf)$/i,
          type: 'asset/resource',
          generator: {
            filename: 'fonts/[name].[hash][ext]',
          },
        },
        // Handle .wasm files for OpenCV.js and other WASM libraries
        {
          test: /\.wasm$/,
          type: 'asset/resource',
          generator: {
            filename: 'wasm/[name].[hash][ext]',
          },
        },
      ],
    },

    plugins: [
      // Define environment variables for runtime
      new webpack.DefinePlugin({
        'process.env': {
          NODE_ENV: JSON.stringify(argv.mode || 'development'),
          REACT_APP_FORCE_CPU_ONLY: JSON.stringify(FORCE_CPU_ONLY),
          REACT_APP_DISABLE_GPU_DETECTION: JSON.stringify(DISABLE_GPU_DETECTION),
          REACT_APP_PREFERRED_BACKEND: JSON.stringify(PREFERRED_BACKEND),
          REACT_APP_DEBUG_GPU_INFO: JSON.stringify(process.env.REACT_APP_DEBUG_GPU_INFO || 'false'),
          MINGW64_COMPAT: JSON.stringify(MINGW64_COMPAT),
        },
      }),

      // Provide polyfills for Node.js globals
      new webpack.ProvidePlugin({
        Buffer: ['buffer', 'Buffer'],
        process: 'process/browser',
      }),

      // Ignore Node.js modules that shouldn't be bundled
      new webpack.IgnorePlugin({
        resourceRegExp: /^(fs|path|os|crypto)$/,
        contextRegExp: /node_modules/,
      }),
    ],

    optimization: {
      splitChunks: {
        chunks: 'all',
        cacheGroups: {
          // Separate bundle for TensorFlow.js (large library)
          tensorflow: {
            test: /[\\/]node_modules[\\/]@tensorflow[\\/]/,
            name: 'tensorflow',
            chunks: 'all',
            priority: 20,
          },
          
          // Separate bundle for OpenCV.js
          opencv: {
            test: /[\\/]node_modules[\\/]opencv/,
            name: 'opencv',
            chunks: 'all',
            priority: 19,
          },

          // Separate bundle for image processing libraries
          imageLibs: {
            test: /[\\/]node_modules[\\/](jimp|sharp)[\\/]/,
            name: 'image-libs',
            chunks: 'all',
            priority: 18,
          },

          // Common vendor bundle
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            chunks: 'all',
            priority: 10,
          },

          // Default bundle
          default: {
            minChunks: 2,
            priority: -10,
            reuseExistingChunk: true,
          },
        },
      },

      // Tree shaking and dead code elimination
      usedExports: true,
      sideEffects: false,
    },

    externals: {
      // Don't bundle these in the browser - they'll be loaded conditionally
      ...(typeof window !== 'undefined' ? {
        'sharp': 'commonjs sharp',
        'canvas': 'commonjs canvas',
        'opencv4nodejs': 'commonjs opencv4nodejs',
      } : {}),
    },

    devServer: {
      static: {
        directory: path.join(__dirname, 'public'),
      },
      compress: true,
      port: 3000,
      hot: true,
      open: true,
      historyApiFallback: true,
      headers: {
        // Enable SharedArrayBuffer for WASM libraries
        'Cross-Origin-Embedder-Policy': 'require-corp',
        'Cross-Origin-Opener-Policy': 'same-origin',
      },
    },

    devtool: isDevelopment ? 'eval-source-map' : 'source-map',

    performance: {
      // Increase bundle size limits for image processing libraries
      maxAssetSize: 10 * 1024 * 1024, // 10MB
      maxEntrypointSize: 10 * 1024 * 1024, // 10MB
      hints: isProduction ? 'warning' : false,
    },

    // Conditional compilation based on environment
    ...(FORCE_CPU_ONLY && {
      resolve: {
        ...config.resolve,
        alias: {
          ...config.resolve.alias,
          // Redirect GPU libraries to CPU-only versions
          '@tensorflow/tfjs': '@tensorflow/tfjs-cpu',
          '@tensorflow/tfjs-backend-webgl': '@tensorflow/tfjs-cpu',
        },
      },
    }),

    // MINGW64 compatibility adjustments
    ...(MINGW64_COMPAT && {
      resolve: {
        ...config.resolve,
        fallback: {
          ...config.resolve.fallback,
          // Additional MINGW64 specific fallbacks
          'child_process': false,
          'worker_threads': false,
        },
      },
    }),
  };

  return config;
};

// Additional configuration for different environments
if (process.env.NODE_ENV === 'test') {
  module.exports.target = 'node';
  module.exports.externals = {
    'canvas': 'commonjs canvas',
    'sharp': 'commonjs sharp',
    'opencv4nodejs': 'commonjs opencv4nodejs',
  };
}

// Export configuration function for dynamic environments
module.exports.createConfig = (options = {}) => {
  const {
    target = 'web',
    forceCPU = false,
    enableGPU = true,
    platform = 'browser',
  } = options;

  const baseConfig = module.exports({}, { mode: 'production' });

  if (forceCPU) {
    baseConfig.resolve.alias = {
      ...baseConfig.resolve.alias,
      '@tensorflow/tfjs': '@tensorflow/tfjs-cpu',
    };
  }

  if (target === 'node') {
    baseConfig.target = 'node';
    baseConfig.externals = {
      'canvas': 'commonjs canvas',
      'sharp': 'commonjs sharp',
      'opencv4nodejs': 'commonjs opencv4nodejs',
      'jimp': 'commonjs jimp',
    };
  }

  return baseConfig;
};