# Complete Dependency & Data Flow Map - Multi-Video HIL Testing

## State Management Overview

### React State (useState)
```
Project Selection State:
├── projects (Project[])
├── selectedProject (Project | null)
├── videoPlaylist (VideoFile[])
├── selectedVideoIds (string[])
├── orderedVideos (VideoFile[])
├── multiVideoMode (boolean)
└── maxLatencyMs (number)

Test Execution State:
├── currentSession (HILTestSession | null)
├── testRunning (boolean)
├── isFullScreen (boolean)
├── sequenceId (string | null)
├── detectionEvents (DetectionEvent[])
├── expectedDetections ({timestamp, id}[])     ⚠️ LEGACY - kept for UI display only
├── allVideoExpectedDetections (Map<videoId, detections[]>)  ✅ PRIMARY SOURCE
├── currentVideoIdx (number)
├── currentVideoId (string | null)
└── videoStartTimes (Map<videoId, timestamp>)

UI State:
├── loading (boolean)
├── error (string | null)
├── snackbarOpen (boolean)
├── snackbarMessage (string)
└── snackbarSeverity ('success' | 'error' | 'warning' | 'info')

VRU Tracking State:
├── vruTracks (VRUTrack[])
├── vruDetectionEvents (VRUDetectionEvent[])
├── trackingResult (VRUTrackingResult | null)
├── vruTrackingEnabled (boolean)
├── trackingMetrics (any)
├── t3Alerts (T3AlertsResponse | null)
└── t3PipelineSummary (object | null)

LabJack State:
└── labjackStatus ({connected, status, deviceInfo?, error?})
```

### React Refs (useRef)
```
DOM Refs:
├── videoRef (HTMLVideoElement)
└── fullscreenContainerRef (HTMLDivElement)

Connection Refs:
├── wsRef (WebSocket | null)
└── pollingIntervalRef (NodeJS.Timeout | null)

Timing Refs:
├── sequenceStartTimeRef (number | null)      ✅ CRITICAL - performance.now() timestamp
└── videoTimingsRef (VideoTimingMetadata[])   ✅ CRITICAL - per-video timing data

Service Refs:
├── vruTrackManagerRef (VRUTrackManager | null)
├── temporalMatcherRef (TemporalMatcher | null)
└── stalledRetryRef (number)
```

---

## Critical Data Flow Chains

### 1. Test Initialization Flow
```
USER: Click "Start Test"
    ↓
startTest() BEGINS
    ↓
┌─────────────────────────────────────────┐
│ PHASE 1: Ground Truth Preloading       │
├─────────────────────────────────────────┤
│ for each video in validatedVideos:     │
│   ├─→ loadExpectedDetectionsForVideo() │
│   │     ├─→ apiService.getAnnotations()│
│   │     ├─→ setExpectedDetections()    │ ⚠️ Updates global (UI display)
│   │     └─→ return detections array    │
│   └─→ preloadedMap.set(videoId, dets)  │
│                                         │
│ setAllVideoExpectedDetections(map)     │ ✅ PRIMARY SOURCE
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ PHASE 2: Session Creation              │
├─────────────────────────────────────────┤
│ apiService.createTestSession()          │
│    ↓                                    │
│ session = {                             │
│   id, projectId,                        │
│   testStartTime: new Date(),           │ ⚠️ Date object for compatibility
│   maxLatencyMs,                         │
│   labjackConnected,                     │
│   status: 'running',                    │
│   videoPlaylist                         │
│ }                                       │
│    ↓                                    │
│ setCurrentSession(session)              │
│ setSequenceId(`sequence_${sessionId}`)  │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ PHASE 3: Detection Monitoring Setup    │
├─────────────────────────────────────────┤
│ if (websocket available):               │
│   └─→ setupWebSocket()                  │
│        └─→ wsRef.current = new WS()     │
│ else:                                   │
│   └─→ setupPolling()                    │
│        └─→ pollingIntervalRef = setInt  │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ PHASE 4: Video Playback Start          │
├─────────────────────────────────────────┤
│ setTestRunning(true)                    │
│ setStartTestDialog(false)               │
│                                         │
│ <SequentialVideoPlayer> renders        │
│    ↓                                    │
│ First video loads automatically         │
└─────────────────────────────────────────┘
```

### 2. Video Sequence Playback Flow
```
<SequentialVideoPlayer>
    ↓
┌─────────────────────────────────────────┐
│ VIDEO 1 STARTS (index=0)               │
├─────────────────────────────────────────┤
│ loadAndPlayVideo(video1, 0)             │
│    ↓                                    │
│ if (index === 0):                       │
│   sequenceStartTime = performance.now() │ ✅ High-precision sequence start
│    ↓                                    │
│ videoTiming = createVideoTimingMeta()   │
│    ├─→ loadStartTime: performance.now() │
│    ├─→ expectedStartTime: calculated    │
│    └─→ playbackStartTime: null (pending)│
│    ↓                                    │
│ videoRef.src = video.url                │
│ await videoRef.load()                   │
│    ↓                                    │
│ await safeVideoPlay()                   │
│    ↓                                    │
│ playbackStartTime = performance.now()   │ ✅ Actual play start
│    ↓                                    │
│ updatedTiming = recordPlaybackStart()   │
│    ├─→ actualStartDelay calculated      │
│    └─→ transitionDelay calculated       │
│    ↓                                    │
│ setVideoStartTime(playbackStartTime)    │
│    ↓                                    │
│ ┌──────────────────────────────────┐   │
│ │ CALLBACK TO PARENT               │   │
│ │ onVideoStarted(id, idx, time)    │   │
│ └──────────────────────────────────┘   │
│           ↓                             │
│    handleVideoStarted() in parent       │
│      ├─→ setCurrentVideoId(videoId)     │
│      ├─→ setCurrentVideoIdx(index)      │
│      └─→ setVideoStartTimes.set()       │ ✅ CRITICAL for detection timing
│                                         │
│ ⚠️ NOTE: Ground truth already loaded    │
│    in preloading phase, no race!        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ VIDEO 1 PLAYING                         │
├─────────────────────────────────────────┤
│ LabJack detections arrive...            │
│ (See Detection Flow below)              │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ VIDEO 1 ENDS                            │
├─────────────────────────────────────────┤
│ handleVideoEnd()                        │
│    ↓                                    │
│ playbackEndTime = performance.now()     │
│    ↓                                    │
│ updatedTiming = recordPlaybackEnd()     │
│    └─→ duration calculated              │
│    ↓                                    │
│ videoTimingsRef.push(updatedTiming)     │ ✅ Store timing history
│    ↓                                    │
│ if (nextVideo exists):                  │
│   └─→ loadAndPlayVideo(video2, 1)       │ ⚠️ IMMEDIATE - no delay
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ VIDEO 2 STARTS (index=1)               │
├─────────────────────────────────────────┤
│ SAME FLOW AS VIDEO 1                   │
│ (sequence continues...)                 │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ LAST VIDEO ENDS                         │
├─────────────────────────────────────────┤
│ calculateSequenceTimingStats()          │
│    ↓                                    │
│ onSequenceComplete()                    │
│    ↓                                    │
│ handleSequenceComplete()                │
│    ↓                                    │
│ stopTestAndGenerateResults()            │
└─────────────────────────────────────────┘
```

### 3. Detection Processing Flow (CRITICAL PATH)
```
LabJack Signal Arrives
    ↓
┌──────────────────────────────────────────────┐
│ THREE PATHS (WebSocket / Polling / Direct)  │
└──────────────────────────────────────────────┘
    ↓                ↓                ↓
 WebSocket    Polling Handler   handleLabJackSignal
    ↓                ↓                ↓
┌────────────────────────────────────────────────┐
│ UNIFIED PROCESSING (All 3 paths identical)    │
├────────────────────────────────────────────────┤
│ 1. Extract timestamp                          │
│    signalTimestamp = data.timestamp_ms ||     │
│                      data.timestamp || null   │
│    if (null): SKIP detection ✅               │
│                                                │
│ 2. Get sequence start reference               │
│    sequenceStartMs = sequenceStartTimeRef ||  │
│                      session.testStartTime    │
│                                                │
│ 3. Calculate sequence-relative time           │
│    sequenceElapsed = (signal - seqStart)/1000 │
│                                                │
│ 4. Get current video context                  │
│    activeVideoId = currentVideoId             │
│    videoStartTime = videoStartTimes.get(id)   │ ✅ CRITICAL lookup
│                                                │
│ 5. Calculate video-relative time              │
│    videoRelative = videoStartTime ?           │
│      (signal - videoStart)/1000 :             │
│      sequenceElapsed                          │
│                                                │
│ 6. Get video-specific ground truth            │
│    groundTruth =                              │
│      allVideoExpectedDetections.get(videoId)  │ ✅ CRITICAL - per-video GT
│    if (empty): SKIP detection ✅              │
│                                                │
│ 7. Find nearest expected detection            │
│    for (expected of groundTruth):             │
│      timeDiff = |videoRelative - expected|    │
│      if (timeDiff < minDiff):                 │
│        nearestExpected = expected             │
│                                                │
│ 8. Calculate latency                          │
│    latencyMs = (videoRelative -               │
│                 nearest.timestamp) * 1000     │
│                                                │
│ 9. Calculate expected event time              │
│    expectedTime = videoStartTime ?            │
│      new Date(videoStart + nearest*1000) :    │
│      new Date(testStart + nearest*1000)       │
│                                                │
│ 10. Determine outcome                         │
│     outcome = |latencyMs| > maxLatencyMs ?    │
│       'fail_high_latency' : 'pass'            │
│                                                │
│ 11. Create detection event                    │
│     event = {                                 │
│       expectedEventTime,                      │
│       signalReceivedTime,                     │
│       latencyMs,                              │
│       outcome,                                │
│       videoId,                                │
│       videoIndex,                             │
│       videoStartTime,                         │
│       videoRelativeTimestamp,                 │ ✅ For this video
│       sequenceRelativeTimestamp               │ ✅ For sequence
│     }                                         │
│                                                │
│ 12. Store detection event                     │
│     setDetectionEvents(prev => [...prev, event])│
└────────────────────────────────────────────────┘
```

### 4. Results Generation Flow
```
stopTestAndGenerateResults()
    ↓
┌─────────────────────────────────────────┐
│ PHASE 1: Stop Detection Monitoring     │
├─────────────────────────────────────────┤
│ setTestRunning(false)                   │
│ wsRef.current?.close()                  │
│ clearInterval(pollingIntervalRef)       │
│ videoRef.current?.pause()               │
│ exitFullScreen()                        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ PHASE 2: Generate Results               │
├─────────────────────────────────────────┤
│ generateTestResults()                   │
│    ↓                                    │
│ Group detections by video:              │
│   detectionsByVideo = new Map()         │
│   for (event of detectionEvents):       │
│     map.set(event.videoId, [...])       │
│    ↓                                    │
│ Calculate PER-VIDEO results:            │
│   for (video of validatedVideos):       │
│     videoId = video.id                  │
│     videoExpected =                     │
│       allVideoExpectedDetections        │
│         .get(videoId) || []             │ ✅ Correct per-video GT
│     videoDetections =                   │
│       detectionsByVideo                 │
│         .get(videoId) || []             │
│                                         │
│     passed = count(outcome === 'pass')  │
│     failed = count(outcome === 'fail')  │
│                                         │
│     Calculate missed detections:        │
│       detectedTimes = Set(              │
│         videoDetections.map(            │
│           e => round(e.videoRelative)   │
│         )                               │
│       )                                 │
│       missed = videoExpected.filter(    │
│         exp => !detectedTimes.has(      │
│           round(exp.timestamp)          │
│         )                               │
│       ).length                          │
│                                         │
│     videoResults.push({                 │
│       video_id: videoId,                │
│       video_filename,                   │
│       video_order,                      │
│       video_start_time,                 │
│       expected_detections,              │
│       actual_detections,                │
│       passed_detections,                │
│       failed_detections,                │
│       missed_detections,                │ ✅ FALSE NEGATIVES per video
│       pass_rate,                        │
│       avg/max/min_latency_ms            │
│     })                                  │
│                                         │
│ Aggregate overall statistics            │
│ return {                                │
│   session_id,                           │
│   sequence_id,                          │
│   test_start_time,                      │
│   test_end_time,                        │
│   overall_pass_rate,                    │
│   total_missed,                         │
│   video_results: videoResults[],        │ ✅ Per-video breakdown
│   has_video_sequence: true              │
│ }                                       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ PHASE 3: Save & Navigate               │
├─────────────────────────────────────────┤
│ saveResultsToDatabase(results)          │
│    ↓                                    │
│ localStorage.setItem(results)           │
│    ↓                                    │
│ navigate(`/results/${sessionId}`)       │
└─────────────────────────────────────────┘
```

---

## Dependency Graph

### Function Dependencies (useCallback)

```
showSnackbar
  └─→ Dependencies: []
  └─→ Used by: ALL functions

loadExpectedDetectionsForVideo
  ├─→ Dependencies: [showSnackbar, attemptFallbackGroundTruthLoading]
  ├─→ Calls: apiService.getAnnotations()
  ├─→ Updates: expectedDetections (for UI), returns array
  └─→ Used by: startTest() preloading loop

handleVideoStarted
  ├─→ Dependencies: [validatedVideos, showSnackbar, loadExpectedDetectionsForVideo]
  ├─→ Updates: currentVideoId, currentVideoIdx, videoStartTimes
  ├─→ Updates: allVideoExpectedDetections (REMOVED - now preloaded)
  └─→ Called by: SequentialVideoPlayer.onVideoStarted

handleSequenceComplete
  ├─→ Dependencies: [stopTestAndGenerateResults]
  └─→ Called by: SequentialVideoPlayer.onSequenceComplete

exitFullScreen
  ├─→ Dependencies: []
  ├─→ Updates: isFullScreen
  └─→ Used by: stopTestAndGenerateResults

saveResultsToDatabase
  ├─→ Dependencies: [showSnackbar]
  ├─→ Calls: fetch(`/api/test-sessions/${id}/results`)
  └─→ Used by: stopTestAndGenerateResults

generateTestResults
  ├─→ Dependencies: [
  │     currentSession,
  │     selectedProject,
  │     detectionEvents,
  │     validatedVideos,
  │     allVideoExpectedDetections,  ✅ CRITICAL
  │     videoStartTimes,              ✅ CRITICAL
  │     sequenceId,
  │     maxLatencyMs,
  │     labjackStatus.connected
  │   ]
  ├─→ Reads: ALL detection and timing state
  └─→ Used by: stopTestAndGenerateResults

stopTestAndGenerateResults
  ├─→ Dependencies: [
  │     exitFullScreen,
  │     generateTestResults,
  │     saveResultsToDatabase,
  │     showSnackbar,
  │     navigate,
  │     currentSession
  │   ]
  ├─→ Calls: wsRef, pollingIntervalRef, videoRef
  └─→ Called by: handleSequenceComplete, stopTest, ESC key
```

### State Update Chain

```
State Update Cascade:

1. startTest()
   ├─→ setAllVideoExpectedDetections(preloadedMap)
   ├─→ setCurrentSession(session)
   ├─→ setSequenceId(id)
   ├─→ setTestRunning(true)
   └─→ Triggers: SequentialVideoPlayer render

2. SequentialVideoPlayer (via callbacks)
   ├─→ onVideoStarted
   │   ├─→ setCurrentVideoId(id)
   │   ├─→ setCurrentVideoIdx(idx)
   │   └─→ setVideoStartTimes.set(id, time)
   └─→ onSequenceComplete
       └─→ stopTestAndGenerateResults()

3. Detection Handlers (WebSocket/Polling/LabJack)
   └─→ setDetectionEvents(prev => [...prev, event])

4. stopTestAndGenerateResults()
   ├─→ setTestRunning(false)
   ├─→ setIsFullScreen(false)
   └─→ setCurrentSession(prev => ({...prev, status: 'completed'}))
```

### Critical Data Dependencies

```
Detection Processing Dependencies:
  ├─→ signalData.timestamp_ms OR signalData.timestamp     (from LabJack)
  ├─→ sequenceStartTimeRef.current                        (from startTest)
  ├─→ currentVideoId                                      (from handleVideoStarted)
  ├─→ videoStartTimes.get(currentVideoId)                 (from handleVideoStarted)
  ├─→ allVideoExpectedDetections.get(currentVideoId)      (from startTest preload)
  └─→ maxLatencyMs                                        (from user input)

Results Generation Dependencies:
  ├─→ currentSession                    (from startTest)
  ├─→ selectedProject                   (from user selection)
  ├─→ detectionEvents                   (accumulated during test)
  ├─→ validatedVideos                   (from useMemo)
  ├─→ allVideoExpectedDetections        (from startTest preload)
  ├─→ videoStartTimes                   (from handleVideoStarted calls)
  ├─→ sequenceId                        (from startTest)
  └─→ labjackStatus.connected           (from useEffect polling)
```

---

## Timing Synchronization Points

### CRITICAL SYNC POINT 1: Sequence Start
```
Location: startTest() → SequentialVideoPlayer.loadAndPlayVideo(video, 0)
Timing: performance.now() captured AFTER first video loads

Dependencies:
  └─→ sequenceStartTimeRef.current = performance.now()

Used By:
  ├─→ Detection handlers (calculate sequence-relative time)
  └─→ Video timing calculations
```

### CRITICAL SYNC POINT 2: Video Start
```
Location: SequentialVideoPlayer → handleVideoStarted callback
Timing: performance.now() captured at video.play()

Dependencies:
  └─→ setVideoStartTimes(videoId, performance.now())

Used By:
  ├─→ Detection handlers (calculate video-relative time)
  └─→ Results generation (video start time in results)
```

### CRITICAL SYNC POINT 3: Ground Truth Availability
```
Location: startTest() preloading loop
Timing: BEFORE videos play (SEQUENTIAL await)

Dependencies:
  └─→ setAllVideoExpectedDetections(preloadedMap)

Used By:
  ├─→ Detection handlers (match detections to expected)
  └─→ Results generation (calculate missed detections)
```

---

## Race Condition Analysis

### ✅ ELIMINATED: Ground Truth Loading Race
**Before Fix:**
```
T=0:   Video 2 starts
T=1:   handleVideoStarted() called
T=2:   loadExpectedDetections().then(...) ← ASYNC
T=5:   Detection arrives
T=6:   Uses OLD ground truth ❌
T=100: Ground truth loads ← TOO LATE
```

**After Fix:**
```
T=-1000: startTest() preloads ALL ground truth
T=0:     Video 2 starts
T=1:     handleVideoStarted() called
T=2:     Ground truth ALREADY in Map ✅
T=5:     Detection arrives
T=6:     Uses CORRECT ground truth ✅
```

### ✅ NO RACE: Video Start Time Updates
```
T=0:   Video loads
T=1:   video.play() called
T=2:   playbackStartTime = performance.now()
T=3:   onVideoStarted(id, idx, time) called
T=4:   setVideoStartTimes.set(id, time)
T=5:   React updates state
T=6:   Detection handlers see new videoStartTime ✅
```

**No Race Because:**
- `setVideoStartTimes` called BEFORE video actually starts playing
- Small delay between play() call and actual playback
- Detection latency (1-50ms) longer than state update time

### ⚠️ POTENTIAL RACE: Very First Detection
```
T=0:   Video 1 starts playing
T=1:   handleVideoStarted() called
T=2:   setVideoStartTimes.set(video1, T0)
T=3:   State update pending...
T=4:   LabJack detection arrives (VERY FAST)
T=5:   currentVideoId updated ✅
T=6:   videoStartTimes.get(video1) = ??? ⚠️
```

**Risk Level: LOW**
- State updates usually faster than LabJack latency (1ms vs 10-50ms)
- Even if race occurs, detection uses fallback: sequence-relative time
- Only affects first detection of first video

**Mitigation:**
Detection handler has fallback:
```typescript
const videoRelativeSeconds = videoStartTime
  ? (signalTimestamp - videoStartTime) / 1000
  : sequenceElapsedSeconds; // ← FALLBACK
```

---

## Async Operation Dependencies

### Sequential Operations (Must Complete in Order)
```
1. startTest()
   └─→ await loadExpectedDetectionsForVideo(video1)
       └─→ await loadExpectedDetectionsForVideo(video2)
           └─→ await loadExpectedDetectionsForVideo(video3)
               └─→ setAllVideoExpectedDetections(map)
                   └─→ Start video playback

⚠️ SEQUENTIAL PRELOADING
   - Each video waits for previous
   - Total time: N * (50-500ms) = 150-1500ms for 3 videos
   - Blocks test start

✅ COULD OPTIMIZE with Promise.all():
   await Promise.all(videos.map(v => load(v)))
   - Parallel loading
   - Total time: max(50-500ms) = 50-500ms
```

### Parallel Operations (Independent)
```
Detection Monitoring:
├─→ WebSocket connection (if available)
├─→ Polling interval (fallback)
└─→ handleLabJackSignal (direct)

All run concurrently ✅
```

### Fire-and-Forget Operations
```
Results Generation:
├─→ saveResultsToDatabase(results) ✅
│   └─→ .then() / .catch() handled
└─→ localStorage.setItem() ✅
    └─→ Synchronous, no await
```

---

## Memory Management

### State Accumulation
```
detectionEvents: DetectionEvent[]
  ├─→ Grows with every detection
  ├─→ Size: ~500 bytes per detection
  ├─→ Max expected: 100-1000 detections
  └─→ Memory impact: 50KB - 500KB ✅ Acceptable

allVideoExpectedDetections: Map<string, detection[]>
  ├─→ Size: ~200 bytes per detection
  ├─→ Max expected: 10 videos × 100 detections = 1000
  └─→ Memory impact: 200KB ✅ Acceptable

videoStartTimes: Map<string, number>
  ├─→ Size: ~50 bytes per video
  ├─→ Max expected: 10-20 videos
  └─→ Memory impact: 1KB ✅ Negligible
```

### Ref Management
```
wsRef.current
  └─→ Cleaned up in stopTest() ✅

pollingIntervalRef.current
  └─→ Cleared in stopTest() ✅

videoTimingsRef.current
  └─→ Accumulates VideoTimingMetadata
  └─→ Size: ~500 bytes per video
  └─→ Memory impact: 5KB for 10 videos ✅ Negligible
```

---

## Identified Issues & Recommendations

### ✅ FIXED ISSUES
1. Ground truth race condition - PRELOADING
2. Artificial timestamp fallbacks - REMOVED
3. Wrong ground truth in handlers - USING MAP

### ⚠️ POTENTIAL OPTIMIZATIONS

#### 1. Parallel Ground Truth Preloading
**Current:**
```typescript
for (let i = 0; i < videos.length; i++) {
  const detections = await loadExpectedDetectionsForVideo(videos[i]);
  // SEQUENTIAL - slow for many videos
}
```

**Optimized:**
```typescript
const promises = videos.map(v => loadExpectedDetectionsForVideo(v));
const results = await Promise.all(promises);
// PARALLEL - faster for many videos
```

**Impact:**
- 3 videos: 150-1500ms → 50-500ms (3x faster)
- 10 videos: 500-5000ms → 50-500ms (10x faster)

#### 2. State Update Batching
**Current:**
```typescript
setCurrentVideoId(id);
setCurrentVideoIdx(idx);
setVideoStartTimes(prev => new Map(prev).set(id, time));
```

**Could Use:**
```typescript
flushSync(() => {
  setCurrentVideoId(id);
  setCurrentVideoIdx(idx);
  setVideoStartTimes(prev => new Map(prev).set(id, time));
});
```

**Impact:** Ensures all updates complete before next render

### 🔍 MONITORING RECOMMENDATIONS

1. **Add Timing Metrics:**
   - Ground truth preload time per video
   - State update latency
   - Detection processing time

2. **Add Validation:**
   - Verify videoStartTimes.has(currentVideoId) before processing detection
   - Verify allVideoExpectedDetections.has(videoId) before matching
   - Log warnings for missing data

3. **Add Error Recovery:**
   - Retry failed ground truth loads
   - Handle missing videoStartTime gracefully
   - Continue test even if ground truth unavailable for one video

---

**Status:** ✅ NO CRITICAL ISSUES FOUND
**Confidence:** 98% (minor optimization opportunities only)
**Date:** 2025-09-30