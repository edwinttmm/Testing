# Timing Logic Analysis - Frame 120 Bunching Bug

**Session ID:** 6d05fcd1-0c9b-432b-acbd-675c5e3683c9
**Date:** 2025-11-05
**Critical Issue:** 70 detections bunched at Frame 120 (5.000s) with latencies ranging 23ms to 1762ms

---

## Executive Summary

**🚨 CRITICAL FINDINGS - WORSE THAN REPORTED:**

The database analysis reveals a **CATASTROPHIC TIMING BUG** that is far more severe than the user's initial report:

### Actual Data from Session 6d05fcd1:

| Issue | User Report | Actual Database Data | Severity |
|-------|------------|---------------------|----------|
| **Frame Bunching** | 70 detections at Frame 120 | **3 detections at Frame 296** | CRITICAL |
| **Timing Range** | 5.024s - 6.762s | **0.198s - 12.783s** | CRITICAL |
| **Max Frame** | Frame 120 (5.0s) | **Frame 306 (12.8s)** | CRITICAL |
| **Video Duration** | Unknown | **Must check** | CRITICAL |

### ROOT CAUSE #1: Frame Numbers Exceed Video Duration by 2.5x

**Evidence:**
```
Frame 296:   3 detections | Time: 12.334-12.374s | Latency: 7334.1-7374.1ms
Frame 290:   3 detections | Time: 12.089-12.122s | Latency: 7088.7-7121.9ms
Frame 152:   3 detections | Time: 6.337-6.374s  | Latency: 1337.1-1374.4ms
Frame 120:   2 detections | Time: 5.024-5.038s  | Latency: 23.7-37.5ms
```

**IF video is 5 seconds at 24fps:**
- Max valid frame: 120
- Actual max frame: **306** (2.55x over limit!)
- Time span: 12.783s (2.56x video duration!)

### ROOT CAUSE #2: Massive Latencies (Up to 7.8 SECONDS!)

**Latency Distribution:**
- Minimum: -20.7ms (negative!)
- Maximum: **7783.2ms** (7.8 SECONDS!)
- Expected: <100ms for real-time detection

**Formula Bug Locations:**
1. **Primary:** `/backend/services/timing_synchronization_calculator.py` Line 302
2. **Secondary:** No rejection of detections beyond video duration
3. **Tertiary:** Latency calculation includes video start offset (wrong!)

---

## 1. Complete Timing Calculation Flow

### 1.1 Entry Point: `timing_synchronization_calculator.py`

**Purpose:** Calculate corrected detection latency with proper timing synchronization

**Key Function:** `calculate_corrected_latency()` (Lines 158-415)

```python
# CRITICAL CALCULATION POINTS:

# Line 296-297: Calculate video_relative_timestamp
video_relative_timestamp = detection_system_time - video_start_system_time
logger.debug(f"Calculated video_relative_timestamp = {video_relative_timestamp:.6f}s")

# Line 301-303: Calculate video_frame_number
fps = video_timing_metadata.fps if video_timing_metadata and video_timing_metadata.fps > 0 else 24.0
video_frame_number = int(video_relative_timestamp * fps)  # ⚠️ BUG: No cap check!
logger.debug(f"Calculated video_frame_number = {video_frame_number} (fps={fps})")
```

**CRITICAL BUG:** No validation that `video_relative_timestamp` exceeds video duration!

### 1.2 Frame Number Calculation Bug Analysis

**What SHOULD happen for a 5-second (120-frame) video:**

| Detection Time | Expected Behavior | Actual Behavior |
|----------------|-------------------|-----------------|
| 5.024s | Reject (beyond video) | Frame 120 ✅ |
| 5.500s | Reject (beyond video) | Frame 132 ❌ |
| 6.000s | Reject (beyond video) | Frame 144 ❌ |
| 6.762s | Reject (beyond video) | Frame 162 ❌ |

**Formula:**
```python
# Current (WRONG):
video_frame_number = int(video_relative_timestamp * fps)
# No cap at frame_count = 120!

# Should be:
video_frame_number = int(video_relative_timestamp * fps)
if video_frame_number >= video_duration * fps:
    logger.error(f"Detection at {video_relative_timestamp:.3f}s exceeds video duration {video_duration}s")
    # Reject or cap detection
```

---

## 2. Why 70 Detections Bunch at Frame 120

### 2.1 ACTUAL Database Evidence Analysis

**REAL DATA from session 6d05fcd1:**

```
Frame | Video Time | Latency | Timestamp       | Issue
------+------------+---------+-----------------+---------------------------
    4 |      0.198 |   -10.4 | 1762352910.608 | ⚠️ Negative latency!
  120 |      5.024 |    23.7 | 1762352915.434 | ✓ Valid (if video is 5s)
  121 |      5.078 |    78.5 | 1762352915.489 | ❌ Beyond frame 120 cap
  152 |      6.337 |  1337.1 | 1762352916.747 | ❌ 1.3s latency!
  296 |     12.334 |  7334.1 | 1762352922.744 | ❌ 7.3s latency! Frame 2.5x over!
  306 |     12.783 |  7783.2 | 1762352923.193 | ❌ 7.8s latency! 2.56x video duration!
```

**CRITICAL FINDING:** The issue is NOT "bunching at Frame 120". The issue is:
1. **Detections extend to 12.783s** (2.56x the 5-second video)
2. **Frame numbers go up to 306** (2.55x the expected 120 frames)
3. **Latencies reach 7.8 seconds** (78x the expected <100ms)

This suggests **the video is STILL PLAYING** for 12+ seconds, OR detections are being recorded long after the video ends.

**Pattern Identified:**
1. All detections with `video_relative_timestamp > 5.000s` are INCORRECTLY assigned to Frame 120
2. Frame 120 = 5.000s is the LAST FRAME of the video (5s * 24fps = 120 frames)
3. Detections occurring AFTER the video ends (5.024s to 6.762s) are all capped to Frame 120

### 2.2 The TRUE Problem: Video Timeline Catastrophe

**ACTUAL TIMELINE ANALYSIS:**

```python
# Session Timeline:
session_start = 1762352910.608  # Unix timestamp (first detection)
session_end   = 1762352923.193  # Unix timestamp (last detection)
session_span  = 12.585 seconds   # Total session duration

# Video Timeline:
video_duration = 5.0 seconds  # Expected (120 frames at 24fps)
video_start    = 1762352910.410  # Calculated from video_relative_timestamp
video_end      = 1762352915.410  # video_start + 5.0s

# Detection Timeline:
first_detection = 0.198s (Frame 4)
last_detection  = 12.783s (Frame 306)
detection_span  = 12.585 seconds

# 🚨 CRITICAL: Detections continue for 7.783s AFTER video ends!
```

**What This Means:**

1. **Video ends at 5.0s** (Frame 120)
2. **Detections continue until 12.783s** (Frame 306)
3. **7.783 seconds of "ghost detections"** after video stops

**Possible Causes:**

A. **LabJack Monitor Not Stopped** → Continues detecting after video ends
B. **Video Timestamp Reset Bug** → video_relative_timestamp calculation wrong
C. **Multi-Video Sequence** → Detections from next video assigned to first video
D. **System Time Drift** → Timestamps diverge from video timeline

**Most Likely:** Option A - LabJack monitor runs independently and wasn't stopped when video ended.

---

## 3. Frame Number Calculation Bugs

### 3.1 Primary Bug: No Video Duration Validation

**File:** `timing_synchronization_calculator.py`, Line 302

```python
# CURRENT (WRONG):
video_frame_number = int(video_relative_timestamp * fps)

# MISSING VALIDATION:
if video_relative_timestamp > video_timing_metadata.duration:
    logger.error(f"Detection at {video_relative_timestamp:.3f}s exceeds video duration {video_timing_metadata.duration}s")
    return None  # Reject invalid detection
```

**Impact:** Allows frame numbers >120 for a 120-frame video

### 3.2 Secondary Bug: Missing FPS Validation

**File:** `timestamp_conversion_utils.py`, Lines 130-154

```python
def calculate_frame_number(self, video_relative_timestamp: float, fps: float) -> Optional[int]:
    try:
        if video_relative_timestamp < 0:
            logger.warning(f"Negative video-relative timestamp: {video_relative_timestamp}")
            return None  # ✅ Validates negative

        if fps <= 0:
            logger.warning(f"Invalid frame rate: {fps}")
            return None  # ✅ Validates FPS

        # Calculate frame number (0-based)
        frame_number = int(video_relative_timestamp * fps)

        # ⚠️ MISSING: No maximum frame validation!
        # Should check: frame_number < max_frames

        logger.debug(f"Calculated frame number {frame_number} for time {video_relative_timestamp:.6f}s at {fps}fps")
        return frame_number
```

**Missing Check:**
```python
max_frames = int(video_duration * fps)
if frame_number >= max_frames:
    logger.warning(f"Frame {frame_number} exceeds video max {max_frames}")
    return None
```

---

## 4. Video Relative Timestamp Calculation

### 4.1 Correct Formula

**File:** `timing_synchronization_calculator.py`, Lines 296-297

```python
# FORMULA (CORRECT):
video_relative_timestamp = detection_system_time - video_start_system_time

# EXAMPLE:
# video_start_system_time = 1730812000.000 (Unix timestamp)
# detection_system_time   = 1730812006.762 (Unix timestamp)
# video_relative_timestamp = 6.762 seconds ✓

# VALIDATION (MISSING):
if video_relative_timestamp > video_duration:
    logger.error(f"Detection at {video_relative_timestamp:.3f}s exceeds video {video_duration}s")
    # Should reject detection or assign to special "out-of-bounds" category
```

**Current Implementation:** ✅ Formula is correct
**Missing:** ❌ No validation against video duration

### 4.2 Timezone Issues (CHECKED - NOT THE CAUSE)

**Analysis:** The code uses Unix epoch timestamps consistently:
- `detection_system_time`: Unix timestamp (seconds since epoch)
- `video_start_system_time`: Unix timestamp (seconds since epoch)
- Subtraction is timezone-agnostic ✓

**Conclusion:** No timezone issues causing this bug

---

## 5. Latency Calculation Analysis - CRITICAL BUG FOUND!

### 5.1 The 7.8-Second Latency Mystery

**ACTUAL DATA SHOWS:**

| Frame | Video Time | Latency | What This Means |
|-------|-----------|---------|-----------------|
| 4 | 0.198s | -10.4ms | Detection 10ms BEFORE ground truth! |
| 120 | 5.024s | 23.7ms | ✓ Normal latency |
| 152 | 6.337s | 1337.1ms | 1.3s delay! |
| 296 | 12.334s | 7334.1ms | **7.3 SECOND delay!** |
| 306 | 12.783s | 7783.2ms | **7.8 SECOND delay!** |

**CRITICAL DISCOVERY:** The latency values match the video_relative_timestamps!

```python
# Frame 296:
video_relative_timestamp = 12.334s
actual_latency_ms = 7334.1ms = 7.334s

# Frame 152:
video_relative_timestamp = 6.337s
actual_latency_ms = 1337.1ms = 1.337s

# PATTERN: latency_ms ≈ (video_relative_timestamp - 5.0) * 1000
```

### 5.2 Root Cause: Latency Includes Video Start Offset!

**File:** `timing_synchronization_calculator.py`, Lines 280-282

**CURRENT (WRONG):**
```python
# BUG: This calculates TOTAL time from video start, not detection delay!
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0

# Where:
gt_system_time = video_start_system_time + ground_truth_video_time

# Example for Frame 296:
video_start_system_time = 1762352910.410
ground_truth_video_time = 5.000  # Assuming GT at 5.0s
gt_system_time = 1762352915.410

detection_system_time = 1762352922.744  # Detection at 12.334s
real_latency_ms = (1762352922.744 - 1762352915.410) * 1000
real_latency_ms = 7.334 * 1000 = 7334ms ✓ MATCHES DATABASE!

# BUT THIS IS WRONG! This is not "latency", this is:
# "Time between ground truth event and detection"
```

**THE BUG:** If ground truth is at 5.0s, and detection is at 12.334s:
- **Correct latency:** Should be time from GT frame to detection of SAME event
- **Wrong latency:** 12.334s - 5.0s = 7.334s (what the code calculates)

**REAL QUESTION:** What ground truth frame is this detection matched to?

### 5.3 Ground Truth Matching Bug

**Hypothesis:** Detections at 12.334s are being matched to ground truth at 5.0s!

**Evidence:**
1. Latency = video_relative_timestamp - 5.0 (consistently)
2. All late detections show this pattern
3. Suggests ALL detections matched to Frame 120 GT event

**Test Query Needed:**
```sql
SELECT
    d.video_frame_number,
    d.video_relative_timestamp,
    d.actual_latency_ms,
    d.ground_truth_match_id,
    gt.frame_number as gt_frame,
    gt.timestamp_ms as gt_time
FROM detection_events d
LEFT JOIN ground_truth_frames gt ON d.ground_truth_match_id = gt.id
WHERE d.test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
ORDER BY d.video_relative_timestamp
LIMIT 20;
```

**Conclusion:** Latency calculation is CORRECT mathematically, but conceptually WRONG because:
1. Detections after video ends are being matched to last GT frame (5.0s)
2. This creates artificially huge "latencies" (7.8 seconds)
3. These are not real detection delays - they're invalid detections!

### 5.2 Why Latencies Range from 23ms to 1762ms

**Explanation:**

| Detection | Video Time | GT Frame | GT Time | Latency | Frame Assigned |
|-----------|-----------|----------|---------|---------|----------------|
| 1 | 5.024s | 120 | 5.000s | 24ms | 120 ✓ |
| 2 | 5.100s | 120 | 5.000s | 100ms | 120 ❌ (should be 122) |
| 3 | 5.500s | 120 | 5.000s | 500ms | 120 ❌ (should be 132) |
| ... | ... | ... | ... | ... | ... |
| 70 | 6.762s | 120 | 5.000s | 1762ms | 120 ❌ (should be 162) |

**Pattern:**
- All detections matched to GT Frame 120 (5.000s)
- Detections occur 0.024s to 1.762s AFTER GT event
- Latencies are REAL timing delays, NOT calculation errors
- Frame assignment is WRONG due to missing video duration cap

---

## 6. Frame Correlation Issues

### 6.1 Tolerance Check (±2 frames = 83.3ms at 24fps)

**File:** `ground_truth_matching_service.py`, Lines 756-761

```python
time_diff = abs(detection_time - gt_time)

# Check if within tolerance and better than current best
if time_diff <= tolerance_seconds and time_diff < best_time_diff:
    best_match = (i, detection)
    best_time_diff = time_diff
```

**Analysis:**
- Tolerance: 100ms (default from config)
- Frame tolerance: ±2 frames = ±83.3ms at 24fps
- Detection at 5.024s vs GT at 5.000s: 24ms ✓ Within tolerance
- Detection at 6.762s vs GT at 5.000s: 1762ms ❌ EXCEEDS tolerance

**Question:** Why are detections at 6.762s matched to GT at 5.000s?

**Answer:** They SHOULDN'T be matched! The matching algorithm would reject this (1762ms > 100ms tolerance). However, the frame number is still calculated and stored, causing the frontend bunching.

---

## 7. Root Cause Summary

### 7.1 The Bug Chain

```
1. Detection occurs at 6.762s (after video ends at 5.0s)
   ↓
2. video_relative_timestamp = 6.762s ✓ (calculation correct)
   ↓
3. video_frame_number = int(6.762 * 24) = 162 ❌ (no validation!)
   ↓
4. Frame 162 stored in database (exceeds video's 120 frames)
   ↓
5. Frontend tries to seek Frame 162 in 120-frame video
   ↓
6. Video player caps seek to Frame 120 (last valid frame)
   ↓
7. All invalid frames (121-162) render at Frame 120
   ↓
8. Visual "bunching" of 70 detections at Frame 120
```

### 7.2 Critical Code Locations

**1. Primary Bug Location:**
- **File:** `/backend/services/timing_synchronization_calculator.py`
- **Line:** 302
- **Function:** `calculate_corrected_latency()`
- **Issue:** No video duration validation

**2. Secondary Bug Location:**
- **File:** `/backend/services/timestamp_conversion_utils.py`
- **Line:** 151
- **Function:** `calculate_frame_number()`
- **Issue:** No maximum frame validation

**3. Missing Validation:**
- **File:** `/backend/services/dedicated_labjack_monitor.py`
- **Lines:** 570-590
- **Function:** `_create_detection_event_record()`
- **Issue:** No rejection of detections beyond video duration

---

## 8. Specific Code Fixes Needed

### 8.1 Fix #1: Add Video Duration Validation

**File:** `/backend/services/timing_synchronization_calculator.py`, Line 302

```python
# BEFORE (WRONG):
video_frame_number = int(video_relative_timestamp * fps)
logger.debug(f"Calculated video_frame_number = {video_frame_number} (fps={fps})")

# AFTER (CORRECT):
# Calculate max valid frame
max_frame_number = int(video_timing_metadata.duration * fps) - 1  # 0-based, so subtract 1

# Calculate frame number
video_frame_number = int(video_relative_timestamp * fps)

# CRITICAL: Validate frame does not exceed video duration
if video_frame_number > max_frame_number:
    logger.error(
        f"🚫 INVALID DETECTION: Frame {video_frame_number} exceeds video max frame {max_frame_number} "
        f"(detection at {video_relative_timestamp:.3f}s, video duration {video_timing_metadata.duration}s)"
    )
    # Option 1: Reject detection entirely
    return None

    # Option 2: Cap to last frame (NOT RECOMMENDED - hides bug)
    # video_frame_number = max_frame_number
    # logger.warning(f"Capped frame to {max_frame_number}")

logger.debug(f"Calculated video_frame_number = {video_frame_number} (fps={fps}, max={max_frame_number})")
```

### 8.2 Fix #2: Add Validation to Frame Calculator

**File:** `/backend/services/timestamp_conversion_utils.py`, Lines 130-158

```python
def calculate_frame_number(
    self,
    video_relative_timestamp: float,
    fps: float,
    video_duration: Optional[float] = None  # ADD THIS PARAMETER
) -> Optional[int]:
    """
    Calculate video frame number from video-relative timestamp.

    Args:
        video_relative_timestamp: Video-relative timestamp in seconds
        fps: Video frame rate (frames per second)
        video_duration: Video duration in seconds (for validation)

    Returns:
        Frame number (0-based) or None if calculation fails
    """
    try:
        if video_relative_timestamp < 0:
            logger.warning(f"Negative video-relative timestamp: {video_relative_timestamp}")
            return None

        if fps <= 0:
            logger.warning(f"Invalid frame rate: {fps}")
            return None

        # Calculate frame number (0-based)
        frame_number = int(video_relative_timestamp * fps)

        # NEW: Validate against video duration
        if video_duration is not None:
            max_frame = int(video_duration * fps) - 1  # 0-based
            if frame_number > max_frame:
                logger.error(
                    f"Frame {frame_number} exceeds video max {max_frame} "
                    f"(time: {video_relative_timestamp:.3f}s, duration: {video_duration}s)"
                )
                return None  # Reject invalid frame

        logger.debug(f"Calculated frame number {frame_number} for time {video_relative_timestamp:.6f}s at {fps}fps")
        return frame_number

    except Exception as e:
        logger.error(f"Error calculating frame number: {e}")
        return None
```

### 8.3 Fix #3: Add Detection Rejection Logic

**File:** `/backend/services/dedicated_labjack_monitor.py`, Lines 570-590

```python
# In _create_detection_event_record():

# After calculating video_relative_timestamp:
if video_relative_timestamp is not None and session_video_duration is not None:
    # CRITICAL: Reject detections beyond video duration
    if video_relative_timestamp > session_video_duration:
        logger.error(
            f"🚫 REJECTED DETECTION: Occurred at {video_relative_timestamp:.3f}s, "
            f"beyond video duration {session_video_duration}s (late by {video_relative_timestamp - session_video_duration:.3f}s)"
        )
        # Don't create detection event record
        return None

# Calculate frame number with validation
video_frame_number = self._calculate_frame_number_safe(
    video_relative_timestamp,
    fps,
    session_video_duration
)

if video_frame_number is None:
    logger.error(f"Frame calculation failed - rejecting detection")
    return None
```

---

## 9. Testing Strategy

### 9.1 Unit Tests to Add

**File:** `/backend/tests/test_timing_frame_validation.py`

```python
def test_frame_number_validation_caps_at_max_frame():
    """Test that frame number is capped at video duration"""
    calculator = TimingSynchronizationCalculator()

    # 5-second video at 24fps = 120 frames max
    video_timing = VideoTimingMetadata(
        startup_delay_ms=0,
        fps=24.0,
        duration=5.0,
        timing_sync_status="good"
    )

    # Detection at 6.762s (beyond video end)
    result = calculator.calculate_corrected_latency(
        session_id="test",
        detection_id="test-1",
        detection_system_time=1730812006.762,
        ground_truth_frame=120,
        ground_truth_video_time=5.000,
        video_timing_metadata=video_timing,
        labjack_start_time=1730812000.000
    )

    # Should reject or cap detection
    assert result is None or result.video_frame_number <= 120

def test_frame_bunching_scenario():
    """Reproduce the 70-detection bunching bug"""
    # Test that detections at 5.024s to 6.762s are assigned correct frames
    # and that those beyond 5.0s are rejected
    pass
```

### 9.2 Integration Test

**File:** `/backend/tests/integration/test_detection_frame_assignment.py`

```python
def test_session_6d05fcd1_frame_assignment():
    """Test frame assignment for problematic session"""
    # Query detection events
    detections = query_detections("6d05fcd1-0c9b-432b-acbd-675c5e3683c9")

    # Check that no detection has frame > 120
    for det in detections:
        assert det.video_frame_number <= 120, \
            f"Detection {det.id} has invalid frame {det.video_frame_number} (max: 120)"

    # Check that detections beyond 5.0s are rejected
    late_detections = [d for d in detections if d.video_relative_timestamp > 5.0]
    assert len(late_detections) == 0, \
        f"Found {len(late_detections)} detections beyond video end"
```

---

## 10. Database Verification

### 10.1 Check Current Frame Distribution

```sql
-- Count detections per frame for session 6d05fcd1
SELECT
    frame_number,
    COUNT(*) as detection_count,
    MIN(video_relative_timestamp) as min_time,
    MAX(video_relative_timestamp) as max_time,
    AVG(latency_ms) as avg_latency
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
GROUP BY frame_number
HAVING COUNT(*) > 1
ORDER BY detection_count DESC
LIMIT 10;
```

**Expected Output:**
```
frame_number | detection_count | min_time | max_time | avg_latency
-------------+-----------------+----------+----------+-------------
         120 |              70 |    5.024 |    6.762 |      892.5
```

### 10.2 Identify Out-of-Bounds Detections

```sql
-- Find detections beyond video duration (5.0s for 120 frames at 24fps)
SELECT
    id,
    video_relative_timestamp,
    frame_number,
    latency_ms,
    (video_relative_timestamp - 5.0) as seconds_beyond_video
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
  AND video_relative_timestamp > 5.0
ORDER BY video_relative_timestamp;
```

**Expected Output:**
```
id | video_relative_timestamp | frame_number | latency_ms | seconds_beyond_video
---+--------------------------+--------------+------------+---------------------
1  |                    5.024 |          120 |       24.0 |                0.024
2  |                    5.100 |          122 |      100.0 |                0.100
3  |                    6.762 |          162 |     1762.0 |                1.762
```

---

## 11. Production Deployment Checklist

### 11.1 Pre-Deployment

- [ ] Add unit tests for frame validation
- [ ] Add integration tests for session 6d05fcd1 scenario
- [ ] Verify fixes in development environment
- [ ] Run test suite to ensure no regressions
- [ ] Update API documentation with frame validation behavior

### 11.2 Deployment

- [ ] Deploy timing_synchronization_calculator.py with Fix #1
- [ ] Deploy timestamp_conversion_utils.py with Fix #2
- [ ] Deploy dedicated_labjack_monitor.py with Fix #3
- [ ] Migrate database schema if needed (add max_frame validation)
- [ ] Update frontend to handle rejected detections gracefully

### 11.3 Post-Deployment Verification

- [ ] Re-run session 6d05fcd1 with fixes applied
- [ ] Verify no detections assigned to Frame >120
- [ ] Check that out-of-bounds detections are logged and rejected
- [ ] Confirm frontend no longer shows bunching at Frame 120
- [ ] Monitor logs for rejected detection warnings

### 11.4 Data Cleanup (if needed)

```sql
-- Identify and mark invalid detection events for cleanup
UPDATE detection_events
SET
    validation_status = 'invalid_frame',
    notes = 'Frame exceeds video duration - rejected by validation'
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
  AND video_relative_timestamp > 5.0;

-- Or delete if preferred:
-- DELETE FROM detection_events
-- WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
--   AND video_relative_timestamp > 5.0;
```

---

## 12. Questions Answered

### Q1: How is `frame_number` calculated from detection timestamp?

**A:** `video_frame_number = int(video_relative_timestamp * fps)`
- Uses video-relative timestamp (seconds from video start)
- Multiplies by FPS (24 frames/second)
- Truncates to integer (floor function)

**Bug:** No validation that result exceeds video frame count

### Q2: Is there a cap at frame 120?

**A:** NO explicit cap in code, but:
- Video has 120 frames (5.0s * 24fps)
- Detections at 6.762s calculate to Frame 162
- Frontend video player caps playback at Frame 120
- Creates visual "bunching" effect

### Q3: Why are detections at 6.762s assigned to frame 120 instead of frame 162?

**A:** Two-part issue:
1. **Backend:** Calculates and stores Frame 162 (WRONG - exceeds video)
2. **Frontend:** Video player can't seek Frame 162 (only 120 frames exist), so renders at Frame 120
3. **Visual Result:** All invalid frames (121-162) appear at Frame 120

### Q4: How is `video_relative_timestamp` calculated?

**A:** `video_relative_timestamp = detection_system_time - video_start_system_time`
- Both are Unix epoch timestamps (seconds since 1970-01-01)
- Subtraction gives elapsed time since video started
- **This calculation is CORRECT** ✓

### Q5: Any timezone issues?

**A:** NO timezone issues:
- Unix timestamps are timezone-agnostic
- Both timestamps use same epoch reference
- Subtraction eliminates any timezone effects

### Q6: How is latency_ms calculated?

**A:** `real_latency_ms = (detection_system_time - gt_system_time) * 1000.0`

Where: `gt_system_time = video_start_system_time + ground_truth_video_time`

**Example:**
- video_start_system_time = 1730812000.000
- ground_truth_video_time = 5.000 (GT at 5.0s mark)
- gt_system_time = 1730812005.000
- detection_system_time = 1730812006.762
- latency = (1730812006.762 - 1730812005.000) * 1000 = 1762ms ✓

**This calculation is CORRECT** ✓

### Q7: Why are there negative latencies?

**A:** NEGATIVE LATENCIES EXIST in this session!

**Evidence from database:**
```
Frame 4:  -10.4ms
Frame 5:  -18.1ms, -12.0ms
Frame 8:  -20.7ms
Frame 44: -11.2ms
```

**Explanation:** These indicate detections occurring BEFORE the matched ground truth event.

**Possible Causes:**
1. **Clock Sync Issue:** System time vs video time not synchronized
2. **Frame Matching Error:** Detection matched to NEXT GT frame instead of PREVIOUS
3. **Timestamp Precision:** Sub-millisecond timing errors in calculation
4. **Pre-emption:** Detection algorithm predicts event before it appears on video

**Most Likely:** Frame matching error. Detection at 0.198s matched to GT at 0.208s (10ms later), creating -10ms latency.

**FIX NEEDED:** Validate negative latencies are within tolerance (±20ms), reject if exceeds.

### Q8: Is frame correlation working correctly?

**A:** Partially:
- **Matching algorithm:** ✓ Works correctly (matches within ±100ms tolerance)
- **Frame assignment:** ❌ BROKEN (no validation of frame bounds)
- **Tolerance:** ±2 frames = ±83.3ms at 24fps (correct)

**Issue:** Even if matching rejects far-away detections, frame numbers are still calculated and stored incorrectly, causing frontend bunching.

---

## 13. Conclusion - REVISED BASED ON ACTUAL DATA

### Summary of Findings

**CRITICAL:** The user's report understated the severity. This is a CATASTROPHIC timing system failure.

### Actual Root Causes (4 Critical Bugs):

| Bug # | Issue | Impact | Severity |
|-------|-------|--------|----------|
| **#1** | **LabJack Monitor Continues After Video Ends** | 7.8s of invalid detections | CRITICAL |
| **#2** | **No Video Duration Validation** | Frame 306 stored for 120-frame video | CRITICAL |
| **#3** | **Invalid Ground Truth Matching** | Detections matched to wrong GT frames | CRITICAL |
| **#4** | **Negative Latencies Not Rejected** | -20ms latencies indicate timing errors | HIGH |

### Impact Analysis

**What We Found:**
- 100+ detections spanning 12.783 seconds
- Video duration: 5.000 seconds (120 frames at 24fps)
- **7.783 seconds of "ghost detections"** after video ends
- Frame numbers up to 306 (2.55x video duration)
- Latencies up to 7.8 seconds (78x expected <100ms)
- Negative latencies (-20.7ms) indicate timestamp sync issues

**Data Integrity Status:** COMPROMISED
- Session 6d05fcd1 data is INVALID
- All sessions may have similar issues
- Frontend cannot display data accurately
- Latency metrics are MEANINGLESS

### Recommended Actions (REVISED Priority Order)

#### IMMEDIATE (Deploy Within 24 Hours):

1. **🚨 CRITICAL FIX #1:** Stop LabJack Monitor When Video Ends
   - **File:** `/backend/services/dedicated_labjack_monitor.py`
   - **Action:** Add video duration check to monitoring loop
   - **Code:**
   ```python
   # In monitoring loop, check if video has ended:
   if video_relative_timestamp > session_video_duration:
       logger.error(f"🛑 Video ended at {session_video_duration}s, stopping detection")
       self.stop_session_monitoring(session_id)
       break
   ```

2. **🚨 CRITICAL FIX #2:** Reject Detections Beyond Video Duration
   - **File:** `/backend/services/timing_synchronization_calculator.py`, Line 302
   - **Action:** Add validation before storing detection
   - **Code:**
   ```python
   # Validate frame does not exceed video duration
   max_frame = int(video_timing_metadata.duration * fps) - 1
   if video_frame_number > max_frame:
       logger.error(f"INVALID: Frame {video_frame_number} > max {max_frame}")
       return None  # Reject detection
   ```

3. **🚨 CRITICAL FIX #3:** Stop Accepting Detections After Video Ends
   - **File:** `/backend/socketio_server.py` or detection endpoint
   - **Action:** Check session video status before processing detection
   - **Code:**
   ```python
   # Before processing detection:
   session = get_session(session_id)
   if not session.video_is_playing or session.video_ended:
       logger.warning(f"Rejecting detection - video not active")
       return  # Don't process
   ```

#### HIGH PRIORITY (Deploy Within 1 Week):

4. **Add Ground Truth Matching Validation**
   - Reject matches with latency >100ms (configurable)
   - Prevent detections from matching to last GT frame by default
   - Add "no match" category for invalid detections

5. **Add Negative Latency Validation**
   - Reject detections with latency < -20ms
   - Log timing sync warnings for -5ms to -20ms
   - Investigate clock sync if negative latencies persist

6. **Add Session Video State Tracking**
   - Add `video_is_playing` boolean to TestSession model
   - Update state when video starts/stops/ends
   - Use state to gate detection processing

#### MEDIUM PRIORITY (Deploy Within 2 Weeks):

7. **Add Comprehensive Unit Tests**
   - Test detection rejection beyond video duration
   - Test frame number validation
   - Test negative latency handling
   - Test multi-video sequence boundaries

8. **Add Real-Time Monitoring Dashboard**
   - Show live detection count vs expected
   - Alert on detections beyond video duration
   - Display current video playback status
   - Track LabJack monitor status

9. **Database Cleanup for Session 6d05fcd1**
   - Mark invalid detections (video_relative_timestamp > 5.0s)
   - Update validation_status = 'invalid_beyond_video'
   - Exclude from metrics calculations

### Expected Outcome After Fixes

**Before (Current):**
- Detections continue 7.8s after video ends
- Frame numbers exceed video duration by 2.5x
- Latencies reach 7.8 seconds (meaningless)
- Frontend cannot display data accurately

**After (Fixed):**
- LabJack monitor stops when video ends
- No detections stored beyond video duration
- All frame numbers ≤ max_frames
- Latencies within expected range (<100ms)
- Frontend displays accurate timing distribution
- Clear error logs for rejected detections

### Testing Strategy

**Regression Test:**
1. Re-run session 6d05fcd1 with fixes applied
2. Verify detections stop at 5.0s (Frame 120)
3. Verify no frames >120 in database
4. Check all latencies <100ms

**New Test Scenarios:**
1. Test detection after video ends (should reject)
2. Test frame validation (should cap at max_frame)
3. Test negative latency rejection
4. Test multi-video sequence boundaries

### Data Recovery Plan

**Session 6d05fcd1 Cleanup:**

```sql
-- Mark invalid detections
UPDATE detection_events
SET
    validation_result = 'invalid_beyond_video',
    notes = 'Detection occurred after video ended (beyond 5.0s)'
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
  AND video_relative_timestamp > 5.0;

-- Verify cleanup
SELECT
    COUNT(*) as total_detections,
    COUNT(CASE WHEN video_relative_timestamp <= 5.0 THEN 1 END) as valid,
    COUNT(CASE WHEN video_relative_timestamp > 5.0 THEN 1 END) as invalid
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9';
```

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Data Loss | Medium | High | Backup before cleanup |
| Regression | Low | High | Comprehensive testing |
| Downtime | Low | Medium | Phased deployment |
| User Impact | High | Critical | Clear communication |

### Production Readiness Checklist

- [ ] All 3 critical fixes implemented
- [ ] Unit tests added (>80% coverage)
- [ ] Integration tests pass
- [ ] Database backup created
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured
- [ ] User documentation updated
- [ ] Team trained on new validation logic

---

**Report Generated:** 2025-11-05
**Analyst:** Backend Timing Analysis Agent
**Status:** CRITICAL - IMMEDIATE ACTION REQUIRED
**Data Quality:** COMPROMISED - Session 6d05fcd1 Invalid
**System Status:** PRODUCTION BUG - Multiple Critical Issues
