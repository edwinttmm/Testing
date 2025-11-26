# Timing Quality Tracking - Quick Reference

## TL;DR

**3 new boolean flags** to prevent data corruption from bad timing:

- `TestSession.timing_degraded` - Is timing degraded? (wall clock vs precision)
- `TestSession.timing_verified` - Has timing been verified?
- `DetectionEvent.usable_for_validation` - Can we use this for validation?

## Quick Commands

```bash
# Apply migration
cd /home/rigade/Testing/ai-model-validation-platform/backend
alembic upgrade head
python scripts/migrate_existing_sessions.py

# Rollback if needed
alembic downgrade -1

# Check status
python -c "
from database import SessionLocal
from models import TestSession, DetectionEvent
db = SessionLocal()
print(f'Total sessions: {db.query(TestSession).count()}')
print(f'Degraded: {db.query(TestSession).filter(TestSession.timing_degraded==True).count()}')
print(f'Verified: {db.query(TestSession).filter(TestSession.timing_verified==True).count()}')
db.close()
"
```

## Field Guide

### TestSession Fields

| Field | Type | Default | Indexed | Purpose |
|-------|------|---------|---------|---------|
| `timing_degraded` | Boolean | `False` | ✅ | Timing source degraded (wall clock) |
| `timing_verified` | Boolean | `False` | ❌ | Timing verified against DB |

**When to set `timing_degraded=True`**:
- Using wall clock timestamps instead of LabJack
- Timing synchronization failed
- Hardware timing unavailable
- Fallback timing mode active

**When to set `timing_verified=True`**:
- After cross-checking timing against database
- After manual verification
- After automated verification passes

### DetectionEvent Fields

| Field | Type | Default | Indexed | Purpose |
|-------|------|---------|---------|---------|
| `usable_for_validation` | Boolean | `True` | ✅ | Master validation flag |
| `timing_degraded` | Boolean | `False` | ✅ | Detection timing quality |

**When to set `usable_for_validation=False`**:
- Timing is degraded
- Detection confidence too low
- Hardware signal quality poor
- Manual review fails
- Any reason that makes detection unreliable

## Code Snippets

### Creating a Session

```python
from models import TestSession
from database import SessionLocal

db = SessionLocal()

# ✅ GOOD: Precision timing
session = TestSession(
    name="HIL Test 001",
    project_id="proj-123",
    video_id="video-456",
    timing_degraded=False,      # Precision timing used
    timing_verified=True,       # Already verified
    precision_timing_enabled=True
)

# ⚠️ DEGRADED: Wall clock fallback
session_degraded = TestSession(
    name="Degraded Test",
    project_id="proj-123",
    video_id="video-456",
    timing_degraded=True,       # Wall clock timing
    timing_verified=False,      # Not verified
    precision_timing_enabled=False
)

db.add(session)
db.commit()
db.close()
```

### Creating a Detection

```python
from models import DetectionEvent

db = SessionLocal()

# ✅ GOOD: Valid detection
detection = DetectionEvent(
    test_session_id="session-789",
    timestamp=1234567.89,
    usable_for_validation=True,    # Valid for validation
    timing_degraded=False,         # Precision timing
    labjack_timestamp=1234567.89,
    labjack_voltage=3.3
)

# ❌ BAD: Unusable detection
bad_detection = DetectionEvent(
    test_session_id="session-789",
    timestamp=1234568.00,
    usable_for_validation=False,   # Don't use
    timing_degraded=True,          # Degraded timing
    labjack_timestamp=None
)

db.add(detection)
db.commit()
db.close()
```

### Filtering Sessions

```python
from models import TestSession
from database import SessionLocal

db = SessionLocal()

# Get only verified, non-degraded sessions
good_sessions = db.query(TestSession).filter(
    TestSession.timing_verified == True,
    TestSession.timing_degraded == False
).all()

# Get sessions needing verification
unverified = db.query(TestSession).filter(
    TestSession.timing_verified == False
).all()

# Get degraded sessions
degraded = db.query(TestSession).filter(
    TestSession.timing_degraded == True
).all()

db.close()
```

### Filtering Detections

```python
from models import DetectionEvent
from database import SessionLocal

db = SessionLocal()

# Get only usable detections
usable = db.query(DetectionEvent).filter(
    DetectionEvent.usable_for_validation == True
).all()

# Get detections with good timing
good_timing = db.query(DetectionEvent).filter(
    DetectionEvent.timing_degraded == False
).all()

# Get unusable detections (for review)
unusable = db.query(DetectionEvent).filter(
    DetectionEvent.usable_for_validation == False
).all()

db.close()
```

### Updating Flags After Verification

```python
from models import TestSession
from database import SessionLocal

db = SessionLocal()

# After verifying timing
session = db.query(TestSession).filter(
    TestSession.id == "session-123"
).first()

if session and timing_check_passed(session):
    session.timing_verified = True
    session.timing_degraded = False
    db.commit()

db.close()
```

## SQL Queries

```sql
-- Count by timing quality
SELECT
    timing_degraded,
    timing_verified,
    COUNT(*) as count
FROM test_sessions
GROUP BY timing_degraded, timing_verified;

-- Find unverified sessions
SELECT id, name, created_at
FROM test_sessions
WHERE timing_verified = false
ORDER BY created_at DESC
LIMIT 10;

-- Count unusable detections
SELECT COUNT(*)
FROM detection_events
WHERE usable_for_validation = false;

-- Sessions with all good detections
SELECT ts.id, ts.name,
    COUNT(CASE WHEN de.usable_for_validation = true THEN 1 END) as good,
    COUNT(*) as total
FROM test_sessions ts
JOIN detection_events de ON de.test_session_id = ts.id
GROUP BY ts.id, ts.name
HAVING COUNT(*) = COUNT(CASE WHEN de.usable_for_validation = true THEN 1 END);
```

## Decision Tree

### When Creating a Session

```
Is hardware timing available?
├─ Yes → timing_degraded = False
│        Is timing verified?
│        ├─ Yes → timing_verified = True
│        └─ No  → timing_verified = False
│
└─ No  → timing_degraded = True
         timing_verified = False
```

### When Creating a Detection

```
Is hardware timestamp available?
├─ Yes → timing_degraded = False
│        Is detection reliable?
│        ├─ Yes → usable_for_validation = True
│        └─ No  → usable_for_validation = False
│
└─ No  → timing_degraded = True
         usable_for_validation = False
```

## Common Patterns

### Pattern 1: Precision Timing Session

```python
session = TestSession(
    name="HIL Test",
    timing_degraded=False,
    timing_verified=True,
    precision_timing_enabled=True,
    hil_timing_enabled=True
)
```

### Pattern 2: Degraded Timing Session (Fallback)

```python
session = TestSession(
    name="Fallback Test",
    timing_degraded=True,
    timing_verified=False,
    precision_timing_enabled=False
)
```

### Pattern 3: Filtering for Validation

```python
# Only use high-quality sessions for validation
sessions = db.query(TestSession).filter(
    TestSession.timing_verified == True,
    TestSession.timing_degraded == False,
    TestSession.status == 'completed'
).all()

# Only use reliable detections
detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.usable_for_validation == True
).all()
```

### Pattern 4: Quality Metrics Dashboard

```python
def get_timing_quality_metrics(db):
    """Get timing quality metrics for dashboard"""
    total_sessions = db.query(TestSession).count()
    degraded = db.query(TestSession).filter(
        TestSession.timing_degraded == True
    ).count()
    verified = db.query(TestSession).filter(
        TestSession.timing_verified == True
    ).count()

    total_detections = db.query(DetectionEvent).count()
    unusable = db.query(DetectionEvent).filter(
        DetectionEvent.usable_for_validation == False
    ).count()

    return {
        'sessions': {
            'total': total_sessions,
            'degraded': degraded,
            'degraded_pct': (degraded / total_sessions * 100) if total_sessions > 0 else 0,
            'verified': verified,
            'verified_pct': (verified / total_sessions * 100) if total_sessions > 0 else 0
        },
        'detections': {
            'total': total_detections,
            'unusable': unusable,
            'unusable_pct': (unusable / total_detections * 100) if total_detections > 0 else 0
        }
    }
```

## Troubleshooting

### Issue: All sessions showing as degraded

**Check**:
```python
degraded_count = db.query(TestSession).filter(
    TestSession.timing_degraded == True
).count()
```

**Cause**: Initial migration marks all as degraded

**Solution**: Run verification and update:
```python
for session in verified_sessions:
    session.timing_verified = True
    session.timing_degraded = False
db.commit()
```

### Issue: New sessions still showing as degraded

**Check**: Session creation code

**Solution**: Ensure flags are set:
```python
session = TestSession(
    timing_degraded=False,  # Add this
    timing_verified=True     # Add this
)
```

### Issue: Detections not being used in validation

**Check**:
```python
unusable = db.query(DetectionEvent).filter(
    DetectionEvent.usable_for_validation == False
).count()
```

**Solution**: Review why detections are marked unusable and fix root cause

## Best Practices

1. **Always set timing flags** when creating sessions
2. **Verify timing** before marking `timing_verified=True`
3. **Filter by quality** in validation queries
4. **Monitor metrics** regularly
5. **Document reasons** when marking as unusable
6. **Review degraded sessions** periodically

## Links

- **Full Guide**: [/docs/TIMING_QUALITY_IMPLEMENTATION_SUMMARY.md](/docs/TIMING_QUALITY_IMPLEMENTATION_SUMMARY.md)
- **Migration Guide**: [/docs/DATABASE_MIGRATION_GUIDE.md](/docs/DATABASE_MIGRATION_GUIDE.md)
- **ADR**: [/docs/ADR_TIMING_QUALITY_TRACKING.md](/docs/ADR_TIMING_QUALITY_TRACKING.md)
- **Models**: [/models.py](/models.py)
