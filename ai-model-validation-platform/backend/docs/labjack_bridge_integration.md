# LabJack Bridge Integration - Implementation Summary

## Overview
Modified the LabJack service to prioritize HTTP bridge connection over direct USB access, preventing the `LJME_DEVICE_CURRENTLY_CLAIMED_BY_ANOTHER_PROCESS` error.

## Changes Made

### 1. Connection Logic (`_connect_bridge` method)
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_service.py`

**Key Changes**:
- Added HTTP-first approach using `requests.get(f"{bridge_url}/status")`
- Checks bridge availability before attempting connection
- Stores `bridge_url` for HTTP-based operations
- Falls back to WebSocket only if HTTP is successful
- No direct USB connection attempted when bridge is available

**HTTP Endpoint Check**:
```python
response = requests.get(f"{bridge_url}/status", timeout=5)
status_data = response.json()
if status_data.get("bridge_active") and status_data.get("connected"):
    # Use HTTP bridge mode
```

### 2. Voltage Reading (`read_single_voltage` method)

**HTTP Bridge Mode**:
```python
response = requests.post(
    f"{self.bridge_url}/read-analog",
    json={"channel": channel},
    timeout=5
)
```

- Uses `/read-analog` endpoint with channel parameter
- Returns voltage value from JSON response
- Respects voltage threshold (3.3V from `.env`)

### 3. Streaming Operations

#### Start Stream (`start_stream` method)
```python
response = requests.post(
    f"{self.bridge_url}/stream-start",
    json={"channels": channels, "sample_rate": sample_rate},
    timeout=10
)
```

#### Stop Stream (`stop_stream` method)
```python
response = requests.post(
    f"{self.bridge_url}/stream-stop",
    timeout=10
)
```

#### Read Stream Data (`get_stream_data` method)
```python
response = requests.post(
    f"{self.bridge_url}/stream-read",
    json={"max_samples": max_samples},
    timeout=5
)
```

### 4. Health Monitoring (`_health_monitor_loop` method)

**HTTP Bridge Health Check**:
```python
response = requests.get(f"{self.bridge_url}/status", timeout=5)
status_data = response.json()
if status_data.get("bridge_active") and status_data.get("connected"):
    consecutive_failures = 0
    logger.debug(f"🩺 Bridge health check OK")
```

- Performs HTTP status checks every 30 seconds
- Tracks consecutive failures (max 5)
- Automatic recovery on transient errors

## Bridge API Endpoints Used

| Endpoint | Method | Purpose | Request | Response |
|----------|--------|---------|---------|----------|
| `/status` | GET | Check bridge health | - | `{bridge_active, connected, device_info}` |
| `/read-analog` | POST | Read voltage | `{channel}` | `{success, value, channel}` |
| `/stream-start` | POST | Start streaming | `{channels, sample_rate}` | `{success}` |
| `/stream-stop` | POST | Stop streaming | - | `{success}` |
| `/stream-read` | POST | Read stream data | `{max_samples}` | `{success, data[]}` |

## Environment Configuration

**File**: `.env`
```bash
LABJACK_BRIDGE_HOST=localhost
LABJACK_BRIDGE_PORT=8080
LABJACK_VOLTAGE_THRESHOLD=3.3
LABJACK_CHANNELS=AIN0,AIN1
```

## Connection Priority

1. **Bridge Mode** (HTTP-first) - Primary on WSL
   - Check `http://localhost:8080/status`
   - Use HTTP endpoints for all operations
   - Optional WebSocket for streaming

2. **Direct Mode** - Fallback
   - Only attempted if bridge unavailable
   - Uses USB/LJM library

3. **Mock Mode** - Disabled by default
   - Requires explicit `allow_mock=True`

## Testing Results

### Connection Test
```
✅ Connected via bridge
   Mode: bridge
   Status: connected
   Type: T7
   Connection: HTTP_BRIDGE
   Interface: HTTP_BRIDGE
   Bridge URL: http://localhost:8080
```

### Voltage Reading Test
```
📊 AIN0 voltage: 0.001V
📊 AIN1 voltage: 0.199V
🔍 Voltage threshold check (3.3V):
   ⚪ Voltage < 3.3V (idle)
```

### Health Monitoring Test
```
DEBUG: 🩺 Bridge health check OK
```

## Benefits

1. **No USB Conflicts**: Backend uses HTTP, bridge owns USB connection
2. **WSL Compatible**: Works seamlessly in WSL environment
3. **Clean Architecture**: HTTP API provides clear separation
4. **Real Hardware**: No mock mode fallback ensures real HIL testing
5. **Robust Health Checks**: Automatic monitoring and recovery

## Error Handling

- **Bridge Unavailable**: Falls back to direct connection attempt
- **HTTP Timeout**: Returns 0.0V or empty data with error log
- **Health Check Failure**: Tracks consecutive failures, attempts recovery
- **Stream Errors**: Logs warning but continues operation

## Next Steps

1. ✅ Bridge connection prioritized
2. ✅ HTTP endpoints implemented
3. ✅ Health monitoring updated
4. ✅ Voltage threshold respected
5. ⏭️ Integration testing with actual detection events

## Files Modified

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_service.py`
   - `_connect_bridge()` - HTTP-first connection
   - `read_single_voltage()` - HTTP endpoint for voltage reading
   - `start_stream()` - HTTP endpoint for stream start
   - `stop_stream()` - HTTP endpoint for stream stop
   - `get_stream_data()` - HTTP endpoint for stream data
   - `_health_monitor_loop()` - HTTP-based health checks

## Bridge Service Reference

**Bridge Location**: Running on Windows host at `http://localhost:8080`

**Hardware**: LabJack T7 connected via USB

**Bridge Features**:
- Real-time analog input reading
- Hardware streaming support
- Device status monitoring
- WebSocket streaming (optional)

---

**Status**: ✅ Implementation Complete
**Testing**: ✅ Connection and voltage reading verified
**Compatibility**: ✅ WSL/Linux compatible via HTTP bridge
