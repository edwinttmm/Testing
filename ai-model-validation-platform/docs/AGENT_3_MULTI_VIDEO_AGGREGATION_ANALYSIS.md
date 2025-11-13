# Agent 3: Multi-Video Sequence Aggregation Analysis
**Date:** 2025-11-05
**File Analyzed:** `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`
**Lines Focus:** 869-905 (aggregatedMetrics), 1365-1430 (multi-video display)

---

## Executive Summary

**CRITICAL BUG FOUND:** The multi-video aggregation logic has a **lazy-loading race condition** that causes incorrect metric aggregation when detections are not pre-loaded for all videos.

**Impact:** Multi-video sequences show incorrect aggregated ground truth metrics because:
1. Detections are loaded on-demand (per video)
2. Aggregation runs before all video detections are loaded
3. `videoDetectionMap` is initially empty for non-selected videos

**Expected:** 59 total TP across 2 videos
**Actual:** Only TP from first/selected video

---

## Analysis Findings

### ✅ GOOD: Ground Truth Aggregation Logic (Lines 885-887)

```typescript
const totalTP = videos.reduce((sum, v) =>
  sum + (v.ground_truth_comparison?.true_positives ??
         v.groundTruthComparison?.truePositives ??
         v.ground_truth_metrics?.true_positives ?? 0), 0);
```

**Status:** ✅ CORRECT - Uses backend data from `per_video_results[]`

The aggregation correctly:
- Pulls from `ground_truth_comparison` (backend field)
- Falls back to multiple field name variants
- Does NOT recalculate from detections

### ❌ CRITICAL BUG: Detection Count Aggregation (Lines 896-901)

```typescript
const totalDetections = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  const fallback = v.total_detections ?? v.totalDetections ??
                   v.detection_count ?? v.detectionCount ?? 0;
  return sum + (mapCount || fallback);
}, 0);
```

**Problem:** Uses `videoDetectionMap[currentId]` which is **lazy-loaded**

**Race Condition Flow:**
1. Page loads → `loadHILResults()` runs
2. Backend returns `per_video_results[]` with ALL metrics
3. Frontend sets `videoDetectionMap = {}` (empty!)
4. Frontend loads detections for FIRST video only
5. `aggregatedMetrics` memo calculates with partial data
6. User switches videos → detections load on-demand
7. Metrics don't re-aggregate because backend data doesn't change

**Root Cause:**
```typescript
// Line 721-723 in loadHILResults()
const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};
setVideoDetectionMap(detectionMap);  // ❌ STARTS EMPTY

// Line 734-737 - Only loads FIRST video
if (isSequence && sortedPerVideo.length > 1) {
  await loadDetectionsForVideo(firstVideoId);  // ❌ ONLY ONE VIDEO
}
```

### ❌ CRITICAL BUG: effectivePerVideoSummaries Recalculation (Lines 229-306)

```typescript
const effectivePerVideoSummaries = useMemo(() => {
  // ...
  return sourceList.map((video) => {
    const currentId = video.videoId ?? video.video_id ?? video.id;
    const detections = currentId ? (videoDetectionMap[currentId] ?? []) : [];
    const groundTruth = currentId ? (videoGroundTruthMap[currentId] ?? []) : [];

    // Lines 258-261: Fallback recalculation
    const fallbackMetrics = detections.length > 0 || groundTruth.length > 0
      ? createMetricsFromDetections(detections, groundTruth)  // ❌ RECALCULATES
      : null;
  });
}, [perVideoSummaries, sequenceResults, videoDetectionMap, videoGroundTruthMap]);
```

**Problem:** Even though backend provides correct metrics, this code:
1. Recalculates metrics from client-side detections
2. Uses `createMetricsFromDetections()` (line 260) as fallback
3. Depends on `videoDetectionMap` (lazy-loaded)

**Why This is Wrong:**
- Backend already calculated and returned correct metrics
- Client-side recalculation introduces race conditions
- Lazy-loading makes counts inconsistent

### ⚠️ CONCERN: Multi-Video Timing Display (Lines 1365-1430)

```typescript
<Typography variant="body2" color="text.secondary">
  Total Duration: {(sequenceResults.sequence_duration_seconds ??
                    sequenceResults.sequenceDurationSeconds ?? 0).toFixed(1)}s
</Typography>
```

**Status:** ⚠️ PARTIALLY CORRECT

**Uses:**
- `sequence_duration_seconds` from backend (correct)
- Aggregated latency metrics (correct)
- Per-video duration for visualization (correct)

**Missing:**
- Does NOT display `video_start_time` and `video_end_time` from backend
- Could show actual timestamps: "Video 1: 0.0s-30.5s, Video 2: 30.5s-60.0s"
- Current display only shows durations, not absolute timing

**Not a bug, but missed opportunity for clarity**

---

## Root Cause Analysis

### The Lazy-Loading Architecture Flaw

**Current Flow:**
```
1. loadHILResults() → Backend returns complete per_video_results[]
2. Frontend discards detection data, keeps only summaries
3. Frontend sets videoDetectionMap = {} (empty)
4. Frontend loads detections for FIRST video only
5. aggregatedMetrics calculates with incomplete data
6. User switches video → NEW detections load
7. Aggregation doesn't update (backend data unchanged)
```

**Why This Happens:**
```typescript
// Line 719-723 - THROWS AWAY detection data
// Backend now handles filtering by video_id, so we rely on lazy loading
// via loadDetectionsForVideo
// Start with empty map - detections will be loaded on-demand when video is selected
const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};
```

This comment explains the **WRONG STRATEGY:**
- Backend filters by video_id → Frontend thinks it needs to load per-video
- Frontend starts with empty map
- Frontend loads on-demand
- Aggregation fails because data isn't available

**Correct Strategy:**
- Backend already has ALL detections
- Frontend should load ALL detections upfront for sequences
- Map detections by video_id for filtering
- Aggregation works because all data is present

---

## Bugs Identified

### Bug #1: Lazy-Loaded Detection Counts in Aggregation
**Location:** Lines 896-901
**Severity:** 🔴 CRITICAL
**Impact:** Multi-video sequences show incorrect total detection counts

**Example:**
```
Video 1: 30 detections (loaded)
Video 2: 29 detections (NOT loaded)
Aggregated: 30 (should be 59)
```

**Fix Required:**
```typescript
// BEFORE (lines 896-901)
const totalDetections = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  const fallback = v.total_detections ?? v.totalDetections ?? ...;
  return sum + (mapCount || fallback);  // ❌ Uses lazy-loaded map
}, 0);

// AFTER (proposed fix)
const totalDetections = videos.reduce((sum, v) => {
  // ALWAYS use backend data first (it's complete)
  const backendCount = v.total_detections ?? v.totalDetections ??
                       v.detection_count ?? v.detectionCount ?? 0;

  // Only use map if backend data is missing
  if (backendCount > 0) return sum + backendCount;

  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  return sum + mapCount;
}, 0);
```

### Bug #2: Unnecessary Metric Recalculation in effectivePerVideoSummaries
**Location:** Lines 258-261
**Severity:** 🟡 MAJOR
**Impact:** Recalculates metrics from incomplete client-side data

**Current Code:**
```typescript
const fallbackMetrics = detections.length > 0 || groundTruth.length > 0
  ? createMetricsFromDetections(detections, groundTruth)  // ❌ RECALCULATES
  : null;

const selectedMetrics = hasExistingValues
  ? existingNormalized
  : fallbackMetrics ?? existingNormalized;  // ❌ May use recalculated
```

**Why This is Wrong:**
- Backend already calculated metrics
- Client-side recalculation uses lazy-loaded data
- Introduces inconsistency

**Fix Required:**
```typescript
// Remove fallback recalculation - trust backend data
const selectedMetrics = existingNormalized;

// If backend data is missing, that's an error - don't try to fix it client-side
if (!selectedMetrics) {
  console.error(`Missing ground truth metrics for video ${currentId}`);
  return video;  // Return original without modification
}
```

### Bug #3: Initial Detection Map Empty for Sequences
**Location:** Lines 719-737
**Severity:** 🔴 CRITICAL
**Impact:** Aggregation runs before data is loaded

**Current Code:**
```typescript
// Line 721-723
const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};
setVideoDetectionMap(detectionMap);  // ❌ STARTS EMPTY

// Line 734-735
if (isSequence && sortedPerVideo.length > 1) {
  await loadDetectionsForVideo(firstVideoId);  // ❌ ONLY FIRST VIDEO
}
```

**Fix Required:**
```typescript
// For multi-video sequences, preload ALL video detections upfront
if (isSequence && sortedPerVideo.length > 1) {
  console.log('🔄 Preloading detections for all videos in sequence');

  const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};

  // Load all videos in parallel
  await Promise.all(
    sortedPerVideo.map(async (video) => {
      const videoId = video.video_id ?? video.videoId;
      if (videoId) {
        const response = await apiService.getDetectionEvents(sessionId, videoId);
        const detections = normalizeDetectionEvents(response?.data?.detection_events ?? []);
        detectionMap[videoId] = detections;
      }
    })
  );

  setVideoDetectionMap(detectionMap);

  // Also load ground truth for all videos
  await Promise.all(
    sortedPerVideo.map(video => loadGroundTruthData(video.video_id ?? video.videoId))
  );

  // Set selected video AFTER all data is loaded
  const firstVideoId = sortedPerVideo[0].video_id ?? sortedPerVideo[0].videoId;
  setSelectedVideoId(firstVideoId);
}
```

---

## Correct Data Flow (Proposed)

### Step 1: Backend Provides Complete Data
✅ Already working - backend returns:
```json
{
  "per_video_results": [
    {
      "video_id": "...",
      "ground_truth_comparison": {
        "true_positives": 30,
        "false_positives": 0,
        "false_negatives": 0
      },
      "total_detections": 30
    },
    {
      "video_id": "...",
      "ground_truth_comparison": {
        "true_positives": 29,
        "false_positives": 0,
        "false_negatives": 0
      },
      "total_detections": 29
    }
  ]
}
```

### Step 2: Frontend Loads All Detection Details (NEEDS FIX)
❌ Currently: Loads first video only
✅ Should: Load all videos in parallel

```typescript
// Preload ALL video detections for aggregation
const allDetectionPromises = per_video_results.map(video =>
  apiService.getDetectionEvents(sessionId, video.video_id)
);
const allDetections = await Promise.all(allDetectionPromises);
```

### Step 3: Frontend Aggregates Using Backend Metrics (NEEDS FIX)
✅ Ground truth metrics: Already correct
❌ Detection counts: Uses lazy-loaded map
❌ Recalculation: Unnecessary fallback

**Fix:** Always prioritize backend data over client-side maps

---

## Expected Impact of Fixes

### Before Fixes:
```
Session 463b7ec5 (2 videos):
- Video 1: 30 detections shown (loaded)
- Video 2: 29 detections shown (NOT loaded)
- Aggregated Total: 30 detections (WRONG)
- Ground Truth Aggregated: Correct (uses backend)
```

### After Fixes:
```
Session 463b7ec5 (2 videos):
- Video 1: 30 detections (preloaded)
- Video 2: 29 detections (preloaded)
- Aggregated Total: 59 detections (CORRECT)
- Ground Truth Aggregated: Correct (uses backend)
```

---

## Additional Observations

### Video Timing Display Enhancement (Optional)

**Current:**
```
Total Duration: 60.0s
```

**Could Show:**
```
Total Duration: 60.0s
Video 1: 0.0s - 30.5s (30.5s duration)
Video 2: 30.5s - 60.0s (29.5s duration)
```

**Data Available from Backend:**
```typescript
per_video_results[0].video_start_time  // 0.0
per_video_results[0].video_end_time    // 30.5
per_video_results[1].video_start_time  // 30.5
per_video_results[1].video_end_time    // 60.0
```

**Not a bug, but would improve user understanding of sequence timing**

---

## Summary of Required Fixes

### Priority 1: Critical Fixes
1. **Preload all video detections** for multi-video sequences (lines 719-737)
2. **Prioritize backend data** in aggregation (lines 896-907)
3. **Remove fallback recalculation** from effectivePerVideoSummaries (lines 258-261)

### Priority 2: Code Quality
4. Remove `createMetricsFromDetections()` usage for sequences
5. Add console warnings when backend data is missing
6. Add loading indicators during parallel preload

### Priority 3: Enhancement
7. Display video timing ranges using `video_start_time`/`video_end_time`

---

## Testing Checklist

After fixes are applied, verify:

- [ ] Multi-video sequence loads all detections upfront
- [ ] Aggregated metrics show correct total (e.g., 59 not 30)
- [ ] Video switching is instant (data already loaded)
- [ ] Console shows "Preloading detections for all videos"
- [ ] Backend data is preferred over client calculations
- [ ] No "undefined" or null errors in aggregation
- [ ] UI shows correct "Videos in Sequence" count
- [ ] Ground truth comparison remains accurate

---

## Code Snippets for Implementation

### Fix 1: Preload All Detections (Replace lines 719-737)

```typescript
if (isSequence && sortedPerVideo.length > 1) {
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
        groundTruthMap[videoId] = gtResponse.data.ground_truth_events;
      }

      console.log(`✅ Loaded ${detections.length} detections for video ${videoId}`);
    } catch (error) {
      console.error(`Failed to load data for video ${videoId}:`, error);
      detectionMap[videoId] = [];
      groundTruthMap[videoId] = [];
    }
  });

  await Promise.all(loadPromises);

  setVideoDetectionMap(detectionMap);
  setVideoGroundTruthMap(groundTruthMap);

  const firstVideoId = sortedPerVideo[0].video_id ?? sortedPerVideo[0].videoId;
  setSelectedVideoId(firstVideoId);
  setVideoId(firstVideoId);
}
```

### Fix 2: Prioritize Backend Data in Aggregation (Replace lines 896-907)

```typescript
// Aggregate detection metrics - ALWAYS use backend data first
const totalDetections = videos.reduce((sum, v) => {
  // Backend data is the source of truth
  const backendCount = v.total_detections ?? v.totalDetections ??
                       v.detection_count ?? v.detectionCount ?? 0;

  if (backendCount > 0) {
    return sum + backendCount;
  }

  // Fallback to map only if backend data missing (shouldn't happen)
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  console.warn(`Using map count for video ${currentId}: ${mapCount} (backend data missing)`);
  return sum + mapCount;
}, 0);

const totalGroundTruthEvents = videos.reduce((sum, v) => {
  // Backend data is the source of truth
  const backendCount = v.ground_truth_events_available ??
                       v.groundTruthEventsAvailable ??
                       v.ground_truth_count ??
                       v.groundTruthCount ??
                       v.ground_truth_metrics?.total_ground_truth ?? 0;

  if (backendCount > 0) {
    return sum + backendCount;
  }

  // Fallback to map only if backend data missing
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoGroundTruthMap[currentId]?.length ?? 0) : 0;
  console.warn(`Using map count for GT video ${currentId}: ${mapCount} (backend data missing)`);
  return sum + mapCount;
}, 0);
```

### Fix 3: Remove Recalculation from effectivePerVideoSummaries (Lines 258-275)

```typescript
// Remove lines 258-261 (fallback recalculation)
// Replace with direct use of backend data

const existingMetricsRaw =
  video.ground_truth_metrics ??
  video.groundTruthMetrics ??
  video.ground_truth_comparison ??
  video.groundTruthComparison ??
  null;

const selectedMetrics = normalizeGroundTruthMetrics(existingMetricsRaw);

if (!selectedMetrics) {
  console.error(`Missing ground truth metrics for video ${currentId}`);
  return video;  // Return original without modification
}

// Use backend metrics directly - no recalculation needed
const metrics = selectedMetrics;
```

---

## Conclusion

**Status:** 🔴 CRITICAL BUGS FOUND

The multi-video aggregation has a fundamental architectural flaw where:
1. Backend provides complete metrics
2. Frontend implements lazy-loading for detections
3. Aggregation runs before all data is loaded
4. Metrics show incorrect totals

**Recommendation:** Implement all Priority 1 fixes immediately. The lazy-loading strategy is incompatible with aggregation requirements. For multi-video sequences, ALL video data must be preloaded before aggregation.

**After fixes:** Multi-video sequences will show correct aggregated metrics matching backend calculations.
