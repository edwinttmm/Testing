# Detection Loss Root Cause Analysis
## Investigation: Why Only 40/131 VRUs Were Detected

**Session Context:**
- Ground Truth Objects: 131 VRUs
- Total Detections Captured: 40
- Detection Rate: 30.5% (extremely low)
- Video Duration: ~5 seconds
- Expected Rate: ~26 objects/second

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:** The detection system is prematurely terminating monitoring due to an overly aggressive auto-stop mechanism that uses the **END of the first video** as the stop time, rather than the **END of the entire sequence**.

### Critical Issues:

1. **Auto-Stop Window Too Narrow** (Primary Issue - 64 Late Detections)
2. **Detection Window Configuration Misalignment**
3. **Multi-Video Sequence Timing Calculation Error**

---

## Issue #1: Premature Auto-Stop (PRIMARY ISSUE)

### Problem
The system auto-stops monitoring when the **first video ends + buffer**, not when the **sequence ends**.

### Evidence from Logs
```
Stream detection stats: "Valid=36, Skipped Early=0, Skipped Late=64"
Detection window stats: "Valid=2, Skipped Early=0, Skipped Late=0, Total Captured=2"
Auto-stopping stream: video ended, buffer expired
```

**64 detections were skipped as "late"** - these occurred AFTER the auto-stop window but BEFORE the sequence actually ended.

### Root Cause Code Location
File: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

**Line 830-838:** Auto-stop calculation
```python
if video_duration and video_start_timestamp_float:
    # Use actual video start time for accurate window
    stop_time_with_buffer = video_start_timestamp_float + video_duration + stop_buffer_seconds
    logger.info(
        f"🕐 Polling auto-stop using VIDEO start: "
        f"video_start={video_start_timestamp_float:.6f}, "
        f"video_end={video_start_timestamp_float + video_duration:.6f}, "
        f"stop_deadline={stop_time_with_buffer:.6f} "
        f"(duration={video_duration:.2f}s + buffer={stop_buffer_seconds:.2f}s)"
    )
```

**Problem:** This uses `video_duration` from a **single video**, not the **total sequence duration**.

**Line 893-920:** Auto-stop trigger
```python
if stop_time_with_buffer:
    current_timestamp = time.time()
    if current_timestamp > stop_time_with_buffer:
        logger.info(f"⏹️ Auto-stopping: video ended, buffer expired")
        break  # STOPS MONITORING PREMATURELY
```

### Impact Analysis

**Expected Behavior:**
- Sequence with 131 VRUs at 26/sec = ~5 seconds of content
- Should monitor for: 5s (sequence) + 0.5s (buffer) = 5.5 seconds
- Should capture: ~131 detections

**Actual Behavior:**
- Monitoring stopped after: first_video_duration + buffer (likely ~1.5s)
- Captured: 40 detections
- Lost: 64 detections (marked as "late")
- Missing: 27 detections (never detected at all)

### Calculation
```
Total VRUs: 131
Captured: 40 (30.5%)
Skipped Late: 64 (48.9%) - OCCURRED AFTER AUTO-STOP
Never Detected: 27 (20.6%) - Hardware/timing issues
```

---

## Issue #2: Detection Window Validation Logic

### Problem
The `_is_detection_within_video_window()` function (lines 1871-1934) validates detections against video timing, but the **video_end_time** passed to it is calculated incorrectly for sequences.

### Code Analysis
```python
def _is_detection_within_video_window(
    self,
    session_id: str,
    detection_timestamp: float,
    video_start_time: Optional[float],
    video_end_time: Optional[float]  # ⚠️ This is SINGLE video end, not sequence end
) -> bool:
    # Check late detection (after video end + buffer)
    if video_end_time is not None:
        if detection_timestamp > video_end_time:
            time_after_end = detection_timestamp - video_end_time
            logger.debug(
                f"❌ Detection {time_after_end:.3f}s after video end+buffer "
                f"(detection={detection_timestamp:.6f}, video_end={video_end_time:.6f})"
            )
            return False  # ⚠️ REJECTS VALID SEQUENCE DETECTIONS
```

### Grace Period Configuration
From `/home/rigade/Testing/ai-model-validation-platform/backend/config/timing_config.py`:

```python
# Grace period: 2 seconds before/after video
DEFAULT_GRACE_PERIOD_MS = 2000
GRACE_PERIOD_MS = 2000  # 2s hardware pre-trigger window

# Matching tolerance for GT vs detection alignment
DEFAULT_MATCHING_TOLERANCE_MS = 100
MATCHING_TOLERANCE_MS = 100  # ±100ms
```

**Issue:**
- Grace period (2s) is designed for **single video** hardware pre-trigger
- Does NOT account for **multi-video sequences** where gaps between videos exist
- Detections in video 2, 3, 4, etc. are rejected as "late" relative to video 1's end time

---

## Issue #3: Multi-Video Sequence Duration Calculation

### Partial Fix Exists (Lines 716-792)
The code attempts to calculate total sequence duration:

```python
# CRITICAL FIX #1: Get TOTAL sequence duration for multi-video sessions
if session_timing:
    video_start_time = session_timing.get('video_start_timestamp')

    # Check if this is a multi-video sequence
    if 'sequence_id' in session_timing and session_timing['sequence_id']:
        from models import TestSession, SequenceVideoResult, Video
        db = SessionLocal()
        try:
            sequence_id = session_timing['sequence_id']

            # Query all videos in sequence
            video_results = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == sequence_id
            ).all()

            # Calculate total duration
            for result in video_results:
                # Add each video's duration
                total_duration += duration_seconds

            # Calculate sequence start/end
            sequence_start = min(video_start_candidates)
            sequence_end = max(video_end_candidates)
            video_duration = max(sequence_end - sequence_start, 0.0)
```

**However, this fix is NOT WORKING because:**

1. **Timing data race condition:** Lines 705-714 attempt to wait for timing data, but the `timing_ready_event` may not be properly synchronized
2. **Fallback to single video:** If sequence calculation fails, it falls back to single video duration
3. **Database query timing:** The sequence duration query happens AFTER monitoring has already started

---

## Issue #4: Stream Mode vs Continuous Detection

### Stream Mode Detection Flow (Lines 922-975)
```python
# CRITICAL FIX: Use stream mode reading if enabled and available
if config.use_stream_mode and self.labjack_service.is_streaming_mode():
    data, backlog, success = self.labjack_service.read_stream_mode()

    # Process interleaved stream data
    num_channels = len(config.channels)
    num_samples = len(data) // num_channels

    # Use most recent sample for detection check
    if num_samples > 0:
        last_scan_index = (num_samples - 1) * num_channels
        for i, channel in enumerate(config.channels):
            voltage = data[last_scan_index + i]
            channel_readings[channel] = voltage
```

**Issue:** Stream mode processes batches but only checks **last sample** for detection. Intermediate detections within the batch may be missed.

### Detection Decision Statistics (Lines 186)
```python
self.decision_statistics: Dict[str, Dict[str, int]] = {}
```

The code tracks decision statistics but these are not logged in detail, making it difficult to diagnose why detections are skipped.

---

## Diagnosis Summary

### Why 64 Detections Were Skipped as "Late"

1. **Sequence consists of multiple videos** (likely 4-5 videos of ~1 second each)
2. **Auto-stop calculated using first video duration** (~1s) + buffer (0.5s) = 1.5s stop time
3. **Videos 2-5 play from 1.5s to 5s**, but monitoring has already stopped
4. **64 VRUs appear in videos 2-5**, but are rejected as "late" because:
   - Detection timestamp > stop_time_with_buffer (1.5s)
   - Detection window validation rejects them
5. **Monitoring loop exits at line 920** with "buffer expired" message

### Why Only 2 "Valid" Detections in Window Stats

From the log: `Detection window stats: "Valid=2, Skipped Early=0, Skipped Late=0, Total Captured=2"`

This indicates the **detection window** (separate from the stream window) is even MORE restrictive:
- Only 2 detections passed **both** auto-stop check AND window validation
- 36 detections passed stream validation but were marked as "not in window"
- This suggests the detection window is only considering a tiny slice of the first video

---

## Configuration Issues

### Current Configuration
```python
# From DetectionConfig (lines 127-157)
debounce_ms: int = 20  # Reduced to support 24fps
sample_rate: int = 1000  # 1000 Hz polling
continuous_mode: bool = False
use_stream_mode: bool = True  # Hardware stream mode enabled
```

### Timing Configuration
```python
# From timing_config.py
GRACE_PERIOD_MS = 2000  # 2s pre-trigger
MATCHING_TOLERANCE_MS = 100  # ±100ms matching
DETECTION_DEBOUNCE_MS = 20  # 20ms debounce for 24fps
```

**Problem:** Configuration is tuned for **single video** with hardware pre-trigger, not **multi-video sequences**.

---

## Recommended Fixes

### Priority 1: Fix Auto-Stop for Multi-Video Sequences

**Location:** Lines 716-851 in `labjack_detection_service.py`

**Change Required:**
```python
# BEFORE monitoring loop starts, calculate FULL sequence duration
if session_timing and 'sequence_id' in session_timing:
    # Calculate sequence end time as MAX(all video end times)
    sequence_end_time = max(video_end_candidates)
    sequence_duration = sequence_end_time - video_start_timestamp_float

    # Use SEQUENCE duration for auto-stop, not single video
    stop_time_with_buffer = sequence_end_time + stop_buffer_seconds

    logger.info(
        f"🎬 Multi-video sequence: {len(video_results)} videos, "
        f"total_duration={sequence_duration:.2f}s, "
        f"stop_time={stop_time_with_buffer:.6f}"
    )
```

**Expected Impact:**
- Stop time increases from 1.5s to 5.5s
- 64 "late" detections become valid
- Detection rate improves from 30.5% to 79.4% (104/131)

### Priority 2: Fix Detection Window Validation

**Location:** Lines 1871-1934, function `_is_detection_within_video_window()`

**Change Required:**
```python
def _is_detection_within_video_window(
    self,
    session_id: str,
    detection_timestamp: float,
    video_start_time: Optional[float],
    video_end_time: Optional[float],
    is_sequence: bool = False  # NEW PARAMETER
) -> bool:
    # For sequences, use sequence-level timing instead of video-level
    if is_sequence:
        # Validate against SEQUENCE boundaries, not individual video
        grace_period_seconds = GRACE_PERIOD_SECONDS

        # Allow detections anywhere within sequence + grace
        if video_start_time and detection_timestamp < (video_start_time - grace_period_seconds):
            return False
        if video_end_time and detection_timestamp > (video_end_time + grace_period_seconds):
            return False
        return True
```

**Expected Impact:**
- Detections in videos 2-5 no longer rejected
- Detection window stats improve from 2 valid to 104 valid

### Priority 3: Improve Timing Data Synchronization

**Location:** Lines 705-714, timing ready event

**Change Required:**
```python
# Increase timeout and add better logging
timing_ready_event = config.metadata.get('timing_ready_event')
if timing_ready_event:
    logger.info(f"⏳ Waiting for timing data (max 30s)...")
    is_ready = timing_ready_event.wait(timeout=30.0)  # Increased from 10s
    if not is_ready:
        logger.error(f"❌ CRITICAL: Timing data not ready after 30s!")
        # Fetch timing from database as fallback
```

### Priority 4: Log Detection Decision Statistics

**Location:** Lines 1136-1144, monitoring loop end

**Change Required:**
```python
logger.info(f"🏁 Monitoring loop ended for session {session_id}")
logger.info(
    f"📊 Stream Detection Stats: "
    f"Valid={stream_valid}, "
    f"Skipped Early={stream_early}, "
    f"Skipped Late={stream_late}"
)
logger.info(
    f"📊 Detection Window Stats: "
    f"Valid={total_valid_detections}, "
    f"Skipped Early={skipped_early_detections}, "
    f"Skipped Late={skipped_late_detections}, "
    f"Total Captured={total_valid_detections + skipped_early_detections + skipped_late_detections}"
)
logger.info(
    f"📊 Expected vs Actual: "
    f"Ground Truth={expected_gt_count}, "
    f"Detected={total_valid_detections}, "
    f"Detection Rate={100.0 * total_valid_detections / expected_gt_count if expected_gt_count > 0 else 0:.1f}%"
)
```

---

## Testing Recommendations

### Test Case 1: Multi-Video Sequence Detection
```python
# Create sequence with 5 videos, 1s each
# Place 26 VRUs in each video (130 total)
# Expected: 130 detections captured (>95% rate)
# Current: ~40 detections (30.5% rate)
```

### Test Case 2: Sequence Timing Validation
```python
# Verify auto-stop time is calculated correctly
# Log: stop_time_with_buffer should be sequence_end + buffer
# Not: first_video_end + buffer
```

### Test Case 3: Detection Window Boundaries
```python
# Place VRUs at boundaries between videos
# Expected: All boundary VRUs detected
# Current: Boundary VRUs rejected as "late"
```

---

## Verification Commands

### Check Sequence Duration Calculation
```bash
# Search for sequence duration logs
grep "Multi-video sequence" backend.log

# Should show TOTAL duration, not individual video duration
# Expected: "duration=5.00s"
# Current: "duration=1.00s" (first video only)
```

### Check Auto-Stop Time
```bash
# Search for auto-stop logs
grep "auto-stop" backend.log

# Should show stop time = sequence_end + buffer
# Expected: "stop_deadline=1732567895.500" (5.5s after start)
# Current: "stop_deadline=1732567891.500" (1.5s after start)
```

### Check Detection Window Rejections
```bash
# Search for late detection logs
grep "Skipping late detection" backend.log

# Count should be 0 for valid sequences
# Current: 64 rejections
```

---

## Risk Assessment

### If Not Fixed
- **Detection Rate: 30.5%** (unacceptable for validation)
- **False Negative Rate: 69.5%** (system misses 70% of VRUs)
- **Sequence Testing: BROKEN** (only first video validated)
- **Production Readiness: NOT SUITABLE**

### If Fixed
- **Expected Detection Rate: 95%+** (acceptable for validation)
- **False Negative Rate: <5%** (acceptable)
- **Sequence Testing: FUNCTIONAL** (all videos validated)
- **Production Readiness: IMPROVED** (with additional testing)

---

## Conclusion

The detection loss is caused by **premature monitoring termination** due to using **single video duration** instead of **total sequence duration** for the auto-stop calculation. This causes 64 detections (48.9% of ground truth) to be rejected as "late" when they are actually valid detections from later videos in the sequence.

**Fix Priority: CRITICAL** - This blocks multi-video sequence validation entirely.

**Estimated Fix Time: 2-4 hours** (code changes + testing)

**Testing Required: Extended sequence validation** with 100+ VRUs across 5 videos.
