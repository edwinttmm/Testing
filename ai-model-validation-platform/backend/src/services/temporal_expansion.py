"""
Temporal Expansion Module for Ground Truth Matching
===================================================

This module implements Option C: Post-Processing Temporal Expansion for ground truth matching.
It expands discrete detection events into multiple virtual detections at fixed intervals to
improve matching accuracy without modifying the core detection capture logic.

Key Features:
- Expands each detection into temporal window (default 500ms)
- Generates virtual detections at fixed intervals (default 40ms)
- Maintains parent detection tracking for deduplication
- Zero impact on database storage (expansion only during matching)
- Backward compatible with existing matching algorithm

Architecture:
    Detection Event (DB) → Temporal Expansion → Hungarian Matching → Collapse Duplicates → Results

Reference: RISK_ASSESSMENT_SUMMARY.md - Option C (Post-Processing Expansion)
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ExpandedDetection:
    """
    Represents a virtual detection created by temporal expansion.

    Attributes:
        virtual_id: Unique identifier for this virtual detection
        parent_detection_id: Original detection event ID
        timestamp: Timestamp of this virtual detection (ms)
        video_relative_timestamp: Video-relative time if available
        confidence_score: Confidence from parent detection
        bounding_box_x: X coordinate from parent detection
        bounding_box_y: Y coordinate from parent detection
        bounding_box_width: Width from parent detection
        bounding_box_height: Height from parent detection
        sequence_number: Position in expansion sequence (0-based)
        is_original: True if this is the original detection, not virtual
        video_id: Video ID from parent detection (for multi-video sequences)
        id: Alias for virtual_id (compatibility with matching code)
    """
    virtual_id: str
    parent_detection_id: str
    timestamp: float
    video_relative_timestamp: Optional[float]
    confidence_score: float
    bounding_box_x: Optional[float]
    bounding_box_y: Optional[float]
    bounding_box_width: Optional[float]
    bounding_box_height: Optional[float]
    sequence_number: int
    is_original: bool
    video_id: Optional[str] = None

    @property
    def id(self) -> str:
        """Alias for virtual_id for compatibility with matching code"""
        return self.virtual_id


def expand_detections_temporally(
    detections: List[any],
    window_ms: float = 500.0,
    interval_ms: float = 40.0,
    include_original: bool = True
) -> List[ExpandedDetection]:
    """
    Expand each detection into multiple virtual detections at fixed intervals.

    This function implements temporal expansion to improve ground truth matching accuracy
    by creating virtual detection samples across a time window. Each detection is expanded
    into N samples where N = ceil(window_ms / interval_ms).

    Example:
        Detection at t=1000ms with window_ms=500, interval_ms=40:
        - Virtual detections at: 1000, 1040, 1080, 1120, ..., 1500ms (13 samples)
        - All share the same parent_detection_id for deduplication

    Args:
        detections: List of detection events from database
        window_ms: Duration of temporal expansion window in milliseconds (default 500ms)
        interval_ms: Interval between virtual detections in milliseconds (default 40ms)
        include_original: If True, includes original detection at t=0 (recommended)

    Returns:
        List of ExpandedDetection objects (N × len(detections) samples)

    Performance:
        - Time Complexity: O(N × M) where N=detections, M=window_ms/interval_ms
        - Space Complexity: O(N × M) for expanded set
        - Typical: 100 detections × 13 samples = 1,300 expanded detections

    Notes:
        - Does NOT modify original detections
        - Does NOT write to database
        - All virtual detections reference parent for deduplication
        - Bounding boxes are copied from parent (static position assumption)
    """
    if not detections:
        logger.debug("No detections to expand")
        return []

    if window_ms <= 0:
        raise ValueError(f"window_ms must be positive, got {window_ms}")
    if interval_ms <= 0:
        raise ValueError(f"interval_ms must be positive, got {interval_ms}")
    if interval_ms > window_ms:
        logger.warning(
            f"interval_ms ({interval_ms}ms) > window_ms ({window_ms}ms), "
            f"will generate only 1-2 samples per detection"
        )

    expanded_detections = []
    num_intervals = int(window_ms / interval_ms) + (1 if include_original else 0)

    logger.info(
        f"Expanding {len(detections)} detections: "
        f"window={window_ms}ms, interval={interval_ms}ms, "
        f"samples_per_detection={num_intervals}"
    )

    for det_idx, detection in enumerate(detections):
        # Extract detection properties
        det_id = getattr(detection, 'id', f'det-{det_idx}')
        base_timestamp = float(getattr(detection, 'timestamp', 0.0))
        video_relative_ts = getattr(detection, 'video_relative_timestamp', None)
        # CRITICAL FIX: Handle None confidence values (some detections have confidence=None in DB)
        confidence_raw = getattr(detection, 'confidence', 0.0)
        confidence = float(confidence_raw) if confidence_raw is not None else 0.0
        video_id = getattr(detection, 'video_id', None)

        # Extract bounding box if available
        bbox_x = getattr(detection, 'bounding_box_x', None)
        bbox_y = getattr(detection, 'bounding_box_y', None)
        bbox_width = getattr(detection, 'bounding_box_width', None)
        bbox_height = getattr(detection, 'bounding_box_height', None)

        # Generate virtual detections across temporal window
        sequence_num = 0
        current_time_offset = 0.0

        while current_time_offset <= window_ms:
            # Calculate timestamps for this virtual detection
            virtual_timestamp = base_timestamp + (current_time_offset / 1000.0)  # Convert ms to seconds
            virtual_video_ts = None
            if video_relative_ts is not None:
                virtual_video_ts = video_relative_ts + (current_time_offset / 1000.0)

            # Create expanded detection
            expanded = ExpandedDetection(
                virtual_id=f"{det_id}-v{sequence_num}",
                parent_detection_id=det_id,
                timestamp=virtual_timestamp,
                video_relative_timestamp=virtual_video_ts,
                confidence_score=confidence,
                bounding_box_x=bbox_x,
                bounding_box_y=bbox_y,
                bounding_box_width=bbox_width,
                bounding_box_height=bbox_height,
                sequence_number=sequence_num,
                is_original=(sequence_num == 0 and include_original),
                video_id=video_id
            )

            expanded_detections.append(expanded)

            # Move to next interval
            sequence_num += 1
            current_time_offset += interval_ms

    logger.info(
        f"Temporal expansion complete: {len(detections)} → {len(expanded_detections)} "
        f"(expansion factor: {len(expanded_detections) / len(detections):.1f}×)"
    )

    return expanded_detections


def collapse_duplicates(
    matches: List[any],
    strategy: str = "first"
) -> List[any]:
    """
    Collapse duplicate matches by parent detection ID.

    After Hungarian matching with expanded detections, multiple virtual detections
    from the same parent may match to ground truth. This function deduplicates
    by keeping only one match per parent detection.

    Strategies:
        - "first": Keep earliest match (smallest temporal offset)
        - "best": Keep match with highest confidence
        - "closest": Keep match with smallest temporal offset (absolute)
        - "original": Keep match from original detection (is_original=True)

    Args:
        matches: List of MatchingResult objects from Hungarian matching
        strategy: Deduplication strategy (default "first")

    Returns:
        List of deduplicated MatchingResult objects (1 per parent detection)

    Performance:
        - Time Complexity: O(N) where N=number of matches
        - Space Complexity: O(P) where P=number of parent detections

    Example:
        Input matches (3 virtual detections from same parent):
          - Match(detection_id="det-1-v0", ground_truth_id="gt-5", offset=10ms)
          - Match(detection_id="det-1-v1", ground_truth_id="gt-5", offset=50ms)
          - Match(detection_id="det-1-v2", ground_truth_id="gt-5", offset=90ms)

        Output (strategy="first"):
          - Match(detection_id="det-1-v0", ground_truth_id="gt-5", offset=10ms)
    """
    if not matches:
        return []

    if strategy not in ["first", "best", "closest", "original"]:
        raise ValueError(f"Invalid strategy: {strategy}. Must be one of: first, best, closest, original")

    # Group matches by parent detection ID
    parent_groups: Dict[str, List[any]] = {}

    for match in matches:
        # Extract parent ID from detection_id (format: "parent-vN" or just "parent")
        detection_id = match.detection_id

        # Parse parent ID from virtual detection ID
        if '-v' in detection_id:
            parent_id = detection_id.rsplit('-v', 1)[0]
        else:
            parent_id = detection_id

        if parent_id not in parent_groups:
            parent_groups[parent_id] = []
        parent_groups[parent_id].append(match)

    # Select best match for each parent based on strategy
    deduplicated_matches = []

    for parent_id, group in parent_groups.items():
        if len(group) == 1:
            # No duplicates for this parent
            deduplicated_matches.append(group[0])
            continue

        # Select based on strategy
        if strategy == "first":
            # Keep match with earliest timestamp
            best_match = min(group, key=lambda m: m.temporal_offset_ms)

        elif strategy == "best":
            # Keep match with highest confidence
            best_match = max(group, key=lambda m: m.confidence_score)

        elif strategy == "closest":
            # Keep match with smallest absolute temporal offset
            best_match = min(group, key=lambda m: abs(m.temporal_offset_ms))

        elif strategy == "original":
            # Keep match from original detection (sequence_number=0)
            # Fallback to "first" if original not found
            original_matches = [m for m in group if '-v0' in m.detection_id or '-v' not in m.detection_id]
            if original_matches:
                best_match = original_matches[0]
            else:
                best_match = min(group, key=lambda m: m.temporal_offset_ms)

        # Update detection_id to parent ID (remove virtual suffix)
        best_match.detection_id = parent_id
        deduplicated_matches.append(best_match)

    logger.debug(
        f"Collapsed {len(matches)} matches → {len(deduplicated_matches)} "
        f"(removed {len(matches) - len(deduplicated_matches)} duplicates)"
    )

    return deduplicated_matches


def get_expansion_statistics(
    original_count: int,
    expanded_count: int,
    window_ms: float,
    interval_ms: float
) -> Dict[str, any]:
    """
    Calculate statistics about temporal expansion for logging/debugging.

    Args:
        original_count: Number of original detections
        expanded_count: Number of expanded detections
        window_ms: Expansion window size
        interval_ms: Interval between samples

    Returns:
        Dictionary with expansion statistics
    """
    expansion_factor = expanded_count / original_count if original_count > 0 else 0
    expected_samples_per_detection = int(window_ms / interval_ms) + 1

    return {
        "original_detections": original_count,
        "expanded_detections": expanded_count,
        "expansion_factor": expansion_factor,
        "expected_samples_per_detection": expected_samples_per_detection,
        "actual_avg_samples_per_detection": expansion_factor,
        "window_ms": window_ms,
        "interval_ms": interval_ms,
        "temporal_coverage_ms": window_ms,
        "sample_density_hz": 1000.0 / interval_ms if interval_ms > 0 else 0
    }


def validate_expansion_config(window_ms: float, interval_ms: float) -> Tuple[bool, Optional[str]]:
    """
    Validate temporal expansion configuration parameters.

    Args:
        window_ms: Expansion window in milliseconds
        interval_ms: Interval between samples in milliseconds

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_expansion_config(500, 40)
        (True, None)

        >>> validate_expansion_config(-100, 40)
        (False, "window_ms must be positive")

        >>> validate_expansion_config(500, 0)
        (False, "interval_ms must be positive")
    """
    if window_ms <= 0:
        return False, f"window_ms must be positive, got {window_ms}"

    if interval_ms <= 0:
        return False, f"interval_ms must be positive, got {interval_ms}"

    if window_ms > 10000:
        return False, f"window_ms too large ({window_ms}ms), max 10000ms to prevent memory issues"

    if interval_ms < 1:
        return False, f"interval_ms too small ({interval_ms}ms), min 1ms to prevent explosion"

    samples_per_detection = int(window_ms / interval_ms) + 1
    if samples_per_detection > 1000:
        return False, (
            f"Configuration would generate {samples_per_detection} samples per detection, "
            f"max 1000 allowed. Increase interval_ms or decrease window_ms."
        )

    if interval_ms > window_ms:
        return True, f"Warning: interval_ms ({interval_ms}ms) > window_ms ({window_ms}ms), will generate only 1-2 samples"

    return True, None
