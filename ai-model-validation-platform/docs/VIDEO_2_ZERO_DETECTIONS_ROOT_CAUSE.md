# Video 2 Zero Detections - Root Cause Analysis

**Session ID**: `71976ec4-b37d-4b19-8df7-11fefcb9bba7`
**Date**: 2025-11-03
**Status**: CRITICAL BUG CONFIRMED

---

## Executive Summary

**ROOT CAUSE IDENTIFIED**: Video 2 shows 0 detections because all detection events in the Video 2 time window are incorrectly tagged with Video 1's `video_id`. This is a **video_id assignment bug** in the detection event creation logic.

### The Numbers

| Metric | Expected | Actual | Issue |
|--------|----------|--------|-------|
| Video 1 Detections | 183 | 268 | +85 extra |
| Video 2 Detections | ~51-85 | 0 | Missing all |
| Total Detections | 234-268 | 268 | Correct total |

---

## Detailed Findings

### 1. Sequence Configuration (Correct)

```json
{
  "video_ids": [
    "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",  // Video 1
    "550e3cf8-2755-42df-8c3c-041300735f93"   // Video 2
  ],
  "total_videos": 2,
  "videos_completed": 2
}
```

### 2. Video Timing Windows (Correct)

#### Video 1
- **Configured Start**: `1762191677.75000`
- **Configured End**: `1762191683.07200`
- **Window Duration**: `5.322` seconds
- **Expected Detections**: 183

#### Video 2
- **Configured Start**: `1762191683.45300`
- **Configured End**: `1762191688.61000`
- **Window Duration**: `5.157` seconds
- **Expected Detections**: Unknown (metadata says 0, but this is the bug)

**Gap Between Videos**: `0.381` seconds (Video 1 end to Video 2 start)

### 3. Actual Detection Distribution (INCORRECT)

#### All 268 Detections Assigned to Video 1
```
Video ID: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5
  First Detection: 1762191668.62950
  Last Detection:  1762191687.46151
  Duration:        18.832 seconds
  Count:           268 detections
```

#### Video 2 Has Zero Detections
```
Video ID: 550e3cf8-2755-42df-8c3c-041300735f93
  Detections: 0
```

### 4. The Smoking Gun

**Query**: How many detections fall within Video 2's time window?

```sql
SELECT COUNT(*) FROM detection_events
WHERE timestamp BETWEEN 1762191683.453 AND 1762191688.610
```

**Result**: **51 detections**

**BUT**: All 51 detections have `video_id = "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5"` (Video 1)

**Sample Detection in Video 2 Window**:
```
ID: 6b4717c5-584d-4c45-8d87-2f3b5fd2d697
video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5  ← WRONG! Should be Video 2
timestamp: 1762191683.50224                      ← AFTER Video 2 start!
```

---

## Root Cause

### The Bug

When detection events are created, the `video_id` field is not being updated when transitioning from Video 1 to Video 2. The detection service continues to use Video 1's ID for all detections, even after Video 2 has started.

### Evidence

1. **Timing Mismatch**:
   - Video 1 configured end: `1762191683.072`
   - Video 2 configured start: `1762191683.453`
   - But detections with Video 1 ID continue until: `1762191687.461`
   - **Overlap**: 4.39 seconds of Video 2 detections tagged as Video 1

2. **Detection Count Discrepancy**:
   - Video 1 expected: 183 detections
   - Video 1 actual: 268 detections
   - Extra detections: 85
   - Detections in Video 2 window: 51
   - **Unaccounted**: 34 detections (likely Video 1 detections that occurred BEFORE configured start)

3. **Metadata Inconsistency**:
   - `sequence_metadata.video_timing["Video 2"].detection_count = 0`
   - But actual detections in that time window: 51

---

## Impact Analysis

### User-Facing Impact
1. **Video 2 Results Show Empty**: No detections displayed for second video
2. **Incorrect Metrics**: Video 1 appears to have more detections than it should
3. **Invalid Comparisons**: Multi-video performance analysis is impossible
4. **Ground Truth Matching**: Video 2 detections can't be matched to correct ground truth

### Data Integrity Impact
1. **Database Corruption**: 51+ detection events have wrong `video_id`
2. **Cascade Effects**: Any queries filtering by `video_id` will be wrong
3. **Historical Data**: All past multi-video sessions likely affected

---

## Suspect Code Locations

### 1. Detection Event Creation
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

**Likely Issue**: When creating detection events, the service:
- Gets initial `video_id` from session at start
- Never updates it when video changes
- Should be listening for video transition events

### 2. Video Transition Handling
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py`

**Likely Issue**: When `video_started` event is emitted:
- Frontend updates its state
- Backend updates `sequence_metadata`
- But detection service doesn't get notified
- Detection events continue using old `video_id`

### 3. Session State Management
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

**Likely Issue**: When transitioning videos:
- Updates `current_video_id` in metadata
- But doesn't propagate change to detection service
- Detection service has stale reference

---

## Recommended Fix

### Option 1: Real-Time video_id Updates (Preferred)

```python
# In labjack_detection_service.py
class LabjackDetectionService:
    def __init__(self):
        self.current_video_id = None
        self.session_id = None

    def on_video_transition(self, session_id: str, new_video_id: str):
        """Called when video changes in sequence"""
        if self.session_id == session_id:
            logger.info(f"Updating video_id: {self.current_video_id} -> {new_video_id}")
            self.current_video_id = new_video_id

    def create_detection_event(self, ...):
        # Use current_video_id instead of static session.video_id
        video_id = self.current_video_id or self.get_current_video_from_session()
```

### Option 2: Timestamp-Based video_id Assignment (Fallback)

```python
def assign_video_id_by_timestamp(session_id: str, detection_timestamp: float) -> str:
    """Determine correct video_id based on detection timestamp"""
    session = get_session(session_id)

    if not session.sequence_metadata:
        return session.video_id

    video_timing = session.sequence_metadata.get('video_timing', {})

    for video_id, timing in video_timing.items():
        if timing['started_at'] <= detection_timestamp <= timing['ended_at']:
            return video_id

    # Fallback to first video
    return session.sequence_metadata['video_ids'][0]
```

### Option 3: Retroactive Fix (Data Migration)

```python
def fix_video_id_assignments(session_id: str):
    """Fix video_id for existing detection events"""
    session = db.query(TestSession).filter_by(id=session_id).first()
    video_timing = session.sequence_metadata.get('video_timing', {})

    for video_id, timing in video_timing.items():
        # Update all detections in this time window
        db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.unix_timestamp >= timing['started_at'],
            DetectionEvent.unix_timestamp <= timing['ended_at']
        ).update({'video_id': video_id})

    db.commit()
```

---

## Verification Steps

After fix is applied:

1. **Run test session with 2 videos**
2. **Query detections by video_id**:
   ```sql
   SELECT video_id, COUNT(*)
   FROM detection_events
   WHERE test_session_id = ?
   GROUP BY video_id
   ```
3. **Verify both videos have detections**
4. **Check timestamp ranges match configured windows**
5. **Verify frontend displays both videos correctly**

---

## Files to Investigate

### Backend Services
- `/backend/services/labjack_detection_service.py` - Detection creation
- `/backend/services/raw_labjack_integration.py` - LabJack event handling
- `/backend/services/video_sequence_orchestrator.py` - Video transitions
- `/backend/socketio_server.py` - Event emission

### Backend Routes
- `/backend/routers/test_sessions.py` - Session management
- `/backend/routes/labjack_timing.py` - Timing coordination

### Database Models
- `/backend/models.py` - DetectionEvent model
- `/backend/schemas.py` - Detection schemas

---

## Related Issues

This bug likely affects:
1. All multi-video test sessions
2. Ground truth matching for Video 2+
3. Per-video metrics and analytics
4. Video sequence results page
5. Detection filtering by video

---

## Next Steps

1. ✅ **Root cause identified** - video_id not updated on video transition
2. ⏭️ **Locate exact code** - Find where detection events are created
3. ⏭️ **Implement fix** - Add video transition handler
4. ⏭️ **Test fix** - Verify with new multi-video session
5. ⏭️ **Data migration** - Fix existing sessions (optional)
6. ⏭️ **Add monitoring** - Log video transitions and video_id changes

---

## Appendix: Data Evidence

### Detection Timestamps in Video 2 Window (Sample)

All these should have `video_id = 550e3cf8-2755-42df-8c3c-041300735f93` but have Video 1's ID:

```
1762191683.50224 - 0.049s after Video 2 start
1762191683.57503 - 0.122s after Video 2 start
1762191683.64838 - 0.195s after Video 2 start
1762191683.72018 - 0.267s after Video 2 start
...
1762191687.46151 - 4.008s after Video 2 start (last detection)
```

Total: **51 detections** with wrong video_id

### Timing Timeline

```
1762191668.606 - Session start (video_start_timestamp)
1762191668.630 - First detection (Video 1, but 9.12s before configured start!)
1762191677.750 - Video 1 configured start
1762191683.072 - Video 1 configured end
1762191683.453 - Video 2 configured start ← BUG: video_id not updated here
1762191687.461 - Last detection (still tagged as Video 1!)
1762191688.610 - Video 2 configured end
```

**Problem**: Detection service never learned about video transition at 1762191683.453
