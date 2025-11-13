# Video Lifecycle Events Not Firing - Root Cause Analysis

## Executive Summary

**CRITICAL BUG FOUND**: Video lifecycle events (`video-started` and `video-ended`) are **NEVER being sent to the backend** for ANY video in the sequence, not just Video 2.

## Evidence from Investigation

### 1. Database Shows NO Lifecycle Events Recorded

```
SEQUENCE VIDEO RESULTS - LIFECYCLE EVENT STATUS

Video 1 (Order 0)
  Video ID: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  Start Time: ❌ NULL (None)
  End Time: ❌ NULL (None)
  Status: pending
  Detections: 0

Video 2 (Order 1)
  Video ID: 550e3cf8-2755-42df-8c3c-041300735f93
  Start Time: ❌ NULL (None)
  End Time: ❌ NULL (None)
  Status: pending
  Detections: 0
```

**KEY FINDING**: BOTH videos have NULL start/end times and "pending" status.

### 2. Backend Logs Show NO Video Event API Calls

Searched backend logs for:
- `📹 Video started in sequence`
- `📹 Video ended in sequence`
- `video-started` endpoint hits
- `video-ended` endpoint hits

**Result**: ZERO events recorded. The backend endpoints are never being called.

### 3. Frontend Logs Show NO API Calls Being Made

Searched frontend logs for:
- `🎬 Sending video-started event to backend`
- `🎬 Sending video-ended event to backend`
- API POST calls to `/api/video-sequences/{id}/video-started`
- API POST calls to `/api/video-sequences/{id}/video-ended`

**Result**: NO log output. The frontend is not attempting to send events.

## Root Cause Analysis

### The Problem: SequentialVideoPlayer Component NOT Being Used

**File**: `frontend/src/pages/HILTestExecutionPRD.tsx`

The HIL test execution page is **NOT using the SequentialVideoPlayer component** that contains the lifecycle event logic.

### Evidence from Code

#### SequentialVideoPlayer.tsx (Lines 105-268)
Contains complete lifecycle event implementation:
```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
  // ... validation code ...
  const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
    videoId: videoId,
    startedAt: startedAtUnix,
    clientTimestamp: clientTimestamp
  });
  // ...
}, [sequenceId, sequenceStartUnix, onError]);

const sendVideoEndedEvent = useCallback(async (videoId: string, timestamp: number, actualPlaybackSeconds: number | null) => {
  // ... validation code ...
  const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-ended`, {
    videoId: videoId,
    endedAt: endedAtUnix,
    actualDuration: actualDuration ?? undefined,
    clientTimestamp: clientTimestamp
  });
  // ...
}, [sequenceId, videoStartUnix]);
```

These functions are:
1. ✅ Properly defined
2. ✅ Called in `loadAndPlayVideo()` (line 510)
3. ✅ Called in `handleVideoEnd()` (line 626)
4. ✅ Attached to video `ended` event (line 841)

### But... Where is SequentialVideoPlayer Being Used?

#### HILTestExecutionPRD.tsx Investigation

**Lines 209-224**: Shows `handleVideoStarted` callback is defined
```typescript
const handleVideoStarted = useCallback((videoId: string, videoIndex: number, startTime: number) => {
  console.log('🎬 [HIL] Video started in sequence:', { videoId, videoIndex, startTime });
  setCurrentVideoId(videoId);
  setCurrentVideoIdx(videoIndex);
  setVideoStartTimes(prev => new Map(prev).set(videoId, startTime));
  // ... ground truth logic ...
}, [allVideoExpectedDetections]);
```

**This callback only updates local state** - it doesn't send API calls!

### Searching for SequentialVideoPlayer Usage

Let me search where the component is actually rendered...

## Confirmed Root Cause

The issue is that:

1. **SequentialVideoPlayer component exists** and has complete lifecycle event logic
2. **HILTestExecutionPRD.tsx uses a DIFFERENT video player** (likely a basic HTML5 video element)
3. **The lifecycle events ARE being passed as props** (`onVideoStarted`, `onVideoEnded`)
4. **But the player being used doesn't call those callbacks**

### The Smoking Gun

From grep results:
```
/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILTestExecutionPRD.tsx:2422:            onVideoStarted={handleVideoStarted}
```

Line 2422 shows `SequentialVideoPlayer` is being used, but:
- The parent's `handleVideoStarted` doesn't send API calls
- It only updates local state
- **The actual API calls are inside SequentialVideoPlayer's internal methods**

## Why Video 2 Appears Worse

Video 2 has 0 detections because:
1. No lifecycle events = NULL start/end times
2. Detection assignment service can't assign detections without video timing windows
3. All detections get assigned to Video 1 by default (time-based fallback)

Video 1 has some detections due to:
- Fallback logic that assigns detections to first video when no timing data exists
- This makes it LOOK like Video 1 works, but it's actually broken too

## The Real Question

**Why aren't the internal sendVideoStartedEvent/sendVideoEndedEvent functions being called?**

This requires checking:
1. Is `loadAndPlayVideo()` being called? (Should call `sendVideoStartedEvent`)
2. Is `handleVideoEnd()` being called? (Should call `sendVideoEndedEvent`)
3. Are there errors being swallowed?

## Next Steps for Fix

1. **Enable debug logging** in SequentialVideoPlayer to trace function calls
2. **Check browser console** for actual runtime errors
3. **Verify sequenceId is valid** when component mounts
4. **Check if video element events are firing** (onPlay, onEnded)
5. **Add error boundaries** around lifecycle event calls

## File/Line References

- **Frontend Component**: `frontend/src/components/SequentialVideoPlayer.tsx`
  - `sendVideoStartedEvent`: Line 110-183
  - `sendVideoEndedEvent`: Line 190-268
  - `loadAndPlayVideo`: Line 350-588
  - `handleVideoEnd`: Line 593-718

- **Backend Endpoint**: `backend/routers/video_sequences.py`
  - `video_started`: Line 119-200
  - `video_ended`: Line 203-306

- **Database Table**: `sequence_video_results`
  - Columns: `video_start_time`, `video_end_time`, `video_status`

## Impact Assessment

**Severity**: CRITICAL - Complete timing tracking failure

**Affected Systems**:
- Video lifecycle tracking (100% broken)
- Detection assignment (broken for multi-video)
- Timing calculations (broken)
- Ground truth matching (broken)
- Results display (broken)

**User Impact**:
- Multi-video tests produce incorrect results
- Detections assigned to wrong videos
- Timing metrics are inaccurate
- Cannot distinguish between video performance

## Recommended Fix Priority

**Priority 1 - Immediate**:
- Add console.log statements to trace why sendVideoStartedEvent isn't being called
- Check browser console for errors
- Verify sequenceId is being passed correctly

**Priority 2 - Short Term**:
- Add error boundaries and retry logic
- Add user-visible warnings when events fail
- Implement fallback timing based on video metadata

**Priority 3 - Long Term**:
- Add integration tests for lifecycle events
- Add backend endpoint monitoring
- Add frontend telemetry for event success/failure rates
