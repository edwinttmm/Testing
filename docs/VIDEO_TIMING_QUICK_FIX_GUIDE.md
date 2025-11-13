# Video Timing Quick Fix Guide
**3 Critical Frontend Fixes Required Before Deployment**

## Fix #1: Memory Leak in Event Listener Cleanup (5 min)

**File:** `frontend/src/components/SequentialVideoPlayer.tsx`  
**Lines:** 115-121

**Replace this:**
```typescript
videoEl.addEventListener('stalled', handlePlaybackError);
videoEl.addEventListener('suspend', handlePlaybackError);
videoEl.addEventListener('error', handlePlaybackError);
```

**With this:**
```typescript
const abortController = new AbortController();
const signal = abortController.signal;

videoEl.addEventListener('playing', handlePlaying, { signal });
videoEl.addEventListener('stalled', handlePlaybackError, { signal });
videoEl.addEventListener('suspend', handlePlaybackError, { signal });
videoEl.addEventListener('error', handlePlaybackError, { signal });

const cleanup = () => {
  abortController.abort(); // Removes ALL listeners at once
  window.clearTimeout(timeoutId);
};
```

---

## Fix #2: Race Condition Protection (10 min)

**File:** `frontend/src/components/SequentialVideoPlayer.tsx`  
**Lines:** 98-150

**Add at top of component (after existing refs):**
```typescript
const activeWaitPromiseRef = useRef<Promise<number> | null>(null);
```

**Update `waitForPlaybackStart` function:**
```typescript
const waitForPlaybackStart = useCallback(
  (videoEl: HTMLVideoElement, timeoutMs = 5000): Promise<number> => {
    // Return existing promise if already waiting
    if (activeWaitPromiseRef.current) {
      console.log('[waitForPlaybackStart] Reusing existing promise');
      return activeWaitPromiseRef.current;
    }

    const promise = new Promise<number>((resolve, reject) => {
      // ... existing code ...
      
      const cleanup = () => {
        activeWaitPromiseRef.current = null; // Clear on completion
        window.clearTimeout(timeoutId);
        videoEl.removeEventListener('playing', handlePlaying);
        videoEl.removeEventListener('stalled', handlePlaybackError);
        videoEl.removeEventListener('suspend', handlePlaybackError);
        videoEl.removeEventListener('error', handlePlaybackError);
      };

      // ... rest of existing code
    });

    activeWaitPromiseRef.current = promise;
    return promise;
  },
  []
);
```

---

## Fix #3: Autoplay Blocking Detection (5 min)

**File:** `frontend/src/components/SequentialVideoPlayer.tsx`  
**Lines:** 549-557

**Replace error handling:**
```typescript
if (!playResult.success) {
  const errorMsg = playResult.error?.message || 'Unknown error';
  
  // Check for autoplay blocking
  if (errorMsg.includes('NotAllowedError') || 
      errorMsg.includes('play() request was interrupted')) {
    throw new Error(
      'Browser blocked video autoplay. Please click the video to start playback.'
    );
  }
  
  throw new Error(`Failed to play video: ${errorMsg}`);
}
```

---

## Deployment Steps

1. **Apply all 3 fixes** to `SequentialVideoPlayer.tsx`
2. **Test locally**:
   ```bash
   cd frontend
   npm start
   # Open browser devtools → Console
   # Watch for any memory warnings or errors
   ```
3. **Test rapid video switching**:
   - Create 10-video sequence
   - Rapidly click Next/Previous buttons
   - Watch console for promise resolution issues
4. **Test autoplay blocking**:
   - Open browser in incognito mode
   - Reload page
   - Verify error message appears

## Verification

Run this command to verify fixes are applied:
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend/src/components
grep -n "AbortController\|activeWaitPromiseRef\|NotAllowedError" SequentialVideoPlayer.tsx
```

Expected output:
```
102:const activeWaitPromiseRef = useRef<Promise<number> | null>(null);
118:const abortController = new AbortController();
556:if (errorMsg.includes('NotAllowedError') ||
```

---

**Estimated Fix Time:** 20 minutes  
**Priority:** CRITICAL - Must fix before deployment  
**Impact:** Prevents memory leaks and crashes in production
