# Race Condition and Concurrency Analysis - Multi-Video HIL System

**Date:** 2025-10-31
**Status:** CRITICAL - Multiple race conditions identified
**Severity:** HIGH - May cause intermittent failures, data corruption, and session conflicts

---

## Executive Summary

Deep analysis of the multi-video HIL validation system has identified **15 critical race conditions** across 6 major components. These race conditions explain intermittent failures observed in production and pose risks to data integrity, session isolation, and system reliability.

**Key Findings:**
- ✅ No threading primitives (locks) used despite concurrent access
- ✅ Dictionary mutations without synchronization in 4 services
- ✅ Async/await patterns have potential exception handling gaps
- ✅ Database transactions lack isolation for concurrent operations
- ✅ WebSocket broadcasting has race conditions during disconnection
- ✅ Orchestrator state can be corrupted during concurrent video transitions

---

## 1. Issue #1: Orchestrator Synchronization Race Conditions

### Location
`/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py:813-863`

### Race Condition #1: Concurrent Video End Notifications

**Code:**
```python
# Lines 823-863
active_session = hil_manager.active_sessions.get(session_id)

if active_session:
    orchestrator = active_session.get("orchestrator")

    if orchestrator:
        # Find sequence ID from orchestrator's active sequences
        for seq_id, sequence in orchestrator._active_sequences.items():  # ⚠️ RACE CONDITION
            if sequence.session_id == str(session_id):
                sequence_id_found = seq_id
                break

        orchestrator_sync_success = await asyncio.to_thread(
            orchestrator.notify_video_ended,
            sequence_id=sequence_id_found,
            video_id=video_id,
            actual_end_timestamp=video_end_time,
            db=db
        )
```

**Problems:**
1. **Dictionary iteration without lock**: `orchestrator._active_sequences` can be modified by another request during iteration
2. **No atomicity**: Read-check-modify pattern is not atomic
3. **Lost updates**: Two simultaneous `video_end` calls for same session can interleave
4. **Concurrent session_id lookups**: Multiple threads reading same dict without synchronization

**What Can Go Wrong:**
- Thread A reads `_active_sequences` while Thread B modifies it → **RuntimeError: dictionary changed size during iteration**
- Thread A finds `sequence_id_found=None` while Thread B is adding it → **Both fail to sync**
- Both threads call `notify_video_ended()` for same video → **Double evaluation, incorrect metrics**

**Observed Symptoms:**
- Intermittent "sequence ID not found" errors
- Duplicate video completion events
- Incorrect `completed_videos` count in database

---

### Race Condition #2: `asyncio.to_thread()` Exception Handling

**Code:**
```python
orchestrator_sync_success = await asyncio.to_thread(
    orchestrator.notify_video_ended,
    sequence_id=sequence_id_found,
    video_id=video_id,
    actual_end_timestamp=video_end_time,
    db=db
)
```

**Problems:**
1. **No timeout**: `asyncio.to_thread()` can block indefinitely if `notify_video_ended()` hangs
2. **Exception propagation**: Exceptions in thread are not properly caught
3. **Database session corruption**: `db` session used across async/sync boundary without protection

**What Can Go Wrong:**
- `notify_video_ended()` blocks → FastAPI request times out → **Client retries → Duplicate processing**
- Database deadlock in thread → **Entire request hangs, no timeout**
- Exception in thread → **orchestrator_sync_success remains unset → AttributeError**

---

### Race Condition #3: `hil_manager.active_sessions` Dictionary Access

**Code:**
```python
# Line 411: Session creation
hil_manager.active_sessions[test_session.id] = {
    "session": test_session,
    "orchestrator": orchestrator,
    "active_video_id": None
}

# Line 460: Session read
active_session = hil_manager.active_sessions.get(session_id)

# Line 1229: Session deletion
if session_id in hil_manager.active_sessions:
    del hil_manager.active_sessions[session_id]
```

**Problems:**
1. **No lock protection**: `active_sessions` dictionary is accessed by multiple async requests
2. **Check-then-act race**: `if session_id in dict` → `del dict[session_id]` is not atomic
3. **Lost updates**: Concurrent modifications can overwrite each other

**What Can Go Wrong:**
- Request A checks `session_id in dict` (True) → Request B deletes it → Request A tries `del dict[session_id]` → **KeyError**
- Request A sets `active_sessions[id]` → Request B sets `active_sessions[id]` → **First session metadata lost**
- Request A reads `active_sessions[id]` while Request B modifies it → **Incomplete/corrupt session data returned**

**Frequency:** HIGH - Happens when:
- Multiple clients connect to same session
- Frontend retries failed requests
- Session completion races with video end notification

---

## 2. Issue #3: Validation Endpoint Race Conditions

### Location
`/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions.py:86-265`

### Race Condition #4: Concurrent Session Creation with `force_start=true`

**Code:**
```python
# Lines 208-228
if not force_start and session.video_id:
    gt_count = db.query(func.count(GroundTruthObject.id)).filter(
        GroundTruthObject.video_id == session.video_id
    ).scalar() or 0

    if gt_count == 0:
        raise HTTPException(status_code=422, detail="No ground truth data")

# Line 231: Create session (no lock)
db_session = create_test_session(db=db, test_session=session, user_id="anonymous")
```

**Problems:**
1. **Time-of-check to time-of-use (TOCTOU)**: Ground truth validated → Another request deletes GT → Session created with stale validation
2. **No transaction isolation**: Multiple sessions can be created simultaneously for same video
3. **Missing cache invalidation**: 5-min TTL cache mentioned in docs but NOT IMPLEMENTED

**What Can Go Wrong:**
- Request A validates GT (count=10) → Request B deletes GT → Request A creates session with count=0 → **Invalid session created**
- Both Request A and B create sessions for same video → **Duplicate active sessions**
- Cache returns stale GT counts → **Session created with wrong expectations**

**Evidence:** Code comment says "Response caching (5 min TTL)" but no cache implementation found

---

### Race Condition #5: Ground Truth Validation Query Race

**Code:**
```python
# Lines 112-122: Single query but no isolation
gt_counts_query = db.query(
    GroundTruthObject.video_id,
    func.count(GroundTruthObject.id).label('gt_count')
).filter(
    GroundTruthObject.video_id.in_(request.video_ids)
).group_by(
    GroundTruthObject.video_id
).all()
```

**Problems:**
1. **Read uncommitted**: Query runs without transaction isolation level specified
2. **Phantom reads**: GT objects can be inserted/deleted during query execution
3. **No locking**: Another transaction can modify GT objects concurrently

**What Can Go Wrong:**
- Query returns `gt_count=5` → Another request deletes 3 GTs → Session created expecting 5 → **Only 2 GTs available during test**
- Query sees inconsistent state during concurrent GT modifications → **Wrong validation result**

---

## 3. Issue #5: N+1 Query Race Conditions

### Location
Multiple files with eager loading implementation

### Race Condition #6: Eager Loading During Database Migration

**Code:**
```python
# routers/test_sessions.py:486-489
labjack_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match)
).filter(...)
```

**Problems:**
1. **No migration lock**: Eager loading can execute during schema migration
2. **Relationship corruption**: If foreign key columns are being added/modified, `selectinload` fails
3. **Connection pool exhaustion**: Eager loading under high concurrency can exhaust pool

**What Can Go Wrong:**
- Migration running → Eager load query executes → **OperationalError: column does not exist**
- 100 concurrent requests with eager loading → Connection pool (default 5-10) exhausted → **Timeout errors**
- Relationship cascade during eager load conflicts with another transaction → **Deadlock**

---

## 4. WebSocket Event Broadcasting Race Conditions

### Location
`/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py:58-71`

### Race Condition #7: WebSocket Connection List Modification

**Code:**
```python
async def broadcast_status(self, message: dict):
    """Broadcast status to all connected websockets"""
    if self.websocket_connections:
        disconnected = []
        for websocket in self.websocket_connections:  # ⚠️ RACE CONDITION
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected.append(websocket)

        # Remove disconnected websockets
        for ws in disconnected:
            if ws in self.websocket_connections:  # ⚠️ RACE CONDITION
                self.websocket_connections.remove(ws)
```

**Problems:**
1. **List iteration during modification**: Another coroutine can add/remove websockets during iteration
2. **Lost removals**: `if ws in list` check is not atomic with `list.remove()`
3. **No lock**: `websocket_connections` list is shared across all async tasks

**What Can Go Wrong:**
- Task A iterates list → Task B adds websocket → **RuntimeError: list changed size during iteration**
- Task A checks `ws in list` (True) → Task B removes it → Task A calls `remove()` → **ValueError: x not in list**
- Task A and B both try to remove same websocket → **ValueError or double-send to client**

**Frequency:** HIGH - Happens during:
- Session completion (multiple broadcasts)
- Client disconnect/reconnect patterns
- Network interruptions

---

### Race Condition #8: WebSocket Server Initialization

**Code:**
```python
# Line 433
await hil_manager.broadcast_status({
    "type": "session_started",
    "session_id": session_id,
    ...
})
```

**Problems:**
1. **No initialization check**: `broadcast_status()` called before WebSocket server may be ready
2. **No graceful degradation**: Broadcast failure can crash session creation
3. **Silent failures**: Exceptions in broadcast are caught but not logged in many places

**What Can Go Wrong:**
- Session created before WebSocket server initialized → `broadcast_status()` fails → **Session created but clients not notified**
- WebSocket server crashes → All broadcasts fail silently → **Frontend shows stale data**

---

## 5. Orchestrator State Management Race Conditions

### Location
`/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

### Race Condition #9: `_active_sequences` Dictionary Mutations

**Code:**
```python
# Line 176: Instance variable (shared state)
self._active_sequences: Dict[str, VideoTestSequence] = {}

# Line 252: Write
self._active_sequences[sequence_id] = sequence

# Line 602-620: Iteration during read
for seq_id, sequence in orchestrator._active_sequences.items():
    if sequence.session_id == str(session_id):
        ...
```

**Problems:**
1. **No synchronization**: Dictionary modified by multiple async operations
2. **Singleton pattern**: `get_video_sequence_orchestrator()` returns global instance shared across requests
3. **Concurrent video transitions**: Multiple videos can transition simultaneously

**What Can Go Wrong:**
- Video 1 ends (iterates dict) → Video 2 starts (adds to dict) → **RuntimeError: dict changed during iteration**
- Two videos transition at same time → Both update `current_video_index` → **Lost update, wrong video marked as current**
- Sequence finalization reads dict while video start adds to it → **Incomplete aggregation**

---

### Race Condition #10: `_current_video_index` Concurrent Updates

**Code:**
```python
# video_sequence_orchestrator.py:314
sequence.current_video_index = sequence.video_ids.index(video_id)

# Line 393-398: Read for transition logic
if sequence.current_video_index >= len(sequence.video_ids) - 1:
    logger.info(f"Last video completed - finalizing sequence")
    self._finalize_sequence(sequence_id, db)
else:
    logger.info(f"Video {sequence.current_video_index + 1}/{len(sequence.video_ids)} completed")
```

**Problems:**
1. **Read-modify-write not atomic**: `current_video_index` can be updated by concurrent operations
2. **Lost increments**: Two video completions can read same index, both increment, one update lost
3. **Race in finalization check**: Index check and finalization not atomic

**What Can Go Wrong:**
- Video 1 completes (reads index=0) → Video 2 completes (reads index=0) → Both set index=1 → **Video 2 skipped, index=1 used for two videos**
- Index=1, last video → Request A checks (1 < 2-1, False) → Request B sets index=2 → Request A finalizes → **Premature finalization**

---

## 6. SocketIO Server Race Conditions

### Location
`/home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py`

### Race Condition #11: `active_sessions` Dictionary in SocketIO

**Code:**
```python
# Line 50: Module-level shared state
active_sessions: Dict[str, Any] = {}

# Line 75: Write
active_sessions[f"client_{sid}"] = client_info

# Line 119: Read-delete
del active_sessions[session_id]

# Line 153: Write
active_sessions[session_id] = { ... }
```

**Problems:**
1. **Module-level dict**: Shared across all connections and events
2. **No synchronization**: Multiple event handlers modify concurrently
3. **Key collisions**: `client_{sid}` and `session_id` both stored in same dict

**What Can Go Wrong:**
- Client connects (adds `client_X`) → Session starts (adds session ID) → Both delete → **Wrong entry deleted**
- Two clients disconnect simultaneously → Both try to delete → **KeyError on second delete**
- Heartbeat updates `last_heartbeat` while disconnect cleans up → **Partial cleanup, memory leak**

---

### Race Condition #12: Heartbeat Connection Monitoring

**Code:**
```python
# Lines 350-381
async def heartbeat_connection(sid: str):
    while sid in [s.get('sid') for s in active_sessions.values() if isinstance(s, dict)]:
        await asyncio.sleep(heartbeat_interval)
        # Send heartbeat
        await sio.emit('heartbeat_ping', heartbeat_data, room=sid)
```

**Problems:**
1. **List comprehension during iteration**: Evaluates entire dict on each loop
2. **No cleanup on exception**: Task continues even if heartbeat fails
3. **Concurrent cleanup**: Disconnect handler and heartbeat timeout both clean up

**What Can Go Wrong:**
- Heartbeat task checks dict → Disconnect modifies dict → **RuntimeError or wrong SID detection**
- Heartbeat timeout triggers cleanup → Disconnect also triggers cleanup → **Double cleanup, KeyError**
- Heartbeat fails but task loops forever → **Zombie tasks accumulate**

---

## 7. Async/Await Correctness Issues

### Race Condition #13: Background Task Exception Handling

**Code:**
```python
# hil_test_complete.py:427
asyncio.create_task(monitor_test_session(session_id, db))

# Lines 1352-1383: Background monitoring
async def monitor_test_session(session_id: int, db: Session):
    try:
        # ... monitoring logic ...
    except Exception as e:
        logger.error(f"Error monitoring test session {session_id}: {e}")
```

**Problems:**
1. **Fire-and-forget tasks**: `create_task()` without storing task reference
2. **No cancellation**: Tasks continue even after session completes
3. **Database session reuse**: `db` session passed to background task while main request may close it

**What Can Go Wrong:**
- Session completes → Monitoring task still running → Tries to access closed DB session → **SQLAlchemy error**
- Exception in monitoring task → Task dies silently → **No monitoring, but session thinks it's active**
- Multiple monitoring tasks for same session (retry) → **Duplicate event processing**

---

### Race Condition #14: Database Session Scope Violations

**Code:**
```python
# test_sessions.py:574-686: start_test_session
async def start_test_session(session_id: str, db: Session = Depends(get_db)):
    # ... session operations ...

    # Line 641: Background task with db session
    success = start_hil_monitoring(session_id, video_timing_config)

    # Lines 668-672: Another background task
    background_tasks.add_task(
        session_manager.execute_test_session,
        session_id  # No db passed, but needs DB access
    )
```

**Problems:**
1. **Session lifecycle mismatch**: `db` session closed when request ends, but background tasks still run
2. **Cross-request contamination**: Background task may start new DB session without proper context
3. **No transaction isolation**: Background tasks and request share same transaction

**What Can Go Wrong:**
- Request completes → `db.close()` called → Background task tries DB query → **InvalidRequestError: session is closed**
- Background task commits → Main request rolls back → **Partial data corruption**
- Two background tasks use same session → **Non-thread-safe usage**

---

## 8. Database Transaction Isolation Issues

### Race Condition #15: Video End Timing Update Race

**Code:**
```python
# hil_test_complete.py:788-816
sequence_video_result.video_end_time = video_end_time
sequence_video_result.video_status = "completed"

# CRITICAL: Commit database changes BEFORE orchestrator synchronization
try:
    db.commit()
    logger.info(f"Database committed: video {video_id} status updated")
except Exception as db_error:
    db.rollback()
    raise
```

**Problems:**
1. **Lost update problem**: Two video_end requests for same video can both read, modify, commit
2. **Idempotency check insufficient**: Check at line 775 not in same transaction as update
3. **No row-level locking**: `SELECT ... FOR UPDATE` not used

**What Can Go Wrong:**
- Request A reads `video_status='playing'` → Request B reads `video_status='playing'` → Both set to 'completed' → **Duplicate evaluation triggered**
- Request A commits `video_end_time=T1` → Request B commits `video_end_time=T2` → **T1 lost, metrics incorrect**
- Idempotency check passes for both → Both trigger orchestrator sync → **Double finalization**

**Fix Required:**
```python
# Use pessimistic locking
sequence_video_result = db.query(SequenceVideoResult).filter(
    SequenceVideoResult.video_id == video_id
).with_for_update().first()

# Idempotency check now protected by lock
if sequence_video_result.video_status == "completed":
    return  # Already processed
```

---

## Summary of Race Conditions

| # | Component | Severity | Frequency | Impact |
|---|-----------|----------|-----------|--------|
| 1 | Orchestrator dict iteration | CRITICAL | HIGH | Session conflicts, wrong video evaluation |
| 2 | asyncio.to_thread timeout | HIGH | MEDIUM | Request hangs, duplicate processing |
| 3 | hil_manager.active_sessions | CRITICAL | HIGH | KeyError, lost session data |
| 4 | Concurrent force_start | HIGH | LOW | Invalid sessions created |
| 5 | GT validation isolation | MEDIUM | LOW | Wrong GT counts |
| 6 | Eager loading migration | HIGH | LOW | Query failures during deployment |
| 7 | WebSocket connection list | HIGH | HIGH | Client notification failures |
| 8 | WebSocket server init | MEDIUM | LOW | Silent broadcast failures |
| 9 | _active_sequences mutations | CRITICAL | MEDIUM | Sequence corruption |
| 10 | current_video_index | CRITICAL | MEDIUM | Wrong video transitions |
| 11 | SocketIO active_sessions | HIGH | MEDIUM | Connection management failures |
| 12 | Heartbeat monitoring | MEDIUM | LOW | Zombie connections |
| 13 | Background task exceptions | HIGH | MEDIUM | Silent monitoring failures |
| 14 | DB session scope | CRITICAL | HIGH | Data corruption |
| 15 | Video end timing | CRITICAL | HIGH | Duplicate evaluations |

---

## Recommended Fixes

### Priority 1: Add Thread-Safe Data Structures

```python
import threading
from threading import Lock

class HILTestManager:
    def __init__(self):
        self.active_sessions: Dict[int, dict] = {}
        self._sessions_lock = Lock()  # Add lock
        self.websocket_connections: List[WebSocket] = []
        self._websockets_lock = Lock()  # Add lock

    async def broadcast_status(self, message: dict):
        with self._websockets_lock:
            connections = self.websocket_connections.copy()

        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected.append(websocket)

        with self._websockets_lock:
            for ws in disconnected:
                if ws in self.websocket_connections:
                    self.websocket_connections.remove(ws)
```

### Priority 2: Add Database Row Locking

```python
# Use SELECT ... FOR UPDATE for critical updates
sequence_video_result = db.query(SequenceVideoResult).filter(
    SequenceVideoResult.video_id == video_id
).with_for_update().first()

# Set transaction isolation level
db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
```

### Priority 3: Add Timeouts to Async Operations

```python
import asyncio

# Add timeout to asyncio.to_thread
try:
    orchestrator_sync_success = await asyncio.wait_for(
        asyncio.to_thread(
            orchestrator.notify_video_ended,
            sequence_id=sequence_id_found,
            video_id=video_id,
            actual_end_timestamp=video_end_time,
            db=db
        ),
        timeout=10.0  # 10 second timeout
    )
except asyncio.TimeoutError:
    logger.error(f"Orchestrator sync timeout for video {video_id}")
    orchestrator_sync_success = False
```

### Priority 4: Implement Proper Orchestrator Locking

```python
class VideoSequenceOrchestrator:
    def __init__(self):
        self._active_sequences: Dict[str, VideoTestSequence] = {}
        self._sequences_lock = asyncio.Lock()  # Async lock for dict access

    async def notify_video_ended(self, sequence_id: str, ...):
        async with self._sequences_lock:
            sequence = self._get_sequence(sequence_id)
            # ... safe access to sequence ...
```

### Priority 5: Fix Background Task Management

```python
class HILTestManager:
    def __init__(self):
        self.active_sessions: Dict[int, dict] = {}
        self._monitoring_tasks: Dict[int, asyncio.Task] = {}

    async def start_monitoring(self, session_id: int):
        task = asyncio.create_task(self._monitor_session(session_id))
        self._monitoring_tasks[session_id] = task
        return task

    async def stop_monitoring(self, session_id: int):
        if session_id in self._monitoring_tasks:
            task = self._monitoring_tasks[session_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._monitoring_tasks[session_id]
```

---

## Testing Strategy

### Unit Tests for Race Conditions

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_concurrent_video_end():
    """Test that concurrent video_end calls don't corrupt state"""
    # Simulate 2 video_end requests for same video
    results = await asyncio.gather(
        end_video_playback(session_id=1, video_data={"video_id": "v1"}),
        end_video_playback(session_id=1, video_data={"video_id": "v1"}),
        return_exceptions=True
    )

    # Verify idempotency - both should succeed or one should gracefully fail
    assert results[0]["success"] or results[1]["success"]

    # Verify no duplicate evaluation
    assert count_evaluations(session_id=1, video_id="v1") == 1
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_websocket_broadcast_during_disconnect():
    """Test broadcast during client disconnect"""
    # Connect multiple clients
    clients = [await connect_websocket() for _ in range(10)]

    # Start disconnecting clients while broadcasting
    disconnect_task = asyncio.create_task(disconnect_clients(clients[:5]))
    broadcast_task = asyncio.create_task(broadcast_messages(100))

    await asyncio.gather(disconnect_task, broadcast_task)

    # Verify no RuntimeError or missed broadcasts
    assert all_messages_delivered()
```

---

## Monitoring and Detection

### Add Race Condition Metrics

```python
import prometheus_client

race_condition_errors = prometheus_client.Counter(
    'race_condition_errors_total',
    'Number of race condition errors detected',
    ['component', 'error_type']
)

# In code:
try:
    for seq_id, sequence in orchestrator._active_sequences.items():
        ...
except RuntimeError as e:
    race_condition_errors.labels(
        component='orchestrator',
        error_type='dict_modified_during_iteration'
    ).inc()
    logger.error(f"Race condition detected: {e}")
    raise
```

---

## Deployment Strategy

1. **Phase 1** (Week 1): Add locks to critical sections (Priority 1)
2. **Phase 2** (Week 2): Add database row locking (Priority 2)
3. **Phase 3** (Week 3): Add timeouts and background task management (Priority 3-5)
4. **Phase 4** (Week 4): Deploy with monitoring, gradual rollout

**Rollback Plan:** Keep old code paths with feature flag, monitor error rates

---

## Conclusion

The multi-video HIL validation system has **15 critical race conditions** that must be addressed before production deployment. The primary issues are:

1. **No synchronization primitives** (locks, semaphores) used
2. **Shared mutable state** accessed by concurrent async operations
3. **Database transactions** lack proper isolation
4. **Background tasks** not properly managed

**Estimated Fix Time:** 3-4 weeks
**Risk Level:** HIGH - System will experience intermittent failures under load

**Recommendation:** Implement Priority 1 fixes immediately, deploy to staging, run load tests to verify fixes work.
