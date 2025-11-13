# Multi-Video Schema - Quick Reference Guide

## Schema Status: ✅ IMPLEMENTED | ⚠️ FK ENFORCEMENT NEEDED

---

## 1. Quick Status

```
✅ TestSession.has_video_sequence        (Boolean, indexed)
✅ TestSession.sequence_id               (VARCHAR, indexed)
✅ VideoTestSequence table               (17 fields, 6 indexes)
✅ SequenceVideoResult table             (25 fields, 10 indexes)
✅ DetectionEvent.video_id               (TEXT, indexed, FK defined)
✅ DetectionEvent multi-video fields     (9 fields, 10 indexes)
⚠️ Foreign key enforcement               (DISABLED - needs fix)
```

**Data:** 33 sequences | 66 results | 35 sessions active

---

## 2. Database Tables

### TestSession
```python
has_video_sequence: bool = False        # Multi-video flag
sequence_id: str = None                 # Unique sequence ID
sequence_metadata: dict = None          # Video timing metadata
```

### VideoTestSequence
```python
id: str                                 # Primary key
test_session_id: str                    # FK to test_sessions (CASCADE)
name: str                               # Sequence name
video_ids: list[str]                    # Ordered video IDs [vid1, vid2, ...]
sequence_order: list[dict]              # [{video_id, order, duration_ms}, ...]
status: str                             # pending|running|completed|failed
current_video_index: int = 0            # Currently playing video
total_videos: int                       # Total videos in sequence
completed_videos: int = 0               # Videos finished
sequence_start_time: float              # Unix timestamp (seconds)
sequence_start_time_ns: str             # Nanosecond precision
```

### SequenceVideoResult
```python
id: str                                 # Primary key
video_sequence_id: str                  # FK to video_test_sequences (CASCADE)
video_id: str                           # FK to videos (CASCADE)
sequence_order: int                     # Position in sequence (0-indexed)
video_start_time: float                 # When this video started
video_play_offset_ms: float             # Offset from sequence start
video_status: str                       # pending|playing|completed|failed
validation_result: str                  # Pass|Fail|Error
actual_detection_count: int             # Detections recorded
passed_detections: int                  # Detections within threshold
failed_detections: int                  # Detections exceeding threshold
avg_latency_ms: float                   # Average latency
pass_rate_percent: float                # Success rate
```

### DetectionEvent (Multi-Video Fields)
```python
video_id: str                           # FK to videos
sequence_video_result_id: str           # FK to sequence_video_results
sequence_id: str                        # Sequence identifier
video_relative_timestamp: float         # Time since video start (seconds)
video_frame_number: int                 # Frame number in video
sequence_timestamp: float               # Time since sequence start (seconds)
video_play_offset_ms: float             # Video offset in sequence
correlation_method: str                 # timestamp|frame_number
timing_sync_quality: str                # high|medium|low
actual_latency_ms: float                # Measured latency
```

---

## 3. Query Examples

### Get Sequence with Results
```python
from sqlalchemy.orm import selectinload

session = db.query(TestSession).filter(
    TestSession.has_video_sequence == True,
    TestSession.id == session_id
).options(
    selectinload(TestSession.video_sequences)
    .selectinload(VideoTestSequence.video_results)
).first()

# Access data
sequence = session.video_sequences[0]
print(f"Videos: {sequence.total_videos}")
print(f"Status: {sequence.status}")

for result in sequence.video_results:
    print(f"Video {result.sequence_order}: {result.validation_result}")
    print(f"  Pass Rate: {result.pass_rate_percent}%")
    print(f"  Avg Latency: {result.avg_latency_ms}ms")
```

### Get Detections for Specific Video
```python
detections = db.query(DetectionEvent).filter(
    DetectionEvent.video_id == video_id,
    DetectionEvent.sequence_video_result_id == seq_result_id
).order_by(DetectionEvent.video_relative_timestamp).all()

for det in detections:
    print(f"Frame {det.video_frame_number}: {det.actual_latency_ms}ms")
```

### Get All Videos in Sequence
```python
results = db.query(SequenceVideoResult).filter(
    SequenceVideoResult.video_sequence_id == seq_id
).order_by(SequenceVideoResult.sequence_order).all()

for r in results:
    print(f"{r.sequence_order}. Video {r.video_id}: {r.video_status}")
```

---

## 4. Relationships Diagram

```
TestSession (1)
    ├─ has_video_sequence: bool
    ├─ sequence_id: str
    └─ video_sequences ────────────────┐
                                       │
VideoTestSequence (Many)               │ 1:Many (CASCADE)
    ├─ test_session_id ────────────────┘
    ├─ video_ids: [id1, id2, ...]
    └─ video_results ──────────────────┐
                                       │
SequenceVideoResult (Many)             │ 1:Many (CASCADE)
    ├─ video_sequence_id ──────────────┘
    ├─ video_id ───────────────────────┐
    └─ detection_events ───────────┐   │
                                   │   │
DetectionEvent (Many)              │   │ Many:1 (CASCADE)
    ├─ sequence_video_result_id ───┘   │
    ├─ video_id ───────────────────────┘
    ├─ video_relative_timestamp
    └─ sequence_timestamp
```

---

## 5. Indexes for Performance

### VideoTestSequence (6 indexes)
```sql
idx_video_seq_session                   (test_session_id)
idx_video_seq_status                    (status)
idx_video_seq_session_status            (test_session_id, status)
idx_video_seq_created                   (created_at)
idx_video_seq_progress                  (current_video_index, total_videos)
idx_video_seq_timing                    (sequence_start_time)
```

### SequenceVideoResult (10 indexes)
```sql
idx_seq_video_result_sequence           (video_sequence_id)
idx_seq_video_result_video              (video_id)
idx_seq_video_result_order              (video_sequence_id, sequence_order)
idx_seq_video_result_status             (video_status)
idx_seq_video_result_validation         (validation_result)
idx_seq_video_result_latency            (avg_latency_ms)
idx_seq_video_result_pass_rate          (pass_rate_percent)
idx_seq_video_result_timing             (video_start_time)
idx_seq_video_result_sequence_status    (video_sequence_id, video_status)
idx_seq_video_result_detection_counts   (expected_detection_count, actual_detection_count)
```

### DetectionEvent Multi-Video (10 indexes)
```sql
idx_detection_video_timestamp           (video_id, timestamp)
idx_detection_video_validation          (video_id, validation_result)
idx_detection_sequence_video_result     (sequence_video_result_id)
idx_detection_sequence_timestamp        (sequence_timestamp)
idx_detection_video_relative_timestamp  (video_relative_timestamp)
idx_detection_correlation_method        (correlation_method)
idx_detection_seq_video_validation      (sequence_video_result_id, validation_result)
idx_detection_seq_video_latency         (sequence_video_result_id, actual_latency_ms)
```

---

## 6. Foreign Keys

### Defined (but NOT enforced) ⚠️
```sql
-- VideoTestSequence
FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE

-- SequenceVideoResult
FOREIGN KEY (video_sequence_id) REFERENCES video_test_sequences(id) ON DELETE CASCADE
FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE

-- DetectionEvent
FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
FOREIGN KEY (sequence_video_result_id) REFERENCES sequence_video_results(id) ON DELETE SET NULL
FOREIGN KEY (ground_truth_match_id) REFERENCES ground_truth_objects(id) ON DELETE SET NULL
```

**Problem:** `PRAGMA foreign_keys = 0` (DISABLED)

---

## 7. CRITICAL FIX REQUIRED 🚨

### Enable Foreign Key Enforcement

**File:** `database.py`

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key enforcement for all SQLite connections"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

**Priority:** HIGH - Required before production deployment

---

## 8. Cascade Delete Behavior

```
DELETE TestSession
    ↓ CASCADE
DELETE VideoTestSequence
    ↓ CASCADE
DELETE SequenceVideoResult
    ↓ CASCADE (via relationship)
DELETE DetectionEvent
```

**Note:** Cascade works via SQLAlchemy ORM, but NOT enforced at DB level until FK enforcement enabled.

---

## 9. Status Values

### VideoTestSequence.status
- `pending` - Created, not started
- `running` - Currently executing
- `completed` - All videos finished successfully
- `failed` - Error occurred
- `cancelled` - User cancelled

### SequenceVideoResult.video_status
- `pending` - Waiting to play
- `playing` - Currently playing
- `completed` - Finished successfully
- `failed` - Error occurred

### SequenceVideoResult.validation_result
- `Pass` - All detections within threshold
- `Fail` - One or more detections exceeded threshold
- `Error` - Error during validation

---

## 10. Typical Workflow

```python
# 1. Create test session
session = TestSession(
    name="Multi-Video Test",
    project_id=project_id,
    video_id=video_ids[0],  # First video
    has_video_sequence=True,
    sequence_id=str(uuid.uuid4())
)

# 2. Create video sequence
sequence = VideoTestSequence(
    test_session_id=session.id,
    name="Test Sequence",
    video_ids=video_ids,
    sequence_order=[
        {"video_id": vid1, "order": 0, "duration_ms": 5000},
        {"video_id": vid2, "order": 1, "duration_ms": 5000}
    ],
    total_videos=len(video_ids),
    max_latency_ms=100,
    status="pending"
)

# 3. Create video results for each video
for i, video_id in enumerate(video_ids):
    result = SequenceVideoResult(
        video_sequence_id=sequence.id,
        video_id=video_id,
        sequence_order=i,
        video_status="pending",
        latency_threshold_ms=100
    )
    db.add(result)

# 4. During playback, record detections
detection = DetectionEvent(
    test_session_id=session.id,
    video_id=current_video_id,
    sequence_video_result_id=current_result_id,
    sequence_id=sequence.id,
    timestamp=labjack_timestamp,
    video_relative_timestamp=video_time,
    sequence_timestamp=sequence_time,
    video_play_offset_ms=video_offset,
    actual_latency_ms=latency,
    validation_result="Pass" if latency < 100 else "Fail"
)

# 5. Update result statistics
result.actual_detection_count += 1
if detection.validation_result == "Pass":
    result.passed_detections += 1
else:
    result.failed_detections += 1

result.pass_rate_percent = (
    result.passed_detections / result.actual_detection_count * 100
)
```

---

## 11. Production Checklist

- [x] Schema implemented (100%)
- [x] Models defined (100%)
- [x] Relationships configured (100%)
- [x] Indexes created (26 indexes)
- [x] Foreign keys defined (100%)
- [ ] **Foreign keys enforced** ⚠️ **REQUIRED**
- [x] Real data exists (33 sequences)
- [x] Queries optimized (100%)

**Blocks Production:** Foreign key enforcement disabled

---

**Last Updated:** 2025-10-30
**Full Analysis:** `MULTI_VIDEO_SCHEMA_ANALYSIS_REPORT.md`
**Executive Summary:** `MULTI_VIDEO_SCHEMA_EXECUTIVE_SUMMARY.md`
