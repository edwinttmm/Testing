"""
Optimal Ground Truth Matching Service using Hungarian Algorithm

This service replaces the greedy first-match algorithm with the optimal
Hungarian algorithm (linear_sum_assignment from scipy) to guarantee
mathematically optimal detection-to-ground-truth matching.

Key Improvements:
- Greedy algorithm: O(n*m) with suboptimal results (first-match wins)
- Hungarian algorithm: O(n³) with guaranteed optimal global assignment
- Prevents pathological cases where greedy algorithm fails badly

Author: Agent #5 - Optimal Matching Algorithm Specialist
Date: 2025-11-12

TIMEOUT PROTECTION (Agent #44):
- Hungarian O(n³) can take 73s for 5k×5k matrix
- 30-second timeout with greedy fallback for large datasets
- Max size threshold: 1000 (use greedy if n > 1000)
"""

import logging
import numpy as np
import time
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# CRITICAL DEPENDENCY CHECK: scipy required for Hungarian algorithm
try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    linear_sum_assignment = None
    # Log error but don't raise - let calling code handle it
    import logging
    logging.getLogger(__name__).error(
        "scipy is not installed - optimal matching algorithm will fail. "
        "Install with: pip install scipy"
    )

logger = logging.getLogger(__name__)

# Configuration
HUNGARIAN_TIMEOUT_SECONDS = 30
HUNGARIAN_MAX_SIZE = 1000  # Use greedy if n > 1000


def many_to_one_gt_matching(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float
) -> Dict[str, Any]:
    """
    Many-to-one GT-to-Detection matching for constant voltage scenarios.

    When constant voltage is applied throughout the test, we may have fewer
    detections than GT frames (e.g., 120 detections for 131 GT frames).
    In this case, a single detection should be able to satisfy multiple
    adjacent GT frames within tolerance.

    Algorithm:
    1. For each GT frame, find the closest detection within tolerance
    2. Allow the same detection to match multiple GT frames
    3. GT frames without any detection in tolerance become FN
    4. Detections not matched to any GT become FP

    Args:
        ground_truth_times: List of ground truth timestamps (seconds)
        detection_times: List of detection timestamps (seconds)
        tolerance_seconds: Maximum allowed time difference for valid match

    Returns:
        {
            'true_positives': [(gt_idx, det_idx, latency_ms), ...],
            'false_positives': [det_idx, ...],
            'false_negatives': [gt_idx, ...],
            'total_cost': float,
            'algorithm': 'many_to_one',
            'detections_used': set of detection indices that were matched
        }
    """
    n_gt = len(ground_truth_times)
    n_det = len(detection_times)

    logger.info(
        f"🔄 MANY-TO-ONE MATCHING: {n_gt} GT frames × {n_det} detections "
        f"(tolerance={tolerance_seconds*1000:.0f}ms)"
    )

    true_positives = []
    matched_gt_indices = set()
    used_detections = set()
    total_cost = 0.0

    # For each GT frame, find the closest detection within tolerance
    for gt_idx, gt_time in enumerate(ground_truth_times):
        best_det_idx = None
        best_diff = float('inf')

        for det_idx, det_time in enumerate(detection_times):
            diff = abs(det_time - gt_time)

            if diff <= tolerance_seconds and diff < best_diff:
                best_diff = diff
                best_det_idx = det_idx

        if best_det_idx is not None:
            # Calculate signed latency (detection - gt) in milliseconds
            latency_ms = (detection_times[best_det_idx] - gt_time) * 1000.0
            true_positives.append((gt_idx, best_det_idx, latency_ms))
            matched_gt_indices.add(gt_idx)
            used_detections.add(best_det_idx)
            total_cost += best_diff

    # False negatives: GT frames that had no detection within tolerance
    false_negatives = [i for i in range(n_gt) if i not in matched_gt_indices]

    # False positives: Detections that weren't matched to any GT
    false_positives = [i for i in range(n_det) if i not in used_detections]

    logger.info(
        f"✅ MANY-TO-ONE COMPLETE: {len(true_positives)} TP "
        f"(from {len(used_detections)} unique detections), "
        f"{len(false_positives)} FP, {len(false_negatives)} FN"
    )

    # Log reuse statistics
    detection_reuse = {}
    for gt_idx, det_idx, _ in true_positives:
        detection_reuse[det_idx] = detection_reuse.get(det_idx, 0) + 1

    multi_use = {k: v for k, v in detection_reuse.items() if v > 1}
    if multi_use:
        logger.info(
            f"📊 Detection reuse: {len(multi_use)} detections matched to multiple GT frames"
        )

    return {
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'total_cost': total_cost,
        'algorithm': 'many_to_one',
        'detections_used': used_detections,
        'detection_reuse_count': len(multi_use)
    }


def pre_aggregate_detections_by_frame(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float
) -> Tuple[List[float], List[int]]:
    """
    Pre-aggregate detections: for each GT frame, find the closest detection.

    This solves the problem where constant voltage generates 80+ detections
    for 10 frames (one detection every 5ms). Hungarian algorithm does one-to-one
    matching, so with 80 detections and 10 GT frames, some frames end up with
    no match because the algorithm globally optimizes.

    By pre-aggregating, we reduce 80 detections to ~10 (one per frame), making
    one-to-one matching work correctly.

    Algorithm:
    1. For each GT frame, find all detections within tolerance
    2. Pick the detection with minimum time difference (closest match)
    3. Return reduced detection list and mapping to original indices

    Args:
        ground_truth_times: List of ground truth timestamps (seconds)
        detection_times: List of detection timestamps (seconds)
        tolerance_seconds: Maximum allowed time difference for valid match

    Returns:
        Tuple of (aggregated_detection_times, original_detection_indices)
        - aggregated_detection_times: Reduced list of detection times (one per GT frame)
        - original_detection_indices: Mapping from aggregated index to original detection index

    Example:
        GT times: [1.0, 2.0, 3.0] (3 frames)
        Detection times: [1.001, 1.005, 1.008, 2.002, 2.004, 3.001] (6 detections)

        Pre-aggregation picks:
        - GT 1.0 -> Det 1.001 (index 0, closest to 1.0)
        - GT 2.0 -> Det 2.002 (index 3, closest to 2.0)
        - GT 3.0 -> Det 3.001 (index 5, closest to 3.0)

        Returns: ([1.001, 2.002, 3.001], [0, 3, 5])
    """
    aggregated_det_times = []
    original_indices = []

    logger.info(
        f"Pre-aggregating detections: {len(detection_times)} detections "
        f"-> ~{len(ground_truth_times)} (one per GT frame)"
    )

    for gt_idx, gt_time in enumerate(ground_truth_times):
        best_det_idx = None
        best_diff = float('inf')

        # Find closest detection within tolerance for this GT frame
        for det_idx, det_time in enumerate(detection_times):
            diff = abs(det_time - gt_time)

            if diff <= tolerance_seconds and diff < best_diff:
                best_diff = diff
                best_det_idx = det_idx

        if best_det_idx is not None:
            aggregated_det_times.append(detection_times[best_det_idx])
            original_indices.append(best_det_idx)
            logger.debug(
                f"  GT[{gt_idx}]={gt_time:.3f}s -> Det[{best_det_idx}]="
                f"{detection_times[best_det_idx]:.3f}s (diff={best_diff*1000:.1f}ms)"
            )
        else:
            logger.debug(
                f"  GT[{gt_idx}]={gt_time:.3f}s -> No detection within tolerance"
            )

    logger.info(
        f"Pre-aggregation complete: {len(original_indices)} detections selected "
        f"({len(detection_times) - len(original_indices)} filtered out)"
    )

    return aggregated_det_times, original_indices


@dataclass
class OptimalMatchResult:
    """Result of optimal matching algorithm"""
    true_positives: List[Tuple[int, int, float]]  # [(gt_idx, det_idx, latency_ms), ...]
    false_positives: List[int]  # detection indices with no match
    false_negatives: List[int]  # ground truth indices with no match
    total_cost: float  # sum of matched time differences
    algorithm_used: str  # 'hungarian' or 'greedy' for comparison


def optimal_detection_matching(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float = 0.1,
    return_cost_matrix: bool = False,
    ground_truth_video_ids: List[str] = None,
    detection_video_ids: List[str] = None
) -> Dict[str, Any]:
    """
    Use Hungarian algorithm for optimal detection-to-GT matching with timeout protection.

    The Hungarian algorithm (Kuhn-Munkres) guarantees the globally optimal
    assignment that minimizes total time difference across all matches.
    This is provably superior to greedy first-match algorithms.

    TIMEOUT PROTECTION:
    - For datasets > 1000 elements: automatically use greedy fallback
    - For datasets <= 1000: try Hungarian with 30s timeout, fallback to greedy if timeout
    - This prevents session timeouts on large datasets (5k×5k = 73s)

    Algorithm Steps:
    1. Build cost matrix C[i,j] = time_diff(gt[i], det[j])
    2. Set C[i,j] = infinity for matches outside tolerance window
    3. Set C[i,j] = infinity for cross-video matches (if video IDs provided)
    4. Run linear_sum_assignment to find optimal assignment (with timeout)
    5. Extract TP matches, classify remaining as FP/FN

    Args:
        ground_truth_times: List of ground truth timestamps (seconds)
        detection_times: List of detection timestamps (seconds)
        tolerance_seconds: Maximum allowed time difference for valid match (default: 0.1s = 100ms)
        return_cost_matrix: If True, include cost matrix in output for debugging
        ground_truth_video_ids: Optional list of video IDs for each GT (for multi-video sequences)
        detection_video_ids: Optional list of video IDs for each detection (for multi-video sequences)

    Returns:
        {
            'true_positives': [(gt_idx, det_idx, latency_ms), ...],
            'false_positives': [det_idx, ...],
            'false_negatives': [gt_idx, ...],
            'total_cost': float (sum of time differences for matched pairs),
            'algorithm': 'hungarian' or 'greedy',
            'execution_time_ms': float (milliseconds),
            'cost_matrix': np.ndarray (optional, if return_cost_matrix=True),
            'cross_video_filtered': int (number of cross-video pairs filtered)
        }

    Example:
        >>> gt_times = [1.0, 2.0, 3.0]  # 3 ground truth objects
        >>> det_times = [1.05, 2.02, 2.98]  # 3 detections with small latencies
        >>> result = optimal_detection_matching(gt_times, det_times, tolerance_seconds=0.1)
        >>> len(result['true_positives'])
        3
        >>> result['false_positives']
        []
        >>> result['false_negatives']
        []
    """
    # CRITICAL: Check scipy dependency
    if not SCIPY_AVAILABLE:
        error_msg = (
            "scipy is not installed - cannot perform optimal matching. "
            "Install with: pip install scipy"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    n_gt = len(ground_truth_times)
    n_det = len(detection_times)
    max_size = max(n_gt, n_det)

    start_time = time.time()

    logger.info(
        f"🔬 OPTIMAL MATCHING: {n_gt} ground truth × {n_det} detections "
        f"(tolerance={tolerance_seconds*1000:.0f}ms, max_size={max_size})"
    )

    # CONSTANT VOLTAGE DETECTION: Use many-to-one matching when detections < GT
    # This allows a single detection to satisfy multiple nearby GT frames,
    # which is appropriate when constant voltage is applied but hardware
    # detection rate is lower than video frame rate
    if n_det > 0 and n_gt > n_det:
        detection_ratio = n_det / n_gt
        if detection_ratio < 0.95:  # Less than 95% detection rate
            logger.info(
                f"🔄 Constant voltage scenario detected: {n_det} detections for {n_gt} GT frames "
                f"(ratio={detection_ratio:.1%}). Using many-to-one matching."
            )
            result = many_to_one_gt_matching(
                ground_truth_times,
                detection_times,
                tolerance_seconds
            )
            execution_time_ms = (time.time() - start_time) * 1000.0
            result['execution_time_ms'] = execution_time_ms
            return result

    # Check if dataset too large - use greedy instead
    if max_size > HUNGARIAN_MAX_SIZE:
        logger.warning(
            f"⚠️ Dataset too large ({max_size} > {HUNGARIAN_MAX_SIZE}), "
            f"using greedy matching for performance"
        )
        result = greedy_detection_matching(
            ground_truth_times,
            detection_times,
            tolerance_seconds,
            ground_truth_video_ids,
            detection_video_ids
        )
        execution_time_ms = (time.time() - start_time) * 1000.0
        result['execution_time_ms'] = execution_time_ms
        return result

    # Handle edge cases
    if n_gt == 0:
        # No ground truth - all detections are false positives
        execution_time_ms = (time.time() - start_time) * 1000.0
        return {
            'true_positives': [],
            'false_positives': list(range(n_det)),
            'false_negatives': [],
            'total_cost': 0.0,
            'algorithm': 'hungarian',
            'execution_time_ms': execution_time_ms
        }

    if n_det == 0:
        # No detections - all ground truth are false negatives
        execution_time_ms = (time.time() - start_time) * 1000.0
        return {
            'true_positives': [],
            'false_positives': [],
            'false_negatives': list(range(n_gt)),
            'total_cost': 0.0,
            'algorithm': 'hungarian',
            'execution_time_ms': execution_time_ms
        }

    # Try Hungarian with timeout
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_hungarian_algorithm,
                ground_truth_times,
                detection_times,
                tolerance_seconds,
                return_cost_matrix,
                ground_truth_video_ids,
                detection_video_ids
            )

            # Wait for result with timeout
            result = future.result(timeout=HUNGARIAN_TIMEOUT_SECONDS)
            execution_time_ms = (time.time() - start_time) * 1000.0
            result['execution_time_ms'] = execution_time_ms

            logger.info(
                f"✅ Hungarian algorithm completed in {execution_time_ms:.1f}ms "
                f"({len(result['true_positives'])} TP)"
            )
            return result

    except FuturesTimeoutError:
        execution_time_ms = (time.time() - start_time) * 1000.0
        logger.warning(
            f"⏱️ Hungarian algorithm timeout after {execution_time_ms:.1f}ms "
            f"(limit: {HUNGARIAN_TIMEOUT_SECONDS}s), falling back to greedy"
        )
        result = greedy_detection_matching(
            ground_truth_times,
            detection_times,
            tolerance_seconds,
            ground_truth_video_ids,
            detection_video_ids
        )
        result['execution_time_ms'] = execution_time_ms
        result['timeout_occurred'] = True
        return result

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000.0
        logger.error(
            f"❌ Hungarian algorithm failed after {execution_time_ms:.1f}ms: {e}, "
            f"falling back to greedy"
        )
        result = greedy_detection_matching(
            ground_truth_times,
            detection_times,
            tolerance_seconds,
            ground_truth_video_ids,
            detection_video_ids
        )
        result['execution_time_ms'] = execution_time_ms
        result['error_occurred'] = True
        return result


def _run_hungarian_algorithm(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float,
    return_cost_matrix: bool = False,
    ground_truth_video_ids: List[str] = None,
    detection_video_ids: List[str] = None
) -> Dict[str, Any]:
    """
    Run Hungarian algorithm with prefiltering for sparse matrices.

    FIXED: Handles infeasible cost matrices by prefiltering infinity rows/columns.

    PRE-AGGREGATION FIX (Option 1):
    When there are significantly more detections than GT frames (e.g., 80 detections
    for 10 frames due to constant voltage), we pre-aggregate by picking the closest
    detection for each GT frame. This reduces the problem from 80:10 to ~10:10,
    making one-to-one matching work correctly.

    This function is executed in a separate thread with timeout protection.

    Args:
        ground_truth_times: List of ground truth timestamps (seconds)
        detection_times: List of detection timestamps (seconds)
        tolerance_seconds: Tolerance window
        return_cost_matrix: If True, include cost matrix in output
        ground_truth_video_ids: Optional list of video IDs for each GT
        detection_video_ids: Optional list of video IDs for each detection

    Returns:
        Same format as optimal_detection_matching (without execution_time_ms)
    """
    # Store original counts for FP calculation
    original_n_gt = len(ground_truth_times)
    original_n_det = len(detection_times)

    n_gt = original_n_gt
    n_det = original_n_det

    # PRE-AGGREGATION: If many more detections than GT (constant voltage scenario),
    # reduce detections to one per GT frame before running Hungarian algorithm
    detection_index_map = None  # Maps aggregated index -> original index
    if n_det > n_gt * 2:  # Only if significantly more detections than GT
        logger.info(
            f"Applying pre-aggregation: {n_det} detections >> {n_gt} GT frames "
            f"(ratio: {n_det/n_gt:.1f}:1)"
        )

        # Pre-aggregate: pick closest detection per GT frame
        aggregated_times, original_indices = pre_aggregate_detections_by_frame(
            ground_truth_times, detection_times, tolerance_seconds
        )

        # Store mapping and use aggregated times for Hungarian
        detection_index_map = original_indices
        detection_times = aggregated_times
        n_det = len(detection_times)

        logger.info(
            f"Pre-aggregation reduced detections: {len(original_indices)} -> {n_det}"
        )

        # Also filter video IDs if provided
        if detection_video_ids is not None:
            detection_video_ids = [detection_video_ids[i] for i in original_indices]

    # Step 1: Build cost matrix
    # C[i,j] = absolute time difference between gt[i] and detection[j]
    cost_matrix = np.full((n_gt, n_det), float('inf'), dtype=np.float64)

    cross_video_filtered = 0

    for i, gt_time in enumerate(ground_truth_times):
        for j, det_time in enumerate(detection_times):
            time_diff = abs(det_time - gt_time)

            # CRITICAL FIX: Filter cross-video matches BEFORE Hungarian algorithm
            # This prevents the algorithm from assigning cross-video matches that
            # would be rejected later, leading to unnecessary FP/FN classifications
            if ground_truth_video_ids is not None and detection_video_ids is not None:
                gt_video = ground_truth_video_ids[i]
                det_video = detection_video_ids[j]

                # Skip cross-video pairs (set cost to infinity)
                if gt_video is not None and det_video is not None and gt_video != det_video:
                    cross_video_filtered += 1
                    continue  # cost remains infinity

            # Only consider matches within tolerance window
            if time_diff <= tolerance_seconds:
                cost_matrix[i, j] = time_diff
                logger.debug(f"🔍 VALID MATCH: GT[{i}]={gt_time:.3f}s vs DET[{j}]={det_time:.3f}s, diff={time_diff*1000:.1f}ms")
            # else: cost remains infinity (invalid match)

    # Debug: Log cost matrix statistics
    valid_costs = cost_matrix[cost_matrix < float('inf')]
    if len(valid_costs) > 0:
        logger.debug(
            f"Cost matrix: {len(valid_costs)} valid matches "
            f"(min={valid_costs.min()*1000:.1f}ms, "
            f"mean={valid_costs.mean()*1000:.1f}ms, "
            f"max={valid_costs.max()*1000:.1f}ms)"
        )
    else:
        logger.warning("⚠️ No valid matches found within tolerance window")

    # Step 2: PREFILTER cost matrix to handle sparse/infeasible cases
    # Identify feasible rows (GTs) and columns (detections) that have at least one finite cost
    LARGE_VALUE = 1e9  # Threshold for determining if a cost is "infinity"

    feasible_rows = []  # GT indices with at least one match
    feasible_cols = []  # Detection indices with at least one match

    for i in range(n_gt):
        if np.any(cost_matrix[i, :] < LARGE_VALUE):
            feasible_rows.append(i)

    for j in range(n_det):
        if np.any(cost_matrix[:, j] < LARGE_VALUE):
            feasible_cols.append(j)

    logger.info(
        f"🔍 Prefiltering: {len(feasible_rows)}/{n_gt} feasible GTs, "
        f"{len(feasible_cols)}/{n_det} feasible detections"
    )

    if len(feasible_rows) == 0 or len(feasible_cols) == 0:
        logger.warning("⚠️ No feasible matches found (all outside tolerance): cost matrix is infeasible")
        # Return empty assignment - all GTs are FN, all detections are FP
        return {
            'true_positives': [],
            'false_positives': list(range(n_det)),
            'false_negatives': list(range(n_gt)),
            'total_cost': 0.0,
            'algorithm': 'hungarian',
            'cross_video_filtered': cross_video_filtered
        }

    # Step 3: Create reduced cost matrix with only feasible rows/cols
    reduced_cost_matrix = cost_matrix[np.ix_(feasible_rows, feasible_cols)]

    # Step 4: Run Hungarian algorithm on reduced matrix
    logger.debug(
        f"🔍 Running Hungarian on reduced matrix: "
        f"{len(feasible_rows)}×{len(feasible_cols)} (original: {n_gt}×{n_det})"
    )

    # DEBUG: Inspect reduced matrix before passing to Hungarian
    logger.info(f"🔍 DEBUG: Reduced matrix shape: {reduced_cost_matrix.shape}")
    logger.info(f"🔍 DEBUG: Min value: {np.min(reduced_cost_matrix):.2f}, Max value: {np.max(reduced_cost_matrix):.2f}")
    logger.info(f"🔍 DEBUG: Contains NaN: {np.any(np.isnan(reduced_cost_matrix))}")
    logger.info(f"🔍 DEBUG: Contains Inf: {np.any(np.isinf(reduced_cost_matrix))}")
    logger.info(f"🔍 DEBUG: Number of finite values: {np.isfinite(reduced_cost_matrix).sum()}/{reduced_cost_matrix.size}")

    if reduced_cost_matrix.size > 0:
        finite_mask = np.isfinite(reduced_cost_matrix)
        if np.any(finite_mask):
            logger.info(f"🔍 DEBUG: Finite value range: [{np.min(reduced_cost_matrix[finite_mask]):.2f}, {np.max(reduced_cost_matrix[finite_mask]):.2f}]")
        logger.info(f"🔍 DEBUG: Sample (first 5x5):\n{reduced_cost_matrix[:5, :5]}")

    try:
        row_ind_reduced, col_ind_reduced = linear_sum_assignment(reduced_cost_matrix)
    except ValueError as e:
        logger.error(f"❌ Hungarian failed even after prefiltering: {e}")
        logger.error(f"❌ DEBUG: This suggests the prefiltering logic has a bug or cost matrix construction issue")

        # Fallback to greedy algorithm for sparse scenarios
        logger.warning("⚠️ Falling back to greedy matching algorithm")

        # Use existing greedy algorithm
        LARGE_VALUE = 1e9
        assigned_gts = set()
        assigned_dets = set()
        matches = []

        # Create list of all finite costs with their indices
        finite_costs = []
        for i in range(n_gt):
            for j in range(n_det):
                if cost_matrix[i, j] < LARGE_VALUE:
                    finite_costs.append((cost_matrix[i, j], i, j))

        # Sort by cost (greedy: always pick lowest cost first)
        finite_costs.sort(key=lambda x: x[0])
        logger.info(f"🔍 Greedy: Found {len(finite_costs)} finite costs to evaluate")

        # Greedily assign matches
        for cost, gt_idx, det_idx in finite_costs:
            if gt_idx in assigned_gts or det_idx in assigned_dets:
                continue
            matches.append((gt_idx, det_idx, cost))
            assigned_gts.add(gt_idx)
            assigned_dets.add(det_idx)

        # Extract results
        # IMPORTANT: true_positives must be 3-element tuples (gt_idx, det_idx, latency_ms)
        # to match the format expected by _perform_temporal_matching
        # Map back to original detection indices if pre-aggregation was used
        true_positives = [
            (gt_idx, detection_index_map[det_idx] if detection_index_map else det_idx, cost)
            for gt_idx, det_idx, cost in matches
        ]

        matched_original_det_indices = set(det_idx for _, det_idx, _ in true_positives)

        if detection_index_map:
            # With pre-aggregation: All original detections NOT matched are FP
            false_positives = [i for i in range(original_n_det) if i not in matched_original_det_indices]
        else:
            false_positives = [j for j in range(original_n_det) if j not in assigned_dets]

        false_negatives = [i for i in range(original_n_gt) if i not in assigned_gts]
        total_cost = sum(cost for _, _, cost in matches)

        logger.info(
            f"✅ Greedy completed: {len(true_positives)} matches, "
            f"{len(false_negatives)} unmatched GTs, {len(false_positives)} unmatched dets"
        )

        return {
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'total_cost': total_cost,
            'algorithm': 'greedy',
            'cross_video_filtered': cross_video_filtered
        }

    # Step 5: Map reduced indices back to original indices
    row_ind = np.array([feasible_rows[i] for i in row_ind_reduced])
    col_ind = np.array([feasible_cols[j] for j in col_ind_reduced])

    # Step 6: Filter out assignments that are still infinity (shouldn't happen but be safe)
    valid_assignments = []
    for i, (r, c) in enumerate(zip(row_ind, col_ind)):
        if cost_matrix[r, c] < LARGE_VALUE:
            valid_assignments.append(i)

    row_ind = row_ind[valid_assignments]
    col_ind = col_ind[valid_assignments]

    logger.info(
        f"✅ Hungarian algorithm completed: {len(row_ind)} matches found "
        f"({n_gt - len(row_ind)} unmatched GTs, "
        f"{n_det - len(row_ind)} unmatched detections)"
    )

    # Step 7: Extract true positives
    # Only keep assignments where cost < infinity (within tolerance)
    true_positives = []
    total_cost = 0.0

    for gt_idx, det_idx in zip(row_ind, col_ind):
        cost = cost_matrix[gt_idx, det_idx]

        if cost < float('inf'):
            # Valid match within tolerance
            # Calculate signed latency (detection_time - gt_time)
            latency_ms = (detection_times[det_idx] - ground_truth_times[gt_idx]) * 1000.0

            # Map back to original detection index if pre-aggregation was used
            original_det_idx = detection_index_map[det_idx] if detection_index_map else det_idx

            true_positives.append((gt_idx, original_det_idx, latency_ms))
            total_cost += cost

    # Step 8: Identify unmatched detections (false positives)
    # IMPORTANT: If pre-aggregation was used, all non-selected detections are FP
    matched_original_det_indices = set(det_idx for _, det_idx, _ in true_positives)

    if detection_index_map:
        # With pre-aggregation: All original detections NOT in the matched set are FP
        # This includes both:
        # 1. Detections that were filtered out during pre-aggregation
        # 2. Aggregated detections that weren't matched by Hungarian
        false_positives = [i for i in range(original_n_det) if i not in matched_original_det_indices]
        logger.info(
            f"Pre-aggregation FP handling: {original_n_det} original detections "
            f"- {len(matched_original_det_indices)} matched = {len(false_positives)} FP"
        )
    else:
        false_positives = [i for i in range(original_n_det) if i not in matched_original_det_indices]

    # Step 9: Identify unmatched ground truth (false negatives)
    matched_gt_indices = set(gt_idx for gt_idx, _, _ in true_positives)
    false_negatives = [i for i in range(original_n_gt) if i not in matched_gt_indices]

    # Log results (don't log here - logged by caller with execution time)
    result = {
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'total_cost': total_cost,
        'algorithm': 'hungarian',
        'cross_video_filtered': cross_video_filtered
    }

    # Add pre-aggregation metadata if it was used
    if detection_index_map:
        result['pre_aggregation_applied'] = True
        result['pre_aggregation_stats'] = {
            'original_detections': original_n_det,
            'aggregated_detections': len(detection_index_map),
            'reduction_ratio': f"{original_n_det/len(detection_index_map):.1f}:1"
        }
        logger.info(
            f"✅ Pre-aggregation applied: {original_n_det} -> {len(detection_index_map)} detections "
            f"(reduction: {original_n_det/len(detection_index_map):.1f}:1)"
        )

    if cross_video_filtered > 0:
        logger.info(f"🎬 Filtered {cross_video_filtered} cross-video pairs from cost matrix")

    if return_cost_matrix:
        result['cost_matrix'] = cost_matrix

    return result


def greedy_detection_matching(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float = 0.1,
    ground_truth_video_ids: List[str] = None,
    detection_video_ids: List[str] = None
) -> Dict[str, Any]:
    """
    Greedy first-match algorithm - fallback for large datasets or timeout.

    This is the FALLBACK algorithm used when:
    1. Dataset is too large (> 1000 elements)
    2. Hungarian algorithm times out (> 30 seconds)
    3. Hungarian algorithm fails due to error

    PERFORMANCE:
    - Time complexity: O(n*m) instead of O(n³)
    - Executes in < 1 second even for 5k×5k datasets
    - Results are suboptimal but acceptable for large datasets

    KNOWN ISSUES:
    - First-match wins, even if not optimal globally
    - Can produce suboptimal results in pathological cases
    - Example: GT=[1.0, 2.0], Det=[1.05, 1.06]:
        - Greedy: GT1->Det1, GT2 unmatched (suboptimal)
        - Optimal: GT1->Det1, GT2->Det2 might be better global assignment

    Args:
        ground_truth_times: List of ground truth timestamps
        detection_times: List of detection timestamps
        tolerance_seconds: Tolerance window
        ground_truth_video_ids: Optional list of video IDs for each GT
        detection_video_ids: Optional list of video IDs for each detection

    Returns:
        Same format as optimal_detection_matching
    """
    n_gt = len(ground_truth_times)
    n_det = len(detection_times)

    logger.info(f"🐌 GREEDY MATCHING (fallback): {n_gt} GT × {n_det} Det")

    if n_gt == 0:
        return {
            'true_positives': [],
            'false_positives': list(range(n_det)),
            'false_negatives': [],
            'total_cost': 0.0,
            'algorithm': 'greedy'
        }

    if n_det == 0:
        return {
            'true_positives': [],
            'false_positives': [],
            'false_negatives': list(range(n_gt)),
            'total_cost': 0.0,
            'algorithm': 'greedy'
        }

    true_positives = []
    used_detections = set()
    total_cost = 0.0
    cross_video_filtered = 0

    # Greedy: For each GT, find closest detection (first-match wins)
    for gt_idx, gt_time in enumerate(ground_truth_times):
        best_match = None
        best_time_diff = float('inf')

        for det_idx, det_time in enumerate(detection_times):
            if det_idx in used_detections:
                continue

            # CRITICAL FIX: Skip cross-video matches in greedy algorithm too
            if ground_truth_video_ids is not None and detection_video_ids is not None:
                gt_video = ground_truth_video_ids[gt_idx]
                det_video = detection_video_ids[det_idx]

                if gt_video is not None and det_video is not None and gt_video != det_video:
                    cross_video_filtered += 1
                    continue  # Skip this pairing

            # Handle None timestamps safely
            if det_time is None or gt_time is None:
                continue

            time_diff = abs(det_time - gt_time)

            if time_diff <= tolerance_seconds and time_diff < best_time_diff:
                best_match = det_idx
                best_time_diff = time_diff

        if best_match is not None:
            latency_ms = (detection_times[best_match] - gt_time) * 1000.0
            true_positives.append((gt_idx, best_match, latency_ms))
            used_detections.add(best_match)
            total_cost += best_time_diff

    matched_gt_indices = set(gt_idx for gt_idx, _, _ in true_positives)
    false_negatives = [i for i in range(n_gt) if i not in matched_gt_indices]
    false_positives = [i for i in range(n_det) if i not in used_detections]

    logger.info(
        f"🐌 GREEDY COMPLETE: "
        f"{len(true_positives)} TP, "
        f"{len(false_positives)} FP, "
        f"{len(false_negatives)} FN "
        f"(total_cost={total_cost*1000:.1f}ms)"
    )

    if cross_video_filtered > 0:
        logger.info(f"🎬 Filtered {cross_video_filtered} cross-video pairs (greedy)")

    return {
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'total_cost': total_cost,
        'algorithm': 'greedy',
        'cross_video_filtered': cross_video_filtered
    }


def compare_matching_algorithms(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float = 0.1
) -> Dict[str, Any]:
    """
    Compare greedy vs optimal matching algorithms.

    Returns:
        {
            'optimal_result': {...},
            'greedy_result': {...},
            'comparison': {
                'tp_difference': int,
                'cost_improvement_ms': float,
                'optimal_better': bool
            }
        }
    """
    optimal = optimal_detection_matching(ground_truth_times, detection_times, tolerance_seconds)
    greedy = greedy_detection_matching(ground_truth_times, detection_times, tolerance_seconds)

    tp_diff = len(optimal['true_positives']) - len(greedy['true_positives'])
    cost_improvement_ms = (greedy['total_cost'] - optimal['total_cost']) * 1000.0

    logger.info(
        f"📊 ALGORITHM COMPARISON:\n"
        f"  Optimal: {len(optimal['true_positives'])} TP, cost={optimal['total_cost']*1000:.1f}ms\n"
        f"  Greedy:  {len(greedy['true_positives'])} TP, cost={greedy['total_cost']*1000:.1f}ms\n"
        f"  Difference: {tp_diff:+d} TP, {cost_improvement_ms:+.1f}ms cost reduction"
    )

    return {
        'optimal_result': optimal,
        'greedy_result': greedy,
        'comparison': {
            'tp_difference': tp_diff,
            'cost_improvement_ms': cost_improvement_ms,
            'optimal_better': tp_diff >= 0 and optimal['total_cost'] <= greedy['total_cost']
        }
    }
