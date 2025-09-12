# LabJack Hardware Setup Guide for Windows/WSL Environment

## Overview

This guide provides comprehensive instructions for connecting LabJack hardware to your HIL testing platform running in WSL2. Your backend runs in WSL2 (Ubuntu on Windows) while the LabJack device is connected to Windows, requiring bridge solutions for communication.

## Current Architecture

```
Windows PC
├── LabJack Hardware (USB/Ethernet connected)
├── Windows Host System
└── WSL2 (Ubuntu)
    └── AI Model Validation Backend (Python FastAPI)
```

## Connection Methods

### Method 1: USB/IP Bridge (Recommended) ⭐

The USB/IP bridge method provides direct hardware access with full LJM library support and best performance.

#### Prerequisites
- Windows 10/11 with WSL2 enabled
- Administrator privileges on Windows
- LabJack device connected via USB

#### Installation Steps

**Step 1: Install usbipd-win on Windows**
```powershell
# Open PowerShell as Administrator
winget install usbipd-win

# Alternative: Download from GitHub
# https://github.com/dorssel/usbipd-win/releases
```

**Step 2: Install USB/IP tools in WSL**
```bash
# In WSL terminal
sudo apt update
sudo apt install linux-tools-virtual hwdata
sudo update-alternatives --install /usr/local/bin/usbip usbip "$(ls /usr/lib/linux-tools/*/usbip | tail -n1)" 20
```

**Step 3: Find and Bind LabJack Device**
```powershell
# In Windows PowerShell as Administrator

# List all USB devices
usbipd list

# Look for LabJack device, note the BUSID (e.g., 2-1)
# LabJack devices typically show as "LabJack" or "Meilhaus Electronic"

# Bind the LabJack device (replace 2-1 with your BUSID)
usbipd bind --busid 2-1

# Verify binding
usbipd list
# Should show "Shared" in State column
```

**Step 4: Attach Device to WSL**
```powershell
# Attach LabJack to WSL (replace 2-1 with your BUSID)
usbipd attach --wsl --busid 2-1

# Verify attachment
usbipd list
# Should show "Attached" in State column
```

**Step 5: Verify in WSL**
```bash
# In WSL terminal
lsusb
# Should show LabJack device

# Check if device is accessible
ls -la /dev/bus/usb/
```

#### Automation Script

Save this as `setup-labjack-usbip.ps1`:

```powershell
# LabJack USB/IP Setup Script
# Run as Administrator

Write-Host "LabJack USB/IP Bridge Setup" -ForegroundColor Green

# Check if running as Administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    exit 1
}

# Install usbipd-win if not present
Write-Host "Checking for usbipd-win..." -ForegroundColor Yellow
$usbipd = Get-Command usbipd -ErrorAction SilentlyContinue
if (-not $usbipd) {
    Write-Host "Installing usbipd-win..." -ForegroundColor Yellow
    winget install usbipd-win
    Write-Host "Please restart PowerShell and run script again" -ForegroundColor Green
    exit 0
}

# List devices and find LabJack
Write-Host "Scanning for LabJack devices..." -ForegroundColor Yellow
$devices = usbipd list | Select-String -Pattern "LabJack|Meilhaus"

if ($devices.Count -eq 0) {
    Write-Host "ERROR: No LabJack devices found. Check USB connection." -ForegroundColor Red
    Write-Host "Available devices:" -ForegroundColor Yellow
    usbipd list
    exit 1
}

Write-Host "Found LabJack devices:" -ForegroundColor Green
$devices | ForEach-Object { Write-Host $_.Line -ForegroundColor White }

# Auto-bind first LabJack device found
$busid = ($devices[0].Line -split '\s+')[0]
Write-Host "Binding device $busid..." -ForegroundColor Yellow
usbipd bind --busid $busid

# Attach to WSL
Write-Host "Attaching device to WSL..." -ForegroundColor Yellow
usbipd attach --wsl --busid $busid

# Verify
Write-Host "Verification:" -ForegroundColor Green
usbipd list | Select-String -Pattern "LabJack|Meilhaus"

Write-Host "Setup complete! LabJack should now be accessible in WSL." -ForegroundColor Green
Write-Host "Run 'lsusb' in WSL to verify device is visible." -ForegroundColor Yellow
```

### Method 2: Network LabJack (T7-Pro, T8 Only)

For Ethernet-capable LabJack devices, you can bypass USB entirely.

#### Prerequisites
- LabJack T7-Pro or T8 with Ethernet capability
- Network connection (router/switch)
- Both Windows and WSL on same network

#### Setup Steps

**Step 1: Configure LabJack Network Settings**
```bash
# Use LabJack Kipling software on Windows to configure:
# 1. Static IP address (e.g., 192.168.1.207)
# 2. Subnet mask (e.g., 255.255.255.0)
# 3. Gateway (your router IP)
```

**Step 2: Test Connectivity from WSL**
```bash
# Ping LabJack IP
ping 192.168.1.207

# Test Modbus port
telnet 192.168.1.207 502
# Should connect if LabJack is accessible
```

**Step 3: Update Backend Configuration**
```python
# In config/labjack_config.py
NETWORK_CONFIG = LabJackConfig(
    device_type="T7",
    connection_type="ETHERNET",
    device_identifier="192.168.1.207",  # Your LabJack IP
    ttl_channel="DIO0",
    sample_rate=10000
)
```

### Method 3: Shared Folder Communication

Alternative bridge using Windows shared folders for file-based communication.

#### Prerequisites
- Windows shared folder accessible from WSL
- Windows service to monitor shared folder

#### Setup Steps

**Step 1: Create Shared Communication Directory**
```bash
# In WSL
sudo mkdir -p /mnt/c/temp/labjack_bridge
sudo chmod 777 /mnt/c/temp/labjack_bridge
```

**Step 2: Windows Bridge Service (Python)**

Save as `labjack_bridge_service.py` on Windows:

```python
import os
import json
import time
import threading
from datetime import datetime
import labjack.ljm as ljm

class LabJackBridgeService:
    def __init__(self, bridge_path="C:\\temp\\labjack_bridge"):
        self.bridge_path = bridge_path
        self.labjack_handle = None
        self.running = False
        
        # Create bridge directory
        os.makedirs(bridge_path, exist_ok=True)
        
    def connect_labjack(self):
        """Connect to LabJack device"""
        try:
            self.labjack_handle = ljm.openS("ANY", "ANY", "ANY")
            return True
        except Exception as e:
            print(f"LabJack connection failed: {e}")
            return False
    
    def process_requests(self):
        """Process requests from WSL"""
        request_file = os.path.join(self.bridge_path, "request.json")
        response_file = os.path.join(self.bridge_path, "response.json")
        
        while self.running:
            try:
                if os.path.exists(request_file):
                    with open(request_file, 'r') as f:
                        request = json.load(f)
                    
                    # Process request
                    response = self.handle_request(request)
                    
                    # Write response
                    with open(response_file, 'w') as f:
                        json.dump(response, f)
                    
                    # Remove request file
                    os.remove(request_file)
            
            except Exception as e:
                print(f"Request processing error: {e}")
            
            time.sleep(0.1)  # Check every 100ms
    
    def handle_request(self, request):
        """Handle specific request types"""
        action = request.get("action", "")
        
        if action == "status":
            return {
                "connected": self.labjack_handle is not None,
                "device_type": "LabJack via Shared Folder",
                "timestamp": datetime.now().isoformat()
            }
        
        elif action == "read_digital":
            if self.labjack_handle:
                try:
                    channel = request.get("channel", "DIO0")
                    value = ljm.eReadName(self.labjack_handle, channel)
                    return {
                        "success": True,
                        "value": int(value),
                        "channel": channel,
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}
            else:
                return {"success": False, "error": "Not connected"}
        
        return {"error": "Unknown action"}
    
    def start(self):
        """Start the bridge service"""
        print("Starting LabJack Bridge Service...")
        
        if self.connect_labjack():
            print("✅ LabJack connected")
        else:
            print("⚠️ LabJack not connected - service will run in offline mode")
        
        self.running = True
        thread = threading.Thread(target=self.process_requests, daemon=True)
        thread.start()
        
        print(f"🔄 Monitoring {self.bridge_path} for requests...")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping bridge service...")
            self.running = False
            if self.labjack_handle:
                ljm.close(self.labjack_handle)

if __name__ == "__main__":
    service = LabJackBridgeService()
    service.start()
```

## Testing and Verification

### Connection Test Script

Save as `test_labjack_connection.py` in WSL:

```python
#!/usr/bin/env python3
"""
LabJack Connection Test Script for WSL Environment
"""

import sys
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_usbip_method():
    """Test USB/IP method"""
    logger.info("=== Testing USB/IP Method ===")
    
    try:
        import labjack.ljm as ljm
        logger.info("✅ LabJack library imported successfully")
        
        # List devices
        devices = ljm.listAll(ljm.constants.dtANY, ljm.constants.ctANY)
        logger.info(f"📋 Found {len(devices)} devices")
        
        if devices[0]:  # If devices found
            # Connect to first device
            handle = ljm.open(ljm.constants.dtANY, ljm.constants.ctUSB, "ANY")
            info = ljm.getHandleInfo(handle)
            
            device_type = ljm.numberToType(info[0])
            connection_type = ljm.numberToConnectionType(info[1])
            serial_number = info[2]
            
            logger.info(f"🎉 Connected via USB/IP:")
            logger.info(f"   Device: {device_type}")
            logger.info(f"   Connection: {connection_type}")
            logger.info(f"   Serial: {serial_number}")
            
            # Test digital read
            value = ljm.eReadName(handle, "DIO0")
            logger.info(f"📊 DIO0 Value: {value}")
            
            ljm.close(handle)
            return True
        else:
            logger.warning("⚠️ No devices found via USB/IP")
            return False
            
    except Exception as e:
        logger.error(f"❌ USB/IP test failed: {e}")
        return False

def test_network_method():
    """Test Network method"""
    logger.info("=== Testing Network Method ===")
    
    try:
        import labjack.ljm as ljm
        
        # Try common LabJack IP addresses
        test_ips = ["192.168.1.207", "192.168.0.207"]
        
        for ip in test_ips:
            try:
                logger.info(f"🔍 Testing IP: {ip}")
                handle = ljm.openS("T7", "ETHERNET", ip)
                info = ljm.getHandleInfo(handle)
                
                device_type = ljm.numberToType(info[0])
                logger.info(f"🎉 Connected via Network:")
                logger.info(f"   IP: {ip}")
                logger.info(f"   Device: {device_type}")
                
                # Test digital read
                value = ljm.eReadName(handle, "DIO0")
                logger.info(f"📊 DIO0 Value: {value}")
                
                ljm.close(handle)
                return True
                
            except Exception as e:
                logger.info(f"📍 IP {ip} not accessible: {e}")
        
        logger.warning("⚠️ No network LabJack devices found")
        return False
        
    except Exception as e:
        logger.error(f"❌ Network test failed: {e}")
        return False

def test_shared_folder_method():
    """Test Shared Folder method"""
    logger.info("=== Testing Shared Folder Method ===")
    
    import os
    import json
    
    try:
        bridge_path = "/mnt/c/temp/labjack_bridge"
        
        # Check if bridge directory exists
        if not os.path.exists(bridge_path):
            logger.warning(f"⚠️ Bridge directory not found: {bridge_path}")
            return False
        
        # Create test request
        request_file = os.path.join(bridge_path, "request.json")
        response_file = os.path.join(bridge_path, "response.json")
        
        # Clean up any existing files
        for f in [request_file, response_file]:
            if os.path.exists(f):
                os.remove(f)
        
        # Send status request
        request = {
            "action": "status",
            "timestamp": datetime.now().isoformat()
        }
        
        with open(request_file, 'w') as f:
            json.dump(request, f)
        
        logger.info("📤 Sent status request")
        
        # Wait for response (max 10 seconds)
        for i in range(100):  # 100 * 0.1s = 10s
            if os.path.exists(response_file):
                with open(response_file, 'r') as f:
                    response = json.load(f)
                
                logger.info(f"📬 Received response: {response}")
                
                if response.get("connected"):
                    logger.info("🎉 Shared folder bridge is working!")
                    return True
                else:
                    logger.warning("⚠️ Bridge responded but LabJack not connected")
                    return False
            
            time.sleep(0.1)
        
        logger.warning("⚠️ No response from shared folder bridge")
        return False
        
    except Exception as e:
        logger.error(f"❌ Shared folder test failed: {e}")
        return False

def test_api_endpoints():
    """Test HIL platform API endpoints"""
    logger.info("=== Testing API Endpoints ===")
    
    try:
        import requests
        
        # Test LabJack status endpoint
        response = requests.get("http://localhost:8000/api/labjack/status", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ API Status: {data}")
            return True
        else:
            logger.warning(f"⚠️ API returned status {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ API test failed: {e}")
        logger.info("💡 Make sure the backend is running: python main.py")
        return False

def main():
    """Run all connection tests"""
    logger.info("🚀 LabJack WSL Connection Test Suite")
    logger.info("=" * 50)
    
    results = {
        "USB/IP Method": test_usbip_method(),
        "Network Method": test_network_method(),
        "Shared Folder Method": test_shared_folder_method(),
        "API Endpoints": test_api_endpoints()
    }
    
    # Summary
    logger.info("=" * 50)
    logger.info("📋 TEST RESULTS SUMMARY")
    logger.info("=" * 50)
    
    working_methods = []
    for method, result in results.items():
        if result:
            logger.info(f"✅ {method}: WORKING")
            working_methods.append(method)
        else:
            logger.info(f"❌ {method}: FAILED")
    
    if working_methods:
        logger.info(f"🎉 Working methods: {', '.join(working_methods)}")
        logger.info("🚀 LabJack hardware is ready for HIL testing!")
    else:
        logger.warning("⚠️ No working connection methods found")
        logger.info("💡 Please check setup instructions and try again")

if __name__ == "__main__":
    main()
```

### HIL Test Execution

Test the complete HIL workflow:

```python
#!/usr/bin/env python3
"""
HIL Test Execution Validation
"""

import asyncio
import logging
from datetime import datetime

async def test_hil_workflow():
    """Test complete HIL workflow"""
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing HIL Workflow")
    
    try:
        # Import backend services
        from services.labjack_wsl_service import labjack_service
        from api.hil_test_complete import execute_hil_test
        
        # Check LabJack connection
        status = labjack_service.get_connection_status()
        if not status["connected"]:
            logger.error("❌ LabJack not connected")
            return False
        
        logger.info(f"✅ LabJack connected: {status['device_info']}")
        
        # Execute test session
        test_config = {
            "session_name": f"HIL_Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "video_file": "test_video.mp4",
            "ground_truth_file": "test_annotations.json",
            "ttl_channel": "DIO0",
            "timing_precision": "microsecond"
        }
        
        logger.info("🎬 Starting HIL test execution...")
        result = await execute_hil_test(test_config)
        
        if result["success"]:
            logger.info("🎉 HIL test completed successfully!")
            logger.info(f"📊 Results: {result['metrics']}")
            return True
        else:
            logger.error(f"❌ HIL test failed: {result['error']}")
            return False
            
    except Exception as e:
        logger.error(f"❌ HIL workflow test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_hil_workflow())
```

## Troubleshooting

### Common Issues

#### Issue 1: "usbipd: command not found"
**Solution:**
- Ensure usbipd-win is installed on Windows
- Restart PowerShell after installation
- Check Windows PATH includes usbipd

#### Issue 2: Device not showing in `usbipd list`
**Solution:**
- Check physical USB connection
- Try different USB port
- Install LabJack drivers from LabJack.com
- Check Windows Device Manager

#### Issue 3: "usbipd bind" fails
**Solution:**
- Run PowerShell as Administrator
- Check if device is already bound
- Unbind first: `usbipd unbind --busid X-Y`

#### Issue 4: Device attached but not visible in WSL
**Solution:**
```bash
# Check WSL kernel version
uname -r

# Update WSL kernel if needed
wsl --update

# Check USB subsystem
sudo modprobe usbcore
sudo modprobe usb-storage
```

#### Issue 5: "ImportError: No module named 'labjack'"
**Solution:**
```bash
# In WSL, activate your virtual environment
source .venv/bin/activate

# Install LabJack library
pip install labjack-ljm

# Verify installation
python -c "import labjack.ljm; print('LabJack library installed')"
```

#### Issue 6: Permission denied accessing USB device
**Solution:**
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Set USB permissions
sudo chmod 666 /dev/bus/usb/*/*

# Or create udev rule
sudo nano /etc/udev/rules.d/99-labjack.rules
# Add: SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", MODE="0666"
```

### Diagnostic Commands

**Windows Commands:**
```powershell
# Check USB devices
Get-PnpDevice | Where-Object {$_.FriendlyName -like "*LabJack*"}

# Check usbipd status
usbipd list

# Reset USB device
usbipd unbind --busid X-Y
usbipd bind --busid X-Y
usbipd attach --wsl --busid X-Y
```

**WSL Commands:**
```bash
# Check USB devices
lsusb
lsusb -v | grep -i labjack

# Check device permissions
ls -la /dev/bus/usb/

# Check Python LabJack library
python -c "
import labjack.ljm as ljm
devices = ljm.listAll(ljm.constants.dtANY, ljm.constants.ctANY)
print(f'Found {len(devices)} devices')
"

# Check backend service logs
tail -f logs/labjack_service.log
```

### Performance Optimization

1. **USB/IP Performance:**
   - Use USB 3.0 ports for better bandwidth
   - Avoid USB hubs if possible
   - Consider dedicated USB controller

2. **Network Performance:**
   - Use Gigabit Ethernet for LabJack T7-Pro/T8
   - Configure static IP for LabJack
   - Minimize network latency

3. **WSL Performance:**
   - Allocate sufficient memory to WSL2
   - Use WSL2 (not WSL1) for better performance
   - Consider limiting other WSL processes

## Quick Start Checklist

- [ ] Windows 10/11 with WSL2 enabled
- [ ] LabJack device physically connected
- [ ] Administrator privileges available
- [ ] usbipd-win installed on Windows
- [ ] USB/IP tools installed in WSL
- [ ] LabJack device bound and attached
- [ ] Device visible with `lsusb` in WSL
- [ ] Python labjack-ljm library installed
- [ ] Connection test script passes
- [ ] Backend service running
- [ ] API endpoints responding
- [ ] HIL test workflow functional

## Support

For additional help:
- LabJack Official Documentation: https://labjack.com/support
- usbipd-win GitHub: https://github.com/dorssel/usbipd-win
- WSL Documentation: https://docs.microsoft.com/en-us/windows/wsl/

---

This setup guide provides multiple methods to connect LabJack hardware from WSL2, with the USB/IP bridge being the recommended approach for most users. The testing scripts help verify each method works correctly with your specific hardware configuration.