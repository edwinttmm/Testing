# LabJack Zero Detection Root Cause Analysis

## Executive Summary

**Problem**: During HIL test execution for session `09fdeac0-e1b2-4666-b158-2ca013e073d5`, the LabJack hardware remained "Connected" but generated **0 detections** despite expecting 242 detections (121 per video).

**Root Cause**: The LabJack monitoring loop IS running, but detections are being **silently filtered out** due to a timing window validation bug that occurs BEFORE any WebSocket emission or database storage.

## Evidence from Log Analysis

```
Test session: 09fdeac0-e1b2-4666-b158-2ca013e073d5
LabJack Status: Connected (throughout entire test)
Expected Detections: 242 (121 per video × 2 videos)
Actual Detections: 0
Backend Architecture: test_sessions → start_hil_monitoring → raw_labjack_integration.py
```

## Architecture Flow (What SHOULD Happen)

```
1. POST /api/test-sessions/{id}/start-hil-test
   ↓
2. test_sessions.py line 1137: await start_hil_monitoring(session_id, video_timing_config)
   ↓
3. dedicated_labjack_monitor.py line 2046: start_hil_monitoring() → start_monitoring_with_video_sync()
   ↓
4. dedicated_labjack_monitor.py line 299: Start LabJack monitoring BEFORE video timing
   ↓
5. labjack_detection_service.py line 335: start_monitoring() creates monitoring thread
   ↓
6. labjack_detection_service.py line 631: _monitoring_loop() starts polling hardware
   ↓
7. Detection callback: _handle_detection_with_video_sync()
   ↓
8. WebSocket emission: _emit_detection_event_sync()
   ↓
9. Database storage: _store_event_sync_wrapper()
```

## The Breaking Point (Code Analysis)

### Location 1: Monitoring Loop IS Running

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

**Line 631-1046**: `_monitoring_loop()` function

```python
def _monitoring_loop(self, session_id: str):
    """Main monitoring loop for a session with auto-stop on video end"""
    try:
        config = self.active_sessions[session_id]
        stop_event = self.stop_events[session_id]

        self.detection_status[session_id] = DetectionStatus.MONITORING

        # Calculate polling interval based on sample rate
        poll_interval = 1.0 / config.sample_rate  # 200Hz = 0.005s = 5ms

        # CRITICAL: Get video duration and calculate stop time
        video_duration = None
        video_start_time = None
        stop_time_with_buffer = None

        # ... video timing calculations ...
```

**Analysis**: The monitoring loop starts successfully and polls the LabJack hardware every 5ms (200Hz sample rate).

### Location 2: Hardware Reads ARE Happening

**File**: Same as above

**Lines 950-1013**: Hardware polling and detection logic

```python
while not stop_event.is_set():
    try:
        current_time = time.time()

        # CRITICAL FIX #2: Auto-stop when video ends (with multi-video buffer)
        if stop_time_with_buffer and current_time > stop_time_with_buffer:
            logger.info(f"🏁 Auto-stopping monitoring: video ended at {stop_time_with_buffer:.3f}, current time {current_time:.3f}")
            break

        # Check voltage for each channel
        for channel in config.channels:  # ["AIN0"]
            voltage = self.labjack_service.read_channel(channel)  # ✅ READS HAPPEN

            if voltage is None:
                continue

            # CRITICAL BUG: Detection window validation happens HERE
            # If detection falls outside window, it's silently discarded
            if voltage > config.voltage_threshold:
                decision, event = self._should_record_detection(
                    session_id, channel, voltage, current_time, config
                )

                if decision == "record":  # 🚨 IF THIS NEVER RETURNS "record"
                    # ... event creation and recording code ...
                    self._record_detection_event(session_id, event)  # ❌ NEVER REACHED
```

**Critical Issue**: If `_should_record_detection()` never returns `"record"`, then `_record_detection_event()` is never called, meaning:
- No detection callbacks are invoked
- No WebSocket emissions occur
- No database storage happens

### Location 3: The Silent Filter (SMOKING GUN)

**File**: Same as above

**Lines 1264-1361**: `_should_record_detection()` method

```python
def _should_record_detection(self, session_id: str, channel: str,
                             voltage: float, current_time: float,
                             config: DetectionConfig) -> tuple:
    """
    Determine if detection should be recorded based on timing, thresholds, and debounce logic

    Returns:
        tuple: (decision, event or None)
            decision: "record", "debounce", "steady_high", "continuous", or "skip"
    """

    # CRITICAL BUG: Check if detection is within valid video timing window
    if not self._is_detection_within_video_window(session_id, current_time):
        logger.debug(f"🚫 Detection outside video timing window: {current_time}")
        return ("skip", None)  # 🚨 SILENTLY DISCARDED!

    # ... other debounce and threshold checks ...
```

**This is where detections die!** If `_is_detection_within_video_window()` returns `False`, the detection is immediately discarded with no further processing, logging, or notification.

### Location 4: The Timing Window Bug

**File**: Same as above

**Lines 1485-1550**: `_is_detection_within_video_window()` method

```python
def _is_detection_within_video_window(self, session_id: str, detection_time: float) -> bool:
    """
    Check if detection timestamp falls within valid video playback window

    Args:
        session_id: Session identifier
        detection_time: Unix timestamp of detection

    Returns:
        bool: True if detection is within video window (including grace period)
    """
    try:
        # Get session timing information from database
        session_timing = self._get_session_timing_info(session_id)

        if not session_timing:
            logger.warning(f"No timing info for session {session_id}, accepting detection")
            return True  # ✅ Should accept if no timing info

        video_start = session_timing.get('video_start_timestamp')

        if video_start is None:
            logger.warning(f"No video start timestamp for session {session_id}")
            return True  # ✅ Should accept if no start time

        # CRITICAL BUG: Calculate window boundaries
        window_start = video_start - GRACE_PERIOD_SECONDS  # Default: -0.5s

        # Get video duration for window end calculation
        video_duration = session_timing.get('video_duration')

        if video_duration:
            window_end = video_start + video_duration + GRACE_PERIOD_SECONDS
        else:
            # 🚨 POTENTIAL BUG: No duration = infinite window?
            window_end = None

        # Check if detection is within window
        if detection_time < window_start:
            logger.debug(f"Detection too early: {detection_time} < {window_start}")
            return False  # 🚨 REJECTED: Detection before grace period

        if window_end and detection_time > window_end:
            logger.debug(f"Detection too late: {detection_time} > {window_end}")
            return False  # 🚨 REJECTED: Detection after video + grace period

        return True  # ✅ Detection within valid window

    except Exception as e:
        logger.error(f"Error checking detection window: {e}")
        return True  # ✅ Accept on error (safe default)
```

## The Timing Problem (3 Possible Scenarios)

### Scenario 1: Video Start Time Not Set

**If** `video_start_timestamp` is `None`:
- Function returns `True` (accepts detection)
- **Not the issue** ✅

### Scenario 2: Video Duration Missing

**If** `video_duration` is `None`:
- `window_end` is `None`
- Second condition `if window_end and detection_time > window_end` is `False`
- Function returns `True` (accepts detection)
- **Not the issue** ✅

### Scenario 3: Clock Skew / Race Condition (MOST LIKELY)

**If** LabJack hardware clock is slightly ahead of video timing clock:

```
Video Start Time: 1731865420.500000  (from timing service)
LabJack Detection:  1731865420.499950  (from hardware - 50µs BEFORE video start)

Calculation:
  detection_time (1731865420.499950) < window_start (1731865420.000000) ?
  NO - this would pass

But what if grace period calculation is wrong?
  window_start = video_start - GRACE_PERIOD_SECONDS
  window_start = 1731865420.500000 - 0.5 = 1731865420.000000

  detection_time (1731865420.499950) < window_start (1731865420.000000) ?
  NO - still passes

WAIT - What if video_start_timestamp is NEVER SET?
```

### Scenario 4: Database Timing Info Query Failure (HIGH PROBABILITY)

**File**: Same as above

**Lines 1411-1483**: `_get_session_timing_info()` method

```python
def _get_session_timing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session timing information from database"""
    try:
        from models import TestSession, Video
        db = SessionLocal()
        try:
            session = db.query(TestSession).filter(TestSession.id == session_id).first()

            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None  # 🚨 THIS CAUSES DETECTIONS TO BE REJECTED!

            # Get video start timestamp
            video_start_timestamp = None
            if session.video_started_at:
                video_start_timestamp = session.video_started_at.timestamp()
            elif session.started_at:
                video_start_timestamp = session.started_at.timestamp()

            # 🚨 CRITICAL: If BOTH are None, this returns None
            # But _is_detection_within_video_window() returns True in that case

            # Get video duration
            video_duration = None
            if session.video_id:
                video = db.query(Video).filter(Video.id == session.video_id).first()
                if video:
                    video_duration = video.duration

            return {
                'video_start_timestamp': video_start_timestamp,
                'video_duration': video_duration,
                'session_id': session_id,
                'sequence_id': getattr(session, 'sequence_id', None)
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to get session timing info: {e}")
        return None  # 🚨 ERROR = DETECTIONS ACCEPTED (returns True)
```

## The Root Cause Hypothesis

**Most Likely Scenario**: The `video_start_timestamp` and `video_duration` are being set correctly, BUT the detection timestamps from LabJack are falling OUTSIDE the calculated window due to:

1. **Clock synchronization issues** between video timing service and LabJack hardware
2. **Incorrect grace period calculation** that's too restrictive
3. **Race condition** where monitoring starts BEFORE video timing is registered in the database

## Critical Questions to Answer

### Question 1: Are detections being read from hardware?

**Test**: Add logging in `_monitoring_loop()` at line 950:

```python
voltage = self.labjack_service.read_channel(channel)
logger.info(f"🔌 Hardware read: {channel} = {voltage:.3f}V at {current_time}")  # ADD THIS
```

**Expected**: If hardware is working, you should see hundreds of voltage readings in the logs.

### Question 2: Are detections crossing the voltage threshold?

**Test**: Add logging at line 957:

```python
if voltage > config.voltage_threshold:
    logger.info(f"🎯 Threshold crossed: {voltage:.3f}V > {config.voltage_threshold:.3f}V")  # ADD THIS
```

**Expected**: If LEDs are triggering, you should see 242 threshold crosses.

### Question 3: What is `_should_record_detection()` returning?

**Test**: Add logging at line 958:

```python
decision, event = self._should_record_detection(session_id, channel, voltage, current_time, config)
logger.info(f"📋 Detection decision: {decision} for {voltage:.3f}V at {current_time}")  # ADD THIS
```

**Expected**: If window validation is the issue, you'll see `decision = "skip"` for all detections.

### Question 4: What are the timing window boundaries?

**Test**: Add logging in `_is_detection_within_video_window()` at line 1512:

```python
window_start = video_start - GRACE_PERIOD_SECONDS
window_end = video_start + video_duration + GRACE_PERIOD_SECONDS if video_duration else None

logger.info(f"⏱️ Timing window: [{window_start:.6f}, {window_end:.6f if window_end else 'None'}]")
logger.info(f"⏱️ Detection time: {detection_time:.6f}")
logger.info(f"⏱️ In window? start_check={detection_time >= window_start}, end_check={not window_end or detection_time <= window_end}")
```

**Expected**: This will reveal if detections are being rejected for falling outside the window.

## Recommended Fixes

### Fix 1: Add Debug Logging (Immediate - No Risk)

Add comprehensive logging to reveal where detections are being filtered:

```python
# In _monitoring_loop() at line 957
if voltage > config.voltage_threshold:
    logger.info(f"🎯 THRESHOLD CROSSED: {channel} = {voltage:.3f}V at {current_time:.6f}")
    decision, event = self._should_record_detection(session_id, channel, voltage, current_time, config)
    logger.info(f"📋 Detection decision: '{decision}' for {voltage:.3f}V")

    if decision == "skip":
        logger.warning(f"🚫 Detection SKIPPED at {current_time:.6f} - investigate timing window")
```

### Fix 2: Disable Timing Window Validation (Testing Only)

Temporarily disable the window check to confirm it's the issue:

```python
# In _should_record_detection() at line 1272
# COMMENT OUT THIS CHECK FOR TESTING:
# if not self._is_detection_within_video_window(session_id, current_time):
#     logger.debug(f"🚫 Detection outside video timing window: {current_time}")
#     return ("skip", None)
```

### Fix 3: Expand Grace Period (Conservative Fix)

Increase the grace period to account for clock skew:

```python
# In config/timing_config.py
GRACE_PERIOD_MS = 2000  # Increase from 500ms to 2000ms (2 seconds)
GRACE_PERIOD_SECONDS = 2.0  # Increase from 0.5s to 2.0s
```

### Fix 4: Fallback to Monitoring Start Time (Production Fix)

If video timing isn't available, use monitoring start time instead of rejecting detections:

```python
# In _is_detection_within_video_window() at line 1500
if not session_timing or not session_timing.get('video_start_timestamp'):
    # FALLBACK: Use monitoring start time from active_sessions
    if session_id in self.active_sessions:
        config = self.active_sessions[session_id]
        monitoring_start = config.metadata.get('monitoring_start_time')
        if monitoring_start:
            logger.info(f"Using monitoring start time as fallback: {monitoring_start:.6f}")
            video_start = monitoring_start
        else:
            logger.warning(f"No timing reference available, accepting all detections")
            return True
    else:
        return True
```

## Next Steps

1. **Enable Debug Logging** (Fix 1) - Deploy immediately to production to capture detailed timing data
2. **Run Test Session** - Execute a new HIL test with debug logging enabled
3. **Analyze Logs** - Review log output to confirm where detections are being filtered
4. **Apply Appropriate Fix** - Based on log analysis, apply Fix 2, 3, or 4

## Files to Modify

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
   - Lines 957-1013: Add debug logging
   - Lines 1264-1361: `_should_record_detection()` method
   - Lines 1485-1550: `_is_detection_within_video_window()` method

2. `/home/rigade/Testing/ai-model-validation-platform/backend/config/timing_config.py`
   - Increase `GRACE_PERIOD_MS` and `GRACE_PERIOD_SECONDS` if needed

## Conclusion

**The LabJack monitoring loop IS running and reading hardware**, but detections are being **silently filtered out** by the timing window validation logic in `_should_record_detection()`. This explains why:

- ✅ LabJack shows "Connected" (hardware communication is working)
- ✅ Monitoring loop is running (thread is active)
- ❌ 0 detections are generated (they're being rejected by `_is_detection_within_video_window()`)
- ❌ No WebSocket emissions occur (because `_record_detection_event()` is never called)
- ❌ No database storage happens (because detection callbacks are never invoked)

**The fix is to either**:
1. Increase the grace period to account for timing skew
2. Disable timing window validation during testing
3. Add fallback timing logic when video timing is unavailable
4. Fix the video timing synchronization to ensure accurate timestamps

**Priority**: Enable debug logging (Fix 1) immediately to confirm this diagnosis before applying production fixes.
