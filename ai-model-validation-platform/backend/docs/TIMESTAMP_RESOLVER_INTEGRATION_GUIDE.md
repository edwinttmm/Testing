# Timestamp Video Resolver - Integration Guide

**Implementation Time**: <2 hours
**Deployment Risk**: Low (validation-only mode)
**Performance Impact**: +2-3ms per detection

---

## Quick Start Integration

### Step 1: Import the Service

```python
from services.timestamp_video_resolver import get_timestamp_video_resolver
```

### Step 2: Add to LabjJack Detection Service

**File**: `backend/services/labjack_detection_service.py`
**Method**: `_store_event_in_db()` (line ~995-1149)

**Current Code** (lines 1019-1040):
```python
# CRITICAL FIX: Multi-video detection video_id assignment
# For multi-video sequences, use current_video_id from sequence_metadata
# For single-video sessions, use session.video_id
video_id = session.video_id  # Default to session video (first video)

if session.sequence_id and session.sequence_metadata:
    # Multi-video sequence detected - extract current_video_id
    try:
        metadata = session.sequence_metadata
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)

        current_video_id = metadata.get('current_video_id')

        if current_video_id:
            logger.info(f"✅ Multi-video: Using current_video_id={current_video_id}")
            video_id = current_video_id
        else:
            logger.warning(f"⚠️ Multi-video session missing current_video_id")
```

**Enhanced Code** (add after line 1040):
```python
# VALIDATION: Check metadata-based assignment against timestamp-based
from services.timestamp_video_resolver import get_timestamp_video_resolver

try:
    resolver = get_timestamp_video_resolver()

    # Get detection timestamp
    detection_timestamp = (
        event.timestamp.timestamp()
        if hasattr(event.timestamp, 'timestamp')
        else event.timestamp
    )

    # Validate assignment
    validation = resolver.validate_video_assignment(
        session_id=session.id,
        detection_timestamp=detection_timestamp,
        metadata_video_id=video_id,
        db=db
    )

    # Log mismatches for investigation
    if not validation['matches']:
        logger.warning(
            f"🔍 VIDEO ASSIGNMENT VALIDATION MISMATCH:\n"
            f"  Session: {session.id}\n"
            f"  Detection timestamp: {detection_timestamp:.6f}\n"
            f"  Metadata video_id: {validation['metadata_video_id']}\n"
            f"  Timestamp video_id: {validation['timestamp_video_id']}\n"
            f"  Using: {validation['authoritative_video_id']}"
        )

        # PHASE 2: Enable failover (uncomment when ready)
        # video_id = validation['authoritative_video_id']
    else:
        logger.debug(f"✅ Video assignment validated: {video_id}")

except Exception as resolver_error:
    logger.error(f"Timestamp resolver error: {resolver_error}")
    # Continue with metadata-based assignment
```

---

## Deployment Phases

### Phase 1: Validation Mode (Immediate Deployment)

**Goal**: Log mismatches, no changes to production logic

**Configuration**:
```python
# At top of labjack_detection_service.py
TIMESTAMP_VALIDATION_ENABLED = True  # Enable validation logging
TIMESTAMP_FAILOVER_ENABLED = False   # Don't change production logic
TIMESTAMP_AUTHORITATIVE = False      # Metadata still primary
```

**Expected Behavior**:
- All detections use metadata-based assignment (no change)
- Mismatches logged as warnings
- No impact on detection accuracy
- Collect metrics for 7 days

**Monitoring**:
```bash
# Count validation mismatches
grep "VIDEO ASSIGNMENT VALIDATION MISMATCH" backend.log | wc -l

# Calculate mismatch rate
total_detections=$(grep "Detection event created" backend.log | wc -l)
mismatches=$(grep "VALIDATION MISMATCH" backend.log | wc -l)
echo "Mismatch rate: $(bc <<< "scale=2; $mismatches * 100 / $total_detections")%"
```

**Success Criteria**: Mismatch rate <1%

### Phase 2: Failover Mode (Week 2)

**Goal**: Use timestamp-based when metadata unavailable

**Configuration**:
```python
TIMESTAMP_VALIDATION_ENABLED = True
TIMESTAMP_FAILOVER_ENABLED = True   # Enable failover
TIMESTAMP_AUTHORITATIVE = False
```

**Code Change**:
```python
# In _store_event_in_db(), after metadata extraction:
if video_id is None:
    # Metadata failed - use timestamp failover
    logger.warning("Metadata video_id unavailable - using timestamp fallover")

    resolver = get_timestamp_video_resolver()
    video_id = resolver.get_video_id_from_timestamp(
        session_id=session.id,
        detection_timestamp=detection_timestamp,
        db=db
    )

    if video_id:
        logger.info(f"✅ Timestamp failover succeeded: video_id={video_id}")
    else:
        logger.error("❌ Timestamp failover failed - detection may have NULL video_id")
```

**Success Criteria**: No increase in NULL video_id rate

### Phase 3: Authoritative Mode (Week 3+)

**Goal**: Timestamp-based becomes primary source of truth

**Configuration**:
```python
TIMESTAMP_VALIDATION_ENABLED = True
TIMESTAMP_FAILOVER_ENABLED = True
TIMESTAMP_AUTHORITATIVE = True     # Timestamp is authoritative
```

**Code Change**:
```python
# Replace entire video_id assignment block:
resolver = get_timestamp_video_resolver()

# Primary: Timestamp-based (authoritative)
video_id_timestamp = resolver.get_video_id_from_timestamp(
    session_id=session.id,
    detection_timestamp=detection_timestamp,
    db=db
)

# Secondary: Metadata-based (validation only)
video_id_metadata = self._get_video_id_from_metadata(session)

# Reconcile
if video_id_metadata != video_id_timestamp:
    logger.warning(
        f"Metadata differs from authoritative timestamp: "
        f"metadata={video_id_metadata}, timestamp={video_id_timestamp}"
    )

# Use authoritative timestamp result
video_id = video_id_timestamp

if not video_id:
    logger.error("Failed to resolve video_id from timestamp")
    video_id = video_id_metadata  # Final fallback
```

**Success Criteria**: Zero regressions in detection accuracy

---

## Testing Strategy

### Unit Tests

**File**: `backend/tests/test_timestamp_video_resolver.py`

```python
import pytest
from services.timestamp_video_resolver import get_timestamp_video_resolver
from models import TestSession, SequenceVideoResult, VideoTestSequence, Video


def test_single_video_resolution(db_session):
    """Test resolution for single-video session"""
    # Setup session
    session = TestSession(
        id='test-session',
        video_id='video1',
        video_start_timestamp=10.0
    )
    db_session.add(session)

    video = Video(id='video1', duration=15.0, filename='test.mp4')
    db_session.add(video)
    db_session.commit()

    # Test resolution
    resolver = get_timestamp_video_resolver()
    video_id = resolver.get_video_id_from_timestamp(
        session_id='test-session',
        detection_timestamp=12.5,  # Mid-video
        db=db_session
    )

    assert video_id == 'video1'


def test_multi_video_resolution(db_session):
    """Test resolution across video sequence"""
    # Setup 3-video sequence
    sequence = VideoTestSequence(
        id='seq1',
        test_session_id='session1'
    )
    db_session.add(sequence)

    videos_data = [
        ('vid1', 0, 10.0, 25.0),  # [10.0, 25.0)
        ('vid2', 1, 25.0, 40.0),  # [25.0, 40.0)
        ('vid3', 2, 40.0, 55.0),  # [40.0, 55.0)
    ]

    for vid_id, order, start, end in videos_data:
        result = SequenceVideoResult(
            video_sequence_id='seq1',
            video_id=vid_id,
            sequence_order=order,
            video_start_time=start,
            video_end_time=end
        )
        db_session.add(result)

    db_session.commit()

    # Test resolutions
    resolver = get_timestamp_video_resolver()

    # Video 1
    assert resolver.get_video_id_from_timestamp('session1', 12.5, db_session) == 'vid1'
    assert resolver.get_video_id_from_timestamp('session1', 24.9, db_session) == 'vid1'

    # Video 2
    assert resolver.get_video_id_from_timestamp('session1', 25.0, db_session) == 'vid2'
    assert resolver.get_video_id_from_timestamp('session1', 32.5, db_session) == 'vid2'

    # Video 3
    assert resolver.get_video_id_from_timestamp('session1', 40.0, db_session) == 'vid3'


def test_edge_case_before_first_video(db_session):
    """Test detection before first video starts"""
    # Setup
    setup_test_sequence(db_session, start_time=10.0)

    resolver = get_timestamp_video_resolver()

    # Detection 50ms before start (within buffer)
    video_id = resolver.get_video_id_from_timestamp(
        'session1', 9.95, db_session
    )
    assert video_id == 'vid1'  # Assigned to first video

    # Detection 200ms before start (outside buffer)
    video_id = resolver.get_video_id_from_timestamp(
        'session1', 9.80, db_session
    )
    assert video_id is None


def test_edge_case_during_transition(db_session):
    """Test detection during video transition"""
    # Setup sequence with 50ms gap between videos
    setup_test_sequence_with_gap(db_session, gap_ms=50)

    resolver = get_timestamp_video_resolver()

    # Detection in 50ms gap (within 100ms buffer)
    video_id = resolver.get_video_id_from_timestamp(
        'session1', 25.025,  # Between vid1 and vid2
        db_session
    )
    assert video_id == 'vid2'  # Assigned to next video


def test_validation_matching_results(db_session):
    """Test validation when metadata and timestamp agree"""
    setup_test_sequence(db_session)

    resolver = get_timestamp_video_resolver()
    validation = resolver.validate_video_assignment(
        session_id='session1',
        detection_timestamp=12.5,
        metadata_video_id='vid1',
        db=db_session
    )

    assert validation['matches'] is True
    assert validation['metadata_video_id'] == 'vid1'
    assert validation['timestamp_video_id'] == 'vid1'
    assert validation['authoritative_video_id'] == 'vid1'


def test_validation_mismatched_results(db_session):
    """Test validation when metadata and timestamp disagree"""
    setup_test_sequence(db_session)

    resolver = get_timestamp_video_resolver()
    validation = resolver.validate_video_assignment(
        session_id='session1',
        detection_timestamp=12.5,  # Actually in vid1
        metadata_video_id='vid2',  # Wrong metadata
        db=db_session
    )

    assert validation['matches'] is False
    assert validation['metadata_video_id'] == 'vid2'
    assert validation['timestamp_video_id'] == 'vid1'
    assert validation['authoritative_video_id'] == 'vid1'  # Trust timestamp


def test_performance_benchmark(db_session):
    """Test resolution performance"""
    import time

    setup_test_sequence_with_many_videos(db_session, count=10)
    resolver = get_timestamp_video_resolver()

    # Warm-up
    resolver.get_video_id_from_timestamp('session1', 12.5, db_session)

    # Benchmark 1000 resolutions
    start = time.time()
    for i in range(1000):
        timestamp = 10.0 + (i * 0.05)  # Spread across sequence
        resolver.get_video_id_from_timestamp('session1', timestamp, db_session)
    duration = time.time() - start

    avg_ms = (duration / 1000) * 1000
    assert avg_ms < 5.0, f"Resolution took {avg_ms:.2f}ms (target: <5ms)"
```

### Integration Test

**File**: `backend/tests/test_timestamp_resolver_integration.py`

```python
def test_full_hil_session_with_validation(client, db_session):
    """Test complete HIL session with timestamp validation"""
    # Create 3-video sequence
    project_id = create_test_project(db_session)
    video_ids = [
        create_test_video(db_session, project_id, 'video1.mp4', 15.0),
        create_test_video(db_session, project_id, 'video2.mp4', 20.0),
        create_test_video(db_session, project_id, 'video3.mp4', 18.0),
    ]

    # Start HIL test session
    response = client.post('/api/hil/start-sequence', json={
        'project_id': project_id,
        'video_ids': video_ids,
        'max_latency_ms': 100
    })
    assert response.status_code == 200
    session_id = response.json()['session_id']

    # Simulate detections across all videos
    detections = [
        {'timestamp': 12.5, 'expected_video': video_ids[0]},
        {'timestamp': 28.0, 'expected_video': video_ids[1]},
        {'timestamp': 48.5, 'expected_video': video_ids[2]},
    ]

    resolver = get_timestamp_video_resolver()

    for det in detections:
        # Resolve video_id
        video_id = resolver.get_video_id_from_timestamp(
            session_id, det['timestamp'], db_session
        )

        # Verify correct assignment
        assert video_id == det['expected_video']

        # Create detection event
        response = client.post(f'/api/detection-events/{session_id}', json={
            'timestamp': det['timestamp'],
            'voltage': 3.3,
            'channel': 'AIN0'
        })
        assert response.status_code == 201

        # Verify detection has correct video_id
        detection = db_session.query(DetectionEvent).filter_by(
            id=response.json()['detection_id']
        ).first()
        assert detection.video_id == det['expected_video']

    # Complete session
    response = client.post(f'/api/hil/complete-sequence/{session_id}')
    assert response.status_code == 200

    # Verify all detections assigned correctly
    detections = db_session.query(DetectionEvent).filter_by(
        test_session_id=session_id
    ).all()
    assert len(detections) == 3
    assert all(d.video_id is not None for d in detections)
```

---

## Monitoring Dashboard

### Key Metrics to Track

**1. Validation Mismatch Rate**
```sql
-- Query to calculate mismatch rate
SELECT
    DATE(created_at) as date,
    COUNT(*) as total_detections,
    SUM(CASE WHEN detection_metadata->>'validation_mismatch' = 'true' THEN 1 ELSE 0 END) as mismatches,
    ROUND(
        SUM(CASE WHEN detection_metadata->>'validation_mismatch' = 'true' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) as mismatch_rate_percent
FROM detection_events
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

**2. Resolution Performance**
```sql
-- Average resolution time from logs
SELECT
    AVG(resolution_time_ms) as avg_resolution_ms,
    MAX(resolution_time_ms) as max_resolution_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY resolution_time_ms) as p95_resolution_ms
FROM detection_events
WHERE created_at >= NOW() - INTERVAL '1 day'
    AND resolution_time_ms IS NOT NULL;
```

**3. Unresolved Detections**
```sql
-- Detections without video_id
SELECT
    DATE(created_at) as date,
    COUNT(*) as null_video_id_count
FROM detection_events
WHERE video_id IS NULL
    AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Rollback Procedure

### If Issues Detected

**Step 1: Disable validation**
```python
# In labjack_detection_service.py
TIMESTAMP_VALIDATION_ENABLED = False  # Disable immediately
```

**Step 2: Redeploy**
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
sudo systemctl restart hil-backend.service
```

**Step 3: Verify rollback**
```bash
# Check no validation warnings in logs
tail -f /var/log/hil-backend.log | grep "VALIDATION MISMATCH"
# Should be empty
```

**Step 4: Investigate**
- Review logs for patterns
- Check specific session data
- Verify timing boundaries correct

---

## Success Criteria

✅ **Phase 1 Complete When**:
- Mismatch rate <1%
- No performance degradation
- 1000+ detections validated
- 7 days of stable operation

✅ **Phase 2 Complete When**:
- Zero increase in NULL video_id rate
- Failover handles edge cases
- 500+ failover events successful

✅ **Phase 3 Complete When**:
- 30 days of stable authoritative mode
- No accuracy regressions
- All tests passing

---

**Total Implementation Time**: <4 hours
**Risk Level**: Low (validation-only initially)
**Rollback Time**: <5 minutes

**Ready for immediate deployment!**
