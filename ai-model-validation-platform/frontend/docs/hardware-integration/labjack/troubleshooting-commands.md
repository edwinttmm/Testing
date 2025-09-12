# LabJack Troubleshooting Commands Reference

## Quick Command Reference

### Immediate Diagnostic Commands

```powershell
# Check LabJack USB devices
Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like "*LabJack*" }

# Check LabJack services
Get-Service | Where-Object { $_.Name -like "*LabJack*" }

# Test network LabJack (default IP)
Test-NetConnection -ComputerName "192.168.1.207" -Port 502

# Check API status
Invoke-RestMethod -Uri "http://localhost:8000/api/signal-validation/labjack/status"

# Restart LabJack service
Restart-Service -Name "LabJackUSB" -Force
```

## Device Detection Issues

### Problem: Device Not Showing in Device Manager

```powershell
# Scan for hardware changes
pnputil /scan-devices

# Check all PnP devices for LabJack
Get-PnpDevice | Where-Object { $_.FriendlyName -like "*LabJack*" -or $_.HardwareID -like "*LabJack*" }

# Check USB device enumeration
Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Status -ne "OK" }

# Force driver reinstallation
pnputil /add-driver "C:\Path\To\LabJack\Driver\*.inf" /subdirs /install
```

### Problem: Device Shows as "Unknown Device"

```cmd
# Update drivers automatically
pnputil /add-driver "C:\Program Files (x86)\LabJack\Applications\LJM\Driver\*.inf" /subdirs /install

# Remove conflicting drivers
devcon remove "USB\VID_0CD5*"  # LabJack vendor ID

# Reinstall device
devcon rescan
```

### Problem: Driver Installation Issues

```powershell
# Check driver store for LabJack drivers
pnputil /enum-drivers | Select-String -Pattern "LabJack"

# Remove old drivers
pnputil /delete-driver "oem##.inf" /uninstall /force

# Install fresh drivers
pnputil /add-driver "C:\LabJackDrivers\*.inf" /subdirs /install
```

## USB Connection Problems

### Problem: USB Device Not Recognized

```powershell
# Check USB controller status
Get-WmiObject -Class Win32_USBController | Where-Object { $_.Status -ne "OK" }

# Reset USB controllers
Get-WmiObject -Class Win32_USBController | ForEach-Object { 
    $_.Disable(); 
    Start-Sleep -Seconds 2; 
    $_.Enable() 
}

# Check USB power management
Get-WmiObject -Class Win32_USBHub | ForEach-Object {
    $_.SetPowerState(1)  # Disable power management
}
```

### Problem: USB Device Disconnects Randomly

```powershell
# Disable USB selective suspend
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setactive SCHEME_CURRENT

# Check USB device power settings
Get-WmiObject -Class MSPower_DeviceEnable -Namespace root\wmi | 
Where-Object { $_.InstanceName -like "*USB*LabJack*" } |
Set-WmiInstance -Arguments @{Enable = $false}
```

### Problem: Multiple USB Devices Conflict

```cmd
# List all USB devices with vendor/product IDs
wmic path Win32_USBDevice get DeviceID,Description,Status

# Check for duplicate device entries
reg query "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\USB" /s | findstr "LabJack"

# Clean registry of duplicate entries (BE CAREFUL!)
# reg delete "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\USB\VID_0CD5&PID_####\Duplicate" /f
```

## Network Connection Issues

### Problem: Cannot Discover Ethernet LabJack

```powershell
# Scan network range for LabJack devices
1..254 | ForEach-Object {
    $ip = "192.168.1.$_"
    if (Test-Connection -ComputerName $ip -Count 1 -Quiet -TimeoutSeconds 1) {
        $modbus = Test-NetConnection -ComputerName $ip -Port 502 -WarningAction SilentlyContinue
        if ($modbus.TcpTestSucceeded) {
            Write-Host "LabJack device found at: $ip"
        }
    }
}

# Check common LabJack IP addresses
$labJackIPs = @("192.168.1.207", "192.168.0.207", "169.254.1.207")
foreach ($ip in $labJackIPs) {
    Test-NetConnection -ComputerName $ip -Port 502
}
```

### Problem: Network Connection Timeouts

```powershell
# Test with different timeout values
Test-NetConnection -ComputerName "192.168.1.207" -Port 502 -Timeout 10

# Check Windows Firewall
Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*LabJack*" }

# Temporarily disable Windows Firewall for testing
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False
# Test connection here
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True
```

### Problem: Modbus TCP Communication Errors

```powershell
# Test raw TCP connection
$tcpClient = New-Object System.Net.Sockets.TcpClient
try {
    $tcpClient.Connect("192.168.1.207", 502)
    Write-Host "TCP connection successful"
    $tcpClient.Close()
} catch {
    Write-Host "TCP connection failed: $_"
}

# Check network adapter settings
Get-NetAdapter | Where-Object { $_.Status -eq "Up" }
Get-NetIPConfiguration
```

## Service and Software Issues

### Problem: LabJack Service Not Starting

```cmd
# Check service dependencies
sc qc LabJackUSB

# Start service manually
sc start LabJackUSB

# Check service logs
eventvwr.msc
# Navigate to Windows Logs > System, filter for LabJack
```

### Problem: LJM Library Issues

```powershell
# Check LJM installation
$ljmPath = "C:\Program Files (x86)\LabJack\Applications\LJM\LJM_library.dll"
if (Test-Path $ljmPath) {
    $version = (Get-ItemProperty $ljmPath).VersionInfo.FileVersion
    Write-Host "LJM Version: $version"
} else {
    Write-Host "LJM Library not found"
}

# Check registry entries
Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\LabJack\LJM" -ErrorAction SilentlyContinue

# Repair LJM installation
Start-Process -FilePath "C:\Program Files (x86)\LabJack\Applications\LJM\LJM_installer.exe" -ArgumentList "/repair" -Wait
```

### Problem: Python Module Import Errors

```python
# Test Python path and import
import sys
print("Python paths:")
for path in sys.path:
    print(f"  {path}")

# Add LabJack path manually
sys.path.insert(0, r'C:\Program Files (x86)\LabJack\Applications\LJM\Python')

try:
    from labjack import ljm
    print(f"LJM loaded successfully, version: {ljm.constants.LJM_LIBRARY_VERSION}")
except ImportError as e:
    print(f"Import error: {e}")
```

## Firewall and Security Issues

### Problem: Windows Firewall Blocking LabJack

```powershell
# Check current firewall rules for LabJack
Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*LabJack*" } | 
Select-Object DisplayName, Enabled, Direction, Action

# Create comprehensive firewall rules
New-NetFirewallRule -DisplayName "LabJack LJM Library" -Direction Inbound -Protocol TCP -LocalPort 502 -Action Allow
New-NetFirewallRule -DisplayName "LabJack Kipling" -Direction Inbound -Program "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe" -Action Allow
New-NetFirewallRule -DisplayName "LabJack UDP Discovery" -Direction Inbound -Protocol UDP -LocalPort 5350 -Action Allow

# Allow all LabJack executables
Get-ChildItem "C:\Program Files (x86)\LabJack\" -Recurse -Filter "*.exe" | ForEach-Object {
    New-NetFirewallRule -DisplayName "LabJack - $($_.BaseName)" -Direction Inbound -Program $_.FullName -Action Allow
}
```

### Problem: Windows Defender Interference

```powershell
# Add LabJack folder to Windows Defender exclusions
Add-MpPreference -ExclusionPath "C:\Program Files (x86)\LabJack\"

# Add process exclusions
Add-MpPreference -ExclusionProcess "Kipling.exe"
Add-MpPreference -ExclusionProcess "LJStreamM.exe"
Add-MpPreference -ExclusionProcess "LJLogM.exe"

# Verify exclusions
Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
Get-MpPreference | Select-Object -ExpandProperty ExclusionProcess
```

### Problem: User Account Control (UAC) Issues

```powershell
# Check UAC level
Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableLUA"

# Run LabJack applications with elevated privileges
Start-Process -FilePath "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe" -Verb RunAs

# Create elevated shortcut for frequent use
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut("$env:USERPROFILE\Desktop\Kipling (Admin).lnk")
$shortcut.TargetPath = "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe"
$shortcut.WindowStyle = 1
$shortcut.Save()
```

## API and Backend Issues

### Problem: Backend API Not Responding

```powershell
# Test backend health
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "Backend healthy: $($health.status)"
} catch {
    Write-Host "Backend not accessible: $_"
}

# Test LabJack specific endpoints
$endpoints = @(
    "http://localhost:8000/api/signal-validation/labjack/status",
    "http://localhost:8000/api/signal-validation/test-connection"
)

foreach ($endpoint in $endpoints) {
    try {
        $response = Invoke-RestMethod -Uri $endpoint -TimeoutSec 10
        Write-Host "✓ $endpoint - OK"
    } catch {
        Write-Host "✗ $endpoint - FAILED: $_"
    }
}
```

### Problem: WebSocket Connection Issues

```powershell
# Test WebSocket port availability
Test-NetConnection -ComputerName "localhost" -Port 8000

# Check if port is in use by correct process
netstat -ano | findstr :8000

# Test WebSocket connection (requires additional tools)
# Consider using wscat or similar tool for testing
```

### Problem: API Authentication Errors

```powershell
# Test API without authentication (if supported)
Invoke-RestMethod -Uri "http://localhost:8000/api/signal-validation/labjack/status" -Headers @{"Accept" = "application/json"}

# Check API configuration
$apiConfig = Get-Content "path\to\api\config.json" | ConvertFrom-Json
Write-Host "API Configuration: $($apiConfig | ConvertTo-Json -Depth 2)"
```

## Performance and Communication Issues

### Problem: Slow Communication with Device

```python
# Test communication speed
import time
import sys
sys.path.append(r'C:\Program Files (x86)\LabJack\Applications\LJM\Python')

from labjack import ljm

handle = ljm.openS("ANY", "ANY", "ANY")

# Single read speed test
start = time.time()
for i in range(1000):
    ljm.eReadName(handle, "AIN0")
end = time.time()

print(f"1000 single reads took {end-start:.2f} seconds ({1000/(end-start):.0f} reads/sec)")

ljm.close(handle)
```

### Problem: Streaming Data Loss

```python
# Check for missed scans during streaming
import sys
sys.path.append(r'C:\Program Files (x86)\LabJack\Applications\LJM\Python')

from labjack import ljm

handle = ljm.openS("ANY", "ANY", "ANY")

# Configure and start stream
scan_rate = 1000
scans_per_read = 100
a_scan_list = ljm.namesToAddresses(2, ["AIN0", "AIN1"])[0]

actual_scan_rate = ljm.eStreamStart(handle, scans_per_read, 2, a_scan_list, scan_rate)
print(f"Stream started at {actual_scan_rate} Hz")

# Read data and check for missed scans
for i in range(10):
    ret = ljm.eStreamRead(handle, scans_per_read, 2)
    
    # Check missed scans register
    try:
        missed_scans = ljm.eReadName(handle, "STREAM_NUM_SCANS_MISSED")
        if missed_scans > 0:
            print(f"Warning: {missed_scans} scans missed")
    except:
        pass  # Not all devices support this

ljm.eStreamStop(handle)
ljm.close(handle)
```

## System Resource Issues

### Problem: High CPU Usage During Streaming

```powershell
# Monitor CPU usage
Get-Counter "\Processor(_Total)\% Processor Time" -MaxSamples 10 -SampleInterval 1

# Check specific process CPU usage
Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*Kipling*" } | 
Select-Object ProcessName, CPU, WorkingSet

# Reduce stream rate to lower CPU usage
# Modify scan rate and scans per read in your application
```

### Problem: Memory Leaks

```powershell
# Monitor memory usage
Get-Counter "\Memory\Available MBytes" -MaxSamples 10 -SampleInterval 1

# Check for memory leaks in specific processes
Get-Process | Where-Object { $_.ProcessName -like "*python*" } | 
Select-Object ProcessName, WorkingSet, PeakWorkingSet, VirtualMemorySize

# Force garbage collection in Python
# Add to your Python code: import gc; gc.collect()
```

## Emergency Recovery Commands

### Complete System Reset for LabJack

```powershell
# Complete LabJack system reset (USE WITH CAUTION!)

Write-Host "Starting LabJack system reset..."

# 1. Stop all LabJack services
Get-Service | Where-Object { $_.Name -like "*LabJack*" } | Stop-Service -Force

# 2. Kill all LabJack processes
Get-Process | Where-Object { $_.ProcessName -like "*Kipling*" -or $_.ProcessName -like "*LJ*" } | Stop-Process -Force

# 3. Disable and re-enable all USB LabJack devices
Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like "*LabJack*" } | ForEach-Object {
    Write-Host "Resetting device: $($_.Name)"
    $_.Disable()
    Start-Sleep -Seconds 2
    $_.Enable()
}

# 4. Scan for hardware changes
pnputil /scan-devices

# 5. Restart LabJack services
Get-Service | Where-Object { $_.Name -like "*LabJack*" } | Start-Service

Write-Host "LabJack system reset completed"
```

### Registry Cleanup (Advanced Users Only)

```cmd
REM WARNING: Backup registry before running these commands!
REM reg export HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\USB backup.reg

REM Remove duplicate LabJack USB entries
reg query "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\USB" /s | findstr "LabJack"

REM Clean LabJack software registry entries (if reinstalling)
reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\LabJack" /f
reg delete "HKEY_CURRENT_USER\SOFTWARE\LabJack" /f
```

## Automated Diagnostic Script Usage

### Run Complete Diagnostic

```powershell
# Download and run the diagnostic script
# PowerShell -ExecutionPolicy Bypass -File "labjack-diagnostics.ps1" -ExportResults -FixIssues

# Check results
Get-Content "LabJack_Diagnostic_*.json" | ConvertFrom-Json | Format-List
```

### Quick Fix Batch Script

```cmd
REM Run the quick fix batch script
labjack-quick-fix.bat

REM Or specific fixes:
REM Option 1: Restart LabJack USB Service
REM Option 2: Scan for Hardware Changes  
REM Option 3: Reset USB Devices
REM etc.
```

## Common Error Codes and Solutions

| Error Code | Description | Solution |
|------------|-------------|----------|
| 1224 | LJME_NO_DEVICES_FOUND | Check connections, drivers, and power |
| 1230 | LJME_CANNOT_OPEN_DEVICE | Close other applications using device |
| 1301 | LJME_INVALID_ADDRESS | Check register name spelling |
| 2398 | LJME_CANNOT_START_STREAM | Reduce scan rate or channels |
| 1239 | LJME_U3_NOT_FOUND_TD | U3 device communication error |
| 1315 | LJME_INVALID_VALUE | Check value range for register |

## Logging and Debug Information

### Enable Detailed Logging

```python
# Python logging for LabJack operations
import logging
logging.basicConfig(level=logging.DEBUG)

# LJM debug logging (if available)
import sys
sys.path.append(r'C:\Program Files (x86)\LabJack\Applications\LJM\Python')

from labjack import ljm
ljm.debugLevel = 1  # Enable debug output
```

### Collect System Information

```powershell
# Generate comprehensive system report
$report = @{
    SystemInfo = Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory
    USBDevices = Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like "*LabJack*" }
    Services = Get-Service | Where-Object { $_.Name -like "*LabJack*" }
    FirewallRules = Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*LabJack*" }
    NetworkConfig = Get-NetIPConfiguration
    Processes = Get-Process | Where-Object { $_.ProcessName -like "*LJ*" -or $_.ProcessName -like "*Kipling*" }
}

$report | ConvertTo-Json -Depth 3 | Out-File "LabJack_SystemReport.json"
```

This reference guide provides immediate solutions for the most common LabJack connectivity issues on Windows systems. Keep this document handy for quick troubleshooting during hardware integration work.