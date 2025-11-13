# Race Condition & Timing Issues Analysis

## Critical Findings: Video 2 Timing Race Condition

### Summary
**ROOT CAUSE IDENTIFIED**: Detection events are created with `video_id` but **BEFORE** the orchestrator's `notify_video_started()` is called, resulting in:
- Detections have `video_id=Video2`
- But `video_start_time=NULL` or wrong value
- Ground truth matching uses incorrect timing reference
- All Video 2 detections fail matching

---

## Question 1: When is Video 2's timing written to database?

### Current Flow (BUGGY)

```python
# video_sequence_orchestrator.py - Line 266-336
def notify_video_started(sequence_id, video_id, actual_start_timestamp, db):
    # Update video metadata
    metadata.video_start_time = actual_start_timestamp  # Line 303
    metadata.video_play_offset_ms = video_play_offset_ms

    # Update video result
    result.video_start_time = actual_start_timestamp  # Line 308
    result.video_play_offset_ms = video_play_offset_ms

    # Start video timing in timing service
    self._timing_service.start_video_timing(  # Line 317-326
        session_id=sequence.session_id,
        video_id=video_id,
        db=db
    )
```

**CRITICAL ISSUE**: This is called from the **frontend** when video playback starts:
- Frontend sends POST to `/api/videos/{video_id}/start_playback`
- Backend calls `orchestrator.notify_video_started()`
- Timing data is written to in-memory orchestrator state
- Database update happens via `start_video_timing()`

**BUT**: LabJack monitoring is already running and creating detections!

---

## Question 2: When are DetectionEvents created?

### Detection Creation Flow

```python
# labjack_detection_service.py - Line 421-496
def _monitoring_loop(self, session_id: str):
    while not stop_event.is_set():
        # Read voltages from LabJack
        channel_readings = {}
        for channel in config.channels:
            voltage = self.connection_manager.read_voltage(channel)  # Line 449
            channel_readings[channel] = voltage

        # Check for detection events
        for channel, voltage in channel_readings.items():
            if voltage >= config.voltage_threshold:  # Line 471
                event = self._create_detection_event(...)  # Line 474-476
                self._record_detection_event(session_id, event)  # Line 477
```

**CRITICAL**: `_create_detection_event()` calls `_get_session_timing_info()` (line 524):

```python
# Line 765-788
def _get_session_timing_info(self, session_id: str):
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if session:
        return {
            'video_start_timestamp': session.video_start_timestamp,  # ❌ Wrong!
            'started_at': session.started_at
        }
```

**BUG**: This returns `TestSession.video_start_timestamp` which is:
1. Set only for Video 1 (primary video)
2. **NEVER updated for Video 2** in multi-video sequences
3. Used as timing reference for ALL detections

---

## Question 3: Threading/Concurrency Issues

### Race Condition Timeline

```
Time    Thread                  Action
------  ----------------------  -----------------------------------------
T=0     Main                    Start test session
T=1     Main                    Start LabJack monitoring (background thread)
T=2     Frontend                Start Video 1 playback
T=3     Background (LabJack)    ✅ Create Video 1 detections (correct timing)
T=30    Frontend                Video 1 ends
T=31    Frontend                Start Video 2 playback
T=31    Main                    orchestrator.notify_video_started(video2) ❌ NOT CALLED YET!
T=32    Background (LabJack)    ⚠️ Create Video 2 detections
                                   - video_id = Video2 ✅
                                   - video_start_timestamp = Video1 start ❌ WRONG!
T=33    Main                    notify_video_started() FINALLY called
                                   - Updates in-memory state
                                   - But detections already created!
```

### Root Cause

**The detection service reads timing from the wrong source**:

```python
# labjack_detection_service.py - Line 524
# Get session info from database to calculate video-relative timestamp
session_info = self._get_session_timing_info(session_id)
if session_info and session_info.get('video_start_timestamp'):
    video_start_time = session_info['video_start_timestamp']  # ❌ ALWAYS Video 1 time!
```

**This should be**:
```python
# Get timing from orchestrator for current video
sequence = orchestrator._get_sequence(sequence_id)
current_video_id = get_current_video_id_for_detection(detection_timestamp)
video_metadata = sequence.video_metadata[current_video_id]
video_start_time = video_metadata.video_start_time  # ✅ Correct per-video timing
```

---

## Question 4: Check the actual session b6662f68

**Cannot check** - Session not in current database (likely from different environment/test run).

However, the bug is confirmed in the code:

### Evidence from ground_truth_matching_service.py

```python
# Line 606-636 - Video boundary validation
detection_video_id = getattr(detection, 'video_id', None)
gt_video_id = getattr(gt_obj, 'video_id', None)

if detection_video_id is not None and gt_video_id is not None:
    if detection_video_id != gt_video_id:
        video_boundary_rejections += 1
        continue  # ✅ Correctly rejects cross-video matches
```

**This works IF** `detection.video_id` is correct. But the timing is wrong!

```python
# Line 638-643 - Temporal matching calculation
detection_time = (
    detection.video_relative_timestamp  # ❌ Wrong calculation!
    if getattr(detection, "video_relative_timestamp", None) is not None
    else detection.timestamp
)
time_diff = abs(detection_time - gt_obj.timestamp)
```

**Bug**: `video_relative_timestamp` is calculated from wrong `video_start_time`:
- Video 2 detection @ 32.5s absolute time
- `video_start_time` = Video 1 start (0.0s) ❌
- `video_relative_timestamp` = 32.5s (should be ~2.5s)
- Ground truth @ 2.5s in Video 2
- Time diff = 30s → NO MATCH!

---

## Fix Requirements

### 1. Detection Service Must Use Orchestrator Timing

```python
# labjack_detection_service.py
class LabJackDetectionMonitor:
    def __init__(self, orchestrator_service=None):
        self._orchestrator = orchestrator_service or get_video_sequence_orchestrator()

    def _create_detection_event(self, session_id, ...):
        # Get current video timing from orchestrator
        sequence_id = self._get_sequence_id(session_id)
        if sequence_id:
            sequence = self._orchestrator._get_sequence(sequence_id)
            video_id = self._orchestrator._determine_video_for_detection(
                sequence, timestamp
            )
            if video_id:
                metadata = sequence.video_metadata[video_id]
                video_start_time = metadata.video_start_time  # ✅ Correct!
```

### 2. Cache Refresh Strategy

```python
# Option A: Event-driven cache refresh
def notify_video_started(self, sequence_id, video_id, actual_start_timestamp):
    # ... existing code ...

    # Notify detection service of timing update
    detection_service.update_video_timing_cache(
        session_id=self.session_id,
        video_id=video_id,
        video_start_time=actual_start_timestamp
    )
```

```python
# Option B: Detection service queries orchestrator on every detection
def _create_detection_event(self, session_id, timestamp, ...):
    # Real-time timing lookup (no cache staleness)
    timing_info = self._orchestrator.get_timing_for_timestamp(
        session_id, timestamp
    )
    video_relative_timestamp = timestamp - timing_info.video_start_time
```

### 3. Database Schema Fix (Long-term)

Add `current_video_id` and `current_video_start_time` to `test_sessions`:
```sql
ALTER TABLE test_sessions ADD COLUMN current_video_id TEXT;
ALTER TABLE test_sessions ADD COLUMN current_video_start_time REAL;
```

Update in `notify_video_started()`:
```python
session.current_video_id = video_id
session.current_video_start_time = actual_start_timestamp
db.commit()
```

---

## Recommended Fix (Immediate)

**Pass orchestrator reference to detection service** and query on every detection:

```python
# In session start endpoint
orchestrator = get_video_sequence_orchestrator()
detection_monitor = get_detection_monitor()
detection_monitor.set_orchestrator(orchestrator)

# In detection service
def _create_detection_event(self, session_id, timestamp, channel, voltage, ...):
    # Get current video timing from orchestrator
    if self._orchestrator:
        timing = self._orchestrator.get_timing_for_timestamp(session_id, timestamp)
        if timing:
            video_start_time = timing['video_start_time']
            video_id = timing['video_id']
            video_relative_timestamp = timestamp - video_start_time
    else:
        # Fallback to old method
        video_start_time = self._get_session_timing_info(session_id)
```

**This ensures**:
1. No race condition (always queries latest state)
2. No cache staleness
3. Correct per-video timing
4. Minimal code changes

---

## Testing Strategy

1. **Unit Test**: Mock orchestrator timing updates
2. **Integration Test**: Start sequence, verify detections have correct timing
3. **Timing Test**: Inject detections during Video 2, verify `video_relative_timestamp`
4. **Boundary Test**: Verify detections near video transition are assigned correctly

---

## Conclusion

**Race Condition Confirmed**: Detection events are created with `video_id` from the orchestrator but `video_start_time` from stale database cache (Video 1's start time), causing:
- Incorrect `video_relative_timestamp` calculation
- Ground truth matching failures
- 0 matched detections for Video 2

**Fix**: Detection service must query orchestrator's in-memory timing state instead of database cache.
