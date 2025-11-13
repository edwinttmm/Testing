# Multi-Video Sequential Testing Schema Documentation

## Overview

This document describes the comprehensive database schema for multi-video sequential testing in the AI Model Validation Platform. The schema enables testing multiple videos in a defined sequence with precise timing tracking, individual video results, and detection correlation.

## Migration Information

- **Migration File**: `migrations/add_video_sequence_schema.py`
- **Version**: 2025-09-30
- **Status**: Ready for deployment
- **Backward Compatible**: Yes

## Schema Components

### 1. VideoTestSequence Model

**Purpose**: Container for ordered multi-video test sequences

**Table**: `video_test_sequences`

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | VARCHAR(36) | Primary key (UUID) |
| `test_session_id` | VARCHAR(36) | Foreign key to test_sessions |
| `name` | VARCHAR(255) | Sequence name |
| `video_ids` | JSON | Ordered list of video IDs |
| `sequence_order` | JSON | Detailed order config with duration |
| `status` | VARCHAR(50) | 'pending', 'running', 'completed', 'failed' |
| `max_latency_ms` | INTEGER | Latency threshold for all videos |
| `current_video_index` | INTEGER | Currently playing video (0-indexed) |
| `total_videos` | INTEGER | Total number of videos |
| `completed_videos` | INTEGER | Number of completed videos |
| `sequence_start_time` | FLOAT | Unix timestamp sequence start |
| `sequence_start_time_ns` | VARCHAR(50) | Nanosecond precision start |
| `sequence_end_time` | FLOAT | Unix timestamp sequence end |
| `total_duration_ms` | FLOAT | Total sequence duration |

**Relationships**:
- Belongs to: `TestSession` (CASCADE delete)
- Has many: `SequenceVideoResult` (CASCADE delete)

**Indexes**:
- `idx_video_seq_session`: Fast session lookup
- `idx_video_seq_status`: Status filtering
- `idx_video_seq_session_status`: Combined session + status
- `idx_video_seq_progress`: Progress tracking queries
- `idx_video_seq_timing`: Timing analysis

**Status Flow**:
```
pending → running → completed
                 ↓
              failed/cancelled
```

### 2. SequenceVideoResult Model

**Purpose**: Individual video results within a sequence

**Table**: `sequence_video_results`

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | VARCHAR(36) | Primary key (UUID) |
| `video_sequence_id` | VARCHAR(36) | Foreign key to video_test_sequences |
| `video_id` | VARCHAR(36) | Foreign key to videos |
| `sequence_order` | INTEGER | Position in sequence (0-indexed) |
| `video_start_time` | FLOAT | Video start timestamp |
| `video_start_time_ns` | VARCHAR(50) | Nanosecond precision start |
| `video_end_time` | FLOAT | Video end timestamp |
| `actual_duration_ms` | FLOAT | Actual playback duration |
| `video_play_offset_ms` | FLOAT | Offset from sequence start (dynamic) |
| `video_status` | VARCHAR(50) | 'pending', 'playing', 'completed', 'failed' |
| `validation_result` | VARCHAR(50) | 'Pass', 'Fail', 'Error' |
| `expected_detection_count` | INTEGER | Expected detections from ground truth |
| `actual_detection_count` | INTEGER | Actual detections recorded |
| `passed_detections` | INTEGER | Detections passing latency threshold |
| `failed_detections` | INTEGER | Detections failing latency threshold |
| `avg_latency_ms` | FLOAT | Average latency for this video |
| `max_latency_ms` | FLOAT | Maximum latency |
| `min_latency_ms` | FLOAT | Minimum latency |
| `pass_rate_percent` | FLOAT | Pass rate percentage |
| `latency_threshold_ms` | INTEGER | Threshold used for validation |

**Relationships**:
- Belongs to: `VideoTestSequence` (CASCADE delete)
- Belongs to: `Video` (CASCADE delete)
- Has many: `DetectionEvent` (CASCADE delete)

**Indexes**:
- `idx_seq_video_result_sequence`: Sequence lookup
- `idx_seq_video_result_video`: Video lookup
- `idx_seq_video_result_order`: Order within sequence
- `idx_seq_video_result_latency`: Latency analysis
- `idx_seq_video_result_pass_rate`: Pass rate filtering
- `idx_seq_video_result_detection_counts`: Detection metrics

**Video Status Flow**:
```
pending → playing → completed
                 ↓
              failed
```

### 3. DetectionEvent Enhancements

**Purpose**: Enhanced detection events with video-relative and sequence-relative timing

**New Fields Added**:

| Field | Type | Description |
|-------|------|-------------|
| `sequence_video_result_id` | VARCHAR(36) | Links to sequence video result |
| `video_relative_timestamp` | FLOAT | Timestamp from video start (seconds) |
| `video_relative_timestamp_ns` | VARCHAR(50) | Nanosecond precision video-relative |
| `sequence_timestamp` | FLOAT | Timestamp from sequence start (seconds) |
| `sequence_timestamp_ns` | VARCHAR(50) | Nanosecond precision sequence-relative |
| `video_play_offset_ms` | FLOAT | Video offset from sequence start |
| `correlation_method` | VARCHAR(50) | 'timestamp' or 'frame_number' |

**New Indexes**:
- `idx_detection_sequence_video_result`: Sequence result queries
- `idx_detection_sequence_timestamp`: Sequence timing analysis
- `idx_detection_video_relative_timestamp`: Video timing analysis
- `idx_detection_correlation_method`: Correlation method filtering
- `idx_detection_seq_video_validation`: Combined sequence + validation
- `idx_detection_seq_video_latency`: Combined sequence + latency

**Relationship**:
- Belongs to: `SequenceVideoResult` (SET NULL on delete)

### 4. TestSession Enhancements

**Purpose**: Flag to identify sessions using video sequences

**New Fields Added**:

| Field | Type | Description |
|-------|------|-------------|
| `has_video_sequence` | BOOLEAN | Whether session uses video sequences |

**New Index**:
- `idx_testsession_sequence_flag`: Filter sessions by sequence usage

**Relationship**:
- Has many: `VideoTestSequence` (CASCADE delete)

## Timing Architecture

### Three-Level Timing System

1. **Sequence-Level Timing** (VideoTestSequence)
   - `sequence_start_time`: When entire sequence began
   - `sequence_end_time`: When entire sequence ended
   - `total_duration_ms`: Total elapsed time

2. **Video-Level Timing** (SequenceVideoResult)
   - `video_start_time`: When this video began playing
   - `video_end_time`: When this video ended
   - `video_play_offset_ms`: Offset from sequence start

3. **Detection-Level Timing** (DetectionEvent)
   - `timestamp`: Original LabJack timestamp
   - `video_relative_timestamp`: Time since video start
   - `sequence_timestamp`: Time since sequence start
   - `actual_latency_ms`: Latency measurement

### Timing Calculation Examples

**Example 1: Three-video sequence**
```
Sequence starts at t=0
Video 1: 0-10s (offset: 0ms)
Video 2: 10-25s (offset: 10000ms)
Video 3: 25-40s (offset: 25000ms)

Detection at sequence_timestamp=22.5s:
- In Video 2
- video_relative_timestamp = 12.5s
- video_play_offset_ms = 10000ms
```

**Example 2: Detection correlation**
```python
# Given:
sequence_start_time = 1609459200.0  # Unix timestamp
video_play_offset_ms = 15000  # Video started 15s into sequence
labjack_timestamp = 1609459227.5  # LabJack detection time

# Calculate:
sequence_timestamp = labjack_timestamp - sequence_start_time  # 27.5s
video_relative_timestamp = sequence_timestamp - (video_play_offset_ms / 1000)  # 12.5s
```

## API Schemas

### Pydantic Models (schemas.py)

#### VideoTestSequenceCreate
```python
{
    "name": "Multi-Video HIL Test",
    "videoIds": ["video-uuid-1", "video-uuid-2", "video-uuid-3"],
    "maxLatencyMs": 100,
    "sequenceOrder": [
        {"videoId": "video-uuid-1", "order": 0, "durationMs": 10000},
        {"videoId": "video-uuid-2", "order": 1, "durationMs": 15000},
        {"videoId": "video-uuid-3", "order": 2, "durationMs": 15000}
    ]
}
```

#### VideoTestSequenceResponse
```python
{
    "id": "sequence-uuid",
    "testSessionId": "session-uuid",
    "name": "Multi-Video HIL Test",
    "videoIds": ["video-uuid-1", "video-uuid-2", "video-uuid-3"],
    "status": "running",
    "currentVideoIndex": 1,
    "totalVideos": 3,
    "completedVideos": 1,
    "sequenceStartTime": 1609459200.0,
    "totalDurationMs": 40000.0
}
```

#### SequenceVideoResultResponse
```python
{
    "id": "result-uuid",
    "videoSequenceId": "sequence-uuid",
    "videoId": "video-uuid-2",
    "sequenceOrder": 1,
    "videoStartTime": 1609459210.0,
    "videoPlayOffsetMs": 10000.0,
    "videoStatus": "completed",
    "validationResult": "Pass",
    "expectedDetectionCount": 10,
    "actualDetectionCount": 10,
    "passedDetections": 9,
    "failedDetections": 1,
    "avgLatencyMs": 85.3,
    "passRatePercent": 90.0
}
```

## Migration Execution

### Run Migration
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 migrations/add_video_sequence_schema.py
```

### Rollback Migration
```bash
python3 migrations/add_video_sequence_schema.py rollback
```

### Verification
The migration includes automatic verification that checks:
- All new tables were created
- All new columns were added
- All indexes were created successfully
- Foreign key constraints are in place

## Usage Examples

### Create a Video Sequence

```python
from models import VideoTestSequence, TestSession
from database import SessionLocal

db = SessionLocal()

# Create video sequence
sequence = VideoTestSequence(
    test_session_id="session-uuid",
    name="Pedestrian Detection Sequence",
    video_ids=["video-1", "video-2", "video-3"],
    sequence_order=[
        {"video_id": "video-1", "order": 0, "duration_ms": 10000},
        {"video_id": "video-2", "order": 1, "duration_ms": 15000},
        {"video_id": "video-3", "order": 2, "duration_ms": 15000}
    ],
    total_videos=3,
    max_latency_ms=100
)

db.add(sequence)
db.commit()
```

### Record Video Results

```python
from models import SequenceVideoResult
import time

# Record result for first video in sequence
result = SequenceVideoResult(
    video_sequence_id=sequence.id,
    video_id="video-1",
    sequence_order=0,
    video_start_time=time.time(),
    video_play_offset_ms=0,
    expected_detection_count=5
)

db.add(result)
db.commit()
```

### Record Detection with Sequence Context

```python
from models import DetectionEvent

# Detection at 12.5 seconds into video 2
# Video 2 started at 10s into sequence
detection = DetectionEvent(
    test_session_id="session-uuid",
    video_id="video-2",
    sequence_video_result_id=result.id,
    timestamp=labjack_timestamp,
    sequence_timestamp=22.5,  # 22.5s from sequence start
    video_relative_timestamp=12.5,  # 12.5s from video start
    video_play_offset_ms=10000,  # Video 2 offset
    correlation_method="timestamp",
    actual_latency_ms=85.0,
    validation_result="Pass"
)

db.add(detection)
db.commit()
```

### Query Sequence Statistics

```python
from sqlalchemy import func

# Get aggregated statistics for sequence
stats = db.query(
    VideoTestSequence.id,
    VideoTestSequence.status,
    func.count(SequenceVideoResult.id).label('total_videos'),
    func.sum(SequenceVideoResult.passed_detections).label('total_passed'),
    func.sum(SequenceVideoResult.failed_detections).label('total_failed'),
    func.avg(SequenceVideoResult.avg_latency_ms).label('overall_avg_latency')
).join(SequenceVideoResult).filter(
    VideoTestSequence.id == sequence.id
).group_by(VideoTestSequence.id).first()
```

## Performance Considerations

### Indexes
All critical query paths are indexed:
- Session → Sequence lookup
- Sequence → Video Results lookup
- Video Results → Detection Events lookup
- Timing-based queries (sequence_timestamp, video_relative_timestamp)
- Status filtering (sequence status, video status)
- Validation filtering (pass/fail results)

### Query Optimization
Use composite indexes for common queries:
```sql
-- Fast sequence + status filtering
SELECT * FROM video_test_sequences
WHERE test_session_id = ? AND status = ?;
-- Uses: idx_video_seq_session_status

-- Fast video results by sequence order
SELECT * FROM sequence_video_results
WHERE video_sequence_id = ?
ORDER BY sequence_order;
-- Uses: idx_seq_video_result_order
```

### Cascade Deletes
Proper CASCADE relationships ensure data integrity:
- Delete TestSession → Deletes VideoTestSequence → Deletes SequenceVideoResult → Deletes DetectionEvents
- Delete Video → Deletes SequenceVideoResult (preserves sequence structure)

## Backward Compatibility

### Single-Video Sessions
- Existing single-video sessions continue to work
- `has_video_sequence = False` by default
- All existing DetectionEvents remain valid
- New sequence fields are nullable

### Migration Safety
- Uses `IF NOT EXISTS` checks
- Safe column addition
- Index creation is idempotent
- No data loss during migration

## Testing Requirements

### Unit Tests
- Model creation and relationships
- Timing calculations
- Status transitions
- Cascade deletes

### Integration Tests
- End-to-end sequence creation
- Multi-video playback simulation
- Detection correlation accuracy
- Statistics aggregation

### Performance Tests
- Large sequences (100+ videos)
- High detection rates (1000+ detections/video)
- Query performance benchmarks
- Index effectiveness

## Future Enhancements

### Planned Features
1. **Sequence Templates**: Pre-configured video sequences
2. **Dynamic Reordering**: Change video order mid-sequence
3. **Parallel Sequences**: Multiple sequences in one session
4. **Sequence Analytics**: Advanced statistics and visualizations
5. **Auto-Recovery**: Resume interrupted sequences

### Schema Extensions
1. Add `sequence_template_id` for templates
2. Add `parallel_sequence_group_id` for parallel execution
3. Add `resume_checkpoint` for recovery
4. Add `sequence_metadata` JSON for custom data

## Conclusion

This schema provides a robust foundation for multi-video sequential testing with:
- ✅ Precise timing tracking at three levels
- ✅ Individual video result isolation
- ✅ Detection correlation with video context
- ✅ Comprehensive statistics per video and sequence
- ✅ Performance-optimized indexes
- ✅ Full backward compatibility
- ✅ Data integrity through relationships
- ✅ Extensibility for future features

The migration is production-ready and can be deployed with confidence.