"""
Quality Warning System for Degraded Detections

This service checks and warns about timing quality issues that affect validation reliability.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer

from database import SessionLocal
from models import DetectionEvent, TestSession

logger = logging.getLogger(__name__)


class QualityWarning:
    """Check and warn about detection timing quality issues"""

    @staticmethod
    def check_session_quality(session_id: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Check session quality and generate warnings

        Args:
            session_id: Test session identifier
            db: Optional database session (creates one if not provided)

        Returns:
            List of warning dictionaries with severity and message
        """
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            warnings = []

            # Get detection stats
            total = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).count()

            validated = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.usable_for_validation == True
            ).count()

            degraded = total - validated

            # Generate warnings based on quality metrics
            if total == 0:
                warnings.append({
                    'severity': 'ERROR',
                    'code': 'NO_DETECTIONS',
                    'message': 'No detections captured during test session',
                    'impact': 'Cannot calculate metrics - test invalid',
                    'recommendation': 'Verify LabJack connection and retry test'
                })
            elif validated == 0:
                warnings.append({
                    'severity': 'ERROR',
                    'code': 'ALL_DEGRADED',
                    'message': f'All {total} detections have degraded timing',
                    'impact': 'Results unreliable - timing sync issues throughout test',
                    'recommendation': 'Check video timing synchronization and timing_degraded flags'
                })
            elif validated < total * 0.5:
                warnings.append({
                    'severity': 'WARNING',
                    'code': 'LOW_QUALITY_RATE',
                    'message': f'Only {validated}/{total} detections validated ({degraded} degraded)',
                    'impact': 'Results may be unreliable due to timing issues',
                    'recommendation': 'Review timing synchronization quality'
                })
            elif validated < total * 0.9:
                warnings.append({
                    'severity': 'INFO',
                    'code': 'SOME_DEGRADED',
                    'message': f'{degraded}/{total} detections have degraded timing',
                    'impact': 'Most detections valid, some timing issues detected',
                    'recommendation': 'Results generally reliable, review degraded detections'
                })

            # Check session-level timing degradation flag
            session = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if session and hasattr(session, 'timing_degraded') and session.timing_degraded:
                warnings.append({
                    'severity': 'WARNING',
                    'code': 'SESSION_TIMING_DEGRADED',
                    'message': 'Session marked with degraded timing',
                    'impact': 'Video timing synchronization was lost during test',
                    'recommendation': 'Results should be reviewed carefully'
                })

            # Calculate validation rate for logging
            validation_rate = (validated / total * 100) if total > 0 else 0

            logger.info(
                f"Quality check for session {session_id}: "
                f"total={total}, validated={validated}, degraded={degraded}, "
                f"rate={validation_rate:.1f}%, warnings={len(warnings)}"
            )

            return warnings

        except Exception as e:
            logger.error(f"Error checking session quality for {session_id}: {e}", exc_info=True)
            return [{
                'severity': 'ERROR',
                'code': 'QUALITY_CHECK_FAILED',
                'message': f'Failed to check quality: {str(e)}',
                'impact': 'Cannot assess detection quality',
                'recommendation': 'Check database connectivity'
            }]
        finally:
            if should_close:
                db.close()

    @staticmethod
    def get_quality_statistics(session_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get detailed quality statistics for a session

        Args:
            session_id: Test session identifier
            db: Optional database session

        Returns:
            Dictionary with detailed quality metrics
        """
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            # Get detection counts by quality
            result = db.query(
                func.count(DetectionEvent.id).label('total'),
                func.sum(func.cast(DetectionEvent.usable_for_validation, Integer)).label('validated'),
                func.sum(func.cast(DetectionEvent.timing_degraded, Integer)).label('degraded')
            ).filter(
                DetectionEvent.test_session_id == session_id
            ).first()

            total = result.total or 0
            validated = result.validated or 0
            degraded = result.degraded or 0

            validation_rate = (validated / total * 100) if total > 0 else 0
            degradation_rate = (degraded / total * 100) if total > 0 else 0

            return {
                'total_detections': total,
                'validated_detections': validated,
                'degraded_detections': degraded,
                'non_validated_detections': total - validated,
                'validation_rate': round(validation_rate, 2),
                'degradation_rate': round(degradation_rate, 2),
                'quality_level': (
                    'EXCELLENT' if validation_rate >= 95 else
                    'GOOD' if validation_rate >= 80 else
                    'FAIR' if validation_rate >= 50 else
                    'POOR'
                )
            }

        except Exception as e:
            logger.error(f"Error getting quality statistics for {session_id}: {e}", exc_info=True)
            return {
                'error': str(e),
                'total_detections': 0,
                'validated_detections': 0,
                'degraded_detections': 0
            }
        finally:
            if should_close:
                db.close()


# Convenience function for quick quality check
def check_quality(session_id: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """Quick quality check for a session"""
    return QualityWarning.check_session_quality(session_id, db)


def get_quality_stats(session_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Quick quality statistics for a session"""
    return QualityWarning.get_quality_statistics(session_id, db)
