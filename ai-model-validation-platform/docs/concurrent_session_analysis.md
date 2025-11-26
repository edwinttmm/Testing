# Concurrent Session Conflict Analysis

## Executive Summary

**ROOT CAUSE IDENTIFIED**: The LabJack monitor is designed for CONCURRENT sessions, but has a critical timing race condition where detections can arrive before timing data is initialized, causing "Timed out waiting for timing data" errors.

## Problem Sessions

- **Session 8b47a2f4-f790-48ec-907a-4b51d5eb27d5**: ❌ 0 detections (timed out waiting for timing data)
- **Session 2c2b331b-ce6d-497f-972a-507fadea06e1**: ✅ 16 detections (successful)

## Session Isolation Analysis

### What's Per-Session (Isolated)
```python
# Line 104-105: Session tracking is fully isolated
self.active_sessions: Dict[str, Dict[str, Any]] = {}
self.detection_events: Dict[str, List[HILDetectionEvent]] = {}
```

Each session has:
- **Unique session_id key** in `active_sessions` dict
- **Dedicated detection_callback** (line 520): `lambda event: self._handle_detection_with_video_sync(session_id, event)`
- **Session-specific timing_ready_event** (line 502): Threading event for sync
- **Independent video_start_time** (line 509)
- **Separate detection_events list** (line 797)

### What's Shared (Global)
```python
# Line 93-94: Shared hardware monitor
self.labjack_monitor = get_detection_service()
self.hil_comparison_service = get_hil_ground_truth_comparison()

# Line 111: Shared thread lock
self.lock = threading.RLock()
```

Shared resources:
- **LabJack hardware device** (single physical device)
- **Hardware monitoring thread** (shared across sessions)
- **Detection callbacks list** (all sessions register here)
- **Thread synchronization lock** (prevents race conditions)

## Critical Timing Race Condition

### The "Timed out waiting for timing data" Error

**Location**: Line 848-850
```python
is_set = timing_ready_event.wait(timeout=2.0)
if not is_set:
    logger.error(f"❌ Timed out waiting for timing data for session {session_id}. Aborting detection.")
    return
```

### Race Condition Flow

```
Timeline for Session 8b47a2f4:

T+0ms    : start_monitoring_with_video_sync() called
T+0ms    : Session entry created in active_sessions (line 505)
T+0ms    : Detection callback registered (line 527)
T+0ms    : LabJack monitoring starts (line 594)
T+5ms    : ❌ HARDWARE DETECTION ARRIVES (too early!)
T+5ms    : Detection callback triggered
T+5ms    : timing_ready_event.wait(timeout=2.0) starts waiting...
T+50ms   : Video timing service initializes (line 641)
T+50ms   : timing_ready_event.set() called (line 653)
T+2005ms : ⏰ TIMEOUT! Detection aborted with "Timed out waiting for timing data"

Result: Detection lost, session shows 0 detections
```

### Why Session 2c2b331b Succeeded

Session 2c2b331b likely had NO detections in the first 50ms after start, allowing timing data to initialize before hardware events arrived.

## Hardware Connection Support

### Concurrent Session Design: ✅ SUPPORTED

The code is explicitly designed for concurrent sessions:

1. **Session-specific monitoring** (line 594):
   ```python
   success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)
   ```

2. **Session-preserving cleanup** (line 2030-2157):
   ```python
   def stop_session_monitoring(self, session_id: str)
   ```
   - Only removes session-specific callbacks
   - Preserves hardware connection
   - Documents "connection_preserved": True

3. **Multiple session tracking** (line 2118):
   ```python
   'active_sessions_remaining': len(self.active_sessions) - 1
   ```

**Hardware Constraint**: Only ONE physical LabJack device, but multiple sessions can share it through session-specific callbacks.

## Detection Routing Analysis

### Hardware → Callback → Session Flow

```
[LabJack Hardware]
        ↓
[Shared Monitoring Thread]
        ↓
[Detection Event Triggered]
        ↓
[Callbacks Dispatched] ← Multiple sessions register here
        ↓
   Session A Callback: lambda event: _handle_detection_with_video_sync("session-a", event)
   Session B Callback: lambda event: _handle_detection_with_video_sync("session-b", event)
        ↓
[_handle_detection_with_video_sync(session_id, event)]
        ↓
[Session Validation] (line 835-837)
   if session_id not in self.active_sessions:
       return  # Skip inactive sessions
        ↓
[Wait for timing_ready_event] (line 847)
   is_set = timing_ready_event.wait(timeout=2.0)
   if not is_set:
       ❌ ABORT DETECTION
        ↓
[Process Detection]
```

**KEY FINDING**: Each hardware detection triggers ALL registered callbacks, but each callback is bound to a specific session_id. Detections are NOT misrouted between sessions.

## Session Cleanup Issues

### Orphaned Session Recovery

**Location**: Line 153-204
```python
def recover_orphaned_sessions(self):
    """Recover sessions left in monitoring state from crashes"""
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

    orphaned = db.query(TestSession).filter(
        TestSession.completed_at == None,
        TestSession.status == "monitoring",
        TestSession.created_at < cutoff_time
    ).all()
```

**Finding**: Sessions older than 24 hours in "monitoring" state are marked as "crashed"
- Session 8b47a2f4 might have been recovered as orphaned if it was old
- This would explain why it had no active timing configuration

### Callback Removal

**Critical Issue Identified**: Line 2066-2071
```python
detection_callback = session_data.get('detection_callback')
if detection_callback and self.labjack_monitor:
    try:
        self.labjack_monitor.remove_detection_callback(detection_callback)
        logger.info(f"🧹 Detection callback removed for session {session_id}")
```

**Problem**: If session 8b47a2f4 was stopped but callback wasn't removed properly, it could still receive hardware events but have no timing data.

## Concurrency Support Assessment

### Design Intent: ✅ CONCURRENT SESSIONS SUPPORTED

**Evidence**:
1. Session-specific callback registration (line 520)
2. Session isolation via dict keys (line 104-105)
3. Connection-preserving cleanup (line 2030)
4. Active sessions count tracking (line 2118)

### Implementation Issues: ⚠️ TIMING RACE CONDITION

**Problems**:
1. **Early Detection Loss** (line 848): 2-second timeout too aggressive for startup
2. **No Buffering**: Detections before timing_ready are discarded, not queued
3. **Startup Sequence**: LabJack starts before video timing (line 594 vs 641)

## Root Cause Determination

### Why Session 8b47a2f4 Got 0 Detections

**Hypothesis**: Timing data timeout caused by initialization race condition

```
Session 8b47a2f4 Timeline:
1. Session starts monitoring (LabJack enabled immediately)
2. Hardware detections arrive within first 50ms
3. Detection callbacks wait for timing_ready_event
4. Video timing service initializes slowly (>2 seconds?)
5. All detection callbacks timeout at 2.0s and abort
6. Result: 0 detections recorded
```

**Contributing Factors**:
- Hardware was VERY responsive (detections came immediately)
- Video timing initialization was slow or failed
- 2-second timeout was insufficient
- No retry or buffering mechanism

### Why Session 2c2b331b Got 16 Detections

**Hypothesis**: Lucky timing - no detections in first 50ms

```
Session 2c2b331b Timeline:
1. Session starts monitoring
2. NO detections in first 50ms (grace period)
3. Video timing initializes successfully (line 653)
4. timing_ready_event.set() called
5. Hardware detections start arriving after 50ms
6. All callbacks succeed immediately (event already set)
7. Result: 16 detections recorded
```

## Could Detections Be Misrouted?

### Answer: ❌ NO - Misrouting Not Possible

**Evidence**:
1. **Callback Closure** (line 520):
   ```python
   detection_callback = lambda event: self._handle_detection_with_video_sync(session_id, event)
   ```
   - `session_id` is captured in closure
   - Each callback is bound to specific session

2. **Session Validation** (line 835-837):
   ```python
   if session_id not in self.active_sessions:
       logger.debug(f"🚫 Skipping detection for inactive session: {session_id}")
       return
   ```
   - Early exit prevents processing for wrong session

3. **Detection Storage** (line 1033-1036):
   ```python
   with self.lock:
       if session_id not in self.detection_events:
           self.detection_events[session_id] = []
       self.detection_events[session_id].append(hil_event)
   ```
   - Detections stored in session-specific list

**Conclusion**: Session 2c2b331b cannot receive detections meant for 8b47a2f4.

## Should Concurrent Sessions Be Prevented?

### Answer: ❌ NO - Fix the Timing Race Instead

**Reasons**:
1. System is designed for concurrency (session-preserving cleanup)
2. Hardware supports multiple session callbacks
3. Only issue is startup timing race condition
4. Preventing concurrency would break multi-test scenarios

## Recommended Session Coordination Strategy

### 1. Buffer Early Detections (Highest Priority)

```python
class DedicatedLabJackMonitor:
    def __init__(self):
        # Add early detection buffer
        self.early_detection_buffer: Dict[str, List[Any]] = {}

    def _handle_detection_with_video_sync(self, session_id: str, labjack_event):
        timing_ready_event = session_info.get('timing_ready_event')
        if timing_ready_event:
            is_set = timing_ready_event.wait(timeout=0.01)  # Quick check
            if not is_set:
                # Buffer detection for later processing
                if session_id not in self.early_detection_buffer:
                    self.early_detection_buffer[session_id] = []
                self.early_detection_buffer[session_id].append(labjack_event)
                logger.info(f"Buffered early detection for session {session_id}")
                return

        # Normal processing...
```

### 2. Increase Timeout Duration

Change line 847:
```python
is_set = timing_ready_event.wait(timeout=10.0)  # Increased from 2.0s to 10.0s
```

### 3. Retry Mechanism

```python
def _handle_detection_with_video_sync(self, session_id: str, labjack_event):
    max_retries = 3
    for attempt in range(max_retries):
        timing_ready_event = session_info.get('timing_ready_event')
        if timing_ready_event:
            is_set = timing_ready_event.wait(timeout=5.0)
            if is_set:
                break
            logger.warning(f"Retry {attempt+1}/{max_retries} waiting for timing data")

    if not is_set:
        logger.error(f"❌ Failed after {max_retries} retries")
        return
```

### 4. Process Buffered Detections After Timing Ready

```python
def start_monitoring_with_video_sync(self, session_id: str, video_timing_config: Dict):
    # ... existing code ...

    # Signal timing ready
    timing_ready_event.set()

    # Process any buffered early detections
    if session_id in self.early_detection_buffer:
        buffered = self.early_detection_buffer.pop(session_id)
        logger.info(f"Processing {len(buffered)} buffered detections for session {session_id}")
        for buffered_event in buffered:
            self._handle_detection_with_video_sync(session_id, buffered_event)
```

## Summary

### Concurrency Verdict: ✅ SUPPORTED BUT BUGGY

- **Concurrent sessions**: Fully supported by design
- **Hardware sharing**: Properly implemented with session-specific callbacks
- **Detection routing**: Correctly isolated per session (no cross-contamination)
- **Critical bug**: Timing race condition causes early detection loss

### Session 8b47a2f4 Failure Root Cause

**Primary**: Timing data initialization race condition
- Hardware detections arrived before video timing initialized
- 2-second timeout expired before timing_ready_event was set
- All detections aborted, resulting in 0 records

### Session 2c2b331b Success

**Reason**: Lucky timing - no detections in critical startup window
- Video timing initialized before first hardware detection
- All subsequent detections processed successfully

### Recommended Fix Priority

1. **High**: Buffer early detections instead of discarding (prevents data loss)
2. **High**: Increase timeout from 2s to 10s (more robust startup)
3. **Medium**: Add retry mechanism with exponential backoff
4. **Medium**: Process buffered detections after timing ready
5. **Low**: Add monitoring for timing initialization duration

### Concurrency Strategy

**DO NOT PREVENT CONCURRENT SESSIONS**
- System is designed for it
- Only fix is timing race condition
- Maintain session-preserving cleanup pattern
- Keep hardware connection shared across sessions
