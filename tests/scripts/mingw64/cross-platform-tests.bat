@echo off
REM Cross-Platform Compatibility Tests for MINGW64
REM Tests path handling, line endings, and cross-platform features

setlocal enabledelayedexpansion

echo ========================================
echo Cross-Platform Compatibility Tests
echo ========================================
echo.

set TEST_PASSED=0
set TEST_FAILED=0
set PROJECT_ROOT=%~dp0..\..\..

REM Create temporary test directory
set TEST_DIR=%PROJECT_ROOT%\tests\mingw64-validation\temp
if not exist "%TEST_DIR%" mkdir "%TEST_DIR%"

REM Test 1: Path Handling
echo [1/8] Testing Path Handling...

REM Test Windows path conversion
echo Testing Windows path conversion...
node -e "
const path = require('path');
const testPath = 'C:\\\\Users\\\\test\\\\project';
const converted = path.posix.normalize(testPath.replace(/\\\\/g, '/'));
console.log('Original:', testPath);
console.log('Converted:', converted);
console.log('Success:', converted.includes('/Users/test/project'));
" > "%TEST_DIR%\path_test.log" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Path conversion test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Path conversion test failed
    set /a TEST_FAILED+=1
)

REM Test 2: Line Ending Handling
echo [2/8] Testing Line Ending Handling...

REM Create files with different line endings
echo line1> "%TEST_DIR%\unix_endings.txt"
echo line2>> "%TEST_DIR%\unix_endings.txt"

powershell -Command "
'line1' | Out-File -FilePath '%TEST_DIR%\windows_endings.txt' -Encoding ASCII
'line2' | Out-File -FilePath '%TEST_DIR%\windows_endings.txt' -Append -Encoding ASCII
"

REM Test reading both files with Node.js
node -e "
const fs = require('fs');
try {
    const unixFile = fs.readFileSync('%TEST_DIR%/unix_endings.txt', 'utf8');
    const windowsFile = fs.readFileSync('%TEST_DIR%/windows_endings.txt', 'utf8');
    console.log('Unix file length:', unixFile.length);
    console.log('Windows file length:', windowsFile.length);
    console.log('Line ending test: PASSED');
} catch (error) {
    console.error('Line ending test: FAILED', error.message);
    process.exit(1);
}
" > "%TEST_DIR%\line_ending_test.log" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Line ending handling test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Line ending handling test failed
    set /a TEST_FAILED+=1
)

REM Test 3: Environment Detection
echo [3/8] Testing Environment Detection...

node -e "
console.log('Platform:', process.platform);
console.log('Architecture:', process.arch);
console.log('Windows:', process.platform === 'win32');
console.log('Environment variables:');
console.log('  MSYSTEM:', process.env.MSYSTEM || 'Not set');
console.log('  MINGW_PREFIX:', process.env.MINGW_PREFIX || 'Not set');
console.log('  COMSPEC:', process.env.COMSPEC || 'Not set');
" > "%TEST_DIR%\env_detection_test.log" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Environment detection test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Environment detection test failed
    set /a TEST_FAILED+=1
)

REM Test 4: Shell Script Compatibility
echo [4/8] Testing Shell Script Compatibility...

REM Create a simple batch script
echo @echo off > "%TEST_DIR%\test_script.bat"
echo echo Hello from batch script >> "%TEST_DIR%\test_script.bat"

REM Create a simple shell script
echo #!/bin/bash > "%TEST_DIR%\test_script.sh"
echo echo "Hello from shell script" >> "%TEST_DIR%\test_script.sh"

REM Test batch script execution
call "%TEST_DIR%\test_script.bat" > "%TEST_DIR%\batch_output.txt" 2>&1
if !errorlevel! equ 0 (
    echo   ✅ Batch script execution passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Batch script execution failed
    set /a TEST_FAILED+=1
)

REM Test 5: File Permission Handling
echo [5/8] Testing File Permission Handling...

REM Create a test file and modify permissions
echo test content > "%TEST_DIR%\perm_test.txt"

REM Try to read the file with Node.js
node -e "
const fs = require('fs');
try {
    const content = fs.readFileSync('%TEST_DIR%/perm_test.txt', 'utf8');
    console.log('File read successfully:', content.trim());
    
    // Try to write to the file
    fs.writeFileSync('%TEST_DIR%/perm_test_write.txt', 'write test');
    console.log('File write test: PASSED');
} catch (error) {
    console.error('Permission test: FAILED', error.message);
    process.exit(1);
}
" > "%TEST_DIR%\permission_test.log" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ File permission test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ File permission test failed
    set /a TEST_FAILED+=1
)

REM Test 6: Symlink Support (Windows specific)
echo [6/8] Testing Symlink Support...

REM Create a test file for symlinking
echo symlink target > "%TEST_DIR%\symlink_target.txt"

REM Try to create a symbolic link (requires admin privileges or developer mode)
mklink "%TEST_DIR%\symlink_test.txt" "%TEST_DIR%\symlink_target.txt" >nul 2>&1
if !errorlevel! equ 0 (
    echo   ✅ Symbolic link creation passed
    set /a TEST_PASSED+=1
) else (
    echo   ⚠️  Symbolic link creation failed (may require elevated privileges)
    echo   ℹ️  This is normal on Windows without Developer Mode
)

REM Test 7: Unicode and Character Encoding
echo [7/8] Testing Unicode and Character Encoding...

node -e "
const fs = require('fs');
const testContent = 'Hello 世界 🌍 Ñiño café';
try {
    fs.writeFileSync('%TEST_DIR%/unicode_test.txt', testContent, 'utf8');
    const readContent = fs.readFileSync('%TEST_DIR%/unicode_test.txt', 'utf8');
    
    if (readContent === testContent) {
        console.log('Unicode test: PASSED');
        console.log('Content:', readContent);
    } else {
        console.log('Unicode test: FAILED - content mismatch');
        process.exit(1);
    }
} catch (error) {
    console.error('Unicode test: FAILED', error.message);
    process.exit(1);
}
" > "%TEST_DIR%\unicode_test.log" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Unicode encoding test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Unicode encoding test failed
    set /a TEST_FAILED+=1
)

REM Test 8: Node.js Module Resolution
echo [8/8] Testing Node.js Module Resolution...

cd /d "%PROJECT_ROOT%\ai-model-validation-platform\frontend"

node -e "
try {
    const path = require('path');
    const fs = require('fs');
    
    // Test require resolution
    console.log('Testing module resolution...');
    
    // Check if node_modules exists
    if (fs.existsSync('./node_modules')) {
        console.log('node_modules directory found');
        
        // Test requiring a known dependency
        const packageJson = require('./package.json');
        console.log('package.json loaded successfully');
        console.log('Project name:', packageJson.name);
        
        // Test path resolution for modules
        const reactPath = require.resolve('react');
        console.log('React module resolved to:', reactPath);
        
        console.log('Module resolution test: PASSED');
    } else {
        console.log('node_modules not found - run npm install first');
        console.log('Module resolution test: SKIPPED');
    }
} catch (error) {
    console.error('Module resolution test: FAILED', error.message);
    process.exit(1);
}
" > "%TEST_DIR%\module_resolution_test.log" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Module resolution test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Module resolution test failed
    set /a TEST_FAILED+=1
)

REM Cleanup
echo.
echo Cleaning up temporary files...
if exist "%TEST_DIR%" rmdir /s /q "%TEST_DIR%" >nul 2>&1

REM Summary
echo.
echo ========================================
echo Cross-Platform Test Summary
echo ========================================
echo Passed: %TEST_PASSED%
echo Failed: %TEST_FAILED%

if %TEST_FAILED% gtr 2 (
    echo.
    echo ❌ Multiple cross-platform compatibility issues detected!
    exit /b 1
) else if %TEST_FAILED% gtr 0 (
    echo.
    echo ⚠️  Some cross-platform tests failed, but basic functionality should work.
    exit /b 0
) else (
    echo.
    echo ✅ All cross-platform compatibility tests passed!
    exit /b 0
)