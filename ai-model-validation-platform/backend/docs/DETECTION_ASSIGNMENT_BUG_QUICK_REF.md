# Detection Assignment Bug - Quick Reference

## TL;DR

**Bug**: All 108 detections have `video_id = NULL` and `sequence_video_result_id = NULL`
**Impact**: Frontend cannot display detections (filters by video_id)
**Root Cause**: Detection creation logic never assigns video linkage

---

## Key Facts

| Metric | Value |
|--------|-------|
| Session ID | `026c36cc-3801-4aa7-971f-b54c24d27505` |
| Total Detections | 108 |
| Detections with NULL video_id | 108 (100%) |
| Detections with NULL sequence_video_result_id | 108 (100%) |
| Frontend Result | "No detections found" |
| Actual Data in DB | ✅ Valid |

---

## Database Evidence

```sql
-- All detections missing video linkage
SELECT
  COUNT(*) as total,
  COUNT(CASE WHEN video_id IS NULL THEN 1 END) as missing_video_id
FROM detection_events
WHERE test_session_id = '026c36cc-3801-4aa7-971f-b54c24d27505';

Result: total=108, missing_video_id=108
```

```sql
-- Sequence video results missing timing
SELECT video_start_time, video_end_time, actual_detection_count
FROM sequence_video_results
WHERE video_sequence_id = 'a19211af-08cd-4bef-8997-10bd82cd70ce';

Result: Both NULL, NULL, 0
```

---

## Frontend Code Path

```typescript
// File: /home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx

// User selects video from dropdown
const selectedVideoId = "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5";

// Frontend filters detections
const filteredDetections = detections.filter(
  d => d.video_id === selectedVideoId  // ❌ ALL NULL
);

// Result: filteredDetections = []
// Display: "No detections found"
```

---

## Backend Code Path (Expected vs Actual)

### Expected Flow
```python
# When detection created
detection = DetectionEvent(
    test_session_id=session_id,
    timestamp=labjack_timestamp,
    labjack_voltage=voltage,
    video_id=current_video_id,  # ✅ Should be set
    sequence_video_result_id=current_result_id  # ✅ Should be set
)
```

### Actual Flow
```python
# What's happening now
detection = DetectionEvent(
    test_session_id=session_id,
    timestamp=labjack_timestamp,
    labjack_voltage=voltage,
    video_id=None,  # ❌ Never assigned
    sequence_video_result_id=None  # ❌ Never assigned
)
```

---

## Fix Locations

### 1. Detection Creation Service
**File**: `/backend/services/labjack_detection_service.py`

**Add**:
```python
def get_current_video_for_timestamp(session_id: str, timestamp: float):
    """Determine which video was active at given timestamp"""
    video_result = db.query(SequenceVideoResult).join(
        VideoTestSequence
    ).filter(
        VideoTestSequence.test_session_id == session_id,
        SequenceVideoResult.video_start_time <= timestamp,
        SequenceVideoResult.video_end_time >= timestamp
    ).first()

    return video_result

def create_detection_event(session_id, timestamp, voltage):
    # Get current video
    video_result = get_current_video_for_timestamp(session_id, timestamp)

    if not video_result:
        logger.warning(f"No video found for detection at {timestamp}")
        # Still create detection, but flag for review

    detection = DetectionEvent(
        test_session_id=session_id,
        timestamp=timestamp,
        labjack_voltage=voltage,
        video_id=video_result.video_id if video_result else None,
        sequence_video_result_id=video_result.id if video_result else None
    )

    db.add(detection)
    db.commit()
```

### 2. Sequence Video Results Timing
**File**: `/backend/services/video_sequence_orchestrator.py`

**Fix**:
```python
def video_started(video_id: str, start_timestamp: float):
    """Called when video playback starts"""
    video_result = get_current_sequence_video_result()
    video_result.video_start_time = start_timestamp  # ✅ SET THIS
    db.commit()

def video_ended(video_id: str, end_timestamp: float):
    """Called when video playback ends"""
    video_result = get_current_sequence_video_result()
    video_result.video_end_time = end_timestamp  # ✅ SET THIS
    db.commit()
```

### 3. Session Completion
**File**: `/backend/services/session_completion_service.py`

**Add**:
```python
def finalize_sequence_timing(session_id: str):
    """Update sequence_video_results from session metadata if missing"""
    session = db.query(TestSession).get(session_id)
    metadata = json.loads(session.sequence_metadata)

    for video_id, timing in metadata.get('video_timing', {}).items():
        video_result = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_id == video_id
        ).first()

        if not video_result.video_start_time:
            video_result.video_start_time = timing['started_at']

        if not video_result.video_end_time:
            video_result.video_end_time = timing['ended_at']

    db.commit()
```

---

## Quick Database Repair Script

```python
# File: /backend/scripts/repair_detection_video_assignment.py

import json
from models import TestSession, SequenceVideoResult, DetectionEvent
from database import SessionLocal

def repair_session_026c36cc():
    db = SessionLocal()
    session_id = '026c36cc-3801-4aa7-971f-b54c24d27505'

    # Get session metadata
    session = db.query(TestSession).get(session_id)
    metadata = json.loads(session.sequence_metadata)

    # Get sequence video results
    sequence_id = session.sequence_id
    video_results = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id
    ).all()

    # Update sequence video results timing from metadata
    for video_result in video_results:
        video_id = video_result.video_id
        timing = metadata['video_timing'].get(video_id)

        if timing:
            video_result.video_start_time = timing['started_at']
            video_result.video_end_time = timing['ended_at']

    db.commit()

    # Assign detections to videos based on timestamp
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).all()

    for detection in detections:
        for video_result in video_results:
            if (video_result.video_start_time and
                video_result.video_end_time and
                video_result.video_start_time <= detection.timestamp <= video_result.video_end_time):

                detection.video_id = video_result.video_id
                detection.sequence_video_result_id = video_result.id
                break

    db.commit()

    print(f"✅ Repaired {len(detections)} detections")

if __name__ == "__main__":
    repair_session_026c36cc()
```

---

## Verification

### Database Check
```sql
-- Should return 0
SELECT COUNT(*) FROM detection_events
WHERE test_session_id = '026c36cc-3801-4aa7-971f-b54c24d27505'
AND video_id IS NULL;
```

### Frontend Check
1. Navigate to session results page
2. Select "Video 1" from dropdown
3. Verify detections appear in table
4. Select "Video 2" from dropdown
5. Verify detections appear in table

---

## Related Issues

- Session `463b7ec5`: Same bug, Video 2 shows zero detections
- This is a **systemic regression** affecting all multi-video sessions
- Detection creation logic was working in v7, broken in v8

---

## Next Steps

1. ✅ Root cause identified
2. ⏳ Apply quick repair script to fix existing data
3. ⏳ Implement proper fix in detection creation logic
4. ⏳ Add validation: REQUIRE video_id before detection insert
5. ⏳ Add integration tests to prevent regression
6. ⏳ Audit other sessions for same issue
