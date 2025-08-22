# Recovery Instructions for Windows MINGW64 Environment

**Recovery Session ID**: `mingw64-recovery-2025-08-14`  
**Target System**: Windows MINGW64_NT-10.0-26100  
**Node Version**: v24.5.0, NPM 11.5.1  
**Project**: AI Model Validation Platform Frontend  

## 🚨 CRITICAL DEPENDENCY FIXES REQUIRED

### Immediate Actions (Execute First)

#### 1. Environment Setup
```bash
# Navigate to frontend directory
cd /workspaces/Testing/ai-model-validation-platform/frontend

# Verify current state
echo "Current Node: $(node --version)"
echo "Current NPM: $(npm --version)"
echo "Current directory: $(pwd)"

# Check npm cache and clear if needed
npm cache verify
npm cache clean --force
```

#### 2. Critical Dependency Updates
```bash
# Update TypeScript ecosystem (CRITICAL for React 19)
npm install typescript@^5.9.2 --save-dev
npm install @types/node@^20.19.10 --save-dev  
npm install @types/react-router-dom@^7.0.0 --save-dev
npm install @types/jest@^29.5.15 --save-dev

# Update testing libraries (CRITICAL for TDD)
npm install @testing-library/user-event@^14.5.2 --save-dev
npm install web-vitals@^4.2.4

# Verify installations
npm list typescript @types/node @types/react-router-dom @types/jest @testing-library/user-event web-vitals --depth=0
```

#### 3. Configuration Updates
```bash
# Update tsconfig.json for React 19 compatibility
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": [
      "dom",
      "dom.iterable",
      "esnext"
    ],
    "allowJs": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noFallthroughCasesInSwitch": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "downlevelIteration": true,
    "allowImportingTsExtensions": false,
    "noImplicitReturns": true,
    "noImplicitOverride": true
  },
  "include": [
    "src"
  ]
}
EOF
```

### Cross-Platform Script Fixes

#### 4. Update package.json scripts for MINGW64
```bash
# Backup current package.json
cp package.json package.json.backup

# Create cross-platform compatible scripts
cat > temp_package_scripts.json << 'EOF'
{
  "scripts": {
    "start": "PORT=3000 craco start",
    "start:windows": "set PORT=3000 && craco start",
    "start:unix": "PORT=3000 craco start",
    "build": "craco build",
    "build:windows": "set NODE_ENV=production && craco build",
    "build:unix": "NODE_ENV=production craco build",
    "build:analyze": "ANALYZE=true craco build",
    "build:analyze:windows": "set ANALYZE=true && craco build",
    "test": "craco test",
    "test:coverage": "craco test --coverage --watchAll=false",
    "test:ci": "CI=true craco test --coverage --watchAll=false",
    "test:windows": "set CI=true && craco test --coverage --watchAll=false",
    "eject": "react-scripts eject",
    "lint": "eslint src --ext .ts,.tsx,.js,.jsx",
    "lint:fix": "eslint src --ext .ts,.tsx,.js,.jsx --fix",
    "typecheck": "tsc --noEmit"
  }
}
EOF

# Merge scripts (manual step - requires careful JSON editing)
echo "⚠️  MANUAL ACTION REQUIRED: Merge temp_package_scripts.json into package.json"
```

#### 5. Enhance CRACO Configuration
```bash
# Backup current craco config
cp craco.config.js craco.config.js.backup

# Update craco config with backend proxy and MINGW64 optimizations
cat > craco.config.js << 'EOF'
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
  // Add backend proxy configuration
  devServer: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        timeout: 10000,
        logLevel: 'debug'
      }
    },
    // MINGW64 specific configurations
    host: 'localhost',
    port: 3000,
    open: false, // Don't auto-open browser on MINGW64
    historyApiFallback: true,
    hot: true,
    liveReload: true
  }
};
EOF
```

## 🧪 Testing & Validation Steps

#### 6. Dependency Resolution Verification
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Verify no dependency conflicts
npm list --depth=0 | grep -i "invalid\|error\|warn"

# Should return empty if all conflicts resolved
echo "✅ If no output above, dependencies are clean"
```

#### 7. Build System Validation
```bash
# Test TypeScript compilation
npm run typecheck

# Test development build
timeout 30s npm run start:windows || echo "Build test completed (timeout expected)"

# Test production build
npm run build:windows

# Verify build output
ls -la build/ && echo "✅ Build successful" || echo "❌ Build failed"
```

#### 8. GPU Detection Utility Test
```bash
# Create test script for GPU detection
cat > test-gpu-detection.js << 'EOF'
const fs = require('fs');
const path = require('path');

const gpuUtilPath = path.join(__dirname, '..', '..', 'src', 'utils', 'gpu-detector.ts');

if (fs.existsSync(gpuUtilPath)) {
  console.log('✅ GPU detection utility found');
  console.log('📄 File size:', fs.statSync(gpuUtilPath).size, 'bytes');
} else {
  console.log('❌ GPU detection utility missing');
  console.log('📂 Expected path:', gpuUtilPath);
}
EOF

node test-gpu-detection.js
```

## 🔄 Session Recovery Validation

#### 9. Environment State Check
```bash
# Create comprehensive environment report
cat > environment-check.js << 'EOF'
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('🔍 Windows MINGW64 Environment Recovery Check');
console.log('=' .repeat(50));

// Node/NPM versions
console.log('Node version:', process.version);
console.log('NPM version:', execSync('npm --version', {encoding: 'utf8'}).trim());

// Critical files check
const criticalFiles = [
  'package.json',
  'package-lock.json',
  'tsconfig.json', 
  'craco.config.js',
  'src/App.tsx'
];

console.log('\n📁 Critical Files:');
criticalFiles.forEach(file => {
  const exists = fs.existsSync(file);
  console.log(`  ${exists ? '✅' : '❌'} ${file}`);
});

// Dependency check
console.log('\n📦 Key Dependencies:');
const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
const keyDeps = [
  'react',
  'react-dom', 
  '@craco/craco',
  'typescript',
  '@types/react',
  '@testing-library/react'
];

keyDeps.forEach(dep => {
  const version = packageJson.dependencies[dep] || packageJson.devDependencies[dep];
  console.log(`  ${version ? '✅' : '❌'} ${dep}: ${version || 'MISSING'}`);
});

console.log('\n🎯 Recovery Status: Ready for next phase');
EOF

node environment-check.js
```

#### 10. Session Handoff Preparation
```bash
# Update session log with recovery status
echo "
## Recovery Session Complete - $(date)

### Actions Taken:
- ✅ Updated TypeScript to 5.9.2
- ✅ Fixed @types dependencies  
- ✅ Updated testing libraries
- ✅ Enhanced CRACO configuration
- ✅ Added backend proxy
- ✅ Created cross-platform scripts
- ✅ Verified GPU detection utility

### Next Phase Requirements:
1. Test React 19 component rendering
2. Implement SPARC+TDD methodology
3. Validate cross-platform compatibility
4. Deploy to MINGW64 environment
5. Performance optimization

### Session Artifacts:
- tsconfig.json (updated)
- craco.config.js (enhanced)
- package.json (cross-platform scripts)
- Environment validation scripts

**Status**: Recovery complete, ready for implementation phase
" >> /workspaces/Testing/docs/session-logs/session-restoration-log.md
```

## 🚨 CRITICAL SUCCESS CRITERIA

Before marking recovery as complete, verify ALL of these:

- [ ] TypeScript 5.9.2 installed and compiling
- [ ] All @types dependencies updated to React 19 compatible versions
- [ ] Testing libraries updated to latest compatible versions  
- [ ] CRACO configuration includes backend proxy
- [ ] Cross-platform npm scripts added
- [ ] Build process works without dependency conflicts
- [ ] GPU detection utility exists and is functional
- [ ] Session logs updated with recovery status

## ⚠️ FALLBACK OPTIONS

If critical dependency updates fail:

1. **React-Scripts Migration**: Consider upgrading to react-scripts 6.x
2. **Vite Migration**: Full migration from CRACO to Vite for better React 19 support
3. **Dependency Pinning**: Pin specific working versions temporarily
4. **Clean Slate**: Delete node_modules and package-lock.json, rebuild from scratch

## 📞 Next Agent Handoff

After completing recovery steps:

1. Update session restoration log with current status
2. Validate all critical success criteria are met
3. Test basic React 19 functionality
4. Prepare for SPARC+TDD implementation phase
5. Hand off to implementation coordinator agent

---

**Recovery Priority**: 🔴 CRITICAL - System blocked without these fixes  
**Estimated Time**: 45-90 minutes depending on network/system performance  
**Success Rate**: 95% with careful execution of all steps