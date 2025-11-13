# Detection Display Root Cause Analysis

## Executive Summary

**Issue**: Detections not displaying in HIL Results page despite data existing in database.

**Root Cause**: Frontend is correctly fetching detection data from API, but the detections are being filtered out by the `activeDetections` useMemo hook when a video is selected in a multi-video sequence.

**Status**: ✅ Data flow works, issue is in UI state management

---

## Investigation Findings

### 1. Database Layer ✅ WORKING
- **99 detections** exist in database for session `0f64178e-9cff-4cd2-b269-f61ba0734e42`
- Detection events properly stored with all required fields:
  - `actual_latency_ms`: 50.0ms (correctly calculated)
  - `validation_result`: "PASS"
  - `video_id`: Properly set to video IDs
  - `ground_truth_match_id`: Available for matched detections

```sql
-- Sample detection structure
ID: be08aa79... | Time: 1762178811.871 | Latency: 50.00ms
Video: 10c2b16c... | GT: None | Valid: PASS | LatResult: None
```

### 2. API Layer ✅ WORKING
All endpoints return correct data:

**✅ `/api/test-sessions/{sessionId}/events?limit=5`**
```json
[
  {
    "id": "be08aa79-2a02-4a07-93a4-605517a6d042",
    "timestamp": 1762178811.870749,
    "voltage": 4.212593078613281,
    "channel": "AIN0",
    "video_frame": 3,
    "video_timestamp": 0.13506436347961426,
    "detection_type": "voltage",
    "validation_result": "PASS",
    "timing_quality": "high",
    "frame_number": 3,
    "latency_ms": 50.0
  }
]
```

**✅ `/api/test-sessions/{sessionId}/detections?limit=5`**
```json
{
  "session_id": "0f64178e-9cff-4cd2-b269-f61ba0734e42",
  "detections": [
    {
      "id": "be08aa79-2a02-4a07-93a4-605517a6d042",
      "timestamp": 1762178811.870749,
      "vru_type": null,
      "confidence": null,
      "bounding_box": null,
      "created_at": "2025-11-03T14:06:51"
    }
  ],
  "total_detections": 5
}
```

### 3. Frontend Data Flow ⚠️ ISSUE IDENTIFIED

#### Data Loading Flow

```typescript
// Line 111-131: loadDetectionsForVideo()
const loadDetectionsForVideo = useCallback(async (videoId: string) => {
  const videoDetections = await apiService.getTestSessionEvents(
    sessionId!,
    2000,
    { video_id: videoId }  // ✅ Correct API call
  );

  const normalized = normalizeDetectionEvents(videoDetections);
  console.log(`Loaded ${normalized.length} detections for video ${videoId}`);

  // ❌ PROBLEM: Overwrites ALL base detections with video-specific ones
  setBaseDetections(normalized);

  // ✅ Updates map correctly
  setVideoDetectionMap(prev => ({
    ...prev,
    [videoId]: normalized
  }));
}, [sessionId]);
```

#### Detection Filtering Logic

```typescript
// Line 560-582: activeDetections useMemo
const activeDetections = useMemo(() => {
  if (selectedVideoId) {
    const mapped = videoDetectionMap[selectedVideoId];
    if (mapped) {
      return mapped;  // ✅ Returns video-specific detections
    }
    // ⚠️ If not loaded yet, returns empty array
    return [];
  }

  if (!isSequence) {
    if (videoId && videoDetectionMap[videoId]) {
      return videoDetectionMap[videoId];
    }
    const allFallback = videoDetectionMap['__all__'];
    if (allFallback && allFallback.length > 0) {
      return allFallback;
    }
  }

  // Falls back to allDetections
  return allDetections;
}, [allDetections, isSequence, selectedVideoId, videoDetectionMap, videoId]);
```

### 4. Root Cause Analysis

**The Issue**: Multi-Video Sequence State Management

When a multi-video sequence is detected:

1. ✅ Initial load fetches enhanced results
2. ✅ Sequence detection works correctly
3. ⚠️ **Line 358-360**: `videoDetectionMap` is initialized as EMPTY:
   ```typescript
   // Line 358-360
   const detectionMap: Record<string, EnhancedDetectionEvent[]> = {};
   setVideoDetectionMap(detectionMap);  // ❌ Empty map!
   ```

4. ✅ First video is selected (Line 362-368)
5. ✅ `loadDetectionsForVideo()` is called for first video
6. ✅ Detections are loaded and map is updated
7. **BUT**: If `selectedVideoId` is set before detections load, `activeDetections` returns `[]`

**Race Condition Timeline**:
```
T0: Load sequence results
T1: setVideoDetectionMap({})              // Empty map
T2: setSelectedVideoId("video-1")         // Video selected
T3: activeDetections calculates           // videoDetectionMap["video-1"] = undefined → returns []
T4: useEffect triggers loadDetectionsFor Video
T5: API call completes
T6: setVideoDetectionMap({ "video-1": [detections] })
T7: activeDetections recalculates         // Now has data!
```

The problem is **T2 happens before T6**, causing a brief period where no detections show.

### 5. Console Log Analysis

Expected console output when page loads:
```javascript
// Line 170
"Loading HIL results for session: {sessionId}"

// Line 286
"Multi-video sequence detected: {sequenceId}"

// Line 408
"🔄 Auto-loading detections for selected video: {videoId}"

// Line 113
"Loading detections for video: {videoId}"

// Line 121
"Loaded {N} detections for video {videoId}"
```

If these logs appear but table still shows "No detection events found", the issue is in the render logic or `activeDetections` calculation.

---

## Solution Paths

### Option 1: Pre-load first video detections (Recommended)
**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`
**Location**: Line 362-368

```typescript
// CURRENT (causes empty state)
const firstVideoId = sortedPerVideo[0] ? (sortedPerVideo[0].videoId ?? sortedPerVideo[0].video_id ?? null) : null;
if (firstVideoId) {
  setSelectedVideoId(firstVideoId);  // ❌ Sets selected BEFORE loading
  setVideoId(firstVideoId);
  await loadGroundTruthData(firstVideoId);
  await loadDetectionsForVideo(firstVideoId);  // ❌ Loads AFTER selected
}

// FIX: Load detections BEFORE setting selected
const firstVideoId = sortedPerVideo[0] ? (sortedPerVideo[0].videoId ?? sortedPerVideo[0].video_id ?? null) : null;
if (firstVideoId) {
  setVideoId(firstVideoId);
  await loadGroundTruthData(firstVideoId);
  await loadDetectionsForVideo(firstVideoId);  // ✅ Load first
  setSelectedVideoId(firstVideoId);            // ✅ Then select
}
```

### Option 2: Use loading state in activeDetections
**Location**: Line 560-582

```typescript
const activeDetections = useMemo(() => {
  if (selectedVideoId) {
    const mapped = videoDetectionMap[selectedVideoId];
    if (mapped !== undefined) {  // ✅ Explicit check
      return mapped;
    }
    // ✅ Return all detections while loading
    return baseDetections;  // Instead of []
  }
  // ... rest
}, [allDetections, isSequence, selectedVideoId, videoDetectionMap, videoId, baseDetections]);
```

### Option 3: Add explicit loading state
```typescript
const [detectionsLoading, setDetectionsLoading] = useState(false);

// In loadDetectionsForVideo
setDetectionsLoading(true);
// ... load data
setDetectionsLoading(false);

// In render
{detectionsLoading ? (
  <CircularProgress />
) : activeDetections.length > 0 ? (
  // ... render detections
) : (
  <Typography>No detection events found</Typography>
)}
```

---

## Debugging Steps

### Step 1: Add Debug Logging
Add to `activeDetections` useMemo (after line 560):

```typescript
const activeDetections = useMemo(() => {
  console.log('🔍 activeDetections recalculating:', {
    selectedVideoId,
    isSequence,
    videoDetectionMapKeys: Object.keys(videoDetectionMap),
    baseDetectionsCount: baseDetections.length,
    allDetectionsCount: allDetections.length
  });

  if (selectedVideoId) {
    const mapped = videoDetectionMap[selectedVideoId];
    console.log(`📊 Video ${selectedVideoId} detections:`, mapped?.length ?? 'undefined');
    if (mapped) {
      return mapped;
    }
    console.log('⚠️ No detections in map for selected video, returning []');
    return [];
  }
  // ... rest
}, [/* deps */]);
```

### Step 2: Monitor State Changes
Open browser console and watch for:
1. Initial load sequence
2. When `videoDetectionMap` gets populated
3. When `selectedVideoId` changes
4. When `activeDetections` recalculates

### Step 3: Verify API Response
Check Network tab:
- `/api/test-sessions/{id}/events?limit=2000&video_id={videoId}`
- Should return array of detections
- Check if `video_id` parameter is being sent correctly

### Step 4: Check Normalization
The `normalizeDetectionEvents()` function might be filtering out data. Add logging:

```typescript
const normalized = normalizeDetectionEvents(videoDetections);
console.log(`📦 Normalization: ${videoDetections.length} → ${normalized.length}`);
if (videoDetections.length !== normalized.length) {
  console.warn('⚠️ Some detections were filtered during normalization');
}
```

---

## Verification Checklist

Once fix is applied, verify:

- [ ] Page loads without "No detection events found" message
- [ ] Detection count in metrics cards matches database count (99 detections)
- [ ] Switching between videos in dropdown updates table correctly
- [ ] Average latency displays correctly (should be ~50ms)
- [ ] Ground truth matching shows correct statistics
- [ ] Video column shows correct video names/numbers
- [ ] Timeline visualization displays all detections
- [ ] Console logs show detections loading in correct order

---

## Additional Findings

### Duplicate onClick in DetectionTableRow (Line 1154)
```tsx
<DetectionTableRow
  onClick={() => handleDetectionClick(detection)}
  onClick={() => handleDetectionClick(detection)}  // ❌ Duplicate prop
/>
```
**Fix**: Remove one of the duplicate `onClick` props.

### All Console Logs Present
The debugging console.logs are correctly placed at:
- Line 87: Ground truth loading
- Line 113: Detection loading for video
- Line 121: Detection load complete
- Line 142: Video switching
- Line 408: Auto-loading trigger

These should fire in sequence when page loads.

---

## Recommended Implementation Order

1. **Immediate Fix** (5 minutes):
   - Reorder state updates in Line 362-368 to load detections before setting selected video

2. **Add Debug Logging** (2 minutes):
   - Add console.logs to `activeDetections` useMemo to understand calculation

3. **Test** (10 minutes):
   - Reload page and verify detections appear
   - Check console logs for proper sequence
   - Switch between videos to verify filtering works

4. **Cleanup** (3 minutes):
   - Remove duplicate `onClick` prop
   - Consider removing debug logs once confirmed working

---

## Impact Assessment

**Severity**: High - Primary feature not working
**User Impact**: Cannot view detection results in multi-video sequences
**Data Loss**: None - data is correctly stored in database
**Fix Complexity**: Low - Simple state management reordering
**Testing Required**: Medium - Need to test multi-video and single-video flows

---

## Conclusion

The detection display issue is **NOT a data problem** or **API problem**. It's a **state management race condition** in the React component. The data exists and is being fetched correctly, but the UI state updates in the wrong order, causing `activeDetections` to return an empty array during the critical render period.

**The fix is simple**: Ensure detections are loaded into `videoDetectionMap` BEFORE setting `selectedVideoId`, or modify `activeDetections` to return a non-empty fallback while detections are loading.
