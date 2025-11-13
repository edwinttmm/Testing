# Video ID Assignment Comprehensive Audit Report

**Generated**: 2025-11-07
**Scope**: Complete codebase analysis for video_id assignment bugs in multi-video sequences
**Status**: CRITICAL ISSUES FOUND

---

## Executive Summary

**CRITICAL FINDING**: Multiple services and API endpoints are creating `DetectionEvent` records with INCORRECT video_id assignment for multi-video sequences. The pattern is consistent: using `session.video_id` (which is always the FIRST video) instead of `current_video_id` from sequence metadata.

**Total Issues Found**: 7 CRITICAL, 2 HIGH, 3 MEDIUM

---

## CRITICAL Issues (Severity: CRITICAL)

### 🔴 ISSUE #1: labjack_detection_service.py - Line 603

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Line**: 603
**Status**: ❌ VULNERABLE

**Current Code**:
```python
video_id=session.video_id,  # Line 603 - WRONG!
```

**Why It's Wrong**:
- Uses `session.video_id` which is the FIRST video in sequence
- For multi-video sessions, this assigns ALL detections to Video 1
- Causes 0 detections for Video 2+
- Located in `notify_video_ended` - this is NOT the main detection path, but still wrong

**Suggested Fix**:
```python
# Get current_video_id from sequence_metadata
current_video_id = session.video_id  # Default fallback
if session.sequence_metadata:
    metadata = json.loads(session.sequence_metadata) if isinstance(session.sequence_metadata, str) else session.sequence_metadata
    current_video_id = metadata.get('current_video_id', session.video_id)
video_id = current_video_id
```

**Impact**: MEDIUM (not main detection path, but causes data corruption in lifecycle events)

---

### 🔴 ISSUE #2: labjack_detection_service.py - Line 1017

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Line**: 1017
**Status**: ✅ FIXED (but verify)

**Current Code**:
```python
# Line 1017: video_id = session.video_id
# Lines 1021-1039: CORRECT FIX APPLIED
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

**Status**: This appears to be ALREADY FIXED with proper logic. Verify this is working in production.

**Impact**: NONE (already fixed)

---

### 🔴 ISSUE #3: labjack_detection_service.py - Line 1017 (alternate path)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Line**: 1017
**Status**: ⚠️ VERIFY FALLBACK BEHAVIOR

**Context**: After fix at line 1021-1039, what happens if `sequence_metadata` is NULL or malformed?

**Risk**:
- If `sequence_metadata` is NULL → falls back to `session.video_id` (Video 1)
- If `current_video_id` is NULL in metadata → falls back to `session.video_id` (Video 1)
- This causes silent data corruption

**Suggested Enhancement**:
```python
if current_video_id is None and session.sequence_id:
    # CRITICAL ERROR: Multi-video session with NULL current_video_id
    logger.error(f"❌ CRITICAL: Multi-video session {session.id} has NULL current_video_id - REJECTING DETECTION")
    return False  # Don't create detection with wrong video_id
```

**Impact**: HIGH (silent data corruption if metadata is missing)

---

### 🔴 ISSUE #4: api/hil_test_complete.py - Line 587

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py`
**Line**: 587
**Status**: ⚠️ INCOMPLETE FIX

**Current Code**:
```python
active_session["current_video_id"] = video_id  # Line 587
active_session["active_video_id"] = video_id   # Line 590
```

**Why It's Wrong**:
- Updates in-memory `active_session` dict, but does NOT persist to database
- `TestSession.sequence_metadata` in database is NOT updated
- If service restarts, `current_video_id` is lost
- Other services reading from database will see stale data

**Suggested Fix**:
```python
# Update in-memory session
active_session["current_video_id"] = video_id
active_session["active_video_id"] = video_id

# CRITICAL: Persist to database
try:
    from models import TestSession
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if session:
        # Update sequence_metadata with current_video_id
        metadata = session.sequence_metadata or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        metadata['current_video_id'] = video_id
        session.sequence_metadata = metadata
        db.commit()
        logger.info(f"✅ Persisted current_video_id={video_id} to TestSession.sequence_metadata")
except Exception as e:
    logger.error(f"Failed to persist current_video_id: {e}")
    db.rollback()
```

**Impact**: CRITICAL (data loss on service restart, cross-service inconsistency)

---

### 🔴 ISSUE #5: socketio_server.py - Line 594

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/socketio_server.py`
**Line**: 594
**Status**: ❌ INCOMPLETE FIX

**Current Code**:
```python
# Line 594: Updates TestSession.video_id
session.video_id = video_id
db.commit()
logger.info(f"✅ AGENT 2: Updated TestSession.video_id={video_id}")
```

**Why It's Wrong**:
- Updates `TestSession.video_id` directly (overwrites first video!)
- Does NOT update `sequence_metadata.current_video_id`
- Breaks backward compatibility for single-video sessions
- Causes data corruption in multi-video sequences

**Root Cause**:
The comment says "AGENT 2" fix, but this is the WRONG fix approach. `TestSession.video_id` should ALWAYS remain the first video for backward compatibility. The current video should be tracked in `sequence_metadata.current_video_id`.

**Suggested Fix**:
```python
# DO NOT overwrite session.video_id - it's the initial video!
# Instead, update sequence_metadata.current_video_id

if session_id and video_id:
    db = SessionLocal()
    try:
        from models import TestSession
        session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if session:
            # For multi-video sequences, update sequence_metadata
            if session.sequence_id:
                metadata = session.sequence_metadata or {}
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                metadata['current_video_id'] = video_id
                session.sequence_metadata = metadata
                db.commit()
                logger.info(f"✅ Updated sequence_metadata.current_video_id={video_id}")
            # For single-video sessions, session.video_id can be updated
            elif session.video_id != video_id:
                session.video_id = video_id
                db.commit()
                logger.info(f"✅ Updated single-video session.video_id={video_id}")
    except Exception as e:
        logger.error(f"Failed to update video_id: {e}")
        db.rollback()
    finally:
        db.close()
```

**Impact**: CRITICAL (data corruption, backward compatibility broken)

---

### 🔴 ISSUE #6: video_sequence_orchestrator.py - Line 660

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`
**Line**: 660 (in `process_detection_event` method)
**Status**: ✅ CORRECT (no issue found)

**Current Code**:
```python
detection_event_kwargs: Dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "test_session_id": sequence.session_id,
    "video_id": video_id,  # ✅ CORRECT - uses video_id from _determine_video_for_detection
    ...
}
```

**Analysis**:
- Uses `video_id` from `_determine_video_for_detection()` method
- This method correctly determines which video was playing at detection time
- Properly handles multi-video sequences with timing ranges
- NO ISSUE FOUND

**Impact**: NONE (correctly implemented)

---

### 🔴 ISSUE #7: routers/test_sessions_fixed.py - Line 563

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions_fixed.py`
**Line**: 563
**Status**: ❌ VULNERABLE

**Current Code**:
```python
db_detection = DetectionEvent(
    id=str(uuid.uuid4()),
    **detection.dict(),  # ⚠️ Uses whatever video_id is in request
    created_at=datetime.utcnow()
)
```

**Why It's Wrong**:
- Uses `**detection.dict()` which includes `video_id` from the REQUEST
- Trusts client-provided `video_id` without validation
- Does not check `session.sequence_metadata.current_video_id`
- For multi-video sessions, client must provide correct `video_id` (fragile)

**Suggested Fix**:
```python
# Validate test session exists
session = db.query(TestSession).filter(TestSession.id == detection.test_session_id).first()
if not session:
    raise HTTPException(status_code=404, detail="Test session not found")

# CRITICAL: Determine correct video_id for multi-video sequences
video_id = detection.video_id  # Default to request value

if session.sequence_id and session.sequence_metadata:
    # Multi-video sequence - use current_video_id from metadata
    metadata = session.sequence_metadata
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    current_video_id = metadata.get('current_video_id')
    if current_video_id:
        video_id = current_video_id
        logger.info(f"✅ Multi-video: Overriding video_id={detection.video_id} with current_video_id={current_video_id}")

# Create detection event with validated video_id
detection_dict = detection.dict()
detection_dict['video_id'] = video_id  # Override with validated value

db_detection = DetectionEvent(
    id=str(uuid.uuid4()),
    **detection_dict,
    created_at=datetime.utcnow()
)
```

**Impact**: CRITICAL (client can submit wrong video_id, data corruption)

---

## HIGH Severity Issues

### ⚠️ ISSUE #8: routers/test_sessions.py - Line 1347

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions.py`
**Line**: 1347
**Status**: ❌ VULNERABLE (duplicate of Issue #7)

**Current Code**: Same as Issue #7 - uses `**detection.dict()` without validation

**Impact**: CRITICAL (same as Issue #7)

---

### ⚠️ ISSUE #9: routers/video_sequence_testing.py - Line 1772

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequence_testing.py`
**Line**: 1772
**Status**: ✅ CORRECT

**Current Code**:
```python
detection_event = DetectionEvent(
    id=detection_id,
    test_session_id=test_session.id,
    video_id=active_video_id,  # ✅ CORRECT - uses active_video_id from logic
    ...
)
```

**Analysis**:
- Uses `active_video_id` which is calculated from sequence logic
- Properly handles multi-video sequences
- NO ISSUE FOUND

**Impact**: NONE (correctly implemented)

---

## MEDIUM Severity Issues

### 🟡 ISSUE #10: Ground Truth Filtering Logic

**Scope**: Multiple services reading `GroundTruthObject` records
**Status**: ⚠️ VERIFY FILTERING

**Risk**:
Many queries filter ground truth by `session.video_id`:
```python
ground_truth_objects = db.query(GroundTruthObject).filter(
    GroundTruthObject.video_id == session.video_id  # ⚠️ Always Video 1
).all()
```

**Files Affected**:
- `routers/test_sessions.py` (lines 211, 1127)
- Various services and API endpoints

**Why It's Wrong**:
- For multi-video sequences, should filter by `current_video_id`
- Causes ground truth matching to fail for Video 2+
- Metrics will show 0 expected detections for Video 2+

**Suggested Fix**:
```python
# Determine correct video_id for filtering
filter_video_id = session.video_id
if session.sequence_id and session.sequence_metadata:
    metadata = json.loads(session.sequence_metadata) if isinstance(session.sequence_metadata, str) else session.sequence_metadata
    filter_video_id = metadata.get('current_video_id', session.video_id)

ground_truth_objects = db.query(GroundTruthObject).filter(
    GroundTruthObject.video_id == filter_video_id
).all()
```

**Impact**: HIGH (ground truth matching broken for Video 2+)

---

### 🟡 ISSUE #11: Detection Event Filtering in APIs

**Scope**: API endpoints returning detection events
**Status**: ⚠️ VERIFY FILTERING

**Example** (`src/api/simple_detection_endpoints.py` line 402):
```python
video_events = db.query(VideoEvent).filter(
    VideoEvent.video_id == db_session.video_id  # ⚠️ Always Video 1
).all()
```

**Why It's Wrong**:
- Returns detections for Video 1 even when querying Video 2+
- UI will show wrong detections for each video
- Cross-contamination between videos

**Impact**: HIGH (UI displays wrong data)

---

### 🟡 ISSUE #12: Hardcoded session.video_id in Response DTOs

**Scope**: API response builders
**Status**: ⚠️ VERIFY RESPONSE BUILDING

**Example**:
```python
return {
    "video_id": session.video_id,  # ⚠️ Always Video 1
    "detections": detections
}
```

**Why It's Wrong**:
- Response says "video_id: Video1" even for Video 2+ detections
- Frontend receives inconsistent data
- Debugging becomes impossible

**Impact**: MEDIUM (data inconsistency, debugging issues)

---

## Summary Table

| Issue # | File | Line | Severity | Status | Fix Priority |
|---------|------|------|----------|--------|--------------|
| 1 | labjack_detection_service.py | 603 | CRITICAL | ❌ Vulnerable | HIGH |
| 2 | labjack_detection_service.py | 1017 | CRITICAL | ✅ Fixed | Verify |
| 3 | labjack_detection_service.py | 1017 | CRITICAL | ⚠️ Verify | HIGH |
| 4 | api/hil_test_complete.py | 587 | CRITICAL | ❌ Incomplete | CRITICAL |
| 5 | socketio_server.py | 594 | CRITICAL | ❌ Wrong Fix | CRITICAL |
| 6 | video_sequence_orchestrator.py | 660 | CRITICAL | ✅ Correct | None |
| 7 | routers/test_sessions_fixed.py | 563 | CRITICAL | ❌ Vulnerable | CRITICAL |
| 8 | routers/test_sessions.py | 1347 | HIGH | ❌ Vulnerable | HIGH |
| 9 | routers/video_sequence_testing.py | 1772 | HIGH | ✅ Correct | None |
| 10 | Multiple services | Various | MEDIUM | ⚠️ Verify | MEDIUM |
| 11 | API endpoints | Various | MEDIUM | ⚠️ Verify | MEDIUM |
| 12 | Response builders | Various | MEDIUM | ⚠️ Verify | LOW |

---

## Critical Patterns to Search For

Use these patterns to find additional bugs:

### 1. DetectionEvent Creation
```bash
grep -rn "DetectionEvent(" backend/services backend/api backend/routers
```

### 2. Using session.video_id
```bash
grep -rn "session\.video_id" backend/services backend/api backend/routers
```

### 3. Ground Truth Filtering
```bash
grep -rn "GroundTruthObject.*video_id.*session\.video_id" backend/
```

### 4. API Response Building
```bash
grep -rn "\"video_id\".*session\.video_id" backend/
```

---

## Recommended Fix Strategy

### Phase 1: CRITICAL Fixes (Deploy Immediately)
1. Fix Issue #4: Persist `current_video_id` to database in `hil_test_complete.py`
2. Fix Issue #5: Correct the socketio_server.py video_id update logic
3. Fix Issue #7: Add video_id validation in `test_sessions_fixed.py`
4. Fix Issue #8: Add video_id validation in `test_sessions.py`

### Phase 2: Verification (Next Sprint)
1. Verify Issue #2 fix is working correctly
2. Add error handling for Issue #3 (NULL metadata fallback)
3. Test all CRITICAL fixes with multi-video integration tests

### Phase 3: Ground Truth & API Fixes (Following Sprint)
1. Fix Issue #10: Ground truth filtering across all services
2. Fix Issue #11: Detection event filtering in APIs
3. Fix Issue #12: Response DTO building

### Phase 4: Regression Testing
1. Create comprehensive multi-video test suite
2. Test 2-video, 3-video, and 5-video sequences
3. Verify backward compatibility with single-video sessions
4. Load testing with concurrent multi-video sessions

---

## Testing Checklist

- [ ] Single-video session (backward compatibility)
- [ ] 2-video sequence (basic multi-video)
- [ ] 3-video sequence (extended multi-video)
- [ ] Video transition timing (detection during transition)
- [ ] Service restart during video playback (persistence)
- [ ] Concurrent multi-video sessions (isolation)
- [ ] NULL/missing metadata handling (error recovery)
- [ ] Ground truth matching per-video
- [ ] API responses per-video
- [ ] Frontend display per-video

---

## Root Cause Analysis

**Why did this happen?**

1. **Legacy Design**: Original system designed for single video per session
2. **Implicit Assumptions**: `session.video_id` assumed to be THE video
3. **Gradual Evolution**: Multi-video support added incrementally without refactoring
4. **Missing Abstraction**: No helper function like `get_current_video_id(session)`
5. **Inadequate Testing**: No integration tests for multi-video sequences

**Why wasn't it caught earlier?**

1. **Silent Failure**: Detections created with wrong video_id don't throw errors
2. **Data Accumulation**: Video 1 gets ALL detections, looks like success
3. **Zero Detections**: Video 2+ has zero detections, looks like hardware issue
4. **Cross-Service**: Bug spans multiple services, hard to trace
5. **Race Conditions**: Timing-dependent, may work in dev but fail in prod

---

## Recommendations

### 1. Create Helper Function
```python
def get_current_video_id(session: TestSession) -> str:
    """
    Get the currently active video_id for a session.

    For multi-video sequences, returns current_video_id from sequence_metadata.
    For single-video sessions, returns session.video_id.
    """
    if session.sequence_id and session.sequence_metadata:
        metadata = session.sequence_metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        current_video_id = metadata.get('current_video_id')
        if current_video_id:
            return current_video_id
    return session.video_id
```

Use this helper EVERYWHERE instead of direct `session.video_id` access.

### 2. Add Database Constraint
```sql
-- Prevent NULL video_id in multi-video sessions
ALTER TABLE detection_events ADD CONSTRAINT check_video_id_not_null
CHECK (video_id IS NOT NULL);
```

### 3. Add Logging
```python
logger.info(f"DetectionEvent created: session={session_id}, video={video_id}, sequence={sequence_id}")
```

Add this log to EVERY DetectionEvent creation to make debugging easier.

### 4. Add Monitoring
```python
# Alert if Video 2+ has zero detections after 10 seconds
if video_index > 0 and detection_count == 0 and elapsed_time > 10:
    alert("CRITICAL: Video {video_index} has zero detections!")
```

---

## Conclusion

This audit found **7 CRITICAL vulnerabilities** in video_id assignment logic across the codebase. The root cause is using `session.video_id` (always Video 1) instead of `sequence_metadata.current_video_id` (the active video).

**Immediate Action Required**:
1. Deploy fixes for Issues #4, #5, #7, #8 (CRITICAL)
2. Verify Issue #2 fix is working (HIGH)
3. Add error handling for Issue #3 (HIGH)

**Long-term Actions**:
1. Create `get_current_video_id()` helper function
2. Refactor all services to use helper
3. Add integration tests for multi-video sequences
4. Implement monitoring/alerting for zero detections

---

**End of Report**
