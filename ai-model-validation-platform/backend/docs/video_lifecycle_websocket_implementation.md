# Video Lifecycle WebSocket Implementation

## Overview

Implemented WebSocket event handlers for video lifecycle events (VIDEO_STARTED, VIDEO_ENDED, VIDEO_ERROR) that coordinate with the LabJack monitoring system through the orchestrator.

## Files Created/Modified

### New Files

1. **`services/video_lifecycle_websocket_handlers.py`**
   - Main implementation of video lifecycle WebSocket handlers
   - `VideoLifecycleWebSocketHandler` class handles all lifecycle events
   - `register_video_lifecycle_handlers()` function for integration

2. **`tests/test_video_lifecycle_websocket.py`**
   - Comprehensive test suite for WebSocket handlers
   - Tests all event types and error conditions
   - Includes clock synchronization tests

3. **`docs/video_lifecycle_websocket_implementation.md`**
   - This documentation file

### Modified Files

1. **`socketio_server.py`**
   - Added import for video lifecycle handlers
   - Integrated handler registration in `create_socketio_app()`
   - Graceful fallback if handlers are unavailable

## Implementation Details

### Event Handlers

#### 1. `video-lifecycle` Event

Handles three event types:

**VIDEO_STARTED**
- Validates required fields: `sessionId`, `videoId`, `timestamp`
- Calls `VideoLifecycleOrchestrator.handle_video_started()`
- Starts LabJack monitoring for the video
- Emits acknowledgment: `video-started-ack`
- Broadcasts to session room: `video-monitoring-update`

**VIDEO_ENDED**
- Validates required fields: `sessionId`, `videoId`, `timestamp`
- Calls `VideoLifecycleOrchestrator.handle_video_ended()`
- Stops LabJack monitoring for the video
- Emits acknowledgment: `video-ended-ack`
- Broadcasts to session room: `video-monitoring-update`

**VIDEO_ERROR**
- Validates required fields: `sessionId`, `error`
- Calls `VideoLifecycleOrchestrator.handle_video_error()`
- Stops LabJack monitoring if active
- Emits acknowledgment: `video-error-ack`
- Broadcasts to session room: `video-monitoring-update`

#### 2. `clock-sync-ping` Event

NTP-like clock synchronization:
- Receives client timestamp `t1`
- Records server receive time `t2`
- Responds with `t1`, `t2`, and send time `t3`
- Emits: `clock-sync-pong`

### Event Payload Structures

#### Incoming Events

**VIDEO_STARTED:**
```json
{
  "event": "VIDEO_STARTED",
  "sessionId": "session-uuid",
  "videoId": "video-uuid",
  "timestamp": 1234567890.123,
  "clockOffset": 10.5
}
```

**VIDEO_ENDED:**
```json
{
  "event": "VIDEO_ENDED",
  "sessionId": "session-uuid",
  "videoId": "video-uuid",
  "timestamp": 1234567900.456
}
```

**VIDEO_ERROR:**
```json
{
  "event": "VIDEO_ERROR",
  "sessionId": "session-uuid",
  "videoId": "video-uuid",
  "error": "Error message"
}
```

**Clock Sync Ping:**
```json
{
  "t1": 1234567890.123456
}
```

#### Outgoing Events

**Acknowledgments:**
```json
{
  "sessionId": "session-uuid",
  "videoId": "video-uuid",
  "status": "monitoring_started|monitoring_stopped|error_handled",
  "timestamp": 1234567890.789
}
```

**Monitoring Updates:**
```json
{
  "event": "monitoring_started|monitoring_stopped|monitoring_error",
  "sessionId": "session-uuid",
  "videoId": "video-uuid",
  "timestamp": 1234567890.789
}
```

**Clock Sync Pong:**
```json
{
  "t1": 1234567890.123456,
  "t2": 1234567890.234567,
  "t3": 1234567890.345678
}
```

**Errors:**
```json
{
  "error": "Error message",
  "sessionId": "session-uuid",
  "videoId": "video-uuid",
  "timestamp": 1234567890.789
}
```

## Error Handling

### Validation Errors

- Missing `event` field → `video-lifecycle-error` with "Missing required field: event"
- Missing `sessionId` → `video-lifecycle-error` with "Missing required field: sessionId"
- Missing `videoId` (for VIDEO_STARTED/VIDEO_ENDED) → `video-lifecycle-error` with "Missing required field: videoId"
- Unknown event type → `video-lifecycle-error` with "Unknown event type: {type}"

### Orchestrator Errors

- Orchestrator returns `False` → `video-lifecycle-error` with "Failed to start/stop LabJack monitoring"
- Exception in orchestrator → `video-lifecycle-error` with exception message
- Test continues even if monitoring fails (non-blocking)

### Database Errors

- Database sessions are properly closed in `finally` blocks
- Errors are logged but don't crash the WebSocket connection

## Integration with Orchestrator

The handlers call the `VideoLifecycleOrchestrator` (to be implemented by another agent):

```python
from services.video_lifecycle_orchestrator import VideoLifecycleOrchestrator

orchestrator = VideoLifecycleOrchestrator(db)

# For VIDEO_STARTED
await orchestrator.handle_video_started(
    session_id=session_id,
    video_id=video_id,
    frontend_timestamp=frontend_timestamp,
    clock_offset_ms=clock_offset_ms
)

# For VIDEO_ENDED
await orchestrator.handle_video_ended(
    session_id=session_id,
    video_id=video_id,
    frontend_timestamp=frontend_timestamp
)

# For VIDEO_ERROR
await orchestrator.handle_video_error(
    session_id=session_id,
    video_id=video_id,
    error_message=error_message
)
```

## Testing

Run tests:
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
pytest tests/test_video_lifecycle_websocket.py -v
```

Test coverage:
- ✅ Successful VIDEO_STARTED handling
- ✅ VIDEO_STARTED with missing fields
- ✅ VIDEO_STARTED orchestrator failure
- ✅ Successful VIDEO_ENDED handling
- ✅ Successful VIDEO_ERROR handling
- ✅ Unknown event types
- ✅ Clock synchronization
- ✅ Handler registration

## Usage Example

### Frontend (JavaScript)

```javascript
// Connect to WebSocket
const socket = io('http://localhost:8000');

// Send VIDEO_STARTED event
socket.emit('video-lifecycle', {
  event: 'VIDEO_STARTED',
  sessionId: 'test-session-123',
  videoId: 'video-456',
  timestamp: Date.now() / 1000,
  clockOffset: 10.5
});

// Listen for acknowledgment
socket.on('video-started-ack', (data) => {
  console.log('Video monitoring started:', data);
});

// Listen for errors
socket.on('video-lifecycle-error', (error) => {
  console.error('Lifecycle error:', error);
});

// Clock synchronization
socket.emit('clock-sync-ping', {
  t1: Date.now() / 1000
});

socket.on('clock-sync-pong', (data) => {
  const t4 = Date.now() / 1000;
  const roundTrip = t4 - data.t1;
  const offset = ((data.t2 - data.t1) + (data.t3 - t4)) / 2;
  console.log('Clock offset:', offset, 'seconds');
});
```

## Architecture Benefits

1. **Separation of Concerns**: WebSocket handlers only handle event routing, orchestrator handles business logic
2. **Error Isolation**: Errors in lifecycle events don't crash tests
3. **Testability**: Handlers can be tested independently of orchestrator
4. **Graceful Degradation**: System continues if handlers fail to load
5. **Event Broadcasting**: Session rooms allow multiple clients to monitor lifecycle events
6. **Clock Synchronization**: NTP-like sync for accurate timing

## Next Steps

The following agent needs to implement:

1. **`services/video_lifecycle_orchestrator.py`**
   - `VideoLifecycleOrchestrator` class
   - `handle_video_started()` method
   - `handle_video_ended()` method
   - `handle_video_error()` method
   - Integration with LabJack monitoring service

2. **Database Model (Optional)**
   - `VideoLifecycleEvent` model for event persistence
   - Track event history for debugging/auditing

## Notes

- Handlers use lazy imports to avoid circular dependencies
- All timestamps are in seconds since epoch (Unix time)
- Clock offset is in milliseconds
- Session rooms follow naming convention: `session_{session_id}`
- Acknowledgments are sent to individual clients (via `sid`)
- Monitoring updates are broadcast to session rooms
