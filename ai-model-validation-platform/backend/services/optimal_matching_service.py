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
from scipy.optimize import linear_sum_assignment
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError


logger = logging.getLogger(__name__)

# Configuration
HUNGARIAN_TIMEOUT_SECONDS = 30
HUNGARIAN_MAX_SIZE = 1000  # Use greedy if n > 1000


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
    return_cost_matrix: bool = False
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
    3. Run linear_sum_assignment to find optimal assignment (with timeout)
    4. Extract TP matches, classify remaining as FP/FN

    Args:
        ground_truth_times: List of ground truth timestamps (seconds)
        detection_times: List of detection timestamps (seconds)
        tolerance_seconds: Maximum allowed time difference for valid match (default: 0.1s = 100ms)
        return_cost_matrix: If True, include cost matrix in output for debugging

    Returns:
        {
            'true_positives': [(gt_idx, det_idx, latency_ms), ...],
            'false_positives': [det_idx, ...],
            'false_negatives': [gt_idx, ...],
            'total_cost': float (sum of time differences for matched pairs),
            'algorithm': 'hungarian' or 'greedy',
            'execution_time_ms': float (milliseconds),
            'cost_matrix': np.ndarray (optional, if return_cost_matrix=True)
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
    n_gt = len(ground_truth_times)
    n_det = len(detection_times)
    max_size = max(n_gt, n_det)

    start_time = time.time()

    logger.info(
        f"🔬 OPTIMAL MATCHING: {n_gt} ground truth × {n_det} detections "
        f"(tolerance={tolerance_seconds*1000:.0f}ms, max_size={max_size})"
    )

    # Check if dataset too large - use greedy instead
    if max_size > HUNGARIAN_MAX_SIZE:
        logger.warning(
            f"⚠️ Dataset too large ({max_size} > {HUNGARIAN_MAX_SIZE}), "
            f"using greedy matching for performance"
        )
        result = greedy_detection_matching(
            ground_truth_times,
            detection_times,
            tolerance_seconds
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
                return_cost_matrix
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
            tolerance_seconds
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
            tolerance_seconds
        )
        result['execution_time_ms'] = execution_time_ms
        result['error_occurred'] = True
        return result


def _run_hungarian_algorithm(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float,
    return_cost_matrix: bool = False
) -> Dict[str, Any]:
    """
    Run Hungarian algorithm (no timeout - runs in thread).

    This function is executed in a separate thread with timeout protection.

    Args:
        ground_truth_times: List of ground truth timestamps (seconds)
        detection_times: List of detection timestamps (seconds)
        tolerance_seconds: Tolerance window
        return_cost_matrix: If True, include cost matrix in output

    Returns:
        Same format as optimal_detection_matching (without execution_time_ms)
    """
    n_gt = len(ground_truth_times)
    n_det = len(detection_times)

    # Step 1: Build cost matrix
    # C[i,j] = absolute time difference between gt[i] and detection[j]
    cost_matrix = np.full((n_gt, n_det), float('inf'), dtype=np.float64)

    for i, gt_time in enumerate(ground_truth_times):
        for j, det_time in enumerate(detection_times):
            time_diff = abs(det_time - gt_time)

            # Only consider matches within tolerance window
            if time_diff <= tolerance_seconds:
                cost_matrix[i, j] = time_diff
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

    # Step 2: Run Hungarian algorithm
    # linear_sum_assignment finds the optimal assignment that minimizes total cost
    # CRITICAL: Handle infeasible case (all costs are infinity)
    try:
        gt_indices, det_indices = linear_sum_assignment(cost_matrix)
    except ValueError as e:
        # Cost matrix is infeasible (all values are infinity)
        # This means no valid matches exist within tolerance
        logger.warning(f"⚠️ No feasible matches found (all outside tolerance): {e}")
        return {
            'true_positives': [],
            'false_positives': list(range(n_det)),
            'false_negatives': list(range(n_gt)),
            'total_cost': 0.0,
            'algorithm': 'hungarian'
        }

    # Step 3: Extract true positives
    # Only keep assignments where cost < infinity (within tolerance)
    true_positives = []
    total_cost = 0.0

    for gt_idx, det_idx in zip(gt_indices, det_indices):
        cost = cost_matrix[gt_idx, det_idx]

        if cost < float('inf'):
            # Valid match within tolerance
            # Calculate signed latency (detection_time - gt_time)
            latency_ms = (detection_times[det_idx] - ground_truth_times[gt_idx]) * 1000.0
            true_positives.append((gt_idx, det_idx, latency_ms))
            total_cost += cost

    # Step 4: Identify unmatched detections (false positives)
    matched_det_indices = set(det_idx for _, det_idx, _ in true_positives)
    false_positives = [i for i in range(n_det) if i not in matched_det_indices]

    # Step 5: Identify unmatched ground truth (false negatives)
    matched_gt_indices = set(gt_idx for gt_idx, _, _ in true_positives)
    false_negatives = [i for i in range(n_gt) if i not in matched_gt_indices]

    # Log results (don't log here - logged by caller with execution time)
    result = {
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'total_cost': total_cost,
        'algorithm': 'hungarian'
    }

    if return_cost_matrix:
        result['cost_matrix'] = cost_matrix

    return result


def greedy_detection_matching(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float = 0.1
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

    # Greedy: For each GT, find closest detection (first-match wins)
    for gt_idx, gt_time in enumerate(ground_truth_times):
        best_match = None
        best_time_diff = float('inf')

        for det_idx, det_time in enumerate(detection_times):
            if det_idx in used_detections:
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

    return {
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'total_cost': total_cost,
        'algorithm': 'greedy'
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
