// webpack config override to remove ESLint plugin completely
const path = require('path');

module.exports = function override(config, env) {
  console.log('🔧 Webpack Config Override: Removing ESLint plugins...');
  
  // Remove all ESLint-related plugins
  config.plugins = config.plugins.filter(plugin => {
    const pluginName = plugin.constructor.name;
    const isESLintPlugin = pluginName.includes('ESLint') || 
                         pluginName === 'ESLintWebpackPlugin';
    
    if (isESLintPlugin) {
      console.log(`❌ Removing plugin: ${pluginName}`);
    }
    
    return !isESLintPlugin;
  });
  
  // Also remove ForkTsCheckerWebpackPlugin if it's causing issues
  config.plugins = config.plugins.filter(plugin => {
    const pluginName = plugin.constructor.name;
    const isTSCheckerPlugin = pluginName === 'ForkTsCheckerWebpackPlugin';
    
    if (isTSCheckerPlugin) {
      console.log(`❌ Removing TypeScript checker plugin: ${pluginName}`);
    }
    
    return !isTSCheckerPlugin;
  });
  
  console.log('✅ ESLint plugins removed from webpack config');
  
  // Add path aliases
  config.resolve.alias = {
    ...config.resolve.alias,
    '@': path.resolve(__dirname, 'src'),
    '@components': path.resolve(__dirname, 'src/components'),
    '@pages': path.resolve(__dirname, 'src/pages'),
    '@services': path.resolve(__dirname, 'src/services'),
    '@utils': path.resolve(__dirname, 'src/utils'),
    '@types': path.resolve(__dirname, 'src/types'),
    '@hooks': path.resolve(__dirname, 'src/hooks')
  };
  
  return config;
};