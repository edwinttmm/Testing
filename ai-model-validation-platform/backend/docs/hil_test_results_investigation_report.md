# HIL Test Results Investigation Report
**Session ID:** `e8e108b0-cb20-4cba-a2db-fc29f21efd16`
**Investigation Date:** 2025-11-21
**Session Name:** Video Sequence Test - 2025-11-20 22:18

---

## Executive Summary

**CRITICAL ANOMALY DETECTED:** The overall session metrics show only **41 ground truth annotations** (TP + FN = 40 + 1), but the per-video breakdown correctly shows **257 total ground truth annotations** (131 + 126). This is a **216-annotation discrepancy** (84% data loss) indicating a severe bug in the ground truth matching or aggregation logic.

---

## Session Overview

| Property | Value |
|----------|-------|
| Session ID | `e8e108b0-cb20-4cba-a2db-fc29f21efd16` |
| Session Name | Video Sequence Test - 2025-11-20 22:18 |
| Status | completed |
| Number of Videos | 2 |
| Video 1 ID | `10c2b16c-86fa-4140-b1cf-c0ea42f82ca5` |
| Video 2 ID | `550e3cf8-2755-42df-8c3c-041300735f93` |
| Pass/Fail Result | FAIL |
| Overall Score | 21.33 |
| Accuracy Result | FAIL |
| Latency Result | PASS |

---

## Overall Session Metrics (INCORRECT)

**Source:** TestSession.accuracy_details (aggregated from all videos)

| Metric | Value | Status |
|--------|-------|--------|
| **F1 Score** | 0.213 | ⚠️ INCORRECT - Using wrong GT count |
| **Precision** | 0.120 | ⚠️ INCORRECT - Using wrong GT count |
| **Recall** | 0.976 | ⚠️ INCORRECT - Using wrong GT count |
| **True Positives** | 40 | ⚠️ SUSPICIOUSLY LOW (should be ~251) |
| **False Positives** | 294 | ⚠️ INCORRECT |
| **False Negatives** | 1 | ⚠️ INCORRECT |
| **Total Detections** | 334 | ✅ CORRECT |
| **Calculated GT (TP + FN)** | **41** | 🚨 **WRONG - Should be 257** |

### Why These Metrics Are Wrong:
- With 257 GT annotations, we should expect ~251 TP (not 40) if the model is performing well
- The recall of 0.976 (97.6%) on 41 GT would mean 40 TP - this is mathematically correct but based on wrong GT count
- The actual recall should be calculated as: TP / 257 (not TP / 41)

---

## Per-Video Results (CORRECT)

**Source:** SequenceVideoResult table

### Video 1
| Metric | Value | Notes |
|--------|-------|-------|
| Video ID | `10c2b16c-86fa-4140-b1cf-c0ea42f82ca5` |  |
| Sequence Order | 1 (first video) |  |
| **Ground Truth Count** | **131** | ✅ Correct |
| **Actual Detections** | **138** | ✅ Correct |
| Detection Difference | +7 (7 extra detections) |  |
| F1 Score | null | ❌ Not calculated per-video |
| Precision | null | ❌ Not calculated per-video |
| Recall | null | ❌ Not calculated per-video |
| Passed Detections | 0 | ❓ Not populated |
| Failed Detections | 0 | ❓ Not populated |
| Avg Latency | null | ❓ Not populated |

### Video 2
| Metric | Value | Notes |
|--------|-------|-------|
| Video ID | `550e3cf8-2755-42df-8c3c-041300735f93` |  |
| Sequence Order | 2 (second video) |  |
| **Ground Truth Count** | **126** | ✅ Correct |
| **Actual Detections** | **196** | ✅ Correct |
| Detection Difference | +70 (70 extra detections) | ⚠️ Significant over-detection |
| F1 Score | null | ❌ Not calculated per-video |
| Precision | null | ❌ Not calculated per-video |
| Recall | null | ❌ Not calculated per-video |
| Passed Detections | 0 | ❓ Not populated |
| Failed Detections | 0 | ❓ Not populated |
| Avg Latency | null | ❓ Not populated |

### Per-Video Totals
| Metric | Video 1 | Video 2 | **Total** |
|--------|---------|---------|-----------|
| Ground Truth | 131 | 126 | **257** ✅ |
| Detections | 138 | 196 | **334** ✅ |
| Extra Detections | +7 | +70 | **+77** |

---

## Detection Event Counts (Verification)

**Source:** DetectionEvent table (direct query)

| Video | Detection Count | Matches Per-Video Result |
|-------|-----------------|--------------------------|
| Video 1 (`10c2b16c-...`) | 138 | ✅ Yes |
| Video 2 (`550e3cf8-...`) | 196 | ✅ Yes |
| **Total** | **334** | ✅ Yes |

This confirms the per-video detection counts are accurate.

---

## Latency Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Result | PASS | ✅ |
| Mean Latency | 1.998 ms | ✅ Excellent |
| Max Latency | 8.054 ms | ✅ |
| Min Latency | 0.208 ms | ✅ |
| Std Deviation | 2.323 ms | ✅ |
| Within Tolerance % | 100.0% | ✅ |
| Sample Count | 10 | ⚠️ Only 10 samples |
| Samples by Video | Video 1: 10, Video 2: 0 | 🚨 **Video 2 not sampled!** |

### Latency Anomaly:
- All 10 latency samples came from Video 1 only
- Video 2 has **zero latency samples** despite having 196 detections
- This suggests latency sampling logic may only work on the first video in a sequence

---

## Critical Anomalies Identified

### 1. 🚨 Ground Truth Count Catastrophic Mismatch (Priority: CRITICAL)

**Symptom:**
- Overall session shows: TP=40, FN=1, **Total GT = 41**
- Per-video breakdown shows: **Total GT = 257** (131 + 126)
- **Discrepancy: 216 missing ground truth annotations (84% data loss)**

**Impact:**
- All accuracy metrics (F1, Precision, Recall) are **completely wrong**
- The model appears to have 97.6% recall when it likely has much lower actual recall
- Misleading "FAIL" result - the real performance is likely much worse than reported
- Cannot trust any test results from multi-video sessions

**Root Cause Hypothesis:**
1. Ground truth matching only runs for the first video or a subset of detections
2. Aggregation logic from per-video to session level is broken
3. The `GroundTruthMatchingService` may have timing or video ID issues
4. Detection-to-GT matching may time out or fail silently for video sequences

**Where to Look:**
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/test_results_processor.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/session_completion_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/sequence_video_metrics_aggregator.py`

---

### 2. ⚠️ Per-Video Metrics Not Calculated

**Symptom:**
- Per-video results have GT counts and detection counts
- But F1, Precision, Recall are all `null`
- `passed_detections` and `failed_detections` are all 0

**Impact:**
- Cannot see per-video accuracy breakdown in UI
- Cannot identify which video is causing issues
- Cannot compare model performance across different videos

**Root Cause Hypothesis:**
- The per-video ground truth matching runs and counts GT annotations correctly
- But the matching logic (TP/FP/FN calculation) doesn't populate the results
- May be a separate calculation step that's not being triggered

---

### 3. 🚨 Latency Sampling Only From First Video

**Symptom:**
- 10 latency samples collected
- All 10 samples from Video 1
- Zero samples from Video 2

**Impact:**
- Latency metrics don't represent full session performance
- Video 2 latency is completely unknown
- Multi-video latency distribution is incorrect

**Root Cause Hypothesis:**
- Latency sampling logic may reference a single video ID
- May use `session.video_id` instead of iterating through all videos
- Sampling may only occur during first video processing

**Where to Look:**
- Latency sampling code in detection pipeline
- How `latency_details.samplesByVideo` is populated

---

### 4. ⚠️ Excessive False Detections on Video 2

**Symptom:**
- Video 1: 138 detections vs 131 GT (+7, ~5% over)
- Video 2: 196 detections vs 126 GT (+70, ~56% over)

**Possible Causes:**
- Model performance degrades on second video
- Video 2 has different characteristics
- Timing synchronization issues causing duplicate detections
- Frame timing offset between videos

---

## Correct Metrics (Calculated)

Based on the correct GT count of 257:

| Metric | Incorrect Value | Should Be (if matched correctly) |
|--------|-----------------|----------------------------------|
| Ground Truth Total | 41 | **257** |
| True Positives | 40 | **~180-250** (unknown - need matching) |
| False Positives | 294 | **~84-154** (unknown - need matching) |
| False Negatives | 1 | **~7-77** (unknown - need matching) |
| Recall | 0.976 (97.6%) | **~0.70-0.97** (lower, unknown) |
| Precision | 0.120 (12%) | **~0.54-0.75** (likely higher) |
| F1 Score | 0.213 | **~0.60-0.84** (likely much higher) |

**Note:** Actual values depend on proper GT matching being run.

---

## Cached vs. Recalculated Indicators

The API response includes:
```json
"sequenceMetadata": {
    "post_processing": {
        "status": "queued",
        "updated_at": "2025-11-20T22:18:19.469877+00:00",
        "note": "Triggered by results fetch"
    }
}
```

This suggests results may be cached and post-processing was queued when results were fetched. The incorrect metrics may be from incomplete initial processing.

---

## Recommendations

### Immediate Actions (Priority: CRITICAL)

1. **Fix Ground Truth Aggregation Bug**
   - Investigate `sequence_video_metrics_aggregator.py`
   - Ensure all per-video GT matches are aggregated correctly
   - Add validation that `sum(per_video_gt) == overall_gt`

2. **Implement Per-Video Accuracy Calculations**
   - Calculate F1/Precision/Recall for each video in sequence
   - Populate `SequenceVideoResult` metrics fields
   - Display per-video metrics in UI

3. **Fix Latency Sampling for Multi-Video**
   - Sample latency from all videos, not just the first
   - Ensure `samplesByVideo` includes all videos
   - Add per-video latency statistics

4. **Add Data Validation**
   - Add assertion: `(TP + FN) == sum(video.gt_count for video in sequence)`
   - Fail session processing if validation fails
   - Log detailed error when counts don't match

### Testing Needed

1. Re-run this exact test session with fixes applied
2. Verify GT count of 257 is used in overall metrics
3. Verify per-video accuracy metrics are calculated
4. Verify latency samples come from both videos
5. Add automated test for multi-video GT aggregation

---

## Files to Investigate

Priority order for debugging:

1. `/backend/services/sequence_video_metrics_aggregator.py` - Aggregation logic
2. `/backend/services/ground_truth_matching_service.py` - GT matching
3. `/backend/services/test_results_processor.py` - Results processing
4. `/backend/services/session_completion_service.py` - Session completion
5. `/backend/routers/test_sessions.py` - API endpoints (lines 1977-2124)

---

## Conclusion

The HIL test results page displays **fundamentally incorrect accuracy metrics** due to a critical bug in ground truth aggregation for multi-video sessions. While per-video data is correctly collected (257 total GT annotations), the overall session metrics only reflect 41 GT annotations (84% data loss).

**The system is currently unreliable for multi-video test sessions.** All accuracy metrics shown are mathematically consistent but based on the wrong ground truth count, making them meaningless for actual model validation.

**This is a P0 production bug** that must be fixed before the system can be trusted for multi-video HIL testing.
