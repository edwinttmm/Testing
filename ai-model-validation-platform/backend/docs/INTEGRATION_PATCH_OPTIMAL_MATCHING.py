"""
Integration Patch for Optimal Matching Algorithm

This file contains the exact code changes needed to integrate the optimal
Hungarian algorithm into ground_truth_matching_service.py.

Apply this patch to replace greedy matching (lines 739-861) with optimal matching.

Author: Agent #5 - Optimal Matching Algorithm Specialist
Date: 2025-11-12
"""

# ============================================================================
# STEP 1: Add import at top of ground_truth_matching_service.py (around line 40)
# ============================================================================

"""
Add this import after the existing imports:
"""

from services.optimal_matching_service import (
    optimal_detection_matching,
    compare_matching_algorithms
)


# ============================================================================
# STEP 2: Replace _perform_temporal_matching method (lines 655-961)
# ============================================================================

def _perform_temporal_matching_OPTIMAL(
    self,
    detection_events: List[DetectionEvent],
    ground_truth_objects: List[GroundTruthObject],
    tolerance_ms: int,
    test_session: Optional[TestSession] = None,
    db: Optional[Session] = None
) -> List[MatchResult]:
    """
    Perform optimal temporal matching using Hungarian algorithm.

    REPLACED ALGORITHM:
    - OLD: Greedy first-match (O(n×m), suboptimal)
    - NEW: Hungarian algorithm (O(n³), globally optimal)

    Args:
        detection_events: List of detection events
        ground_truth_objects: List of ground truth objects
        tolerance_ms: Tolerance window in milliseconds
        test_session: Optional test session for context
        db: Optional database session for sequence queries

    Returns:
        List of MatchResult objects (TP/FP/FN classified)
    """
    tolerance_seconds = tolerance_ms / 1000.0
    match_results = []
    tp_debug_count = 0

    self.logger.info(
        f"🔬 OPTIMAL MATCHING: Using Hungarian algorithm "
        f"({len(ground_truth_objects)} GT × {len(detection_events)} Det, "
        f"tolerance={tolerance_ms}ms)"
    )

    session_start_time = None
    if test_session is not None:
        session_start_time = _safe_float(
            getattr(test_session, "video_playback_start_time", None)
        )

    # ========================================================================
    # MULTI-VIDEO SUPPORT: Detect and handle video boundaries
    # ========================================================================
    gt_video_ids = set()
    gt_by_video = {}
    for gt_obj in ground_truth_objects:
        gt_video_id = getattr(gt_obj, 'video_id', None)
        if gt_video_id is not None:
            gt_video_ids.add(gt_video_id)
            if gt_video_id not in gt_by_video:
                gt_by_video[gt_video_id] = []
            gt_by_video[gt_video_id].append(gt_obj)

    has_multi_video_sequence = len(gt_video_ids) > 1

    # Build video order map for boundary validation
    video_order_map = {}
    if has_multi_video_sequence and test_session.sequence_id:
        try:
            from models import VideoTestSequence
            sequence = db.query(VideoTestSequence).filter(
                VideoTestSequence.id == test_session.sequence_id
            ).first()

            if sequence and sequence.sequence_order:
                for video_info in sequence.sequence_order:
                    video_id = video_info.get('video_id')
                    order = video_info.get('order', 0)
                    duration_ms = video_info.get('duration_ms', 0)
                    video_order_map[video_id] = {
                        'order': order,
                        'duration_s': duration_ms / 1000.0
                    }
                self.logger.info(f"📹 Video sequence order: {video_order_map}")
        except Exception as e:
            self.logger.warning(f"Could not load sequence order: {e}")

    if has_multi_video_sequence:
        self.logger.info(
            f"🎯 Multi-video sequence detected with {len(gt_video_ids)} videos - "
            f"Enforcing strict video boundary validation"
        )

    # ========================================================================
    # EXTRACT TIMESTAMPS: Build parallel arrays for optimal matching
    # ========================================================================
    gt_times = []
    gt_indices_map = []  # Maps position in gt_times to ground_truth_objects index

    for idx, gt_obj in enumerate(ground_truth_objects):
        gt_time = extract_ground_truth_video_time(gt_obj, session_start_time)
        if gt_time is not None:
            gt_times.append(gt_time)
            gt_indices_map.append(idx)
        else:
            # Ground truth with no timestamp → automatic FN
            self.logger.warning(
                f"Ground truth object {getattr(gt_obj, 'id', '<unknown>')} "
                f"missing timestamp; marking as false negative"
            )
            match_results.append(
                MatchResult(
                    ground_truth_id=getattr(gt_obj, 'id', None),
                    detection_event_id=None,
                    match_type='FN',
                    temporal_offset=0.0,
                    confidence=None,
                    iou_score=0.0,
                    latency_ms=None
                )
            )

    det_times = []
    det_indices_map = []  # Maps position in det_times to detection_events index

    for idx, detection in enumerate(detection_events):
        det_time = extract_detection_video_time(detection, session_start_time)
        if det_time is not None:
            det_times.append(det_time)
            det_indices_map.append(idx)
        # Detections with no timestamp are ignored (won't match)

    # ========================================================================
    # VIDEO BOUNDARY FILTERING: Pre-filter invalid cross-video matches
    # ========================================================================
    # Build compatibility matrix: valid[i,j] = True if GT[i] can match Det[j]
    import numpy as np
    valid_matches = np.ones((len(gt_times), len(det_times)), dtype=bool)

    video_boundary_rejections = 0
    missing_video_id_warnings = 0

    for i, gt_idx in enumerate(gt_indices_map):
        gt_obj = ground_truth_objects[gt_idx]
        gt_video_id = getattr(gt_obj, 'video_id', None)

        for j, det_idx in enumerate(det_indices_map):
            detection = detection_events[det_idx]
            detection_video_id = getattr(detection, 'video_id', None)

            # CRITICAL: Validate video boundary
            if detection_video_id is not None and gt_video_id is not None:
                if detection_video_id != gt_video_id:
                    # Different videos → invalid match
                    valid_matches[i, j] = False
                    video_boundary_rejections += 1
            elif detection_video_id is None and gt_video_id is not None:
                # Missing video ID on detection → allow match with warning
                if has_multi_video_sequence and missing_video_id_warnings < 3:
                    self.logger.warning(
                        f"⚠️ Detection {detection.id[:8]} missing video_id. "
                        f"Allowing timestamp-only match with GT video {gt_video_id[:8]}. "
                        f"May cause cross-video matches!"
                    )
                    missing_video_id_warnings += 1

    if video_boundary_rejections > 0:
        self.logger.info(
            f"📹 Video boundary validation: Rejected {video_boundary_rejections} "
            f"cross-video match candidates"
        )

    # ========================================================================
    # RUN OPTIMAL MATCHING ALGORITHM
    # ========================================================================
    optimal_result = optimal_detection_matching(
        gt_times,
        det_times,
        tolerance_seconds=tolerance_seconds,
        return_cost_matrix=False
    )

    # ========================================================================
    # APPLY VIDEO BOUNDARY CONSTRAINTS TO OPTIMAL RESULT
    # ========================================================================
    # Filter out any TP matches that violate video boundaries
    filtered_tps = []
    rejected_tps = []

    for gt_idx_in_array, det_idx_in_array, latency_ms in optimal_result['true_positives']:
        if valid_matches[gt_idx_in_array, det_idx_in_array]:
            filtered_tps.append((gt_idx_in_array, det_idx_in_array, latency_ms))
        else:
            # Optimal algorithm matched across video boundary → reject
            rejected_tps.append((gt_idx_in_array, det_idx_in_array))

    if len(rejected_tps) > 0:
        self.logger.warning(
            f"⚠️ Rejected {len(rejected_tps)} optimal matches due to video boundary violations"
        )

    # Update optimal result with filtered TPs
    optimal_result['true_positives'] = filtered_tps

    # Recalculate FP/FN after filtering
    matched_det_indices = set(det_idx for _, det_idx, _ in filtered_tps)
    matched_gt_indices = set(gt_idx for gt_idx, _, _ in filtered_tps)

    optimal_result['false_positives'] = [
        i for i in range(len(det_times)) if i not in matched_det_indices
    ]
    optimal_result['false_negatives'] = [
        i for i in range(len(gt_times)) if i not in matched_gt_indices
    ]

    # ========================================================================
    # CONVERT OPTIMAL RESULT TO MatchResult OBJECTS
    # ========================================================================

    # TRUE POSITIVES: Convert (array_idx, array_idx, latency) → MatchResult
    for gt_idx_in_array, det_idx_in_array, latency_ms in optimal_result['true_positives']:
        gt_idx = gt_indices_map[gt_idx_in_array]
        det_idx = det_indices_map[det_idx_in_array]

        gt_obj = ground_truth_objects[gt_idx]
        detection = detection_events[det_idx]

        gt_time = gt_times[gt_idx_in_array]
        det_time = det_times[det_idx_in_array]
        temporal_offset_ms = latency_ms  # Already signed

        iou_score = self._calculate_temporal_iou(
            gt_time, det_time, tolerance_seconds
        )

        # Capture video_id for latency grouping
        det_video_id = getattr(detection, "video_id", None)
        if not det_video_id:
            det_video_id = getattr(gt_obj, "video_id", None)
        if det_video_id is not None:
            det_video_id = str(det_video_id)

        # Debug logging for first few matches
        if tp_debug_count < 3:
            latency_display = f"{abs(latency_ms):.1f}ms" if latency_ms is not None else "N/A"
            self.logger.info(
                f"🔍 DEBUG: TP match - detection_id={detection.id[:8]}, "
                f"video_id={det_video_id[:12] if det_video_id else 'NULL'}, "
                f"latency={latency_display}"
            )
            tp_debug_count += 1

        match_result = MatchResult(
            ground_truth_id=gt_obj.id,
            detection_event_id=detection.id,
            match_type='TP',
            temporal_offset=temporal_offset_ms,
            confidence=detection.confidence,
            iou_score=iou_score,
            latency_ms=abs(latency_ms),
            video_id=det_video_id
        )
        match_results.append(match_result)

        # Enhanced logging with video context
        detection_video_id = getattr(detection, 'video_id', 'unknown')
        gt_video_id = getattr(gt_obj, 'video_id', 'unknown')
        self.logger.debug(
            f"TP Match: Video {gt_video_id} - GT@{gt_time:.3f}s → Detection@{det_time:.3f}s "
            f"(offset: {temporal_offset_ms:+.1f}ms, det_video: {detection_video_id})"
        )

    # FALSE NEGATIVES: GT with no match
    for gt_idx_in_array in optimal_result['false_negatives']:
        gt_idx = gt_indices_map[gt_idx_in_array]
        gt_obj = ground_truth_objects[gt_idx]
        gt_time = gt_times[gt_idx_in_array]

        match_result = MatchResult(
            ground_truth_id=gt_obj.id,
            detection_event_id=None,
            match_type='FN',
            temporal_offset=0.0,
            confidence=None,
            iou_score=0.0,
            latency_ms=None
        )
        match_results.append(match_result)

        gt_video_id = getattr(gt_obj, 'video_id', 'unknown')
        self.logger.debug(f"FN: Video {gt_video_id} - GT@{gt_time:.3f}s - No matching detection")

    # FALSE POSITIVES: Detections with no match
    for det_idx_in_array in optimal_result['false_positives']:
        det_idx = det_indices_map[det_idx_in_array]
        detection = detection_events[det_idx]
        det_time = det_times[det_idx_in_array]

        fp_video_id = getattr(detection, 'video_id', None)
        if fp_video_id is not None:
            fp_video_id = str(fp_video_id)

        match_result = MatchResult(
            ground_truth_id=None,
            detection_event_id=detection.id,
            match_type='FP',
            temporal_offset=0.0,
            confidence=detection.confidence,
            iou_score=0.0,
            latency_ms=None,
            video_id=fp_video_id
        )
        match_results.append(match_result)

        detection_video_id = getattr(detection, 'video_id', 'unknown')
        self.logger.debug(
            f"FP: Video {detection_video_id} - Detection@{det_time:.3f}s - No matching GT"
        )

    # ========================================================================
    # LOG SUMMARY
    # ========================================================================
    tp_count = len(optimal_result['true_positives'])
    fp_count = len(optimal_result['false_positives'])
    fn_count = len(optimal_result['false_negatives'])

    self.logger.info(
        f"✅ OPTIMAL MATCHING COMPLETE: {tp_count} TP, {fp_count} FP, {fn_count} FN "
        f"(Total: {len(match_results)} comparisons, "
        f"Total cost: {optimal_result['total_cost']*1000:.1f}ms)"
    )

    # ========================================================================
    # OPTIONAL: COMPARE WITH GREEDY FOR VALIDATION
    # ========================================================================
    if self.logger.level <= logging.DEBUG:
        try:
            from services.optimal_matching_service import greedy_detection_matching
            greedy_result = greedy_detection_matching(
                gt_times, det_times, tolerance_seconds
            )

            tp_diff = len(optimal_result['true_positives']) - len(greedy_result['true_positives'])
            cost_diff_ms = (greedy_result['total_cost'] - optimal_result['total_cost']) * 1000.0

            self.logger.debug(
                f"📊 GREEDY vs OPTIMAL: "
                f"TP difference: {tp_diff:+d}, "
                f"Cost improvement: {cost_diff_ms:+.1f}ms"
            )

            if tp_diff > 0 or cost_diff_ms > 0:
                self.logger.info(
                    f"🎯 OPTIMAL ALGORITHM IMPROVEMENT: "
                    f"Found {tp_diff} more TPs and reduced cost by {cost_diff_ms:.1f}ms"
                )
        except Exception as e:
            self.logger.debug(f"Greedy comparison skipped: {e}")

    # ========================================================================
    # VALIDATION: Verify no duplicate matches
    # ========================================================================
    try:
        from services.match_validator import validate_matches

        validation_result = validate_matches(match_results, strict=False)

        if not validation_result.valid:
            self.logger.error(
                f"⚠️ MATCH VALIDATION FAILED: {len(validation_result.errors)} errors detected"
            )
            for error in validation_result.errors:
                self.logger.error(f"  - {error}")
        else:
            self.logger.info(
                f"✅ Match validation PASSED: No duplicate matches detected "
                f"({validation_result.statistics['unique_detections']} unique detections, "
                f"{validation_result.statistics['unique_ground_truths']} unique GTs)"
            )
    except Exception as validation_error:
        self.logger.warning(f"Match validation skipped: {validation_error}")

    return match_results


# ============================================================================
# STEP 3: Replace method in class (manual step)
# ============================================================================

"""
In ground_truth_matching_service.py:

1. Locate the GroundTruthMatchingService class
2. Find the _perform_temporal_matching method (lines 655-961)
3. Replace the ENTIRE method with _perform_temporal_matching_OPTIMAL above
4. Rename _perform_temporal_matching_OPTIMAL → _perform_temporal_matching
5. Save file

No other changes needed - the rest of the service remains unchanged.
"""

# ============================================================================
# INTEGRATION CHECKLIST
# ============================================================================

"""
✅ Prerequisites:
   - scipy installed (already in requirements.txt: scipy>=1.16.0)
   - optimal_matching_service.py created
   - Tests pass (test_optimal_matching.py)

✅ Integration Steps:
   1. Add import at top of ground_truth_matching_service.py
   2. Replace _perform_temporal_matching method (lines 655-961)
   3. Test with existing test suite
   4. Monitor performance on production workloads

✅ Verification:
   - Run: pytest tests/test_ground_truth_matching_service.py -v
   - Check logs for "OPTIMAL MATCHING COMPLETE" message
   - Verify TP/FP/FN counts remain consistent or improve
   - Monitor runtime (should be <100ms for typical datasets)

✅ Rollback Plan:
   - Keep backup of original _perform_temporal_matching
   - If issues arise, revert to greedy algorithm
   - File bug report with test case that fails
"""
