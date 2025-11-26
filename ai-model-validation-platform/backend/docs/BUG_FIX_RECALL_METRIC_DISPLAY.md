# Bug Fix: Recall Metric Display for Multi-Video Sessions

## Bug Report Summary

**Session ID**: `fa204ef2-9d8b-4480-9692-86e338c1218a`

**Problem**:
- UI displayed: "Recall 100.0%"
- Actual data: 87 TP / 242 GT Events = **36% recall**

**Root Cause**: Frontend was displaying per-video recall instead of session-wide recall

---

## Technical Analysis

### Metrics Calculation

#### Per-Video Recall (Individual Video)
```
Per-video recall = TP for this video / GT events for this video

Example:
- Video 1: 10 TP / 10 GT = 100% recall ✓
- Video 2: 77 TP / 232 GT = 33.2% recall ✓
```

#### Session-Wide Recall (All Videos Combined)
```
Session recall = Sum(TP across all videos) / Sum(GT across all videos)

Example:
- Session: (10 + 77) TP / (10 + 232) GT = 87/242 = 35.95% ≈ 36% ✓
```

**CRITICAL**: Session recall ≠ Average of per-video recalls
Session recall is a **weighted aggregate** based on total GT count.

---

## Fix Implementation

### 1. API Response Changes

#### File: `routers/video_sequence_testing.py`

**Per-Video Metrics** (Lines 1757-1771):
```python
# CRITICAL: Per-video metrics - calculated ONLY for THIS video
# WARNING: In multi-video sessions, per-video recall != session-wide recall
ground_truth_metrics = {
    "recall": round(recall_ratio * 100, 1),  # Per-video only
    "metric_scope": "per_video"  # NEW FIELD
}
```

**Session-Wide Metrics** (Lines 1889-1904):
```python
# CRITICAL: Session-wide metrics calculated from ALL videos
ground_truth_comparison = {
    "recall": round(session_metrics.recall * 100, 1),  # Session-wide
    "metric_scope": "session_wide"  # NEW FIELD
}
```

**Fallback Calculation** (Lines 1921-1935):
```python
# CRITICAL: Fallback session-wide metrics from aggregated per-video data
ground_truth_comparison = {
    "recall": round(recall_ratio * 100, 1),  # Session-wide
    "metric_scope": "session_wide"  # NEW FIELD
}
```

#### File: `routers/test_sessions.py`

**Session Metrics** (Lines 2088-2106):
```python
# CRITICAL: Session-wide metrics - calculated across ALL videos/detections
ground_truth_metrics = {
    "recall": round(session_metrics.recall * 100, 1),  # Session-wide
    "metric_scope": "session_wide"  # NEW FIELD
}
```

---

## API Response Structure

### Before Fix
```json
{
  "ground_truth_comparison": {
    "recall": 100.0,  // WRONG - showing per-video value
    "true_positives": 87,
    "total_ground_truth": 242
  }
}
```

### After Fix
```json
{
  "ground_truth_comparison": {
    "recall": 36.0,  // CORRECT - session-wide
    "true_positives": 87,
    "total_ground_truth": 242,
    "metric_scope": "session_wide"  // NEW: Explicit indicator
  },
  "per_video_results": [
    {
      "video_id": "video1",
      "ground_truth_metrics": {
        "recall": 100.0,  // Per-video (can be 100%)
        "true_positives": 10,
        "total_ground_truth": 10,
        "metric_scope": "per_video"  // NEW: Explicit indicator
      }
    },
    {
      "video_id": "video2",
      "ground_truth_metrics": {
        "recall": 33.2,  // Per-video (different value)
        "true_positives": 77,
        "total_ground_truth": 232,
        "metric_scope": "per_video"
      }
    }
  ]
}
```

---

## Test Coverage

### Test File: `tests/test_multi_video_recall_calculation.py`

**6 Tests - All Passing ✓**

1. **test_session_wide_recall_vs_per_video_recall**
   - Validates session recall (36%) ≠ per-video recall (100%)
   - Confirms weighted aggregation, not simple average

2. **test_api_response_structure**
   - Verifies `metric_scope` field presence
   - Ensures session recall < max per-video recall

3. **test_recall_calculation_edge_cases**
   - Tests zero GT events, all TP, no TP
   - Validates bug scenario (87/242 = 36%)

4. **test_validate_session_fa204ef2_metrics**
   - Exact validation of bug report session
   - Confirms 36% (not 100%) is correct

5. **test_metric_scope_documentation**
   - Validates allowed scope values

6. **test_recall_calculation_comments**
   - Documentation verification

**Test Results**:
```
tests/test_multi_video_recall_calculation.py::TestMultiVideoRecallCalculation::test_session_wide_recall_vs_per_video_recall PASSED [ 16%]
tests/test_multi_video_recall_calculation.py::TestMultiVideoRecallCalculation::test_api_response_structure PASSED [ 33%]
tests/test_multi_video_recall_calculation.py::TestMultiVideoRecallCalculation::test_recall_calculation_edge_cases PASSED [ 50%]
tests/test_multi_video_recall_calculation.py::TestMultiVideoRecallCalculation::test_validate_session_fa204ef2_metrics PASSED [ 66%]
tests/test_multi_video_recall_calculation.py::TestGroundTruthMetricsDocumentation::test_metric_scope_documentation PASSED [ 83%]
tests/test_multi_video_recall_calculation.py::TestGroundTruthMetricsDocumentation::test_recall_calculation_comments PASSED [100%]
```

---

## Validation Checklist

- [x] Session-wide recall calculated correctly (87/242 = 36%)
- [x] Per-video recall remains separate and accurate
- [x] API response includes `metric_scope` field
- [x] Backend calculations unchanged (already correct)
- [x] Clear documentation added to code
- [x] Comprehensive test suite created
- [x] Tests validate bug scenario (session fa204ef2)
- [ ] Frontend updated to use `metric_scope` indicator
- [ ] Historical sessions display correctly

---

## Frontend Integration Guide

### What Frontend Needs to Do

1. **Check `metric_scope` field**:
   ```javascript
   if (metrics.metric_scope === "session_wide") {
     // Display as overall session recall
     displaySessionRecall(metrics.recall);
   } else if (metrics.metric_scope === "per_video") {
     // Display as individual video recall
     displayVideoRecall(metrics.recall);
   }
   ```

2. **Display Session Metrics**:
   ```javascript
   // Use ground_truth_comparison for session-level display
   const sessionRecall = response.ground_truth_comparison.recall; // 36%

   // NOT from per_video_results[0].ground_truth_metrics.recall (100%)
   ```

3. **Show Both Metrics Clearly**:
   ```
   Session Overall: 36% recall (87/242 GT events)

   Video Breakdown:
   - Video 1: 100% recall (10/10 GT events)
   - Video 2: 33% recall (77/232 GT events)
   ```

---

## Verification Steps

### Step 1: Check Session fa204ef2 Response
```bash
curl -X GET "http://localhost:8000/api/sessions/fa204ef2-9d8b-4480-9692-86e338c1218a" \
  -H "Authorization: Bearer <token>" | jq '.metrics'
```

**Expected Output**:
```json
{
  "recall": 36.0,
  "true_positives": 87,
  "total_ground_truth": 242,
  "metric_scope": "session_wide"
}
```

### Step 2: Verify Per-Video Results
```bash
curl -X GET "http://localhost:8000/api/video-sequences/<sequence-id>" \
  -H "Authorization: Bearer <token>" | jq '.per_video_results[0].ground_truth_metrics'
```

**Expected Output**:
```json
{
  "recall": 100.0,
  "true_positives": 10,
  "total_ground_truth": 10,
  "metric_scope": "per_video"
}
```

---

## Key Takeaways

1. **Session recall is NOT the average of per-video recalls**
   - It's a weighted aggregate based on total GT count

2. **Per-video recall can be 100% even when session recall is low**
   - This is mathematically correct when videos have different GT counts

3. **The `metric_scope` field is CRITICAL**
   - Frontend must use this to display the correct metric in the correct context

4. **Backend calculations were already correct**
   - Bug was in the frontend interpretation/display

5. **Historical data is still accurate**
   - Database values are correct, just need proper display logic

---

## Related Files

### Modified Files
- `backend/routers/video_sequence_testing.py` (Lines 1757-1935)
- `backend/routers/test_sessions.py` (Lines 2088-2106)

### New Files
- `backend/tests/test_multi_video_recall_calculation.py` (Test suite)
- `backend/docs/BUG_FIX_RECALL_METRIC_DISPLAY.md` (This document)

### Verified Correct (No Changes Needed)
- `backend/services/ground_truth_matching_service.py` (Line 1683)
  - Session recall calculation: `recall = TP / actual_gt_count` ✓

---

## Contact

For questions about this fix, contact the backend team or refer to:
- Bug Report: Session fa204ef2-9d8b-4480-9692-86e338c1218a
- Test Suite: `tests/test_multi_video_recall_calculation.py`
- Code Comments: Search for "CRITICAL: Session-wide" in modified files

---

**Fix Date**: 2025-11-24
**Status**: ✅ Backend Complete - Frontend Integration Pending
**Test Coverage**: 6/6 tests passing
