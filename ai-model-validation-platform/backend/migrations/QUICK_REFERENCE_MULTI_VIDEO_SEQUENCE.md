# Multi-Video Sequential Testing - Quick Reference Guide

## 📋 Table of Contents
1. [Overview](#overview)
2. [Database Tables](#database-tables)
3. [Key Fields](#key-fields)
4. [Relationships](#relationships)
5. [API Examples](#api-examples)
6. [Common Queries](#common-queries)
7. [Deployment](#deployment)

## Overview

Multi-video sequential testing enables testing multiple videos in a defined sequence with precise timing correlation and per-video results tracking.

## Database Tables

### 1. `video_test_sequences`
**Purpose**: Container for ordered video sequences

```sql
CREATE TABLE video_test_sequences (
    id VARCHAR(36) PRIMARY KEY,
    test_session_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    video_ids JSON NOT NULL,
    sequence_order JSON NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    max_latency_ms INTEGER DEFAULT 100,
    current_video_index INTEGER DEFAULT 0,
    total_videos INTEGER NOT NULL,
    completed_videos INTEGER DEFAULT 0,
    sequence_start_time FLOAT,
    sequence_start_time_ns VARCHAR(50),
    sequence_end_time FLOAT,
    total_duration_ms FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
);
```

### 2. `sequence_video_results`
**Purpose**: Individual video results within sequences

```sql
CREATE TABLE sequence_video_results (
    id VARCHAR(36) PRIMARY KEY,
    video_sequence_id VARCHAR(36) NOT NULL,
    video_id VARCHAR(36) NOT NULL,
    sequence_order INTEGER NOT NULL,
    video_start_time FLOAT,
    video_end_time FLOAT,
    actual_duration_ms FLOAT,
    video_play_offset_ms FLOAT,
    video_status VARCHAR(50) DEFAULT 'pending',
    validation_result VARCHAR(50),
    expected_detection_count INTEGER DEFAULT 0,
    actual_detection_count INTEGER DEFAULT 0,
    passed_detections INTEGER DEFAULT 0,
    failed_detections INTEGER DEFAULT 0,
    avg_latency_ms FLOAT,
    pass_rate_percent FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_sequence_id) REFERENCES video_test_sequences(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);
```

### 3. Enhanced `detection_events`
**New Fields Added**:
- `sequence_video_result_id` - Links to sequence video result
- `sequence_timestamp` - Time from sequence start
- `video_play_offset_ms` - Video offset in sequence
- `correlation_method` - How detection is correlated

### 4. Enhanced `test_sessions`
**New Fields Added**:
- `has_video_sequence` - Boolean flag for sequence sessions

## Key Fields

### Status Values

**VideoTestSequence.status**:
- `pending` - Not started
- `running` - Currently executing
- `completed` - Successfully finished
- `failed` - Execution failed
- `cancelled` - User cancelled

**SequenceVideoResult.video_status**:
- `pending` - Waiting to play
- `playing` - Currently playing
- `completed` - Finished playing
- `failed` - Playback failed

**SequenceVideoResult.validation_result**:
- `Pass` - All detections within threshold
- `Fail` - Some detections exceeded threshold
- `Error` - Processing error

### Timing Fields

**Sequence-Level** (VideoTestSequence):
```python
sequence_start_time      # Unix timestamp: 1609459200.0
sequence_start_time_ns   # Nanosecond precision: "1609459200123456789"
sequence_end_time        # Unix timestamp: 1609459240.0
total_duration_ms        # Total duration: 40000.0
```

**Video-Level** (SequenceVideoResult):
```python
video_start_time         # Unix timestamp: 1609459210.0
video_end_time          # Unix timestamp: 1609459225.0
actual_duration_ms      # Actual duration: 15000.0
video_play_offset_ms    # Offset from sequence: 10000.0
```

**Detection-Level** (DetectionEvent):
```python
timestamp               # LabJack timestamp: 1609459227.5
sequence_timestamp      # From sequence start: 27.5
video_relative_timestamp # From video start: 12.5
video_play_offset_ms    # Video offset: 10000.0
```

## Relationships

```
TestSession
  └── has_video_sequence = True
  └── VideoTestSequence (many)
        └── SequenceVideoResult (many)
              └── DetectionEvent (many)
```

**Cascade Behavior**:
- Delete TestSession → Deletes VideoTestSequence
- Delete VideoTestSequence → Deletes SequenceVideoResult
- Delete SequenceVideoResult → Deletes DetectionEvents

## API Examples

### Create Sequence

```python
from models import VideoTestSequence
from database import SessionLocal

db = SessionLocal()

sequence = VideoTestSequence(
    test_session_id="session-uuid",
    name="Multi-Video HIL Test",
    video_ids=["vid1", "vid2", "vid3"],
    sequence_order=[
        {"video_id": "vid1", "order": 0, "duration_ms": 10000},
        {"video_id": "vid2", "order": 1, "duration_ms": 15000},
        {"video_id": "vid3", "order": 2, "duration_ms": 15000}
    ],
    total_videos=3,
    max_latency_ms=100,
    status="pending"
)

db.add(sequence)
db.commit()
```

### Record Video Result

```python
from models import SequenceVideoResult
import time

result = SequenceVideoResult(
    video_sequence_id=sequence.id,
    video_id="vid1",
    sequence_order=0,
    video_start_time=time.time(),
    video_play_offset_ms=0,
    video_status="playing",
    expected_detection_count=10
)

db.add(result)
db.commit()
```

### Record Detection

```python
from models import DetectionEvent

detection = DetectionEvent(
    test_session_id=session.id,
    video_id="vid2",
    sequence_video_result_id=result.id,
    timestamp=labjack_timestamp,
    sequence_timestamp=22.5,
    video_relative_timestamp=12.5,
    video_play_offset_ms=10000,
    correlation_method="timestamp",
    actual_latency_ms=85.0,
    validation_result="Pass"
)

db.add(detection)
db.commit()
```

## Common Queries

### Get Sequence with Results

```python
from models import VideoTestSequence, SequenceVideoResult
from sqlalchemy.orm import joinedload

sequence = db.query(VideoTestSequence)\
    .options(joinedload(VideoTestSequence.video_results))\
    .filter(VideoTestSequence.id == sequence_id)\
    .first()

# Access results
for result in sequence.video_results:
    print(f"Video {result.sequence_order}: {result.pass_rate_percent}% pass rate")
```

### Get Video Results in Order

```python
results = db.query(SequenceVideoResult)\
    .filter(SequenceVideoResult.video_sequence_id == sequence_id)\
    .order_by(SequenceVideoResult.sequence_order)\
    .all()
```

### Get Detections for Video in Sequence

```python
detections = db.query(DetectionEvent)\
    .filter(DetectionEvent.sequence_video_result_id == result_id)\
    .order_by(DetectionEvent.sequence_timestamp)\
    .all()
```

### Calculate Sequence Statistics

```python
from sqlalchemy import func

stats = db.query(
    func.count(SequenceVideoResult.id).label('total_videos'),
    func.sum(SequenceVideoResult.passed_detections).label('total_passed'),
    func.sum(SequenceVideoResult.failed_detections).label('total_failed'),
    func.avg(SequenceVideoResult.avg_latency_ms).label('avg_latency')
).filter(
    SequenceVideoResult.video_sequence_id == sequence_id
).first()

pass_rate = (stats.total_passed / (stats.total_passed + stats.total_failed)) * 100
```

### Find Failed Videos

```python
failed_videos = db.query(SequenceVideoResult)\
    .filter(
        SequenceVideoResult.video_sequence_id == sequence_id,
        SequenceVideoResult.validation_result == 'Fail'
    )\
    .all()
```

### Get Progress

```python
sequence = db.query(VideoTestSequence)\
    .filter(VideoTestSequence.id == sequence_id)\
    .first()

progress = {
    "current_index": sequence.current_video_index,
    "total_videos": sequence.total_videos,
    "completed": sequence.completed_videos,
    "status": sequence.status,
    "progress_percent": (sequence.completed_videos / sequence.total_videos) * 100
}
```

## Deployment

### Step 1: Verify Schema
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 migrations/verify_sequence_schema.py
```

**Expected Output**: ✅ ALL VERIFICATIONS PASSED

### Step 2: Run Migration
```bash
python3 migrations/add_video_sequence_schema.py
```

**Expected Output**:
```
=======================================================================
🚀 Starting Multi-Video Sequential Testing Schema Migration
=======================================================================
✅ test_sessions table upgraded
✅ video_test_sequences table created
✅ sequence_video_results table created
✅ detection_events table upgraded
✅ Migration verification passed
=======================================================================
✅ Multi-Video Sequential Testing Schema Migration Completed Successfully
=======================================================================
```

### Step 3: Verify Migration
```bash
python3 -c "
from models import VideoTestSequence, SequenceVideoResult
print('✅ Models imported successfully')
"
```

### Step 4: Test Database Connection
```python
from database import SessionLocal
from models import VideoTestSequence

db = SessionLocal()

# Check table exists
count = db.query(VideoTestSequence).count()
print(f"✅ video_test_sequences table accessible (count: {count})")

db.close()
```

### Rollback (if needed)
```bash
python3 migrations/add_video_sequence_schema.py rollback
```

## Timing Calculations

### Calculate Sequence Timestamp
```python
# Given LabJack detection at absolute time
labjack_timestamp = 1609459227.5
sequence_start_time = 1609459200.0

sequence_timestamp = labjack_timestamp - sequence_start_time
# Result: 27.5 seconds from sequence start
```

### Calculate Video Relative Timestamp
```python
# Given sequence timestamp and video offset
sequence_timestamp = 27.5  # seconds
video_play_offset_ms = 10000  # 10 seconds

video_relative_timestamp = sequence_timestamp - (video_play_offset_ms / 1000)
# Result: 12.5 seconds from video start
```

### Calculate Video Play Offset
```python
# For video at position 2 in sequence
previous_videos = [
    {"duration_ms": 10000},  # Video 0
    {"duration_ms": 15000}   # Video 1
]

video_play_offset_ms = sum(v["duration_ms"] for v in previous_videos)
# Result: 25000 ms (25 seconds into sequence)
```

## Error Handling

### Common Issues

**Issue**: Foreign key constraint violation
```python
# Solution: Ensure parent records exist
session = db.query(TestSession).filter_by(id=session_id).first()
if not session:
    raise ValueError("Test session not found")

video = db.query(Video).filter_by(id=video_id).first()
if not video:
    raise ValueError("Video not found")
```

**Issue**: Sequence timing inconsistency
```python
# Solution: Validate timing before recording
if video_start_time < sequence.sequence_start_time:
    raise ValueError("Video start time before sequence start")

if video_play_offset_ms < 0:
    raise ValueError("Invalid video offset")
```

**Issue**: Detection correlation failure
```python
# Solution: Verify detection falls within video bounds
video_duration_s = result.actual_duration_ms / 1000
if video_relative_timestamp > video_duration_s:
    logger.warning(f"Detection at {video_relative_timestamp}s exceeds video duration {video_duration_s}s")
```

## Performance Tips

### Use Indexes
All critical query paths are indexed:
```python
# Fast queries
db.query(VideoTestSequence).filter_by(test_session_id=session_id)  # Uses idx_video_seq_session
db.query(SequenceVideoResult).filter_by(video_sequence_id=seq_id)  # Uses idx_seq_video_result_sequence
db.query(DetectionEvent).filter_by(sequence_video_result_id=res_id)  # Uses idx_detection_sequence_video_result
```

### Batch Operations
```python
# Good: Batch insert
results = [SequenceVideoResult(...) for video in videos]
db.bulk_save_objects(results)
db.commit()

# Avoid: Individual commits
for video in videos:
    result = SequenceVideoResult(...)
    db.add(result)
    db.commit()  # Slow!
```

### Eager Loading
```python
# Good: Load relationships upfront
from sqlalchemy.orm import joinedload

sequence = db.query(VideoTestSequence)\
    .options(joinedload(VideoTestSequence.video_results))\
    .first()

# Avoid: Lazy loading in loops
for result in sequence.video_results:  # No additional queries
    print(result.avg_latency_ms)
```

## Next Steps

1. ✅ Schema deployed
2. Create API endpoints (`/api/sequences/*`)
3. Implement sequence execution service
4. Add WebSocket progress updates
5. Build frontend sequence player
6. Add sequence analytics dashboard

## Support

For issues or questions:
- See full documentation: `MULTI_VIDEO_SEQUENCE_SCHEMA_DOCUMENTATION.md`
- See implementation summary: `MULTI_VIDEO_SEQUENCE_IMPLEMENTATION_SUMMARY.md`
- Run verification: `python3 migrations/verify_sequence_schema.py`