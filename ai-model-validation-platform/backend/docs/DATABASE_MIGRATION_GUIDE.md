# Database Migration Guide - Timing Quality Tracking

## Overview

This migration adds timing quality tracking columns to prevent data corruption in ground truth matching. The migration adds:

- **test_sessions.timing_degraded**: Indicates if timing data uses wall clock (degraded) vs precision timing
- **test_sessions.timing_verified**: Indicates if timing has been verified against database
- **detection_events.usable_for_validation**: Indicates if detections are usable for validation

## Pre-Migration Checklist

Before running the migration, ensure:

- [ ] **Database backup completed** (critical for production)
- [ ] All dependent services are stopped (API servers, workers)
- [ ] Database user has ALTER TABLE permissions
- [ ] Python environment is activated with required dependencies
- [ ] Current Alembic revision is up to date (`alembic current`)
- [ ] No pending database transactions

### Create Database Backup

```bash
# PostgreSQL backup
pg_dump -U your_user -h your_host -d your_database > backup_$(date +%Y%m%d_%H%M%S).sql

# Or use environment variables
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# SQLite backup (development)
cp dev_database.db dev_database_backup_$(date +%Y%m%d_%H%M%S).db
```

## Migration Steps

### Step 1: Check Current Migration State

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Check current revision
alembic current

# Should show: add_video_id_to_detection_events (or earlier)
```

### Step 2: Review Migration Script

Review the migration script to understand changes:

```bash
cat migrations/versions/20251119_add_timing_quality_tracking.py
```

**Changes being applied:**
- Add `timing_degraded` column to `test_sessions` (Boolean, default: false)
- Add `timing_verified` column to `test_sessions` (Boolean, default: false)
- Add `usable_for_validation` column to `detection_events` (Boolean, default: true)
- Create indexes for performance

### Step 3: Apply Schema Migration

```bash
# Apply the migration
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade ... -> 20251119_timing_quality, Add timing quality tracking columns
```

**Estimated time:**
- Small databases (<1000 records): < 1 second
- Medium databases (1000-100K records): 1-5 seconds
- Large databases (>100K records): 5-30 seconds

### Step 4: Verify Schema Changes

```bash
# PostgreSQL: Check new columns
psql $DATABASE_URL -c "\d test_sessions" | grep timing
psql $DATABASE_URL -c "\d detection_events" | grep usable

# Expected output:
# timing_degraded     | boolean  | not null | false
# timing_verified     | boolean  | not null | false
# usable_for_validation | boolean | not null | true
```

### Step 5: Run Data Migration

Migrate existing data with conservative defaults:

```bash
python scripts/migrate_existing_sessions.py

# Expected output:
# Starting data migration for timing quality tracking...
# Found X test sessions
# Found Y detection events
# Updated X test sessions
# Updated Y detection events
# ✅ Migration completed successfully
```

**What this does:**
- Marks all existing sessions as `timing_degraded=True` (conservative approach)
- Marks all existing sessions as `timing_verified=False` (not yet verified)
- Marks all existing detections as `usable_for_validation=True` (preserve existing data)

### Step 6: Verify Migration

```bash
# Check migration results
python -c "
from database import SessionLocal
from models import TestSession, DetectionEvent

db = SessionLocal()
print(f'Total sessions: {db.query(TestSession).count()}')
print(f'Degraded sessions: {db.query(TestSession).filter(TestSession.timing_degraded == True).count()}')
print(f'Verified sessions: {db.query(TestSession).filter(TestSession.timing_verified == True).count()}')
print(f'Usable detections: {db.query(DetectionEvent).filter(DetectionEvent.usable_for_validation == True).count()}')
db.close()
"
```

### Step 7: Update Application Code

Update your application code to use the new columns:

```python
# Example: Creating a new test session with timing quality tracking
session = TestSession(
    name="HIL Test 001",
    timing_degraded=False,  # Using precision timing
    timing_verified=True,   # Verified against database
    # ... other fields
)

# Example: Mark detection as unusable if timing is suspect
detection = DetectionEvent(
    timestamp=1234567.89,
    usable_for_validation=False,  # Don't use for validation
    # ... other fields
)
```

## Rollback Procedures

### If Migration Fails

If the migration fails during application:

```bash
# Rollback to previous revision
alembic downgrade -1

# Verify rollback
alembic current
```

### Complete Rollback

To completely rollback the migration after it's been applied:

```bash
# Step 1: Rollback schema changes
alembic downgrade -1

# Step 2: Restore from backup (if needed)
# PostgreSQL:
psql $DATABASE_URL < backup_YYYYMMDD_HHMMSS.sql

# SQLite:
cp dev_database_backup_YYYYMMDD_HHMMSS.db dev_database.db

# Step 3: Verify rollback
alembic current
python -c "
from database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
columns = [c['name'] for c in inspector.get_columns('test_sessions')]
print('timing_degraded in columns:', 'timing_degraded' in columns)
print('Expected: False')
"
```

## Verification Steps

### 1. Schema Verification

```bash
# Check columns exist with correct types
python -c "
from database import engine
from sqlalchemy import inspect

inspector = inspect(engine)

# Check test_sessions
ts_cols = {c['name']: c for c in inspector.get_columns('test_sessions')}
print('test_sessions.timing_degraded:', 'timing_degraded' in ts_cols)
print('test_sessions.timing_verified:', 'timing_verified' in ts_cols)

# Check detection_events
de_cols = {c['name']: c for c in inspector.get_columns('detection_events')}
print('detection_events.usable_for_validation:', 'usable_for_validation' in de_cols)

# Check indexes
ts_indexes = [idx['name'] for idx in inspector.get_indexes('test_sessions')]
de_indexes = [idx['name'] for idx in inspector.get_indexes('detection_events')]
print('Index on timing_degraded:', 'idx_test_sessions_timing_degraded' in ts_indexes)
print('Index on usable_for_validation:', 'idx_detection_events_usable' in de_indexes)
"
```

### 2. Data Integrity Verification

```bash
# Verify all rows have values (no nulls)
python -c "
from database import SessionLocal
from models import TestSession, DetectionEvent

db = SessionLocal()
null_timing = db.query(TestSession).filter(TestSession.timing_degraded == None).count()
null_verified = db.query(TestSession).filter(TestSession.timing_verified == None).count()
null_usable = db.query(DetectionEvent).filter(DetectionEvent.usable_for_validation == None).count()

print(f'Null timing_degraded: {null_timing} (expected: 0)')
print(f'Null timing_verified: {null_verified} (expected: 0)')
print(f'Null usable_for_validation: {null_usable} (expected: 0)')
db.close()
"
```

### 3. Performance Verification

```bash
# Test index usage (PostgreSQL only)
psql $DATABASE_URL -c "
EXPLAIN ANALYZE
SELECT * FROM test_sessions
WHERE timing_degraded = true;
"
# Should show "Index Scan using idx_test_sessions_timing_degraded"
```

## Impact Analysis

### Performance Impact

- **Schema migration**: Minimal downtime (<5 seconds for most databases)
- **Data migration**: No downtime (updates existing rows)
- **Index creation**: Minimal impact (<1 second for small-medium databases)
- **Query performance**: Improved filtering on timing quality

### Storage Impact

- **Per test session**: +2 bytes (2 boolean columns)
- **Per detection event**: +1 byte (1 boolean column)
- **Indexes**: ~4KB per 1000 rows

### Application Impact

- **Breaking changes**: None (columns have defaults)
- **API changes**: None (backward compatible)
- **Query changes**: Optional (can filter by timing quality)

## Post-Migration Tasks

### 1. Review Degraded Sessions

```bash
# List sessions with degraded timing
python -c "
from database import SessionLocal
from models import TestSession

db = SessionLocal()
degraded = db.query(TestSession).filter(
    TestSession.timing_degraded == True
).all()

print(f'Found {len(degraded)} sessions with degraded timing:')
for session in degraded[:10]:  # Show first 10
    print(f'  - {session.id}: {session.name}')
db.close()
"
```

### 2. Update Verified Sessions

For sessions with reliable precision timing:

```python
from database import SessionLocal
from models import TestSession

db = SessionLocal()

# Update sessions that have been verified
session = db.query(TestSession).filter(TestSession.id == "session_id").first()
if session:
    session.timing_verified = True
    session.timing_degraded = False
    db.commit()

db.close()
```

### 3. Monitor Application Logs

Watch for any issues related to timing quality:

```bash
# Monitor application logs
tail -f logs/application.log | grep -i "timing"
```

## Troubleshooting

### Issue: Migration Hangs

**Symptoms**: Migration command doesn't complete

**Solution**:
```bash
# Check for locks
# PostgreSQL:
psql $DATABASE_URL -c "SELECT * FROM pg_locks WHERE NOT granted;"

# Kill hanging connections if needed
psql $DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';"

# Retry migration
alembic upgrade head
```

### Issue: Permission Denied

**Symptoms**: `ERROR: permission denied for table test_sessions`

**Solution**:
```bash
# Grant necessary permissions
psql $DATABASE_URL -c "
GRANT ALTER ON TABLE test_sessions TO your_user;
GRANT ALTER ON TABLE detection_events TO your_user;
"
```

### Issue: Column Already Exists

**Symptoms**: `ERROR: column "timing_degraded" of relation "test_sessions" already exists`

**Solution**:
```bash
# This indicates partial migration - check current state
alembic current

# If in intermediate state, try downgrade then upgrade
alembic downgrade -1
alembic upgrade head
```

## Deployment Checklist

- [ ] Pre-migration backup completed
- [ ] Schema migration applied (`alembic upgrade head`)
- [ ] Data migration completed (`python scripts/migrate_existing_sessions.py`)
- [ ] Schema verification passed
- [ ] Data integrity verification passed
- [ ] Application code updated to use new columns
- [ ] Application restarted with new code
- [ ] Monitoring enabled for timing quality issues
- [ ] Documentation updated with new fields
- [ ] Team notified of new timing quality tracking

## Support

For issues or questions:
- Check the troubleshooting section above
- Review migration logs: `cat alembic.log`
- Check application logs for timing-related errors
- Contact database administrator for permissions issues

## References

- **Migration Script**: `/migrations/versions/20251119_add_timing_quality_tracking.py`
- **Data Migration**: `/scripts/migrate_existing_sessions.py`
- **Models**: `/models.py` (TestSession, DetectionEvent)
- **Alembic Docs**: https://alembic.sqlalchemy.org/
