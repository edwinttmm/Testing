# Bug Analysis: Single-Video vs Multi-Video Impact

## Executive Summary

**ALL FOUR BUGS AFFECT BOTH SINGLE-VIDEO AND MULTI-VIDEO TESTS**

The bugs are **session-level issues** that occur regardless of whether the session contains one video or multiple videos. However, **Bug #4 (debounce) has MORE SEVERE impact on multi-video tests** because the debounce is global across the entire session.

---

## Bug-by-Bug Analysis

### 🐛 BUG #1: Identical Duplicate Entries (Line 325)

**Scope**: **BOTH single-video and multi-video tests**

**Evidence**:
```python
# Line 322-332: Detection events query
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    joinedload(DetectionEvent.test_session)  # ❌ This causes duplicates
).filter(DetectionEvent.test_session_id == session_id)

# Line 328-330: Optional video_id filter
if video_id is not None:
    detection_events_query = detection_events_query.filter(DetectionEvent.video_id == video_id)
```

**Why it affects both**:
- The `joinedload()` causes SQL JOIN that duplicates rows **PER session_id**, not per video_id
- Single-video tests: Get duplicate rows for ALL detections in that video
- Multi-video tests:
  - Without `video_id` filter: Get duplicate rows for ALL detections across ALL videos
  - With `video_id` filter: Get duplicate rows for that specific video only

**Fix applies to**: **BOTH** - Replace `joinedload()` with `selectinload()`

---

### 🐛 BUG #2: Different Value Duplicates (Lines 867-941 vs 944-1048)

**Scope**: **BOTH single-video and multi-video tests**

**Evidence**:
```python
# Line 867-941: FALLBACK PATH (no ground truth matches)
if len(corrected_results) == 0 and len(detection_events_result) > 0:
    for i, original_event in enumerate(detection_events_result):
        single_latency_ms = _get_single_authoritative_latency(original_event, None)
        enhanced_detection_events.append({
            "latency_ms": round(single_latency_ms, 3),
            "latency_source": "raw_measurement_no_ground_truth",  # ❌ DIFFERENT
            # Line 937: Pass/fail using single_latency_ms
            "result": "pass" if (single_latency_ms <= tolerance) else "fail"
        })

# Line 944-1048: NORMAL PATH (with ground truth matches)
else:
    for i, (original_event, corrected_result) in enumerate(zip(...)):
        single_latency_ms = _get_single_authoritative_latency(original_event, corrected_result)
        enhanced_detection_events.append({
            "latency_ms": round(single_latency_ms, 3),
            "latency_source": "timing_calculator_corrected",  # ❌ DIFFERENT
            # Line 1044: Pass/fail using single_latency_ms
            "result": "pass" if (single_latency_ms <= tolerance) else "fail"
        })
```

**Why it affects both**:
- The two code paths are triggered by **ground truth availability**, NOT by video count
- Single-video test: Uses fallback path if NO ground truth, normal path if ground truth exists
- Multi-video test: Uses fallback path if NO ground truth, normal path if ground truth exists
- Same detection can appear in BOTH lists with DIFFERENT latency values from different sources

**Fix applies to**: **BOTH** - Unify the two code paths

---

### 🐛 BUG #3: 0ms Latency = False PASS (Lines 937, 1044)

**Scope**: **BOTH single-video and multi-video tests**

**Evidence**:
```python
# Line 937 (fallback path) and Line 1044 (normal path):
"result": "pass" if (single_latency_ms is not None and single_latency_ms <= (session_result.tolerance_ms or 100)) else "fail"
```

**Priority sources in `_get_single_authoritative_latency()` (Lines 50-97)**:
```python
def _get_single_authoritative_latency(detection_event, corrected_result):
    # Priority 1: Timing calculator result
    if corrected_result and hasattr(corrected_result, 'detection_latency_ms'):
        return to_float(corrected_result.detection_latency_ms)

    # Priority 2: Stored latency (if not FP marker 10000ms)
    if hasattr(detection_event, 'actual_latency_ms'):
        latency = to_float(detection_event.actual_latency_ms)
        if latency is not None and latency < 10000:
            return latency

    # Priority 3: Calculate from timestamps
    if has video_relative_timestamp and matched_gt_time:
        return abs(det_time - gt_time) * 1000.0

    # Priority 4: Return None (no valid measurement)
    return None
```

**Problem**: When `single_latency_ms = 0.0` (valid measurement):
- `0.0 <= 100` → `True` → **"pass"** ✅
- When `single_latency_ms = None` (no GT match):
- `None is not None` → `False` → **"fail"** ✅

**But in Priority 3 calculation**:
```python
return abs(det_time - gt_time) * 1000.0
```
If both timestamps are exactly equal (0.0 - 0.0 = 0.0ms), this returns `0.0`, which passes!

**Why it affects both**:
- This is a **latency calculation issue** independent of video count
- Single-video: Can have 0ms latency if timestamps perfectly align
- Multi-video: Can have 0ms latency if timestamps perfectly align in ANY video
- Both incorrectly pass when the issue is timestamp synchronization, not actual 0ms latency

**Fix applies to**: **BOTH** - Add validation for suspiciously low latencies (< 5ms)

---

### 🐛 BUG #4: Missing Frame Detections - 100ms Debounce (Line 135)

**Scope**: **BOTH, but MORE SEVERE for multi-video tests**

**Evidence**:
```python
# labjack_detection_service.py Line 135:
debounce_ms: int = 100  # Default debounce time

# Line 182: Detection state storage
self.last_detection_times: Dict[str, Dict[str, datetime]] = {}
# Structure: session_id -> channel -> timestamp

# Line 1625-1628: Debounce check
session_detections = self.last_detection_times.setdefault(session_id, {})
last_detection = session_detections.get(channel, datetime.min)
debounce_delta = timedelta(milliseconds=config.debounce_ms)
delta_ms = (current_time - last_detection).total_seconds() * 1000.0

# Line 1647-1666: Debounce filter
if current_time - last_detection < debounce_delta:
    # SKIP DETECTION - within debounce window
    return None
```

**Critical Issue**: The debounce is **SESSION-LEVEL, not VIDEO-LEVEL**

**Storage structure**:
```python
self.last_detection_times = {
    "session_abc123": {
        "AIN0": datetime(2025, 1, 15, 10, 30, 45, 100000),  # Last detection across ALL videos
        "AIN1": datetime(2025, 1, 15, 10, 30, 45, 200000)
    }
}
```

**Impact Analysis**:

**Single-Video Test** (24 FPS = 41.67ms frame period):
- Frame 1 at 0ms → Detected ✅
- Frame 2 at 41.67ms → **BLOCKED** (< 100ms debounce) ❌
- Frame 3 at 83.33ms → **BLOCKED** (< 100ms debounce) ❌
- Frame 4 at 125ms → Detected ✅
- **Detection rate**: 50% (detects every other frame at best)

**Multi-Video Test** (3 videos, each 24 FPS):
- **Video 1**:
  - Frame 1 at 0ms → Detected ✅
  - Frame 2 at 41.67ms → **BLOCKED** ❌
  - Frame 3 at 83.33ms → **BLOCKED** ❌
  - Frame 4 at 125ms → Detected ✅

- **Video 2** starts at 5000ms:
  - Frame 1 at 5000ms → Detected ✅ (> 100ms since last)
  - Frame 2 at 5041.67ms → **BLOCKED** ❌
  - Frame 3 at 5083.33ms → **BLOCKED** ❌
  - Frame 4 at 5125ms → Detected ✅

- **Video 3** starts at 10000ms:
  - **SAME PATTERN** - session debounce still active

**Why multi-video is worse**:
- The debounce timer **never resets between videos**
- If videos play back-to-back with <100ms gap, the FIRST frame of the new video might be blocked
- Example: Video 1 ends at 9958ms, Video 2 starts at 10000ms → First frame at 10000ms **BLOCKED** (only 42ms gap)

**Current Video Tracking**:
```python
# labjack_detection_service.py Line 2022-2035:
current_video_id = metadata.get('current_video_id')
if current_video_id:
    current_video_timing = video_timing.get(current_video_id)
    # Uses current_video_id for timing, but NOT for debounce
```

**Fix applies to**: **BOTH**
- **Single-video**: Needs per-channel, per-video debounce
- **Multi-video**: **CRITICAL** - Needs per-channel, per-video debounce to prevent cross-video blocking

**Recommended Fix**:
```python
# Change storage structure to be video-aware:
self.last_detection_times: Dict[str, Dict[str, Dict[str, datetime]]] = {}
# Structure: session_id -> video_id -> channel -> timestamp

# Update debounce check:
session_detections = self.last_detection_times.setdefault(session_id, {})
video_detections = session_detections.setdefault(current_video_id, {})
last_detection = video_detections.get(channel, datetime.min)
```

---

## Summary Table

| Bug # | Description | Single-Video | Multi-Video | Severity | Video-Aware Fix Needed |
|-------|-------------|--------------|-------------|----------|----------------------|
| **1** | Identical duplicates (joinedload) | ✅ Affected | ✅ Affected | High | ❌ No - Session-level fix |
| **2** | Different value duplicates (two paths) | ✅ Affected | ✅ Affected | High | ❌ No - Logic unification |
| **3** | 0ms latency = false PASS | ✅ Affected | ✅ Affected | Medium | ❌ No - Validation logic |
| **4** | Missing frames (100ms debounce) | ✅ Affected (50% loss) | ⚠️ **MORE SEVERE** (cross-video blocking) | **CRITICAL** | ✅ **YES** - Video-aware debounce |

---

## Detailed Impact on Test Types

### Single-Video Tests
- **Bug #1**: Duplicate rows in results → Inflated counts
- **Bug #2**: Same detection listed twice with different values → Inconsistent metrics
- **Bug #3**: False passes for synchronized timestamps → Incorrect validation
- **Bug #4**: ~50% of frames not detected → Under-reporting

### Multi-Video Tests
- **Bug #1**: Duplicate rows per video → Multiplicative inflation across videos
- **Bug #2**: Same detection listed twice per video → Severe data corruption
- **Bug #3**: False passes in any video → System-wide validation failure
- **Bug #4**: **CRITICAL** - Cross-video detection blocking → Complete failure in rapid sequences

---

## Recommendations

### Immediate Actions (All Tests)
1. **Bug #1**: Replace `joinedload()` with `selectinload()` - **Universal fix**
2. **Bug #2**: Unify fallback and normal code paths - **Universal fix**
3. **Bug #3**: Add `if latency_ms < 5.0: flag as suspicious` - **Universal fix**

### Critical Action (Multi-Video Priority)
4. **Bug #4**: Implement **video-aware debounce** with structure:
   ```python
   session_id -> video_id -> channel -> last_detection_time
   ```
   This is **ESSENTIAL** for multi-video tests to work correctly.

---

## Conclusion

**All four bugs affect both test types**, but:
- Bugs #1, #2, #3: Equal severity for both types → Universal fixes work
- Bug #4: **Disproportionately impacts multi-video tests** → Requires video-aware implementation

**Priority Order**:
1. **Bug #4** (multi-video blocker) - Video-aware debounce
2. **Bug #1** (data corruption) - joinedload fix
3. **Bug #2** (data inconsistency) - Code path unification
4. **Bug #3** (validation accuracy) - Latency validation

---

**Generated**: 2025-11-25
**Analysis Tool**: Claude Code - Code Quality Analyzer
