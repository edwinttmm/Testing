"""
Simple LabJack Bridge Service for Windows
Provides HTTP API for WSL backend to communicate with LabJack hardware
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

# Create FastAPI app
app = FastAPI(title="LabJack Bridge Service")

# Enable CORS for WSL access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock LabJack state (replace with actual LabJack library when available)
labjack_state = {
    "connected": False,
    "device_id": None,
    "mode": "mock",
    "streaming": False,
    "last_values": {}
}

@app.get("/")
def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "LabJack Bridge", "time": datetime.now().isoformat()}

@app.get("/api/health")
def health_check():
    """Service health status"""
    return {
        "status": "healthy",
        "mode": labjack_state["mode"],
        "connected": labjack_state["connected"],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/devices")
def get_devices():
    """Get available LabJack devices"""
    # In real implementation, scan for devices
    return {
        "devices": [
            {"id": "MOCK-001", "type": "T7", "connection": "USB", "status": "available"}
        ] if not labjack_state["connected"] else []
    }

@app.post("/api/devices/{device_id}/connect")
def connect_device(device_id: str):
    """Connect to a LabJack device"""
    labjack_state["connected"] = True
    labjack_state["device_id"] = device_id
    return {
        "success": True,
        "device_id": device_id,
        "message": f"Connected to {device_id} (mock mode)"
    }

@app.delete("/api/devices/{device_id}/disconnect")
def disconnect_device(device_id: str):
    """Disconnect from LabJack device"""
    labjack_state["connected"] = False
    labjack_state["device_id"] = None
    return {"success": True, "message": "Disconnected"}

@app.post("/api/analog/read")
async def read_analog(data: Dict[str, Any]):
    """Read analog input channels"""
    if not labjack_state["connected"]:
        raise HTTPException(status_code=400, detail="No device connected")
    
    channels = data.get("channels", [0, 1, 2, 3])
    # Mock voltage readings
    import random
    values = [round(random.uniform(0, 5), 3) for _ in channels]
    
    labjack_state["last_values"] = dict(zip(channels, values))
    
    return {
        "success": True,
        "channels": channels,
        "values": values,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/analog/write")
async def write_analog(data: Dict[str, Any]):
    """Write analog output channels"""
    if not labjack_state["connected"]:
        raise HTTPException(status_code=400, detail="No device connected")
    
    channel = data.get("channel", 0)
    value = data.get("value", 0.0)
    
    return {
        "success": True,
        "channel": channel,
        "value": value,
        "message": f"Set channel {channel} to {value}V (mock)"
    }

@app.post("/api/streaming/start")
async def start_streaming(data: Dict[str, Any]):
    """Start data streaming"""
    if not labjack_state["connected"]:
        raise HTTPException(status_code=400, detail="No device connected")
    
    labjack_state["streaming"] = True
    channels = data.get("channels", ["AIN0", "AIN1"])
    scan_rate = data.get("scan_rate", 1000)
    
    return {
        "success": True,
        "streaming": True,
        "channels": channels,
        "scan_rate": scan_rate,
        "message": "Streaming started (mock mode)"
    }

@app.post("/api/streaming/stop/{device_id}")
async def stop_streaming(device_id: str):
    """Stop data streaming"""
    labjack_state["streaming"] = False
    return {
        "success": True,
        "streaming": False,
        "message": "Streaming stopped"
    }

@app.get("/api/status")
def get_status():
    """Get current bridge status"""
    return {
        "bridge_status": "operational",
        "labjack_state": labjack_state,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("="*60)
    print("LabJack Bridge Service")
    print("="*60)
    print("Starting server on http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("="*60)
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8080)