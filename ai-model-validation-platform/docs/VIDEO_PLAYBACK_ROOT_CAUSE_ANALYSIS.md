# HIL Video Playback - Root Cause Analysis & Comprehensive Fix

## Executive Summary

**Status**: Video player component failing to mount/execute during HIL test execution
**Impact**: NO video playback = NO LabJack detections = 100% False Negatives
**Root Causes Identified**: 5 critical issues preventing video playback

---

## Critical Issues Found

### 1. ⚠️ **SequentialVideoPlayer Component Not Executing**

**Evidence**:
- Test starts successfully ✅
- Fullscreen entered ✅
- Ground truth loaded (200 detections) ✅
- **NO logs from SequentialVideoPlayer component** ❌
- Component should auto-play via `useEffect` on mount
- Zero video playback initialization logs

**Root Cause**:
Component is mounting but **crashing silently** before `useEffect` executes.

**Possible Causes**:
1. Missing/undefined video URLs in `validatedVideos` array
2. `sequenceId` prop evaluation error
3. Backend API route missing (`/api/video-sequences/`)
4. Video file URLs returning 404

---

### 2. 🚫 **WebSocket Connection Rejected (403 Forbidden)**

**Error**:
```
WebSocket connection to 'ws://localhost:8000/ws/test-sessions/{session_id}/detections' failed:
Error during WebSocket handshake: Unexpected response code: 403
```

**Impact**:
- LabJack detection events cannot reach frontend
- Fallback to polling may miss real-time detections
- Detection data lost even if LabJack is working

**Root Cause**:
Backend WebSocket endpoint rejecting connections due to:
- Missing authentication
- CORS configuration
- WebSocket route not properly registered

---

### 3. ❌ **Missing Backend API Routes (404 Errors)**

**Missing Endpoints**:
```
GET /api/t3/{session_id}/alerts → 404
GET /api/t3/{session_id}/pipeline?limit=100 → 404
POST /api/video-sequences/{sequence_id}/video-started → Unknown
POST /api/video-sequences/{sequence_id}/video-ended → Unknown
```

**Impact**:
- T3 service polling fails continuously
- Video sequence tracking broken
- SequentialVideoPlayer API calls fail silently
- Component may crash on failed API calls

---

### 4. 🔌 **Socket.io Connection Failed (400 Bad Request)**

**Error**:
```
:8000/socket.io/:1 Failed to load resource: server responded with status 400 (Bad Request)
```

**Root Cause**:
- Socket.io server not initialized/configured
- Frontend attempting Socket.io connection but backend doesn't support it
- May be legacy code expecting Socket.io

---

### 5. 🎬 **Video URL Construction Issues**

**Analysis of Video URL System**:

**VideoFile Interface**:
```typescript
interface VideoFile {
  url?: string;          // May be undefined
  filePath?: string;     // Alternative path source
  filename: string;      // Base filename
  file_path?: string;    // Backend snake_case variant
}
```

**URL Construction Flow**:
1. Backend returns `file_path` (e.g., `/uploads/video.mp4`)
2. Frontend `fixVideoUrl()` constructs: `http://localhost:8000/uploads/video.mp4`
3. SequentialVideoPlayer uses `video.url || ''` for playback
4. **If URL is empty/undefined → video won't load**

**Potential Issues**:
- `file_path` not being converted to full URL
- URL construction happens async but component tries to play immediately
- Video files may not exist at constructed URLs
- CORS issues preventing video file access

---

## Video Playback Flow Analysis

### Expected Flow:
```
1. User clicks "Start Test"
2. HILTestExecutionPRD.startTest() executes
3. testRunning set to true
4. SequentialVideoPlayer mounts
5. useEffect triggers: loadAndPlayVideo(videoPlaylist[0], 0)
6. Video URL loaded into <video> element
7. video.play() called
8. Playback starts → LabJack monitoring begins
```

### Actual Flow (Broken):
```
1. User clicks "Start Test" ✅
2. HILTestExecutionPRD.startTest() executes ✅
3. testRunning set to true ✅
4. SequentialVideoPlayer mounts ✅
5. useEffect triggers → ??? ❌ NO LOGS
6. Component crashes/fails silently
7. NO video playback
8. NO LabJack signals detected
9. NO detection events created
10. Ground truth matching: 0 detections vs 122 annotations = 100% FN
```

---

## Overlay & Z-Index Analysis

**Fullscreen Overlays**:
- **Stop Button**: `position: absolute`, `zIndex: 1000`, top-right
- **Progress Indicator**: `position: absolute`, `zIndex: 1000`, bottom

**Video Player Layout**:
```jsx
<Box> <!-- Container: display: flex, alignItems: center -->
  <SequentialVideoPlayer /> <!-- Should render video element -->
  {isFullScreen && <Overlay 1 />}
  {isFullScreen && <Overlay 2 />}
</Box>
```

**Verdict**: Overlays are **NOT blocking** the video:
- Overlays render AFTER SequentialVideoPlayer
- Positioned absolute with high z-index
- Video should be in normal flow
- **Issue is component not rendering/executing, not overlay blocking**

---

## Comprehensive Root Cause Summary

### Primary Issue: **SequentialVideoPlayer Initialization Failure**

**Chain of Failures**:
```
1. Component mounts with props
2. Tries to call backend API: /api/video-sequences/{id}/video-started → 404
3. API call fails, throws error
4. Error not caught, component crashes
5. useEffect never executes
6. Video never plays
```

**OR**:
```
1. Component mounts with props
2. videoPlaylist has videos but URLs are undefined/malformed
3. loadAndPlayVideo() tries to set video.src = undefined
4. Video element fails to load
5. Error not logged
6. Playback silently fails
```

---

## Required Fixes

### Fix 1: Add Error Boundaries & Logging
```typescript
// Wrap SequentialVideoPlayer in error boundary
<ErrorBoundary fallback={<VideoPlayerError />}>
  <SequentialVideoPlayer ... />
</ErrorBoundary>
```

### Fix 2: Implement Missing Backend Routes
```python
# Add to main.py or create video_sequences router
@app.post("/api/video-sequences/{sequence_id}/video-started")
async def video_started(sequence_id: str, data: dict):
    logger.info(f"Video started: {sequence_id}, {data}")
    return {"status": "acknowledged"}

@app.post("/api/video-sequences/{sequence_id}/video-ended")
async def video_ended(sequence_id: str, data: dict):
    logger.info(f"Video ended: {sequence_id}, {data}")
    return {"status": "acknowledged", "nextVideoId": None}
```

### Fix 3: Fix WebSocket Authentication
```python
# In WebSocket endpoint
@app.websocket("/ws/test-sessions/{session_id}/detections")
async def detection_websocket(websocket: WebSocket, session_id: str):
    # Remove or fix authentication check
    await websocket.accept()  # Accept all connections for now
    # ... rest of code
```

### Fix 4: Remove/Stub T3 API Calls
```typescript
// In HILTestExecutionPRD.tsx - wrap T3 calls in try-catch
try {
  const alerts = await getT3Alerts(sessionId);
} catch (e) {
  console.warn('T3 service not available, continuing without it');
  // Don't fail the test
}
```

### Fix 5: Validate Video URLs Before Playback
```typescript
// In SequentialVideoPlayer - add URL validation
const loadAndPlayVideo = async (video: VideoFile, index: number) => {
  console.log('🎬 Loading video:', video);

  if (!video.url) {
    const error = `Video URL is missing for: ${video.filename}`;
    console.error('❌', error);
    onError(error);
    return;
  }

  console.log('🎬 Video URL:', video.url);

  // Test URL accessibility
  try {
    const response = await fetch(video.url, { method: 'HEAD' });
    if (!response.ok) {
      throw new Error(`Video not accessible: ${response.status}`);
    }
  } catch (fetchError) {
    console.error('❌ Video URL not accessible:', video.url, fetchError);
    onError(`Video file not found: ${video.filename}`);
    return;
  }

  // Continue with playback...
};
```

### Fix 6: Add Comprehensive Logging
```typescript
// At component mount
console.log('🎬 SequentialVideoPlayer MOUNTED', {
  videoPlaylist,
  sequenceId,
  videoCount: videoPlaylist.length,
  firstVideoUrl: videoPlaylist[0]?.url
});

// In useEffect
useEffect(() => {
  console.log('🎬 SequentialVideoPlayer useEffect triggered');
  console.log('🎬 Video playlist:', videoPlaylist);
  console.log('🎬 Current video:', currentVideo);

  if (videoPlaylist.length > 0 && !currentVideo) {
    console.log('🎬 Starting first video...');
    loadAndPlayVideo(videoPlaylist[0], 0);
  }
}, []);
```

---

## Testing Checklist

After applying fixes, verify:

- [ ] SequentialVideoPlayer mount logs appear
- [ ] Video URL is valid and accessible
- [ ] Video element receives valid src attribute
- [ ] video.play() is called
- [ ] WebSocket connects (or falls back gracefully)
- [ ] LabJack monitoring starts
- [ ] Detection events are created
- [ ] Ground truth matching works
- [ ] Test results are generated

---

## Priority Order

1. **HIGH**: Add logging to SequentialVideoPlayer (identify exact failure point)
2. **HIGH**: Validate video URLs before playback
3. **HIGH**: Implement missing backend video-sequences routes
4. **MEDIUM**: Fix WebSocket 403 error
5. **LOW**: Stub/remove T3 API calls
6. **LOW**: Remove Socket.io connection attempts

---

## Conclusion

Video playback is failing due to a **cascade of errors** starting with the SequentialVideoPlayer component:

1. Component mounts
2. Tries to call missing backend APIs
3. Fails silently without proper error handling
4. useEffect never completes
5. Video never plays
6. No LabJack detection events
7. Test fails with 100% False Negatives

**The fix requires both frontend error handling AND backend route implementation.**
