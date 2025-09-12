# USB/IP (usbipd-win) Setup Guide

The USB/IP protocol allows sharing USB devices over the network. This is the recommended method for LabJack connectivity in WSL2 and containerized environments.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Device Management](#device-management)
4. [WSL2 Integration](#wsl2-integration)
5. [Docker Integration](#docker-integration)
6. [Automation](#automation)

## Installation

### Method 1: Windows Package Manager (Recommended)

```powershell
# Run as Administrator
winget install --id=dorssel.usbipd-win

# Verify installation
usbipd --version
```

### Method 2: GitHub Release

1. Download the latest MSI from [usbipd-win releases](https://github.com/dorssel/usbipd-win/releases)
2. Run the installer as Administrator
3. Restart your computer

### Method 3: Chocolatey

```powershell
# Install Chocolatey if not already installed
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

# Install usbipd-win
choco install usbipd-win
```

## Configuration

### Initial Setup

1. **Enable WSL2 Feature** (if not already enabled):
```powershell
# Run as Administrator
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

2. **Set WSL2 as default**:
```powershell
wsl --set-default-version 2
```

3. **Install Linux distribution** (if needed):
```powershell
wsl --install Ubuntu
```

### Service Configuration

The USB/IP service should start automatically. Verify it's running:

```powershell
# Check service status
Get-Service -Name usbipd

# Start service if stopped
Start-Service -Name usbipd

# Set to start automatically
Set-Service -Name usbipd -StartupType Automatic
```

## Device Management

### Listing USB Devices

```powershell
# List all USB devices
usbipd list

# Example output:
# BUSID  VID:PID    DEVICE                                          STATE
# 1-4    0cd5:0009  LabJack U3-LV                                   Not shared
# 2-1    046d:c52b  Logitech USB Input Device                       Not shared
```

![Screenshot placeholder: USB device list output]

### Identifying LabJack Devices

LabJack devices have specific Vendor IDs (VID):
- **0cd5**: LabJack Corporation
- Common PIDs:
  - 0009: U3-LV/U3-HV
  - 000A: U6/U6-Pro
  - 000B: UE9/UE9-Pro
  - 4004: T4
  - 4007: T7/T7-Pro

### Binding Devices

Before sharing, devices must be bound to usbipd:

```powershell
# Bind LabJack device (replace 1-4 with your BUSID)
usbipd bind --busid 1-4

# Verify binding
usbipd list
# State should show "Shared"
```

### Unbinding Devices

```powershell
# Unbind device
usbipd unbind --busid 1-4
```

## WSL2 Integration

### Attaching Devices to WSL

```powershell
# Attach LabJack to WSL (auto-selects default distribution)
usbipd attach --wsl --busid 1-4

# Attach to specific distribution
usbipd attach --wsl Ubuntu-20.04 --busid 1-4
```

### Verifying in WSL

```bash
# Check if device is visible in WSL
lsusb

# Look for LabJack specifically
lsusb | grep -i labjack

# Example output:
# Bus 001 Device 002: ID 0cd5:0009 LabJack U3-LV
```

### Detaching Devices

```powershell
# Detach from WSL
usbipd detach --busid 1-4
```

### Installing LabJack Software in WSL

```bash
# Update package list
sudo apt update

# Install required dependencies
sudo apt install -y build-essential libusb-1.0-0-dev

# Download and install LabJack Exodriver
cd /tmp
wget https://github.com/labjack/exodriver/archive/master.zip
unzip master.zip
cd exodriver-master
sudo ./install.sh

# Verify installation
ls /usr/local/lib/liblabjackusb*
```

## Docker Integration

### Docker Desktop Setup

1. **Enable WSL2 Backend** in Docker Desktop settings
2. **Share USB device** with WSL first
3. **Mount device** in container

### Running LabJack in Docker

```bash
# Create Dockerfile
cat > Dockerfile << EOF
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install LabJack Python library
RUN pip3 install labjack-ljm

WORKDIR /app
COPY . .

CMD ["python3", "test_labjack.py"]
EOF

# Build image
docker build -t labjack-app .

# Run with USB device access
docker run --rm -it \
  --device=/dev/bus/usb \
  -v /dev/bus/usb:/dev/bus/usb \
  labjack-app
```

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'
services:
  labjack-app:
    build: .
    devices:
      - "/dev/bus/usb:/dev/bus/usb"
    volumes:
      - "/dev/bus/usb:/dev/bus/usb"
    privileged: false
    user: root
```

## Automation

### PowerShell Script for Device Management

Create `manage-labjack.ps1`:

```powershell
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("list", "bind", "unbind", "attach", "detach", "status")]
    [string]$Action,
    
    [string]$BusId,
    [string]$Distribution = ""
)

function Find-LabJackDevice {
    $devices = usbipd list | Select-String "0cd5:"
    if ($devices) {
        $devices | ForEach-Object {
            $line = $_.Line
            if ($line -match "^(\S+)\s+0cd5:(\w+)\s+(.+?)\s+(.+)$") {
                [PSCustomObject]@{
                    BusId = $matches[1]
                    ProductId = $matches[2]
                    Description = $matches[3].Trim()
                    State = $matches[4].Trim()
                }
            }
        }
    }
}

switch ($Action) {
    "list" {
        Write-Host "LabJack Devices:" -ForegroundColor Green
        Find-LabJackDevice | Format-Table -AutoSize
    }
    
    "bind" {
        if (-not $BusId) {
            $devices = Find-LabJackDevice
            if ($devices.Count -eq 1) {
                $BusId = $devices[0].BusId
                Write-Host "Auto-detected LabJack at $BusId" -ForegroundColor Yellow
            } else {
                Write-Error "Multiple LabJack devices found. Please specify -BusId"
                return
            }
        }
        Write-Host "Binding device $BusId..." -ForegroundColor Blue
        usbipd bind --busid $BusId
    }
    
    "attach" {
        if (-not $BusId) {
            Write-Error "BusId required for attach operation"
            return
        }
        
        $cmd = "usbipd attach --wsl --busid $BusId"
        if ($Distribution) {
            $cmd += " $Distribution"
        }
        
        Write-Host "Attaching device $BusId to WSL..." -ForegroundColor Blue
        Invoke-Expression $cmd
    }
    
    "detach" {
        if (-not $BusId) {
            Write-Error "BusId required for detach operation"
            return
        }
        Write-Host "Detaching device $BusId..." -ForegroundColor Blue
        usbipd detach --busid $BusId
    }
    
    "status" {
        Write-Host "USB/IP Service Status:" -ForegroundColor Green
        Get-Service -Name usbipd
        Write-Host "`nLabJack Devices:" -ForegroundColor Green
        Find-LabJackDevice | Format-Table -AutoSize
    }
}
```

### Usage Examples

```powershell
# List all LabJack devices
.\manage-labjack.ps1 -Action list

# Bind first detected LabJack
.\manage-labjack.ps1 -Action bind

# Attach to WSL
.\manage-labjack.ps1 -Action attach -BusId 1-4

# Check status
.\manage-labjack.ps1 -Action status
```

### Batch Script for Quick Setup

Create `setup-labjack.bat`:

```batch
@echo off
echo LabJack USB Passthrough Quick Setup
echo ====================================

echo.
echo 1. Checking usbipd installation...
usbipd --version >nul 2>&1
if errorlevel 1 (
    echo usbipd-win not found. Installing...
    winget install --id=dorssel.usbipd-win
) else (
    echo usbipd-win is installed.
)

echo.
echo 2. Listing USB devices...
usbipd list

echo.
echo 3. Looking for LabJack devices...
usbipd list | findstr "0cd5:"

echo.
echo Setup complete. Use 'usbipd bind --busid X-Y' to bind your LabJack device.
pause
```

### Linux Helper Script

Create `labjack-helper.sh` for WSL:

```bash
#!/bin/bash

check_device() {
    if lsusb | grep -q "0cd5:"; then
        echo "✓ LabJack device detected"
        lsusb | grep "0cd5:"
        return 0
    else
        echo "✗ No LabJack device found"
        return 1
    fi
}

install_drivers() {
    echo "Installing LabJack drivers..."
    
    # Install dependencies
    sudo apt update
    sudo apt install -y build-essential libusb-1.0-0-dev wget unzip
    
    # Download and install Exodriver
    cd /tmp
    wget https://github.com/labjack/exodriver/archive/master.zip
    unzip -o master.zip
    cd exodriver-master
    sudo ./install.sh
    
    echo "Drivers installed successfully"
}

test_connection() {
    echo "Testing LabJack connection..."
    
    if command -v python3 &> /dev/null; then
        python3 -c "
import sys
try:
    import u3
    d = u3.U3()
    print('✓ Successfully connected to U3')
    d.close()
except Exception as e:
    print('✗ Connection failed:', str(e))
    sys.exit(1)
"
    else
        echo "Python3 not found. Install python3 to test connection."
    fi
}

case "$1" in
    "check")
        check_device
        ;;
    "install")
        install_drivers
        ;;
    "test")
        test_connection
        ;;
    *)
        echo "Usage: $0 {check|install|test}"
        echo "  check   - Check if LabJack device is detected"
        echo "  install - Install LabJack drivers"
        echo "  test    - Test connection to device"
        ;;
esac
```

Make it executable:
```bash
chmod +x labjack-helper.sh
```

## Next Steps

- Review [Alternative Methods](./02-alternative-methods.md) for other connection approaches
- Check [Troubleshooting Guide](./03-troubleshooting.md) if you encounter issues
- See [Performance Optimization](./04-performance.md) for speed improvements