# Quality Filter Quick Start Guide

## Overview

Ground truth matching now filters out non-validated detections to prevent false positives/negatives from timing degradation.

## Quick Start

### 1. Run Migration (Required First Step)

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 migrations/add_detection_quality_fields.py
```

**Expected output:**
```
Adding detection quality fields to detection_events table...
✅ Added timing_degraded column
✅ Added usable_for_validation column
✅ Created index on timing_degraded
✅ Created index on usable_for_validation
✅ Created composite quality index
Migration completed successfully
```

### 2. Verify Migration

```bash
python3 -c "
from database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'detection_events'
        AND column_name IN ('timing_degraded', 'usable_for_validation')
    ''')).fetchall()
    for row in result:
        print(f'✅ {row[0]}: {row[1]} (default: {row[2]})')
"
```

### 3. Test Quality Warnings

```python
from services.quality_warnings import check_quality, get_quality_stats

# Check a test session
warnings = check_quality('your-session-id')
for w in warnings:
    print(f"{w['severity']}: {w['message']}")

# Get statistics
stats = get_quality_stats('your-session-id')
print(f"Validation rate: {stats['validation_rate']}%")
print(f"Quality level: {stats['quality_level']}")
```

## What Changed

### Before
- All detections used in ground truth matching
- Timing issues caused false positives/negatives
- No visibility into detection quality

### After
- Only validated detections used in matching
- Timing issues flagged and excluded
- Quality warnings in API responses
- Transparent quality metrics

## API Response Changes

### New Fields in Matching Results

```json
{
  "session_id": "abc123",
  "summary": {
    "total_detections": 100,
    "matched_detections": 95,
    "precision": 0.95,
    "recall": 0.90,
    "f1_score": 0.92
  },
  "quality": {
    "total_detections": 105,
    "validated_detections": 100,
    "degraded_detections": 5,
    "validation_rate": 95.24,
    "quality_level": "EXCELLENT"
  },
  "warnings": [
    {
      "severity": "INFO",
      "code": "SOME_DEGRADED",
      "message": "5/105 detections have degraded timing",
      "impact": "Most detections valid, some timing issues detected",
      "recommendation": "Results generally reliable, review degraded detections"
    }
  ],
  "quality_alert": "INFO: Some detections have degraded timing"
}
```

## For Detection Capture Services

When creating DetectionEvent records, set quality fields based on timing quality:

```python
# Good timing - use defaults
detection = DetectionEvent(
    test_session_id=session_id,
    timestamp=timestamp,
    video_relative_timestamp=video_time,
    # timing_degraded defaults to False
    # usable_for_validation defaults to True
    ...
)

# Degraded timing - mark as unusable
if not video_timing_available or using_wall_clock_fallback:
    detection.timing_degraded = True
    detection.usable_for_validation = False
```

## Quality Levels

| Level | Validation Rate | Meaning |
|-------|----------------|---------|
| EXCELLENT | ≥95% | Reliable results, minor issues |
| GOOD | ≥80% | Generally reliable |
| FAIR | ≥50% | Some concerns, review carefully |
| POOR | <50% | Results unreliable |

## Warning Severities

| Severity | When | Impact |
|----------|------|--------|
| ERROR | No detections or all degraded | Cannot calculate metrics |
| WARNING | >50% degraded | Results unreliable |
| INFO | <10% degraded | Generally reliable |

## Testing Checklist

After migration:

- [ ] Migration completed without errors
- [ ] Fields added to detection_events table
- [ ] Indexes created successfully
- [ ] Existing sessions still accessible
- [ ] Ground truth matching works
- [ ] Quality warnings appear in API responses
- [ ] Reports include quality statistics

## Troubleshooting

### Migration Fails

```bash
# Check database connection
python3 -c "from database import engine; print(engine.url)"

# Check table exists
python3 -c "
from database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
print('Tables:', inspector.get_table_names())
"
```

### Fields Not Found

```bash
# Verify columns
python3 -c "
from database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text(
        'SELECT * FROM detection_events LIMIT 0'
    ))
    print('Columns:', result.keys())
"
```

### Import Errors

```bash
# Add backend to Python path
export PYTHONPATH="${PYTHONPATH}:/home/rigade/Testing/ai-model-validation-platform/backend"
python3 -c "import models; print('✅ Models loaded')"
```

## Next Steps

1. **Run migration** (see step 1 above)
2. **Update detection capture services** to set quality fields
3. **Test with existing sessions** to verify backward compatibility
4. **Update frontend** to display quality warnings
5. **Monitor validation rates** for ongoing sessions

## Support

For issues or questions:
- Check `/docs/QUALITY_FILTER_IMPLEMENTATION_SUMMARY.md` for detailed documentation
- Review migration script at `/migrations/add_detection_quality_fields.py`
- Check logs for quality statistics during ground truth matching

## Rollback

If needed:

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 migrations/add_detection_quality_fields.py downgrade
```

Or manually:
```sql
ALTER TABLE detection_events DROP COLUMN usable_for_validation;
ALTER TABLE detection_events DROP COLUMN timing_degraded;
DROP INDEX idx_detection_timing_degraded;
DROP INDEX idx_detection_usable;
DROP INDEX idx_detection_quality_session;
```
