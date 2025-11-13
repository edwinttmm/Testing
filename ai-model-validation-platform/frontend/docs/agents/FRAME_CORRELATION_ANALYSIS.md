# Frame Correlation Algorithm Analysis - Frame 120 Bunching Issue

## Executive Summary

**CRITICAL BUG FOUND**: The frame correlation algorithm uses `clampFrame()` which caps all frame numbers at `totalFrames - 1`. When video duration is 5 seconds at 24fps, this creates a hard limit at Frame 119 (0-indexed). Any detections beyond Frame 119 get clamped to Frame 119, causing all late detections (5.024s - 6.762s) to bunch at the same frame number.

**Impact**: 70 detections spanning 1.7+ seconds are all being mapped to Frame 120 (5.000s), making the timeline visualization completely inaccurate and alignment metrics unreliable.

## Root Cause Analysis

### 1. The `clampFrame()` Function (Line 82-86)

```typescript
const clampFrame = (frame: number): number => {
  if (!Number.isFinite(frame)) return 0;
  if (totalFrames == null) return Math.max(0, Math.floor(frame));
  return Math.min(Math.max(0, Math.floor(frame)), Math.max(0, totalFrames - 1));
  //     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  //     THIS IS THE BUG: Caps frames at (totalFrames - 1)
};
```

**Problem**: The last argument `Math.max(0, totalFrames - 1)` creates a hard ceiling.

### 2. Video Duration Calculation (Line 79)

```typescript
const totalFrames = typeof duration === 'number' && Number.isFinite(duration)
  ? Math.max(0, Math.round(duration * fps))
  : undefined;
```

For the problematic session:
- `duration = 5.0s` (video end time)
- `fps = 24`
- `totalFrames = Math.round(5.0 * 24) = 120 frames`
- **Maximum allowed frame = 119** (0-indexed)

### 3. Frame Clamping Applied to ALL Events

**Ground Truth Events (Line 167)**:
```typescript
const gtFrameNumber = gtFrameValid ? clampFrame(gtFrameRaw) : 0;
```

**Detection Events (Line 206)**:
```typescript
const detectionFrameNumber = detectionFrameValid ? clampFrame(detectionFrameRaw) : 0;
```

**Correlation Matching (Line 227, 260)**:
```typescript
const gtFrame = gtFrameValid ? clampFrame(gtFrameRaw) : 0;
const closestGTFrame = closestGtFrameValid ? clampFrame(closestGtFrameRaw) : 0;
```

### 4. Real-World Example from Session Data

From the UI showing "218 events, 97 Aligned":
- Video duration: 5.0s (Frame 0-119)
- Detections occurring: 5.024s to 6.762s (Frames 120-162)
- **All 70 detections get clamped to Frame 119**
- Timeline shows them at 5.000s instead of their actual times

## Frame Correlation Algorithm Flow

### Step-by-Step Processing

```
1. Calculate totalFrames:
   duration = 5.0s, fps = 24
   totalFrames = round(5.0 * 24) = 120
   maxFrame = totalFrames - 1 = 119

2. Process Ground Truth Events:
   For each GT:
     - Extract frame number from GT data
     - Call clampFrame(frameNumber)
       └─> If frame >= 119, return 119
     - Store clamped frame for correlation

3. Process Detection Events:
   For each detection:
     - Extract frame number from detection data
     - Call clampFrame(frameNumber)
       └─> If frame >= 119, return 119  ← BUG HERE
     - Find nearest GT by comparing CLAMPED frames
     - Calculate correlation status

4. Correlation Logic (Lines 268-279):
   frameOffsetFrames = abs(detectionFrame - closestGTFrame)
   frameOffsetMs = (frameOffsetFrames / fps) * 1000

   IF frameOffsetMs <= (1000/fps) * 2:  // Within 2 frames
     status = 'aligned'
   ELSE IF frameOffsetMs <= (1000/fps) * 5:  // Within 5 frames
     status = 'misaligned'
   ELSE:
     status = 'missing'
```

### Why All Detections Show "Aligned"

**Scenario**: Detection at 6.000s (Frame 144) vs GT at 5.000s (Frame 120)

```typescript
// WITHOUT CLAMPING (correct):
detectionFrame = 144
gtFrame = 120
frameOffset = |144 - 120| = 24 frames
frameOffsetMs = (24 / 24) * 1000 = 1000ms
status = 'missing' ✓

// WITH CLAMPING (buggy):
detectionFrame = clamp(144) = 119  ← CLAMPED
gtFrame = clamp(120) = 119         ← CLAMPED
frameOffset = |119 - 119| = 0 frames
frameOffsetMs = 0ms
status = 'aligned' ✗ WRONG!
```

**Result**: All detections after Frame 119 appear perfectly aligned because they're all artificially set to Frame 119.

## Video Duration and Frame Cap Issues

### Issue 1: Video Duration vs Detection Duration

The code uses `videoMetadata.duration` to calculate frame limits, but this represents **video file duration**, not **detection monitoring duration**.

```typescript
// Line 156-157
const videoDuration = videoMetadata?.duration ?? Infinity;
console.log(`Video duration: ${Number.isFinite(videoDuration) ? videoDuration.toFixed(3) + 's' : 'unknown'}`);
```

**Problem**: System may continue detecting events after video ends (e.g., synthetic detections, test scenarios, delayed processing).

### Issue 2: "Video Ended" Logic Doesn't Apply to Detections

```typescript
// Lines 180-183 - Only marks GROUND TRUTH as video_ended
if (Number.isFinite(videoDuration) && gtTimeSeconds > videoDuration) {
  gtCorrelationStatus = 'video_ended';
}
```

**Missing**: No equivalent logic for detections. Detections beyond video duration get clamped instead of marked as "video_ended" or "out_of_bounds".

### Issue 3: Frame Validation Threshold is Too Permissive

```typescript
// Lines 163-166 (GT) and 199-201 (Detection)
const frameThreshold = Number.isFinite(totalFrames ?? NaN)
  ? (totalFrames ?? 0) * 1.5  // Allows 50% overshoot
  : 10000;

const gtFrameValid =
  Number.isFinite(gtFrameRaw) &&
  gtFrameRaw >= 0 &&
  (!Number.isFinite(totalFrames ?? NaN) || gtFrameRaw <= frameThreshold);
```

**Problem**: Even though validation allows up to 150% of totalFrames, the `clampFrame()` function still caps at `totalFrames - 1`, making the validation pointless.

## Alignment Calculation Logic

### Two-Frame Tolerance (Line 273)

```typescript
if (frameOffsetMs <= (1000 / fps) * 2) { // Within 2 frames
  correlationStatus = 'aligned';
}
```

**At 24fps**:
- 1 frame = 41.67ms
- 2 frames = 83.33ms
- Tolerance window: ±83.33ms

**Why This Matters**: Because all frames are clamped to 119, the offset is always 0ms, so everything appears "aligned" even when it's actually seconds off.

### Five-Frame Tolerance for Misalignment (Line 275-276)

```typescript
else if (frameOffsetMs <= (1000 / fps) * 5) { // Within 5 frames
  correlationStatus = 'misaligned';
}
```

**At 24fps**:
- 5 frames = 208.33ms
- Beyond 5 frames = 'missing'

**Current Behavior**: Since offset is always 0ms for clamped frames, nothing ever gets marked as 'misaligned' or 'missing'.

## Timestamp vs Frame Number Handling

### Dual Time Representations

The code handles both:
1. **Frame numbers** (discrete, 0-indexed)
2. **Timestamps** (continuous, seconds)

```typescript
// Lines 209-215 - Timestamp normalization
const rawDetTimestamp = Number(det.timestamp ?? det.video_timestamp ?? ...);
const normalizedDetTime = normalizeTimestamp(rawDetTimestamp, videoStartEpoch);
const frameDerivedTime = detectionFrameValid && detectionFrameNumber > 0 && Number.isFinite(fps)
  ? detectionFrameNumber / fps
  : undefined;
const videoTimeSeconds = Number.isFinite(normalizedDetTime) && normalizedDetTime >= 0
  ? normalizedDetTime
  : (frameDerivedTime ?? 0);
```

### Critical Flow

```
Raw Detection Data
    ↓
1. Extract frame_number (e.g., 144)
2. Call clampFrame(144) → returns 119  ← BUG
3. Calculate time from clamped frame: 119/24 = 4.958s
4. BUT: Also extract timestamp directly: 6.000s
5. Use timestamp for display: 6.000s  ← Correct
6. Use clamped frame for correlation: Frame 119  ← Wrong
```

**Result**: Timeline shows detection at 6.000s (correct timestamp) but correlates it as Frame 119 (wrong frame), causing alignment to appear correct when it's not.

## Detection Timeline Display

### How Detections are Displayed (Lines 494-620)

```typescript
correlatedEvents.map((event, index) => (
  <TableRow>
    <TableCell>
      <Typography variant="body2" fontWeight="bold">
        Frame {event.frame_number}  ← Shows clamped frame (119)
      </Typography>
    </TableCell>
    <TableCell>
      <Typography variant="body2">
        {formatFrameTime(event.frame_number)}  ← 119/24 = 4.958s
      </Typography>
    </TableCell>
    <TableCell>
      <Chip
        label={event.correlation_status}  ← Shows 'aligned'
        color={getCorrelationColor(event.correlation_status)}
      />
    </TableCell>
  </TableRow>
))
```

**Display Logic**:
- Shows **frame number** (clamped to 119)
- Calculates **display time** from clamped frame (4.958s)
- But actual **timestamp** in event object is correct (6.000s)

### formatFrameTime Function (Lines 371-374)

```typescript
const formatFrameTime = (frameNumber: number) => {
  const timeSeconds = frameNumber / fps;
  return `${timeSeconds.toFixed(3)}s`;
};
```

**Issue**: Converts clamped frame back to time, showing 4.958s instead of actual 6.000s.

## Video Ended Logic

### Current Implementation (Lines 178-183)

```typescript
// FIX #19: Mark as video_ended ONLY if GT is beyond actual video duration
if (Number.isFinite(videoDuration) && gtTimeSeconds > videoDuration) {
  gtCorrelationStatus = 'video_ended';
}
```

**Applied to**: Ground truth events ONLY
**Not applied to**: Detection events

### Statistics Calculation (Lines 333-346)

```typescript
const videoEnded = groundTruths.filter(e => e.correlation_status === 'video_ended').length;

// Calculate alignment rate based on monitored period only (exclude video_ended)
const monitoredGroundTruths = groundTruths.filter(e => e.correlation_status !== 'video_ended').length;
```

**UI Display (Lines 412-418)**:
```typescript
<Chip
  label={`${correlationStats.videoEnded} Video Ended`}
  color="info"
  size="small"
/>
```

**Current Issue**: Shows "0 Video Ended" because:
1. Only GT events can be marked as 'video_ended'
2. Detections beyond video duration are clamped instead
3. No detection is ever marked as 'video_ended'

## Why Alignment Rate Shows 100%

### Statistics Calculation (Lines 326-349)

```typescript
const correlationStats = useMemo(() => {
  const detections = correlatedEvents.filter(e => e.type === 'detection');
  const groundTruths = correlatedEvents.filter(e => e.type === 'ground_truth');

  const aligned = detections.filter(e => e.correlation_status === 'aligned').length;
  const misaligned = detections.filter(e => e.correlation_status === 'misaligned').length;
  const missing = detections.filter(e => e.correlation_status === 'missing').length;

  return {
    total: detections.length,
    aligned,
    misaligned,
    missing,
    alignmentRate: detections.length > 0 ? (aligned / detections.length) * 100 : 0
  };
}, [correlatedEvents]);
```

**Current Results** (from UI):
- Total: 218 events
- Aligned: 97
- Misaligned: 0
- Missing: 0
- **Alignment Rate: 100%**

**Why This is Wrong**:
```
Real scenario:
- 27 detections at Frame 120-130 (should be aligned)
- 70 detections at Frame 131-162 (should be missing/misaligned)

With clamping bug:
- All 97 detections at Frame 119 (appear aligned)
- frameOffset = 0 for all
- All marked as 'aligned'
```

## Recommended Fixes

### Fix 1: Remove Frame Clamping (Primary Fix)

**Replace clampFrame() with validation-only approach:**

```typescript
// BEFORE (buggy):
const clampFrame = (frame: number): number => {
  if (!Number.isFinite(frame)) return 0;
  if (totalFrames == null) return Math.max(0, Math.floor(frame));
  return Math.min(Math.max(0, Math.floor(frame)), Math.max(0, totalFrames - 1));
};

// AFTER (fixed):
const validateFrame = (frame: number): number | null => {
  if (!Number.isFinite(frame)) return null;
  if (frame < 0) return null;
  return Math.floor(frame);
};

const getFrameStatus = (frame: number | null, totalFrames: number | undefined): 'valid' | 'out_of_bounds' => {
  if (frame === null) return 'out_of_bounds';
  if (totalFrames !== undefined && frame >= totalFrames) return 'out_of_bounds';
  return 'valid';
};
```

**Usage:**
```typescript
const detectionFrameNumber = validateFrame(detectionFrameRaw);
const frameStatus = getFrameStatus(detectionFrameNumber, totalFrames);

if (frameStatus === 'out_of_bounds') {
  correlationStatus = 'video_ended'; // or 'out_of_bounds'
}
```

### Fix 2: Add "Out of Bounds" Status for Detections

**Extend correlation status enum:**

```typescript
type CorrelationStatus = 'aligned' | 'misaligned' | 'missing' | 'video_ended' | 'out_of_bounds';
```

**Apply to detections beyond video:**

```typescript
// For detections (add after line 280)
if (detectionFrameNumber !== null && totalFrames !== undefined && detectionFrameNumber >= totalFrames) {
  correlationStatus = 'out_of_bounds';
} else if (closestGT) {
  // ... existing correlation logic
}
```

### Fix 3: Fix Display Time Calculation

**Use actual timestamp instead of frame-derived time:**

```typescript
// BEFORE (line 534):
<Typography variant="body2">
  {formatFrameTime(event.frame_number)}  ← Wrong: uses clamped frame
</Typography>

// AFTER:
<Typography variant="body2">
  {event.timestamp.toFixed(3)}s  ← Correct: uses actual timestamp
</Typography>
```

### Fix 4: Separate Video Duration from Detection Window

**Add detection window parameter:**

```typescript
interface FrameCorrelationTimelineProps {
  detectionEvents: any[];
  groundTruthEvents: any[];
  videoMetadata: {
    fps?: number;
    duration?: number;  // Video file duration
    detectionWindowEnd?: number;  // Maximum time for valid detections
    filename?: string;
    video_start_timestamp_epoch_sec?: number;
  };
  // ...
}
```

**Usage:**

```typescript
const videoDuration = videoMetadata?.duration ?? Infinity;
const detectionWindow = videoMetadata?.detectionWindowEnd ?? videoDuration;

// Use videoDuration for video file boundaries
// Use detectionWindow for marking detections as out_of_bounds
```

### Fix 5: Update Statistics to Include Out-of-Bounds

```typescript
const correlationStats = useMemo(() => {
  const detections = correlatedEvents.filter(e => e.type === 'detection');
  const aligned = detections.filter(e => e.correlation_status === 'aligned').length;
  const misaligned = detections.filter(e => e.correlation_status === 'misaligned').length;
  const missing = detections.filter(e => e.correlation_status === 'missing').length;
  const outOfBounds = detections.filter(e => e.correlation_status === 'out_of_bounds').length;

  // Calculate alignment rate excluding out-of-bounds detections
  const validDetections = detections.length - outOfBounds;
  const alignmentRate = validDetections > 0 ? (aligned / validDetections) * 100 : 0;

  return {
    total: detections.length,
    aligned,
    misaligned,
    missing,
    outOfBounds,
    validDetections,
    alignmentRate
  };
}, [correlatedEvents]);
```

## Testing Strategy

### Test Case 1: Normal Case (All Frames Within Bounds)

```typescript
// Video: 5.0s, 24fps → 120 frames (0-119)
// Detections: Frames 10, 50, 100
// Expected: All aligned, no clamping issues
```

### Test Case 2: Boundary Case (Frames Near End)

```typescript
// Video: 5.0s, 24fps → 120 frames (0-119)
// Detections: Frames 115, 118, 119
// Expected: All valid, proper correlation
```

### Test Case 3: Out of Bounds (Frames Beyond Video)

```typescript
// Video: 5.0s, 24fps → 120 frames (0-119)
// Detections: Frames 120, 130, 144, 162
// Expected:
//   - All marked as 'out_of_bounds'
//   - NOT aligned with any GT
//   - Display actual timestamps (5.000s, 5.417s, 6.000s, 6.750s)
//   - Excluded from alignment rate calculation
```

### Test Case 4: Mixed Case (Some In, Some Out)

```typescript
// Video: 5.0s, 24fps → 120 frames (0-119)
// Detections: Frames 100, 110, 115, 120, 130, 140
// Expected:
//   - Frames 100, 110, 115: Valid, can be correlated
//   - Frames 120, 130, 140: Out of bounds
//   - Alignment rate based only on valid frames
```

## Priority and Impact

### Severity: CRITICAL

**Reasons**:
1. **Data Integrity**: All detections after video end are incorrectly reported as aligned
2. **Metric Accuracy**: 100% alignment rate is misleading when 72% of detections are actually out of bounds
3. **User Trust**: Users see "97 Aligned" when only ~27 should be aligned
4. **Debugging**: Makes it impossible to identify real timing issues

### Affected Components

1. **FrameCorrelationTimeline.tsx** (Primary)
   - clampFrame() function
   - Correlation calculation
   - Statistics computation
   - Display logic

2. **HILResults.tsx** (Secondary)
   - Video metadata handling
   - Timeline visualization integration

3. **Backend API** (Tertiary)
   - Should validate frame numbers before sending
   - Should flag out-of-bounds detections

### Deployment Risk

**Low** - Fix is isolated to visualization logic, doesn't affect:
- Detection capture
- Database storage
- Ground truth matching
- Latency calculation

## Performance Considerations

### Current Performance

```typescript
// O(n*m) - For each detection, find closest GT
groundTruthEvents.forEach((gt: any) => {
  const timeDiff = Math.abs(videoTimeSeconds - gtTimeSeconds);
  if (timeDiff < minTimeDiff) {
    minTimeDiff = timeDiff;
    closestGT = gt;
  }
});
```

**Optimization Opportunity**: With frame clamping removed, could add early exit:

```typescript
// Sort GTs by frame once
const sortedGTs = [...groundTruthEvents].sort((a, b) => a.frame - b.frame);

// Binary search for closest GT
const closestGT = findClosestGT(detectionFrame, sortedGTs);
```

## Additional Findings

### Timestamp Normalization (Lines 92-106)

The code handles epoch timestamps correctly:

```typescript
const normalizeTimestamp = useCallback((timestamp: number, videoStartEpoch?: number): number => {
  // If timestamp > 100000, it's epoch seconds - convert to video-relative
  if (timestamp > 100000) {
    if (videoStartEpoch && videoStartEpoch > 0) {
      const videoRelative = timestamp - videoStartEpoch;
      return videoRelative;
    }
    console.warn(`Epoch timestamp ${timestamp.toFixed(2)}s detected but no video start time available`);
    return 0;
  }
  return timestamp;
}, []);
```

**Good**: This prevents epoch timestamp issues
**Note**: Frame clamping bug is independent of timestamp normalization

### Frame Offset Calculation (Lines 268-279)

```typescript
const frameOffsetFrames = Math.abs(detectionFrameNumber - closestGTFrame);
frameOffsetMs = (frameOffsetFrames / fps) * 1000;
gtLatencyMs = (videoTimeSeconds - closestGTTimeSec) * 1000;  // Signed latency
```

**Observation**: Code calculates both:
1. Frame-based offset (for correlation status)
2. Time-based latency (for display)

**Issue**: Frame-based offset is wrong due to clamping, but time-based latency might be correct if timestamps are preserved.

## Conclusion

The frame bunching at Frame 120 is caused by the `clampFrame()` function's hard ceiling at `totalFrames - 1`. This causes:

1. **Incorrect Correlation**: All detections beyond video end appear aligned
2. **False Metrics**: 100% alignment rate when reality is ~28% (27/97)
3. **Misleading Visualization**: Timeline shows bunching instead of out-of-bounds
4. **Missing Classification**: No way to identify post-video detections

**Recommended Action**: Implement Fix 1 (remove clamping) + Fix 2 (add out_of_bounds status) as the minimum viable fix. Fixes 3-5 are enhancements that should follow.

**Estimated Fix Time**: 2-4 hours
**Testing Time**: 2-3 hours
**Total**: 4-7 hours to production-ready fix
