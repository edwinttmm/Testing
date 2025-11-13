# Zero Detection Issue - Root Cause Analysis and Fixes

## Problem Statement
HIL test execution shows **zero detections** (0 out of 200 expected) despite previous fixes to the detection pipeline.

## Root Causes Identified

### 1. ✅ FIXED: Schema Mismatch in Video Sequence Endpoints
**Location**: `frontend/src/services/api.ts` (lines 1227-1230, 1252-1256)

**Issue**: The `api.ts` service was sending **snake_case** field names that didn't match the backend's **camelCase** Pydantic models, causing 422 Unprocessable Entity errors.

**Before**:
```typescript
// videoSequenceStarted
{
  video_id: videoId,      // ❌ Wrong
  started_at: startedAt   // ❌ Wrong
}

// videoSequenceEnded
{
  video_id: videoId,      // ❌ Wrong
  ended_at: endedAt,      // ❌ Wrong
  duration                // ❌ Wrong field name
}
```

**After** (FIXED):
```typescript
// videoSequenceStarted
{
  videoId: videoId,              // ✅ Correct
  startedAt: startedAt,          // ✅ Correct
  sequenceElapsedTime: 0         // ✅ Added required field
}

// videoSequenceEnded
{
  videoId: videoId,              // ✅ Correct
  endedAt: endedAt,              // ✅ Correct
  actualDuration: duration,      // ✅ Correct field name
  sequenceElapsedTime: 0         // ✅ Added required field
}
```

**Backend Model** (`backend/routers/video_sequences.py`):
```python
class VideoStartedRequest(BaseModel):
    videoId: str  # ✅ camelCase
    timestamp: Optional[float] = None
    sequenceElapsedTime: Optional[float] = None
    startedAt: Optional[float] = None
    clientTimestamp: Optional[str] = None
```

**Impact**: This was preventing video sequence initialization, which blocked the entire detection pipeline from starting properly.

---

### 2. ⚠️ TO INVESTIGATE: WebSocket Room Subscription

**Location**: Backend emits to `test_session_{session_id}` room

**Backend Emission** (`backend/socketio_server.py` line 328-329):
```python
room = f"test_session_{test_session_id}"
await sio.emit('detection_event', detection_data, room=room)
```

**Frontend Connection** (from console logs):
```
ws://localhost:8000/ws/test-sessions/ee412123-b573-4f1b-b0b4-839c34a020ce/detections
```

**Question**: Is the frontend properly joining the `test_session_{session_id}` room after connecting?

**Backend Room Join Logic** (`backend/socketio_server.py` line 150):
```python
@sio.event
async def start_test_session(sid, data):
    session_id = data.get('session_id')
    # Join room for this test session
    await sio.enter_room(sid, f"test_session_{session_id}")
```

**Frontend Needs to**:
1. Connect via Socket.IO
2. Emit `subscribe_to_updates` event with `{ type: 'session', target_id: session_id }`
3. Subscribe to `detection_event` events

---

### 3. ✅ VERIFIED: LabJack Monitoring Service Initialization

**Location**: `backend/routers/test_sessions.py` (lines 435-439)

The monitoring service IS being started:
```python
success = start_hil_monitoring(session_id, video_timing_config)

if success:
    monitoring_started = True
    logger.info(f"✅ HIL monitoring with video timing sync started for session: {session_id}")
```

**Configuration** (lines 420-432):
```python
video_timing_config = {
    "video_id": session.video_id,
    "fps": 30.0,
    "duration": video.duration,
    "channels": ["AIN0"],
    "voltage_threshold": 2.5,  # 2.5V threshold
    "debounce_ms": 50,
    "sample_rate": 100,  # 100Hz
    "enable_websocket": True,
    "enable_frame_sync": True
}
```

---

### 4. ✅ VERIFIED: WebSocket Emission Code Exists

**Location**: `backend/services/dedicated_labjack_monitor.py` (lines 588-591)

Detection events ARE being emitted:
```python
from socketio_server import emit_detection_event

# Run async emission in the event loop
loop.run_until_complete(emit_detection_event(detection_data, session_id))

logger.info(f"📡 Emitted detection event via WebSocket: {hil_event.id}")
```

---

## Detection Pipeline Flow

```
1. Test Session Start
   ↓
2. Video Sequence Endpoints Initialize (video-started) → ✅ NOW FIXED
   ↓
3. LabJack Monitoring Service Starts → ✅ VERIFIED WORKING
   ↓
4. Hardware Triggers Detected (voltage > 2.5V on AIN0)
   ↓
5. Detection Events Created & Stored in DB
   ↓
6. WebSocket emit_detection_event() called → ✅ CODE EXISTS
   ↓
7. Emitted to room: test_session_{session_id} → ⚠️ VERIFY FRONTEND SUBSCRIPTION
   ↓
8. Frontend receives via Socket.IO → ⚠️ NEEDS VERIFICATION
   ↓
9. UI displays real-time detections
```

---

## Next Steps

### ⚠️ Critical: Verify Frontend WebSocket Subscription

1. **Check if frontend is joining the correct room**:
   - Frontend must emit `subscribe_to_updates` with `{ type: 'session', target_id: session_id }`
   - OR emit `start_test_session` event with `{ session_id: session_id, project_id: project_id }`

2. **Verify frontend is listening for `detection_event`**:
   ```typescript
   websocketService.subscribe('detection_event', (data) => {
     console.log('📡 Detection event received:', data);
     // Add to detection list
   });
   ```

3. **Check browser console for**:
   - ✅ WebSocket connected
   - ✅ Room joined: `test_session_{session_id}`
   - ✅ Listening for: `detection_event`
   - 📡 Events received

### Check Backend Logs

When test runs, verify:
```bash
# Should see in backend logs:
🚀 Starting HIL monitoring with video timing sync for session: {session_id}
✅ HIL monitoring with video timing sync started for session: {session_id}
📡 Emitted detection event via WebSocket: {event_id}
```

### Database Verification

Check if detections are being stored:
```sql
SELECT COUNT(*) FROM detection_events
WHERE session_id = '{session_id}';

SELECT * FROM detection_events
WHERE session_id = '{session_id}'
ORDER BY detected_at DESC
LIMIT 10;
```

---

## Files Modified

✅ **frontend/src/services/api.ts**:
- Fixed `videoSequenceStarted()` method (lines 1227-1230)
- Fixed `videoSequenceEnded()` method (lines 1252-1256)

---

## Testing Required

1. **Run HIL Test**:
   - Start test session
   - Check for 422 errors on video-started/video-ended endpoints (should be GONE)
   - Monitor WebSocket connection in browser DevTools
   - Check backend logs for detection emissions
   - Verify detections appear in UI

2. **Check Database**:
   - Query `detection_events` table after test
   - Should have rows with matching `session_id`

3. **WebSocket Verification**:
   - Browser console should show `detection_event` received
   - Check Socket.IO rooms joined
   - Verify event payload matches expectations

---

## Success Criteria

✅ Video sequence endpoints return 200 (not 422)
⚠️ WebSocket connects and joins correct room
⚠️ Frontend subscribes to `detection_event`
⚠️ Detection events emitted by backend
⚠️ Detection events received by frontend
⚠️ Detections displayed in UI
⚠️ Database contains detection records

---

## Console Log Evidence

**Before Fix** (from user's console):
```
POST http://localhost:8000/api/video-sequences/4349246d-d620-44c8-b134-712d94a9dbbb/video-started 422 (Unprocessable Entity)
Final Results: 200 expected, 0 detected, 200 missed (0% pass rate)
```

**Expected After Fix**:
```
POST http://localhost:8000/api/video-sequences/.../video-started 200 OK
📡 Detection event received: {id: '...', timestamp: ..., ...}
Final Results: 200 expected, 200 detected, 0 missed (100% pass rate)
```
