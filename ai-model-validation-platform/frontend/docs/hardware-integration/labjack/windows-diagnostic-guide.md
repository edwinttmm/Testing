# LabJack Windows Integration Diagnostic Guide

## Overview

This comprehensive guide provides Windows-specific diagnostic procedures, troubleshooting steps, and validation tests for LabJack device connectivity in the AI Model Validation Platform.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-Connection Diagnostics](#pre-connection-diagnostics)
3. [Windows Device Manager Checks](#windows-device-manager-checks)
4. [USB Driver Installation](#usb-driver-installation)
5. [LabJack Software Requirements](#labjack-software-requirements)
6. [Firewall and Security Configuration](#firewall-and-security-configuration)
7. [Hardware Connection Validation](#hardware-connection-validation)
8. [Communication Protocol Testing](#communication-protocol-testing)
9. [Troubleshooting Common Issues](#troubleshooting-common-issues)
10. [Diagnostic Scripts](#diagnostic-scripts)
11. [Integration Testing](#integration-testing)

## System Requirements

### Windows Compatibility
- **Supported OS**: Windows 10 (1903+), Windows 11
- **Architecture**: x64 (64-bit) recommended, x86 (32-bit) supported
- **USB**: USB 2.0 or higher ports
- **RAM**: Minimum 4GB, Recommended 8GB+
- **.NET Framework**: 4.7.2 or later
- **Visual C++**: Microsoft Visual C++ 2015-2022 Redistributable

### LabJack Device Compatibility
- **T4**: Full support (USB/Ethernet)
- **T7**: Full support (USB/Ethernet/WiFi)
- **T8**: Full support (USB/Ethernet)
- **U3**: Limited support (USB only)
- **U6**: Limited support (USB only)

## Pre-Connection Diagnostics

### 1. System Information Check

```powershell
# Get Windows version and architecture
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory, CsProcessors

# Check USB controllers
Get-WmiObject -Class Win32_USBController | Select-Object Name, Status, DeviceID

# Verify .NET Framework versions
Get-ChildItem 'HKLM:SOFTWARE\Microsoft\NET Framework Setup\NDP' -Recurse |
Get-ItemProperty -Name Version -EA 0 |
Where-Object { $_.PSChildName -Match '^(?!S)\p{L}' } |
Select-Object PSChildName, Version
```

### 2. Port Availability Check

```powershell
# Check USB port status
Get-WmiObject -Class Win32_USBHub | Select-Object DeviceID, Status, Description

# Test network connectivity (for Ethernet LabJack devices)
Test-NetConnection -ComputerName "192.168.1.207" -Port 502 -WarningAction SilentlyContinue
```

## Windows Device Manager Checks

### Diagnostic Checklist

#### Step 1: Open Device Manager
```cmd
# Command line method
devmgmt.msc

# PowerShell method
Start-Process devmgmt.msc
```

#### Step 2: LabJack Device Detection

**Expected Device Locations:**
- **Universal Serial Bus devices** → "LabJack T4", "LabJack T7", etc.
- **Human Interface Devices** → "HID-compliant device" (LabJack HID interface)
- **Network adapters** → "LabJack Ethernet Interface" (Ethernet models)

**Status Indicators:**
- ✅ **Working**: Device shows without warning icons
- ⚠️ **Problem**: Yellow warning triangle
- ❌ **Error**: Red X or not detected
- ❓ **Unknown**: "Unknown device" in Device Manager

#### Step 3: Device Properties Verification

```powershell
# Get LabJack device information
Get-PnpDevice | Where-Object { $_.FriendlyName -like "*LabJack*" } | 
Select-Object FriendlyName, Status, InstanceId, Class

# Check USB device details
Get-WmiObject -Class Win32_USBDevice | 
Where-Object { $_.Description -like "*LabJack*" } |
Select-Object Name, Description, DeviceID, Status
```

### Device Manager Troubleshooting

#### Problem: Device Not Detected
```powershell
# Refresh hardware changes
Get-PnpDevice | Where-Object { $_.Status -eq "Unknown" } | Enable-PnpDevice -Confirm:$false

# Scan for hardware changes (equivalent to "Scan for hardware changes")
pnputil /scan-devices
```

#### Problem: Driver Issues
```cmd
# Update drivers
pnputil /add-driver "C:\Path\To\LabJack\Driver\*.inf" /subdirs /install

# Remove problematic drivers
pnputil /delete-driver "oem##.inf" /uninstall
```

## USB Driver Installation

### Automatic Installation (Recommended)

#### Step 1: Download LabJack Software Bundle
```powershell
# Download and install LabJack software (includes drivers)
# URL: https://labjack.com/support/software/installers/ljm

# Verify installation
if (Test-Path "C:\Program Files (x86)\LabJack\Applications") {
    Write-Host "✅ LabJack software installed" -ForegroundColor Green
} else {
    Write-Host "❌ LabJack software not found" -ForegroundColor Red
}
```

### Manual Driver Installation

#### Step 1: Download Drivers
- **T4/T7/T8**: Download LJM (LabJack Modbus) drivers
- **U3/U6**: Download UD (Universal Driver) drivers

#### Step 2: Installation Commands
```cmd
# Run as Administrator
# For T4/T7/T8 devices
"C:\Program Files (x86)\LabJack\Applications\LJM\LJM_installer.exe" /S

# Verify driver installation
sc query "LabJackUSB" | findstr "STATE"
```

### Driver Verification

```powershell
# Check LabJack services
Get-Service | Where-Object { $_.Name -like "*LabJack*" } | Select-Object Name, Status, StartType

# Verify LJM library installation
$ljmPath = "C:\Program Files (x86)\LabJack\Applications\LJM"
if (Test-Path "$ljmPath\LJM_library.dll") {
    $version = (Get-ItemProperty "$ljmPath\LJM_library.dll").VersionInfo.FileVersion
    Write-Host "✅ LJM Library version: $version" -ForegroundColor Green
}

# Check registry entries
Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\LabJack\LJM" -Name "Version" -ErrorAction SilentlyContinue
```

## LabJack Software Requirements

### Core Components

#### 1. LJM (LabJack Modbus) Library
- **Required for**: T4, T7, T8 devices
- **Version**: 1.21.0 or later recommended
- **Installation path**: `C:\Program Files (x86)\LabJack\Applications\LJM\`

#### 2. Kipling (LabJack's Configuration Software)
- **Purpose**: Device configuration and testing
- **Installation path**: `C:\Program Files (x86)\LabJack\Applications\Kipling\`

#### 3. LJLogM (Data Logging Software)
- **Purpose**: Data logging and streaming
- **Optional**: For advanced data collection

### Installation Verification Script

```powershell
# LabJack Software Installation Checker
function Test-LabJackInstallation {
    $results = @{}
    
    # Check LJM Library
    $ljmPath = "C:\Program Files (x86)\LabJack\Applications\LJM\LJM_library.dll"
    $results.LJM = Test-Path $ljmPath
    
    # Check Kipling
    $kiplingPath = "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe"
    $results.Kipling = Test-Path $kiplingPath
    
    # Check registry
    try {
        $ljmReg = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\LabJack\LJM" -Name "Version" -ErrorAction Stop
        $results.Registry = $true
        $results.Version = $ljmReg.Version
    } catch {
        $results.Registry = $false
    }
    
    # Check services
    $ljmService = Get-Service -Name "LabJackUSB" -ErrorAction SilentlyContinue
    $results.Service = $ljmService -ne $null -and $ljmService.Status -eq "Running"
    
    return $results
}

# Run the test
$installCheck = Test-LabJackInstallation
$installCheck | Format-Table -AutoSize
```

## Firewall and Security Configuration

### Windows Firewall Rules

#### Create Firewall Rules for LabJack
```powershell
# Allow LabJack software through Windows Firewall
New-NetFirewallRule -DisplayName "LabJack LJM Library" -Direction Inbound -Protocol TCP -LocalPort 502 -Action Allow
New-NetFirewallRule -DisplayName "LabJack Kipling" -Direction Inbound -Program "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe" -Action Allow

# Allow specific ports for Ethernet LabJack devices
New-NetFirewallRule -DisplayName "LabJack Modbus TCP" -Direction Inbound -Protocol TCP -LocalPort 502 -Action Allow
New-NetFirewallRule -DisplayName "LabJack UDP Discovery" -Direction Inbound -Protocol UDP -LocalPort 5350 -Action Allow

# Check current firewall rules
Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*LabJack*" } | Select-Object DisplayName, Enabled, Direction, Action
```

### Windows Defender Antivirus

#### Add Exclusions
```powershell
# Add LabJack installation directory to exclusions
Add-MpPreference -ExclusionPath "C:\Program Files (x86)\LabJack\"

# Add process exclusions
Add-MpPreference -ExclusionProcess "Kipling.exe"
Add-MpPreference -ExclusionProcess "python.exe"  # If using Python integration

# Verify exclusions
Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
Get-MpPreference | Select-Object -ExpandProperty ExclusionProcess
```

### User Account Control (UAC)

```powershell
# Check UAC status
Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableLUA"

# Temporarily disable UAC for installation (requires restart)
# Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableLUA" -Value 0

# Run applications with elevated privileges
Start-Process -FilePath "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe" -Verb RunAs
```

## Hardware Connection Validation

### USB Connection Tests

#### Test 1: Physical Connection
```powershell
# Check USB device enumeration
Get-WmiObject -Class Win32_USBDevice | 
Where-Object { $_.Description -like "*LabJack*" -or $_.Name -like "*LabJack*" } |
Select-Object Name, DeviceID, Status, Description

# Monitor USB events (requires running as Administrator)
Register-WmiEvent -Query "SELECT * FROM Win32_VolumeChangeEvent WHERE EventType = 2" -Action {
    Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like "*LabJack*" }
}
```

#### Test 2: Device Communication
```powershell
# Test basic device communication using LJM
$testScript = @"
import sys
sys.path.append(r'C:\Program Files (x86)\LabJack\Applications\LJM\Python')

try:
    from labjack import ljm
    
    # Open device
    handle = ljm.openS("T7", "USB", "ANY")
    
    # Read device info
    info = ljm.getHandleInfo(handle)
    print(f"Device Type: {info[0]}")
    print(f"Connection Type: {info[1]}")
    print(f"Serial Number: {info[2]}")
    
    # Test analog input
    voltage = ljm.eReadName(handle, "AIN0")
    print(f"AIN0 Voltage: {voltage:.3f}V")
    
    # Close connection
    ljm.close(handle)
    print("✅ Device communication successful")
    
except Exception as e:
    print(f"❌ Device communication failed: {e}")
"@

# Save and run the test script
$testScript | Out-File -FilePath "test_labjack.py" -Encoding UTF8
python test_labjack.py
```

### Ethernet Connection Tests

#### Network Discovery
```powershell
# Discover LabJack devices on network
$devices = @()
1..254 | ForEach-Object {
    $ip = "192.168.1.$_"
    if (Test-Connection -ComputerName $ip -Count 1 -Quiet -TimeoutSeconds 1) {
        $port = Test-NetConnection -ComputerName $ip -Port 502 -WarningAction SilentlyContinue
        if ($port.TcpTestSucceeded) {
            $devices += $ip
        }
    }
}

Write-Host "LabJack devices found at:" -ForegroundColor Green
$devices | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
```

#### Modbus TCP Test
```powershell
# Test Modbus TCP connection
function Test-ModbusTCP {
    param([string]$IPAddress = "192.168.1.207", [int]$Port = 502)
    
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect($IPAddress, $Port)
        
        if ($tcpClient.Connected) {
            Write-Host "✅ Modbus TCP connection successful to $IPAddress:$Port" -ForegroundColor Green
            $tcpClient.Close()
            return $true
        }
    } catch {
        Write-Host "❌ Modbus TCP connection failed: $_" -ForegroundColor Red
        return $false
    }
}

Test-ModbusTCP
```

## Communication Protocol Testing

### Protocol Validation Script

```powershell
# LabJack Protocol Test Suite
function Test-LabJackProtocols {
    param(
        [string]$DeviceType = "T7",
        [string]$ConnectionType = "USB"
    )
    
    $results = @{
        USBConnection = $false
        EthernetConnection = $false
        ModbusProtocol = $false
        StreamingMode = $false
        AnalogInputs = $false
        DigitalIO = $false
    }
    
    # Test USB connection
    try {
        $usbDevices = Get-WmiObject -Class Win32_USBDevice | 
                     Where-Object { $_.Description -like "*LabJack*" }
        $results.USBConnection = $usbDevices.Count -gt 0
    } catch {
        Write-Warning "USB connection test failed: $_"
    }
    
    # Test Ethernet connection
    try {
        $ethernetTest = Test-NetConnection -ComputerName "192.168.1.207" -Port 502 -WarningAction SilentlyContinue
        $results.EthernetConnection = $ethernetTest.TcpTestSucceeded
    } catch {
        Write-Warning "Ethernet connection test failed: $_"
    }
    
    return $results
}

# Run protocol tests
$protocolResults = Test-LabJackProtocols
$protocolResults | Format-Table -AutoSize
```

### API Integration Test

```powershell
# Test API integration with backend
$apiTestScript = @"
import requests
import json

# Test LabJack status endpoint
try:
    response = requests.get('http://localhost:8000/api/signal-validation/labjack/status', timeout=5)
    data = response.json()
    
    print("LabJack API Status:")
    print(f"  Connected: {data.get('connected', 'Unknown')}")
    print(f"  Mock Mode: {data.get('mock_mode', 'Unknown')}")
    print(f"  Channels: {data.get('channels', 'Unknown')}")
    print(f"  Sample Rate: {data.get('sample_rate', 'Unknown')}")
    
    if data.get('error'):
        print(f"  Error: {data['error']}")
        
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to backend API")
except Exception as e:
    print(f"❌ API test failed: {e}")
"@

$apiTestScript | Out-File -FilePath "test_api.py" -Encoding UTF8
python test_api.py
```

## Troubleshooting Common Issues

### Issue 1: Device Not Detected

**Symptoms:**
- Device Manager shows "Unknown Device"
- No LabJack entries in Device Manager
- API returns `connected: false`

**Resolution Steps:**

```powershell
# Step 1: Check USB connection
Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Status -ne "OK" }

# Step 2: Restart LabJack services
Restart-Service -Name "LabJackUSB" -Force

# Step 3: Re-enumerate USB devices
pnputil /scan-devices

# Step 4: Check for driver conflicts
Get-WmiObject -Class Win32_SystemDriver | Where-Object { $_.Name -like "*usb*" -and $_.State -ne "Running" }
```

### Issue 2: Permission Denied

**Symptoms:**
- "Access denied" errors in API
- Device detected but cannot communicate
- Kipling shows permission errors

**Resolution Steps:**

```powershell
# Step 1: Run as Administrator
Start-Process powershell -Verb RunAs

# Step 2: Check service permissions
$service = Get-WmiObject -Class Win32_Service -Filter "Name='LabJackUSB'"
$service.Change($null, $null, $null, $null, $null, $null, "LocalSystem", $null)

# Step 3: Grant full control to device
$devicePath = (Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like "*LabJack*" }).DeviceID
icacls "$devicePath" /grant "*S-1-1-0:(OI)(CI)F"
```

### Issue 3: Intermittent Connection

**Symptoms:**
- Device connects/disconnects randomly
- Communication timeouts
- Streaming interruptions

**Resolution Steps:**

```powershell
# Step 1: Check USB power management
Get-WmiObject -Class Win32_USBHub | ForEach-Object {
    $_.SetPowerState(1)  # Disable power management
}

# Step 2: Update USB drivers
pnputil /add-driver "C:\Windows\System32\DriverStore\FileRepository\usb.inf_*\*.inf" /install

# Step 3: Check system resources
Get-Counter "\Processor(_Total)\% Processor Time"
Get-Counter "\Memory\Available MBytes"
```

### Issue 4: Network Discovery Problems

**Symptoms:**
- Cannot discover Ethernet LabJack devices
- Network connection fails
- Modbus TCP errors

**Resolution Steps:**

```powershell
# Step 1: Check network configuration
Get-NetAdapter | Where-Object { $_.Status -eq "Up" }
Get-NetIPConfiguration

# Step 2: Test network connectivity
Test-NetConnection -ComputerName "192.168.1.207" -Port 502 -DiagnoseRouting

# Step 3: Reset network stack
netsh winsock reset
netsh int ip reset
```

## Diagnostic Scripts

### Complete System Diagnostic

```powershell
# LabJack System Diagnostic Script
# Save as: LabjackDiagnostic.ps1

param(
    [switch]$Detailed,
    [switch]$ExportResults,
    [string]$OutputPath = "LabJack_Diagnostic_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
)

function Write-DiagnosticHeader {
    param([string]$Title)
    Write-Host "`n" + "="*60 -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor White
    Write-Host "="*60 -ForegroundColor Cyan
}

function Test-LabJackSystemDiagnostic {
    $results = @{}
    
    Write-DiagnosticHeader "SYSTEM INFORMATION"
    
    # System info
    $sysInfo = Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory
    Write-Host "OS: $($sysInfo.WindowsProductName)"
    Write-Host "Version: $($sysInfo.WindowsVersion)"
    Write-Host "RAM: $([math]::Round($sysInfo.TotalPhysicalMemory/1GB, 1)) GB"
    $results.SystemInfo = $sysInfo
    
    Write-DiagnosticHeader "USB CONTROLLERS"
    
    # USB controllers
    $usbControllers = Get-WmiObject -Class Win32_USBController
    $usbControllers | Select-Object Name, Status | Format-Table -AutoSize
    $results.USBControllers = $usbControllers
    
    Write-DiagnosticHeader "LABJACK DEVICES"
    
    # LabJack devices
    $labJackDevices = Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like "*LabJack*" }
    if ($labJackDevices) {
        $labJackDevices | Select-Object Name, DeviceID, Status | Format-Table -AutoSize
        Write-Host "✅ LabJack devices detected: $($labJackDevices.Count)" -ForegroundColor Green
    } else {
        Write-Host "❌ No LabJack devices detected" -ForegroundColor Red
    }
    $results.LabJackDevices = $labJackDevices
    
    Write-DiagnosticHeader "LABJACK SOFTWARE"
    
    # Software installation
    $ljmPath = "C:\Program Files (x86)\LabJack\Applications\LJM\LJM_library.dll"
    $kiplingPath = "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe"
    
    $softwareStatus = @{
        LJMLibrary = Test-Path $ljmPath
        Kipling = Test-Path $kiplingPath
        Registry = $false
        Service = $false
    }
    
    # Check registry
    try {
        $ljmReg = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\LabJack\LJM" -Name "Version" -ErrorAction Stop
        $softwareStatus.Registry = $true
        $softwareStatus.Version = $ljmReg.Version
    } catch {
        $softwareStatus.Registry = $false
    }
    
    # Check services
    $ljmService = Get-Service -Name "LabJackUSB" -ErrorAction SilentlyContinue
    $softwareStatus.Service = $ljmService -ne $null -and $ljmService.Status -eq "Running"
    
    $softwareStatus | Format-Table -AutoSize
    $results.SoftwareStatus = $softwareStatus
    
    Write-DiagnosticHeader "NETWORK CONNECTIVITY"
    
    # Network test
    $networkTest = Test-NetConnection -ComputerName "192.168.1.207" -Port 502 -WarningAction SilentlyContinue
    if ($networkTest.TcpTestSucceeded) {
        Write-Host "✅ Network LabJack accessible at 192.168.1.207:502" -ForegroundColor Green
    } else {
        Write-Host "❌ No network LabJack found at 192.168.1.207:502" -ForegroundColor Red
    }
    $results.NetworkTest = $networkTest
    
    Write-DiagnosticHeader "FIREWALL RULES"
    
    # Firewall rules
    $firewallRules = Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*LabJack*" }
    if ($firewallRules) {
        $firewallRules | Select-Object DisplayName, Enabled, Direction, Action | Format-Table -AutoSize
    } else {
        Write-Host "⚠️ No LabJack firewall rules found" -ForegroundColor Yellow
    }
    $results.FirewallRules = $firewallRules
    
    Write-DiagnosticHeader "API CONNECTIVITY"
    
    # Test backend API
    try {
        $apiResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/signal-validation/labjack/status" -TimeoutSec 5
        Write-Host "✅ Backend API accessible" -ForegroundColor Green
        Write-Host "  Connected: $($apiResponse.connected)"
        Write-Host "  Mock Mode: $($apiResponse.mock_mode)"
        if ($apiResponse.error) {
            Write-Host "  Error: $($apiResponse.error)" -ForegroundColor Red
        }
        $results.APITest = $apiResponse
    } catch {
        Write-Host "❌ Backend API not accessible: $_" -ForegroundColor Red
        $results.APITest = $null
    }
    
    return $results
}

# Run diagnostic
$diagnosticResults = Test-LabJackSystemDiagnostic

# Export results if requested
if ($ExportResults) {
    $diagnosticResults | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutputPath -Encoding UTF8
    Write-Host "`nDiagnostic results exported to: $OutputPath" -ForegroundColor Green
}

Write-Host "`nDiagnostic completed. Check results above for any issues." -ForegroundColor Cyan
```

### Hardware Validation Script

```powershell
# LabJack Hardware Validation Script
function Test-LabJackHardware {
    param(
        [string]$DeviceType = "ANY",
        [string]$ConnectionType = "ANY",
        [switch]$Verbose
    )
    
    $testResults = @{
        DeviceDetection = $false
        Communication = $false
        AnalogInput = $false
        DigitalIO = $false
        StreamingTest = $false
        PerformanceTest = @{}
    }
    
    # Python test script for hardware validation
    $hardwareTestScript = @"
import sys
import time
import statistics
sys.path.append(r'C:\Program Files (x86)\LabJack\Applications\LJM\Python')

try:
    from labjack import ljm
    
    print("🔍 Searching for LabJack devices...")
    
    # Device detection test
    try:
        handle = ljm.openS("$DeviceType", "$ConnectionType", "ANY")
        info = ljm.getHandleInfo(handle)
        
        print(f"✅ Device detected:")
        print(f"   Type: {info[0]}")
        print(f"   Connection: {info[1]}")
        print(f"   Serial: {info[2]}")
        
        device_detection = True
    except Exception as e:
        print(f"❌ Device detection failed: {e}")
        device_detection = False
        exit(1)
    
    # Communication test
    try:
        # Read device name
        name = ljm.eReadNameString(handle, "DEVICE_NAME_DEFAULT")
        print(f"✅ Communication test passed - Device name: {name}")
        communication = True
    except Exception as e:
        print(f"❌ Communication test failed: {e}")
        communication = False
    
    # Analog input test
    try:
        voltage_readings = []
        for i in range(10):
            voltage = ljm.eReadName(handle, "AIN0")
            voltage_readings.append(voltage)
            time.sleep(0.01)
        
        avg_voltage = statistics.mean(voltage_readings)
        voltage_std = statistics.stdev(voltage_readings) if len(voltage_readings) > 1 else 0
        
        print(f"✅ Analog input test - AIN0:")
        print(f"   Average: {avg_voltage:.4f}V")
        print(f"   Std Dev: {voltage_std:.4f}V")
        
        analog_input = True
    except Exception as e:
        print(f"❌ Analog input test failed: {e}")
        analog_input = False
    
    # Digital I/O test
    try:
        # Test digital output
        ljm.eWriteName(handle, "FIO0", 1)  # Set high
        state1 = ljm.eReadName(handle, "FIO0")
        
        ljm.eWriteName(handle, "FIO0", 0)  # Set low
        state2 = ljm.eReadName(handle, "FIO0")
        
        if state1 == 1 and state2 == 0:
            print("✅ Digital I/O test passed")
            digital_io = True
        else:
            print(f"❌ Digital I/O test failed - States: {state1}, {state2}")
            digital_io = False
            
    except Exception as e:
        print(f"❌ Digital I/O test failed: {e}")
        digital_io = False
    
    # Streaming test
    try:
        print("🚀 Starting streaming test...")
        
        # Configure streaming
        scan_rate = 1000
        scans_per_read = 100
        
        a_scan_list_names = ["AIN0", "AIN1"]
        num_addresses = len(a_scan_list_names)
        a_scan_list = ljm.namesToAddresses(num_addresses, a_scan_list_names)[0]
        
        # Start stream
        actual_scan_rate = ljm.eStreamStart(handle, scans_per_read, num_addresses, a_scan_list, scan_rate)
        print(f"   Configured rate: {scan_rate} Hz")
        print(f"   Actual rate: {actual_scan_rate} Hz")
        
        # Read stream data
        start_time = time.time()
        ret = ljm.eStreamRead(handle, scans_per_read, num_addresses)
        end_time = time.time()
        
        # Stop stream
        ljm.eStreamStop(handle)
        
        read_time = end_time - start_time
        samples_per_second = (scans_per_read * num_addresses) / read_time
        
        print(f"✅ Streaming test passed:")
        print(f"   Read time: {read_time:.3f}s")
        print(f"   Samples/sec: {samples_per_second:.0f}")
        print(f"   Data points: {len(ret[0])}")
        
        streaming_test = True
        
    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        streaming_test = False
    
    # Performance benchmark
    try:
        print("⚡ Running performance benchmark...")
        
        # Single read benchmark
        start_time = time.time()
        for i in range(1000):
            ljm.eReadName(handle, "AIN0")
        single_read_time = time.time() - start_time
        
        # Batch read benchmark
        addresses = [0, 2, 4, 6]  # AIN0, AIN1, AIN2, AIN3
        start_time = time.time()
        for i in range(250):
            ljm.eReadAddresses(handle, len(addresses), addresses)
        batch_read_time = time.time() - start_time
        
        print(f"✅ Performance benchmark:")
        print(f"   Single reads (1000x): {single_read_time:.3f}s ({1000/single_read_time:.0f} reads/sec)")
        print(f"   Batch reads (250x4): {batch_read_time:.3f}s ({1000/batch_read_time:.0f} values/sec)")
        
        performance = {
            'single_read_rate': 1000/single_read_time,
            'batch_read_rate': 1000/batch_read_time,
            'single_read_time': single_read_time,
            'batch_read_time': batch_read_time
        }
        
    except Exception as e:
        print(f"❌ Performance benchmark failed: {e}")
        performance = {}
    
    # Close device
    ljm.close(handle)
    print("\n🎯 Hardware validation completed")
    
    # Output results as JSON for PowerShell to parse
    import json
    results = {
        'device_detection': device_detection,
        'communication': communication,
        'analog_input': analog_input,
        'digital_io': digital_io,
        'streaming_test': streaming_test,
        'performance': performance
    }
    
    print(f"\nRESULTS_JSON:{json.dumps(results)}")
    
except ImportError:
    print("❌ LabJack LJM Python module not found. Please install LabJack software.")
except Exception as e:
    print(f"❌ Hardware validation failed: {e}")
"@
    
    # Run the hardware test
    $hardwareTestScript | Out-File -FilePath "hardware_test.py" -Encoding UTF8
    $testOutput = python hardware_test.py 2>&1
    
    # Parse results
    $jsonLine = $testOutput | Where-Object { $_ -match "RESULTS_JSON:" }
    if ($jsonLine) {
        $jsonData = ($jsonLine -split "RESULTS_JSON:")[1]
        try {
            $parsedResults = ConvertFrom-Json $jsonData
            $testResults.DeviceDetection = $parsedResults.device_detection
            $testResults.Communication = $parsedResults.communication
            $testResults.AnalogInput = $parsedResults.analog_input
            $testResults.DigitalIO = $parsedResults.digital_io
            $testResults.StreamingTest = $parsedResults.streaming_test
            $testResults.PerformanceTest = $parsedResults.performance
        } catch {
            Write-Warning "Failed to parse test results JSON"
        }
    }
    
    # Display output
    $testOutput | ForEach-Object { Write-Host $_ }
    
    return $testResults
}

# Usage example:
# Test-LabJackHardware -DeviceType "T7" -ConnectionType "USB" -Verbose
```

## Integration Testing

### Frontend Integration Test

```powershell
# Test frontend LabJack integration
function Test-FrontendIntegration {
    param(
        [string]$FrontendURL = "http://localhost:3000",
        [string]$BackendURL = "http://localhost:8000"
    )
    
    Write-Host "🧪 Testing LabJack Frontend Integration" -ForegroundColor Cyan
    
    # Test 1: Backend API connectivity
    try {
        $apiHealth = Invoke-RestMethod -Uri "$BackendURL/health" -TimeoutSec 5
        Write-Host "✅ Backend API healthy" -ForegroundColor Green
    } catch {
        Write-Host "❌ Backend API not accessible: $_" -ForegroundColor Red
        return $false
    }
    
    # Test 2: LabJack status endpoint
    try {
        $labJackStatus = Invoke-RestMethod -Uri "$BackendURL/api/signal-validation/labjack/status" -TimeoutSec 10
        Write-Host "✅ LabJack status endpoint accessible" -ForegroundColor Green
        Write-Host "  Connected: $($labJackStatus.connected)"
        Write-Host "  Mock Mode: $($labJackStatus.mock_mode)"
    } catch {
        Write-Host "❌ LabJack status endpoint failed: $_" -ForegroundColor Red
    }
    
    # Test 3: Initialize LabJack
    try {
        $initResponse = Invoke-RestMethod -Uri "$BackendURL/api/signal-validation/labjack/initialize" -Method POST -Body "{}" -ContentType "application/json" -TimeoutSec 15
        Write-Host "✅ LabJack initialization successful" -ForegroundColor Green
        Write-Host "  Status: $($initResponse.status)"
        Write-Host "  Message: $($initResponse.message)"
    } catch {
        Write-Host "❌ LabJack initialization failed: $_" -ForegroundColor Red
    }
    
    # Test 4: WebSocket connection (simulate)
    try {
        # This is a simplified test - actual WebSocket testing requires more complex setup
        $wsTest = Test-NetConnection -ComputerName "localhost" -Port 8000 -WarningAction SilentlyContinue
        if ($wsTest.TcpTestSucceeded) {
            Write-Host "✅ WebSocket port accessible" -ForegroundColor Green
        } else {
            Write-Host "❌ WebSocket port not accessible" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "❌ WebSocket test failed: $_" -ForegroundColor Red
    }
    
    Write-Host "`n🎯 Frontend integration test completed" -ForegroundColor Cyan
}

# Run the test
Test-FrontendIntegration
```

### Component Integration Test

```javascript
// Save as: test-labjack-integration.js
// Run with Node.js to test the integration test component

const axios = require('axios');

async function testLabJackIntegration() {
    console.log('🧪 Running LabJack Integration Component Test\n');
    
    const baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    
    const tests = [
        {
            name: 'API Health Check',
            test: async () => {
                const response = await axios.get(`${baseUrl}/health`);
                return { success: true, data: response.data };
            }
        },
        {
            name: 'LabJack Status Check',
            test: async () => {
                const response = await axios.get(`${baseUrl}/api/signal-validation/labjack/status`);
                return { 
                    success: true, 
                    data: {
                        connected: response.data.connected,
                        mock_mode: response.data.mock_mode,
                        channels: response.data.channels
                    }
                };
            }
        },
        {
            name: 'LabJack Initialization',
            test: async () => {
                const config = {
                    voltage_threshold: { lower: 4.0, upper: 5.5 },
                    channels: ['AIN0'],
                    sample_rate: 1000
                };
                const response = await axios.post(`${baseUrl}/api/signal-validation/labjack/initialize`, config);
                return { success: response.data.status === 'connected' || response.data.status === 'success', data: response.data };
            }
        },
        {
            name: 'Signal Monitoring Start',
            test: async () => {
                const response = await axios.post(`${baseUrl}/api/signal-validation/monitoring/start/test-session`);
                return { success: response.data.status === 'success' || response.data.status === 'started', data: response.data };
            }
        },
        {
            name: 'Signal Monitoring Stop',
            test: async () => {
                const response = await axios.post(`${baseUrl}/api/signal-validation/monitoring/stop`);
                return { success: response.data.status === 'success', data: response.data };
            }
        }
    ];
    
    const results = [];
    
    for (const test of tests) {
        try {
            console.log(`⚡ Running: ${test.name}`);
            const result = await test.test();
            
            if (result.success) {
                console.log(`✅ ${test.name}: PASSED`);
                console.log(`   Data:`, JSON.stringify(result.data, null, 2));
            } else {
                console.log(`❌ ${test.name}: FAILED`);
                console.log(`   Data:`, JSON.stringify(result.data, null, 2));
            }
            
            results.push({ name: test.name, success: result.success, data: result.data });
            
        } catch (error) {
            console.log(`❌ ${test.name}: FAILED`);
            console.log(`   Error: ${error.message}`);
            results.push({ name: test.name, success: false, error: error.message });
        }
        
        console.log(''); // Empty line between tests
    }
    
    // Summary
    const passed = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;
    
    console.log('📊 Test Summary:');
    console.log(`   ✅ Passed: ${passed}`);
    console.log(`   ❌ Failed: ${failed}`);
    console.log(`   📝 Total: ${results.length}`);
    
    if (failed === 0) {
        console.log('\n🎉 All tests passed! LabJack integration is working correctly.');
    } else {
        console.log(`\n⚠️  ${failed} test(s) failed. Check the logs above for details.`);
        
        // Provide troubleshooting suggestions
        console.log('\n💡 Troubleshooting suggestions:');
        results.filter(r => !r.success).forEach(result => {
            switch (result.name) {
                case 'API Health Check':
                    console.log('   - Check if the backend server is running');
                    console.log('   - Verify the API URL is correct');
                    break;
                case 'LabJack Status Check':
                case 'LabJack Initialization':
                    console.log('   - Ensure LabJack hardware is connected');
                    console.log('   - Check LabJack drivers are installed');
                    console.log('   - Verify backend signal validation service is running');
                    break;
                case 'Signal Monitoring Start':
                case 'Signal Monitoring Stop':
                    console.log('   - Check LabJack is properly initialized');
                    console.log('   - Ensure no other applications are using the device');
                    break;
            }
        });
    }
    
    return results;
}

// Run the test if this file is executed directly
if (require.main === module) {
    testLabJackIntegration().catch(console.error);
}

module.exports = testLabJackIntegration;
```

## Quick Reference Commands

### Essential PowerShell Commands

```powershell
# Check LabJack device status
Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like "*LabJack*" }

# Test network LabJack
Test-NetConnection -ComputerName "192.168.1.207" -Port 502

# Check LabJack services
Get-Service | Where-Object { $_.Name -like "*LabJack*" }

# Restart USB services
Restart-Service -Name "LabJackUSB" -Force

# Scan for hardware changes
pnputil /scan-devices

# Check firewall rules
Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*LabJack*" }

# Test API endpoints
Invoke-RestMethod -Uri "http://localhost:8000/api/signal-validation/labjack/status"
```

### Batch File for Quick Diagnosis

```batch
@echo off
echo LabJack Quick Diagnostic Tool
echo =============================
echo.

echo 1. Checking USB devices...
powershell -Command "Get-WmiObject -Class Win32_USBDevice | Where-Object { $_.Description -like '*LabJack*' } | Select-Object Name, Status"
echo.

echo 2. Checking LabJack services...
powershell -Command "Get-Service | Where-Object { $_.Name -like '*LabJack*' } | Select-Object Name, Status"
echo.

echo 3. Testing network connectivity...
powershell -Command "Test-NetConnection -ComputerName '192.168.1.207' -Port 502 -WarningAction SilentlyContinue | Select-Object ComputerName, RemotePort, TcpTestSucceeded"
echo.

echo 4. Checking API connectivity...
powershell -Command "try { Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 5 | ConvertTo-Json } catch { Write-Host 'API not accessible' }"
echo.

echo Diagnostic completed.
pause
```

## Conclusion

This guide provides comprehensive Windows-specific diagnostic and troubleshooting procedures for LabJack device integration. Use the provided scripts and commands to identify and resolve connectivity issues systematically.

For additional support:
- LabJack Support: https://labjack.com/support
- Documentation: https://labjack.com/support/software/api
- Community Forums: https://labjack.com/forums

Remember to run diagnostic scripts as Administrator for full system access and accurate results.