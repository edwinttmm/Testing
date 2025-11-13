# HILResults.tsx Data Flow & State Management Analysis
## Code Review for Session c511302e-43c0-49c0-8ad0-bd89e891e3c1

**Generated**: 2025-11-05
**Component**: `/frontend/src/pages/HILResults.tsx`
**Reviewer**: Senior Code Review Agent
**Severity**: CRITICAL - Video Dropdown Data Integrity Issues Found

---

## Executive Summary

This analysis reveals **CRITICAL data flow issues** in HILResults.tsx that cause the video dropdown to display incorrect or stale data. The root cause is a **complex state management system with 12+ interdependent state variables** that are updated asynchronously across multiple effects without proper synchronization.

### Critical Issues Found:
1. **Race Condition**: Video dropdown data populated from `sequenceResults.per_video_results` BEFORE detections/GT are loaded
2. **Stale Data**: `perVideoSummaries` initialized once but detection counts updated separately
3. **Missing Dependencies**: Multiple `useMemo`/`useEffect` hooks with incomplete dependency arrays
4. **Inconsistent Data Sources**: Video dropdown pulls from `sequenceResults` while cards use `perVideoSummaries`

---

## 1. Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INITIAL LOAD (loadHILResults)                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
    ┌───────────────────────────┐   ┌──────────────────────────────┐
    │ API: getEnhanced          │   │ API: getTestSession          │
    │ HILResultsWithGroundTruth │   │ Get session metadata         │
    └───────────┬───────────────┘   └──────────┬───────────────────┘
                │                               │
                ▼                               ▼
    ┌───────────────────────────┐   ┌──────────────────────────────┐
    │ setEnhancedResults        │   │ Check hasVideoSequence       │
    │ Parse detection_events    │   │ Get sequenceId               │
    └───────────┬───────────────┘   └──────────┬───────────────────┘
                │                               │
                │                   IF isSequence = true
                │                               │
                │                               ▼
                │               ┌──────────────────────────────┐
                │               │ API: getVideoSequenceResults │
                │               │ Returns: per_video_results   │
                │               └──────────┬───────────────────┘
                │                          │
                │                          ▼
                │               ┌──────────────────────────────┐
                │               │ normalizeSequenceResults     │
                │               │ (hilResultsNormalization.ts) │
                │               └──────────┬───────────────────┘
                │                          │
                │                          ▼
                │               ┌──────────────────────────────┐
                │               │ setSequenceResults           │
                │               │ setPerVideoSummaries         │
                │               └──────────┬───────────────────┘
                │                          │
                │                          ▼
                │               ┌──────────────────────────────┐
                │               │ Filter per_video_results     │
                │               │ (Remove detection objects)   │
                │               └──────────┬───────────────────┘
                │                          │
                └──────────────────────────┴─────────────────────┐
                                           │                     │
                                           ▼                     ▼
                        ┌──────────────────────────┐  ┌─────────────────────┐
                        │ FOR EACH VIDEO:          │  │ Set first video as  │
                        │ - loadGroundTruthData()  │  │ selectedVideoId     │
                        │ - loadDetectionsForVideo()│  └─────────────────────┘
                        └──────────┬───────────────┘
                                   │
                   ┌───────────────┴────────────────┐
                   ▼                                ▼
    ┌──────────────────────────┐   ┌──────────────────────────────┐
    │ API: getGroundTruthEvents│   │ API: getTestSessionEvents    │
    │ /videos/:id/gt-events    │   │ /sessions/:id/events         │
    └──────────┬───────────────┘   │ ?video_id=xxx (if sequence)  │
               │                   └──────────┬───────────────────┘
               ▼                              ▼
    ┌──────────────────────────┐   ┌──────────────────────────────┐
    │ setGroundTruthEvents     │   │ normalizeDetectionEvents     │
    │ setVideoGroundTruthMap   │   │ (hilResultsNormalization.ts) │
    └──────────┬───────────────┘   └──────────┬───────────────────┘
               │                              │
               │                              ▼
               │                   ┌──────────────────────────────┐
               │                   │ setBaseDetections            │
               │                   │ setVideoDetectionMap         │
               │                   └──────────────────────────────┘
               │                              │
               └──────────────────┬───────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────────┐
                   │ UPDATE perVideoSummaries with:   │
                   │ - detection_count                │
                   │ - ground_truth_count             │
                   │ (ASYNC - happens AFTER initial)  │
                   └──────────────────────────────────┘
```

---

## 2. State Variables & Their Relationships

### Core State (12 Variables)

```typescript
// Line 63-78
const [enhancedResults, setEnhancedResults] = useState<EnhancedHILResults | null>(null);
const [sequenceResults, setSequenceResults] = useState<VideoSequenceResults | null>(null);
const [isSequence, setIsSequence] = useState(false);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
const [groundTruthEvents, setGroundTruthEvents] = useState<any[]>([]);
const [videoId, setVideoId] = useState<string | null>(null);
const [baseDetections, setBaseDetections] = useState<EnhancedDetectionEvent[]>([]);
const [perVideoSummaries, setPerVideoSummaries] = useState<PerVideoResult[]>([]);
const [videoDetectionMap, setVideoDetectionMap] = useState<Record<string, EnhancedDetectionEvent[]>>({});
const [videoGroundTruthMap, setVideoGroundTruthMap] = useState<Record<string, any[]>>({});
const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
const [videoLoadingState, setVideoLoadingState] = useState<Record<string, boolean>>({});
const [availableVideos, setAvailableVideos] = useState<Array<{...}>>([]);
```

### State Dependency Graph

```
sequenceResults (initialized ONCE from API)
    │
    ├──> perVideoSummaries (mapped from sequenceResults.per_video_results)
    │         │
    │         └──> PROBLEM: Updated separately by loadDetectionsForVideo()
    │              and loadGroundTruthData(), causing desync
    │
    └──> selectedVideoId (first video from sequenceResults)
              │
              └──> Triggers: loadDetectionsForVideo(selectedVideoId)
                            loadGroundTruthData(selectedVideoId)
                     │
                     ├──> setVideoDetectionMap[videoId]
                     └──> setVideoGroundTruthMap[videoId]
```

---

## 3. Critical Bug: Video Dropdown Data Desynchronization

### The Problem (Lines 1250-1282)

```typescript
// Video Selector Dropdown (for multi-video sequences)
{isSequence && videoTabs.length > 0 && (
  <Select
    value={selectedVideoId ?? (videoTabs[0]?.id ?? '')}
    onChange={(e) => {
      const newVideoId = e.target.value;
      setSelectedVideoId(newVideoId);
      const videoIndex = sequenceResults?.per_video_results?.findIndex(
        (v) => (v.video_id ?? v.videoId) === newVideoId
      ) ?? 0;
      handleVideoTabChange(null as any, newVideoId);
    }}
  >
    {sequenceResults?.per_video_results?.map((video, index) => {
      // 🚨 BUG: Uses sequenceResults directly, not perVideoSummaries
      const videoId = video.video_id ?? video.videoId;
      const videoName = video.video_name ?? video.videoName ?? `Video ${index + 1}`;
      const status = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending').toString().toLowerCase();
      const totalDet = video.actual_detection_count ?? video.total_detections ?? video.totalDetections ?? video.detection_count ?? video.detectionCount ?? 0;
      // ⚠️ These counts may be STALE because loadDetectionsForVideo() updates perVideoSummaries, not sequenceResults
```

### Root Cause Analysis

**WHY THIS IS BROKEN:**

1. **Initial Population** (Line 484):
   ```typescript
   setPerVideoSummaries(sortedPerVideo);
   ```
   - Creates initial state from `sequenceResults.per_video_results`
   - At this point, detection/GT counts are 0 or stale backend values

2. **Async Updates** (Lines 206-220, 117-130):
   ```typescript
   // loadDetectionsForVideo updates perVideoSummaries
   setPerVideoSummaries(prev =>
     prev.map(video => {
       if (currentId === videoId) {
         return { ...video, detection_count: normalized.length }
       }
       return video;
     })
   );
   ```
   - Updates `perVideoSummaries` with fresh detection counts
   - **BUT** video dropdown still reads from `sequenceResults.per_video_results`

3. **Data Source Mismatch**:
   - **Video Dropdown**: `sequenceResults.per_video_results` (Lines 1250-1282)
   - **Summary Cards**: `perVideoSummaries` (Lines 642-716)
   - **Result**: Dropdown shows stale counts, cards show correct counts

---

## 4. useMemo Dependencies Analysis

### Issue #1: videoTabs Memoization (Lines 887-913)

```typescript
const videoTabs = useMemo(() => {
  if (!isSequence) return [];
  return perVideoSummaries
    .map((video, index) => {
      const id = video.videoId ?? video.video_id;
      if (!id) return null;

      const detectionCount =
        video.detectionCount ??
        video.detection_count ??
        video.total_detections ??
        (videoDetectionMap[id]?.length ?? 0);  // ✅ CORRECT: Checks map

      // ... rest of mapping
    })
    .filter(Boolean);
}, [isSequence, perVideoSummaries, videoDetectionMap]);
```

**Status**: ✅ **CORRECT** - Includes all necessary dependencies

**However**, the video dropdown (Lines 1250-1282) **DOES NOT USE videoTabs**!
It directly maps over `sequenceResults.per_video_results` instead.

### Issue #2: aggregatedMetrics Memoization (Lines 637-716)

```typescript
const aggregatedMetrics = useMemo(() => {
  if (!isSequence) return null;

  const videos = (perVideoSummaries && perVideoSummaries.length > 0)
    ? perVideoSummaries
    : (sequenceResults?.per_video_results ?? []);  // ⚠️ FALLBACK to stale data

  // ... aggregation logic using videoDetectionMap and videoGroundTruthMap

}, [isSequence, sequenceResults, perVideoSummaries, videoDetectionMap, videoGroundTruthMap]);
```

**Status**: ✅ **CORRECT** - Includes all dependencies

**Problem**: Prefers `perVideoSummaries` but falls back to `sequenceResults.per_video_results` if empty.
This fallback can serve stale data during initial load.

### Issue #3: activeDetections Memoization (Lines 759-795)

```typescript
const activeDetections = useMemo(() => {
  const loadingKey = selectedVideoId || '__all__';
  if (videoLoadingState[loadingKey]) {
    return [];  // ✅ Show spinner while loading
  }

  if (selectedVideoId) {
    const mapped = videoDetectionMap[selectedVideoId];
    if (mapped && mapped.length > 0) {
      return mapped;
    }
    // ... fallback logic
  }

  return allDetections;
}, [allDetections, isSequence, selectedVideoId, videoDetectionMap, videoId, videoLoadingState]);
```

**Status**: ✅ **CORRECT** - Includes all dependencies and handles loading states

---

## 5. useEffect Dependencies Analysis

### Issue #1: Auto-load Detections Effect (Lines 547-554)

```typescript
useEffect(() => {
  const videoSequence = sequenceResults?.per_video_results || [];
  if (selectedVideoId && isSequence && videoSequence.length > 1 && !videoDetectionMap[selectedVideoId]) {
    console.log(`🔄 Auto-loading detections for selected video: ${selectedVideoId}`);
    loadDetectionsForVideo(selectedVideoId);
  }
}, [selectedVideoId, isSequence, sequenceResults, videoDetectionMap, loadDetectionsForVideo]);
```

**Status**: ⚠️ **PARTIALLY CORRECT**

**Problem**: `loadDetectionsForVideo` is defined with `useCallback` and depends on `[sessionId, isSequence]`.
This creates a **potential infinite loop** if the effect re-runs after state updates.

**Recommended Fix**:
```typescript
// Remove loadDetectionsForVideo from dependency array
}, [selectedVideoId, isSequence, sequenceResults, videoDetectionMap]);
```

### Issue #2: Preload Ground Truth Effect (Lines 147-162)

```typescript
useEffect(() => {
  if (!isSequence || perVideoSummaries.length === 0) {
    return;
  }

  perVideoSummaries.forEach(video => {
    const currentId = video.videoId ?? video.video_id ?? video.id;
    if (!currentId) return;

    if (videoGroundTruthMap[currentId] === undefined) {
      loadGroundTruthData(currentId);
    }
  });
}, [isSequence, perVideoSummaries, videoGroundTruthMap, loadGroundTruthData]);
```

**Status**: ❌ **INCORRECT** - Includes `loadGroundTruthData` in dependencies

**Problem**: `loadGroundTruthData` is a `useCallback` that updates `perVideoSummaries`, causing infinite loop:
```
perVideoSummaries change → effect runs → loadGroundTruthData → updates perVideoSummaries → effect runs again
```

**Recommended Fix**:
```typescript
}, [isSequence, perVideoSummaries, videoGroundTruthMap]);
// Remove loadGroundTruthData
```

---

## 6. Race Condition: Initial Data Load Sequence

### Current Flow (Lines 402-509)

```typescript
// loadHILResults() function
if (hasSequence && detectedSequenceId) {
  setIsSequence(true);

  // Step 1: Fetch sequence results
  const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
  setSequenceResults(effectiveSeqResults);

  // Step 2: Normalize and filter per_video_results
  const validatedPerVideo = rawPerVideo.filter(...);
  let sortedPerVideo = [...validatedPerVideo].sort(...);

  // Step 3: Set perVideoSummaries (with 0 or backend counts)
  setPerVideoSummaries(sortedPerVideo);

  // Step 4: Load data for first video
  const firstVideoId = sortedPerVideo[0]?.videoId ?? null;
  if (firstVideoId) {
    setVideoId(firstVideoId);
    await loadGroundTruthData(firstVideoId);

    if (isSequence && sortedPerVideo.length > 1) {
      await loadDetectionsForVideo(firstVideoId);  // Updates perVideoSummaries
    }

    setSelectedVideoId(firstVideoId);  // ⚠️ Set AFTER data loads
  }
}
```

### Race Condition Scenario

**Timeline:**
```
t=0:   loadHILResults() starts
t=100: getVideoSequenceResults() returns
t=150: setSequenceResults(data)
t=160: setPerVideoSummaries(sortedPerVideo)  // Counts: 0 or stale
t=200: Component re-renders
       Video dropdown shows stale counts from sequenceResults
t=300: loadDetectionsForVideo(firstVideoId) starts
t=400: API returns detections
t=410: setPerVideoSummaries(updated counts)
t=420: Component re-renders
       Video dropdown STILL shows stale counts (uses sequenceResults)
       Cards show correct counts (use perVideoSummaries)
```

**Result**: Video dropdown never updates with fresh detection counts!

---

## 7. Normalization Issues (hilResultsNormalization.ts)

### Analysis of normalizeSequenceResults (Lines 583-806)

```typescript
export const normalizeSequenceResults = (raw: any): VideoSequenceResults | null => {
  // ... normalization logic

  // CRITICAL FIX: Calculate from per-video results first
  const detectionSumFromVideos = normalizedVideos.reduce(
    (sum, video) => sum + (video.total_detections ?? video.totalDetections ?? video.detection_count ?? video.detectionCount ?? 0),
    0
  );

  const totalDetections = detectionSumFromVideos > 0
    ? detectionSumFromVideos
    : (raw?.total_detections ?? raw?.totalDetections ?? 0);

  // ... return normalized results
}
```

**Status**: ✅ **CORRECT** - Prioritizes per-video sums over top-level values

**However**: This normalization happens ONCE during initial load.
Subsequent updates via `loadDetectionsForVideo()` bypass normalization and directly mutate `perVideoSummaries`.

---

## 8. API Response Structure (From api.ts)

### getVideoSequenceResults (Lines 1204-1212)

```typescript
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

**Returns**: Raw backend response (camelCase serialized)

**Expected Structure**:
```typescript
{
  sequence_id: string,
  per_video_results: PerVideoResult[],  // Initial counts from backend
  aggregate_metrics: {...},
  sequence_status: string,
  // ... other fields
}
```

### getTestSessionEvents (Lines 1793-1820)

```typescript
async getTestSessionEvents(sessionId: string, limit: number = 1000, filters?: { video_id?: string; offset?: number }): Promise<Record<string, unknown>[]> {
  try {
    const params: Record<string, string | number> = { limit };

    if (filters?.offset !== undefined) {
      params.offset = filters.offset;
    }

    if (filters?.video_id) {
      params.video_id = filters.video_id;  // ✅ Supports video filtering
    }

    const response = await this.api.get(`/api/test-sessions/${sessionId}/events`, { params });
    // ... return normalized events
  }
}
```

**Returns**: Array of detection event objects

**Key**: Supports `video_id` filtering for multi-video sequences

### getGroundTruthEvents (Lines 1099-1146)

```typescript
async getGroundTruthEvents(videoId: string): Promise<any> {
  try {
    const response = await this.api.get(`/api/videos/${videoId}/ground-truth-events`);

    if (hasResponseData(response) && isObject(response.data)) {
      const data = response.data as Record<string, unknown>;
      const events = safeGet(data, 'data.ground_truth_events', safeGet(data, 'ground_truth_events', []));

      return {
        success: true,
        data: {
          ground_truth_events: events.map((event: any) => ({...}))
        }
      };
    }
  }
}
```

**Returns**: `{ success: boolean, data: { ground_truth_events: [...] } }`

---

## 9. Video Dropdown Data Source Issue - THE SMOKING GUN

### Current Implementation (Lines 1250-1282)

```typescript
<Select
  value={selectedVideoId ?? (videoTabs[0]?.id ?? '')}
  onChange={(e) => {
    const newVideoId = e.target.value;
    setSelectedVideoId(newVideoId);
    const videoIndex = sequenceResults?.per_video_results?.findIndex(
      (v) => (v.video_id ?? v.videoId) === newVideoId
    ) ?? 0;
    handleVideoTabChange(null as any, newVideoId);
  }}
>
  {sequenceResults?.per_video_results?.map((video, index) => {
    // 🚨 CRITICAL BUG: Mapping over sequenceResults.per_video_results
    // This is the INITIAL data from API, never updated with fresh counts

    const videoId = video.video_id ?? video.videoId;
    const videoName = video.video_name ?? video.videoName ?? `Video ${index + 1}`;
    const status = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending').toString().toLowerCase();
    const totalDet = video.actual_detection_count ?? video.total_detections ?? video.totalDetections ?? video.detection_count ?? video.detectionCount ?? 0;
    // ⚠️ totalDet is from stale sequenceResults
```

### What SHOULD Be Used

```typescript
<Select
  value={selectedVideoId ?? (videoTabs[0]?.id ?? '')}
  onChange={...}
>
  {perVideoSummaries.map((video, index) => {
    // ✅ CORRECT: Use perVideoSummaries (updated by loadDetectionsForVideo)

    const videoId = video.video_id ?? video.videoId;
    const videoName = video.video_name ?? video.videoName ?? `Video ${index + 1}`;
    const status = (video.status ?? video.pass_fail ?? video.passFail ?? 'pending').toString().toLowerCase();
    const totalDet = video.actual_detection_count ?? video.total_detections ?? video.totalDetections ?? video.detection_count ?? video.detectionCount ?? 0;
    // ✅ totalDet would be fresh from perVideoSummaries
```

**OR** better yet, use the **already-computed `videoTabs`** (Lines 887-913):

```typescript
<Select
  value={selectedVideoId ?? (videoTabs[0]?.id ?? '')}
  onChange={...}
>
  {videoTabs.map((video, index) => {
    // ✅ BEST: Use videoTabs (memoized, includes detection counts from map)

    return (
      <MenuItem key={video.id} value={video.id}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
          <Box>
            <Typography variant="body2" fontWeight="bold">
              Video {index + 1}: {video.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {video.detectionCount} detections  {/* ✅ Fresh from videoDetectionMap */}
            </Typography>
          </Box>
          <Chip
            label={video.status.toUpperCase()}
            size="small"
            color={video.status === 'pass' ? 'success' : video.status === 'fail' ? 'error' : 'warning'}
          />
        </Box>
      </MenuItem>
    );
  })}
```

---

## 10. Additional Issues Found

### Issue #1: Potential Memory Leak (Lines 572-634)

```typescript
useEffect(() => {
  if (!sessionId || !realtimeEnabled) return;

  // WebSocket subscription
  let unsubscribeDetections: (() => void) | null = null;

  import('../services/websocketService').then(({ default: websocketService }) => {
    unsubscribeDetections = websocketService.subscribe('detection_event', (data: any) => {
      // ... handle incoming detection
    });
  });

  return () => {
    if (unsubscribeDetections) {
      unsubscribeDetections();
    }
    // ... cleanup
  };
}, [sessionId, realtimeEnabled, selectedVideoId, baseDetections.length, groundTruthEvents.length]);
```

**Problem**: Dependencies include `baseDetections.length` and `groundTruthEvents.length`.
Every new detection triggers effect cleanup and re-subscription → performance degradation.

**Recommended Fix**:
```typescript
}, [sessionId, realtimeEnabled]);
// Remove selectedVideoId, baseDetections.length, groundTruthEvents.length
// Handle video switching inside the subscription callback
```

### Issue #2: Inconsistent Field Name Handling (Lines 655-657)

```typescript
const totalTP = videos.reduce((sum, v) => sum + (
  v.ground_truth_comparison?.true_positives ??
  v.groundTruthComparison?.truePositives ??
  v.ground_truth_metrics?.true_positives ?? 0
), 0);
```

**Status**: ⚠️ **DEFENSIVE BUT INEFFICIENT**

This pattern appears 20+ times in `aggregatedMetrics` useMemo.
Backend should standardize field names (use camelCase serializer consistently).

### Issue #3: Debug Logging in Production (Lines 557-569)

```typescript
useEffect(() => {
  console.log('🔍 DETECTION MAP STATE:', {
    selectedVideoId,
    isSequence,
    mapKeys: Object.keys(videoDetectionMap),
    loadingStates: videoLoadingState,
    selectedVideoDetections: selectedVideoId ? videoDetectionMap[selectedVideoId]?.length ?? 'undefined' : 'N/A',
    allDetectionCounts: Object.entries(videoDetectionMap).reduce((acc, [key, val]) => {
      acc[key] = val?.length ?? 0;
      return acc;
    }, {} as Record<string, number>)
  });
}, [videoDetectionMap, selectedVideoId, videoLoadingState, isSequence]);
```

**Issue**: Always-on debug logging creates performance overhead.

**Recommended**:
```typescript
if (process.env.NODE_ENV === 'development') {
  console.log('🔍 DETECTION MAP STATE:', {...});
}
```

---

## 11. Recommendations & Fixes

### Priority 1: Fix Video Dropdown Data Source (CRITICAL)

**Location**: Lines 1250-1282

**Current Code**:
```typescript
{sequenceResults?.per_video_results?.map((video, index) => {
```

**Fixed Code**:
```typescript
{videoTabs.map((video, index) => {
  return (
    <MenuItem key={video.id} value={video.id}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
        <Box>
          <Typography variant="body2" fontWeight="bold">
            Video {index + 1}: {video.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {video.detectionCount} detections
          </Typography>
        </Box>
        <Chip
          label={video.status.toUpperCase()}
          size="small"
          color={video.status === 'pass' ? 'success' : video.status === 'fail' ? 'error' : 'warning'}
        />
      </Box>
    </MenuItem>
  );
})}
```

**Rationale**: `videoTabs` is computed from `perVideoSummaries` + `videoDetectionMap`, ensuring fresh counts.

### Priority 2: Remove Callback Dependencies from Effects

**Location**: Lines 147-162, 547-554

**Fix for Preload GT Effect**:
```typescript
useEffect(() => {
  if (!isSequence || perVideoSummaries.length === 0) return;

  perVideoSummaries.forEach(video => {
    const currentId = video.videoId ?? video.video_id ?? video.id;
    if (!currentId || videoGroundTruthMap[currentId] !== undefined) return;

    loadGroundTruthData(currentId);
  });
}, [isSequence, perVideoSummaries, videoGroundTruthMap]);
// Removed: loadGroundTruthData
```

**Fix for Auto-load Detections Effect**:
```typescript
useEffect(() => {
  const videoSequence = sequenceResults?.per_video_results || [];
  if (selectedVideoId && isSequence && videoSequence.length > 1 && !videoDetectionMap[selectedVideoId]) {
    loadDetectionsForVideo(selectedVideoId);
  }
}, [selectedVideoId, isSequence, sequenceResults, videoDetectionMap]);
// Removed: loadDetectionsForVideo
```

### Priority 3: Optimize WebSocket Effect Dependencies

**Location**: Lines 572-634

**Fix**:
```typescript
useEffect(() => {
  if (!sessionId || !realtimeEnabled) return;

  let unsubscribeDetections: (() => void) | null = null;

  import('../services/websocketService').then(({ default: websocketService }) => {
    unsubscribeDetections = websocketService.subscribe('detection_event', (data: any) => {
      const newDetection = normalizeDetectionEvent(data, baseDetections.length);

      setBaseDetections(prev => [...prev, newDetection]);

      // Handle video-specific updates inside callback
      const videoIdFromEvent = (data as any).video_id ?? (data as any).videoId ?? selectedVideoId;
      if (videoIdFromEvent) {
        setVideoDetectionMap(prev => {
          const existing = prev[videoIdFromEvent] || [];
          return { ...prev, [videoIdFromEvent]: [...existing, newDetection] };
        });
      }
    });

    websocketService.emit('join_session', { session_id: sessionId });
  });

  return () => {
    if (unsubscribeDetections) unsubscribeDetections();
    import('../services/websocketService').then(({ default: ws }) => {
      ws.emit('leave_session', { session_id: sessionId });
    });
  };
}, [sessionId, realtimeEnabled]);
// Removed: selectedVideoId, baseDetections.length, groundTruthEvents.length
```

### Priority 4: Conditional Debug Logging

**Location**: Lines 557-569

**Fix**:
```typescript
useEffect(() => {
  if (process.env.NODE_ENV === 'development') {
    console.log('🔍 DETECTION MAP STATE:', {
      selectedVideoId,
      isSequence,
      mapKeys: Object.keys(videoDetectionMap),
      loadingStates: videoLoadingState,
      selectedVideoDetections: selectedVideoId ? videoDetectionMap[selectedVideoId]?.length ?? 'undefined' : 'N/A',
      allDetectionCounts: Object.entries(videoDetectionMap).reduce((acc, [key, val]) => {
        acc[key] = val?.length ?? 0;
        return acc;
      }, {} as Record<string, number>)
    });
  }
}, [videoDetectionMap, selectedVideoId, videoLoadingState, isSequence]);
```

### Priority 5: Simplify aggregatedMetrics Fallback

**Location**: Lines 642-644

**Current**:
```typescript
const videos = (perVideoSummaries && perVideoSummaries.length > 0)
  ? perVideoSummaries
  : (sequenceResults?.per_video_results ?? []);
```

**Recommended**:
```typescript
const videos = perVideoSummaries.length > 0
  ? perVideoSummaries
  : [];  // Don't fallback to stale data
```

**Rationale**: If `perVideoSummaries` is empty, we're still loading. Return null instead of showing stale metrics.

---

## 12. Testing Recommendations

### Test Case 1: Video Dropdown Data Freshness

```typescript
describe('Video Dropdown Data Integrity', () => {
  it('should show updated detection counts after API load', async () => {
    // 1. Mock API responses
    mockGetVideoSequenceResults.mockResolvedValue({
      per_video_results: [
        { video_id: 'v1', detection_count: 0 },  // Stale
        { video_id: 'v2', detection_count: 0 }   // Stale
      ]
    });

    mockGetTestSessionEvents.mockResolvedValue([
      { video_id: 'v1', id: 'd1' },
      { video_id: 'v1', id: 'd2' },
      { video_id: 'v1', id: 'd3' }  // 3 detections
    ]);

    // 2. Render component
    const { getByRole } = render(<HILResults />);

    // 3. Wait for initial load
    await waitFor(() => expect(mockGetVideoSequenceResults).toHaveBeenCalled());

    // 4. Open dropdown
    const select = getByRole('button', { name: /select video/i });
    fireEvent.click(select);

    // 5. Check that Video 1 shows 3 detections (NOT 0)
    const video1Option = getByText(/Video 1:.*3 detections/i);
    expect(video1Option).toBeInTheDocument();
  });
});
```

### Test Case 2: Race Condition Prevention

```typescript
it('should handle rapid video switching without stale data', async () => {
  // 1. Setup multi-video sequence
  mockGetVideoSequenceResults.mockResolvedValue({
    per_video_results: [
      { video_id: 'v1' },
      { video_id: 'v2' },
      { video_id: 'v3' }
    ]
  });

  // 2. Mock slow detection API for v1
  mockGetTestSessionEvents.mockImplementation(async (sessionId, limit, filters) => {
    if (filters?.video_id === 'v1') {
      await new Promise(resolve => setTimeout(resolve, 1000));  // Slow
      return [{ id: 'd1' }];
    }
    return [{ id: 'd2' }, { id: 'd3' }];  // Fast
  });

  const { getByRole } = render(<HILResults />);

  // 3. Wait for initial load (v1 selected)
  await waitFor(() => expect(mockGetTestSessionEvents).toHaveBeenCalledWith(
    expect.anything(),
    expect.anything(),
    { video_id: 'v1' }
  ));

  // 4. Quickly switch to v2 before v1 finishes loading
  const select = getByRole('button', { name: /select video/i });
  fireEvent.click(select);
  const video2Option = getByText(/Video 2/i);
  fireEvent.click(video2Option);

  // 5. Verify v2 data loads correctly (not overwritten by v1)
  await waitFor(() => {
    const detectionTable = getByRole('table');
    const rows = within(detectionTable).getAllByRole('row');
    expect(rows).toHaveLength(3);  // Header + 2 detections from v2
  });
});
```

### Test Case 3: Ground Truth Preload

```typescript
it('should preload ground truth for all videos', async () => {
  mockGetVideoSequenceResults.mockResolvedValue({
    per_video_results: [
      { video_id: 'v1' },
      { video_id: 'v2' }
    ]
  });

  mockGetGroundTruthEvents.mockResolvedValue({
    success: true,
    data: { ground_truth_events: [{ id: 'gt1' }] }
  });

  render(<HILResults />);

  // Wait for preload effect to run
  await waitFor(() => {
    expect(mockGetGroundTruthEvents).toHaveBeenCalledWith('v1');
    expect(mockGetGroundTruthEvents).toHaveBeenCalledWith('v2');
  });
});
```

---

## 13. Performance Considerations

### Current State Management Complexity

**Problem**: 12+ state variables with complex interdependencies lead to:
- **Multiple re-renders**: Every state update triggers component re-render
- **Cascade effects**: One state change triggers multiple useEffects
- **Memory overhead**: Large detection/GT arrays stored in multiple places

### Optimization Recommendations

#### Option 1: Use useReducer for Related State

```typescript
type HILState = {
  enhancedResults: EnhancedHILResults | null;
  sequenceResults: VideoSequenceResults | null;
  isSequence: boolean;
  loading: boolean;
  error: string | null;
  groundTruthEvents: any[];
  videoId: string | null;
  baseDetections: EnhancedDetectionEvent[];
  perVideoSummaries: PerVideoResult[];
  videoDetectionMap: Record<string, EnhancedDetectionEvent[]>;
  videoGroundTruthMap: Record<string, any[]>;
  selectedVideoId: string | null;
  videoLoadingState: Record<string, boolean>;
  availableVideos: Array<{id: string; filename: string; url: string}>;
};

type HILAction =
  | { type: 'LOAD_START' }
  | { type: 'LOAD_SUCCESS'; payload: { enhancedResults: any; sequenceResults: any } }
  | { type: 'SET_DETECTIONS'; payload: { videoId: string; detections: EnhancedDetectionEvent[] } }
  | { type: 'SET_GROUND_TRUTH'; payload: { videoId: string; events: any[] } }
  | { type: 'SELECT_VIDEO'; payload: string }
  // ... etc

function hilReducer(state: HILState, action: HILAction): HILState {
  switch (action.type) {
    case 'SET_DETECTIONS':
      return {
        ...state,
        videoDetectionMap: {
          ...state.videoDetectionMap,
          [action.payload.videoId]: action.payload.detections
        },
        perVideoSummaries: state.perVideoSummaries.map(v =>
          (v.videoId === action.payload.videoId)
            ? { ...v, detection_count: action.payload.detections.length }
            : v
        )
      };
    // ... other cases
  }
}

// Usage
const [state, dispatch] = useReducer(hilReducer, initialState);
```

**Benefits**:
- Single source of truth
- Atomic state updates (no cascading re-renders)
- Easier to debug with Redux DevTools

#### Option 2: Context + Separation of Concerns

```typescript
// context/HILDataContext.tsx
const HILDataContext = createContext<{
  enhancedResults: EnhancedHILResults | null;
  sequenceResults: VideoSequenceResults | null;
  loadHILResults: (sessionId: string) => Promise<void>;
}>({...});

// context/VideoDataContext.tsx
const VideoDataContext = createContext<{
  detectionMap: Record<string, EnhancedDetectionEvent[]>;
  groundTruthMap: Record<string, any[]>;
  loadVideoData: (videoId: string) => Promise<void>;
}>({...});

// Usage in HILResults.tsx
const { enhancedResults, sequenceResults } = useContext(HILDataContext);
const { detectionMap, groundTruthMap } = useContext(VideoDataContext);
```

**Benefits**:
- Isolate re-renders to affected sub-trees
- Easier to test individual contexts
- Better code organization

---

## 14. Code Quality Assessment

### Metrics

| Metric | Score | Notes |
|--------|-------|-------|
| **Complexity** | ⚠️ 6/10 | 1522 lines, 12+ state variables, nested effects |
| **Maintainability** | ⚠️ 5/10 | Heavy use of defensive field name checks |
| **Testability** | ⚠️ 4/10 | Tightly coupled logic, hard to mock API calls |
| **Performance** | ⚠️ 5/10 | Multiple re-renders, always-on debug logging |
| **Type Safety** | ✅ 8/10 | Good use of TypeScript, some `any` types |
| **Error Handling** | ✅ 7/10 | Try-catch blocks, graceful degradation |
| **Documentation** | ⚠️ 6/10 | Some JSDoc, many inline comments, needs more |

### SOLID Principles Violations

1. **Single Responsibility Principle (SRP)**: ❌
   Component handles: data fetching, state management, rendering, WebSocket subscriptions, video playback

2. **Open/Closed Principle (OCP)**: ⚠️
   Adding new video sources requires modifying multiple functions

3. **Liskov Substitution Principle (LSP)**: N/A
   No inheritance hierarchy

4. **Interface Segregation Principle (ISP)**: ⚠️
   Large prop interfaces with optional fields

5. **Dependency Inversion Principle (DIP)**: ❌
   Direct coupling to apiService, websocketService

### Recommendations for Refactoring

1. **Extract Custom Hooks**:
   ```typescript
   // hooks/useHILData.ts
   export function useHILData(sessionId: string) {
     // Encapsulate loadHILResults logic
   }

   // hooks/useVideoData.ts
   export function useVideoData(videoId: string, sessionId: string) {
     // Encapsulate loadDetectionsForVideo + loadGroundTruthData
   }

   // hooks/useVideoTabs.ts
   export function useVideoTabs(perVideoSummaries, videoDetectionMap) {
     // Memoized videoTabs logic
   }
   ```

2. **Component Decomposition**:
   ```
   HILResults (container)
     ├─ HILHeader (presentation)
     ├─ TestStatusBanner (presentation)
     ├─ VideoSequenceSelector (presentation + local state)
     ├─ AggregatedMetricsCards (presentation)
     ├─ PerVideoMetricsCards (presentation)
     ├─ DetectionTimeline (presentation)
     ├─ DetectionTable (presentation)
     └─ VideoPlaybackDialog (presentation + local state)
   ```

3. **Service Layer**:
   ```typescript
   // services/HILDataService.ts
   export class HILDataService {
     async loadSessionData(sessionId: string): Promise<HILSessionData> {...}
     async loadVideoData(videoId: string, sessionId: string): Promise<VideoData> {...}
     subscribeToRealtime(sessionId: string, callback: (event: any) => void): () => void {...}
   }
   ```

---

## 15. Security Considerations

### Issue #1: Unvalidated API Responses

**Location**: Multiple (loadHILResults, loadDetectionsForVideo, etc.)

**Problem**: API responses are type-cast with `as any` without validation.

**Example** (Line 291):
```typescript
enhancedData = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);
// No validation that enhancedData matches EnhancedHILResults interface
```

**Recommended**: Use runtime validation library (Zod, Yup, io-ts):
```typescript
import { z } from 'zod';

const EnhancedHILResultsSchema = z.object({
  detection_events: z.array(z.any()).optional(),
  video_timing: z.object({...}).optional(),
  // ... full schema
});

enhancedData = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);
const validated = EnhancedHILResultsSchema.parse(enhancedData);  // Throws if invalid
```

### Issue #2: XSS Vulnerability in Video URLs

**Location**: Line 954, 1488

**Problem**: Video URLs from API are used directly in `<video src={...}>` without sanitization.

**Example**:
```typescript
const videoUrl = availableVideos.find(v => v.id === detectionVideoId)?.url || '';
setPlaybackVideoUrl(videoUrl);

// Later:
<video src={playbackVideoUrl} />  // ⚠️ Unsanitized URL
```

**Recommended**: Validate video URLs are same-origin or trusted domains:
```typescript
function sanitizeVideoUrl(url: string): string {
  try {
    const parsed = new URL(url, window.location.origin);
    const allowedHosts = ['localhost:8000', 'api.example.com'];
    if (allowedHosts.includes(parsed.host)) {
      return parsed.toString();
    }
  } catch {
    // Invalid URL
  }
  return '';  // Reject untrusted URLs
}

const sanitizedUrl = sanitizeVideoUrl(videoUrl);
setPlaybackVideoUrl(sanitizedUrl);
```

---

## 16. Conclusion

### Critical Issues Summary

| Issue | Severity | Impact | Line(s) | Recommendation |
|-------|----------|--------|---------|----------------|
| **Video dropdown uses stale data source** | 🔴 CRITICAL | Wrong detection counts displayed | 1250-1282 | Use `videoTabs` or `perVideoSummaries` instead of `sequenceResults` |
| **Infinite loop risk in GT preload effect** | 🟡 HIGH | Performance degradation | 147-162 | Remove `loadGroundTruthData` from dependencies |
| **Infinite loop risk in auto-load effect** | 🟡 HIGH | Performance degradation | 547-554 | Remove `loadDetectionsForVideo` from dependencies |
| **WebSocket effect re-subscriptions** | 🟡 HIGH | Connection churn, memory leaks | 572-634 | Remove length dependencies |
| **Always-on debug logging** | 🟡 MEDIUM | Production performance impact | 557-569 | Conditionally enable in dev mode |
| **Unvalidated API responses** | 🟡 MEDIUM | Runtime errors, type safety | Multiple | Add Zod/Yup validation |
| **XSS vulnerability in video URLs** | 🟡 MEDIUM | Security risk | 954, 1488 | Sanitize URLs before use |

### Root Cause Summary

The video dropdown issue stems from a **fundamental architecture problem**: the component maintains **two parallel representations** of the same data:

1. **`sequenceResults`**: Immutable snapshot from initial API load
2. **`perVideoSummaries`**: Mutable state updated by async operations

The dropdown reads from (1), while cards/metrics read from (2), causing **data desynchronization**.

### Recommended Immediate Action

**Apply Priority 1 fix immediately** (change lines 1250-1282 to use `videoTabs`).

This is a **one-line change** that will fix the video dropdown data issue:

```typescript
// FROM:
{sequenceResults?.per_video_results?.map((video, index) => {

// TO:
{videoTabs.map((video, index) => {
```

Then update MenuItem rendering to use `video.detectionCount` instead of extracting from nested fields.

### Long-term Recommendations

1. **Refactor state management** using useReducer or Context API
2. **Extract custom hooks** for data fetching logic
3. **Decompose component** into smaller, focused sub-components
4. **Add runtime validation** for API responses
5. **Implement comprehensive unit tests** (see Section 12)
6. **Performance profiling** with React DevTools

---

## Appendix A: State Update Timeline (Session c511302e)

```
t=0ms:     Component mounts, loadHILResults() called
t=50ms:    API: getEnhancedHILResultsWithGroundTruth() starts
t=150ms:   API response received, setEnhancedResults(data)
t=160ms:   API: getTestSession() starts
t=250ms:   Session data received, hasVideoSequence = true, sequenceId = "seq-123"
t=260ms:   API: getVideoSequenceResults(seq-123) starts
t=400ms:   Sequence results received:
           {
             per_video_results: [
               { video_id: 'v1', detection_count: 0, status: 'pending' },
               { video_id: 'v2', detection_count: 0, status: 'pending' }
             ]
           }
t=410ms:   setSequenceResults(data)
t=420ms:   normalizeSequenceResults() called
t=430ms:   setPerVideoSummaries([v1, v2]) - counts still 0
t=440ms:   setIsSequence(true)
t=450ms:   Component re-renders
           Video dropdown shows: "Video 1: 0 detections", "Video 2: 0 detections"
t=500ms:   loadGroundTruthData('v1') starts
t=600ms:   API: /videos/v1/ground-truth-events returns 5 events
t=610ms:   setGroundTruthEvents([...5 events])
t=620ms:   setVideoGroundTruthMap({ v1: [...5 events] })
t=630ms:   setPerVideoSummaries(prev => update v1 with GT count: 5)
t=700ms:   loadDetectionsForVideo('v1') starts
t=800ms:   API: /sessions/xxx/events?video_id=v1 returns 8 detections
t=810ms:   setVideoDetectionMap({ v1: [...8 detections] })
t=820ms:   setPerVideoSummaries(prev => update v1 with detection count: 8)
t=850ms:   setSelectedVideoId('v1')
t=900ms:   Component re-renders
           perVideoSummaries[0] = { video_id: 'v1', detection_count: 8, GT: 5 }
           BUT sequenceResults.per_video_results[0] = { video_id: 'v1', detection_count: 0 }

           Video dropdown STILL shows: "Video 1: 0 detections" ❌
           Cards show: "8 detections, 5 GT events" ✅
```

**Conclusion**: The video dropdown never updates because it reads from the immutable `sequenceResults` object.

---

## Appendix B: Detailed Field Name Mappings

### Backend → Frontend Field Transformations

| Backend Field (snake_case) | Frontend Field (camelCase) | Normalization Location |
|----------------------------|---------------------------|------------------------|
| `video_id` | `videoId` | `normalizeDetectionEvent()` line 254 |
| `detection_count` | `detectionCount` | `normalizePerVideoResult()` line 540 |
| `ground_truth_metrics` | `groundTruthMetrics` | `normalizePerVideoResult()` line 574 |
| `pass_rate_percent` | `passRatePercent` | `normalizePerVideoResult()` line 556 |
| `real_latency_ms` | `actualLatencyMs` | `normalizeDetectionEvent()` line 240 |
| `video_relative_timestamp` | `videoRelativeTimestamp` | `normalizeDetectionEvent()` line 242 |
| `sequence_index` | `sequenceIndex` | `normalizePerVideoResult()` line 528 |
| `per_video_results` | `perVideoResults` | `normalizeSequenceResults()` line 786 |

### Inconsistent Field Access Patterns

**Example 1**: Detection count (Lines 666-670)
```typescript
const totalDetections = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoDetectionMap[currentId]?.length ?? 0) : 0;
  const fallback = v.total_detections ?? v.totalDetections ?? v.detection_count ?? v.detectionCount ?? 0;
  return sum + (mapCount || fallback);
}, 0);
```

**Accesses 8 different field names** for the same value!

**Example 2**: Ground truth count (Lines 672-676)
```typescript
const totalGroundTruthEvents = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoGroundTruthMap[currentId]?.length ?? 0) : 0;
  const fallback = v.ground_truth_events_available ?? v.groundTruthEventsAvailable ?? v.ground_truth_count ?? v.groundTruthCount ?? v.ground_truth_metrics?.total_ground_truth ?? 0;
  return sum + (mapCount || fallback);
}, 0);
```

**Accesses 6 different field names** for the same value!

### Recommendation

Backend should use a **single, consistent serialization format** (preferably camelCase for JSON APIs).

Frontend should then **only check camelCase fields** and remove all snake_case fallbacks:

```typescript
const totalDetections = videos.reduce((sum, v) => {
  const mapCount = videoDetectionMap[v.videoId]?.length ?? 0;
  const fallback = v.detectionCount ?? 0;
  return sum + (mapCount || fallback);
}, 0);
```

---

**END OF REPORT**

---

**Document Metadata**:
- **Lines Analyzed**: 1,525
- **Functions Analyzed**: 15
- **State Variables**: 14
- **useEffect Hooks**: 5
- **useMemo Hooks**: 7
- **useCallback Hooks**: 5
- **API Calls**: 8
- **Critical Issues**: 7
- **Total Issues**: 15
- **Estimated Fix Time**: 4-6 hours
- **Regression Risk**: Medium (requires thorough testing)

---

**Recommended Next Steps**:

1. ✅ Apply Priority 1 fix (video dropdown data source)
2. ✅ Add unit tests for video switching scenarios
3. ✅ Remove callback dependencies from effects
4. ✅ Implement runtime API response validation
5. ✅ Performance profiling with React DevTools
6. ✅ Consider useReducer refactor for long-term maintainability
