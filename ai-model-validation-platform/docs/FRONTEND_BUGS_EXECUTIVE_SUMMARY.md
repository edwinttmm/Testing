# Frontend Integration Bugs - Executive Summary

**Date**: 2025-10-29
**Session**: HIL Results Display Issue Investigation
**Status**: 3 Critical Bugs Found, 5 Medium Issues Identified

---

## TL;DR: Why Detections Don't Display

### Most Likely Root Cause

**Timestamp Unit Mismatch** (Critical Bug #1)

Ground truth events from database use **epoch seconds** (e.g., 1730217600), while detection events are normalized to **video-relative seconds** (e.g., 2.5). The correlation algorithm in `FrameCorrelationTimeline.tsx` directly compares these incompatible units:

```typescript
// Line 141
const timeDiff = Math.abs(videoTimeSeconds - (gt.timestamp || 0));
```

When `gt.timestamp = 1730217600` and `videoTimeSeconds = 2.5`, the `timeDiff` is billions of milliseconds. No events correlate, so all detections appear as "missing" and may be filtered from display.

---

## Critical Bugs (Fix Immediately)

### Bug #1: Timestamp Unit Mismatch ⚠️ CRITICAL

**File**: `frontend/src/components/FrameCorrelationTimeline.tsx`
**Lines**: 104-169
**Severity**: HIGH

**Problem**:
- Ground truth timestamps: Epoch seconds from database
- Detection timestamps: Video-relative seconds (frame_number / fps)
- Correlation algorithm compares them directly → NO MATCHES

**Fix**:
```typescript
// Normalize ground truth to video-relative time
const gtTimeSeconds = gt.video_frame > 0
  ? (gt.video_frame / fps)  // Use frame number if available
  : (gt.timestamp > 100000 ? gt.timestamp - firstEventEpoch : gt.timestamp);  // Convert epoch to relative
```

**Verification**:
```bash
# Check if timestamps are compatible
console.log('GT timestamp:', groundTruthEvents[0]?.timestamp);  # Should be < 1000 for video-relative
console.log('Detection timestamp:', detectionEvents[0]?.timestamp);  # Should be < 1000
```

---

### Bug #2: Type Safety Completely Bypassed ❌ CRITICAL

**File**: `frontend/src/pages/HILResults.tsx`
**Lines**: 187, 191, 241, 284, 355
**Severity**: HIGH

**Problem**:
Extensive use of `as any` casts bypass all TypeScript safety:

```typescript
const sess = await apiService.getTestSession(sessionId);  // Returns any
const sessVideoId = (sess as any).video_id;  // No compile-time checking
detection_events: (((enhancedData as any).detection_events) || [])  // Double cast
```

**Impact**:
- Accessing non-existent properties → undefined
- Wrong field names (camelCase vs snake_case) → empty arrays
- Runtime errors that should be caught at compile-time

**Fix**:
```typescript
// Define proper interfaces
interface TestSessionResponse {
  id: string;
  video_id?: string;
  has_video_sequence?: boolean;
  sequence_metadata?: {
    video_ids: string[];
  };
}

const sess: TestSessionResponse = await apiService.getTestSession(sessionId);
const sessVideoId = sess.video_id;  // Type-safe access
```

---

### Bug #3: Video Selector Race Condition ⚠️ MEDIUM

**File**: `frontend/src/pages/HILResults.tsx`
**Lines**: 153-159
**Severity**: MEDIUM

**Problem**:
When user switches videos quickly, ground truth for Video A might load after user has switched to Video B, causing wrong data to display.

```typescript
const handleVideoChange = async (event: any) => {
  setSelectedVideoId(newVideoId);  // State update 1
  setVideoId(newVideoId);          // State update 2
  await loadGroundTruthData(newVideoId);  // Async - might complete late
};
```

**Fix**:
```typescript
const abortControllerRef = useRef<AbortController | null>(null);

const handleVideoChange = async (event: any) => {
  abortControllerRef.current?.abort();  // Cancel previous request
  abortControllerRef.current = new AbortController();

  const newVideoId = event.target.value;
  setSelectedVideoId(newVideoId);
  setVideoId(newVideoId);

  try {
    await loadGroundTruthData(newVideoId, abortControllerRef.current.signal);
  } catch (error) {
    if (error.name !== 'AbortError') throw error;
  }
};
```

---

## Medium Priority Issues

### Issue #1: Missing Null Checks for FPS

**File**: `FrameCorrelationTimeline.tsx`
**Line**: 76
**Impact**: If FPS is 0 or missing, all calculations wrong

```typescript
const fps = videoMetadata?.fps || 24;  // Wrong: 0 is falsy
// Should be:
const fps = videoMetadata?.fps ?? 24;  // Nullish coalescing
```

---

### Issue #2: Silent Error Handling

**File**: `HILResults.tsx`
**Lines**: 145-148
**Impact**: Users don't know when ground truth fails to load

**Current**:
```typescript
} catch (error) {
  console.warn('Failed to load ground truth data:', error);
  setGroundTruthEvents([]);  // Silent failure
}
```

**Should Be**:
```typescript
} catch (error) {
  console.error('Failed to load ground truth data:', error);
  setError('Ground truth data unavailable for this video');
  // Show error banner to user
}
```

---

### Issue #3: O(n×m) Correlation Algorithm

**File**: `FrameCorrelationTimeline.tsx`
**Lines**: 129-146
**Impact**: UI lag with large datasets (1000+ detections)

**Current**: O(n×m) nested loops
**Optimization**: O(n log m) with binary search

---

### Issue #4: WebSocket Integration Not Used

**File**: `websocketService.ts` has `subscribeToSequence()` method
**File**: `HILResults.tsx` doesn't use it
**Impact**: No real-time updates during test execution

---

### Issue #5: Redundant State Variables

**Impact**: Code complexity, potential bugs

```typescript
// Redundant state
const [hil, setHil] = useState<HILTestResults | null>(null);
const [enhancedResults, setEnhancedResults] = useState<EnhancedHILResults | null>(null);
// Both store similar data

// Redundant video tracking
const [videoId, setVideoId] = useState<string | null>(null);
const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
// Could be one variable
```

---

## Data Flow Verification ✅

### Session ID Usage: CORRECT

All API calls properly use `sessionId` from URL params:
- ✅ `getEnhancedHILResultsWithGroundTruth(sessionId)`
- ✅ `getTestSession(sessionId)`
- ✅ `checkIfSessionIsSequence(sessionId)`
- ✅ `getVideoSequenceResults(sessionId)`

### API Response Parsing: DEFENSIVE

Code handles multiple field name variations:
- ✅ `actualLatencyMs` OR `actual_latency_ms`
- ✅ `video_frame_number` OR `frame_number`
- ✅ `has_video_sequence` OR `hasVideoSequence`

This suggests backend inconsistency (camelCase vs snake_case).

### Multi-Video Sequence: FUNCTIONAL

Sequence detection and video selector work correctly:
- ✅ Parses `sequence_metadata.video_ids`
- ✅ Loads all videos in sequence
- ✅ Dropdown shows video list
- ✅ Ground truth loads per video

---

## Debugging Steps (In Order)

### Step 1: Verify Backend Returns Data

```bash
# Check API response
curl http://localhost:8000/api/test-sessions/{sessionId}/enhanced-hil-results

# Expected fields:
# - detection_events: Array (should have items)
# - video_timing.fps: Number
# - session_id: String matching URL param
```

### Step 2: Add Console Logs in Frontend

**In HILResults.tsx after line 174**:
```typescript
console.log('🔍 API Response:', {
  sessionId: enhancedData.session_id,
  detectionCount: enhancedData.detection_events?.length,
  firstDetection: enhancedData.detection_events?.[0],
  videoTiming: enhancedData.video_timing
});
```

**Before FrameCorrelationTimeline (line 2000+)**:
```typescript
console.log('📊 Timeline Props:', {
  detectionEvents: detectionEvents.length,
  groundTruthEvents: groundTruthEvents.length,
  firstDetection: detectionEvents[0],
  firstGT: groundTruthEvents[0]
});
```

### Step 3: Check Timestamp Units

```typescript
// In FrameCorrelationTimeline after line 88
console.log('⏱️ Timestamp Check:', {
  gtTimestamp: groundTruthEvents[0]?.timestamp,
  gtIsEpoch: groundTruthEvents[0]?.timestamp > 100000,
  detTimestamp: detectionEvents[0]?.timestamp,
  detIsRelative: detectionEvents[0]?.timestamp < 1000
});
```

### Step 4: Verify Correlation

```typescript
// In FrameCorrelationTimeline after correlation (line 194)
console.log('🔗 Correlation Stats:', {
  total: correlatedEvents.length,
  aligned: correlatedEvents.filter(e => e.correlation_status === 'aligned').length,
  misaligned: correlatedEvents.filter(e => e.correlation_status === 'misaligned').length,
  missing: correlatedEvents.filter(e => e.correlation_status === 'missing').length
});
```

---

## Quick Fix Priority

1. **Fix timestamp normalization** (15 minutes)
2. **Add console.log debugging** (5 minutes)
3. **Add type interfaces** (30 minutes)
4. **Fix video selector race condition** (15 minutes)
5. **Add error display to UI** (20 minutes)

**Total Time**: ~1.5 hours for critical fixes

---

## Expected Behavior After Fixes

1. Detection events display in FrameCorrelationTimeline
2. Ground truth events correlate with detections
3. Video selector switches without race conditions
4. Errors shown to user (not silently logged)
5. TypeScript catches field name mismatches at compile-time

---

## Next Steps

1. **Immediate**: Apply timestamp normalization fix
2. **Short-term**: Add type interfaces for all API responses
3. **Medium-term**: Optimize correlation algorithm
4. **Long-term**: Integrate WebSocket for real-time updates

---

**Full Report**: See `/docs/FRONTEND_INTEGRATION_REVIEW.md`
