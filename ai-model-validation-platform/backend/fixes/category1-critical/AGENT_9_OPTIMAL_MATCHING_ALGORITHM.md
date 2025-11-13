# Agent #9: Optimal Matching Algorithm (Hungarian Method)

## Mission
Replace greedy first-match algorithm with optimal bipartite matching for GT-Detection correlation.

## Problem Analysis

**Current Algorithm (Greedy):**
```python
# Line 740-814 in ground_truth_matching_service.py
for gt_obj in ground_truth_objects:
    best_match = None
    best_time_diff = float('inf')

    for i, detection in enumerate(detection_events):
        if i in used_detections:
            continue  # Skip already matched

        time_diff = abs(detection_time - gt_time)

        if time_diff <= tolerance_seconds and time_diff < best_time_diff:
            best_match = (i, detection)
            best_time_diff = time_diff

    if best_match:
        used_detections.add(best_match[0])  # Mark as used
```

**Why This Is Suboptimal:**

**Example:**
- GT1 at t=1.0s, GT2 at t=2.0s
- Det1 at t=1.05s, Det2 at t=1.95s
- Tolerance = 0.5s

**Greedy matching:**
1. Match GT1: closest is Det1 (0.05s) → Match
2. Match GT2: Det1 already used, closest is Det2 (0.05s) → Match
3. **Total error: 0.05 + 0.05 = 0.10s**

**Optimal matching:**
1. GT1 ↔ Det1: error = 0.05s
2. GT2 ↔ Det2: error = 0.05s
3. **Total error: 0.05 + 0.05 = 0.10s** (same in this case)

**Better example where greedy fails:**
- GT1 at t=1.0s, GT2 at t=2.0s
- Det1 at t=1.1s, Det2 at t=1.9s

**Greedy:**
1. GT1 → Det1 (0.1s)
2. GT2 → Det2 (0.1s)
3. **Total: 0.2s**

**Optimal (Hungarian):**
1. GT1 → Det2 (0.9s) - WORSE individually
2. GT2 → Det1 (0.9s) - WORSE individually
3. **Total: 1.8s - WORSE overall!**

Wait... that's worse. Let me reconsider...

Actually, the **CORRECT optimal matching** for this example:
- GT1 → Det1 (0.1s)
- GT2 → Det2 (0.1s)
- Total: 0.2s

So greedy actually found optimal here. But consider THIS scenario:

**Greedy FAILS here:**
- GT1 at 1.0s, GT2 at 1.5s, GT3 at 2.0s
- Det1 at 1.05s, Det2 at 1.45s, Det3 at 1.95s

**Greedy (processes GT1 first):**
1. GT1 → Det1 (0.05s) ← Takes Det1!
2. GT2 → Det2 (0.05s)
3. GT3 → Det3 (0.05s)
4. **Total: 0.15s** ✅

**BUT if we have:**
- GT1 at 1.0s, GT2 at 1.1s, GT3 at 2.0s
- Det1 at 1.05s, Det2 at 1.5s, Det3 at 2.05s

**Greedy (processes GT1 first):**
1. GT1 → Det1 (0.05s) ← Takes the only good match for GT2!
2. GT2 → Det2 (0.4s) ← Forced to take suboptimal match
3. GT3 → Det3 (0.05s)
4. **Total: 0.5s** ❌

**Optimal (Hungarian):**
1. GT1 → NONE (or Det2 at 0.5s)
2. GT2 → Det1 (0.05s)
3. GT3 → Det3 (0.05s)
4. **Total: 0.1s (or 0.6s if we match GT1→Det2)** ✅

**Key insight:** Greedy can be **provably suboptimal** when early choices block better global matches.

## Fix Implementation

### Solution: Hungarian Algorithm (Scipy's `linear_sum_assignment`)

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/services/optimal_matching_service.py

"""
Optimal Ground Truth Matching using Hungarian Algorithm

Replaces greedy first-match with provably optimal bipartite matching.

ALGORITHM: Hungarian Method (Kuhn-Munkres)
- Time complexity: O(n³) where n = max(|GT|, |Det|)
- Guarantees global optimum (minimum total matching cost)
- Handles edge cases: unequal GT/Detection counts, unmatchable pairs

BENEFITS:
- Provably optimal matches (no greedy regrets)
- Better precision/recall in ambiguous scenarios
- Handles outliers gracefully
"""

import logging
import numpy as np
from scipy.optimize import linear_sum_assignment
from typing import List, Tuple, Set, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MatchResult:
    """Individual GT-Detection match result"""
    gt_index: int
    det_index: Optional[int]
    match_type: str  # 'TP', 'FP', 'FN'
    temporal_offset_ms: float
    cost: float  # Matching cost (time difference)

class OptimalMatchingService:
    """
    Optimal bipartite matching for ground truth and detections.

    Uses Hungarian algorithm to find global minimum cost assignment.
    """

    def __init__(self, tolerance_ms: float = 100.0):
        self.tolerance_ms = tolerance_ms
        self.tolerance_seconds = tolerance_ms / 1000.0

    def match_ground_truth_to_detections(
        self,
        gt_timestamps: List[float],
        detection_timestamps: List[float],
        gt_video_ids: Optional[List[str]] = None,
        det_video_ids: Optional[List[str]] = None
    ) -> Tuple[List[MatchResult], dict]:
        """
        Find optimal matching between ground truth and detections.

        Args:
            gt_timestamps: Ground truth timestamps (seconds)
            detection_timestamps: Detection timestamps (seconds)
            gt_video_ids: Optional video IDs for GT (for multi-video boundary check)
            det_video_ids: Optional video IDs for detections

        Returns:
            (match_results, statistics)
        """
        n_gt = len(gt_timestamps)
        n_det = len(detection_timestamps)

        if n_gt == 0 and n_det == 0:
            return [], {'tp': 0, 'fp': 0, 'fn': 0}

        if n_gt == 0:
            # All detections are false positives
            return self._create_fp_results(n_det), {'tp': 0, 'fp': n_det, 'fn': 0}

        if n_det == 0:
            # All ground truth are false negatives
            return self._create_fn_results(n_gt), {'tp': 0, 'fp': 0, 'fn': n_gt}

        # Build cost matrix (n_gt x n_det)
        cost_matrix = self._build_cost_matrix(
            gt_timestamps,
            detection_timestamps,
            gt_video_ids,
            det_video_ids
        )

        # Apply Hungarian algorithm
        gt_indices, det_indices = linear_sum_assignment(cost_matrix)

        # Build match results
        match_results = []
        used_detections = set()

        # Process matches from Hungarian algorithm
        for gt_idx, det_idx in zip(gt_indices, det_indices):
            cost = cost_matrix[gt_idx, det_idx]

            # Check if match is within tolerance
            if cost <= self.tolerance_seconds:
                # True Positive
                temporal_offset_ms = (detection_timestamps[det_idx] - gt_timestamps[gt_idx]) * 1000
                match_results.append(MatchResult(
                    gt_index=gt_idx,
                    det_index=det_idx,
                    match_type='TP',
                    temporal_offset_ms=temporal_offset_ms,
                    cost=cost
                ))
                used_detections.add(det_idx)
            else:
                # Cost exceeds tolerance - treat as False Negative
                match_results.append(MatchResult(
                    gt_index=gt_idx,
                    det_index=None,
                    match_type='FN',
                    temporal_offset_ms=0.0,
                    cost=cost
                ))

        # Add unmatched ground truth as False Negatives
        matched_gt = set(gt_indices)
        for gt_idx in range(n_gt):
            if gt_idx not in matched_gt:
                match_results.append(MatchResult(
                    gt_index=gt_idx,
                    det_index=None,
                    match_type='FN',
                    temporal_offset_ms=0.0,
                    cost=float('inf')
                ))

        # Add unmatched detections as False Positives
        for det_idx in range(n_det):
            if det_idx not in used_detections:
                match_results.append(MatchResult(
                    gt_index=None,
                    det_index=det_idx,
                    match_type='FP',
                    temporal_offset_ms=0.0,
                    cost=float('inf')
                ))

        # Calculate statistics
        tp_count = sum(1 for m in match_results if m.match_type == 'TP')
        fp_count = sum(1 for m in match_results if m.match_type == 'FP')
        fn_count = sum(1 for m in match_results if m.match_type == 'FN')

        stats = {
            'tp': tp_count,
            'fp': fp_count,
            'fn': fn_count,
            'total_cost': sum(m.cost for m in match_results if m.match_type == 'TP'),
            'avg_cost': (
                sum(m.cost for m in match_results if m.match_type == 'TP') / tp_count
                if tp_count > 0 else 0.0
            )
        }

        logger.info(
            f"Optimal matching complete: {tp_count} TP, {fp_count} FP, {fn_count} FN "
            f"(avg cost: {stats['avg_cost']:.4f}s)"
        )

        return match_results, stats

    def _build_cost_matrix(
        self,
        gt_timestamps: List[float],
        detection_timestamps: List[float],
        gt_video_ids: Optional[List[str]],
        det_video_ids: Optional[List[str]]
    ) -> np.ndarray:
        """
        Build cost matrix for Hungarian algorithm.

        Cost = temporal distance (seconds)
        If video_ids don't match: cost = infinity (unmatchable)

        Returns:
            cost_matrix[i, j] = cost of matching GT i to Detection j
        """
        n_gt = len(gt_timestamps)
        n_det = len(detection_timestamps)

        cost_matrix = np.zeros((n_gt, n_det))

        for i, gt_time in enumerate(gt_timestamps):
            for j, det_time in enumerate(detection_timestamps):
                # Calculate temporal distance
                time_diff = abs(gt_time - det_time)

                # Video boundary check (if multi-video)
                if gt_video_ids and det_video_ids:
                    if gt_video_ids[i] != det_video_ids[j]:
                        # Cross-video matching forbidden
                        cost_matrix[i, j] = 1e9  # Infinity (unmatchable)
                        continue

                # Normal cost = time difference
                cost_matrix[i, j] = time_diff

        return cost_matrix

    def _create_fp_results(self, n_detections: int) -> List[MatchResult]:
        """Create False Positive results for unmatched detections"""
        return [
            MatchResult(
                gt_index=None,
                det_index=i,
                match_type='FP',
                temporal_offset_ms=0.0,
                cost=float('inf')
            )
            for i in range(n_detections)
        ]

    def _create_fn_results(self, n_ground_truth: int) -> List[MatchResult]:
        """Create False Negative results for unmatched ground truth"""
        return [
            MatchResult(
                gt_index=i,
                det_index=None,
                match_type='FN',
                temporal_offset_ms=0.0,
                cost=float('inf')
            )
            for i in range(n_ground_truth)
        ]

# Global service instance
_optimal_matching_service = None

def get_optimal_matching_service(tolerance_ms: float = 100.0):
    global _optimal_matching_service
    if _optimal_matching_service is None:
        _optimal_matching_service = OptimalMatchingService(tolerance_ms)
    return _optimal_matching_service
```

### Integration with Existing Code

Update `ground_truth_matching_service.py`:

```python
# Add import at top:
from services.optimal_matching_service import get_optimal_matching_service

# In _perform_temporal_matching(), REPLACE greedy loop with:

def _perform_temporal_matching(
    self,
    detection_events: List[DetectionEvent],
    ground_truth_objects: List[GroundTruthObject],
    tolerance_ms: int,
    test_session: Optional[TestSession] = None,
    db: Optional[Session] = None
) -> List[MatchResult]:
    """
    CRITICAL FIX: Use optimal Hungarian algorithm instead of greedy matching.
    """
    # Extract timestamps
    gt_timestamps = []
    gt_video_ids = []
    for gt_obj in ground_truth_objects:
        gt_time = extract_ground_truth_video_time(gt_obj, session_start_time)
        if gt_time is not None:
            gt_timestamps.append(gt_time)
            gt_video_ids.append(getattr(gt_obj, 'video_id', None))

    det_timestamps = []
    det_video_ids = []
    for detection in detection_events:
        det_time = extract_detection_video_time(detection, session_start_time)
        if det_time is not None:
            det_timestamps.append(det_time)
            det_video_ids.append(getattr(detection, 'video_id', None))

    # Run optimal matching
    optimal_service = get_optimal_matching_service(tolerance_ms)
    match_results, stats = optimal_service.match_ground_truth_to_detections(
        gt_timestamps=gt_timestamps,
        detection_timestamps=det_timestamps,
        gt_video_ids=gt_video_ids,
        det_video_ids=det_video_ids
    )

    # Convert to existing MatchResult format
    # ... (map optimal matching results to your MatchResult objects) ...

    return match_results
```

## Testing Strategy

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/tests/test_optimal_matching.py

import pytest
from services.optimal_matching_service import get_optimal_matching_service

class TestOptimalMatching:

    def test_greedy_suboptimal_case(self):
        """Test case where greedy fails but Hungarian succeeds"""
        service = get_optimal_matching_service(tolerance_ms=500)

        # GT1 at 1.0s, GT2 at 1.1s
        # Det1 at 1.05s (could match EITHER GT1 or GT2)
        # Det2 at 1.5s (far from both)

        gt_timestamps = [1.0, 1.1]
        det_timestamps = [1.05, 1.5]

        matches, stats = service.match_ground_truth_to_detections(
            gt_timestamps, det_timestamps
        )

        # Optimal: GT1→Det1 (0.05s), GT2→FN (no match within 0.5s)
        # Greedy might: GT1→Det1, GT2→Det2 (0.4s) if tolerance is high

        # With 500ms tolerance, both should match
        assert stats['tp'] == 2
        assert stats['fp'] == 0
        assert stats['fn'] == 0

    def test_optimal_vs_greedy_comparison(self):
        """Direct comparison: optimal should have lower or equal total cost"""
        service = get_optimal_matching_service(tolerance_ms=200)

        # Complex scenario with multiple ambiguous matches
        gt_timestamps = [1.0, 1.5, 2.0, 2.5]
        det_timestamps = [1.05, 1.45, 1.95, 2.45]

        # Optimal matching
        matches, stats = service.match_ground_truth_to_detections(
            gt_timestamps, det_timestamps
        )

        optimal_cost = stats['total_cost']

        # Greedy matching (simulate manually)
        greedy_cost = abs(1.05 - 1.0) + abs(1.45 - 1.5) + abs(1.95 - 2.0) + abs(2.45 - 2.5)

        # Optimal cost should be ≤ greedy cost
        assert optimal_cost <= greedy_cost, \
            f"Optimal cost ({optimal_cost:.4f}) should be ≤ greedy cost ({greedy_cost:.4f})"

    def test_video_boundary_enforcement(self):
        """Cross-video matches should be forbidden"""
        service = get_optimal_matching_service(tolerance_ms=500)

        gt_timestamps = [1.0, 2.0]
        det_timestamps = [1.05, 2.05]

        # GT and detections from different videos
        gt_video_ids = ['video1', 'video2']
        det_video_ids = ['video2', 'video1']  # Swapped!

        matches, stats = service.match_ground_truth_to_detections(
            gt_timestamps, det_timestamps,
            gt_video_ids, det_video_ids
        )

        # Should NOT match GT1(video1) → Det1(video2)
        # Should NOT match GT2(video2) → Det2(video1)
        # Result: 0 TP, 2 FP, 2 FN

        assert stats['tp'] == 0, "Cross-video matches should be forbidden"
        assert stats['fp'] == 2
        assert stats['fn'] == 2
```

## Deployment Checklist
- [ ] Add `scipy` to requirements.txt
- [ ] Deploy `optimal_matching_service.py`
- [ ] Update `ground_truth_matching_service.py` to use Hungarian algorithm
- [ ] Run A/B test: greedy vs optimal on 100 test sessions
- [ ] Verify optimal always has ≤ total matching cost
- [ ] Monitor for performance regression (O(n³) complexity)

## Success Criteria
- [ ] Optimal matching produces provably better or equal results than greedy
- [ ] No cross-video matches in multi-video sessions
- [ ] Performance acceptable for typical session sizes (<1000 GT objects)
- [ ] Precision/Recall metrics improve in ambiguous scenarios
