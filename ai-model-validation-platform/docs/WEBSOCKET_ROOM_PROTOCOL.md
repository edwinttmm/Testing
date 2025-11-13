# WebSocket Room-Based Event Isolation Protocol

## Overview

This document describes the Socket.IO room-based event isolation system implemented to improve privacy, scalability, and bandwidth efficiency for concurrent HIL test sessions.

## Architecture

### Before (Broadcast Model)
```
Backend → ALL clients (filter client-side by session_id)
```
**Problems:**
- All clients receive all events
- Privacy concern: clients see other session IDs
- Bandwidth scales with total event rate
- Doesn't scale with concurrent sessions

### After (Room-Based Isolation)
```
Backend → Session Room → Only subscribed clients
```
**Benefits:**
- Events scoped to session rooms only
- Privacy: no cross-session data leakage
- Bandwidth scales with session rate (not total event rate)
- Natural scalability for concurrent sessions

## Protocol Specification

### 1. Client Connection Flow

```typescript
// 1. Connect to Socket.IO server
await websocketService.connect();

// 2. Join session room
await websocketService.joinSession(sessionId);

// 3. Listen to events (no filtering needed - already scoped to room)
websocketService.subscribe('detection_event', (data) => {
  // Process detection - guaranteed to be for this session
  handleDetection(data);
});

// 4. Leave session room when done
await websocketService.leaveSession(sessionId);
```

### 2. Room Naming Convention

**Format:** `session_{session_id}`

**Examples:**
- Session `abc123` → Room `session_abc123`
- Session `test-456` → Room `session_test-456`

### 3. Event Payload Changes

#### Before (with session_id):
```json
{
  "session_id": "abc123",
  "voltage": 3.3,
  "timestamp": 12345.67
}
```

#### After (NO session_id):
```json
{
  "voltage": 3.3,
  "timestamp": 12345.67
}
```

**Rationale:** Session context is already established by room membership. Including `session_id` in payloads is redundant and a privacy leak.

### 4. Backend Emission

#### Old Method (Broadcast):
```python
# DEPRECATED
socketio.emit('detection_event', {
    'session_id': session_id,
    'voltage': voltage
})
```

#### New Method (Room-Based):
```python
from services.websocket_rooms import notify_session_room

notify_session_room(session_id, 'detection_event', {
    'voltage': voltage  # No session_id needed
})
```

## API Reference

### Frontend (TypeScript)

#### `joinSession(sessionId: string): Promise<boolean>`
Join a session room for event isolation.

**Parameters:**
- `sessionId` - Test session identifier

**Returns:** Promise resolving to `true` if successful

**Example:**
```typescript
try {
  await websocketService.joinSession('abc123');
  console.log('Joined session room');
} catch (error) {
  console.error('Failed to join:', error);
}
```

#### `leaveSession(sessionId: string): Promise<boolean>`
Leave a session room.

**Parameters:**
- `sessionId` - Test session identifier

**Returns:** Promise resolving to `true` if successful

**Example:**
```typescript
await websocketService.leaveSession('abc123');
```

### Backend (Python)

#### `notify_session_room(session_id, event, data) -> bool`
Emit event to session room only.

**Parameters:**
- `session_id` - Test session identifier
- `event` - Event name
- `data` - Event payload (dict)

**Returns:** `True` if emission succeeded

**Example:**
```python
from services.websocket_rooms import notify_session_room

notify_session_room('abc123', 'detection_event', {
    'voltage': 3.3,
    'timestamp': time.time()
})
```

#### `get_room_members(session_id) -> int`
Get number of clients in session room.

**Parameters:**
- `session_id` - Test session identifier

**Returns:** Number of clients in room

**Example:**
```python
from services.websocket_rooms import get_room_members

member_count = get_room_members('abc123')
print(f"{member_count} clients watching session")
```

#### `broadcast_to_room(session_id, event, data) -> bool`
Broadcast event to session room with logging.

**Parameters:**
- `session_id` - Test session identifier
- `event` - Event name
- `data` - Event payload (dict)

**Returns:** `True` if broadcast succeeded

**Example:**
```python
from services.websocket_rooms import broadcast_to_room

broadcast_to_room('abc123', 'session_completed', {
    'status': 'completed',
    'duration': 125.5
})
```

## Event Types

### Detection Events
**Event:** `detection_event`

**Payload:**
```json
{
  "id": "detection_uuid",
  "timestamp": 12345.67,
  "voltage": 3.3,
  "channel": "AIN0",
  "latency_ms": 42.5,
  "video_id": "video_uuid",
  "frame_number": 120
}
```

**Scope:** Session room only

### Video Lifecycle Events
**Events:** `video_started`, `video_completed`, `video_transition`

**Payload:**
```json
{
  "video_id": "video_uuid",
  "status": "playing",
  "timestamp": 12345.67
}
```

**Scope:** Session room only

### Session Status Events
**Events:** `session_started`, `session_completed`, `session_failed`

**Payload:**
```json
{
  "status": "completed",
  "duration": 125.5,
  "detection_count": 15
}
```

**Scope:** Session room only

## Migration Guide

### Updating Service Files

**Before:**
```python
from socketio_server import emit_detection_event

emit_detection_event({
    'session_id': session_id,
    'voltage': voltage
}, session_id)
```

**After:**
```python
from services.websocket_rooms import notify_session_room

notify_session_room(session_id, 'detection_event', {
    'voltage': voltage
})
```

### Updating Frontend Components

**Before:**
```typescript
websocketService.subscribe('detection_event', (data) => {
  // Filter by session_id
  if (data.session_id === sessionId) {
    handleDetection(data);
  }
});
```

**After:**
```typescript
// Join session room first
await websocketService.joinSession(sessionId);

// No filtering needed - already scoped to session
websocketService.subscribe('detection_event', (data) => {
  handleDetection(data);
});
```

## Reconnection Handling

After reconnection, clients **MUST** rejoin their session rooms:

```typescript
websocketService.subscribe('connection', (data) => {
  if (data.status === 'reconnected' && data.needsRejoin) {
    // Rejoin session room after reconnection
    websocketService.joinSession(sessionId)
      .then(() => console.log('Rejoined session after reconnect'))
      .catch(error => console.error('Failed to rejoin:', error));
  }
});
```

## Privacy Benefits

### Before
- Client A in Session 1 sees: `{session_id: "session_2", voltage: 3.3}`
- Privacy leak: Client A knows Session 2 exists and is active

### After
- Client A in Session 1 receives only Session 1 events
- No knowledge of other sessions
- Perfect session isolation

## Scalability Benefits

### Bandwidth Comparison

**Scenario:** 10 concurrent sessions, 100 detections/sec total

**Before (Broadcast):**
- All 10 clients receive all 100 events/sec
- Total bandwidth: 1000 events/sec distributed

**After (Room-Based):**
- Each client receives only their session's events (~10 events/sec)
- Total bandwidth: 100 events/sec distributed
- **10x bandwidth reduction**

### Scalability Formula

**Before:** `Bandwidth = Events × Clients`
**After:** `Bandwidth = Events × (Clients_per_session)`

Room-based isolation ensures bandwidth scales with session rate, not total event rate.

## Testing

### Unit Tests
Located in: `/backend/tests/test_websocket_room_isolation.py`

Run tests:
```bash
pytest backend/tests/test_websocket_room_isolation.py -v
```

### Integration Tests
Test cross-session isolation:
```bash
pytest backend/tests/test_websocket_room_isolation.py::TestPrivacyAndScalability::test_cross_session_isolation -v
```

## Monitoring

### Room Member Tracking
```python
from services.websocket_rooms import get_all_session_rooms

rooms = get_all_session_rooms()
for session_id, member_count in rooms.items():
    print(f"Session {session_id}: {member_count} clients")
```

### Health Check
```python
from services.websocket_rooms import get_room_members

# Check if session has active clients
if get_room_members(session_id) > 0:
    print(f"Session {session_id} has active viewers")
```

## Best Practices

1. **Always join session rooms** before subscribing to events
2. **Leave rooms** when navigating away or unmounting components
3. **Handle reconnections** by rejoining session rooms
4. **Never include session_id** in event payloads (redundant and privacy leak)
5. **Use room utilities** (`notify_session_room`, `broadcast_to_room`) instead of direct `sio.emit`

## Production Readiness Checklist

- [x] Room handlers implemented (join_session, leave_session)
- [x] Room utilities module created
- [x] Backend services updated to use room emission
- [x] Frontend WebSocket service supports join/leave
- [x] Frontend components updated to use room-based events
- [x] Integration tests for room isolation
- [x] Documentation complete
- [x] Privacy verification (no session_id in payloads)
- [x] Scalability verification (bandwidth efficiency)
- [x] Reconnection handling implemented

## Support

For questions or issues, contact the development team or file an issue in the project repository.

---

**Version:** 1.0
**Last Updated:** 2025-11-11
**Author:** WebSocket Optimization Specialist
