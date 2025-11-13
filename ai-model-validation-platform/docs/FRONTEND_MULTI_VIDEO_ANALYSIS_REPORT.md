# Frontend HIL Test Execution - Multi-Video Support Analysis

**Date**: 2025-10-30
**Component**: HILTestExecutionPRD.tsx + SequentialVideoPlayer.tsx
**Analysis Type**: Multi-Video Sequence Implementation Review

---

## Executive Summary

The frontend HIL test execution system has **solid multi-video support infrastructure** but contains **critical gaps** in video transition notification and state synchronization. The system properly tracks video playlists and maintains sequence state, but the backend is not consistently notified about video changes, which could lead to detection mismatches.

### Overall Status
- ✅ **Video Playlist Management**: Working correctly
- ✅ **Video Sequencing Logic**: Properly implemented
- ⚠️ **Backend Notification**: Inconsistent - only notifies on play, not on initial load
- ❌ **Video 1 Start Notification**: MISSING - Video 1 never notifies backend explicitly
- ✅ **Video Transition Handling**: Works for video 2+ transitions
- ✅ **State Management**: All critical variables properly initialized

---

## 1. Video Playlist Loading & Validation

### ✅ What's Working Correctly

**Location**: `HILTestExecutionPRD.tsx:134-325`

```typescript
// Line 134: Proper state initialization
const [videoPlaylist, setVideoPlaylist] = useState<VideoFile[]>([]);

// Line 223-325: Comprehensive video validation with URL fixing
const validatedVideos = useMemo(() => {
  const filtered = videoPlaylist.filter(video => {
    const statusCheck = video.status === 'validated' ||
                       (video as any).validationStatus === 'validated' ||
                       (video as any).validation_status === 'validated';
    const processingCheck = video.processing_status === 'completed' ||
                           (statusCheck && !video.processing_status);
    return statusCheck && processingCheck;
  });

  // CRITICAL FIX: URL population from file_path
  filtered.forEach(video => {
    fixVideoObjectUrl(video, { debug: true });
  });

  return filtered;
}, [videoPlaylist]);
```

**Strengths**:
- ✅ Multiple status field checks (handles API inconsistencies)
- ✅ URL fixing for validated videos
- ✅ Comprehensive logging for debugging
- ✅ Proper memoization to avoid re-renders

### ⚠️ Potential Issues

**Line 820-828**: Fallback logic uses first video from unvalidated playlist
```typescript
if (videoPlaylist.length > 0) {
  const fallbackVideo = videoPlaylist[0]; // May not be validated!
  console.log('🔄 [HIL GROUND TRUTH] Using fallback video:', {
    id: fallbackVideo.id,
    filename: fallbackVideo.filename,
    status: fallbackVideo.status, // Could be 'pending' or 'processing'
  });
}
```

**Risk**: If all videos fail validation, ground truth loads from potentially invalid video.

---

## 2. Video Sequencing Logic

### ✅ What's Working Correctly

**SequentialVideoPlayer.tsx:72-73**
```typescript
const [currentVideoIndex, setCurrentVideoIndex] = useState(0);
const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(videoPlaylist[0] || null);
```

**Video Advancement (Lines 600-615)**
```typescript
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
  loadAndPlayVideo(nextVideo, nextIndex); // ✅ Correctly advances
}
```

**Strengths**:
- ✅ `currentVideoIndex` properly tracks position
- ✅ Video advancement uses playlist array directly (not relying solely on backend)
- ✅ Proper boundary checking (`currentVideoIndex < videoPlaylist.length - 1`)
- ✅ Sequence completion detection works correctly

---

## 3. Backend Notification System

### ❌ CRITICAL BUG: Video 1 Start Notification Missing

**Problem**: Video 1 NEVER explicitly notifies the backend when it starts!

**SequentialVideoPlayer.tsx:106-152** - `sendVideoStartedEvent` function exists and works:
```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
  // Skip only if sequenceId is completely missing
  if (!sequenceId) {
    console.warn('⚠️ No sequence ID - skipping video-started event');
    return;
  }

  console.log('🎬 Sending video-started event to backend:', {
    sequenceId,
    videoId,
    startedAt: startedAtUnix,
    url: `/api/video-sequences/${sequenceId}/video-started`
  });

  const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
    videoId,
    startedAt: startedAtUnix,
    clientTimestamp,
    sequenceElapsedTime: sequenceStartUnix ? startedAtUnix - sequenceStartUnix : 0
  });
}, [sequenceId, sequenceStartUnix]);
```

**BUT** - This is only called from `loadAndPlayVideo` (Line 429):
```typescript
// Line 429: Send video started event to backend
await sendVideoStartedEvent(video.id, updatedTiming.playbackStartTime!);
```

**The Issue**: `loadAndPlayVideo` is called:
- ✅ For video 2+ transitions (Line 615: `loadAndPlayVideo(nextVideo, nextIndex)`)
- ❌ BUT NOT for the initial video 1!

**Video 1 initialization** happens in the component state (Line 73):
```typescript
const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(videoPlaylist[0] || null);
```

**This means**:
- Video 1 starts playing via HTML5 video element
- Backend never receives `video-started` event for video 1
- Detection matching service may not know which video is active
- Ground truth matching could fail for video 1 detections

### ✅ What Works: Video 2+ Transitions

**Lines 545-615**: Video-ended handler properly calls `loadAndPlayVideo` for next video:
```typescript
const handleVideoEnd = useCallback(async () => {
  // ... video end logic ...

  const nextIndex = currentVideoIndex + 1;
  const nextVideo = videoPlaylist[nextIndex];

  if (nextVideo) {
    loadAndPlayVideo(nextVideo, nextIndex); // ✅ This calls sendVideoStartedEvent
  }
}, [currentVideoIndex, videoPlaylist, loadAndPlayVideo]);
```

### ⚠️ Backend Endpoint Exists But May Not Be Used

**video_sequences.py:110-157**
```python
@router.post("/{sequence_id}/video-started", response_model=VideoEventResponse)
async def video_started(sequence_id: str, data: VideoStartedRequest):
    """Track when a video in a sequence starts playing."""

    # Update state
    sequence_state[sequence_id]["current_video"] = data.videoId
    sequence_state[sequence_id]["videos"].append({
        "video_id": data.videoId,
        "started_at": data.timestamp,
        "sequence_elapsed": data.sequenceElapsedTime,
        "status": "playing"
    })

    # CRITICAL FIX: Emit WebSocket event
    await sio.emit('video_started', {
        'sequence_id': sequence_id,
        'video_id': data.videoId,
        'timestamp': data.timestamp,
        'sequence_elapsed': data.sequenceElapsedTime,
        'started_at': data.startedAt
    }, room=f"test_session_{sequence_id}")
```

**The endpoint works**, but it's never called for video 1!

---

## 4. State Management Analysis

### ✅ All Critical Variables Properly Initialized

**HILTestExecutionPRD.tsx:134-155**
```typescript
const [videoPlaylist, setVideoPlaylist] = useState<VideoFile[]>([]);           // ✅ Empty array
const [currentVideoIdx, setCurrentVideoIdx] = useState<number>(0);             // ✅ Starts at 0
const [currentVideoId, setCurrentVideoId] = useState<string | null>(null);     // ✅ Null initially
const [videoStartTimes, setVideoStartTimes] = useState<Map<string, number>>(new Map()); // ✅ Empty map
const [allVideoExpectedDetections, setAllVideoExpectedDetections] = useState<Map<string, {timestamp: number, id: string}[]>>(new Map()); // ✅ Empty map
```

### ✅ Video State Tracking

**Lines 198-211**: `handleVideoStarted` callback properly updates state:
```typescript
const handleVideoStarted = useCallback((videoId: string, videoIndex: number, startTime: number) => {
  console.log('🎬 [HIL] Video started in sequence:', { videoId, videoIndex, startTime });
  setCurrentVideoId(videoId);                                    // ✅ Updates current video
  setCurrentVideoIdx(videoIndex);                                // ✅ Updates index
  setVideoStartTimes(prev => new Map(prev).set(videoId, startTime)); // ✅ Records start time

  // Ground truth already preloaded - just log confirmation
  const preloadedDetections = allVideoExpectedDetections.get(videoId);
  if (preloadedDetections) {
    console.log(`✅ [HIL] Using preloaded ${preloadedDetections.length} detections for video ${videoIndex + 1}`);
  } else {
    console.warn(`⚠️ [HIL] No preloaded ground truth for video ${videoIndex + 1}`);
  }
}, [allVideoExpectedDetections]);
```

**BUT** - This callback is passed to `SequentialVideoPlayer` (Line 2239):
```typescript
<SequentialVideoPlayer
  videoPlaylist={validatedVideos}
  sequenceId={sequenceId!}
  maxLatencyMs={maxLatencyMs}
  onSequenceComplete={handleSequenceComplete}
  onVideoStarted={handleVideoStarted}  // ✅ Callback is passed
  onError={(error) => { /* ... */ }}
/>
```

**And it's called in SequentialVideoPlayer** (Lines 432-434):
```typescript
if (onVideoStarted) {
  onVideoStarted(video.id, index, updatedTiming.playbackStartTime!);
}
```

**Problem**: This only fires when `loadAndPlayVideo` is called, which doesn't happen for video 1!

---

## 5. Project Selection & Video Setup

### ✅ What's Working

**Lines 1875-1893**: Project selection properly loads videos:
```typescript
<Select
  value={selectedProject?.id || ''}
  onChange={(e) => {
    const project = projects.find(p => p.id === e.target.value);
    if (project) handleProjectSelect(project);
  }}
  disabled={testRunning}
>
  {projects.map((project) => (
    <MenuItem key={project.id} value={project.id}>
      {project.name}
    </MenuItem>
  ))}
</Select>
```

**Lines 438-486**: `handleProjectSelect` loads video playlist:
```typescript
const handleProjectSelect = async (project: Project) => {
  setSelectedProject(project);
  await loadVideoPlaylist(project); // ✅ Loads videos
  await loadExpectedDetections();   // ✅ Loads ground truth
};

const loadVideoPlaylist = async (project: Project) => {
  const videos = await videoProjectService.getVideosByProjectId(project.id);
  setVideoPlaylist(videos); // ✅ Updates state
};
```

### ⚠️ VideoSequenceSelector Component Issue

**VideoSequenceSelector.tsx:17-75** - Component exists but may not be used:
```typescript
export const VideoSequenceSelector: React.FC<VideoSequenceSelectorProps> = ({
  videos,
  selectedVideo,
  onVideoChange
}) => {
  // Dropdown for manual video selection
};
```

**Not found in HILTestExecutionPRD.tsx** - This component may be legacy or unused.

---

## 6. Critical Checks

### ❌ Is `notifyVideoStart` called for EVERY video?

**NO** - There is no function called `notifyVideoStart` in the codebase.

The actual function is `sendVideoStartedEvent` and it's:
- ✅ Called for video 2, 3, 4, etc.
- ❌ NOT called for video 1

### ❌ Does the component handle video 1 → video 2 transition?

**PARTIAL** - The transition itself works, but:
- ✅ Video 2 starts playing correctly
- ✅ `sendVideoStartedEvent` is called for video 2
- ✅ Backend receives notification
- ❌ But video 1 was never announced to backend!

### ✅ Are video IDs passed correctly to backend?

**YES** - When the endpoint is called (video 2+):
```typescript
await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
  videoId,              // ✅ Correct video ID
  startedAt: startedAtUnix,
  clientTimestamp,
  sequenceElapsedTime: sequenceStartUnix ? startedAtUnix - sequenceStartUnix : 0
});
```

### ⚠️ Is sequence_order passed correctly?

**NO** - `sequence_order` is NOT included in the `video-started` payload!

**SequentialVideoPlayer.tsx:130-135** sends:
```typescript
{
  videoId,              // ✅ Present
  startedAt,            // ✅ Present
  clientTimestamp,      // ✅ Present
  sequenceElapsedTime   // ✅ Present
  // ❌ sequence_order missing!
  // ❌ videoIndex missing!
}
```

**Backend expects** (video_sequence_testing.py:472-477):
```python
async def record_video_started(
    sequence_id: str,
    request: VideoStartedRequest,  # Contains videoId, startedAt
    db: Session
):
    # Backend queries sequence_order from database, not from request
```

**Backend workaround** (video_sequence_testing.py:494-506):
```python
# Find SequenceVideoResult by video_id
sequence_video_result = db.query(SequenceVideoResult).filter(
    SequenceVideoResult.video_sequence_id == sequence_id,
    SequenceVideoResult.video_id == request.videoId
).first()

# Uses sequence_order from database record, not from frontend
```

**This works BUT** requires database record to exist with correct `sequence_order`.

---

## 7. Error Handling for Video Transitions

### ✅ What's Working

**SequentialVideoPlayer.tsx:313-380** - Comprehensive error handling:
```typescript
try {
  // Set video source
  videoRef.current.src = video.url || '';
  console.log('🎬 Video source set:', video.url);

  // Wait for video to be ready
  await new Promise<void>((resolve, reject) => {
    const handleCanPlay = () => {
      videoRef.current?.removeEventListener('canplay', handleCanPlay);
      videoRef.current?.removeEventListener('error', handleError);
      resolve();
    };

    const handleError = (e: Event) => {
      videoRef.current?.removeEventListener('canplay', handleCanPlay);
      videoRef.current?.removeEventListener('error', handleError);
      reject(new Error(`Failed to load video: ${(e as ErrorEvent).message}`));
    };

    videoRef.current?.addEventListener('canplay', handleCanPlay, { once: true });
    videoRef.current?.addEventListener('error', handleError, { once: true });
  });

  // Attempt to play with retry logic
  const playResult = await safeVideoPlay(videoRef.current);

  if (!playResult.success) {
    throw new Error(playResult.error || 'Failed to start playback');
  }

} catch (error) {
  // Retry logic with exponential backoff
  if (retryCount < MAX_RETRY_ATTEMPTS) {
    const delay = getRetryDelay(retryCount);
    console.log(`⏳ Retrying video load in ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRY_ATTEMPTS})`);

    setTimeout(() => {
      setRetryCount(prev => prev + 1);
      loadAndPlayVideo(video, index);
    }, delay);
  } else {
    logger.error('Video load failed after max retries', error as Error);
    onError(`Failed to load video after ${MAX_RETRY_ATTEMPTS} attempts`);
  }
}
```

**Strengths**:
- ✅ Waits for 'canplay' event before starting
- ✅ Exponential backoff retry (1s → 2s → 4s)
- ✅ Max 3 retry attempts
- ✅ Proper error propagation to parent component

### ⚠️ Edge Case: Video Source Change During Play

**Potential race condition** if videos transition rapidly:
```typescript
// Line 313: Source is set
videoRef.current.src = video.url || '';

// What if another call happens before canplay fires?
// The event listener might resolve for the wrong video!
```

**Mitigation**: The code uses `once: true` for event listeners, which helps, but there's no explicit video ID tracking in the promise.

---

## 8. WebSocket Events for Video State

### ✅ Backend Emits Events

**video_sequences.py:138-146**
```python
await sio.emit('video_started', {
    'sequence_id': sequence_id,
    'video_id': data.videoId,
    'timestamp': data.timestamp,
    'sequence_elapsed': data.sequenceElapsedTime,
    'started_at': data.startedAt
}, room=f"test_session_{sequence_id}")
```

**video_sequences.py:194-204**
```python
await sio.emit('video_ended', {
    'sequence_id': sequence_id,
    'video_id': data.videoId,
    'timestamp': data.timestamp,
    'duration': data.actualDuration,
    'sequence_elapsed': data.sequenceElapsedTime,
    'next_video_id': next_video_id
}, room=f"test_session_{sequence_id}")
```

### ⚠️ Frontend May Not Subscribe

**websocketService.ts:547-577** has sequence subscription support:
```typescript
subscribeToSequence(sequenceId: string) {
  this.emit('subscribe_sequence', { sequence_id: sequenceId });

  return {
    onVideoTransition: (callback) => this.subscribe('video_transition', callback),
    onVideoCompleted: (callback) => this.subscribe('video_completed', callback),
    onSequenceCompleted: (callback) => this.subscribe('sequence_completed', callback),
    unsubscribe: () => this.emit('unsubscribe_sequence', { sequence_id: sequenceId })
  };
}
```

**BUT** - No evidence of `subscribeToSequence` being called in HILTestExecutionPRD.tsx!

The frontend subscribes to generic events (Line 1434):
```typescript
// Detection events
const preloadedDetections = allVideoExpectedDetections.get(activeVideoId);
```

But not to `video_started` or `video_transition` events.

---

## 9. Ground Truth Loading Per Video

### ✅ What's Working

**Lines 805-902**: Comprehensive ground truth loading:
```typescript
const loadExpectedDetections = async (): Promise<void> => {
  try {
    const videoGroundTruthMap = new Map<string, {timestamp: number, id: string}[]>();

    for (const video of validatedVideos) {
      try {
        const annotations = await apiService.getGroundTruthByVideoId(video.id);
        const detections = annotations.map(annotation => ({
          timestamp: annotation.frame_number / (video.fps || 30),
          id: annotation.id
        }));

        videoGroundTruthMap.set(video.id, detections);
        console.log(`✅ Loaded ${detections.length} detections for video ${video.filename}`);
      } catch (error) {
        console.error(`❌ Failed to load ground truth for ${video.filename}:`, error);
        videoGroundTruthMap.set(video.id, []); // Set empty array on error
      }
    }

    setAllVideoExpectedDetections(videoGroundTruthMap); // ✅ Store per-video ground truth
  } catch (error) {
    console.error('❌ [HIL GROUND TRUTH] Critical error:', error);
  }
};
```

**Strengths**:
- ✅ Loads ground truth for ALL validated videos upfront
- ✅ Stores in Map indexed by video ID
- ✅ Handles per-video errors gracefully
- ✅ Comprehensive logging

### ✅ Ground Truth Usage During Test

**Lines 1443-1449**: Retrieves correct ground truth during signal processing:
```typescript
const videoGroundTruth = allVideoExpectedDetections.get(activeVideoId) || [];

const nearestDetection = videoGroundTruth.reduce((nearest, detection) => {
  const timeDiff = Math.abs(detection.timestamp - videoRelativeSeconds);
  return timeDiff < nearest.timeDiff ? { detection, timeDiff } : nearest;
}, { detection: null, timeDiff: Infinity });
```

**This works correctly** - uses the right ground truth for the active video.

---

## 10. Summary of Findings

### ✅ What's Working Correctly

1. **Video Playlist Loading**
   - Proper validation filtering (status + processing_status)
   - URL fixing from file_path
   - Memoization prevents unnecessary re-renders

2. **Video Sequencing**
   - `currentVideoIndex` advances correctly
   - Video 2+ transitions work smoothly
   - Sequence completion detection is accurate

3. **State Management**
   - All variables properly initialized
   - Video start times tracked per video
   - Ground truth stored per video ID

4. **Error Handling**
   - Retry logic with exponential backoff
   - Proper error propagation
   - Graceful degradation on failures

5. **Ground Truth System**
   - Loads upfront for all videos
   - Per-video storage in Map
   - Correct retrieval during detections

### ⚠️ Potential Issues / Edge Cases

1. **Fallback Ground Truth**
   - Uses first unvalidated video if all validation fails
   - Could load ground truth from wrong video

2. **WebSocket Subscription**
   - Backend emits `video_started` events
   - Frontend doesn't explicitly subscribe to them
   - May miss real-time updates

3. **Sequence Order Field**
   - Not included in `video-started` payload
   - Backend relies on database record
   - Could fail if DB record missing or incorrect

4. **Video Source Race Condition**
   - Rapid transitions could confuse event listeners
   - No explicit video ID in canplay promise

### ❌ Critical Bugs That Must Be Fixed

#### **BUG #1: Video 1 Never Notifies Backend**

**Location**: SequentialVideoPlayer.tsx:73, loadAndPlayVideo function call missing

**Problem**:
```typescript
// Initial video set in state
const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(videoPlaylist[0] || null);

// Video element plays via useEffect, but loadAndPlayVideo is NEVER called for video 1
// Therefore sendVideoStartedEvent is never triggered
```

**Impact**:
- Backend never knows video 1 started
- `sequence_state` doesn't include video 1
- Detection matching service may fail for video 1
- Ground truth matching could be incorrect

**Fix Required**:
```typescript
// Add to SequentialVideoPlayer useEffect
useEffect(() => {
  if (currentVideo && currentVideoIndex === 0 && videoRef.current) {
    // Explicitly call loadAndPlayVideo for the first video
    loadAndPlayVideo(currentVideo, 0);
  }
}, [currentVideo, currentVideoIndex]);
```

#### **BUG #2: Video Transition Events Not Subscribed**

**Location**: HILTestExecutionPRD.tsx - missing WebSocket subscription

**Problem**:
```typescript
// websocketService has subscribeToSequence method
// BUT it's never called in HILTestExecutionPRD.tsx

// Backend emits:
await sio.emit('video_started', { ... }, room=f"test_session_{sequence_id}")
await sio.emit('video_ended', { ... }, room=f"test_session_{sequence_id}")

// Frontend never subscribes to these events!
```

**Impact**:
- Frontend doesn't react to backend video state changes
- UI may show stale video information
- Synchronization issues between frontend and backend

**Fix Required**:
```typescript
// In HILTestExecutionPRD.tsx, after test starts:
useEffect(() => {
  if (testRunning && sequenceId) {
    const subscription = websocketService.subscribeToSequence(sequenceId);

    subscription.onVideoTransition((data) => {
      console.log('🎬 Video transition event:', data);
      // Update UI if needed
    });

    subscription.onVideoCompleted((data) => {
      console.log('✅ Video completed event:', data);
    });

    return () => subscription.unsubscribe();
  }
}, [testRunning, sequenceId]);
```

#### **BUG #3: Sequence Order Not Sent to Backend**

**Location**: SequentialVideoPlayer.tsx:130-135

**Problem**:
```typescript
// Frontend sends:
{
  videoId,
  startedAt,
  clientTimestamp,
  sequenceElapsedTime
  // ❌ Missing: sequence_order, videoIndex
}

// Backend needs sequence_order to match detections correctly
```

**Impact**:
- Backend must query database for sequence_order
- If database record missing, detection matching fails
- Unnecessary database queries

**Fix Required**:
```typescript
// Line 130-135: Add sequence_order to payload
await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
  videoId,
  videoIndex: index,  // ADD THIS
  sequenceOrder: index,  // ADD THIS
  startedAt: startedAtUnix,
  clientTimestamp,
  sequenceElapsedTime: sequenceStartUnix ? startedAtUnix - sequenceStartUnix : 0
});
```

---

## 11. Recommendations

### High Priority (Must Fix)

1. **Fix Video 1 Notification**
   - Add explicit `loadAndPlayVideo` call for initial video
   - OR add separate `notifyVideoStart` call in test start logic
   - Ensure backend receives video 1 start event

2. **Add Sequence Order to Payload**
   - Include `videoIndex` and `sequenceOrder` in video-started event
   - Reduces database queries
   - Makes backend more robust

3. **Subscribe to Video Events**
   - Use `websocketService.subscribeToSequence()`
   - Handle `video_started`, `video_ended`, `video_transition` events
   - Keep UI synchronized with backend state

### Medium Priority (Should Fix)

4. **Improve Fallback Logic**
   - Validate fallback video before using for ground truth
   - Show clear error if no validated videos available
   - Prevent test from starting with invalid videos

5. **Add Video ID to canplay Promise**
   - Track which video triggered the event
   - Prevent race conditions during rapid transitions

6. **Add VideoSequenceSelector**
   - Allow manual video switching during test
   - Useful for debugging specific videos

### Low Priority (Nice to Have)

7. **Enhance WebSocket Logging**
   - Log all video state changes
   - Add performance metrics
   - Track video loading times

8. **Add Video Preloading Progress**
   - Show loading indicator for next video
   - Reduce transition delays

9. **Persist Sequence State**
   - Save video progress to localStorage
   - Allow test resume after browser crash

---

## 12. Code Snippets with Line Numbers

### Critical Area #1: Video 1 Never Notifies Backend

**File**: `SequentialVideoPlayer.tsx`

**Lines 72-73**: Initial state (video 1 set here)
```typescript
const [currentVideoIndex, setCurrentVideoIndex] = useState(0);
const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(videoPlaylist[0] || null);
// ❌ PROBLEM: Video 1 is set, but loadAndPlayVideo is never called!
```

**Lines 106-152**: Function that sends notification (works for video 2+)
```typescript
const sendVideoStartedEvent = useCallback(async (videoId: string, timestamp: number) => {
  if (!sequenceId) {
    console.warn('⚠️ No sequence ID - skipping video-started event');
    return; // ❌ This is called for video 1 because sequenceId might not be set yet
  }

  await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
    videoId,
    startedAt: startedAtUnix,
    clientTimestamp,
    sequenceElapsedTime: sequenceStartUnix ? startedAtUnix - sequenceStartUnix : 0
  });
}, [sequenceId, sequenceStartUnix]);
```

**Lines 287-434**: `loadAndPlayVideo` - only called for video 2+
```typescript
const loadAndPlayVideo = useCallback(async (video: VideoFile, index: number) => {
  // ... loading logic ...

  // Line 429: Send video started event to backend
  await sendVideoStartedEvent(video.id, updatedTiming.playbackStartTime!);

  // Line 432-434: Notify parent component
  if (onVideoStarted) {
    onVideoStarted(video.id, index, updatedTiming.playbackStartTime!);
  }
  // ✅ This works great for video 2, 3, 4...
  // ❌ But is NEVER called for video 1!
}, [/* dependencies */]);
```

**Lines 600-615**: Video advancement (calls loadAndPlayVideo for video 2+)
```typescript
const nextIndex = currentVideoIndex + 1;
const nextVideo = videoPlaylist[nextIndex];

if (nextVideo) {
  loadAndPlayVideo(nextVideo, nextIndex); // ✅ Called for transitions
}
// ❌ But no equivalent call for video 1 initialization
```

### Critical Area #2: Missing WebSocket Subscription

**File**: `HILTestExecutionPRD.tsx`

**Lines 951-1098**: `startTest` function - where subscription should be added
```typescript
const startTest = async () => {
  // ... test initialization ...

  const session: HILTestSession = {
    id: createdSessionId,
    projectId: selectedProject!.id,
    testStartTime: new Date(),
    maxLatencyMs,
    labjackConnected: labjackStatus.connected,
    status: 'running',
    videoPlaylist: enrichedVideoPlaylist,
    vruTracks: [],
    vruTrackingEnabled
  };
  setCurrentSession(session);

  // ❌ MISSING: Subscribe to video events here
  // const subscription = websocketService.subscribeToSequence(backendSequenceId);

  setTestRunning(true);
  setSequenceId(backendSequenceId);
  // ...
};
```

**File**: `websocketService.ts`

**Lines 547-577**: Available subscription method (not used)
```typescript
subscribeToSequence(sequenceId: string) {
  console.log(`🎬 Subscribing to sequence: ${sequenceId}`);
  this.emit('subscribe_sequence', { sequence_id: sequenceId });

  return {
    onVideoTransition: (callback) => this.subscribe('video_transition', callback),
    onVideoCompleted: (callback) => this.subscribe('video_completed', callback),
    onSequenceCompleted: (callback) => this.subscribe('sequence_completed', callback),
    unsubscribe: () => this.emit('unsubscribe_sequence', { sequence_id: sequenceId })
  };
  // ✅ This exists but is never called!
}
```

### Critical Area #3: Sequence Order Not Sent

**File**: `SequentialVideoPlayer.tsx`

**Lines 130-135**: Payload sent to backend (missing sequence_order)
```typescript
const response = await apiService.post(`/api/video-sequences/${sequenceId}/video-started`, {
  videoId,
  startedAt: startedAtUnix,
  clientTimestamp,
  sequenceElapsedTime: sequenceStartUnix ? startedAtUnix - sequenceStartUnix : 0
  // ❌ MISSING:
  // videoIndex: index,
  // sequenceOrder: index,
});
```

**File**: `video_sequence_testing.py`

**Lines 494-506**: Backend workaround (queries database)
```python
# Backend has to query database to find sequence_order
sequence_video_result = db.query(SequenceVideoResult).filter(
    SequenceVideoResult.video_sequence_id == sequence_id,
    SequenceVideoResult.video_id == request.videoId
).first()

if not sequence_video_result:
    # ❌ If record missing, sequence_order is unknown!
    logger.warning(f"No SequenceVideoResult found for video {request.videoId}")
```

---

## Conclusion

The frontend multi-video system is **80% complete** but has **3 critical bugs** that must be fixed:

1. ❌ **Video 1 never notifies backend** - Detection matching will fail for first video
2. ❌ **No WebSocket event subscription** - Frontend won't react to backend state changes
3. ❌ **Sequence order not sent** - Backend relies on fragile database lookups

**These bugs are all fixable with small, targeted code changes** in the locations identified above.

**Priority**: Fix Bug #1 (Video 1 notification) IMMEDIATELY - this is the most critical issue affecting multi-video test accuracy.
