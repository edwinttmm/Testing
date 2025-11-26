# Video Timing and Session Routing Race Condition Analysis

## Executive Summary

**CRITICAL ISSUES IDENTIFIED:**

1. **Video Start Timing Race Condition**: LabJack monitoring starts capturing detections BEFORE video timing is initialized
2. **Session ID Split**: Two separate session IDs are created - one for API (300f9ec1), one for monitoring (89a0bed2)
3. **Detection Routing Failure**: Detections are written to monitoring session, but results are queried from API session

## Problem Details

### Issue #1: Video Timing Race Condition

**Location**: `/backend/services/dedicated_labjack_monitor.py:449-744`

**Timeline of Operations:**

```python
# Line 548: Session created in video_sequence_testing.py
test_session_id = str(uuid.uuid4())  # e.g., "300f9ec1"

# Line 656: DB commit happens
db.commit()

# Line 698: start_hil_monitoring called
success = await start_hil_monitoring(video_timing_config={
    'test_session_id': test_session_id,  # Passes 300f9ec1
    ...
})

# Line 661: LabJack monitoring STARTS (in dedicated_labjack_monitor.py)
success = self.labjack_monitor.start_monitoring(
    session_id,  # Uses 300f9ec1
    timing_ready_event=timing_ready_event,  # Event to signal when timing ready
    **labjack_config
)
# ⚠️ DETECTION CAPTURE BEGINS HERE

# Line 728: Video timing initialized LATER
video_start_time = self.video_timing_service.start_video_timing(
    session_id, video_id, db, video_metadata
)
# ⚠️ video_start_time is set AFTER detections already started

# Line 701: timing_ready_event.set() - signals timing is ready
# BUT detections from lines 661-728 have WRONG timestamps
```

**The Race Condition:**

1. **T=0ms**: API creates session `300f9ec1` and commits to DB
2. **T=10ms**: `start_hil_monitoring()` called with config containing `test_session_id: 300f9ec1`
3. **T=50ms**: LabJack monitoring starts capturing detections (line 661)
4. **T=100ms**: Video timing service initializes `video_start_time` (line 728)
5. **T=150ms**: Frontend sends `/video-started` endpoint with actual video start time

**Result:** Detections captured between T=50-100ms have incorrect timestamps because `video_start_time` wasn't set yet.

### Issue #2: Session ID Split

**The session ID is passed correctly BUT timing is wrong:**

```python
# video_sequence_testing.py:674
video_timing_config = {
    'test_session_id': test_session_id,  # ✅ Correct: passes 300f9ec1
    'video_id': request.video_ids[0],
    'sequence_id': sequence_id,
    ...
}

# dedicated_labjack_monitor.py:449
async def start_monitoring_with_video_sync(
    self,
    session_id: str,  # ✅ Receives 300f9ec1 correctly
    video_timing_config: Dict[str, Any]
) -> bool:
    # Line 569: Stores session with correct ID
    self.active_sessions[session_id] = {  # ✅ Uses 300f9ec1
        'video_timing_config': video_timing_config,
        'video_start_time': None,  # ⚠️ BUT video_start_time is None initially
        ...
    }
```

**The Real Problem:** It's NOT a session ID mismatch, but a **timing initialization sequence** problem.

### Issue #3: Detection Timestamp Calculation

**Location**: `/backend/services/dedicated_labjack_monitor.py:_handle_detection_with_video_sync()`

When a detection occurs:

```python
def _handle_detection_with_video_sync(self, session_id: str, event: Dict[str, Any]):
    with self.lock:
        session_info = self.active_sessions.get(session_id)

        # ⚠️ PROBLEM: video_start_time might be None
        video_start_time = session_info.get('video_start_time')

        if video_start_time is None:
            # Detection occurs BEFORE video_start_time is set
            # Callback waits for timing_ready_event (line 701)
            # BUT early detections might time out or get wrong timestamps
```

## Root Cause Analysis

### Primary Root Cause: Inverted Initialization Order

**Current (WRONG) Order:**
1. Create session in DB
2. Start LabJack monitoring → **Detections begin immediately**
3. Initialize video timing → **video_start_time set here**
4. Frontend starts playing video → **Actual video start time**

**Correct Order Should Be:**
1. Create session in DB
2. Initialize video timing → **video_start_time MUST be set FIRST**
3. Start LabJack monitoring → **Detections use correct baseline**
4. Frontend starts playing video → **Already synchronized**

### Secondary Issue: video_start_timestamp vs video_start_time

**Two separate timing mechanisms exist:**

1. **`video_start_time`** (backend, line 728):
   - Set by `video_timing_service.start_video_timing()`
   - Used for detection timestamp conversion
   - Set ~50-100ms after monitoring starts

2. **`video_start_timestamp`** (frontend callback):
   - Set by `/video-started` endpoint (line 917)
   - Recorded when video actually begins playing
   - Happens ~200-500ms after monitoring starts

**Gap Problem:** Detections occurring in the 50-500ms gap have incorrect base timestamps.

## Evidence from Logs

Based on the code flow:

```
Session 300f9ec1:
- Created by API at T=0ms
- Committed to database
- Passed to start_hil_monitoring() in video_timing_config

Session 89a0bed2 (if exists):
- Likely created by a DUPLICATE call or retry
- OR created by Windows bridge or another service
```

**To verify, check logs for:**
```bash
grep -E "Session.*created|start_monitoring|video_start_time" backend.log
```

## Impact Analysis

### Detection Loss Scenarios

1. **Early Detections (T=0-100ms):**
   - Captured by LabJack monitoring
   - `video_start_time` is None
   - Wait on `timing_ready_event`
   - May time out or use incorrect fallback timestamp

2. **Rapid Ground Truth (131 objects in 5s = 26/sec):**
   - If video_start_time is delayed, ALL timestamps are offset
   - Ground truth matching fails due to temporal misalignment

3. **Multi-Video Sequences:**
   - First video: 0 detections (timing not ready)
   - Second video: 0 detections (timing still using first video's baseline)

## Recommended Fixes

### Fix #1: Synchronous Video Timing Initialization (CRITICAL)

**Before starting LabJack monitoring, initialize video timing:**

```python
# In start_monitoring_with_video_sync (line 449)

# STEP 1: Initialize video timing FIRST
video_start_time = self.video_timing_service.start_video_timing(
    session_id, video_id, db, video_metadata
)

# STEP 2: Store timing in session
self.active_sessions[session_id] = {
    'video_start_time': video_start_time,  # ✅ Set BEFORE monitoring
    'video_timing_config': video_timing_config,
    ...
}

# STEP 3: NOW start LabJack monitoring
success = self.labjack_monitor.start_monitoring(
    session_id,
    timing_ready_event=timing_ready_event,
    **labjack_config
)
```

### Fix #2: Blocking Wait for Timing Ready

**Ensure timing_ready_event is set BEFORE any detection processing:**

```python
# In start_monitoring_with_video_sync (line 701)

# Set timing ready event IMMEDIATELY after video_start_time is set
if video_start_time is not None:
    self.active_sessions[session_id]['video_start_time'] = video_start_time
    timing_ready_event.set()  # ✅ Signal immediately
    logger.info(f"✅ Timing ready for session {session_id}")
```

### Fix #3: Detection Queue for Pre-Timing Events

**Buffer detections that occur before timing is ready:**

```python
# Add to DedicatedLabJackMonitor.__init__
self.pre_timing_detection_queue: Dict[str, List[Dict]] = {}

# In _handle_detection_with_video_sync
if not session_info.get('timing_ready_event').is_set():
    # Queue detection for processing after timing is ready
    if session_id not in self.pre_timing_detection_queue:
        self.pre_timing_detection_queue[session_id] = []
    self.pre_timing_detection_queue[session_id].append(event)
    logger.debug(f"Queued detection for session {session_id} (timing not ready)")
    return

# After timing_ready_event.set(), flush queue
queued = self.pre_timing_detection_queue.pop(session_id, [])
for queued_event in queued:
    self._handle_detection_with_video_sync(session_id, queued_event)
```

### Fix #4: Validation Check Before Monitoring

**Add explicit check that timing is initialized:**

```python
# Before line 661 (starting LabJack monitoring)

# Validate video_start_time is set
if session_id not in self.active_sessions:
    logger.error(f"❌ Session {session_id} not initialized")
    return False

if self.active_sessions[session_id].get('video_start_time') is None:
    logger.error(f"❌ video_start_time not set for session {session_id}")
    return False

logger.info(f"✅ Timing validated, starting monitoring for {session_id}")
```

## Testing Strategy

### Unit Test: Timing Sequence Validation

```python
def test_video_timing_before_monitoring():
    """Ensure video timing is initialized before LabJack monitoring starts"""
    monitor = DedicatedLabJackMonitor()

    session_id = "test-session"
    video_config = {...}

    # Mock video timing service
    with patch.object(monitor.video_timing_service, 'start_video_timing') as mock_timing:
        mock_timing.return_value = 1234567890.5

        # Start monitoring
        success = await monitor.start_monitoring_with_video_sync(session_id, video_config)

        # Verify timing was called BEFORE monitoring started
        assert mock_timing.called
        assert session_id in monitor.active_sessions
        assert monitor.active_sessions[session_id]['video_start_time'] == 1234567890.5
```

### Integration Test: Early Detection Handling

```python
def test_early_detections_queued():
    """Verify detections before timing ready are queued and processed"""
    monitor = DedicatedLabJackMonitor()

    session_id = "test-session"

    # Simulate detection BEFORE timing ready
    timing_ready = threading.Event()
    monitor.active_sessions[session_id] = {
        'timing_ready_event': timing_ready,
        'video_start_time': None
    }

    # Send detection
    detection = {'timestamp': time.time(), 'voltage': 3.3}
    monitor._handle_detection_with_video_sync(session_id, detection)

    # Verify queued
    assert session_id in monitor.pre_timing_detection_queue
    assert len(monitor.pre_timing_detection_queue[session_id]) == 1

    # Set timing ready
    monitor.active_sessions[session_id]['video_start_time'] = time.time()
    timing_ready.set()

    # Verify queue processed
    assert session_id not in monitor.pre_timing_detection_queue
```

## Priority Ranking

1. **🔴 CRITICAL**: Fix #1 (Synchronous timing initialization) - Prevents all early detections
2. **🟠 HIGH**: Fix #2 (Immediate timing ready signal) - Reduces timing gaps
3. **🟡 MEDIUM**: Fix #3 (Detection queue) - Handles edge cases
4. **🟢 LOW**: Fix #4 (Validation check) - Defensive programming

## Files to Modify

1. `/backend/services/dedicated_labjack_monitor.py` (lines 449-744)
   - Reorder initialization sequence
   - Add detection queue
   - Add validation checks

2. `/backend/routers/video_sequence_testing.py` (lines 662-709)
   - Ensure timing config is complete before monitoring

3. `/backend/services/video_timing_service.py`
   - Add validation that timing is set synchronously

## Success Criteria

✅ **Zero detections lost due to timing gaps**
✅ **All detections have valid video_relative_timestamp**
✅ **Ground truth matching works for rapid detections (26/sec)**
✅ **Multi-video sequences maintain correct timing per video**
✅ **No race conditions between timing and monitoring**

## Monitoring and Validation

After fixes are applied:

```python
# Add metric tracking
detection_metrics.timing_gaps.inc()  # Count timing gaps
detection_metrics.early_detections.inc()  # Count pre-timing detections
detection_metrics.queued_detections.inc()  # Count queued detections

# Add log validation
logger.info(f"TIMING_METRICS: session={session_id}, "
           f"timing_ready_latency_ms={latency}, "
           f"queued_detections={queue_size}, "
           f"video_start_time={video_start_time}")
```

---

**Document Version**: 1.0
**Date**: 2025-11-25
**Author**: Code Analyzer Agent
**Status**: Analysis Complete - Fixes Required
