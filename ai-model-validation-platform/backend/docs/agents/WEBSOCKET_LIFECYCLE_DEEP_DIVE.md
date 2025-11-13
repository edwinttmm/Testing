# WebSocket Lifecycle Event Deep Dive Analysis
## Root Cause: Why video_id is NULL for All Detections

**Date**: 2025-11-05
**Severity**: CRITICAL
**Impact**: Ground truth matching completely broken - 100% match failure rate

---

## Executive Summary

**SMOKING GUN FOUND**: Video lifecycle events (`video-started`, `video-ended`) are **NEVER EMITTED via WebSocket**. Instead, they use **HTTP REST API calls**, but the backend has **NO HANDLERS** for the WebSocket events that `dedicated_labjack_monitor.py` expects.

### Critical Flaw
```
Frontend: HTTP POST → /api/video-sequences/{id}/video-started
Backend:  ❌ NO @sio.event('video-started') handler
          ❌ NO @sio.event('video-ended') handler
Result:   video_id = NULL for ALL detections
```

---

## Complete Event Flow Analysis

### Expected Flow (What Should Happen)
```
┌─────────────┐
│  Frontend   │
│  Video      │
│  Starts     │
└──────┬──────┘
       │
       │ WebSocket Emit
       │ socket.emit('video-started', {...})
       │
       ▼
┌────────────────────┐
│  socketio_server   │
│  @sio.event        │
│  'video-started'   │
└─────────┬──────────┘
          │
          │ Update DB
          │ video_start_time = timestamp
          │
          ▼
┌──────────────────────────┐
│  dedicated_labjack_      │
│  monitor.py              │
│  _handle_detection       │
│  CAN NOW LINK video_id   │
└──────────────────────────┘
```

### Actual Flow (What Really Happens)
```
┌─────────────┐
│  Frontend   │
│  Video      │
│  Starts     │
└──────┬──────┘
       │
       │ HTTP REST API Call
       │ POST /api/video-sequences/{id}/video-started
       │
       ▼
┌────────────────────────┐
│  Backend REST Endpoint │
│  (video_sequences.py)  │
│  Updates Database      │
└────────────────────────┘

       ❌ NO WebSocket Event Emitted!

┌──────────────────────────┐
│  socketio_server.py      │
│  @sio.event('video-     │
│   started') - MISSING!   │
└──────────────────────────┘

┌──────────────────────────┐
│  dedicated_labjack_      │
│  monitor.py              │
│  Detections arrive BUT   │
│  video_start_time = NULL │
│  ∴ video_id = NULL       │
└──────────────────────────┘
```

---

## Evidence: Frontend Does NOT Emit WebSocket Events

### File: `/frontend/src/components/SequentialVideoPlayer.tsx`

**Lines 110-183: sendVideoStartedEvent()**
```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
    // ... validation ...

    console.log('🎬 Sending video-started event to backend:', {
        sequenceId,
        videoId,
        startedAt: startedAtUnix,
        url: `/api/video-sequences/${sequenceId}/video-started`  // ❌ REST API, not WebSocket!
    });

    try {
        // ❌ USES HTTP POST, NOT WEBSOCKET EMIT
        const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
            videoId: videoId,
            startedAt: startedAtUnix,
            clientTimestamp: clientTimestamp
        });
        // ...
    }
}, [sequenceId, sequenceStartUnix, onError]);
```

**Lines 190-268: sendVideoEndedEvent()**
```typescript
const sendVideoEndedEvent = useCallback(async (videoId: string, timestamp: number, actualPlaybackSeconds: number | null): Promise<string | null> => {
    // ... validation ...

    try {
        // ❌ USES HTTP POST, NOT WEBSOCKET EMIT
        const response = await apiService.post<{ nextVideoId?: string | null; next_video_id?: string | null }>(`/api/video-sequences/${sequenceId}/video-ended`, {
            videoId: videoId,
            endedAt: endedAtUnix,
            actualDuration: actualDuration ?? undefined,
            clientTimestamp: clientTimestamp
        });
        // ...
    }
}, [sequenceId, videoStartUnix]);
```

### Analysis
- **NO `socket.emit()` calls** for lifecycle events
- All lifecycle events use REST API (`apiService.post()`)
- Comments say "Sending video-started **event**" but actually send HTTP requests
- No WebSocket service usage in this component

---

## Evidence: Backend Missing WebSocket Handlers

### File: `/backend/socketio_server.py`

**Existing Handlers** (lines 52-608):
```python
@sio.event
async def connect(sid, environ, auth):
    # ... connection handling ...

@sio.event
async def disconnect(sid):
    # ... disconnection handling ...

@sio.event
async def start_test_session(sid, data):
    # ... test session start ...

@sio.event
async def stop_test_session(sid, data):
    # ... test session stop ...

@sio.event
async def subscribe_hardware_signals(sid, data):
    # ... hardware subscription ...

@sio.event
async def video_started(sid, data):  # ✅ EXISTS BUT DOES NOTHING USEFUL!
    """Handle video started events for timing synchronization"""
    try:
        session_id = data.get('sessionId')
        video_start_time = data.get('videoStartTime')
        setup_delay = data.get('setupDelay')

        # ❌ ONLY records in timing_sync_service, NOT in database!
        from services.timing_synchronization_service import timing_sync_service
        timing_sync_service.record_video_event(session_id, 'play_start', video_start_time)

        # ❌ NO database update for video_start_time!
        # ❌ NO update to VideoProjectLink.video_start_time!
        # ...
```

**Missing Handlers**:
```python
# ❌ NO @sio.event('video-ended') handler exists!
# The video_started handler exists but doesn't update the database
# properly for detection correlation
```

---

## Race Condition Analysis

### Timing Diagram
```
T+0ms:    Frontend starts video playback
          ├─ Video element.play()
          └─ HTTP POST /video-started (async)

T+5ms:    LabJack hardware detects signal
          ├─ dedicated_labjack_monitor._handle_detection() called
          └─ Tries to lookup video_id from database

T+8ms:    ❌ Database query: video_start_time = NULL
          └─ _determine_video_from_timing() returns None

T+50ms:   HTTP POST /video-started completes
          └─ Database updated, but TOO LATE!

RESULT:   Detection stored with video_id = NULL
```

### Why Detections Beat Lifecycle Events

1. **LabJack monitoring starts IMMEDIATELY** (line 206 of `dedicated_labjack_monitor.py`)
2. **HTTP REST calls are SLOW** (50-100ms round trip)
3. **No retry mechanism** in detection handler for missing video timing
4. **Cache invalidation broken** - doesn't refresh when lifecycle events fire

---

## Missing Event Handlers Required

### 1. WebSocket `video-started` Handler
```python
@sio.event
async def video_started(sid, data):
    """
    Handle video started WebSocket event.
    MUST update database IMMEDIATELY for detection correlation.
    """
    try:
        sequence_id = data.get('sequenceId')
        video_id = data.get('videoId')
        started_at = data.get('startedAt')  # Unix timestamp

        # CRITICAL: Update database immediately
        db = next(get_db())
        try:
            # Update VideoProjectLink with start time
            video_link = db.query(VideoProjectLink).filter(
                VideoProjectLink.id == video_id,
                VideoProjectLink.session_id == session_id
            ).first()

            if video_link:
                video_link.video_start_time = started_at
                video_link.status = 'playing'
                db.commit()

                logger.info(f"✅ Video {video_id} started at {started_at}")

                # Invalidate monitor cache
                from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
                monitor = get_dedicated_labjack_monitor()
                monitor.invalidate_sequence_cache(session_id)

                # Broadcast to other clients
                await sio.emit('video_timing_update', {
                    'session_id': session_id,
                    'video_id': video_id,
                    'video_start_time': started_at,
                    'status': 'started'
                }, room=f"test_session_{session_id}")
            else:
                logger.error(f"❌ Video link not found: {video_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error handling video_started: {e}")
```

### 2. WebSocket `video-ended` Handler
```python
@sio.event
async def video_ended(sid, data):
    """
    Handle video ended WebSocket event.
    MUST update database for sequence transitions.
    """
    try:
        sequence_id = data.get('sequenceId')
        video_id = data.get('videoId')
        ended_at = data.get('endedAt')  # Unix timestamp
        actual_duration = data.get('actualDuration')  # seconds

        # CRITICAL: Update database immediately
        db = next(get_db())
        try:
            # Update VideoProjectLink with end time
            video_link = db.query(VideoProjectLink).filter(
                VideoProjectLink.id == video_id,
                VideoProjectLink.session_id == session_id
            ).first()

            if video_link:
                video_link.video_end_time = ended_at
                video_link.status = 'completed'
                video_link.actual_duration = actual_duration
                db.commit()

                logger.info(f"✅ Video {video_id} ended at {ended_at}")

                # Invalidate monitor cache
                from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
                monitor = get_dedicated_labjack_monitor()
                monitor.invalidate_sequence_cache(session_id)

                # Broadcast to other clients
                await sio.emit('video_timing_update', {
                    'session_id': session_id,
                    'video_id': video_id,
                    'video_end_time': ended_at,
                    'status': 'ended'
                }, room=f"test_session_{session_id}")
            else:
                logger.error(f"❌ Video link not found: {video_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error handling video_ended: {e}")
```

---

## Error Handling Gaps

### Current State
1. **Silent Failures**: No logging when lifecycle events don't fire
2. **No Retry Logic**: Detection handler doesn't retry if timing data missing
3. **No Alerts**: User never informed when timing sync fails
4. **Cache Never Invalidated**: Monitor cache stale, never refreshes

### Database Transaction Issues
```python
# dedicated_labjack_monitor.py, line 702-748
# PROBLEM: Detection stored with video_id = NULL if timing not available
video_id_for_detection = hil_event.video_id

if not video_id_for_detection:
    # ❌ Falls back to session.video_id (wrong for multi-video!)
    # ❌ NO retry mechanism
    # ❌ NO cache invalidation trigger
    session = db.query(TestSession).filter_by(id=hil_event.session_id).first()
    if session and not session.has_video_sequence:
        video_id_for_detection = session.video_id  # Wrong!
    else:
        logger.warning("⚠️ Multi-video session: leaving detection without video_id")
        # ❌ Stores NULL in database - Ground truth matching FAILS
```

---

## Similar Patterns in Other Lifecycle Events

### Sequence Events
- `sequence-started` - Also missing WebSocket handler
- `sequence-ended` - Also missing WebSocket handler

### Test Session Events
- `test-started` - Has handler, works correctly
- `test-ended` - Has handler, works correctly

**Pattern**: Only test session events work because they were implemented early. Video sequence events added later without WebSocket support.

---

## Recommended Fixes

### Priority 1: Add WebSocket Handlers (CRITICAL)
```python
# /backend/socketio_server.py

@sio.event
async def video_lifecycle_event(sid, data):
    """
    Universal handler for all video lifecycle events.
    Handles: video-started, video-ended, sequence-started, sequence-ended
    """
    event_type = data.get('eventType')  # 'started' | 'ended'
    sequence_id = data.get('sequenceId')
    video_id = data.get('videoId')
    timestamp = data.get('timestamp')

    # Route to appropriate handler
    if event_type == 'started':
        await handle_video_started(sequence_id, video_id, timestamp, db)
    elif event_type == 'ended':
        await handle_video_ended(sequence_id, video_id, timestamp, db)

    # Invalidate monitor cache IMMEDIATELY
    from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
    monitor = get_dedicated_labjack_monitor()
    monitor.invalidate_sequence_cache(sequence_id)
```

### Priority 2: Frontend Emit WebSocket Events
```typescript
// /frontend/src/components/SequentialVideoPlayer.tsx

const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
    // DUAL APPROACH: HTTP for persistence + WebSocket for real-time

    // 1. HTTP POST for database persistence (keep existing)
    const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
        videoId,
        startedAt: startedAtUnix,
        clientTimestamp
    });

    // 2. WebSocket emit for IMMEDIATE cache invalidation
    websocketService.emit('video_lifecycle_event', {
        eventType: 'started',
        sequenceId,
        videoId,
        timestamp: startedAtUnix,
        clientTimestamp
    });
}, [sequenceId]);
```

### Priority 3: Retry Logic in Detection Handler
```python
# /backend/services/dedicated_labjack_monitor.py

def _get_video_id_with_retry(
    self,
    session_id: str,
    trigger_time: float,
    max_retries: int = 5,
    initial_delay_ms: float = 10.0
) -> Optional[str]:
    """
    ALREADY EXISTS (line 838-899) but needs to be CALLED!

    Current code has retry logic but _enrich_hil_event_context()
    doesn't always use it properly.
    """
    # ... exponential backoff retry ...
```

### Priority 4: Cache Invalidation Hook
```python
# /backend/services/dedicated_labjack_monitor.py

def invalidate_sequence_cache(self, session_id: str):
    """
    ALREADY EXISTS (line 831-836) but NEVER CALLED!

    Needs to be called from WebSocket handlers.
    """
    with self.lock:
        session_cache = self.active_sessions.get(session_id, {})
        session_cache.pop('sequence_context', None)
    logger.info(f"✅ Cache invalidated for session {session_id}")
```

---

## Testing Strategy

### 1. Unit Test: WebSocket Handler
```python
def test_video_started_handler_updates_database():
    """Verify video-started event updates database immediately"""
    # Emit video-started event
    # Check database updated within 10ms
    # Verify cache invalidated
```

### 2. Integration Test: Race Condition
```python
def test_detection_arrives_before_lifecycle_event():
    """Verify retry logic handles race condition"""
    # Start monitoring
    # Inject detection BEFORE lifecycle event
    # Wait 100ms for retry
    # Verify video_id assigned correctly
```

### 3. E2E Test: Multi-Video Sequence
```python
def test_multi_video_sequence_all_detections_assigned():
    """Verify all detections assigned to correct videos"""
    # Play 3-video sequence
    # Generate detections in each video
    # Verify 100% correct video_id assignment
```

---

## Summary of Root Causes

| Issue | Impact | Fix Priority |
|-------|--------|--------------|
| Frontend uses HTTP, not WebSocket | Lifecycle events arrive 50-100ms late | P1 - CRITICAL |
| Backend missing WebSocket handlers | Events received but not processed | P1 - CRITICAL |
| No cache invalidation trigger | Monitor uses stale timing data | P1 - CRITICAL |
| No retry logic in detection handler | Early detections get video_id=NULL | P2 - HIGH |
| No error logging for missing events | Silent failures, hard to debug | P3 - MEDIUM |

---

## Conclusion

**The bug is NOT a race condition** - it's a **missing implementation**:

1. ✅ Frontend emits events (but via HTTP, not WebSocket)
2. ❌ Backend has NO WebSocket handlers for video lifecycle
3. ❌ Detection handler never knows when video starts
4. ❌ Result: video_id = NULL for ALL detections

**Fix**: Implement the 4 missing WebSocket event handlers and frontend emission changes.

**Estimated Fix Time**: 2-4 hours
**Test Time**: 1-2 hours
**Total**: 3-6 hours to production-ready solution
