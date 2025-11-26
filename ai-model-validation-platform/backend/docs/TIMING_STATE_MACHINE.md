# Timing State Machine Documentation

## Overview

This document describes the state machine for LabJack monitoring with video timing synchronization. The state machine ensures proper coordination between session verification, timing initialization, and event signaling to prevent race conditions and deadlocks.

## State Machine Diagram

```
INITIAL → VERIFYING → VERIFIED → TIMING_INIT → READY
              ↓           ↓           ↓
              └─ DEGRADED ←────────────┘
```

## State Definitions

### 1. INITIAL
- **Description**: Session tracking created, monitoring not yet started
- **State Flags**:
  - `timing_verified = False`
  - `timing_degraded = False`
  - `timing_ready_event = not set`
- **Actions**: Initialize session_info dictionary with timing_ready_event

### 2. VERIFYING
- **Description**: Attempting to verify session exists in database
- **State Flags**:
  - `timing_verified = False`
  - `timing_degraded = False`
  - `timing_ready_event = not set`
- **Actions**:
  - Call `_wait_for_session_visibility()` with MVCC retry
  - Exponential backoff: 10ms, 20ms, 40ms, 80ms, 160ms (max 5 retries)
  - Refresh database snapshot on each attempt

### 3. VERIFIED
- **Description**: Session found and verified in database
- **State Flags**:
  - `timing_verified = True`
  - `timing_degraded = False`
  - `timing_ready_event = not set`
- **Actions**:
  - Set `timing_verified = True`
  - Proceed to timing initialization

### 4. TIMING_INIT
- **Description**: Initializing video timing service
- **State Flags**:
  - `timing_verified = True`
  - `timing_degraded = (depends on initialization)`
  - `timing_ready_event = not set`
- **Actions**:
  - Call `video_timing_service.start_video_timing()`
  - If successful: `timing_degraded = False`
  - If failed/None: `timing_degraded = True`, use fallback wall clock
  - Update database with timing status
  - **ALWAYS signal event after this step**

### 5. READY
- **Description**: Monitoring ready, event signaled
- **State Flags**:
  - `timing_verified = True`
  - `timing_degraded = (from TIMING_INIT)`
  - `timing_ready_event = set`
- **Actions**:
  - Signal `timing_ready_event.set()`
  - LabJack monitoring proceeds
  - Detections processed with timing context

### 6. DEGRADED
- **Description**: Session failed verification OR timing initialization failed
- **State Flags**:
  - `timing_verified = (depends on which step failed)`
  - `timing_degraded = True`
  - `timing_ready_event = set` (to prevent deadlock)
- **Actions**:
  - Signal `timing_ready_event.set()` to prevent callback hanging
  - Use wall clock timestamps as fallback
  - Mark detections as `usable_for_validation = False`
  - Update database with degraded status

## State Transitions

### Normal Flow (Success Path)

```python
INITIAL → VERIFYING → VERIFIED → TIMING_INIT → READY
```

1. **INITIAL → VERIFYING**
   - Trigger: `start_monitoring_with_video_sync()` called
   - Action: Call `_wait_for_session_visibility()`

2. **VERIFYING → VERIFIED**
   - Trigger: Session found in database
   - Action: Set `timing_verified = True`

3. **VERIFIED → TIMING_INIT**
   - Trigger: Session verification complete
   - Action: Call `video_timing_service.start_video_timing()`

4. **TIMING_INIT → READY**
   - Trigger: Timing initialization complete (success or fallback)
   - Action: Signal `timing_ready_event.set()`

### Error Paths (Degraded Mode)

#### Path A: Session Not Found

```python
INITIAL → VERIFYING → DEGRADED
```

- **Trigger**: Session not found after 5 MVCC retries
- **Actions**:
  1. Set `timing_verified = False`
  2. Set `timing_degraded = True`
  3. Signal `timing_ready_event.set()`
  4. Stop LabJack monitoring
  5. Return `False` from `start_monitoring_with_video_sync()`

#### Path B: Timing Initialization Failed

```python
INITIAL → VERIFYING → VERIFIED → TIMING_INIT → DEGRADED
```

- **Trigger**: `video_timing_service.start_video_timing()` returns None or raises exception
- **Actions**:
  1. Set `timing_verified = True` (session exists)
  2. Set `timing_degraded = True` (timing unreliable)
  3. Use fallback: `video_start_time = time.time()`
  4. Update database with degraded status
  5. Signal `timing_ready_event.set()`
  6. Continue monitoring with wall clock timestamps

## Event Signaling Rules

### Critical Rule: Always Signal Event

**The `timing_ready_event` MUST be signaled in ALL cases, including errors.**

This prevents the detection callback from waiting forever (10-second timeout).

### Signaling Logic

```python
# ✅ CORRECT: Signal after verification and timing init
try:
    session_db = _wait_for_session_visibility(db, session_id)
    if not session_db:
        # Failed verification - signal degraded
        timing_ready_event.set()
        return False

    # Verification successful
    timing_verified = True

    # Try timing init
    try:
        video_start_time = start_video_timing(...)
        timing_degraded = (video_start_time is None)
    except:
        timing_degraded = True
        video_start_time = time.time()

    # Update database
    session_db.timing_verified = timing_verified
    session_db.timing_degraded = timing_degraded
    db.commit()

    # ALWAYS signal, regardless of degraded status
    timing_ready_event.set()

except Exception as fatal_error:
    # Even on fatal error, signal to prevent deadlock
    timing_degraded = True
    timing_ready_event.set()
```

### Why Signal After Verification?

**Problem with signaling BEFORE verification:**
```python
# ❌ WRONG: Signal before verification
timing_ready_event.set()  # Signal immediately

session_db = query_session(session_id)
if not session_db:
    raise Exception("Session not found")  # Too late! Event already signaled
```

**Result**: Callback proceeds with bad data, database queries fail, detections lost.

**Solution: Signal AFTER verification:**
```python
# ✅ CORRECT: Verify first, then signal
session_db = _wait_for_session_visibility(db, session_id)
if not session_db:
    timing_ready_event.set()  # Signal degraded state
    return False

# Session verified
timing_verified = True
# ... timing init ...
timing_ready_event.set()  # Signal ready state
```

**Result**: Callback waits for verification, then proceeds with correct state.

## MVCC Retry Logic

### Purpose

PostgreSQL's Multi-Version Concurrency Control (MVCC) can cause visibility delays between transactions. A session might be committed but not yet visible to other transactions.

### Implementation

```python
def _wait_for_session_visibility(db: Session, session_id: str, max_retries: int = 5) -> Optional[TestSession]:
    """
    Wait for session to become visible in PostgreSQL with MVCC retry.
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
            return session

        if attempt < max_retries - 1:
            time.sleep(retry_delays[attempt])

    return None  # Not found after retries
```

### Retry Schedule

| Attempt | Delay (ms) | Cumulative (ms) |
|---------|-----------|----------------|
| 1       | 0         | 0              |
| 2       | 10        | 10             |
| 3       | 20        | 30             |
| 4       | 40        | 70             |
| 5       | 80        | 150            |
| Total   | 160       | 310            |

**Maximum wait time**: 310ms for all retries

## Detection Callback Coordination

### Callback Wait Logic

```python
def _on_labjack_detection_callback(session_id, voltage, timestamp):
    session_info = active_sessions.get(session_id)
    timing_ready_event = session_info.get('timing_ready_event')

    if timing_ready_event:
        # Wait up to 10 seconds for timing to be ready
        is_set = timing_ready_event.wait(timeout=10.0)

        if not is_set:
            # Timeout - use degraded timing
            timing_degraded = True
            # CRITICAL: Continue processing, don't discard detection
        else:
            # Event signaled - check degradation status
            timing_degraded = session_info.get('timing_degraded', False)

    # Process detection with timing context
    usable_for_validation = not timing_degraded
    # ... store detection with usable_for_validation flag ...
```

### Timeout Handling

- **Timeout Duration**: 10 seconds (increased from 2s to handle slow timing init)
- **On Timeout**: Mark as degraded, continue with fallback timing
- **Critical**: Never discard detections on timeout

## Database Schema Updates

### New Fields in TestSession

```python
class TestSession(Base):
    # ... existing fields ...

    timing_verified = Column(Boolean, default=False)  # Session verification status
    timing_degraded = Column(Boolean, default=False)  # Timing reliability flag
```

### New Fields in DetectionEvent

```python
class DetectionEvent(Base):
    # ... existing fields ...

    usable_for_validation = Column(Boolean, default=True)  # Can be used for validation
    timing_degraded = Column(Boolean, default=False)       # Timing was degraded
```

## Error Handling

### Error Categories

1. **Session Not Found** (DEGRADED Path A)
   - Session doesn't exist in database
   - Verification fails after MVCC retries
   - Stop monitoring, return False

2. **Timing Init Failed** (DEGRADED Path B)
   - Session exists but timing service fails
   - Use fallback wall clock timestamps
   - Continue monitoring with degraded timing

3. **Fatal Error**
   - Unexpected exception in monitoring setup
   - Signal event to prevent deadlock
   - Stop monitoring, return False

### Error Recovery

```python
try:
    # Verification + Timing Init
    ...
except Exception as fatal_error:
    logger.error(f"Fatal error: {fatal_error}")
    # Ensure event is signaled
    timing_degraded = True
    timing_ready_event.set()
    return False
```

## Monitoring Flow

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. start_monitoring_with_video_sync()                       │
│    - Initialize session_info                                │
│    - Create timing_ready_event                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Start LabJack Monitoring                                 │
│    - Pass timing_ready_event to monitoring loop             │
│    - Detection callback waits for event                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. VERIFYING: _wait_for_session_visibility()                │
│    - MVCC retry with exponential backoff                    │
│    - If not found → DEGRADED (Path A)                       │
│    - If found → VERIFIED                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. VERIFIED: Session exists                                 │
│    - Set timing_verified = True                             │
│    - Proceed to timing init                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. TIMING_INIT: start_video_timing()                        │
│    - Try to initialize timing service                       │
│    - If fails → timing_degraded = True, use fallback        │
│    - If success → timing_degraded = False                   │
│    - Update database with status                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. READY: Signal timing_ready_event                         │
│    - ALWAYS signal, even if degraded                        │
│    - Detection callback proceeds                            │
│    - Monitoring active with timing context                  │
└─────────────────────────────────────────────────────────────┘
```

## Key Takeaways

1. **Always Verify Session First**: Use MVCC retry to handle visibility delays
2. **Signal Event After State is Known**: Prevent callbacks from proceeding with unknown state
3. **Always Signal Event**: Even on errors, signal to prevent deadlock
4. **Use Fallback Timing**: Don't fail sessions due to timing issues, use degraded mode
5. **Track State Explicitly**: Use timing_verified and timing_degraded flags
6. **Update Database**: Persist timing status for observability
7. **Never Discard Detections**: Even degraded timing is better than no data

## Related Files

- `/backend/services/dedicated_labjack_monitor.py` - Main implementation
- `/backend/services/video_timing_service.py` - Timing initialization
- `/backend/models.py` - Database schema with timing flags
- `/backend/config/timing_config.py` - Timing constants
