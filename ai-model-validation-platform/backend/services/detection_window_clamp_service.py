"""
Detection Window Clamp Service

Prevents overlapping detection windows in multi-video sequences by implementing
intelligent grace period clamping and temporal assignment algorithms.

Problem Solved:
- Video transitions create overlapping detection windows (360ms overlap zones)
- Grace period (2000ms) extends before each video start
- Next video also has 2000ms grace period, causing non-deterministic assignment
- Overlap = 2000ms + transition_gap causes detection assignment conflicts

Solution:
- Implement detection window clamping with gap-splitting algorithm
- Use temporal distance for tie-breaking in overlap zones
- Ensure deterministic video assignment for all detections
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Import centralized timing configuration
from config.timing_config import GRACE_PERIOD_MS

logger = logging.getLogger(__name__)


@dataclass
class VideoTiming:
    """Video timing information for window calculation"""
    video_id: str
    sequence_position: int
    start_time: float  # Unix timestamp (seconds)
    end_time: Optional[float] = None  # Unix timestamp (seconds), None if ongoing
    duration_ms: Optional[float] = None
    video_play_offset_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClampedWindow:
    """Clamped detection window with no overlaps"""
    video_id: str
    sequence_position: int
    start_time: float  # Clamped grace start time
    end_time: float  # Video end time or next video's clamped start
    grace_period_applied_ms: float  # Actual grace period used
    grace_period_original_ms: float  # Original grace period requested
    is_clamped: bool  # Whether clamping was applied
    clamp_reason: Optional[str] = None  # Why clamping occurred
    overlap_detected: bool = False  # Whether overlap was detected


# Use centralized grace period configuration (imported from config.timing_config)
DEFAULT_GRACE_PERIOD_MS = GRACE_PERIOD_MS  # 2000ms from centralized config

# Minimum grace period to maintain when clamping (100ms)
# This is a lower bound for clamped windows, NOT the standard grace period
MIN_GRACE_PERIOD_MS = 100


class DetectionWindowClampService:
    """
    Service for clamping detection windows to prevent overlaps in multi-video sequences.

    Implements intelligent grace period management to ensure deterministic detection
    assignment while maximizing capture windows for each video.
    """

    def __init__(self, grace_period_ms: float = DEFAULT_GRACE_PERIOD_MS):
        """
        Initialize the detection window clamp service.

        Args:
            grace_period_ms: Default grace period in milliseconds
        """
        self.grace_period_ms = grace_period_ms
        logger.info(f"Detection window clamp service initialized with {grace_period_ms}ms grace period")

    def clamp_detection_windows(
        self,
        video_timings: List[VideoTiming],
        grace_period_ms: Optional[float] = None
    ) -> List[ClampedWindow]:
        """
        Prevent overlapping detection windows by clamping grace periods.

        Algorithm:
        1. Each video gets full grace period if possible
        2. If overlap detected, split the gap 50/50
        3. Use temporal distance for tie-breaking
        4. Ensure minimum grace period is maintained

        Args:
            video_timings: List of video timing information
            grace_period_ms: Override grace period (uses default if None)

        Returns:
            List of clamped detection windows with no overlaps
        """
        if not video_timings:
            logger.warning("No video timings provided for clamping")
            return []

        grace_ms = grace_period_ms or self.grace_period_ms
        grace_seconds = grace_ms / 1000.0

        # Sort videos by start time
        sorted_videos = sorted(video_timings, key=lambda x: x.start_time)

        windows: List[ClampedWindow] = []

        for i, timing in enumerate(sorted_videos):
            # Calculate desired grace start (may be clamped)
            desired_grace_start = timing.start_time - grace_seconds

            # Check for overlap with previous video
            if i > 0:
                prev_window = windows[-1]
                prev_end = prev_window.end_time

                if desired_grace_start < prev_end:
                    # OVERLAP DETECTED - split the gap 50/50
                    gap_seconds = timing.start_time - sorted_videos[i-1].start_time

                    if gap_seconds <= 0:
                        logger.error(
                            f"Invalid video sequence: Video {timing.video_id} starts at or before "
                            f"previous video {sorted_videos[i-1].video_id}"
                        )
                        # Use minimal separation (100ms)
                        actual_grace_start = prev_end + 0.1
                        clamp_reason = "zero_gap_minimal_separation"
                    else:
                        # Split the gap evenly between videos
                        gap_midpoint = sorted_videos[i-1].start_time + (gap_seconds / 2.0)

                        # Update previous window's end time to midpoint
                        prev_window.end_time = gap_midpoint
                        prev_window.is_clamped = True
                        prev_window.clamp_reason = f"overlap_split_with_{timing.video_id}"

                        # Set current grace start to midpoint
                        actual_grace_start = gap_midpoint
                        clamp_reason = f"overlap_split_with_{sorted_videos[i-1].video_id}"

                        logger.info(
                            f"Overlap detected between {sorted_videos[i-1].video_id} and {timing.video_id}: "
                            f"split gap at {gap_midpoint:.3f}s (gap: {gap_seconds:.3f}s)"
                        )

                    is_clamped = True
                    overlap_detected = True
                    actual_grace_ms = (timing.start_time - actual_grace_start) * 1000.0
                else:
                    # No overlap - use full grace period
                    actual_grace_start = desired_grace_start
                    is_clamped = False
                    clamp_reason = None
                    overlap_detected = False
                    actual_grace_ms = grace_ms
            else:
                # First video - use full grace period
                actual_grace_start = desired_grace_start
                is_clamped = False
                clamp_reason = None
                overlap_detected = False
                actual_grace_ms = grace_ms

            # Determine window end time
            if timing.end_time is not None:
                window_end = timing.end_time
            elif i < len(sorted_videos) - 1:
                # Not the last video and no explicit end - use next video's grace start
                next_timing = sorted_videos[i + 1]
                window_end = next_timing.start_time  # Will be clamped in next iteration
            else:
                # Last video without end time - use start + duration or start + grace
                if timing.duration_ms:
                    window_end = timing.start_time + (timing.duration_ms / 1000.0)
                else:
                    # Open-ended window
                    window_end = timing.start_time + grace_seconds * 2  # Allow detections after start

            # Create clamped window
            window = ClampedWindow(
                video_id=timing.video_id,
                sequence_position=timing.sequence_position,
                start_time=actual_grace_start,
                end_time=window_end,
                grace_period_applied_ms=actual_grace_ms,
                grace_period_original_ms=grace_ms,
                is_clamped=is_clamped,
                clamp_reason=clamp_reason,
                overlap_detected=overlap_detected
            )

            windows.append(window)

            logger.debug(
                f"Window {i+1}/{len(sorted_videos)}: {timing.video_id} "
                f"[{actual_grace_start:.3f}s - {window_end:.3f}s] "
                f"(grace: {actual_grace_ms:.0f}ms, clamped: {is_clamped})"
            )

        return windows

    def assign_detection_to_video(
        self,
        detection_timestamp: float,
        clamped_windows: List[ClampedWindow]
    ) -> Optional[Tuple[str, str]]:
        """
        Assign a detection to a video using clamped windows.

        Uses temporal distance for tie-breaking when detection falls in overlap zone.

        Args:
            detection_timestamp: Unix timestamp of detection
            clamped_windows: List of clamped detection windows

        Returns:
            Tuple of (video_id, assignment_reason) or None if no match
        """
        if not clamped_windows:
            logger.warning("No clamped windows available for detection assignment")
            return None

        # Sort windows by start time
        sorted_windows = sorted(clamped_windows, key=lambda x: x.start_time)

        # Find windows that contain the detection
        matching_windows = []
        for window in sorted_windows:
            if window.start_time <= detection_timestamp < window.end_time:
                matching_windows.append(window)

        if not matching_windows:
            logger.warning(
                f"Detection at {detection_timestamp:.3f}s does not fall within any window"
            )
            return None

        if len(matching_windows) == 1:
            # Single match - deterministic assignment
            window = matching_windows[0]
            reason = "exact_window_match"
            logger.debug(
                f"Detection at {detection_timestamp:.3f}s assigned to {window.video_id} ({reason})"
            )
            return (window.video_id, reason)

        # Multiple matches (should not happen with proper clamping, but handle defensively)
        logger.warning(
            f"Detection at {detection_timestamp:.3f}s matches {len(matching_windows)} windows - "
            f"using temporal distance tie-breaker"
        )

        # Use temporal distance to closest video start
        closest_window = None
        min_distance = float('inf')

        for window in matching_windows:
            # Find original video start time from sorted_windows
            video_start = None
            for w in sorted_windows:
                if w.video_id == window.video_id:
                    # Use sequence position to find original start
                    video_start = w.end_time - (w.grace_period_applied_ms / 1000.0)
                    break

            if video_start is None:
                continue

            distance = abs(detection_timestamp - video_start)
            if distance < min_distance:
                min_distance = distance
                closest_window = window

        if closest_window:
            reason = f"temporal_distance_tiebreak_{min_distance:.3f}s"
            logger.info(
                f"Detection at {detection_timestamp:.3f}s assigned to {closest_window.video_id} "
                f"by temporal distance ({reason})"
            )
            return (closest_window.video_id, reason)

        logger.error(f"Failed to assign detection at {detection_timestamp:.3f}s")
        return None

    def get_window_statistics(self, clamped_windows: List[ClampedWindow]) -> Dict[str, Any]:
        """
        Get statistics about clamped windows.

        Args:
            clamped_windows: List of clamped detection windows

        Returns:
            Dictionary containing window statistics
        """
        if not clamped_windows:
            return {
                'total_windows': 0,
                'clamped_windows': 0,
                'overlap_detections': 0,
                'average_grace_period_ms': 0.0,
                'min_grace_period_ms': 0.0,
                'max_grace_period_ms': 0.0
            }

        clamped_count = sum(1 for w in clamped_windows if w.is_clamped)
        overlap_count = sum(1 for w in clamped_windows if w.overlap_detected)
        grace_periods = [w.grace_period_applied_ms for w in clamped_windows]

        return {
            'total_windows': len(clamped_windows),
            'clamped_windows': clamped_count,
            'overlap_detections': overlap_count,
            'average_grace_period_ms': sum(grace_periods) / len(grace_periods),
            'min_grace_period_ms': min(grace_periods),
            'max_grace_period_ms': max(grace_periods),
            'clamp_percentage': (clamped_count / len(clamped_windows)) * 100.0
        }


# Global service instance
_clamp_service: Optional[DetectionWindowClampService] = None


def get_detection_window_clamp_service(
    grace_period_ms: float = DEFAULT_GRACE_PERIOD_MS
) -> DetectionWindowClampService:
    """
    Get global detection window clamp service instance (singleton).

    Args:
        grace_period_ms: Default grace period in milliseconds

    Returns:
        DetectionWindowClampService instance
    """
    global _clamp_service

    if _clamp_service is None:
        _clamp_service = DetectionWindowClampService(grace_period_ms)

    return _clamp_service


# Convenience functions
def clamp_video_windows(
    video_timings: List[VideoTiming],
    grace_period_ms: Optional[float] = None
) -> List[ClampedWindow]:
    """Clamp video detection windows to prevent overlaps"""
    service = get_detection_window_clamp_service()
    return service.clamp_detection_windows(video_timings, grace_period_ms)


def assign_detection(
    detection_timestamp: float,
    clamped_windows: List[ClampedWindow]
) -> Optional[Tuple[str, str]]:
    """Assign detection to video using clamped windows"""
    service = get_detection_window_clamp_service()
    return service.assign_detection_to_video(detection_timestamp, clamped_windows)


# Export key components
__all__ = [
    "VideoTiming",
    "ClampedWindow",
    "DetectionWindowClampService",
    "get_detection_window_clamp_service",
    "clamp_video_windows",
    "assign_detection"
]
