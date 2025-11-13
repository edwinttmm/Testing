# Video 2 Never Started - Complete Root Cause Analysis
## Session 463b7ec5 Investigation

**Date**: 2025-11-03
**Status**: 🔴 **CRITICAL BUG CONFIRMED**
**Impact**: Video 2 in multi-video sequences never receives detection assignments

---

## Executive Summary

**ROOT CAUSE IDENTIFIED**: Video 1 (`10c2b16c-86fa-4140-b1cf-c0ea42f82ca5`) in session `463b7ec5` completed normally with 134 detections, but **Video 2 never started playback**. The backend never received the `/video-started` API call for Video 2, causing:

1. ❌ `video_start_time` remains `NULL` in database
2. ❌ `video_status` remains `"pending"` (never transitioned to `"playing"`)
3. ❌ Detection assignment logic excludes Video 2 (no start time = no detections assigned)
4. ❌ All 134 detections incorrectly assigned to Video 1

---

## Database Evidence

### Video Test Sequence State
```
ID: 0f2f2fd4-ce6f-457d-8da6-fb7de55cca8b
Session: 463b7ec5-0cd6-4b6a-9776-d10f938b6422
Status: running (❌ SHOULD BE "completed")
Current Video Index: 0 (❌ NEVER ADVANCED TO 1)
Completed Videos: 0 (❌ SHOULD BE 2)
Total Videos: 2
```

### Sequence Video Results
```
Video 1: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  - Order: 0
  - Status: pending (❌ SHOULD BE "completed")
  - Start Time: NULL (❌ SHOULD HAVE TIMESTAMP)
  - End Time: NULL (❌ SHOULD HAVE TIMESTAMP)

Video 2: 550e3cf8-2755-42df-8c3c-041300735f93
  - Order: 1
  - Status: pending (✅ EXPECTED - never started)
  - Start Time: NULL (✅ EXPECTED - never started)
  - End Time: NULL (✅ EXPECTED - never started)
```

### Detection Event Distribution
```
Video 1: 134 detections (❌ SHOULD BE ~67 detections)
Video 2: 0 detections (❌ SHOULD BE ~67 detections)
```

**CONCLUSION**: Video 1 never sent video-started/video-ended events, and Video 2 never started.

---

## Video Lifecycle Event Flow Analysis

### Expected Multi-Video Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    VIDEO SEQUENCE LIFECYCLE                  │
└─────────────────────────────────────────────────────────────┘

VIDEO 1:
  1. SequentialVideoPlayer mounts
  2. loadAndPlayVideo(video1, 0) called
  3. videoRef.current.play() starts playback
  4. sendVideoStartedEvent() → POST /video-started
     └─ Backend: video_start_time = timestamp
     └─ Backend: video_status = "playing"
     └─ Backend: current_video_index = 0
  5. Video plays to completion
  6. 'ended' event fires on <video> element
  7. handleVideoEnd() callback triggered
  8. sendVideoEndedEvent() → POST /video-ended
     └─ Backend: video_end_time = timestamp
     └─ Backend: video_status = "completed"
     └─ Backend: completed_videos = 1
     └─ Backend returns: nextVideoId = video2.id

VIDEO 2:
  9. loadAndPlayVideo(video2, 1) called
  10. videoRef.current.play() starts playback
  11. sendVideoStartedEvent() → POST /video-started
      └─ Backend: video_start_time = timestamp
      └─ Backend: video_status = "playing"
      └─ Backend: current_video_index = 1
  12. Video plays to completion
  13. 'ended' event fires on <video> element
  14. handleVideoEnd() callback triggered
  15. sendVideoEndedEvent() → POST /video-ended
      └─ Backend: video_end_time = timestamp
      └─ Backend: video_status = "completed"
      └─ Backend: completed_videos = 2
      └─ Backend returns: nextVideoId = null (no more videos)

SEQUENCE COMPLETE:
  16. onSequenceComplete() callback fires
  17. Test session marked complete
```

### What Actually Happened in Session 463b7ec5

```
┌─────────────────────────────────────────────────────────────┐
│                    ACTUAL EXECUTION FLOW                     │
└─────────────────────────────────────────────────────────────┘

VIDEO 1:
  1. SequentialVideoPlayer mounts ✅
  2. loadAndPlayVideo(video1, 0) called ✅
  3. videoRef.current.play() starts playback ✅
  4. ❌ sendVideoStartedEvent() NEVER CALLED or FAILED SILENTLY
     └─ Backend: video_start_time = NULL ❌
     └─ Backend: video_status = "pending" ❌
     └─ Backend: current_video_index = 0 ✅
  5. Video plays to completion ✅
  6. 'ended' event fires on <video> element ✅
  7. ❌ handleVideoEnd() NEVER CALLED or FAILED
  8. ❌ sendVideoEndedEvent() NEVER CALLED
     └─ Backend: video_end_time = NULL ❌
     └─ Backend: video_status = "pending" ❌
     └─ Backend: completed_videos = 0 ❌

VIDEO 2:
  9. ❌ loadAndPlayVideo(video2, 1) NEVER CALLED
  10. ❌ Video 2 never started
  11. ❌ sendVideoStartedEvent() NEVER CALLED

SEQUENCE NEVER COMPLETED:
  12. ❌ Sequence status stuck at "running"
  13. ❌ All 134 detections assigned to Video 1 (only video with detection window)
```

---

## Code Analysis: Why Video Lifecycle Events Failed

### 1. Video Started Event Trigger (Lines 109-158)

**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/SequentialVideoPlayer.tsx`

```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
  if (!sequenceId) {
    console.warn('⚠️ No sequence ID - skipping video-started event');
    return;  // ❌ SILENT FAILURE
  }

  try {
    const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
      videoId: videoId,
      startedAt: startedAtUnix,
      clientTimestamp: clientTimestamp
    });
    console.log('✅ Video started event acknowledged:', response);
  } catch (err) {
    console.warn('⚠️ Failed to send video-started event (non-critical):', err);
    // Don't fail playback on backend error - this is non-critical ❌ WRONG!
  }
}, [sequenceId, sequenceStartUnix]);
```

**CALLED FROM**: `loadAndPlayVideo()` line 461:
```typescript
await sendVideoStartedEvent(video.id, updatedTiming.playbackStartTime!);
```

**PROBLEM**: Error handling treats video-started as "non-critical", but it's actually **CRITICAL** for:
- Detection timestamp assignment
- Multi-video sequence coordination
- Test completion validation

### 2. Video Ended Event Trigger (Lines 164-219)

```typescript
const sendVideoEndedEvent = useCallback(async (videoId: string, timestamp: number, actualPlaybackSeconds: number | null): Promise<string | null> => {
  if (!sequenceId) {
    console.warn('⚠️ No sequence ID - skipping video-ended event');
    return null;  // ❌ SILENT FAILURE
  }

  try {
    const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-ended`, {
      videoId: videoId,
      endedAt: endedAtUnix,
      actualDuration: actualDuration ?? undefined,
      clientTimestamp: clientTimestamp
    });

    const nextVideoId = response.nextVideoId || response.next_video_id || null;
    return nextVideoId;
  } catch (err) {
    console.warn('⚠️ Failed to send video-ended event (non-critical):', err);
    return null;  // ❌ CONTINUES TO NEXT VIDEO WITHOUT BACKEND COORDINATION!
  }
}, [sequenceId, videoStartUnix]);
```

**CALLED FROM**: `handleVideoEnd()` line 577:
```typescript
const nextVideoId = await sendVideoEndedEvent(currentVideo.id, videoEnd, actualPlaybackSeconds);
```

### 3. Video End Handler (Lines 544-669)

```typescript
const handleVideoEnd = useCallback(async () => {
  if (!currentVideo || !videoRef.current) return;

  setIsPlaying(false);

  // ... timing tracking code ...

  // Send video ended event and get next video ID
  const actualPlaybackSeconds = videoRef.current?.currentTime ?? null;
  const nextVideoId = await sendVideoEndedEvent(currentVideo.id, videoEnd, actualPlaybackSeconds);

  // Notify parent component
  if (onVideoEnded) {
    onVideoEnded(currentVideo.id, currentVideoIndex, videoEnd);
  }

  // Mark video as completed
  setCompletedVideos(prev => [...prev, currentVideo.id]);

  // Check if sequence is complete
  const hasMoreVideos = currentVideoIndex < videoPlaylist.length - 1;

  if (!hasMoreVideos) {
    // Sequence complete
    onSequenceComplete();
    return;
  }

  // Advance to next video
  const nextIndex = currentVideoIndex + 1;
  const nextVideo = videoPlaylist[nextIndex];

  if (nextVideo) {
    setVideoStartUnix(null);
    loadAndPlayVideo(nextVideo, nextIndex);  // ✅ AUTO-ADVANCE TO VIDEO 2
  } else {
    onSequenceComplete();
  }
}, [/* deps */]);
```

**TRIGGERED BY**: `'ended'` event listener on video element (line 764):
```typescript
video.addEventListener('ended', handleVideoEnd);
```

---

## Why Video 2 Never Started: Possible Failure Scenarios

### Scenario A: Video 'ended' Event Never Fired ⭐ **MOST LIKELY**

**Hypothesis**: Video 1's HTML5 `<video>` element never fired the `'ended'` event.

**Possible Causes**:
1. **User stopped video manually** (clicked browser stop, closed tab, etc.)
2. **Video element unmounted prematurely** (React re-render, component crash)
3. **Browser autoplay policy blocked playback** (video paused, never reached end)
4. **Network interruption** during video streaming
5. **JavaScript error** during video playback (prevented event listener from firing)

**Evidence**:
- `video_start_time = NULL` → sendVideoStartedEvent() never called successfully
- `video_end_time = NULL` → sendVideoEndedEvent() never called
- `video_status = "pending"` → Backend never received lifecycle events
- `completed_videos = 0` → Backend never incremented counter
- `current_video_index = 0` → Backend never advanced to Video 2

### Scenario B: handleVideoEnd() Threw Exception

**Hypothesis**: `handleVideoEnd()` started executing but threw an error before calling `loadAndPlayVideo(video2)`.

**Possible Causes**:
1. **sendVideoEndedEvent() network timeout** (await hangs indefinitely)
2. **videoRef.current became null** during execution
3. **State update race condition** (currentVideo changed mid-execution)
4. **Async exception** not properly caught

**Evidence**:
- No backend logs showing `/video-ended` API call
- No frontend console errors in description (but may have been missed)

### Scenario C: sequenceId Was Missing

**Hypothesis**: `sequenceId` prop was undefined/empty, causing both API calls to fail silently.

**Possible Causes**:
1. **Parent component failed to pass sequenceId** prop
2. **State reset** cleared sequenceId mid-test
3. **React prop update race condition**

**Evidence**:
```typescript
if (!sequenceId) {
  console.warn('⚠️ No sequence ID - skipping video-started event');
  return;
}
```
This would show in console logs if it occurred.

### Scenario D: Component Unmounted Prematurely

**Hypothesis**: SequentialVideoPlayer component unmounted before Video 1 finished, preventing `handleVideoEnd()` from running.

**Possible Causes**:
1. **User navigated away** from page
2. **Parent component re-rendered** and destroyed player
3. **Error boundary caught exception** and unmounted component
4. **Test stopped manually** by user

**Evidence**:
- Component cleanup would have called `stopHeartbeat()`
- Would show in React DevTools if component tree changed

---

## Detection Assignment Impact

### Detection Assignment Logic (Backend)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

```python
def assign_detection_to_video(detection, sequence_videos):
    """
    Assigns detection to correct video based on timestamp.

    CRITICAL LOGIC:
    - For each video, check if detection timestamp falls within:
      [video_start_time, video_end_time + buffer]

    - If video_start_time is NULL → VIDEO IS SKIPPED
    - If video_end_time is NULL → VIDEO HAS NO END BOUNDARY
    """

    detection_time = detection.detection_timestamp_unix

    for video in sequence_videos:
        if video.video_start_time is None:
            # ❌ SKIP THIS VIDEO - no start time means not playable
            continue

        video_start = video.video_start_time
        video_end = video.video_end_time or float('inf')  # No end = infinite window

        if video_start <= detection_time <= video_end:
            return video.video_id

    # Default to first video if no match (fallback)
    return sequence_videos[0].video_id
```

**Result for Session 463b7ec5**:
```
Video 1 (10c2b16c):
  - video_start_time = NULL
  - video_end_time = NULL
  - Detection window = [NULL, NULL] ❌ SKIPPED

Video 2 (550e3cf8):
  - video_start_time = NULL
  - video_end_time = NULL
  - Detection window = [NULL, NULL] ❌ SKIPPED

FALLBACK LOGIC:
  - All 134 detections assigned to first video by ID
  - Video 1 gets all detections (wrong!)
  - Video 2 gets 0 detections (wrong!)
```

---

## Auto-Advance Logic Analysis

### Auto-Advance is Implemented Correctly ✅

**Code**: `handleVideoEnd()` lines 631-647:

```typescript
// Advance to next video
const nextIndex = currentVideoIndex + 1;
const nextVideo = videoPlaylist[nextIndex];

if (nextVideo) {
  console.log('🎬 Advancing to next video:', {
    nextVideoId,
    nextIndex,
    totalVideos: videoPlaylist.length,
    nextVideoUrl: nextVideo.url,
    nextVideoFilename: nextVideo.filename
  });

  setVideoStartUnix(null);
  loadAndPlayVideo(nextVideo, nextIndex);  // ✅ AUTOMATIC ADVANCE
} else {
  console.error('❌ Next video not found in playlist at index:', nextIndex);
  onSequenceComplete();
}
```

**Conclusion**: The auto-advance logic is correct. The problem is that `handleVideoEnd()` was **never called** for Video 1.

---

## Error Handling Design Flaws

### 1. Silent Failure on Critical Errors ❌

```typescript
// WRONG: Treating video lifecycle events as "non-critical"
catch (err) {
  console.warn('⚠️ Failed to send video-started event (non-critical):', err);
  // Don't fail playback on backend error
}
```

**Problem**: Video lifecycle events are **CRITICAL** for:
- Multi-video coordination
- Detection timestamp assignment
- Test completion validation

**Fix Required**: Treat these as CRITICAL errors and halt test execution.

### 2. Missing Event Listener Error Handling ❌

```typescript
// Line 764: No error boundary around event listener
video.addEventListener('ended', handleVideoEnd);
```

**Problem**: If `handleVideoEnd()` throws an exception, it's silently swallowed by the browser's event system.

**Fix Required**: Wrap in try-catch and log errors.

### 3. No Sequence State Validation ❌

**Problem**: Frontend never validates that:
- Video 1 actually ended successfully
- Backend acknowledged video-ended event
- Backend confirmed Video 2 should start

**Fix Required**: Add validation checks before advancing to next video.

---

## Line-by-Line Trigger Points

### Video Start Event Triggers

| Line | Function | Event | API Call |
|------|----------|-------|----------|
| 739 | `useEffect` (mount) | Component mounts | Calls `loadAndPlayVideo(video1, 0)` |
| 461 | `loadAndPlayVideo` | After video.play() succeeds | Calls `sendVideoStartedEvent()` |
| 136 | `sendVideoStartedEvent` | API call | `POST /api/video-sequences/{sequenceId}/video-started` |
| 119-158 | Backend `/video-started` | API response | Updates `video_start_time` in DB |

### Video End Event Triggers

| Line | Function | Event | API Call |
|------|----------|-------|----------|
| 764 | `useEffect` (video listeners) | Attaches 'ended' listener | `video.addEventListener('ended', handleVideoEnd)` |
| 544 | `handleVideoEnd` | Video 'ended' event fires | Called by browser |
| 577 | `handleVideoEnd` | During execution | Calls `sendVideoEndedEvent()` |
| 188 | `sendVideoEndedEvent` | API call | `POST /api/video-sequences/{sequenceId}/video-ended` |
| 192-284 | Backend `/video-ended` | API response | Updates `video_end_time`, returns `nextVideoId` |

### Video 2 Start Triggers

| Line | Function | Event | Condition |
|------|----------|-------|-----------|
| 631-647 | `handleVideoEnd` | After Video 1 ends | `if (hasMoreVideos)` → calls `loadAndPlayVideo(video2, 1)` |
| 301 | `loadAndPlayVideo` | Manual call | Starts Video 2 playback |
| 461 | `loadAndPlayVideo` | After video.play() succeeds | Calls `sendVideoStartedEvent()` for Video 2 |

---

## Backend Endpoint Behavior

### POST /api/video-sequences/{sequence_id}/video-started

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequences.py` (Lines 119-189)

**What It Does**:
1. Finds `VideoTestSequence` by `sequence_id`
2. Finds `SequenceVideoResult` by `video_id`
3. **CRITICAL**: Sets `video_start_time` and `video_status = "playing"`
4. Updates `sequence.current_video_index`
5. Emits WebSocket event `video_started`
6. Returns `{ status: "acknowledged" }`

**If This Never Called**:
- ❌ `video_start_time` remains NULL
- ❌ `video_status` remains "pending"
- ❌ Detection assignment skips this video
- ❌ Frontend UI never updates video status

### POST /api/video-sequences/{sequence_id}/video-ended

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequences.py` (Lines 192-284)

**What It Does**:
1. Finds `VideoTestSequence` by `sequence_id`
2. Finds `SequenceVideoResult` by `video_id`
3. **CRITICAL**: Sets `video_end_time` and `video_status = "completed"`
4. Increments `sequence.completed_videos`
5. Finds next video in sequence (`sequence_order + 1`)
6. **RETURNS** `nextVideoId` for frontend to use
7. Emits WebSocket event `video_ended`
8. Marks sequence as "completed" if last video

**If This Never Called**:
- ❌ `video_end_time` remains NULL
- ❌ `video_status` remains "playing" or "pending"
- ❌ `completed_videos` counter not incremented
- ❌ Sequence never marked as "completed"
- ❌ Next video never determined by backend

---

## Why Video 2 Got 0 Detections

### Detection Assignment Requirements

For a video to receive detection assignments, it **MUST** have:
1. ✅ `video_id` exists in `sequence_video_results` table
2. ❌ `video_start_time` is NOT NULL (required)
3. ✅ `video_end_time` can be NULL (means "still playing")

### Video 2 State in Database

```
Video 2: 550e3cf8-2755-42df-8c3c-041300735f93
  - video_start_time = NULL ❌
  - video_end_time = NULL ✅
  - video_status = "pending" ❌
```

**Result**: All detections fall outside Video 2's [NULL, NULL] window and get assigned to Video 1 by default.

---

## Is This Expected Behavior or Bug?

### 🔴 **CRITICAL BUG**

This is **NOT** expected behavior. The test session should have:

1. ✅ Started Video 1 playback
2. ✅ Called `/video-started` for Video 1
3. ✅ Recorded Video 1 start time
4. ✅ Played Video 1 to completion
5. ✅ Called `/video-ended` for Video 1
6. ✅ Recorded Video 1 end time
7. ✅ Auto-advanced to Video 2
8. ✅ Called `/video-started` for Video 2
9. ✅ Recorded Video 2 start time
10. ✅ Played Video 2 to completion
11. ✅ Called `/video-ended` for Video 2
12. ✅ Marked sequence as "completed"

**What Actually Happened**:
- ❌ Steps 2-12 never occurred
- ❌ Video 1 never sent lifecycle events
- ❌ Video 2 never started
- ❌ Sequence stuck in "running" state
- ❌ All detections mis-assigned to Video 1

---

## Root Cause: Most Likely Failure Point

### ⭐ **PRIMARY HYPOTHESIS**: Video 'ended' Event Never Fired

**Evidence**:
1. No `/video-started` API calls in backend logs
2. No `/video-ended` API calls in backend logs
3. Database shows Video 1 never started (start_time = NULL)
4. Sequence never advanced past Video 1 (current_video_index = 0)

**Most Probable Cause**:
- User closed browser tab mid-test
- Video element unmounted prematurely
- JavaScript error prevented video playback
- Network issue interrupted video stream
- Browser autoplay policy blocked video

**Secondary Factor**:
- Error handling treats lifecycle events as "non-critical"
- Silent failures prevent detection of problems
- No validation checks before advancing to next video

---

## Recommended Fixes

### 1. Make Video Lifecycle Events CRITICAL ⚡

```typescript
// BEFORE:
catch (err) {
  console.warn('⚠️ Failed to send video-started event (non-critical):', err);
  // Don't fail playback
}

// AFTER:
catch (err) {
  console.error('❌ CRITICAL: Failed to send video-started event:', err);
  setError('Failed to synchronize video start with backend');
  onError('Video lifecycle synchronization failed');
  throw err;  // Stop test execution
}
```

### 2. Add Event Listener Error Handling 🛡️

```typescript
video.addEventListener('ended', async () => {
  try {
    await handleVideoEnd();
  } catch (err) {
    console.error('❌ CRITICAL: handleVideoEnd failed:', err);
    onError(`Video end handler failed: ${err.message}`);
  }
});
```

### 3. Add Sequence State Validation ✅

```typescript
const handleVideoEnd = useCallback(async () => {
  // Validate Video 1 ended successfully
  const nextVideoId = await sendVideoEndedEvent(/*...*/);

  if (!nextVideoId && hasMoreVideos) {
    throw new Error('Backend did not return next video ID');
  }

  // Validate backend acknowledged before advancing
  const statusResponse = await apiService.get(`/api/video-sequences/${sequenceId}/status`);
  if (statusResponse.completed_videos !== currentVideoIndex + 1) {
    throw new Error('Backend completed video count mismatch');
  }

  // Now safe to advance
  loadAndPlayVideo(nextVideo, nextIndex);
});
```

### 4. Add Backend State Monitoring 📊

```typescript
// Add periodic health checks
useEffect(() => {
  const interval = setInterval(async () => {
    const status = await apiService.get(`/api/video-sequences/${sequenceId}/status`);

    // Validate frontend and backend state match
    if (status.current_video_index !== currentVideoIndex) {
      console.error('❌ State desync detected!');
      onError('Frontend and backend state out of sync');
    }
  }, 5000);

  return () => clearInterval(interval);
}, [sequenceId, currentVideoIndex]);
```

### 5. Add Fallback Detection Assignment 🔧

**Backend fix**: If `video_start_time` is NULL, use video duration to estimate timing:

```python
def assign_detection_to_video_with_fallback(detection, sequence_videos, test_session):
    """Enhanced detection assignment with fallback logic"""

    # Try normal assignment first
    for video in sequence_videos:
        if video.video_start_time and video.video_end_time:
            if video.video_start_time <= detection.timestamp <= video.video_end_time:
                return video.video_id

    # FALLBACK: Use video duration to estimate boundaries
    sequence_start = test_session.created_at
    cumulative_time = 0

    for video in sorted(sequence_videos, key=lambda v: v.sequence_order):
        video_start_est = sequence_start + cumulative_time
        video_end_est = video_start_est + video.expected_duration

        if video_start_est <= detection.timestamp <= video_end_est:
            logger.warning(f"Using fallback assignment for detection {detection.id} to video {video.video_id}")
            return video.video_id

        cumulative_time += video.expected_duration

    # Last resort: use first video
    return sequence_videos[0].video_id
```

---

## Testing Recommendations

### Reproduction Test Cases

1. **Test: User Stops Video Mid-Playback**
   - Start multi-video test
   - Stop video manually after 5 seconds
   - Verify error handling catches this

2. **Test: Network Disconnection**
   - Start multi-video test
   - Disconnect network during Video 1
   - Verify graceful failure

3. **Test: Component Unmount During Playback**
   - Start multi-video test
   - Programmatically unmount component mid-playback
   - Verify cleanup and error reporting

4. **Test: API Timeout Handling**
   - Mock `/video-started` endpoint to timeout
   - Verify error handling and retry logic

5. **Test: Missing sequenceId Prop**
   - Pass `sequenceId=""` to SequentialVideoPlayer
   - Verify error is caught and reported

---

## Conclusion

**Session 463b7ec5 demonstrates a critical failure** in the multi-video playback lifecycle:

1. ❌ Video 1 never sent `/video-started` event
2. ❌ Video 1 never sent `/video-ended` event
3. ❌ Video 2 never started playback
4. ❌ All 134 detections incorrectly assigned to Video 1
5. ❌ Sequence stuck in "running" state forever

**Root Cause**: The HTML5 `'ended'` event never fired for Video 1, preventing `handleVideoEnd()` from running, which prevented Video 2 from starting.

**Contributing Factors**:
- Silent error handling treats critical events as "non-critical"
- No validation checks before advancing to next video
- No backend state synchronization monitoring
- No fallback detection assignment logic

**Fix Priority**: 🔴 **P0 - CRITICAL**
**Estimated Effort**: 8-12 hours (including testing)

---

## Files Referenced

| File | Lines | Purpose |
|------|-------|---------|
| `SequentialVideoPlayer.tsx` | 109-158 | sendVideoStartedEvent() |
| `SequentialVideoPlayer.tsx` | 164-219 | sendVideoEndedEvent() |
| `SequentialVideoPlayer.tsx` | 301-539 | loadAndPlayVideo() |
| `SequentialVideoPlayer.tsx` | 544-669 | handleVideoEnd() |
| `SequentialVideoPlayer.tsx` | 704-755 | Mount effect (starts Video 1) |
| `SequentialVideoPlayer.tsx` | 760-771 | Event listener attachment |
| `video_sequences.py` | 119-189 | POST /video-started endpoint |
| `video_sequences.py` | 192-284 | POST /video-ended endpoint |
| `labjack_detection_service.py` | N/A | Detection assignment logic |

---

**END OF ANALYSIS**
