# File Update Checklist - Quality Tracking Implementation

## Executive Summary

This document tracks the systematic update of **47+ files** across the codebase to implement quality tracking and exception handling improvements identified by Agent 6.

**Total Impact:**
- **100+ DetectionEvent query locations** need quality filtering
- **46 files** with `start_video_timing` calls need degradation handling
- **202 files** with `SessionLocal()` need connection management fixes
- **24 files** using `timing_ready_event` need degradation awareness

---

## Category 1: DetectionEvent Quality Filtering

### Problem
All DetectionEvent queries assume data quality is valid. Need to filter by `usable_for_validation` flag.

### Files Requiring Updates (100+ locations)

#### Core Routers (High Priority)
1. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/hil_testing.py`
   - Lines: 109, 215, 368, 373, 431
   - **Impact**: HIL test results API

2. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions.py`
   - Lines: 928, 993, 1295, 1331, 1701, 2117
   - **Impact**: Test session management

3. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions_fixed.py`
   - Lines: 369, 616
   - **Impact**: Fixed test session endpoints

4. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/datasets.py`
   - Lines: 53, 192
   - **Impact**: Dataset API endpoints

5. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/videos.py`
   - Lines: 850, 1096
   - **Impact**: Video management API

6. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequence_testing.py`
   - Lines: 798, 979, 1480
   - **Impact**: Multi-video sequence testing

7. `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
   - Lines: 2345, 2473, 3286, 3593, 3690, 4670
   - **Impact**: Main application endpoints

#### Services (High Priority)
8. `/home/rigade/Testing/ai-model-validation-platform/backend/crud.py`
   - Line: 502
   - **Impact**: Core CRUD operations

#### Test Files (Medium Priority)
9-30. Various test files (see grep results)
   - **Impact**: Test suite accuracy

#### Scripts (Low Priority)
31-50. Various maintenance scripts
   - **Impact**: Data migration and analysis

### Update Template

```python
# BEFORE (Unsafe - uses all data)
detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id
).all()

# AFTER (Safe - filters by quality)
detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.usable_for_validation == True  # Quality filter
).all()
```

### Verification Steps
1. Search for `db.query(DetectionEvent)` without `usable_for_validation`
2. Confirm all queries include quality filter
3. Run integration tests to ensure no data loss
4. Check API responses for consistent behavior

---

## Category 2: Timing Degradation Handling

### Problem
46 files call `start_video_timing` and assume timing is always valid. Need to handle degraded mode.

### Files Requiring Updates (46 files)

#### Core Services (Critical Priority)
1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_timing_service.py`
   - **Already implements**: Source of timing degradation logic
   - **Action**: Document degradation mode return values

2. `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`
   - **Impact**: Hardware timing integration
   - **Action**: Add degradation checks before using timing data

3. `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`
   - **Impact**: Multi-video orchestration
   - **Action**: Handle partial timing availability

4. `/home/rigade/Testing/ai-model-validation-platform/backend/services/test_execution_service.py`
   - **Impact**: Test workflow execution
   - **Action**: Mark test sessions with timing quality status

#### Routers (High Priority)
5. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequence_testing.py`
   - **Impact**: Video sequence API
   - **Action**: Return timing quality status in responses

6. `/home/rigade/Testing/ai-model-validation-platform/backend/routes/video_timing.py`
   - **Impact**: Video timing API
   - **Action**: **ALREADY HANDLES** VideoTimingError

7. `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
   - **Impact**: Main application
   - **Action**: Add timing quality checks to test endpoints

#### Test Files (Medium Priority)
8-46. Various test files
   - **Impact**: Test coverage
   - **Action**: Add tests for degraded timing scenarios

### Update Template

```python
from services.video_timing_service import VideoTimingService, VideoTimingError

# BEFORE (Assumes timing always works)
timing = video_timing_service.start_video_timing(session_id, video_id)
# Use timing without checking quality

# AFTER (Handles degraded mode)
try:
    timing = video_timing_service.start_video_timing(session_id, video_id)

    # Check if timing is degraded
    if timing.get('timing_degraded', False):
        logger.warning(f"Session {session_id} operating with degraded timing")
        # Mark session quality
        session.timing_quality_degraded = True
        db.commit()

    # Use timing with awareness of quality
    return {
        "timing": timing,
        "quality_warning": timing.get('timing_degraded', False)
    }

except VideoTimingError as e:
    logger.error(f"Timing service error: {e}")
    # Fallback: Continue without timing
    return {
        "timing": None,
        "quality_warning": True,
        "error": str(e)
    }
```

### Verification Steps
1. Search for `start_video_timing` calls
2. Verify each call checks `timing_degraded` flag
3. Confirm VideoTimingError is caught
4. Test degraded mode with integration tests

---

## Category 3: VideoTimingError Exception Handling

### Problem
Only 1 file properly catches VideoTimingError. Need to add exception handling everywhere timing service is used.

### Files Requiring Updates (3 files already implement it, need 43 more)

#### Already Implementing (Reference Examples)
1. `/home/rigade/Testing/ai-model-validation-platform/backend/routes/video_timing.py`
   - Line: 186
   - **Status**: ✅ GOOD EXAMPLE

2. `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_timing_service.py`
   - Lines: 181, 186, 189, 238, 264, 269
   - **Status**: ✅ SOURCE OF EXCEPTION

3. `/home/rigade/Testing/ai-model-validation-platform/backend/tests/test_video_timing_service.py`
   - Lines: 538, 540
   - **Status**: ✅ TEST COVERAGE

#### Need Implementation (43 files)
All files from Category 2 that call `start_video_timing` but don't catch VideoTimingError.

### Update Template

```python
from services.video_timing_service import VideoTimingService, VideoTimingError

# BEFORE (No exception handling)
timing = video_timing_service.start_video_timing(session_id, video_id)

# AFTER (Proper exception handling)
try:
    timing = video_timing_service.start_video_timing(session_id, video_id)

    # Check degradation
    if timing.get('timing_degraded'):
        logger.warning("Operating with degraded timing")

except VideoTimingError as e:
    # Handle timing failure gracefully
    logger.error(f"Video timing error: {e}")

    # Option 1: Continue without timing
    timing = None

    # Option 2: Mark session as degraded
    session.timing_quality_degraded = True
    db.commit()

    # Option 3: Return error to client
    raise HTTPException(
        status_code=500,
        detail=f"Timing service unavailable: {str(e)}"
    )
```

### Verification Steps
1. Search for `start_video_timing` without try/except
2. Add VideoTimingError imports
3. Wrap calls in try/except blocks
4. Test exception handling with simulated failures

---

## Category 4: Database Connection Management

### Problem
202 files use `SessionLocal()` without proper cleanup, causing connection leaks.

### Files Requiring Updates (202 files)

This affects nearly ALL files that interact with the database. High-volume files include:

#### High Priority (Most Queries)
1. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions.py`
2. `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
3. `/home/rigade/Testing/ai-model-validation-platform/backend/routers/hil_testing.py`
4. `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`
5. `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_pipeline_service.py`

#### Medium Priority (Moderate Usage)
6-50. Various routers and services

#### Low Priority (Scripts and Tests)
51-202. Maintenance scripts and test files

### Update Template

```python
# BEFORE (Connection leak)
from database import SessionLocal

def process_data(session_id: str):
    db = SessionLocal()
    result = db.query(TestSession).filter_by(id=session_id).first()
    # db.close() often forgotten!
    return result

# AFTER (Proper context manager)
from utils.db_utils import managed_db_session

def process_data(session_id: str):
    with managed_db_session() as db:
        result = db.query(TestSession).filter_by(id=session_id).first()
        return result
    # Automatically closed and cleaned up

# OR (For FastAPI dependency injection)
from fastapi import Depends
from database import get_db

@router.get("/data/{session_id}")
def get_data(session_id: str, db: Session = Depends(get_db)):
    result = db.query(TestSession).filter_by(id=session_id).first()
    return result
    # FastAPI handles cleanup
```

### Required Utility

Create `/home/rigade/Testing/ai-model-validation-platform/backend/utils/db_utils.py`:

```python
from contextlib import contextmanager
from database import SessionLocal
import logging

logger = logging.getLogger(__name__)

@contextmanager
def managed_db_session():
    """
    Context manager for database sessions with automatic cleanup.

    Usage:
        with managed_db_session() as db:
            result = db.query(Model).all()
            return result
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error, rolling back: {e}")
        raise
    finally:
        db.close()
```

### Verification Steps
1. Search for `SessionLocal()` direct instantiation
2. Replace with `managed_db_session()` or `Depends(get_db)`
3. Remove manual `db.close()` calls
4. Test connection pooling under load

---

## Priority Matrix

### Phase 1: Critical Updates (Week 1)
1. **Category 1**: Update core routers (routers/hil_testing.py, routers/test_sessions.py, main.py)
2. **Category 3**: Add VideoTimingError handling to services
3. **Category 4**: Create db_utils.py utility

### Phase 2: Service Layer (Week 2)
1. **Category 1**: Update all services with DetectionEvent queries
2. **Category 2**: Add timing degradation checks to services
3. **Category 4**: Update services to use managed_db_session

### Phase 3: Test & Script Updates (Week 3)
1. **Category 1**: Update test files
2. **Category 2**: Add degraded timing tests
3. **Category 4**: Update maintenance scripts

### Phase 4: Verification (Week 4)
1. Run automated verification script
2. Integration testing
3. Performance testing
4. Documentation updates

---

## Automation Support

### Automated Migration Script
See: `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/update_codebase.py`

### Verification Script
See: `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/verify_updates.py`

---

## Breaking Changes

### ⚠️ API Response Changes
- All endpoints returning DetectionEvent data will now filter by quality
- Clients may see fewer detection events (only usable ones)
- **Migration**: Clients should not rely on exact detection counts

### ⚠️ Timing Behavior Changes
- Sessions may report `timing_degraded: true`
- Clients should handle degraded timing gracefully
- **Migration**: Update frontend to display timing quality warnings

### ⚠️ Database Connection Changes
- Connection pooling behavior may change
- Scripts need to use context managers
- **Migration**: Update all direct SessionLocal() usage

---

## Success Criteria

### Must Have
- ✅ All DetectionEvent queries filter by usable_for_validation
- ✅ All start_video_timing calls handle VideoTimingError
- ✅ All SessionLocal() replaced with managed contexts
- ✅ All tests pass
- ✅ No connection leaks under load

### Should Have
- ✅ Timing degradation properly logged
- ✅ API responses include quality metadata
- ✅ Frontend displays quality warnings

### Nice to Have
- ✅ Automated quality monitoring
- ✅ Quality metrics dashboard
- ✅ Historical quality trends

---

## Contact & Support

**Lead**: Agent 6 (Quality & Exception Handling Specialist)
**Review**: Integration Lead
**Approval**: Architecture Team

---

*Last Updated: 2025-11-19*
*Version: 1.0*
*Status: IN PROGRESS*
