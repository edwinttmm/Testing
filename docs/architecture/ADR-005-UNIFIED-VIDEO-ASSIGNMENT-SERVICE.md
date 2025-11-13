# ADR-005: Unified Video ID Assignment Service

**Status**: PROPOSED
**Date**: 2025-11-07
**Authors**: System Architecture Team
**Deciders**: Engineering Leadership

---

## Context and Problem Statement

The current system has **THREE independent video_id assignment mechanisms** operating simultaneously, creating what we call a "Frankenstein Architecture":

### Current State: Three Independent Methods

1. **Metadata-Based Assignment** (`labjack_detection_service.py:1021-1047`)
   - Extracts `current_video_id` from `TestSession.sequence_metadata` JSON
   - Used during LabJack hardware detection event processing
   - Vulnerable to metadata staleness and JSON parsing errors

2. **Session Tracking Assignment** (`socketio_server.py:583-603`)
   - Updates `TestSession.video_id` field via WebSocket events
   - Used during frontend video lifecycle events (video_started)
   - Creates race conditions with hardware detection timing

3. **Timestamp Correlation Assignment** (`video_sequence_orchestrator.py:857-879`)
   - Calculates video_id from detection timestamp vs video timing boundaries
   - Uses `SequenceVideoResult.video_start_time` and `video_end_time`
   - Most robust but only used in orchestrator context

### Problems This Creates

**High Complexity**
- Three codepaths to understand, maintain, and debug
- New engineers spend weeks understanding the interaction patterns
- Bug fixes in one method don't propagate to others

**Brittleness**
- Changes to one method can break another unexpectedly
- No single source of truth for "which video is this detection from?"
- Defensive coding everywhere to handle method disagreements

**Data Inconsistency Risk**
- Methods can disagree on video_id assignment
- Race conditions when metadata updates lag behind timing boundaries
- Detection events may have incorrect video_id under load

**Maintenance Nightmare**
- Bug fixes require changes in 3+ files
- Testing requires validating all three methods
- Regression risk is extremely high

---

## Decision Drivers

1. **Single Source of Truth**: One canonical method for video assignment
2. **Robustness**: Must handle edge cases (startup, shutdown, transitions)
3. **Performance**: Sub-millisecond assignment under high detection rates
4. **Safety**: Zero-downtime migration from current state
5. **Testability**: Easy to unit test and validate correctness

---

## Considered Options

### Option 1: Metadata-Based (Status Quo - Rejected)

**Pros**:
- Simple JSON extraction
- No database queries needed

**Cons**:
- Metadata can become stale (race conditions)
- JSON parsing errors break assignment
- Frontend-driven, not hardware-driven
- No confidence scoring

**Decision**: ❌ REJECTED - Too fragile for production HIL system

---

### Option 2: Session Tracking (Status Quo - Rejected)

**Pros**:
- Real-time updates from frontend
- Direct session field access

**Cons**:
- Race conditions with hardware timing
- WebSocket events can be delayed/lost
- Requires frontend to be authoritative (wrong for HIL)
- No historical tracking

**Decision**: ❌ REJECTED - Hardware should be authoritative, not frontend

---

### Option 3: Timestamp Correlation (SELECTED)

**Pros**:
- ✅ Most robust - based on hardware timestamps
- ✅ Database-backed timing boundaries (SequenceVideoResult)
- ✅ Handles edge cases with grace periods
- ✅ Provides confidence scores for validation
- ✅ Self-correcting as timing data improves

**Cons**:
- Requires database query per detection (mitigated with caching)
- Depends on accurate video_start_time persistence

**Decision**: ✅ SELECTED - This is the correct architecture

---

## Decision Outcome

### Chosen Solution: Unified VideoAssignmentService

**Design Philosophy**: "Hardware timing is the single source of truth"

#### Core Architecture

```python
class VideoAssignmentService:
    """
    Single authoritative service for video_id assignment.

    DESIGN PRINCIPLES:
    1. Hardware timestamps are authoritative
    2. Database timing boundaries are canonical
    3. Confidence scores enable validation
    4. Caching provides performance
    5. Graceful degradation on failures
    """

    def get_video_id_for_detection(
        self,
        session_id: str,
        detection_timestamp: float,
        db: Session
    ) -> VideoAssignmentResult:
        """
        Determine which video a detection belongs to.

        Returns:
            VideoAssignmentResult with video_id and confidence
        """
```

#### Algorithm (Timestamp-Based with Grace Periods)

1. **Query Video Timing Boundaries**
   ```sql
   SELECT video_id, video_start_time, video_end_time
   FROM sequence_video_results
   WHERE video_sequence_id = (
       SELECT sequence_id FROM test_sessions WHERE id = :session_id
   )
   ORDER BY sequence_order
   ```

2. **Find Matching Video**
   - Check: `video_start_time <= timestamp < video_end_time`
   - Grace period: ±100ms for transition timing tolerance
   - Handle edge case: First detection before any video starts

3. **Calculate Confidence Score**
   ```
   confidence = 1.0 if exact match
   confidence = 0.8 if within grace period
   confidence = 0.5 if inferred from session metadata
   confidence = 0.0 if no match found
   ```

4. **Cache Results**
   - LRU cache keyed by `(session_id, timestamp_bucket)`
   - 1-second buckets for cache efficiency
   - Max 1000 entries to prevent memory growth

---

## Migration Strategy: Safe 4-Week Rollout

### Phase 5a: Deploy Service (Week 1) - Validation-Only Mode

**Goal**: Introduce service without changing behavior

```python
# In labjack_detection_service.py (line 1033)
video_id = self._get_video_id_from_metadata()  # EXISTING

# NEW: Run unified service in validation mode
unified_result = video_assignment_service.get_video_id_for_detection(
    session_id=session.id,
    detection_timestamp=timestamp,
    db=db
)

# Log discrepancies for analysis
if unified_result.video_id != video_id:
    logger.warning(
        f"VIDEO_ID_MISMATCH: metadata={video_id}, "
        f"unified={unified_result.video_id}, "
        f"confidence={unified_result.confidence}"
    )
```

**Success Criteria**:
- Service runs without errors for 1 week
- Confidence scores > 0.8 for 99% of detections
- Mismatch rate < 1% after initial calibration

**Rollback**: Delete validation code, no production impact

---

### Phase 5b: Switch LabJack Service (Week 2)

**Goal**: Use unified service for hardware detections

```python
# In labjack_detection_service.py (line 1033)
# OLD CODE REMOVED:
# if session.sequence_id and session.sequence_metadata:
#     metadata = session.sequence_metadata
#     current_video_id = metadata.get('current_video_id')

# NEW CODE:
assignment = video_assignment_service.get_video_id_for_detection(
    session_id=session.id,
    detection_timestamp=timestamp,
    db=db
)

if assignment.confidence < 0.5:
    logger.error(f"Low confidence video assignment: {assignment.confidence}")
    # Fallback to session.video_id

video_id = assignment.video_id
```

**Success Criteria**:
- Detection assignment accuracy > 99.5%
- Zero data loss events
- Latency calculation correctness maintained

**Rollback**: Revert to metadata extraction, keep validation logs

---

### Phase 5c: Switch Orchestrator (Week 3)

**Goal**: Replace `_determine_video_for_detection` with unified service

```python
# In video_sequence_orchestrator.py (line 445)
# OLD CODE REMOVED:
# video_id = self._determine_video_for_detection(sequence, sequence_timestamp)

# NEW CODE:
assignment = self.video_assignment_service.get_video_id_for_detection(
    session_id=sequence.session_id,
    detection_timestamp=sequence_timestamp,
    db=db
)

video_id = assignment.video_id
if video_id is None:
    logger.warning(f"Could not determine video at {sequence_timestamp:.6f}")
    return None
```

**Success Criteria**:
- Multi-video sequence tests pass 100%
- Ground truth matching accuracy unchanged
- Per-video metrics calculation correct

**Rollback**: Restore `_determine_video_for_detection` method

---

### Phase 5d: Remove Legacy Code (Week 4)

**Goal**: Clean up old metadata-based and session-tracking methods

**Remove**:
1. `socketio_server.py:583-603` - TestSession.video_id updates
2. `labjack_detection_service.py:1021-1040` - Metadata extraction logic
3. `video_sequence_orchestrator.py:857-879` - `_determine_video_for_detection`

**Keep**:
- `TestSession.sequence_metadata` field (used for other purposes)
- `TestSession.video_id` field (used for single-video sessions)

**Success Criteria**:
- All tests pass with removed code
- Code complexity metrics improve
- No production incidents for 2 weeks

**Rollback**: Git revert to Phase 5c state

---

## Positive Consequences

1. **Reduced Complexity**
   - One method to understand instead of three
   - 40% reduction in video assignment code
   - Easier onboarding for new engineers

2. **Increased Reliability**
   - Timestamp-based assignment is most robust
   - Confidence scores enable validation
   - Self-correcting as timing data improves

3. **Better Performance**
   - LRU caching reduces database queries by ~80%
   - Sub-millisecond assignment latency
   - Scales to 1000+ detections/second

4. **Easier Testing**
   - Single service to unit test
   - Clear contract: (session_id, timestamp) → video_id
   - Mock-friendly design

5. **Future-Proof Architecture**
   - Easy to add new assignment strategies
   - Confidence scoring enables A/B testing
   - Supports video sequence evolution

---

## Negative Consequences

1. **Migration Risk**
   - 4-week phased rollout required
   - Potential for regression during transition
   - **Mitigation**: Extensive validation logging, rollback at each phase

2. **Database Dependency**
   - Requires SequenceVideoResult timing data to be accurate
   - **Mitigation**: Validation in Phase 5a ensures data quality

3. **Cache Complexity**
   - LRU cache adds state to service
   - **Mitigation**: Cache invalidation on video transitions

4. **Performance Requirements**
   - Must handle 1000+ detections/second
   - **Mitigation**: Benchmark testing before Phase 5b

---

## Implementation Details

See accompanying files:
- `UNIFIED-VIDEO-ASSIGNMENT-IMPLEMENTATION.py` - Complete service code
- `MIGRATION-PLAN-PHASE5.md` - Detailed week-by-week rollout
- `BEFORE-AFTER-COMPARISON.md` - Visual architecture diagrams
- `INTEGRATION-GUIDE-PHASE5.md` - Component integration instructions
- `RISK-ASSESSMENT-PHASE5.md` - Failure modes and mitigations

---

## Links

- [Issue #5: Video Assignment Inconsistencies](../backend/docs/VIDEO_2_ZERO_DETECTIONS_ROOT_CAUSE_ANALYSIS.md)
- [SequenceVideoResult Schema](../backend/models.py:487-547)
- [Current Orchestrator Logic](../backend/services/video_sequence_orchestrator.py:857-879)
- [LabJack Detection Service](../backend/services/labjack_detection_service.py:1021-1047)

---

## Approval

- [ ] System Architect Review
- [ ] Backend Team Lead Approval
- [ ] QA Team Sign-off
- [ ] Production Readiness Checklist Complete

**Approval Date**: _____________
**Deployed Date**: _____________
