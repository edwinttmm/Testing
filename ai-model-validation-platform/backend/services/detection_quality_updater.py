"""
Detection Quality Updater Service

This service updates usable_for_validation flags based on comprehensive quality assessment.
Fixes the contradiction where detections are marked as usable but have unreliable quality.
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QualityAssessmentResult:
    """Quality assessment result for a detection"""
    category: str  # "excellent", "good", "acceptable", "unreliable"
    validation_suitability: str  # "suitable", "conditional", "unsuitable"
    confidence_score: float  # 0.0-1.0
    notes: str  # Human-readable assessment notes
    should_be_usable: bool  # Whether detection should be usable for validation


class DetectionQualityUpdater:
    """
    Service to assess detection quality and update usable_for_validation flags.

    This fixes the critical bug where detections are marked as usable_for_validation=True
    but have quality assessments of "unreliable" or "unsuitable".
    """

    def __init__(self):
        self.logger = logger

    def assess_detection_quality(
        self,
        detection,
        timing_sync_result: Optional[Any] = None
    ) -> Optional[QualityAssessmentResult]:
        """
        Assess detection quality and determine if it should be usable for validation.

        Args:
            detection: DetectionEvent object
            timing_sync_result: TimingSynchronizationResult (if available)

        Returns:
            QualityAssessmentResult with assessment details
        """
        try:
            # Extract quality metrics from detection
            timing_degraded = getattr(detection, 'timing_degraded', False)
            timing_clamped = getattr(detection, 'timing_clamped', False)
            timing_sync_quality = getattr(detection, 'timing_sync_quality', None)

            # Default values
            category = "acceptable"
            validation_suitability = "suitable"
            confidence_score = 0.7
            notes_parts = []

            # Check session-level timing quality
            if timing_degraded:
                category = "unreliable"
                validation_suitability = "unsuitable"
                confidence_score = 0.3
                notes_parts.append("Session timing degraded")

            # Check if timing was clamped (detection exceeded video duration)
            if timing_clamped:
                if category != "unreliable":
                    category = "unreliable"
                validation_suitability = "unsuitable"
                confidence_score = min(confidence_score, 0.4)
                notes_parts.append("Timing clamped (exceeded video duration)")

            # Check timing sync quality if available
            if timing_sync_quality:
                if timing_sync_quality in ["excellent", "good"]:
                    # Keep or improve category
                    if category == "acceptable":
                        category = timing_sync_quality
                    confidence_score = max(confidence_score, 0.8 if timing_sync_quality == "excellent" else 0.7)
                elif timing_sync_quality == "poor":
                    category = "unreliable"
                    validation_suitability = "unsuitable"
                    confidence_score = 0.3
                    notes_parts.append(f"Poor timing sync quality: {timing_sync_quality}")

            # Integrate timing synchronization result if available
            if timing_sync_result:
                # Check if timing result has quality classification
                if hasattr(timing_sync_result, 'quality_classification') and timing_sync_result.quality_classification:
                    quality_class = timing_sync_result.quality_classification
                    category = quality_class.category
                    validation_suitability = quality_class.validation_suitability
                    confidence_score = getattr(timing_sync_result, 'confidence_score', confidence_score)

                    # Add warning flags to notes
                    if quality_class.warning_flags:
                        notes_parts.extend(quality_class.warning_flags)

            # Determine if detection should be usable based on final assessment
            should_be_usable = (
                category != "unreliable" and
                validation_suitability != "unsuitable" and
                not timing_degraded and
                not timing_clamped
            )

            # Build notes
            notes = "; ".join(notes_parts) if notes_parts else f"Quality: {category}, Validation: {validation_suitability}"

            result = QualityAssessmentResult(
                category=category,
                validation_suitability=validation_suitability,
                confidence_score=confidence_score,
                notes=notes,
                should_be_usable=should_be_usable
            )

            self.logger.debug(
                f"Quality assessment for detection: category={category}, "
                f"suitability={validation_suitability}, usable={should_be_usable}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Failed to assess detection quality: {e}", exc_info=True)
            return None

    def update_detection_quality_fields(
        self,
        detection,
        quality_result: QualityAssessmentResult
    ) -> None:
        """
        Update detection quality fields based on assessment result.

        This is the CRITICAL FIX that resolves the usable_for_validation contradiction.

        Args:
            detection: DetectionEvent object
            quality_result: QualityAssessmentResult from assessment
        """
        try:
            # Update quality tracking fields
            detection.quality_category = quality_result.category
            detection.quality_validation_suitability = quality_result.validation_suitability
            detection.quality_confidence_score = quality_result.confidence_score
            detection.quality_notes = quality_result.notes

            # CRITICAL FIX: Update usable_for_validation based on quality assessment
            # This ensures the flag matches the quality assessment
            original_usable = detection.usable_for_validation
            detection.usable_for_validation = quality_result.should_be_usable

            # Log if flag changed
            if original_usable != quality_result.should_be_usable:
                status_change = "✅ USABLE → ❌ NON-USABLE" if original_usable else "❌ NON-USABLE → ✅ USABLE"
                self.logger.warning(
                    f"🔄 Detection quality update changed validation flag: {status_change}\n"
                    f"   Category: {quality_result.category}\n"
                    f"   Validation Suitability: {quality_result.validation_suitability}\n"
                    f"   Reason: {quality_result.notes}"
                )

        except Exception as e:
            self.logger.error(f"Failed to update detection quality fields: {e}", exc_info=True)

    def assess_and_update_detection(
        self,
        detection,
        timing_sync_result: Optional[Any] = None
    ) -> Optional[QualityAssessmentResult]:
        """
        Convenience method to assess and update detection in one call.

        Args:
            detection: DetectionEvent object
            timing_sync_result: TimingSynchronizationResult (if available)

        Returns:
            QualityAssessmentResult or None if assessment failed
        """
        quality_result = self.assess_detection_quality(detection, timing_sync_result)

        if quality_result:
            self.update_detection_quality_fields(detection, quality_result)

        return quality_result


# Global service instance
_quality_updater_instance: Optional[DetectionQualityUpdater] = None


def get_detection_quality_updater() -> DetectionQualityUpdater:
    """Get global detection quality updater instance (singleton)"""
    global _quality_updater_instance

    if _quality_updater_instance is None:
        _quality_updater_instance = DetectionQualityUpdater()

    return _quality_updater_instance


# Convenience function
def assess_and_update_detection_quality(detection, timing_sync_result: Optional[Any] = None) -> Optional[QualityAssessmentResult]:
    """
    Convenience function to assess and update detection quality.

    This is the primary entry point for fixing usable_for_validation contradictions.

    Args:
        detection: DetectionEvent object
        timing_sync_result: TimingSynchronizationResult (optional)

    Returns:
        QualityAssessmentResult or None if failed
    """
    updater = get_detection_quality_updater()
    return updater.assess_and_update_detection(detection, timing_sync_result)


__all__ = [
    "DetectionQualityUpdater",
    "QualityAssessmentResult",
    "get_detection_quality_updater",
    "assess_and_update_detection_quality"
]
