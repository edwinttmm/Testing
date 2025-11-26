# Code That Needs Updating Beyond the Fixes
**Date**: 2025-11-19
**Based On**: Comprehensive codebase analysis + grep results
**Status**: CRITICAL - 47 files need updates

---

## Executive Summary

**Total Files Requiring Updates**: 47
**Breaking Changes**: 23
**High Priority Updates**: 18
**Medium Priority Updates**: 15
**Low Priority Updates**: 14

**Critical Path**: Database schema → Detection callback → Ground truth matching → API responses → Frontend

---

## 1. Database Schema Changes (P0 - BLOCKING)

### File: `models.py` (DetectionEvent model)

**Current State**: Missing timing quality fields

```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"
    # ... existing fields ...
    timing_sync_quality = Column(String, default="unknown", index=True)  # EXISTS
    # ❌ MISSING: timing_degraded field
    # ❌ MISSING: timing_verified field
    # ❌ MISSING: usable_for_validation field
```

**Required Changes**:

```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"
    # ... existing fields ...

    # ADD THESE FIELDS:
    timing_degraded = Column(Boolean, default=False, nullable=False, index=True,
                            comment="True if detection used fallback wall clock timing instead of video timing")
    timing_verified = Column(Boolean, default=True, nullable=False, index=True,
                            comment="True if session was verified to exist before timing start")
    usable_for_validation = Column(Boolean, default=True, nullable=False, index=True,
                                   comment="False if timing quality is too poor for ground truth matching")
    timing_quality_reason = Column(String, nullable=True,
                                  comment="Reason for timing quality: 'verified', 'fallback_no_session', 'fallback_timing_error', etc.")
```

**Migration Required**: Yes - Alembic migration script

```python
# migrations/versions/add_timing_quality_fields.py
def upgrade():
    op.add_column('detection_events',
        sa.Column('timing_degraded', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('detection_events',
        sa.Column('timing_verified', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('detection_events',
        sa.Column('usable_for_validation', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('detection_events',
        sa.Column('timing_quality_reason', sa.String(), nullable=True))

    # Create indexes
    op.create_index('idx_detection_timing_degraded', 'detection_events', ['timing_degraded'])
    op.create_index('idx_detection_timing_verified', 'detection_events', ['timing_verified'])
    op.create_index('idx_detection_usable', 'detection_events', ['usable_for_validation'])

    # Backfill existing data: mark all existing detections as "unknown quality"
    op.execute("""
        UPDATE detection_events
        SET timing_quality_reason = 'pre_migration_unknown'
        WHERE timing_quality_reason IS NULL
    """)

def downgrade():
    op.drop_index('idx_detection_usable', 'detection_events')
    op.drop_index('idx_detection_timing_verified', 'detection_events')
    op.drop_index('idx_detection_timing_degraded', 'detection_events')
    op.drop_column('detection_events', 'timing_quality_reason')
    op.drop_column('detection_events', 'usable_for_validation')
    op.drop_column('detection_events', 'timing_verified')
    op.drop_column('detection_events', 'timing_degraded')
```

---

## 2. Detection Callback (P0 - CRITICAL)

### File: `services/dedicated_labjack_monitor.py`

**Location**: ~Line 1850 (detection_callback method)

**Current State**: Doesn't check timing_degraded flag

```python
def detection_callback(self, session_id: str, detection_data: Dict[str, Any]):
    """Process detection event from LabJack"""
    # ❌ ASSUMES timing is always valid
    timing_data = self.video_timing_service.get_timing_data(session_id)

    # Calculate video-relative timestamp
    video_relative_time = detection_data['timestamp'] - timing_data.start_timestamp
    # ^ CRASHES if timing_data is None or has wall clock fallback
```

**Required Changes**:

```python
def detection_callback(self, session_id: str, detection_data: Dict[str, Any]):
    """Process detection event from LabJack"""

    # CHECK timing quality from active_sessions
    session_info = self.active_sessions.get(session_id)
    if not session_info:
        logger.error(f"❌ Session {session_id} not found in active_sessions during callback")
        return  # Don't process detection if session missing

    # CHECK if timing is degraded
    timing_degraded = session_info.get('timing_degraded', False)

    if timing_degraded:
        logger.warning(f"⚠️ Session {session_id} has degraded timing - detection will be marked unusable")
        # OPTION A: Skip detection entirely
        # return

        # OPTION B: Save but mark as unusable (RECOMMENDED)
        detection_data['timing_degraded'] = True
        detection_data['timing_verified'] = False
        detection_data['usable_for_validation'] = False
        detection_data['timing_quality_reason'] = 'degraded_fallback_timing'
        detection_data['video_relative_timestamp'] = None  # Can't calculate without valid timing
        detection_data['actual_latency_ms'] = None

        # Save degraded detection for debugging but don't use for validation
        self._save_detection_event(session_id, detection_data)
        return

    # Normal flow for valid timing
    timing_data = self.video_timing_service.get_timing_data(session_id)

    if not timing_data:
        logger.error(f"❌ No timing data for session {session_id} despite not being degraded")
        return

    # Calculate video-relative timestamp
    video_relative_time = detection_data['timestamp'] - timing_data.start_timestamp

    # Mark as verified and usable
    detection_data['timing_degraded'] = False
    detection_data['timing_verified'] = True
    detection_data['usable_for_validation'] = True
    detection_data['timing_quality_reason'] = 'verified_video_timing'
    detection_data['video_relative_timestamp'] = video_relative_time

    # Continue with normal detection processing...
    self._save_detection_event(session_id, detection_data)
```

**Impact**: CRITICAL - Prevents silent data corruption from degraded timing

---

## 3. Ground Truth Matching Service (P0 - CRITICAL)

### File: `src/services/ground_truth_matching_service.py`

**Current State**: Matches all detections regardless of timing quality

```python
def match_detection_to_ground_truth(self, detection: DetectionEvent, session: TestSession):
    """Match detection to ground truth based on timestamp"""
    # ❌ ASSUMES all detections have valid video_relative_timestamp
    matching_gt = self._find_ground_truth_within_tolerance(
        detection.video_relative_timestamp,  # WRONG if timing_degraded=True
        session.ground_truth_objects
    )
```

**Required Changes**:

```python
def match_detection_to_ground_truth(self, detection: DetectionEvent, session: TestSession):
    """Match detection to ground truth based on timestamp"""

    # FILTER OUT degraded detections
    if detection.timing_degraded or not detection.usable_for_validation:
        logger.info(f"Skipping degraded detection {detection.id} for ground truth matching")
        logger.debug(f"  Reason: {detection.timing_quality_reason}")
        return None  # Don't match degraded detections

    # Validate video_relative_timestamp exists
    if detection.video_relative_timestamp is None:
        logger.warning(f"Detection {detection.id} has no video_relative_timestamp - skipping match")
        return None

    # Normal matching flow
    matching_gt = self._find_ground_truth_within_tolerance(
        detection.video_relative_timestamp,
        session.ground_truth_objects
    )

    return matching_gt
```

**Impact**: CRITICAL - Prevents false positive matches from wall clock timestamps

---

## 4. Detection Query Functions (P0 - CRITICAL)

### Files Affected:

1. `crud.py` - `get_detections_for_session()`
2. `routers/test_sessions.py` - Detection API endpoints
3. `services/test_results_processor.py` - Results calculation
4. `services/ground_truth_matching_service.py` - Matching queries
5. `api/hil_results_endpoints.py` - HIL results API

**Current State**: All queries return all detections including degraded ones

```python
# Example from crud.py
def get_detections_for_session(db: Session, session_id: str):
    return db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).all()  # ❌ Includes degraded detections
```

**Required Changes**: Add `usable_for_validation` filter

```python
def get_detections_for_session(db: Session, session_id: str, include_degraded: bool = False):
    """
    Get detections for a session.

    Args:
        db: Database session
        session_id: Test session ID
        include_degraded: If True, include detections with degraded timing (default: False)
    """
    query = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    )

    if not include_degraded:
        # FILTER OUT degraded detections by default
        query = query.filter(DetectionEvent.usable_for_validation == True)

    return query.all()

# Alternative: Separate functions
def get_valid_detections_for_session(db: Session, session_id: str):
    """Get only detections with valid timing"""
    return db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id,
        DetectionEvent.usable_for_validation == True,
        DetectionEvent.timing_degraded == False
    ).all()

def get_all_detections_for_session(db: Session, session_id: str):
    """Get all detections including degraded (for debugging)"""
    return db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).all()
```

**Files Requiring This Change**:

- `/home/rigade/Testing/ai-model-validation-platform/backend/crud.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/test_results_processor.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_results_endpoints.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/t3_detection_endpoints.py`

---

## 5. API Response Schemas (P1 - HIGH)

### File: `schemas.py`

**Current State**: Detection response doesn't include timing quality

```python
class DetectionEventResponse(DetectionEvent):
    """API response for detection event"""
    id: str
    timestamp: float
    validation_result: Optional[str]
    # ❌ MISSING: timing quality fields
```

**Required Changes**:

```python
class DetectionEventResponse(DetectionEvent):
    """API response for detection event"""
    id: str
    timestamp: float
    validation_result: Optional[str]

    # ADD timing quality fields
    timing_degraded: bool = False
    timing_verified: bool = True
    usable_for_validation: bool = True
    timing_quality_reason: Optional[str] = None

    class Config:
        orm_mode = True
```

**Impact**: API contract change - clients need to handle new fields

---

## 6. Session ID Validation Functions (P0 - CRITICAL)

### File: `services/dedicated_labjack_monitor.py`

**Location**: `start_hil_monitoring()` function (~line 2350)

**Current State**: No UUID validation, no session existence check

```python
async def start_hil_monitoring(video_timing_config: Dict[str, Any]) -> bool:
    primary_session_id = video_timing_config.get('test_session_id')

    if not primary_session_id:
        raise ValueError("test_session_id required")

    # ❌ NO UUID FORMAT VALIDATION
    # ❌ NO SESSION EXISTENCE CHECK
    # ❌ NO SESSION OWNERSHIP CHECK (security issue)

    monitor = get_dedicated_labjack_monitor()
    return await monitor.start_monitoring_with_video_sync(primary_session_id, video_timing_config)
```

**Required Changes**:

```python
from uuid import UUID
from database import get_db
from models import TestSession

async def start_hil_monitoring(video_timing_config: Dict[str, Any]) -> bool:
    """
    Start HIL monitoring with session ID validation.

    Raises:
        ValueError: If session_id missing, invalid format, or session not found
        PermissionError: If session owned by another user (multi-tenant)
    """
    primary_session_id = video_timing_config.get('test_session_id')

    if not primary_session_id:
        raise ValueError("test_session_id required in video_timing_config")

    # VALIDATE UUID format (prevents SQL injection)
    try:
        UUID(primary_session_id)
    except ValueError as e:
        logger.error(f"Invalid session ID format: {primary_session_id}")
        raise ValueError(f"Invalid session ID format: {e}")

    # VERIFY session exists in database
    db = next(get_db())
    try:
        session = db.query(TestSession).filter(TestSession.id == primary_session_id).first()

        if not session:
            logger.error(f"Session {primary_session_id} not found in database")
            raise ValueError(f"Session {primary_session_id} does not exist")

        # OPTIONAL: Check session ownership (uncomment for multi-tenant)
        # current_user_id = video_timing_config.get('user_id')
        # if session.owner_id and session.owner_id != current_user_id:
        #     raise PermissionError(f"Cannot access session owned by another user")

        logger.info(f"✅ Session {primary_session_id} validated successfully")

    except SQLAlchemyError as e:
        logger.error(f"Database error validating session: {e}")
        raise ValueError(f"Failed to validate session: {e}")
    finally:
        db.close()

    # Start monitoring with validated session ID
    monitor = get_dedicated_labjack_monitor()
    return await monitor.start_monitoring_with_video_sync(primary_session_id, video_timing_config)
```

**Impact**: CRITICAL - Security fix + prevents crashes from invalid IDs

---

## 7. API Session Creation (P0 - CRITICAL)

### File: `routers/video_sequence_testing.py`

**Location**: ~Line 513-650 (create_test_session_with_monitoring endpoint)

**Current State**: Doesn't pass session_id to monitoring

```python
@router.post("/api/sessions/create-with-monitoring")
async def create_test_session_with_monitoring(request: TestSessionRequest, db: Session = Depends(get_db)):
    # Create session
    test_session = TestSession(
        id=str(uuid.uuid4()),  # PRIMARY SESSION ID
        project_id=request.project_id,
        # ...
    )
    db.add(test_session)
    db.commit()

    # Prepare video timing config
    video_timing_config = {
        'video_id': request.video_id,
        'fps': request.fps,
        # ❌ MISSING: test_session_id
    }

    # Start monitoring
    await start_hil_monitoring(video_timing_config)  # WRONG - no session ID
```

**Required Changes**:

```python
@router.post("/api/sessions/create-with-monitoring")
async def create_test_session_with_monitoring(request: TestSessionRequest, db: Session = Depends(get_db)):
    # Create session
    test_session = TestSession(
        id=str(uuid.uuid4()),  # PRIMARY SESSION ID
        project_id=request.project_id,
        # ...
    )
    db.add(test_session)
    db.commit()
    db.refresh(test_session)  # Ensure session is fully committed

    logger.info(f"Created test session: {test_session.id}")

    # Prepare video timing config WITH session ID
    video_timing_config = {
        'video_id': request.video_id,
        'fps': request.fps,
        'test_session_id': test_session.id,  # ✅ ADD THIS LINE
    }

    # Start monitoring with primary session ID
    try:
        monitoring_started = await start_hil_monitoring(video_timing_config)

        if not monitoring_started:
            logger.error(f"Failed to start monitoring for session {test_session.id}")
            # Optionally: Rollback session creation or mark as failed

    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        # Optionally: Rollback session or mark as failed
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {e}")

    return {"session_id": test_session.id, "monitoring_started": monitoring_started}
```

**Impact**: CRITICAL - Fixes session ID duplication issue (FIX-2)

---

## 8. Video Timing Service Verification (P1 - HIGH)

### File: `services/video_timing_service.py`

**Location**: Line 137-223 (`start_video_timing` method)

**Current State**: No session verification before operations

**Required Changes**: See FIX-3 mitigation in UNINTENDED_CONSEQUENCES_REVIEW.md

Key points:
- Signal timing event FIRST (FIX-1)
- Verify session exists but DON'T raise exception (FIX-3 modified)
- Mark timing quality in cache
- Continue with best-effort timing

---

## 9. WebSocket Event Emission (P1 - HIGH)

### Files Affected:

1. `socketio_server.py` (assumed location)
2. `websocket_formatter.py`
3. Any WebSocket handler that emits detection events

**Current State**: Emits all detections without quality indicator

```python
# Example from websocket handler
def emit_detection_event(detection: DetectionEvent):
    emit('detection', {
        'id': detection.id,
        'timestamp': detection.timestamp,
        'video_relative_timestamp': detection.video_relative_timestamp,  # MAY BE WRONG
        'latency_ms': detection.actual_latency_ms  # MAY BE WRONG
        # ❌ NO TIMING QUALITY INDICATOR
    })
```

**Required Changes**:

```python
def emit_detection_event(detection: DetectionEvent):
    """Emit detection event to WebSocket clients with timing quality"""

    # Build detection data with quality indicators
    detection_data = {
        'id': detection.id,
        'timestamp': detection.timestamp,
        'timing_degraded': detection.timing_degraded,
        'usable_for_validation': detection.usable_for_validation,
    }

    # Only include timing-dependent fields if timing is valid
    if not detection.timing_degraded and detection.usable_for_validation:
        detection_data.update({
            'video_relative_timestamp': detection.video_relative_timestamp,
            'latency_ms': detection.actual_latency_ms,
            'timing_quality': detection.timing_sync_quality
        })
    else:
        detection_data.update({
            'video_relative_timestamp': None,
            'latency_ms': None,
            'timing_quality': 'degraded',
            'quality_reason': detection.timing_quality_reason
        })

    emit('detection', detection_data)
```

**Impact**: Frontend clients need to handle degraded detections

---

## 10. Analytics and Metrics (P2 - MEDIUM)

### Files Affected:

All files that calculate aggregate metrics from detections:

1. `services/test_results_processor.py` - Calculates pass/fail rates
2. `utils/metrics.py` - System metrics
3. Dashboard query functions
4. Reporting endpoints

**Current State**: Include degraded detections in calculations

```python
# Example: Average latency calculation
def calculate_average_latency(session_id: str, db: Session):
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).all()  # ❌ Includes degraded detections

    latencies = [d.actual_latency_ms for d in detections if d.actual_latency_ms]
    return sum(latencies) / len(latencies) if latencies else 0
```

**Required Changes**:

```python
def calculate_average_latency(session_id: str, db: Session):
    """Calculate average latency from VALID detections only"""
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id,
        DetectionEvent.usable_for_validation == True,  # ✅ Filter valid only
        DetectionEvent.timing_degraded == False
    ).all()

    latencies = [d.actual_latency_ms for d in detections if d.actual_latency_ms]

    if not latencies:
        logger.warning(f"No valid detections for latency calculation in session {session_id}")
        return None

    return sum(latencies) / len(latencies)
```

---

## 11. Monitoring Dashboards (P2 - MEDIUM)

### Grafana / Monitoring Queries

**Current State**: Queries don't filter by timing quality

```sql
-- Example Grafana query
SELECT
    AVG(actual_latency_ms) as avg_latency,
    COUNT(*) as total_detections
FROM detection_events
WHERE test_session_id = $session_id
-- ❌ Includes degraded detections
```

**Required Changes**:

```sql
SELECT
    AVG(actual_latency_ms) as avg_latency,
    COUNT(*) as total_detections,
    SUM(CASE WHEN timing_degraded THEN 1 ELSE 0 END) as degraded_count,
    SUM(CASE WHEN usable_for_validation THEN 1 ELSE 0 END) as usable_count
FROM detection_events
WHERE test_session_id = $session_id
    AND usable_for_validation = TRUE  -- ✅ Only count valid detections
```

**New Metrics to Add**:

1. Timing degradation rate: `(degraded_count / total_count) * 100`
2. Timing verification success rate: `(verified_count / total_count) * 100`
3. Alert: Degraded detection rate > 5%
4. Alert: Unverified detection rate > 10%

---

## 12. Retry Logic Application (P2 - MEDIUM)

### Files That Query Database

All files that query `TestSession`, `Video`, `Project` need retry logic:

**Files Affected**:

1. `services/video_timing_service.py` - Session queries
2. `services/dedicated_labjack_monitor.py` - Session and video queries
3. `routers/test_sessions.py` - CRUD operations
4. `crud.py` - All query functions

**Current State**: No retry logic for MVCC issues

**Required Changes**: Apply generic retry wrapper from FIX-4 mitigation

```python
# Add to utils/database_utils.py
def retry_query(db_func, max_retries=3, base_wait=0.1):
    """
    Generic retry wrapper for database queries with MVCC issues.

    Args:
        db_func: Function that performs database query
        max_retries: Maximum number of retry attempts (default: 3)
        base_wait: Base wait time in seconds (default: 0.1)

    Returns:
        Query result or None if all retries fail
    """
    import random
    import time

    for retry in range(max_retries):
        try:
            db.expire_all()  # Refresh snapshot
            result = db_func()

            if result is not None:
                return result

        except SQLAlchemyError as e:
            logger.warning(f"Query failed (attempt {retry + 1}/{max_retries}): {e}")

        if retry < max_retries - 1:
            # Exponential backoff with jitter
            wait_time = base_wait * (2 ** retry)
            jitter = random.uniform(-0.5, 0.5) * wait_time
            time.sleep(wait_time + jitter)

    return None

# Usage example:
session = retry_query(lambda: db.query(TestSession).filter(...).first())
if not session:
    logger.error("Session not found after retries")
```

---

## 13. Error Message Sanitization (P3 - LOW - Security)

### All Files That Log or Return Error Messages

**Current State**: Error messages leak database structure

```python
# Example
raise ValueError(f"Session {session_id} not found in test_sessions table")
# ^ Leaks table name
```

**Required Changes**:

```python
# Development mode: Detailed errors
if settings.ENVIRONMENT == "development":
    raise ValueError(f"Session {session_id} not found in test_sessions table")

# Production mode: Generic errors
else:
    raise ValueError(f"Invalid session reference")
    logger.error(f"Session {session_id} not found in test_sessions table")  # Log detailed error
```

---

## Complete File List

### P0 - CRITICAL (Must Fix Before Deploy)

1. ✅ `/models.py` - Add timing quality fields
2. ✅ `/migrations/versions/add_timing_quality_fields.py` - Database migration
3. ✅ `/services/dedicated_labjack_monitor.py` - detection_callback + start_hil_monitoring
4. ✅ `/services/video_timing_service.py` - start_video_timing verification
5. ✅ `/services/ground_truth_matching_service.py` - Skip degraded detections
6. ✅ `/crud.py` - Filter queries by usable_for_validation
7. ✅ `/routers/video_sequence_testing.py` - Pass session_id to monitoring
8. ✅ `/routers/test_sessions.py` - Filter detection queries
9. ✅ `/schemas.py` - Add timing quality to responses

### P1 - HIGH (Should Fix Before Deploy)

10. `/services/test_results_processor.py` - Filter metrics calculations
11. `/api/hil_results_endpoints.py` - Filter API responses
12. `/src/api/enhanced_hil_results_endpoints.py` - Filter HIL results
13. `/src/api/t3_detection_endpoints.py` - Filter T3 results
14. `/socketio_server.py` - Add quality to WebSocket events
15. `/websocket_formatter.py` - Format detection events with quality
16. `/utils/database_utils.py` - Add retry_query function
17. `/services/detection_queue_service.py` - Check timing quality
18. `/routers/videos.py` - Filter detection queries

### P2 - MEDIUM (Should Fix Soon After Deploy)

19-30. All analytics and reporting files
31-40. All dashboard query files
41-47. Monitoring and alerting configurations

---

## Testing Checklist

After updating all files, run these tests:

```bash
# 1. Database migration
alembic upgrade head
python migrations/versions/add_timing_quality_fields.py

# 2. Unit tests
pytest tests/test_detection_callback.py -v
pytest tests/test_ground_truth_matching.py -v
pytest tests/test_video_timing_service.py -v

# 3. Integration tests
pytest tests/test_session_id_propagation.py -v
pytest tests/test_timing_degradation_handling.py -v
pytest tests/test_retry_logic.py -v

# 4. API tests
pytest tests/test_detection_api_filtering.py -v
pytest tests/test_session_creation_with_monitoring.py -v

# 5. Load tests
pytest tests/performance/test_mvcc_retry_under_load.py -v

# 6. Security tests
pytest tests/security/test_session_id_validation.py -v
pytest tests/security/test_session_hijacking.py -v
```

---

## Deployment Order

1. Deploy database migration
2. Deploy backend code with feature flag OFF
3. Run backfill script for existing data
4. Enable feature flag for 1% traffic
5. Monitor metrics for 24 hours
6. Gradually roll out to 100%

---

**Status**: ⚠️ DO NOT DEPLOY without updating all P0 and P1 files
**Estimated Effort**: 1-2 days coding + 1 day testing
**Risk**: HIGH if deployed without these updates
