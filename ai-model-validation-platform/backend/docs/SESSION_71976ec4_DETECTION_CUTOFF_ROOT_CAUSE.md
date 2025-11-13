# Detection Cutoff Root Cause Analysis - Session 71976ec4

## Executive Summary

**CRITICAL BUG FOUND**: Video sequence results have **NULL start and end times**, preventing proper detection assignment and causing severe data loss.

- **Session**: 71976ec4-b37d-4b19-8df7-11fefcb9bba7
- **Total Detections Captured**: 268
- **Videos in Sequence**: 2
- **Expected Ground Truth**: 514 objects (per user report)
- **Capture Rate**: 52% (SEVERELY LOW - Expected >90%)
- **Status**: Both videos show "pending" status with NULL timing

## Critical Findings

### 1. **Video Timing Never Recorded** ❌

```
Video 1: child_test_video_20251031_144012.mp4
  Expected Duration: 5.04s
  Status: pending
  Start: NULL ⚠️
  End: NULL ⚠️

Video 2: Child_20251031_143523.mp4
  Expected Duration: 5.04s
  Status: pending
  Start: NULL ⚠️
  End: NULL ⚠️
```

**Impact**: Without video timing windows, the system cannot:
- Assign detections to the correct video
- Validate if detections fall within video playback time
- Calculate video-relative timestamps accurately
- Determine if monitoring stopped prematurely

### 2. **All Detections Assigned to Single Video** ⚠️

```sql
Video 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5: 268 detections
  Time Range: 1762191668.607250 - 1762191687.450024 (18.843s)
```

**Analysis**:
- All 268 detections are assigned to the SAME video ID
- Detection window is 18.843s (should be ~10.08s for 2 videos @ 5.04s each)
- Suggests both videos played, but timing metadata was never recorded

### 3. **Video Sequence Status Stuck in "Pending"**

Both `sequence_video_results` records show:
- `video_status = "pending"`
- `video_start_time = NULL`
- `video_end_time = NULL`

**Root Cause**: The `video_start` and `video_end` endpoints were never called OR failed to update the database.

## Evidence Trail

### Detection Timeline
```
Session Started:  2025-11-03 17:41:08.446283
First Detection:  1762191668.607250 (Unix)
Last Detection:   1762191687.450024 (Unix)
Session Complete: 2025-11-03 17:41:26.718949
Detection Window: 18.843 seconds
```

### Expected vs Actual
```
Expected Total Duration: 2 videos × 5.04s = 10.08s
Actual Detection Window: 18.843s
Difference: +8.763s (87% longer than expected)
```

This suggests:
- Videos played normally (18.8s is reasonable for 2 videos with transitions)
- Detection monitoring worked correctly
- **Video lifecycle events (`video_start`, `video_end`) FAILED to execute**

## Root Causes Identified

### Primary Cause: Video Lifecycle Events Not Called

**Location**: `/backend/api/hil_test_complete.py`

The video sequence orchestrator is supposed to call:
1. `POST /api/test-sessions/{session_id}/video-sequence/video-start` - Sets `video_start_time`
2. `POST /api/test-sessions/{session_id}/video-sequence/video-end` - Sets `video_end_time`, updates status

**Evidence**: Both endpoints were never called or failed silently.

**Verification Needed**:
```bash
# Check if endpoints were called in logs
grep "video-start" backend/nohup.out
grep "video-end" backend/nohup.out
grep "71976ec4" backend/nohup.out | grep -E "(video.*start|video.*end)"
```

### Secondary Cause: Cache Context Not Refreshed

**Location**: `/backend/services/dedicated_labjack_monitor.py` lines 728-801

The `_enrich_hil_event_context()` method relies on cached sequence context:

```python
# BUG FIX #8: Cache Invalidation for Multi-Video Sequences
cached_context = session_cache.get('sequence_context')

if not cached_context or 'video_timing' not in cached_context:
    context = self._load_sequence_context(session_id)
```

**Issue**: If video timing is never written to the database, the cache will always be empty, and all detections get assigned to the fallback video.

### Tertiary Cause: Frontend May Not Be Calling Lifecycle Events

**Location**: `/frontend/src/components/SequentialVideoPlayer.tsx`

The frontend video player must call:
```typescript
// On video start
await api.post(`/api/test-sessions/${sessionId}/video-sequence/video-start`, {
  video_id: videoId,
  video_start_time: Date.now() / 1000
});

// On video end
await api.post(`/api/test-sessions/${sessionId}/video-sequence/video-end`, {
  video_id: videoId,
  video_end_time: Date.now() / 1000
});
```

**Verification Required**: Check if these API calls are actually being made.

## Missing Detections Analysis

### Detection Count Discrepancy

```
Total Detections Captured: 268
Expected Ground Truth: 514 objects
Capture Rate: 52%
Missing: 246 detections (48%)
```

### Possible Reasons for Missing Detections

1. **Auto-Stop Timer Triggered Too Early**
   - Code: `/backend/services/dedicated_labjack_monitor.py` lines 277-350
   - Auto-stop timer may have been set for single-video duration (5.04s) instead of sequence duration (10.08s)
   - Grace period: `max(0.25, min(2.0, duration * 0.05))` = 0.252s for 5.04s video
   - This would stop monitoring at ~5.3s, missing the entire second video

2. **Detection Filtering**
   - Check if voltage threshold is too high
   - Verify debounce settings aren't suppressing valid detections

3. **Monitoring Never Started for Video 2**
   - If `video_start` was never called for the second video, monitoring may have stopped after Video 1

## Immediate Actions Required

### 1. Check Backend Logs
```bash
# Search for session 71976ec4 video lifecycle events
cd /home/rigade/Testing/ai-model-validation-platform/backend
grep -A 5 "71976ec4" nohup.out | grep -E "(video-start|video-end|video.*complete)"
```

### 2. Verify Frontend API Calls
```bash
# Check if video_start/video_end endpoints are called
cd /home/rigade/Testing/ai-model-validation-platform/frontend
grep -r "video-start" src/
grep -r "video-end" src/
```

### 3. Test Auto-Stop Logic
```bash
# Check if auto-stop is disabled for sequences
cd /home/rigade/Testing/ai-model-validation-platform/backend
grep -A 20 "auto-stop timer" services/dedicated_labjack_monitor.py
```

### 4. Validate Database State
```bash
# Check sequence_metadata for video timing
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 -c "
import sqlite3, json
conn = sqlite3.connect('dev_database.db')
cursor = conn.cursor()
cursor.execute('SELECT sequence_metadata FROM test_sessions WHERE id = \"71976ec4-b37d-4b19-8df7-11fefcb9bba7\"')
metadata = cursor.fetchone()[0]
if metadata:
    print(json.dumps(json.loads(metadata) if isinstance(metadata, str) else metadata, indent=2))
conn.close()
"
```

## Recommended Fixes

### Fix 1: Ensure Video Lifecycle Events Are Called

**File**: `/frontend/src/components/SequentialVideoPlayer.tsx`

Add robust error handling and retry logic:

```typescript
const handleVideoStart = async (videoId: string) => {
  try {
    const response = await api.post(
      `/api/test-sessions/${sessionId}/video-sequence/video-start`,
      { video_id: videoId, video_start_time: Date.now() / 1000 }
    );
    console.log(`✅ Video start recorded for ${videoId}`);
  } catch (error) {
    console.error(`❌ Failed to record video start for ${videoId}:`, error);
    // Retry once
    setTimeout(() => handleVideoStart(videoId), 1000);
  }
};
```

### Fix 2: Add Fallback Detection Assignment

**File**: `/backend/services/dedicated_labjack_monitor.py`

If video timing is missing, use detection timestamp and expected video duration to infer which video:

```python
def _fallback_video_assignment(self, sequence_id: str, detection_timestamp: float):
    """Assign video based on detection timestamp when timing data is missing"""
    # Get video order and expected durations
    videos = self._get_sequence_videos(sequence_id)

    # Calculate which video should be playing based on timestamp offset
    sequence_start = self._get_sequence_start_time(sequence_id)
    offset = detection_timestamp - sequence_start

    cumulative_duration = 0
    for video in videos:
        cumulative_duration += video.expected_duration
        if offset < cumulative_duration:
            return video.id

    return videos[-1].id  # Default to last video
```

### Fix 3: Disable Auto-Stop for Multi-Video Sequences

**File**: `/backend/services/dedicated_labjack_monitor.py` line 303

Ensure this logic is working:

```python
if is_sequence:
    logger.info(f"🎬 Skipping auto-stop timer for multi-video sequence {sequence_id} - orchestrator will control lifecycle")
```

**Verification**: Check logs to confirm this message appears for session 71976ec4.

### Fix 4: Add Video Timing Validation

**File**: `/backend/api/hil_test_complete.py`

Before completing a session, validate video timing:

```python
@router.post("/{session_id}/complete")
async def complete_session(session_id: str, db: Session = Depends(get_db)):
    # Validate video sequence timing
    if session.has_video_sequence:
        results = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == session.sequence_id
        ).all()

        for result in results:
            if result.video_start_time is None or result.video_end_time is None:
                logger.error(f"❌ Video {result.video_id} missing timing: start={result.video_start_time}, end={result.video_end_time}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Video {result.video_id} missing timing data - cannot complete session"
                )
```

## Testing Checklist

- [ ] Verify `video_start` endpoint is called for each video in sequence
- [ ] Verify `video_end` endpoint is called for each video in sequence
- [ ] Confirm auto-stop timer is NOT activated for multi-video sequences
- [ ] Validate sequence_metadata contains video_timing for all videos
- [ ] Ensure detections are properly distributed across videos
- [ ] Verify capture rate is >90% for each video in sequence

## Conclusion

The detection cutoff issue is caused by **missing video lifecycle event calls**, resulting in:
1. NULL video timing in database
2. All detections assigned to a single video
3. Inability to validate if monitoring stopped early
4. 52% capture rate instead of expected >90%

**Primary Fix**: Ensure frontend calls `video_start` and `video_end` endpoints reliably for each video in the sequence.

**Secondary Fixes**: Add fallback assignment logic, improve error handling, and validate timing data before session completion.
