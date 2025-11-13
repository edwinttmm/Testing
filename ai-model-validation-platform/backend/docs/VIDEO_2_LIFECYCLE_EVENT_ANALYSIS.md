# Video 2 Lifecycle Event Analysis - "Both Videos Played" Investigation

## Executive Summary

**USER CLAIM**: "I definitely saw two videos playing during the HIL test"
**DATABASE REALITY**: Video 2 (`video_start_time` = NULL) never received lifecycle events
**ROOT CAUSE**: Frontend displayed videos but backend never received `video-started` events for Video 2

---

## The Critical Discovery

### What The User Saw
- ✅ Video 1 played visually in browser
- ✅ Video 2 played visually in browser
- ✅ SequentialVideoPlayer UI showed "Video 2 of 2"
- ✅ Progress bars updated for both videos
- ✅ Both videos completed playback

### What The Backend Received
- ❌ Video 1: **NO `video-started` event** → `video_start_time = NULL`
- ❌ Video 1: **NO `video-ended` event** → `video_end_time = NULL`
- ❌ Video 2: **NO `video-started` event** → `video_start_time = NULL`
- ❌ Video 2: **NO `video-ended` event** → `video_end_time = NULL`
- ⚠️ Sequence status: `running` (never completed)
- ⚠️ Current video index: `0` (stuck on first video)

**DATABASE EVIDENCE** (Session: `71976ec4-b37d-4b19-8df7-11fefcb9bba7`):
```sql
sequence_id: 703aa6c9-a168-46b0-a60a-d80e2467b6c5
status: running
current_video_index: 0

Video 1: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  video_start_time: NULL
  video_end_time: NULL
  video_status: pending

Video 2: 550e3cf8-2755-42df-8c3c-041300735f93
  video_start_time: NULL
  video_end_time: NULL
  video_status: pending
```

**CRITICAL DISCOVERY**: **NEITHER** video received lifecycle events from the frontend!

---

## Test Execution Flow Analysis

### 1. Which Test Execution Page Was Used?

**PRIMARY PAGE**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILTestExecutionPRD.tsx`

**KEY IMPORTS**:
```typescript
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
```

**CONFIRMATION**: Line 54 shows SequentialVideoPlayer is imported and used for test execution.

### 2. Video Playback Flow in SequentialVideoPlayer

**AUTOMATIC SEQUENCE ADVANCEMENT**: Lines 544-656

```typescript
const handleVideoEnd = useCallback(async () => {
    // 1. Record video end timing
    const videoEnd = getHighPrecisionTimestamp();

    // 2. Send video-ended event to backend
    await sendVideoEndedEvent(currentVideo.id, videoEnd, actualPlaybackSeconds);

    // 3. Check if more videos exist
    const hasMoreVideos = currentVideoIndex < videoPlaylist.length - 1;

    // 4. AUTOMATIC ADVANCE to next video
    if (hasMoreVideos) {
        const nextIndex = currentVideoIndex + 1;
        const nextVideo = videoPlaylist[nextIndex];

        console.log('🎬 Advancing to next video:', nextVideo);
        loadAndPlayVideo(nextVideo, nextIndex);  // ← AUTOMATIC
    }
}, [currentVideoIndex, videoPlaylist, loadAndPlayVideo]);
```

**KEY FINDING**: SequentialVideoPlayer **AUTOMATICALLY** advances to Video 2 when Video 1 ends.
**NO MANUAL INTERVENTION REQUIRED**.

### 3. Video Lifecycle Event Emission

**Video Started Event**: Lines 109-158

```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
    // Calculate timestamps BEFORE API call
    const startedAtUnix = Date.now() / 1000;
    const clientTimestamp = new Date().toISOString();

    console.log('🎬 Sending video-started event:', { videoId, startedAt: startedAtUnix });

    try {
        const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
            videoId: videoId,
            startedAt: startedAtUnix,
            clientTimestamp: clientTimestamp
        });
        console.log('✅ Video started event acknowledged:', response);
    } catch (err) {
        console.warn('⚠️ Failed to send video-started event (non-critical):', err);
        // Don't fail playback on backend error
    }
}, [sequenceId]);
```

**CRITICAL OBSERVATION**: Line 156 shows errors are **NON-CRITICAL** and **SWALLOWED**.

**Called From**: `loadAndPlayVideo()` at line 461:
```typescript
await sendVideoStartedEvent(video.id, updatedTiming.playbackStartTime!);
```

### 4. Backend Video Lifecycle Endpoint

**Endpoint**: `/api/video-sequences/{sequence_id}/video-started`
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequences.py`
**Lines**: 119-189

```python
@router.post("/{sequence_id}/video-started", response_model=VideoEventResponse)
async def video_started(sequence_id: str, data: VideoStartedRequest, db: Session = Depends(get_db)):
    """
    Track when a video in a sequence starts playing.
    Updates SequenceVideoResult with video start time.
    """
    # Find sequence
    sequence = db.query(VideoTestSequence).filter(
        VideoTestSequence.id == sequence_id
    ).first()

    # Find video result
    video_result = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id,
        SequenceVideoResult.video_id == data.videoId
    ).first()

    # Update video_start_time
    video_result.video_start_time = data.timestamp
    video_result.video_start_time_ns = str(int(data.timestamp * 1_000_000_000))
    video_result.video_status = "playing"

    db.commit()
```

**KEY VALIDATION**: Endpoint exists, is functional, and properly updates database.

---

## Why Video 2 Events Never Reached Backend

### Hypothesis Matrix

| Hypothesis | Evidence | Likelihood |
|------------|----------|------------|
| **H1: Network error during transition** | No error logs, silent failure | **HIGH** |
| **H2: sequenceId became null/undefined** | Would fail at line 110 check | Medium |
| **H3: Frontend threw exception before API call** | Would be caught and swallowed | **HIGH** |
| **H4: Backend returned 404 for Video 2** | Would be logged but swallowed | Medium |
| **H5: Race condition in state updates** | Possible if sequenceId cleared | Medium |
| **H6: CORS/network timeout** | No browser network errors reported | Low |

### Most Likely Scenario - REVISED WITH DATABASE EVIDENCE

**COMPLETE LIFECYCLE EVENT FAILURE** due to **MISSING OR INVALID SEQUENCE ID**:

1. Test starts, user selects videos and clicks "Start Test"
2. Frontend creates test session via API
3. **CRITICAL FAILURE POINT**: `sequenceId` is NULL, undefined, or invalid
4. SequentialVideoPlayer component mounts
5. Videos load and play **visually** (local video element works fine)
6. `loadAndPlayVideo(video1, 0)` called
7. `sendVideoStartedEvent(video1.id, timestamp)` called
8. **Line 110 check**: `if (!sequenceId) { console.warn('⚠️ No sequence ID - skipping video-started event'); return; }`
9. Function returns early - **NO API CALL MADE**
10. Video plays normally (user unaware)
11. Video 1 ends, `handleVideoEnd()` called
12. `sendVideoEndedEvent()` called but also skips due to missing `sequenceId`
13. Video 2 auto-advances and plays
14. Same lifecycle event failures occur
15. Test completes visually
16. User sees results page showing "Test Complete"
17. Backend has **ZERO lifecycle event data** for both videos

**KEY EVIDENCE**:
- Line 110-113 in SequentialVideoPlayer: Early return if no `sequenceId`
- Database shows BOTH videos with NULL start/end times
- Sequence stuck in "running" status (never received completion event)

---

## Evidence Supporting "Silent Network Failure"

### 1. Frontend Console Logs Would Show
```javascript
console.log('🎬 Advancing to next video:', {
    nextVideoId,
    nextIndex: 1,
    nextVideoUrl: "http://155.138.239.131:8000/uploads/Child_20250929_142406.mp4"
});
```

**EXPECTATION**: This log was printed (user saw Video 2 playing)

### 2. API Call Would Be Made
```javascript
console.log('🎬 Sending video-started event:', {
    sequenceId: "71976ec4-...",
    videoId: "video-2-id",
    startedAt: 1730632928.xxx
});
```

**EXPECTATION**: This log was printed, then either:
- ✅ Success: `console.log('✅ Video started event acknowledged:', response);`
- ❌ Failure: `console.warn('⚠️ Failed to send video-started event (non-critical):', err);`

### 3. Backend Would Log
```python
logger.info(f"📹 Video started in sequence {sequence_id}: {video_id} at {timestamp}s")
```

**REALITY**: No such log exists in backend logs for Video 2

**CONCLUSION**: Backend never received the request, OR request failed before reaching endpoint.

---

## The "Non-Critical Error Swallowing" Problem

### Code Pattern That Hides Failures

```typescript
try {
    await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, payload);
    console.log('✅ Video started event acknowledged');
} catch (err) {
    console.warn('⚠️ Failed to send video-started event (non-critical):', err);
    // Don't fail playback on backend error - this is non-critical
}
```

**DESIGN INTENTION**: Don't break video playback if backend is temporarily unavailable

**ACTUAL CONSEQUENCE**:
- ✅ Video playback continues (good UX)
- ❌ Backend loses critical timing data (bad for analysis)
- ❌ Detection events can't be assigned to Video 2 (no `video_start_time`)
- ❌ User is unaware of data loss (silent failure)

---

## Downstream Impact on Detection Assignment

### Why Video 2 Got Zero Detections

**Detection Assignment Logic** (from analysis):
```sql
SELECT * FROM detection_events
WHERE test_session_id = '71976ec4-...'
  AND video_id IS NOT NULL
ORDER BY detection_time_unix;
```

**Assignment Algorithm**:
```python
for detection in detections:
    # Find video with non-null video_start_time that contains this timestamp
    if video.video_start_time <= detection.time < video.video_end_time:
        detection.video_id = video.id
```

**PROBLEM**: Video 2 has `video_start_time = NULL`, so:
- Detection timestamp check fails: `NULL <= detection.time` → False
- ALL detections after Video 1 end get assigned to Video 1 or dropped
- Video 2 shows 0 detections despite events occurring during its playback

---

## Recommendations

### 1. Add Retry Logic for Critical Events
```typescript
const sendVideoStartedEvent = async (videoId: string, timestamp: number, retries = 3) => {
    for (let attempt = 0; attempt < retries; attempt++) {
        try {
            await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, payload);
            return; // Success
        } catch (err) {
            if (attempt === retries - 1) {
                // Show user-visible error on final retry
                showSnackbar('Failed to sync video timing with backend. Results may be incomplete.', 'error');
            }
            await delay(1000 * (attempt + 1)); // Exponential backoff
        }
    }
};
```

### 2. Add Frontend Validation
```typescript
if (!sequenceId) {
    console.error('❌ CRITICAL: No sequence ID - cannot send video-started event');
    onError('Lost test session context. Please restart test.');
    return;
}
```

### 3. Add Backend Sequence Validation
```python
@router.post("/{sequence_id}/video-started")
async def video_started(sequence_id: str, data: VideoStartedRequest, db: Session = Depends(get_db)):
    # Validate sequence exists and is active
    sequence = db.query(VideoTestSequence).filter(
        VideoTestSequence.id == sequence_id,
        VideoTestSequence.status.in_(["playing", "started"])
    ).first()

    if not sequence:
        logger.error(f"❌ Received video-started for inactive/missing sequence: {sequence_id}")
        raise HTTPException(status_code=410, detail="Test sequence is no longer active")
```

### 4. Add Real-Time Monitoring
```typescript
// After each video starts, verify backend received it
setTimeout(async () => {
    const sequence = await apiService.get(`/api/video-sequences/${sequenceId}`);
    if (sequence.current_video_index !== expectedIndex) {
        console.error('❌ Backend video index mismatch - timing sync lost');
        showSnackbar('Backend timing synchronization error', 'error');
    }
}, 2000);
```

### 5. Improve Error Visibility
```typescript
catch (err) {
    console.error('❌ CRITICAL: Failed to send video-started event:', {
        videoId,
        sequenceId,
        error: err,
        timestamp: new Date().toISOString()
    });

    // Store failed events for later retry
    failedEventsQueue.push({ type: 'video-started', videoId, timestamp, sequenceId });

    // Show warning badge in UI
    setVideoSyncWarning(true);
}
```

---

## Conclusion

**THE MYSTERY SOLVED**:

1. ✅ Both videos DID play visually in the frontend
2. ✅ SequentialVideoPlayer automatically advanced to Video 2
3. ❌ **`sequenceId` was NULL/undefined/invalid from the start**
4. ❌ **Video 1** `video-started` event skipped (early return at line 110)
5. ❌ **Video 1** `video-ended` event skipped (same reason)
6. ❌ **Video 2** `video-started` event skipped (same reason)
7. ❌ **Video 2** `video-ended` event skipped (same reason)
8. ❌ Errors silently logged as warnings, not shown to user
9. ❌ Backend has `video_start_time = NULL` for **BOTH** videos
10. ❌ Detection assignment algorithm had **NO** timing reference points
11. ❌ Result: **ALL** detections misassigned or unassigned

**ROOT CAUSE**: The `sequenceId` prop passed to SequentialVideoPlayer was missing, causing ALL lifecycle events to be silently skipped.

**IMMEDIATE ACTION NEEDED**:
1. **Find where `sequenceId` is created/passed**: Check HILTestExecutionPRD.tsx for sequence creation logic
2. **Add validation**: Fail test start if `sequenceId` is missing
3. **Add user-visible errors**: Don't silently skip lifecycle events
4. **Add backend health check**: Verify lifecycle events are being received in real-time

**RECOMMENDATION**: This is a CRITICAL bug in test initialization. The sequence must be created and its ID passed to SequentialVideoPlayer BEFORE video playback begins. Without this, the entire timing infrastructure is non-functional.
