const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { ProvidePlugin } = require('webpack');

// Ultra-minimal webpack config with ZERO websocket client injection
module.exports = {
  mode: 'development',
  entry: './src/index.tsx',
  target: 'web',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'app.js',
    publicPath: '/',
    clean: true,
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js', '.jsx'],
    fallback: {
      "crypto": require.resolve("crypto-browserify"),
      "stream": require.resolve("stream-browserify"),
      "buffer": require.resolve("buffer"),
      "path": require.resolve("path-browserify"),
      "os": require.resolve("os-browserify/browser"),
    }
  },
  module: {
    rules: [
      // Use the existing babel-preset-react-app
      {
        test: /\.(js|jsx|ts|tsx)$/,
        exclude: /node_modules/,
        use: [
          {
            loader: require.resolve('babel-loader'),
            options: {
              presets: [require.resolve('babel-preset-react-app')],
              cacheDirectory: true,
              cacheCompression: false,
              compact: false,
            }
          }
        ]
      },
      // CSS
      {
        test: /\.css$/,
        use: [
          require.resolve('style-loader'),
          {
            loader: require.resolve('css-loader'),
            options: {
              importLoaders: 1,
            }
          }
        ],
      },
      // Images and assets
      {
        test: /\.(png|svg|jpg|jpeg|gif|ico)$/i,
        type: 'asset/resource',
        generator: {
          filename: 'static/media/[name].[hash:8][ext]'
        }
      },
      // Fonts
      {
        test: /\.(woff|woff2|eot|ttf|otf)$/i,
        type: 'asset/resource',
        generator: {
          filename: 'static/media/[name].[hash:8][ext]'
        }
      },
    ],
  },
  plugins: [
    new ProvidePlugin({
      Buffer: ['buffer', 'Buffer'],
      process: 'process/browser',
    }),
    new HtmlWebpackPlugin({
      template: './public/index.html',
      inject: 'body',
      scriptLoading: 'blocking',
    }),
  ],
  devServer: {
    static: [
      {
        directory: path.join(__dirname, 'public'),
        publicPath: '/',
        serveIndex: false,
        watch: false,
      }
    ],
    port: 3000,
    host: 'localhost',
    open: false,
    hot: false,               // Disable Hot Module Replacement
    liveReload: false,        // Disable live reload
    client: false,            // Completely disable client-side code injection
    webSocketServer: false,   // Disable WebSocket server entirely
    compress: false,
    historyApiFallback: {
      disableDotRule: true,
      index: '/index.html'
    },
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-cache',
    },
    allowedHosts: 'all',
    devMiddleware: {
      writeToDisk: false,
      publicPath: '/',
      stats: 'errors-only',
    },
    setupMiddlewares: (middlewares, devServer) => {
      // Filter out ALL webpack-dev-server client middlewares
      return middlewares.filter(middleware => {
        const name = middleware.name || '';
        const path = middleware.path || '';
        return !name.includes('webpack-dev-server') && 
               !name.includes('hmr') && 
               !name.includes('hot') &&
               !name.includes('websocket') &&
               !name.includes('sockjs') &&
               !path.includes('__webpack') &&
               !path.includes('hot-update');
      });
    }
  },
  optimization: {
    runtimeChunk: false,     // Prevent runtime chunk that injects websocket code
    splitChunks: false,      // Keep everything in one bundle to avoid chunk loading
    minimize: false,         // Keep readable for debugging
  },
  stats: {
    all: false,
    errors: true,
    warnings: false,
    colors: true,
    timings: true,
  },
  performance: {
    hints: false,
  },
  infrastructureLogging: {
    level: 'error',
  },
  // Explicitly disable any webpack features that might inject client code
  watchOptions: {
    ignored: /node_modules/,
  },
};