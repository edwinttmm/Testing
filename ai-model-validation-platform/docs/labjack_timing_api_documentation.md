# LabJack Timing Validation API Documentation

## Overview

The LabJack Timing Validation API provides comprehensive endpoints for video timing synchronization, detection event processing, and latency-based validation. This system enables precise measurement and validation of timing between video playback and hardware detection events from LabJack devices.

## Key Features

- **Video Timing Synchronization**: Start/stop video timing with precise timestamps
- **Real-time Detection Processing**: Process LabJack detection events with latency calculation  
- **Latency-based Validation**: Pass/Fail determination based on configurable thresholds
- **WebSocket Real-time Updates**: Live monitoring of detection events and results
- **Comprehensive Session Management**: Full lifecycle management of timing sessions
- **Detailed Analytics**: Latency distribution, performance metrics, and event analysis

## API Endpoints

### 1. Start Timing Session

**POST** `/api/test-sessions/{session_id}/start-timing`

Start video timing and LabJack monitoring for a test session.

#### Request Body
```json
{
  "video_id": "test_video_001",
  "latency_threshold_ms": 50.0,
  "voltage_threshold": 3.0,
  "detection_channels": [0, 1],
  "sampling_rate_hz": 1000.0,
  "metadata": {
    "test_type": "timing_validation",
    "operator": "test_user"
  }
}
```

#### Response
```json
{
  "session_id": "session_001",
  "video_start_timestamp": 1699123456.789,
  "monitoring_status": "ACTIVE",
  "labjack_status": "MONITORING",
  "configuration": {
    "video_id": "test_video_001",
    "latency_threshold_ms": 50.0,
    "voltage_threshold": 3.0,
    "detection_channels": [0, 1],
    "sampling_rate_hz": 1000.0
  },
  "message": "Timing session started successfully"
}
```

#### Parameters
- `video_id` (string): Video identifier for timing synchronization
- `latency_threshold_ms` (float): Maximum acceptable latency (1.0-10000.0ms)
- `voltage_threshold` (float): Voltage threshold for detection events (0.1-10.0V)
- `detection_channels` (array): LabJack channels to monitor (default: [0])
- `sampling_rate_hz` (float): Sampling rate in Hz (default: 1000.0)
- `metadata` (object): Additional session metadata

---

### 2. Process Detection Event

**POST** `/api/labjack/detection-event`

Receive and process detection event from LabJack hardware.

#### Request Body
```json
{
  "session_id": "session_001",
  "timestamp": 1699123456.814,
  "voltage": 3.2,
  "channel": 0,
  "pin_state": true,
  "metadata": {
    "raw_adc": 1024,
    "temperature": 23.5
  }
}
```

#### Response
```json
{
  "event_id": "evt_12345",
  "session_id": "session_001", 
  "latency_ms": 25.0,
  "validation_result": "PASS",
  "timestamp_processed": 1699123456.815,
  "message": "Detection event processed: PASS (latency: 25.00ms)"
}
```

#### Parameters
- `session_id` (string): Active test session identifier
- `timestamp` (float): High-precision detection timestamp
- `voltage` (float): Voltage level at detection
- `channel` (integer): LabJack channel number (0-15)
- `pin_state` (boolean): Digital pin state (optional)
- `metadata` (object): Additional event metadata

#### Validation Results
- `PASS`: Latency ≤ threshold
- `FAIL`: Latency > threshold  
- `PENDING`: Processing incomplete

---

### 3. Get Latency Results

**GET** `/api/test-sessions/{session_id}/latency-results`

Get comprehensive latency-based results for a test session.

#### Response
```json
{
  "session_id": "session_001",
  "total_events": 150,
  "pass_count": 135,
  "fail_count": 15,
  "pass_rate": 90.0,
  "average_latency_ms": 32.5,
  "min_latency_ms": 12.1,
  "max_latency_ms": 87.3,
  "latency_distribution": {
    "0-10ms": 5,
    "10-25ms": 45,
    "25-50ms": 85,
    "50-100ms": 12,
    "100-500ms": 3,
    "500ms+": 0
  },
  "threshold_ms": 50.0,
  "session_status": "ACTIVE"
}
```

#### Metrics Included
- **Pass Rate**: Percentage of events meeting latency threshold
- **Latency Statistics**: Min, max, average latency measurements
- **Distribution**: Histogram of latency ranges
- **Event Counts**: Total, pass, and fail counts

---

### 4. Stop Timing Session

**POST** `/api/test-sessions/{session_id}/stop-timing`

Stop video timing and LabJack monitoring, finalize session results.

#### Response
```json
{
  "session_id": "session_001",
  "session_duration_ms": 45000.0,
  "total_events": 150,
  "final_results": {
    // ... same structure as latency-results endpoint
  },
  "message": "Timing session stopped successfully"
}
```

---

### 5. Get Detection Events

**GET** `/api/test-sessions/{session_id}/detection-events`

Get detailed list of detection events for debugging and analysis.

#### Query Parameters
- `skip` (integer): Number of events to skip (pagination)
- `limit` (integer): Maximum events to return (1-1000)
- `validation_result` (string): Filter by PASS/FAIL/PENDING
- `channel` (integer): Filter by channel number (0-15)

#### Response
```json
{
  "session_id": "session_001",
  "events": [
    {
      "event_id": "evt_001",
      "timestamp": 1699123456.814,
      "voltage": 3.2,
      "channel": 0,
      "latency_ms": 25.0,
      "validation_result": "PASS",
      "video_timestamp": 1699123456.789,
      "metadata": {...}
    }
  ],
  "total_count": 150,
  "filtered_count": 135,
  "session_status": "ACTIVE"
}
```

---

### 6. WebSocket Real-time Updates

**WebSocket** `/api/test-sessions/{session_id}/ws`

Real-time WebSocket connection for live timing validation updates.

#### Events Sent

**Detection Event**
```json
{
  "event": "detection_event",
  "data": {
    "event_id": "evt_001",
    "timestamp": 1699123456.814,
    "voltage": 3.2,
    "channel": 0,
    "validation_result": "PASS"
  },
  "timestamp": "2023-11-04T15:30:56.789Z"
}
```

**Latency Calculated**
```json
{
  "event": "latency_calculated", 
  "data": {
    "event_id": "evt_001",
    "latency_ms": 25.0,
    "threshold_ms": 50.0,
    "validation_result": "PASS",
    "pass_rate": 90.0
  },
  "timestamp": "2023-11-04T15:30:56.790Z"
}
```

**Session Completed**
```json
{
  "event": "session_completed",
  "data": {
    "session_id": "session_001",
    "session_duration_ms": 45000.0,
    "total_events": 150,
    "pass_rate": 90.0,
    "average_latency_ms": 32.5
  },
  "timestamp": "2023-11-04T15:30:56.791Z"
}
```

---

### 7. Health Check

**GET** `/api/labjack-timing/health`

Check API health and service status.

#### Response
```json
{
  "status": "healthy",
  "timestamp": "2023-11-04T15:30:56.789Z",
  "active_sessions": 3,
  "services": {
    "labjack_detection_service": true,
    "video_timing_service": true,
    "latency_validation_service": true
  },
  "api_version": "1.0.0"
}
```

---

### 8. Session Cleanup

**DELETE** `/api/test-sessions/{session_id}/cleanup`

Cleanup session data and resources (maintenance endpoint).

#### Query Parameters
- `force` (boolean): Force cleanup even if session is active

---

## Integration Workflow

### Basic Timing Validation Flow

```python
# 1. Start timing session
session_config = {
    "video_id": "test_video_001",
    "latency_threshold_ms": 50.0,
    "voltage_threshold": 3.0,
    "detection_channels": [0, 1]
}
start_result = await client.start_timing_session(session_id, session_config)

# 2. Process detection events (usually from LabJack hardware)
event_data = {
    "session_id": session_id,
    "timestamp": current_timestamp,
    "voltage": detected_voltage,
    "channel": detection_channel
}
event_result = await client.send_detection_event(event_data)

# 3. Monitor results in real-time
results = await client.get_latency_results(session_id)

# 4. Stop session and get final results
final_results = await client.stop_timing_session(session_id)
```

### Real-time Monitoring

```python
# Connect to WebSocket for real-time updates
websocket_uri = f"ws://localhost:8000/api/test-sessions/{session_id}/ws"

async with websockets.connect(websocket_uri) as websocket:
    async for message in websocket:
        event_data = json.loads(message)
        
        if event_data['event'] == 'latency_calculated':
            latency = event_data['data']['latency_ms']
            result = event_data['data']['validation_result']
            print(f"Latency: {latency}ms - {result}")
```

## Error Handling

### Common Error Codes

- **400 Bad Request**: Invalid parameters or session state
- **404 Not Found**: Session not found or inactive
- **500 Internal Server Error**: Service unavailable or processing error

### Example Error Response
```json
{
  "detail": "Session not found or not active",
  "status_code": 404
}
```

### Best Practices

1. **Check API Health**: Always verify service availability before starting sessions
2. **Handle WebSocket Disconnections**: Implement reconnection logic for real-time monitoring
3. **Validate Input Data**: Ensure timestamps, voltages, and channels are within valid ranges
4. **Monitor Session State**: Check session status before sending events
5. **Cleanup Resources**: Use cleanup endpoint for proper resource management

## Performance Considerations

### Latency Optimization

- Use high-precision timestamps for accurate latency measurement
- Minimize network latency between LabJack and API server
- Configure appropriate sampling rates based on requirements
- Consider batch processing for high-frequency events

### Scalability

- Monitor active session count and resource usage
- Implement session timeouts and automatic cleanup
- Use connection pooling for HTTP clients
- Consider load balancing for high-throughput scenarios

## Security

### Authentication

Currently uses session-based authentication. Future versions will include:
- API key authentication
- Role-based access control
- Request rate limiting
- Audit logging

### Data Protection

- All timing data stored with encryption at rest
- WebSocket connections use secure protocols in production
- Sensitive configuration data properly encrypted
- Regular security audits and updates

## Troubleshooting

### Common Issues

1. **"Session not found"**: Ensure session was started successfully before sending events
2. **High latency values**: Check system clock synchronization and network latency
3. **WebSocket disconnections**: Implement ping/pong and reconnection logic
4. **Service unavailable**: Check LabJack hardware connection and driver installation

### Debug Information

Use the detection events endpoint to get detailed event information:
```
GET /api/test-sessions/{session_id}/detection-events?limit=1000
```

### Logging

Enable debug logging to trace API calls and timing measurements:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Example Applications

### Quality Assurance Testing
```python
# Test video synchronization accuracy
threshold_ms = 16.67  # 60fps = ~16.67ms per frame
results = validate_timing_accuracy(video_file, threshold_ms)
assert results['pass_rate'] >= 95.0
```

### Performance Benchmarking
```python
# Measure system latency under load
for i in range(1000):
    await send_detection_event(session_id, time.time(), 3.3, 0)

results = await get_latency_results(session_id)
print(f"Average latency under load: {results['average_latency_ms']}ms")
```

### Real-time Monitoring Dashboard
```python
# WebSocket-based real-time dashboard
async def update_dashboard(event_data):
    if event_data['event'] == 'latency_calculated':
        dashboard.update_latency_chart(event_data['data'])
```

## Support and Resources

- **API Documentation**: Complete OpenAPI specification available
- **Code Examples**: See `/backend/examples/labjack_timing_integration.py`
- **Testing**: Use provided test utilities for validation
- **Issues**: Report bugs and feature requests through standard channels

For additional support or custom integration assistance, contact the development team.