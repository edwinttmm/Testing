"""
LabJack Bridge Service - Windows Service Implementation
Provides HTTP REST API and WebSocket streaming for LabJack hardware communication
"""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import socket
import sys
import os

# Third-party imports
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import websockets

# Windows service imports
try:
    import win32service
    import win32serviceutil
    import win32event
    import servicemanager
    WINDOWS_SERVICE_AVAILABLE = True
except ImportError:
    WINDOWS_SERVICE_AVAILABLE = False
    print("Warning: Windows service modules not available. Running in standalone mode.")

# LabJack imports
try:
    from labjack import ljm
    LABJACK_AVAILABLE = True
except ImportError:
    LABJACK_AVAILABLE = False
    print("Warning: LabJack modules not available. Running in mock mode.")

# Configuration
SERVICE_NAME = "LabJackBridgeService"
SERVICE_DISPLAY_NAME = "LabJack Bridge Service"
SERVICE_DESCRIPTION = "Provides HTTP and WebSocket API for LabJack hardware communication"

# Data models
class LabJackDevice(BaseModel):
    device_type: str
    connection_type: str
    identifier: str
    handle: Optional[int] = None
    serial_number: Optional[int] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None

class AnalogReadRequest(BaseModel):
    device_id: str
    channels: List[int]
    resolution_index: Optional[int] = 0
    settling_time: Optional[float] = 0

class AnalogWriteRequest(BaseModel):
    device_id: str
    channel: int
    voltage: float

class DigitalReadRequest(BaseModel):
    device_id: str
    channels: List[int]

class DigitalWriteRequest(BaseModel):
    device_id: str
    channel: int
    state: bool

class StreamingConfig(BaseModel):
    device_id: str
    channels: List[int]
    scan_rate: float = 1000.0
    scans_per_read: int = 100
    buffer_size: int = 10000

class LabJackBridgeAPI:
    """Main API class for LabJack bridge functionality"""
    
    def __init__(self):
        self.devices: Dict[str, LabJackDevice] = {}
        self.device_handles: Dict[str, int] = {}
        self.streaming_active: Dict[str, bool] = {}
        self.websocket_clients: List[WebSocket] = []
        self.logger = self._setup_logging()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="LabJack Bridge API",
            description="REST and WebSocket API for LabJack hardware communication",
            version="1.0.0"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self._setup_routes()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("LabJackBridge")
        logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # File handler
        log_file = os.path.join(log_dir, f"labjack_bridge_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "labjack_available": LABJACK_AVAILABLE,
                "devices_connected": len(self.devices)
            }
        
        @self.app.get("/api/devices")
        async def list_devices():
            """List all connected LabJack devices"""
            try:
                devices = self.discover_devices()
                return {"devices": devices}
            except Exception as e:
                self.logger.error(f"Error listing devices: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/devices/{device_id}/connect")
        async def connect_device(device_id: str):
            """Connect to a specific LabJack device"""
            try:
                result = self.connect_device(device_id)
                return result
            except Exception as e:
                self.logger.error(f"Error connecting to device {device_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/devices/{device_id}/disconnect")
        async def disconnect_device(device_id: str):
            """Disconnect from a specific LabJack device"""
            try:
                result = self.disconnect_device(device_id)
                return result
            except Exception as e:
                self.logger.error(f"Error disconnecting from device {device_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/analog/read")
        async def read_analog(request: AnalogReadRequest):
            """Read analog values from LabJack device"""
            try:
                result = self.read_analog_channels(
                    request.device_id,
                    request.channels,
                    request.resolution_index,
                    request.settling_time
                )
                return result
            except Exception as e:
                self.logger.error(f"Error reading analog channels: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/analog/write")
        async def write_analog(request: AnalogWriteRequest):
            """Write analog value to LabJack device"""
            try:
                result = self.write_analog_channel(
                    request.device_id,
                    request.channel,
                    request.voltage
                )
                return result
            except Exception as e:
                self.logger.error(f"Error writing analog channel: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/digital/read")
        async def read_digital(request: DigitalReadRequest):
            """Read digital values from LabJack device"""
            try:
                result = self.read_digital_channels(
                    request.device_id,
                    request.channels
                )
                return result
            except Exception as e:
                self.logger.error(f"Error reading digital channels: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/digital/write")
        async def write_digital(request: DigitalWriteRequest):
            """Write digital value to LabJack device"""
            try:
                result = self.write_digital_channel(
                    request.device_id,
                    request.channel,
                    request.state
                )
                return result
            except Exception as e:
                self.logger.error(f"Error writing digital channel: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/streaming/start")
        async def start_streaming(config: StreamingConfig, background_tasks: BackgroundTasks):
            """Start streaming data from LabJack device"""
            try:
                background_tasks.add_task(self.start_streaming, config)
                return {"status": "streaming_started", "device_id": config.device_id}
            except Exception as e:
                self.logger.error(f"Error starting streaming: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/streaming/stop/{device_id}")
        async def stop_streaming(device_id: str):
            """Stop streaming data from LabJack device"""
            try:
                result = self.stop_streaming(device_id)
                return result
            except Exception as e:
                self.logger.error(f"Error stopping streaming: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws/stream")
        async def websocket_stream(websocket: WebSocket):
            """WebSocket endpoint for real-time data streaming"""
            await websocket.accept()
            self.websocket_clients.append(websocket)
            self.logger.info(f"WebSocket client connected. Total clients: {len(self.websocket_clients)}")
            
            try:
                while True:
                    # Keep connection alive
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.websocket_clients.remove(websocket)
                self.logger.info(f"WebSocket client disconnected. Total clients: {len(self.websocket_clients)}")
    
    def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover available LabJack devices"""
        devices = []
        
        if not LABJACK_AVAILABLE:
            # Mock devices for testing
            devices.append({
                "device_type": "T7",
                "connection_type": "TCP",
                "identifier": "192.168.1.100",
                "serial_number": 470010001,
                "status": "available"
            })
            return devices
        
        try:
            # Discover USB devices
            device_info = ljm.listAll(ljm.constants.dtANY, ljm.constants.ctUSB)
            for i in range(len(device_info[0])):
                device_type = ljm.numberToDeviceType(device_info[0][i])
                serial_number = device_info[2][i]
                devices.append({
                    "device_type": device_type,
                    "connection_type": "USB",
                    "identifier": f"USB_{serial_number}",
                    "serial_number": serial_number,
                    "status": "available"
                })
            
            # Discover TCP devices (scan common IP range)
            for i in range(100, 110):
                try:
                    ip = f"192.168.1.{i}"
                    handle = ljm.openS("ANY", "TCP", ip)
                    device_type = ljm.eReadName(handle, "DEVICE_NAME_DEFAULT")
                    serial_number = ljm.eReadName(handle, "SERIAL_NUMBER")
                    ljm.close(handle)
                    
                    devices.append({
                        "device_type": device_type,
                        "connection_type": "TCP",
                        "identifier": ip,
                        "serial_number": int(serial_number),
                        "status": "available"
                    })
                except:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error discovering devices: {e}")
        
        return devices
    
    def connect_device(self, device_id: str) -> Dict[str, Any]:
        """Connect to a LabJack device"""
        if not LABJACK_AVAILABLE:
            # Mock connection
            self.devices[device_id] = LabJackDevice(
                device_type="T7",
                connection_type="TCP",
                identifier=device_id,
                handle=12345
            )
            self.device_handles[device_id] = 12345
            return {"status": "connected", "device_id": device_id, "handle": 12345}
        
        try:
            # Determine connection type and parameters
            if device_id.startswith("USB_"):
                serial_number = device_id.replace("USB_", "")
                handle = ljm.openS("ANY", "USB", serial_number)
            else:
                # Assume TCP connection
                handle = ljm.openS("ANY", "TCP", device_id)
            
            # Get device info
            device_type = ljm.eReadName(handle, "DEVICE_NAME_DEFAULT")
            serial_number = ljm.eReadName(handle, "SERIAL_NUMBER")
            
            device = LabJackDevice(
                device_type=device_type,
                connection_type="TCP" if not device_id.startswith("USB_") else "USB",
                identifier=device_id,
                handle=handle,
                serial_number=int(serial_number)
            )
            
            self.devices[device_id] = device
            self.device_handles[device_id] = handle
            
            self.logger.info(f"Connected to device {device_id} (handle: {handle})")
            
            return {
                "status": "connected",
                "device_id": device_id,
                "handle": handle,
                "device_type": device_type,
                "serial_number": int(serial_number)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to connect to device {device_id}: {e}")
            raise Exception(f"Failed to connect to device: {e}")
    
    def disconnect_device(self, device_id: str) -> Dict[str, Any]:
        """Disconnect from a LabJack device"""
        if device_id not in self.device_handles:
            raise Exception(f"Device {device_id} not connected")
        
        try:
            # Stop streaming if active
            if device_id in self.streaming_active and self.streaming_active[device_id]:
                self.stop_streaming(device_id)
            
            if LABJACK_AVAILABLE:
                handle = self.device_handles[device_id]
                ljm.close(handle)
            
            del self.devices[device_id]
            del self.device_handles[device_id]
            
            self.logger.info(f"Disconnected from device {device_id}")
            
            return {"status": "disconnected", "device_id": device_id}
            
        except Exception as e:
            self.logger.error(f"Failed to disconnect from device {device_id}: {e}")
            raise Exception(f"Failed to disconnect from device: {e}")
    
    def read_analog_channels(self, device_id: str, channels: List[int], 
                           resolution_index: int = 0, settling_time: float = 0) -> Dict[str, Any]:
        """Read analog input channels"""
        if device_id not in self.device_handles:
            raise Exception(f"Device {device_id} not connected")
        
        if not LABJACK_AVAILABLE:
            # Mock data
            values = [2.5 + 0.1 * ch for ch in channels]
            return {
                "device_id": device_id,
                "channels": channels,
                "values": values,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            handle = self.device_handles[device_id]
            
            # Configure resolution and settling time if needed
            if resolution_index > 0:
                ljm.eWriteName(handle, "AIN_RESOLUTION_INDEX", resolution_index)
            if settling_time > 0:
                ljm.eWriteName(handle, "AIN_SETTLING_US", settling_time)
            
            # Read channels
            names = [f"AIN{ch}" for ch in channels]
            values = ljm.eReadNames(handle, len(names), names)
            
            return {
                "device_id": device_id,
                "channels": channels,
                "values": values,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to read analog channels from {device_id}: {e}")
            raise Exception(f"Failed to read analog channels: {e}")
    
    def write_analog_channel(self, device_id: str, channel: int, voltage: float) -> Dict[str, Any]:
        """Write analog output channel"""
        if device_id not in self.device_handles:
            raise Exception(f"Device {device_id} not connected")
        
        if not LABJACK_AVAILABLE:
            # Mock write
            return {
                "device_id": device_id,
                "channel": channel,
                "voltage": voltage,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            handle = self.device_handles[device_id]
            ljm.eWriteName(handle, f"DAC{channel}", voltage)
            
            return {
                "device_id": device_id,
                "channel": channel,
                "voltage": voltage,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to write analog channel {channel} on {device_id}: {e}")
            raise Exception(f"Failed to write analog channel: {e}")
    
    def read_digital_channels(self, device_id: str, channels: List[int]) -> Dict[str, Any]:
        """Read digital input channels"""
        if device_id not in self.device_handles:
            raise Exception(f"Device {device_id} not connected")
        
        if not LABJACK_AVAILABLE:
            # Mock data
            values = [ch % 2 == 0 for ch in channels]
            return {
                "device_id": device_id,
                "channels": channels,
                "values": values,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            handle = self.device_handles[device_id]
            names = [f"DIO{ch}" for ch in channels]
            values = ljm.eReadNames(handle, len(names), names)
            boolean_values = [bool(int(v)) for v in values]
            
            return {
                "device_id": device_id,
                "channels": channels,
                "values": boolean_values,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to read digital channels from {device_id}: {e}")
            raise Exception(f"Failed to read digital channels: {e}")
    
    def write_digital_channel(self, device_id: str, channel: int, state: bool) -> Dict[str, Any]:
        """Write digital output channel"""
        if device_id not in self.device_handles:
            raise Exception(f"Device {device_id} not connected")
        
        if not LABJACK_AVAILABLE:
            # Mock write
            return {
                "device_id": device_id,
                "channel": channel,
                "state": state,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            handle = self.device_handles[device_id]
            ljm.eWriteName(handle, f"DIO{channel}", int(state))
            
            return {
                "device_id": device_id,
                "channel": channel,
                "state": state,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to write digital channel {channel} on {device_id}: {e}")
            raise Exception(f"Failed to write digital channel: {e}")
    
    async def start_streaming(self, config: StreamingConfig):
        """Start streaming data from device"""
        device_id = config.device_id
        
        if device_id not in self.device_handles:
            raise Exception(f"Device {device_id} not connected")
        
        if device_id in self.streaming_active and self.streaming_active[device_id]:
            self.logger.warning(f"Streaming already active for device {device_id}")
            return
        
        self.streaming_active[device_id] = True
        self.logger.info(f"Starting streaming for device {device_id}")
        
        try:
            if LABJACK_AVAILABLE:
                handle = self.device_handles[device_id]
                
                # Configure streaming
                scan_list_names = [f"AIN{ch}" for ch in config.channels]
                scan_list = ljm.namesToAddresses(len(scan_list_names), scan_list_names)[0]
                
                ljm.eStreamStart(handle, config.scans_per_read, len(scan_list), 
                               scan_list, config.scan_rate)
                
                # Streaming loop
                while self.streaming_active.get(device_id, False):
                    try:
                        data = ljm.eStreamRead(handle)
                        
                        # Format data
                        stream_data = {
                            "device_id": device_id,
                            "channels": config.channels,
                            "scan_rate": config.scan_rate,
                            "data": data[0],
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # Send to WebSocket clients
                        await self.broadcast_to_websockets(stream_data)
                        
                    except Exception as e:
                        self.logger.error(f"Error during streaming: {e}")
                        break
                
                # Stop streaming
                ljm.eStreamStop(handle)
            else:
                # Mock streaming
                import random
                while self.streaming_active.get(device_id, False):
                    mock_data = []
                    for _ in range(config.scans_per_read):
                        scan = [random.uniform(0, 5) for _ in config.channels]
                        mock_data.extend(scan)
                    
                    stream_data = {
                        "device_id": device_id,
                        "channels": config.channels,
                        "scan_rate": config.scan_rate,
                        "data": mock_data,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await self.broadcast_to_websockets(stream_data)
                    await asyncio.sleep(config.scans_per_read / config.scan_rate)
                    
        except Exception as e:
            self.logger.error(f"Streaming error for device {device_id}: {e}")
        finally:
            self.streaming_active[device_id] = False
            self.logger.info(f"Streaming stopped for device {device_id}")
    
    def stop_streaming(self, device_id: str) -> Dict[str, Any]:
        """Stop streaming data from device"""
        if device_id in self.streaming_active:
            self.streaming_active[device_id] = False
            self.logger.info(f"Stopping streaming for device {device_id}")
            return {"status": "streaming_stopped", "device_id": device_id}
        else:
            return {"status": "streaming_not_active", "device_id": device_id}
    
    async def broadcast_to_websockets(self, data: Dict[str, Any]):
        """Broadcast data to all connected WebSocket clients"""
        if not self.websocket_clients:
            return
        
        message = json.dumps(data)
        clients_to_remove = []
        
        for client in self.websocket_clients:
            try:
                await client.send_text(message)
            except Exception as e:
                self.logger.warning(f"Failed to send data to WebSocket client: {e}")
                clients_to_remove.append(client)
        
        # Remove disconnected clients
        for client in clients_to_remove:
            self.websocket_clients.remove(client)

class LabJackBridgeService(win32serviceutil.ServiceFramework if WINDOWS_SERVICE_AVAILABLE else object):
    """Windows Service wrapper for LabJack Bridge API"""
    
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION
    
    def __init__(self, args=None):
        if WINDOWS_SERVICE_AVAILABLE:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        
        self.is_running = True
        self.bridge_api = LabJackBridgeAPI()
        self.server_thread = None
    
    def SvcStop(self):
        """Stop the service"""
        if WINDOWS_SERVICE_AVAILABLE:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.hWaitStop)
        
        self.is_running = False
        if self.server_thread:
            self.server_thread.join(timeout=5)
    
    def SvcDoRun(self):
        """Run the service"""
        if WINDOWS_SERVICE_AVAILABLE:
            servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                                servicemanager.PYS_SERVICE_STARTED,
                                (self._svc_name_, ''))
        
        self.run_server()
    
    def run_server(self):
        """Run the FastAPI server"""
        config = uvicorn.Config(
            self.bridge_api.app,
            host="0.0.0.0",
            port=8080,
            log_level="info",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        
        # Run server in thread
        self.server_thread = threading.Thread(target=server.run)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.bridge_api.logger.info("LabJack Bridge Service started on port 8080")
        
        # Keep service running
        if WINDOWS_SERVICE_AVAILABLE:
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        else:
            try:
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.bridge_api.logger.info("Service stopped by user")

def main():
    """Main entry point"""
    if len(sys.argv) == 1:
        # Run as standalone application
        service = LabJackBridgeService()
        try:
            service.run_server()
            while service.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down service...")
            service.SvcStop()
    else:
        # Run as Windows service
        if WINDOWS_SERVICE_AVAILABLE:
            win32serviceutil.HandleCommandLine(LabJackBridgeService)
        else:
            print("Windows service modules not available. Use standalone mode.")

if __name__ == "__main__":
    main()