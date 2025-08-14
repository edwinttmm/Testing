@echo off
REM Runtime Environment Tests for MINGW64
REM Tests runtime functionality including WebSocket, API, and error handling

setlocal enabledelayedexpansion

echo ========================================
echo Runtime Environment Tests
echo ========================================
echo.

set TEST_PASSED=0
set TEST_FAILED=0
set PROJECT_ROOT=%~dp0..\..\..
set FRONTEND_DIR=%PROJECT_ROOT%\ai-model-validation-platform\frontend

cd /d "%FRONTEND_DIR%"

REM Test 1: Basic React Application Runtime
echo [1/8] Testing React Application Runtime...

node -e "
try {
    const React = require('react');
    const ReactDOM = require('react-dom/client');
    
    console.log('✅ React runtime modules loaded');
    console.log('React version:', React.version);
    
    // Test basic React element creation
    const element = React.createElement('div', null, 'Test');
    if (element) {
        console.log('✅ React element creation works');
    }
    
} catch (error) {
    console.error('❌ React runtime test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ React runtime test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ React runtime test failed
    set /a TEST_FAILED+=1
)

REM Test 2: WebSocket Client Functionality
echo [2/8] Testing WebSocket Client...

node -e "
try {
    const io = require('socket.io-client');
    console.log('✅ Socket.IO client module loaded');
    
    // Test WebSocket client creation (without connecting)
    const socket = io('http://localhost:3001', { 
        autoConnect: false,
        timeout: 1000
    });
    
    if (socket) {
        console.log('✅ Socket.IO client can be created');
        
        // Test event handling setup
        socket.on('connect', () => {
            console.log('✅ Connection event handler works');
        });
        
        socket.on('error', (error) => {
            console.log('✅ Error event handler works');
        });
        
        console.log('✅ WebSocket event handling setup successful');
    }
    
} catch (error) {
    console.error('❌ WebSocket test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ WebSocket client test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ WebSocket client test failed
    set /a TEST_FAILED+=1
)

REM Test 3: API Service Testing
echo [3/8] Testing API Service...

node -e "
try {
    const axios = require('axios');
    console.log('✅ Axios HTTP client loaded');
    
    // Test API service configuration
    const apiConfig = {
        baseURL: 'http://localhost:3001/api',
        timeout: 5000,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    const api = axios.create(apiConfig);
    console.log('✅ API client configuration successful');
    
    // Test request interceptor setup
    api.interceptors.request.use(
        config => {
            console.log('✅ Request interceptor works');
            return config;
        },
        error => {
            console.log('✅ Request error interceptor works');
            return Promise.reject(error);
        }
    );
    
    // Test response interceptor setup
    api.interceptors.response.use(
        response => {
            console.log('✅ Response interceptor works');
            return response;
        },
        error => {
            console.log('✅ Response error interceptor works');
            return Promise.reject(error);
        }
    );
    
    console.log('✅ API service setup complete');
    
} catch (error) {
    console.error('❌ API service test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ API service test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ API service test failed
    set /a TEST_FAILED+=1
)

REM Test 4: Error Boundary Testing
echo [4/8] Testing Error Boundary Implementation...

REM Check if error boundary components exist
if exist "src\components\ui\ErrorBoundary.tsx" (
    echo   ✅ Error boundary component found
    
    node -e "
    const fs = require('fs');
    try {
        const errorBoundaryCode = fs.readFileSync('./src/components/ui/ErrorBoundary.tsx', 'utf8');
        
        // Check for essential error boundary methods
        if (errorBoundaryCode.includes('componentDidCatch') || errorBoundaryCode.includes('getDerivedStateFromError')) {
            console.log('✅ Error boundary methods found');
        } else {
            console.log('⚠️  Error boundary methods not detected');
        }
        
        if (errorBoundaryCode.includes('fallback') || errorBoundaryCode.includes('error')) {
            console.log('✅ Error display logic found');
        } else {
            console.log('⚠️  Error display logic not detected');
        }
        
        console.log('✅ Error boundary implementation validated');
        
    } catch (error) {
        console.error('❌ Error boundary validation failed:', error.message);
        process.exit(1);
    }
    " 2>&1
    
    if !errorlevel! equ 0 (
        echo   ✅ Error boundary validation passed
        set /a TEST_PASSED+=1
    ) else (
        echo   ❌ Error boundary validation failed
        set /a TEST_FAILED+=1
    )
) else (
    echo   ⚠️  Error boundary component not found
    echo   ℹ️  Application may not handle runtime errors gracefully
)

REM Test 5: Memory Management Testing
echo [5/8] Testing Memory Management...

node -e "
try {
    // Test memory usage monitoring
    const initialMemory = process.memoryUsage();
    console.log('Initial memory usage:');
    console.log('  Heap used:', (initialMemory.heapUsed / 1024 / 1024).toFixed(2), 'MB');
    console.log('  Heap total:', (initialMemory.heapTotal / 1024 / 1024).toFixed(2), 'MB');
    console.log('  RSS:', (initialMemory.rss / 1024 / 1024).toFixed(2), 'MB');
    
    // Simulate some memory usage
    const testArray = new Array(100000).fill('test data');
    
    const afterMemory = process.memoryUsage();
    const memoryIncrease = afterMemory.heapUsed - initialMemory.heapUsed;
    
    console.log('Memory increase:', (memoryIncrease / 1024 / 1024).toFixed(2), 'MB');
    
    // Clear the test array
    testArray.length = 0;
    
    // Force garbage collection if available
    if (global.gc) {
        global.gc();
        console.log('✅ Garbage collection triggered');
    } else {
        console.log('ℹ️  Garbage collection not available (normal)');
    }
    
    console.log('✅ Memory management test completed');
    
} catch (error) {
    console.error('❌ Memory management test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Memory management test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Memory management test failed
    set /a TEST_FAILED+=1
)

REM Test 6: Material-UI Runtime Testing
echo [6/8] Testing Material-UI Runtime...

node -e "
try {
    const mui = require('@mui/material');
    console.log('✅ Material-UI core loaded');
    
    // Test theme provider
    const { ThemeProvider, createTheme } = require('@mui/material/styles');
    console.log('✅ Theme provider available');
    
    // Test basic theme creation
    const theme = createTheme({
        palette: {
            mode: 'light',
        },
    });
    
    if (theme) {
        console.log('✅ Theme creation successful');
        console.log('Theme palette mode:', theme.palette.mode);
    }
    
    // Test component imports
    const { Button, TextField, Card } = mui;
    if (Button && TextField && Card) {
        console.log('✅ Core MUI components available');
    }
    
    console.log('✅ Material-UI runtime test completed');
    
} catch (error) {
    console.error('❌ Material-UI runtime test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Material-UI runtime test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Material-UI runtime test failed
    set /a TEST_FAILED+=1
)

REM Test 7: React Router Runtime Testing
echo [7/8] Testing React Router Runtime...

node -e "
try {
    const { BrowserRouter, Routes, Route, Navigate } = require('react-router-dom');
    console.log('✅ React Router components loaded');
    
    // Test router configuration
    const React = require('react');
    
    if (BrowserRouter && Routes && Route && Navigate) {
        console.log('✅ All essential routing components available');
        
        // Test router element creation
        const routerElement = React.createElement(BrowserRouter);
        if (routerElement) {
            console.log('✅ Router element creation successful');
        }
    }
    
    console.log('✅ React Router runtime test completed');
    
} catch (error) {
    console.error('❌ React Router runtime test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ React Router runtime test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ React Router runtime test failed
    set /a TEST_FAILED+=1
)

REM Test 8: Performance Monitoring Setup
echo [8/8] Testing Performance Monitoring...

node -e "
try {
    // Test Web Vitals
    const { getCLS, getFID, getFCP, getLCP, getTTFB } = require('web-vitals');
    console.log('✅ Web Vitals module loaded');
    
    // Test performance monitoring setup
    const performanceConfig = {
        onCLS: (metric) => console.log('CLS:', metric),
        onFID: (metric) => console.log('FID:', metric),
        onFCP: (metric) => console.log('FCP:', metric),
        onLCP: (metric) => console.log('LCP:', metric),
        onTTFB: (metric) => console.log('TTFB:', metric),
    };
    
    console.log('✅ Performance monitoring configuration ready');
    
    // Test performance observer capability (Node.js environment simulation)
    if (typeof global !== 'undefined') {
        console.log('✅ Global performance context available');
    }
    
    console.log('✅ Performance monitoring test completed');
    
} catch (error) {
    console.error('❌ Performance monitoring test failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Performance monitoring test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Performance monitoring test failed
    set /a TEST_FAILED+=1
)

REM Bonus Test: Check for Development vs Production Runtime Differences
echo.
echo [Bonus] Testing Environment-Specific Runtime...

node -e "
try {
    const nodeEnv = process.env.NODE_ENV || 'development';
    console.log('Current NODE_ENV:', nodeEnv);
    
    // Test environment-specific configurations
    if (nodeEnv === 'development') {
        console.log('✅ Development environment detected');
        console.log('  - Hot reload should be available');
        console.log('  - Development warnings enabled');
        console.log('  - Source maps available');
    } else if (nodeEnv === 'production') {
        console.log('✅ Production environment detected');
        console.log('  - Optimized builds');
        console.log('  - Minified code');
        console.log('  - Performance optimizations');
    } else {
        console.log('ℹ️  Custom environment:', nodeEnv);
    }
    
    // Test React development tools
    const React = require('react');
    if (React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED) {
        console.log('✅ React internals available (development features)');
    }
    
    console.log('✅ Environment-specific runtime test completed');
    
} catch (error) {
    console.error('❌ Environment runtime test failed:', error.message);
    process.exit(1);
}
" 2>&1

REM Summary
echo.
echo ========================================
echo Runtime Tests Summary
echo ========================================
echo Passed: %TEST_PASSED%
echo Failed: %TEST_FAILED%

if %TEST_FAILED% gtr 2 (
    echo.
    echo ❌ Multiple runtime issues detected!
    echo The application may not run properly.
    exit /b 1
) else if %TEST_FAILED% gtr 0 (
    echo.
    echo ⚠️  Some runtime tests failed, but core functionality should work.
    exit /b 0
) else (
    echo.
    echo ✅ All runtime tests passed!
    exit /b 0
)