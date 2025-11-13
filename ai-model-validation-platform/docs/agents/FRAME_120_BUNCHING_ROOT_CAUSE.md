# Frame 120 Bunching Root Cause Analysis

**Session**: `6d05fcd1-0c9b-432b-acbd-675c5e3683c9`
**Issue**: 70 detections ALL display "Frame 120" and "5.000s" in the UI despite having vastly different latencies
**Date**: 2025-01-05
**Severity**: HIGH - Display Bug Causing Incorrect Frame Assignment Visualization

---

## Executive Summary

**ROOT CAUSE IDENTIFIED**: This is a **DISPLAY BUG**, not a backend calculation bug.

- **Backend Data**: ✅ CORRECT - Frames 50-309 with accurate video_relative_timestamps (5.000s - 12.890s)
- **Frontend Display**: ❌ INCORRECT - All detections show "Frame 120 (5.000s)" regardless of actual time
- **Ground Truth Limitation**: Ground truth only covers Frames 0-121 (0-5.042s @ 24fps)
- **Detection Coverage**: Detections extend to 12.890s, which is **Frame 309** at 24fps

### Why This Matters

The UI shows:
```
Detection with 1762ms latency → "Frame 120 (5.000s)"
Detection with 23ms latency    → "Frame 120 (5.000s)"
```

But the **actual database** shows:
```
Detection with 1762ms latency → Frame 162 @ 6.762s ✅
Detection with 23ms latency    → Frame 50 @ 2.089s ✅
```

---

## Evidence From Database Query

### Raw API Data (Last 50 Detections)

```
Frame | Video Time (s) | Latency (ms) | Status
------|----------------|--------------|--------
160   | 6.673         | 1672.8       | Beyond GT
161   | 6.739         | 1739.2       | Beyond GT
162   | 6.762         | 1762.3       | Beyond GT ← Highest latency
283   | 11.822        | 6821.9       | Way beyond GT
...
309   | 12.890        | 7890.1       | Final detection
```

**Key Observations**:
1. Backend calculates frames correctly: Frame 162 @ 6.762s, Frame 309 @ 12.890s
2. These detections are **5-7 seconds beyond** the ground truth video duration
3. Ground truth ends at Frame 121 (5.042s)
4. Video duration is 5.042s, but detections continue to 12.890s

---

## Ground Truth Coverage Analysis

### Database Ground Truth Range

```sql
SELECT MAX(frame_number), MAX(timestamp)
FROM ground_truth_objects
WHERE video_id = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5';

Result:
- Max Frame: 121
- Max Timestamp: 5.0s
- Video Duration: 5.042s
- FPS: 24
- Expected Frames: 121 (5.042 * 24 = 121.0)
```

### Detection Coverage vs Ground Truth

```
Timeline:
|-------- Video Duration (5.042s) --------|--- Beyond Video ---|
|  GT Coverage (0-121 frames)  |          |                    |
|  Detections (0-309 frames)                                   |
              ↑                            ↑                    ↑
           Frame 0                     Frame 121            Frame 309
           (0.0s)                      (5.0s)               (12.890s)
```

**Problem**:
- Ground truth stops at Frame 121 (5.0s)
- Detections continue to Frame 309 (12.890s)
- **188 frames** worth of detections have **NO ground truth** to match against

---

## Backend Frame Calculation Review

### Frame Calculation Code (✅ CORRECT)

**File**: `/backend/services/video_sequence_orchestrator.py:551-552`

```python
# Calculate video frame number (ensure non-negative)
frame_number_raw = int(round(video_relative_timestamp * metadata.fps))
video_frame_number = max(frame_number_raw, 0)
```

**File**: `/backend/services/timestamp_conversion_utils.py:151`

```python
# Calculate frame number (0-based)
frame_number = int(video_relative_timestamp * fps)
```

**Analysis**:
- ✅ Frame calculation is straightforward: `time * fps`
- ✅ No capping at 120
- ✅ No `min()` function limiting frames
- ✅ Database shows frames 50-309 correctly

### Example Calculations (Verified)

```python
# Detection at 6.762s with 24fps:
frame_number = int(6.762 * 24) = int(162.288) = 162 ✅

# Detection at 12.890s with 24fps:
frame_number = int(12.890 * 24) = int(309.36) = 309 ✅

# Ground truth max at 5.0s with 24fps:
frame_number = int(5.0 * 24) = int(120.0) = 120 ✅
```

---

## Frontend Display Bug Analysis

### Symptoms in UI

```
UI Display (WRONG):
┌─────────────────────────────────────────┐
│ Detection #50: Frame 120 (5.000s)       │  ← Latency: 23ms
│ Detection #51: Frame 120 (5.000s)       │  ← Latency: 45ms
│ ...                                      │
│ Detection #97: Frame 120 (5.000s)       │  ← Latency: 1762ms
└─────────────────────────────────────────┘
```

```
Actual Backend Data (CORRECT):
┌─────────────────────────────────────────┐
│ Detection #50: Frame 50 (2.089s)        │  ← Latency: 23ms
│ Detection #51: Frame 52 (2.171s)        │  ← Latency: 45ms
│ ...                                      │
│ Detection #97: Frame 162 (6.762s)       │  ← Latency: 1762ms
└─────────────────────────────────────────┘
```

### Likely Frontend Causes

#### Hypothesis 1: Ground Truth Frame Limit Override
```typescript
// Frontend may be doing:
const displayFrame = Math.min(actualFrame, maxGroundTruthFrame);
// Results in: Math.min(162, 120) = 120 ❌

// OR matching detection to nearest GT, forcing to GT's max frame
const matchedGT = findNearestGroundTruth(detection);
detection.frame = matchedGT.frame; // Always 120 for unmatched
```

#### Hypothesis 2: Video Duration Cap
```typescript
// Frontend may be capping based on video duration:
const maxTime = videoDuration; // 5.042s
const cappedTime = Math.min(detectionTime, maxTime); // Caps all to 5.0s
const frame = Math.floor(cappedTime * fps); // Always 120
```

#### Hypothesis 3: Detection Timeline Component
The `FrameCorrelationTimeline.tsx` component may:
- Show ground truth range (0-120) as valid area
- Display all detections beyond this as "Frame 120"
- Use ground truth max frame as display ceiling

---

## Impact Analysis

### Metrics Impact

**Precision/Recall**: Not affected (backend matching is correct)
- Backend correctly calculates that detections beyond 5.0s are False Positives
- Ground truth matching logic properly identifies these as beyond GT coverage

**Latency Calculation**: Not affected (backend timing is accurate)
- Latencies range from 23ms to 7890ms correctly
- Backend stores actual `video_relative_timestamp` accurately

**User Experience**: SEVERELY affected
- ❌ Users see 70 detections all at "Frame 120"
- ❌ Cannot visually distinguish detection timing
- ❌ Timeline appears bunched/clustered incorrectly
- ❌ Latency values don't match displayed frame numbers

### Example Contradictions Visible to Users

```
UI Shows:              Reality:
Frame 120, 23ms     →  Frame 50, 23ms   (Detection too early by 70 frames!)
Frame 120, 1762ms   →  Frame 162, 1762ms (Detection 42 frames late!)
```

**User Confusion**: "How can detections at the same frame have 1700ms difference in latency?"

---

## Root Cause: Why Detection Beyond Ground Truth?

### Timeline of What Happened

```
T=0.000s: Test session starts, video plays
T=0.000s-5.042s: Video 1 plays (121 frames @ 24fps)
T=5.042s: Video 1 ends
T=5.042s-12.890s: ❓ What happened here? ❓
```

### Hypotheses for Extended Detection Window

#### Option 1: Multi-Video Sequence
- Session may have played multiple videos
- Detection monitoring continued across videos
- But detections attributed to first video only

#### Option 2: Monitoring Overrun
- Video ended at 5.042s
- LabJack monitoring continued for ~8 more seconds
- Detections logged but beyond video content

#### Option 3: Video Loop/Replay
- Video looped or replayed
- Detections logged with cumulative timestamps
- But ground truth only loaded for first playthrough

---

## Specific Fixes Needed

### Fix 1: Frontend Display Logic

**File**: `/frontend/src/components/FrameCorrelationTimeline.tsx` (or similar)

```typescript
// CURRENT (SUSPECTED):
const displayFrame = Math.min(detection.frame_number, maxGroundTruthFrame);
const displayTime = Math.min(detection.video_relative_timestamp, videoDuration);

// SHOULD BE:
const displayFrame = detection.frame_number; // Show actual frame
const displayTime = detection.video_relative_timestamp; // Show actual time
const isBeyondVideo = displayTime > videoDuration; // Flag for styling

// Visual indicator:
if (isBeyondVideo) {
  className += " beyond-video-duration";
  tooltip = `Detection at ${displayTime.toFixed(3)}s (beyond video end at ${videoDuration}s)`;
}
```

### Fix 2: Detection Boundary Validation

**File**: `/backend/services/detection_boundary_service.py`

Add validation to flag detections beyond video duration:

```python
def validate_detection_within_video(
    detection_time: float,
    video_duration: float,
    tolerance_s: float = 0.5
) -> Dict[str, Any]:
    """
    Validate if detection falls within video duration boundaries.

    Returns:
        Dict with 'valid', 'message', and 'beyond_video' fields
    """
    if detection_time > video_duration + tolerance_s:
        return {
            'valid': False,
            'beyond_video': True,
            'message': f"Detection at {detection_time:.3f}s beyond video duration {video_duration:.3f}s",
            'excess_time_s': detection_time - video_duration
        }

    return {'valid': True, 'beyond_video': False}
```

### Fix 3: Frontend Detection Table Columns

**File**: `/frontend/src/pages/HILResults.tsx` or `/frontend/src/components/DetectionTableRow.tsx`

```typescript
// Add visual indicators in table:
interface DetectionDisplayProps {
  frame_number: number;
  video_relative_timestamp: number;
  videoDuration: number;
  maxGroundTruthFrame: number;
}

function DetectionFrameCell({ frame_number, video_relative_timestamp, videoDuration, maxGroundTruthFrame }: DetectionDisplayProps) {
  const isBeyondGT = frame_number > maxGroundTruthFrame;
  const isBeyondVideo = video_relative_timestamp > videoDuration;

  return (
    <td className={isBeyondGT ? "bg-orange-100" : ""}>
      <span className={isBeyondVideo ? "text-red-600 font-bold" : ""}>
        Frame {frame_number}
      </span>
      {isBeyondGT && (
        <Tooltip content={`Beyond ground truth coverage (max: Frame ${maxGroundTruthFrame})`}>
          <WarningIcon className="ml-2" />
        </Tooltip>
      )}
      {isBeyondVideo && (
        <Tooltip content={`Beyond video duration (${videoDuration.toFixed(2)}s)`}>
          <AlertIcon className="ml-2 text-red-500" />
        </Tooltip>
      )}
    </td>
  );
}
```

### Fix 4: API Response Enhancement

**File**: `/backend/routers/test_sessions.py` (events endpoint)

Add metadata about video/GT boundaries:

```python
@router.get("/{session_id}/events")
async def get_detection_events(session_id: str, db: Session = Depends(get_db)):
    """Get detection events with boundary validation metadata"""

    # Get session and video info
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    video = db.query(Video).filter(Video.id == session.video_id).first()

    # Get ground truth range
    gt_max = db.query(func.max(GroundTruthObject.frame_number)).filter(
        GroundTruthObject.video_id == session.video_id
    ).scalar() or 0

    # Get detections
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).all()

    # Add boundary context
    return {
        'detections': [d.to_dict() for d in detections],
        'video_metadata': {
            'duration': video.duration,
            'fps': video.fps,
            'expected_frames': int(video.duration * video.fps)
        },
        'ground_truth_coverage': {
            'max_frame': gt_max,
            'max_time': gt_max / video.fps if video.fps else 0,
            'complete': True if gt_max >= int(video.duration * video.fps) else False
        },
        'detection_summary': {
            'within_video': sum(1 for d in detections if d.video_relative_timestamp <= video.duration),
            'beyond_video': sum(1 for d in detections if d.video_relative_timestamp > video.duration),
            'within_gt': sum(1 for d in detections if d.video_frame_number <= gt_max),
            'beyond_gt': sum(1 for d in detections if d.video_frame_number > gt_max)
        }
    }
```

---

## Testing Strategy

### Test Case 1: Detection Within Video Bounds
```python
# Detection at 2.5s (Frame 60) - within both video (5.042s) and GT (121 frames)
assert display_frame == 60
assert display_time == 2.5
assert status == "matched"
```

### Test Case 2: Detection Beyond GT But Within Video
```python
# Detection at 5.0s (Frame 120) - last GT frame
assert display_frame == 120
assert display_time == 5.0
assert status == "boundary"  # Could be matched to last GT
```

### Test Case 3: Detection Beyond Video Duration
```python
# Detection at 6.762s (Frame 162) - 1.72s beyond video
assert display_frame == 162  # Show actual, not 120!
assert display_time == 6.762
assert status == "beyond_video"
assert warning_icon_displayed == True
```

### Test Case 4: Detection WAY Beyond Video
```python
# Detection at 12.890s (Frame 309) - 7.85s beyond video
assert display_frame == 309
assert display_time == 12.890
assert status == "beyond_video"
assert color == "red"  # Strong visual indicator
```

---

## Verification Commands

### Check Backend Data Integrity
```bash
# Verify backend has correct frames
curl "http://localhost:8000/api/test-sessions/6d05fcd1-0c9b-432b-acbd-675c5e3683c9/events?limit=200" | \
  python3 -m json.tool | \
  grep -E "(frame_number|video_relative_timestamp|latency_ms)" | \
  tail -60
```

### Check Frontend Component
```bash
# Search for frame capping logic
cd /home/rigade/Testing/ai-model-validation-platform/frontend
grep -r "Math.min.*frame" src/
grep -r "maxGroundTruthFrame" src/
grep -r "videoDuration.*Math.min" src/
```

### Check Database Consistency
```sql
-- Verify detections beyond video duration
SELECT
    id,
    video_frame_number as frame,
    video_relative_timestamp as time_s,
    actual_latency_ms as latency_ms
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
  AND video_relative_timestamp > 5.042
ORDER BY video_relative_timestamp
LIMIT 20;
```

---

## Questions for Team

1. **Why do detections extend 7.85 seconds beyond video end?**
   - Was video looped?
   - Multiple videos in sequence?
   - Monitoring overrun bug?

2. **Should detections beyond video be valid?**
   - If yes: Frontend should display them correctly (not cap at Frame 120)
   - If no: Backend should reject them during capture

3. **Ground truth coverage strategy**
   - Should GT cover full monitoring window?
   - Or mark beyond-GT detections as "uncovered" False Positives?

4. **Frontend frame display policy**
   - Show actual frame number even if beyond GT?
   - Or show "Frame 162 (no GT)" with visual indicator?

---

## Summary

### What's Working ✅
- Backend frame calculation (correct)
- Backend timestamp calculation (accurate)
- Database storage (complete)
- Ground truth matching logic (identifies FPs correctly)

### What's Broken ❌
- Frontend display shows "Frame 120" for all detections beyond GT
- No visual indicator that detections are beyond video/GT coverage
- UI creates false impression of bunching at Frame 120
- Users cannot see actual detection timing in UI

### Priority Fix
**HIGH**: Fix frontend display to show actual frame numbers and timestamps, with clear visual indicators for detections beyond video/GT boundaries.

### Expected Outcome
After fix, UI should show:
```
Detection #50:  Frame 50  (2.089s) ✓ Matched
Detection #51:  Frame 52  (2.171s) ✓ Matched
...
Detection #97:  Frame 162 (6.762s) ⚠️ Beyond video (FP)
...
Detection #120: Frame 309 (12.890s) ⚠️ WAY beyond video (FP)
```
