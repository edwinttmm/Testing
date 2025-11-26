# LabJack LJM Software Installation Guide (WSL/Linux)

**Date:** 2025-11-17
**Platform:** WSL2 / Ubuntu Linux
**Target:** LabJack LJM Software (Python bindings)
**Status:** Step-by-step installation guide

---

## Overview

This guide walks through installing the LabJack LJM (LabJack Modbus) software on WSL/Linux for use with the AI Model Validation Platform's Hardware-in-Loop (HIL) testing system.

---

## Prerequisites

### 1. System Requirements

```bash
# Check your system architecture (should show x86_64)
uname -m

# Check WSL version (should be WSL2 for USB support)
wsl --version  # Run in Windows PowerShell

# Check Ubuntu version
lsb_release -a
```

**Required:**
- WSL2 (for USB device access)
- Ubuntu 20.04+ or Debian-based distro
- x86_64 architecture
- USB access configured (see USB Setup section)

### 2. Install Build Dependencies

```bash
# Update package lists
sudo apt-get update

# Install required dependencies
sudo apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    libusb-1.0-0-dev \
    udev \
    wget \
    curl
```

---

## Installation Steps

### Step 1: Download the Correct .deb Package

**IMPORTANT:** The LabJack download page shows an HTML wrapper. You need the actual binary .deb file.

#### Option A: Direct Download (Recommended)

```bash
# Navigate to Downloads directory
cd ~/Downloads

# Download the latest LJM installer (as of March 2024)
# NOTE: Check https://labjack.com/pages/support for the latest version
curl -L -o labjack_ljm.deb \
  'https://labjack.com/sites/default/files/software/2024/03/08/labjack_ljm_software_2024_03_08_x86_64.deb'

# Verify it's a real Debian package (not HTML)
file labjack_ljm.deb

# Expected output:
# labjack_ljm.deb: Debian binary package (format 2.0)

# Check file size (should be ~20-30 MB, not a few KB)
ls -lh labjack_ljm.deb
```

**If you see "HTML document":** You downloaded the web page instead of the .deb file.

#### Option B: Manual Browser Download

1. **Visit:** https://labjack.com/pages/support
2. **Navigate to:** Software → LJM Software → Linux x64
3. **Find the link** that ends in `.deb` (NOT the page link)
4. **Right-click** → "Save link as..." or "Copy link address"
5. **Download to** `~/Downloads/` or `/mnt/c/Users/[YourUser]/Downloads/`

### Step 2: Verify the Download

```bash
cd ~/Downloads

# Method 1: Check file type
file labjack_ljm.deb
# Should output: "Debian binary package (format 2.0)"

# Method 2: Check file size
ls -lh labjack_ljm.deb
# Should be 20-30 MB, NOT a few KB

# Method 3: Check with dpkg (doesn't install)
dpkg -I labjack_ljm.deb
# Should show package info, NOT "error: not a Debian format archive"
```

**If verification fails:**
```bash
# Remove the bad file
rm labjack_ljm.deb

# Try again with a direct URL from LabJack's support page
# Example (update date/version as needed):
wget https://labjack.com/sites/default/files/software/2024/03/08/labjack_ljm_software_2024_03_08_x86_64.deb \
  -O labjack_ljm.deb
```

### Step 3: Install the .deb Package

```bash
cd ~/Downloads

# Install the package
sudo dpkg -i labjack_ljm.deb

# If you see dependency errors, run:
sudo apt-get -f install

# This will automatically resolve and install missing dependencies
```

**Expected output:**
```
Selecting previously unselected package labjack-ljm.
(Reading database ... 123456 files and directories currently installed.)
Preparing to unpack labjack_ljm.deb ...
Unpacking labjack-ljm (1.21.0) ...
Setting up labjack-ljm (1.21.0) ...
```

### Step 4: Verify System-Level Installation

```bash
# Check if libraries are installed
ls -la /usr/local/lib | grep LabJack

# Expected output:
# libLabJackM.so
# libLabJackM.so.1
# libLabJackM.so.1.21.0

# Check if headers are installed
ls -la /usr/local/include | grep LabJack

# Expected output:
# LabJackM.h

# Verify library can be loaded
ldconfig -p | grep LabJack

# Expected output (shows library path):
# libLabJackM.so.1 (libc6,x86-64) => /usr/local/lib/libLabJackM.so.1
```

### Step 5: Install Python Bindings

```bash
# Activate your backend virtual environment
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate

# Install LabJack Python package
pip install labjack-ljm

# Verify installation
pip show labjack-ljm

# Expected output:
# Name: labjack-ljm
# Version: 1.21.0
# Summary: Python wrapper for the LabJack LJM library
# ...
```

### Step 6: Configure USB Permissions (Critical for WSL)

```bash
# Add udev rules for LabJack devices
sudo tee /etc/udev/rules.d/99-labjack.rules > /dev/null << 'EOF'
# LabJack U3
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="0003", MODE="0666"

# LabJack U6
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="0006", MODE="0666"

# LabJack UE9
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="0009", MODE="0666"

# LabJack T4
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="4004", MODE="0666"

# LabJack T7 and T7-Pro
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="7004", MODE="0666"

# LabJack T8
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="8004", MODE="0666"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## WSL2 USB Device Setup

**IMPORTANT:** WSL2 requires USB/IP for device access.

### Option 1: USB/IP Bridge (Recommended for WSL2)

```bash
# In WSL2, install USB/IP tools
sudo apt-get install -y linux-tools-generic hwdata

# In Windows PowerShell (as Administrator):
# Install usbipd-win from https://github.com/dorssel/usbipd-win/releases

# List USB devices (in Windows PowerShell):
usbipd list

# Find your LabJack device (e.g., "LabJack U3" or similar)
# Note the BUSID (e.g., 2-1)

# Attach device to WSL (in Windows PowerShell as Admin):
usbipd bind --busid 2-1
usbipd attach --wsl --busid 2-1

# Verify in WSL:
lsusb | grep LabJack
```

### Option 2: Network Connection (Alternative)

If USB passthrough is problematic, configure LabJack for Ethernet/network access:

```bash
# In your backend .env file, configure network connection:
LABJACK_CONNECTION_TYPE=ethernet
LABJACK_IDENTIFIER=192.168.1.207  # Your LabJack's IP
```

---

## Verification Tests

### Test 1: Basic Import

```bash
# Activate backend venv
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate

# Test Python import
python3 << 'EOF'
try:
    from labjack import ljm
    print("✅ LabJack LJM Python module imported successfully")
    print(f"   LJM Library version: {ljm.constants.LIBRARY_VERSION}")
except Exception as e:
    print(f"❌ Import failed: {e}")
EOF
```

**Expected output:**
```
✅ LabJack LJM Python module imported successfully
   LJM Library version: 1.2100
```

### Test 2: Device Connection

```bash
# Run connection test
python3 << 'EOF'
from labjack import ljm

print("🔍 Scanning for LabJack devices...")
try:
    # Try to open ANY LabJack on ANY connection type
    handle = ljm.openS("ANY", "ANY", "ANY")

    info = ljm.getHandleInfo(handle)
    print(f"✅ Connected to LabJack!")
    print(f"   Device Type: {info[0]}")
    print(f"   Connection Type: {info[1]}")
    print(f"   Serial Number: {info[2]}")
    print(f"   IP Address: {info[3]}")
    print(f"   Port: {info[4]}")
    print(f"   Max Bytes/MB: {info[5]}")

    # Read firmware version
    firmware = ljm.eReadName(handle, "FIRMWARE_VERSION")
    print(f"   Firmware Version: {firmware}")

    ljm.close(handle)
    print("✅ Connection test passed!")

except ljm.LJMError as e:
    print(f"❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("  1. Check USB connection (lsusb | grep LabJack)")
    print("  2. Verify udev rules (/etc/udev/rules.d/99-labjack.rules)")
    print("  3. Check WSL USB passthrough (usbipd list in Windows)")
    print("  4. Try network connection if USB fails")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
EOF
```

### Test 3: Analog Input Read (HIL Test)

```bash
# Test analog input reading (used for detection events)
python3 << 'EOF'
from labjack import ljm
import time

try:
    handle = ljm.openS("ANY", "ANY", "ANY")
    print("✅ Connected to LabJack")

    # Read AIN0 (analog input 0) - used for detection signals
    channel = "AIN0"
    print(f"\n🔍 Reading {channel} for 5 seconds...")
    print("   (Connect a signal source to test detection)")

    for i in range(5):
        value = ljm.eReadName(handle, channel)
        print(f"   [{i+1}/5] {channel} = {value:.3f} V")
        time.sleep(1)

    ljm.close(handle)
    print("\n✅ Analog input test completed!")

except ljm.LJMError as e:
    print(f"❌ LabJack error: {e}")
except Exception as e:
    print(f"❌ Test failed: {e}")
EOF
```

---

## Integration with Backend

### Test Backend Connection

```bash
# Navigate to backend
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate

# Run LabJack status check endpoint
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')

from services.labjack_service import LabJackService

try:
    service = LabJackService()
    status = service.get_status()

    print("✅ Backend LabJack integration test:")
    print(f"   Connected: {status.get('is_connected', False)}")
    print(f"   Status: {status.get('connection_status', 'Unknown')}")
    print(f"   Device Info: {status.get('device_info', {})}")

    if status.get('is_connected'):
        print("\n🎉 LabJack is ready for HIL testing!")
    else:
        print("\n⚠️ LabJack not connected - check hardware connection")

except Exception as e:
    print(f"❌ Backend integration test failed: {e}")
    import traceback
    traceback.print_exc()
EOF
```

---

## Common Issues and Solutions

### Issue 1: "Cannot load library"

**Error:**
```
OSError: Cannot load library libLabJackM.so
```

**Solutions:**
```bash
# Check if library exists
ls -la /usr/local/lib/libLabJackM.so

# If missing, reinstall .deb package
sudo dpkg -i ~/Downloads/labjack_ljm.deb

# Update library cache
sudo ldconfig

# Verify library path
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ldconfig -p | grep LabJack
```

### Issue 2: "HTML document" instead of .deb

**Error:**
```
dpkg-deb: error: 'labjack_ljm.deb' is not a Debian format archive
file labjack_ljm.deb
# Output: HTML document, ASCII text
```

**Solution:**
```bash
# You downloaded the web page, not the file
rm labjack_ljm.deb

# Use direct download link
curl -L -o labjack_ljm.deb \
  'https://labjack.com/sites/default/files/software/2024/03/08/labjack_ljm_software_2024_03_08_x86_64.deb'

# Or visit support page and right-click → "Save link as..."
```

### Issue 3: USB Device Not Found

**Error:**
```
LJMError: LJME_DEVICE_NOT_FOUND
```

**Solutions:**
```bash
# Check USB connection (WSL)
lsusb | grep LabJack
# Should show: Bus 002 Device 003: ID 0cd5:XXXX LabJack Corporation

# If not visible in WSL, attach from Windows (PowerShell as Admin):
usbipd list
usbipd attach --wsl --busid X-X

# Check udev rules
cat /etc/udev/rules.d/99-labjack.rules
sudo udevadm control --reload-rules

# Check permissions
ls -la /dev/bus/usb/*/*  # Should show mode 0666 for LabJack
```

### Issue 4: Permission Denied

**Error:**
```
LJMError: LJME_PERMISSION_DENIED
```

**Solutions:**
```bash
# Add user to dialout/plugdev group
sudo usermod -a -G dialout,plugdev $USER

# Re-login or run:
newgrp dialout

# Reapply udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Reboot WSL if needed (in Windows PowerShell):
wsl --shutdown
# Then relaunch WSL
```

---

## Next Steps

After successful installation:

1. **Start Backend Server:**
   ```bash
   cd /home/rigade/Testing/ai-model-validation-platform/backend
   source venv/bin/activate
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Check LabJack Status:**
   - Navigate to: http://localhost:3000/hil-test
   - Look for "LabJack Status: Connected" indicator
   - Green checkmark should appear if connection successful

3. **Run HIL Test:**
   - Select test project
   - Load validated videos
   - Click "Load Ground Truth"
   - Click "Start Test"
   - Verify detections appear (should see counts > 0 now after type fix)

---

## Verification Checklist

- [ ] Downloaded actual .deb package (not HTML)
- [ ] File shows "Debian binary package" type
- [ ] Installed with `sudo dpkg -i`
- [ ] Libraries visible in `/usr/local/lib`
- [ ] Python package installed (`pip show labjack-ljm`)
- [ ] Python import works (`from labjack import ljm`)
- [ ] USB device visible (`lsusb | grep LabJack`)
- [ ] udev rules configured
- [ ] Connection test passes (device detected)
- [ ] Analog input reads successfully
- [ ] Backend integration test passes
- [ ] HIL test page shows "Connected" status

---

## Support Resources

- **LabJack Official Support:** https://labjack.com/pages/support
- **LJM User's Guide:** https://labjack.com/pages/support?doc=/software-driver/ljm-users-guide/
- **WSL USB/IP Guide:** https://github.com/dorssel/usbipd-win
- **Project Issues:** Report in GitHub Issues

---

**Installation Guide Version:** 1.0
**Last Updated:** 2025-11-17
**Tested On:** WSL2 Ubuntu 22.04, LabJack T7
