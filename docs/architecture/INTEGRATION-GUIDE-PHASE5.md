# Integration Guide: Unified Video Assignment Service

**Target Audience**: Backend Engineers, DevOps, QA
**Prerequisites**: Understanding of ADR-005 and migration plan

---

## Overview

This guide provides step-by-step instructions for integrating the `VideoAssignmentService` into each component of the HIL validation system.

---

## Integration Point 1: LabJack Detection Service

**File**: `backend/services/labjack_detection_service.py`
**Line**: 1033 (current metadata extraction)
**Phase**: 5b (Week 2)

### Current Code (To Be Replaced)

```python
# Lines 1021-1047 - REMOVE THIS BLOCK
if session.sequence_id and session.sequence_metadata:
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
    except Exception as meta_error:
        logger.error(f"Failed to parse sequence_metadata: {meta_error}")
```

### New Code (Phase 5b)

```python
# Import at top of file
from services.video_assignment_service import get_video_assignment_service

# In _handle_detection_event method, around line 1033
# Replace metadata extraction with unified service call

# Get singleton service instance
assignment_service = get_video_assignment_service()

# Assign video_id using unified service
try:
    assignment = assignment_service.get_video_id_for_detection(
        session_id=session.id,
        detection_timestamp=timestamp,
        db=db
    )

    # Handle result based on confidence
    if assignment.confidence >= 0.8:
        # High confidence - use assigned video_id
        video_id = assignment.video_id
        logger.info(
            f"✅ Video assignment: video_id={video_id}, "
            f"confidence={assignment.confidence:.2f}, "
            f"method={assignment.method}"
        )

    elif assignment.confidence >= 0.5:
        # Medium confidence - use but log warning
        video_id = assignment.video_id
        logger.warning(
            f"⚠️ Medium confidence video assignment: "
            f"video_id={video_id}, "
            f"confidence={assignment.confidence:.2f}, "
            f"method={assignment.method}, "
            f"debug={assignment.debug_info}"
        )

    else:
        # Low confidence - fallback to session.video_id
        video_id = session.video_id if hasattr(session, 'video_id') else None
        logger.error(
            f"❌ Low confidence video assignment: "
            f"confidence={assignment.confidence:.2f}, "
            f"method={assignment.method}, "
            f"debug={assignment.debug_info}, "
            f"fallback_video_id={video_id}"
        )

except Exception as assignment_error:
    # Service failure - fallback to session.video_id
    video_id = session.video_id if hasattr(session, 'video_id') else None
    logger.error(
        f"❌ Video assignment service error: {assignment_error}, "
        f"fallback_video_id={video_id}",
        exc_info=True
    )

# Continue with existing validation logic...
if video_id:
    from models import Video
    video_exists = db.query(Video).filter(Video.id == video_id).first()
    if not video_exists:
        logger.warning(f"Video {video_id} not found, clearing video_id")
        video_id = None
```

### Testing

```bash
# Unit test
cd backend/tests
pytest test_labjack_detection_service.py::test_video_assignment_integration -v

# Integration test
pytest test_integration_ground_truth.py -v

# Manual validation
python3 scripts/verify_detection_accuracy.py --session-id <test_session>
```

---

## Integration Point 2: Video Sequence Orchestrator

**File**: `backend/services/video_sequence_orchestrator.py`
**Lines**: 445 (detection handling), 857-879 (method to remove)
**Phase**: 5c (Week 3)

### Step 1: Inject Service in `__init__`

```python
# At class initialization (around line 50)
from services.video_assignment_service import get_video_assignment_service

class VideoSequenceOrchestrator:
    def __init__(self):
        self._sequences: Dict[str, VideoTestSequence] = {}
        self.video_assignment_service = get_video_assignment_service()  # ADD THIS
```

### Step 2: Replace `_determine_video_for_detection` Call

```python
# In handle_detection_event method (around line 445)
# OLD CODE - REMOVE:
# video_id = self._determine_video_for_detection(sequence, sequence_timestamp)

# NEW CODE - ADD:
try:
    assignment = self.video_assignment_service.get_video_id_for_detection(
        session_id=sequence.session_id,
        detection_timestamp=sequence_timestamp,
        db=db
    )

    video_id = assignment.video_id

    if video_id is None or assignment.confidence < 0.5:
        logger.warning(
            f"Could not determine video at {sequence_timestamp:.6f}: "
            f"confidence={assignment.confidence}, "
            f"method={assignment.method}, "
            f"debug={assignment.debug_info}"
        )
        return None

    logger.debug(
        f"Orchestrator video assignment: "
        f"video_id={video_id}, "
        f"confidence={assignment.confidence}, "
        f"sequence_order={assignment.debug_info.get('sequence_order', 'N/A')}"
    )

except Exception as assignment_error:
    logger.error(
        f"Video assignment failed in orchestrator: {assignment_error}",
        exc_info=True
    )
    return None
```

### Step 3: Remove Old Method

```python
# DELETE method _determine_video_for_detection (lines 857-879)
# This entire method can be removed:
#
# def _determine_video_for_detection(
#     self,
#     sequence: VideoTestSequence,
#     detection_timestamp: float
# ) -> Optional[str]:
#     """Determine which video was playing at detection time"""
#     # ... 25 lines of code ...
#     return None
```

### Testing

```bash
# Unit test orchestrator
pytest test_video_sequence_orchestrator.py -v

# Multi-video timing tests
pytest test_multi_video_timing_accuracy.py -v

# Per-video metrics validation
pytest test_per_video_ground_truth_metrics.py -v

# End-to-end sequence test
python3 scripts/validate_video_sequence.py --session-id <multi_video_session>
```

---

## Integration Point 3: SocketIO Server (Cleanup Only)

**File**: `backend/socketio_server.py`
**Lines**: 583-603 (TestSession.video_id updates)
**Phase**: 5d (Week 4)

### Current Code (To Be Removed)

```python
# Lines 583-603 - REMOVE THIS BLOCK in Phase 5d
if session_id and video_id:
    db = SessionLocal()
    try:
        from models import TestSession

        session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if session:
            session.video_id = video_id
            db.commit()
            logger.info(f"✅ Updated TestSession.video_id={video_id}")
        else:
            logger.error(f"❌ TestSession {session_id} not found")
    except Exception as session_error:
        logger.error(f"❌ Failed to update TestSession.video_id: {session_error}")
        db.rollback()
    finally:
        db.close()
```

### New Code (Phase 5d)

```python
# Replace with simple logging (video_id assignment now handled by unified service)
logger.info(
    f"Video started event: session={session_id}, video={video_id} "
    f"(video_id assignment handled by VideoAssignmentService)"
)

# Keep video timing persistence (this is still needed)
# Lines 605-629 remain unchanged - they persist video_start_time
```

### Testing

```bash
# Test WebSocket events still work
pytest test_socketio_video_events.py -v

# Verify video timing persistence intact
pytest test_video_timing_persistence.py -v
```

---

## Integration Point 4: Ground Truth Matching Service (Optional Enhancement)

**File**: `backend/services/ground_truth_matching_service.py`
**Enhancement**: Use confidence scoring for match validation
**Phase**: 5c or 5d (Optional)

### Enhancement Code

```python
# In ground_truth_matching_service.py
# When matching detections to ground truth

from services.video_assignment_service import get_video_assignment_service

class GroundTruthMatchingService:
    def __init__(self):
        self.video_assignment_service = get_video_assignment_service()

    def match_detection_to_ground_truth(
        self,
        detection_event: DetectionEvent,
        db: Session
    ) -> Optional[GroundTruthObject]:
        """
        Match detection to ground truth with video_id validation.
        """
        # Validate video_id assignment confidence
        assignment = self.video_assignment_service.get_video_id_for_detection(
            session_id=detection_event.test_session_id,
            detection_timestamp=detection_event.timestamp,
            db=db
        )

        # Only match if video_id is high confidence
        if assignment.confidence < 0.8:
            logger.warning(
                f"Skipping ground truth matching - low video_id confidence: "
                f"detection={detection_event.id}, "
                f"confidence={assignment.confidence}"
            )
            return None

        # Verify detection's video_id matches assignment
        if detection_event.video_id != assignment.video_id:
            logger.error(
                f"Video ID mismatch detected: "
                f"detection.video_id={detection_event.video_id}, "
                f"assigned_video_id={assignment.video_id}, "
                f"confidence={assignment.confidence}"
            )
            # Optionally auto-correct video_id
            # detection_event.video_id = assignment.video_id
            # db.commit()

        # Continue with ground truth matching...
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == assignment.video_id,
            # ... rest of matching logic
        ).all()

        return self._find_best_match(detection_event, ground_truth_objects)
```

---

## Common Integration Patterns

### Pattern 1: High-Confidence Usage

```python
# Use this when you MUST have a valid video_id
assignment = service.get_video_id_for_detection(session_id, timestamp, db)

if assignment.confidence >= 0.8:
    video_id = assignment.video_id
    # Proceed with confidence
else:
    # Abort or use fallback
    raise ValueError(f"Cannot proceed with confidence {assignment.confidence}")
```

### Pattern 2: Graceful Degradation

```python
# Use this when you want to handle low confidence gracefully
assignment = service.get_video_id_for_detection(session_id, timestamp, db)

if assignment.confidence >= 0.5:
    video_id = assignment.video_id
    logger.warning(f"Using video_id with confidence {assignment.confidence}")
else:
    # Fallback to legacy method
    video_id = session.video_id
    logger.error(f"Falling back to session.video_id")
```

### Pattern 3: Validation and Logging

```python
# Use this for debugging and validation
assignment = service.get_video_id_for_detection(session_id, timestamp, db)

logger.info(
    f"Video assignment result: "
    f"video_id={assignment.video_id}, "
    f"confidence={assignment.confidence}, "
    f"method={assignment.method}, "
    f"debug_info={json.dumps(assignment.debug_info)}"
)

# Proceed based on confidence
if assignment.confidence > 0.5:
    video_id = assignment.video_id
```

---

## Error Handling Best Practices

### Handling Service Failures

```python
try:
    assignment = service.get_video_id_for_detection(session_id, timestamp, db)
    video_id = assignment.video_id

except Exception as e:
    # Log error with context
    logger.error(
        f"VideoAssignmentService failed: {e}, "
        f"session_id={session_id}, "
        f"timestamp={timestamp}",
        exc_info=True
    )

    # Fallback strategy
    video_id = self._get_fallback_video_id(session_id, db)

    # Emit alert for monitoring
    self._emit_service_failure_alert("VideoAssignmentService", session_id)
```

### Handling Low Confidence

```python
assignment = service.get_video_id_for_detection(session_id, timestamp, db)

if assignment.confidence < 0.5:
    # Log detailed debug info
    logger.error(
        f"Low confidence video assignment: "
        f"confidence={assignment.confidence}, "
        f"method={assignment.method}, "
        f"debug_info={assignment.debug_info}, "
        f"session_id={session_id}, "
        f"timestamp={timestamp}"
    )

    # Depending on context, either:
    # Option 1: Use fallback
    video_id = session.video_id

    # Option 2: Skip this detection
    return None

    # Option 3: Mark for manual review
    self._flag_for_manual_review(detection_id, assignment.debug_info)
```

---

## Cache Management

### Invalidating Cache on Video Transitions

```python
# In socketio_server.py - on video_started or video_ended events

from services.video_assignment_service import get_video_assignment_service

@socketio.on('video_ended')
def handle_video_ended(data):
    session_id = data.get('sessionId')
    video_id = data.get('videoId')

    # ... existing video timing persistence ...

    # Invalidate assignment cache for this session
    service = get_video_assignment_service()
    service.invalidate_session_cache(session_id)

    logger.info(f"Invalidated video assignment cache for session {session_id}")
```

### Monitoring Cache Performance

```python
# Add to monitoring/health check endpoint

from services.video_assignment_service import get_video_assignment_service

@app.get("/api/v1/health/video-assignment")
def video_assignment_health():
    service = get_video_assignment_service()
    stats = service.get_statistics()

    return {
        "status": "healthy",
        "cache_hit_rate": stats["cache_hit_rate"],
        "total_assignments": stats["total_assignments"],
        "assignment_methods": stats["assignment_methods"],
        "cache_hits": stats["cache_hits"],
        "cache_misses": stats["cache_misses"]
    }
```

---

## Testing Checklist

### Per Integration Point

- [ ] Unit tests pass for modified component
- [ ] Integration tests pass with real database
- [ ] Manual testing with multi-video test session
- [ ] Performance benchmarking (< 1ms overhead)
- [ ] Error handling validation
- [ ] Logging output reviewed
- [ ] Cache performance measured
- [ ] Rollback procedure tested

### System-Wide Tests

- [ ] End-to-end multi-video sequence test
- [ ] Ground truth matching accuracy validation
- [ ] Latency calculation correctness
- [ ] Per-video metrics accuracy
- [ ] Frontend display correctness
- [ ] Load testing (1000+ detections/second)
- [ ] Failure scenario testing
- [ ] Cache invalidation testing

---

## Monitoring and Alerts

### Key Metrics to Monitor

```python
# Grafana/Prometheus metrics to track

# Confidence distribution
video_assignment_confidence_histogram

# Assignment method usage
video_assignment_method_counter{method="timestamp_match"}
video_assignment_method_counter{method="grace_period"}
video_assignment_method_counter{method="failed"}

# Cache performance
video_assignment_cache_hit_rate
video_assignment_cache_size

# Latency
video_assignment_duration_seconds

# Errors
video_assignment_errors_total
video_assignment_low_confidence_total
```

### Alert Thresholds

```yaml
# alerts.yml
- alert: LowVideoAssignmentConfidence
  expr: rate(video_assignment_low_confidence_total[5m]) > 0.05
  annotations:
    summary: "High rate of low-confidence video assignments"

- alert: VideoAssignmentCacheDegraded
  expr: video_assignment_cache_hit_rate < 0.7
  annotations:
    summary: "Video assignment cache hit rate below 70%"

- alert: VideoAssignmentServiceErrors
  expr: rate(video_assignment_errors_total[5m]) > 0.01
  annotations:
    summary: "Video assignment service error rate elevated"
```

---

## Troubleshooting Guide

### Issue: Low Confidence Assignments

**Symptoms**: `assignment.confidence < 0.5` frequently

**Diagnosis**:
```sql
-- Check if video timing data is missing
SELECT
    svr.video_id,
    svr.video_start_time,
    svr.video_end_time,
    svr.video_status
FROM sequence_video_results svr
WHERE svr.video_sequence_id = '<sequence_id>'
ORDER BY svr.sequence_order;
```

**Solution**: Ensure video_start_time is persisted correctly in socketio_server.py

---

### Issue: Video ID Mismatches

**Symptoms**: Detection assigned to wrong video

**Diagnosis**:
```python
# Check assignment debug info
assignment = service.get_video_id_for_detection(session_id, timestamp, db)
print(f"Debug info: {assignment.debug_info}")

# Check timing boundaries
print(f"Start time: {assignment.debug_info.get('start_time')}")
print(f"End time: {assignment.debug_info.get('end_time')}")
print(f"Timestamp: {assignment.debug_info.get('timestamp')}")
```

**Solution**: Verify video timing boundaries are correctly calculated

---

### Issue: Cache Not Invalidating

**Symptoms**: Stale video_id assignments after video transitions

**Solution**:
```python
# Manually clear cache
from services.video_assignment_service import get_video_assignment_service
service = get_video_assignment_service()
service.clear_cache()
```

---

## Summary

This integration guide provides:
1. ✅ Step-by-step code changes for each component
2. ✅ Testing procedures for validation
3. ✅ Error handling best practices
4. ✅ Cache management strategies
5. ✅ Monitoring and alerting setup
6. ✅ Troubleshooting procedures

Follow this guide during Phase 5b-5d migration to ensure safe, successful integration of the unified VideoAssignmentService.

---

**Last Updated**: 2025-11-07
**Document Version**: 1.0
**Maintainer**: Backend Engineering Team
