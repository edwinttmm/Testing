#!/usr/bin/env python3
"""
LabJack Connection Test Script for WSL Environment
Comprehensive testing of all connection methods and HIL integration
"""

import sys
import os
import time
import json
import logging
import asyncio
import requests
from datetime import datetime
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LabJackConnectionTester:
    """Comprehensive LabJack connection tester for WSL environment"""
    
    def __init__(self):
        self.test_results = {}
        
    def test_library_import(self):
        """Test LabJack library import and availability"""
        logger.info("=== Testing LabJack Library Import ===")
        
        try:
            import labjack.ljm as ljm
            logger.info("✅ LabJack library imported successfully")
            
            # Test basic constants
            constants_to_test = ['dtANY', 'ctANY', 'ctUSB', 'ctETHERNET']
            for const in constants_to_test:
                if hasattr(ljm.constants, const):
                    logger.info(f"✅ Constant {const} available")
                else:
                    logger.warning(f"⚠️ Constant {const} not available")
            
            # Test functions
            functions_to_test = ['listAll', 'openS', 'close', 'getHandleInfo', 'eReadName']
            for func in functions_to_test:
                if hasattr(ljm, func):
                    logger.info(f"✅ Function {func} available")
                else:
                    logger.warning(f"⚠️ Function {func} not available")
            
            return True
            
        except ImportError as e:
            logger.error(f"❌ Failed to import LabJack library: {e}")
            logger.info("💡 Install with: pip install labjack-ljm")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error testing library: {e}")
            return False

    def test_usbip_method(self):
        """Test USB/IP connection method"""
        logger.info("=== Testing USB/IP Method ===")
        
        try:
            import labjack.ljm as ljm
            
            # Check USB device enumeration
            logger.info("🔍 Enumerating USB devices...")
            try:
                devices = ljm.listAll(ljm.constants.dtANY, ljm.constants.ctUSB)
                logger.info(f"📋 Found {len(devices)} USB devices")
                
                if devices[0]:  # If devices found
                    logger.info("🎉 LabJack USB devices detected!")
                    
                    # Try to connect to first device
                    try:
                        handle = ljm.open(ljm.constants.dtANY, ljm.constants.ctUSB, "ANY")
                        info = ljm.getHandleInfo(handle)
                        
                        device_type = ljm.numberToType(info[0])
                        connection_type = ljm.numberToConnectionType(info[1])
                        serial_number = info[2]
                        
                        logger.info(f"🎉 Connected via USB/IP:")
                        logger.info(f"   Device: {device_type}")
                        logger.info(f"   Connection: {connection_type}")
                        logger.info(f"   Serial: {serial_number}")
                        
                        # Test basic I/O
                        try:
                            value = ljm.eReadName(handle, "DIO0")
                            logger.info(f"📊 DIO0 Value: {value}")
                            
                            # Try setting an output
                            ljm.eWriteName(handle, "DAC0", 2.5)  # Safe test voltage
                            dac_value = ljm.eReadName(handle, "DAC0")
                            logger.info(f"📊 DAC0 Test Value: {dac_value}")
                            
                        except Exception as io_error:
                            logger.warning(f"⚠️ I/O test failed: {io_error}")
                        
                        ljm.close(handle)
                        return "HARDWARE_CONNECTED"
                        
                    except Exception as connect_error:
                        logger.warning(f"⚠️ Connection attempt failed: {connect_error}")
                        return "DEVICES_FOUND_CONNECTION_FAILED"
                else:
                    logger.info("📍 No LabJack USB devices found")
                    return "NO_DEVICES"
                    
            except Exception as enum_error:
                logger.warning(f"⚠️ Device enumeration failed: {enum_error}")
                return "ENUMERATION_FAILED"
                
        except ImportError:
            logger.error("❌ LabJack library not available")
            return False
        except Exception as e:
            logger.error(f"❌ USB/IP test failed: {e}")
            return False

    def test_network_method(self):
        """Test Network connection method"""
        logger.info("=== Testing Network Method ===")
        
        try:
            import labjack.ljm as ljm
            
            # Test common LabJack IP addresses
            test_ips = [
                "192.168.1.207",  # Common default
                "192.168.0.207",  # Alternative default
                "10.0.0.207",     # Another common range
                "169.254.1.207"   # Link-local
            ]
            
            for ip in test_ips:
                try:
                    logger.info(f"🔍 Testing IP: {ip}")
                    
                    # Test basic connectivity first
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((ip, 502))  # Modbus port
                    sock.close()
                    
                    if result == 0:
                        logger.info(f"✅ Network connectivity to {ip}:502 successful")
                        
                        # Try LabJack connection
                        handle = ljm.openS("T7", "ETHERNET", ip)
                        info = ljm.getHandleInfo(handle)
                        
                        device_type = ljm.numberToType(info[0])
                        logger.info(f"🎉 Connected via Network:")
                        logger.info(f"   IP: {ip}")
                        logger.info(f"   Device: {device_type}")
                        logger.info(f"   Serial: {info[2]}")
                        
                        # Test I/O
                        value = ljm.eReadName(handle, "DIO0")
                        logger.info(f"📊 DIO0 Value: {value}")
                        
                        ljm.close(handle)
                        return "NETWORK_CONNECTED"
                        
                    else:
                        logger.info(f"📍 No response from {ip}:502")
                        
                except Exception as e:
                    logger.info(f"📍 IP {ip} not accessible: {e}")
            
            logger.info("📍 No network LabJack devices found")
            return "NO_NETWORK_DEVICES"
            
        except ImportError:
            logger.error("❌ LabJack library not available")
            return False
        except Exception as e:
            logger.error(f"❌ Network test failed: {e}")
            return False

    def test_shared_folder_method(self):
        """Test Shared Folder communication method"""
        logger.info("=== Testing Shared Folder Method ===")
        
        try:
            bridge_path = "/mnt/c/temp/labjack_bridge"
            
            # Check if bridge directory exists
            if not os.path.exists("/mnt/c"):
                logger.warning("⚠️ Windows C: drive not mounted in WSL")
                return "NO_WINDOWS_MOUNT"
                
            if not os.path.exists(bridge_path):
                logger.info(f"📁 Creating bridge directory: {bridge_path}")
                os.makedirs(bridge_path, exist_ok=True)
            
            # Test file creation/access
            test_file = os.path.join(bridge_path, "wsl_test.txt")
            try:
                with open(test_file, 'w') as f:
                    f.write(f"WSL test at {datetime.now().isoformat()}")
                
                with open(test_file, 'r') as f:
                    content = f.read()
                    logger.info(f"✅ File I/O test successful: {content[:50]}...")
                
                os.remove(test_file)
            except Exception as file_error:
                logger.error(f"❌ Shared folder file I/O failed: {file_error}")
                return "FILE_IO_FAILED"
            
            # Test bridge communication
            request_file = os.path.join(bridge_path, "request.json")
            response_file = os.path.join(bridge_path, "response.json")
            
            # Clean up any existing files
            for f in [request_file, response_file]:
                if os.path.exists(f):
                    os.remove(f)
            
            # Send status request
            request = {
                "action": "status",
                "timestamp": datetime.now().isoformat(),
                "source": "wsl_test"
            }
            
            with open(request_file, 'w') as f:
                json.dump(request, f, indent=2)
            
            logger.info("📤 Sent status request to bridge")
            
            # Wait for response (max 10 seconds)
            response_received = False
            for i in range(100):  # 100 * 0.1s = 10s
                if os.path.exists(response_file):
                    with open(response_file, 'r') as f:
                        response = json.load(f)
                    
                    logger.info(f"📬 Received response: {response}")
                    response_received = True
                    
                    if response.get("connected"):
                        logger.info("🎉 Shared folder bridge is working with hardware!")
                        return "BRIDGE_WITH_HARDWARE"
                    else:
                        logger.info("✅ Shared folder bridge is working (no hardware)")
                        return "BRIDGE_NO_HARDWARE"
                    break
                
                time.sleep(0.1)
            
            if not response_received:
                logger.warning("⚠️ No response from shared folder bridge")
                logger.info("💡 Start Windows bridge service: python labjack_bridge_service.py")
                return "NO_BRIDGE_RESPONSE"
                
        except Exception as e:
            logger.error(f"❌ Shared folder test failed: {e}")
            return False

    def test_wsl_usb_setup(self):
        """Test WSL USB setup and permissions"""
        logger.info("=== Testing WSL USB Setup ===")
        
        try:
            import subprocess
            
            # Check lsusb availability
            result = subprocess.run(['which', 'lsusb'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("⚠️ lsusb not available")
                logger.info("💡 Install with: sudo apt install usbutils")
                return "LSUSB_NOT_AVAILABLE"
            
            # Run lsusb to check devices
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if result.returncode == 0:
                usb_devices = result.stdout
                logger.info(f"📋 USB devices visible in WSL: {len(usb_devices.splitlines())} devices")
                
                # Look for LabJack devices
                if 'LabJack' in usb_devices or 'Meilhaus' in usb_devices:
                    logger.info("🎉 LabJack device visible in WSL!")
                    logger.info("USB devices containing 'LabJack' or 'Meilhaus':")
                    for line in usb_devices.splitlines():
                        if 'LabJack' in line or 'Meilhaus' in line:
                            logger.info(f"   {line}")
                    return "LABJACK_VISIBLE"
                else:
                    logger.info("📍 No LabJack devices visible in lsusb output")
                    if len(usb_devices.splitlines()) > 1:
                        logger.info("Sample USB devices:")
                        for line in usb_devices.splitlines()[:5]:
                            logger.info(f"   {line}")
                    return "NO_LABJACK_VISIBLE"
            else:
                logger.error(f"❌ lsusb failed: {result.stderr}")
                return "LSUSB_FAILED"
                
        except Exception as e:
            logger.error(f"❌ WSL USB setup test failed: {e}")
            return False

    def test_backend_integration(self):
        """Test backend service integration"""
        logger.info("=== Testing Backend Integration ===")
        
        try:
            # Test if backend services are importable
            try:
                from services.labjack_wsl_service import labjack_service
                logger.info("✅ LabJack WSL service imported")
                
                # Test service status
                status = labjack_service.get_connection_status()
                logger.info(f"📊 Service Status: {status}")
                
                if status.get("connected"):
                    logger.info("🎉 Backend reports LabJack connected!")
                    return "BACKEND_CONNECTED"
                else:
                    logger.info("📍 Backend service ready but no hardware connected")
                    return "BACKEND_READY"
                    
            except ImportError as import_error:
                logger.warning(f"⚠️ Backend service import failed: {import_error}")
                return "BACKEND_IMPORT_FAILED"
                
        except Exception as e:
            logger.error(f"❌ Backend integration test failed: {e}")
            return False

    def test_api_endpoints(self):
        """Test LabJack API endpoints"""
        logger.info("=== Testing API Endpoints ===")
        
        try:
            base_url = "http://localhost:8000"
            
            # Test endpoints
            endpoints_to_test = [
                "/api/labjack/status",
                "/api/labjack/connection-info",
                "/api/health"
            ]
            
            working_endpoints = []
            
            for endpoint in endpoints_to_test:
                try:
                    response = requests.get(f"{base_url}{endpoint}", timeout=5)
                    
                    if response.status_code == 200:
                        logger.info(f"✅ {endpoint}: OK")
                        working_endpoints.append(endpoint)
                        
                        # Log response for status endpoints
                        if 'status' in endpoint:
                            data = response.json()
                            logger.info(f"   Response: {data}")
                    else:
                        logger.warning(f"⚠️ {endpoint}: HTTP {response.status_code}")
                        
                except requests.exceptions.ConnectionError:
                    logger.warning(f"⚠️ {endpoint}: Connection refused")
                except requests.exceptions.Timeout:
                    logger.warning(f"⚠️ {endpoint}: Timeout")
                except Exception as e:
                    logger.warning(f"⚠️ {endpoint}: {e}")
            
            if working_endpoints:
                logger.info(f"✅ Working endpoints: {working_endpoints}")
                return "API_WORKING"
            else:
                logger.warning("⚠️ No API endpoints responding")
                logger.info("💡 Make sure backend is running: python main.py")
                return "NO_API_RESPONSE"
                
        except Exception as e:
            logger.error(f"❌ API endpoint test failed: {e}")
            return False

    def run_all_tests(self):
        """Run comprehensive test suite"""
        logger.info("🚀 LabJack WSL Connection Test Suite")
        logger.info("=" * 60)
        
        # Test sequence
        tests = [
            ("Library Import", self.test_library_import),
            ("WSL USB Setup", self.test_wsl_usb_setup),
            ("USB/IP Method", self.test_usbip_method),
            ("Network Method", self.test_network_method),
            ("Shared Folder Method", self.test_shared_folder_method),
            ("Backend Integration", self.test_backend_integration),
            ("API Endpoints", self.test_api_endpoints)
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n🧪 Running {test_name} test...")
            try:
                result = test_func()
                self.test_results[test_name] = result
            except Exception as e:
                logger.error(f"❌ {test_name} test crashed: {e}")
                self.test_results[test_name] = f"CRASHED: {e}"
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate test results summary with recommendations"""
        logger.info("\n" + "=" * 60)
        logger.info("📋 TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        
        # Categorize results
        passed_tests = []
        hardware_connected = []
        setup_needed = []
        failed_tests = []
        
        for test_name, result in self.test_results.items():
            if result is True or "WORKING" in str(result):
                passed_tests.append(test_name)
            elif "CONNECTED" in str(result) or "HARDWARE" in str(result):
                hardware_connected.append((test_name, result))
            elif result is False or "FAILED" in str(result):
                failed_tests.append((test_name, result))
            else:
                setup_needed.append((test_name, result))
        
        # Print results
        for test_name, result in self.test_results.items():
            if result is True:
                logger.info(f"✅ {test_name}: PASSED")
            elif result is False:
                logger.info(f"❌ {test_name}: FAILED")
            elif "CONNECTED" in str(result) or "HARDWARE" in str(result):
                logger.info(f"🎉 {test_name}: {result}")
            else:
                logger.info(f"📍 {test_name}: {result}")
        
        # Generate recommendations
        logger.info("\n" + "=" * 60)
        logger.info("🔧 RECOMMENDATIONS")
        logger.info("=" * 60)
        
        if hardware_connected:
            logger.info("🎉 HARDWARE DETECTED!")
            for test_name, result in hardware_connected:
                logger.info(f"   ✅ {test_name}: {result}")
            logger.info("🚀 Your LabJack hardware is ready for HIL testing!")
            
        elif any("VISIBLE" in str(result) for result in self.test_results.values()):
            logger.info("📱 HARDWARE VISIBLE BUT NOT ACCESSIBLE")
            logger.info("   Recommendations:")
            logger.info("   1. Check LabJack library installation: pip install labjack-ljm")
            logger.info("   2. Check USB permissions in WSL")
            logger.info("   3. Try restarting the backend service")
            
        else:
            logger.info("🔧 HARDWARE SETUP NEEDED")
            
            if "NO_LABJACK_VISIBLE" in self.test_results.get("WSL USB Setup", ""):
                logger.info("   USB/IP Bridge Setup Required:")
                logger.info("   1. Run Windows PowerShell as Administrator")
                logger.info("   2. Execute: .\\setup-labjack-usbip.ps1")
                logger.info("   3. Or manually:")
                logger.info("      - usbipd list (find LabJack BUSID)")
                logger.info("      - usbipd bind --busid X-Y")
                logger.info("      - usbipd attach --wsl --busid X-Y")
            
            if "NO_NETWORK_DEVICES" in self.test_results.get("Network Method", ""):
                logger.info("   Network LabJack Setup (alternative):")
                logger.info("   1. Configure LabJack with static IP (use Kipling)")
                logger.info("   2. Update backend config with LabJack IP")
                logger.info("   3. Test connectivity: ping [labjack-ip]")
            
            if "NO_BRIDGE_RESPONSE" in self.test_results.get("Shared Folder Method", ""):
                logger.info("   Shared Folder Bridge Setup (alternative):")
                logger.info("   1. Copy labjack_bridge_service.py to Windows")
                logger.info("   2. Install LabJack Python library on Windows")
                logger.info("   3. Run bridge service: python labjack_bridge_service.py")
        
        # Final status
        logger.info("\n" + "=" * 60)
        hardware_ready = bool(hardware_connected)
        
        if hardware_ready:
            logger.info("🎉 STATUS: HARDWARE READY FOR HIL TESTING!")
        else:
            logger.info("⚠️ STATUS: HARDWARE SETUP REQUIRED")
        
        logger.info(f"✅ Tests Passed: {len(passed_tests)}/{len(self.test_results)}")
        logger.info("🔧 See recommendations above for next steps")
        
        # Save detailed results
        results_file = "labjack_connection_test_results.json"
        try:
            with open(results_file, 'w') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "hardware_ready": hardware_ready,
                    "test_results": self.test_results,
                    "summary": {
                        "passed": len(passed_tests),
                        "total": len(self.test_results),
                        "hardware_connected": bool(hardware_connected)
                    }
                }, f, indent=2)
            logger.info(f"📄 Detailed results saved to: {results_file}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save results file: {e}")

def main():
    """Main test function"""
    tester = LabJackConnectionTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()