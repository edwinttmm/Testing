# Backend Approval Process & Validation Logic Analysis

## Executive Summary

This document provides a comprehensive analysis of the backend approval workflow for test sessions in the AI Model Validation Platform, covering the complete lifecycle from test execution through validation, ground truth matching, metrics calculation, and final approval.

**Report Date:** 2025-11-11
**Analysis Scope:** Test session approval workflow, validation logic, pass/fail determination, ground truth matching, and metrics calculation.

---

## Table of Contents

1. [Complete Approval Workflow](#complete-approval-workflow)
2. [Validation Rules & Checks](#validation-rules--checks)
3. [Pass/Fail Determination Logic](#passfail-determination-logic)
4. [Ground Truth Matching Algorithm](#ground-truth-matching-algorithm)
5. [Metrics Calculation Formulas](#metrics-calculation-formulas)
6. [Database Updates During Approval](#database-updates-during-approval)
7. [Code Snippets - Key Logic](#code-snippets---key-logic)

---

## Complete Approval Workflow

### Phase 1: Test Session Creation
**File:** `routers/test_sessions.py` (Lines 183-265)

```python
@router.post("", response_model=TestSessionResponse)
async def create_new_test_session(
    session: TestSessionCreate,
    force_start: bool = Query(False),
    db: Session = Depends(get_db)
):
    # 1. Validate project exists
    project = db.query(Project).filter(Project.id == session.project_id).first()

    # 2. Optional ground truth pre-validation (unless force_start=true)
    if not force_start and session.video_id:
        gt_count = db.query(func.count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id == session.video_id
        ).scalar() or 0

        if gt_count == 0:
            raise HTTPException(
                status_code=422,
                detail=f"Video {session.video_id} has no ground truth data"
            )

    # 3. Create session with status='created'
    db_session = create_test_session(db=db, test_session=session, user_id="anonymous")
```

**Key Points:**
- Pre-session ground truth validation prevents tests from starting without reference data
- `force_start=true` bypasses validation for emergency scenarios
- Session created with status='created', transitions to 'running' on start

### Phase 2: Test Execution & Monitoring
**File:** `routers/test_sessions.py` (Lines 896-1023)

```python
@router.post("/{session_id}/start")
async def start_test_session(session_id: str, db: Session = Depends(get_db)):
    # 1. Update session status and initialize timing
    session.status = "running"
    session.started_at = datetime.utcnow()

    # 2. Initialize HIL video timing synchronization
    video_playback_start_time = session.started_at.timestamp()
    session.video_playback_start_time = video_playback_start_time
    session.hil_timing_enabled = True
    session.video_timing_sync_status = "pending"

    # 3. Start HIL monitoring with video timing sync
    start_hil_monitoring(session_id, video_timing_config)
```

**Key Points:**
- Precise timestamp capture for video synchronization
- HIL monitoring started with video timing correlation
- Status transitions: `created` → `running`

### Phase 3: Video Sequence Validation (Multi-Video Sessions)
**File:** `services/session_completion_service.py` (Lines 21-169)

```python
def validate_video_sequence_completion(db: Session, session_id: str) -> tuple[bool, str]:
    """
    CRITICAL VALIDATION: Ensures video sequence has proper timing data before completion.

    Validation Rules:
    1. Non-sequence sessions always pass (no validation needed)
    2. Sequence sessions must have sequence_metadata with video_timing
    3. Each video must have:
       - started_at timestamp (not NULL)
       - ended_at timestamp (not NULL)
    4. Videos with status "pending" are rejected at completion time
    """

    # Check sequence_metadata exists
    if not session.sequence_metadata:
        return (False, "Video sequence session missing sequence_metadata")

    # Check video_timing exists
    if 'video_timing' not in metadata:
        return (False, "Missing video_timing in sequence_metadata")

    # Validate each video has start and end times
    missing_start_times = []
    missing_end_times = []

    for video_id, timing in video_timing.items():
        started_at = timing.get('started_at') or timing.get('start_time')
        if started_at is None:
            missing_start_times.append(video_id)

        ended_at = timing.get('ended_at') or timing.get('end_time')
        if ended_at is None:
            missing_end_times.append(video_id)

    if missing_start_times or missing_end_times:
        return (False, f"Video(s) missing timing data: {missing_start_times}")

    return (True, "")
```

**Key Points:**
- Prevents completion of sessions with incomplete video lifecycle events
- Ensures frontend video playback events (onPlay, onEnded) were captured
- Blocks sessions where video timing synchronization failed

### Phase 4: Test Session Completion
**File:** `services/session_completion_service.py` (Lines 214-378)

```python
async def complete_session(self, session_id: str, force: bool = False) -> bool:
    """
    Complete session with comprehensive validation and cleanup.

    Steps:
    1. Validate video sequence timing data
    2. Stop LabJack monitoring (preserve hardware connection)
    3. Reassign NULL video_ids (race condition fix)
    4. Update session status to 'completed'
    5. Generate test results
    6. Trigger ground truth matching
    7. Clean up monitoring resources
    """

    # STEP 1: Critical validation
    is_valid, error_message = validate_video_sequence_completion(db, session_id)
    if not is_valid:
        session.status = "validation_failed"
        raise ValueError(f"Cannot complete session: {error_message}")

    # STEP 2: Stop monitoring with connection preservation
    stop_labjack_monitoring()

    # STEP 3: Fix race condition - reassign NULL video_ids
    reassign_null_video_ids(session_id, dry_run=False)

    # STEP 4: Update session status
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()

    # STEP 5: Generate results
    result_data = test_execution_service.get_session_results(session_id)

    # STEP 6: Ground truth matching for validation
    matching_service = get_ground_truth_matching_service()
    matching_results = matching_service.match_detections_to_ground_truth(session_id)
```

**Key Points:**
- Validation-first approach prevents incomplete sessions from completing
- Hardware connection preserved for future tests
- Race condition fix ensures all detections have video_id assignments
- Status transitions: `running` → `completed` (or `validation_failed`)

### Phase 5: Ground Truth Matching
**File:** `services/ground_truth_matching_service.py` (Lines 178-303)

```python
def match_detections_to_ground_truth(
    self,
    session_id: str,
    tolerance_ms: Optional[int] = None,
    force_rematch: bool = False
) -> Optional[SessionMetrics]:
    """
    Main entry point for ground truth matching.

    Process:
    1. Retrieve all detection events and ground truth objects
    2. Perform temporal matching within tolerance windows
    3. Classify as TP/FP/FN
    4. Calculate latency metrics
    5. Populate database with results
    6. Calculate and store session metrics
    """

    # Get detection events and ground truth
    detection_events = db.execute(text("""
        SELECT id, timestamp, confidence, class_label, actual_latency_ms,
               video_relative_timestamp, video_frame_number, video_id
        FROM detection_events
        WHERE test_session_id = :session_id
        ORDER BY timestamp
    """), {'session_id': session_id}).fetchall()

    # Multi-video support: Get GT for all videos in sequence
    ground_truth_objects = self._get_ground_truth_for_session(db, test_session, session_id)

    # Temporal matching algorithm
    match_results = self._perform_temporal_matching(
        detection_events,
        ground_truth_objects,
        tolerance_ms,
        test_session=test_session,
        db=db
    )

    # Populate detection_comparisons table
    self._populate_detection_comparisons(db, session_id, match_results)

    # Calculate and store metrics
    metrics = self._calculate_and_store_metrics(db, session_id, match_results)

    return metrics
```

**Key Points:**
- Tolerance window configurable (default: 100ms)
- Supports both single-video and multi-video sequences
- Results cached - force_rematch clears existing comparisons
- Comprehensive metrics calculation

---

## Validation Rules & Checks

### Pre-Session Validation (Issue #3 Implementation)
**File:** `routers/test_sessions.py` (Lines 86-180)

```python
@router.post("/validate-ground-truth", response_model=GTValidationResponse)
async def validate_ground_truth(request: GTValidationRequest, db: Session = Depends(get_db)):
    """
    Pre-session ground truth validation endpoint.

    Features:
    - Single optimized database query with GROUP BY
    - Response caching (5 min TTL)
    - Per-video status information
    - Minimum detection threshold check
    """

    # CRITICAL: Single query to get ground truth counts
    gt_counts_query = db.query(
        GroundTruthObject.video_id,
        func.count(GroundTruthObject.id).label('gt_count')
    ).filter(
        GroundTruthObject.video_id.in_(request.video_ids)
    ).group_by(
        GroundTruthObject.video_id
    ).all()

    # Build status per video
    for video_id in request.video_ids:
        count = gt_counts.get(video_id, 0)

        if count == 0:
            status = "missing_gt"
        elif count < 5:  # Configurable threshold
            status = "insufficient_gt"
        else:
            status = "ready"
```

**Validation Thresholds:**
- **Missing GT:** 0 ground truth objects → `missing_gt` status
- **Insufficient GT:** 1-4 objects → `insufficient_gt` status
- **Ready:** ≥5 objects → `ready` status

### Video Sequence Validation Rules
**File:** `services/session_completion_service.py` (Lines 21-169)

| Rule | Validation | Consequence |
|------|------------|-------------|
| Sequence metadata exists | `sequence_metadata` field not NULL | Session fails completion |
| Video timing populated | `video_timing` dict in metadata | Session fails completion |
| All videos started | Each video has `started_at` timestamp | Session fails completion |
| All videos ended | Each video has `ended_at` timestamp | Session fails completion |
| No pending videos | No videos with status='pending' | Session fails completion |

### Detection Event Validation
**File:** `services/ground_truth_matching_service.py` (Lines 1006-1056)

```python
# Update detection_events table with validation result
if match_result.detection_event_id:
    detection_event = db.query(DetectionEvent).filter(
        DetectionEvent.id == match_result.detection_event_id
    ).first()

    if detection_event:
        # Update validation_result field (TP/FP/FN)
        detection_event.validation_result = match_result.match_type

        # Update latency and threshold
        if match_result.latency_ms is not None:
            detection_event.actual_latency_ms = match_result.latency_ms
            threshold_ms = detection_event.latency_threshold_ms or session_tolerance_ms

            # Determine pass/fail based on threshold
            detection_event.latency_result = (
                "pass" if match_result.latency_ms <= threshold_ms else "fail"
            )

        # Link to ground truth for TP matches
        if match_result.match_type == 'TP':
            detection_event.ground_truth_match_id = match_result.ground_truth_id
```

**Validation Fields Updated:**
- `validation_result`: TP/FP/FN classification
- `actual_latency_ms`: Measured latency in milliseconds
- `latency_result`: pass/fail based on threshold
- `ground_truth_match_id`: Link to matched GT object (TP only)

---

## Pass/Fail Determination Logic

### Session-Level Pass/Fail
**File:** `services/ground_truth_matching_service.py` (Lines 1207-1236)

```python
def _update_test_session_results(self, db: Session, test_session: TestSession, metrics: SessionMetrics):
    """
    Determine overall session result based on precision, recall, and latency.

    Pass/Fail Criteria:
    - PASS: Precision ≥ 0.8 AND Recall ≥ 0.75 AND Mean Latency ≤ 100ms
    - CONDITIONAL_PASS: Precision ≥ 0.6 AND Recall ≥ 0.6
    - FAIL: Below conditional thresholds
    """

    test_session.actual_detections = metrics.total_detections
    test_session.overall_score = metrics.f1_score * 100

    # Determine pass/fail result
    if metrics.precision >= 0.8 and metrics.recall >= 0.75 and metrics.mean_latency_ms <= 100:
        test_session.pass_fail_result = "PASS"
    elif metrics.precision >= 0.6 and metrics.recall >= 0.6:
        test_session.pass_fail_result = "CONDITIONAL_PASS"
    else:
        test_session.pass_fail_result = "FAIL"
```

**Pass/Fail Thresholds:**

| Result | Precision | Recall | Mean Latency |
|--------|-----------|--------|--------------|
| **PASS** | ≥ 0.8 (80%) | ≥ 0.75 (75%) | ≤ 100ms |
| **CONDITIONAL_PASS** | ≥ 0.6 (60%) | ≥ 0.6 (60%) | Any |
| **FAIL** | < 0.6 (60%) | < 0.6 (60%) | Any |

### Detection-Level Pass/Fail
**File:** `services/ground_truth_matching_service.py` (Lines 1014-1033)

```python
# Individual detection pass/fail based on latency threshold
if match_result.latency_ms is not None:
    threshold_ms = (
        detection_event.latency_threshold_ms
        or session_tolerance_ms
        or self.default_tolerance_ms  # 100ms default
    )

    detection_event.latency_threshold_ms = threshold_ms

    # Pass if latency within threshold
    if match_result.latency_ms <= threshold_ms:
        detection_event.latency_result = "pass"
    else:
        detection_event.latency_result = "fail"
```

**Detection Pass Criteria:**
- **Pass:** `actual_latency_ms ≤ latency_threshold_ms`
- **Fail:** `actual_latency_ms > latency_threshold_ms`
- **Pending:** Latency not yet calculated

---

## Ground Truth Matching Algorithm

### Temporal Matching Overview
**File:** `services/ground_truth_matching_service.py` (Lines 644-918)

The matching algorithm uses a **greedy nearest-neighbor approach** with temporal tolerance windows:

#### Phase 1: Match Ground Truth to Detections (True Positives)

```python
def _perform_temporal_matching(self, detection_events, ground_truth_objects, tolerance_ms):
    """
    Two-phase temporal matching algorithm.

    Phase 1: For each GT, find closest detection within tolerance → TP
    Phase 2: Remaining detections → FP
    Unmatched GT → FN
    """
    tolerance_seconds = tolerance_ms / 1000.0
    used_detections = set()

    # PHASE 1: Match ground truth to nearest detections
    for gt_obj in ground_truth_objects:
        best_match = None
        best_time_diff = float('inf')
        gt_time = extract_ground_truth_video_time(gt_obj, session_start_time)

        for i, detection in enumerate(detection_events):
            if i in used_detections:
                continue  # Skip already matched detections

            # CRITICAL: Video boundary validation (multi-video support)
            detection_video_id = getattr(detection, 'video_id', None)
            gt_video_id = getattr(gt_obj, 'video_id', None)

            if detection_video_id != gt_video_id:
                continue  # Don't match across video boundaries

            detection_time = extract_detection_video_time(detection, session_start_time)
            time_diff = abs(detection_time - gt_time)

            # Find closest detection within tolerance
            if time_diff <= tolerance_seconds and time_diff < best_time_diff:
                best_match = (i, detection)
                best_time_diff = time_diff

        if best_match:
            # TRUE POSITIVE: GT matched to detection
            detection_idx, detection = best_match
            used_detections.add(detection_idx)

            temporal_offset_ms = (detection_time - gt_time) * 1000
            latency_ms = abs(temporal_offset_ms)

            match_results.append(MatchResult(
                ground_truth_id=gt_obj.id,
                detection_event_id=detection.id,
                match_type='TP',
                temporal_offset=temporal_offset_ms,
                latency_ms=latency_ms,
                video_id=detection_video_id
            ))
        else:
            # FALSE NEGATIVE: GT with no matching detection
            match_results.append(MatchResult(
                ground_truth_id=gt_obj.id,
                detection_event_id=None,
                match_type='FN',
                temporal_offset=0.0,
                latency_ms=None
            ))
```

#### Phase 2: Mark Remaining Detections as False Positives

```python
    # PHASE 2: Remaining detections are false positives
    for i, detection in enumerate(detection_events):
        if i not in used_detections:
            match_results.append(MatchResult(
                ground_truth_id=None,
                detection_event_id=detection.id,
                match_type='FP',
                temporal_offset=0.0,
                latency_ms=None,
                video_id=getattr(detection, 'video_id', None)
            ))
```

### Multi-Video Sequence Support
**File:** `services/ground_truth_matching_service.py` (Lines 682-726)

```python
# BUG #10 FIX: Detect multi-video sequences
gt_video_ids = set()
for gt_obj in ground_truth_objects:
    gt_video_id = getattr(gt_obj, 'video_id', None)
    if gt_video_id is not None:
        gt_video_ids.add(gt_video_id)

has_multi_video_sequence = len(gt_video_ids) > 1

if has_multi_video_sequence:
    logger.info(f"BUG #10 FIX: Multi-video sequence detected - "
                f"Enforcing strict video boundary validation")

    # CRITICAL: Don't match detections across video boundaries
    if detection_video_id != gt_video_id:
        video_boundary_rejections += 1
        continue  # Skip this detection for this GT
```

**Key Features:**
- Video boundary enforcement prevents cross-video false matches
- Supports batch query for sequences up to 25k GT objects
- Per-video caching for larger sequences (>25k objects)
- Proper ordering by video_id + timestamp for consistency

### Temporal IoU Scoring
**File:** `services/ground_truth_matching_service.py` (Lines 920-947)

```python
def _calculate_temporal_iou(self, gt_timestamp, detection_timestamp, tolerance_seconds):
    """
    Calculate temporal Intersection over Union (IoU) score.

    Provides normalized score based on proximity within tolerance window.
    - Perfect match (0 diff) = 1.0
    - At tolerance boundary = ~0.5
    - Outside tolerance = 0.0
    """
    time_diff = abs(gt_timestamp - detection_timestamp)

    if time_diff > tolerance_seconds:
        return 0.0

    # IoU score degrades linearly with temporal distance
    iou_score = 1.0 - (time_diff / tolerance_seconds) * 0.5
    return max(0.0, min(1.0, iou_score))
```

**IoU Score Formula:**
```
if time_diff > tolerance:
    IoU = 0.0
else:
    IoU = 1.0 - (time_diff / tolerance) * 0.5
```

---

## Metrics Calculation Formulas

### Core Classification Metrics
**File:** `services/ground_truth_matching_service.py` (Lines 1075-1205)

```python
def _calculate_and_store_metrics(self, db, session_id, match_results):
    """
    Calculate comprehensive performance metrics.

    Metrics:
    - Precision: TP / (TP + FP)
    - Recall: TP / (TP + FN)
    - F1 Score: 2 * (Precision * Recall) / (Precision + Recall)
    - Accuracy: TP / (TP + FN)
    """

    # Count classifications
    tp_results = [mr for mr in match_results if mr.match_type == 'TP']
    fp_results = [mr for mr in match_results if mr.match_type == 'FP']
    fn_results = [mr for mr in match_results if mr.match_type == 'FN']

    true_positives = len(tp_results)
    false_positives = len(fp_results)
    false_negatives = len(fn_results)

    # Precision: What % of detections were correct?
    precision = true_positives / (true_positives + false_positives) \
        if (true_positives + false_positives) > 0 else 0.0

    # Recall: What % of ground truth was detected?
    recall = true_positives / (true_positives + false_negatives) \
        if (true_positives + false_negatives) > 0 else 0.0

    # F1: Harmonic mean of precision and recall
    f1_score = 2 * (precision * recall) / (precision + recall) \
        if (precision + recall) > 0 else 0.0

    # Accuracy: What % of ground truth was correctly detected?
    accuracy = true_positives / (true_positives + false_negatives) \
        if (true_positives + false_negatives) > 0 else 0.0
```

### Latency Statistics (BUG FIX: First 10 TP per Video)
**File:** `services/ground_truth_matching_service.py` (Lines 1107-1143)

```python
    # CRITICAL FIX: Only use first 10 TP detections per video
    # Prevents contamination from late-stage detections when GT runs out

    video_tp_latencies = defaultdict(list)
    for mr in tp_results:
        if mr.latency_ms is not None:
            video_id = str(mr.video_id) if mr.video_id else 'default_video'

            # Only first 10 per video
            if len(video_tp_latencies[video_id]) < 10:
                video_tp_latencies[video_id].append(mr.latency_ms)

    # Combine first 10 from each video for overall average
    valid_latencies = []
    for video_id, latencies in video_tp_latencies.items():
        valid_latencies.extend(latencies)

    if valid_latencies:
        mean_latency_ms = statistics.mean(valid_latencies)
        std_latency_ms = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0.0
        max_latency_ms = max(valid_latencies)
        min_latency_ms = min(valid_latencies)

        # Calculate within-tolerance percentage
        tolerance_ms = test_session.tolerance_ms or self.default_tolerance_ms
        within_tolerance_count = sum(1 for lat in valid_latencies if lat <= tolerance_ms)
        within_tolerance_percentage = (within_tolerance_count / len(valid_latencies)) * 100
```

**Latency Formulas:**

| Metric | Formula |
|--------|---------|
| **Mean Latency** | `mean(first_10_tp_per_video.latency_ms)` |
| **Std Dev Latency** | `stdev(first_10_tp_per_video.latency_ms)` |
| **Max Latency** | `max(first_10_tp_per_video.latency_ms)` |
| **Min Latency** | `min(first_10_tp_per_video.latency_ms)` |
| **Within Tolerance %** | `(count(latency ≤ threshold) / total) * 100` |

**Why First 10 Per Video?**
- Prevents contamination when ground truth runs out before video ends
- Late detections would falsely appear as high latency FP when they're actually valid but unmatchable
- Ensures metrics reflect actual system performance, not data availability

---

## Database Updates During Approval

### Tables Modified During Approval Process

#### 1. `test_sessions` Table
**File:** `services/session_completion_service.py` (Lines 296-308)

```python
# Update session status and timestamps
session.status = "completed"
session.completed_at = datetime.now(timezone.utc)
session.actual_detections = metrics.total_detections
session.overall_score = metrics.f1_score * 100
session.pass_fail_result = "PASS" | "CONDITIONAL_PASS" | "FAIL"
db.commit()
```

**Fields Updated:**
- `status`: `running` → `completed` (or `validation_failed`)
- `completed_at`: Current UTC timestamp
- `actual_detections`: Total detection count
- `overall_score`: F1 score as percentage
- `pass_fail_result`: PASS/CONDITIONAL_PASS/FAIL

#### 2. `detection_events` Table
**File:** `services/ground_truth_matching_service.py` (Lines 1006-1056)

```python
# Update detection event with validation results
detection_event.validation_result = 'TP' | 'FP' | 'FN'
detection_event.actual_latency_ms = match_result.latency_ms
detection_event.latency_threshold_ms = threshold_ms
detection_event.latency_result = 'pass' | 'fail' | 'pending'
detection_event.ground_truth_match_id = gt_obj.id  # TP only
db.commit()
```

**Fields Updated:**
- `validation_result`: TP/FP/FN classification
- `actual_latency_ms`: Measured latency
- `latency_threshold_ms`: Threshold used for pass/fail
- `latency_result`: pass/fail/pending
- `ground_truth_match_id`: Link to matched GT (TP only)

#### 3. `detection_comparisons` Table
**File:** `services/ground_truth_matching_service.py` (Lines 949-1073)

```python
# Populate detection_comparisons with match results
for match_result in match_results:
    payload = {
        "id": str(uuid.uuid4()),
        "test_session_id": session_id,
        "ground_truth_id": match_result.ground_truth_id,
        "detection_event_id": match_result.detection_event_id,
        "match_type": 'TP' | 'FP' | 'FN',
        "iou_score": match_result.iou_score,
        "temporal_offset": match_result.temporal_offset,
        "notes": f"Temporal matching with offset {offset:.1f}ms"
    }
    db.execute(insert(comparison_table).values(**payload))
```

**Fields Populated:**
- `id`: UUID
- `test_session_id`: Session identifier
- `ground_truth_id`: GT object ID (NULL for FP)
- `detection_event_id`: Detection ID (NULL for FN)
- `match_type`: TP/FP/FN
- `iou_score`: Temporal IoU score (0.0-1.0)
- `temporal_offset`: Time difference in milliseconds
- `notes`: Matching details

#### 4. `performance_metrics` Table
**File:** `services/ground_truth_matching_service.py` (Lines 1165-1198)

```python
# Store comprehensive performance metrics
performance_metrics = PerformanceMetrics(
    test_session_id=session_id,
    precision=precision,
    recall=recall,
    f1_score=f1_score,
    accuracy=accuracy,
    mean_latency_ms=mean_latency_ms,
    std_latency_ms=std_latency_ms,
    max_latency_ms=max_latency_ms,
    within_tolerance_percentage=within_tolerance_percentage,
    true_positives=true_positives,
    false_positives=false_positives,
    false_negatives=false_negatives,
    overall_score=f1_score * 100,
    statistical_data={
        'latency_distribution': valid_latencies[:100],
        'temporal_offsets': [mr.temporal_offset for mr in tp_results],
        'confidence_scores': [mr.confidence for mr in tp_results],
        'matching_summary': {...}
    }
)
db.add(performance_metrics)
```

**Fields Populated:**
- Core metrics: precision, recall, f1_score, accuracy
- Latency stats: mean, std, max, within_tolerance_%
- Counts: true_positives, false_positives, false_negatives
- Statistical data: distributions, offsets, confidences

#### 5. `test_results` Table
**File:** `routers/test_sessions.py` (Lines 1186-1230)

```python
# Create TestResult entry with ground truth metrics
test_result = TestResult(
    id=str(uuid.uuid4()),
    test_session_id=session_id,
    total_detections=detection_count,
    passed_detections=matching_results.true_positives,
    failed_detections=matching_results.false_positives,
    pass_rate=matching_results.precision * 100,
    test_duration_seconds=duration,
    detection_rate_hz=detection_count / duration if duration > 0 else 0,
    validation_type="HIL_GroundTruth_Matched",
    threshold_ms=500,  # Temporal matching tolerance

    # Real latency measurements
    avg_latency_ms=matching_results.avg_latency_ms,
    min_latency_ms=matching_results.min_latency_ms,
    max_latency_ms=matching_results.max_latency_ms,
    median_latency_ms=matching_results.median_latency_ms,

    # ML metrics from ground truth matching
    precision=matching_results.precision,
    recall=matching_results.recall,
    f1_score=matching_results.f1_score,
    accuracy=(matching_results.true_positives / max(1, ground_truth_count)),

    # Confusion matrix
    true_positives=matching_results.true_positives,
    false_positives=matching_results.false_positives,
    false_negatives=matching_results.false_negatives,

    created_at=datetime.utcnow()
)
db.add(test_result)
```

**Fields Populated:**
- Detection counts and rates
- Latency measurements (avg, min, max, median)
- ML metrics (precision, recall, F1, accuracy)
- Confusion matrix (TP, FP, FN)
- Validation type and threshold

---

## Code Snippets - Key Logic

### Complete Session Workflow (End-to-End)

```python
# STEP 1: Pre-session validation
gt_count = db.query(func.count(GroundTruthObject.id)).filter(
    GroundTruthObject.video_id == session.video_id
).scalar()

if gt_count == 0:
    raise HTTPException(status_code=422, detail="No ground truth data")

# STEP 2: Create and start session
session = create_test_session(db, session_data)
session.status = "running"
start_hil_monitoring(session_id)

# STEP 3: Monitor test execution
# (LabJack detections captured in real-time)

# STEP 4: Validate video sequence completion
is_valid, error = validate_video_sequence_completion(db, session_id)
if not is_valid:
    raise ValueError(f"Completion validation failed: {error}")

# STEP 5: Complete session
session.status = "completed"
session.completed_at = datetime.now(timezone.utc)

# STEP 6: Perform ground truth matching
matching_service = get_ground_truth_matching_service()
metrics = matching_service.match_detections_to_ground_truth(session_id)

# STEP 7: Determine pass/fail
if metrics.precision >= 0.8 and metrics.recall >= 0.75 and metrics.mean_latency_ms <= 100:
    session.pass_fail_result = "PASS"
elif metrics.precision >= 0.6 and metrics.recall >= 0.6:
    session.pass_fail_result = "CONDITIONAL_PASS"
else:
    session.pass_fail_result = "FAIL"

# STEP 8: Populate results tables
db.add(test_result)
db.add(performance_metrics)
db.commit()
```

### Temporal Matching Core Algorithm

```python
# For each ground truth object
for gt_obj in ground_truth_objects:
    best_match = None
    best_time_diff = float('inf')

    # Find nearest detection within tolerance
    for i, detection in enumerate(detection_events):
        if i in used_detections:
            continue

        # Video boundary check (multi-video support)
        if detection.video_id != gt_obj.video_id:
            continue

        time_diff = abs(detection_time - gt_time)

        if time_diff <= tolerance_seconds and time_diff < best_time_diff:
            best_match = (i, detection)
            best_time_diff = time_diff

    # Classify result
    if best_match:
        # TRUE POSITIVE
        used_detections.add(best_match[0])
        latency_ms = best_time_diff * 1000
        match_results.append(MatchResult(type='TP', latency_ms=latency_ms))
    else:
        # FALSE NEGATIVE
        match_results.append(MatchResult(type='FN', latency_ms=None))

# Remaining detections are FALSE POSITIVES
for i, detection in enumerate(detection_events):
    if i not in used_detections:
        match_results.append(MatchResult(type='FP', latency_ms=None))
```

### Pass/Fail Determination

```python
# Session-level pass/fail criteria
if precision >= 0.8 and recall >= 0.75 and mean_latency <= 100:
    result = "PASS"
elif precision >= 0.6 and recall >= 0.6:
    result = "CONDITIONAL_PASS"
else:
    result = "FAIL"

# Detection-level pass/fail
if actual_latency_ms <= latency_threshold_ms:
    detection.latency_result = "pass"
else:
    detection.latency_result = "fail"
```

### Metrics Calculation

```python
# Precision: Correct detections / Total detections
precision = TP / (TP + FP)

# Recall: Detected GT / Total GT
recall = TP / (TP + FN)

# F1: Harmonic mean of precision and recall
f1_score = 2 * (precision * recall) / (precision + recall)

# Accuracy: Correct detections / Total GT
accuracy = TP / (TP + FN)

# Latency (first 10 TP per video only)
mean_latency = mean([latency for latency in first_10_tp_per_video])
std_latency = stdev([latency for latency in first_10_tp_per_video])
within_tolerance_% = (count(latency <= threshold) / total) * 100
```

---

## Summary

The backend approval workflow implements a **comprehensive validation pipeline** with:

1. **Pre-session validation** ensures ground truth availability
2. **Video sequence validation** prevents incomplete sessions from completing
3. **Temporal matching algorithm** classifies detections as TP/FP/FN with configurable tolerance
4. **Multi-video support** with video boundary enforcement
5. **Robust metrics calculation** using first 10 TP per video to prevent contamination
6. **Database persistence** across 5 tables with comprehensive result storage
7. **Tiered pass/fail criteria** with PASS/CONDITIONAL_PASS/FAIL levels

**Key Innovations:**
- Video lifecycle validation prevents premature completion
- Video boundary enforcement prevents cross-video false matches
- First-10-per-video latency calculation prevents GT-depletion bias
- Temporal IoU scoring provides match quality assessment
- Comprehensive audit trail with full result traceability

This workflow ensures **high-confidence validation results** with full transparency into classification decisions and performance metrics.

---

**Analysis Complete**
Generated: 2025-11-11
Platform: AI Model Validation Platform (HIL Testing System)
