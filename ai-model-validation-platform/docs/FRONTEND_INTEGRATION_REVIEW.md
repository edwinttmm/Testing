# Frontend Integration Review - HIL Results Display

## Executive Summary

**Date**: 2025-10-29
**Reviewer**: Code Review Agent
**Focus**: Frontend data flow from API to UI for HIL results display

### Critical Findings

1. **Session ID Correctly Used**: Session ID is properly extracted from URL params and passed to all API calls
2. **Multi-Video Sequence Detection Working**: Code properly detects sequence sessions and loads appropriate results
3. **Ground Truth Integration Present**: Ground truth events loaded separately per video
4. **Type Safety Issues**: Several `any` type casts bypass TypeScript safety
5. **Data Flow Complexity**: Multiple fallback paths create debugging challenges

---

## 1. Data Flow Analysis

### API → State → UI Path

```
URL Route (/results/:sessionId)
    ↓
useParams() extracts sessionId
    ↓
useEffect() triggers data loading
    ↓
loadEnhancedHILResults() OR loadVideoSequenceResults()
    ↓
apiService.getEnhancedHILResultsWithGroundTruth(sessionId)
    ↓
setEnhancedResults(data) → State Update
    ↓
Components re-render with new data
    ↓
FrameCorrelationTimeline receives detectionEvents and groundTruthEvents
```

### Session ID Usage Verification ✅

**HILResults.tsx Line 72**:
```typescript
const { sessionId } = useParams<{ sessionId: string }>();
```

**All API Calls Use Correct Session ID**:
- Line 173: `apiService.getEnhancedHILResultsWithGroundTruth(sessionId)` ✅
- Line 178: `apiService.getEnhancedHILResults(sessionId)` ✅
- Line 187: `apiService.getTestSession(sessionId)` ✅
- Line 748: `apiService.checkIfSessionIsSequence(sessionId)` ✅
- Line 755: `apiService.getVideoSequenceResults(sessionId)` ✅

**Verdict**: Session ID is correctly passed to all backend API calls.

---

## 2. Multi-Video Sequence Handling

### Sequence Detection Logic (Lines 191-234)

```typescript
// Check if this is a multi-video sequence session
const hasSequence = (sess as any).has_video_sequence || (sess as any).hasVideoSequence;
const sequenceMetadata = (sess as any).sequence_metadata || (sess as any).sequenceMetadata;

if (hasSequence && sequenceMetadata) {
  // Parse video_ids from sequence_metadata
  const metadata = typeof sequenceMetadata === 'string'
    ? JSON.parse(sequenceMetadata)
    : sequenceMetadata;
  const videoIds = metadata.video_ids || metadata.videoIds || [];

  // Load all sequence videos
  const videos = await Promise.all(
    videoIds.map(async (vid: string, idx: number) => {
      const videoData = await apiService.getVideo(vid);
      return {
        id: vid,
        filename: videoData.filename || `Video ${idx + 1}`,
        sequence_order: idx
      };
    })
  );

  setSequenceVideos(videos);
  setSelectedVideoId(videoIds[0]);
  setVideoId(videoIds[0]);
  await loadGroundTruthData(videoIds[0]);
}
```

**Issues Found**:
1. ❌ **Type Safety**: Uses `(sess as any)` - bypasses TypeScript checking
2. ⚠️ **Dual Naming**: Checks both `has_video_sequence` and `hasVideoSequence` (camelCase vs snake_case inconsistency)
3. ⚠️ **JSON Parsing**: `sequence_metadata` might be string or object - handled but fragile

**Recommendation**: Define proper TypeScript interfaces for session response:
```typescript
interface TestSessionResponse {
  has_video_sequence?: boolean;
  sequence_metadata?: {
    video_ids: string[];
    total_duration_ms?: number;
  };
  video_id?: string;
}
```

---

## 3. Ground Truth Data Loading

### Video-Specific Ground Truth (Lines 130-150)

```typescript
const loadGroundTruthData = async (videoId: string) => {
  try {
    console.log(`🔍 Loading ground truth data for video: ${videoId}`);
    const groundTruthResponse = await apiService.getGroundTruthEvents(videoId);

    if (groundTruthResponse?.success && groundTruthResponse?.data?.ground_truth_events) {
      const gtEvents = groundTruthResponse.data.ground_truth_events;
      console.log(`✅ Loaded ${gtEvents.length} ground truth events`);
      setGroundTruthEvents(gtEvents);
      return gtEvents;
    } else {
      console.log('⚠️ No ground truth data available for this video');
      setGroundTruthEvents([]);
      return [];
    }
  } catch (error) {
    console.warn('Failed to load ground truth data:', error);
    setGroundTruthEvents([]);
    return [];
  }
};
```

**Analysis**:
- ✅ Proper error handling (catch block prevents crashes)
- ✅ Defensive null checking (`?.success`, `?.data`)
- ⚠️ **Silent Failures**: Errors logged but not shown to user
- ⚠️ **State Race Condition**: Multiple calls could overwrite each other

**Recommendation**: Add loading state and error display:
```typescript
const [groundTruthLoading, setGroundTruthLoading] = useState(false);
const [groundTruthError, setGroundTruthError] = useState<string | null>(null);

// In loadGroundTruthData:
setGroundTruthLoading(true);
setGroundTruthError(null);
try {
  // ... existing code
} catch (error) {
  setGroundTruthError('Failed to load ground truth data');
  // Show error to user in UI
} finally {
  setGroundTruthLoading(false);
}
```

---

## 4. Detection Events Processing

### Video-Relative Timestamp Normalization (Lines 284-318)

```typescript
detection_events: (((enhancedData as any).detection_events) || []).map((event: any, idx: number) => {
  const fps = (enhancedData as any).video_timing?.fps || 24;
  const rawFrame = event.video_frame_number ?? event.frame_number ?? 0;
  const frame_number = Number.isFinite(rawFrame) ? Number(rawFrame) : 0;
  const timestamp = frame_number > 0 ? (frame_number / fps) : 0; // seconds relative to video

  return {
    id: event.event_id,
    timestamp, // IMPORTANT: video-relative seconds
    frame_number,
    video_frame_number: frame_number,
    detection_time_ms: event.actualLatencyMs || event.actual_latency_ms,
    voltage: event.voltage_level,
    // ... more fields
  };
})
```

**Critical Analysis**:
1. ✅ **Timestamp Normalization**: Converts frame numbers to video-relative seconds
2. ✅ **Defensive Coding**: Handles missing frame numbers, defaults to 0
3. ✅ **FPS Fallback**: Defaults to 24 FPS if not provided
4. ❌ **Type Casts**: `(enhancedData as any)` bypasses all type checking
5. ⚠️ **Dual Field Names**: Checks both `actualLatencyMs` and `actual_latency_ms`

**Potential Bug**: If `frame_number` is 0 (first frame), timestamp becomes 0, which is correct. But if frame_number is legitimately missing (undefined), it also becomes 0 - can't distinguish between "first frame" and "missing data".

**Recommendation**:
```typescript
const frame_number = event.video_frame_number ?? event.frame_number;
if (frame_number === null || frame_number === undefined) {
  console.warn(`Missing frame number for event ${event.event_id}`);
  // Either skip this event or use index-based fallback
}
const timestamp = frame_number !== null ? (frame_number / fps) : null;
```

---

## 5. FrameCorrelationTimeline Component

### Event Correlation Logic (Lines 88-194)

**Input Data**:
```typescript
<FrameCorrelationTimeline
  detectionEvents={detectionEvents}  // From enhancedResults
  groundTruthEvents={groundTruthEvents}  // Loaded separately
  videoMetadata={{
    fps: enhancedResults?.video_timing?.fps,
    duration: enhancedResults?.video_timing?.duration,
    filename: enhancedResults?.video_timing?.filename
  }}
/>
```

**Correlation Algorithm** (Lines 129-169):
```typescript
detectionEvents.forEach((det: any) => {
  const detectionFrameNumber = clampFrame(Number(det.video_frame_number ?? det.frame_number ?? 0));
  const videoTimeSeconds = detectionFrameNumber > 0 ? (detectionFrameNumber / fps) : 0;

  // Find closest ground truth event
  let closestGT = null;
  let minTimeDiff = Infinity;

  groundTruthEvents.forEach((gt: any) => {
    const gtFrame = gt.video_frame || gt.frame_number || 0;
    const frameDiff = Math.abs(detectionFrameNumber - gtFrame);
    const timeDiff = Math.abs(videoTimeSeconds - (gt.timestamp || 0));

    if (timeDiff < minTimeDiff) {
      minTimeDiff = timeDiff;
      closestGT = gt;
    }
  });

  // Determine correlation status
  if (closestGT) {
    const frameOffsetFrames = Math.abs(detectionFrameNumber - closestGTFrame);
    frameOffsetMs = (frameOffsetFrames / fps) * 1000;

    if (frameOffsetMs <= (1000 / fps) * 2) {
      correlationStatus = 'aligned';  // Within 2 frames
    } else if (frameOffsetMs <= (1000 / fps) * 5) {
      correlationStatus = 'misaligned';  // Within 5 frames
    }
  }
});
```

**Analysis**:
- ✅ Correlation algorithm is sound
- ✅ Uses both frame-based and time-based matching
- ✅ Classifies alignment quality (aligned/misaligned/missing)
- ⚠️ **Performance**: O(n×m) complexity for n detections × m ground truth events
- ⚠️ **Type Safety**: `det: any` and `gt: any` bypass type checking

**Potential Issue**: If ground truth timestamp is in epoch seconds but detection timestamp is in video-relative seconds, the `timeDiff` calculation will be wrong.

---

## 6. Video Selector for Sequences

### Dropdown Handler (Lines 153-159)

```typescript
const handleVideoChange = async (event: any) => {
  const newVideoId = event.target.value;
  console.log(`🎬 Switching to video: ${newVideoId}`);
  setSelectedVideoId(newVideoId);
  setVideoId(newVideoId);
  await loadGroundTruthData(newVideoId);
};
```

**Rendering** (Lines 1240-1265):
```typescript
{isSequence && sequenceVideos.length > 0 && (
  <FormControl fullWidth>
    <InputLabel>Select Video</InputLabel>
    <Select
      value={selectedVideoId || ''}
      onChange={handleVideoChange}
    >
      {sequenceVideos.map((video) => (
        <MenuItem key={video.id} value={video.id}>
          Video {video.sequence_order + 1}: {video.filename}
        </MenuItem>
      ))}
    </Select>
  </FormControl>
)}
```

**Analysis**:
- ✅ Video selector only shown when `isSequence` is true
- ✅ Properly iterates through `sequenceVideos` array
- ✅ Uses video ID as key and value
- ⚠️ **State Update Race**: `setSelectedVideoId` and `setVideoId` might not execute atomically
- ⚠️ **Async Loading**: Ground truth loads asynchronously - UI doesn't show loading state

**Recommendation**: Show loading spinner while ground truth loads:
```typescript
const [isLoadingVideo, setIsLoadingVideo] = useState(false);

const handleVideoChange = async (event: any) => {
  const newVideoId = event.target.value;
  setIsLoadingVideo(true);
  try {
    setSelectedVideoId(newVideoId);
    setVideoId(newVideoId);
    await loadGroundTruthData(newVideoId);
  } finally {
    setIsLoadingVideo(false);
  }
};

// In render:
{isLoadingVideo && <CircularProgress />}
```

---

## 7. WebSocket Integration

### Connection Setup (websocketService.ts Lines 541-571)

```typescript
subscribeToSequence(sequenceId: string) {
  if (!sequenceId) {
    console.error('❌ Cannot subscribe to sequence: sequenceId is required');
    return null;
  }

  console.log(`🎬 Subscribing to sequence: ${sequenceId}`);
  this.emit('subscribe_sequence', { sequence_id: sequenceId });

  return {
    onVideoTransition: (callback: (data: unknown) => void) => {
      return this.subscribe('video_transition', callback);
    },
    onVideoCompleted: (callback: (data: unknown) => void) => {
      return this.subscribe('video_completed', callback);
    },
    onSequenceCompleted: (callback: (data: unknown) => void) => {
      return this.subscribe('sequence_completed', callback);
    },
    unsubscribe: () => {
      this.emit('unsubscribe_sequence', { sequence_id: sequenceId });
    }
  };
}
```

**Analysis**:
- ✅ Proper null check for sequenceId
- ✅ Emits subscription request to backend
- ✅ Provides event handlers for video transitions
- ❌ **Not Used in HILResults.tsx**: WebSocket integration code exists but is not actually used in the HIL Results page
- ⚠️ **Missing Real-Time Updates**: Detection events are not updated via WebSocket during test execution

**Recommendation**: Add WebSocket subscription in HILResults.tsx:
```typescript
useEffect(() => {
  if (!sessionId || !isSequence) return;

  const sequenceSubscription = websocketService.subscribeToSequence(sessionId);
  if (!sequenceSubscription) return;

  const unsubTransition = sequenceSubscription.onVideoTransition((data) => {
    console.log('Video transition:', data);
    // Update UI to show which video is currently playing
  });

  const unsubCompleted = sequenceSubscription.onVideoCompleted((data) => {
    console.log('Video completed:', data);
    // Refresh detection events for completed video
  });

  return () => {
    unsubTransition();
    unsubCompleted();
    sequenceSubscription.unsubscribe();
  };
}, [sessionId, isSequence]);
```

---

## 8. Type Safety Issues

### Critical Type Casts Found

1. **Line 76**: `setEnhancedResults<EnhancedHILResults | null>(null)` ✅ (typed)
2. **Line 187**: `const sess = await apiService.getTestSession(sessionId);` ❌ (returns `any`)
3. **Line 191**: `const sessVideoId = (sess as any).video_id` ❌ (bypasses types)
4. **Line 260**: `const compatHIL: HILTestResults = { ... }` ✅ (typed conversion)
5. **Line 284**: `detection_events: (((enhancedData as any).detection_events) || [])` ❌ (double cast)

**Impact**: Type casts bypass TypeScript's safety checks, allowing:
- Accessing non-existent properties without compile-time errors
- Passing wrong data shapes to components
- Runtime errors that could have been caught during development

**Recommendation**: Define proper response interfaces:
```typescript
interface EnhancedHILResultsResponse {
  session_id: string;
  hardware_status: {
    labjack_connected: boolean;
    model: string;
  };
  video_timing: {
    fps?: number;
    duration?: number;
    filename?: string;
    startup_delay_ms: number;
    timing_sync_status: string;
    timing_accuracy_ns: number | null;
  };
  detection_events: Array<{
    event_id: string;
    frame_number: number;
    video_frame_number?: number;
    actualLatencyMs?: number;
    actual_latency_ms?: number;
    voltage_level: number;
    result: 'pass' | 'fail';
  }>;
  session_info?: {
    project_name?: string;
    name?: string;
    duration_seconds?: number;
    status?: string;
  };
}

// Then use:
const enhancedData: EnhancedHILResultsResponse = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);
```

---

## 9. Error Handling Analysis

### Fallback Chain (Lines 162-370)

```
Try: getEnhancedHILResultsWithGroundTruth(sessionId)
  ↓ (on error)
Fallback 1: getEnhancedHILResults(sessionId)
  ↓ (on error)
Fallback 2: loadHILResults() [legacy method]
  ↓ (on error)
Fallback 3: createDemoHILResults(sessionId) [demo data]
```

**Analysis**:
- ✅ Comprehensive fallback chain prevents blank screen
- ✅ Error logging at each stage
- ⚠️ **Silent Degradation**: User sees results but might not know they're using fallback data
- ⚠️ **Demo Data Confusion**: `createDemoHILResults()` creates fake data - user can't tell it's not real

**Recommendation**: Show warning banner when using fallback/demo data:
```typescript
const [dataSource, setDataSource] = useState<'live' | 'enhanced' | 'legacy' | 'demo'>('live');

// In UI:
{dataSource === 'demo' && (
  <Alert severity="warning">
    Displaying demo data - actual test results not available
  </Alert>
)}
{dataSource === 'legacy' && (
  <Alert severity="info">
    Displaying legacy format results (enhanced data unavailable)
  </Alert>
)}
```

---

## 10. State Management Review

### State Variables (Lines 75-93)

```typescript
const [hil, setHil] = useState<HILTestResults | null>(null);
const [enhancedResults, setEnhancedResults] = useState<EnhancedHILResults | null>(null);
const [sequenceResults, setSequenceResults] = useState<VideoSequenceResults | null>(null);
const [isSequence, setIsSequence] = useState(false);
const [groundTruthEvents, setGroundTruthEvents] = useState<any[]>([]);
const [videoId, setVideoId] = useState<string | null>(null);
const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
const [sequenceVideos, setSequenceVideos] = useState<any[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
```

**Issues**:
1. ⚠️ **Redundant State**: Both `hil` and `enhancedResults` store similar data
2. ⚠️ **Dual Video ID**: Both `videoId` and `selectedVideoId` track current video
3. ❌ **Untyped Arrays**: `groundTruthEvents` and `sequenceVideos` use `any[]`
4. ⚠️ **Missing Derived State**: Some values could be computed from existing state

**Recommendation**: Consolidate state:
```typescript
// Remove redundant hil state, use only enhancedResults
const [results, setResults] = useState<EnhancedHILResults | VideoSequenceResults | null>(null);
const [currentVideoId, setCurrentVideoId] = useState<string | null>(null);
const [groundTruthEvents, setGroundTruthEvents] = useState<GroundTruthEvent[]>([]);
const [sequenceVideos, setSequenceVideos] = useState<VideoInfo[]>([]);

// Derive isSequence from results:
const isSequence = 'sequence_summary' in (results ?? {});
```

---

## 11. API Response Parsing

### Detection Event Mapping (Lines 284-318)

**Field Name Inconsistencies**:
```typescript
detection_time_ms: event.actualLatencyMs || event.actual_latency_ms
real_latency_ms: event.actualLatencyMs || event.actual_latency_ms
voltage: event.voltage_level
frame_number: event.video_frame_number ?? event.frame_number ?? 0
```

**Backend Field Variations Handled**:
- ✅ `actualLatencyMs` OR `actual_latency_ms`
- ✅ `video_frame_number` OR `frame_number`
- ✅ `voltage_level` mapped to `voltage`

**Issue**: This suggests backend is sending inconsistent field names (camelCase vs snake_case). Frontend compensates but it's fragile.

**Recommendation**: Standardize backend serialization:
```python
# Backend should use consistent camelCase via Pydantic
class DetectionEvent(BaseModel):
    eventId: str
    frameNumber: int
    videoFrameNumber: Optional[int]
    actualLatencyMs: float
    voltageLevel: float

    class Config:
        alias_generator = to_camel
        populate_by_name = True
```

---

## 12. Critical Bugs Found

### Bug #1: Timestamp Unit Mismatch Potential

**Location**: FrameCorrelationTimeline.tsx Lines 129-169

**Issue**: Ground truth timestamps from database might be in epoch seconds, while detection timestamps are converted to video-relative seconds. The correlation algorithm compares them directly:

```typescript
const timeDiff = Math.abs(videoTimeSeconds - (gt.timestamp || 0));
```

If `gt.timestamp` is epoch seconds (e.g., 1730217600) and `videoTimeSeconds` is relative (e.g., 2.5), the `timeDiff` will be enormous, and no events will correlate.

**Impact**: HIGH - All detections would show as "missing" correlation

**Test**:
```typescript
console.log('GT timestamp:', groundTruthEvents[0]?.timestamp);
console.log('Detection timestamp:', detectionEvents[0]?.timestamp);
// If GT is > 1000000, it's epoch; if detection is < 1000, it's relative
```

**Fix**: Normalize timestamps before correlation:
```typescript
const gtTimeSeconds = gt.video_frame > 0
  ? (gt.video_frame / fps)  // Calculate from frame number
  : (gt.timestamp > 100000 ? gt.timestamp / 1000 : gt.timestamp);  // Handle epoch ms or relative
```

---

### Bug #2: Video Selector State Race Condition

**Location**: Lines 153-159

**Issue**: When switching videos, three state updates happen sequentially:
```typescript
setSelectedVideoId(newVideoId);
setVideoId(newVideoId);
await loadGroundTruthData(newVideoId);
```

If `loadGroundTruthData` takes time, and user switches videos again quickly, ground truth for the first video might load after switching to the second video.

**Impact**: MEDIUM - Ground truth for wrong video might be displayed

**Fix**: Use abort controller:
```typescript
const abortControllerRef = useRef<AbortController | null>(null);

const handleVideoChange = async (event: any) => {
  // Abort previous request
  abortControllerRef.current?.abort();
  abortControllerRef.current = new AbortController();

  const newVideoId = event.target.value;
  setSelectedVideoId(newVideoId);
  setVideoId(newVideoId);

  try {
    await loadGroundTruthData(newVideoId, abortControllerRef.current.signal);
  } catch (error) {
    if (error.name !== 'AbortError') {
      console.error('Failed to load ground truth:', error);
    }
  }
};
```

---

### Bug #3: Missing Null Checks in FrameCorrelationTimeline

**Location**: FrameCorrelationTimeline.tsx Lines 76-78

```typescript
const fps = videoMetadata?.fps || 24;
const duration = videoMetadata?.duration ?? undefined;
const totalFrames = typeof duration === 'number' && Number.isFinite(duration)
  ? Math.max(0, Math.round(duration * fps))
  : undefined;
```

**Issue**: If `videoMetadata.fps` is 0 (falsy), defaults to 24. But what if FPS is legitimately 0 or missing? All frame-to-time calculations will be wrong.

**Impact**: MEDIUM - Incorrect timeline display if FPS is missing

**Fix**:
```typescript
const fps = videoMetadata?.fps ?? 24;  // Use nullish coalescing
if (!fps || fps <= 0) {
  console.warn('Invalid FPS, defaulting to 24');
  fps = 24;
}
```

---

## 13. UI Bug Analysis

### Missing Detection Events Display

**Potential Causes**:

1. **Empty Detection Events Array**:
   - Check if `enhancedResults.detection_events` is empty
   - Verify backend is returning events for the session

2. **Type Mismatch Filtering**:
   - Line 284: `(((enhancedData as any).detection_events) || [])`
   - If field name is wrong (e.g., `detectionEvents` vs `detection_events`), array defaults to empty

3. **Timestamp Filtering**:
   - Detection events with invalid timestamps (0, null, undefined) might be filtered out
   - Check if `showFailuresOnly` filter is active (Line 85)

4. **Video Selector Mismatch**:
   - If sequence has multiple videos, events might be loaded for wrong video ID
   - Check if `selectedVideoId` matches the session's video

**Debug Steps**:
```typescript
// Add console.logs in loadEnhancedHILResults (after line 182):
console.log('📊 Enhanced Results:', {
  sessionId: enhancedData.session_id,
  detectionEventsCount: enhancedData.detection_events?.length,
  firstEvent: enhancedData.detection_events?.[0],
  videoTiming: enhancedData.video_timing,
  sessionInfo: enhancedData.session_info
});

// In render (before passing to FrameCorrelationTimeline):
console.log('📊 Passing to FrameCorrelationTimeline:', {
  detectionEventsCount: detectionEvents.length,
  groundTruthEventsCount: groundTruthEvents.length,
  firstDetection: detectionEvents[0],
  firstGroundTruth: groundTruthEvents[0]
});
```

---

## 14. Performance Issues

### O(n×m) Correlation Algorithm

**Location**: FrameCorrelationTimeline.tsx Lines 129-146

```typescript
detectionEvents.forEach((det) => {  // n iterations
  groundTruthEvents.forEach((gt) => {  // m iterations
    // Find closest match
  });
});
```

**Complexity**: O(n×m) where n = detections, m = ground truth events

**Impact**: If n = 1000, m = 500, that's 500,000 iterations - could cause UI lag

**Optimization**:
```typescript
// Pre-sort ground truth by timestamp for binary search
const sortedGT = groundTruthEvents.sort((a, b) => a.timestamp - b.timestamp);

detectionEvents.forEach((det) => {
  // Binary search for closest GT (O(log m) instead of O(m))
  const closestGT = binarySearchClosest(sortedGT, det.timestamp);
  // ... rest of logic
});

// Complexity: O(n log m) - much better for large datasets
```

---

## 15. Recommended Fixes (Prioritized)

### Priority 1: Critical Bugs

1. **Timestamp Normalization** (Bug #1)
   - Ensure ground truth and detection timestamps use same units
   - Convert epoch to video-relative or vice versa consistently

2. **Type Safety** (Bug #8)
   - Define TypeScript interfaces for all API responses
   - Remove all `as any` casts
   - Enable strict null checks

3. **Video Selector Race Condition** (Bug #2)
   - Add abort controller to prevent wrong ground truth loading
   - Show loading spinner during video switch

### Priority 2: User Experience

4. **Loading States**
   - Show spinner while ground truth loads
   - Indicate when fallback/demo data is used
   - Add "No data" empty state messages

5. **Error Visibility**
   - Display ground truth loading errors to user
   - Show warning when enhanced results unavailable
   - Add retry button for failed API calls

### Priority 3: Code Quality

6. **State Consolidation**
   - Remove redundant state variables
   - Use derived state where possible
   - Standardize naming (camelCase)

7. **Performance Optimization**
   - Implement binary search for event correlation
   - Memoize expensive computations
   - Use React.memo for component re-renders

### Priority 4: Features

8. **WebSocket Integration**
   - Add real-time updates during test execution
   - Show live progress for multi-video sequences
   - Display current video in sequence

9. **Enhanced Debugging**
   - Add developer mode with detailed logs
   - Export timing data for analysis
   - Show data source indicator (enhanced/legacy/demo)

---

## 16. Conclusion

### What's Working ✅

1. Session ID correctly passed to all API endpoints
2. Multi-video sequence detection and handling implemented
3. Ground truth data loaded separately per video
4. Video selector dropdown functions properly
5. Comprehensive fallback chain prevents crashes
6. Detection event normalization to video-relative time

### What's Broken ❌

1. Timestamp unit mismatch between ground truth and detections (HIGH)
2. Type safety completely bypassed with `any` casts (HIGH)
3. Video selector state race condition (MEDIUM)
4. Missing null checks for FPS and duration (MEDIUM)
5. WebSocket integration not actually used (LOW)
6. O(n×m) correlation algorithm (LOW for small datasets)

### Root Cause of Missing Detections

**Most Likely**: Backend is not returning detection events, OR they're being filtered out due to:
- Invalid timestamps (null/undefined/0)
- Wrong field names (camelCase vs snake_case mismatch)
- Session ID doesn't have associated detections in database
- Video ID mismatch in sequence scenarios

**Debugging Strategy**:
1. Add console.log in `loadEnhancedHILResults` after API call (line 174)
2. Log raw response: `console.log('Raw API response:', enhancedData)`
3. Check `enhancedData.detection_events` array length
4. If empty, backend issue; if populated but not displayed, frontend filtering issue

---

## Appendix A: Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         URL Route                            │
│                  /results/:sessionId                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    useParams() Hook                          │
│                  Extracts sessionId                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   useEffect Trigger                          │
│         Detects sessionId change, starts load                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              checkIfSessionIsSequence(sessionId)             │
│                 Returns: true/false                          │
└─────────────┬───────────────────────────────┬───────────────┘
              │                               │
         true │                               │ false
              ▼                               ▼
┌──────────────────────────┐    ┌────────────────────────────┐
│ loadVideoSequenceResults │    │ loadEnhancedHILResults     │
│                          │    │                            │
│ - Fetches sequence data  │    │ - Fetches single session   │
│ - Loads per-video results│    │ - Loads detection events   │
│ - Gets video list        │    │ - Loads ground truth       │
└────────┬─────────────────┘    └─────────┬──────────────────┘
         │                                 │
         ▼                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                   State Updates                              │
│  - setSequenceResults() OR setEnhancedResults()              │
│  - setGroundTruthEvents()                                    │
│  - setSequenceVideos() (if sequence)                         │
│  - setIsSequence()                                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Component Re-render                         │
│                                                              │
│  ┌────────────────────────────────────────────────┐         │
│  │  Video Selector Dropdown (if sequence)         │         │
│  │  - Shows list of videos in sequence            │         │
│  │  - onChange → loadGroundTruthData(newVideoId)  │         │
│  └────────────────────────────────────────────────┘         │
│                                                              │
│  ┌────────────────────────────────────────────────┐         │
│  │  FrameCorrelationTimeline Component            │         │
│  │  - Receives detectionEvents array              │         │
│  │  - Receives groundTruthEvents array            │         │
│  │  - Correlates events by timestamp/frame        │         │
│  │  - Displays timeline visualization             │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Critical Code Paths

### Path 1: Single Video Session

```
sessionId = "abc-123"
  ↓
checkIfSessionIsSequence("abc-123") → false
  ↓
loadEnhancedHILResults()
  ↓
apiService.getEnhancedHILResultsWithGroundTruth("abc-123")
  ↓
Response: { session_id, detection_events: [...], video_timing: {...} }
  ↓
getTestSession("abc-123")
  ↓
Response: { video_id: "video-456" }
  ↓
loadGroundTruthData("video-456")
  ↓
apiService.getGroundTruthEvents("video-456")
  ↓
Response: { success: true, data: { ground_truth_events: [...] } }
  ↓
setGroundTruthEvents([...])
  ↓
FrameCorrelationTimeline renders with both arrays
```

### Path 2: Multi-Video Sequence

```
sessionId = "seq-789"
  ↓
checkIfSessionIsSequence("seq-789") → true
  ↓
loadVideoSequenceResults()
  ↓
apiService.getVideoSequenceResults("seq-789")
  ↓
Response: {
  session_id,
  sequence_summary: {...},
  per_video_results: [
    { video_id: "vid-1", detection_events: [...] },
    { video_id: "vid-2", detection_events: [...] }
  ]
}
  ↓
getTestSession("seq-789")
  ↓
Response: {
  has_video_sequence: true,
  sequence_metadata: { video_ids: ["vid-1", "vid-2"] }
}
  ↓
Load both videos: getVideo("vid-1"), getVideo("vid-2")
  ↓
setSequenceVideos([{id: "vid-1", filename: "..."}, ...])
  ↓
setSelectedVideoId("vid-1")  // Default to first
  ↓
loadGroundTruthData("vid-1")
  ↓
Video Selector shows dropdown
  ↓
User selects "vid-2"
  ↓
handleVideoChange("vid-2")
  ↓
setSelectedVideoId("vid-2")
  ↓
loadGroundTruthData("vid-2")
  ↓
FrameCorrelationTimeline re-renders with vid-2 data
```

---

**End of Report**
