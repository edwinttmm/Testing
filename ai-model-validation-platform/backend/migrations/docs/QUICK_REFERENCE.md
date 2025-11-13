# Database Migrations - Quick Reference

**Created**: 2025-11-11 | **Status**: Ready to Apply

---

## What Was Created

### Two New Migrations

1. **Frontend Playing Delay** (`950b4c965ca9`)
   - Adds `frontend_playing_delay_ms` to `sequence_video_results`
   - Tracks T1-T0 presentation delay for accurate detection windows

2. **Dual-Evaluation Fields** (`a1b2c3d4e5f6`)
   - Adds `evaluation_details` JSON to `test_sessions`
   - Enables separate accuracy and latency assessment

---

## Quick Start

### Apply Migrations
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
./scripts/apply_migrations.sh
```

### Verify Application
```bash
python3 scripts/test_new_migrations.py
```

### Rollback (if needed)
```bash
./scripts/rollback_migrations.sh 2
```

---

## New Fields

### SequenceVideoResult
```python
frontend_playing_delay_ms: float | None  # T1-T0 delay in milliseconds
```

### TestSession
```python
evaluation_details: dict | None  # JSON with evaluation reasoning
# Example:
{
    "accuracy_threshold": 0.80,
    "accuracy_score": 0.92,
    "accuracy_reasoning": "F1 score 0.92 exceeds threshold",
    "latency_threshold_ms": 100,
    "latency_mean_ms": 145.3,
    "latency_reasoning": "Mean latency exceeds threshold",
    "overall_recommendation": "Review required"
}
```

---

## Code Examples

### Store Presentation Delay
```python
video_result.frontend_playing_delay_ms = (t1_playing - t0_load) * 1000.0
session.commit()
```

### Store Evaluation Details
```python
test_session.evaluation_details = {
    "accuracy_threshold": 0.80,
    "accuracy_score": f1_score,
    "accuracy_reasoning": f"F1 {f1_score:.3f} exceeds threshold",
    "latency_threshold_ms": 100,
    "latency_mean_ms": mean_latency,
    "latency_reasoning": f"Mean {mean_latency:.1f}ms within threshold"
}
session.commit()
```

### Query Dual-Evaluation Results
```python
# Sessions with good accuracy but poor latency
sessions = session.query(TestSession).filter(
    TestSession.accuracy_result == "PASS",
    TestSession.latency_result == "FAIL"
).all()
```

---

## File Locations

```
backend/
├── migrations/versions/
│   ├── 20251111_add_frontend_playing_delay.py    ← Migration 1
│   └── 20251111_add_dual_evaluation_fields.py    ← Migration 2
├── scripts/
│   ├── apply_migrations.sh                       ← Apply helper
│   ├── rollback_migrations.sh                    ← Rollback helper
│   └── test_new_migrations.py                    ← Verification tests
└── migrations/docs/
    ├── DUAL_EVALUATION_MIGRATION_GUIDE.md        ← Full guide
    ├── MIGRATION_CREATION_REPORT.md              ← Detailed report
    └── QUICK_REFERENCE.md                        ← This file
```

---

## Common Tasks

### Check Current Revision
```bash
alembic current
```

### View Migration History
```bash
alembic history | head -20
```

### Apply Specific Migration
```bash
alembic upgrade 950b4c965ca9  # Just frontend_playing_delay_ms
alembic upgrade a1b2c3d4e5f6  # Both migrations
alembic upgrade head           # All pending migrations
```

### Generate SQL (without applying)
```bash
alembic upgrade head --sql > migration.sql
```

---

## Troubleshooting

### "Column already exists"
- Migrations check for existing columns before adding
- If error persists, check model vs database schema mismatch

### "Index already exists"
- Migrations gracefully handle existing indexes
- Safe to ignore if migration succeeds

### "Revision not found"
- Check `alembic current` matches expected revision
- May need to update `down_revision` in migration files

---

## Success Checklist

- [ ] Applied migrations: `./scripts/apply_migrations.sh`
- [ ] Verified fields exist: `python3 scripts/test_new_migrations.py`
- [ ] Updated code to use new fields
- [ ] Tested dual-evaluation queries
- [ ] Tested presentation delay tracking
- [ ] Updated API to return evaluation_details
- [ ] Created reports using new indexes

---

## Next Steps

1. **Apply migrations** to development database
2. **Update session finalization** to populate evaluation_details
3. **Add T0/T1 tracking** in frontend video player
4. **Create dual-evaluation reports** using new indexes
5. **Test in staging** before production deployment

---

For detailed documentation, see: [DUAL_EVALUATION_MIGRATION_GUIDE.md](./DUAL_EVALUATION_MIGRATION_GUIDE.md)
