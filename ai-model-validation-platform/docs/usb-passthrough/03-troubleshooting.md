# USB Passthrough Troubleshooting Guide

This guide covers common issues encountered when setting up USB passthrough for LabJack devices and their solutions.

## Table of Contents

1. [Common Error Messages](#common-error-messages)
2. [Device Detection Issues](#device-detection-issues)
3. [Connection Problems](#connection-problems)
4. [Performance Issues](#performance-issues)
5. [WSL2 Specific Issues](#wsl2-specific-issues)
6. [Docker Integration Issues](#docker-integration-issues)
7. [Diagnostic Tools](#diagnostic-tools)
8. [Advanced Troubleshooting](#advanced-troubleshooting)

## Common Error Messages

### "Access is denied" when running usbipd commands

**Error**:
```
usbipd: error: Access is denied.
```

**Cause**: Insufficient privileges

**Solution**:
```powershell
# Run PowerShell as Administrator
# Check if running as admin
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Please run as Administrator" -ForegroundColor Red
    exit 1
}

# Try the command again
usbipd list
```

### "No such device" when attaching to WSL

**Error**:
```
usbipd: error: The specified device was not found; it may have been disconnected.
```

**Causes & Solutions**:

1. **Device disconnected**:
   ```powershell
   # Check if device is still connected
   usbipd list
   # If not listed, reconnect the device
   ```

2. **Bus ID changed**:
   ```powershell
   # Bus IDs can change when devices are reconnected
   usbipd list | findstr "LabJack"
   # Use the new Bus ID
   ```

3. **Device not bound**:
   ```powershell
   # Bind the device first
   usbipd bind --busid 1-4
   usbipd attach --wsl --busid 1-4
   ```

### "WSL 2 distributions not found"

**Error**:
```
usbipd: error: No WSL 2 distributions found.
```

**Solution**:
```powershell
# Check WSL installations
wsl --list --verbose

# If no WSL installed, install Ubuntu
wsl --install Ubuntu

# If WSL version is 1, convert to version 2
wsl --set-version Ubuntu 2
wsl --set-default-version 2
```

### "Failed to attach device" in WSL

**Error**:
```
usbip: error: Attach Request for 1-4 failed - Invalid argument
```

**Causes & Solutions**:

1. **Linux kernel modules not loaded**:
   ```bash
   # Load required modules
   sudo modprobe usbip-core
   sudo modprobe vhci-hcd
   
   # Verify modules loaded
   lsmod | grep usbip
   ```

2. **Insufficient permissions**:
   ```bash
   # Add user to dialout group for device access
   sudo usermod -a -G dialout $USER
   sudo usermod -a -G plugdev $USER
   
   # Logout and login again
   ```

3. **Conflicting drivers**:
   ```bash
   # Check for conflicting drivers
   lsusb -v | grep -i labjack
   
   # Remove conflicting drivers if found
   sudo rmmod ftdi_sio
   ```

## Device Detection Issues

### LabJack not appearing in device list

**Check USB connection**:
```powershell
# List all USB devices including hidden ones
Get-WmiObject Win32_PnPEntity | Where-Object { $_.Caption -match "LabJack" }

# Check Device Manager
devmgmt.msc
```

**Check device drivers**:
```powershell
# Download and install LabJack Windows drivers
# https://labjack.com/support/software/installers
```

**Verify device functionality**:
```powershell
# Use LabJack's LJControlPanel to test
# Download from https://labjack.com/support/software/applications/ud/ljcontrolpanel
```

### Device detected but not bindable

**Error**: Device appears in `usbipd list` but cannot be bound

**Solution**:
```powershell
# Check if device is in use by another application
Get-Process | Where-Object { $_.ProcessName -match "LabJack" }

# Stop LabJack applications
Stop-Process -Name "LJControlPanel" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "U3_Test" -Force -ErrorAction SilentlyContinue

# Try binding again
usbipd bind --busid 1-4
```

### Multiple LabJack devices conflict

**Scenario**: Multiple LabJack devices causing interference

**Solution**:
```powershell
# List all LabJack devices
usbipd list | findstr "0cd5:"

# Bind and attach devices one at a time
usbipd bind --busid 1-4    # First device
usbipd bind --busid 2-1    # Second device

# Attach to different WSL instances if needed
usbipd attach --wsl Ubuntu-20.04 --busid 1-4
usbipd attach --wsl Ubuntu-22.04 --busid 2-1
```

## Connection Problems

### Intermittent connection drops

**Symptoms**: Device disconnects randomly during operation

**Solutions**:

1. **Disable USB selective suspend**:
   ```powershell
   # Open Power Options
   powercfg.cpl
   # Advanced settings > USB settings > USB selective suspend setting > Disabled
   ```

2. **Update USB drivers**:
   ```powershell
   # Update via Device Manager
   Get-WindowsDriver -Online | Where-Object { $_.ClassName -eq "USB" } | Update-Driver
   ```

3. **Check power management**:
   ```powershell
   # Disable power management for USB hub
   Get-WmiObject Win32_USBHub | ForEach-Object {
       $_.SetPowerManagement($false)
   }
   ```

### Slow data transfer rates

**Check USB version**:
```bash
# In WSL, check USB connection speed
lsusb -v | grep -A 5 -B 5 "LabJack"
```

**Optimize buffer sizes**:
```python
# In Python applications
import u3

# Increase buffer size for better performance
device = u3.U3()
device.debug = False  # Disable debug output
device.configU3(LocalID=1, TimerCounterPinOffset=4, DAC1Enable=0)
```

### Authentication/permission errors in container

**Error**: Permission denied when accessing device in Docker

**Solution**:
```yaml
# docker-compose.yml
version: '3.8'
services:
  labjack-app:
    image: your-app:latest
    devices:
      - "/dev/bus/usb:/dev/bus/usb"
    privileged: false
    user: root
    environment:
      - UDEV=1
    volumes:
      - "/run/udev:/run/udev:ro"
```

**Alternative with custom user**:
```dockerfile
# Dockerfile
FROM ubuntu:22.04

# Create user with proper permissions
RUN groupadd -g 1000 labjack && \
    useradd -u 1000 -g labjack -G dialout,plugdev labjack

# Install udev rules
COPY 99-labjack.rules /etc/udev/rules.d/
RUN udevadm control --reload-rules

USER labjack
```

## Performance Issues

### High latency readings

**Optimize LabJack settings**:
```python
import u3

device = u3.U3()

# Configure for speed
device.configU3(
    LocalID=1,
    TimerCounterPinOffset=4,
    DAC1Enable=0
)

# Use streaming mode for high-speed data
device.streamConfig(
    NumChannels=4,
    ChannelNumbers=[0, 1, 2, 3],
    ChannelOptions=[0, 0, 0, 0],
    SettlingFactor=0,
    ResolutionIndex=0,
    SampleFrequency=1000
)
```

### CPU usage spikes

**Monitor resource usage**:
```bash
# Check CPU usage by usbipd
top -p $(pgrep usbipd)

# Monitor USB traffic
sudo usbmon
```

**Optimize polling frequency**:
```python
import time

# Reduce polling frequency if high-speed not required
while True:
    data = device.getAIN(0)
    process_data(data)
    time.sleep(0.1)  # 10Hz instead of maximum speed
```

### Memory leaks

**Check for memory leaks**:
```bash
# Monitor memory usage over time
watch -n 5 'ps aux | grep labjack'

# Use valgrind for C applications
valgrind --leak-check=full ./your_labjack_app
```

**Fix common Python leaks**:
```python
import u3

# Properly close connections
try:
    device = u3.U3()
    # Your code here
finally:
    device.close()

# Use context manager
with u3.U3() as device:
    voltage = device.getAIN(0)
```

## WSL2 Specific Issues

### WSL kernel doesn't support USB

**Check kernel version**:
```bash
uname -r
# Should be 5.4.72+ or higher
```

**Update WSL kernel**:
```powershell
# Download latest WSL2 kernel update
# https://aka.ms/wsl2kernel

# Update WSL
wsl --update
```

### USB device not visible in WSL after attachment

**Check usbip modules**:
```bash
# Load required modules
sudo modprobe usbip-core
sudo modprobe usbip-vudc  
sudo modprobe vhci-hcd

# Check if modules loaded
lsmod | grep -E "(usbip|vhci)"
```

**Restart usbip daemon**:
```bash
# Kill existing processes
sudo pkill usbipd

# Restart WSL instance
# From PowerShell
wsl --shutdown
wsl
```

### WSL networking issues preventing attachment

**Reset WSL networking**:
```powershell
# Reset WSL network adapter
wsl --shutdown
Get-NetAdapter "vEthernet (WSL)" | Restart-NetAdapter
wsl
```

**Check firewall settings**:
```powershell
# Allow WSL through firewall
New-NetFirewallRule -DisplayName "WSL" -Direction Inbound -Protocol TCP -Action Allow
```

## Docker Integration Issues

### Device not accessible in container

**Check device permissions**:
```bash
# In container
ls -la /dev/bus/usb/
# Should show proper permissions

# Check if device node exists
find /dev -name "*labjack*" -o -name "ttyUSB*"
```

**Fix udev rules**:
```bash
# Create udev rule file
cat > /etc/udev/rules.d/99-labjack.rules << EOF
# LabJack U3
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="0009", MODE="0666", GROUP="dialout"
# LabJack U6  
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="000a", MODE="0666", GROUP="dialout"
# LabJack UE9
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="000b", MODE="0666", GROUP="dialout"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Container cannot find LabJack libraries

**Install libraries in container**:
```dockerfile
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    libusb-1.0-0-dev \
    python3 \
    python3-pip \
    wget \
    unzip \
    build-essential

# Install LabJack Exodriver
RUN cd /tmp && \
    wget https://github.com/labjack/exodriver/archive/master.zip && \
    unzip master.zip && \
    cd exodriver-master && \
    ./install.sh

# Install Python library
RUN pip3 install u3

# Verify installation
RUN python3 -c "import u3; print('LabJack library installed')"
```

## Diagnostic Tools

### PowerShell Diagnostic Script

Create `diagnose-usb-passthrough.ps1`:

```powershell
#Requires -RunAsAdministrator

Write-Host "LabJack USB Passthrough Diagnostics" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green
Write-Host ""

# Check Windows version
Write-Host "1. Checking Windows Version..." -ForegroundColor Yellow
$winVersion = (Get-ItemProperty "HKLM:SOFTWARE\Microsoft\Windows NT\CurrentVersion").ReleaseId
$buildNumber = (Get-ItemProperty "HKLM:SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuild
Write-Host "   Windows Release: $winVersion (Build $buildNumber)"

if ([int]$buildNumber -lt 19041) {
    Write-Host "   WARNING: Windows 10 build 19041+ required for WSL2" -ForegroundColor Red
}

# Check WSL installation
Write-Host "`n2. Checking WSL..." -ForegroundColor Yellow
try {
    $wslVersion = wsl --version 2>&1
    if ($wslVersion -match "WSL version") {
        Write-Host "   WSL2 installed: Yes"
        wsl --list --verbose
    } else {
        Write-Host "   WSL2 installed: No" -ForegroundColor Red
        Write-Host "   Install with: wsl --install"
    }
} catch {
    Write-Host "   WSL not found" -ForegroundColor Red
}

# Check usbipd installation
Write-Host "`n3. Checking usbipd-win..." -ForegroundColor Yellow
try {
    $usbipd = usbipd --version 2>&1
    Write-Host "   usbipd-win version: $usbipd"
} catch {
    Write-Host "   usbipd-win not installed" -ForegroundColor Red
    Write-Host "   Install with: winget install usbipd"
}

# Check USB devices
Write-Host "`n4. Checking USB devices..." -ForegroundColor Yellow
try {
    $devices = usbipd list 2>&1
    $labJackDevices = $devices | Select-String "0cd5:"
    
    if ($labJackDevices) {
        Write-Host "   LabJack devices found:"
        $labJackDevices | ForEach-Object { Write-Host "   $_" -ForegroundColor Green }
    } else {
        Write-Host "   No LabJack devices detected" -ForegroundColor Red
        Write-Host "   Check physical USB connection and Windows drivers"
    }
} catch {
    Write-Host "   Cannot list USB devices" -ForegroundColor Red
}

# Check services
Write-Host "`n5. Checking services..." -ForegroundColor Yellow
$service = Get-Service -Name "usbipd" -ErrorAction SilentlyContinue
if ($service) {
    Write-Host "   usbipd service: $($service.Status)"
    if ($service.Status -ne "Running") {
        Write-Host "   Starting service..."
        Start-Service -Name "usbipd"
    }
} else {
    Write-Host "   usbipd service not found" -ForegroundColor Red
}

# Check firewall
Write-Host "`n6. Checking Windows Firewall..." -ForegroundColor Yellow
$firewallRules = Get-NetFirewallRule | Where-Object { $_.DisplayName -match "WSL" }
if ($firewallRules) {
    Write-Host "   WSL firewall rules: Found"
} else {
    Write-Host "   WSL firewall rules: Not found" -ForegroundColor Yellow
    Write-Host "   Consider adding rules if having connection issues"
}

# Check Hyper-V
Write-Host "`n7. Checking Hyper-V..." -ForegroundColor Yellow
$hyperv = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
if ($hyperv.State -eq "Enabled") {
    Write-Host "   Hyper-V: Enabled"
} else {
    Write-Host "   Hyper-V: Disabled" -ForegroundColor Yellow
    Write-Host "   WSL2 requires Hyper-V or Virtual Machine Platform"
}

Write-Host "`n8. Recommendations:" -ForegroundColor Green
Write-Host "   - Ensure LabJack is connected and drivers installed"
Write-Host "   - Run 'usbipd bind --busid X-Y' to bind device"  
Write-Host "   - Run 'usbipd attach --wsl --busid X-Y' to attach"
Write-Host "   - In WSL: run 'lsusb' to verify device visibility"

Write-Host "`nDiagnostics complete!" -ForegroundColor Green
```

### Linux Diagnostic Script

Create `diagnose-labjack.sh`:

```bash
#!/bin/bash

echo "LabJack Device Diagnostics (Linux/WSL)"
echo "====================================="
echo ""

# Check if running in WSL
echo "1. Environment Check..."
if grep -qi microsoft /proc/version; then
    echo "   Running in WSL: Yes"
    echo "   WSL Version: $(cat /proc/version)"
else
    echo "   Running in WSL: No"
    echo "   Running on native Linux"
fi

# Check kernel modules
echo ""
echo "2. Kernel Modules..."
REQUIRED_MODULES=("usbip_core" "vhci_hcd" "usbip_host")

for module in "${REQUIRED_MODULES[@]}"; do
    if lsmod | grep -q "$module"; then
        echo "   ✓ $module: loaded"
    else
        echo "   ✗ $module: not loaded"
        echo "     Load with: sudo modprobe $module"
    fi
done

# Check USB devices
echo ""
echo "3. USB Device Detection..."
if command -v lsusb >/dev/null 2>&1; then
    echo "   USB devices:"
    lsusb | while IFS= read -r line; do
        if echo "$line" | grep -qi "0cd5:"; then
            echo "   ✓ LabJack found: $line"
        else
            echo "     $line"
        fi
    done
    
    # Check specifically for LabJack
    LABJACK_COUNT=$(lsusb | grep -c "0cd5:")
    if [ "$LABJACK_COUNT" -eq 0 ]; then
        echo "   ✗ No LabJack devices detected"
    else
        echo "   ✓ Found $LABJACK_COUNT LabJack device(s)"
    fi
else
    echo "   ✗ lsusb not available"
    echo "     Install with: sudo apt install usbutils"
fi

# Check permissions
echo ""
echo "4. User Permissions..."
GROUPS=("dialout" "plugdev")
for group in "${GROUPS[@]}"; do
    if groups | grep -q "$group"; then
        echo "   ✓ User in $group group"
    else
        echo "   ✗ User not in $group group"
        echo "     Add with: sudo usermod -a -G $group $USER"
    fi
done

# Check LabJack software
echo ""
echo "5. LabJack Software..."

# Check for Exodriver
if [ -f "/usr/local/lib/liblabjackusb.so" ]; then
    echo "   ✓ Exodriver installed"
else
    echo "   ✗ Exodriver not found"
    echo "     Install from: https://github.com/labjack/exodriver"
fi

# Check Python library
if python3 -c "import u3" 2>/dev/null; then
    echo "   ✓ Python u3 library available"
else
    echo "   ✗ Python u3 library not found"
    echo "     Install with: pip3 install u3"
fi

# Test device access
echo ""
echo "6. Device Access Test..."
if python3 -c "
import sys
try:
    import u3
    device = u3.U3()
    print('   ✓ Successfully connected to U3')
    device.close()
except ImportError:
    print('   ✗ u3 library not available')
    sys.exit(1)
except Exception as e:
    print(f'   ✗ Connection failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
    echo "   Device test passed!"
else
    echo "   Device test failed"
fi

# System information
echo ""
echo "7. System Information..."
echo "   Kernel: $(uname -r)"
echo "   Distribution: $(lsb_release -d 2>/dev/null | cut -f2 || echo 'Unknown')"
echo "   Architecture: $(uname -m)"

echo ""
echo "Diagnostics complete!"
```

## Advanced Troubleshooting

### Network Packet Analysis

Use Wireshark to analyze USB/IP traffic:

```bash
# Install Wireshark
sudo apt install wireshark

# Capture USB/IP packets
sudo wireshark -i any -f "tcp port 3240"
```

### USB Protocol Analysis

Monitor USB traffic with usbmon:

```bash
# Enable usbmon
sudo modprobe usbmon

# Monitor USB bus
sudo cat /sys/kernel/debug/usb/usbmon/1u

# Or use tcpdump
sudo tcpdump -i usbmon1 -w usb_capture.pcap
```

### Registry Analysis (Windows)

Check USB-related registry keys:

```powershell
# Check USB storage policy
Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR" -Name "Start"

# Check device installation restrictions
Get-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions"

# List all USB devices
Get-ChildItem -Path "HKLM:\SYSTEM\CurrentControlSet\Enum\USB" -Recurse
```

### Event Log Analysis

Monitor Windows event logs for USB-related errors:

```powershell
# Check System event log
Get-WinEvent -FilterHashtable @{LogName='System'; ID=1001,1002,1003} | Select-Object TimeCreated,Id,LevelDisplayName,Message

# Check USB-related events
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-USB*'}
```

### Performance Profiling

Profile LabJack application performance:

```python
import cProfile
import u3
import time

def profile_labjack_operations():
    device = u3.U3()
    
    # Profile analog input reads
    start_time = time.time()
    for i in range(1000):
        voltage = device.getAIN(0)
    end_time = time.time()
    
    print(f"1000 analog reads took {end_time - start_time:.2f} seconds")
    print(f"Rate: {1000/(end_time - start_time):.2f} reads/second")
    
    device.close()

# Run with profiling
cProfile.run('profile_labjack_operations()')
```

## Next Steps

- Review [Performance Optimization](./04-performance.md) for speed improvements
- Check [Security Considerations](./05-security.md) for best practices
- See [Validation Procedures](./06-validation.md) for testing methods