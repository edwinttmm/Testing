# HIL Ground Truth Timing Migration

## Overview

This migration adds comprehensive support for video timing synchronization and ground truth matching in the HIL (Hardware-in-the-Loop) validation system. The migration enables precise temporal alignment between ground truth data and detection events for accurate latency measurement and validation.

## Database Changes

### 1. Test Sessions Table Enhancements

New columns added to `test_sessions`:

```sql
ALTER TABLE test_sessions ADD COLUMN video_playback_start_time DOUBLE PRECISION;
ALTER TABLE test_sessions ADD COLUMN video_playback_duration DOUBLE PRECISION;
ALTER TABLE test_sessions ADD COLUMN ground_truth_count INTEGER;
```

**Fields Description:**
- `video_playback_start_time`: Unix timestamp when video playback started
- `video_playback_duration`: Actual duration of video playback in seconds
- `ground_truth_count`: Number of ground truth objects in the associated video

### 2. Detection Events Table Enhancements

New columns added to `detection_events`:

```sql
ALTER TABLE detection_events ADD COLUMN video_relative_timestamp DOUBLE PRECISION;
ALTER TABLE detection_events ADD COLUMN actual_latency_ms DOUBLE PRECISION;
```

**Fields Description:**
- `video_relative_timestamp`: Timestamp relative to video start (seconds)
- `actual_latency_ms`: Measured latency from ground truth to detection (-1000ms to +1000ms)

### 3. Detection Comparisons Table

New table created for tracking ground truth matching:

```sql
CREATE TABLE detection_comparisons (
    id VARCHAR(36) PRIMARY KEY,
    test_session_id VARCHAR(36) NOT NULL,
    detection_event_id VARCHAR(36),
    ground_truth_object_id VARCHAR(36),
    is_matched BOOLEAN DEFAULT FALSE,
    matching_confidence DOUBLE PRECISION,
    match_quality VARCHAR(20),
    latency_ms DOUBLE PRECISION,
    validation_result VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (detection_event_id) REFERENCES detection_events(id) ON DELETE CASCADE,
    FOREIGN KEY (ground_truth_object_id) REFERENCES ground_truth_objects(id) ON DELETE CASCADE
);
```

### 4. Performance Indexes

New indexes for timing-based queries:

```sql
CREATE INDEX idx_detection_events_video_relative_time ON detection_events(video_relative_timestamp);
CREATE INDEX idx_detection_events_session_time ON detection_events(test_session_id, video_relative_timestamp);
CREATE INDEX idx_ground_truth_video_time ON ground_truth_objects(video_id, timestamp);
CREATE INDEX idx_detection_comparisons_session ON detection_comparisons(test_session_id);
CREATE INDEX idx_detection_comparisons_matched ON detection_comparisons(is_matched, match_quality);
```

## Files Structure

```
migrations/
├── add_ground_truth_timing_fields.py  # Main migration script
├── test_migration.py                  # Comprehensive testing
├── data_validation_utils.py          # Validation utilities
└── README.md                         # This documentation

schemas/
└── hil_timing_schemas.py             # Pydantic schemas for HIL system

models_enhanced.py                    # Updated SQLAlchemy models
```

## Usage

### Running the Migration

```bash
# Run migration
python migrations/add_ground_truth_timing_fields.py

# Run with specific database URL
python migrations/add_ground_truth_timing_fields.py --database-url postgresql://user:pass@host:port/db

# Rollback migration
python migrations/add_ground_truth_timing_fields.py rollback
```

### Testing the Migration

```bash
# Run comprehensive tests
python migrations/test_migration.py

# Test with specific database
python migrations/test_migration.py postgresql://user:pass@host:port/db
```

### Validation

```python
from migrations.data_validation_utils import validate_hil_system_health
from database import get_db

# Validate system health
with get_db() as session:
    results = validate_hil_system_health(session, tolerance_ms=100)
    print(results)
```

## API Integration

### Updated Schemas

The migration includes new Pydantic schemas in `schemas/hil_timing_schemas.py`:

- `TestSessionCreateHIL`: Enhanced test session creation
- `DetectionEventCreateHIL`: Enhanced detection event creation
- `DetectionComparisonCreate`: Detection comparison creation
- `TimingAnalysisRequest/Response`: Timing analysis operations

### Example Usage

```python
from schemas.hil_timing_schemas import TestSessionCreateHIL, DetectionEventCreateHIL

# Create test session with timing data
test_session = TestSessionCreateHIL(
    name="HIL Test Session",
    project_id="project-uuid",
    video_id="video-uuid",
    video_playback_start_time=1609459200.0,
    video_playback_duration=120.5,
    ground_truth_count=15
)

# Create detection event with timing
detection = DetectionEventCreateHIL(
    test_session_id="session-uuid",
    timestamp=1609459210.5,
    confidence=0.92,
    class_label="pedestrian",
    video_relative_timestamp=10.5,
    actual_latency_ms=75.0
)
```

## Migration Safety

### Pre-Migration Checks

1. **Backup Database**: Always backup before running migration
2. **Check Dependencies**: Ensure all dependencies are installed
3. **Test Environment**: Run migration in test environment first

### Rollback Capability

The migration supports rollback:

```bash
python migrations/add_ground_truth_timing_fields.py rollback
```

**Note**: SQLite doesn't support DROP COLUMN, so columns remain but are ignored.

### Data Integrity

- Existing data is preserved during migration
- New columns are added with appropriate defaults
- Foreign key constraints are maintained
- Indexes are created for optimal performance

## Performance Considerations

### Query Optimization

New indexes enable efficient queries:

```sql
-- Fast timing-based queries
SELECT * FROM detection_events 
WHERE video_relative_timestamp BETWEEN 10.0 AND 30.0;

-- Efficient session-based timing queries
SELECT * FROM detection_events 
WHERE test_session_id = 'session-uuid' 
ORDER BY video_relative_timestamp;

-- Quick matching analysis
SELECT * FROM detection_comparisons 
WHERE test_session_id = 'session-uuid' 
AND is_matched = true;
```

### Memory Usage

- Minimal overhead for new columns
- Efficient storage for timing data (DOUBLE PRECISION)
- Proper indexing prevents full table scans

## Validation Features

### Timing Validation

- Video timing parameter validation
- Timestamp alignment verification
- Latency measurement validation
- Boundary checks for timing data

### Data Integrity Validation

- Database relationship validation
- Orphaned record detection
- Consistency checks across tables
- Performance threshold validation

### System Health Monitoring

```python
# Comprehensive health check
results = validate_hil_system_health(session)

# Returns:
# - Overall system health status
# - Per-session validation results
# - Issue categorization and severity
# - Suggested fixes for problems
```

## Troubleshooting

### Common Issues

1. **Column Already Exists**
   - Migration checks for existing columns
   - Safe to re-run migration

2. **Permission Denied**
   - Ensure database user has ALTER TABLE permissions
   - Check connection string credentials

3. **Index Creation Failed**
   - Usually indicates data type mismatch
   - Run data validation to identify issues

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks

Run validation after migration:

```bash
python -c "
from migrations.data_validation_utils import validate_hil_system_health
from database import SessionLocal
session = SessionLocal()
results = validate_hil_system_health(session)
print(f'System Health: {results[\"system_health\"]}')
session.close()
"
```

## Migration History

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | 2025-09-16 | Initial HIL timing fields migration |

## Contributing

When modifying this migration:

1. Update version in migration script
2. Add comprehensive tests
3. Update this documentation
4. Test rollback functionality
5. Validate data integrity

## License

This migration is part of the AI Model Validation Platform.