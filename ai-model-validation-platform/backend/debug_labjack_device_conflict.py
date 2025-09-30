#!/usr/bin/env python3
"""
LabJack Device Conflict Resolution Tool

This script identifies and resolves LabJack device conflicts that prevent
HIL test execution by finding processes that claim the device.

Key Functions:
1. Detect current LabJack device holders
2. Safely release device connections
3. Reset LabJack connection state
4. Verify device availability
5. Test successful connection after cleanup
"""

import time
import logging
import sys
import os
import subprocess
from typing import List, Dict, Any, Optional

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LabJackDeviceConflictResolver:
    """Resolves LabJack device conflicts for HIL testing"""
    
    def __init__(self):
        self.device_info = {}
        self.conflict_processes = []
        
    def check_ljm_installation(self) -> bool:
        """Check if LabJack LJM library is properly installed"""
        logger.info("=== Checking LJM Installation ===")
        
        try:
            import labjack.ljm as ljm
            logger.info("✅ LabJack LJM library imported successfully")
            
            # Check LJM version
            try:
                version = ljm.libVersion()
                logger.info(f"📊 LJM Library Version: {version}")
            except Exception as e:
                logger.warning(f"Could not get LJM version: {e}")
                
            return True
            
        except ImportError as e:
            logger.error(f"❌ LabJack LJM library not available: {e}")
            return False
    
    def scan_for_labjack_devices(self) -> List[Dict[str, Any]]:
        """Scan for available LabJack devices"""
        logger.info("=== Scanning for LabJack Devices ===")
        
        devices = []
        
        try:
            import labjack.ljm as ljm
            
            # Scan for devices
            device_types = [ljm.constants.dtT7, ljm.constants.dtT4]  # Common device types
            connection_types = [ljm.constants.ctUSB, ljm.constants.ctETHERNET, ljm.constants.ctWIFI]
            
            for device_type in device_types:
                for conn_type in connection_types:
                    try:
                        device_info = ljm.listAll(device_type, conn_type)
                        if device_info[0]:  # If devices found
                            for i in range(device_info[0]):  # device_info[0] is count
                                device_data = {
                                    'device_type': device_type,
                                    'connection_type': conn_type,
                                    'serial_number': device_info[1][i] if len(device_info[1]) > i else None,
                                    'ip_address': device_info[2][i] if len(device_info[2]) > i else None,
                                    'port': device_info[3][i] if len(device_info[3]) > i else None,
                                    'max_bytes_per_MB': device_info[4][i] if len(device_info[4]) > i else None
                                }
                                devices.append(device_data)
                                logger.info(f"📱 Found device: Type={device_type}, "
                                           f"Serial={device_data['serial_number']}, "
                                           f"Connection={conn_type}")
                    
                    except Exception as e:
                        # This is normal - not all combinations will have devices
                        pass
                        
            if not devices:
                logger.warning("⚠️ No LabJack devices found during scan")
            else:
                logger.info(f"✅ Found {len(devices)} LabJack device(s)")
                
        except Exception as e:
            logger.error(f"❌ Device scan failed: {e}")
            
        return devices
    
    def test_device_connection(self, device_info: Optional[Dict] = None) -> Optional[int]:
        """Test connection to a specific device or any available device"""
        logger.info("=== Testing Device Connection ===")
        
        try:
            import labjack.ljm as ljm
            
            handle = None
            if device_info:
                # Try specific device
                logger.info(f"Attempting to connect to specific device: {device_info}")
                try:
                    handle = ljm.openS(
                        device_info.get('device_type', 'ANY'),
                        device_info.get('connection_type', 'ANY'),
                        str(device_info.get('serial_number', ''))
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to connect to specific device: {e}")
                    if "LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS" in str(e):
                        logger.error("🚨 Device is claimed by another process!")
                        return None
            else:
                # Try any device
                logger.info("Attempting to connect to any available device...")
                try:
                    handle = ljm.openS("ANY", "ANY", "ANY")
                except Exception as e:
                    logger.error(f"❌ Failed to connect to any device: {e}")
                    if "LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS" in str(e):
                        logger.error("🚨 Device is claimed by another process!")
                        return None
                    elif "LJME_NO_DEVICES_FOUND" in str(e):
                        logger.error("🚨 No LabJack devices found!")
                        return None
            
            if handle is not None:
                logger.info(f"✅ Successfully connected to LabJack (handle: {handle})")
                
                # Test basic read operation
                try:
                    voltage = ljm.eReadName(handle, "AIN0")
                    logger.info(f"📊 Test voltage reading AIN0: {voltage:.4f}V")
                except Exception as e:
                    logger.warning(f"⚠️ Could not read voltage: {e}")
                
                return handle
            else:
                logger.error("❌ Failed to get device handle")
                return None
                
        except Exception as e:
            logger.error(f"❌ Device connection test failed: {e}")
            return None
    
    def close_all_connections(self) -> bool:
        """Close all LabJack connections to free the device"""
        logger.info("=== Closing All LabJack Connections ===")
        
        try:
            import labjack.ljm as ljm
            
            # Close all devices - this is a global LJM operation
            ljm.closeAll()
            logger.info("✅ Called ljm.closeAll() to free all connections")
            
            # Give some time for cleanup
            time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to close connections: {e}")
            return False
    
    def check_system_processes(self) -> List[Dict[str, Any]]:
        """Check for system processes that might be using LabJack"""
        logger.info("=== Checking System Processes ===")
        
        suspect_processes = []
        
        try:
            # Check for processes that might be using LabJack
            process_patterns = [
                'python.*labjack',
                'python.*ljm',
                'labjack',
                'ljm',
                'kipling',  # LabJack's Kipling software
                'labview.*labjack'
            ]
            
            for pattern in process_patterns:
                try:
                    result = subprocess.run(['pgrep', '-fl', pattern], 
                                          capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0 and result.stdout.strip():
                        processes = result.stdout.strip().split('\n')
                        for proc in processes:
                            if proc.strip():
                                pid, *cmd = proc.split(None, 1)
                                suspect_processes.append({
                                    'pid': pid,
                                    'command': cmd[0] if cmd else '',
                                    'pattern': pattern
                                })
                                logger.info(f"🔍 Found process: PID={pid}, CMD={cmd[0] if cmd else ''}")
                
                except subprocess.TimeoutExpired:
                    logger.warning(f"Process search timed out for pattern: {pattern}")
                except FileNotFoundError:
                    logger.debug("pgrep not available")
                    break
                except Exception as e:
                    logger.debug(f"Process search failed for {pattern}: {e}")
            
            # Also check our own Python processes
            try:
                result = subprocess.run(['pgrep', '-fl', 'python.*main.py'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    processes = result.stdout.strip().split('\n')
                    for proc in processes:
                        if proc.strip():
                            pid, *cmd = proc.split(None, 1)
                            suspect_processes.append({
                                'pid': pid,
                                'command': cmd[0] if cmd else '',
                                'pattern': 'python main.py'
                            })
                            logger.info(f"🐍 Found Python main process: PID={pid}")
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"❌ Process check failed: {e}")
        
        if not suspect_processes:
            logger.info("✅ No suspect processes found")
        
        return suspect_processes
    
    def kill_conflicting_processes(self, processes: List[Dict[str, Any]], 
                                 confirm: bool = True) -> bool:
        """Kill processes that might be holding the LabJack device"""
        logger.info("=== Killing Conflicting Processes ===")
        
        if not processes:
            logger.info("No processes to kill")
            return True
        
        killed_processes = []
        
        for proc in processes:
            pid = proc['pid']
            command = proc['command']
            
            if confirm:
                response = input(f"Kill process PID={pid} ({command})? [y/N]: ")
                if response.lower() != 'y':
                    logger.info(f"Skipping process {pid}")
                    continue
            
            try:
                # Try SIGTERM first
                subprocess.run(['kill', pid], check=True, timeout=5)
                time.sleep(1)
                
                # Check if still running
                result = subprocess.run(['kill', '-0', pid], 
                                      capture_output=True, timeout=5)
                
                if result.returncode == 0:
                    # Still running, try SIGKILL
                    logger.warning(f"Process {pid} still running, using SIGKILL")
                    subprocess.run(['kill', '-9', pid], check=True, timeout=5)
                
                killed_processes.append(proc)
                logger.info(f"✅ Killed process {pid} ({command})")
                
            except subprocess.CalledProcessError as e:
                if e.returncode == 1:
                    logger.info(f"Process {pid} already terminated")
                    killed_processes.append(proc)
                else:
                    logger.error(f"❌ Failed to kill process {pid}: {e}")
            except Exception as e:
                logger.error(f"❌ Error killing process {pid}: {e}")
        
        logger.info(f"✅ Killed {len(killed_processes)} processes")
        return len(killed_processes) > 0 or len(processes) == 0
    
    def resolve_device_conflict(self, auto_kill: bool = False) -> bool:
        """Complete device conflict resolution process"""
        logger.info("🚀 Starting LabJack Device Conflict Resolution")
        logger.info("=" * 60)
        
        success = True
        
        # Step 1: Check LJM installation
        if not self.check_ljm_installation():
            logger.error("❌ Cannot proceed without LJM library")
            return False
        
        # Step 2: Scan for devices
        devices = self.scan_for_labjack_devices()
        if not devices:
            logger.error("❌ No LabJack devices found")
            return False
        
        # Step 3: Try initial connection
        logger.info("\n" + "=" * 60)
        logger.info("Testing initial connection...")
        handle = self.test_device_connection()
        
        if handle is not None:
            # Connection successful
            logger.info("✅ Device is available - no conflict detected")
            try:
                import labjack.ljm as ljm
                ljm.close(handle)
            except:
                pass
            return True
        
        # Step 4: Device conflict detected - start resolution
        logger.error("🚨 Device conflict detected - starting resolution process")
        
        # Step 5: Close all existing connections
        logger.info("\n" + "=" * 60)
        self.close_all_connections()
        time.sleep(2)  # Wait for cleanup
        
        # Step 6: Check for conflicting processes
        logger.info("\n" + "=" * 60)
        processes = self.check_system_processes()
        
        if processes:
            if auto_kill:
                killed = self.kill_conflicting_processes(processes, confirm=False)
                if not killed:
                    success = False
            else:
                logger.info("🔍 Found conflicting processes:")
                for proc in processes:
                    logger.info(f"  PID={proc['pid']}: {proc['command']}")
                
                print("\n" + "=" * 60)
                print("MANUAL INTERVENTION REQUIRED:")
                print("Please stop these processes manually, then rerun the test")
                print("Or run with --auto-kill to automatically terminate them")
                print("=" * 60)
                
                return False
        
        # Step 7: Wait and test connection again
        logger.info("\n" + "=" * 60)
        logger.info("Waiting 3 seconds for device to become available...")
        time.sleep(3)
        
        logger.info("Testing connection after conflict resolution...")
        handle = self.test_device_connection()
        
        if handle is not None:
            logger.info("✅ Device conflict resolved successfully!")
            try:
                import labjack.ljm as ljm
                ljm.close(handle)
            except:
                pass
            return True
        else:
            logger.error("❌ Device conflict not resolved")
            return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Resolve LabJack device conflicts')
    parser.add_argument('--auto-kill', action='store_true',
                       help='Automatically kill conflicting processes')
    parser.add_argument('--test-only', action='store_true',
                       help='Only test device connection, do not resolve conflicts')
    
    args = parser.parse_args()
    
    resolver = LabJackDeviceConflictResolver()
    
    if args.test_only:
        logger.info("🧪 Testing device connection only...")
        handle = resolver.test_device_connection()
        if handle:
            try:
                import labjack.ljm as ljm
                ljm.close(handle)
            except:
                pass
            logger.info("✅ Device connection test successful")
            return True
        else:
            logger.error("❌ Device connection test failed")
            return False
    
    success = resolver.resolve_device_conflict(auto_kill=args.auto_kill)
    
    if success:
        logger.info("🎉 Device conflict resolution successful!")
        logger.info("You can now run HIL tests")
        return True
    else:
        logger.error("🚨 Device conflict resolution failed")
        logger.error("Manual intervention may be required")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)