# Video Player Instrumentation - Edge Case Analysis Report

**Date:** 2025-11-11
**Analyst:** QA & Testing Agent
**Scope:** SequentialVideoPlayer + HILTestExecutionComplete timing instrumentation

---

## Executive Summary

This report analyzes 10 common edge cases plus 8 additional critical failure scenarios identified in the video player timing instrumentation. **Critical finding: 6/18 scenarios require immediate fixes before production deployment.**

### Risk Level Summary
- **CRITICAL (Blocking):** 3 scenarios will cause crashes or data loss
- **HIGH (Must Fix):** 3 scenarios will cause incorrect timing data
- **MEDIUM (Should Fix):** 5 scenarios will degrade user experience
- **LOW (Monitor):** 7 scenarios work correctly but need monitoring

---

## Detailed Scenario Analysis

### 1. User Skips Video Before Playing Event Fires

**Status:** ✅ **PASS** (Gracefully Handled)
**Risk Level:** LOW
**Code Location:** `SequentialVideoPlayer.tsx` lines 101-149

#### Analysis:
```typescript
const waitForPlaybackStart = useCallback(
  (videoEl: HTMLVideoElement, timeoutMs = 5000): Promise<number> => {
    // Cleanup function removes all listeners (lines 115-121)
    const cleanup = () => {
      window.clearTimeout(timeoutId);
      videoEl.removeEventListener('playing', handlePlaying);
      videoEl.removeEventListener('stalled', handlePlaybackError);
      videoEl.removeEventListener('suspend', handlePlaybackError);
      videoEl.removeEventListener('error', handlePlaybackError);
    };
```

**What Happens:**
1. If user calls `stopTest()` or advances video manually
2. Component unmount triggers cleanup (line 888-894)
3. All event listeners are removed
4. Promise remains in pending state but cleanup prevents memory leaks

**Timing Data Impact:**
- Current video timing metadata is NOT added to `videoTimingsRef.current` (line 669)
- Incomplete video is excluded from statistics
- `sequenceElapsedTime` continues counting accurately

**Verdict:** ✅ Works correctly. No timing data corruption.

**Recommendation:**
- Add explicit detection of component unmount in promise
- Log warning when video skipped before playback

---

### 2. Video Fails to Load (404, CORS)

**Status:** ⚠️ **NEEDS FIX** (Partial Handling)
**Risk Level:** HIGH
**Code Location:** `SequentialVideoPlayer.tsx` lines 526-547, 616-641

#### Analysis:
```typescript
// Wait for metadata to load (lines 526-547)
await new Promise<void>((resolve, reject) => {
  const handleError = () => {
    clearTimeout(timeoutId);
    videoRef.current?.removeEventListener('loadedmetadata', handleLoad);
    videoRef.current?.removeEventListener('error', handleError);
    reject(new Error(`Video load error: ${videoRef.current?.error?.message || 'Unknown error'}`));
  };

  videoRef.current?.addEventListener('error', handleError);
});
```

**What Happens:**
1. ✅ Error is caught and logged (line 618)
2. ✅ Retry logic kicks in (lines 625-636)
3. ✅ After 3 retries, error is shown to user (line 638-639)
4. ❌ **BUG:** `waitForPlaybackStart` promise is still pending from line 559
5. ❌ **BUG:** Video timing metadata is never finalized
6. ❌ **BUG:** Sequence may hang if autoAdvanceVideos is true

**Timing Data Impact:**
- `currentVideoTimingRef.current` left in incomplete state
- Not added to `videoTimingsRef.current` array
- Timing statistics exclude failed video
- Next video's `expectedStartTime` calculation is WRONG (line 506)

**Verdict:** ❌ Requires immediate fix.

**Recommended Fix:**
```typescript
catch (err) {
  // Add explicit cleanup
  if (currentVideoTimingRef.current) {
    const failedTiming = {
      ...currentVideoTimingRef.current,
      playbackStartTime: null,
      playbackEndTime: null,
      duration: null,
      actualStartDelay: -1, // Mark as failed
    };
    videoTimingsRef.current.push(failedTiming);
  }

  // Advance to next video after retries exhausted
  if (retryCount >= MAX_RETRY_ATTEMPTS && currentVideoIndex < videoPlaylist.length - 1) {
    setCurrentVideoIndex(prev => prev + 1);
  }
}
```

---

### 3. Autoplay Blocked by Browser

**Status:** 🔴 **CRITICAL FIX REQUIRED**
**Risk Level:** CRITICAL (Blocking)
**Code Location:** `SequentialVideoPlayer.tsx` lines 550-557, `HILTestExecutionComplete.tsx` lines 483

#### Analysis:
```typescript
// Play video (line 550)
const playResult = await safeVideoPlay(videoRef.current, {
  userInitiated: true,
  forceMuted: false
});

if (!playResult.success) {
  throw new Error(`Failed to play video: ${playResult.error?.message || 'Unknown error'}`);
}
```

**What Happens:**
1. ✅ `safeVideoPlay` handles DOMException correctly
2. ❌ **CRITICAL BUG:** If autoplay blocked, promise rejects
3. ❌ **CRITICAL BUG:** `waitForPlaybackStart` called on STOPPED video (line 559)
4. ❌ **CRITICAL BUG:** Promise will timeout after 5 seconds
5. ❌ **CRITICAL BUG:** User sees "Timed out waiting for video to begin playback"
6. ❌ **CRITICAL BUG:** Test is completely BLOCKED - no way to recover

**In HILTestExecutionComplete:**
```typescript
// Line 483 - autoplay without user interaction check
await videoRef.current.play();
```
- No error handling at all
- Will throw unhandled promise rejection
- Test will silently fail

**Timing Data Impact:**
- Complete test failure
- No timing data recorded
- Sequence cannot proceed

**Verdict:** 🔴 **CRITICAL - MUST FIX BEFORE DEPLOYMENT**

**Recommended Fix:**
```typescript
// Add autoplay detection
try {
  const playResult = await safeVideoPlay(videoRef.current, {
    userInitiated: false, // Mark as automated
    forceMuted: true  // Try muted first
  });

  if (!playResult.success) {
    // Fallback: Show UI prompt for user interaction
    setError('Browser blocked autoplay. Click Play to continue.');
    setAwaitingUserInteraction(true);

    // Wait for user click
    await new Promise((resolve) => {
      const handleUserPlay = () => {
        setAwaitingUserInteraction(false);
        resolve(null);
      };
      // Add play button click handler
    });
  }
} catch (err) {
  // Explicit autoplay failure handling
}
```

---

### 4. Video Already Playing When waitForPlaybackStart Called

**Status:** ✅ **PASS** (Handled Correctly)
**Risk Level:** LOW
**Code Location:** `SequentialVideoPlayer.tsx` lines 109-113

#### Analysis:
```typescript
// If playback is already in progress (e.g., cached autoplay), resolve immediately
if (!videoEl.paused && videoEl.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
  resolve(getHighPrecisionTimestamp());
  return;
}
```

**What Happens:**
1. ✅ Checks if video is already playing
2. ✅ Resolves immediately with current timestamp
3. ✅ No event listeners added (cleanup not needed)
4. ✅ Timing recorded accurately

**Timing Data Impact:**
- Timing is accurate (uses current timestamp)
- No delays introduced

**Verdict:** ✅ Perfect implementation.

**Recommendation:** None - works as designed.

---

### 5. Rapid Video Switching (Promise Pile-Up)

**Status:** 🔴 **CRITICAL MEMORY LEAK**
**Risk Level:** CRITICAL
**Code Location:** `SequentialVideoPlayer.tsx` lines 559, 642-651

#### Analysis:
```typescript
// Line 559 - Promise created but never explicitly cancelled
const playbackStartedAt = await waitForPlaybackStart(videoRef.current);

// Lines 642-651 - loadAndPlayVideo called again
}, [
  sequenceStartTime,
  sequenceId,
  sendVideoStartedEvent,
  preloadNextVideo,
  retryCount,
  onError,
  onVideoStarted,
  waitForPlaybackStart
]);
```

**What Happens if user clicks "Next Video" rapidly:**
1. ❌ First `waitForPlaybackStart` promise still pending
2. ❌ Second `loadAndPlayVideo` call creates NEW promise
3. ❌ First promise's event listeners NEVER cleaned up (line 117-120)
4. ❌ `videoRef.current` now points to NEW video element
5. ❌ Old listeners attached to WRONG video element
6. ❌ Memory leak - listeners accumulate indefinitely
7. ❌ Race condition - first promise may resolve AFTER second

**Timing Data Impact:**
- Multiple incomplete timing records
- Possible duplicate entries in `videoTimingsRef.current`
- Statistics corrupted

**Proof of Bug:**
```typescript
// Current code has NO cancellation token
const waitForPlaybackStart = useCallback(
  (videoEl: HTMLVideoElement, timeoutMs = 5000): Promise<number> => {
    return new Promise((resolve, reject) => {
      // ❌ No way to cancel this promise from outside
      // ❌ cleanup() only called when promise settles, not when cancelled
```

**Verdict:** 🔴 **CRITICAL MEMORY LEAK - MUST FIX**

**Recommended Fix:**
```typescript
// Add cancellation token
interface CancellablePromise<T> extends Promise<T> {
  cancel: () => void;
}

const activePromisesRef = useRef<Set<CancellablePromise<any>>>(new Set());

const waitForPlaybackStart = useCallback(
  (videoEl: HTMLVideoElement, timeoutMs = 5000): CancellablePromise<number> => {
    let cancelled = false;

    const promise = new Promise((resolve, reject) => {
      const cleanup = () => {
        if (!cancelled) {
          // ... existing cleanup code
        }
      };
      // ... rest of implementation
    }) as CancellablePromise<number>;

    promise.cancel = () => {
      cancelled = true;
      cleanup();
      activePromisesRef.current.delete(promise);
    };

    activePromisesRef.current.add(promise);
    return promise;
  }
);

// In loadAndPlayVideo:
const loadAndPlayVideo = useCallback(async (video: VideoFile, index: number) => {
  // Cancel all pending promises
  activePromisesRef.current.forEach(p => p.cancel());
  activePromisesRef.current.clear();

  // ... rest of implementation
});
```

---

### 6. Browser Tab Backgrounded (Video Stalls)

**Status:** ⚠️ **PARTIAL HANDLING**
**Risk Level:** MEDIUM
**Code Location:** `SequentialVideoPlayer.tsx` lines 118-120, 137-140

#### Analysis:
```typescript
// Stalled event listener added (line 118-119)
videoEl.addEventListener('stalled', handlePlaybackError);
videoEl.addEventListener('suspend', handlePlaybackError);

// Timeout set to 5 seconds (line 137-140)
const timeoutId = window.setTimeout(() => {
  cleanup();
  reject(new Error('Timed out waiting for video to begin playback'));
}, timeoutMs);
```

**What Happens When Tab Backgrounded:**
1. ✅ Browser may fire `suspend` event - handled (line 119)
2. ⚠️ If `suspend` fires AFTER playback started, ignored
3. ❌ Timeout uses `setTimeout` which throttles in background (1Hz)
4. ❌ Actual timeout may be 5+ seconds instead of exact 5 seconds
5. ⚠️ Video pauses but timing continues counting

**Timing Data Impact:**
- `sequenceElapsedTime` includes background time
- `videoElapsedTime` may drift from video.currentTime
- Timing statistics inaccurate

**Verdict:** ⚠️ Needs improvement for accuracy.

**Recommended Fix:**
```typescript
// Add Page Visibility API monitoring
useEffect(() => {
  const handleVisibilityChange = () => {
    if (document.hidden && isPlaying) {
      // Pause timing when backgrounded
      pauseTimestamp.current = getHighPrecisionTimestamp();
    } else if (!document.hidden && pauseTimestamp.current) {
      // Resume timing - adjust for gap
      const gap = getHighPrecisionTimestamp() - pauseTimestamp.current;
      timingOffsetRef.current += gap;
      pauseTimestamp.current = null;
    }
  };

  document.addEventListener('visibilitychange', handleVisibilityChange);
  return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
}, [isPlaying]);
```

---

### 7. Network Interruption Mid-Video

**Status:** ❌ **NO HANDLING**
**Risk Level:** HIGH
**Code Location:** `SequentialVideoPlayer.tsx` lines 143-145

#### Analysis:
```typescript
// Only listening for these events BEFORE playback starts
videoEl.addEventListener('stalled', handlePlaybackError);
videoEl.addEventListener('suspend', handlePlaybackError);
videoEl.addEventListener('error', handlePlaybackError);
```

**What Happens:**
1. ❌ Event listeners removed after `playing` event fires (line 117)
2. ❌ If network drops DURING playback, no listeners active
3. ❌ Video element fires `stalled` or `waiting` events - IGNORED
4. ❌ User sees frozen video with no error message
5. ❌ Timing continues counting as if video still playing
6. ❌ Test may hang indefinitely

**Timing Data Impact:**
- Timing data completely wrong
- Video duration includes stall time
- Detection events mapped to wrong timestamps

**Verdict:** ❌ **HIGH PRIORITY FIX REQUIRED**

**Recommended Fix:**
```typescript
// Add persistent monitoring during playback
useEffect(() => {
  const video = videoRef.current;
  if (!video || !isPlaying) return;

  const handleStalled = () => {
    console.warn('Video playback stalled - network issue?');
    setError('Video buffering - checking network connection...');
  };

  const handleWaiting = () => {
    console.warn('Video waiting for data');
  };

  const handleError = () => {
    console.error('Video error during playback:', video.error);
    setError(`Playback error: ${video.error?.message}`);

    // Try to recover
    const currentTime = video.currentTime;
    video.load();
    video.currentTime = currentTime;
    video.play();
  };

  video.addEventListener('stalled', handleStalled);
  video.addEventListener('waiting', handleWaiting);
  video.addEventListener('error', handleError);

  return () => {
    video.removeEventListener('stalled', handleStalled);
    video.removeEventListener('waiting', handleWaiting);
    video.removeEventListener('error', handleError);
  };
}, [isPlaying]);
```

---

### 8. sequenceStartUnix is null

**Status:** ⚠️ **PARTIAL HANDLING**
**Risk Level:** MEDIUM
**Code Location:** `SequentialVideoPlayer.tsx` lines 184-192

#### Analysis:
```typescript
// Line 184 - Fallback to current timestamp
const sequenceStartSeconds = sequenceStartUnix ?? startedAtUnix;
const sequenceElapsedSeconds = startedAtUnix - sequenceStartSeconds;

// Line 190-192 - Initialize if null
if (sequenceStartUnix === null) {
  setSequenceStartUnix(sequenceStartSeconds);
}
```

**What Happens:**
1. ✅ First video initializes `sequenceStartUnix` (line 191)
2. ⚠️ If component re-renders before state updates, race condition possible
3. ⚠️ Multiple videos might initialize with different values
4. ✅ Fallback ensures no crash

**Timing Data Impact:**
- Slight drift possible if race condition occurs
- Usually harmless due to fast state updates

**Verdict:** ⚠️ Low risk but could be more robust.

**Recommended Fix:**
```typescript
// Use useRef for synchronous initialization
const sequenceStartUnixRef = useRef<number | null>(null);

const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
  const startedAtUnix = timestamp / 1000;

  // Initialize sequence start ONCE (synchronous)
  if (sequenceStartUnixRef.current === null) {
    sequenceStartUnixRef.current = startedAtUnix;
    setSequenceStartUnix(startedAtUnix); // Also update state for UI
  }

  const sequenceElapsedSeconds = startedAtUnix - sequenceStartUnixRef.current;
  // ...
});
```

---

### 9. Clock Skew Between Client and Server

**Status:** ⚠️ **KNOWN LIMITATION**
**Risk Level:** MEDIUM
**Code Location:** `videoTimingUtils.ts` lines 65-67

#### Analysis:
```typescript
// Using Date.now() for Unix epoch timestamps
export function getHighPrecisionTimestamp(): number {
  return Date.now();
}
```

**What Happens:**
1. ✅ Client uses `Date.now()` - system clock
2. ✅ Server receives Unix timestamp
3. ❌ If client clock is wrong (e.g., +5 minutes), all timing wrong
4. ❌ Ground truth matching fails (events appear before video starts)
5. ❌ Latency calculations completely wrong

**Example:**
```
Client clock: 2025-11-11 14:05:00 (5 minutes fast)
Server clock: 2025-11-11 14:00:00 (correct)

Video starts (client): 1731340500000 ms
Detection arrives (server): 1731340200500 ms
Calculated latency: -299500 ms (NEGATIVE!)
```

**Timing Data Impact:**
- Completely incorrect timing if clock skew > 1 second
- Production environments with NTP should be fine
- Development/testing environments may have issues

**Verdict:** ⚠️ Acceptable for production with monitoring.

**Recommended Mitigation:**
```typescript
// Add clock skew detection
const detectClockSkew = async (): Promise<number> => {
  const clientTime = Date.now();
  const response = await fetch('/api/time');
  const serverTime = await response.json();
  const roundTripTime = Date.now() - clientTime;

  // Estimate server time when request sent
  const estimatedServerTime = serverTime.timestamp + (roundTripTime / 2);
  const skew = clientTime - estimatedServerTime;

  if (Math.abs(skew) > 1000) {
    console.warn(`Clock skew detected: ${skew}ms`);
  }

  return skew;
};

// Use in timing calculations
const adjustedTimestamp = getHighPrecisionTimestamp() - clockSkewRef.current;
```

---

### 10. Video Duration Unknown (Streaming/Live)

**Status:** ✅ **HANDLED**
**Risk Level:** LOW
**Code Location:** `SequentialVideoPlayer.tsx` lines 683-684

#### Analysis:
```typescript
// Line 683-684 - Fallback calculation
const actualPlaybackSeconds = videoRef.current?.currentTime ?? null;
const derivedDuration = videoStartUnix !== null ? Math.max(endedAtUnix - videoStartUnix, 0) : null;
const actualDuration = actualPlaybackSeconds ?? derivedDuration;
```

**What Happens:**
1. ✅ Uses `video.currentTime` as primary source
2. ✅ Falls back to calculated duration
3. ✅ `Math.max(..., 0)` prevents negative durations
4. ✅ Handles streaming video correctly

**Timing Data Impact:**
- Accurate for known-duration videos
- Accurate for streaming (uses elapsed time)

**Verdict:** ✅ Well implemented.

**Recommendation:** None needed.

---

## Additional Critical Scenarios

### 11. Video Element Removed from DOM

**Status:** 🔴 **CRITICAL**
**Risk Level:** CRITICAL
**Code Location:** Multiple locations using `videoRef.current`

#### Analysis:
- If parent component unmounts, `videoRef.current` becomes null
- Pending promises crash when trying to access null
- Event listeners reference stale element

**Recommended Fix:**
- Add null checks before every `videoRef.current` access
- Clean up promises in `useEffect` cleanup function

---

### 12. Multiple Videos with Same ID

**Status:** ⚠️ **DATA CORRUPTION**
**Risk Level:** HIGH
**Code Location:** `videoTimingUtils.ts` line 191-271

#### Analysis:
```typescript
export function mapDetectionToVideo(
  detectionTimestamp: number,
  sequenceStartTime: number,
  videoTimings: VideoTimingMetadata[]
): DetectionTimingResult | null {
  // Searches by timestamp, not video ID
  // If two videos have same ID, wrong mapping possible
}
```

**Recommended Fix:**
- Add unique sequence index to metadata
- Use `(videoId, videoIndex)` tuple for mapping

---

### 13. Incomplete Timing Metadata in Array

**Status:** ⚠️ **STATISTICS CORRUPTION**
**Risk Level:** MEDIUM
**Code Location:** `videoTimingUtils.ts` lines 349-400

#### Analysis:
```typescript
export function calculateSequenceTimingStats(
  videoTimings: VideoTimingMetadata[]
): SequenceTimingStats {
  const completedVideos = videoTimings.filter(v => v.duration !== null);
  // Only counts completed videos - GOOD

  const totalLoadingDelay = videoTimings.reduce((sum, v) => sum + v.actualStartDelay, 0);
  // ❌ Includes incomplete videos in delay calculation
}
```

**Recommended Fix:**
- Filter incomplete videos from ALL calculations

---

### 14. Video Codec Not Supported

**Status:** ❌ **NO DETECTION**
**Risk Level:** HIGH
**Code Location:** `SequentialVideoPlayer.tsx` line 522

#### Analysis:
- Browser silently fails to play unsupported codec
- Generic error message shown
- No specific guidance to user

**Recommended Fix:**
```typescript
// Check codec support before loading
const canPlayType = videoRef.current.canPlayType(video.mimeType);
if (!canPlayType || canPlayType === 'no') {
  throw new Error(`Unsupported video codec: ${video.mimeType}`);
}
```

---

### 15. Zero-Duration Videos

**Status:** ⚠️ **EDGE CASE**
**Risk Level:** LOW
**Code Location:** `videoTimingUtils.ts` line 304-310

#### Analysis:
- Empty videos (0 duration) cause division by zero
- Expected start time calculations break
- Statistics show `NaN` or `Infinity`

**Recommended Fix:**
- Filter videos with `duration <= 0`
- Show warning to user

---

### 16. Very Large Video Playlists (100+ Videos)

**Status:** ⚠️ **PERFORMANCE DEGRADATION**
**Risk Level:** MEDIUM
**Code Location:** `SequentialVideoPlayer.tsx` line 669

#### Analysis:
- Array grows unbounded
- Each detection searches entire array
- O(n²) performance for long sequences

**Recommended Fix:**
- Use Map for O(1) lookups
- Implement pagination for statistics

---

### 17. Concurrent Test Sessions

**Status:** ❌ **DATA MIXING**
**Risk Level:** HIGH
**Code Location:** `HILTestExecutionComplete.tsx` WebSocket handling

#### Analysis:
- No session ID validation in WebSocket events
- Multiple tabs could mix detection events
- Race conditions on backend

**Recommended Fix:**
- Add session ID to all WebSocket messages
- Filter events by session ID on client

---

### 18. Browser Memory Pressure

**Status:** ⚠️ **PERFORMANCE**
**Risk Level:** LOW
**Code Location:** Entire component

#### Analysis:
- Video buffers consume memory
- Long-running tests accumulate data
- No cleanup of old timing data

**Recommended Fix:**
- Implement windowing for very long sequences
- Clear old video buffers
- Offload statistics to backend

---

## Summary Tables

### Critical Issues (Must Fix Before Deployment)

| # | Scenario | Impact | Severity | Recommended Action |
|---|----------|--------|----------|-------------------|
| 3 | Autoplay blocked | Test completely blocked | CRITICAL | Add user interaction fallback |
| 5 | Rapid video switching | Memory leak + corruption | CRITICAL | Implement promise cancellation |
| 11 | Video element removed | Crash | CRITICAL | Add comprehensive null checks |

### High Priority Issues (Should Fix)

| # | Scenario | Impact | Severity | Recommended Action |
|---|----------|--------|----------|-------------------|
| 2 | Video load failure | Wrong timing stats | HIGH | Finalize timing on failure |
| 7 | Network interruption | Hang + wrong timing | HIGH | Add persistent error monitoring |
| 17 | Concurrent sessions | Data mixing | HIGH | Add session ID validation |

### Medium Priority Issues (Monitor)

| # | Scenario | Impact | Severity | Recommended Action |
|---|----------|--------|----------|-------------------|
| 6 | Tab backgrounded | Timing drift | MEDIUM | Add visibility API handling |
| 8 | Null sequenceStart | Race condition | MEDIUM | Use ref for sync init |
| 9 | Clock skew | Wrong latency | MEDIUM | Add skew detection |

### Low Priority Issues (Working)

| # | Scenario | Impact | Severity | Notes |
|---|----------|--------|----------|-------|
| 1 | User skips video | None - handled | LOW | Works correctly |
| 4 | Video already playing | None - handled | LOW | Optimized for caching |
| 10 | Unknown duration | None - handled | LOW | Good fallback logic |

---

## Test Coverage Recommendations

### Unit Tests Needed

```typescript
describe('waitForPlaybackStart', () => {
  it('should handle rapid cancellation', async () => {
    const video = createMockVideo();
    const promise1 = waitForPlaybackStart(video);
    promise1.cancel();

    const promise2 = waitForPlaybackStart(video);
    await promise2;

    expect(eventListenerCount(video)).toBe(expectedCount);
  });

  it('should handle autoplay block', async () => {
    const video = createMockVideo({ autoplayBlocked: true });
    await expect(waitForPlaybackStart(video)).rejects.toThrow('autoplay');
  });

  it('should handle network interruption', async () => {
    const video = createMockVideo();
    setTimeout(() => video.dispatchEvent('stalled'), 1000);

    await expect(waitForPlaybackStart(video)).rejects.toThrow('stalled');
  });
});
```

### Integration Tests Needed

```typescript
describe('SequentialVideoPlayer - Edge Cases', () => {
  it('should survive rapid video switching', async () => {
    render(<SequentialVideoPlayer {...props} />);

    for (let i = 0; i < 10; i++) {
      fireEvent.click(screen.getByText('Next'));
      await waitFor(() => screen.getByText(`Video ${i + 2}`));
    }

    expect(screen.queryByText('Error')).not.toBeInTheDocument();
  });

  it('should handle video load failure gracefully', async () => {
    server.use(
      rest.get('/uploads/video.mp4', (req, res, ctx) => {
        return res(ctx.status(404));
      })
    );

    render(<SequentialVideoPlayer {...props} />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });
});
```

### E2E Tests Needed

```typescript
describe('HIL Test Execution - Edge Cases', () => {
  it('should handle autoplay block with user prompt', async () => {
    await page.goto('/hil-test-execution');
    await page.click('[data-testid="start-test"]');

    // Simulate autoplay block
    await page.evaluate(() => {
      HTMLVideoElement.prototype.play = () =>
        Promise.reject(new DOMException('Autoplay blocked'));
    });

    await page.waitForSelector('[data-testid="play-prompt"]');
    await page.click('[data-testid="user-play-button"]');

    await page.waitForSelector('[data-testid="video-playing"]');
  });
});
```

---

## Production Monitoring Recommendations

### Metrics to Track

1. **Video Load Failures**
   - Count per video
   - Failure reasons (404, CORS, codec, etc.)

2. **Autoplay Blocks**
   - Browser type
   - Frequency
   - User recovery rate

3. **Network Interruptions**
   - Stall events per session
   - Recovery time
   - Impact on timing accuracy

4. **Memory Usage**
   - Heap size over time
   - Promise leak detection
   - Event listener count

5. **Clock Skew**
   - Client-server time delta
   - Impact on latency calculations

### Alerts to Configure

```typescript
// Add to monitoring service
if (videoLoadFailureRate > 0.05) {
  alert('High video load failure rate: ' + videoLoadFailureRate);
}

if (autoplayBlockRate > 0.20) {
  alert('Many users experiencing autoplay blocks');
}

if (averageClockSkew > 5000) {
  alert('Significant clock skew detected: ' + averageClockSkew + 'ms');
}
```

---

## Deployment Checklist

### Must Fix Before Deploy

- [ ] Fix autoplay blocking (Scenario 3)
- [ ] Implement promise cancellation (Scenario 5)
- [ ] Add null checks for video element (Scenario 11)

### Should Fix Before Deploy

- [ ] Handle video load failures correctly (Scenario 2)
- [ ] Add network interruption recovery (Scenario 7)
- [ ] Validate session IDs in WebSocket events (Scenario 17)

### Nice to Have

- [ ] Add visibility API handling (Scenario 6)
- [ ] Implement clock skew detection (Scenario 9)
- [ ] Add comprehensive unit tests

### Testing Requirements

- [ ] Test on Safari (strict autoplay policies)
- [ ] Test on mobile browsers (aggressive backgrounding)
- [ ] Test with slow 3G network (network interruptions)
- [ ] Test with 50+ video playlist (memory/performance)
- [ ] Test with concurrent sessions (data isolation)

---

## Conclusion

The video player instrumentation has **good foundation** but requires **6 critical fixes** before production deployment. The most severe issues are:

1. **Autoplay blocking** - Will break test execution completely
2. **Promise memory leaks** - Will cause browser crashes on long tests
3. **Network interruption handling** - Will produce incorrect timing data

After implementing the recommended fixes, the system should be robust enough for production use with appropriate monitoring.

**Estimated Fix Time:** 8-12 hours for critical issues
**Estimated Testing Time:** 16-20 hours for comprehensive validation

