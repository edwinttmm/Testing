# Detection Storage Implementation Analysis for Post-Test Correlation

**Date:** 2025-11-14
**Objective:** Analyze current detection storage to understand what needs to change for post-test correlation
**Status:** CRITICAL - Real-time correlation should be eliminated

---

## Executive Summary

The current implementation performs **real-time correlation** during test execution, attempting to match detections to videos immediately as hardware events occur. This causes race conditions, retry loops, and complex timing coordination. For post-test correlation, we need to **simplify to pure capture** and defer all matching to after test completion.

---

## 1. Current Detection Storage Function

### Location
`/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

### Primary Function: `_store_event_sync_wrapper` (Lines 748-875)

**Current Behavior:**
```python
def _store_event_sync_wrapper(self, hil_event, labjack_trigger_time, detection_record_time):
    """
    CURRENT IMPLEMENTATION: Attempts real-time video_id assignment
    """
    db = next(get_db())
    try:
        # ❌ PROBLEM: Enriches event context during detection capture
        if not hil_event.video_id or (hil_event.sequence_id and not hil_event.sequence_video_result_id):
            self._enrich_hil_event_context(hil_event, hil_event.session_id, labjack_trigger_time)

        # ❌ PROBLEM: Complex fallback logic for video_id
        video_id_for_detection = hil_event.video_id
        if not video_id_for_detection:
            session = db.query(TestSession).filter_by(id=hil_event.session_id).first()
            if session:
                if not session.has_video_sequence and session.video_id:
                    video_id_for_detection = session.video_id  # Single-video fallback
                else:
                    # ❌ LEAVES NULL for multi-video - relies on background job
                    logger.warning("Multi-video: leaving video_id NULL until timing ready")

        # ❌ PROBLEM: Complex normalization during capture
        normalized_video_relative = hil_event.video_relative_timestamp
        if hil_event.sequence_timestamp and hil_event.video_play_offset_ms:
            normalized_video_relative = (
                hil_event.sequence_timestamp - (hil_event.video_play_offset_ms / 1000.0)
            )

        # Create DetectionEvent record
        detection_event = DetectionEvent(
            id=hil_event.id,
            test_session_id=hil_event.session_id,
            video_id=video_id_for_detection,  # ❌ ATTEMPTS real-time assignment
            sequence_id=hil_event.sequence_id,
            sequence_video_result_id=hil_event.sequence_video_result_id,
            timestamp=labjack_trigger_time,
            video_relative_timestamp=hil_event.video_relative_timestamp,
            # ... many other fields
        )

        db.add(detection_event)
        db.commit()
```

---

## 2. Fields Currently Set on DetectionEvent

### Fields Set During Capture (Lines 834-862)

| Field | Current Value | Post-Test Goal |
|-------|---------------|----------------|
| `id` | UUID | ✅ Keep |
| `test_session_id` | Session ID | ✅ Keep |
| `video_id` | **Attempted real-time assignment** | ❌ **NULL during capture** |
| `sequence_id` | From enrichment | ❌ **NULL during capture** |
| `sequence_video_result_id` | From enrichment | ❌ **NULL during capture** |
| `timestamp` | LabJack trigger time | ✅ Keep |
| `validation_result` | "PENDING" | ✅ Keep |
| `processing_time_ms` | Latency | ❌ Remove (not latency) |
| `labjack_timestamp` | Trigger time | ✅ Keep |
| `labjack_timestamp_ns` | Nanosecond precision | ✅ Keep |
| `labjack_voltage` | Voltage reading | ✅ Keep |
| `detection_channel` | Channel (AIN0, etc.) | ✅ Keep |
| `video_relative_timestamp` | **Calculated real-time** | ❌ **NULL during capture** |
| `video_frame_number` | **Calculated from FPS** | ❌ **NULL during capture** |
| `actual_latency_ms` | **Calculated latency** | ❌ **NULL during capture** |
| `timing_sync_quality` | "high", "medium", etc. | ❌ **NULL during capture** |
| `detection_type` | "labjack_voltage" | ✅ Keep |
| `source` | "dedicated_labjack_monitor" | ✅ Keep |
| `screenshot_path` | HIL screenshot | ⚠️ Optional |
| `screenshot_zoom_path` | HIL zoom screenshot | ⚠️ Optional |
| `unix_timestamp` | Detection record time | ✅ Keep |
| `detection_timestamp` | DateTime version | ✅ Keep |
| `signal_value` | Voltage | ✅ Keep |
| `sequence_timestamp` | **From enrichment** | ❌ **NULL during capture** |
| `video_play_offset_ms` | **From enrichment** | ❌ **NULL during capture** |
| `detection_metadata` | JSON blob | ✅ Keep (minimal) |
| `signal_type` | 'labjack_voltage' | ✅ Keep |

---

## 3. Real-Time Matching/Correlation Logic to Remove

### A. Video Context Enrichment (Lines 978-1196)

**Function:** `_enrich_hil_event_context`

**Purpose:** Attempts to determine video_id and sequence metadata in real-time

**Problems:**
- Race condition retry logic (5 retries with exponential backoff)
- Cache invalidation complexity
- Database queries during hot path
- Complex window matching algorithm

**Code to Remove:**
```python
def _enrich_hil_event_context(self, hil_event, session_id, labjack_trigger_time):
    """
    ❌ ENTIRE FUNCTION NEEDS REMOVAL

    This performs:
    - Multi-video detection (lines 991-1024)
    - Cache management (lines 1025-1037)
    - Context loading from database (lines 1030-1031)
    - Video matching with retry (lines 1046-1088)
    - Video status validation (lines 1102-1105)
    - Fallback video assignment (lines 1107-1114)
    - SequenceVideoResult lookup (lines 1116-1120)
    - Timestamp normalization (lines 1141-1193)
    """
```

### B. Retry Logic with Exponential Backoff (Lines 915-976)

**Function:** `_get_video_id_with_retry`

**Purpose:** Retries video_id lookup up to 5 times with delays

**Problems:**
- Blocks detection capture for up to 310ms
- Exponential backoff: 10ms, 20ms, 40ms, 80ms, 160ms
- Forces cache refresh on each retry
- Still fails for early detections

**Code to Remove:**
```python
def _get_video_id_with_retry(self, session_id, trigger_time, max_retries=5, initial_delay_ms=10.0):
    """
    ❌ ENTIRE FUNCTION NEEDS REMOVAL

    Current retry pattern:
    - Attempt 1: Immediate
    - Attempt 2: +10ms delay
    - Attempt 3: +20ms delay
    - Attempt 4: +40ms delay
    - Attempt 5: +80ms delay
    Total: Up to 310ms blocking per detection
    """
```

### C. Video Determination from Timing (Lines 1387-1510)

**Function:** `_determine_video_from_timing`

**Purpose:** Uses clamped detection windows to assign video_id

**Problems:**
- Requires pre-computed clamped windows
- Complex grace period logic
- Window cache management
- Fallback to legacy logic

**Code to Remove:**
```python
def _determine_video_from_timing(self, video_timing, trigger_time):
    """
    ❌ REMOVE - Replace with post-test correlation

    Current logic:
    1. Get or create clamped windows (lines 1420)
    2. Use assign_detection() from clamp service (lines 1427)
    3. Fallback to legacy grace period logic (lines 1423)
    """
```

### D. Clamped Window Management (Lines 1311-1385)

**Function:** `_get_or_create_clamped_windows`

**Purpose:** Pre-computes non-overlapping detection windows

**Problems:**
- Cache management complexity
- Requires video timing metadata
- Integration with detection_window_clamp_service

**Code to Remove:**
```python
def _get_or_create_clamped_windows(self, session_id, video_timing):
    """
    ❌ REMOVE - Windows computed post-test instead

    Current logic:
    1. Check window cache (line 1330)
    2. Convert timing dict to VideoTiming objects (lines 1338-1356)
    3. Call clamp_video_windows() (lines 1362-1366)
    4. Cache results (line 1369)
    """
```

### E. Cache Invalidation (Lines 877-913)

**Function:** `invalidate_sequence_cache`

**Purpose:** Clears cached sequence context and pre-generates windows

**Problems:**
- Called after every lifecycle event
- Triggers immediate window regeneration
- Complex locking logic

**Code to Remove:**
```python
def invalidate_sequence_cache(self, session_id):
    """
    ❌ REMOVE - No cache needed for pure capture

    Current operations:
    1. Pop sequence_context from cache
    2. Delete clamped_windows cache
    3. Immediately regenerate windows
    4. Complex locking to prevent deadlock
    """
```

### F. Video Status Validation (Lines 1279-1309)

**Function:** `_validate_video_status`

**Purpose:** Checks if video exists and is part of active sequence

**Problems:**
- Database queries during hot path
- Complex validation logic
- Not needed during capture

**Code to Remove:**
```python
def _validate_video_status(self, video_id, session_id):
    """
    ❌ REMOVE - Validation done post-test

    Current checks:
    1. Video exists in catalog
    2. Video part of sequence
    3. Video link verification
    """
```

---

## 4. Background Jobs / Retry Loops

### A. Detection Video Reassignment Service

**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_video_reassignment.py`

**Purpose:** Background job that fixes NULL video_id after test completion

**Status:** ✅ **KEEP THIS** - This is exactly what we need!

**Current Implementation:**
```python
async def reassign_null_video_ids(session_id, dry_run=False):
    """
    ✅ KEEP - This is the post-test correlation we want

    Process:
    1. Query detections with NULL video_id
    2. Load video timing from SequenceVideoResult
    3. Match detection timestamps to video windows
    4. Update video_id, video_relative_timestamp, frame_number
    5. Report statistics
    """
```

**Improvements Needed:**
- Currently called as background job (implied)
- Should be called explicitly at test end
- Should handle ALL correlation, not just NULL fixes
- Should recalculate all timing fields (latency, relative timestamps)

---

## 5. Real-Time Video Lookup Queries During Test

### Query 1: Session and Sequence Context (Lines 995-1015)
```python
db = SessionLocal()
try:
    session = db.query(TestSession).filter_by(id=session_id).first()
    if session:
        metadata = session.sequence_metadata  # JSON field
        metadata_video_ids = metadata.get("video_ids", [])
        sequence_video_count = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == session.sequence_id
        ).count()
finally:
    db.close()
```

**Problem:** Runs on EVERY detection capture

### Query 2: Load Sequence Context (Lines 1209-1261)
```python
def _load_sequence_context(self, session_id, retry_attempt=0):
    db = SessionLocal()
    try:
        session_record = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        results = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence_id
        ).all()

        # Build context dict with video_timing
    finally:
        db.close()
```

**Problem:** Called multiple times per detection (initial + retries)

### Query 3: Video Validation (Lines 1282-1306)
```python
def _validate_video_status(self, video_id, session_id):
    db = next(get_db())
    try:
        # Check video exists
        video_exists = db.query(Video).filter(Video.id == video_id).first()

        # Check video is part of sequence
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        link = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == session.sequence_id,
            SequenceVideoResult.video_id == video_id
        ).first()
    finally:
        db.close()
```

**Problem:** Extra validation during hot path

---

## 6. DetectionEvent Database Schema

### Current Schema (from models.py lines 328-454)

```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    # ✅ KEEP - Core identification
    id = Column(String(36), primary_key=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"), nullable=False, index=True)

    # ❌ CHANGE - Should be NULL during capture, filled post-test
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=True, index=True)
    sequence_id = Column(String(36), nullable=True, index=True)  # Added but not in code yet
    sequence_video_result_id = Column(String(36), ForeignKey("sequence_video_results.id"), nullable=True, index=True)

    # ✅ KEEP - Raw hardware timing
    timestamp = Column(Float, nullable=False, index=True)  # LabJack trigger time
    labjack_timestamp = Column(Float, nullable=True, index=True)
    labjack_timestamp_ns = Column(String, nullable=True)
    labjack_voltage = Column(Float, nullable=True)
    detection_channel = Column(String, nullable=True)
    unix_timestamp = Column(Float, nullable=True)
    detection_timestamp = Column(DateTime(timezone=True), nullable=True)

    # ❌ CHANGE - Should be NULL during capture, calculated post-test
    validation_result = Column(String, index=True)  # Keep as "PENDING"
    actual_latency_ms = Column(Float, nullable=True, index=True)  # NULL → calculated post-test
    video_relative_timestamp = Column(Float, nullable=True, index=True)  # NULL → calculated post-test
    video_frame_number = Column(Integer, nullable=True, index=True)  # NULL → calculated post-test
    timing_sync_quality = Column(String, default="unknown", index=True)  # Keep "unknown"
    sequence_timestamp = Column(Float, nullable=True, index=True)  # NULL → calculated post-test
    video_play_offset_ms = Column(Float, nullable=True)  # NULL → from SequenceVideoResult post-test

    # ✅ KEEP - Metadata
    detection_type = Column(String, nullable=True)  # "labjack_voltage"
    source = Column(String, nullable=True)  # "dedicated_labjack_monitor"
    detection_metadata = Column(JSON, nullable=True)
    signal_value = Column(Float, nullable=True)  # Same as labjack_voltage
    signal_type = Column(String, nullable=True)  # 'labjack_voltage'

    # ⚠️ DEPRECATED - Remove or ignore
    processing_time_ms = Column(Float, nullable=True)  # Not latency!
    latency_ns = Column(String, nullable=True)  # Use actual_latency_ms instead

    # ⚠️ OPTIONAL - HIL screenshot fields
    screenshot_path = Column(String, nullable=True)
    screenshot_zoom_path = Column(String, nullable=True)

    # ❌ CHANGE - Ground truth matching done post-test
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id"), nullable=True, index=True)

    # ✅ KEEP - Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
```

### Schema Changes Needed

| Field | Current Behavior | Post-Test Behavior |
|-------|-----------------|-------------------|
| `video_id` | Attempted real-time | **NULL during capture** |
| `sequence_id` | From enrichment | **NULL during capture** |
| `sequence_video_result_id` | From enrichment | **NULL during capture** |
| `video_relative_timestamp` | Calculated real-time | **NULL during capture** |
| `video_frame_number` | Calculated from FPS | **NULL during capture** |
| `actual_latency_ms` | Calculated real-time | **NULL during capture** |
| `timing_sync_quality` | "high"/"medium"/etc | **"pending" during capture** |
| `sequence_timestamp` | From enrichment | **NULL during capture** |
| `video_play_offset_ms` | From enrichment | **NULL during capture** |
| `ground_truth_match_id` | NULL (good!) | **NULL during capture, matched post-test** |

**Key Point:** All NULL fields are **perfectly acceptable** during capture. The schema already supports this with `nullable=True`.

---

## 7. Code Blocks to Simplify for "Pure Capture"

### Before: Complex Real-Time Storage (Current)
```python
# Lines 748-875 in dedicated_labjack_monitor.py
def _store_event_sync_wrapper(self, hil_event, labjack_trigger_time, detection_record_time):
    db = next(get_db())
    try:
        # ❌ REMOVE: Real-time enrichment
        if not hil_event.video_id or (hil_event.sequence_id and not hil_event.sequence_video_result_id):
            self._enrich_hil_event_context(hil_event, hil_event.session_id, labjack_trigger_time)

        # ❌ REMOVE: Complex fallback logic
        video_id_for_detection = hil_event.video_id
        if not video_id_for_detection:
            session = db.query(TestSession).filter_by(id=hil_event.session_id).first()
            if session:
                if not session.has_video_sequence and session.video_id:
                    video_id_for_detection = session.video_id
                else:
                    logger.warning("Multi-video: leaving video_id NULL")

        # ❌ REMOVE: Normalization logic
        normalized_video_relative = hil_event.video_relative_timestamp
        if hil_event.sequence_timestamp and hil_event.video_play_offset_ms:
            normalized_video_relative = (
                hil_event.sequence_timestamp - (hil_event.video_play_offset_ms / 1000.0)
            )

        # ❌ REMOVE: Frame number calculation
        if normalized_video_relative and not hil_event.video_frame_number:
            fps = 24.0  # or from metadata
            hil_event.video_frame_number = int(round(normalized_video_relative * fps))

        # Create record with many attempted calculations
        detection_event = DetectionEvent(
            # ... 30+ fields, many calculated in real-time
        )
        db.add(detection_event)
        db.commit()
```

### After: Simplified Pure Capture (Target)
```python
def _store_detection_pure_capture(self, hil_event, labjack_trigger_time):
    """
    ✅ NEW: Pure capture - no matching, no enrichment
    """
    db = next(get_db())
    try:
        # Create minimal detection record with only hardware data
        detection_event = DetectionEvent(
            # IDENTIFICATION
            id=hil_event.id,
            test_session_id=hil_event.session_id,

            # HARDWARE TIMING (raw capture)
            timestamp=labjack_trigger_time,
            labjack_timestamp=labjack_trigger_time,
            labjack_timestamp_ns=int(labjack_trigger_time * 1e9),
            unix_timestamp=time.time(),
            detection_timestamp=datetime.now(timezone.utc),

            # HARDWARE SIGNAL
            labjack_voltage=hil_event.labjack_voltage,
            detection_channel=hil_event.detection_channel,
            signal_value=hil_event.labjack_voltage,
            signal_type='labjack_voltage',

            # METADATA
            detection_type="labjack_voltage",
            source="dedicated_labjack_monitor",
            detection_metadata={
                "capture_time": time.time(),
                "channel": hil_event.detection_channel,
                "voltage": hil_event.labjack_voltage
            },

            # STATUS
            validation_result="PENDING",
            timing_sync_quality="pending",

            # NULL FIELDS (filled post-test)
            video_id=None,
            sequence_id=None,
            sequence_video_result_id=None,
            video_relative_timestamp=None,
            video_frame_number=None,
            actual_latency_ms=None,
            sequence_timestamp=None,
            video_play_offset_ms=None,
            ground_truth_match_id=None
        )

        db.add(detection_event)
        db.commit()
        logger.debug(f"Stored detection {hil_event.id} with pure capture (no correlation)")

    except Exception as e:
        db.rollback()
        logger.error(f"Pure capture storage failed: {e}")
        raise
    finally:
        db.close()
```

**Lines Reduced:** ~127 lines → ~50 lines (60% reduction)

---

## 8. Summary of Changes Required

### Remove These Functions Entirely:
1. `_enrich_hil_event_context()` - Lines 978-1196 (218 lines)
2. `_get_video_id_with_retry()` - Lines 915-976 (61 lines)
3. `_determine_video_from_timing()` - Lines 1387-1510 (123 lines)
4. `_get_or_create_clamped_windows()` - Lines 1311-1385 (74 lines)
5. `invalidate_sequence_cache()` - Lines 877-913 (36 lines)
6. `_validate_video_status()` - Lines 1279-1309 (30 lines)
7. `_load_sequence_context()` - Lines 1198-1261 (63 lines)
8. `_determine_video_from_timing_legacy()` - Lines 1445-1510 (65 lines)

**Total Lines to Remove:** ~670 lines of complex real-time correlation logic

### Simplify These Functions:
1. `_store_event_sync_wrapper()` - Reduce from 127 lines to ~50 lines
2. `_handle_detection_with_video_sync()` - Remove enrichment call (line 648)

### Keep/Enhance These:
1. ✅ `DetectionVideoReassignmentService.reassign_null_video_ids()`
   - This is the post-test correlation we want
   - Needs enhancement to handle ALL correlation, not just NULL fixes

### Database Queries to Eliminate:
- Session context queries during capture (3 queries per detection)
- SequenceVideoResult queries during capture
- Video validation queries during capture
- Cache loading queries during retries

### Fields to Store as NULL During Capture:
- `video_id`
- `sequence_id`
- `sequence_video_result_id`
- `video_relative_timestamp`
- `video_frame_number`
- `actual_latency_ms`
- `sequence_timestamp`
- `video_play_offset_ms`
- `ground_truth_match_id`

### Fields to Calculate Post-Test:
All of the above, plus:
- `timing_sync_quality` (change from "pending" to "high"/"medium"/"low")
- `validation_result` (change from "PENDING" to "PASS"/"FAIL")
- `latency_result` (NEW - "pass"/"fail" based on threshold)

---

## 9. Benefits of Post-Test Correlation

### Performance Benefits:
- **No race conditions** - Detection capture independent of lifecycle events
- **No retry loops** - Eliminates up to 310ms blocking per detection
- **No database queries** during hot path (3+ queries per detection eliminated)
- **No cache management** complexity
- **No window clamping** overhead during capture
- **Faster detection capture** - Only write hardware data

### Reliability Benefits:
- **No NULL video_id bugs** - All detections get assigned post-test
- **No early detection loss** - All detections captured regardless of timing
- **No cache invalidation issues** - No cache needed
- **Consistent timing calculations** - All done with complete data
- **Deterministic results** - Same inputs always produce same outputs

### Maintainability Benefits:
- **670 lines of code removed** - Simpler codebase
- **Clearer separation of concerns** - Capture vs. correlation
- **Easier testing** - Pure capture function is trivial to test
- **Easier debugging** - Correlation happens in single batch job
- **Better error handling** - Failures don't affect capture

---

## 10. Migration Path

### Phase 1: Implement Pure Capture (Week 1)
1. Create new `_store_detection_pure_capture()` function
2. Update `_handle_detection_with_video_sync()` to call pure capture
3. Keep old code as fallback (feature flag)
4. Test with single-video and multi-video sessions

### Phase 2: Enhance Post-Test Correlation (Week 2)
1. Extend `DetectionVideoReassignmentService` to:
   - Calculate video_relative_timestamp
   - Calculate video_frame_number
   - Calculate actual_latency_ms
   - Calculate sequence_timestamp
   - Update timing_sync_quality
2. Add explicit call at test end (not background job)
3. Test with production data

### Phase 3: Remove Old Code (Week 3)
1. Remove 8 functions listed above (~670 lines)
2. Remove cache management code
3. Remove retry logic
4. Remove real-time database queries
5. Clean up HILDetectionEvent dataclass
6. Update documentation

### Phase 4: Ground Truth Matching (Week 4)
1. Implement post-test ground truth matching
2. Use same timing windows as video correlation
3. Update `ground_truth_match_id` field
4. Calculate match quality scores

---

## 11. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing tests depend on real-time fields | High | Feature flag for gradual rollout |
| Post-test correlation failures | Medium | Validate with dry_run first |
| Performance of batch correlation | Low | Optimize with bulk updates |
| Migration complexity | Medium | Phase-based rollout |

---

## Conclusion

The current implementation performs **excessive work during capture** that should be **deferred to post-test**. By simplifying to pure capture:

1. **Remove 670 lines** of complex correlation code
2. **Eliminate race conditions** and retry loops
3. **Improve capture performance** (no queries, no retries)
4. **Increase reliability** (all detections captured)
5. **Simplify maintenance** (clearer separation of concerns)

The existing `DetectionVideoReassignmentService` provides the foundation for post-test correlation. We just need to enhance it to handle ALL correlation work instead of only fixing NULL video_ids.

**Next Steps:**
1. Review this analysis with team
2. Create implementation plan for pure capture
3. Design comprehensive post-test correlation service
4. Plan migration strategy with feature flags
