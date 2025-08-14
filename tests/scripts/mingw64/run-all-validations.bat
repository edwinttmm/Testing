@echo off
REM MINGW64 Comprehensive Validation Script
REM Runs all validation tests for Windows MINGW64 environment

setlocal enabledelayedexpansion

echo ========================================
echo MINGW64 Dependency Validation Suite
echo ========================================
echo.

REM Set project root
set PROJECT_ROOT=%~dp0..\..\..
cd /d "%PROJECT_ROOT%"

REM Create results directory
if not exist "tests\mingw64-validation\results" mkdir "tests\mingw64-validation\results"

REM Timestamp for this run
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%

echo Starting validation at %date% %time%
echo Results will be saved with timestamp: %TIMESTAMP%
echo.

REM 1. Environment Validation
echo [1/8] Running Environment Validation...
call tests\scripts\mingw64\validate-environment.bat > "tests\mingw64-validation\results\environment_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ Environment validation failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ Environment validation passed
)

REM 2. Dependency Analysis
echo [2/8] Running Dependency Analysis...
node tests\mingw64-validation\mingw64-dependency-validator.js > "tests\mingw64-validation\results\dependencies_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ Dependency validation failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ Dependency validation passed
)

REM 3. Cross-Platform Tests
echo [3/8] Running Cross-Platform Tests...
call tests\scripts\mingw64\cross-platform-tests.bat > "tests\mingw64-validation\results\cross-platform_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ Cross-platform tests failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ Cross-platform tests passed
)

REM 4. Build Process Validation
echo [4/8] Running Build Process Validation...
call tests\scripts\mingw64\build-validation.bat > "tests\mingw64-validation\results\build_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ Build validation failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ Build validation passed
)

REM 5. Runtime Environment Tests
echo [5/8] Running Runtime Environment Tests...
call tests\scripts\mingw64\runtime-tests.bat > "tests\mingw64-validation\results\runtime_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ Runtime tests failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ Runtime tests passed
)

REM 6. GPU/CPU Fallback Tests
echo [6/8] Running GPU/CPU Fallback Tests...
call tests\scripts\mingw64\gpu-fallback-tests.bat > "tests\mingw64-validation\results\gpu-fallback_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ GPU/CPU fallback tests failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ GPU/CPU fallback tests passed
)

REM 7. Performance Tests
echo [7/8] Running Performance Tests...
call tests\scripts\mingw64\performance-tests.bat > "tests\mingw64-validation\results\performance_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ Performance tests failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ Performance tests passed
)

REM 8. CI/CD Compatibility Tests
echo [8/8] Running CI/CD Compatibility Tests...
call tests\scripts\mingw64\cicd-tests.bat > "tests\mingw64-validation\results\cicd_%TIMESTAMP%.log" 2>&1
if !errorlevel! neq 0 (
    echo   ❌ CI/CD tests failed
    set VALIDATION_FAILED=1
) else (
    echo   ✅ CI/CD tests passed
)

echo.
echo ========================================
echo Validation Summary
echo ========================================

REM Generate combined report
node tests\scripts\mingw64\generate-report.js "%TIMESTAMP%" > "tests\mingw64-validation\results\summary_%TIMESTAMP%.txt" 2>&1

if defined VALIDATION_FAILED (
    echo ❌ Some validations failed. Check individual logs for details.
    echo 📄 Results saved in: tests\mingw64-validation\results\
    exit /b 1
) else (
    echo ✅ All validations passed successfully!
    echo 📄 Results saved in: tests\mingw64-validation\results\
    exit /b 0
)