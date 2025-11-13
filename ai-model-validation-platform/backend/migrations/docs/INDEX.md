# Database Migrations Documentation Index

**Last Updated**: 2025-11-11
**Version**: 1.0

---

## 📚 Documentation Library

### Quick Start
- **[QUICK_REFERENCE.md](./QUICK_REFERENCE.md)** - Get started in 5 minutes
  - Apply migrations
  - Code examples
  - Common tasks
  - Troubleshooting

### Comprehensive Guide
- **[DUAL_EVALUATION_MIGRATION_GUIDE.md](./DUAL_EVALUATION_MIGRATION_GUIDE.md)** - Complete documentation
  - Overview and rationale
  - Schema changes with SQL
  - Data migration strategy
  - Usage patterns
  - Performance considerations
  - Integration examples
  - Troubleshooting guide

### Technical Report
- **[MIGRATION_CREATION_REPORT.md](./MIGRATION_CREATION_REPORT.md)** - Detailed technical report
  - Executive summary
  - Deliverables list
  - Schema changes
  - Success criteria
  - Known issues
  - Integration tasks
  - File locations

---

## 🗂️ Migration Files

### Migration 1: Frontend Playing Delay
- **File**: `../versions/20251111_add_frontend_playing_delay.py`
- **Revision**: `950b4c965ca9`
- **Purpose**: Add `frontend_playing_delay_ms` field for T1-T0 presentation delay tracking

### Migration 2: Dual-Evaluation Fields
- **File**: `../versions/20251111_add_dual_evaluation_fields.py`
- **Revision**: `a1b2c3d4e5f6`
- **Purpose**: Add `evaluation_details` JSON field for detailed evaluation metrics

---

## 🛠️ Scripts and Tools

### Application Scripts
- **[../scripts/apply_migrations.sh](../../scripts/apply_migrations.sh)** - Apply migrations with verification
- **[../scripts/rollback_migrations.sh](../../scripts/rollback_migrations.sh)** - Safe rollback with confirmation

### Testing Scripts
- **[../scripts/test_new_migrations.py](../../scripts/test_new_migrations.py)** - Automated verification suite

---

## 📊 Schema Reference

### New Fields Added

#### SequenceVideoResult
```python
frontend_playing_delay_ms: float | None
# Milliseconds between video load and playing event (T1-T0)
# Indexed for performance
# Backfilled with 1500ms for legacy data
```

#### TestSession
```python
evaluation_details: dict | None
# JSON field with detailed evaluation metrics and reasoning
# Structure:
{
    "accuracy_threshold": 0.80,
    "accuracy_score": 0.92,
    "accuracy_reasoning": "F1 score 0.92 exceeds threshold",
    "latency_threshold_ms": 100,
    "latency_mean_ms": 145.3,
    "latency_reasoning": "Mean latency exceeds threshold",
    "overall_recommendation": "Review required",
    "migrated": true,  # For backfilled data
    "migration_date": "2025-11-11T15:00:00"
}
```

### Indexes Created

| Table | Index Name | Columns | Type |
|-------|-----------|---------|------|
| sequence_video_results | idx_sequence_video_results_playing_delay | frontend_playing_delay_ms | Single |
| sequence_video_results | idx_sequence_video_results_delay_status | frontend_playing_delay_ms, video_status | Composite |
| test_sessions | idx_test_sessions_dual_eval | accuracy_result, latency_result, overall_test_result | Composite |
| test_sessions | idx_test_sessions_evaluation_details | evaluation_details | GIN (PostgreSQL) |

---

## 🚀 Quick Start Guide

### 1. Apply Migrations
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
./scripts/apply_migrations.sh
```

### 2. Verify Application
```bash
python3 scripts/test_new_migrations.py
```

### 3. Start Using New Fields

#### Frontend Playing Delay
```python
video_result.frontend_playing_delay_ms = (t1_playing - t0_load) * 1000.0
session.commit()
```

#### Evaluation Details
```python
test_session.evaluation_details = {
    "accuracy_threshold": 0.80,
    "accuracy_score": 0.92,
    "latency_threshold_ms": 100,
    "latency_mean_ms": 145.3,
    "overall_recommendation": "Approve"
}
session.commit()
```

---

## 📋 Checklist for Production Deployment

### Pre-Deployment
- [ ] Review migration files
- [ ] Check current database revision: `alembic current`
- [ ] Backup database
- [ ] Test migrations in staging environment
- [ ] Review application code changes

### Deployment
- [ ] Apply migrations: `./scripts/apply_migrations.sh`
- [ ] Verify field existence: `python3 scripts/test_new_migrations.py`
- [ ] Check index creation
- [ ] Verify backfill data

### Post-Deployment
- [ ] Monitor query performance
- [ ] Verify new fields are being populated
- [ ] Test dual-evaluation queries
- [ ] Update API documentation
- [ ] Train team on new evaluation system

### Rollback Plan (if needed)
- [ ] Run rollback script: `./scripts/rollback_migrations.sh 2`
- [ ] Verify rollback success
- [ ] Restore database backup if needed

---

## 🔍 Common Tasks

### View Migration History
```bash
alembic history | head -20
```

### Check Current Revision
```bash
alembic current
```

### Apply Specific Migration
```bash
alembic upgrade 950b4c965ca9  # Just frontend_playing_delay_ms
alembic upgrade a1b2c3d4e5f6  # Both migrations
alembic upgrade head           # All pending migrations
```

### Generate SQL Preview
```bash
alembic upgrade head --sql > preview.sql
```

### Rollback Migrations
```bash
./scripts/rollback_migrations.sh 2  # Rollback both migrations
./scripts/rollback_migrations.sh 1  # Rollback just evaluation_details
```

---

## 🐛 Troubleshooting

### Common Issues

#### "Column already exists"
- **Cause**: Migration trying to add existing column
- **Solution**: Migrations check for existing columns; if error persists, check schema mismatch
- **Documentation**: See [DUAL_EVALUATION_MIGRATION_GUIDE.md](./DUAL_EVALUATION_MIGRATION_GUIDE.md#troubleshooting)

#### "Index already exists"
- **Cause**: Index created by previous migration or manual operation
- **Solution**: Migrations gracefully handle existing indexes
- **Action**: Safe to ignore if migration succeeds

#### "Revision not found"
- **Cause**: Migration dependency chain broken
- **Solution**: Check `alembic current` and update `down_revision` in migration files
- **Documentation**: See [MIGRATION_CREATION_REPORT.md](./MIGRATION_CREATION_REPORT.md#known-issues-and-considerations)

### Getting Help

1. **Check Quick Reference**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#troubleshooting)
2. **Review Comprehensive Guide**: [DUAL_EVALUATION_MIGRATION_GUIDE.md](./DUAL_EVALUATION_MIGRATION_GUIDE.md#troubleshooting)
3. **Run Verification Tests**: `python3 scripts/test_new_migrations.py`
4. **Check Alembic Logs**: Review output from `alembic upgrade` command

---

## 📈 Performance Monitoring

### Query Performance

Monitor these query patterns after migration:

```sql
-- Dual-evaluation filtering (uses idx_test_sessions_dual_eval)
SELECT * FROM test_sessions
WHERE accuracy_result = 'PASS' AND latency_result = 'FAIL';

-- Presentation delay analysis (uses idx_sequence_video_results_playing_delay)
SELECT AVG(frontend_playing_delay_ms) FROM sequence_video_results
WHERE frontend_playing_delay_ms IS NOT NULL;

-- JSON evaluation details search (uses GIN index in PostgreSQL)
SELECT * FROM test_sessions
WHERE evaluation_details->>'overall_recommendation' = 'Review required';
```

### Index Usage Analysis

**SQLite**:
```sql
EXPLAIN QUERY PLAN SELECT * FROM test_sessions
WHERE accuracy_result = 'PASS' AND latency_result = 'FAIL';
```

**PostgreSQL**:
```sql
EXPLAIN ANALYZE SELECT * FROM test_sessions
WHERE accuracy_result = 'PASS' AND latency_result = 'FAIL';
```

---

## 📞 Support and Contact

### Documentation Issues
- Check all documentation in `migrations/docs/`
- Run verification tests: `python3 scripts/test_new_migrations.py`

### Technical Questions
- Review comprehensive guide: [DUAL_EVALUATION_MIGRATION_GUIDE.md](./DUAL_EVALUATION_MIGRATION_GUIDE.md)
- Check technical report: [MIGRATION_CREATION_REPORT.md](./MIGRATION_CREATION_REPORT.md)

### Migration Problems
- Follow rollback procedure: `./scripts/rollback_migrations.sh`
- Review troubleshooting section in guides
- Check Alembic documentation: https://alembic.sqlalchemy.org/

---

## 📝 Version History

### Version 1.0 (2025-11-11)
- Initial migration creation
- Added `frontend_playing_delay_ms` field
- Added `evaluation_details` field
- Created comprehensive documentation
- Implemented testing and rollback scripts

---

## 🔗 Related Documentation

- **Models**: `../../models.py` (updated with new fields)
- **Database**: `../../database.py` (SQLAlchemy configuration)
- **Alembic Config**: `../../alembic.ini` (Alembic settings)
- **Migration Versions**: `../versions/` (all migration files)

---

**Quick Navigation**:
- [Quick Reference](./QUICK_REFERENCE.md) - Fast answers
- [Comprehensive Guide](./DUAL_EVALUATION_MIGRATION_GUIDE.md) - Complete documentation
- [Technical Report](./MIGRATION_CREATION_REPORT.md) - Detailed analysis

**Status**: ✅ Production Ready | **Created**: 2025-11-11 | **Version**: 1.0
