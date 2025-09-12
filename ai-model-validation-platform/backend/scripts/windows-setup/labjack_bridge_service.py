#!/usr/bin/env python3
"""
LabJack Bridge Service for Windows
Provides shared folder communication bridge between Windows LabJack and WSL backend

This service runs on Windows and monitors a shared directory for requests from WSL.
It handles LabJack hardware operations and returns results via file communication.

Usage:
    python labjack_bridge_service.py [--bridge-path C:\temp\labjack_bridge]
"""

import os
import sys
import json
import time
import threading
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Try to import LabJack library
try:
    import labjack.ljm as ljm
    LABJACK_AVAILABLE = True
    print("✅ LabJack library imported successfully")
except ImportError as e:
    LABJACK_AVAILABLE = False
    print(f"⚠️ LabJack library not available: {e}")
    print("💡 Install with: pip install labjack-ljm")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('labjack_bridge.log')
    ]
)
logger = logging.getLogger(__name__)

class LabJackBridgeService:
    """Windows bridge service for LabJack hardware access from WSL"""
    
    def __init__(self, bridge_path="C:\\temp\\labjack_bridge"):
        self.bridge_path = Path(bridge_path)
        self.labjack_handle = None
        self.device_info = {}
        self.running = False
        self.request_count = 0
        
        # Create bridge directory
        self.bridge_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Bridge path: {self.bridge_path}")
        
        # Initialize LabJack connection
        if LABJACK_AVAILABLE:
            self.connect_labjack()
        else:
            logger.warning("LabJack library not available - running in offline mode")
        
    def connect_labjack(self):
        """Connect to LabJack device"""
        try:
            logger.info("Attempting to connect to LabJack...")
            
            # Try to open any LabJack device
            self.labjack_handle = ljm.openS("ANY", "ANY", "ANY")
            
            # Get device information
            info = ljm.getHandleInfo(self.labjack_handle)
            device_type = ljm.numberToType(info[0])
            connection_type = ljm.numberToConnectionType(info[1])
            serial_number = info[2]
            
            self.device_info = {
                "device_type": device_type,
                "connection_type": connection_type,
                "serial_number": serial_number,
                "firmware_version": ljm.eReadName(self.labjack_handle, "FIRMWARE_VERSION"),
                "bootloader_version": ljm.eReadName(self.labjack_handle, "BOOTLOADER_VERSION"),
                "hardware_version": ljm.eReadName(self.labjack_handle, "HARDWARE_VERSION")
            }
            
            logger.info("🎉 LabJack connected successfully!")
            logger.info(f"   Device: {device_type}")
            logger.info(f"   Connection: {connection_type}")
            logger.info(f"   Serial: {serial_number}")
            logger.info(f"   Firmware: {self.device_info['firmware_version']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ LabJack connection failed: {e}")
            self.labjack_handle = None
            self.device_info = {}
            return False
    
    def disconnect_labjack(self):
        """Disconnect from LabJack device"""
        if self.labjack_handle:
            try:
                ljm.close(self.labjack_handle)
                self.labjack_handle = None
                self.device_info = {}
                logger.info("🔌 LabJack disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting LabJack: {e}")
    
    def process_requests(self):
        """Main request processing loop"""
        logger.info("🔄 Starting request processing loop...")
        
        request_file = self.bridge_path / "request.json"
        response_file = self.bridge_path / "response.json"
        
        while self.running:
            try:
                if request_file.exists():
                    # Read request
                    with open(request_file, 'r') as f:
                        request = json.load(f)
                    
                    self.request_count += 1
                    logger.info(f"📥 Processing request #{self.request_count}: {request.get('action', 'unknown')}")
                    
                    # Process request
                    response = self.handle_request(request)
                    response["request_id"] = self.request_count
                    response["processed_at"] = datetime.now().isoformat()
                    
                    # Write response
                    with open(response_file, 'w') as f:
                        json.dump(response, f, indent=2)
                    
                    # Remove request file
                    request_file.unlink()
                    
                    logger.info(f"📤 Response sent for request #{self.request_count}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in request: {e}")
                # Remove invalid request file
                try:
                    request_file.unlink()
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Request processing error: {e}")
            
            # Check every 100ms
            time.sleep(0.1)
    
    def handle_request(self, request):
        """Handle specific request types"""
        action = request.get("action", "")
        timestamp = datetime.now().isoformat()
        
        try:
            if action == "status":
                return self.handle_status_request(request)
                
            elif action == "device_info":
                return self.handle_device_info_request(request)
                
            elif action == "read_digital":
                return self.handle_read_digital_request(request)
                
            elif action == "read_analog":
                return self.handle_read_analog_request(request)
                
            elif action == "write_digital":
                return self.handle_write_digital_request(request)
                
            elif action == "write_analog":
                return self.handle_write_analog_request(request)
                
            elif action == "stream_start":
                return self.handle_stream_start_request(request)
                
            elif action == "stream_read":
                return self.handle_stream_read_request(request)
                
            elif action == "stream_stop":
                return self.handle_stream_stop_request(request)
                
            elif action == "reconnect":
                return self.handle_reconnect_request(request)
                
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "timestamp": timestamp
                }
                
        except Exception as e:
            logger.error(f"Error handling {action} request: {e}")
            return {
                "success": False,
                "error": str(e),
                "action": action,
                "timestamp": timestamp
            }
    
    def handle_status_request(self, request):
        """Handle status request"""
        return {
            "success": True,
            "connected": self.labjack_handle is not None,
            "device_type": self.device_info.get("device_type", "Unknown"),
            "connection_type": self.device_info.get("connection_type", "Unknown"),
            "serial_number": self.device_info.get("serial_number"),
            "method": "shared_folder",
            "bridge_active": True,
            "requests_processed": self.request_count,
            "timestamp": datetime.now().isoformat()
        }
    
    def handle_device_info_request(self, request):
        """Handle device info request"""
        if not self.labjack_handle:
            return {
                "success": False,
                "error": "LabJack not connected",
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "success": True,
            "device_info": self.device_info,
            "timestamp": datetime.now().isoformat()
        }
    
    def handle_read_digital_request(self, request):
        """Handle digital input read request"""
        if not self.labjack_handle:
            return {
                "success": False,
                "error": "LabJack not connected",
                "timestamp": datetime.now().isoformat()
            }
        
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
            return {
                "success": False,
                "error": str(e),
                "channel": request.get("channel", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
    
    def handle_read_analog_request(self, request):
        """Handle analog input read request"""
        if not self.labjack_handle:
            return {
                "success": False,
                "error": "LabJack not connected",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            channel = request.get("channel", "AIN0")
            value = ljm.eReadName(self.labjack_handle, channel)
            
            return {
                "success": True,
                "value": float(value),
                "channel": channel,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "channel": request.get("channel", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
    
    def handle_write_digital_request(self, request):
        """Handle digital output write request"""
        if not self.labjack_handle:
            return {
                "success": False,
                "error": "LabJack not connected",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            channel = request.get("channel", "DIO1")
            value = request.get("value", 0)
            
            ljm.eWriteName(self.labjack_handle, channel, int(value))
            
            return {
                "success": True,
                "channel": channel,
                "value": int(value),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "channel": request.get("channel", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
    
    def handle_write_analog_request(self, request):
        """Handle analog output write request"""
        if not self.labjack_handle:
            return {
                "success": False,
                "error": "LabJack not connected",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            channel = request.get("channel", "DAC0")
            value = request.get("value", 0.0)
            
            ljm.eWriteName(self.labjack_handle, channel, float(value))
            
            return {
                "success": True,
                "channel": channel,
                "value": float(value),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "channel": request.get("channel", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
    
    def handle_reconnect_request(self, request):
        """Handle reconnection request"""
        logger.info("🔄 Reconnection requested")
        
        # Disconnect if connected
        if self.labjack_handle:
            self.disconnect_labjack()
        
        # Wait a moment
        time.sleep(1)
        
        # Try to reconnect
        if LABJACK_AVAILABLE:
            success = self.connect_labjack()
            return {
                "success": success,
                "connected": success,
                "message": "Reconnection successful" if success else "Reconnection failed",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "LabJack library not available",
                "timestamp": datetime.now().isoformat()
            }
    
    def handle_stream_start_request(self, request):
        """Handle stream start request (placeholder)"""
        return {
            "success": False,
            "error": "Streaming not implemented in bridge service",
            "timestamp": datetime.now().isoformat()
        }
    
    def handle_stream_read_request(self, request):
        """Handle stream read request (placeholder)"""
        return {
            "success": False,
            "error": "Streaming not implemented in bridge service",
            "timestamp": datetime.now().isoformat()
        }
    
    def handle_stream_stop_request(self, request):
        """Handle stream stop request (placeholder)"""
        return {
            "success": False,
            "error": "Streaming not implemented in bridge service",
            "timestamp": datetime.now().isoformat()
        }
    
    def start(self):
        """Start the bridge service"""
        logger.info("🚀 Starting LabJack Bridge Service")
        logger.info(f"   Bridge path: {self.bridge_path}")
        logger.info(f"   LabJack library: {'Available' if LABJACK_AVAILABLE else 'Not Available'}")
        logger.info(f"   Hardware connected: {'Yes' if self.labjack_handle else 'No'}")
        
        # Create status file
        status_file = self.bridge_path / "bridge_status.json"
        with open(status_file, 'w') as f:
            json.dump({
                "service": "LabJack Bridge Service",
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "bridge_path": str(self.bridge_path),
                "labjack_available": LABJACK_AVAILABLE,
                "hardware_connected": self.labjack_handle is not None,
                "device_info": self.device_info
            }, f, indent=2)
        
        self.running = True
        
        # Start request processing thread
        process_thread = threading.Thread(target=self.process_requests, daemon=True)
        process_thread.start()
        
        logger.info("✅ Bridge service is running")
        logger.info("📂 Monitoring for requests in: {self.bridge_path}")
        logger.info("🛑 Press Ctrl+C to stop")
        
        try:
            # Main loop - just keep alive
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Stopping bridge service...")
            self.running = False
            
            # Clean shutdown
            if self.labjack_handle:
                self.disconnect_labjack()
            
            # Remove status file
            try:
                status_file.unlink()
            except:
                pass
            
            logger.info("✅ Bridge service stopped")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="LabJack Bridge Service for Windows/WSL")
    parser.add_argument(
        "--bridge-path", 
        default="C:\\temp\\labjack_bridge",
        help="Path for shared communication directory"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create service
    service = LabJackBridgeService(args.bridge_path)
    
    # Start service
    service.start()

if __name__ == "__main__":
    main()