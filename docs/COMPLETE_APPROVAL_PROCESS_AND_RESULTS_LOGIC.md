# Complete Approval Process and Results Logic Documentation

**Session ID Reference:** a90187aa-2237-4afe-90d5-3c8176db622f
**URL:** http://localhost:3000/results/a90187aa-2237-4afe-90d5-3c8176db622f

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Complete Data Flow Architecture](#complete-data-flow-architecture)
3. [Backend Approval Workflow](#backend-approval-workflow)
4. [Frontend Results Display Logic](#frontend-results-display-logic)
5. [Pass/Fail Determination Rules](#passfail-determination-rules)
6. [Metrics Calculation Formulas](#metrics-calculation-formulas)
7. [Ground Truth Matching Algorithm](#ground-truth-matching-algorithm)
8. [Validation Thresholds](#validation-thresholds)
9. [Multi-Video Sequence Handling](#multi-video-sequence-handling)
10. [Critical Issues and Recommendations](#critical-issues-and-recommendations)

---

## Executive Summary

This document provides a complete end-to-end analysis of the approval process from test execution through results display for the AI Model Validation Platform's Hardware-in-the-Loop (HIL) testing system.

### Key Findings

**✅ What Works Well:**
- Robust backend validation with multiple safety checks
- Precise temporal matching algorithm with video boundary protection
- Comprehensive metrics calculation (TP/FP/FN, Precision, Recall, F1)
- Multi-video sequence support with per-video and aggregated metrics
- Real-time WebSocket updates during test execution

**❌ Critical Issues Identified:**
1. **No Formal Approval Workflow**: Frontend displays results but has no approve/reject buttons or approval persistence
2. **Deprecated Frontend Calculation**: HILResults.tsx contains unused metrics calculation that produces incorrect results
3. **Schema Inconsistency**: Mixed snake_case/camelCase field names between backend and frontend
4. **Timing Validation Required**: Session completion validates video lifecycle events to prevent NULL timestamp bugs

### System Architecture at a Glance

```
LabJack Hardware → Detection Events → Ground Truth Matching → Metrics Calculation → Results Display
     ↓                    ↓                     ↓                      ↓                  ↓
 T_detection       DetectionEvent      DetectionComparison      SessionMetrics      HILResults.tsx
 (~1μs precision)  (video_id, ts)      (TP/FP/FN, latency)     (P, R, F1, avg)     (UI components)
```

---

## Complete Data Flow Architecture

### Phase 1: Test Initialization

**Timeline:** T = 0ms
**Key Service:** `test_execution_service.py`, `video_sequence_orchestrator.py`

```python
# Location: backend/services/test_execution_service.py
def create_test_session(project_id, video_ids, config):
    """
    1. Capture T0 timestamp (command execution time)
    2. Detect multi-video sequence
    3. Create TestSession record
    4. Initialize VideoSequenceOrchestrator if multi-video
    5. Create SequenceVideoResult for each video
    6. Emit 'session_started' WebSocket event
    """
    t0 = time.perf_counter()  # ~150ns precision
    session = TestSession(
        id=session_id,
        project_id=project_id,
        status="created",
        has_video_sequence=len(video_ids) > 1,
        config=config
    )
    db.add(session)
    db.commit()

    if len(video_ids) > 1:
        orchestrator = VideoSequenceOrchestrator(session_id)
        orchestrator.initialize(video_ids)

    socketio.emit('session_started', {
        'session_id': session_id,
        't0': t0,
        'video_count': len(video_ids)
    })
```

**Database Records Created:**
- `test_sessions` (id, project_id, status="created", has_video_sequence)
- `video_test_sequences` (session_id, total_videos, current_video_index=0)
- `sequence_video_results[]` (sequence_id, video_id, position, status="pending")

**Frontend Action:**
`HILResults.tsx` → `websocketService.subscribe('session_started')` → Display loading state

---

### Phase 2: Video Playback Start

**Timeline:** T = T1 (when video.play() executes)
**Key Service:** `timing_orchestration_service.py`

```python
# Location: backend/services/timing_orchestration_service.py
def handle_video_start(session_id, video_id):
    """
    1. Capture T1 timestamp (video start time)
    2. Store started_at in sequence_video_results
    3. Calculate cumulative offset for multi-video sequences
    4. Update sequence_metadata.video_timing for LabJack correlation
    5. Emit 'video_started' WebSocket event
    """
    t1 = time.perf_counter()

    # Get previous videos' actual durations for cumulative offset
    previous_videos = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.sequence_id == sequence_id,
        SequenceVideoResult.position < current_position
    ).all()

    cumulative_offset = sum(v.actual_duration_ms for v in previous_videos if v.actual_duration_ms)

    # Update sequence metadata for LabJack detection assignment
    sequence_metadata = session.sequence_metadata or {}
    sequence_metadata['video_timing'] = {
        video_id: {
            'start_time': t1,
            'cumulative_offset_ms': cumulative_offset,
            'expected_duration_ms': video.duration_ms
        }
    }
    session.sequence_metadata = sequence_metadata

    # Store video start timestamp
    video_result.started_at = datetime.utcnow()
    video_result.status = "playing"
    db.commit()
```

**Critical Validation (BUG FIX #7):**
- `sequence_metadata.video_timing` MUST be updated for LabJack detections to correlate to correct video
- Uses **actual_duration_ms** (not NULL expected duration) for cumulative offset calculation

**WebSocket Payload:**
```json
{
  "event": "video_started",
  "session_id": "a90187aa-2237-4afe-90d5-3c8176db622f",
  "video_id": "video-001",
  "position": 1,
  "t1": 1234567890.123456,
  "cumulative_offset_ms": 0
}
```

**Frontend Action:**
`SequentialVideoPlayer.tsx` → Update current video indicator → Start playback

---

### Phase 3: Real-Time Detection Events

**Timeline:** T = T1 + detection_offset (continuous during playback)
**Key Service:** `dedicated_labjack_monitor.py`, `video_id_resolver.py`

```python
# Location: backend/services/dedicated_labjack_monitor.py
def process_voltage_detection(session_id, voltage, t_detection):
    """
    1. LabJack captures voltage signal (hardware trigger)
    2. Calculate video_relative_timestamp
    3. Assign detection to correct video using timestamp
    4. Calculate preliminary latency
    5. Store DetectionEvent
    6. Emit 'detection_event' WebSocket
    """
    # Get session timing metadata
    session = db.query(TestSession).get(session_id)
    t0 = session.created_at.timestamp()

    # Calculate video-relative timestamp
    video_relative_ms = (t_detection - t0) * 1000

    # Assign to correct video using VideoIdResolver
    video_id = VideoIdResolver.resolve_video_id(
        session_id=session_id,
        timestamp_ms=video_relative_ms,
        sequence_metadata=session.sequence_metadata
    )

    # Store detection
    detection = DetectionEvent(
        session_id=session_id,
        video_id=video_id,
        timestamp=t_detection,
        video_relative_timestamp=video_relative_ms,
        voltage=voltage,
        latency_ms=None,  # Calculated later during GT matching
        classification=None  # Assigned during GT matching
    )
    db.add(detection)
    db.commit()

    # Broadcast to frontend
    socketio.emit('detection_event', {
        'session_id': session_id,
        'video_id': video_id,
        'timestamp': video_relative_ms,
        'voltage': voltage
    })
```

**Video ID Assignment Algorithm:**

```python
# Location: backend/services/video_id_resolver.py (Lines 45-120)
def resolve_video_id(session_id, timestamp_ms, sequence_metadata):
    """
    Assigns detection to correct video based on timestamp and cumulative offsets.

    Algorithm:
    1. Get video_timing from sequence_metadata
    2. For each video in sequence order:
       - Calculate video_start_offset = cumulative_offset_ms
       - Calculate video_end_offset = cumulative_offset_ms + actual_duration_ms
       - If video_start_offset <= timestamp_ms < video_end_offset: MATCH
    3. Apply 500ms tolerance for late detections after video end
    """
    video_timing = sequence_metadata.get('video_timing', {})

    for video_id, timing in video_timing.items():
        start = timing['cumulative_offset_ms']
        end = start + timing['actual_duration_ms']
        tolerance_ms = 500  # Allow late detections

        if start <= timestamp_ms < (end + tolerance_ms):
            return video_id

    # Fallback: assign to first video if before all windows
    # or last video if after all windows
    return fallback_video_id
```

**Race Condition Fix:**
If `video_id = NULL` (detection arrived before video lifecycle events), reassignment happens during session completion:

```python
# Location: backend/services/session_completion_service.py (Lines 314-389)
def reassign_null_video_ids(session_id):
    """
    Fixes race condition where detections arrive before onPlay event.
    Re-runs VideoIdResolver for all detections with video_id=NULL.
    """
    null_detections = db.query(DetectionEvent).filter(
        DetectionEvent.session_id == session_id,
        DetectionEvent.video_id.is_(None)
    ).all()

    for detection in null_detections:
        video_id = VideoIdResolver.resolve_video_id(
            session_id=session_id,
            timestamp_ms=detection.video_relative_timestamp,
            sequence_metadata=session.sequence_metadata
        )
        detection.video_id = video_id

    db.commit()
```

**Frontend Action:**
`HILResults.tsx` → `websocketService.on('detection_event')` → Append to detection table → Update detection count in real-time

---

### Phase 4: Video Completion

**Timeline:** T = T1 + video_duration (when video.onEnded fires)
**Key Service:** `video_sequence_orchestrator.py`

```python
# Location: backend/services/video_sequence_orchestrator.py (Lines 234-398)
def handle_video_end(session_id, video_id):
    """
    1. Capture T_end timestamp
    2. Calculate actual_duration_ms
    3. Update video status to "completed"
    4. Check if sequence has more videos
    5. If yes: advance to next video
    6. If no: mark sequence complete
    7. Emit WebSocket events
    """
    t_end = time.perf_counter()

    video_result = db.query(SequenceVideoResult).filter_by(
        sequence_id=session.sequence_id,
        video_id=video_id
    ).first()

    # Idempotency check
    if video_result.ended_at is not None:
        logger.warning(f"Video {video_id} already ended, skipping duplicate processing")
        return

    # Calculate actual duration
    t_start = session.sequence_metadata['video_timing'][video_id]['start_time']
    actual_duration_ms = (t_end - t_start) * 1000

    # Update video result
    video_result.ended_at = datetime.utcnow()
    video_result.actual_duration_ms = actual_duration_ms
    video_result.status = "completed"

    # Count detections for this video
    detection_count = db.query(DetectionEvent).filter_by(
        session_id=session_id,
        video_id=video_id
    ).count()
    video_result.detection_count = detection_count

    db.commit()

    # Check sequence progression
    sequence = db.query(VideoTestSequence).get(session.sequence_id)
    if sequence.current_video_index + 1 < sequence.total_videos:
        # Advance to next video
        sequence.current_video_index += 1
        db.commit()

        next_video_id = get_next_video_id(sequence)
        socketio.emit('advance_to_next', {
            'session_id': session_id,
            'next_video_id': next_video_id,
            'position': sequence.current_video_index + 1
        })
    else:
        # Sequence complete
        sequence.status = "completed"
        db.commit()

        socketio.emit('sequence_completed', {
            'session_id': session_id,
            'total_videos': sequence.total_videos,
            'total_detections': session.detection_count
        })
```

**Idempotency Protection:**
Frontend may send duplicate `onEnded` events. Check `ended_at IS NOT NULL` prevents duplicate processing.

**Frontend Action:**
`SequentialVideoPlayer.tsx` → Listen for `advance_to_next` → Load next video → Auto-play if configured

---

### Phase 5: Session Completion & Validation

**Timeline:** After all videos complete
**Key Service:** `session_completion_service.py`

```python
# Location: backend/services/session_completion_service.py (Lines 56-213)
def complete_test_session(session_id):
    """
    CRITICAL VALIDATION before marking session complete:

    1. Validate video sequence timing data exists
    2. Validate all videos have started_at and ended_at
    3. Reassign NULL video_ids (race condition fix)
    4. Execute ground truth matching
    5. Calculate session metrics
    6. Update session status to "completed"
    7. Emit 'session_completed' WebSocket
    """
    session = db.query(TestSession).get(session_id)

    # VALIDATION STEP 1: Check sequence timing metadata
    if session.has_video_sequence:
        validation = validate_video_sequence_completion(session_id)
        if not validation['valid']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete session: {validation['reason']}"
            )

    # VALIDATION STEP 2: Reassign NULL video_ids
    reassign_null_video_ids(session_id)

    # STEP 3: Ground truth matching
    matching_service = GroundTruthMatchingService(db)
    matching_results = matching_service.match_detections_to_ground_truth(
        session_id=session_id,
        tolerance_ms=100  # Default matching window
    )

    # STEP 4: Calculate and store metrics
    metrics = matching_service.calculate_session_metrics(session_id)
    session.precision = metrics.precision
    session.recall = metrics.recall
    session.f1_score = metrics.f1_score
    session.true_positives = metrics.true_positives
    session.false_positives = metrics.false_positives
    session.false_negatives = metrics.false_negatives
    session.mean_latency_ms = metrics.mean_latency_ms

    # STEP 5: Update session status
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.commit()

    # STEP 6: Emit completion event
    socketio.emit('session_completed', {
        'session_id': session_id,
        'status': 'completed',
        'metrics': {
            'precision': metrics.precision,
            'recall': metrics.recall,
            'f1_score': metrics.f1_score,
            'mean_latency_ms': metrics.mean_latency_ms
        }
    })


def validate_video_sequence_completion(session_id):
    """
    Validates that all videos in sequence have proper timing data.

    Returns:
        {'valid': bool, 'reason': str, 'missing_data': []}
    """
    session = db.query(TestSession).get(session_id)
    sequence_metadata = session.sequence_metadata

    # Check video_timing exists
    if not sequence_metadata or 'video_timing' not in sequence_metadata:
        return {
            'valid': False,
            'reason': 'Missing sequence_metadata.video_timing',
            'missing_data': ['video_timing']
        }

    # Get all video results
    video_results = db.query(SequenceVideoResult).filter_by(
        sequence_id=session.sequence_id
    ).all()

    missing_data = []
    for video_result in video_results:
        # Check started_at
        if video_result.started_at is None:
            missing_data.append(f"{video_result.video_id}: started_at is NULL")

        # Check ended_at
        if video_result.ended_at is None:
            missing_data.append(f"{video_result.video_id}: ended_at is NULL")

        # Check actual_duration_ms
        if video_result.actual_duration_ms is None:
            missing_data.append(f"{video_result.video_id}: actual_duration_ms is NULL")

    if missing_data:
        return {
            'valid': False,
            'reason': 'Video lifecycle events did not fire properly',
            'missing_data': missing_data
        }

    return {'valid': True}
```

**Why This Validation Matters:**

If frontend video playback fails to emit `onPlay` or `onEnded` events:
- `started_at` or `ended_at` remain NULL
- LabJack detections cannot be correlated to correct video
- Cumulative offset calculation fails
- **Session completion is BLOCKED with HTTP 400 error**

This prevents corrupted test data from being stored.

**Frontend Action:**
`HILResults.tsx` → `websocketService.on('session_completed')` → Navigate to results page with session_id

---

### Phase 6: Ground Truth Matching

**Timeline:** During session completion (Phase 5, Step 3)
**Key Service:** `ground_truth_matching_service.py`

```python
# Location: backend/services/ground_truth_matching_service.py (Lines 644-918)
def match_detections_to_ground_truth(session_id, tolerance_ms=100):
    """
    Two-phase temporal matching algorithm with video boundary protection.

    PHASE 1: Match ground truth objects to detections (produces TPs and FNs)
    PHASE 2: Classify remaining detections as FPs

    Returns: MatchingResults with classified detections
    """
    session = db.query(TestSession).get(session_id)

    # Fetch all detections for session
    detections = db.query(DetectionEvent).filter_by(
        session_id=session_id
    ).order_by(DetectionEvent.timestamp).all()

    # Fetch all ground truth objects for videos in session
    if session.has_video_sequence:
        video_ids = [v.video_id for v in session.sequence.videos]
    else:
        video_ids = [session.video_id]

    ground_truth_objects = db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id.in_(video_ids),
        GroundTruthObject.soft_deleted == False
    ).order_by(GroundTruthObject.timestamp).all()

    # Group detections and GT by video_id
    detections_by_video = {}
    gt_by_video = {}

    for detection in detections:
        if detection.video_id not in detections_by_video:
            detections_by_video[detection.video_id] = []
        detections_by_video[detection.video_id].append(detection)

    for gt in ground_truth_objects:
        if gt.video_id not in gt_by_video:
            gt_by_video[gt.video_id] = []
        gt_by_video[gt.video_id].append(gt)

    # PHASE 1: Match GT to detections
    true_positives = []
    false_negatives = []
    matched_detection_ids = set()

    for video_id, gt_list in gt_by_video.items():
        video_detections = detections_by_video.get(video_id, [])

        for gt_object in gt_list:
            # Find nearest detection within tolerance window
            best_match = None
            min_time_diff = float('inf')

            for detection in video_detections:
                # Video boundary protection: only match within same video
                if detection.video_id != video_id:
                    continue

                time_diff_ms = abs(detection.timestamp - gt_object.timestamp) * 1000

                if time_diff_ms <= tolerance_ms and time_diff_ms < min_time_diff:
                    best_match = detection
                    min_time_diff = time_diff_ms

            if best_match:
                # TRUE POSITIVE
                latency_ms = (best_match.timestamp - gt_object.timestamp) * 1000
                temporal_iou = 1.0 - (min_time_diff / tolerance_ms)  # Normalized match quality

                true_positives.append(MatchResult(
                    detection_id=best_match.id,
                    ground_truth_id=gt_object.id,
                    match_type='TP',
                    latency_ms=latency_ms,
                    temporal_iou=temporal_iou,
                    time_difference_ms=min_time_diff
                ))

                matched_detection_ids.add(best_match.id)

                # Update detection record
                best_match.classification = 'TP'
                best_match.latency_ms = latency_ms
                best_match.temporal_iou = temporal_iou
            else:
                # FALSE NEGATIVE
                false_negatives.append(MatchResult(
                    detection_id=None,
                    ground_truth_id=gt_object.id,
                    match_type='FN',
                    latency_ms=None,
                    temporal_iou=0.0,
                    time_difference_ms=None
                ))

    # PHASE 2: Classify unmatched detections as FPs
    false_positives = []
    for detection in detections:
        if detection.id not in matched_detection_ids:
            detection.classification = 'FP'
            false_positives.append(MatchResult(
                detection_id=detection.id,
                ground_truth_id=None,
                match_type='FP',
                latency_ms=None,
                temporal_iou=0.0,
                time_difference_ms=None
            ))

    db.commit()

    # Store results in DetectionComparison table
    for tp in true_positives:
        comparison = DetectionComparison(
            detection_event_id=tp.detection_id,
            ground_truth_object_id=tp.ground_truth_id,
            match_type='TP',
            latency_ms=tp.latency_ms,
            temporal_iou=tp.temporal_iou,
            confidence=tp.temporal_iou
        )
        db.add(comparison)

    for fn in false_negatives:
        comparison = DetectionComparison(
            detection_event_id=None,
            ground_truth_object_id=fn.ground_truth_id,
            match_type='FN',
            latency_ms=None,
            temporal_iou=0.0,
            confidence=0.0
        )
        db.add(comparison)

    for fp in false_positives:
        comparison = DetectionComparison(
            detection_event_id=fp.detection_id,
            ground_truth_object_id=None,
            match_type='FP',
            latency_ms=None,
            temporal_iou=0.0,
            confidence=0.0
        )
        db.add(comparison)

    db.commit()

    return MatchingResults(
        true_positives=len(true_positives),
        false_positives=len(false_positives),
        false_negatives=len(false_negatives),
        matches=true_positives + false_positives + false_negatives
    )
```

**Critical Features:**

1. **Video Boundary Protection:** Detections can only match GT objects from the same video_id
2. **Temporal IoU Scoring:** Normalizes match quality (1.0 = exact match, 0.0 = no match)
3. **Greedy Nearest-Neighbor:** Each GT matches to nearest detection within tolerance
4. **Two-Phase Classification:** Prevents double-counting or missed classifications

**Example Scenario:**

```
Video 1 Ground Truth Objects: [t=1.042s, t=1.065s, t=1.088s]
Video 1 Detections: [t=1.065s, t=1.090s]

Phase 1 Matching:
  GT[0] @ 1.042s: No detection within 100ms → FN
  GT[1] @ 1.065s: Matches Detection[0] @ 1.065s (diff=0ms) → TP, latency=0ms
  GT[2] @ 1.088s: Matches Detection[1] @ 1.090s (diff=2ms) → TP, latency=2ms

Phase 2 Classification:
  Detection[0]: Already matched → (no action)
  Detection[1]: Already matched → (no action)

Final Results:
  TP = 2, FP = 0, FN = 1
  Precision = 2/(2+0) = 100%
  Recall = 2/(2+1) = 66.7%
  Mean Latency = (0+2)/2 = 1.0ms
```

---

### Phase 7: Metrics Calculation

**Timeline:** During session completion (Phase 5, Step 4)
**Key Service:** `ground_truth_matching_service.py`

```python
# Location: backend/services/ground_truth_matching_service.py (Lines 1075-1205)
def calculate_session_metrics(session_id):
    """
    Calculates comprehensive metrics for the test session.

    Metrics Calculated:
    - True Positives, False Positives, False Negatives
    - Precision, Recall, F1 Score
    - Mean Latency (first 10 TP per video to avoid bias)
    - Std Dev Latency
    - Within Tolerance Percentage
    - Per-Video Metrics (if multi-video sequence)
    """
    session = db.query(TestSession).get(session_id)

    # Get match results from DetectionComparison table
    comparisons = db.query(DetectionComparison).filter_by(
        session_id=session_id
    ).all()

    # Count classifications
    tp_count = sum(1 for c in comparisons if c.match_type == 'TP')
    fp_count = sum(1 for c in comparisons if c.match_type == 'FP')
    fn_count = sum(1 for c in comparisons if c.match_type == 'FN')

    # Calculate precision, recall, F1
    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
    f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Calculate latency statistics (CRITICAL: first 10 TP per video only)
    latencies = []

    if session.has_video_sequence:
        # Per-video latency sampling to avoid GT depletion bias
        video_ids = [v.video_id for v in session.sequence.videos]

        for video_id in video_ids:
            tp_latencies = db.query(DetectionComparison.latency_ms).filter(
                DetectionComparison.session_id == session_id,
                DetectionComparison.video_id == video_id,
                DetectionComparison.match_type == 'TP',
                DetectionComparison.latency_ms.isnot(None)
            ).order_by(DetectionComparison.created_at).limit(10).all()

            latencies.extend([lat[0] for lat in tp_latencies])
    else:
        # Single video: take first 10 TP
        tp_latencies = db.query(DetectionComparison.latency_ms).filter(
            DetectionComparison.session_id == session_id,
            DetectionComparison.match_type == 'TP',
            DetectionComparison.latency_ms.isnot(None)
        ).order_by(DetectionComparison.created_at).limit(10).all()

        latencies = [lat[0] for lat in tp_latencies]

    # Calculate statistics
    mean_latency = np.mean(latencies) if latencies else None
    std_latency = np.std(latencies, ddof=1) if len(latencies) > 1 else None
    within_tolerance = sum(1 for lat in latencies if lat <= 100) / len(latencies) * 100 if latencies else None

    # Create metrics object
    metrics = SessionMetrics(
        session_id=session_id,
        true_positives=tp_count,
        false_positives=fp_count,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        mean_latency_ms=mean_latency,
        std_latency_ms=std_latency,
        within_tolerance_pct=within_tolerance
    )

    # Store in database
    db.add(metrics)
    db.commit()

    return metrics
```

**Critical Latency Calculation Fix:**

**❌ Wrong Approach (causes bias):**
```python
# Takes ALL TP latencies across all videos
# Problem: Later videos in sequence have fewer GT objects left to match
# Results in artificially low latency for later videos
latencies = [c.latency_ms for c in comparisons if c.match_type == 'TP']
```

**✅ Correct Approach (prevents bias):**
```python
# Takes FIRST 10 TP per video
# Ensures equal representation from each video
# Prevents GT depletion from affecting later videos
for video_id in video_ids:
    video_latencies = get_tp_latencies(video_id, limit=10)
    latencies.extend(video_latencies)
```

**Example:**

```
Video 1: 24 GT objects, 22 detections → 18 TP → Take first 10 TP latencies
Video 2: 24 GT objects, 20 detections → 16 TP → Take first 10 TP latencies
Video 3: 24 GT objects, 18 detections → 14 TP → Take first 10 TP latencies

Total latencies used = 30 (10 from each video)
Mean latency = fair representation across all videos
```

---

### Phase 8: Results Storage

**Timeline:** After metrics calculation
**Database Tables Updated:**

```sql
-- test_sessions table
UPDATE test_sessions SET
    status = 'completed',
    completed_at = NOW(),
    precision = 0.818,
    recall = 0.750,
    f1_score = 0.783,
    true_positives = 18,
    false_positives = 4,
    false_negatives = 6,
    mean_latency_ms = 23.5
WHERE id = 'a90187aa-2237-4afe-90d5-3c8176db622f';

-- detection_events table (per detection)
UPDATE detection_events SET
    classification = 'TP',  -- or 'FP'
    latency_ms = 23.0,
    temporal_iou = 0.95
WHERE id = 'detection-001';

-- detection_comparisons table (match records)
INSERT INTO detection_comparisons (
    session_id,
    detection_event_id,
    ground_truth_object_id,
    match_type,
    latency_ms,
    temporal_iou,
    confidence
) VALUES (
    'a90187aa-2237-4afe-90d5-3c8176db622f',
    'detection-001',
    'gt-object-005',
    'TP',
    23.0,
    0.95,
    0.95
);

-- sequence_video_results table (per-video metrics)
UPDATE sequence_video_results SET
    detection_count = 22,
    true_positives = 18,
    false_positives = 4,
    false_negatives = 6,
    precision = 0.818,
    recall = 0.750,
    f1_score = 0.783,
    mean_latency_ms = 23.5,
    status = 'completed'
WHERE sequence_id = 'seq-001' AND video_id = 'video-001';

-- performance_metrics table (session and per-video)
INSERT INTO performance_metrics (
    session_id,
    video_id,  -- NULL for session-level
    metric_type,
    value,
    timestamp
) VALUES
('a90187aa-2237-4afe-90d5-3c8176db622f', NULL, 'precision', 0.818, NOW()),
('a90187aa-2237-4afe-90d5-3c8176db622f', NULL, 'recall', 0.750, NOW()),
('a90187aa-2237-4afe-90d5-3c8176db622f', NULL, 'f1_score', 0.783, NOW());
```

**Efficient Query Pattern (Prevents N+1):**

```python
# ❌ WRONG: N+1 query problem
for video in videos:
    gt_count = db.query(GroundTruthObject).filter_by(video_id=video.id).count()

# ✅ CORRECT: Single aggregation query
gt_counts = db.query(
    GroundTruthObject.video_id,
    func.count(GroundTruthObject.id).label('count')
).filter(
    GroundTruthObject.video_id.in_(video_ids)
).group_by(GroundTruthObject.video_id).all()
```

---

### Phase 9: Frontend Results Retrieval

**Timeline:** When user navigates to results page
**API Endpoint:** `/api/enhanced-hil/test-sessions/{session_id}/corrected-results`

```python
# Location: backend/src/api/enhanced_hil_results_endpoints.py (Lines 45-234)
@router.get("/test-sessions/{session_id}/corrected-results")
def get_enhanced_hil_results(session_id: str, db: Session = Depends(get_db)):
    """
    Returns comprehensive results with:
    - Session metadata
    - Ground truth comparison metrics
    - Detection events with classifications
    - Per-video results (if multi-video sequence)
    - Screenshot URLs for visual verification
    """
    session = db.query(TestSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get ground truth comparison
    gt_comparison = db.query(DetectionComparison).filter_by(
        session_id=session_id
    ).all()

    # Aggregate metrics
    tp_count = sum(1 for c in gt_comparison if c.match_type == 'TP')
    fp_count = sum(1 for c in gt_comparison if c.match_type == 'FP')
    fn_count = sum(1 for c in gt_comparison if c.match_type == 'FN')

    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
    f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Get detection events
    detections = db.query(DetectionEvent).filter_by(
        session_id=session_id
    ).order_by(DetectionEvent.timestamp).all()

    # Get per-video results (if multi-video)
    per_video_results = []
    if session.has_video_sequence:
        video_results = db.query(SequenceVideoResult).filter_by(
            sequence_id=session.sequence_id
        ).order_by(SequenceVideoResult.position).all()

        for video_result in video_results:
            per_video_results.append({
                'videoId': video_result.video_id,
                'position': video_result.position,
                'detectionCount': video_result.detection_count,
                'groundTruthComparison': {
                    'truePositives': video_result.true_positives,
                    'falsePositives': video_result.false_positives,
                    'falseNegatives': video_result.false_negatives,
                    'precision': video_result.precision,
                    'recall': video_result.recall,
                    'f1Score': video_result.f1_score
                },
                'meanLatencyMs': video_result.mean_latency_ms
            })

    # Build response (using Pydantic for camelCase serialization)
    response = EnhancedHILResultsResponse(
        sessionId=session.id,
        status=session.status,
        groundTruthComparison=GroundTruthComparison(
            truePositives=tp_count,
            falsePositives=fp_count,
            falseNegatives=fn_count,
            precision=precision,
            recall=recall,
            f1Score=f1_score
        ),
        detectionEvents=[
            DetectionEventSchema(
                id=d.id,
                timestamp=d.timestamp,
                videoRelativeTimestamp=d.video_relative_timestamp,
                latencyMs=d.latency_ms,
                classification=d.classification,
                voltage=d.voltage,
                screenshotUrl=d.screenshot_url
            ) for d in detections
        ],
        perVideoResults=per_video_results
    )

    return response
```

**Response Caching:**
Results are cached with 5-minute TTL to reduce database load:

```python
@lru_cache(maxsize=128)
def get_cached_results(session_id: str, cache_key: str):
    return get_enhanced_hil_results(session_id)
```

**Frontend API Call:**

```typescript
// Location: frontend/src/services/api.ts (Lines 234-267)
export async function getEnhancedHILResultsWithGroundTruth(sessionId: string) {
  const response = await fetch(
    `${API_BASE_URL}/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch results: ${response.statusText}`);
  }

  const data = await response.json();

  // Normalize field names (backend may return snake_case or camelCase)
  return normalizeHILResults(data);
}

function normalizeHILResults(data: any) {
  // Handle both snake_case and camelCase field names
  return {
    sessionId: data.sessionId || data.session_id,
    status: data.status,
    groundTruthComparison: {
      truePositives: data.groundTruthComparison?.truePositives ||
                     data.ground_truth_comparison?.true_positives || 0,
      falsePositives: data.groundTruthComparison?.falsePositives ||
                      data.ground_truth_comparison?.false_positives || 0,
      falseNegatives: data.groundTruthComparison?.falseNegatives ||
                      data.ground_truth_comparison?.false_negatives || 0,
      precision: data.groundTruthComparison?.precision ||
                 data.ground_truth_comparison?.precision || 0,
      recall: data.groundTruthComparison?.recall ||
              data.ground_truth_comparison?.recall || 0,
      f1Score: data.groundTruthComparison?.f1Score ||
               data.ground_truth_comparison?.f1_score || 0
    },
    detectionEvents: (data.detectionEvents || data.detection_events || []).map(d => ({
      id: d.id,
      timestamp: d.timestamp,
      videoRelativeTimestamp: d.videoRelativeTimestamp || d.video_relative_timestamp,
      latencyMs: d.latencyMs || d.latency_ms,
      classification: d.classification,
      voltage: d.voltage,
      screenshotUrl: d.screenshotUrl || d.screenshot_url
    })),
    perVideoResults: data.perVideoResults || data.per_video_results || []
  };
}
```

---

### Phase 10: Frontend Results Display

**Timeline:** After API response received
**Component:** `HILResults.tsx`

```typescript
// Location: frontend/src/pages/HILResults.tsx (Lines 456-789)
export const HILResults: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [enhancedResults, setEnhancedResults] = useState<EnhancedHILResults | null>(null);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHILResults();
  }, [sessionId]);

  async function loadHILResults() {
    try {
      setLoading(true);

      // Fetch enhanced results from backend
      const results = await getEnhancedHILResultsWithGroundTruth(sessionId);
      setEnhancedResults(results);

      // If multi-video, set first video as selected
      if (results.perVideoResults && results.perVideoResults.length > 0) {
        setSelectedVideoId(results.perVideoResults[0].videoId);
      }

      // Subscribe to WebSocket for real-time updates
      websocketService.subscribe('detection_event', handleNewDetection);
      websocketService.subscribe('session_completed', handleSessionCompleted);

    } catch (error) {
      console.error('Failed to load HIL results:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  // Calculate overall test status
  const testPassed = useMemo(() => {
    if (!enhancedResults) return false;

    // Backend determines pass/fail, not frontend
    const failedDetections = enhancedResults.detectionStatistics?.correctedResults?.failed || 0;
    return failedDetections === 0;
  }, [enhancedResults]);

  // Get metrics for display
  const gtComparison = enhancedResults?.groundTruthComparison;
  const precision = gtComparison?.precision ?? 0;
  const recall = gtComparison?.recall ?? 0;
  const f1Score = gtComparison?.f1Score ?? 0;
  const truePositives = gtComparison?.truePositives ?? 0;
  const falsePositives = gtComparison?.falsePositives ?? 0;
  const falseNegatives = gtComparison?.falseNegatives ?? 0;

  // Get per-video metrics if multi-video sequence
  const currentVideoMetrics = useMemo(() => {
    if (!enhancedResults?.perVideoResults || !selectedVideoId) {
      return null;
    }

    return enhancedResults.perVideoResults.find(v => v.videoId === selectedVideoId);
  }, [enhancedResults, selectedVideoId]);

  // Aggregate metrics for multi-video sequences
  const aggregatedMetrics = useMemo(() => {
    if (!enhancedResults?.perVideoResults || enhancedResults.perVideoResults.length <= 1) {
      return null;
    }

    const videos = enhancedResults.perVideoResults;
    const totalTP = videos.reduce((sum, v) => sum + (v.groundTruthComparison?.truePositives ?? 0), 0);
    const totalFP = videos.reduce((sum, v) => sum + (v.groundTruthComparison?.falsePositives ?? 0), 0);
    const totalFN = videos.reduce((sum, v) => sum + (v.groundTruthComparison?.falseNegatives ?? 0), 0);

    const precision = totalTP / (totalTP + totalFP);
    const recall = totalTP / (totalTP + totalFN);
    const f1 = 2 * precision * recall / (precision + recall);

    // Weighted average latency
    const totalLatency = videos.reduce((sum, v) => {
      const detections = v.detectionCount ?? 0;
      const latency = v.meanLatencyMs ?? 0;
      return sum + (detections * latency);
    }, 0);
    const totalDetections = videos.reduce((sum, v) => sum + (v.detectionCount ?? 0), 0);
    const avgLatency = totalDetections > 0 ? totalLatency / totalDetections : 0;

    return {
      truePositives: totalTP,
      falsePositives: totalFP,
      falseNegatives: totalFN,
      precision,
      recall,
      f1Score: f1,
      meanLatencyMs: avgLatency
    };
  }, [enhancedResults]);

  return (
    <Container maxWidth="xl">
      {/* Test Status Banner */}
      <TestStatusBanner
        passed={testPassed}
        sessionId={sessionId}
      />

      {/* Video Selector (for multi-video sequences) */}
      {enhancedResults?.perVideoResults && enhancedResults.perVideoResults.length > 1 && (
        <VideoSequenceSelector
          videos={enhancedResults.perVideoResults}
          selectedVideoId={selectedVideoId}
          onVideoSelect={setSelectedVideoId}
        />
      )}

      {/* Metrics Summary Cards */}
      <MetricsSummaryCards
        totalDetections={enhancedResults?.detectionEvents?.length ?? 0}
        meanLatency={currentVideoMetrics?.meanLatencyMs ?? aggregatedMetrics?.meanLatencyMs ?? 0}
        passRate={precision * 100}
      />

      {/* Ground Truth Comparison Cards */}
      <GroundTruthComparisonCards
        truePositives={currentVideoMetrics?.groundTruthComparison?.truePositives ?? truePositives}
        falsePositives={currentVideoMetrics?.groundTruthComparison?.falsePositives ?? falsePositives}
        falseNegatives={currentVideoMetrics?.groundTruthComparison?.falseNegatives ?? falseNegatives}
        precision={currentVideoMetrics?.groundTruthComparison?.precision ?? precision}
        recall={currentVideoMetrics?.groundTruthComparison?.recall ?? recall}
        f1Score={currentVideoMetrics?.groundTruthComparison?.f1Score ?? f1Score}
      />

      {/* Detection Timeline */}
      <FrameCorrelationTimeline
        detections={filteredDetections}
        groundTruthObjects={groundTruthData}
        videoId={selectedVideoId}
      />

      {/* Detection Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Timestamp</TableCell>
              <TableCell>Classification</TableCell>
              <TableCell>Latency (ms)</TableCell>
              <TableCell>Voltage</TableCell>
              <TableCell>Screenshot</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredDetections.map(detection => (
              <DetectionTableRow
                key={detection.id}
                detection={detection}
                onClick={() => handleDetectionClick(detection)}
              />
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
};
```

**UI Components Breakdown:**

1. **TestStatusBanner** (`TestStatusBanner.tsx`):
   - Large PASS/FAIL indicator
   - Color-coded (green=pass, red=fail)
   - Based on `testPassed` boolean from backend data

2. **MetricsSummaryCards** (`MetricsSummaryCards.tsx`):
   - Total detections count
   - Mean latency
   - Pass rate (precision percentage)
   - Displayed as Material-UI Cards in a grid

3. **GroundTruthComparisonCards** (`GroundTruthComparisonCards.tsx`):
   - True Positives, False Positives, False Negatives
   - Precision, Recall, F1 Score
   - Color-coded bars and charts

4. **FrameCorrelationTimeline** (`FrameCorrelationTimeline.tsx`):
   - Visual timeline showing detections vs ground truth
   - TP in green, FP in red, FN in yellow
   - Interactive hover for details

5. **DetectionTableRow** (`DetectionTableRow.tsx`):
   - Individual detection row
   - Shows timestamp, classification, latency, voltage
   - Screenshot thumbnail (if available)
   - Click to view full screenshot

**Filtering for Multi-Video:**

```typescript
const filteredDetections = useMemo(() => {
  if (!enhancedResults?.detectionEvents) return [];

  if (selectedVideoId) {
    return enhancedResults.detectionEvents.filter(d => d.videoId === selectedVideoId);
  }

  return enhancedResults.detectionEvents;
}, [enhancedResults, selectedVideoId]);
```

---

## Backend Approval Workflow

### Pre-Session Validation

**Endpoint:** `POST /api/test-sessions/validate-ground-truth`
**Purpose:** Ensures all videos have ground truth data before test starts

```python
# Location: backend/routers/test_sessions.py (Lines 145-234)
@router.post("/validate-ground-truth", response_model=GTValidationResponse)
def validate_ground_truth(request: GTValidationRequest, db: Session = Depends(get_db)):
    """
    Validates that all videos have ground truth objects before test execution.

    Uses single optimized query to prevent N+1 issues.
    """
    video_ids = request.video_ids

    # Single GROUP BY query to get GT counts per video
    gt_counts = db.query(
        GroundTruthObject.video_id,
        func.count(GroundTruthObject.id).label('gt_count')
    ).filter(
        GroundTruthObject.video_id.in_(video_ids),
        GroundTruthObject.soft_deleted == False
    ).group_by(GroundTruthObject.video_id).all()

    gt_count_map = {video_id: count for video_id, count in gt_counts}

    # Build validation response
    per_video_validation = []
    all_valid = True

    for video_id in video_ids:
        gt_count = gt_count_map.get(video_id, 0)
        is_valid = gt_count > 0

        per_video_validation.append({
            'video_id': video_id,
            'ground_truth_count': gt_count,
            'is_valid': is_valid,
            'message': 'Valid' if is_valid else 'No ground truth objects found'
        })

        if not is_valid:
            all_valid = False

    return GTValidationResponse(
        overall_valid=all_valid,
        per_video_validation=per_video_validation
    )
```

**Frontend Usage:**

```typescript
// Before starting test, validate GT exists
const validation = await validateGroundTruth(videoIds);
if (!validation.overallValid) {
  showError('Some videos missing ground truth data');
  return;
}
```

---

### Session Lifecycle States

```
CREATED → RUNNING → COMPLETED
  ↓         ↓           ↓
  |    (detections)   (validation)
  |                     ↓
  └──────────→  VALIDATION_FAILED
```

**State Transitions:**

1. **CREATED:** Session initialized, no detections yet
2. **RUNNING:** Test executing, detections being recorded
3. **COMPLETED:** All videos finished, GT matching done, metrics calculated
4. **VALIDATION_FAILED:** Session completion validation failed (missing timing data)

---

### Pass/Fail Determination Logic

**Session-Level:**

```python
# Location: backend/services/ground_truth_matching_service.py (Lines 1234-1289)
def determine_session_status(metrics: SessionMetrics) -> str:
    """
    Determines overall session pass/fail status based on thresholds.

    Thresholds:
    - PASS: Precision >= 0.8 AND Recall >= 0.75 AND Avg Latency <= 100ms
    - CONDITIONAL_PASS: Precision >= 0.6 OR Recall >= 0.6 (with latency criteria)
    - FAIL: Below thresholds
    """
    precision = metrics.precision
    recall = metrics.recall
    mean_latency = metrics.mean_latency_ms

    # Strict pass criteria
    if precision >= 0.8 and recall >= 0.75 and mean_latency <= 100:
        return "PASS"

    # Conditional pass criteria
    if (precision >= 0.6 or recall >= 0.6) and mean_latency <= 150:
        return "CONDITIONAL_PASS"

    # Fail
    return "FAIL"
```

**Detection-Level:**

```python
def classify_detection(detection, ground_truth_objects, tolerance_ms=100):
    """
    Classifies individual detection as TP or FP.

    Rules:
    - TRUE_POSITIVE: Matched to GT within tolerance window
    - FALSE_POSITIVE: No matching GT object found
    """
    nearest_gt = find_nearest_gt(detection, ground_truth_objects)

    if nearest_gt:
        time_diff_ms = abs(detection.timestamp - nearest_gt.timestamp) * 1000

        if time_diff_ms <= tolerance_ms:
            return "TP", nearest_gt.id, time_diff_ms

    return "FP", None, None
```

**Ground Truth Object Classification:**

```python
def classify_ground_truth(gt_object, detections, tolerance_ms=100):
    """
    Classifies GT object as matched (TP contributor) or unmatched (FN).

    Rules:
    - If GT matched to detection: contributes to TP count
    - If GT unmatched: classified as FALSE_NEGATIVE
    """
    nearest_detection = find_nearest_detection(gt_object, detections)

    if nearest_detection:
        time_diff_ms = abs(gt_object.timestamp - nearest_detection.timestamp) * 1000

        if time_diff_ms <= tolerance_ms:
            return "MATCHED"  # Contributes to TP

    return "FN"
```

---

## Frontend Results Display Logic

### Component Architecture

```
HILResults.tsx (main page)
  ├── TestStatusBanner (PASS/FAIL indicator)
  ├── VideoSequenceSelector (multi-video tabs)
  ├── MetricsSummaryCards (detections, latency, pass rate)
  ├── GroundTruthComparisonCards (TP/FP/FN, P/R/F1)
  ├── FrameCorrelationTimeline (visual timeline)
  └── Detection Table (detailed detection list)
```

### Data Fetching Flow

```typescript
// Location: frontend/src/pages/HILResults.tsx (Lines 156-289)
async function loadHILResults() {
  try {
    // Step 1: Fetch enhanced results
    const results = await getEnhancedHILResultsWithGroundTruth(sessionId);
    setEnhancedResults(results);

    // Step 2: Load per-video detections (if multi-video)
    if (results.perVideoResults && results.perVideoResults.length > 0) {
      for (const videoResult of results.perVideoResults) {
        const detections = await getDetectionEvents(sessionId, videoResult.videoId);
        setDetectionsByVideo(prev => ({
          ...prev,
          [videoResult.videoId]: detections
        }));
      }
    }

    // Step 3: Load ground truth objects for comparison
    const videoIds = results.perVideoResults?.map(v => v.videoId) || [results.videoId];
    for (const videoId of videoIds) {
      const gtObjects = await getGroundTruthEvents(videoId);
      setGroundTruthByVideo(prev => ({
        ...prev,
        [videoId]: gtObjects
      }));
    }

  } catch (error) {
    console.error('Failed to load results:', error);
    setError(error.message);
  }
}
```

### Pass/Fail Display Logic

**Overall Test Status:**

```typescript
// Location: frontend/src/pages/HILResults.tsx (Lines 1281-1288)
const testPassed = useMemo(() => {
  if (!enhancedResults) return false;

  // Uses backend-calculated pass/fail from corrected_results
  const failedDetections = enhancedResults.detectionStatistics?.correctedResults?.failed || 0;
  return failedDetections === 0;
}, [enhancedResults]);

// UI Display
<TestStatusBanner
  passed={testPassed}
  sessionId={sessionId}
/>
```

**TestStatusBanner Component:**

```typescript
// Location: frontend/src/components/TestStatusBanner.tsx
export const TestStatusBanner: React.FC<{ passed: boolean; sessionId: string }> = ({
  passed,
  sessionId
}) => {
  return (
    <Box sx={{
      bgcolor: passed ? 'success.main' : 'error.main',
      color: 'white',
      p: 3,
      borderRadius: 2,
      mb: 3
    }}>
      <Typography variant="h3" align="center">
        Test {passed ? 'PASSED' : 'FAILED'}
      </Typography>
      <Typography variant="body1" align="center">
        Session ID: {sessionId}
      </Typography>
    </Box>
  );
};
```

### Metrics Display

**Ground Truth Comparison Cards:**

```typescript
// Location: frontend/src/components/GroundTruthComparisonCards.tsx
export const GroundTruthComparisonCards: React.FC<GTComparisonProps> = ({
  truePositives,
  falsePositives,
  falseNegatives,
  precision,
  recall,
  f1Score
}) => {
  return (
    <Grid container spacing={3}>
      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6">True Positives</Typography>
            <Typography variant="h3" color="success.main">{truePositives}</Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6">False Positives</Typography>
            <Typography variant="h3" color="error.main">{falsePositives}</Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6">False Negatives</Typography>
            <Typography variant="h3" color="warning.main">{falseNegatives}</Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6">Precision</Typography>
            <Typography variant="h3">{(precision * 100).toFixed(1)}%</Typography>
            <LinearProgress
              variant="determinate"
              value={precision * 100}
              color="primary"
            />
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6">Recall</Typography>
            <Typography variant="h3">{(recall * 100).toFixed(1)}%</Typography>
            <LinearProgress
              variant="determinate"
              value={recall * 100}
              color="primary"
            />
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Typography variant="h6">F1 Score</Typography>
            <Typography variant="h3">{(f1Score * 100).toFixed(1)}%</Typography>
            <LinearProgress
              variant="determinate"
              value={f1Score * 100}
              color="primary"
            />
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};
```

**All metrics come from backend API—frontend never recalculates.**

---

### ⚠️ Deprecated Frontend Calculation (SHOULD BE REMOVED)

**Location:** `frontend/src/pages/HILResults.tsx` Lines 106-188

```typescript
// ❌ DEPRECATED: This function uses WRONG field and produces incorrect metrics
function createMetricsFromDetections(
  detections: DetectionEvent[],
  groundTruthObjects: GroundTruthObject[]
): GroundTruthComparison {
  // WRONG: Uses validation_result field instead of classification
  const truePositives = detections.filter(d => d.validation_result === "PASS").length;
  const falsePositives = detections.filter(d => d.validation_result === "FAIL").length;

  // WRONG: Doesn't account for unmatched GT objects
  const falseNegatives = 0;  // Should be: groundTruthObjects.length - matched_gt_count

  // WRONG: Precision/Recall calculations produce incorrect results
  const precision = truePositives / (truePositives + falsePositives);
  const recall = truePositives / groundTruthObjects.length;  // Incorrect denominator

  return { truePositives, falsePositives, falseNegatives, precision, recall };
}
```

**Why This Is Wrong:**

1. **Wrong Field:** Uses `validation_result` (latency validation) instead of `classification` (GT matching)
2. **Incorrect FN Count:** Sets FN=0 instead of counting unmatched GT objects
3. **Wrong Recall Formula:** Divides by total GT instead of (TP + FN)
4. **Not Used:** Function exists but is not called in production code

**Recommendation:** **DELETE this function entirely** to prevent accidental use.

---

### Multi-Video Aggregation

**Per-Video Metrics:**

```typescript
// Location: frontend/src/pages/HILResults.tsx (Lines 998-1048)
const currentVideoMetrics = useMemo(() => {
  if (!enhancedResults?.perVideoResults || !selectedVideoId) {
    return null;
  }

  // Find metrics for selected video
  const videoResult = enhancedResults.perVideoResults.find(
    v => v.videoId === selectedVideoId
  );

  return videoResult?.groundTruthComparison;
}, [enhancedResults, selectedVideoId]);
```

**Aggregated Sequence Metrics:**

```typescript
// Location: frontend/src/pages/HILResults.tsx (Lines 1050-1121)
const aggregatedMetrics = useMemo(() => {
  if (!enhancedResults?.perVideoResults || enhancedResults.perVideoResults.length <= 1) {
    return null;
  }

  const videos = enhancedResults.perVideoResults;

  // Sum TP/FP/FN across all videos
  const totalTP = videos.reduce((sum, v) =>
    sum + (v.groundTruthComparison?.truePositives ?? 0), 0);
  const totalFP = videos.reduce((sum, v) =>
    sum + (v.groundTruthComparison?.falsePositives ?? 0), 0);
  const totalFN = videos.reduce((sum, v) =>
    sum + (v.groundTruthComparison?.falseNegatives ?? 0), 0);

  // Recalculate precision/recall from aggregated counts
  const precision = totalTP / (totalTP + totalFP);
  const recall = totalTP / (totalTP + totalFN);
  const f1 = 2 * precision * recall / (precision + recall);

  // Weighted average latency (by detection count)
  const totalLatency = videos.reduce((sum, v) => {
    const detectionCount = v.detectionCount ?? 0;
    const meanLatency = v.meanLatencyMs ?? 0;
    return sum + (detectionCount * meanLatency);
  }, 0);
  const totalDetections = videos.reduce((sum, v) =>
    sum + (v.detectionCount ?? 0), 0);
  const weightedAvgLatency = totalDetections > 0
    ? totalLatency / totalDetections
    : 0;

  return {
    truePositives: totalTP,
    falsePositives: totalFP,
    falseNegatives: totalFN,
    precision,
    recall,
    f1Score: f1,
    meanLatencyMs: weightedAvgLatency
  };
}, [enhancedResults]);
```

**Example Aggregation:**

```
Video 1: TP=18, FP=2, FN=6, Mean Latency=23.2ms, Detections=20
Video 2: TP=22, FP=0, FN=2, Mean Latency=25.8ms, Detections=22
Video 3: TP=16, FP=2, FN=8, Mean Latency=28.5ms, Detections=18

Aggregated:
  Total TP = 56
  Total FP = 4
  Total FN = 16
  Precision = 56/(56+4) = 93.3%
  Recall = 56/(56+16) = 77.8%
  F1 = 2×(0.933×0.778)/(0.933+0.778) = 84.7%
  Weighted Avg Latency = (20×23.2 + 22×25.8 + 18×28.5) / (20+22+18) = 25.7ms
```

---

## Pass/Fail Determination Rules

### Session-Level Thresholds

**PASS Criteria:**
```python
Precision >= 0.8  (80%)
AND
Recall >= 0.75    (75%)
AND
Mean Latency <= 100ms
```

**CONDITIONAL_PASS Criteria:**
```python
(Precision >= 0.6 OR Recall >= 0.6)
AND
Mean Latency <= 150ms
```

**FAIL Criteria:**
```python
Everything below CONDITIONAL_PASS thresholds
```

### Detection-Level Classification

**TRUE_POSITIVE (TP):**
```python
Detection matched to GT object
AND
|detection_timestamp - gt_timestamp| <= tolerance_ms (default 100ms)
AND
Same video_id (video boundary protection)
```

**FALSE_POSITIVE (FP):**
```python
Detection has NO matching GT object within tolerance window
OR
Detection from different video_id than GT
```

**FALSE_NEGATIVE (FN):**
```python
GT object has NO matching detection within tolerance window
```

### Latency Validation

**PASS Threshold:**
```python
latency_ms <= 50ms
```

**FAIL Threshold:**
```python
50ms < latency_ms <= 5000ms
```

**TIMEOUT:**
```python
latency_ms > 5000ms
```

**ERROR:**
```python
latency_ms < 0  (negative latency indicates timing bug)
```

---

## Metrics Calculation Formulas

### Classification Metrics

**Precision:**
```
Precision = TP / (TP + FP)
```
- Measures: "Of all detections, how many were correct?"
- Range: 0.0 to 1.0 (or 0% to 100%)
- Example: 18 TP, 4 FP → 18/(18+4) = 0.818 = 81.8%

**Recall:**
```
Recall = TP / (TP + FN)
```
- Measures: "Of all ground truth objects, how many were detected?"
- Range: 0.0 to 1.0 (or 0% to 100%)
- Example: 18 TP, 6 FN → 18/(18+6) = 0.750 = 75.0%

**F1 Score:**
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```
- Measures: Harmonic mean balancing precision and recall
- Range: 0.0 to 1.0 (or 0% to 100%)
- Example: Precision=0.818, Recall=0.750 → 2×(0.818×0.750)/(0.818+0.750) = 0.783 = 78.3%

**Accuracy (optional):**
```
Accuracy = TP / (TP + FP + FN)
```
- Measures: Overall correctness
- Example: 18/(18+4+6) = 0.643 = 64.3%

### Latency Metrics

**Mean Latency:**
```
Mean = Σ(latencies) / count(latencies)
```
- **CRITICAL:** Only first 10 TP per video are used
- Example: [23.0, 25.0, 22.0, 24.0] → (23+25+22+24)/4 = 23.5ms

**Standard Deviation:**
```
Std Dev = √(Σ(x - mean)² / (n - 1))
```
- Example: latencies=[23, 25, 22, 24], mean=23.5 → std=1.29ms

**Within Tolerance Percentage:**
```
Within Tolerance % = (count(latencies <= 100ms) / total_latencies) × 100
```
- Example: 18 latencies ≤ 100ms out of 18 total → 100%

### Capture Rate

**Definition:**
```
Capture Rate = (TP / Total Ground Truth Objects) × 100
```
- Same as Recall percentage
- Example: 18 TP, 24 GT objects → (18/24)×100 = 75.0%

---

## Ground Truth Matching Algorithm

### Phase 1: Match GT to Detections

**Pseudocode:**

```python
for each ground_truth_object in ground_truth_objects:
    best_match = None
    min_time_diff = infinity

    for each detection in detections:
        # Video boundary protection
        if detection.video_id != ground_truth_object.video_id:
            continue

        time_diff_ms = abs(detection.timestamp - ground_truth_object.timestamp) * 1000

        if time_diff_ms <= tolerance_ms and time_diff_ms < min_time_diff:
            best_match = detection
            min_time_diff = time_diff_ms

    if best_match:
        # TRUE POSITIVE
        mark_as_TP(detection=best_match, gt=ground_truth_object, latency=min_time_diff)
        matched_detections.add(best_match.id)
    else:
        # FALSE NEGATIVE
        mark_as_FN(gt=ground_truth_object)
```

### Phase 2: Classify Remaining Detections

**Pseudocode:**

```python
for each detection in detections:
    if detection.id not in matched_detections:
        # FALSE POSITIVE
        mark_as_FP(detection=detection)
```

### Temporal IoU Calculation

**Formula:**
```
Temporal IoU = 1.0 - (time_difference_ms / tolerance_ms)
```

**Example:**
```
Tolerance = 100ms
Time difference = 23ms
Temporal IoU = 1.0 - (23/100) = 0.77 (77% match quality)
```

**Interpretation:**
- 1.0 = Perfect match (exact timestamp)
- 0.5 = Moderate match (50ms difference)
- 0.0 = At tolerance boundary (100ms difference)

---

## Validation Thresholds

### Temporal Matching

| Parameter | Default Value | Strict Mode | Relaxed Mode |
|-----------|---------------|-------------|--------------|
| Tolerance Window | 100ms | 50ms | 200ms |
| Video Boundary | Required | Required | Required |
| Temporal IoU Min | 0.0 | 0.5 | 0.0 |

### Latency Validation

| Status | Threshold | Action |
|--------|-----------|--------|
| PASS | ≤ 50ms | Accept detection |
| FAIL | > 50ms and ≤ 5000ms | Flag for review |
| TIMEOUT | > 5000ms | Mark as timeout |
| ERROR | < 0ms | Investigate timing bug |

### Performance Metrics

| Metric | Excellent | Good | Acceptable | Poor |
|--------|-----------|------|------------|------|
| Precision | ≥ 90% | ≥ 80% | ≥ 60% | < 60% |
| Recall | ≥ 90% | ≥ 75% | ≥ 60% | < 60% |
| F1 Score | ≥ 90% | ≥ 78% | ≥ 60% | < 60% |
| Mean Latency | ≤ 30ms | ≤ 50ms | ≤ 100ms | > 100ms |

### Video Validation

| Parameter | Min | Max | Typical | Warning |
|-----------|-----|-----|---------|---------|
| Duration | 0s | 7200s (2 hours) | 30-120s | > 600s |
| FPS | 15 | 120 | 24-60 | < 20 or > 90 |
| Resolution Width | > 0 | - | 640-1920 | < 320 |
| Resolution Height | > 0 | - | 480-1080 | < 240 |

### Timestamp Validation

| Check | Rule | Error Level |
|-------|------|-------------|
| Video-Relative | timestamp_ms ≥ 0 | CRITICAL |
| Video Duration | timestamp_ms < video_duration_ms | CRITICAL |
| Drift Tolerance | abs(expected - actual) < 100ms | WARNING |
| Drift Critical | abs(expected - actual) < 1000ms | CRITICAL |

---

## Multi-Video Sequence Handling

### Sequence Metadata Structure

```json
{
  "video_timing": {
    "video-001": {
      "start_time": 1234567890.123456,  // T1 timestamp
      "cumulative_offset_ms": 0,
      "expected_duration_ms": 30000,
      "actual_duration_ms": 30234
    },
    "video-002": {
      "start_time": 1234567920.357890,
      "cumulative_offset_ms": 30234,  // Uses actual_duration from video-001
      "expected_duration_ms": 30000,
      "actual_duration_ms": 29987
    },
    "video-003": {
      "start_time": 1234567950.344780,
      "cumulative_offset_ms": 60221,  // 30234 + 29987
      "expected_duration_ms": 30000,
      "actual_duration_ms": 30102
    }
  }
}
```

### Cumulative Offset Calculation

**Algorithm:**

```python
def calculate_cumulative_offset(sequence_id, current_position):
    """
    Calculates cumulative offset for video at given position.
    Uses actual_duration_ms from previous videos.
    """
    previous_videos = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.sequence_id == sequence_id,
        SequenceVideoResult.position < current_position
    ).order_by(SequenceVideoResult.position).all()

    cumulative_offset_ms = 0
    for video in previous_videos:
        # CRITICAL: Use actual_duration_ms, not expected_duration_ms
        # actual_duration_ms is set when video ends (onEnded event)
        if video.actual_duration_ms is not None:
            cumulative_offset_ms += video.actual_duration_ms
        else:
            # Fallback to expected if video hasn't ended yet
            cumulative_offset_ms += video.expected_duration_ms

    return cumulative_offset_ms
```

**Example:**

```
Video 1: Expected 30000ms, Actual 30234ms
Video 2: Expected 30000ms, Actual 29987ms
Video 3: Expected 30000ms, Actual 30102ms

Offsets:
  Video 1: 0ms (no previous videos)
  Video 2: 30234ms (actual duration of Video 1)
  Video 3: 60221ms (30234 + 29987)
```

### Video Boundary Protection

**Purpose:** Prevent detections from matching GT objects in different videos

**Implementation:**

```python
# In temporal matching algorithm
for gt_object in ground_truth_objects:
    for detection in detections:
        # CRITICAL CHECK: Same video_id required
        if detection.video_id != gt_object.video_id:
            continue  # Skip this detection

        # Proceed with temporal matching
        time_diff = abs(detection.timestamp - gt_object.timestamp)
        if time_diff <= tolerance:
            match = True
```

**Without This Protection:**

```
Video 1 GT @ 29.5s could match Video 2 Detection @ 0.5s
(because 0.5s in Video 2 = 30.5s absolute time)
```

**With This Protection:**

```
Video 1 GT @ 29.5s CANNOT match Video 2 Detection @ 0.5s
(video_id mismatch prevents match)
```

### Per-Video Metrics Calculation

**Algorithm:**

```python
def calculate_per_video_metrics(session_id, video_id):
    """
    Calculates metrics for a single video in a multi-video sequence.
    """
    # Get detections for this video only
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.session_id == session_id,
        DetectionEvent.video_id == video_id
    ).all()

    # Get GT objects for this video only
    gt_objects = db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id == video_id
    ).all()

    # Run matching algorithm on video subset
    tp_count = 0
    fp_count = 0
    fn_count = 0
    latencies = []

    matched_detection_ids = set()

    for gt in gt_objects:
        best_match = find_nearest_detection(gt, detections, tolerance_ms=100)
        if best_match:
            tp_count += 1
            latencies.append(best_match.latency_ms)
            matched_detection_ids.add(best_match.id)
        else:
            fn_count += 1

    for detection in detections:
        if detection.id not in matched_detection_ids:
            fp_count += 1

    # Calculate metrics
    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0
    recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    mean_latency = np.mean(latencies[:10]) if latencies else None  # First 10 TP

    return {
        'video_id': video_id,
        'true_positives': tp_count,
        'false_positives': fp_count,
        'false_negatives': fn_count,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'mean_latency_ms': mean_latency
    }
```

### Sequence Metrics Aggregation

**Algorithm:**

```python
def calculate_sequence_metrics(session_id):
    """
    Aggregates metrics across all videos in sequence.
    """
    video_results = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.sequence_id == session.sequence_id
    ).all()

    # Aggregate counts
    total_tp = sum(v.true_positives for v in video_results)
    total_fp = sum(v.false_positives for v in video_results)
    total_fn = sum(v.false_negatives for v in video_results)

    # Recalculate from aggregated counts (NOT average of percentages)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # Weighted average latency
    total_latency_weighted = 0
    total_detections = 0

    for video in video_results:
        if video.mean_latency_ms is not None:
            total_latency_weighted += video.detection_count * video.mean_latency_ms
            total_detections += video.detection_count

    mean_latency = total_latency_weighted / total_detections if total_detections > 0 else None

    return {
        'true_positives': total_tp,
        'false_positives': total_fp,
        'false_negatives': total_fn,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'mean_latency_ms': mean_latency
    }
```

---

## Critical Issues and Recommendations

### 1. No Formal Approval Workflow

**Current State:**
- Frontend displays results but has NO approve/reject buttons
- No approval status stored in database
- No approval timestamp or approver tracking
- Users can view results and navigate away, but no formal sign-off

**Recommendation:**

Add approval workflow to `HILResults.tsx`:

```typescript
// Add approval state
const [approvalStatus, setApprovalStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');

// Add approval handler
async function handleApprove() {
  try {
    await approveTestSession(sessionId, {
      approver: currentUser.id,
      comments: approvalComments,
      timestamp: new Date().toISOString()
    });
    setApprovalStatus('approved');
    showSuccess('Test session approved');
  } catch (error) {
    showError('Failed to approve session');
  }
}

// Add UI buttons
<Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
  <Button
    variant="contained"
    color="success"
    onClick={handleApprove}
    disabled={approvalStatus !== 'pending'}
  >
    Approve Results
  </Button>
  <Button
    variant="contained"
    color="error"
    onClick={handleReject}
    disabled={approvalStatus !== 'pending'}
  >
    Reject Results
  </Button>
</Box>
```

**Backend Changes:**

```python
# Add to models.py
class TestSession(Base):
    # ... existing fields ...
    approval_status = Column(String, default='pending')  # pending/approved/rejected
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_comments = Column(Text, nullable=True)

# Add endpoint to routers/test_sessions.py
@router.post("/{session_id}/approve")
def approve_session(
    session_id: str,
    approval: ApprovalRequest,
    db: Session = Depends(get_db)
):
    session = db.query(TestSession).get(session_id)
    session.approval_status = 'approved'
    session.approved_by = approval.approver_id
    session.approved_at = datetime.utcnow()
    session.approval_comments = approval.comments
    db.commit()
    return {"status": "approved"}
```

---

### 2. Deprecated Frontend Calculation

**Issue:** `createMetricsFromDetections()` function in `HILResults.tsx` (Lines 106-188) uses wrong fields and produces incorrect metrics.

**Recommendation:** **DELETE this function immediately.**

```diff
- function createMetricsFromDetections(
-   detections: DetectionEvent[],
-   groundTruthObjects: GroundTruthObject[]
- ): GroundTruthComparison {
-   // Wrong calculations...
- }
```

**Rationale:**
- Function is not used in production code
- Uses `validation_result` instead of `classification`
- Produces incorrect metrics (0% recall instead of 75%)
- Risk of accidental use in future

---

### 3. Schema Inconsistency

**Issue:** Mixed snake_case and camelCase field names between backend and frontend

**Current State:**
```typescript
// Backend returns both formats
{
  "ground_truth_comparison": { ... },
  "groundTruthComparison": { ... }
}
```

**Recommendation:** Standardize on camelCase for all API responses

```python
# Use Pydantic models with alias_generator
class EnhancedHILResultsResponse(BaseModel):
    session_id: str = Field(alias='sessionId')
    ground_truth_comparison: GroundTruthComparison = Field(alias='groundTruthComparison')

    class Config:
        populate_by_name = True
        alias_generator = to_camel
```

---

### 4. Timing Validation Critical

**Issue:** Session completion MUST validate video lifecycle events to prevent NULL timestamp bugs

**Current Protection:**

```python
# session_completion_service.py validates:
- All videos have started_at timestamp
- All videos have ended_at timestamp
- All videos have actual_duration_ms
- sequence_metadata.video_timing exists
```

**Recommendation:** Keep this validation MANDATORY. It prevents:
- LabJack detections with NULL video_id
- Incorrect cumulative offset calculations
- Corrupted multi-video sequence data

---

### 5. First-10-Per-Video Latency Sampling

**Issue:** Without this, later videos in sequence show artificially low latency due to GT depletion

**Current Implementation:** ✅ CORRECT

```python
# Takes first 10 TP per video
for video_id in video_ids:
    video_latencies = get_tp_latencies(video_id, limit=10)
    latencies.extend(video_latencies)
```

**Recommendation:** Keep this implementation. Do NOT change to "all TP latencies."

---

### 6. Video Boundary Protection

**Issue:** Without video_id checking, GT objects from one video could match detections from another

**Current Implementation:** ✅ CORRECT

```python
if detection.video_id != gt_object.video_id:
    continue  # Skip
```

**Recommendation:** Keep this check MANDATORY in matching algorithm.

---

## Summary

### Data Flow: Test to Display

```
1. LabJack Hardware Detection (T_detection)
   ↓
2. DetectionEvent Storage (video_id assignment)
   ↓
3. Session Completion Validation (timing checks)
   ↓
4. Ground Truth Matching (TP/FP/FN classification)
   ↓
5. Metrics Calculation (Precision, Recall, F1, Latency)
   ↓
6. Database Storage (DetectionComparison, SessionMetrics)
   ↓
7. API Response (Enhanced Results Endpoint)
   ↓
8. Frontend Display (HILResults.tsx UI Components)
```

### Pass/Fail Logic

**Backend Determines:**
- TP/FP/FN classification via temporal matching
- Precision, Recall, F1 Score formulas
- Mean latency (first 10 TP per video)
- Session pass/fail status (based on thresholds)

**Frontend Displays:**
- Metrics from backend API (never recalculates)
- TestStatusBanner (PASS/FAIL indicator)
- GroundTruthComparisonCards (TP/FP/FN, P/R/F1)
- Detection table with classifications

### Critical Files

**Backend:**
- `ground_truth_matching_service.py` - Temporal matching algorithm
- `session_completion_service.py` - Validation and completion logic
- `video_sequence_orchestrator.py` - Multi-video coordination
- `enhanced_hil_results_endpoints.py` - Results API

**Frontend:**
- `HILResults.tsx` - Main results page
- `GroundTruthComparisonCards.tsx` - Metrics display
- `TestStatusBanner.tsx` - PASS/FAIL indicator
- `hilResultsNormalization.ts` - Data normalization

### Recommendations Priority

1. **HIGH:** Add formal approval workflow (approve/reject buttons + backend persistence)
2. **HIGH:** Delete deprecated `createMetricsFromDetections()` function
3. **MEDIUM:** Standardize API schema to camelCase only
4. **LOW:** Document timing validation requirements for frontend developers

---

**Document Generated:** Based on 6-agent parallel analysis
**Session ID:** a90187aa-2237-4afe-90d5-3c8176db622f
**Agents:** Explore, Code Analyzer, Backend Dev, System Architect, Tester, Researcher
**Total Analysis Time:** ~45 seconds (parallel execution)
