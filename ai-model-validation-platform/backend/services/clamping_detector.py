"""
Timing Clamping Detector Service

This service detects when detection timestamps are clamped to video duration boundaries
and flags them appropriately instead of silently hiding the errors.

CRITICAL FIX: This addresses the issue where detections exceeding video duration were
silently clamped, hiding timing errors that should affect validation suitability.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ClampingDetector:
    """Detects and flags timing clamping in detection events"""

    def __init__(self):
        self.logger = logger
        self.tolerance_ms = 50  # 50ms tolerance for floating point comparisons

    def check_and_flag_clamping(
        self,
        detection,
        video_duration: float
    ) -> bool:
        """
        Check if detection timestamp was clamped and flag it appropriately.

        CRITICAL FIX: Instead of silently clamping, this explicitly flags clamped
        detections so they can be marked as non-usable for validation.

        Args:
            detection: DetectionEvent object
            video_duration: Video duration in seconds

        Returns:
            True if clamping was detected and flagged, False otherwise
        """
        try:
            video_relative = detection.video_relative_timestamp

            if video_relative is None:
                return False

            # Check if timestamp exceeds video duration (with tolerance)
            tolerance_s = self.tolerance_ms / 1000.0

            if video_relative > video_duration + tolerance_s:
                # CLAMPING DETECTED
                original_timestamp = video_relative

                # Flag the detection
                detection.timing_clamped = True
                detection.original_video_relative = original_timestamp

                # Clamp to video duration
                detection.video_relative_timestamp = video_duration

                # Add quality notes
                clamp_amount = original_timestamp - video_duration
                quality_note = (
                    f"Timing clamped: exceeded video duration by {clamp_amount:.3f}s "
                    f"(original: {original_timestamp:.3f}s, clamped to: {video_duration:.3f}s)"
                )

                # Append to existing quality notes if present
                if detection.quality_notes:
                    detection.quality_notes += f"; {quality_note}"
                else:
                    detection.quality_notes = quality_note

                self.logger.warning(
                    f"⚠️ Detection {detection.id} CLAMPED: "
                    f"timestamp {original_timestamp:.3f}s exceeded video duration {video_duration:.3f}s by {clamp_amount:.3f}s"
                )

                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to check clamping for detection: {e}", exc_info=True)
            return False

    def check_multiple_detections(
        self,
        detections: list,
        video_duration: float
    ) -> dict:
        """
        Check multiple detections for clamping.

        Args:
            detections: List of DetectionEvent objects
            video_duration: Video duration in seconds

        Returns:
            Dictionary with clamping statistics
        """
        try:
            clamped_count = 0
            total_clamp_amount = 0.0

            for detection in detections:
                if self.check_and_flag_clamping(detection, video_duration):
                    clamped_count += 1
                    if detection.original_video_relative:
                        clamp_amount = detection.original_video_relative - detection.video_relative_timestamp
                        total_clamp_amount += clamp_amount

            if clamped_count > 0:
                avg_clamp = total_clamp_amount / clamped_count
                self.logger.warning(
                    f"⚠️ Clamping summary: {clamped_count}/{len(detections)} detections clamped, "
                    f"average clamp amount: {avg_clamp:.3f}s"
                )

            return {
                'total_detections': len(detections),
                'clamped_count': clamped_count,
                'average_clamp_amount': total_clamp_amount / clamped_count if clamped_count > 0 else 0.0,
                'clamping_rate': clamped_count / len(detections) if detections else 0.0
            }

        except Exception as e:
            self.logger.error(f"Failed to check multiple detections for clamping: {e}", exc_info=True)
            return {
                'total_detections': len(detections) if detections else 0,
                'clamped_count': 0,
                'average_clamp_amount': 0.0,
                'clamping_rate': 0.0,
                'error': str(e)
            }


# Global service instance
_clamping_detector_instance: Optional[ClampingDetector] = None


def get_clamping_detector() -> ClampingDetector:
    """Get global clamping detector instance (singleton)"""
    global _clamping_detector_instance

    if _clamping_detector_instance is None:
        _clamping_detector_instance = ClampingDetector()

    return _clamping_detector_instance


# Convenience function
def check_and_flag_clamping(detection, video_duration: float) -> bool:
    """
    Convenience function to check and flag timing clamping.

    This is the primary entry point for detecting clamped timestamps.

    Args:
        detection: DetectionEvent object
        video_duration: Video duration in seconds

    Returns:
        True if clamping was detected, False otherwise
    """
    detector = get_clamping_detector()
    return detector.check_and_flag_clamping(detection, video_duration)


__all__ = [
    "ClampingDetector",
    "get_clamping_detector",
    "check_and_flag_clamping"
]
