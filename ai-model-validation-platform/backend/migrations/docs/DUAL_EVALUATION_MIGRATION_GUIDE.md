# Dual-Evaluation Database Migrations

## Overview

This document describes the database migrations implemented on 2025-11-11 to support:

1. **Frontend Playing Delay Tracking** - Precise measurement of video presentation delay
2. **Dual-Evaluation System** - Separate assessment of accuracy and latency performance

## Migration Files

### Migration 1: Frontend Playing Delay
**File**: `20251111_add_frontend_playing_delay.py`
**Revision**: `950b4c965ca9`
**Depends on**: `add_approval_workflow`

**Changes**:
- Adds `frontend_playing_delay_ms` field to `sequence_video_results` table
- Creates performance indexes for timing analysis
- Backfills legacy data with 1500ms estimate (based on historical browser behavior)

### Migration 2: Dual-Evaluation Fields
**File**: `20251111_add_dual_evaluation_fields.py`
**Revision**: `a1b2c3d4e5f6`
**Depends on**: `950b4c965ca9`

**Changes**:
- Adds `evaluation_details` JSON field to `test_sessions` table
- Creates indexes for dual-evaluation filtering
- Backfills legacy sessions with migrated evaluation data

## Schema Changes

### SequenceVideoResult Table

```sql
-- New field added
frontend_playing_delay_ms FLOAT NULL
    -- Milliseconds between video load and playing event (T1-T0 presentation delay)
    -- Used for accurate detection window calculation

-- New indexes created
CREATE INDEX idx_sequence_video_results_playing_delay
    ON sequence_video_results(frontend_playing_delay_ms);

CREATE INDEX idx_sequence_video_results_delay_status
    ON sequence_video_results(frontend_playing_delay_ms, video_status);
```

### TestSession Table

```sql
-- New field added
evaluation_details JSON NULL
    -- Detailed evaluation metrics, reasoning, and threshold data
    -- Structure: {
    --   "accuracy_threshold": 0.80,
    --   "latency_threshold_ms": 100,
    --   "accuracy_reasoning": "...",
    --   "latency_reasoning": "...",
    --   "migrated": true/false,
    --   "migration_date": "ISO-8601 timestamp"
    -- }

-- New indexes created
CREATE INDEX idx_test_sessions_dual_eval
    ON test_sessions(accuracy_result, latency_result, overall_test_result);

-- PostgreSQL only (GIN index for JSON queries)
CREATE INDEX idx_test_sessions_evaluation_details
    ON test_sessions USING GIN (evaluation_details);
```

## Data Migration Strategy

### Frontend Playing Delay Backfill

Legacy sessions created before 2025-11-11 are backfilled with a 1500ms estimate:

```sql
UPDATE sequence_video_results
SET frontend_playing_delay_ms = 1500.0
WHERE frontend_playing_delay_ms IS NULL
  AND created_at < '2025-11-11'
```

**Rationale**: Historical data shows average ~1.5s delay between `loadeddata` and `playing` events in browsers.

### Evaluation Details Backfill

Legacy sessions are migrated with structured evaluation data:

```sql
UPDATE test_sessions
SET evaluation_details = json_object(
    'migrated', 1,
    'original_result', pass_fail_result,
    'migration_date', datetime('now'),
    'accuracy_threshold', 0.80,
    'latency_threshold_ms', latency_threshold_ms,
    'notes', 'Migrated from legacy pass_fail_result system'
)
WHERE evaluation_details IS NULL
  AND created_at < '2025-11-11'
```

## Usage Guide

### Applying Migrations

```bash
# Navigate to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Apply migrations using helper script
./scripts/apply_migrations.sh

# Or manually with alembic
alembic upgrade head
```

### Verification

```bash
# Run automated verification tests
python3 scripts/test_new_migrations.py

# Check current migration revision
alembic current

# View migration history
alembic history
```

### Rollback (if needed)

```bash
# Rollback both migrations
./scripts/rollback_migrations.sh 2

# Rollback just the dual-evaluation migration
./scripts/rollback_migrations.sh 1

# Or manually with alembic
alembic downgrade -2
```

## Field Usage in Code

### Frontend Playing Delay

```python
from models import SequenceVideoResult

# Store measured presentation delay
video_result = SequenceVideoResult(
    video_sequence_id=sequence_id,
    video_id=video_id,
    frontend_playing_delay_ms=1450.2  # Measured T1-T0
)
session.add(video_result)
session.commit()

# Query videos with high presentation delay
slow_videos = session.query(SequenceVideoResult).filter(
    SequenceVideoResult.frontend_playing_delay_ms > 2000
).all()
```

### Evaluation Details

```python
from models import TestSession

# Store dual-evaluation results
test_session = TestSession(
    name="Test Session 123",
    accuracy_result="PASS",
    latency_result="FAIL",
    overall_test_result="CONDITIONAL_PASS",
    evaluation_details={
        "accuracy_threshold": 0.80,
        "accuracy_score": 0.92,
        "accuracy_reasoning": "F1 score 0.92 exceeds 0.80 threshold",
        "latency_threshold_ms": 100,
        "latency_mean_ms": 145.3,
        "latency_reasoning": "Mean latency 145.3ms exceeds 100ms threshold",
        "overall_reasoning": "Excellent accuracy but latency concerns",
        "recommendations": [
            "Investigate latency outliers",
            "Consider system optimization"
        ]
    }
)
session.add(test_session)
session.commit()

# Query sessions with specific evaluation patterns
failed_latency_sessions = session.query(TestSession).filter(
    TestSession.accuracy_result == "PASS",
    TestSession.latency_result == "FAIL"
).all()
```

## Performance Considerations

### Index Usage

1. **frontend_playing_delay_ms**: Enables fast sorting/filtering by presentation delay
2. **evaluation_details (GIN)**: Enables efficient JSON queries in PostgreSQL
3. **Composite dual_eval index**: Optimizes queries filtering by multiple evaluation results

### Query Examples

```sql
-- Find sessions with good accuracy but poor latency
SELECT * FROM test_sessions
WHERE accuracy_result = 'PASS'
  AND latency_result IN ('FAIL', 'CONDITIONAL_PASS')
ORDER BY created_at DESC;

-- Analyze presentation delay distribution
SELECT
    ROUND(frontend_playing_delay_ms / 100) * 100 as delay_bucket,
    COUNT(*) as count
FROM sequence_video_results
WHERE frontend_playing_delay_ms IS NOT NULL
GROUP BY delay_bucket
ORDER BY delay_bucket;

-- PostgreSQL JSON query example
SELECT * FROM test_sessions
WHERE evaluation_details->>'latency_reasoning' LIKE '%exceeds%';
```

## Database Compatibility

Both migrations are designed for **SQLite** and **PostgreSQL** compatibility:

- SQLite: Uses standard SQL with JSON stored as TEXT
- PostgreSQL: Uses native JSON type with GIN indexing support
- Comments: PostgreSQL-specific (wrapped in try/except for SQLite)

## Troubleshooting

### Migration Fails: "column already exists"

The migrations check for existing columns before adding them. If you see this error:

```python
# Check what columns exist
from sqlalchemy import inspect, create_engine
engine = create_engine('sqlite:///dev_database.db')
inspector = inspect(engine)
print(inspector.get_columns('test_sessions'))
```

### Index Creation Fails

Indexes may already exist from previous migrations. The scripts handle this gracefully:

```python
try:
    op.create_index(...)
except Exception:
    pass  # Index already exists
```

### Backfill Data Validation

Verify backfilled data is correct:

```sql
-- Check frontend_playing_delay_ms backfill
SELECT COUNT(*) as total,
       COUNT(frontend_playing_delay_ms) as with_delay,
       MIN(frontend_playing_delay_ms) as min_delay,
       MAX(frontend_playing_delay_ms) as max_delay,
       AVG(frontend_playing_delay_ms) as avg_delay
FROM sequence_video_results;

-- Check evaluation_details backfill
SELECT COUNT(*) as total,
       COUNT(evaluation_details) as with_details,
       SUM(CASE WHEN json_extract(evaluation_details, '$.migrated') = 1
           THEN 1 ELSE 0 END) as migrated_count
FROM test_sessions;
```

## Integration with Existing Code

### No Breaking Changes

These migrations are **additive only**:
- All existing fields remain unchanged
- New fields are nullable
- Legacy code continues to work without modification

### Gradual Adoption

You can adopt the new fields incrementally:

1. **Phase 1**: Apply migrations (no code changes needed)
2. **Phase 2**: Start populating `frontend_playing_delay_ms` in new sessions
3. **Phase 3**: Update evaluation logic to use `evaluation_details`
4. **Phase 4**: Migrate legacy data processing if needed

## Related Documentation

- [Detection Window Timing Analysis](../../docs/DETECTION_WINDOW_TIMING_ANALYSIS.md)
- [Dual-Evaluation System Design](../../docs/DUAL_EVALUATION_SYSTEM.md)
- [Schema Evolution Guide](../../docs/SCHEMA_EVOLUTION.md)

## Revision History

- **2025-11-11**: Initial migration creation
  - Added frontend_playing_delay_ms field
  - Added evaluation_details field
  - Created indexes and backfill logic

## Contact

For questions or issues with these migrations, contact the Database Migration Creator.
