# Agent #7: Detection Window Overlap Fix

## Mission
Fix overlapping detection windows and implement closest-match assignment logic.

## Problem Analysis

**Current Issue:** Detection windows overlap by 360ms between videos

**Example:**
- Video 1: `[10.5s - 2.0s grace, 10.5s + 5.0s duration] = [8.5s, 15.5s]`
- Video 2: `[20.0s - 2.0s grace, 20.0s + 5.0s duration] = [18.0s, 25.0s]`
- Gap between videos: 4.5s (no overlap) ✅

**BUT** if videos are back-to-back:
- Video 1 ends: 15.5s
- Video 2 grace starts: 18.0s
- **If Video 2 starts at 15.86s instead of 20.0s:**
  - Video 2 grace: `[15.86 - 2.0, 15.86 + 5.0] = [13.86s, 20.86s]`
  - **OVERLAP: [13.86s, 15.5s] = 1.64 seconds = 1640ms!!!**

## Root Cause

**File:** `ground_truth_matching_service.py`, Line 768

```python
# GREEDY FIRST-MATCH (vulnerable to overlaps):
for i, detection in enumerate(detection_events):
    if i in used_detections:
        continue  # Skip already matched

    detection_time = extract_detection_video_time(detection, session_start_time)
    if detection_time is None:
        continue

    time_diff = abs(detection_time - gt_time)

    # BUG: Takes FIRST match within tolerance, not CLOSEST
    if time_diff <= tolerance_seconds and time_diff < best_time_diff:
        best_match = (i, detection)
        best_time_diff = time_diff
```

**Problem:** When windows overlap, a detection at 14.5s could match GT in EITHER video:
- Video 1 GT at 14.0s → `time_diff = 0.5s` (within 2.0s tolerance)
- Video 2 GT at 14.8s → `time_diff = 0.3s` (closer match, but might not be checked if Video 1 matched first)

## Fix Implementation

### Solution 1: Clamp Detection Windows to Prevent Overlap

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/services/detection_window_clamp_service.py

"""
Detection Window Clamping Service

Prevents overlapping windows by clamping grace periods to not exceed video boundaries.

ALGORITHM:
1. Sort videos by start time
2. For each video:
   - Calculate unclamped grace window: [start - grace_period, end]
   - Clamp grace start to previous video's end (if exists)
   - Ensure no overlap with next video's grace start
"""

import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class VideoWindow:
    """Detection window for a single video"""
    video_id: str
    start_time: float
    end_time: float
    grace_start: float  # Clamped grace period start
    grace_end: float    # Same as end_time
    duration: float
    sequence_order: int

class DetectionWindowClampService:
    """Clamp detection windows to prevent overlaps in multi-video sequences"""

    def __init__(self, grace_period_ms: float = 2000):
        self.grace_period_seconds = grace_period_ms / 1000.0

    def calculate_non_overlapping_windows(
        self,
        videos: List[Dict[str, any]]
    ) -> List[VideoWindow]:
        """
        Calculate clamped detection windows that don't overlap.

        Args:
            videos: List of video dicts with start_time, duration, video_id

        Returns:
            List of VideoWindow with clamped boundaries
        """
        # Sort videos by start time
        sorted_videos = sorted(videos, key=lambda v: v['start_time'])

        windows = []
        prev_end_time = None

        for idx, video in enumerate(sorted_videos):
            start_time = video['start_time']
            duration = video['duration']
            end_time = start_time + duration

            # Calculate unclamped grace start
            grace_start_unclamped = start_time - self.grace_period_seconds

            # CLAMP: grace_start cannot be before previous video's end
            if prev_end_time is not None:
                grace_start = max(grace_start_unclamped, prev_end_time)

                if grace_start != grace_start_unclamped:
                    clamped_amount_ms = (grace_start - grace_start_unclamped) * 1000
                    logger.warning(
                        f"⚠️  Video {video['video_id']}: Grace period clamped by {clamped_amount_ms:.1f}ms "
                        f"to prevent overlap with previous video"
                    )
            else:
                grace_start = grace_start_unclamped

            window = VideoWindow(
                video_id=video['video_id'],
                start_time=start_time,
                end_time=end_time,
                grace_start=grace_start,
                grace_end=end_time,
                duration=duration,
                sequence_order=idx
            )

            windows.append(window)
            prev_end_time = end_time

        # Verify no overlaps
        for i in range(len(windows) - 1):
            current = windows[i]
            next_win = windows[i + 1]

            if current.grace_end > next_win.grace_start:
                raise ValueError(
                    f"CRITICAL: Windows still overlap after clamping! "
                    f"Video {i} end={current.grace_end:.3f}s > "
                    f"Video {i+1} grace_start={next_win.grace_start:.3f}s"
                )

        logger.info(f"✅ Calculated {len(windows)} non-overlapping windows")
        return windows

    def assign_detection_to_window(
        self,
        detection_timestamp: float,
        windows: List[VideoWindow]
    ) -> Tuple[VideoWindow, str]:
        """
        Assign detection to closest non-overlapping window.

        Args:
            detection_timestamp: Detection epoch timestamp
            windows: List of non-overlapping windows

        Returns:
            (matched_window, assignment_reason)
        """
        # Find all windows that contain this timestamp
        containing_windows = []
        for window in windows:
            if window.grace_start <= detection_timestamp <= window.grace_end:
                containing_windows.append(window)

        if not containing_windows:
            # No window contains this timestamp - find closest
            closest_window = min(
                windows,
                key=lambda w: min(
                    abs(detection_timestamp - w.grace_start),
                    abs(detection_timestamp - w.grace_end)
                )
            )
            distance = min(
                abs(detection_timestamp - closest_window.grace_start),
                abs(detection_timestamp - closest_window.grace_end)
            )
            return closest_window, f"closest_window (distance={distance:.3f}s)"

        if len(containing_windows) == 1:
            # Only one window contains timestamp (expected case)
            return containing_windows[0], "exact_match"

        # CRITICAL: Multiple windows contain timestamp (should be impossible after clamping!)
        logger.error(
            f"❌ CRITICAL: Detection at {detection_timestamp:.3f}s matches MULTIPLE windows: "
            f"{[w.video_id for w in containing_windows]}"
        )

        # Fallback: Choose window closest to detection timestamp
        closest = min(
            containing_windows,
            key=lambda w: abs(detection_timestamp - w.start_time)
        )
        return closest, "fallback_closest (OVERLAP ERROR)"

# Global service instance
_clamp_service = None

def get_detection_window_clamp_service(grace_period_ms: float = 2000):
    global _clamp_service
    if _clamp_service is None:
        _clamp_service = DetectionWindowClampService(grace_period_ms)
    return _clamp_service
```

### Solution 2: Closest-Match Assignment Logic

Update `ground_truth_matching_service.py`:

```python
# In _perform_temporal_matching(), replace greedy first-match with closest-match:

def _perform_temporal_matching(
    self,
    detection_events: List[DetectionEvent],
    ground_truth_objects: List[GroundTruthObject],
    tolerance_ms: int,
    test_session: Optional[TestSession] = None,
    db: Optional[Session] = None
) -> List[MatchResult]:
    """
    CRITICAL FIX: Use CLOSEST-match instead of FIRST-match to handle overlaps.
    """
    tolerance_seconds = tolerance_ms / 1000.0
    match_results = []
    used_detections = set()

    # Phase 1: Match ground truth to CLOSEST detection (not first)
    for gt_obj in ground_truth_objects:
        best_match = None
        best_time_diff = float('inf')
        gt_time = extract_ground_truth_video_time(gt_obj, session_start_time)

        if gt_time is None:
            # ... handle missing timestamp ...
            continue

        # Find CLOSEST detection within tolerance
        for i, detection in enumerate(detection_events):
            if i in used_detections:
                continue

            # Video boundary validation (if multi-video)
            detection_video_id = getattr(detection, 'video_id', None)
            gt_video_id = getattr(gt_obj, 'video_id', None)

            if detection_video_id is not None and gt_video_id is not None:
                if detection_video_id != gt_video_id:
                    continue  # Skip cross-video matches

            detection_time = extract_detection_video_time(detection, session_start_time)
            if detection_time is None:
                continue

            time_diff = abs(detection_time - gt_time)

            # CRITICAL FIX: Find CLOSEST match, not FIRST match
            # This prevents greedy assignment in overlapping windows
            if time_diff <= tolerance_seconds:
                if time_diff < best_time_diff:
                    best_match = (i, detection)
                    best_time_diff = time_diff

        # If we found a match, mark it as used
        if best_match:
            detection_idx, detection = best_match
            used_detections.add(detection_idx)

            # ... create MatchResult as before ...

    # Phase 2: Mark remaining detections as False Positives
    # ... (no changes needed) ...
```

## Testing Strategy

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/tests/test_detection_window_overlap_fix.py

import pytest
from services.detection_window_clamp_service import get_detection_window_clamp_service

class TestDetectionWindowOverlapFix:

    def test_back_to_back_videos_no_overlap(self):
        """Back-to-back videos should have clamped grace periods with no overlap"""
        service = get_detection_window_clamp_service(grace_period_ms=2000)

        videos = [
            {'video_id': 'v1', 'start_time': 10.0, 'duration': 5.0},
            {'video_id': 'v2', 'start_time': 15.0, 'duration': 5.0},  # Immediately after v1
        ]

        windows = service.calculate_non_overlapping_windows(videos)

        # Video 1 window should be [8.0, 15.0] (no clamping needed)
        assert windows[0].grace_start == 8.0
        assert windows[0].grace_end == 15.0

        # Video 2 window should be [15.0, 20.0] (grace clamped from 13.0 to 15.0)
        assert windows[1].grace_start == 15.0, "Grace should be clamped to previous video's end"
        assert windows[1].grace_end == 20.0

    def test_gap_between_videos_no_clamp(self):
        """Videos with gaps should not need clamping"""
        service = get_detection_window_clamp_service(grace_period_ms=2000)

        videos = [
            {'video_id': 'v1', 'start_time': 10.0, 'duration': 5.0},
            {'video_id': 'v2', 'start_time': 20.0, 'duration': 5.0},  # 5s gap
        ]

        windows = service.calculate_non_overlapping_windows(videos)

        # No clamping needed
        assert windows[0].grace_start == 8.0
        assert windows[1].grace_start == 18.0

    def test_detection_assignment_boundary_case(self):
        """Detection at boundary should go to closest video"""
        service = get_detection_window_clamp_service(grace_period_ms=2000)

        videos = [
            {'video_id': 'v1', 'start_time': 10.0, 'duration': 5.0},
            {'video_id': 'v2', 'start_time': 15.0, 'duration': 5.0},
        ]

        windows = service.calculate_non_overlapping_windows(videos)

        # Detection at exactly 15.0s (boundary)
        window, reason = service.assign_detection_to_window(15.0, windows)

        # Should go to video 2 (start of that video)
        assert window.video_id == 'v2'
        assert reason == "exact_match"

    def test_overlapping_grace_periods_clamped(self):
        """Overlapping grace periods should be clamped to prevent double-matching"""
        service = get_detection_window_clamp_service(grace_period_ms=5000)  # Large grace period

        videos = [
            {'video_id': 'v1', 'start_time': 10.0, 'duration': 3.0},
            {'video_id': 'v2', 'start_time': 13.0, 'duration': 3.0},  # Only 3s gap
        ]

        windows = service.calculate_non_overlapping_windows(videos)

        # Video 1 window: [10.0 - 5.0, 10.0 + 3.0] = [5.0, 13.0]
        assert windows[0].grace_start == 5.0
        assert windows[0].grace_end == 13.0

        # Video 2 window: grace should be clamped from 8.0 to 13.0
        assert windows[1].grace_start == 13.0, "Grace should be clamped to prevent overlap"
        assert windows[1].grace_end == 16.0
```

## Deployment Checklist
- [ ] Add `detection_window_clamp_service.py` to services/
- [ ] Update `ground_truth_matching_service.py` with closest-match logic
- [ ] Add window clamping to video sequence orchestrator
- [ ] Run overlap tests to verify zero overlaps
- [ ] Monitor logs for "grace period clamped" warnings

## Success Criteria
- [ ] Zero overlapping windows in production
- [ ] Detections at boundaries assigned to correct video (closest match)
- [ ] Grace periods automatically clamped when videos are back-to-back
- [ ] No false TP/FP classification due to window overlaps
