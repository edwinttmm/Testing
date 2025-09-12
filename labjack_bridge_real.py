"""
LabJack Bridge Service with Real Hardware Support
Provides HTTP API for WSL backend to communicate with actual LabJack hardware
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

# Try to import LabJack library
try:
    from labjack import ljm
    LABJACK_AVAILABLE = True
    print("✅ LabJack LJM library loaded successfully")
except ImportError:
    LABJACK_AVAILABLE = False
    print("⚠️ LabJack LJM library not available - install from labjack.com")

app = FastAPI(title="LabJack Bridge Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LabJack state
labjack_state = {
    "handle": None,
    "connected": False,
    "device_info": {},
    "streaming": False
}

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "LabJack Bridge",
        "time": datetime.now().isoformat(),
        "labjack_available": LABJACK_AVAILABLE
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "labjack_available": LABJACK_AVAILABLE,
        "connected": labjack_state["connected"],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/devices")
def get_devices():
    """Scan for available LabJack devices"""
    if not LABJACK_AVAILABLE:
        return {"devices": [{"id": "MOCK-001", "type": "T7", "connection": "Mock"}]}
    
    try:
        # Scan for devices
        found_devices = []
        
        # Try USB devices
        try:
            info = ljm.listAllS("USB", "ANY")
            for i in range(info[0]):
                found_devices.append({
                    "id": str(info[2][i]),
                    "type": info[3][i],
                    "connection": "USB",
                    "serial": info[2][i]
                })
        except:
            pass
        
        # Try Ethernet devices
        try:
            info = ljm.listAllS("ETHERNET", "ANY")
            for i in range(info[0]):
                found_devices.append({
                    "id": str(info[2][i]),
                    "type": info[3][i],
                    "connection": "ETHERNET",
                    "serial": info[2][i]
                })
        except:
            pass
        
        # Try WiFi devices
        try:
            info = ljm.listAllS("WIFI", "ANY")
            for i in range(info[0]):
                found_devices.append({
                    "id": str(info[2][i]),
                    "type": info[3][i],
                    "connection": "WIFI",
                    "serial": info[2][i]
                })
        except:
            pass
        
        if not found_devices:
            # Try ANY connection as fallback
            try:
                handle = ljm.openS("ANY", "ANY", "ANY")
                info = ljm.getHandleInfo(handle)
                found_devices.append({
                    "id": str(info[2]),
                    "type": ljm.numberToType(info[0]),
                    "connection": ljm.numberToConnectionType(info[1]),
                    "serial": info[2]
                })
                ljm.close(handle)
            except:
                pass
        
        return {"devices": found_devices}
    except Exception as e:
        return {"devices": [], "error": str(e)}

@app.post("/api/devices/{device_id}/connect")
def connect_device(device_id: str):
    """Connect to a LabJack device"""
    if not LABJACK_AVAILABLE:
        labjack_state["connected"] = True
        labjack_state["device_info"] = {"mock": True, "id": device_id}
        return {"success": True, "message": "Connected to mock device"}
    
    try:
        # Close existing connection
        if labjack_state["handle"]:
            try:
                ljm.close(labjack_state["handle"])
            except:
                pass
        
        # Open new connection
        if device_id == "ANY":
            handle = ljm.openS("ANY", "ANY", "ANY")
        else:
            handle = ljm.openS("ANY", "ANY", device_id)
        
        # Get device info
        info = ljm.getHandleInfo(handle)
        
        labjack_state["handle"] = handle
        labjack_state["connected"] = True
        labjack_state["device_info"] = {
            "device_type": ljm.numberToType(info[0]),
            "connection_type": ljm.numberToConnectionType(info[1]),
            "serial_number": info[2],
            "ip_address": ljm.numberToIP(info[3]),
            "port": info[4],
            "max_bytes": info[5]
        }
        
        return {
            "success": True,
            "device_info": labjack_state["device_info"],
            "message": f"Connected to {labjack_state['device_info']['device_type']}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect: {str(e)}")

@app.delete("/api/devices/{device_id}/disconnect")
def disconnect_device(device_id: str):
    """Disconnect from LabJack device"""
    if labjack_state["handle"] and LABJACK_AVAILABLE:
        try:
            ljm.close(labjack_state["handle"])
        except:
            pass
    
    labjack_state["handle"] = None
    labjack_state["connected"] = False
    labjack_state["device_info"] = {}
    
    return {"success": True, "message": "Disconnected"}

@app.post("/api/analog/read")
async def read_analog(data: Dict[str, Any]):
    """Read analog input channels"""
    if not labjack_state["connected"]:
        raise HTTPException(status_code=400, detail="No device connected")
    
    channels = data.get("channels", [0, 1, 2, 3])
    
    if not LABJACK_AVAILABLE or not labjack_state["handle"]:
        # Mock data
        import random
        values = [round(random.uniform(0, 5), 3) for _ in channels]
    else:
        # Read real data
        try:
            channel_names = [f"AIN{ch}" for ch in channels]
            values = ljm.eReadNames(labjack_state["handle"], len(channel_names), channel_names)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Read error: {str(e)}")
    
    return {
        "success": True,
        "channels": channels,
        "values": values,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/streaming/start")
async def start_streaming(data: Dict[str, Any]):
    """Start data streaming"""
    if not labjack_state["connected"]:
        raise HTTPException(status_code=400, detail="No device connected")
    
    channels = data.get("channels", ["AIN0", "AIN1"])
    scan_rate = data.get("scan_rate", 1000)
    
    if not LABJACK_AVAILABLE or not labjack_state["handle"]:
        labjack_state["streaming"] = True
        return {
            "success": True,
            "streaming": True,
            "channels": channels,
            "scan_rate": scan_rate,
            "message": "Mock streaming started"
        }
    
    try:
        # Configure streaming
        scans_per_read = int(scan_rate / 10)  # Read 10 times per second
        
        # Start stream
        scan_list = ljm.namesToAddresses(len(channels), channels)[0]
        scan_rate = ljm.eStreamStart(
            labjack_state["handle"],
            scans_per_read,
            len(channels),
            scan_list,
            scan_rate
        )
        
        labjack_state["streaming"] = True
        
        return {
            "success": True,
            "streaming": True,
            "channels": channels,
            "actual_scan_rate": scan_rate,
            "message": "Streaming started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream error: {str(e)}")

@app.post("/api/streaming/stop/{device_id}")
async def stop_streaming(device_id: str):
    """Stop data streaming"""
    if LABJACK_AVAILABLE and labjack_state["handle"] and labjack_state["streaming"]:
        try:
            ljm.eStreamStop(labjack_state["handle"])
        except:
            pass
    
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
        "labjack_available": LABJACK_AVAILABLE,
        "labjack_state": {
            "connected": labjack_state["connected"],
            "device_info": labjack_state["device_info"],
            "streaming": labjack_state["streaming"]
        },
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("="*60)
    print("LabJack Bridge Service (Real Hardware Support)")
    print("="*60)
    print(f"LabJack LJM Available: {LABJACK_AVAILABLE}")
    if not LABJACK_AVAILABLE:
        print("⚠️ Install LabJack LJM from: https://labjack.com/pages/support?doc=/software-driver/installer-downloads/")
    print("Starting server on http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("="*60)
    
    uvicorn.run(app, host="0.0.0.0", port=8080)