# Video Lifecycle Tracking Implementation

**Created**: 2025-11-20
**Migration ID**: `f18f8e9c1590_add_video_lifecycle_tracking`
**Status**: Ready for Production

---

## Overview

This implementation adds comprehensive video lifecycle event tracking for precise drift calculation in Hardware-in-the-Loop (HIL) testing. It enables accurate timestamp correlation between browser events, backend processing, and LabJack hardware timing.

## Key Features

### 1. **New Table: video_lifecycle_events**
Dedicated table for tracking VIDEO_START, VIDEO_END, and VIDEO_ERROR events with complete timestamp chain for drift calculation.

### 2. **Drift Compensation Fields**
- `drift_compensated_timestamp` in detection_events
- `original_timestamp` in detection_events (preserved for debugging)
- `average_drift_ms` in test_sessions

### 3. **Automatic Drift Calculation**
Database trigger automatically calculates drift when VIDEO_END event is inserted by comparing with VIDEO_START.

### 4. **Drift Analysis View**
`video_drift_summary` view provides easy access to drift metrics across all test sessions.

---

## Schema Design

### video_lifecycle_events Table

```sql
CREATE TABLE video_lifecycle_events (
    id UUID PRIMARY KEY,
    test_session_id UUID NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,

    -- Event identification
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('VIDEO_START', 'VIDEO_END', 'VIDEO_ERROR')),

    -- Timestamp chain for drift calculation
    frontend_timestamp FLOAT NOT NULL,              -- Browser performance.now()
    backend_received_timestamp FLOAT NOT NULL,      -- Backend server timestamp
    labjack_command_sent_timestamp FLOAT,           -- T0: LabJack command sent
    labjack_monitoring_timestamp FLOAT,             -- T1: LabJack monitoring started

    -- Clock synchronization and drift
    clock_offset_ms FLOAT,                          -- Browser-backend offset
    calculated_drift_ms FLOAT,                      -- Total drift for video

    -- Additional context
    event_metadata JSONB,                           -- Additional event data

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT ck_lifecycle_drift_range
        CHECK (calculated_drift_ms IS NULL OR
               (calculated_drift_ms >= -1000 AND calculated_drift_ms <= 1000)),
    CONSTRAINT uq_lifecycle_event
        UNIQUE (test_session_id, video_id, event_type)
);
```

### Indexes

```sql
-- Primary query indexes
CREATE INDEX idx_lifecycle_session_event_created
    ON video_lifecycle_events(test_session_id, event_type, created_at);

CREATE INDEX idx_lifecycle_video_event
    ON video_lifecycle_events(video_id, event_type);

-- Drift analysis (partial index for non-null values)
CREATE INDEX idx_lifecycle_drift
    ON video_lifecycle_events(calculated_drift_ms)
    WHERE calculated_drift_ms IS NOT NULL;
```

### Updated Tables

**detection_events**:
- Added `drift_compensated_timestamp` (FLOAT)
- Added `original_timestamp` (FLOAT)
- Added index `idx_detection_drift_timestamp`

**test_sessions**:
- Added `average_drift_ms` (FLOAT)
- Added index `idx_session_average_drift`

---

## Drift Calculation Formula

```python
# For each video in a session:
start_event = video_lifecycle_events.where(event_type='VIDEO_START')
end_event = video_lifecycle_events.where(event_type='VIDEO_END')

# Clock offset at each point
start_offset = start_event.backend_received_timestamp - start_event.frontend_timestamp
end_offset = end_event.backend_received_timestamp - end_event.frontend_timestamp

# Drift is the change in offset over video lifecycle
calculated_drift_ms = end_offset - start_offset
```

### Interpretation

- **Positive drift**: Backend clock is drifting faster than browser clock
- **Negative drift**: Backend clock is drifting slower than browser clock
- **Zero drift**: Clocks remain synchronized
- **Acceptable range**: ±1000ms (enforced by CHECK constraint)

---

## Usage Examples

### 1. Record Video Start Event

```python
from models import VideoLifecycleEvent
import time

# Frontend sends event
frontend_timestamp = 12345.678  # performance.now()
backend_received = time.time()

# Record in database
start_event = VideoLifecycleEvent(
    test_session_id=session_id,
    video_id=video_id,
    event_type='VIDEO_START',
    frontend_timestamp=frontend_timestamp,
    backend_received_timestamp=backend_received,
    labjack_command_sent_timestamp=labjack_t0,  # When LabJack command sent
    labjack_monitoring_timestamp=labjack_t1,    # When LabJack confirmed
    clock_offset_ms=(backend_received * 1000) - frontend_timestamp
)
db.add(start_event)
db.commit()
```

### 2. Record Video End Event (Automatic Drift Calculation)

```python
# Frontend sends event
frontend_timestamp = 18901.234  # performance.now()
backend_received = time.time()

# Record in database
end_event = VideoLifecycleEvent(
    test_session_id=session_id,
    video_id=video_id,
    event_type='VIDEO_END',
    frontend_timestamp=frontend_timestamp,
    backend_received_timestamp=backend_received,
    clock_offset_ms=(backend_received * 1000) - frontend_timestamp
)
db.add(end_event)
db.commit()  # Trigger automatically calculates drift
```

### 3. Apply Drift Compensation to Detections

```python
# Get calculated drift for video
drift = db.query(VideoLifecycleEvent.calculated_drift_ms).filter(
    VideoLifecycleEvent.test_session_id == session_id,
    VideoLifecycleEvent.video_id == video_id,
    VideoLifecycleEvent.event_type == 'VIDEO_END'
).scalar()

# Apply to all detections for this video
db.execute(
    update(DetectionEvent)
    .where(DetectionEvent.test_session_id == session_id)
    .where(DetectionEvent.video_id == video_id)
    .values(
        drift_compensated_timestamp=DetectionEvent.timestamp + drift,
        original_timestamp=DetectionEvent.timestamp
    )
)
```

### 4. Query Drift Summary

```python
# Using the drift summary view
from sqlalchemy import text

drift_summary = db.execute(text("""
    SELECT
        session_name,
        video_filename,
        drift_ms,
        drift_severity
    FROM video_drift_summary
    WHERE test_session_id = :session_id
    ORDER BY drift_ms DESC
"""), {"session_id": session_id}).fetchall()

for row in drift_summary:
    print(f"{row.video_filename}: {row.drift_ms}ms ({row.drift_severity})")
```

---

## API Integration

### Frontend WebSocket Events

```typescript
// Video start event
socket.emit('video_lifecycle_event', {
  sessionId: sessionId,
  videoId: videoId,
  eventType: 'VIDEO_START',
  frontendTimestamp: performance.now(),
  metadata: {
    browserInfo: navigator.userAgent,
    videoMetadata: { duration: video.duration, fps: 30 }
  }
});

// Video end event
socket.emit('video_lifecycle_event', {
  sessionId: sessionId,
  videoId: videoId,
  eventType: 'VIDEO_END',
  frontendTimestamp: performance.now(),
  metadata: {
    actualPlayDuration: actualDuration,
    endReason: 'completed'  // or 'error', 'user_stopped'
  }
});
```

### Backend WebSocket Handler

```python
@socketio.on('video_lifecycle_event')
def handle_video_lifecycle_event(data):
    backend_received = time.time()

    # Extract frontend timestamp
    frontend_ts = data['frontendTimestamp']

    # Calculate clock offset
    clock_offset = (backend_received * 1000) - frontend_ts

    # Create lifecycle event
    event = VideoLifecycleEvent(
        test_session_id=data['sessionId'],
        video_id=data['videoId'],
        event_type=data['eventType'],
        frontend_timestamp=frontend_ts,
        backend_received_timestamp=backend_received,
        clock_offset_ms=clock_offset,
        event_metadata=data.get('metadata', {})
    )

    db.add(event)
    db.commit()

    # If VIDEO_END, drift is automatically calculated by trigger
    if event.event_type == 'VIDEO_END':
        # Refresh to get calculated drift
        db.refresh(event)

        # Apply drift compensation to detections
        apply_drift_compensation(event.test_session_id, event.video_id, event.calculated_drift_ms)

        # Update session average
        update_session_average_drift(event.test_session_id)

    return {'status': 'success', 'drift_ms': event.calculated_drift_ms}
```

---

## Migration Instructions

### Pre-Migration Checklist

```bash
# 1. Backup production database
pg_dump -U postgres -d prod_db > backup_pre_lifecycle_$(date +%Y%m%d).sql

# 2. Verify current migration state
python3 -m alembic current

# 3. Test migration on staging
python3 -m alembic upgrade f18f8e9c1590 --sql > migration_preview.sql
# Review migration_preview.sql before proceeding
```

### Running Migration

```bash
# Production migration
python3 -m alembic upgrade f18f8e9c1590

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade add_video_markers -> f18f8e9c1590
# Creating video_lifecycle_events table...
# Creating indexes for video_lifecycle_events...
# Adding drift compensation columns to detection_events...
# Adding average drift tracking to test_sessions...
# Backfilling original_timestamp for existing detection_events...
# Creating trigger for automatic drift calculation...
# Creating video_drift_summary view...
# Backfilling lifecycle events from existing video_markers...
# Calculating average drift for test sessions...
# Running validation checks...
# === Video Lifecycle Events Migration Summary ===
# Total events created: 1234
#   - VIDEO_START: 617
#   - VIDEO_END: 617
#   - VIDEO_ERROR: 0
# Sessions with drift data: 123
# All videos have matching START/END events
# === Migration completed successfully ===
```

### Post-Migration Validation

```sql
-- 1. Check table created
SELECT COUNT(*) FROM video_lifecycle_events;

-- 2. Verify drift calculations
SELECT
    event_type,
    COUNT(*) as count,
    AVG(calculated_drift_ms) as avg_drift,
    MAX(calculated_drift_ms) as max_drift,
    MIN(calculated_drift_ms) as min_drift
FROM video_lifecycle_events
WHERE calculated_drift_ms IS NOT NULL
GROUP BY event_type;

-- 3. Check detection_events columns
SELECT COUNT(*) FROM detection_events
WHERE original_timestamp IS NOT NULL;

-- 4. Check test_sessions average drift
SELECT COUNT(*) FROM test_sessions
WHERE average_drift_ms IS NOT NULL;

-- 5. Test drift summary view
SELECT * FROM video_drift_summary LIMIT 10;
```

### Rollback (if needed)

```bash
# Downgrade to previous migration
python3 -m alembic downgrade -1

# This will:
# - Drop video_drift_summary view
# - Drop trigger and function
# - Remove columns from test_sessions and detection_events
# - Drop video_lifecycle_events table
```

---

## Performance Considerations

### Query Performance

| Query Type | Index Used | Expected Performance |
|------------|-----------|---------------------|
| Get events for session | `idx_lifecycle_session_event_created` | O(log n) |
| Get events for video | `idx_lifecycle_video_event` | O(1) |
| Drift analysis queries | `idx_lifecycle_drift` | O(log n) |
| Detection drift compensation | `idx_detection_drift_timestamp` | O(log n) |

### Storage Overhead

- **Per video**: ~200 bytes (2 events: START + END)
- **1,000 videos**: ~200 KB
- **10,000 videos**: ~2 MB
- **Negligible** compared to detection_events table

### Trigger Performance

- **Trigger fires**: On INSERT/UPDATE of VIDEO_END events
- **Complexity**: O(1) - single SELECT + UPDATE
- **Expected latency**: <5ms
- **Impact**: Minimal - only affects video end events

---

## Monitoring and Alerting

### Recommended Metrics

```sql
-- 1. Drift distribution
SELECT
    CASE
        WHEN ABS(calculated_drift_ms) <= 50 THEN '0-50ms'
        WHEN ABS(calculated_drift_ms) <= 100 THEN '50-100ms'
        WHEN ABS(calculated_drift_ms) <= 200 THEN '100-200ms'
        WHEN ABS(calculated_drift_ms) <= 500 THEN '200-500ms'
        ELSE '>500ms'
    END as drift_range,
    COUNT(*) as count
FROM video_lifecycle_events
WHERE event_type = 'VIDEO_END'
    AND calculated_drift_ms IS NOT NULL
    AND created_at >= NOW() - INTERVAL '24 hours'
GROUP BY drift_range
ORDER BY drift_range;

-- 2. High drift sessions (alert threshold)
SELECT
    ts.id,
    ts.name,
    ts.average_drift_ms,
    COUNT(vle.id) as video_count
FROM test_sessions ts
JOIN video_lifecycle_events vle ON ts.id = vle.test_session_id
WHERE ts.average_drift_ms IS NOT NULL
    AND ABS(ts.average_drift_ms) > 200  -- Alert threshold
    AND ts.created_at >= NOW() - INTERVAL '1 hour'
GROUP BY ts.id, ts.name, ts.average_drift_ms
ORDER BY ABS(ts.average_drift_ms) DESC;

-- 3. Missing lifecycle events (data quality check)
SELECT
    ts.id,
    ts.name,
    COUNT(DISTINCT vle.video_id) as videos_with_events,
    COUNT(DISTINCT svr.video_id) as total_videos_in_sequence
FROM test_sessions ts
JOIN video_test_sequences vts ON ts.id = vts.test_session_id
JOIN sequence_video_results svr ON vts.id = svr.video_sequence_id
LEFT JOIN video_lifecycle_events vle ON ts.id = vle.test_session_id
WHERE ts.status = 'completed'
    AND ts.created_at >= NOW() - INTERVAL '24 hours'
GROUP BY ts.id, ts.name
HAVING COUNT(DISTINCT vle.video_id) < COUNT(DISTINCT svr.video_id);
```

### Alert Thresholds

1. **High Drift Alert**: `ABS(average_drift_ms) > 200ms`
2. **Extreme Drift Alert**: `ABS(calculated_drift_ms) > 500ms`
3. **Missing Events**: `completed_sessions_without_lifecycle_events > 0`
4. **Clock Desync**: `ABS(clock_offset_ms) > 5000ms`

---

## Troubleshooting

### Issue 1: Drift Calculation Not Working

**Symptoms**: `calculated_drift_ms` is always NULL

**Diagnosis**:
```sql
-- Check if VIDEO_START exists for VIDEO_END events
SELECT
    vle_end.test_session_id,
    vle_end.video_id,
    vle_end.event_type,
    CASE
        WHEN vle_start.id IS NOT NULL THEN 'HAS_START'
        ELSE 'MISSING_START'
    END as status
FROM video_lifecycle_events vle_end
LEFT JOIN video_lifecycle_events vle_start ON
    vle_start.test_session_id = vle_end.test_session_id
    AND vle_start.video_id = vle_end.video_id
    AND vle_start.event_type = 'VIDEO_START'
WHERE vle_end.event_type = 'VIDEO_END'
    AND vle_end.calculated_drift_ms IS NULL;
```

**Solution**: Ensure VIDEO_START is inserted before VIDEO_END

### Issue 2: Trigger Not Firing

**Diagnosis**:
```sql
-- Check if trigger exists
SELECT tgname, tgenabled FROM pg_trigger
WHERE tgname = 'trigger_calculate_video_drift';

-- Test trigger manually
UPDATE video_lifecycle_events
SET backend_received_timestamp = backend_received_timestamp + 0.001
WHERE event_type = 'VIDEO_END' LIMIT 1;
```

**Solution**: Re-create trigger with migration

### Issue 3: High Drift Values

**Symptoms**: `calculated_drift_ms > 500ms` consistently

**Diagnosis**:
```sql
-- Analyze drift sources
SELECT
    ts.name,
    v.filename,
    vle.calculated_drift_ms,
    vle.clock_offset_ms,
    vle.frontend_timestamp,
    vle.backend_received_timestamp
FROM video_lifecycle_events vle
JOIN test_sessions ts ON vle.test_session_id = ts.id
JOIN videos v ON vle.video_id = v.id
WHERE vle.event_type = 'VIDEO_END'
    AND ABS(vle.calculated_drift_ms) > 500
ORDER BY ABS(vle.calculated_drift_ms) DESC
LIMIT 10;
```

**Possible Causes**:
1. Browser clock adjustment (system time change)
2. Server clock adjustment (NTP sync)
3. High system load causing timestamp delays
4. Frontend timer precision issues

---

## Best Practices

### 1. Always Record Both START and END

```python
# ✅ CORRECT: Always record both events
record_lifecycle_event(session_id, video_id, 'VIDEO_START', ...)
# ... video plays ...
record_lifecycle_event(session_id, video_id, 'VIDEO_END', ...)

# ❌ WRONG: Recording only one event
record_lifecycle_event(session_id, video_id, 'VIDEO_START', ...)
# ... video plays but no END event ...
```

### 2. Use Consistent Timestamp Sources

```javascript
// ✅ CORRECT: Use performance.now() consistently
const startTs = performance.now();
// ... later ...
const endTs = performance.now();

// ❌ WRONG: Mixing timestamp sources
const startTs = performance.now();
const endTs = Date.now();  // Different clock!
```

### 3. Handle Error Cases

```python
try:
    # ... video playback ...
    record_lifecycle_event(session_id, video_id, 'VIDEO_END', ...)
except Exception as e:
    # Record error event for data completeness
    record_lifecycle_event(
        session_id, video_id, 'VIDEO_ERROR',
        event_metadata={'error': str(e), 'reason': 'playback_failure'}
    )
```

### 4. Apply Drift Compensation After Calculation

```python
# Wait for drift calculation before compensating detections
end_event = record_lifecycle_event(session_id, video_id, 'VIDEO_END', ...)
db.commit()  # Trigger calculates drift

# Now apply to detections
if end_event.calculated_drift_ms is not None:
    apply_drift_compensation(session_id, video_id, end_event.calculated_drift_ms)
```

---

## Future Enhancements

### 1. Multi-Video Drift Interpolation

For sessions with >2 videos, interpolate drift between START/END events for more accurate mid-video compensation.

### 2. Real-time Drift Monitoring

WebSocket stream of drift calculations for live monitoring dashboard.

### 3. Adaptive Drift Thresholds

Machine learning model to predict acceptable drift ranges based on session characteristics.

### 4. Clock Synchronization Service

Dedicated NTP-like service for browser-backend clock synchronization.

---

## References

- **Design Document**: `/backend/docs/VIDEO_MARKERS_SCHEMA_DESIGN.md`
- **Migration File**: `/backend/alembic/versions/f18f8e9c1590_add_video_lifecycle_tracking.py`
- **Model Definition**: `/backend/models.py` (VideoLifecycleEvent class)
- **HIL Timing Reference**: `/backend/docs/HIL_TIMING_FIX_QUICK_REFERENCE.md`

---

**Document Version**: 1.0
**Last Updated**: 2025-11-20
**Maintainer**: Backend Team
