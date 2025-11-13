# Video Tracking Architecture - Quick Reference Card

**Last Updated:** 2025-11-07
**Status:** Architecture Proposal
**Related Docs:**
- Full ADR: `/docs/VIDEO_TRACKING_ARCHITECTURE_REDESIGN.md`
- Diagrams: `/docs/VIDEO_TRACKING_ARCHITECTURE_DIAGRAM.txt`

---

## Problem Summary

**Current Bug:** When `sequence_metadata.current_video_id` isn't updated during video transitions, ALL detections get assigned to the wrong video.

**Example:**
```
Video A ends → Video B starts → metadata update FAILS →
All Video B detections wrongly assigned to Video A
```

**Impact:** Test results are completely invalid, compliance risk for HIL validation.

---

## Solution: Timestamp-Based Assignment

**Core Principle:** Don't trust mutable metadata. Compute video_id from immutable timing boundaries.

```python
# BEFORE (Vulnerable):
video_id = session.sequence_metadata.get('current_video_id')  # ❌ Can be stale

# AFTER (Robust):
assignment = video_assignment_service.get_video_for_timestamp(
    session_id, detection_timestamp, db
)
video_id = assignment.video_id  # ✅ Computed from database timing
```

---

## Key Components

### 1. VideoAssignmentService (New)

**Purpose:** Determine correct video_id from detection timestamp

**Location:** `/backend/services/video_assignment_service.py`

**Main Method:**
```python
def get_video_for_timestamp(
    session_id: str,
    detection_timestamp: float,
    db: Session
) -> VideoAssignment:
    """
    Query SequenceVideoResult table to find video where:
        video_start_time <= detection_timestamp < video_end_time

    Returns VideoAssignment with:
        - video_id: Computed video ID
        - confidence: 0.0 to 1.0
        - method: "timestamp_query", "fallback", etc.
        - is_valid: Whether assignment succeeded
        - validation_warnings: List of issues found
    """
```

**Algorithm:**
1. Query `SequenceVideoResult` for videos in sequence
2. Find video with matching time range (with grace period)
3. Cross-validate with metadata (if available)
4. Return assignment with confidence metrics

### 2. Updated Detection Storage

**Location:** `/backend/services/labjack_detection_service.py`

**Changes:**
```python
async def _store_event_in_db(self, event: DetectionEvent):
    # NEW: Use assignment service instead of metadata
    assignment = video_assignment_service.get_video_for_timestamp(
        event.session_id, event.timestamp, db
    )

    if not assignment.is_valid:
        logger.error("Invalid video assignment!")
        return False  # Reject detection

    video_id = assignment.video_id

    # NEW: Cross-validate with metadata
    if metadata_video_id != video_id:
        logger.error("🚨 METADATA DRIFT DETECTED")
        metrics.record_mismatch()

    # NEW: Store assignment metadata for auditing
    db_event.detection_metadata['video_assignment'] = {
        'method': assignment.method,
        'confidence': assignment.confidence,
        'warnings': assignment.validation_warnings
    }
```

### 3. Database Schema (Existing)

**Single Source of Truth:** `SequenceVideoResult` table

```sql
-- Already exists! No schema changes needed.
CREATE TABLE sequence_video_results (
    id VARCHAR(36) PRIMARY KEY,
    video_sequence_id VARCHAR(36),
    video_id VARCHAR(36),
    sequence_order INTEGER,

    -- These are our immutable timing boundaries
    video_start_time FLOAT,  -- Unix epoch when video started
    video_end_time FLOAT,    -- Unix epoch when video ended (NULL if current)

    INDEX (video_sequence_id, video_start_time, video_end_time)
);
```

---

## Migration Phases

### Phase 1: Parallel Validation (Week 1-2)
- Both methods run, no behavior change
- Timestamp-based logs warnings only
- Collect mismatch statistics
- **Action:** Monitor dashboards, verify <1% mismatch rate

### Phase 2: Timestamp Primary (Week 3)
- Use timestamp result for video_id
- Validate against metadata
- Alert on mismatches
- **Action:** Respond to metadata drift alerts, fix upstream bugs

### Phase 3: Timestamp Only (Week 4)
- Remove metadata-based assignment
- Stop updating `current_video_id`
- Clean up legacy code
- **Action:** Verify metrics, update documentation

---

## Monitoring

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| `video_assignment.confidence` p50 | >0.95 | <0.95 for >1% detections |
| `video_assignment.mismatch_rate` | <0.1% | >1% for 5 min |
| `video_assignment.query_latency_ms` p99 | <5ms | >10ms for 10 min |
| `detection.wrong_video_rate` | 0% | >0.1% for 5 min |

### Dashboards

1. **Video Assignment Dashboard** - Assignment confidence, mismatch rate, query latency
2. **Detection Quality Dashboard** - Detections per video, rejection rate

### Alerts

**Critical (Page On-Call):**
- Metadata mismatch rate >5/min for 5 min
- Invalid assignment rate >10/min for 5 min

**Warning (Slack):**
- Query latency p99 >10ms for 10 min
- Cache hit rate <80% for 30 min

---

## Testing Checklist

### Unit Tests
- ✅ Single video detection
- ✅ Multi-video detection
- ✅ Video transition boundary (grace period)
- ✅ Metadata drift detection
- ✅ NULL end_time handling

### Integration Tests
- ✅ Database query performance
- ✅ Concurrent detection assignment
- ✅ Cross-validation logic

### E2E Tests
- ✅ Full video sequence with detections
- ✅ Video transition during active detection
- ✅ Metadata drift scenario

---

## Common Scenarios

### Scenario 1: Normal Operation
```
Detection at t=15.0s in 2-video sequence
→ Query: start_time <= 15.0 AND end_time > 15.0
→ Result: video_id="bbb", confidence=1.0 ✅
→ Metadata check: Matches ✅
→ Store with video_id="bbb"
```

### Scenario 2: Metadata Drift (Bug Prevented!)
```
Detection at t=15.0s in 2-video sequence
→ Query: start_time <= 15.0 AND end_time > 15.0
→ Result: video_id="bbb", confidence=1.0 ✅
→ Metadata check: metadata says "aaa" ❌ MISMATCH
→ Log error + alert + metric
→ Store with video_id="bbb" (trust timestamp) ✅
```

### Scenario 3: Boundary Detection
```
Detection at t=12.05s (Video A→B transition at t=12.0s)
→ Query with grace period (±100ms)
→ Result: video_id="bbb", confidence=0.95 ✅
→ Warning: "Near transition boundary"
→ Store with video_id="bbb"
```

### Scenario 4: Database Query Failure
```
Detection at t=15.0s
→ Query fails (database unavailable)
→ Result: video_id=None, confidence=0.0, is_valid=False ❌
→ Fallback: Use session.video_id with warning
→ Log error + alert
→ Store with fallback video_id + reduced confidence
```

---

## API Usage Examples

### For Detection Storage
```python
from services.video_assignment_service import get_video_assignment_service

# In detection storage code:
assignment_service = get_video_assignment_service()

assignment = assignment_service.get_video_for_timestamp(
    session_id="session_123",
    detection_timestamp=15.0,
    db=db_session
)

if not assignment.is_valid:
    logger.error(f"Assignment failed: {assignment.validation_warnings}")
    # Handle error: reject or use fallback

video_id = assignment.video_id
confidence = assignment.confidence

# Store detection
detection.video_id = video_id
detection.detection_metadata['assignment'] = {
    'method': assignment.method,
    'confidence': confidence,
    'warnings': assignment.validation_warnings
}
```

### For Validation
```python
# Validate an existing video_id assignment
is_valid = assignment_service.validate_video_assignment(
    video_id="video_bbb",
    detection_timestamp=15.0,
    session_id="session_123",
    db=db_session
)

if not is_valid:
    logger.error("Video ID validation failed!")
```

---

## Troubleshooting

### Problem: High Mismatch Rate
**Symptoms:** `video_assignment.mismatch_rate` >1%
**Diagnosis:** Metadata update logic broken upstream
**Fix:**
1. Check orchestrator's `notify_video_started()` logs
2. Verify `SequenceVideoResult` records created correctly
3. Fix metadata update logic if needed

**Workaround:** System continues working (uses timestamp, not metadata)

### Problem: Invalid Assignments
**Symptoms:** `detection.rejected_invalid_video` >5/min
**Diagnosis:** Video timing records missing or incorrect
**Fix:**
1. Check `SequenceVideoResult` for NULL `video_start_time`
2. Verify orchestrator creates timing records atomically
3. Check database constraints

### Problem: Slow Queries
**Symptoms:** `video_assignment.query_latency_ms` p99 >10ms
**Diagnosis:** Missing or inefficient database index
**Fix:**
1. Check index exists: `SHOW INDEX FROM sequence_video_results`
2. Run `EXPLAIN` on query
3. Rebuild index if needed

---

## Rollback Procedure

If critical bug found in new system:

### Quick Rollback (5 minutes)
```bash
# Disable timestamp-based assignment via feature flag
kubectl set env deployment/backend VIDEO_ASSIGNMENT_METHOD=metadata

# Restart
kubectl rollout restart deployment/backend

# Verify
curl https://api/health/video-assignment
```

### Phase-Specific Rollback
- **Phase 1 → Production:** Just disable logging (no behavior change)
- **Phase 2 → Phase 1:** Flip flag to `VIDEO_ASSIGNMENT_METHOD=metadata`
- **Phase 3 → Phase 2:** Re-enable metadata updates, restore validation

---

## Decision Tree: Which Method To Use?

```
Does session have sequence_id?
    │
    ├─ YES → Multi-video sequence
    │   │
    │   └─ Use VideoAssignmentService.get_video_for_timestamp()
    │       Query SequenceVideoResult by timestamp
    │       Cross-validate with metadata
    │       Return with confidence metrics
    │
    └─ NO → Single-video session
        │
        └─ Use session.video_id directly
            Validate against session.video_start_timestamp
            Return with confidence=1.0
```

---

## Code Review Checklist

When reviewing code that assigns video_id:

- [ ] Uses `VideoAssignmentService` instead of reading metadata directly
- [ ] Checks `assignment.is_valid` before using `video_id`
- [ ] Stores assignment metadata (`confidence`, `method`, `warnings`)
- [ ] Logs warnings for low confidence (<0.95)
- [ ] Emits metrics for monitoring
- [ ] Has tests for edge cases (boundaries, failures)

---

## Performance Targets

| Operation | Target | Max |
|-----------|--------|-----|
| `get_video_for_timestamp()` query | <5ms | <10ms |
| Detection storage with assignment | <20ms | <50ms |
| Cross-validation check | <1ms | <5ms |
| Database index scan | <1ms | <2ms |

---

## Related Issues

- **Issue #X:** Detections assigned to wrong video in multi-video sequences
- **Issue #Y:** Metadata synchronization race conditions
- **Issue #Z:** Video transition boundary handling

---

## Contact

**Architecture Owner:** System Architecture Team
**Implementation Lead:** Backend Team
**Questions:** #video-tracking-architecture Slack channel

---

## Quick Commands

```bash
# Check assignment service status
curl https://api/health/video-assignment

# Get metrics
curl https://api/metrics | grep video_assignment

# View recent mismatches
curl https://api/admin/video-assignment/mismatches?limit=10

# Toggle feature flag
kubectl set env deployment/backend VIDEO_ASSIGNMENT_METHOD=timestamp

# View service logs
kubectl logs -l app=backend --tail=100 | grep VideoAssignment
```
