@echo off
REM MINGW64 Environment Validation Script
REM Validates the Windows MINGW64 development environment

setlocal enabledelayedexpansion

echo ========================================
echo MINGW64 Environment Validation
echo ========================================
echo.

set VALIDATION_PASSED=0
set VALIDATION_FAILED=0

REM Check MSYS2/MINGW64 Installation
echo [1/12] Checking MSYS2/MINGW64 Installation...
if exist "C:\msys64" (
    echo   ✅ MSYS2 found at C:\msys64
    set /a VALIDATION_PASSED+=1
) else (
    echo   ❌ MSYS2 not found at expected location
    set /a VALIDATION_FAILED+=1
)

if exist "C:\msys64\mingw64" (
    echo   ✅ MINGW64 found
    set /a VALIDATION_PASSED+=1
) else (
    echo   ❌ MINGW64 not found
    set /a VALIDATION_FAILED+=1
)

REM Check Environment Variables
echo [2/12] Checking Environment Variables...
if defined MSYSTEM (
    echo   ✅ MSYSTEM is set to: %MSYSTEM%
    set /a VALIDATION_PASSED+=1
) else (
    echo   ⚠️  MSYSTEM not set
    set /a VALIDATION_FAILED+=1
)

if defined MINGW_PREFIX (
    echo   ✅ MINGW_PREFIX is set to: %MINGW_PREFIX%
    set /a VALIDATION_PASSED+=1
) else (
    echo   ⚠️  MINGW_PREFIX not set
)

REM Check Node.js
echo [3/12] Checking Node.js Installation...
node --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
    echo   ✅ Node.js version: !NODE_VERSION!
    set /a VALIDATION_PASSED+=1
) else (
    echo   ❌ Node.js not found or not accessible
    set /a VALIDATION_FAILED+=1
)

REM Check NPM
echo [4/12] Checking NPM Installation...
npm --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i
    echo   ✅ NPM version: !NPM_VERSION!
    set /a VALIDATION_PASSED+=1
) else (
    echo   ❌ NPM not found or not accessible
    set /a VALIDATION_FAILED+=1
)

REM Check Git
echo [5/12] Checking Git Installation...
git --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%i in ('git --version') do set GIT_VERSION=%%i
    echo   ✅ Git version: !GIT_VERSION!
    set /a VALIDATION_PASSED+=1
) else (
    echo   ❌ Git not found or not accessible
    set /a VALIDATION_FAILED+=1
)

REM Check Python
echo [6/12] Checking Python Installation...
python --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
    echo   ✅ Python version: !PYTHON_VERSION!
    set /a VALIDATION_PASSED+=1
) else (
    echo   ⚠️  Python not found (may be optional)
)

REM Check PATH Configuration
echo [7/12] Checking PATH Configuration...
echo %PATH% | findstr /i "mingw64" >nul
if !errorlevel! equ 0 (
    echo   ✅ MINGW64 found in PATH
    set /a VALIDATION_PASSED+=1
) else (
    echo   ⚠️  MINGW64 not found in PATH
)

echo %PATH% | findstr /i "nodejs\|node" >nul
if !errorlevel! equ 0 (
    echo   ✅ Node.js found in PATH
    set /a VALIDATION_PASSED+=1
) else (
    echo   ⚠️  Node.js path not explicitly found in PATH
)

REM Check Windows Version
echo [8/12] Checking Windows Version...
for /f "tokens=4-5 delims=. " %%i in ('ver') do set VERSION=%%i.%%j
echo   ℹ️  Windows version: %VERSION%

REM Check Architecture
echo [9/12] Checking System Architecture...
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo   ✅ 64-bit architecture detected
    set /a VALIDATION_PASSED+=1
) else (
    echo   ⚠️  Non-64-bit architecture: %PROCESSOR_ARCHITECTURE%
)

REM Check PowerShell
echo [10/12] Checking PowerShell...
powershell -Command "Get-Host | Select-Object Version" >nul 2>&1
if !errorlevel! equ 0 (
    echo   ✅ PowerShell available
    set /a VALIDATION_PASSED+=1
) else (
    echo   ❌ PowerShell not accessible
    set /a VALIDATION_FAILED+=1
)

REM Check CMD Encoding
echo [11/12] Checking Command Prompt Encoding...
chcp | findstr "65001" >nul
if !errorlevel! equ 0 (
    echo   ✅ UTF-8 encoding (65001) active
    set /a VALIDATION_PASSED+=1
) else (
    echo   ⚠️  Non-UTF-8 encoding detected, may cause issues with international characters
)

REM Check File System
echo [12/12] Checking File System Support...
echo test > temp_test_file.txt 2>nul
if exist temp_test_file.txt (
    echo   ✅ File system write permissions working
    del temp_test_file.txt >nul 2>&1
    set /a VALIDATION_PASSED+=1
) else (
    echo   ❌ File system write test failed
    set /a VALIDATION_FAILED+=1
)

REM Summary
echo.
echo ========================================
echo Environment Validation Summary
echo ========================================
echo Passed: %VALIDATION_PASSED%
echo Failed/Warnings: %VALIDATION_FAILED%

if %VALIDATION_FAILED% gtr 3 (
    echo.
    echo ❌ Critical environment issues detected!
    echo Please fix the failed checks before proceeding.
    exit /b 1
) else if %VALIDATION_FAILED% gtr 0 (
    echo.
    echo ⚠️  Some warnings detected, but environment should be functional.
    exit /b 0
) else (
    echo.
    echo ✅ Environment validation completed successfully!
    exit /b 0
)