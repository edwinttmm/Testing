# Bug Investigation Summary: Zero-Duration Videos

**Date:** 2024-11-24
**Session:** `daad8bf6-b5da-4423-abc4-a85e83bc1c16`
**Investigator:** Code Analyzer Agent

---

## Executive Summary

Investigated why video timing map showed 0-duration videos causing all ground truth matches to fail. Found and fixed the root cause in `ground_truth_matching_service.py`.

**Status:**
- ✅ **PRIMARY BUG FIXED:** Zero-duration video calculation
- ⚠️ **SECONDARY BUG FOUND:** Timestamp coordinate system mismatch (needs separate fix)

---

## Primary Bug: Zero-Duration Videos

### Root Cause

**Location:** `/backend/services/ground_truth_matching_service.py:1050`

```python
# BEFORE (BUGGY):
duration_s = result.actual_duration_ms / 1000.0 if result.actual_duration_ms else 0
video_end = video_start + duration_s if video_start else None
```

**Problem:**
- `SequenceVideoResult.actual_duration_ms` was `NULL` in database
- Calculation resulted in `duration_s = 0`
- Made `video_end = video_start` (same timestamp)
- Videos appeared as zero-width windows

### Evidence

```
Database Query Results:
Video 1 (10c2b16c-86fa-4140-b1cf-c0ea42f82ca5):
  video_start_time: 1763988511.881546 ✅
  video_end_time: 1763988516.9232128 ✅ (Correct!)
  actual_duration_ms: None ❌ (Not populated)

Calculated (BEFORE FIX):
  duration_s = 0.00s ❌
  video_end = video_start + 0 = video_start ❌

Logged:
  📹 Video 1: 1763988511.882s - 1763988511.882s (duration: 0.00s) ❌
```

### Solution

**Location:** `/backend/services/ground_truth_matching_service.py:1050-1053`

```python
# AFTER (FIXED):
video_end = result.video_end_time  # Use authoritative source
duration_s = (video_end - video_start) if (video_end and video_start) else 0
```

**Rationale:**
- `video_end_time` already correctly populated in database
- Calculate duration from start/end instead of relying on `actual_duration_ms`
- Uses authoritative source of truth

### Verification

```
✅ After Fix:
Video 1: 1763988511.882s - 1763988516.923s (duration: 5.04s) ✅
Video 2: 1763988516.924s - 1763988521.965s (duration: 5.04s) ✅
```

---

## Secondary Bug: Timestamp Coordinate Mismatch

After fixing the duration bug, matching still fails with 0 TP / 173 FP / 257 FN.

### Root Cause

**Detections** use absolute Unix timestamps:
```
DetectionEvent.timestamp:
  1763988511.976s
  1763988512.118s
  1763988512.229s
```

**Ground Truth** uses video-relative timestamps:
```
GroundTruthObject.timestamp:
  0.000s (start of video)
  0.042s (42ms into video)
  0.083s (83ms into video)
```

### Why This Breaks Matching

```
Detection: 1763988511.976s
GT:        0.000s
Difference: 1763988511.976s (1.76 billion seconds!)
Tolerance:  0.100s (100ms)
Result:     NO MATCH ❌
```

### Next Steps

**Investigate coordinate conversion functions:**

1. `extract_ground_truth_video_time()` (line ~1092)
   - Should convert GT relative time → absolute Unix time
   - Check: Is video_timing_map being used correctly?

2. `extract_detection_video_time()` (line ~1097)
   - Should convert detection absolute time → video-relative time
   - Or ensure both are in same coordinate system

**Hypothesis:** These functions may not be using the (now-fixed) video timing map correctly.

---

## Files Modified

### ✅ Fixed
1. `/backend/services/ground_truth_matching_service.py`
   - Lines 1050-1053: Duration calculation fix

### 📝 Documentation Created
1. `/backend/docs/BUG_VIDEO_DURATION_ZERO_INVESTIGATION.md`
2. `/backend/docs/BUG_INVESTIGATION_SUMMARY.md`

---

## Database Schema Reference

### Video Table
```python
Video.duration: Float  # Duration in seconds (5.04s) ✅ Correct
```

### SequenceVideoResult Table
```python
video_start_time: Float       # Unix timestamp (1763988511.882) ✅ Correct
video_end_time: Float         # Unix timestamp (1763988516.923) ✅ Correct
actual_duration_ms: Float     # Milliseconds (NULL) ❌ Not populated
video_play_offset_ms: Float   # Offset from sequence start ✅ Correct
```

### DetectionEvent Table
```python
timestamp: Float              # Unix timestamp (1763988511.976) ✅ Correct
```

### GroundTruthObject Table
```python
timestamp: Float              # Video-relative seconds (0.042) ✅ Correct
```

---

## Impact

### Before Fix
- ❌ All videos showed 0.00s duration
- ❌ Detections appeared outside video boundaries
- ❌ All matches failed (0 TP, 173 FP, 257 FN)

### After Primary Fix
- ✅ Videos show correct 5.04s duration
- ⚠️ Still no matches due to coordinate mismatch
- ❌ Matching fails (0 TP, 173 FP, 257 FN)

### After Secondary Fix (Pending)
- 🎯 Expected: Correct matching results
- 🎯 Expected: ~173 True Positives
- 🎯 Expected: Latency calculations working

---

## Recommended Next Action

**Investigate coordinate conversion functions:**
1. Find `extract_ground_truth_video_time()` implementation
2. Find `extract_detection_video_time()` implementation
3. Verify they use the video_timing_map correctly
4. Ensure both convert to same coordinate system (probably absolute Unix time)
5. Add debug logging to show converted timestamps

**Test command:**
```bash
python3 -c "
from database import SessionLocal
from services.ground_truth_matching_service import GroundTruthMatchingService
db = SessionLocal()
service = GroundTruthMatchingService(db)
result = service.match_detections_to_ground_truth(
    session_id='daad8bf6-b5da-4423-abc4-a85e83bc1c16',
    force_rematch=True
)
print(f'TP: {result.true_positives}, FP: {result.false_positives}, FN: {result.false_negatives}')
db.close()
"
```
