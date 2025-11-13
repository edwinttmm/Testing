# Ground Truth Display Debug Report

## Executive Summary

**CRITICAL BUG FOUND:** Ground truth metrics show ALL ZEROS (0 TP, 0 FP, 0 FN) instead of expected values (0 TP, 193 FP, 514 FN).

**Root Cause:** The component is checking for `selectedVideoSummary?.ground_truth_metrics` before displaying per-video GT cards, but this field is likely **NULL** or **UNDEFINED** in the data returned from the backend API.

---

## 1. Individual Video Ground Truth Display (Lines 1343-1356)

### Location: `/frontend/src/pages/HILResults.tsx`

```typescript
// LINE 1343-1356
{/* Per-Video Ground Truth Metrics */}
{selectedVideoSummary?.ground_truth_metrics && (
  <Box sx={{ mt: 3 }}>
    <GroundTruthComparisonCards
      precision={selectedVideoSummary.ground_truth_metrics.precision ?? 0}
      recall={selectedVideoSummary.ground_truth_metrics.recall ?? 0}
      f1Score={selectedVideoSummary.ground_truth_metrics.f1_score ?? selectedVideoSummary.ground_truth_metrics.f1Score ?? 0}
      truePositives={selectedVideoSummary.ground_truth_metrics.true_positives ?? selectedVideoSummary.ground_truth_metrics.truePositives ?? 0}
      falsePositives={selectedVideoSummary.ground_truth_metrics.false_positives ?? selectedVideoSummary.ground_truth_metrics.falsePositives ?? 0}
      falseNegatives={selectedVideoSummary.ground_truth_metrics.false_negatives ?? selectedVideoSummary.ground_truth_metrics.falseNegatives ?? 0}
      totalGroundTruth={selectedVideoSummary.ground_truth_metrics.total_ground_truth ?? selectedVideoSummary.ground_truth_metrics.totalGroundTruth}
      title={`Ground Truth Metrics - ${selectedVideoSummary.videoName ?? selectedVideoSummary.video_name ?? 'Selected Video'}`}
    />
  </Box>
)}
```

### Variables Used:
- **`selectedVideoSummary`** - Computed from `useMemo` at line 880-885
- **`selectedVideoSummary.ground_truth_metrics`** - Object containing TP/FP/FN values

### Data Flow:
```
perVideoSummaries (state)
  → selectedVideoSummary (useMemo, line 880-885)
    → selectedVideoSummary.ground_truth_metrics (LIKELY NULL/UNDEFINED)
      → GroundTruthComparisonCards (line 1345-1354)
```

### Why It Shows Zero:
**The conditional check `{selectedVideoSummary?.ground_truth_metrics &&` is FALSE**, so the entire `<GroundTruthComparisonCards>` component is NOT RENDERED AT ALL.

This means:
1. Either `selectedVideoSummary` is null
2. Or `selectedVideoSummary.ground_truth_metrics` is null/undefined
3. The backend API is not populating `ground_truth_metrics` in `per_video_results`

---

## 2. Aggregated Ground Truth Display (Lines 1118-1128)

### Location: `/frontend/src/pages/HILResults.tsx`

```typescript
// LINE 1118-1128
{/* Show GT cards if we have aggregated metrics OR if any GT data exists */}
{(aggregatedMetrics || totalTruePositives > 0 || totalFalsePositives > 0 || totalFalseNegatives > 0) && (
  <GroundTruthComparisonCards
    f1Score={aggregatedF1Score}
    precision={aggregatedPrecision}
    recall={aggregatedRecall}
    truePositives={totalTruePositives}
    falsePositives={totalFalsePositives}
    falseNegatives={totalFalseNegatives}
    title="Aggregated Across All Videos"
  />
)}
```

### Variables Used (from aggregatedMetrics useMemo, lines 637-716):
- **`totalTruePositives`** - Line 655, aggregated from videos
- **`totalFalsePositives`** - Line 656, aggregated from videos
- **`totalFalseNegatives`** - Line 657, aggregated from videos

### Aggregation Logic (LINE 655-657):
```typescript
const totalTP = videos.reduce((sum, v) => sum + (
  v.ground_truth_comparison?.true_positives ??
  v.groundTruthComparison?.truePositives ??
  v.ground_truth_metrics?.true_positives ??
  0
), 0);

const totalFP = videos.reduce((sum, v) => sum + (
  v.ground_truth_comparison?.false_positives ??
  v.groundTruthComparison?.falsePositives ??
  v.ground_truth_metrics?.false_positives ??
  0
), 0);

const totalFN = videos.reduce((sum, v) => sum + (
  v.ground_truth_comparison?.false_negatives ??
  v.groundTruthComparison?.falseNegatives ??
  v.ground_truth_metrics?.false_negatives ??
  0
), 0);
```

### Why It Shows Zero:
**ALL three field paths are returning `undefined` or `null`:**
1. `v.ground_truth_comparison?.true_positives` → undefined
2. `v.groundTruthComparison?.truePositives` → undefined
3. `v.ground_truth_metrics?.true_positives` → undefined

This means the backend API is **not populating ANY of these fields** in the `per_video_results` array.

---

## 3. selectedVideoSummary Calculation (Lines 880-885)

```typescript
const selectedVideoSummary = useMemo(() => {
  if (!selectedVideoId) {
    return null;
  }
  return perVideoSummaries.find(video => (video.videoId ?? video.video_id) === selectedVideoId) ?? null;
}, [perVideoSummaries, selectedVideoId]);
```

### Source:
- **`perVideoSummaries`** (state variable, line 71) - Populated from backend API response

### Where perVideoSummaries is Set:
1. **Line 484** - From `sequenceResults?.perVideoResults` or `sequenceResults?.per_video_results`
2. **Line 117-130** - Updated when ground truth data is loaded
3. **Line 206-220** - Updated when detections are loaded

### Critical Issue:
**The backend API response is NOT including `ground_truth_metrics` or `ground_truth_comparison` in the `per_video_results` array.**

---

## 4. Debug Steps to Find the Issue

### Step 1: Add Console Logs to Check Data
```typescript
// LINE 880 - AFTER selectedVideoSummary calculation
const selectedVideoSummary = useMemo(() => {
  if (!selectedVideoId) {
    return null;
  }
  const summary = perVideoSummaries.find(video => (video.videoId ?? video.video_id) === selectedVideoId) ?? null;

  // 🔍 DEBUG LOG
  console.log('🐛 [GT DEBUG] selectedVideoSummary:', summary);
  console.log('🐛 [GT DEBUG] ground_truth_metrics:', summary?.ground_truth_metrics);
  console.log('🐛 [GT DEBUG] ground_truth_comparison:', summary?.ground_truth_comparison);
  console.log('🐛 [GT DEBUG] groundTruthMetrics:', summary?.groundTruthMetrics);
  console.log('🐛 [GT DEBUG] groundTruthComparison:', summary?.groundTruthComparison);

  return summary;
}, [perVideoSummaries, selectedVideoId]);
```

### Step 2: Log Aggregated Metrics Calculation
```typescript
// LINE 655 - BEFORE aggregation calculation
const videos = (perVideoSummaries && perVideoSummaries.length > 0)
  ? perVideoSummaries
  : (sequenceResults?.per_video_results ?? []);

// 🔍 DEBUG LOG
console.log('🐛 [GT DEBUG] Aggregating from videos:', videos);
videos.forEach((v, idx) => {
  console.log(`🐛 [GT DEBUG] Video ${idx + 1}:`, {
    video_id: v.video_id || v.videoId,
    ground_truth_comparison: v.ground_truth_comparison,
    groundTruthComparison: v.groundTruthComparison,
    ground_truth_metrics: v.ground_truth_metrics,
    groundTruthMetrics: v.groundTruthMetrics
  });
});
```

### Step 3: Log API Response
```typescript
// LINE 407 - AFTER sequence results are loaded
const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
console.log('🐛 [GT DEBUG] Sequence Results API Response:', seqResults);
console.log('🐛 [GT DEBUG] per_video_results:', seqResults.per_video_results);
```

### Step 4: Check Backend API Call
```bash
# In browser console, check the network tab for:
# GET /api/v1/video-sequences/{sequence_id}/results
#
# Look for the response structure:
# - Does per_video_results contain ground_truth_metrics?
# - Does per_video_results contain ground_truth_comparison?
```

---

## 5. Root Cause Analysis

### Primary Issue:
**Backend API is NOT returning `ground_truth_metrics` or `ground_truth_comparison` in the `per_video_results` array.**

### Evidence:
1. Line 1343 condition `{selectedVideoSummary?.ground_truth_metrics &&` is FALSE
2. Line 655-657 aggregation returns 0 for all TP/FP/FN values
3. No console errors indicating data format issues

### Expected Backend Response Structure:
```typescript
{
  per_video_results: [
    {
      video_id: "abc123",
      video_name: "test_video_1.mp4",
      // ❌ MISSING - Backend should include:
      ground_truth_metrics: {
        true_positives: 0,
        false_positives: 193,
        false_negatives: 514,
        precision: 0.0,
        recall: 0.0,
        f1_score: 0.0,
        total_ground_truth: 514
      }
    }
  ]
}
```

---

## 6. Recommended Fix

### Option A: Backend Fix (RECOMMENDED)
**Fix the backend API to include ground truth metrics in per_video_results**

File: `/backend/routers/video_sequences.py` or `/backend/services/video_sequence_orchestrator.py`

The backend should calculate and include `ground_truth_metrics` for each video in the sequence when building the response.

### Option B: Frontend Workaround (TEMPORARY)
**Calculate ground truth metrics in the frontend from available data**

```typescript
// LINE 880 - Enhance selectedVideoSummary calculation
const selectedVideoSummary = useMemo(() => {
  if (!selectedVideoId) {
    return null;
  }
  const summary = perVideoSummaries.find(video => (video.videoId ?? video.video_id) === selectedVideoId) ?? null;

  // 🔧 WORKAROUND: Calculate GT metrics if missing
  if (summary && !summary.ground_truth_metrics && !summary.ground_truth_comparison) {
    const videoGT = videoGroundTruthMap[selectedVideoId] || [];
    const videoDetections = videoDetectionMap[selectedVideoId] || [];

    // Calculate matched detections (those with ground_truth_match_id)
    const matchedDetections = videoDetections.filter(d =>
      (d as any)?.ground_truth_match_id || (d as any)?.groundTruthMatchId
    );

    const truePositives = matchedDetections.length;
    const falsePositives = videoDetections.length - matchedDetections.length;
    const falseNegatives = videoGT.length - matchedDetections.length;
    const totalGT = videoGT.length;

    const precision = (truePositives + falsePositives) > 0
      ? (truePositives / (truePositives + falsePositives)) * 100
      : 0;
    const recall = totalGT > 0
      ? (truePositives / totalGT) * 100
      : 0;
    const f1Score = (precision + recall) > 0
      ? (2 * (precision * recall) / (precision + recall))
      : 0;

    summary.ground_truth_metrics = {
      true_positives: truePositives,
      false_positives: falsePositives,
      false_negatives: falseNegatives,
      total_ground_truth: totalGT,
      precision,
      recall,
      f1_score: f1Score
    };
  }

  return summary;
}, [perVideoSummaries, selectedVideoId, videoGroundTruthMap, videoDetectionMap]);
```

---

## 7. Testing Verification

### After Fix, Verify:
1. ✅ Individual video GT cards appear (line 1343)
2. ✅ Aggregated GT cards show correct totals (line 1118)
3. ✅ TP = number of detections with `ground_truth_match_id`
4. ✅ FP = detections WITHOUT `ground_truth_match_id`
5. ✅ FN = ground truth events NOT matched to any detection
6. ✅ Precision = TP / (TP + FP) × 100
7. ✅ Recall = TP / (TP + FN) × 100
8. ✅ F1 Score = 2 × (Precision × Recall) / (Precision + Recall)

### Console Debug Commands:
```javascript
// In browser console after fix:
console.log('Selected Video Summary:', window.__selectedVideoSummary);
console.log('Ground Truth Metrics:', window.__selectedVideoSummary?.ground_truth_metrics);
console.log('Aggregated Metrics:', window.__aggregatedMetrics);
```

---

## 8. Backend API Investigation

### Check Backend Endpoint:
**File:** `/backend/routers/video_sequences.py`
**Function:** `get_video_sequence_results(sequence_id: str)`

**Expected behavior:**
1. Load all videos in sequence
2. For each video, calculate ground truth metrics
3. Include `ground_truth_metrics` in `per_video_results`

### Backend Query to Check:
```python
# In backend, check if ground truth matching is being calculated
# File: backend/services/ground_truth_matching_service.py

def calculate_per_video_metrics(video_id: str, detections: List, ground_truth: List):
    """
    This function should:
    1. Match detections to ground truth events
    2. Calculate TP, FP, FN
    3. Return metrics object
    """
    matched_detections = [d for d in detections if d.ground_truth_match_id]

    tp = len(matched_detections)
    fp = len(detections) - tp
    fn = len(ground_truth) - tp

    precision = (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0
    recall = (tp / len(ground_truth) * 100) if len(ground_truth) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "total_ground_truth": len(ground_truth),
        "precision": precision,
        "recall": recall,
        "f1_score": f1
    }
```

---

## 9. Summary of Findings

### Bug Location:
- **File:** `/frontend/src/pages/HILResults.tsx`
- **Lines:** 1343 (individual video GT), 1118 (aggregated GT)

### Root Cause:
**Backend API response is missing `ground_truth_metrics` in `per_video_results`**

### Impact:
- Ground truth comparison cards not displayed
- Users cannot see TP/FP/FN metrics
- Validation quality assessment impossible

### Fix Priority: 🔴 **CRITICAL**

### Estimated Fix Time:
- **Backend Fix:** 2-4 hours (calculate and include metrics)
- **Frontend Workaround:** 1-2 hours (calculate from available data)

---

## 10. Next Steps

1. ✅ Verify backend API response structure
2. ✅ Add debug console.log statements
3. ✅ Check if ground truth matching is running
4. ✅ Implement backend fix to include metrics
5. ✅ Test with known session that has GT data
6. ✅ Remove debug logs after verification

---

**Report Generated:** $(date)
**Analyzed By:** Code Implementation Agent
**Priority:** CRITICAL - User cannot see ground truth validation metrics
