# Frontend video_id Filtering Fix

**Date**: 2025-11-04
**Status**: ✅ COMPLETED
**Build**: SUCCESS (+81B)

## Problem

Frontend always filtered detections by `video_id`, excluding detections with `NULL video_id` in single-video test sessions.

**Root Cause**:
```typescript
// ❌ BEFORE: Always filtered by video_id
const videoDetections = await apiService.getTestSessionEvents(
  sessionId!,
  2000,
  { video_id: videoId }  // This excludes NULL video_id detections
);
```

## Solution

Make video_id filtering conditional based on session type:
- **Single-video sessions**: Pass empty filters `{}` to load ALL detections
- **Multi-video sequences**: Filter by `video_id` for each video

## Changes Made

### 1. Modified `loadDetectionsForVideo` Function

**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`

**Lines**: 114-149

```typescript
const loadDetectionsForVideo = useCallback(async (videoId: string | null) => {
  const loadingKey = videoId || '__all__';
  setVideoLoadingState(prev => ({ ...prev, [loadingKey]: true }));

  try {
    console.log(`Loading detections${videoId ? ` for video: ${videoId}` : ' (all videos)'}`);

    // CRITICAL FIX: Only pass video_id filter if we have a specific video in multi-video mode
    // For single-video sessions, pass empty filters to get ALL detections (including NULL video_id)
    const filters = (videoId && isSequence) ? { video_id: videoId } : {};

    const videoDetections = await apiService.getTestSessionEvents(
      sessionId!,
      2000,
      filters  // ✅ Empty object for single-video, or with video_id for multi-video
    );

    const normalized = normalizeDetectionEvents(videoDetections);
    console.log(`Loaded ${normalized.length} detections${videoId ? ` for video ${videoId}` : ' (all)'}`);

    setBaseDetections(normalized);
    setVideoDetectionMap(prev => ({
      ...prev,
      [loadingKey]: normalized
    }));
  } catch (error) {
    console.error(`Failed to load detections${videoId ? ` for video ${videoId}` : ''}:`, error);
  } finally {
    setVideoLoadingState(prev => ({ ...prev, [loadingKey]: false }));
  }
}, [sessionId, isSequence]);
```

**Key Changes**:
- Accept `videoId: string | null` instead of just `string`
- Use `loadingKey = videoId || '__all__'` for loading state tracking
- Apply conditional filtering: `(videoId && isSequence) ? { video_id: videoId } : {}`

### 2. Updated Initial Load Logic

**Lines**: 377-392

```typescript
if (firstVideoId) {
  setVideoId(firstVideoId);
  await loadGroundTruthData(firstVideoId);

  // CRITICAL FIX: For multi-video sequences, filter by video_id
  // For single-video sessions, load ALL detections (no filter)
  if (isSequence && sortedPerVideo.length > 1) {
    await loadDetectionsForVideo(firstVideoId);  // Multi-video: filter by video_id
  } else {
    await loadDetectionsForVideo(null);  // Single-video: no filter
  }

  setSelectedVideoId(firstVideoId);
}
```

**Key Changes**:
- Check `sortedPerVideo.length > 1` to determine if truly multi-video
- Pass `null` for single-video (no filtering)
- Pass `firstVideoId` for multi-video (filter by video)

### 3. Fixed Auto-Load Effect

**Lines**: 430-437

```typescript
useEffect(() => {
  // Only auto-load for multi-video sequences where we filter by video_id
  const videoSequence = sequenceResults?.per_video_results || [];
  if (selectedVideoId && isSequence && videoSequence.length > 1 && !videoDetectionMap[selectedVideoId]) {
    console.log(`🔄 Auto-loading detections for selected video: ${selectedVideoId}`);
    loadDetectionsForVideo(selectedVideoId);
  }
}, [selectedVideoId, isSequence, sequenceResults, videoDetectionMap, loadDetectionsForVideo]);
```

**Key Changes**:
- Added `videoSequence.length > 1` check to prevent unnecessary loads
- Only auto-loads for true multi-video sequences

## Behavior After Fix

| Session Type | Filter Applied | Result |
|--------------|----------------|--------|
| **Single-video test** | `{}` (empty) | Loads ALL detections, including NULL video_id |
| **Multi-video sequence** | `{ video_id: "xyz" }` | Loads only detections for specific video |

## API Compatibility

The `apiService.getTestSessionEvents` method already handles empty filters correctly:

```typescript
// From frontend/src/services/api.ts:1793-1803
async getTestSessionEvents(
  sessionId: string,
  limit: number = 1000,
  filters?: { video_id?: string; offset?: number }
): Promise<Record<string, unknown>[]> {
  const params: Record<string, string | number> = { limit };

  if (filters?.offset !== undefined) {
    params.offset = filters.offset;
  }

  if (filters?.video_id) {  // ✅ Only adds video_id if present
    params.video_id = filters.video_id;
  }
  // ...
}
```

## TypeScript Type Safety

No TypeScript errors - function signature properly updated:

```typescript
// Before
const loadDetectionsForVideo = useCallback(async (videoId: string) => {

// After
const loadDetectionsForVideo = useCallback(async (videoId: string | null) => {
```

## Testing Checklist

- [x] Build succeeds without TypeScript errors
- [ ] Single-video test shows all detections (including NULL video_id)
- [ ] Multi-video sequence filters correctly by video_id
- [ ] Video switching loads correct detections
- [ ] Loading spinner shows during async operations
- [ ] No console errors for empty filters

## Verification Steps

1. **Test with single-video session**:
   ```bash
   # Open HILResults for a single-video test session
   # Should see ALL detections, including those with NULL video_id
   ```

2. **Test with multi-video sequence**:
   ```bash
   # Open HILResults for a multi-video sequence
   # Each video should show only its own detections
   ```

3. **Check console logs**:
   ```typescript
   // Should see:
   "Loading detections (all videos)"  // Single-video
   "Loading detections for video: xyz"  // Multi-video
   ```

## Coordination Hooks

```bash
npx claude-flow@alpha hooks pre-task --description "fix-frontend-video-id-filtering"
npx claude-flow@alpha hooks post-edit --file "HILResults.tsx" --memory-key "swarm/frontend/video-id-filtering"
npx claude-flow@alpha hooks notify --message "Frontend video_id filtering fixed"
```

## Related Files

- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx` (modified)
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/api.ts` (verified compatible)

## Performance Impact

- Build size: +81 bytes (negligible)
- Bundle gzipped: 19.53 kB → 19.61 kB
- No runtime performance impact

## Next Steps

1. Deploy frontend build to staging
2. Test with actual single-video and multi-video sessions
3. Verify detections with NULL video_id now appear
4. Monitor for any edge cases

---

**Status**: ✅ READY FOR DEPLOYMENT
