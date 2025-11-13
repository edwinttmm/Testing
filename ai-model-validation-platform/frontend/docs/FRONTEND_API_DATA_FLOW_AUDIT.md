# Frontend API Data Flow Audit - Multi-Video Sequence Issue

**Session ID:** 8cb122e4-79e9-4c15-8938-18f2d3eadfb8
**Sequence ID:** 52579bd0-1512-4c77-973a-1d3671b83d42
**Component:** HILResults.tsx
**Date:** 2025-11-05

## Executive Summary

The backend API `/api/video-sequences/{sequenceId}/results` returns **CORRECT** data with:
- `perVideoResults` array containing 2 videos
- Each video has `ground_truth_comparison` with 97 TP, 100% F1 score
- Each video has `detectionEvents` array

However, the frontend displays **WRONG** data:
- 0% F1 score
- "Unknown" video names
- 0ms latency
- Missing detection counts

## Root Cause Analysis

### Issue #1: Backend Data is Correct BUT Frontend Consumes It Incorrectly

**Backend API Endpoint Called:**
```typescript
// Line 660: HILResults.tsx
const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
```

**API Implementation:**
```typescript
// api.ts:1204-1212
async getVideoSequenceResults(sequenceId: string): Promise<any> {
  try {
    const response = await this.api.get(`/api/video-sequences/${sequenceId}/results`);
    return response.data;
  } catch (error: unknown) {
    console.warn(`Video sequence results fetch failed for sequence ${sequenceId}:`, error);
    throw error;
  }
}
```

✅ **This endpoint IS correct and returns proper data**

### Issue #2: Data Structure Mapping Problem

**Backend Returns:**
```json
{
  "perVideoResults": [
    {
      "video_id": "xxx",
      "video_name": "actual_name.mp4",
      "ground_truth_comparison": {
        "true_positives": 97,
        "false_positives": 0,
        "false_negatives": 0,
        "precision": 100,
        "recall": 100,
        "f1_score": 100
      },
      "detectionEvents": [...],
      "total_detections": 97,
      "average_latency_ms": 45.2
    },
    // ... video 2
  ]
}
```

**Frontend Expects (Line 703-707):**
```typescript
const rawPerVideo = (
  effectiveSeqResults?.perVideoResults ??
  effectiveSeqResults?.per_video_results ??
  []
) as PerVideoResult[];
```

✅ **Mapping IS correct - checks both camelCase and snake_case**

### Issue #3: The Real Problem - effectivePerVideoSummaries Logic

**Line 247-336: effectivePerVideoSummaries useMemo Hook**

This is where the corruption happens:

```typescript
const effectivePerVideoSummaries = useMemo(() => {
  const sourceList: any[] =
    (perVideoSummaries && perVideoSummaries.length > 0
      ? perVideoSummaries
      : sequenceResults?.per_video_results) ?? [];

  if (!sourceList.length) {
    return [];
  }

  return sourceList.map((video) => {
    const currentId = video.videoId ?? video.video_id ?? video.id;
    const detections = currentId ? (videoDetectionMap[currentId] ?? []) : [];
    const groundTruth = currentId ? (videoGroundTruthMap[currentId] ?? []) : [];

    // CRITICAL FIX: Always prefer backend ground_truth_comparison over frontend recalculation
    const existingMetricsRaw =
      video.ground_truth_comparison ??
      video.groundTruthComparison ??
      video.ground_truth_metrics ??
      video.groundTruthMetrics ??
      null;

    const existingNormalized = normalizeGroundTruthMetrics(existingMetricsRaw);

    // Check if backend provided any ground truth data at all
    const hasBackendGroundTruthData = !!existingNormalized && (
      existingNormalized.true_positives > 0 ||
      existingNormalized.false_positives > 0 ||
      existingNormalized.false_negatives > 0 ||
      existingNormalized.total_ground_truth > 0 ||
      existingNormalized.precision > 0 ||
      existingNormalized.recall > 0
    );

    console.log(`[effectivePerVideoSummaries] Video ${currentId}: Backend GT data=${hasBackendGroundTruthData}`, existingNormalized);

    // ONLY use frontend recalculation if backend provided NO ground truth data at all
    const selectedMetrics = hasBackendGroundTruthData
      ? existingNormalized
      : existingNormalized; // Never use createMetricsFromDetections()

    if (!selectedMetrics) {
      return video;  // ❌ BUG: Returns video WITHOUT enriched metrics
    }

    const metrics = mergeGroundTruthMetrics(existingNormalized, selectedMetrics);
    if (!metrics) {
      return video;  // ❌ BUG: Returns video WITHOUT enriched metrics
    }

    // ... rest of enrichment logic
  });
}, [perVideoSummaries, sequenceResults, videoDetectionMap, videoGroundTruthMap]);
```

### Issue #4: Race Condition in Data Loading

**Line 741-817: Multi-Video Sequence Loading**

```typescript
if (hasSequence && detectedSequenceId) {
  console.log('Multi-video sequence detected:', detectedSequenceId);
  setIsSequence(true);

  try {
    const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
    const normalizedSeqResults = normalizeSequenceResults(seqResults);
    const effectiveSeqResults = normalizedSeqResults ?? seqResults;
    setSequenceResults(effectiveSeqResults);  // ✅ Correct backend data stored

    // ... 60 lines of processing

    const rawPerVideo = (
      effectiveSeqResults?.perVideoResults ??
      effectiveSeqResults?.per_video_results ??
      []
    ) as PerVideoResult[];

    setPerVideoSummaries(sortedPerVideo);  // ✅ Correct data stored

    // CRITICAL FIX: For multi-video sequences, preload ALL detections upfront
    if (isSequence && sortedPerVideo.length > 1) {  // ❌ BUG: isSequence was just set, may not be true yet
      console.log(`🔄 Preloading detections for ${sortedPerVideo.length} videos in sequence`);

      const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};
      const groundTruthMap: Record<string, any[]> = {};

      // Load all videos in parallel
      const loadPromises = sortedPerVideo.map(async (video) => {
        const videoId = video.video_id ?? video.videoId;
        if (!videoId) return;

        try {
          // Load detections
          const detResponse = await apiService.getDetectionEvents(sessionId, videoId);
          const detections = normalizeDetectionEvents(detResponse?.data?.detection_events ?? []);
          detectionMap[videoId] = detections;

          // Load ground truth
          const gtResponse = await apiService.getGroundTruthEvents(videoId);
          if (gtResponse?.success && gtResponse?.data?.ground_truth_events) {
            const rawEvents = gtResponse.data.ground_truth_events;
            // ... deduplication logic
            groundTruthMap[videoId] = dedupedEvents;
          }
        } catch (error) {
          console.error(`Failed to load data for video ${videoId}:`, error);
          detectionMap[videoId] = [];
          groundTruthMap[videoId] = [];
        }
      });

      await Promise.all(loadPromises);

      setVideoDetectionMap(detectionMap);  // ✅ Async detections loaded
      setVideoGroundTruthMap(groundTruthMap);  // ✅ Async GT loaded
    }
  }
}
```

**The Race Condition:**
1. Backend data arrives with correct `perVideoResults`
2. `setPerVideoSummaries(sortedPerVideo)` stores correct data
3. Async loading starts for detections/GT (takes time)
4. `effectivePerVideoSummaries` useMemo runs BEFORE async data arrives
5. `videoDetectionMap` is empty → `detections.length = 0`
6. `videoGroundTruthMap` is empty → `groundTruth.length = 0`
7. Metrics calculation returns empty/zero values

## Specific Issues Found

### 1. API Endpoint Usage ✅ CORRECT
**Line 660:**
```typescript
const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
```
- Calls `/api/video-sequences/{sequenceId}/results`
- Backend returns correct data structure

### 2. perVideoResults Consumption ✅ PARTIALLY CORRECT
**Line 703-707:**
```typescript
const rawPerVideo = (
  effectiveSeqResults?.perVideoResults ??
  effectiveSeqResults?.per_video_results ??
  []
) as PerVideoResult[];
```
- Correctly reads `perVideoResults` from backend
- Handles both naming conventions

### 3. ground_truth_comparison Usage ❌ INCORRECT
**Line 262-290:**
```typescript
const existingMetricsRaw =
  video.ground_truth_comparison ??
  video.groundTruthComparison ??
  video.ground_truth_metrics ??
  video.groundTruthMetrics ??
  null;

const existingNormalized = normalizeGroundTruthMetrics(existingMetricsRaw);

const hasBackendGroundTruthData = !!existingNormalized && (
  existingNormalized.true_positives > 0 ||
  existingNormalized.false_positives > 0 ||
  existingNormalized.false_negatives > 0 ||
  existingNormalized.total_ground_truth > 0 ||
  existingNormalized.precision > 0 ||
  existingNormalized.recall > 0
);
```

**Problem:** The check `hasBackendGroundTruthData` will be FALSE if backend sent correct data but the async loading hasn't completed yet.

### 4. Aggregated Metrics Calculation ❌ INCORRECT TIMING
**Line 945-1059:**
```typescript
const aggregatedMetrics = useMemo(() => {
  if (!isSequence) {
    return null;
  }

  const videos = effectivePerVideoSummaries;

  if (!videos.length) {
    console.warn('[aggregatedMetrics] No videos available for aggregation');
    return null;
  }

  // Aggregate ground truth metrics from backend ground_truth_comparison
  const totalTP = videos.reduce((sum, v) => {
    const tp = v.ground_truth_comparison?.true_positives ??
               v.groundTruthComparison?.truePositives ??
               v.ground_truth_metrics?.true_positives ?? 0;
    console.log(`[aggregatedMetrics] Video ${v.video_id}: TP=${tp}`);
    return sum + tp;
  }, 0);
}, [isSequence, sequenceResults, perVideoSummaries, videoDetectionMap, videoGroundTruthMap, effectivePerVideoSummaries]);
```

**Problem:** This runs IMMEDIATELY when state changes, but async data loading (lines 752-794) hasn't completed yet.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. API Call (Line 660)                                      │
│    apiService.getVideoSequenceResults(sequenceId)           │
│    ↓                                                         │
│    Returns CORRECT DATA:                                    │
│    {                                                         │
│      perVideoResults: [                                     │
│        {                                                     │
│          video_id: "xxx",                                   │
│          video_name: "actual.mp4",                          │
│          ground_truth_comparison: {TP: 97, F1: 100}        │
│        }                                                     │
│      ]                                                       │
│    }                                                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. State Update (Line 663, 741)                             │
│    setSequenceResults(effectiveSeqResults) ✅               │
│    setPerVideoSummaries(sortedPerVideo) ✅                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Async Loading Starts (Line 752-794)                      │
│    Promise.all([                                            │
│      loadDetections(video1),  ⏳ Takes 100-500ms           │
│      loadGroundTruth(video1), ⏳ Takes 100-500ms           │
│      loadDetections(video2),  ⏳ Takes 100-500ms           │
│      loadGroundTruth(video2)  ⏳ Takes 100-500ms           │
│    ])                                                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ❌ RACE CONDITION ❌
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. effectivePerVideoSummaries useMemo Runs (Line 247)      │
│    BEFORE async data arrives                                │
│    ↓                                                         │
│    videoDetectionMap = {} ← EMPTY                          │
│    videoGroundTruthMap = {} ← EMPTY                        │
│    ↓                                                         │
│    hasBackendGroundTruthData = FALSE ← WRONG               │
│    ↓                                                         │
│    Returns video WITHOUT enriched metrics                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. aggregatedMetrics useMemo Runs (Line 945)               │
│    effectivePerVideoSummaries has NO metrics                │
│    ↓                                                         │
│    totalTP = 0 (should be 194)                             │
│    totalFP = 0 (should be 0)                               │
│    totalFN = 0 (should be 0)                               │
│    aggregatedF1Score = 0 (should be 100)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. UI Renders with WRONG Data                               │
│    - 0% F1 Score (should be 100%)                          │
│    - "Unknown" video names (should be actual names)         │
│    - 0ms latency (should be ~45ms)                         │
│    - 0 detections (should be 97 per video)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Async Loading Completes (500ms later)                    │
│    setVideoDetectionMap(detectionMap) ✅                   │
│    setVideoGroundTruthMap(groundTruthMap) ✅               │
│    ↓                                                         │
│    effectivePerVideoSummaries re-runs                       │
│    aggregatedMetrics re-runs                                │
│    ↓                                                         │
│    UI SHOULD update... but may not trigger re-render       │
└─────────────────────────────────────────────────────────────┘
```

## Required Fixes

### Fix #1: Use Backend Data Directly, Skip Async Enrichment

**Problem:** Lines 752-794 load detections/GT asynchronously, causing race condition

**Solution:** Trust backend `perVideoResults` data, don't re-fetch:

```typescript
// AFTER Line 741: setPerVideoSummaries(sortedPerVideo)

// ❌ REMOVE async loading block (lines 752-794)
// if (isSequence && sortedPerVideo.length > 1) {
//   const loadPromises = sortedPerVideo.map(async (video) => { ... });
// }

// ✅ ADD: Use backend data directly
setVideoDetectionMap({}); // Clear map, rely on backend counts
setVideoGroundTruthMap({}); // Clear map, rely on backend counts

// Set first video as selected
const firstVideoId = sortedPerVideo[0].video_id ?? sortedPerVideo[0].videoId;
setSelectedVideoId(firstVideoId);
setVideoId(firstVideoId);
```

### Fix #2: Simplify effectivePerVideoSummaries - Trust Backend

**Problem:** Lines 247-336 try to enrich data from empty maps

**Solution:** Return backend data as-is:

```typescript
const effectivePerVideoSummaries = useMemo(() => {
  const sourceList: any[] =
    (perVideoSummaries && perVideoSummaries.length > 0
      ? perVideoSummaries
      : sequenceResults?.per_video_results) ?? [];

  if (!sourceList.length) {
    return [];
  }

  // ✅ TRUST BACKEND DATA - just normalize field names
  return sourceList.map((video) => {
    const videoName = video.videoName ?? video.video_name ?? video.video_filename ?? video.videoFilename ?? 'Unknown';

    // Backend already provides ground_truth_comparison - just ensure both naming conventions
    const gtComparison = video.ground_truth_comparison ?? video.groundTruthComparison;

    return {
      ...video,
      videoName,
      video_name: videoName,
      ground_truth_comparison: gtComparison,
      groundTruthComparison: gtComparison,
      // Preserve all other backend fields as-is
    };
  });
}, [perVideoSummaries, sequenceResults]);
```

### Fix #3: aggregatedMetrics - Read from Backend Directly

**Problem:** Lines 963-975 try to read from effectivePerVideoSummaries which may be empty

**Solution:** Read from backend data first, fallback to enriched:

```typescript
const aggregatedMetrics = useMemo(() => {
  if (!isSequence) {
    return null;
  }

  // ✅ PREFER direct backend data
  const videos = perVideoSummaries.length > 0
    ? perVideoSummaries
    : (sequenceResults?.perVideoResults ?? sequenceResults?.per_video_results ?? []);

  if (!videos.length) {
    console.warn('[aggregatedMetrics] No videos available for aggregation');
    return null;
  }

  // Aggregate from backend ground_truth_comparison directly
  const totalTP = videos.reduce((sum, v) => {
    const tp = v.ground_truth_comparison?.true_positives ??
               v.groundTruthComparison?.truePositives ?? 0;
    return sum + tp;
  }, 0);
  // ... rest of aggregation
}, [isSequence, perVideoSummaries, sequenceResults]);
```

## Line-by-Line Changes Needed

### File: /home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx

1. **Line 247-336:** Simplify `effectivePerVideoSummaries` to trust backend data
2. **Line 752-794:** Remove async detection/GT loading for sequences (causes race condition)
3. **Line 945-1059:** Update `aggregatedMetrics` to read directly from backend data
4. **Line 963-975:** Change to read from `perVideoSummaries` first, not `effectivePerVideoSummaries`

## Testing Verification

After fixes, verify:

```bash
# 1. Load HIL Results page for sequence 52579bd0-1512-4c77-973a-1d3671b83d42
# 2. Check browser console for:
console.log('[aggregatedMetrics] Video ${v.video_id}: TP=${tp}');
# Should show: TP=97 for both videos

# 3. Check UI displays:
# - F1 Score: 100% (not 0%)
# - Video names: actual filenames (not "Unknown")
# - Latency: ~45ms (not 0ms)
# - Detection counts: 97 per video (not 0)
```

## Summary

**Root Cause:** Race condition between backend data arrival and async enrichment loading
**Impact:** Frontend displays zeros/unknowns despite backend providing correct data
**Solution:** Trust backend `perVideoResults` data directly, skip async re-fetching
**Estimated Fix Time:** 30 minutes
**Risk Level:** LOW (simplifies logic, removes unnecessary async complexity)
