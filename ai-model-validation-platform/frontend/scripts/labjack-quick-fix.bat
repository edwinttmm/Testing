@echo off
REM LabJack Quick Fix Batch Script
REM ==============================
REM Windows batch script for common LabJack connectivity issues
REM Run as Administrator for best results

title LabJack Quick Fix Tool

echo.
echo ========================================
echo  LabJack Quick Fix Tool
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo WARNING: Not running as Administrator
    echo Some fixes may not work properly
    echo.
    pause
)

echo Checking LabJack connectivity...
echo.

:MENU
echo ========================================
echo  Quick Fix Options
echo ========================================
echo  1. Restart LabJack USB Service
echo  2. Scan for Hardware Changes
echo  3. Reset USB Devices
echo  4. Create Firewall Rules
echo  5. Test Device Connection
echo  6. Open Device Manager
echo  7. Open Kipling (if installed)
echo  8. Check System Status
echo  9. Run Full Diagnostic
echo  0. Exit
echo ========================================
echo.

set /p choice="Select option (0-9): "

if "%choice%"=="1" goto RESTART_SERVICE
if "%choice%"=="2" goto SCAN_HARDWARE
if "%choice%"=="3" goto RESET_USB
if "%choice%"=="4" goto CREATE_FIREWALL
if "%choice%"=="5" goto TEST_CONNECTION
if "%choice%"=="6" goto OPEN_DEVMGMT
if "%choice%"=="7" goto OPEN_KIPLING
if "%choice%"=="8" goto CHECK_STATUS
if "%choice%"=="9" goto FULL_DIAGNOSTIC
if "%choice%"=="0" goto EXIT

echo Invalid option, please try again.
echo.
goto MENU

:RESTART_SERVICE
echo.
echo Restarting LabJack USB Service...
echo ========================================
sc stop LabJackUSB 2>nul
timeout /t 2 >nul
sc start LabJackUSB 2>nul
if %errorLevel%==0 (
    echo SUCCESS: LabJack USB Service restarted
) else (
    echo ERROR: Could not restart service - may not be installed
)
echo.
pause
goto MENU

:SCAN_HARDWARE
echo.
echo Scanning for Hardware Changes...
echo ========================================
pnputil /scan-devices
echo Hardware scan completed
echo.
pause
goto MENU

:RESET_USB
echo.
echo Resetting USB Devices...
echo ========================================
echo This will disable and re-enable USB devices
echo.
set /p confirm="Continue? (y/n): "
if /i "%confirm%" neq "y" goto MENU

powershell -Command "Get-WmiObject -Class Win32_USBHub | ForEach-Object { $_.Disable(); Start-Sleep -Seconds 1; $_.Enable() }"
echo USB devices reset completed
echo.
pause
goto MENU

:CREATE_FIREWALL
echo.
echo Creating Firewall Rules for LabJack...
echo ========================================
netsh advfirewall firewall add rule name="LabJack Modbus TCP" dir=in action=allow protocol=TCP localport=502
netsh advfirewall firewall add rule name="LabJack UDP Discovery" dir=in action=allow protocol=UDP localport=5350
netsh advfirewall firewall add rule name="LabJack Kipling" dir=in action=allow program="C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe"

if %errorLevel%==0 (
    echo SUCCESS: Firewall rules created
) else (
    echo ERROR: Could not create firewall rules
)
echo.
pause
goto MENU

:TEST_CONNECTION
echo.
echo Testing Device Connection...
echo ========================================

REM Check USB devices
echo Checking USB devices...
powershell -Command "Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like '*LabJack*' } | Select-Object Name, Status | Format-Table -AutoSize"

echo.
echo Checking network connectivity...
powershell -Command "Test-NetConnection -ComputerName '192.168.1.207' -Port 502 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded"

echo.
echo Checking LabJack services...
powershell -Command "Get-Service | Where-Object { $_.Name -like '*LabJack*' } | Select-Object Name, Status, StartType | Format-Table -AutoSize"

echo.
pause
goto MENU

:OPEN_DEVMGMT
echo.
echo Opening Device Manager...
devmgmt.msc
goto MENU

:OPEN_KIPLING
echo.
echo Opening Kipling (if installed)...
if exist "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe" (
    start "" "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe"
    echo Kipling started
) else (
    echo Kipling not found. Please install LabJack software.
)
echo.
pause
goto MENU

:CHECK_STATUS
echo.
echo Checking System Status...
echo ========================================

echo System Information:
echo -------------------
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"Total Physical Memory"

echo.
echo USB Controllers:
echo ----------------
powershell -Command "Get-WmiObject -Class Win32_USBController | Select-Object Name, Status | Format-Table -AutoSize"

echo.
echo LabJack Software Check:
echo -----------------------
if exist "C:\Program Files (x86)\LabJack\Applications\LJM\LJM_library.dll" (
    echo [OK] LJM Library found
) else (
    echo [MISSING] LJM Library not found
)

if exist "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe" (
    echo [OK] Kipling found
) else (
    echo [MISSING] Kipling not found
)

echo.
echo API Connectivity Test:
echo ----------------------
powershell -Command "try { $response = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 5; Write-Host '[OK] Backend API accessible' } catch { Write-Host '[ERROR] Backend API not accessible' }"

echo.
pause
goto MENU

:FULL_DIAGNOSTIC
echo.
echo Running Full Diagnostic...
echo ========================================
echo This may take a few minutes...
echo.

REM Check if PowerShell diagnostic script exists
if exist "labjack-diagnostics.ps1" (
    echo Running PowerShell diagnostic script...
    powershell -ExecutionPolicy Bypass -File "labjack-diagnostics.ps1" -ExportResults
) else (
    echo PowerShell diagnostic script not found in current directory
    echo Running basic diagnostic...
    
    echo.
    echo === BASIC DIAGNOSTIC RESULTS ===
    
    echo 1. USB Device Check:
    powershell -Command "Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like '*LabJack*' } | Select-Object Name, Status"
    
    echo.
    echo 2. Service Check:
    sc query LabJackUSB
    
    echo.
    echo 3. Network Test:
    ping -n 1 192.168.1.207 >nul 2>&1
    if %errorLevel%==0 (
        echo [OK] Network device reachable at 192.168.1.207
    ) else (
        echo [INFO] No network device at 192.168.1.207
    )
    
    echo.
    echo 4. API Test:
    powershell -Command "try { Invoke-RestMethod -Uri 'http://localhost:8000/api/signal-validation/labjack/status' -TimeoutSec 5 | ConvertTo-Json } catch { Write-Host 'API not accessible or no response' }"
)

echo.
echo Diagnostic completed.
pause
goto MENU

:EXIT
echo.
echo LabJack Quick Fix Tool - Goodbye!
echo.
exit /b 0

REM Error handling
:ERROR
echo.
echo An error occurred: %errorlevel%
echo Please try running as Administrator or check the logs.
echo.
pause
goto MENU