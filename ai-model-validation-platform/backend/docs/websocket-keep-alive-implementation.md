# WebSocket Keep-Alive Implementation

## Overview
Comprehensive keep-alive mechanisms to prevent premature WebSocket closure during detection streaming sessions.

## Problem Statement
**ISSUE**: WebSocket connections were closing before detections were delivered during monitoring sessions.

**ROOT CAUSE**:
- No explicit tracking of active detection streams
- Connection heartbeat only maintained for general sessions
- No differentiation between idle connections and active streaming sessions

## Solution Implementation

### 1. Active Stream Tracking

**File**: `socketio_server.py`

```python
# Track active detection streaming sessions (prevents premature closure)
active_detection_streams: Dict[str, Dict[str, Any]] = {}
connection_heartbeat_tasks: Dict[str, asyncio.Task] = {}
```

**Purpose**: Maintain registry of active detection streaming sessions to ensure keep-alive continues during monitoring.

### 2. Enhanced Heartbeat Mechanism

**Reduced Interval**: 30s → 5s for active streaming
**Dual Condition Check**: Keeps connection alive if EITHER:
- Client has active session
- Client has detection stream subscription

```python
async def heartbeat_connection(sid: str):
    """Send periodic heartbeat to maintain connection during streaming

    CRITICAL: This prevents premature WebSocket closure during detection streaming
    by maintaining active communication even when no detections are being sent.
    """
    heartbeat_interval = 5  # REDUCED: Send every 5 seconds for active streaming

    while True:
        # Check if connection is still tracked
        is_active_client = f"client_{sid}" in active_sessions
        has_detection_stream = sid in active_detection_streams

        # Keep connection alive if EITHER condition is true
        if not (is_active_client or has_detection_stream):
            break
```

**Key Features**:
- Sends heartbeat every 5 seconds during active streaming
- Monitors both general sessions and detection streams
- Logs detailed state information for debugging
- Gracefully handles connection failures (3 missed heartbeats → cleanup)

### 3. Detection Stream Subscription

**New Events**: `subscribe_detections` and `unsubscribe_detections`

```python
@sio.event
async def subscribe_detections(sid, data):
    """Subscribe to detection events for a test session

    CRITICAL: This registers the client for detection streaming and enables
    keep-alive mechanisms to prevent premature connection closure.
    """
    session_id = data.get('session_id')

    # Register detection stream (enables keep-alive)
    active_detection_streams[sid] = {
        'session_id': session_id,
        'subscribed_at': asyncio.get_event_loop().time(),
        'detection_count': 0
    }

    logger.info(
        f"🔌 Detection stream opened: {session_id} (sid: {sid}) - "
        f"Keep-alive enabled"
    )
```

**Frontend Usage**:
```javascript
// Subscribe to detection events (enables keep-alive)
socket.emit('subscribe_detections', { session_id: sessionId });

// Server confirms with keep-alive info
socket.on('detection_subscription_confirmed', (data) => {
  console.log('Keep-alive enabled:', data.keep_alive_enabled);
  console.log('Heartbeat interval:', data.heartbeat_interval_seconds);
});
```

### 4. Connection State Logging

**Comprehensive Logging**:
```
🔌 KEEP-ALIVE: Heartbeat started for client {sid} (interval: 5s)
🔌 Detection stream opened: {session_id} (sid: {sid}) - Keep-alive enabled
🔌 KEEP-ALIVE: Heartbeat #5 sent to {sid} (detection stream: {session_id})
🔌 Detection stream closed: {session_id} (sid: {sid}) - Detections received: 42
```

### 5. Enhanced Connection Lifecycle

**Connect Event**:
```python
# Send enhanced connection confirmation
await sio.emit('connection_status', {
    'status': 'connected',
    'features': {
        'heartbeat': True,
        'keep_alive': True  # NEW: Indicate keep-alive support
    }
})

# Start heartbeat with enhanced keep-alive
heartbeat_task = asyncio.create_task(heartbeat_connection(sid))
connection_heartbeat_tasks[sid] = heartbeat_task
```

**Disconnect Event**:
```python
# Cancel heartbeat task
if sid in connection_heartbeat_tasks:
    heartbeat_task.cancel()

# Clean up active detection streams
if sid in active_detection_streams:
    stream_info = active_detection_streams[sid]
    logger.info(f"Detection stream closed: {stream_info.get('session_id')}")
```

### 6. Detection Counter Tracking

```python
async def emit_detection_event(detection_data: dict, test_session_id: str):
    """Update detection counter for active streams"""
    for sid, stream_info in active_detection_streams.items():
        if stream_info.get('session_id') == test_session_id:
            stream_info['detection_count'] = stream_info.get('detection_count', 0) + 1
```

**Purpose**: Track number of detections delivered per stream for diagnostics and verification.

## Configuration

### Socket.IO Server Settings
```python
sio = socketio.AsyncServer(
    ping_timeout=60,      # 60 seconds before considering client disconnected
    ping_interval=25,     # Send ping every 25 seconds
    transports=['websocket', 'polling'],
)
```

### Heartbeat Settings
```python
heartbeat_interval = 5              # Send every 5 seconds during streaming
max_missed_heartbeats = 3          # Allow 3 failures before cleanup
total_timeout = 5 * 3 = 15 seconds # Maximum silent period
```

## Frontend Integration

### 1. Subscribe to Detection Stream
```javascript
// Enable keep-alive for detection monitoring
socket.emit('subscribe_detections', {
  session_id: testSessionId
});

// Confirm subscription
socket.on('detection_subscription_confirmed', (data) => {
  console.log('Stream opened:', data.session_id);
  console.log('Keep-alive:', data.keep_alive_enabled);
});
```

### 2. Handle Heartbeats
```javascript
// Receive heartbeat pings
socket.on('heartbeat_ping', (data) => {
  console.log('Heartbeat #' + data.count,
              'Stream active:', data.has_detection_stream);

  // Optional: Respond with pong
  socket.emit('heartbeat_pong', {
    timestamp: Date.now()
  });
});
```

### 3. Receive Detections
```javascript
// Detections delivered via keep-alive connection
socket.on('detection_event', (data) => {
  console.log('Detection received:', data.detection);
});
```

### 4. Unsubscribe Gracefully
```javascript
// Clean up detection stream
socket.emit('unsubscribe_detections', {
  session_id: testSessionId
});

socket.on('detection_unsubscription_confirmed', (data) => {
  console.log('Stream closed:', data.session_id);
});
```

## Testing

### Manual Test Procedure
1. Start monitoring session
2. Subscribe to detection stream: `subscribe_detections`
3. Verify heartbeat logs every 5 seconds
4. Wait through idle period (no detections)
5. Verify connection stays open
6. Verify detections delivered when they occur
7. Unsubscribe: `unsubscribe_detections`
8. Verify cleanup logs

### Expected Log Output
```
🔌 Client abc123 successfully connected with keep-alive enabled
🔌 KEEP-ALIVE: Heartbeat started for client abc123 (interval: 5s)
🔌 Detection stream opened: session-456 (sid: abc123) - Keep-alive enabled
🔌 KEEP-ALIVE: Heartbeat #1 sent to abc123 (detection stream: session-456)
🔌 KEEP-ALIVE: Heartbeat #2 sent to abc123 (detection stream: session-456)
... [detections delivered]
🔌 Detection stream closed: session-456 (sid: abc123) - Detections received: 42
🔌 KEEP-ALIVE: Client abc123 no longer active, stopping heartbeat
```

## Monitoring & Diagnostics

### Check Active Streams
```python
# Server-side inspection
print(f"Active detection streams: {len(active_detection_streams)}")
for sid, info in active_detection_streams.items():
    print(f"  {sid}: session={info['session_id']}, count={info['detection_count']}")
```

### Check Heartbeat Tasks
```python
# Server-side inspection
print(f"Active heartbeat tasks: {len(connection_heartbeat_tasks)}")
for sid, task in connection_heartbeat_tasks.items():
    print(f"  {sid}: done={task.done()}, cancelled={task.cancelled()}")
```

## Benefits

1. **Prevents Premature Closure**: WebSocket stays open during entire monitoring session
2. **Explicit Stream Tracking**: Clear registration of active detection streams
3. **Enhanced Logging**: Detailed connection state information for debugging
4. **Graceful Cleanup**: Proper resource cleanup on disconnect
5. **Detection Counter**: Verification of delivered detections per stream
6. **Configurable Intervals**: 5-second heartbeat for active streaming vs 30s for general sessions

## API Reference

### WebSocket Events

#### Client → Server

| Event | Data | Description |
|-------|------|-------------|
| `subscribe_detections` | `{ session_id: string }` | Enable detection stream with keep-alive |
| `unsubscribe_detections` | `{ session_id: string }` | Disable detection stream |
| `heartbeat_pong` | `{ timestamp: number }` | (Optional) Respond to heartbeat |

#### Server → Client

| Event | Data | Description |
|-------|------|-------------|
| `detection_subscription_confirmed` | `{ session_id, keep_alive_enabled, heartbeat_interval_seconds }` | Confirm stream opened |
| `heartbeat_ping` | `{ timestamp, count, has_detection_stream }` | Keep-alive heartbeat |
| `detection_event` | `{ detection, timestamp }` | Real-time detection delivery |
| `detection_unsubscription_confirmed` | `{ session_id, timestamp }` | Confirm stream closed |

### Exported Functions

```python
from socketio_server import (
    sio,
    active_detection_streams,
    connection_heartbeat_tasks,
    heartbeat_connection
)
```

## Troubleshooting

### Connection Closes Before Detections

**Symptom**: WebSocket disconnects before detection events delivered

**Solution**: Verify client called `subscribe_detections` before monitoring starts

**Check**:
```javascript
// ❌ WRONG: No subscription
socket.on('detection_event', handler);

// ✅ CORRECT: Subscribe first
socket.emit('subscribe_detections', { session_id });
socket.on('detection_event', handler);
```

### No Heartbeats Received

**Symptom**: No `heartbeat_ping` events on client

**Check Server Logs**:
```
🔌 KEEP-ALIVE: Heartbeat started for client {sid}
```

**Verify**: Heartbeat task is running in `connection_heartbeat_tasks`

### Stale Connection Not Cleaned Up

**Symptom**: Connection stays in `active_detection_streams` after disconnect

**Check**: Verify disconnect event triggered and cleanup ran

**Fix**: Wait for 3 missed heartbeats (15 seconds) for automatic cleanup

## Performance Impact

- **Heartbeat Overhead**: ~100 bytes every 5 seconds per connection
- **Memory Overhead**: ~200 bytes per detection stream entry
- **CPU Impact**: Negligible (async sleep-based)
- **Network Impact**: ~20 bytes/sec per active connection

## Future Enhancements

1. **Adaptive Heartbeat**: Adjust interval based on detection frequency
2. **Bandwidth Monitoring**: Track total bytes sent per connection
3. **Stream Health Metrics**: Latency, jitter, packet loss
4. **Automatic Reconnection**: Client-side reconnect on failure
5. **Stream Prioritization**: QoS for high-priority detection streams

## Related Files

- `/home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py` - Main implementation
- `/home/rigade/Testing/ai-model-validation-platform/backend/websocket_enhanced.py` - Enhanced WebSocket utilities
- `/home/rigade/Testing/ai-model-validation-platform/backend/main.py` - FastAPI integration

## Authors

**Backend API Developer** - WebSocket keep-alive implementation

## Last Updated

2025-01-17
