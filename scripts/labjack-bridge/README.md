# LabJack Bridge Service

A robust Windows service that provides HTTP REST API and WebSocket streaming capabilities for LabJack hardware communication. This service acts as a bridge between your applications (running in WSL or native Windows) and LabJack devices.

## Features

- **Windows Service Integration**: Runs as a native Windows service with automatic startup
- **HTTP REST API**: Complete REST API for all LabJack operations
- **WebSocket Streaming**: Real-time data streaming with low latency
- **Auto-Discovery**: Automatic detection of LabJack devices (USB and TCP)
- **Connection Management**: Robust connection handling with monitoring and recovery
- **Error Handling**: Comprehensive error handling and logging
- **Cross-Platform Client Support**: Works with applications running in WSL or native Windows

## Architecture

```
┌─────────────────┐    HTTP/WebSocket    ┌─────────────────┐    LabJack API    ┌─────────────────┐
│   Your App      │ ────────────────────▶ │ Bridge Service  │ ────────────────▶ │ LabJack Device  │
│ (WSL/Windows)   │ ◀──────────────────── │   (Windows)     │ ◀──────────────── │   (Hardware)    │
└─────────────────┘                      └─────────────────┘                  └─────────────────┘
```

## Installation

### Automatic Installation

#### Python Installer
```bash
# Run as Administrator
python install/install_service.py
```

#### PowerShell Installer
```powershell
# Run as Administrator
./install/install_service.ps1
```

### Manual Installation

1. **Install Python Dependencies**:
   ```bash
   pip install -r src/requirements.txt
   ```

2. **Install LabJack LJM Software**:
   - Download from [LabJack.com](https://labjack.com/support/software/installers/ljm)
   - Install the LJM library for your system

3. **Install Windows Service**:
   ```bash
   python src/labjack_bridge_service.py install
   ```

4. **Start Service**:
   ```bash
   sc start LabJackBridgeService
   ```

## API Documentation

### Base URL
```
http://localhost:8080/api
```

### Health Check
```http
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "labjack_available": true,
  "devices_connected": 1
}
```

### Device Management

#### Discover Devices
```http
GET /api/devices
```

#### Connect Device
```http
POST /api/devices/{device_id}/connect
```

#### Disconnect Device
```http
DELETE /api/devices/{device_id}/disconnect
```

### Analog I/O

#### Read Analog Inputs
```http
POST /api/analog/read
Content-Type: application/json

{
  "device_id": "192.168.1.100",
  "channels": [0, 1, 2, 3],
  "resolution_index": 0,
  "settling_time": 0
}
```

#### Write Analog Output
```http
POST /api/analog/write
Content-Type: application/json

{
  "device_id": "192.168.1.100",
  "channel": 0,
  "voltage": 2.5
}
```

### Digital I/O

#### Read Digital Inputs
```http
POST /api/digital/read
Content-Type: application/json

{
  "device_id": "192.168.1.100",
  "channels": [0, 1, 2, 3]
}
```

#### Write Digital Output
```http
POST /api/digital/write
Content-Type: application/json

{
  "device_id": "192.168.1.100",
  "channel": 0,
  "state": true
}
```

### Streaming

#### Start Streaming
```http
POST /api/streaming/start
Content-Type: application/json

{
  "device_id": "192.168.1.100",
  "channels": [0, 1, 2],
  "scan_rate": 1000.0,
  "scans_per_read": 100
}
```

#### Stop Streaming
```http
POST /api/streaming/stop/{device_id}
```

### WebSocket Streaming

Connect to WebSocket endpoint for real-time data:
```
ws://localhost:8080/ws/stream
```

Stream data format:
```json
{
  "device_id": "192.168.1.100",
  "channels": [0, 1, 2],
  "scan_rate": 1000.0,
  "data": [2.5, 1.2, 0.8, ...],
  "timestamp": "2024-01-15T10:30:00"
}
```

## Client Examples

### Python Client
```python
from client_example import LabJackBridgeClient

client = LabJackBridgeClient()

# Discover and connect
devices = client.discover_devices()
client.connect_device(devices[0]['identifier'])

# Read analog inputs
data = client.read_analog(devices[0]['identifier'], [0, 1, 2, 3])
print(f"Values: {data['values']}")

# Start streaming with WebSocket
await client.websocket_stream_listener(callback=my_callback, duration=10)
```

### JavaScript Client
```javascript
// REST API
const response = await fetch('http://localhost:8080/api/devices');
const devices = await response.json();

// WebSocket streaming
const ws = new WebSocket('ws://localhost:8080/ws/stream');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Stream data:', data);
};
```

### cURL Examples
```bash
# Health check
curl http://localhost:8080/api/health

# Discover devices
curl http://localhost:8080/api/devices

# Read analog inputs
curl -X POST http://localhost:8080/api/analog/read \
  -H "Content-Type: application/json" \
  -d '{"device_id":"192.168.1.100","channels":[0,1,2,3]}'
```

## Service Management

### Command Line
```bash
# Start service
sc start LabJackBridgeService

# Stop service
sc stop LabJackBridgeService

# Check status
sc query LabJackBridgeService

# Uninstall service
python src/labjack_bridge_service.py remove
```

### PowerShell
```powershell
# Using management script
.\manage_service.ps1 -Action start
.\manage_service.ps1 -Action status
.\manage_service.ps1 -Action logs
```

### Batch Scripts
- `start_service.bat` - Start the service
- `stop_service.bat` - Stop the service
- `service_status.bat` - Check service status
- `uninstall_service.bat` - Uninstall service

## Configuration

Edit `config/service_config.json`:

```json
{
  "service": {
    "host": "0.0.0.0",
    "port": 8080,
    "log_level": "info"
  },
  "labjack": {
    "auto_discover": true,
    "connection_timeout": 5.0,
    "retry_attempts": 3
  },
  "streaming": {
    "max_scan_rate": 100000,
    "default_scans_per_read": 100
  }
}
```

## Logging

Logs are stored in the `logs/` directory:
- Service events and errors
- API request/response logging
- Device connection status
- Performance metrics

## Testing

Run the comprehensive test suite:
```bash
python src/test_bridge.py
```

Performance testing:
```bash
python src/test_bridge.py --performance --duration 60
```

## Troubleshooting

### Service Won't Start
1. Check Windows Event Viewer for error details
2. Verify LabJack LJM software is installed
3. Ensure Python dependencies are installed
4. Check firewall settings for port 8080

### Device Not Found
1. Verify LabJack device is connected and powered
2. Check device IP address for TCP connections
3. Install latest LabJack drivers
4. Test with LabJack's Kipling software first

### API Connection Issues
1. Verify service is running: `sc query LabJackBridgeService`
2. Check firewall allows connections on port 8080
3. Test health endpoint: `curl http://localhost:8080/api/health`
4. Review service logs in `logs/` directory

### WebSocket Issues
1. Verify WebSocket support in your client
2. Check for proxy/firewall blocking WebSocket connections
3. Ensure streaming is started before connecting to WebSocket
4. Monitor connection logs for errors

## Development

### Project Structure
```
labjack-bridge/
├── src/
│   ├── labjack_bridge_service.py  # Main service implementation
│   ├── client_example.py          # Python client example
│   ├── test_bridge.py             # Test suite
│   └── requirements.txt           # Python dependencies
├── config/
│   └── service_config.json        # Service configuration
├── install/
│   ├── install_service.py         # Python installer
│   └── install_service.ps1        # PowerShell installer
└── logs/                          # Service logs
```

### Adding New Features
1. Update `labjack_bridge_service.py` with new endpoints
2. Add tests in `test_bridge.py`
3. Update client examples
4. Document API changes

## Support

- Check service logs in `logs/` directory
- Test with `test_bridge.py`
- Verify LabJack hardware with Kipling software
- Review Windows Event Viewer for service issues

## License

This project is provided as-is for development and testing purposes.