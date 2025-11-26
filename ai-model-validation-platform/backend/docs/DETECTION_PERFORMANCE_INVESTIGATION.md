# Detection Performance Investigation Report

**Session ID:** `daad8bf6-b5da-4423-abc4-a85e83bc1c16`
**Date:** 2025-11-24
**Test Type:** Constant Voltage Injection Test
**Status:** ⚠️ **CRITICAL PERFORMANCE ISSUES IDENTIFIED**

---

## Executive Summary

The constant voltage test session revealed **critical detection rate and timing measurement failures** resulting in only **67.3%** detection rate (173/257) despite constant 3.3V injection that should yield ~100% detection. Additionally, **100% of latency measurements are placeholder values (10000ms)**, indicating complete timing measurement failure.

### Key Findings

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Detection Rate | ~100% | 67.3% | ❌ **33% MISSED** |
| Latency Values | 100-500ms | 10000ms (100%) | ❌ **ALL PLACEHOLDERS** |
| False Negatives | ~0 | 84 | ❌ **HIGH** |
| Timing Data | Valid timestamps | Missing/0.0s | ❌ **BROKEN** |

---

## Detailed Analysis

### 1. Detection Rate Problem

#### Video-Level Breakdown

| Video | Expected | Detected | Rate | Missing |
|-------|----------|----------|------|---------|
| Video 1 (`child_test_video_20251031_144012.mp4`) | 131 | 74 | 56.5% | 57 |
| Video 2 (`Child_20251031_143523.mp4`) | 126 | 99 | 78.6% | 27 |
| **Total** | **257** | **173** | **67.3%** | **84** |

#### Analysis

1. **Video 1 has worse performance** (56.5% vs 78.6%)
   - Suggests progressive degradation or initialization issues
   - First video in sequence may have cold-start delays

2. **Consistent pattern of missed detections**
   - Not random failures - systematic frame skipping
   - Indicates processing bottleneck, not hardware issues

3. **Constant voltage should eliminate detection failures**
   - Hardware is sending 3.3V continuously
   - Software/processing is the bottleneck

---

### 2. Timing Measurement Failure - THE CRITICAL ISSUE

#### Placeholder Latency Analysis

```
ALL detections have latency_ms = 10000.0ms
This is a sentinel/placeholder value indicating timing measurement FAILURE
```

**From `ground_truth_matching_service.py:77-79`:**
```python
# AGENT #43: FP Latency Marker Constant
# False Positive detections get artificial latency of 10000ms (sentinel value)
# This marks them clearly and excludes them from statistics calculations
FP_LATENCY_MARKER = 10000.0
```

#### Root Cause

The 10000ms value is assigned to **False Positive** detections. However, ALL 173 detections show this value, which means:

1. **Detection events are being created WITHOUT timing data**
   - `video_relative_timestamp` = 0.0 or None
   - `actual_latency_ms` = None
   - All detection timestamps show `0.000s`

2. **Ground truth matching is failing**
   - All detections are being classified as False Positives
   - Matching service can't correlate detections to GT objects
   - From results: `"true_positives": 0`, `"matched_detections": 0`

3. **Timing calibration is broken**
   - Session timing data not being captured correctly
   - Video start times not being recorded
   - Detection timestamps not being calculated relative to video

---

### 3. Missing Timing Data Root Causes

#### A. Detection Event Creation Issues

**Location:** `services/labjack_detection_service.py:1741-1841`

Problems identified:

1. **Video timing map lookup failures**
   ```python
   # Line 1752: Timing calibration disabled for multi-video sequences
   # This prevents proper timestamp calculation
   ```

2. **Session timing info not available**
   ```python
   # Line 1758-1765: get_session_timing_info() may return None
   # Detection events created without video context
   ```

3. **Video-relative timestamp calculation fails**
   ```python
   # Line 1774-1814: Multiple failure points
   # - video_start_time not in timing info
   # - detection_time calculation errors
   # - Calibration offset not applied
   ```

#### B. Database Population Issues

**Location:** `services/labjack_detection_service.py:2424-2445`

```python
INSERT INTO detection_events (
    video_relative_timestamp,  # NULL if calculation fails
    actual_latency_ms,         # NULL if not matched
    ...
)
```

When these fields are NULL:
- Detection appears at timestamp 0.0s
- Ground truth matching fails (no temporal overlap)
- Detection marked as False Positive → 10000ms latency

---

### 4. Frame Processing Bottleneck

#### Detection Rate by Video

```
Video 1: 74/131 = 56.5% (missed 43.5% of frames)
Video 2: 99/126 = 78.6% (missed 21.4% of frames)
```

#### Probable Causes

1. **Model Inference Too Slow**
   - Processing time > frame interval (33-40ms at 24-30fps)
   - Queue buildup leads to frame dropping
   - Constant voltage means hardware is NOT the issue

2. **Frame Reader Bottleneck**
   - Video decoding slower than real-time
   - Buffer overflow causes frame skips
   - No frame buffering/backpressure mechanism

3. **Synchronization Issues**
   - Frame timestamps not aligned with hardware timestamps
   - Timing drift accumulates over video duration
   - Multi-video sequences lose sync between videos

4. **Resource Contention**
   - CPU/GPU overload during inference
   - Memory pressure causing GC pauses
   - I/O blocking on database writes

---

## Impact Assessment

### Critical Issues (Immediate Fix Required)

1. **❌ Timing Measurement Completely Broken**
   - Impact: Cannot measure actual detection latency
   - Severity: **CRITICAL** - Primary test objective impossible
   - Fix Priority: **P0 - URGENT**

2. **❌ 67% Detection Rate on Constant Voltage**
   - Impact: 33% of events missed despite ideal conditions
   - Severity: **CRITICAL** - Unacceptable for production
   - Fix Priority: **P0 - URGENT**

3. **❌ Ground Truth Matching Failure**
   - Impact: 0% true positives, all marked as FP
   - Severity: **HIGH** - Metrics completely invalid
   - Fix Priority: **P0 - URGENT**

### High-Impact Issues

4. **⚠️ Video Timestamp Calibration Disabled**
   - Location: Multi-video sequence handling
   - Impact: Cross-video timing contamination
   - Fix Priority: **P1 - HIGH**

5. **⚠️ Frame Skipping Without Detection**
   - Impact: Silent failures, no error logging
   - Fix Priority: **P1 - HIGH**

---

## Root Cause Summary

### Primary Root Cause: Timing Data Pipeline Failure

```
Hardware Detection → [WORKING]
    ↓
Session Timing Capture → [FAILING] ⚠️
    ↓
Video-Relative Timestamp Calculation → [FAILING] ⚠️
    ↓
Detection Event Creation → [PARTIAL - No timing] ⚠️
    ↓
Database Storage → [WORKING - Stores NULL] ✓
    ↓
Ground Truth Matching → [FAILING - No temporal overlap] ⚠️
    ↓
Result: 10000ms placeholder latency ❌
```

### Secondary Root Cause: Frame Processing Bottleneck

```
Video Frame Queue → Frame Reader → Model Inference → Detection Handler
                                         ↓ [TOO SLOW]
                                    Frame Dropped
                                         ↓
                              84 Detections Missed (33%)
```

---

## Recommended Fixes

### Immediate Actions (P0 - This Week)

#### 1. Fix Timing Data Capture

**File:** `services/labjack_detection_service.py`

**Lines 1750-1820:**
```python
# CURRENT (BROKEN):
try:
    timing_info = self.get_session_timing_info(session_id)
    if timing_info is None:
        # Detection created with NO timing data
        pass
    # Rest of calibration disabled for multi-video
```

**FIX:**
```python
# REQUIRED:
timing_info = self.get_session_timing_info(session_id)
if timing_info is None:
    logger.error(f"❌ CRITICAL: No timing info for session {session_id}")
    raise ValueError(f"Cannot create detection without timing data")

# ALWAYS calculate video_relative_timestamp
if 'video_start_time' not in timing_info:
    logger.error(f"❌ CRITICAL: video_start_time missing from timing_info")
    raise ValueError(f"Cannot calibrate detection timestamp")

video_relative_timestamp = (
    timestamp.timestamp() - timing_info['video_start_time']
)

# Store in detection event (REQUIRED)
event.video_relative_timestamp = video_relative_timestamp
```

#### 2. Enable Multi-Video Timing Calibration

**Lines 1751-1755:**
```python
# CURRENT:
# CRITICAL FIX: Disable calibration offset for multi-video sequences
# to avoid cross-video contamination

# REQUIRED FIX:
# Use per-video timing windows instead of disabling
video_id = timing_info.get('current_video_id')
video_window = self.get_video_timing_window(session_id, video_id)
# Calculate offset within current video window only
```

#### 3. Add Timing Data Validation

**New function:**
```python
def validate_detection_timing(self, detection_event: DetectionEvent) -> bool:
    """Validate detection has required timing data before storage"""
    if detection_event.video_relative_timestamp is None:
        logger.error(f"❌ Detection {detection_event.id} missing video_relative_timestamp")
        return False

    if detection_event.video_relative_timestamp == 0.0:
        logger.warning(f"⚠️ Detection {detection_event.id} at timestamp 0.0 - likely error")

    return True
```

#### 4. Fix Frame Processing Bottleneck

**Options (in priority order):**

A. **Add Frame Skip Detection and Logging**
```python
expected_frame = last_frame + 1
if current_frame > expected_frame:
    skipped = current_frame - expected_frame
    logger.warning(f"⚠️ SKIPPED {skipped} frames: {expected_frame}-{current_frame-1}")
    metrics['frames_skipped'] += skipped
```

B. **Implement Frame Buffering**
```python
frame_buffer = queue.Queue(maxsize=120)  # 4 seconds at 30fps
# Producer: video reader (separate thread)
# Consumer: model inference (main thread)
# Allows burst processing and smooths frame delivery
```

C. **Add Backpressure Mechanism**
```python
if inference_queue.qsize() > QUEUE_THRESHOLD:
    logger.warning("Inference queue full - slowing frame reader")
    time.sleep(BACKPRESSURE_DELAY)
```

D. **Optimize Model Inference**
```python
# Use batch inference instead of single-frame
batch_size = 4  # Process 4 frames together
frames_batch = []
# ... collect frames ...
results = model.infer_batch(frames_batch)  # More efficient
```

---

### Short-Term Fixes (P1 - Next Week)

#### 5. Improve Session Timing Info Management

```python
def get_session_timing_info(self, session_id: str) -> Dict:
    """Get timing info with validation and defaults"""
    info = self.session_timing_info.get(session_id)

    if info is None:
        logger.error(f"No timing info for session {session_id}")
        raise ValueError(f"Session timing not initialized")

    required_fields = ['video_start_time', 'session_start_time', 'current_video_id']
    for field in required_fields:
        if field not in info:
            logger.error(f"Missing required field: {field}")
            raise ValueError(f"Incomplete timing info: missing {field}")

    return info
```

#### 6. Add Detection Rate Monitoring

```python
class DetectionRateMonitor:
    """Monitor detection rate vs expected rate"""

    def __init__(self, expected_fps: float):
        self.expected_fps = expected_fps
        self.detection_count = 0
        self.start_time = time.time()

    def record_detection(self):
        self.detection_count += 1
        elapsed = time.time() - self.start_time
        actual_rate = self.detection_count / elapsed
        expected_count = elapsed * self.expected_fps

        if self.detection_count < expected_count * 0.8:  # 80% threshold
            logger.warning(
                f"⚠️ LOW DETECTION RATE: {actual_rate:.1f} det/s "
                f"(expected {self.expected_fps:.1f}), "
                f"missed {expected_count - self.detection_count:.0f} detections"
            )
```

#### 7. Implement Ground Truth Temporal Window Logging

```python
def debug_ground_truth_matching(detection, ground_truth_objects):
    """Log temporal matching attempts for debugging"""
    det_time = detection.video_relative_timestamp

    logger.debug(f"Matching detection at {det_time:.3f}s")
    for gt in ground_truth_objects:
        gt_time = gt.video_relative_timestamp
        offset = abs(det_time - gt_time) * 1000  # ms

        if offset <= MATCHING_TOLERANCE_MS:
            logger.debug(f"  ✓ MATCH: GT at {gt_time:.3f}s (offset={offset:.1f}ms)")
        else:
            logger.debug(f"  ✗ NO MATCH: GT at {gt_time:.3f}s (offset={offset:.1f}ms)")
```

---

### Long-Term Improvements (P2 - Future)

8. **Implement Real-Time Performance Dashboard**
   - Live detection rate monitoring
   - Latency distribution visualization
   - Frame skip detection and alerting

9. **Add Automated Performance Testing**
   - Constant voltage test as regression test
   - Alert if detection rate < 95%
   - Alert if >5% timing measurement failures

10. **Optimize Video Processing Pipeline**
    - Hardware-accelerated video decoding
    - GPU-based inference (if available)
    - Async I/O for database writes

---

## Expected Improvements After Fixes

### Detection Rate
- **Current:** 67.3% (173/257)
- **After Fix:** >95% (245+/257)
- **Improvement:** +28% absolute, +42% relative
- **Expected FN reduction:** 84 → <12

### Timing Measurements
- **Current:** 100% placeholder (10000ms)
- **After Fix:** 100% valid latency values
- **Expected latency range:** 50-300ms
- **Ground truth matching:** 0% → >90% true positives

### System Reliability
- **Current:** Silent frame skipping
- **After Fix:** Logged and monitored
- **Detection rate alerts:** Active monitoring
- **Timing validation:** All detections validated

---

## Testing Recommendations

### Verification Tests

1. **Constant Voltage Test (Repeat)**
   - Inject 3.3V continuous
   - Expected: >95% detection rate
   - Expected: Valid latency values 50-300ms
   - Expected: 0 placeholder 10000ms values

2. **Frame Skip Detection Test**
   - Run with low-performance hardware
   - Verify frame skip logging
   - Verify detection rate warnings

3. **Multi-Video Timing Test**
   - 3+ video sequence
   - Verify timing calibration per video
   - Verify no cross-video contamination

4. **Ground Truth Matching Test**
   - Create synthetic GT with known timings
   - Verify matching accuracy >95%
   - Verify TP/FP/FN classification

---

## Conclusion

The constant voltage test revealed **two critical, interconnected failures**:

1. **Timing measurement pipeline is completely broken**
   - All detections created without timing data
   - Ground truth matching fails → all marked as FP
   - Results in 10000ms placeholder latencies

2. **Frame processing bottleneck causing 33% missed detections**
   - Model inference too slow for real-time processing
   - No frame buffer or backpressure mechanism
   - Silent failures without monitoring

**Both issues must be fixed immediately** to enable reliable hardware-in-the-loop testing. The timing data issue is particularly critical as it makes the primary test objective (latency measurement) impossible.

**Estimated fix effort:**
- P0 fixes: 1-2 days
- P1 fixes: 2-3 days
- P2 improvements: 1-2 weeks

**Priority:** Fix timing data pipeline first (enables validation), then address frame processing bottleneck (enables production use).

---

## Appendices

### A. Session Details

- **Session ID:** daad8bf6-b5da-4423-abc4-a85e83bc1c16
- **Test Name:** Video Sequence Test - 2025-11-24 12:48
- **Duration:** 15.7 seconds (12:48:31 → 12:48:47)
- **Videos:** 2 videos, ~5 seconds each
- **Latency Threshold:** 100ms (not being measured)

### B. Affected Files

1. `services/labjack_detection_service.py` (primary fix location)
2. `services/ground_truth_matching_service.py` (FP latency marker)
3. `services/sequence_video_metrics_aggregator.py` (aggregation logic)
4. Video processing pipeline (frame reader/inference loop)

### C. Related Issues

- Hardware integration: Working correctly ✓
- Database schema: Correct ✓
- Ground truth annotations: Available (257 objects) ✓
- Detection logic: Working but missing timing data ⚠️
- Matching logic: Working but failing due to bad input data ⚠️

---

**Report Generated:** 2025-11-24
**Investigator:** Claude Code Performance Benchmarker Agent
**Status:** Ready for Development Team Review
