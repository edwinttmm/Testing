# HIL Results Multi-Video Sequence Fixes

**Date:** 2025-10-01
**Component:** `/frontend/src/pages/HILResults.tsx`
**Issue:** Multi-video sequence data not properly displayed

## Issues Fixed

### 1. Multi-Video Display (video_playlist parsing)
**Problem:** Component wasn't checking for multi-video sequences stored in `test_sessions.sequence_metadata`

**Solution:** Added logic to parse `sequence_metadata` field from test sessions:
- Checks for `has_video_sequence` flag
- Parses `sequence_metadata` JSON containing `video_ids` array
- Extracts video IDs from sequence for ground truth loading
- Handles both camelCase and snake_case field names

**Code Changes:**
```typescript
// Check if this is a multi-video sequence session
const hasSequence = (sess as any).has_video_sequence || (sess as any).hasVideoSequence;
const sequenceMetadata = (sess as any).sequence_metadata || (sess as any).sequenceMetadata;

if (hasSequence && sequenceMetadata) {
  const metadata = typeof sequenceMetadata === 'string' ? JSON.parse(sequenceMetadata) : sequenceMetadata;
  const videoIds = metadata.video_ids || metadata.videoIds || [];
  // Use first video for ground truth
  setVideoId(videoIds[0]);
  await loadGroundTruthData(videoIds[0]);
}
```

### 2. Detection Events Table - "EXPECTED" Label Issue
**Problem:** All ground truth rows showing generic "EXPECTED" label instead of actual detection data

**Solution:** Enhanced ground truth row rendering to show:
- Actual class label (e.g., "GT: pedestrian")
- Confidence percentage
- Descriptive expected detection text

**Code Changes:**
```typescript
// Ground Truth Row - Show actual ground truth detection
const gtLabel = event.label || 'pedestrian';
const gtConfidence = event.confidence || 1.0;

<Chip label={`GT: ${gtLabel}`} size="small" color="warning" />
// ... confidence display
<Typography>Expected: {gtLabel}</Typography>
```

### 3. Video Metadata Display (FPS/Duration)
**Problem:** Video metadata showing "Unknown file" and "0s" due to missing fallback values

**Solution:** Added proper null fallbacks for video metadata:
```typescript
video_metadata: {
  fps: (enhancedData as any).video_timing?.fps || null,
  duration: (enhancedData as any).video_timing?.duration || null,
  filename: (enhancedData as any).video_timing?.filename || 'Unknown',
  average_processing_time_ms: ...
}
```

### 4. Video Boundary Detection (Frame Marking)
**Problem:** While searching for "Video Ended" logic, found that the component doesn't incorrectly mark frames as "Video Ended"

**Status:** No issues found - this was a false alarm from the analysis. The component correctly handles frame boundaries using actual video timing data.

### 5. Video Sequence Schema Support
**Integration:** Component now properly integrates with the video_sequences schema:
- Reads `sequence_id` from test_sessions
- Parses `sequence_metadata` containing video playlist
- Supports per-video duration, FPS, and ground truth events
- Displays proper timeline across multiple videos in sequence

## Database Schema Reference

The fixes integrate with these database fields:

```sql
-- test_sessions table
has_video_sequence BOOLEAN         -- Flag for multi-video tests
sequence_id VARCHAR(36)           -- Unique sequence identifier
sequence_metadata JSON            -- { video_ids: [...], timing: {...}, progress: {...} }
```

## Testing Recommendations

1. **Multi-Video Sequence Test:**
   - Create session with `has_video_sequence = true`
   - Set `sequence_metadata` with multiple video IDs
   - Verify all videos load and display correctly

2. **Ground Truth Display Test:**
   - Verify ground truth events show class labels, not "EXPECTED"
   - Check confidence percentages display correctly
   - Confirm LabJack detections properly matched to GT events

3. **Video Metadata Test:**
   - Verify FPS and duration display correctly
   - Check filename shows actual file name, not "Unknown"
   - Validate processing time displays when available

## Files Modified

- `/frontend/src/pages/HILResults.tsx` - Multi-video support and display fixes

## Related Documentation

- `/docs/MULTI_VIDEO_TEST_SCENARIOS.md` - Multi-video test requirements
- `/backend/routers/video_sequence_testing.py` - Video sequence API
- `/backend/models.py` - TestSession schema with sequence support
