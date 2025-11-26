# Detection Queue Test Quick Reference
## Fast Lookup for Test Execution

**Last Updated:** 2025-11-13

---

## Quick Test Commands

```bash
# Run all queue tests
pytest backend/tests/test_detection_queue.py -v

# Run integration tests only
pytest backend/tests/integration/test_detection_queue_integration.py -v

# Run performance tests
pytest backend/tests/performance/test_detection_queue_performance.py -v

# Run specific test
pytest backend/tests/test_detection_queue.py::test_race_condition_resolution -v

# Run with coverage
pytest backend/tests/test_detection_queue.py --cov=services.detection_queue_service --cov-report=html
```

---

## Quick Verification Queries

### Check NULL Rate (Should be 0%)
```sql
SELECT
    COUNT(*) FILTER (WHERE video_id IS NULL) as null_count,
    COUNT(*) as total,
    ROUND((COUNT(*) FILTER (WHERE video_id IS NULL)::decimal / COUNT(*)) * 100, 2) as null_pct
FROM detection_events
WHERE test_session_id = '<session_id>';
```

### Check Queue Health
```python
from services.detection_queue_service import get_detection_queue

queue = get_detection_queue()
health = queue.get_queue_health()
print(f"Healthy: {health['healthy']}")
print(f"Warnings: {health['warnings']}")
```

### Check Queue Stats
```python
stats = get_detection_queue().get_stats()
print(f"Total Queued: {stats['total_queued']}")
print(f"Total Flushed: {stats['total_flushed']}")
print(f"Avg Queue Time: {stats['avg_queue_time_ms']:.1f}ms")
```

---

## Critical Test Cases

### UT-001: Singleton Pattern
```python
def test_singleton_initialization():
    queue1 = get_detection_queue()
    queue2 = get_detection_queue()
    assert queue1 is queue2
```

### IT-001: Race Condition Fix (MOST IMPORTANT)
```python
async def test_race_condition_resolution(db_session):
    # Detection arrives BEFORE video starts
    detection = create_detection(video_id=None)
    queue.enqueue(session_id, detection.id, timestamp)

    # Video starts
    video_result = create_video_result(session_id, video_id)

    # Flush queue
    assigned = queue.flush_for_video(session_id, video_id, db)

    # Verify: NULL rate = 0%
    assert detection.video_id == video_id
```

### EC-004: Large Queue
```python
def test_large_queue_flush():
    # Queue 100 detections
    for i in range(100):
        queue.enqueue(session_id, f"det-{i}", timestamp)

    # Flush
    assigned = queue.flush_for_video(session_id, video_id, db)

    # Verify all assigned
    assert assigned == 100
```

---

## Performance Benchmarks

| Metric | Target | Critical |
|--------|--------|----------|
| NULL Rate | 0% | <5% |
| Avg Queue Time | <100ms | <500ms |
| Enqueue/s | >1000 | >500 |
| Flush/s | >500 | >200 |

---

## Common Issues & Solutions

### Issue: Tests failing with "Database locked"
**Solution:**
```python
# Use separate database for tests
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///test_queue.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
```

### Issue: Race condition test inconsistent
**Solution:**
```python
# Add explicit timing control
import time
queue.enqueue(session_id, detection.id, timestamp)
time.sleep(0.01)  # Ensure detection queued before flush
queue.flush_for_video(session_id, video_id, db)
```

### Issue: NULL rate still >0%
**Solution:**
```sql
-- Find detections not flushed
SELECT id, test_session_id, video_id, timestamp
FROM detection_events
WHERE video_id IS NULL
  AND test_session_id IN (
      SELECT DISTINCT test_session_id
      FROM sequence_video_results
  );

-- Manual flush if needed
-- (Should not happen in production)
```

---

## Rollback Commands

```bash
# Disable queue feature
export DETECTION_QUEUE_ENABLED=false

# Restart service
sudo systemctl restart ai-validation-backend

# Verify disabled
curl http://localhost:8000/api/queue/health
# Should return: {"enabled": false}
```

---

## Test Data Fixtures

```python
# Session fixture
@pytest.fixture
def test_session(db):
    session = TestSession(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status="in_progress"
    )
    db.add(session)
    db.commit()
    yield session

# Detection fixture (NULL video_id)
@pytest.fixture
def null_detection(db, test_session):
    det = DetectionEvent(
        id=str(uuid.uuid4()),
        test_session_id=test_session.id,
        video_id=None,  # Race condition
        timestamp=time.time(),
        validation_result="Pending"
    )
    db.add(det)
    db.commit()
    yield det
```

---

## Monitoring Commands

```python
# Check queue size
from services.detection_queue_service import get_detection_queue

queue = get_detection_queue()
print(f"Sessions with queued detections: {len(queue.get_all_queued_sessions())}")

for session_id in queue.get_all_queued_sessions():
    size = queue.get_queue_size(session_id)
    print(f"  {session_id}: {size} detections")

# Clear stuck queue (emergency)
queue.clear_queue("session-id-here")
```

---

## Test Execution Checklist

- [ ] Unit tests pass (8/8)
- [ ] Integration tests pass (3/3)
- [ ] Edge cases pass (4/4)
- [ ] Performance tests pass (2/2)
- [ ] NULL rate verified (0%)
- [ ] Queue stats healthy
- [ ] No memory leaks
- [ ] Rollback tested

---

## Quick Links

- **Full Test Plan:** `/backend/docs/QUEUE_TEST_PLAN.md`
- **Implementation:** `/backend/services/detection_queue_service.py`
- **Usage (LabJack):** `/backend/services/labjack_detection_service.py`
- **Usage (Video):** `/backend/routers/video_sequence_testing.py`

---

**End of Quick Reference**
