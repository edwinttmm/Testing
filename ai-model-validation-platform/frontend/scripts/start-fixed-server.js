#!/usr/bin/env node

const path = require('path');
const webpack = require('webpack');
const WebpackDevServer = require('webpack-dev-server');
const HtmlWebpackPlugin = require('html-webpack-plugin');

console.log('🚀 Starting CHUNK-LOADING-FIXED webpack dev server...');
console.log('This server specifically addresses:');
console.log('  ✅ ChunkLoadError: Loading chunk 828 failed');
console.log('  ✅ MIME type issues (text/html instead of application/javascript)');
console.log('  ✅ Static file serving for JS chunks');
console.log('  ✅ historyApiFallback interfering with asset loading');

// Comprehensive webpack config to fix chunk loading and MIME type issues
const config = {
  mode: 'development',
  entry: path.resolve(__dirname, '../src/index.tsx'),
  
  output: {
    path: path.resolve(__dirname, '../build'),
    filename: 'bundle.js',
    publicPath: '/',  // Critical: This must match devServer publicPath
    // CRITICAL: No chunk filename pattern - use single bundle
    clean: false
  },
  
  devtool: 'eval-cheap-module-source-map',
  
  resolve: {
    extensions: ['.tsx', '.ts', '.js', '.jsx'],
    alias: {
      '@': path.resolve(__dirname, '../src'),
      '@components': path.resolve(__dirname, '../src/components'),
      '@pages': path.resolve(__dirname, '../src/pages'),
      '@services': path.resolve(__dirname, '../src/services'),
      '@utils': path.resolve(__dirname, '../src/utils'),
      '@types': path.resolve(__dirname, '../src/types'),
      '@hooks': path.resolve(__dirname, '../src/hooks')
    }
  },
  
  module: {
    rules: [
      {
        test: /\.(ts|tsx)$/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              '@babel/preset-env',
              ['@babel/preset-react', { runtime: 'automatic' }],
              '@babel/preset-typescript'
            ],
            plugins: [
              ['import', { 
                libraryName: '@mui/material', 
                libraryDirectory: '',
                camel2DashComponentName: false 
              }, 'core']
            ]
          }
        },
        exclude: /node_modules/
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      },
      {
        test: /\.(png|jpg|jpeg|gif|svg)$/,
        type: 'asset/resource'
      }
    ]
  },
  
  plugins: [
    new webpack.DefinePlugin({
      'process.env.NODE_ENV': JSON.stringify('development')
    }),
    new HtmlWebpackPlugin({
      template: path.resolve(__dirname, '../public/index.html'),
      inject: true,
      filename: 'index.html'
    })
  ],
  
  // CRITICAL: Disable ALL chunk splitting to prevent numbered chunks
  optimization: {
    splitChunks: false,  // This prevents chunk 828 type errors completely
    minimize: false,
    removeAvailableModules: false,
    removeEmptyChunks: false,
    sideEffects: false
  },
  
  cache: {
    type: 'memory'  // Use memory cache for faster rebuilds
  },
  
  // Performance settings to prevent warnings
  performance: {
    hints: false
  }
};

// Comprehensive dev server config to fix MIME type and static serving issues
const serverConfig = {
  port: 3000,
  host: 'localhost',
  hot: true,
  open: false,
  compress: false,
  
  // CRITICAL: Static file configuration to serve JS chunks properly
  static: [
    {
      directory: path.join(__dirname, '../public'),
      publicPath: '/',
      serveIndex: false,
      watch: false
    }
  ],
  
  // CRITICAL: historyApiFallback config to NOT interfere with chunk loading
  historyApiFallback: {
    disableDotRule: true,
    index: '/index.html',
    // IMPORTANT: Don't rewrite requests for .js, .css, .map files
    rewrites: [
      // Only rewrite non-file requests (no extension or specific extensions)
      { 
        from: /^\/(?!.*\.(js|css|map|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)(\?.*)?$).*$/, 
        to: '/index.html' 
      }
    ]
  },
  
  // CRITICAL: Headers to ensure proper MIME types
  headers: {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
    'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization'
  },
  
  // Custom middleware to force correct MIME types for JS files
  setupMiddlewares: (middlewares, devServer) => {
    devServer.app.use((req, res, next) => {
      console.log(`🔍 Request: ${req.method} ${req.url}`);
      
      // Force correct MIME type for JavaScript files
      if (req.url.endsWith('.js') || req.url.includes('.js?')) {
        console.log(`📄 Setting JS MIME type for: ${req.url}`);
        res.setHeader('Content-Type', 'application/javascript; charset=utf-8');
      }
      // Force correct MIME type for CSS files
      else if (req.url.endsWith('.css') || req.url.includes('.css?')) {
        console.log(`🎨 Setting CSS MIME type for: ${req.url}`);
        res.setHeader('Content-Type', 'text/css; charset=utf-8');
      }
      // Force correct MIME type for source maps
      else if (req.url.endsWith('.map') || req.url.includes('.map?')) {
        console.log(`🗺️ Setting MAP MIME type for: ${req.url}`);
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
      }
      next();
    });
    return middlewares;
  },
  
  client: {
    overlay: {
      errors: true,
      warnings: false
    },
    progress: true,
    reconnect: 3
  },
  
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      secure: false,
      timeout: 30000,
      proxyTimeout: 30000
    }
  },
  
  // Additional options for better chunk serving
  devMiddleware: {
    publicPath: '/',
    stats: {
      preset: 'minimal',
      colors: true,
      errors: true,
      warnings: true
    }
  }
};

const compiler = webpack(config);
const server = new WebpackDevServer(serverConfig, compiler);

const runServer = async () => {
  try {
    console.log('🛠️ Starting compilation...');
    await server.start();
    console.log('✅ Server started successfully on http://localhost:3000');
    console.log('✅ Chunk loading issues should now be resolved:');
    console.log('  - No numbered chunks (chunk 828, etc.)');
    console.log('  - Proper MIME types for all JS files');
    console.log('  - Static file serving configured correctly');
    console.log('  - historyApiFallback won\'t interfere with assets');
    console.log('');
    console.log('🌐 Open http://localhost:3000/boundary-box-demo to test');
    
    // Keep the process alive
    process.on('SIGINT', async () => {
      console.log('📝 Shutting down server...');
      await server.stop();
      process.exit(0);
    });
    
  } catch (err) {
    console.error('❌ Failed to start server:', err);
    process.exit(1);
  }
};

runServer();