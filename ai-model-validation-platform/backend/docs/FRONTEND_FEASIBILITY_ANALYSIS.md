# Frontend Feasibility Analysis: Multi-Video Timing Synchronization

**Analysis Date:** 2025-11-20
**Platform:** AI Model Validation Platform
**Scope:** Frontend feasibility for multi-video sequential playback with high-precision timing synchronization

---

## Executive Summary

**VERDICT: ✅ FEASIBLE WITH MODIFICATIONS**

The current React Native-style frontend components can achieve multi-video sequential timing synchronization with millisecond-level precision. However, **microsecond/sub-millisecond precision is not achievable in browser environments** due to JavaScript timer resolution and browser throttling limitations.

**Key Findings:**
- ✅ HTML5 Video Events are reliable for lifecycle tracking
- ✅ `performance.now()` provides millisecond precision (±1ms accuracy)
- ⚠️ Browser clocks have ~1ms minimum resolution (not nanoseconds)
- ❌ Autoplay restrictions require user interaction or muted playback
- ⚠️ Background tab throttling degrades timing accuracy significantly
- ✅ WebSocket-based orchestration is suitable for event coordination
- ⚠️ Network latency (20-100ms typical) must be compensated

**Recommended Approach:**
1. **Server-side timestamp authority:** Backend assigns canonical timestamps
2. **Event-driven architecture:** Frontend emits lifecycle events, backend correlates
3. **Network latency compensation:** Client reports round-trip time with each event
4. **Millisecond precision target:** Achievable with proper clock sync
5. **Grace period buffers:** 100-200ms tolerance for video transitions

---

## 1. Browser API Review

### 1.1 HTML5 Video Events

**Available Events for Lifecycle Tracking:**

| Event | Trigger Condition | Reliability | Use Case |
|-------|------------------|-------------|----------|
| `loadedmetadata` | Video metadata loaded (duration, dimensions) | ⭐⭐⭐⭐⭐ High | Get video duration before buffering |
| `loadeddata` | First frame loaded and ready | ⭐⭐⭐⭐ Good | "Video ready" but may still buffer |
| `canplaythrough` | Buffered enough to play without stalling | ⭐⭐⭐ Moderate | **Best "truly ready" indicator** |
| `canplay` | Can start playing (but may stall) | ⭐⭐ Low | Too early - not fully buffered |
| `playing` | Playback has begun after pause/load | ⭐⭐⭐⭐⭐ High | **Emit `video_started` here** |
| `ended` | Video playback completed | ⭐⭐⭐⭐⭐ High | **Emit `video_ended` here** |
| `timeupdate` | Playback position changed (~250ms intervals) | ⭐⭐⭐⭐ Good | Progress tracking |
| `waiting` | Playback paused due to buffering | ⭐⭐⭐⭐ Good | Detect buffering stalls |
| `stalled` | Browser trying to fetch data but not receiving | ⭐⭐⭐ Moderate | Network issues |

**Recommended Event Flow:**
```javascript
// 1. Wait for video to be ready (buffered)
video.addEventListener('canplaythrough', () => {
  emitWebSocket('video_ready', { video_index, buffered: true });
});

// 2. Record precise start time when playback begins
video.addEventListener('playing', () => {
  const timestamp = performance.now() + performance.timeOrigin;
  emitWebSocket('video_started', {
    video_index,
    timestamp_ms: timestamp,
    rtt_ms: lastMeasuredRTT
  });
});

// 3. Record precise end time when video completes
video.addEventListener('ended', () => {
  const timestamp = performance.now() + performance.timeOrigin;
  emitWebSocket('video_ended', {
    video_index,
    timestamp_ms: timestamp,
    rtt_ms: lastMeasuredRTT
  });
});

// 4. Detect buffering during playback
video.addEventListener('waiting', () => {
  emitWebSocket('video_buffering', { video_index });
});
```

**Cross-Browser Compatibility:**

| Event | Chrome | Firefox | Safari | Edge |
|-------|--------|---------|--------|------|
| `loadedmetadata` | ✅ | ✅ | ✅ | ✅ |
| `canplaythrough` | ✅ | ✅ | ✅ ⚠️ (sometimes unreliable) |
| `playing` | ✅ | ✅ | ✅ | ✅ |
| `ended` | ✅ | ✅ | ✅ | ✅ |
| `waiting` | ✅ | ✅ | ✅ | ✅ |

**Safari Caveat:** Safari's `canplaythrough` may fire prematurely. Recommend dual-check:
```javascript
const isReallyReady = video.readyState >= 3; // HAVE_FUTURE_DATA
if (isReallyReady) {
  emitReady();
}
```

---

### 1.2 Timestamp Precision

**Available Timing APIs:**

| API | Resolution | Precision | Use Case |
|-----|-----------|-----------|----------|
| `Date.now()` | 1ms | ±1ms | ❌ System clock, subject to drift |
| `performance.now()` | 0.001ms (1μs) | ±1ms actual | ✅ **Monotonic, best for duration** |
| `performance.timeOrigin` | 1ms | ±1ms | ✅ Convert `performance.now()` to epoch |
| `video.currentTime` | Float (seconds) | ±frame duration | ⚠️ Video timeline, not wall clock |

**Recommended Approach: `performance.now()` + `performance.timeOrigin`**

```javascript
// Monotonic timestamp (milliseconds since page load)
const monotonicTime = performance.now(); // e.g., 12345.678

// Convert to Unix epoch milliseconds
const epochTimestamp = performance.now() + performance.timeOrigin;

// Send to backend with RTT for latency compensation
emitWebSocket('video_started', {
  video_index: 0,
  timestamp_ms: epochTimestamp,
  monotonic_ms: monotonicTime,
  rtt_ms: lastRTT,
  client_time: new Date().toISOString()
});
```

**Precision Analysis:**

| Metric | JavaScript Capability | HIL Requirement | Gap |
|--------|----------------------|----------------|-----|
| **Timer Resolution** | ~1ms (browser-dependent) | ~0.001ms (1μs) | ❌ 1000x gap |
| **Timestamp Precision** | ±1-5ms typical | ±0.1ms (sub-millisecond) | ⚠️ 10-50x gap |
| **Monotonic Clock** | ✅ `performance.now()` | ✅ Required | ✅ Available |
| **Epoch Timestamp** | ✅ `performance.timeOrigin` | ✅ Required | ✅ Available |

**Verdict:**
- ✅ Millisecond precision (1-5ms accuracy) is **achievable**
- ❌ Sub-millisecond precision (<1ms) is **not achievable in browser**
- **Recommendation:** Backend should be authoritative for sub-millisecond timing

---

### 1.3 Autoplay Restrictions

**Browser Autoplay Policies (2024):**

| Browser | Autoplay Allowed? | Workaround |
|---------|------------------|------------|
| **Chrome** | ❌ Only muted videos | ✅ `video.muted = true` |
| **Firefox** | ❌ Only muted videos | ✅ `video.muted = true` |
| **Safari** | ❌ Requires user interaction | ⚠️ Play button or muted with permission |
| **Edge** | ❌ Only muted videos | ✅ `video.muted = true` |

**Current Implementation Issue:**

The existing `AutomatedVideoPlayer.tsx` correctly uses `muted` attribute:
```javascript
<video
  ref={videoRef}
  src={videoUrl}
  muted // ✅ Required for auto-play in many browsers
  playsInline
/>
```

**Recommended Autoplay Strategy:**

```javascript
// Strategy 1: Muted autoplay (works in all modern browsers)
const startVideo = async () => {
  try {
    videoRef.current.muted = true; // Force muted
    await videoRef.current.play();
    setIsPlaying(true);
  } catch (error) {
    // Fallback: Show play button for user interaction
    setRequiresUserAction(true);
  }
};

// Strategy 2: Request permission first (for Safari/strict environments)
const requestAutoplayPermission = async () => {
  try {
    // Attempt silent play with user interaction
    await videoRef.current.play();
    videoRef.current.pause();
    setAutoplayAllowed(true);
  } catch {
    setAutoplayAllowed(false);
  }
};
```

**Verdict:**
- ✅ Autoplay is **feasible** with muted videos in automated test scenarios
- ⚠️ User interaction required in Safari unless video is muted
- **Recommendation:** Always use `muted` + `playsInline` for automated testing

---

## 2. Buffering & Load States

### 2.1 "Truly Ready" Detection

**Problem:** How to know when video is **truly ready** to play without buffering?

**Video Ready States (readyState property):**

| readyState | Constant | Meaning | Ready to Play? |
|-----------|----------|---------|----------------|
| 0 | `HAVE_NOTHING` | No data loaded | ❌ No |
| 1 | `HAVE_METADATA` | Metadata loaded (duration, dimensions) | ❌ No |
| 2 | `HAVE_CURRENT_DATA` | Current frame loaded | ⚠️ Maybe (will stall) |
| 3 | `HAVE_FUTURE_DATA` | Current + next frames loaded | ⚠️ Probably (may stall) |
| 4 | `HAVE_ENOUGH_DATA` | Enough data to play through | ✅ **Yes (safe to play)** |

**Recommended Ready Check:**

```javascript
const checkVideoReady = () => {
  const video = videoRef.current;

  // Method 1: Check readyState (most reliable)
  if (video.readyState >= 3) { // HAVE_FUTURE_DATA or better
    return true;
  }

  // Method 2: Check buffered ranges
  if (video.buffered.length > 0) {
    const bufferedEnd = video.buffered.end(0);
    const hasEnoughBuffered = bufferedEnd >= 3; // 3 seconds buffered
    return hasEnoughBuffered;
  }

  return false;
};

// Use with canplaythrough event
video.addEventListener('canplaythrough', () => {
  if (checkVideoReady()) {
    emitWebSocket('video_ready', { video_index, buffered: true });
    // Wait for orchestrator confirmation before calling play()
  }
});
```

**Handle Slow Networks / Large Videos:**

```javascript
const loadWithTimeout = (videoUrl, timeoutMs = 30000) => {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error(`Video load timeout after ${timeoutMs}ms`));
    }, timeoutMs);

    video.addEventListener('canplaythrough', () => {
      clearTimeout(timeout);
      resolve();
    }, { once: true });

    video.addEventListener('error', () => {
      clearTimeout(timeout);
      reject(new Error(`Video load failed: ${video.error.message}`));
    }, { once: true });

    video.src = videoUrl;
    video.load();
  });
};
```

**Verdict:**
- ✅ "Truly ready" detection is **achievable** via `readyState >= 3` + `canplaythrough`
- ✅ Buffered range checking provides additional confidence
- **Recommendation:** Use `canplaythrough` event + readyState verification

---

### 2.2 Prevent Playback Before Confirmation

**Requirement:** Wait for orchestrator confirmation before starting playback.

**Current Architecture Gap:**
The existing `AutomatedVideoPlayer.tsx` starts playback immediately after load:

```javascript
// CURRENT (INCORRECT for synchronized sequences):
useEffect(() => {
  if (videoUrl && isAutomated && videoRef.current) {
    const playVideo = async () => {
      video.load();
      await video.play(); // ❌ Starts immediately
    };
    setTimeout(playVideo, 100);
  }
}, [videoUrl, isAutomated]);
```

**Recommended Architecture: State Machine**

```javascript
enum VideoState {
  IDLE = 'idle',
  LOADING = 'loading',
  READY = 'ready',
  WAITING_CONFIRMATION = 'waiting_confirmation',
  PLAYING = 'playing',
  ENDED = 'ended',
  ERROR = 'error'
}

const [videoState, setVideoState] = useState(VideoState.IDLE);

// Step 1: Load video
useEffect(() => {
  if (videoUrl) {
    setVideoState(VideoState.LOADING);
    videoRef.current.src = videoUrl;
    videoRef.current.load();
  }
}, [videoUrl]);

// Step 2: Video ready, emit and wait
const handleCanPlayThrough = () => {
  if (videoState === VideoState.LOADING) {
    setVideoState(VideoState.READY);
    emitWebSocket('video_ready', { video_index, buffered: true });
    setVideoState(VideoState.WAITING_CONFIRMATION);
  }
};

// Step 3: Receive confirmation from orchestrator
useEffect(() => {
  const handleOrchestratorMessage = (message) => {
    if (message.type === 'play_video' && message.video_index === currentVideoIndex) {
      if (videoState === VideoState.WAITING_CONFIRMATION) {
        videoRef.current.play().then(() => {
          setVideoState(VideoState.PLAYING);
        });
      }
    }
  };

  websocket.on('message', handleOrchestratorMessage);
  return () => websocket.off('message', handleOrchestratorMessage);
}, [videoState, currentVideoIndex]);
```

**Verdict:**
- ✅ Playback gating is **fully achievable** via state machine + WebSocket coordination
- **Recommendation:** Implement explicit state machine with orchestrator handshake

---

### 2.3 Buffering During Playback

**Problem:** Video may start buffering mid-playback. Should we pause monitoring?

**Detection Strategy:**

```javascript
const [isBuffering, setIsBuffering] = useState(false);

// Detect buffering start
video.addEventListener('waiting', () => {
  setIsBuffering(true);
  emitWebSocket('video_buffering_start', {
    video_index,
    timestamp_ms: performance.now() + performance.timeOrigin
  });
});

// Detect buffering end
video.addEventListener('playing', () => {
  if (isBuffering) {
    setIsBuffering(false);
    emitWebSocket('video_buffering_end', {
      video_index,
      timestamp_ms: performance.now() + performance.timeOrigin
    });
  }
});

// Monitor stalled state (no progress)
video.addEventListener('stalled', () => {
  emitWebSocket('video_stalled', {
    video_index,
    error: 'Network stalled - no data received'
  });
});
```

**Backend Handling Recommendation:**

```python
# Backend should mark buffering periods in detection timeline
def handle_buffering_period(
    video_index: int,
    buffering_start_ms: float,
    buffering_end_ms: float
):
    """Mark buffering period to exclude from latency calculations"""

    # Invalidate detections during buffering
    for detection in session_detections:
        if (buffering_start_ms <= detection.timestamp_ms <= buffering_end_ms):
            detection.validity_status = "buffering_period"
            detection.include_in_metrics = False
```

**Verdict:**
- ✅ Buffering detection is **reliable** via `waiting` + `playing` events
- ✅ Backend can compensate by marking buffering periods as invalid
- **Recommendation:** Emit buffering events, backend invalidates affected detections

---

## 3. Playlist Implementation

### 3.1 Current VideoPlayer Component Architecture

**Existing Components:**

1. **`AutomatedVideoPlayer.tsx`** (Single video player)
   - ✅ Basic playback controls
   - ✅ Auto-play support
   - ✅ Error handling
   - ❌ No orchestrator integration
   - ❌ No WebSocket event emission

2. **`SequentialVideoManager.tsx`** (Playlist manager)
   - ✅ Multi-video state management
   - ✅ Progress tracking
   - ✅ Auto-advance logic
   - ⚠️ Uses internal callbacks (not WebSocket)
   - ❌ No orchestrator coordination

**Architecture Gap:**

```
Current Flow:
  VideoManager → VideoPlayer → onVideoEnd callback → advance

Required Flow:
  VideoManager → VideoPlayer → emit 'video_ended' →
    Orchestrator → emit 'play_video' → VideoManager
```

---

### 3.2 Strict Sequential Playback

**Requirement:** Never skip ahead, strict order enforcement.

**Recommended Implementation:**

```javascript
const SequentialVideoPlayer = ({ videos, sessionId }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [videoStates, setVideoStates] = useState(
    videos.map(() => VideoState.IDLE)
  );

  // Strict state enforcement
  const canPlayVideo = (index) => {
    // Video must be ready
    if (videoStates[index] !== VideoState.WAITING_CONFIRMATION) {
      return false;
    }

    // Previous video must be completed (except first video)
    if (index > 0 && videoStates[index - 1] !== VideoState.ENDED) {
      return false;
    }

    // No gaps allowed - all previous videos must be completed
    for (let i = 0; i < index; i++) {
      if (videoStates[i] !== VideoState.ENDED) {
        return false;
      }
    }

    return true;
  };

  // Handle orchestrator play command
  useEffect(() => {
    const handlePlayCommand = (message) => {
      if (message.type === 'play_video' && message.video_index === currentIndex) {
        if (canPlayVideo(currentIndex)) {
          // Play video
          videoRefs[currentIndex].current.play();
          updateVideoState(currentIndex, VideoState.PLAYING);
        } else {
          // Reject invalid play command
          emitWebSocket('play_rejected', {
            video_index: currentIndex,
            reason: 'Preconditions not met',
            state: videoStates[currentIndex]
          });
        }
      }
    };

    websocket.on('message', handlePlayCommand);
    return () => websocket.off('message', handlePlayCommand);
  }, [currentIndex, videoStates]);

  // Auto-advance to next video on completion
  const handleVideoEnded = (index) => {
    updateVideoState(index, VideoState.ENDED);
    emitWebSocket('video_ended', {
      video_index: index,
      timestamp_ms: performance.now() + performance.timeOrigin
    });

    // Move to next video
    if (index < videos.length - 1) {
      setCurrentIndex(index + 1);
      // Start loading next video
      updateVideoState(index + 1, VideoState.LOADING);
    } else {
      // Sequence complete
      emitWebSocket('sequence_completed', { session_id: sessionId });
    }
  };
};
```

**Verdict:**
- ✅ Strict sequential playback is **fully achievable** with state machine
- ✅ Gap prevention logic is straightforward
- **Recommendation:** Use explicit precondition checks before each video starts

---

### 3.3 Video Load Failure Handling

**Error Recovery Strategy:**

```javascript
const handleVideoLoadError = (videoIndex, error) => {
  updateVideoState(videoIndex, VideoState.ERROR);

  emitWebSocket('video_load_failed', {
    video_index: videoIndex,
    error_message: error.message,
    error_code: videoRef.current.error?.code
  });

  // Retry logic (3 attempts)
  if (retryCount < 3) {
    setRetryCount(retryCount + 1);
    setTimeout(() => {
      videoRef.current.load();
    }, 2000 * retryCount); // Exponential backoff
  } else {
    // Skip video after 3 failed attempts
    emitWebSocket('video_skipped', {
      video_index: videoIndex,
      reason: 'Load failed after 3 retries'
    });

    // Move to next video
    handleVideoEnded(videoIndex);
  }
};

// Error codes
// 1 = MEDIA_ERR_ABORTED - User aborted
// 2 = MEDIA_ERR_NETWORK - Network error
// 3 = MEDIA_ERR_DECODE - Decode error
// 4 = MEDIA_ERR_SRC_NOT_SUPPORTED - Format not supported
```

**Verdict:**
- ✅ Error handling is **robust** with retry + skip logic
- ✅ HTML5 video error codes provide diagnostic information
- **Recommendation:** Implement exponential backoff retry with skip-after-3-attempts policy

---

### 3.4 UI/UX for Multi-Video Progress

**Recommended UI Elements:**

```javascript
const VideoSequenceUI = ({ videos, currentIndex, videoStates }) => {
  return (
    <Box>
      {/* Overall sequence progress */}
      <LinearProgress
        variant="determinate"
        value={(currentIndex / videos.length) * 100}
      />

      {/* Per-video status cards */}
      <List>
        {videos.map((video, index) => (
          <ListItem key={video.id}>
            <StatusIcon state={videoStates[index]} />
            <ListItemText
              primary={`Video ${index + 1}: ${video.filename}`}
              secondary={getStateDescription(videoStates[index])}
            />
            {index === currentIndex && <Chip label="Current" color="primary" />}
          </ListItem>
        ))}
      </List>

      {/* Current video player */}
      {currentIndex < videos.length && (
        <AutomatedVideoPlayer
          videoUrl={videos[currentIndex].url}
          videoIndex={currentIndex}
          isAutomated={true}
          onVideoEnd={() => handleVideoEnded(currentIndex)}
        />
      )}
    </Box>
  );
};
```

**Verdict:**
- ✅ Existing `SequentialVideoManager.tsx` has good UI foundation
- ⚠️ Needs orchestrator integration (WebSocket events)
- **Recommendation:** Extend current UI with state machine + WebSocket layer

---

## 4. Clock Synchronization

### 4.1 Browser Clock Drift

**Problem:** Browser clock (`Date.now()`) can drift from server clock.

**Drift Sources:**
1. **System clock drift** (1-100ms/day typical)
2. **Time zone changes** (DST, manual adjustment)
3. **VM/container clock skew** (can be seconds)

**Measurement Strategy:**

```javascript
// Client-side clock sync check
const measureClockDrift = async () => {
  const clientTime = Date.now();
  const clientMonotonic = performance.now();

  const response = await fetch('/api/clock-sync', {
    method: 'POST',
    body: JSON.stringify({ client_time: clientTime })
  });

  const { server_time, server_monotonic } = await response.json();

  // Calculate round-trip time
  const rtt = performance.now() - clientMonotonic;

  // Calculate drift (assuming symmetric latency)
  const estimatedServerTime = server_time + (rtt / 2);
  const drift = clientTime - estimatedServerTime;

  return { drift_ms: drift, rtt_ms: rtt };
};

// Run on page load
useEffect(() => {
  measureClockDrift().then(({ drift_ms, rtt_ms }) => {
    if (Math.abs(drift_ms) > 1000) { // 1 second drift
      console.warn(`⚠️ Clock drift detected: ${drift_ms}ms`);
      // Notify user or adjust timestamps
    }
    setClockDrift(drift_ms);
    setNetworkRTT(rtt_ms);
  });
}, []);
```

**Backend Drift Validation:**

From existing `clock_sync_service.py`:
```python
def validate_clock_sync(
    frontend_timestamp: float,
    backend_timestamp: Optional[float] = None,
    max_frontend_drift_seconds: float = 5.0
):
    backend_timestamp = backend_timestamp or time.time()
    frontend_drift = abs(frontend_timestamp - backend_timestamp)

    if frontend_drift > max_frontend_drift_seconds:
        raise ClockSkewError(
            f"Frontend clock drift {frontend_drift:.3f}s exceeds threshold"
        )
```

**Verdict:**
- ⚠️ Browser clock drift is **real** (1-100ms typical, can be seconds)
- ✅ Drift detection is **achievable** via client-server handshake
- **Recommendation:** Backend validates timestamps, rejects if drift > 5 seconds

---

### 4.2 Network Latency Compensation

**Problem:** WebSocket events have network latency (20-100ms typical).

**NTP-Style Compensation:**

```javascript
// Measure network RTT
const measureRTT = async () => {
  const sentTime = performance.now();

  return new Promise((resolve) => {
    const requestId = uuid.v4();

    websocket.emit('ping', { request_id: requestId, sent_time: sentTime });

    const handlePong = (message) => {
      if (message.request_id === requestId) {
        const receivedTime = performance.now();
        const rtt = receivedTime - sentTime;
        resolve(rtt);
        websocket.off('pong', handlePong);
      }
    };

    websocket.on('pong', handlePong);
  });
};

// Send timestamps with RTT context
const emitWithLatencyContext = (eventType, payload) => {
  const timestamp = performance.now() + performance.timeOrigin;

  websocket.emit(eventType, {
    ...payload,
    timestamp_ms: timestamp,
    rtt_ms: lastMeasuredRTT,
    client_monotonic_ms: performance.now()
  });
};

// Backend compensates for network latency
// Server-side (Python):
def adjust_for_network_latency(
    client_timestamp_ms: float,
    rtt_ms: float,
    received_at_ms: float
):
    # Assume symmetric latency
    one_way_latency = rtt_ms / 2

    # Estimate when event actually occurred
    event_time_ms = received_at_ms - one_way_latency

    # Use server timestamp as authoritative
    return event_time_ms
```

**Verdict:**
- ✅ Network latency compensation is **feasible** via RTT measurement
- ✅ Backend can use server timestamps as authoritative source
- **Recommendation:** Client reports RTT with each event, backend adjusts timestamps

---

### 4.3 Server Timestamps as Authority

**Recommended Architecture:**

```python
# Backend assigns authoritative timestamps
class VideoEventHandler:
    def handle_video_started(self, session_id, video_index, client_timestamp_ms, rtt_ms):
        # Record server timestamp as authoritative
        server_timestamp_ms = time.time() * 1000

        # Calculate clock drift
        clock_drift_ms = client_timestamp_ms - server_timestamp_ms

        # Validate drift is acceptable
        if abs(clock_drift_ms) > 5000:  # 5 seconds
            raise ClockSkewError(f"Clock drift {clock_drift_ms}ms exceeds threshold")

        # Store both timestamps for analysis
        video_timing_service.start_video_timing(
            session_id=session_id,
            video_id=video_id,
            server_timestamp_ms=server_timestamp_ms,  # AUTHORITATIVE
            client_timestamp_ms=client_timestamp_ms,  # Reference
            clock_drift_ms=clock_drift_ms,
            rtt_ms=rtt_ms
        )

        return server_timestamp_ms  # Return to client for confirmation
```

**Client Confirmation:**

```javascript
// Client receives authoritative timestamp from server
const handleVideoStartConfirmation = (message) => {
  const { video_index, server_timestamp_ms, clock_drift_ms } = message;

  console.log(`✅ Video ${video_index} started at ${server_timestamp_ms} (server time)`);
  console.log(`   Clock drift: ${clock_drift_ms}ms`);

  // Store for local reference but trust server timestamp
  setAuthoritative Timestamp(server_timestamp_ms);
};
```

**Verdict:**
- ✅ Server-authoritative timestamps are **strongly recommended**
- ✅ Eliminates client clock drift issues
- **Recommendation:** Backend assigns canonical timestamps, client uses for display only

---

## 5. Edge Cases

### 5.1 User Manually Seeks/Pauses Video

**Problem:** User interaction breaks automated timing.

**Detection + Prevention:**

```javascript
// Disable user controls in automated mode
<video
  ref={videoRef}
  src={videoUrl}
  controls={!isAutomated} // ❌ No controls in automated mode
  disablePictureInPicture
  controlsList="nodownload nofullscreen noremoteplayback"
/>

// Detect manual seek attempts
video.addEventListener('seeking', (event) => {
  if (isAutomated) {
    // Prevent seek
    event.preventDefault();
    video.currentTime = lastKnownTime;

    emitWebSocket('user_seek_attempted', {
      video_index,
      attempted_seek_to: video.currentTime
    });
  }
});

// Detect manual pause attempts
video.addEventListener('pause', (event) => {
  if (isAutomated && videoState === VideoState.PLAYING) {
    // Prevent pause
    video.play();

    emitWebSocket('user_pause_attempted', { video_index });
  }
});
```

**Verdict:**
- ✅ User interactions can be **prevented** by disabling controls
- ✅ Event detection allows logging of attempted interference
- **Recommendation:** Disable all user controls during automated testing

---

### 5.2 Browser Tab Backgrounded

**Problem:** Browser throttles background tabs (timers run at 1Hz instead of 60Hz).

**Impact:**
- `setTimeout` / `setInterval` throttled to 1000ms minimum
- `requestAnimationFrame` paused entirely
- Video playback continues but events may be delayed

**Detection:**

```javascript
// Detect page visibility changes
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    emitWebSocket('tab_backgrounded', {
      video_index: currentIndex,
      timestamp_ms: performance.now() + performance.timeOrigin
    });

    // Optionally pause test
    if (strictTiming) {
      videoRef.current.pause();
      showWarning('Tab backgrounded - test paused');
    }
  } else {
    emitWebSocket('tab_foregrounded', {
      video_index: currentIndex,
      timestamp_ms: performance.now() + performance.timeOrigin
    });

    if (strictTiming) {
      videoRef.current.play();
    }
  }
});

// Monitor playback drift
const checkTimingDrift = () => {
  const expectedTime = (performance.now() - videoStartMonotonic) / 1000;
  const actualTime = videoRef.current.currentTime;
  const drift = Math.abs(expectedTime - actualTime);

  if (drift > 0.5) { // 500ms drift threshold
    emitWebSocket('timing_drift_detected', {
      video_index: currentIndex,
      drift_seconds: drift
    });
  }
};

setInterval(checkTimingDrift, 1000);
```

**Mitigation:**

1. **Warn User:** Display prominent warning if tab is backgrounded
2. **Pause Test:** Auto-pause playback when backgrounded
3. **Invalidate Results:** Mark test as invalid if backgrounding detected
4. **Use WebLocks API:** Prevent backgrounding (Chromium only)

```javascript
// Chromium-only: Request wake lock to prevent throttling
let wakeLock = null;

const requestWakeLock = async () => {
  try {
    wakeLock = await navigator.wakeLock.request('screen');
    console.log('✅ Wake lock acquired - tab will not be throttled');
  } catch (err) {
    console.warn('⚠️ Wake lock not supported');
  }
};
```

**Verdict:**
- ⚠️ Background tab throttling is **severe** (1000x slowdown for timers)
- ✅ Detection is **reliable** via `visibilitychange` event
- ✅ Mitigation via pause/warning is **recommended**
- **Recommendation:** Require tab to remain foreground, invalidate if backgrounded

---

### 5.3 Network Disconnection During Test

**Problem:** WebSocket connection lost mid-test.

**Detection + Recovery:**

```javascript
const [wsConnected, setWsConnected] = useState(false);
const [offlineQueue, setOfflineQueue] = useState([]);

// Detect disconnection
websocket.on('disconnect', () => {
  setWsConnected(false);
  console.warn('⚠️ WebSocket disconnected - queueing events');

  // Pause video playback
  videoRef.current.pause();
  updateVideoState(currentIndex, VideoState.PAUSED);

  showNotification('Connection lost - test paused');
});

// Queue events while offline
const emitOrQueue = (eventType, payload) => {
  if (wsConnected) {
    websocket.emit(eventType, payload);
  } else {
    setOfflineQueue([...offlineQueue, { eventType, payload, queued_at: Date.now() }]);
  }
};

// Reconnect + flush queue
websocket.on('connect', () => {
  setWsConnected(true);
  console.log('✅ WebSocket reconnected - flushing queue');

  // Flush queued events
  offlineQueue.forEach(({ eventType, payload }) => {
    websocket.emit(eventType, payload);
  });
  setOfflineQueue([]);

  // Resume playback
  videoRef.current.play();
  updateVideoState(currentIndex, VideoState.PLAYING);

  showNotification('Connection restored - test resumed');
});
```

**Backend Tolerance:**

```python
# Backend should have grace period for reconnection
class VideoEventHandler:
    def handle_disconnection(self, session_id):
        # Mark session as "disconnected" but don't fail immediately
        session.connection_status = "disconnected"
        session.disconnected_at = time.time()

    def handle_reconnection(self, session_id):
        # Calculate downtime
        downtime_seconds = time.time() - session.disconnected_at

        if downtime_seconds < 30:  # 30 second grace period
            # Resume session
            session.connection_status = "connected"
            logger.info(f"Session {session_id} reconnected after {downtime_seconds}s")
        else:
            # Fail session
            session.status = "failed"
            session.failure_reason = "Disconnected for too long"
```

**Verdict:**
- ✅ Disconnection detection is **reliable** via WebSocket events
- ✅ Event queueing prevents data loss during brief disconnections
- ✅ Grace period (30s) allows recovery from temporary network issues
- **Recommendation:** Queue events, pause playback, resume on reconnect within 30s

---

### 5.4 Browser Refresh/Crash Recovery

**Problem:** Browser refresh or crash loses all state.

**Recovery Strategy:**

```javascript
// Persist state to sessionStorage
const persistState = () => {
  sessionStorage.setItem('test_state', JSON.stringify({
    session_id: sessionId,
    current_index: currentIndex,
    video_states: videoStates,
    started_at: startedAt,
    paused_at: isPaused ? Date.now() : null
  }));
};

// Restore state on page load
useEffect(() => {
  const savedState = sessionStorage.getItem('test_state');
  if (savedState) {
    const state = JSON.parse(savedState);

    // Notify backend of recovery
    emitWebSocket('session_recovered', {
      session_id: state.session_id,
      recovered_at: Date.now(),
      last_video_index: state.current_index
    });

    // Ask user if they want to resume
    showDialog({
      title: 'Recover Test Session?',
      message: `Resume from Video ${state.current_index + 1}?`,
      onConfirm: () => {
        setCurrentIndex(state.current_index);
        setVideoStates(state.video_states);
      },
      onCancel: () => {
        sessionStorage.removeItem('test_state');
        startNewSession();
      }
    });
  }
}, []);

// Persist on every state change
useEffect(() => {
  persistState();
}, [currentIndex, videoStates]);
```

**Backend Handling:**

```python
# Backend should support session resumption
class VideoEventHandler:
    def handle_session_recovered(self, session_id, last_video_index):
        session = get_session(session_id)

        # Check if session can be resumed
        if session.status in ["running", "paused"]:
            # Allow resumption
            session.status = "running"
            session.recovered_at = datetime.now()
            session.recovery_count += 1

            logger.info(f"Session {session_id} recovered at video {last_video_index}")
            return {"can_resume": True, "resume_from_index": last_video_index}
        else:
            # Session already completed/failed
            logger.warning(f"Cannot resume session {session_id} - status is {session.status}")
            return {"can_resume": False, "reason": f"Session {session.status}"}
```

**Verdict:**
- ✅ State recovery is **achievable** via sessionStorage
- ✅ Backend can support session resumption
- ⚠️ Limited to current browser session (sessionStorage cleared on tab close)
- **Recommendation:** Persist minimal state, prompt user to resume or restart

---

## 6. Network Latency Mitigation

**Typical Latency Values:**

| Connection Type | Round-Trip Time (RTT) | One-Way Latency |
|----------------|----------------------|----------------|
| Localhost | 1-2ms | 0.5-1ms |
| Same data center | 1-5ms | 0.5-2.5ms |
| Same city | 5-20ms | 2.5-10ms |
| Same country | 20-50ms | 10-25ms |
| Cross-continent | 100-300ms | 50-150ms |

**Mitigation Strategies:**

### 6.1 RTT Measurement

```javascript
// Periodic RTT measurement
const measureRTTPeriodically = () => {
  setInterval(async () => {
    const rtt = await measureRTT();
    setNetworkRTT(rtt);

    if (rtt > 100) { // High latency threshold
      console.warn(`⚠️ High network latency: ${rtt}ms`);
      showNotification(`Network latency high: ${rtt}ms`);
    }
  }, 5000); // Measure every 5 seconds
};
```

### 6.2 Backend Timestamp Authority

```python
# Backend adjusts for network latency
def calculate_authoritative_timestamp(
    client_timestamp_ms: float,
    rtt_ms: float,
    server_received_at_ms: float
):
    # Assume symmetric latency
    one_way_latency_ms = rtt_ms / 2

    # Estimate when event occurred on client
    estimated_event_time_ms = server_received_at_ms - one_way_latency_ms

    # Use server timestamp as authoritative (more accurate)
    authoritative_timestamp_ms = server_received_at_ms

    # Calculate client-server drift
    client_server_drift_ms = client_timestamp_ms - server_received_at_ms

    return {
        "authoritative_timestamp_ms": authoritative_timestamp_ms,
        "estimated_event_time_ms": estimated_event_time_ms,
        "client_timestamp_ms": client_timestamp_ms,
        "clock_drift_ms": client_server_drift_ms,
        "network_latency_ms": one_way_latency_ms
    }
```

### 6.3 Grace Period Buffers

```python
# Video transition grace period
VIDEO_TRANSITION_GRACE_MS = 200  # 200ms buffer

def assign_detection_to_video(detection_timestamp_ms, video_timings):
    """Assign detection to correct video with grace period"""

    for video in video_timings:
        video_start_ms = video.start_time * 1000
        video_end_ms = (video.start_time + video.duration) * 1000

        # Apply grace period
        window_start_ms = video_start_ms - VIDEO_TRANSITION_GRACE_MS
        window_end_ms = video_end_ms + VIDEO_TRANSITION_GRACE_MS

        if window_start_ms <= detection_timestamp_ms <= window_end_ms:
            return video.video_id

    return None  # Detection outside any video window
```

**Verdict:**
- ✅ Network latency is **predictable** and **measurable**
- ✅ Backend can compensate via timestamp adjustment
- ✅ Grace periods (100-200ms) handle transition timing uncertainty
- **Recommendation:** Server-authoritative timestamps + 200ms grace period

---

## 7. Recommended Architecture

### 7.1 Component Hierarchy

```
VideoSequenceOrchestrator (New Component)
  ├── WebSocket Connection Manager
  │   ├── Clock Sync Service
  │   ├── RTT Measurement
  │   └── Event Queue (offline resilience)
  │
  ├── Sequence State Machine
  │   ├── VideoState[] (per-video state tracking)
  │   ├── canPlayVideo() precondition checks
  │   └── Strict ordering enforcement
  │
  ├── Video Player Manager
  │   ├── AutomatedVideoPlayer (current component)
  │   ├── Video Lifecycle Event Handlers
  │   └── Buffering Detection
  │
  └── UI Components
      ├── SequenceProgressBar
      ├── VideoStatusList
      └── NetworkStatusIndicator
```

### 7.2 Event Flow Diagram

```
┌─────────────────┐
│  Frontend       │
│  (Browser)      │
└────────┬────────┘
         │
         │ 1. Load video
         ├──────────────────────────────────────────┐
         │                                          │
         │ 2. canplaythrough event                 │
         ├──────────────────────────────────────────┤
         │                                          │
         │ 3. emit 'video_ready' (video_index, rtt)│
         │                                          │
         ├──────────────────────────────────────────▼
         │                                  ┌───────────────┐
         │                                  │   Backend     │
         │                                  │  Orchestrator │
         │                                  └───────┬───────┘
         │                                          │
         │                                          │ 4. Validate timing
         │                                          │    Check preconditions
         │                                          │
         │ 5. emit 'play_video' (video_index)      │
         │◄─────────────────────────────────────────┤
         │                                          │
         │ 6. video.play()                         │
         ├──────────────────────────────────────────┤
         │                                          │
         │ 7. playing event                        │
         ├──────────────────────────────────────────┤
         │                                          │
         │ 8. emit 'video_started' (timestamp, rtt)│
         ├──────────────────────────────────────────▶
         │                                          │
         │                                          │ 9. Record server timestamp
         │                                          │    Start detection monitoring
         │                                          │
         │ 10. emit 'video_started_confirmed' (...)│
         │◄─────────────────────────────────────────┤
         │                                          │
         │                                          │
         │ (Video plays...)                        │
         │                                          │ (Detections occur...)
         │                                          │
         │ 11. ended event                         │
         ├──────────────────────────────────────────┤
         │                                          │
         │ 12. emit 'video_ended' (timestamp, rtt) │
         ├──────────────────────────────────────────▶
         │                                          │
         │                                          │ 13. Record end timestamp
         │                                          │     Evaluate video results
         │                                          │     Prepare next video
         │                                          │
         │ 14. emit 'play_video' (next_index)      │
         │◄─────────────────────────────────────────┤
         │                                          │
         │ 15. Load next video...                  │
         │                                          │
         └─────────────────────────────────────────┘
```

### 7.3 State Machine

```
Video State Machine:

IDLE
  │
  └─[load video]─→ LOADING
                     │
                     └─[canplaythrough]─→ READY
                                          │
                                          └─[emit video_ready]─→ WAITING_CONFIRMATION
                                                                  │
                                                                  └─[receive play_video]─→ STARTING
                                                                                          │
                                                                                          └─[playing event]─→ PLAYING
                                                                                                              │
                                                                                                              ├─[waiting event]─→ BUFFERING
                                                                                                              │                   │
                                                                                                              │                   └─[playing event]─→ PLAYING
                                                                                                              │
                                                                                                              └─[ended event]─→ ENDED
                                                                                                                                │
                                                                                                                                └─[next video]─→ IDLE

Error transitions:
  ANY_STATE ─[error event]─→ ERROR
  ERROR ─[retry]─→ LOADING
  ERROR ─[skip]─→ ENDED
```

---

## 8. Browser Compatibility Matrix

| Feature | Chrome 120+ | Firefox 121+ | Safari 17+ | Edge 120+ | Notes |
|---------|------------|--------------|-----------|-----------|-------|
| **HTML5 Video Events** |
| `canplaythrough` | ✅ | ✅ | ⚠️ | ✅ | Safari sometimes fires prematurely |
| `playing` | ✅ | ✅ | ✅ | ✅ | Fully reliable |
| `ended` | ✅ | ✅ | ✅ | ✅ | Fully reliable |
| `waiting` | ✅ | ✅ | ✅ | ✅ | Buffering detection |
| **Timestamp APIs** |
| `performance.now()` | ✅ | ✅ | ✅ | ✅ | 1μs resolution, ±1ms accuracy |
| `performance.timeOrigin` | ✅ | ✅ | ✅ | ✅ | Epoch conversion |
| **Autoplay** |
| Muted autoplay | ✅ | ✅ | ✅ | ✅ | Works reliably |
| Unmuted autoplay | ❌ | ❌ | ❌ | ❌ | Requires user interaction |
| **WebSocket** |
| WebSocket API | ✅ | ✅ | ✅ | ✅ | Fully supported |
| **Visibility API** |
| `visibilitychange` | ✅ | ✅ | ✅ | ✅ | Tab backgrounding detection |
| **Wake Lock API** |
| `navigator.wakeLock` | ✅ | ❌ | ❌ | ✅ | Chromium-only |

**Testing Recommendations:**

1. **Primary Target:** Chrome 120+ (most common for testing)
2. **Secondary Target:** Firefox 121+ (good alternative)
3. **Limited Support:** Safari 17+ (has quirks, requires extra validation)
4. **Avoid:** Internet Explorer (no longer supported)

---

## 9. Code Examples

### 9.1 Enhanced VideoPlayer Component

```typescript
import React, { useRef, useState, useEffect, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';

enum VideoState {
  IDLE = 'idle',
  LOADING = 'loading',
  READY = 'ready',
  WAITING_CONFIRMATION = 'waiting_confirmation',
  STARTING = 'starting',
  PLAYING = 'playing',
  BUFFERING = 'buffering',
  ENDED = 'ended',
  ERROR = 'error'
}

interface VideoPlayerProps {
  videoUrl: string;
  videoIndex: number;
  sessionId: string;
  websocket: Socket;
  onStateChange?: (state: VideoState) => void;
}

export const EnhancedVideoPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl,
  videoIndex,
  sessionId,
  websocket,
  onStateChange
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoState, setVideoState] = useState<VideoState>(VideoState.IDLE);
  const [networkRTT, setNetworkRTT] = useState<number>(0);
  const [retryCount, setRetryCount] = useState<number>(0);

  // Update state and notify parent
  const updateState = useCallback((newState: VideoState) => {
    setVideoState(newState);
    onStateChange?.(newState);
  }, [onStateChange]);

  // Emit event with timing context
  const emitEvent = useCallback((eventType: string, payload: any) => {
    const timestamp = performance.now() + performance.timeOrigin;
    websocket.emit(eventType, {
      ...payload,
      session_id: sessionId,
      video_index: videoIndex,
      timestamp_ms: timestamp,
      monotonic_ms: performance.now(),
      rtt_ms: networkRTT,
      client_time: new Date().toISOString()
    });
  }, [websocket, sessionId, videoIndex, networkRTT]);

  // Measure network RTT
  const measureRTT = useCallback(async (): Promise<number> => {
    return new Promise((resolve) => {
      const requestId = Math.random().toString(36);
      const sentTime = performance.now();

      websocket.emit('ping', { request_id: requestId, sent_time: sentTime });

      const handlePong = (message: any) => {
        if (message.request_id === requestId) {
          const receivedTime = performance.now();
          const rtt = receivedTime - sentTime;
          resolve(rtt);
          websocket.off('pong', handlePong);
        }
      };

      websocket.on('pong', handlePong);

      // Timeout after 5 seconds
      setTimeout(() => resolve(100), 5000); // Default to 100ms if no response
    });
  }, [websocket]);

  // Load video
  useEffect(() => {
    if (videoUrl && videoRef.current) {
      updateState(VideoState.LOADING);
      videoRef.current.src = videoUrl;
      videoRef.current.load();
    }
  }, [videoUrl, updateState]);

  // Video event handlers
  const handleLoadedMetadata = useCallback(() => {
    console.log(`✅ Video ${videoIndex}: Metadata loaded`);
  }, [videoIndex]);

  const handleCanPlayThrough = useCallback(async () => {
    if (videoState === VideoState.LOADING && videoRef.current) {
      // Verify truly ready
      const isReady = videoRef.current.readyState >= 3;
      if (isReady) {
        updateState(VideoState.READY);

        // Measure RTT before emitting
        const rtt = await measureRTT();
        setNetworkRTT(rtt);

        // Emit ready event
        emitEvent('video_ready', { buffered: true });
        updateState(VideoState.WAITING_CONFIRMATION);
      }
    }
  }, [videoState, updateState, measureRTT, emitEvent]);

  const handlePlaying = useCallback(() => {
    if (videoState === VideoState.STARTING || videoState === VideoState.BUFFERING) {
      updateState(VideoState.PLAYING);

      if (videoState === VideoState.STARTING) {
        emitEvent('video_started', {});
      }
    }
  }, [videoState, updateState, emitEvent]);

  const handleEnded = useCallback(() => {
    updateState(VideoState.ENDED);
    emitEvent('video_ended', {});
  }, [updateState, emitEvent]);

  const handleWaiting = useCallback(() => {
    if (videoState === VideoState.PLAYING) {
      updateState(VideoState.BUFFERING);
      emitEvent('video_buffering_start', {});
    }
  }, [videoState, updateState, emitEvent]);

  const handleError = useCallback(() => {
    if (videoRef.current?.error) {
      updateState(VideoState.ERROR);
      emitEvent('video_error', {
        error_message: videoRef.current.error.message,
        error_code: videoRef.current.error.code
      });

      // Retry logic
      if (retryCount < 3) {
        setTimeout(() => {
          setRetryCount(retryCount + 1);
          videoRef.current?.load();
        }, 2000 * (retryCount + 1)); // Exponential backoff
      }
    }
  }, [updateState, emitEvent, retryCount]);

  // Listen for orchestrator commands
  useEffect(() => {
    const handlePlayCommand = (message: any) => {
      if (message.video_index === videoIndex && message.session_id === sessionId) {
        if (videoState === VideoState.WAITING_CONFIRMATION && videoRef.current) {
          updateState(VideoState.STARTING);
          videoRef.current.play().catch((error) => {
            console.error(`Play failed for video ${videoIndex}:`, error);
            handleError();
          });
        }
      }
    };

    websocket.on('play_video', handlePlayCommand);
    return () => websocket.off('play_video', handlePlayCommand);
  }, [websocket, videoIndex, sessionId, videoState, updateState, handleError]);

  // Attach event listeners
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('canplaythrough', handleCanPlayThrough);
    video.addEventListener('playing', handlePlaying);
    video.addEventListener('ended', handleEnded);
    video.addEventListener('waiting', handleWaiting);
    video.addEventListener('error', handleError);

    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('canplaythrough', handleCanPlayThrough);
      video.removeEventListener('playing', handlePlaying);
      video.removeEventListener('ended', handleEnded);
      video.removeEventListener('waiting', handleWaiting);
      video.removeEventListener('error', handleError);
    };
  }, [handleLoadedMetadata, handleCanPlayThrough, handlePlaying, handleEnded, handleWaiting, handleError]);

  // Periodic RTT measurement
  useEffect(() => {
    const interval = setInterval(async () => {
      const rtt = await measureRTT();
      setNetworkRTT(rtt);
    }, 5000); // Every 5 seconds

    return () => clearInterval(interval);
  }, [measureRTT]);

  return (
    <div>
      <video
        ref={videoRef}
        muted
        playsInline
        style={{ width: '100%', height: 'auto', maxHeight: '400px', backgroundColor: '#000' }}
      />
      <div>
        <p>State: {videoState}</p>
        <p>Network RTT: {networkRTT.toFixed(2)}ms</p>
        {retryCount > 0 && <p>Retry attempt: {retryCount}/3</p>}
      </div>
    </div>
  );
};
```

### 9.2 Backend Event Handler (Python)

```python
from typing import Dict, Optional
import time
import logging
from socketio import AsyncServer

logger = logging.getLogger(__name__)

class VideoSequenceOrchestrator:
    def __init__(self, sio: AsyncServer, video_timing_service):
        self.sio = sio
        self.video_timing_service = video_timing_service
        self.active_sessions: Dict[str, Dict] = {}

    async def handle_video_ready(self, sid: str, data: Dict):
        """Handle video_ready event from frontend"""
        session_id = data['session_id']
        video_index = data['video_index']
        client_timestamp_ms = data['timestamp_ms']
        rtt_ms = data['rtt_ms']

        # Record server timestamp as authoritative
        server_timestamp_ms = time.time() * 1000

        # Calculate clock drift
        clock_drift_ms = client_timestamp_ms - server_timestamp_ms

        # Validate clock drift
        if abs(clock_drift_ms) > 5000:  # 5 seconds
            logger.error(f"Clock drift {clock_drift_ms}ms exceeds threshold")
            await self.sio.emit('error', {
                'message': 'Clock drift too large',
                'drift_ms': clock_drift_ms
            }, room=sid)
            return

        logger.info(
            f"✅ Video {video_index} ready for session {session_id} "
            f"(clock_drift={clock_drift_ms:.1f}ms, rtt={rtt_ms:.1f}ms)"
        )

        # Check preconditions for playing this video
        can_play = self._check_preconditions(session_id, video_index)

        if can_play:
            # Send play command
            await self.sio.emit('play_video', {
                'session_id': session_id,
                'video_index': video_index,
                'server_timestamp_ms': server_timestamp_ms
            }, room=sid)
        else:
            logger.warning(f"Cannot play video {video_index} - preconditions not met")

    async def handle_video_started(self, sid: str, data: Dict):
        """Handle video_started event from frontend"""
        session_id = data['session_id']
        video_index = data['video_index']
        client_timestamp_ms = data['timestamp_ms']
        rtt_ms = data['rtt_ms']

        # Record server timestamp as authoritative
        server_timestamp_ms = time.time() * 1000

        # Adjust for network latency
        one_way_latency_ms = rtt_ms / 2
        estimated_event_time_ms = server_timestamp_ms - one_way_latency_ms

        # Store timing data
        video_id = self._get_video_id(session_id, video_index)
        self.video_timing_service.start_video_timing(
            session_id=session_id,
            video_id=video_id,
            db=None,  # Will use internal database session
            video_metadata={
                'fps': 30,  # From video metadata
                'duration': 10.0  # From video metadata
            }
        )

        logger.info(
            f"🎬 Video {video_index} started for session {session_id} "
            f"(server_time={server_timestamp_ms:.1f}ms, "
            f"estimated_event_time={estimated_event_time_ms:.1f}ms, "
            f"latency={one_way_latency_ms:.1f}ms)"
        )

        # Confirm to frontend
        await self.sio.emit('video_started_confirmed', {
            'session_id': session_id,
            'video_index': video_index,
            'server_timestamp_ms': server_timestamp_ms,
            'estimated_event_time_ms': estimated_event_time_ms,
            'clock_drift_ms': client_timestamp_ms - server_timestamp_ms
        }, room=sid)

    async def handle_video_ended(self, sid: str, data: Dict):
        """Handle video_ended event from frontend"""
        session_id = data['session_id']
        video_index = data['video_index']
        client_timestamp_ms = data['timestamp_ms']

        server_timestamp_ms = time.time() * 1000

        logger.info(
            f"🏁 Video {video_index} ended for session {session_id} "
            f"(server_time={server_timestamp_ms:.1f}ms)"
        )

        # Evaluate video results
        self._evaluate_video_results(session_id, video_index)

        # Move to next video
        next_video_index = video_index + 1
        total_videos = self._get_total_videos(session_id)

        if next_video_index < total_videos:
            # Signal frontend to load next video
            await self.sio.emit('load_next_video', {
                'session_id': session_id,
                'video_index': next_video_index,
                'video_url': self._get_video_url(session_id, next_video_index)
            }, room=sid)
        else:
            # Sequence complete
            await self.sio.emit('sequence_completed', {
                'session_id': session_id,
                'total_videos': total_videos
            }, room=sid)

    def _check_preconditions(self, session_id: str, video_index: int) -> bool:
        """Check if video can be played"""
        # First video can always play
        if video_index == 0:
            return True

        # Previous video must be completed
        session_state = self.active_sessions.get(session_id)
        if not session_state:
            return False

        completed_videos = session_state.get('completed_videos', [])
        expected_completed = list(range(video_index))

        return expected_completed == completed_videos

    def _evaluate_video_results(self, session_id: str, video_index: int):
        """Evaluate detection results for completed video"""
        # Get detections for this video
        # Compare with ground truth
        # Calculate metrics (precision, recall, latency)
        # Store results
        pass  # Implementation from existing video_sequence_orchestrator.py
```

---

## 10. Testing Approach

### 10.1 Unit Tests

```typescript
// Test video state machine
describe('EnhancedVideoPlayer State Machine', () => {
  test('transitions from IDLE to LOADING on videoUrl change', () => {
    const { result } = renderHook(() => useVideoPlayer());

    act(() => {
      result.current.setVideoUrl('http://example.com/video.mp4');
    });

    expect(result.current.videoState).toBe(VideoState.LOADING);
  });

  test('transitions from LOADING to READY on canplaythrough', () => {
    const { result } = renderHook(() => useVideoPlayer());
    const video = result.current.videoRef.current;

    act(() => {
      fireEvent(video, new Event('canplaythrough'));
    });

    expect(result.current.videoState).toBe(VideoState.READY);
  });

  test('emits video_ready event with RTT measurement', async () => {
    const mockEmit = jest.fn();
    const { result } = renderHook(() => useVideoPlayer({ websocket: { emit: mockEmit } }));

    act(() => {
      fireEvent(result.current.videoRef.current, new Event('canplaythrough'));
    });

    await waitFor(() => {
      expect(mockEmit).toHaveBeenCalledWith('video_ready', expect.objectContaining({
        rtt_ms: expect.any(Number)
      }));
    });
  });
});
```

### 10.2 Integration Tests

```typescript
describe('Video Sequence Playback Integration', () => {
  test('plays videos in strict sequential order', async () => {
    const videos = [
      { id: '1', url: 'video1.mp4' },
      { id: '2', url: 'video2.mp4' },
      { id: '3', url: 'video3.mp4' }
    ];

    const { getByTestId } = render(
      <VideoSequencePlayer videos={videos} sessionId="test-session" />
    );

    // Wait for first video to load and play
    await waitFor(() => {
      expect(getByTestId('video-player-0')).toHaveAttribute('data-state', 'playing');
    });

    // Simulate video end
    fireEvent(getByTestId('video-player-0'), new Event('ended'));

    // Second video should start loading
    await waitFor(() => {
      expect(getByTestId('video-player-1')).toHaveAttribute('data-state', 'loading');
    });

    // First video should be completed
    expect(getByTestId('video-player-0')).toHaveAttribute('data-state', 'ended');
  });

  test('handles video load failure with retry', async () => {
    const videos = [{ id: '1', url: 'invalid-video.mp4' }];

    const { getByTestId, getByText } = render(
      <VideoSequencePlayer videos={videos} sessionId="test-session" />
    );

    // Simulate error
    const video = getByTestId('video-player-0');
    fireEvent.error(video);

    // Should show retry attempt
    await waitFor(() => {
      expect(getByText('Retry attempt: 1/3')).toBeInTheDocument();
    });
  });
});
```

### 10.3 End-to-End Tests (Playwright)

```typescript
import { test, expect } from '@playwright/test';

test('complete video sequence playback', async ({ page }) => {
  // Navigate to test page
  await page.goto('http://localhost:3000/test-execution/session-123');

  // Wait for first video to be ready
  await page.waitForSelector('[data-video-index="0"][data-state="ready"]');

  // Backend should send play command
  await page.waitForSelector('[data-video-index="0"][data-state="playing"]');

  // Wait for video to complete
  await page.waitForSelector('[data-video-index="0"][data-state="ended"]', { timeout: 15000 });

  // Second video should auto-load
  await page.waitForSelector('[data-video-index="1"][data-state="loading"]');

  // Verify sequence progress
  const progress = await page.locator('.sequence-progress').textContent();
  expect(progress).toContain('1 / 3');
});

test('detects tab backgrounding and pauses', async ({ page, context }) => {
  await page.goto('http://localhost:3000/test-execution/session-123');

  // Start playing
  await page.waitForSelector('[data-state="playing"]');

  // Create new tab (backgrounds current tab)
  const newPage = await context.newPage();
  await newPage.goto('about:blank');

  // Switch back to original tab
  await page.bringToFront();

  // Should show warning about backgrounding
  await expect(page.locator('.warning-backgrounded')).toBeVisible();
});
```

---

## 11. Summary & Recommendations

### 11.1 Feasibility Verdict

| Requirement | Feasibility | Notes |
|------------|------------|-------|
| **Video Lifecycle Events** | ✅ Fully Feasible | Use `canplaythrough`, `playing`, `ended` |
| **Millisecond Timestamp Precision** | ✅ Fully Feasible | `performance.now()` provides ±1-5ms accuracy |
| **Sub-millisecond Precision** | ❌ Not Feasible | Browser timer resolution limited to ~1ms |
| **Playlist Sequential Playback** | ✅ Fully Feasible | State machine + orchestrator handshake |
| **Autoplay (Muted)** | ✅ Fully Feasible | Works in all modern browsers |
| **Autoplay (Unmuted)** | ❌ Not Feasible | Requires user interaction |
| **Buffering Detection** | ✅ Fully Feasible | `waiting` + `playing` events |
| **Clock Synchronization** | ⚠️ Partially Feasible | ±1-5s drift typical, needs validation |
| **Network Latency Compensation** | ✅ Fully Feasible | RTT measurement + server-authoritative timestamps |
| **Background Tab Handling** | ⚠️ Partially Feasible | Detection reliable, mitigation (pause) required |

### 11.2 Recommended Implementation

**Phase 1: Core Functionality (Week 1-2)**
1. ✅ Implement state machine-based video player
2. ✅ Add WebSocket event emission (video_ready, video_started, video_ended)
3. ✅ Implement orchestrator handshake (wait for play_video command)
4. ✅ Add RTT measurement and clock sync check

**Phase 2: Error Handling (Week 3)**
1. ✅ Implement retry logic for video load failures
2. ✅ Add buffering detection and reporting
3. ✅ Add network disconnection handling with event queue
4. ✅ Implement tab backgrounding detection + pause

**Phase 3: Testing & Refinement (Week 4)**
1. ✅ Unit tests for state machine
2. ✅ Integration tests for multi-video sequences
3. ✅ End-to-end tests with real WebSocket backend
4. ✅ Cross-browser compatibility testing

### 11.3 Critical Design Decisions

**1. Server-Authoritative Timestamps**
- ✅ Backend assigns canonical timestamps for all events
- ✅ Client reports RTT with each event for latency compensation
- ✅ Clock drift validation (reject if > 5 seconds)

**2. Millisecond Precision Target**
- ✅ Achievable with `performance.now()` + `performance.timeOrigin`
- ❌ Sub-millisecond precision not achievable in browser
- ✅ Backend timing service provides nanosecond precision for hardware correlation

**3. Event-Driven Architecture**
- ✅ Frontend emits lifecycle events (video_ready, video_started, video_ended)
- ✅ Backend orchestrator coordinates playback (play_video commands)
- ✅ Strict state machine prevents invalid transitions

**4. Grace Period Buffers**
- ✅ 100-200ms grace period for video transitions
- ✅ Compensates for network latency + browser timing jitter
- ✅ Backend clamps detection windows to prevent cross-video contamination

**5. Fail-Safe Mechanisms**
- ✅ Retry logic for transient failures (3 attempts with exponential backoff)
- ✅ Event queue for network disconnections (30-second grace period)
- ✅ Tab backgrounding detection + pause (invalidate results if backgrounded)

### 11.4 Performance Expectations

| Metric | Expected Performance |
|--------|---------------------|
| **Timestamp Precision** | ±1-5ms (browser-dependent) |
| **Clock Drift** | ±1-5 seconds typical (OS-dependent) |
| **Network Latency** | 20-100ms typical (LAN environment) |
| **Video Transition Gap** | 100-500ms (backend processing + network) |
| **Buffering Recovery** | <5 seconds (network-dependent) |
| **WebSocket Reconnect** | <5 seconds (automatic retry) |

### 11.5 Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| **Sub-millisecond precision unavailable** | Cannot match backend nanosecond precision | Backend timing service authoritative |
| **Autoplay restrictions** | Requires muted playback | Use `muted` attribute (acceptable for testing) |
| **Background tab throttling** | Timing degradation if tab backgrounded | Detect + pause, invalidate if backgrounded |
| **Safari quirks** | `canplaythrough` unreliable | Double-check with `readyState >= 3` |
| **Network latency variability** | 20-100ms jitter | RTT measurement + grace period |

---

## 12. Conclusion

Multi-video timing synchronization is **feasible in the browser with millisecond-level precision** using the recommended architecture:

1. **HTML5 Video Events** provide reliable lifecycle tracking (`canplaythrough`, `playing`, `ended`)
2. **performance.now()** provides monotonic millisecond-precision timestamps
3. **WebSocket-based orchestration** enables strict sequential playback control
4. **Server-authoritative timestamps** eliminate client clock drift issues
5. **RTT measurement + grace periods** compensate for network latency

**Key Success Factors:**
- ✅ Use state machine for strict ordering enforcement
- ✅ Backend orchestrator coordinates all playback decisions
- ✅ Server timestamps are authoritative (client reports for context only)
- ✅ 100-200ms grace periods handle network jitter
- ✅ Detect + mitigate edge cases (backgrounding, disconnection, buffering)

**Sub-millisecond precision is NOT achievable in browser**, but the backend timing service can provide nanosecond precision for hardware detection correlation. The frontend's role is to emit reliable lifecycle events with millisecond accuracy, while the backend correlates these with high-precision hardware timestamps.

---

**Document Version:** 1.0
**Author:** Technical Analysis Team
**Last Updated:** 2025-11-20
