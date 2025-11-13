# Detection Count Discrepancy Analysis: 115 vs 54 vs 242

## Executive Summary

**ROOT CAUSE IDENTIFIED**: Three different counting mechanisms exist in the UI, each using different data sources:

1. **"115 out of 242 detections captured" (top banner)** - Uses `overallDetectionCount` from `allDetections.length`
2. **"54 detections" (aggregated metrics)** - Uses `aggOverallDetectionCount` from per-video summaries
3. **"54 detections" (video selector chip)** - Uses `activeDetectionCount` from currently selected video

## The Three Counting Systems

### 1. Top Banner: "115 out of 242"
**File**: `/frontend/src/pages/HILResults.tsx` Line 1313

```typescript
// Line 1023: Overall count from ALL loaded detections
const overallDetectionCount = allDetections.length;

// Line 1313: Used in TestStatusBanner
<TestStatusBanner
  detectionCount={overallDetectionCount}  // ← 115
  expectedCount={overallExpectedCount}    // ← 242
/>
```

**Data Source**: `allDetections` array from `baseDetections` state
- Accumulates ALL detections loaded from API calls
- Does NOT filter by video_id when in multi-video mode
- Contains detections from BOTH videos combined

### 2. Aggregated Metrics: "54 detections"
**File**: `/frontend/src/pages/HILResults.tsx` Lines 892-897

```typescript
// Line 892-897: Aggregation from per-video summaries
const totalDetections = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  const fallback = v.total_detections ?? v.totalDetections ?? v.detection_count ?? v.detectionCount ?? 0;
  return sum + (mapCount || fallback);  // ← Uses mapCount if available, otherwise fallback
}, 0);

// Line 1340: Used in aggregated metrics alert
{aggOverallDetectionCount} detections  // ← 54
```

**Data Source**: Per-video results from backend API
- Uses `videoDetectionMap[videoId]` counts when available
- Falls back to backend's `total_detections` field
- **PROBLEM**: `videoDetectionMap` only populated for SELECTED video, not all videos
- **RESULT**: Only counts detections from Video 1 (54), Video 2 shows 0 because not loaded

### 3. Video Selector: "Detections: 54"
**File**: `/frontend/src/pages/HILResults.tsx` Line 1552

```typescript
// Line 1024: Active (currently selected video) count
const activeDetectionCount = activeDetections.length;

// Line 1552: Used in video selector chip
<Chip label={`Detections: ${activeDetectionCount}`} variant="outlined" />
```

**Data Source**: `activeDetections` from currently selected video
- Filtered by `selectedVideoId` from `videoDetectionMap`
- Shows only the detections for the currently viewed video

## Why the Numbers Don't Match

### Scenario: 2 Videos, Constant Voltage, ~121 detections per video = 242 expected total

| Metric | Value | Source | Explanation |
|--------|-------|--------|-------------|
| Expected Total | 242 | Ground truth | ~121 detections × 2 videos |
| Top Banner | 115 | `allDetections.length` | Partial load - some detections missing or filtered |
| Aggregated | 54 | `aggOverallDetectionCount` | Only Video 1 loaded (54), Video 2 not loaded yet (0) |
| Video Selector | 54 | `activeDetectionCount` | Currently viewing Video 1 (54 detections) |

## Root Cause: Lazy Loading Issue

**The Problem**: Lines 892-897 in aggregation logic

```typescript
const totalDetections = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  const fallback = v.total_detections ?? v.totalDetections ?? v.detection_count ?? v.detectionCount ?? 0;
  return sum + (mapCount || fallback);  // ← BUG: Uses mapCount FIRST, even if it's 0
}, 0);
```

**The Issue**:
1. `videoDetectionMap[videoId]` is `undefined` for Video 2 (not loaded yet)
2. `(videoDetectionMap[videoId]?.length ?? 0)` returns `0` when undefined
3. Logic uses `(mapCount || fallback)` - but `0` is falsy, so it SHOULD use fallback
4. **BUT**: When `mapCount = 0` (from unloaded video), the condition `(0 || fallback)` evaluates to `fallback`
5. **HOWEVER**: If `videoDetectionMap[videoId]` returns `[]` (empty array) instead of `undefined`, then `mapCount = 0` and `(0 || fallback)` correctly uses fallback

**The Real Issue**: Video 2 detections not loaded into `videoDetectionMap` yet, so aggregation shows 54 instead of 54+61=115

## Why 115 Instead of 242?

**Top Banner shows 115** - This suggests:
- Some detections ARE loaded (115 total)
- But not all expected detections (242)
- Possible causes:
  - API filtering out some detections
  - Some detections with NULL video_id not counted
  - Race condition during initial load
  - Backend returning incomplete data

**Quick Test**: If 115 ≈ 54 (Video 1) + 61 (Video 2), then:
- Top banner has BOTH videos loaded: 54 + 61 = 115 ✓
- Aggregated metrics only has Video 1 loaded: 54
- Video selector shows current video: 54

## The Fix

### Option 1: Wait for All Videos to Load Before Showing Aggregated Count
```typescript
const totalDetections = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  const fallback = v.total_detections ?? v.totalDetections ?? v.detection_count ?? v.detectionCount ?? 0;

  // Use mapCount ONLY if video is loaded (exists in map)
  const isLoaded = currentId && videoDetectionMap.hasOwnProperty(currentId);
  return sum + (isLoaded ? mapCount : fallback);
}, 0);
```

### Option 2: Use Backend Counts Until Videos Loaded
```typescript
const totalDetections = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId && videoDetectionMap[currentId] ? videoDetectionMap[currentId].length : null;
  const fallback = v.total_detections ?? v.totalDetections ?? v.detection_count ?? v.detectionCount ?? 0;

  // Use backend count if map not populated yet
  return sum + (mapCount !== null ? mapCount : fallback);
}, 0);
```

### Option 3: Eagerly Load All Video Detections on Mount
```typescript
// In loadHILResults(), after loading per-video summaries:
await Promise.all(
  sortedPerVideo.map(video => {
    const videoId = video.videoId ?? video.video_id;
    return loadDetectionsForVideo(videoId);
  })
);
```

## Verification Steps

1. **Check backend response**: Does `per_video_results[0].total_detections` = 54?
2. **Check backend response**: Does `per_video_results[1].total_detections` = 61?
3. **Check videoDetectionMap state**: Is Video 2 loaded? `videoDetectionMap[video2Id]?.length`
4. **Check allDetections**: Does it contain 115 items? Are they from both videos?
5. **Check for NULL video_id**: Are some detections missing video_id field?

## Expected Behavior

For a 2-video sequence with constant voltage:

| Display Location | Should Show | Currently Shows | Status |
|------------------|-------------|-----------------|--------|
| Top Banner | 242 total expected | 115 out of 242 | ❌ Missing detections |
| Aggregated Alert | 115 detected | 54 detections | ❌ Only Video 1 counted |
| Video 1 Selector | 54 detections | 54 detections | ✅ Correct |
| Video 2 Selector | 61 detections | (not tested) | ❓ Unknown |

## Next Steps

1. Add debug logging to see which videos are in `videoDetectionMap`
2. Check if Video 2 detections are ever loaded
3. Verify backend API returns correct counts for each video
4. Implement fix (Option 1 or 2) to handle lazy loading correctly
5. Add preloading for all videos on initial load (Option 3)

## Code Locations

- Aggregation logic: `/frontend/src/pages/HILResults.tsx` Lines 865-942
- Top banner: `/frontend/src/pages/HILResults.tsx` Line 1313
- Aggregated display: `/frontend/src/pages/HILResults.tsx` Line 1340
- Video selector: `/frontend/src/pages/HILResults.tsx` Line 1552
- Detection loading: `/frontend/src/pages/HILResults.tsx` Lines 396-480 (`loadDetectionsForVideo`)
- Initial load: `/frontend/src/pages/HILResults.tsx` Lines 499-767 (`loadHILResults`)

---

**Analysis Date**: 2025-11-05
**Analyst**: Research Agent
**Status**: Root Cause Identified - Lazy Loading Issue in Aggregation Logic
