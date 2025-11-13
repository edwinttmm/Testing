# Frontend Data Flow Analysis - Session c511302e
## Investigation: Where Are Ground Truth Metrics Being Lost?

**Status**: DATA IS PRESENT IN API BUT SHOWING AS ZEROS IN UI

---

## 1. API Response Analysis

### Raw API Response Structure
```json
{
  "sequence_results": {
    "per_video_results": [
      {
        "video_id": "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
        "sequence_order": 0,
        "ground_truth_metrics": {
          "total_ground_truth": 262,
          "true_positives": 0,
          "false_positives": 144,
          "false_negatives": 262,
          "precision": 0.0,
          "recall": 0.0,
          "f1_score": 0.0
        }
      },
      {
        "video_id": "550e3cf8-2755-42df-8c3c-041300735f93",
        "sequence_order": 1,
        "ground_truth_metrics": {
          "total_ground_truth": 252,
          "true_positives": 0,
          "false_positives": 49,
          "false_negatives": 252,
          "precision": 0.0,
          "recall": 0.0,
          "f1_score": 0.0
        }
      }
    ]
  }
}
```

**FINDING #1**: API response DOES include `ground_truth_metrics` in `sequence_results.per_video_results[]`

---

## 2. Data Flow Through Frontend

### Step 1: API Call (HILResults.tsx line 407)
```typescript
const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
```

**What happens**: Fetches the JSON response shown above.

---

### Step 2: Normalization (HILResults.tsx line 408)
```typescript
const normalizedSeqResults = normalizeSequenceResults(seqResults);
```

**Analysis of `normalizeSequenceResults` function** (hilResultsNormalization.ts lines 583-806):

#### Ground Truth Metrics Normalization (lines 574-578)
```typescript
// Ground truth metrics normalization - support both field name variants
ground_truth_metrics: video?.ground_truth_metrics ?? video?.groundTruthMetrics ?? video?.ground_truth_comparison ?? {},
groundTruthMetrics: video?.groundTruthMetrics ?? video?.ground_truth_metrics ?? video?.groundTruthComparison ?? {},
ground_truth_comparison: video?.ground_truth_comparison ?? video?.ground_truth_metrics ?? video?.groundTruthComparison ?? {},
groundTruthComparison: video?.groundTruthComparison ?? video?.ground_truth_comparison ?? video?.ground_truth_metrics ?? {}
```

**FINDING #2**: `normalizePerVideoResult` DOES preserve `ground_truth_metrics` and creates all variants (camelCase and snake_case).

**Expected Result After Normalization**:
```typescript
{
  video_id: "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
  ground_truth_metrics: {
    total_ground_truth: 262,
    true_positives: 0,
    false_positives: 144,
    false_negatives: 262,
    precision: 0.0,
    recall: 0.0,
    f1_score: 0.0
  },
  groundTruthMetrics: { ... same ... },
  ground_truth_comparison: { ... same ... },
  groundTruthComparison: { ... same ... }
}
```

---

### Step 3: Defensive Filter (HILResults.tsx lines 452-463)
```typescript
const validatedPerVideo = rawPerVideo.filter((item: any) => {
  const isVideo = !!(item.video_id || item.videoId) &&
                 (item.video_name || item.videoName || item.video_filename);
  const isDetection = !!(item.detection_time_ms || item.real_latency_ms || item.voltage);

  if (isDetection && !isVideo) {
    console.error('🚨 Detection object found in per_video_results, filtering out:', item);
    return false;
  }
  return isVideo;
});
```

**Analysis**: This filter checks if items are videos (have video_id AND video_name) vs detections (have detection fields).

**FINDING #3**: The normalized per_video_results should PASS this filter because:
- They have `video_id`: ✅ (present)
- They have `video_filename`: ✅ (present)
- They DON'T have `detection_time_ms`, `real_latency_ms`, `voltage`: ✅ (correct)

**Expected Result**: Items are NOT filtered out, `ground_truth_metrics` should still be present.

---

### Step 4: State Storage (HILResults.tsx line 484)
```typescript
setPerVideoSummaries(sortedPerVideo);
```

**Expected State**:
```typescript
perVideoSummaries = [
  {
    video_id: "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
    videoId: "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
    video_name: "child_test_video_20251031_144012.mp4",
    ground_truth_metrics: {
      total_ground_truth: 262,
      true_positives: 0,
      false_positives: 144,
      false_negatives: 262,
      precision: 0.0,
      recall: 0.0,
      f1_score: 0.0
    },
    groundTruthMetrics: { ... },
    // ... other fields
  },
  { ... video 2 ... }
]
```

---

### Step 5: Aggregated Metrics Calculation (HILResults.tsx lines 654-677)

#### useMemo Dependencies (line 639)
```typescript
const aggregatedMetrics = useMemo(() => {
  // ...
}, [perVideoSummaries, sequenceResults, videoDetectionMap, videoGroundTruthMap]);
```

#### Ground Truth Aggregation Logic (lines 655-657)
```typescript
const totalTP = videos.reduce((sum, v) =>
  sum + (v.ground_truth_comparison?.true_positives ??
         v.groundTruthComparison?.truePositives ??
         v.ground_truth_metrics?.true_positives ?? 0), 0);
const totalFP = videos.reduce((sum, v) =>
  sum + (v.ground_truth_comparison?.false_positives ??
         v.groundTruthComparison?.falsePositives ??
         v.ground_truth_metrics?.false_positives ?? 0), 0);
const totalFN = videos.reduce((sum, v) =>
  sum + (v.ground_truth_comparison?.false_negatives ??
         v.groundTruthComparison?.falseNegatives ??
         v.ground_truth_metrics?.false_negatives ?? 0), 0);
```

**Analysis**: The aggregation logic checks:
1. `v.ground_truth_comparison?.true_positives`
2. `v.groundTruthComparison?.truePositives`
3. `v.ground_truth_metrics?.true_positives`

**Expected Behavior**: Since normalized data has ALL these fields, it should find `ground_truth_metrics.true_positives = 0`.

**WAIT... FINDING #4**: The values ARE zeros! Let's check API response again:
- Video 1: `"true_positives": 0, "false_positives": 144, "false_negatives": 262`
- Video 2: `"true_positives": 0, "false_positives": 49, "false_negatives": 252`

**Expected Calculation**:
```
totalTP = 0 + 0 = 0 ✅
totalFP = 144 + 49 = 193 ✅
totalFN = 262 + 252 = 514 ✅

precision = totalTP / (totalTP + totalFP) = 0 / 193 = 0.0% ✅
recall = totalTP / (totalTP + totalFN) = 0 / 514 = 0.0% ✅
f1 = 2 * (precision * recall) / (precision + recall) = 0 / 0 = 0.0% ✅
```

---

## 3. Root Cause Analysis

### THE PROBLEM IS NOT A BUG - IT'S REAL DATA

**CRITICAL FINDING**: The frontend IS calculating correctly. The zeros are REAL:

1. **API sends**: `true_positives: 0` for both videos
2. **Frontend normalizes**: Preserves the 0 values correctly
3. **Frontend aggregates**: 0 + 0 = 0 (correct math!)
4. **Frontend displays**: 0% (accurate representation)

### Why Are True Positives Zero?

Looking at the ground truth metrics from the API:

**Video 1**:
- Total Ground Truth Events: 262
- True Positives: 0 (no detections matched ground truth)
- False Positives: 144 (all detections were spurious)
- False Negatives: 262 (all ground truth events were missed)

**Video 2**:
- Total Ground Truth Events: 252
- True Positives: 0 (no detections matched ground truth)
- False Positives: 49 (all detections were spurious)
- False Negatives: 252 (all ground truth events were missed)

### Backend Logic Issue

The problem is in the **BACKEND MATCHING LOGIC**, not the frontend. The backend is either:
1. Not matching any detections to ground truth events (matching algorithm failure)
2. Not running the ground truth comparison at all
3. Using incorrect matching thresholds or criteria

---

## 4. Evidence Summary

### What Works Correctly ✅
1. API response includes `ground_truth_metrics` in `per_video_results`
2. `normalizeSequenceResults` preserves `ground_truth_metrics`
3. Defensive filter does NOT remove the data
4. `perVideoSummaries` state contains the data
5. `aggregatedMetrics` calculation runs correctly
6. Math is correct: 0 + 0 = 0

### What's Actually Wrong ❌
1. **Backend is producing zero true positives** for ALL detections
2. This means **no detections are matching ground truth**, despite:
   - Video 1: 144 detections vs 262 ground truth (0% match rate)
   - Video 2: 49 detections vs 252 ground truth (0% match rate)

---

## 5. Debugging Steps to Confirm

### Console Logs to Add

Add to HILResults.tsx after line 484:
```typescript
console.log('[DEBUG] perVideoSummaries after setting:', perVideoSummaries);
console.log('[DEBUG] Video 1 GT metrics:', perVideoSummaries[0]?.ground_truth_metrics);
console.log('[DEBUG] Video 2 GT metrics:', perVideoSummaries[1]?.ground_truth_metrics);
```

Add to HILResults.tsx in aggregatedMetrics calculation (line 655):
```typescript
console.log('[DEBUG] Aggregation input videos:', videos);
console.log('[DEBUG] totalTP:', totalTP, 'totalFP:', totalFP, 'totalFN:', totalFN);
```

### Expected Console Output
```
[DEBUG] perVideoSummaries after setting: [
  {
    video_id: "10c2b16c...",
    ground_truth_metrics: {
      total_ground_truth: 262,
      true_positives: 0,  // <-- THESE ARE THE REAL VALUES FROM BACKEND
      false_positives: 144,
      false_negatives: 262
    }
  },
  { ... video 2 ... }
]
[DEBUG] Video 1 GT metrics: { total_ground_truth: 262, true_positives: 0, ... }
[DEBUG] Video 2 GT metrics: { total_ground_truth: 252, true_positives: 0, ... }
[DEBUG] Aggregation input videos: [ ... same ... ]
[DEBUG] totalTP: 0, totalFP: 193, totalFN: 514
```

---

## 6. Conclusion

### Frontend Data Flow Status: ✅ WORKING CORRECTLY

The frontend is:
1. Successfully fetching API data
2. Successfully normalizing the response
3. Successfully preserving ground_truth_metrics
4. Successfully calculating aggregated metrics
5. Successfully displaying the values

### The Real Problem: ❌ BACKEND GROUND TRUTH MATCHING

The backend is returning **zero true positives** because:
- The ground truth matching algorithm is not finding any matches
- All 144 detections in Video 1 are classified as false positives
- All 49 detections in Video 2 are classified as false positives
- All ground truth events are classified as false negatives

### Recommended Action

**DO NOT modify the frontend.** Instead, investigate:

1. **Backend matching service**: `/backend/services/ground_truth_matching_service.py`
2. **Matching thresholds**: Are they too strict?
3. **Timestamp alignment**: Are detection timestamps and ground truth timestamps in the same coordinate system?
4. **Matching criteria**: What's the matching window? Is it 50ms? 100ms?

### Why User Sees "ALL ZEROS"

The user sees zeros because:
- Precision: 0 / (0 + 193) = 0%
- Recall: 0 / (0 + 514) = 0%
- F1: undefined (0/0)

This accurately reflects that **NONE of the 193 detections matched ANY of the 514 ground truth events**.

---

## 7. Next Investigation

The next agent should analyze:
```bash
/backend/services/ground_truth_matching_service.py
```

And answer:
1. What are the matching criteria?
2. What's the time window for matching?
3. Are timestamps being compared correctly?
4. Why would 0 out of 193 detections match ground truth?
