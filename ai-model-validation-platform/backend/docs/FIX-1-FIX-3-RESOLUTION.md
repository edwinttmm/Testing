# FIX-1 + FIX-3 Conflict Resolution

## Problem Summary

The original implementation had a critical race condition between:
- **FIX-1**: Signal `timing_ready_event` immediately after DB query
- **FIX-3**: Verify session exists in database

### The Conflict

```python
# ❌ BROKEN FLOW
1. Signal timing_ready_event.set() (FIX-1)
2. Try to verify session exists (FIX-3)
3. If verification fails, raise exception
4. Exception bypasses event signaling
5. But wait, we already signaled in step 1!
6. Confusion: Event says "ready" but timing actually failed
```

**Problem**: Should we signal BEFORE or AFTER verification?
- Signal BEFORE: Callback proceeds with bad data
- Signal AFTER: Callback waits 10s if verification fails

## Solution: State-Aware Event Signaling

### Key Insight

**The event should be signaled AFTER we know the state, but ALWAYS signaled to prevent deadlock.**

### Implementation

#### 1. Added MVCC Retry Helper

**File**: `/backend/services/dedicated_labjack_monitor.py`

```python
def _wait_for_session_visibility(self, db: Session, session_id: str, max_retries: int = 5) -> Optional[TestSession]:
    """
    Wait for session to become visible in PostgreSQL with MVCC retry.

    PostgreSQL's MVCC can cause delays between transaction commit and visibility
    to other transactions. This method retries with exponential backoff.
    """
    retry_delays = [0.01, 0.02, 0.04, 0.08, 0.16]  # Exponential backoff

    for attempt in range(max_retries):
        # Refresh database snapshot
        db.flush()
        db.expire_all()

        # Query for session
        session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if session:
            logger.info(f"✅ Session {session_id} found (attempt {attempt + 1}/{max_retries})")
            return session

        if attempt < max_retries - 1:
            delay = retry_delays[attempt]
            time.sleep(delay)

    logger.warning(f"⚠️ Session {session_id} not found after {max_retries} retries")
    return None
```

**Benefits**:
- Handles PostgreSQL MVCC visibility delays
- Exponential backoff: 10ms → 160ms
- Maximum wait: 310ms total
- Returns None if not found (no exception)

#### 2. Redesigned Event Signaling Flow

**New Flow**:
```python
# ✅ CORRECT FLOW
try:
    # STEP 1: VERIFY SESSION EXISTS (FIX-3)
    session_db = self._wait_for_session_visibility(db, session_id)

    if not session_db:
        # Session doesn't exist - mark as degraded and signal
        self.active_sessions[session_id]['timing_degraded'] = True
        self.active_sessions[session_id]['timing_verified'] = False
        timing_ready_event.set()  # Signal so callback doesn't hang

        # Stop monitoring since session is invalid
        self.labjack_monitor.stop_monitoring(session_id)
        return False

    # Session exists and verified!
    self.active_sessions[session_id]['timing_verified'] = True
    logger.info(f"✅ Session {session_id} verified in database")

    # STEP 2: INITIALIZE VIDEO TIMING (FIX-1)
    try:
        video_start_time = self.video_timing_service.start_video_timing(
            session_id, video_id, db, video_metadata
        )

        if video_start_time is None:
            logger.warning(f"⚠️ Video timing returned None")
            self.active_sessions[session_id]['timing_degraded'] = True
            video_start_time = time.time()  # Fallback
        else:
            logger.info(f"✅ Video timing initialized: {video_start_time}")
            self.active_sessions[session_id]['timing_degraded'] = False

    except Exception as timing_error:
        logger.error(f"❌ Video timing failed: {timing_error}")
        self.active_sessions[session_id]['timing_degraded'] = True
        video_start_time = time.time()  # Fallback

    # STEP 3: UPDATE DATABASE WITH STATUS
    try:
        session_db.timing_degraded = self.active_sessions[session_id]['timing_degraded']
        session_db.timing_verified = self.active_sessions[session_id]['timing_verified']
        db.commit()
        logger.info(
            f"📊 Session status: "
            f"verified={self.active_sessions[session_id]['timing_verified']}, "
            f"degraded={self.active_sessions[session_id]['timing_degraded']}"
        )
    except Exception as db_error:
        logger.error(f"Failed to update session status: {db_error}")
        db.rollback()

    # STEP 4: SIGNAL EVENT (Always signal, even if degraded)
    timing_ready_event.set()
    logger.info(f"🚦 Timing event signaled for session {session_id}")

except Exception as fatal_error:
    logger.error(f"Fatal error: {fatal_error}")
    # Even on fatal error, signal event to prevent deadlock
    self.active_sessions[session_id]['timing_degraded'] = True
    timing_ready_event.set()
    return False
```

**Key Changes**:
1. Verify session FIRST with MVCC retry
2. Initialize timing SECOND with error handling
3. Update database with status flags
4. Signal event LAST, after state is known
5. Always signal, even on errors

#### 3. Updated Session Info Tracking

**Added State Flags**:
```python
self.active_sessions[session_id] = {
    'video_timing_config': video_timing_config,
    'labjack_config': labjack_config,
    'started_at': session_init_time,
    'video_start_time': None,
    'detection_callback': None,
    'timing_ready_event': timing_ready_event,
    'timing_degraded': False,   # NEW: Timing reliability flag
    'timing_verified': False,   # NEW: Session verification flag
    'current_video': None,
    'video_history': [],
    'video_boundary_buffer': 0.5
}
```

## State Machine

### States

```
INITIAL → VERIFYING → VERIFIED → TIMING_INIT → READY
              ↓           ↓           ↓
              └─ DEGRADED ←────────────┘
```

### State Transitions

| From | To | Trigger | Actions |
|------|-----|---------|---------|
| INITIAL | VERIFYING | `start_monitoring_with_video_sync()` called | Call `_wait_for_session_visibility()` |
| VERIFYING | VERIFIED | Session found in DB | Set `timing_verified = True` |
| VERIFYING | DEGRADED | Session not found | Set `timing_verified = False`, `timing_degraded = True`, signal event, stop monitoring |
| VERIFIED | TIMING_INIT | Session verified | Call `start_video_timing()` |
| TIMING_INIT | READY | Timing initialized | Set `timing_degraded = False`, signal event |
| TIMING_INIT | DEGRADED | Timing failed | Set `timing_degraded = True`, use fallback, signal event |

### Error Handling

**Path A: Session Not Found**
```
INITIAL → VERIFYING → DEGRADED (stop monitoring)
```

**Path B: Timing Init Failed**
```
INITIAL → VERIFYING → VERIFIED → TIMING_INIT → DEGRADED (continue with fallback)
```

## Database Schema Updates

### TestSession Model

```python
class TestSession(Base):
    # ... existing fields ...

    timing_verified = Column(Boolean, default=False)  # Session verification status
    timing_degraded = Column(Boolean, default=False)  # Timing reliability flag
```

### DetectionEvent Model

```python
class DetectionEvent(Base):
    # ... existing fields ...

    usable_for_validation = Column(Boolean, default=True)  # Can be used for validation
    timing_degraded = Column(Boolean, default=False)       # Timing was degraded
```

## Benefits

### 1. Race Condition Eliminated

- Event signaling happens AFTER state is determined
- Callbacks receive accurate state information
- No confusion between "ready" and "failed"

### 2. MVCC Visibility Handled

- Exponential backoff retry logic
- Handles PostgreSQL transaction visibility delays
- Maximum 310ms wait for session to appear

### 3. Degraded Mode Support

- System continues operating with fallback timing
- Detections marked as `usable_for_validation = False`
- No data loss, just reduced validation confidence

### 4. No Deadlocks

- Event ALWAYS signaled, even on errors
- Callbacks never wait forever
- 10-second timeout as final safety net

### 5. Observable State

- State flags stored in `session_info`
- State persisted to database
- Clear logging at each state transition

## Testing Recommendations

### Unit Tests

1. **Test MVCC retry logic**
   - Session appears on retry 1, 2, 3, 4, 5
   - Session never appears (returns None)

2. **Test state transitions**
   - Success path: INITIAL → VERIFYING → VERIFIED → TIMING_INIT → READY
   - Error path A: INITIAL → VERIFYING → DEGRADED
   - Error path B: INITIAL → VERIFYING → VERIFIED → TIMING_INIT → DEGRADED

3. **Test event signaling**
   - Event signaled after verification success
   - Event signaled after verification failure
   - Event signaled after timing success
   - Event signaled after timing failure
   - Event signaled on fatal exception

### Integration Tests

1. **Test callback coordination**
   - Callback waits for event
   - Callback receives correct state
   - Callback handles degraded mode

2. **Test database updates**
   - `timing_verified` flag persisted
   - `timing_degraded` flag persisted
   - Detection `usable_for_validation` flag set correctly

3. **Test timing accuracy**
   - Normal mode: Video-relative timestamps
   - Degraded mode: Wall clock timestamps
   - Detection quality tracking

## Migration Notes

### No Breaking Changes

- Existing code continues to work
- New fields have default values
- Degraded mode is graceful fallback

### Deployment

1. Apply database migrations for new fields
2. Deploy updated `dedicated_labjack_monitor.py`
3. Monitor logs for state transitions
4. Check database for timing status flags

### Monitoring

**Key Metrics to Track**:
- `timing_verified` rate (should be ~100%)
- `timing_degraded` rate (should be <1%)
- MVCC retry counts (most should succeed on attempt 1)
- Detection `usable_for_validation` rate

**Alert Conditions**:
- High `timing_degraded` rate (>5%)
- Frequent MVCC retries (>3 attempts)
- Low `usable_for_validation` rate (<95%)

## Files Modified

1. `/backend/services/dedicated_labjack_monitor.py`
   - Added `_wait_for_session_visibility()` method
   - Redesigned `start_monitoring_with_video_sync()` flow
   - Updated session_info initialization

2. `/backend/docs/TIMING_STATE_MACHINE.md` (NEW)
   - Complete state machine documentation
   - State transition diagrams
   - Error handling paths

3. `/backend/docs/FIX-1-FIX-3-RESOLUTION.md` (THIS FILE)
   - Problem analysis
   - Solution overview
   - Implementation details

## References

- Original FIX-1: Signal event immediately after DB query
- Original FIX-3: Verify session exists before timing
- PostgreSQL MVCC: https://www.postgresql.org/docs/current/mvcc.html
- State Machine Pattern: https://en.wikipedia.org/wiki/State_pattern

## Conclusion

The conflict between FIX-1 and FIX-3 has been resolved by:

1. **Verifying session first** with MVCC retry logic
2. **Initializing timing second** with graceful error handling
3. **Signaling event last** after state is determined
4. **Always signaling** to prevent deadlocks
5. **Using degraded mode** for partial failures

This ensures robust operation with clear state tracking and no race conditions.
