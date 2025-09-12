const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const webpack = require('webpack');
const express = require('express');
const fs = require('fs');

// Custom plugin to strip ALL webpack-dev-server client code
class StripWebSocketClientPlugin {
  apply(compiler) {
    compiler.hooks.compilation.tap('StripWebSocketClientPlugin', (compilation) => {
      compilation.hooks.processAssets.tap(
        {
          name: 'StripWebSocketClientPlugin',
          stage: webpack.Compilation.PROCESS_ASSETS_STAGE_OPTIMIZE_SIZE,
        },
        (assets) => {
          Object.keys(assets).forEach((filename) => {
            if (filename.endsWith('.js')) {
              const asset = assets[filename];
              let source = asset.source();
              
              // Nuclear approach: Remove ALL WebSocket related code
              const patterns = [
                // Remove webpack-dev-server client entirely
                /\/\*\*\*\/ ".*webpack-dev-server.*?",/gs,
                /\/\*\*\*\/ ".*webpack\/hot.*?",/gs,
                /\/\*\*\*\/ ".*sockjs-client.*?",/gs,
                /\/\*\*\*\/ ".*ansi-html-community.*?",/gs,
                /\/\*\*\*\/ ".*html-entities.*?",/gs,
                // Remove WebSocket constructors and connections
                /new WebSocket\([^)]*\)/gs,
                /WebSocket\(/gs,
                /ws:\/\/[^"'\s)]+/gs,
                /wss:\/\/[^"'\s)]+/gs,
                // Remove entire webpack HMR runtime
                /module\.hot[\s\S]*?(?=\/\*\*\*\/|$)/gs,
                /webpackHotUpdate[\s\S]*?(?=\/\*\*\*\/|$)/gs,
                /module\.hot\.accept[\s\S]*?;/gs,
                /if\s*\(\s*module\.hot\s*\)[\s\S]*?}/gs,
                // Remove WebSocketClient specifically
                /function WebSocketClient[\s\S]*?(?=function|var|const|let|$)/gs,
                /class WebSocketClient[\s\S]*?(?=function|var|const|let|class|$)/gs,
                /WebSocketClient\s*=\s*[\s\S]*?;/gs,
                // Remove any URL containing ws://
                /["'][^"']*ws:\/\/[^"']*["']/gs,
                // Remove sockjs and related imports
                /require\(["'][^"']*sockjs[^"']*["']\)/gs,
                /import[^;]*sockjs[^;]*;/gs,
                // Remove hot reload infrastructure
                /__webpack_require__\.hmrD[\s\S]*?;/gs,
                /__webpack_require__\.hmrC[\s\S]*?;/gs,
                /hotCreateModule[\s\S]*?(?=function|var|const|let|$)/gs,
                // Remove error overlay
                /createErrorOverlay[\s\S]*?(?=function|var|const|let|$)/gs,
                /showErrorOverlay[\s\S]*?(?=function|var|const|let|$)/gs,
                // Remove any remaining client connection attempts
                /socket\s*=\s*new[\s\S]*?;/gs,
                /connect\s*\([^)]*3000[^)]*\)/gs
              ];
              
              patterns.forEach(pattern => {
                source = source.replace(pattern, '');
              });
              
              // Additional cleanup - remove empty webpack module containers
              source = source.replace(/\/\*\*\*\/ "",?/gs, '');
              source = source.replace(/,\s*,/gs, ',');
              source = source.replace(/\[\s*,/gs, '[');
              source = source.replace(/,\s*\]/gs, ']');
              
              compilation.updateAsset(filename, new webpack.sources.RawSource(source));
            }
          });
        }
      );
    });
  }
}

module.exports = {
  mode: 'development',
  entry: {
    main: [
      // NO webpack-dev-server client entry points
      './src/index.tsx'
    ]
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'static/js/[name].js',
    publicPath: '/'
  },
  devtool: false, // No source maps to avoid debug connections
  module: {
    rules: [
      {
        test: /\.(js|jsx|ts|tsx)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              ['@babel/preset-env', { targets: 'defaults' }],
              ['@babel/preset-react', { runtime: 'automatic' }]
            ]
          }
        }
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      },
      {
        test: /\.(png|svg|jpg|jpeg|gif)$/i,
        type: 'asset/resource'
      }
    ]
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: './public/index.html',
      inject: true,
      minify: false
    }),
    new StripWebSocketClientPlugin(),
    new webpack.DefinePlugin({
      'process.env.NODE_ENV': JSON.stringify('development'),
      'process.env.DISABLE_WEBSOCKET': JSON.stringify('true'),
      'process.env.DISABLE_HMR': JSON.stringify('true')
    }),
    // Ignore webpack-dev-server modules entirely
    new webpack.IgnorePlugin({
      resourceRegExp: /webpack-dev-server/
    }),
    new webpack.IgnorePlugin({
      resourceRegExp: /sockjs-client/
    })
  ],
  resolve: {
    extensions: ['.js', '.jsx', '.ts', '.tsx'],
    alias: {
      // Redirect any webpack-dev-server imports to empty module
      'webpack-dev-server/client': false,
      'webpack/hot/dev-server': false,
      'sockjs-client': false
    }
  },
  optimization: {
    minimize: false, // Keep readable for debugging
    splitChunks: false // Single bundle to control content
  },
  // Completely disable webpack-dev-server
  devServer: undefined,
  infrastructureLogging: {
    level: 'error'
  },
  stats: 'errors-only'
};

// Custom build and serve function
function buildAndServe() {
  const webpack = require('webpack');
  const config = module.exports;
  
  console.log('🚀 Building bundle without WebSocket client...');
  
  const compiler = webpack(config);
  
  compiler.run((err, stats) => {
    if (err) {
      console.error('❌ Build failed:', err);
      return;
    }
    
    if (stats.hasErrors()) {
      console.error('❌ Build errors:', stats.toJson().errors);
      return;
    }
    
    console.log('✅ Build completed successfully!');
    
    // Start Express server to serve built files
    const app = express();
    const distPath = path.resolve(__dirname, 'dist');
    
    // Serve static files
    app.use(express.static(distPath));
    
    // Copy config.js if it exists
    const configPath = path.resolve(__dirname, 'public/config.js');
    if (fs.existsSync(configPath)) {
      app.get('/config.js', (req, res) => {
        res.sendFile(configPath);
      });
    }
    
    // Fallback to index.html for SPA
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
    
    const port = process.env.PORT || 3000;
    app.listen(port, () => {
      console.log(`🎉 Server running at http://localhost:${port}`);
      console.log('🛡️  No WebSocket client injected!');
    });
  });
}

// Export build function for external use
if (typeof module !== 'undefined' && module.exports) {
  module.exports.buildAndServe = buildAndServe;
}
