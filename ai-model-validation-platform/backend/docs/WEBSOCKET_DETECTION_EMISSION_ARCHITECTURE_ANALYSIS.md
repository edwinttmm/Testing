# WebSocket Detection Emission Architecture Analysis

## Executive Summary

**CRITICAL FINDING**: There are TWO separate emission paths for detection events, causing potential conflicts and confusion:

1. **Socket.IO Path** (main.py:241) - `emit_detection_event()` from `socketio_server.py`
2. **WebSocket Path** (main.py:4111) - `send_detection_to_client()` overwriting the first path

**ISSUE**: The WebSocket endpoint at `/ws/test-sessions/{session_id}/detections` (main.py:4075-4147) calls `set_websocket_emit_function()` which **OVERWRITES** the Socket.IO emission function registered during startup, potentially breaking Socket.IO clients.

---

## 1. Socket.IO Detection Emission Path (Primary)

### Registration (main.py:238-242)
```python
from socketio_server import emit_detection_event
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor

monitor = get_dedicated_labjack_monitor(websocket_emit_fn=emit_detection_event)
logger.info("✅ WebSocket real-time detection broadcasting enabled")
```

### Flow Chain:
```
main.py:241 (startup)
    ↓ registers
dedicated_labjack_monitor.py:96
    ↓ calls
labjack_detection_service.py:332 (set_websocket_emit_function)
    ↓ stores in
labjack_detection_service.py:195 (_websocket_emit_fn)
    ↓ called by
labjack_detection_service.py:1918 (await self._websocket_emit_fn())
    ↓ executes
socketio_server.py:522 (emit_detection_event)
    ↓ emits to Socket.IO rooms
socketio_server.py:558-562
```

### emit_detection_event() Function (socketio_server.py:522-569)

**Purpose**: Broadcast detection events via Socket.IO to session-specific rooms

**Implementation**:
```python
async def emit_detection_event(detection_data: dict, test_session_id: str):
    """Emit real-time detection event to all connected clients

    CRITICAL: This function updates detection counters for keep-alive monitoring.
    """
    try:
        # Timestamp validation (lines 530-546)
        # ... ensures ISO 8601 format ...

        # Update detection counter for active streams (lines 552-554)
        for sid, stream_info in active_detection_streams.items():
            if stream_info.get('session_id') == test_session_id:
                stream_info['detection_count'] = stream_info.get('detection_count', 0) + 1

        # CRITICAL FIX: Use "session_" prefix to match client join_session room naming
        room = f"session_{test_session_id}"  # ✅ Line 558
        await sio.emit('detection_event', detection_data, room=room)

        # Emit to general detections room for monitoring
        await sio.emit('detection_event', detection_data, room='detections')

        logger.debug(f"Emitted detection event to room {room}")
```

**Socket.IO Rooms Used**:
- `session_{test_session_id}` - Session-specific room (primary)
- `detections` - General monitoring room (broadcast)

**Message Format**:
```javascript
{
  'id': hil_event.id,
  'timestamp': '2025-01-17T12:34:56.789Z',  // ISO 8601
  'timestamp_ms': 1737118496789,
  'video_relative_timestamp': 0.123,
  'sequence_timestamp': 5.678,
  'latency_ms': 12.5,
  'voltage': 3.3,
  'channel': 'AIN0',
  'frame_number': 42,
  'timing_quality': 'excellent',
  'detection_type': 'labjack_voltage',
  'source': 'dedicated_labjack_monitor',
  'video_id': 'uuid-video',
  'sequence_id': 'uuid-sequence',
  'sequence_video_result_id': 'uuid-result',
  'video_play_offset_ms': 123.45
}
```

---

## 2. WebSocket Detection Emission Path (Overwriting)

### Registration (main.py:4109-4113)
```python
# Get detection monitor instance
detection_monitor = get_detection_service()

# Register WebSocket callback with detection service
if detection_monitor and hasattr(detection_monitor, 'set_websocket_emit_function'):
    detection_monitor.set_websocket_emit_function(send_detection_to_client)  # ⚠️ OVERWRITES
    callback_registered = True
```

### send_detection_to_client() Function (main.py:4095-4106)

**Purpose**: Send detection events via native WebSocket to a single client

**Implementation**:
```python
async def send_detection_to_client(detection_data: dict, event_session_id: str):
    """Send detection event to this WebSocket client"""
    if event_session_id == session_id:  # Session filtering
        try:
            await websocket.send_json({
                "type": "detection_event",
                "data": detection_data,
                "timestamp": datetime.now().isoformat()
            })
            logger.debug(f"📤 Sent detection event to WebSocket client: {session_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send detection to WebSocket: {e}")
```

**Emission Pattern**: Unicast (single WebSocket connection)

**Message Format**:
```javascript
{
  "type": "detection_event",
  "data": { /* detection_data object */ },
  "timestamp": "2025-01-17T12:34:56.789000"
}
```

---

## 3. The Overwrite Problem

### Issue Description:
When a client connects to `/ws/test-sessions/{session_id}/detections`, the WebSocket endpoint calls:

```python
detection_monitor.set_websocket_emit_function(send_detection_to_client)
```

This **OVERWRITES** the global `_websocket_emit_fn` in `labjack_detection_service.py:332`:

```python
def set_websocket_emit_function(self, emit_fn: Callable):
    """Set the WebSocket emission function from socketio_server."""
    self._websocket_emit_fn = emit_fn  # ⚠️ GLOBAL STATE - overwritten by last caller
```

### Consequences:

1. **Socket.IO clients lose real-time updates** after WebSocket connection
2. **Only one emission path active at a time** (last registered wins)
3. **Session-specific unicast replaces broadcast** to all Socket.IO clients
4. **Race condition**: Emission path depends on connection timing

### Evidence from Code:

**labjack_detection_service.py:1883-1918**:
```python
# ✅ NEW: Emit detection event via WebSocket after successful storage
if self._websocket_emit_fn:  # ⚠️ Only ONE function registered
    try:
        # ... timestamp validation ...

        # Call async emit function
        await self._websocket_emit_fn(detection_data, event.session_id)  # ⚠️ Calls LAST registered
        logger.debug(f"🔔 WebSocket emission triggered for detection {event.id}")
```

---

## 4. Frontend Socket.IO Event Handlers

### Connection Setup (websocketService.ts:171-172)
```typescript
// Emit join_session event
this.socket.emit('join_session', { session_id: sessionId });
```

### Detection Event Listener (websocketService.ts:390-393)
```typescript
// Handle detection events for real-time updates
this.socket.on('detection_event', (data) => {
  console.log('🎯 Detection event received:', data);
  this.notifySubscribers('detection_event', data);
});
```

### Room Joining Pattern:
Frontend emits `join_session` → Backend joins client to `session_{session_id}` room → Detection events broadcast to room

### Used by:
- `HILResults.tsx:965` - Main HIL results page
- `EnhancedResults.tsx:193` - Enhanced results page
- `detectionService.ts:489` - Detection service

---

## 5. Socket.IO Room Strategy

### Room Naming Convention:

| Room Name | Purpose | Joined By |
|-----------|---------|-----------|
| `session_{session_id}` | Session-specific events | `join_session` handler (socketio_server.py:260) |
| `test_session_{session_id}` | Test session updates | `subscribe_detections` handler (socketio_server.py:309) |
| `detections` | General detection monitoring | `subscribe_to_updates` handler (socketio_server.py:709) |
| `general` | System-wide broadcasts | Auto-joined on connect (socketio_server.py:93) |

### CRITICAL ROOM NAMING ISSUE:

**Detection emission uses**: `session_{test_session_id}` (line 558)
**Clients join via**: `join_session` which creates `session_{session_id}` (line 260)

✅ **These MATCH** - Clients should receive events correctly

**Alternative room**: `test_session_{session_id}` used by `subscribe_detections` (line 309)
- This is for keep-alive monitoring, not primary detection events

---

## 6. Correct Emission Pattern for HIL Tests

### ✅ RECOMMENDED APPROACH: Use Socket.IO Only

**Why**:
1. **Broadcast capability**: Send to multiple clients simultaneously
2. **Room isolation**: Session-specific delivery via `session_{session_id}` rooms
3. **No overwriting**: Socket.IO path registered at startup remains stable
4. **Frontend compatibility**: All production pages use Socket.IO client

**Implementation**:
```python
# main.py:238-242 (already correct - keep as-is)
from socketio_server import emit_detection_event
monitor = get_dedicated_labjack_monitor(websocket_emit_fn=emit_detection_event)
```

**For HIL Tests**:
```python
# Test setup
import socketio

# Connect Socket.IO client
sio = socketio.AsyncClient()
await sio.connect('http://localhost:8000')

# Join session room
await sio.emit('join_session', {'session_id': test_session_id})

# Listen for detections
@sio.on('detection_event')
async def on_detection(data):
    print(f"Detection received: {data}")
    # ... validate detection ...

# Start HIL test
# ... detections automatically emitted via emit_detection_event() ...
```

---

## 7. The Right Way to Send Detections

### Architecture Decision:

**SINGLE EMISSION PATH**: Keep Socket.IO as the ONLY real-time detection emission mechanism

### Changes Required:

#### Option A: Remove WebSocket Endpoint (RECOMMENDED)
```python
# main.py - DELETE lines 4075-4147
# @app.websocket("/ws/test-sessions/{session_id}/detections")
# async def websocket_test_session_detections(...):
#     ...
```

**Rationale**:
- WebSocket endpoint duplicates Socket.IO functionality
- Causes emission path conflicts
- Not used by production frontend
- Adds unnecessary complexity

#### Option B: Make WebSocket Endpoint Read-Only
```python
@app.websocket("/ws/test-sessions/{session_id}/detections")
async def websocket_test_session_detections(websocket: WebSocket, session_id: str):
    await websocket.accept()

    # ❌ REMOVE: detection_monitor.set_websocket_emit_function(send_detection_to_client)

    # ✅ ADD: Subscribe to Socket.IO events instead
    from socketio_server import sio

    async def forward_to_websocket(data):
        """Forward Socket.IO events to WebSocket client"""
        if data.get('session_id') == session_id:
            await websocket.send_json({
                "type": "detection_event",
                "data": data,
                "timestamp": datetime.now().isoformat()
            })

    # Subscribe to Socket.IO room events (implementation TBD)
    # ...
```

**Rationale**:
- WebSocket becomes a "view" into Socket.IO stream
- No overwriting of emission function
- Maintains WebSocket endpoint for testing tools

---

## 8. Multi-Session Isolation Strategy

### Current Approach (Correct):
**Room-based isolation** via Socket.IO rooms

### How It Works:

1. **Client connects**: Joins `session_{session_id}` room
2. **Detection emitted**: Sent to `room=session_{test_session_id}`
3. **Delivery**: Only clients in that specific room receive event

### Example:

```
Session A (ID: abc123)
  ↓
Client 1 joins room "session_abc123"
Client 2 joins room "session_abc123"

Session B (ID: def456)
  ↓
Client 3 joins room "session_def456"

Detection for Session A emitted to "session_abc123"
  → Client 1 receives ✅
  → Client 2 receives ✅
  → Client 3 DOES NOT receive ✅ (different room)
```

### Room Validation (socketio_server.py:247-257):
```python
# Validate session exists
db = SessionLocal()
try:
    from models import TestSession
    session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if not session:
        await sio.emit('error', {
            'message': f'Invalid session_id: {session_id}'
        }, room=sid)
        return {'error': 'Invalid session_id'}
```

---

## 9. Broadcast vs Unicast Comparison

| Aspect | Socket.IO (emit_detection_event) | WebSocket (send_detection_to_client) |
|--------|----------------------------------|--------------------------------------|
| **Pattern** | Broadcast (room-based) | Unicast (single connection) |
| **Clients** | Multiple clients per session | One client per WebSocket |
| **Isolation** | Room-based (`session_{id}`) | Session ID filtering in function |
| **Scalability** | Excellent (built-in rooms) | Poor (one WebSocket per session) |
| **Frontend Compatibility** | ✅ All production pages | ❌ Not used by production |
| **Keep-Alive** | ✅ Heartbeat mechanism | Manual heartbeat required |
| **Reconnection** | ✅ Automatic (Socket.IO client) | Manual reconnection logic |
| **Event Replay** | ✅ Possible (room history) | ❌ No replay support |

---

## 10. Recommendations

### Immediate Actions:

1. **DELETE WebSocket endpoint** (main.py:4075-4147)
   - Eliminates emission path conflict
   - Simplifies architecture
   - Removes untested/unused code path

2. **Document Socket.IO as canonical emission path**
   - Update HIL testing documentation
   - Clarify room naming conventions
   - Provide Socket.IO client examples for tests

3. **Add emission path validation**
   ```python
   # labjack_detection_service.py
   def set_websocket_emit_function(self, emit_fn: Callable):
       """Set the WebSocket emission function - SINGLETON pattern enforced"""
       if self._websocket_emit_fn is not None:
           logger.warning(
               f"⚠️ OVERWRITING existing WebSocket emit function! "
               f"Old: {self._websocket_emit_fn.__name__}, "
               f"New: {emit_fn.__name__}"
           )
       self._websocket_emit_fn = emit_fn
   ```

### Long-Term Improvements:

1. **Refactor to event bus pattern**
   - Replace direct function assignment with pub/sub
   - Allow multiple emission handlers simultaneously
   - Example: `detection_event_bus.subscribe('detection', emit_fn)`

2. **Add emission metrics**
   - Track which emission path was used
   - Monitor delivery success rates
   - Alert on emission failures

3. **Create HIL testing utilities**
   ```python
   # tests/utils/socketio_test_client.py
   class HILTestSocketClient:
       """Socket.IO client for HIL tests with detection tracking"""

       async def connect_and_subscribe(self, session_id: str):
           """Connect and join session room"""
           await self.sio.connect(BACKEND_URL)
           await self.sio.emit('join_session', {'session_id': session_id})

       async def wait_for_detections(self, count: int, timeout: float = 30.0):
           """Wait for N detections with timeout"""
           # ...
   ```

---

## 11. Summary: The RIGHT Way for HIL Tests

### ✅ CORRECT PATTERN:

```python
# 1. Backend: Use Socket.IO emission (already configured correctly)
# main.py:238-242
from socketio_server import emit_detection_event
monitor = get_dedicated_labjack_monitor(websocket_emit_fn=emit_detection_event)

# 2. HIL Test: Connect Socket.IO client
import socketio

async def test_hil_detection_emission():
    # Connect Socket.IO client
    sio = socketio.AsyncClient()
    await sio.connect('http://localhost:8000')

    # Join session room
    test_session_id = 'test-session-uuid'
    await sio.emit('join_session', {'session_id': test_session_id})

    # Wait for room join confirmation
    @sio.on('joined_session')
    async def on_joined(data):
        print(f"✅ Joined session room: {data}")

    # Listen for detection events
    detections_received = []

    @sio.on('detection_event')
    async def on_detection(data):
        print(f"🎯 Detection received: {data}")
        detections_received.append(data)

    # Start LabJack monitoring
    await start_labjack_monitoring(test_session_id)

    # Wait for detections
    await asyncio.sleep(10)  # Or use proper event waiting

    # Validate detections
    assert len(detections_received) > 0
    for det in detections_received:
        assert 'timestamp' in det
        assert 'voltage' in det
        assert det['session_id'] == test_session_id  # Implicit via room

    # Cleanup
    await sio.emit('leave_session', {'session_id': test_session_id})
    await sio.disconnect()
```

### ❌ INCORRECT PATTERN (avoid):
```python
# Using native WebSocket endpoint
websocket = await websockets.connect(f"ws://localhost:8000/ws/test-sessions/{session_id}/detections")
# This OVERWRITES Socket.IO emission and breaks other clients!
```

---

## Conclusion

**Current Issue**: Dual emission paths with global state overwriting

**Root Cause**: WebSocket endpoint at main.py:4075-4147 calls `set_websocket_emit_function()`, overwriting the Socket.IO emission function registered at startup

**Solution**: Use Socket.IO exclusively for detection emission
- ✅ Broadcast to multiple clients
- ✅ Room-based session isolation
- ✅ Production-proven and frontend-compatible
- ✅ Built-in heartbeat and reconnection

**Next Steps**:
1. Remove WebSocket endpoint (main.py:4075-4147)
2. Update HIL tests to use Socket.IO client
3. Document Socket.IO as canonical detection emission path
4. Add emission path validation/monitoring
