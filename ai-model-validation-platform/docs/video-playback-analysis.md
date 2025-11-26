# Video Playback Issue Analysis

**Date**: 2025-11-14
**Component**: SequentialVideoPlayer
**Issue**: Video not playing after expectedStartTime fix

---

## Executive Summary

The video is not playing after the build succeeded because `safeVideoPlay()` is returning `success: false` due to **metadata not being loaded** when the play attempt is made. This is a **race condition** between the metadata loading promise and the play attempt.

---

## Root Cause Analysis

### Primary Issue: Race Condition in loadAndPlayVideo()

**Location**: `SequentialVideoPlayer.tsx` lines 595-621

The problem occurs in this sequence:

```typescript
// Lines 572-593: Wait for metadata to load
await new Promise<void>((resolve, reject) => {
  const timeoutId = setTimeout(() => {
    reject(new Error('Video metadata load timeout'));
  }, 10000);

  const handleLoad = () => {
    clearTimeout(timeoutId);
    videoRef.current?.removeEventListener('loadedmetadata', handleLoad);
    videoRef.current?.removeEventListener('error', handleError);
    resolve();  // ✅ Promise resolves here
  };

  const handleError = () => {
    clearTimeout(timeoutId);
    videoRef.current?.removeEventListener('loadedmetadata', handleLoad);
    videoRef.current?.removeEventListener('error', handleError);
    reject(new Error(`Video load error: ${videoRef.current?.error?.message || 'Unknown error'}`));
  };

  videoRef.current?.addEventListener('loadedmetadata', handleLoad);
  videoRef.current?.addEventListener('error', handleError);
});

// Lines 598-599: Send video-started event
const actualStartTimestamp = Date.now();
await sendVideoStartedEvent(video.id, actualStartTimestamp);

// Lines 602-621: Attempt to play video
const playResult = await safeVideoPlay(videoRef.current, {
  userInitiated: true,
  forceMuted: false
});
```

**The Problem**:
1. The `loadedmetadata` event fires
2. The promise resolves immediately
3. Code proceeds to `sendVideoStartedEvent()` (which takes time due to network request)
4. Then `safeVideoPlay()` is called
5. **BUT**: Even though `loadedmetadata` fired, the video element's `readyState` might still be `HAVE_METADATA (1)` instead of `HAVE_CURRENT_DATA (2)` or higher
6. `safeVideoPlay()` checks `readyState < HAVE_METADATA` at line 162 of `videoUtils.ts`

---

## Code Analysis

### safeVideoPlay() Check (videoUtils.ts:162-165)

```typescript
// Check if video is ready to play
if (videoElement.readyState < HTMLMediaElement.HAVE_METADATA) {
  console.log('🔍 DEBUG: Video metadata not loaded, readyState:', videoElement.readyState);
  return { success: false, error: new Error('Video metadata not loaded') };
}
```

**HTML5 Video readyState Values**:
- `HAVE_NOTHING = 0` - No information about media
- `HAVE_METADATA = 1` - Metadata loaded (duration, dimensions)
- `HAVE_CURRENT_DATA = 2` - Data for current position available
- `HAVE_FUTURE_DATA = 3` - Data for current + future positions available
- `HAVE_ENOUGH_DATA = 4` - Enough data to play without buffering

### The Race Condition

**What's happening**:
```
Time  | Event
------|----------------------------------------------------------
T0    | videoRef.current.load() called
T1    | 'loadedmetadata' event fires → Promise resolves
T2    | sendVideoStartedEvent() starts (network delay ~50-200ms)
T3    | sendVideoStartedEvent() completes
T4    | safeVideoPlay() called
T5    | readyState check: Still HAVE_METADATA (1) ❌
T6    | Returns {success: false, error: 'Video metadata not loaded'}
```

**Expected behavior**:
- `readyState` should be ≥ `HAVE_METADATA (1)` for the check to pass
- The check currently uses `<` which means it requires `> HAVE_METADATA`
- This effectively requires `HAVE_CURRENT_DATA (2)` or higher

---

## Secondary Issues Identified

### 1. Line 598: Premature sendVideoStartedEvent()

**Current Code**:
```typescript
const actualStartTimestamp = Date.now();
await sendVideoStartedEvent(video.id, actualStartTimestamp);
```

**Issue**: This sends the event **before** playback actually starts. The timestamp doesn't represent actual playback start, just when we attempt to start.

**Comment says** (line 595-597):
```typescript
// FIX #4: Send video-started event BEFORE playback starts
// This ensures SequenceVideoResult exists before LabJack detections arrive
// Prevents NULL video_id race condition
```

**This is correct** for preventing NULL video_id issues with LabJack, but the timestamp is misleading.

### 2. Line 623: waitForPlaybackStart() Called After safeVideoPlay()

**Current Code**:
```typescript
const playResult = await safeVideoPlay(videoRef.current, {
  userInitiated: true,
  forceMuted: false
});

// ... error checking ...

const playbackStartedAt = await waitForPlaybackStart(videoRef.current);
```

**Issue**: If `safeVideoPlay()` fails, we never reach `waitForPlaybackStart()`, so we never get the actual playback timestamp.

### 3. Inconsistent Timestamp Usage

**Three different timestamps are used**:
1. `actualStartTimestamp = Date.now()` (line 598) - Before play attempt
2. `playbackStartedAt = await waitForPlaybackStart()` (line 623) - After `playing` event
3. `updatedTiming.playbackStartTime` (line 633) - From timing metadata

**This creates confusion** about which timestamp represents actual playback start.

---

## Recommended Fixes

### Fix #1: Change readyState Check (CRITICAL)

**File**: `frontend/src/utils/videoUtils.ts`
**Line**: 162

**Current**:
```typescript
if (videoElement.readyState < HTMLMediaElement.HAVE_METADATA) {
```

**Should be**:
```typescript
if (videoElement.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
```

**OR wait for higher readyState**:
```typescript
if (videoElement.readyState < HTMLMediaElement.HAVE_ENOUGH_DATA) {
```

**Reasoning**:
- `HAVE_METADATA` means we know the video dimensions and duration
- But we need `HAVE_CURRENT_DATA` or `HAVE_ENOUGH_DATA` to actually play
- The check should wait for sufficient data to be loaded

### Fix #2: Add Explicit readyState Wait

**File**: `frontend/src/components/SequentialVideoPlayer.tsx`
**Location**: After line 593 (after metadata load promise)

**Add**:
```typescript
// Wait for sufficient data to be available for playback
await new Promise<void>((resolve, reject) => {
  const checkReadyState = () => {
    if (videoRef.current?.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      resolve();
    } else {
      setTimeout(checkReadyState, 50); // Poll every 50ms
    }
  };

  // Set timeout
  const timeoutId = setTimeout(() => {
    reject(new Error('Timeout waiting for video data'));
  }, 5000);

  checkReadyState();
});
```

**OR use event-based approach**:
```typescript
// Wait for 'canplay' or 'canplaythrough' event
await new Promise<void>((resolve, reject) => {
  const timeoutId = setTimeout(() => {
    cleanup();
    reject(new Error('Timeout waiting for video to be playable'));
  }, 5000);

  const handleCanPlay = () => {
    cleanup();
    resolve();
  };

  const cleanup = () => {
    clearTimeout(timeoutId);
    videoRef.current?.removeEventListener('canplay', handleCanPlay);
  };

  videoRef.current?.addEventListener('canplay', handleCanPlay);

  // If already playable, resolve immediately
  if (videoRef.current?.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
    cleanup();
    resolve();
  }
});
```

### Fix #3: Reorder Operations (RECOMMENDED)

**File**: `frontend/src/components/SequentialVideoPlayer.tsx`
**Lines**: 595-640

**Current Order**:
1. Wait for metadata
2. Send video-started event
3. Try to play
4. Wait for 'playing' event
5. Record playback start

**Recommended Order**:
1. Wait for metadata
2. Wait for sufficient data (canplay event)
3. Try to play
4. Wait for 'playing' event
5. **THEN** send video-started event with actual timestamp
6. Record playback start

**Implementation**:
```typescript
// Load video source
videoRef.current.src = video.url || '';
videoRef.current.load();

// Wait for metadata to load
await new Promise<void>((resolve, reject) => {
  const timeoutId = setTimeout(() => {
    reject(new Error('Video metadata load timeout'));
  }, 10000);

  const handleLoad = () => {
    clearTimeout(timeoutId);
    videoRef.current?.removeEventListener('loadedmetadata', handleLoad);
    videoRef.current?.removeEventListener('error', handleError);
    resolve();
  };

  const handleError = () => {
    clearTimeout(timeoutId);
    videoRef.current?.removeEventListener('loadedmetadata', handleLoad);
    videoRef.current?.removeEventListener('error', handleError);
    reject(new Error(`Video load error: ${videoRef.current?.error?.message || 'Unknown error'}`));
  };

  videoRef.current?.addEventListener('loadedmetadata', handleLoad);
  videoRef.current?.addEventListener('error', handleError);
});

// Wait for video to be playable (HAVE_CURRENT_DATA or higher)
await new Promise<void>((resolve, reject) => {
  const timeoutId = setTimeout(() => {
    cleanup();
    reject(new Error('Timeout waiting for video to be playable'));
  }, 10000);

  const handleCanPlay = () => {
    cleanup();
    resolve();
  };

  const cleanup = () => {
    clearTimeout(timeoutId);
    videoRef.current?.removeEventListener('canplay', handleCanPlay);
  };

  // Check if already playable
  if (videoRef.current?.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
    cleanup();
    resolve();
    return;
  }

  videoRef.current?.addEventListener('canplay', handleCanPlay);
});

console.log('✅ Video is ready to play, readyState:', videoRef.current?.readyState);

// Play video and wait for the first playing event
const playResult = await safeVideoPlay(videoRef.current, {
  userInitiated: true,
  forceMuted: false
});

if (!playResult.success) {
  throw new Error(`Failed to play video: ${playResult.error?.message || 'Unknown error'}`);
}

// Wait for actual playback to start
const playbackStartedAt = await waitForPlaybackStart(videoRef.current);

// NOW send video-started event with actual playback timestamp
await sendVideoStartedEvent(video.id, playbackStartedAt);

// Record playback start with high precision
const updatedTiming = recordVideoPlaybackStart(
  currentVideoTimingRef.current,
  playbackStartedAt
);
currentVideoTimingRef.current = updatedTiming;
```

**Benefits**:
- ✅ Ensures video is truly playable before play attempt
- ✅ Sends accurate playback timestamp to backend
- ✅ Eliminates race condition between metadata and playability
- ✅ Maintains LabJack detection ordering (video-started still sent before detections)

---

## Testing Recommendations

### Console Logs to Check

Add these debug logs to verify the fix:

```typescript
console.log('🎬 Metadata loaded, readyState:', videoRef.current?.readyState);
console.log('🎬 Waiting for canplay event...');
// ... after canplay ...
console.log('✅ Video canplay, readyState:', videoRef.current?.readyState);
console.log('🎬 Attempting playback...');
// ... after play() ...
console.log('✅ Play succeeded, waiting for playing event...');
// ... after playing event ...
console.log('✅ Playing event fired at:', playbackStartedAt);
```

### Expected Output

```
🎬 Metadata loaded, readyState: 1
🎬 Waiting for canplay event...
✅ Video canplay, readyState: 3
🎬 Attempting playback...
🔍 DEBUG: safeVideoPlay() called with options: {userInitiated: true, forceMuted: false}
🔍 DEBUG: Video element state: {readyState: 3, paused: true, ...}
🔍 DEBUG: Video metadata is loaded, proceeding with playback
🔍 DEBUG: Attempting normal (unmuted) playback
🔍 DEBUG: videoElement.play() called, promise: Promise {<pending>}
🔍 DEBUG: Normal playback succeeded
✅ Play succeeded, waiting for playing event...
✅ Playing event fired at: 1731589712345.678
🎬 Sending video-started event to backend (with millisecond precision): {...}
```

---

## Impact Assessment

### Current Behavior
- ❌ Video fails to play
- ❌ User sees error message
- ❌ Test sequence cannot continue
- ❌ Invalid timestamps sent to backend

### After Fix #1 (Change readyState check only)
- ✅ Video should play (if data is available)
- ⚠️ Still risk of race condition if network is slow
- ⚠️ Timestamp may be inaccurate

### After Fix #3 (Recommended full fix)
- ✅ Video plays reliably
- ✅ Accurate timestamps
- ✅ Proper sequencing of events
- ✅ No race conditions
- ✅ Works on slow networks

---

## Additional Notes

### Browser Autoplay Policy Compliance

The code already handles autoplay blocking:
- Lines 607-618 check for `NotAllowedError`
- User-friendly error message displayed
- Muted fallback available

**This is working correctly** and doesn't need changes.

### Video URL Handling

The code includes extensive URL validation:
- Lines 459-510 validate and fix URLs
- HEAD request tests accessibility
- Multiple fallback mechanisms

**This is also working correctly** and doesn't contribute to the playback issue.

---

## Conclusion

The video playback failure is caused by a **race condition** where `safeVideoPlay()` is called before the video has sufficient data loaded for playback. The `readyState` check in `safeVideoPlay()` incorrectly assumes that `HAVE_METADATA` is sufficient, when actually `HAVE_CURRENT_DATA` or `HAVE_ENOUGH_DATA` is needed.

**Recommended Action**: Implement Fix #3 (reorder operations) for the most robust solution.

**Quick Fix**: Implement Fix #1 (change readyState check) if time is limited.

**Both fixes should be applied** for maximum reliability.
