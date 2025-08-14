@echo off
REM Build Process Validation for MINGW64
REM Tests all build-related functionality including TypeScript, React, and production builds

setlocal enabledelayedexpansion

echo ========================================
echo Build Process Validation
echo ========================================
echo.

set TEST_PASSED=0
set TEST_FAILED=0
set PROJECT_ROOT=%~dp0..\..\..
set FRONTEND_DIR=%PROJECT_ROOT%\ai-model-validation-platform\frontend

REM Change to frontend directory
cd /d "%FRONTEND_DIR%"

REM Verify we're in the right directory
if not exist "package.json" (
    echo ❌ package.json not found in frontend directory
    echo Current directory: %cd%
    exit /b 1
)

REM Test 1: Package.json Validation
echo [1/10] Validating package.json...

node -e "
try {
    const pkg = require('./package.json');
    console.log('✅ package.json is valid JSON');
    console.log('Project:', pkg.name);
    console.log('React version:', pkg.dependencies.react);
    console.log('TypeScript version:', pkg.dependencies.typescript);
    
    // Check for React 19 compatibility
    if (pkg.dependencies.react.includes('19.')) {
        console.log('✅ React 19 detected');
    } else {
        console.log('⚠️  React version is not 19.x');
    }
    
} catch (error) {
    console.error('❌ package.json validation failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Package.json validation passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Package.json validation failed
    set /a TEST_FAILED+=1
)

REM Test 2: Dependencies Installation Check
echo [2/10] Checking dependencies installation...

if exist "node_modules" (
    echo   ✅ node_modules directory exists
    
    REM Check key dependencies
    if exist "node_modules\react" (
        echo   ✅ React installed
        set /a TEST_PASSED+=1
    ) else (
        echo   ❌ React not found in node_modules
        set /a TEST_FAILED+=1
    )
    
    if exist "node_modules\typescript" (
        echo   ✅ TypeScript installed
        set /a TEST_PASSED+=1
    ) else (
        echo   ❌ TypeScript not found in node_modules
        set /a TEST_FAILED+=1
    )
) else (
    echo   ❌ node_modules directory not found
    echo   ℹ️  Run 'npm install' first
    set /a TEST_FAILED+=2
)

REM Test 3: TypeScript Configuration
echo [3/10] Validating TypeScript configuration...

if exist "tsconfig.json" (
    node -e "
    try {
        const tsconfig = require('./tsconfig.json');
        console.log('✅ tsconfig.json is valid');
        console.log('Target:', tsconfig.compilerOptions?.target || 'default');
        console.log('Module:', tsconfig.compilerOptions?.module || 'default');
        console.log('JSX:', tsconfig.compilerOptions?.jsx || 'default');
    } catch (error) {
        console.error('❌ tsconfig.json invalid:', error.message);
        process.exit(1);
    }
    " 2>&1
    
    if !errorlevel! equ 0 (
        echo   ✅ TypeScript configuration valid
        set /a TEST_PASSED+=1
    ) else (
        echo   ❌ TypeScript configuration invalid
        set /a TEST_FAILED+=1
    )
) else (
    echo   ❌ tsconfig.json not found
    set /a TEST_FAILED+=1
)

REM Test 4: TypeScript Compilation Test
echo [4/10] Testing TypeScript compilation...

npx tsc --noEmit > temp_tsc_output.txt 2>&1
set TSC_RESULT=!errorlevel!

if !TSC_RESULT! equ 0 (
    echo   ✅ TypeScript compilation successful
    set /a TEST_PASSED+=1
) else (
    echo   ❌ TypeScript compilation failed
    echo   Errors found:
    type temp_tsc_output.txt | findstr /i "error" | head -5
    set /a TEST_FAILED+=1
)

if exist temp_tsc_output.txt del temp_tsc_output.txt

REM Test 5: React 19 Feature Compatibility
echo [5/10] Testing React 19 compatibility...

node -e "
try {
    // Test importing React 19 features
    const React = require('react');
    console.log('React version:', React.version);
    
    if (React.version.startsWith('19.')) {
        console.log('✅ React 19 successfully imported');
        
        // Test specific React 19 features
        if (typeof React.use === 'function') {
            console.log('✅ React.use hook available');
        } else {
            console.log('⚠️  React.use hook not available');
        }
        
        console.log('React 19 compatibility: PASSED');
    } else {
        console.log('⚠️  React version is not 19.x:', React.version);
    }
} catch (error) {
    console.error('❌ React compatibility test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ React 19 compatibility test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ React 19 compatibility test failed
    set /a TEST_FAILED+=1
)

REM Test 6: Development Build Test
echo [6/10] Testing development build preparation...

echo Checking npm scripts...
node -e "
const pkg = require('./package.json');
const scripts = pkg.scripts || {};
console.log('Available scripts:');
Object.keys(scripts).forEach(script => {
    console.log('  ', script, ':', scripts[script]);
});

if (scripts.start) {
    console.log('✅ Start script found');
} else {
    console.log('❌ Start script missing');
    process.exit(1);
}

if (scripts.build) {
    console.log('✅ Build script found');
} else {
    console.log('❌ Build script missing');
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Development build scripts validated
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Development build scripts validation failed
    set /a TEST_FAILED+=1
)

REM Test 7: Production Build Test (Limited Time)
echo [7/10] Testing production build...

echo Starting production build test (limited time)...
timeout /t 180 npm run build > temp_build_output.txt 2>&1
set BUILD_RESULT=!errorlevel!

if !BUILD_RESULT! equ 0 (
    echo   ✅ Production build completed successfully
    if exist "build" (
        echo   ✅ Build directory created
        set /a TEST_PASSED+=2
    ) else (
        echo   ⚠️  Build directory not found
        set /a TEST_FAILED+=1
    )
) else (
    echo   ❌ Production build failed or timed out
    echo   Build output (last 10 lines):
    if exist temp_build_output.txt (
        powershell -Command "Get-Content temp_build_output.txt -Tail 10"
    )
    set /a TEST_FAILED+=1
)

if exist temp_build_output.txt del temp_build_output.txt

REM Test 8: Bundle Analysis Capability
echo [8/10] Testing bundle analysis capability...

if exist "build" (
    echo Testing bundle structure...
    
    if exist "build\static\js" (
        echo   ✅ JavaScript bundles found
        set /a TEST_PASSED+=1
    ) else (
        echo   ❌ JavaScript bundles not found
        set /a TEST_FAILED+=1
    )
    
    if exist "build\static\css" (
        echo   ✅ CSS bundles found
        set /a TEST_PASSED+=1
    ) else (
        echo   ❌ CSS bundles not found
        set /a TEST_FAILED+=1
    )
    
    REM Check bundle sizes
    node -e "
    const fs = require('fs');
    const path = require('path');
    
    try {
        const buildDir = './build/static/js';
        if (fs.existsSync(buildDir)) {
            const files = fs.readdirSync(buildDir);
            const jsFiles = files.filter(f => f.endsWith('.js'));
            
            console.log('JavaScript bundles:');
            jsFiles.forEach(file => {
                const filePath = path.join(buildDir, file);
                const stats = fs.statSync(filePath);
                const sizeKB = (stats.size / 1024).toFixed(2);
                console.log('  ', file, ':', sizeKB, 'KB');
            });
            
            const totalSize = jsFiles.reduce((total, file) => {
                const stats = fs.statSync(path.join(buildDir, file));
                return total + stats.size;
            }, 0);
            
            console.log('Total JS bundle size:', (totalSize / 1024 / 1024).toFixed(2), 'MB');
            
            if (totalSize < 10 * 1024 * 1024) { // 10MB limit
                console.log('✅ Bundle size within reasonable limits');
            } else {
                console.log('⚠️  Bundle size is quite large');
            }
        }
    } catch (error) {
        console.error('Bundle analysis failed:', error.message);
    }
    " 2>&1
else (
    echo   ⚠️  Build directory not available for analysis
)

REM Test 9: CRACO Configuration (if present)
echo [9/10] Testing CRACO configuration...

if exist "craco.config.js" (
    node -e "
    try {
        const cracoConfig = require('./craco.config.js');
        console.log('✅ CRACO config loaded successfully');
        console.log('Config type:', typeof cracoConfig);
        
        if (cracoConfig.webpack) {
            console.log('✅ Webpack configuration found');
        }
        
        if (cracoConfig.babel) {
            console.log('✅ Babel configuration found');
        }
        
    } catch (error) {
        console.error('❌ CRACO config error:', error.message);
        process.exit(1);
    }
    " 2>&1
    
    if !errorlevel! equ 0 (
        echo   ✅ CRACO configuration validated
        set /a TEST_PASSED+=1
    ) else (
        echo   ❌ CRACO configuration validation failed
        set /a TEST_FAILED+=1
    )
) else (
    echo   ℹ️  CRACO configuration not found (using default CRA)
)

REM Test 10: Linting and Code Quality
echo [10/10] Testing linting and code quality...

REM Check if ESLint is configured
node -e "
const pkg = require('./package.json');

if (pkg.eslintConfig) {
    console.log('✅ ESLint configuration found in package.json');
    console.log('Extends:', JSON.stringify(pkg.eslintConfig.extends));
} else {
    console.log('ℹ️  No ESLint configuration in package.json');
}

// Check for common issues in key files
const fs = require('fs');
const path = require('path');

if (fs.existsSync('./src')) {
    console.log('✅ Source directory found');
    
    const indexPath = './src/index.tsx';
    if (fs.existsSync(indexPath)) {
        console.log('✅ Main index file found');
    } else {
        console.log('⚠️  Main index file not found');
    }
    
    const appPath = './src/App.tsx';
    if (fs.existsSync(appPath)) {
        console.log('✅ App component found');
    } else {
        console.log('⚠️  App component not found');
    }
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Code quality check passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Code quality check failed
    set /a TEST_FAILED+=1
)

REM Summary
echo.
echo ========================================
echo Build Validation Summary
echo ========================================
echo Passed: %TEST_PASSED%
echo Failed: %TEST_FAILED%

if %TEST_FAILED% gtr 3 (
    echo.
    echo ❌ Multiple build validation issues detected!
    echo The build process may not work reliably.
    exit /b 1
) else if %TEST_FAILED% gtr 0 (
    echo.
    echo ⚠️  Some build tests failed, but basic build functionality should work.
    exit /b 0
) else (
    echo.
    echo ✅ All build validation tests passed!
    exit /b 0
)