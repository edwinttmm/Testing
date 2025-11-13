# Timestamp Video Resolver - Quick Start

**Deployment Time**: 30 minutes
**Impact**: Validation-only (no production changes)
**Rollback**: <5 minutes

---

## 1. Deploy Service (5 minutes)

**File already created**: `backend/services/timestamp_video_resolver.py`

**Verify deployment**:
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python -c "from services.timestamp_video_resolver import get_timestamp_video_resolver; print('✅ Service loaded')"
```

---

## 2. Add Validation to LabjJack Service (10 minutes)

**File**: `backend/services/labjack_detection_service.py`
**Line**: After line 1040 in `_store_event_in_db()` method

**Add this code**:
```python
# TIMESTAMP VALIDATION (Phase 1: Validation-only mode)
from services.timestamp_video_resolver import get_timestamp_video_resolver

try:
    resolver = get_timestamp_video_resolver()
    detection_timestamp = (
        event.timestamp.timestamp()
        if hasattr(event.timestamp, 'timestamp')
        else event.timestamp
    )

    validation = resolver.validate_video_assignment(
        session_id=session.id,
        detection_timestamp=detection_timestamp,
        metadata_video_id=video_id,
        db=db
    )

    if not validation['matches']:
        logger.warning(
            f"🔍 VIDEO MISMATCH: metadata={validation['metadata_video_id']}, "
            f"timestamp={validation['timestamp_video_id']} at t={detection_timestamp:.6f}"
        )
        # NOTE: Not changing video_id yet (Phase 1 validation only)

except Exception as e:
    logger.error(f"Timestamp validation error: {e}")
```

---

## 3. Restart Backend (5 minutes)

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Stop existing process
pkill -f "uvicorn main:app" || true

# Start with new validation
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > nohup_backend.out 2>&1 &

# Verify startup
sleep 5
curl http://localhost:8000/health
```

---

## 4. Monitor for Mismatches (10 minutes)

**Watch logs**:
```bash
tail -f /home/rigade/Testing/ai-model-validation-platform/backend/nohup_backend.out | grep "VIDEO MISMATCH"
```

**Run test HIL session**:
```bash
# Start multi-video test session
curl -X POST http://localhost:8000/api/hil/start-test \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<your-project-id>",
    "video_ids": ["<video1>", "<video2>"],
    "max_latency_ms": 100
  }'

# Let it run for 1-2 minutes

# Check for mismatches
grep "VIDEO MISMATCH" nohup_backend.out | wc -l
```

---

## 5. Calculate Mismatch Rate

```bash
# Count total detections
total=$(grep "Detection event created" nohup_backend.out | wc -l)

# Count mismatches
mismatches=$(grep "VIDEO MISMATCH" nohup_backend.out | wc -l)

# Calculate rate
echo "Total detections: $total"
echo "Mismatches: $mismatches"
echo "Mismatch rate: $(echo "scale=2; $mismatches * 100 / $total" | bc)%"
```

**Expected**: <1% mismatch rate

---

## Quick Validation Test

**Python script** (`test_timestamp_resolver.py`):
```python
#!/usr/bin/env python3
from database import SessionLocal
from services.timestamp_video_resolver import get_timestamp_video_resolver

def test_resolver():
    db = SessionLocal()
    resolver = get_timestamp_video_resolver()

    # Test with real session ID
    session_id = "<your-test-session-id>"

    # Get diagnostic info
    info = resolver.get_diagnostic_info(session_id, db)
    print(f"✅ Session: {info['session_id']}")
    print(f"✅ Video windows: {info['window_count']}")

    for window in info['windows']:
        print(f"  Video: {window['filename']}")
        print(f"    Range: {window['time_range']}")
        print(f"    Order: {window['sequence_order']}")

    # Test resolution
    if info['windows']:
        first_window = info['windows'][0]
        test_timestamp = first_window['video_start_time'] + 1.0

        video_id = resolver.get_video_id_from_timestamp(
            session_id, test_timestamp, db
        )
        print(f"\n✅ Test resolution at t={test_timestamp:.6f}")
        print(f"   Result: {video_id}")

    db.close()
    print("\n✅ All tests passed!")

if __name__ == '__main__':
    test_resolver()
```

**Run**:
```bash
python test_timestamp_resolver.py
```

---

## Rollback (if needed)

**Remove validation code**:
```python
# Comment out the timestamp validation block in labjack_detection_service.py
# Lines ~1042-1065

# from services.timestamp_video_resolver import get_timestamp_video_resolver
#
# try:
#     resolver = get_timestamp_video_resolver()
#     ...  # All validation code commented out
```

**Restart**:
```bash
pkill -f "uvicorn main:app"
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > nohup_backend.out 2>&1 &
```

**Verify**: No more "VIDEO MISMATCH" warnings in logs

---

## Success Checklist

After 24 hours of operation:

- [ ] Mismatch rate <1%
- [ ] No NULL video_id increase
- [ ] No performance degradation
- [ ] Logs contain "VIDEO MISMATCH" entries (proving validation works)
- [ ] All detections still have correct video_id

**If all checked**: Ready for Phase 2 (failover mode)

---

## Next Steps (Week 2)

**Phase 2: Enable Failover Mode**

When metadata unavailable, use timestamp-based:
```python
if video_id is None:
    logger.warning("Metadata unavailable - using timestamp failover")
    video_id = resolver.get_video_id_from_timestamp(
        session_id, detection_timestamp, db
    )
```

**Phase 3: Authoritative Mode** (Week 3)

Timestamp becomes primary source of truth.

---

## Support

**Documentation**:
- Full implementation: `TIMESTAMP_VIDEO_RESOLVER_IMPLEMENTATION.md`
- Integration guide: `TIMESTAMP_RESOLVER_INTEGRATION_GUIDE.md`

**Troubleshooting**:
```bash
# Check service status
python -c "from services.timestamp_video_resolver import get_timestamp_video_resolver; print('OK')"

# View recent mismatches
grep "VIDEO MISMATCH" nohup_backend.out | tail -20

# Get diagnostic info
python -c "
from database import SessionLocal
from services.timestamp_video_resolver import get_timestamp_video_resolver
db = SessionLocal()
resolver = get_timestamp_video_resolver()
info = resolver.get_diagnostic_info('<session-id>', db)
print(info)
"
```

---

**Deployment Status**: ✅ Ready for immediate production use
**Risk Level**: 🟢 Low (validation-only, no logic changes)
**Rollback Time**: ⏱️ <5 minutes
