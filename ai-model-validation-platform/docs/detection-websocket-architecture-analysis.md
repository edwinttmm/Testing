# Detection Event Streaming Architecture Analysis

## Executive Summary

The HIL testing system experiences **zero detection events** reaching the frontend despite:
- ✅ WebSocket successfully connecting to `ws://localhost:8000/ws/test-sessions/{session_id}/detections`
- ✅ LabJack hardware connected and functioning
- ✅ Ground truth data loading perfectly (242 events)
- ⚠️ Warning message: `No sequence start time available`

**Root Cause:** Detection events are being filtered/blocked before WebSocket emission due to missing `sequence_start_time` initialization.

---

## Architecture Overview

### Detection Event Flow (Text Diagram)

```
┌─────────────────────────────────────────────────────────────────┐
│                  HARDWARE LAYER (LabJack)                        │
│  - Physical voltage triggers from test equipment                 │
│  - GPIO pins detect state changes                                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│         DETECTION CAPTURE (dedicated_labjack_monitor.py)         │
│  - Polls LabJack device at high frequency                        │
│  - Creates HILDetectionEvent objects with timing data            │
│  - Enriches with video/sequence context                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│       TIMING ENRICHMENT (video_sequence_orchestrator.py)         │
│  ⚠️ CRITICAL POINT: sequence_start_time initialization          │
│  - Calculates video_relative_timestamp                           │
│  - Calculates sequence_timestamp                                 │
│  - Assigns video_id for multi-video sequences                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│         DATABASE STORAGE (DetectionEvent model)                  │
│  - Persists to detection_events table                            │
│  - Stores all timing fields                                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│     WEBSOCKET EMISSION (_emit_detection_event_sync)              │
│  - Formats detection payload                                     │
│  - Uses room-based emission (session-specific)                   │
│  - Calls notify_session_room()                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│      SOCKET.IO BROADCAST (socketio_server.py)                    │
│  - emit_detection_event() function                               │
│  - Room: f"session_{session_id}"                                 │
│  - Event: 'detection_event'                                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              FRONTEND CLIENT (React/TypeScript)                  │
│  - Subscribes to detection_event                                 │
│  - Updates UI with real-time detections                          │
│  - Shows "No sequence start time" warning                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. WebSocket Route Definition

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py`

**Line 286-333:** `subscribe_detections` event handler

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

    # Join detection monitoring room
    room_name = f"test_session_{session_id}"
    await sio.enter_room(sid, room_name)
```

**Key Points:**
- ✅ Frontend successfully subscribes and joins the room
- ✅ Heartbeat mechanism prevents connection closure
- ✅ Room naming matches emission pattern

---

### 2. Detection Event Schema

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/models.py`

**Lines 328-427:** `DetectionEvent` SQLAlchemy model

**Critical Fields:**
```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    # Primary timing fields
    timestamp = Column(Float, nullable=False, index=True)
    actual_latency_ms = Column(Float, nullable=True, index=True)

    # HIL-specific fields
    labjack_timestamp = Column(Float, nullable=True, index=True)
    labjack_voltage = Column(Float, nullable=True)
    detection_channel = Column(String, nullable=True)

    # Multi-video sequence timing
    sequence_timestamp = Column(Float, nullable=True, index=True)
    video_relative_timestamp = Column(Float, nullable=True, index=True)
    video_play_offset_ms = Column(Float, nullable=True)

    # Context fields
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=True)
    sequence_id = Column(String(36), nullable=True, index=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"), nullable=False)
```

**What Should Be Present:**
1. `timestamp` - Unix timestamp of detection
2. `video_relative_timestamp` - Time since video started (seconds)
3. `sequence_timestamp` - Time since sequence started (seconds)
4. `labjack_voltage` - Voltage reading that triggered detection
5. `detection_channel` - LabJack channel (e.g., "AIN0")
6. `video_id` - Which video in the sequence (multi-video support)

---

### 3. Sequence Start Time Initialization

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Lines 315-347:** Critical initialization logic

```python
def notify_video_started(
    self,
    sequence_id: str,
    video_id: str,
    actual_start_timestamp: float,
    db: Session
) -> bool:
    """CRITICAL: Initialize sequence_start_time on first video"""

    # Get sequence state from memory
    sequence = self.active_sequences.get(sequence_id)

    # ISSUE: sequence_start_time initialization logic
    if sequence.sequence_start_time is None:
        # Atomic CAS (Compare-And-Set) to prevent race conditions
        try:
            video_sequence_db = db.query(VideoTestSequence).filter(
                VideoTestSequence.id == sequence_id,
                VideoTestSequence.sequence_start_time == None  # WHERE clause
            ).with_for_update().first()

            if video_sequence_db:
                # CRITICAL: Set sequence start time
                video_sequence_db.sequence_start_time = actual_start_timestamp
                db.commit()
                sequence.sequence_start_time = actual_start_timestamp
                logger.info(f"✅ Set sequence_start_time={actual_start_timestamp:.6f}")
        except Exception as e:
            logger.error(f"Failed to set sequence_start_time: {e}")

    # Calculate video play offset
    video_play_offset_ms = (actual_start_timestamp - sequence.sequence_start_time) * 1000.0
```

**Problem Areas:**
1. **Timing:** Is `notify_video_started` called BEFORE detections arrive?
2. **Database:** Is the database update committed successfully?
3. **Memory:** Is the in-memory `sequence` object updated?
4. **Race Condition:** Could detections arrive before initialization completes?

---

### 4. Detection Event Emission

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

**Lines 822-860:** WebSocket emission logic

```python
def _emit_detection_event_sync(self, hil_event: HILDetectionEvent, session_id: str):
    """Thread-safe wrapper for async WebSocket emission to session room"""
    try:
        # Create detection data payload
        detection_data = {
            'id': hil_event.id,
            'timestamp': hil_event.unix_timestamp,
            'video_relative_timestamp': hil_event.video_relative_timestamp,
            'sequence_timestamp': hil_event.sequence_timestamp,
            'latency_ms': hil_event.actual_latency_ms,
            'voltage': hil_event.labjack_voltage,
            'channel': hil_event.detection_channel,
            'video_id': hil_event.video_id,
            'sequence_id': hil_event.sequence_id,
            'video_play_offset_ms': hil_event.video_play_offset_ms
        }

        # Emit to session-specific room
        from services.websocket_rooms import notify_session_room
        success = notify_session_room(session_id, 'detection_event', detection_data)

        if success:
            logger.info(f"📡 Emitted detection event: {hil_event.id}")
        else:
            logger.error(f"❌ Failed to emit detection event")
    except Exception as e:
        logger.error(f"Failed to emit detection event: {e}")
```

**Critical Questions:**
1. Are `video_relative_timestamp` and `sequence_timestamp` calculated correctly?
2. Is `notify_session_room()` functioning properly?
3. Are any fields NULL that would cause filtering?

---

### 5. Socket.IO Emission Function

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py`

**Lines 522-569:** Core emission function

```python
async def emit_detection_event(detection_data: dict, test_session_id: str):
    """Emit real-time detection event to all connected clients"""
    try:
        # CRITICAL: Validate timestamp field
        if 'timestamp' not in detection_data:
            logger.warning(f"⚠️ Detection event missing timestamp")
            detection_data['timestamp'] = datetime.now().isoformat()

        # Emit to test session room
        room = f"session_{test_session_id}"
        await sio.emit('detection_event', detection_data, room=room)

        logger.debug(f"Emitted detection event to room {room}")
    except Exception as e:
        logger.error(f"❌ Failed to emit detection event: {str(e)}")
```

**Validation Checks:**
1. Is `timestamp` field present and properly formatted?
2. Does the room name match subscription (`session_` vs `test_session_`)?
3. Are there any silent failures in the emission?

---

## Critical Issues Identified

### Issue #1: Sequence Start Time Not Initialized

**Evidence:** Frontend logs show `⚠️ [HIL WebSocket] No sequence start time available`

**Location:** Video sequence orchestrator initialization

**Impact:**
- Detection events cannot calculate `sequence_timestamp`
- `video_relative_timestamp` may be incorrect
- Events may be filtered out or delayed

**Root Cause Hypotheses:**

1. **Video Lifecycle Event Not Received**
   ```python
   # socketio_server.py:851
   async def video_started(sid, data):
       # CRITICAL: This triggers notify_video_started()
       # If this is not called, sequence_start_time remains NULL
   ```

2. **Race Condition**
   - Detections arrive BEFORE `video_started` event
   - `sequence_start_time` is still NULL when enrichment happens
   - Events are created but missing critical timing fields

3. **Database Transaction Not Committed**
   ```python
   # video_sequence_orchestrator.py:325
   video_sequence_db.sequence_start_time = actual_start_timestamp
   db.commit()  # ⚠️ Could this fail silently?
   ```

---

### Issue #2: Room Naming Mismatch

**Subscription Room:** `test_session_{session_id}`
**Emission Room:** `session_{session_id}` (in some code paths)

**Location:** Multiple files have inconsistent naming

**Evidence:**
```python
# socketio_server.py:558 - USES session_ prefix
room = f"session_{test_session_id}"

# socketio_server.py:309 - USES test_session_ prefix
room_name = f"test_session_{session_id}"
```

**Impact:** Events emitted to wrong room won't reach subscribed clients

---

### Issue #3: Timestamp Validation Failures

**Location:** `socketio_server.py:530-546`

**Logic:**
```python
if 'timestamp' not in detection_data:
    logger.warning(f"⚠️ Detection event missing timestamp")
    detection_data['timestamp'] = datetime.now().isoformat()
elif not isinstance(detection_data['timestamp'], str):
    # Convert non-string timestamps to ISO format
    ts = detection_data['timestamp']
    if hasattr(ts, 'isoformat'):
        detection_data['timestamp'] = ts.isoformat()
```

**Potential Issue:** Numeric timestamps (Unix epoch) might trigger unnecessary conversions

---

## Configuration Gaps

### Missing Initialization Steps

1. **VideoTestSequence.sequence_start_time** - Not set on sequence creation
   ```python
   # Should be initialized when sequence is created
   sequence = VideoTestSequence(
       id=sequence_id,
       test_session_id=session_id,
       sequence_start_time=None,  # ❌ Should be set immediately
       status="pending"
   )
   ```

2. **Frontend Video Lifecycle Events** - May not be emitting properly
   ```typescript
   // Frontend should emit video_started with:
   socket.emit('video_started', {
       sessionId: session_id,
       videoId: video_id,
       sequenceId: sequence_id,
       videoStartTime: performance.now() / 1000,
       sequenceElapsedTime: elapsed_time_since_sequence_start
   });
   ```

3. **Detection Enrichment** - Missing fallback logic
   ```python
   # If sequence_start_time is NULL, should we:
   # A) Drop the detection?
   # B) Store it and backfill later?
   # C) Estimate based on first detection?
   ```

---

## Recommended Fixes

### Fix #1: Initialize sequence_start_time on Sequence Creation

**File:** `video_sequence_orchestrator.py` or sequence creation endpoint

```python
# When creating VideoTestSequence:
sequence_start_time = time.time()  # Use actual system time

video_sequence = VideoTestSequence(
    id=sequence_id,
    test_session_id=session_id,
    sequence_start_time=sequence_start_time,  # ✅ Set immediately
    status="pending"
)
db.add(video_sequence)
db.commit()
```

**Rationale:** Ensures `sequence_start_time` is available BEFORE any detections arrive

---

### Fix #2: Standardize Room Naming

**Apply consistently across all files:**

```python
# Standard: Use "session_" prefix everywhere
DETECTION_ROOM_PATTERN = "session_{session_id}"

# socketio_server.py
room = f"session_{test_session_id}"

# websocket_rooms.py
room = f"session_{session_id}"

# dedicated_labjack_monitor.py
# Uses notify_session_room() which should use "session_" prefix
```

---

### Fix #3: Add Detection Buffering for Early Arrivals

**File:** `video_sequence_orchestrator.py`

```python
class VideoSequenceOrchestrator:
    def __init__(self):
        self.pending_detections: Dict[str, List[HILDetectionEvent]] = {}

    def enrich_detection_with_timing(self, detection, session_id):
        sequence = self.active_sequences.get(detection.sequence_id)

        if sequence and sequence.sequence_start_time is None:
            # Buffer detection until sequence_start_time is set
            if detection.sequence_id not in self.pending_detections:
                self.pending_detections[detection.sequence_id] = []

            self.pending_detections[detection.sequence_id].append(detection)
            logger.info(f"⏳ Buffered detection (waiting for sequence_start_time)")
            return False  # Don't emit yet

        # Process normally with sequence_start_time available
        # ... existing enrichment logic ...

    def notify_video_started(self, sequence_id, ...):
        # ... existing initialization logic ...

        # After setting sequence_start_time, process buffered detections
        if sequence_id in self.pending_detections:
            buffered = self.pending_detections.pop(sequence_id)
            logger.info(f"⚡ Processing {len(buffered)} buffered detections")

            for detection in buffered:
                self.enrich_detection_with_timing(detection, session_id)
                # Emit buffered detection
```

---

### Fix #4: Add Diagnostic Logging

**File:** `dedicated_labjack_monitor.py`

```python
def _emit_detection_event_sync(self, hil_event: HILDetectionEvent, session_id: str):
    """Enhanced logging for debugging"""

    # Log detection state
    logger.info(f"""
    📡 Detection Event Emission:
       Event ID: {hil_event.id}
       Session: {session_id}
       Timestamp: {hil_event.unix_timestamp}
       Sequence Timestamp: {hil_event.sequence_timestamp}
       Video Rel Timestamp: {hil_event.video_relative_timestamp}
       Video ID: {hil_event.video_id}
       Sequence ID: {hil_event.sequence_id}
       Voltage: {hil_event.labjack_voltage}
       Channel: {hil_event.detection_channel}
       Timing Quality: {hil_event.timing_sync_quality}
    """)

    # ... existing emission logic ...

    # Log emission result
    if success:
        logger.info(f"✅ Successfully emitted detection {hil_event.id} to session_{session_id}")
    else:
        logger.error(f"❌ Failed to emit detection {hil_event.id}")
        logger.error(f"   Room: session_{session_id}")
        logger.error(f"   Detection Data: {json.dumps(detection_data, indent=2)}")
```

---

## Testing Recommendations

### Test #1: Verify Sequence Start Time Initialization

```python
# Test: Ensure sequence_start_time is set on video playback
def test_sequence_start_time_initialization():
    # 1. Create test session and sequence
    session_id = create_test_session()
    sequence_id = create_video_sequence(session_id)

    # 2. Emit video_started event
    socket.emit('video_started', {
        'sessionId': session_id,
        'videoId': video_id,
        'sequenceId': sequence_id,
        'videoStartTime': time.time(),
        'sequenceElapsedTime': 0.0
    })

    # 3. Verify sequence_start_time is set in database
    sequence = db.query(VideoTestSequence).filter_by(id=sequence_id).first()
    assert sequence.sequence_start_time is not None, "sequence_start_time not initialized"
    assert sequence.sequence_start_time > 0, "sequence_start_time invalid"
```

---

### Test #2: Verify WebSocket Room Subscription

```python
# Test: Ensure client joins correct room and receives events
async def test_websocket_detection_emission():
    # 1. Subscribe to detections
    socket.emit('subscribe_detections', {'session_id': session_id})

    # 2. Wait for subscription confirmation
    confirmation = await wait_for_event('detection_subscription_confirmed')
    assert confirmation['session_id'] == session_id

    # 3. Trigger a detection (simulate LabJack event)
    labjack_service.trigger_detection(session_id, voltage=3.3, channel="AIN0")

    # 4. Verify detection event received on client
    detection = await wait_for_event('detection_event', timeout=5.0)
    assert detection is not None, "Detection event not received"
    assert detection['session_id'] == session_id
    assert detection['voltage'] == 3.3
    assert detection['channel'] == "AIN0"
```

---

### Test #3: Verify Detection Timestamp Enrichment

```python
# Test: Ensure sequence_timestamp is calculated correctly
def test_detection_timestamp_enrichment():
    # 1. Set sequence_start_time
    sequence_start_time = time.time()

    # 2. Create detection 5 seconds later
    detection_time = sequence_start_time + 5.0

    # 3. Enrich detection with timing
    detection = HILDetectionEvent(
        unix_timestamp=detection_time,
        session_id=session_id,
        sequence_id=sequence_id
    )

    orchestrator.enrich_detection_with_timing(detection, session_id)

    # 4. Verify sequence_timestamp is correct
    assert detection.sequence_timestamp == 5.0, \
        f"Expected 5.0s, got {detection.sequence_timestamp}s"
```

---

## Files to Review

### Priority 1 (Critical Path)

1. `/backend/socketio_server.py` (Lines 286-333, 522-569)
   - WebSocket route handlers
   - Detection emission function

2. `/backend/services/video_sequence_orchestrator.py` (Lines 143, 315-347)
   - Sequence start time initialization
   - Video lifecycle event handling

3. `/backend/services/dedicated_labjack_monitor.py` (Lines 809-860)
   - Detection event emission
   - WebSocket integration

### Priority 2 (Context & Support)

4. `/backend/services/websocket_rooms.py`
   - Room-based emission utilities

5. `/backend/models.py` (Lines 328-427)
   - DetectionEvent schema

6. `/backend/schemas.py` (Lines 695-696)
   - Sequence timing schema definitions

### Priority 3 (Frontend Integration)

7. `/frontend/src/services/websocketService.ts`
   - Client-side WebSocket connection

8. `/frontend/src/pages/HILTestExecutionPRD.tsx`
   - Video lifecycle event emission
   - Detection event handling

---

## Specific Line Numbers for Investigation

### socketio_server.py

- **Line 309:** `room_name = f"test_session_{session_id}"` - Subscription room
- **Line 558:** `room = f"session_{test_session_id}"` - Emission room (MISMATCH?)
- **Line 530:** Timestamp validation logic
- **Line 851:** `video_started` event handler

### video_sequence_orchestrator.py

- **Line 143:** `sequence_start_time: Optional[float] = None` - Initial state
- **Line 315:** `if sequence.sequence_start_time is None:` - Initialization check
- **Line 325:** `video_sequence_db.sequence_start_time = actual_start_timestamp` - Database update
- **Line 327:** Database commit

### dedicated_labjack_monitor.py

- **Line 822:** `_emit_detection_event_sync` method definition
- **Line 826:** Detection payload construction
- **Line 850:** `notify_session_room` call
- **Line 853:** Success/failure logging

---

## Summary of Findings

### ✅ Working Components

1. **WebSocket Connection:** Frontend successfully connects and subscribes
2. **LabJack Hardware:** Device connected and generating voltage triggers
3. **Ground Truth Loading:** 242 events loaded correctly
4. **Database Schema:** All required fields present in `detection_events` table

### ❌ Problematic Areas

1. **Sequence Start Time:** Not initialized when video playback begins
2. **Room Naming:** Inconsistent use of `session_` vs `test_session_` prefix
3. **Timing Enrichment:** Race condition if detections arrive before initialization
4. **Error Handling:** Silent failures in WebSocket emission

### ⚠️ High-Risk Code Paths

1. **video_sequence_orchestrator.py:315-347** - CAS logic for `sequence_start_time`
2. **socketio_server.py:851-1027** - `video_started` event handler
3. **dedicated_labjack_monitor.py:822-860** - Detection emission

---

## Next Steps

1. **Immediate:** Add diagnostic logging to track `sequence_start_time` initialization
2. **Short-term:** Implement detection buffering for early arrivals
3. **Medium-term:** Standardize room naming across all components
4. **Long-term:** Add comprehensive integration tests for detection streaming

---

## Contact

For questions about this analysis, contact the HIL Testing Architecture Team.

**Document Version:** 1.0
**Last Updated:** 2025-01-17
**Analysis Scope:** Detection Event Streaming Architecture
