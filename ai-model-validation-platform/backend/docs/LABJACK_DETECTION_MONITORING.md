# LabJack Detection Monitoring Service

## Overview

The LabJack Detection Monitoring Service provides real-time event-based detection monitoring for LabJack hardware devices. This service is designed specifically for latency analysis and validation testing, focusing on recording precise timestamps when detection events occur rather than continuous data streaming.

## Key Features

- **Event-Based Detection**: Monitors for voltage threshold crossings, not continuous data
- **Precise Timestamps**: Records exact detection timestamps for latency calculations
- **Configurable Thresholds**: Support for custom voltage thresholds per channel
- **Debounce Logic**: Prevents duplicate detections with configurable debounce periods
- **Multi-Channel Support**: Monitor multiple LabJack channels simultaneously
- **Thread-Safe**: Concurrent monitoring sessions with thread-safe operations
- **Database Integration**: Automatic persistence of detection events
- **WebSocket Notifications**: Real-time notifications for detection events
- **Session Management**: Track multiple monitoring sessions independently

## Architecture

The service consists of several key components:

1. **LabJackDetectionMonitor**: Main monitoring class that handles detection logic
2. **DetectionEvent**: Data structure for detection events with timestamps
3. **DetectionDatabaseService**: Database integration for event persistence
4. **API Endpoints**: REST API for controlling monitoring sessions
5. **WebSocket Integration**: Real-time notifications

## Quick Start

### 1. Import and Initialize

```python
from services.labjack_detection_service import get_detection_monitor

# Get the global detection monitor
monitor = get_detection_monitor()
```

### 2. Start Monitoring

```python
# Start basic monitoring
success = monitor.start_monitoring(
    session_id="test_session_1",
    channels=["AIN0", "AIN1"],
    voltage_threshold=2.5,  # 2.5V detection threshold
    debounce_ms=100        # 100ms debounce
)
```

### 3. Retrieve Detection Events

```python
# Get all detection events for a session
events = monitor.get_detection_events("test_session_1")

for event in events:
    print(f"Detection: {event['channel']} = {event['voltage']:.3f}V @ {event['timestamp']}")
```

### 4. Stop Monitoring

```python
# Stop monitoring
monitor.stop_monitoring("test_session_1")
```

## API Endpoints

The service provides REST API endpoints for remote control:

### Start Detection Monitoring

```http
POST /api/detection/start
Content-Type: application/json

{
    "session_id": "my_session",
    "channels": ["AIN0", "AIN1"],
    "voltage_threshold": 2.5,
    "debounce_ms": 100,
    "sample_rate": 1000,
    "enable_websocket": true,
    "store_in_db": true,
    "metadata": {
        "experiment": "latency_test_1"
    }
}
```

### Stop Detection Monitoring

```http
POST /api/detection/stop
Content-Type: application/json

{
    "session_id": "my_session"
}
```

### Get Detection Events

```http
GET /api/detection/events/my_session
```

Response:
```json
{
    "session_id": "my_session",
    "event_count": 15,
    "events": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_id": "my_session",
            "timestamp": "2024-01-15T10:30:45.123456",
            "channel": "AIN0",
            "voltage": 3.2,
            "threshold": 2.5,
            "detected": true,
            "is_duplicate": false,
            "metadata": {
                "labjack_mode": "direct",
                "sample_method": "single_read"
            }
        }
    ]
}
```

### Get Session Status

```http
GET /api/detection/status/my_session
```

### Get All Sessions

```http
GET /api/detection/sessions
```

### Health Check

```http
GET /api/detection/health
```

## Configuration Options

### DetectionConfig

```python
@dataclass
class DetectionConfig:
    session_id: str                     # Unique session identifier
    channels: List[str]                 # LabJack channels to monitor
    voltage_threshold: float = 2.5      # Detection voltage threshold (V)
    debounce_ms: int = 100             # Debounce time (ms)
    sample_rate: int = 1000            # Sampling rate (Hz)
    enable_websocket: bool = True       # Enable WebSocket notifications
    store_in_db: bool = True           # Store events in database
    metadata: Optional[Dict] = None     # Additional metadata
```

### Channel Configuration

Supported LabJack channels:
- **AIN0-AIN3**: Analog input channels (T4/T7)
- **AIN0-AIN13**: Extended analog inputs (T7)

### Voltage Thresholds

- **Range**: 0.0V to 10.0V (LabJack dependent)
- **Precision**: 0.001V resolution
- **Recommended**: 2.5V for digital-like signals

### Debounce Settings

- **Range**: 10ms to 5000ms
- **Purpose**: Prevent multiple detections for single event
- **Recommended**: 100ms for mechanical signals, 50ms for electronic

## Database Integration

Detection events are automatically stored in the database with the following schema:

### Detection Events Table

```sql
CREATE TABLE detection_events (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    event_id VARCHAR(255),
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    channel VARCHAR(50) NOT NULL,
    voltage FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    detected BOOLEAN DEFAULT TRUE,
    is_duplicate BOOLEAN DEFAULT FALSE,
    metadata TEXT
);
```

### Detection Sessions Table

```sql
CREATE TABLE detection_sessions (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    ended_at DATETIME,
    channels TEXT NOT NULL,
    voltage_threshold FLOAT DEFAULT 2.5,
    debounce_ms INTEGER DEFAULT 100,
    sample_rate INTEGER DEFAULT 1000,
    is_active BOOLEAN DEFAULT FALSE,
    total_events INTEGER DEFAULT 0,
    metadata TEXT
);
```

## Latency Analysis

The service is designed for precise latency measurements:

### Event Timing

```python
# Get events with precise timestamps
events = monitor.get_detection_events(session_id)

# Calculate intervals between detections
timestamps = [datetime.fromisoformat(e['timestamp']) for e in events]
intervals = []

for i in range(1, len(timestamps)):
    interval_ms = (timestamps[i] - timestamps[i-1]).total_seconds() * 1000
    intervals.append(interval_ms)

# Analysis
avg_interval = sum(intervals) / len(intervals)
min_interval = min(intervals)
max_interval = max(intervals)
```

### Video Synchronization

For video validation, detection events can be correlated with video timestamps:

```python
# Video start time (from video recording system)
video_start = datetime.fromisoformat("2024-01-15T10:30:00.000000")

# Detection events
detection_events = monitor.get_detection_events(session_id)

for event in detection_events:
    detection_time = datetime.fromisoformat(event['timestamp'])
    
    # Calculate offset from video start
    offset_ms = (detection_time - video_start).total_seconds() * 1000
    
    print(f"Detection at video offset: {offset_ms:.1f}ms")
```

## WebSocket Integration

Real-time notifications are sent via WebSocket when detections occur:

### Setup WebSocket Callback

```python
from services.labjack_detection_service import setup_websocket_integration

# Setup with your WebSocket manager
setup_websocket_integration(your_websocket_manager)
```

### WebSocket Message Format

```json
{
    "type": "detection_event",
    "session_id": "my_session",
    "event": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2024-01-15T10:30:45.123456",
        "channel": "AIN0",
        "voltage": 3.2,
        "threshold": 2.5
    }
}
```

## Error Handling

The service includes comprehensive error handling:

### Common Errors

1. **LabJack Not Connected**
   ```
   Error: LabJack hardware not connected
   Solution: Connect LabJack and verify with labjack_service
   ```

2. **Database Connection Failed**
   ```
   Warning: Database not available, events stored in memory only
   Impact: Events lost on service restart
   ```

3. **Invalid Channel**
   ```
   Error: Invalid channel 'AIN99'
   Solution: Use valid channels (AIN0-AIN13 for T7)
   ```

4. **Threshold Out of Range**
   ```
   Error: Voltage threshold must be between 0.0V and 10.0V
   Solution: Adjust threshold to valid range
   ```

## Performance Considerations

### Sample Rate Guidelines

- **Low-frequency signals**: 100-500 Hz
- **General purpose**: 1000 Hz (default)
- **High-frequency signals**: 2000-5000 Hz
- **Maximum**: Limited by LabJack hardware (varies by model)

### Memory Usage

- Each detection event: ~200 bytes in memory
- 1000 events/hour: ~200 KB memory
- Database storage recommended for long sessions

### Thread Usage

- One thread per monitoring session
- Threads are daemon threads (auto-cleanup)
- Maximum concurrent sessions: System dependent

## Troubleshooting

### LabJack Connection Issues

1. Check LabJack service status:
   ```python
   from services.labjack_service import get_labjack_service
   
   labjack = get_labjack_service()
   status = labjack.get_status()
   print(f"LabJack status: {status.status}")
   ```

2. Test basic voltage reading:
   ```python
   voltage = await labjack.read_single_voltage("AIN0")
   print(f"AIN0 voltage: {voltage}V")
   ```

### No Detection Events

1. **Check voltage threshold**: Lower threshold if signals are weak
2. **Verify channel connections**: Ensure proper wiring
3. **Check debounce setting**: Reduce debounce time if needed
4. **Monitor raw voltages**: Use LabJack service directly to verify signals

### Performance Issues

1. **Reduce sample rate**: Lower sample_rate parameter
2. **Limit channels**: Monitor fewer channels simultaneously
3. **Increase debounce**: Reduce event frequency with higher debounce
4. **Database optimization**: Ensure database has proper indexes

## Example Usage Scenarios

### Scenario 1: Video Latency Testing

```python
# Start detection monitoring before video recording
monitor.start_monitoring(
    session_id=f"video_test_{timestamp}",
    channels=["AIN0"],
    voltage_threshold=2.0,  # LED detection threshold
    debounce_ms=50,         # Fast response for LED changes
    metadata={"test_type": "video_latency", "operator": "test_user"}
)

# ... Record video with LED changes ...

# Stop monitoring after video recording
events = monitor.get_detection_events(session_id)
monitor.stop_monitoring(session_id)

# Analyze latency between detection and video
analyze_video_latency(events, video_file)
```

### Scenario 2: Hardware Response Time Testing

```python
# Multiple channel monitoring for complex hardware
monitor.start_monitoring(
    session_id="hardware_response_test",
    channels=["AIN0", "AIN1", "AIN2"],  # Input, processing, output signals
    voltage_threshold=3.0,
    debounce_ms=25,  # Fast hardware response
    sample_rate=2000  # High-speed sampling
)

# ... Trigger hardware test sequence ...

# Analyze response times between channels
events = monitor.get_detection_events(session_id)
analyze_hardware_response(events)
```

### Scenario 3: Long-Duration Monitoring

```python
# Setup for extended monitoring with database storage
monitor.start_monitoring(
    session_id="long_duration_test",
    channels=["AIN0"],
    voltage_threshold=2.5,
    debounce_ms=200,  # Reduce event frequency
    store_in_db=True,  # Essential for long tests
    metadata={
        "duration": "24_hours",
        "test_purpose": "reliability_testing"
    }
)

# Monitor will run continuously...
# Events automatically stored in database

# Later analysis (even after service restart)
events = monitor.get_detection_events(session_id, from_database=True)
```

## Integration with Existing System

### FastAPI Integration

Add to your FastAPI application:

```python
from api_labjack_detection import detection_router

app = FastAPI()
app.include_router(detection_router)
```

### Database Migration

The service automatically creates required tables, but for production:

```python
from services.detection_database_integration import DetectionEvent, DetectionSession
from alembic import command
from alembic.config import Config

# Create migration
alembic_cfg = Config("alembic.ini")
command.revision(alembic_cfg, autogenerate=True, message="Add detection tables")
command.upgrade(alembic_cfg, "head")
```

## Maintenance

### Regular Cleanup

```python
# Clean up old detection data (older than 30 days)
cleaned_count = await monitor.cleanup_old_data(days_old=30)
print(f"Cleaned up {cleaned_count} old sessions")
```

### Health Monitoring

```python
# Regular health checks
stats = monitor.get_statistics()
if not stats['labjack_connected'] == 'CONNECTED':
    logger.warning("LabJack connection lost")

if not stats['database_available']:
    logger.warning("Database not available - events not persisted")
```

## Support and Troubleshooting

For issues and questions:

1. Check logs for detailed error messages
2. Verify LabJack hardware connection
3. Test basic LabJack operations first
4. Ensure database connectivity
5. Monitor system resources (memory, threads)

The LabJack Detection Monitoring Service provides a robust, production-ready solution for event-based detection monitoring with precise timing capabilities essential for latency analysis and hardware validation testing.