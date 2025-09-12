#!/usr/bin/env python3
"""
LabJack USB Passthrough Device Manager

A comprehensive Python script for managing LabJack devices through USB passthrough.
Provides device detection, connection management, testing, and monitoring capabilities.
"""

import argparse
import json
import logging
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('labjack_manager.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class LabJackDevice:
    """Represents a LabJack device"""
    bus_id: str
    vid_pid: str
    description: str
    state: str
    device_type: Optional[str] = None
    
    @property
    def vendor_id(self) -> str:
        """Get vendor ID from VID:PID"""
        return self.vid_pid.split(':')[0]
    
    @property
    def product_id(self) -> str:
        """Get product ID from VID:PID"""
        return self.vid_pid.split(':')[1]
    
    def __str__(self) -> str:
        return f"{self.bus_id} - {self.description} ({self.vid_pid}) - {self.state}"

class LabJackManager:
    """Main LabJack device manager class"""
    
    # Device type mappings
    DEVICE_TYPES = {
        '0009': 'U3',
        '000a': 'U6', 
        '000b': 'UE9',
        '4004': 'T4',
        '4007': 'T7',
        '4008': 'T8'
    }
    
    def __init__(self, wsl_distribution: str = 'Ubuntu'):
        self.wsl_distribution = wsl_distribution
        self.platform = platform.system()
        self.is_windows = self.platform == 'Windows'
        
        # Validate environment
        self._validate_environment()
    
    def _validate_environment(self):
        """Validate the environment and required tools"""
        if self.is_windows:
            # Check for usbipd-win
            try:
                result = subprocess.run(['usbipd', '--version'], 
                                      capture_output=True, text=True, check=True)
                logger.info(f"usbipd-win version: {result.stdout.strip()}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError("usbipd-win is not installed or not accessible")
            
            # Check for WSL2
            try:
                result = subprocess.run(['wsl', '--list', '--verbose'], 
                                      capture_output=True, text=True, check=True)
                if 'VERSION 2' not in result.stdout:
                    raise RuntimeError("WSL2 is not available")
                logger.info("WSL2 is available")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError("WSL is not installed")
        else:
            # Linux/WSL environment
            if not os.path.exists('/dev/bus/usb'):
                raise RuntimeError("/dev/bus/usb not found - USB subsystem not available")
    
    def list_devices(self) -> List[LabJackDevice]:
        """List all LabJack devices"""
        devices = []
        
        if self.is_windows:
            devices = self._list_devices_windows()
        else:
            devices = self._list_devices_linux()
        
        # Identify device types
        for device in devices:
            if device.product_id in self.DEVICE_TYPES:
                device.device_type = self.DEVICE_TYPES[device.product_id]
        
        return devices
    
    def _list_devices_windows(self) -> List[LabJackDevice]:
        """List devices on Windows using usbipd"""
        devices = []
        
        try:
            result = subprocess.run(['usbipd', 'list'], 
                                  capture_output=True, text=True, check=True)
            
            for line in result.stdout.split('\n')[2:]:  # Skip header
                if line.strip() and '0cd5:' in line:  # LabJack vendor ID
                    parts = line.split()
                    if len(parts) >= 4:
                        bus_id = parts[0]
                        vid_pid = parts[1]
                        description = ' '.join(parts[2:-1])
                        state = parts[-1]
                        
                        devices.append(LabJackDevice(
                            bus_id=bus_id,
                            vid_pid=vid_pid,
                            description=description,
                            state=state
                        ))
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list USB devices: {e}")
        
        return devices
    
    def _list_devices_linux(self) -> List[LabJackDevice]:
        """List devices on Linux using lsusb"""
        devices = []
        
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True, check=True)
            
            for line in result.stdout.split('\n'):
                if '0cd5:' in line:  # LabJack vendor ID
                    # Parse lsusb output: Bus 001 Device 002: ID 0cd5:0009 LabJack U3
                    parts = line.split()
                    if len(parts) >= 6:
                        bus = parts[1]
                        device = parts[3].rstrip(':')
                        vid_pid = parts[5]
                        description = ' '.join(parts[6:])
                        
                        devices.append(LabJackDevice(
                            bus_id=f"{bus}-{device}",
                            vid_pid=vid_pid,
                            description=description,
                            state='Attached'  # If visible in Linux, it's attached
                        ))
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list USB devices: {e}")
        
        return devices
    
    def bind_device(self, bus_id: str) -> bool:
        """Bind device for sharing (Windows only)"""
        if not self.is_windows:
            logger.warning("Bind operation only available on Windows")
            return False
        
        try:
            result = subprocess.run(['usbipd', 'bind', '--busid', bus_id],
                                  capture_output=True, text=True, check=True)
            logger.info(f"Device {bus_id} bound successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to bind device {bus_id}: {e.stderr}")
            return False
    
    def unbind_device(self, bus_id: str) -> bool:
        """Unbind device (Windows only)"""
        if not self.is_windows:
            logger.warning("Unbind operation only available on Windows")
            return False
        
        try:
            result = subprocess.run(['usbipd', 'unbind', '--busid', bus_id],
                                  capture_output=True, text=True, check=True)
            logger.info(f"Device {bus_id} unbound successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to unbind device {bus_id}: {e.stderr}")
            return False
    
    def attach_device(self, bus_id: str) -> bool:
        """Attach device to WSL (Windows only)"""
        if not self.is_windows:
            logger.warning("Attach operation only available on Windows")
            return False
        
        try:
            result = subprocess.run(['usbipd', 'attach', '--wsl', self.wsl_distribution, '--busid', bus_id],
                                  capture_output=True, text=True, check=True)
            logger.info(f"Device {bus_id} attached to WSL successfully")
            
            # Verify attachment
            time.sleep(2)  # Give time for device to appear
            if self._verify_device_in_wsl(bus_id):
                logger.info(f"Device {bus_id} verified in WSL")
                return True
            else:
                logger.warning(f"Device {bus_id} attached but not visible in WSL")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to attach device {bus_id}: {e.stderr}")
            return False
    
    def detach_device(self, bus_id: str) -> bool:
        """Detach device from WSL (Windows only)"""
        if not self.is_windows:
            logger.warning("Detach operation only available on Windows")
            return False
        
        try:
            result = subprocess.run(['usbipd', 'detach', '--busid', bus_id],
                                  capture_output=True, text=True, check=True)
            logger.info(f"Device {bus_id} detached successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to detach device {bus_id}: {e.stderr}")
            return False
    
    def _verify_device_in_wsl(self, bus_id: str) -> bool:
        """Verify device is visible in WSL"""
        try:
            if self.is_windows:
                result = subprocess.run(['wsl', '-d', self.wsl_distribution, 'lsusb'],
                                      capture_output=True, text=True, check=True)
            else:
                result = subprocess.run(['lsusb'], capture_output=True, text=True, check=True)
            
            return '0cd5:' in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    def test_device_connection(self, device_type: Optional[str] = None) -> Dict[str, any]:
        """Test LabJack device connection"""
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'device_info': None,
            'tests': {},
            'errors': []
        }
        
        try:
            # Import LabJack library based on device type
            if device_type and device_type.upper() in ['U3', 'U6', 'UE9']:
                if device_type.upper() == 'U3':
                    import u3 as labjack_module
                    device_class = u3.U3
                elif device_type.upper() == 'U6':
                    import u6 as labjack_module
                    device_class = u6.U6
                elif device_type.upper() == 'UE9':
                    import ue9 as labjack_module
                    device_class = ue9.UE9
            else:
                # Try U3 as default
                import u3 as labjack_module
                device_class = u3.U3
            
            # Test device connection
            logger.info("Testing device connection...")
            device = device_class()
            
            try:
                # Get device information
                device_name = device.getName()
                device_serial = getattr(device, 'serialNumber', 'Unknown')
                
                test_results['device_info'] = {
                    'name': device_name,
                    'serial': device_serial,
                    'type': device_type or 'Unknown'
                }
                
                logger.info(f"Connected to: {device_name} (Serial: {device_serial})")
                
                # Test analog input reading
                logger.info("Testing analog input reading...")
                try:
                    voltage = device.getAIN(0)
                    test_results['tests']['analog_input'] = {
                        'success': True,
                        'voltage': voltage,
                        'channel': 0
                    }
                    logger.info(f"Channel 0 voltage: {voltage:.3f}V")
                except Exception as e:
                    test_results['tests']['analog_input'] = {
                        'success': False,
                        'error': str(e)
                    }
                    logger.error(f"Analog input test failed: {e}")
                
                # Test digital I/O
                logger.info("Testing digital I/O...")
                try:
                    # Toggle digital output
                    if hasattr(device, 'setDIOState'):
                        device.setDIOState(4, 1)  # Set FIO4 high
                        time.sleep(0.1)
                        device.setDIOState(4, 0)  # Set FIO4 low
                        
                        test_results['tests']['digital_io'] = {
                            'success': True,
                            'channel': 4
                        }
                        logger.info("Digital I/O test passed")
                    else:
                        test_results['tests']['digital_io'] = {
                            'success': False,
                            'error': 'Digital I/O not supported'
                        }
                except Exception as e:
                    test_results['tests']['digital_io'] = {
                        'success': False,
                        'error': str(e)
                    }
                    logger.error(f"Digital I/O test failed: {e}")
                
                # Test device configuration
                logger.info("Testing device configuration...")
                try:
                    if hasattr(device, 'configU3'):
                        config = device.configU3()
                        test_results['tests']['configuration'] = {
                            'success': True,
                            'config': config
                        }
                        logger.info("Configuration test passed")
                    elif hasattr(device, 'configU6'):
                        config = device.configU6()
                        test_results['tests']['configuration'] = {
                            'success': True,
                            'config': config
                        }
                        logger.info("Configuration test passed")
                    else:
                        test_results['tests']['configuration'] = {
                            'success': False,
                            'error': 'Configuration not supported'
                        }
                except Exception as e:
                    test_results['tests']['configuration'] = {
                        'success': False,
                        'error': str(e)
                    }
                    logger.error(f"Configuration test failed: {e}")
                
                test_results['success'] = True
                logger.info("Device test completed successfully")
                
            finally:
                device.close()
                
        except ImportError as e:
            error_msg = f"LabJack library not available: {e}"
            test_results['errors'].append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Device connection failed: {e}"
            test_results['errors'].append(error_msg)
            logger.error(error_msg)
        
        return test_results
    
    def monitor_devices(self, duration: int = 60, interval: int = 5) -> Dict[str, any]:
        """Monitor device status over time"""
        logger.info(f"Starting device monitoring for {duration} seconds (interval: {interval}s)")
        
        monitoring_data = {
            'start_time': datetime.now().isoformat(),
            'duration': duration,
            'interval': interval,
            'samples': []
        }
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            sample_time = datetime.now().isoformat()
            devices = self.list_devices()
            
            sample = {
                'timestamp': sample_time,
                'device_count': len(devices),
                'devices': [
                    {
                        'bus_id': d.bus_id,
                        'device_type': d.device_type,
                        'state': d.state
                    } for d in devices
                ]
            }
            
            monitoring_data['samples'].append(sample)
            logger.info(f"Sample {len(monitoring_data['samples'])}: {len(devices)} devices detected")
            
            time.sleep(interval)
        
        monitoring_data['end_time'] = datetime.now().isoformat()
        return monitoring_data
    
    def generate_device_report(self, include_tests: bool = False) -> Dict[str, any]:
        """Generate comprehensive device report"""
        logger.info("Generating device report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'platform': self.platform,
            'wsl_distribution': self.wsl_distribution if self.is_windows else 'N/A',
            'devices': [],
            'summary': {
                'total_devices': 0,
                'device_types': {},
                'attached_devices': 0,
                'available_devices': 0
            }
        }
        
        devices = self.list_devices()
        report['summary']['total_devices'] = len(devices)
        
        for device in devices:
            device_info = {
                'bus_id': device.bus_id,
                'vid_pid': device.vid_pid,
                'description': device.description,
                'state': device.state,
                'device_type': device.device_type
            }
            
            # Count device types
            if device.device_type:
                if device.device_type not in report['summary']['device_types']:
                    report['summary']['device_types'][device.device_type] = 0
                report['summary']['device_types'][device.device_type] += 1
            
            # Count states
            if 'Attached' in device.state or 'attached' in device.state:
                report['summary']['attached_devices'] += 1
            elif 'Not shared' in device.state or 'Available' in device.state:
                report['summary']['available_devices'] += 1
            
            # Include test results if requested
            if include_tests:
                logger.info(f"Testing device: {device}")
                test_results = self.test_device_connection(device.device_type)
                device_info['test_results'] = test_results
            
            report['devices'].append(device_info)
        
        return report
    
    def save_report(self, report: Dict[str, any], filename: Optional[str] = None) -> str:
        """Save report to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"labjack_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to: {filename}")
        return filename

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='LabJack USB Passthrough Device Manager')
    parser.add_argument('--wsl-distribution', default='Ubuntu',
                       help='WSL distribution name (default: Ubuntu)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List LabJack devices')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Bind command
    bind_parser = subparsers.add_parser('bind', help='Bind device for sharing')
    bind_parser.add_argument('bus_id', help='Device bus ID to bind')
    
    # Unbind command
    unbind_parser = subparsers.add_parser('unbind', help='Unbind device')
    unbind_parser.add_argument('bus_id', help='Device bus ID to unbind')
    
    # Attach command
    attach_parser = subparsers.add_parser('attach', help='Attach device to WSL')
    attach_parser.add_argument('bus_id', nargs='?', help='Device bus ID to attach (optional, will attach all if omitted)')
    
    # Detach command
    detach_parser = subparsers.add_parser('detach', help='Detach device from WSL')
    detach_parser.add_argument('bus_id', nargs='?', help='Device bus ID to detach (optional, will detach all if omitted)')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test device connection')
    test_parser.add_argument('--device-type', choices=['u3', 'u6', 'ue9'],
                           help='Specify device type for testing')
    test_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor devices over time')
    monitor_parser.add_argument('--duration', type=int, default=60,
                               help='Monitoring duration in seconds (default: 60)')
    monitor_parser.add_argument('--interval', type=int, default=5,
                               help='Sample interval in seconds (default: 5)')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate device report')
    report_parser.add_argument('--include-tests', action='store_true',
                              help='Include device tests in report')
    report_parser.add_argument('--output', help='Output filename')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        manager = LabJackManager(args.wsl_distribution)
        
        if args.command == 'list':
            devices = manager.list_devices()
            
            if args.json:
                device_data = [
                    {
                        'bus_id': d.bus_id,
                        'vid_pid': d.vid_pid,
                        'description': d.description,
                        'state': d.state,
                        'device_type': d.device_type
                    } for d in devices
                ]
                print(json.dumps(device_data, indent=2))
            else:
                if devices:
                    print(f"\nFound {len(devices)} LabJack device(s):")
                    for device in devices:
                        type_info = f" [{device.device_type}]" if device.device_type else ""
                        print(f"  {device}{type_info}")
                else:
                    print("No LabJack devices found")
        
        elif args.command == 'bind':
            success = manager.bind_device(args.bus_id)
            return 0 if success else 1
        
        elif args.command == 'unbind':
            success = manager.unbind_device(args.bus_id)
            return 0 if success else 1
        
        elif args.command == 'attach':
            if args.bus_id:
                success = manager.attach_device(args.bus_id)
                return 0 if success else 1
            else:
                # Attach all devices
                devices = manager.list_devices()
                all_success = True
                for device in devices:
                    if device.state != 'Attached':
                        if device.state != 'Shared':
                            manager.bind_device(device.bus_id)
                        success = manager.attach_device(device.bus_id)
                        all_success = all_success and success
                return 0 if all_success else 1
        
        elif args.command == 'detach':
            if args.bus_id:
                success = manager.detach_device(args.bus_id)
                return 0 if success else 1
            else:
                # Detach all devices
                devices = manager.list_devices()
                all_success = True
                for device in devices:
                    success = manager.detach_device(device.bus_id)
                    all_success = all_success and success
                return 0 if all_success else 1
        
        elif args.command == 'test':
            test_results = manager.test_device_connection(args.device_type)
            
            if args.json:
                print(json.dumps(test_results, indent=2))
            else:
                print(f"\nDevice Test Results:")
                print(f"Success: {test_results['success']}")
                if test_results['device_info']:
                    info = test_results['device_info']
                    print(f"Device: {info['name']} (Serial: {info['serial']})")
                
                for test_name, test_result in test_results['tests'].items():
                    status = "PASS" if test_result['success'] else "FAIL"
                    print(f"{test_name.replace('_', ' ').title()}: {status}")
                    if not test_result['success'] and 'error' in test_result:
                        print(f"  Error: {test_result['error']}")
                
                if test_results['errors']:
                    print("Errors:")
                    for error in test_results['errors']:
                        print(f"  {error}")
            
            return 0 if test_results['success'] else 1
        
        elif args.command == 'monitor':
            monitoring_data = manager.monitor_devices(args.duration, args.interval)
            
            print(f"\nDevice Monitoring Results:")
            print(f"Duration: {monitoring_data['duration']} seconds")
            print(f"Samples: {len(monitoring_data['samples'])}")
            
            # Show summary statistics
            device_counts = [sample['device_count'] for sample in monitoring_data['samples']]
            if device_counts:
                print(f"Device count - Min: {min(device_counts)}, Max: {max(device_counts)}, Avg: {sum(device_counts)/len(device_counts):.1f}")
        
        elif args.command == 'report':
            report = manager.generate_device_report(args.include_tests)
            filename = manager.save_report(report, args.output)
            
            print(f"\nDevice Report Generated: {filename}")
            print(f"Total Devices: {report['summary']['total_devices']}")
            print(f"Attached: {report['summary']['attached_devices']}")
            print(f"Available: {report['summary']['available_devices']}")
            
            if report['summary']['device_types']:
                print("Device Types:")
                for device_type, count in report['summary']['device_types'].items():
                    print(f"  {device_type}: {count}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())